from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
import time
import logging
import uuid
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
ASSETS_DIR = Path("assets")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("voice_service starting up; rate window=%s max=%s", RATE_LIMIT_WINDOW, RATE_LIMIT_MAX)
    yield


app = FastAPI(title="Roxy Voice Assistant (prototype)", lifespan=lifespan)
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
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
    session_id: Optional[str] = None
    profile: Dict[str, object] = Field(default_factory=dict)


class ProfileRequest(BaseModel):
    user: Optional[str] = None
    profile: Dict[str, object] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    rating: str
    user: Optional[str] = None
    session_id: Optional[str] = None
    intent: Optional[str] = None
    query: Optional[str] = None
    reply: Optional[str] = None
    note: Optional[str] = None


def empty_active_context() -> dict[str, object]:
    return {
        "active_intent": "",
        "active_symbol": "",
        "active_topic": "",
        "last_safety_level": "",
        "needs_confirmation": False,
        "next_best_actions": ["ask_latest_opportunity", "ask_market_summary"],
    }


def add_turn_metadata(state: dict[str, object], started_at: float, response_source: str) -> dict[str, object]:
    payload = dict(state or {})
    payload.setdefault("turn_id", uuid.uuid4().hex[:12])
    payload["server_latency_ms"] = max(0.0, round((time.perf_counter() - started_at) * 1000, 1))
    payload["response_source"] = response_source
    return payload


def sync_request_profile(req: AssistRequest) -> None:
    """Persist safe visible profile fields before the brain reads user context."""
    if not req.profile or va_backend is None or not hasattr(va_backend, "update_user_profile"):
        return
    try:
        va_backend.update_user_profile(req.user, req.profile)
    except Exception:
        logger.exception("inline profile sync error")


def sse_event(event_name: str, payload: dict[str, object]) -> str:
    body = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_name}\ndata: {body}\n\n"


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


