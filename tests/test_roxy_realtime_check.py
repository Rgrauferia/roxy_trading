import json
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import numpy as np

from tools import roxy_realtime_check
from tools.roxy_realtime_check import (
    BASE_DIR,
    acquire_run_lock,
    alert_quality_report_needs_recovery,
    append_health_history,
    build_operational_summary,
    command_has_flag,
    command_option_int,
    command_has_timeframes,
    evaluate_realtime_health,
    chart_health_report_needs_recovery,
    ensure_core_launchagents,
    ensure_alert_quality_report,
    ensure_ai_brief_report,
    ensure_chart_health_report,
    ensure_live_data_run,
    ensure_output_maintenance_report,
    ensure_runtime_backup_daemon,
    ensure_runtime_backup_report,
    ensure_storage_migration_target,
    ensure_yfinance_cache_recovery,
    heartbeat_check,
    health_history_entry,
    health_notification_message,
    json_safe,
    live_data_recovery_should_wait_for_service,
    live_data_needs_recovery,
    notify_health_if_needed,
    render_text_report,
    read_health_history_entries,
    recover_streamlit_app,
    release_run_lock,
    should_send_health_notification,
    streamlit_app_needs_recovery,
    storage_migration_needs_recovery,
    summarize_health_history_entries,
    output_maintenance_report_needs_recovery,
    runtime_backup_report_needs_recovery,
    validate_daily_service,
    validate_disk_space,
    validate_external_disk,
    validate_health_watchdog_service,
    validate_chart_health_report,
    validate_alert_quality_report,
    validate_app_url,
    validate_live_service,
    validate_notification_delivery,
    validate_output_maintenance_report,
    validate_output_maintenance_service,
    validate_operational_logs,
    validate_runtime_backup_report,
    validate_runtime_backup_service,
    validate_salto_integration,
    validate_storage_migration,
    validate_streamlit_service,
    write_run_lock_status,
    write_report,
    yfinance_cache_needs_recovery,
)


def _touch(path, now):
    ts = now.timestamp()
    os.utime(path, (ts, ts))


def _write_good_artifacts(base_dir, now):
    output = base_dir / "output"
    alerts = base_dir / "alerts"
    db = base_dir / "db"
    data = base_dir / "data"
    output.mkdir()
    alerts.mkdir()
    db.mkdir()
    data.mkdir()
    (db / "roxy.db").write_text("db")
    (data / "state.json").write_text("{}")
    scan = output / "ma_live_strategy_both_20260608_120000.csv"
    pd.DataFrame(
        [
            {"market": "stock", "symbol": "AAPL", "tf": "15m", "signal": "WATCH"},
            {"market": "stock", "symbol": "AAPL", "tf": "1h", "signal": "WATCH"},
            {"market": "stock", "symbol": "AAPL", "tf": "2h", "signal": "WATCH"},
            {"market": "stock", "symbol": "AAPL", "tf": "4h", "signal": "BUY"},
        ]
    ).to_csv(scan, index=False)
    confluence = output / "ma_confluence_20260608_120000.csv"
    pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "AAPL",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 70,
                "higher_tf_bias": "PARTIAL",
                "htf_2h_signal": "WATCH",
                "htf_4h_signal": "BUY",
            }
        ]
    ).to_csv(confluence, index=False)
    options = output / "options_candidates_20260608_120000.csv"
    pd.DataFrame([{"symbol": "AAPL", "option_score": 70}]).to_csv(options, index=False)
    (alerts / "ma_live_heartbeat.json").write_text(
        json.dumps(
            {
                "status": "SUCCESS",
                "duration_seconds": 4.2,
                "scan_path": str(scan),
                "confluence_path": str(confluence),
                "options_path": str(options),
            }
        )
    )
    (alerts / "roxy_ai_brief.json").write_text(
        json.dumps({"source_freshness": {"alerts_allowed": True, "detail": "live/confluencia actualizados hace 2 min."}})
    )
    (alerts / "alert_quality.json").write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "status": "OK",
                "entry": {"state": "WAITING", "notifications_ready": 0, "total_opportunities": 4, "avg_readiness": 62.5},
                "summary": {
                    "state": "WAITING",
                    "latest_notifications_ready": 0,
                    "latest_total_opportunities": 4,
                    "waiting_streak": 2,
                    "avg_readiness": 62.5,
                    "latest_top_blocker": "15m da entrada: WAIT",
                },
            }
        )
    )
    (alerts / "output_maintenance.json").write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "output_dir": str(output),
                "dry_run": False,
                "removed_count": 0,
                "kept_counts": {"ma_live_strategy_*.csv": 1},
            }
        )
    )
    backup = base_dir / "external" / "runtime_backup.tar.gz"
    backup.parent.mkdir()
    import tarfile

    with tarfile.open(backup, "w:gz") as tar:
        tar.add(alerts, arcname="alerts")
        tar.add(base_dir / "db", arcname="db")
        tar.add(base_dir / "data", arcname="data")
    (alerts / "runtime_backup.json").write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "status": "OK",
                "target_dir": str(backup.parent),
                "archive_path": str(backup),
                "archive_exists": True,
                "archive_size_bytes": backup.stat().st_size,
                "include_paths": ["alerts", "db", "data"],
                "dry_run": False,
                "removed_count": 0,
            }
        )
    )
    for path in (
        scan,
        confluence,
        options,
        alerts / "ma_live_heartbeat.json",
        alerts / "roxy_ai_brief.json",
        alerts / "alert_quality.json",
        alerts / "output_maintenance.json",
        alerts / "runtime_backup.json",
    ):
        _touch(path, now)


def test_validate_operational_logs_accepts_missing_logs(tmp_path):
    status = validate_operational_logs([tmp_path / "missing.err"])

    assert status["status"] == "OK"
    assert status["existing_count"] == 0
    assert status["active_count"] == 0


def test_validate_operational_logs_ignores_benign_noise(tmp_path):
    log_path = tmp_path / "streamlit_launchd.err"
    log_path.write_text(
        "\n".join(
            [
                "2026-06-10 Please replace `use_container_width` with `width`.",
                "`use_container_width` will be removed after 2025-12-31.",
                "/tmp/.venv/lib/python3.9/site-packages/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+",
                "  warnings.warn(",
            ]
        )
    )

    status = validate_operational_logs([log_path], now=datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc))

    assert status["status"] == "OK"
    assert status["ignored_line_count"] == 4
    assert status["critical_issues"] == []


def test_validate_operational_logs_fails_on_recent_traceback(tmp_path):
    log_path = tmp_path / "ma_live.err"
    log_path.write_text(
        "\n".join(
            [
                "Traceback (most recent call last):",
                "  File \"tools/ma_live.py\", line 1, in <module>",
                "PermissionError: [Errno 1] Operation not permitted: '/Volumes/RoxyData/project'",
            ]
        )
    )

    status = validate_operational_logs([log_path], now=datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc))

    assert status["status"] == "FAIL"
    assert status["critical_issues"]
    assert any("PermissionError" in item["line"] for item in status["critical_issues"])


def test_validate_operational_logs_ignores_streamlit_websocket_close(tmp_path):
    log_path = tmp_path / "streamlit_launchd.err"
    log_path.write_text(
        "\n".join(
            [
                "2026-06-10 14:47:15,227 ERROR Task exception was never retrieved",
                "future: <Task finished coro=<WebSocketProtocol13.write_message.<locals>.wrapper()>>",
                "Traceback (most recent call last):",
                "  File \"/tmp/.venv/lib/python3.9/site-packages/tornado/websocket.py\", line 1113, in wrapper",
                "    await fut",
                "tornado.iostream.StreamClosedError: Stream is closed",
                "During handling of the above exception, another exception occurred:",
                "Traceback (most recent call last):",
                "  File \"/tmp/.venv/lib/python3.9/site-packages/tornado/websocket.py\", line 1115, in wrapper",
                "    raise WebSocketClosedError()",
                "tornado.websocket.WebSocketClosedError",
            ]
        )
    )

    status = validate_operational_logs([log_path], now=datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc))

    assert status["status"] == "OK"
    assert status["critical_issues"] == []


def test_validate_operational_logs_keeps_typeerror_critical(tmp_path):
    log_path = tmp_path / "streamlit_launchd.err"
    log_path.write_text(
        "\n".join(
            [
                "Traceback (most recent call last):",
                "TypeError: altair_chart() got an unexpected keyword argument 'width'",
            ]
        )
    )

    status = validate_operational_logs([log_path], now=datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc))

    assert status["status"] == "FAIL"
    assert any("TypeError" in item["line"] for item in status["critical_issues"])


