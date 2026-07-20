import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from tools import launchd_recovery
from tools import mobile_gateway
from tools import ma_daily_launchd
from tools import ma_live_launchd
from tools import output_maintenance_launchd
from tools import price_alert_monitor_launchd
from tools import roxy_health_launchd
from tools import streamlit_launchd
from tools import voice_live_launchd


def test_price_alert_monitor_launchd_contract_is_core_and_runs_every_minute(tmp_path):
    plist = price_alert_monitor_launchd.build_plist(
        python_path=tmp_path / "python",
        interval_seconds=60,
    )
    command = plist["ProgramArguments"][2]

    assert launchd_recovery.CORE_LAUNCHD_MODULES["price_alert_monitor"] == "tools.price_alert_monitor_launchd"
    assert plist["StartInterval"] == 60
    assert plist["RunAtLoad"] is True
    assert "price_alert_monitor.py" in command
    assert "--no-fail" in command
    assert "Application Support/RoxyTrading/.env" in command


def test_voice_live_launchd_is_core_and_reinstalls_legacy_direct_command(monkeypatch, tmp_path):
    legacy = {
        "label": voice_live_launchd.DEFAULT_LABEL,
        "installed": True,
        "loaded": True,
        "path": str(tmp_path / "voice.plist"),
        "command": "python -m uvicorn tools.voice_service:app --host 127.0.0.1 --port 8010",
        "host": "127.0.0.1",
        "port": 8010,
        "environment_managed": False,
        "pythonpath_managed": False,
    }
    current = {
        **legacy,
        "command": "source managed.env && export PYTHONPATH=x && uvicorn tools.voice_service:app --host 127.0.0.1 --port 8010",
        "environment_managed": True,
        "pythonpath_managed": True,
    }
    states = iter((legacy, current))
    monkeypatch.setattr(voice_live_launchd, "status", lambda: next(states))
    monkeypatch.setattr(voice_live_launchd, "configured_host", lambda: "127.0.0.1")
    monkeypatch.setattr(voice_live_launchd, "configured_port", lambda: 8010)
    monkeypatch.setattr(voice_live_launchd, "install", lambda args: tmp_path / "voice.plist")

    result = launchd_recovery.recover_voice_live_config()

    assert launchd_recovery.CORE_LAUNCHD_MODULES["voice_live"] == "tools.voice_live_launchd"
    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["environment_not_managed", "pythonpath_not_managed"]
    assert result["after_issues"] == []


def test_launchd_recovery_cli_help_runs_from_repo_root():
    root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "tools/launchd_recovery.py", "--help"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Recover installed Roxy LaunchAgents" in result.stdout


def test_mobile_gateway_is_recoverable_but_not_a_core_requirement(monkeypatch, tmp_path):
    states = iter((
        {
            "label": mobile_gateway.DEFAULT_LABEL,
            "installed": True,
            "loaded": False,
            "path": str(tmp_path / "gateway.plist"),
        },
        {
            "label": mobile_gateway.DEFAULT_LABEL,
            "installed": True,
            "loaded": True,
            "path": str(tmp_path / "gateway.plist"),
        },
    ))
    monkeypatch.setattr(mobile_gateway, "status", lambda: next(states))
    monkeypatch.setattr(mobile_gateway, "bootstrap", lambda path: None)

    result = launchd_recovery.recover_launch_agent("tools.mobile_gateway")

    assert "mobile_gateway" not in launchd_recovery.CORE_LAUNCHD_MODULES
    assert launchd_recovery.OPTIONAL_LAUNCHD_MODULES["mobile_gateway"] == "tools.mobile_gateway"
    assert result["action"] == "bootstrapped"
    assert result["ok"] is True


def health_watchdog_command(realtime_command: str) -> str:
    if "roxy_realtime_check.py" in realtime_command and "--app-url" not in realtime_command:
        realtime_command = realtime_command.replace(
            "roxy_realtime_check.py ",
            "roxy_realtime_check.py --app-url http://127.0.0.1:3000 ",
            1,
        )
    return (
        "python tools/chart_realtime_health.py --include-active-alert-symbols --no-fail "
        "&& python alert_quality.py "
        f"&& {realtime_command}"
    )


