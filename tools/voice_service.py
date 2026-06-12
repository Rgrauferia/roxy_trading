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
  <main>
    <section class="top">
      <div id="avatar" class="avatar">
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
          <button data-prompt="frescura de datos">Datos</button>
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
          <label class="slider">Velocidad <input id="voiceRate" type="range" min="0.75" max="1.15" step="0.05" value="0.95" /></label>
          <label class="slider">Tono <input id="voicePitch" type="range" min="0.85" max="1.2" step="0.05" value="1.05" /></label>
          <input id="wakeWord" placeholder="Wake: Roxy" value="Roxy" />
          <input id="feedbackNote" placeholder="Nota feedback: mas corto, mas claro..." />
        </div>
        <div class="controls">
          <button id="start" class="primary">Hablar</button>
          <button id="stop" class="warn">Parar</button>
          <button id="send">Enviar</button>
          <button id="repeat">Repetir voz</button>
          <button id="feedbackUp">Sirvio</button>
          <button id="feedbackDown">No sirvio</button>
          <button id="loadMemory">Cargar memoria</button>
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
    const duplicateVoiceWindowMs = 2500;
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
      $("voiceRate").value = localStorage.getItem("roxyLiveVoiceRate") || "0.95";
      $("voicePitch").value = localStorage.getItem("roxyLiveVoicePitch") || "1.05";
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
      localStorage.setItem("roxyLiveVoiceRate", $("voiceRate").value || "0.95");
      localStorage.setItem("roxyLiveVoicePitch", $("voicePitch").value || "1.05");
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
      connect_realtime_voice: ["Voz", "estado de roxy"],
      connect_news_source: ["Noticias", "analiza impacto de noticia: pega aqui el titular"],
      confirm_trade_guardrails: ["Guardrails", "puedo operar ahora"],
      run_scan: ["Datos", "frescura de datos"],
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
      const blocked = ["ROXY", "BUY", "SELL", "WATCH", "WAIT", "READY", "BLOCKED", "LONG", "SHORT", "STOP", "TARGET"];
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
      if (reason) appendMessage("system", reason, "voice-control");
    }

    function prepareListeningTurn() {
      clearTimeout(pendingListenTimer);
      cancelActiveAssist();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      isSpeaking = false;
      manualStop = false;
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

    function extractWakeCommand(text) {
      const wake = normalizeSpeech($("wakeWord").value || "Roxy");
      const normalized = normalizeSpeech(text);
      const words = normalized.split(" ").filter(Boolean);
      const wakeIndex = words.findIndex(word => word === wake || word.includes(wake));
      if (wakeIndex < 0) return null;
      return words.slice(wakeIndex + 1).join(" ").trim();
    }

    function handleFinalTranscript(text) {
      const finalText = (text || "").trim();
      if (!finalText) return;
      if (isDuplicateFinalTranscript(finalText)) {
        $("events").textContent = "voice: duplicate ignored";
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
        $("query").value = command;
        send();
        return;
      }
      if ($("autoSendVoice").checked) send();
    }

    function speechLang(languageValue) {
      return (languageValue || "es") === "en" ? "en-US" : "es-US";
    }

    function chooseVoice(languageOverride) {
      const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
      const selected = $("voiceSelect").value;
      if (selected) {
        const exact = voices.find(v => v.name === selected);
        if (exact) return exact;
      }
      const lang = languageOverride || $("language").value || "es";
      if (lang === "en") {
        return voices.find(v => (v.lang || "").toLowerCase().startsWith("en") && /female|samantha|victoria|zira|google/i.test(v.name || ""))
          || voices.find(v => (v.lang || "").toLowerCase().startsWith("en"))
          || voices[0];
      }
      const preferredNames = ["paulina", "monica", "sabina", "google español", "spanish", "español"];
      return voices.find(v => preferredNames.some(name => (v.name || "").toLowerCase().includes(name)))
        || voices.find(v => (v.lang || "").toLowerCase().startsWith("es"))
        || voices[0];
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
      if (selected && Array.from(select.options).some(o => o.value === selected)) {
        select.value = selected;
      } else {
        const preferred = chooseVoice();
        if (preferred) select.value = preferred.name;
      }
      updateVoiceDiagnostics();
    }

    function speak(text, languageOverride) {
      if (!text || !("speechSynthesis" in window)) return false;
      const run = () => {
        const lang = languageOverride || $("language").value || "es";
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = speechLang(lang);
        utterance.rate = Number($("voiceRate").value || 0.95);
        utterance.pitch = Number($("voicePitch").value || 1.05);
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
        };
        utterance.onerror = () => {
          isSpeaking = false;
          setAvatar("ready", $("emotion").textContent);
          scheduleListen();
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
        voice_rate: Number($("voiceRate").value || 0.95),
        voice_pitch: Number($("voicePitch").value || 1.05),
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
      updateVoiceDiagnostics(state.language || $("language").value);
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
      if (profile.voice_pitch) $("voicePitch").value = profile.voice_pitch;
      if (profile.voice_name) $("voiceSelect").value = profile.voice_name;
      saveSettings();
      appendMessage("system", "Perfil cargado.", "profile");
    }

    async function loadSources() {
      const headers = {};
      const key = $("apiKey").value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      const res = await fetch("/v1/knowledge/sources", {headers});
      if (!res.ok) {
        appendMessage("system", "No pude cargar fuentes: " + res.status, "sources");
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
      appendMessage("system", "Fuentes cargadas: " + sources.filter(s => s.exists).length + " disponible(s).", "sources");
    }

    async function loadLearning() {
      const headers = {};
      const key = $("apiKey").value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      const params = new URLSearchParams({user: $("user").value || "local", session_id: session.value || ""});
      const res = await fetch("/v1/learning/status?" + params.toString(), {headers});
      if (!res.ok) {
        appendMessage("system", "No pude cargar aprendizaje: " + res.status, "learning");
        return;
      }
      const payload = await res.json();
      const feedback = payload.feedback || {};
      const memory = payload.memory || {};
      const recommendations = Array.isArray(payload.recommendations) ? payload.recommendations : [];
      renderActiveContext(memory.active_context || {});
      const text = "Aprendizaje local: feedback " + (feedback.total || 0) +
        " total, " + (feedback.down || 0) + " a mejorar. Memoria: " +
        (memory.turn_count || memory.total_turns || 0) + " turno(s). " +
        recommendations.join(" ");
      appendMessage("system", text.trim(), "learning");
    }

    async function submitFeedback(rating) {
      if (!lastReply) {
        appendMessage("system", "No hay respuesta de Roxy para calificar todavia.", "feedback");
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
        appendMessage("system", "No pude guardar feedback: " + res.status, "feedback");
        return;
      }
      appendMessage("system", rating === "up" ? "Feedback guardado: sirvio." : "Feedback guardado: Roxy debe mejorar esa respuesta.", "feedback");
      if (rating === "down") $("feedbackNote").value = "";
    }

    function startListening() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        $("reply").textContent = "Tu navegador no soporta SpeechRecognition. Usa Chrome o Edge.";
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
        $("query").value = text.trim();
        if (event.results[event.results.length - 1].isFinal) {
          lastFinalTranscript = $("query").value;
          handleFinalTranscript(lastFinalTranscript);
        }
      };
      recognition.onerror = (event) => {
        $("reply").textContent = "Microfono: " + event.error;
        $("voiceStatus").textContent = "mic error · " + event.error;
        isListening = false;
        manualStop = true;
        setAvatar("blocked", "serious");
      };
      recognition.onend = () => {
        isListening = false;
        updateVoiceDiagnostics();
        setAvatar("ready", $("emotion").textContent);
        if (($("conversationMode").checked || $("wakeMode").checked) && !manualStop) scheduleListen();
        lastFinalTranscript = "";
      };
      recognition.start();
    }

    $("start").onclick = startListening;
    $("stop").onclick = () => stopAll("Escucha detenida.");
    $("send").onclick = send;
    $("repeat").onclick = () => speak(lastReply, lastState.language || $("language").value);
    $("feedbackUp").onclick = () => submitFeedback("up");
    $("feedbackDown").onclick = () => submitFeedback("down");
    $("loadMemory").onclick = loadMemory;
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
      scheduleListen();
    });
    $("wakeMode").addEventListener("change", () => {
      saveSettings();
      manualStop = false;
      appendMessage("system", $("wakeMode").checked ? "Wake Roxy activo. Di: Roxy, seguido de tu pregunta." : "Wake Roxy apagado.", "wake");
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
