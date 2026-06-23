from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roxy_paths import data_dir


DEFAULT_STRATEGY_OVERRIDES_PATH = data_dir() / "roxy_strategy_overrides.json"


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def load_strategy_overrides(path: str | Path = DEFAULT_STRATEGY_OVERRIDES_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text())
    except Exception:
        return {"version": 1, "strategy_overrides": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "strategy_overrides": {}}
    overrides = payload.get("strategy_overrides")
    if not isinstance(overrides, dict):
        payload["strategy_overrides"] = {}
    return payload


def override_for_row(row: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    family = safe_text(row.get("strategy_family") or row.get("salto_family") or row.get("trigger_setup"))
    rows = overrides.get("strategy_overrides") if isinstance(overrides.get("strategy_overrides"), dict) else {}
    found = rows.get(family)
    if not isinstance(found, dict):
        return {}
    if found.get("active") is False or safe_text(found.get("status")).upper() == "ROLLED_BACK":
        return {}
    return found


def apply_strategy_override_to_row(row: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    override = override_for_row(row, overrides)
    if not override:
        return dict(row)
    item = dict(row)
    action = safe_text(override.get("action")).upper()
    note = safe_text(override.get("reason"))
    item["autopilot_override"] = override
    item["autopilot_override_action"] = action
    item["autopilot_note"] = note
    if action in {"SHADOW_TEST", "TIGHTEN_FILTER"}:
        if safe_text(item.get("ai_action")).upper() == "ALERT":
            item["ai_action"] = "WATCH"
        item["alert_gate"] = "BLOCKED_BY_AUTOPILOT_SHADOW" if action == "SHADOW_TEST" else "BLOCKED_BY_AUTOPILOT_FILTER"
        blockers = item.get("alert_blockers") if isinstance(item.get("alert_blockers"), list) else []
        blocker = note or f"Autopilot {action} activo para {item.get('strategy_family')}"
        item["alert_blockers"] = [*blockers, blocker]
        readiness = safe_float(item.get("alert_readiness_score"))
        delta = safe_float(override.get("min_readiness_delta")) or 0.0
        if readiness is not None and delta:
            item["alert_readiness_score"] = max(0.0, readiness - delta)
    elif action == "PROMOTE_SHADOW":
        score = safe_float(item.get("ai_score"))
        weight = safe_float(override.get("ranking_weight")) or 1.0
        if score is not None:
            item["ai_score"] = int(max(0, min(100, round(score * weight))))
        item["autopilot_promotion_shadow"] = True
    return item


def apply_strategy_overrides_to_rows(rows: list[dict[str, Any]], overrides: dict[str, Any]) -> list[dict[str, Any]]:
    adjusted = [apply_strategy_override_to_row(row, overrides) for row in rows]
    adjusted.sort(
        key=lambda row: (
            safe_text(row.get("ai_action")).upper() == "ALERT",
            safe_float(row.get("alert_readiness_score")) or 0.0,
            safe_float(row.get("ai_score")) or 0.0,
        ),
        reverse=True,
    )
    return adjusted
