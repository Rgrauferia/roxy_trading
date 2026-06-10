from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Mapping

from platform_execution import BROKER_ENV_KEYS, LIVE_EXECUTION_FLAG, live_execution_requested
from platform_router import PLATFORM_PROFILES, safe_text

try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None


SECRET_PREFIX = "broker"
DB_PATH = os.path.join(os.getcwd(), "db", "roxy.db")
FERNET_KEY_ENV = "FERNET_KEY"
FERNET_KEY_FILE_ENV = "FERNET_KEY_FILE"
DEFAULT_FERNET_KEY_FILE = os.path.join(os.getcwd(), "run", "roxy_fernet.key")


def _get_fernet_key() -> bytes | None:
    key = os.getenv(FERNET_KEY_ENV)
    if key:
        return key.encode()
    key_file = os.getenv(FERNET_KEY_FILE_ENV)
    if key_file:
        try:
            with open(key_file, "rb") as handle:
                return handle.read().strip()
        except Exception:
            return None
    if os.path.exists(DEFAULT_FERNET_KEY_FILE):
        try:
            with open(DEFAULT_FERNET_KEY_FILE, "rb") as handle:
                return handle.read().strip()
        except Exception:
            return None
    return None


def _get_fernet():
    if Fernet is None:
        return None
    key = _get_fernet_key()
    if not key:
        return None
    try:
        return Fernet(key)
    except Exception:
        return None


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def ensure_tables() -> None:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS secrets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE,
              provider TEXT,
              encrypted_value BLOB NOT NULL,
              metadata TEXT,
              version INTEGER NOT NULL DEFAULT 1,
              created_by TEXT,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS secret_revisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              secret_id INTEGER NOT NULL,
              encrypted_value BLOB NOT NULL,
              version INTEGER NOT NULL,
              rotated_by TEXT,
              rotated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              reason TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS secret_audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              secret_id INTEGER,
              actor TEXT,
              action TEXT,
              details TEXT,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _encrypt(value: str) -> bytes:
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("FERNET not configured")
    return fernet.encrypt(value.encode())


def initialize_local_vault_key(*, overwrite: bool = False) -> dict[str, Any]:
    if Fernet is None:
        raise RuntimeError("cryptography is not installed")
    path = DEFAULT_FERNET_KEY_FILE
    existed = os.path.exists(path)
    if existed and not overwrite:
        return {"created": False, "path": path, "existed": True, "mode": oct(os.stat(path).st_mode & 0o777)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    key = Fernet.generate_key()
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, key + b"\n")
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
    return {"created": True, "path": path, "existed": existed, "mode": oct(os.stat(path).st_mode & 0o777)}


def encryption_status() -> dict[str, Any]:
    enabled = _get_fernet() is not None
    source = "none"
    if os.getenv(FERNET_KEY_ENV):
        source = FERNET_KEY_ENV
    elif os.getenv(FERNET_KEY_FILE_ENV):
        source = FERNET_KEY_FILE_ENV
    elif os.path.exists(DEFAULT_FERNET_KEY_FILE):
        source = "local_key_file"
    return {
        "enabled": enabled,
        "key_env": FERNET_KEY_ENV,
        "key_file_env": FERNET_KEY_FILE_ENV,
        "default_key_file": DEFAULT_FERNET_KEY_FILE,
        "source": source,
        "store": DB_PATH,
    }


def secret_name(platform_id: str, key_name: str) -> str:
    return f"{SECRET_PREFIX}.{platform_id}.{key_name}"


def platform_for_secret_name(name: str) -> tuple[str, str] | None:
    parts = safe_text(name).split(".", 2)
    if len(parts) != 3 or parts[0] != SECRET_PREFIX:
        return None
    return parts[1], parts[2]


def _env_has(env: Mapping[str, str] | None, key_name: str) -> bool:
    source = env if env is not None else os.environ
    return bool(safe_text(source.get(key_name)))


def saved_secret_names() -> set[str]:
    ensure_tables()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM secrets WHERE name LIKE ?", (f"{SECRET_PREFIX}.%.%",))
        return {str(row[0]) for row in cur.fetchall()}
    finally:
        conn.close()