@app.get("/roxy-live", response_class=HTMLResponse)
def roxy_live_page():
    return HTMLResponse(
        """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Roxy Live</title>
  <link rel="icon" href="/assets/roxy_avatar_icon.jpg" />
  <link rel="apple-touch-icon" href="/assets/roxy_avatar_icon.jpg" />
  <style>
    :root {
      color-scheme: dark;
      --bg: #07111f;
      --panel: #0d1b2d;
      --line: #24405f;
      --text: #edf4ff;
      --muted: #9bb2cb;
      --accent: #42d392;
      --warn: #fbbf24;
      --danger: #fb7185;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at 50% 0%, #0f2a44 0, var(--bg) 45%, #030712 100%);
      color: var(--text);
    }
    main {
      width: min(1040px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0;
      display: grid;
      gap: 18px;
    }
    .top {
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 18px;
      align-items: stretch;
    }
    main.voice-idle .top {
      grid-template-columns: minmax(0, 1fr);
    }
    main.voice-idle .avatar {
      display: none;
    }
    .avatar, .panel {
      border: 1px solid var(--line);
      background: rgba(13, 27, 45, 0.88);
      border-radius: 8px;
      box-shadow: 0 18px 70px rgba(0,0,0,.3);
    }
    .avatar {
      min-height: 260px;
      display: grid;
      place-items: center;
      text-align: center;
      padding: 18px;
    }
    .face {
      width: 152px;
      height: 152px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      border: 1px solid #2f638f;
      background: linear-gradient(145deg, #12324e, #0b1728);
      font-size: 54px;
      font-weight: 800;
      letter-spacing: 0;
      color: #e8f7ff;
      text-shadow: 0 0 18px rgba(66,211,146,.35);
      overflow: hidden;
      margin: 0 auto;
    }
    .face img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      object-position: center 30%;
      display: block;
    }
    .fallback-face {
      display: none;
    }
    .avatar.speaking .face { outline: 4px solid rgba(66,211,146,.28); }
    .avatar.listening .face { outline: 4px solid rgba(96,165,250,.32); }
    .avatar.blocked .face { outline: 4px solid rgba(251,113,133,.32); }
    h1 { margin: 0; font-size: 32px; line-height: 1.1; letter-spacing: 0; }
    p { color: var(--muted); margin: 8px 0 0; }
    .panel { padding: 18px; }
    .controls {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }
    button, input, textarea {
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #081526;
      color: var(--text);
      font: inherit;
    }
    button {
      min-height: 44px;
      cursor: pointer;
      font-weight: 700;
    }
    button.primary { background: #0f5132; border-color: #1f9d60; }
    button.warn { background: #4a3208; border-color: #a76a05; }
    button.danger { background: #4c1020; border-color: #a82b45; }
    textarea {
      min-height: 112px;
      resize: vertical;
      padding: 12px;
      margin-top: 12px;
    }
    input { min-height: 42px; padding: 0 12px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
    }
    .chip {
      border: 1px solid var(--line);
      background: #081526;
      border-radius: 8px;
      padding: 10px;
      min-height: 58px;
    }
    .chip span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }
    .reply {
      margin-top: 14px;
      border-left: 3px solid var(--accent);
      padding: 12px 14px;
      background: rgba(66,211,146,.08);
      min-height: 70px;
      line-height: 1.45;
    }
    .welcome-card {
      display: grid;
      grid-template-columns: 84px 1fr;
      gap: 12px;
      align-items: center;
      margin-top: 12px;
      border: 1px solid rgba(96,165,250,.28);
      background: rgba(8,21,38,.72);
      border-radius: 8px;
      padding: 10px;
    }
    .welcome-card img {
      width: 84px;
      height: 84px;
      border-radius: 8px;
      object-fit: cover;
      object-position: center 30%;
      display: block;
      border: 1px solid rgba(96,165,250,.34);
    }
    .welcome-card strong {
      display: block;
      font-size: 16px;
    }
    .welcome-card small {
      color: var(--muted);
      line-height: 1.35;
    }
    .events {
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .quick {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }
    .quick button {
      min-height: 38px;
      font-size: 14px;
      color: var(--muted);
      font-weight: 600;
    }
    .next-actions {
      grid-template-columns: repeat(6, minmax(0, 1fr));
      margin-top: 10px;
    }
    .next-actions:empty {
      display: none;
    }
    .next-actions button {
      border-color: rgba(66,211,146,.35);
      color: #d9fbea;
      background: rgba(15,81,50,.34);
    }
    .toggles {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
    }
    .toggles label {
      display: flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      background: #081526;
      border-radius: 8px;
      min-height: 40px;
      padding: 0 10px;
    }
    .toggles input {
      width: auto;
      min-height: auto;
    }
    .chat {
      margin-top: 14px;
      display: grid;
      gap: 10px;
      max-height: 360px;
      overflow: auto;
      padding-right: 4px;
    }
    .msg {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      line-height: 1.4;
      background: #081526;
      white-space: pre-wrap;
    }
    .msg.user {
      border-color: #255c85;
      background: rgba(96,165,250,.08);
    }
    .msg.roxy {
      border-color: #1f9d60;
      background: rgba(66,211,146,.08);
    }
    .msg.system {
      color: var(--muted);
      font-size: 13px;
    }
    .msg b {
      display: block;
      margin-bottom: 4px;
      color: var(--text);
    }
    .sources {
      margin-top: 12px;
      display: grid;
      gap: 8px;
    }
    .source {
      border: 1px solid var(--line);
      background: #081526;
      border-radius: 8px;
      padding: 9px 10px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .source b {
      color: var(--text);
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 10px;
      margin-top: 12px;
    }
    .voice-row {
      display: grid;
      grid-template-columns: 2fr 1fr 1fr 1fr;
      gap: 10px;
      margin-top: 12px;
      align-items: center;
    }
    select {
      width: 100%;
      min-height: 42px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #081526;
      color: var(--text);
      font: inherit;
      padding: 0 10px;
    }
    .slider {
      border: 1px solid var(--line);
      background: #081526;
      border-radius: 8px;
      min-height: 42px;
      padding: 8px 10px;
      color: var(--muted);
      font-size: 12px;
    }
    .slider input {
      min-height: auto;
      padding: 0;
    }
    @media (max-width: 760px) {
      .top, .row { grid-template-columns: 1fr; }
      .controls, .grid, .quick, .toggles, .voice-row { grid-template-columns: 1fr 1fr; }
    }
  </style>
</head>
<body>
  <main id="roxyLiveMain" class="voice-idle">
    <section class="top">
      <div id="avatar" class="avatar" aria-hidden="true">
        <div>
          <div class="face">
            <img id="roxyAvatar" src="/assets/roxy_avatar.jpg" alt="Roxy avatar" />
            <span id="roxyFallback" class="fallback-face">R</span>
          </div>
          <h2>ROXY</h2>
          <p id="avatarText">ready</p>
        </div>
      </div>
      <div class="panel">
        <h1>Roxy Live</h1>
        <p>Habla con Roxy en tiempo real. Chrome o Edge ofrecen mejor soporte de microfono.</p>
        <div class="welcome-card">
          <img src="/assets/roxy_avatar_card.jpg" alt="Roxy bienvenida" />
          <div>
            <strong>Roxy IA activa</strong>
            <small>Avatar oficial, voz femenina configurable, memoria de sesion y modo conversacion.</small>
          </div>
        </div>
        <div class="row">
          <input id="user" placeholder="Usuario" value="local" />
          <input id="session" placeholder="Session ID" />
          <input id="apiKey" placeholder="VOICE_API_KEY si aplica" type="password" />
        </div>
        <div class="row">
          <input id="preferredName" placeholder="Nombre preferido" />
          <select id="language" aria-label="Idioma de Roxy">
            <option value="es">Español</option>
            <option value="en">English</option>
          </select>
          <select id="tradingMode" aria-label="Modo trading">
            <option value="paper">paper</option>
            <option value="semi-auto">semi-auto</option>
            <option value="full-auto guarded">full-auto guarded</option>
          </select>
          <input id="defaultSymbol" placeholder="Simbolo base (SPY)" />
        </div>
        <div class="row">
          <input id="watchlist" placeholder="Watchlist: SPY, QQQ, NVDA" />
          <button id="saveProfile" class="primary">Guardar perfil</button>
          <button id="loadProfile">Cargar perfil</button>
        </div>
        <textarea id="query" placeholder="Pulsa Hablar o escribe aqui..."></textarea>
        <div class="quick">
          <button data-prompt="hola roxy">Saludo</button>
          <button data-prompt="estado de roxy">Estado</button>
          <button data-prompt="que puedes hacer">Capacidades</button>
          <button data-prompt="resumen de sesion">Sesión</button>
          <button data-prompt="briefing diario">Briefing</button>
          <button data-prompt="resumen del mercado">Mercado</button>
          <button data-prompt="sesion de mercado">Horario</button>
          <button data-prompt="frescura de datos">Datos</button>
          <button data-prompt="soporte y resistencia">Niveles</button>
          <button data-prompt="indicadores tecnicos">Indicadores</button>
          <button data-prompt="vigila mi watchlist">Watchlist</button>
          <button data-prompt="analiza impacto de noticia: pega aqui el titular">Impacto news</button>
          <button data-prompt="puedo operar ahora">Decisión</button>
          <button data-prompt="resumen de oportunidad">Oportunidad</button>
          <button data-prompt="top oportunidades">Ranking</button>
          <button data-prompt="plan de monitoreo">Monitoreo</button>
          <button data-prompt="prepara alerta">Alerta</button>
          <button data-prompt="explica riesgo entrada stop target">Riesgo</button>
          <button data-prompt="checklist de entrada">Checklist</button>
          <button data-prompt="tamaño de posicion con capital 10000 riesgo 0.5%">Sizing</button>
          <button data-prompt="lee el manual de Roxy Trading">Manual</button>
        </div>
        <div class="toggles">
          <label><input id="autoSpeak" type="checkbox" checked /> Voz automatica</label>
          <label><input id="autoSendVoice" type="checkbox" checked /> Enviar al terminar</label>
          <label><input id="conversationMode" type="checkbox" /> Modo conversacion</label>
          <label><input id="wakeMode" type="checkbox" /> Wake Roxy</label>
          <label><input id="saveSettings" type="checkbox" checked /> Guardar usuario/sesion</label>
        </div>
        <div class="voice-row">
          <select id="voiceSelect" aria-label="Voz de Roxy"></select>
          <label class="slider">Velocidad <input id="voiceRate" type="range" min="0.75" max="1.15" step="0.05" value="0.9" /></label>
          <label class="slider">Tono <input id="voicePitch" type="range" min="0.85" max="1.2" step="0.05" value="1.1" /></label>
          <input id="wakeWord" placeholder="Wake: Roxy" value="Roxy" />
          <input id="feedbackNote" placeholder="Nota feedback: mas corto, mas claro..." />
        </div>
        <div class="controls">
          <button id="start" class="primary" title="Hablar / interrumpir respuesta">Hablar</button>
          <button id="stop" class="warn">Parar</button>
          <button id="send">Enviar</button>
          <button id="voiceGuide">Iniciar voz</button>
          <button id="voiceTest">Probar voz</button>
          <button id="repeat">Repetir voz</button>
          <button id="voiceOptions">Opciones voz</button>
          <button id="voicePreset">Voz clara</button>
          <button id="systemCheck">Diagnostico</button>
          <button id="feedbackUp">Sirvio</button>
          <button id="feedbackDown">No sirvio</button>
          <button id="loadMemory">Cargar memoria</button>
          <button id="sessionBrief">Brief local</button>
          <button id="loadLearning">Aprendizaje</button>
          <button id="loadSources">Fuentes</button>
          <button id="clearChat" class="danger">Limpiar chat</button>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="grid">
        <div class="chip"><span>Intent</span><b id="intent">-</b></div>
        <div class="chip"><span>Avatar</span><b id="avatarState">-</b></div>
        <div class="chip"><span>Emotion</span><b id="emotion">-</b></div>
        <div class="chip"><span>Safety</span><b id="safety">-</b></div>
        <div class="chip"><span>Priority</span><b id="priority">-</b></div>
        <div class="chip"><span>Live source</span><b id="liveSource">-</b></div>
        <div class="chip"><span>Voice</span><b id="voiceStatus">-</b></div>
        <div class="chip"><span>Heard</span><b id="voiceHeardStatus">-</b></div>
        <div class="chip"><span>Draft</span><b id="voiceDraftStatus">-</b></div>
        <div class="chip"><span>Context</span><b id="activeContext">-</b></div>
        <div class="chip"><span>Latency</span><b id="latency">-</b></div>
      </div>
      <div id="reply" class="reply">Roxy esta lista.</div>
      <div id="events" class="events">events: ready</div>
      <div id="nextActions" class="quick next-actions" aria-label="Siguientes acciones de Roxy"></div>
      <div id="sources" class="sources"></div>
      <div id="chat" class="chat" aria-live="polite"></div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const session = $("session");
    let recognition = null;
    let lastReply = "";
    let lastQuery = "";
    let lastState = {};
    let lastFinalTranscript = "";
    let isListening = false;
    let isSpeaking = false;
    let manualStop = false;
    let pendingListenTimer = null;
    let activeAssistController = null;
    let lastHandledVoiceText = "";
    let lastHandledVoiceAt = 0;
    let voiceDraftText = "";
    let voicePresenceActive = false;
    const duplicateVoiceWindowMs = 2500;
    const lowVoiceConfidenceThreshold = 0.55;
    const defaultAssistTimeoutMs = 45000;
    const assistStreamEndpoint = "/v1/assist/stream";

    function restoreSettings() {
      $("user").value = localStorage.getItem("roxyLiveUser") || "local";
      $("session").value = localStorage.getItem("roxyLiveSession") || ("roxy-live-" + Math.random().toString(36).slice(2, 10));
      $("apiKey").value = "";
      $("autoSpeak").checked = localStorage.getItem("roxyLiveAutoSpeak") !== "false";
      $("autoSendVoice").checked = localStorage.getItem("roxyLiveAutoSend") !== "false";
      $("conversationMode").checked = localStorage.getItem("roxyLiveConversationMode") === "true";
      $("wakeMode").checked = localStorage.getItem("roxyLiveWakeMode") === "true";
      $("wakeWord").value = localStorage.getItem("roxyLiveWakeWord") || "Roxy";
      $("voiceRate").value = localStorage.getItem("roxyLiveVoiceRate") || "0.9";
      $("voicePitch").value = localStorage.getItem("roxyLiveVoicePitch") || "1.1";
      $("preferredName").value = localStorage.getItem("roxyLivePreferredName") || "";
      $("language").value = localStorage.getItem("roxyLiveLanguage") || "es";
      $("tradingMode").value = localStorage.getItem("roxyLiveTradingMode") || "paper";
      $("defaultSymbol").value = localStorage.getItem("roxyLiveDefaultSymbol") || "SPY";
      $("watchlist").value = localStorage.getItem("roxyLiveWatchlist") || "SPY, QQQ";
    }

    function saveSettings() {
      if (!$("saveSettings").checked) return;
      localStorage.setItem("roxyLiveUser", $("user").value || "local");
      localStorage.setItem("roxyLiveSession", $("session").value || "local");
      localStorage.setItem("roxyLiveAutoSpeak", $("autoSpeak").checked ? "true" : "false");
      localStorage.setItem("roxyLiveAutoSend", $("autoSendVoice").checked ? "true" : "false");
      localStorage.setItem("roxyLiveConversationMode", $("conversationMode").checked ? "true" : "false");
      localStorage.setItem("roxyLiveWakeMode", $("wakeMode").checked ? "true" : "false");
      localStorage.setItem("roxyLiveWakeWord", $("wakeWord").value || "Roxy");
      localStorage.setItem("roxyLiveVoiceName", $("voiceSelect").value || "");
      localStorage.setItem("roxyLiveVoiceRate", $("voiceRate").value || "0.9");
      localStorage.setItem("roxyLiveVoicePitch", $("voicePitch").value || "1.1");
      localStorage.setItem("roxyLivePreferredName", $("preferredName").value || "");
      localStorage.setItem("roxyLiveLanguage", $("language").value || "es");
      localStorage.setItem("roxyLiveTradingMode", $("tradingMode").value || "paper");
      localStorage.setItem("roxyLiveDefaultSymbol", $("defaultSymbol").value || "SPY");
      localStorage.setItem("roxyLiveWatchlist", $("watchlist").value || "");
    }

    function appendMessage(role, text, meta) {
      const node = document.createElement("div");
      node.className = "msg " + role;
      const label = role === "roxy" ? "Roxy" : role === "user" ? "Tu" : "Sistema";
      node.innerHTML = "<b></b><span></span>";
      node.querySelector("b").textContent = meta ? label + " · " + meta : label;
      node.querySelector("span").textContent = text || "";
      $("chat").appendChild(node);
      $("chat").scrollTop = $("chat").scrollHeight;
    }

    const suggestedActionPrompts = {
      ask_latest_opportunity: ["Oportunidad", "resumen de oportunidad"],
      ask_capabilities: ["Capacidades", "que puedes hacer"],
      ask_market_summary: ["Mercado", "resumen del mercado"],
      ask_market_session: ["Horario", "sesion de mercado"],
      market_session: ["Horario", "sesion de mercado"],
      connect_realtime_voice: ["Voz", "estado de roxy"],
      connect_news_source: ["Noticias", "analiza impacto de noticia: pega aqui el titular"],
      confirm_trade_guardrails: ["Guardrails", "puedo operar ahora"],
      run_scan: ["Datos", "frescura de datos"],
      support_resistance: ["Niveles", "soporte y resistencia"],
      technical_indicators: ["Indicadores", "indicadores tecnicos"],
      entry_checklist: ["Checklist", "checklist de entrada"],
      position_size: ["Sizing", "tamaño de posicion con capital 10000 riesgo 0.5%"],
      monitoring_plan: ["Monitoreo", "plan de monitoreo"],
      compare_opportunities: ["Ranking", "top oportunidades"],
      data_freshness: ["Datos", "frescura de datos"],
      set_alert: ["Alerta", "prepara alerta"],
      alert_draft: ["Alerta", "prepara alerta"],
      confirm_alert: ["Confirmar alerta", "prepara alerta"],
      trade_readiness: ["Decisión", "puedo operar ahora"],
      confirm_before_execution: ["Go/no-go", "puedo operar ahora"],
      show_risk_check: ["Riesgo", "explica riesgo entrada stop target"],
      show_trade_ticket: ["Ticket", "checklist de entrada"],
      require_explicit_confirmation: ["Confirmar", "puedo operar ahora"],
      ask_risk: ["Riesgo", "explica riesgo entrada stop target"],
      ask_why: ["Por qué", "por que?"],
      ask_followup: ["Sesión", "resumen de sesion"],
      review_learning_status: ["Aprendizaje", "aprendizaje"],
      review_feedback: ["Feedback", "aprendizaje"],
      keep_session_id: ["Sesión", "resumen de sesion"],
      enable_wake_roxy: ["Estado", "estado de roxy"],
      ask_news_impact: ["Impacto news", "analiza impacto de noticia: pega aqui el titular"],
    };

    function fallbackActionPrompt(action) {
      const label = (action || "").replace(/_/g, " ").replace(/\\b\\w/g, c => c.toUpperCase()).slice(0, 28);
      return [label || "Siguiente", (action || "").replace(/_/g, " ") || "que puedes hacer"];
    }

    function renderSuggestedActions(actions) {
      const target = $("nextActions");
      target.innerHTML = "";
      const unique = [];
      for (const action of Array.isArray(actions) ? actions : []) {
        if (action && !unique.includes(action)) unique.push(action);
      }
      for (const action of unique.slice(0, 6)) {
        const config = suggestedActionPrompts[action] || fallbackActionPrompt(action);
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = config[0];
        button.title = action;
        button.dataset.prompt = config[1];
        button.addEventListener("click", () => {
          $("query").value = config[1];
          send();
        });
        target.appendChild(button);
      }
    }

    function renderActiveContext(context) {
      const ctx = context && typeof context === "object" ? context : {};
      const parts = [];
      if (ctx.active_symbol) parts.push(ctx.active_symbol);
      if (ctx.active_intent) parts.push(ctx.active_intent);
      if (ctx.needs_confirmation) parts.push("confirmar");
      const actions = Array.isArray(ctx.next_best_actions) ? ctx.next_best_actions : [];
      if (actions.length) parts.push(actions.slice(0, 2).join(", "));
      $("activeContext").textContent = parts.join(" · ") || "-";
      if (actions.length) renderSuggestedActions(actions);
    }

    function extractContextSymbol(text) {
      const blocked = ["ROXY", "I", "A", "OK", "BUY", "SELL", "WATCH", "WAIT", "READY", "BLOCKED", "LONG", "SHORT", "STOP", "TARGET"];
      const matches = (text || "").match(/\\b[A-Z][A-Z0-9.:-]{0,11}\\b/g) || [];
      return matches.map(symbol => symbol.toUpperCase()).find(symbol => !blocked.includes(symbol)) || "";
    }

    function currentTurnContext(state, text) {
      const actions = Array.isArray(state.suggested_actions) ? state.suggested_actions : [];
      return {
        active_intent: state.intent || "",
        active_symbol: state.active_symbol || extractContextSymbol([text, state.reply].join(" ")),
        active_topic: text || "",
        last_safety_level: state.safety_level || "",
        needs_confirmation: state.safety_level === "critical" || actions.includes("require_explicit_confirmation"),
        next_best_actions: actions,
      };
    }

    function setAvatar(state, emotion) {
      const avatar = $("avatar");
      avatar.className = "avatar " + (state || "ready");
      $("avatarText").textContent = [state || "ready", emotion || ""].filter(Boolean).join(" / ");
      updateVoicePresenceVisibility();
    }

    function updateVoiceDraftStatus() {
      const draft = (voiceDraftText || "").trim();
      const status = $("voiceDraftStatus");
      if (!status) return;
      status.textContent = draft ? "ready · " + (draft.length > 28 ? draft.slice(0, 28) + "..." : draft) : "-";
      status.title = draft;
    }

    function updateVoiceHeardStatus(transcript, isFinal, confidence) {
      const status = $("voiceHeardStatus");
      if (!status) return;
      const clean = (transcript || "").replace(/\s+/g, " ").trim();
      if (!clean) {
        status.textContent = "-";
        status.title = "";
        return;
      }
      const preview = clean.length > 42 ? clean.slice(0, 42) + "..." : clean;
      const confidenceText = Number.isFinite(confidence) && confidence > 0
        ? " · " + Math.round(confidence * 100) + "%"
        : "";
      status.textContent = (isFinal ? "final" : "oyendo") + " · " + preview + confidenceText;
      status.title = clean;
    }

    function voiceConfidenceIsLow(confidence) {
      return Number.isFinite(confidence) && confidence > 0 && confidence < lowVoiceConfidenceThreshold;
    }

    function latestHeardTranscript() {
      const heard = $("voiceHeardStatus");
      const fromHeard = heard && heard.title ? heard.title.trim() : "";
      return fromHeard || ($("query").value || "").replace(/\s+/g, " ").trim();
    }

    function speakLatestHeardTranscript() {
      const language = $("language").value || "es";
      const transcript = latestHeardTranscript();
      const message = transcript
        ? localizedText("Escuche: " + transcript, "I heard: " + transcript, language)
        : localizedText(
          "Todavia no tengo una frase escuchada para leer.",
          "I do not have a heard phrase to read yet.",
          language
        );
      speakLocalControlMessage(message, language, "voice: heard readback", "voice-heard");
      return true;
    }

    function voiceModeActive() {
      return !manualStop && ($("conversationMode").checked || $("wakeMode").checked);
    }

    function voicePresenceVisible() {
      return Boolean(voicePresenceActive || voiceModeActive() || isListening || isSpeaking);
    }

    function updateVoicePresenceVisibility() {
      const visible = voicePresenceVisible();
      $("roxyLiveMain").classList.toggle("voice-idle", !visible);
      $("avatar").setAttribute("aria-hidden", visible ? "false" : "true");
    }

    function setVoicePresenceActive(active) {
      voicePresenceActive = Boolean(active);
      updateVoicePresenceVisibility();
    }

    function releaseVoicePresenceIfIdle() {
      if (!voiceModeActive() && !isListening && !isSpeaking) voicePresenceActive = false;
      updateVoicePresenceVisibility();
    }

    function scheduleListen() {
      clearTimeout(pendingListenTimer);
      if ((!$("conversationMode").checked && !$("wakeMode").checked) || manualStop || isListening || isSpeaking) return;
      pendingListenTimer = setTimeout(() => {
        if ((!$("conversationMode").checked && !$("wakeMode").checked) || manualStop || isListening || isSpeaking) return;
        startListening();
      }, 850);
    }

    function normalizeSpeech(text) {
      return (text || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\\u0300-\\u036f]/g, "")
        .replace(/[^a-z0-9ñ\\s]/g, " ")
        .replace(/\\s+/g, " ")
        .trim();
    }

    function stopAll(reason) {
      manualStop = true;
      clearTimeout(pendingListenTimer);
      cancelActiveAssist();
      lastHandledVoiceText = "";
      lastHandledVoiceAt = 0;
      if (recognition) recognition.stop();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      isSpeaking = false;
      isListening = false;
      setAvatar("ready", $("emotion").textContent);
      releaseVoicePresenceIfIdle();
      if (reason) appendMessage("system", reason, "voice-control");
    }

    function prepareListeningTurn() {
      setVoicePresenceActive(true);
      clearTimeout(pendingListenTimer);
      cancelActiveAssist();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      isSpeaking = false;
      manualStop = false;
      updateVoiceHeardStatus("", false);
    }

    function isDuplicateFinalTranscript(text) {
      const normalized = normalizeSpeech(text);
      const now = Date.now();
      const isDuplicate = normalized && normalized === lastHandledVoiceText && (now - lastHandledVoiceAt) < duplicateVoiceWindowMs;
      if (normalized && !isDuplicate) {
        lastHandledVoiceText = normalized;
        lastHandledVoiceAt = now;
      }
      return Boolean(isDuplicate);
    }

    function isRecoverableMicError(error) {
      return ["no-speech", "aborted"].includes(error || "");
    }

    function recoverFromMicError(error) {
      $("voiceStatus").textContent = "mic waiting · " + error;
      $("events").textContent = "voice: retry after " + error;
      isListening = false;
      manualStop = false;
      setAvatar("ready", $("emotion").textContent);
      scheduleListen();
    }

    function micErrorMessage(error, language) {
      const key = error || "unknown";
      if (key === "unsupported") {
        return localizedText(
          "Este navegador no soporta reconocimiento de voz. Abre Roxy en Chrome o Edge y vuelve a pulsar Hablar.",
          "This browser does not support speech recognition. Open Roxy in Chrome or Edge and press Talk again.",
          language
        );
      }
      if (["not-allowed", "service-not-allowed", "permission-denied"].includes(key)) {
        return localizedText(
          "Microfono bloqueado. Permite el microfono para 127.0.0.1 en el navegador y vuelve a pulsar Hablar.",
          "Microphone is blocked. Allow microphone access for 127.0.0.1 in the browser, then press Talk again.",
          language
        );
      }
      if (key === "audio-capture") {
        return localizedText(
          "No encuentro un microfono disponible. Revisa el dispositivo de entrada y vuelve a pulsar Hablar.",
          "I cannot find an available microphone. Check the input device, then press Talk again.",
          language
        );
      }
      return localizedText(
        "Microfono: " + key + ". Pulsa Parar, revisa permisos o dispositivo, y vuelve a intentar.",
        "Microphone: " + key + ". Press Stop, check permissions or device, and try again.",
        language
      );
    }

    function handleFatalMicError(error) {
      const key = error || "unknown";
      const language = $("language").value || "es";
      const permissionBlocked = ["not-allowed", "service-not-allowed", "permission-denied"].includes(key);
      const unsupported = key === "unsupported";
      const message = micErrorMessage(key, language);
      $("reply").textContent = message;
      $("voiceStatus").textContent = unsupported ? "mic no soportado" : permissionBlocked ? "mic blocked · " + key : "mic error · " + key;
      $("events").textContent = unsupported ? "voice: mic unsupported" : permissionBlocked ? "voice: mic blocked" : "voice: mic error";
      appendMessage("system", message, "voice-error");
      isListening = false;
      manualStop = true;
      setAvatar("blocked", "serious");
      releaseVoicePresenceIfIdle();
    }

    function extractWakeCommand(text) {
      const wake = normalizeSpeech($("wakeWord").value || "Roxy");
      const normalized = normalizeSpeech(text);
      const words = normalized.split(" ").filter(Boolean);
      const wakeIndex = words.findIndex(word => word === wake || word.includes(wake));
      if (wakeIndex < 0) return null;
      return words.slice(wakeIndex + 1).join(" ").trim();
    }

    function languageCommandTarget(command) {
      const normalized = normalizeSpeech(command);
      const englishPhrases = [
        "english", "ingles", "en ingles", "habla ingles", "hablar ingles",
        "speak english", "speak in english", "english mode", "modo ingles",
        "cambia a ingles", "change to english"
      ];
      const spanishPhrases = [
        "espanol", "spanish", "en espanol", "habla espanol", "hablar espanol",
        "speak spanish", "speak in spanish", "spanish mode", "modo espanol",
        "cambia a espanol", "change to spanish"
      ];
      if (englishPhrases.some(phrase => normalized === phrase || normalized.includes(phrase))) return "en";
      if (spanishPhrases.some(phrase => normalized === phrase || normalized.includes(phrase))) return "es";
      return "";
    }

    function commandMatches(command, phrases) {
      const normalized = normalizeSpeech(command);
      return phrases.some(phrase => normalized === phrase || normalized.includes(phrase));
    }

    function localizedText(esText, enText, languageOverride) {
      const language = languageOverride || $("language").value || "es";
      return language === "en" ? enText : esText;
    }

    function speakLocalControlMessage(message, language, eventName, messageType) {
      $("reply").textContent = message;
      $("events").textContent = eventName;
      appendMessage("system", message, messageType || "voice-control");
      if (!speak(message, language)) {
        scheduleListen();
        releaseVoicePresenceIfIdle();
      }
    }

    function applyVoiceStopCommand(command) {
      const normalized = normalizeSpeech(command);
      const stopPhrases = [
        "silencio", "para", "parar", "calla", "callate", "detente",
        "stop", "stop listening", "be quiet", "silence", "quiet"
      ];
      if (!stopPhrases.includes(normalized)) return false;
      const language = $("language").value || "es";
      const message = localizedText("Escucha detenida.", "Listening stopped.", language);
      stopAll(message);
      $("reply").textContent = message;
      $("events").textContent = "voice: stop";
      return true;
    }

    function setVoiceRateFromCommand(rate, esMessage, enMessage, eventName) {
      const bounded = Math.min(1.15, Math.max(0.75, Number(rate || 0.9)));
      const language = $("language").value || "es";
      $("voiceRate").value = bounded.toFixed(2);
      saveSettings();
      updateVoiceDiagnostics(language);
      speakLocalControlMessage(localizedText(esMessage, enMessage, language), language, eventName, "voice-profile");
      return true;
    }

    function applyVoicePaceCommand(command) {
      if (commandMatches(command, [
        "voz mas lenta", "habla mas lento", "mas lento", "lee mas lento",
        "slower voice", "speak slower", "read slower", "slower"
      ])) {
        return setVoiceRateFromCommand(
          Number($("voiceRate").value || 0.9) - 0.1,
          "Voz mas lenta.",
          "Slower voice.",
          "voice: pace slower"
        );
      }
      if (commandMatches(command, [
        "voz mas rapida", "habla mas rapido", "mas rapido", "lee mas rapido",
        "faster voice", "speak faster", "read faster", "faster"
      ])) {
        return setVoiceRateFromCommand(
          Number($("voiceRate").value || 0.9) + 0.1,
          "Voz mas rapida.",
          "Faster voice.",
          "voice: pace faster"
        );
      }
      if (commandMatches(command, [
        "voz normal", "velocidad normal", "ritmo normal", "normal voice",
        "normal speed", "default voice speed"
      ])) {
        return setVoiceRateFromCommand(0.9, "Voz a velocidad normal.", "Voice speed reset.", "voice: pace normal");
      }
      return false;
    }

    function applyVoiceSpeechOutputCommand(command) {
      const normalized = normalizeSpeech(command);
      const offPhrases = ["sin voz", "no hables", "voz off", "apaga voz", "mute voice", "voice off", "speech off"];
      const onPhrases = ["con voz", "habla de nuevo", "voz on", "activa voz", "unmute voice", "voice on", "speech on"];
      if (offPhrases.includes(normalized)) {
        const language = $("language").value || "es";
        const message = localizedText("Voz automatica apagada.", "Automatic voice is off.", language);
        $("autoSpeak").checked = false;
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
        saveSettings();
        $("reply").textContent = message;
        $("events").textContent = "voice: speech off";
        appendMessage("system", message, "voice-profile");
        scheduleListen();
        releaseVoicePresenceIfIdle();
        return true;
      }
      if (onPhrases.includes(normalized)) {
        const language = $("language").value || "es";
        $("autoSpeak").checked = true;
        saveSettings();
        speakLocalControlMessage(
          localizedText("Voz automatica activada.", "Automatic voice is on.", language),
          language,
          "voice: speech on",
          "voice-profile"
        );
        return true;
      }
      return false;
    }

    function applyVoiceSendModeCommand(command) {
      const normalized = normalizeSpeech(command);
      const manualPhrases = ["modo dictado", "no enviar solo", "no enviar automatico", "dictation mode", "manual send"];
      const autoPhrases = ["enviar al terminar", "envia al terminar", "auto enviar", "auto send", "send when done"];
      if (manualPhrases.includes(normalized)) {
        const language = $("language").value || "es";
        $("autoSendVoice").checked = false;
        saveSettings();
        speakLocalControlMessage(
          localizedText("Modo dictado activo. Revisare el texto antes de enviar.", "Dictation mode active. Review the text before sending.", language),
          language,
          "voice: autosend off",
          "voice-profile"
        );
        return true;
      }
      if (autoPhrases.includes(normalized)) {
        const language = $("language").value || "es";
        $("autoSendVoice").checked = true;
        saveSettings();
        speakLocalControlMessage(
          localizedText("Envio automatico al terminar activado.", "Auto-send when done is on.", language),
          language,
          "voice: autosend on",
          "voice-profile"
        );
        return true;
      }
      return false;
    }

    function voiceDraftAction(command) {
      const normalized = normalizeSpeech(command);
      const sendPhrases = ["enviar", "envia", "mandar", "manda eso", "envia eso", "enviar ahora", "send", "send it", "send now"];
      const clearPhrases = ["borrar", "borra", "limpiar", "limpia", "descartar", "clear", "clear draft", "discard", "discard draft"];
      const readPhrases = ["leer borrador", "revisar borrador", "repite borrador", "que escribi", "read draft", "review draft", "repeat draft"];
      if (sendPhrases.includes(normalized)) return "send";
      if (clearPhrases.includes(normalized)) return "clear";
      if (readPhrases.includes(normalized)) return "read";
      return "";
    }

    const voiceDraftCorrectionPrefixes = [
      "corrige borrador", "corrige el borrador", "corrige texto", "corrige el texto",
      "corrige a", "reemplaza borrador", "reemplaza el borrador", "reemplaza con",
      "cambia borrador a", "cambia el borrador a", "correct draft", "correct draft to",
      "replace draft", "replace draft with", "replace with", "change draft to"
    ];

    function voiceDraftCorrectionText(command) {
      return commandRemainder(command, voiceDraftCorrectionPrefixes);
    }

    function isVoiceDraftCorrectionRequest(command) {
      const normalized = normalizeSpeech(command);
      return voiceDraftCorrectionPrefixes.some(prefix => normalized === prefix);
    }

    function voiceCommandCandidate(text) {
      const wakeCommand = extractWakeCommand(text);
      return wakeCommand !== null ? wakeCommand : text;
    }

    function isVoiceDraftAction(command) {
      return Boolean(voiceDraftAction(command) || voiceDraftCorrectionText(command) || isVoiceDraftCorrectionRequest(command));
    }

    function setVoiceDraft(text) {
      const draft = (text || "").trim();
      if (!draft) return false;
      const language = $("language").value || "es";
      voiceDraftText = draft;
      updateVoiceDraftStatus();
      $("query").value = draft;
      const message = localizedText(
        "Borrador listo. Di: Roxy, enviar para mandarlo.",
        "Draft ready. Say: Roxy, send it to send.",
        language
      );
      $("reply").textContent = message;
      $("events").textContent = "voice: draft ready";
      appendMessage("system", message, "voice-draft");
      scheduleListen();
      releaseVoicePresenceIfIdle();
      return true;
    }

    function voiceDraftForAction(command) {
      const draft = (voiceDraftText || $("query").value || "").trim();
      if (!draft) return "";
      const normalizedDraft = normalizeSpeech(draft);
      const normalizedCommand = normalizeSpeech(command);
      const normalizedWakeCommand = [normalizeSpeech($("wakeWord").value || "Roxy"), normalizedCommand].filter(Boolean).join(" ");
      if (normalizedDraft === normalizedCommand || normalizedDraft === normalizedWakeCommand) return "";
      return draft;
    }

    function applyVoiceDraftCorrectionCommand(command) {
      const replacement = voiceDraftCorrectionText(command);
      const language = $("language").value || "es";
      if (!replacement) {
        if (!isVoiceDraftCorrectionRequest(command)) return false;
        speakLocalControlMessage(
          localizedText(
            "Di: Roxy, corrige borrador, seguido del texto correcto.",
            "Say: Roxy, replace draft with, followed by the correct text.",
            language
          ),
          language,
          "voice: draft correction empty",
          "voice-draft"
        );
        return true;
      }
      voiceDraftText = replacement;
      updateVoiceDraftStatus();
      updateVoiceHeardStatus(replacement, true);
      $("query").value = replacement;
      speakLocalControlMessage(
        localizedText(
          "Borrador corregido. Di: Roxy, enviar para mandarlo.",
          "Draft corrected. Say: Roxy, send it to send.",
          language
        ),
        language,
        "voice: draft corrected",
        "voice-draft"
      );
      return true;
    }

    function holdLowConfidenceVoiceDraft(text, confidence) {
      const language = $("language").value || "es";
      const percent = Math.round(confidence * 100);
      voiceDraftText = text;
      updateVoiceDraftStatus();
      updateVoiceHeardStatus(text, true, confidence);
      $("query").value = text;
      const message = localizedText(
        "No lo envio todavia: confianza de voz " + percent + "%. Revisa el borrador y di: Roxy, enviar.",
        "I am not sending it yet: voice confidence " + percent + "%. Review the draft and say: Roxy, send it.",
        language
      );
      $("reply").textContent = message;
      $("events").textContent = "voice: low confidence draft";
      appendMessage("system", message, "voice-draft");
      if (!speak(message, language)) {
        scheduleListen();
        releaseVoicePresenceIfIdle();
      }
    }

    function voiceExecutionIntent(text) {
      const normalized = normalizeSpeech(text);
      if (!normalized) return false;
      const directPrefixes = [
        "buy", "sell", "short", "cover",
        "compra", "comprar", "vende", "vender",
        "ejecuta", "ejecutar", "abre posicion", "abrir posicion",
        "cierra posicion", "cerrar posicion"
      ];
      if (directPrefixes.some(prefix => normalized === prefix || normalized.startsWith(prefix + " "))) return true;
      const orderPhrases = [
        "send order", "place order", "execute order", "market order",
        "manda orden", "envia orden", "pon orden", "ejecuta orden", "orden de mercado"
      ];
      return orderPhrases.some(phrase => normalized === phrase || normalized.includes(phrase));
    }

    function holdExecutionVoiceDraft(text) {
      const language = $("language").value || "es";
      voiceDraftText = text;
      updateVoiceDraftStatus();
      updateVoiceHeardStatus(text, true);
      $("query").value = text;
      const message = localizedText(
        "Esto parece una instruccion de ejecucion. Lo deje como borrador para revisar; ninguna orden fue enviada.",
        "This sounds like an execution instruction. I kept it as a draft for review; no order was sent.",
        language
      );
      $("reply").textContent = message;
      $("events").textContent = "voice: execution draft";
      appendMessage("system", message, "voice-safety");
      if (!speak(message, language)) {
        scheduleListen();
        releaseVoicePresenceIfIdle();
      }
    }

    function submitOrDraftVoicePrompt(text, confidence) {
      const prompt = (text || "").trim();
      if (!prompt) return;
      $("query").value = prompt;
      if ($("autoSendVoice").checked && voiceExecutionIntent(prompt)) {
        holdExecutionVoiceDraft(prompt);
        return;
      }
      if ($("autoSendVoice").checked && voiceConfidenceIsLow(confidence)) {
        holdLowConfidenceVoiceDraft(prompt, confidence);
        return;
      }
      if ($("autoSendVoice").checked) send();
      else setVoiceDraft(prompt);
    }

    function applyVoiceDraftActionCommand(command) {
      const action = voiceDraftAction(command);
      if (!action) return false;
      const language = $("language").value || "es";
      if (action === "send") {
        const draft = voiceDraftForAction(command);
        if (!draft) {
          speakLocalControlMessage(
            localizedText("No hay borrador listo para enviar.", "There is no draft ready to send.", language),
            language,
            "voice: draft empty",
            "voice-draft"
          );
          return true;
        }
        $("query").value = draft;
        voiceDraftText = "";
        updateVoiceDraftStatus();
        $("events").textContent = "voice: draft send";
        appendMessage("system", localizedText("Enviando borrador.", "Sending draft.", language), "voice-draft");
        send();
        return true;
      }
      if (action === "clear") {
        voiceDraftText = "";
        updateVoiceDraftStatus();
        $("query").value = "";
        speakLocalControlMessage(
          localizedText("Borrador borrado.", "Draft cleared.", language),
          language,
          "voice: draft cleared",
          "voice-draft"
        );
        return true;
      }
      const draft = voiceDraftForAction(command);
      speakLocalControlMessage(
        draft
          ? localizedText("Borrador: " + draft, "Draft: " + draft, language)
          : localizedText("No hay borrador listo.", "There is no draft ready.", language),
        language,
        "voice: draft read",
        "voice-draft"
      );
      return true;
    }

    function speakVoiceStatusBrief() {
      const language = $("language").value || "es";
      const mode = $("wakeMode").checked
        ? localizedText("Wake Roxy", "Wake Roxy", language)
        : $("conversationMode").checked
          ? localizedText("conversación continua", "continuous conversation", language)
          : localizedText("manual", "manual", language);
      const speech = $("autoSpeak").checked
        ? localizedText("voz activa", "speech on", language)
        : localizedText("voz apagada", "speech off", language);
      const sending = $("autoSendVoice").checked
        ? localizedText("envío automático", "auto-send", language)
        : localizedText("modo dictado", "dictation mode", language);
      const voiceName = $("voiceSelect").value || localizedText("voz del navegador", "browser voice", language);
      const symbol = ($("defaultSymbol").value || "SPY").trim().toUpperCase();
      const watchlist = parseWatchlist($("watchlist").value).slice(0, 4).join(", ") || symbol;
      const message = localizedText(
        "Estado de voz: modo " + mode + ", " + speech + ", " + sending + ". Voz: " + voiceName + ". Símbolo base: " + symbol + ". Watchlist: " + watchlist + ".",
        "Voice status: " + mode + ", " + speech + ", " + sending + ". Voice: " + voiceName + ". Default symbol: " + symbol + ". Watchlist: " + watchlist + ".",
        language
      );
      speakLocalControlMessage(message, language, "voice: local status", "voice-status");
      return true;
    }

    function applyVoiceLanguageCommand(languageValue) {
      const language = languageValue === "en" ? "en" : "es";
      const message = language === "en" ? "English mode." : "Modo español.";
      $("language").value = language;
      alignVoiceSelection(language);
      saveSettings();
      updateVoiceDiagnostics(language);
      if (recognition) recognition.lang = speechLang(language);
      $("reply").textContent = message;
      $("events").textContent = "voice: language " + language;
      appendMessage("system", message, "language");
      if (!speak(message, language)) scheduleListen();
    }

    function setVoiceModeState({conversationMode, wakeMode, eventName, esMessage, enMessage}) {
      if (typeof conversationMode === "boolean") $("conversationMode").checked = conversationMode;
      if (typeof wakeMode === "boolean") $("wakeMode").checked = wakeMode;
      manualStop = !($("conversationMode").checked || $("wakeMode").checked);
      saveSettings();
      updateVoiceDiagnostics();
      if (voiceModeActive()) setVoicePresenceActive(true);
      else releaseVoicePresenceIfIdle();
      const language = $("language").value || "es";
      const message = localizedText(esMessage, enMessage, language);
      speakLocalControlMessage(message, language, eventName, "voice-mode");
    }

    function applyVoiceListeningModeCommand(command) {
      if (commandMatches(command, [
        "modo siri", "activar modo siri", "activar wake", "wake on", "wake roxy on",
        "escucha siempre", "manos libres", "siri mode", "hands free", "always listen"
      ])) {
        setVoiceModeState({
          conversationMode: false,
          wakeMode: true,
          eventName: "voice: wake on",
          esMessage: "Modo Siri activo. Di Roxy antes de cada instrucción.",
          enMessage: "Siri-style mode active. Say Roxy before each instruction.",
        });
        return true;
      }
      if (commandMatches(command, [
        "modo conversacion", "activar conversacion", "conversacion continua", "sigue escuchando",
        "conversation mode", "continuous conversation", "keep listening", "keep listening mode"
      ])) {
        setVoiceModeState({
          conversationMode: true,
          wakeMode: false,
          eventName: "voice: conversation on",
          esMessage: "Modo conversación activo. Roxy seguirá escuchando después de responder.",
          enMessage: "Conversation mode active. Roxy will keep listening after each answer.",
        });
        return true;
      }
      if (commandMatches(command, [
        "apagar wake", "desactivar wake", "wake off", "wake roxy off",
        "apagar modo siri", "desactivar modo siri", "siri off"
      ])) {
        setVoiceModeState({
          wakeMode: false,
          eventName: "voice: wake off",
          esMessage: "Wake Roxy apagado.",
          enMessage: "Wake Roxy is off.",
        });
        return true;
      }
      if (commandMatches(command, [
        "apagar conversacion", "desactivar conversacion", "conversation off", "stop conversation mode",
        "continuous conversation off"
      ])) {
        setVoiceModeState({
          conversationMode: false,
          eventName: "voice: conversation off",
          esMessage: "Modo conversación apagado.",
          enMessage: "Conversation mode is off.",
        });
        return true;
      }
      if (commandMatches(command, ["modo manual", "manual mode", "escucha manual", "manual listening"])) {
        setVoiceModeState({
          conversationMode: false,
          wakeMode: false,
          eventName: "voice: manual mode",
          esMessage: "Modo manual activo. Pulsa Hablar cuando quieras hablar conmigo.",
          enMessage: "Manual mode active. Press Talk when you want to speak with me.",
        });
        return true;
      }
      return false;
    }

    function sendVoiceLearningPrompt(command) {
      if (commandMatches(command, [
        "aprendizaje", "estado aprendizaje", "que aprendiste", "que estas aprendiendo",
        "aprendiste algo", "learning", "learning status", "what did you learn",
        "what have you learned", "what are you learning"
      ])) {
        $("events").textContent = "voice: learning status";
        loadLearning({speakNow: true});
        return true;
      }
      if (commandMatches(command, [
        "fuentes", "fuentes conocimiento", "fuentes de conocimiento", "documentos",
        "sources", "knowledge sources", "source list", "documents"
      ])) {
        $("events").textContent = "voice: knowledge sources";
        loadSources({speakNow: true});
        return true;
      }
      return false;
    }

    function voiceFeedbackCommand(command) {
      const negativeNote = commandRemainder(command, [
        "eso no sirvio", "no sirvio", "no me sirvio", "no fue util", "respuesta mala",
        "bad answer", "that did not help", "not helpful", "not useful"
      ]);
      if (negativeNote || commandMatches(command, [
        "eso no sirvio", "no sirvio", "no me sirvio", "no fue util", "respuesta mala",
        "bad answer", "that did not help", "not helpful", "not useful",
        "mas corto", "mas claro", "demasiado largo", "too long", "be shorter", "be clearer"
      ])) {
        return {rating: "down", note: negativeNote || normalizeSpeech(command)};
      }
      const positiveNote = commandRemainder(command, [
        "eso sirvio", "si sirvio", "me sirvio", "sirvio", "respuesta util", "fue util",
        "good answer", "that helped", "helpful", "useful"
      ]);
      if (positiveNote || commandMatches(command, [
        "eso sirvio", "si sirvio", "me sirvio", "sirvio", "respuesta util", "fue util",
        "good answer", "that helped", "helpful", "useful"
      ])) {
        return {rating: "up", note: positiveNote};
      }
      return null;
    }

    function applyVoiceFeedbackCommand(command) {
      const feedback = voiceFeedbackCommand(command);
      if (!feedback) return false;
      if (feedback.note) $("feedbackNote").value = feedback.note;
      submitFeedback(feedback.rating, {speakNow: true});
      return true;
    }

    function conciseLastReplyText(text) {
      const source = (text || "").replace(/\\s+/g, " ").trim();
      if (!source) return "";
      const sentences = source.match(/[^.!?]+[.!?]?/g) || [source];
      const compact = sentences.slice(0, 2).join(" ").trim();
      return compact.length > 420 ? compact.slice(0, 417).trim() + "..." : compact;
    }

    function speakConciseLastReply() {
      const language = lastState.language || $("language").value || "es";
      if (!lastReply) {
        const message = localizedText(
          "No tengo una respuesta anterior para resumir.",
          "I do not have a previous answer to shorten.",
          language
        );
        speakLocalControlMessage(message, language, "voice: concise unavailable", "voice-followup");
        return true;
      }
      const compact = conciseLastReplyText(lastReply);
      const message = localizedText("Respuesta corta: " + compact, "Short version: " + compact, language);
      $("reply").textContent = message;
      $("events").textContent = "voice: concise answer";
      appendMessage("system", message, "voice-followup");
      if (!speak(message, language)) scheduleListen();
      return true;
    }

    function followupTopic() {
      return (lastQuery || $("query").value || lastReply || "").replace(/\\s+/g, " ").trim();
    }

    function sendVoiceFollowupPrompt(command) {
      const normalized = normalizeSpeech(command);
      const negativeFeedback = [
        "eso no sirvio", "no sirvio", "no me sirvio", "no fue util", "respuesta mala",
        "bad answer", "that did not help", "not helpful", "not useful"
      ];
      if (negativeFeedback.some(phrase => normalized === phrase || normalized.startsWith(phrase + " "))) return false;
      if (commandMatches(command, [
        "mas corto", "hazlo mas corto", "resumen corto", "resume eso", "resumelo",
        "shorter", "make it shorter", "short version", "summarize that"
      ])) return speakConciseLastReply();

      const language = $("language").value || "es";
      const topic = followupTopic();
      if (!topic) return false;
      let prompt = "";
      if (commandMatches(command, [
        "mas detalle", "explica mas", "amplia eso", "dame mas detalle",
        "more detail", "explain more", "expand that", "give more detail"
      ])) {
        prompt = language === "en" ? "give more detail about: " + topic : "explica con mas detalle: " + topic;
      } else if (commandMatches(command, [
        "pasos", "dame pasos", "pasos concretos", "plan paso a paso",
        "steps", "give me steps", "step by step", "concrete steps"
      ])) {
        prompt = language === "en" ? "give concrete next steps for: " + topic : "dame pasos concretos para: " + topic;
      } else if (commandMatches(command, [
        "explicalo simple", "mas simple", "en palabras simples", "simplifica eso",
        "explain simply", "simpler", "simple words", "make it simple"
      ])) {
        prompt = language === "en" ? "explain simply: " + topic : "explicalo simple: " + topic;
      }
      if (!prompt) return false;
      $("query").value = prompt;
      $("events").textContent = "voice: follow-up shortcut";
      appendMessage("system", "Voice follow-up: " + prompt, "voice-followup");
      if ($("autoSendVoice").checked) send();
      else setVoiceDraft(prompt);
      return true;
    }

    function repeatLastReplyByVoice() {
      const language = lastState.language || $("language").value || "es";
      if (!lastReply) {
        const message = localizedText(
          "No tengo una respuesta anterior para repetir.",
          "I do not have a previous answer to repeat.",
          language
        );
        speakLocalControlMessage(message, language, "voice: repeat unavailable", "voice-control");
        return;
      }
      $("reply").textContent = lastReply;
      $("events").textContent = "voice: repeat";
      appendMessage(
        "system",
        localizedText("Repitiendo la ultima respuesta.", "Repeating the last answer.", language),
        "voice-control"
      );
      if (!speak(lastReply, language)) scheduleListen();
    }

    function speakVoiceSample() {
      const language = $("language").value || "es";
      alignVoiceSelection(language);
      saveSettings();
      updateVoiceDiagnostics(language);
      const message = localizedText(
        "Hola, soy Roxy. Esta es mi voz clara y femenina. Te escucho y puedo ayudarte con mercado, noticias, riesgo y estrategia.",
        "Hello, I am Roxy. This is my clear feminine voice. I can listen and help with markets, news, risk, and strategy.",
        language
      );
      $("reply").textContent = message;
      $("events").textContent = "voice: test";
      appendMessage("system", message, "voice-test");
      if (!speak(message, language)) scheduleListen();
      return true;
    }

    function applyReceptionistVoicePreset() {
      const language = $("language").value || "es";
      const voice = alignVoiceSelection(language, {ignoreSelected: true});
      $("voiceRate").value = "0.9";
      $("voicePitch").value = language === "en" ? "1.05" : "1.1";
      $("autoSpeak").checked = true;
      saveSettings();
      updateVoiceDiagnostics(language);
      const voiceName = voice ? voice.name : localizedText("voz del navegador", "browser voice", language);
      const message = localizedText(
        "Voz clara activada. Usare " + voiceName + " con ritmo natural de recepcionista joven.",
        "Clear receptionist voice is active. I will use " + voiceName + " with a natural front-desk pace.",
        language
      );
      $("reply").textContent = message;
      $("events").textContent = "voice: receptionist preset";
      appendMessage("system", message, "voice-profile");
      if (!speak(message, language)) scheduleListen();
      return true;
    }

    function startGuidedVoiceSession() {
      const language = $("language").value || "es";
      $("autoSpeak").checked = true;
      $("autoSendVoice").checked = true;
      $("conversationMode").checked = true;
      $("wakeMode").checked = true;
      alignVoiceSelection(language);
      saveSettings();
      updateVoiceDiagnostics(language);
      manualStop = false;
      setVoicePresenceActive(true);
      const message = localizedText(
        "Modo voz listo. Pulsa Hablar y di Roxy antes de cada instruccion. Prueba: Roxy, briefing diario; Roxy, mercado; Roxy, puedo operar ahora; o Roxy, ayuda. No ejecutare operaciones sin confirmacion explicita.",
        "Voice mode is ready. Press Talk and say Roxy before each instruction. Try: Roxy, daily briefing; Roxy, market; Roxy, can I trade now; or Roxy, help. I will not execute trades without explicit confirmation.",
        language
      );
      speakLocalControlMessage(message, language, "voice: guided session", "voice-guide");
      return true;
    }

    function actionDisplayName(action) {
      const config = suggestedActionPrompts[action] || fallbackActionPrompt(action);
      return config[0] || (action || "").replace(/_/g, " ");
    }

    function activeSessionContext() {
      const ctx = currentTurnContext(lastState || {}, lastQuery || $("query").value || "");
      if (!Array.isArray(ctx.next_best_actions) || !ctx.next_best_actions.length) {
        ctx.next_best_actions = ["ask_market_summary", "ask_latest_opportunity"];
      }
      return ctx;
    }

    function sessionVoiceBrief() {
      const language = lastState.language || $("language").value || "es";
      const ctx = activeSessionContext();
      renderActiveContext(ctx);
      let message = "";
      if (!lastReply && !lastQuery) {
        message = localizedText(
          "Todavía no hay una conversación activa. Puedo empezar con mercado, oportunidades o estado de Roxy.",
          "There is no active conversation yet. I can start with market, opportunities, or Roxy status.",
          language
        );
      } else {
        const symbol = ctx.active_symbol || $("defaultSymbol").value || "-";
        const intent = ctx.active_intent || "-";
        const safety = ctx.last_safety_level || lastState.safety_level || "-";
        const actions = (ctx.next_best_actions || []).slice(0, 2).map(actionDisplayName).join(", ");
        message = localizedText(
          "Contexto actual: " + symbol + ". Tema: " + intent + ". Seguridad: " + safety + ". Siguiente: " + (actions || "resumen del mercado") + ".",
          "Current context: " + symbol + ". Topic: " + intent + ". Safety: " + safety + ". Next: " + (actions || "market summary") + ".",
          language
        );
      }
      speakLocalControlMessage(message, language, "voice: session brief", "voice-context");
      return true;
    }

    function speakVoiceOptionsBrief() {
      const language = lastState.language || $("language").value || "es";
      const pendingDraft = (voiceDraftText || "").trim();
      if (pendingDraft) {
        const message = localizedText(
          "Opciones de voz: hay un borrador pendiente. Puedes decir: Roxy, leer borrador; Roxy, enviar; o Roxy, borrar.",
          "Voice options: there is a pending draft. You can say: Roxy, read draft; Roxy, send it; or Roxy, clear draft.",
          language
        );
        speakLocalControlMessage(message, language, "voice: options", "voice-options");
        return true;
      }
      const ctx = activeSessionContext();
      renderActiveContext(ctx);
      const unique = [];
      for (const action of Array.isArray(ctx.next_best_actions) ? ctx.next_best_actions : []) {
        if (action && !unique.includes(action)) unique.push(action);
      }
      const rows = (unique.length ? unique : ["ask_market_summary", "ask_latest_opportunity"])
        .slice(0, 3)
        .map(action => {
          const config = suggestedActionPrompts[action] || fallbackActionPrompt(action);
          const prompt = nextActionPromptWithContext(action, config[1] || "resumen del mercado", ctx);
          return {label: config[0] || actionDisplayName(action), prompt};
        });
      const labels = rows.map(row => row.label).join(", ");
      const prompts = rows.map(row => "Roxy, " + row.prompt).join("; ");
      const message = localizedText(
        "Opciones de voz: " + labels + ". Puedes decir: " + prompts + ".",
        "Voice options: " + labels + ". You can say: " + prompts + ".",
        language
      );
      speakLocalControlMessage(message, language, "voice: options", "voice-options");
      return true;
    }

    function nextActionPromptWithContext(action, prompt, ctx) {
      const symbol = (ctx.active_symbol || "").trim().toUpperCase();
      if (!symbol || !prompt) return prompt;
      const symbolActions = new Set([
        "ask_risk", "show_risk_check", "entry_checklist", "monitoring_plan",
        "set_alert", "alert_draft", "confirm_alert", "show_trade_ticket",
        "position_size", "trade_readiness", "confirm_before_execution",
        "require_explicit_confirmation", "ask_why"
      ]);
      if (!symbolActions.has(action)) return prompt;
      return prompt.toUpperCase().includes(symbol) ? prompt : prompt + " " + symbol;
    }

    function speakNextStepBrief() {
      const language = lastState.language || $("language").value || "es";
      const pendingDraft = (voiceDraftText || "").trim();
      if (pendingDraft) {
        const message = localizedText(
          "Hay un borrador pendiente. Siguiente paso seguro: di Roxy, leer borrador; Roxy, enviar; o Roxy, borrar.",
          "There is a pending draft. Safe next step: say Roxy, read draft; Roxy, send it; or Roxy, clear draft.",
          language
        );
        speakLocalControlMessage(message, language, "voice: next step", "voice-context");
        return true;
      }

      const ctx = activeSessionContext();
      renderActiveContext(ctx);
      const actions = Array.isArray(ctx.next_best_actions) && ctx.next_best_actions.length
        ? ctx.next_best_actions
        : ["ask_market_summary"];
      const action = actions[0] || "ask_market_summary";
      const config = suggestedActionPrompts[action] || fallbackActionPrompt(action);
      const label = config[0] || actionDisplayName(action);
      const prompt = nextActionPromptWithContext(action, config[1] || "resumen del mercado", ctx);
      const safety = (ctx.last_safety_level || lastState.safety_level || "").toLowerCase();
      const guarded = safety === "critical" || actions.includes("confirm_before_execution") || actions.includes("require_explicit_confirmation");
      $("query").value = prompt;
      const message = localizedText(
        "Siguiente paso seguro: " + label + ". Dejé preparado: " + prompt + "." + (guarded ? " No ejecutes nada sin confirmación explícita." : ""),
        "Safe next step: " + label + ". I prepared: " + prompt + "." + (guarded ? " Do not execute anything without explicit confirmation." : ""),
        language
      );
      speakLocalControlMessage(message, language, "voice: next step", "voice-context");
      return true;
    }

    function explainVoiceCommands() {
      const language = $("language").value || "es";
      const message = localizedText(
        "Puedes decir: Roxy, iniciar voz; Roxy, modo Siri; Roxy, modo conversación; Roxy, modo semi auto; Roxy, modo dictado; Roxy, enviar; Roxy, que escuchaste; Roxy, corrige borrador comprar SPY; Roxy, estado de voz; Roxy, voz clara; Roxy, prueba tu voz; Roxy, opciones; Roxy, más corto; Roxy, más detalle; Roxy, pasos; Roxy, sin voz; Roxy, voz más lenta; Roxy, contexto actual; Roxy, qué sigue; Roxy, aprendizaje; Roxy, fuentes; Roxy, símbolo NVDA; Roxy, watchlist SPY QQQ NVDA; Roxy, mercado; Roxy, briefing diario; Roxy, top oportunidades; Roxy, horario de mercado; Roxy, frescura de datos; Roxy, puedo operar ahora; Roxy, niveles de SPY; Roxy, indicadores de SPY; Roxy, plan de monitoreo SPY; Roxy, prepara alerta SPY; Roxy, tamaño de posición SPY capital 10000 riesgo 0.5%; Roxy, noticia Tesla sube; Roxy, riesgo de SPY; Roxy, no sirvió, más corto; Roxy, repite; o Roxy, silencio.",
        "You can say: Roxy, start voice session; Roxy, Siri mode; Roxy, conversation mode; Roxy, semi auto mode; Roxy, dictation mode; Roxy, send it; Roxy, what did you hear; Roxy, replace draft with buy SPY; Roxy, voice status; Roxy, receptionist voice; Roxy, test voice; Roxy, options; Roxy, shorter; Roxy, give more detail; Roxy, steps; Roxy, voice off; Roxy, slower voice; Roxy, current context; Roxy, next step; Roxy, learning status; Roxy, sources; Roxy, symbol NVDA; Roxy, watchlist SPY QQQ NVDA; Roxy, market; Roxy, daily briefing; Roxy, top opportunities; Roxy, market hours; Roxy, data freshness; Roxy, can I trade now; Roxy, support and resistance SPY; Roxy, technical indicators SPY; Roxy, monitoring plan SPY; Roxy, set alert SPY; Roxy, position size SPY account 10000 risk 0.5%; Roxy, news impact Nvidia reports revenue; Roxy, risk SPY; Roxy, bad answer, be shorter; Roxy, repeat; or Roxy, stop.",
        language
      );
      speakLocalControlMessage(message, language, "voice: help", "voice-help");
    }

    function voiceNewsHeadline(command) {
      const normalized = normalizeSpeech(command);
      const impactPrefixes = [
        "impacto noticia", "impacto de noticia", "impacto del titular",
        "analiza noticia", "analiza la noticia", "analiza titular",
        "noticia", "titular", "sentimiento noticia", "sentimiento de noticia",
        "news impact", "headline impact", "analyze news", "analyze the news",
        "news sentiment", "headline", "news"
      ];
      for (const prefix of impactPrefixes) {
        if (normalized === prefix) return "";
        if (normalized.startsWith(prefix + " ")) return normalized.slice(prefix.length).trim();
      }
      return "";
    }

    function newsVoicePrompt(command) {
      const language = $("language").value || "es";
      const normalized = normalizeSpeech(command);
      const summaryPhrases = ["noticias", "noticias mercado", "actualidad", "mercado hoy", "news", "market news"];
      if (summaryPhrases.includes(normalized)) return language === "en" ? "news" : "noticias";
      const headline = voiceNewsHeadline(command);
      if (headline) {
        return (language === "en" ? "news impact: " : "analiza impacto de noticia: ") + headline;
      }
      if (commandMatches(command, ["impacto noticia", "impacto de noticia", "impacto titular", "news impact", "headline impact"])) {
        return language === "en" ? "news impact: paste the headline" : "analiza impacto de noticia: pega aqui el titular";
      }
      return "";
    }

    function sendVoiceNewsPrompt(command) {
      const prompt = newsVoicePrompt(command);
      if (!prompt) return false;
      $("query").value = prompt;
      $("events").textContent = "voice: news shortcut";
      appendMessage("system", "Voice shortcut: " + prompt, "voice-news");
      if ($("autoSendVoice").checked) send();
      else setVoiceDraft(prompt);
      return true;
    }

    function voiceSymbolBlocklist() {
      return new Set([
        "ROXY", "MERCADO", "RESUMEN", "DEL", "DE", "EL", "LA", "LOS", "LAS", "MARKET", "SUMMARY",
        "BRIEFING", "DAILY", "BRIEF", "TOP", "OPORTUNIDADES", "MEJORES", "OPPORTUNITIES", "BEST",
        "WATCHLIST", "VIGILA", "MI", "WATCH", "MY", "RIESGO", "EXPLICA", "ENTRADA", "TARGET",
        "RISK", "EXPLAIN", "ENTRY", "STOP", "CHECKLIST", "DATOS", "FRESCURA", "DATA",
        "FRESHNESS", "SOURCE", "STATUS", "PUEDO", "OPERAR", "AHORA", "CAN", "I", "TRADE",
        "NOW", "PARA", "FOR", "OF", "ABOUT", "ON", "EN", "CON", "WITH", "PLAN", "MONITOREO",
        "MONITORING", "MONITOR", "ALERTA", "ALERT", "DRAFT", "PREPARA", "PREPARAR", "PREPARE",
        "CREAR", "CREATE", "SET", "BORRADOR", "THE", "A", "AN", "TO", "AND", "OR", "USD", "USDT",
        "BASE", "SYMBOL", "TICKER", "ACTIVO", "LIST", "LISTA", "TRACKING", "SEGUIMIENTO",
        "ANALIZA", "ANALIZAR", "ANALYZE", "IMPACTO", "NOTICIA", "TITULAR", "HEADLINE",
        "SENTIMENT", "SENTIMIENTO",
        "HORARIO", "HOURS", "SESSION", "REGULAR", "EXTENDED", "ABIERTO", "CERRADO", "ACCIONES",
        "NIVELES", "NIVEL", "LEVEL", "LEVELS", "KEY", "KEYS", "PRICE", "SOPORTE", "RESISTENCIA",
        "SUPPORT", "RESISTANCE",
        "INDICADOR", "INDICADORES", "INDICATOR", "INDICATORS", "TECHNICAL", "TECNICO", "TÉCNICO",
        "EMA", "RSI", "MACD", "VWAP", "BOLLINGER", "VOLUME", "VOLUMEN", "MOVING", "AVERAGES",
        "MEDIAS", "MOVILES", "MÓVILES", "TAMANO", "TAMAÑO", "POSICION", "POSICIÓN", "POSITION",
        "SIZE", "SIZING", "CAPITAL", "CUENTA", "ACCOUNT", "EQUITY", "BALANCE",
      ]);
    }

    function preferredVoiceSymbols() {
      const symbols = new Set(["SPY", "QQQ", "AAPL", "NVDA", "TSLA", "MSFT", "META", "AMZN", "GOOGL", "GOOG", "BTC/USD", "ETH/USD", "SOL/USD"]);
      for (const symbol of parseWatchlist($("watchlist").value)) symbols.add(symbol);
      const defaultSymbol = ($("defaultSymbol").value || "").trim().toUpperCase();
      if (defaultSymbol) symbols.add(defaultSymbol);
      return symbols;
    }

    function normalizeVoiceSymbol(token, nextToken, preferredSymbols) {
      const upper = (token || "").toUpperCase();
      const next = (nextToken || "").toUpperCase();
      if (!upper || voiceSymbolBlocklist().has(upper)) return "";
      if (next === "USD" && ["BTC", "ETH", "SOL", "DOGE", "ADA", "XRP"].includes(upper)) return upper + "/USD";
      if (preferredSymbols.has(upper + "/USD")) return upper + "/USD";
      if (preferredSymbols.has(upper)) return upper;
      if (/^[A-Z][A-Z0-9.]{0,6}$/.test(upper) && !voiceSymbolBlocklist().has(upper)) return upper;
      return "";
    }

    function voiceCommandSymbol(command) {
      const normalized = normalizeSpeech(command);
      const tokens = normalized.split(" ").filter(Boolean);
      const preferredSymbols = preferredVoiceSymbols();
      for (let index = 0; index < tokens.length; index++) {
        const symbol = normalizeVoiceSymbol(tokens[index], tokens[index + 1], preferredSymbols);
        if (symbol) return symbol;
      }
      return "";
    }

    function voiceCommandSymbols(command) {
      const normalized = normalizeSpeech(command);
      const tokens = normalized.split(" ").filter(Boolean);
      const preferredSymbols = preferredVoiceSymbols();
      const symbols = [];
      for (let index = 0; index < tokens.length; index++) {
        const symbol = normalizeVoiceSymbol(tokens[index], tokens[index + 1], preferredSymbols);
        if (symbol && !symbols.includes(symbol)) symbols.push(symbol);
      }
      return symbols;
    }

    function withVoiceSymbol(prompt, command) {
      const symbol = voiceCommandSymbol(command);
      if (!symbol) return prompt;
      return prompt + " " + symbol;
    }

    function positionSizeVoicePrompt(command) {
      const language = $("language").value || "es";
      const prefixes = [
        "tamano de posicion", "tamano posicion", "tamaño de posicion", "tamaño posicion",
        "calcula tamano", "calcula tamaño", "calcula sizing", "sizing",
        "position size", "size position", "calculate size", "calculate sizing"
      ];
      const remainder = commandRemainder(command, prefixes);
      if (!remainder && !commandMatches(command, prefixes)) return "";
      const base = language === "en" ? "position size" : "tamaño de posicion";
      if (remainder) return base + " " + remainder;
      return withVoiceSymbol(base, command);
    }

    function commandRemainder(command, prefixes) {
      const normalized = normalizeSpeech(command);
      for (const prefix of prefixes) {
        if (normalized === prefix) return "";
        if (normalized.startsWith(prefix + " ")) return normalized.slice(prefix.length).trim();
      }
      return "";
    }

    function applyVoiceDefaultSymbol(command) {
      const remainder = commandRemainder(command, [
        "simbolo base", "default symbol", "base symbol", "ticker symbol", "simbolo", "ticker", "activo", "symbol"
      ]);
      if (!remainder) return false;
      const symbol = voiceCommandSymbol(remainder);
      if (!symbol) return false;
      const language = $("language").value || "es";
      $("defaultSymbol").value = symbol;
      saveSettings();
      const message = localizedText(
        "Símbolo base actualizado a " + symbol + ".",
        "Default symbol updated to " + symbol + ".",
        language
      );
      speakLocalControlMessage(message, language, "voice: profile symbol", "voice-profile");
      return true;
    }

    function applyVoiceWatchlist(command) {
      const remainder = commandRemainder(command, [
        "lista de seguimiento", "lista seguimiento", "mi watchlist", "watch list", "tracking list",
        "watchlist", "lista", "vigilar", "vigila", "watch"
      ]);
      if (!remainder) return false;
      const symbols = voiceCommandSymbols(remainder).slice(0, 20);
      if (!symbols.length) return false;
      const language = $("language").value || "es";
      $("watchlist").value = symbols.join(", ");
      saveSettings();
      const message = localizedText(
        "Watchlist actualizada: " + symbols.join(", ") + ".",
        "Watchlist updated: " + symbols.join(", ") + ".",
        language
      );
      speakLocalControlMessage(message, language, "voice: profile watchlist", "voice-profile");
      return true;
    }

    function voiceTradingModeTarget(command) {
      const normalized = normalizeSpeech(command);
      if (commandMatches(normalized, [
        "modo paper", "trading paper", "paper mode", "paper trading", "solo paper", "paper only"
      ])) return "paper";
      if (commandMatches(normalized, [
        "modo semi auto", "modo semiauto", "semi auto", "semiautomatico", "semi automatico",
        "semi auto mode", "semi automatic", "semi automatic mode"
      ])) return "semi-auto";
      if (commandMatches(normalized, [
        "modo full auto", "full auto", "full auto guarded", "full automatic guarded",
        "automatico protegido", "autonomo protegido", "modo autonomo protegido"
      ])) return "full-auto guarded";
      return "";
    }

    function applyVoiceTradingMode(command) {
      const mode = voiceTradingModeTarget(command);
      if (!mode) return false;
      const language = $("language").value || "es";
      $("tradingMode").value = mode;
      saveSettings();
      const label = mode === "paper" ? "paper" : mode === "semi-auto" ? "semi-auto" : "full-auto guarded";
      const message = localizedText(
        "Modo trading actualizado a " + label + ". Esto solo cambia el perfil local; no ejecuta ordenes.",
        "Trading mode updated to " + label + ". This only changes the local profile; it does not place orders.",
        language
      );
      speakLocalControlMessage(message, language, "voice: profile trading mode", "voice-profile");
      return true;
    }

    function handleVoiceProfileCommand(command) {
      return applyVoiceDefaultSymbol(command) || applyVoiceWatchlist(command) || applyVoiceTradingMode(command);
    }

    function marketVoicePrompt(command) {
      const language = $("language").value || "es";
      const sizingPrompt = positionSizeVoicePrompt(command);
      if (sizingPrompt) return sizingPrompt;
      const shortcuts = [
        {
          phrases: [
            "horario", "horario mercado", "horario de mercado", "sesion de mercado", "sesion mercado",
            "mercado abierto", "mercado cerrado", "market hours", "market session", "regular hours", "extended hours"
          ],
          es: "sesion de mercado",
          en: "market hours",
        },
        {
          phrases: ["mercado", "resumen mercado", "resumen del mercado", "market", "market summary"],
          es: "resumen del mercado",
          en: "market summary",
        },
        {
          phrases: ["briefing", "briefing diario", "daily briefing", "daily brief"],
          es: "briefing diario",
          en: "daily briefing",
        },
        {
          phrases: ["oportunidades", "top oportunidades", "mejores oportunidades", "opportunities", "top opportunities", "best opportunities"],
          es: "top oportunidades",
          en: "top opportunities",
        },
        {
          phrases: ["watchlist", "vigila watchlist", "vigila mi watchlist", "watch my watchlist"],
          es: "vigila mi watchlist",
          en: "watch my watchlist",
        },
        {
          phrases: ["riesgo", "explica riesgo", "entrada stop target", "risk", "explain risk", "entry stop target"],
          es: "explica riesgo entrada stop target",
          en: "explain entry stop target risk",
        },
        {
          phrases: [
            "niveles", "niveles clave", "soporte", "resistencia", "soporte resistencia",
            "soporte y resistencia", "support resistance", "support and resistance", "key levels", "price levels"
          ],
          es: "soporte y resistencia",
          en: "support and resistance",
        },
        {
          phrases: [
            "indicadores", "indicador", "indicadores tecnicos", "lectura tecnica", "medias moviles",
            "rsi", "macd", "vwap", "bollinger", "ema", "technical indicators", "indicators",
            "indicator", "technical read", "moving averages", "volume read"
          ],
          es: "indicadores tecnicos",
          en: "technical indicators",
        },
        {
          phrases: ["checklist", "checklist entrada", "checklist de entrada", "entry checklist"],
          es: "checklist de entrada",
          en: "entry checklist",
        },
        {
          phrases: [
            "monitoreo", "plan monitoreo", "plan de monitoreo", "monitorea", "monitorear",
            "monitoring", "monitoring plan", "monitor plan", "watch plan"
          ],
          es: "plan de monitoreo",
          en: "monitoring plan",
        },
        {
          phrases: [
            "alerta", "prepara alerta", "preparar alerta", "crear alerta", "borrador alerta",
            "set alert", "prepare alert", "alert draft", "create alert"
          ],
          es: "prepara alerta",
          en: "set alert",
        },
        {
          phrases: ["datos", "frescura datos", "frescura de datos", "data freshness", "source status"],
          es: "frescura de datos",
          en: "data freshness",
        },
        {
          phrases: ["puedo operar", "puedo operar ahora", "operar ahora", "can i trade", "can i trade now", "trade now"],
          es: "puedo operar ahora",
          en: "can I trade now",
        },
      ];
      const shortcut = shortcuts.find(item => commandMatches(command, item.phrases));
      if (!shortcut) return "";
      return withVoiceSymbol(language === "en" ? shortcut.en : shortcut.es, command);
    }

    function sendVoiceMarketPrompt(command) {
      const prompt = marketVoicePrompt(command);
      if (!prompt) return false;
      $("query").value = prompt;
      $("events").textContent = "voice: market shortcut";
      appendMessage("system", "Voice shortcut: " + prompt, "voice-market");
      if ($("autoSendVoice").checked) send();
      else setVoiceDraft(prompt);
      return true;
    }

    function handleVoiceControlCommand(command) {
      if (applyVoiceStopCommand(command)) return true;
      const language = languageCommandTarget(command);
      if (language) {
        applyVoiceLanguageCommand(language);
        return true;
      }
      if (commandMatches(command, [
        "iniciar voz", "activar voz guiada", "activar roxy", "empezar roxy",
        "iniciar conversacion", "empezar conversacion", "start voice", "start voice session",
        "start roxy", "voice setup", "guided voice"
      ])) return startGuidedVoiceSession();
      if (applyVoiceListeningModeCommand(command)) return true;
      if (applyVoicePaceCommand(command)) return true;
      if (applyVoiceSpeechOutputCommand(command)) return true;
      if (applyVoiceSendModeCommand(command)) return true;
      if (applyVoiceDraftCorrectionCommand(command)) return true;
      if (applyVoiceDraftActionCommand(command)) return true;
      if (commandMatches(command, [
        "probar voz", "prueba voz", "prueba tu voz", "escuchar voz", "muestra voz",
        "test voice", "voice test", "try voice", "try your voice", "sample voice"
      ])) return speakVoiceSample();
      if (commandMatches(command, [
        "voz clara", "voz femenina", "voz recepcionista", "arregla tu voz",
        "corrige tu voz", "voz natural", "clear voice", "female voice",
        "receptionist voice", "fix your voice", "natural voice"
      ])) return applyReceptionistVoicePreset();
      if (commandMatches(command, [
        "estado de voz", "estado voz", "diagnostico voz", "diagnostico de voz",
        "estado local", "estado de roxy local", "voice status", "voice diagnostics",
        "local status", "local voice status"
      ])) return speakVoiceStatusBrief();
      if (commandMatches(command, [
        "diagnostico", "diagnostico de roxy", "chequeo de roxy", "chequeo sistema",
        "estado del sistema", "revisa sistema", "system check", "diagnostics",
        "roxy diagnostics", "check system", "run diagnostics"
      ])) {
        runVoiceSystemCheck({speakNow: true});
        return true;
      }
      if (sendVoiceLearningPrompt(command)) return true;
      if (sendVoiceFollowupPrompt(command)) return true;
      if (applyVoiceFeedbackCommand(command)) return true;
      if (commandMatches(command, [
        "contexto actual", "brief local", "resumen local", "que recuerdas", "que recuerdas ahora",
        "donde vamos", "en que estamos", "current context", "session brief", "what do you remember",
        "what are we discussing", "where are we"
      ])) {
        return sessionVoiceBrief();
      }
      if (commandMatches(command, [
        "opciones", "opciones de voz", "que opciones tengo", "que puedo preguntar ahora",
        "acciones disponibles", "options", "voice options", "what can i ask next",
        "available actions", "what are my options"
      ])) {
        return speakVoiceOptionsBrief();
      }
      if (commandMatches(command, [
        "que escuchaste", "que oiste", "lee lo que escuchaste", "repite lo que escuchaste",
        "what did you hear", "read what you heard", "repeat what you heard", "what did i say"
      ])) {
        return speakLatestHeardTranscript();
      }
      if (commandMatches(command, [
        "que sigue", "que sigue ahora", "siguiente paso", "proximo paso", "proxima accion",
        "next step", "what next", "what should i do next", "next action"
      ])) {
        return speakNextStepBrief();
      }
      if (commandMatches(command, ["repite", "repetir", "repite eso", "otra vez", "dilo otra vez", "repeat", "repeat that", "say again", "say that again"])) {
        repeatLastReplyByVoice();
        return true;
      }
      if (commandMatches(command, ["ayuda", "comandos", "que puedo decir", "help", "commands", "what can i say"])) {
        explainVoiceCommands();
        return true;
      }
      if (handleVoiceProfileCommand(command)) return true;
      if (sendVoiceNewsPrompt(command)) return true;
      if (sendVoiceMarketPrompt(command)) return true;
      return false;
    }

    function handleFinalTranscript(text, confidence) {
      const finalText = (text || "").trim();
      if (!finalText) return;
      setVoicePresenceActive(true);
      updateVoiceHeardStatus(finalText, true, confidence);
      $("events").textContent = "voice: heard";
      if (isDuplicateFinalTranscript(finalText)) {
        $("events").textContent = "voice: duplicate ignored";
        releaseVoicePresenceIfIdle();
        return;
      }
      if ($("wakeMode").checked) {
        const command = extractWakeCommand(finalText);
        if (command === null) {
          $("events").textContent = "wake: esperando '" + ($("wakeWord").value || "Roxy") + "'";
          return;
        }
        if (!command) {
          $("query").value = "";
          $("reply").textContent = "Te escucho. Di: Roxy, seguido de tu pregunta.";
          speak("Te escucho.");
          return;
        }
        if (["para", "parar", "silencio", "calla", "callate", "detente", "stop"].includes(command)) {
          stopAll("Comando recibido: " + command);
          return;
        }
        if (handleVoiceControlCommand(command)) return;
        submitOrDraftVoicePrompt(command, confidence);
        return;
      }
      const manualWakeCommand = extractWakeCommand(finalText);
      if (manualWakeCommand !== null) {
        if (!manualWakeCommand) {
          $("query").value = "";
          $("reply").textContent = "Te escucho. Di: Roxy, seguido de tu pregunta.";
          speak("Te escucho.");
          return;
        }
        if (["para", "parar", "silencio", "calla", "callate", "detente", "stop"].includes(manualWakeCommand)) {
          stopAll("Comando recibido: " + manualWakeCommand);
          return;
        }
        if (handleVoiceControlCommand(manualWakeCommand)) return;
        submitOrDraftVoicePrompt(manualWakeCommand, confidence);
        return;
      }
      if (handleVoiceControlCommand(finalText)) return;
      submitOrDraftVoicePrompt(finalText, confidence);
    }

    function speechLang(languageValue) {
      return (languageValue || "es") === "en" ? "en-US" : "es-US";
    }

    function normalizedVoiceName(voice) {
      return (voice && voice.name ? voice.name : "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
    }

    function feminineVoiceNames(languageValue) {
      return (languageValue || "es") === "en"
        ? ["samantha", "ava", "victoria", "zira", "jenny", "aria", "sandy", "shelley", "flo", "karen", "female"]
        : ["paulina", "monica", "flo", "shelley", "sandy", "google espanol", "google us spanish", "sabina", "helena", "female"];
    }

    function masculineOrHeavyVoiceNames() {
      return [
        "eddy", "reed", "rocko", "grandpa", "grandma", "albert", "alex", "daniel",
        "fred", "ralph", "thomas", "jorge", "diego", "carlos"
      ];
    }

    function voiceIsFemininePreferred(voice, languageValue) {
      const name = normalizedVoiceName(voice);
      return feminineVoiceNames(languageValue).some(token => name.includes(token));
    }

    function voiceIsHeavyOrMasculine(voice) {
      const name = normalizedVoiceName(voice);
      return masculineOrHeavyVoiceNames().some(token => name.includes(token));
    }

    function receptionistVoiceScore(voice, languageValue) {
      if (!voiceMatchesLanguage(voice, languageValue)) return -1000;
      const name = normalizedVoiceName(voice);
      let score = 10;
      const preferred = feminineVoiceNames(languageValue);
      preferred.forEach((token, index) => {
        if (name.includes(token)) score += 100 - index * 4;
      });
      if (voiceIsFemininePreferred(voice, languageValue)) score += 15;
      if (voiceIsHeavyOrMasculine(voice)) score -= 250;
      if (name.includes("enhanced") || name.includes("premium") || name.includes("google")) score += 8;
      if ((voice.lang || "").toLowerCase() === speechLang(languageValue).toLowerCase()) score += 5;
      return score;
    }

    function voiceMatchesLanguage(voice, languageValue) {
      const voiceLang = (voice && voice.lang ? voice.lang : "").toLowerCase();
      const lang = languageValue || "es";
      return lang === "en" ? voiceLang.startsWith("en") : voiceLang.startsWith("es");
    }

    function chooseVoice(languageOverride, options) {
      const opts = options || {};
      const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
      const lang = languageOverride || $("language").value || "es";
      const selected = $("voiceSelect").value;
      if (selected && !opts.ignoreSelected) {
        const exact = voices.find(v => v.name === selected);
        if (exact && voiceMatchesLanguage(exact, lang) && !voiceIsHeavyOrMasculine(exact)) return exact;
      }
      const matching = voices.filter(v => voiceMatchesLanguage(v, lang));
      const preferred = matching
        .slice()
        .sort((a, b) => receptionistVoiceScore(b, lang) - receptionistVoiceScore(a, lang))[0];
      return preferred
        || matching.find(v => !voiceIsHeavyOrMasculine(v))
        || matching[0]
        || voices[0];
    }

    function alignVoiceSelection(languageValue, options) {
      const voice = chooseVoice(languageValue, options);
      const select = $("voiceSelect");
      if (voice && Array.from(select.options).some(o => o.value === voice.name)) {
        select.value = voice.name;
      }
      return voice;
    }

    function updateVoiceDiagnostics(languageOverride) {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      const ttsReady = "speechSynthesis" in window;
      const lang = languageOverride || $("language").value || "es";
      const voice = chooseVoice(lang);
      const parts = [
        SR ? "mic OK" : "mic no soportado",
        ttsReady ? "voz OK" : "voz no soportada",
        speechLang(lang),
      ];
      if (voice) parts.push(voice.name + " / " + voice.lang);
      $("voiceStatus").textContent = parts.join(" · ");
    }

    function syncLanguageFromState(state) {
      const language = state && (state.language === "en" || state.language === "es") ? state.language : "";
      if (language) {
        const changed = $("language").value !== language;
        const previousVoice = $("voiceSelect").value;
        if (changed) $("language").value = language;
        alignVoiceSelection(language);
        if (changed || previousVoice !== $("voiceSelect").value) saveSettings();
        return language;
      }
      return $("language").value || "es";
    }

    function populateVoices() {
      if (!("speechSynthesis" in window)) return;
      const select = $("voiceSelect");
      const voices = window.speechSynthesis.getVoices() || [];
      const selected = localStorage.getItem("roxyLiveVoiceName") || select.value;
      select.innerHTML = "";
      const sorted = voices.slice().sort((a, b) => {
        const aes = (a.lang || "").toLowerCase().startsWith("es") ? 0 : 1;
        const bes = (b.lang || "").toLowerCase().startsWith("es") ? 0 : 1;
        return aes - bes || (a.name || "").localeCompare(b.name || "");
      });
      for (const voice of sorted) {
        const option = document.createElement("option");
        option.value = voice.name;
        option.textContent = voice.name + " · " + voice.lang;
        select.appendChild(option);
      }
      const selectedVoice = voices.find(v => v.name === selected);
      const selectedWasHeavy = selectedVoice && voiceIsHeavyOrMasculine(selectedVoice);
      if (selected && Array.from(select.options).some(o => o.value === selected)) {
        select.value = selected;
      }
      const preferred = chooseVoice();
      const previous = select.value;
      if (preferred && Array.from(select.options).some(o => o.value === preferred.name)) select.value = preferred.name;
      if (selectedWasHeavy && previous !== select.value) {
        $("voiceRate").value = "0.9";
        $("voicePitch").value = "1.1";
      }
      if (previous !== select.value) saveSettings();
      updateVoiceDiagnostics();
    }

    function speak(text, languageOverride) {
      if (!text || !("speechSynthesis" in window)) return false;
      setVoicePresenceActive(true);
      const run = () => {
        const lang = languageOverride || $("language").value || "es";
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = speechLang(lang);
        utterance.rate = Number($("voiceRate").value || 0.9);
        utterance.pitch = Number($("voicePitch").value || 1.1);
        const voice = chooseVoice(lang);
        if (voice) utterance.voice = voice;
        utterance.onstart = () => {
          isSpeaking = true;
          updateVoiceDiagnostics(lang);
          setAvatar("speaking", $("emotion").textContent);
        };
        utterance.onend = () => {
          isSpeaking = false;
          setAvatar("ready", $("emotion").textContent);
          scheduleListen();
          releaseVoicePresenceIfIdle();
        };
        utterance.onerror = () => {
          isSpeaking = false;
          setAvatar("ready", $("emotion").textContent);
          scheduleListen();
          releaseVoicePresenceIfIdle();
        };
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      };
      if (window.speechSynthesis.getVoices().length === 0) {
        window.speechSynthesis.onvoiceschanged = run;
        setTimeout(run, 300);
      } else {
        run();
      }
      return true;
    }

    function cancelActiveAssist() {
      if (activeAssistController) {
        activeAssistController.abort();
        activeAssistController = null;
        $("events").textContent = "events: aborted";
      }
    }

    function isAbortError(err) {
      return err && (err.name === "AbortError" || String(err.message || "").toLowerCase().includes("abort"));
    }

    function assistTimeoutMs() {
      const configured = Number(window.__roxyAssistTimeoutMs || defaultAssistTimeoutMs);
      return Number.isFinite(configured) && configured > 0 ? configured : defaultAssistTimeoutMs;
    }

    function showAssistTimeout() {
      const message = "Roxy tardo demasiado en responder. Intenta de nuevo o revisa el servicio.";
      $("reply").textContent = message;
      $("events").textContent = "events: timeout";
      appendMessage("system", message, "timeout");
      settleAfterTurn(lastState || {});
    }

    function requestHeaders() {
      const headers = {"Content-Type": "application/json"};
      const key = $("apiKey").value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      return headers;
    }

    function parseWatchlist(value) {
      return (value || "")
        .split(/[,\\s]+/)
        .map(item => item.trim().toUpperCase())
        .filter(Boolean)
        .slice(0, 20);
    }

    function currentProfilePayload() {
      return {
        preferred_name: $("preferredName").value,
        language: $("language").value || "es",
        trading_mode: $("tradingMode").value,
        default_symbol: $("defaultSymbol").value,
        watchlist: parseWatchlist($("watchlist").value),
        voice_name: $("voiceSelect").value,
        voice_rate: Number($("voiceRate").value || 0.9),
        voice_pitch: Number($("voicePitch").value || 1.1),
      };
    }

    function requestBody(text) {
      return JSON.stringify({
        query: text,
        user: $("user").value || "local",
        session_id: session.value,
        profile: currentProfilePayload(),
      });
    }

    function showAssistError(status) {
      const message = "Error " + status + ": revisa VOICE_API_KEY o el servicio.";
      $("reply").textContent = message;
      appendMessage("system", message, "error");
      setAvatar("blocked", "serious");
    }

    function settleAfterTurn(state) {
      const blocked = state && (state.avatar_state === "blocked" || state.safety_level === "critical");
      const emotion = state && state.emotion ? state.emotion : $("emotion").textContent;
      isSpeaking = false;
      setAvatar(blocked ? "blocked" : "ready", blocked ? "serious" : emotion);
      scheduleListen();
      releaseVoicePresenceIfIdle();
    }

    function applyAssistState(state, text, options) {
      const opts = options || {};
      lastReply = state.reply || "";
      lastQuery = text;
      lastState = state || {};
      $("intent").textContent = state.intent || "-";
      $("avatarState").textContent = state.avatar_state || "-";
      $("emotion").textContent = state.emotion || "-";
      $("safety").textContent = state.safety_level || "-";
      $("priority").textContent = state.priority || "-";
      $("liveSource").textContent = state.needs_live_source ? "Needed" : "OK";
      $("latency").textContent = Number.isFinite(Number(state.server_latency_ms)) ? state.server_latency_ms + " ms" : "-";
      const activeLanguage = syncLanguageFromState(state);
      updateVoiceDiagnostics(activeLanguage);
      $("reply").textContent = lastReply || "(sin respuesta)";
      renderSuggestedActions(state.suggested_actions || []);
      renderActiveContext(currentTurnContext(state, text));
      if (Array.isArray(state.events) && opts.eventsText === undefined) {
        $("events").textContent = "events: " + (state.events.map(e => e.type).join(" -> ") || "-");
      }
      if (opts.eventsText !== undefined) $("events").textContent = opts.eventsText;
      if (opts.appendRoxy !== false) {
        appendMessage("roxy", lastReply || "(sin respuesta)", [state.intent, state.safety_level].filter(Boolean).join(" / "));
      }
      setAvatar(state.avatar_state || "speaking", state.emotion || "focused");
      if (opts.speakNow !== false && state.should_speak !== false && $("autoSpeak").checked) {
        if (!speak(lastReply, state.language || $("language").value)) settleAfterTurn(state);
      } else if (opts.scheduleAfter !== false) {
        settleAfterTurn(state);
      }
    }

    function parseSseBlock(block) {
      const lines = (block || "").split(/\\r?\\n/);
      let eventName = "message";
      const dataLines = [];
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      let payload = {};
      if (dataLines.length) {
        try { payload = JSON.parse(dataLines.join("\\n")); }
        catch (_err) { payload = {type: eventName, raw: dataLines.join("\\n")}; }
      }
      return {eventName, payload};
    }

    async function readAssistStream(res, text) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const eventNames = [];
      let finalState = null;
      let spoke = false;
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, {stream: true});
        const blocks = buffer.split("\\n\\n");
        buffer = blocks.pop() || "";
        for (const block of blocks) {
          if (!block.trim()) continue;
          const parsed = parseSseBlock(block);
          const payload = parsed.payload || {};
          const eventName = payload.type || parsed.eventName;
          eventNames.push(eventName);
          $("events").textContent = "events: " + eventNames.join(" -> ");
          if (eventName === "transcript_received") {
            setAvatar("listening", "attentive");
          } else if (eventName === "thinking") {
            setAvatar("thinking", "focused");
            $("reply").textContent = "Roxy esta pensando...";
          } else if (eventName === "reply_ready") {
            finalState = payload;
            applyAssistState(finalState, text, {
              eventsText: "events: " + eventNames.join(" -> "),
              speakNow: false,
              scheduleAfter: false,
            });
          } else if (eventName === "speak") {
            spoke = true;
            const started = finalState && $("autoSpeak").checked
              ? speak(finalState.reply || payload.text || "", finalState.language || payload.language || $("language").value)
              : false;
            if (!started) settleAfterTurn(finalState || payload);
          } else if (eventName === "error") {
            $("reply").textContent = payload.detail || "Error en streaming.";
            appendMessage("system", $("reply").textContent, "stream");
            setAvatar("blocked", "serious");
          }
        }
      }
      if (finalState && !spoke) settleAfterTurn(finalState);
      return Boolean(finalState);
    }

    async function sendViaStream(text, headers, body, signal) {
      if (typeof TextDecoder === "undefined") return false;
      const res = await fetch(assistStreamEndpoint, {method: "POST", headers, body, signal});
      if (!res.ok) {
        showAssistError(res.status);
        return true;
      }
      if (!res.body || !res.body.getReader) return false;
      const handled = await readAssistStream(res, text);
      return handled;
    }

    async function sendViaState(text, headers, body, signal) {
      const res = await fetch("/v1/assist/state", {method: "POST", headers, body, signal});
      if (!res.ok) {
        showAssistError(res.status);
        return;
      }
      const state = await res.json();
      applyAssistState(state, text);
    }

    async function send() {
      const text = $("query").value.trim();
      if (!text) return;
      voiceDraftText = "";
      updateVoiceDraftStatus();
      saveSettings();
      setAvatar("thinking", "focused");
      $("reply").textContent = "Roxy esta pensando...";
      renderSuggestedActions([]);
      appendMessage("user", text, new Date().toLocaleTimeString());
      const headers = requestHeaders();
      const body = requestBody(text);
      cancelActiveAssist();
      const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
      activeAssistController = controller;
      let timedOut = false;
      const timeoutId = controller ? setTimeout(() => {
        if (activeAssistController === controller) {
          timedOut = true;
          controller.abort();
        }
      }, assistTimeoutMs()) : null;
      try {
        try {
          if (await sendViaStream(text, headers, body, controller ? controller.signal : undefined)) return;
        } catch (err) {
          if (isAbortError(err)) {
            if (timedOut) showAssistTimeout();
            else if (activeAssistController === controller) settleAfterTurn(lastState || {});
            return;
          }
          appendMessage("system", "Streaming no disponible, usando respuesta normal.", "stream");
        }
        try {
          await sendViaState(text, headers, body, controller ? controller.signal : undefined);
        } catch (err) {
          if (!isAbortError(err)) throw err;
          if (timedOut) showAssistTimeout();
          else if (activeAssistController === controller) settleAfterTurn(lastState || {});
        }
      } finally {
        if (timeoutId) clearTimeout(timeoutId);
        if (activeAssistController === controller) activeAssistController = null;
      }
    }

    async function loadMemory() {
      saveSettings();
      const headers = {};
      const key = $("apiKey").value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      const res = await fetch("/v1/assist/session/" + encodeURIComponent(session.value) + "?limit=12", {headers});
      if (!res.ok) {
        appendMessage("system", "No pude cargar memoria: " + res.status, "memory");
        return;
      }
      const memory = await res.json();
      const turns = Array.isArray(memory.recent_turns) ? memory.recent_turns : [];
      renderActiveContext(memory.active_context || {});
      appendMessage("system", "Memoria cargada: " + turns.length + " turno(s). Ultima intencion: " + (memory.last_intent || "-"), "memory");
      for (const turn of turns.slice(-6)) {
        if (turn.query) appendMessage("user", turn.query, "memoria");
        if (turn.reply) appendMessage("roxy", turn.reply, turn.intent || "memoria");
      }
    }

    async function saveProfile() {
      saveSettings();
      const headers = {"Content-Type": "application/json"};
      const key = $("apiKey").value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      const profile = currentProfilePayload();
      const res = await fetch("/v1/profile", {
        method: "POST",
        headers,
        body: JSON.stringify({user: $("user").value || "local", profile})
      });
      if (!res.ok) {
        appendMessage("system", "No pude guardar perfil: " + res.status, "profile");
        return;
      }
      appendMessage("system", "Perfil guardado. Roxy usara estas preferencias en la conversacion.", "profile");
    }

    async function loadProfile() {
      const headers = {};
      const key = $("apiKey").value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      const user = encodeURIComponent($("user").value || "local");
      const res = await fetch("/v1/profile/" + user, {headers});
      if (!res.ok) {
        appendMessage("system", "No pude cargar perfil: " + res.status, "profile");
        return;
      }
      const profile = await res.json();
      $("preferredName").value = profile.preferred_name || "";
      $("language").value = profile.language || "es";
      $("tradingMode").value = profile.trading_mode || "paper";
      $("defaultSymbol").value = profile.default_symbol || "SPY";
      $("watchlist").value = Array.isArray(profile.watchlist) ? profile.watchlist.join(", ") : "";
      if (profile.voice_rate) $("voiceRate").value = profile.voice_rate;
      else $("voiceRate").value = "0.9";
      if (profile.voice_pitch) $("voicePitch").value = profile.voice_pitch;
      else $("voicePitch").value = "1.1";
      if (profile.voice_name) $("voiceSelect").value = profile.voice_name;
      alignVoiceSelection(profile.language || $("language").value || "es");
      saveSettings();
      appendMessage("system", "Perfil cargado.", "profile");
    }

    async function loadSources(options) {
      const opts = options || {};
      const headers = requestHeaders();
      const res = await fetch("/v1/knowledge/sources", {headers});
      if (!res.ok) {
        const message = localizedText(
          "No pude cargar fuentes: " + res.status,
          "I could not load sources: " + res.status,
          $("language").value || "es"
        );
        appendMessage("system", message, "sources");
        if (opts.speakNow) speak(message, $("language").value || "es");
        return;
      }
      const payload = await res.json();
      const sources = Array.isArray(payload.sources) ? payload.sources : [];
      $("sources").innerHTML = "";
      for (const source of sources) {
        const node = document.createElement("div");
        node.className = "source";
        const state = source.exists ? "disponible" : "faltante";
        const size = source.size_bytes ? Math.round(source.size_bytes / 1024) + " KB" : "0 KB";
        node.innerHTML = "<b></b><span></span>";
        node.querySelector("b").textContent = source.path || "-";
        node.querySelector("span").textContent = " · " + state + " · " + size;
        $("sources").appendChild(node);
      }
      const available = sources.filter(s => s.exists).length;
      const language = $("language").value || "es";
      const message = localizedText(
        "Fuentes cargadas: " + available + " disponible(s) de " + sources.length + ".",
        "Sources loaded: " + available + " available out of " + sources.length + ".",
        language
      );
      appendMessage("system", message, "sources");
      if (opts.speakNow) speak(message, language);
    }

    async function loadLearning(options) {
      const opts = options || {};
      const headers = requestHeaders();
      const params = new URLSearchParams({user: $("user").value || "local", session_id: session.value || ""});
      const res = await fetch("/v1/learning/status?" + params.toString(), {headers});
      if (!res.ok) {
        const message = localizedText(
          "No pude cargar aprendizaje: " + res.status,
          "I could not load learning status: " + res.status,
          $("language").value || "es"
        );
        appendMessage("system", message, "learning");
        if (opts.speakNow) speak(message, $("language").value || "es");
        return;
      }
      const payload = await res.json();
      const feedback = payload.feedback || {};
      const memory = payload.memory || {};
      const recommendations = Array.isArray(payload.recommendations) ? payload.recommendations : [];
      renderActiveContext(memory.active_context || {});
      const language = $("language").value || "es";
      const turnCount = memory.turn_count || memory.total_turns || 0;
      const text = localizedText(
        "Aprendizaje local: feedback " + (feedback.total || 0) +
          " total, " + (feedback.down || 0) + " a mejorar. Memoria: " +
          turnCount + " turno(s). " + recommendations.join(" "),
        "Local learning: " + (feedback.total || 0) +
          " feedback item(s), " + (feedback.down || 0) + " need improvement. Memory: " +
          turnCount + " turn(s). " + recommendations.join(" "),
        language
      );
      appendMessage("system", text.trim(), "learning");
      if (opts.speakNow) speak(text.trim(), language);
    }

    async function runVoiceSystemCheck(options) {
      const opts = options || {};
      const language = $("language").value || "es";
      const headers = requestHeaders();
      const sessionId = session.value || "local";
      const report = {
        backend: "unknown",
        sourcesAvailable: null,
        sourcesTotal: null,
        feedbackTotal: null,
        feedbackDown: null,
        turnCount: null,
        context: "",
      };
      setVoicePresenceActive(true);
      setAvatar("thinking", "diagnostic");
      $("events").textContent = "voice: system check";
      updateVoiceDiagnostics(language);

      try {
        const healthRes = await fetch("/health");
        if (healthRes.ok) {
          const health = await healthRes.json();
          report.backend = health.status || "ok";
        } else {
          report.backend = "error " + healthRes.status;
        }
      } catch (err) {
        report.backend = "offline";
      }

      try {
        const sourcesRes = await fetch("/v1/knowledge/sources", {headers});
        if (sourcesRes.ok) {
          const payload = await sourcesRes.json();
          const sources = Array.isArray(payload.sources) ? payload.sources : [];
          report.sourcesAvailable = sources.filter(source => source.exists).length;
          report.sourcesTotal = sources.length;
        }
      } catch (err) {
        report.sourcesAvailable = null;
      }

      try {
        const params = new URLSearchParams({user: $("user").value || "local", session_id: sessionId});
        const learningRes = await fetch("/v1/learning/status?" + params.toString(), {headers});
        if (learningRes.ok) {
          const payload = await learningRes.json();
          const feedback = payload.feedback || {};
          const memory = payload.memory || {};
          report.feedbackTotal = feedback.total || 0;
          report.feedbackDown = feedback.down || 0;
          report.turnCount = memory.turn_count || memory.total_turns || 0;
          if (memory.active_context) renderActiveContext(memory.active_context);
        }
      } catch (err) {
        report.feedbackTotal = null;
      }

      try {
        const contextRes = await fetch("/v1/assist/context/" + encodeURIComponent(sessionId) + "?limit=8", {headers});
        if (contextRes.ok) {
          const payload = await contextRes.json();
          const context = payload.active_context || {};
          renderActiveContext(context);
          report.turnCount = payload.turn_count || report.turnCount || 0;
          report.context = [
            context.active_symbol || "",
            context.active_intent || payload.last_intent || "",
          ].filter(Boolean).join(" / ");
        }
      } catch (err) {
        report.context = report.context || "";
      }

      const voice = $("voiceStatus").textContent || "-";
      const sourcesText = report.sourcesTotal === null
        ? localizedText("fuentes sin verificar", "sources unchecked", language)
        : report.sourcesAvailable + "/" + report.sourcesTotal + " " + localizedText("fuentes", "sources", language);
      const learningText = report.feedbackTotal === null
        ? localizedText("aprendizaje sin verificar", "learning unchecked", language)
        : report.feedbackTotal + " feedback, " + report.feedbackDown + " " + localizedText("a mejorar", "need improvement", language);
      const turnsText = report.turnCount === null
        ? localizedText("memoria sin verificar", "memory unchecked", language)
        : report.turnCount + " " + localizedText("turno(s)", "turn(s)", language);
      const contextText = report.context || localizedText("sin contexto activo", "no active context", language);
      const message = localizedText(
        "Diagnostico Roxy: backend " + report.backend + ", voz " + voice + ", " +
          sourcesText + ", aprendizaje " + learningText + ", memoria " + turnsText +
          ", contexto " + contextText + ".",
        "Roxy diagnostics: backend " + report.backend + ", voice " + voice + ", " +
          sourcesText + ", learning " + learningText + ", memory " + turnsText +
          ", context " + contextText + ".",
        language
      );
      $("reply").textContent = message;
      appendMessage("system", message, "diagnostic");
      if (!opts.speakNow || !speak(message, language)) {
        setAvatar("ready", $("emotion").textContent);
        scheduleListen();
        releaseVoicePresenceIfIdle();
      }
    }

    async function submitFeedback(rating, options) {
      const opts = options || {};
      const language = $("language").value || "es";
      if (!lastReply) {
        const message = localizedText(
          "No hay respuesta de Roxy para calificar todavía.",
          "There is no Roxy answer to rate yet.",
          language
        );
        appendMessage("system", message, "feedback");
        if (opts.speakNow) speak(message, language);
        return;
      }
      const headers = {"Content-Type": "application/json"};
      const key = $("apiKey").value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      const res = await fetch("/v1/feedback", {
        method: "POST",
        headers,
        body: JSON.stringify({
          rating,
          user: $("user").value || "local",
          session_id: session.value,
          intent: lastState.intent || "",
          query: lastQuery || $("query").value || "",
          reply: lastReply,
          note: $("feedbackNote").value || "",
        })
      });
      if (!res.ok) {
        const message = localizedText(
          "No pude guardar feedback: " + res.status,
          "I could not save feedback: " + res.status,
          language
        );
        appendMessage("system", message, "feedback");
        if (opts.speakNow) speak(message, language);
        return;
      }
      const message = rating === "up"
        ? localizedText("Feedback guardado: sirvió.", "Feedback saved: that helped.", language)
        : localizedText("Feedback guardado: Roxy debe mejorar esa respuesta.", "Feedback saved: Roxy should improve that answer.", language);
      appendMessage("system", message, "feedback");
      if (opts.speakNow) speak(message, language);
      if (rating === "down") $("feedbackNote").value = "";
    }

    function startListening() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        handleFatalMicError("unsupported");
        return;
      }
      if (isListening) return;
      prepareListeningTurn();
      recognition = new SR();
      recognition.lang = speechLang($("language").value);
      recognition.interimResults = true;
      recognition.continuous = $("wakeMode").checked || $("conversationMode").checked;
      recognition.onstart = () => {
        isListening = true;
        $("voiceStatus").textContent = "escuchando · " + recognition.lang;
        setAvatar("listening", "attentive");
      };
      recognition.onresult = (event) => {
        let text = "";
        for (let i = event.resultIndex; i < event.results.length; i++) text += event.results[i][0].transcript;
        const transcript = text.trim();
        const isFinal = event.results[event.results.length - 1].isFinal;
        const latest = event.results[event.results.length - 1][0];
        const confidence = latest && typeof latest.confidence === "number" ? latest.confidence : null;
        updateVoiceHeardStatus(transcript, isFinal, confidence);
        if (isFinal && isVoiceDraftAction(voiceCommandCandidate(transcript))) {
          const currentDraft = (voiceDraftText || $("query").value || "").trim();
          if (currentDraft && normalizeSpeech(currentDraft) !== normalizeSpeech(transcript)) {
            voiceDraftText = currentDraft;
            updateVoiceDraftStatus();
          }
        }
        $("query").value = transcript;
        if (isFinal) {
          lastFinalTranscript = transcript;
          handleFinalTranscript(lastFinalTranscript, confidence);
        }
      };
      recognition.onerror = (event) => {
        const error = event.error || "unknown";
        if (manualStop && error === "aborted") {
          isListening = false;
          setAvatar("ready", $("emotion").textContent);
          return;
        }
        if (($("conversationMode").checked || $("wakeMode").checked) && isRecoverableMicError(error)) {
          recoverFromMicError(error);
          return;
        }
        handleFatalMicError(error);
      };
      recognition.onend = () => {
        isListening = false;
        updateVoiceDiagnostics();
        setAvatar("ready", $("emotion").textContent);
        if (($("conversationMode").checked || $("wakeMode").checked) && !manualStop) scheduleListen();
        releaseVoicePresenceIfIdle();
        lastFinalTranscript = "";
      };
      recognition.start();
    }

    function startListeningFromControl() {
      if (isListening) return;
      if (isSpeaking || activeAssistController) {
        const language = $("language").value || "es";
        $("events").textContent = "voice: barge-in";
        appendMessage(
          "system",
          localizedText("Interrumpiendo para escucharte.", "Interrupting so I can listen.", language),
          "voice-control"
        );
      }
      startListening();
    }

    $("start").onclick = startListeningFromControl;
    $("stop").onclick = () => stopAll("Escucha detenida.");
    $("send").onclick = send;
    $("voiceGuide").onclick = startGuidedVoiceSession;
    $("voiceTest").onclick = speakVoiceSample;
    $("repeat").onclick = () => speak(lastReply, lastState.language || $("language").value);
    $("voiceOptions").onclick = speakVoiceOptionsBrief;
    $("voicePreset").onclick = applyReceptionistVoicePreset;
    $("systemCheck").onclick = () => runVoiceSystemCheck({speakNow: true});
    $("feedbackUp").onclick = () => submitFeedback("up");
    $("feedbackDown").onclick = () => submitFeedback("down");
    $("loadMemory").onclick = loadMemory;
    $("sessionBrief").onclick = sessionVoiceBrief;
    $("loadLearning").onclick = loadLearning;
    $("loadSources").onclick = loadSources;
    $("saveProfile").onclick = saveProfile;
    $("loadProfile").onclick = loadProfile;
    $("clearChat").onclick = () => { $("chat").innerHTML = ""; appendMessage("system", "Chat limpio. Sesion activa: " + session.value, "ready"); };
    document.querySelectorAll("[data-prompt]").forEach((button) => {
      button.addEventListener("click", () => {
        $("query").value = button.getAttribute("data-prompt") || "";
        send();
      });
    });
    $("conversationMode").addEventListener("change", () => {
      saveSettings();
      manualStop = false;
      appendMessage("system", $("conversationMode").checked ? "Modo conversacion activo." : "Modo conversacion apagado.", "mode");
      if ($("conversationMode").checked) setVoicePresenceActive(true);
      else releaseVoicePresenceIfIdle();
      scheduleListen();
    });
    $("wakeMode").addEventListener("change", () => {
      saveSettings();
      manualStop = false;
      appendMessage("system", $("wakeMode").checked ? "Wake Roxy activo. Di: Roxy, seguido de tu pregunta." : "Wake Roxy apagado.", "wake");
      if ($("wakeMode").checked) setVoicePresenceActive(true);
      else releaseVoicePresenceIfIdle();
      scheduleListen();
    });
    [
      "user", "session", "apiKey", "language", "autoSpeak", "autoSendVoice", "voiceSelect", "voiceRate", "voicePitch", "wakeWord",
      "preferredName", "tradingMode", "defaultSymbol", "watchlist"
    ].forEach((id) => {
      $(id).addEventListener("change", saveSettings);
    });
    ["language", "voiceSelect", "voiceRate", "voicePitch"].forEach((id) => {
      $(id).addEventListener("change", () => updateVoiceDiagnostics());
    });
    $("query").addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") send();
    });
    restoreSettings();
    populateVoices();
    updateVoiceDiagnostics();
    updateVoiceDraftStatus();
    if ("speechSynthesis" in window) {
      window.speechSynthesis.onvoiceschanged = () => {
        populateVoices();
        updateVoiceDiagnostics();
      };
    }
    $("roxyAvatar").onerror = () => {
      $("roxyAvatar").style.display = "none";
      $("roxyFallback").style.display = "block";
    };
    appendMessage("system", "Roxy Live lista. Pulsa Hablar o usa un prompt rapido.", "ready");
    setAvatar("ready", "calm");
  </script>
</body>
</html>
        """.strip()
    )


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
    session_id = req.session_id
    logger.info("assist request user=%s query=%s", user, q[:200])
    sync_request_profile(req)

    # Prefer the local Roxy brain because it owns safety and product context.
    reply = None
    if va_backend is not None:
        try:
            reply = va_backend.generate_reply(q, user=user, session_id=session_id)
        except TypeError:
            reply = va_backend.generate_reply(q, user=user)
        except Exception:
            logger.exception("voice backend error")
            raise HTTPException(status_code=500, detail="assistant backend error")

    if llm is not None:
        try:
            reply = reply or llm.generate_reply(q, user=user)
        except Exception:
            logger.exception("LLM provider error")
            reply = None

    if not reply:
        # fallback simple echo
        reply = f"(assistant stub) You said: {q}"

    return {"reply": reply}


