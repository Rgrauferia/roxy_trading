import json
from datetime import datetime, timezone

from tools import runtime_backup_screen


def test_build_daemon_command_runs_daemon_with_logs():
    command = runtime_backup_screen.build_daemon_command(interval_hours=12, poll_seconds=60, run_at_start=False)

    assert "tools/runtime_backup_daemon.py" in command
    assert "--interval-hours 12.0" in command
    assert "--poll-seconds 60.0" in command
    assert "--no-run-at-start" in command
    assert "runtime_backup_daemon.out" in command
    assert "runtime_backup_daemon.err" in command


def test_status_marks_fresh_screen_daemon_healthy(tmp_path, monkeypatch):
    heartbeat = tmp_path / "runtime_backup_daemon_heartbeat.json"
    heartbeat.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "RUNNING",
                "pid": 123,
                "last_backup_status": "OK",
                "last_backup_at": datetime.now(timezone.utc).isoformat(),
                "last_archive_path": "/tmp/backup.tar.gz",
                "next_backup_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    monkeypatch.setattr(runtime_backup_screen, "screen_session_exists", lambda session_name: True)
    monkeypatch.setattr(runtime_backup_screen, "pid_is_running", lambda pid: True)

    status = runtime_backup_screen.status(heartbeat_path=heartbeat)

    assert status["running"] is True
    assert status["healthy"] is True
    assert status["last_backup_status"] == "OK"


def test_ensure_does_not_restart_healthy_daemon(monkeypatch):
    healthy = {"healthy": True, "running": True}
    monkeypatch.setattr(runtime_backup_screen, "status", lambda **kwargs: healthy)

    result = runtime_backup_screen.ensure()

    assert result["action"] == "healthy"
    assert result["status"] == healthy