def test_recover_launch_agent_does_nothing_when_loaded(monkeypatch):
    module = SimpleNamespace(
        DEFAULT_LABEL="com.test.loaded",
        status=lambda: {"label": "com.test.loaded", "installed": True, "loaded": True, "path": "/tmp/test.plist"},
        bootstrap=lambda path: (_ for _ in ()).throw(AssertionError("should not bootstrap")),
    )
    monkeypatch.setattr(launchd_recovery.importlib, "import_module", lambda name: module)

    result = launchd_recovery.recover_launch_agent("tools.fake")

    assert result["action"] == "already_loaded"
    assert result["ok"] is True


def test_recover_launch_agent_bootstraps_installed_unloaded_service(monkeypatch):
    calls = []
    states = [
        {"label": "com.test.unloaded", "installed": True, "loaded": False, "path": "/tmp/test.plist"},
        {"label": "com.test.unloaded", "installed": True, "loaded": True, "path": "/tmp/test.plist"},
    ]

    def status():
        return states[min(len(calls), 1)]

    def bootstrap(path):
        calls.append(str(path))

    module = SimpleNamespace(DEFAULT_LABEL="com.test.unloaded", status=status, bootstrap=bootstrap)
    monkeypatch.setattr(launchd_recovery.importlib, "import_module", lambda name: module)

    result = launchd_recovery.recover_launch_agent("tools.fake")

    assert result["action"] == "bootstrapped"
    assert result["ok"] is True
    assert calls == ["/tmp/test.plist"]


def test_ensure_core_launch_agents_summarizes_failures(monkeypatch):
    results = {
        "tools.ok": {"action": "already_loaded", "ok": True},
        "tools.fail": {"action": "not_installed", "ok": False},
    }
    monkeypatch.setattr(launchd_recovery, "recover_launch_agent", lambda module_name: results[module_name])

    result = launchd_recovery.ensure_core_launch_agents({"ok": "tools.ok", "fail": "tools.fail"})

    assert result["status"] == "WARN"
    assert result["failed"] == ["fail"]


def test_ensure_core_launch_agents_writes_report_when_path_is_provided(monkeypatch, tmp_path):
    report_path = tmp_path / "launchd_recovery.json"
    generated_at = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    results = {
        "tools.ok": {"action": "already_loaded", "ok": True},
        "tools.recovered": {"action": "bootstrapped", "ok": True},
    }
    monkeypatch.setattr(launchd_recovery, "recover_launch_agent", lambda module_name: results[module_name])
    monkeypatch.setattr(launchd_recovery, "utc_now", lambda: generated_at)

    result = launchd_recovery.ensure_core_launch_agents(
        {"ok": "tools.ok", "recovered": "tools.recovered"},
        report_path=report_path,
    )

    payload = json.loads(report_path.read_text())
    assert result["status"] == "OK"
    assert result["report_path"] == str(report_path)
    assert payload["generated_at"] == "2026-06-10T12:00:00+00:00"
    assert payload["status"] == "OK"
    assert payload["service_count"] == 2
    assert payload["recovered"] == ["recovered"]
    assert payload["failed"] == []
    assert payload["report_path"] == str(report_path)


