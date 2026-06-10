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
DEFAULT_LABEL = "com.roxy.ma_live"


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


def build_ma_live_args(
    *,
    python_path: str | Path,
    market: str,
    stock_intervals: str,
    crypto_timeframes: str,
    trigger_tf: str,
    trend_tf: str,
    poll_seconds: int,
    limit: int,
    report_limit: int,
    retention_count: int,
    health_check: bool = False,
    health_app_url: str = "",
    health_chart_symbol: str = "",
    health_chart_timeframe: str = "",
    health_skip_chart_fetch: bool = False,
    symbols: str | None = None,
) -> list[str | Path]:
    args: list[str | Path] = [
        Path(python_path),
        TOOLS_DIR / "ma_live.py",
        "--market",
        market,
        "--stock-intervals",
        stock_intervals,
        "--crypto-timeframes",
        crypto_timeframes,
        "--trigger-tf",
        trigger_tf,
        "--trend-tf",
        trend_tf,
        "--poll-seconds",
        str(poll_seconds),
        "--limit",
        str(limit),
        "--report-limit",
        str(report_limit),
        "--retention-count",
        str(retention_count),
    ]
    if health_check:
        args.append("--health-check")
        if health_app_url:
            args.extend(["--health-app-url", health_app_url])
        if health_chart_symbol:
            args.extend(["--health-chart-symbol", health_chart_symbol])
        if health_chart_timeframe:
            args.extend(["--health-chart-timeframe", health_chart_timeframe])
        if health_skip_chart_fetch:
            args.append("--health-skip-chart-fetch")
    if symbols:
        args.extend(["--symbols", symbols])
    return args


def build_shell_command(
    *,
    python_path: str | Path,
    market: str,
    stock_intervals: str,
    crypto_timeframes: str,
    trigger_tf: str,
    trend_tf: str,
    poll_seconds: int,
    limit: int,
    report_limit: int,
    retention_count: int,
    health_check: bool = False,
    health_app_url: str = "",
    health_chart_symbol: str = "",
    health_chart_timeframe: str = "",
    health_skip_chart_fetch: bool = False,
    symbols: str | None = None,
) -> str:
    live_args = build_ma_live_args(
        python_path=python_path,
        market=market,
        stock_intervals=stock_intervals,
        crypto_timeframes=crypto_timeframes,
        trigger_tf=trigger_tf,
        trend_tf=trend_tf,
        poll_seconds=poll_seconds,
        limit=limit,
        report_limit=report_limit,
        retention_count=retention_count,
        health_check=health_check,
        health_app_url=health_app_url,
        health_chart_symbol=health_chart_symbol,
        health_chart_timeframe=health_chart_timeframe,
        health_skip_chart_fetch=health_skip_chart_fetch,
        symbols=symbols,
    )
    return (
        f"cd {shlex.quote(str(BASE_DIR))} "
        "&& set -a "
        f"&& {env_source_command()} "
        "&& set +a "
        f"&& {pythonpath_export()} "
        f"&& exec {shell_join(live_args)}"
    )


def build_plist(
    *,
    label: str,
    command: str,
    stdout_path: str | Path,
    stderr_path: str | Path,
    run_at_load: bool,
    keep_alive: bool,
) -> dict[str, Any]:
    return {
        "Label": label,
        "ProgramArguments": ["/bin/bash", "-lc", command],
        "RunAtLoad": run_at_load,
        "KeepAlive": keep_alive,
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
            or "failed to load LaunchAgent"
        )
        raise RuntimeError(message)


