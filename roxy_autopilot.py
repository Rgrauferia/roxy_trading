from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from accuracy_tracker import build_accuracy_report
from roxy_ai import autonomous_learning_plan, load_memory
from roxy_paths import alerts_dir, data_dir, project_path


AUTOPILOT_STATUS_PATH = alerts_dir() / "roxy_autopilot_status.json"
AUTOPILOT_PROPOSALS_DIR = alerts_dir() / "autopilot_proposals"
STRATEGY_OVERRIDES_PATH = data_dir() / "roxy_strategy_overrides.json"
CODE_WRITE_ENV = "ROXY_AUTOPILOT_CODE_WRITE"
DEFAULT_STREAMLIT_URL = "http://localhost:3000/_stcore/health"
MAX_APPLIED_PER_RUN = 5
AUTOHEAL_TIMEOUT_SECONDS = 90
AUTOHEAL_MAX_AGE_SECONDS = 300
ROLLBACK_MIN_MEASURED_SIGNALS = 3
ROLLBACK_HIT_2_RATE = 0.60
ROLLBACK_MAX_STOP_RATE = 0.35
CONFIRM_FILTER_STOP_RATE = 0.50
CONFIRM_FILTER_MAX_HIT_2_RATE = 0.35
STOP_STATUSES = {"STOP", "STOPPED", "STOP_HIT", "HIT_STOP"}
HIT_STATUSES = {"HIT_2PCT", "HIT_5PCT", "HIT_10PCT"}


def autopilot_python_path() -> str:
    venv_python = project_path(".venv/bin/python")
    return str(venv_python) if venv_python.exists() else sys.executable


