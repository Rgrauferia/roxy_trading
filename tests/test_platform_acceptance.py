import json
import stat
import subprocess
import sys
from datetime import datetime, timezone

from tools.platform_acceptance import (
    CONTRACT_VERSION,
    VOICE_EVIDENCE_FILES,
    build_platform_acceptance,
    write_acceptance_report,
)


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _healthy_fixture(tmp_path, *, stocks_allowed=False, elevenlabs_blocked=True, document_encrypted=False):
    alerts = tmp_path / "alerts"
    allowed = ["crypto", "stock"] if stocks_allowed else ["crypto"]
    blocked = [] if stocks_allowed else ["stock", "options"]
    checks = [
        {"name": name, "status": "OK"}
        for name in (
            "chart_indicators",
            "chart_realtime_health_report",
            "dashboard_render_probe",
            "dashboard_search_render_probe",
            "dual_chart_crosshair_probe",
            "smart_alert_contract",
            "price_alert_monitor",
            "opportunity_sync",
            "opportunity_lifecycle",
        )
    ]
    _write(
        alerts / "roxy_realtime_check.json",
        {
            "status": "WARN" if blocked else "OK",
            "checks": checks,
            "stability_summary": {
                "core_recovered_sustained": True,
                "core_recovery_state": "RECOVERED",
                "external_blocking": bool(blocked),
            },
            "market_realtime": {"allowed_markets": allowed, "blocked_markets": blocked},
        },
    )
    _write(
        alerts / "responsive_route_matrix.json",
        {"status": "OK", "passed": 42, "failed": 0},
    )
    _write(alerts / "chart_realtime_health.json", {"status": "OK"})
    _write(alerts / "opportunity_sync.json", {"status": "OK"})
    _write(
        alerts / "output_maintenance.json",
        {"hygiene_summary": {"external_snapshot_degraded": bool(blocked)}},
    )
    _write(
        alerts / "elevenlabs_auth_circuit.json",
        {"state": "AUTH_INVALID" if elevenlabs_blocked else "CLOSED"},
    )
    for name in VOICE_EVIDENCE_FILES:
        _write(alerts / name, {"status": "OK"})
    _write(alerts / "personal_task_check.json", {"status": "OK", "sync_state": "LOCAL_ONLY"})
    _write(alerts / "shopping_list_check.json", {"status": "OK", "sync_state": "LOCAL_ONLY"})
    _write(alerts / "home_assistant_check.json", {"status": "WARN", "contract_status": "OK", "connected": False})
    _write(
        alerts / "document_vault_check.json",
        {
            "status": "OK" if document_encrypted else "WARN",
            "contract_status": "OK",
            "at_rest_encryption": document_encrypted,
        },
    )
    _write(alerts / "email_check.json", {"status": "WARN", "contract_status": "OK", "connected": False})
    _write(
        alerts / "device_sync_check.json",
        {"status": "WARN", "contract_status": "OK", "remote_status": "NOT_CONFIGURED"},
    )
    _write(
        alerts / "mobile_client_check.json",
        {"status": "WARN", "contract_status": "OK", "remote_status": "NOT_CONFIGURED"},
    )
    _write(
        alerts / "mobile_gateway_check.json",
        {
            "status": "WARN",
            "contract_status": "OK",
            "gateway_status": "READY_FOR_PHYSICAL_TEST",
            "physical_reachability": "UNVERIFIED",
        },
    )


def test_platform_acceptance_keeps_external_and_ecosystem_gaps_explicit(tmp_path):
    _healthy_fixture(tmp_path)

    payload = build_platform_acceptance(
        tmp_path,
        now=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
    )

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["status"] == "IN_PROGRESS"
    assert payload["ready_for_full_vision"] is False
    assert payload["accepted_count"] == 0
    assert payload["partial_count"] == 6
    assert payload["incomplete_count"] == 1
    assert payload["allowed_markets"] == ["crypto"]
    assert payload["blocked_markets"] == ["options", "stock"]
    statuses = {item["phase"]: item["status"] for item in payload["phases"]}
    assert statuses == {
        1: "PARTIAL_EXTERNAL",
        2: "ACCEPTED_LOCAL",
        3: "PARTIAL_MARKET",
        4: "ACCEPTED_CRYPTO_PARTIAL_STOCK",
        5: "ACCEPTED_CRYPTO_PARTIAL_STOCK",
        6: "ACCEPTED_LOCAL_PARTIAL_EXTERNAL",
        7: "IN_PROGRESS",
    }
    assert any("Alpaca" in blocker for blocker in payload["phases"][0]["blockers"])
    assert any("ElevenLabs" in blocker for blocker in payload["phases"][5]["blockers"])
    assert any("Tareas personales" in item for item in payload["phases"][6]["proven"])
    assert any("Lista de compras" in item for item in payload["phases"][6]["proven"])
    assert any("Home Assistant" in item for item in payload["phases"][6]["proven"])
    assert any("URL/token" in item for item in payload["phases"][6]["blockers"])
    assert any("Repositorio documental" in item for item in payload["phases"][6]["proven"])
    assert any("cifrado" in item for item in payload["phases"][6]["blockers"])
    assert any("Gmail" in item for item in payload["phases"][6]["proven"])
    assert any("Gmail o Outlook" in item for item in payload["phases"][6]["blockers"])
    assert any("sincronización revisionada" in item for item in payload["phases"][6]["proven"])
    assert any("CA local" in item for item in payload["phases"][6]["blockers"])
    assert any("Cliente móvil PWA" in item for item in payload["phases"][6]["proven"])
    assert any("Gateway móvil HTTPS" in item for item in payload["phases"][6]["proven"])
    assert "alerts/mobile_gateway_check.json" in payload["phases"][6]["evidence"]
    assert payload["phases"][6]["status"] == "IN_PROGRESS"


