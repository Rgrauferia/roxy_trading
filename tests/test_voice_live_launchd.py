import argparse
from pathlib import Path

from tools import voice_live_launchd


def test_voice_launchd_defaults_to_loopback_and_managed_environment(tmp_path):
    plist = voice_live_launchd.build_plist(python_path=tmp_path / "python")
    command = plist["ProgramArguments"][2]

    assert plist["ProgramArguments"][:2] == ["/bin/bash", "-lc"]
    assert "tools.voice_service:app" in command
    assert "--host 127.0.0.1" in command
    assert "--port 8010" in command
    assert "Application Support/RoxyTrading/.env" in command
    assert "set -a" in command and "set +a" in command
    assert "export PYTHONPATH=" in command


def test_voice_launchd_status_detects_managed_contract(tmp_path, monkeypatch):
    plist_path = tmp_path / "com.roxy.voice-live.plist"
    payload = voice_live_launchd.build_plist(
        python_path=tmp_path / "python",
        host="127.0.0.1",
        port=8010,
    )
    voice_live_launchd.write_plist(plist_path, payload)
    monkeypatch.setattr(voice_live_launchd, "plist_path_for_label", lambda label: plist_path)
    monkeypatch.setattr(voice_live_launchd, "is_loaded", lambda label: True)

    status = voice_live_launchd.status()

    assert status["installed"] is True
    assert status["loaded"] is True
    assert status["host"] == "127.0.0.1"
    assert status["port"] == 8010
    assert status["environment_managed"] is True
    assert status["pythonpath_managed"] is True


def test_voice_launchd_install_syncs_env_before_loading(tmp_path, monkeypatch):
    calls: list[str] = []
    plist_path = tmp_path / "voice.plist"
    monkeypatch.setattr(voice_live_launchd, "sync_launchd_env", lambda: calls.append("sync"))
    monkeypatch.setattr(voice_live_launchd, "plist_path_for_label", lambda label: plist_path)
    monkeypatch.setattr(voice_live_launchd, "is_loaded", lambda label: False)
    monkeypatch.setattr(voice_live_launchd, "bootstrap", lambda path: calls.append(f"load:{path}"))
    monkeypatch.setattr(voice_live_launchd, "LOG_DIR", tmp_path / "logs")
    args = argparse.Namespace(
        label=voice_live_launchd.DEFAULT_LABEL,
        python_path=tmp_path / "python",
        host="127.0.0.1",
        port=8010,
        load=True,
    )

    path = voice_live_launchd.install(args)

    assert path == plist_path
    assert calls == ["sync", f"load:{plist_path}"]
    assert plist_path.exists()
