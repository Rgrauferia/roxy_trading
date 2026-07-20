from pathlib import Path

import pytest

from tools.provider_credential_setup import (
    SUPPORTED_PROVIDERS,
    configure_provider,
    read_env_values,
    sync_environment_files,
    validate_provider_candidate,
)


def test_sync_environment_files_updates_atomically_and_owner_only(tmp_path: Path):
    project = tmp_path / "project.env"
    managed = tmp_path / "managed" / ".env"
    project.write_text("KEEP=value\nALPACA_API_KEY=old\n", encoding="utf-8")
    project.chmod(0o644)

    sync_environment_files(
        {"ALPACA_API_KEY": "new key", "ALPACA_API_SECRET": "new-secret"},
        project_env=project,
        managed_env=managed,
    )

    assert read_env_values(project) == {
        "KEEP": "value",
        "ALPACA_API_KEY": "new key",
        "ALPACA_API_SECRET": "new-secret",
    }
    assert project.read_text() == managed.read_text()
    assert project.stat().st_mode & 0o777 == 0o600
    assert managed.stat().st_mode & 0o777 == 0o600


def test_invalid_candidate_is_not_persisted_or_restarted(tmp_path: Path):
    project = tmp_path / ".env"
    managed = tmp_path / "managed.env"
    project.write_text("ALPACA_API_KEY=working-old\n", encoding="utf-8")
    restarts = []

    result = configure_provider(
        "alpaca",
        {"ALPACA_API_KEY": "rejected-new", "ALPACA_API_SECRET": "rejected-secret"},
        project_env=project,
        managed_env=managed,
        validator=lambda provider, values: {"provider": provider, "ok": False, "state": "AUTH_INVALID"},
        restarter=lambda: restarts.append("called") or {},
    )

    assert result["saved"] is False
    assert read_env_values(project) == {"ALPACA_API_KEY": "working-old"}
    assert not managed.exists()
    assert restarts == []
    assert "rejected-secret" not in str(result)


def test_valid_candidate_syncs_and_restarts_without_returning_values(tmp_path: Path):
    project = tmp_path / ".env"
    managed = tmp_path / "managed.env"
    project.write_text("KEEP=value\n", encoding="utf-8")

    result = configure_provider(
        "elevenlabs",
        {"ELEVENLABS_AGENT_ID": "agent_test", "ELEVENLABS_API_KEY": "accepted-secret"},
        project_env=project,
        managed_env=managed,
        validator=lambda provider, values: {"provider": provider, "ok": True, "state": "CONNECTED"},
        restarter=lambda: {"com.roxy.streamlit": "restarted"},
    )

    assert result["saved"] is True
    assert result["validated"] is True
    assert result["permissions"] == "0600"
    assert result["services"] == {"com.roxy.streamlit": "restarted"}
    assert read_env_values(project)["ELEVENLABS_API_KEY"] == "accepted-secret"
    assert project.read_text() == managed.read_text()
    assert "accepted-secret" not in str(result)


def test_home_assistant_candidate_is_validated_read_only_and_without_enabling_controls(monkeypatch):
    from roxy_os.home_assistant import HomeAssistantClient

    monkeypatch.setattr(
        HomeAssistantClient,
        "status",
        lambda self: {"status": "CONNECTED", "connected": True, "detail": "Conexion verificada."},
    )
    result = validate_provider_candidate(
        "home_assistant",
        {"ROXY_HOME_ASSISTANT_URL": "http://homeassistant.local:8123", "ROXY_HOME_ASSISTANT_TOKEN": "private-token"},
    )

    assert result["ok"] is True
    assert result["control_enabled"] is False
    assert "private-token" not in str(result)


@pytest.mark.parametrize(
    ("provider", "token_key", "client_name"),
    (("gmail", "ROXY_GMAIL_ACCESS_TOKEN", "GmailReadonlyClient"), ("outlook", "ROXY_OUTLOOK_ACCESS_TOKEN", "OutlookReadonlyClient")),
)
def test_email_candidate_validation_keeps_send_disabled(monkeypatch, provider, token_key, client_name):
    from roxy_os import email_service

    client_class = getattr(email_service, client_name)
    monkeypatch.setattr(
        client_class,
        "status",
        lambda self: {"status": "CONNECTED", "connected": True, "send_enabled": False, "detail": "readonly"},
    )
    result = validate_provider_candidate(provider, {token_key: "private-access-token"})

    assert result["ok"] is True
    assert result["read_only"] is True
    assert result["send_enabled"] is False
    assert result["temporary_access_token"] is True
    assert "private-access-token" not in str(result)


def test_provider_setup_rejects_unexpected_keys_and_placeholder_tokens(tmp_path: Path):
    assert set(("home_assistant", "gmail", "outlook")).issubset(SUPPORTED_PROVIDERS)
    with pytest.raises(ValueError, match="Unexpected settings"):
        configure_provider(
            "gmail",
            {"ROXY_GMAIL_ACCESS_TOKEN": "valid-token", "ALPACA_API_KEY": "cross-provider"},
            project_env=tmp_path / ".env",
            managed_env=tmp_path / "managed.env",
        )
    with pytest.raises(ValueError, match="placeholder"):
        configure_provider(
            "outlook",
            {"ROXY_OUTLOOK_ACCESS_TOKEN": "replace_me"},
            project_env=tmp_path / ".env",
            managed_env=tmp_path / "managed.env",
        )


def test_home_assistant_valid_candidate_is_saved_and_services_restart(tmp_path: Path):
    project = tmp_path / ".env"
    managed = tmp_path / "managed.env"
    result = configure_provider(
        "home_assistant",
        {
            "ROXY_HOME_ASSISTANT_URL": "http://homeassistant.local:8123",
            "ROXY_HOME_ASSISTANT_TOKEN": "accepted-home-token",
            "ROXY_HOME_CONTROL_ENABLED": "1",
        },
        project_env=project,
        managed_env=managed,
        validator=lambda provider, values: {"provider": provider, "ok": True, "state": "CONNECTED"},
        restarter=lambda: {"com.roxy.mobile-gateway": "restarted"},
    )

    assert result["saved"] is True
    assert result["services"] == {"com.roxy.mobile-gateway": "restarted"}
    assert read_env_values(managed)["ROXY_HOME_CONTROL_ENABLED"] == "0"
    assert "accepted-home-token" not in str(result)


def test_email_setup_selects_validated_provider_atomically(tmp_path: Path):
    project = tmp_path / ".env"
    managed = tmp_path / "managed.env"
    result = configure_provider(
        "outlook",
        {"ROXY_OUTLOOK_ACCESS_TOKEN": "accepted-outlook-token"},
        project_env=project,
        managed_env=managed,
        validator=lambda provider, values: {
            "provider": provider,
            "ok": values.get("ROXY_EMAIL_PROVIDER") == "outlook",
            "state": "CONNECTED",
        },
        restarter=lambda: {},
    )

    values = read_env_values(managed)
    assert result["saved"] is True
    assert values["ROXY_EMAIL_PROVIDER"] == "outlook"
    assert values["ROXY_OUTLOOK_ACCESS_TOKEN"] == "accepted-outlook-token"
    assert "accepted-outlook-token" not in str(result)
