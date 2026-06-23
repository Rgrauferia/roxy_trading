from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ma_reporting import write_scan_report


OUTPUT_DIR = BASE_DIR / "output"
ALERTS_DIR = BASE_DIR / "alerts"


def latest_scan_path() -> Path | None:
    matches = sorted(
        (Path(path) for path in glob.glob(str(OUTPUT_DIR / "ma_strategy_both_*.csv"))),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        matches = sorted(
            (Path(path) for path in glob.glob(str(OUTPUT_DIR / "ma_strategy_*.csv"))),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    return matches[0] if matches else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a readable report from a filtered SMA scan CSV.")
    parser.add_argument("--scan-csv", help="Scan CSV. Defaults to latest output/ma_strategy_*.csv.")
    parser.add_argument("--report-path", default=str(ALERTS_DIR / "ma_daily_report.txt"))
    parser.add_argument("--json-path", default=str(ALERTS_DIR / "ma_daily_summary.json"))
    parser.add_argument("--limit", type=int, default=12)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scan_path = Path(args.scan_csv) if args.scan_csv else latest_scan_path()
    if not scan_path or not scan_path.exists():
        raise SystemExit("No scan CSV found. Run tools/ma_scan.py first.")

    df = pd.read_csv(scan_path)
    summary = write_scan_report(
        df,
        scan_path=scan_path,
        report_path=args.report_path,
        json_path=args.json_path,
        limit=args.limit,
    )
    print(f"Wrote report: {args.report_path}")
    print(f"Wrote summary: {args.json_path}")
    print(
        f"BUY: {summary['buy_count']} | downgraded raw BUY: {summary['filtered_buy_count']} | "
        f"eligible non-BUY: {summary['eligible_watch_count']}"
    )


if __name__ == "__main__":
    main()
