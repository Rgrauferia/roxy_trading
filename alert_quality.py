from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALERTS_DIR = Path("alerts")
DEFAULT_BRIEF_PATH = ALERTS_DIR / "roxy_ai_brief.json"
DEFAULT_REPORT_PATH = ALERTS_DIR / "alert_quality.json"
DEFAULT_HISTORY_PATH = ALERTS_DIR / "alert_quality_history.jsonl"
DEFAULT_HISTORY_LIMIT = 500


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_text(value: Any) -> str:
    return "" if value is None else str(value)


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_utc_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_history(path: Path = DEFAULT_HISTORY_PATH, *, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(errors="replace").splitlines()[-max(1, int(limit)) :]:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def append_history(path: Path, entry: dict[str, Any], *, limit: int = DEFAULT_HISTORY_LIMIT) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_history(path, limit=limit)
    rows.append(entry)
    rows = rows[-max(1, int(limit)) :]
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
    return len(rows)


def top_opportunity_snapshot(brief: dict[str, Any]) -> dict[str, Any]:
    opportunities = brief.get("top_opportunities")
    if not isinstance(opportunities, list) or not opportunities:
        opportunities = brief.get("opportunities")
    if not isinstance(opportunities, list) or not opportunities:
        return {}
    top = opportunities[0] if isinstance(opportunities[0], dict) else {}
    if not top:
        return {}
    smart_alert = top.get("smart_alert") if isinstance(top.get("smart_alert"), dict) else {}
    blockers = top.get("alert_blockers")
    if not isinstance(blockers, list):
        blockers = smart_alert.get("blockers") if isinstance(smart_alert.get("blockers"), list) else []
    return {
        "symbol": safe_text(top.get("symbol") or "-"),
        "market": safe_text(top.get("market") or "-"),
        "action": safe_text(top.get("ai_action") or top.get("action") or "-"),
        "trade_decision": safe_text(top.get("trade_decision") or "-"),
        "gate": safe_text(top.get("alert_gate") or smart_alert.get("gate") or "-"),
        "readiness": safe_float(top.get("alert_readiness_score") or smart_alert.get("readiness_score")),
        "quality": safe_text(top.get("alert_quality") or smart_alert.get("quality") or "-"),
        "primary_blocker": safe_text(top.get("alert_primary_blocker") or smart_alert.get("primary_blocker") or "-"),
        "next_action": safe_text(top.get("alert_next_action") or smart_alert.get("next_action") or "-"),
        "blockers": [safe_text(item) for item in blockers[:5]],
    }


def alert_quality_entry(brief: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    generated_at = safe_text(brief.get("generated_at")) or current.isoformat()
    gate_summary = brief.get("alert_gate_summary") if isinstance(brief.get("alert_gate_summary"), dict) else {}
    freshness = brief.get("source_freshness") if isinstance(brief.get("source_freshness"), dict) else {}
    realtime = brief.get("realtime_health") if isinstance(brief.get("realtime_health"), dict) else {}
    session = brief.get("market_session") if isinstance(brief.get("market_session"), dict) else {}
    total = int(gate_summary.get("total_opportunities") or len(brief.get("opportunities") or []) or 0)
    ready = int(gate_summary.get("notifications_ready") or 0)
    alert_count = int(gate_summary.get("alert_count") or brief.get("alert_count") or 0)
    watch_count = int(gate_summary.get("watch_count") or brief.get("watch_count") or 0)
    avg_readiness = safe_float(gate_summary.get("avg_readiness"))
    data_allowed = bool(freshness.get("alerts_allowed", True))
    realtime_allowed = bool(realtime.get("alerts_allowed", True))
    stock_allowed = bool(session.get("stock_alerts_allowed", True))
    blocked_realtime = int(gate_summary.get("blocked_realtime_count") or 0)
    top_setup = top_opportunity_snapshot(brief)

    if not data_allowed or not realtime_allowed:
        state = "BLOCKED_DATA"
    elif ready > 0:
        state = "READY"
    elif total <= 0:
        state = "NO_SETUPS"
    elif blocked_realtime:
        state = "BLOCKED_REALTIME"
    else:
        state = "WAITING"

    return {
        "generated_at": generated_at,
        "recorded_at": current.isoformat(),
        "state": state,
        "total_opportunities": total,
        "alert_count": alert_count,
        "watch_count": watch_count,
        "notifications_ready": ready,
        "ready_ratio": float(gate_summary.get("ready_ratio") or 0.0),
        "avg_readiness": avg_readiness,
        "top_gate": safe_text(gate_summary.get("top_gate") or "-"),
        "top_gate_label": safe_text(gate_summary.get("top_gate_label") or "-"),
        "top_blocker": safe_text(gate_summary.get("top_blocker") or "-"),
        "top_quality": safe_text(gate_summary.get("top_quality") or "-"),
        "top_readiness": safe_float(gate_summary.get("top_readiness")),
        "blocked_realtime_count": blocked_realtime,
        "data_alerts_allowed": data_allowed,
        "realtime_alerts_allowed": realtime_allowed,
        "stock_alerts_allowed": stock_allowed,
        "data_label": safe_text(freshness.get("label") or "-"),
        "health_label": safe_text(realtime.get("label") or "-"),
        "stock_session": safe_text(session.get("stock_session") or "-"),
        "top_setup": top_setup,
        "top_symbol": safe_text(top_setup.get("symbol") or "-") if top_setup else "-",
        "top_next_action": safe_text(top_setup.get("next_action") or "-") if top_setup else "-",
    }


def summarize_quality_history(rows: list[dict[str, Any]], *, limit: int = 50) -> dict[str, Any]:
    sample = list(rows)[-max(1, int(limit)) :]
    if not sample:
        return {
            "sample_size": 0,
            "state": "UNKNOWN",
            "ready_rate": None,
            "waiting_streak": 0,
            "current_streak_state": "UNKNOWN",
            "current_streak_count": 0,
        }
    state_counts: dict[str, int] = {}
    ready_count = 0
    readiness_values: list[float] = []
    for row in sample:
        state = safe_text(row.get("state") or "UNKNOWN").upper()
        state_counts[state] = state_counts.get(state, 0) + 1
        if int(row.get("notifications_ready") or 0) > 0 or state == "READY":
            ready_count += 1
        readiness = safe_float(row.get("avg_readiness"))
        if readiness is not None:
            readiness_values.append(readiness)
    latest = sample[-1]
    latest_state = safe_text(latest.get("state") or "UNKNOWN").upper()
    latest_blocker = safe_text(latest.get("top_blocker") or "-")
    latest_gate = safe_text(latest.get("top_gate_label") or latest.get("top_gate") or "-")
    streak = 0
    for row in reversed(sample):
        if safe_text(row.get("state") or "UNKNOWN").upper() == latest_state:
            streak += 1
        else:
            break
    blocker_streak = 0
    blocker_streak_started_at = None
    if latest_blocker and latest_blocker != "-":
        for row in reversed(sample):
            if safe_text(row.get("top_blocker") or "-") == latest_blocker:
                blocker_streak += 1
                blocker_streak_started_at = safe_text(row.get("recorded_at") or row.get("generated_at") or "")
            else:
                break
    gate_streak = 0
    if latest_gate and latest_gate != "-":
        for row in reversed(sample):
            gate = safe_text(row.get("top_gate_label") or row.get("top_gate") or "-")
            if gate == latest_gate:
                gate_streak += 1
            else:
                break
    blocked_minutes = None
    started_at = parse_utc_datetime(blocker_streak_started_at)
    latest_recorded_at = parse_utc_datetime(latest.get("recorded_at") or latest.get("generated_at"))
    if started_at is not None and latest_recorded_at is not None:
        blocked_minutes = round(max(0.0, (latest_recorded_at - started_at).total_seconds() / 60.0), 1)
    waiting_streak = streak if latest_state in {"WAITING", "NO_SETUPS"} else 0
    severity = "OK"
    diagnostic_label = "Normal"
    diagnostic_detail = "Alert quality operating normally"
    latest_ready = int(latest.get("notifications_ready") or 0)
    latest_total = int(latest.get("total_opportunities") or 0)
    if latest_state in {"BLOCKED_DATA", "BLOCKED_REALTIME"}:
        severity = "ATTENTION"
        diagnostic_label = "Datos bloquean"
        diagnostic_detail = latest_blocker if latest_blocker != "-" else latest_state
    elif latest_ready > 0 or latest_state == "READY":
        diagnostic_label = "Lista"
        diagnostic_detail = f"{latest_ready}/{latest_total} opportunities ready"
    elif latest_state == "WAITING" and latest_total > 0 and blocker_streak >= 12:
        severity = "ATTENTION"
        diagnostic_label = f"Bloqueador x{blocker_streak}"
        diagnostic_detail = latest_blocker
    elif latest_state == "WAITING" and latest_total > 0 and blocker_streak >= 3:
        severity = "WATCH"
        diagnostic_label = f"Bloqueador x{blocker_streak}"
        diagnostic_detail = latest_blocker
    elif latest_state == "NO_SETUPS":
        diagnostic_label = "Sin setups"
        diagnostic_detail = "No opportunities in current brief"
    return {
        "sample_size": len(sample),
        "state": latest_state,
        "state_counts": dict(sorted(state_counts.items(), key=lambda item: (-item[1], item[0]))),
        "ready_count": ready_count,
        "ready_rate": round(ready_count / len(sample), 4),
        "avg_readiness": round(sum(readiness_values) / len(readiness_values), 1) if readiness_values else None,
        "waiting_streak": waiting_streak,
        "current_streak_state": latest_state,
        "current_streak_count": streak,
        "latest_top_gate": latest_gate,
        "latest_top_blocker": latest_blocker,
        "latest_top_blocker_streak": blocker_streak,
        "latest_top_gate_streak": gate_streak,
        "persistent_blocker": latest_blocker if blocker_streak >= 3 and latest_blocker != "-" else "",
        "persistent_blocker_minutes": blocked_minutes,
        "diagnostic_severity": severity,
        "diagnostic_label": diagnostic_label,
        "diagnostic_detail": diagnostic_detail,
        "latest_notifications_ready": latest_ready,
        "latest_total_opportunities": latest_total,
    }


def build_alert_quality_report(
    brief: dict[str, Any],
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    now: datetime | None = None,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> dict[str, Any]:
    entry = alert_quality_entry(brief, now=now)
    previous = read_history(history_path, limit=history_limit)
    summary = summarize_quality_history([*previous, entry])
    return {
        "generated_at": entry["recorded_at"],
        "brief_generated_at": entry["generated_at"],
        "status": "OK",
        "entry": entry,
        "latest_entry": entry,
        "summary": summary,
        "history_path": str(history_path),
    }


def write_alert_quality_report(
    brief: dict[str, Any],
    *,
    report_path: Path = DEFAULT_REPORT_PATH,
    history_path: Path = DEFAULT_HISTORY_PATH,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    report = build_alert_quality_report(brief, history_path=history_path, now=now, history_limit=history_limit)
    count = append_history(history_path, report["entry"], limit=history_limit)
    report["history_count"] = count
    write_json(report_path, report)
    return report


def update_from_brief_file(
    *,
    brief_path: Path = DEFAULT_BRIEF_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> dict[str, Any]:
    brief = read_json(brief_path)
    if not brief:
        report = {
            "generated_at": utc_now().isoformat(),
            "status": "WARN",
            "detail": "Brief not found or unreadable",
            "brief_path": str(brief_path),
        }
        write_json(report_path, report)
        return report
    return write_alert_quality_report(brief, report_path=report_path, history_path=history_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Roxy alert quality report and history from the current AI brief.")
    parser.add_argument("--brief-path", default=str(DEFAULT_BRIEF_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--history-path", default=str(DEFAULT_HISTORY_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = update_from_brief_file(
        brief_path=Path(args.brief_path),
        report_path=Path(args.report_path),
        history_path=Path(args.history_path),
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