def install(args: argparse.Namespace) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    LAUNCHD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    sync_launchd_env()
    python_path = normalize_python_path(args.python_path) if args.python_path else launchd_python_path()
    command = build_shell_command(
        python_path=python_path,
        market=args.market,
        stock_intervals=args.stock_intervals,
        crypto_timeframes=args.crypto_timeframes,
        trigger_tf=args.trigger_tf,
        trend_tf=args.trend_tf,
        poll_seconds=args.poll_seconds,
        limit=args.limit,
        report_limit=args.report_limit,
        retention_count=args.retention_count,
        health_check=args.health_check,
        health_app_url=args.health_app_url,
        health_chart_symbol=args.health_chart_symbol,
        health_chart_timeframe=args.health_chart_timeframe,
        health_skip_chart_fetch=args.health_skip_chart_fetch,
        symbols=args.symbols,
    )
    plist = build_plist(
        label=args.label,
        command=command,
        stdout_path=LAUNCHD_LOG_DIR / "ma_live.out",
        stderr_path=LAUNCHD_LOG_DIR / "ma_live.err",
        run_at_load=True,
        keep_alive=True,
    )
    path = plist_path_for_label(args.label)
    write_plist(path, plist)

    if args.load:
        if is_loaded(args.label):
            bootout(args.label)
        bootstrap(path)

    return path


def uninstall(args: argparse.Namespace) -> Path:
    path = plist_path_for_label(args.label)
    if is_loaded(args.label):
        bootout(args.label)
    if path.exists():
        path.unlink()
    return path


def status(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    loaded = is_loaded(label)
    info: dict[str, Any] = {
        "label": label,
        "path": str(path),
        "installed": path.exists(),
        "loaded": loaded,
        "keep_alive": False,
        "command": "",
        "stdout": "-",
        "stderr": "-",
    }
    if path.exists():
        with path.open("rb") as fh:
            plist = plistlib.load(fh)
        info.update(
            {
                "keep_alive": bool(plist.get("KeepAlive", False)),
                "command": " ".join(plist.get("ProgramArguments", [])),
                "stdout": str(plist.get("StandardOutPath", "-")),
                "stderr": str(plist.get("StandardErrorPath", "-")),
            }
        )
    return info


def print_status(label: str) -> None:
    info = status(label)
    path = Path(str(info["path"]))
    loaded = bool(info["loaded"])
    print(f"Label: {label}")
    print(f"Plist: {path}")
    print(f"Installed: {'yes' if info['installed'] else 'no'}")
    print(f"Loaded: {'yes' if loaded else 'no'}")
    if info["installed"]:
        print(f"KeepAlive: {info['keep_alive']}")
        print(f"Command: {info['command']}")
        print(f"Stdout: {info['stdout']}")
        print(f"Stderr: {info['stderr']}")


def add_shared_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--label", default=DEFAULT_LABEL)
    parser.add_argument("--python-path")
    parser.add_argument("--market", choices=["stocks", "crypto", "both"], default="both")
    parser.add_argument("--symbols", help="Comma-separated symbols for targeted live runs.")
    parser.add_argument("--stock-intervals", default="15m,1h,2h,4h")
    parser.add_argument("--crypto-timeframes", default="15m,1h,2h,4h")
    parser.add_argument("--trigger-tf", default="15m")
    parser.add_argument("--trend-tf", default="1h")
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--report-limit", type=int, default=12)
    parser.add_argument("--retention-count", type=int, default=96)
    parser.add_argument("--health-check", dest="health_check", action="store_true", default=True)
    parser.add_argument("--no-health-check", dest="health_check", action="store_false")
    parser.add_argument("--health-app-url", default="http://127.0.0.1:8501")
    parser.add_argument("--health-chart-symbol", default="AAPL")
    parser.add_argument("--health-chart-timeframe", default="1h")
    parser.add_argument("--health-skip-chart-fetch", action="store_true")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install or control the live SMA launchd job.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Write and load the macOS LaunchAgent.")
    add_shared_options(install_parser)
    install_parser.add_argument("--no-load", dest="load", action="store_false")
    install_parser.set_defaults(load=True)

    status_parser = subparsers.add_parser("status", help="Show LaunchAgent status.")
    status_parser.add_argument("--label", default=DEFAULT_LABEL)

    uninstall_parser = subparsers.add_parser("uninstall", help="Unload and delete the LaunchAgent.")
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
    elif args.command == "uninstall":
        path = uninstall(args)
        print(f"Uninstalled: {path}")


if __name__ == "__main__":
    main()
