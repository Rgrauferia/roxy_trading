"""Feature engineering helpers for Roxy Trading.

Functions:
- `compute_technical_indicators(df)`: add SMA/EMA/ATR/RSI/volatility/returns
- `get_feature_window(symbol, lookback)`: load recent OHLCV from DB and return features

This module is dependency-light and safe to call from Streamlit, modeling or LLM prompt builders.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional
import pandas as pd
import numpy as np

DB_PATH = os.path.join(os.getcwd(), "db", "roxy.db")


def _read_ohlcv_from_db(symbol: str, lookback: int = 500) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT ts, open, high, low, close, volume FROM ohlcv WHERE symbol=? ORDER BY ts DESC LIMIT ?", (symbol, lookback * 2))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"])
        df = df.sort_values("ts").reset_index(drop=True)
        return df.tail(lookback).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add common technical indicators in-place (returns a new DataFrame).

    Indicators added:
    - `ret`: pct change
    - `sma_{n}`: simple moving averages
    - `ema_{n}`: exponential moving averages
    - `atr_{n}`: average true range (rolling)
    - `rsi_{n}`: RSI
    - `vol_{n}`: rolling volatility of returns
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    out["ret"] = out["close"].pct_change().fillna(0)

    # SMAs and EMAs
    for n in (3, 10, 30):
        out[f"sma_{n}"] = out["close"].rolling(n, min_periods=1).mean()
        out[f"ema_{n}"] = out["close"].ewm(span=n, adjust=False).mean()

    # ATR
    high_low = out["high"] - out["low"]
    high_prev_close = (out["high"] - out["close"].shift(1)).abs()
    low_prev_close = (out["low"] - out["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    out["atr_14"] = tr.rolling(14, min_periods=1).mean()

    # RSI (14)
    delta = out["close"].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    roll_up = up.rolling(14, min_periods=1).mean()
    roll_down = down.rolling(14, min_periods=1).mean()
    rs = roll_up / (roll_down + 1e-9)
    out["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

    # volatility
    for n in (10, 30):
        out[f"vol_{n}"] = out["ret"].rolling(n, min_periods=1).std()

    # momentum: close / sma10 - 1
    out["momentum_10"] = out["close"] / out["sma_10"] - 1.0

    return out


def get_feature_window(symbol: str, lookback: int = 200) -> pd.DataFrame:
    """Return a DataFrame of features for `symbol` suitable for modeling or prompting."""
    df = _read_ohlcv_from_db(symbol, lookback=lookback)
    if df.empty:
        return df
    return compute_technical_indicators(df)
