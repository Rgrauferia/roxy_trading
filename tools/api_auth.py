"""API authentication dependency for FastAPI routers.

Provides `require_api_key` dependency which accepts either ADMIN_TOKEN
or a managed API key persisted in the `api_keys` table (created via
`tools.secrets_service`). Returns a small dict with caller info.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from fastapi import Request, HTTPException

from roxy_time import utc_now_naive

try:
    from tools import secrets_service
except Exception:
    secrets_service = None


DB_PATH = secrets_service.DB_PATH if secrets_service is not None else (os.path.join(os.getcwd(), "db", "roxy.db"))


def _conn():
    path = secrets_service.DB_PATH if secrets_service is not None else DB_PATH
    return sqlite3.connect(path)


def require_api_key(req: Request):
    auth = req.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = auth.split(" ", 1)[1]

    # admin token shortcut
    admin_token = os.getenv("ADMIN_TOKEN")
    if admin_token and token == admin_token:
        return {"type": "admin"}

    # try to validate against api_keys table using secrets_service hashing
    try:
        if secrets_service is None:
            raise Exception("secrets_service not available")
        h = secrets_service._hash_key(token)
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT id, name, owner, scopes, revoked, expires_at FROM api_keys WHERE key_hash = ?", (h,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=403, detail="invalid API key")
        kid, name, owner, scopes_s, revoked, expires_at = row
        if revoked:
            raise HTTPException(status_code=403, detail="API key revoked")
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at)
                if exp < utc_now_naive():
                    raise HTTPException(status_code=403, detail="API key expired")
            except ValueError:
                # not ISO format, ignore
                pass
        scopes = [s.strip() for s in (scopes_s or "").split(",") if s.strip()]
        return {"type": "api_key", "id": kid, "name": name, "owner": owner, "scopes": scopes}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="invalid API key")


__all__ = ["require_api_key"]
