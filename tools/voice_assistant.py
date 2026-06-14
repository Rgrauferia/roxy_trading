from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import storage

from tools.roxy_interactive_brain import RoxyBrainReply
from tools.roxy_interactive_brain import RoxyConversationMemory
from tools.roxy_interactive_brain import RoxyFeedbackMemory
from tools.roxy_interactive_brain import RoxyInteractiveBrain
from tools.roxy_interactive_brain import RoxyUserProfile
from tools.roxy_interactive_brain import build_voice_events
from tools.roxy_interactive_brain import list_knowledge_sources


BRIEF_PATH = Path("alerts/roxy_ai_brief.json")
MEMORY_PATH = Path("alerts/roxy_ai_memory.json")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number * 100:.2f}%"


def _price(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number:.2f}"


def speakable_timeframe(value: str, language: str = "es") -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    compact = raw.lower().replace(" ", "")
    units = {
        "m": ("minute", "minutes", "minuto", "minutos"),
        "h": ("hour", "hours", "hora", "horas"),
        "d": ("day", "days", "dia", "dias"),
    }
    suffix = compact[-1:]
    amount = compact[:-1]
    if suffix in units and amount.isdigit():
        en_singular, en_plural, es_singular, es_plural = units[suffix]
        if language == "en":
            unit = en_singular if amount == "1" else en_plural
        else:
            unit = es_singular if amount == "1" else es_plural
        return f"{amount} {unit}"
    return raw


def _latest_opportunity(symbol: str | None = None) -> dict[str, Any]:
    brief = _load_json(BRIEF_PATH)
    rows = brief.get("opportunities") or []
    if not isinstance(rows, list):
        return {}
    if symbol:
        target = symbol.upper()
        for row in rows:
            if str(row.get("symbol") or "").upper() == target:
                return row
    return rows[0] if rows else {}


def _summarize_opportunity(row: dict[str, Any]) -> str:
    if not row:
        return "Ahora mismo Roxy no tiene una oportunidad clara en el brief."
    symbol = str(row.get("symbol") or "-").upper()
    action = str(row.get("ai_action") or row.get("signal") or "WATCH")
    family = str(row.get("strategy_family") or "-")
    decision = str(row.get("trade_decision") or "-")
    entry = _price(row.get("entry"))
    stop = _price(row.get("stop"))
    risk = _pct(row.get("risk_pct"))
    target = _pct(row.get("recommended_target_pct"))
    explanation = str(row.get("explanation") or row.get("memory_note") or "")
    return (
        f"{symbol}: estado {action}, estrategia {family}, decision {decision}. "
        f"Entrada {entry}, stop {stop}, riesgo {risk}, objetivo {target}. {explanation}"
    ).strip()


def _summarize_learning() -> str:
    brief = _load_json(BRIEF_PATH)
    profiles = brief.get("learning_profiles") or []
    if not profiles:
        memory = _load_json(MEMORY_PATH)
        stats = memory.get("strategy_stats") or {}
        if not stats:
            return "Roxy todavia esta recolectando memoria. Necesita mas senales cerradas para aprender con confianza."
        profiles = [
            {
                "strategy_family": family,
                "alerts": values.get("alerts", 0),
                "hit_2pct": values.get("hit_2pct", 0),
                "stops": values.get("stops", 0),
                "lesson": values.get("learning_note", ""),
            }
            for family, values in stats.items()
        ]
    lines = []
    for profile in profiles[:4]:
        family = str(profile.get("strategy_family") or "estrategia")
        bias = str(profile.get("bias") or "learning")
        alerts = int(profile.get("alerts", 0) or 0)
        lesson = str(profile.get("lesson") or "")
        lines.append(f"{family}: sesgo {bias}, {alerts} alerta(s). {lesson}")
    return " ".join(lines)


def _summarize_research_queue() -> str:
    brief = _load_json(BRIEF_PATH)
    lab_rows = brief.get("strategy_lab") or []
    if isinstance(lab_rows, list) and lab_rows:
        lines = []
        for row in lab_rows[:4]:
            family = str(row.get("strategy_family") or "-")
            state = str(row.get("lab_state") or "-")
            decision = str(row.get("lab_decision") or "")
            rule = str(row.get("experiment_rule") or "")
            lines.append(f"{family}: estado {state}. {decision} Regla: {rule}")
        return " ".join(lines)
    rows = brief.get("research_queue") or []
    if not rows:
        return "No hay experimentos nuevos listos. Roxy seguira recolectando datos antes de cambiar la estrategia."
    lines = []
    for row in rows[:4]:
        family = str(row.get("strategy_family") or "-")
        priority = str(row.get("priority") or "-")
        idea = str(row.get("idea") or "")
        rule = str(row.get("rule") or "")
        lines.append(f"{family}: prioridad {priority}. {idea} Regla: {rule}")
    return " ".join(lines)


