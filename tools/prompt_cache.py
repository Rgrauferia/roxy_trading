"""Simple persistent prompt cache backed by SQLite (`db/roxy.db`).

Usage:
- `get_cached(prompt, ttl_seconds)` returns cached response or None
- `set_cached(prompt, response, model, ttl_seconds)` stores a response

Cache key is SHA256(prompt) to avoid storing huge prompts as keys.
"""
from __future__ import annotations

import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from roxy_time import utc_now_naive

DB_PATH = os.path.join(os.getcwd(), "db", "roxy.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _pkey(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


def get_cached(prompt: str) -> Optional[str]:
    pkey = _pkey(prompt)
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT response, expires_at FROM prompt_cache WHERE pkey=?", (pkey,))
        r = cur.fetchone()
        if not r:
            return None
        response, expires_at = r
        if expires_at:
            try:
                if expires_at <= utc_now_naive().isoformat():
                    # expired — delete
                    cur.execute("DELETE FROM prompt_cache WHERE pkey=?", (pkey,))
                    conn.commit()
                    return None
            except Exception:
                pass
        return response
    finally:
        conn.close()


def set_cached(prompt: str, response: str, model: Optional[str] = None, ttl_seconds: int = 3600) -> None:
    pkey = _pkey(prompt)
    expires_at = (utc_now_naive() + timedelta(seconds=ttl_seconds)).isoformat() if ttl_seconds else None
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO prompt_cache (pkey, prompt, response, model, created_at, expires_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (pkey, prompt, response, model, expires_at),
        )
        conn.commit()
    finally:
        conn.close()
