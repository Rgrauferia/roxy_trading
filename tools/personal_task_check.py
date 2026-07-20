from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from durable_storage import atomic_write_text
from roxy_os import RoxyOrchestrator
from roxy_os.personal_tasks import PersonalTaskStore


CONTRACT_VERSION = "roxy-personal-tasks/1.0.0"
DEFAULT_REPORT_PATH = Path("alerts/personal_task_check.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_personal_task_check(root: str | Path = ".") -> dict[str, Any]:
    base = Path(root)
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="roxy-personal-task-check-") as directory:
        temp = Path(directory)
        task_path = temp / "tasks.json"
        store = PersonalTaskStore(task_path)
        past_due = datetime.now(timezone.utc) - timedelta(minutes=1)
        task = store.create("probe_user", "Verificar tarea durable", due_at=past_due, source="diagnostic")
        store.create("other_user", "Tarea aislada", source="diagnostic")
        reopened = PersonalTaskStore(task_path)
        isolated = reopened.list_tasks("probe_user")
        checks.append(
            {
                "name": "durable_user_isolation",
                "status": "OK" if len(isolated) == 1 and isolated[0].get("id") == task.get("id") else "ERROR",
            }
        )
        started = reopened.transition("probe_user", task["id"], "IN_PROGRESS")
        completed = reopened.transition("probe_user", task["id"], "DONE")
        checks.append(
            {
                "name": "lifecycle",
                "status": "OK" if started.get("status") == "IN_PROGRESS" and completed.get("completed_at") else "ERROR",
            }
        )

        memory_path = temp / "memory.json"
        roxy = RoxyOrchestrator(memory_path=memory_path)
        voice_result = roxy.handle("Roxy acuerdame revisar la agenda", user_id="probe_user")
        voice_tasks = PersonalTaskStore(temp / "roxy_personal_tasks.json").list_tasks("probe_user")
        checks.append(
            {
                "name": "voice_shared_store",
                "status": "OK" if voice_tasks and voice_result.data.get("task", {}).get("id") == voice_tasks[0].get("id") else "ERROR",
            }
        )

    try:
        source = (base / "streamlit_app.py").read_text(encoding="utf-8")
    except OSError:
        source = ""
    ui_contract = all(
        marker in source
        for marker in (
            '"ecosystem.tasks": {"view": "Tareas"',
            'elif selected_page == "Tareas":',
            "show_personal_tasks_screen()",
            '"personal_task_snapshot": personal_task_snapshot',
            "LOCAL_ONLY",
        )
    )
    checks.append({"name": "ui_route_and_context", "status": "OK" if ui_contract else "ERROR"})
    probe_reports = [
        _read_json(base / "alerts" / "personal_tasks_desktop_probe.json"),
        _read_json(base / "alerts" / "personal_tasks_mobile_probe.json"),
    ]
    responsive_runtime_ok = all(
        str(report.get("status") or "").upper() == "OK"
        and int(report.get("blocking_console_error_count") or 0) == 0
        and int(report.get("blocking_page_error_count") or 0) == 0
        for report in probe_reports
    )
    checks.append({"name": "desktop_mobile_runtime", "status": "OK" if responsive_runtime_ok else "ERROR"})
    status = "OK" if all(check["status"] == "OK" for check in checks) else "ERROR"
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source": "local_durable",
        "sync_state": "LOCAL_ONLY",
        "checks": checks,
        "production_data_mutated": False,
        "runtime_evidence": [
            "alerts/personal_tasks_desktop_probe.json",
            "alerts/personal_tasks_mobile_probe.json",
        ],
    }


def write_report(payload: dict[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica tareas personales durables y contexto compartido de Roxy.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_personal_task_check(args.root)
    write_report(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
