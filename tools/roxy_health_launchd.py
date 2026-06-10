from __future__ import annotations

import argparse
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = BASE_DIR / "tools"
LOG_DIR = BASE_DIR / "logs"
LAUNCHD_LOG_DIR = Path.home() / "Library" / "Logs" / "RoxyTrading"
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "RoxyTrading"
LAUNCHD_ENV_PATH = APP_SUPPORT_DIR / ".env"
DEFAULT_LABEL = "com.roxy.health_watchdog"
DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_APP_URL = "http://127.0.0.1:8501"
DEFAULT_CHART_SYMBOL = "AAPL"
DEFAULT_CHART_TIMEFRAME = "1h"


def venv_site_packages() -> Path:
    return BASE_DIR / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"


def launchd_python_path() -> Path:
    system_python = Path("/Library/Developer/CommandLineTools/usr/bin/python3")
    if system_python.exists():
        return system_python
    return Path(sys.executable)


def default_python_path() -> Path:
    venv_python = BASE_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def normalize_python_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return Path.cwd() / path


def shell_join(args: list[str | Path]) -> str:
    return " ".join(shlex.quote(str(arg)) for arg in args)


def pythonpath_export() -> str:
    paths = [BASE_DIR, venv_site_packages()]
    value = ":".join(shlex.quote(str(path)) for path in paths)
    return f"export PYTHONPATH={value}${{PYTHONPATH:+:$PYTHONPATH}}"


def env_source_command() -> str:
    env_path = shlex.quote(str(LAUNCHD_ENV_PATH))
    return f"if [ -f {env_path} ]; then source {env_path}; fi"


def sync_launchd_env() -> None:
    source = BASE_DIR / ".env"
    if not source.exists():
        return
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, LAUNCHD_ENV_PATH)
    LAUNCHD_ENV_PATH.chmod(0o600)


def build_health_args(
    *,
    python_path: str | Path,
    app_url: str = DEFAULT_APP_URL,
    chart_symbol: str = DEFAULT_CHART_SYMBOL,
    chart_timeframe: str = DEFAULT_CHART_TIMEFRAME,
    skip_chart_fetch: bool = False,
    notify_health: bool = True,
    ensure_runtime_backup_daemon: bool = True,
    ensure_runtime_backup_report: bool = True,
    ensure_core_launchagents: bool = True,
    ensure_storage_migration: bool = True,
    ensure_live_data: bool = True,
    ensure_yfinance_cache: bool = True,
    ensure_streamlit_app: bool = True,
    ensure_chart_health_report: bool = True,
    ensure_output_maintenance_report: bool = True,
    ensure_alert_quality_report: bool = True,
    no_fail: bool = True,
) -> list[str | Path]:
    args: list[str | Path] = [
        Path(python_path),
        TOOLS_DIR / "roxy_realtime_check.py",
    ]
    if app_url:
        args.extend(["--app-url", app_url])
    if chart_symbol:
        args.extend(["--chart-symbol", chart_symbol])
    if chart_timeframe:
        args.extend(["--chart-timeframe", chart_timeframe])
    if skip_chart_fetch:
        args.append("--skip-chart-fetch")
    if notify_health:
        args.append("--notify-health")
    if ensure_runtime_backup_daemon:
        args.append("--ensure-runtime-backup-daemon")
    if ensure_runtime_backup_report:
        args.append("--ensure-runtime-backup-report")
    if ensure_core_launchagents:
        args.append("--ensure-core-launchagents")
    if ensure_storage_migration:
        args.append("--ensure-storage-migration")
    if ensure_live_data:
        args.append("--ensure-live-data")
    if ensure_yfinance_cache:
        args.append("--ensure-yfinance-cache")
    if ensure_streamlit_app:
        args.append("--ensure-streamlit-app")
    if ensure_chart_health_report:
        args.append("--ensure-chart-health-report")
    if ensure_output_maintenance_report:
        args.append("--ensure-output-maintenance-report")
    if ensure_alert_quality_report:
        args.append("--ensure-alert-quality-report")
    if no_fail:
        args.append("--no-fail")
    return args


def build_chart_health_args(*, python_path: str | Path) -> list[str | Path]:
    return [
        Path(python_path),
        TOOLS_DIR / "chart_realtime_health.py",
        "--no-fail",
    ]


def build_alert_quality_args(*, python_path: str | Path) -> list[str | Path]:
    return [
        Path(python_path),
        BASE_DIR / "alert_quality.py",
    ]


