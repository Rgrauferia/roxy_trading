from __future__ import annotations

import argparse
import importlib
import json
import shlex
from pathlib import Path
from typing import Any


CORE_LAUNCHD_MODULES: dict[str, str] = {
    "streamlit": "tools.streamlit_launchd",
    "ma_live": "tools.ma_live_launchd",
    "ma_daily": "tools.ma_daily_launchd",
    "output_maintenance": "tools.output_maintenance_launchd",
}
HEALTH_WATCHDOG_NAME = "health_watchdog"
OUTPUT_MAINTENANCE_NAME = "output_maintenance"
MA_LIVE_NAME = "ma_live"
STREAMLIT_NAME = "streamlit"
MA_DAILY_NAME = "ma_daily"
REQUIRED_LIVE_TIMEFRAMES = {"15m", "1h", "2h", "4h"}
HEALTH_WATCHDOG_REQUIRED_FLAGS = [
    "--notify-health",
    "--ensure-runtime-backup-daemon",
    "--ensure-runtime-backup-report",
        "--ensure-core-launchagents",
        "--ensure-live-data",
        "--ensure-yfinance-cache",
        "--ensure-streamlit-app",
    "--ensure-chart-health-report",
    "--ensure-output-maintenance-report",
    "--ensure-alert-quality-report",
    "--no-fail",
]


