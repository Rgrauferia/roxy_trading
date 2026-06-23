from __future__ import annotations

"""Secrets service: DB-backed encrypted secret storage and rotation endpoints.

This module provides a FastAPI `APIRouter` exposing CRUD + rotate + revisions
endpoints for secrets. Secrets are encrypted with Fernet before persisting in
the existing `db/roxy.db` SQLite database.

Auth: admin endpoints require `ADMIN_TOKEN` (env) to be provided as
`Authorization: Bearer <ADMIN_TOKEN>`.
"""
import os
import sqlite3
import json
import logging
from typing import Optional, List
from datetime import datetime
from datetime import timedelta
import hashlib
import hmac
import secrets as _secrets
import base64

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from pydantic import BaseModel

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:
    Fernet = None
    InvalidToken = Exception

try:
    import keyring
except Exception:
    keyring = None

logger = logging.getLogger("secrets_service")

DB_PATH = os.path.join(os.getcwd(), "db", "roxy.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
ADMIN_OAUTH_PROVIDER = os.getenv("ADMIN_OAUTH_PROVIDER", "github")
ADMIN_USERS = set([u.strip() for u in os.getenv("ADMIN_USERS", "").split(",") if u.strip()])
ADMIN_ORGS = set([o.strip() for o in os.getenv("ADMIN_ORGS", "").split(",") if o.strip()])
API_KEY_TTL_DAYS = int(os.getenv("API_KEY_TTL_DAYS", "90"))
ROTATION_PRUNE_DAYS = int(os.getenv("ROTATION_PRUNE_DAYS", "90"))
ROTATION_MAX_REVISIONS = int(os.getenv("ROTATION_MAX_REVISIONS", "10"))
SCHEDULER_ENABLED = os.getenv("SECRETS_SCHEDULER_ENABLED", "1") != "0"
FERNET_KEY_ENV = "FERNET_KEY"
FERNET_KEY_FILE_ENV = "FERNET_KEY_FILE"

router = APIRouter(prefix="/api")


class SecretCreate(BaseModel):
    name: str
    value: str
    provider: Optional[str] = None
    metadata: Optional[dict] = None


class SecretMeta(BaseModel):
    name: str
    provider: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


def _get_fernet_key() -> Optional[bytes]:
    # 1) env var
    k = os.getenv(FERNET_KEY_ENV)
    if k:
        return k.encode()

    # 2) file path
    path = os.getenv(FERNET_KEY_FILE_ENV)
    if path:
        try:
            with open(path, "rb") as f:
                return f.read().strip()
        except Exception:
            logger.exception("Failed to read FERNET_KEY_FILE %s", path)

    # 3) keyring
    if keyring is not None:
        try:
            v = keyring.get_password("roxy", "fernet_key")
            if v:
                return v.encode()
        except Exception:
            logger.exception("keyring lookup for fernet_key failed")

    return None


def _get_fernet() -> Optional["Fernet"]:
    if Fernet is None:
        return None
    key = _get_fernet_key()
    if not key:
        logger.warning("FERNET_KEY not configured; secrets endpoints will be disabled")
        return None
    try:
        return Fernet(key)
    except Exception:
        logger.exception("Invalid FERNET_KEY")
        return None


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def ensure_tables():
    sql = [
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
                """,
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT NOT NULL UNIQUE,
                    name TEXT,
                    owner TEXT,
                    scopes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    revoked INTEGER DEFAULT 0,
                    last_used DATETIME
                )
                """,
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
        """,
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_hash TEXT NOT NULL UNIQUE,
                    username TEXT,
                    provider TEXT,
                    encrypted_token BLOB,
                    scopes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS oauth_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state TEXT NOT NULL UNIQUE,
                    redirect_uri TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS oauth_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state TEXT NOT NULL UNIQUE,
                    username TEXT,
                    session_token TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """,
                        """
                        CREATE TABLE IF NOT EXISTS ai_runs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            run_id TEXT,
                            user TEXT,
                            prompt TEXT,
                            response TEXT,
                            parsed_json TEXT,
                            model TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                        """,
                        """
                        CREATE TABLE IF NOT EXISTS prompt_cache (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            pkey TEXT NOT NULL UNIQUE,
                            prompt TEXT,
                            response TEXT,
                            model TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            expires_at DATETIME
                        )
                        """,
        """
        CREATE TABLE IF NOT EXISTS secret_audit (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          secret_id INTEGER,
          actor TEXT,
          action TEXT,
          details TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    conn = _conn()
    try:
        cur = conn.cursor()
        for s in sql:
            cur.execute(s)
        # migration: ensure sessions has newer columns
        try:
            cur.execute("PRAGMA table_info(sessions)")
            cols = [r[1] for r in cur.fetchall()]
            if 'encrypted_token' not in cols:
                cur.execute("ALTER TABLE sessions ADD COLUMN encrypted_token BLOB")
            if 'scopes' not in cols:
                cur.execute("ALTER TABLE sessions ADD COLUMN scopes TEXT")
            if 'last_used' not in cols:
                cur.execute("ALTER TABLE sessions ADD COLUMN last_used DATETIME")
            if 'refresh_token_hash' not in cols:
                cur.execute("ALTER TABLE sessions ADD COLUMN refresh_token_hash TEXT")
            if 'refresh_expires_at' not in cols:
                cur.execute("ALTER TABLE sessions ADD COLUMN refresh_expires_at DATETIME")
            if 'refresh_revoked' not in cols:
                cur.execute("ALTER TABLE sessions ADD COLUMN refresh_revoked INTEGER DEFAULT 0")
        except Exception:
            # ignore if sessions doesn't exist yet or ALTER not supported
            pass
        conn.commit()
    finally:
        conn.close()


ensure_tables()


def _encrypt(value: str) -> bytes:
    f = _get_fernet()
    if not f:
        raise RuntimeError("FERNET not configured")
    return f.encrypt(value.encode())


def _decrypt(token: bytes) -> str:
    f = _get_fernet()
    if not f:
        raise RuntimeError("FERNET not configured")
    try:
        return f.decrypt(token).decode()
    except InvalidToken:
        raise HTTPException(status_code=500, detail="Failed to decrypt secret")


def _require_admin(req: Request):
    # If ADMIN_TOKEN present, accept it for backwards compatibility
    auth = req.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        if ADMIN_TOKEN and token == ADMIN_TOKEN:
            return {"type": "admin_token"}

        # try OAuth provider (e.g., GitHub) token introspection via `auth` module
        try:
            import auth as oauth_auth

            user_info = oauth_auth.fetch_user_info(ADMIN_OAUTH_PROVIDER, token)
            username = user_info.get("login") or user_info.get("username")
            if username in ADMIN_USERS:
                return {"type": "user", "user": username}
            # check orgs membership
            if ADMIN_ORGS:
                orgs = oauth_auth.get_user_orgs(token)
                if any(o in ADMIN_ORGS for o in orgs):
                    return {"type": "user", "user": username}
        except Exception:
            # ignore and fall through to unauthorized
            pass

    # permissive dev mode if no ADMIN_TOKEN and no ADMIN_USERS/ORGS configured
    if not ADMIN_TOKEN and not ADMIN_USERS and not ADMIN_ORGS:
        logger.warning("No admin auth configured; admin endpoints permissive in dev")
        return {"type": "dev"}

    raise HTTPException(status_code=403, detail="admin authorization required")


def _actor_label(actor) -> str:
    if isinstance(actor, dict):
        return str(actor.get("user") or actor.get("type") or json.dumps(actor, sort_keys=True))
    return str(actor or "unknown")


def _create_session(username: str, provider: str = "local", ttl_days: int = 7) -> dict:
    plain = _secrets.token_urlsafe(32)
    h = _hash_key(plain)
    expires_at = (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO sessions (token_hash, username, provider, expires_at) VALUES (?, ?, ?, ?)", (h, username, provider, expires_at))
        conn.commit()
        sid = cur.lastrowid
        return {"id": sid, "token": plain, "expires_at": expires_at, "username": username}
    finally:
        conn.close()


def _create_session_with_provider_token(username: str, provider: str, provider_token_plain: str, scopes: Optional[list] = None, ttl_days: int = 7) -> dict:
    """Create a session and store an encrypted provider token in the sessions table."""
    plain = _secrets.token_urlsafe(32)
    h = _hash_key(plain)
    expires_at = (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()
    enc_token = _encrypt(provider_token_plain)
    scopes_s = ",".join(scopes or [])
    conn = _conn()
    try:
        cur = conn.cursor()
        # optionally create a refresh token and store its hash
        refresh_plain = _secrets.token_urlsafe(48)
        refresh_hash = _hash_key(refresh_plain)
        refresh_expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
        cur.execute(
            "INSERT INTO sessions (token_hash, username, provider, encrypted_token, scopes, expires_at, refresh_token_hash, refresh_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (h, username, provider, enc_token, scopes_s, expires_at, refresh_hash, refresh_expires),
        )
        conn.commit()
        sid = cur.lastrowid
        return {"id": sid, "token": plain, "expires_at": expires_at, "username": username, "refresh_token": refresh_plain, "refresh_expires_at": refresh_expires}
    finally:
        conn.close()


def _get_session_by_token(token: str) -> Optional[dict]:
    h = _hash_key(token)
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, provider, expires_at FROM sessions WHERE token_hash=? AND (expires_at IS NULL OR expires_at > ?)", (h, datetime.utcnow().isoformat()))
        r = cur.fetchone()
        if not r:
            return None
        # update last_used timestamp
        try:
            cur.execute("UPDATE sessions SET last_used=? WHERE id=?", (datetime.utcnow().isoformat(), r[0]))
            conn.commit()
        except Exception:
            pass
        return {"id": r[0], "username": r[1], "provider": r[2], "expires_at": r[3]}
    finally:
        conn.close()


@router.post('/auth/mock-login')
def auth_mock_login(username: str = Body(...)):
    """Create a short-lived session token for local development and tests."""
    return _create_session(username=username, provider="mock", ttl_days=7)


@router.post('/auth/device/start')
def auth_device_start():
    """Start GitHub device flow and return device/user codes to the client."""
    try:
        import auth as oauth
        df = oauth.github_start_device_flow()
        return df
    except Exception as e:
        logger.exception("device start failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/auth/device/poll')
def auth_device_poll(device_code: str = Body(...)):
    """Poll GitHub for device flow completion, create session and store provider token encrypted."""
    try:
        import auth as oauth
        res = oauth.github_poll_device_flow(device_code)
        # res is DeviceFlowResult(user, access_token)
        sess = _create_session_with_provider_token(res.user, provider='github', provider_token_plain=res.access_token)
        # ensure account exists
        try:
            import storage
            storage.create_account_if_missing(res.user)
        except Exception:
            pass
        return {"username": res.user, "session_token": sess["token"]}
    except Exception as e:
        logger.exception("device poll failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/auth/start')
def auth_start_redirect(redirect_uri: str):
    """Return an authorization URL to redirect the browser to (GitHub redirect flow)."""
    try:
        import auth as oauth
        # generate server-side state and persist for CSRF protection
        state = _secrets.token_urlsafe(24)
        expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        conn = _conn()
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO oauth_states (state, redirect_uri, expires_at) VALUES (?, ?, ?)", (state, redirect_uri, expires))
            conn.commit()
        finally:
            conn.close()
        sig = _sign_state(state)
        url = oauth.start_oauth_flow('github', redirect_uri, state=state)
        return {"url": url, "state": state, "sig": sig}
    except Exception as e:
        logger.exception("redirect start failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/auth/callback')
def auth_oauth_callback(code: str, state: Optional[str] = None, redirect_uri: str = None):
    """Exchange code for token, store provider token encrypted, and return a session token."""
    try:
        import auth as oauth
        # validate provided state server-side if present
        if state:
            conn = _conn()
            try:
                cur = conn.cursor()
                cur.execute("SELECT id, expires_at FROM oauth_states WHERE state=?", (state,))
                r = cur.fetchone()
                if not r:
                    raise HTTPException(status_code=400, detail="invalid or expired state")
                # delete state after use
                cur.execute("DELETE FROM oauth_states WHERE id=?", (r[0],))
                conn.commit()
            finally:
                conn.close()

        token = oauth.exchange_code_for_token('github', code, redirect_uri)
        info = oauth.fetch_user_info('github', token)
        username = info.get('login')
        # store provider token encrypted and include scopes if returned
        sess = _create_session_with_provider_token(username, provider='github', provider_token_plain=token, scopes=["read:user","read:org"])
        # if state provided, write oauth_results so the UI can poll for the resulting session token
        if state:
            try:
                conn = _conn()
                cur = conn.cursor()
                cur.execute("INSERT OR REPLACE INTO oauth_results (state, username, session_token) VALUES (?, ?, ?)", (state, username, sess['token']))
                conn.commit()
            except Exception:
                logger.exception("failed to write oauth_results")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        # optionally write a run/oauth_callback.json for Streamlit redirect helper
        try:
            from pathlib import Path
            p = Path('run')
            p.mkdir(parents=True, exist_ok=True)
            (p / 'oauth_callback.json').write_text(json.dumps({'login': username, 'access_token': token}))
        except Exception:
            pass
        return {"username": username, "session_token": sess['token']}
    except Exception as e:
        logger.exception("oauth callback failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/auth/check_state')
def auth_check_state(state: str, sig: Optional[str] = None):
    """Check whether an OAuth flow for `state` has completed and return session token once.

    This endpoint returns `{username, session_token}` when available and deletes the result
    so it can only be consumed once.
    """
    if not sig:
        raise HTTPException(status_code=400, detail="sig required")
    # verify signature
    if not _verify_state_sig(state, sig):
        raise HTTPException(status_code=403, detail="invalid signature")
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT username, session_token FROM oauth_results WHERE state=?", (state,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="not ready")
        username, token = r
        cur.execute("DELETE FROM oauth_results WHERE state=?", (state,))
        conn.commit()
        return {"username": username, "session_token": token}
    finally:
        conn.close()


@router.post('/auth/refresh')
def auth_refresh(request: Request):
    """Rotate the current session token and extend its expiry.

    Caller must present the current token in `Authorization: Bearer <token>`.
    Returns a new plain token and new expiry. The old token is invalidated.
    """
    authh = request.headers.get('Authorization')
    if not authh or not authh.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="missing authorization")
    token = authh.split(' ', 1)[1]
    s = _get_session_by_token(token)
    if not s:
        raise HTTPException(status_code=401, detail="invalid token")
    # generate new plain token and store its hash
    new_plain = _secrets.token_urlsafe(32)
    new_hash = _hash_key(new_plain)
    new_expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE sessions SET token_hash=?, expires_at=?, last_used=? WHERE id=?", (new_hash, new_expires, datetime.utcnow().isoformat(), s['id']))
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'rotate_session', ?)", (s['id'], s['username'], json.dumps({'rotated_by': 'self'})))
        conn.commit()
        return {"token": new_plain, "expires_at": new_expires}
    finally:
        conn.close()


@router.post('/auth/refresh-token')
def auth_refresh_token(refresh_token: str = Body(...)):
    """Exchange a refresh token for a new session token. The refresh token is rotated on use."""
    if not refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token required")
    rh = _hash_key(refresh_token)
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, refresh_expires_at, refresh_revoked FROM sessions WHERE refresh_token_hash=?", (rh,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=401, detail="invalid refresh token")
        sid, username, refresh_expires_at, refresh_revoked = r
        if refresh_revoked:
            raise HTTPException(status_code=401, detail="refresh token revoked")
        if refresh_expires_at and refresh_expires_at <= datetime.utcnow().isoformat():
            raise HTTPException(status_code=401, detail="refresh token expired")
        # rotate access token and refresh token
        new_plain = _secrets.token_urlsafe(32)
        new_hash = _hash_key(new_plain)
        new_expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
        # rotate refresh token
        new_refresh_plain = _secrets.token_urlsafe(48)
        new_refresh_hash = _hash_key(new_refresh_plain)
        new_refresh_expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
        cur.execute("UPDATE sessions SET token_hash=?, expires_at=?, refresh_token_hash=?, refresh_expires_at=?, last_used=? WHERE id=?", (new_hash, new_expires, new_refresh_hash, new_refresh_expires, datetime.utcnow().isoformat(), sid))
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'refresh_token_rotate', ?)", (sid, username, json.dumps({'rotated_by': 'refresh'})))
        conn.commit()
        return {"token": new_plain, "expires_at": new_expires, "refresh_token": new_refresh_plain, "refresh_expires_at": new_refresh_expires}
    finally:
        conn.close()


@router.post('/auth/revoke')
def auth_revoke(request: Request):
    """Revoke the session represented by the provided bearer token."""
    authh = request.headers.get('Authorization')
    if not authh or not authh.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="missing authorization")
    token = authh.split(' ', 1)[1]
    s = _get_session_by_token(token)
    if not s:
        raise HTTPException(status_code=401, detail="invalid token")
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE id=?", (s['id'],))
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'revoke_session', ?)", (s['id'], s['username'], json.dumps({})))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get('/auth/me')
def auth_me(request: Request):
    """Return information about the current authenticated session or oauth token."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthenticated")
    # if session-based, return username and type
    if user.get('type') == 'session':
        return {"username": user.get('user'), "type": "session"}
    return {"username": user.get('user'), "type": "oauth"}


def get_current_user(request: Request) -> Optional[dict]:
    """Dependency: resolve bearer token to session or validate OAuth provider token via `auth` module."""
    authh = request.headers.get('Authorization')
    if not authh:
        return None
    if not authh.startswith('Bearer '):
        return None
    token = authh.split(' ', 1)[1]
    # check session table
    s = _get_session_by_token(token)
    if s:
        return {"type": "session", "user": s['username']}
    # otherwise try provider introspection
    try:
        import auth as oauth_auth
        user_info = oauth_auth.fetch_user_info(ADMIN_OAUTH_PROVIDER, token)
        username = user_info.get('login') or user_info.get('username')
        return {"type": "oauth", "user": username, "info": user_info}
    except Exception:
        return None


def _get_master_key() -> Optional[bytes]:
    # use the fernet key as HMAC secret if available
    k = _get_fernet_key()
    if k:
        return k
    # fallback to environment SALT
    s = os.getenv("API_KEY_HASH_SALT")
    if s:
        return s.encode()
    return None


def _hash_key(plain: str) -> str:
    secret = _get_master_key()
    if secret:
        return hmac.new(secret, plain.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(plain.encode()).hexdigest()


def _generate_plain_api_key() -> str:
    # url-safe token
    return _secrets.token_urlsafe(32)


def _sign_state(state: str) -> str:
    """Return urlsafe base64 HMAC signature for `state` using master key."""
    key = _get_master_key()
    if not key:
        # fallback to unhashed token (not recommended)
        return ""
    sig = hmac.new(key, state.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def _verify_state_sig(state: str, sig: str) -> bool:
    key = _get_master_key()
    if not key:
        return False
    try:
        expected = hmac.new(key, state.encode(), hashlib.sha256).digest()
        # decode provided sig
        padded = sig + '=' * (-len(sig) % 4)
        provided = base64.urlsafe_b64decode(padded.encode())
        return hmac.compare_digest(expected, provided)
    except Exception:
        return False


@router.get("/secrets", response_model=List[SecretMeta])
def list_secrets(skip: int = 0, limit: int = 100):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, provider, version, created_at, updated_at FROM secrets ORDER BY name LIMIT ? OFFSET ?", (limit, skip))
        rows = cur.fetchall()
        return [
            SecretMeta(name=r[0], provider=r[1], version=r[2], created_at=r[3], updated_at=r[4]) for r in rows
        ]
    finally:
        conn.close()


@router.post("/secrets", response_model=SecretMeta, status_code=201)
def create_secret(payload: SecretCreate, actor: Optional[str] = Depends(_require_admin)):
    if _get_fernet() is None:
        raise HTTPException(status_code=503, detail="secrets not configured (FERNET_KEY missing)")
    enc = _encrypt(payload.value)
    actor_text = _actor_label(actor)
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO secrets (name, provider, encrypted_value, metadata, created_by, version) VALUES (?, ?, ?, ?, ?, 1)",
            (payload.name, payload.provider, enc, json.dumps(payload.metadata or {}), actor_text),
        )
        secret_id = cur.lastrowid
        cur.execute(
            "INSERT INTO secret_revisions (secret_id, encrypted_value, version, rotated_by) VALUES (?, ?, ?, ?)",
            (secret_id, enc, 1, actor_text),
        )
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'create', ?)", (secret_id, actor_text, json.dumps({"name": payload.name})))
        conn.commit()
        cur.execute("SELECT name, provider, version, created_at, updated_at FROM secrets WHERE id=?", (secret_id,))
        r = cur.fetchone()
        return SecretMeta(name=r[0], provider=r[1], version=r[2], created_at=r[3], updated_at=r[4])
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="secret already exists")
    finally:
        conn.close()