def build_shell_command(
    *,
    python_path: str | Path,
    app_url: str = DEFAULT_APP_URL,
    chart_symbol: str = DEFAULT_CHART_SYMBOL,
    chart_timeframe: str = DEFAULT_CHART_TIMEFRAME,
    skip_chart_fetch: bool = False,
    skip_chart_health: bool = False,
    notify_health: bool = True,
    ensure_runtime_backup_daemon: bool = True,
    ensure_runtime_backup_report: bool = True,
    ensure_core_launchagents: bool = True,
    ensure_storage_migration: bool = True,
    ensure_live_data: bool = True,
    ensure_yfinance_cache: bool = True,
    ensure_streamlit_app: bool = True,
    ensure_chart_health_report: bool = True,
    ensure_output_maintenance_report: bool = True,
    ensure_alert_quality_report: bool = True,
    skip_alert_quality: bool = False,
) -> str:
    chart_health_args = build_chart_health_args(python_path=python_path)
    alert_quality_args = build_alert_quality_args(python_path=python_path)
    health_args = build_health_args(
        python_path=python_path,
        app_url=app_url,
        chart_symbol=chart_symbol,
        chart_timeframe=chart_timeframe,
        skip_chart_fetch=skip_chart_fetch,
        notify_health=notify_health,
        ensure_runtime_backup_daemon=ensure_runtime_backup_daemon,
        ensure_runtime_backup_report=ensure_runtime_backup_report,
        ensure_core_launchagents=ensure_core_launchagents,
        ensure_storage_migration=ensure_storage_migration,
        ensure_live_data=ensure_live_data,
        ensure_yfinance_cache=ensure_yfinance_cache,
        ensure_streamlit_app=ensure_streamlit_app,
        ensure_chart_health_report=ensure_chart_health_report,
        ensure_output_maintenance_report=ensure_output_maintenance_report,
        ensure_alert_quality_report=ensure_alert_quality_report,
        no_fail=True,
    )
    chart_command = "" if skip_chart_health else f"&& {shell_join(chart_health_args)} "
    alert_quality_command = "" if skip_alert_quality else f"&& {shell_join(alert_quality_args)} "
    return (
        f"cd {shlex.quote(str(BASE_DIR))} "
        "&& set -a "
        f"&& {env_source_command()} "
        "&& set +a "
        f"&& {pythonpath_export()} "
        f"{chart_command}"
        f"{alert_quality_command}"
        f"&& exec {shell_join(health_args)}"
    )


def build_plist(
    *,
    label: str,
    command: str,
    interval_seconds: int,
    stdout_path: str | Path,
    stderr_path: str | Path,
    run_at_load: bool,
) -> dict[str, Any]:
    return {
        "Label": label,
        "ProgramArguments": ["/bin/bash", "-lc", command],
        "StartInterval": int(interval_seconds),
        "RunAtLoad": run_at_load,
        "WorkingDirectory": str(Path.home()),
        "StandardOutPath": str(stdout_path),
        "StandardErrorPath": str(stderr_path),
    }


def launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def plist_path_for_label(label: str) -> Path:
    return launch_agents_dir() / f"{label}.plist"


def write_plist(path: Path, plist: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(plist, fh, sort_keys=False)


def launchctl_target() -> str:
    return f"gui/{os.getuid()}"


def run_launchctl(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["launchctl", *args], text=True, capture_output=True, check=False)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "launchctl failed"
        raise RuntimeError(message)
    return result


def is_loaded(label: str) -> bool:
    result = run_launchctl(["print", f"{launchctl_target()}/{label}"])
    return result.returncode == 0


def bootout(label: str) -> None:
    run_launchctl(["bootout", f"{launchctl_target()}/{label}"])


def bootstrap(path: Path) -> None:
    result = run_launchctl(["bootstrap", launchctl_target(), str(path)])
    if result.returncode == 0:
        return
    fallback = run_launchctl(["load", str(path)])
    if fallback.returncode != 0:
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or fallback.stderr.strip()
            or fallback.stdout.strip()
            or "failed to load health watchdog LaunchAgent"
        )
        raise RuntimeError(message)


def kickstart(label: str) -> None:
    run_launchctl(["kickstart", "-k", f"{launchctl_target()}/{label}"], check=True)


