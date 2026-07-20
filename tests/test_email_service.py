import requests

from roxy_os.email_service import GmailReadonlyClient, OutlookReadonlyClient, readonly_email_client


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


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


def test_gmail_reports_not_configured_without_network():
    session = Session([])
    result = GmailReadonlyClient("", session=session).status()
    assert result["status"] == "SERVICE_NOT_CONFIGURED"
    assert result["send_enabled"] is False
    assert session.calls == []


def test_gmail_status_never_returns_token():
    session = Session([Response(payload={"emailAddress": "user@example.com", "messagesTotal": 4, "threadsTotal": 3})])
    result = GmailReadonlyClient("secret-token", session=session).status()
    assert result["status"] == "CONNECTED"
    assert result["account"] == "user@example.com"
    assert "secret-token" not in str(result)


def test_gmail_inbox_loads_metadata_only_and_caps_limit():
    session = Session([
        Response(payload={"messages": [{"id": "m1", "threadId": "t1"}], "resultSizeEstimate": 20}),
        Response(payload={
            "id": "m1", "threadId": "t1", "labelIds": ["INBOX", "UNREAD"],
            "payload": {"headers": [
                {"name": "From", "value": "Sender <s@example.com>"},
                {"name": "Subject", "value": "Resumen"},
                {"name": "Date", "value": "Sun, 20 Jul 2026 01:00:00 +0000"},
                {"name": "Authorization", "value": "hidden"},
            ]},
        }),
    ])
    result = GmailReadonlyClient("token", session=session).inbox(limit=99)
    assert result["status"] == "CONNECTED"
    assert result["messages"][0]["subject"] == "Resumen"
    assert result["messages"][0]["unread"] is True
    assert result["messages"][0]["body_loaded"] is False
    assert "Authorization" not in str(result)
    assert session.calls[0][2]["params"]["maxResults"] == 5
    assert session.calls[1][2]["params"]["format"] == "metadata"


def test_gmail_maps_auth_rate_limit_and_timeout():
    assert GmailReadonlyClient("x", session=Session([Response(401)])).status()["status"] == "AUTH_INVALID"
    assert GmailReadonlyClient("x", session=Session([Response(429)])).status()["status"] == "RATE_LIMITED"
    assert GmailReadonlyClient("x", session=Session([requests.Timeout()])).status()["status"] == "UNAVAILABLE"


def test_gmail_skips_untrusted_message_identifiers_without_extra_request():
    session = Session([Response(payload={"messages": [{"id": "../profile?fields=token"}]})])
    result = GmailReadonlyClient("token", session=session).inbox()
    assert result["status"] == "CONNECTED"
    assert result["messages"] == []
    assert len(session.calls) == 1


def test_gmail_send_is_always_disabled_without_network():
    session = Session([])
    result = GmailReadonlyClient("token", session=session).send(to="x@example.com", subject="x", body="x")
    assert result == {
        "status": "SEND_DISABLED",
        "sent": False,
        "detail": "Roxy no envia correo desde este adaptador de solo lectura.",
    }
    assert session.calls == []


def test_outlook_reports_not_configured_without_network():
    session = Session([])
    result = OutlookReadonlyClient("", session=session).inbox()
    assert result["status"] == "SERVICE_NOT_CONFIGURED"
    assert result["send_enabled"] is False
    assert session.calls == []


def test_outlook_status_and_inbox_use_fixed_metadata_only_graph_fields():
    session = Session([
        Response(payload={"displayName": "R User", "mail": "r@example.com"}),
        Response(payload={"value": [{
            "id": "m1", "conversationId": "c1", "subject": "Resumen",
            "receivedDateTime": "2026-07-20T01:00:00Z", "isRead": False,
            "categories": ["Trabajo"],
            "from": {"emailAddress": {"name": "Sender", "address": "s@example.com"}},
            "body": {"content": "must never be selected or returned"},
        }]}),
    ])
    client = OutlookReadonlyClient("secret-graph-token", session=session)

    status = client.status()
    inbox = client.inbox(limit=99)

    assert status["status"] == "CONNECTED"
    assert status["account"] == "r@example.com"
    assert inbox["messages"][0]["subject"] == "Resumen"
    assert inbox["messages"][0]["unread"] is True
    assert inbox["messages"][0]["body_loaded"] is False
    assert "must never" not in str(inbox)
    assert "secret-graph-token" not in str(status) + str(inbox)
    assert session.calls[1][2]["params"]["$top"] == 5
    assert "body" not in session.calls[1][2]["params"]["$select"]
    assert session.calls[1][0] == "GET"


def test_outlook_maps_errors_and_never_sends():
    assert OutlookReadonlyClient("x", session=Session([Response(403)])).status()["status"] == "AUTH_INVALID"
    assert OutlookReadonlyClient("x", session=Session([Response(429)])).status()["status"] == "RATE_LIMITED"
    assert OutlookReadonlyClient("x", session=Session([requests.Timeout()])).status()["status"] == "UNAVAILABLE"
    session = Session([])
    assert OutlookReadonlyClient("x", session=session).send()["status"] == "SEND_DISABLED"
    assert session.calls == []


def test_readonly_email_factory_fails_safe_to_supported_provider():
    assert isinstance(readonly_email_client("outlook", token=""), OutlookReadonlyClient)
    assert isinstance(readonly_email_client("unknown", token=""), GmailReadonlyClient)
