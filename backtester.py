"""Simple backtest runner that replays OHLCV and uses `score_setup` to generate entries.

This is intentionally small: it buys one unit when `score >= buy_score` and closes
position when price hits TP1 or Stop based on the `score_setup` outputs.
"""
from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime

from roxy_time import utc_now_naive_iso

import pandas as pd

from execution import PaperTrader
from roxy_scanner import score_setup, add_indicators
from logging_config import get_logger
try:
    import storage
except Exception:
    storage = None

logger = get_logger("backtester")


def run_backtest(
    df: pd.DataFrame,
    trader: Optional[PaperTrader] = None,
    buy_score: int = 55,
    starting_capital: float = 10000.0,
    position_size: float = 0.01,
    slippage_pct: float = 0.0005,
    fee_pct: float = 0.0005,
    name: str = "default",
    warmup: int = 60,
) -> Dict[str, float]:
    """Run a simple backtest and return metrics.

    Parameters
    - starting_capital: initial cash.
    - position_size: fraction of current equity to allocate per trade (e.g. 0.01 = 1%).
    - slippage_pct: fractional slippage applied to executed prices.
    - fee_pct: fractional fee per trade (applied on traded notional at entry and exit).
    """
    if trader is None:
        trader = PaperTrader()

    equity = float(starting_capital)
    trades = 0
    wins = 0
    losses = 0
    realized_pnl = 0.0
    equity_curve: list[float] = []

    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1].copy()
        try:
            meta = score_setup(window)
        except KeyError:
            # try to compute indicators if raw OHLCV is present
            if "close" in window.columns:
                window = add_indicators(window).dropna()
                if len(window) < warmup:
                    continue
                meta = score_setup(window)
            else:
                continue
        score = meta.get("score")
        if score is None:
            continue

        sym = window.iloc[-1].get("symbol", "TEST")
        pos = trader.get_position(sym)
        if score >= buy_score and pos <= 0:
            entry_price = meta.get("entry")
            stop = meta.get("stop")
            tp1 = meta.get("tp1")
            if entry_price is None:
                continue
            entry_price = float(entry_price)

            # apply slippage: buyer pays more
            entry_price_adj = entry_price * (1.0 + float(slippage_pct))
            # determine quantity from current equity and position_size
            qty = (equity * float(position_size)) / entry_price_adj
            if qty <= 0:
                continue

            trader.buy(sym, qty, entry_price_adj)
            trades += 1

            # simulate forward until TP or stop hit
            closed = False
            for j in range(i + 1, len(df)):
                row = df.iloc[j]
                high = float(row["high"])
                low = float(row["low"])
                if tp1 is not None and high >= float(tp1):
                    exit_price = float(tp1)
                    exit_price_adj = exit_price * (1.0 - float(slippage_pct))
                    trader.sell(sym, qty, exit_price_adj)
                    gross = (exit_price_adj - entry_price_adj) * qty
                    fees = float(fee_pct) * (entry_price_adj * qty) + float(fee_pct) * (exit_price_adj * qty)
                    pnl = gross - fees
                    realized_pnl += pnl
                    equity += pnl
                    equity_curve.append(equity)
                    wins += 1
                    closed = True
                    break
                if stop is not None and low <= float(stop):
                    exit_price = float(stop)
                    exit_price_adj = exit_price * (1.0 - float(slippage_pct))
                    trader.sell(sym, qty, exit_price_adj)
                    gross = (exit_price_adj - entry_price_adj) * qty
                    fees = float(fee_pct) * (entry_price_adj * qty) + float(fee_pct) * (exit_price_adj * qty)
                    pnl = gross - fees
                    realized_pnl += pnl
                    equity += pnl
                    equity_curve.append(equity)
                    losses += 1
                    closed = True
                    break
            if not closed:
                # position still open at series end; compute unrealized using last close
                last_close = float(window.iloc[-1]["close"])
                last_price_adj = last_close * (1.0 - float(slippage_pct))
                # unrealized PnL is available but not realized into equity here
                _ = (last_price_adj - entry_price_adj) * qty

    # build summary metrics
    total_return_abs = equity - starting_capital
    total_return_pct = (total_return_abs / starting_capital) if starting_capital else 0.0
    avg_return_per_trade = (realized_pnl / trades) if trades else 0.0
    # compute max drawdown
    max_dd = 0.0
    if equity_curve:
        peak = equity_curve[0]
        for v in equity_curve:
            if v > peak:
                peak = v
            dd = (peak - v)
            if dd > max_dd:
                max_dd = dd

    # additional performance metrics (approximate, annualized by 252)
    sharpe = 0.0
    cagr = 0.0
    annual_vol = 0.0
    try:
        import math
        import numpy as np

        if len(equity_curve) > 1:
            returns = np.diff(np.array(equity_curve)) / np.array(equity_curve)[:-1]
            avg = float(returns.mean())
            std = float(returns.std(ddof=1)) if returns.size > 1 else 0.0
            annual_vol = std * (252 ** 0.5) if std else 0.0
            sharpe = (avg / std) * (252 ** 0.5) if std else 0.0
            # CAGR approximate using number of periods as 'days'
            periods = len(returns)
            if periods > 0 and equity_curve[0] > 0:
                try:
                    cagr = (equity_curve[-1] / equity_curve[0]) ** (252.0 / max(1, periods)) - 1
                except Exception:
                    cagr = 0.0
    except Exception:
        # numpy may not be available; ignore and leave zeros
        pass

    metrics = {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / trades) if trades else 0.0,
        "realized_pnl": realized_pnl,
        "total_return_abs": total_return_abs,
        "total_return_pct": total_return_pct,
        "avg_return_per_trade": avg_return_per_trade,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "cagr": cagr,
        "annual_vol": annual_vol,
        "equity_curve": equity_curve,
        "timestamp": utc_now_naive_iso(),
    }

    # persist backtest metadata if storage available
    if storage is not None:
        try:
            bt_id = storage.save_backtest_result(name, metrics)
            # persist equity series separately for easier analysis
            try:
                storage.save_equity_series(bt_id, metrics.get("equity_curve", []))
            except Exception:
                logger.exception("Failed to save equity series")
        except Exception:
            logger.exception("Failed to save backtest result")

    return metrics


