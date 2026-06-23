"""TradingView webhook ingestion and confirmation helpers.

The module is intentionally file-backed so Roxy can consume webhook alerts
without starting another development server or moving away from the fixed
Streamlit URL. It stores only analysis signals; it never places orders.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd


DEFAULT_WEBHOOK_PATH = Path("alerts/tradingview_webhooks.jsonl")
SECRET_KEY_PARTS = ("secret", "token", "passphrase", "password", "apikey", "api_key", "key")
SECRET_ENV_KEY = "TRADINGVIEW_WEBHOOK_SECRET"
SECRET_HEADER_KEYS = (
    "X-TradingView-Secret",
    "X-Roxy-TradingView-Secret",
    "X-Roxy-Webhook-Secret",
    "X-Webhook-Secret",
)
SECRET_PAYLOAD_KEYS = ("secret", "passphrase", "webhook_secret", "roxy_secret")
BUY_SIGNALS = {"BUY", "LONG", "ENTRY", "ENTER_LONG", "STRATEGY_LONG"}
SELL_SIGNALS = {"SELL", "SHORT", "EXIT", "CLOSE", "CLOSE_LONG", "STRATEGY_SHORT"}
AVOID_SIGNALS = {"AVOID", "NO_TRADE", "BLOCK", "BLOCKED", "CANCEL"}


def _now_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return result


def _nested_value(payload: Mapping[str, Any], key: str) -> Any:
    if key in payload:
        return payload.get(key)
    current: Any = payload
    for part in key.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current.get(part)
    return current


def _first_value(payload: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = _nested_value(payload, key)
        if _text(value):
            return value
    return None


def configured_tradingview_webhook_secret(env: Mapping[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    return _text(source.get(SECRET_ENV_KEY))


def validate_tradingview_webhook_secret(
    payload: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    expected = configured_tradingview_webhook_secret(env)
    if not expected:
        return {
            "ok": False,
            "status": "MISSING_SECRET_CONFIG",
            "detail": f"{SECRET_ENV_KEY} is not configured; authenticated TradingView ingestion is disabled.",
        }
    candidates: list[str] = []
    header_map = headers or {}
    for key in SECRET_HEADER_KEYS:
        value = header_map.get(key)
        if value is None:
            value = header_map.get(key.lower())
        if _text(value):
            candidates.append(_text(value))
    if isinstance(payload, Mapping):
        for key in SECRET_PAYLOAD_KEYS:
            value = _nested_value(payload, key)
            if _text(value):
                candidates.append(_text(value))
    if expected in candidates:
        return {"ok": True, "status": "OK", "detail": "TradingView webhook secret accepted."}
    return {
        "ok": False,
        "status": "INVALID_SECRET",
        "detail": "TradingView webhook secret missing or invalid.",
    }


def sanitize_tradingview_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower().replace("-", "_")
            if any(part in lowered for part in SECRET_KEY_PARTS):
                clean[key_text] = "[redacted]"
            else:
                clean[key_text] = sanitize_tradingview_payload(item)
        return clean
    if isinstance(value, list):
        return [sanitize_tradingview_payload(item) for item in value]
    return value


def normalize_tradingview_timeframe(value: Any) -> str:
    text = _text(value).lower().replace(" ", "")
    if not text:
        return "-"
    aliases = {
        "1": "1m",
        "3": "3m",
        "5": "5m",
        "15": "15m",
        "30": "30m",
        "45": "45m",
        "60": "1h",
        "120": "2h",
        "240": "4h",
        "d": "1d",
        "1d": "1d",
        "day": "1d",
        "w": "1w",
        "1w": "1w",
    }
    if text in aliases:
        return aliases[text]
    if text.endswith("min"):
        return f"{text[:-3]}m"
    return text


def normalize_tradingview_symbol(value: Any) -> tuple[str, str]:
    raw = _text(value).upper()
    if not raw:
        return "-", "-"
    exchange = "-"
    symbol = raw
    if ":" in raw:
        exchange, symbol = raw.split(":", 1)
    symbol = symbol.strip().replace(" ", "")
    if "/" not in symbol:
        for quote in ("USDT", "USDC", "USD"):
            if symbol.endswith(quote) and len(symbol) > len(quote):
                symbol = f"{symbol[:-len(quote)]}/{quote}"
                break
    return symbol or "-", exchange or "-"


def tradingview_symbol_key(value: Any) -> str:
    symbol, _exchange = normalize_tradingview_symbol(value)
    compact = symbol.replace("/", "").replace("-", "").replace(".", "").upper()
    for stable_quote in ("USDT", "USDC"):
        if compact.endswith(stable_quote) and len(compact) > len(stable_quote):
            return f"{compact[:-len(stable_quote)]}USD"
    return compact


def tradingview_market_for_symbol(symbol: Any, exchange: Any = None) -> str:
    symbol_text = _text(symbol).upper()
    exchange_text = _text(exchange).upper()
    if "/" in symbol_text or exchange_text in {"BINANCE", "BINANCEUS", "COINBASE", "KRAKEN", "BITSTAMP"}:
        return "crypto"
    if symbol_text.endswith(("USDT", "USDC", "USD")) and len(symbol_text) > 4:
        return "crypto"
    return "stock"


def normalize_tradingview_signal(value: Any) -> str:
    text = _text(value).upper().replace(" ", "_").replace("-", "_")
    if not text:
        return "WATCH"
    if text in BUY_SIGNALS:
        return "BUY"
    if text in SELL_SIGNALS:
        return "SELL"
    if text in AVOID_SIGNALS:
        return "AVOID"
    if "BUY" in text or "LONG" in text:
        return "BUY"
    if "SELL" in text or "SHORT" in text or "EXIT" in text:
        return "SELL"
    if "AVOID" in text or "NO_TRADE" in text:
        return "AVOID"
    return text[:32]


def parse_tradingview_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    if text.isdigit():
        stamp = int(text)
        if stamp > 10_000_000_000:
            stamp = int(stamp / 1000)
        try:
            return datetime.fromtimestamp(stamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_tradingview_payload(payload: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("TradingView payload must be a mapping")
    raw_symbol = _first_value(payload, ("symbol", "ticker", "syminfo.ticker", "syminfo.tickerid"))
    symbol, exchange = normalize_tradingview_symbol(raw_symbol)
    if exchange == "-":
        exchange = _text(_first_value(payload, ("exchange", "syminfo.prefix"))) or "-"
    timeframe = normalize_tradingview_timeframe(_first_value(payload, ("timeframe", "interval", "tf", "resolution")))
    signal = normalize_tradingview_signal(
        _first_value(payload, ("signal", "action", "strategy.order.action", "strategy_action", "side"))
    )
    event_time = parse_tradingview_datetime(
        _first_value(payload, ("timestamp", "time", "timenow", "bar_time", "strategy.order.time"))
    )
    event_time_iso = _now_iso(event_time) if event_time else "-"
    received_at = _now_iso(now)
    price = _float(_first_value(payload, ("price", "close", "strategy.order.price", "last", "current_price")))
    strategy = _text(_first_value(payload, ("strategy", "setup", "strategy_name", "alert_name"))) or "-"
    message = _text(_first_value(payload, ("message", "comment", "note", "text"))) or "-"
    market = _text(_first_value(payload, ("market", "asset_class"))) or tradingview_market_for_symbol(symbol, exchange)
    identity_payload = {
        "symbol": tradingview_symbol_key(symbol),
        "timeframe": timeframe,
        "signal": signal,
        "event_time": event_time_iso,
        "price": price,
        "strategy": strategy,
        "message": message,
    }
    webhook_id = hashlib.sha256(json.dumps(identity_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {
        "webhook_id": webhook_id,
        "received_at": received_at,
        "event_time": event_time_iso,
        "source": "TradingView webhook",
        "symbol": symbol,
        "symbol_key": tradingview_symbol_key(symbol),
        "exchange": exchange,
        "market": market.lower(),
        "timeframe": timeframe,
        "signal": signal,
        "price": price,
        "strategy": strategy,
        "message": message,
        "raw_payload": sanitize_tradingview_payload(dict(payload)),
    }


def load_tradingview_webhooks(path: Path | str = DEFAULT_WEBHOOK_PATH, *, limit: int | None = 250) -> pd.DataFrame:
    file_path = Path(path)
    rows: list[dict[str, Any]] = []
    if not file_path.exists():
        return pd.DataFrame()
    for line in file_path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    if limit is not None and limit > 0:
        rows = rows[-limit:]
    return pd.DataFrame(rows)


def append_tradingview_webhook(
    payload: Mapping[str, Any],
    path: Path | str = DEFAULT_WEBHOOK_PATH,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    row = normalize_tradingview_payload(payload, now=now)
    file_path = Path(path)
    existing = load_tradingview_webhooks(file_path, limit=None)
    if not existing.empty and "webhook_id" in existing.columns:
        if row["webhook_id"] in set(existing["webhook_id"].astype(str)):
            row["duplicate"] = True
            return row
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    row["duplicate"] = False
    return row


def append_authenticated_tradingview_webhook(
    payload: Mapping[str, Any],
    *,
    headers: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    path: Path | str = DEFAULT_WEBHOOK_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    auth = validate_tradingview_webhook_secret(payload, headers=headers, env=env)
    if not auth.get("ok"):
        return {
            "ok": False,
            "status": auth["status"],
            "detail": auth["detail"],
            "duplicate": None,
        }
    row = append_tradingview_webhook(payload, path=path, now=now)
    return {
        "ok": True,
        "status": "DUPLICATE" if row.get("duplicate") else "RECORDED",
        "detail": "TradingView webhook duplicate ignored." if row.get("duplicate") else "TradingView webhook recorded.",
        "duplicate": bool(row.get("duplicate")),
        "symbol": row.get("symbol"),
        "timeframe": row.get("timeframe"),
        "signal": row.get("signal"),
        "received_at": row.get("received_at"),
        "webhook_id": row.get("webhook_id"),
    }


def latest_tradingview_confirmation(
    symbol: Any,
    timeframe: Any = None,
    *,
    max_age_minutes: int = 90,
    rows: pd.DataFrame | None = None,
    path: Path | str = DEFAULT_WEBHOOK_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    data = rows if isinstance(rows, pd.DataFrame) else load_tradingview_webhooks(path)
    if data.empty or "symbol_key" not in data.columns:
        return {"label": "Sin webhook TV", "fresh": False, "detail": "No hay webhooks recientes de TradingView."}
    symbol_key = tradingview_symbol_key(symbol)
    filtered = data[data["symbol_key"].astype(str).str.upper().eq(symbol_key)]
    tf_key = normalize_tradingview_timeframe(timeframe)
    if tf_key != "-" and "timeframe" in filtered.columns:
        exact_tf = filtered[filtered["timeframe"].astype(str).str.lower().eq(tf_key)]
        if not exact_tf.empty:
            filtered = exact_tf
    if filtered.empty:
        return {"label": "Sin webhook TV", "fresh": False, "detail": "No hay webhook para este ticker/timeframe."}
    filtered = filtered.copy()
    filtered["_received_dt"] = pd.to_datetime(filtered.get("received_at"), errors="coerce", utc=True)
    filtered = filtered.sort_values("_received_dt", ascending=False, na_position="last")
    latest = filtered.iloc[0].to_dict()
    received_at = parse_tradingview_datetime(latest.get("received_at"))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age_minutes = None
    fresh = False
    if received_at is not None:
        age_minutes = max(0.0, (current.astimezone(timezone.utc) - received_at).total_seconds() / 60.0)
        fresh = age_minutes <= max_age_minutes
    latest["fresh"] = bool(fresh)
    latest["age_minutes"] = age_minutes
    latest["label"] = "Webhook TV fresco" if fresh else "Webhook TV viejo"
    latest["detail"] = (
        f"{latest.get('signal', 'WATCH')} {latest.get('symbol', symbol)} "
        f"{latest.get('timeframe', '-')}, recibido hace {age_minutes:.0f}m."
        if age_minutes is not None
        else "Webhook TradingView sin timestamp valido."
    )
    return latest


def tradingview_confirmation_bias_for_opportunity(
    row: Mapping[str, Any],
    *,
    rows: pd.DataFrame | None = None,
    max_age_minutes: int = 90,
    now: datetime | None = None,
) -> dict[str, Any]:
    symbol = row.get("symbol") or row.get("ticker")
    timeframe = row.get("timeframe") or row.get("tf")
    latest = latest_tradingview_confirmation(
        symbol,
        timeframe,
        rows=rows,
        max_age_minutes=max_age_minutes,
        now=now,
    )
    if not latest.get("fresh"):
        return {
            "label": "Sin webhook TV",
            "tone": "watch",
            "priority_delta": 0,
            "detail": _text(latest.get("detail")) or "Sin confirmacion TradingView fresca.",
            "action": "Esperar confirmacion 15m/1h o usar chart visual.",
        }
    signal = _text(latest.get("signal")).upper()
    detail = _text(latest.get("detail"))
    if signal == "BUY":
        return {
            "label": "TradingView confirma",
            "tone": "buy",
            "priority_delta": 1,
            "detail": detail,
            "action": "Subir prioridad: webhook BUY fresco confirma el setup.",
        }
    if signal in {"SELL", "AVOID"}:
        return {
            "label": "TradingView contradice",
            "tone": "avoid",
            "priority_delta": -1,
            "detail": detail,
            "action": "Esperar: webhook TradingView contradice o marca salida.",
        }
    return {
        "label": "TradingView vigila",
        "tone": "watch",
        "priority_delta": 0,
        "detail": detail,
        "action": "No entrar todavia; webhook no confirma BUY.",
    }
