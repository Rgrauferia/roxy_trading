import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.output_maintenance import (
    DEFAULT_ALERT_REPORT_RETENTION_RULES,
    DEFAULT_DASHBOARD_HISTORY_MAX_ROWS,
    DEFAULT_HISTORY_FILES,
    STALE_OUTPUT_MAX_AGE_DAYS_RULES,
    compact_dashboard_history_file,
    cleanup_alert_report_files,
    cleanup_local_safe_cache_from_pressure_report,
    cleanup_log_snapshots,
    cleanup_output_files,
    cleanup_partial_video_learning_artifacts,
    cleanup_runtime_artifacts,
    cleanup_stale_output_files,
    compact_learning_journal_history_file,
    directory_footprint,
    history_file_budget_reports,
    local_cache_cleanup_skip_summary,
    maintenance_hygiene_summary,
    maintenance_operation_summary,
    maintenance_top_level_aliases,
    render_text_report,
    runtime_footprint,
    sqlite_db_maintenance,
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


def test_runtime_footprint_counts_runtime_files_and_bytes(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    for path in (output, alerts, logs):
        path.mkdir()
    (output / "scan.csv").write_text("abcd")
    (alerts / "health.json").write_text("{}")
    (logs / "ma_live.out").write_text("xyz")

    footprint = runtime_footprint(output_dir=output, alerts_path=alerts, log_dirs=[logs])

    assert directory_footprint(output)["files"] == 1
    assert footprint["total_files"] == 3
    assert footprint["total_bytes"] == 9
    assert footprint["output"]["bytes"] == 4


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
    assert STALE_OUTPUT_MAX_AGE_DAYS_RULES["plots/fine_sweep_*.png"] == 7.0
    assert STALE_OUTPUT_MAX_AGE_DAYS_RULES["plots/sweep_*.png"] == 7.0
    assert STALE_OUTPUT_MAX_AGE_DAYS_RULES["plots/analysis_fine_sweep_*.png"] == 30.0
    assert STALE_OUTPUT_MAX_AGE_DAYS_RULES["backtests/fine_sweep_*.json"] == 30.0
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


def test_cleanup_stale_output_files_covers_nested_backtest_artifacts(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    plots = tmp_path / "plots"
    backtests = tmp_path / "backtests"
    plots.mkdir()
    backtests.mkdir()
    stale_plot = plots / "fine_sweep_bs30_ps0p05_bs26_ps0p075.png"
    stale_summary_plot = plots / "sweep_bs30_ps0p05.png"
    stale_analysis_plot = plots / "analysis_fine_sweep_bs30_ps0p05_bs26_ps0p075.png"
    stale_backtest = backtests / "fine_sweep_bs30_ps0p05_bs26_ps0p075.json"
    fresh_backtest = backtests / "fine_sweep_bs30_ps0p05_bs28_ps0p075.json"
    persistent_plot = plots / "top_backtests_compare.png"
    for path in [
        stale_plot,
        stale_summary_plot,
        stale_analysis_plot,
        stale_backtest,
        fresh_backtest,
        persistent_plot,
    ]:
        path.write_text(path.name)
    old = now - timedelta(days=40)
    fresh = now - timedelta(days=1)
    for path in [stale_plot, stale_summary_plot, stale_analysis_plot, stale_backtest]:
        os.utime(path, (old.timestamp(), old.timestamp()))
    for path in [fresh_backtest, persistent_plot]:
        os.utime(path, (fresh.timestamp(), fresh.timestamp()))

    result = cleanup_stale_output_files(
        output_dir=tmp_path,
        max_age_days_rules=STALE_OUTPUT_MAX_AGE_DAYS_RULES,
        now=now,
    )

    assert result["removed_count"] == 4
    assert not stale_plot.exists()
    assert not stale_summary_plot.exists()
    assert not stale_analysis_plot.exists()
    assert not stale_backtest.exists()
    assert fresh_backtest.exists()
    assert persistent_plot.exists()
    assert result["removed_counts"]["plots/fine_sweep_*.png"] == 1
    assert result["removed_counts"]["plots/sweep_*.png"] == 1
    assert result["removed_counts"]["plots/analysis_fine_sweep_*.png"] == 1
    assert result["removed_counts"]["backtests/fine_sweep_*.json"] == 1


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


def test_cleanup_local_safe_cache_blocks_manual_top_source(tmp_path):
    cache_dir = tmp_path / "Library" / "Caches"
    cache_dir.mkdir(parents=True)
    old_cache = cache_dir / "old.cache"
    old_cache.write_text("cache")
    report = tmp_path / "local_storage_pressure_sources.json"
    report.write_text(
        json.dumps(
            {
                "check": {
                    "status": "INFO",
                    "cleanup_plan_state": "MANUAL_REVIEW_REQUIRED",
                    "cleanup_automation_ready": False,
                    "cleanup_automation_blocked_reason": "manual_top_source",
                    "safe_cleanup_entries": [{"name": "Library/Caches", "path": str(cache_dir)}],
                }
            }
        )
    )

    result = cleanup_local_safe_cache_from_pressure_report(report_path=report, enabled=True)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "manual_top_source"
    assert result["removed_count"] == 0
    assert old_cache.exists()


def test_cleanup_local_safe_cache_infers_plan_from_older_pressure_cache(tmp_path):
    cache_dir = tmp_path / "Library" / "Caches"
    cache_dir.mkdir(parents=True)
    report = tmp_path / "local_storage_pressure_sources.json"
    report.write_text(
        json.dumps(
            {
                "check": {
                    "status": "INFO",
                    "pressure_active": True,
                    "top_entries": [
                        {"name": "Downloads", "cleanup_policy": "MANUAL_REVIEW_REQUIRED"},
                        {"name": "Library/Caches", "cleanup_policy": "SAFE_CACHE_REVIEW", "path": str(cache_dir)},
                    ],
                    "safe_cleanup_entries": [{"name": "Library/Caches", "path": str(cache_dir)}],
                    "manual_review_entries": [{"name": "Downloads"}],
                }
            }
        )
    )

    result = cleanup_local_safe_cache_from_pressure_report(report_path=report, enabled=True)

    assert result["status"] == "BLOCKED"
    assert result["plan_state"] == "MANUAL_REVIEW_REQUIRED"
    assert result["automation_ready"] is False
    assert result["reason"] == "manual_top_source"


def test_cleanup_local_safe_cache_removes_old_files_when_plan_ready(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    cache_dir = tmp_path / "Library" / "Caches"
    cache_dir.mkdir(parents=True)
    old_cache = cache_dir / "old.cache"
    fresh_cache = cache_dir / "fresh.cache"
    old_cache.write_text("old")
    fresh_cache.write_text("fresh")
    os.utime(old_cache, ((now - timedelta(days=10)).timestamp(), (now - timedelta(days=10)).timestamp()))
    os.utime(fresh_cache, ((now - timedelta(days=1)).timestamp(), (now - timedelta(days=1)).timestamp()))
    report = tmp_path / "local_storage_pressure_sources.json"
    report.write_text(
        json.dumps(
            {
                "check": {
                    "status": "INFO",
                    "cleanup_plan_state": "SAFE_CACHE_REVIEW_READY",
                    "cleanup_automation_ready": True,
                    "safe_cleanup_entries": [{"name": "Library/Caches", "path": str(cache_dir)}],
                }
            }
        )
    )

    dry = cleanup_local_safe_cache_from_pressure_report(
        report_path=report,
        enabled=True,
        dry_run=True,
        min_age_days=7,
        now=now,
    )
    assert dry["status"] == "DRY_RUN"
    assert dry["removed_count"] == 1
    assert dry["fresh_protected_count"] == 1
    assert dry["fresh_protected_bytes"] == 5
    assert old_cache.exists()
    result = cleanup_local_safe_cache_from_pressure_report(
        report_path=report,
        enabled=True,
        min_age_days=7,
        now=now,
    )

    assert result["status"] == "DONE"
    assert result["removed_count"] == 1
    assert result["removed_bytes"] == 3
    assert result["fresh_protected_count"] == 1
    assert result["fresh_protected_bytes"] == 5
    assert not old_cache.exists()
    assert fresh_cache.exists()


def test_cleanup_local_safe_cache_reports_unlink_skip_metadata(tmp_path, monkeypatch):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    cache_dir = tmp_path / "Library" / "Caches"
    cache_dir.mkdir(parents=True)
    old_cache = cache_dir / "locked.cache"
    old_cache.write_text("old")
    os.utime(old_cache, ((now - timedelta(days=10)).timestamp(), (now - timedelta(days=10)).timestamp()))
    report = tmp_path / "local_storage_pressure_sources.json"
    report.write_text(
        json.dumps(
            {
                "check": {
                    "status": "INFO",
                    "cleanup_plan_state": "SAFE_CACHE_REVIEW_READY",
                    "cleanup_automation_ready": True,
                    "safe_cleanup_entries": [{"name": "Library/Caches", "path": str(cache_dir)}],
                }
            }
        )
    )

    def fail_unlink(self, missing_ok=False):
        if self == old_cache:
            raise OSError("locked")
        return original_unlink(self, missing_ok=missing_ok)

    original_unlink = Path.unlink
    monkeypatch.setattr(Path, "unlink", fail_unlink)

    result = cleanup_local_safe_cache_from_pressure_report(
        report_path=report,
        enabled=True,
        min_age_days=7,
        now=now,
    )

    assert result["status"] == "DONE"
    assert result["removed_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped_bytes"] == 3
    assert result["skipped_mb"] == 0.0
    assert result["skipped_top_reason"] == "unlink_error"
    assert result["skipped_top_path"] == str(old_cache)
    assert result["skipped_ratio"] == 1.0
    assert result["skip_state"] == "ALL_ELIGIBLE_SKIPPED"
    assert result["retry_recommended"] is True
    assert old_cache.exists()


def test_local_cache_cleanup_skip_summary_marks_all_eligible_skipped():
    summary = local_cache_cleanup_skip_summary(
        {"eligible_bytes": 53248, "skipped_bytes": 53248, "skipped_count": 1}
    )

    assert summary["skipped_ratio"] == 1.0
    assert summary["skip_state"] == "ALL_ELIGIBLE_SKIPPED"
    assert summary["retry_recommended"] is True


def test_cleanup_local_safe_cache_previews_candidates_when_disabled(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    cache_dir = tmp_path / "Library" / "Caches"
    cache_dir.mkdir(parents=True)
    old_cache = cache_dir / "old.cache"
    fresh_cache = cache_dir / "fresh.cache"
    old_cache.write_text("old")
    fresh_cache.write_text("fresh")
    os.utime(old_cache, ((now - timedelta(days=10)).timestamp(), (now - timedelta(days=10)).timestamp()))
    os.utime(fresh_cache, ((now - timedelta(days=1)).timestamp(), (now - timedelta(days=1)).timestamp()))
    report = tmp_path / "local_storage_pressure_sources.json"
    report.write_text(
        json.dumps(
            {
                "check": {
                    "status": "INFO",
                    "cleanup_plan_state": "SAFE_CACHE_REVIEW_READY",
                    "cleanup_automation_ready": True,
                    "safe_cleanup_entries": [{"name": "Library/Caches", "path": str(cache_dir)}],
                }
            }
        )
    )

    result = cleanup_local_safe_cache_from_pressure_report(
        report_path=report,
        enabled=False,
        min_age_days=7,
        now=now,
    )

    assert result["status"] == "SKIPPED"
    assert result["reason"] == "disabled"
    assert result["eligible_count"] == 1
    assert result["eligible_bytes"] == 3
    assert result["fresh_protected_count"] == 1
    assert result["fresh_protected_bytes"] == 5
    assert result["removed_count"] == 0
    assert old_cache.exists()
    assert fresh_cache.exists()


def test_cleanup_partial_video_learning_artifacts_removes_unindexed_partial_target(tmp_path):
    training = tmp_path / "training_videos"
    target = training / "partial_video"
    target.mkdir(parents=True)
    (target / "frame.jpg").write_bytes(b"x" * 1024)
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "source_path": "/tmp/lesson.mp4-2.download.mp4",
                "processed_at": "2026-06-10T00:00:00+00:00",
                "target_dir": str(target),
            }
        )
    )
    (training / "video_learning_index.json").write_text(json.dumps({"videos": [], "materials": []}))

    result = cleanup_partial_video_learning_artifacts(training_videos_path=training)

    assert result["status"] == "DONE"
    assert result["removed_count"] == 1
    assert result["reclaimed_bytes"] > 0
    assert not target.exists()


def test_cleanup_partial_video_learning_artifacts_dry_run_keeps_target(tmp_path):
    training = tmp_path / "training_videos"
    target = training / "partial_video"
    target.mkdir(parents=True)
    (target / "frame.jpg").write_bytes(b"x")
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "source_path": "/tmp/lesson.mp4-2.download.mp4",
                "processed_at": "2026-06-10T00:00:00+00:00",
                "target_dir": str(target),
            }
        )
    )
    (training / "video_learning_index.json").write_text(json.dumps({"videos": [], "materials": []}))

    result = cleanup_partial_video_learning_artifacts(training_videos_path=training, dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["removed_count"] == 1
    assert target.exists()


def test_write_report_outputs_json_and_text(tmp_path):
    result = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "output_dir": str(tmp_path),
        "dry_run": False,
        "removed_count": 2,
        "output_archive_count": 1,
        "archived": ["archive/a.csv"],
        "prepared_dir_count": 1,
        "prepared_dirs": {"created_dirs": ["archive"], "dir_errors": {}},
        "removed_counts": {"ma_live_strategy_*.csv": 2},
        "kept_counts": {"ma_live_strategy_*.csv": 96},
        "stale_output_removed_count": 1,
        "stale_output_archived": [],
        "stale_output_removed_counts": {"fine_sweep_*": 1},
        "stale_output_max_age_days_rules": {"fine_sweep_*": 7.0},
        "runtime_footprint_after": {"total_mb": 12.5},
        "runtime_footprint_reclaimed_bytes": 42,
        "sqlite_db_size_mb": 181.0,
        "sqlite_db_reclaimable_mb": 0.0,
        "sqlite_db_vacuumed": False,
        "sqlite_maintenance": {"status": "OK", "optimized": True, "freelist_count": 0, "reclaimable_mb": 0.0},
        "removed": ["a.csv", "b.csv"],
        "hygiene_summary": {"label": "Protegido", "detail": "archive OK", "next_action": "Monitorear"},
    }

    json_path, text_path = write_report(result, json_path=tmp_path / "maintenance.json", text_path=tmp_path / "maintenance.txt")

    assert json.loads(json_path.read_text())["removed_count"] == 2
    assert "Roxy output maintenance: DONE" in text_path.read_text()
    assert "removed 2, kept 96" in render_text_report(result)
    assert "Archived output: 1" in render_text_report(result)
    assert "archived output: archive/a.csv" in render_text_report(result)
    assert "Prepared external dirs: 1" in render_text_report(result)
    assert "Runtime footprint: 12.5 MB" in render_text_report(result)
    assert "SQLite DB: 181.0 MB | reclaimable 0.0 MB | vacuumed False" in render_text_report(result)
    assert "sqlite maintenance: OK | optimized True" in render_text_report(result)
    assert "Next action: Monitorear" in render_text_report(result)
    assert "Reclaimed runtime bytes: 42" in render_text_report(result)
    assert "prepared dir: archive" in render_text_report(result)
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
    assert result["removed_lines"] == 7
    assert history.read_text().splitlines() == ["line-7", "line-8", "line-9"]


