from __future__ import annotations

import argparse
import glob
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from moving_average_strategy import MovingAverageConfig, scan_moving_average_strategy
from roxy_paths import data_dir, output_dir


OUTPUT_DIR = output_dir()
DATA_DIR = data_dir()
INTRADAY_STOCK_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "2h", "4h"}
DERIVED_STOCK_INTERVALS = {"2h": "2h", "4h": "4h"}


def read_symbols(path: Path) -> list[str]:
    if not path.exists():
        return []
    symbols = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            symbols.append(value)
    return symbols


def compact_reasons(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value[:5])
    return str(value or "")


def parse_csv_list(value: str | None, default: list[str] | None = None) -> list[str]:
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def is_intraday_stock_interval(interval: str) -> bool:
    return interval.lower() in INTRADAY_STOCK_INTERVALS


def stock_fetch_interval(interval: str) -> str:
    normalized = interval.lower()
    if normalized == "1h":
        return "60m"
    if normalized == "1w":
        return "1wk"
    return normalized


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
    return (
        data.set_index("ts")
        .resample(rule, label="right", closed="right")
        .agg({column: aggregations[column] for column in keep})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )


def stock_period_for_interval(interval: str, stock_period: str | None, intraday_stock_period: str) -> str:
    if stock_period:
        return stock_period
    if interval.lower() in DERIVED_STOCK_INTERVALS:
        return "730d"
    if is_intraday_stock_interval(interval):
        return intraday_stock_period
    return "2y"


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def write_timing_json(
    path: str | Path | None,
    *,
    market: str,
    stock_intervals: list[str],
    crypto_timeframes: list[str],
    started_monotonic: float,
    steps: list[dict[str, Any]],
    total_rows: int = 0,
    saved_path: str | None = None,
    status: str = "RUNNING",
) -> None:
    if not path:
        return
    timing_path = Path(path)
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": status,
        "market": market,
        "stock_intervals": stock_intervals,
        "crypto_timeframes": crypto_timeframes,
        "total_duration_seconds": round(time.monotonic() - started_monotonic, 2),
        "total_rows": int(total_rows),
        "saved_path": saved_path,
        "steps": steps,
    }
    timing_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def latest_backtest_summary_paths(market: str) -> list[Path]:
    markets = []
    if market in {"stocks", "both"}:
        markets.append("stocks")
    if market in {"crypto", "both"}:
        markets.append("crypto")

    paths = []
    for item in markets:
        matches = sorted(
            (Path(path) for path in glob.glob(str(OUTPUT_DIR / f"ma_backtest_summary_{item}_*.csv"))),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if matches:
            paths.append(matches[0])
    return paths


def load_backtest_eligibility(paths: list[str | Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        frame = pd.read_csv(p)
        if frame.empty:
            continue
        frame["symbol"] = frame["symbol"].astype(str)
        frame["market"] = frame["market"].astype(str)
        frame["eligible"] = frame["eligible"].apply(parse_bool) if "eligible" in frame.columns else False
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["market", "symbol"], keep="last")
    keep = [
        "market",
        "symbol",
        "eligible",
        "trades",
        "total_return_pct",
        "buy_hold_account_return_pct",
        "buy_hold_edge_pct",
        "max_drawdown_pct",
        "profit_factor",
        "sharpe",
        "eligibility_reasons",
    ]
    return combined[[column for column in keep if column in combined.columns]]


def _append_reason(value: Any, reason: str) -> list[str]:
    if isinstance(value, list):
        reasons = [str(item) for item in value]
    elif value is None or (not isinstance(value, str) and pd.isna(value)):
        reasons = []
    elif str(value):
        reasons = [str(value)]
    else:
        reasons = []
    reasons.append(reason)
    return reasons


def apply_backtest_filter(
    df: pd.DataFrame,
    eligibility: pd.DataFrame,
    *,
    require_eligible: bool,
) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out["raw_signal"] = out["signal"]

    if eligibility.empty:
        out["backtest_eligible"] = False
        out["backtest_eligibility_reasons"] = "missing_backtest"
    else:
        renamed = eligibility.rename(
            columns={
                "eligible": "backtest_eligible",
                "trades": "backtest_trades",
                "total_return_pct": "backtest_total_return_pct",
                "buy_hold_account_return_pct": "backtest_buy_hold_account_return_pct",
                "buy_hold_edge_pct": "backtest_buy_hold_edge_pct",
                "max_drawdown_pct": "backtest_max_drawdown_pct",
                "profit_factor": "backtest_profit_factor",
                "sharpe": "backtest_sharpe",
                "eligibility_reasons": "backtest_eligibility_reasons",
            }
        )
        out = out.merge(renamed, on=["market", "symbol"], how="left")
        out["backtest_eligible"] = out["backtest_eligible"].apply(parse_bool)
        out["backtest_eligibility_reasons"] = out["backtest_eligibility_reasons"].fillna("missing_backtest")

    if require_eligible:
        mask = out["raw_signal"].eq("BUY") & ~out["backtest_eligible"]
        out.loc[mask, "signal"] = "WATCH"
        out.loc[mask, "reasons"] = out.loc[mask].apply(
            lambda row: _append_reason(
                row.get("reasons"),
                f"Backtest filter: {row.get('backtest_eligibility_reasons') or 'not eligible'}",
            ),
            axis=1,
        )

    return out


def sort_scan_results(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    signal_rank = {"BUY": 0, "WATCH": 1, "AVOID": 2, "NO_DATA": 3, "ERROR": 4, "INSUFFICIENT_DATA": 5}
    out["_signal_rank"] = out["signal"].map(signal_rank).fillna(9)
    if "backtest_eligible" not in out.columns:
        out["backtest_eligible"] = False
    out = out.sort_values(
        ["_signal_rank", "backtest_eligible", "score", "symbol"],
        ascending=[True, False, False, True],
    )
    return out.drop(columns=["_signal_rank"]).reset_index(drop=True)


def run_stock_scan(
    symbols: list[str],
    interval: str,
    period: str,
    config: MovingAverageConfig,
    *,
    include_extended_hours: bool = False,
) -> pd.DataFrame:
    import roxy_scanner as scanner

    normalized_interval = interval.lower()

    def fetch(symbol: str) -> pd.DataFrame:
        if normalized_interval in DERIVED_STOCK_INTERVALS:
            base = scanner.fetch_stock_ohlcv(
                symbol,
                interval=stock_fetch_interval("1h"),
                period=period,
                prepost=include_extended_hours,
            )
            return resample_ohlcv(base, DERIVED_STOCK_INTERVALS[normalized_interval])
        return scanner.fetch_stock_ohlcv(
            symbol,
            interval=stock_fetch_interval(interval),
            period=period,
            prepost=include_extended_hours and is_intraday_stock_interval(interval),
        )

    return scan_moving_average_strategy(
        symbols,
        fetch,
        market="stock",
        timeframe=interval,
        config=config,
    )


def run_crypto_scan(symbols: list[str], timeframe: str, limit: int, config: MovingAverageConfig) -> pd.DataFrame:
    import roxy_scanner as scanner

    return scan_moving_average_strategy(
        symbols,
        lambda symbol: scanner.fetch_crypto_ohlcv(symbol, timeframe=timeframe, limit=limit),
        market="crypto",
        timeframe=timeframe,
        config=config,
    )


def print_table(df: pd.DataFrame, limit: int) -> None:
    if df.empty:
        print("No results.")
        return

    display = df.head(limit).copy()
    display["reasons"] = display["reasons"].apply(compact_reasons)
    columns = [
        "market",
        "symbol",
        "tf",
        "signal",
        "raw_signal",
        "backtest_eligible",
        "setup",
        "score",
        "backtest_total_return_pct",
        "backtest_buy_hold_edge_pct",
        "backtest_profit_factor",
        "backtest_trades",
        "close",
        "sma20",
        "sma40",
        "sma100",
        "sma200",
        "dist_sma20_pct",
        "dist_sma200_pct",
        "relative_volume",
        "atr_pct",
        "stop",
        "reasons",
    ]
    columns = [column for column in columns if column in display.columns]
    print(display[columns].to_string(index=False, max_colwidth=70))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan symbols with the SMA 20/40/100/200 strategy.")
    parser.add_argument("--market", choices=["stocks", "crypto", "both"], default="both")
    parser.add_argument("--symbols", help="Comma-separated symbols. Overrides watchlist files.")
    parser.add_argument("--stock-watchlist", default=str(DATA_DIR / "watchlist_stocks.txt"))
    parser.add_argument("--crypto-watchlist", default=str(DATA_DIR / "watchlist_crypto.txt"))
    parser.add_argument("--stock-interval", default="1d")
    parser.add_argument("--stock-intervals", help="Comma-separated stock intervals, e.g. 15m,1h.")
    parser.add_argument("--stock-period", help="Stock history period. Defaults to 2y for daily and 60d intraday.")
    parser.add_argument("--intraday-stock-period", default="60d")
    parser.add_argument(
        "--include-extended-hours",
        action="store_true",
        help="Include premarket/postmarket candles for intraday stock intervals when available.",
    )
    parser.add_argument("--crypto-timeframe", default="1d")
    parser.add_argument("--crypto-timeframes", help="Comma-separated crypto timeframes, e.g. 15m,1h.")
    parser.add_argument("--crypto-limit", type=int, default=500)
    parser.add_argument("--limit", type=int, default=25, help="Rows to print.")
    parser.add_argument("--save", action="store_true", help="Save a CSV under output/.")
    parser.add_argument("--output-prefix", default="ma_strategy")
    parser.add_argument("--timing-json", help="Optional path to write per-market/interval scan timing telemetry.")
    parser.add_argument("--buy-score", type=int, default=70)
    parser.add_argument("--watch-score", type=int, default=45)
    parser.add_argument("--max-extension-pct", type=float, default=12.0)
    parser.add_argument("--pullback-band-pct", type=float, default=3.0)
    parser.add_argument(
        "--backtest-summary",
        action="append",
        help="Backtest summary CSV. Can be repeated. Defaults to latest summary per market when filtering is enabled.",
    )
    parser.add_argument(
        "--require-backtest-eligible",
        action="store_true",
        help="Only keep BUY as BUY when the symbol passed historical backtest filters.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started_monotonic = time.monotonic()
    config = MovingAverageConfig(
        buy_score=args.buy_score,
        watch_score=args.watch_score,
        max_extension_pct=args.max_extension_pct,
        pullback_band_pct=args.pullback_band_pct,
    )

    frames = []
    timing_steps: list[dict[str, Any]] = []
    stock_intervals: list[str] = []
    crypto_timeframes: list[str] = []
    if args.market in {"stocks", "both"}:
        stocks = (
            parse_csv_list(args.symbols)
            if args.symbols
            else read_symbols(Path(args.stock_watchlist))
        )
        stock_intervals = parse_csv_list(args.stock_intervals, default=[args.stock_interval])
        for interval in stock_intervals:
            period = stock_period_for_interval(interval, args.stock_period, args.intraday_stock_period)
            step_started = time.monotonic()
            frame = run_stock_scan(
                stocks,
                interval,
                period,
                config,
                include_extended_hours=args.include_extended_hours,
            )
            frames.append(frame)
            timing_steps.append(
                {
                    "market": "stock",
                    "timeframe": interval,
                    "symbol_count": len(stocks),
                    "rows": 0 if frame is None else int(len(frame)),
                    "duration_seconds": round(time.monotonic() - step_started, 2),
                    "period": period,
                }
            )
            write_timing_json(
                args.timing_json,
                market=args.market,
                stock_intervals=stock_intervals,
                crypto_timeframes=crypto_timeframes,
                started_monotonic=started_monotonic,
                steps=timing_steps,
                status="RUNNING",
            )

    if args.market in {"crypto", "both"}:
        crypto = (
            parse_csv_list(args.symbols)
            if args.symbols
            else read_symbols(Path(args.crypto_watchlist))
        )
        crypto_timeframes = parse_csv_list(args.crypto_timeframes, default=[args.crypto_timeframe])
        for timeframe in crypto_timeframes:
            step_started = time.monotonic()
            frame = run_crypto_scan(crypto, timeframe, args.crypto_limit, config)
            frames.append(frame)
            timing_steps.append(
                {
                    "market": "crypto",
                    "timeframe": timeframe,
                    "symbol_count": len(crypto),
                    "rows": 0 if frame is None else int(len(frame)),
                    "duration_seconds": round(time.monotonic() - step_started, 2),
                    "limit": args.crypto_limit,
                }
            )
            write_timing_json(
                args.timing_json,
                market=args.market,
                stock_intervals=stock_intervals,
                crypto_timeframes=crypto_timeframes,
                started_monotonic=started_monotonic,
                steps=timing_steps,
                status="RUNNING",
            )

    frames = [frame for frame in frames if frame is not None and not frame.empty]
    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not result.empty:
        summary_paths = [Path(path) for path in args.backtest_summary or []]
        if args.require_backtest_eligible and not summary_paths:
            summary_paths = latest_backtest_summary_paths(args.market)
        eligibility = load_backtest_eligibility(summary_paths)
        if args.require_backtest_eligible or not eligibility.empty:
            result = apply_backtest_filter(result, eligibility, require_eligible=args.require_backtest_eligible)
        result = sort_scan_results(result)

    print_table(result, args.limit)

    saved_path = None
    if args.save and not result.empty:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUTPUT_DIR / f"{args.output_prefix}_{args.market}_{ts}.csv"
        to_save = result.copy()
        to_save["reasons"] = to_save["reasons"].apply(compact_reasons)
        to_save.to_csv(path, index=False)
        saved_path = str(path)
        print(f"\nSaved: {path}")
    if args.timing_json:
        write_timing_json(
            args.timing_json,
            market=args.market,
            stock_intervals=stock_intervals,
            crypto_timeframes=crypto_timeframes,
            started_monotonic=started_monotonic,
            steps=timing_steps,
            total_rows=int(len(result)),
            saved_path=saved_path,
            status="SUCCESS",
        )


if __name__ == "__main__":
    main()
