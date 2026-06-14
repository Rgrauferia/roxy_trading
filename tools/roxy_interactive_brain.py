from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from tools import weather_service


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
SYMBOL_INFERENCE_INTENTS = {
    "opportunity",
    "opportunity_reason",
    "opportunity_risk",
    "technical_indicators",
    "support_resistance",
    "trading_dashboard_handoff",
    "trade_readiness",
    "pre_trade_preflight",
    "trade_ticket",
    "position_size",
    "monitoring_plan",
    "alert_draft",
    "news_impact",
    "watchlist",
    "action_confirmation_required",
}


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
    active_symbol: str = ""
    active_market: str = ""
    active_timeframe: str = ""
    action_url: str = ""
    action_label: str = ""
    action_kind: str = ""

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
            "active_symbol": self.active_symbol,
            "active_market": self.active_market,
            "active_timeframe": self.active_timeframe,
            "action_url": self.action_url,
            "action_label": self.action_label,
            "action_kind": self.action_kind,
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
            "active_symbol": response.active_symbol,
            "action_url": response.action_url,
            "action_label": response.action_label,
            "action_kind": response.action_kind,
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
        active_context = _active_conversation_context(turns)
        return {
            "session_id": _safe_session_id(session_id or "local"),
            "turn_count": len(turns),
            "last_intent": _safe_text(last_turn.get("intent")),
            "last_safety_level": _safe_text(last_turn.get("safety_level")),
            "active_context": active_context,
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
            active_context = _active_conversation_context([turn for turn in turns if isinstance(turn, dict)])
            rows.append(
                {
                    "session_id": _safe_session_id(session_id),
                    "turn_count": len(turns),
                    "last_intent": _safe_text(last_turn.get("intent")),
                    "last_at": _safe_text(last_turn.get("at")),
                    "last_safety_level": _safe_text(last_turn.get("safety_level")),
                    "active_symbol": _safe_text(active_context.get("active_symbol")).upper(),
                    "active_market": _safe_text(active_context.get("active_market")),
                    "active_timeframe": _safe_text(active_context.get("active_timeframe")),
                    "action_url": _safe_text(active_context.get("action_url")),
                    "action_label": _safe_text(active_context.get("action_label")),
                    "action_kind": _safe_text(active_context.get("action_kind")),
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
        active_symbol = response.active_symbol
        if not active_symbol and response.intent in SYMBOL_INFERENCE_INTENTS:
            active_symbol = _extract_symbol(f"{query} {response.reply}") or ""
        turns.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "query": _redact_sensitive_text(query),
                "reply": _redact_sensitive_text(response.reply),
                "intent": response.intent,
                "safety_level": response.safety_level,
                "language": response.language,
                "priority": response.priority,
                "needs_live_source": response.needs_live_source,
                "suggested_actions": list(response.suggested_actions),
                "active_symbol": active_symbol,
                "active_market": response.active_market,
                "active_timeframe": response.active_timeframe,
                "action_url": response.action_url,
                "action_label": response.action_label,
                "action_kind": response.action_kind,
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
        "location",
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
            elif key == "location":
                location = re.sub(r"[^A-Za-z0-9, .'-]+", "", str(value or "")).strip()
                if location:
                    clean[key] = location[:120]
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


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _money(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "-"
    if 0 < abs(number) < 1:
        return f"{number:.6f}".rstrip("0").rstrip(".")
    return f"{number:.2f}"


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _strip_voice_preamble(query: str) -> str:
    text = str(query or "").strip()
    if not text:
        return ""
    cleaned = text
    preamble_patterns = (
        r"(?i)^\s*(?:hola|hello|hi|hey|buenos dias|buenas tardes|buenas noches|buenas)\s*,?\s+roxy\b[\s,.:;-]*",
        r"(?i)^\s*roxy\b[\s,.:;-]*",
        r"(?i)^\s*(?:hola|hello|hi|hey|buenos dias|buenas tardes|buenas noches|buenas)\b[\s,.:;-]*",
    )
    changed = True
    while changed:
        changed = False
        for pattern in preamble_patterns:
            updated = re.sub(pattern, "", cleaned, count=1).strip()
            if updated != cleaned:
                cleaned = updated
                changed = True
    return cleaned or text


def _is_knowledge_query(text: str) -> bool:
    normalized = str(text or "").lower()
    phrase_terms = (
        "explica el sistema",
        "explain the system",
        "explicame el sistema",
        "universo roxy",
        "roxy trading",
        "como funciona",
        "how does it work",
    )
    if any(term in normalized for term in phrase_terms):
        return True
    tokens = set(re.findall(r"[a-záéíóúñ]+", normalized))
    return bool(tokens & {"lee", "read", "documento", "document", "manual"})


def _is_sports_result_query(text: str) -> bool:
    normalized = str(text or "").lower()
    sports_terms = {
        "partido",
        "resultado",
        "marcador",
        "futbol",
        "fútbol",
        "soccer",
        "football",
        "game",
        "score",
        "match",
    }
    team_terms = {"brazil", "brasil", "morocco", "maruecos"}
    tokens = set(re.findall(r"[a-záéíóúñ]+", normalized))
    return bool(tokens & sports_terms) and (bool(tokens & team_terms) or " vs " in normalized or " con " in normalized)


def _is_crypto_market_query(text: str) -> bool:
    normalized = str(text or "").lower().strip()
    if normalized in {"crypto", "cripto", "criptomonedas", "cryptocurrency", "cryptocurrencies"}:
        return True
    return _contains_any(
        normalized,
        (
            "mercado cripto",
            "mercado de criptomonedas",
            "resumen cripto",
            "resumen de cripto",
            "crypto market",
            "crypto summary",
            "cryptocurrency market",
        ),
    )


def _row_is_crypto(row: dict[str, Any]) -> bool:
    symbol = _safe_text(row.get("symbol") or row.get("ticker")).upper().replace("-", "/")
    market = _safe_text(row.get("market") or row.get("asset_class") or row.get("asset_type") or row.get("type")).lower()
    if "crypto" in market or "cripto" in market:
        return True
    return "/" in symbol and symbol.split("/", 1)[1] in {"USD", "USDT", "USDC"}


def _parse_compact_number(raw: str, suffix: str = "") -> float | None:
    try:
        number = float(str(raw or "").replace(",", ""))
    except ValueError:
        return None
    suffix = str(suffix or "").lower()
    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000
    return number


def _extract_query_equity(query: str) -> float | None:
    text = str(query or "")
    number = r"([\d][\d,]*(?:\.\d+)?)\s*([kKmM]?)"
    for marker in ("capital", "cuenta", "saldo", "account", "equity", "balance", "portfolio"):
        match = re.search(
            rf"(?i)\b{marker}\b\s*(?:de|of|is|=|:|con|with)?\s*\$?\s*{number}",
            text,
        )
        if match:
            return _parse_compact_number(match.group(1), match.group(2))
    match = re.search(rf"\$\s*{number}", text)
    if match:
        return _parse_compact_number(match.group(1), match.group(2))
    return None


def _extract_query_risk_fraction(query: str) -> tuple[float | None, bool]:
    text = str(query or "")
    for marker in ("riesgo", "risk", "arriesga", "arriesgar", "risking"):
        match = re.search(rf"(?i)\b{marker}\b\s*(?:de|=|:)?\s*([\d]+(?:\.\d+)?)\s*%", text)
        if match:
            value = _safe_float(match.group(1))
            if value is not None and value > 0:
                return value / 100, True
    return None, False


def _extract_query_timeframe(query: str) -> str:
    text = str(query or "").lower()
    if re.search(r"\b15\s*m(?:in|inutos?)?\b|\b15m\b", text):
        return "15m"
    if re.search(r"\b2\s*h(?:oras?)?\b|\b2h\b", text):
        return "2h"
    if re.search(r"\b4\s*h(?:oras?)?\b|\b4h\b", text):
        return "4h"
    if re.search(r"\b1\s*d(?:ia|ía|ay)?\b|\b1d\b|\bdiario\b|\bdaily\b", text):
        return "1d"
    return "1h"


def _trading_dashboard_url(symbol: str, market: str, timeframe: str) -> str:
    clean_symbol = _safe_text(symbol).upper() or "SPY"
    clean_market = "crypto" if _safe_text(market).lower() == "crypto" or "/" in clean_symbol else "stock"
    clean_timeframe = _extract_query_timeframe(timeframe)
    return (
        "http://127.0.0.1:8501/?view=Activo"
        f"&symbol={quote(clean_symbol, safe='')}"
        f"&market={quote(clean_market, safe='')}"
        f"&tf={quote(clean_timeframe, safe='')}"
    )


def _detect_language(query: str, profile: dict[str, Any]) -> str:
    preferred = _safe_text(profile.get("language")).lower()
    normalized = str(query or "").lower()
    if any(phrase in normalized for phrase in ("ticket de trade", "ticket operativo", "preflight operativo")):
        return "es"
    english_terms = {
        "hello",
        "hi",
        "what",
        "who",
        "status",
        "market",
        "news",
        "daily",
        "brief",
        "briefing",
        "indicator",
        "indicators",
        "technical",
        "ema",
        "rsi",
        "macd",
        "vwap",
        "bollinger",
        "volume",
        "level",
        "levels",
        "support",
        "resistance",
        "trade",
        "trading",
        "preflight",
        "operational",
        "before",
        "ticket",
        "handoff",
        "opportunity",
        "risk",
        "buy",
        "sell",
        "recommend",
        "recommendation",
        "help",
        "explain",
        "read",
        "document",
        "manual",
        "voice",
        "safety",
        "learning",
        "memory",
        "autonomous",
        "continue",
        "details",
        "more",
        "why",
        "position",
        "size",
        "shares",
        "equity",
        "capital",
        "account",
        "cash",
        "portfolio",
        "positions",
        "buying",
        "power",
        "checklist",
        "valid",
        "ready",
        "compare",
        "opportunities",
        "top",
        "best",
        "ranking",
        "rank",
        "monitor",
        "monitoring",
        "watch",
        "track",
        "alert",
        "notify",
        "notification",
        "when",
        "data",
        "fresh",
        "freshness",
        "source",
        "updated",
        "should",
        "safe",
        "go",
        "no",
        "readiness",
        "session",
        "hours",
        "open",
        "closed",
        "regular",
        "extended",
        "premarket",
        "crypto",
        "cryptocurrency",
        "cryptocurrencies",
        "recap",
        "summarize",
        "weather",
        "forecast",
        "temperature",
        "discuss",
        "catch",
        "speed",
        "miss",
        "left",
        "off",
    }
    spanish_terms = {
        "hola",
        "que",
        "quien",
        "estado",
        "mercado",
        "noticia",
        "diario",
        "briefing",
        "indicador",
        "indicadores",
        "tecnico",
        "técnico",
        "ema",
        "rsi",
        "macd",
        "vwap",
        "bollinger",
        "volumen",
        "nivel",
        "niveles",
        "soporte",
        "resistencia",
        "operacion",
        "operativo",
        "operativa",
        "revision",
        "revisión",
        "ticket",
        "oportunidad",
        "riesgo",
        "compra",
        "vende",
        "ayuda",
        "explica",
        "lee",
        "documento",
        "manual",
        "voz",
        "seguridad",
        "aprendizaje",
        "memoria",
        "autonomo",
        "continua",
        "detalles",
        "mas",
        "porque",
        "tamano",
        "tamaño",
        "cantidad",
        "acciones",
        "capital",
        "cuenta",
        "efectivo",
        "portafolio",
        "portfolio",
        "posiciones",
        "comprador",
        "checklist",
        "valida",
        "listo",
        "compara",
        "comparar",
        "oportunidades",
        "mejores",
        "ranking",
        "monitoreo",
        "vigilar",
        "seguimiento",
        "alerta",
        "avisame",
        "avísame",
        "cuando",
        "prepara",
        "datos",
        "frescura",
        "fuente",
        "actualizado",
        "actualizaste",
        "debo",
        "puedo",
        "seguro",
        "decision",
        "decisión",
        "sesion",
        "sesión",
        "cripto",
        "criptomonedas",
        "resumir",
        "hablamos",
        "clima",
        "tiempo",
        "temperatura",
        "pronostico",
        "pronóstico",
        "abre",
        "abrir",
        "pagina",
        "página",
        "pantalla",
        "terminal",
    }
    tokens = set(re.findall(r"[a-záéíóúñ]+", normalized))
    english_score = len(tokens.intersection(english_terms))
    spanish_score = len(tokens.intersection(spanish_terms))
    if preferred.startswith("en"):
        if spanish_score >= 2 and spanish_score > english_score:
            return "es"
        return "en"
    if preferred.startswith("es"):
        if english_score >= 2 and english_score > spanish_score:
            return "en"
        return "es"
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
        "Cerrado": "Closed",
        "Mercado abierto": "Regular market open",
        "After-hours": "After-hours",
        "Premarket": "Premarket",
        "Fin de semana; acciones/opciones solo para estudio.": "Weekend; stocks/options are study-only.",
        "Confirmar volumen y spreads antes de entrar.": "Confirm volume and spreads before entering.",
        "Acciones/opciones con liquidez regular.": "Stocks/options have regular-session liquidity.",
        "Solo setups muy claros; spreads pueden abrirse.": "Only very clear setups; spreads can widen.",
        "Fuera de horario extendido; esperar siguiente sesion.": "Outside extended hours; wait for the next session.",
        "Crypto sigue disponible 24h; vigilar liquidez y volatilidad.": "Crypto remains available 24h; watch liquidity and volatility.",
        "Esperar gatillo BUY en 15m mientras 1h sigue valido.": "Wait for a 15m BUY trigger while 1h remains valid.",
        "Invalidar si pierde": "Invalidate if it loses",
        "No operar todavia: faltan condiciones importantes del checklist.": "Do not trade yet: important checklist conditions are still missing.",
        "15m da entrada": "15m entry",
        "2h/4h validan": "2h/4h validation",
        "2h/4h contradicen el gatillo": "2h/4h contradict the trigger",
        "Volumen acompana": "Volume confirms",
        "falta volumen": "missing volume",
        "Solo alertar cuando 1h confirma, 15m da entrada, volumen acompana, riesgo es bajo y target 2% es viable.": (
            "Only alert when 1h confirms, 15m gives entry, volume confirms, risk is low, and 2% target is viable."
        ),
    }
    if text in translations:
        return translations[text]
    localized = text
    for source, target in translations.items():
        localized = localized.replace(source, target)
    return localized


def _sentence_fragment(value: Any) -> str:
    return _safe_text(value).rstrip(" .")


def _symbol_matches(row_symbol: Any, requested_symbol: str) -> bool:
    row = _safe_text(row_symbol).upper().replace("-", "/")
    requested = _safe_text(requested_symbol).upper().replace("-", "/")
    if not row or not requested:
        return False
    if row == requested:
        return True
    return row.split("/", 1)[0] == requested.split("/", 1)[0]


def _is_placeholder_headline(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", _safe_text(text).lower()).strip(" .:-")
    if not normalized:
        return True
    placeholders = {
        "headline",
        "news",
        "noticia",
        "titular",
        "paste headline",
        "paste the headline",
        "pega titular",
        "pega el titular",
        "pega aqui el titular",
        "pega aqui la noticia",
        "pega aqui el titular real",
    }
    return normalized in placeholders


def _extract_headline_from_query(query: str) -> str:
    text = _safe_text(query)
    if not text:
        return ""

    quoted = re.search(r"[\"']([^\"']{12,500})[\"']", text)
    if quoted:
        candidate = quoted.group(1).strip()
        return "" if _is_placeholder_headline(candidate) else candidate[:500]

    marker_pattern = re.compile(
        r"(?is)(?:news impact|headline impact|impacto de noticia|impacto del titular|"
        r"analiza(?:r)?(?: la| el)? noticia|analiza(?:r)?(?: el)? titular|analyze news|"
        r"news sentiment|sentimiento de noticia|sentimiento del titular|headline|titular|noticia|news)"
        r"\s*[:\-]\s*(.+)"
    )
    match = marker_pattern.search(text)
    if match:
        candidate = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        return "" if _is_placeholder_headline(candidate) else candidate[:500]

    stripped = re.sub(
        r"(?is)^\s*(?:roxy,?\s*)?(?:analiza(?:r)?(?: el)? impacto(?: de)?(?: la)? noticia|"
        r"analiza(?:r)?(?: el)? titular|analyze(?: the)? news(?: impact)?|news impact|"
        r"headline impact|sentimiento de noticia|news sentiment)\s+",
        "",
        text,
    ).strip(" .:-")
    if stripped != text and len(re.findall(r"\w+", stripped)) >= 5 and not _is_placeholder_headline(stripped):
        return stripped[:500]
    return ""


def _news_item_fields(item: Any) -> tuple[str, str, str]:
    if isinstance(item, dict):
        headline = _safe_text(item.get("title") or item.get("headline") or item.get("summary"))
        source = _safe_text(item.get("source") or item.get("publisher"))
        timestamp = _safe_text(
            item.get("published_at")
            or item.get("timestamp")
            or item.get("time")
            or item.get("updated_at")
            or item.get("created_at")
        )
    else:
        headline = _safe_text(item)
        source = ""
        timestamp = ""
    return headline[:500], source[:80], timestamp[:80]


def _first_news_item_from_brief(brief: dict[str, Any]) -> tuple[str, str, str]:
    news_items = brief.get("news") or brief.get("market_news") or []
    if not isinstance(news_items, list):
        return "", "", ""
    for item in news_items:
        headline, source, timestamp = _news_item_fields(item)
        if headline:
            return headline, source, timestamp
    return "", "", ""


def _news_detail_parts(source: str, timestamp: str, language: str = "es") -> list[str]:
    parts = []
    if source:
        parts.append(source)
    if timestamp:
        parts.append(timestamp)
        freshness = _news_timestamp_freshness(timestamp, language)
        if freshness:
            parts.append(freshness)
    else:
        parts.append("timestamp missing" if language == "en" else "hora no disponible")
    return parts


def _news_timestamp_freshness(timestamp: str, language: str = "es") -> str:
    parsed = _parse_iso_datetime(timestamp)
    if parsed is None:
        return "time not verified" if language == "en" else "hora no verificable"
    age_minutes = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60)
    age_text = f"{age_minutes:.0f} min" if age_minutes < 120 else f"{age_minutes / 60:.1f} h"
    if age_minutes <= 15:
        label = "fresh" if language == "en" else "fresca"
    elif age_minutes <= 60:
        label = "aging" if language == "en" else "envejeciendo"
    else:
        label = "stale" if language == "en" else "vieja"
    return f"{label} {age_text}"


def _news_timestamp_needs_refresh(timestamp: str) -> bool:
    parsed = _parse_iso_datetime(timestamp)
    if parsed is None:
        return True
    age_minutes = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60)
    return age_minutes > 60


def _keyword_hits(text: str, terms: Iterable[str]) -> list[str]:
    normalized = f" {str(text or '').lower()} "
    hits = []
    for term in terms:
        clean = _safe_text(term).lower()
        if not clean:
            continue
        if " " in clean:
            matched = clean in normalized
        else:
            matched = re.search(rf"\b{re.escape(clean)}\b", normalized) is not None
        if matched and clean not in hits:
            hits.append(clean)
    return hits


def _news_sentiment(headline: str) -> tuple[str, list[str]]:
    bullish_terms = (
        "beat",
        "beats",
        "upgrade",
        "approval",
        "approved",
        "deal",
        "partnership",
        "acquisition",
        "record revenue",
        "rate cut",
        "lower inflation",
        "surge",
        "rally",
        "guidance raised",
        "supera",
        "mejora",
        "aprobacion",
        "aprobado",
        "acuerdo",
        "alianza",
        "adquisicion",
        "ingresos record",
        "recorte de tasas",
        "baja inflacion",
        "sube tras",
        "repunte",
    )
    bearish_terms = (
        "miss",
        "misses",
        "lawsuit",
        "investigation",
        "cut",
        "downgrade",
        "inflation",
        "rate hike",
        "war",
        "hack",
        "bankruptcy",
        "recall",
        "guidance cut",
        "weak",
        "falls",
        "drops",
        "demanda",
        "investigacion",
        "recorte",
        "inflacion",
        "subida de tasas",
        "guerra",
        "hackeo",
        "bancarrota",
        "retiro",
        "debil",
        "cae",
        "baja por",
    )
    bullish_hits = _keyword_hits(headline, bullish_terms)
    bearish_hits = _keyword_hits(headline, bearish_terms)
    if len(bullish_hits) > len(bearish_hits):
        return "bullish", bullish_hits[:4]
    if len(bearish_hits) > len(bullish_hits):
        return "bearish", bearish_hits[:4]
    return "neutral", (bullish_hits + bearish_hits)[:4]


def _last_turn_intent(recent_turns: list[dict[str, Any]]) -> str:
    ignored = {"", "fallback", "followup", "idle", "greeting", "autonomy_status"}
    for turn in reversed(recent_turns):
        intent = _safe_text(turn.get("intent"))
        if intent not in ignored:
            return intent
    return ""


def _last_symbol_from_turns(recent_turns: list[dict[str, Any]]) -> str | None:
    for turn in reversed(recent_turns):
        if _safe_text(turn.get("intent")) not in SYMBOL_INFERENCE_INTENTS:
            continue
        for key in ("query", "reply"):
            symbol = _extract_symbol(_safe_text(turn.get(key)))
            if symbol:
                return symbol
    return None


def _active_conversation_context(recent_turns: list[dict[str, Any]]) -> dict[str, Any]:
    if not recent_turns:
        return {
            "active_intent": "",
            "active_symbol": "",
            "active_topic": "",
            "last_safety_level": "",
            "needs_confirmation": False,
            "next_best_actions": ["ask_latest_opportunity", "ask_market_summary"],
        }

    last_turn = recent_turns[-1] if isinstance(recent_turns[-1], dict) else {}
    active_intent = _last_turn_intent(recent_turns) or _safe_text(last_turn.get("intent"))
    active_symbol = ""
    for turn in reversed(recent_turns):
        if _safe_text(turn.get("intent")) not in SYMBOL_INFERENCE_INTENTS:
            continue
        active_symbol = _safe_text(turn.get("active_symbol")).upper()
        if active_symbol:
            break
    if not active_symbol:
        active_symbol = _last_symbol_from_turns(recent_turns) or ""
    active_market = ""
    active_timeframe = ""
    action_url = ""
    action_label = ""
    action_kind = ""
    for turn in reversed(recent_turns):
        active_market = _safe_text(turn.get("active_market"))
        active_timeframe = _safe_text(turn.get("active_timeframe"))
        action_url = _safe_text(turn.get("action_url"))
        action_label = _safe_text(turn.get("action_label"))
        action_kind = _safe_text(turn.get("action_kind"))
        if active_market or active_timeframe or action_url or action_label or action_kind:
            break
    active_topic = ""
    for turn in reversed(recent_turns):
        query = _redact_sensitive_text(_safe_text(turn.get("query")))[:120]
        if query:
            active_topic = query
            break
    last_safety_level = _safe_text(last_turn.get("safety_level"))
    needs_confirmation = last_safety_level == "critical" or active_intent == "action_confirmation_required"
    return {
        "active_intent": active_intent,
        "active_symbol": active_symbol,
        "active_market": active_market,
        "active_timeframe": active_timeframe,
        "action_url": action_url,
        "action_label": action_label,
        "action_kind": action_kind,
        "active_topic": active_topic,
        "last_safety_level": last_safety_level,
        "needs_confirmation": needs_confirmation,
        "next_best_actions": _next_best_actions_for_context(active_intent, last_safety_level, bool(active_symbol)),
    }


def _next_best_actions_for_context(intent: str, safety_level: str, has_symbol: bool) -> list[str]:
    if safety_level == "critical" or intent == "action_confirmation_required":
        return ["show_risk_check", "show_trade_ticket", "require_explicit_confirmation"]
    if intent == "catch_up":
        actions = ["trade_readiness", "monitoring_plan", "session_recap"]
        if has_symbol:
            actions.append("position_size")
        return actions
    if intent in {
        "opportunity",
        "opportunity_reason",
        "opportunity_risk",
        "technical_indicators",
        "support_resistance",
        "trading_dashboard_handoff",
        "trade_readiness",
        "pre_trade_preflight",
        "trade_ticket",
    }:
        actions = ["trade_readiness", "monitoring_plan", "position_size"]
        if has_symbol:
            actions.append("alert_draft")
        return actions
    if intent in {"market_summary", "data_freshness", "market_session"}:
        return ["ask_latest_opportunity", "compare_opportunities", "data_freshness", "market_session"]
    if intent in {"watchlist", "monitoring_plan"}:
        return ["monitoring_plan", "market_summary", "alert_draft"]
    if intent in {"knowledge", "knowledge_sources"}:
        return ["read_knowledge_source", "ask_capabilities", "session_recap"]
    if intent == "session_recap":
        return ["trade_readiness", "monitoring_plan", "session_recap"]
    return ["ask_latest_opportunity", "ask_market_summary", "session_recap"]


def _is_contextual_followup_query(query: str) -> bool:
    normalized = str(query or "").lower().strip()
    if not normalized:
        return False
    tokens = re.findall(r"[a-záéíóúñ]+", normalized)
    if len(tokens) > 8:
        return False
    followup_terms = {
        "continua",
        "continue",
        "sigue",
        "more",
        "mas",
        "más",
        "detalle",
        "detalles",
        "details",
        "plan",
        "why",
        "porque",
        "por que",
        "por qué",
        "motivo",
        "razon",
        "razón",
        "reason",
        "falta",
        "missing",
        "next",
        "siguiente",
    }
    return any(term in normalized for term in followup_terms)


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
        "GOOGLE": "GOOGL",
        "ALPHABET": "GOOGL",
        "GOOG": "GOOGL",
        "GOOGL": "GOOGL",
        "MICROSOFT": "MSFT",
        "META": "META",
        "BITCOIN": "BTC/USD",
        "BTC": "BTC/USD",
        "ETHEREUM": "ETH/USD",
        "ETH": "ETH/USD",
        "SOLANA": "SOL/USD",
        "SOL": "SOL/USD",
        "DOGECOIN": "DOGE/USD",
        "DOGE": "DOGE/USD",
        "SPY": "SPY",
        "QQQ": "QQQ",
    }
    ignored = {
        "ROXY",
        "DIME",
        "DAME",
        "QUE",
        "COMO",
        "DE",
        "POR",
        "PARA",
        "CON",
        "ES",
        "SI",
        "SIN",
        "UNA",
        "LAS",
        "LOS",
        "DEL",
        "EL",
        "LA",
        "Y",
        "HOY",
        "RIESGO",
        "RISK",
        "EXPLAIN",
        "READ",
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
        "THE",
        "ABRE",
        "ABRIR",
        "OPEN",
        "PAGE",
        "PAGINA",
        "PÁGINA",
        "PANTALLA",
        "TERMINAL",
        "DASHBOARD",
        "DESK",
        "TRADING",
        "LOCAL",
        "LINK",
        "URL",
        "IS",
        "IT",
        "AND",
        "TO",
        "OF",
        "FOR",
        "WITH",
        "IN",
        "ON",
        "AT",
        "AS",
        "BY",
        "OR",
        "IF",
        "FROM",
        "THIS",
        "THAT",
        "THEN",
        "THAN",
        "ARE",
        "BE",
        "HAS",
        "HAVE",
        "ACCOUNT",
        "GIVE",
        "ME",
        "PLAN",
        "SIZE",
        "SIZING",
        "POSITION",
        "POSICION",
        "POSICIÓN",
        "TAMANO",
        "TAMAÑO",
        "CAPITAL",
        "CUENTA",
        "SALDO",
        "EQUITY",
        "BALANCE",
        "ACCIONES",
        "SHARES",
        "QTY",
        "CANTIDAD",
        "CHECKLIST",
        "TICKET",
        "VALIDA",
        "VALIDAR",
        "LISTO",
        "READY",
        "ACTIVE",
        "ACTIVA",
        "VOICE",
        "VOZ",
        "CONTEXT",
        "CONTEXTO",
        "MEMORY",
        "MEMORIA",
        "CONFIRMACION",
        "CONFIRMATION",
        "WATCHLIST",
        "LISTA",
        "VIGILA",
        "MONITOREA",
        "MONITOR",
        "MI",
        "MY",
        "ACTION",
        "DECISION",
        "BUY",
        "COMPRA",
        "COMPRAR",
        "SELL",
        "VENDE",
        "VENDER",
        "TRADE",
        "AHORA",
        "TOP",
        "BEST",
        "COMPARE",
        "COMPARA",
        "COMPARAR",
        "OPPORTUNITIES",
        "OPORTUNIDADES",
        "MEJORES",
        "RANKING",
        "RANK",
        "WATCH",
        "MONITORING",
        "INDICATOR",
        "INDICATORS",
        "INDICADOR",
        "INDICADORES",
        "TECHNICAL",
        "TECNICO",
        "TÉCNICO",
        "EMA",
        "RSI",
        "MACD",
        "VWAP",
        "BOLLINGER",
        "VOLUME",
        "VOLUMEN",
        "MOVING",
        "AVERAGES",
        "MEDIAS",
        "MOVILES",
        "MÓVILES",
        "LEVEL",
        "LEVELS",
        "KEY",
        "KEYS",
        "PRICE",
        "NIVEL",
        "NIVELES",
        "SUPPORT",
        "RESISTANCE",
        "SOPORTE",
        "RESISTENCIA",
        "MONITOREO",
        "SEGUIMIENTO",
        "VIGILAR",
        "VIGILO",
        "TRACK",
        "OBSERVAR",
        "OBSERVE",
        "ALERTA",
        "ALERT",
        "PREPARA",
        "PREPARAR",
        "NOTIFY",
        "NOTIFICATION",
        "AVISAME",
        "AVÍSAME",
        "CUANDO",
        "WHEN",
        "SET",
        "CREATE",
        "CREA",
        "CREAR",
        "DRAFT",
        "DATA",
        "DATOS",
        "FRESH",
        "FRESHNESS",
        "SOURCE",
        "FUENTE",
        "UPDATED",
        "ACTUALIZADO",
        "ACTUALIZASTE",
        "TIMESTAMP",
        "SHOULD",
        "SAFE",
        "GO",
        "NO",
        "DEBO",
        "PUEDO",
        "SEGURO",
        "DECISION",
        "DECISIÓN",
        "I",
        "CAN",
        "NOW",
        "AHORA",
        "OPERAR",
        "OPERA",
        "SESSION",
        "RECAP",
        "SUMMARIZE",
        "RESUME",
        "SESION",
        "SESIÓN",
        "CONVERSACION",
        "CONVERSACIÓN",
        "DISCUSSED",
        "DISCUSS",
        "HABLAMOS",
        "MARKET",
        "MERCADO",
        "CRYPTO",
        "CRIPTO",
        "CRYPTOCURRENCY",
        "CRYPTOCURRENCIES",
        "CRIPTOMONEDAS",
        "PORTFOLIO",
        "PORTAFOLIO",
        "CASH",
        "EFECTIVO",
        "BUYING",
        "POWER",
        "POSITIONS",
        "POSICIONES",
        "EXPOSURE",
        "EXPOSICION",
        "EXPOSICIÓN",
        "CLIMA",
        "TIEMPO",
        "TEMPERATURA",
        "PRONOSTICO",
        "PRONÓSTICO",
        "WEATHER",
        "FORECAST",
        "NEWS",
        "NOTICIAS",
        "RESUMEN",
        "SUMMARY",
    }
    for raw_word in query.split():
        word = raw_word.strip(".,:;!?()[]{}\"'").upper().replace("-", "/")
        base_word = word.split("/", 1)[0]
        if word in aliases:
            return aliases[word]
        if base_word in aliases:
            return aliases[base_word]
        if "/" in word and 1 <= len(base_word) <= 6 and base_word.isalpha() and base_word not in ignored:
            return word
        if 1 <= len(word) <= 6 and word.isalpha() and word not in ignored:
            return word
    return None


def _symbols_from_query(query: str) -> list[str]:
    symbols = []
    for raw_word in str(query or "").split():
        symbol = _extract_symbol(raw_word)
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols[:12]


def _extract_weather_location(query: str, profile: dict[str, Any]) -> str:
    text = _safe_text(query)
    patterns = (
        r"(?i)\b(?:clima|tiempo|temperatura|pronostico|pronóstico|weather|forecast|temperature)\s+(?:en|de|para|in|for)\s+([A-Za-z0-9, .'-]{2,80})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            location = re.split(r"\b(?:ahora|today|hoy|please|por favor)\b", match.group(1), maxsplit=1, flags=re.I)[0]
            location = re.sub(r"[^A-Za-z0-9, .'-]+", "", location).strip(" ,.")
            if location:
                return location[:80]
    profile_location = _safe_text(profile.get("location"))
    return profile_location or weather_service.default_weather_location()


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

        q_intent = _strip_voice_preamble(q)
        lq = q_intent.lower()
        news_impact_terms = (
            "news impact",
            "headline impact",
            "impacto de noticia",
            "impacto del titular",
            "analiza noticia",
            "analiza la noticia",
            "analiza el titular",
            "analyze news",
            "news sentiment",
            "sentimiento de noticia",
            "sentimiento del titular",
        )
        watchlist_terms = (
            "watchlist",
            "lista de seguimiento",
            "mi lista",
            "mis simbolos",
            "mis símbolos",
            "my symbols",
            "vigila mi lista",
            "vigila mi watchlist",
            "monitorea mi lista",
            "monitor my list",
        )
        opportunity_compare_terms = (
            "top oportunidades",
            "compara oportunidades",
            "comparar oportunidades",
            "ranking de oportunidades",
            "ranking oportunidades",
            "mejores oportunidades",
            "top trades",
            "top opportunities",
            "compare opportunities",
            "opportunity ranking",
            "best opportunities",
        )
        monitoring_plan_terms = (
            "plan de monitoreo",
            "plan seguimiento",
            "plan de seguimiento",
            "seguimiento de oportunidad",
            "monitorea oportunidad",
            "vigilar oportunidad",
            "que debo vigilar en",
            "qué debo vigilar en",
            "que debo vigilar para",
            "qué debo vigilar para",
            "monitoring plan",
            "watch plan",
            "monitor this setup",
            "track this setup",
            "what should i monitor on",
            "what should i watch on",
        )
        alert_plan_terms = (
            "prepara alerta",
            "preparar alerta",
            "alerta preparada",
            "crear alerta",
            "crea alerta",
            "avisame cuando",
            "avísame cuando",
            "notificame cuando",
            "notifícame cuando",
            "set alert",
            "alert plan",
            "alert draft",
            "notify me when",
            "prepare alert",
            "create alert",
        )
        trading_dashboard_terms = (
            "abre roxy trade",
            "abrir roxy trade",
            "open roxy trade",
            "abre la pagina para operar",
            "abre pagina para operar",
            "abrir la pagina para operar",
            "abrir pagina para operar",
            "pagina para operar",
            "página para operar",
            "pantalla para operar",
            "terminal para operar",
            "terminal de trading",
            "dashboard para operar",
            "dashboard operativo",
            "trading dashboard",
            "trading desk",
            "open trading page",
            "open trade page",
            "open trading dashboard",
            "open the trading dashboard",
            "open the trade page",
            "open the trading desk",
        )
        data_freshness_terms = (
            "frescura de datos",
            "datos frescos",
            "estado de datos",
            "timestamp del brief",
            "cuando actualizaste",
            "cuándo actualizaste",
            "cuando se actualizo",
            "cuándo se actualizo",
            "cuando se actualizó",
            "cuándo se actualizó",
            "data freshness",
            "fresh data",
            "source status",
            "data status",
            "brief timestamp",
            "when was data updated",
            "when did you update",
        )
        knowledge_source_terms = (
            "fuentes de conocimiento",
            "fuentes locales",
            "fuentes roxy",
            "documentos roxy",
            "documentos conectados",
            "documentos locales",
            "que fuentes tienes",
            "qué fuentes tienes",
            "que documentos tienes",
            "qué documentos tienes",
            "knowledge sources",
            "approved sources",
            "source list",
            "connected documents",
            "local documents",
            "what sources do you know",
            "what documents do you know",
        )
        market_session_terms = (
            "sesion de mercado",
            "sesión de mercado",
            "horario de mercado",
            "mercado abierto",
            "mercado cerrado",
            "acciones abiertas",
            "pre market",
            "premarket",
            "after hours",
            "fuera de horario",
            "market session",
            "market hours",
            "is the market open",
            "is stock market open",
            "regular hours",
            "extended hours",
        )
        account_status_terms = (
            "estado de cuenta",
            "estado cuenta",
            "balance de cuenta",
            "equity de cuenta",
            "capital disponible",
            "poder de compra",
            "posiciones abiertas",
            "mis posiciones",
            "estado de portafolio",
            "estado portfolio",
            "riesgo de portfolio",
            "account status",
            "account balance",
            "portfolio status",
            "portfolio risk",
            "buying power",
            "cash balance",
            "open positions",
            "my positions",
            "position exposure",
        )
        pre_trade_preflight_terms = (
            "preflight",
            "pre flight",
            "pre trade",
            "pre-trade",
            "pre trade check",
            "trading preflight",
            "operational preflight",
            "chequeo pre trade",
            "chequeo pretrade",
            "chequeo antes de operar",
            "revision antes de operar",
            "revisión antes de operar",
            "revisa antes de operar",
            "estado operativo",
            "revision operativa",
            "revisión operativa",
            "before i trade",
            "before trading",
        )
        trade_readiness_terms = (
            "puedo operar",
            "debo operar",
            "operar ahora",
            "decision de trade",
            "decisión de trade",
            "decision operativa",
            "decisión operativa",
            "go no go",
            "go/no-go",
            "trade readiness",
            "should i trade",
            "can i trade",
            "is it safe to trade",
            "trade decision",
        )
        technical_indicator_terms = (
            "indicadores tecnicos",
            "indicadores técnicos",
            "indicadores",
            "indicador",
            "lectura tecnica",
            "lectura técnica",
            "medias moviles",
            "medias móviles",
            "rsi",
            "macd",
            "vwap",
            "bollinger",
            "ema",
            "technical indicators",
            "indicators",
            "indicator",
            "technical read",
            "moving averages",
            "volume read",
        )
        support_resistance_terms = (
            "soporte resistencia",
            "soporte y resistencia",
            "soporte",
            "resistencia",
            "niveles clave",
            "niveles de precio",
            "nivel clave",
            "support resistance",
            "support and resistance",
            "support",
            "resistance",
            "key levels",
            "price levels",
            "levels",
        )
        session_recap_terms = (
            "resumen de sesion",
            "resumen de sesión",
            "resumen de la sesion",
            "resumen de la sesión",
            "resume la conversacion",
            "resume la conversación",
            "resume esta conversacion",
            "resume esta conversación",
            "que hemos hablado",
            "qué hemos hablado",
            "session recap",
            "conversation recap",
            "summarize session",
            "summarize conversation",
            "what did we discuss",
        )
        catch_up_terms = (
            "ponme al dia",
            "ponme al día",
            "ponme al corriente",
            "actualizame",
            "actualízame",
            "en que vamos",
            "en qué vamos",
            "donde estamos",
            "dónde estamos",
            "que me perdi",
            "qué me perdi",
            "qué me perdí",
            "retomemos",
            "catch me up",
            "bring me up to speed",
            "where are we",
            "where did we leave off",
            "what did i miss",
            "resume where we left off",
        )
        weather_terms = (
            "clima",
            "el tiempo",
            "temperatura",
            "pronostico",
            "pronóstico",
            "weather",
            "forecast",
            "temperature",
        )
        news_summary_terms = (
            "resumen de noticias",
            "noticias breves",
            "resumen noticias",
            "brief de noticias",
            "news summary",
            "brief news",
            "short news",
            "quick news",
        )
        if _contains_any(lq, weather_terms):
            response = self._weather_reply(q_intent, profile, language)
            return finish(response)

        if _is_sports_result_query(lq):
            response = self._sports_result_reply(q_intent, language)
            return finish(response)

        if _contains_any(lq, news_summary_terms):
            response = self._news_summary_reply(language)
            return finish(response)

        if _contains_any(lq, news_impact_terms):
            response = self._news_impact_reply(q_intent, language)
            return finish(response)

        if _contains_any(lq, ("hola", "hello", "hi", "hey", "buenos dias", "buenas")):
            response = self._greeting_reply(user, profile)
            return finish(response)

        if _contains_any(lq, watchlist_terms):
            response = self._watchlist_reply(profile, q_intent, language)
            return finish(response)

        if _contains_any(lq, trading_dashboard_terms):
            response = self._trading_dashboard_handoff_reply(q_intent, language)
            return finish(response)

        if _contains_any(lq, pre_trade_preflight_terms):
            response = self._pre_trade_preflight_reply(q_intent, language)
            return finish(response)

        if _contains_any(lq, knowledge_source_terms):
            response = self._knowledge_sources_reply(language)
            return finish(response)

        if _contains_any(lq, data_freshness_terms):
            response = self._data_freshness_reply(language)
            return finish(response)

        if _contains_any(lq, market_session_terms):
            response = self._market_session_reply(language)
            return finish(response)

        if _contains_any(lq, account_status_terms):
            response = self._account_status_reply(language)
            return finish(response)

        if _contains_any(lq, technical_indicator_terms):
            response = self._technical_indicators_reply(q_intent, language=language)
            return finish(response)

        if _contains_any(lq, support_resistance_terms):
            response = self._support_resistance_reply(q_intent, language=language)
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

        if _contains_any(lq, session_recap_terms):
            response = self._session_recap_reply(recent_turns, language)
            return finish(response)

        if _contains_any(lq, catch_up_terms):
            response = self._catch_up_reply(recent_turns, language)
            return finish(response)

        if _contains_any(lq, ("quien eres", "who are you", "tu rostro", "cara", "avatar", "identidad", "identity")):
            response = self._identity_reply()
            return finish(response)

        if _is_knowledge_query(lq):
            response = self._knowledge_reply(q_intent, language=language)
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

        if _contains_any(lq, monitoring_plan_terms):
            response = self._monitoring_plan_reply(q_intent, language)
            return finish(response)

        if _contains_any(lq, alert_plan_terms):
            response = self._alert_plan_reply(q_intent, language)
            return finish(response)

        if _contains_any(lq, trade_readiness_terms):
            response = self._trade_readiness_reply(q_intent, language)
            return finish(response)

        if _contains_any(
            lq,
            (
                "briefing",
                "daily brief",
                "daily briefing",
                "morning brief",
                "market briefing",
                "que debo vigilar",
                "qué debo vigilar",
                "briefing diario",
                "resumen ejecutivo",
                "plan del dia",
                "plan del día",
            ),
        ):
            response = self._daily_briefing_reply(language)
            return finish(response)

        if _is_crypto_market_query(lq):
            response = self._market_summary_reply(language, scope="crypto")
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
                "actualizacion del mercado",
                "actualización del mercado",
                "update del mercado",
                "resumen del mercado",
                "regimen del mercado",
                "market update",
                "alcista",
                "bajista",
                "lateral",
            ),
        ):
            response = self._market_summary_reply(language)
            return finish(response)

        if _contains_any(lq, opportunity_compare_terms):
            response = self._opportunity_compare_reply(language)
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
            response = self._action_guardrail_reply(q_intent)
            return finish(response)

        if _contains_any(lq, ("noticia", "news", "titular", "mercado hoy", "actualidad")):
            response = self._news_reply(language)
            return finish(response)

        if _contains_any(
            lq,
            (
                "checklist",
                "trade checklist",
                "entry checklist",
                "validar entrada",
                "valida entrada",
                "entrada valida",
                "entrada válida",
                "esta listo",
                "está listo",
                "listo para operar",
                "ready to trade",
                "is it ready",
                "valid entry",
            ),
        ):
            response = self._entry_checklist_reply(q_intent, language=language)
            return finish(response)

        if _contains_any(
            lq,
            (
                "ticket de trade",
                "ticket de operacion",
                "ticket de operación",
                "ticket operativo",
                "trade ticket",
                "order ticket",
                "show ticket",
                "execution ticket",
                "handoff ticket",
            ),
        ):
            response = self._trade_ticket_reply(q_intent, language=language)
            return finish(response)

        if _is_knowledge_query(lq):
            response = self._knowledge_reply(q_intent, language=language)
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
                "position size",
                "position sizing",
                "size position",
                "tamano de posicion",
                "tamaño de posicion",
                "tamano posicion",
                "tamaño posicion",
                "cantidad de acciones",
                "cuantas acciones",
                "cuántas acciones",
                "cuanto comprar",
                "cuánto comprar",
                "qty",
                "shares",
                "risk budget",
            ),
        ):
            response = self._position_size_reply(q_intent, language=language)
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
            response = self._opportunity_risk_reply(q_intent, language=language)
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
                "hablame de",
                "háblame de",
                "tell me about",
                "talk to me about",
                "recomienda",
                "recommend",
                "recomendacion",
                "recommendation",
            ),
        ):
            response = self._opportunity_reply(q_intent, language=language)
            return finish(response)

        contextual = self._contextual_followup_reply(q_intent, recent_turns, language)
        if contextual:
            return finish(contextual)

        symbol = _extract_symbol(q_intent)
        if symbol:
            response = self._opportunity_reply(q_intent, language=language)
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
            active_symbol=response.active_symbol,
            active_market=response.active_market,
            active_timeframe=response.active_timeframe,
            action_url=response.action_url,
            action_label=response.action_label,
            action_kind=response.action_kind,
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
            active_symbol=response.active_symbol,
            active_market=response.active_market,
            active_timeframe=response.active_timeframe,
            action_url=response.action_url,
            action_label=response.action_label,
            action_kind=response.action_kind,
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

    def _contextual_followup_reply(
        self, query: str, recent_turns: list[dict[str, Any]], language: str
    ) -> RoxyBrainReply | None:
        if not recent_turns or not _is_contextual_followup_query(query):
            return None

        lq = query.lower()
        last_intent = _last_turn_intent(recent_turns)
        symbol = _last_symbol_from_turns(recent_turns)
        symbol_query = f"{query} {symbol}" if symbol else query
        opportunity_intents = {"opportunity", "opportunity_risk", "opportunity_reason", "support_resistance", "daily_briefing"}

        asks_reason = _contains_any(lq, ("por que", "por qué", "porque", "why", "motivo", "razon", "razón", "reason"))
        asks_missing = _contains_any(lq, ("falta", "missing", "bloquea", "blocker", "confirmacion", "confirmation"))
        asks_plan = _contains_any(lq, ("plan", "detalle", "detalles", "details", "more", "mas", "más", "continua", "continue", "sigue"))

        if last_intent in opportunity_intents and asks_reason:
            return self._opportunity_reason_reply(symbol_query, language=language)
        if last_intent in opportunity_intents and (asks_missing or asks_plan):
            return self._opportunity_risk_reply(symbol_query, language=language)
        if last_intent == "market_summary" and asks_plan:
            return self._daily_briefing_reply(language)
        if last_intent in {"news_unavailable", "news_impact_unavailable"}:
            return RoxyBrainReply(
                intent="followup",
                reply=(
                    "Sobre noticias, necesito un titular o una fuente live conectada. Pegame el titular con fuente "
                    "y hora, y te explico impacto, tono, confirmacion necesaria y riesgo."
                ),
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("paste_headline", "connect_news_source"),
            )
        if last_intent == "news_impact" and asks_plan:
            return RoxyBrainReply(
                intent="followup",
                reply=(
                    "Puedo continuar cruzando esa noticia con el resumen de mercado y una oportunidad concreta. "
                    "El titular solo no basta; necesito ver reaccion precio-volumen, tendencia y plan de riesgo."
                ),
                emotion="analytical",
                safety_level="guarded",
                suggested_actions=("ask_market_summary", "ask_latest_opportunity", "ask_risk"),
            )
        return None

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

    def _session_recap_reply(self, recent_turns: list[dict[str, Any]], language: str = "es") -> RoxyBrainReply:
        if not recent_turns:
            reply = (
                "I do not have saved turns for this session yet. Keep the same session_id while you talk with me and I can recap the thread."
                if language == "en"
                else "Todavia no tengo turnos guardados para esta sesion. Mantén el mismo session_id mientras hablas conmigo y puedo resumir el hilo."
            )
            return RoxyBrainReply(
                intent="session_recap",
                reply=reply,
                emotion="cautious",
                safety_level="guarded",
                suggested_actions=("keep_session_id", "ask_latest_opportunity"),
            )

        compact_turns = []
        for turn in recent_turns[-5:]:
            intent = _safe_text(turn.get("intent")) or "unknown"
            query = _redact_sensitive_text(_safe_text(turn.get("query")))[:90]
            compact_turns.append((intent, query))
        intent_counts: dict[str, int] = {}
        for intent, _query in compact_turns:
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        top_intents = ", ".join(f"{intent} x{count}" for intent, count in sorted(intent_counts.items(), key=lambda item: (-item[1], item[0]))[:3])
        last_intent, last_query = compact_turns[-1]
        topic_lines = []
        for idx, (intent, query) in enumerate(compact_turns, start=1):
            topic_lines.append(f"{idx}. {intent}: {query or '-'}")

        if language == "en":
            reply = (
                f"Session recap: {len(recent_turns)} saved turn(s). Main intents: {top_intents or '-'}. "
                f"Recent thread: {' | '.join(topic_lines)}. Last topic: {last_intent}. "
                "Next useful step: ask for go/no-go, monitoring plan, or position size for the active opportunity."
            )
        else:
            reply = (
                f"Resumen de sesion: {len(recent_turns)} turno(s) guardados. Intenciones principales: {top_intents or '-'}. "
                f"Hilo reciente: {' | '.join(topic_lines)}. Ultimo tema: {last_intent}. "
                "Siguiente paso util: pedir go/no-go, plan de monitoreo o sizing para la oportunidad activa."
            )
        return RoxyBrainReply(
            intent="session_recap",
            reply=reply,
            avatar_state="speaking",
            emotion="informative",
            safety_level="guarded",
            suggested_actions=("trade_readiness", "monitoring_plan", "position_size"),
        )

    def _catch_up_reply(self, recent_turns: list[dict[str, Any]], language: str = "es") -> RoxyBrainReply:
        context = _active_conversation_context(recent_turns)
        active_symbol = _safe_text(context.get("active_symbol")).upper()
        active_intent = _safe_text(context.get("active_intent")) or "-"
        active_topic = _safe_text(context.get("active_topic")) or "-"
        freshness = self._data_freshness_snapshot()
        freshness_state = _safe_text(freshness.get("state") or "missing")
        freshness_age = _safe_text(freshness.get("age_text") or "-")
        session = self._market_session_snapshot()
        top = self._latest_opportunity(active_symbol or None)
        account = self._account_snapshot_from_brief()
        needs_confirmation = bool(context.get("needs_confirmation"))

        needs_live_source = bool(freshness.get("needs_live_source")) or not bool(top)
        if freshness.get("timestamp") is None:
            needs_live_source = True

        def catch_up_actions(base_actions: tuple[str, ...]) -> tuple[str, ...]:
            if not account or "account_status" in base_actions:
                return base_actions
            return (*base_actions[:-1], "account_status", base_actions[-1]) if base_actions else ("account_status",)

        def account_text(language_code: str) -> str:
            if not account:
                return ""
            equity = account.get("equity")
            buying_power = account.get("buying_power")
            exposure = account.get("exposure")
            open_positions = int(account.get("open_positions") or 0)
            exposure_pct = None
            if _safe_float(equity) and _safe_float(exposure) is not None:
                exposure_pct = (_safe_float(exposure) or 0.0) / (_safe_float(equity) or 1.0)
            if language_code == "en":
                pct = f" ({_pct(exposure_pct)} of equity)" if exposure_pct is not None else ""
                return (
                    f" Account: equity {_money(equity)}, buying power {_money(buying_power)}, "
                    f"exposure {_money(exposure)}{pct}, open positions {open_positions}."
                )
            pct = f" ({_pct(exposure_pct)} del equity)" if exposure_pct is not None else ""
            return (
                f" Cuenta: equity {_money(equity)}, buying power {_money(buying_power)}, "
                f"exposicion {_money(exposure)}{pct}, posiciones abiertas {open_positions}."
            )

        if language == "en":
            freshness_label = {
                "fresh": "fresh",
                "usable": "usable but aging",
                "stale": "stale",
                "missing": "missing",
            }.get(freshness_state, freshness_state or "unknown")
            stock_session = _localize_market_phrase(session.get("stock_session") or "-", language) if session else "-"
            crypto_session = _localize_market_phrase(session.get("crypto_session") or "-", language) if session else "-"
            if not recent_turns and not top:
                reply = (
                    "Catch-up: I do not have saved session turns or a local opportunity snapshot yet. "
                    f"Data is {freshness_label} / {freshness_age}; session stocks {stock_session}, crypto {crypto_session}. "
                    f"{account_text('en')} "
                    "Keep the same session_id and refresh the scan so I can continue with real context instead of guessing."
                )
                actions = catch_up_actions(("keep_session_id", "run_scan", "ask_market_summary"))
            else:
                top_text = "no local top opportunity"
                if top:
                    symbol = _safe_text(top.get("symbol") or active_symbol or "-").upper()
                    action = _safe_text(top.get("signal") or top.get("ai_action") or "WATCH").upper()
                    decision = _localize_market_phrase(_safe_text(top.get("decision") or top.get("trade_decision") or "-"), language)
                    readiness = _safe_float(top.get("readiness") or top.get("ai_score") or top.get("confluence_score"))
                    readiness_text = "-" if readiness is None else f"{readiness:.1f}"
                    missing = _sentence_fragment(
                        _localize_market_phrase(
                            _safe_text(top.get("what_is_missing") or top.get("missing") or top.get("blockers")),
                            language,
                        )
                    )
                    trigger = _sentence_fragment(
                        _localize_market_phrase(
                            _safe_text(top.get("entry_trigger") or top.get("trigger") or top.get("entry_tf")),
                            language,
                        )
                    )
                    top_text = (
                        f"top setup {symbol}: {action}, decision {decision}, readiness {readiness_text}, "
                        f"entry {_price(top.get('entry'))}, stop {_price(top.get('stop'))}, risk {_pct(top.get('risk_pct'))}, "
                        f"trigger {trigger or '-'}, missing {missing or '-'}"
                    )
                guard = (
                    " The last context needs explicit confirmation, so do not advance to execution."
                    if needs_confirmation
                    else " This is continuity context only, not execution permission."
                )
                reply = (
                    f"Catch-up: {len(recent_turns)} saved turn(s). Last useful intent {active_intent}; "
                    f"last topic '{active_topic}'. Data {freshness_label} / {freshness_age}; "
                    f"session stocks {stock_session}, crypto {crypto_session}.{account_text('en')} "
                    f"Current read: {top_text}.{guard} "
                    "Next: ask for go/no-go, monitoring plan, or position size."
                )
                actions = (
                    ("show_trade_ticket", "trade_readiness", "require_explicit_confirmation")
                    if needs_confirmation
                    else catch_up_actions(("run_scan", "ask_market_summary", "session_recap"))
                    if needs_live_source
                    else catch_up_actions(("trade_readiness", "monitoring_plan", "position_size", "session_recap"))
                )
        else:
            freshness_label = {
                "fresh": "frescos",
                "usable": "usables pero envejeciendo",
                "stale": "viejos",
                "missing": "faltantes",
            }.get(freshness_state, freshness_state or "desconocidos")
            stock_session = _safe_text(session.get("stock_session") or "-") if session else "-"
            crypto_session = _safe_text(session.get("crypto_session") or "-") if session else "-"
            if not recent_turns and not top:
                reply = (
                    "Puesta al dia: no tengo turnos guardados ni snapshot local de oportunidad todavia. "
                    f"Datos {freshness_label} / {freshness_age}; sesion acciones {stock_session}, cripto {crypto_session}. "
                    f"{account_text('es')} "
                    "Mantén el mismo session_id y refresca el scan para continuar con contexto real, no con suposiciones."
                )
                actions = catch_up_actions(("keep_session_id", "run_scan", "ask_market_summary"))
            else:
                top_text = "sin top oportunidad local"
                if top:
                    symbol = _safe_text(top.get("symbol") or active_symbol or "-").upper()
                    action = _safe_text(top.get("signal") or top.get("ai_action") or "WATCH").upper()
                    decision = _safe_text(top.get("decision") or top.get("trade_decision") or "-")
                    readiness = _safe_float(top.get("readiness") or top.get("ai_score") or top.get("confluence_score"))
                    readiness_text = "-" if readiness is None else f"{readiness:.1f}"
                    missing = _sentence_fragment(_safe_text(top.get("what_is_missing") or top.get("missing") or top.get("blockers")))
                    trigger = _sentence_fragment(_safe_text(top.get("entry_trigger") or top.get("trigger") or top.get("entry_tf")))
                    top_text = (
                        f"setup principal {symbol}: {action}, decision {decision}, readiness {readiness_text}, "
                        f"entrada {_price(top.get('entry'))}, stop {_price(top.get('stop'))}, riesgo {_pct(top.get('risk_pct'))}, "
                        f"gatillo {trigger or '-'}, falta {missing or '-'}"
                    )
                guard = (
                    " El ultimo contexto requiere confirmacion explicita, asi que no avances a ejecucion."
                    if needs_confirmation
                    else " Esto es contexto de continuidad, no permiso de ejecucion."
                )
                reply = (
                    f"Puesta al dia: {len(recent_turns)} turno(s) guardados. Ultimo intent util {active_intent}; "
                    f"ultimo tema '{active_topic}'. Datos {freshness_label} / {freshness_age}; "
                    f"sesion acciones {stock_session}, cripto {crypto_session}.{account_text('es')} "
                    f"Lectura actual: {top_text}.{guard} "
                    "Siguiente: pide go/no-go, plan de monitoreo o tamano de posicion."
                )
                actions = (
                    ("show_trade_ticket", "trade_readiness", "require_explicit_confirmation")
                    if needs_confirmation
                    else catch_up_actions(("run_scan", "ask_market_summary", "session_recap"))
                    if needs_live_source
                    else catch_up_actions(("trade_readiness", "monitoring_plan", "position_size", "session_recap"))
                )

        return RoxyBrainReply(
            intent="catch_up",
            reply=reply,
            avatar_state="blocked" if needs_confirmation else "ready",
            emotion="attentive" if top else "cautious",
            needs_live_source=needs_live_source,
            safety_level="guarded",
            priority="high" if needs_confirmation or freshness_state == "stale" else "normal",
            suggested_actions=actions,
        )

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

    def _data_freshness_snapshot(self) -> dict[str, Any]:
        brief = _load_json(self.brief_path)
        plan = brief.get("daily_opportunity_plan") if isinstance(brief.get("daily_opportunity_plan"), dict) else {}
        summary = brief.get("alert_gate_summary") if isinstance(brief.get("alert_gate_summary"), dict) else {}
        candidates = (
            ("daily_opportunity_plan.generated_at", plan.get("generated_at")),
            ("brief.generated_at", brief.get("generated_at")),
            ("brief.updated_at", brief.get("updated_at")),
            ("alert_gate_summary.generated_at", summary.get("generated_at")),
        )
        timestamp: datetime | None = None
        source = ""
        for label, value in candidates:
            timestamp = _parse_iso_datetime(value)
            if timestamp is not None:
                source = label
                break

        if timestamp is None and self.brief_path.exists():
            timestamp = datetime.fromtimestamp(self.brief_path.stat().st_mtime, timezone.utc)
            source = "brief file modified_at"

        if timestamp is None:
            return {
                "state": "missing",
                "source": "",
                "timestamp": None,
                "age_minutes": None,
                "age_text": "-",
                "needs_live_source": True,
            }

        age_minutes = max(0.0, (datetime.now(timezone.utc) - timestamp).total_seconds() / 60)
        if age_minutes <= 15:
            state = "fresh"
        elif age_minutes <= 60:
            state = "usable"
        else:
            state = "stale"
        age_text = f"{age_minutes:.0f} min" if age_minutes < 120 else f"{age_minutes / 60:.1f} h"
        return {
            "state": state,
            "source": source,
            "timestamp": timestamp,
            "age_minutes": age_minutes,
            "age_text": age_text,
            "needs_live_source": state == "stale",
        }

    def _data_freshness_reply(self, language: str = "es") -> RoxyBrainReply:
        freshness = self._data_freshness_snapshot()
        if freshness["timestamp"] is None:
            reply = (
                "I do not see a local market brief timestamp yet. Run or connect a scan before treating any opportunity as current."
                if language == "en"
                else "No veo timestamp local del brief de mercado todavia. Ejecuta o conecta un scan antes de tratar cualquier oportunidad como actual."
            )
            return RoxyBrainReply(
                intent="data_freshness",
                reply=reply,
                avatar_state="waiting",
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                priority="high",
                suggested_actions=("run_scan", "ask_market_summary", "market_session"),
            )

        state = _safe_text(freshness["state"])
        source = _safe_text(freshness["source"])
        timestamp = freshness["timestamp"]
        timestamp_text = timestamp.isoformat() if isinstance(timestamp, datetime) else "-"
        age_text = _safe_text(freshness["age_text"])
        needs_live_source = bool(freshness["needs_live_source"])

        if language == "en":
            state_text = {"fresh": "fresh", "usable": "usable but aging", "stale": "stale"}[state]
            reply = (
                f"Data freshness: {state_text}. Source {source}, timestamp UTC {timestamp_text}, age {age_text}. "
                "Guardrail: if the read is stale, refresh the scan before ranking, sizing, alerts, or any trade decision."
            )
        else:
            state_text = {"fresh": "frescos", "usable": "usables pero envejeciendo", "stale": "viejos"}[state]
            reply = (
                f"Frescura de datos: {state_text}. Fuente {source}, timestamp UTC {timestamp_text}, edad {age_text}. "
                "Guardrail: si la lectura esta vieja, refresca el scan antes de rankear, calcular sizing, preparar alertas o decidir una operacion."
            )
        return RoxyBrainReply(
            intent="data_freshness",
            reply=reply,
            avatar_state="ready" if state != "stale" else "waiting",
            emotion="cautious" if state == "stale" else "informative",
            needs_live_source=needs_live_source,
            safety_level="guarded",
            priority="high" if state == "stale" else "normal",
            suggested_actions=(
                ("run_scan", "ask_market_summary", "market_session")
                if state == "stale"
                else ("ask_market_summary", "ask_latest_opportunity", "market_session")
            ),
        )

    def _watchlist_symbols(self, profile: dict[str, Any], query: str) -> list[str]:
        symbols: list[str] = []
        watchlist = profile.get("watchlist") if isinstance(profile.get("watchlist"), list) else []
        for item in watchlist:
            symbol = _safe_text(item).upper().replace("-", "/")
            if symbol and symbol not in symbols:
                symbols.append(symbol)
        default_symbol = _safe_text(profile.get("default_symbol")).upper().replace("-", "/")
        if default_symbol and default_symbol not in symbols:
            symbols.append(default_symbol)
        for symbol in _symbols_from_query(query):
            if symbol not in symbols:
                symbols.append(symbol)
        return symbols[:10]

    def _opportunity_rows(self) -> list[dict[str, Any]]:
        brief = _load_json(self.brief_path)
        plan = brief.get("daily_opportunity_plan") if isinstance(brief.get("daily_opportunity_plan"), dict) else {}
        rows = plan.get("opportunities") if isinstance(plan.get("opportunities"), list) else []
        if not rows:
            rows = brief.get("opportunities") if isinstance(brief.get("opportunities"), list) else []
        if not rows:
            rows = brief.get("crypto_scan_candidates") if isinstance(brief.get("crypto_scan_candidates"), list) else []
        return [row for row in rows if isinstance(row, dict)]

    def _watchlist_reply(self, profile: dict[str, Any], query: str, language: str = "es") -> RoxyBrainReply:
        symbols = self._watchlist_symbols(profile, query)
        if not symbols:
            if language == "en":
                reply = (
                    "I do not have a saved watchlist yet. Save symbols in the Roxy Live profile, or ask with symbols "
                    "like 'watchlist SPY QQQ NVDA', and I will monitor the local brief for each one."
                )
            else:
                reply = (
                    "Todavia no tengo una watchlist guardada. Guarda simbolos en el perfil de Roxy Live, o pregunta "
                    "con simbolos como 'watchlist SPY QQQ NVDA', y reviso el brief local para cada uno."
                )
            return RoxyBrainReply(
                intent="watchlist_summary",
                reply=reply,
                emotion="cautious",
                safety_level="guarded",
                suggested_actions=("save_profile_watchlist", "run_scan", "ask_market_summary"),
            )

        rows = self._opportunity_rows()
        matched: list[str] = []
        missing: list[str] = []
        for symbol in symbols:
            row = next((item for item in rows if _symbol_matches(item.get("symbol"), symbol)), None)
            if not row:
                missing.append(symbol)
                continue
            row_symbol = _safe_text(row.get("symbol") or symbol).upper()
            action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH")
            decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
            if language == "en":
                decision = _localize_market_phrase(decision, language)
            readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
            readiness_text = "-" if readiness is None else f"{readiness:.1f}"
            risk = _pct(row.get("risk_pct"))
            entry = _price(row.get("entry"))
            stop = _price(row.get("stop"))
            missing_text = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
            if language == "en":
                missing_text = _sentence_fragment(_localize_market_phrase(missing_text, language))
                matched.append(
                    f"{row_symbol}: {action}, decision {decision}, readiness {readiness_text}, "
                    f"entry {entry}, stop {stop}, risk {risk}, missing {missing_text or '-'}"
                )
            else:
                missing_text = _sentence_fragment(missing_text)
                matched.append(
                    f"{row_symbol}: {action}, decision {decision}, readiness {readiness_text}, "
                    f"entrada {entry}, stop {stop}, riesgo {risk}, falta {missing_text or '-'}"
                )

        if language == "en":
            lines = "; ".join(matched) if matched else "no saved symbol has a local opportunity row right now"
            missing_line = f" Missing local rows: {', '.join(missing)}." if missing else ""
            reply = (
                f"Watchlist read for {', '.join(symbols)}: {lines}.{missing_line} "
                "Guardrail: this is local monitoring only; refresh the scan before acting, and require explicit confirmation."
            )
        else:
            lines = "; ".join(matched) if matched else "ningun simbolo guardado tiene fila local de oportunidad ahora"
            missing_line = f" Sin fila local: {', '.join(missing)}." if missing else ""
            reply = (
                f"Lectura de watchlist para {', '.join(symbols)}: {lines}.{missing_line} "
                "Guardrail: esto es monitoreo local; refresca el scan antes de actuar y exige confirmacion explicita."
            )
        return RoxyBrainReply(
            intent="watchlist_summary",
            reply=reply,
            emotion="analytical" if matched else "cautious",
            needs_live_source=not bool(rows),
            safety_level="guarded",
            suggested_actions=("ask_risk", "run_scan", "save_profile_watchlist"),
        )

    def _weather_reply(self, query: str, profile: dict[str, Any], language: str = "es") -> RoxyBrainReply:
        location = _extract_weather_location(query, profile)
        snapshot = weather_service.fetch_current_weather(location)
        if snapshot.status == "missing_key":
            reply = (
                f"Weather is wired to OpenWeather, but OPENWEATHER_API_KEY is not set yet. Default location is {location}. "
                "Set the key in the local environment and ask again for live weather."
                if language == "en"
                else f"El clima ya esta conectado a OpenWeather, pero falta OPENWEATHER_API_KEY. Ubicacion base: {location}. "
                "Guarda la clave en el entorno local y vuelve a pedirme clima en vivo."
            )
            return RoxyBrainReply(
                intent="weather",
                reply=reply,
                avatar_state="waiting",
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("configure_openweather_key", "ask_market_summary"),
            )
        if snapshot.status != "ok":
            reply = (
                f"Weather source error for {location}: {snapshot.message or snapshot.status}. I will not invent current conditions."
                if language == "en"
                else f"Error de fuente de clima para {location}: {snapshot.message or snapshot.status}. No voy a inventar condiciones actuales."
            )
            return RoxyBrainReply(
                intent="weather",
                reply=reply,
                avatar_state="waiting",
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("retry_weather", "ask_market_summary"),
            )

        temp = "-" if snapshot.temperature_c is None else f"{snapshot.temperature_c:.1f} C"
        feels = "-" if snapshot.feels_like_c is None else f"{snapshot.feels_like_c:.1f} C"
        humidity = "-" if snapshot.humidity is None else f"{snapshot.humidity}%"
        wind = "-" if snapshot.wind_mps is None else f"{snapshot.wind_mps:.1f} m/s"
        observed = datetime.fromtimestamp(snapshot.observed_at, timezone.utc).isoformat() if snapshot.observed_at else "-"
        if language == "en":
            reply = (
                f"Weather for {snapshot.location}: {snapshot.description or 'conditions unavailable'}, {temp}, feels like {feels}, "
                f"humidity {humidity}, wind {wind}. Source OpenWeather, observed UTC {observed}. "
                "For trading, I use weather only as operational context, not as a market signal."
            )
        else:
            reply = (
                f"Clima en {snapshot.location}: {snapshot.description or 'condicion no disponible'}, {temp}, sensacion {feels}, "
                f"humedad {humidity}, viento {wind}. Fuente OpenWeather, observado UTC {observed}. "
                "Para trading uso el clima solo como contexto operativo, no como senal de mercado."
            )
        return RoxyBrainReply(
            intent="weather",
            reply=reply,
            avatar_state="speaking",
            emotion="informative",
            safety_level="guarded",
            suggested_actions=("ask_market_summary", "ask_latest_opportunity"),
        )

    def _sports_result_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        if language == "en":
            reply = (
                "I understand this as a live sports-result question, but no approved live sports source is connected yet. "
                "I will not invent a score. Connect a sports/news source or give me the source and timestamp, and I can read it back."
            )
        else:
            reply = (
                "Entiendo esto como una pregunta de resultado deportivo en vivo, pero todavia no tengo una fuente deportiva live aprobada. "
                "No voy a inventar el marcador. Conecta una fuente de deportes/noticias o dame fuente y hora, y lo puedo leer."
            )
        return RoxyBrainReply(
            intent="sports_result",
            reply=reply,
            avatar_state="waiting",
            emotion="cautious",
            needs_live_source=True,
            safety_level="normal",
            suggested_actions=("connect_sports_source", "ask_news_summary"),
        )

    def _brief_news_lines(self, language: str = "es", limit: int = 3) -> tuple[list[str], bool]:
        brief = _load_json(self.brief_path)
        news_items = brief.get("news") or brief.get("market_news") or []
        if not isinstance(news_items, list):
            return [], True
        lines: list[str] = []
        needs_refresh = False
        for item in news_items[: max(1, limit)]:
            title, source, timestamp = _news_item_fields(item)
            if not title:
                continue
            sentiment, cues = _news_sentiment(title)
            if timestamp and _news_timestamp_needs_refresh(timestamp):
                needs_refresh = True
            elif not timestamp:
                needs_refresh = True
            tone = {
                "bullish": "bullish" if language == "en" else "alcista",
                "bearish": "bearish" if language == "en" else "bajista",
                "neutral": "neutral",
            }[sentiment]
            details = ", ".join(_news_detail_parts(source, timestamp, language))
            cue_text = f"; cues {', '.join(cues[:2])}" if cues and language == "en" else f"; pistas {', '.join(cues[:2])}" if cues else ""
            lines.append(f"{title} ({tone}{cue_text}; {details})" if details else f"{title} ({tone}{cue_text})")
        return lines, needs_refresh

    def _news_summary_reply(self, language: str = "es") -> RoxyBrainReply:
        lines, needs_refresh = self._brief_news_lines(language=language, limit=3)
        if not lines:
            return self._news_reply(language)
        signal_text = self._signal_state_text(language=language)
        if language == "en":
            reply = (
                "Brief news summary: "
                + " ".join(f"{idx + 1}. {line}." for idx, line in enumerate(lines))
                + f" {signal_text} Guardrail: headlines are context; verify source/time and price-volume reaction before any trade."
            )
        else:
            reply = (
                "Resumen breve de noticias: "
                + " ".join(f"{idx + 1}. {line}." for idx, line in enumerate(lines))
                + f" {signal_text} Guardrail: los titulares son contexto; verifica fuente/hora y reaccion precio-volumen antes de operar."
            )
        return RoxyBrainReply(
            intent="news_summary",
            reply=reply,
            emotion="informative",
            needs_live_source=needs_refresh,
            safety_level="guarded",
            priority="high" if needs_refresh else "normal",
            suggested_actions=("ask_news_impact", "ask_market_summary", "ask_latest_opportunity"),
        )

    def _news_reply(self, language: str = "es") -> RoxyBrainReply:
        brief = _load_json(self.brief_path)
        news_items = brief.get("news") or brief.get("market_news") or []
        if isinstance(news_items, list) and news_items:
            headlines = []
            needs_refresh = False
            for item in news_items[:3]:
                title, source, timestamp = _news_item_fields(item)
                if title:
                    if not timestamp or _news_timestamp_needs_refresh(timestamp):
                        needs_refresh = True
                    details = ", ".join(_news_detail_parts(source, timestamp, language))
                    headlines.append(f"{title}" + (f" ({details})" if details else ""))
            if headlines:
                prefix = "Relevant news: " if language == "en" else "Noticias relevantes: "
                return RoxyBrainReply(
                    intent="news",
                    reply=prefix + " ".join(f"{idx + 1}. {headline}." for idx, headline in enumerate(headlines)),
                    emotion="informative",
                    needs_live_source=needs_refresh,
                    safety_level="guarded",
                    suggested_actions=("ask_news_impact", "ask_latest_opportunity", "ask_market_summary"),
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

    def _news_impact_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        brief = _load_json(self.brief_path)
        headline = _extract_headline_from_query(query)
        source = ""
        timestamp = ""
        from_local_brief = False
        if not headline:
            headline, source, timestamp = _first_news_item_from_brief(brief)
            from_local_brief = bool(headline)

        if not headline:
            if language == "en":
                return RoxyBrainReply(
                    intent="news_impact_unavailable",
                    reply=(
                        "I can analyze the impact of a specific headline, but I do not see one in the prompt or "
                        "the local brief. I will not invent live news. Paste the headline with its source and time, "
                        "or connect a news feed, and I will explain sentiment, likely market impact, and risk checks."
                    ),
                    emotion="cautious",
                    needs_live_source=True,
                    safety_level="guarded",
                    suggested_actions=("paste_headline", "connect_news_source", "ask_market_summary"),
                )
            return RoxyBrainReply(
                intent="news_impact_unavailable",
                reply=(
                    "Puedo analizar el impacto de un titular especifico, pero no veo uno en el mensaje ni en el "
                    "brief local. No voy a inventar noticias live. Pegame el titular con fuente y hora, o conecta "
                    "un feed de noticias, y explico sentimiento, impacto probable y controles de riesgo."
                ),
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("paste_headline", "connect_news_source", "ask_market_summary"),
            )

        sentiment, cues = _news_sentiment(headline)
        symbol = _extract_symbol(headline) or _extract_symbol(query)
        source_text = f" Source: {source}." if source and language == "en" else f" Fuente: {source}." if source else ""
        if timestamp:
            freshness_text = _news_timestamp_freshness(timestamp, language)
            if language == "en":
                time_text = f" Time: {timestamp}" + (f" ({freshness_text})." if freshness_text else ".")
            else:
                time_text = f" Hora: {timestamp}" + (f" ({freshness_text})." if freshness_text else ".")
        elif from_local_brief:
            time_text = " Time: missing from local brief." if language == "en" else " Hora: no disponible en el brief local."
        else:
            time_text = ""
        cue_text = ", ".join(cues) if cues else ("no strong keyword cue" if language == "en" else "sin palabra clave fuerte")
        opportunity_context = self._news_opportunity_context(symbol, sentiment, language)
        stale_local_news = bool(from_local_brief and timestamp and _news_timestamp_needs_refresh(timestamp))

        if language == "en":
            sentiment_label = {"bullish": "bullish", "bearish": "bearish", "neutral": "neutral"}[sentiment]
            if sentiment == "bullish":
                impact = "likely positive for risk appetite, but only if price and volume confirm instead of fading the move"
            elif sentiment == "bearish":
                impact = "likely defensive or volatile; protect downside first and avoid chasing before confirmation"
            else:
                impact = "unclear by itself; the market reaction, volume, and related sector move matter more than the words"
            asset = f" for {symbol}" if symbol else ""
            reply = (
                f"News impact{asset}: '{headline}'.{source_text}{time_text} Tone: {sentiment_label}; cues: {cue_text}. "
                f"Likely impact: {impact}.{opportunity_context} Verify source, timestamp, whether the headline is confirmed, and the first "
                "price-volume reaction. This is not a trade signal by itself; I would pair it with the market summary, "
                "entry trigger, stop, and position risk before recommending action."
            )
        else:
            sentiment_label = {"bullish": "alcista", "bearish": "bajista", "neutral": "neutral"}[sentiment]
            if sentiment == "bullish":
                impact = (
                    "puede favorecer apetito por riesgo, pero solo si precio y volumen confirman y el movimiento no se revierte"
                )
            elif sentiment == "bearish":
                impact = "puede activar defensa o volatilidad; primero protege downside y evita perseguir sin confirmacion"
            else:
                impact = (
                    "no es claro por si solo; pesa mas la reaccion del precio, volumen y sector que las palabras del titular"
                )
            asset = f" para {symbol}" if symbol else ""
            reply = (
                f"Impacto de noticia{asset}: '{headline}'.{source_text}{time_text} Tono: {sentiment_label}; pistas: {cue_text}. "
                f"Impacto probable: {impact}.{opportunity_context} Verifica fuente, hora, si el titular esta confirmado y la primera reaccion "
                "precio-volumen. Esto no es una senal de trade por si solo; lo cruzaria con resumen de mercado, gatillo "
                "de entrada, stop y riesgo de posicion antes de recomendar accion."
            )

        actions = ("entry_checklist", "ask_market_summary", "ask_latest_opportunity", "paste_source") if opportunity_context else (
            "ask_market_summary",
            "ask_latest_opportunity",
            "paste_source",
        )
        if from_local_brief and not timestamp:
            actions = ("verify_news_timestamp", *actions)
        elif stale_local_news:
            actions = ("refresh_news_source", "verify_news_timestamp", *actions)
        return RoxyBrainReply(
            intent="news_impact",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if stale_local_news else "normal",
            suggested_actions=actions,
        )

    def _news_opportunity_context(self, symbol: str | None, sentiment: str, language: str = "es") -> str:
        if not symbol:
            return ""
        row = self._latest_opportunity(symbol)
        if not row:
            return ""

        symbol_text = _safe_text(row.get("symbol") or symbol).upper()
        action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH").upper()
        decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
        entry = _price(row.get("entry"))
        stop = _price(row.get("stop"))
        risk = _pct(row.get("risk_pct"))
        missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))

        bullish_alignment = sentiment == "bullish" and action in {"BUY", "ALERT", "READY", "WATCH"}
        bearish_alignment = sentiment == "bearish" and action in {"SELL", "SHORT", "AVOID", "WAIT"}
        aligned = bullish_alignment or bearish_alignment
        has_trade_frame = entry != "-" and stop != "-" and risk != "-"

        if language == "en":
            missing_text = f" Missing: {missing}." if missing else " Missing: none listed."
            frame_text = f" entry {entry}, stop {stop}, risk {risk}" if has_trade_frame else " incomplete entry/stop/risk"
            read = (
                "headline can support the local watch bias, but it remains blocked until price-volume and trigger confirm"
                if aligned
                else "headline does not confirm the local setup by itself; treat it as context until the chart agrees"
            )
            return (
                f" Local setup context for {symbol_text}: Roxy has {action} / {decision},{frame_text}."
                f"{missing_text} Read: {read}."
            )

        missing_text = f" Falta: {missing}." if missing else " Falta: nada listado."
        frame_text = f" entrada {entry}, stop {stop}, riesgo {risk}" if has_trade_frame else " entrada/stop/riesgo incompletos"
        read = (
            "el titular puede apoyar el sesgo de vigilancia local, pero sigue bloqueado hasta que precio-volumen y gatillo confirmen"
            if aligned
            else "el titular no confirma el setup local por si solo; tratalo como contexto hasta que la grafica confirme"
        )
        return (
            f" Contexto local {symbol_text}: Roxy tiene {action} / {decision},{frame_text}."
            f"{missing_text} Lectura: {read}."
        )

    def _signal_state_text(
        self, language: str = "es", symbol: str | None = None, rows_override: list[dict[str, Any]] | None = None
    ) -> str:
        rows = self._ranked_opportunities(rows_override if rows_override is not None else self._opportunity_rows())
        if symbol:
            rows = [row for row in rows if _symbol_matches(row.get("symbol"), symbol)]
        freshness = self._data_freshness_snapshot()
        freshness_state = _safe_text(freshness.get("state") or "missing")
        freshness_age = _safe_text(freshness.get("age_text") or "-")
        if not rows:
            return (
                f"Live signals: no local rows; data {freshness_state}/{freshness_age}."
                if language == "en"
                else f"Senales live: sin filas locales; datos {freshness_state}/{freshness_age}."
            )
        top = rows[0]
        symbol_text = _safe_text(top.get("symbol") or symbol or "-").upper()
        action = _safe_text(top.get("signal") or top.get("ai_action") or "WATCH").upper()
        decision = _safe_text(top.get("decision") or top.get("trade_decision") or "-")
        readiness = _safe_float(top.get("readiness") or top.get("ai_score") or top.get("confluence_score"))
        readiness_text = "-" if readiness is None else f"{readiness:.1f}"
        missing = _sentence_fragment(_safe_text(top.get("what_is_missing") or top.get("missing") or top.get("blockers")))
        actionable = sum(
            1
            for row in rows
            if _safe_text(row.get("signal") or row.get("ai_action")).upper() in {"ALERT", "BUY", "SELL", "READY"}
        )
        if language == "en":
            decision = _localize_market_phrase(decision, language)
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            stale = " Refresh before acting." if freshness.get("needs_live_source") else ""
            return (
                f"Live signals: {len(rows)} row(s), {actionable} actionable; top {symbol_text} {action}/{decision}, "
                f"readiness {readiness_text}, entry {_price(top.get('entry'))}, stop {_price(top.get('stop'))}, "
                f"risk {_pct(top.get('risk_pct'))}, missing {missing or 'none'}, data {freshness_state}/{freshness_age}.{stale}"
            )
        stale = " Refresca antes de actuar." if freshness.get("needs_live_source") else ""
        return (
            f"Senales live: {len(rows)} fila(s), {actionable} accionable(s); top {symbol_text} {action}/{decision}, "
            f"readiness {readiness_text}, entrada {_price(top.get('entry'))}, stop {_price(top.get('stop'))}, "
            f"riesgo {_pct(top.get('risk_pct'))}, falta {missing or 'ninguna'}, datos {freshness_state}/{freshness_age}.{stale}"
        )

    def _market_summary_reply(self, language: str = "es", scope: str = "all") -> RoxyBrainReply:
        brief = _load_json(self.brief_path)
        gate = brief.get("alert_gate_summary") if isinstance(brief.get("alert_gate_summary"), dict) else {}
        plan = brief.get("daily_opportunity_plan") if isinstance(brief.get("daily_opportunity_plan"), dict) else {}
        scope = scope if scope in {"all", "crypto"} else "all"
        plan_rows = plan.get("opportunities") if isinstance(plan.get("opportunities"), list) else []
        brief_rows = brief.get("opportunities") if isinstance(brief.get("opportunities"), list) else []
        crypto_rows = brief.get("crypto_scan_candidates") if isinstance(brief.get("crypto_scan_candidates"), list) else []
        if scope == "crypto":
            rows = [row for row in [*plan_rows, *brief_rows, *crypto_rows] if isinstance(row, dict) and _row_is_crypto(row)]
            gate = {}
        else:
            rows = plan_rows or brief_rows or crypto_rows

        if not rows and not gate:
            if language == "en" and scope == "crypto":
                reply = (
                    "I do not have a local crypto market snapshot yet. Refresh the crypto scan before relying on a "
                    "crypto trend read."
                )
            elif language == "en":
                reply = (
                    "I do not have enough local market data to classify the regime yet. Connect or refresh the scan "
                    "before relying on a trend read."
                )
            elif scope == "crypto":
                reply = (
                    "Todavia no tengo un snapshot local de mercado cripto. Refresca el escaneo cripto antes de usar "
                    "una lectura de tendencia cripto."
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
        readiness_values = [
            value
            for value in (
                _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
                for row in rows
                if isinstance(row, dict)
            )
            if value is not None
        ]
        ready_ratio = _safe_float(gate.get("ready_ratio"))
        if ready_ratio is None and scope == "crypto" and readiness_values:
            ready_ratio = sum(1 for value in readiness_values if value >= 70) / len(readiness_values)
        top_gate = _localize_market_phrase(gate.get("top_gate_label") or gate.get("top_gate") or "-", language)
        top_readiness = _safe_float(gate.get("top_readiness"))
        if top_readiness is None and scope == "crypto" and readiness_values:
            top_readiness = max(readiness_values)
        if scope == "crypto" and top_gate == "-":
            top_gate = "crypto scan"
        market_counts = plan.get("market_counts") if isinstance(plan.get("market_counts"), dict) else {}
        if scope == "crypto":
            markets = f"crypto:{len(rows)}"
        else:
            markets = ", ".join(f"{key}:{value}" for key, value in sorted(market_counts.items())) if market_counts else "-"
        session = plan.get("market_session") if isinstance(plan.get("market_session"), dict) else {}
        stock_session = _safe_text(session.get("stock_session") or "-")
        crypto_session = _safe_text(session.get("crypto_session") or "-")
        freshness = self._data_freshness_snapshot()
        freshness_state = _safe_text(freshness.get("state") or "")
        freshness_age = _safe_text(freshness.get("age_text") or "-")
        stale_market_read = bool(freshness.get("needs_live_source"))
        signal_state = self._signal_state_text(language=language, rows_override=[row for row in rows if isinstance(row, dict)])

        if language == "en":
            condition_text = {
                "bullish": "bullish watch",
                "bearish": "bearish watch",
                "sideways": "sideways/wait",
                "unknown": "unclear/wait",
            }[condition]
            ready_text = "-" if ready_ratio is None else f"{ready_ratio * 100:.1f}%"
            top_readiness_text = "-" if top_readiness is None else f"{top_readiness:.1f}"
            prefix = "Local crypto regime" if scope == "crypto" else "Local market regime"
            session_text = (
                f"Crypto session: {crypto_session}. "
                if scope == "crypto"
                else f"Stock session: {stock_session}; crypto session: {crypto_session}. "
            )
            freshness_guard = (
                f"Data guardrail: local scan is {freshness_state} / {freshness_age}; refresh before treating this regime as current. "
                if stale_market_read
                else ""
            )
            reply = (
                f"{prefix}: {condition_text}. I see {total} opportunity row(s), {watch_count} in watch mode, "
                f"ready ratio {ready_text}, top gate {top_gate}, top readiness {top_readiness_text}. "
                f"Markets: {markets}. {session_text}"
                f"{freshness_guard}"
                f"{signal_state} "
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
            prefix = "Regimen local cripto" if scope == "crypto" else "Regimen local del mercado"
            session_text = (
                f"Sesion cripto: {crypto_session}. "
                if scope == "crypto"
                else f"Sesion acciones: {stock_session}; cripto: {crypto_session}. "
            )
            freshness_label = {
                "fresh": "fresco",
                "usable": "usable pero envejeciendo",
                "stale": "viejo",
                "missing": "sin timestamp",
            }.get(freshness_state, freshness_state or "desconocido")
            freshness_guard = (
                f"Guardrail de datos: scan local {freshness_label} / {freshness_age}; refresca antes de tratar este regimen como actual. "
                if stale_market_read
                else ""
            )
            reply = (
                f"{prefix}: {condition_text}. Veo {total} oportunidad(es), {watch_count} en modo watch, "
                f"ready ratio {ready_text}, filtro principal {top_gate}, readiness maxima {top_readiness_text}. "
                f"Mercados: {markets}. {session_text}"
                f"{freshness_guard}"
                f"{signal_state} "
                "Nota de riesgo: esto es apoyo de decision, no garantia ni orden de ejecucion."
            )
        actions = (
            ("run_scan", "data_freshness", "ask_latest_opportunity", "market_session")
            if stale_market_read
            else ("ask_latest_opportunity", "ask_risk", "run_scan", "market_session")
        )

        return RoxyBrainReply(
            intent="market_summary",
            reply=reply,
            avatar_state="waiting" if stale_market_read else "speaking",
            emotion="cautious" if stale_market_read else "analytical",
            needs_live_source=stale_market_read,
            safety_level="guarded",
            priority="high" if stale_market_read else "normal",
            suggested_actions=actions,
        )

    def _market_session_snapshot(self) -> dict[str, Any]:
        brief = _load_json(self.brief_path)
        plan = brief.get("daily_opportunity_plan") if isinstance(brief.get("daily_opportunity_plan"), dict) else {}
        session = plan.get("market_session") if isinstance(plan.get("market_session"), dict) else {}
        if not session:
            session = brief.get("market_session") if isinstance(brief.get("market_session"), dict) else {}
        return session if isinstance(session, dict) else {}

    def _market_session_reply(self, language: str = "es") -> RoxyBrainReply:
        session = self._market_session_snapshot()
        if not session:
            if language == "en":
                reply = (
                    "I do not have a local market-session snapshot yet. Refresh the scan so Roxy can read stock hours, "
                    "extended-hours status, and crypto 24h status before making timing decisions."
                )
            else:
                reply = (
                    "Todavia no tengo una lectura local de sesion de mercado. Refresca el escaneo para que Roxy lea "
                    "horario de acciones, horario extendido y estado 24h de cripto antes de decidir tiempos."
                )
            return RoxyBrainReply(
                intent="market_session",
                reply=reply,
                avatar_state="ready",
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "data_freshness", "ask_market_summary"),
            )

        local_time = _safe_text(session.get("local_time") or "-")
        timezone_name = _safe_text(session.get("timezone") or "America/New_York")
        stock_session = _localize_market_phrase(session.get("stock_session") or "-", language)
        stock_detail = _sentence_fragment(_localize_market_phrase(session.get("stock_detail") or "-", language))
        crypto_session = _localize_market_phrase(session.get("crypto_session") or "24h", language)
        crypto_detail = _sentence_fragment(_localize_market_phrase(session.get("crypto_detail") or "", language))
        stock_alerts_allowed = bool(session.get("stock_alerts_allowed", True))

        if language == "en":
            alert_text = (
                "Stock/options alerts may stay active only with liquidity and spread checks."
                if stock_alerts_allowed
                else "Stock/options alerts are paused; keep crypto on 24h watch only."
            )
            reply = (
                f"Market session: stocks {stock_session}; crypto {crypto_session}. Local time {local_time} "
                f"{timezone_name}. Stock note: {stock_detail}. Crypto note: {crypto_detail or 'watch liquidity and volatility'}. "
                f"{alert_text} Guardrail: session status is timing context, not permission to execute."
            )
        else:
            alert_text = (
                "Alertas de acciones/opciones pueden seguir activas solo con chequeo de liquidez y spreads."
                if stock_alerts_allowed
                else "Alertas de acciones/opciones pausadas; mantener solo vigilancia cripto 24h."
            )
            reply = (
                f"Sesion de mercado: acciones {stock_session}; cripto {crypto_session}. Hora local {local_time} "
                f"{timezone_name}. Nota acciones: {stock_detail}. Nota cripto: {crypto_detail or 'vigilar liquidez y volatilidad'}. "
                f"{alert_text} Guardrail: el estado de sesion es contexto de tiempo, no permiso para ejecutar."
            )

        return RoxyBrainReply(
            intent="market_session",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            suggested_actions=("data_freshness", "ask_market_summary", "ask_latest_opportunity"),
        )

    def _pre_trade_preflight_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        freshness = self._data_freshness_snapshot()
        session = self._market_session_snapshot()
        account = self._account_snapshot_from_brief()
        row = self._latest_opportunity(symbol)
        row_is_crypto = bool(row and _row_is_crypto(row))

        blockers: list[str] = []
        waits: list[str] = []
        freshness_state = _safe_text(freshness.get("state") or "missing")
        freshness_age = _safe_text(freshness.get("age_text") or "-")
        if freshness.get("timestamp") is None or freshness_state == "missing":
            blockers.append("data_snapshot")
        elif freshness_state == "stale":
            blockers.append("fresh_data")
        elif freshness_state == "usable":
            waits.append("aging_data")

        if not session:
            blockers.append("market_session")
        else:
            stock_alerts_allowed = bool(session.get("stock_alerts_allowed", True))
            if not stock_alerts_allowed and not row_is_crypto:
                waits.append("stock_session")

        if not account:
            blockers.append("account_snapshot")

        setup_status = "blocked"
        action = "-"
        decision = "-"
        entry = stop = risk_pct = readiness = None
        missing = trigger = reason = ""
        if not row:
            blockers.append("opportunity")
            symbol_text = _safe_text(symbol or "top setup").upper()
        else:
            symbol_text = _safe_text(row.get("symbol") or symbol or "top setup").upper()
            action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH").upper()
            decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
            entry = _safe_float(row.get("entry"))
            stop = _safe_float(row.get("stop"))
            risk_pct = _safe_float(row.get("risk_pct"))
            readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
            missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
            trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
            reason = _safe_text(row.get("why") or row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))
            combined_text = " ".join([action, decision, missing, trigger, reason]).lower()
            if entry is None or entry <= 0:
                blockers.append("entry")
            if stop is None or stop <= 0:
                blockers.append("stop")
            if risk_pct is None or risk_pct <= 0:
                blockers.append("risk")
            if missing:
                waits.append("confirmations")
            explicit_wait = any(term in combined_text for term in ("wait", "esperar", "no operar", "missing", "falta"))
            explicit_ready = action in {"ALERT", "BUY", "SELL", "READY"} or "trade" in combined_text or "operar" in combined_text
            readiness_ok = readiness is None or readiness >= 70
            if explicit_wait or not readiness_ok or not explicit_ready:
                waits.append("setup_not_ready")

        if blockers:
            setup_status = "blocked"
        elif waits:
            setup_status = "wait"
        else:
            setup_status = "prepare"

        def labels(values: list[str]) -> str:
            unique = []
            for value in values:
                if value not in unique:
                    unique.append(value)
            if language == "en":
                mapping = {
                    "data_snapshot": "data snapshot",
                    "fresh_data": "fresh data",
                    "aging_data": "aging data",
                    "market_session": "market session",
                    "stock_session": "stock timing",
                    "account_snapshot": "account snapshot",
                    "opportunity": "local opportunity",
                    "entry": "entry",
                    "stop": "stop",
                    "risk": "risk",
                    "confirmations": "confirmations",
                    "setup_not_ready": "setup not ready",
                }
                return ", ".join(mapping.get(item, item) for item in unique) if unique else "none"
            mapping = {
                "data_snapshot": "snapshot de datos",
                "fresh_data": "datos frescos",
                "aging_data": "datos envejeciendo",
                "market_session": "sesion de mercado",
                "stock_session": "timing acciones",
                "account_snapshot": "snapshot de cuenta",
                "opportunity": "oportunidad local",
                "entry": "entrada",
                "stop": "stop",
                "risk": "riesgo",
                "confirmations": "confirmaciones",
                "setup_not_ready": "setup no listo",
            }
            return ", ".join(mapping.get(item, item) for item in unique) if unique else "ninguno"

        stock_session = _safe_text(session.get("stock_session") or "-") if session else "-"
        crypto_session = _safe_text(session.get("crypto_session") or "-") if session else "-"
        if language == "en":
            freshness_label = {
                "fresh": "fresh",
                "usable": "usable but aging",
                "stale": "stale",
                "missing": "missing",
            }.get(freshness_state, freshness_state or "unknown")
            stock_session = _localize_market_phrase(stock_session, language)
            crypto_session = _localize_market_phrase(crypto_session, language)
            decision = _localize_market_phrase(decision, language)
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            trigger = _sentence_fragment(_localize_market_phrase(trigger, language))
            reason = _sentence_fragment(_localize_market_phrase(reason, language))
            status_label = {"blocked": "BLOCKED", "wait": "WAIT", "prepare": "PREPARE ONLY"}[setup_status]
            account_text = (
                f"account equity {_money(account.get('equity'))}, buying power {_money(account.get('buying_power'))}"
                if account
                else "account snapshot missing"
            )
            reply = (
                f"Operational preflight {symbol_text}: {status_label}. Data {freshness_label} / {freshness_age}; "
                f"session stocks {stock_session}, crypto {crypto_session}; {account_text}. "
                f"Setup {action}, decision {decision}, entry {_money(entry)}, stop {_money(stop)}, risk {_pct(risk_pct)}, "
                f"readiness {'-' if readiness is None else f'{readiness:.1f}'}. "
                f"Blockers: {labels(blockers)}. Pending: {labels(waits)}. "
                f"Trigger: {trigger or '-'}. Context: {reason or missing or '-'}. "
                "Next: refresh blocked data, then run checklist and sizing; voice preflight is not execution permission."
            )
        else:
            freshness_label = {
                "fresh": "frescos",
                "usable": "usables pero envejeciendo",
                "stale": "viejos",
                "missing": "faltantes",
            }.get(freshness_state, freshness_state or "desconocidos")
            missing = _sentence_fragment(missing)
            trigger = _sentence_fragment(trigger)
            reason = _sentence_fragment(reason)
            status_label = {"blocked": "BLOQUEADO", "wait": "ESPERAR", "prepare": "PREPARAR SOLO"}[setup_status]
            account_text = (
                f"cuenta equity {_money(account.get('equity'))}, buying power {_money(account.get('buying_power'))}"
                if account
                else "snapshot de cuenta faltante"
            )
            reply = (
                f"Preflight operativo {symbol_text}: {status_label}. Datos {freshness_label} / {freshness_age}; "
                f"sesion acciones {stock_session}, cripto {crypto_session}; {account_text}. "
                f"Setup {action}, decision {decision}, entrada {_money(entry)}, stop {_money(stop)}, riesgo {_pct(risk_pct)}, "
                f"readiness {'-' if readiness is None else f'{readiness:.1f}'}. "
                f"Bloqueos: {labels(blockers)}. Pendiente: {labels(waits)}. "
                f"Gatillo: {trigger or '-'}. Contexto: {reason or missing or '-'}. "
                "Siguiente: refrescar datos bloqueados, luego checklist y sizing; el preflight por voz no es permiso de ejecucion."
            )

        needs_live_source = bool(blockers)
        actions = (
            ("run_scan", "data_freshness", "market_session", "account_status")
            if blockers
            else ("entry_checklist", "position_size", "confirm_before_execution")
            if setup_status == "prepare"
            else ("monitoring_plan", "ask_market_summary", "set_alert")
        )
        return RoxyBrainReply(
            intent="pre_trade_preflight",
            reply=reply,
            avatar_state="blocked" if blockers else "speaking",
            emotion="serious" if blockers else "analytical",
            needs_live_source=needs_live_source,
            safety_level="guarded",
            priority="high" if setup_status in {"blocked", "prepare"} else "normal",
            suggested_actions=actions,
        )

    def _daily_briefing_reply(self, language: str = "es") -> RoxyBrainReply:
        brief = _load_json(self.brief_path)
        plan = brief.get("daily_opportunity_plan") if isinstance(brief.get("daily_opportunity_plan"), dict) else {}
        gate = brief.get("alert_gate_summary") if isinstance(brief.get("alert_gate_summary"), dict) else {}
        market_summary = self._market_summary_reply(language)
        top = self._latest_opportunity(None)
        generated_at = _safe_text(plan.get("generated_at") or brief.get("generated_at"))
        policy = _safe_text(plan.get("alert_policy") or "")
        session = plan.get("market_session") if isinstance(plan.get("market_session"), dict) else {}
        local_time = _safe_text(session.get("local_time") or "")
        alert_count = int(gate.get("alert_count") or brief.get("alert_count") or 0)
        if language == "en":
            policy = _sentence_fragment(_localize_market_phrase(policy, language))
        else:
            policy = _sentence_fragment(policy)

        if not top:
            if language == "en":
                reply = (
                    "Daily briefing: I do not have a ranked local opportunity yet. Refresh the scan, then ask me "
                    "for market trend or risk plan. Guardrail: no execution without confirmation."
                )
            else:
                reply = (
                    "Briefing diario: todavia no tengo una oportunidad local ordenada. Refresca el escaneo y luego "
                    "pideme tendencia del mercado o plan de riesgo. Guardrail: no ejecuto sin confirmacion."
                )
            return RoxyBrainReply(
                intent="daily_briefing",
                reply=reply,
                avatar_state="ready",
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol = _safe_text(top.get("symbol") or "-").upper()
        decision = _safe_text(top.get("decision") or top.get("trade_decision") or "-")
        if language == "en":
            decision = _localize_market_phrase(decision, language)
        entry = _price(top.get("entry"))
        stop = _price(top.get("stop"))
        risk = _pct(top.get("risk_pct"))
        readiness = _safe_float(top.get("readiness") or top.get("ai_score") or top.get("confluence_score"))
        readiness_text = "-" if readiness is None else f"{readiness:.1f}"
        missing = _safe_text(top.get("what_is_missing") or top.get("why") or "")
        if language == "en":
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            reply = (
                f"Daily briefing{f' at {local_time}' if local_time else ''}: {market_summary.reply} "
                f"Top watch: {symbol}, decision {decision}, entry {entry}, stop {stop}, risk {risk}, "
                f"readiness {readiness_text}. Missing: {missing or '-'}. Alerts ready: {alert_count}. "
                f"Policy: {policy or 'wait for full checklist confirmation'}. Generated: {generated_at or '-'}. "
                "Next: monitor the trigger, ask for the risk plan, and do not execute without explicit confirmation."
            )
        else:
            missing = _sentence_fragment(missing)
            reply = (
                f"Briefing diario{f' a las {local_time}' if local_time else ''}: {market_summary.reply} "
                f"Top watch: {symbol}, decision {decision}, entrada {entry}, stop {stop}, riesgo {risk}, "
                f"readiness {readiness_text}. Falta: {missing or '-'}. Alertas listas: {alert_count}. "
                f"Politica: {policy or 'esperar confirmacion completa del checklist'}. Generado: {generated_at or '-'}. "
                "Siguiente: vigilar el gatillo, pedir plan de riesgo y no ejecutar sin confirmacion explicita."
            )
        return RoxyBrainReply(
            intent="daily_briefing",
            reply=reply,
            avatar_state="ready",
            emotion="analytical",
            safety_level="guarded",
            priority="high" if alert_count > 0 else "normal",
            suggested_actions=("ask_market_summary", "ask_risk", "monitor_trigger"),
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

    def _knowledge_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        match = self._best_knowledge_match(query)
        if not match:
            reply = (
                "I did not find a clear local source for that question inside the Roxy universe. "
                "I can answer better when it is connected to a specific document, note, or brief."
                if language == "en"
                else (
                    "No encontre una fuente local clara para esa pregunta dentro del universo Roxy. "
                    "Puedo responder mejor si la conectamos a un documento, nota o brief especifico."
                )
            )
            return RoxyBrainReply(
                intent="knowledge",
                reply=reply,
                emotion="cautious",
                suggested_actions=("attach_document", "ask_latest_opportunity"),
            )

        path, excerpt = match
        reply = f"According to {path}: {excerpt}" if language == "en" else f"Segun {path}: {excerpt}"
        return RoxyBrainReply(
            intent="knowledge",
            reply=reply,
            emotion="informative",
            suggested_actions=("ask_followup", "open_source_document"),
        )

    def _knowledge_sources_reply(self, language: str = "es") -> RoxyBrainReply:
        sources = list_knowledge_sources(self.knowledge_paths)
        available = [source for source in sources if source.get("exists")]
        missing = [source for source in sources if not source.get("exists")]
        available_names = ", ".join(Path(_safe_text(source.get("path"))).name for source in available[:6])
        missing_names = ", ".join(Path(_safe_text(source.get("path"))).name for source in missing[:6])
        available_text = available_names or ("none" if language == "en" else "ninguna")
        missing_text = missing_names or ("none" if language == "en" else "ninguna")

        if language == "en":
            reply = (
                f"Knowledge sources: {len(available)}/{len(sources)} approved local document(s) available. "
                f"Available: {available_text}. Missing: {missing_text}. "
                "I use these local docs for Roxy-universe reads and avoid inventing content that is not connected."
            )
        else:
            reply = (
                f"Fuentes de conocimiento: {len(available)} de {len(sources)} documento(s) local(es) aprobado(s) disponibles. "
                f"Disponibles: {available_text}. Faltantes: {missing_text}. "
                "Uso estos documentos locales para lecturas del universo Roxy y evito inventar contenido que no este conectado."
            )

        return RoxyBrainReply(
            intent="knowledge_sources",
            reply=reply,
            avatar_state="ready",
            emotion="informative" if available else "cautious",
            safety_level="guarded",
            priority="high" if not available else "normal",
            suggested_actions=("read_knowledge_source", "ask_capabilities", "review_learning_status")
            if available
            else ("attach_document", "ask_capabilities", "review_learning_status"),
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

    def _opportunity_compare_reply(self, language: str = "es") -> RoxyBrainReply:
        rows = self._ranked_opportunities(self._opportunity_rows())[:3]
        if not rows:
            if language == "en":
                reply = (
                    "I do not have local opportunity rows to rank yet. Run a fresh scan or connect the market brief, "
                    "then I can compare the top setups with entry, stop, risk, and missing confirmations."
                )
            else:
                reply = (
                    "Todavia no tengo oportunidades locales para rankear. Ejecuta un scan fresco o conecta el brief de mercado, "
                    "y puedo comparar los mejores setups con entrada, stop, riesgo y confirmaciones faltantes."
                )
            return RoxyBrainReply(
                intent="opportunity_compare",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        lines: list[str] = []
        top_priority = False
        for idx, row in enumerate(rows, start=1):
            symbol = _safe_text(row.get("symbol") or "-").upper()
            action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH").upper()
            decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
            missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
            reason = _safe_text(row.get("why") or row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))
            trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
            readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
            readiness_text = "-" if readiness is None else f"{readiness:.1f}"
            if action in {"ALERT", "BUY", "SELL", "READY"}:
                top_priority = True

            if language == "en":
                decision = _localize_market_phrase(decision, language)
                missing = _sentence_fragment(_localize_market_phrase(missing, language))
                reason = _sentence_fragment(_localize_market_phrase(reason, language))
                trigger = _sentence_fragment(_localize_market_phrase(trigger, language))
                blocker = missing or "none"
                why = reason or trigger or "local ranking score"
                lines.append(
                    f"{idx}. {symbol}: {action}, decision {decision}, readiness {readiness_text}, "
                    f"entry {_price(row.get('entry'))}, stop {_price(row.get('stop'))}, risk {_pct(row.get('risk_pct'))}. "
                    f"Why: {why}. Missing: {blocker}."
                )
            else:
                missing = _sentence_fragment(missing)
                reason = _sentence_fragment(reason)
                trigger = _sentence_fragment(trigger)
                blocker = missing or "ninguna"
                why = reason or trigger or "score local del ranking"
                lines.append(
                    f"{idx}. {symbol}: {action}, decision {decision}, readiness {readiness_text}, "
                    f"entrada {_price(row.get('entry'))}, stop {_price(row.get('stop'))}, riesgo {_pct(row.get('risk_pct'))}. "
                    f"Por que: {why}. Falta: {blocker}."
                )

        if language == "en":
            reply = (
                "Top opportunities from the local brief: "
                + " ".join(lines)
                + " Guardrail: this ranking is decision support, not execution. Confirm live data, liquidity, account risk, and explicit approval first."
            )
        else:
            reply = (
                "Top oportunidades del brief local: "
                + " ".join(lines)
                + " Guardrail: este ranking es apoyo de decision, no ejecucion. Confirma datos en vivo, liquidez, riesgo de cuenta y aprobacion explicita primero."
            )
        return RoxyBrainReply(
            intent="opportunity_compare",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if top_priority else "normal",
            suggested_actions=("entry_checklist", "ask_risk", "position_size", "confirm_before_execution"),
        )

    def _monitoring_plan_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"I do not have a local opportunity{target} to monitor yet. Run a fresh scan first so I can define trigger, invalidation, and risk."
                if language == "en"
                else f"No tengo una oportunidad local{target} para monitorear todavia. Ejecuta un scan fresco primero para definir gatillo, invalidacion y riesgo."
            )
            return RoxyBrainReply(
                intent="monitoring_plan",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH").upper()
        decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
        trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
        invalidation = _safe_text(row.get("invalidation") or row.get("exit_condition"))
        missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
        reason = _safe_text(row.get("why") or row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))
        readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
        readiness_text = "-" if readiness is None else f"{readiness:.1f}"
        entry = _price(row.get("entry"))
        stop = _price(row.get("stop"))
        risk = _pct(row.get("risk_pct"))

        if not invalidation and stop != "-":
            invalidation = f"stop {stop}"
        if not trigger:
            trigger = "esperar confirmacion de precio y volumen" if language != "en" else "wait for price and volume confirmation"

        if language == "en":
            decision = _localize_market_phrase(decision, language)
            trigger = _sentence_fragment(_localize_market_phrase(trigger, language))
            invalidation = _sentence_fragment(_localize_market_phrase(invalidation, language))
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            reason = _sentence_fragment(_localize_market_phrase(reason, language))
            reply = (
                f"Monitoring {symbol_text}: current action {action}, decision {decision}, readiness {readiness_text}. "
                f"Watch: {trigger}. Invalidation: {invalidation or '-'}. Confirm before action: {missing or 'price-volume confirmation'}. "
                f"Risk frame: entry {entry}, stop {stop}, risk {risk}. Context: {reason or '-'}. "
                "This is a monitoring plan, not execution; ask for checklist or position size only after live data confirms the trigger."
            )
        else:
            trigger = _sentence_fragment(trigger)
            invalidation = _sentence_fragment(invalidation)
            missing = _sentence_fragment(missing)
            reason = _sentence_fragment(reason)
            reply = (
                f"Monitoreo {symbol_text}: accion actual {action}, decision {decision}, readiness {readiness_text}. "
                f"Vigila: {trigger}. Invalidacion: {invalidation or '-'}. Confirma antes de actuar: {missing or 'precio-volumen acompana'}. "
                f"Marco de riesgo: entrada {entry}, stop {stop}, riesgo {risk}. Contexto: {reason or '-'}. "
                "Esto es plan de monitoreo, no ejecucion; pide checklist o sizing solo si los datos en vivo confirman el gatillo."
            )
        return RoxyBrainReply(
            intent="monitoring_plan",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if action in {"ALERT", "BUY", "SELL", "READY"} else "normal",
            suggested_actions=("entry_checklist", "position_size", "ask_market_summary", "set_alert"),
        )

    def _alert_plan_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"I cannot draft a useful alert{target} without a local opportunity. Run a scan first so the alert has a trigger, invalidation, and risk frame."
                if language == "en"
                else f"No puedo preparar una alerta util{target} sin una oportunidad local. Ejecuta un scan primero para que la alerta tenga gatillo, invalidacion y marco de riesgo."
            )
            return RoxyBrainReply(
                intent="alert_plan",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH").upper()
        decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
        trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
        invalidation = _safe_text(row.get("invalidation") or row.get("exit_condition"))
        missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
        entry = _price(row.get("entry"))
        stop = _price(row.get("stop"))
        risk = _pct(row.get("risk_pct"))

        if not trigger and entry != "-":
            trigger = f"price confirms near entry {entry}" if language == "en" else f"precio confirma cerca de entrada {entry}"
        if not invalidation and stop != "-":
            invalidation = f"stop {stop}"

        if language == "en":
            decision = _localize_market_phrase(decision, language)
            trigger = _sentence_fragment(_localize_market_phrase(trigger, language))
            invalidation = _sentence_fragment(_localize_market_phrase(invalidation, language))
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            message = (
                f"{symbol_text} {action}: trigger confirmed. Decision {decision}. Entry {entry}, stop {stop}, risk {risk}. "
                f"Check missing items: {missing or 'none'}."
            )
            reply = (
                f"Alert draft {symbol_text}: condition '{trigger or 'fresh trigger confirmation'}'. "
                f"Cancel or downgrade if: {invalidation or '-'}. Message: {message} "
                "No notification was sent and this is not an order; the operational flow must confirm and activate the alert."
            )
        else:
            trigger = _sentence_fragment(trigger)
            invalidation = _sentence_fragment(invalidation)
            missing = _sentence_fragment(missing)
            message = (
                f"{symbol_text} {action}: gatillo confirmado. Decision {decision}. Entrada {entry}, stop {stop}, riesgo {risk}. "
                f"Revisar faltantes: {missing or 'ninguno'}."
            )
            reply = (
                f"Alerta preparada {symbol_text}: condicion '{trigger or 'confirmacion fresca del gatillo'}'. "
                f"Cancelar o bajar prioridad si: {invalidation or '-'}. Mensaje: {message} "
                "No se envio ninguna notificacion y esto no es orden; el flujo operacional debe confirmar y activar la alerta."
            )
        return RoxyBrainReply(
            intent="alert_plan",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if action in {"ALERT", "BUY", "SELL", "READY"} else "normal",
            suggested_actions=("confirm_alert", "entry_checklist", "position_size", "confirm_before_execution"),
        )

    def _trading_dashboard_handoff_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        requested_symbol = _extract_symbol(query)
        row = self._latest_opportunity(requested_symbol)
        symbol_text = _safe_text((row or {}).get("symbol") or requested_symbol or "SPY").upper()
        timeframe = _extract_query_timeframe(query)
        market = "crypto" if (row and _row_is_crypto(row)) or "/" in symbol_text else "stock"
        url = _trading_dashboard_url(symbol_text, market, timeframe)
        freshness = self._data_freshness_snapshot()
        freshness_state = _safe_text(freshness.get("state") or "missing")
        freshness_age = _safe_text(freshness.get("age_text") or "-")
        action = _safe_text((row or {}).get("signal") or (row or {}).get("ai_action") or "-").upper()
        decision = _safe_text((row or {}).get("decision") or (row or {}).get("trade_decision") or "-")
        readiness = _safe_float((row or {}).get("readiness") or (row or {}).get("ai_score") or (row or {}).get("confluence_score"))
        readiness_text = "-" if readiness is None else f"{readiness:.1f}"

        if language == "en":
            decision = _localize_market_phrase(decision, language)
            if row:
                context = f"Local setup: action {action}, decision {decision}, readiness {readiness_text}."
                next_step = "Ask me for go/no-go, checklist, or position size before any approval."
                actions = ("trade_readiness", "entry_checklist", "position_size", "confirm_before_execution")
                needs_live_source = freshness_state in {"missing", "stale"}
            else:
                context = "I do not have a matching local setup yet."
                next_step = "Refresh the scan first, then ask for go/no-go or a trade ticket."
                actions = ("run_scan", "data_freshness", "market_session")
                needs_live_source = True
            reply = (
                f"Trading page ready: {symbol_text}, {market}, {timeframe}. Open: {url}. "
                f"Data {freshness_state} / {freshness_age}. {context} "
                f"{next_step} This opens the dashboard only; it does not create or send an order."
            )
        else:
            if row:
                context = f"Setup local: accion {action}, decision {decision}, readiness {readiness_text}."
                next_step = "Pideme go/no-go, checklist o tamaño de posicion antes de cualquier aprobacion."
                actions = ("trade_readiness", "entry_checklist", "position_size", "confirm_before_execution")
                needs_live_source = freshness_state in {"missing", "stale"}
            else:
                context = "Todavia no tengo un setup local que coincida."
                next_step = "Refresca el scan primero y luego pideme go/no-go o ticket de trade."
                actions = ("run_scan", "data_freshness", "market_session")
                needs_live_source = True
            reply = (
                f"Pagina operativa lista: {symbol_text}, {market}, {timeframe}. Abre: {url}. "
                f"Datos {freshness_state} / {freshness_age}. {context} "
                f"{next_step} Esto solo abre el dashboard; no crea ni envia una orden."
            )

        return RoxyBrainReply(
            intent="trading_dashboard_handoff",
            reply=reply,
            avatar_state="ready" if row else "blocked",
            emotion="focused" if row else "cautious",
            needs_live_source=needs_live_source,
            safety_level="guarded",
            priority="high",
            suggested_actions=actions,
            active_symbol=symbol_text,
            active_market=market,
            active_timeframe=timeframe,
            action_url=url,
            action_label="Open Roxy Trade" if language == "en" else "Abrir Roxy Trade",
            action_kind="local_trading_dashboard",
        )

    def _trade_readiness_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        freshness = self._data_freshness_snapshot()
        freshness_state = _safe_text(freshness.get("state"))
        freshness_age = _safe_text(freshness.get("age_text"))
        row = self._latest_opportunity(symbol)

        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"Go/no-go{target}: BLOCKED. I do not have a local opportunity to evaluate. Refresh the scan first."
                if language == "en"
                else f"Go/no-go{target}: BLOQUEADO. No tengo una oportunidad local para evaluar. Refresca el scan primero."
            )
            return RoxyBrainReply(
                intent="trade_readiness",
                reply=reply,
                avatar_state="blocked",
                emotion="serious",
                needs_live_source=True,
                safety_level="guarded",
                priority="high",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH").upper()
        decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
        entry = _safe_float(row.get("entry"))
        stop = _safe_float(row.get("stop"))
        risk_pct = _safe_float(row.get("risk_pct"))
        readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
        missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
        trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
        reason = _safe_text(row.get("why") or row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))
        combined_text = " ".join([action, decision, missing, trigger, reason]).lower()

        missing_labels: list[str] = []
        if entry is None or entry <= 0:
            missing_labels.append("entry")
        if stop is None or stop <= 0:
            missing_labels.append("stop")
        if risk_pct is None or risk_pct <= 0:
            missing_labels.append("risk")
        if freshness_state in {"missing", "stale"}:
            missing_labels.append("fresh_data")
        if missing:
            missing_labels.append("confirmations")

        explicit_wait = any(term in combined_text for term in ("wait", "esperar", "no operar", "missing", "falta"))
        explicit_ready = action in {"ALERT", "BUY", "SELL", "READY"} or "trade" in combined_text or "operar" in combined_text
        readiness_ok = readiness is None or readiness >= 70

        if freshness_state in {"missing", "stale"} or entry is None or stop is None or risk_pct is None:
            status = "blocked"
        elif missing or explicit_wait or not readiness_ok or not explicit_ready:
            status = "wait"
        else:
            status = "prepare"

        readiness_text = "-" if readiness is None else f"{readiness:.1f}"
        data_text = f"{freshness_state or 'unknown'} / {freshness_age or '-'}"
        priority = "high" if status in {"blocked", "prepare"} else "normal"
        needs_live_source = freshness_state in {"missing", "stale"}
        signal_state = self._signal_state_text(language=language, symbol=symbol_text)

        if language == "en":
            decision = _localize_market_phrase(decision, language)
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            trigger = _sentence_fragment(_localize_market_phrase(trigger, language))
            reason = _sentence_fragment(_localize_market_phrase(reason, language))
            status_label = {"blocked": "BLOCKED", "wait": "WAIT", "prepare": "PREPARE ONLY"}[status]
            missing_text = ", ".join(missing_labels) if missing_labels else "none"
            next_step = (
                "Refresh the scan before any decision."
                if needs_live_source
                else "Run checklist and sizing before any explicit approval."
                if status == "prepare"
                else "Keep monitoring the trigger and missing confirmations."
            )
            reply = (
                f"Go/no-go {symbol_text}: {status_label}. Data {data_text}. Action {action}, decision {decision}, "
                f"readiness {readiness_text}, entry {_money(entry)}, stop {_money(stop)}, risk {_pct(risk_pct)}. "
                f"Missing gates: {missing_text}. Trigger: {trigger or '-'}. Context: {reason or missing or '-'}. "
                f"{signal_state} Next step: {next_step} This is not execution permission."
            )
        else:
            missing = _sentence_fragment(missing)
            trigger = _sentence_fragment(trigger)
            reason = _sentence_fragment(reason)
            status_label = {"blocked": "BLOQUEADO", "wait": "ESPERAR", "prepare": "PREPARAR SOLO"}[status]
            label_translations = {
                "entry": "entrada",
                "stop": "stop",
                "risk": "riesgo",
                "fresh_data": "datos frescos",
                "confirmations": "confirmaciones",
            }
            missing_text = ", ".join(label_translations.get(label, label) for label in missing_labels) if missing_labels else "ninguno"
            next_step = (
                "Refresca el scan antes de decidir."
                if needs_live_source
                else "Corre checklist y sizing antes de cualquier aprobacion explicita."
                if status == "prepare"
                else "Sigue vigilando el gatillo y las confirmaciones faltantes."
            )
            reply = (
                f"Go/no-go {symbol_text}: {status_label}. Datos {data_text}. Accion {action}, decision {decision}, "
                f"readiness {readiness_text}, entrada {_money(entry)}, stop {_money(stop)}, riesgo {_pct(risk_pct)}. "
                f"Puertas faltantes: {missing_text}. Gatillo: {trigger or '-'}. Contexto: {reason or missing or '-'}. "
                f"{signal_state} Siguiente paso: {next_step} Esto no es permiso de ejecucion."
            )

        return RoxyBrainReply(
            intent="trade_readiness",
            reply=reply,
            avatar_state="blocked" if status == "blocked" else "ready" if status == "prepare" else "speaking",
            emotion="serious" if status == "blocked" else "analytical",
            needs_live_source=needs_live_source,
            safety_level="guarded",
            priority=priority,
            suggested_actions=(
                ("run_scan", "ask_market_summary")
                if needs_live_source
                else ("entry_checklist", "position_size", "confirm_before_execution")
                if status == "prepare"
                else ("monitoring_plan", "ask_market_summary", "set_alert")
            ),
        )

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
                active_symbol=symbol or "",
                emotion="cautious",
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        action = _safe_text(row.get("ai_action") or row.get("signal") or "WATCH")
        family = _safe_text(row.get("strategy_family") or "-")
        decision = _safe_text(row.get("trade_decision") or row.get("decision") or "-")
        explanation = _safe_text(row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))
        signal_state = self._signal_state_text(language=language, symbol=symbol_text)
        if language == "en":
            reply = (
                f"{symbol_text}: status {action}, strategy {family}, decision {decision}. "
                f"Entry {_price(row.get('entry'))}, stop {_price(row.get('stop'))}, "
                f"risk {_pct(row.get('risk_pct'))}, target {_pct(row.get('recommended_target_pct') or row.get('target_pct'))}. "
                f"{explanation} {signal_state}"
            ).strip()
        else:
            reply = (
                f"{symbol_text}: estado {action}, estrategia {family}, decision {decision}. "
                f"Entrada {_price(row.get('entry'))}, stop {_price(row.get('stop'))}, "
                f"riesgo {_pct(row.get('risk_pct'))}, objetivo {_pct(row.get('recommended_target_pct') or row.get('target_pct'))}. "
                f"{explanation} {signal_state}"
            ).strip()
        return RoxyBrainReply(
            intent="opportunity",
            reply=reply,
            active_symbol=symbol_text,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if action.upper() in {"ALERT", "BUY", "SELL"} else "normal",
            suggested_actions=("ask_why", "ask_risk", "confirm_before_execution"),
        )

    def _opportunity_reason_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"I do not have a local opportunity{target} with enough context to explain the reason. Refresh the scan first."
                if language == "en"
                else f"No tengo una oportunidad local{target} con suficiente contexto para explicar el motivo. Refresca el escaneo primero."
            )
            return RoxyBrainReply(
                intent="opportunity_reason",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
        strategy = _safe_text(row.get("strategy_family") or row.get("strategy") or row.get("trend_setup") or "-")
        why = _safe_text(row.get("why") or row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))
        missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
        trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
        readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
        risk = _pct(row.get("risk_pct"))

        if language == "en":
            decision = _localize_market_phrase(decision, language)
            why = _sentence_fragment(_localize_market_phrase(why, language))
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            trigger = _sentence_fragment(_localize_market_phrase(trigger, language))
            readiness_text = "-" if readiness is None else f"{readiness:.1f}"
            reply = (
                f"{symbol_text} reason: strategy {strategy}, decision {decision}, readiness {readiness_text}, risk {risk}. "
                f"Why: {why or '-'}. Missing confirmation: {missing or '-'}. Trigger to monitor: {trigger or '-'}. "
                "My read stays guarded until the missing confirmations are resolved and price-volume agrees."
            )
        else:
            why = _sentence_fragment(why)
            missing = _sentence_fragment(missing)
            trigger = _sentence_fragment(trigger)
            readiness_text = "-" if readiness is None else f"{readiness:.1f}"
            reply = (
                f"{symbol_text} motivo: estrategia {strategy}, decision {decision}, readiness {readiness_text}, riesgo {risk}. "
                f"Por que: {why or '-'}. Confirmacion faltante: {missing or '-'}. Gatillo a vigilar: {trigger or '-'}. "
                "Mi lectura sigue protegida hasta que se resuelvan las confirmaciones faltantes y precio-volumen acompanen."
            )
        return RoxyBrainReply(
            intent="opportunity_reason",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            suggested_actions=("ask_risk", "ask_market_summary", "monitor_trigger"),
        )

    def _account_equity_from_brief(self) -> float | None:
        brief = _load_json(self.brief_path)
        containers = [
            brief,
            brief.get("account") if isinstance(brief.get("account"), dict) else {},
            brief.get("account_summary") if isinstance(brief.get("account_summary"), dict) else {},
            brief.get("portfolio") if isinstance(brief.get("portfolio"), dict) else {},
        ]
        keys = ("equity", "account_equity", "portfolio_value", "cash", "buying_power")
        for container in containers:
            if not isinstance(container, dict):
                continue
            for key in keys:
                value = _safe_float(container.get(key))
                if value is not None and value > 0:
                    return value
        return None

    def _account_snapshot_from_brief(self) -> dict[str, Any]:
        brief = _load_json(self.brief_path)
        containers: list[dict[str, Any]] = [brief]
        for key in (
            "account",
            "account_summary",
            "portfolio",
            "paper_account",
            "alpaca_account",
            "broker_account",
        ):
            value = brief.get(key)
            if isinstance(value, dict):
                containers.append(value)

        journal = {}
        for key in (
            "alpaca_paper_journal",
            "alpaca_paper_journal_snapshot",
            "paper_journal",
            "paper_journal_snapshot",
            "broker_journal",
        ):
            value = brief.get(key)
            if isinstance(value, dict):
                journal = value
                containers.append(value)
                break

        summary = journal.get("summary") if isinstance(journal.get("summary"), dict) else {}
        if summary:
            containers.append(summary)

        def first_number(keys: tuple[str, ...]) -> float | None:
            for container in containers:
                for key in keys:
                    value = _safe_float(container.get(key))
                    if value is not None:
                        return value
            return None

        positions: list[dict[str, Any]] = []
        orders: list[dict[str, Any]] = []
        for container in containers:
            raw_positions = container.get("positions")
            if isinstance(raw_positions, list) and raw_positions:
                positions = [row for row in raw_positions if isinstance(row, dict)]
                break
        for container in containers:
            raw_orders = container.get("orders")
            if isinstance(raw_orders, list) and raw_orders:
                orders = [row for row in raw_orders if isinstance(row, dict)]
                break

        equity = first_number(("equity", "account_equity", "net_liquidation", "portfolio_value"))
        portfolio_value = first_number(("portfolio_value", "account_value", "net_liquidation", "equity"))
        cash = first_number(("cash", "cash_balance", "available_cash"))
        buying_power = first_number(("buying_power", "day_trade_buying_power", "available_buying_power"))
        exposure = first_number(("exposure", "market_value", "gross_exposure", "position_value"))
        if exposure is None and positions:
            exposure_values = [_safe_float(row.get("market_value") or row.get("notional")) or 0.0 for row in positions]
            exposure = sum(exposure_values)
        unrealized_pl = first_number(("unrealized_pl", "unrealized_pnl", "open_pnl", "pnl"))
        if unrealized_pl is None and positions:
            unrealized_pl = sum((_safe_float(row.get("unrealized_pl") or row.get("unrealized_pnl")) or 0.0) for row in positions)
        open_positions = first_number(("open_positions", "position_count"))
        if open_positions is None and positions:
            open_positions = float(len(positions))
        recent_orders = first_number(("recent_orders", "order_count"))
        if recent_orders is None and orders:
            recent_orders = float(len(orders))
        open_winners = first_number(("open_winners", "winning_positions"))
        if open_winners is None and positions:
            open_winners = float(
                sum(1 for row in positions if (_safe_float(row.get("unrealized_pl") or row.get("unrealized_pnl")) or 0.0) >= 0)
            )
        top_position_symbol = ""
        top_position_value = None
        top_position_pct = None
        if positions:
            top_position = max(
                positions,
                key=lambda row: abs(_safe_float(row.get("market_value") or row.get("notional") or row.get("position_value")) or 0.0),
            )
            top_position_symbol = _safe_text(top_position.get("symbol") or top_position.get("ticker")).upper()
            top_position_value = _safe_float(
                top_position.get("market_value") or top_position.get("notional") or top_position.get("position_value")
            )
            if _safe_float(equity) and top_position_value is not None:
                top_position_pct = abs(top_position_value) / (_safe_float(equity) or 1.0)
        as_of = ""
        for container in containers:
            as_of = _safe_text(container.get("as_of") or container.get("updated_at") or container.get("generated_at") or container.get("timestamp"))
            if as_of:
                break

        has_snapshot = any(
            value is not None
            for value in (equity, portfolio_value, cash, buying_power, exposure, unrealized_pl, open_positions, recent_orders)
        )
        if not has_snapshot:
            return {}
        return {
            "equity": equity,
            "portfolio_value": portfolio_value,
            "cash": cash,
            "buying_power": buying_power,
            "exposure": exposure,
            "unrealized_pl": unrealized_pl,
            "open_positions": open_positions,
            "recent_orders": recent_orders,
            "open_winners": open_winners,
            "top_position_symbol": top_position_symbol,
            "top_position_value": top_position_value,
            "top_position_pct": top_position_pct,
            "as_of": as_of,
        }

    def _account_status_reply(self, language: str = "es") -> RoxyBrainReply:
        snapshot = self._account_snapshot_from_brief()
        if not snapshot:
            if language == "en":
                reply = (
                    "I do not have a local account or portfolio snapshot yet. Connect the paper broker snapshot "
                    "or provide account equity before sizing or trade decisions. I will not infer buying power, cash, or positions."
                )
            else:
                reply = (
                    "Todavia no tengo un snapshot local de cuenta o portafolio. Conecta el snapshot del broker paper "
                    "o dame el equity de cuenta antes de sizing o decisiones de trade. No voy a inferir buying power, efectivo ni posiciones."
                )
            return RoxyBrainReply(
                intent="account_status",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("connect_broker_snapshot", "provide_account_equity", "run_scan"),
            )

        equity = snapshot.get("equity")
        exposure = snapshot.get("exposure")
        exposure_pct = None
        if _safe_float(equity) and _safe_float(exposure) is not None:
            exposure_pct = (_safe_float(exposure) or 0.0) / (_safe_float(equity) or 1.0)
        as_of = _safe_text(snapshot.get("as_of"))
        as_of_text = f" Snapshot: {as_of}." if as_of and language == "en" else f" Snapshot: {as_of}." if as_of else ""
        if exposure_pct is None:
            exposure_band = "unknown"
        elif exposure_pct < 0.10:
            exposure_band = "low"
        elif exposure_pct < 0.30:
            exposure_band = "moderate"
        elif exposure_pct < 0.60:
            exposure_band = "high"
        else:
            exposure_band = "aggressive"
        top_position_symbol = _safe_text(snapshot.get("top_position_symbol"))
        top_position_value = snapshot.get("top_position_value")
        top_position_pct = _safe_float(snapshot.get("top_position_pct"))
        if top_position_pct is None:
            concentration_band = "unknown"
        elif top_position_pct < 0.15:
            concentration_band = "low"
        elif top_position_pct < 0.25:
            concentration_band = "moderate"
        else:
            concentration_band = "high"
        priority = "high" if exposure_band in {"high", "aggressive"} or concentration_band == "high" else "normal"

        if language == "en":
            exposure_label = {
                "low": "low",
                "moderate": "moderate",
                "high": "high",
                "aggressive": "aggressive",
                "unknown": "unknown",
            }[exposure_band]
            concentration_label = {
                "low": "low",
                "moderate": "moderate",
                "high": "high",
                "unknown": "unknown",
            }[concentration_band]
            concentration_text = (
                f"Largest position {top_position_symbol or '-'} {_money(top_position_value)}"
                f"{' (' + _pct(top_position_pct) + ' of equity)' if top_position_pct is not None else ''}, "
                f"concentration {concentration_label}."
                if top_position_symbol or top_position_value is not None
                else "Largest position unavailable; concentration unknown."
            )
            risk_next = (
                "Risk next: pause new sizing until exposure, stops, and concentration are reviewed."
                if exposure_band in {"high", "aggressive"} or concentration_band == "high"
                else "Risk next: sizing can be reviewed only after fresh opportunity and stop data are confirmed."
            )
            reply = (
                "Account snapshot: "
                f"equity {_money(snapshot.get('equity'))}, portfolio value {_money(snapshot.get('portfolio_value'))}, "
                f"cash {_money(snapshot.get('cash'))}, buying power {_money(snapshot.get('buying_power'))}. "
                f"Open positions {int(snapshot.get('open_positions') or 0)}, exposure {_money(exposure)}"
                f"{' (' + _pct(exposure_pct) + ' of equity)' if exposure_pct is not None else ''}, "
                f"exposure risk {exposure_label}, open P/L {_money(snapshot.get('unrealized_pl'))}, "
                f"recent orders {int(snapshot.get('recent_orders') or 0)}. {concentration_text} {risk_next}"
                f"{as_of_text} Guardrail: this is a local account read only, not a broker command; confirm broker state before acting."
            )
        else:
            exposure_label = {
                "low": "bajo",
                "moderate": "moderado",
                "high": "alto",
                "aggressive": "agresivo",
                "unknown": "desconocido",
            }[exposure_band]
            concentration_label = {
                "low": "baja",
                "moderate": "moderada",
                "high": "alta",
                "unknown": "desconocida",
            }[concentration_band]
            concentration_text = (
                f"Mayor posicion {top_position_symbol or '-'} {_money(top_position_value)}"
                f"{' (' + _pct(top_position_pct) + ' del equity)' if top_position_pct is not None else ''}, "
                f"concentracion {concentration_label}."
                if top_position_symbol or top_position_value is not None
                else "Mayor posicion no disponible; concentracion desconocida."
            )
            risk_next = (
                "Siguiente riesgo: pausa nuevo sizing hasta revisar exposicion, stops y concentracion."
                if exposure_band in {"high", "aggressive"} or concentration_band == "high"
                else "Siguiente riesgo: revisar sizing solo despues de confirmar oportunidad fresca y stop."
            )
            reply = (
                "Snapshot de cuenta: "
                f"equity {_money(snapshot.get('equity'))}, valor portafolio {_money(snapshot.get('portfolio_value'))}, "
                f"efectivo {_money(snapshot.get('cash'))}, buying power {_money(snapshot.get('buying_power'))}. "
                f"Posiciones abiertas {int(snapshot.get('open_positions') or 0)}, exposicion {_money(exposure)}"
                f"{' (' + _pct(exposure_pct) + ' del equity)' if exposure_pct is not None else ''}, "
                f"riesgo de exposicion {exposure_label}, P/L abierto {_money(snapshot.get('unrealized_pl'))}, "
                f"ordenes recientes {int(snapshot.get('recent_orders') or 0)}. {concentration_text} {risk_next}"
                f"{as_of_text} Guardrail: esto es solo lectura local de cuenta, no comando de broker; confirma el estado del broker antes de actuar."
            )
        actions = (
            ("risk_review", "trade_readiness", "confirm_before_execution")
            if exposure_band in {"high", "aggressive"} or concentration_band == "high"
            else ("position_size", "trade_readiness", "confirm_before_execution")
        )
        return RoxyBrainReply(
            intent="account_status",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority=priority,
            suggested_actions=actions,
        )

    def _trade_ticket_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"Trade ticket{target}: BLOCKED. I do not have a local opportunity with entry, stop, and risk. Refresh the scan first."
                if language == "en"
                else f"Ticket de trade{target}: BLOQUEADO. No tengo una oportunidad local con entrada, stop y riesgo. Refresca el scan primero."
            )
            return RoxyBrainReply(
                intent="trade_ticket",
                reply=reply,
                avatar_state="blocked",
                emotion="serious",
                needs_live_source=True,
                safety_level="guarded",
                priority="high",
                suggested_actions=("run_scan", "ask_latest_opportunity", "data_freshness"),
            )

        account = self._account_snapshot_from_brief()
        equity = _extract_query_equity(query) or _safe_float(account.get("equity") if account else None)
        risk_fraction, explicit_risk = _extract_query_risk_fraction(query)
        if risk_fraction is None:
            risk_fraction = 0.005
        risk_fraction = max(0.0001, min(risk_fraction, 0.05))

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH").upper()
        decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
        entry = _safe_float(row.get("entry"))
        stop = _safe_float(row.get("stop"))
        risk_pct = _safe_float(row.get("risk_pct"))
        readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
        missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
        trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
        invalidation = _safe_text(row.get("invalidation") or row.get("exit_condition"))
        why = _safe_text(row.get("why") or row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))

        blockers: list[str] = []
        if entry is None or entry <= 0:
            blockers.append("entry")
        if stop is None or stop <= 0:
            blockers.append("stop")
        if risk_pct is None or risk_pct <= 0:
            blockers.append("risk")
        if not trigger:
            blockers.append("trigger")
        if missing:
            blockers.append("confirmations")

        sizing_text = ""
        if equity is not None and equity > 0 and entry and stop and entry > 0 and stop > 0 and entry != stop:
            per_unit_risk = abs(entry - stop)
            risk_budget = equity * risk_fraction
            raw_qty = risk_budget / per_unit_risk if per_unit_risk > 0 else 0
            is_fractional = "/" in symbol_text
            qty = raw_qty if is_fractional else int(raw_qty)
            notional = qty * entry
            used_risk = qty * per_unit_risk
            qty_text = f"{qty:.6f}".rstrip("0").rstrip(".") if is_fractional else str(int(qty))
            risk_source = "explicit" if explicit_risk and language == "en" else "explicito" if explicit_risk else "default 0.5%"
            if language == "en":
                sizing_text = (
                    f"Sizing: equity {_money(equity)}, account risk {_pct(risk_fraction)} ({risk_source}), "
                    f"qty {qty_text}, notional {_money(notional)}, risk used {_money(used_risk)}."
                )
            else:
                sizing_text = (
                    f"Sizing: equity {_money(equity)}, riesgo cuenta {_pct(risk_fraction)} ({risk_source}), "
                    f"cantidad {qty_text}, nocional {_money(notional)}, riesgo usado {_money(used_risk)}."
                )
        else:
            if equity is None or equity <= 0:
                blockers.append("account_equity")
            sizing_text = (
                "Sizing: account equity missing or entry/stop invalid."
                if language == "en"
                else "Sizing: falta equity de cuenta o entrada/stop valido."
            )

        status = "blocked" if any(item in blockers for item in ("entry", "stop", "risk", "account_equity")) else (
            "wait" if blockers else "draft"
        )
        readiness_text = "-" if readiness is None else f"{readiness:.1f}"

        def blocker_text() -> str:
            unique = []
            for item in blockers:
                if item not in unique:
                    unique.append(item)
            if language == "en":
                mapping = {
                    "entry": "entry",
                    "stop": "stop",
                    "risk": "risk",
                    "trigger": "trigger",
                    "confirmations": "confirmations",
                    "account_equity": "account equity",
                }
                return ", ".join(mapping.get(item, item) for item in unique) if unique else "none"
            mapping = {
                "entry": "entrada",
                "stop": "stop",
                "risk": "riesgo",
                "trigger": "gatillo",
                "confirmations": "confirmaciones",
                "account_equity": "equity de cuenta",
            }
            return ", ".join(mapping.get(item, item) for item in unique) if unique else "ninguno"

        if language == "en":
            decision = _localize_market_phrase(decision, language)
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            trigger = _sentence_fragment(_localize_market_phrase(trigger, language))
            invalidation = _sentence_fragment(_localize_market_phrase(invalidation, language))
            why = _sentence_fragment(_localize_market_phrase(why, language))
            status_label = {"blocked": "BLOCKED", "wait": "WAIT", "draft": "DRAFT ONLY"}[status]
            reply = (
                f"Trade ticket {symbol_text}: {status_label}. Action {action}, decision {decision}, "
                f"readiness {readiness_text}, entry {_money(entry)}, stop {_money(stop)}, risk {_pct(risk_pct)}. "
                f"Trigger: {trigger or '-'}. Invalidation: {invalidation or '-'}. Reason: {why or '-'}. "
                f"Pending: {blocker_text()}. {sizing_text} "
                "No order was created; execution requires explicit confirmation in the operational flow."
            )
        else:
            missing = _sentence_fragment(missing)
            trigger = _sentence_fragment(trigger)
            invalidation = _sentence_fragment(invalidation)
            why = _sentence_fragment(why)
            status_label = {"blocked": "BLOQUEADO", "wait": "ESPERAR", "draft": "BORRADOR SOLO"}[status]
            reply = (
                f"Ticket de trade {symbol_text}: {status_label}. Accion {action}, decision {decision}, "
                f"readiness {readiness_text}, entrada {_money(entry)}, stop {_money(stop)}, riesgo {_pct(risk_pct)}. "
                f"Gatillo: {trigger or '-'}. Invalidacion: {invalidation or '-'}. Razon: {why or '-'}. "
                f"Pendiente: {blocker_text()}. {sizing_text} "
                "No se creo ninguna orden; ejecutar requiere confirmacion explicita en el flujo operacional."
            )

        return RoxyBrainReply(
            intent="trade_ticket",
            reply=reply,
            avatar_state="blocked" if status == "blocked" else "speaking",
            emotion="serious" if status == "blocked" else "analytical",
            safety_level="guarded",
            priority="high" if status in {"blocked", "draft"} else "normal",
            suggested_actions=(
                ("provide_account_equity", "position_size", "entry_checklist", "confirm_before_execution")
                if "account_equity" in blockers
                else ("entry_checklist", "position_size", "confirm_before_execution")
            ),
        )

    def _position_size_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"I do not have a local opportunity{target} with entry and stop. Refresh the scan before sizing."
                if language == "en"
                else f"No tengo una oportunidad local{target} con entrada y stop. Refresca el scan antes de calcular tamaño."
            )
            return RoxyBrainReply(
                intent="position_size",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_risk"),
            )

        equity = _extract_query_equity(query) or self._account_equity_from_brief()
        if equity is None or equity <= 0:
            if language == "en":
                reply = (
                    "I can size the position, but I need account equity or capital first. Ask like: "
                    "'position size NVDA with account 25000 risk 0.5%'. I will not infer account size."
                )
            else:
                reply = (
                    "Puedo calcular el tamaño de posición, pero primero necesito capital o equity de cuenta. "
                    "Pregunta por ejemplo: 'tamaño de posicion NVDA con capital 25000 riesgo 0.5%'. No voy a inferir tamaño de cuenta."
                )
            return RoxyBrainReply(
                intent="position_size",
                reply=reply,
                emotion="cautious",
                safety_level="guarded",
                suggested_actions=("provide_account_equity", "ask_risk", "run_scan"),
            )

        entry = _safe_float(row.get("entry"))
        stop = _safe_float(row.get("stop"))
        if entry is None or stop is None or entry <= 0 or stop <= 0 or entry == stop:
            symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
            reply = (
                f"{symbol_text} is missing a valid entry/stop pair, so I cannot size it safely."
                if language == "en"
                else f"{symbol_text} no tiene un par entrada/stop valido, asi que no puedo calcular tamaño con seguridad."
            )
            return RoxyBrainReply(
                intent="position_size",
                reply=reply,
                emotion="cautious",
                safety_level="guarded",
                suggested_actions=("ask_risk", "run_scan"),
            )

        risk_fraction, explicit_risk = _extract_query_risk_fraction(query)
        if risk_fraction is None:
            risk_fraction = 0.005
        risk_fraction = max(0.0001, min(risk_fraction, 0.05))
        risk_budget = equity * risk_fraction
        per_unit_risk = abs(entry - stop)
        raw_qty = risk_budget / per_unit_risk if per_unit_risk > 0 else 0
        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        is_fractional = "/" in symbol_text
        qty = raw_qty if is_fractional else int(raw_qty)
        notional = qty * entry
        used_risk = qty * per_unit_risk
        risk_source = "explicito" if explicit_risk and language != "en" else "explicit" if explicit_risk else (
            "default 0.5%" if language == "en" else "default 0.5%"
        )
        qty_text = f"{qty:.6f}".rstrip("0").rstrip(".") if is_fractional else str(int(qty))

        if language == "en":
            reply = (
                f"{symbol_text} position size: account {_money(equity)}, account risk {_pct(risk_fraction)} "
                f"({risk_source}), risk budget {_money(risk_budget)}. Entry {_money(entry)}, stop {_money(stop)}, "
                f"risk per unit {_money(per_unit_risk)}. Qty {qty_text}, notional {_money(notional)}, "
                f"risk used {_money(used_risk)}. This is sizing math only, not an execution order; confirm source data and account state first."
            )
        else:
            reply = (
                f"{symbol_text} tamaño de posicion: cuenta {_money(equity)}, riesgo de cuenta {_pct(risk_fraction)} "
                f"({risk_source}), presupuesto de riesgo {_money(risk_budget)}. Entrada {_money(entry)}, stop {_money(stop)}, "
                f"riesgo por unidad {_money(per_unit_risk)}. Cantidad {qty_text}, nocional {_money(notional)}, "
                f"riesgo usado {_money(used_risk)}. Esto es solo calculo de sizing, no una orden; confirma datos y estado de cuenta primero."
            )
        return RoxyBrainReply(
            intent="position_size",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            suggested_actions=("show_trade_ticket", "ask_market_summary", "confirm_before_execution"),
        )

    def _entry_checklist_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"I do not have a local opportunity{target} to validate. Refresh the scan first."
                if language == "en"
                else f"No tengo una oportunidad local{target} para validar. Refresca el scan primero."
            )
            return RoxyBrainReply(
                intent="entry_checklist",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        action = _safe_text(row.get("signal") or row.get("ai_action") or "WATCH").upper()
        decision = _safe_text(row.get("decision") or row.get("trade_decision") or "-")
        entry = _safe_float(row.get("entry"))
        stop = _safe_float(row.get("stop"))
        risk_pct = _safe_float(row.get("risk_pct"))
        readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
        missing = _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers"))
        trigger = _safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf"))
        invalidation = _safe_text(row.get("invalidation") or row.get("exit_condition"))
        why = _safe_text(row.get("why") or row.get("explanation") or row.get("memory_note") or row.get("alert_quality_reason"))

        checks: list[tuple[str, bool]] = [
            ("entry", entry is not None and entry > 0),
            ("stop", stop is not None and stop > 0),
            ("risk", risk_pct is not None and risk_pct > 0),
            ("trigger", bool(trigger)),
            ("readiness", readiness is not None and readiness >= 70),
            ("no_missing", not bool(missing)),
        ]
        missing_labels = [label for label, passed in checks if not passed]
        lower_text = " ".join([action, decision, missing, why]).lower()
        explicit_wait = any(term in lower_text for term in ("wait", "esperar", "no operar", "missing", "falta"))
        explicit_ready = action in {"ALERT", "BUY", "SELL", "READY"} or "trade" in lower_text or "operar" in lower_text

        if missing_labels or explicit_wait:
            status = "wait"
        elif explicit_ready and readiness is not None and readiness >= 70:
            status = "ready"
        else:
            status = "wait"
        if entry is None or stop is None or risk_pct is None:
            status = "blocked"

        if language == "en":
            decision = _localize_market_phrase(decision, language)
            missing = _sentence_fragment(_localize_market_phrase(missing, language))
            trigger = _sentence_fragment(_localize_market_phrase(trigger, language))
            invalidation = _sentence_fragment(_localize_market_phrase(invalidation, language))
            status_label = {"ready": "READY TO PREPARE", "wait": "WAIT", "blocked": "BLOCKED"}[status]
            readiness_text = "-" if readiness is None else f"{readiness:.1f}"
            reply = (
                f"{symbol_text} entry checklist: {status_label}. Action {action}, decision {decision}, "
                f"readiness {readiness_text}, entry {_money(entry)}, stop {_money(stop)}, risk {_pct(risk_pct)}. "
                f"Trigger: {trigger or '-'}. Invalidation: {invalidation or '-'}. "
                f"Missing checks: {', '.join(missing_labels) if missing_labels else 'none'}. "
                f"Missing note: {missing or '-'}. Guardrail: even if ready, this is preparation only; execution needs explicit confirmation."
            )
        else:
            missing = _sentence_fragment(missing)
            trigger = _sentence_fragment(trigger)
            invalidation = _sentence_fragment(invalidation)
            status_label = {"ready": "LISTO PARA PREPARAR", "wait": "ESPERAR", "blocked": "BLOQUEADO"}[status]
            readiness_text = "-" if readiness is None else f"{readiness:.1f}"
            label_translations = {
                "entry": "entrada",
                "stop": "stop",
                "risk": "riesgo",
                "trigger": "gatillo",
                "readiness": "readiness",
                "no_missing": "confirmaciones pendientes",
            }
            missing_text = ", ".join(label_translations.get(label, label) for label in missing_labels) if missing_labels else "ninguno"
            reply = (
                f"{symbol_text} checklist de entrada: {status_label}. Accion {action}, decision {decision}, "
                f"readiness {readiness_text}, entrada {_money(entry)}, stop {_money(stop)}, riesgo {_pct(risk_pct)}. "
                f"Gatillo: {trigger or '-'}. Invalidacion: {invalidation or '-'}. "
                f"Checks faltantes: {missing_text}. Nota faltante: {missing or '-'}. "
                f"Guardrail: aunque este listo, esto solo prepara la operacion; ejecutar requiere confirmacion explicita."
            )

        priority = "high" if status == "ready" else "normal"
        avatar_state = "ready" if status == "ready" else "blocked" if status == "blocked" else "speaking"
        emotion = "serious" if status == "blocked" else "analytical"
        return RoxyBrainReply(
            intent="entry_checklist",
            reply=reply,
            avatar_state=avatar_state,
            emotion=emotion,
            safety_level="guarded",
            priority=priority,
            suggested_actions=("ask_risk", "position_size", "confirm_before_execution"),
        )

    def _first_float_from_row(self, row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = _safe_float(row.get(key))
            if value is not None and value > 0:
                return value
        return None

    def _first_number_from_row(self, row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = _safe_float(row.get(key))
            if value is not None:
                return value
        return None

    def _technical_indicators_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"I do not have a local technical-indicator snapshot{target}. Refresh the scan or chart first."
                if language == "en"
                else f"No tengo una lectura local de indicadores tecnicos{target}. Refresca el scan o la grafica primero."
            )
            return RoxyBrainReply(
                intent="technical_indicators",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "data_freshness", "ask_market_summary"),
            )

        indicator_keys = (
            "ema9",
            "ema21",
            "sma20",
            "sma40",
            "sma100",
            "sma200",
            "rsi",
            "rsi14",
            "macd",
            "macd_signal",
            "macd_hist",
            "vwap",
            "bb_upper",
            "bb_lower",
            "rel_volume",
            "relative_volume",
            "volume",
        )
        has_indicator_data = any(row.get(key) is not None for key in indicator_keys)
        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        if not has_indicator_data:
            reply = (
                f"{symbol_text} has a local opportunity row, but no EMA/RSI/VWAP/MACD/volume snapshot. Refresh the chart scan before reading indicators."
                if language == "en"
                else f"{symbol_text} tiene oportunidad local, pero no trae snapshot de EMA/RSI/VWAP/MACD/volumen. Refresca el scan de grafica antes de leer indicadores."
            )
            return RoxyBrainReply(
                intent="technical_indicators",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "data_freshness", "support_resistance"),
            )

        close = self._first_number_from_row(row, ("close", "last_price", "current_price", "price", "mark"))
        ema_fast = self._first_number_from_row(row, ("ema9", "ema_9", "ema_fast"))
        ema_slow = self._first_number_from_row(row, ("ema21", "ema_21", "ema_slow", "sma20"))
        sma_major = self._first_number_from_row(row, ("sma40", "sma50", "sma100", "sma200"))
        rsi = self._first_number_from_row(row, ("rsi14", "rsi"))
        vwap = self._first_number_from_row(row, ("vwap",))
        macd = self._first_number_from_row(row, ("macd",))
        macd_signal = self._first_number_from_row(row, ("macd_signal", "macd_sig"))
        macd_hist = self._first_number_from_row(row, ("macd_hist", "macd_histogram"))
        bb_lower = self._first_number_from_row(row, ("bb_lower", "bollinger_lower"))
        bb_upper = self._first_number_from_row(row, ("bb_upper", "bollinger_upper"))
        volume = self._first_number_from_row(row, ("volume",))
        rel_volume = self._first_number_from_row(row, ("rel_volume", "relative_volume"))

        bias_parts_es: list[str] = []
        bias_parts_en: list[str] = []
        if ema_fast is not None and ema_slow is not None:
            if ema_fast > ema_slow:
                bias_parts_es.append("EMA corta sobre media lenta")
                bias_parts_en.append("fast EMA above slower average")
            elif ema_fast < ema_slow:
                bias_parts_es.append("EMA corta bajo media lenta")
                bias_parts_en.append("fast EMA below slower average")
        if close is not None and vwap is not None:
            if close >= vwap:
                bias_parts_es.append("precio sobre VWAP")
                bias_parts_en.append("price above VWAP")
            else:
                bias_parts_es.append("precio bajo VWAP")
                bias_parts_en.append("price below VWAP")
        if rsi is not None:
            if rsi >= 70:
                bias_parts_es.append("RSI extendido")
                bias_parts_en.append("RSI extended")
            elif rsi >= 55:
                bias_parts_es.append("RSI constructivo")
                bias_parts_en.append("RSI constructive")
            elif rsi <= 35:
                bias_parts_es.append("RSI debil/sobrevendido")
                bias_parts_en.append("RSI weak/oversold")
            else:
                bias_parts_es.append("RSI neutral")
                bias_parts_en.append("RSI neutral")
        if macd is not None and macd_signal is not None:
            if macd >= macd_signal:
                bias_parts_es.append("MACD sobre senal")
                bias_parts_en.append("MACD above signal")
            else:
                bias_parts_es.append("MACD bajo senal")
                bias_parts_en.append("MACD below signal")
        if rel_volume is not None:
            if rel_volume >= 1.2:
                bias_parts_es.append("volumen relativo confirma")
                bias_parts_en.append("relative volume confirms")
            elif rel_volume < 0.8:
                bias_parts_es.append("volumen relativo bajo")
                bias_parts_en.append("relative volume low")

        rsi_text = "-" if rsi is None else f"{rsi:.1f}"
        macd_text = "/".join(
            "-" if value is None else f"{value:.3f}".rstrip("0").rstrip(".")
            for value in (macd, macd_signal, macd_hist)
        )
        volume_text = "-" if volume is None else f"{volume:,.0f}"
        rel_volume_text = "-" if rel_volume is None else f"{rel_volume:.2f}x"
        if language == "en":
            read = "; ".join(bias_parts_en) or "insufficient indicator agreement"
            reply = (
                f"{symbol_text} indicators: price {_money(close)}, EMA9 {_money(ema_fast)}, EMA21/SMA20 {_money(ema_slow)}, "
                f"major SMA {_money(sma_major)}, VWAP {_money(vwap)}, RSI {rsi_text}, MACD/signal/hist {macd_text}, "
                f"Bollinger {_money(bb_lower)}-{_money(bb_upper)}, volume {volume_text} ({rel_volume_text}). "
                f"Read: {read}. This is technical decision support only; confirm fresh candles, levels, liquidity, and risk before acting."
            )
        else:
            read = "; ".join(bias_parts_es) or "acuerdo tecnico insuficiente"
            reply = (
                f"{symbol_text} indicadores: precio {_money(close)}, EMA9 {_money(ema_fast)}, EMA21/SMA20 {_money(ema_slow)}, "
                f"SMA mayor {_money(sma_major)}, VWAP {_money(vwap)}, RSI {rsi_text}, MACD/senal/hist {macd_text}, "
                f"Bollinger {_money(bb_lower)}-{_money(bb_upper)}, volumen {volume_text} ({rel_volume_text}). "
                f"Lectura: {read}. Esto es solo apoyo tecnico de decision; confirma velas frescas, niveles, liquidez y riesgo antes de actuar."
            )
        return RoxyBrainReply(
            intent="technical_indicators",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if _safe_text(row.get("signal") or row.get("ai_action")).upper() in {"ALERT", "BUY", "SELL"} else "normal",
            suggested_actions=("support_resistance", "entry_checklist", "ask_risk", "confirm_before_execution"),
        )

    def _support_resistance_reply(self, query: str, language: str = "es") -> RoxyBrainReply:
        symbol = _extract_symbol(query)
        row = self._latest_opportunity(symbol)
        if not row:
            target = f" for {symbol}" if symbol and language == "en" else f" para {symbol}" if symbol else ""
            reply = (
                f"I do not have local support/resistance levels{target}. Refresh the scan first so I can read real levels instead of guessing."
                if language == "en"
                else f"No tengo niveles locales de soporte/resistencia{target}. Refresca el scan primero para leer niveles reales sin adivinar."
            )
            return RoxyBrainReply(
                intent="support_resistance",
                reply=reply,
                emotion="cautious",
                needs_live_source=True,
                safety_level="guarded",
                suggested_actions=("run_scan", "ask_market_summary"),
            )

        symbol_text = _safe_text(row.get("symbol") or symbol or "-").upper()
        close = self._first_float_from_row(row, ("close", "last_price", "current_price", "price", "mark"))
        support = self._first_float_from_row(
            row,
            ("support", "support_level", "range_low_60", "recent_low", "pivot_low", "bb_lower", "lower_band", "stop"),
        )
        resistance = self._first_float_from_row(
            row,
            (
                "resistance",
                "resistance_level",
                "range_high_60",
                "recent_high",
                "pivot_high",
                "bb_upper",
                "upper_band",
                "target_2",
                "target_2pct",
                "target",
                "recommended_target_price",
            ),
        )
        entry = _safe_float(row.get("entry"))
        stop = _safe_float(row.get("stop"))
        target = self._first_float_from_row(
            row,
            ("recommended_target_price", "target", "target_2", "target_2pct", "target_5", "target_5pct"),
        )
        trigger = _sentence_fragment(_safe_text(row.get("entry_trigger") or row.get("trigger") or row.get("entry_tf")))
        missing = _sentence_fragment(_safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers")))

        if close is not None and support is not None and resistance is not None:
            if close < support:
                zone_es = "precio bajo soporte; setup defensivo o invalido hasta recuperar"
                zone_en = "price below support; defensive or invalid until it reclaims"
            elif close > resistance:
                zone_es = "ruptura sobre resistencia; necesita sostener y confirmar volumen"
                zone_en = "breakout above resistance; it must hold and confirm volume"
            elif abs(close - support) / close <= 0.012:
                zone_es = "cerca de soporte; buscar defensa/rebote antes de preparar"
                zone_en = "near support; look for defense/rebound before preparing"
            elif abs(close - resistance) / close <= 0.012:
                zone_es = "cerca de resistencia; ruptura valida solo con volumen"
                zone_en = "near resistance; breakout is valid only with volume"
            else:
                zone_es = "entre soporte y resistencia; esperar pullback o ruptura"
                zone_en = "between support and resistance; wait for pullback or breakout"
        else:
            zone_es = "niveles incompletos; tratarlos como mapa preliminar"
            zone_en = "levels incomplete; treat this as a preliminary map"

        if language == "en":
            reply = (
                f"{symbol_text} key levels: support {_money(support)}, resistance {_money(resistance)}, "
                f"current {_money(close)}, entry {_money(entry)}, stop {_money(stop)}, nearby target {_money(target)}. "
                f"Read: {zone_en}. Trigger: {_localize_market_phrase(trigger, language) or '-'}. "
                f"Missing confirmation: {_localize_market_phrase(missing, language) or '-'}. "
                "Use these as decision support only; confirm fresh data, volume, spreads, and risk before any order."
            )
        else:
            reply = (
                f"{symbol_text} niveles clave: soporte {_money(support)}, resistencia {_money(resistance)}, "
                f"precio actual {_money(close)}, entrada {_money(entry)}, stop {_money(stop)}, objetivo cercano {_money(target)}. "
                f"Lectura: {zone_es}. Gatillo: {trigger or '-'}. Confirmacion faltante: {missing or '-'}. "
                "Usa esto solo como apoyo de decision; confirma datos frescos, volumen, spreads y riesgo antes de cualquier orden."
            )

        return RoxyBrainReply(
            intent="support_resistance",
            reply=reply,
            emotion="analytical",
            safety_level="guarded",
            priority="high" if _safe_text(row.get("signal") or row.get("ai_action")).upper() in {"ALERT", "BUY", "SELL"} else "normal",
            suggested_actions=("entry_checklist", "ask_risk", "set_alert", "confirm_before_execution"),
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
        rows = self._opportunity_rows()
        if symbol:
            matches = [row for row in rows if _symbol_matches(row.get("symbol"), symbol)]
            return self._ranked_opportunities(matches)[0] if matches else {}
        ranked = self._ranked_opportunities(rows)
        return ranked[0] if ranked else {}

    def _ranked_opportunities(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        indexed = [(self._opportunity_rank_score(row), idx, row) for idx, row in enumerate(rows)]
        indexed.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        return [row for _score, _idx, row in indexed]

    def _opportunity_rank_score(self, row: dict[str, Any]) -> float:
        action = _safe_text(row.get("signal") or row.get("ai_action")).upper()
        decision = _safe_text(row.get("decision") or row.get("trade_decision")).lower()
        text = " ".join(
            _safe_text(row.get(key))
            for key in (
                "why",
                "explanation",
                "memory_note",
                "alert_quality_reason",
                "what_is_missing",
                "missing",
                "blockers",
                "entry_trigger",
                "trigger",
            )
        ).lower()
        score = {
            "BUY": 110,
            "SELL": 110,
            "ALERT": 100,
            "READY": 95,
            "WATCH": 45,
        }.get(action, 20)
        readiness = _safe_float(row.get("readiness") or row.get("ai_score") or row.get("confluence_score"))
        if readiness is not None:
            score += max(0, min(readiness, 100))
        probability = _safe_float(row.get("probability"))
        if probability is not None:
            score += max(0, min(probability, 100)) * 0.15
        if "trade" in decision or "operar" in decision or "ready" in decision:
            score += 25
        if "wait" in decision or "esperar" in decision or "no operar" in text:
            score -= 15
        if row.get("entry") is not None and row.get("stop") is not None and row.get("risk_pct") is not None:
            score += 15
        if _safe_text(row.get("what_is_missing") or row.get("missing") or row.get("blockers")):
            score -= 20
        return score


def generate_interactive_reply(query: str, user: str | None = None) -> str:
    return RoxyInteractiveBrain().generate_reply(query, user=user).reply
