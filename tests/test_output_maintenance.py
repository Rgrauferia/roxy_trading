import os
import json
from datetime import datetime, timedelta, timezone

from tools.output_maintenance import (
    DEFAULT_ALERT_REPORT_RETENTION_RULES,
    DEFAULT_HISTORY_FILES,
    STALE_OUTPUT_MAX_AGE_DAYS_RULES,
    cleanup_alert_report_files,
    cleanup_log_snapshots,
    cleanup_output_files,
    cleanup_runtime_artifacts,
    cleanup_stale_output_files,
    render_text_report,
    trim_history_file,
    trim_log_files,
    write_report,
)


def test_cleanup_output_files_applies_pattern_retention(tmp_path):
    old_path = tmp_path / "stocks_tech_20260606_000000.csv"
    new_path = tmp_path / "stocks_tech_20260607_000000.csv"
    unrelated = tmp_path / "manual_note.csv"
    old_path.write_text("old")
    new_path.write_text("new")
    unrelated.write_text("keep")
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))

    result = cleanup_output_files(
        output_dir=tmp_path,
        retention_rules={"stocks_tech_*.csv": 1},
    )

    assert result["removed_count"] == 1
    assert not old_path.exists()
    assert new_path.exists()
    assert unrelated.exists()


def test_cleanup_output_files_dry_run_keeps_files(tmp_path):
    first = tmp_path / "ma_confluence_20260606_000000.csv"
    second = tmp_path / "ma_confluence_20260607_000000.csv"
    first.write_text("old")
    second.write_text("new")
    os.utime(first, (1, 1))
    os.utime(second, (2, 2))

    result = cleanup_output_files(
        output_dir=tmp_path,
        retention_rules={"ma_confluence_*.csv": 1},
        dry_run=True,
    )

    assert result["removed_count"] == 1
    assert first.exists()
    assert second.exists()


def test_cleanup_output_files_archives_removed_files(tmp_path):
    output = tmp_path / "output"
    archive = tmp_path / "archive"
    output.mkdir()
    old_path = output / "stocks_tech_20260606_000000.csv"
    new_path = output / "stocks_tech_20260607_000000.csv"
    old_path.write_text("old")
    new_path.write_text("new")
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))

    result = cleanup_output_files(
        output_dir=output,
        retention_rules={"stocks_tech_*.csv": 1},
        archive_dir=archive,
    )

    archived = archive / old_path.name
    assert result["removed_count"] == 1
    assert result["archived_count"] == 1
    assert not old_path.exists()
    assert new_path.exists()
    assert archived.read_text() == "old"


def test_cleanup_output_files_keeps_original_when_archive_fails(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    blocking_file = tmp_path / "archive"
    blocking_file.write_text("not a directory")
    old_path = output / "stocks_tech_20260606_000000.csv"
    new_path = output / "stocks_tech_20260607_000000.csv"
    old_path.write_text("old")
    new_path.write_text("new")
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))

    result = cleanup_output_files(
        output_dir=output,
        retention_rules={"stocks_tech_*.csv": 1},
        archive_dir=blocking_file,
    )

    assert result["removed_count"] == 0
    assert result["archived_count"] == 0
    assert result["archive_error_count"] == 1
    assert old_path.exists()
    assert old_path.read_text() == "old"


def test_default_stale_output_rules_cover_transient_dev_artifacts():
    assert STALE_OUTPUT_MAX_AGE_DAYS_RULES["fine_sweep_*"] == 7.0
    assert STALE_OUTPUT_MAX_AGE_DAYS_RULES["synthetic_ohlcv.csv"] == 7.0
    assert STALE_OUTPUT_MAX_AGE_DAYS_RULES["backtest_batch_summary_*.json"] == 30.0