def test_trim_history_file_preserves_csv_header_when_capping_lines(tmp_path):
    history = tmp_path / "roxy_learning_journal.csv"
    history.write_text("generated_at,symbol,action\n" + "\n".join(f"ts-{idx},SYM{idx},WATCH" for idx in range(6)) + "\n")

    result = trim_history_file(history, max_lines=4)

    assert result["before_lines"] == 7
    assert result["after_lines"] == 4
    assert result["removed_lines"] == 3
    assert result["preserved_header"] is True
    assert history.read_text().splitlines() == [
        "generated_at,symbol,action",
        "ts-3,SYM3,WATCH",
        "ts-4,SYM4,WATCH",
        "ts-5,SYM5,WATCH",
    ]


def test_compact_learning_journal_history_file_keeps_first_and_last_fingerprint_rows(tmp_path):
    history = tmp_path / "roxy_learning_journal.csv"
    history.write_text(
        "generated_at,symbol,fingerprint\n"
        "2026-06-14T00:00:00+00:00,BNB,fp-a\n"
        "2026-06-14T00:05:00+00:00,BNB,fp-a\n"
        "2026-06-14T00:10:00+00:00,BNB,fp-a\n"
        "2026-06-14T00:15:00+00:00,ETH,fp-b\n"
        "2026-06-14T00:20:00+00:00,ETH,fp-b\n"
    )

    result = compact_learning_journal_history_file(history)

    assert result["before_lines"] == 6
    assert result["after_lines"] == 5
    assert result["removed_lines"] == 1
    assert result["compaction_type"] == "learning_journal_duplicate_fingerprint"
    assert history.read_text().splitlines() == [
        "generated_at,symbol,fingerprint",
        "2026-06-14T00:00:00+00:00,BNB,fp-a",
        "2026-06-14T00:10:00+00:00,BNB,fp-a",
        "2026-06-14T00:15:00+00:00,ETH,fp-b",
        "2026-06-14T00:20:00+00:00,ETH,fp-b",
    ]