def _extract_symbol(query: str) -> str | None:
    words = [word.strip(".,:;!?()[]{}").upper() for word in query.split()]
    aliases = {"APPLE": "AAPL", "APOL": "AAPL", "NVIDIA": "NVDA", "TESLA": "TSLA", "MICROSOFT": "MSFT"}
    for word in words:
        if word in aliases:
            return aliases[word]
        if 1 <= len(word) <= 6 and word.isalpha() and word not in {"ROXY", "DIME", "QUE", "COMO", "POR"}:
            return word
    return None


def _is_position_sizing_query(query: str) -> bool:
    lq = query.lower()
    return any(
        term in lq
        for term in (
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
        )
    )


def _is_structured_account_query(query: str) -> bool:
    lq = query.lower()
    return any(
        term in lq
        for term in (
            "estado de cuenta",
            "estado cuenta",
            "estado de portafolio",
            "estado portfolio",
            "riesgo de portfolio",
            "riesgo de portafolio",
            "posiciones abiertas",
            "mis posiciones",
            "account status",
            "portfolio status",
            "portfolio risk",
            "open positions",
            "my positions",
            "position exposure",
        )
    )


def _account_reply(query: str, user: Optional[str]) -> str | None:
    lq = query.lower()
    if _is_position_sizing_query(query):
        return None
    if _is_structured_account_query(query):
        return None
    if any(term in lq for term in ("balance", "equity", "cuenta", "capital")):
        if user:
            try:
                eq = storage.get_account_equity(user)
                return f"Cuenta {user}: equity simulada {eq:.2f}."
            except Exception:
                return "No pude leer el equity de la cuenta en este momento."
        return "Necesitas iniciar sesion para que Roxy lea tu cuenta simulada."

    if any(term in lq for term in ("posicion", "posiciones", "position", "open")):
        if user:
            try:
                pos = storage.get_open_positions(user)
                if not pos:
                    return "No tienes posiciones simuladas abiertas."
                summaries = [f"{item[3]}: {item[4]} unidades a {item[5]}" for item in pos[:5]]
                return "Posiciones abiertas: " + ", ".join(summaries)
            except Exception:
                return "No pude leer las posiciones abiertas en este momento."
        return "Necesitas iniciar sesion para que Roxy lea tus posiciones."
    return None


def generate_reply_state(query: str, user: Optional[str] = None, session_id: Optional[str] = None) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        response = RoxyInteractiveBrain(BRIEF_PATH, MEMORY_PATH).generate_reply(q, user=user, session_id=session_id)
        state = response.as_dict()
        state["events"] = build_voice_events(q, response)
        return state

    account = _account_reply(q, user)
    if account:
        response = RoxyBrainReply(
            reply=account,
            intent="account",
            safety_level="guarded",
            suggested_actions=("ask_positions", "ask_latest_opportunity"),
        )
        state = {
            "reply": account,
            "intent": "account",
            "voice_style": "female_es_latam",
            "avatar_state": "speaking",
            "emotion": "focused",
            "should_speak": True,
            "needs_live_source": False,
            "safety_level": "guarded",
            "priority": "normal",
            "suggested_actions": ["ask_positions", "ask_latest_opportunity"],
        }
        state["events"] = build_voice_events(q, response)
        return state

    try:
        response = RoxyInteractiveBrain(BRIEF_PATH, MEMORY_PATH).generate_reply(q, user=user, session_id=session_id)
        state = response.as_dict()
        state["events"] = build_voice_events(q, response)
        return state
    except Exception:
        pass

    lq = q.lower()
    if any(term in lq for term in ("hola", "hello", "hi", "hey")):
        return (
            f"Hola {user or ''}. Soy Roxy. Puedo leerte oportunidades, explicar estrategias, "
            "resumir aprendizaje y revisar tu cuenta simulada."
        ).strip()

    if any(term in lq for term in ("aprendizaje", "aprendiendo", "learning", "memoria")):
        return _summarize_learning()

    if any(term in lq for term in ("laboratorio", "experimento", "estrategia nueva", "mejora")):
        return _summarize_research_queue()

    if any(term in lq for term in ("alerta", "oportunidad", "resumen", "comprar", "compra", "call")):
        symbol = _extract_symbol(q)
        return _summarize_opportunity(_latest_opportunity(symbol))

    if any(term in lq for term in ("ayuda", "help", "que puedes")):
        return (
            "Puedes preguntarme: cual es la mejor oportunidad, que estas aprendiendo, "
            "que experimento sigue, como esta AAPL, o leer posiciones y cuenta simulada."
        )

    symbol = _extract_symbol(q)
    if symbol:
        return _summarize_opportunity(_latest_opportunity(symbol))

    return (
        "No encontre una lectura especifica para esa pregunta. Prueba con: "
        "resumen, aprendizaje, laboratorio, alertas, o un simbolo como AAPL."
    )


