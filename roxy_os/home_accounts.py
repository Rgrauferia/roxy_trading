from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


ACCOUNT_STORE_VERSION = 1
PASSWORD_ITERATIONS = 600_000
MEMBER_THEMES = {"classic", "olive", "coastal", "terracotta"}
MEMBER_BACKGROUNDS = {"plant", "linen", "clean", "warm"}
MEMBER_AVATARS = {"home", "professional", "monogram"}
MEMBER_RESPONSE_STYLES = {"balanced", "brief", "close", "explanatory"}
MEMBER_TEXT_SCALES = {"compact", "standard", "large"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_username(value: Any) -> str:
    username = re.sub(r"[^a-z0-9_.@-]+", "", str(value or "").strip().lower())
    if not 3 <= len(username) <= 64:
        raise ValueError("El usuario debe tener entre 3 y 64 caracteres.")
    return username


def normalize_display_name(value: Any) -> str:
    name = " ".join(str(value or "").strip().split())
    if not 1 <= len(name) <= 64:
        raise ValueError("El nombre debe tener entre 1 y 64 caracteres.")
    return name


def validate_password(value: Any) -> str:
    password = str(value or "")
    if not 8 <= len(password) <= 128:
        raise ValueError("La contraseña debe tener entre 8 y 128 caracteres.")
    return password


def default_member_preferences() -> dict[str, str]:
    return {
        "theme": "classic",
        "background": "plant",
        "avatar": "home",
        "response_style": "balanced",
        "text_scale": "standard",
    }


def normalize_member_preferences(values: Any) -> dict[str, str]:
    source = values if isinstance(values, dict) else {}
    result = default_member_preferences()
    allowed = {
        "theme": MEMBER_THEMES,
        "background": MEMBER_BACKGROUNDS,
        "avatar": MEMBER_AVATARS,
        "response_style": MEMBER_RESPONSE_STYLES,
        "text_scale": MEMBER_TEXT_SCALES,
    }
    for key, choices in allowed.items():
        value = str(source.get(key) or result[key]).strip().lower()
        if value not in choices:
            raise ValueError(f"La preferencia {key} no es válida.")
        result[key] = value
    return result


def hash_password(password: Any) -> str:
    value = validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode(), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode().rstrip("="),
        base64.urlsafe_b64encode(digest).decode().rstrip("="),
    )


def verify_password(password: Any, encoded: Any) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = str(encoded or "").split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(raw_iterations)
        if not 100_000 <= iterations <= 1_000_000:
            return False
        salt = base64.urlsafe_b64decode(raw_salt + "=" * (-len(raw_salt) % 4))
        expected = base64.urlsafe_b64decode(raw_digest + "=" * (-len(raw_digest) % 4))
        candidate = hashlib.pbkdf2_hmac("sha256", str(password or "").encode(), salt, iterations)
        return hmac.compare_digest(candidate, expected)
    except (TypeError, ValueError):
        return False


def public_member(member: dict[str, Any], household: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": member["id"],
        "username": member["username"],
        "display_name": member["display_name"],
        "role": member["role"],
        "household_id": household["id"],
        "household_name": household["name"],
        "storage_user_id": household["storage_user_id"],
        "active": bool(member.get("active", True)),
        "preferences": normalize_member_preferences(member.get("preferences")),
    }