def test_validate_operational_logs_ignores_stale_critical_log(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    log_path = tmp_path / "runtime_backup.err"
    log_path.write_text("Traceback (most recent call last):\nPermissionError: stale\n")
    _touch(log_path, now - timedelta(minutes=120))

    status = validate_operational_logs([log_path], max_age_minutes=30, now=now)

    assert status["status"] == "OK"
    assert status["active_count"] == 0


def test_validate_operational_logs_flags_yfinance_cache_issue(tmp_path):
    log_path = tmp_path / "ma_live.err"
    log_path.write_text(
        "\n".join(
            [
                "2026-06-10 15:48:32,111 ERROR",
                "1 Failed download:",
                "2026-06-10 15:48:32,111 ERROR ['SBUX']: OperationalError('unable to open database file')",
            ]
        )
    )

    status = validate_operational_logs([log_path], now=datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc))
    report = {"checks": [status]}

    assert status["status"] == "WARN"
    assert status["yfinance_cache_issue_count"] == 1
    assert yfinance_cache_needs_recovery(report)


def test_validate_operational_logs_ignores_yahoo_provider_noise_without_cache_issue(tmp_path):
    log_path = tmp_path / "streamlit_launchd.err"
    log_path.write_text(
        "\n".join(
            [
                "2026-06-10 15:51:09,932 ERROR Failed to get ticker 'MATIC/USD' reason: Expecting value: line 1 column 1 (char 0)",
                "2026-06-10 15:51:10,512 ERROR HTTP Error 502: <!DOCTYPE html>",
                "2026-06-10 15:52:04,459 ERROR ['MATIC/USD']: RuntimeError('*** YAHOO! FINANCE IS CURRENTLY DOWN! ***')",
                "2026-06-10 15:51:10,977 ERROR",
                "1 Failed download:",
            ]
        )
    )

    status = validate_operational_logs([log_path], now=datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc))

    assert status["status"] == "OK"
    assert status["warning_issues"] == []
    assert status["yfinance_cache_issue_count"] == 0


