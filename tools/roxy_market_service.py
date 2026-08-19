"""Focused, independently deployable Roxy Trading and Roxy Crypto surfaces."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from roxy_trader.openai_brain import (
    RoxyCryptoOpenAIBrain,
    RoxyTradingOpenAIBrain,
    crypto_openai_status,
    trading_openai_status,
)


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PRODUCT = "crypto" if os.getenv("ROXY_MARKET_PRODUCT", "trading").strip().lower() == "crypto" else "trading"
COOKIE_NAME = f"roxy_{PRODUCT}_session"
SESSION_SECONDS = 365 * 24 * 60 * 60
_RATE: dict[str, deque[float]] = defaultdict(deque)
_CONTEXT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class ExplainRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    symbol: str = Field(min_length=1, max_length=24)
    depth: str = Field(default="routine", pattern="^(routine|deep)$")
    confirmed: bool = False


def _scope_prefix() -> str:
    return f"ROXY_{PRODUCT.upper()}"


def _access_key() -> str:
    return str(os.getenv(f"{_scope_prefix()}_ACCESS_KEY") or "").strip()


def _normalize_symbol(raw: Any) -> str:
    value = re.sub(r"[^A-Za-z0-9./-]", "", str(raw or "").upper())
    if PRODUCT == "crypto":
        base = value.split("/", 1)[0].split("-", 1)[0]
        if not re.fullmatch(r"[A-Z0-9]{2,12}", base):
            raise HTTPException(status_code=422, detail="Símbolo crypto no válido")
        return f"{base}/USD"
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,11}", value):
        raise HTTPException(status_code=422, detail="Ticker no válido")
    return value


def _signature(expires: int) -> str:
    key = _access_key()
    return hmac.new(key.encode(), f"{PRODUCT}:{expires}".encode(), hashlib.sha256).hexdigest()


def _session_value() -> str:
    expires = int(time.time()) + SESSION_SECONDS
    return f"{expires}.{_signature(expires)}"


def _valid_session(value: str) -> bool:
    try:
        raw_expires, supplied = str(value or "").split(".", 1)
        expires = int(raw_expires)
    except (TypeError, ValueError):
        return False
    return expires > int(time.time()) and hmac.compare_digest(supplied, _signature(expires))


def _authenticate(request: Request, authorization: str | None = Header(default=None)) -> str:
    configured = _access_key()
    if not configured:
        raise HTTPException(status_code=503, detail=f"Falta {_scope_prefix()}_ACCESS_KEY")
    bearer = str(authorization or "")
    if bearer.startswith("Bearer ") and hmac.compare_digest(bearer[7:], configured):
        return PRODUCT
    if _valid_session(request.cookies.get(COOKIE_NAME, "")):
        return PRODUCT
    raise HTTPException(status_code=401, detail="Conecta este dispositivo")


def _rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    current = time.monotonic()
    bucket = _RATE[key]
    while bucket and bucket[0] < current - 60:
        bucket.popleft()
    if len(bucket) >= 60:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes; espera un minuto")
    bucket.append(current)


def _market_context(symbol: str) -> dict[str, Any]:
    normalized = _normalize_symbol(symbol)
    cached = _CONTEXT_CACHE.get(normalized)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    snapshot = _fetch_market_snapshot(normalized)
    source = str(snapshot.get("source") or "").strip()
    data_as_of = str(snapshot.get("price_timestamp") or snapshot.get("observed_at") or "").strip()
    sources = []
    if snapshot.get("price") is not None and source not in {"", "unavailable", "mercado cerrado"}:
        sources.append({"name": source, "as_of": data_as_of})
    context = {
        "product": f"roxy_{PRODUCT}",
        "symbol": normalized,
        "market": PRODUCT,
        "price": snapshot.get("price"),
        "previous_close": snapshot.get("previous_close"),
        "change_pct": snapshot.get("change_pct"),
        "freshness": snapshot.get("freshness"),
        "market_open": snapshot.get("market_open"),
        "provider": snapshot.get("provider"),
        "source_mode": snapshot.get("source_mode"),
        "latency_note": snapshot.get("latency_note"),
        "data_as_of": data_as_of,
        "sources": sources,
    }
    _CONTEXT_CACHE[normalized] = (time.monotonic() + 15, context)
    return context


def _fetch_market_snapshot(symbol: str) -> dict[str, Any]:
    """Fetch one real quote without importing the large Streamlit application."""
    observed = datetime.now(timezone.utc).isoformat()
    try:
        if PRODUCT == "crypto":
            import ccxt

            exchange = ccxt.binanceus({"enableRateLimit": True, "timeout": 7000})
            ticker = exchange.fetch_ticker(symbol)
            price = ticker.get("last") or ticker.get("close") or ticker.get("bid") or ticker.get("ask")
            if price is None or float(price) <= 0:
                raise RuntimeError("El exchange no devolvió un precio válido")
            timestamp = ticker.get("timestamp")
            data_as_of = (
                datetime.fromtimestamp(float(timestamp) / 1000, timezone.utc).isoformat()
                if timestamp
                else observed
            )
            return {
                "price": float(price),
                "previous_close": ticker.get("previousClose"),
                "change_pct": ticker.get("percentage"),
                "price_timestamp": data_as_of,
                "observed_at": observed,
                "freshness": "LIVE" if timestamp else "FRESH",
                "source": "BinanceUS ticker",
                "source_mode": "EXCHANGE_TICKER",
                "provider": "BinanceUS",
                "market_open": True,
                "latency_note": "Ticker público del exchange vía REST.",
            }

        import requests

        bridge_url = str(
            os.getenv("ROXY_STOCK_SNAPSHOT_URL")
            or "https://roxy-stock-stream.onrender.com/v1/market/stock-snapshot"
        ).strip()
        response = requests.get(bridge_url, params={"symbols": symbol}, timeout=8)
        response.raise_for_status()
        payload = response.json()
        quote = (payload.get("quotes") or {}).get(symbol) if isinstance(payload, dict) else None
        if not isinstance(quote, dict) or quote.get("price") is None:
            raise RuntimeError("El bridge no devolvió una cotización válida")
        return {
            "price": float(quote["price"]),
            "previous_close": quote.get("previous"),
            "change_pct": quote.get("changePct"),
            "price_timestamp": str(payload.get("serverTime") or observed),
            "observed_at": observed,
            "freshness": quote.get("freshness") or "FRESH",
            "source": quote.get("source") or "Roxy stock stream",
            "source_mode": quote.get("mode") or "SNAPSHOT",
            "provider": "Roxy stock stream",
            "market_open": quote.get("marketOpen"),
            "latency_note": "Cotización sanitizada por el bridge de acciones de Roxy.",
        }
    except Exception as exc:
        return {
            "price": None,
            "previous_close": None,
            "change_pct": None,
            "price_timestamp": "",
            "observed_at": observed,
            "freshness": "FAIL",
            "source": "unavailable",
            "source_mode": "NO_DATA",
            "provider": "",
            "market_open": None,
            "latency_note": "No usar para operar hasta recuperar una cotización verificable.",
            "error": f"{type(exc).__name__}: {exc}"[:240],
        }


def _brain() -> RoxyTradingOpenAIBrain:
    return RoxyCryptoOpenAIBrain() if PRODUCT == "crypto" else RoxyTradingOpenAIBrain()


app = FastAPI(title=f"Roxy {PRODUCT.title()}", docs_url=None, redoc_url=None)
app.mount("/assets", StaticFiles(directory=str(ASSETS)), name="assets")


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


@app.get("/")
def root() -> FileResponse:
    return FileResponse(ASSETS / "roxy_market.html", media_type="text/html")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": f"roxy-{PRODUCT}", "product": PRODUCT}


@app.post("/v1/session")
def create_session(request: Request, authorization: str | None = Header(default=None)) -> JSONResponse:
    _rate_limit(request)
    configured = _access_key()
    supplied = str(authorization or "")
    if not configured or not supplied.startswith("Bearer ") or not hmac.compare_digest(supplied[7:], configured):
        raise HTTPException(status_code=401, detail="Clave de acceso incorrecta")
    response = JSONResponse({"status": "CONNECTED", "product": PRODUCT})
    response.set_cookie(
        COOKIE_NAME,
        _session_value(),
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return response


@app.delete("/v1/session")
def delete_session() -> JSONResponse:
    response = JSONResponse({"status": "DISCONNECTED"})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.get("/v1/config")
def config(_: str = Depends(_authenticate)) -> dict[str, Any]:
    status = crypto_openai_status() if PRODUCT == "crypto" else trading_openai_status()
    other = os.getenv("ROXY_TRADING_APP_URL" if PRODUCT == "crypto" else "ROXY_CRYPTO_APP_URL", "")
    return {
        "product": PRODUCT,
        "title": "Roxy Crypto" if PRODUCT == "crypto" else "Roxy Trading",
        "default_symbol": "BTC/USD" if PRODUCT == "crypto" else "AAPL",
        "other_url": str(other).strip(),
        "openai": status,
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/v1/market/{symbol:path}")
def market_context(symbol: str, request: Request, _: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    return _market_context(symbol)


@app.post("/v1/ai/explain")
def explain(payload: ExplainRequest, request: Request, _: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    context = _market_context(payload.symbol)
    answer = _brain().answer(
        payload.question,
        market_context=context,
        requested_depth=payload.depth,
        confirmed=payload.confirmed,
    )
    return {"answer": answer.public_dict(), "context": context}
