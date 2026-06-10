import plistlib

from tools.ma_live_launchd import build_plist, build_shell_command, parse_args, write_plist


def test_build_shell_command_runs_live_tool_with_polling():
    command = build_shell_command(
        python_path="/tmp/venv/bin/python",
        market="both",
        stock_intervals="15m,1h",
        crypto_timeframes="15m,1h",
        trigger_tf="15m",
        trend_tf="1h",
        poll_seconds=300,
        limit=30,
        report_limit=12,
        retention_count=96,
        health_check=True,
        health_app_url="http://127.0.0.1:8501",
        health_chart_symbol="AAPL",
        health_chart_timeframe="1h",
        health_skip_chart_fetch=False,
        symbols="AAPL,MSFT",
    )

    assert "Application Support/RoxyTrading/.env" in command
    assert "PYTHONPATH=" in command
    assert "/tmp/venv/bin/python" in command
    assert "tools/ma_live.py" in command
    assert "--stock-intervals 15m,1h" in command
    assert "--crypto-timeframes 15m,1h" in command
    assert "--trigger-tf 15m" in command
    assert "--trend-tf 1h" in command
    assert "--poll-seconds 300" in command
    assert "--retention-count 96" in command
    assert "--health-check" in command
    assert "--health-app-url http://127.0.0.1:8501" in command
    assert "--health-chart-symbol AAPL" in command
    assert "--symbols AAPL,MSFT" in command


def test_build_plist_is_keepalive_service():
    plist = build_plist(
        label="com.roxy.ma_live",
        command="echo live",
        stdout_path="/tmp/ma_live.out",
        stderr_path="/tmp/ma_live.err",
        run_at_load=True,
        keep_alive=True,
    )

    assert plist["Label"] == "com.roxy.ma_live"
    assert plist["ProgramArguments"] == ["/bin/bash", "-lc", "echo live"]
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] is True
    assert plist["StandardOutPath"] == "/tmp/ma_live.out"
    assert plist["StandardErrorPath"] == "/tmp/ma_live.err"


def test_write_plist_round_trips(tmp_path):
    path = tmp_path / "com.roxy.ma_live.plist"
    plist = build_plist(
        label="com.roxy.ma_live",
        command="echo live",
        stdout_path="/tmp/ma_live.out",
        stderr_path="/tmp/ma_live.err",
        run_at_load=True,
        keep_alive=True,
    )

    write_plist(path, plist)

    with path.open("rb") as fh:
        loaded = plistlib.load(fh)
    assert loaded == plist


def test_install_defaults_cover_higher_timeframes(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ma_live_launchd.py", "install", "--no-load"])

    args = parse_args()

    assert args.stock_intervals == "15m,1h,2h,4h"
    assert args.crypto_timeframes == "15m,1h,2h,4h"
    assert args.retention_count == 96
    assert args.health_check is True
