from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from moving_average_strategy import MovingAverageConfig, add_moving_averages, analyze_moving_average_setup


@dataclass(frozen=True)
class MovingAverageBacktestConfig:
    starting_capital: float = 10000.0
    position_size_pct: float = 0.25
    fee_pct: float = 0.0005
    slippage_pct: float = 0.0005
    cooldown_bars: int = 5
    warmup: int = 200


@dataclass(frozen=True)
class BacktestEligibilityConfig:
    min_profit_factor: float = 1.2
    min_return_pct: float = 0.0
    max_drawdown_pct: float = 0.15
    min_trades: int = 8
    min_buy_hold_edge_pct: float | None = None


def evaluate_backtest_eligibility(
    metrics: dict[str, Any],
    config: BacktestEligibilityConfig | None = None,
) -> dict[str, Any]:
    cfg = config or BacktestEligibilityConfig()
    reasons = []

    if int(metrics.get("trades", 0)) < cfg.min_trades:
        reasons.append(f"trades<{cfg.min_trades}")

    if float(metrics.get("profit_factor", 0.0)) < cfg.min_profit_factor:
        reasons.append(f"profit_factor<{cfg.min_profit_factor:g}")

    if float(metrics.get("total_return_pct", 0.0)) < cfg.min_return_pct:
        reasons.append(f"return<{cfg.min_return_pct:.2%}")

    if float(metrics.get("max_drawdown_pct", 0.0)) > cfg.max_drawdown_pct:
        reasons.append(f"drawdown>{cfg.max_drawdown_pct:.2%}")

    if cfg.min_buy_hold_edge_pct is not None:
        edge = float(
            metrics.get(
                "buy_hold_edge_pct",
                float(metrics.get("total_return_pct", 0.0)) - float(metrics.get("buy_hold_return_pct", 0.0)),
            )
        )
        if edge < cfg.min_buy_hold_edge_pct:
            reasons.append(f"buy_hold_edge<{cfg.min_buy_hold_edge_pct:.2%}")

    return {
        "eligible": not reasons,
        "eligibility_reasons": reasons,
    }


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(column).lower() for column in out.columns]
    required = {"open", "high", "low", "close"}
    missing = required.difference(out.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {', '.join(sorted(missing))}")
    if "volume" not in out.columns:
        out["volume"] = 0
    if "ts" in out.columns:
        out = out.sort_values("ts")
    return out.reset_index(drop=True)


def _row_ts(row: pd.Series, index: int) -> str:
    value = row.get("ts", index)
    try:
        if pd.isna(value):
            return str(index)
    except TypeError:
        pass
    return str(value)


def _max_drawdown(values: list[float]) -> tuple[float, float]:
    peak = None
    max_abs = 0.0
    max_pct = 0.0
    for value in values:
        if peak is None or value > peak:
            peak = value
        if peak and peak > 0:
            drawdown_abs = peak - value
            drawdown_pct = drawdown_abs / peak
            max_abs = max(max_abs, drawdown_abs)
            max_pct = max(max_pct, drawdown_pct)
    return max_abs, max_pct


def _sharpe_from_equity(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    returns = np.diff(np.array(values)) / np.array(values[:-1])
    if returns.size < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if std == 0:
        return 0.0
    return float((returns.mean() / std) * np.sqrt(252))


def _profit_factor(trades: list[dict[str, Any]]) -> float:
    gross_profit = sum(float(trade["pnl"]) for trade in trades if float(trade["pnl"]) > 0)
    gross_loss = abs(sum(float(trade["pnl"]) for trade in trades if float(trade["pnl"]) < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _exit_reason(row: pd.Series) -> str | None:
    if pd.notna(row.get("sma20")) and pd.notna(row.get("sma40")) and float(row["sma20"]) < float(row["sma40"]):
        return "SMA20_BELOW_SMA40"
    if pd.notna(row.get("sma40")) and float(row["close"]) < float(row["sma40"]):
        return "CLOSE_BELOW_SMA40"
    if pd.notna(row.get("sma100")) and float(row["close"]) < float(row["sma100"]):
        return "CLOSE_BELOW_SMA100"
    return None


def run_ma_backtest(
    df: pd.DataFrame,
    *,
    symbol: str = "TEST",
    ma_config: MovingAverageConfig | None = None,
    backtest_config: MovingAverageBacktestConfig | None = None,
) -> dict[str, Any]:
    strategy_cfg = ma_config or MovingAverageConfig()
    cfg = backtest_config or MovingAverageBacktestConfig()
    raw = _normalize_ohlcv(df)
    data = add_moving_averages(raw)
    start_index = max(int(cfg.warmup), 200)

    cash = float(cfg.starting_capital)
    position: dict[str, Any] | None = None
    next_entry_allowed_index = start_index
    trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []

    if len(data) <= start_index:
        return {
            "symbol": symbol,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "starting_capital": cfg.starting_capital,
            "final_equity": cfg.starting_capital,
            "total_return_abs": 0.0,
            "total_return_pct": 0.0,
            "max_drawdown_abs": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "sharpe": 0.0,
            "buy_hold_return_pct": 0.0,
            "buy_hold_account_return_pct": 0.0,
            "buy_hold_edge_pct": 0.0,
            "exposure_pct": 0.0,
            "eligible": False,
            "eligibility_reasons": ["insufficient_data"],
            "trades_detail": [],
            "equity_curve": [],
        }

    def close_position(index: int, row: pd.Series, exit_price: float, reason: str) -> None:
        nonlocal cash, next_entry_allowed_index, position
        if position is None:
            return
        exit_price_adj = exit_price * (1.0 - cfg.slippage_pct)
        exit_notional = position["qty"] * exit_price_adj
        exit_fee = exit_notional * cfg.fee_pct
        cash += exit_notional - exit_fee
        pnl = exit_notional - exit_fee - position["entry_notional"] - position["entry_fee"]
        return_pct = pnl / position["entry_notional"] if position["entry_notional"] else 0.0
        trades.append(
            {
                "symbol": symbol,
                "entry_ts": position["entry_ts"],
                "exit_ts": _row_ts(row, index),
                "entry_index": position["entry_index"],
                "exit_index": index,
                "entry_price": position["entry_price"],
                "exit_price": exit_price_adj,
                "qty": position["qty"],
                "pnl": pnl,
                "return_pct": return_pct,
                "entry_signal_score": position["signal_score"],
                "entry_setup": position["setup"],
                "exit_reason": reason,
            }
        )
        next_entry_allowed_index = index + max(0, int(cfg.cooldown_bars))
        position = None

    for index in range(start_index, len(data)):
        row = data.iloc[index]

        if position is not None:
            if pd.notna(row.get("sma40")) and pd.notna(row.get("sma100")):
                trailing_anchor = min(float(row["sma40"]), float(row["sma100"]))
                position["stop"] = max(position["stop"], trailing_anchor * (1.0 - strategy_cfg.stop_buffer_pct / 100.0))

            if float(row["low"]) <= position["stop"]:
                close_position(index, row, float(position["stop"]), "STOP")
            else:
                reason = _exit_reason(row)
                if reason:
                    close_position(index, row, float(row["close"]), reason)

        mark_value = cash
        if position is not None:
            mark_value += position["qty"] * float(row["close"])
        equity_curve.append({"ts": _row_ts(row, index), "equity": mark_value})

        if position is not None or index >= len(data) - 1 or index < next_entry_allowed_index:
            continue

        signal = analyze_moving_average_setup(raw.iloc[: index + 1], config=strategy_cfg)
        if signal.get("signal") != "BUY":
            continue

        next_row = data.iloc[index + 1]
        entry_raw = float(next_row["open"])
        entry_price = entry_raw * (1.0 + cfg.slippage_pct)
        equity_now = cash
        entry_notional = equity_now * cfg.position_size_pct
        if entry_notional <= 0 or cash < entry_notional:
            continue
        qty = entry_notional / entry_price
        entry_fee = entry_notional * cfg.fee_pct
        if cash < entry_notional + entry_fee:
            continue

        stop = signal.get("stop")
        if stop is None or pd.isna(stop) or float(stop) <= 0:
            stop = float(signal["sma100"]) * (1.0 - strategy_cfg.stop_buffer_pct / 100.0)

        cash -= entry_notional + entry_fee
        position = {
            "entry_index": index + 1,
            "entry_ts": _row_ts(next_row, index + 1),
            "entry_price": entry_price,
            "entry_notional": entry_notional,
            "entry_fee": entry_fee,
            "qty": qty,
            "stop": float(stop),
            "signal_score": signal.get("score"),
            "setup": signal.get("setup"),
        }

    if position is not None:
        last_index = len(data) - 1
        last_row = data.iloc[last_index]
        close_position(last_index, last_row, float(last_row["close"]), "END_OF_DATA")
        equity_curve.append({"ts": _row_ts(last_row, last_index), "equity": cash})

    equity_values = [float(point["equity"]) for point in equity_curve] or [float(cfg.starting_capital)]
    final_equity = float(cash)
    wins = [trade for trade in trades if float(trade["pnl"]) > 0]
    losses = [trade for trade in trades if float(trade["pnl"]) <= 0]
    max_dd_abs, max_dd_pct = _max_drawdown(equity_values)
    exposed_bars = sum(int(trade["exit_index"]) - int(trade["entry_index"]) + 1 for trade in trades)
    total_bars = max(1, len(data) - start_index)

    first_close = float(data.iloc[start_index]["close"])
    last_close = float(data.iloc[-1]["close"])
    buy_hold_return_pct = (last_close / first_close - 1.0) if first_close else 0.0
    buy_hold_account_return_pct = buy_hold_return_pct * cfg.position_size_pct

    metrics = {
        "symbol": symbol,
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "starting_capital": cfg.starting_capital,
        "final_equity": final_equity,
        "total_return_abs": final_equity - cfg.starting_capital,
        "total_return_pct": (final_equity / cfg.starting_capital - 1.0) if cfg.starting_capital else 0.0,
        "avg_trade_return_pct": float(np.mean([trade["return_pct"] for trade in trades])) if trades else 0.0,
        "max_drawdown_abs": max_dd_abs,
        "max_drawdown_pct": max_dd_pct,
        "profit_factor": _profit_factor(trades),
        "sharpe": _sharpe_from_equity(equity_values),
        "buy_hold_return_pct": buy_hold_return_pct,
        "buy_hold_account_return_pct": buy_hold_account_return_pct,
        "buy_hold_edge_pct": (
            (final_equity / cfg.starting_capital - 1.0) - buy_hold_account_return_pct if cfg.starting_capital else 0.0
        ),
        "exposure_pct": exposed_bars / total_bars,
        "trades_detail": trades,
        "equity_curve": equity_curve,
    }
    metrics.update(evaluate_backtest_eligibility(metrics))
    return metrics
