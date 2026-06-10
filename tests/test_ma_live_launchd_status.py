import plistlib

from tools.ma_live_launchd import build_plist, status, write_plist


def test_status_returns_structured_plist_info(tmp_path, monkeypatch):
    path = tmp_path / "com.roxy.ma_live.plist"
    plist = build_plist(
        label="com.roxy.ma_live",
        command="echo live --stock-intervals 15m,1h,2h,4h",
        stdout_path="/tmp/ma_live.out",
        stderr_path="/tmp/ma_live.err",
        run_at_load=True,
        keep_alive=True,
    )
    write_plist(path, plist)
    monkeypatch.setattr("tools.ma_live_launchd.plist_path_for_label", lambda label: path)
    monkeypatch.setattr("tools.ma_live_launchd.is_loaded", lambda label: True)

    info = status("com.roxy.ma_live")

    assert info["installed"] is True
    assert info["loaded"] is True
    assert info["keep_alive"] is True
    assert "--stock-intervals 15m,1h,2h,4h" in info["command"]

    with path.open("rb") as fh:
        assert plistlib.load(fh)["KeepAlive"] is True
