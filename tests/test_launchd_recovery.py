from types import SimpleNamespace

from tools import launchd_recovery
from tools import ma_daily_launchd
from tools import ma_live_launchd
from tools import output_maintenance_launchd
from tools import roxy_health_launchd
from tools import streamlit_launchd


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


def test_recover_health_watchdog_config_does_nothing_when_current(monkeypatch):
    command = (
        "python tools/roxy_realtime_check.py --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-chart-health-report --ensure-output-maintenance-report "
        "--ensure-alert-quality-report --no-fail"
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


def test_recover_health_watchdog_config_reinstalls_when_flags_are_missing(monkeypatch, tmp_path):
    calls = []
    old_command = "python tools/roxy_realtime_check.py --notify-health --no-fail"
    new_command = (
        "python tools/roxy_realtime_check.py --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-chart-health-report --ensure-output-maintenance-report "
        "--ensure-alert-quality-report --no-fail"
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
        "--ensure-chart-health-report",
        "--ensure-output-maintenance-report",
        "--ensure-alert-quality-report",
    ]
    assert result["after_missing_flags"] == []
    assert calls[0].load is True
    assert calls[0].interval_seconds == roxy_health_launchd.DEFAULT_INTERVAL_SECONDS


def test_recover_health_watchdog_config_reinstalls_when_unloaded(monkeypatch, tmp_path):
    calls = []
    command = (
        "python tools/roxy_realtime_check.py --notify-health --ensure-runtime-backup-daemon "
        "--ensure-runtime-backup-report --ensure-core-launchagents --ensure-storage-migration --ensure-streamlit-app "
        "--ensure-live-data --ensure-yfinance-cache --ensure-chart-health-report --ensure-output-maintenance-report "
        "--ensure-alert-quality-report --no-fail"
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
            "command": "python tools/output_maintenance.py",
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
                "command": "python tools/output_maintenance.py",
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
    assert result["issues"] == ["dry_run"]
    assert result["after_issues"] == []
    assert calls[0].dry_run is False
    assert calls[0].load is True


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
                "--crypto-timeframes 15m,1h,2h,4h --retention-count 96 --health-check"
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
                    "--crypto-timeframes 15m,1h,2h,4h --retention-count 96 --health-check"
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
    assert result["issues"] == ["stock_timeframes", "crypto_timeframes", "retention_missing", "health_check_missing"]
    assert result["after_issues"] == []
    assert calls[0].stock_intervals == "15m,1h,2h,4h"
    assert calls[0].crypto_timeframes == "15m,1h,2h,4h"
    assert calls[0].retention_count == 96
    assert calls[0].health_check is True
    assert calls[0].load is True


def test_recover_streamlit_config_does_nothing_when_current(monkeypatch):
    monkeypatch.setattr(
        streamlit_launchd,
        "status",
        lambda: {
            "label": "com.roxy.streamlit",
            "installed": True,
            "loaded": True,
            "keep_alive": True,
            "command": "python -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501",
            "address": "0.0.0.0",
            "port": 8501,
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
                "command": "python -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501",
                "address": "0.0.0.0",
                "port": 8501,
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
        DEFAULT_PORT=8501,
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
