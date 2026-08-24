from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"


@dataclass(frozen=True)
class GoogleCalendarConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    encryption_key: str
    store_path: Path
    authorization_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url: str = "https://oauth2.googleapis.com/token"
    api_base_url: str = "https://www.googleapis.com/calendar/v3"

    @classmethod
    def from_env(cls) -> "GoogleCalendarConfig":
        return cls(
            client_id=str(os.getenv("ROXY_HOME_GOOGLE_CALENDAR_CLIENT_ID") or "").strip(),
            client_secret=str(os.getenv("ROXY_HOME_GOOGLE_CALENDAR_CLIENT_SECRET") or "").strip(),
            redirect_uri=str(os.getenv("ROXY_HOME_GOOGLE_CALENDAR_REDIRECT_URI") or "https://roxy-home.onrender.com/v1/home-calendar/google/callback").strip(),
            encryption_key=str(os.getenv("ROXY_HOME_CALENDAR_ENCRYPTION_KEY") or "").strip(),
            store_path=Path(os.getenv("ROXY_HOME_CALENDAR_SYNC_PATH", "data/roxy_home_calendar_sync.json")),
            authorization_url=str(os.getenv("ROXY_HOME_GOOGLE_AUTHORIZATION_URL") or "https://accounts.google.com/o/oauth2/v2/auth").strip(),
            token_url=str(os.getenv("ROXY_HOME_GOOGLE_TOKEN_URL") or "https://oauth2.googleapis.com/token").strip(),
            api_base_url=str(os.getenv("ROXY_HOME_GOOGLE_CALENDAR_API_URL") or "https://www.googleapis.com/calendar/v3").rstrip("/"),
        )

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri and self.encryption_key)


