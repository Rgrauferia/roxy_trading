from __future__ import annotations

from typing import Any

from trade_brief import CORE_STRATEGIES, safe_float, safe_text, strategy_family_from_setup


STOP_STATUSES = {"STOP", "STOPPED", "STOP_HIT", "HIT_STOP"}
HIT_STATUSES = {"HIT_2PCT", "HIT_5PCT", "HIT_10PCT"}
MILESTONE_ORDER = ("2%", "5%", "10%")


def _int_value(value: Any) -> int:
    number = safe_float(value)
    return int(number) if number is not None else 0


def _rate(part: int, total: int) -> float | None:
    return part / total if total > 0 else None


def _milestones(alert: dict[str, Any]) -> set[str]:
    values = set()
    for key in ("milestones", "recorded_milestones"):
        raw = alert.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        for item in raw:
            text = safe_text(item)
            if text in MILESTONE_ORDER:
                values.add(text)
    status = safe_text(alert.get("status")).upper()
    if status == "HIT_10PCT":
        values.update(MILESTONE_ORDER)
    elif status == "HIT_5PCT":
        values.update({"2%", "5%"})
    elif status == "HIT_2PCT":
        values.add("2%")
    return values


def _strategy_family(alert: dict[str, Any]) -> str:
    family = safe_text(alert.get("strategy_family"))
    if family:
        return family
    return strategy_family_from_setup(
        safe_text(alert.get("trigger_setup") or alert.get("setup")),
        trend_setup=safe_text(alert.get("trend_setup")),
    )


def _alert_status(alert: dict[str, Any]) -> str:
    status = safe_text(alert.get("status")).upper()
    if status in STOP_STATUSES:
        return "STOP"
    if status in HIT_STATUSES:
        return status
    if _milestones(alert):
        return "HIT_PARTIAL"
    return status or "OPEN"


def _outcome_state(alert: dict[str, Any]) -> str:
    state = safe_text(alert.get("outcome_state")).upper()
    if state:
        return state
    status = _alert_status(alert)
    if status in {"STOP", "HIT_2PCT", "HIT_5PCT", "HIT_10PCT", "HIT_PARTIAL"}:
        return status
    progress_to_2pct = safe_float(alert.get("progress_to_2pct")) or 0.0
    progress_to_stop = safe_float(alert.get("progress_to_stop")) or 0.0
    if progress_to_stop >= 0.75 and progress_to_2pct < 0.50:
        return "DANGER_STOP"
    if progress_to_2pct >= 0.75:
        return "NEAR_2PCT"
    return status


def _empty_counts() -> dict[str, int]:
    return {
        "alerts": 0,
        "open": 0,
        "measured": 0,
        "hit_2pct": 0,
        "hit_5pct": 0,
        "hit_10pct": 0,
        "stops": 0,
    }


def _counts_from_alerts(alerts: list[dict[str, Any]]) -> dict[str, int]:
    counts = _empty_counts()
    counts["alerts"] = len(alerts)
    for alert in alerts:
        status = _alert_status(alert)
        milestones = _milestones(alert)
        stopped = status == "STOP"
        hit_2 = "2%" in milestones
        hit_5 = "5%" in milestones
        hit_10 = "10%" in milestones
        if hit_2:
            counts["hit_2pct"] += 1
        if hit_5:
            counts["hit_5pct"] += 1
        if hit_10:
            counts["hit_10pct"] += 1
        if stopped:
            counts["stops"] += 1
        if stopped or hit_2 or hit_5 or hit_10:
            counts["measured"] += 1
        else:
            counts["open"] += 1
    return counts


