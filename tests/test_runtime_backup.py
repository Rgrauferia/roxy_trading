import json
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import tools.runtime_backup as runtime_backup
from tools.runtime_backup import create_runtime_backup, prune_backups, render_text_report, verify_archive_contents


def test_create_runtime_backup_archives_selected_paths(tmp_path):
    base = tmp_path / "project"
    target = tmp_path / "external" / "runtime"
    alerts = base / "alerts"
    db = base / "db"
    alerts.mkdir(parents=True)
    db.mkdir()
    (alerts / "roxy_realtime_check.json").write_text("{}")
    (db / "roxy.db").write_text("db")
    (db / "scan_history.csv").write_text("ts,market,symbol,tf,signal,score\n")

    result = create_runtime_backup(
        base_dir=base,
        target_dir=target,
        report_path=base / "alerts" / "runtime_backup.json",
        text_path=base / "alerts" / "runtime_backup.txt",
        include_paths=("alerts", "db", "data"),
        retention_count=3,
        now=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
    )

    archive_path = target / "roxy_runtime_20260610_120000.tar.gz"
    assert result["status"] == "OK"
    assert result["archive_path"] == str(archive_path)
    assert result["archive_exists"] is True
    assert result["archive_readable"] is True
    assert result["archive_verified"] is True
    assert result["archive_missing_verified_paths"] == []
    assert set(result["archive_verified_paths"]) == {"alerts", "db"}
    assert result["archive_verified_members"] == [
        "alerts/roxy_realtime_check.json",
        "alerts/runtime_backup.json",
        "db/scan_history.csv",
    ]
    assert result["archive_missing_critical_members"] == []
    assert result["archive_database_member_verified"] is True
    assert result["archive_member_count"] >= 4
    assert result["missing_paths"] == ["data"]
    assert json.loads((base / "alerts" / "runtime_backup.json").read_text())["archive_exists"] is True
    assert "Roxy runtime backup: OK" in (base / "alerts" / "runtime_backup.txt").read_text()
    assert "Verified: True" in (base / "alerts" / "runtime_backup.txt").read_text()
    assert "Critical verified: 3/3" in (base / "alerts" / "runtime_backup.txt").read_text()
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
    assert "alerts/roxy_realtime_check.json" in names
    assert "alerts/runtime_backup.json" in names
    assert "db/roxy.db" in names
    assert "db/scan_history.csv" in names


def test_verify_archive_contents_reports_missing_expected_paths(tmp_path):
    archive_path = tmp_path / "runtime.tar.gz"
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "roxy_realtime_check.json").write_text("{}")
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(alerts, arcname="alerts")

    result = verify_archive_contents(archive_path, ("alerts", "db"))

    assert result["archive_readable"] is True
    assert result["archive_verified"] is False
    assert result["archive_verified_paths"] == ["alerts"]
    assert result["archive_missing_verified_paths"] == ["db"]
    assert result["archive_verified_members"] == ["alerts/roxy_realtime_check.json"]
    assert result["archive_missing_critical_members"] == [
        "alerts/runtime_backup.json",
        "db/scan_history.csv",
        "db/*.db",
    ]
    assert result["archive_database_member_verified"] is False


def test_verify_archive_contents_accepts_critical_members(tmp_path):
    archive_path = tmp_path / "runtime.tar.gz"
    alerts = tmp_path / "alerts"
    db = tmp_path / "db"
    alerts.mkdir()
    db.mkdir()
    (alerts / "roxy_realtime_check.json").write_text("{}")
    (alerts / "runtime_backup.json").write_text("{}")
    (db / "scan_history.csv").write_text("ts,market,symbol,tf,signal,score\n")
    (db / "roxy.sqlite3").write_text("db")
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(alerts, arcname="alerts")
        archive.add(db, arcname="db")

    result = verify_archive_contents(archive_path, ("alerts", "db"))

    assert result["archive_readable"] is True
    assert result["archive_verified"] is True
    assert result["archive_missing_verified_paths"] == []
    assert result["archive_verified_members"] == [
        "alerts/roxy_realtime_check.json",
        "alerts/runtime_backup.json",
        "db/scan_history.csv",
    ]
    assert result["archive_missing_critical_members"] == []
    assert result["archive_database_member_verified"] is True