def install(args: argparse.Namespace) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    LAUNCHD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    sync_launchd_env()
    python_path = normalize_python_path(args.python_path) if args.python_path else launchd_python_path()
    command = build_shell_command(
        python_path=python_path,
        app_url=args.app_url,
        chart_symbol=args.chart_symbol,
        chart_timeframe=args.chart_timeframe,
        skip_chart_fetch=args.skip_chart_fetch,
        skip_chart_health=args.skip_chart_health,
        notify_health=args.notify_health,
        ensure_runtime_backup_daemon=args.ensure_runtime_backup_daemon,
        ensure_runtime_backup_report=args.ensure_runtime_backup_report,
        ensure_core_launchagents=args.ensure_core_launchagents,
        ensure_storage_migration=args.ensure_storage_migration,
        ensure_live_data=args.ensure_live_data,
        ensure_yfinance_cache=args.ensure_yfinance_cache,
        ensure_streamlit_app=args.ensure_streamlit_app,
        ensure_chart_health_report=args.ensure_chart_health_report,
        ensure_output_maintenance_report=args.ensure_output_maintenance_report,
        ensure_alert_quality_report=args.ensure_alert_quality_report,
        skip_alert_quality=args.skip_alert_quality,
    )
    plist = build_plist(
        label=args.label,
        command=command,
        interval_seconds=args.interval_seconds,
        stdout_path=LAUNCHD_LOG_DIR / "roxy_health_watchdog.out",
        stderr_path=LAUNCHD_LOG_DIR / "roxy_health_watchdog.err",
        run_at_load=True,
    )
    path = plist_path_for_label(args.label)
    write_plist(path, plist)
    if args.load:
        if is_loaded(args.label):
            bootout(args.label)
        bootstrap(path)
        if args.run_now:
            kickstart(args.label)
    return path


def uninstall(args: argparse.Namespace) -> Path:
    path = plist_path_for_label(args.label)
    if is_loaded(args.label):
        bootout(args.label)
    if path.exists():
        path.unlink()
    return path


def run_now(args: argparse.Namespace) -> int:
    python_path = normalize_python_path(args.python_path or default_python_path())
    command = build_shell_command(
        python_path=python_path,
        app_url=args.app_url,
        chart_symbol=args.chart_symbol,
        chart_timeframe=args.chart_timeframe,
        skip_chart_fetch=args.skip_chart_fetch,
        skip_chart_health=args.skip_chart_health,
        notify_health=args.notify_health,
        ensure_runtime_backup_daemon=args.ensure_runtime_backup_daemon,
        ensure_runtime_backup_report=args.ensure_runtime_backup_report,
        ensure_core_launchagents=args.ensure_core_launchagents,
        ensure_storage_migration=args.ensure_storage_migration,
        ensure_live_data=args.ensure_live_data,
        ensure_yfinance_cache=args.ensure_yfinance_cache,
        ensure_streamlit_app=args.ensure_streamlit_app,
        ensure_chart_health_report=args.ensure_chart_health_report,
        ensure_output_maintenance_report=args.ensure_output_maintenance_report,
        ensure_alert_quality_report=args.ensure_alert_quality_report,
        skip_alert_quality=args.skip_alert_quality,
    )
    result = subprocess.run(["/bin/bash", "-lc", command], cwd=BASE_DIR, text=True, check=False)
    return result.returncode