def test_ensure_yfinance_cache_recovery_creates_cache_dirs_and_rotates_logs(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    cache_a = tmp_path / "home_cache" / "py-yfinance"
    cache_b = tmp_path / "library_cache" / "py-yfinance"
    log_path = tmp_path / "ma_live.err"
    log_path.write_text("ERROR ['SBUX']: OperationalError('unable to open database file')\n")
    report = {"checks": [{"name": "operational_logs", "yfinance_cache_issues": [{"path": str(log_path), "line": log_path.read_text()}]}]}

    result = ensure_yfinance_cache_recovery(
        report,
        cache_paths=(cache_a, cache_b),
        restart_services=False,
        now=now,
    )

    assert result["ok"] is True
    assert cache_a.exists()
    assert cache_b.exists()
    assert result["rotated_logs"]
    assert log_path.exists()
    assert log_path.read_text() == ""


def test_validate_app_url_fails_on_recent_streamlit_traceback(tmp_path, monkeypatch):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    log_path = tmp_path / "streamlit_launchd.err"
    log_path.write_text("Traceback (most recent call last):\nTypeError: altair_chart() got an unexpected keyword argument 'width'\n")
    _touch(log_path, now)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(roxy_realtime_check, "urlopen", lambda *args, **kwargs: Response())

    status = validate_app_url("http://127.0.0.1:8501", log_paths=[log_path], now=now)

    assert status["status"] == "FAIL"
    assert "recent Streamlit log critical" in status["detail"]
    assert status["recent_critical"]


def test_validate_app_url_accepts_http_ok_with_clean_recent_log(tmp_path, monkeypatch):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    log_path = tmp_path / "streamlit_launchd.err"
    log_path.write_text("2026-06-10 12:00:00 app heartbeat ok\n")
    _touch(log_path, now)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(roxy_realtime_check, "urlopen", lambda *args, **kwargs: Response())

    status = validate_app_url("http://127.0.0.1:8501", log_paths=[log_path], now=now)

    assert status["status"] == "OK"
    assert status["recent_log_count"] == 1


def test_evaluate_realtime_health_passes_with_good_artifacts(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    _write_good_artifacts(tmp_path, now - timedelta(minutes=2))

    report = evaluate_realtime_health(base_dir=tmp_path, now=now, skip_chart_fetch=True, skip_service_check=True)

    assert report["status"] == "WARN"
    assert any(item["name"] == "timeframe_coverage" and item["status"] == "OK" for item in report["checks"])
    assert any(item["name"] == "higher_timeframe_confluence" and item["status"] == "OK" for item in report["checks"])
    assert any(item["name"] == "salto_integration" and item["status"] == "OK" for item in report["checks"])
    assert any(item["name"] == "chart_indicators" and item["status"] == "WARN" for item in report["checks"])


def test_evaluate_realtime_health_fails_when_required_timeframe_missing(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    _write_good_artifacts(tmp_path, now - timedelta(minutes=2))
    scan = tmp_path / "output" / "ma_live_strategy_both_20260608_120000.csv"
    df = pd.read_csv(scan)
    df = df[df["tf"] != "4h"]
    df.to_csv(scan, index=False)

    report = evaluate_realtime_health(base_dir=tmp_path, now=now, skip_chart_fetch=True, skip_service_check=True)

    assert report["status"] == "FAIL"
    tf_check = next(item for item in report["checks"] if item["name"] == "timeframe_coverage")
    assert tf_check["missing"] == ["4h"]


def test_evaluate_realtime_health_fails_when_heartbeat_failed(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    _write_good_artifacts(tmp_path, now - timedelta(minutes=2))
    heartbeat = tmp_path / "alerts" / "ma_live_heartbeat.json"
    heartbeat.write_text(json.dumps({"status": "FAILED", "error": "network unavailable"}))

    report = evaluate_realtime_health(base_dir=tmp_path, now=now, skip_chart_fetch=True, skip_service_check=True)

    assert report["status"] == "FAIL"
    assert any(item["name"] == "heartbeat" and item["status"] == "FAIL" for item in report["checks"])


def test_evaluate_realtime_health_uses_latest_files_while_heartbeat_running(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    _write_good_artifacts(tmp_path, now - timedelta(minutes=2))
    heartbeat = tmp_path / "alerts" / "ma_live_heartbeat.json"
    heartbeat.write_text(json.dumps({"status": "RUNNING"}))

    report = evaluate_realtime_health(base_dir=tmp_path, now=now, skip_chart_fetch=True, skip_service_check=True)

    assert report["status"] == "WARN"
    assert any(item["name"] == "heartbeat" and item["status"] == "WARN" for item in report["checks"])
    assert any(item["name"] == "timeframe_coverage" and item["status"] == "OK" for item in report["checks"])


def test_heartbeat_running_is_ok_inside_normal_window(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    heartbeat = {"status": "RUNNING", "started_at": (now - timedelta(minutes=5)).isoformat()}

    status, hb_status = heartbeat_check(tmp_path / "heartbeat.json", heartbeat, now=now, running_warn_minutes=15, running_fail_minutes=30)

    assert hb_status == "RUNNING"
    assert status["status"] == "OK"
    assert status["running_minutes"] == 5.0


def test_heartbeat_running_fails_after_stuck_window(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    heartbeat = {"status": "RUNNING", "started_at": (now - timedelta(minutes=45)).isoformat()}

    status, hb_status = heartbeat_check(tmp_path / "heartbeat.json", heartbeat, now=now, running_warn_minutes=15, running_fail_minutes=30)

    assert hb_status == "RUNNING"
    assert status["status"] == "FAIL"
    assert "likely stuck" in status["detail"]


def test_running_heartbeat_extends_freshness_window(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    _write_good_artifacts(tmp_path, now - timedelta(minutes=13))
    heartbeat = tmp_path / "alerts" / "ma_live_heartbeat.json"
    heartbeat.write_text(json.dumps({"status": "RUNNING", "started_at": (now - timedelta(minutes=5)).isoformat()}))

    report = evaluate_realtime_health(base_dir=tmp_path, now=now, max_age_minutes=10, skip_chart_fetch=True, skip_service_check=True)

    assert any(item["name"] == "heartbeat" and item["status"] == "OK" for item in report["checks"])
    assert any(item["name"] == "live_scan_freshness" and item["status"] == "OK" for item in report["checks"])
    assert any(item["name"] == "confluence_freshness" and item["status"] == "OK" for item in report["checks"])


def test_evaluate_realtime_health_uses_configured_runtime_dirs(tmp_path, monkeypatch):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "custom_output"
    alerts = tmp_path / "custom_alerts"
    output.mkdir()
    alerts.mkdir()
    scan = output / "ma_live_strategy_both_20260608_120000.csv"
    pd.DataFrame(
        [
            {"market": "stock", "symbol": "AAPL", "tf": "15m", "signal": "WATCH"},
            {"market": "stock", "symbol": "AAPL", "tf": "1h", "signal": "WATCH"},
            {"market": "stock", "symbol": "AAPL", "tf": "2h", "signal": "WATCH"},
            {"market": "stock", "symbol": "AAPL", "tf": "4h", "signal": "BUY"},
        ]
    ).to_csv(scan, index=False)
    confluence = output / "ma_confluence_20260608_120000.csv"
    pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "AAPL",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 70,
                "higher_tf_bias": "PARTIAL",
                "htf_2h_signal": "WATCH",
                "htf_4h_signal": "BUY",
            }
        ]
    ).to_csv(confluence, index=False)
    (alerts / "ma_live_heartbeat.json").write_text(json.dumps({"status": "RUNNING"}))
    (alerts / "roxy_ai_brief.json").write_text(json.dumps({"source_freshness": {"alerts_allowed": True}}))
    (alerts / "output_maintenance.json").write_text(
        json.dumps({"generated_at": (now - timedelta(minutes=1)).isoformat(), "output_dir": str(output), "dry_run": False})
    )
    for path in (scan, confluence, alerts / "ma_live_heartbeat.json", alerts / "roxy_ai_brief.json", alerts / "output_maintenance.json"):
        _touch(path, now - timedelta(minutes=1))
    monkeypatch.setattr("tools.roxy_realtime_check.OUTPUT_DIR", output)
    monkeypatch.setattr("tools.roxy_realtime_check.ALERTS_DIR", alerts)

    report = evaluate_realtime_health(base_dir=BASE_DIR, now=now, skip_chart_fetch=True, skip_service_check=True)

    assert report["paths"]["scan"] == str(scan)
    assert report["paths"]["confluence"] == str(confluence)
    assert any(item["name"] == "timeframe_coverage" and item["status"] == "OK" for item in report["checks"])


def test_evaluate_realtime_health_prefers_heartbeat_paths(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    _write_good_artifacts(tmp_path, now - timedelta(minutes=2))
    newer = tmp_path / "output" / "ma_live_strategy_both_20260608_120100.csv"
    pd.DataFrame([{"market": "stock", "symbol": "MSFT", "tf": "15m", "signal": "WATCH"}]).to_csv(newer, index=False)
    _touch(newer, now - timedelta(minutes=1))

    report = evaluate_realtime_health(base_dir=tmp_path, now=now, skip_chart_fetch=True, skip_service_check=True)

    assert report["paths"]["scan"].endswith("ma_live_strategy_both_20260608_120000.csv")
    assert any(item["name"] == "timeframe_coverage" and item["status"] == "OK" for item in report["checks"])


def test_evaluate_realtime_health_accepts_zero_options_summary_without_csv(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    _write_good_artifacts(tmp_path, now - timedelta(minutes=2))
    options = tmp_path / "output" / "options_candidates_20260608_120000.csv"
    options.unlink()
    heartbeat = tmp_path / "alerts" / "ma_live_heartbeat.json"
    payload = json.loads(heartbeat.read_text())
    payload["options_path"] = None
    heartbeat.write_text(json.dumps(payload))
    (tmp_path / "alerts" / "options_summary.json").write_text(json.dumps({"candidate_count": 0}))

    report = evaluate_realtime_health(base_dir=tmp_path, now=now, skip_chart_fetch=True, skip_service_check=True)

    options_check = next(item for item in report["checks"] if item["name"] == "options_candidates")
    assert options_check["status"] == "OK"
    assert options_check["rows"] == 0


def test_write_report_outputs_json_and_text(tmp_path):
    report = {"status": "OK", "generated_at": "2026-06-08T12:00:00+00:00", "checks": [{"name": "x", "status": "OK", "detail": "done"}]}

    json_path, text_path = write_report(report, json_path=tmp_path / "check.json", text_path=tmp_path / "check.txt")

    assert json.loads(json_path.read_text())["status"] == "OK"
    assert "Roxy realtime check: OK" in text_path.read_text()
    assert "OK: x | done" in render_text_report(report)


def test_health_history_entry_counts_statuses_and_top_issue():
    report = {
        "status": "WARN",
        "generated_at": "2026-06-08T12:00:00+00:00",
        "operational_summary": {"mode": "SYSTEM_WARN", "label": "Sistema revisar", "market_state": "UNKNOWN"},
        "checks": [
            {"name": "disk_space", "status": "OK", "detail": "ok"},
            {"name": "heartbeat", "status": "WARN", "detail": "running long"},
            {"name": "streamlit_app", "status": "FAIL", "detail": "timeout"},
        ],
    }

    entry = health_history_entry(report)

    assert entry["status"] == "WARN"
    assert entry["ok"] is False
    assert entry["ok_count"] == 1
    assert entry["warn_count"] == 1
    assert entry["fail_count"] == 1
    assert entry["operational_mode"] == "SYSTEM_WARN"
    assert entry["top_issue"]["name"] == "heartbeat"
    assert entry["checks"]["streamlit_app"] == "FAIL"


def test_build_operational_summary_prioritizes_system_failures():
    summary = build_operational_summary(
        {
            "status": "FAIL",
            "checks": [{"name": "streamlit_app", "status": "FAIL", "detail": "HTTP timeout"}],
        },
        alert_quality_report={"summary": {"state": "READY", "latest_notifications_ready": 2}},
    )

    assert summary["mode"] == "SYSTEM_FAIL"
    assert summary["label"] == "Sistema falla"
    assert summary["tone"] == "avoid"
    assert "streamlit_app" in summary["detail"]


def test_build_operational_summary_distinguishes_market_waiting_from_system_failure():
    summary = build_operational_summary(
        {"status": "OK", "checks": [{"name": "heartbeat", "status": "OK", "detail": "ok"}]},
        alert_quality_report={
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 8,
                "diagnostic_label": "Bloqueador x22",
                "diagnostic_detail": "15m da entrada: WAIT",
                "latest_top_blocker_streak": 22,
            }
        },
    )

    assert summary["mode"] == "MARKET_WAITING"
    assert summary["label"] == "Mercado espera"
    assert summary["tone"] == "watch"
    assert "Bloqueador x22" in summary["detail"]


def test_build_operational_summary_flags_ready_alerts():
    summary = build_operational_summary(
        {"status": "OK", "checks": [{"name": "heartbeat", "status": "OK", "detail": "ok"}]},
        alert_quality_report={"summary": {"state": "READY", "latest_notifications_ready": 2, "latest_total_opportunities": 5}},
    )

    assert summary["mode"] == "READY_TO_REVIEW"
    assert summary["label"] == "Alertas listas"
    assert summary["tone"] == "buy"


def test_append_health_history_trims_to_max_entries(tmp_path):
    history_path = tmp_path / "history.jsonl"

    for idx in range(5):
        append_health_history(
            {"status": "OK", "generated_at": f"2026-06-08T12:0{idx}:00+00:00", "checks": []},
            history_path=history_path,
            max_entries=3,
        )

    lines = history_path.read_text().splitlines()
    payloads = [json.loads(line) for line in lines]
    assert len(lines) == 3
    assert payloads[0]["generated_at"] == "2026-06-08T12:02:00+00:00"
    assert payloads[-1]["generated_at"] == "2026-06-08T12:04:00+00:00"


def test_read_health_history_entries_skips_bad_lines(tmp_path):
    history_path = tmp_path / "history.jsonl"
    history_path.write_text('{"status":"OK"}\nnot-json\n{"status":"WARN"}\n')

    rows = read_health_history_entries(history_path, limit=10)

    assert [row["status"] for row in rows] == ["OK", "WARN"]


def test_run_lock_blocks_overlapping_checks_and_releases(tmp_path):
    lock_path = tmp_path / "roxy.lock"
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)

    first = acquire_run_lock(lock_path, now=now)
    second = acquire_run_lock(lock_path, now=now + timedelta(minutes=1))
    release_run_lock(first)
    third = acquire_run_lock(lock_path, now=now + timedelta(minutes=2))
    release_run_lock(third)

    assert first["acquired"] is True
    assert second["acquired"] is False
    assert second["pid"] == first["pid"]
    assert third["acquired"] is True
    assert not lock_path.exists()


def test_run_lock_replaces_stale_lock(tmp_path):
    lock_path = tmp_path / "roxy.lock"
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)

    first = acquire_run_lock(lock_path, now=now)
    replacement = acquire_run_lock(lock_path, stale_minutes=30, now=now + timedelta(minutes=45))
    release_run_lock(replacement)

    assert first["acquired"] is True
    assert replacement["acquired"] is True
    assert replacement["stale_replaced"] is True
    assert replacement["stale_age_minutes"] == 45.0


def test_write_run_lock_status_records_blocked_and_released(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    status_path = tmp_path / "alerts" / "roxy_realtime_lock.json"
    lock_info = {
        "acquired": False,
        "lock_path": str(tmp_path / "roxy.lock"),
        "pid": 123,
        "started_at": (now - timedelta(minutes=4)).isoformat(),
        "age_minutes": 4.0,
        "stale_minutes": 30.0,
    }

    blocked = write_run_lock_status(lock_info, status_path, event="blocked", now=now)
    released = write_run_lock_status({**lock_info, "acquired": True}, status_path, event="released", now=now + timedelta(minutes=1))
    payload = json.loads(status_path.read_text())

    assert blocked["event"] == "blocked"
    assert blocked["acquired"] is False
    assert released["event"] == "released"
    assert payload["event"] == "released"
    assert payload["released_at"] == (now + timedelta(minutes=1)).isoformat()


def test_summarize_health_history_entries_reports_rates_and_streak():
    rows = [
        {"status": "OK", "generated_at": "2026-06-08T12:00:00+00:00"},
        {"status": "WARN", "generated_at": "2026-06-08T12:05:00+00:00", "top_issue": {"name": "heartbeat"}},
        {"status": "FAIL", "generated_at": "2026-06-08T12:07:00+00:00", "top_issue": {"name": "heartbeat"}},
        {"status": "OK", "generated_at": "2026-06-08T12:10:00+00:00"},
        {"status": "OK", "generated_at": "2026-06-08T12:15:00+00:00"},
    ]

    summary = summarize_health_history_entries(rows)

    assert summary["sample_size"] == 5
    assert summary["ok_rate"] == 0.6
    assert summary["warn_rate"] == 0.2
    assert summary["fail_rate"] == 0.2
    assert summary["current_streak_status"] == "OK"
    assert summary["current_streak_count"] == 2
    assert summary["current_streak_started_at"] == "2026-06-08T12:10:00+00:00"
    assert summary["current_streak_minutes"] == 5.0
    assert summary["incident_free_minutes"] == 8.0
    assert summary["last_incident_at"] == "2026-06-08T12:07:00+00:00"
    assert summary["last_issue"]["name"] == "heartbeat"
    assert summary["dominant_issue"] == {"name": "heartbeat", "count": 2}


def test_render_text_report_includes_stability_summary():
    report = {
        "status": "OK",
        "generated_at": "2026-06-08T12:00:00+00:00",
        "stability_summary": {
            "ok_rate": 0.95,
            "sample_size": 20,
            "current_streak_status": "OK",
            "current_streak_count": 12,
            "incident_free_minutes": 42.5,
            "dominant_issue": {"name": "operational_logs", "count": 3},
        },
        "checks": [],
    }

    text = render_text_report(report)

    assert "Stability: OK 95.0% over 20 checks | streak OK x12 | recovered 42.5m | top issue operational_logs x3" in text


def test_health_notification_message_uses_top_issue_and_recovery():
    warn_report = {
        "status": "WARN",
        "checks": [
            {"name": "disk_space", "status": "OK", "detail": "ok"},
            {"name": "heartbeat", "status": "WARN", "detail": "running long"},
        ],
    }
    ok_report = {"status": "OK", "checks": []}

    assert health_notification_message(warn_report) == "ROXY HEALTH WARN | heartbeat: running long"
    assert health_notification_message(ok_report) == ""
    assert health_notification_message(ok_report, {"last_status": "FAIL"}) == "ROXY HEALTH OK | realtime pipeline recovered"


def test_should_send_health_notification_respects_cooldown():
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    recent = {"last_message": "same", "last_sent_at": (now - timedelta(minutes=10)).isoformat()}
    old = {"last_message": "same", "last_sent_at": (now - timedelta(minutes=40)).isoformat()}

    assert should_send_health_notification(message="", state={}, now=now, cooldown_minutes=30) is False
    assert should_send_health_notification(message="new", state=recent, now=now, cooldown_minutes=30) is True
    assert should_send_health_notification(message="same", state=recent, now=now, cooldown_minutes=30) is False
    assert should_send_health_notification(message="same", state=old, now=now, cooldown_minutes=30) is True


def test_notify_health_if_needed_uses_dedicated_state_and_cooldown(tmp_path, monkeypatch):
    calls = []
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    report = {
        "status": "FAIL",
        "checks": [{"name": "heartbeat", "status": "FAIL", "detail": "network unavailable"}],
    }

    def fake_send(message, *, reason, header):
        calls.append({"message": message, "reason": reason, "header": header})
        return {"sent": True, "reason": reason, "message": message}

    monkeypatch.setattr("notifier.send_notification_message", fake_send)
    state_path = tmp_path / "health_state.json"

    first = notify_health_if_needed(report, state_path=state_path, cooldown_minutes=30, now=now)
    second = notify_health_if_needed(report, state_path=state_path, cooldown_minutes=30, now=now + timedelta(minutes=5))

    assert first["sent"] is True
    assert second["sent"] is False
    assert second["reason"] == "cooldown"
    assert calls == [
        {
            "message": "ROXY HEALTH FAIL | heartbeat: network unavailable",
            "reason": "health_watchdog",
            "header": "ROXY HEALTH",
        }
    ]


def test_notify_health_if_needed_sends_recovery_after_failure(tmp_path, monkeypatch):
    calls = []
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    state_path = tmp_path / "health_state.json"
    state_path.write_text(json.dumps({"last_status": "FAIL", "last_message": "ROXY HEALTH FAIL | heartbeat: failed"}))

    def fake_send(message, *, reason, header):
        calls.append(message)
        return {"sent": True, "reason": reason, "message": message}

    monkeypatch.setattr("notifier.send_notification_message", fake_send)

    result = notify_health_if_needed({"status": "OK", "checks": []}, state_path=state_path, now=now)

    assert result["sent"] is True
    assert calls == ["ROXY HEALTH OK | realtime pipeline recovered"]


def test_notify_health_if_needed_cools_down_recorded_local_attempts(tmp_path, monkeypatch):
    calls = []
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    report = {
        "status": "WARN",
        "checks": [{"name": "notification_delivery", "status": "INFO", "detail": "local only"}],
    }

    def fake_send(message, *, reason, header):
        calls.append({"message": message, "reason": reason, "header": header})
        return {"sent": False, "reason": "recorded_local", "message": message, "channels": []}

    monkeypatch.setattr("notifier.send_notification_message", fake_send)
    state_path = tmp_path / "health_state.json"

    first = notify_health_if_needed(report, state_path=state_path, cooldown_minutes=30, now=now)
    second = notify_health_if_needed(report, state_path=state_path, cooldown_minutes=30, now=now + timedelta(minutes=5))
    saved = json.loads(state_path.read_text())

    assert first["sent"] is False
    assert first["reason"] == "recorded_local"
    assert second["sent"] is False
    assert second["reason"] == "cooldown"
    assert len(calls) == 1
    assert "last_attempt_at" in saved
    assert "last_sent_at" not in saved


def test_validate_salto_integration_is_operational():
    status = validate_salto_integration()

    assert status["status"] == "OK"
    assert status["definitions"] >= 5
    assert status["active_or_watch"] >= 1


def test_command_has_timeframes_checks_required_values():
    command = "tools/ma_live.py --stock-intervals 15m,1h,2h,4h --crypto-timeframes 15m,1h,2h,4h"

    assert command_has_timeframes(command, "--stock-intervals", {"15m", "1h", "2h", "4h"})
    assert not command_has_timeframes(command, "--stock-intervals", {"15m", "1h", "2h", "4h", "1d"})


def test_command_option_int_reads_numeric_option():
    command = "tools/ma_live.py --poll-seconds 300 --retention-count 96"

    assert command_option_int(command, "--retention-count") == 96
    assert command_option_int(command, "--missing") is None


def test_command_has_flag_checks_whole_argument():
    command = "tools/ma_live.py --health-check --retention-count 96"

    assert command_has_flag(command, "--health-check")
    assert not command_has_flag(command, "--health")


def test_validate_live_service_flags_outdated_command(monkeypatch):
    monkeypatch.setattr(
        "tools.ma_live_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": "tools/ma_live.py --stock-intervals 15m,1h --crypto-timeframes 15m,1h",
        },
    )

    status = validate_live_service({"15m", "1h", "2h", "4h"})

    assert status["status"] == "FAIL"
    assert "missing 2h/4h" in status["detail"]


def test_validate_live_service_accepts_full_command(monkeypatch):
    monkeypatch.setattr(
        "tools.ma_live_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": "tools/ma_live.py --stock-intervals 15m,1h,2h,4h --crypto-timeframes 15m,1h,2h,4h --retention-count 96 --health-check",
        },
    )

    status = validate_live_service({"15m", "1h", "2h", "4h"})

    assert status["status"] == "OK"
    assert status["retention_count"] == 96
    assert status["health_check"] is True


def test_validate_live_service_requires_retention(monkeypatch):
    monkeypatch.setattr(
        "tools.ma_live_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": "tools/ma_live.py --stock-intervals 15m,1h,2h,4h --crypto-timeframes 15m,1h,2h,4h",
        },
    )

    status = validate_live_service({"15m", "1h", "2h", "4h"})

    assert status["status"] == "FAIL"
    assert "retention missing" in status["detail"]


def test_validate_live_service_requires_continuous_health_check(monkeypatch):
    monkeypatch.setattr(
        "tools.ma_live_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": "tools/ma_live.py --stock-intervals 15m,1h,2h,4h --crypto-timeframes 15m,1h,2h,4h --retention-count 96",
        },
    )

    status = validate_live_service({"15m", "1h", "2h", "4h"})

    assert status["status"] == "FAIL"
    assert "continuous health check missing" in status["detail"]


def test_validate_streamlit_service_accepts_loaded_keepalive_job(monkeypatch):
    monkeypatch.setattr(
        "tools.streamlit_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "address": "0.0.0.0",
            "port": 8501,
            "command": "python -m streamlit run /tmp/streamlit_app.py --server.port 8501",
        },
    )

    status = validate_streamlit_service()

    assert status["status"] == "OK"
    assert status["keep_alive"] is True
    assert status["port"] == 8501


