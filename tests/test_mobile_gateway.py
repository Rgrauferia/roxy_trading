import ipaddress
import os
import subprocess

from cryptography import x509

from tools import mobile_gateway


def test_mobile_gateway_generates_private_credentials_and_lan_certificate(tmp_path, monkeypatch):
    monkeypatch.setattr(mobile_gateway, "local_ipv4_addresses", lambda: ["192.168.50.20"])
    monkeypatch.setattr(mobile_gateway.socket, "gethostname", lambda: "roxy-mac.local")

    result = mobile_gateway.generate_credentials(tmp_path / "gateway", port=8443)
    paths = result["paths"]
    certificate = x509.load_pem_x509_certificate(paths["server_cert"].read_bytes())
    sans = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value

    assert result["public_url"] == "https://192.168.50.20:8443"
    assert ipaddress.ip_address("192.168.50.20") in sans.get_values_for_type(x509.IPAddress)
    assert "roxy-mac.local" in sans.get_values_for_type(x509.DNSName)
    for name in ("ca_key", "server_key", "token", "env", "pairing"):
        assert os.stat(paths[name]).st_mode & 0o777 == 0o600
    token = paths["token"].read_text()
    assert len(token) >= 48
    assert token in paths["env"].read_text()
    assert token in paths["pairing"].read_text()
    assert "CA URL: https://192.168.50.20:8443/roxy-mobile-ca.crt" in paths["pairing"].read_text()
    assert "ROXY_STATE_SYNC_USERS=local_user" in paths["env"].read_text()
    assert "ROXY_VOICE_TLS_TERMINATED=1" in paths["env"].read_text()


def test_mobile_gateway_plist_sources_isolated_env_without_embedding_token(tmp_path):
    root = tmp_path / "gateway"
    payload = mobile_gateway.build_plist(python_path=tmp_path / "python", root=root)
    command = payload["ProgramArguments"][2]

    assert "tools.voice_service:app" in command
    assert "--host 0.0.0.0" in command
    assert "--port 8443" in command
    assert "--ssl-keyfile" in command and "--ssl-certfile" in command
    assert str(root / "gateway.env") in command
    assert str(mobile_gateway.MANAGED_PROVIDER_ENV) in command
    assert command.index(str(mobile_gateway.MANAGED_PROVIDER_ENV)) < command.index(str(root / "gateway.env"))
    assert "VOICE_API_KEY=" not in command
    assert payload["Label"] == mobile_gateway.DEFAULT_LABEL


def test_mobile_gateway_refuses_install_without_lan_address(tmp_path, monkeypatch):
    monkeypatch.setattr(mobile_gateway, "local_ipv4_addresses", lambda: [])
    try:
        mobile_gateway.generate_credentials(tmp_path / "gateway")
    except RuntimeError as exc:
        assert "IPv4 LAN" in str(exc)
    else:
        raise AssertionError("The gateway must not bind without a certificate LAN identity")


def test_mobile_gateway_reuses_valid_credentials_instead_of_rotating(tmp_path, monkeypatch):
    monkeypatch.setattr(mobile_gateway, "local_ipv4_addresses", lambda: ["192.168.50.20"])
    monkeypatch.setattr(mobile_gateway.socket, "gethostname", lambda: "roxy-mac.local")
    root = tmp_path / "gateway"
    first = mobile_gateway.ensure_credentials(root)
    token = first["paths"]["token"].read_text()

    second = mobile_gateway.ensure_credentials(root)

    assert first["reused_credentials"] is False
    assert second["reused_credentials"] is True
    assert second["paths"]["token"].read_text() == token


def test_mobile_gateway_retries_launchd_bootstrap_race(tmp_path, monkeypatch):
    calls = []
    bootstraps = 0
    bootstrap_results = iter((
        subprocess.CompletedProcess([], 5, "", "Input/output error"),
        subprocess.CompletedProcess([], 0, "", ""),
    ))

    def fake_launchctl(*args):
        nonlocal bootstraps
        calls.append(args)
        if args[0] == "bootstrap":
            bootstraps += 1
            return next(bootstrap_results)
        if args[0] == "print" and bootstraps >= 2:
            return subprocess.CompletedProcess([], 0, "", "")
        return subprocess.CompletedProcess([], 1, "", "not loaded")

    monkeypatch.setattr(mobile_gateway, "launchctl", fake_launchctl)
    monkeypatch.setattr(mobile_gateway.time, "sleep", lambda _: None)

    mobile_gateway.load_launchagent(tmp_path / "gateway.plist", attempts=2)

    assert [args[0] for args in calls].count("bootstrap") == 2
    assert [args[0] for args in calls].count("print") == 2