def build_assist_state(req: AssistRequest, started_at: float) -> dict[str, object]:
    q = (req.query or "").strip()
    user = req.user
    session_id = req.session_id
    logger.info("assist state request user=%s session=%s query=%s", user, session_id, q[:200])
    sync_request_profile(req)

    if va_backend is not None:
        try:
            if hasattr(va_backend, "generate_reply_state"):
                state = va_backend.generate_reply_state(q, user=user, session_id=session_id)
                return add_turn_metadata(state, started_at, "local_brain")
            return add_turn_metadata(
                {
                    "reply": va_backend.generate_reply(q, user=user),
                    "intent": "legacy",
                    "voice_style": "female_es_latam",
                    "should_speak": True,
                    "needs_live_source": False,
                    "safety_level": "normal",
                    "suggested_actions": [],
                },
                started_at,
                "legacy_backend",
            )
        except Exception:
            logger.exception("voice backend state error")
            raise HTTPException(status_code=500, detail="assistant backend error")

    if llm is not None:
        try:
            reply = llm.generate_reply(q, user=user)
            return add_turn_metadata(
                {
                    "reply": reply,
                    "intent": "llm",
                    "voice_style": "female_es_latam",
                    "should_speak": True,
                    "needs_live_source": False,
                    "safety_level": "normal",
                    "suggested_actions": [],
                },
                started_at,
                "llm_provider",
            )
        except Exception:
            logger.exception("LLM provider error")

    return add_turn_metadata(
        {
            "reply": f"(assistant stub) You said: {q}",
            "intent": "stub",
            "voice_style": "female_es_latam",
            "should_speak": True,
            "needs_live_source": False,
            "safety_level": "normal",
            "suggested_actions": [],
        },
        started_at,
        "stub",
    )


