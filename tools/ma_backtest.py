from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ma_backtester import (
    BacktestEligibilityConfig,
    MovingAverageBacktestConfig,
    evaluate_backtest_eligibility,
    run_ma_backtest,
)
from moving_average_strategy import MovingAverageConfig


DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"


def read_symbols(path: Path) -> list[str]:
    if not path.exists():
        return []
    symbols = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            symbols.append(value)
    return symbols


def parse_symbols(value: str | None, watchlist: str) -> list[str]:
    if value:
        return [symbol.strip() for symbol in value.split(",") if symbol.strip()]
    return read_symbols(Path(watchlist))


def fetch_stock(symbol: str, interval: str, period: str) -> pd.DataFrame:
    import roxy_scanner as scanner

    return scanner.fetch_stock_ohlcv(symbol, interval=interval, period=period)


def fetch_crypto(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    import roxy_scanner as scanner

    return scanner.fetch_crypto_ohlcv(symbol, timeframe=timeframe, limit=limit)


def pct(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value * 100:.2f}%"


def compact_reasons(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value or "")


def printable_summary(rows: list[dict[str, Any]], limit: int, only_eligible: bool = False) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values(["total_return_pct", "profit_factor"], ascending=[False, False])
    if only_eligible and "eligible" in df.columns:
        df = df[df["eligible"]]
    if df.empty:
        return pd.DataFrame()
    display = df.head(limit).copy()
    for column in (
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "buy_hold_return_pct",
        "buy_hold_account_return_pct",
        "buy_hold_edge_pct",
        "exposure_pct",
    ):
        if column not in display.columns:
            continue
        display[column] = display[column].apply(pct)
    if "eligibility_reasons" in display.columns:
        display["eligibility_reasons"] = display["eligibility_reasons"].apply(compact_reasons)
    numeric = ["final_equity", "total_return_abs", "avg_trade_return_pct", "profit_factor", "sharpe"]
    for column in numeric:
        if column in display.columns:
            display[column] = display[column].apply(lambda value: round(float(value), 4) if pd.notna(value) else value)
    columns = [
        "market",
        "symbol",
        "tf",
        "eligible",
        "trades",
        "win_rate",
        "total_return_pct",
        "buy_hold_account_return_pct",
        "buy_hold_edge_pct",
        "buy_hold_return_pct",
        "max_drawdown_pct",
        "profit_factor",
        "sharpe",
        "final_equity",
        "exposure_pct",
        "eligibility_reasons",
    ]
    return display[[column for column in columns if column in display.columns]]


def flatten_summary(metrics: dict[str, Any], market: str, timeframe: str) -> dict[str, Any]:
    return {
        "market": market,
        "symbol": metrics["symbol"],
        "tf": timeframe,
        "trades": metrics["trades"],
        "wins": metrics["wins"],
        "losses": metrics["losses"],
        "win_rate": metrics["win_rate"],
        "starting_capital": metrics["starting_capital"],
        "final_equity": metrics["final_equity"],
        "total_return_abs": metrics["total_return_abs"],
        "total_return_pct": metrics["total_return_pct"],
        "avg_trade_return_pct": metrics["avg_trade_return_pct"],
        "max_drawdown_abs": metrics["max_drawdown_abs"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "profit_factor": metrics["profit_factor"],
        "sharpe": metrics["sharpe"],
        "buy_hold_return_pct": metrics["buy_hold_return_pct"],
        "buy_hold_account_return_pct": metrics.get("buy_hold_account_return_pct", 0.0),
        "buy_hold_edge_pct": metrics.get("buy_hold_edge_pct", 0.0),
        "exposure_pct": metrics["exposure_pct"],
        "eligible": metrics.get("eligible", False),
        "eligibility_reasons": metrics.get("eligibility_reasons", []),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest the SMA 20/40/100/200 strategy.")
    parser.add_argument("--market", choices=["stocks", "crypto", "both"], default="stocks")
    parser.add_argument("--symbols", help="Comma-separated symbols. Overrides watchlist files.")
    parser.add_argument("--stock-watchlist", default=str(DATA_DIR / "watchlist_stocks.txt"))
    parser.add_argument("--crypto-watchlist", default=str(DATA_DIR / "watchlist_crypto.txt"))
    parser.add_argument("--stock-interval", default="1d")
    parser.add_argument("--stock-period", default="5y")
    parser.add_argument("--crypto-timeframe", default="1d")
    parser.add_argument("--crypto-limit", type=int, default=1000)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--starting-capital", type=float, default=10000.0)
    parser.add_argument("--position-size-pct", type=float, default=0.25)
    parser.add_argument("--fee-pct", type=float, default=0.0005)
    parser.add_argument("--slippage-pct", type=float, default=0.0005)
    parser.add_argument("--cooldown-bars", type=int, default=5)
    parser.add_argument("--buy-score", type=int, default=70)
    parser.add_argument("--watch-score", type=int, default=45)
    parser.add_argument("--max-extension-pct", type=float, default=12.0)
    parser.add_argument("--pullback-band-pct", type=float, default=3.0)
    parser.add_argument("--min-profit-factor", type=float, default=1.2)
    parser.add_argument("--min-return-pct", type=float, default=0.0, help="Minimum total return, expressed as percent.")
    parser.add_argument("--max-drawdown-pct", type=float, default=15.0, help="Maximum drawdown, expressed as percent.")
    parser.add_argument("--min-trades", type=int, default=8)
    parser.add_argument(
        "--min-buy-hold-edge-pct",
        type=float,
        default=None,
        help="Minimum strategy return minus buy-and-hold return, expressed as percent.",
    )
    parser.add_argument("--only-eligible", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ma_config = MovingAverageConfig(
        buy_score=args.buy_score,
        watch_score=args.watch_score,
        max_extension_pct=args.max_extension_pct,
        pullback_band_pct=args.pullback_band_pct,
    )
    backtest_config = MovingAverageBacktestConfig(
        starting_capital=args.starting_capital,
        position_size_pct=args.position_size_pct,
        fee_pct=args.fee_pct,
        slippage_pct=args.slippage_pct,
        cooldown_bars=args.cooldown_bars,
    )
    eligibility_config = BacktestEligibilityConfig(
        min_profit_factor=args.min_profit_factor,
        min_return_pct=args.min_return_pct / 100.0,
        max_drawdown_pct=args.max_drawdown_pct / 100.0,
        min_trades=args.min_trades,
        min_buy_hold_edge_pct=None if args.min_buy_hold_edge_pct is None else args.min_buy_hold_edge_pct / 100.0,
    )

    summary_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

    jobs: list[tuple[str, str, str, Any]] = []
    if args.market in {"stocks", "both"}:
        for symbol in parse_symbols(args.symbols, args.stock_watchlist):
            jobs.append(
                (
                    "stock",
                    symbol,
                    args.stock_interval,
                    lambda s, args=args: fetch_stock(s, args.stock_interval, args.stock_period),
                )
            )
    if args.market in {"crypto", "both"}:
        for symbol in parse_symbols(args.symbols, args.crypto_watchlist):
            jobs.append(
                (
                    "crypto",
                    symbol,
                    args.crypto_timeframe,
                    lambda s, args=args: fetch_crypto(s, args.crypto_timeframe, args.crypto_limit),
                )
            )

    for market, symbol, timeframe, fetcher in jobs:
        try:
            df = fetcher(symbol)
            metrics = run_ma_backtest(df, symbol=symbol, ma_config=ma_config, backtest_config=backtest_config)
            metrics.update(evaluate_backtest_eligibility(metrics, eligibility_config))
            summary_rows.append(flatten_summary(metrics, market, timeframe))
            for trade in metrics["trades_detail"]:
                trade_rows.append({"market": market, "tf": timeframe, **trade})
        except Exception as exc:
            summary_rows.append(
                {
                    "market": market,
                    "symbol": symbol,
                    "tf": timeframe,
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.0,
                    "starting_capital": args.starting_capital,
                    "final_equity": args.starting_capital,
                    "total_return_abs": 0.0,
                    "total_return_pct": 0.0,
                    "avg_trade_return_pct": 0.0,
                    "max_drawdown_abs": 0.0,
                    "max_drawdown_pct": 0.0,
                    "profit_factor": 0.0,
                    "sharpe": 0.0,
                    "buy_hold_return_pct": 0.0,
                    "buy_hold_account_return_pct": 0.0,
                    "buy_hold_edge_pct": 0.0,
                    "exposure_pct": 0.0,
                    "eligible": False,
                    "eligibility_reasons": [str(exc)],
                    "error": str(exc),
                }
            )

    display = printable_summary(summary_rows, args.limit, only_eligible=args.only_eligible)
    if display.empty:
        print("No backtest results.")
    else:
        print(display.to_string(index=False))

    if args.save and summary_rows:
        OUTPUT_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = OUTPUT_DIR / f"ma_backtest_summary_{args.market}_{ts}.csv"
        trades_path = OUTPUT_DIR / f"ma_backtest_trades_{args.market}_{ts}.csv"
        summary_df = pd.DataFrame(summary_rows)
        if "eligibility_reasons" in summary_df.columns:
            summary_df["eligibility_reasons"] = summary_df["eligibility_reasons"].apply(compact_reasons)
        summary_df.to_csv(summary_path, index=False)
        pd.DataFrame(trade_rows).to_csv(trades_path, index=False)
        print(f"\nSaved summary: {summary_path}")
        print(f"Saved trades : {trades_path}")


if __name__ == "__main__":
    main()