def generate_reply(query: str, user: Optional[str] = None, session_id: Optional[str] = None) -> str:
    state = generate_reply_state(query, user=user, session_id=session_id)
    if isinstance(state, dict):
        return str(state.get("reply") or "")
    return str(state or "")


def get_session_state(session_id: Optional[str], limit: int = 8) -> dict[str, Any]:
    return RoxyConversationMemory().session_state(session_id, limit=limit)


def session_overview_from_memory(overview: dict[str, Any], language: str = "es") -> dict[str, Any]:
    language = "en" if str(language or "").lower().startswith("en") else "es"
    overview = overview if isinstance(overview, dict) else {}
    rows = overview.get("recent_sessions") if isinstance(overview.get("recent_sessions"), list) else []
    clean_rows = [row for row in rows if isinstance(row, dict)]
    session_count = int(overview.get("session_count", len(clean_rows)) or 0)
    total_turns = int(overview.get("total_turns", 0) or 0)
    if not clean_rows:
        summary = (
            "There are no saved Roxy sessions yet. Start a conversation and I will remember the context."
            if language == "en"
            else "Todavia no hay sesiones guardadas de Roxy. Inicia una conversacion y recordare el contexto."
        )
    else:
        parts = []
        for row in clean_rows[:5]:
            session_id = str(row.get("session_id") or "local")
            turns = int(row.get("turn_count", 0) or 0)
            intent = str(row.get("last_intent") or "-")
            symbol = str(row.get("active_symbol") or "").strip()
            market = str(row.get("active_market") or "").strip()
            timeframe = speakable_timeframe(str(row.get("active_timeframe") or "").strip(), language)
            context = " ".join(part for part in (symbol, market, timeframe) if part)
            handoff_ready = bool(str(row.get("action_url") or "").strip())
            if language == "en":
                details = [f"{turns} turn(s)"]
                if context:
                    details.append(context)
                details.append(f"last topic {intent}")
                if handoff_ready:
                    details.append("trade handoff ready")
                parts.append(f"{session_id}: {', '.join(details)}")
            else:
                details = [f"{turns} turno(s)"]
                if context:
                    details.append(context)
                details.append(f"ultimo tema {intent}")
                if handoff_ready:
                    details.append("handoff trade listo")
                parts.append(f"{session_id}: {', '.join(details)}")
        prompt = (
            "Say: Roxy, switch session to "
            if language == "en"
            else "Di: Roxy, cambia a sesion "
        )
        first_session = str(clean_rows[0].get("session_id") or "local")
        summary = (
            f"Recent sessions: {'; '.join(parts)}. {prompt}{first_session}."
            if language == "en"
            else f"Sesiones recientes: {'; '.join(parts)}. {prompt}{first_session}."
        )
    return {
        "language": language,
        "session_count": session_count,
        "total_turns": total_turns,
        "recent_sessions": clean_rows[: max(1, min(len(clean_rows), 20))],
        "speakable_summary": summary,
        "suggested_actions": ["switch_session", "session_brief"],
    }


def get_session_overview(limit: int = 8, language: str = "es") -> dict[str, Any]:
    overview = RoxyConversationMemory().overview(limit=limit)
    return session_overview_from_memory(overview, language=language)


