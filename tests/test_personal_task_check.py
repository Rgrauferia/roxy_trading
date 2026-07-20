import json

from tools.personal_task_check import CONTRACT_VERSION, build_personal_task_check, write_report


def test_personal_task_check_proves_durability_voice_and_ui(tmp_path):
    (tmp_path / "streamlit_app.py").write_text(
        '\n'.join(
            (
                '"ecosystem.tasks": {"view": "Tareas"',
                'elif selected_page == "Tareas":',
                "show_personal_tasks_screen()",
                '"personal_task_snapshot": personal_task_snapshot',
                "LOCAL_ONLY",
            )
        )
    )
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    for name in ("personal_tasks_desktop_probe.json", "personal_tasks_mobile_probe.json"):
        (alerts / name).write_text(
            json.dumps({"status": "OK", "blocking_console_error_count": 0, "blocking_page_error_count": 0})
        )

    payload = build_personal_task_check(tmp_path)

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["status"] == "OK"
    assert payload["sync_state"] == "LOCAL_ONLY"
    assert payload["production_data_mutated"] is False
    assert {row["name"] for row in payload["checks"]} == {
        "durable_user_isolation",
        "lifecycle",
        "voice_shared_store",
        "ui_route_and_context",
        "desktop_mobile_runtime",
    }


def test_personal_task_check_fails_closed_without_ui_contract(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("# missing integration")

    payload = build_personal_task_check(tmp_path)

    assert payload["status"] == "ERROR"
    assert next(row for row in payload["checks"] if row["name"] == "ui_route_and_context")["status"] == "ERROR"
    assert next(row for row in payload["checks"] if row["name"] == "desktop_mobile_runtime")["status"] == "ERROR"


def test_personal_task_check_report_round_trips(tmp_path):
    target = tmp_path / "alerts" / "personal.json"
    payload = {"contract_version": CONTRACT_VERSION, "status": "OK"}

    assert write_report(payload, target) == target
    assert json.loads(target.read_text()) == payload
