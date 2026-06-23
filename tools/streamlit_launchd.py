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
LAUNCHD_LOG_DIR = Path.home() / "Library" / "Logs" / "RoxyTrading"
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "RoxyTrading"
LAUNCHD_ENV_PATH = APP_SUPPORT_DIR / ".env"
DEFAULT_LABEL = "com.roxy.streamlit"
DEFAULT_PORT = 3000
DEFAULT_ADDRESS = "0.0.0.0"


def venv_site_packages() -> Path:
    return BASE_DIR / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"


def launchd_python_path() -> Path:
    return default_python_path()


def default_python_path() -> Path:
    venv_python = BASE_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def normalize_python_path(value: str | Path | None) -> Path:
    if not value:
        return default_python_path()
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def build_program_arguments(
    *,
    python_path: str | Path,
    address: str = DEFAULT_ADDRESS,
    port: int = DEFAULT_PORT,
) -> list[str]:
    return [
        str(python_path),
        "-m",
        "streamlit",
        "run",
        str(BASE_DIR / "streamlit_app.py"),
        "--server.address",
        str(address),
        "--server.port",
        str(int(port)),
        "--server.headless",
        "true",
        "--server.runOnSave",
        "true",
        "--server.fileWatcherType",
        "auto",
        "--browser.gatherUsageStats",
        "false",
    ]


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


def build_shell_command(
    *,
    python_path: str | Path,
    address: str = DEFAULT_ADDRESS,
    port: int = DEFAULT_PORT,
) -> str:
    streamlit_args = build_program_arguments(python_path=python_path, address=address, port=port)
    return (
        f"cd {shlex.quote(str(BASE_DIR))} "
        "&& set -a "
        f"&& {env_source_command()} "
        "&& set +a "
        f"&& {pythonpath_export()} "
        f"&& exec {shell_join(streamlit_args)}"
    )


def build_plist(
    *,
    label: str = DEFAULT_LABEL,
    python_path: str | Path,
    address: str = DEFAULT_ADDRESS,
    port: int = DEFAULT_PORT,
    stdout_path: str | Path | None = None,
    stderr_path: str | Path | None = None,
    run_at_load: bool = True,
    keep_alive: bool = True,
) -> dict[str, Any]:
    command = build_shell_command(python_path=python_path, address=address, port=port)
    return {
        "Label": label,
        "ProgramArguments": ["/bin/bash", "-lc", command],
        "RunAtLoad": run_at_load,
        "KeepAlive": keep_alive,
        "WorkingDirectory": str(Path.home()),
        "StandardOutPath": str(stdout_path or LOG_DIR / "streamlit_launchd.out"),
        "StandardErrorPath": str(stderr_path or LOG_DIR / "streamlit_launchd.err"),
    }


def launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def plist_path_for_label(label: str = DEFAULT_LABEL) -> Path:
    return launch_agents_dir() / f"{label}.plist"


def write_plist(path: Path, plist: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(plist, fh, sort_keys=False)


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
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or fallback.stderr.strip()
            or fallback.stdout.strip()
            or "failed to load Streamlit LaunchAgent"
        )
        raise RuntimeError(message)


def install(args: argparse.Namespace) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    LAUNCHD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    sync_launchd_env()
    python_path = normalize_python_path(args.python_path) if args.python_path else launchd_python_path()
    plist = build_plist(
        label=args.label,
        python_path=python_path,
        address=args.address,
        port=args.port,
        stdout_path=LAUNCHD_LOG_DIR / "streamlit_launchd.out",
        stderr_path=LAUNCHD_LOG_DIR / "streamlit_launchd.err",
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


def read_plist(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return plistlib.load(fh)


def streamlit_address_from_plist(plist: dict[str, Any]) -> str:
    args = streamlit_args_from_plist(plist)
    if "--server.address" in args:
        idx = args.index("--server.address")
        if idx + 1 < len(args):
            return args[idx + 1]
    return "-"


def streamlit_port_from_plist(plist: dict[str, Any]) -> int | None:
    args = streamlit_args_from_plist(plist)
    if "--server.port" in args:
        idx = args.index("--server.port")
        if idx + 1 < len(args):
            try:
                return int(args[idx + 1])
            except ValueError:
                return None
    return None


def streamlit_args_from_plist(plist: dict[str, Any]) -> list[str]:
    args = [str(item) for item in plist.get("ProgramArguments", [])]
    if len(args) >= 3 and args[:2] == ["/bin/bash", "-lc"]:
        try:
            return shlex.split(args[2])
        except ValueError:
            return args
    return args


def status(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    path = plist_path_for_label(label)
    plist = read_plist(label)
    address = streamlit_address_from_plist(plist)
    port = streamlit_port_from_plist(plist)
    program = plist.get("ProgramArguments", [])
    command = ""
    if len(program) >= 3 and program[:2] == ["/bin/bash", "-lc"]:
        command = str(program[2])
    elif program:
        command = " ".join(str(item) for item in program)
    return {
        "label": label,
        "plist": str(path),
        "installed": path.exists(),
        "loaded": is_loaded(label),
        "keep_alive": bool(plist.get("KeepAlive")),
        "address": address,
        "port": port,
        "lan_ready": address in {"0.0.0.0", "::", "*"},
        "program": program,
        "command": command,
    }


def print_status(label: str = DEFAULT_LABEL) -> None:
    info = status(label)
    print(f"Label: {info['label']}")
    print(f"Plist: {info['plist']}")
    print(f"Installed: {'yes' if info['installed'] else 'no'}")
    print(f"Loaded: {'yes' if info['loaded'] else 'no'}")
    print(f"Address: {info['address']}")
    print(f"Port: {info['port'] or '-'}")
    print(f"LAN ready: {'yes' if info['lan_ready'] else 'no'}")
    if info["program"]:
        print("Command: " + " ".join(str(item) for item in info["program"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install or control the Roxy Streamlit LaunchAgent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Write and load the Streamlit macOS LaunchAgent.")
    install_parser.add_argument("--label", default=DEFAULT_LABEL)
    install_parser.add_argument("--python-path")
    install_parser.add_argument("--address", default=DEFAULT_ADDRESS)
    install_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    install_parser.add_argument("--no-load", dest="load", action="store_false")
    install_parser.set_defaults(load=True)

    status_parser = subparsers.add_parser("status", help="Show Streamlit LaunchAgent status.")
    status_parser.add_argument("--label", default=DEFAULT_LABEL)

    uninstall_parser = subparsers.add_parser("uninstall", help="Unload and delete the Streamlit LaunchAgent.")
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
