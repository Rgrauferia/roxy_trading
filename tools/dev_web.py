from __future__ import annotations

import argparse
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_PORT = 3000
DEFAULT_HOST = "localhost"


def health_url(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> str:
    return f"http://{host}:{int(port)}/_stcore/health"


def app_url(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> str:
    return f"http://{host}:{int(port)}"


def streamlit_health_ok(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, *, timeout: float = 1.5) -> bool:
    try:
        with urlopen(health_url(port, host), timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="ignore").strip().lower()
            return int(getattr(response, "status", 0) or 0) == 200 and body == "ok"
    except (OSError, URLError, TimeoutError, ValueError):
        return False


def wait_for_streamlit(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, *, timeout_seconds: float = 30.0) -> bool:
    deadline = time.time() + max(1.0, float(timeout_seconds))
    while time.time() <= deadline:
        if streamlit_health_ok(port, host):
            return True
        time.sleep(1.0)
    return False


def ensure_dev_web(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> int:
    if streamlit_health_ok(port, host):
        print(f"Roxy Trading dev web already running: {app_url(port, host)}")
        return 0

    command = [
        sys.executable,
        "tools/streamlit_launchd.py",
        "install",
        "--port",
        str(int(port)),
    ]
    result = subprocess.run(command, text=True, check=False)
    if result.returncode != 0:
        return result.returncode
    if not wait_for_streamlit(port, host):
        print(f"Roxy Trading dev web did not become healthy on {app_url(port, host)}", file=sys.stderr)
        return 1
    print(f"Roxy Trading dev web: {app_url(port, host)}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure the stable Roxy Trading development web server is running.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(ensure_dev_web(port=args.port, host=args.host))


if __name__ == "__main__":
    main()
