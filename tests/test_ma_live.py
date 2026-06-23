from argparse import Namespace
import json
import os
import subprocess

from tools import ma_live
from tools.ma_live import (
    build_ai_watch_command,
    build_confluence_command,
    build_health_check_command,
    build_report_command,
    build_scan_command,
    cleanup_live_outputs,
    effective_scan_market,
    extract_saved_scan_path,
    run_once,
    write_heartbeat,
)


def test_build_scan_command_uses_intraday_timeframes_and_extended_hours():
    args = Namespace(
        market="both",
        stock_intervals="15m,1h",
        stock_period="60d",
        intraday_stock_period="60d",
        crypto_timeframes="15m,1h",
        crypto_limit=500,
        trigger_tf="15m",
        trend_tf="1h",
        limit=30,
        report_limit=12,
        symbols=None,
    )

    cmd = build_scan_command(args, "/tmp/python")

    assert cmd[0] == "/tmp/python"
    assert cmd[1].endswith("tools/ma_scan.py")
    assert "--stock-intervals" in cmd
    assert "15m,1h" in cmd
    assert "--crypto-timeframes" in cmd
    assert "--include-extended-hours" in cmd
    assert "--output-prefix" in cmd
    assert "ma_live_strategy" in cmd
    assert "--timing-json" in cmd
    assert "alerts/ma_live_scan_timing.json" in " ".join(cmd)


def test_effective_scan_market_routes_both_to_crypto_when_stocks_are_blocked(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "roxy_status.json").write_text(
        json.dumps(
            {
                "safe_mode": "NO_STOCK_OR_OPTIONS_ALERTS",
                "allowed_markets": ["crypto"],
                "blocked_markets": ["stock", "options"],
                "active_route_label": "Operar solo CRYPTO",
            }
        )
    )
    args = Namespace(market="both", symbols=None)

    market, reason = effective_scan_market(args, alerts)

    assert market == "crypto"
    assert "stock/options blocked" in reason


def test_effective_scan_market_keeps_targeted_symbols_even_when_stocks_are_blocked(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "roxy_status.json").write_text(
        json.dumps(
            {
                "safe_mode": "NO_STOCK_OR_OPTIONS_ALERTS",
                "allowed_markets": ["crypto"],
                "blocked_markets": ["stock", "options"],
            }
        )
    )
    args = Namespace(market="both", symbols="AAPL")

    market, reason = effective_scan_market(args, alerts)

    assert market == "both"
    assert reason == ""


def test_effective_scan_market_uses_provider_block_when_status_snapshot_is_dirty(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "roxy_status.json").write_text(
        json.dumps(
            {
                "safe_mode": "NO_ALERTS_UNTIL_DATA_OK",
                "allowed_markets": [],
                "blocked_markets": [],
            }
        )
    )
    (alerts / "roxy_realtime_check.json").write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "name": "chart_provider_effective",
                        "status": "WARN",
                        "detail": "issue AAPL 1h alpaca_auth, alternate polygon_not_configured",
                    }
                ]
            }
        )
    )
    args = Namespace(market="both", symbols=None)

    market, reason = effective_scan_market(args, alerts)

    assert market == "crypto"
    assert "premium stock provider blocked" in reason


def test_effective_scan_market_routes_partial_crypto_route_even_when_waiting(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "roxy_status.json").write_text(
        json.dumps(
            {
                "safe_mode": "WAIT_FOR_CONFIRMATION",
                "allowed_markets": ["crypto"],
                "blocked_markets": ["stock", "options"],
                "active_route_label": "Operar solo CRYPTO",
            }
        )
    )
    args = Namespace(market="both", symbols=None)

    market, reason = effective_scan_market(args, alerts)

    assert market == "crypto"
    assert "stock/options blocked" in reason


def test_build_scan_command_can_override_effective_market():
    args = Namespace(
        market="both",
        stock_intervals="15m,1h",
        stock_period="60d",
        intraday_stock_period="60d",
        crypto_timeframes="15m,1h",
        crypto_limit=500,
        trigger_tf="15m",
        trend_tf="1h",
        limit=30,
        report_limit=12,
        symbols=None,
    )

    cmd = build_scan_command(args, "/tmp/python", market="crypto")

    assert cmd[cmd.index("--market") + 1] == "crypto"


