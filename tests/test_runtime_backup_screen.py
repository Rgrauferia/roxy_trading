import json
from datetime import datetime, timezone

from tools import runtime_backup_daemon, runtime_backup_screen


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
    healthy = {"healthy": True, "running": True, "process_count": 1}
    monkeypatch.setattr(runtime_backup_screen, "status", lambda **kwargs: healthy)

    result = runtime_backup_screen.ensure()

    assert result["action"] == "healthy"
    assert result["status"] == healthy


def test_status_accepts_orphaned_screen_process_when_heartbeat_is_fresh(tmp_path, monkeypatch):
    heartbeat = tmp_path / "runtime_backup_daemon_heartbeat.json"
    heartbeat.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "RUNNING",
                "pid": 321,
                "last_backup_status": "OK",
            }
        )
    )
    monkeypatch.setattr(runtime_backup_screen, "screen_session_exists", lambda session_name: False)
    monkeypatch.setattr(runtime_backup_screen, "pid_is_running", lambda pid: True)
    monkeypatch.setattr(runtime_backup_screen, "runtime_backup_daemon_pids", lambda: [321])

    result = runtime_backup_screen.status(heartbeat_path=heartbeat)

    assert result["running"] is True
    assert result["healthy"] is True
    assert result["process_count"] == 1


def test_ensure_deduplicates_multiple_daemons(monkeypatch):
    before = {"healthy": True, "running": True, "process_count": 3, "session_exists": False}
    stopped = []
    monkeypatch.setattr(runtime_backup_screen, "status", lambda **kwargs: before)
    monkeypatch.setattr(runtime_backup_screen, "stop", lambda session_name: stopped.append(session_name))
    monkeypatch.setattr(runtime_backup_screen.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        runtime_backup_screen,
        "start",
        lambda **kwargs: {"status": {"healthy": True, "process_count": 1}, "command": "daemon"},
    )

    result = runtime_backup_screen.ensure()

    assert result["action"] == "deduplicated"
    assert stopped == [runtime_backup_screen.DEFAULT_SESSION_NAME]


def test_previous_backup_result_reuses_verified_report(tmp_path):
    report = tmp_path / "runtime_backup.json"
    report.write_text(
        json.dumps({"status": "OK", "generated_at": "2026-07-19T12:00:00+00:00", "archive_path": "/backup.tgz"})
    )

    result = runtime_backup_daemon.previous_backup_result(report)

    assert result is not None
    assert result["archive_path"] == "/backup.tgz"
