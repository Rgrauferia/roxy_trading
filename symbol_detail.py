from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from moving_average_strategy import add_moving_averages
from salto_strategies import detect_salto_setups
from tools.ma_scan import is_intraday_stock_interval, stock_fetch_interval, stock_period_for_interval


SYMBOL_ALIASES = {
    "APPLE": "AAPL",
    "APPLE INC": "AAPL",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "TESLA": "TSLA",
    "AMAZON": "AMZN",
    "GOOGLE": "GOOGL",
    "META": "META",
    "AMD": "AMD",
    "PALANTIR": "PLTR",
    "BITCOIN": "BTC/USD",
    "BTC": "BTC/USD",
    "ETHEREUM": "ETH/USD",
    "ETH": "ETH/USD",
    "SOLANA": "SOL/USD",
    "SOL": "SOL/USD",
}

DERIVED_INTRADAY_TIMEFRAMES = {"2h": "2h", "4h": "4h"}
STOCK_ALPACA_TIMEFRAMES = {"1m", "5m", "15m", "1h", "1d", "1w"}
STOCK_POLYGON_TIMEFRAMES = {"1m", "5m", "15m", "1h", "1d", "1w"}
ALPACA_KEY_ENV_KEYS = ("ALPACA_API_KEY",)
ALPACA_SECRET_ENV_KEYS = ("ALPACA_API_SECRET", "ALPACA_SECRET_KEY")
POLYGON_KEY_ENV_KEYS = ("POLYGON_API_KEY", "POLYGON_API_TOKEN")
ALPACA_PLACEHOLDER_VALUES = {
    "TU_KEY_PAPER",
    "TU_SECRET_PAPER",
    "YOUR_ALPACA_API_KEY",
    "YOUR_ALPACA_API_SECRET",
    "YOUR_ALPACA_SECRET_KEY",
    "CHANGE_ME",
    "REPLACE_ME",
    "PASTE_KEY_HERE",
    "PASTE_SECRET_HERE",
}