def test_build_report_command_writes_live_report_paths():
    args = Namespace(report_limit=12)

    cmd = build_report_command(args, "/tmp/python", "/tmp/scan.csv")

    assert "--scan-csv" in cmd
    assert "/tmp/scan.csv" in cmd
    assert "alerts/ma_live_report.txt" in " ".join(cmd)
    assert "alerts/ma_live_summary.json" in " ".join(cmd)


def test_build_confluence_command_writes_specialized_report_paths():
    args = Namespace(report_limit=12, trigger_tf="15m", trend_tf="1h")

    cmd = build_confluence_command(args, "/tmp/python", "/tmp/scan.csv")

    assert "--scan-csv" in cmd
    assert "/tmp/scan.csv" in cmd
    assert "--trigger-tf" in cmd
    assert "15m" in cmd
    assert "--trend-tf" in cmd
    assert "1h" in cmd
    assert "alerts/ma_confluence_report.txt" in " ".join(cmd)
    assert "alerts/ma_confluence_summary.json" in " ".join(cmd)


def test_extract_saved_scan_path():
    output = "x\nSaved: /tmp/output.csv\n"

    assert extract_saved_scan_path(output) == "/tmp/output.csv"


def test_build_ai_watch_command_writes_brief_and_notifications():
    args = Namespace(notify=True)

    cmd = build_ai_watch_command(args, "/tmp/python", "/tmp/scan.csv", "/tmp/confluence.csv", "/tmp/options.csv")

    joined = " ".join(cmd)
    assert cmd[0] == "/tmp/python"
    assert "tools/roxy_ai_watch.py" in joined
    assert "--scan-csv /tmp/scan.csv" in joined
    assert "--confluence-csv /tmp/confluence.csv" in joined
    assert "--options-csv /tmp/options.csv" in joined
    assert "--notify" in cmd


def test_build_health_check_command_writes_realtime_report():
    args = Namespace(
        health_app_url="http://127.0.0.1:3000",
        health_chart_symbol="AAPL",
        health_chart_timeframe="1h",
        health_skip_chart_fetch=False,
    )

    cmd = build_health_check_command(args, "/tmp/python")
    joined = " ".join(cmd)

    assert cmd[0] == "/tmp/python"
    assert "tools/roxy_realtime_check.py" in joined
    assert "--no-fail" in cmd
    assert "--app-url http://127.0.0.1:3000" in joined
    assert "--chart-symbol AAPL" in joined
    assert "--ensure-dashboard-render-probe-report" in cmd
    assert "--ensure-chart-health-report" in cmd
    assert "--ensure-alert-quality-report" in cmd
    assert "--ensure-daily-opportunity-plan-report" in cmd
    assert "--ensure-status-snapshot-report" in cmd


def test_cleanup_live_outputs_keeps_recent_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ma_live, "OUTPUT_DIR", tmp_path)
    old_files = []
    new_files = []
    for prefix in ("ma_live_strategy_both", "ma_confluence", "options_candidates"):
        old_path = tmp_path / f"{prefix}_20260606_000000.csv"
        new_path = tmp_path / f"{prefix}_20260607_000000.csv"
        old_path.write_text("old")
        new_path.write_text("new")
        os.utime(old_path, (1, 1))
        os.utime(new_path, (2, 2))
        old_files.append(old_path)
        new_files.append(new_path)

    removed = cleanup_live_outputs(1)

    assert len(removed) == 3
    assert all(not path.exists() for path in old_files)
    assert all(path.exists() for path in new_files)


def test_write_heartbeat_round_trips_json(tmp_path):
    path = tmp_path / "ma_live_heartbeat.json"

    written = write_heartbeat({"status": "SUCCESS", "duration_seconds": 1.2}, path)

    assert written == path
    assert json.loads(path.read_text())["status"] == "SUCCESS"
    assert not path.with_suffix(".json.tmp").exists()


