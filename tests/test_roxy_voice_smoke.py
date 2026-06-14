from __future__ import annotations

from urllib.error import URLError

from tools import roxy_voice_smoke


def test_build_targets_normalizes_voice_base_url():
    targets = roxy_voice_smoke.build_targets(
        voice_base="http://127.0.0.1:8010/",
        trade_url="http://127.0.0.1:8501/?view=Activo",
    )

    assert [target.name for target in targets] == ["health", "roxy_live", "sessions", "trade_dashboard"]
    assert targets[0].url == "http://127.0.0.1:8010/health"
    assert targets[1].url == "http://127.0.0.1:8010/roxy-live"
    assert targets[2].url == "http://127.0.0.1:8010/v1/assist/sessions?language=es&limit=1"
    assert targets[3].url == "http://127.0.0.1:8501/?view=Activo"


def test_run_smoke_passes_with_expected_roxy_responses(monkeypatch):
    def fake_fetch_url(url: str, timeout: float = 5.0):
        if url.endswith("/health"):
            return 200, '{"status":"ok"}', 1.2
        if url.endswith("/roxy-live"):
            return 200, "<html><title>Roxy Live</title></html>", 2.3
        if "/v1/assist/sessions" in url:
            return (
                200,
                '{"session_count":1,"recent_sessions":[],"suggested_actions":["switch_session"]}',
                1.0,
            )
        return 200, "<html><title>Streamlit</title></html>", 4.0

    monkeypatch.setattr(roxy_voice_smoke, "fetch_url", fake_fetch_url)

    checks = roxy_voice_smoke.run_smoke(
        voice_base="http://voice.local",
        trade_url="http://trade.local",
        timeout=0.1,
    )
    summary = roxy_voice_smoke.summarize_checks(checks)

    assert [check.ok for check in checks] == [True, True, True, True]
    assert summary["ok"] is True
    assert summary["passed"] == 4
    assert summary["failed"] == 0


def test_run_check_reports_down_service(monkeypatch):
    def fake_fetch_url(url: str, timeout: float = 5.0):
        raise URLError("connection refused")

    monkeypatch.setattr(roxy_voice_smoke, "fetch_url", fake_fetch_url)

    check = roxy_voice_smoke.run_check(
        roxy_voice_smoke.SmokeTarget("health", "http://127.0.0.1:8010/health"),
        timeout=0.1,
    )

    assert check.ok is False
    assert check.status_code is None
    assert "connection refused" in check.detail


def test_main_returns_failure_when_any_check_fails(monkeypatch, capsys):
    checks = [
        roxy_voice_smoke.SmokeCheck("health", "http://voice.local/health", True, 200, "ok", 1.0),
        roxy_voice_smoke.SmokeCheck("trade_dashboard", "http://trade.local", False, 500, "bad", 1.0),
    ]
    monkeypatch.setattr(roxy_voice_smoke, "run_smoke", lambda **kwargs: checks)

    exit_code = roxy_voice_smoke.main(["--json"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '"ok": false' in captured.out
    assert '"failed": 1' in captured.out
