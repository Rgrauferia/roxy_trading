from __future__ import annotations

import argparse

from tools.macro_calendar_launchd import build_plist, build_shell_command, install, status


def test_macro_calendar_launchd_plist_is_bounded_and_runs_official_sync():
    plist = build_plist(python_path="/tmp/roxy python", interval_seconds=10)
    command = plist["ProgramArguments"][2]

    assert plist["Label"] == "com.roxy.macro-calendar"
    assert plist["RunAtLoad"] is True
    assert plist["StartInterval"] == 3_600
    assert "macro_calendar_sync.py" in command
    assert "--no-fail" in command
    assert build_shell_command("/tmp/roxy python") == command


def test_macro_calendar_launchd_install_and_status_without_loading(tmp_path, monkeypatch):
    plist_path = tmp_path / "macro.plist"
    monkeypatch.setattr("tools.macro_calendar_launchd.plist_path_for_label", lambda label: plist_path)
    monkeypatch.setattr("tools.macro_calendar_launchd.LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr("tools.macro_calendar_launchd.is_loaded", lambda label: False)
    args = argparse.Namespace(
        label="com.roxy.macro-calendar-test",
        python_path="/tmp/python",
        interval_seconds=21_600,
        load=False,
    )

    written = install(args)
    info = status(args.label)

    assert written == plist_path
    assert info["installed"] is True
    assert info["loaded"] is False
    assert info["interval_seconds"] == 21_600
    assert not [path for path in tmp_path.iterdir() if path.name.endswith(".tmp")]
