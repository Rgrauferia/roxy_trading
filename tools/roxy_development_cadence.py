from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = BASE_DIR / "logs" / "development_cadence"
STATE_PATH = LOG_DIR / "state.json"
STATUS_PATH = LOG_DIR / "status.json"
EVENTS_PATH = LOG_DIR / "events.jsonl"
REPORT_PATH = LOG_DIR / "latest_report.md"
TASKS_PATH = LOG_DIR / "NEXT_TASKS.md"

CHART_FILES = [
    "streamlit_app.py",
    "symbol_detail.py",
    "chart_health.py",
    "tools/chart_realtime_health.py",
]

HOURLY_FILES = [
    "MASTER_CONTEXT.md",
    "ROXY_DEVELOPMENT_CADENCE.md",
    "training_videos/ROXY_LEARNING_SYNC.md",
    "trade_brief.py",
    "trade_enrichment.py",
    "options_strategy.py",
    "smart_alerts.py",
    "alpaca_paper_practice.py",
]

CHART_TASKS = [
    "Revisar si la grafica principal muestra velas, SMA/EMA, volumen, soportes, resistencias, entrada, stop y objetivos 2/5/10 sin saturar.",
    "Verificar que AAPL u otro simbolo liquido pueda leerse con una semana de contexto cuando el timeframe lo permita.",
    "Mejorar una pieza visual pequena si hay evidencia clara: labels, zonas, volumen, layout movil o lectura del setup.",
    "Si no se edita codigo, dejar una nota de auditoria con el proximo ajuste visual concreto.",
]

