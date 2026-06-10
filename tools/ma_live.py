from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
TOOLS_DIR = BASE_DIR / "tools"
from roxy_paths import alerts_dir, output_dir

ALERTS_DIR = alerts_dir()
OUTPUT_DIR = output_dir()
HEARTBEAT_PATH = ALERTS_DIR / "ma_live_heartbeat.json"
LIVE_OUTPUT_PATTERNS = (
    "ma_live_strategy_*.csv",
    "ma_confluence_*.csv",
    "options_candidates_*.csv",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_heartbeat(payload: dict[str, Any], path: str | Path | None = None) -> Path:
    heartbeat_path = Path(path) if path is not None else HEARTBEAT_PATH
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = heartbeat_path.with_suffix(heartbeat_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp_path.replace(heartbeat_path)
    return heartbeat_path


def heartbeat_base(args: argparse.Namespace, *, status: str, started_at: str) -> dict[str, Any]:
    return {
        "status": status,
        "started_at": started_at,
        "finished_at": None,
        "duration_seconds": None,
        "market": args.market,
        "symbols": args.symbols,
        "stock_intervals": args.stock_intervals,
        "crypto_timeframes": args.crypto_timeframes,
        "trigger_tf": args.trigger_tf,
        "trend_tf": args.trend_tf,
        "scan_path": None,
        "confluence_path": None,
        "options_path": None,
        "ai_watch_ran": False,
        "removed_old_files": 0,
        "error": None,
    }


def extract_saved_scan_path(output: str) -> str | None:
    for line in output.splitlines():
        if line.startswith("Saved:"):
            return line.split("Saved:", 1)[1].strip()
    return None


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args), flush=True)
    result = subprocess.run(args, cwd=BASE_DIR, text=True, capture_output=True, check=False)
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
    return result


def build_scan_command(args: argparse.Namespace, python: str) -> list[str]:
    cmd = [
        python,
        str(TOOLS_DIR / "ma_scan.py"),
        "--market",
        args.market,
        "--stock-intervals",
        args.stock_intervals,
        "--stock-period",
        args.stock_period,
        "--intraday-stock-period",
        args.intraday_stock_period,
        "--crypto-timeframes",
        args.crypto_timeframes,
        "--crypto-limit",
        str(args.crypto_limit),
        "--require-backtest-eligible",
        "--include-extended-hours",
        "--limit",
        str(args.limit),
        "--output-prefix",
        "ma_live_strategy",
        "--save",
    ]
    if args.symbols:
        cmd.extend(["--symbols", args.symbols])
    return cmd


def build_report_command(args: argparse.Namespace, python: str, scan_path: str) -> list[str]:
    return [
        python,
        str(TOOLS_DIR / "ma_report.py"),
        "--scan-csv",
        scan_path,
        "--report-path",
        str(ALERTS_DIR / "ma_live_report.txt"),
        "--json-path",
        str(ALERTS_DIR / "ma_live_summary.json"),
        "--limit",
        str(args.report_limit),
    ]


def build_confluence_command(args: argparse.Namespace, python: str, scan_path: str) -> list[str]:
    return [
        python,
        str(TOOLS_DIR / "ma_confluence.py"),
        "--scan-csv",
        scan_path,
        "--trigger-tf",
        args.trigger_tf,
        "--trend-tf",
        args.trend_tf,
        "--report-path",
        str(ALERTS_DIR / "ma_confluence_report.txt"),
        "--json-path",
        str(ALERTS_DIR / "ma_confluence_summary.json"),
        "--limit",
        str(args.report_limit),
        "--output-dir",
        str(OUTPUT_DIR),
        "--save",
    ]


def build_options_command(args: argparse.Namespace, python: str, confluence_path: str | None = None) -> list[str]:
    cmd = [
        python,
        str(TOOLS_DIR / "options_scan.py"),
        "--limit",
        str(args.report_limit),
        "--output-dir",
        str(OUTPUT_DIR),
        "--save",
    ]
    if confluence_path:
        cmd.extend(["--confluence-csv", confluence_path])
    return cmd


def build_ai_watch_command(
    args: argparse.Namespace,
    python: str,
    scan_path: str | None,
    confluence_path: str | None,
    options_path: str | None,
) -> list[str]:
    cmd = [python, str(TOOLS_DIR / "roxy_ai_watch.py")]
    if scan_path:
        cmd.extend(["--scan-csv", scan_path])
    if confluence_path:
        cmd.extend(["--confluence-csv", confluence_path])
    if options_path:
        cmd.extend(["--options-csv", options_path])
    if args.notify:
        cmd.append("--notify")
    return cmd


