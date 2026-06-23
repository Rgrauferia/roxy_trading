from cryptography.fernet import Fernet

from platform_credentials import (
    credential_table_rows,
    encryption_status,
    initialize_local_vault_key,
    platform_credential_status,
    save_platform_credential,
    save_platform_credentials,
    secret_name,
)
import platform_credentials


def configure_temp_vault(monkeypatch, tmp_path):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(platform_credentials, "DB_PATH", str(tmp_path / "roxy_test.db"))
    monkeypatch.setattr(platform_credentials, "DEFAULT_FERNET_KEY_FILE", str(tmp_path / "roxy_fernet.key"))
    platform_credentials.ensure_tables()


def test_encryption_status_reports_enabled_without_key_value(monkeypatch, tmp_path):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", key)
    monkeypatch.setattr(platform_credentials, "DB_PATH", str(tmp_path / "roxy_test.db"))
    monkeypatch.setattr(platform_credentials, "DEFAULT_FERNET_KEY_FILE", str(tmp_path / "roxy_fernet.key"))

    status = encryption_status()

    assert status["enabled"] is True
    assert key not in str(status)


def test_initialize_local_vault_key_creates_private_key_file(monkeypatch, tmp_path):
    monkeypatch.delenv("FERNET_KEY", raising=False)
    monkeypatch.delenv("FERNET_KEY_FILE", raising=False)
    key_path = tmp_path / "roxy_fernet.key"
    monkeypatch.setattr(platform_credentials, "DEFAULT_FERNET_KEY_FILE", str(key_path))

    result = initialize_local_vault_key()
    status = encryption_status()

    assert result["created"] is True
    assert result["mode"] == "0o600"
    assert status["enabled"] is True
    assert status["source"] == "local_key_file"
    assert key_path.exists()
    assert key_path.read_text().strip() not in str(result)
    assert key_path.read_text().strip() not in str(status)


def test_initialize_local_vault_key_does_not_overwrite_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("FERNET_KEY", raising=False)
    monkeypatch.delenv("FERNET_KEY_FILE", raising=False)
    key_path = tmp_path / "roxy_fernet.key"
    monkeypatch.setattr(platform_credentials, "DEFAULT_FERNET_KEY_FILE", str(key_path))

    first = initialize_local_vault_key()
    original = key_path.read_text()
    second = initialize_local_vault_key()

    assert first["created"] is True
    assert second["created"] is False
    assert key_path.read_text() == original


def test_save_platform_credential_creates_vault_metadata(monkeypatch, tmp_path):
    configure_temp_vault(monkeypatch, tmp_path)

    result = save_platform_credential("crypto_com", "CRYPTO_COM_API_KEY", "super-secret-value")
    status = platform_credential_status("crypto_com", env={})

    assert result["name"] == secret_name("crypto_com", "CRYPTO_COM_API_KEY")
    assert result["action"] == "create"
    assert status["key_rows"][0]["source"] == "vault"
    assert "super-secret-value" not in str(status)


def test_save_platform_credentials_rotates_existing_value(monkeypatch, tmp_path):
    configure_temp_vault(monkeypatch, tmp_path)

    first = save_platform_credential("webull", "WEBULL_APP_KEY", "old-value")
    second = save_platform_credential("webull", "WEBULL_APP_KEY", "new-value")

    assert first["version"] == 1
    assert second["action"] == "rotate"
    assert second["version"] == 2
    assert "new-value" not in str(platform_credential_status("webull", env={}))


def test_env_source_beats_vault_source_without_revealing_value(monkeypatch, tmp_path):
    configure_temp_vault(monkeypatch, tmp_path)
    save_platform_credential("schwab", "SCHWAB_CLIENT_ID", "vault-id")

    status = platform_credential_status("schwab", env={"SCHWAB_CLIENT_ID": "env-id"})

    assert status["key_rows"][0]["source"] == "env"
    assert "env-id" not in str(status)
    assert "vault-id" not in str(status)


def test_credential_table_rows_lists_sources_not_values(monkeypatch, tmp_path):
    configure_temp_vault(monkeypatch, tmp_path)
    save_platform_credentials("crypto_com", {"CRYPTO_COM_API_KEY": "api-key", "CRYPTO_COM_API_SECRET": "api-secret"})

    rows = credential_table_rows(env={})
    crypto = next(row for row in rows if row["platform"] == "Crypto.com")

    assert crypto["configured"] is True
    assert "CRYPTO_COM_API_KEY:vault" in crypto["sources"]
    assert "api-key" not in str(rows)
    assert "api-secret" not in str(rows)


def test_robinhood_credentials_are_vault_placeholders_and_preview_only(monkeypatch, tmp_path):
    configure_temp_vault(monkeypatch, tmp_path)
    save_platform_credentials(
        "robinhood",
        {
            "ROBINHOOD_USERNAME": "user@example.com",
            "ROBINHOOD_DEVICE_TOKEN": "device-token",
            "ROBINHOOD_ACCOUNT_ID": "account-id",
        },
    )

    status = platform_credential_status("robinhood", env={"ROXY_ENABLE_LIVE_BROKER_EXECUTION": "1"})

    assert status["configured"] is True
    assert status["strict_preview_only"] is True
    assert status["mode"] == "PREVIEW_ONLY"
    assert status["live_enabled"] is False
    assert all(row["source"] == "vault" for row in status["key_rows"])
    assert "user@example.com" not in str(status)
    assert "device-token" not in str(status)