def command_has_flag(command: str, flag: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    return flag in parts


def command_parts(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return str(command or "").split()


def command_option_value(command: str, option: str) -> str | None:
    parts = command_parts(command)
    if option not in parts:
        return None
    idx = parts.index(option)
    if idx + 1 >= len(parts):
        return None
    return parts[idx + 1]


def command_option_int(command: str, option: str) -> int | None:
    value = command_option_value(command, option)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def command_has_timeframes(command: str, option: str, required: set[str]) -> bool:
    value = command_option_value(command, option)
    if not value:
        return False
    present = {part.strip().lower() for part in value.split(",") if part.strip()}
    return required.issubset(present)


def health_watchdog_install_args(module: Any) -> argparse.Namespace:
    return argparse.Namespace(
        label=getattr(module, "DEFAULT_LABEL"),
        python_path=None,
        app_url=getattr(module, "DEFAULT_APP_URL"),
        chart_symbol=getattr(module, "DEFAULT_CHART_SYMBOL"),
        chart_timeframe=getattr(module, "DEFAULT_CHART_TIMEFRAME"),
        skip_chart_fetch=False,
        skip_chart_health=False,
        skip_alert_quality=False,
        notify_health=True,
        ensure_runtime_backup_daemon=True,
        ensure_runtime_backup_report=True,
        ensure_core_launchagents=True,
        ensure_live_data=True,
        ensure_yfinance_cache=True,
        ensure_streamlit_app=True,
        ensure_chart_health_report=True,
        ensure_output_maintenance_report=True,
        ensure_alert_quality_report=True,
        interval_seconds=getattr(module, "DEFAULT_INTERVAL_SECONDS"),
        load=True,
        run_now=False,
    )


def recover_health_watchdog_config() -> dict[str, Any]:
    from tools import roxy_health_launchd

    before = roxy_health_launchd.status()
    command = str(before.get("command") or "")
    missing_flags = [flag for flag in HEALTH_WATCHDOG_REQUIRED_FLAGS if not command_has_flag(command, flag)]
    try:
        interval_seconds = int(before.get("interval_seconds") or 0)
    except (TypeError, ValueError):
        interval_seconds = 0
    issues = []
    if not before.get("installed"):
        issues.append("not_installed")
    if not before.get("loaded"):
        issues.append("not_loaded")
    if "roxy_realtime_check.py" not in command:
        issues.append("wrong_command")
    if missing_flags:
        issues.append("missing_flags")
    if interval_seconds <= 0:
        issues.append("missing_interval")
    elif interval_seconds > 900:
        issues.append("slow_interval")

    result: dict[str, Any] = {
        "module": "tools.roxy_health_launchd",
        "label": str(before.get("label") or getattr(roxy_health_launchd, "DEFAULT_LABEL", "")),
        "before": before,
        "missing_flags": missing_flags,
        "issues": issues,
        "interval_seconds": interval_seconds,
        "action": "none",
        "ok": bool(before.get("installed") and before.get("loaded") and not issues),
    }
    if not issues:
        result["action"] = "already_current"
        result["after"] = before
        return result

    try:
        path = roxy_health_launchd.install(health_watchdog_install_args(roxy_health_launchd))
        after = roxy_health_launchd.status()
        after_command = str(after.get("command") or "")
        after_missing_flags = [
            flag for flag in HEALTH_WATCHDOG_REQUIRED_FLAGS if not command_has_flag(after_command, flag)
        ]
        result["action"] = "reinstalled"
        result["path"] = str(path)
        result["after"] = after
        result["after_missing_flags"] = after_missing_flags
        result["ok"] = bool(after.get("installed") and after.get("loaded") and not after_missing_flags)
        return result
    except Exception as exc:
        result["action"] = "error"
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["after"] = roxy_health_launchd.status()
        return result


def ma_live_install_args(module: Any) -> argparse.Namespace:
    return argparse.Namespace(
        label=getattr(module, "DEFAULT_LABEL"),
        python_path=None,
        market="both",
        symbols=None,
        stock_intervals="15m,1h,2h,4h",
        crypto_timeframes="15m,1h,2h,4h",
        trigger_tf="15m",
        trend_tf="1h",
        poll_seconds=300,
        limit=30,
        report_limit=12,
        retention_count=96,
        health_check=True,
        health_app_url="http://127.0.0.1:8501",
        health_chart_symbol="AAPL",
        health_chart_timeframe="1h",
        health_skip_chart_fetch=False,
        load=True,
    )


def ma_live_config_issues(info: dict[str, Any]) -> list[str]:
    command = str(info.get("command") or "")
    issues = []
    if not info.get("installed"):
        issues.append("not_installed")
    if not info.get("loaded"):
        issues.append("not_loaded")
    if not info.get("keep_alive"):
        issues.append("keep_alive_disabled")
    if "ma_live.py" not in command:
        issues.append("wrong_command")
    if not command_has_timeframes(command, "--stock-intervals", REQUIRED_LIVE_TIMEFRAMES):
        issues.append("stock_timeframes")
    if not command_has_timeframes(command, "--crypto-timeframes", REQUIRED_LIVE_TIMEFRAMES):
        issues.append("crypto_timeframes")
    retention_count = command_option_int(command, "--retention-count")
    if retention_count is None:
        issues.append("retention_missing")
    elif retention_count <= 0 or retention_count > 288:
        issues.append("retention_out_of_range")
    if not command_has_flag(command, "--health-check"):
        issues.append("health_check_missing")
    return issues


def recover_ma_live_config() -> dict[str, Any]:
    from tools import ma_live_launchd

    before = ma_live_launchd.status()
    issues = ma_live_config_issues(before)
    result: dict[str, Any] = {
        "module": "tools.ma_live_launchd",
        "label": str(before.get("label") or getattr(ma_live_launchd, "DEFAULT_LABEL", "")),
        "before": before,
        "issues": issues,
        "action": "none",
        "ok": bool(before.get("installed") and before.get("loaded") and not issues),
    }
    if not issues:
        result["action"] = "already_current"
        result["after"] = before
        return result

    try:
        path = ma_live_launchd.install(ma_live_install_args(ma_live_launchd))
        after = ma_live_launchd.status()
        after_issues = ma_live_config_issues(after)
        result["action"] = "reinstalled"
        result["path"] = str(path)
        result["after"] = after
        result["after_issues"] = after_issues
        result["ok"] = not after_issues
        return result
    except Exception as exc:
        result["action"] = "error"
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["after"] = ma_live_launchd.status()
        return result


def streamlit_install_args(module: Any) -> argparse.Namespace:
    return argparse.Namespace(
        label=getattr(module, "DEFAULT_LABEL"),
        python_path=None,
        address=getattr(module, "DEFAULT_ADDRESS"),
        port=getattr(module, "DEFAULT_PORT"),
        load=True,
    )


def streamlit_config_issues(info: dict[str, Any], module: Any) -> list[str]:
    command = str(info.get("command") or "")
    issues = []
    if not info.get("installed"):
        issues.append("not_installed")
    if not info.get("loaded"):
        issues.append("not_loaded")
    if not info.get("keep_alive"):
        issues.append("keep_alive_disabled")
    if "streamlit_app.py" not in command:
        issues.append("wrong_command")
    if info.get("port") != getattr(module, "DEFAULT_PORT"):
        issues.append("port_mismatch")
    if info.get("lan_ready") is False:
        issues.append("lan_not_ready")
    return issues


def recover_streamlit_config() -> dict[str, Any]:
    from tools import streamlit_launchd

    before = streamlit_launchd.status()
    issues = streamlit_config_issues(before, streamlit_launchd)
    result: dict[str, Any] = {
        "module": "tools.streamlit_launchd",
        "label": str(before.get("label") or getattr(streamlit_launchd, "DEFAULT_LABEL", "")),
        "before": before,
        "issues": issues,
        "action": "none",
        "ok": bool(before.get("installed") and before.get("loaded") and not issues),
    }
    if not issues:
        result["action"] = "already_current"
        result["after"] = before
        return result

    try:
        path = streamlit_launchd.install(streamlit_install_args(streamlit_launchd))
        after = streamlit_launchd.status()
        after_issues = streamlit_config_issues(after, streamlit_launchd)
        result["action"] = "reinstalled"
        result["path"] = str(path)
        result["after"] = after
        result["after_issues"] = after_issues
        result["ok"] = not after_issues
        return result
    except Exception as exc:
        result["action"] = "error"
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["after"] = streamlit_launchd.status()
        return result


def ma_daily_install_args(module: Any) -> argparse.Namespace:
    return argparse.Namespace(
        label=getattr(module, "DEFAULT_LABEL"),
        python_path=None,
        market="both",
        symbols=None,
        limit=30,
        report_limit=12,
        refresh_backtests=False,
        stock_period="5y",
        crypto_limit=1000,
        min_buy_hold_edge_pct=0.0,
        retention_count=30,
        hour=getattr(module, "DEFAULT_HOUR"),
        minute=getattr(module, "DEFAULT_MINUTE"),
        run_at_load=False,
        load=True,
        run_now=False,
    )


def ma_daily_config_issues(info: dict[str, Any]) -> list[str]:
    command = str(info.get("command") or "")
    schedule = dict(info.get("schedule") or {})
    issues = []
    if not info.get("installed"):
        issues.append("not_installed")
    if not info.get("loaded"):
        issues.append("not_loaded")
    if "ma_daily.py" not in command:
        issues.append("wrong_command")
    if "Hour" not in schedule or "Minute" not in schedule:
        issues.append("missing_schedule")
    retention_count = command_option_int(command, "--retention-count")
    if retention_count is None:
        issues.append("retention_missing")
    elif retention_count <= 0 or retention_count > 120:
        issues.append("retention_out_of_range")
    return issues


def recover_ma_daily_config() -> dict[str, Any]:
    from tools import ma_daily_launchd

    before = ma_daily_launchd.status()
    issues = ma_daily_config_issues(before)
    result: dict[str, Any] = {
        "module": "tools.ma_daily_launchd",
        "label": str(before.get("label") or getattr(ma_daily_launchd, "DEFAULT_LABEL", "")),
        "before": before,
        "issues": issues,
        "action": "none",
        "ok": bool(before.get("installed") and before.get("loaded") and not issues),
    }
    if not issues:
        result["action"] = "already_current"
        result["after"] = before
        return result

    try:
        path = ma_daily_launchd.install(ma_daily_install_args(ma_daily_launchd))
        after = ma_daily_launchd.status()
        after_issues = ma_daily_config_issues(after)
        result["action"] = "reinstalled"
        result["path"] = str(path)
        result["after"] = after
        result["after_issues"] = after_issues
        result["ok"] = not after_issues
        return result
    except Exception as exc:
        result["action"] = "error"
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["after"] = ma_daily_launchd.status()
        return result


def output_maintenance_install_args(module: Any) -> argparse.Namespace:
    return argparse.Namespace(
        label=getattr(module, "DEFAULT_LABEL"),
        python_path=None,
        dry_run=False,
        hour=getattr(module, "DEFAULT_HOUR"),
        minute=getattr(module, "DEFAULT_MINUTE"),
        run_at_load=False,
        load=True,
        run_now=False,
    )


def recover_output_maintenance_config() -> dict[str, Any]:
    from tools import output_maintenance_launchd

    before = output_maintenance_launchd.status()
    command = str(before.get("command") or "")
    schedule = dict(before.get("schedule") or {})
    issues = []
    if not before.get("installed"):
        issues.append("not_installed")
    if not before.get("loaded"):
        issues.append("not_loaded")
    if "output_maintenance.py" not in command:
        issues.append("wrong_command")
    if command_has_flag(command, "--dry-run"):
        issues.append("dry_run")
    if "Hour" not in schedule or "Minute" not in schedule:
        issues.append("missing_schedule")

    result: dict[str, Any] = {
        "module": "tools.output_maintenance_launchd",
        "label": str(before.get("label") or getattr(output_maintenance_launchd, "DEFAULT_LABEL", "")),
        "before": before,
        "issues": issues,
        "action": "none",
        "ok": bool(before.get("installed") and before.get("loaded") and not issues),
    }
    if not issues:
        result["action"] = "already_current"
        result["after"] = before
        return result

    try:
        path = output_maintenance_launchd.install(output_maintenance_install_args(output_maintenance_launchd))
        after = output_maintenance_launchd.status()
        after_command = str(after.get("command") or "")
        after_schedule = dict(after.get("schedule") or {})
        after_issues = []
        if not after.get("installed"):
            after_issues.append("not_installed")
        if not after.get("loaded"):
            after_issues.append("not_loaded")
        if "output_maintenance.py" not in after_command:
            after_issues.append("wrong_command")
        if command_has_flag(after_command, "--dry-run"):
            after_issues.append("dry_run")
        if "Hour" not in after_schedule or "Minute" not in after_schedule:
            after_issues.append("missing_schedule")
        result["action"] = "reinstalled"
        result["path"] = str(path)
        result["after"] = after
        result["after_issues"] = after_issues
        result["ok"] = not after_issues
        return result
    except Exception as exc:
        result["action"] = "error"
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["after"] = output_maintenance_launchd.status()
        return result


def recover_launch_agent(module_name: str, *, label: str | None = None) -> dict[str, Any]:
    module = importlib.import_module(module_name)
    status_fn = getattr(module, "status")
    if label:
        before = status_fn(label)
    else:
        before = status_fn()
    result: dict[str, Any] = {
        "module": module_name,
        "label": label or str(before.get("label") or getattr(module, "DEFAULT_LABEL", "")),
        "before": before,
        "action": "none",
        "ok": bool(before.get("loaded")),
    }
    if before.get("loaded"):
        result["action"] = "already_loaded"
        result["after"] = before
        return result
    if not before.get("installed"):
        result["action"] = "not_installed"
        result["ok"] = False
        result["after"] = before
        return result

    plist_path = Path(str(before.get("path") or ""))
    try:
        getattr(module, "bootstrap")(plist_path)
        if label:
            after = status_fn(label)
        else:
            after = status_fn()
        result["action"] = "bootstrapped"
        result["after"] = after
        result["ok"] = bool(after.get("loaded"))
        return result
    except Exception as exc:
        result["action"] = "error"
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        if label:
            result["after"] = status_fn(label)
        else:
            result["after"] = status_fn()
        return result


def restart_launch_agent(module_name: str, *, label: str | None = None) -> dict[str, Any]:
    module = importlib.import_module(module_name)
    status_fn = getattr(module, "status")
    if label:
        before = status_fn(label)
    else:
        before = status_fn()
    service_label = label or str(before.get("label") or getattr(module, "DEFAULT_LABEL", ""))
    result: dict[str, Any] = {
        "module": module_name,
        "label": service_label,
        "before": before,
        "action": "restart",
        "ok": False,
    }
    if not before.get("installed"):
        result["action"] = "not_installed"
        result["after"] = before
        return result

    plist_path = Path(str(before.get("path") or before.get("plist") or ""))
    try:
        if before.get("loaded"):
            getattr(module, "bootout")(service_label)
        getattr(module, "bootstrap")(plist_path)
        if label:
            after = status_fn(label)
        else:
            after = status_fn()
        result["after"] = after
        result["ok"] = bool(after.get("loaded"))
        return result
    except Exception as exc:
        result["action"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        if label:
            result["after"] = status_fn(label)
        else:
            result["after"] = status_fn()
        return result


def ensure_core_launch_agents(modules: dict[str, str] | None = None) -> dict[str, Any]:
    selected = dict(modules or CORE_LAUNCHD_MODULES)
    services = {name: recover_launch_agent(module_name) for name, module_name in selected.items()}
    if modules is None:
        services[HEALTH_WATCHDOG_NAME] = recover_health_watchdog_config()
        services[OUTPUT_MAINTENANCE_NAME] = recover_output_maintenance_config()
        services[MA_LIVE_NAME] = recover_ma_live_config()
        services[STREAMLIT_NAME] = recover_streamlit_config()
        services[MA_DAILY_NAME] = recover_ma_daily_config()
    recovered = [name for name, item in services.items() if item.get("action") == "bootstrapped" and item.get("ok")]
    recovered.extend(name for name, item in services.items() if item.get("action") == "reinstalled" and item.get("ok"))
    failed = [name for name, item in services.items() if not item.get("ok")]
    return {
        "status": "OK" if not failed else "WARN",
        "service_count": len(services),
        "recovered": recovered,
        "failed": failed,
        "services": services,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover installed Roxy LaunchAgents that are not loaded.")
    parser.add_argument("--service", choices=sorted(CORE_LAUNCHD_MODULES), action="append")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    modules = CORE_LAUNCHD_MODULES
    if args.service:
        modules = {name: CORE_LAUNCHD_MODULES[name] for name in args.service}
    print(json.dumps(ensure_core_launch_agents(modules), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