def headline_accuracy(memory: dict[str, Any], *, minimum_sample: int = 30) -> dict[str, Any]:
    history = list(memory.get("alert_history") or [])
    counts = _counts_from_alerts(history)

    aggregate_alerts = 0
    aggregate_hit_2 = 0
    aggregate_hit_5 = 0
    aggregate_hit_10 = 0
    aggregate_stops = 0
    for stats in (memory.get("strategy_stats") or {}).values():
        aggregate_alerts += _int_value(stats.get("alerts"))
        aggregate_hit_2 += _int_value(stats.get("hit_2pct"))
        aggregate_hit_5 += _int_value(stats.get("hit_5pct"))
        aggregate_hit_10 += _int_value(stats.get("hit_10pct"))
        aggregate_stops += _int_value(stats.get("stops"))

    if aggregate_alerts > counts["alerts"]:
        counts["alerts"] = aggregate_alerts
        counts["hit_2pct"] = max(counts["hit_2pct"], aggregate_hit_2)
        counts["hit_5pct"] = max(counts["hit_5pct"], aggregate_hit_5)
        counts["hit_10pct"] = max(counts["hit_10pct"], aggregate_hit_10)
        counts["stops"] = max(counts["stops"], aggregate_stops)
        counts["measured"] = max(counts["measured"], min(counts["alerts"], counts["hit_2pct"] + counts["stops"]))

    sample_gap = max(0, minimum_sample - counts["measured"])
    sample_status = "READY" if counts["measured"] >= minimum_sample else "NEEDS_DATA"
    return {
        **counts,
        "hit_2_rate": _rate(counts["hit_2pct"], counts["alerts"]),
        "hit_5_rate": _rate(counts["hit_5pct"], counts["alerts"]),
        "hit_10_rate": _rate(counts["hit_10pct"], counts["alerts"]),
        "stop_rate": _rate(counts["stops"], counts["alerts"]),
        "sample_status": sample_status,
        "minimum_sample": minimum_sample,
        "sample_gap": sample_gap,
    }


def _strategy_status(alerts: int, hit_2_rate: float | None, stop_rate: float | None, minimum_alerts: int) -> str:
    hit_2 = hit_2_rate or 0.0
    stop = stop_rate or 0.0
    if alerts < minimum_alerts:
        return "NEEDS_DATA"
    if stop >= 0.50 and hit_2 < 0.35:
        return "RISKY"
    if hit_2 >= 0.55 and stop <= 0.35:
        return "PROMISING"
    if hit_2 >= 0.45 and stop <= 0.40:
        return "WATCH"
    return "MIXED"


def strategy_accuracy_rows(memory: dict[str, Any], *, minimum_alerts: int = 10) -> list[dict[str, Any]]:
    history = list(memory.get("alert_history") or [])
    history_by_family: dict[str, list[dict[str, Any]]] = {}
    for alert in history:
        history_by_family.setdefault(_strategy_family(alert), []).append(alert)

    families = set(CORE_STRATEGIES) | set(memory.get("strategy_stats") or {}) | set(history_by_family)
    rows: list[dict[str, Any]] = []
    for family in sorted(families):
        stats = (memory.get("strategy_stats") or {}).get(family, {})
        alert_counts = _counts_from_alerts(history_by_family.get(family, []))
        alerts = max(_int_value(stats.get("alerts")), alert_counts["alerts"])
        seen = max(_int_value(stats.get("seen")), alerts)
        hit_2 = max(_int_value(stats.get("hit_2pct")), alert_counts["hit_2pct"])
        hit_5 = max(_int_value(stats.get("hit_5pct")), alert_counts["hit_5pct"])
        hit_10 = max(_int_value(stats.get("hit_10pct")), alert_counts["hit_10pct"])
        stops = max(_int_value(stats.get("stops")), alert_counts["stops"])
        measured = max(alert_counts["measured"], min(alerts, hit_2 + stops))
        hit_2_rate = _rate(hit_2, alerts)
        hit_5_rate = _rate(hit_5, alerts)
        hit_10_rate = _rate(hit_10, alerts)
        stop_rate = _rate(stops, alerts)
        status = _strategy_status(alerts, hit_2_rate, stop_rate, minimum_alerts)
        rows.append(
            {
                "strategy_family": family,
                "status": status,
                "seen": seen,
                "alerts": alerts,
                "measured": measured,
                "open": max(0, alerts - measured),
                "hit_2pct": hit_2,
                "hit_5pct": hit_5,
                "hit_10pct": hit_10,
                "stops": stops,
                "hit_2_rate": hit_2_rate,
                "hit_5_rate": hit_5_rate,
                "hit_10_rate": hit_10_rate,
                "stop_rate": stop_rate,
                "sample_gap": max(0, minimum_alerts - alerts),
                "last_seen_at": stats.get("last_seen_at"),
                "last_outcome_at": stats.get("last_outcome_at"),
            }
        )
    rows.sort(
        key=lambda row: (
            row["status"] == "PROMISING",
            row["hit_2_rate"] or 0.0,
            -(row["stop_rate"] or 0.0),
            row["alerts"],
        ),
        reverse=True,
    )
    return rows


