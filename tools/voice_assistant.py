from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import storage


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


def _account_reply(query: str, user: Optional[str]) -> str | None:
    lq = query.lower()
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


def generate_reply(query: str, user: Optional[str] = None) -> str:
    q = (query or "").strip()
    if not q:
        return (
            "Estoy aqui. Puedes decir: resumen, aprendizaje, laboratorio, alertas, "
            "o preguntarme por un simbolo como AAPL."
        )

    account = _account_reply(q, user)
    if account:
        return account

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