def test_run_once_writes_success_heartbeat(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "heartbeat.json"
    lock_path = tmp_path / "ma_live.lock"
    monkeypatch.setattr(ma_live, "HEARTBEAT_PATH", heartbeat_path)
    monkeypatch.setattr(ma_live, "LOCK_PATH", lock_path)
    monkeypatch.setattr(ma_live, "cleanup_live_outputs", lambda retention_count: [])

    outputs = {
        "ma_scan.py": "Saved: /tmp/scan.csv\n",
        "ma_confluence.py": "Saved: /tmp/confluence.csv\n",
        "options_scan.py": "Saved: /tmp/options.csv\n",
    }
    commands: list[str] = []

    health_saw_final_heartbeat = False

    def fake_run_command(cmd):
        nonlocal health_saw_final_heartbeat
        joined = " ".join(cmd)
        commands.append(joined)
        if "roxy_realtime_check.py" in joined:
            health_saw_final_heartbeat = json.loads(heartbeat_path.read_text())["status"] == "SUCCESS"
        stdout = ""
        for name, output in outputs.items():
            if name in joined:
                stdout = output
                break
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(ma_live, "run_command", fake_run_command)
    args = Namespace(
        market="stocks",
        symbols="AAPL",
        stock_intervals="15m,1h,2h,4h",
        stock_period="60d",
        intraday_stock_period="60d",
        crypto_timeframes="15m,1h,2h,4h",
        crypto_limit=500,
        trigger_tf="15m",
        trend_tf="1h",
        limit=5,
        report_limit=3,
        skip_ai_watch=False,
        notify=False,
        retention_count=10,
        health_check=True,
        health_app_url="",
        health_chart_symbol="AAPL",
        health_chart_timeframe="1h",
        health_skip_chart_fetch=True,
    )

    scan_path = run_once(args)
    heartbeat = json.loads(heartbeat_path.read_text())

    assert scan_path == "/tmp/scan.csv"
    assert heartbeat["status"] == "SUCCESS"
    assert heartbeat["scan_path"] == "/tmp/scan.csv"
    assert heartbeat["confluence_path"] == "/tmp/confluence.csv"
    assert heartbeat["options_path"] == "/tmp/options.csv"
    assert heartbeat["ai_watch_ran"] is True
    assert heartbeat["duration_seconds"] >= 0
    assert heartbeat["current_step"] is None
    assert [step["name"] for step in heartbeat["steps"]] == [
        "scan",
        "report",
        "confluence",
        "options",
        "ai_watch",
        "cleanup",
    ]
    assert all(step["status"] == "SUCCESS" for step in heartbeat["steps"])
    assert all(step["duration_seconds"] >= 0 for step in heartbeat["steps"])
    assert heartbeat["steps"][-1]["removed_old_files"] == 0
    assert any("roxy_ai_watch.py" in command for command in commands)
    assert any("roxy_realtime_check.py" in command for command in commands)
    assert health_saw_final_heartbeat is True
    assert not lock_path.exists()


def test_run_once_uses_adaptive_effective_market(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "heartbeat.json"
    lock_path = tmp_path / "ma_live.lock"
    monkeypatch.setattr(ma_live, "HEARTBEAT_PATH", heartbeat_path)
    monkeypatch.setattr(ma_live, "LOCK_PATH", lock_path)
    monkeypatch.setattr(ma_live, "cleanup_live_outputs", lambda retention_count: [])
    monkeypatch.setattr(
        ma_live,
        "effective_scan_market",
        lambda args: ("crypto", "stock/options blocked by provider premium; scanning crypto only"),
    )

    commands: list[str] = []

    def fake_run_command(cmd):
        joined = " ".join(cmd)
        commands.append(joined)
        if "ma_scan.py" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="Saved: /tmp/crypto_scan.csv\n", stderr="")
        if "ma_confluence.py" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="Saved: /tmp/confluence.csv\n", stderr="")
        if "options_scan.py" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="Saved: /tmp/options.csv\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(ma_live, "run_command", fake_run_command)
    args = Namespace(
        market="both",
        symbols=None,
        stock_intervals="15m,1h,2h,4h",
        stock_period="60d",
        intraday_stock_period="60d",
        crypto_timeframes="15m,1h,2h,4h",
        crypto_limit=500,
        trigger_tf="15m",
        trend_tf="1h",
        limit=5,
        report_limit=3,
        skip_ai_watch=True,
        notify=False,
        retention_count=10,
        health_check=False,
    )

    scan_path = run_once(args)
    heartbeat = json.loads(heartbeat_path.read_text())
    scan_command = next(command for command in commands if "ma_scan.py" in command)

    assert scan_path == "/tmp/crypto_scan.csv"
    assert heartbeat["requested_market"] == "both"
    assert heartbeat["effective_market"] == "crypto"
    assert "stock/options blocked" in heartbeat["adaptive_market_reason"]
    assert "--market crypto" in scan_command
    assert not lock_path.exists()