def test_validate_streamlit_service_flags_unloaded_or_wrong_command(monkeypatch):
    monkeypatch.setattr(
        "tools.streamlit_launchd.status",
        lambda: {
            "installed": True,
            "loaded": False,
            "keep_alive": False,
            "address": "127.0.0.1",
            "port": 8502,
            "command": "python -m streamlit run other.py --server.port 8502",
        },
    )

    status = validate_streamlit_service()

    assert status["status"] == "FAIL"
    assert "not loaded" in status["detail"]
    assert "KeepAlive disabled" in status["detail"]
    assert "streamlit_app.py" in status["detail"]
    assert "port mismatch" in status["detail"]


def test_validate_daily_service_accepts_loaded_daily_job(monkeypatch):
    monkeypatch.setattr(
        "tools.ma_daily_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "command": "python tools/ma_daily.py --market both --retention-count 30",
            "schedule": {"Hour": 18, "Minute": 5},
        },
    )

    status = validate_daily_service()

    assert status["status"] == "OK"
    assert status["retention_count"] == 30


def test_validate_daily_service_requires_schedule_and_retention(monkeypatch):
    monkeypatch.setattr(
        "tools.ma_daily_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "command": "python tools/ma_daily.py --market both",
            "schedule": {},
        },
    )

    status = validate_daily_service()

    assert status["status"] == "FAIL"
    assert "daily schedule missing" in status["detail"]
    assert "retention missing" in status["detail"]