def session_brief_from_state(state: dict[str, Any], language: str = "es") -> dict[str, Any]:
    language = "en" if str(language or "").lower().startswith("en") else "es"
    state = state if isinstance(state, dict) else {}
    context = state.get("active_context") if isinstance(state.get("active_context"), dict) else {}
    actions = context.get("next_best_actions") if isinstance(context.get("next_best_actions"), list) else []
    actions = [str(action) for action in actions if action][:3]
    turn_count = int(state.get("turn_count", 0) or 0)
    session_id = str(state.get("session_id") or "local")
    intent = str(context.get("active_intent") or state.get("last_intent") or "-")
    symbol = str(context.get("active_symbol") or "-")
    market = str(context.get("active_market") or "").strip()
    timeframe = speakable_timeframe(str(context.get("active_timeframe") or "").strip(), language)
    action_url = str(context.get("action_url") or "").strip()
    action_label = str(context.get("action_label") or "").strip()
    action_kind = str(context.get("action_kind") or "").strip()
    safety = str(context.get("last_safety_level") or state.get("last_safety_level") or "-")
    needs_confirmation = bool(context.get("needs_confirmation"))
    next_actions = actions or ["ask_market_summary", "ask_latest_opportunity"]
    market_context = ""
    if market or timeframe:
        if language == "en":
            market_context = f" Market: {market or '-'}, timeframe: {timeframe or '-'}."
        else:
            market_context = f" Mercado: {market or '-'}, marco: {timeframe or '-'}."
    handoff_context = ""
    if action_url:
        if language == "en":
            label = action_label or "Open Roxy Trade"
            kind = f" ({action_kind})" if action_kind else ""
            handoff_context = f" Operational handoff is ready: {label}{kind}."
        else:
            label = action_label or "Abrir Roxy Trade"
            kind = f" ({action_kind})" if action_kind else ""
            handoff_context = f" Handoff operativo listo: {label}{kind}."
    if turn_count <= 0:
        summary = (
            "There is no saved context for this session yet. Ask one market or opportunity question to start memory."
            if language == "en"
            else "Todavia no hay contexto guardado para esta sesion. Haz una pregunta de mercado u oportunidad para iniciar memoria."
        )
    elif language == "en":
        confirmation = " Confirmation is required before any sensitive action." if needs_confirmation else ""
        summary = (
            f"Session context: {turn_count} saved turn(s). Active symbol: {symbol}. "
            f"Topic: {intent}. Safety: {safety}.{market_context}{handoff_context} "
            f"Next: {', '.join(next_actions[:2])}.{confirmation}"
        )
    else:
        confirmation = " Requiere confirmacion antes de cualquier accion sensible." if needs_confirmation else ""
        summary = (
            f"Contexto de sesion: {turn_count} turno(s) guardado(s). Simbolo activo: {symbol}. "
            f"Tema: {intent}. Seguridad: {safety}.{market_context}{handoff_context} "
            f"Siguiente: {', '.join(next_actions[:2])}.{confirmation}"
        )
    return {
        "session_id": session_id,
        "turn_count": turn_count,
        "language": language,
        "speakable_summary": summary,
        "active_context": context,
        "suggested_actions": next_actions,
        "action_url": action_url,
        "action_label": action_label,
        "action_kind": action_kind,
    }


def get_session_brief(session_id: Optional[str], language: str = "es", limit: int = 8) -> dict[str, Any]:
    state = get_session_state(session_id, limit=limit)
    return session_brief_from_state(state, language=language)


def get_user_profile(user: Optional[str]) -> dict[str, Any]:
    return RoxyUserProfile().read(user)


def update_user_profile(user: Optional[str], updates: dict[str, Any]) -> dict[str, Any]:
    return RoxyUserProfile().update(user, updates)


def get_knowledge_sources() -> list[dict[str, Any]]:
    return list_knowledge_sources()


def record_feedback(feedback: dict[str, Any]) -> dict[str, Any]:
    return RoxyFeedbackMemory().record(feedback)


def get_feedback_summary(user: Optional[str] = None) -> dict[str, Any]:
    return RoxyFeedbackMemory().summary(user=user)


def get_learning_snapshot(user: Optional[str] = None, session_id: Optional[str] = None) -> dict[str, Any]:
    return RoxyInteractiveBrain(BRIEF_PATH, MEMORY_PATH).learning_snapshot(user=user, session_id=session_id)
