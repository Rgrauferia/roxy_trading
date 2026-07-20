"""LLM-based signal agent prototype.

Provides a simple FastAPI router at `/api/ai` with a `/signal` endpoint
"""
import logging
import os
import json
import sqlite3
from typing import List, Optional

from roxy_time import utc_now_naive_iso
from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel
from tools.api_auth import require_api_key

logger = logging.getLogger("llm_agent")
router = APIRouter(prefix="/api/ai")


DB_PATH = os.path.join(os.getcwd(), "db", "roxy.db")


class SignalRequest(BaseModel):
    symbols: List[str]
    horizon: Optional[str] = "1d"
    context: Optional[dict] = None


class Signal(BaseModel):
    action: str
    symbol: str
    price: Optional[float] = None
    size_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    rationale: Optional[str] = None
    confidence: Optional[float] = None


def _model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _insert_ai_run(run_id: str, user: Optional[str], prompt: str, response: str, parsed_json: Optional[str], model: Optional[str] = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ai_runs (run_id, user, prompt, response, parsed_json, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)" ,
            (run_id, user, prompt, response, parsed_json, model, utc_now_naive_iso()),
        )
        conn.commit()
    except Exception:
        logger.exception("failed to write ai_runs audit")
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.post("/signal", response_model=List[Signal])
def generate_signals(payload: SignalRequest = Body(...), caller: dict = Depends(require_api_key)):
    """Generate signals via configured LLM provider.

    The agent formats a small prompt, attempts to call a streaming API (OpenAI) if available,
    falls back to `tools.llm_provider.generate_reply`, parses a JSON array of signals,
    and persists an audit row to `ai_runs`.
    """
    caller_type = caller.get("type") if isinstance(caller, dict) else None
    if caller_type == "api_key" and "ai:signal" not in (caller.get("scopes") or []):
        raise HTTPException(status_code=403, detail="API key missing required scope: ai:signal")
    if caller_type not in {"admin", "api_key"}:
        raise HTTPException(status_code=403, detail="unauthorized caller")
    try:
        symbols = [s.strip().upper() for s in payload.symbols]
        # Attempt to include small feature snapshots for each symbol
        feature_snapshot = {}
        try:
            from tools import features as feature_lib
            for s in symbols[:5]:
                try:
                    feature_snapshot[s] = feature_lib.get_feature_window(s, lookback=20)
                except Exception:
                    feature_snapshot[s] = None
        except Exception:
            feature_snapshot = None

        # Build prompt using centralized prompt templates and safety checks
        try:
            from tools import ai_prompts
            prompt = ai_prompts.build_signal_prompt(symbols, horizon=payload.horizon, feature_snapshot=feature_snapshot)
            if not ai_prompts.safety_filter_prompt(prompt):
                raise RuntimeError("prompt failed safety checks")
        except Exception:
            # fallback to basic inline prompt
            prompt = (
                "You are a concise trading assistant. For each symbol in the input, produce a JSON array of objects with keys: "
                "action (buy/sell/hold/short/cover), symbol, size_pct (0-1), stop_loss (pct), take_profit (pct), rationale, confidence (0-1).\n"
                f"Context: horizon={payload.horizon}. Symbols: {', '.join(symbols)}.\n"
                "Return output as a strict JSON array."
            )

        run_id = os.urandom(8).hex()
        model_used = None
        text = None

        # check cache first
        try:
            from tools import prompt_cache
            cached = prompt_cache.get_cached(prompt)
            if cached:
                text = cached
                model_used = "cache"
        except Exception:
            cached = None

        # try streaming with OpenAI if available
        try:
            from tools import llm_provider
            provider = llm_provider._choose_provider()
        except Exception:
            provider = None

        if provider == "openai":
            try:
                # attempt to stream from OpenAI
                import openai

                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    openai.api_key = api_key
                    model_used = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
                    # build messages
                    system = os.getenv("OPENAI_SYSTEM_PROMPT", "You are a helpful trading assistant.")
                    stream_resp = openai.ChatCompletion.create(model=model_used, messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}], max_tokens=512, stream=True)
                    parts = []
                    for chunk in stream_resp:
                        try:
                            # new SDK returns chunks with choices->[delta]->content
                            delta = chunk.choices[0].delta
                            if hasattr(delta, 'get'):
                                txt = delta.get('content')
                            else:
                                txt = getattr(delta, 'content', None)
                            if txt:
                                parts.append(txt)
                        except Exception:
                            try:
                                txt = getattr(chunk.choices[0], 'text', None)
                                if txt:
                                    parts.append(txt)
                            except Exception:
                                pass
                    text = "".join(parts).strip()
            except Exception:
                logger.exception("OpenAI streaming failed; will fall back to sync provider")

        # if we have a text and it wasn't from cache, store it
        if text and (not getattr(cached, 'strip', lambda: None)()):
            try:
                from tools import prompt_cache
                prompt_cache.set_cached(prompt, text, model=model_used or provider, ttl_seconds=3600)
            except Exception:
                logger.exception("failed to write prompt cache")

        # fallback to provider sync call
        if not text:
            try:
                from tools import llm_provider
                model_used = model_used or llm_provider._choose_provider()
                text = llm_provider.generate_reply(prompt)
                if isinstance(text, dict):
                    text = text.get("text") or str(text)
            except Exception:
                logger.exception("llm_provider.generate_reply failed")
                text = None

        parsed = None
        results = []
        if text:
            try:
                from tools import ai_prompts
                parsed = ai_prompts.extract_json_array(text)
                if parsed is None:
                    # last-resort try raw json loads
                    parsed = json.loads(text)
                for item in parsed:
                    try:
                        s = Signal(**item)
                        results.append(s)
                    except Exception:
                        sym = item.get("symbol") or item.get("ticker")
                        act = item.get("action") or "hold"
                        results.append(Signal(action=act, symbol=sym or "", rationale=item.get("rationale"), confidence=item.get("confidence", 0.0)))
            except Exception:
                logger.exception("Failed to parse LLM JSON response")

        # fallback: emit hold signals
        if not results:
            for s in symbols:
                results.append(Signal(action="hold", symbol=s, confidence=0.05, rationale="fallback"))

        # persist audit
        try:
            _insert_ai_run(run_id=run_id, user=None, prompt=prompt, response=text or "", parsed_json=json.dumps([_model_to_dict(r) for r in results]), model=model_used)
        except Exception:
            logger.exception("failed to persist ai run")

        return results
    except Exception as e:
        logger.exception("generate_signals failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
