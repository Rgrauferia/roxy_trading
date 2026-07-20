import json

from tools.email_check import build_email_check, write_report


class Client:
    def __init__(self, status):
        self.status_value = status

    def status(self):
        return {"status": self.status_value, "send_enabled": False, "detail": "fixture"}


def _root(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("\n".join((
        '"ecosystem.email": {"view": "Correo"',
        'elif selected_page == "Correo":',
        "show_email_screen()",
        "Envio deshabilitado",
        "ROXY_OUTLOOK_ACCESS_TOKEN",
        "Mail.Read",
    )))
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    for name in ("email_desktop_probe.json", "email_mobile_probe.json"):
        (alerts / name).write_text(json.dumps({
            "status": "OK", "blocking_console_error_count": 0, "blocking_page_error_count": 0,
        }))


def test_email_check_accepts_missing_oauth_as_explicit_degradation(tmp_path):
    _root(tmp_path)
    payload = build_email_check(tmp_path, client=Client("SERVICE_NOT_CONFIGURED"))
    assert payload["contract_status"] == "OK"
    assert payload["status"] == "WARN"
    assert payload["send_enabled"] is False
    assert payload["body_loading_enabled"] is False
    assert payload["outlook_status"] == "SERVICE_NOT_CONFIGURED"


def test_email_check_is_operational_only_when_connected(tmp_path):
    _root(tmp_path)
    assert build_email_check(tmp_path, client=Client("CONNECTED"))["status"] == "OK"


def test_email_check_fails_closed_without_ui_or_runtime(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("# absent")
    assert build_email_check(tmp_path, client=Client("CONNECTED"))["contract_status"] == "ERROR"


def test_email_check_report_round_trips(tmp_path):
    target = tmp_path / "alerts" / "email.json"
    payload = {"status": "WARN", "contract_status": "OK"}
    assert write_report(payload, target) == target
    assert json.loads(target.read_text()) == payload