def build_health_check_command(args: argparse.Namespace, python: str) -> list[str]:
    cmd = [
        python,
        str(TOOLS_DIR / "roxy_realtime_check.py"),
        "--no-fail",
    ]
    if args.health_app_url:
        cmd.extend(["--app-url", args.health_app_url])
    if args.health_chart_symbol:
        cmd.extend(["--chart-symbol", args.health_chart_symbol])
    if args.health_chart_timeframe:
        cmd.extend(["--chart-timeframe", args.health_chart_timeframe])
    if args.health_skip_chart_fetch:
        cmd.append("--skip-chart-fetch")
    return cmd


def cleanup_live_outputs(retention_count: int) -> list[str]:
    if retention_count <= 0:
        return []
    from tools.output_maintenance import cleanup_output_files

    result = cleanup_output_files(
        output_dir=OUTPUT_DIR,
        retention_rules={pattern: retention_count for pattern in LIVE_OUTPUT_PATTERNS},
    )
    removed = [str(path) for path in result["removed"]]
    if removed:
        print(f"Cleaned {len(removed)} old live output file(s).", flush=True)
    return removed


def run_once(args: argparse.Namespace) -> str | None:
    python = sys.executable
    started_at = now_iso()
    started_monotonic = time.monotonic()
    heartbeat = heartbeat_base(args, status="RUNNING", started_at=started_at)
    write_heartbeat(heartbeat)
    print(f"\n[{datetime.now().isoformat(timespec='seconds')}] Starting live SMA scan", flush=True)
    try:
        scan_result = run_command(build_scan_command(args, python))
        scan_path = extract_saved_scan_path(scan_result.stdout)
        heartbeat["scan_path"] = scan_path
        if scan_path:
            run_command(build_report_command(args, python, scan_path))
            confluence_result = run_command(build_confluence_command(args, python, scan_path))
            confluence_path = extract_saved_scan_path(confluence_result.stdout)
            heartbeat["confluence_path"] = confluence_path
            options_result = run_command(build_options_command(args, python, confluence_path))
            options_path = extract_saved_scan_path(options_result.stdout)
            heartbeat["options_path"] = options_path
            if not args.skip_ai_watch:
                run_command(build_ai_watch_command(args, python, scan_path, confluence_path, options_path))
                heartbeat["ai_watch_ran"] = True
            removed = cleanup_live_outputs(args.retention_count)
            heartbeat["removed_old_files"] = len(removed)
            heartbeat["status"] = "SUCCESS"
        else:
            print("No scan CSV was saved; report not refreshed.", flush=True)
            heartbeat["status"] = "NO_SCAN"
            heartbeat["error"] = "Scan command completed but did not report a saved CSV."
        return scan_path
    except Exception as exc:
        heartbeat["status"] = "FAILED"
        heartbeat["error"] = str(exc)
        raise
    finally:
        heartbeat["finished_at"] = now_iso()
        heartbeat["duration_seconds"] = round(time.monotonic() - started_monotonic, 2)
        write_heartbeat(heartbeat)
        if getattr(args, "health_check", False):
            try:
                run_command(build_health_check_command(args, python))
            except Exception as exc:
                print(f"Health check failed after live run: {exc}", file=sys.stderr, flush=True)
        print(f"[{datetime.now().isoformat(timespec='seconds')}] Live SMA scan finished", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuously scan SMA 20/40/100/200 on intraday timeframes.")
    parser.add_argument("--market", choices=["stocks", "crypto", "both"], default="both")
    parser.add_argument("--symbols", help="Comma-separated symbols for targeted live runs.")
    parser.add_argument("--stock-intervals", default="15m,1h,2h,4h")
    parser.add_argument("--stock-period", default="60d")
    parser.add_argument("--intraday-stock-period", default="60d")
    parser.add_argument("--crypto-timeframes", default="15m,1h,2h,4h")
    parser.add_argument("--crypto-limit", type=int, default=500)
    parser.add_argument("--trigger-tf", default="15m")
    parser.add_argument("--trend-tf", default="1h")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--report-limit", type=int, default=12)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--skip-ai-watch", action="store_true")
    parser.add_argument("--no-notify", dest="notify", action="store_false")
    parser.add_argument("--health-check", action="store_true", help="Run roxy_realtime_check.py after every live cycle.")
    parser.add_argument("--health-app-url", default="")
    parser.add_argument("--health-chart-symbol", default="AAPL")
    parser.add_argument("--health-chart-timeframe", default="1h")
    parser.add_argument("--health-skip-chart-fetch", action="store_true")
    parser.add_argument(
        "--retention-count",
        type=int,
        default=288,
        help="Keep this many recent live CSV files per output type. Use 0 to disable cleanup.",
    )
    parser.set_defaults(notify=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ALERTS_DIR.mkdir(exist_ok=True)

    if args.once:
        run_once(args)
        return

    while True:
        try:
            run_once(args)
        except Exception as exc:
            print(f"[{datetime.now().isoformat(timespec='seconds')}] Live SMA scan failed: {exc}", file=sys.stderr)
        time.sleep(max(30, args.poll_seconds))


if __name__ == "__main__":
    main()