def symbol_accuracy_rows(memory: dict[str, Any]) -> list[dict[str, Any]]:
    history = list(memory.get("alert_history") or [])
    history_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for alert in history:
        symbol = safe_text(alert.get("symbol")).upper()
        if symbol:
            history_by_symbol.setdefault(symbol, []).append(alert)

    symbols = set(memory.get("symbols") or {}) | set(history_by_symbol)
    rows: list[dict[str, Any]] = []
    for symbol in sorted(symbols):
        stats = (memory.get("symbols") or {}).get(symbol, {})
        alert_counts = _counts_from_alerts(history_by_symbol.get(symbol, []))
        alerts = max(_int_value(stats.get("alerts")), alert_counts["alerts"])
        hit_2 = alert_counts["hit_2pct"]
        stops = alert_counts["stops"]
        rows.append(
            {
                "symbol": symbol,
                "seen": _int_value(stats.get("seen")),
                "alerts": alerts,
                "best_ai_score": _int_value(stats.get("best_ai_score")),
                "last_signal": stats.get("last_signal"),
                "hit_2pct": hit_2,
                "stops": stops,
                "hit_2_rate": _rate(hit_2, alerts),
                "stop_rate": _rate(stops, alerts),
                "last_seen_at": stats.get("last_seen_at"),
            }
        )
    rows.sort(key=lambda row: (row["alerts"], row["best_ai_score"], row["seen"]), reverse=True)
    return rows


