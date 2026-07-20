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
from durable_storage import atomic_write_csv, atomic_write_text
from roxy_paths import alerts_dir, data_dir, output_dir


OUTPUT_DIR = output_dir()
DATA_DIR = data_dir()
ALERTS_DIR = alerts_dir()
BINANCEUS_COVERAGE_PATH = ALERTS_DIR / "binanceus_symbol_coverage.json"
INTRADAY_STOCK_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "2h", "4h"}
DERIVED_STOCK_INTERVALS = {"2h": "2h", "4h": "4h"}
DERIVED_CRYPTO_INTERVALS = {"2h": ("1h", "2h", 2), "4h": ("1h", "4h", 4)}
MAX_BINANCEUS_OHLCV_LIMIT = 1_000


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


def build_crypto_history_cache(
    symbols: list[str],
    timeframes: list[str],
    limit: int,
    *,
    exchange: Any,
    symbol_map: dict[str, str] | None = None,
    fetcher=None,
) -> tuple[dict[tuple[str, str], pd.DataFrame], dict[str, Any]]:
    """Fetch one expanded 1h series and derive requested 2h/4h frames locally."""
    requested = [str(value).strip().lower() for value in timeframes]
    derived = [value for value in requested if value in DERIVED_CRYPTO_INTERVALS]
    if not derived:
        return {}, {"enabled": False, "base_request_count": 0, "saved_request_count": 0}
    import roxy_scanner as scanner

    load = fetcher or scanner.fetch_crypto_ohlcv
    effective_map = dict(symbol_map or {})
    largest_factor = max(DERIVED_CRYPTO_INTERVALS[value][2] for value in derived)
    base_limit = min(MAX_BINANCEUS_OHLCV_LIMIT, max(int(limit), int(limit) * largest_factor))
    cache: dict[tuple[str, str], pd.DataFrame] = {}
    for symbol in symbols:
        try:
            base = load(
                symbol,
                timeframe="1h",
                limit=base_limit,
                exchange=exchange,
                provider_symbol=effective_map.get(symbol, symbol),
            )
        except Exception:
            base = pd.DataFrame()
        cache[(symbol, "1h")] = base
        for timeframe in derived:
            _base_timeframe, rule, _factor = DERIVED_CRYPTO_INTERVALS[timeframe]
            cache[(symbol, timeframe)] = resample_ohlcv(base, rule)
    direct_request_count = len(symbols) * len(derived)
    if "1h" in requested:
        direct_request_count += len(symbols)
    return cache, {
        "enabled": True,
        "base_timeframe": "1h",
        "base_limit": base_limit,
        "derived_timeframes": derived,
        "base_request_count": len(symbols),
        "direct_request_count": direct_request_count,
        "saved_request_count": max(0, direct_request_count - len(symbols)),
    }


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


def write_json_atomic(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(payload, indent=2, sort_keys=True), target)
    return target


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
    crypto_symbol_coverage: dict[str, Any] | None = None,
    crypto_fetch_optimization: dict[str, Any] | None = None,
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
        "crypto_symbol_coverage": dict(crypto_symbol_coverage or {}),
        "crypto_fetch_optimization": dict(crypto_fetch_optimization or {}),
    }
    write_json_atomic(timing_path, payload)


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