def test_run_once_writes_failed_heartbeat(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "heartbeat.json"
    lock_path = tmp_path / "ma_live.lock"
    monkeypatch.setattr(ma_live, "HEARTBEAT_PATH", heartbeat_path)
    monkeypatch.setattr(ma_live, "LOCK_PATH", lock_path)

    def fake_run_command(cmd):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(ma_live, "run_command", fake_run_command)
    args = Namespace(
        market="stocks",
        symbols="AAPL",
        stock_intervals="15m,1h,2h,4h",
        stock_period="60d",
        intraday_stock_period="60d",
        crypto_timeframes="15m,1h,2h,4h",
        crypto_limit=500,
        trigger_tf="15m",
        trend_tf="1h",
        limit=5,
        report_limit=3,
        skip_ai_watch=True,
        notify=False,
        retention_count=10,
    )

    try:
        run_once(args)
    except RuntimeError:
        pass
    else:
        raise AssertionError("run_once should re-raise command failures")

    heartbeat = json.loads(heartbeat_path.read_text())
    assert heartbeat["status"] == "FAILED"
    assert heartbeat["error"] == "network unavailable"
    assert heartbeat["finished_at"]
    assert heartbeat["duration_seconds"] >= 0
    assert heartbeat["current_step"] is None
    assert heartbeat["steps"][0]["name"] == "scan"
    assert heartbeat["steps"][0]["status"] == "FAILED"
    assert heartbeat["steps"][0]["error"] == "network unavailable"
    assert not lock_path.exists()


def test_run_once_skips_when_active_lock_exists(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "heartbeat.json"
    lock_path = tmp_path / "ma_live.lock"
    lock_path.write_text(json.dumps({"pid": 999, "started_epoch": ma_live.time.time(), "started_at": "now"}))
    monkeypatch.setattr(ma_live, "HEARTBEAT_PATH", heartbeat_path)
    monkeypatch.setattr(ma_live, "LOCK_PATH", lock_path)
    monkeypatch.setattr(ma_live, "pid_is_running", lambda pid: int(pid) == 999)

    def fake_run_command(cmd):
        raise AssertionError("scan should not run while lock is active")

    monkeypatch.setattr(ma_live, "run_command", fake_run_command)
    args = Namespace(
        market="stocks",
        symbols="AAPL",
        stock_intervals="15m,1h,2h,4h",
        stock_period="60d",
        intraday_stock_period="60d",
        crypto_timeframes="15m,1h,2h,4h",
        crypto_limit=500,
        trigger_tf="15m",
        trend_tf="1h",
        limit=5,
        report_limit=3,
        skip_ai_watch=True,
        notify=False,
        retention_count=10,
        health_check=False,
    )

    assert run_once(args) is None
    heartbeat = json.loads(heartbeat_path.read_text())
    assert heartbeat["status"] == "SKIPPED_ACTIVE_LOCK"
    assert heartbeat["active_lock"]["pid"] == 999
    assert lock_path.exists()
