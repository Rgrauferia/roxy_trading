from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
TOOLS_DIR = BASE_DIR / "tools"
OUTPUT_DIR = BASE_DIR / "output"
DAILY_OUTPUT_PATTERNS = (
    "ma_strategy_*.csv",
    "ma_backtest_summary_*.csv",
    "ma_backtest_trades_*.csv",
)


def extract_saved_scan_path(output: str) -> str | None:
    for line in output.splitlines():
        if line.startswith("Saved:"):
            return line.split("Saved:", 1)[1].strip()
    return None


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args))
    result = subprocess.run(args, cwd=BASE_DIR, text=True, capture_output=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def cleanup_daily_outputs(retention_count: int) -> list[str]:
    if retention_count <= 0:
        return []
    from tools.output_maintenance import cleanup_output_files

    result = cleanup_output_files(
        output_dir=OUTPUT_DIR,
        retention_rules={pattern: retention_count for pattern in DAILY_OUTPUT_PATTERNS},
    )
    removed = [str(path) for path in result["removed"]]
    if removed:
        print(f"Cleaned {len(removed)} old daily output file(s).")
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily SMA 20/40/100/200 workflow.")
    parser.add_argument("--market", choices=["stocks", "crypto", "both"], default="both")
    parser.add_argument("--symbols", help="Comma-separated symbols for quick targeted runs.")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--report-limit", type=int, default=12)
    parser.add_argument("--refresh-backtests", action="store_true")
    parser.add_argument("--stock-period", default="5y")
    parser.add_argument("--crypto-limit", type=int, default=1000)
    parser.add_argument("--min-buy-hold-edge-pct", type=float, default=0.0)
    parser.add_argument("--retention-count", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    python = sys.executable

    if args.refresh_backtests:
        if args.market in {"stocks", "both"}:
            cmd = [
                python,
                str(TOOLS_DIR / "ma_backtest.py"),
                "--market",
                "stocks",
                "--stock-period",
                args.stock_period,
                "--min-buy-hold-edge-pct",
                str(args.min_buy_hold_edge_pct),
                "--only-eligible",
                "--save",
            ]
            if args.symbols:
                cmd.extend(["--symbols", args.symbols])
            run_command(cmd)

        if args.market in {"crypto", "both"}:
            cmd = [
                python,
                str(TOOLS_DIR / "ma_backtest.py"),
                "--market",
                "crypto",
                "--crypto-limit",
                str(args.crypto_limit),
                "--min-buy-hold-edge-pct",
                str(args.min_buy_hold_edge_pct),
                "--only-eligible",
                "--save",
            ]
            if args.symbols:
                cmd.extend(["--symbols", args.symbols])
            run_command(cmd)

    scan_cmd = [
        python,
        str(TOOLS_DIR / "ma_scan.py"),
        "--market",
        args.market,
        "--require-backtest-eligible",
        "--limit",
        str(args.limit),
        "--save",
    ]
    if args.symbols:
        scan_cmd.extend(["--symbols", args.symbols])
    scan_result = run_command(scan_cmd)
    scan_path = extract_saved_scan_path(scan_result.stdout)

    report_cmd = [python, str(TOOLS_DIR / "ma_report.py"), "--limit", str(args.report_limit)]
    if scan_path:
        report_cmd.extend(["--scan-csv", scan_path])
    run_command(report_cmd)
    cleanup_daily_outputs(args.retention_count)


if __name__ == "__main__":
    main()
