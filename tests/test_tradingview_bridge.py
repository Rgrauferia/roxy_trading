from tools import tradingview_bridge


def test_tradingview_bridge_urls_are_fixed_to_local_bridge():
    assert tradingview_bridge.bridge_url() == "http://127.0.0.1:8001"
    assert tradingview_bridge.health_url() == "http://127.0.0.1:8001/health"


def test_tradingview_bridge_reuses_running_service(monkeypatch):
    monkeypatch.setattr(tradingview_bridge, "bridge_health_ok", lambda port, host: True)

    result = tradingview_bridge.ensure_tradingview_bridge(env={})

    assert result == 0


def test_tradingview_bridge_requires_secret_before_start(monkeypatch):
    monkeypatch.setattr(tradingview_bridge, "bridge_health_ok", lambda port, host: False)

    result = tradingview_bridge.ensure_tradingview_bridge(env={})

    assert result == 2


def test_tradingview_bridge_starts_admin_api_on_fixed_port(monkeypatch):
    calls = {}

    class Result:
        returncode = 0

    def fake_run(command, env, check):
        calls["command"] = command
        calls["env"] = env
        calls["check"] = check
        return Result()

    monkeypatch.setattr(tradingview_bridge, "bridge_health_ok", lambda port, host: False)
    monkeypatch.setattr(tradingview_bridge.subprocess, "run", fake_run)
    monkeypatch.setattr(tradingview_bridge.sys, "executable", "/python")

    result = tradingview_bridge.ensure_tradingview_bridge(env={"TRADINGVIEW_WEBHOOK_SECRET": "secret"})

    assert result == 0
    assert calls["command"] == ["/python", "tools/admin_api.py"]
    assert calls["env"]["ADMIN_API_PORT"] == "8001"
    assert calls["env"]["TRADINGVIEW_WEBHOOK_SECRET"] == "secret"