def test_trim_history_file_preserves_csv_header_when_bounding_bytes(tmp_path):
    history = tmp_path / "roxy_learning_journal.csv"
    history.write_text(
        "generated_at,symbol,action\n"
        + "\n".join(f"2026-06-12T00:0{idx}:00+00:00,SYM{idx},WATCH-{'x' * 20}" for idx in range(5))
        + "\n"
    )

    result = trim_history_file(history, max_lines=6, max_bytes=110, min_lines=3)

    lines = history.read_text().splitlines()
    assert result["preserved_header"] is True
    assert result["after_lines"] == 3
    assert result["removed_lines"] == 3
    assert lines[0] == "generated_at,symbol,action"
    assert lines[1:] == [
        "2026-06-12T00:03:00+00:00,SYM3,WATCH-" + "x" * 20,
        "2026-06-12T00:04:00+00:00,SYM4,WATCH-" + "x" * 20,
    ]


def test_trim_history_file_bounds_bytes_while_preserving_recent_minimum(tmp_path):
    history = tmp_path / "roxy_realtime_history.jsonl"
    history.write_text("\n".join(f"line-{idx}-{'x' * 20}" for idx in range(10)) + "\n")

    result = trim_history_file(history, max_lines=10, max_bytes=70, min_lines=3)

    lines = history.read_text().splitlines()
    assert result["before_lines"] == 10
    assert result["after_lines"] == 3
    assert result["removed_lines"] == 7
    assert result["before_bytes"] > result["after_bytes"]
    assert result["after_bytes"] > 70
    assert lines == [
        "line-7-" + "x" * 20,
        "line-8-" + "x" * 20,
        "line-9-" + "x" * 20,
    ]


def test_trim_history_file_dry_run_reports_byte_trim_without_writing(tmp_path):
    history = tmp_path / "roxy_realtime_history.jsonl"
    original = "\n".join(f"line-{idx}-{'x' * 20}" for idx in range(6)) + "\n"
    history.write_text(original)

    result = trim_history_file(history, max_lines=6, max_bytes=80, min_lines=2, dry_run=True)

    assert result["after_lines"] == 2
    assert result["removed_bytes"] > 0
    assert history.read_text() == original


