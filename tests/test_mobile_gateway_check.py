import json
import hashlib
import plistlib
from datetime import datetime, timezone

from tools import mobile_gateway
from tools.mobile_gateway_check import (
    CONTRACT_VERSION,
    build_mobile_gateway_check,
    write_report,
)


def _configured_gateway(tmp_path, monkeypatch):
    root = tmp_path / "gateway"
    monkeypatch.setattr(mobile_gateway, "local_ipv4_addresses", lambda: ["192.168.50.20"])
    monkeypatch.setattr(mobile_gateway.socket, "gethostname", lambda: "roxy-mac.local")
    mobile_gateway.generate_credentials(root, port=8443)
    launchagent = tmp_path / "com.roxy.mobile-gateway.plist"
    launchagent.write_bytes(
        plistlib.dumps(
            mobile_gateway.build_plist(
                python_path=tmp_path / "python",
                root=root,
                port=8443,
            )
        )
    )
    return root, launchagent


def test_mobile_gateway_check_accepts_private_tls_contract_without_claiming_reachability(
    tmp_path, monkeypatch
):
    root, launchagent = _configured_gateway(tmp_path, monkeypatch)

    payload = build_mobile_gateway_check(
        root,
        launchagent=launchagent,
        perform_runtime=False,
    )

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["status"] == "WARN"
    assert payload["contract_status"] == "OK"
    assert payload["gateway_status"] == "READY_FOR_PHYSICAL_TEST"
    assert payload["physical_reachability"] == "UNVERIFIED"
    assert payload["public_url"] == "https://192.168.50.20:8443"
    assert payload["bearer_configured"] is True
    assert payload["allowed_user_count"] == 1
    assert payload["secrets_exposed"] is False
    assert all(item["status"] == "OK" for item in payload["checks"])
    assert not any("token" in key.lower() for key in payload)


def test_mobile_gateway_check_fails_closed_when_material_is_missing(tmp_path):
    payload = build_mobile_gateway_check(
        tmp_path / "missing",
        launchagent=tmp_path / "missing.plist",
        perform_runtime=False,
    )

    assert payload["status"] == "ERROR"
    assert payload["contract_status"] == "ERROR"
    assert payload["gateway_status"] == "ERROR"
    assert payload["physical_reachability"] == "UNVERIFIED"
    assert payload["bearer_configured"] is False


def test_mobile_gateway_report_round_trips_without_credentials(tmp_path, monkeypatch):
    root, launchagent = _configured_gateway(tmp_path, monkeypatch)
    payload = build_mobile_gateway_check(
        root,
        launchagent=launchagent,
        perform_runtime=False,
    )
    target = tmp_path / "alerts" / "mobile_gateway_check.json"

    written = write_report(payload, target)
    persisted = json.loads(written.read_text(encoding="utf-8"))

    assert written == target
    assert persisted == payload
    serialized = written.read_text(encoding="utf-8")
    assert mobile_gateway.gateway_paths(root)["token"].read_text(encoding="utf-8") not in serialized


def test_mobile_gateway_check_accepts_fresh_proof_bound_to_current_ca_and_bearer(tmp_path, monkeypatch):
    root, launchagent = _configured_gateway(tmp_path, monkeypatch)
    paths = mobile_gateway.gateway_paths(root)
    token = paths["token"].read_text(encoding="utf-8")
    proof = {
        "contract_version": "roxy-mobile-physical-proof/1.0.0",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "user_id": "local_user",
        "transport": "https",
        "remote_client": True,
        "client_fingerprint": "0123456789abcdef",
        "bearer_fingerprint": hashlib.sha256(token.encode("utf-8")).hexdigest()[:16],
        "ca_fingerprint": hashlib.sha256(paths["ca_cert"].read_bytes()).hexdigest()[:16],
    }
    paths["physical_proof"].write_text(json.dumps(proof), encoding="utf-8")
    paths["physical_proof"].chmod(0o600)

    payload = build_mobile_gateway_check(root, launchagent=launchagent, perform_runtime=False)

    assert payload["status"] == "OK"
    assert payload["gateway_status"] == "CONNECTED_PHYSICAL"
    assert payload["physical_reachability"] == "VERIFIED_REMOTE_CLIENT"
    assert payload["physical_verified_at"]
