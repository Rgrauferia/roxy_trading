import plistlib
from pathlib import Path

from tools.ma_daily_launchd import build_plist, build_shell_command, normalize_python_path, status, write_plist


def test_build_shell_command_sources_env_and_runs_daily_tool():
    command = build_shell_command(
        python_path="/tmp/venv/bin/python",
        market="both",
        limit=30,
        report_limit=12,
        refresh_backtests=True,
        stock_period="5y",
        crypto_limit=1000,
        min_buy_hold_edge_pct=0,
        symbols="AAPL,MSFT",
    )

    assert "Application Support/RoxyTrading/.env" in command
    assert "PYTHONPATH=" in command
    assert "/tmp/venv/bin/python" in command
    assert "tools/ma_daily.py" in command
    assert "--market both" in command
    assert "--refresh-backtests" in command
    assert "--retention-count 30" in command
    assert "--symbols AAPL,MSFT" in command


def test_build_plist_has_daily_calendar_and_logs():
    plist = build_plist(
        label="com.roxy.ma_daily",
        command="echo run",
        hour=18,
        minute=5,
        stdout_path="/tmp/ma_daily.out",
        stderr_path="/tmp/ma_daily.err",
        run_at_load=False,
    )

    assert plist["Label"] == "com.roxy.ma_daily"
    assert plist["ProgramArguments"] == ["/bin/bash", "-lc", "echo run"]
    assert plist["StartCalendarInterval"] == {"Hour": 18, "Minute": 5}
    assert plist["RunAtLoad"] is False
    assert plist["StandardOutPath"] == "/tmp/ma_daily.out"
    assert plist["StandardErrorPath"] == "/tmp/ma_daily.err"


def test_write_plist_round_trips(tmp_path):
    path = tmp_path / "com.roxy.ma_daily.plist"
    plist = build_plist(
        label="com.roxy.ma_daily",
        command="echo run",
        hour=18,
        minute=5,
        stdout_path="/tmp/ma_daily.out",
        stderr_path="/tmp/ma_daily.err",
        run_at_load=False,
    )

    write_plist(path, plist)

    with path.open("rb") as fh:
        loaded = plistlib.load(fh)
    assert loaded == plist


def test_normalize_python_path_does_not_resolve_symlink_like_path():
    path = normalize_python_path("/tmp/project/.venv/bin/python")

    assert path == Path("/tmp/project/.venv/bin/python")


def test_status_reads_daily_schedule_and_command(tmp_path, monkeypatch):
    path = tmp_path / "com.roxy.ma_daily.plist"
    plist = build_plist(
        label="com.roxy.ma_daily",
        command="python tools/ma_daily.py --market both --retention-count 30",
        hour=18,
        minute=5,
        stdout_path="/tmp/ma_daily.out",
        stderr_path="/tmp/ma_daily.err",
        run_at_load=False,
    )
    write_plist(path, plist)
    monkeypatch.setattr("tools.ma_daily_launchd.plist_path_for_label", lambda label: path)
    monkeypatch.setattr("tools.ma_daily_launchd.is_loaded", lambda label: True)

    info = status()

    assert info["installed"] is True
    assert info["loaded"] is True
    assert info["schedule"] == {"Hour": 18, "Minute": 5}
    assert "tools/ma_daily.py" in info["command"]