def test_history_file_budget_reports_flags_near_limit_without_trimming(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    near = alerts / "alert_quality_history.jsonl"
    near.write_text("\n".join(f"line-{idx}" for idx in range(9)) + "\n")
    ok = alerts / "notification_history.jsonl"
    ok.write_text("short\n")

    reports = history_file_budget_reports(
        alerts_path=alerts,
        history_files=("alert_quality_history.jsonl", "notification_history.jsonl"),
        max_lines=10,
        max_bytes=500,
        warn_ratio=0.85,
    )

    assert len(reports) == 2
    near_report = reports[0]
    assert near_report["name"] == "alert_quality_history.jsonl"
    assert near_report["status"] == "NEAR_LIMIT"
    assert near_report["line_count"] == 9
    assert near_report["max_lines"] == 10
    assert near_report["line_ratio"] == 0.9
    assert near_report["line_margin"] == 1
    assert near_report["line_warn_threshold"] == 8
    assert near_report["estimated_appends_until_line_warn"] == 0
    assert near_report["estimated_appends_until_warn"] == 0
    assert near_report["byte_ratio"] < 1.0
    assert near.read_text().splitlines() == [f"line-{idx}" for idx in range(9)]
    assert reports[1]["status"] == "OK"
    assert reports[1]["estimated_appends_until_line_warn"] == 7


def test_history_file_budget_reports_surfaces_projected_byte_pressure(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    history = alerts / "roxy_realtime_history.jsonl"
    history.write_text("\n".join(f"line-{idx:03d}-{'x' * 22}" for idx in range(132)) + "\n")

    reports = history_file_budget_reports(
        alerts_path=alerts,
        history_files=("roxy_realtime_history.jsonl",),
        max_lines=500,
        max_bytes=5000,
        warn_ratio=0.85,
        byte_projection_lines=4,
    )

    report = reports[0]
    assert report["status"] == "OK"
    assert report["projected_next_status"] == "NEAR_LIMIT"
    assert report["byte_ratio"] < 0.85
    assert report["projected_next_byte_ratio"] >= 0.85
    assert report["byte_projection_lines"] == 4
    assert report["average_recent_line_bytes"] == 32.0
    assert report["byte_warn_threshold"] == 4250
    assert report["estimated_appends_until_byte_warn"] == 1
    assert report["estimated_appends_until_warn"] == 1
    assert report["projected_next_bytes"] >= 4250
    assert report["projected_next_byte_margin"] < report["byte_margin"]
    assert report["projected_next_line_count"] == 136
    assert report["projected_next_line_ratio"] == 0.272


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


def test_compact_dashboard_history_file_dedupes_and_bounds_rows(tmp_path):
    history = tmp_path / "scan_history.csv"
    history.write_text(
        "\n".join(
            [
                "ts,market,symbol,tf,signal,score,rr_tp2,entry,stop,tp2",
                "2026-06-10T12:00:00+00:00,stocks,AAPL,1h,WATCH,80,2,100,98,104",
                "2026-06-10T12:00:30+00:00,stocks,AAPL,1h,WATCH,80.2,2,100,98,104",
                "2026-06-10T12:02:00+00:00,stocks,MSFT,1h,WATCH,82,2,200,196,208",
                "2026-06-10T12:03:00+00:00,stocks,NVDA,1h,WATCH,83,2,300,294,312",
            ]
        )
        + "\n"
    )

    result = compact_dashboard_history_file(history, max_rows=2)

    assert result["compacted"] is True
    assert result["before_rows"] == 4
    assert result["after_rows"] == 2
    assert result["removed_rows"] == 2
    assert "MSFT" in history.read_text()
    assert "NVDA" in history.read_text()
    assert "AAPL" not in history.read_text()


def test_compact_dashboard_history_file_dry_run_keeps_file(tmp_path):
    history = tmp_path / "scan_history.csv"
    original = "\n".join(
        [
            "ts,market,symbol,tf,signal,score,rr_tp2,entry,stop,tp2",
            "2026-06-10T12:00:00+00:00,stocks,AAPL,1h,WATCH,80,2,100,98,104",
            "2026-06-10T12:00:30+00:00,stocks,AAPL,1h,WATCH,80.2,2,100,98,104",
        ]
    ) + "\n"
    history.write_text(original)

    result = compact_dashboard_history_file(history, max_rows=1, dry_run=True)

    assert result["reason"] == "dry_run"
    assert result["before_rows"] == 2
    assert history.read_text() == original


def test_default_dashboard_history_max_rows_is_bounded():
    assert DEFAULT_DASHBOARD_HISTORY_MAX_ROWS == 5000


def test_sqlite_db_maintenance_vacuums_when_reclaimable(tmp_path):
    db_path = tmp_path / "roxy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE candles(id INTEGER PRIMARY KEY, payload BLOB)")
        payload = b"x" * 4096
        conn.executemany("INSERT INTO candles(payload) VALUES (?)", [(payload,) for _ in range(200)])
        conn.execute("DROP TABLE candles")

    dry = sqlite_db_maintenance(db_path, dry_run=True, vacuum_min_reclaim_mb=0.0)
    result = sqlite_db_maintenance(db_path, dry_run=False, vacuum_min_reclaim_mb=0.0)

    assert dry["exists"] is True
    assert dry["optimized"] is False
    assert dry["freelist_count"] > 0
    assert dry["reclaimable_mb"] > 0
    assert result["status"] == "OK"
    assert result["optimized"] is True
    assert result["vacuumed"] is True
    assert result["freelist_count"] == 0
    assert result["size_bytes"] < dry["size_bytes"]


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
    dashboard_history = tmp_path / "scan_history.csv"
    dashboard_history.write_text(
        "\n".join(
            [
                "ts,market,symbol,tf,signal,score,rr_tp2,entry,stop,tp2",
                "2026-06-10T12:00:00+00:00,stocks,AAPL,1h,WATCH,80,2,100,98,104",
                "2026-06-10T12:00:30+00:00,stocks,AAPL,1h,WATCH,80.2,2,100,98,104",
            ]
        )
        + "\n"
    )
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
        sqlite_db_path=tmp_path / "missing.db",
        dashboard_history_path=dashboard_history,
    )

    assert result["removed_count"] == 1
    assert result["output_archive_count"] == 1
    assert result["prepared_dir_count"] == 1
    assert result["output_archive_exists"] is True
    assert result["log_snapshot_dir_exists"] is True
    assert result["stale_output_removed_count"] == 0
    assert result["trimmed_log_count"] == 1
    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 5
    assert result["removed_alert_report_count"] == 1
    assert result["removed_log_snapshot_count"] == 1
    assert result["dashboard_history_removed_rows"] == 1
    assert result["dashboard_history_after_rows"] == 1
    assert result["sqlite_maintenance"]["status"] == "MISSING"
    assert result["hygiene_summary"]["label"] == "Protegido"
    assert result["operation_summary"]["label"] == "Limpieza aplicada"
    assert result["status"] == "OK"
    assert result["label"] == "Limpieza aplicada"
    assert result["tone"] == "buy"
    assert result["protected"] is True
    assert result["operation"] == "Limpieza aplicada"
    assert result["operation_status"] == "OK"
    assert result["operation_action_count"] >= 5
    assert result["hygiene_status"] == "OK"
    assert result["hygiene_label"] == "Protegido"
    assert result["hygiene_protected"] is True
    assert result["dashboard_history_rows"] == 1
    assert result["local_cache_plan"] == "MISSING"
    assert result["local_cache_status"] == "BLOCKED"
    assert result["trimmed_history_files"] == ["roxy_learning_journal.csv"]
    assert result["trimmed_history_bytes"] > 0
    assert result["operation_summary"]["protected"] is True
    assert result["operation_summary"]["action_count"] >= 5
    assert result["operation_summary"]["archive_count"] == 1
    assert result["operation_summary"]["removed_file_count"] == 3
    assert result["operation_summary"]["trimmed_item_count"] == 2
    assert result["operation_summary"]["dashboard_history_removed_rows"] == 1
    assert result["hygiene_summary"]["protected"] is True
    assert result["hygiene_summary"]["next_action"] == "Limpieza aplicada"
    assert result["maintenance_next_action"] == "Limpieza aplicada"
    assert result["external_archive_ready"] is True
    assert result["hygiene_summary"]["archive_ready"] is True
    assert result["hygiene_summary"]["log_snapshots_ready"] is True
    assert result["hygiene_summary"]["dashboard_history_rows"] == 1
    assert result["runtime_footprint_before"]["total_files"] >= result["runtime_footprint_after"]["total_files"]
    assert result["runtime_footprint_reclaimed_bytes"] > 0
    assert "Trimmed logs: 1" in render_text_report(result)
    assert "Trimmed histories: 1 | removed lines 5" in render_text_report(result)
    assert "Hygiene: Protegido" in render_text_report(result)
    assert "Operation: Limpieza aplicada" in render_text_report(result)
    assert "Next action: Limpieza aplicada" in render_text_report(result)
    assert "Archived output: 1" in render_text_report(result)
    assert "Removed alert reports: 1" in render_text_report(result)
    assert "Removed log snapshots: 1" in render_text_report(result)
    assert "Dashboard history: 1 rows | removed 1" in render_text_report(result)


def test_cleanup_runtime_artifacts_runs_partial_video_artifact_cleanup(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    training = tmp_path / "training_videos"
    partial = training / "partial_video"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    partial.mkdir(parents=True)
    (partial / "frame.jpg").write_bytes(b"x" * 1024)
    (partial / "manifest.json").write_text(
        json.dumps(
            {
                "source_path": "/tmp/lesson.mp4-2.download.mp4",
                "processed_at": "2026-06-10T00:00:00+00:00",
                "target_dir": str(partial),
            }
        )
    )
    (training / "video_learning_index.json").write_text(json.dumps({"videos": [], "materials": []}))

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=None,
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        dashboard_history_path=tmp_path / "missing_history.csv",
        training_videos_path=training,
    )

    assert result["partial_video_artifact_cleanup_status"] == "DONE"
    assert result["partial_video_artifact_cleanup_removed_count"] == 1
    assert result["operation_summary"]["partial_video_artifact_removed_count"] == 1
    assert result["operation_summary"]["action_count"] >= 1
    assert not partial.exists()
    assert "Partial video artifacts: DONE | removed 1" in render_text_report(result)