def run_crypto_scan(
    symbols: list[str],
    timeframe: str,
    limit: int,
    config: MovingAverageConfig,
    *,
    exchange=None,
    symbol_map: dict[str, str] | None = None,
    history_by_symbol: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    import roxy_scanner as scanner

    effective_map = dict(symbol_map or {})
    cached_history = history_by_symbol if isinstance(history_by_symbol, dict) else None
    out = scan_moving_average_strategy(
        symbols,
        (
            lambda symbol: cached_history.get(symbol, pd.DataFrame()).copy()
            if cached_history is not None
            else scanner.fetch_crypto_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit,
                exchange=exchange,
                provider_symbol=effective_map.get(symbol, symbol),
            )
        ),
        market="crypto",
        timeframe=timeframe,
        config=config,
    )
    if not out.empty:
        out["provider_symbol"] = out["symbol"].map(lambda symbol: effective_map.get(str(symbol), str(symbol)))
        out["symbol_resolution"] = out.apply(
            lambda row: "EXACT" if str(row.get("symbol")) == str(row.get("provider_symbol")) else "QUOTE_FALLBACK",
            axis=1,
        )
        out["data_source"] = "ccxt:binanceus"
    return out


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
    parser.add_argument("--crypto-coverage-json", default=str(BINANCEUS_COVERAGE_PATH))
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
    crypto_symbol_coverage: dict[str, Any] = {}
    crypto_fetch_optimization: dict[str, Any] = {}
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
        import roxy_scanner as scanner

        crypto_exchange = scanner.create_binanceus_exchange()
        crypto_symbol_coverage = scanner.binanceus_symbol_coverage(crypto, exchange=crypto_exchange)
        write_json_atomic(args.crypto_coverage_json, crypto_symbol_coverage)
        if crypto_symbol_coverage.get("status") == "CONNECTED":
            crypto_scan_symbols = list(crypto_symbol_coverage.get("supported_symbols") or [])
        else:
            crypto_scan_symbols = list(crypto)
        crypto_symbol_map = dict(crypto_symbol_coverage.get("symbol_map") or {})
        crypto_timeframes = parse_csv_list(args.crypto_timeframes, default=[args.crypto_timeframe])
        crypto_history_cache, crypto_cache_meta = build_crypto_history_cache(
            crypto_scan_symbols,
            crypto_timeframes,
            args.crypto_limit,
            exchange=crypto_exchange,
            symbol_map=crypto_symbol_map,
        )
        crypto_fetch_optimization = crypto_cache_meta
        for timeframe in crypto_timeframes:
            step_started = time.monotonic()
            history_by_symbol = (
                {
                    symbol: crypto_history_cache.get((symbol, timeframe), pd.DataFrame())
                    for symbol in crypto_scan_symbols
                }
                if crypto_cache_meta.get("enabled")
                and (timeframe == "1h" or timeframe in DERIVED_CRYPTO_INTERVALS)
                else None
            )
            frame = run_crypto_scan(
                crypto_scan_symbols,
                timeframe,
                args.crypto_limit,
                config,
                exchange=crypto_exchange,
                symbol_map=crypto_symbol_map,
                history_by_symbol=history_by_symbol,
            )
            frames.append(frame)
            timing_steps.append(
                {
                    "market": "crypto",
                    "timeframe": timeframe,
                    "symbol_count": len(crypto_scan_symbols),
                    "requested_symbol_count": len(crypto),
                    "unsupported_symbol_count": int(crypto_symbol_coverage.get("unsupported_count") or 0),
                    "rows": 0 if frame is None else int(len(frame)),
                    "duration_seconds": round(time.monotonic() - step_started, 2),
                    "limit": args.crypto_limit,
                    "fetch_mode": (
                        "DERIVED_FROM_1H"
                        if timeframe in DERIVED_CRYPTO_INTERVALS and history_by_symbol is not None
                        else "SHARED_1H"
                        if timeframe == "1h" and history_by_symbol is not None
                        else "DIRECT"
                    ),
                    "api_requests_saved": (
                        len(crypto_scan_symbols) if timeframe in DERIVED_CRYPTO_INTERVALS else 0
                    ),
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
                crypto_symbol_coverage=crypto_symbol_coverage,
                crypto_fetch_optimization=crypto_fetch_optimization,
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
        atomic_write_csv(to_save, path)
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
            crypto_symbol_coverage=crypto_symbol_coverage,
            crypto_fetch_optimization=crypto_fetch_optimization,
        )


if __name__ == "__main__":
    main()
