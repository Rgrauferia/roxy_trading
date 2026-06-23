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
DEFAULT_LABEL = "com.roxy.output_maintenance"
DEFAULT_HOUR = 3
DEFAULT_MINUTE = 10


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


def build_maintenance_args(
    *,
    python_path: str | Path,
    dry_run: bool = False,
    enable_local_cache_cleanup: bool = True,
) -> list[str | Path]:
    args: list[str | Path] = [
        Path(python_path),
        TOOLS_DIR / "output_maintenance.py",
    ]
    if dry_run:
        args.append("--dry-run")
    if enable_local_cache_cleanup:
        args.append("--enable-local-cache-cleanup")
    return args


def build_shell_command(
    *,
    python_path: str | Path,
    dry_run: bool = False,
    enable_local_cache_cleanup: bool = True,
) -> str:
    maintenance_args = build_maintenance_args(
        python_path=python_path,
        dry_run=dry_run,
        enable_local_cache_cleanup=enable_local_cache_cleanup,
    )
    return (
        f"cd {shlex.quote(str(BASE_DIR))} "
        "&& set -a "
        f"&& {env_source_command()} "
        "&& set +a "
        f"&& {pythonpath_export()} "
        f"&& exec {shell_join(maintenance_args)}"
    )


def build_plist(
    *,
    label: str,
    command: str,
    hour: int,
    minute: int,
    stdout_path: str | Path,
    stderr_path: str | Path,
    run_at_load: bool,
) -> dict[str, Any]:
    return {
        "Label": label,
        "ProgramArguments": ["/bin/bash", "-lc", command],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
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
            or "failed to load LaunchAgent"
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
        dry_run=args.dry_run,
        enable_local_cache_cleanup=args.enable_local_cache_cleanup,
    )
    plist = build_plist(
        label=args.label,
        command=command,
        hour=args.hour,
        minute=args.minute,
        stdout_path=LAUNCHD_LOG_DIR / "output_maintenance.out",
        stderr_path=LAUNCHD_LOG_DIR / "output_maintenance.err",
        run_at_load=args.run_at_load,
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
        dry_run=args.dry_run,
        enable_local_cache_cleanup=args.enable_local_cache_cleanup,
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
        "schedule": {},
        "command": "",
        "stdout": "-",
        "stderr": "-",
    }
    if path.exists():
        with path.open("rb") as fh:
            plist = plistlib.load(fh)
        info.update(
            {
                "schedule": plist.get("StartCalendarInterval", {}),
                "command": " ".join(plist.get("ProgramArguments", [])),
                "stdout": str(plist.get("StandardOutPath", "-")),
                "stderr": str(plist.get("StandardErrorPath", "-")),
            }
        )
    return info


def print_status(label: str) -> None:
    info = status(label)
    schedule = dict(info.get("schedule") or {})
    print(f"Label: {label}")
    print(f"Plist: {info['path']}")
    print(f"Installed: {'yes' if info['installed'] else 'no'}")
    print(f"Loaded: {'yes' if info['loaded'] else 'no'}")
    if schedule:
        print(f"Schedule: {schedule.get('Hour', '-')!s}:{int(schedule.get('Minute', 0)):02d} local time")
    if info["command"]:
        print(f"Command: {info['command']}")
        print(f"Stdout: {info['stdout']}")
        print(f"Stderr: {info['stderr']}")


def add_shared_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--label", default=DEFAULT_LABEL)
    parser.add_argument("--python-path")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--enable-local-cache-cleanup",
        dest="enable_local_cache_cleanup",
        action="store_true",
        default=True,
        help="Enable guarded cleanup for SAFE_CACHE_REVIEW_READY local cache entries.",
    )
    parser.add_argument(
        "--no-enable-local-cache-cleanup",
        dest="enable_local_cache_cleanup",
        action="store_false",
        help="Keep local cache cleanup in preview-only mode.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install or control the output maintenance LaunchAgent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Write and load the macOS LaunchAgent.")
    add_shared_options(install_parser)
    install_parser.add_argument("--hour", type=int, default=DEFAULT_HOUR)
    install_parser.add_argument("--minute", type=int, default=DEFAULT_MINUTE)
    install_parser.add_argument("--run-at-load", action="store_true")
    install_parser.add_argument("--no-load", dest="load", action="store_false")
    install_parser.add_argument("--run-now", action="store_true")
    install_parser.set_defaults(load=True)

    status_parser = subparsers.add_parser("status", help="Show LaunchAgent status.")
    status_parser.add_argument("--label", default=DEFAULT_LABEL)

    run_now_parser = subparsers.add_parser("run-now", help="Run output maintenance immediately.")
    add_shared_options(run_now_parser)

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
    elif args.command == "run-now":
        raise SystemExit(run_now(args))
    elif args.command == "uninstall":
        path = uninstall(args)
        print(f"Uninstalled: {path}")


if __name__ == "__main__":
    main()
