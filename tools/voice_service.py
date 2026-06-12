from __future__ import annotations

from contextlib import asynccontextmanager
import os
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
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


class ProfileRequest(BaseModel):
    user: Optional[str] = None
    profile: Dict[str, object] = {}


class FeedbackRequest(BaseModel):
    rating: str
    user: Optional[str] = None
    session_id: Optional[str] = None
    intent: Optional[str] = None
    query: Optional[str] = None
    reply: Optional[str] = None
    note: Optional[str] = None


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
          <button data-prompt="resumen del mercado">Mercado</button>
          <button data-prompt="resumen de oportunidad">Oportunidad</button>
          <button data-prompt="explica riesgo entrada stop target">Riesgo</button>
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
      </div>
      <div id="reply" class="reply">Roxy esta lista.</div>
      <div id="events" class="events">events: ready</div>
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
      if (recognition) recognition.stop();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      isSpeaking = false;
      isListening = false;
      setAvatar("ready", $("emotion").textContent);
      if (reason) appendMessage("system", reason, "voice-control");
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

    function chooseVoice() {
      const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
      const selected = $("voiceSelect").value;
      if (selected) {
        const exact = voices.find(v => v.name === selected);
        if (exact) return exact;
      }
      const lang = $("language").value || "es";
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
    }

    function speak(text) {
      if (!text || !("speechSynthesis" in window)) return;
      const run = () => {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = ($("language").value || "es") === "en" ? "en-US" : "es-US";
        utterance.rate = Number($("voiceRate").value || 0.95);
        utterance.pitch = Number($("voicePitch").value || 1.05);
        const voice = chooseVoice();
        if (voice) utterance.voice = voice;
        utterance.onstart = () => {
          isSpeaking = true;
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
    }

    async function send() {
      const text = $("query").value.trim();
      if (!text) return;
      saveSettings();
      setAvatar("thinking", "focused");
      $("reply").textContent = "Roxy esta pensando...";
      appendMessage("user", text, new Date().toLocaleTimeString());
      const headers = {"Content-Type": "application/json"};
      const key = $("apiKey").value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      const res = await fetch("/v1/assist/state", {
        method: "POST",
        headers,
        body: JSON.stringify({query: text, user: $("user").value || "local", session_id: session.value})
      });
      if (!res.ok) {
        const message = "Error " + res.status + ": revisa VOICE_API_KEY o el servicio.";
        $("reply").textContent = message;
        appendMessage("system", message, "error");
        setAvatar("blocked", "serious");
        return;
      }
      const state = await res.json();
      lastReply = state.reply || "";
      lastQuery = text;
      lastState = state || {};
      $("intent").textContent = state.intent || "-";
      $("avatarState").textContent = state.avatar_state || "-";
      $("emotion").textContent = state.emotion || "-";
      $("safety").textContent = state.safety_level || "-";
      $("priority").textContent = state.priority || "-";
      $("liveSource").textContent = state.needs_live_source ? "Needed" : "OK";
      $("reply").textContent = lastReply || "(sin respuesta)";
      const events = Array.isArray(state.events) ? state.events.map(e => e.type).join(" -> ") : "";
      $("events").textContent = "events: " + (events || "-");
      appendMessage("roxy", lastReply || "(sin respuesta)", [state.intent, state.safety_level].filter(Boolean).join(" / "));
      setAvatar(state.avatar_state || "speaking", state.emotion || "focused");
      if (state.should_speak !== false && $("autoSpeak").checked) speak(lastReply);
      else scheduleListen();
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
      const profile = {
        preferred_name: $("preferredName").value,
        language: $("language").value || "es",
        trading_mode: $("tradingMode").value,
        default_symbol: $("defaultSymbol").value,
        watchlist: $("watchlist").value,
        voice_name: $("voiceSelect").value,
        voice_rate: Number($("voiceRate").value || 0.95),
        voice_pitch: Number($("voicePitch").value || 1.05),
      };
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
      clearTimeout(pendingListenTimer);
      if (isListening) return;
      manualStop = false;
      recognition = new SR();
      recognition.lang = ($("language").value || "es") === "en" ? "en-US" : "es-US";
      recognition.interimResults = true;
      recognition.continuous = $("wakeMode").checked || $("conversationMode").checked;
      recognition.onstart = () => {
        isListening = true;
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
        isListening = false;
        manualStop = true;
        setAvatar("blocked", "serious");
      };
      recognition.onend = () => {
        isListening = false;
        setAvatar("ready", $("emotion").textContent);
        if (($("conversationMode").checked || $("wakeMode").checked) && !manualStop) scheduleListen();
        lastFinalTranscript = "";
      };
      recognition.start();
    }

    $("start").onclick = startListening;
    $("stop").onclick = () => stopAll("Escucha detenida.");
    $("send").onclick = send;
    $("repeat").onclick = () => speak(lastReply);
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
      "user", "session", "apiKey", "autoSpeak", "autoSendVoice", "voiceSelect", "voiceRate", "voicePitch", "wakeWord",
      "preferredName", "tradingMode", "defaultSymbol", "watchlist"
    ].forEach((id) => {
      $(id).addEventListener("change", saveSettings);
    });
    $("query").addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") send();
    });
    restoreSettings();
    populateVoices();
    if ("speechSynthesis" in window) window.speechSynthesis.onvoiceschanged = populateVoices;
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


@app.post("/v1/assist/state")
def assist_state(req: AssistRequest, token: Optional[str] = Depends(require_api_key)):
    """Return Roxy's structured voice state for visual and operational clients."""
    try:
        rate_limited(token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Rate limiter error: %s", e)

    q = (req.query or "").strip()
    user = req.user
    session_id = req.session_id
    logger.info("assist state request user=%s session=%s query=%s", user, session_id, q[:200])

    if va_backend is not None:
        try:
            if hasattr(va_backend, "generate_reply_state"):
                return va_backend.generate_reply_state(q, user=user, session_id=session_id)
            return {
                "reply": va_backend.generate_reply(q, user=user),
                "intent": "legacy",
                "voice_style": "female_es_latam",
                "should_speak": True,
                "needs_live_source": False,
                "safety_level": "normal",
                "suggested_actions": [],
            }
        except Exception:
            logger.exception("voice backend state error")
            raise HTTPException(status_code=500, detail="assistant backend error")

    if llm is not None:
        try:
            reply = llm.generate_reply(q, user=user)
            return {
                "reply": reply,
                "intent": "llm",
                "voice_style": "female_es_latam",
                "should_speak": True,
                "needs_live_source": False,
                "safety_level": "normal",
                "suggested_actions": [],
            }
        except Exception:
            logger.exception("LLM provider error")

    return {
        "reply": f"(assistant stub) You said: {q}",
        "intent": "stub",
        "voice_style": "female_es_latam",
        "should_speak": True,
        "needs_live_source": False,
        "safety_level": "normal",
        "suggested_actions": [],
    }


@app.post("/v1/assist/events")
def assist_events(req: AssistRequest, token: Optional[str] = Depends(require_api_key)):
    """Return only the ordered voice/UI events for a request."""
    state = assist_state(req, token=token)
    events = state.get("events") if isinstance(state, dict) else None
    return {
        "events": events if isinstance(events, list) else [],
        "state": state,
    }


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
        "recent_turns": [],
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
        "memory": {"turn_count": 0, "recent_turns": []},
        "knowledge_sources": [],
        "recommendations": ["Conectar el backend de Roxy para activar aprendizaje local."],
    }
