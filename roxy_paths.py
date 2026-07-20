from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIRECTORY_ENV = {
    "output": "ROXY_OUTPUT_DIR",
    "alerts": "ROXY_ALERTS_DIR",
    "data": "ROXY_DATA_DIR",
    "db": "ROXY_DB_DIR",
}


def _base_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


def project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    parts = path.parts
    if parts:
        configured = os.getenv(RUNTIME_DIRECTORY_ENV.get(parts[0], ""))
        if configured:
            return _base_path(configured).joinpath(*parts[1:])
    return BASE_DIR / path


def configured_dir(env_name: str, default: str | Path) -> Path:
    value = os.getenv(env_name)
    return _base_path(value if value else default)


def output_dir() -> Path:
    return configured_dir("ROXY_OUTPUT_DIR", "output")


def alerts_dir() -> Path:
    return configured_dir("ROXY_ALERTS_DIR", "alerts")


def data_dir() -> Path:
    return configured_dir("ROXY_DATA_DIR", "data")


def db_dir() -> Path:
    return configured_dir("ROXY_DB_DIR", "db")
