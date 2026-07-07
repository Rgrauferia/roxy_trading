from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from roxy_knowledge_brain import default_knowledge_brain


ADVANCED_ORIGIN_TERMS = {
    "adx",
    "bollinger",
    "ema",
    "fibonacci",
    "ichimoku",
    "ict",
    "macd",
    "market profile",
    "options chain",
    "rsi",
    "smart money",
    "supertrend",
    "vwap",
    "wyckoff",
}


PLANET_KNOWLEDGE_PROFILES: dict[str, dict[str, Any]] = {
    "origen": {
        "title": "Planeta Origen",
        "role": "Fundamentos para aprender el idioma basico del trading.",
        "query": (
            "trading basics financial assets stock price buy sell gain loss risk demo account "
            "broker market order beginner education capital position size stop target watchlist"
        ),
        "categories": ("libros", "documentos-publicos", "apuntes-propios", "estrategias-internas"),
        "points": (
            "Primero se aprende vocabulario: activo, precio, comprar, vender, ganancia, perdida y riesgo.",
            "Una clase basica debe separar aprender, practicar en demo y operar dinero real.",
            "Antes de mirar una estrategia, el usuario debe entender entrada, salida, riesgo y tamano.",
            "Los ejemplos usan datos vivos solo como practica de lectura, no como senales para operar.",
        ),
        "practice": (
            "Explica el concepto con tus propias palabras.",
            "Busca un ejemplo real en una accion conocida y describe que dato estas mirando.",
            "Escribe una regla simple para evitar operar por impulso.",
        ),
        "avoid_advanced": True,
    },
    "cripto": {
        "title": "Planeta Cripto",
        "role": "Conceptos clave del mercado digital.",
        "query": (
            "cryptocurrency bitcoin ethereum blockchain wallet exchange stablecoin volatility "
            "market capitalization liquidity crypto risk beginner"
        ),
        "categories": ("libros", "documentos-publicos", "datos-mercado-api", "apuntes-propios"),
        "points": (
            "Crypto opera 24/7 y por eso el contexto de liquidez y volatilidad cambia durante el dia.",
            "El usuario debe distinguir moneda, token, wallet, exchange, stablecoin y red blockchain.",
            "La gestion del riesgo es mas estricta porque los movimientos pueden ser rapidos.",
            "Ninguna senal crypto se estudia sin entender spread, comisiones y volatilidad.",
        ),
        "practice": (
            "Compara BTC, ETH y SOL por precio, cambio y volatilidad.",
            "Identifica si el movimiento parece tranquilo, impulsivo o lateral.",
            "Describe que riesgo especial tiene operar un activo 24/7.",
        ),
        "avoid_advanced": False,
    },
    "analisis": {
        "title": "Planeta Analisis",
        "role": "Lectura de graficas, velas, volumen e indicadores.",
        "query": (
            "chart candlestick support resistance trend volume timeframe moving average EMA RSI MACD "
            "Bollinger ATR price action technical analysis"
        ),
        "categories": ("libros", "indicadores", "estrategias-internas", "backtesting"),
        "points": (
            "La grafica se lee por precio, tiempo, volumen y contexto antes de hablar de prediccion.",
            "Las velas muestran apertura, maximo, minimo y cierre; no son una garantia por si solas.",
            "Los indicadores deben confirmar contexto, no reemplazar el plan.",
            "La misma grafica cambia de significado segun el timeframe.",
        ),
        "practice": (
            "Marca apertura, cierre, maximo y minimo en una vela.",
            "Compara un timeframe corto con uno mas grande.",
            "Explica que confirma el volumen antes de usar un indicador.",
        ),
        "avoid_advanced": False,
    },
    "estrategia": {
        "title": "Planeta Estrategia",
        "role": "Reglas, riesgo, ejecucion, bitacora y backtesting.",
        "query": (
            "trading plan risk management stop loss take profit position sizing journal checklist "
            "backtesting strategy pullback breakout reversal trend following"
        ),
        "categories": ("libros", "estrategias-internas", "backtesting", "diario-de-trading"),
        "points": (
            "Una estrategia debe tener condicion de entrada, invalidacion, salida y tamano.",
            "El backtesting ayuda a separar una idea repetible de una impresion visual.",
            "La bitacora convierte errores en reglas nuevas.",
            "Una buena estrategia tambien dice cuando no operar.",
        ),
        "practice": (
            "Define entrada, stop, target y razon de invalidacion.",
            "Registra si la operacion cumplio el checklist.",
            "Compara resultado contra el plan, no contra la emocion.",
        ),
        "avoid_advanced": False,
    },
    "elite": {
        "title": "Planeta Elite",
        "role": "Consistencia, revision y mejora continua.",
        "query": (
            "trading psychology discipline consistency review performance journal trading plan "
            "process risk control portfolio backtesting improvement"
        ),
        "categories": ("libros", "diario-de-trading", "backtesting", "estrategias-internas"),
        "points": (
            "El objetivo es ejecutar un proceso repetible, no perseguir una operacion perfecta.",
            "La revision semanal identifica errores de entrada, riesgo, salida y emocion.",
            "La consistencia exige reglas, descanso, bitacora y control de tamano.",
            "Las mejoras se prueban antes de agregarse al sistema operativo.",
        ),
        "practice": (
            "Resume tres decisiones buenas y tres errores de la semana.",
            "Propone una regla nueva y pruebala en demo o backtest.",
            "Mide si la mejora reduce riesgo o solo aumenta complejidad.",
        ),
        "avoid_advanced": False,
    },
}


