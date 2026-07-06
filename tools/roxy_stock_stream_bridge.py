"""Server-side stock stream bridge for Roxy Trading.

This service keeps market-data credentials on the server and exposes only
sanitized Server-Sent Events to the browser. It prefers Alpaca's market-data
WebSocket and falls back to the existing quote snapshot path when streaming is
not available.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
from datetime import datetime, time, timezone
from typing import Any, AsyncIterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError:  # pragma: no cover - service runtime installs requirements.txt
    FastAPI = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
    StreamingResponse = None  # type: ignore[assignment]

ALPACA_STREAM_BASE = "wss://stream.data.alpaca.markets/v2"
ALPACA_REST_BASE = "https://data.alpaca.markets/v2"
DEFAULT_SYMBOLS = ("AAPL", "MSFT", "NVDA", "TSLA", "AMD")
MAX_SYMBOLS = 24
HTTP_TIMEOUT_SECONDS = 6

app = FastAPI(title="Roxy Stock Stream Bridge", version="1.0.0") if FastAPI is not None else None


def normalize_stock_symbols(raw_symbols: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Return clean uppercase stock symbols suitable for market-data requests."""
    if raw_symbols is None:
        candidates: list[str] = list(DEFAULT_SYMBOLS)
    elif isinstance(raw_symbols, str):
        candidates = re.split(r"[\s,;|]+", raw_symbols)
    else:
        candidates = [str(item) for item in raw_symbols]

    clean: list[str] = []
    for item in candidates:
        symbol = re.sub(r"[^A-Za-z0-9.\-]", "", str(item or "").upper()).strip()
        if not symbol or symbol in clean:
            continue
        clean.append(symbol)
        if len(clean) >= MAX_SYMBOLS:
            break
    return clean or list(DEFAULT_SYMBOLS)


def sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'), ensure_ascii=False)}\n\n"


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def stock_market_open_state() -> dict[str, Any]:
    now = datetime.now(ZoneInfo("America/New_York"))
    is_weekday = now.weekday() < 5
    is_open = is_weekday and time(9, 30) <= now.time() <= time(16, 0)
    return {
        "open": is_open,
        "label": "mercado abierto" if is_open else "mercado cerrado",
        "updatedAt": now.strftime("%I:%M:%S %p").lstrip("0"),
    }


def _feed_name() -> str:
    feed = re.sub(r"[^a-z]", "", os.getenv("ALPACA_DATA_FEED", "iex").lower())
    return feed if feed in {"iex", "sip"} else "iex"


def _stream_enabled() -> bool:
    return os.getenv("ROXY_STOCK_ALPACA_STREAM", "1").strip().lower() not in {"0", "false", "no", "off"}


def _alpaca_credentials() -> tuple[str, str]:
    return os.getenv("ALPACA_API_KEY", "").strip(), os.getenv("ALPACA_API_SECRET", "").strip()


def _http_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any] | list[Any] | None:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _alpaca_rest_quote(symbol: str) -> dict[str, Any] | None:
    key, secret = _alpaca_credentials()
    if not key or not secret:
        return None

    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }
    feed = _feed_name()
    query = urlencode({"feed": feed})
    trade_url = f"{ALPACA_REST_BASE}/stocks/{symbol}/trades/latest?{query}"
    quote_url = f"{ALPACA_REST_BASE}/stocks/{symbol}/quotes/latest?{query}"

    trade_payload = _http_json(trade_url, headers=headers)
    quote_payload = _http_json(quote_url, headers=headers)
    trade = trade_payload.get("trade") if isinstance(trade_payload, dict) else None
    quote = quote_payload.get("quote") if isinstance(quote_payload, dict) else None

    price = safe_float(trade.get("p") if isinstance(trade, dict) else None)
    if price is None and isinstance(quote, dict):
        bid = safe_float(quote.get("bp"))
        ask = safe_float(quote.get("ap"))
        if bid is not None and ask is not None and bid > 0 and ask > 0:
            price = (bid + ask) / 2
        else:
            price = bid or ask

    if price is None or price <= 0:
        return None

    market_state = stock_market_open_state()
    return {
        "symbol": symbol,
        "price": round(price, 6),
        "changePct": None,
        "previous": None,
        "source": f"Alpaca {feed.upper()} REST",
        "marketOpen": bool(market_state.get("open")),
        "freshness": "latest trade/quote",
        "updatedAt": str(market_state.get("updatedAt")),
    }


