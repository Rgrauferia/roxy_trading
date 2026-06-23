from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SYMBOL_KEYS = {"symbol", "top_symbol", "daily_plan_top_symbol"}
BLOCKED_CHART_GATES = {
    "BLOCKED_DATA",
    "BLOCKED_REALTIME_DATA",
    "BLOCKED_BY_MEMORY",
    "DATOS BLOQUEAN",
    "BLOQUEADO POR DATOS REALTIME",
}


def normalize_chart_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper().replace("$", "")
    if symbol in {"", "-", "N/A", "NA", "NONE", "NULL"}:
        return ""
    if "/" in symbol:
        parts = [part for part in symbol.split("/") if part]
        if len(parts) == 2 and all(part.replace("-", "").isalnum() for part in parts):
            return "/".join(parts)
        return ""
    if not symbol[0].isalpha():
        return ""
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    if any(char not in allowed for char in symbol):
        return ""
    return symbol[:16]


def active_chart_symbols_from_payloads(payloads: list[Any], *, limit: int = 8) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()

    def chart_candidate_blocked(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        gates = [
            value.get("state"),
            value.get("status_state"),
            value.get("market_state"),
            value.get("alert_gate"),
            value.get("gate"),
            value.get("top_gate"),
            value.get("daily_plan_top_gate"),
            value.get("label"),
            value.get("blocker"),
        ]
        for gate in gates:
            normalized = str(gate or "").strip().upper()
            if normalized in BLOCKED_CHART_GATES:
                return True
            if "DATOS REALTIME" in normalized and ("FALLO" in normalized or "BLOQUE" in normalized):
                return True
        return False

    def add(value: Any, *, blocked: bool = False) -> None:
        if blocked:
            return
        symbol = normalize_chart_symbol(value)
        if symbol and symbol not in seen and len(symbols) < limit:
            seen.add(symbol)
            symbols.append(symbol)

    def walk(value: Any, *, key: str = "") -> None:
        if len(symbols) >= limit:
            return
        if isinstance(value, dict):
            for item_key, item_value in value.items():
                if str(item_key) in SYMBOL_KEYS:
                    add(item_value, blocked=chart_candidate_blocked(value))
                elif str(item_key) in {"rows", "opportunities", "alerts", "watchlist"}:
                    walk(item_value, key=str(item_key))
        elif isinstance(value, list) and key in {"rows", "opportunities", "alerts", "watchlist"}:
            for item in value:
                walk(item, key=key)

    for payload in payloads:
        walk(payload)
        if len(symbols) >= limit:
            break
    return symbols


def active_chart_symbols_from_alerts(alerts_path: str | Path, *, limit: int = 8) -> list[str]:
    base = Path(alerts_path)
    payloads: list[Any] = []
    for name in ("roxy_ai_brief.json", "roxy_status.json", "roxy_daily_opportunity_plan.json"):
        path = base / name
        if not path.exists():
            continue
        try:
            payloads.append(json.loads(path.read_text()))
        except Exception:
            continue
    return active_chart_symbols_from_payloads(payloads, limit=limit)


def timeframe_minutes(timeframe: str) -> int:
    value = str(timeframe or "1h").strip().lower()
    if value.endswith("m"):
        try:
            return max(1, int(value[:-1]))
        except ValueError:
            return 60
    if value.endswith("h"):
        try:
            return max(1, int(value[:-1])) * 60
        except ValueError:
            return 60
    if value in {"1d", "d", "day", "daily"}:
        return 24 * 60
    return 60


def latest_chart_timestamp(chart_df: pd.DataFrame) -> pd.Timestamp | None:
    if chart_df.empty or "ts" not in chart_df.columns:
        return None
    values = pd.to_datetime(chart_df["ts"], errors="coerce").dropna()
    if values.empty:
        return None
    return values.max()


def severity_max(*statuses: str) -> str:
    order = {"OK": 0, "INFO": 0, "WARN": 1, "FAIL": 2}
    normalized = [str(status or "OK").upper() for status in statuses]
    return max(normalized, key=lambda status: order.get(status, 0)) if normalized else "OK"


def chart_data_quality_status(chart_df: pd.DataFrame, *, min_rows: int = 40) -> dict[str, Any]:
    if chart_df.empty:
        return {
            "status": "FAIL",
            "detail": "Sin filas",
            "valid_ohlc_rows": 0,
            "duplicate_ts_count": 0,
            "flat_close": True,
            "volume_status": "WARN",
        }

    required = ["ts", "open", "high", "low", "close"]
    missing = [column for column in required if column not in chart_df.columns]
    if missing:
        return {
            "status": "FAIL",
            "detail": "Faltan columnas " + ", ".join(missing),
            "valid_ohlc_rows": 0,
            "duplicate_ts_count": 0,
            "flat_close": True,
            "volume_status": "WARN",
        }

    data = chart_df.copy()
    data["ts"] = pd.to_datetime(data["ts"], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    valid = data.dropna(subset=required)
    valid_ohlc_rows = int(len(valid))
    duplicate_ts_count = int(valid["ts"].duplicated().sum()) if not valid.empty else 0
    issues: list[str] = []
    status = "OK"

    if valid_ohlc_rows < min_rows:
        issues.append(f"{valid_ohlc_rows} velas validas")
        status = "FAIL"

    if not valid.empty:
        price_cols = ["open", "high", "low", "close"]
        non_positive_count = int((valid[price_cols] <= 0).any(axis=1).sum())
        if non_positive_count:
            issues.append(f"{non_positive_count} velas con precio <= 0")
            status = "FAIL"
        inconsistent_count = int(
            (
                (valid["high"] < valid["low"])
                | (valid["high"] < valid[["open", "close"]].max(axis=1))
                | (valid["low"] > valid[["open", "close"]].min(axis=1))
            ).sum()
        )
        if inconsistent_count:
            issues.append(f"{inconsistent_count} velas OHLC invalidas")
            status = "FAIL"
        close = valid["close"].tail(max(min_rows, 20))
        reference = float(close.median()) if not close.empty else 0.0
        close_range = float(close.max() - close.min()) if not close.empty else 0.0
        flat_close = bool(reference <= 0 or close.nunique(dropna=True) <= 1 or (close_range / reference) < 0.00001)
        if flat_close:
            issues.append("cierre plano")
            status = severity_max(status, "FAIL")
    else:
        flat_close = True
        issues.append("sin OHLC valido")
        status = "FAIL"

    if duplicate_ts_count:
        issues.append(f"{duplicate_ts_count} timestamps duplicados")
        status = severity_max(status, "WARN")

    if "volume" in data.columns:
        volume = pd.to_numeric(data["volume"], errors="coerce").dropna()
        volume_status = "OK" if not volume.empty and (volume.tail(max(min_rows, 20)) > 0).any() else "WARN"
    else:
        volume_status = "WARN"
    if volume_status == "WARN":
        issues.append("volumen no confirma")
        status = severity_max(status, "WARN")

    return {
        "status": status,
        "detail": ", ".join(issues) if issues else f"{valid_ohlc_rows} velas OHLC validas",
        "valid_ohlc_rows": valid_ohlc_rows,
        "duplicate_ts_count": duplicate_ts_count,
        "flat_close": flat_close,
        "volume_status": volume_status,
    }


def chart_freshness_status(
    chart_df: pd.DataFrame,
    *,
    market: str,
    timeframe: str,
    now: datetime | None = None,
    stock_alerts_allowed: bool | None = None,
) -> dict[str, Any]:
    latest = latest_chart_timestamp(chart_df)
    if latest is None:
        return {
            "label": "Sin velas",
            "tone": "avoid",
            "status": "FAIL",
            "detail": "No hay timestamp",
            "age_minutes": None,
            "latest": "-",
        }

    latest_dt = latest.to_pydatetime()
    if latest_dt.tzinfo is not None:
        current = now or datetime.now(latest_dt.tzinfo)
        if current.tzinfo is None:
            current = current.replace(tzinfo=latest_dt.tzinfo)
    else:
        current = now or datetime.now()
        if current.tzinfo is not None:
            current = current.replace(tzinfo=None)
        latest_dt = latest_dt.replace(tzinfo=None)
    age_minutes = max(0.0, (current - latest_dt).total_seconds() / 60.0)
    expected = timeframe_minutes(timeframe)
    freshness_budget = max(expected * 2.5, 10)
    cadence_lag_minutes = max(0.0, age_minutes - expected)
    health_lag_minutes = max(0.0, age_minutes - freshness_budget)
    next_expected_update_in_minutes = max(0.0, expected - age_minutes)
    candle_progress_pct = min(100.0, max(0.0, (age_minutes / expected) * 100.0)) if expected > 0 else 0.0
    close_soon_threshold = max(1.0, min(5.0, expected * 0.2))
    market_value = str(market or "stock").lower()

    if stock_alerts_allowed is None:
        try:
            from roxy_ai import market_session_status

            stock_alerts_allowed = bool(market_session_status(now=current).get("stock_alerts_allowed"))
        except Exception:
            stock_alerts_allowed = True

    market_closed_freshness_budget = max(96 * 60, expected * 8)
    market_closed_accepted = (
        market_value == "stock"
        and not stock_alerts_allowed
        and age_minutes <= market_closed_freshness_budget
    )
    if market_closed_accepted:
        label = "Mercado cerrado"
        tone = "watch"
        status = "OK"
        cadence_lag_minutes = 0.0
        health_lag_minutes = 0.0
        next_expected_update_in_minutes = 0.0
        candle_phase = "MARKET_CLOSED"
        candle_phase_label = "Mercado cerrado"
    elif age_minutes <= freshness_budget:
        label = "Viva"
        tone = "buy"
        status = "OK"
        if cadence_lag_minutes > 0:
            candle_phase = "LATE_WITHIN_BUDGET"
            candle_phase_label = "Retraso leve"
        elif next_expected_update_in_minutes <= close_soon_threshold:
            candle_phase = "CLOSE_SOON"
            candle_phase_label = "Cierre cerca"
        elif candle_progress_pct <= 20.0:
            candle_phase = "NEW_CANDLE"
            candle_phase_label = "Vela nueva"
        else:
            candle_phase = "IN_PROGRESS"
            candle_phase_label = "Vela en curso"
    elif age_minutes <= max(expected * 8, 45):
        label = "Revisar"
        tone = "watch"
        status = "WARN"
        candle_phase = "LATE"
        candle_phase_label = "Vela retrasada"
    else:
        label = "Estancada"
        tone = "avoid"
        status = "FAIL"
        candle_phase = "STALE"
        candle_phase_label = "Sin pulso"

    return {
        "label": label,
        "tone": tone,
        "status": status,
        "detail": f"{age_minutes:.0f} min desde ultima vela",
        "age_minutes": age_minutes,
        "latest": latest_dt.strftime("%Y-%m-%d %H:%M"),
        "expected_minutes": expected,
        "freshness_budget_minutes": freshness_budget,
        "cadence_lag_minutes": cadence_lag_minutes,
        "health_lag_minutes": health_lag_minutes,
        "next_expected_update_in_minutes": next_expected_update_in_minutes,
        "candle_progress_pct": candle_progress_pct,
        "candle_phase": candle_phase,
        "candle_phase_label": candle_phase_label,
        "market_closed_accepted": market_closed_accepted,
    }


def chart_health_row(
    *,
    symbol: str,
    market: str,
    timeframe: str,
    chart_df: pd.DataFrame,
    now: datetime | None = None,
    stock_alerts_allowed: bool | None = None,
) -> dict[str, Any]:
    freshness = chart_freshness_status(
        chart_df,
        market=market,
        timeframe=timeframe,
        now=now,
        stock_alerts_allowed=stock_alerts_allowed,
    )
    has_rsi = "rsi14" in chart_df.columns and chart_df["rsi14"].notna().any()
    has_macd = "macd_hist" in chart_df.columns and chart_df["macd_hist"].notna().any()
    indicator_status = "OK" if len(chart_df) >= 40 and has_rsi and has_macd else "FAIL"
    quality = chart_data_quality_status(chart_df)
    quality_status = quality["status"]
    quality_detail = quality["detail"]
    quality_grace = False
    try:
        candle_progress_pct = float(freshness.get("candle_progress_pct") or 0.0)
    except (TypeError, ValueError):
        candle_progress_pct = 0.0
    if (
        quality_status == "FAIL"
        and bool(quality.get("flat_close"))
        and quality_detail == "cierre plano"
        and freshness.get("status") == "OK"
        and freshness.get("candle_phase") == "NEW_CANDLE"
        and candle_progress_pct <= 20.0
    ):
        quality_status = "WARN"
        quality_detail = "cierre plano en vela nueva; revalidar al cierre"
        quality_grace = True
    status = severity_max(freshness["status"], indicator_status, quality_status)
    detail = freshness["detail"]
    if quality_status != "OK":
        detail = f"{detail}; calidad: {quality_detail}"
    tone = "avoid" if status == "FAIL" else "watch" if status == "WARN" else freshness["tone"]
    return {
        "symbol": str(symbol).upper(),
        "market": str(market or "stock").lower(),
        "timeframe": str(timeframe or "1h"),
        "status": status,
        "label": freshness["label"],
        "tone": tone,
        "detail": detail,
        "age_minutes": freshness["age_minutes"],
        "latest": freshness["latest"],
        "expected_minutes": freshness.get("expected_minutes"),
        "freshness_budget_minutes": freshness.get("freshness_budget_minutes"),
        "cadence_lag_minutes": freshness.get("cadence_lag_minutes"),
        "health_lag_minutes": freshness.get("health_lag_minutes"),
        "next_expected_update_in_minutes": freshness.get("next_expected_update_in_minutes"),
        "candle_progress_pct": freshness.get("candle_progress_pct"),
        "candle_phase": freshness.get("candle_phase"),
        "candle_phase_label": freshness.get("candle_phase_label"),
        "market_closed_accepted": freshness.get("market_closed_accepted"),
        "rows": int(len(chart_df)),
        "has_rsi": bool(has_rsi),
        "has_macd": bool(has_macd),
        "indicator_status": indicator_status,
        "data_quality_status": quality_status,
        "data_quality_detail": quality_detail,
        "data_quality_grace": quality_grace,
        "valid_ohlc_rows": quality["valid_ohlc_rows"],
        "duplicate_ts_count": quality["duplicate_ts_count"],
        "flat_close": quality["flat_close"],
        "volume_status": quality["volume_status"],
    }


def chart_freshness_margin_state(
    margin_minutes: float | None,
    budget_minutes: float | None,
) -> tuple[str, float | None]:
    if margin_minutes is None or budget_minutes is None or budget_minutes <= 0:
        return "UNKNOWN", None
    warn_threshold = min(10.0, max(2.0, float(budget_minutes) * 0.2))
    if margin_minutes <= 0:
        return "STALE", round(warn_threshold, 1)
    if margin_minutes <= warn_threshold:
        return "WATCH", round(warn_threshold, 1)
    return "OK", round(warn_threshold, 1)


def _chart_freshness_margin_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    margin_rows: list[dict[str, Any]] = []
    for row in rows:
        try:
            age_minutes = float(row.get("age_minutes"))
            budget_minutes = float(row.get("freshness_budget_minutes"))
        except (TypeError, ValueError):
            continue
        if budget_minutes <= 0:
            continue
        margin_minutes = budget_minutes - age_minutes
        margin_rows.append(
            {
                "symbol": row.get("symbol"),
                "timeframe": row.get("timeframe"),
                "market": row.get("market"),
                "age_minutes": round(age_minutes, 1),
                "freshness_budget_minutes": round(budget_minutes, 1),
                "margin_minutes": round(margin_minutes, 1),
                "margin_ratio": round(margin_minutes / budget_minutes, 4),
                "market_closed_accepted": bool(row.get("market_closed_accepted")),
            }
        )
    return margin_rows


def summarize_chart_health(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fail_count = sum(1 for row in rows if str(row.get("status")) == "FAIL")
    raw_warn_count = sum(1 for row in rows if str(row.get("status")) == "WARN")
    market_closed_ok_count = sum(
        1
        for row in rows
        if str(row.get("label")) == "Mercado cerrado"
        and str(row.get("status")) in {"OK", "WARN"}
        and str(row.get("indicator_status")) == "OK"
        and str(row.get("data_quality_status", "OK")) == "OK"
        and float(row.get("health_lag_minutes") or 0.0) <= 0.0
    )
    market_closed_warn_count = sum(
        1
        for row in rows
        if str(row.get("status")) == "WARN"
        and str(row.get("label")) == "Mercado cerrado"
        and str(row.get("indicator_status")) == "OK"
        and str(row.get("data_quality_status", "OK")) == "OK"
        and float(row.get("health_lag_minutes") or 0.0) <= 0.0
    )
    warn_count = max(0, raw_warn_count - market_closed_warn_count)
    stale_count = sum(1 for row in rows if str(row.get("label")) == "Estancada")
    missing_indicator_count = sum(1 for row in rows if str(row.get("indicator_status")) == "FAIL")
    data_quality_issue_count = sum(1 for row in rows if str(row.get("data_quality_status", "OK")) != "OK")
    age_values = [
        float(row.get("age_minutes"))
        for row in rows
        if row.get("age_minutes") is not None
    ]
    operable_rows = [row for row in rows if not bool(row.get("market_closed_accepted"))]
    operable_age_values = [
        float(row.get("age_minutes"))
        for row in operable_rows
        if row.get("age_minutes") is not None
    ]
    max_age_minutes = round(max(age_values), 1) if age_values else None
    avg_age_minutes = round(sum(age_values) / len(age_values), 1) if age_values else None
    operable_max_age_minutes = round(max(operable_age_values), 1) if operable_age_values else None
    operable_avg_age_minutes = (
        round(sum(operable_age_values) / len(operable_age_values), 1) if operable_age_values else None
    )
    cadence_lag_values = [
        float(row.get("cadence_lag_minutes"))
        for row in rows
        if row.get("cadence_lag_minutes") is not None
    ]
    operable_cadence_lag_values = [
        float(row.get("cadence_lag_minutes"))
        for row in operable_rows
        if row.get("cadence_lag_minutes") is not None
    ]
    health_lag_values = [
        float(row.get("health_lag_minutes"))
        for row in rows
        if row.get("health_lag_minutes") is not None
    ]
    operable_health_lag_values = [
        float(row.get("health_lag_minutes"))
        for row in operable_rows
        if row.get("health_lag_minutes") is not None
    ]
    next_update_values = [
        float(row.get("next_expected_update_in_minutes"))
        for row in rows
        if row.get("next_expected_update_in_minutes") is not None and float(row.get("next_expected_update_in_minutes") or 0) > 0
    ]
    operable_next_update_values = [
        float(row.get("next_expected_update_in_minutes"))
        for row in operable_rows
        if row.get("next_expected_update_in_minutes") is not None
        and float(row.get("next_expected_update_in_minutes") or 0) > 0
    ]
    max_cadence_lag_minutes = round(max(cadence_lag_values), 1) if cadence_lag_values else None
    operable_max_cadence_lag_minutes = (
        round(max(operable_cadence_lag_values), 1) if operable_cadence_lag_values else None
    )
    max_health_lag_minutes = round(max(health_lag_values), 1) if health_lag_values else None
    operable_max_health_lag_minutes = (
        round(max(operable_health_lag_values), 1) if operable_health_lag_values else None
    )
    next_expected_update_in_minutes = round(min(next_update_values), 1) if next_update_values else None
    operable_next_expected_update_in_minutes = (
        round(min(operable_next_update_values), 1) if operable_next_update_values else None
    )
    stalest_chart = {}
    if age_values:
        stalest_chart = max(
            (row for row in rows if row.get("age_minutes") is not None),
            key=lambda row: float(row.get("age_minutes") or 0),
        )
    operable_stalest_chart = {}
    if operable_age_values:
        operable_stalest_chart = max(
            (row for row in operable_rows if row.get("age_minutes") is not None),
            key=lambda row: float(row.get("age_minutes") or 0),
        )
    most_overdue_chart = {}
    if cadence_lag_values and max(cadence_lag_values) > 0:
        most_overdue_chart = max(
            (row for row in rows if row.get("cadence_lag_minutes") is not None),
            key=lambda row: float(row.get("cadence_lag_minutes") or 0),
        )
    operable_most_overdue_chart = {}
    if operable_cadence_lag_values and max(operable_cadence_lag_values) > 0:
        operable_most_overdue_chart = max(
            (row for row in operable_rows if row.get("cadence_lag_minutes") is not None),
            key=lambda row: float(row.get("cadence_lag_minutes") or 0),
        )
    freshness_margin_rows = _chart_freshness_margin_rows(rows)
    min_freshness_margin_chart = (
        min(freshness_margin_rows, key=lambda row: float(row.get("margin_minutes") or 0.0))
        if freshness_margin_rows
        else {}
    )
    operable_freshness_margin_rows = [
        row for row in freshness_margin_rows if not bool(row.get("market_closed_accepted"))
    ]
    operable_min_freshness_margin_chart = (
        min(operable_freshness_margin_rows, key=lambda row: float(row.get("margin_minutes") or 0.0))
        if operable_freshness_margin_rows
        else {}
    )
    operable_min_freshness_margin_minutes = operable_min_freshness_margin_chart.get("margin_minutes")
    operable_min_freshness_budget_minutes = operable_min_freshness_margin_chart.get(
        "freshness_budget_minutes"
    )
    operable_freshness_margin_state, operable_freshness_margin_warn_threshold_minutes = (
        chart_freshness_margin_state(
            float(operable_min_freshness_margin_minutes)
            if operable_min_freshness_margin_minutes is not None
            else None,
            float(operable_min_freshness_budget_minutes)
            if operable_min_freshness_budget_minutes is not None
            else None,
        )
    )
    if fail_count:
        status = "FAIL"
        label = "Graficas fallan"
        tone = "avoid"
    elif warn_count:
        status = "WARN"
        label = "Graficas revisar"
        tone = "watch"
    elif rows:
        status = "OK"
        label = "Graficas vivas"
        tone = "buy"
    else:
        status = "WARN"
        label = "Sin graficas"
        tone = "watch"
    top_issue = next(
        (
            row
            for row in rows
            if str(row.get("status")) == "FAIL"
            or (
                str(row.get("status")) == "WARN"
                and not (
                    str(row.get("label")) == "Mercado cerrado"
                    and str(row.get("indicator_status")) == "OK"
                    and str(row.get("data_quality_status", "OK")) == "OK"
                    and float(row.get("health_lag_minutes") or 0.0) <= 0.0
                )
            )
        ),
        {},
    )
    return {
        "status": status,
        "label": label,
        "tone": tone,
        "checked_count": len(rows),
        "operable_checked_count": len(operable_rows),
        "fail_count": fail_count,
        "warn_count": warn_count,
        "market_closed_ok_count": market_closed_ok_count,
        "stale_count": stale_count,
        "missing_indicator_count": missing_indicator_count,
        "data_quality_issue_count": data_quality_issue_count,
        "max_age_minutes": max_age_minutes,
        "avg_age_minutes": avg_age_minutes,
        "operable_max_age_minutes": operable_max_age_minutes,
        "operable_avg_age_minutes": operable_avg_age_minutes,
        "max_cadence_lag_minutes": max_cadence_lag_minutes,
        "operable_max_cadence_lag_minutes": operable_max_cadence_lag_minutes,
        "max_health_lag_minutes": max_health_lag_minutes,
        "operable_max_health_lag_minutes": operable_max_health_lag_minutes,
        "min_freshness_margin_minutes": min_freshness_margin_chart.get("margin_minutes"),
        "min_freshness_margin_ratio": min_freshness_margin_chart.get("margin_ratio"),
        "min_freshness_budget_minutes": min_freshness_margin_chart.get("freshness_budget_minutes"),
        "min_freshness_margin_chart": min_freshness_margin_chart,
        "operable_min_freshness_margin_minutes": operable_min_freshness_margin_minutes,
        "operable_min_freshness_margin_ratio": operable_min_freshness_margin_chart.get("margin_ratio"),
        "operable_min_freshness_budget_minutes": operable_min_freshness_budget_minutes,
        "operable_freshness_margin_state": operable_freshness_margin_state,
        "operable_freshness_margin_warn_threshold_minutes": (
            operable_freshness_margin_warn_threshold_minutes
        ),
        "operable_min_freshness_margin_chart": operable_min_freshness_margin_chart,
        "next_expected_update_in_minutes": next_expected_update_in_minutes,
        "operable_next_expected_update_in_minutes": operable_next_expected_update_in_minutes,
        "stalest_chart": stalest_chart,
        "operable_stalest_chart": operable_stalest_chart,
        "most_overdue_chart": most_overdue_chart,
        "operable_most_overdue_chart": operable_most_overdue_chart,
        "top_issue": top_issue,
    }


def write_chart_health_report(rows: list[dict[str, Any]], path: str | Path, *, generated_at: datetime | None = None) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    current = generated_at or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    summary = summarize_chart_health(rows)
    payload = {
        "generated_at": current.isoformat(),
        **summary,
        "checked": summary.get("checked_count"),
        "max_chart_age_minutes": summary.get("max_age_minutes"),
        "operable_max_chart_age_minutes": summary.get("operable_max_age_minutes"),
        "next_candle_minutes": summary.get("next_expected_update_in_minutes"),
        "operable_next_candle_minutes": summary.get("operable_next_expected_update_in_minutes"),
        "summary": summary,
        "charts": rows,
    }
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return report_path
