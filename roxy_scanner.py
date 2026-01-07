# ===== ROXY TRADING SCANNER (PRO) =====
import os
import time
from typing import Optional

import ccxt
import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import AverageTrueRange

from logging_config import get_logger

# logger
logger = get_logger("roxy.scanner")

# -------------------------
# Helpers
# -------------------------


def safe_read_list(path: str):
    if not os.path.exists(path):
        return None
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            items.append(s)
    return items or None


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema50"] = EMAIndicator(df["close"], window=50).ema_indicator()
    df["ema200"] = EMAIndicator(df["close"], window=200).ema_indicator()
    df["rsi"] = RSIIndicator(df["close"], window=14).rsi()

    macd = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    atr = AverageTrueRange(df["high"], df["low"], df["close"], window=14)
    df["atr"] = atr.average_true_range()

    df["vol_ma20"] = df["volume"].rolling(20).mean()
    return df


def breakout_level(df: pd.DataFrame, lookback: int = 40) -> float:
    if len(df) < lookback + 2:
        return np.nan
    return float(df["high"].iloc[-(lookback + 1) : -1].max())


def support_level(df: pd.DataFrame, lookback: int = 40) -> float:
    if len(df) < lookback + 2:
        return np.nan
    return float(df["low"].iloc[-(lookback + 1) : -1].min())


def score_setup(df: pd.DataFrame, atr_mult_stop=2.0, atr_mult_tp1=2.0, atr_mult_tp2=3.5) -> dict:
    last = df.iloc[-1]
    prev = df.iloc[-2]

    reasons = []
    score = 0

    if last["close"] > last["ema200"]:
        score += 15
        reasons.append("Precio > EMA200")
    if last["ema50"] > last["ema200"]:
        score += 15
        reasons.append("EMA50 > EMA200")

    if 45 <= last["rsi"] <= 60 and last["rsi"] > prev["rsi"]:
        score += 15
        reasons.append("RSI 45–60 y subiendo")
    elif last["rsi"] < 35:
        score += 8
        reasons.append("RSI bajo")

    if last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
        score += 15
        reasons.append("MACD cruce alcista")
    elif last["macd_hist"] > prev["macd_hist"] and last["macd_hist"] > 0:
        score += 8
        reasons.append("MACD acelerando")

    if pd.notna(last["vol_ma20"]) and last["volume"] > 1.5 * last["vol_ma20"]:
        score += 15
        reasons.append("Volumen fuerte")

    res = breakout_level(df, lookback=40)
    if pd.notna(res) and last["close"] > res:
        score += 20
        reasons.append("Breakout")

    if pd.notna(last["ema50"]) and last["close"] > last["ema50"] * 1.08:
        score -= 8
        reasons.append("Extendido")

    score = int(max(0, min(100, score)))

    entry = float(last["close"])
    atr = float(last["atr"]) if pd.notna(last["atr"]) else None
    sup = support_level(df, lookback=40)

    stop = tp1 = tp2 = None
    if atr:
        base_stop = entry - atr_mult_stop * atr
        stop = min(base_stop, sup * 0.995) if pd.notna(sup) else base_stop
        tp1 = entry + atr_mult_tp1 * atr
        tp2 = entry + atr_mult_tp2 * atr

    return {
        "score": score,
        "reasons": reasons,
        "entry": entry,
        "stop": stop,
        "tp1": tp1,
        "tp2": tp2,
    }


# -------------------------
# Data fetch
# -------------------------


def fetch_crypto_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    ex = ccxt.binanceus({"enableRateLimit": True})
    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df


def fetch_stock_ohlcv(symbol: str, interval: str = "1h", period: str = "6mo") -> pd.DataFrame:
    data = yf.download(symbol, interval=interval, period=period, auto_adjust=True, progress=False, group_by="column")
    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [c[0] for c in data.columns]

    data = data.reset_index()
    ts_col = "Datetime" if "Datetime" in data.columns else ("Date" if "Date" in data.columns else data.columns[0])

    def col1d(name):
        v = data[name].values
        return v.ravel() if hasattr(v, "ravel") else v

    df = pd.DataFrame(
        {
            "ts": col1d(ts_col),
            "open": col1d("Open"),
            "high": col1d("High"),
            "low": col1d("Low"),
            "close": col1d("Close"),
            "volume": col1d("Volume"),
        }
    )
    # return cleaned frame
    return df.dropna()


# -------------------------
# Growth
# -------------------------


def growth_features(df: pd.DataFrame, lookback_52w: int = 252) -> dict:
    out = {"near_52w_high": None, "rel_volume": None, "breakout": False}
    if len(df) < lookback_52w + 10:
        return out

    recent = df.iloc[-1]
    high_52w = df["high"].iloc[-lookback_52w:].max()
    out["near_52w_high"] = float(recent["close"] / high_52w) if high_52w else None

    if pd.notna(recent.get("vol_ma20")) and recent["vol_ma20"] != 0:
        out["rel_volume"] = float(recent["volume"] / recent["vol_ma20"])

    res = breakout_level(df, lookback=40)
    out["breakout"] = bool(pd.notna(res) and recent["close"] > res)
    return out


