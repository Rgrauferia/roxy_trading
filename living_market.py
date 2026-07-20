from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd

from roxy_trader.indicators import IndicatorConfig, add_indicators as add_central_indicators
from roxy_trader.cache_policy import cache_ttl
from roxy_trader.api_budget import observe_api_call

from symbol_detail import alpaca_env_credentials, alpaca_fallback_info, alpaca_placeholder_credential_keys


DEFAULT_STOCK_SYMBOLS = (
    "SPY",
    "QQQ",
    "NVDA",
    "TSLA",
    "AAPL",
    "MSFT",
    "AMD",
    "COIN",
    "PLTR",
    "RKLB",
    "ASTS",
    "SPCX",
)
DEFAULT_CRYPTO_SYMBOLS = ("BTC/USD", "ETH/USD", "SOL/USD", "LINK/USD", "DOGE/USD")
LIVE_PRICE_REFRESH_SECONDS = cache_ttl("live_price")
OPPORTUNITY_REFRESH_SECONDS = cache_ttl("opportunity")
DEFAULT_NEWS_FEEDS = (
    "https://finance.yahoo.com/news/rssindex",
    "https://www.nasdaq.com/feed/rssoutbound?category=IPOs",
)
ALPACA_ENDPOINT_ENV_KEYS = ("ALPACA_BASE_URL", "ALPACA_ENDPOINT", "ALPACA_API_BASE_URL")
ALPACA_PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
ALPACA_LIVE_ENDPOINT = "https://api.alpaca.markets"
HIGH_IMPACT_TERMS = (
    "ipo",
    "nasdaq",
    "nyse",
    "ticker",
    "spacex",
    "spcx",
    "earnings",
    "guidance",
    "merger",
    "acquisition",
    "sec",
    "fda",
    "bankruptcy",
    "offering",
    "split",
)
NEW_TICKER_TERMS = ("ipo", "debut", "begins trading", "priced", "nasdaq", "nyse", "ticker")
TICKER_PATTERN = re.compile(r"(?:\$|\b)([A-Z]{2,5})(?:\b)")
NOISE_TICKERS = {
    "THE",
    "AND",
    "FOR",
    "WITH",
    "FROM",
    "NYSE",
    "NASDAQ",
    "IPO",
    "SEC",
    "ETF",
    "CEO",
    "CFO",
    "USA",
    "USD",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | pd.Timestamp | None) -> str:
    if value is None:
        return ""
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def stock_market_open_state(now: datetime | None = None) -> dict[str, Any]:
    eastern = ZoneInfo("America/New_York")
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local = current.astimezone(eastern)
    minutes = local.hour * 60 + local.minute
    weekday = local.weekday()
    if weekday >= 5:
        return {"open": False, "label": "Mercado cerrado", "detail": "Fin de semana"}
    if 4 * 60 <= minutes < 9 * 60 + 30:
        return {"open": True, "label": "Premarket", "detail": "Horario extendido"}
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return {"open": True, "label": "Mercado abierto", "detail": "Sesion regular"}
    if 16 * 60 <= minutes < 20 * 60:
        return {"open": True, "label": "After-hours", "detail": "Horario extendido"}
    return {"open": False, "label": "Mercado cerrado", "detail": "Fuera de horario extendido"}


def safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def source_row(name: str, status: str, detail: str, *, last_response: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "last_response": str(last_response or "")[:260],
    }


def tradingview_chart_url(symbol: str, market: str = "stock") -> str:
    safe_symbol = "".join(char for char in str(symbol or "").upper() if char.isalnum() or char in {".", "-", "/"})
    if not safe_symbol:
        return ""
    is_crypto = str(market or "").lower() == "crypto" or "/" in safe_symbol
    chart_symbol = safe_symbol.replace("/", "") if is_crypto else safe_symbol.split("/")[0]
    return f"https://www.tradingview.com/chart/?symbol={quote(chart_symbol, safe='')}"


def normalize_history_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    data = df.copy()
    lower = {str(column).lower(): column for column in data.columns}
    rename = {}
    for target in ("ts", "open", "high", "low", "close", "volume"):
        if target in lower:
            rename[lower[target]] = target
    for timestamp_name in ("datetime", "date", "time", "timestamp"):
        if "ts" not in rename.values() and timestamp_name in lower:
            rename[lower[timestamp_name]] = "ts"
    data = data.rename(columns=rename)
    required = {"ts", "open", "high", "low", "close"}
    if not required.issubset(set(data.columns)):
        return pd.DataFrame()
    if "volume" not in data.columns:
        data["volume"] = 0.0
    data["ts"] = pd.to_datetime(data["ts"], errors="coerce", utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["ts", "open", "high", "low", "close"]).sort_values("ts")
    return data.tail(500).reset_index(drop=True)


def enrich_indicators(df: pd.DataFrame) -> pd.DataFrame:
    data = normalize_history_frame(df)
    if data.empty:
        return data
    data = add_central_indicators(
        data,
        config=IndicatorConfig(sma_windows=(20, 50, 200), ema_windows=(9, 21, 50, 200)),
    )
    data["volume_avg20"] = data["volume_sma20"]
    close = data["close"]
    data["resistance40"] = data["high"].shift(1).rolling(40, min_periods=5).max()
    data["support40"] = data["low"].shift(1).rolling(40, min_periods=5).min()
    prev_close = close.shift(24) if len(data) >= 24 else close.shift(1)
    data["change_window_pct"] = ((close - prev_close) / prev_close.replace(0, pd.NA)) * 100
    return data


def trend_regime(row: pd.Series) -> str:
    close = safe_float(row.get("close"))
    sma20 = safe_float(row.get("sma20"))
    sma50 = safe_float(row.get("sma50"))
    sma200 = safe_float(row.get("sma200"))
    if close is None or sma20 is None or sma50 is None:
        return "lateral"
    if close > sma20 > sma50 and (sma200 is None or close > sma200):
        return "alcista"
    if close < sma20 < sma50 and (sma200 is None or close < sma200):
        return "bajista"
    return "lateral"


def related_news_for_symbol(symbol: str, news: list[dict[str, Any]]) -> dict[str, Any] | None:
    base = symbol.split("/")[0].upper()
    aliases = {base}
    if base == "SPCX":
        aliases.add("SPACEX")
    for item in news:
        text = f"{item.get('title', '')} {item.get('summary', '')}".upper()
        if any(alias in text for alias in aliases):
            return item
    return None


