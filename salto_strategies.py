from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd


SALTO_PREFIX = "Salto"


@dataclass(frozen=True)
class SaltoStrategyDefinition:
    key: str
    family: str
    headline: str
    works_when: str
    entry: str
    avoid: str
    option_note: str
    practice: str
    requirements: tuple[str, ...] = ()
    confirmation_timeframes: tuple[str, ...] = ()
    direction: str = "bullish"


SALTO_STRATEGIES: tuple[SaltoStrategyDefinition, ...] = (
    SaltoStrategyDefinition(
        key="SALTO_EMA_HOURS",
        family="Salto por cruce de EMA en horas",
        headline="Buscar salto de continuidad cuando el canal alcista inicia y el precio respeta EMA9.",
        works_when="Canal alcista en formacion, SMA20>SMA40, cierre tocando EMA9 y confirmacion 2h/4h.",
        entry="Entrada solo cerca del cierre de sesion, idealmente 5 minutos antes, si 15m no invalida y 1h/4h sostienen tendencia.",
        avoid="Evitar si EMA9 queda pegada a SMA20 sin espacio, si el canal esta viejo o si el cierre pierde SMA20.",
        option_note="Calls solo paper/manual hasta validar DTE, spread, delta y que el max loss quepa en 1R.",
        practice="Marca EMA9, SMA20 y SMA40; busca cierres sobre EMA9 dentro de un canal que apenas empieza.",
        requirements=(
            "Formacion de canal alcista",
            "Precio cierra tocando EMA9",
            "SMA20 y SMA40 ordenadas en canal sostenido",
            "Distancia sana entre EMA9 y SMA20",
            "Canal apenas iniciando",
            "Confirmacion en 2h y 4h",
            "Entrada solo cerca del cierre",
        ),
        confirmation_timeframes=("15m", "1h", "2h", "4h"),
        direction="bullish",
    ),
    SaltoStrategyDefinition(
        key="SALTO_MA_DISTANCE",
        family="Salto por distancia entre medias moviles",
        headline="Detectar fuerza cuando las medias se separan por impulso y el precio cierra sobre la media clave.",
        works_when="Precio avanza continuo, SMA20 se separa de SMA40, SMA40 de SMA100 y hay espacio entre canal y tendencia.",
        entry="Comprar cerca del cierre si 1h/2h/4h mantienen osciladores con espacio y 15m confirma separacion.",
        avoid="Evitar si el movimiento ya esta demasiado extendido sobre SMA20 o si las medias se separan sin volumen.",
        option_note="Preferir paper en opciones si la prima ya descuenta el salto o el break-even queda lejos.",
        practice="Mide la distancia entre SMA20/SMA40/SMA100 y verifica que el precio no este persiguiendo una vela vertical.",
        requirements=(
            "Precio sube o baja de forma continua",
            "Las medias se separan por fuerza del movimiento",
            "Precio cierra sobre la media movil clave",
            "Oscilador superior cierra o muestra debilidad",
            "En 1h/2h/4h cierran osciladores",
            "15m confirma separacion entre canal y tendencia",
            "Entrada solo cerca del cierre",
        ),
        confirmation_timeframes=("15m", "1h", "2h", "4h"),
        direction="continuation",
    ),
    SaltoStrategyDefinition(
        key="SALTO_ATH_BREAKOUT",
        family="Salto por ruptura de maximos historicos",
        headline="Buscar ruptura fuerte cuando el precio rompe maximos y se mantiene sobre resistencia.",
        works_when="Precio rompe maximo reciente/historico, cierra sobre resistencia y Bollinger deja espacio para expansion.",
        entry="Entrada cerca del cierre despues de confirmar que la ruptura no vuelve bajo resistencia.",
        avoid="Evitar rupturas sin volumen, velas que cierran debajo del nivel roto o entradas pegadas a extension extrema.",
        option_note="Calls solo si el spread es bajo y el contrato permite salida rapida si falla la ruptura.",
        practice="Dibuja resistencia de 60 velas, espera cierre encima y usa esa zona como referencia de invalidez.",
        requirements=(
            "Precio rompe maximos o minimos historicos",
            "Ruptura se mantiene sobre resistencia",
            "Canal alineado con separacion de medias",
            "Osciladores abiertos con espacio para salto",
            "Precio cierra sobre la linea de resistencia",
            "Entrada solo cerca del cierre",
        ),
        confirmation_timeframes=("15m", "1h", "2h", "4h"),
        direction="breakout",
    ),
    SaltoStrategyDefinition(
        key="SALTO_EMA_2H_BEARISH",
        family="Salto por cruce de EMA en 2 horas",
        headline="Detectar salto bajista cuando EMA9 cruza en canal bajista con espacio de Bollinger.",
        works_when="Canal bajista, EMA9 cruza contra SMA20/SMA40, precio debajo de EMA9 en 4h y 1h/4h confirman debilidad.",
        entry="Para puts o espera defensiva, actuar cerca del cierre solo si el precio cierra en el cruce y no recupera EMA9.",
        avoid="Evitar puts si el precio recupera EMA9/SMA20 o si Bollinger no tiene espacio para continuar.",
        option_note="Puts solo con liquidez y perdida maxima definida; si no cabe en 1R, paper.",
        practice="Estudia el cruce EMA9/SMA20 en tendencia bajista y exige confirmacion de 1h y 4h.",
        requirements=(
            "Formacion de canal bajista",
            "EMA9 cruzando SMA",
            "Precio cierra en el cruce de EMA",
            "Debe tener espacio en Bollinger para saltar",
            "Confirmacion con 1h y 4h",
            "Precio debajo de EMA9 en 4h",
            "Entrada solo cerca del cierre",
        ),
        confirmation_timeframes=("15m", "1h", "2h", "4h"),
        direction="bearish",
    ),
    SaltoStrategyDefinition(
        key="SALTO_CHANNEL_CHANGE",
        family="Salto para cambio de canal",
        headline="Buscar transicion cuando un canal deja de hacer nuevos maximos o minimos y las medias muestran debilidad.",
        works_when="Canal alcista o bajista pierde continuidad, EMA9/SMA20 se debilitan y medias de canal se separan de la tendencia.",
        entry="Esperar confirmacion cerca del cierre; operar solo cuando el cambio de canal tenga stop medible.",
        avoid="Evitar anticipar el giro si el canal sigue haciendo maximos/minimos nuevos o si 15m no confirma.",
        option_note="Opciones en modo paper hasta comprobar que el cambio de canal no es ruido de rango.",
        practice="Compara los ultimos pivotes del canal y revisa si las medias cortas dejan de sostener el movimiento.",
        requirements=(
            "Precio forma canal bajista o alcista",
            "Confirmar si el canal es de corto o largo plazo",
            "Canal deja de formar nuevos maximos o minimos",
            "Medias del canal se separan de las de tendencia",
            "EMA9/SMA20 presentan debilidad",
            "Entrada solo cerca del cierre",
        ),
        confirmation_timeframes=("15m", "1h", "2h", "4h"),
        direction="transition",
    ),
    SaltoStrategyDefinition(
        key="BUSQUEDA_REBOTE_MEDIA",
        family="Busqueda de media movil con confirmacion",
        headline="Buscar rebote controlado cuando el precio toca SMA20/SMA40 o EMA9 y confirma recuperacion.",
        works_when="Tendencia mayor no bajista, precio sobre SMA200, toque/rebote en media y 15m/1h confirman.",
        entry="Esperar cierre verde sobre EMA9/SMA20 o SMA40; comprar solo si volumen, riesgo y target 2% son validos.",
        avoid="Evitar una media aislada, entradas bajo SMA200, vela llena, exposicion fuera de Bollinger o rebote sin confirmacion.",
        option_note="Calls solo si la accion ya tiene setup BUY/WATCH confirmado; no comprar prima por simple toque de media.",
        practice="Marca la zona EMA9/SMA20/SMA40, espera toque, rechazo y cierre limpio; mide stop bajo la media/soporte.",
        requirements=(
            "Tendencia mayor no debe estar bajista",
            "Precio sobre SMA200 o recuperandola con cierre fuerte",
            "Toque o rebote en EMA9/SMA20/SMA40",
            "Cierre verde sobre la media que actua como piso",
            "Volumen relativo acompanando",
            "15m confirma entrada y 1h sostiene tendencia",
            "Stop medible y target minimo 2% viable",
        ),
        confirmation_timeframes=("15m", "1h", "2h", "4h"),
        direction="rebound",
    ),
    SaltoStrategyDefinition(
        key="PATRON_IMPARABLE_EMA9",
        family="Patron imparable EMA9",
        headline="Buscar rebote o continuacion cuando EMA9 guia el movimiento y el oscilador deja espacio.",
        works_when="Precio respeta EMA9/SMA20, SMA20/SMA40 no se quiebran, SMA200 no bloquea y Bollinger deja espacio.",
        entry="Esperar cierre sobre EMA9 con 15m/1h alineados; en lateralidad, solo operar rebote en soporte o ruptura limpia.",
        avoid="Evitar si SMA20 esta lateral/invertida sin recuperacion, si EMA9 cruza bajista o si el movimiento es manipulacion sin confirmacion.",
        option_note="Opciones solo si el setup esta confirmado; no comprar prima cuando el patron sigue en fase de manipulacion/lateralidad.",
        practice="Marca EMA9, SMA20, SMA40, SMA200, bandas y soporte/resistencia; identifica si la fase es lateral, invertida o bajista.",
        requirements=(
            "EMA9 guia o recupera el movimiento",
            "SMA20/SMA40 sostienen el canal o muestran recuperacion",
            "SMA200 no bloquea compras",
            "Bollinger deja espacio para continuidad",
            "Oscilador superior/inferior no esta cerrando el movimiento",
            "Evitar manipulacion sin cierre confirmado",
            "15m y 1h deben confirmar antes de operar",
        ),
        confirmation_timeframes=("15m", "1h", "4h"),
        direction="structure",
    ),
)