@router.get("/secrets/{name}", response_model=SecretMeta)
def get_secret_meta(name: str):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, provider, version, created_at, updated_at FROM secrets WHERE name=?", (name,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        return SecretMeta(name=r[0], provider=r[1], version=r[2], created_at=r[3], updated_at=r[4])
    finally:
        conn.close()


@router.get("/secrets/{name}/reveal")
def reveal_secret(name: str, actor: Optional[str] = Depends(_require_admin)):
    # admin-only reveal; audited
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, encrypted_value FROM secrets WHERE name=?", (name,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        secret_id = r[0]
        enc = r[1]
        val = _decrypt(enc)
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'reveal', ?)", (secret_id, _actor_label(actor), json.dumps({"name": name})))
        conn.commit()
        return {"name": name, "value": val}
    finally:
        conn.close()


@router.post("/secrets/{name}/rotate")
def rotate_secret(name: str, new_value: Optional[str] = Body(None), reason: Optional[str] = Body(None), actor: Optional[str] = Depends(_require_admin)):
    if _get_fernet() is None:
        raise HTTPException(status_code=503, detail="secrets not configured (FERNET_KEY missing)")
    actor_text = _actor_label(actor)
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, encrypted_value, version FROM secrets WHERE name=?", (name,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        secret_id, old_enc, old_version = r
        if new_value is None:
            # generate random 32-byte base64 key for service secrets
            new_plain = Fernet.generate_key().decode()
        else:
            new_plain = new_value
        new_enc = _encrypt(new_plain)
        new_version = old_version + 1
        cur.execute("UPDATE secrets SET encrypted_value=?, version=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_enc, new_version, secret_id))
        cur.execute("INSERT INTO secret_revisions (secret_id, encrypted_value, version, rotated_by, reason) VALUES (?, ?, ?, ?, ?)", (secret_id, new_enc, new_version, actor_text, reason))
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'rotate', ?)", (secret_id, actor_text, json.dumps({"reason": reason})))
        conn.commit()
        return {"name": name, "version": new_version}
    finally:
        conn.close()