class GoogleCalendarSync:
    """One-way Roxy -> Google Calendar sync with encrypted per-member tokens."""

    def __init__(self, config: GoogleCalendarConfig | None = None, *, session: Any = requests) -> None:
        self.config = config or GoogleCalendarConfig.from_env()
        self.session = session
        self.lock_path = self.config.store_path.with_suffix(self.config.store_path.suffix + ".lock")
        key = hashlib.sha256(self.config.encryption_key.encode("utf-8")).digest()
        self.cipher = AESGCM(key)

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"version": 1, "states": {}, "connections": {}}

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.config.store_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty()
        return value if isinstance(value, dict) else self._empty()

    def _write(self, value: dict[str, Any]) -> None:
        self.config.store_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.config.store_path.name}.", dir=str(self.config.store_path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush(); os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.config.store_path)
        finally:
            try: os.unlink(temp_name)
            except FileNotFoundError: pass

    def _mutate(self, callback):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            os.chmod(self.lock_path, 0o600)
            if fcntl is not None: fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                value = self._read(); result = callback(value); self._write(value); return result
            finally:
                if fcntl is not None: fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _seal(self, owner: str, token: dict[str, Any]) -> str:
        nonce = os.urandom(12)
        encrypted = self.cipher.encrypt(nonce, json.dumps(token).encode(), owner.encode())
        return base64.urlsafe_b64encode(nonce + encrypted).decode()

    def _open(self, owner: str, value: str) -> dict[str, Any]:
        raw = base64.urlsafe_b64decode(value.encode())
        return json.loads(self.cipher.decrypt(raw[:12], raw[12:], owner.encode()).decode())

    def status(self, owner: str) -> dict[str, Any]:
        connection = self._read().get("connections", {}).get(str(owner)) or {}
        connected = bool(self.config.configured and connection.get("token"))
        return {
            "configured": self.config.configured,
            "connected": connected,
            "provider": "Google Calendar",
            "last_synced_at": connection.get("last_synced_at"),
            "message": "Google Calendar está conectado y enviará los avisos al teléfono." if connected else ("Conecta Google Calendar una sola vez para recibir avisos sin abrir Roxy." if self.config.configured else "La conexión con Google Calendar necesita configuración del servidor."),
        }

    def authorization_url(self, owner: str) -> str:
        if not self.config.configured:
            raise RuntimeError("Google Calendar no está configurado.")
        state = secrets.token_urlsafe(32)
        digest = hashlib.sha256(state.encode()).hexdigest()
        self._mutate(lambda value: value.setdefault("states", {}).__setitem__(digest, {"owner": str(owner), "expires_at": int(time.time()) + 600}))
        params = {"client_id": self.config.client_id, "redirect_uri": self.config.redirect_uri, "response_type": "code", "scope": GOOGLE_CALENDAR_SCOPE, "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state}
        return f"{self.config.authorization_url}?{urlencode(params)}"

    def _consume_state(self, state: str) -> str:
        digest = hashlib.sha256(str(state).encode()).hexdigest()
        def consume(value): return value.setdefault("states", {}).pop(digest, None)
        row = self._mutate(consume)
        if not row or int(row.get("expires_at") or 0) < int(time.time()):
            raise ValueError("La autorización expiró o ya fue utilizada.")
        return str(row["owner"])

    def exchange_code(self, state: str, code: str) -> str:
        owner = self._consume_state(state)
        response = self.session.post(self.config.token_url, data={"client_id": self.config.client_id, "client_secret": self.config.client_secret, "code": code, "grant_type": "authorization_code", "redirect_uri": self.config.redirect_uri}, timeout=20)
        response.raise_for_status(); token = response.json()
        token["expires_at"] = int(time.time()) + int(token.get("expires_in") or 3600)
        def save(value):
            current = value.setdefault("connections", {}).get(owner) or {}
            if not token.get("refresh_token") and current.get("token"):
                previous = self._open(owner, current["token"])
                token["refresh_token"] = previous.get("refresh_token")
            value["connections"][owner] = {"token": self._seal(owner, token), "events": current.get("events") or {}, "connected_at": datetime.now(timezone.utc).isoformat()}
        self._mutate(save)
        return owner

    def _access_token(self, owner: str) -> str:
        value = self._read(); connection = value.get("connections", {}).get(owner) or {}
        if not connection.get("token"): raise RuntimeError("Google Calendar no está conectado.")
        token = self._open(owner, connection["token"])
        if int(token.get("expires_at") or 0) > int(time.time()) + 60: return str(token["access_token"])
        response = self.session.post(self.config.token_url, data={"client_id": self.config.client_id, "client_secret": self.config.client_secret, "refresh_token": token.get("refresh_token"), "grant_type": "refresh_token"}, timeout=20)
        response.raise_for_status(); refreshed = response.json(); token.update(refreshed); token["expires_at"] = int(time.time()) + int(refreshed.get("expires_in") or 3600)
        self._mutate(lambda data: data["connections"][owner].__setitem__("token", self._seal(owner, token)))
        return str(token["access_token"])

    @staticmethod
    def _payload(event: dict[str, Any]) -> dict[str, Any]:
        timezone_name = str(event.get("timezone") or "America/New_York")
        result = {"summary": event["title"], "description": event.get("notes") or "Creado por Roxy Home", "location": event.get("location") or "", "start": {"dateTime": event["starts_at"], "timeZone": timezone_name}, "end": {"dateTime": event["ends_at"], "timeZone": timezone_name}, "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": int(event.get("reminder_minutes") or 0)}]}}
        attendees = [{"email": value} for value in event.get("participants") or [] if "@" in value]
        if attendees: result["attendees"] = attendees
        recurrence = str(event.get("recurrence") or "NONE")
        until = str(event.get("recurrence_until") or "").replace("-", "")
        rules = {"DAILY": "FREQ=DAILY", "WEEKLY": "FREQ=WEEKLY", "WEEKDAYS": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"}
        if recurrence in rules: result["recurrence"] = [f"RRULE:{rules[recurrence]};UNTIL={until}T235959Z"]
        return result

    def upsert_event(self, owner: str, event: dict[str, Any]) -> dict[str, Any]:
        if not self.status(owner)["connected"]: return {"synced": False, "reason": "not_connected"}
        token = self._access_token(owner); connection = self._read()["connections"][owner]
        google_id = (connection.get("events") or {}).get(event["id"]) or f"ro{event['id']}"
        url = f"{self.config.api_base_url}/calendars/primary/events/{google_id}"
        response = self.session.put(url, headers={"Authorization": f"Bearer {token}"}, json=self._payload(event), timeout=20)
        response.raise_for_status(); remote = response.json()
        now = datetime.now(timezone.utc).isoformat()
        def save(value):
            row = value["connections"][owner]; row.setdefault("events", {})[event["id"]] = remote.get("id") or google_id; row["last_synced_at"] = now
        self._mutate(save)
        return {"synced": True, "provider": "Google Calendar", "event_id": remote.get("id") or google_id}

    def delete_event(self, owner: str, event_id: str) -> dict[str, Any]:
        connection = self._read().get("connections", {}).get(owner) or {}; google_id = (connection.get("events") or {}).get(event_id)
        if not google_id: return {"synced": False, "reason": "not_mapped"}
        response = self.session.delete(f"{self.config.api_base_url}/calendars/primary/events/{google_id}", headers={"Authorization": f"Bearer {self._access_token(owner)}"}, timeout=20)
        if response.status_code not in (204, 404): response.raise_for_status()
        def remove(value): value["connections"][owner].setdefault("events", {}).pop(event_id, None)
        self._mutate(remove); return {"synced": True, "provider": "Google Calendar"}

    def sync_all(self, owner: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        synced = 0; errors = []
        for event in events:
            try: synced += int(bool(self.upsert_event(owner, event).get("synced")))
            except Exception as exc: errors.append({"event_id": event.get("id"), "error": str(exc)[:240]})
        return {"synced": synced, "errors": errors}

    def disconnect(self, owner: str) -> None:
        self._mutate(lambda value: value.setdefault("connections", {}).pop(str(owner), None))