def status(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    loaded = is_loaded(label)
    info: dict[str, Any] = {
        "label": label,
        "path": str(path),
        "installed": path.exists(),
        "loaded": loaded,
        "interval_seconds": None,
        "run_at_load": False,
        "command": "",
        "stdout": "-",
        "stderr": "-",
    }
    if path.exists():
        with path.open("rb") as fh:
            plist = plistlib.load(fh)
        info.update(
            {
                "interval_seconds": plist.get("StartInterval"),
                "run_at_load": bool(plist.get("RunAtLoad")),
                "command": " ".join(plist.get("ProgramArguments", [])),
                "stdout": str(plist.get("StandardOutPath", "-")),
                "stderr": str(plist.get("StandardErrorPath", "-")),
            }
        )
    return info


def print_status(label: str) -> None:
    info = status(label)
    print(f"Label: {label}")
    print(f"Plist: {info['path']}")
    print(f"Installed: {'yes' if info['installed'] else 'no'}")
    print(f"Loaded: {'yes' if info['loaded'] else 'no'}")
    if info["installed"]:
        print(f"Interval: {info['interval_seconds'] or '-'}s")
        print(f"RunAtLoad: {info['run_at_load']}")
        print(f"Command: {info['command']}")
        print(f"Stdout: {info['stdout']}")
        print(f"Stderr: {info['stderr']}")


def add_shared_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--label", default=DEFAULT_LABEL)
    parser.add_argument("--python-path")
    parser.add_argument("--app-url", default=DEFAULT_APP_URL)
    parser.add_argument("--chart-symbol", default=DEFAULT_CHART_SYMBOL)
    parser.add_argument("--chart-timeframe", default=DEFAULT_CHART_TIMEFRAME)
    parser.add_argument("--skip-chart-fetch", action="store_true")
    parser.add_argument("--skip-chart-health", action="store_true")
    parser.add_argument("--skip-alert-quality", action="store_true")
    parser.add_argument("--notify-health", dest="notify_health", action="store_true", default=True)
    parser.add_argument("--no-notify-health", dest="notify_health", action="store_false")
    parser.add_argument("--ensure-runtime-backup-daemon", dest="ensure_runtime_backup_daemon", action="store_true", default=True)
    parser.add_argument("--no-ensure-runtime-backup-daemon", dest="ensure_runtime_backup_daemon", action="store_false")
    parser.add_argument("--ensure-runtime-backup-report", dest="ensure_runtime_backup_report", action="store_true", default=True)
    parser.add_argument("--no-ensure-runtime-backup-report", dest="ensure_runtime_backup_report", action="store_false")
    parser.add_argument("--ensure-core-launchagents", dest="ensure_core_launchagents", action="store_true", default=True)
    parser.add_argument("--no-ensure-core-launchagents", dest="ensure_core_launchagents", action="store_false")
    parser.add_argument("--ensure-storage-migration", dest="ensure_storage_migration", action="store_true", default=True)
    parser.add_argument("--no-ensure-storage-migration", dest="ensure_storage_migration", action="store_false")
    parser.add_argument("--ensure-live-data", dest="ensure_live_data", action="store_true", default=True)
    parser.add_argument("--no-ensure-live-data", dest="ensure_live_data", action="store_false")
    parser.add_argument("--ensure-yfinance-cache", dest="ensure_yfinance_cache", action="store_true", default=True)
    parser.add_argument("--no-ensure-yfinance-cache", dest="ensure_yfinance_cache", action="store_false")
    parser.add_argument("--ensure-streamlit-app", dest="ensure_streamlit_app", action="store_true", default=True)
    parser.add_argument("--no-ensure-streamlit-app", dest="ensure_streamlit_app", action="store_false")
    parser.add_argument("--ensure-chart-health-report", dest="ensure_chart_health_report", action="store_true", default=True)
    parser.add_argument("--no-ensure-chart-health-report", dest="ensure_chart_health_report", action="store_false")
    parser.add_argument("--ensure-output-maintenance-report", dest="ensure_output_maintenance_report", action="store_true", default=True)
    parser.add_argument("--no-ensure-output-maintenance-report", dest="ensure_output_maintenance_report", action="store_false")
    parser.add_argument("--ensure-alert-quality-report", dest="ensure_alert_quality_report", action="store_true", default=True)
    parser.add_argument("--no-ensure-alert-quality-report", dest="ensure_alert_quality_report", action="store_false")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install or control the Roxy realtime health watchdog LaunchAgent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Write and load the health watchdog LaunchAgent.")
    add_shared_options(install_parser)
    install_parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    install_parser.add_argument("--no-load", dest="load", action="store_false")
    install_parser.add_argument("--run-now", action="store_true")
    install_parser.set_defaults(load=True)

    status_parser = subparsers.add_parser("status", help="Show health watchdog LaunchAgent status.")
    status_parser.add_argument("--label", default=DEFAULT_LABEL)

    run_now_parser = subparsers.add_parser("run-now", help="Run the realtime health check immediately.")
    add_shared_options(run_now_parser)

    uninstall_parser = subparsers.add_parser("uninstall", help="Unload and delete the health watchdog LaunchAgent.")
    uninstall_parser.add_argument("--label", default=DEFAULT_LABEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "install":
        path = install(args)
        print(f"Installed: {path}")
        print_status(args.label)
    elif args.command == "status":
        print_status(args.label)
    elif args.command == "run-now":
        raise SystemExit(run_now(args))
    elif args.command == "uninstall":
        path = uninstall(args)
        print(f"Uninstalled: {path}")


if __name__ == "__main__":
    main()