SALTO_STRATEGY_FAMILIES = tuple(item.family for item in SALTO_STRATEGIES)
SALTO_BY_KEY = {item.key: item for item in SALTO_STRATEGIES}
SALTO_BY_FAMILY = {item.family: item for item in SALTO_STRATEGIES}
SALTO_KEY_TO_FAMILY = {item.key: item.family for item in SALTO_STRATEGIES}

EXTERNAL_STRATEGY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Finviz: Triangulo ascendente", ("triangle asc", "triangulo asc", "triangle ascending")),
    ("Finviz: Triangulo descendente", ("triangle desc", "triangulo desc", "triangle descending")),
    ("Finviz: Triangulo", ("triangle", "triangulo")),
    ("Finviz: Cuna alcista", ("wedge up", "wedge asc", "cuna alcista")),
    ("Finviz: Cuna bajista", ("wedge down", "cuna bajista")),
    ("Finviz: Canal alcista", ("channel up", "canal alcista")),
    ("Finviz: Canal bajista", ("channel down", "canal bajista")),
    ("Finviz: Canal", ("channel", "canal")),
    ("Finviz: Doble piso", ("double bottom", "doble piso")),
    ("Finviz: Doble techo", ("double top", "doble techo")),
    ("Finviz: Multiples pisos", ("multiple bottom", "multiples pisos")),
    ("Finviz: Multiples techos", ("multiple top", "multiples techos")),
    ("Finviz: Cabeza y hombros", ("head&shoulders", "head and shoulders", "cabeza y hombros")),
    ("Finviz: Soporte de tendencia", ("tl supp", "trendline support", "soporte tendencia")),
    ("Finviz: Resistencia de tendencia", ("tl resist", "trendline resistance", "resistencia tendencia")),
    ("Finviz: Soporte/Resistencia horizontal", ("horizontal s/r", "horizontal sr")),
    ("Estrategia: Cruce EMA 9/21", ("ema 9/21", "ema9/21", "cruce ema", "ema cross")),
    ("Estrategia: Momentum", ("momentum", "fuerza relativa")),
    ("Estrategia: Volumen", ("volumen", "volume", "unusual volume")),
    ("Estrategia: Breakout", ("breakout", "ruptura", "rompiendo")),
    ("Estrategia: Pullback", ("pullback", "retroceso", "rebote")),
    ("Estrategia: Reversal", ("reversal", "reversion")),
    ("Estrategia: Soporte/Resistencia", ("soporte/resistencia", "support/resistance", "resistance", "support")),
    ("Estrategia: Riesgo 1R", ("riesgo 1r", "1r", "risk 1r")),
)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def load_teacher_playbook(path: str | Path = "training_videos/roxy_teacher_playbook.json") -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent / p
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text())
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def normalize_salto_family(value: Any) -> str | None:
    text = safe_text(value)
    if not text:
        return None
    upper = text.upper()
    if upper in SALTO_KEY_TO_FAMILY:
        return SALTO_KEY_TO_FAMILY[upper]
    for family in SALTO_STRATEGY_FAMILIES:
        if upper == family.upper():
            return family
    if "MAXIMOS" in upper or "ATH" in upper or "BREAKOUT" in upper:
        return SALTO_KEY_TO_FAMILY["SALTO_ATH_BREAKOUT"]
    if "DISTANCIA" in upper or "MA_DISTANCE" in upper:
        return SALTO_KEY_TO_FAMILY["SALTO_MA_DISTANCE"]
    if "2H" in upper or "2 HORAS" in upper:
        return SALTO_KEY_TO_FAMILY["SALTO_EMA_2H_BEARISH"]
    if "CAMBIO" in upper and "CANAL" in upper:
        return SALTO_KEY_TO_FAMILY["SALTO_CHANNEL_CHANGE"]
    if "PATRON" in upper or "IMPARABLE" in upper:
        return SALTO_KEY_TO_FAMILY["PATRON_IMPARABLE_EMA9"]
    if "BUSQUEDA" in upper or "BÚSQUEDA" in upper or "REBOTE" in upper:
        return SALTO_KEY_TO_FAMILY["BUSQUEDA_REBOTE_MEDIA"]
    if "EMA" in upper and ("HORA" in upper or "HOURS" in upper):
        return SALTO_KEY_TO_FAMILY["SALTO_EMA_HOURS"]
    if "EMA9" in upper:
        return SALTO_KEY_TO_FAMILY["PATRON_IMPARABLE_EMA9"]
    return None


