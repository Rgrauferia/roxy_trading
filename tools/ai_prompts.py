"""Prompt templates and safety helpers for Roxy AI.

Provides:
- `build_signal_prompt(symbols, horizon, feature_snapshot)` — formats a compact prompt for the LLM.
- `sanitize_prompt(prompt)` — trims and cleans prompt text.
- `extract_json_array(text)` — attempts to find and parse a JSON array from LLM output.
- `safety_filter_prompt(prompt)` — basic safety checks to avoid leaking secrets.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

MAX_PROMPT_CHARS = 3200

DEFAULT_SYSTEM = (
    "You are a concise, safety-aware trading assistant. Provide discrete trading signals in a strict JSON array. "
    "Do not include any private keys, credentials, or PII. If you cannot produce a signal, return an empty JSON array []."
)

BASE_INSTRUCTIONS = (
    "For each symbol, return an object with keys: action (buy/sell/hold/short/cover), symbol, size_pct (0-1), "
    "stop_loss (pct, optional), take_profit (pct, optional), rationale (short), confidence (0-1)."
)


def _short_feature_summary(df) -> str:
    """Given a DataFrame-like feature snapshot, return a short tabular summary string.

    Accepts anything with `close` and `ts` columns. Limits to last 5 rows.
    """
    try:
        rows = []
        if hasattr(df, "tail"):
            small = df.tail(5)
            for _, r in small.iterrows():
                rows.append(f"{r['ts']}: close={r['close']:.2f}")
        if not rows:
            return ""
        return "\n".join(rows)
    except Exception:
        return ""


def build_signal_prompt(symbols: List[str], horizon: str = "1d", feature_snapshot: Optional[dict] = None) -> str:
    """Build a compact prompt including system instructions, signal requirements, and optional small feature snapshot.

    `feature_snapshot` may be a dict mapping symbol -> DataFrame or summary string; the function will include a short summary.
    """
    syms = ", ".join(symbols)
    prompt_parts = [DEFAULT_SYSTEM, BASE_INSTRUCTIONS, f"Horizon: {horizon}.", f"Symbols: {syms}."]
    # include feature snapshot summaries
    if feature_snapshot:
        summaries = []
        if isinstance(feature_snapshot, dict):
            for s, snap in feature_snapshot.items():
                try:
                    summ = _short_feature_summary(snap)
                except Exception:
                    summ = str(snap)[:400]
                if summ:
                    summaries.append(f"{s}:\n{summ}")
        else:
            summaries.append(str(feature_snapshot)[:800])
        if summaries:
            prompt_parts.append("Feature snapshots (last rows):")
            prompt_parts.extend(summaries)

    prompt_parts.append("Return ONLY a JSON array. No extra commentary.")
    prompt = "\n\n".join(prompt_parts)
    return sanitize_prompt(prompt)


def sanitize_prompt(prompt: str) -> str:
    """Basic sanitation: trim and ensure prompt length within limits."""
    p = str(prompt).strip()
    if len(p) > MAX_PROMPT_CHARS:
        p = p[: MAX_PROMPT_CHARS - 32] + "\n... (truncated)"
    return p


_JSON_ARRAY_RE = re.compile(r"(\[\s*\{.*?\}\s*\])", re.S)


def extract_json_array(text: str) -> Optional[list]:
    """Attempt to extract and parse a JSON array from raw LLM text.

    Returns parsed list on success or None.
    """
    if not text:
        return None
    # try direct load first
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass
    # try to locate a JSON array substring
    m = _JSON_ARRAY_RE.search(text)
    if m:
        candidate = m.group(1)
        try:
            obj = json.loads(candidate)
            if isinstance(obj, list):
                return obj
        except Exception:
            pass
    # fallback: try to strip leading/trailing non-json characters
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            if isinstance(obj, list):
                return obj
        except Exception:
            pass
    return None


def safety_filter_prompt(prompt: str) -> bool:
    """Return False if prompt appears to contain secrets or disallowed tokens.

    This is a basic heuristic: look for 'PRIVATE', 'SECRET', 'KEY=', 'PASSWORD' etc.
    """
    deny_keywords = ["PRIVATE", "SECRET", "KEY=", "PASSWORD", "AWS_SECRET", "API_KEY"]
    p = prompt.upper()
    for k in deny_keywords:
        if k in p:
            return False
    return True
