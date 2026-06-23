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
DEFAULT_LABEL = "com.roxy.autopilot"
DEFAULT_INTERVAL_SECONDS = 60


def venv_site_packages() -> Path:
    return BASE_DIR / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"


def launchd_python_path() -> Path:
    system_python = Path("/Library/Developer/CommandLineTools/usr/bin/python3")
    if system_python.exists():
        return system_python
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


def build_autopilot_args(*, python_path: str | Path, apply: bool = True) -> list[str | Path]:
    args: list[str | Path] = [Path(python_path), TOOLS_DIR / "roxy_autopilot.py"]
    if apply:
        args.append("--apply")
    return args


def build_shell_command(*, python_path: str | Path, apply: bool = True) -> str:
    autopilot_args = build_autopilot_args(python_path=python_path, apply=apply)
    return (
        f"cd {shlex.quote(str(BASE_DIR))} "
        "&& set -a "
        f"&& {env_source_command()} "
        "&& set +a "
        f"&& {pythonpath_export()} "
        f"&& exec {shell_join(autopilot_args)}"
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
            or "failed to load Autopilot LaunchAgent"
        )
        raise RuntimeError(message)


def install(args: argparse.Namespace) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    LAUNCHD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    sync_launchd_env()
    python_path = normalize_python_path(args.python_path) if args.python_path else launchd_python_path()
    command = build_shell_command(python_path=python_path, apply=args.apply)
    stdout_path = LAUNCHD_LOG_DIR / "roxy_autopilot.out"
    stderr_path = LAUNCHD_LOG_DIR / "roxy_autopilot.err"
    plist = build_plist(
        label=args.label,
        command=command,
        interval_seconds=args.interval_seconds,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        run_at_load=not args.no_run_at_load,
    )
    path = plist_path_for_label(args.label)
    if is_loaded(args.label):
        bootout(args.label)
    write_plist(path, plist)
    if not args.no_load:
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
    plist: dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as fh:
            plist = plistlib.load(fh)
    return {
        "label": label,
        "plist_path": str(path),
        "installed": path.exists(),
        "loaded": is_loaded(label),
        "interval_seconds": plist.get("StartInterval"),
        "run_at_load": plist.get("RunAtLoad"),
        "command": " ".join(plist.get("ProgramArguments", [])) if plist else "",
        "stdout_path": plist.get("StandardOutPath"),
        "stderr_path": plist.get("StandardErrorPath"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install or control the Roxy Autopilot LaunchAgent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Write and load the Autopilot LaunchAgent.")
    install_parser.add_argument("--label", default=DEFAULT_LABEL)
    install_parser.add_argument("--python-path", default="")
    install_parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    install_parser.add_argument("--apply", action=argparse.BooleanOptionalAction, default=True)
    install_parser.add_argument("--no-load", action="store_true")
    install_parser.add_argument("--no-run-at-load", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show Autopilot LaunchAgent status.")
    status_parser.add_argument("--label", default=DEFAULT_LABEL)

    uninstall_parser = subparsers.add_parser("uninstall", help="Unload and delete the Autopilot LaunchAgent.")
    uninstall_parser.add_argument("--label", default=DEFAULT_LABEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "install":
        path = install(args)
        print(f"Installed: {path}")
        print(status(args.label))
    elif args.command == "status":
        print(status(args.label))
    elif args.command == "uninstall":
        path = uninstall(args)
        print(f"Uninstalled: {path}")


if __name__ == "__main__":
    main()
