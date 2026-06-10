import plistlib

from tools.roxy_health_launchd import build_plist, build_shell_command, parse_args, status, write_plist


def test_build_shell_command_runs_realtime_check():
    command = build_shell_command(
        python_path="/tmp/venv/bin/python",
        app_url="http://127.0.0.1:8501",
        chart_symbol="AAPL",
        chart_timeframe="1h",
    )

    assert "Application Support/RoxyTrading/.env" in command
    assert "PYTHONPATH=" in command
    assert "/tmp/venv/bin/python" in command
    assert "tools/chart_realtime_health.py" in command
    assert "alert_quality.py" in command
    assert "tools/roxy_realtime_check.py" in command
    assert "--app-url http://127.0.0.1:8501" in command
    assert "--chart-symbol AAPL" in command
    assert "--chart-timeframe 1h" in command
    assert "--notify-health" in command
    assert "--ensure-runtime-backup-daemon" in command
    assert "--ensure-runtime-backup-report" in command
    assert "--ensure-core-launchagents" in command
    assert "--ensure-storage-migration" in command
    assert "--ensure-live-data" in command
    assert "--ensure-yfinance-cache" in command
    assert "--ensure-streamlit-app" in command
    assert "--ensure-chart-health-report" in command
    assert "--ensure-output-maintenance-report" in command
    assert "--ensure-alert-quality-report" in command
    assert "--no-fail" in command


def test_build_plist_has_start_interval_and_logs():
    plist = build_plist(
        label="com.roxy.health_watchdog",
        command="echo check",
        interval_seconds=300,
        stdout_path="/tmp/health.out",
        stderr_path="/tmp/health.err",
        run_at_load=True,
    )

    assert plist["Label"] == "com.roxy.health_watchdog"
    assert plist["ProgramArguments"] == ["/bin/bash", "-lc", "echo check"]
    assert plist["StartInterval"] == 300
    assert plist["RunAtLoad"] is True
    assert plist["StandardOutPath"] == "/tmp/health.out"
    assert plist["StandardErrorPath"] == "/tmp/health.err"


def test_write_plist_round_trips(tmp_path):
    path = tmp_path / "com.roxy.health_watchdog.plist"
    plist = build_plist(
        label="com.roxy.health_watchdog",
        command="echo check",
        interval_seconds=300,
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
        run_at_load=True,
    )

    write_plist(path, plist)

    with path.open("rb") as fh:
        loaded = plistlib.load(fh)
    assert loaded == plist


def test_status_reads_interval_and_command(tmp_path, monkeypatch):
    path = tmp_path / "com.roxy.health_watchdog.plist"
    plist = build_plist(
        label="com.roxy.health_watchdog",
        command="python tools/roxy_realtime_check.py --no-fail",
        interval_seconds=300,
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
        run_at_load=True,
    )
    write_plist(path, plist)
    monkeypatch.setattr("tools.roxy_health_launchd.plist_path_for_label", lambda label: path)
    monkeypatch.setattr("tools.roxy_health_launchd.is_loaded", lambda label: True)

    info = status()

    assert info["installed"] is True
    assert info["loaded"] is True
    assert info["interval_seconds"] == 300
    assert info["run_at_load"] is True
    assert "roxy_realtime_check.py" in info["command"]


def test_install_defaults_to_five_minute_watchdog(monkeypatch):
    monkeypatch.setattr("sys.argv", ["roxy_health_launchd.py", "install", "--no-load"])

    args = parse_args()

    assert args.interval_seconds == 300
    assert args.app_url == "http://127.0.0.1:8501"
    assert args.chart_symbol == "AAPL"
    assert args.skip_chart_health is False
    assert args.skip_alert_quality is False
    assert args.notify_health is True
    assert args.ensure_runtime_backup_daemon is True
    assert args.ensure_runtime_backup_report is True
    assert args.ensure_core_launchagents is True
    assert args.ensure_storage_migration is True
    assert args.ensure_live_data is True
    assert args.ensure_yfinance_cache is True
    assert args.ensure_streamlit_app is True
    assert args.ensure_chart_health_report is True
    assert args.ensure_output_maintenance_report is True
    assert args.ensure_alert_quality_report is True


def test_build_shell_command_can_skip_chart_health():
    command = build_shell_command(
        python_path="/tmp/venv/bin/python",
        app_url="http://127.0.0.1:8501",
        chart_symbol="AAPL",
        chart_timeframe="1h",
        skip_chart_health=True,
    )

    assert "tools/chart_realtime_health.py" not in command
    assert "tools/roxy_realtime_check.py" in command