def _stooq_quote(symbol: str) -> dict[str, Any] | None:
    # Public delayed fallback used only when Alpaca is unavailable.
    stooq_symbol = f"{symbol.lower()}.us"
    url = f"https://stooq.com/q/l/?s={stooq_symbol}&f=sd2t2ohlcv&h&e=csv"
    request = Request(url, headers={"User-Agent": "RoxyTrading/1.0"})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None

    rows = list(csv.DictReader(body.splitlines()))
    if not rows:
        return None
    row = rows[0]
    close = safe_float(row.get("Close"))
    open_price = safe_float(row.get("Open"))
    if close is None or close <= 0:
        return None
    change_pct = None
    if open_price is not None and open_price > 0:
        change_pct = ((close - open_price) / open_price) * 100
    market_state = stock_market_open_state()
    return {
        "symbol": symbol,
        "price": round(close, 6),
        "changePct": round(change_pct, 4) if change_pct is not None else None,
        "previous": round(open_price, 6) if open_price is not None else None,
        "source": "Stooq delayed fallback",
        "marketOpen": bool(market_state.get("open")),
        "freshness": "delayed fallback",
        "updatedAt": str(market_state.get("updatedAt")),
    }


def _quote_from_snapshot(symbol: str) -> dict[str, Any] | None:
    return _alpaca_rest_quote(symbol) or _stooq_quote(symbol)


async def _polling_quotes(symbols: list[str], delay_seconds: float = 2.0) -> AsyncIterator[dict[str, Any]]:
    while True:
        for symbol in symbols:
            quote = await asyncio.to_thread(_quote_from_snapshot, symbol)
            if quote:
                quote["mode"] = "polling"
                yield quote
            await asyncio.sleep(0.05)
        await asyncio.sleep(delay_seconds)


async def _alpaca_trade_stream(symbols: list[str]) -> AsyncIterator[dict[str, Any]]:
    key, secret = _alpaca_credentials()
    if not key or not secret:
        raise RuntimeError("ALPACA_API_KEY/ALPACA_API_SECRET not configured")
    if not _stream_enabled():
        raise RuntimeError("ROXY_STOCK_ALPACA_STREAM disabled")

    try:
        import websockets
    except ImportError as exc:  # pragma: no cover - requirements include uvicorn[standard]
        raise RuntimeError("websockets package is not installed") from exc

    feed = _feed_name()
    url = f"{ALPACA_STREAM_BASE}/{feed}"
    async with websockets.connect(url, ping_interval=20, ping_timeout=20, close_timeout=5) as ws:
        await ws.send(json.dumps({"action": "auth", "key": key, "secret": secret}))
        await ws.send(json.dumps({"action": "subscribe", "trades": symbols}))
        async for message in ws:
            try:
                items = json.loads(message)
            except json.JSONDecodeError:
                continue
            if isinstance(items, dict):
                items = [items]
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("T")
                if item_type == "success":
                    continue
                if item_type == "error":
                    raise RuntimeError(str(item.get("msg") or item)[:180])
                if item_type != "t":
                    continue
                symbol = str(item.get("S") or "").upper()
                price = safe_float(item.get("p"))
                if not symbol or price is None or price <= 0:
                    continue
                market_state = stock_market_open_state()
                yield {
                    "symbol": symbol,
                    "price": round(price, 6),
                    "changePct": None,
                    "previous": None,
                    "source": f"Alpaca {feed.upper()} stream",
                    "marketOpen": bool(market_state.get("open")),
                    "freshness": "tick trade",
                    "updatedAt": datetime.now().strftime("%I:%M:%S %p").lstrip("0"),
                    "mode": "stream",
                }


async def stock_stream_events(symbols: list[str]) -> AsyncIterator[str]:
    yield sse_event(
        "status",
        {
            "mode": "starting",
            "symbols": symbols,
            "serverTime": datetime.now(timezone.utc).isoformat(),
        },
    )
    try:
        async for quote in _alpaca_trade_stream(symbols):
            yield sse_event("quote", quote)
    except Exception as exc:
        yield sse_event(
            "status",
            {
                "mode": "polling_fallback",
                "symbols": symbols,
                "reason": str(exc)[:180],
                "serverTime": datetime.now(timezone.utc).isoformat(),
            },
        )
        async for quote in _polling_quotes(symbols):
            yield sse_event("quote", quote)


if app is not None:

    @app.get("/")
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "ok": True,
                "service": "roxy-stock-stream-bridge",
                "health": "/health",
                "stream": "/v1/market/stock-stream",
            }
        )

    @app.get("/health")
    def health() -> JSONResponse:
        key, secret = _alpaca_credentials()
        return JSONResponse(
            {
                "ok": True,
                "service": "roxy-stock-stream-bridge",
                "alpacaConfigured": bool(key and secret),
                "feed": _feed_name(),
            }
        )

    @app.get("/v1/market/stock-stream")
    def stream_stock_quotes(symbols: str = Query(default="")) -> StreamingResponse:
        clean_symbols = normalize_stock_symbols(symbols)
        return StreamingResponse(
            stock_stream_events(clean_symbols),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": os.getenv("ROXY_STOCK_STREAM_ALLOWED_ORIGIN", "*"),
            },
        )


def main() -> None:
    if app is None:
        raise RuntimeError("FastAPI is not installed. Install requirements.stock-bridge.txt.")

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is not installed. Install requirements.stock-bridge.txt.") from exc

    port = int(os.getenv("PORT", "8765"))
    print(f"Starting Roxy stock stream bridge on port {port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
