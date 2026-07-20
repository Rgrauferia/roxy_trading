from __future__ import annotations

import argparse
import os
import plistlib
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = Path.home() / "Library" / "Logs" / "RoxyTrading"
DEFAULT_LABEL = "com.roxy.macro-calendar"
DEFAULT_INTERVAL_SECONDS = 21_600


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


def build_shell_command(python_path: str | Path) -> str:
    python = shlex.quote(str(Path(python_path).expanduser()))
    base = shlex.quote(str(BASE_DIR))
    script = shlex.quote(str(BASE_DIR / "tools" / "macro_calendar_sync.py"))
    return f"cd {base} && export PYTHONPATH={base}${{PYTHONPATH:+:$PYTHONPATH}} && exec {python} {script} --no-fail"


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
        "StartInterval": max(3_600, int(interval_seconds)),
        "ThrottleInterval": 60,
        "WorkingDirectory": str(BASE_DIR),
        "StandardOutPath": str(LOG_DIR / "macro_calendar.out"),
        "StandardErrorPath": str(LOG_DIR / "macro_calendar.err"),
    }


def read_plist(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    if not path.is_file():
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
        "installed": path.is_file(),
        "loaded": is_loaded(label),
        "interval_seconds": int(plist.get("StartInterval") or 0),
        "command": command,
        "program": program,
    }


def atomic_write_plist(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            plistlib.dump(payload, stream, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def install(args: argparse.Namespace) -> Path:
    label = str(getattr(args, "label", DEFAULT_LABEL) or DEFAULT_LABEL)
    path = plist_path_for_label(label)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_plist(
        path,
        build_plist(
            label=label,
            python_path=getattr(args, "python_path", None) or default_python_path(),
            interval_seconds=int(getattr(args, "interval_seconds", DEFAULT_INTERVAL_SECONDS)),
        ),
    )
    if bool(getattr(args, "load", True)):
        if is_loaded(label):
            run_launchctl(["bootout", f"{launchctl_target()}/{label}"])
        result = run_launchctl(["bootstrap", launchctl_target(), str(path)])
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "launchctl bootstrap failed")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install/check the official Roxy macro-calendar sync.")
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
