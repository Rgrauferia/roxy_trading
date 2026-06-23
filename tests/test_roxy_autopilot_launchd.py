import plistlib

from tools.roxy_autopilot_launchd import build_plist, build_shell_command, parse_args, status, write_plist


def test_build_shell_command_runs_autopilot_apply():
    command = build_shell_command(python_path="/tmp/venv/bin/python", apply=True)

    assert "Application Support/RoxyTrading/.env" in command
    assert "PYTHONPATH=" in command
    assert "/tmp/venv/bin/python" in command
    assert "tools/roxy_autopilot.py" in command
    assert "--apply" in command


def test_build_shell_command_can_run_observe_only():
    command = build_shell_command(python_path="/tmp/venv/bin/python", apply=False)

    assert "tools/roxy_autopilot.py" in command
    assert "--apply" not in command


def test_build_plist_has_interval_and_logs():
    plist = build_plist(
        label="com.roxy.autopilot",
        command="echo autopilot",
        interval_seconds=60,
        stdout_path="/tmp/autopilot.out",
        stderr_path="/tmp/autopilot.err",
        run_at_load=True,
    )

    assert plist["Label"] == "com.roxy.autopilot"
    assert plist["ProgramArguments"] == ["/bin/bash", "-lc", "echo autopilot"]
    assert plist["StartInterval"] == 60
    assert plist["RunAtLoad"] is True
    assert plist["StandardOutPath"] == "/tmp/autopilot.out"
    assert plist["StandardErrorPath"] == "/tmp/autopilot.err"


def test_write_plist_round_trips(tmp_path):
    path = tmp_path / "com.roxy.autopilot.plist"
    plist = build_plist(
        label="com.roxy.autopilot",
        command="echo autopilot",
        interval_seconds=60,
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
        run_at_load=True,
    )

    write_plist(path, plist)

    with path.open("rb") as fh:
        loaded = plistlib.load(fh)
    assert loaded == plist


def test_status_reads_interval_and_command(tmp_path, monkeypatch):
    path = tmp_path / "com.roxy.autopilot.plist"
    plist = build_plist(
        label="com.roxy.autopilot",
        command="python tools/roxy_autopilot.py --apply",
        interval_seconds=60,
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
        run_at_load=True,
    )
    write_plist(path, plist)
    monkeypatch.setattr("tools.roxy_autopilot_launchd.plist_path_for_label", lambda label: path)
    monkeypatch.setattr("tools.roxy_autopilot_launchd.is_loaded", lambda label: True)

    info = status()

    assert info["installed"] is True
    assert info["loaded"] is True
    assert info["interval_seconds"] == 60
    assert "--apply" in info["command"]


def test_install_defaults_to_one_minute_apply(monkeypatch):
    monkeypatch.setattr("sys.argv", ["roxy_autopilot_launchd.py", "install", "--no-load"])

    args = parse_args()

    assert args.interval_seconds == 60
    assert args.apply is True