def growth_score(df: pd.DataFrame) -> dict:
    f = growth_features(df)
    score = 0
    reasons = []
    last = df.iloc[-1]

    if last["close"] > last["ema200"]:
        score += 15
        reasons.append("Precio > EMA200")
    if last["ema50"] > last["ema200"]:
        score += 15
        reasons.append("EMA50 > EMA200")

    if f["near_52w_high"] is not None:
        if f["near_52w_high"] >= 0.95:
            score += 25
            reasons.append("Muy cerca 52W High")
        elif f["near_52w_high"] >= 0.90:
            score += 18
            reasons.append("Cerca 52W High")
        elif f["near_52w_high"] >= 0.85:
            score += 12
            reasons.append("Fuerza relativa")

    if f["rel_volume"] is not None:
        if f["rel_volume"] >= 2.0:
            score += 20
            reasons.append("Volumen fuerte")
        elif f["rel_volume"] >= 1.5:
            score += 12
            reasons.append("Volumen arriba")

    if f["breakout"]:
        score += 20
        reasons.append("Breakout")

    score = int(max(0, min(100, score)))
    return {
        "growth_score": score,
        "growth_reasons": reasons,
        "near_52w_high": f["near_52w_high"],
        "rel_volume": f["rel_volume"],
        "breakout": f["breakout"],
    }


# -------------------------
# Scanners
# -------------------------


def scan_crypto(symbols, timeframes, atr_mult_stop=2.0, atr_mult_tp1=2.0, atr_mult_tp2=3.5, limit=500):
    rows = []
    for sym in symbols:
        for tf in timeframes:
            try:
                df = fetch_crypto_ohlcv(sym, tf, limit=limit)
                df = add_indicators(df).dropna()
                if len(df) < 60:
                    continue
                sig = score_setup(df, atr_mult_stop, atr_mult_tp1, atr_mult_tp2)
                rows.append({"market": "crypto", "symbol": sym, "tf": tf, **sig})
                time.sleep(0.1)
            except Exception:
                logger.exception("scan_crypto failed for %s %s", sym, tf)
                continue
    out = pd.DataFrame(rows)
    return out.sort_values("score", ascending=False) if not out.empty else out


def scan_stocks(symbols, interval="1h", period="6mo", atr_mult_stop=2.0, atr_mult_tp1=2.0, atr_mult_tp2=3.5):
    rows = []
    for sym in symbols:
        try:
            df = fetch_stock_ohlcv(sym, interval=interval, period=period)
            if df.empty:
                continue
            df = add_indicators(df).dropna()
            if len(df) < 220:
                continue
            sig = score_setup(df, atr_mult_stop, atr_mult_tp1, atr_mult_tp2)
            rows.append({"market": "stock", "symbol": sym, "tf": interval, **sig})
        except Exception:
            logger.exception("scan_stocks failed for %s", sym)
            continue
    out = pd.DataFrame(rows)
    return out.sort_values("score", ascending=False) if not out.empty else out


def scan_growth_stocks(symbols, interval="1h", period="1y"):
    rows = []
    for sym in symbols:
        try:
            df = fetch_stock_ohlcv(sym, interval=interval, period=period)
            if df.empty:
                continue
            df = add_indicators(df).dropna()
            if len(df) < 260:
                continue
            g = growth_score(df)
            rows.append({"symbol": sym, "tf": interval, **g})
        except Exception:
            logger.exception("scan_growth_stocks failed for %s", sym)
            continue
    out = pd.DataFrame(rows)
    return out.sort_values("growth_score", ascending=False) if not out.empty else out


def risk_reward(entry: Optional[float], stop: Optional[float], tp1: Optional[float]) -> Optional[float]:
    if entry is None or stop is None or tp1 is None:
        return None
    risk = entry - stop
    reward = tp1 - entry
    if risk <= 0:
        return None
    return float(reward / risk)


def signal_from_score(score, buy=55, watch=30):
    if score is None:
        return "AVOID"
    if score >= buy:
        return "BUY"
    if score >= watch:
        return "WATCH"
    return "AVOID"


def add_trade_meta(df, buy_score=55, watch_score=30):
    if df is None or df.empty:
        return df
    df = df.copy()
    df["rr_tp1"] = df.apply(lambda r: risk_reward(r.get("entry"), r.get("stop"), r.get("tp1")), axis=1)
    df["rr_tp2"] = df.apply(lambda r: risk_reward(r.get("entry"), r.get("stop"), r.get("tp2")), axis=1)
    df["signal"] = df["score"].apply(lambda s: signal_from_score(s, buy=buy_score, watch=watch_score))
    return df


def signal_tech_advanced(
    score,
    rr_tp2,
    buy_score=55,
    watch_score=30,
    min_rr_buy_tp2=1.1,
    prebuy_score=50,
    prebuy_min_rr_tp2=1.1,
):
    # BUY: score alto + RR(TP2) mínimo
    if score is None:
        return "AVOID"
    if score >= buy_score and (rr_tp2 is None or rr_tp2 >= min_rr_buy_tp2):
        return "BUY"
    # PRE-BUY: casi BUY (para alertarte antes)
    if score >= prebuy_score and (rr_tp2 is None or rr_tp2 >= prebuy_min_rr_tp2):
        return "PRE-BUY"
    if score >= watch_score:
        return "WATCH"
    return "AVOID"
