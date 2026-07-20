from __future__ import annotations

import argparse
import ipaddress
import os
import plistlib
import secrets
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


BASE_DIR = Path(__file__).resolve().parents[1]
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "RoxyTrading" / "mobile_gateway"
LOG_DIR = BASE_DIR / "logs"
DEFAULT_LABEL = "com.roxy.mobile-gateway"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8443
MANAGED_PROVIDER_ENV = Path.home() / "Library" / "Application Support" / "RoxyTrading" / ".env"


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            value = str(item[4][0])
            if not ipaddress.ip_address(value).is_loopback:
                addresses.add(value)
    except OSError:
        pass
    for interface in ("en0", "en1"):
        result = subprocess.run(["ipconfig", "getifaddr", interface], capture_output=True, text=True, check=False)
        value = result.stdout.strip()
        try:
            if value and not ipaddress.ip_address(value).is_loopback:
                addresses.add(value)
        except ValueError:
            pass
    return sorted(addresses)


def gateway_paths(root: Path = APP_SUPPORT_DIR) -> dict[str, Path]:
    return {
        "root": root,
        "ca_key": root / "roxy-mobile-ca.key",
        "ca_cert": root / "roxy-mobile-ca.crt",
        "server_key": root / "roxy-mobile-server.key",
        "server_cert": root / "roxy-mobile-server.crt",
        "token": root / "bearer_token",
        "env": root / "gateway.env",
        "pairing": root / "pairing.txt",
        "physical_proof": root / "physical_proof.json",
    }


def _pairing_payload(*, public_url: str, token: str) -> bytes:
    return (
        f"Roxy Mobile\nURL: {public_url}/roxy-mobile\nUsuario: local_user\n"
        f"Bearer: {token}\nCA URL: {public_url}/roxy-mobile-ca.crt\n"
    ).encode("utf-8")