def normalize_external_strategy_family(value: Any) -> str | None:
    normalized = safe_text(value).lower()
    if not normalized:
        return None
    salto_family = normalize_salto_family(value)
    if salto_family:
        return salto_family
    for family, needles in EXTERNAL_STRATEGY_ALIASES:
        if any(needle in normalized for needle in needles):
            return family
    return None


def strategy_family_for_opportunity(row: Mapping[str, Any] | dict[str, Any]) -> str:
    """Classify one opportunity without merging unrelated strategies."""
    if not isinstance(row, Mapping):
        return "Sin estrategia definida"
    direct_fields = (
        "strategy_family",
        "salto_family",
        "learned_strategy",
        "pattern_strategy",
        "canonical_pattern",
        "finviz_signal",
        "source_signal",
        "trigger_setup",
        "trend_setup",
        "setup",
        "strategy",
        "signal",
        "trade_decision",
    )
    for field in direct_fields:
        family = normalize_external_strategy_family(row.get(field))
        if family:
            return family
    joined = " ".join(safe_text(row.get(field)) for field in direct_fields if safe_text(row.get(field)))
    return normalize_external_strategy_family(joined) or "Sin estrategia definida"


def strategy_score_for_opportunity(row: Mapping[str, Any] | dict[str, Any]) -> float:
    if not isinstance(row, Mapping):
        return 0.0
    for field in (
        "roxy_priority_score",
        "alert_readiness_score",
        "readiness",
        "confidence",
        "strategy_score",
        "confluence_score",
        "ai_score",
        "score",
        "trend_score",
    ):
        value = safe_float(row.get(field))
        if value is not None:
            return max(0.0, min(100.0, value))
    return 0.0


