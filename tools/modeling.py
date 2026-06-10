"""Baseline modeling utilities for Roxy AI.

Provides simple feature loader stubs, training/evaluation helpers, and a
small backtest helper to apply binary signals to price series.

This is intentionally small and dependency-light; it uses scikit-learn when
available, otherwise falls back to a simple numpy implementation for tests.
"""
from __future__ import annotations

import os
import json
import logging
from typing import Tuple, Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger("roxy.modeling")

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, roc_auc_score
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False


@dataclass
class ModelMetrics:
    accuracy: float
    auc: Optional[float]


def load_feature_window(symbol: str, lookback: int = 100) -> pd.DataFrame:
    """Load a recent feature window for `symbol`.

    This is a convenience stub. It will try to read `db/ohlcv` via `sqlite3` and
    compute simple returns and moving averages. If DB access fails it returns an
    empty DataFrame.
    """
    try:
        import sqlite3
        db = os.path.join(os.getcwd(), "db", "roxy.db")
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT ts, close FROM ohlcv WHERE symbol=? ORDER BY ts DESC LIMIT ?", (symbol, lookback*2))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["ts", "close"])
        df["ts"] = pd.to_datetime(df["ts"])
        df = df.sort_values("ts").reset_index(drop=True)
        # basic features: returns, 3/10/30 SMA
        df["ret"] = df["close"].pct_change().fillna(0)
        df["sma3"] = df["close"].rolling(3).mean().bfill()
        df["sma10"] = df["close"].rolling(10).mean().bfill()
        df["sma30"] = df["close"].rolling(30).mean().bfill()
        df["momentum"] = df["close"] / df["sma10"] - 1.0
        return df.tail(lookback).reset_index(drop=True)
    except Exception:
        logger.exception("failed to load feature window for %s", symbol)
        return pd.DataFrame()


def prepare_training_data(df: pd.DataFrame, label_horizon: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    """Build X, y from a feature DataFrame using forward returns as labels.

    y = 1 if forward return over `label_horizon` candles > 0 else 0.
    """
    if df.empty:
        return np.empty((0, 0)), np.empty((0,))
    prices = df["close"].values
    forward = np.roll(prices, -label_horizon) / prices - 1.0
    # last rows without forward target
    valid = ~np.isnan(forward)[:-label_horizon] if label_horizon > 0 else np.ones(len(prices), dtype=bool)
    X = df.loc[: len(prices) - label_horizon - 1, ["ret", "sma3", "sma10", "sma30", "momentum"]].values
    y = (forward[: len(prices) - label_horizon] > 0).astype(int)
    return X, y


def train_baseline_model(X: np.ndarray, y: np.ndarray, test_size: float = 0.2, random_state: int = 42) -> Tuple[Optional[object], ModelMetrics]:
    """Train a simple Logistic Regression baseline and return model + metrics.

    If scikit-learn is not available, trains a trivial mean-predictor.
    """
    if X.size == 0 or y.size == 0:
        raise ValueError("empty training data")
    if SKLEARN_AVAILABLE:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state)
        model = LogisticRegression(max_iter=200)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        probs = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None
        acc = float(accuracy_score(y_test, preds))
        auc = float(roc_auc_score(y_test, probs)) if probs is not None else None
        return model, ModelMetrics(accuracy=acc, auc=auc)
    else:
        # trivial predictor: always predict the majority class
        from collections import Counter

        cnt = Counter(y.tolist())
        majority = 1 if cnt[1] >= cnt[0] else 0
        def model_stub(X_in):
            return np.array([majority] * len(X_in))
        # compute metrics on arbitrary split
        n = len(y)
        split = int(n * (1 - test_size))
        y_test = y[split:]
        preds = model_stub(X[split:])
        acc = float((preds == y_test).mean()) if len(y_test) else 0.0
        return model_stub, ModelMetrics(accuracy=acc, auc=None)


def quick_backtest_from_predictions(prices: pd.Series, preds: np.ndarray, size_pct: float = 0.01) -> dict:
    """Run a simple backtest applying binary predictions to a price series.

    - longs when pred==1, flat otherwise
    - entry at next open (approximated by next close), no slippage
    Returns cumulative returns and simple metrics.
    """
    if len(prices) != len(preds):
        raise ValueError("prices and preds length mismatch")
    returns = prices.pct_change().fillna(0).values
    # apply prediction as position fraction
    pos = preds.astype(float)
    pnl = pos * returns
    cum = np.cumprod(1 + pnl) - 1
    total_return = float(cum[-1]) if len(cum) else 0.0
    # compute simple annualized-like metric (assume daily)
    ann_return = (1 + total_return) ** (252 / len(cum)) - 1 if len(cum) else 0.0
    sharpe = (np.mean(pnl) / (np.std(pnl) + 1e-9)) * np.sqrt(252) if np.std(pnl) > 0 else 0.0
    return {"total_return": total_return, "annualized": ann_return, "sharpe": float(sharpe)}
