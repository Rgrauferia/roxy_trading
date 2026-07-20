from __future__ import annotations

import argparse
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = Path.home() / "Library" / "Logs" / "RoxyTrading"
APP_ENV = Path.home() / "Library" / "Application Support" / "RoxyTrading" / ".env"
DEFAULT_LABEL = "com.roxy.price-alert-monitor"
DEFAULT_INTERVAL_SECONDS = 60


def default_python_path() -> Path:
    candidate = BASE_DIR / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def plist_path_for_label(label: str = DEFAULT_LABEL) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def launchctl_target() -> str:
    return f"gui/{os.getuid()}"


def run_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], text=True, capture_output=True, check=False)


def is_loaded(label: str = DEFAULT_LABEL) -> bool:
    return run_launchctl(["print", f"{launchctl_target()}/{label}"]).returncode == 0


def bootout(label: str = DEFAULT_LABEL) -> None:
    run_launchctl(["bootout", f"{launchctl_target()}/{label}"])


def bootstrap(path: Path) -> None:
    result = run_launchctl(["bootstrap", launchctl_target(), str(path)])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "launchctl bootstrap failed")


def build_shell_command(python_path: str | Path) -> str:
    python = shlex.quote(str(Path(python_path).expanduser()))
    base = shlex.quote(str(BASE_DIR))
    env_path = shlex.quote(str(APP_ENV))
    site = BASE_DIR / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    pythonpath = ":".join(shlex.quote(str(path)) for path in (BASE_DIR, site))
    script = shlex.quote(str(BASE_DIR / "tools" / "price_alert_monitor.py"))
    return (
        f"cd {base} && set -a && if [ -f {env_path} ]; then source {env_path}; fi && set +a "
        f"&& export PYTHONPATH={pythonpath}${{PYTHONPATH:+:$PYTHONPATH}} "
        f"&& exec {python} {script} --no-fail"
    )


def build_plist(
    *,
    label: str = DEFAULT_LABEL,
    python_path: str | Path | None = None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> dict[str, Any]:
    return {
        "Label": label,
        "ProgramArguments": ["/bin/bash", "-lc", build_shell_command(python_path or default_python_path())],
        "RunAtLoad": True,
        "StartInterval": max(30, int(interval_seconds)),
        "ThrottleInterval": 30,
        "WorkingDirectory": str(BASE_DIR),
        "StandardOutPath": str(LOG_DIR / "price_alert_monitor.out"),
        "StandardErrorPath": str(LOG_DIR / "price_alert_monitor.err"),
    }


def read_plist(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    if not path.exists():
        return {}
    with path.open("rb") as stream:
        return plistlib.load(stream)


def status(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    plist = read_plist(label)
    program = plist.get("ProgramArguments") if isinstance(plist.get("ProgramArguments"), list) else []
    command = str(program[2]) if len(program) >= 3 and program[:2] == ["/bin/bash", "-lc"] else ""
    return {
        "label": label,
        "path": str(path),
        "plist": str(path),
        "installed": path.exists(),
        "loaded": is_loaded(label),
        "interval_seconds": int(plist.get("StartInterval") or 0),
        "command": command,
        "program": program,
    }


def install(args: argparse.Namespace) -> Path:
    label = str(getattr(args, "label", DEFAULT_LABEL) or DEFAULT_LABEL)
    path = plist_path_for_label(label)
    path.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plist = build_plist(
        label=label,
        python_path=getattr(args, "python_path", None) or default_python_path(),
        interval_seconds=int(getattr(args, "interval_seconds", DEFAULT_INTERVAL_SECONDS)),
    )
    with path.open("wb") as stream:
        plistlib.dump(plist, stream, sort_keys=False)
    if bool(getattr(args, "load", True)):
        if is_loaded(label):
            bootout(label)
        bootstrap(path)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install/check the Roxy background price-alert monitor.")
    parser.add_argument("command", choices=("install", "status"))
    parser.add_argument("--label", default=DEFAULT_LABEL)
    parser.add_argument("--python-path")
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--no-load", dest="load", action="store_false")
    parser.set_defaults(load=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "install":
        print(f"Installed: {install(args)}")
    print(status(args.label))


if __name__ == "__main__":
    main()
