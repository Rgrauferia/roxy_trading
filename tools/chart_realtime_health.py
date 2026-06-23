from __future__ import annotations

import argparse
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from chart_health import (
    active_chart_symbols_from_alerts,
    chart_health_row,
    normalize_chart_symbol,
    summarize_chart_health,
    write_chart_health_report,
)
from roxy_paths import alerts_dir


DEFAULT_REPORT_PATH = alerts_dir() / "chart_realtime_health.json"
DEFAULT_STOCK_SYMBOLS = ("AAPL", "NVDA", "AMD", "MSFT", "QQQ")
DEFAULT_CRYPTO_SYMBOLS = ("BTC/USD",)
DEFAULT_TIMEFRAMES = ("15m", "1h")


def market_for_symbol(symbol: str) -> str:
    return "crypto" if "/" in str(symbol) else "stock"


def parse_csv_list(value: str | None, defaults: tuple[str, ...]) -> list[str]:
    if not value:
        return list(defaults)
    return [item.strip() for item in value.split(",") if item.strip()]


def merge_symbols(*groups: list[str]) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            symbol = normalize_chart_symbol(value)
            if symbol and symbol not in seen:
                seen.add(symbol)
                selected.append(symbol)
    return selected


def selected_chart_symbols(
    *,
    symbols_arg: str | None = None,
    include_active_alert_symbols: bool = True,
    active_symbol_limit: int = 8,
    alerts_path: str | Path | None = None,
) -> list[str]:
    base_symbols = parse_csv_list(symbols_arg, DEFAULT_STOCK_SYMBOLS + DEFAULT_CRYPTO_SYMBOLS)
    active_symbols: list[str] = []
    if include_active_alert_symbols:
        active_symbols = active_chart_symbols_from_alerts(
            Path(alerts_path) if alerts_path is not None else alerts_dir(),
            limit=max(1, int(active_symbol_limit)),
        )
    return merge_symbols(base_symbols, active_symbols)


def collect_chart_health(
    *,
    symbols: list[str],
    timeframes: list[str],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    from symbol_detail import fetch_symbol_history, prepare_symbol_chart_data

    current = now or datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        market = market_for_symbol(symbol)
        for timeframe in timeframes:
            try:
                history = fetch_symbol_history(symbol, market=market, timeframe=timeframe)
                chart_df = prepare_symbol_chart_data(history)
                row = chart_health_row(symbol=symbol, market=market, timeframe=timeframe, chart_df=chart_df, now=current)
            except Exception as exc:
                row = {
                    "symbol": symbol.upper(),
                    "market": market,
                    "timeframe": timeframe,
                    "status": "FAIL",
                    "label": "Error",
                    "tone": "avoid",
                    "detail": str(exc),
                    "age_minutes": None,
                    "latest": "-",
                    "rows": 0,
                    "has_rsi": False,
                    "has_macd": False,
                    "indicator_status": "FAIL",
                }
            rows.append(row)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check realtime freshness and indicators for key Roxy chart panels.")
    parser.add_argument("--symbols", help="Comma-separated symbols. Defaults to core stock + crypto symbols.")
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES))
    parser.add_argument(
        "--include-active-alert-symbols",
        dest="include_active_alert_symbols",
        action="store_true",
        default=True,
        help="Also check symbols from current Roxy alerts, status, and daily plan. Enabled by default.",
    )
    parser.add_argument(
        "--no-active-alert-symbols",
        dest="include_active_alert_symbols",
        action="store_false",
        help="Only check the configured/default symbol list.",
    )
    parser.add_argument("--active-symbol-limit", type=int, default=8)
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--no-fail", action="store_true", help="Always exit 0 after writing the report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_path_arg = Path(args.report_path).expanduser()
    symbols = selected_chart_symbols(
        symbols_arg=args.symbols,
        include_active_alert_symbols=args.include_active_alert_symbols,
        active_symbol_limit=args.active_symbol_limit,
        alerts_path=report_path_arg.parent,
    )
    timeframes = parse_csv_list(args.timeframes, DEFAULT_TIMEFRAMES)
    rows = collect_chart_health(symbols=symbols, timeframes=timeframes)
    report_path = write_chart_health_report(rows, args.report_path)
    summary = summarize_chart_health(rows)
    print(
        f"Chart realtime health: {summary['status']} | checked {summary['checked_count']} | "
        f"fail {summary['fail_count']} | warn {summary['warn_count']}"
    )
    print(f"Report: {report_path}")
    if summary["status"] == "FAIL" and not args.no_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
