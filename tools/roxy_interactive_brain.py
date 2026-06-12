from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


BRIEF_PATH = Path("alerts/roxy_ai_brief.json")
MEMORY_PATH = Path("alerts/roxy_ai_memory.json")
STATUS_PATH = Path("alerts/roxy_status.json")
CONVERSATION_MEMORY_PATH = Path("alerts/roxy_conversation_memory.json")
USER_PROFILE_PATH = Path("alerts/roxy_user_profile.json")
FEEDBACK_PATH = Path("alerts/roxy_feedback.json")
MAX_SESSION_TURNS = 20
MAX_MEMORY_SESSIONS = 120
MAX_FEEDBACK_ITEMS = 500
KNOWLEDGE_PATHS = (
    Path("MASTER_CONTEXT.md"),
    Path("README.md"),
    Path("README_UI.md"),
    Path("docs/ai_spec.md"),
    Path("docs/roxy_interactive_strategy.md"),
)
MAX_KNOWLEDGE_CHARS = 8000


@dataclass(frozen=True)
class RoxyBrainReply:
    reply: str
    intent: str
    language: str = "es"
    voice_style: str = "female_es_latam"
    avatar_state: str = "speaking"
    emotion: str = "focused"
    should_speak: bool = True
    needs_live_source: bool = False
    safety_level: str = "normal"
    priority: str = "normal"
    suggested_actions: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "intent": self.intent,
            "language": self.language,
            "voice_style": self.voice_style,
            "avatar_state": self.avatar_state,
            "emotion": self.emotion,
            "should_speak": self.should_speak,
            "needs_live_source": self.needs_live_source,
            "safety_level": self.safety_level,
            "priority": self.priority,
            "suggested_actions": list(self.suggested_actions),
        }


def build_voice_events(query: str, response: RoxyBrainReply) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    transcript = _redact_sensitive_text(query)
    if transcript:
        events.append(
            {
                "type": "transcript_received",
                "text": transcript,
                "avatar_state": "listening",
                "emotion": "attentive",
                "priority": "normal",
            }
        )
    events.append(
        {
            "type": "thinking",
            "avatar_state": "thinking",
            "emotion": "focused",
            "priority": "normal",
        }
    )
    events.append(
        {
            "type": "reply_ready",
            "text": response.reply,
            "intent": response.intent,
            "language": response.language,
            "avatar_state": response.avatar_state,
            "emotion": response.emotion,
            "priority": response.priority,
            "safety_level": response.safety_level,
        }
    )
    if response.should_speak:
        events.append(
            {
                "type": "speak",
                "text": response.reply,
                "language": response.language,
                "voice_style": response.voice_style,
                "avatar_state": "speaking",
                "emotion": response.emotion,
                "priority": response.priority,
            }
        )
    if response.needs_live_source:
        events.append(
            {
                "type": "live_source_required",
                "avatar_state": "waiting",
                "emotion": "cautious",
                "priority": "high",
            }
        )
    if response.safety_level == "critical":
        events.append(
            {
                "type": "action_confirmation_required",
                "avatar_state": "blocked",
                "emotion": "serious",
                "priority": "high",
            }
        )
    return events


class RoxyConversationMemory:
    def __init__(
        self,
        path: Path = CONVERSATION_MEMORY_PATH,
        max_turns: int = MAX_SESSION_TURNS,
        max_sessions: int = MAX_MEMORY_SESSIONS,
    ):
        self.path = path
        self.max_turns = max_turns
        self.max_sessions = max_sessions

    def recent_turns(self, session_id: str | None, limit: int = 6) -> list[dict[str, Any]]:
        if not session_id:
            return []
        payload = _load_json(self.path)
        sessions = payload.get("sessions") or {}
        turns = sessions.get(_safe_session_id(session_id)) or []
        if not isinstance(turns, list):
            return []
        return [turn for turn in turns[-limit:] if isinstance(turn, dict)]

    def session_state(self, session_id: str | None, limit: int = 8) -> dict[str, Any]:
        turns = self.recent_turns(session_id, limit=limit)
        last_turn = turns[-1] if turns else {}
        return {
            "session_id": _safe_session_id(session_id or "local"),
            "turn_count": len(turns),
            "last_intent": _safe_text(last_turn.get("intent")),
            "last_safety_level": _safe_text(last_turn.get("safety_level")),
            "recent_turns": turns,
        }

    def overview(self, limit: int = 8) -> dict[str, Any]:
        payload = _load_json(self.path)
        sessions = payload.get("sessions") if isinstance(payload, dict) else {}
        if not isinstance(sessions, dict):
            sessions = {}
        rows = []
        total_turns = 0
        for session_id, turns in sessions.items():
            if not isinstance(turns, list):
                continue
            total_turns += len(turns)
            last_turn = turns[-1] if turns and isinstance(turns[-1], dict) else {}
            rows.append(
                {
                    "session_id": _safe_session_id(session_id),
                    "turn_count": len(turns),
                    "last_intent": _safe_text(last_turn.get("intent")),
                    "last_at": _safe_text(last_turn.get("at")),
                }
            )
        rows.sort(key=lambda row: row.get("last_at") or "", reverse=True)
        return {
            "session_count": len(rows),
            "total_turns": total_turns,
            "recent_sessions": rows[: max(1, min(int(limit), 20))],
        }

    def append(self, session_id: str | None, query: str, response: RoxyBrainReply) -> None:
        if not session_id:
            return
        session_key = _safe_session_id(session_id)
        payload = _load_json(self.path)
        sessions = payload.get("sessions")
        if not isinstance(sessions, dict):
            sessions = {}

        turns = sessions.get(session_key)
        if not isinstance(turns, list):
            turns = []
        turns.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "query": _redact_sensitive_text(query),
                "reply": _redact_sensitive_text(response.reply),
                "intent": response.intent,
                "safety_level": response.safety_level,
            }
        )
        sessions[session_key] = turns[-self.max_turns :]
        sessions = self._pruned_sessions(sessions)
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sessions": sessions,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _pruned_sessions(self, sessions: dict[str, Any]) -> dict[str, Any]:
        if len(sessions) <= self.max_sessions:
            return sessions

        rows = []
        for session_id, turns in sessions.items():
            last_at = ""
            if isinstance(turns, list) and turns and isinstance(turns[-1], dict):
                last_at = _safe_text(turns[-1].get("at"))
            rows.append((last_at, session_id, turns))
        rows.sort(key=lambda row: row[0], reverse=True)
        keep = rows[: self.max_sessions]
        return {session_id: turns for _last_at, session_id, turns in keep}


