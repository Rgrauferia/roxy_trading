import plistlib

from tools.runtime_backup_launchd import build_plist, build_shell_command, parse_args, write_plist


def test_build_shell_command_runs_runtime_backup():
    command = build_shell_command(python_path="/tmp/venv/bin/python", dry_run=True)

    assert "Application Support/RoxyTrading/.env" in command
    assert "PYTHONPATH=" in command
    assert "/tmp/venv/bin/python" in command
    assert "tools/runtime_backup.py" in command
    assert "--dry-run" in command


def test_build_plist_has_daily_calendar_and_logs():
    plist = build_plist(
        label="com.roxy.runtime_backup",
        command="echo backup",
        hour=3,
        minute=25,
        stdout_path="/tmp/runtime_backup.out",
        stderr_path="/tmp/runtime_backup.err",
        run_at_load=False,
    )

    assert plist["Label"] == "com.roxy.runtime_backup"
    assert plist["ProgramArguments"] == ["/bin/bash", "-lc", "echo backup"]
    assert plist["StartCalendarInterval"] == {"Hour": 3, "Minute": 25}
    assert plist["RunAtLoad"] is False
    assert plist["StandardOutPath"] == "/tmp/runtime_backup.out"
    assert plist["StandardErrorPath"] == "/tmp/runtime_backup.err"


def test_write_plist_round_trips(tmp_path):
    path = tmp_path / "com.roxy.runtime_backup.plist"
    plist = build_plist(
        label="com.roxy.runtime_backup",
        command="echo backup",
        hour=3,
        minute=25,
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
        run_at_load=False,
    )

    write_plist(path, plist)

    with path.open("rb") as fh:
        loaded = plistlib.load(fh)
    assert loaded == plist


def test_install_defaults_to_overnight_backup(monkeypatch):
    monkeypatch.setattr("sys.argv", ["runtime_backup_launchd.py", "install", "--no-load"])

    args = parse_args()

    assert args.hour == 3
    assert args.minute == 25
    assert args.dry_run is False