def test_cleanup_runtime_artifacts_reports_near_limit_history_budget(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "alert_quality_history.jsonl"
    history.write_text("\n".join(f"line-{idx}" for idx in range(9)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=10,
        max_history_bytes=500,
    )

    assert result["trimmed_history_count"] == 0
    assert result["history_budget_report_count"] == 1
    assert result["history_budget_near_limit_count"] == 1
    assert result["history_budget_over_limit_count"] == 0
    assert result["history_budget_at_cap_count"] == 0
    assert result["history_budget_status"] == "WARN"
    assert result["history_budget_pressure"] == "NEAR_LIMIT"
    assert result["history_budget_attention_file_count"] == 1
    assert result["history_budget_attention_files"][0]["name"] == "alert_quality_history.jsonl"
    assert result["history_budget_top_name"] == "alert_quality_history.jsonl"
    assert result["history_budget_top_status"] == "NEAR_LIMIT"
    assert result["history_budget_top_line_ratio"] == 0.9
    assert result["history_budget_top_line_margin"] == 1
    assert result["current_history_budget_available"] is True
    assert result["current_history_budget_report_count"] == 1
    assert result["current_history_budget_status"] == "WARN"
    assert result["current_history_budget_pressure"] == "NEAR_LIMIT"
    assert result["current_history_budget_attention_file_count"] == 1
    assert result["current_history_budget_top_name"] == "alert_quality_history.jsonl"
    assert result["current_history_budget_top_status"] == "NEAR_LIMIT"
    assert result["current_history_budget_top_line_ratio"] == 0.9
    assert result["current_history_budget_top_line_margin"] == 1
    assert result["current_history_budget_min_estimated_appends_until_warn"] == 0
    assert result["current_history_budget_min_estimated_appends_until_warn_name"] == "alert_quality_history.jsonl"
    assert result["hygiene_summary"]["status"] == "OK"
    assert result["hygiene_summary"]["protected"] is True
    assert result["hygiene_summary"]["history_budget_status"] == "WARN"
    assert result["hygiene_summary"]["history_budget_pressure"] == "NEAR_LIMIT"
    assert result["hygiene_summary"]["next_action"] == "Monitorear historiales"
    assert "hist status warn" in result["hygiene_summary"]["detail"]
    assert (
        "hist budget near 1 over 0 top alert_quality_history.jsonl near_limit lines 90.0%"
        in result["hygiene_summary"]["detail"]
    )
    assert history.read_text().splitlines() == [f"line-{idx}" for idx in range(9)]


def test_cleanup_runtime_artifacts_trims_low_line_margin_history(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "roxy_learning_journal.csv"
    history.write_text("generated_at,symbol,action\n" + "\n".join(f"ts-{idx},SYM{idx},WATCH" for idx in range(493)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=500_000,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 94
    assert result["history_budget_near_limit_count"] == 0
    assert result["history_budget_over_limit_count"] == 0
    assert result["history_budget_at_cap_count"] == 0
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    assert result["history_budget_attention_file_count"] == 0
    assert result["hygiene_summary"]["next_action"] == "Limpieza aplicada"
    report = result["history_budget_reports"][0]
    assert report["name"] == "roxy_learning_journal.csv"
    assert report["status"] == "OK"
    assert report["line_count"] == 400
    assert report["line_ratio"] == 0.8
    trimmed = result["trimmed_histories"][0]
    assert trimmed["configured_max_lines"] == 500
    assert trimmed["low_line_margin_ratio"] == 0.02
    assert trimmed["low_line_margin_threshold"] == 10
    assert trimmed["proactive_line_cap_trim"] is False
    assert trimmed["proactive_low_line_margin_trim"] is True
    lines = history.read_text().splitlines()
    assert len(lines) == 400
    assert lines[0] == "generated_at,symbol,action"
    assert lines[1] == "ts-94,SYM94,WATCH"
    assert lines[-1] == "ts-492,SYM492,WATCH"


def test_cleanup_runtime_artifacts_compacts_learning_journal_before_budget(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "roxy_learning_journal.csv"
    rows = ["generated_at,symbol,fingerprint"]
    for idx in range(141):
        for repeat in range(3):
            rows.append(f"2026-06-14T00:{repeat:02d}:00+00:00,SYM{idx},fp-{idx}")
    history.write_text("\n".join(rows) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=500_000,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 141
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    report = result["history_budget_reports"][0]
    assert report["name"] == "roxy_learning_journal.csv"
    assert report["line_count"] == 283
    trimmed = result["trimmed_histories"][0]
    assert trimmed["compaction_type"] == "learning_journal_duplicate_fingerprint"
    assert history.read_text().splitlines()[0] == "generated_at,symbol,fingerprint"


def test_cleanup_runtime_artifacts_trims_line_warning_history(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "notification_history.jsonl"
    history.write_text("\n".join(f"line-{idx}" for idx in range(432)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=500_000,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 32
    assert result["history_budget_near_limit_count"] == 0
    assert result["history_budget_over_limit_count"] == 0
    assert result["history_budget_at_cap_count"] == 0
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    report = result["history_budget_reports"][0]
    assert report["name"] == "notification_history.jsonl"
    assert report["status"] == "OK"
    assert report["line_count"] == 400
    assert report["line_ratio"] == 0.8
    trimmed = result["trimmed_histories"][0]
    assert trimmed["configured_max_lines"] == 500
    assert trimmed["line_warn_ratio"] == 0.85
    assert trimmed["line_warn_threshold"] == 425
    assert trimmed["proactive_line_cap_trim"] is False
    assert trimmed["proactive_low_line_margin_trim"] is False
    assert trimmed["proactive_line_warn_trim"] is True
    assert history.read_text().splitlines() == [f"line-{idx}" for idx in range(32, 432)]


def test_cleanup_runtime_artifacts_trims_projected_line_warning_history(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "notification_history.jsonl"
    history.write_text("\n".join(f"line-{idx}" for idx in range(424)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=500_000,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 24
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    report = result["history_budget_reports"][0]
    assert report["name"] == "notification_history.jsonl"
    assert report["line_count"] == 400
    assert report["line_ratio"] == 0.8
    trimmed = result["trimmed_histories"][0]
    assert trimmed["name"] == "notification_history.jsonl"
    assert trimmed["line_warn_threshold"] == 425
    assert trimmed["proactive_line_warn_trim"] is False
    assert trimmed["proactive_projected_line_warn_trim"] is True
    assert history.read_text().splitlines() == [f"line-{idx}" for idx in range(24, 424)]


def test_cleanup_runtime_artifacts_trims_projected_line_warning_window(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "notification_history.jsonl"
    history.write_text("\n".join(f"line-{idx}" for idx in range(421)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=500_000,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 21
    assert result["history_budget_projected_near_limit_count"] == 0
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    report = result["history_budget_reports"][0]
    assert report["name"] == "notification_history.jsonl"
    assert report["line_count"] == 400
    assert report["projected_next_line_count"] == 404
    trimmed = result["trimmed_histories"][0]
    assert trimmed["proactive_projected_line_warn_trim"] is True
    assert trimmed["projected_line_window"] == 4
    assert history.read_text().splitlines() == [f"line-{idx}" for idx in range(21, 421)]


def test_cleanup_runtime_artifacts_trims_append_guard_line_warning_window(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "notification_history.jsonl"
    history.write_text("\n".join(f"line-{idx}" for idx in range(420)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=500_000,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 20
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    report = result["history_budget_reports"][0]
    assert report["name"] == "notification_history.jsonl"
    assert report["line_count"] == 400
    assert report["line_ratio"] == 0.8
    trimmed = result["trimmed_histories"][0]
    assert trimmed["name"] == "notification_history.jsonl"
    assert trimmed["line_warn_threshold"] == 425
    assert trimmed["min_appends_until_warn"] == 8
    assert trimmed["projected_line_window"] == 4
    assert trimmed["line_warn_append_guard_window"] == 8
    assert trimmed["proactive_projected_line_warn_trim"] is False
    assert trimmed["proactive_append_guard_line_warn_trim"] is True
    assert history.read_text().splitlines() == [f"line-{idx}" for idx in range(20, 420)]


def test_cleanup_runtime_artifacts_trims_byte_margin_history(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "roxy_realtime_history.jsonl"
    history.write_text("\n".join(f"line-{idx:03d}-{'x' * 23}" for idx in range(130)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=5000,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 9
    assert result["history_budget_near_limit_count"] == 0
    assert result["history_budget_over_limit_count"] == 0
    assert result["history_budget_at_cap_count"] == 0
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    report = result["history_budget_reports"][0]
    assert report["name"] == "roxy_realtime_history.jsonl"
    assert report["status"] == "OK"
    assert report["byte_ratio"] < 0.85
    trimmed = result["trimmed_histories"][0]
    assert trimmed["configured_max_bytes"] == 5000
    assert trimmed["max_bytes"] == 4000
    assert trimmed["byte_margin_warn_ratio"] == 0.85
    assert trimmed["byte_margin_threshold"] == 4250
    assert trimmed["proactive_line_cap_trim"] is False
    assert trimmed["proactive_low_line_margin_trim"] is False
    assert trimmed["proactive_byte_margin_trim"] is True
    lines = history.read_text().splitlines()
    assert len(lines) == 121
    assert lines[0] == "line-009-" + "x" * 23
    assert lines[-1] == "line-129-" + "x" * 23


def test_cleanup_runtime_artifacts_trims_projected_byte_margin_history(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "roxy_realtime_history.jsonl"
    history.write_text("\n".join(f"line-{idx:03d}-{'x' * 22}" for idx in range(132)) + "\n")
    before_size = history.stat().st_size

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=5000,
    )

    assert before_size < 4250
    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] > 0
    assert result["history_budget_near_limit_count"] == 0
    assert result["history_budget_over_limit_count"] == 0
    assert result["history_budget_at_cap_count"] == 0
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    report = result["history_budget_reports"][0]
    assert report["name"] == "roxy_realtime_history.jsonl"
    assert report["status"] == "OK"
    assert report["byte_ratio"] < 0.85
    trimmed = result["trimmed_histories"][0]
    assert trimmed["configured_max_bytes"] == 5000
    assert trimmed["max_bytes"] == 3866
    assert trimmed["byte_margin_warn_ratio"] == 0.85
    assert trimmed["byte_margin_threshold"] == 4250
    assert trimmed["byte_projection_lines"] == 4
    assert trimmed["projected_byte_margin_threshold"] == 4250
    assert trimmed["byte_warn_append_guard_target_window"] == 12
    assert trimmed["byte_append_guard_target_bytes"] == 3866
    assert trimmed["projected_next_bytes"] >= 4250
    assert trimmed["proactive_byte_margin_trim"] is False
    assert trimmed["proactive_projected_byte_margin_trim"] is True


def test_cleanup_runtime_artifacts_trims_append_guard_byte_margin_history(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "roxy_realtime_history.jsonl"
    history.write_text("\n".join(f"line-{idx:03d}-{'x' * 22}" for idx in range(128)) + "\n")
    before_size = history.stat().st_size

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=5000,
    )

    assert before_size < 4250
    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 8
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    report = result["history_budget_reports"][0]
    assert report["name"] == "roxy_realtime_history.jsonl"
    assert report["status"] == "OK"
    assert report["byte_ratio"] < 0.8
    trimmed = result["trimmed_histories"][0]
    assert trimmed["configured_max_bytes"] == 5000
    assert trimmed["max_bytes"] == 3866
    assert trimmed["byte_margin_threshold"] == 4250
    assert trimmed["byte_projection_lines"] == 4
    assert trimmed["byte_warn_append_guard_window"] == 8
    assert trimmed["byte_warn_append_guard_target_window"] == 12
    assert trimmed["byte_append_guard_target_bytes"] == 3866
    assert trimmed["projected_next_bytes"] < 4250
    assert trimmed["projected_append_guard_next_bytes"] >= 4250
    assert trimmed["proactive_byte_margin_trim"] is False
    assert trimmed["proactive_projected_byte_margin_trim"] is False
    assert trimmed["proactive_append_guard_byte_margin_trim"] is True
    lines = history.read_text().splitlines()
    assert len(lines) == 120
    assert lines[0] == "line-008-" + "x" * 22
    assert lines[-1] == "line-127-" + "x" * 22


def test_cleanup_runtime_artifacts_relaxes_min_lines_for_projected_byte_trim(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "roxy_realtime_history.jsonl"
    history.write_text("\n".join(f"line-{idx:03d}-{'x' * 43}" for idx in range(80)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=5000,
        min_history_lines=120,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] > 0
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    assert result["history_budget_projected_near_limit_count"] == 0
    assert result["history_budget_projected_over_limit_count"] == 0
    assert result["history_budget_projected_attention_file_count"] == 0
    assert result["history_budget_projected_top_name"] is None
    assert result["history_budget_projected_top_status"] is None
    assert result["history_budget_projected_pressure"] == "CLEAR"
    assert result["history_budget_margin_bytes"] > 0
    assert result["history_budget_max_projected_usage_ratio"] < 0.85
    assert result["hygiene_summary"]["history_budget_projected_near_limit_count"] == 0
    assert result["hygiene_summary"]["history_budget_projected_top_name"] == ""
    assert result["hygiene_summary"]["next_action"] == "Limpieza aplicada"
    assert result["trimmed_history_min_lines_relaxed_count"] == 1
    assert result["trimmed_history_min_lines_relaxed_files"] == ["roxy_realtime_history.jsonl"]
    assert result["trimmed_history_min_lines_relaxed_top_name"] == "roxy_realtime_history.jsonl"
    assert result["hygiene_summary"]["trimmed_history_min_lines_relaxed_count"] == 1
    assert "hist min relaxed 1" in result["hygiene_summary"]["detail"]
    assert result["operation_summary"]["trimmed_history_min_lines_relaxed_count"] == 1
    assert "hist min relajado 1" in result["operation_summary"]["detail"]
    assert "History min-lines relaxed: 1 | files roxy_realtime_history.jsonl" in render_text_report(result)
    report = result["history_budget_reports"][0]
    assert report["name"] == "roxy_realtime_history.jsonl"
    assert report["byte_ratio"] < 0.85
    assert report["line_count"] < 120
    trimmed = result["trimmed_histories"][0]
    assert trimmed["name"] == "roxy_realtime_history.jsonl"
    assert trimmed["configured_min_lines"] == 120
    assert trimmed["effective_min_lines"] < 120
    assert trimmed["min_line_floor"] == 60
    assert trimmed["min_lines_relaxed"] is True
    assert trimmed["proactive_projected_byte_margin_trim"] is True


def test_cleanup_runtime_artifacts_uses_alert_quality_history_byte_budget(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "alert_quality_history.jsonl"
    history.write_text("\n".join(f"line-{idx:03d}-{'x' * 9000}" for idx in range(208)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=500,
        max_history_bytes=7_500_000,
    )

    assert result["trimmed_history_count"] == 1
    assert result["history_budget_status"] == "OK"
    report = result["history_budget_reports"][0]
    assert report["name"] == "alert_quality_history.jsonl"
    assert report["max_bytes"] == 2_000_000
    assert report["global_max_bytes"] == 7_500_000
    assert report["byte_ratio"] < 0.85
    trimmed = result["trimmed_histories"][0]
    assert trimmed["configured_max_bytes"] == 2_000_000
    assert trimmed["global_configured_max_bytes"] == 7_500_000
    assert trimmed["max_bytes"] == 1_600_000
    assert trimmed["proactive_byte_margin_trim"] is True


def test_cleanup_runtime_artifacts_proactively_trims_line_cap_history(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    history = alerts / "alert_quality_history.jsonl"
    history.write_text("\n".join(f"line-{idx}" for idx in range(10)) + "\n")

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        max_history_lines=10,
        max_history_bytes=500,
        min_history_lines=3,
    )

    assert result["trimmed_history_count"] == 1
    assert result["trimmed_history_removed_lines"] == 2
    assert result["history_budget_report_count"] == 1
    assert result["history_budget_near_limit_count"] == 0
    assert result["history_budget_over_limit_count"] == 0
    assert result["history_budget_at_cap_count"] == 0
    assert result["history_budget_status"] == "OK"
    assert result["history_budget_pressure"] == "CLEAR"
    assert result["history_budget_top_name"] is None
    assert result["history_budget_top_status"] is None
    assert result["history_budget_top_line_ratio"] is None
    assert result["history_budget_top_line_margin"] is None
    assert result["hygiene_summary"]["status"] == "OK"
    assert result["hygiene_summary"]["protected"] is True
    assert result["hygiene_summary"]["next_action"] == "Limpieza aplicada"
    assert "hist trimmed 1/2 lines" in result["hygiene_summary"]["detail"]
    report = result["history_budget_reports"][0]
    assert report["status"] == "OK"
    assert report["line_at_cap"] is False
    assert report["line_ratio"] == 0.8
    trimmed = result["trimmed_histories"][0]
    assert trimmed["configured_max_lines"] == 10
    assert trimmed["max_bytes"] == 500
    assert trimmed["cap_target_ratio"] == 0.8
    assert trimmed["proactive_line_cap_trim"] is True
    assert history.read_text().splitlines() == [f"line-{idx}" for idx in range(2, 10)]


def test_cleanup_runtime_artifacts_prepares_missing_external_dirs(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    archive = tmp_path / "external" / "output_archive"
    snapshots = tmp_path / "external" / "log_snapshots"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=archive,
        log_snapshot_dir=snapshots,
    )

    assert archive.is_dir()
    assert snapshots.is_dir()
    assert result["prepared_dir_count"] == 2
    assert result["prepared_dir_error_count"] == 0
    assert result["output_archive_exists"] is True
    assert result["log_snapshot_dir_exists"] is True
    assert result["log_snapshot_counts"]["exists"] is True


def test_cleanup_runtime_artifacts_records_local_cache_cleanup(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    cache_dir = tmp_path / "Library" / "Caches"
    for path in (output, alerts, logs, cache_dir):
        path.mkdir(parents=True)
    old_cache = cache_dir / "old.cache"
    old_cache.write_text("old")
    os.utime(old_cache, (1, 1))
    pressure_report = alerts / "local_storage_pressure_sources.json"
    pressure_report.write_text(
        json.dumps(
            {
                "check": {
                    "status": "INFO",
                    "cleanup_plan_state": "SAFE_CACHE_REVIEW_READY",
                    "cleanup_automation_ready": True,
                    "safe_cleanup_entries": [{"name": "Library/Caches", "path": str(cache_dir)}],
                }
            }
        )
    )

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        enable_local_cache_cleanup=True,
    )

    assert result["local_cache_cleanup_status"] == "DONE"
    assert result["local_cache_cleanup_plan_state"] == "SAFE_CACHE_REVIEW_READY"
    assert result["local_cache_cleanup_automation_ready"] is True
    assert result["local_cache_cleanup_removed_count"] == 1
    assert result["local_cache_cleanup_skipped_ratio"] == 0.0
    assert result["local_cache_cleanup_skip_state"] == "CLEAR"
    assert result["local_cache_cleanup_retry_recommended"] is False
    assert result["operation_summary"]["local_cache_removed_count"] == 1
    assert "Local cache cleanup: DONE" in render_text_report(result)
    assert not old_cache.exists()


def test_cleanup_runtime_artifacts_marks_all_eligible_local_cache_skipped(tmp_path, monkeypatch):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    cache_dir = tmp_path / "Library" / "Caches"
    for path in (output, alerts, logs, cache_dir):
        path.mkdir(parents=True)
    old_cache = cache_dir / "old.cache"
    old_cache.write_text("locked")
    os.utime(old_cache, (1, 1))
    pressure_report = alerts / "local_storage_pressure_sources.json"
    pressure_report.write_text(
        json.dumps(
            {
                "check": {
                    "status": "INFO",
                    "cleanup_plan_state": "SAFE_CACHE_REVIEW_READY",
                    "cleanup_automation_ready": True,
                    "safe_cleanup_entries": [{"name": "Library/Caches", "path": str(cache_dir)}],
                }
            }
        )
    )
    original_unlink = type(old_cache).unlink

    def fail_locked_cache_unlink(self, *args, **kwargs):
        if self == old_cache:
            raise OSError("locked")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(type(old_cache), "unlink", fail_locked_cache_unlink)

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        enable_local_cache_cleanup=True,
    )

    assert result["local_cache_cleanup_status"] == "DONE"
    assert result["local_cache_cleanup_eligible_count"] == 1
    assert result["local_cache_cleanup_eligible_bytes"] == len("locked")
    assert result["local_cache_cleanup_removed_count"] == 0
    assert result["local_cache_cleanup_skipped_count"] == 1
    assert result["local_cache_cleanup_skipped_bytes"] == len("locked")
    assert result["local_cache_cleanup_skipped_top_reason"] == "unlink_error"
    assert result["local_cache_cleanup_skipped_top_path"] == str(old_cache)
    assert result["local_cache_cleanup_skipped_ratio"] == 1.0
    assert result["local_cache_cleanup_skip_state"] == "ALL_ELIGIBLE_SKIPPED"
    assert result["local_cache_cleanup_retry_recommended"] is True
    assert result["local_cache_cleanup"]["skipped_ratio"] == 1.0
    assert result["local_cache_cleanup"]["skip_state"] == "ALL_ELIGIBLE_SKIPPED"
    assert result["local_cache_cleanup"]["retry_recommended"] is True
    assert "local skipped 1 unlink_error all_eligible_skipped retry" in result["hygiene_summary"]["detail"]
    assert "skip_state ALL_ELIGIBLE_SKIPPED | retry True" in render_text_report(result)
    assert old_cache.exists()


def test_cleanup_runtime_artifacts_records_local_cache_preview_when_disabled(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    cache_dir = tmp_path / "Library" / "Caches"
    for path in (output, alerts, logs, cache_dir):
        path.mkdir(parents=True)
    old_cache = cache_dir / "old.cache"
    old_cache.write_text("old")
    os.utime(old_cache, ((now - timedelta(days=10)).timestamp(), (now - timedelta(days=10)).timestamp()))
    pressure_report = alerts / "local_storage_pressure_sources.json"
    pressure_report.write_text(
        json.dumps(
            {
                "check": {
                    "status": "INFO",
                    "cleanup_plan_state": "SAFE_CACHE_REVIEW_READY",
                    "cleanup_automation_ready": True,
                    "safe_cleanup_entries": [{"name": "Library/Caches", "path": str(cache_dir)}],
                }
            }
        )
    )

    result = cleanup_runtime_artifacts(
        output_dir=output,
        alerts_path=alerts,
        log_dirs=[logs],
        retention_rules={},
        stale_output_rules={},
        output_archive_dir=tmp_path / "archive",
        log_snapshot_dir=tmp_path / "snapshots",
        sqlite_db_path=tmp_path / "missing.db",
        enable_local_cache_cleanup=False,
        local_cache_cleanup_min_age_days=7,
    )

    assert result["local_cache_cleanup_status"] == "SKIPPED"
    assert result["local_cache_cleanup_plan_state"] == "SAFE_CACHE_REVIEW_READY"
    assert result["local_cache_cleanup_eligible_count"] == 1
    assert result["local_cache_cleanup_eligible_bytes"] == 3
    assert result["local_cache_cleanup_fresh_protected_count"] == 0
    assert result["hygiene_summary"]["next_action"] == "Activar limpieza cache local"
    assert "local eligible 1/0.0MB" in result["hygiene_summary"]["detail"]
    assert "eligible 1" in render_text_report(result)
    assert old_cache.exists()


def test_maintenance_hygiene_summary_warns_on_missing_protection():
    summary = maintenance_hygiene_summary(
        {
            "dry_run": True,
            "output_archive_exists": False,
            "log_snapshot_dir_exists": False,
            "output_archive_error_count": 1,
            "prepared_dir_error_count": 0,
            "dashboard_history_after_rows": 6000,
            "dashboard_history_max_rows": 5000,
            "trimmed_history_count": 2,
            "trimmed_history_removed_lines": 40,
            "sqlite_maintenance": {"status": "ERROR", "reclaimable_mb": 80.0},
            "runtime_footprint_after": {"total_mb": 120.5, "total_files": 999},
        }
    )

    assert summary["status"] == "WARN"
    assert summary["tone"] == "avoid"
    assert summary["protected"] is False
    assert "output archive dir missing" in summary["issues"]
    assert "sqlite maintenance error" in summary["issues"]
    assert "dashboard history 6000>5000" in summary["issues"]
    assert summary["trimmed_history_count"] == 2
    assert summary["trimmed_history_removed_lines"] == 40
    assert summary["next_action"] == "Ejecutar limpieza real"
    assert summary["external_archive_ready"] is False


def test_maintenance_operation_summary_surfaces_protection_and_actions():
    result = {
        "dry_run": False,
        "removed_count": 2,
        "stale_output_removed_count": 1,
        "removed_alert_report_count": 3,
        "removed_log_snapshot_count": 4,
        "trimmed_log_count": 1,
        "trimmed_history_count": 1,
        "dashboard_history_removed_rows": 5,
        "local_cache_cleanup_status": "DONE",
        "local_cache_cleanup_removed_count": 2,
        "local_cache_cleanup_removed_bytes": 3 * 1024 * 1024,
        "output_archive_count": 6,
        "runtime_footprint_reclaimed_bytes": 2 * 1024 * 1024,
        "runtime_footprint_after": {"total_mb": 12.5},
        "hygiene_summary": {
            "status": "OK",
            "label": "Protegido",
            "tone": "buy",
            "protected": True,
            "next_action": "Limpieza aplicada",
            "issues": [],
        },
    }

    summary = maintenance_operation_summary(result)

    assert summary["status"] == "OK"
    assert summary["label"] == "Limpieza aplicada"
    assert summary["tone"] == "buy"
    assert summary["protected"] is True
    assert summary["action_count"] == 19
    assert summary["removed_file_count"] == 10
    assert summary["trimmed_item_count"] == 2
    assert summary["dashboard_history_removed_rows"] == 5
    assert summary["local_cache_removed_count"] == 2
    assert summary["local_cache_removed_bytes"] == 3 * 1024 * 1024
    assert summary["archive_count"] == 6
    assert summary["reclaimed_mb"] == 5.0
    assert "acciones 19" in summary["detail"]
    assert "recuperado 5.0MB" in summary["detail"]
    assert "cache removidos 2" in summary["detail"]


def test_maintenance_top_level_aliases_expose_history_budget_files_and_trim_lines():
    aliases = maintenance_top_level_aliases(
        {
            "history_budget_attention_files": [
                {"name": "alert_quality_history.jsonl", "status": "NEAR_LIMIT"},
            ],
            "history_budget_projected_attention_files": [
                {"name": "notification_history.jsonl", "projected_next_status": "NEAR_LIMIT"},
            ],
            "history_budget_projected_near_limit_count": 1,
            "history_budget_projected_over_limit_count": 0,
            "history_budget_projected_top_name": "notification_history.jsonl",
            "history_budget_reports": [
                {
                    "name": "notification_history.jsonl",
                    "byte_margin": 123,
                    "projected_next_byte_ratio": 0.862,
                    "projected_next_status": "NEAR_LIMIT",
                    "estimated_appends_until_line_warn": 10,
                    "estimated_appends_until_byte_warn": 3,
                    "estimated_appends_until_warn": 3,
                },
                {
                    "name": "alert_quality_history.jsonl",
                    "byte_margin": 456,
                    "projected_next_byte_ratio": 0.5,
                    "projected_next_status": "OK",
                    "estimated_appends_until_line_warn": 12,
                    "estimated_appends_until_byte_warn": 99,
                    "estimated_appends_until_warn": 12,
                },
            ],
            "trimmed_histories": [
                {"name": "alert_quality_history.jsonl"},
                {"name": "roxy_realtime_history.jsonl", "min_lines_relaxed": True},
            ],
            "trimmed_history_removed_lines": 6,
            "trimmed_history_removed_bytes": 72_430,
        }
    )

    assert aliases["history_budget_files"] == ["alert_quality_history.jsonl"]
    assert aliases["history_budget_projected_near_count"] == 1
    assert aliases["history_budget_projected_over_count"] == 0
    assert aliases["history_budget_projected_files"] == ["notification_history.jsonl"]
    assert aliases["top_projected_history_budget_file"] == "notification_history.jsonl"
    assert aliases["history_budget_projected_pressure"] == "NEAR_LIMIT"
    assert aliases["history_budget_max_projected_usage_ratio"] == 0.862
    assert aliases["history_budget_min_estimated_appends_until_warn"] == 3
    assert aliases["history_budget_min_estimated_appends_until_warn_name"] == "notification_history.jsonl"
    assert aliases["history_budget_min_estimated_appends_until_line_warn"] == 10
    assert aliases["history_budget_min_estimated_appends_until_byte_warn"] == 3
    assert aliases["current_history_budget_available"] is True
    assert aliases["current_history_budget_report_count"] == 2
    assert aliases["current_history_budget_near_limit_count"] == 0
    assert aliases["current_history_budget_projected_near_limit_count"] == 1
    assert aliases["current_history_budget_status"] == ""
    assert aliases["current_history_budget_pressure"] == ""
    assert aliases["current_history_budget_projected_top_name"] == "notification_history.jsonl"
    assert aliases["current_history_budget_projected_top_status"] == ""
    assert aliases["current_history_budget_min_estimated_appends_until_warn"] == 3
    assert aliases["current_history_budget_min_estimated_appends_until_warn_name"] == "notification_history.jsonl"
    assert aliases["current_history_budget_min_estimated_appends_until_line_warn"] == 10
    assert aliases["current_history_budget_min_estimated_appends_until_byte_warn"] == 3
    assert aliases["trimmed_history_files"] == ["alert_quality_history.jsonl", "roxy_realtime_history.jsonl"]
    assert aliases["trimmed_history_lines"] == 6
    assert aliases["trimmed_history_bytes"] == 72_430
    assert aliases["trimmed_history_min_lines_relaxed_count"] == 1
    assert aliases["trimmed_history_min_lines_relaxed_files"] == ["roxy_realtime_history.jsonl"]
    assert aliases["top_min_lines_relaxed_history_file"] == "roxy_realtime_history.jsonl"
