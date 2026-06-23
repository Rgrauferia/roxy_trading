from __future__ import annotations

from typing import Any


MAX_HEALTHY_EXTENSION = 0.08
MAX_MEDIAS_SEPARATION = 0.12
MAX_RISK_PCT = 0.035
MIN_TARGET_PCT = 0.02
MIN_VOLUME = 0.8
IDEAL_VOLUME = 1.1


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


def first_float(*values: Any) -> float | None:
    for value in values:
        number = safe_float(value)
        if number is not None:
            return number
    return None


def _check(label: str, passed: bool, detail: str, *, severity: str = "soft") -> dict[str, Any]:
    return {
        "label": label,
        "passed": bool(passed),
        "detail": detail,
        "severity": severity,
    }


def _setup_text(source: dict[str, Any]) -> str:
    return safe_text(
        source.get("setup")
        or source.get("trigger_setup")
        or source.get("trend_setup")
        or source.get("strategy_family")
    ).upper()


def evaluate_natalia_strategy_rules(
    setup: dict[str, Any],
    confluence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate the Natalia Trading class rules as an execution gate.

    The rules are conservative by design. They can support a BUY, downgrade it
    to WAIT, or block it, but they do not create a BUY by themselves.
    """
    confluence = confluence or {}
    merged = {**setup, **confluence}
    close = first_float(setup.get("close"), setup.get("entry"), confluence.get("entry"), confluence.get("close"))
    sma20 = first_float(setup.get("sma20"), confluence.get("sma20"))
    sma40 = first_float(setup.get("sma40"), confluence.get("sma40"))
    sma100 = first_float(setup.get("sma100"), confluence.get("sma100"))
    sma200 = first_float(setup.get("sma200"), confluence.get("sma200"))
    ema9 = first_float(setup.get("ema9"), setup.get("ema_9"), confluence.get("ema9"), confluence.get("ema_9"))
    rel_vol = first_float(confluence.get("relative_volume_15m"), setup.get("relative_volume"), confluence.get("relative_volume"))
    risk_pct = first_float(confluence.get("risk_pct"), setup.get("risk_pct"))
    target_pct = first_float(confluence.get("recommended_target_pct"), setup.get("recommended_target_pct"))
    signal = safe_text(merged.get("signal")).upper()
    trade_decision = safe_text(merged.get("trade_decision")).upper()
    setup_name = _setup_text(merged)
    trend_setup = safe_text(merged.get("trend_setup")).upper()
    trigger_setup = safe_text(merged.get("trigger_setup") or setup_name).upper()

    aligned_20_40 = bool(sma20 is not None and sma40 is not None and sma20 > sma40)
    fully_aligned = bool(
        close is not None
        and sma20 is not None
        and sma40 is not None
        and sma100 is not None
        and sma200 is not None
        and close > sma20 > sma40 > sma100 > sma200
    )
    above_sma200 = not (close is not None and sma200 is not None and close < sma200)
    above_sma40 = not (close is not None and sma40 is not None and close < sma40)
    bullish_context = (
        fully_aligned
        or "PULLBACK" in {setup_name, trend_setup, trigger_setup}
        or "TREND_CONTINUATION" in {setup_name, trend_setup, trigger_setup}
        or "CANAL ALCISTA" in safe_text(merged.get("strategy_family")).upper()
    )
    lost_sma40 = bool(bullish_context and not above_sma40)
    fifteen_one_hour_ok = signal == "BUY" and trade_decision.startswith("TRADE_FOR")
    volume_ok = rel_vol is not None and rel_vol >= MIN_VOLUME
    target_ok = target_pct is not None and target_pct >= MIN_TARGET_PCT
    risk_ok = risk_pct is not None and risk_pct <= MAX_RISK_PCT
    extension = (close - sma20) / sma20 if close is not None and sma20 and sma20 > 0 else None
    separation = (sma20 - sma40) / sma40 if sma20 is not None and sma40 and sma40 > 0 else None
    overextended = bool(
        (extension is not None and extension > MAX_HEALTHY_EXTENSION)
        or (separation is not None and separation > MAX_MEDIAS_SEPARATION)
    )
    ema_support = bool(ema9 is not None and sma20 is not None and ema9 >= sma20)

    checks = [
        _check(
            "Filtro SMA200",
            above_sma200,
            (
                f"Precio {price_text(close)} debajo de SMA200 {price_text(sma200)}; bloquear compras."
                if not above_sma200
                else f"Precio respeta o no tiene bloqueo SMA200 ({price_text(sma200)})."
            ),
            severity="hard",
        ),
        _check(
            "SMA40 sostiene canal",
            not lost_sma40,
            (
                f"Precio {price_text(close)} perdio SMA40 {price_text(sma40)} dentro de contexto alcista/pullback."
                if lost_sma40
                else "SMA40 no esta rota dentro del canal observado."
            ),
            severity="hard",
        ),
        _check(
            "15m + 1h confirman",
            fifteen_one_hour_ok,
            "15m da BUY y 1h mantiene operacion." if fifteen_one_hour_ok else "Falta que 15m sea BUY y 1h mantenga TRADE_FOR.",
            severity="wait",
        ),
        _check(
            "Volumen acompana",
            volume_ok,
            f"Volumen relativo {rel_vol:.2f}x." if rel_vol is not None else "Falta volumen relativo.",
            severity="wait",
        ),
        _check(
            "Riesgo medible",
            risk_ok,
            f"Riesgo {pct_text(risk_pct)}." if risk_pct is not None else "Falta stop/riesgo valido.",
            severity="wait",
        ),
        _check(
            "Target minimo 2%",
            target_ok,
            f"Target {pct_text(target_pct)}." if target_pct is not None else "Falta objetivo minimo 2%.",
            severity="wait",
        ),
        _check(
            "No perseguir distancia",
            not overextended,
            (
                "Precio o medias demasiado extendidas; esperar pullback antes de perseguir."
                if overextended
                else "Distancia entre precio y medias esta dentro de rango sano."
            ),
            severity="soft",
        ),
        _check(
            "Orden 20/40/100/200",
            (sma20 is None or sma40 is None) or fully_aligned or aligned_20_40,
            (
                "Medias alineadas para canal alcista."
                if fully_aligned
                else "SMA20 sobre SMA40; falta orden completo 20/40/100/200."
                if aligned_20_40
                else "Faltan medias completas; Roxy mantiene la regla como evidencia pendiente."
                if sma20 is None or sma40 is None
                else "Medias no estan ordenadas para compra limpia."
            ),
            severity="soft",
        ),
    ]
    if ema9 is not None and sma20 is not None:
        checks.append(
            _check(
                "EMA9 apoya salto",
                ema_support,
                (
                    f"EMA9 {price_text(ema9)} sostiene sobre SMA20 {price_text(sma20)}."
                    if ema_support
                    else f"EMA9 {price_text(ema9)} no sostiene sobre SMA20 {price_text(sma20)}."
                ),
                severity="soft",
            )
        )

    hard_failures = [item for item in checks if item["severity"] == "hard" and not item["passed"]]
    wait_failures = [item for item in checks if item["severity"] == "wait" and not item["passed"]]
    soft_failures = [item for item in checks if item["severity"] == "soft" and not item["passed"]]
    if hard_failures:
        decision_gate = "BLOCK_BUY"
        bias = "NO_TRADE"
        action_hint = "No operar"
        movement = "Esperar recuperacion de estructura: SMA200/SMA40, 15m+1h, volumen, riesgo y target 2% deben coincidir."
    elif wait_failures or soft_failures:
        decision_gate = "WAIT_CONFIRMATION"
        bias = "WAIT"
        action_hint = "Esperar"
        movement = "Esperar confirmacion completa: 15m+1h, volumen, riesgo, target 2% y distancia sana de medias."
    else:
        decision_gate = "ALLOW"
        bias = "BUY_READY"
        action_hint = "Operar si el plan manual confirma"
        movement = "Setup alineado: tendencia, medias, volumen, riesgo y target minimo estan listos para plan manual."

    reasons = [item["detail"] for item in hard_failures[:3]]
    if not reasons:
        reasons = [item["detail"] for item in wait_failures[:3]]
    if not reasons:
        reasons = [item["detail"] for item in soft_failures[:3]]
    if not reasons:
        reasons = [
            "La lectura de clase apoya operar solo con medias ordenadas, confirmacion 15m/1h, volumen y riesgo controlado."
        ]

    return {
        "source": "natalia_trading_class_rules",
        "bias": bias,
        "decision_gate": decision_gate,
        "action_hint": action_hint,
        "alert_ok": decision_gate == "ALLOW",
        "hard_block": decision_gate == "BLOCK_BUY",
        "wait_block": decision_gate == "WAIT_CONFIRMATION",
        "score_adjustment": -20 if decision_gate == "BLOCK_BUY" else -8 if decision_gate == "WAIT_CONFIRMATION" else 5,
        "movement": movement,
        "summary": reasons[0],
        "reasons": reasons,
        "checks": checks,
        "levels": {
            "close": close,
            "ema9": ema9,
            "sma20": sma20,
            "sma40": sma40,
            "sma100": sma100,
            "sma200": sma200,
            "relative_volume": rel_vol,
            "risk_pct": risk_pct,
            "target_pct": target_pct,
        },
    }