def test_validate_health_watchdog_service_accepts_loaded_periodic_job(monkeypatch):
    command = (
        "python tools/roxy_realtime_check.py --app-url http://127.0.0.1:8501 "
        "--notify-health --ensure-runtime-backup-daemon --ensure-runtime-backup-report "
        "--ensure-core-launchagents --ensure-storage-migration --ensure-live-data --ensure-yfinance-cache --ensure-streamlit-app --ensure-chart-health-report "
        "--ensure-output-maintenance-report --ensure-alert-quality-report --no-fail"
    )
    monkeypatch.setattr(
        "tools.roxy_health_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "command": command,
            "interval_seconds": 300,
            "run_at_load": True,
        },
    )

    status = validate_health_watchdog_service()

    assert status["status"] == "OK"
    assert status["interval_seconds"] == 300
    assert status["missing_flags"] == []


def test_validate_health_watchdog_service_flags_missing_or_slow_job(monkeypatch):
    monkeypatch.setattr(
        "tools.roxy_health_launchd.status",
        lambda: {
            "installed": True,
            "loaded": False,
            "command": "python tools/other.py",
            "interval_seconds": 1200,
            "run_at_load": False,
        },
    )

    status = validate_health_watchdog_service()

    assert status["status"] == "FAIL"
    assert "not loaded" in status["detail"]
    assert "roxy_realtime_check.py" in status["detail"]
    assert "interval too slow" in status["detail"]
    assert "--ensure-runtime-backup-report" in status["detail"]


def test_validate_notification_delivery_accepts_configured_channels(tmp_path, monkeypatch):
    monkeypatch.setattr("notifier.configured_channels", lambda: ["macos", "email"])
    monkeypatch.setattr("notifier.notification_channel_status", lambda: [{"channel": "macos", "configured": True}])

    status = validate_notification_delivery(tmp_path)

    assert status["status"] == "OK"
    assert status["channel_count"] == 2
    assert "macos" in status["detail"]


def test_validate_notification_delivery_accepts_local_file_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr("notifier.configured_channels", lambda: [])
    monkeypatch.setattr("notifier.notification_channel_status", lambda: [])

    status = validate_notification_delivery(tmp_path)

    assert status["status"] == "INFO"
    assert status["channel_count"] == 0
    assert status["local_file_fallback"] is True
    assert status["probe_error"] == ""
    assert "local alert files" in status["detail"]


def test_validate_notification_delivery_fails_without_channels_or_writable_fallback(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    monkeypatch.setattr("notifier.configured_channels", lambda: [])
    monkeypatch.setattr("notifier.notification_channel_status", lambda: [])

    status = validate_notification_delivery(missing)

    assert status["status"] == "FAIL"
    assert "No notification channels" in status["detail"]


def test_validate_output_maintenance_service_accepts_loaded_daily_job(monkeypatch):
    monkeypatch.setattr(
        "tools.output_maintenance_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "command": "python tools/output_maintenance.py",
            "schedule": {"Hour": 3, "Minute": 10},
        },
    )

    status = validate_output_maintenance_service()

    assert status["status"] == "OK"
    assert status["schedule"] == {"Hour": 3, "Minute": 10}


def test_validate_output_maintenance_service_requires_loaded_job(monkeypatch):
    monkeypatch.setattr(
        "tools.output_maintenance_launchd.status",
        lambda: {
            "installed": True,
            "loaded": False,
            "command": "python tools/output_maintenance.py",
            "schedule": {"Hour": 3, "Minute": 10},
        },
    )

    status = validate_output_maintenance_service()

    assert status["status"] == "FAIL"
    assert "not loaded" in status["detail"]


def test_validate_runtime_backup_service_accepts_loaded_daily_job(monkeypatch):
    monkeypatch.setattr(
        "tools.runtime_backup_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "command": "python tools/runtime_backup.py",
            "schedule": {"Hour": 3, "Minute": 25},
        },
    )

    status = validate_runtime_backup_service()

    assert status["status"] == "OK"
    assert status["loaded"] is True


def test_validate_runtime_backup_service_requires_loaded_job(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.roxy_realtime_check.DEFAULT_RUNTIME_BACKUP_DAEMON_HEARTBEAT_PATH", tmp_path / "missing_heartbeat.json")
    monkeypatch.setattr(
        "tools.runtime_backup_launchd.status",
        lambda: {
            "installed": True,
            "loaded": False,
            "command": "python tools/runtime_backup.py",
            "schedule": {"Hour": 3, "Minute": 25},
        },
    )

    status = validate_runtime_backup_service()

    assert status["status"] == "FAIL"
    assert "not loaded" in status["detail"]


def test_validate_runtime_backup_service_accepts_active_daemon_when_launchd_not_loaded(tmp_path, monkeypatch):
    heartbeat = tmp_path / "alerts" / "runtime_backup_daemon_heartbeat.json"
    heartbeat.parent.mkdir()
    heartbeat.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "RUNNING",
                "pid": 12345,
                "last_backup_status": "OK",
            }
        )
    )
    monkeypatch.setattr("tools.roxy_realtime_check.DEFAULT_RUNTIME_BACKUP_DAEMON_HEARTBEAT_PATH", heartbeat)
    monkeypatch.setattr("tools.roxy_realtime_check.pid_is_running", lambda pid: True)
    monkeypatch.setattr(
        "tools.runtime_backup_launchd.status",
        lambda: {
            "installed": True,
            "loaded": False,
            "command": "python tools/runtime_backup.py",
            "schedule": {"Hour": 3, "Minute": 25},
        },
    )

    status = validate_runtime_backup_service()

    assert status["status"] == "OK"
    assert status["daemon_running"] is True
    assert "daemon active" in status["detail"]


def test_ensure_runtime_backup_daemon_delegates_to_screen_controller(monkeypatch):
    called = {}

    def fake_ensure(**kwargs):
        called.update(kwargs)
        return {"action": "healthy"}

    monkeypatch.setattr("tools.runtime_backup_screen.ensure", fake_ensure)

    result = ensure_runtime_backup_daemon(interval_hours=12, poll_seconds=60, stale_minutes=5)

    assert result == {"action": "healthy"}
    assert called == {"interval_hours": 12, "poll_seconds": 60, "stale_minutes": 5}


def test_ensure_core_launchagents_delegates_to_recovery(monkeypatch):
    monkeypatch.setattr("tools.launchd_recovery.ensure_core_launch_agents", lambda: {"status": "OK", "recovered": []})

    result = ensure_core_launchagents()

    assert result == {"status": "OK", "recovered": []}


def test_streamlit_app_needs_recovery_detects_failed_app_check():
    assert streamlit_app_needs_recovery({"checks": [{"name": "streamlit_app", "status": "FAIL"}]}) is True
    assert streamlit_app_needs_recovery({"checks": [{"name": "streamlit_app", "status": "OK"}]}) is False


