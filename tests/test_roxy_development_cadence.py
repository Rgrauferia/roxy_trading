import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools import roxy_development_cadence as cadence


def test_should_run_hourly_when_missing_state():
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)

    assert cadence.should_run_hourly({}, now) is True


def test_should_not_run_hourly_before_interval():
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    state = {"last_hourly_at": (now - timedelta(minutes=10)).isoformat(timespec="seconds")}

    assert cadence.should_run_hourly(state, now) is False


def test_should_run_hourly_after_twenty_minutes():
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    state = {"last_hourly_at": (now - timedelta(minutes=20, seconds=1)).isoformat(timespec="seconds")}

    assert cadence.should_run_hourly(state, now) is True


def test_changed_files_matches_watched_paths():
    git_lines = [
        " M streamlit_app.py",
        " M trade_brief.py",
        "?? tools/roxy_development_cadence.py",
    ]

    changed = cadence.changed_files(git_lines, ["streamlit_app.py", "symbol_detail.py"])

    assert changed == ["streamlit_app.py"]


def test_run_once_writes_cadence_outputs(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "MASTER_CONTEXT.md").write_text("# Master\n")
    (repo / "ROXY_DEVELOPMENT_CADENCE.md").write_text("# Cadence\n")
    (repo / "streamlit_app.py").write_text("print('ok')\n")
    log_dir = tmp_path / "logs" / "development_cadence"
    monkeypatch.setattr(cadence, "LOG_DIR", log_dir)
    monkeypatch.setattr(cadence, "STATE_PATH", log_dir / "state.json")
    monkeypatch.setattr(cadence, "STATUS_PATH", log_dir / "status.json")
    monkeypatch.setattr(cadence, "EVENTS_PATH", log_dir / "events.jsonl")
    monkeypatch.setattr(cadence, "REPORT_PATH", log_dir / "latest_report.md")
    monkeypatch.setattr(cadence, "TASKS_PATH", log_dir / "NEXT_TASKS.md")

    status = cadence.run_once(repo)

    assert status["mode"] == "audit_only"
    assert status["safety"]["places_orders"] is False
    assert (log_dir / "latest_report.md").exists()
    assert (log_dir / "NEXT_TASKS.md").exists()
    saved = json.loads((log_dir / "status.json").read_text())
    assert saved["cadence"]["chart_minutes"] == 20
    assert saved["cadence"]["hourly_minutes"] == 20
    assert "next_chart_tasks" in saved
