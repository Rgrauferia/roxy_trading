from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from roxy_os.home_calendar import HomeCalendarStore, parse_calendar_command


def event_payload(**overrides):
    payload = {
        "title": "Llamada del trabajo",
        "starts_at": "2026-08-24T17:00:00-04:00",
        "ends_at": "2026-08-24T18:00:00-04:00",
        "timezone": "America/New_York",
        "category": "WORK",
        "reminder_minutes": 60,
        "location": "",
        "notes": "Revisión del proyecto",
        "participants": [],
        "recurrence": "NONE",
        "recurrence_until": None,
        "all_day": False,
    }
    payload.update(overrides)
    return payload


def test_calendar_store_requires_confirmation_and_exports_native_ics(tmp_path):
    store = HomeCalendarStore(tmp_path / "calendar.json")
    draft = store.save_draft("member:robert", event_payload())

    assert store.list_events(
        "member:robert",
        start="2026-08-24T00:00:00-04:00",
        end="2026-08-25T00:00:00-04:00",
    ) == []

    event = store.confirm_draft("member:robert", draft["id"])
    rows = store.list_events(
        "member:robert",
        start="2026-08-24T00:00:00-04:00",
        end="2026-08-25T00:00:00-04:00",
    )
    ics = store.export_ics("member:robert", event["id"])

    assert rows[0]["title"] == "Llamada del trabajo"
    assert store.list_events(
        "member:otra-persona",
        start="2026-08-24T00:00:00-04:00",
        end="2026-08-25T00:00:00-04:00",
    ) == []
    assert "BEGIN:VCALENDAR" in ics
    assert "BEGIN:VALARM" in ics
    assert "TRIGGER:-PT60M" in ics


def test_calendar_store_expands_weekday_recurrence_and_detects_conflicts(tmp_path):
    store = HomeCalendarStore(tmp_path / "calendar.json")
    recurring = event_payload(
        title="Llevar a los niños a la escuela",
        starts_at="2026-08-24T07:30:00-04:00",
        ends_at="2026-08-24T08:00:00-04:00",
        recurrence="WEEKDAYS",
        recurrence_until="2026-08-28",
        category="SCHOOL",
    )
    store.create("member:robert", recurring)
    rows = store.list_events(
        "member:robert",
        start="2026-08-24T00:00:00-04:00",
        end="2026-08-31T00:00:00-04:00",
    )
    conflicts = store.conflicts(
        "member:robert",
        event_payload(
            title="Otra cita",
            starts_at="2026-08-25T07:45:00-04:00",
            ends_at="2026-08-25T08:15:00-04:00",
        ),
    )

    assert len(rows) == 5
    assert conflicts[0]["title"] == "Llevar a los niños a la escuela"


def test_spanish_calendar_parser_understands_confirmation_details_and_recurrence():
    current = datetime.fromisoformat("2026-08-23T10:00:00-04:00")
    parsed = parse_calendar_command(
        "Roxy, agrega una llamada del trabajo el lunes 24 a las 5:00 p. m. y recuérdame una hora antes",
        current=current,
    )
    recurring = parse_calendar_command(
        "Llevar a los niños a la escuela de lunes a viernes a las 7:30 a. m.",
        current=current,
    )

    assert parsed["starts_at"].startswith("2026-08-24T17:00:00")
    assert parsed["category"] == "WORK"
    assert parsed["reminder_minutes"] == 60
    assert recurring["recurrence"] == "WEEKDAYS"
    assert recurring["needs_clarification"] is True


def test_calendar_parser_removes_voice_controls_from_professional_title():
    current = datetime.fromisoformat("2026-08-24T10:00:00-04:00")

    work = parse_calendar_command(
        "Roxy, pon en el calendario que hoy trabajo a las 2:00 p. m.",
        current=current,
    )
    appointment = parse_calendar_command(
        "Agrega al calendario una cita con el dentista mañana a las 10:30 a. m.",
        current=current,
    )

    assert work["title"] == "Trabajo"
    assert work["category"] == "WORK"
    assert work["starts_at"].startswith("2026-08-24T14:00:00")
    assert appointment["title"] == "Cita con el dentista"
    assert appointment["category"] == "APPOINTMENTS"


def test_calendar_api_and_voice_are_private_and_persistent(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "calendar-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_CALENDAR_PATH", str(tmp_path / "calendar.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    client.post("/v1/shopping/session/robert", headers={"Authorization": "Bearer calendar-test-key"})

    proposal = client.post(
        "/v1/assistant/command/robert",
        json={"text": "programa una llamada del trabajo el lunes 24 a las 5:00 p. m. y recuérdame una hora antes"},
    )
    before = client.get(
        "/v1/home-calendar/robert",
        params={"start": "2026-08-23T00:00:00-04:00", "end": "2026-08-30T00:00:00-04:00"},
    )
    confirmed = client.post("/v1/assistant/command/robert", json={"text": "sí, confirmo"})
    after = client.get(
        "/v1/home-calendar/robert",
        params={"start": "2026-08-23T00:00:00-04:00", "end": "2026-08-30T00:00:00-04:00"},
    )
    forbidden = client.get(
        "/v1/home-calendar/alice",
        params={"start": "2026-08-23T00:00:00-04:00", "end": "2026-08-30T00:00:00-04:00"},
    )

    assert proposal.status_code == 200
    assert proposal.json()["intent"] == "calendar_create"
    assert "¿Lo confirmo?" in proposal.json()["message"]
    assert before.json()["events"] == []
    assert confirmed.status_code == 200
    assert confirmed.json()["intent"] == "calendar_confirm"
    assert after.json()["events"][0]["title"].lower().startswith("llamada del trabajo")
    assert forbidden.status_code == 403

    cancel_proposal = client.post(
        "/v1/assistant/command/robert",
        json={"text": "cancela la llamada del trabajo"},
    )
    still_present = client.get(
        "/v1/home-calendar/robert",
        params={"start": "2026-08-23T00:00:00-04:00", "end": "2026-08-30T00:00:00-04:00"},
    )
    cancel_confirmed = client.post("/v1/assistant/command/robert", json={"text": "sí, confirmo"})
    removed = client.get(
        "/v1/home-calendar/robert",
        params={"start": "2026-08-23T00:00:00-04:00", "end": "2026-08-30T00:00:00-04:00"},
    )

    assert cancel_proposal.json()["intent"] == "calendar_cancel"
    assert len(still_present.json()["events"]) == 1
    assert cancel_confirmed.json()["intent"] == "calendar_confirm"
    assert removed.json()["events"] == []
def test_calendar_sentences_never_become_shopping_items(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "calendar-routing-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_CALENDAR_PATH", str(tmp_path / "calendar.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_CONVERSATION_PATH", str(tmp_path / "conversation.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    client.post("/v1/shopping/session/robert", headers={"Authorization": "Bearer calendar-routing-key"})

    veterinarian = client.post(
        "/v1/assistant/command/robert",
        json={"text": "agrega al calendario que mañana tengo que llevar a Bella al veterinario a las 2:00 p. m."},
    )
    work = client.post(
        "/v1/assistant/command/robert",
        json={"text": "evento en calendario: mañana a las 2:00 p. m. tengo que trabajar"},
    )
    shopping = client.get("/v1/shopping/robert")

    assert veterinarian.status_code == 200
    assert veterinarian.json()["intent"] == "calendar_create"
    assert "veterinario" in veterinarian.json()["data"]["calendar_draft"]["title"].lower()
    assert work.status_code == 200
    assert work.json()["intent"] == "calendar_create"
    assert shopping.json()["items"] == []