def build_market_opportunity(
    symbol: str,
    market: str,
    df: pd.DataFrame,
    source_meta: dict[str, Any],
    *,
    related_news: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    data = enrich_indicators(df)
    if len(data) < 8:
        return None
    current = data.iloc[-1]
    previous = data.iloc[-2]
    price = safe_float(current.get("close"))
    if price is None or price <= 0:
        return None

    score = 0
    reasons: list[str] = []
    indicators: dict[str, Any] = {}
    rsi = safe_float(current.get("rsi14"))
    macd = safe_float(current.get("macd"))
    macd_signal = safe_float(current.get("macd_signal"))
    macd_hist = safe_float(current.get("macd_hist"))
    previous_macd = safe_float(previous.get("macd"))
    previous_signal = safe_float(previous.get("macd_signal"))
    previous_hist = safe_float(previous.get("macd_hist"))
    sma20 = safe_float(current.get("sma20"))
    sma50 = safe_float(current.get("sma50"))
    sma200 = safe_float(current.get("sma200"))
    resistance = safe_float(current.get("resistance40"))
    support = safe_float(current.get("support40"))
    volume = safe_float(current.get("volume")) or 0.0
    volume_avg = safe_float(current.get("volume_avg20"))
    volume_ratio = volume / volume_avg if volume_avg and volume_avg > 0 else None
    change_pct = safe_float(current.get("change_window_pct"))
    regime = trend_regime(current)

    if regime == "alcista":
        score += 18
        reasons.append("Tendencia alcista: precio sobre medias clave")
    elif regime == "bajista" and rsi is not None and rsi < 35:
        score += 8
        reasons.append("Rebote especulativo en tendencia bajista")

    if sma20 is not None and sma50 is not None and sma20 > sma50:
        score += 10
        reasons.append("SMA20 > SMA50")
    if sma200 is not None and price > sma200:
        score += 10
        reasons.append("Precio sobre SMA200")
    if rsi is not None:
        if 45 <= rsi <= 65 and rsi >= safe_float(previous.get("rsi14") or rsi):
            score += 12
            reasons.append("RSI sano y subiendo")
        elif rsi < 35:
            score += 12
            reasons.append("RSI sobrevendido")
        elif rsi > 72:
            score -= 8
            reasons.append("RSI sobrecomprado; controlar persecucion")
    if macd is not None and macd_signal is not None:
        if previous_macd is not None and previous_signal is not None and macd > macd_signal and previous_macd <= previous_signal:
            score += 16
            reasons.append("MACD cruce alcista")
        elif macd_hist is not None and previous_hist is not None and macd_hist > 0 and macd_hist > previous_hist:
            score += 10
            reasons.append("MACD acelera positivo")
    if volume_ratio is not None and volume_ratio >= 1.5:
        score += 14
        reasons.append("Volumen relativo alto")
    if resistance is not None and price > resistance:
        score += 18
        reasons.append("Breakout sobre resistencia 40 velas")
    if market == "crypto" and change_pct is not None and abs(change_pct) >= 3.0:
        score += 10
        reasons.append(f"Movimiento cripto fuerte {change_pct:.1f}%")
    if related_news:
        score += 8
        reasons.append("Noticia relacionada detectada")

    confidence = max(0, min(100, int(score)))
    if confidence < 18 and not related_news:
        return None

    fallback_stop = price * 0.965
    stop = support * 0.995 if support and support < price else fallback_stop
    risk_per_share = max(price - stop, price * 0.015)
    take_profit = price + (risk_per_share * 2.0)
    risk_pct = (price - stop) / price * 100 if price else None
    risk_level = "alto" if risk_pct and risk_pct > 7 else ("medio" if risk_pct and risk_pct > 3.5 else "controlado")
    direction = "LONG_WATCH"
    if resistance is not None and price > resistance:
        direction = "BREAKOUT"
    elif rsi is not None and rsi < 35:
        direction = "REVERSAL_WATCH"
    elif rsi is not None and rsi > 72:
        direction = "RISK_ALERT"

    indicators.update(
        {
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "rsi14": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "volume_ratio": volume_ratio,
            "support": support,
            "resistance": resistance,
            "change_window_pct": change_pct,
            "trend": regime,
        }
    )
    timestamp = pd.to_datetime(current.get("ts"), errors="coerce", utc=True)
    current_time = now or utc_now()
    age_seconds = None
    if not pd.isna(timestamp):
        age_seconds = max(0, int((current_time - timestamp.to_pydatetime()).total_seconds()))

    return {
        "symbol": symbol,
        "market": market,
        "timeframe": "1h",
        "price": price,
        "price_timestamp": iso_utc(timestamp) if not pd.isna(timestamp) else "",
        "data_age_seconds": age_seconds,
        "source": source_meta.get("label") or source_meta.get("source") or source_meta.get("provider") or "-",
        "source_mode": source_meta.get("mode") or "-",
        "source_detail": source_meta.get("detail") or "",
        "direction": direction,
        "reason": "; ".join(reasons[:8]) if reasons else "Setup tecnico vivo sin razon dominante",
        "indicators": indicators,
        "entry": price,
        "stop_loss": stop,
        "take_profit": take_profit,
        "risk_level": risk_level,
        "risk_pct": risk_pct,
        "confidence": confidence,
        "trend": regime,
        "related_news": related_news or {},
        "tradingview_url": tradingview_chart_url(symbol, market),
        "paper_only": True,
    }


def classify_signal_state(opportunity: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(opportunity, dict) or not opportunity:
        return {
            "signal_state": "API_FAIL",
            "alert_ready": False,
            "state_reason": "Sin oportunidad ni precio utilizable.",
        }
    confidence = int(opportunity.get("confidence") or 0)
    source_mode = str(opportunity.get("source_mode") or "").upper()
    data_age = safe_float(opportunity.get("data_age_seconds"))
    if source_mode in {"NO_DATA", ""}:
        return {
            "signal_state": "API_FAIL",
            "alert_ready": False,
            "state_reason": "Fuente sin datos utiles.",
        }
    if source_mode in {"PUBLIC_MARKET_DATA", "FALLBACK"}:
        return {
            "signal_state": "STALE_BLOCKED",
            "alert_ready": False,
            "state_reason": "Fuente publica/fallback; no habilita alerta rapida.",
        }
    if data_age is not None and data_age > 120:
        return {
            "signal_state": "STALE_BLOCKED",
            "alert_ready": False,
            "state_reason": f"Precio/vela con {int(data_age)}s de edad.",
        }
    if confidence >= 60:
        return {
            "signal_state": "LIVE_READY",
            "alert_ready": True,
            "state_reason": "Fuente live confirmada y confianza suficiente.",
        }
    return {
        "signal_state": "WAIT_CONFIRMATION",
        "alert_ready": False,
        "state_reason": "Setup vivo, pero falta confirmacion de confianza/entrada.",
    }


def extract_news_tickers(text: str) -> list[str]:
    tickers = []
    for match in TICKER_PATTERN.findall(str(text or "").upper()):
        if match not in NOISE_TICKERS and match not in tickers:
            tickers.append(match)
    if "SPACEX" in str(text or "").upper() and "SPCX" not in tickers:
        tickers.append("SPCX")
    return tickers[:8]


def fetch_market_news(
    feeds: tuple[str, ...] = DEFAULT_NEWS_FEEDS,
    *,
    limit: int = 12,
    timeout: float = 5.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    news: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for feed_url in feeds:
        try:
            request = Request(feed_url, headers={"User-Agent": "Mozilla/5.0 RoxyTrading/1.0"})
            with observe_api_call("rss_news", "market_feed") as observation:
                with urlopen(request, timeout=timeout) as response:
                    observation.set_http_status(getattr(response, "status", None))
                    payload = response.read()
            parsed = feedparser.parse(payload)
            entries = list(parsed.entries or [])
            sources.append(source_row(f"news:{feed_url}", "OK" if entries else "WARN", f"{len(entries)} noticias RSS"))
            for entry in entries[:limit]:
                title = str(entry.get("title") or "").strip()
                summary = str(entry.get("summary") or entry.get("description") or "").strip()
                published = entry.get("published") or entry.get("updated") or ""
                text = f"{title} {summary}"
                lowered = text.lower()
                high_impact = any(term in lowered for term in HIGH_IMPACT_TERMS)
                news.append(
                    {
                        "title": title,
                        "summary": re.sub(r"<[^>]+>", "", summary)[:320],
                        "published_at": str(published),
                        "source": feed_url,
                        "url": str(entry.get("link") or ""),
                        "tickers": extract_news_tickers(text),
                        "impact": "alto" if high_impact else "normal",
                        "new_ticker_signal": any(term in lowered for term in NEW_TICKER_TERMS),
                    }
                )
        except Exception as exc:
            sources.append(source_row(f"news:{feed_url}", "FAIL", "RSS no disponible", last_response=exc))
    unique: list[dict[str, Any]] = []
    seen = set()
    for item in news:
        key = (item.get("title"), item.get("url"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:limit], sources


def fetch_nasdaq_ipo_calendar(now: datetime | None = None, *, timeout: float = 8.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    current = now or utc_now()
    query = urlencode({"date": current.strftime("%Y-%m")})
    url = f"https://api.nasdaq.com/api/ipo/calendar?{query}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 RoxyTrading/1.0",
            "Accept": "application/json,text/plain,*/*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/market-activity/ipos",
        },
    )
    try:
        with observe_api_call("nasdaq", "ipo_calendar") as observation:
            with urlopen(request, timeout=timeout) as response:
                observation.set_http_status(getattr(response, "status", None))
                payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return [], source_row("nasdaq_ipo_calendar", "FAIL", "Calendario IPO no disponible", last_response=exc)

    rows: list[dict[str, Any]] = []
    data = payload.get("data") if isinstance(payload, dict) else {}
    calendar = data.get("priced") or data.get("upcoming") or data.get("filings") or []
    if isinstance(calendar, dict):
        for value in calendar.values():
            if isinstance(value, list):
                calendar = value
                break
    if isinstance(calendar, list):
        for item in calendar[:20]:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "company": item.get("companyName") or item.get("company") or item.get("name") or "-",
                    "symbol": item.get("proposedTickerSymbol") or item.get("symbol") or item.get("ticker") or "-",
                    "exchange": item.get("exchange") or item.get("proposedExchange") or "-",
                    "date": item.get("pricedDate") or item.get("expectedDate") or item.get("date") or "-",
                    "source": "Nasdaq IPO calendar",
                }
            )
    return rows, source_row("nasdaq_ipo_calendar", "OK" if rows else "WARN", f"{len(rows)} filas IPO")


def new_ticker_candidates(news: list[dict[str, Any]], ipos: list[dict[str, Any]], symbols: tuple[str, ...]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for item in news:
        if not item.get("new_ticker_signal") and item.get("impact") != "alto":
            continue
        for ticker in item.get("tickers") or []:
            candidates[ticker] = {
                "symbol": ticker,
                "reason": "Noticia de IPO/ticker o alto impacto",
                "source": item.get("source"),
                "headline": item.get("title"),
                "tradingview_url": tradingview_chart_url(ticker, "stock"),
            }
    for item in ipos:
        ticker = str(item.get("symbol") or "").upper()
        if ticker and ticker != "-":
            candidates[ticker] = {
                "symbol": ticker,
                "reason": "Calendario IPO",
                "source": item.get("source"),
                "headline": item.get("company"),
                "tradingview_url": tradingview_chart_url(ticker, "stock"),
            }
    if "SPCX" in symbols and "SPCX" not in candidates:
        candidates["SPCX"] = {
            "symbol": "SPCX",
            "reason": "Ticker vigilado por IPO/noticias SpaceX",
            "source": "watchlist",
            "headline": "SpaceX/SPCX en vigilancia activa",
            "tradingview_url": tradingview_chart_url("SPCX", "stock"),
        }
    return list(candidates.values())[:12]


def fetch_stock_history_fast(symbol: str, *, interval: str = "1h", period: str = "15d") -> pd.DataFrame:
    import yfinance as yf

    kwargs = {
        "interval": interval,
        "period": period,
        "auto_adjust": True,
        "progress": False,
        "group_by": "column",
        "prepost": True,
        "threads": False,
        "timeout": 8,
    }
    try:
        with observe_api_call("yfinance", "stock_history"):
            data = yf.download(symbol, **kwargs)
    except TypeError:
        kwargs.pop("timeout", None)
        with observe_api_call("yfinance", "stock_history_compat"):
            data = yf.download(symbol, **kwargs)
    if data is None or data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [column[0] for column in data.columns]
    data = data.reset_index()
    ts_col = "Datetime" if "Datetime" in data.columns else ("Date" if "Date" in data.columns else data.columns[0])
    columns = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    if not set(columns).issubset(data.columns):
        return pd.DataFrame()
    out = pd.DataFrame({"ts": data[ts_col]})
    for source, target in columns.items():
        out[target] = data[source].values.ravel() if hasattr(data[source].values, "ravel") else data[source].values
    return out


def fetch_crypto_history_fast(symbol: str, *, timeframe: str = "1h", limit: int = 180) -> pd.DataFrame:
    import ccxt

    exchange = ccxt.binanceus({"enableRateLimit": True, "timeout": 8000})
    with observe_api_call("binanceus", "ohlcv"):
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    data = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    data["ts"] = pd.to_datetime(data["ts"], unit="ms", utc=True)
    return data


def _object_value(item: Any, *names: str) -> Any:
    if isinstance(item, dict):
        for name in names:
            if name in item:
                return item.get(name)
    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return None


def env_bool_value(source: dict[str, str], key: str, default: bool = False) -> bool:
    raw = str(source.get(key) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "paper"}


def first_env_value(source: dict[str, str], keys: tuple[str, ...]) -> tuple[str, str]:
    for key in keys:
        value = str(source.get(key) or "").strip()
        if value:
            return value, key
    return "", ""


def _alpaca_feed_name(env: dict[str, str]) -> str:
    return str(env.get("ALPACA_DATA_FEED") or "iex").strip().upper() or "IEX"


def _alpaca_result_from_exception(exc: Exception) -> dict[str, Any]:
    fallback = alpaca_fallback_info("alpaca_error", exc=exc)
    return {
        "ok": False,
        "configured": True,
        "reason": fallback.get("fallback_reason") or "alpaca_error",
        "detail": fallback.get("fallback_detail") or "Alpaca no entrego datos.",
        "action": fallback.get("fallback_action") or "Revisar credenciales/permisos Alpaca.",
        "error": f"{type(exc).__name__}: {exc}",
    }


def _alpaca_placeholder_result(env: dict[str, str]) -> dict[str, Any] | None:
    placeholder_keys = alpaca_placeholder_credential_keys(env)
    if not placeholder_keys:
        return None
    return {
        "ok": False,
        "configured": False,
        "reason": "alpaca_placeholder_credentials",
        "detail": "Alpaca tiene placeholders en lugar de credenciales paper reales.",
        "action": "Reemplazar TU_KEY_PAPER/TU_SECRET_PAPER por ALPACA_API_KEY y ALPACA_API_SECRET reales de paper; luego recargar Roxy.",
        "placeholder_keys": placeholder_keys,
    }


def _alpaca_stock_data_client(env: dict[str, str]):
    credentials = alpaca_env_credentials(env)
    key = credentials.get("key")
    secret = credentials.get("secret")
    if not key or not secret or alpaca_placeholder_credential_keys(env):
        return None
    from alpaca.data.historical.stock import StockHistoricalDataClient

    return StockHistoricalDataClient(key, secret)


def _alpaca_data_feed(env: dict[str, str]):
    from alpaca.data.enums import DataFeed

    feed_name = _alpaca_feed_name(env)
    return getattr(DataFeed, feed_name, DataFeed.IEX)


def _single_symbol_payload(response: Any, symbol: str) -> Any:
    if isinstance(response, dict):
        return response.get(str(symbol).upper()) or next(iter(response.values()), None)
    return response


def fetch_alpaca_latest_trade(symbol: str, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    source_env = env if env is not None else os.environ
    credentials = alpaca_env_credentials(source_env)
    key = credentials.get("key")
    secret = credentials.get("secret")
    if not key or not secret:
        return {
            "ok": False,
            "configured": False,
            "reason": "alpaca_not_configured",
            "detail": "Alpaca no tiene credenciales disponibles para precio live.",
        }
    placeholder_result = _alpaca_placeholder_result(source_env)
    if placeholder_result:
        return placeholder_result

    try:
        from alpaca.data.requests import StockLatestTradeRequest

        feed = _alpaca_data_feed(source_env)
        client = _alpaca_stock_data_client(source_env)
        request = StockLatestTradeRequest(symbol_or_symbols=str(symbol).upper(), feed=feed)
        with observe_api_call("alpaca", "latest_trade"):
            response = client.get_stock_latest_trade(request)
        trade = _single_symbol_payload(response, symbol)
        price = safe_float(_object_value(trade, "price", "p"))
        timestamp = _object_value(trade, "timestamp", "t")
        if price is None or price <= 0:
            raise RuntimeError("Alpaca latest trade sin precio utilizable")
        price_time = pd.to_datetime(timestamp, errors="coerce", utc=True)
        if pd.isna(price_time):
            price_time = pd.Timestamp(utc_now())
        return {
            "ok": True,
            "configured": True,
            "price": price,
            "price_time": price_time.to_pydatetime(),
            "source": f"Alpaca {feed.name}",
            "source_mode": "BROKER_DATA",
            "detail": "Latest trade de Alpaca para acciones.",
        }
    except Exception as exc:
        result = _alpaca_result_from_exception(exc)
        result["detail"] = result.get("detail") or "Alpaca no entrego latest trade."
        return result


def fetch_alpaca_latest_quote(symbol: str, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    source_env = env if env is not None else os.environ
    credentials = alpaca_env_credentials(source_env)
    if not credentials.get("key") or not credentials.get("secret"):
        return {
            "ok": False,
            "configured": False,
            "reason": "alpaca_not_configured",
            "detail": "Alpaca no tiene credenciales disponibles para latest quote.",
        }
    placeholder_result = _alpaca_placeholder_result(source_env)
    if placeholder_result:
        return placeholder_result
    try:
        from alpaca.data.requests import StockLatestQuoteRequest

        feed = _alpaca_data_feed(source_env)
        client = _alpaca_stock_data_client(source_env)
        request = StockLatestQuoteRequest(symbol_or_symbols=str(symbol).upper(), feed=feed)
        with observe_api_call("alpaca", "latest_quote"):
            response = client.get_stock_latest_quote(request)
        quote = _single_symbol_payload(response, symbol)
        bid = safe_float(_object_value(quote, "bid_price", "bp", "bid"))
        ask = safe_float(_object_value(quote, "ask_price", "ap", "ask"))
        price = ((bid or 0) + (ask or 0)) / 2 if bid and ask else bid or ask
        timestamp = _object_value(quote, "timestamp", "t")
        if price is None or price <= 0:
            raise RuntimeError("Alpaca latest quote sin bid/ask utilizable")
        price_time = pd.to_datetime(timestamp, errors="coerce", utc=True)
        if pd.isna(price_time):
            price_time = pd.Timestamp(utc_now())
        return {
            "ok": True,
            "configured": True,
            "price": price,
            "bid": bid,
            "ask": ask,
            "price_time": price_time.to_pydatetime(),
            "source": f"Alpaca {feed.name}",
            "source_mode": "BROKER_DATA",
            "detail": "Latest quote de Alpaca para acciones.",
        }
    except Exception as exc:
        result = _alpaca_result_from_exception(exc)
        result["detail"] = result.get("detail") or "Alpaca no entrego latest quote."
        return result


def fetch_alpaca_latest_bar(symbol: str, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    source_env = env if env is not None else os.environ
    credentials = alpaca_env_credentials(source_env)
    if not credentials.get("key") or not credentials.get("secret"):
        return {
            "ok": False,
            "configured": False,
            "reason": "alpaca_not_configured",
            "detail": "Alpaca no tiene credenciales disponibles para latest bar.",
        }
    placeholder_result = _alpaca_placeholder_result(source_env)
    if placeholder_result:
        return placeholder_result
    try:
        from alpaca.data.requests import StockLatestBarRequest

        feed = _alpaca_data_feed(source_env)
        client = _alpaca_stock_data_client(source_env)
        request = StockLatestBarRequest(symbol_or_symbols=str(symbol).upper(), feed=feed)
        with observe_api_call("alpaca", "latest_bar"):
            response = client.get_stock_latest_bar(request)
        bar = _single_symbol_payload(response, symbol)
        price = safe_float(_object_value(bar, "close", "c"))
        timestamp = _object_value(bar, "timestamp", "t")
        if price is None or price <= 0:
            raise RuntimeError("Alpaca latest bar sin close utilizable")
        price_time = pd.to_datetime(timestamp, errors="coerce", utc=True)
        if pd.isna(price_time):
            price_time = pd.Timestamp(utc_now())
        return {
            "ok": True,
            "configured": True,
            "price": price,
            "price_time": price_time.to_pydatetime(),
            "source": f"Alpaca {feed.name}",
            "source_mode": "BROKER_DATA",
            "detail": "Latest bar de Alpaca para acciones.",
        }
    except Exception as exc:
        result = _alpaca_result_from_exception(exc)
        result["detail"] = result.get("detail") or "Alpaca no entrego latest bar."
        return result


def alpaca_error_category(reason: str) -> str:
    normalized = str(reason or "").lower()
    if normalized == "alpaca_not_configured":
        return "NOT_CONFIGURED"
    if normalized == "alpaca_placeholder_credentials":
        return "PLACEHOLDER_KEYS"
    if normalized == "alpaca_auth":
        return "AUTH_INVALID"
    if normalized == "alpaca_feed_permission":
        return "FEED_PERMISSION"
    if normalized == "alpaca_rate_limit":
        return "RATE_LIMIT"
    if normalized == "alpaca_network":
        return "NETWORK"
    if normalized.startswith("alpaca_error"):
        return "ALPACA_ERROR"
    return normalized.upper() if normalized else "UNKNOWN"


def alpaca_probe_row(name: str, result: dict[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    result = result or {}
    ok = bool(result.get("ok"))
    price_time = result.get("price_time")
    age_seconds = None
    timestamp = ""
    if price_time:
        parsed = pd.to_datetime(price_time, errors="coerce", utc=True)
        if not pd.isna(parsed):
            timestamp = iso_utc(parsed)
            age_seconds = max(0, int((now - parsed.to_pydatetime()).total_seconds()))
    reason = str(result.get("reason") or "")
    return {
        "probe": name,
        "status": "OK" if ok else "FAIL",
        "ok": ok,
        "price": safe_float(result.get("price")),
        "timestamp": timestamp,
        "age_seconds": age_seconds,
        "reason": reason,
        "error_category": "" if ok else alpaca_error_category(reason),
        "detail": result.get("detail") or result.get("error") or "",
        "action": result.get("action") or "",
        "last_response": str(result.get("error") or result.get("detail") or "")[:260],
    }


def _alpaca_skipped_probe(name: str, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "probe": name,
        "status": "SKIPPED",
        "ok": False,
        "price": None,
        "timestamp": "",
        "age_seconds": None,
        "reason": source.get("reason") or "",
        "error_category": source.get("error_category") or "",
        "detail": "Omitido porque latest_trade ya fallo por auth/feed.",
        "action": source.get("action") or "",
        "last_response": source.get("last_response") or "",
    }


def build_alpaca_market_data_diagnostic(
    symbol: str = "AAPL",
    *,
    env: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    source_env = env if env is not None else os.environ
    normalized_symbol = str(symbol or "AAPL").strip().upper()
    if "/" in normalized_symbol:
        normalized_symbol = "AAPL"
    credentials = alpaca_env_credentials(source_env)
    endpoint, endpoint_name = first_env_value(source_env, ALPACA_ENDPOINT_ENV_KEYS)
    paper_flag = env_bool_value(source_env, "ALPACA_PAPER", True)
    expected_endpoint = ALPACA_PAPER_ENDPOINT if paper_flag else ALPACA_LIVE_ENDPOINT
    effective_endpoint = endpoint or expected_endpoint
    endpoint_lower = effective_endpoint.lower()
    endpoint_mismatch = bool(
        endpoint
        and (
            (paper_flag and "paper-api.alpaca.markets" not in endpoint_lower)
            or (not paper_flag and "paper-api.alpaca.markets" in endpoint_lower)
        )
    )
    placeholder_keys = alpaca_placeholder_credential_keys(source_env)
    configured = bool(credentials.get("key") and credentials.get("secret")) and not placeholder_keys
    credential_keys = [key for key in (credentials.get("key_name"), credentials.get("secret_name")) if key]
    feed = _alpaca_feed_name(source_env)
    base = {
        "symbol": normalized_symbol,
        "generated_at": iso_utc(current),
        "configured": configured,
        "credential_keys": credential_keys,
        "placeholder_keys": placeholder_keys,
        "missing_keys": [
            key
            for key, present in (
                ("ALPACA_API_KEY", bool(credentials.get("key"))),
                ("ALPACA_API_SECRET or ALPACA_SECRET_KEY", bool(credentials.get("secret"))),
            )
            if not present
        ],
        "feed": feed,
        "paper_flag": paper_flag,
        "mode": "paper" if paper_flag else "live_readonly",
        "expected_endpoint": expected_endpoint,
        "effective_endpoint": effective_endpoint,
        "endpoint_key": endpoint_name,
        "endpoint_mismatch": endpoint_mismatch,
        "live_orders_allowed": False,
        "paper_only": True,
    }
    if not configured:
        if placeholder_keys:
            return {
                **base,
                "status": "FAIL",
                "error_category": "PLACEHOLDER_KEYS",
                "safe_for_signals": False,
                "summary": "Alpaca market data tiene placeholders de credenciales.",
                "next_action": "Reemplazar TU_KEY_PAPER/TU_SECRET_PAPER por credenciales paper reales en .env y recargar el servicio Roxy.",
                "probes": [],
            }
        return {
            **base,
            "status": "FAIL",
            "error_category": "NOT_CONFIGURED",
            "safe_for_signals": False,
            "summary": "Alpaca market data no configurado.",
            "next_action": "Configurar ALPACA_API_KEY y ALPACA_API_SECRET/ALPACA_SECRET_KEY en el entorno del servicio Streamlit.",
            "probes": [],
        }

    trade = alpaca_probe_row("latest_trade", fetch_alpaca_latest_trade(normalized_symbol, env=source_env), now=current)
    run_remaining = trade["ok"] or trade["error_category"] not in {"AUTH_INVALID", "FEED_PERMISSION"}
    quote = (
        alpaca_probe_row("latest_quote", fetch_alpaca_latest_quote(normalized_symbol, env=source_env), now=current)
        if run_remaining
        else _alpaca_skipped_probe("latest_quote", trade)
    )
    bar = (
        alpaca_probe_row("latest_bar", fetch_alpaca_latest_bar(normalized_symbol, env=source_env), now=current)
        if run_remaining
        else _alpaca_skipped_probe("latest_bar", trade)
    )
    probes = [trade, quote, bar]
    ok_count = sum(1 for item in probes if item.get("ok"))
    failed_categories = [str(item.get("error_category") or "") for item in probes if item.get("error_category")]
    primary_category = failed_categories[0] if failed_categories else ""
    if endpoint_mismatch:
        status = "FAIL"
        primary_category = "ENDPOINT_MISMATCH"
        summary = "Alpaca tiene endpoint desalineado con ALPACA_PAPER; Roxy bloquea ejecucion."
        next_action = "Alinear ALPACA_PAPER con ALPACA_BASE_URL: paper usa https://paper-api.alpaca.markets."
    elif ok_count:
        status = "OK" if ok_count == len(probes) else "WARN"
        summary = f"Alpaca market data responde para {normalized_symbol} ({ok_count}/{len(probes)} probes OK)."
        next_action = "Usar como fuente broker read-only; ordenes reales siguen deshabilitadas."
    else:
        status = "FAIL"
        summary = f"Alpaca no entrego market data util para {normalized_symbol}."
        next_action = trade.get("action") or "Rotar/corregir credenciales, feed y permisos Alpaca."
    return {
        **base,
        "status": status,
        "error_category": primary_category,
        "safe_for_signals": status in {"OK", "WARN"} and ok_count > 0 and not endpoint_mismatch,
        "summary": summary,
        "next_action": next_action,
        "probes": probes,
    }


def fetch_yfinance_live_price(symbol: str) -> dict[str, Any]:
    import yfinance as yf

    attempts = (("1d", "1m"), ("5d", "1m"), ("5d", "5m"), ("1mo", "15m"))
    last_error = "sin velas"
    try:
        quote = fetch_yfinance_quote_price(symbol)
        if quote.get("price"):
            return quote
    except Exception as exc:
        last_error = f"quote: {type(exc).__name__}: {exc}"
    for period, interval in attempts:
        try:
            with observe_api_call("yfinance", "live_price_history"):
                data = yf.download(
                    symbol,
                    period=period,
                    interval=interval,
                    auto_adjust=True,
                    progress=False,
                    prepost=True,
                    threads=False,
                    timeout=5,
                )
            data = normalize_history_frame(data.reset_index() if data is not None and not data.empty else pd.DataFrame())
            if data.empty:
                last_error = f"sin velas {period}/{interval}"
                continue
            latest = data.iloc[-1]
            price = safe_float(latest.get("close"))
            price_time = pd.to_datetime(latest.get("ts"), errors="coerce", utc=True).to_pydatetime()
            if price is None or price <= 0:
                last_error = f"precio invalido {period}/{interval}"
                continue
            return {"price": price, "price_time": price_time, "interval": interval, "period": period}
        except Exception as exc:
            last_error = f"{period}/{interval}: {type(exc).__name__}: {exc}"
    raise RuntimeError(last_error)


def epoch_to_utc(value: Any) -> datetime | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp, timezone.utc)


def fetch_yfinance_quote_price(symbol: str) -> dict[str, Any]:
    import yfinance as yf

    ticker = yf.Ticker(str(symbol or "").strip().upper())
    info: dict[str, Any] = {}
    try:
        info = dict(getattr(ticker, "info", {}) or {})
    except Exception:
        info = {}
    fast_info: dict[str, Any] = {}
    try:
        fast_info = dict(getattr(ticker, "fast_info", {}) or {})
    except Exception:
        fast_info = {}

    price_candidates = [
        ("currentPrice", info.get("currentPrice"), info.get("regularMarketTime"), "currentPrice"),
        ("regularMarketPrice", info.get("regularMarketPrice"), info.get("regularMarketTime"), "regularMarketPrice"),
        ("postMarketPrice", info.get("postMarketPrice"), info.get("postMarketTime"), "postMarketPrice"),
        ("preMarketPrice", info.get("preMarketPrice"), info.get("preMarketTime"), "preMarketPrice"),
        ("fastInfoLastPrice", fast_info.get("lastPrice"), None, "fast_info.lastPrice"),
    ]
    bid = safe_float(info.get("bid") or fast_info.get("bid"))
    ask = safe_float(info.get("ask") or fast_info.get("ask"))
    previous_close = safe_float(
        info.get("previousClose")
        or info.get("regularMarketPreviousClose")
        or fast_info.get("previousClose")
        or fast_info.get("previous_close")
        or fast_info.get("regularMarketPreviousClose")
        or fast_info.get("regular_market_previous_close")
    )
    if bid and ask and ask >= bid:
        price_candidates.append(("bidAskMid", (bid + ask) / 2, info.get("regularMarketTime"), "bid/ask midpoint"))

    for field, raw_price, raw_time, label in price_candidates:
        price = safe_float(raw_price)
        if price is None or price <= 0:
            continue
        price_time = epoch_to_utc(raw_time) or utc_now()
        regular_price = safe_float(info.get("regularMarketPrice") or info.get("currentPrice") or fast_info.get("lastPrice"))
        post_price = safe_float(info.get("postMarketPrice"))
        pre_price = safe_float(info.get("preMarketPrice"))
        return {
            "price": price,
            "price_time": price_time,
            "interval": "quote",
            "period": "quote",
            "field": field,
            "label": label,
            "regular_market_price": regular_price,
            "post_market_price": post_price,
            "pre_market_price": pre_price,
            "bid": bid,
            "ask": ask,
            "previous_close": previous_close,
            "change_pct": ((price - previous_close) / previous_close)
            if previous_close not in (None, 0)
            else None,
        }
    raise RuntimeError("yfinance quote sin precio utilizable")


def build_live_price_snapshot(symbol: str, market: str, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    normalized_symbol = str(symbol or "AAPL").strip().upper()
    normalized_market = "crypto" if market == "crypto" or "/" in normalized_symbol else "stock"
    if normalized_market == "crypto" and "/" not in normalized_symbol:
        normalized_symbol = f"{normalized_symbol}/USD"
    try:
        if normalized_market == "crypto":
            import ccxt

            exchange = ccxt.binanceus({"enableRateLimit": True, "timeout": 5000})
            with observe_api_call("binanceus", "ticker"):
                ticker = exchange.fetch_ticker(normalized_symbol)
            price = safe_float(ticker.get("last") or ticker.get("close") or ticker.get("bid") or ticker.get("ask"))
            ts = ticker.get("timestamp")
            price_time = datetime.fromtimestamp(ts / 1000, timezone.utc) if ts else current
            source = "BinanceUS ticker"
            mode = "EXCHANGE_TICKER"
            provider = "BinanceUS"
            market_open = True
            latency_note = "Ticker de exchange via REST; refresco UI cada pocos segundos."
        else:
            stock_session = stock_market_open_state(current)
            alpaca_snapshot = fetch_alpaca_latest_trade(normalized_symbol)
            provider_issue = ""
            provider_action = ""
            previous_close = None
            change_pct = None
            if alpaca_snapshot.get("ok"):
                price = safe_float(alpaca_snapshot.get("price"))
                price_time = alpaca_snapshot.get("price_time") or current
                source = str(alpaca_snapshot.get("source") or "Alpaca")
                mode = str(alpaca_snapshot.get("source_mode") or "BROKER_DATA")
                provider = "Alpaca"
                market_open = bool(stock_session.get("open"))
                latency_note = str(alpaca_snapshot.get("detail") or "Dato broker Alpaca.")
                # Do not turn a confirmed broker quote into an unbounded public
                # network dependency. Optional session context must arrive in
                # the same Alpaca snapshot or remain explicitly unavailable.
                previous_close = safe_float(alpaca_snapshot.get("previous_close"))
                regular_price = safe_float(alpaca_snapshot.get("regular_market_price"))
                post_price = safe_float(alpaca_snapshot.get("post_market_price"))
                pre_price = safe_float(alpaca_snapshot.get("pre_market_price"))
                if price is not None and previous_close not in (None, 0):
                    change_pct = (price - previous_close) / previous_close
            else:
                provider_issue = str(alpaca_snapshot.get("reason") or "")
                provider_action = str(alpaca_snapshot.get("action") or alpaca_snapshot.get("detail") or "")
                fallback = fetch_yfinance_live_price(normalized_symbol)
                price = safe_float(fallback.get("price"))
                price_time = fallback.get("price_time") or current
                fallback_label = fallback.get("field") or fallback.get("interval") or "public"
                source = f"yfinance {fallback_label}"
                mode = "PUBLIC_MARKET_DATA"
                provider = "yfinance"
                market_open = bool(stock_session.get("open"))
                fallback_interval = str(fallback.get("label") or fallback_label or "public")
                latency_note = f"Dato publico {fallback_interval}; puede venir retrasado si no hay feed premium realtime."
                regular_price = safe_float(fallback.get("regular_market_price"))
                post_price = safe_float(fallback.get("post_market_price"))
                pre_price = safe_float(fallback.get("pre_market_price"))
                previous_close = safe_float(fallback.get("previous_close"))
                change_pct = safe_float(fallback.get("change_pct"))
                if price is not None and change_pct is None and previous_close not in (None, 0):
                    change_pct = (price - previous_close) / previous_close
                session_prices = []
                if regular_price is not None:
                    session_prices.append(f"regular/current {regular_price:.2f}")
                if post_price is not None:
                    session_prices.append(f"post {post_price:.2f}")
                if pre_price is not None:
                    session_prices.append(f"pre {pre_price:.2f}")
                if session_prices:
                    latency_note = f"{latency_note} Comparacion sesiones: {', '.join(session_prices)}."
                if provider_issue:
                    latency_note = f"{latency_note} Alpaca no confirmado: {provider_issue}."
        if price is None or price <= 0:
            raise RuntimeError("precio invalido")
        age_seconds = max(0, int((current - price_time).total_seconds()))
        if age_seconds <= 15:
            freshness = "LIVE"
        elif age_seconds <= 90:
            freshness = "FRESH"
        else:
            freshness = "STALE"
        return {
            "symbol": normalized_symbol,
            "market": normalized_market,
            "price": price,
            "price_timestamp": iso_utc(price_time),
            "observed_at": iso_utc(current),
            "age_seconds": age_seconds,
            "freshness": freshness,
            "source": source,
            "source_mode": mode,
            "provider": provider,
            "market_open": market_open,
            "latency_note": latency_note,
            "provider_issue": locals().get("provider_issue", ""),
            "provider_action": locals().get("provider_action", ""),
            "regular_market_price": locals().get("regular_price", None),
            "post_market_price": locals().get("post_price", None),
            "pre_market_price": locals().get("pre_price", None),
            "previous_close": locals().get("previous_close", None),
            "change_pct": locals().get("change_pct", None),
            "error": "",
        }
    except Exception as exc:
        stock_session = stock_market_open_state(current) if normalized_market == "stock" else {}
        session_closed = normalized_market == "stock" and not bool(stock_session.get("open"))
        source = text = "unavailable"
        latency_note = "No usar para trading hasta recuperar precio live."
        if session_closed:
            source = "mercado cerrado"
            text = str(stock_session.get("label") or "Mercado cerrado")
            latency_note = f"{text}: sin tick live de acciones; usa crypto 24h o espera premarket/mercado abierto."
        return {
            "symbol": normalized_symbol,
            "market": normalized_market,
            "price": None,
            "price_timestamp": "",
            "observed_at": iso_utc(current),
            "age_seconds": None,
            "freshness": "FAIL",
            "source": source,
            "source_mode": "NO_DATA",
            "provider": "",
            "market_open": False if session_closed else None,
            "latency_note": latency_note,
            "provider_issue": locals().get("provider_issue", ""),
            "provider_action": locals().get("provider_action", ""),
            "error": f"{type(exc).__name__}: {exc}",
        }


def fetch_asset_history(symbol: str, market: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if market == "crypto":
        return fetch_crypto_history_fast(symbol), {
            "provider": "ccxt",
            "source": "ccxt:binanceus",
            "mode": "EXCHANGE_API",
            "label": "BinanceUS API",
            "detail": "Velas cripto reales via ccxt/binanceus.",
            "fallback": False,
        }
    return fetch_stock_history_fast(symbol), {
        "provider": "yfinance",
        "source": "yfinance",
        "mode": "PUBLIC_MARKET_DATA",
        "label": "yfinance",
        "detail": "Velas de acciones reales via yfinance para pulso live rapido.",
        "fallback": False,
    }


def build_living_market_snapshot(
    *,
    stock_symbols: tuple[str, ...] = DEFAULT_STOCK_SYMBOLS,
    crypto_symbols: tuple[str, ...] = DEFAULT_CRYPTO_SYMBOLS,
    scan_interval_seconds: int = 30,
    now: datetime | None = None,
    news_limit: int = 12,
) -> dict[str, Any]:
    current = now or utc_now()
    news, news_sources = fetch_market_news(limit=news_limit)
    ipos, ipo_source = fetch_nasdaq_ipo_calendar(current)
    sources: list[dict[str, Any]] = [*news_sources, ipo_source]
    diagnostics_logs: list[str] = []
    opportunities: list[dict[str, Any]] = []
    errors: list[str] = []

    for market, symbols in (("stock", stock_symbols), ("crypto", crypto_symbols)):
        for symbol in symbols:
            try:
                history, meta = fetch_asset_history(symbol, market)
                data = normalize_history_frame(history)
                sources.append(
                    source_row(
                        f"{market}:{symbol}",
                        "OK" if not data.empty else "WARN",
                        f"{len(data)} velas desde {meta.get('label') or meta.get('source') or '-'}",
                        last_response=meta.get("fallback_detail") or meta.get("detail"),
                    )
                )
                related = related_news_for_symbol(symbol, news)
                opportunity = build_market_opportunity(symbol, market, data, meta, related_news=related, now=current)
                if opportunity:
                    opportunity.update(classify_signal_state(opportunity))
                    opportunities.append(opportunity)
                    diagnostics_logs.append(f"{symbol}: oportunidad {opportunity['direction']} confianza {opportunity['confidence']}")
                else:
                    diagnostics_logs.append(f"{symbol}: sin setup accionable con datos reales")
            except Exception as exc:
                message = f"{market}:{symbol} fallo: {type(exc).__name__}: {exc}"
                errors.append(message)
                diagnostics_logs.append(message)
                sources.append(source_row(f"{market}:{symbol}", "FAIL", "No se recibieron velas utilizables", last_response=exc))

    opportunities.sort(key=lambda item: (int(item.get("confidence") or 0), float(item.get("price") or 0)), reverse=True)
    source_statuses = [str(item.get("status") or "") for item in sources]
    real_source_count = sum(1 for status in source_statuses if status == "OK")
    failing_source_count = sum(1 for status in source_statuses if status == "FAIL")
    interval = max(5, int(scan_interval_seconds or OPPORTUNITY_REFRESH_SECONDS))
    next_scan = current + timedelta(seconds=interval)

    return {
        "status": "Roxy esta escaneando el mercado",
        "generated_at": iso_utc(current),
        "next_scan_at": iso_utc(next_scan),
        "scan_interval_seconds": interval,
        "data_mode": "REAL" if real_source_count else "NO_DATA",
        "paper_only": True,
        "disclaimer": "Analisis educativo para paper trading/simulacion. No coloca ordenes ni garantiza resultados.",
        "opportunities_found_today": len(opportunities),
        "active_alerts": sum(1 for item in opportunities if bool(item.get("alert_ready"))),
        "sources": sources,
        "news": news,
        "ipos": ipos,
        "new_tickers": new_ticker_candidates(news, ipos, stock_symbols),
        "opportunities": opportunities[:12],
        "diagnostics": {
            "real_source_count": real_source_count,
            "failing_source_count": failing_source_count,
            "chart_data_errors": [error for error in errors if "stock:" in error or "crypto:" in error],
            "data_errors": errors,
            "using_demo_data": False,
            "logs": diagnostics_logs[-40:],
        },
    }