@app.post("/v1/assist/state")
def assist_state(req: AssistRequest, token: Optional[str] = Depends(require_api_key)):
    """Return Roxy's structured voice state for visual and operational clients."""
    started_at = time.perf_counter()
    try:
        rate_limited(token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Rate limiter error: %s", e)

    return build_assist_state(req, started_at)


@app.post("/v1/assist/events")
def assist_events(req: AssistRequest, token: Optional[str] = Depends(require_api_key)):
    """Return only the ordered voice/UI events for a request."""
    state = assist_state(req, token=token)
    events = state.get("events") if isinstance(state, dict) else None
    return {
        "events": events if isinstance(events, list) else [],
        "state": state,
    }


@app.post("/v1/assist/stream")
def assist_stream(req: AssistRequest, token: Optional[str] = Depends(require_api_key)):
    """Stream ordered Roxy turn events with Server-Sent Events."""
    started_at = time.perf_counter()
    try:
        rate_limited(token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Rate limiter error: %s", e)

    query = (req.query or "").strip()

    def event_stream():
        if query:
            yield sse_event(
                "transcript_received",
                {
                    "type": "transcript_received",
                    "text": query,
                    "avatar_state": "listening",
                    "emotion": "attentive",
                    "priority": "normal",
                },
            )
        yield sse_event(
            "thinking",
            {
                "type": "thinking",
                "avatar_state": "thinking",
                "emotion": "focused",
                "priority": "normal",
            },
        )
        try:
            state = build_assist_state(req, started_at)
        except Exception as exc:
            logger.exception("assist stream backend error")
            yield sse_event(
                "error",
                {
                    "type": "error",
                    "detail": f"{type(exc).__name__}: assistant backend error",
                    "avatar_state": "blocked",
                    "emotion": "serious",
                    "priority": "high",
                },
            )
            return

        yield sse_event("reply_ready", {"type": "reply_ready", **state})
        if state.get("should_speak") is not False:
            yield sse_event(
                "speak",
                {
                    "type": "speak",
                    "text": state.get("reply", ""),
                    "language": state.get("language", "es"),
                    "voice_style": state.get("voice_style", "female_es_latam"),
                    "avatar_state": "speaking",
                    "emotion": state.get("emotion", "focused"),
                    "priority": state.get("priority", "normal"),
                    "turn_id": state.get("turn_id", ""),
                },
            )
        yield sse_event(
            "done",
            {
                "type": "done",
                "turn_id": state.get("turn_id", ""),
                "server_latency_ms": state.get("server_latency_ms", 0),
                "response_source": state.get("response_source", ""),
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/v1/assist/session/{session_id}")
def assist_session(session_id: str, token: Optional[str] = Depends(require_api_key), limit: int = 8):
    """Return recent Roxy conversation memory for a session."""
    try:
        rate_limited(token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Rate limiter error: %s", e)

    if va_backend is not None and hasattr(va_backend, "get_session_state"):
        try:
            return va_backend.get_session_state(session_id, limit=max(1, min(int(limit), 20)))
        except Exception:
            logger.exception("voice backend session error")
            raise HTTPException(status_code=500, detail="assistant backend error")

    return {
        "session_id": session_id,
        "turn_count": 0,
        "last_intent": "",
        "last_safety_level": "",
        "active_context": empty_active_context(),
        "recent_turns": [],
    }


@app.get("/v1/assist/session/{session_id}/brief")
def assist_session_brief(
    session_id: str,
    token: Optional[str] = Depends(require_api_key),
    language: str = "es",
    limit: int = 8,
):
    """Return a compact, speakable context brief for voice and mobile clients."""
    try:
        rate_limited(token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Rate limiter error: %s", e)

    bounded_limit = max(1, min(int(limit), 20))
    if va_backend is not None and hasattr(va_backend, "get_session_brief"):
        try:
            return va_backend.get_session_brief(session_id, language=language, limit=bounded_limit)
        except Exception:
            logger.exception("voice backend session brief error")
            raise HTTPException(status_code=500, detail="assistant backend error")

    state = {
        "session_id": session_id,
        "turn_count": 0,
        "last_intent": "",
        "last_safety_level": "",
        "active_context": empty_active_context(),
    }
    clean_language = "en" if str(language or "").lower().startswith("en") else "es"
    summary = (
        "There is no saved context for this session yet."
        if clean_language == "en"
        else "Todavia no hay contexto guardado para esta sesion."
    )
    return {
        "session_id": session_id,
        "turn_count": 0,
        "language": clean_language,
        "speakable_summary": summary,
        "active_context": state["active_context"],
        "suggested_actions": state["active_context"]["next_best_actions"],
    }


@app.get("/v1/assist/context/{session_id}")
def assist_context(session_id: str, token: Optional[str] = Depends(require_api_key), limit: int = 8):
    """Return only active session context for lightweight UI clients."""
    state = assist_session(session_id, token=token, limit=limit)
    context = state.get("active_context") if isinstance(state, dict) else None
    return {
        "session_id": state.get("session_id", session_id) if isinstance(state, dict) else session_id,
        "turn_count": state.get("turn_count", 0) if isinstance(state, dict) else 0,
        "last_intent": state.get("last_intent", "") if isinstance(state, dict) else "",
        "last_safety_level": state.get("last_safety_level", "") if isinstance(state, dict) else "",
        "active_context": context if isinstance(context, dict) else empty_active_context(),
    }


@app.get("/v1/profile/{user}")
def read_profile(user: str, token: Optional[str] = Depends(require_api_key)):
    if va_backend is not None and hasattr(va_backend, "get_user_profile"):
        try:
            return va_backend.get_user_profile(user)
        except Exception:
            logger.exception("profile read error")
            raise HTTPException(status_code=500, detail="profile backend error")
    return {}


@app.post("/v1/profile")
def save_profile(req: ProfileRequest, token: Optional[str] = Depends(require_api_key)):
    if va_backend is not None and hasattr(va_backend, "update_user_profile"):
        try:
            return va_backend.update_user_profile(req.user, req.profile)
        except Exception:
            logger.exception("profile update error")
            raise HTTPException(status_code=500, detail="profile backend error")
    return {}


@app.get("/v1/knowledge/sources")
def knowledge_sources(token: Optional[str] = Depends(require_api_key)):
    if va_backend is not None and hasattr(va_backend, "get_knowledge_sources"):
        try:
            return {"sources": va_backend.get_knowledge_sources()}
        except Exception:
            logger.exception("knowledge sources error")
            raise HTTPException(status_code=500, detail="knowledge backend error")
    return {"sources": []}


@app.post("/v1/feedback")
def save_feedback(req: FeedbackRequest, token: Optional[str] = Depends(require_api_key)):
    if va_backend is not None and hasattr(va_backend, "record_feedback"):
        try:
            return va_backend.record_feedback(req.model_dump())
        except AttributeError:
            return va_backend.record_feedback(req.dict())
        except Exception:
            logger.exception("feedback save error")
            raise HTTPException(status_code=500, detail="feedback backend error")
    return {}


@app.get("/v1/feedback/summary")
def feedback_summary(user: Optional[str] = None, token: Optional[str] = Depends(require_api_key)):
    if va_backend is not None and hasattr(va_backend, "get_feedback_summary"):
        try:
            return va_backend.get_feedback_summary(user=user)
        except Exception:
            logger.exception("feedback summary error")
            raise HTTPException(status_code=500, detail="feedback backend error")
    return {"total": 0, "up": 0, "down": 0, "top_intents": [], "recent": []}


@app.get("/v1/learning/status")
def learning_status(
    user: Optional[str] = None, session_id: Optional[str] = None, token: Optional[str] = Depends(require_api_key)
):
    if va_backend is not None and hasattr(va_backend, "get_learning_snapshot"):
        try:
            return va_backend.get_learning_snapshot(user=user, session_id=session_id)
        except Exception:
            logger.exception("learning status error")
            raise HTTPException(status_code=500, detail="learning backend error")
    return {
        "status": "unavailable",
        "mode": "none",
        "user": user or "local",
        "session_id": session_id or "",
        "feedback": {"total": 0, "up": 0, "down": 0, "top_intents": [], "recent": []},
        "memory": {
            "turn_count": 0,
            "active_context": empty_active_context(),
            "recent_turns": [],
        },
        "knowledge_sources": [],
        "recommendations": ["Conectar el backend de Roxy para activar aprendizaje local."],
    }
