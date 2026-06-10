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
        health_app_url="http://127.0.0.1:8501",
        health_chart_symbol="AAPL",
        health_chart_timeframe="1h",
        health_skip_chart_fetch=False,
    )

    cmd = build_health_check_command(args, "/tmp/python")
    joined = " ".join(cmd)

    assert cmd[0] == "/tmp/python"
    assert "tools/roxy_realtime_check.py" in joined
    assert "--no-fail" in cmd
    assert "--app-url http://127.0.0.1:8501" in joined
    assert "--chart-symbol AAPL" in joined


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
    monkeypatch.setattr(ma_live, "HEARTBEAT_PATH", heartbeat_path)
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
    assert any("roxy_ai_watch.py" in command for command in commands)
    assert any("roxy_realtime_check.py" in command for command in commands)
    assert health_saw_final_heartbeat is True


def test_run_once_writes_failed_heartbeat(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "heartbeat.json"
    monkeypatch.setattr(ma_live, "HEARTBEAT_PATH", heartbeat_path)

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