def platform_credential_status(platform_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    profile = PLATFORM_PROFILES.get(platform_id, PLATFORM_PROFILES["schwab"])
    required = BROKER_ENV_KEYS.get(platform_id, ())
    saved = saved_secret_names()
    key_rows = []
    present_keys = []
    missing_keys = []
    for key_name in required:
        if _env_has(env, key_name):
            source = "env"
        elif secret_name(platform_id, key_name) in saved:
            source = "vault"
        else:
            source = "missing"
        if source == "missing":
            missing_keys.append(key_name)
        else:
            present_keys.append(key_name)
        key_rows.append({"key": key_name, "source": source, "configured": source != "missing"})

    configured = bool(required) and not missing_keys
    live_enabled = live_execution_requested(env)
    if not configured:
        mode = "NEEDS_CREDENTIALS"
    elif not live_enabled:
        mode = "PREVIEW_ONLY"
    else:
        mode = "LIVE_ARMED"
    return {
        "platform_id": platform_id,
        "platform": profile["name"],
        "required_keys": list(required),
        "present_keys": present_keys,
        "missing_keys": missing_keys,
        "key_rows": key_rows,
        "configured": configured,
        "live_enabled": live_enabled,
        "mode": mode,
    }


def credential_table_rows(env: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    rows = []
    for platform_id in PLATFORM_PROFILES:
        status = platform_credential_status(platform_id, env=env)
        rows.append(
            {
                "platform_id": platform_id,
                "platform": status["platform"],
                "mode": status["mode"],
                "configured": status["configured"],
                "live_enabled": status["live_enabled"],
                "missing": ", ".join(status["missing_keys"]) if status["missing_keys"] else "-",
                "sources": ", ".join(f"{row['key']}:{row['source']}" for row in status["key_rows"]),
            }
        )
    return rows


def save_platform_credential(platform_id: str, key_name: str, value: str, *, actor: str = "streamlit_ui") -> dict[str, Any]:
    if key_name not in BROKER_ENV_KEYS.get(platform_id, ()):
        raise ValueError(f"{key_name} is not a supported credential for {platform_id}")
    if not safe_text(value):
        raise ValueError("Credential value is empty")
    if not encryption_status()["enabled"]:
        raise RuntimeError("FERNET_KEY or FERNET_KEY_FILE must be configured before saving broker credentials")

    ensure_tables()
    encrypted_value = _encrypt(value)
    name = secret_name(platform_id, key_name)
    metadata = {
        "platform_id": platform_id,
        "key_name": key_name,
        "scope": "broker_api",
    }
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, version FROM secrets WHERE name=?", (name,))
        row = cur.fetchone()
        if row:
            secret_id, version = row
            new_version = int(version) + 1
            cur.execute(
                "UPDATE secrets SET encrypted_value=?, provider=?, metadata=?, version=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (encrypted_value, platform_id, json.dumps(metadata), new_version, secret_id),
            )
            cur.execute(
                "INSERT INTO secret_revisions (secret_id, encrypted_value, version, rotated_by, reason) VALUES (?, ?, ?, ?, ?)",
                (secret_id, encrypted_value, new_version, actor, "platform credential updated"),
            )
            action = "rotate"
            version = new_version
        else:
            cur.execute(
                "INSERT INTO secrets (name, provider, encrypted_value, metadata, created_by, version) VALUES (?, ?, ?, ?, ?, 1)",
                (name, platform_id, encrypted_value, json.dumps(metadata), actor),
            )
            secret_id = cur.lastrowid
            cur.execute(
                "INSERT INTO secret_revisions (secret_id, encrypted_value, version, rotated_by, reason) VALUES (?, ?, ?, ?, ?)",
                (secret_id, encrypted_value, 1, actor, "platform credential created"),
            )
            action = "create"
            version = 1
        cur.execute(
            "INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, ?, ?)",
            (secret_id, actor, f"platform_{action}", json.dumps({"name": name, "platform_id": platform_id, "key_name": key_name})),
        )
        conn.commit()
        return {"name": name, "platform_id": platform_id, "key_name": key_name, "version": version, "action": action}
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_platform_credentials(platform_id: str, values: Mapping[str, str], *, actor: str = "streamlit_ui") -> list[dict[str, Any]]:
    results = []
    for key_name, value in values.items():
        if safe_text(value):
            results.append(save_platform_credential(platform_id, key_name, value, actor=actor))
    return results


__all__ = [
    "SECRET_PREFIX",
    "credential_table_rows",
    "encryption_status",
    "initialize_local_vault_key",
    "platform_credential_status",
    "platform_for_secret_name",
    "save_platform_credential",
    "save_platform_credentials",
    "saved_secret_names",
    "secret_name",
]
