from __future__ import annotations

import argparse
import json
import os
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
from durable_storage import atomic_write_text

ALERTS_DIR = alerts_dir()
OUTPUT_DIR = output_dir()
HEARTBEAT_PATH = ALERTS_DIR / "ma_live_heartbeat.json"
LOCK_PATH = ALERTS_DIR / "ma_live.lock"
DEFAULT_LOCK_STALE_SECONDS = 60 * 30
LIVE_OUTPUT_PATTERNS = (
    "ma_live_strategy_*.csv",
    "ma_confluence_*.csv",
    "options_candidates_*.csv",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_heartbeat(payload: dict[str, Any], path: str | Path | None = None) -> Path:
    heartbeat_path = Path(path) if path is not None else HEARTBEAT_PATH
    atomic_write_text(json.dumps(payload, indent=2, sort_keys=True), heartbeat_path)
    return heartbeat_path


def pid_is_running(pid: Any) -> bool:
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
    except OSError:
        return False
    return True


def read_live_lock(path: str | Path = LOCK_PATH) -> dict[str, Any]:
    lock_path = Path(path)
    if not lock_path.exists():
        return {}
    try:
        payload = json.loads(lock_path.read_text())
    except Exception:
        return {"malformed": True, "path": str(lock_path)}
    return payload if isinstance(payload, dict) else {"malformed": True, "path": str(lock_path)}


def acquire_live_lock(path: str | Path = LOCK_PATH, *, stale_seconds: float = DEFAULT_LOCK_STALE_SECONDS) -> tuple[bool, dict[str, Any]]:
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    current = time.time()
    existing = read_live_lock(lock_path)
    if existing:
        started_epoch = float(existing.get("started_epoch") or 0.0)
        age_seconds = max(0.0, current - started_epoch) if started_epoch else None
        active = pid_is_running(existing.get("pid"))
        stale = bool(age_seconds is not None and age_seconds > stale_seconds)
        if active and not stale:
            existing["age_seconds"] = age_seconds
            existing["active"] = True
            return False, existing
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            existing["active"] = active
            existing["age_seconds"] = age_seconds
            return False, existing
    payload = {"pid": os.getpid(), "started_at": now_iso(), "started_epoch": current}
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        existing = read_live_lock(lock_path)
        existing["active"] = pid_is_running(existing.get("pid"))
        return False, existing
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True))
    return True, payload


def release_live_lock(path: str | Path = LOCK_PATH) -> None:
    lock_path = Path(path)
    payload = read_live_lock(lock_path)
    if int(payload.get("pid") or -1) == os.getpid():
        lock_path.unlink(missing_ok=True)


def heartbeat_base(args: argparse.Namespace, *, status: str, started_at: str) -> dict[str, Any]:
    return {
        "status": status,
        "started_at": started_at,
        "finished_at": None,
        "duration_seconds": None,
        "market": args.market,
        "requested_market": args.market,
        "effective_market": args.market,
        "adaptive_market_reason": "",
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
        "current_step": None,
        "steps": [],
        "lock_path": str(LOCK_PATH),
        "error": None,
    }


def read_json_object(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text())
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def market_route_snapshot(alerts_path: str | Path = ALERTS_DIR) -> dict[str, Any]:
    alerts = Path(alerts_path)
    status_payload = read_json_object(alerts / "roxy_status.json")
    realtime_payload = read_json_object(alerts / "roxy_realtime_check.json")
    checks = realtime_payload.get("checks") if isinstance(realtime_payload.get("checks"), list) else []
    provider_blocked = any(
        str(item.get("name") or "") in {"chart_provider_effective", "alpaca_account_probe"}
        and str(item.get("status") or "").upper() in {"WARN", "FAIL"}
        and any(
            marker in str(item.get("detail") or "").lower()
            for marker in ("alpaca_auth", "alpaca account auth failed", "polygon_not_configured")
        )
        for item in checks
        if isinstance(item, dict)
    )
    if status_payload:
        return {
            "source": str(alerts / "roxy_status.json"),
            "safe_mode": status_payload.get("safe_mode"),
            "allowed_markets": status_payload.get("allowed_markets") or [],
            "blocked_markets": status_payload.get("blocked_markets") or [],
            "active_route_label": status_payload.get("active_route_label"),
            "premium_provider_blocked": provider_blocked,
        }

    operational = realtime_payload.get("operational_summary") if isinstance(realtime_payload.get("operational_summary"), dict) else {}
    if operational:
        return {
            "source": str(alerts / "roxy_realtime_check.json"),
            "safe_mode": operational.get("safe_mode"),
            "allowed_markets": operational.get("allowed_markets") or [],
            "blocked_markets": operational.get("blocked_markets") or [],
            "active_route_label": operational.get("active_route_label"),
            "premium_provider_blocked": provider_blocked,
        }
    return {"premium_provider_blocked": provider_blocked}


