"""Consent-based household presence for Roxy Home.

This store keeps consented foreground positions supplied by authenticated
household members.  Browser tracking stops when the page is closed; a future
native collector can write the same position schema after obtaining the
platform's background-location permission.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import secrets
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


PLACE_KINDS = {"HOME": "Casa", "WORK": "Trabajo", "STORE": "Tienda frecuente", "OTHER": "Otro lugar"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _distance_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    d_phi = math.radians(b_lat - a_lat)
    d_lam = math.radians(b_lon - a_lon)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class HomeFamilyStore:
    def __init__(self, path: str | Path = "data/roxy_home_family.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"schema_version": 3, "households": {}, "links": {}}

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._empty()
        return value if isinstance(value, dict) else self._empty()

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _locked(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                value = self._read()
                result = callback(value)
                self._write(value)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _household(value: dict[str, Any], household_id: str) -> dict[str, Any]:
        return value.setdefault("households", {}).setdefault(
            household_id,
            {"members": {}, "directory": {}, "external_members": {}, "invitations": {}, "places": {}, "alerts": []},
        )

    def resolve_household(self, default_household_id: str, member_id: str) -> tuple[str, str]:
        value = self._read()
        linked = str((value.get("links") or {}).get(member_id) or "")
        household = (value.get("households") or {}).get(linked, {})
        if linked and member_id in (household.get("external_members") or {}):
            return linked, "NEXO_ONLY"
        return default_household_id, "HOUSEHOLD"

    def remember_household_members(self, household_id: str, members: list[dict[str, Any]]) -> None:
        def apply(value: dict[str, Any]) -> None:
            directory = self._household(value, household_id).setdefault("directory", {})
            for member in members:
                member_id = str(member.get("id") or "")
                if member_id:
                    directory[member_id] = {
                        "id": member_id,
                        "display_name": _text(member.get("display_name"), 80),
                        "role": _text(member.get("role"), 30),
                        "avatar": _text((member.get("preferences") or {}).get("avatar"), 500),
                        "external": False,
                    }

        self._locked(apply)

    def snapshot(self, household_id: str, members: list[dict[str, Any]], viewer_id: str) -> dict[str, Any]:
        household = self._household(self._read(), household_id)
        presence = household.get("members", {})
        directory = deepcopy(household.get("directory") or {})
        if not directory:
            directory = {str(row.get("id") or ""): row for row in members if row.get("id")}
        directory.update(deepcopy(household.get("external_members") or {}))
        rows = []
        for member in directory.values():
            state = presence.get(str(member.get("id") or ""), {})
            location = deepcopy(state.get("location")) if state.get("sharing_enabled") else None
            rows.append(
                {
                    "id": member.get("id"),
                    "display_name": member.get("display_name"),
                    "role": member.get("role"),
                    "avatar": member.get("avatar") or (member.get("preferences") or {}).get("avatar", ""),
                    "external": bool(member.get("external")),
                    "relationship": _text(member.get("relationship"), 40),
                    "is_viewer": member.get("id") == viewer_id,
                    "sharing_enabled": bool(state.get("sharing_enabled")),
                    "location": location,
                    "status": _text(state.get("status"), 80),
                    "updated_at": state.get("updated_at"),
                }
            )
        return {
            "status": "READY",
            "members": rows,
            "places": sorted(deepcopy(list(household.get("places", {}).values())), key=lambda row: row.get("name", "")),
            "alerts": deepcopy((household.get("alerts") or [])[-10:]),
            "connections": sorted(
                deepcopy(list((household.get("external_members") or {}).values())),
                key=lambda row: row.get("display_name", ""),
            ),
            "invitations": [
                {key: deepcopy(invite.get(key)) for key in ("id", "display_name", "relationship", "status", "expires_at", "created_at")}
                for invite in (household.get("invitations") or {}).values()
                if invite.get("status") == "PENDING"
            ],
            "capabilities": {
                "foreground_location": True,
                "background_tracking": False,
                "route_history": True,
                "speed_while_open": True,
                "driving_reports": False,
                "pet_tag_tracking": False,
            },
            "privacy_notice": "Tu elección permanece activa hasta que la desactives manualmente. Roxy reanuda la actualización cuando abres la aplicación; una web no puede enviar ubicación mientras está completamente cerrada.",
        }

    def create_invitation(
        self, household_id: str, *, actor_id: str, display_name: str, relationship: str
    ) -> dict[str, Any]:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        invite_id = uuid4().hex
        created_at = _now()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        def apply(value: dict[str, Any]) -> None:
            household = self._household(value, household_id)
            household.setdefault("invitations", {})[invite_id] = {
                "id": invite_id,
                "token_hash": token_hash,
                "display_name": _text(display_name, 80) or "Conexión de confianza",
                "relationship": _text(relationship, 40) or "Persona de confianza",
                "status": "PENDING",
                "created_by": actor_id,
                "created_at": created_at,
                "expires_at": expires_at,
            }

        self._locked(apply)
        return {"id": invite_id, "token": token, "display_name": _text(display_name, 80), "relationship": _text(relationship, 40), "expires_at": expires_at}

    def redeem_invitation(self, token: str, member: dict[str, Any]) -> dict[str, Any]:
        digest = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()
        member_id = str(member.get("id") or "")
        if not member_id:
            raise ValueError("Perfil inválido")

        def apply(value: dict[str, Any]) -> dict[str, Any]:
            for household_id, household in (value.get("households") or {}).items():
                for invite in (household.get("invitations") or {}).values():
                    if not secrets.compare_digest(str(invite.get("token_hash") or ""), digest):
                        continue
                    if invite.get("status") != "PENDING":
                        raise ValueError("Esta invitación ya fue utilizada")
                    if datetime.fromisoformat(str(invite["expires_at"]).replace("Z", "+00:00")) < datetime.now(timezone.utc):
                        invite["status"] = "EXPIRED"
                        raise ValueError("Esta invitación expiró")
                    external = {
                        "id": member_id,
                        "display_name": _text(member.get("display_name"), 80) or invite.get("display_name"),
                        "role": "TRUSTED_CONNECTION",
                        "relationship": invite.get("relationship"),
                        "avatar": _text((member.get("preferences") or {}).get("avatar"), 500),
                        "external": True,
                        "joined_at": _now(),
                    }
                    household.setdefault("external_members", {})[member_id] = external
                    value.setdefault("links", {})[member_id] = household_id
                    invite.update({"status": "ACCEPTED", "accepted_by": member_id, "accepted_at": _now()})
                    return {"household_id": household_id, "connection": deepcopy(external), "access_scope": "NEXO_ONLY"}
            raise ValueError("Invitación inválida")

        return self._locked(apply)

    def revoke_connection(self, household_id: str, member_id: str) -> bool:
        def apply(value: dict[str, Any]) -> bool:
            household = self._household(value, household_id)
            removed = household.setdefault("external_members", {}).pop(member_id, None)
            household.setdefault("members", {}).pop(member_id, None)
            if (value.get("links") or {}).get(member_id) == household_id:
                value["links"].pop(member_id, None)
            return removed is not None

        return bool(self._locked(apply))

    def update_location(
        self,
        household_id: str,
        member_id: str,
        *,
        latitude: float,
        longitude: float,
        accuracy_m: float | None,
        altitude_m: float | None = None,
        speed_mps: float | None = None,
        heading_deg: float | None = None,
        recorded_at: str | None = None,
        consent: bool,
        shopping_pending: int = 0,
    ) -> dict[str, Any]:
        if not consent:
            raise PermissionError("Debes autorizar expresamente compartir esta ubicación.")
        latitude = round(float(latitude), 6)
        longitude = round(float(longitude), 6)
        accuracy = round(float(accuracy_m or 0), 1) or None
        if accuracy is not None and accuracy > 5_000:
            raise ValueError("La ubicación es demasiado imprecisa para compartirla.")
        speed = None if speed_mps is None else max(0.0, min(120.0, round(float(speed_mps), 2)))
        heading = None if heading_deg is None else round(float(heading_deg) % 360, 1)
        altitude = None if altitude_m is None else round(float(altitude_m), 1)

        def apply(value: dict[str, Any]) -> dict[str, Any]:
            household = self._household(value, household_id)
            member = household.setdefault("members", {}).setdefault(member_id, {})
            previous = deepcopy(member.get("location"))
            current_place = self._place_for(household, latitude, longitude)
            previous_place = None
            if previous:
                previous_place = self._place_for(household, float(previous["latitude"]), float(previous["longitude"]))
            moment = _now()
            point = {
                "latitude": latitude,
                "longitude": longitude,
                "accuracy_m": accuracy,
                "altitude_m": altitude,
                "speed_mps": speed,
                "heading_deg": heading,
                "recorded_at": _text(recorded_at, 40) or moment,
                "received_at": moment,
                "source": "FOREGROUND_WEB",
            }
            member.update(
                {
                    "sharing_enabled": True,
                    "location": {
                        **point,
                        "shared_at": moment,
                        "place_id": current_place.get("id") if current_place else "",
                        "place_name": current_place.get("name") if current_place else "",
                    },
                    "status": f"En {current_place['name']}" if current_place else "Ubicación compartida ahora",
                    "updated_at": moment,
                }
            )
            history = member.setdefault("history", [])
            if not history or _distance_m(
                float(history[-1]["latitude"]), float(history[-1]["longitude"]), latitude, longitude
            ) >= 5 or speed is not None:
                history.append(point)
            member["history"] = history[-2_000:]
            alert = None
            if previous_place and previous_place.get("kind") == "WORK" and not current_place and shopping_pending > 0:
                alert = {
                    "id": uuid4().hex,
                    "member_id": member_id,
                    "kind": "SHOPPING_AFTER_WORK",
                    "title": "Compras pendientes",
                    "message": f"Tienes {shopping_pending} artículos pendientes ahora que saliste del trabajo.",
                    "created_at": moment,
                }
                household.setdefault("alerts", []).append(alert)
                household["alerts"] = household["alerts"][-50:]
            return {"location": deepcopy(member["location"]), "alert": deepcopy(alert)}

        return self._locked(apply)

    def history(self, household_id: str, member_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        household = self._household(self._read(), household_id)
        member = household.get("members", {}).get(member_id, {})
        if not member.get("sharing_enabled"):
            return []
        return deepcopy((member.get("history") or [])[-max(1, min(int(limit), 2_000)):])

    @staticmethod
    def _place_for(household: dict[str, Any], latitude: float, longitude: float) -> dict[str, Any] | None:
        candidates = []
        for place in household.get("places", {}).values():
            distance = _distance_m(latitude, longitude, float(place["latitude"]), float(place["longitude"]))
            if distance <= float(place.get("radius_m") or 200):
                candidates.append((distance, place))
        return deepcopy(min(candidates, key=lambda row: row[0])[1]) if candidates else None

    def stop_sharing(self, household_id: str, member_id: str) -> None:
        def apply(value: dict[str, Any]) -> None:
            member = self._household(value, household_id).setdefault("members", {}).setdefault(member_id, {})
            member.update({"sharing_enabled": False, "location": None, "history": [], "status": "Ubicación privada", "updated_at": _now()})

        self._locked(apply)

    def save_place(
        self,
        household_id: str,
        *,
        name: str,
        kind: str,
        latitude: float,
        longitude: float,
        radius_m: float,
    ) -> dict[str, Any]:
        kind = str(kind or "OTHER").upper()
        if kind not in PLACE_KINDS:
            raise ValueError("Tipo de lugar inválido")
        place = {
            "id": uuid4().hex,
            "name": _text(name, 60) or PLACE_KINDS[kind],
            "kind": kind,
            "latitude": round(float(latitude), 4),
            "longitude": round(float(longitude), 4),
            "radius_m": max(50, min(1000, round(float(radius_m or 200)))),
            "created_at": _now(),
        }

        def apply(value: dict[str, Any]) -> dict[str, Any]:
            household = self._household(value, household_id)
            household.setdefault("places", {})[place["id"]] = place
            return deepcopy(place)

        return self._locked(apply)

    def delete_place(self, household_id: str, place_id: str) -> bool:
        def apply(value: dict[str, Any]) -> bool:
            return self._household(value, household_id).setdefault("places", {}).pop(place_id, None) is not None

        return bool(self._locked(apply))