def normalize_timeframe(timeframe: str) -> str:
    value = str(timeframe or "1h").strip().lower()
    aliases = {
        "1min": "1m",
        "1 minute": "1m",
        "5min": "5m",
        "5 minute": "5m",
        "15min": "15m",
        "15 minute": "15m",
        "60m": "1h",
        "120m": "2h",
        "240m": "4h",
        "1d": "1d",
        "day": "1d",
        "daily": "1d",
        "1wk": "1w",
        "1w": "1w",
        "week": "1w",
        "weekly": "1w",
    }
    return aliases.get(value, value)


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty or "ts" not in df.columns:
        return pd.DataFrame()
    data = df.copy()
    data["ts"] = pd.to_datetime(data["ts"], errors="coerce")
    data = data.dropna(subset=["ts"]).sort_values("ts")
    if data.empty:
        return pd.DataFrame()
    aggregations = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    keep = [column for column in aggregations if column in data.columns]
    if not {"open", "high", "low", "close"}.issubset(keep):
        return pd.DataFrame()
    resampled = (
        data.set_index("ts")
        .resample(rule, label="right", closed="right")
        .agg({column: aggregations[column] for column in keep})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    return resampled


def resolve_symbol_query(query: str, market: str = "stock") -> str:
    value = str(query or "").strip().upper()
    if not value:
        return ""
    value = SYMBOL_ALIASES.get(value, value)
    if market == "crypto" and "/" not in value:
        value = f"{value}/USD"
    return value


def first_env_value(source: dict[str, str], keys: tuple[str, ...]) -> tuple[str, str]:
    for key in keys:
        value = str(source.get(key) or "").strip()
        if value:
            return value, key
    return "", ""


def alpaca_env_credentials(env: dict[str, str] | None = None) -> dict[str, str]:
    source = env if env is not None else os.environ
    key, key_name = first_env_value(source, ALPACA_KEY_ENV_KEYS)
    secret, secret_name = first_env_value(source, ALPACA_SECRET_ENV_KEYS)
    return {"key": key, "key_name": key_name, "secret": secret, "secret_name": secret_name}


def looks_like_placeholder_secret(value: str) -> bool:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return False
    return (
        normalized in ALPACA_PLACEHOLDER_VALUES
        or normalized.startswith("TU_")
        or normalized.startswith("YOUR_")
        or normalized.startswith("PASTE_")
        or normalized.endswith("_HERE")
    )


def alpaca_placeholder_credential_keys(env: dict[str, str] | None = None) -> list[str]:
    credentials = alpaca_env_credentials(env)
    placeholder_keys: list[str] = []
    for value_name, key_name_name in (("key", "key_name"), ("secret", "secret_name")):
        value = credentials.get(value_name) or ""
        key_name = credentials.get(key_name_name) or value_name
        if looks_like_placeholder_secret(value):
            placeholder_keys.append(key_name)
    return placeholder_keys


def alpaca_credentials_available(env: dict[str, str] | None = None) -> bool:
    credentials = alpaca_env_credentials(env)
    return bool(credentials["key"] and credentials["secret"]) and not alpaca_placeholder_credential_keys(env)


def polygon_api_key(env: dict[str, str] | None = None) -> tuple[str, str]:
    source = env if env is not None else os.environ
    return first_env_value(source, POLYGON_KEY_ENV_KEYS)


def polygon_credentials_available(env: dict[str, str] | None = None) -> bool:
    key, _key_name = polygon_api_key(env)
    return bool(key)


def alpaca_fallback_info(reason: str, *, exc: Exception | None = None) -> dict[str, str]:
    raw_text = " ".join(str(part) for part in getattr(exc, "args", []) if part) if exc is not None else ""
    text = f"{type(exc).__name__ if exc is not None else ''} {raw_text} {str(exc) if exc is not None else ''}".lower()
    code = str(reason or "alpaca_unavailable")
    if exc is not None:
        if any(token in text for token in ["401", "403", "unauthorized", "forbidden", "invalid", "authentication", "permission"]):
            if any(token in text for token in ["subscription", "sip", "iex", "feed", "permission"]):
                code = "alpaca_feed_permission"
                detail = "Alpaca respondio, pero el feed/permisos no permiten esas velas."
                action = "Revisar permisos IEX/SIP o usar yfinance como respaldo para esa grafica."
            else:
                code = "alpaca_auth"
                detail = "Alpaca rechazo las credenciales o el token."
                action = "Revisar credenciales ALPACA_API_KEY y ALPACA_API_SECRET/ALPACA_SECRET_KEY en el entorno del servicio Streamlit."
        elif any(token in text for token in ["429", "rate limit", "too many requests"]):
            code = "alpaca_rate_limit"
            detail = "Alpaca limito temporalmente las llamadas."
            action = "Mantener fallback y reintentar en el siguiente ciclo."
        elif any(token in text for token in ["timeout", "connection", "network", "temporarily", "503", "502", "500"]):
            code = "alpaca_network"
            detail = "Alpaca no respondio de forma estable."
            action = "Mantener fallback y verificar conectividad/API status."
        else:
            code = f"alpaca_error:{type(exc).__name__}"
            detail = "Alpaca fallo con un error no clasificado."
            action = "Mantener fallback y revisar logs si se repite."
    elif code == "alpaca_not_configured":
        detail = "El servicio no tiene credenciales Alpaca disponibles."
        action = "Configurar ALPACA_API_KEY y ALPACA_API_SECRET/ALPACA_SECRET_KEY para activar velas Alpaca."
    elif code == "alpaca_placeholder_credentials":
        detail = "El servicio todavia tiene placeholders de Alpaca en lugar de credenciales paper reales."
        action = "Reemplazar TU_KEY_PAPER/TU_SECRET_PAPER por claves paper reales en el .env del servicio y recargar Roxy."
    elif code == "unsupported_timeframe":
        detail = "Ese timeframe no esta conectado a Alpaca directo."
        action = "Roxy usa base 1h o yfinance para derivar la grafica."
    elif code == "alpaca_empty":
        detail = "Alpaca respondio sin velas utilizables."
        action = "Mantener fallback y validar simbolo/timeframe/feed."
    else:
        detail = "Alpaca no pudo alimentar esta grafica."
        action = "Mantener fallback hasta recuperar la fuente premium."
    return {"fallback_reason": code, "fallback_detail": detail, "fallback_action": action}


def polygon_fallback_info(reason: str, *, exc: Exception | None = None) -> dict[str, str]:
    raw_text = " ".join(str(part) for part in getattr(exc, "args", []) if part) if exc is not None else ""
    text = f"{type(exc).__name__ if exc is not None else ''} {raw_text} {str(exc) if exc is not None else ''}".lower()
    code = str(reason or "polygon_unavailable")
    if exc is not None:
        if any(token in text for token in ["401", "403", "unauthorized", "forbidden", "invalid"]):
            code = "polygon_auth"
            detail = "Polygon rechazo la API key o no permite esa consulta."
            action = "Revisar POLYGON_API_KEY/POLYGON_API_TOKEN y permisos de plan."
        elif any(token in text for token in ["429", "rate limit", "too many requests"]):
            code = "polygon_rate_limit"
            detail = "Polygon limito temporalmente las llamadas."
            action = "Mantener fallback y reintentar en el siguiente ciclo."
        elif any(token in text for token in ["timeout", "connection", "network", "temporarily", "503", "502", "500"]):
            code = "polygon_network"
            detail = "Polygon no respondio de forma estable."
            action = "Mantener fallback y verificar conectividad/API status."
        else:
            code = f"polygon_error:{type(exc).__name__}"
            detail = "Polygon fallo con un error no clasificado."
            action = "Mantener fallback y revisar logs si se repite."
    elif code == "polygon_not_configured":
        detail = "El servicio no tiene POLYGON_API_KEY/POLYGON_API_TOKEN disponible."
        action = "Configurar Polygon como proveedor premium alterno para acciones."
    elif code == "unsupported_timeframe":
        detail = "Ese timeframe no esta conectado a Polygon directo."
        action = "Roxy usa base 1h o yfinance para derivar la grafica."
    elif code == "polygon_empty":
        detail = "Polygon respondio sin velas utilizables."
        action = "Mantener fallback y validar simbolo/timeframe/plan."
    else:
        detail = "Polygon no pudo alimentar esta grafica."
        action = "Mantener fallback hasta recuperar la fuente premium."
    return {"polygon_fallback_reason": code, "polygon_fallback_detail": detail, "polygon_fallback_action": action}


def alpaca_timeframe_for(timeframe: str):
    try:
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    except Exception:
        return None

    normalized = normalize_timeframe(timeframe)
    if normalized == "1m":
        return TimeFrame.Minute
    if normalized == "5m":
        return TimeFrame(5, TimeFrameUnit.Minute)
    if normalized == "15m":
        return TimeFrame(15, TimeFrameUnit.Minute)
    if normalized == "1h":
        return TimeFrame.Hour
    if normalized == "1d":
        return TimeFrame.Day
    if normalized == "1w":
        return TimeFrame.Week
    return None


def alpaca_start_for_timeframe(timeframe: str, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    normalized = normalize_timeframe(timeframe)
    if normalized == "1m":
        return current - timedelta(days=7)
    if normalized == "5m":
        return current - timedelta(days=30)
    if normalized == "15m":
        return current - timedelta(days=45)
    if normalized == "1h":
        return current - timedelta(days=180)
    if normalized == "1w":
        return current - timedelta(days=3650)
    return current - timedelta(days=730)


def polygon_range_for_timeframe(timeframe: str) -> tuple[int, str] | None:
    normalized = normalize_timeframe(timeframe)
    if normalized == "1m":
        return 1, "minute"
    if normalized == "5m":
        return 5, "minute"
    if normalized == "15m":
        return 15, "minute"
    if normalized == "1h":
        return 1, "hour"
    if normalized == "1d":
        return 1, "day"
    if normalized == "1w":
        return 1, "week"
    return None


def polygon_start_for_timeframe(timeframe: str, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    normalized = normalize_timeframe(timeframe)
    if normalized == "1m":
        return current - timedelta(days=7)
    if normalized == "5m":
        return current - timedelta(days=30)
    if normalized == "15m":
        return current - timedelta(days=30)
    if normalized == "1h":
        return current - timedelta(days=120)
    if normalized == "1w":
        return current - timedelta(days=3650)
    return current - timedelta(days=730)


def normalize_alpaca_bars_frame(raw: Any, symbol: str) -> pd.DataFrame:
    df = getattr(raw, "df", raw)
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    data = df.copy()
    if isinstance(data.index, pd.MultiIndex):
        data = data.reset_index()
        if "symbol" in data.columns:
            data = data[data["symbol"].astype(str).str.upper().eq(str(symbol).upper())]
    else:
        data = data.reset_index()

    rename = {
        "timestamp": "ts",
        "time": "ts",
        "Timestamp": "ts",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    data = data.rename(columns={column: rename.get(column, column) for column in data.columns})
    if "ts" not in data.columns:
        first_datetime = next((column for column in data.columns if "time" in str(column).lower() or "date" in str(column).lower()), None)
        if first_datetime:
            data = data.rename(columns={first_datetime: "ts"})
    required = ["ts", "open", "high", "low", "close", "volume"]
    if not set(required).issubset(data.columns):
        return pd.DataFrame()
    out = data[required].copy()
    out["ts"] = pd.to_datetime(out["ts"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["ts", "open", "high", "low", "close"]).sort_values("ts")
    return out.reset_index(drop=True)


def normalize_polygon_aggs_payload(raw: Any) -> pd.DataFrame:
    if not isinstance(raw, dict):
        return pd.DataFrame()
    results = raw.get("results")
    if not isinstance(results, list) or not results:
        return pd.DataFrame()
    data = pd.DataFrame(results)
    rename = {
        "t": "ts",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
    }
    data = data.rename(columns={column: rename.get(column, column) for column in data.columns})
    required = ["ts", "open", "high", "low", "close", "volume"]
    if not set(required).issubset(data.columns):
        return pd.DataFrame()
    out = data[required].copy()
    out["ts"] = pd.to_datetime(pd.to_numeric(out["ts"], errors="coerce"), unit="ms", utc=True, errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["ts", "open", "high", "low", "close"]).sort_values("ts")
    return out.reset_index(drop=True)


def fetch_alpaca_stock_ohlcv(
    symbol: str,
    *,
    timeframe: str,
    limit: int = 1000,
    env: dict[str, str] | None = None,
    feed: str = "iex",
) -> pd.DataFrame:
    credentials = alpaca_env_credentials(env)
    key = credentials["key"]
    secret = credentials["secret"]
    if not key or not secret or alpaca_placeholder_credential_keys(env):
        return pd.DataFrame()

    alpaca_timeframe = alpaca_timeframe_for(timeframe)
    if alpaca_timeframe is None:
        return pd.DataFrame()

    try:
        from alpaca.data.enums import DataFeed
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
    except Exception:
        return pd.DataFrame()

    feed_value = str(feed or "iex").strip().upper()
    data_feed = getattr(DataFeed, feed_value, DataFeed.IEX)
    client = StockHistoricalDataClient(key, secret)
    request = StockBarsRequest(
        symbol_or_symbols=str(symbol).upper(),
        timeframe=alpaca_timeframe,
        start=alpaca_start_for_timeframe(timeframe),
        limit=limit,
        feed=data_feed,
    )
    bars = client.get_stock_bars(request)
    return normalize_alpaca_bars_frame(bars, symbol)


def fetch_polygon_stock_ohlcv(
    symbol: str,
    *,
    timeframe: str,
    limit: int = 1000,
    env: dict[str, str] | None = None,
    timeout: float = 12.0,
) -> pd.DataFrame:
    key, _key_name = polygon_api_key(env)
    if not key:
        return pd.DataFrame()
    range_spec = polygon_range_for_timeframe(timeframe)
    if range_spec is None:
        return pd.DataFrame()

    multiplier, timespan = range_spec
    start = polygon_start_for_timeframe(timeframe).date().isoformat()
    end = datetime.now(timezone.utc).date().isoformat()
    query = urlencode(
        {
            "adjusted": "true",
            "sort": "asc",
            "limit": max(1, int(limit)),
            "apiKey": key,
        }
    )
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{str(symbol).upper()}/range/"
        f"{multiplier}/{timespan}/{start}/{end}?{query}"
    )
    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, dict) and str(payload.get("status") or "").upper() in {"ERROR", "NOT_AUTHORIZED"}:
        raise RuntimeError(str(payload.get("error") or payload.get("message") or payload.get("status")))
    return normalize_polygon_aggs_payload(payload)


def _fetch_stock_history_with_source(
    symbol: str,
    *,
    timeframe: str,
    include_extended_hours: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    import roxy_scanner as scanner

    timeframe = normalize_timeframe(timeframe)
    alpaca_configured = alpaca_credentials_available(env)
    alpaca_placeholder_keys = alpaca_placeholder_credential_keys(env)
    polygon_configured = polygon_credentials_available(env)
    provider_fallback_meta: dict[str, str] = {}
    if alpaca_configured and timeframe in STOCK_ALPACA_TIMEFRAMES:
        try:
            alpaca_df = fetch_alpaca_stock_ohlcv(symbol, timeframe=timeframe, env=env)
            if not alpaca_df.empty:
                return alpaca_df, {
                    "provider": "Alpaca",
                    "source": "alpaca_iex",
                    "mode": "BROKER_DATA",
                    "label": "Alpaca IEX",
                    "detail": "Velas de acciones desde Alpaca/IEX.",
                    "fallback": False,
                }
        except Exception as exc:
            provider_fallback_meta.update(alpaca_fallback_info("alpaca_error", exc=exc))
        else:
            provider_fallback_meta.update(alpaca_fallback_info("alpaca_empty"))
    else:
        if alpaca_placeholder_keys:
            alpaca_reason = "alpaca_placeholder_credentials"
        else:
            alpaca_reason = "alpaca_not_configured" if not alpaca_configured else "unsupported_timeframe"
        provider_fallback_meta.update(alpaca_fallback_info(alpaca_reason))

    if polygon_configured and timeframe in STOCK_POLYGON_TIMEFRAMES:
        try:
            polygon_df = fetch_polygon_stock_ohlcv(symbol, timeframe=timeframe, env=env)
            if not polygon_df.empty:
                return polygon_df, {
                    "provider": "Polygon",
                    "source": "polygon_aggs",
                    "mode": "PREMIUM_DATA",
                    "label": "Polygon aggregates",
                    "detail": "Velas de acciones desde Polygon como proveedor premium alterno.",
                    "fallback": False,
                    "upstream_fallback_reason": provider_fallback_meta.get("fallback_reason", ""),
                    "upstream_fallback_detail": provider_fallback_meta.get("fallback_detail", ""),
                    "upstream_fallback_action": provider_fallback_meta.get("fallback_action", ""),
                }
        except Exception as exc:
            provider_fallback_meta.update(polygon_fallback_info("polygon_error", exc=exc))
        else:
            provider_fallback_meta.update(polygon_fallback_info("polygon_empty"))
    else:
        provider_fallback_meta.update(polygon_fallback_info("polygon_not_configured" if not polygon_configured else "unsupported_timeframe"))

    period = stock_period_for_interval(timeframe, None, "60d")
    fallback_df = scanner.fetch_stock_ohlcv(
        symbol,
        interval=stock_fetch_interval(timeframe),
        period=period,
        prepost=include_extended_hours and is_intraday_stock_interval(timeframe),
    )
    return fallback_df, {
        "provider": "yfinance",
        "source": "yfinance",
        "mode": "FALLBACK",
        "label": "yfinance fallback",
        "detail": "Velas de acciones desde yfinance fallback.",
        "fallback": True,
        **provider_fallback_meta,
    }


def fetch_symbol_history_with_source(
    symbol: str,
    *,
    market: str,
    timeframe: str,
    include_extended_hours: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    import roxy_scanner as scanner

    timeframe = normalize_timeframe(timeframe)
    if timeframe in DERIVED_INTRADAY_TIMEFRAMES:
        if market == "crypto":
            base = scanner.fetch_crypto_ohlcv(symbol, timeframe="1h", limit=1000)
            return resample_ohlcv(base, DERIVED_INTRADAY_TIMEFRAMES[timeframe]), {
                "provider": "ccxt",
                "source": "ccxt:binanceus",
                "mode": "EXCHANGE_API",
                "label": "BinanceUS API",
                "detail": "Velas cripto via ccxt/binanceus.",
                "fallback": False,
            }
        base, meta = _fetch_stock_history_with_source(
            symbol,
            timeframe="1h",
            include_extended_hours=include_extended_hours,
            env=env,
        )
        meta = dict(meta)
        meta["derived_from"] = "1h"
        meta["timeframe"] = timeframe
        return resample_ohlcv(base, DERIVED_INTRADAY_TIMEFRAMES[timeframe]), meta

    if market == "crypto":
        return scanner.fetch_crypto_ohlcv(symbol, timeframe=timeframe, limit=1000), {
            "provider": "ccxt",
            "source": "ccxt:binanceus",
            "mode": "EXCHANGE_API",
            "label": "BinanceUS API",
            "detail": "Velas cripto via ccxt/binanceus.",
            "fallback": False,
        }

    return _fetch_stock_history_with_source(
        symbol,
        timeframe=timeframe,
        include_extended_hours=include_extended_hours,
        env=env,
    )


def fetch_symbol_history(
    symbol: str,
    *,
    market: str,
    timeframe: str,
    include_extended_hours: bool = True,
) -> pd.DataFrame:
    data, _source = fetch_symbol_history_with_source(
        symbol,
        market=market,
        timeframe=timeframe,
        include_extended_hours=include_extended_hours,
    )
    return data


def prepare_symbol_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = add_moving_averages(df)
    out = out.copy()
    out["ts"] = pd.to_datetime(out["ts"])
    out["ema9"] = out["close"].ewm(span=9, adjust=False).mean()
    delta = out["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, pd.NA)
    out["rsi14"] = 100.0 - (100.0 / (1.0 + rs))
    out.loc[(loss == 0) & (gain > 0), "rsi14"] = 100.0
    out.loc[(loss == 0) & (gain == 0), "rsi14"] = 50.0
    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["bb_mid"] = out["close"].rolling(window=20, min_periods=20).mean()
    bb_std = out["close"].rolling(window=20, min_periods=20).std()
    out["bb_upper"] = out["bb_mid"] + (bb_std * 2.0)
    out["bb_lower"] = out["bb_mid"] - (bb_std * 2.0)
    out["range_high_60"] = out["high"].rolling(window=60, min_periods=20).max() if "high" in out.columns else None
    out["range_low_60"] = out["low"].rolling(window=60, min_periods=20).min() if "low" in out.columns else None
    if {"range_high_60", "range_low_60", "close"}.issubset(out.columns):
        out["channel_width_pct"] = (out["range_high_60"] - out["range_low_60"]) / out["close"]
    keep = [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "ema9",
        "sma20",
        "sma40",
        "sma100",
        "sma200",
        "bb_mid",
        "bb_upper",
        "bb_lower",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_hist",
        "range_high_60",
        "range_low_60",
        "channel_width_pct",
        "volume",
        "volume_sma20",
        "relative_volume",
        "atr_pct",
    ]
    return out[[col for col in keep if col in out.columns]].dropna(subset=["close"]).reset_index(drop=True)


def latest_symbol_rows(scan_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if scan_df.empty or "symbol" not in scan_df.columns:
        return pd.DataFrame()
    out = scan_df[scan_df["symbol"].astype(str).str.upper().eq(symbol.upper())].copy()
    if out.empty:
        return out
    if "score" in out.columns:
        out["score"] = pd.to_numeric(out["score"], errors="coerce")
        out = out.sort_values(["tf", "score"], ascending=[True, False])
    return out.reset_index(drop=True)


def latest_confluence_row(confluence_df: pd.DataFrame, symbol: str) -> dict[str, Any]:
    if confluence_df.empty or "symbol" not in confluence_df.columns:
        return {}
    rows = confluence_df[confluence_df["symbol"].astype(str).str.upper().eq(symbol.upper())].copy()
    if rows.empty:
        return {}
    if "confluence_score" in rows.columns:
        rows["confluence_score"] = pd.to_numeric(rows["confluence_score"], errors="coerce")
        rows = rows.sort_values("confluence_score", ascending=False)
    return rows.iloc[0].to_dict()


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    number = _safe_float(value)
    return int(number) if number is not None else 0


def _safe_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip().upper()


def _risk_pct(setup: dict[str, Any]) -> float | None:
    entry = _safe_float(setup.get("entry"))
    stop = _safe_float(setup.get("stop"))
    if entry is None or stop is None or entry <= 0 or stop <= 0 or stop >= entry:
        return None
    return (entry - stop) / entry


def classify_strategy_playbook(
    setup: dict[str, Any],
    *,
    confluence: dict[str, Any] | None = None,
    market: str = "stock",
    timeframe: str = "1d",
) -> dict[str, str]:
    """Translate raw SMA metrics into a trading playbook explanation."""
    confluence = confluence or {}
    signal = _safe_text(setup.get("signal"))
    setup_name = _safe_text(setup.get("setup"))
    confluence_signal = _safe_text(confluence.get("signal"))
    trade_decision = _safe_text(confluence.get("trade_decision"))
    score = _safe_int(setup.get("score"))

    close = _safe_float(setup.get("close") or setup.get("entry"))
    sma20 = _safe_float(setup.get("sma20"))
    sma40 = _safe_float(setup.get("sma40"))
    sma100 = _safe_float(setup.get("sma100"))
    sma200 = _safe_float(setup.get("sma200"))
    dist20 = _safe_float(setup.get("dist_sma20_pct"))
    dist40 = _safe_float(setup.get("dist_sma40_pct"))
    risk = _risk_pct(setup)
    salto_family = _safe_text(setup.get("salto_family") or confluence.get("salto_family") or setup.get("strategy_family"))

    moving_averages = [sma20, sma40, sma100, sma200]
    has_all_ma = close is not None and all(value is not None for value in moving_averages)
    bullish_stack = bool(has_all_ma and sma20 > sma40 > sma100 > sma200)
    bearish_stack = bool(has_all_ma and sma20 < sma40 < sma100 < sma200)
    close_above_all = bool(has_all_ma and close > max(moving_averages))
    close_below_200 = bool(has_all_ma and close < sma200)
    near_20_40 = any(value is not None and abs(value) <= 3.0 for value in (dist20, dist40))
    extended = bool(dist20 is not None and dist20 > 12.0)
    confluence_confirmed = confluence_signal == "BUY" and trade_decision.startswith("TRADE_FOR")
    confluence_wait = confluence_signal in {"WATCH", "AVOID"} or trade_decision in {"WAIT", "NO_TRADE", "NO_TRADE_DOWNTREND"}
    risk_high = bool(risk is not None and risk > 0.03)

    if salto_family.startswith("SALTO") or "SALTO" in salto_family:
        regime = "Setup de salto"
        strategy = str(setup.get("salto_family") or confluence.get("salto_family") or "Salto pendiente de confirmar")
        entry_rule = "Confirmar 15m/1h y preparar entrada manual cerca del cierre; no activar sin stop medible."
    elif close_below_200 or bearish_stack or setup_name == "DOWNTREND":
        regime = "Bajista / debajo de SMA200"
        strategy = "No trade: esperar recuperacion de SMA200"
        entry_rule = "No buscar compras hasta que el precio recupere SMA200 y SMA20 vuelva sobre SMA40."
    elif bullish_stack and setup_name == "PULLBACK":
        regime = "Canal alcista"
        strategy = "Rebote en SMA20/SMA40"
        entry_rule = "Entrada solo si rebota en SMA20/SMA40 con volumen y el gatillo 15m confirma."
    elif bullish_stack and close_above_all and extended:
        regime = "Tendencia alcista extendida"
        strategy = "Canal fortalecido, pero precio lejos de SMA20"
        entry_rule = "No perseguir vela extendida; esperar retroceso a SMA20/SMA40 o consolidacion."
    elif bullish_stack and close_above_all:
        regime = "Canal fortalecido de largo plazo"
        strategy = "Continuacion de tendencia 20 > 40 > 100 > 200"
        entry_rule = "Entrada valida con cierre sobre SMA20 y confirmacion 15m/1h."
    elif setup_name == "EARLY_UPTREND":
        regime = "Transicion alcista"
        strategy = "Cruce de medias hacia tendencia"
        entry_rule = "Esperar que SMA20>SMA40 y que el precio mantenga SMA100/SMA200 como soporte."
    elif has_all_ma and close > sma200 and near_20_40:
        regime = "Canal lateral sobre SMA200"
        strategy = "Rebote controlado en medias"
        entry_rule = "Comprar solo ruptura o rebote confirmado; evitar entradas dentro del rango sin volumen."
    else:
        regime = "Neutral / canal lateral"
        strategy = "Watchlist: esperar ruptura o pullback limpio"
        entry_rule = "Esperar alineacion de SMA20/40 y confirmacion de volumen antes de operar."

    if signal == "BUY" and confluence_confirmed and not risk_high:
        stock_plan = "Operable segun la estrategia: usar entrada, stop y objetivo del confluence."
    elif signal == "BUY" and confluence_confirmed and risk_high:
        stock_plan = "Setup confirmado, pero riesgo alto; reducir tamano o esperar stop mas cercano."
    elif signal == "BUY":
        stock_plan = "Watchlist fuerte: no entrar todavia; esperar confirmacion de 15m/1h."
    elif signal == "WATCH":
        stock_plan = "Vigilar: falta una condicion antes de operar."
    else:
        stock_plan = "No operar: la estrategia no tiene compra valida ahora."

    if confluence_wait and signal == "BUY":
        stock_plan += " La lectura intradia todavia no acompana."
    if risk_high:
        stock_plan += " El stop actual queda lejos; el riesgo supera 3%."

    if market == "stock":
        if signal == "BUY" and confluence_confirmed and not risk_high:
            options_plan = "Opciones: considerar call/debit spread liquido solo si spread, DTE y volumen son sanos."
        elif signal == "BUY":
            options_plan = "Opciones: esperar; no comprar contratos hasta que 15m/1h confirme entrada."
        else:
            options_plan = "Opciones: no operar sin setup BUY y confluence confirmado."
    else:
        options_plan = "No aplica para crypto."

    return {
        "regime": regime,
        "strategy": strategy,
        "entry_rule": entry_rule,
        "stock_plan": stock_plan,
        "options_plan": options_plan,
        "timing": "Pre/post market se usa solo como informacion; la entrada se valida con volumen y 15m/1h.",
        "score_note": f"Score {score}: senal {signal or '-'} en {timeframe}.",
    }


def _pct_distance(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None or reference == 0:
        return None
    return ((value / reference) - 1.0) * 100.0


def _status(active: bool, watch: bool = False) -> str:
    if active:
        return "ACTIVE"
    if watch:
        return "WATCH"
    return "BLOCKED"


def detect_reference_strategies(chart_df: pd.DataFrame, setup: dict[str, Any]) -> list[dict[str, str]]:
    """Detect the strategy families shown in the user's reference photos."""
    if chart_df.empty:
        return []

    complete = chart_df.dropna(subset=["close"]).copy()
    if complete.empty:
        return []

    last = complete.iloc[-1]
    close = _safe_float(last.get("close"))
    ema9 = _safe_float(last.get("ema9"))
    sma20 = _safe_float(last.get("sma20"))
    sma40 = _safe_float(last.get("sma40"))
    sma100 = _safe_float(last.get("sma100"))
    sma200 = _safe_float(last.get("sma200"))
    upper = _safe_float(last.get("bb_upper"))
    lower = _safe_float(last.get("bb_lower"))
    resistance = _safe_float(last.get("range_high_60"))
    support = _safe_float(last.get("range_low_60"))
    channel_width = _safe_float(last.get("channel_width_pct"))
    rel_vol = _safe_float(last.get("relative_volume"))
    setup_name = _safe_text(setup.get("setup"))
    signal = _safe_text(setup.get("signal"))

    has_stack = all(value is not None for value in [close, sma20, sma40, sma100, sma200])
    bullish_stack = bool(has_stack and sma20 > sma40 > sma100 > sma200)
    bearish_stack = bool(has_stack and sma20 < sma40 < sma100 < sma200)
    close_above_200 = bool(close is not None and sma200 is not None and close > sma200)
    close_above_20_40 = bool(close is not None and sma20 is not None and sma40 is not None and close > sma20 and close > sma40)
    near_ema9 = abs(_pct_distance(close, ema9) or 999.0) <= 1.5
    near_sma20_40 = min(abs(_pct_distance(close, sma20) or 999.0), abs(_pct_distance(close, sma40) or 999.0)) <= 3.0
    near_sma100_200 = min(abs(_pct_distance(close, sma100) or 999.0), abs(_pct_distance(close, sma200) or 999.0)) <= 3.5
    near_resistance = abs(_pct_distance(close, resistance) or 999.0) <= 2.0
    near_support = abs(_pct_distance(close, support) or 999.0) <= 2.0
    compressed_channel = bool(channel_width is not None and channel_width <= 0.22)
    broad_channel = bool(channel_width is not None and channel_width <= 0.35)
    strong_volume = bool(rel_vol is not None and rel_vol >= 1.1)
    band_breakout = bool(close is not None and upper is not None and close > upper)
    lower_reclaim = bool(close is not None and lower is not None and support is not None and close > support and close > lower)

    rows: list[dict[str, str]] = []

    rows.append(
        {
            "family": "Canal alcista con tendencia alcista",
            "status": _status(bullish_stack and close_above_20_40, bullish_stack or setup_name in {"PULLBACK", "EARLY_UPTREND"}),
            "trigger": "Rebote en EMA9/SMA20/SMA40",
            "action": (
                "Buscar entrada solo si 15m confirma rebote y volumen."
                if bullish_stack and (near_ema9 or near_sma20_40)
                else "Esperar pullback a EMA9, SMA20 o SMA40."
            ),
            "why": "La estructura ideal es SMA20 > SMA40 > SMA100 > SMA200 con precio respetando medias.",
        }
    )

    rows.append(
        {
            "family": "Canal fortalecido de largo plazo",
            "status": _status(bullish_stack and close_above_20_40 and signal in {"BUY", "WATCH"}, bullish_stack),
            "trigger": "SMA20 y SMA40 sostienen el avance",
            "action": "Comprar pullback controlado; evitar perseguir si esta muy extendido sobre SMA20.",
            "why": "Replica la referencia de AMD: canal principal guiado por SMA20/40.",
        }
    )

    rows.append(
        {
            "family": "Tendencia alcista de largo plazo",
            "status": _status(close_above_200 and bullish_stack, close_above_200 and not bearish_stack),
            "trigger": "Precio sobre SMA200 y medias largas alineadas",
            "action": "Mantener sesgo alcista; entradas nuevas necesitan confirmacion 15m/1h.",
            "why": "SMA100/SMA200 definen el filtro de direccion principal.",
        }
    )

    lateral_active = broad_channel and not bullish_stack and not bearish_stack
    rows.append(
        {
            "family": "Canal lateral",
            "status": _status(lateral_active, broad_channel),
            "trigger": "Patron imparable / salto por manipulacion",
            "action": (
                "Comprar ruptura con volumen o rebote en soporte; evitar largos pegados al techo."
                if not near_resistance
                else "Esta cerca del techo del canal; esperar ruptura confirmada o retroceso."
            ),
            "why": "Usa soporte/resistencia de 60 velas y bandas para detectar rango.",
        }
    )

    lateral_long = compressed_channel or near_sma100_200
    rows.append(
        {
            "family": "Tendencia lateral de largo plazo",
            "status": _status(lateral_long, broad_channel or near_sma100_200),
            "trigger": "Cruce de medias / busqueda SMA100-SMA200",
            "action": (
                "Esperar ruptura de resistencia con volumen o rebote claro en SMA100/SMA200."
                if lateral_long
                else "No es lateral limpio; priorizar la lectura del regimen dominante."
            ),
            "why": "Se enfoca en cruces, rebote en techo y fuerza inversa entre SMA100/SMA200.",
        }
    )

    rows.append(
        {
            "family": "Banda / nube de volatilidad",
            "status": _status(band_breakout or lower_reclaim, upper is not None and lower is not None),
            "trigger": "Ruptura de banda o recuperacion desde banda baja",
            "action": (
                "Validar con volumen antes de entrada."
                if band_breakout or lower_reclaim
                else "Usar la nube como contexto; no es gatillo por si sola."
            ),
            "why": "La nube ayuda a ver expansion, compresion y extremos del precio.",
        }
    )

    if strong_volume:
        for row in rows:
            if row["status"] == "WATCH":
                row["action"] += " Volumen acompana."
    if near_support:
        rows.append(
            {
                "family": "Rebote en soporte",
                "status": "WATCH",
                "trigger": "Precio cerca del piso del canal",
                "action": "Esperar vela de rechazo y confirmacion 15m antes de comprar.",
                "why": "La zona de soporte puede dar mejor riesgo que entrar en medio del rango.",
            }
        )

    for salto in detect_salto_setups(chart_df, setup):
        rows.append(
            {
                "family": str(salto.get("family")),
                "status": str(salto.get("status")),
                "trigger": str(salto.get("trigger")),
                "action": str(salto.get("action")),
                "why": str(salto.get("why")),
            }
        )

    return rows


def latest_chart_strategy_events(chart_df: pd.DataFrame, setup: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return the latest actionable chart events that match the strategy photos."""
    if chart_df.empty:
        return []

    complete = chart_df.dropna(subset=["close"]).copy()
    if complete.empty:
        return []
    setup = setup or {}
    last = complete.iloc[-1]
    prev = complete.iloc[-2] if len(complete) >= 2 else last

    close = _safe_float(last.get("close"))
    open_ = _safe_float(last.get("open")) or close
    low = _safe_float(last.get("low")) or close
    sma20 = _safe_float(last.get("sma20"))
    sma40 = _safe_float(last.get("sma40"))
    sma100 = _safe_float(last.get("sma100"))
    sma200 = _safe_float(last.get("sma200"))
    prev_sma20 = _safe_float(prev.get("sma20"))
    prev_sma40 = _safe_float(prev.get("sma40"))
    prev_sma100 = _safe_float(prev.get("sma100"))
    rel_vol = _safe_float(last.get("relative_volume"))
    support = _safe_float(last.get("range_low_60"))
    resistance = _safe_float(last.get("range_high_60"))
    setup_name = _safe_text(setup.get("setup"))

    has_stack = close is not None and all(value is not None for value in [sma20, sma40, sma100, sma200])
    bullish_stack = bool(has_stack and close > sma20 > sma40 > sma100 > sma200)
    close_above_200 = bool(close is not None and sma200 is not None and close > sma200)
    green_close = bool(close is not None and open_ is not None and close >= open_)
    near_sma20_40 = min(abs(_pct_distance(close, sma20) or 999.0), abs(_pct_distance(close, sma40) or 999.0)) <= 2.5
    near_support = abs(_pct_distance(close, support) or 999.0) <= 2.0
    near_resistance = abs(_pct_distance(close, resistance) or 999.0) <= 2.0
    strong_volume = bool(rel_vol is not None and rel_vol >= 1.1)

    events: list[dict[str, Any]] = []

    def add_event(event: str, status: str, marker: str, meaning: str, wait_for: str, color: str) -> None:
        if close is None:
            return
        events.append(
            {
                "ts": last.get("ts"),
                "price": close,
                "event": event,
                "status": status,
                "marker": marker,
                "what_it_means": meaning,
                "wait_for": wait_for,
                "color": color,
            }
        )

    if bullish_stack:
        add_event(
            "MA_STACK_BULL",
            "ACTIVE",
            "Canal alcista",
            "SMA20 > SMA40 > SMA100 > SMA200 y precio sobre las medias.",
            "Buscar pullback o continuacion con 15m BUY y volumen.",
            "#22c55e",
        )

    if prev_sma20 is not None and prev_sma40 is not None and sma20 is not None and sma40 is not None:
        if prev_sma20 <= prev_sma40 and sma20 > sma40:
            add_event(
                "SMA20_CROSS_SMA40",
                "ACTIVE",
                "Cruce 20/40",
                "La media rapida recupera la media de tendencia corta.",
                "Confirmar que el precio mantenga SMA20 como soporte.",
                "#38bdf8",
            )
        elif sma20 > sma40 and abs(_pct_distance(sma20, sma40) or 999.0) <= 1.5:
            add_event(
                "SMA20_OVER_SMA40",
                "WATCH",
                "20 sobre 40",
                "La estructura corta sigue positiva, pero no es un cruce nuevo.",
                "Esperar entrada limpia en 15m o rebote en SMA20/SMA40.",
                "#38bdf8",
            )

    if prev_sma20 is not None and prev_sma100 is not None and sma20 is not None and sma100 is not None:
        if prev_sma20 <= prev_sma100 and sma20 > sma100:
            add_event(
                "SMA20_CROSS_SMA100",
                "ACTIVE",
                "Cruce 20/100",
                "La fuerza de corto plazo supera una media principal.",
                "Esperar retroceso controlado o ruptura con volumen.",
                "#a78bfa",
            )

    if green_close and near_sma20_40 and (bullish_stack or close_above_200 or setup_name == "PULLBACK"):
        add_event(
            "PULLBACK_REBOUND",
            "ACTIVE",
            "Rebote en media",
            "Precio respeta SMA20/SMA40 y cierra fuerte.",
            "Entrada solo si 15m confirma y el stop queda cerca.",
            "#f59e0b",
        )

    if resistance is not None and close is not None:
        if close > resistance and strong_volume:
            add_event(
                "RESISTANCE_BREAK",
                "ACTIVE",
                "Ruptura con volumen",
                "Precio rompe resistencia de rango con volumen relativo fuerte.",
                "Usar entrada con stop bajo la ruptura; evitar perseguir si se extiende.",
                "#22d3ee",
            )
        elif near_resistance:
            add_event(
                "RESISTANCE_TEST",
                "WATCH",
                "Probando resistencia",
                "Precio esta cerca del techo del canal.",
                "Esperar ruptura con volumen o rechazo para evitar entrada tarde.",
                "#22d3ee",
            )

    if support is not None and close is not None and low is not None:
        if low <= support * 1.01 and close > support and green_close:
            add_event(
                "SUPPORT_REBOUND",
                "ACTIVE",
                "Rebote en soporte",
                "Precio defendio soporte de rango.",
                "Confirmar 15m BUY; stop debe ir debajo del soporte.",
                "#60a5fa",
            )
        elif near_support:
            add_event(
                "SUPPORT_TEST",
                "WATCH",
                "Probando soporte",
                "Precio esta cerca del piso del canal.",
                "Esperar rebote verde o perder soporte para evitar entrada anticipada.",
                "#60a5fa",
            )

    if strong_volume:
        add_event(
            "VOLUME_CONFIRM",
            "ACTIVE",
            "Volumen confirma",
            "Volumen relativo mayor a 1.10x.",
            "Solo usarlo a favor de una entrada tecnica valida.",
            "#eab308",
        )
    elif rel_vol is not None and rel_vol < 0.8:
        add_event(
            "LOW_VOLUME",
            "BLOCKED",
            "Volumen debil",
            "El movimiento no tiene volumen suficiente.",
            "Esperar que el volumen acompanhe antes de operar.",
            "#ef4444",
        )

    salto_colors = {
        "SALTO_EMA_HOURS": "#14b8a6",
        "SALTO_MA_DISTANCE": "#84cc16",
        "SALTO_ATH_BREAKOUT": "#f97316",
        "SALTO_EMA_2H_BEARISH": "#ef4444",
        "SALTO_CHANNEL_CHANGE": "#c084fc",
        "PATRON_IMPARABLE_EMA9": "#22c55e",
    }
    for salto in detect_salto_setups(complete, setup):
        if salto.get("status") == "BLOCKED":
            continue
        add_event(
            str(salto.get("key")),
            str(salto.get("status")),
            str(salto.get("family")),
            str(salto.get("why")),
            str(salto.get("action")),
            salto_colors.get(str(salto.get("key")), "#f97316"),
        )

    order = {"ACTIVE": 0, "WATCH": 1, "BLOCKED": 2}
    return sorted(events, key=lambda row: (order.get(str(row.get("status")), 9), str(row.get("event"))))