if __name__ == "__main__":
    import argparse
    from config import (
        BACKTEST_STARTING_CAPITAL,
        BACKTEST_POSITION_SIZE,
        BACKTEST_SLIPPAGE_PCT,
        BACKTEST_FEE_PCT,
    )

    p = argparse.ArgumentParser(description="Run a simple replay backtest on OHLCV CSV")
    p.add_argument("path", help="Path to OHLCV CSV")
    p.add_argument("-n", "--name", default="default", help="Backtest name")
    p.add_argument("--starting-capital", type=float, default=BACKTEST_STARTING_CAPITAL)
    p.add_argument("--position-size", type=float, default=BACKTEST_POSITION_SIZE)
    p.add_argument("--slippage-pct", type=float, default=BACKTEST_SLIPPAGE_PCT)
    p.add_argument("--fee-pct", type=float, default=BACKTEST_FEE_PCT)
    p.add_argument("--warmup", type=int, default=60, help="Warmup/lookback bars required before scoring")
    p.add_argument("--buy-score", type=int, default=55)
    args = p.parse_args()

    df = pd.read_csv(args.path)
    metrics = run_backtest(
        df,
        buy_score=args.buy_score,
        starting_capital=args.starting_capital,
        position_size=args.position_size,
        slippage_pct=args.slippage_pct,
        fee_pct=args.fee_pct,
        name=args.name,
        warmup=args.warmup,
    )
    print(f"Backtest {args.name}:\n", metrics)