def alert_history_rows(memory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for alert in memory.get("alert_history") or []:
        milestones = sorted(_milestones(alert), key=lambda item: MILESTONE_ORDER.index(item) if item in MILESTONE_ORDER else 99)
        rows.append(
            {
                "symbol": safe_text(alert.get("symbol")).upper(),
                "strategy_family": _strategy_family(alert),
                "status": _alert_status(alert),
                "entry": safe_float(alert.get("entry")),
                "stop": safe_float(alert.get("stop")),
                "last_price": safe_float(alert.get("last_price")),
                "max_price": safe_float(alert.get("max_price")),
                "min_price": safe_float(alert.get("min_price")),
                "max_gain_pct": safe_float(alert.get("max_gain_pct")),
                "max_drawdown_pct": safe_float(alert.get("max_drawdown_pct")),
                "current_gain_pct": safe_float(alert.get("current_gain_pct")),
                "current_drawdown_pct": safe_float(alert.get("current_drawdown_pct")),
                "progress_to_2pct": safe_float(alert.get("progress_to_2pct")),
                "progress_to_stop": safe_float(alert.get("progress_to_stop")),
                "best_target_hit": safe_text(alert.get("best_target_hit")) or "-",
                "best_target_pct": safe_float(alert.get("best_target_pct")),
                "best_reward_r": safe_float(alert.get("best_reward_r")),
                "current_reward_r": safe_float(alert.get("current_reward_r")),
                "stopped_after_target": bool(alert.get("stopped_after_target")),
                "stopped_before_target": bool(alert.get("stopped_before_target")),
                "outcome_state": _outcome_state(alert),
                "milestones": ", ".join(milestones) if milestones else "-",
                "opened_at": alert.get("opened_at") or alert.get("created_at") or alert.get("ts"),
                "last_checked_at": alert.get("last_checked_at") or alert.get("updated_at"),
                "closed_at": alert.get("closed_at"),
            }
        )
    rows.sort(key=lambda row: safe_text(row.get("opened_at")), reverse=True)
    return rows


def signal_journal_rows(memory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for signal in memory.get("signal_journal") or []:
        milestones = sorted(_milestones(signal), key=lambda item: MILESTONE_ORDER.index(item) if item in MILESTONE_ORDER else 99)
        rows.append(
            {
                "symbol": safe_text(signal.get("symbol")).upper(),
                "market": signal.get("market"),
                "ai_action": signal.get("ai_action"),
                "signal": signal.get("signal"),
                "trade_decision": signal.get("trade_decision"),
                "strategy_family": _strategy_family(signal),
                "alert_gate": signal.get("alert_gate"),
                "readiness": safe_float(signal.get("alert_readiness_score")),
                "status": _alert_status(signal),
                "entry": safe_float(signal.get("entry")),
                "stop": safe_float(signal.get("stop")),
                "last_price": safe_float(signal.get("last_price")),
                "max_price": safe_float(signal.get("max_price")),
                "min_price": safe_float(signal.get("min_price")),
                "max_gain_pct": safe_float(signal.get("max_gain_pct")),
                "max_drawdown_pct": safe_float(signal.get("max_drawdown_pct")),
                "current_gain_pct": safe_float(signal.get("current_gain_pct")),
                "current_drawdown_pct": safe_float(signal.get("current_drawdown_pct")),
                "progress_to_2pct": safe_float(signal.get("progress_to_2pct")),
                "progress_to_stop": safe_float(signal.get("progress_to_stop")),
                "best_target_hit": safe_text(signal.get("best_target_hit")) or "-",
                "best_target_pct": safe_float(signal.get("best_target_pct")),
                "best_reward_r": safe_float(signal.get("best_reward_r")),
                "current_reward_r": safe_float(signal.get("current_reward_r")),
                "stopped_after_target": bool(signal.get("stopped_after_target")),
                "stopped_before_target": bool(signal.get("stopped_before_target")),
                "outcome_state": _outcome_state(signal),
                "milestones": ", ".join(milestones) if milestones else "-",
                "opened_at": signal.get("opened_at") or signal.get("created_at") or signal.get("ts"),
                "last_seen_at": signal.get("last_seen_at"),
                "last_checked_at": signal.get("last_checked_at") or signal.get("updated_at"),
                "closed_at": signal.get("closed_at"),
            }
        )
    rows.sort(key=lambda row: safe_text(row.get("opened_at")), reverse=True)
    return rows


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def watch_progress_summary(memory: dict[str, Any]) -> dict[str, Any]:
    rows = signal_journal_rows(memory)
    progress_to_2pct: list[float] = []
    progress_to_stop: list[float] = []
    observed = 0
    hit_2_count = 0

    for row in rows:
        to_target = safe_float(row.get("progress_to_2pct"))
        to_stop = safe_float(row.get("progress_to_stop"))
        status = safe_text(row.get("status")).upper()
        milestones = safe_text(row.get("milestones"))
        if to_target is not None or to_stop is not None:
            observed += 1
        if to_target is not None:
            progress_to_2pct.append(max(0.0, to_target))
        if to_stop is not None:
            progress_to_stop.append(max(0.0, to_stop))
        if status in {"HIT_2PCT", "HIT_5PCT", "HIT_10PCT", "HIT_PARTIAL"} or "2%" in milestones:
            hit_2_count += 1

    near_2pct_count = sum(1 for value in progress_to_2pct if value >= 0.75)
    danger_stop_count = sum(1 for value in progress_to_stop if value >= 0.75)
    return {
        "tracked": len(rows),
        "observed": observed,
        "hit_2_count": hit_2_count,
        "near_2pct_count": near_2pct_count,
        "danger_stop_count": danger_stop_count,
        "avg_progress_to_2pct": _average(progress_to_2pct),
        "max_progress_to_2pct": max(progress_to_2pct) if progress_to_2pct else None,
        "avg_progress_to_stop": _average(progress_to_stop),
        "max_progress_to_stop": max(progress_to_stop) if progress_to_stop else None,
    }


def real_signal_memory_summary(
    memory: dict[str, Any],
    *,
    strategy_family: str | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Summarize measured outcomes Roxy can actually learn from."""
    strategy_filter = safe_text(strategy_family)
    symbol_filter = safe_text(symbol).upper()
    raw_items: list[dict[str, Any]] = []
    for source_key, source in (("alert", memory.get("alert_history") or []), ("journal", memory.get("signal_journal") or [])):
        for index, item in enumerate(source):
            row = dict(item)
            row["_source"] = source_key
            row["_index"] = index
            if strategy_filter and _strategy_family(row) != strategy_filter:
                continue
            if symbol_filter and safe_text(row.get("symbol")).upper() != symbol_filter:
                continue
            raw_items.append(row)

    seen_keys: set[tuple[Any, ...]] = set()
    items: list[dict[str, Any]] = []
    for row in raw_items:
        key = (
            safe_text(row.get("symbol")).upper(),
            safe_text(row.get("opened_at") or row.get("created_at") or row.get("ts") or row.get("_index")),
            _strategy_family(row),
            safe_float(row.get("entry")),
            safe_float(row.get("stop")),
            _alert_status(row),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        items.append(row)

    counts = _counts_from_alerts(items)
    if not items and strategy_filter:
        stats = (memory.get("strategy_stats") or {}).get(strategy_filter, {})
        counts["alerts"] = _int_value(stats.get("alerts"))
        counts["hit_2pct"] = _int_value(stats.get("hit_2pct"))
        counts["hit_5pct"] = _int_value(stats.get("hit_5pct"))
        counts["hit_10pct"] = _int_value(stats.get("hit_10pct"))
        counts["stops"] = _int_value(stats.get("stops"))
        counts["measured"] = min(counts["alerts"], counts["hit_2pct"] + counts["stops"])
        counts["open"] = max(0, counts["alerts"] - counts["measured"])

    hit_2_rate = _rate(counts["hit_2pct"], counts["alerts"])
    stop_rate = _rate(counts["stops"], counts["alerts"])
    if counts["measured"] <= 0:
        lesson = "Roxy todavia no tiene senales cerradas para medir 2%, 5%, 10% o stop."
        confidence = "Recolectando datos"
    elif counts["alerts"] < 10:
        lesson = "Hay medicion real, pero la muestra aun es pequena. Mantener tamano bajo."
        confidence = "Muestra pequena"
    elif (hit_2_rate or 0.0) >= 0.55 and (stop_rate or 0.0) <= 0.35:
        lesson = "La memoria favorece este setup: llega a 2% mas veces de las que toca stop."
        confidence = "Favorable"
    elif (stop_rate or 0.0) >= 0.50 and (hit_2_rate or 0.0) < 0.35:
        lesson = "La memoria penaliza este setup: toca stop demasiado para la tasa de 2%."
        confidence = "Riesgosa"
    else:
        lesson = "La memoria esta mixta; Roxy debe exigir confirmacion limpia antes de subir riesgo."
        confidence = "Mixta"

    return {
        **counts,
        "hit_2_rate": hit_2_rate,
        "hit_5_rate": _rate(counts["hit_5pct"], counts["alerts"]),
        "hit_10_rate": _rate(counts["hit_10pct"], counts["alerts"]),
        "stop_rate": stop_rate,
        "strategy_family": strategy_filter or "Todas",
        "symbol": symbol_filter or "Todos",
        "confidence": confidence,
        "lesson": lesson,
    }


def build_accuracy_report(memory: dict[str, Any], *, minimum_sample: int = 30, minimum_strategy_alerts: int = 10) -> dict[str, Any]:
    headline = headline_accuracy(memory, minimum_sample=minimum_sample)
    strategy_rows = strategy_accuracy_rows(memory, minimum_alerts=minimum_strategy_alerts)
    symbol_rows = symbol_accuracy_rows(memory)
    alert_rows = alert_history_rows(memory)
    journal_rows = signal_journal_rows(memory)
    watch_progress = watch_progress_summary(memory)
    real_memory = real_signal_memory_summary(memory)

    next_actions: list[str] = []
    if headline["alerts"] <= 0:
        next_actions.append("Start logging only high-quality BUY alerts before trusting accuracy numbers.")
    if headline["sample_status"] == "NEEDS_DATA":
        next_actions.append(
            f"Collect {headline['sample_gap']} more measured signals before increasing trade size from the $500 plan."
        )
    risky = [row["strategy_family"] for row in strategy_rows if row["status"] == "RISKY"]
    promising = [row["strategy_family"] for row in strategy_rows if row["status"] == "PROMISING"]
    if risky:
        next_actions.append("Tighten filters for: " + ", ".join(risky[:3]) + ".")
    if promising:
        next_actions.append("Promote only small-size tests for: " + ", ".join(promising[:3]) + ".")
    if watch_progress["near_2pct_count"] > 0:
        next_actions.append("Review WATCH setups that reached 75%+ of the 2% target; filters may be too strict.")
    if watch_progress["danger_stop_count"] > 0:
        next_actions.append("Review WATCH setups that moved 75%+ toward stop; tighten risk filters.")
    next_actions.append("Keep live broker execution off until previews, credentials, and sample history are proven.")

    return {
        "headline": headline,
        "strategy_rows": strategy_rows,
        "symbol_rows": symbol_rows,
        "alert_rows": alert_rows,
        "signal_journal_rows": journal_rows,
        "watch_progress": watch_progress,
        "real_memory": real_memory,
        "next_actions": next_actions,
    }
