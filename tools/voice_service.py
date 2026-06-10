from __future__ import annotations

from contextlib import asynccontextmanager
import os
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
try:
    # mount secrets router if available
    from tools.secrets_service import router as secrets_router
except Exception:
    secrets_router = None

try:
    # local rule-based helper
    from tools import voice_assistant as va_backend
except Exception:
    va_backend = None

try:
    # optional LLM provider
    from tools import llm_provider as llm
except Exception:
    llm = None

try:
    from tools import llm_agent as llm_agent_router
except Exception:
    llm_agent_router = None
try:
    from tools import ab_api as ab_api_router
except Exception:
    ab_api_router = None
try:
    from tools import auto_api as auto_api_router
except Exception:
    auto_api_router = None


VOICE_API_KEY = os.getenv("VOICE_API_KEY")
RATE_LIMIT_WINDOW = int(os.getenv("VOICE_RATE_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX = int(os.getenv("VOICE_RATE_MAX", "30"))
_DEV_AUTH_WARNING_LOGGED = False

# simple in-memory rate limiter: api_key -> (count, window_start)
_RATE_STATE: Dict[str, Dict[str, int]] = {}

# optional Redis for persistent rate limiting if REDIS_URL is provided
REDIS_URL = os.getenv("REDIS_URL")
redis_client = None
if REDIS_URL:
    try:
        import redis

        redis_client = redis.from_url(REDIS_URL)
    except Exception:
        redis_client = None


def setup_logger() -> logging.Logger:
    log = logging.getLogger("voice_service")
    if not log.handlers:
        log.setLevel(logging.INFO)
        handler = TimedRotatingFileHandler("logs/voice_service.log", when="midnight", backupCount=7)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("voice_service starting up; rate window=%s max=%s", RATE_LIMIT_WINDOW, RATE_LIMIT_MAX)
    yield


app = FastAPI(title="Roxy Voice Assistant (prototype)", lifespan=lifespan)
if secrets_router is not None:
    app.include_router(secrets_router)
if llm_agent_router is not None:
    try:
        app.include_router(llm_agent_router.router)
    except Exception:
        pass
if ab_api_router is not None:
    try:
        app.include_router(ab_api_router.router)
    except Exception:
        pass
if auto_api_router is not None:
    try:
        app.include_router(auto_api_router.router)
    except Exception:
        pass


class AssistRequest(BaseModel):
    query: str
    user: Optional[str] = None


def require_api_key(request: Request):
    global _DEV_AUTH_WARNING_LOGGED
    if VOICE_API_KEY is None:
        # allow local dev when VOICE_API_KEY not set, but log warning
        if not _DEV_AUTH_WARNING_LOGGED:
            logger.warning("VOICE_API_KEY not set — running in permissive dev mode")
            _DEV_AUTH_WARNING_LOGGED = True
        return None
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = auth.split(" ", 1)[1]
    if token != VOICE_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return token


def rate_limited(token: Optional[str]):
    key = token or "dev"
    now = int(time.time())
    # persistent limiter using Redis if available
    if redis_client:
        try:
            pipe = redis_client.pipeline()
            count = redis_client.get(f"ratelimit:{key}")
            if not count:
                pipe.setex(f"ratelimit:{key}", RATE_LIMIT_WINDOW, 1)
                pipe.execute()
                return
            else:
                count = int(count)
                if count >= RATE_LIMIT_MAX:
                    raise HTTPException(status_code=429, detail="Rate limit exceeded")
                redis_client.incr(f"ratelimit:{key}")
                return
        except HTTPException:
            raise
        except Exception:
            # fall back to memory-based if Redis fails
            pass

    st = _RATE_STATE.get(key)
    if not st:
        _RATE_STATE[key] = {"count": 1, "start": now}
        return
    if now - st["start"] > RATE_LIMIT_WINDOW:
        _RATE_STATE[key] = {"count": 1, "start": now}
        return
    if st["count"] >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    st["count"] += 1


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/assist")
def assist(req: AssistRequest, token: Optional[str] = Depends(require_api_key)):
    """Return a text reply for a given query. This is a prototype service.

    Security: requires `Authorization: Bearer <VOICE_API_KEY>` unless VOICE_API_KEY is unset (dev).
    Rate limiting: per-key in-memory window controlled by env vars.
    """
    # rate limiting
    try:
        rate_limited(token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Rate limiter error: %s", e)

    q = (req.query or "").strip()
    user = req.user
    logger.info("assist request user=%s query=%s", user, q[:200])

    # Prefer integrating with an LLM here — check llm_provider, then rule-based backend
    reply = None
    if llm is not None:
        try:
            reply = llm.generate_reply(q, user=user)
        except Exception:
            logger.exception("LLM provider error")
            reply = None

    if not reply and va_backend is not None:
        try:
            reply = va_backend.generate_reply(q, user=user)
        except Exception:
            logger.exception("voice backend error")
            raise HTTPException(status_code=500, detail="assistant backend error")

    if not reply:
        # fallback simple echo
        reply = f"(assistant stub) You said: {q}"

    return {"reply": reply}