@router.get("/secrets/{name}/revisions")
def list_revisions(name: str):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM secrets WHERE name=?", (name,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        secret_id = r[0]
        cur.execute("SELECT version, rotated_by, rotated_at, reason FROM secret_revisions WHERE secret_id=? ORDER BY version DESC", (secret_id,))
        rows = cur.fetchall()
        out = []
        for ver, by, at, reason in rows:
            out.append({"version": ver, "rotated_by": by, "rotated_at": at, "reason": reason})
        return out
    finally:
        conn.close()


# ------------------------ API key management ------------------------


def _now_iso():
    return datetime.utcnow().isoformat()


@router.post("/api-keys")
def create_api_key(name: Optional[str] = Body(None), owner: Optional[str] = Body(None), scopes: Optional[List[str]] = Body(None), expires_in_days: Optional[int] = Body(None), actor: Optional[dict] = Depends(_require_admin)):
    """Create an API key and return the plain key once."""
    plain = _generate_plain_api_key()
    h = _hash_key(plain)
    scopes_s = ",".join(scopes or [])
    expires_in = expires_in_days or API_KEY_TTL_DAYS
    expires_at = (datetime.utcnow() + timedelta(days=expires_in)).isoformat()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO api_keys (key_hash, name, owner, scopes, expires_at) VALUES (?, ?, ?, ?, ?)", (h, name, owner, scopes_s, expires_at))
        conn.commit()
        kid = cur.lastrowid
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'create_api_key', ?)", (kid, _actor_label(actor), json.dumps({"name": name, "owner": owner})))
        conn.commit()
        return {"id": kid, "plain_key": plain, "expires_at": expires_at}
    finally:
        conn.close()


