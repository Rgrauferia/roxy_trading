import json

from tools.home_assistant_check import build_home_assistant_check, write_report


class Client:
    def __init__(self, status):
        self.status = status

    def entities(self):
        return {"status": self.status, "control_enabled": False, "entity_count": 0, "detail": "fixture"}


def _root(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("\n".join((
        '"ecosystem.home": {"view": "Hogar"',
        'elif selected_page == "Hogar":',
        "show_roxy_home_screen()",
        "ROXY_HOME_CONTROL_ENABLED=0",
        "Confirmo esta entidad y accion exactas",
    )))
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    for name in ("home_assistant_desktop_probe.json", "home_assistant_mobile_probe.json"):
        (alerts / name).write_text(json.dumps({
            "status": "OK", "blocking_console_error_count": 0, "blocking_page_error_count": 0,
        }))


def test_home_check_accepts_explicit_not_configured_as_degraded_contract(tmp_path):
    _root(tmp_path)
    payload = build_home_assistant_check(tmp_path, client=Client("SERVICE_NOT_CONFIGURED"))

    assert payload["contract_status"] == "OK"
    assert payload["status"] == "WARN"
    assert payload["connected"] is False
    assert payload["secrets_exposed"] is False


def test_home_check_is_operational_only_when_provider_connects(tmp_path):
    _root(tmp_path)
    payload = build_home_assistant_check(tmp_path, client=Client("CONNECTED"))

    assert payload["status"] == "OK"
    assert payload["connected"] is True


def test_home_check_fails_closed_without_runtime_evidence(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("# absent")
    payload = build_home_assistant_check(tmp_path, client=Client("CONNECTED"))
    assert payload["contract_status"] == "ERROR"


def test_home_check_report_round_trips(tmp_path):
    target = tmp_path / "alerts" / "home.json"
    payload = {"status": "WARN", "contract_status": "OK"}
    assert write_report(payload, target) == target
    assert json.loads(target.read_text()) == payload