def effective_scan_market(args: argparse.Namespace, alerts_path: str | Path = ALERTS_DIR) -> tuple[str, str]:
    requested = str(args.market or "both")
    if requested != "both":
        return requested, ""
    if str(getattr(args, "symbols", "") or "").strip():
        return requested, ""

    route = market_route_snapshot(alerts_path)
    allowed = {str(value).lower() for value in route.get("allowed_markets") or []}
    blocked = {str(value).lower() for value in route.get("blocked_markets") or []}
    safe_mode = str(route.get("safe_mode") or "")
    if "crypto" in allowed and {"stock", "options"}.issubset(blocked):
        reason = (
            "stock/options blocked by provider premium; scanning crypto only until premium realtime recovers"
        )
        return "crypto", reason
    if bool(route.get("premium_provider_blocked")) and safe_mode in {"NO_ALERTS_UNTIL_DATA_OK", "NO_STOCK_OR_OPTIONS_ALERTS", ""}:
        reason = "premium stock provider blocked; scanning crypto only to keep live cycle fast"
        return "crypto", reason
    return requested, ""


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


def run_heartbeat_step(
    heartbeat: dict[str, Any],
    name: str,
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    step = {
        "name": name,
        "status": "RUNNING",
        "started_at": now_iso(),
        "finished_at": None,
        "duration_seconds": None,
    }
    heartbeat["current_step"] = name
    heartbeat.setdefault("steps", []).append(step)
    write_heartbeat(heartbeat)
    started = time.monotonic()
    try:
        result = run_command(command)
        step["status"] = "SUCCESS"
        return result
    except Exception as exc:
        step["status"] = "FAILED"
        step["error"] = str(exc)
        raise
    finally:
        step["finished_at"] = now_iso()
        step["duration_seconds"] = round(time.monotonic() - started, 2)
        heartbeat["current_step"] = None
        write_heartbeat(heartbeat)


def run_local_heartbeat_step(
    heartbeat: dict[str, Any],
    name: str,
    fn,
) -> Any:
    step = {
        "name": name,
        "status": "RUNNING",
        "started_at": now_iso(),
        "finished_at": None,
        "duration_seconds": None,
    }
    heartbeat["current_step"] = name
    heartbeat.setdefault("steps", []).append(step)
    write_heartbeat(heartbeat)
    started = time.monotonic()
    try:
        result = fn()
        step["status"] = "SUCCESS"
        return result
    except Exception as exc:
        step["status"] = "FAILED"
        step["error"] = str(exc)
        raise
    finally:
        step["finished_at"] = now_iso()
        step["duration_seconds"] = round(time.monotonic() - started, 2)
        heartbeat["current_step"] = None
        write_heartbeat(heartbeat)


def build_scan_command(args: argparse.Namespace, python: str, *, market: str | None = None) -> list[str]:
    scan_market = market or args.market
    cmd = [
        python,
        str(TOOLS_DIR / "ma_scan.py"),
        "--market",
        scan_market,
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
        "--timing-json",
        str(ALERTS_DIR / "ma_live_scan_timing.json"),
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
        "--ensure-dashboard-render-probe-report",
        "--ensure-chart-health-report",
        "--ensure-alert-quality-report",
        "--ensure-daily-opportunity-plan-report",
        "--ensure-status-snapshot-report",
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
    scan_market, adaptive_reason = effective_scan_market(args)
    heartbeat["effective_market"] = scan_market
    heartbeat["adaptive_market_reason"] = adaptive_reason
    acquired, lock_info = acquire_live_lock(LOCK_PATH)
    if not acquired:
        heartbeat.update(
            {
                "status": "SKIPPED_ACTIVE_LOCK",
                "finished_at": now_iso(),
                "duration_seconds": round(time.monotonic() - started_monotonic, 2),
                "error": "Another ma_live run is already active.",
                "active_lock": lock_info,
            }
        )
        write_heartbeat(heartbeat)
        print("Skipped live SMA scan because another ma_live run is active.", flush=True)
        return None
    write_heartbeat(heartbeat)
    if adaptive_reason:
        print(
            f"\n[{datetime.now().isoformat(timespec='seconds')}] Starting live SMA scan "
            f"({args.market} -> {scan_market}: {adaptive_reason})",
            flush=True,
        )
    else:
        print(f"\n[{datetime.now().isoformat(timespec='seconds')}] Starting live SMA scan", flush=True)
    try:
        scan_result = run_heartbeat_step(heartbeat, "scan", build_scan_command(args, python, market=scan_market))
        scan_path = extract_saved_scan_path(scan_result.stdout)
        heartbeat["scan_path"] = scan_path
        if scan_path:
            run_heartbeat_step(heartbeat, "report", build_report_command(args, python, scan_path))
            confluence_result = run_heartbeat_step(
                heartbeat, "confluence", build_confluence_command(args, python, scan_path)
            )
            confluence_path = extract_saved_scan_path(confluence_result.stdout)
            heartbeat["confluence_path"] = confluence_path
            options_result = run_heartbeat_step(heartbeat, "options", build_options_command(args, python, confluence_path))
            options_path = extract_saved_scan_path(options_result.stdout)
            heartbeat["options_path"] = options_path
            if not args.skip_ai_watch:
                run_heartbeat_step(
                    heartbeat, "ai_watch", build_ai_watch_command(args, python, scan_path, confluence_path, options_path)
                )
                heartbeat["ai_watch_ran"] = True
            removed = run_local_heartbeat_step(heartbeat, "cleanup", lambda: cleanup_live_outputs(args.retention_count))
            heartbeat["removed_old_files"] = len(removed)
            if heartbeat.get("steps"):
                heartbeat["steps"][-1]["removed_old_files"] = len(removed)
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
        release_live_lock(LOCK_PATH)
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