class RoxyUserProfile:
    ALLOWED_KEYS = {
        "preferred_name",
        "language",
        "tone",
        "trading_mode",
        "default_symbol",
        "watchlist",
        "voice_name",
        "voice_rate",
        "voice_pitch",
    }

    def __init__(self, path: Path = USER_PROFILE_PATH):
        self.path = path

    def read(self, user: str | None = None) -> dict[str, Any]:
        payload = _load_json(self.path)
        profiles = payload.get("profiles") if isinstance(payload, dict) else {}
        if not isinstance(profiles, dict):
            profiles = {}
        key = _safe_session_id(user or "local")
        profile = profiles.get(key) or {}
        return profile if isinstance(profile, dict) else {}

    def update(self, user: str | None, updates: dict[str, Any]) -> dict[str, Any]:
        key = _safe_session_id(user or "local")
        payload = _load_json(self.path)
        profiles = payload.get("profiles") if isinstance(payload, dict) else {}
        if not isinstance(profiles, dict):
            profiles = {}
        current = profiles.get(key) if isinstance(profiles.get(key), dict) else {}
        clean_updates = self._clean_updates(updates)
        current.update(clean_updates)
        profiles[key] = current
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "profiles": profiles,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return current

    def _clean_updates(self, updates: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for key, value in (updates or {}).items():
            if key not in self.ALLOWED_KEYS:
                continue
            if key == "watchlist":
                if isinstance(value, str):
                    raw_items = re.split(r"[,\s]+", value)
                elif isinstance(value, list):
                    raw_items = value
                else:
                    raw_items = []
                symbols = []
                for item in raw_items:
                    symbol = re.sub(r"[^A-Za-z0-9.:-]+", "", str(item or "").upper())
                    if 1 <= len(symbol) <= 12:
                        symbols.append(symbol)
                clean[key] = symbols[:20]
            elif key in {"voice_rate", "voice_pitch"}:
                number = _safe_float(value)
                if number is not None:
                    clean[key] = max(0.5, min(1.5, number))
            elif key == "language":
                language = _safe_text(value).lower()
                clean[key] = "en" if language.startswith("en") or "english" in language else "es"
            else:
                clean[key] = _redact_sensitive_text(str(value or ""))[:160]
        return clean


class RoxyFeedbackMemory:
    def __init__(self, path: Path = FEEDBACK_PATH, max_items: int = MAX_FEEDBACK_ITEMS):
        self.path = path
        self.max_items = max_items

    def record(self, feedback: dict[str, Any]) -> dict[str, Any]:
        payload = _load_json(self.path)
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            items = []

        rating = _safe_text(feedback.get("rating")).lower()
        if rating not in {"up", "down"}:
            rating = "up"
        item = {
            "at": datetime.now(timezone.utc).isoformat(),
            "rating": rating,
            "user": _safe_session_id(_safe_text(feedback.get("user") or "local")),
            "session_id": _safe_session_id(_safe_text(feedback.get("session_id") or "local")),
            "intent": _safe_text(feedback.get("intent"))[:80],
            "query": _redact_sensitive_text(_safe_text(feedback.get("query")))[:500],
            "reply": _redact_sensitive_text(_safe_text(feedback.get("reply")))[:900],
            "note": _redact_sensitive_text(_safe_text(feedback.get("note")))[:500],
        }
        items.append(item)
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": items[-self.max_items :],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return item

    def _items(self, user: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        payload = _load_json(self.path)
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            items = []
        if user:
            safe_user = _safe_session_id(user)
            items = [item for item in items if isinstance(item, dict) and item.get("user") == safe_user]
        return [item for item in items[-limit:] if isinstance(item, dict)]

    def summary(self, user: str | None = None, limit: int = 200) -> dict[str, Any]:
        clean_items = self._items(user=user, limit=limit)
        by_intent: dict[str, dict[str, int]] = {}
        for item in clean_items:
            intent = _safe_text(item.get("intent")) or "unknown"
            bucket = by_intent.setdefault(intent, {"up": 0, "down": 0})
            rating = _safe_text(item.get("rating"))
            if rating == "down":
                bucket["down"] += 1
            else:
                bucket["up"] += 1
        up = sum(1 for item in clean_items if item.get("rating") == "up")
        down = sum(1 for item in clean_items if item.get("rating") == "down")
        top_intents = sorted(
            ({"intent": intent, "up": values["up"], "down": values["down"]} for intent, values in by_intent.items()),
            key=lambda row: (row["down"], row["up"]),
            reverse=True,
        )
        return {
            "total": len(clean_items),
            "up": up,
            "down": down,
            "top_intents": top_intents[:8],
            "recent": clean_items[-10:],
        }

    def guidance_for_intent(self, intent: str, user: str | None = None) -> dict[str, Any]:
        target = _safe_text(intent)
        if not target:
            return {"total": 0, "up": 0, "down": 0, "needs_adjustment": False, "latest_note": ""}

        rows = [item for item in self._items(user=user) if _safe_text(item.get("intent")) == target]
        up = sum(1 for item in rows if item.get("rating") == "up")
        down = sum(1 for item in rows if item.get("rating") == "down")
        latest_note = ""
        for item in reversed(rows):
            if item.get("rating") == "down":
                latest_note = _safe_text(item.get("note"))
                break
        return {
            "total": len(rows),
            "up": up,
            "down": down,
            "needs_adjustment": down > 0 and down >= up,
            "latest_note": latest_note[:180],
        }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def list_knowledge_sources(knowledge_paths: tuple[Path, ...] = KNOWLEDGE_PATHS) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in knowledge_paths:
        exists = path.exists() and path.is_file()
        stat = path.stat() if exists else None
        sources.append(
            {
                "path": str(path),
                "exists": exists,
                "size_bytes": stat.st_size if stat else 0,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else "",
            }
        )
    return sources


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_session_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip())[:80]
    return cleaned or "local"


def _redact_sensitive_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(api[_ -]?key|secret|token|password)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    text = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[redacted]", text)
    return text[:1200]


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _price(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number:.2f}"


def _pct(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number * 100:.2f}%"


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _detect_language(query: str, profile: dict[str, Any]) -> str:
    preferred = _safe_text(profile.get("language")).lower()
    if preferred.startswith("en"):
        return "en"
    if preferred.startswith("es"):
        return "es"

    normalized = str(query or "").lower()
    english_terms = {
        "hello",
        "hi",
        "what",
        "who",
        "status",
        "market",
        "news",
        "trade",
        "trading",
        "opportunity",
        "risk",
        "buy",
        "sell",
        "recommend",
        "recommendation",
        "help",
        "explain",
        "read",
        "learning",
        "memory",
        "autonomous",
    }
    spanish_terms = {
        "hola",
        "que",
        "quien",
        "estado",
        "mercado",
        "noticia",
        "operacion",
        "oportunidad",
        "riesgo",
        "compra",
        "vende",
        "ayuda",
        "explica",
        "lee",
        "aprendizaje",
        "memoria",
        "autonomo",
    }
    tokens = set(re.findall(r"[a-záéíóúñ]+", normalized))
    english_score = len(tokens.intersection(english_terms))
    spanish_score = len(tokens.intersection(spanish_terms))
    if english_score > spanish_score:
        return "en"
    return "es"


def _voice_style_for_language(language: str) -> str:
    return "female_en_us" if language == "en" else "female_es_latam"


def _localize_market_phrase(value: Any, language: str) -> str:
    text = _safe_text(value)
    if language != "en":
        return text
    translations = {
        "Esperar entrada 15m": "Wait for 15m entry",
        "WAIT_15M_ENTRY": "Wait for 15m entry",
        "Esperar": "Wait",
        "Operar": "Actionable",
        "No tocar": "Do not touch",
        "Esperar gatillo BUY en 15m mientras 1h sigue valido.": "Wait for a 15m BUY trigger while 1h remains valid.",
        "Invalidar si pierde": "Invalidate if it loses",
        "No operar todavia: faltan condiciones importantes del checklist.": "Do not trade yet: important checklist conditions are still missing.",
        "15m da entrada": "15m entry",
        "2h/4h validan": "2h/4h validation",
        "2h/4h contradicen el gatillo": "2h/4h contradict the trigger",
        "Volumen acompana": "Volume confirms",
        "falta volumen": "missing volume",
    }
    if text in translations:
        return translations[text]
    localized = text
    for source, target in translations.items():
        localized = localized.replace(source, target)
    return localized


def _sentence_fragment(value: Any) -> str:
    return _safe_text(value).rstrip(" .")


def _tokenize(text: str) -> set[str]:
    stopwords = {
        "como",
        "para",
        "que",
        "con",
        "del",
        "las",
        "los",
        "una",
        "uno",
        "este",
        "esta",
        "the",
        "and",
        "for",
        "you",
        "roxy",
    }
    words = re.findall(r"[A-Za-z0-9_áéíóúñÁÉÍÓÚÑ]+", str(text or "").lower())
    return {word for word in words if len(word) >= 3 and word not in stopwords}


def _knowledge_excerpt(text: str, query_terms: set[str], max_chars: int = 520) -> str:
    lines = [" ".join(line.strip().split()) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return "La fuente esta vacia."

    best_line = lines[0]
    best_score = -1
    for idx, line in enumerate(lines):
        terms = _tokenize(line)
        score = len(query_terms.intersection(terms))
        if score > best_score:
            best_score = score
            start = max(0, idx - 1)
            end = min(len(lines), idx + 3)
            best_line = " ".join(lines[start:end])

    if len(best_line) <= max_chars:
        return best_line
    return best_line[: max_chars - 3].rstrip() + "..."


def _extract_symbol(query: str) -> str | None:
    aliases = {
        "APPLE": "AAPL",
        "APOL": "AAPL",
        "NVIDIA": "NVDA",
        "TESLA": "TSLA",
        "MICROSOFT": "MSFT",
        "META": "META",
        "SPY": "SPY",
        "QQQ": "QQQ",
    }
    ignored = {
        "ROXY",
        "DIME",
        "QUE",
        "COMO",
        "POR",
        "PARA",
        "CON",
        "UNA",
        "LAS",
        "LOS",
        "DEL",
        "EL",
        "LA",
        "Y",
        "HOY",
        "RIESGO",
        "STOP",
        "ENTRA",
        "ENTRADA",
        "ESTADO",
        "FALTA",
        "PORQUE",
        "SIGUE",
        "STATUS",
        "ENTRY",
        "TARGET",
        "TRIGGER",
        "MISSING",
        "WHAT",
        "WHY",
        "HOW",
        "PLAN",
        "ACTION",
        "DECISION",
        "BUY",
        "SELL",
        "TRADE",
    }
    for raw_word in query.split():
        word = raw_word.strip(".,:;!?()[]{}\"'").upper()
        if word in aliases:
            return aliases[word]
        if 1 <= len(word) <= 6 and word.isalpha() and word not in ignored:
            return word
    return None


class RoxyInteractiveBrain:
    """Conversation strategy layer for Roxy.

    This module stays provider-neutral: it prepares speakable, safety-aware
    replies from local Roxy context. A visual UI, speech engine, or LLM can use
    the returned contract without owning strategy decisions.
    """

    def __init__(
        self,
        brief_path: Path = BRIEF_PATH,
        memory_path: Path = MEMORY_PATH,
        status_path: Path = STATUS_PATH,
        conversation_memory: RoxyConversationMemory | None = None,
        user_profile: RoxyUserProfile | None = None,
        feedback_memory: RoxyFeedbackMemory | None = None,
        knowledge_paths: tuple[Path, ...] = KNOWLEDGE_PATHS,
    ):
        self.brief_path = brief_path
        self.memory_path = memory_path
        self.status_path = status_path
        self.conversation_memory = conversation_memory or RoxyConversationMemory()
        self.user_profile = user_profile or RoxyUserProfile()
        self.feedback_memory = feedback_memory or RoxyFeedbackMemory()
        self.knowledge_paths = knowledge_paths

    def generate_reply(self, query: str, user: str | None = None, session_id: str | None = None) -> RoxyBrainReply:
        q = (query or "").strip()
        recent_turns = self.conversation_memory.recent_turns(session_id)
        profile = self.user_profile.read(user)
        language = _detect_language(q, profile)

        def finish(response: RoxyBrainReply) -> RoxyBrainReply:
            localized = self._apply_language(response, language, user, session_id, recent_turns, profile, q)
            adjusted = self._apply_feedback_guidance(localized, user)
            self.conversation_memory.append(session_id, q, adjusted)
            return adjusted

        if not q:
            response = self._idle_reply(user, recent_turns, profile)
            return finish(response)

        lq = q.lower()
        if _contains_any(lq, ("hola", "hello", "hi", "hey", "buenos dias", "buenas")):
            response = self._greeting_reply(user, profile)
            return finish(response)

        if _contains_any(
            lq,
            (
                "estado de roxy",
                "estado roxy",
                "estado local",
                "modo autonomo",
                "autonomia",
                "estas activa",
                "estas escuchando",
                "sigues activa",
                "status",
                "are you active",
                "are you listening",
                "autonomous mode",
            ),
        ) or lq in {"estado", "status"}:
            response = self._autonomy_status_reply(user, session_id, recent_turns, profile)
            return finish(response)

        if _contains_any(lq, ("quien eres", "who are you", "tu rostro", "cara", "avatar", "identidad", "identity", "roxy")):
            response = self._identity_reply()
            return finish(response)

        if _contains_any(
            lq,
            (
                "que puedes",
                "what can you",
                "can you do",
                "capabilities",
                "ayuda",
                "help",
                "hablar",
                "talk",
                "conversacion",
                "conversation",
                "voz",
                "voice",
                "fluida",
            ),
        ):
            response = self._capability_reply(profile)
            return finish(response)

        if _contains_any(
            lq,
            (
                "market trend",
                "market condition",
                "market summary",
                "market regime",
                "bullish",
                "bearish",
                "sideways",
                "tendencia del mercado",
                "condicion del mercado",
                "resumen del mercado",
                "regimen del mercado",
                "alcista",
                "bajista",
                "lateral",
            ),
        ):
            response = self._market_summary_reply(language)
            return finish(response)

        if _contains_any(
            lq,
            (
                "ejecuta",
                "execute",
                "ejecutar",
                "manda orden",
                "send order",
                "enviar orden",
                "abrir posicion",
                "open position",
                "abre posicion",
                "compra ahora",
                "buy now",
                "vende ahora",
                "sell now",
                "operar real",
                "real trading",
                "live trade",
            ),
        ):
            response = self._action_guardrail_reply(q)
            return finish(response)

        if _contains_any(lq, ("noticia", "news", "titular", "mercado hoy", "actualidad")):
            response = self._news_reply(language)
            return finish(response)

        if _contains_any(
            lq,
            (
                "explica el sistema",
                "explain the system",
                "explicame el sistema",
                "lee",
                "read",
                "documento",
                "document",
                "manual",
                "universo roxy",
                "roxy trading",
                "como funciona",
                "how does it work",
            ),
        ):
            response = self._knowledge_reply(q)
            return finish(response)

        if _contains_any(lq, ("aprendizaje", "aprendiendo", "aprendiste", "aprendi", "learning", "memoria", "memory")):
            if _contains_any(lq, ("feedback", "opinion", "calificacion", "calificaciones", "te sirvio")):
                response = self._feedback_learning_reply(user)
            else:
                response = self._learning_reply()
            return finish(response)

        if _contains_any(lq, ("laboratorio", "experimento", "estrategia nueva", "mejora")):
            response = self._lab_reply()
            return finish(response)

        if _contains_any(
            lq,
            (
                "riesgo",
                "risk",
                "stop",
                "target",
                "objetivo",
                "take profit",
                "entry",
                "entrada",
                "trigger",
                "gatillo",
                "invalidation",
                "invalidar",
                "que falta",
                "what is missing",
                "missing",
            ),
        ):
            response = self._opportunity_risk_reply(q, language=language)
            return finish(response)

        if _contains_any(
            lq,
            (
                "alerta",
                "alert",
                "oportunidad",
                "opportunity",
                "resumen",
                "summary",
                "comprar",
                "compra",
                "buy",
                "vender",
                "sell",
                "trade",
                "entry",
                "recomienda",
                "recommend",
                "recomendacion",
                "recommendation",
            ),
        ):
            response = self._opportunity_reply(q, language=language)
            return finish(response)

        symbol = _extract_symbol(q)
        if symbol:
            response = self._opportunity_reply(q, language=language)
            return finish(response)

        response = self._contextual_fallback(recent_turns)
        return finish(response)

    def _apply_language(
        self,
        response: RoxyBrainReply,
        language: str,
        user: str | None,
        session_id: str | None,
        recent_turns: list[dict[str, Any]],
        profile: dict[str, Any],
        query: str,
    ) -> RoxyBrainReply:
        reply = response.reply
        if language == "en":
            reply = self._english_reply_text(response, user, session_id, recent_turns, profile, query)
        return RoxyBrainReply(
            reply=reply,
            intent=response.intent,
            language=language,
            voice_style=_voice_style_for_language(language),
            avatar_state=response.avatar_state,
            emotion=response.emotion,
            should_speak=response.should_speak,
            needs_live_source=response.needs_live_source,
            safety_level=response.safety_level,
            priority=response.priority,
            suggested_actions=response.suggested_actions,
        )

    def _english_reply_text(
        self,
        response: RoxyBrainReply,
        user: str | None,
        session_id: str | None,
        recent_turns: list[dict[str, Any]],
        profile: dict[str, Any],
        query: str,
    ) -> str:
        name = self._display_name(user, profile)
        if response.intent == "greeting":
            mode = _safe_text(profile.get("trading_mode"))
            mode_text = f" Current mode: {mode}." if mode else ""
            return (
                f"Hi{name}. I'm Roxy, your intelligent assistant. I can talk with you in real time, "
                "explain market data, read opportunities, and help you make decisions with more context."
                f"{mode_text}"
            )
        if response.intent == "identity":
            return (
                "My identity should feel professional, clear, and approachable: a synthetic human face, "
                "a professional female voice, calm tone, and direct answers. I should not act like an impulsive "
                "trader; I should explain, compare options, and request confirmation before sensitive actions."
            )
        if response.intent == "capabilities":
            watchlist = profile.get("watchlist") if isinstance(profile.get("watchlist"), list) else []
            watchlist_text = f" Your current watchlist is: {', '.join(watchlist[:6])}." if watchlist else ""
            return (
                "I can hold a natural conversation, read information from the Roxy universe, explain a signal, "
                "summarize news when a source is connected, compare strategies, and recommend next steps. "
                "For live trading, my rule is clear: inform first and execute only with explicit permission."
                f"{watchlist_text}"
            )
        if response.intent == "autonomy_status":
            feedback = self.feedback_memory.summary(user=user)
            feedback_total = int(feedback.get("total", 0) or 0)
            feedback_down = int(feedback.get("down", 0) or 0)
            last_intent = "-"
            for turn in reversed(recent_turns):
                last_intent = _safe_text(turn.get("intent")) or "-"
                if last_intent != "-":
                    break
            if session_id:
                session_text = f"Session {session_id}: {len(recent_turns)} turn(s), last intent {last_intent}."
            else:
                session_text = "No active session_id; I can talk, but session memory will not be saved."
            return (
                f"I'm active{name}. Local voice is ready in Roxy Live, local memory is working, and trading "
                f"guardrails are on. {session_text} Learned feedback: {feedback_total} mark(s), "
                f"{feedback_down} to improve. Recommended next step: keep Wake Roxy on, ask one concrete "
                "question, and use feedback when my answer is not useful."
            )
        if response.intent == "action_confirmation_required":
            symbol = _extract_symbol(query)
            target = f" for {symbol}" if symbol else ""
            return (
                f"I will not execute a trade{target} from a conversational phrase alone. First I need to show "
                "entry, stop, risk, data source, and account status. Then I need explicit confirmation in the "
                "operational flow."
            )
        if response.intent == "news_unavailable":
            return (
                "I can discuss news when the project has a live source connected to the brain. I do not see "
                "fresh headlines in the local brief right now, so I will not invent them. Give me a headline "
                "or connect a news feed and I can explain likely impact."
            )
        if response.intent == "idle":
            if recent_turns:
                last_intent = _safe_text(recent_turns[-1].get("intent"))
                if last_intent:
                    return (
                        f"I'm here{name}. The last topic was {last_intent}. I can continue from there or read "
                        "a new opportunity."
                    )
            return (
                f"I'm here{name}. Ask me about opportunities, learning, the strategy lab, connected news, "
                "or any information you want me to read by voice."
            )
        if response.intent == "followup":
            if recent_turns and _safe_text(recent_turns[-1].get("intent")) == "news_unavailable":
                return (
                    "For news, I need a headline or a connected live source. With that I can summarize impact, "
                    "affected sectors, and possible effect on opportunities."
                )
            return (
                "If you mean the previous opportunity, I can explain the reason, risk, stop, or what is missing "
                "before it becomes a valid entry."
            )
        if response.intent == "fallback":
            return (
                "I'm listening. I can talk, explain dashboard information, read opportunities, summarize learning, "
                "review the strategy lab, or prepare a voice-ready answer."
            )
        return response.reply

    def _apply_feedback_guidance(self, response: RoxyBrainReply, user: str | None) -> RoxyBrainReply:
        if response.intent in {"feedback_learning", "action_confirmation_required"}:
            return response

        guidance = self.feedback_memory.guidance_for_intent(response.intent, user=user)
        if not guidance.get("needs_adjustment"):
            return response

        note = _safe_text(guidance.get("latest_note"))
        if response.language == "en":
            note_text = f" Correction note: {note}." if note else ""
            reply = (
                "Adjustment from your feedback: I will be more direct and separate the read, risk, and next step. "
                f"{response.reply}{note_text}"
            )
        else:
            note_text = f" Nota que voy a corregir: {note}." if note else ""
            reply = (
                "Ajuste por tu feedback: voy mas directo, separando lectura, riesgo y siguiente paso. "
                f"{response.reply}{note_text}"
            )
        return RoxyBrainReply(
            reply=reply,
            intent=response.intent,
            language=response.language,
            voice_style=response.voice_style,
            avatar_state=response.avatar_state,
            emotion=response.emotion,
            should_speak=response.should_speak,
            needs_live_source=response.needs_live_source,
            safety_level=response.safety_level,
            priority=response.priority,
            suggested_actions=response.suggested_actions + ("feedback_adjusted",),
        )

    def learning_snapshot(self, user: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        profile = self.user_profile.read(user)
        feedback = self.feedback_memory.summary(user=user)
        sources = list_knowledge_sources(self.knowledge_paths)
        memory = (
            self.conversation_memory.session_state(session_id=session_id, limit=8)
            if session_id
            else self.conversation_memory.overview(limit=8)
        )
        recommendations = self._learning_recommendations(profile, feedback, sources, memory)
        return {
            "status": "learning",
            "mode": "local_feedback_profile_memory",
            "user": _safe_session_id(user or "local"),
            "session_id": _safe_session_id(session_id) if session_id else "",
            "profile": profile,
            "feedback": feedback,
            "memory": memory,
            "knowledge_sources": sources,
            "recommendations": recommendations,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _learning_recommendations(
        self,
        profile: dict[str, Any],
        feedback: dict[str, Any],
        sources: list[dict[str, Any]],
        memory: dict[str, Any],
    ) -> list[str]:
        recommendations: list[str] = []
        if not profile:
            recommendations.append("Guardar perfil local para adaptar nombre, watchlist, modo y voz.")
        if int(feedback.get("down", 0) or 0) > 0:
            top_down = [
                row.get("intent")
                for row in feedback.get("top_intents", [])
                if isinstance(row, dict) and int(row.get("down", 0) or 0) > 0
            ]
            label = ", ".join(_safe_text(item) for item in top_down[:3] if item) or "respuestas marcadas"
            recommendations.append(f"Revisar y acortar los intents con feedback negativo: {label}.")
        if int(memory.get("total_turns", memory.get("turn_count", 0)) or 0) <= 0:
            recommendations.append("Mantener una sesion conversacional para construir contexto local.")
        missing_sources = [source.get("path") for source in sources if isinstance(source, dict) and not source.get("exists")]
        if missing_sources:
            recommendations.append("Completar fuentes locales faltantes para mejorar lectura del universo Roxy.")
        if not recommendations:
            recommendations.append("Continuar recolectando conversaciones y feedback; el aprendizaje local esta operativo.")
        return recommendations[:5]

    def _contextual_fallback(self, recent_turns: list[dict[str, Any]]) -> RoxyBrainReply:
        last_intent = ""
        for turn in reversed(recent_turns):
            last_intent = _safe_text(turn.get("intent"))
            if last_intent:
                break
        if last_intent == "opportunity":
            return RoxyBrainReply(
                intent="followup",
                reply=(
                    "Si te refieres a la oportunidad anterior, puedo explicarte el motivo, el riesgo, el stop "
                    "o que falta para convertirla en entrada valida."
                ),
                emotion="attentive",
                safety_level="guarded",
                suggested_actions=("ask_why", "ask_risk", "ask_missing_confirmation"),
            )
        if last_intent == "news_unavailable":
            return RoxyBrainReply(
                intent="followup",
                reply=(
                    "Sobre noticias, necesito un titular o una fuente live conectada. Con eso puedo resumir "
                    "impacto, sectores afectados y posible efecto en las oportunidades."
                ),
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("connect_news_source", "paste_headline"),
            )
        return RoxyBrainReply(
            intent="fallback",
            reply=(
                "Te escucho. Puedo conversar, explicar informacion del dashboard, leer oportunidades, "
                "resumir aprendizaje, revisar laboratorio de estrategias o preparar una respuesta para voz."
            ),
            avatar_state="ready",
            emotion="attentive",
            suggested_actions=("ask_latest_opportunity", "ask_learning", "ask_strategy_lab"),
        )

    def _idle_reply(
        self, user: str | None, recent_turns: list[dict[str, Any]], profile: dict[str, Any]
    ) -> RoxyBrainReply:
        name = self._display_name(user, profile)
        if recent_turns:
            last_intent = _safe_text(recent_turns[-1].get("intent"))
            if last_intent:
                return RoxyBrainReply(
                    intent="idle",
                    reply=(
                        f"Estoy aqui{name}. Lo ultimo que estabamos tratando fue {last_intent}. "
                        "Puedo continuar desde ahi o leer una oportunidad nueva."
                    ),
                    avatar_state="ready",
                    emotion="attentive",
                    suggested_actions=("continue_last_topic", "ask_latest_opportunity"),
                )
        return RoxyBrainReply(
            intent="idle",
            reply=(
                f"Estoy aqui{name}. Preguntame por oportunidades, aprendizaje, laboratorio de estrategia, "
                "una noticia conectada al sistema o cualquier informacion que quieras que lea en voz."
            ),
            avatar_state="ready",
            emotion="calm",
            suggested_actions=("ask_latest_opportunity", "ask_market_summary"),
        )

    def _greeting_reply(self, user: str | None, profile: dict[str, Any]) -> RoxyBrainReply:
        name = self._display_name(user, profile)
        mode = _safe_text(profile.get("trading_mode"))
        mode_text = f" Modo actual: {mode}." if mode else ""
        return RoxyBrainReply(
            intent="greeting",
            reply=(
                f"Hola{name}. Soy Roxy, tu asistente inteligente. Puedo hablar contigo en tiempo real, "
                "explicar datos del mercado, leer oportunidades y ayudarte a decidir con mas contexto."
                f"{mode_text}"
            ),
            emotion="warm",
            suggested_actions=("ask_latest_opportunity", "ask_capabilities"),
        )

    def _identity_reply(self) -> RoxyBrainReply:
        return RoxyBrainReply(
            intent="identity",
            reply=(
                "Mi identidad debe sentirse profesional, cercana y clara: rostro humano sintetico, voz femenina, "
                "tono calmado y respuestas directas. No debo actuar como trader impulsiva; debo explicar, "
                "comparar opciones y pedir confirmacion antes de cualquier accion sensible."
            ),
            emotion="professional",
            safety_level="guarded",
            suggested_actions=("align_visual_avatar", "configure_voice_profile"),
        )

    def _capability_reply(self, profile: dict[str, Any]) -> RoxyBrainReply:
        watchlist = profile.get("watchlist") if isinstance(profile.get("watchlist"), list) else []
        watchlist_text = f" Tu watchlist actual es: {', '.join(watchlist[:6])}." if watchlist else ""
        return RoxyBrainReply(
            intent="capabilities",
            reply=(
                "Puedo mantener una conversacion natural, leer informacion del universo Roxy, explicar una senal, "
                "resumir noticias cuando haya fuente conectada, comparar estrategias y recomendar proximos pasos. "
                "Para operaciones reales, mi regla es clara: informar primero y ejecutar solo con permiso explicito."
                f"{watchlist_text}"
            ),
            emotion="confident",
            safety_level="guarded",
            suggested_actions=("connect_realtime_voice", "connect_news_source", "confirm_trade_guardrails"),
        )

    def _autonomy_status_reply(
        self,
        user: str | None,
        session_id: str | None,
        recent_turns: list[dict[str, Any]],
        profile: dict[str, Any],
    ) -> RoxyBrainReply:
        name = self._display_name(user, profile)
        feedback = self.feedback_memory.summary(user=user)
        feedback_total = int(feedback.get("total", 0) or 0)
        feedback_down = int(feedback.get("down", 0) or 0)
        last_intent = "-"
        for turn in reversed(recent_turns):
            last_intent = _safe_text(turn.get("intent")) or "-"
            if last_intent != "-":
                break
        if session_id:
            session_text = f"Sesion {session_id}: {len(recent_turns)} turno(s), ultimo intent {last_intent}."
        else:
            session_text = "Sin session_id activo; puedo conversar, pero la memoria de sesion no se guarda."
        return RoxyBrainReply(
            intent="autonomy_status",
            reply=(
                f"Estoy activa{name}. Voz local lista en Roxy Live, memoria local operativa y guardrails de trading "
                f"encendidos. {session_text} Feedback aprendido: {feedback_total} marca(s), {feedback_down} a mejorar. "
                "Siguiente paso recomendado: mantener Wake Roxy activo, hacer una pregunta concreta y usar feedback "
                "cuando mi respuesta no sea util."
            ),
            avatar_state="ready",
            emotion="attentive",
            safety_level="guarded",
            suggested_actions=("enable_wake_roxy", "ask_latest_opportunity", "review_learning_status"),
        )

    def _display_name(self, user: str | None, profile: dict[str, Any]) -> str:
        preferred = _safe_text(profile.get("preferred_name"))
        raw = preferred or _safe_text(user)
        return f" {raw}" if raw else ""

    def _action_guardrail_reply(self, query: str) -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        target = f" para {symbol}" if symbol else ""
        return RoxyBrainReply(
            intent="action_confirmation_required",
            reply=(
                f"No voy a ejecutar una operacion{target} solo por una frase conversacional. "
                "Primero debo mostrar entrada, stop, riesgo, fuente de datos y estado de cuenta. "
                "Despues necesito una confirmacion explicita en el flujo operacional."
            ),
            avatar_state="blocked",
            emotion="serious",
            safety_level="critical",
            priority="high",
            suggested_actions=("show_trade_ticket", "show_risk_check", "require_explicit_confirmation"),
        )

    def _news_reply(self, language: str = "es") -> RoxyBrainReply:
        brief = _load_json(self.brief_path)
        news_items = brief.get("news") or brief.get("market_news") or []
        if isinstance(news_items, list) and news_items:
            headlines = []
            for item in news_items[:3]:
                if isinstance(item, dict):
                    title = _safe_text(item.get("title") or item.get("headline"))
                    source = _safe_text(item.get("source"))
                    if title:
                        headlines.append(f"{title}" + (f" ({source})" if source else ""))
                elif item:
                    headlines.append(_safe_text(item))
            if headlines:
                prefix = "Relevant news: " if language == "en" else "Noticias relevantes: "
                return RoxyBrainReply(
                    intent="news",
                    reply=prefix + " ".join(f"{idx + 1}. {headline}." for idx, headline in enumerate(headlines)),
                    emotion="informative",
                    suggested_actions=("ask_news_impact", "ask_latest_opportunity"),
                )

        if language == "en":
            return RoxyBrainReply(
                intent="news_unavailable",
                reply=(
                    "I can discuss news when the project has a live source connected to the brain. I do not see "
                    "fresh headlines in the local brief right now, so I will not invent them. Give me a headline "
                    "or connect a news feed and I can explain likely impact."
                ),
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("connect_news_source", "ask_market_summary"),
            )

        return RoxyBrainReply(
            intent="news_unavailable",
            reply=(
                "Puedo hablar de noticias cuando el proyecto tenga una fuente live conectada al cerebro. "
                "Ahora no veo titulares frescos en el brief local, asi que no voy a inventarlos. "
                "Puedo explicar el impacto si me das el titular o si conectamos el feed de noticias."
            ),
            emotion="cautious",
            needs_live_source=True,
            safety_level="guarded",
            suggested_actions=("connect_news_source", "ask_market_summary"),
        )

    def _market_summary_reply(self, language: str = "es") -> RoxyBrainReply:
        brief = _load_json(self.brief_path)
        gate = brief.get("alert_gate_summary") if isinstance(brief.get("alert_gate_summary"), dict) else {}
        plan = brief.get("daily_opportunity_plan") if isinstance(brief.get("daily_opportunity_plan"), dict) else {}
        rows = plan.get("opportunities") if isinstance(plan.get("opportunities"), list) else []
        if not rows:
            rows = brief.get("opportunities") if isinstance(brief.get("opportunities"), list) else []
        if not rows:
            rows = brief.get("crypto_scan_candidates") if isinstance(brief.get("crypto_scan_candidates"), list) else []

        if not rows and not gate:
            if language == "en":
                reply = (
                    "I do not have enough local market data to classify the regime yet. Connect or refresh the scan "
                    "before relying on a trend read."
                )
            else:
                reply = (
                    "Todavia no tengo suficientes datos locales para clasificar el regimen del mercado. "
                    "Conecta o refresca el escaneo antes de usar una lectura de tendencia."
                )
            return RoxyBrainReply(
                intent="market_summary",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "connect_live_data"),
            )

        condition = self._infer_market_condition(rows)
        total = int(gate.get("total_opportunities") or len(rows))
        watch_count = int(
            gate.get("watch_count")
            or sum(1 for row in rows if isinstance(row, dict) and _safe_text(row.get("signal")).upper() == "WATCH")
        )
        ready_ratio = _safe_float(gate.get("ready_ratio"))
        top_gate = _localize_market_phrase(gate.get("top_gate_label") or gate.get("top_gate") or "-", language)
        top_readiness = _safe_float(gate.get("top_readiness"))
        market_counts = plan.get("market_counts") if isinstance(plan.get("market_counts"), dict) else {}
        markets = ", ".join(f"{key}:{value}" for key, value in sorted(market_counts.items())) if market_counts else "-"
        session = plan.get("market_session") if isinstance(plan.get("market_session"), dict) else {}
        stock_session = _safe_text(session.get("stock_session") or "-")
        crypto_session = _safe_text(session.get("crypto_session") or "-")

        if language == "en":
            condition_text = {
                "bullish": "bullish watch",
                "bearish": "bearish watch",
                "sideways": "sideways/wait",
                "unknown": "unclear/wait",
            }[condition]
            ready_text = "-" if ready_ratio is None else f"{ready_ratio * 100:.1f}%"
            top_readiness_text = "-" if top_readiness is None else f"{top_readiness:.1f}"
            reply = (
                f"Local market regime: {condition_text}. I see {total} opportunity row(s), {watch_count} in watch mode, "
                f"ready ratio {ready_text}, top gate {top_gate}, top readiness {top_readiness_text}. "
                f"Markets: {markets}. Stock session: {stock_session}; crypto session: {crypto_session}. "
                "Risk note: this is a decision-support read, not a guarantee or an execution command."
            )
        else:
            condition_text = {
                "bullish": "alcista en observacion",
                "bearish": "bajista en observacion",
                "sideways": "lateral/esperar",
                "unknown": "poco claro/esperar",
            }[condition]
            ready_text = "-" if ready_ratio is None else f"{ready_ratio * 100:.1f}%"
            top_readiness_text = "-" if top_readiness is None else f"{top_readiness:.1f}"
            reply = (
                f"Regimen local del mercado: {condition_text}. Veo {total} oportunidad(es), {watch_count} en modo watch, "
                f"ready ratio {ready_text}, filtro principal {top_gate}, readiness maxima {top_readiness_text}. "
                f"Mercados: {markets}. Sesion acciones: {stock_session}; cripto: {crypto_session}. "
                "Nota de riesgo: esto es apoyo de decision, no garantia ni orden de ejecucion."
            )

        return RoxyBrainReply(
            intent="market_summary",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            suggested_actions=("ask_latest_opportunity", "ask_risk", "run_scan"),
        )

    def _infer_market_condition(self, rows: list[Any]) -> str:
        bullish = 0
        bearish = 0
        sideways = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = " ".join(
                _safe_text(row.get(key))
                for key in (
                    "signal",
                    "raw_signal",
                    "trend_setup",
                    "trigger_setup",
                    "mtf_explanation",
                    "mtf_channel",
                    "strategy",
                    "reasons",
                )
            ).lower()
            trend_score = _safe_float(row.get("trend_score") or row.get("ai_score") or row.get("readiness"))
            if "sell" in text or "bearish" in text or "bajista" in text or "downtrend" in text:
                bearish += 1
            elif "lateral" in text or "sideways" in text or "range" in text:
                sideways += 1
            elif (
                "buy" in text
                or "bullish" in text
                or "alcista" in text
                or "uptrend" in text
                or "pullback" in text
                or (trend_score is not None and trend_score >= 70)
            ):
                bullish += 1

        if bullish > max(bearish, sideways):
            return "bullish"
        if bearish > max(bullish, sideways):
            return "bearish"
        if sideways > 0:
            return "sideways"
        return "unknown"

    def _learning_reply(self) -> RoxyBrainReply:
        brief = _load_json(self.brief_path)
        profiles = brief.get("learning_profiles") or []
        if not profiles:
            memory = _load_json(self.memory_path)
            stats = memory.get("strategy_stats") or {}
            profiles = [
                {
                    "strategy_family": family,
                    "bias": values.get("bias") or "learning",
                    "alerts": values.get("alerts", 0),
                    "lesson": values.get("learning_note", ""),
                }
                for family, values in stats.items()
                if isinstance(values, dict)
            ]

        if not profiles:
            return RoxyBrainReply(
                intent="learning",
                reply=(
                    "Todavia estoy construyendo memoria. La decision correcta es recolectar mas senales cerradas "
                    "antes de cambiar reglas de estrategia."
                ),
                emotion="analytical",
                suggested_actions=("collect_more_closed_signals",),
            )

        lines = []
        for profile in profiles[:4]:
            family = _safe_text(profile.get("strategy_family") or "estrategia")
            bias = _safe_text(profile.get("bias") or "learning")
            alerts = int(profile.get("alerts", 0) or 0)
            lesson = _safe_text(profile.get("lesson") or profile.get("learning_note"))
            lines.append(f"{family}: sesgo {bias}, {alerts} alerta(s). {lesson}".strip())
        return RoxyBrainReply(
            intent="learning",
            reply=" ".join(lines),
            emotion="analytical",
            suggested_actions=("ask_strategy_lab",),
        )

    def _feedback_learning_reply(self, user: str | None = None) -> RoxyBrainReply:
        summary = self.feedback_memory.summary(user=user)
        total = int(summary.get("total", 0) or 0)
        if total <= 0:
            return RoxyBrainReply(
                intent="feedback_learning",
                reply=(
                    "Todavia no tengo feedback guardado para aprender de tus preferencias. "
                    "Usa los botones de feedback despues de una respuesta y ajustare mi lectura local."
                ),
                emotion="analytical",
                suggested_actions=("give_feedback", "ask_latest_opportunity"),
            )
        up = int(summary.get("up", 0) or 0)
        down = int(summary.get("down", 0) or 0)
        intent_lines = []
        for row in summary.get("top_intents", [])[:3]:
            intent_lines.append(f"{row.get('intent')}: {row.get('up', 0)} utiles, {row.get('down', 0)} a mejorar")
        detail = "; ".join(intent_lines) if intent_lines else "sin patron por intent todavia"
        return RoxyBrainReply(
            intent="feedback_learning",
            reply=(
                f"He recibido {total} feedback(s): {up} utiles y {down} a mejorar. "
                f"Patrones principales: {detail}. Usare esto para priorizar respuestas mas claras y directas."
            ),
            emotion="analytical",
            suggested_actions=("review_feedback", "ask_capabilities"),
        )

    def _lab_reply(self) -> RoxyBrainReply:
        brief = _load_json(self.brief_path)
        lab_rows = brief.get("strategy_lab") or brief.get("research_queue") or []
        if not isinstance(lab_rows, list) or not lab_rows:
            return RoxyBrainReply(
                intent="strategy_lab",
                reply=(
                    "No hay experimentos listos para promover. Mi recomendacion estrategica es mantener el sistema "
                    "en observacion y esperar mas datos antes de endurecer o relajar filtros."
                ),
                emotion="analytical",
                suggested_actions=("collect_more_closed_signals",),
            )

        lines = []
        for row in lab_rows[:4]:
            if not isinstance(row, dict):
                continue
            family = _safe_text(row.get("strategy_family") or "-")
            state = _safe_text(row.get("lab_state") or row.get("priority") or "-")
            decision = _safe_text(row.get("lab_decision") or row.get("idea"))
            rule = _safe_text(row.get("experiment_rule") or row.get("rule"))
            lines.append(f"{family}: estado {state}. {decision} Regla: {rule}".strip())
        return RoxyBrainReply(
            intent="strategy_lab",
            reply=" ".join(lines),
            emotion="analytical",
            suggested_actions=("ask_learning",),
        )

    def _knowledge_reply(self, query: str) -> RoxyBrainReply:
        match = self._best_knowledge_match(query)
        if not match:
            return RoxyBrainReply(
                intent="knowledge",
                reply=(
                    "No encontre una fuente local clara para esa pregunta dentro del universo Roxy. "
                    "Puedo responder mejor si la conectamos a un documento, nota o brief especifico."
                ),
                emotion="cautious",
                suggested_actions=("attach_document", "ask_latest_opportunity"),
            )

        path, excerpt = match
        return RoxyBrainReply(
            intent="knowledge",
            reply=f"Segun {path}: {excerpt}",
            emotion="informative",
            suggested_actions=("ask_followup", "open_source_document"),
        )

    def _best_knowledge_match(self, query: str) -> tuple[str, str] | None:
        query_terms = _tokenize(query)
        if not query_terms:
            return None

        best_score = 0
        best_path: Path | None = None
        best_text = ""
        for path in self.knowledge_paths:
            if not path.exists() or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:MAX_KNOWLEDGE_CHARS]
            except Exception:
                continue
            searchable = " ".join(_tokenize(text))
            score = sum(1 for term in query_terms if term in searchable)
            if score > best_score:
                best_score = score
                best_path = path
                best_text = text

        if best_score <= 0 or best_path is None:
            return None
        return str(best_path), _knowledge_excerpt(best_text, query_terms)

    def _opportunity_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            if language == "en":
                target = f" for {symbol}" if symbol else ""
                reply = (
                    f"I do not see a clear opportunity{target} in the current brief. The right response is to wait "
                    "for fresh data or run a scan before recommending an entry."
                )
            else:
                target = f" para {symbol}" if symbol else ""
                reply = (
                    f"No veo una oportunidad clara{target} en el brief actual. La respuesta correcta es esperar "
                    "datos nuevos o pedir un escaneo antes de recomendar entrada."
                )
            return RoxyBrainReply(
                intent="opportunity",
                reply=reply,
                emotion="cautious",
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        action = _safe_text(row.get("ai_action") or row.get("signal") or "WATCH")
        family = _safe_text(row.get("strategy_family") or "-")
        decision = _safe_text(row.get("trade_decision") or row.get("decision") or "-")
        explanation = _safe_text(row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))
        if language == "en":
            reply = (
                f"{symbol_text}: status {action}, strategy {family}, decision {decision}. "
                f"Entry {_price(row.get('entry'))}, stop {_price(row.get('stop'))}, "
                f"risk {_pct(row.get('risk_pct'))}, target {_pct(row.get('recommended_target_pct') or row.get('target_pct'))}. "
                f"{explanation}"
            ).strip()
        else:
            reply = (
                f"{symbol_text}: estado {action}, estrategia {family}, decision {decision}. "
                f"Entrada {_price(row.get('entry'))}, stop {_price(row.get('stop'))}, "
                f"riesgo {_pct(row.get('risk_pct'))}, objetivo {_pct(row.get('recommended_target_pct') or row.get('target_pct'))}. "
                f"{explanation}"
            ).strip()
        return RoxyBrainReply(
            intent="opportunity",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if action.upper() in {"ALERT", "BUY", "SELL"} else "normal",
            suggested_actions=("ask_why", "ask_risk", "confirm_before_execution"),
        )

    def _opportunity_risk_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"I do not have a local opportunity{target} with enough risk data. Run or refresh the scan first."
                if language == "en"
                else f"No tengo una oportunidad local{target} con suficientes datos de riesgo. Refresca el escaneo primero."
            )
            return RoxyBrainReply(
                intent="opportunity_risk",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH")
        decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
        if language == "en":
            decision = _localize_market_phrase(decision, language)
        entry = _price(row.get("entry"))
        stop = _price(row.get("stop"))
        risk = _pct(row.get("risk_pct"))
        target_2 = _price(row.get("target_2") or row.get("target_2pct"))
        target_5 = _price(row.get("target_5") or row.get("target_5pct"))
        target_10 = _price(row.get("target_10") or row.get("target_10pct"))
        target_pct = _pct(row.get("recommended_target_pct") or row.get("target_pct"))
        trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
        invalidation = _safe_text(row.get("invalidation") or row.get("exit_condition"))
        missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
        why = _safe_text(row.get("why") or row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))
        if language == "en":
            trigger = _localize_market_phrase(trigger, language)
            invalidation = _localize_market_phrase(invalidation, language)
            missing = _localize_market_phrase(missing, language)
            why = _localize_market_phrase(why, language)
        trigger = _sentence_fragment(trigger)
        invalidation = _sentence_fragment(invalidation)
        missing = _sentence_fragment(missing)
        why = _sentence_fragment(why)
        readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
        probability = _safe_float(row.get("probability"))
        quality = _safe_text(row.get("quality"))

        readiness_text = "-" if readiness is None else f"{readiness:.1f}"
        probability_text = "-" if probability is None else f"{probability:.0f}%"
        if language == "en":
            reply = (
                f"{symbol_text} risk plan: action {action}, decision {decision}, entry {entry}, stop {stop}, "
                f"risk {risk}. Targets: 2% {target_2}, 5% {target_5}, 10% {target_10}, recommended target {target_pct}. "
                f"Trigger: {trigger or '-'}. Invalidation: {invalidation or '-'}. "
                f"Missing: {missing or '-'}. Readiness {readiness_text}, probability {probability_text}, quality {quality or '-'}. "
                f"Reason: {why or '-'}. This is not an execution order; confirmation is required before any trade."
            )
        else:
            reply = (
                f"{symbol_text} plan de riesgo: accion {action}, decision {decision}, entrada {entry}, stop {stop}, "
                f"riesgo {risk}. Targets: 2% {target_2}, 5% {target_5}, 10% {target_10}, objetivo recomendado {target_pct}. "
                f"Gatillo: {trigger or '-'}. Invalidacion: {invalidation or '-'}. "
                f"Falta: {missing or '-'}. Readiness {readiness_text}, probabilidad {probability_text}, calidad {quality or '-'}. "
                f"Razon: {why or '-'}. Esto no es una orden de ejecucion; requiere confirmacion antes de operar."
            )
        return RoxyBrainReply(
            intent="opportunity_risk",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if action.upper() in {"ALERT", "BUY", "SELL"} else "normal",
            suggested_actions=("show_trade_ticket", "ask_market_summary", "confirm_before_execution"),
        )

    def _latest_opportunity(self, symbol: str | None) -> dict[str, Any]:
        brief = _load_json(self.brief_path)
        plan = brief.get("daily_opportunity_plan") if isinstance(brief.get("daily_opportunity_plan"), dict) else {}
        rows = plan.get("opportunities") if isinstance(plan.get("opportunities"), list) else []
        if not rows:
            rows = brief.get("opportunities") or []
        if not rows:
            rows = brief.get("crypto_scan_candidates") or []
        if not isinstance(rows, list):
            return {}
        if symbol:
            target = symbol.upper()
            for row in rows:
                if isinstance(row, dict) and _safe_text(row.get("symbol")).upper() == target:
                    return row
        for row in rows:
            if isinstance(row, dict):
                return row
        return {}


def generate_interactive_reply(query: str, user: str | None = None) -> str:
    return RoxyInteractiveBrain().generate_reply(query, user=user).reply