@router.get("/api-keys")
def list_api_keys(actor: Optional[dict] = Depends(_require_admin)):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, owner, scopes, created_at, expires_at, revoked, last_used FROM api_keys ORDER BY id DESC")
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({"id": r[0], "name": r[1], "owner": r[2], "scopes": r[3].split(',') if r[3] else [], "created_at": r[4], "expires_at": r[5], "revoked": bool(r[6]), "last_used": r[7]})
        return out
    finally:
        conn.close()


@router.post("/api-keys/{kid}/rotate")
def rotate_api_key(kid: int, actor: Optional[dict] = Depends(_require_admin)):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, owner, scopes, revoked FROM api_keys WHERE id=?", (kid,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        if r[4]:
            raise HTTPException(status_code=400, detail="key revoked")
        name, owner, scopes = r[1], r[2], r[3]
        # revoke old
        cur.execute("UPDATE api_keys SET revoked=1 WHERE id=?", (kid,))
        # create new
        plain = _generate_plain_api_key()
        h = _hash_key(plain)
        expires_at = (datetime.utcnow() + timedelta(days=API_KEY_TTL_DAYS)).isoformat()
        cur.execute("INSERT INTO api_keys (key_hash, name, owner, scopes, expires_at) VALUES (?, ?, ?, ?, ?)", (h, name, owner, scopes, expires_at))
        new_id = cur.lastrowid
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'rotate_api_key', ?)", (kid, _actor_label(actor), json.dumps({"new_id": new_id})))
        conn.commit()
        return {"id": new_id, "plain_key": plain, "expires_at": expires_at}
    finally:
        conn.close()


