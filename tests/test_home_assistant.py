import requests

from roxy_os.home_assistant import HomeAssistantClient, HomeAssistantConfig


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def config(**overrides):
    values = {"base_url": "http://192.168.1.20:8123", "token": "secret", "control_enabled": False}
    values.update(overrides)
    return HomeAssistantConfig(**values)


def test_home_assistant_reports_missing_configuration_without_network():
    session = Session([])
    client = HomeAssistantClient(HomeAssistantConfig("", "", False), session=session)

    result = client.status()

    assert result["status"] == "SERVICE_NOT_CONFIGURED"
    assert result["connected"] is False
    assert session.calls == []


def test_home_assistant_invalid_timeout_env_falls_back(monkeypatch):
    monkeypatch.setenv("ROXY_HOME_ASSISTANT_TIMEOUT", "invalid")
    assert HomeAssistantConfig.from_env().timeout_seconds == 5.0


def test_home_assistant_rejects_insecure_public_http_and_paths():
    public = HomeAssistantClient(config(base_url="http://example.com"), session=Session([])).status()
    path = HomeAssistantClient(config(base_url="https://ha.example.com/api"), session=Session([])).status()

    assert public["status"] == "CONFIGURATION_ERROR"
    assert "https_required" in public["detail"]
    assert path["status"] == "CONFIGURATION_ERROR"


def test_home_assistant_normalizes_readable_entities_without_sensitive_attributes():
    session = Session([Response(payload=[
        {"entity_id": "light.office", "state": "on", "last_updated": "2026-07-20T00:00:00Z", "attributes": {"friendly_name": "Office", "access_token": "never expose"}},
        {"entity_id": "camera.entry", "state": "idle", "attributes": {"friendly_name": "Entry", "entity_picture": "/secret"}},
        {"entity_id": "automation.private", "state": "on", "attributes": {"friendly_name": "Hidden"}},
    ])])

    result = HomeAssistantClient(config(), session=session).entities()

    assert result["status"] == "CONNECTED"
    assert result["entity_count"] == 2
    assert result["entities"][0]["sensitive"] is True
    assert "attributes" not in result["entities"][0]
    assert "access_token" not in str(result)


def test_home_assistant_maps_auth_and_timeout_states():
    auth = HomeAssistantClient(config(), session=Session([Response(401)])).status()
    timeout = HomeAssistantClient(config(), session=Session([requests.Timeout()])).status()

    assert auth["status"] == "AUTH_INVALID"
    assert timeout["status"] == "UNAVAILABLE"


def test_home_assistant_controls_are_fail_closed_until_all_gates_pass():
    disabled = HomeAssistantClient(config(control_enabled=False), session=Session([]))
    enabled_session = Session([Response(payload=[{"entity_id": "light.office"}])])
    enabled = HomeAssistantClient(config(control_enabled=True), session=enabled_session)

    assert disabled.call_service(domain="light", service="turn_off", entity_id="light.office", confirmed=True, permission_granted=True)["status"] == "CONTROL_DISABLED"
    assert enabled.call_service(domain="light", service="turn_off", entity_id="light.office", confirmed=False, permission_granted=True)["status"] == "CONFIRMATION_REQUIRED"
    assert enabled.call_service(domain="lock", service="unlock", entity_id="lock.front", confirmed=True, permission_granted=True)["status"] == "BLOCKED"
    executed = enabled.call_service(domain="light", service="turn_off", entity_id="light.office", confirmed=True, permission_granted=True)

    assert executed["executed"] is True
    assert enabled_session.calls[0][0] == "POST"
    assert enabled_session.calls[0][2]["json"] == {"entity_id": "light.office"}