def test_recover_streamlit_app_restarts_launchagent_without_wait(monkeypatch):
    monkeypatch.setattr(
        "tools.launchd_recovery.restart_launch_agent",
        lambda module_name: {"action": "restart", "ok": True, "module": module_name},
    )

    result = recover_streamlit_app(wait_seconds=0)

    assert result["action"] == "restart"
    assert result["ok"] is True
    assert result["module"] == "tools.streamlit_launchd"
    assert result["app_url"] == "http://127.0.0.1:8501"
    assert result["ready"] in {True, False}


def test_validate_output_maintenance_report_accepts_recent_run(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "output"
    output.mkdir()
    report = tmp_path / "alerts" / "output_maintenance.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "generated_at": (now - timedelta(hours=1)).isoformat(),
                "output_dir": str(output),
                "dry_run": False,
                "removed_count": 3,
                "output_archive_count": 2,
                "output_archive_dir": str(tmp_path / "archive"),
                "stale_output_removed_count": 5,
                "stale_output_removed_counts": {"fine_sweep_*": 5},
                "trimmed_log_count": 2,
                "trimmed_history_count": 1,
                "removed_alert_report_count": 4,
                "kept_counts": {"ma_live_strategy_*.csv": 96},
            }
        )
    )

    status = validate_output_maintenance_report(report, max_age_hours=36, now=now)

    assert status["status"] == "OK"
    assert status["removed_count"] == 3
    assert status["output_archive_count"] == 2
    assert status["output_archive_dir"] == str(tmp_path / "archive")
    assert "archived output 2" in status["detail"]
    assert status["stale_output_removed_count"] == 5
    assert status["stale_output_removed_counts"] == {"fine_sweep_*": 5}
    assert status["trimmed_log_count"] == 2
    assert status["trimmed_history_count"] == 1
    assert status["removed_alert_report_count"] == 4
    assert status["output_exists"] is True


def test_validate_output_maintenance_report_warns_on_dry_run(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "output"
    output.mkdir()
    report = tmp_path / "alerts" / "output_maintenance.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"generated_at": now.isoformat(), "output_dir": str(output), "dry_run": True}))

    status = validate_output_maintenance_report(report, max_age_hours=36, now=now)

    assert status["status"] == "WARN"
    assert "dry-run" in status["detail"]


def test_validate_output_maintenance_report_warns_on_archive_errors(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "output"
    output.mkdir()
    report = tmp_path / "alerts" / "output_maintenance.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "output_dir": str(output),
                "dry_run": False,
                "output_archive_error_count": 1,
            }
        )
    )

    status = validate_output_maintenance_report(report, max_age_hours=36, now=now)

    assert status["status"] == "WARN"
    assert status["output_archive_error_count"] == 1
    assert "archive errors 1" in status["detail"]


def test_validate_output_maintenance_report_fails_when_stale(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    output = tmp_path / "output"
    output.mkdir()
    report = tmp_path / "alerts" / "output_maintenance.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"generated_at": (now - timedelta(hours=80)).isoformat(), "output_dir": str(output), "dry_run": False}))

    status = validate_output_maintenance_report(report, max_age_hours=36, now=now)

    assert status["status"] == "FAIL"
    assert status["age_hours"] == 80.0


def test_output_maintenance_report_needs_recovery_for_warn_or_fail():
    assert output_maintenance_report_needs_recovery({"checks": [{"name": "output_maintenance_report", "status": "WARN"}]})
    assert output_maintenance_report_needs_recovery({"checks": [{"name": "output_maintenance_report", "status": "FAIL"}]})
    assert not output_maintenance_report_needs_recovery({"checks": [{"name": "output_maintenance_report", "status": "OK"}]})


def test_ensure_output_maintenance_report_regenerates_report(tmp_path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    logs = tmp_path / "logs"
    output.mkdir()
    alerts.mkdir()
    logs.mkdir()
    old_path = output / "stocks_tech_20260606_000000.csv"
    new_path = output / "stocks_tech_20260607_000000.csv"
    old_path.write_text("old")
    new_path.write_text("new")
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))
    old_report = alerts / "weekly_report_20260601_090000.txt"
    newer_report = alerts / "weekly_report_20260608_090000.txt"
    old_report.write_text("old")
    newer_report.write_text("new")
    os.utime(old_report, (1, 1))
    os.utime(newer_report, (2, 2))

    result = ensure_output_maintenance_report(
        output_path=output,
        alerts_path=alerts,
        report_path=alerts / "output_maintenance.json",
        text_path=alerts / "output_maintenance.txt",
        log_dirs=[logs],
    )

    assert result["action"] == "regenerated"
    assert result["ok"] is True
    assert result["output_archive_count"] == 0
    assert result["removed_alert_report_count"] == 0
    assert (alerts / "output_maintenance.json").exists()
    assert (alerts / "output_maintenance.txt").exists()
    payload = json.loads((alerts / "output_maintenance.json").read_text())
    assert payload["output_dir"] == str(output)


def test_validate_runtime_backup_report_accepts_recent_archive(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    archive = tmp_path / "external" / "roxy_runtime_20260610_110000.tar.gz"
    archive.parent.mkdir()
    source = tmp_path / "source"
    alerts_source = source / "alerts"
    db_source = source / "db"
    alerts_source.mkdir(parents=True)
    db_source.mkdir()
    (alerts_source / "roxy_realtime_check.json").write_text("{}")
    (db_source / "roxy.db").write_text("db")
    import tarfile

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(alerts_source, arcname="alerts")
        tar.add(db_source, arcname="db")
    report = tmp_path / "alerts" / "runtime_backup.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "generated_at": (now - timedelta(hours=1)).isoformat(),
                "status": "OK",
                "target_dir": str(archive.parent),
                "archive_path": str(archive),
                "archive_exists": True,
                "archive_size_bytes": archive.stat().st_size,
                "include_paths": ["alerts", "db"],
                "dry_run": False,
                "removed_count": 2,
            }
        )
    )

    status = validate_runtime_backup_report(report, now=now)

    assert status["status"] == "OK"
    assert status["archive_exists"] is True
    assert status["archive_size_bytes"] == archive.stat().st_size
    assert status["archive_verified"] is True
    assert status["archive_member_count"] >= 4
    assert status["archive_missing_verified_paths"] == []
    assert status["removed_count"] == 2


def test_validate_runtime_backup_report_fails_unreadable_archive(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    archive = tmp_path / "external" / "roxy_runtime_20260610_110000.tar.gz"
    archive.parent.mkdir()
    archive.write_text("not a tar")
    report = tmp_path / "alerts" / "runtime_backup.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "status": "OK",
                "archive_path": str(archive),
                "archive_exists": True,
                "archive_size_bytes": archive.stat().st_size,
                "include_paths": ["alerts", "db"],
                "dry_run": False,
            }
        )
    )

    status = validate_runtime_backup_report(report, now=now)

    assert status["status"] == "FAIL"
    assert status["archive_exists"] is True
    assert status["archive_readable"] is False
    assert status["archive_verified"] is False
    assert status["archive_missing_verified_paths"] == ["alerts", "db"]
    assert status["archive_verification_error"]


def test_validate_runtime_backup_report_trusts_recent_report_verification_when_reread_is_permission_blocked(
    tmp_path, monkeypatch
):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    archive = tmp_path / "external" / "roxy_runtime_20260610_110000.tar.gz"
    archive.parent.mkdir()
    archive.write_bytes(b"verified archive")
    report = tmp_path / "alerts" / "runtime_backup.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "generated_at": (now - timedelta(minutes=20)).isoformat(),
                "status": "OK",
                "archive_path": str(archive),
                "archive_exists": True,
                "archive_size_bytes": archive.stat().st_size,
                "archive_readable": True,
                "archive_verified": True,
                "archive_member_count": 8,
                "archive_verified_paths": ["alerts", "db", "data"],
                "archive_missing_verified_paths": [],
                "include_paths": ["alerts", "db", "data"],
                "dry_run": False,
            }
        )
    )

    def blocked_open(*args, **kwargs):
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr("tools.roxy_realtime_check.tarfile.open", blocked_open)

    status = validate_runtime_backup_report(report, now=now)

    assert status["status"] == "OK"
    assert status["archive_verified"] is True
    assert status["archive_readable"] is True
    assert status["archive_verification_source"] == "report"
    assert "PermissionError" in status["archive_verification_error"]


def test_validate_runtime_backup_report_fails_missing_archive(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    report = tmp_path / "alerts" / "runtime_backup.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "status": "OK",
                "archive_path": str(tmp_path / "missing.tar.gz"),
                "archive_exists": True,
                "archive_size_bytes": 12,
                "dry_run": False,
            }
        )
    )

    status = validate_runtime_backup_report(report, now=now)

    assert status["status"] == "FAIL"
    assert status["archive_exists"] is False