def _opportunity_records(opportunities: Any) -> list[dict[str, Any]]:
    if isinstance(opportunities, pd.DataFrame):
        return opportunities.to_dict("records")
    if isinstance(opportunities, Mapping):
        return [dict(opportunities)]
    if isinstance(opportunities, Iterable) and not isinstance(opportunities, (str, bytes)):
        return [dict(item) for item in opportunities if isinstance(item, Mapping)]
    return []


def separate_opportunities_by_strategy(
    opportunities: Any,
    *,
    limit_per_strategy: int = 5,
) -> list[dict[str, Any]]:
    """Group opportunities by setup family and keep each strategy independent."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in _opportunity_records(opportunities):
        family = strategy_family_for_opportunity(row)
        row["_strategy_family"] = family
        row["_strategy_score"] = strategy_score_for_opportunity(row)
        grouped.setdefault(family, []).append(row)

    groups: list[dict[str, Any]] = []
    for family, rows in grouped.items():
        ranked = sorted(
            rows,
            key=lambda item: (
                -float(item.get("_strategy_score") or 0.0),
                safe_text(item.get("symbol") or item.get("ticker")),
            ),
        )
        best = ranked[0] if ranked else {}
        scores = [float(item.get("_strategy_score") or 0.0) for item in ranked]
        groups.append(
            {
                "strategy_family": family,
                "count": len(ranked),
                "best": best,
                "best_score": float(best.get("_strategy_score") or 0.0),
                "avg_score": (sum(scores) / len(scores)) if scores else 0.0,
                "opportunities": ranked[: max(1, int(limit_per_strategy))],
            }
        )
    return sorted(groups, key=lambda group: (-float(group["best_score"]), safe_text(group["strategy_family"])))


def best_opportunities_by_strategy(opportunities: Any, *, limit: int = 12) -> list[dict[str, Any]]:
    best_rows: list[dict[str, Any]] = []
    for rank, group in enumerate(separate_opportunities_by_strategy(opportunities, limit_per_strategy=1), start=1):
        row = dict(group.get("best") or {})
        row["_strategy_rank"] = rank
        row["_strategy_family"] = group.get("strategy_family")
        row["_strategy_best_score"] = group.get("best_score")
        row["_strategy_group_count"] = group.get("count")
        best_rows.append(row)
    return best_rows[: max(1, int(limit))]


def _pct_distance(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None or reference == 0:
        return None
    return ((value / reference) - 1.0) * 100.0


def _slope(series: pd.Series, periods: int = 8) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) <= periods:
        return None
    old = float(clean.iloc[-(periods + 1)])
    new = float(clean.iloc[-1])
    return _pct_distance(new, old)


def _crossed(fast: pd.Series, slow: pd.Series, *, direction: str) -> bool:
    if len(fast) < 2 or len(slow) < 2:
        return False
    prev_fast = safe_float(fast.iloc[-2])
    prev_slow = safe_float(slow.iloc[-2])
    last_fast = safe_float(fast.iloc[-1])
    last_slow = safe_float(slow.iloc[-1])
    if None in (prev_fast, prev_slow, last_fast, last_slow):
        return False
    if direction == "above":
        return bool(prev_fast <= prev_slow and last_fast > last_slow)
    return bool(prev_fast >= prev_slow and last_fast < last_slow)


def _touch_event_count(price: pd.Series, reference: pd.Series, *, tolerance_pct: float = 0.8, lookback: int = 60) -> int:
    price_clean = pd.to_numeric(price, errors="coerce")
    reference_clean = pd.to_numeric(reference, errors="coerce")
    frame = pd.DataFrame({"price": price_clean, "reference": reference_clean}).dropna().tail(lookback)
    if frame.empty:
        return 0
    distance = ((frame["price"] / frame["reference"]) - 1.0).abs() * 100.0
    touches = distance <= tolerance_pct
    touch_starts = touches & ~touches.shift(1, fill_value=False)
    return int(touch_starts.sum())


def _status(active: bool, watch: bool) -> str:
    if active:
        return "ACTIVE"
    if watch:
        return "WATCH"
    return "BLOCKED"


def detect_salto_setups(chart_df: pd.DataFrame, setup: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if chart_df.empty:
        return []

    data = chart_df.dropna(subset=["close"]).copy()
    if data.empty:
        return []
    setup = setup or {}
    last = data.iloc[-1]
    prev = data.iloc[-2] if len(data) >= 2 else last

    close = safe_float(last.get("close"))
    open_ = safe_float(last.get("open")) or close
    low = safe_float(last.get("low"))
    ema9 = safe_float(last.get("ema9"))
    sma20 = safe_float(last.get("sma20"))
    sma40 = safe_float(last.get("sma40"))
    sma100 = safe_float(last.get("sma100"))
    sma200 = safe_float(last.get("sma200"))
    upper = safe_float(last.get("bb_upper"))
    lower = safe_float(last.get("bb_lower"))
    resistance = safe_float(last.get("range_high_60"))
    support = safe_float(last.get("range_low_60"))
    rel_vol = safe_float(last.get("relative_volume"))
    rsi14 = safe_float(last.get("rsi14"))
    macd_hist = safe_float(last.get("macd_hist"))
    prev_macd_hist = safe_float(prev.get("macd_hist"))

    has_ma = close is not None and all(value is not None for value in (ema9, sma20, sma40, sma100, sma200))
    bullish_stack = bool(has_ma and sma20 > sma40 > sma100 > sma200)
    bearish_stack = bool(has_ma and sma20 < sma40 < sma100 < sma200)
    close_above_200 = bool(close is not None and sma200 is not None and close > sma200)
    green_close = bool(close is not None and open_ is not None and close >= open_)
    near_ema9 = abs(_pct_distance(close, ema9) or 999.0) <= 1.0
    near_sma20 = abs(_pct_distance(close, sma20) or 999.0) <= 1.8
    near_sma40 = abs(_pct_distance(close, sma40) or 999.0) <= 1.8
    near_resistance = abs(_pct_distance(close, resistance) or 999.0) <= 2.0
    dist_20_40 = abs(_pct_distance(sma20, sma40) or 0.0)
    dist_40_100 = abs(_pct_distance(sma40, sma100) or 0.0)
    dist_close_20 = abs(_pct_distance(close, sma20) or 0.0)
    strong_volume = bool(rel_vol is not None and rel_vol >= 1.1)
    oscillator_has_upside_room = bool(rsi14 is None or rsi14 < 75)
    oscillator_confirms_up = bool(
        oscillator_has_upside_room
        and (macd_hist is None or prev_macd_hist is None or macd_hist >= prev_macd_hist or macd_hist >= 0)
    )
    oscillator_confirms_down = bool(
        rsi14 is None
        or rsi14 > 25
        or (macd_hist is not None and prev_macd_hist is not None and macd_hist <= prev_macd_hist)
    )
    breakout = bool(close is not None and resistance is not None and close > resistance)
    band_space_up = bool(close is not None and upper is not None and close < upper * 0.995)
    band_space_down = bool(close is not None and lower is not None and close > lower * 1.005)
    lower_reclaim = bool(close is not None and lower is not None and support is not None and close > support and close > lower)
    ema_cross_down = "ema9" in data.columns and "sma20" in data.columns and _crossed(data["ema9"], data["sma20"], direction="below")
    ema_cross_up = "ema9" in data.columns and "sma20" in data.columns and _crossed(data["ema9"], data["sma20"], direction="above")
    sma20_slope = _slope(data["sma20"]) if "sma20" in data.columns else None
    sma40_slope = _slope(data["sma40"]) if "sma40" in data.columns else None
    channel_high = safe_float(data["high"].tail(20).max()) if "high" in data.columns else None
    channel_low = safe_float(data["low"].tail(20).min()) if "low" in data.columns else None
    prev_channel_high = safe_float(data["high"].tail(40).head(20).max()) if "high" in data.columns and len(data) >= 40 else None
    prev_channel_low = safe_float(data["low"].tail(40).head(20).min()) if "low" in data.columns and len(data) >= 40 else None
    stopped_new_highs = bool(channel_high is not None and prev_channel_high is not None and channel_high <= prev_channel_high * 1.005)
    stopped_new_lows = bool(channel_low is not None and prev_channel_low is not None and channel_low >= prev_channel_low * 0.995)
    ema9_above_20 = bool(ema9 is not None and sma20 is not None and ema9 >= sma20)
    ema9_recovered = bool(close is not None and ema9 is not None and close >= ema9)
    ema9_touch_events = (
        _touch_event_count(data["close"], data["ema9"], tolerance_pct=0.9, lookback=80)
        if "close" in data.columns and "ema9" in data.columns
        else 0
    )
    ema9_touch_capacity = bool(ema9_touch_events <= 4)
    touched_rebound_zone = bool(
        low is not None
        and close is not None
        and any(
            level is not None and low <= level * 1.01 and close >= level * 0.995
            for level in (ema9, sma20, sma40)
        )
    )
    sma20_lateral = bool(sma20_slope is not None and abs(sma20_slope) <= 0.35)
    sma20_inverted = bool(sma20_slope is not None and sma20_slope < -0.35)
    manipulation_risk = bool(
        (near_resistance and not breakout)
        or (close is not None and upper is not None and close >= upper and not strong_volume)
        or (sma20_lateral and not strong_volume)
    )

    rows: list[dict[str, Any]] = []

    def add(key: str, active: bool, watch: bool, trigger: str, action: str, why: str, score: int) -> None:
        definition = SALTO_BY_KEY[key]
        rows.append(
            {
                "key": key,
                "family": definition.family,
                "status": _status(active, watch),
                "trigger": trigger,
                "action": action,
                "why": why,
                "score": max(0, min(100, int(score))),
                "preferred_timing": "5 minutos antes del cierre del mercado, solo si el cierre confirma.",
                "requirements": list(definition.requirements),
                "confirmation_timeframes": list(definition.confirmation_timeframes),
                "direction": definition.direction,
                "source": "salto_strategies",
            }
        )

    add(
        "SALTO_EMA_HOURS",
        active=bullish_stack and near_ema9 and green_close and bool(sma20_slope is not None and sma20_slope > 0),
        watch=bullish_stack or (bool(sma20 is not None and sma40 is not None and sma20 > sma40) and near_ema9),
        trigger="Cierre tocando EMA9 en canal alcista inicial",
        action="Esperar cierre sobre EMA9/SMA20 y confirmar 2h/4h antes de preparar entrada manual.",
        why="El salto por EMA en horas necesita canal alcista, EMA9 respetada y medias 20/40 ordenadas.",
        score=74 if bullish_stack and near_ema9 else 56 if bullish_stack else 35,
    )

    add(
        "SALTO_MA_DISTANCE",
        active=bool(
            bullish_stack
            and dist_20_40 >= 1.2
            and dist_40_100 >= 1.0
            and dist_close_20 <= 8.0
            and oscillator_confirms_up
        ),
        watch=bool((sma20 is not None and sma40 is not None and sma20 > sma40 and dist_20_40 >= 0.8) or strong_volume),
        trigger="Separacion sana entre SMA20/SMA40/SMA100",
        action="Validar que la separacion tenga volumen y que el precio no este demasiado extendido sobre SMA20.",
        why="La fuerza aparece cuando las medias se abren por impulso y los osciladores dejan espacio para continuidad.",
        score=76 if bullish_stack and dist_20_40 >= 1.2 else 54,
    )

    add(
        "SALTO_ATH_BREAKOUT",
        active=bool(breakout and green_close and (strong_volume or band_space_up) and oscillator_confirms_up),
        watch=bool((close is not None and resistance is not None and abs(_pct_distance(close, resistance) or 999.0) <= 2.0) or breakout),
        trigger="Ruptura de maximos/resistencia con cierre encima",
        action="Comprar solo si se mantiene sobre resistencia; stop debe quedar debajo de la zona rota.",
        why="El salto por ruptura exige sostenerse sobre resistencia, volumen/espacio y osciladores abiertos.",
        score=82 if breakout and strong_volume else 62 if breakout else 48,
    )

    add(
        "SALTO_EMA_2H_BEARISH",
        active=bool(
            (bearish_stack or ema_cross_down)
            and close is not None
            and ema9 is not None
            and close < ema9
            and band_space_down
            and oscillator_confirms_down
        ),
        watch=bool(ema_cross_down or bearish_stack),
        trigger="EMA9 cruza o rechaza en canal bajista",
        action="No buscar calls; para puts, exigir cierre debajo de EMA9 y confirmacion 1h/4h.",
        why="Este setup es defensivo/bajista: precio bajo EMA9 con espacio de Bollinger para continuar.",
        score=78 if ema_cross_down and band_space_down else 56 if bearish_stack else 34,
    )

    add(
        "SALTO_CHANNEL_CHANGE",
        active=bool((stopped_new_highs or stopped_new_lows) and (ema_cross_down or ema_cross_up or near_sma20)),
        watch=bool(stopped_new_highs or stopped_new_lows or near_sma20),
        trigger="El canal deja de hacer nuevos extremos y EMA9/SMA20 muestran debilidad",
        action="Esperar confirmacion del nuevo canal; no anticipar sin stop medible.",
        why="El cambio de canal requiere pivotes debilitandose y separacion entre medias de canal y tendencia.",
        score=70 if stopped_new_highs or stopped_new_lows else 46,
    )

    add(
        "BUSQUEDA_REBOTE_MEDIA",
        active=bool(
            close_above_200
            and not bearish_stack
            and touched_rebound_zone
            and green_close
            and (near_ema9 or near_sma20 or near_sma40)
            and oscillator_confirms_up
            and (strong_volume or rel_vol is None)
            and band_space_up
        ),
        watch=bool(
            close_above_200
            and not bearish_stack
            and (touched_rebound_zone or near_ema9 or near_sma20 or near_sma40)
        ),
        trigger="Busqueda/rebote en EMA9, SMA20 o SMA40 con cierre confirmado",
        action="Esperar que la media funcione como piso: cierre verde, 15m/1h alineados, volumen y stop bajo la zona.",
        why="La clase de busqueda de media exige rebote confirmado; tocar una media sin estructura no es entrada.",
        score=82 if close_above_200 and touched_rebound_zone and green_close and oscillator_confirms_up else 58,
    )

    add(
        "PATRON_IMPARABLE_EMA9",
        active=bool(
            ema9_recovered
            and ema9_above_20
            and close_above_200
            and ema9_touch_capacity
            and not manipulation_risk
            and (near_ema9 or near_sma20)
            and (strong_volume or oscillator_confirms_up)
        ),
        watch=bool(
            (ema9_recovered and not bearish_stack)
            or (near_ema9 and close_above_200)
            or (lower_reclaim and oscillator_confirms_up)
        ),
        trigger="Patron EMA9: rebote/recuperacion con oscilador y bandas",
        action=(
            "Esperar cierre sobre EMA9/SMA20 con 15m y 1h alineados; si supera 4 toques EMA9, esperar reinicio o nueva separacion."
        ),
        why="El patron imparable no opera una media aislada: exige EMA9, SMA20/SMA40, SMA200, bandas, volumen, cierre confirmado y toques EMA9 controlados.",
        score=80 if ema9_recovered and ema9_above_20 and close_above_200 and ema9_touch_capacity and not manipulation_risk else 58,
    )

    order = {"ACTIVE": 0, "WATCH": 1, "BLOCKED": 2}
    return sorted(rows, key=lambda row: (order.get(str(row["status"]), 9), -int(row["score"])))


def best_salto_setup(chart_df: pd.DataFrame, setup: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for row in detect_salto_setups(chart_df, setup):
        if row.get("status") in {"ACTIVE", "WATCH"}:
            return row
    return None


def apply_learned_strategy_brain(chart_df: pd.DataFrame, setup: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach the strongest learned class strategy to a symbol setup.

    This is Roxy's explicit learning bridge: class/video strategies stay
    separate from the raw SMA score, then enrich the trade brief with the
    best matching setup, blockers, and teaching explanation.
    """
    enriched = dict(setup or {})
    teacher_playbook = load_teacher_playbook()
    if teacher_playbook:
        enriched.setdefault("teacher_playbook_generated_at", teacher_playbook.get("generated_at"))
        enriched.setdefault("teacher_opportunity_checklist", teacher_playbook.get("opportunity_checklist") or [])
        enriched.setdefault(
            "teacher_strategy_rules",
            [
                {
                    "id": rule.get("id"),
                    "name": rule.get("name"),
                    "rule": rule.get("rule"),
                    "sources": (rule.get("sources") or [])[:4],
                }
                for rule in (teacher_playbook.get("strategy_rules") or [])[:6]
                if isinstance(rule, dict)
            ],
        )
    detections = detect_salto_setups(chart_df, enriched)
    if not detections:
        enriched.setdefault("learned_strategy_status", "NO_MATCH")
        enriched.setdefault("learned_strategy_note", "Sin estrategia aprendida detectada en esta grafica.")
        return enriched

    actionable = [row for row in detections if row.get("status") in {"ACTIVE", "WATCH"}]
    best = actionable[0] if actionable else detections[0]
    learned_status = str(best.get("status") or "BLOCKED")
    learned_family = str(best.get("family") or "")
    learned_score = safe_float(best.get("score")) or 0.0

    enriched["learned_strategy"] = learned_family
    enriched["learned_strategy_key"] = best.get("key")
    enriched["learned_strategy_status"] = learned_status
    enriched["learned_strategy_score"] = learned_score
    enriched["learned_strategy_trigger"] = best.get("trigger")
    enriched["learned_strategy_action"] = best.get("action")
    enriched["learned_strategy_reason"] = best.get("why")
    enriched["learned_strategy_requirements"] = best.get("requirements") or []
    enriched["learned_strategy_timeframes"] = best.get("confirmation_timeframes") or []
    enriched["learned_strategy_direction"] = best.get("direction")
    enriched["learned_strategy_candidates"] = detections

    if learned_status == "ACTIVE":
        enriched["strategy_family"] = learned_family
        enriched["salto_family"] = learned_family
        enriched["learned_strategy_note"] = (
            f"Roxy detecta {learned_family}: {best.get('why')} "
            f"Accion: {best.get('action')}"
        )
        base_score = safe_float(enriched.get("score")) or 0.0
        enriched["score"] = max(base_score, min(100.0, learned_score))
        if safe_text(enriched.get("signal")).upper() != "AVOID":
            enriched["signal"] = "WATCH" if learned_score < 82 else "BUY"
    elif learned_status == "WATCH":
        enriched.setdefault("strategy_family", learned_family)
        enriched.setdefault("salto_family", learned_family)
        enriched["learned_strategy_note"] = (
            f"Roxy esta vigilando {learned_family}: {best.get('action')}"
        )
        base_score = safe_float(enriched.get("score")) or 0.0
        enriched["score"] = max(base_score, min(74.0, learned_score))
    else:
        enriched["learned_strategy_note"] = (
            f"Roxy bloquea la estrategia aprendida principal: {best.get('why')}"
        )
    return enriched