PLANET_CURRICULUM_LESSONS: dict[str, tuple[str, ...]] = {
    "cripto": (
        "Que es una criptomoneda?",
        "Que es blockchain?",
        "Bitcoin y oferta limitada",
        "Ethereum y contratos inteligentes",
        "Wallets: custodial vs self-custody",
        "Exchanges centralizados y descentralizados",
        "Stablecoins y riesgo de respaldo",
        "Market cap, liquidez y volumen",
        "Volatilidad crypto 24/7",
        "Fees, spread y slippage",
        "Seguridad basica y estafas comunes",
        "Como leer BTC sin operar todavia",
        "Correlacion crypto con noticias macro",
        "Plan demo crypto",
        "Examen Planeta Cripto",
    ),
    "analisis": (
        "Que es un grafico?",
        "Tipos de graficos",
        "Eje de precio y eje de tiempo",
        "Velas: apertura, maximo, minimo y cierre",
        "Cuerpo y mechas",
        "Volumen basico",
        "Tendencia alcista, bajista y lateral",
        "Soporte y resistencia basicos",
        "Rangos y rupturas simples",
        "Medias moviles como referencia",
        "RSI y momentum basico",
        "Bollinger y volatilidad basica",
        "Confirmacion entre timeframes",
        "Lectura limpia sin sobrecargar la grafica",
        "Examen Planeta Analisis",
    ),
    "estrategia": (
        "Que es una estrategia?",
        "Entrada, invalidacion y salida",
        "Stop loss operativo",
        "Target y toma parcial",
        "Relacion riesgo beneficio",
        "Tamano de posicion",
        "Checklist antes de operar",
        "Plan de trading simple",
        "Diario de trading",
        "Backtesting basico",
        "Paper trading serio",
        "Errores de ejecucion",
        "Cuando no operar",
        "Revision semanal",
        "Examen Planeta Estrategia",
    ),
    "elite": (
        "Rutina profesional",
        "Gestion de energia y descanso",
        "Revision de estadisticas",
        "Mejora de estrategia sin romper reglas",
        "Control de drawdown",
        "Plan semanal",
        "Preparacion premercado",
        "Post-market review",
        "Consistencia y paciencia",
        "Simulacion final",
        "Graduacion Roxy Academy",
    ),
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _contains_advanced_origin_term(text: str) -> bool:
    haystack = text.lower()
    return any(term in haystack for term in ADVANCED_ORIGIN_TERMS)


def _clean_snippet(text: str, *, limit: int = 180) -> str:
    snippet = " ".join(_safe_text(text).split())
    snippet = re.sub(r"\s+", " ", snippet)
    if len(snippet) > limit:
        snippet = snippet[: limit - 3].rstrip() + "..."
    return snippet


@lru_cache(maxsize=128)
def academy_planet_knowledge(planet_key: str, lesson_title: str = "", lesson_text: str = "") -> dict[str, Any]:
    key = _safe_text(planet_key).lower() or "origen"
    profile = PLANET_KNOWLEDGE_PROFILES.get(key, PLANET_KNOWLEDGE_PROFILES["origen"])
    lesson_query = " ".join(part for part in (lesson_title, lesson_text) if part)
    query = f"{profile['query']} {lesson_query}".strip()
    sources: list[dict[str, Any]] = []
    try:
        raw_sources = default_knowledge_brain().search(
            query,
            categories=profile.get("categories") or (),
            limit=10,
        )
    except Exception:
        raw_sources = []
    for item in raw_sources:
        title = _safe_text(item.get("title"))
        snippet = _clean_snippet(item.get("snippet"))
        source_text = f"{title} {snippet} {_safe_text(item.get('category'))}"
        if profile.get("avoid_advanced") and _contains_advanced_origin_term(source_text):
            continue
        sources.append(
            {
                "title": title or "Fuente local",
                "category": _safe_text(item.get("category")) or "knowledge",
                "source": _safe_text(item.get("source")),
                "snippet": snippet,
                "score": item.get("score"),
            }
        )
        if len(sources) >= 4:
            break

    return {
        "planet": key,
        "title": profile["title"],
        "role": profile["role"],
        "query": query,
        "points": list(profile["points"]),
        "practice": list(profile["practice"]),
        "sources": sources,
        "source_count": len(sources),
        "status": "READY" if sources else "NO_LOCAL_MATCH",
    }


def enrich_academy_lesson(planet_key: str, lesson: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(lesson)
    title = _safe_text(enriched.get("title"))
    lesson_text = " ".join(
        _safe_text(enriched.get(key))
        for key in ("explanation", "study", "mission", "question")
    )
    knowledge = academy_planet_knowledge(planet_key, title, lesson_text)
    deep_points = list(enriched.get("deep_points") or [])
    for point in knowledge["points"]:
        if point not in deep_points:
            deep_points.append(point)
    practice_steps = list(enriched.get("practice_steps") or [])
    for step in knowledge["practice"]:
        if step not in practice_steps:
            practice_steps.append(step)
    enriched["deep_points"] = tuple(deep_points)
    enriched["practice_steps"] = tuple(practice_steps)
    enriched["knowledge_context"] = knowledge
    return enriched


def planet_curriculum_summary(planet_key: str) -> dict[str, Any]:
    return academy_planet_knowledge(planet_key)


def planet_curriculum_lessons(planet_key: str, origin_lessons: tuple[str, ...] | list[str] | None = None) -> list[str]:
    key = _safe_text(planet_key).lower() or "origen"
    if key == "origen" and origin_lessons:
        return [str(item) for item in origin_lessons]
    return list(PLANET_CURRICULUM_LESSONS.get(key, PLANET_CURRICULUM_LESSONS["cripto"]))