def test_verify_archive_contents_reports_unreadable_archive(tmp_path):
    archive_path = tmp_path / "runtime.tar.gz"
    archive_path.write_text("not a gzip tar")

    result = verify_archive_contents(archive_path, ("alerts",))

    assert result["archive_readable"] is False
    assert result["archive_verified"] is False
    assert result["archive_missing_verified_paths"] == ["alerts"]
    assert result["archive_missing_critical_members"] == [
        "alerts/roxy_realtime_check.json",
        "alerts/runtime_backup.json",
    ]
    assert result["archive_verification_error"]


def test_prune_backups_keeps_recent_archives(tmp_path):
    target = tmp_path / "runtime"
    target.mkdir()
    for idx in range(5):
        path = target / f"roxy_runtime_20260610_12000{idx}.tar.gz"
        path.write_text(str(idx))
        ts = (datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=idx)).timestamp()
        path.touch()
        import os

        os.utime(path, (ts, ts))

    removed = prune_backups(target, retention_count=2)

    remaining = sorted(path.name for path in target.glob("roxy_runtime_*.tar.gz"))
    assert len(removed) == 3
    assert remaining == ["roxy_runtime_20260610_120003.tar.gz", "roxy_runtime_20260610_120004.tar.gz"]


def test_create_runtime_backup_removes_temp_archive_on_failure(tmp_path, monkeypatch):
    base = tmp_path / "project"
    target = tmp_path / "external" / "runtime"
    alerts = base / "alerts"
    alerts.mkdir(parents=True)
    (alerts / "roxy_realtime_check.json").write_text("{}")

    def fail_open(*args, **kwargs):
        raise RuntimeError("tar failed")

    monkeypatch.setattr(runtime_backup.tarfile, "open", fail_open)

    with pytest.raises(RuntimeError):
        create_runtime_backup(
            base_dir=base,
            target_dir=target,
            report_path=base / "alerts" / "runtime_backup.json",
            text_path=base / "alerts" / "runtime_backup.txt",
            include_paths=("alerts",),
            now=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
        )

    assert not list(target.glob("roxy_runtime_*.tar.gz"))
    assert not list(target.glob("*.tmp"))


def test_create_runtime_backup_uses_verified_local_fallback_when_external_target_is_denied(tmp_path, monkeypatch):
    base = tmp_path / "project"
    external = tmp_path / "external" / "runtime"
    fallback = tmp_path / "local" / "runtime"
    alerts = base / "alerts"
    db = base / "db"
    alerts.mkdir(parents=True)
    db.mkdir()
    (alerts / "roxy_realtime_check.json").write_text("{}")
    (db / "scan_history.csv").write_text("ts,market,symbol,tf,signal,score\n")
    (db / "roxy.db").write_text("db")
    real_tar_open = runtime_backup.tarfile.open

    def deny_external(path, *args, **kwargs):
        if str(path).startswith(str(external)):
            raise PermissionError("external volume denied to LaunchAgent")
        return real_tar_open(path, *args, **kwargs)

    monkeypatch.setattr(runtime_backup.tarfile, "open", deny_external)

    result = create_runtime_backup(
        base_dir=base,
        target_dir=external,
        fallback_target_dir=fallback,
        report_path=alerts / "runtime_backup.json",
        text_path=alerts / "runtime_backup.txt",
        include_paths=("alerts", "db"),
        now=datetime(2026, 7, 18, 20, 0, tzinfo=timezone.utc),
    )

    assert result["status"] == "OK"
    assert result["target_fallback"] is True
    assert result["requested_target_dir"] == str(external)
    assert result["target_dir"] == str(fallback)
    assert result["archive_verified"] is True
    assert Path(result["archive_path"]).exists()
    assert "PermissionError" in result["target_fallback_reason"]
    assert "Target fallback:" in (alerts / "runtime_backup.txt").read_text()


def test_render_text_report_includes_missing_paths():
    text = render_text_report(
        {
            "status": "OK",
            "generated_at": "2026-06-10T12:00:00+00:00",
            "archive_path": "/tmp/backup.tar.gz",
            "archive_size_bytes": 123,
            "include_paths": ["alerts"],
            "removed_count": 0,
            "missing_paths": ["data"],
        }
    )

    assert "Missing: data" in text