HOURLY_TASKS = [
    "Revisar cambios de otras pestanas con git status y contexto antes de editar.",
    "Elegir una mejora comercial verificable: memoria real, opciones profesionales, alertas sin ruido, Roxy Lab, Estudios, UI movil o seguridad de plataformas.",
    "Integrar conocimiento nuevo como enriquecimiento, no como reemplazo ciego de reglas probadas.",
    "Ejecutar pruebas enfocadas y actualizar contexto si cambia una regla importante.",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_git_status(repo: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def file_snapshot(repo: Path, files: list[str]) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for name in files:
        path = repo / name
        item: dict[str, Any] = {"path": name, "exists": path.exists()}
        if path.exists():
            stat = path.stat()
            item.update(
                {
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                }
            )
        snapshot.append(item)
    return snapshot


def changed_files(git_lines: list[str], watched: list[str]) -> list[str]:
    changed: list[str] = []
    for line in git_lines:
        path = line[3:] if len(line) > 3 else line
        for watched_path in watched:
            if path == watched_path or path.endswith(watched_path):
                changed.append(path)
    return sorted(set(changed))


def should_run_hourly(state: dict[str, Any], now: datetime, interval_seconds: int = 7200) -> bool:
    last = state.get("last_hourly_at")
    if not isinstance(last, str) or not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    return (now - last_dt).total_seconds() >= interval_seconds


def build_status(repo: Path, now: datetime, state: dict[str, Any]) -> dict[str, Any]:
    git_lines = run_git_status(repo)
    hourly_due = should_run_hourly(state, now)
    return {
        "generated_at": iso(now),
        "repo": str(repo),
        "mode": "audit_only",
        "safety": {
            "edits_code": False,
            "places_orders": False,
            "real_trading": False,
            "purpose": "Mantener contexto, reportes y siguientes tareas para Codex/Roxy.",
        },
        "cadence": {
            "chart_minutes": 120,
            "hourly_minutes": 120,
            "run_count": int(state.get("run_count", 0)) + 1,
            "hourly_due": hourly_due,
        },
        "git": {
            "dirty_count": len(git_lines),
            "dirty_preview": git_lines[:40],
            "chart_changed": changed_files(git_lines, CHART_FILES),
            "hourly_changed": changed_files(git_lines, HOURLY_FILES),
        },
        "snapshots": {
            "chart_files": file_snapshot(repo, CHART_FILES),
            "hourly_files": file_snapshot(repo, HOURLY_FILES),
        },
        "next_chart_tasks": CHART_TASKS,
        "next_hourly_tasks": HOURLY_TASKS if hourly_due else [],
    }


def render_tasks(status: dict[str, Any]) -> str:
    lines = [
        "# Roxy Next Tasks",
        "",
        f"Generated: {status['generated_at']}",
        "",
        "## Cada 2 Horas: Graficas",
    ]
    lines.extend(f"- [ ] {task}" for task in status["next_chart_tasks"])
    lines.extend(["", "## Cada 2 Horas: Producto"])
    hourly_tasks = status.get("next_hourly_tasks") or ["Todavia no toca bloque de 2 horas; seguir con graficas y claridad."]
    lines.extend(f"- [ ] {task}" for task in hourly_tasks)
    lines.extend(
        [
            "",
            "## Reglas De Seguridad",
            "- Este runner no edita codigo automaticamente.",
            "- Este runner no envia ordenes reales ni paper orders.",
            "- Codex debe leer este archivo antes de continuar si la sesion cambia.",
            "",
        ]
    )
    return "\n".join(lines)


def render_report(status: dict[str, Any]) -> str:
    git = status["git"]
    chart_changed = git["chart_changed"] or ["Sin cambios detectados en archivos de grafica."]
    hourly_changed = git["hourly_changed"] or ["Sin cambios detectados en archivos de producto/contexto."]
    hourly_note = "Toca bloque de 2 horas." if status["cadence"]["hourly_due"] else "No toca bloque de 2 horas todavia."
    lines = [
        "# Roxy Development Cadence Report",
        "",
        f"Generated: {status['generated_at']}",
        f"Repo: `{status['repo']}`",
        "",
        "## Estado",
        f"- Modo: `{status['mode']}`",
        f"- Run count: `{status['cadence']['run_count']}`",
        f"- Dirty files: `{git['dirty_count']}`",
        f"- Hourly: {hourly_note}",
        "",
        "## Cambios Relevantes Para Graficas",
    ]
    lines.extend(f"- {item}" for item in chart_changed)
    lines.extend(["", "## Cambios Relevantes Para Producto"])
    lines.extend(f"- {item}" for item in hourly_changed)
    lines.extend(["", "## Proximo Bloque De 2 Horas"])
    lines.extend(f"- {task}" for task in status["next_chart_tasks"])
    lines.extend(["", "## Proximo Bloque De 2 Horas"])
    hourly_tasks = status.get("next_hourly_tasks") or ["Esperar al proximo ciclo de 2 horas."]
    lines.extend(f"- {task}" for task in hourly_tasks)
    lines.extend(
        [
            "",
            "## Handoff Para Codex",
            "Leer `ROXY_DEVELOPMENT_CADENCE.md`, `MASTER_CONTEXT.md` y este reporte. Trabajar sobre el cambio de mayor valor sin revertir trabajo ajeno.",
            "",
        ]
    )
    return "\n".join(lines)


def append_event(status: dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a") as fh:
        fh.write(json.dumps(status, sort_keys=True) + "\n")


def run_once(repo: Path = BASE_DIR) -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    state = load_json(STATE_PATH, {"run_count": 0, "last_hourly_at": ""})
    status = build_status(repo, now, state)
    state["run_count"] = status["cadence"]["run_count"]
    state["last_run_at"] = status["generated_at"]
    if status["cadence"]["hourly_due"]:
        state["last_hourly_at"] = status["generated_at"]
    write_json(STATE_PATH, state)
    write_json(STATUS_PATH, status)
    TASKS_PATH.write_text(render_tasks(status))
    REPORT_PATH.write_text(render_report(status))
    append_event(status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Roxy development cadence every 2 hours.")
    parser.add_argument("--repo", default=str(BASE_DIR), help="Roxy repo path.")
    parser.add_argument("--once", action="store_true", help="Run one audit cycle and exit.")
    parser.add_argument("--json", action="store_true", help="Print status JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    status = run_once(Path(args.repo).expanduser().resolve())
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(f"Wrote {REPORT_PATH}")
        print(f"Wrote {TASKS_PATH}")


if __name__ == "__main__":
    main()
