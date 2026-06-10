from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


def configured_dir(env_name: str, default: str | Path) -> Path:
    value = os.getenv(env_name)
    return project_path(value) if value else project_path(default)


def output_dir() -> Path:
    return configured_dir("ROXY_OUTPUT_DIR", "output")


def alerts_dir() -> Path:
    return configured_dir("ROXY_ALERTS_DIR", "alerts")


def data_dir() -> Path:
    return configured_dir("ROXY_DATA_DIR", "data")


def db_dir() -> Path:
    return configured_dir("ROXY_DB_DIR", "db")