def test_validate_runtime_backup_report_warns_on_dry_run(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    report = tmp_path / "alerts" / "runtime_backup.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"generated_at": now.isoformat(), "status": "DRY_RUN", "dry_run": True}))

    status = validate_runtime_backup_report(report, now=now)

    assert status["status"] == "WARN"
    assert "dry-run" in status["detail"]


def test_runtime_backup_report_needs_recovery_for_warn_or_fail():
    assert runtime_backup_report_needs_recovery({"checks": [{"name": "runtime_backup_report", "status": "WARN"}]})
    assert runtime_backup_report_needs_recovery({"checks": [{"name": "runtime_backup_report", "status": "FAIL"}]})
    assert not runtime_backup_report_needs_recovery({"checks": [{"name": "runtime_backup_report", "status": "OK"}]})


def test_ensure_runtime_backup_report_creates_archive(tmp_path):
    base = tmp_path / "project"
    alerts = base / "alerts"
    db = base / "db"
    target = tmp_path / "external" / "runtime"
    alerts.mkdir(parents=True)
    db.mkdir()
    (alerts / "roxy_realtime_check.json").write_text("{}")
    (db / "roxy.db").write_text("db")

    result = ensure_runtime_backup_report(
        base_dir=base,
        target_dir=target,
        report_path=alerts / "runtime_backup.json",
        text_path=alerts / "runtime_backup.txt",
    )

    assert result["action"] == "regenerated"
    assert result["ok"] is True
    assert result["archive_exists"] is True
    assert result["archive_size_bytes"] > 0
    assert result["archive_verified"] is True
    assert set(result["archive_verified_paths"]) == {"alerts", "db"}
    assert (alerts / "runtime_backup.json").exists()
    assert (alerts / "runtime_backup.txt").exists()


def test_validate_disk_space_warns_when_threshold_is_above_free_space(tmp_path):
    status = validate_disk_space(tmp_path, warn_free_gb=10_000, fail_free_gb=0)

    assert status["status"] == "WARN"
    assert status["free_gb"] >= 0


def test_validate_external_disk_accepts_writable_mounted_path(tmp_path):
    status = validate_external_disk(tmp_path, warn_free_gb=0, fail_free_gb=0)

    assert status["status"] == "OK"
    assert status["mounted"] is True
    assert status["writable"] is True


def test_validate_external_disk_fails_missing_mount(tmp_path):
    status = validate_external_disk(tmp_path / "missing")

    assert status["status"] == "FAIL"
    assert status["mounted"] is False


def test_validate_external_disk_accepts_recent_operational_backup_when_probe_denied(tmp_path, monkeypatch):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    archive = tmp_path / "projects" / "roxy_trading" / "_backup" / "runtime" / "roxy_runtime_20260610_120000.tar.gz"
    archive.parent.mkdir(parents=True)
    archive.write_text("backup")
    report = tmp_path / "alerts" / "runtime_backup.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "status": "OK",
                "archive_path": str(archive),
                "archive_size_bytes": archive.stat().st_size,
            }
        )
    )
    original_write_text = type(tmp_path).write_text

    def deny_probe(self, *args, **kwargs):
        if self.name.startswith(".roxy_write_test_"):
            raise PermissionError("denied")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "write_text", deny_probe)

    status = validate_external_disk(tmp_path, warn_free_gb=0, fail_free_gb=0, operational_report_path=report, now=now)

    assert status["status"] == "OK"
    assert status["writable"] is False
    assert status["operational_write_verified"] is True


