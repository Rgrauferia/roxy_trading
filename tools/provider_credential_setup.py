from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_ENV = BASE_DIR / ".env"
DEFAULT_MANAGED_ENV = Path.home() / "Library" / "Application Support" / "RoxyTrading" / ".env"
RESTART_LABELS = (
    "com.roxy.streamlit",
    "com.roxy.ma_live",
    "com.roxy.price-alert-monitor",
    "com.roxy.health_watchdog",
    "com.roxy.voice-live",
    "com.roxy.mobile-gateway",
)
SUPPORTED_PROVIDERS = ("alpaca", "elevenlabs", "home_assistant", "gmail", "outlook")
PROVIDER_ALLOWED_KEYS: dict[str, set[str]] = {
    "alpaca": {"ALPACA_API_KEY", "ALPACA_API_SECRET", "ALPACA_SECRET_KEY", "ALPACA_PAPER", "ALPACA_BASE_URL"},
    "elevenlabs": {"ELEVENLABS_AGENT_ID", "ELEVENLABS_API_KEY"},
    "home_assistant": {"ROXY_HOME_ASSISTANT_URL", "ROXY_HOME_ASSISTANT_TOKEN", "ROXY_HOME_CONTROL_ENABLED", "ROXY_HOME_ASSISTANT_TIMEOUT"},
    "gmail": {"ROXY_EMAIL_PROVIDER", "ROXY_GMAIL_ACCESS_TOKEN"},
    "outlook": {"ROXY_EMAIL_PROVIDER", "ROXY_OUTLOOK_ACCESS_TOKEN"},
}
PROVIDER_REQUIRED_KEYS: dict[str, tuple[tuple[str, ...], ...]] = {
    "alpaca": (("ALPACA_API_KEY",), ("ALPACA_API_SECRET", "ALPACA_SECRET_KEY")),
    "elevenlabs": (("ELEVENLABS_AGENT_ID",), ("ELEVENLABS_API_KEY",)),
    "home_assistant": (("ROXY_HOME_ASSISTANT_URL",), ("ROXY_HOME_ASSISTANT_TOKEN",)),
    "gmail": (("ROXY_GMAIL_ACCESS_TOKEN",),),
    "outlook": (("ROXY_OUTLOOK_ACCESS_TOKEN",),),
}
ENV_LINE = re.compile(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)(\s*=).*$")


