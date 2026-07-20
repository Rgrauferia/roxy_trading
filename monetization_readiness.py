from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


DEFAULT_APP_STORE_COMMISSION = 0.15
SIGNAL_VALIDATION_MIN_CLOSED = 100
BETA_MIN_TRACKED = 25
PROFITABILITY_MIN_CLOSED = 100
PROFITABILITY_MIN_BACKTEST_ROWS = 10
PROFITABILITY_MIN_WEEKS = 4
PROFITABILITY_MIN_CONSISTENT_WEEKS = 3
PROFITABILITY_MIN_CLOSED_PER_WEEK = 5
PROFIT_FACTOR_TARGET = 1.5
PAPER_HIT_RATE_TARGET = 0.60
MAX_ACCEPTABLE_DRAWDOWN = 0.15


def _text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def _float(value: Any) -> float | None:
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


def _rate(part: int, total: int) -> float | None:
    return part / total if total > 0 else None


def _journal_records(journal: pd.DataFrame | list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if journal is None:
        return []
    if isinstance(journal, pd.DataFrame):
        if journal.empty:
            return []
        return [dict(row) for row in journal.to_dict("records")]
    return [dict(row) for row in journal if isinstance(row, Mapping)]


def paper_evidence_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Collapse repeated scanner snapshots into independent paper episodes."""
    episodes: dict[tuple[Any, ...], dict[str, Any]] = {}
    eligible_raw = 0
    for index, row in enumerate(records):
        status = _text(row.get("status")).upper()
        outcome = _text(row.get("closed_outcome") or row.get("outcome")).upper()
        is_closed = status.startswith("CLOSED_") or outcome in {"HIT_2", "HIT_5", "HIT_10", "STOP"}
        is_ready = status in {"READY_FOR_PAPER", "OPEN", "PAPER_OPEN"}
        if not (is_ready or is_closed):
            continue
        eligible_raw += 1
        symbol = _text(row.get("symbol")).upper()
        strategy = _text(row.get("strategy_family") or row.get("strategy"))
        timeframe = _text(row.get("timeframe")) or "-"
        opened = _parse_datetime(row.get("ts") or row.get("opened_at") or row.get("created_at"))
        if symbol and opened is not None:
            market = _text(row.get("market")).lower()
            session_date = opened.date().isoformat()
            key = (market, symbol, strategy, timeframe, session_date)
        else:
            # Legacy/test rows without identity or timestamps remain independent.
            key = ("row", index)
        existing = episodes.get(key)
        existing_status = _text((existing or {}).get("status")).upper()
        existing_outcome = _text((existing or {}).get("closed_outcome") or (existing or {}).get("outcome")).upper()
        existing_closed = existing_status.startswith("CLOSED_") or existing_outcome in {"HIT_2", "HIT_5", "HIT_10", "STOP"}
        if existing is None or (is_closed and not existing_closed):
            episodes[key] = row
        elif is_closed == existing_closed:
            current_time = _text(row.get("closed_at") or row.get("ts"))
            previous_time = _text(existing.get("closed_at") or existing.get("ts"))
            if current_time >= previous_time:
                episodes[key] = row
    evidence = list(episodes.values())
    return evidence, max(0, eligible_raw - len(evidence))


def paper_journal_monetization_summary(journal: pd.DataFrame | list[Mapping[str, Any]] | None) -> dict[str, Any]:
    records = _journal_records(journal)
    candidates = len(records)
    evidence_records, duplicates_collapsed = paper_evidence_records(records)
    tracked = 0
    closed = 0
    ready = 0
    blocked = 0
    hit_2 = 0
    hit_5 = 0
    hit_10 = 0
    stops = 0
    closed_moves: list[float] = []

    blocked = sum(1 for row in records if _text(row.get("status")).upper() == "BLOCKED")

    for row in evidence_records:
        status = _text(row.get("status")).upper()
        outcome = _text(row.get("closed_outcome") or row.get("outcome")).upper()
        is_closed = status.startswith("CLOSED_") or outcome in {"HIT_2", "HIT_5", "HIT_10", "STOP"}
        is_ready = status in {"READY_FOR_PAPER", "OPEN", "PAPER_OPEN"}
        if is_ready or is_closed:
            tracked += 1
        if status == "READY_FOR_PAPER":
            ready += 1
        if is_closed:
            closed += 1
            move = _float(row.get("closed_move_pct") or row.get("move_pct"))
            if move is not None:
                closed_moves.append(move)
        if outcome in {"HIT_2", "HIT_5", "HIT_10"}:
            hit_2 += 1
        if outcome in {"HIT_5", "HIT_10"}:
            hit_5 += 1
        if outcome == "HIT_10":
            hit_10 += 1
        if outcome == "STOP":
            stops += 1

    return {
        "candidates": candidates,
        "duplicates_collapsed": duplicates_collapsed,
        "tracked": tracked,
        "closed": closed,
        "open": max(0, tracked - closed),
        "ready": ready,
        "blocked": blocked,
        "hit_2": hit_2,
        "hit_5": hit_5,
        "hit_10": hit_10,
        "stops": stops,
        "hit_2_rate": _rate(hit_2, closed),
        "hit_5_rate": _rate(hit_5, closed),
        "hit_10_rate": _rate(hit_10, closed),
        "stop_rate": _rate(stops, closed),
        "avg_closed_move_pct": sum(closed_moves) / len(closed_moves) if closed_moves else None,
    }


def combined_paper_monetization_summary(
    alpaca_journal: pd.DataFrame | list[Mapping[str, Any]] | None = None,
    crypto_journal: pd.DataFrame | list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    alpaca = paper_journal_monetization_summary(alpaca_journal)
    crypto = paper_journal_monetization_summary(crypto_journal)
    closed = int(alpaca["closed"]) + int(crypto["closed"])
    hit_2 = int(alpaca["hit_2"]) + int(crypto["hit_2"])
    hit_5 = int(alpaca["hit_5"]) + int(crypto["hit_5"])
    hit_10 = int(alpaca["hit_10"]) + int(crypto["hit_10"])
    stops = int(alpaca["stops"]) + int(crypto["stops"])
    avg_moves: list[tuple[float, int]] = []
    for summary in (alpaca, crypto):
        avg_move = _float(summary.get("avg_closed_move_pct"))
        summary_closed = int(summary.get("closed") or 0)
        if avg_move is not None and summary_closed > 0:
            avg_moves.append((avg_move, summary_closed))
    weighted_move = (
        sum(avg * count for avg, count in avg_moves) / sum(count for _, count in avg_moves)
        if avg_moves
        else None
    )
    return {
        "alpaca": alpaca,
        "crypto": crypto,
        "candidates": int(alpaca["candidates"]) + int(crypto["candidates"]),
        "duplicates_collapsed": int(alpaca["duplicates_collapsed"]) + int(crypto["duplicates_collapsed"]),
        "tracked": int(alpaca["tracked"]) + int(crypto["tracked"]),
        "closed": closed,
        "open": int(alpaca["open"]) + int(crypto["open"]),
        "ready": int(alpaca["ready"]) + int(crypto["ready"]),
        "blocked": int(alpaca["blocked"]) + int(crypto["blocked"]),
        "hit_2": hit_2,
        "hit_5": hit_5,
        "hit_10": hit_10,
        "stops": stops,
        "hit_2_rate": _rate(hit_2, closed),
        "hit_5_rate": _rate(hit_5, closed),
        "hit_10_rate": _rate(hit_10, closed),
        "stop_rate": _rate(stops, closed),
        "avg_closed_move_pct": weighted_move,
    }


def _records_frame(rows: pd.DataFrame | list[Mapping[str, Any]] | None) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    return pd.DataFrame([dict(row) for row in rows if isinstance(row, Mapping)])


def _mean_float(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.mean())


def _median_float(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.median())


def _finite_mean_float(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna()
    if values.empty:
        return None
    return float(values.mean())


def _parse_datetime(value: Any) -> pd.Timestamp | None:
    text = _text(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed


def backtest_profitability_summary(
    backtest_rows: pd.DataFrame | list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    frame = _records_frame(backtest_rows)
    if frame.empty:
        return {
            "rows": 0,
            "eligible_rows": 0,
            "avg_return_pct": None,
            "median_return_pct": None,
            "avg_win_rate": None,
            "avg_profit_factor": None,
            "median_drawdown_pct": None,
            "max_drawdown_pct": None,
            "promising": False,
            "top_symbols": [],
        }

    eligible_mask = pd.Series([True] * len(frame), index=frame.index)
    if "eligible" in frame.columns:
        eligible_mask = frame["eligible"].astype(str).str.lower().isin({"true", "1", "yes", "y"})
    eligible = frame.loc[eligible_mask].copy()
    metric_frame = eligible if not eligible.empty else frame.copy()
    return_col = "total_return_pct" if "total_return_pct" in metric_frame.columns else "return_pct"
    dd_col = "max_drawdown_pct" if "max_drawdown_pct" in metric_frame.columns else "drawdown_pct"
    pf_col = "profit_factor" if "profit_factor" in metric_frame.columns else "pf"

    avg_return = _mean_float(metric_frame.get(return_col, pd.Series(dtype=float)))
    avg_pf = _finite_mean_float(metric_frame.get(pf_col, pd.Series(dtype=float)))
    median_dd = _median_float(metric_frame.get(dd_col, pd.Series(dtype=float)))
    max_dd = _mean_float(metric_frame.get(dd_col, pd.Series(dtype=float)).abs()) if dd_col in metric_frame else None
    if dd_col in metric_frame:
        dd_values = pd.to_numeric(metric_frame[dd_col], errors="coerce").abs().dropna()
        max_dd = float(dd_values.max()) if not dd_values.empty else None

    top_symbols: list[str] = []
    if "symbol" in metric_frame.columns and return_col in metric_frame.columns:
        ranked = metric_frame.assign(_return=pd.to_numeric(metric_frame[return_col], errors="coerce"))
        ranked = ranked.sort_values("_return", ascending=False)
        top_symbols = [str(value) for value in ranked["symbol"].head(5).tolist()]

    promising = (
        len(metric_frame) >= PROFITABILITY_MIN_BACKTEST_ROWS
        and avg_return is not None
        and avg_return > 0
        and avg_pf is not None
        and avg_pf >= PROFIT_FACTOR_TARGET
        and (median_dd is None or abs(median_dd) <= MAX_ACCEPTABLE_DRAWDOWN)
    )

    return {
        "rows": int(len(frame)),
        "eligible_rows": int(len(eligible)),
        "avg_return_pct": avg_return,
        "median_return_pct": _median_float(metric_frame.get(return_col, pd.Series(dtype=float))),
        "avg_win_rate": _mean_float(metric_frame.get("win_rate", pd.Series(dtype=float))),
        "avg_profit_factor": avg_pf,
        "median_drawdown_pct": median_dd,
        "max_drawdown_pct": max_dd,
        "promising": bool(promising),
        "top_symbols": top_symbols,
    }


def paper_weekly_consistency_summary(
    alpaca_journal: pd.DataFrame | list[Mapping[str, Any]] | None = None,
    crypto_journal: pd.DataFrame | list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    records, _duplicates_collapsed = paper_evidence_records(
        _journal_records(alpaca_journal) + _journal_records(crypto_journal)
    )
    rows: list[dict[str, Any]] = []
    for row in records:
        status = _text(row.get("status")).upper()
        outcome = _text(row.get("closed_outcome") or row.get("outcome")).upper()
        is_closed = status.startswith("CLOSED_") or outcome in {"HIT_2", "HIT_5", "HIT_10", "STOP"}
        if not is_closed:
            continue
        when = _parse_datetime(row.get("closed_at") or row.get("ts") or row.get("created_at"))
        if when is None:
            continue
        week_dt = when.tz_convert("UTC").tz_localize(None) if when.tzinfo else when
        move = _float(row.get("closed_move_pct") or row.get("move_pct"))
        rows.append(
            {
                "week": week_dt.to_period("W").start_time.date().isoformat(),
                "outcome": outcome,
                "move": move,
            }
        )

    if not rows:
        return {
            "weeks_observed": 0,
            "weeks_with_min_closed": 0,
            "consistent_weeks": 0,
            "weekly_rows": [],
            "consistent": False,
        }

    frame = pd.DataFrame(rows)
    weekly_rows: list[dict[str, Any]] = []
    for week, group in frame.groupby("week", sort=True):
        closed = int(len(group))
        hit_2 = int(group["outcome"].isin({"HIT_2", "HIT_5", "HIT_10"}).sum())
        stops = int((group["outcome"] == "STOP").sum())
        moves = pd.to_numeric(group["move"], errors="coerce").dropna()
        avg_move = float(moves.mean()) if not moves.empty else None
        hit_rate = _rate(hit_2, closed)
        stop_rate = _rate(stops, closed)
        week_consistent = (
            closed >= PROFITABILITY_MIN_CLOSED_PER_WEEK
            and hit_rate is not None
            and hit_rate >= PAPER_HIT_RATE_TARGET
            and (stop_rate is None or stop_rate <= (1.0 - PAPER_HIT_RATE_TARGET))
            and (avg_move is None or avg_move > 0)
        )
        weekly_rows.append(
            {
                "week": str(week),
                "closed": closed,
                "hit_2": hit_2,
                "stops": stops,
                "hit_2_rate": hit_rate,
                "stop_rate": stop_rate,
                "avg_closed_move_pct": avg_move,
                "consistent": bool(week_consistent),
            }
        )

    weeks_with_min_closed = sum(
        1 for row in weekly_rows if int(row.get("closed") or 0) >= PROFITABILITY_MIN_CLOSED_PER_WEEK
    )
    consistent_weeks = sum(1 for row in weekly_rows if row.get("consistent"))
    consistent = (
        len(weekly_rows) >= PROFITABILITY_MIN_WEEKS
        and weeks_with_min_closed >= PROFITABILITY_MIN_WEEKS
        and consistent_weeks >= PROFITABILITY_MIN_CONSISTENT_WEEKS
    )
    return {
        "weeks_observed": int(len(weekly_rows)),
        "weeks_with_min_closed": int(weeks_with_min_closed),
        "consistent_weeks": int(consistent_weeks),
        "weekly_rows": weekly_rows[-8:],
        "consistent": bool(consistent),
    }


def profitability_validation_status(
    *,
    paper_summary: Mapping[str, Any],
    backtest_summary: Mapping[str, Any] | None = None,
    weekly_summary: Mapping[str, Any] | None = None,
    measured: int = 0,
) -> dict[str, Any]:
    backtest = dict(backtest_summary or {})
    weekly = dict(weekly_summary or {})
    closed = int(paper_summary.get("closed") or 0)
    hit_rate = _float(paper_summary.get("hit_2_rate"))
    stop_rate = _float(paper_summary.get("stop_rate"))
    avg_move = _float(paper_summary.get("avg_closed_move_pct"))
    paper_edge = (
        closed >= PROFITABILITY_MIN_CLOSED
        and hit_rate is not None
        and hit_rate >= PAPER_HIT_RATE_TARGET
        and (stop_rate is None or stop_rate <= (1.0 - PAPER_HIT_RATE_TARGET))
        and (avg_move is None or avg_move > 0)
    )
    weekly_consistent = bool(weekly.get("consistent"))
    backtest_promising = bool(backtest.get("promising"))

    if paper_edge and weekly_consistent:
        stage = "PAPER_VALIDATED"
        evidence_grade = "A"
        headline = "Rentabilidad paper validada con muestra y consistencia semanal; aun no es garantia futura."
    elif paper_edge or closed >= 30:
        stage = "PAPER_VALIDATING"
        evidence_grade = "B"
        headline = "Roxy esta validando rentabilidad en paper; falta consistencia semanal suficiente para publicarla."
    elif backtest_promising:
        stage = "BACKTEST_PROMISING"
        evidence_grade = "C"
        headline = "Potencial por backtest; rentabilidad live todavia no esta probada."
    else:
        stage = "NOT_VALIDATED"
        evidence_grade = "D"
        headline = "Rentabilidad no comprobada; usar como investigacion y paper trading."

    return {
        "stage": stage,
        "evidence_grade": evidence_grade,
        "headline": headline,
        "can_claim_profitability": bool(paper_edge and weekly_consistent and measured >= PROFITABILITY_MIN_CLOSED),
        "paper_closed": closed,
        "paper_hit_2_rate": hit_rate,
        "paper_stop_rate": stop_rate,
        "paper_avg_closed_move_pct": avg_move,
        "backtest": backtest,
        "weekly": weekly,
    }


def subscription_scenarios(*, commission_rate: float = DEFAULT_APP_STORE_COMMISSION) -> list[dict[str, Any]]:
    tiers = [
        {"tier": "Beta Scanner", "price": 19.0, "paid_users": 100},
        {"tier": "Pro Trader", "price": 49.0, "paid_users": 1000},
        {"tier": "Desk", "price": 99.0, "paid_users": 2500},
    ]
    rows: list[dict[str, Any]] = []
    for tier in tiers:
        gross = tier["price"] * tier["paid_users"]
        net = gross * (1.0 - commission_rate)
        rows.append(
            {
                **tier,
                "gross_monthly": round(gross, 2),
                "net_monthly_after_store": round(net, 2),
                "commission_rate": commission_rate,
            }
        )
    return rows


def build_monetization_readiness_report(
    *,
    accuracy_report: Mapping[str, Any] | None = None,
    alpaca_journal: pd.DataFrame | list[Mapping[str, Any]] | None = None,
    crypto_journal: pd.DataFrame | list[Mapping[str, Any]] | None = None,
    live_status: Mapping[str, Any] | None = None,
    backtest_rows: pd.DataFrame | list[Mapping[str, Any]] | None = None,
    live_orders_enabled: bool = False,
    commission_rate: float = DEFAULT_APP_STORE_COMMISSION,
) -> dict[str, Any]:
    accuracy = dict(accuracy_report or {})
    headline = dict(accuracy.get("headline") or {})
    paper = combined_paper_monetization_summary(alpaca_journal, crypto_journal)
    live = dict(live_status or {})
    freshness = dict(live.get("source_freshness") or {})
    freshness_status = _text(freshness.get("status") or live.get("source_freshness_status")).upper()
    live_fresh = freshness_status in {"FRESH", "OK", "LIVE"} or bool(freshness.get("alerts_allowed"))
    measured = int(_float(headline.get("measured")) or 0)
    closed = int(paper.get("closed") or 0)
    tracked = int(paper.get("tracked") or 0)
    backtest = backtest_profitability_summary(backtest_rows)
    weekly = paper_weekly_consistency_summary(alpaca_journal, crypto_journal)
    profitability = profitability_validation_status(
        paper_summary=paper,
        backtest_summary=backtest,
        weekly_summary=weekly,
        measured=measured,
    )

    blockers: list[str] = []
    warnings: list[str] = []
    if not live_fresh:
        blockers.append("Validar que el feed live este fresco antes de vender alertas como tiempo real.")
    if live_orders_enabled:
        blockers.append("Ordenes reales deben seguir OFF para una beta comercial segura.")
    if closed < 30 and measured < 30:
        warnings.append("Todavia no hay suficientes resultados cerrados para publicar precision.")
    if tracked < BETA_MIN_TRACKED:
        warnings.append(f"Recolectar al menos {BETA_MIN_TRACKED} setups paper antes de abrir beta amplia.")

    beta_ready = live_fresh and not live_orders_enabled and tracked >= BETA_MIN_TRACKED
    signal_validated = (closed >= SIGNAL_VALIDATION_MIN_CLOSED or measured >= SIGNAL_VALIDATION_MIN_CLOSED) and not blockers

    if signal_validated:
        stage = "SIGNAL_VALIDATION_READY"
        product_positioning = "Scanner con senales paper validadas y metricas publicables."
    elif beta_ready:
        stage = "BETA_SCANNER_READY"
        product_positioning = "Scanner educativo live con paper trading, watchlists, alertas y dashboard."
    elif blockers:
        stage = "FOUNDATION_BLOCKED"
        product_positioning = "Producto interno hasta resolver datos live y seguridad."
    else:
        stage = "PRIVATE_ALPHA"
        product_positioning = "Alpha privada para recolectar evidencia antes de cobrar a publico amplio."

    next_actions = []
    if closed < SIGNAL_VALIDATION_MIN_CLOSED and measured < SIGNAL_VALIDATION_MIN_CLOSED:
        remaining = max(0, SIGNAL_VALIDATION_MIN_CLOSED - max(closed, measured))
        next_actions.append(f"Cerrar y etiquetar {remaining} senales paper mas antes de vender precision como metrica.")
    if not profitability.get("can_claim_profitability"):
        next_actions.append("Separar marketing de rentabilidad: hoy solo se puede mostrar evidencia, no prometer ganancias.")
    next_actions.append("Mantener copy comercial como analisis educativo/paper; no prometer ganancias ni asesoramiento personalizado.")
    next_actions.append("Mostrar siempre fuente, timestamp, entrada, stop, target, riesgo y estado de datos en cada oportunidad.")
    next_actions.append("Preparar beta con suscripcion mensual y feedback de usuarios antes de escalar App Store.")

    return {
        "stage": stage,
        "beta_ready": beta_ready,
        "signal_validated": signal_validated,
        "product_positioning": product_positioning,
        "can_sell_as": (
            "scanner educativo live + paper trading + dashboard de oportunidades"
            if stage in {"BETA_SCANNER_READY", "SIGNAL_VALIDATION_READY"}
            else "alpha privada de investigacion"
        ),
        "cannot_sell_as": "asesor financiero, garantia de ganancias, ni ejecucion automatica con dinero real",
        "paper_summary": paper,
        "accuracy_measured": measured,
        "profitability_validation": profitability,
        "live_fresh": live_fresh,
        "live_orders_enabled": bool(live_orders_enabled),
        "blockers": blockers,
        "warnings": warnings,
        "next_actions": next_actions,
        "subscription_scenarios": subscription_scenarios(commission_rate=commission_rate),
    }


__all__ = [
    "BETA_MIN_TRACKED",
    "DEFAULT_APP_STORE_COMMISSION",
    "MAX_ACCEPTABLE_DRAWDOWN",
    "PAPER_HIT_RATE_TARGET",
    "PROFITABILITY_MIN_CLOSED_PER_WEEK",
    "PROFITABILITY_MIN_CLOSED",
    "PROFITABILITY_MIN_CONSISTENT_WEEKS",
    "PROFITABILITY_MIN_WEEKS",
    "PROFIT_FACTOR_TARGET",
    "SIGNAL_VALIDATION_MIN_CLOSED",
    "backtest_profitability_summary",
    "build_monetization_readiness_report",
    "combined_paper_monetization_summary",
    "paper_journal_monetization_summary",
    "paper_evidence_records",
    "paper_weekly_consistency_summary",
    "profitability_validation_status",
    "subscription_scenarios",
]