def test_evaluate_realtime_health_can_check_configured_external_disk(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    _write_good_artifacts(tmp_path, now)

    report = evaluate_realtime_health(
        base_dir=tmp_path,
        now=now,
        skip_chart_fetch=True,
        skip_service_check=True,
        external_disk_path=tmp_path,
        external_warn_free_gb=0,
        external_fail_free_gb=0,
        storage_migration_source_path=tmp_path / "home" / "Parallels",
        storage_migration_destination_path=tmp_path / "MacArchive" / "robertograu" / "Parallels",
        storage_migration_log_path=tmp_path / "MacArchive" / "migration_logs" / "parallels_migration.log",
    )

    external = next(item for item in report["checks"] if item["name"] == "external_disk")
    migration = next(item for item in report["checks"] if item["name"] == "storage_migration")
    assert external["status"] == "OK"
    assert migration["status"] == "OK"
    assert migration["state"] == "NOT_PRESENT"


def test_validate_storage_migration_waits_when_parallels_is_still_local(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    external = tmp_path / "RoxyData"
    source = tmp_path / "home" / "Parallels"
    destination = external / "MacArchive" / "robertograu" / "Parallels"
    log = external / "MacArchive" / "migration_logs" / "parallels_migration.log"
    source.mkdir(parents=True)
    external.mkdir(parents=True)
    log.parent.mkdir(parents=True)
    (source / "Windows.pvm").write_text("vm")
    log.write_text("2026-06-10T12:00:00Z Parallels sigue corriendo. Esperando 60s antes de reintentar.")
    _touch(log, now)

    status = validate_storage_migration(
        source_path=source,
        destination_path=destination,
        log_path=log,
        external_disk_path=external,
        now=now,
    )

    assert status["status"] == "INFO"
    assert status["state"] == "WAITING_FOR_PARALLELS"
    assert status["waiting_for_parallels"] is True
    assert status["source_size_bytes"] == 2


def test_validate_storage_migration_accepts_completed_symlink(tmp_path):
    external = tmp_path / "RoxyData"
    destination = external / "MacArchive" / "robertograu" / "Parallels"
    source = tmp_path / "home" / "Parallels"
    destination.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    (destination / "Windows.pvm").write_text("vm")
    source.symlink_to(destination, target_is_directory=True)

    status = validate_storage_migration(
        source_path=source,
        destination_path=destination,
        log_path=external / "MacArchive" / "migration_logs" / "parallels_migration.log",
        external_disk_path=external,
    )

    assert status["status"] == "OK"
    assert status["state"] == "MIGRATED"
    assert status["source_is_symlink"] is True


def test_validate_storage_migration_warns_on_broken_external_symlink(tmp_path):
    external = tmp_path / "RoxyData"
    destination = external / "MacArchive" / "robertograu" / "Parallels"
    source = tmp_path / "home" / "Parallels"
    external.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    source.symlink_to(destination, target_is_directory=True)

    status = validate_storage_migration(
        source_path=source,
        destination_path=destination,
        log_path=external / "MacArchive" / "migration_logs" / "parallels_migration.log",
        external_disk_path=external,
    )
    report = {"checks": [status]}

    assert status["status"] == "WARN"
    assert status["state"] == "BROKEN_SYMLINK"
    assert status["source_broken_symlink"] is True
    assert storage_migration_needs_recovery(report)


def test_ensure_storage_migration_target_repairs_broken_external_symlink(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    external = tmp_path / "RoxyData"
    destination = external / "MacArchive" / "robertograu" / "Parallels"
    source = tmp_path / "home" / "Parallels"
    log = external / "MacArchive" / "migration_logs" / "parallels_migration.log"
    external.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    source.symlink_to(destination, target_is_directory=True)

    result = ensure_storage_migration_target(
        source_path=source,
        destination_path=destination,
        external_disk_path=external,
        log_path=log,
        now=now,
    )

    assert result["action"] == "created_missing_destination"
    assert result["ok"] is True
    assert destination.exists()
    assert result["after"]["state"] == "MIGRATED"
    assert "Recreated missing Parallels destination" in log.read_text()


def test_validate_chart_health_report_accepts_recent_ok_report(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    report = tmp_path / "chart_realtime_health.json"
    report.write_text(
        json.dumps(
            {
                "generated_at": (now - timedelta(minutes=5)).isoformat(),
                "summary": {
                    "status": "OK",
                    "checked_count": 4,
                    "fail_count": 0,
                    "warn_count": 0,
                    "max_age_minutes": 24.5,
                    "avg_age_minutes": 10.0,
                    "stalest_chart": {"symbol": "AAPL", "timeframe": "1h"},
                },
            }
        )
    )

    status = validate_chart_health_report(report, now=now)

    assert status["status"] == "OK"
    assert status["checked_count"] == 4
    assert status["max_chart_age_minutes"] == 24.5
    assert status["avg_chart_age_minutes"] == 10.0
    assert status["stalest_chart"] == {"symbol": "AAPL", "timeframe": "1h"}
    assert "max chart age 24.5m" in status["detail"]
    assert "stalest AAPL 1h" in status["detail"]


def test_validate_chart_health_report_fails_stale_report(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    report = tmp_path / "chart_realtime_health.json"
    report.write_text(
        json.dumps(
            {
                "generated_at": (now - timedelta(hours=3)).isoformat(),
                "summary": {"status": "OK", "checked_count": 4, "fail_count": 0, "warn_count": 0},
            }
        )
    )

    status = validate_chart_health_report(report, max_age_minutes=30, now=now)

    assert status["status"] == "FAIL"


def test_chart_health_report_needs_recovery_for_warn_or_fail():
    assert chart_health_report_needs_recovery({"checks": [{"name": "chart_realtime_health_report", "status": "WARN"}]})
    assert chart_health_report_needs_recovery({"checks": [{"name": "chart_realtime_health_report", "status": "FAIL"}]})
    assert not chart_health_report_needs_recovery({"checks": [{"name": "chart_realtime_health_report", "status": "OK"}]})


def test_ensure_chart_health_report_regenerates_report(tmp_path, monkeypatch):
    report_path = tmp_path / "chart_realtime_health.json"

    def fake_collect_chart_health(*, symbols, timeframes, now=None):
        return [
            {
                "symbol": symbols[0],
                "market": "stock",
                "timeframe": timeframes[0],
                "status": "OK",
                "label": "Live",
                "tone": "buy",
                "detail": "fresh",
                "rows": 200,
                "has_rsi": True,
                "has_macd": True,
                "indicator_status": "OK",
            }
        ]

    monkeypatch.setattr("tools.chart_realtime_health.collect_chart_health", fake_collect_chart_health)

    result = ensure_chart_health_report(report_path=report_path, symbols=["AAPL"], timeframes=["1h"])

    assert result["action"] == "regenerated"
    assert result["status"] == "OK"
    assert result["checked_count"] == 1
    assert report_path.exists()
    payload = json.loads(report_path.read_text())
    assert payload["summary"]["status"] == "OK"


def test_validate_alert_quality_report_accepts_recent_waiting_state(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    report = tmp_path / "alert_quality.json"
    report.write_text(
        json.dumps(
            {
                "generated_at": (now - timedelta(minutes=5)).isoformat(),
                "brief_generated_at": (now - timedelta(minutes=6)).isoformat(),
                "status": "OK",
                "entry": {"state": "WAITING", "notifications_ready": 0, "total_opportunities": 8},
                "summary": {
                    "state": "WAITING",
                    "latest_notifications_ready": 0,
                    "latest_total_opportunities": 8,
                    "waiting_streak": 3,
                    "latest_top_blocker_streak": 3,
                    "persistent_blocker_minutes": 12.5,
                    "avg_readiness": 61.3,
                    "readiness_delta": -4.2,
                    "dominant_blocker": {"name": "15m da entrada: WAIT", "count": 3},
                    "latest_top_blocker": "15m da entrada: WAIT",
                },
            }
        )
    )

    status = validate_alert_quality_report(report, now=now)

    assert status["status"] == "OK"
    assert status["state"] == "WAITING"
    assert status["waiting_streak"] == 3
    assert status["latest_top_blocker_streak"] == 3
    assert status["persistent_blocker_minutes"] == 12.5
    assert status["readiness_delta"] == -4.2
    assert status["dominant_blocker"] == {"name": "15m da entrada: WAIT", "count": 3}
    assert status["brief_age_minutes"] == 6.0
    assert "persistent 12.5m" in status["detail"]
    assert "readiness trend -4.2" in status["detail"]
    assert "recurrent blocker 15m da entrada: WAIT x3" in status["detail"]
    assert "ready 0/8" in status["detail"]


def test_validate_alert_quality_report_fails_when_brief_is_stale(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    report = tmp_path / "alert_quality.json"
    report.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "brief_generated_at": (now - timedelta(hours=4)).isoformat(),
                "status": "OK",
                "entry": {"state": "WAITING", "notifications_ready": 0, "total_opportunities": 8},
            }
        )
    )

    status = validate_alert_quality_report(report, max_age_minutes=30, now=now)

    assert status["status"] == "FAIL"
    assert status["brief_age_minutes"] == 240.0
    assert "brief age 240m" in status["detail"]


def test_validate_alert_quality_report_fails_when_stale(tmp_path):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    report = tmp_path / "alert_quality.json"
    report.write_text(json.dumps({"generated_at": (now - timedelta(hours=4)).isoformat(), "status": "OK"}))

    status = validate_alert_quality_report(report, max_age_minutes=30, now=now)

    assert status["status"] == "FAIL"


def test_alert_quality_report_needs_recovery_for_warn_or_fail():
    assert alert_quality_report_needs_recovery({"checks": [{"name": "alert_quality_report", "status": "WARN"}]})
    assert alert_quality_report_needs_recovery({"checks": [{"name": "alert_quality_report", "status": "FAIL"}]})
    assert not alert_quality_report_needs_recovery({"checks": [{"name": "alert_quality_report", "status": "OK"}]})


def test_live_data_needs_recovery_for_stale_or_failed_core_checks():
    assert live_data_needs_recovery({"checks": [{"name": "live_scan_freshness", "status": "WARN"}]})
    assert live_data_needs_recovery({"checks": [{"name": "heartbeat", "status": "FAIL"}]})
    assert not live_data_needs_recovery(
        {
            "checks": [
                {"name": "heartbeat", "status": "OK"},
                {"name": "live_scan_freshness", "status": "OK"},
                {"name": "confluence_freshness", "status": "OK"},
                {"name": "notification_delivery", "status": "INFO"},
            ]
        }
    )


def test_live_data_recovery_should_wait_when_live_service_is_running_normally():
    report = {
        "checks": [
            {"name": "live_service_24h", "status": "OK"},
            {"name": "heartbeat", "status": "OK", "detail": "Live backend running normally for 4 min"},
            {"name": "live_scan_freshness", "status": "WARN", "detail": "scan age 11 min"},
        ]
    }

    assert live_data_needs_recovery(report)
    assert live_data_recovery_should_wait_for_service(report)


def test_live_data_recovery_does_not_wait_when_heartbeat_failed():
    report = {
        "checks": [
            {"name": "live_service_24h", "status": "OK"},
            {"name": "heartbeat", "status": "FAIL", "detail": "Live backend failed"},
            {"name": "live_scan_freshness", "status": "FAIL", "detail": "scan missing"},
        ]
    }

    assert live_data_needs_recovery(report)
    assert not live_data_recovery_should_wait_for_service(report)


def test_ensure_live_data_run_invokes_ma_live_once(tmp_path, monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = "line\nSaved: /tmp/scan.csv\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, **kwargs})
        return Result()

    monkeypatch.setattr(roxy_realtime_check.subprocess, "run", fake_run)

    result = ensure_live_data_run(
        base_dir=tmp_path,
        timeout_seconds=120,
        stock_intervals="15m,1h,2h,4h",
        crypto_timeframes="15m,1h,2h,4h",
        retention_count=96,
    )

    assert result["action"] == "ran_live_scan"
    assert result["ok"] is True
    assert calls
    command = " ".join(calls[0]["cmd"])
    assert "tools/ma_live.py" in command
    assert "--once" in command
    assert "--stock-intervals 15m,1h,2h,4h" in command
    assert "--crypto-timeframes 15m,1h,2h,4h" in command
    assert "--retention-count 96" in command
    assert calls[0]["timeout"] == 120


def test_ensure_alert_quality_report_regenerates_report(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    brief = alerts / "roxy_ai_brief.json"
    report = alerts / "alert_quality.json"
    history = alerts / "alert_quality_history.jsonl"
    brief.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-10T12:00:00+00:00",
                "alert_gate_summary": {
                    "total_opportunities": 2,
                    "notifications_ready": 0,
                    "avg_readiness": 61.3,
                    "top_gate_label": "Esperar entrada 15m",
                    "top_blocker": "15m da entrada: WAIT",
                },
            }
        )
    )

    result = ensure_alert_quality_report(brief_path=brief, report_path=report, history_path=history)

    assert result["action"] == "regenerated"
    assert result["ok"] is True
    assert result["state"] == "WAITING"
    assert report.exists()
    assert history.exists()
    payload = json.loads(report.read_text())
    assert payload["summary"]["latest_top_blocker"] == "15m da entrada: WAIT"


def test_ensure_ai_brief_report_runs_watch_builder(tmp_path, monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = "Roxy AI alerts: 0 | watch: 8\n"
        stderr = ""

    def fake_run(cmd, cwd, text, capture_output, timeout):
        calls.append(
            {
                "cmd": cmd,
                "cwd": cwd,
                "text": text,
                "capture_output": capture_output,
                "timeout": timeout,
            }
        )
        return Result()

    monkeypatch.setattr(roxy_realtime_check.subprocess, "run", fake_run)

    result = ensure_ai_brief_report(base_dir=tmp_path, timeout_seconds=77)

    assert result["action"] == "regenerated"
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert "roxy_ai_watch.py" in " ".join(calls[0]["cmd"])
    assert calls[0]["cwd"] == str(tmp_path)
    assert calls[0]["timeout"] == 77
    assert "Roxy AI alerts" in result["output_tail"]


def test_json_safe_converts_numpy_scalars():
    payload = json_safe({"ok": np.bool_(True), "rows": np.int64(3), "score": np.float64(1.5)})

    assert payload == {"ok": True, "rows": 3, "score": 1.5}