class HomeAccountStore:
    """Durable Home identities layered over one shared household namespace."""

    def __init__(self, path: str | Path = "data/roxy_home_accounts.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"schema_version": ACCOUNT_STORE_VERSION, "households": {}, "members": {}}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(payload, dict):
            return self._empty()
        payload["schema_version"] = ACCOUNT_STORE_VERSION
        if not isinstance(payload.get("households"), dict):
            payload["households"] = {}
        if not isinstance(payload.get("members"), dict):
            payload["members"] = {}
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = ACCOUNT_STORE_VERSION
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _mutate(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                self.lock_path.chmod(0o600)
            except OSError:
                pass
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read_unlocked()
                result = callback(payload)
                self._write_unlocked(payload)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def household_configured(self, storage_user_id: str) -> bool:
        return any(
            row.get("storage_user_id") == storage_user_id
            for row in self._read_unlocked().get("households", {}).values()
        )

    def bootstrap(
        self,
        storage_user_id: str,
        *,
        household_name: Any,
        username: Any,
        display_name: Any,
        password: Any,
    ) -> dict[str, Any]:
        normalized_username = normalize_username(username)
        normalized_name = normalize_display_name(display_name)
        normalized_household = normalize_display_name(household_name)
        encoded_password = hash_password(password)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if any(row.get("storage_user_id") == storage_user_id for row in payload["households"].values()):
                raise ValueError("Este hogar ya tiene perfiles configurados.")
            if any(row.get("username") == normalized_username for row in payload["members"].values()):
                raise ValueError("Ese usuario ya existe.")
            household_id = str(uuid4())
            member_id = str(uuid4())
            household = {
                "id": household_id,
                "name": normalized_household,
                "storage_user_id": storage_user_id,
                "created_at": _now_iso(),
            }
            member = {
                "id": member_id,
                "household_id": household_id,
                "username": normalized_username,
                "display_name": normalized_name,
                "password_hash": encoded_password,
                "role": "OWNER",
                "active": True,
                "preferences": default_member_preferences(),
                "created_at": _now_iso(),
            }
            payload["households"][household_id] = household
            payload["members"][member_id] = member
            return public_member(member, household)

        return self._mutate(apply)

    def authenticate(self, username: Any, password: Any) -> dict[str, Any] | None:
        try:
            normalized = normalize_username(username)
        except ValueError:
            normalized = "invalid-user"
        payload = self._read_unlocked()
        member = next((row for row in payload["members"].values() if row.get("username") == normalized), None)
        encoded = member.get("password_hash") if member else "pbkdf2_sha256$600000$MDAwMDAwMDAwMDAwMDAwMA$MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA"
        valid = verify_password(password, encoded)
        if not member or not valid or not member.get("active", True):
            return None
        household = payload["households"].get(member.get("household_id"))
        return public_member(member, household) if household else None

    def member(self, member_id: str) -> dict[str, Any] | None:
        payload = self._read_unlocked()
        member = payload["members"].get(str(member_id))
        household = payload["households"].get(member.get("household_id")) if member else None
        return public_member(member, household) if member and household and member.get("active", True) else None

    def members(self, member_id: str) -> list[dict[str, Any]]:
        current = self.member(member_id)
        if current is None:
            raise KeyError(member_id)
        payload = self._read_unlocked()
        household = payload["households"][current["household_id"]]
        rows = [
            public_member(member, household)
            for member in payload["members"].values()
            if member.get("household_id") == current["household_id"] and member.get("active", True)
        ]
        return sorted(rows, key=lambda row: (row["role"] != "OWNER", row["display_name"].lower()))

    def add_member(
        self,
        actor_member_id: str,
        *,
        username: Any,
        display_name: Any,
        password: Any,
    ) -> dict[str, Any]:
        normalized_username = normalize_username(username)
        normalized_name = normalize_display_name(display_name)
        encoded_password = hash_password(password)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            actor = payload["members"].get(actor_member_id)
            if not actor or not actor.get("active", True) or actor.get("role") != "OWNER":
                raise PermissionError("Solo la persona administradora puede añadir miembros.")
            if any(row.get("username") == normalized_username for row in payload["members"].values()):
                raise ValueError("Ese usuario ya existe.")
            household = payload["households"].get(actor.get("household_id"))
            if household is None:
                raise KeyError(actor.get("household_id"))
            member_id = str(uuid4())
            member = {
                "id": member_id,
                "household_id": household["id"],
                "username": normalized_username,
                "display_name": normalized_name,
                "password_hash": encoded_password,
                "role": "MEMBER",
                "active": True,
                "preferences": default_member_preferences(),
                "created_at": _now_iso(),
            }
            payload["members"][member_id] = member
            return public_member(member, household)

        return self._mutate(apply)

    def update_personalization(
        self,
        member_id: str,
        *,
        display_name: Any,
        preferences: dict[str, Any],
        household_name: Any | None = None,
    ) -> dict[str, Any]:
        normalized_name = normalize_display_name(display_name)
        normalized_preferences = normalize_member_preferences(preferences)
        requested_household_name = None if household_name is None else normalize_display_name(household_name)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            member = payload["members"].get(member_id)
            if not member or not member.get("active", True):
                raise KeyError(member_id)
            household = payload["households"].get(member.get("household_id"))
            if household is None:
                raise KeyError(member.get("household_id"))
            if requested_household_name is not None and requested_household_name != household.get("name"):
                if member.get("role") != "OWNER":
                    raise PermissionError("Solo la persona administradora puede cambiar el nombre del hogar.")
                household["name"] = requested_household_name
                household["updated_at"] = _now_iso()
            member["display_name"] = normalized_name
            member["preferences"] = normalized_preferences
            member["updated_at"] = _now_iso()
            return public_member(member, household)

        return self._mutate(apply)