def read_env_values(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    source = Path(path)
    if not source.is_file():
        return values
    for raw_line in source.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = ENV_LINE.match(raw_line)
        if not match:
            continue
        raw_value = raw_line.split("=", 1)[1].strip()
        try:
            parts = shlex.split(raw_value, comments=True, posix=True)
        except ValueError:
            parts = []
        values[match.group(2)] = parts[0] if parts else ""
    return values


def placeholder_credential(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return True
    return any(
        token in normalized
        for token in ("tu_key", "tu_secret", "your_key", "your_secret", "replace_me", "placeholder", "changeme")
    )


def updated_env_text(original: str, updates: Mapping[str, str]) -> str:
    pending = {str(key): str(value) for key, value in updates.items()}
    lines: list[str] = []
    for raw_line in original.splitlines():
        match = ENV_LINE.match(raw_line)
        key = match.group(2) if match else ""
        if key not in pending:
            lines.append(raw_line)
            continue
        lines.append(f"{match.group(1)}{key}{match.group(3)}{shlex.quote(pending.pop(key))}")
    if pending and lines and lines[-1].strip():
        lines.append("")
    lines.extend(f"{key}={shlex.quote(value)}" for key, value in pending.items())
    return "\n".join(lines).rstrip() + "\n"


def write_owner_only_env(path: str | Path, content: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, target)
        target.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def sync_environment_files(
    updates: Mapping[str, str],
    *,
    project_env: str | Path = DEFAULT_PROJECT_ENV,
    managed_env: str | Path = DEFAULT_MANAGED_ENV,
) -> tuple[Path, Path]:
    project_path = Path(project_env)
    original = project_path.read_text(encoding="utf-8", errors="ignore") if project_path.is_file() else ""
    content = updated_env_text(original, updates)
    write_owner_only_env(project_path, content)
    write_owner_only_env(managed_env, content)
    return project_path, Path(managed_env)


def validate_provider_candidate(provider: str, values: Mapping[str, str]) -> dict[str, Any]:
    if provider == "alpaca":
        from tools.roxy_realtime_check import validate_alpaca_account_probe

        check = validate_alpaca_account_probe(env=dict(values))
        return {
            "provider": "alpaca",
            "ok": check.get("auth_ok") is True and str(check.get("status") or "").upper() == "OK",
            "status": check.get("status"),
            "state": check.get("error_category") or check.get("diagnosis") or "CONNECTED",
            "detail": check.get("detail"),
        }
    if provider == "elevenlabs":
        from tools.elevenlabs_roxy import get_conversation_token

        session = get_conversation_token(env=dict(values))
        return {
            "provider": "elevenlabs",
            "ok": session.configured and bool(session.conversation_token),
            "status": "OK" if session.configured else "ERROR",
            "state": session.state,
            "http_status": session.http_status,
            "detail": "ElevenLabs authentication accepted." if session.configured else session.error,
        }
    if provider == "home_assistant":
        from roxy_os.home_assistant import HomeAssistantClient, HomeAssistantConfig

        config = HomeAssistantConfig(
            base_url=str(values.get("ROXY_HOME_ASSISTANT_URL") or "").strip(),
            token=str(values.get("ROXY_HOME_ASSISTANT_TOKEN") or "").strip(),
            control_enabled=False,
        )
        status = HomeAssistantClient(config).status()
        return {
            "provider": provider,
            "ok": status.get("connected") is True,
            "status": status.get("status"),
            "state": status.get("status"),
            "detail": status.get("detail"),
            "control_enabled": False,
        }
    if provider in {"gmail", "outlook"}:
        from roxy_os.email_service import GmailReadonlyClient, OutlookReadonlyClient

        token_key = "ROXY_GMAIL_ACCESS_TOKEN" if provider == "gmail" else "ROXY_OUTLOOK_ACCESS_TOKEN"
        client = GmailReadonlyClient(token=str(values.get(token_key) or "")) if provider == "gmail" else OutlookReadonlyClient(token=str(values.get(token_key) or ""))
        status = client.status()
        return {
            "provider": provider,
            "ok": status.get("connected") is True and status.get("send_enabled") is False,
            "status": status.get("status"),
            "state": status.get("status"),
            "detail": status.get("detail"),
            "read_only": True,
            "send_enabled": False,
            "temporary_access_token": True,
        }
    raise ValueError(f"Unsupported provider: {provider}")


def restart_consumer_services(labels: tuple[str, ...] = RESTART_LABELS) -> dict[str, str]:
    target = f"gui/{os.getuid()}"
    actions: dict[str, str] = {}
    for label in labels:
        loaded = subprocess.run(
            ["launchctl", "print", f"{target}/{label}"],
            text=True,
            capture_output=True,
            check=False,
        ).returncode == 0
        if not loaded:
            actions[label] = "not_loaded"
            continue
        result = subprocess.run(
            ["launchctl", "kickstart", "-k", f"{target}/{label}"],
            text=True,
            capture_output=True,
            check=False,
        )
        actions[label] = "restarted" if result.returncode == 0 else "restart_failed"
    return actions


def configure_provider(
    provider: str,
    updates: Mapping[str, str],
    *,
    project_env: str | Path = DEFAULT_PROJECT_ENV,
    managed_env: str | Path = DEFAULT_MANAGED_ENV,
    save_unverified: bool = False,
    restart: bool = True,
    validator: Callable[[str, Mapping[str, str]], dict[str, Any]] = validate_provider_candidate,
    restarter: Callable[[], dict[str, str]] = restart_consumer_services,
) -> dict[str, Any]:
    provider = str(provider or "").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    normalized_updates = {str(key): str(value) for key, value in updates.items()}
    unexpected = sorted(set(normalized_updates) - PROVIDER_ALLOWED_KEYS[provider])
    if unexpected:
        raise ValueError(f"Unexpected settings for {provider}: {', '.join(unexpected)}")
    if provider == "home_assistant":
        normalized_updates["ROXY_HOME_CONTROL_ENABLED"] = "0"
    if provider in {"gmail", "outlook"}:
        normalized_updates["ROXY_EMAIL_PROVIDER"] = provider
    if any(placeholder_credential(value) for key, value in normalized_updates.items() if key.endswith(("KEY", "SECRET", "TOKEN"))):
        raise ValueError("Empty or placeholder credentials are not accepted")
    candidate = read_env_values(project_env)
    candidate.update(normalized_updates)
    missing = [
        "/".join(group)
        for group in PROVIDER_REQUIRED_KEYS[provider]
        if not any(not placeholder_credential(candidate.get(key, "")) for key in group)
    ]
    if missing:
        raise ValueError(f"Missing required settings for {provider}: {', '.join(missing)}")
    validation = validator(provider, candidate)
    if not validation.get("ok") and not save_unverified:
        return {"provider": provider, "saved": False, "validation": validation, "services": {}}
    project_path, managed_path = sync_environment_files(
        normalized_updates,
        project_env=project_env,
        managed_env=managed_env,
    )
    services = restarter() if restart and validation.get("ok") else {}
    return {
        "provider": provider,
        "saved": True,
        "validated": bool(validation.get("ok")),
        "validation": validation,
        "project_env": str(project_path),
        "managed_env": str(managed_path),
        "permissions": "0600",
        "services": services,
    }


def prompted_updates(provider: str, current: Mapping[str, str]) -> dict[str, str]:
    if provider == "alpaca":
        return {
            "ALPACA_API_KEY": getpass.getpass("Alpaca paper API key: ").strip(),
            "ALPACA_API_SECRET": getpass.getpass("Alpaca paper API secret: ").strip(),
            "ALPACA_PAPER": "true",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        }
    if provider == "elevenlabs":
        agent_id = str(current.get("ELEVENLABS_AGENT_ID") or "").strip()
        if not agent_id:
            agent_id = input("ElevenLabs agent ID: ").strip()
        return {
            "ELEVENLABS_AGENT_ID": agent_id,
            "ELEVENLABS_API_KEY": getpass.getpass("ElevenLabs API key: ").strip(),
        }
    if provider == "home_assistant":
        base_url = input("Home Assistant base URL (for example http://homeassistant.local:8123): ").strip()
        return {
            "ROXY_HOME_ASSISTANT_URL": base_url,
            "ROXY_HOME_ASSISTANT_TOKEN": getpass.getpass("Home Assistant long-lived access token: ").strip(),
            "ROXY_HOME_CONTROL_ENABLED": "0",
        }
    if provider == "gmail":
        return {
            "ROXY_EMAIL_PROVIDER": "gmail",
            "ROXY_GMAIL_ACCESS_TOKEN": getpass.getpass("Gmail OAuth access token (gmail.readonly): ").strip(),
        }
    if provider == "outlook":
        return {
            "ROXY_EMAIL_PROVIDER": "outlook",
            "ROXY_OUTLOOK_ACCESS_TOKEN": getpass.getpass("Microsoft Graph OAuth access token (Mail.Read): ").strip(),
        }
    raise ValueError(f"Unsupported provider: {provider}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and atomically install Roxy provider credentials without exposing values in argv/output."
    )
    parser.add_argument("provider", choices=SUPPORTED_PROVIDERS)
    parser.add_argument("--project-env", default=str(DEFAULT_PROJECT_ENV))
    parser.add_argument("--managed-env", default=str(DEFAULT_MANAGED_ENV))
    parser.add_argument("--save-unverified", action="store_true")
    parser.add_argument("--no-restart", dest="restart", action="store_false", default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    current = read_env_values(args.project_env)
    updates = prompted_updates(args.provider, current)
    result = configure_provider(
        args.provider,
        updates,
        project_env=args.project_env,
        managed_env=args.managed_env,
        save_unverified=args.save_unverified,
        restart=args.restart,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("saved") and result.get("validated") else 2


if __name__ == "__main__":
    raise SystemExit(main())