def test_platform_acceptance_promotes_market_phases_after_provider_recovery(tmp_path):
    _healthy_fixture(tmp_path, stocks_allowed=True, elevenlabs_blocked=False)

    payload = build_platform_acceptance(tmp_path)
    statuses = {item["phase"]: item["status"] for item in payload["phases"]}

    assert statuses[1] == "ACCEPTED"
    assert statuses[3] == "ACCEPTED"
    assert statuses[4] == "ACCEPTED"
    assert statuses[5] == "ACCEPTED"
    assert statuses[6] == "ACCEPTED"
    assert payload["accepted_count"] == 5
    assert payload["partial_count"] == 1
    assert payload["incomplete_count"] == 1
    assert payload["ready_for_full_vision"] is False


def test_platform_acceptance_removes_document_blocker_after_verified_encryption(tmp_path):
    _healthy_fixture(tmp_path, document_encrypted=True)

    payload = build_platform_acceptance(tmp_path)
    phase7 = payload["phases"][6]

    assert any("AES-256-GCM" in item for item in phase7["proven"])
    assert not any("cifrado en reposo" in item for item in phase7["blockers"])


def test_platform_acceptance_removes_only_physical_blocker_after_remote_proof(tmp_path):
    _healthy_fixture(tmp_path, document_encrypted=True)
    _write(
        tmp_path / "alerts" / "mobile_gateway_check.json",
        {
            "status": "OK",
            "contract_status": "OK",
            "gateway_status": "CONNECTED_PHYSICAL",
            "physical_reachability": "VERIFIED_REMOTE_CLIENT",
        },
    )

    payload = build_platform_acceptance(tmp_path)
    phase7 = payload["phases"][6]

    assert any("cliente remoto verificados" in item for item in phase7["proven"])
    assert not any("CA local" in item for item in phase7["blockers"])
    assert any("Home Assistant" in item for item in phase7["blockers"])
    assert any("OAuth" in item for item in phase7["blockers"])


def test_platform_acceptance_fails_closed_when_evidence_is_missing(tmp_path):
    payload = build_platform_acceptance(tmp_path)

    assert payload["status"] == "IN_PROGRESS"
    assert payload["accepted_count"] == 0
    assert payload["partial_count"] == 0
    assert payload["incomplete_count"] == 7
    assert all(item["status"] in {"INCOMPLETE", "IN_PROGRESS"} for item in payload["phases"])


def test_platform_acceptance_explains_pending_core_recovery_window(tmp_path):
    _healthy_fixture(tmp_path)
    report = json.loads((tmp_path / "alerts" / "roxy_realtime_check.json").read_text())
    report["stability_summary"].update(
        {
            "core_recovered_sustained": False,
            "core_recovery_state": "PENDING",
            "core_runtime_status": "OK",
            "current_core_streak_count": 7,
            "core_recovery_required_streak": 10,
            "core_recovery_cycles_remaining": 3,
        }
    )
    _write(tmp_path / "alerts" / "roxy_realtime_check.json", report)

    payload = build_platform_acceptance(tmp_path)
    phase1 = payload["phases"][0]

    assert phase1["status"] == "INCOMPLETE"
    assert any("7/10 ciclos OK" in item and "faltan 3" in item for item in phase1["blockers"])
    assert any("ventana sostenida" in item for item in phase1["proven"])


def test_write_acceptance_report_round_trips(tmp_path):
    target = tmp_path / "alerts" / "acceptance.json"
    payload = {"contract_version": CONTRACT_VERSION, "status": "IN_PROGRESS", "phases": []}

    written = write_acceptance_report(payload, target)

    assert written == target
    assert json.loads(target.read_text()) == payload
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_platform_acceptance_cli_runs_from_project_script(tmp_path):
    output = tmp_path / "acceptance.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/platform_acceptance.py",
            "--root",
            str(tmp_path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert json.loads(output.read_text())["status"] == "IN_PROGRESS"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test_diagnostics_renders_phase_acceptance_contract():
    source = open("streamlit_app.py", encoding="utf-8").read()

    assert "from tools.platform_acceptance import build_platform_acceptance" in source
    assert 'st.markdown("**Aceptacion por fase de la vision completa**")' in source
    assert '"Aceptadas sin condiciones"' in source
    assert "no equivale a una fase aceptada sin condiciones" in source
