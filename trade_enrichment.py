from __future__ import annotations

from typing import Any


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def price_text(value: Any) -> str:
    number = safe_float(value)
    return f"{number:.2f}" if number is not None else "-"


def pct_text(value: Any) -> str:
    number = safe_float(value)
    return f"{number * 100:.2f}%" if number is not None else "-"


def _first_float(*values: Any) -> float | None:
    for value in values:
        number = safe_float(value)
        if number is not None:
            return number
    return None


def _card(title: str, state: str, detail: str, *, evidence: list[str] | None = None) -> dict[str, Any]:
    return {
        "title": title,
        "state": state,
        "detail": detail,
        "evidence": [item for item in (evidence or []) if safe_text(item)],
    }


def _check(label: str, state: str, detail: str, *, group: str) -> dict[str, Any]:
    return {
        "label": label,
        "state": state,
        "passed": state in {"OK", "INFO"},
        "detail": detail,
        "group": group,
    }


def _option_enrichment(option: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    option = option or {}
    checks: list[dict[str, Any]] = []
    gaps: list[str] = []
    if not option:
        gaps.append("No hay contrato de opcion validado para enriquecer la lectura de calls/puts.")
        return (
            _card(
                "Opciones",
                "INFO",
                "Sin contrato candidato; Roxy debe priorizar accion o esperar setup base.",
            ),
            checks,
            gaps,
        )

    professional_decision = safe_text(option.get("professional_decision") or option.get("option_decision")).upper()
    dte = safe_float(option.get("dte"))
    delta = safe_float(option.get("delta"))
    spread_pct = _first_float(option.get("spread_pct"))
    volume = safe_float(option.get("volume"))
    open_interest = _first_float(option.get("openInterest"), option.get("open_interest"))
    breakeven_pct = safe_float(option.get("breakeven_pct"))
    max_loss = safe_float(option.get("max_loss_per_contract"))
    greek_quality = safe_text(option.get("greek_quality"))

    metric_rows = [
        ("DTE", dte is not None and 7 <= dte <= 45, f"{dte:.0f} dias" if dte is not None else "Sin DTE"),
        ("Delta", delta is not None and 0.30 <= abs(delta) <= 0.70, f"{delta:.2f}" if delta is not None else "Sin delta"),
        (
            "Spread",
            spread_pct is not None and spread_pct <= 0.18,
            pct_text(spread_pct) if spread_pct is not None else "Sin bid/ask",
        ),
        ("Volumen", volume is not None and volume >= 50, f"{volume:.0f}" if volume is not None else "Sin volumen"),
        (
            "Open interest",
            open_interest is not None and open_interest >= 100,
            f"{open_interest:.0f}" if open_interest is not None else "Sin open interest",
        ),
        (
            "Break-even",
            breakeven_pct is not None and abs(breakeven_pct) <= 0.07,
            pct_text(breakeven_pct) if breakeven_pct is not None else "Sin break-even",
        ),
        (
            "Riesgo maximo",
            max_loss is not None and max_loss > 0,
            f"${max_loss:.2f} por contrato" if max_loss is not None else "Sin perdida maxima",
        ),
    ]
    for label, passed, detail in metric_rows:
        checks.append(_check(f"Opcion {label}", "OK" if passed else "WARN", detail, group="Opciones"))

    if delta is None or not greek_quality or "MISSING" in greek_quality.upper():
        gaps.append("Greeks incompletos: usar proveedor profesional antes de confiar en calls/puts.")

    failures = [item["label"].replace("Opcion ", "") for item in checks if item["state"] == "WARN"]
    if professional_decision == "MIRAR_CALL" and not failures:
        state = "OK"
        detail = "Contrato alineado: DTE, delta, spread, liquidez, break-even y perdida maxima pasan filtros."
    elif professional_decision in {"MIRAR_CALL", "OPTION_CANDIDATE"}:
        state = "WARN"
        detail = "Contrato interesante, pero revisar antes de operar: " + ", ".join(failures[:4])
    else:
        state = "INFO"
        detail = "La opcion no es candidata principal; usarla solo como estudio o esperar mejor contrato."
    return _card("Opciones", state, detail), checks, gaps


def build_trade_enrichment(
    *,
    symbol: str,
    market: str,
    timeframe: str,
    setup: dict[str, Any],
    confluence: dict[str, Any] | None = None,
    option: dict[str, Any] | None = None,
    memory_context: dict[str, Any] | None = None,
    strategy_family: str = "",
    decision: str = "",
    action: str = "",
    risk_pct: Any = None,
    target_pct: Any = None,
    reward_r: Any = None,
    relative_volume: Any = None,
) -> dict[str, Any]:
    """Add learned context without changing the base trade decision.

    The output is intentionally separate from `condition_checks` so new class/video
    knowledge enriches Roxy's explanation without silently overriding the core gate.
    """
    confluence = confluence or {}
    memory_context = memory_context or {}
    option = option or {}
    symbol_text = symbol.upper()
    setup_name = safe_text(setup.get("setup") or confluence.get("trigger_setup")).upper()
    signal = safe_text(setup.get("signal") or confluence.get("signal")).upper()
    close = _first_float(setup.get("close"), setup.get("entry"), confluence.get("entry"))
    open_ = safe_float(setup.get("open"))
    high = safe_float(setup.get("high"))
    low = safe_float(setup.get("low"))
    sma20 = _first_float(setup.get("sma20"), confluence.get("sma20"))
    sma40 = _first_float(setup.get("sma40"), confluence.get("sma40"))
    sma100 = _first_float(setup.get("sma100"), confluence.get("sma100"))
    sma200 = _first_float(setup.get("sma200"), confluence.get("sma200"))
    ema9 = _first_float(setup.get("ema9"), setup.get("ema_9"), confluence.get("ema9"))
    resistance = _first_float(setup.get("resistance"), setup.get("recent_high"), confluence.get("resistance"))
    support = _first_float(setup.get("support"), setup.get("recent_low"), confluence.get("support"))
    rel_vol = _first_float(relative_volume, confluence.get("relative_volume_15m"), setup.get("relative_volume"))
    spread_pct = _first_float(setup.get("spread_pct"), confluence.get("spread_pct"), option.get("spread_pct"))
    short_interest = _first_float(setup.get("short_interest_pct"), setup.get("short_float_pct"), confluence.get("short_interest_pct"))
    days_to_cover = _first_float(setup.get("days_to_cover"), confluence.get("days_to_cover"))
    gap_pct = _first_float(setup.get("gap_pct"), confluence.get("gap_pct"))
    risk_value = safe_float(risk_pct)
    target_value = safe_float(target_pct)
    reward_value = safe_float(reward_r)

    layers: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    data_gaps: list[str] = []

    if None not in (close, sma20, sma40, sma100, sma200):
        ordered_bull = bool(sma20 > sma40 > sma100 > sma200 and close > sma20)
        ordered_bear = bool(sma20 < sma40 < sma100 < sma200 or close < sma200)
        if ordered_bull:
            structure_state = "OK"
            structure_detail = "Canal/tendencia alcista limpia: precio sobre medias y 20/40/100/200 ordenadas."
        elif ordered_bear:
            structure_state = "WARN"
            structure_detail = "Estructura bajista o bajo SMA200; no perseguir compras hasta recuperar medias."
        else:
            structure_state = "INFO"
            structure_detail = "Medias mixtas; Roxy debe tratarlo como espera, lateral o setup de transicion."
        layers.append(
            _card(
                "Estructura 20/40/100/200",
                structure_state,
                structure_detail,
                evidence=[
                    f"Precio {price_text(close)}",
                    f"SMA20 {price_text(sma20)}",
                    f"SMA40 {price_text(sma40)}",
                    f"SMA100 {price_text(sma100)}",
                    f"SMA200 {price_text(sma200)}",
                ],
            )
        )
        checks.append(_check("Estructura de medias", structure_state, structure_detail, group="Tendencia"))
    else:
        data_gaps.append("Faltan medias completas 20/40/100/200 para una lectura estructural total.")

    volume_state = "INFO"
    if rel_vol is None:
        volume_detail = "Sin volumen relativo; Roxy no debe subir confianza sin confirmar participacion."
        data_gaps.append("Volumen relativo faltante.")
    elif rel_vol >= 1.1:
        volume_state = "OK"
        volume_detail = f"Volumen acompana ({rel_vol:.2f}x); hay participacion suficiente."
    elif rel_vol >= 0.8:
        volume_state = "INFO"
        volume_detail = f"Volumen aceptable pero no fuerte ({rel_vol:.2f}x)."
    else:
        volume_state = "WARN"
        volume_detail = f"Volumen debil ({rel_vol:.2f}x); esperar confirmacion antes de entrar."
    layers.append(_card("Volumen y participacion", volume_state, volume_detail))
    checks.append(_check("Volumen enriquecido", volume_state, volume_detail, group="Microestructura"))

    if spread_pct is None:
        micro_state = "INFO"
        micro_detail = "Sin spread/Level2/Time&Sales; usar orden limitada y no asumir liquidez real."
        data_gaps.append("Falta spread, Level2 o Time&Sales para validar microestructura.")
    elif spread_pct <= 0.01:
        micro_state = "OK"
        micro_detail = f"Spread estrecho ({pct_text(spread_pct)}); ejecucion mas limpia."
    elif spread_pct <= 0.05:
        micro_state = "INFO"
        micro_detail = f"Spread moderado ({pct_text(spread_pct)}); entrar solo con limite."
    else:
        micro_state = "WARN"
        micro_detail = f"Spread amplio ({pct_text(spread_pct)}); evitar market order."
    layers.append(_card("Microestructura", micro_state, micro_detail))
    checks.append(_check("Spread/Level2", micro_state, micro_detail, group="Microestructura"))

    option_card, option_checks, option_gaps = _option_enrichment(option)
    if market == "stock":
        layers.append(option_card)
        checks.extend(option_checks)
        data_gaps.extend(option_gaps)

    stats = memory_context.get("stats") or {}
    alerts = int(stats.get("alerts", 0) or 0)
    hit_2pct = int(stats.get("hit_2pct", 0) or 0)
    stops = int(stats.get("stops", 0) or 0)
    memory_bias = safe_text(memory_context.get("bias"))
    if alerts >= 3:
        hit_rate = hit_2pct / alerts
        stop_rate = stops / alerts
        if memory_bias == "positive" or (hit_rate >= 0.50 and stop_rate <= 0.35):
            expectancy_state = "OK"
            expectancy_detail = f"Memoria favorece el setup: {hit_rate:.0%} llega a 2% y {stop_rate:.0%} toca stop."
        elif memory_bias == "negative" or stop_rate >= 0.50:
            expectancy_state = "WARN"
            expectancy_detail = f"Memoria penaliza: {hit_rate:.0%} llega a 2% y {stop_rate:.0%} toca stop."
        else:
            expectancy_state = "INFO"
            expectancy_detail = f"Memoria mixta: {hit_rate:.0%} llega a 2% y {stop_rate:.0%} toca stop."
    else:
        expectancy_state = "INFO"
        expectancy_detail = "Poca muestra real; Roxy debe seguir midiendo antes de subir tamano."
    layers.append(_card("Expectativa y memoria", expectancy_state, expectancy_detail))
    checks.append(_check("Expectativa medida", expectancy_state, expectancy_detail, group="Memoria"))

    if risk_value is not None and target_value is not None:
        if risk_value <= 0.035 and target_value >= 0.02 and (reward_value or 0) >= 1.0:
            risk_state = "OK"
            risk_detail = f"Riesgo {pct_text(risk_value)}, objetivo {pct_text(target_value)}, RR {reward_value:.2f}R."
        else:
            risk_state = "WARN"
            risk_detail = f"Plan necesita ajuste: riesgo {pct_text(risk_value)}, objetivo {pct_text(target_value)}, RR {reward_value or 0:.2f}R."
    else:
        risk_state = "WARN"
        risk_detail = "Falta stop/target medible; no operar real sin definir perdida maxima."
    layers.append(_card("Riesgo y expectativa", risk_state, risk_detail))
    checks.append(_check("Riesgo enriquecido", risk_state, risk_detail, group="Riesgo"))

    candle_range = (high - low) if high is not None and low is not None and high > low else None
    candle_body = abs(close - open_) if close is not None and open_ is not None else None
    body_pct = candle_body / candle_range if candle_range and candle_body is not None else None
    extension = (close - sma20) / sma20 if close is not None and sma20 and sma20 > 0 else None
    if body_pct is not None and body_pct >= 0.75:
        discipline_state = "WARN"
        discipline_detail = "Vela llena: esperar retroceso o cierre confirmado; no entrar por FOMO."
    elif extension is not None and extension > 0.08:
        discipline_state = "WARN"
        discipline_detail = f"Precio extendido {extension:.1%} sobre SMA20; esperar pullback sano."
    else:
        discipline_state = "OK"
        discipline_detail = "Disciplina correcta: no hay senal fuerte de perseguir precio."
    layers.append(_card("Psicologia y disciplina", discipline_state, discipline_detail))
    checks.append(_check("No perseguir", discipline_state, discipline_detail, group="Psicologia"))

    squeeze_evidence = []
    squeeze_active = False
    if short_interest is not None and short_interest >= 15:
        squeeze_active = True
        squeeze_evidence.append(f"Short interest {short_interest:.1f}%")
    if days_to_cover is not None and days_to_cover >= 3:
        squeeze_active = True
        squeeze_evidence.append(f"Days to cover {days_to_cover:.1f}")
    if gap_pct is not None and gap_pct >= 0.03 and rel_vol is not None and rel_vol >= 1.5:
        squeeze_active = True
        squeeze_evidence.append(f"Gap {gap_pct:.1%} con volumen {rel_vol:.2f}x")
    if close is not None and resistance is not None and close > resistance and rel_vol is not None and rel_vol >= 1.2:
        squeeze_active = True
        squeeze_evidence.append(f"Ruptura resistencia {price_text(resistance)} con volumen")
    if squeeze_active:
        layers.append(
            _card(
                "Momentum / short squeeze",
                "OK",
                "Hay contexto de momentum; solo operar si la estructura base tambien confirma.",
                evidence=squeeze_evidence,
            )
        )
        checks.append(_check("Momentum squeeze", "OK", "Contexto activo; requiere confirmacion base.", group="Momentum"))
    else:
        checks.append(_check("Momentum squeeze", "INFO", "Sin datos suficientes o sin squeeze activo.", group="Momentum"))

    if support is not None or resistance is not None:
        layers.append(
            _card(
                "Soporte / resistencia",
                "INFO",
                "Usar estos niveles para no comprar contra techo ni vender justo sobre soporte.",
                evidence=[f"Soporte {price_text(support)}", f"Resistencia {price_text(resistance)}"],
            )
        )

    fundamental_bias = safe_text(
        setup.get("fundamental_bias")
        or confluence.get("fundamental_bias")
        or setup.get("sector_context")
        or confluence.get("sector_context")
    )
    if fundamental_bias:
        layers.append(_card("Fundamental/contexto", "INFO", f"Contexto no tecnico: {fundamental_bias}."))
    else:
        data_gaps.append("No hay capa fundamental; usarla como contexto, no como gatillo intradia.")

    operator_rules = [
        "Usar orden limite; nunca market order si el spread esta amplio o no hay Level2/Time&Sales.",
        "Registrar entrada, stop, salida parcial 2/5/10 y resultado para que la memoria aprenda.",
        "No subir tamano hasta tener muestra real de al menos 30 senales medidas por estrategia.",
        "Si toca stop, no reentrar sin nueva confirmacion 15m/1h y volumen.",
    ]
    if ema9 is not None and sma20 is not None:
        operator_rules.append(
            f"Para saltos EMA, validar EMA9 {price_text(ema9)} contra SMA20 {price_text(sma20)} cerca del cierre."
        )

    caution_count = sum(1 for item in checks if item.get("state") == "WARN")
    if action in {"BUY_STOCK", "WATCH_CALL"} and caution_count == 0:
        summary = f"El conocimiento nuevo apoya la decision base en {symbol_text}; ejecutar solo con stop y orden limite."
        bias = "supportive"
    elif action in {"BUY_STOCK", "WATCH_CALL"}:
        summary = (
            f"La decision base sigue viva en {symbol_text}, pero la capa aprendida pide validar "
            f"{caution_count} punto(s) antes de aumentar tamano."
        )
        bias = "caution"
    elif action == "NO_TRADE":
        summary = f"La capa aprendida refuerza No operar en {symbol_text}: esperar recuperacion y mejor calidad."
        bias = "defensive"
    else:
        summary = f"La capa aprendida mantiene a {symbol_text} en observacion; buscar confirmacion sin perseguir."
        bias = "watch"

    return {
        "symbol": symbol_text,
        "market": market,
        "timeframe": timeframe,
        "decision": decision,
        "action": action,
        "strategy_family": strategy_family,
        "bias": bias,
        "summary": summary,
        "layers": layers,
        "checks": checks,
        "operator_rules": operator_rules,
        "data_gaps": sorted(set(item for item in data_gaps if item)),
        "source": "class_video_materials_plus_existing_roxy_rules",
        "mode": "enrichment_only",
        "note": "Esta capa explica y prioriza; no cambia la decision base por si sola.",
    }
