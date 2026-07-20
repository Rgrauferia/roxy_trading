import json

from tools.device_sync_check import CONTRACT_VERSION, build_device_sync_check, write_report


def test_device_sync_check_proves_contract_but_keeps_remote_gap_explicit(tmp_path):
    payload = build_device_sync_check(tmp_path, env={})

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["contract_status"] == "OK"
    assert payload["status"] == "WARN"
    assert payload["remote_status"] == "NOT_CONFIGURED"
    assert payload["production_data_mutated"] is False
    assert payload["scopes"] == ["personal_tasks", "shopping_list", "ui_state", "watchlists"]
    assert all(check["status"] == "OK" for check in payload["checks"])


def test_device_sync_check_accepts_secure_remote_configuration(tmp_path):
    payload = build_device_sync_check(
        tmp_path,
        env={
            "VOICE_API_KEY": "configured",
            "ROXY_STATE_SYNC_USERS": "local_user",
            "ROXY_VOICE_BIND_HOST": "0.0.0.0",
            "ROXY_VOICE_PUBLIC_BASE_URL": "https://roxy.example",
        },
    )

    assert payload["status"] == "OK"
    assert payload["remote_status"] == "CONNECTED"


def test_device_sync_check_reports_gateway_ready_without_claiming_connection(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "mobile_gateway_check.json").write_text(
        json.dumps(
            {
                "contract_status": "OK",
                "gateway_status": "READY_FOR_PHYSICAL_TEST",
                "physical_reachability": "UNVERIFIED",
            }
        ),
        encoding="utf-8",
    )

    payload = build_device_sync_check(tmp_path, env={})

    assert payload["status"] == "WARN"
    assert payload["remote_status"] == "READY_FOR_PHYSICAL_TEST"
    assert "dispositivo fisico" in payload["configuration_detail"]


def test_device_sync_check_promotes_verified_remote_proof(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "mobile_gateway_check.json").write_text(
        json.dumps(
            {
                "contract_status": "OK",
                "gateway_status": "CONNECTED_PHYSICAL",
                "physical_reachability": "VERIFIED_REMOTE_CLIENT",
            }
        ),
        encoding="utf-8",
    )

    payload = build_device_sync_check(tmp_path, env={})

    assert payload["remote_status"] == "CONNECTED"
    assert "Cliente remoto autenticado" in payload["configuration_detail"]


def test_device_sync_check_report_round_trips(tmp_path):
    target = tmp_path / "alerts" / "device_sync.json"
    payload = {"contract_version": CONTRACT_VERSION, "status": "WARN"}
    assert write_report(payload, target) == target
    assert json.loads(target.read_text()) == payload