AUTOHEAL_TARGETS: dict[str, dict[str, Any]] = {
    "roxy_ai_brief": {
        "path": alerts_dir() / "roxy_ai_brief.json",
        "max_age_seconds": AUTOHEAL_MAX_AGE_SECONDS,
        "command": lambda python: [python, str(project_path("tools/roxy_ai_watch.py"))],
    },
    "alert_quality": {
        "path": alerts_dir() / "alert_quality.json",
        "max_age_seconds": AUTOHEAL_MAX_AGE_SECONDS,
        "command": lambda python: [python, str(project_path("alert_quality.py"))],
    },
    "chart_realtime_health": {
        "path": alerts_dir() / "chart_realtime_health.json",
        "max_age_seconds": AUTOHEAL_MAX_AGE_SECONDS,
        "command": lambda python: [
            python,
            str(project_path("tools/chart_realtime_health.py")),
            "--include-active-alert-symbols",
            "--no-fail",
        ],
    },
    "realtime_check": {
        "path": alerts_dir() / "roxy_realtime_check.json",
        "max_age_seconds": AUTOHEAL_MAX_AGE_SECONDS,
        "command": lambda python: [
            python,
            str(project_path("tools/roxy_realtime_check.py")),
            "--app-url",
            "http://127.0.0.1:3000",
            "--ensure-chart-health-report",
            "--ensure-alert-quality-report",
            "--ensure-daily-opportunity-plan-report",
            "--ensure-status-snapshot-report",
            "--no-fail",
        ],
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None


def env_enabled(env: dict[str, str] | None = None, *, key: str = CODE_WRITE_ENV) -> bool:
    source = env if env is not None else os.environ
    raw = str(source.get(key) or "").strip().lower()
    return raw in {"1", "true", "yes", "on", "apply", "write"}


def load_json(path: str | Path, default: Any) -> Any:
    p = Path(path)
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def write_json_with_backup(path: str | Path, payload: Any) -> Path | None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if p.exists():
        backup_path = p.with_suffix(p.suffix + f".bak.{utc_now().strftime('%Y%m%d%H%M%S%f')}")
        shutil.copy2(p, backup_path)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return backup_path


def file_age_seconds(path: str | Path, *, now: datetime | None = None) -> int | None:
    p = Path(path)
    if not p.exists():
        return None
    current = now or utc_now()
    modified = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
    return max(0, int((current - modified).total_seconds()))


def streamlit_health(url: str = DEFAULT_STREAMLIT_URL, *, timeout: float = 1.5) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="ignore").strip().lower()
            ok = int(getattr(response, "status", 0) or 0) == 200 and body == "ok"
            return {"status": "OK" if ok else "WARN", "detail": body or "empty", "url": url}
    except (OSError, URLError, TimeoutError, ValueError) as exc:
        return {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}", "url": url}


def alpaca_market_data_status(symbol: str = "AAPL") -> dict[str, Any]:
    try:
        from living_market import build_alpaca_market_data_diagnostic

        diagnostic = build_alpaca_market_data_diagnostic(symbol)
        return {
            "status": diagnostic.get("status", "FAIL"),
            "error_category": diagnostic.get("error_category") or "",
            "feed": diagnostic.get("feed") or "",
            "safe_for_signals": bool(diagnostic.get("safe_for_signals")),
            "next_action": diagnostic.get("next_action") or "",
        }
    except Exception as exc:
        return {
            "status": "FAIL",
            "error_category": "DIAGNOSTIC_ERROR",
            "feed": "",
            "safe_for_signals": False,
            "next_action": f"Revisar living_market diagnostic: {type(exc).__name__}: {exc}",
        }


def build_health_snapshot(*, now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    file_rows = []
    for name, target in AUTOHEAL_TARGETS.items():
        path = Path(target["path"])
        age = file_age_seconds(path, now=current)
        max_age = int(target.get("max_age_seconds") or AUTOHEAL_MAX_AGE_SECONDS)
        if age is None:
            status = "FAIL"
            detail = "missing"
        elif age <= 120:
            status = "OK"
            detail = f"{age}s"
        elif age <= max_age:
            status = "WARN"
            detail = f"{age}s"
        else:
            status = "STALE"
            detail = f"{age}s"
        file_rows.append(
            {
                "name": name,
                "status": status,
                "age_seconds": age,
                "max_age_seconds": max_age,
                "detail": detail,
                "path": str(path),
            }
        )

    streamlit = streamlit_health()
    alpaca = alpaca_market_data_status()
    failing = [row for row in file_rows if row["status"] in {"FAIL", "STALE"}]
    status = "OK"
    if streamlit["status"] == "FAIL" or failing:
        status = "WARN"
    if alpaca["status"] == "FAIL":
        status = "WARN"
    return {
        "status": status,
        "generated_at": current.isoformat(),
        "streamlit": streamlit,
        "alpaca_market_data": alpaca,
        "files": file_rows,
        "issues": [f"{row['name']}:{row['status']}" for row in failing],
    }


def proposal_id(action: str, family: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in f"{action}_{family}")
    return "_".join(part for part in cleaned.split("_") if part)


def strategy_override_from_learning_action(action: dict[str, Any]) -> dict[str, Any] | None:
    family = safe_text(action.get("strategy_family"))
    plan_action = safe_text(action.get("action")).upper()
    if not family:
        return None
    evidence = safe_float(action.get("evidence_score")) or 0.0
    if plan_action == "TIGHTEN_FILTER":
        return {
            "strategy_family": family,
            "action": "TIGHTEN_FILTER",
            "status": "ACTIVE",
            "active": True,
            "mode": "PAPER_ONLY",
            "min_readiness_delta": 10,
            "risk_multiplier": 0.75,
            "max_position_scale": 0.0,
            "reason": action.get("why") or action.get("proposed_rule"),
            "evidence_score": round(evidence, 4),
        }
    if plan_action == "PROMOTE_IN_RANKING":
        return {
            "strategy_family": family,
            "action": "PROMOTE_SHADOW",
            "status": "ACTIVE",
            "active": True,
            "mode": "PAPER_ONLY",
            "ranking_weight": 1.1,
            "max_position_scale": 0.0,
            "reason": action.get("why") or action.get("proposed_rule"),
            "evidence_score": round(evidence, 4),
        }
    if plan_action.startswith("SHADOW_TEST_"):
        return {
            "strategy_family": family,
            "action": "SHADOW_TEST",
            "status": "ACTIVE",
            "active": True,
            "mode": "PAPER_ONLY",
            "max_position_scale": 0.0,
            "reason": action.get("why") or action.get("proposed_rule"),
            "evidence_score": round(evidence, 4),
        }
    return None


def build_improvement_proposals(
    memory: dict[str, Any],
    *,
    existing_overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    accuracy = build_accuracy_report(memory, minimum_sample=30, minimum_strategy_alerts=10)
    learning_plan = autonomous_learning_plan(memory)
    current_rows = (
        existing_overrides.get("strategy_overrides")
        if isinstance(existing_overrides, dict) and isinstance(existing_overrides.get("strategy_overrides"), dict)
        else {}
    )
    proposals: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for action in learning_plan:
        override = strategy_override_from_learning_action(action)
        if not override:
            continue
        family = override["strategy_family"]
        current = current_rows.get(family) if isinstance(current_rows.get(family), dict) else {}
        if safe_text(current.get("status")).upper() == "ROLLED_BACK":
            continue
        current_id = proposal_id(override["action"], family)
        if current_id in seen_ids:
            continue
        seen_ids.add(current_id)
        proposals.append(
            {
                "id": current_id,
                "type": "strategy_override",
                "status": "READY",
                "title": f"{override['action']} para {family}",
                "risk": "LOW",
                "safety_mode": "PAPER_ONLY",
                "requires_env": CODE_WRITE_ENV,
                "target_path": str(STRATEGY_OVERRIDES_PATH),
                "override": override,
                "tests": ["python -m pytest tests/test_roxy_autopilot.py -q"],
                "source": "autonomous_learning_plan",
            }
        )

    if not proposals and accuracy.get("headline", {}).get("sample_status") == "NEEDS_DATA":
        proposals.append(
            {
                "id": "collect_more_signal_data",
                "type": "learning_task",
                "status": "WAITING_FOR_DATA",
                "title": "Recolectar mas resultados antes de modificar estrategias",
                "risk": "LOW",
                "safety_mode": "PAPER_ONLY",
                "requires_env": "",
                "target_path": "",
                "override": {},
                "tests": [],
                "source": "accuracy_tracker",
            }
        )
    return proposals[:20]


def autoheal_needed_targets(health: dict[str, Any]) -> list[str]:
    names = []
    for row in health.get("files") or []:
        if not isinstance(row, dict):
            continue
        name = safe_text(row.get("name"))
        age = safe_float(row.get("age_seconds"))
        max_age = safe_float(row.get("max_age_seconds")) or AUTOHEAL_MAX_AGE_SECONDS
        status = safe_text(row.get("status")).upper()
        if name in AUTOHEAL_TARGETS and (status in {"FAIL", "STALE"} or (age is not None and age > max_age)):
            names.append(name)
    return names


def run_autoheal_command(name: str, *, timeout_seconds: int = AUTOHEAL_TIMEOUT_SECONDS) -> dict[str, Any]:
    target = AUTOHEAL_TARGETS.get(name)
    if not target:
        return {"name": name, "status": "SKIPPED", "ok": False, "detail": "target not allowlisted"}
    command_builder = target.get("command")
    if not callable(command_builder):
        return {"name": name, "status": "SKIPPED", "ok": False, "detail": "missing command builder"}
    command = list(command_builder(autopilot_python_path()))
    started = time.time()
    try:
        result = subprocess.run(command, cwd=str(project_path(".")), text=True, capture_output=True, timeout=timeout_seconds)
        duration = round(time.time() - started, 3)
        output = (result.stdout or result.stderr or "").strip()
        return {
            "name": name,
            "status": "OK" if result.returncode == 0 else "FAIL",
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "duration_seconds": duration,
            "command": command,
            "output": output[-1200:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "status": "TIMEOUT",
            "ok": False,
            "returncode": None,
            "duration_seconds": round(time.time() - started, 3),
            "command": command,
            "output": safe_text(exc),
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "FAIL",
            "ok": False,
            "returncode": None,
            "duration_seconds": round(time.time() - started, 3),
            "command": command,
            "output": f"{type(exc).__name__}: {exc}",
        }


def autoheal_stale_reports(
    health: dict[str, Any],
    *,
    enabled: bool = True,
    timeout_seconds: int = AUTOHEAL_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    targets = autoheal_needed_targets(health)
    if not enabled:
        return [
            {
                "name": name,
                "status": "SKIPPED",
                "ok": False,
                "detail": "autoheal disabled",
                "command": list(AUTOHEAL_TARGETS[name]["command"](autopilot_python_path())),
            }
            for name in targets
        ]
    actions = []
    for name in targets:
        actions.append(run_autoheal_command(name, timeout_seconds=timeout_seconds))
    return actions


def write_proposal_files(proposals: list[dict[str, Any]], *, directory: Path = AUTOPILOT_PROPOSALS_DIR) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for proposal in proposals:
        path = directory / f"{proposal['id']}.json"
        path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
        written.append(str(path))
    return written


def apply_strategy_override(proposal: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    target_path = path or STRATEGY_OVERRIDES_PATH
    override = proposal.get("override") if isinstance(proposal.get("override"), dict) else {}
    family = safe_text(override.get("strategy_family"))
    if not family:
        return {"applied": False, "reason": "missing strategy_family"}
    state = load_json(target_path, {"version": 1, "updated_at": "", "strategy_overrides": {}})
    overrides = state.setdefault("strategy_overrides", {})
    current = dict(overrides.get(family) or {})
    if (
        current.get("active") is True
        and safe_text(current.get("status")).upper() == "ACTIVE"
        and safe_text(current.get("action")).upper() == safe_text(override.get("action")).upper()
    ):
        return {
            "applied": False,
            "path": str(target_path),
            "reason": "override already active",
            "proposal_id": current.get("proposal_id") or proposal.get("id"),
        }
    current.update(override)
    current.setdefault("created_at", iso_now())
    current.setdefault("tracking", {})
    current["active"] = True
    current["status"] = safe_text(current.get("status")) or "ACTIVE"
    current["updated_at"] = iso_now()
    current["proposal_id"] = proposal.get("id")
    overrides[family] = current
    state["updated_at"] = iso_now()
    backup = write_json_with_backup(target_path, state)
    return {"applied": True, "path": str(target_path), "backup_path": str(backup) if backup else ""}


def signal_milestones(signal: dict[str, Any]) -> set[str]:
    values = set()
    raw = signal.get("milestones") or signal.get("recorded_milestones") or []
    if isinstance(raw, str):
        raw = [raw]
    for item in raw:
        text = safe_text(item)
        if text:
            values.add(text)
    status = safe_text(signal.get("status")).upper()
    if status == "HIT_10PCT":
        values.update({"2%", "5%", "10%"})
    elif status == "HIT_5PCT":
        values.update({"2%", "5%"})
    elif status == "HIT_2PCT":
        values.add("2%")
    return values


def family_signal_metrics(memory: dict[str, Any], family: str) -> dict[str, Any]:
    rows = []
    for row in memory.get("signal_journal") or []:
        if safe_text(row.get("strategy_family")) == family:
            rows.append(row)
    tracked = len(rows)
    hit_2 = 0
    stops = 0
    measured = 0
    for row in rows:
        status = safe_text(row.get("status")).upper()
        milestones = signal_milestones(row)
        row_hit_2 = "2%" in milestones or status in HIT_STATUSES
        row_stop = status in STOP_STATUSES or bool(row.get("stopped_before_target"))
        if row_hit_2:
            hit_2 += 1
        if row_stop:
            stops += 1
        if row_hit_2 or row_stop:
            measured += 1
    hit_2_rate = hit_2 / measured if measured else None
    stop_rate = stops / measured if measured else None
    return {
        "tracked": tracked,
        "measured": measured,
        "hit_2": hit_2,
        "stops": stops,
        "hit_2_rate": hit_2_rate,
        "stop_rate": stop_rate,
    }


def review_override_row(family: str, override: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    metrics = family_signal_metrics(memory, family)
    action = safe_text(override.get("action")).upper()
    current_status = safe_text(override.get("status")).upper() or "ACTIVE"
    measured = int(metrics.get("measured") or 0)
    hit_rate = safe_float(metrics.get("hit_2_rate")) or 0.0
    stop_rate = safe_float(metrics.get("stop_rate")) or 0.0
    recommendation = "COLLECT_MORE_DATA"
    reason = f"Necesita {ROLLBACK_MIN_MEASURED_SIGNALS} senales medidas para revisar rollback."
    next_status = current_status
    if current_status == "ROLLED_BACK" or override.get("active") is False:
        recommendation = "NO_ACTION"
        reason = "Override ya desactivado."
        next_status = "ROLLED_BACK"
    elif action in {"SHADOW_TEST", "TIGHTEN_FILTER"} and measured >= ROLLBACK_MIN_MEASURED_SIGNALS:
        if hit_rate >= ROLLBACK_HIT_2_RATE and stop_rate <= ROLLBACK_MAX_STOP_RATE:
            recommendation = "ROLLBACK"
            reason = (
                f"Las senales shadow de {family} llegaron a target 2% en {hit_rate:.0%} "
                f"con stops {stop_rate:.0%}; el override puede estar bloqueando oportunidades buenas."
            )
            next_status = "ROLLBACK_READY"
        elif stop_rate >= CONFIRM_FILTER_STOP_RATE and hit_rate <= CONFIRM_FILTER_MAX_HIT_2_RATE:
            recommendation = "KEEP_FILTER"
            reason = f"Filtro confirmado: stops {stop_rate:.0%}, target 2% {hit_rate:.0%}."
            next_status = "CONFIRMED_FILTER"
        else:
            recommendation = "KEEP_TESTING"
            reason = f"Resultado mixto: target 2% {hit_rate:.0%}, stops {stop_rate:.0%}."
            next_status = "ACTIVE"
    return {
        "strategy_family": family,
        "action": action,
        "status": current_status,
        "next_status": next_status,
        "active": override.get("active", True) is not False,
        "recommendation": recommendation,
        "reason": reason,
        "metrics": metrics,
        "proposal_id": override.get("proposal_id", ""),
    }


def review_strategy_overrides(
    memory: dict[str, Any],
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    state = load_json(path or STRATEGY_OVERRIDES_PATH, {"version": 1, "strategy_overrides": {}})
    rows = state.get("strategy_overrides") if isinstance(state.get("strategy_overrides"), dict) else {}
    return [review_override_row(family, override, memory) for family, override in rows.items() if isinstance(override, dict)]


def apply_override_rollbacks(
    memory: dict[str, Any],
    *,
    env: dict[str, str] | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    target_path = path or STRATEGY_OVERRIDES_PATH
    state = load_json(target_path, {"version": 1, "updated_at": "", "strategy_overrides": {}})
    rows = state.get("strategy_overrides") if isinstance(state.get("strategy_overrides"), dict) else {}
    reviews = [review_override_row(family, override, memory) for family, override in rows.items() if isinstance(override, dict)]
    rollback_reviews = [row for row in reviews if row.get("recommendation") == "ROLLBACK"]
    if not rollback_reviews:
        return []
    if not env_enabled(env):
        return [
            {
                "strategy_family": row.get("strategy_family"),
                "applied": False,
                "reason": f"{CODE_WRITE_ENV} is not enabled",
                "recommendation": row.get("recommendation"),
            }
            for row in rollback_reviews
        ]
    for row in rollback_reviews:
        family = safe_text(row.get("strategy_family"))
        override = rows.get(family) if isinstance(rows.get(family), dict) else {}
        override["active"] = False
        override["status"] = "ROLLED_BACK"
        override["rolled_back_at"] = iso_now()
        override["rollback_reason"] = row.get("reason")
        override["tracking"] = row.get("metrics")
        override["updated_at"] = iso_now()
        rows[family] = override
    state["updated_at"] = iso_now()
    backup = write_json_with_backup(target_path, state)
    return [
        {
            "strategy_family": row.get("strategy_family"),
            "applied": True,
            "path": str(target_path),
            "backup_path": str(backup) if backup else "",
            "reason": row.get("reason"),
            "recommendation": row.get("recommendation"),
        }
        for row in rollback_reviews
    ]


def apply_proposals(proposals: list[dict[str, Any]], *, env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    if not env_enabled(env):
        return [
            {
                "proposal_id": proposal.get("id"),
                "applied": False,
                "reason": f"{CODE_WRITE_ENV} is not enabled",
            }
            for proposal in proposals
            if proposal.get("type") == "strategy_override"
        ]
    applied = []
    for proposal in proposals:
        if len(applied) >= MAX_APPLIED_PER_RUN:
            break
        if proposal.get("type") != "strategy_override":
            continue
        result = apply_strategy_override(proposal)
        result["proposal_id"] = proposal.get("id")
        applied.append(result)
    return applied


def build_autopilot_report(
    *,
    memory: dict[str, Any] | None = None,
    apply: bool = False,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_env = env if env is not None else os.environ
    loaded_memory = memory if memory is not None else load_memory()
    health = build_health_snapshot()
    autoheal_actions = autoheal_stale_reports(health, enabled=True)
    if autoheal_actions:
        health = build_health_snapshot()
    rollback_applied = apply_override_rollbacks(loaded_memory, env=source_env) if apply else []
    existing_overrides = load_json(STRATEGY_OVERRIDES_PATH, {"version": 1, "strategy_overrides": {}})
    override_reviews = review_strategy_overrides(loaded_memory)
    proposals = build_improvement_proposals(loaded_memory, existing_overrides=existing_overrides)
    proposal_files = write_proposal_files(proposals)
    applied = apply_proposals(proposals, env=source_env) if apply else []
    code_write_enabled = env_enabled(source_env)
    return {
        "generated_at": iso_now(),
        "mode": "ROXY_AUTOPILOT",
        "status": "ACTIVE" if health["status"] in {"OK", "WARN"} else "DEGRADED",
        "code_write_enabled": code_write_enabled,
        "apply_requested": bool(apply),
        "live_orders_allowed": False,
        "paper_only": True,
        "guardrails": {
            "allowed_write_targets": [str(STRATEGY_OVERRIDES_PATH), str(AUTOPILOT_PROPOSALS_DIR)],
            "requires_env": CODE_WRITE_ENV,
            "max_applied_per_run": MAX_APPLIED_PER_RUN,
            "real_money_trading": "DISABLED",
        },
        "health": health,
        "autoheal_actions": autoheal_actions,
        "proposal_count": len(proposals),
        "proposals": proposals,
        "proposal_files": proposal_files,
        "applied": applied,
        "override_reviews": override_reviews,
        "rollback_applied": rollback_applied,
    }


def write_autopilot_report(report: dict[str, Any], *, path: Path = AUTOPILOT_STATUS_PATH) -> Path:
    write_json_with_backup(path, report)
    return path


def run_autopilot(*, apply: bool = False, env: dict[str, str] | None = None) -> dict[str, Any]:
    report = build_autopilot_report(apply=apply, env=env)
    write_autopilot_report(report)
    return report


def load_autopilot_status(path: str | Path = AUTOPILOT_STATUS_PATH) -> dict[str, Any]:
    return load_json(project_path(path), {})
