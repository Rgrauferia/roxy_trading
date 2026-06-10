from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


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
    market_value = str(market or "stock").lower()

    if stock_alerts_allowed is None:
        try:
            from roxy_ai import market_session_status

            stock_alerts_allowed = bool(market_session_status().get("stock_alerts_allowed"))
        except Exception:
            stock_alerts_allowed = True

    if market_value == "stock" and not stock_alerts_allowed and age_minutes <= max(24 * 60, expected * 8):
        label = "Mercado cerrado"
        tone = "watch"
        status = "WARN"
    elif age_minutes <= max(expected * 2.5, 10):
        label = "Viva"
        tone = "buy"
        status = "OK"
    elif age_minutes <= max(expected * 8, 45):
        label = "Revisar"
        tone = "watch"
        status = "WARN"
    else:
        label = "Estancada"
        tone = "avoid"
        status = "FAIL"

    return {
        "label": label,
        "tone": tone,
        "status": status,
        "detail": f"{age_minutes:.0f} min desde ultima vela",
        "age_minutes": age_minutes,
        "latest": latest_dt.strftime("%Y-%m-%d %H:%M"),
        "expected_minutes": expected,
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
    status = severity_max(freshness["status"], indicator_status, quality["status"])
    detail = freshness["detail"]
    if quality["status"] != "OK":
        detail = f"{detail}; calidad: {quality['detail']}"
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
        "rows": int(len(chart_df)),
        "has_rsi": bool(has_rsi),
        "has_macd": bool(has_macd),
        "indicator_status": indicator_status,
        "data_quality_status": quality["status"],
        "data_quality_detail": quality["detail"],
        "valid_ohlc_rows": quality["valid_ohlc_rows"],
        "duplicate_ts_count": quality["duplicate_ts_count"],
        "flat_close": quality["flat_close"],
        "volume_status": quality["volume_status"],
    }


def summarize_chart_health(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fail_count = sum(1 for row in rows if str(row.get("status")) == "FAIL")
    warn_count = sum(1 for row in rows if str(row.get("status")) == "WARN")
    stale_count = sum(1 for row in rows if str(row.get("label")) == "Estancada")
    missing_indicator_count = sum(1 for row in rows if str(row.get("indicator_status")) == "FAIL")
    data_quality_issue_count = sum(1 for row in rows if str(row.get("data_quality_status", "OK")) != "OK")
    age_values = [
        float(row.get("age_minutes"))
        for row in rows
        if row.get("age_minutes") is not None
    ]
    max_age_minutes = round(max(age_values), 1) if age_values else None
    avg_age_minutes = round(sum(age_values) / len(age_values), 1) if age_values else None
    stalest_chart = {}
    if age_values:
        stalest_chart = max(
            (row for row in rows if row.get("age_minutes") is not None),
            key=lambda row: float(row.get("age_minutes") or 0),
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
    top_issue = next((row for row in rows if str(row.get("status")) in {"FAIL", "WARN"}), {})
    return {
        "status": status,
        "label": label,
        "tone": tone,
        "checked_count": len(rows),
        "fail_count": fail_count,
        "warn_count": warn_count,
        "stale_count": stale_count,
        "missing_indicator_count": missing_indicator_count,
        "data_quality_issue_count": data_quality_issue_count,
        "max_age_minutes": max_age_minutes,
        "avg_age_minutes": avg_age_minutes,
        "stalest_chart": stalest_chart,
        "top_issue": top_issue,
    }


def write_chart_health_report(rows: list[dict[str, Any]], path: str | Path, *, generated_at: datetime | None = None) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    current = generated_at or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    payload = {
        "generated_at": current.isoformat(),
        "summary": summarize_chart_health(rows),
        "charts": rows,
    }
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return report_path
