import json

from tools.shopping_list_check import CONTRACT_VERSION, build_shopping_list_check, write_report


def _healthy_root(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("\n".join((
        '"ecosystem.shopping": {"view": "Compras"',
        'elif selected_page == "Compras":',
        "show_shopping_list_screen()",
        '"shopping_list_snapshot": shopping_list_snapshot',
        "LOCAL_ONLY",
    )))
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    for name in ("shopping_list_desktop_probe.json", "shopping_list_mobile_probe.json"):
        (alerts / name).write_text(json.dumps({
            "status": "OK", "blocking_console_error_count": 0, "blocking_page_error_count": 0,
        }))


def test_shopping_check_proves_shared_durable_runtime(tmp_path):
    _healthy_root(tmp_path)

    payload = build_shopping_list_check(tmp_path)

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["status"] == "OK"
    assert payload["sync_state"] == "LOCAL_ONLY"
    assert payload["production_data_mutated"] is False
    assert len(payload["checks"]) == 5


def test_shopping_check_fails_closed_without_evidence(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("# absent")

    payload = build_shopping_list_check(tmp_path)

    assert payload["status"] == "ERROR"


def test_shopping_check_report_round_trips(tmp_path):
    target = tmp_path / "alerts" / "shopping.json"
    payload = {"contract_version": CONTRACT_VERSION, "status": "OK"}
    assert write_report(payload, target) == target
    assert json.loads(target.read_text()) == payload
