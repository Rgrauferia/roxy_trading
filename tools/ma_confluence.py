from __future__ import annotations

import argparse
import glob
import importlib.util
import sys
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_CORE_SPEC = importlib.util.spec_from_file_location("roxy_ma_confluence_core", BASE_DIR / "ma_confluence.py")
if _CORE_SPEC is None or _CORE_SPEC.loader is None:
    raise ImportError("Cannot load root ma_confluence.py")
_CORE_MODULE = importlib.util.module_from_spec(_CORE_SPEC)
_CORE_SPEC.loader.exec_module(_CORE_MODULE)
build_confluence = _CORE_MODULE.build_confluence
write_confluence_report = _CORE_MODULE.write_confluence_report

from durable_storage import atomic_write_csv
from roxy_paths import alerts_dir, output_dir

OUTPUT_DIR = output_dir()
ALERTS_DIR = alerts_dir()


def latest_live_scan_path() -> Path | None:
    matches = sorted(
        (Path(path) for path in glob.glob(str(OUTPUT_DIR / "ma_live_strategy_both_*.csv"))),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        matches = sorted(
            (Path(path) for path in glob.glob(str(OUTPUT_DIR / "ma_live_strategy_*.csv"))),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    return matches[0] if matches else None


def print_table(df: pd.DataFrame, limit: int) -> None:
    if df.empty:
        print("No confluence results.")
        return
    display = df.head(limit)
    columns = [
        "market",
        "symbol",
        "signal",
        "action",
        "trade_decision",
        "confluence_score",
        "recommended_target_pct",
        "recommended_target_price",
        "entry",
        "stop",
        "risk_pct",
        "risk_level",
        "target_2pct_ok",
        "target_2pct_reward_r",
        "target_5pct_ok",
        "target_5pct_reward_r",
        "target_10pct_ok",
        "target_10pct_reward_r",
        "target_1r",
        "target_2r",
        "relative_volume_15m",
        "atr_pct_15m",
        "trigger_setup",
        "trigger_score",
        "trend_setup",
        "trend_score",
        "higher_tf_bias",
        "higher_tf_confirmations",
        "htf_2h_setup",
        "htf_2h_score",
        "htf_4h_setup",
        "htf_4h_score",
        "backtest_eligible",
        "reasons",
    ]
    columns = [column for column in columns if column in display.columns]
    print(display[columns].to_string(index=False, max_colwidth=80))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build specialized SMA 1h trend + 15m trigger confluence.")
    parser.add_argument("--scan-csv", help="Live SMA scan CSV. Defaults to latest output/ma_live_strategy_*.csv.")
    parser.add_argument("--trigger-tf", default="15m")
    parser.add_argument("--trend-tf", default="1h")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--report-path", default=str(ALERTS_DIR / "ma_confluence_report.txt"))
    parser.add_argument("--json-path", default=str(ALERTS_DIR / "ma_confluence_summary.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scan_path = Path(args.scan_csv) if args.scan_csv else latest_live_scan_path()
    if not scan_path or not scan_path.exists():
        raise SystemExit("No live scan CSV found. Run tools/ma_live.py first.")

    scan_df = pd.read_csv(scan_path)
    confluence = build_confluence(scan_df, trigger_tf=args.trigger_tf, trend_tf=args.trend_tf)
    print_table(confluence, args.limit)

    saved_path = None
    if args.save and not confluence.empty:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_path = output_dir / f"ma_confluence_{ts}.csv"
        atomic_write_csv(confluence, saved_path)
        print(f"\nSaved: {saved_path}")

    summary = write_confluence_report(
        confluence,
        scan_path=scan_path,
        report_path=args.report_path,
        json_path=args.json_path,
        limit=args.limit,
    )
    print(f"Wrote report: {args.report_path}")
    print(f"Wrote summary: {args.json_path}")
    print(f"Confluence BUY: {summary['buy_count']} | WATCH: {summary['watch_count']}")


if __name__ == "__main__":
    main()
