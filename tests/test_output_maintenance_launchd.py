import plistlib

from tools.output_maintenance_launchd import build_plist, build_shell_command, parse_args, write_plist


def test_build_shell_command_runs_output_maintenance():
    command = build_shell_command(python_path="/tmp/venv/bin/python", dry_run=True)

    assert "Application Support/RoxyTrading/.env" in command
    assert "PYTHONPATH=" in command
    assert "/tmp/venv/bin/python" in command
    assert "tools/output_maintenance.py" in command
    assert "--dry-run" in command


def test_build_plist_has_daily_calendar_and_logs():
    plist = build_plist(
        label="com.roxy.output_maintenance",
        command="echo clean",
        hour=3,
        minute=10,
        stdout_path="/tmp/output_maintenance.out",
        stderr_path="/tmp/output_maintenance.err",
        run_at_load=False,
    )

    assert plist["Label"] == "com.roxy.output_maintenance"
    assert plist["ProgramArguments"] == ["/bin/bash", "-lc", "echo clean"]
    assert plist["StartCalendarInterval"] == {"Hour": 3, "Minute": 10}
    assert plist["RunAtLoad"] is False
    assert plist["StandardOutPath"] == "/tmp/output_maintenance.out"
    assert plist["StandardErrorPath"] == "/tmp/output_maintenance.err"


def test_write_plist_round_trips(tmp_path):
    path = tmp_path / "com.roxy.output_maintenance.plist"
    plist = build_plist(
        label="com.roxy.output_maintenance",
        command="echo clean",
        hour=3,
        minute=10,
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
        run_at_load=False,
    )

    write_plist(path, plist)

    with path.open("rb") as fh:
        loaded = plistlib.load(fh)
    assert loaded == plist


def test_install_defaults_to_overnight_cleanup(monkeypatch):
    monkeypatch.setattr("sys.argv", ["output_maintenance_launchd.py", "install", "--no-load"])

    args = parse_args()

    assert args.hour == 3
    assert args.minute == 10
    assert args.dry_run is False