def test_cleanup_stale_output_files_removes_old_transient_artifacts(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    stale = tmp_path / "fine_sweep_summary.csv"
    fresh = tmp_path / "fine_sweep_latest.csv"
    live = tmp_path / "ma_live_strategy_both_20260610_120000.csv"
    stale.write_text("old")
    fresh.write_text("new")
    live.write_text("live")
    os.utime(stale, ((now - timedelta(days=9)).timestamp(), (now - timedelta(days=9)).timestamp()))
    os.utime(fresh, ((now - timedelta(days=1)).timestamp(), (now - timedelta(days=1)).timestamp()))
    os.utime(live, ((now - timedelta(days=20)).timestamp(), (now - timedelta(days=20)).timestamp()))

    result = cleanup_stale_output_files(
        output_dir=tmp_path,
        max_age_days_rules={"fine_sweep_*": 7.0},
        now=now,
    )

    assert result["removed_count"] == 1
    assert not stale.exists()
    assert fresh.exists()
    assert live.exists()


def test_cleanup_stale_output_files_dry_run_keeps_files(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    stale = tmp_path / "synthetic_ohlcv.csv"
    stale.write_text("old")
    os.utime(stale, ((now - timedelta(days=9)).timestamp(), (now - timedelta(days=9)).timestamp()))

    result = cleanup_stale_output_files(
        output_dir=tmp_path,
        max_age_days_rules={"synthetic_ohlcv.csv": 7.0},
        dry_run=True,
        now=now,
    )

    assert result["removed_count"] == 1
    assert stale.exists()


def test_cleanup_stale_output_files_archives_old_transient_artifacts(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "output"
    archive = tmp_path / "archive"
    output.mkdir()
    stale = output / "synthetic_ohlcv.csv"
    stale.write_text("old")
    os.utime(stale, ((now - timedelta(days=9)).timestamp(), (now - timedelta(days=9)).timestamp()))

    result = cleanup_stale_output_files(
        output_dir=output,
        max_age_days_rules={"synthetic_ohlcv.csv": 7.0},
        archive_dir=archive,
        now=now,
    )

    archived = archive / stale.name
    assert result["removed_count"] == 1
    assert result["archived_count"] == 1
    assert not stale.exists()
    assert archived.read_text() == "old"


def test_write_report_outputs_json_and_text(tmp_path):
    result = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "output_dir": str(tmp_path),
        "dry_run": False,
        "removed_count": 2,
        "output_archive_count": 1,
        "archived": ["archive/a.csv"],
        "removed_counts": {"ma_live_strategy_*.csv": 2},
        "kept_counts": {"ma_live_strategy_*.csv": 96},
        "stale_output_removed_count": 1,
        "stale_output_archived": [],
        "stale_output_removed_counts": {"fine_sweep_*": 1},
        "stale_output_max_age_days_rules": {"fine_sweep_*": 7.0},
        "removed": ["a.csv", "b.csv"],
    }

    json_path, text_path = write_report(result, json_path=tmp_path / "maintenance.json", text_path=tmp_path / "maintenance.txt")

    assert json.loads(json_path.read_text())["removed_count"] == 2
    assert "Roxy output maintenance: DONE" in text_path.read_text()
    assert "removed 2, kept 96" in render_text_report(result)
    assert "Archived output: 1" in render_text_report(result)
    assert "archived output: archive/a.csv" in render_text_report(result)
    assert "Removed stale output: 1" in render_text_report(result)
    assert "stale fine_sweep_*: removed 1, max age 7.0d" in render_text_report(result)


def test_default_history_files_include_realtime_health_history():
    assert "roxy_realtime_history.jsonl" in DEFAULT_HISTORY_FILES


def test_default_alert_report_rules_keep_weekly_reports_bounded():
    assert DEFAULT_ALERT_REPORT_RETENTION_RULES["weekly_report_*.json"] == 12
    assert DEFAULT_ALERT_REPORT_RETENTION_RULES["weekly_report_*.txt"] == 12


def test_cleanup_alert_report_files_applies_report_retention(tmp_path):
    old_path = tmp_path / "weekly_report_20260601_090000.txt"
    mid_path = tmp_path / "weekly_report_20260608_090000.txt"
    new_path = tmp_path / "weekly_report_20260615_090000.txt"
    unrelated = tmp_path / "ma_live_report.txt"
    for idx, path in enumerate([old_path, mid_path, new_path, unrelated], start=1):
        path.write_text(path.name)
        os.utime(path, (idx, idx))

    result = cleanup_alert_report_files(
        alerts_path=tmp_path,
        retention_rules={"weekly_report_*.txt": 2},
    )

    assert result["removed_count"] == 1
    assert not old_path.exists()
    assert mid_path.exists()
    assert new_path.exists()
    assert unrelated.exists()


def test_trim_log_files_keeps_tail_when_file_is_too_large(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "ma_live.out"
    log_path.write_text("a" * 120 + "TAIL")

    trimmed = trim_log_files(log_dirs=[log_dir], max_bytes=100)

    assert len(trimmed) == 1
    assert trimmed[0]["before_bytes"] == 124
    content = log_path.read_text()
    assert "trimmed by Roxy output maintenance" in content
    assert trimmed[0]["after_bytes"] <= 100
    assert len(content.encode()) <= 100
    assert content.endswith("TAIL")


def test_trim_log_files_dry_run_keeps_original_content(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "roxy_run.log"
    original = "x" * 100
    log_path.write_text(original)

    trimmed = trim_log_files(log_dirs=[log_dir], max_bytes=10, dry_run=True)

    assert len(trimmed) == 1
    assert log_path.read_text() == original


def test_trim_history_file_keeps_recent_lines(tmp_path):
    history = tmp_path / "notification_history.jsonl"
    history.write_text("\n".join(f"line-{idx}" for idx in range(10)) + "\n")

    result = trim_history_file(history, max_lines=3)

    assert result["before_lines"] == 10
    assert result["after_lines"] == 3
    assert history.read_text().splitlines() == ["line-7", "line-8", "line-9"]


def test_cleanup_log_snapshots_keeps_recent_files_by_pattern(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    old_path = snapshot_dir / "ma_live.err.20260610_100000"
    mid_path = snapshot_dir / "ma_live.err.20260610_110000"
    new_path = snapshot_dir / "ma_live.err.20260610_120000"
    unrelated = snapshot_dir / "manual.txt"
    for idx, path in enumerate([old_path, mid_path, new_path, unrelated], start=1):
        path.write_text(path.name)
        os.utime(path, (idx, idx))

    result = cleanup_log_snapshots(snapshot_dir=snapshot_dir, keep_count=2)

    assert result["removed_count"] == 1
    assert not old_path.exists()
    assert mid_path.exists()
    assert new_path.exists()
    assert unrelated.exists()


def test_cleanup_log_snapshots_dry_run_keeps_files(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    first = snapshot_dir / "streamlit_launchd.err.1"
    second = snapshot_dir / "streamlit_launchd.err.2"
    first.write_text("old")
    second.write_text("new")
    os.utime(first, (1, 1))
    os.utime(second, (2, 2))

    result = cleanup_log_snapshots(snapshot_dir=snapshot_dir, keep_count=1, dry_run=True)

    assert result["removed_count"] == 1
    assert first.exists()
    assert second.exists()


def test_cleanup_runtime_artifacts_reports_trimmed_logs_and_histories(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    old_path = output / "stocks_tech_20260606_000000.csv"
    new_path = output / "stocks_tech_20260607_000000.csv"
    old_path.write_text("old")
    new_path.write_text("new")
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))
    (logs / "ma_live.out").write_text("z" * 80)
    (alerts / "roxy_learning_journal.csv").write_text("\n".join(str(idx) for idx in range(8)) + "\n")
    old_report = alerts / "weekly_report_20260601_090000.txt"
    new_report = alerts / "weekly_report_20260608_090000.txt"
    old_report.write_text("old")
    new_report.write_text("new")
    os.utime(old_report, (1, 1))
    os.utime(new_report, (2, 2))
    old_snapshot = snapshots / "ma_live.err.20260610_100000"
    new_snapshot = snapshots / "ma_live.err.20260610_120000"
    old_snapshot.write_text("old")
    new_snapshot.write_text("new")
    os.utime(old_snapshot, (1, 1))
    os.utime(new_snapshot, (2, 2))

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={"stocks_tech_*.csv": 1},
        stale_output_rules={"fine_sweep_*": 7.0},
        output_archive_dir=tmp_path / "archive",
        alert_report_retention_rules={"weekly_report_*.txt": 1},
        max_log_bytes=20,
        max_history_lines=3,
        log_snapshot_dir=snapshots,
        log_snapshot_keep_count=1,
    )

    assert result["removed_count"] == 1
    assert result["output_archive_count"] == 1
    assert result["stale_output_removed_count"] == 0
    assert result["trimmed_log_count"] == 1
    assert result["trimmed_history_count"] == 1
    assert result["removed_alert_report_count"] == 1
    assert result["removed_log_snapshot_count"] == 1
    assert "Trimmed logs: 1" in render_text_report(result)
    assert "Archived output: 1" in render_text_report(result)
    assert "Removed alert reports: 1" in render_text_report(result)
    assert "Removed log snapshots: 1" in render_text_report(result)
