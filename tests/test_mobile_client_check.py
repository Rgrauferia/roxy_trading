import json

from tools.mobile_client_check import CONTRACT_VERSION, build_mobile_client_check, write_report


def _fixture(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "roxy_mobile.html").write_text("roxy-mobile-manifest.json roxy_mobile.js roxy_mobile.css")
    common = "watchlists ui_state personal_tasks shopping_list response.status===409 await load() secureTransport Transporte inseguro cache:'no-store' remoteNetworkClient /v1/mobile/physical-proof/ dispositivo remoto verificado"
    (assets / "roxy_mobile.js").write_text("// " + common + "\nconst ready = true;\n")
    (assets / "roxy_mobile.css").write_text("body{display:block}")
    (assets / "roxy_mobile_sw.js").write_text("// url.pathname.startsWith('/v1/')\nconst ready = true;\n")
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "voice_service.py").write_text('\n'.join((
        '@app.get("/roxy-mobile"', '@app.get("/roxy-mobile-manifest.json"', '@app.get("/roxy-mobile-sw.js"',
        '@app.get("/roxy-mobile-ca.mobileconfig"',
        '@app.post("/v1/mobile/physical-proof/{user_id}")',
        '"Content-Security-Policy"', '"Service-Worker-Allowed"',
    )))
    output = tmp_path / "output" / "playwright"
    output.mkdir(parents=True)
    (output / "roxy_mobile_desktop.png").write_bytes(b"x" * 1200)
    (output / "roxy_mobile_phone.png").write_bytes(b"x" * 1200)


def test_mobile_client_contract_is_ready_local_and_remote_gap_is_explicit(tmp_path):
    _fixture(tmp_path)
    payload = build_mobile_client_check(tmp_path, env={})
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["contract_status"] == "OK"
    assert payload["status"] == "WARN"
    assert payload["client_status"] == "READY_LOCAL"
    assert payload["remote_status"] == "NOT_CONFIGURED"
    assert payload["pwa_installable"] is True
    assert payload["stores_sensitive_state"] is False


def test_mobile_client_check_fails_closed_without_assets(tmp_path):
    assert build_mobile_client_check(tmp_path, env={})["contract_status"] == "ERROR"


def test_mobile_client_reports_gateway_ready_without_claiming_physical_connection(tmp_path):
    _fixture(tmp_path)
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

    payload = build_mobile_client_check(tmp_path, env={})

    assert payload["status"] == "WARN"
    assert payload["remote_status"] == "READY_FOR_PHYSICAL_TEST"
    assert "dispositivo fisico" in payload["remote_detail"]


def test_mobile_client_promotes_only_verified_remote_proof(tmp_path):
    _fixture(tmp_path)
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

    payload = build_mobile_client_check(tmp_path, env={})

    assert payload["remote_status"] == "CONNECTED"
    assert "Cliente remoto autenticado" in payload["remote_detail"]


def test_mobile_client_report_round_trips(tmp_path):
    target = tmp_path / "alerts" / "mobile.json"
    payload = {"contract_version": CONTRACT_VERSION, "status": "WARN"}
    assert write_report(payload, target) == target
    assert json.loads(target.read_text()) == payload
