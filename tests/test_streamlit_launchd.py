import plistlib

from tools import streamlit_launchd
from tools.streamlit_launchd import (
    build_plist,
    build_program_arguments,
    launchd_python_path,
    status,
    streamlit_address_from_plist,
    streamlit_port_from_plist,
    write_plist,
)


def test_build_program_arguments_defaults_to_lan_binding():
    args = build_program_arguments(python_path="/tmp/venv/bin/python")

    assert args[:4] == ["/tmp/venv/bin/python", "-m", "streamlit", "run"]
    assert "--server.address" in args
    assert args[args.index("--server.address") + 1] == "0.0.0.0"
    assert "--server.port" in args
    assert args[args.index("--server.port") + 1] == "3000"
    assert "--server.headless" in args
    assert args[args.index("--server.runOnSave") + 1] == "true"
    assert args[args.index("--server.fileWatcherType") + 1] == "auto"


def test_launchd_python_path_prefers_project_venv(tmp_path, monkeypatch):
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.touch()
    monkeypatch.setattr(streamlit_launchd, "BASE_DIR", tmp_path)

    path = launchd_python_path()

    assert path == venv_python


def test_build_plist_reads_address_and_port():
    plist = build_plist(
        label="com.roxy.streamlit",
        python_path="/tmp/venv/bin/python",
        address="0.0.0.0",
        port=3000,
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
    )

    assert plist["Label"] == "com.roxy.streamlit"
    assert plist["KeepAlive"] is True
    assert streamlit_address_from_plist(plist) == "0.0.0.0"
    assert streamlit_port_from_plist(plist) == 3000


def test_write_plist_round_trips(tmp_path):
    path = tmp_path / "com.roxy.streamlit.plist"
    plist = build_plist(
        label="com.roxy.streamlit",
        python_path="/tmp/venv/bin/python",
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
    )

    write_plist(path, plist)

    with path.open("rb") as fh:
        loaded = plistlib.load(fh)
    assert loaded == plist


def test_status_exposes_keepalive_and_command(tmp_path, monkeypatch):
    path = tmp_path / "com.roxy.streamlit.plist"
    plist = build_plist(
        label="com.roxy.streamlit",
        python_path="/tmp/venv/bin/python",
        address="0.0.0.0",
        port=3000,
        stdout_path="/tmp/out.log",
        stderr_path="/tmp/err.log",
    )
    write_plist(path, plist)
    monkeypatch.setattr("tools.streamlit_launchd.plist_path_for_label", lambda label="com.roxy.streamlit": path)
    monkeypatch.setattr("tools.streamlit_launchd.is_loaded", lambda label="com.roxy.streamlit": True)

    info = status()

    assert info["installed"] is True
    assert info["loaded"] is True
    assert info["keep_alive"] is True
    assert info["port"] == 3000
    assert "streamlit_app.py" in info["command"]
