import json
from urllib.parse import parse_qs, urlparse

from roxy_os.home_calendar_google import GoogleCalendarConfig, GoogleCalendarSync


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {}
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse({"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_in": 3600})

    def put(self, url, **kwargs):
        self.calls.append(("PUT", url, kwargs))
        return FakeResponse({"id": url.rsplit("/", 1)[-1]})

    def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url, kwargs))
        return FakeResponse(status_code=204)


def config(tmp_path):
    return GoogleCalendarConfig(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://roxy.test/v1/home-calendar/google/callback",
        encryption_key="a-private-server-key",
        store_path=tmp_path / "sync.json",
        authorization_url="https://google.test/auth",
        token_url="https://google.test/token",
        api_base_url="https://google.test/calendar/v3",
    )


def event_payload():
    return {
        "id": "abcdef0123456789abcdef0123456789",
        "title": "Dentista",
        "starts_at": "2026-08-31T10:00:00-04:00",
        "ends_at": "2026-08-31T11:00:00-04:00",
        "timezone": "America/New_York",
        "reminder_minutes": 60,
        "notes": "Limpieza",
        "location": "Clínica",
        "participants": [],
        "recurrence": "NONE",
    }


def test_oauth_tokens_are_encrypted_and_state_is_one_time(tmp_path):
    session = FakeSession()
    google = GoogleCalendarSync(config(tmp_path), session=session)
    url = google.authorization_url("member:robert")
    state = parse_qs(urlparse(url).query)["state"][0]

    assert google.exchange_code(state, "oauth-code") == "member:robert"
    stored = config(tmp_path).store_path.read_text()
    assert "access-secret" not in stored
    assert "refresh-secret" not in stored
    assert google.status("member:robert")["connected"] is True

    try:
        google.exchange_code(state, "another-code")
    except ValueError:
        pass
    else:
        raise AssertionError("OAuth state must be single-use")


def test_event_sync_uses_exact_payload_reminder_and_mapping(tmp_path):
    session = FakeSession()
    google = GoogleCalendarSync(config(tmp_path), session=session)
    state = parse_qs(urlparse(google.authorization_url("member:robert")).query)["state"][0]
    google.exchange_code(state, "oauth-code")

    result = google.upsert_event("member:robert", event_payload())
    put = next(call for call in session.calls if call[0] == "PUT")

    assert result["synced"] is True
    assert put[2]["json"]["summary"] == "Dentista"
    assert put[2]["json"]["reminders"]["overrides"] == [{"method": "popup", "minutes": 60}]
    assert "/calendars/primary/events/roabcdef" in put[1]
    assert "access-secret" not in json.dumps(google._read())

    deleted = google.delete_event("member:robert", event_payload()["id"])
    assert deleted["synced"] is True
    assert any(call[0] == "DELETE" for call in session.calls)


def test_status_requires_a_token_decryptable_with_current_server_key(tmp_path):
    original = GoogleCalendarSync(config(tmp_path), session=FakeSession())
    state = parse_qs(urlparse(original.authorization_url("member:robert")).query)["state"][0]
    original.exchange_code(state, "oauth-code")
    rotated = GoogleCalendarSync(
        GoogleCalendarConfig(
            **{**config(tmp_path).__dict__, "encryption_key": "a-different-private-server-key"}
        ),
        session=FakeSession(),
    )

    status = rotated.status("member:robert")

    assert status["configured"] is True
    assert status["connected"] is False
    assert status["reconnect_required"] is True
    assert "Vuelve a conectar" in status["message"]
