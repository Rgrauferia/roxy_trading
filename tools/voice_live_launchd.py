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
LOG_DIR = BASE_DIR / "logs"
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "RoxyTrading"
LAUNCHD_ENV_PATH = APP_SUPPORT_DIR / ".env"
DEFAULT_LABEL = "com.roxy.voice-live"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8010


def configured_host() -> str:
    return str(os.getenv("ROXY_VOICE_BIND_HOST") or DEFAULT_HOST).strip() or DEFAULT_HOST


def configured_port() -> int:
    try:
        return int(str(os.getenv("ROXY_VOICE_PORT") or DEFAULT_PORT).strip())
    except ValueError:
        return DEFAULT_PORT


def venv_site_packages() -> Path:
    return BASE_DIR / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"


def default_python_path() -> Path:
    candidate = BASE_DIR / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def normalize_python_path(value: str | Path | None) -> Path:
    if not value:
        return default_python_path()
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def shell_join(args: list[str | Path]) -> str:
    return " ".join(shlex.quote(str(arg)) for arg in args)


def env_source_command() -> str:
    path = shlex.quote(str(LAUNCHD_ENV_PATH))
    return f"if [ -f {path} ]; then source {path}; fi"


def pythonpath_export() -> str:
    value = ":".join(shlex.quote(str(path)) for path in (BASE_DIR, venv_site_packages()))
    return f"export PYTHONPATH={value}${{PYTHONPATH:+:$PYTHONPATH}}"


def sync_launchd_env() -> None:
    source = BASE_DIR / ".env"
    if not source.exists():
        return
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, LAUNCHD_ENV_PATH)
    LAUNCHD_ENV_PATH.chmod(0o600)


def build_server_arguments(
    *,
    python_path: str | Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> list[str]:
    return [
        str(python_path),
        "-m",
        "uvicorn",
        "tools.voice_service:app",
        "--host",
        str(host),
        "--port",
        str(int(port)),
    ]


def build_shell_command(
    *,
    python_path: str | Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> str:
    server = build_server_arguments(python_path=python_path, host=host, port=port)
    return (
        f"cd {shlex.quote(str(BASE_DIR))} "
        "&& set -a "
        f"&& {env_source_command()} "
        "&& set +a "
        f"&& {pythonpath_export()} "
        f"&& exec {shell_join(server)}"
    )


def build_plist(
    *,
    label: str = DEFAULT_LABEL,
    python_path: str | Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    stdout_path: str | Path | None = None,
    stderr_path: str | Path | None = None,
    run_at_load: bool = True,
    keep_alive: bool = True,
) -> dict[str, Any]:
    command = build_shell_command(python_path=python_path, host=host, port=port)
    return {
        "Label": label,
        "ProgramArguments": ["/bin/bash", "-lc", command],
        "RunAtLoad": run_at_load,
        "KeepAlive": keep_alive,
        "WorkingDirectory": str(Path.home()),
        "StandardOutPath": str(stdout_path or LOG_DIR / "roxy_live.log"),
        "StandardErrorPath": str(stderr_path or LOG_DIR / "roxy_live.err.log"),
    }


def launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def plist_path_for_label(label: str = DEFAULT_LABEL) -> Path:
    return launch_agents_dir() / f"{label}.plist"


def write_plist(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=False)


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
    if result.returncode == 0:
        return
    fallback = run_launchctl(["load", str(path)])
    if fallback.returncode != 0:
        message = result.stderr.strip() or fallback.stderr.strip() or "failed to load voice LaunchAgent"
        raise RuntimeError(message)


def read_plist(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return plistlib.load(handle)


def command_from_plist(payload: dict[str, Any]) -> str:
    args = [str(item) for item in payload.get("ProgramArguments", [])]
    return args[2] if len(args) >= 3 and args[:2] == ["/bin/bash", "-lc"] else shell_join(args)


def server_args_from_plist(payload: dict[str, Any]) -> list[str]:
    command = command_from_plist(payload)
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def option_value(args: list[str], option: str) -> str | None:
    if option not in args:
        return None
    index = args.index(option)
    return args[index + 1] if index + 1 < len(args) else None


def status(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    payload = read_plist(label)
    command = command_from_plist(payload)
    args = server_args_from_plist(payload)
    port_value = option_value(args, "--port")
    try:
        port = int(port_value) if port_value is not None else None
    except ValueError:
        port = None
    return {
        "label": label,
        "path": str(path),
        "plist": str(path),
        "installed": path.exists(),
        "loaded": is_loaded(label),
        "command": command,
        "host": option_value(args, "--host") or "",
        "port": port,
        "environment_managed": str(LAUNCHD_ENV_PATH) in command and "set -a" in command and "set +a" in command,
        "pythonpath_managed": "export PYTHONPATH=" in command,
    }


def install(args: argparse.Namespace) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    sync_launchd_env()
    path = plist_path_for_label(args.label)
    write_plist(
        path,
        build_plist(
            label=args.label,
            python_path=normalize_python_path(args.python_path),
            host=args.host,
            port=args.port,
        ),
    )
    if args.load:
        if is_loaded(args.label):
            bootout(args.label)
        bootstrap(path)
    return path


def uninstall(args: argparse.Namespace) -> Path:
    path = plist_path_for_label(args.label)
    if is_loaded(args.label):
        bootout(args.label)
    path.unlink(missing_ok=True)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install and manage Roxy's local voice LaunchAgent.")
    parser.add_argument("action", choices=("install", "status", "uninstall"), nargs="?", default="status")
    parser.add_argument("--label", default=DEFAULT_LABEL)
    parser.add_argument("--python-path")
    parser.add_argument("--host", default=configured_host())
    parser.add_argument("--port", type=int, default=configured_port())
    parser.add_argument("--no-load", dest="load", action="store_false", default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.action == "install":
        print(install(args))
    elif args.action == "uninstall":
        print(uninstall(args))
    else:
        print(status(args.label))


if __name__ == "__main__":
    main()
