import json

from tools.document_vault_check import build_document_vault_check, write_report


def _healthy_root(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("\n".join((
        '"ecosystem.documents": {"view": "Documentos"',
        'elif selected_page == "Documentos":',
        "show_document_vault_screen()",
        "AES-256-GCM",
        "Preparar contenido",
    )))
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    for name in ("document_vault_desktop_probe.json", "document_vault_mobile_probe.json"):
        (alerts / name).write_text(json.dumps({
            "status": "OK", "blocking_console_error_count": 0, "blocking_page_error_count": 0,
        }))


def test_document_check_accepts_private_encrypted_repository(tmp_path):
    _healthy_root(tmp_path)
    payload = build_document_vault_check(tmp_path)
    assert payload["contract_status"] == "OK"
    assert payload["status"] == "OK"
    assert payload["sync_state"] == "LOCAL_ENCRYPTED"
    assert payload["at_rest_encryption"] is True
    assert payload["encryption_algorithm"] == "AES-256-GCM"
    assert payload["production_data_mutated"] is False
    assert len(payload["checks"]) == 5


def test_document_check_fails_closed_without_runtime_evidence(tmp_path):
    (tmp_path / "streamlit_app.py").write_text("# missing")
    assert build_document_vault_check(tmp_path)["contract_status"] == "ERROR"


def test_document_check_report_round_trips(tmp_path):
    target = tmp_path / "alerts" / "documents.json"
    payload = {"status": "OK", "contract_status": "OK"}
    assert write_report(payload, target) == target
    assert json.loads(target.read_text()) == payload