@router.post("/api-keys/{kid}/revoke")
def revoke_api_key(kid: int, actor: Optional[dict] = Depends(_require_admin)):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE api_keys SET revoked=1 WHERE id=?", (kid,))
        cur.execute("INSERT INTO secret_audit (secret_id, actor, action, details) VALUES (?, ?, 'revoke_api_key', ?)", (kid, _actor_label(actor), json.dumps({})))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ------------------------ Scheduler jobs ------------------------


def rotate_expired_api_keys_job():
    logger.info("rotate_expired_api_keys_job: scanning for expired keys")
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM api_keys WHERE revoked=0 AND expires_at <= ?", (datetime.utcnow().isoformat(),))
        rows = cur.fetchall()
        for (kid,) in rows:
            try:
                rotate_api_key(kid, actor={"type": "system"})
            except Exception:
                logger.exception("failed to rotate api key %s", kid)
    finally:
        conn.close()


def prune_old_revisions_job():
    logger.info("prune_old_revisions_job: pruning old secret revisions")
    cutoff = (datetime.utcnow() - timedelta(days=ROTATION_PRUNE_DAYS)).isoformat()
    conn = _conn()
    try:
        cur = conn.cursor()
        # remove revisions older than cutoff
        cur.execute("DELETE FROM secret_revisions WHERE rotated_at <= ?", (cutoff,))
        conn.commit()
        # also enforce max revisions per secret
        cur.execute("SELECT id FROM secrets")
        secret_ids = [r[0] for r in cur.fetchall()]
        for sid in secret_ids:
            cur.execute("SELECT id FROM secret_revisions WHERE secret_id=? ORDER BY version DESC", (sid,))
            rows = [r[0] for r in cur.fetchall()]
            if len(rows) > ROTATION_MAX_REVISIONS:
                to_delete = rows[ROTATION_MAX_REVISIONS:]
                cur.executemany("DELETE FROM secret_revisions WHERE id=?", [(i,) for i in to_delete])
        conn.commit()
    finally:
        conn.close()


_scheduler = None
def _start_scheduler():
    global _scheduler
    if not SCHEDULER_ENABLED or BackgroundScheduler is None:
        logger.info("Scheduler disabled or APScheduler unavailable")
        return
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(rotate_expired_api_keys_job, 'interval', minutes=5)
    _scheduler.add_job(prune_old_revisions_job, 'cron', hour=3, minute=0)
    _scheduler.start()
    logger.info("Secrets scheduler started")


# start scheduler on import
try:
    _start_scheduler()
except Exception:
    logger.exception("failed to start scheduler")