def generate_credentials(root: Path = APP_SUPPORT_DIR, *, port: int = DEFAULT_PORT) -> dict[str, Any]:
    paths = gateway_paths(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    ips = local_ipv4_addresses()
    if not ips:
        raise RuntimeError("No se encontro una direccion IPv4 LAN para el gateway movil.")
    hostname = socket.gethostname().strip() or "roxy.local"
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Roxy Mobile Local CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    sans: list[x509.GeneralName] = [x509.DNSName("localhost"), x509.DNSName(hostname)]
    sans.extend(x509.IPAddress(ipaddress.ip_address(value)) for value in ["127.0.0.1", *ips])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name).issuer_name(ca_name).public_key(server_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    _write_private(paths["ca_key"], ca_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    _write_private(paths["server_key"], server_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    _write_private(paths["ca_cert"], ca_cert.public_bytes(serialization.Encoding.PEM))
    _write_private(paths["server_cert"], server_cert.public_bytes(serialization.Encoding.PEM))
    token = secrets.token_urlsafe(48)
    _write_private(paths["token"], token.encode("ascii"))
    public_url = f"https://{ips[0]}:{int(port)}"
    env_lines = [
        f"VOICE_API_KEY={shlex.quote(token)}",
        "ROXY_STATE_SYNC_USERS=local_user",
        "ROXY_VOICE_BIND_HOST=0.0.0.0",
        f"ROXY_VOICE_PORT={int(port)}",
        f"ROXY_VOICE_PUBLIC_BASE_URL={shlex.quote(public_url)}",
        "ROXY_VOICE_TLS_TERMINATED=1",
        f"ROXY_MOBILE_GATEWAY_DIR={shlex.quote(str(root))}",
    ]
    _write_private(paths["env"], ("\n".join(env_lines) + "\n").encode("utf-8"))
    _write_private(paths["pairing"], _pairing_payload(public_url=public_url, token=token))
    return {"public_url": public_url, "ips": ips, "hostname": hostname, "paths": paths}


def existing_credentials(root: Path = APP_SUPPORT_DIR, *, port: int = DEFAULT_PORT) -> dict[str, Any] | None:
    paths = gateway_paths(root)
    required = ("ca_key", "ca_cert", "server_key", "server_cert", "token", "env", "pairing")
    if not all(paths[name].is_file() and not paths[name].is_symlink() for name in required):
        return None
    ips = local_ipv4_addresses()
    if not ips:
        return None
    try:
        certificate = x509.load_pem_x509_certificate(paths["server_cert"].read_bytes())
        certificate_ips = {
            str(value) for value in certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
        }
        token = paths["token"].read_text(encoding="ascii").strip()
        expires = certificate.not_valid_after_utc
    except (OSError, ValueError, x509.ExtensionNotFound):
        return None
    if not set(ips) <= certificate_ips or expires <= datetime.now(timezone.utc) + timedelta(days=7) or len(token) < 48:
        return None
    public_url = f"https://{ips[0]}:{int(port)}"
    _write_private(paths["pairing"], _pairing_payload(public_url=public_url, token=token))
    return {
        "public_url": public_url,
        "ips": ips,
        "hostname": socket.gethostname().strip() or "roxy.local",
        "paths": paths,
        "reused_credentials": True,
    }


def ensure_credentials(root: Path = APP_SUPPORT_DIR, *, port: int = DEFAULT_PORT, rotate: bool = False) -> dict[str, Any]:
    existing = None if rotate else existing_credentials(root, port=port)
    return existing or {**generate_credentials(root, port=port), "reused_credentials": False}


def build_server_arguments(*, python_path: Path, root: Path = APP_SUPPORT_DIR, port: int = DEFAULT_PORT) -> list[str]:
    paths = gateway_paths(root)
    return [str(python_path), "-m", "uvicorn", "tools.voice_service:app", "--host", DEFAULT_HOST, "--port", str(int(port)), "--ssl-keyfile", str(paths["server_key"]), "--ssl-certfile", str(paths["server_cert"])]


def build_plist(*, python_path: Path, root: Path = APP_SUPPORT_DIR, port: int = DEFAULT_PORT, label: str = DEFAULT_LABEL) -> dict[str, Any]:
    env_path = gateway_paths(root)["env"]
    args = " ".join(shlex.quote(value) for value in build_server_arguments(python_path=python_path, root=root, port=port))
    pythonpath = f"{BASE_DIR}:{BASE_DIR / '.venv' / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'}"
    managed = shlex.quote(str(MANAGED_PROVIDER_ENV))
    command = (
        f"cd {shlex.quote(str(BASE_DIR))} && set -a && "
        f"if [ -f {managed} ]; then source {managed}; fi && "
        f"source {shlex.quote(str(env_path))} && set +a && "
        f"export PYTHONPATH={shlex.quote(pythonpath)}${{PYTHONPATH:+:$PYTHONPATH}} && exec {args}"
    )
    return {
        "Label": label,
        "ProgramArguments": ["/bin/bash", "-lc", command],
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(Path.home()),
        "StandardOutPath": str(LOG_DIR / "mobile_gateway.out.log"),
        "StandardErrorPath": str(LOG_DIR / "mobile_gateway.err.log"),
    }


def plist_path(label: str = DEFAULT_LABEL) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)


def bootstrap(path: str | Path) -> None:
    load_launchagent(Path(path))


def load_launchagent(target: Path, *, label: str = DEFAULT_LABEL, attempts: int = 4) -> None:
    """Load a freshly written agent while tolerating launchd's post-bootout race."""
    last_error = ""
    for attempt in range(max(1, int(attempts))):
        result = launchctl("bootstrap", f"gui/{os.getuid()}", str(target))
        if result.returncode == 0:
            time.sleep(0.5)
            if launchctl("print", f"gui/{os.getuid()}/{label}").returncode == 0:
                return
            last_error = "launchd retiro el servicio despues de bootstrap"
            continue
        if launchctl("print", f"gui/{os.getuid()}/{label}").returncode == 0:
            launchctl("kickstart", "-k", f"gui/{os.getuid()}/{label}")
            time.sleep(0.5)
            if launchctl("print", f"gui/{os.getuid()}/{label}").returncode == 0:
                return
        last_error = result.stderr.strip() or result.stdout.strip() or "bootstrap failed"
        if attempt + 1 < attempts:
            time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(last_error or "No se pudo iniciar el gateway movil.")


def install(*, root: Path = APP_SUPPORT_DIR, port: int = DEFAULT_PORT, label: str = DEFAULT_LABEL, rotate: bool = False) -> dict[str, Any]:
    credentials = ensure_credentials(root, port=port, rotate=rotate)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    target = plist_path(label)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as stream:
        plistlib.dump(build_plist(python_path=BASE_DIR / ".venv" / "bin" / "python", root=root, port=port, label=label), stream, sort_keys=False)
    removed = launchctl("bootout", f"gui/{os.getuid()}/{label}")
    if removed.returncode == 0:
        time.sleep(0.75)
    load_launchagent(target, label=label)
    return {**credentials, "plist": target, "label": label}


def status(*, root: Path = APP_SUPPORT_DIR, label: str = DEFAULT_LABEL) -> dict[str, Any]:
    paths = gateway_paths(root)
    loaded = launchctl("print", f"gui/{os.getuid()}/{label}").returncode == 0
    return {
        "label": label,
        "installed": plist_path(label).exists(),
        "loaded": loaded,
        "path": str(plist_path(label)),
        "credentials_ready": all(paths[name].exists() for name in ("ca_cert", "server_cert", "server_key", "token", "env", "pairing")),
        "pairing_path": str(paths["pairing"]),
        "ca_path": str(paths["ca_cert"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Instala el gateway HTTPS aislado para Roxy Mobile.")
    parser.add_argument("action", choices=("install", "status"), nargs="?", default="status")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--rotate", action="store_true", help="Rota CA, certificado y Bearer; requiere volver a vincular dispositivos.")
    args = parser.parse_args()
    payload = install(port=args.port, rotate=args.rotate) if args.action == "install" else status()
    safe = {key: str(value) if isinstance(value, Path) else value for key, value in payload.items() if key != "paths"}
    print(safe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
