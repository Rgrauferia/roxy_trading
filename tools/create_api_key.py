"""Utility: create an API key in the local DB with given scopes.

Usage (run from repo root):
    python -m tools.create_api_key --name auto-svc --owner ops --scopes auto:execute

This script uses the same hashing and storage conventions as the
`tools.secrets_service` module so keys created here will be accepted by
the API auth dependency.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime, timedelta

from roxy_time import utc_now_naive

try:
    from tools import secrets_service
except Exception:
    secrets_service = None


DB_PATH = os.path.join(os.getcwd(), "db", "roxy.db")


def _conn(path: str = None):
    return sqlite3.connect(path or DB_PATH)


def create_api_key(name: str, owner: str, scopes: str, ttl_days: int = 365) -> str:
    """Create an API key and return the plaintext value.

    The function mirrors the behavior of the secrets service API: it generates
    a random token, hashes it with the internal master key, and stores the
    hash alongside metadata in the `api_keys` table.
    """
    if secrets_service is None:
        raise RuntimeError("tools.secrets_service not importable; run inside the repo with dependencies installed")

    plain = secrets_service._generate_plain_api_key()
    h = secrets_service._hash_key(plain)
    expires_at = (utc_now_naive() + timedelta(days=ttl_days)).isoformat()

    conn = _conn()
    try:
        cur = conn.cursor()
        # ensure tables exist
        try:
            secrets_service.ensure_tables()
        except Exception:
            pass
        cur.execute("INSERT INTO api_keys (key_hash, name, owner, scopes, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (h, name, owner, scopes, utc_now_naive().isoformat(), expires_at))
        conn.commit()
    finally:
        conn.close()

    return plain


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--scopes", required=True, help="comma-separated scopes, e.g. auto:execute")
    p.add_argument("--ttl-days", type=int, default=365)
    args = p.parse_args()

    key = create_api_key(args.name, args.owner, args.scopes, ttl_days=args.ttl_days)
    print("API key created:")
    print(key)
    print()
    print("Store this value securely — it will not be shown again.")


if __name__ == "__main__":
    main()