def test_recover_health_watchdog_config_does_nothing_when_current(monkeypatch):
    command = health_watchdog_command(
        "python tools/roxy_realtime_check.py --app-url http://127.0.0.1:3000 --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report --ensure-chart-health-report --ensure-output-maintenance-report "
        "--ensure-alert-quality-report --ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )
    monkeypatch.setattr(
        roxy_health_launchd,
        "status",
        lambda: {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        },
    )
    monkeypatch.setattr(
        roxy_health_launchd,
        "install",
        lambda args: (_ for _ in ()).throw(AssertionError("should not reinstall")),
    )

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "already_current"
    assert result["ok"] is True
    assert result["missing_flags"] == []
    assert result["app_url"] == "http://127.0.0.1:3000"
    assert result["chart_health_preflight"] is True
    assert result["alert_quality_preflight"] is True
    assert result["chart_health_preflight_no_fail"] is True
    assert result["preflight_order_ok"] is True


def test_recover_health_watchdog_config_reinstalls_when_flags_are_missing(monkeypatch, tmp_path):
    calls = []
    old_command = "python tools/roxy_realtime_check.py --notify-health --no-fail"
    new_command = health_watchdog_command(
        "python tools/roxy_realtime_check.py --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report --ensure-chart-health-report --ensure-output-maintenance-report "
        "--ensure-alert-quality-report --ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )

    def status():
        command = new_command if calls else old_command
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["missing_flags"] == [
        "--ensure-runtime-backup-daemon",
        "--ensure-runtime-backup-report",
        "--ensure-core-launchagents",
        "--ensure-storage-migration",
        "--ensure-live-data",
        "--ensure-yfinance-cache",
        "--ensure-streamlit-app",
        "--ensure-dashboard-history-sample",
        "--ensure-dashboard-render-probe-report",
        "--ensure-chart-health-report",
        "--ensure-output-maintenance-report",
        "--ensure-alert-quality-report",
        "--ensure-daily-opportunity-plan-report",
        "--ensure-status-snapshot-report",
    ]
    assert result["after_missing_flags"] == []
    assert result["after_chart_health_preflight"] is True
    assert result["after_alert_quality_preflight"] is True
    assert result["after_chart_health_preflight_no_fail"] is True
    assert calls[0].load is True
    assert calls[0].ensure_dashboard_history_sample is True
    assert calls[0].interval_seconds == roxy_health_launchd.DEFAULT_INTERVAL_SECONDS


def test_recover_health_watchdog_config_reinstalls_when_realtime_flag_is_missing(monkeypatch, tmp_path):
    calls = []
    old_realtime_command = (
        "python tools/roxy_realtime_check.py --app-url http://127.0.0.1:3000 --notify-health "
        "--ensure-runtime-backup-daemon --ensure-runtime-backup-report --ensure-core-launchagents "
        "--ensure-storage-migration --ensure-streamlit-app --ensure-live-data --ensure-yfinance-cache "
        "--ensure-dashboard-history-sample --ensure-dashboard-render-probe-report --ensure-chart-health-report "
        "--ensure-output-maintenance-report --ensure-alert-quality-report --ensure-daily-opportunity-plan-report "
        "--ensure-status-snapshot-report"
    )
    new_realtime_command = f"{old_realtime_command} --no-fail"
    old_command = (
        "python tools/chart_realtime_health.py --include-active-alert-symbols --no-fail "
        "&& python alert_quality.py "
        f"&& {old_realtime_command}"
    )
    new_command = health_watchdog_command(new_realtime_command)

    def status():
        command = new_command if calls else old_command
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["missing_flags"]
    assert result["missing_flags"] == ["--no-fail"]
    assert result["after_missing_flags"] == []
    assert calls


def test_recover_health_watchdog_config_reinstalls_for_forced_chart_symbol(monkeypatch, tmp_path):
    calls = []
    old_command = health_watchdog_command(
        "python tools/roxy_realtime_check.py --chart-symbol AAPL --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report "
        "--ensure-chart-health-report --ensure-output-maintenance-report --ensure-alert-quality-report "
        "--ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )
    new_command = old_command.replace("--chart-symbol AAPL ", "")

    def status():
        command = new_command if calls else old_command
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["forced_chart_symbol"]
    assert result["forced_chart_symbol"] == "AAPL"
    assert calls[0].chart_symbol == ""


def test_recover_health_watchdog_config_reinstalls_when_preflights_are_missing(monkeypatch, tmp_path):
    calls = []
    old_command = (
        "python tools/roxy_realtime_check.py --app-url http://127.0.0.1:3000 --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report "
        "--ensure-chart-health-report --ensure-output-maintenance-report --ensure-alert-quality-report "
        "--ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )
    new_command = health_watchdog_command(old_command)

    def status():
        command = new_command if calls else old_command
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["missing_chart_health_preflight", "missing_alert_quality_preflight"]
    assert result["chart_health_preflight"] is False
    assert result["alert_quality_preflight"] is False
    assert result["after_chart_health_preflight"] is True
    assert result["after_alert_quality_preflight"] is True
    assert calls


def test_recover_health_watchdog_config_reinstalls_when_chart_preflight_can_fail(monkeypatch, tmp_path):
    calls = []
    realtime_command = (
        "python tools/roxy_realtime_check.py --app-url http://127.0.0.1:3000 --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report "
        "--ensure-chart-health-report --ensure-output-maintenance-report --ensure-alert-quality-report "
        "--ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )
    old_command = (
        "python tools/chart_realtime_health.py --include-active-alert-symbols "
        "&& python alert_quality.py "
        f"&& {realtime_command}"
    )
    new_command = health_watchdog_command(realtime_command)

    def status():
        command = new_command if calls else old_command
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["missing_chart_health_preflight_no_fail"]
    assert result["chart_health_preflight"] is True
    assert result["chart_health_preflight_no_fail"] is False
    assert result["after_chart_health_preflight_no_fail"] is True
    assert calls


def test_recover_health_watchdog_config_reinstalls_when_preflights_run_after_check(monkeypatch, tmp_path):
    calls = []
    realtime_command = (
        "python tools/roxy_realtime_check.py --app-url http://127.0.0.1:3000 --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report "
        "--ensure-chart-health-report --ensure-output-maintenance-report --ensure-alert-quality-report "
        "--ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )
    old_command = (
        f"{realtime_command} "
        "&& python tools/chart_realtime_health.py --include-active-alert-symbols --no-fail "
        "&& python alert_quality.py"
    )
    new_command = health_watchdog_command(realtime_command)

    def status():
        command = new_command if calls else old_command
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["watchdog_preflight_order"]
    assert result["preflight_order_ok"] is False
    assert result["realtime_check_position"] < result["chart_health_position"]
    assert result["after_preflight_order_ok"] is True
    assert calls


def test_recover_health_watchdog_config_reinstalls_when_app_url_is_missing(monkeypatch, tmp_path):
    calls = []
    old_realtime_command = (
        "python tools/roxy_realtime_check.py --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report "
        "--ensure-chart-health-report --ensure-output-maintenance-report --ensure-alert-quality-report "
        "--ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )
    new_realtime_command = (
        "python tools/roxy_realtime_check.py --app-url http://127.0.0.1:3000 --notify-health "
        "--ensure-runtime-backup-daemon --ensure-runtime-backup-report --ensure-core-launchagents "
        "--ensure-storage-migration --ensure-streamlit-app --ensure-live-data --ensure-yfinance-cache "
        "--ensure-dashboard-history-sample --ensure-dashboard-render-probe-report --ensure-chart-health-report "
        "--ensure-output-maintenance-report --ensure-alert-quality-report --ensure-daily-opportunity-plan-report "
        "--ensure-status-snapshot-report --no-fail"
    )
    old_command = (
        "python tools/chart_realtime_health.py --include-active-alert-symbols --no-fail "
        "&& python alert_quality.py "
        f"&& {old_realtime_command}"
    )
    new_command = health_watchdog_command(new_realtime_command)

    def status():
        command = new_command if calls else old_command
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["missing_app_url"]
    assert result["app_url"] == ""
    assert result["after_app_url"] == "http://127.0.0.1:3000"
    assert calls[0].app_url == roxy_health_launchd.DEFAULT_APP_URL


def test_recover_health_watchdog_config_reinstalls_when_realtime_app_url_is_missing(monkeypatch, tmp_path):
    calls = []
    old_realtime_command = (
        "python tools/roxy_realtime_check.py --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report "
        "--ensure-chart-health-report --ensure-output-maintenance-report --ensure-alert-quality-report "
        "--ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )
    new_realtime_command = (
        "python tools/roxy_realtime_check.py --app-url http://127.0.0.1:3000 --notify-health "
        "--ensure-runtime-backup-daemon --ensure-runtime-backup-report --ensure-core-launchagents "
        "--ensure-storage-migration --ensure-streamlit-app --ensure-live-data --ensure-yfinance-cache "
        "--ensure-dashboard-history-sample --ensure-dashboard-render-probe-report --ensure-chart-health-report "
        "--ensure-output-maintenance-report --ensure-alert-quality-report --ensure-daily-opportunity-plan-report "
        "--ensure-status-snapshot-report --no-fail"
    )
    old_command = (
        "python tools/chart_realtime_health.py --app-url http://127.0.0.1:3000 "
        "--include-active-alert-symbols --no-fail "
        "&& python alert_quality.py "
        f"&& {old_realtime_command}"
    )
    new_command = health_watchdog_command(new_realtime_command)

    def status():
        command = new_command if calls else old_command
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": True,
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["missing_app_url"]
    assert result["app_url"] == ""
    assert result["after_app_url"] == "http://127.0.0.1:3000"
    assert calls[0].app_url == roxy_health_launchd.DEFAULT_APP_URL


def test_recover_health_watchdog_config_reinstalls_when_unloaded(monkeypatch, tmp_path):
    calls = []
    command = health_watchdog_command(
        "python tools/roxy_realtime_check.py --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-dashboard-history-sample --ensure-dashboard-render-probe-report --ensure-chart-health-report --ensure-output-maintenance-report "
        "--ensure-alert-quality-report --ensure-daily-opportunity-plan-report --ensure-status-snapshot-report --no-fail"
    )

    def status():
        return {
            "label": "com.roxy.health_watchdog",
            "installed": True,
            "loaded": bool(calls),
            "interval_seconds": 300,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.health_watchdog.plist"

    monkeypatch.setattr(roxy_health_launchd, "status", status)
    monkeypatch.setattr(roxy_health_launchd, "install", install)

    result = launchd_recovery.recover_health_watchdog_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["not_loaded"]
    assert calls


def test_recover_output_maintenance_config_does_nothing_when_current(monkeypatch):
    monkeypatch.setattr(
        output_maintenance_launchd,
        "status",
        lambda: {
            "label": "com.roxy.output_maintenance",
            "installed": True,
            "loaded": True,
            "command": "python tools/output_maintenance.py --enable-local-cache-cleanup",
            "schedule": {"Hour": 3, "Minute": 10},
        },
    )
    monkeypatch.setattr(
        output_maintenance_launchd,
        "install",
        lambda args: (_ for _ in ()).throw(AssertionError("should not reinstall")),
    )

    result = launchd_recovery.recover_output_maintenance_config()

    assert result["action"] == "already_current"
    assert result["ok"] is True
    assert result["issues"] == []


def test_recover_output_maintenance_config_reinstalls_dry_run_job(monkeypatch, tmp_path):
    calls = []

    def status():
        if calls:
            return {
                "label": "com.roxy.output_maintenance",
                "installed": True,
                "loaded": True,
                "command": "python tools/output_maintenance.py --enable-local-cache-cleanup",
                "schedule": {"Hour": 3, "Minute": 10},
            }
        return {
            "label": "com.roxy.output_maintenance",
            "installed": True,
            "loaded": True,
            "command": "python tools/output_maintenance.py --dry-run",
            "schedule": {"Hour": 3, "Minute": 10},
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.output_maintenance.plist"

    monkeypatch.setattr(output_maintenance_launchd, "status", status)
    monkeypatch.setattr(output_maintenance_launchd, "install", install)

    result = launchd_recovery.recover_output_maintenance_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["dry_run", "local_cache_cleanup_disabled"]
    assert result["after_issues"] == []
    assert calls[0].dry_run is False
    assert calls[0].enable_local_cache_cleanup is True
    assert calls[0].load is True


def test_recover_output_maintenance_config_reinstalls_preview_only_cache_job(monkeypatch, tmp_path):
    calls = []

    def status():
        if calls:
            return {
                "label": "com.roxy.output_maintenance",
                "installed": True,
                "loaded": True,
                "command": "python tools/output_maintenance.py --enable-local-cache-cleanup",
                "schedule": {"Hour": 3, "Minute": 10},
            }
        return {
            "label": "com.roxy.output_maintenance",
            "installed": True,
            "loaded": True,
            "command": "python tools/output_maintenance.py",
            "schedule": {"Hour": 3, "Minute": 10},
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.output_maintenance.plist"

    monkeypatch.setattr(output_maintenance_launchd, "status", status)
    monkeypatch.setattr(output_maintenance_launchd, "install", install)

    result = launchd_recovery.recover_output_maintenance_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["local_cache_cleanup_disabled"]
    assert result["after_issues"] == []
    assert calls[0].enable_local_cache_cleanup is True


def test_recover_ma_live_config_does_nothing_when_current(monkeypatch):
    monkeypatch.setattr(
        ma_live_launchd,
        "status",
        lambda: {
            "label": "com.roxy.ma_live",
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": (
                "python tools/ma_live.py --stock-intervals 15m,1h,2h,4h "
                "--crypto-timeframes 15m,1h,2h,4h --retention-count 96"
            ),
        },
    )
    monkeypatch.setattr(
        ma_live_launchd,
        "install",
        lambda args: (_ for _ in ()).throw(AssertionError("should not reinstall")),
    )

    result = launchd_recovery.recover_ma_live_config()

    assert result["action"] == "already_current"
    assert result["ok"] is True
    assert result["issues"] == []


def test_recover_ma_live_config_reinstalls_outdated_command(monkeypatch, tmp_path):
    calls = []

    def status():
        if calls:
            return {
                "label": "com.roxy.ma_live",
                "installed": True,
                "loaded": True,
                "keep_alive": True,
                "command": (
                    "python tools/ma_live.py --stock-intervals 15m,1h,2h,4h "
                    "--crypto-timeframes 15m,1h,2h,4h --retention-count 96"
                ),
            }
        return {
            "label": "com.roxy.ma_live",
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": "python tools/ma_live.py --stock-intervals 15m,1h --crypto-timeframes 15m,1h",
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.ma_live.plist"

    monkeypatch.setattr(ma_live_launchd, "status", status)
    monkeypatch.setattr(ma_live_launchd, "install", install)

    result = launchd_recovery.recover_ma_live_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["stock_timeframes", "crypto_timeframes", "retention_missing"]
    assert result["after_issues"] == []
    assert calls[0].stock_intervals == "15m,1h,2h,4h"
    assert calls[0].crypto_timeframes == "15m,1h,2h,4h"
    assert calls[0].retention_count == 96
    assert calls[0].health_check is False
    assert calls[0].load is True


def test_recover_ma_live_config_removes_duplicate_health_check(monkeypatch, tmp_path):
    calls = []

    def status():
        command = (
            "python tools/ma_live.py --stock-intervals 15m,1h,2h,4h "
            "--crypto-timeframes 15m,1h,2h,4h --retention-count 96"
        )
        if not calls:
            command = f"{command} --health-check"
        return {
            "label": "com.roxy.ma_live",
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": command,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.ma_live.plist"

    monkeypatch.setattr(ma_live_launchd, "status", status)
    monkeypatch.setattr(ma_live_launchd, "install", install)

    result = launchd_recovery.recover_ma_live_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["health_check_duplicate"]
    assert result["after_issues"] == []
    assert calls[0].health_check is False


def test_recover_streamlit_config_does_nothing_when_current(monkeypatch):
    monkeypatch.setattr(
        streamlit_launchd,
        "status",
        lambda: {
            "label": "com.roxy.streamlit",
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": "python -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 3000",
            "address": "0.0.0.0",
            "port": 3000,
            "lan_ready": True,
        },
    )
    monkeypatch.setattr(
        streamlit_launchd,
        "install",
        lambda args: (_ for _ in ()).throw(AssertionError("should not reinstall")),
    )

    result = launchd_recovery.recover_streamlit_config()

    assert result["action"] == "already_current"
    assert result["ok"] is True
    assert result["issues"] == []


def test_recover_streamlit_config_reinstalls_wrong_port(monkeypatch, tmp_path):
    calls = []

    def status():
        if calls:
            return {
                "label": "com.roxy.streamlit",
                "installed": True,
                "loaded": True,
                "keep_alive": True,
                "command": "python -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 3000",
                "address": "0.0.0.0",
                "port": 3000,
                "lan_ready": True,
            }
        return {
            "label": "com.roxy.streamlit",
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": "python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8502",
            "address": "127.0.0.1",
            "port": 8502,
            "lan_ready": False,
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.streamlit.plist"

    monkeypatch.setattr(streamlit_launchd, "status", status)
    monkeypatch.setattr(streamlit_launchd, "install", install)

    result = launchd_recovery.recover_streamlit_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["port_mismatch", "lan_not_ready"]
    assert result["after_issues"] == []
    assert calls[0].address == streamlit_launchd.DEFAULT_ADDRESS
    assert calls[0].port == streamlit_launchd.DEFAULT_PORT
    assert calls[0].load is True


def test_recover_ma_daily_config_does_nothing_when_current(monkeypatch):
    monkeypatch.setattr(
        ma_daily_launchd,
        "status",
        lambda: {
            "label": "com.roxy.ma_daily",
            "installed": True,
            "loaded": True,
            "command": "python tools/ma_daily.py --market both --retention-count 30",
            "schedule": {"Hour": 18, "Minute": 5},
        },
    )
    monkeypatch.setattr(
        ma_daily_launchd,
        "install",
        lambda args: (_ for _ in ()).throw(AssertionError("should not reinstall")),
    )

    result = launchd_recovery.recover_ma_daily_config()

    assert result["action"] == "already_current"
    assert result["ok"] is True
    assert result["issues"] == []


def test_recover_ma_daily_config_reinstalls_missing_schedule_and_retention(monkeypatch, tmp_path):
    calls = []

    def status():
        if calls:
            return {
                "label": "com.roxy.ma_daily",
                "installed": True,
                "loaded": True,
                "command": "python tools/ma_daily.py --market both --retention-count 30",
                "schedule": {"Hour": 18, "Minute": 5},
            }
        return {
            "label": "com.roxy.ma_daily",
            "installed": True,
            "loaded": True,
            "command": "python tools/ma_daily.py --market both",
            "schedule": {},
        }

    def install(args):
        calls.append(args)
        return tmp_path / "com.roxy.ma_daily.plist"

    monkeypatch.setattr(ma_daily_launchd, "status", status)
    monkeypatch.setattr(ma_daily_launchd, "install", install)

    result = launchd_recovery.recover_ma_daily_config()

    assert result["action"] == "reinstalled"
    assert result["ok"] is True
    assert result["issues"] == ["missing_schedule", "retention_missing"]
    assert result["after_issues"] == []
    assert calls[0].market == "both"
    assert calls[0].retention_count == 30
    assert calls[0].hour == ma_daily_launchd.DEFAULT_HOUR
    assert calls[0].minute == ma_daily_launchd.DEFAULT_MINUTE
    assert calls[0].load is True
    assert calls[0].run_now is False


def test_restart_launch_agent_bootouts_and_bootstraps_loaded_service(monkeypatch):
    calls = []
    states = [
        {"label": "com.test.restart", "installed": True, "loaded": True, "path": "/tmp/test.plist"},
        {"label": "com.test.restart", "installed": True, "loaded": True, "path": "/tmp/test.plist"},
    ]

    def status():
        return states[min(len(calls) // 2, 1)]

    def bootout(label):
        calls.append(("bootout", label))

    def bootstrap(path):
        calls.append(("bootstrap", str(path)))

    module = SimpleNamespace(DEFAULT_LABEL="com.test.restart", status=status, bootout=bootout, bootstrap=bootstrap)
    monkeypatch.setattr(launchd_recovery.importlib, "import_module", lambda name: module)

    result = launchd_recovery.restart_launch_agent("tools.fake")

    assert result["action"] == "restart"
    assert result["ok"] is True
    assert calls == [("bootout", "com.test.restart"), ("bootstrap", "/tmp/test.plist")]


def test_restart_launch_agent_reinstalls_when_bootstrap_leaves_service_unloaded(monkeypatch, tmp_path):
    calls = []
    states = [
        {"label": "com.roxy.streamlit", "installed": True, "loaded": True, "path": str(tmp_path / "streamlit.plist")},
        {"label": "com.roxy.streamlit", "installed": True, "loaded": False, "path": str(tmp_path / "streamlit.plist")},
        {"label": "com.roxy.streamlit", "installed": True, "loaded": True, "path": str(tmp_path / "streamlit.plist")},
    ]
    status_calls = []

    def tracked_status():
        index = min(len(status_calls), 2)
        status_calls.append(index)
        calls.append(("status", ""))
        return states[index]

    def bootout(label):
        calls.append(("bootout", label))

    def bootstrap(path):
        calls.append(("bootstrap", str(path)))

    def install(args):
        calls.append(("install", args.label, args.load))
        return tmp_path / "streamlit.plist"

    module = SimpleNamespace(
        DEFAULT_LABEL="com.roxy.streamlit",
        DEFAULT_ADDRESS="0.0.0.0",
        DEFAULT_PORT=3000,
        status=tracked_status,
        bootout=bootout,
        bootstrap=bootstrap,
        install=install,
    )
    monkeypatch.setattr(launchd_recovery.importlib, "import_module", lambda name: module)

    result = launchd_recovery.restart_launch_agent("tools.streamlit_launchd")

    assert result["action"] == "restart_reinstalled"
    assert result["ok"] is True
    assert ("bootout", "com.roxy.streamlit") in calls
    assert ("bootstrap", str(tmp_path / "streamlit.plist")) in calls
    assert ("install", "com.roxy.streamlit", True) in calls
