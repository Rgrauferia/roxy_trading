import os
import pytest

flask = pytest.importorskip("flask")

from tools import admin_api


def test_admin_api_audit_csv_and_log(tmp_path, monkeypatch):
    # Provide ADMIN_TOKEN via env and config fallback
    token = "testtoken123"
    monkeypatch.setenv("ADMIN_TOKEN", token)

    # ensure storage has at least one role audit entry
    import storage
    db = tmp_path / "roxy.db"
    storage.DB_PATH = str(db)
    storage.init_db(storage.DB_PATH)
    storage.set_user_role("alice", "admin", actor="system")

    client = admin_api.app.test_client()

    # CSV endpoint
    resp = client.get("/audit.csv", headers={"X-Admin-Token": token})
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "target_user" in text or "alice" in text

    # Log endpoint (may be empty at first)
    resp2 = client.get("/audit/log", headers={"X-Admin-Token": token})
    assert resp2.status_code == 200
