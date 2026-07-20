from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from cryptography import x509

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from durable_storage import atomic_write_text
from tools.mobile_gateway import APP_SUPPORT_DIR, DEFAULT_LABEL, MANAGED_PROVIDER_ENV, gateway_paths, plist_path


CONTRACT_VERSION = "roxy-mobile-gateway/1.0.0"
DEFAULT_REPORT_PATH = Path("alerts/mobile_gateway_check.json")


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        try:
            parsed = shlex.split(raw)
        except ValueError:
            continue
        values[key.strip()] = parsed[0] if parsed else ""
    return values


def build_mobile_gateway_check(
    root: str | Path = APP_SUPPORT_DIR,
    *,
    launchagent: str | Path | None = None,
    perform_runtime: bool = True,
) -> dict[str, Any]:
    base = Path(root)
    paths = gateway_paths(base)
    target = Path(launchagent) if launchagent else plist_path(DEFAULT_LABEL)
    env = _read_env(paths["env"])
    checks: list[dict[str, Any]] = []
    files_ready = all(paths[name].is_file() and not paths[name].is_symlink() for name in (
        "ca_key", "ca_cert", "server_key", "server_cert", "token", "env", "pairing"
    ))
    private_ready = files_ready and all((paths[name].stat().st_mode & 0o077) == 0 for name in (
        "ca_key", "server_key", "token", "env", "pairing"
    ))
    checks.append({"name": "private_gateway_material", "status": "OK" if private_ready else "ERROR"})
    cert_ok = False
    san_ips: list[str] = []
    expires_at = ""
    if files_ready:
        try:
            cert = x509.load_pem_x509_certificate(paths["server_cert"].read_bytes())
            san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            san_ips = sorted(str(value) for value in san.get_values_for_type(x509.IPAddress))
            expires_at = cert.not_valid_after_utc.isoformat()
            cert_ok = any(value != "127.0.0.1" for value in san_ips) and cert.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=7)
        except (OSError, ValueError, x509.ExtensionNotFound):
            pass
    checks.append({"name": "valid_lan_certificate", "status": "OK" if cert_ok else "ERROR"})
    plist_ok = False
    if target.is_file():
        try:
            payload = plistlib.loads(target.read_bytes())
            command = " ".join(str(value) for value in payload.get("ProgramArguments", []))
            plist_ok = all(marker in command for marker in (
                "--host 0.0.0.0", "--port 8443", "--ssl-keyfile", "--ssl-certfile",
                str(MANAGED_PROVIDER_ENV), str(paths["env"])
            )) and command.index(str(MANAGED_PROVIDER_ENV)) < command.index(str(paths["env"])) and "VOICE_API_KEY=" not in command
        except (OSError, ValueError, plistlib.InvalidFileException):
            pass
    checks.append({"name": "isolated_tls_launchagent", "status": "OK" if plist_ok else "ERROR"})
    loaded = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{DEFAULT_LABEL}"], capture_output=True, text=True, check=False
    ).returncode == 0 if perform_runtime else True
    checks.append({"name": "gateway_process", "status": "OK" if loaded else "ERROR"})
    public_url = str(env.get("ROXY_VOICE_PUBLIC_BASE_URL") or "")
    policy_ok = public_url.startswith("https://") and bool(env.get("VOICE_API_KEY")) and env.get("ROXY_STATE_SYNC_USERS") == "local_user"
    checks.append({"name": "https_bearer_allowlist_policy", "status": "OK" if policy_ok else "ERROR"})
    runtime_ok = not perform_runtime
    profile_ok = not perform_runtime
    runtime_detail = "not_requested"
    if perform_runtime and files_ready and env.get("VOICE_API_KEY"):
        for attempt in range(12):
            try:
                port = int(env.get("ROXY_VOICE_PORT") or 8443)
                base_url = f"https://127.0.0.1:{port}"
                session = requests.Session()
                session.trust_env = False
                unauth = session.get(base_url + "/v1/state-sync/local_user", verify=str(paths["ca_cert"]), timeout=3)
                auth = session.get(
                    base_url + "/v1/state-sync/local_user",
                    headers={"Authorization": f"Bearer {env['VOICE_API_KEY']}"},
                    verify=str(paths["ca_cert"]), timeout=3,
                )
                body = auth.json() if auth.ok else {}
                profile_response = session.get(
                    base_url + "/roxy-mobile-ca.mobileconfig",
                    verify=str(paths["ca_cert"]),
                    timeout=3,
                )
                profile = plistlib.loads(profile_response.content) if profile_response.ok else {}
                profile_ok = (
                    profile_response.status_code == 200
                    and str(profile_response.headers.get("content-type") or "").startswith("application/x-apple-aspen-config")
                    and profile.get("PayloadType") == "Configuration"
                    and (profile.get("PayloadContent") or [{}])[0].get("PayloadType") == "com.apple.security.root"
                    and env["VOICE_API_KEY"].encode("utf-8") not in profile_response.content
                )
                runtime_ok = unauth.status_code == 401 and auth.status_code == 200 and body.get("auth_mode") == "bearer" and body.get("contract_version") == "roxy-device-sync/1.1.0"
                runtime_detail = f"unauth={unauth.status_code}; auth={auth.status_code}; contract={body.get('contract_version') or '-'}"
                break
            except (OSError, ValueError, requests.RequestException):
                runtime_ok = False
                profile_ok = False
                runtime_detail = "tls_runtime_unavailable"
                if attempt < 11:
                    time.sleep(0.25)
    checks.append({"name": "verified_tls_and_bearer_runtime", "status": "OK" if runtime_ok else "ERROR"})
    checks.append({"name": "ios_public_ca_profile", "status": "OK" if profile_ok else "ERROR"})
    contract_ok = all(check["status"] == "OK" for check in checks)
    physical_verified = False
    physical_verified_at = ""
    physical_proof_age_days: float | None = None
    if contract_ok and paths["physical_proof"].is_file() and not paths["physical_proof"].is_symlink():
        try:
            proof = json.loads(paths["physical_proof"].read_text(encoding="utf-8"))
            verified_at = datetime.fromisoformat(str(proof.get("verified_at") or "").replace("Z", "+00:00"))
            if verified_at.tzinfo is None:
                verified_at = verified_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - verified_at.astimezone(timezone.utc)
            physical_proof_age_days = round(max(0.0, age.total_seconds()) / 86400.0, 3)
            expected_bearer = hashlib.sha256(env["VOICE_API_KEY"].encode("utf-8")).hexdigest()[:16]
            expected_ca = hashlib.sha256(paths["ca_cert"].read_bytes()).hexdigest()[:16]
            physical_verified = (
                proof.get("contract_version") == "roxy-mobile-physical-proof/1.0.0"
                and proof.get("remote_client") is True
                and proof.get("transport") == "https"
                and proof.get("user_id") == "local_user"
                and proof.get("bearer_fingerprint") == expected_bearer
                and proof.get("ca_fingerprint") == expected_ca
                and bool(proof.get("client_fingerprint"))
                and (paths["physical_proof"].stat().st_mode & 0o077) == 0
                and timedelta(minutes=-5) <= age <= timedelta(days=30)
            )
            physical_verified_at = verified_at.astimezone(timezone.utc).isoformat() if physical_verified else ""
        except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError):
            physical_verified = False
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if contract_ok and physical_verified else "WARN" if contract_ok else "ERROR",
        "contract_status": "OK" if contract_ok else "ERROR",
        "gateway_status": "CONNECTED_PHYSICAL" if contract_ok and physical_verified else "READY_FOR_PHYSICAL_TEST" if contract_ok else "ERROR",
        "physical_reachability": "VERIFIED_REMOTE_CLIENT" if physical_verified else "UNVERIFIED",
        "physical_verified_at": physical_verified_at,
        "physical_proof_age_days": physical_proof_age_days,
        "public_url": public_url,
        "certificate_expires_at": expires_at,
        "certificate_san_ips": san_ips,
        "bearer_configured": bool(env.get("VOICE_API_KEY")),
        "allowed_user_count": len([value for value in env.get("ROXY_STATE_SYNC_USERS", "").split(",") if value.strip()]),
        "secrets_exposed": False,
        "runtime_detail": runtime_detail,
        "checks": checks,
    }


def write_report(payload: dict[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica TLS, Bearer y aislamiento del gateway movil.")
    parser.add_argument("--root", default=str(APP_SUPPORT_DIR))
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_mobile_gateway_check(args.root)
    write_report(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["gateway_status"] in {"READY_FOR_PHYSICAL_TEST", "CONNECTED_PHYSICAL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
