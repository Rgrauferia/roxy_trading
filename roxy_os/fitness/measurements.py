"""Optional, member-private, self-reported measurements; no assessment or advice.

Uses the foundation's verified TLS transaction and member RLS context. Importing
this module neither connects nor provisions storage. Migration 003 is manual.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from .domain import FitnessInputError
from .repository import (FitnessConflict, FitnessConsentRequired, FitnessStorageUnavailable,
                         PostgresFitnessRepository, _dump, _member_id, _mutation_arguments)
from .schemas import FitnessProfileInput, StrictModel

PURPOSE = "fitness_measurements"
CONSENT_VERSION = "fitness-measurements-v1"
TABLES = {"measurements_state", "measurements_idempotency"}
MAX_RECORDS = 500
MAX_VERSION = 2**53 - 1


def _number(value):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Introduce un número finito, sin texto ni valores especiales.")
    return value


def _rounded(value):
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError("El registro necesita un identificador UUID válido.") from None
    return value


class MeasurementWeight(StrictModel):
    unit: Literal["kg", "lb"]
    value: float

    @field_validator("value", mode="before")
    @classmethod
    def finite_number(cls, value):
        return _number(value)

    def kilograms(self):
        return Decimal(str(self.value)) * (Decimal("0.45359237") if self.unit == "lb" else Decimal(1))

    @model_validator(mode="after")
    def technical_bounds(self):
        if not Decimal(1) <= self.kilograms() <= Decimal(1000):
            raise ValueError("Revisa el peso y su unidad; el registro admite entre 1 y 1000 kg o su equivalente.")
        return self


class MeasurementHeightCm(StrictModel):
    unit: Literal["cm"]
    value: float

    @field_validator("value", mode="before")
    @classmethod
    def finite_number(cls, value):
        return _number(value)

    def centimeters(self):
        return Decimal(str(self.value))


class MeasurementHeightFeet(StrictModel):
    unit: Literal["ft_in"]
    feet: int = Field(ge=0, le=9)
    inches: float = Field(ge=0, lt=12)

    @field_validator("inches", mode="before")
    @classmethod
    def finite_number(cls, value):
        return _number(value)

    def centimeters(self):
        return (Decimal(self.feet * 12) + Decimal(str(self.inches))) * Decimal("2.54")


MeasurementHeight = Annotated[MeasurementHeightCm | MeasurementHeightFeet, Field(discriminator="unit")]


class Measurement(StrictModel):
    id: str
    date: str
    timezone: str = "UTC"
    weight: MeasurementWeight | None = None
    height: MeasurementHeight | None = None

    @field_validator("id")
    @classmethod
    def valid_id(cls, value):
        return _uuid(value)

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError()
        except ValueError:
            raise ValueError("Selecciona una fecha válida con formato AAAA-MM-DD.") from None
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        return FitnessProfileInput.known_timezone(value)

    @model_validator(mode="after")
    def valid_measurement(self):
        if self.weight is None and self.height is None:
            raise ValueError("Añade peso, estatura o ambos; el peso es opcional.")
        if date.fromisoformat(self.date) > datetime.now(ZoneInfo(self.timezone)).date():
            raise ValueError("La medición debe ser de hoy o de una fecha anterior.")
        if self.height and not Decimal(30) <= self.height.centimeters() <= Decimal(300):
            raise ValueError("Revisa la estatura y su unidad; el registro admite entre 30 y 300 cm o su equivalente.")
        return self

    def canonical(self):
        return {"weight_kg": _rounded(self.weight.kilograms()) if self.weight else None,
                "height_cm": _rounded(self.height.centimeters()) if self.height else None}


class StoredMeasurement(Measurement):
    weight_kg: float | None
    height_cm: float | None
    recorded_at: str
    updated_at: str

    @field_validator("weight_kg", "height_cm", mode="before")
    @classmethod
    def finite_optional_number(cls, value):
        return None if value is None else _number(value)

    @field_validator("recorded_at", "updated_at")
    @classmethod
    def aware_timestamp(cls, value):
        if datetime.fromisoformat(value).tzinfo is None:
            raise ValueError("El registro necesita una fecha con zona horaria.")
        return value

    @model_validator(mode="after")
    def consistent_storage(self):
        if any(getattr(self, key) != value for key, value in self.canonical().items()):
            raise ValueError("La medida normalizada no coincide con la unidad de entrada.")
        if datetime.fromisoformat(self.updated_at) < datetime.fromisoformat(self.recorded_at):
            raise ValueError("La fecha de edición no puede preceder al registro.")
        return self


class MeasurementConsent(StrictModel):
    purpose: Literal["fitness_measurements"]
    text_version: Literal["fitness-measurements-v1"]
    granted: bool


class MeasurementWrite(StrictModel):
    expected_version: int = Field(ge=0, le=MAX_VERSION)
    measurement: Measurement


class MeasurementConsentWrite(StrictModel):
    expected_version: int = Field(ge=0, le=MAX_VERSION)
    consent: MeasurementConsent


class MeasurementDeleteWrite(StrictModel):
    expected_version: int = Field(ge=0, le=MAX_VERSION)
    confirm_delete: Literal[True]

    @field_validator("confirm_delete", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("Confirma explícitamente que quieres eliminar las mediciones.")
        return value


def _snapshot(row):
    if row is None:
        return {"version": 0, "measurements": [], "consent": None, "updated_at": None}
    try:
        version = row["version"]
        if isinstance(version, bool) or not isinstance(version, int) or not 0 <= version <= MAX_VERSION:
            raise ValueError()
        raw = row["measurements"]
        if not isinstance(raw, list) or len(raw) > MAX_RECORDS:
            raise ValueError()
        measurements = [StoredMeasurement.model_validate(item).model_dump(mode="json") for item in raw]
        if len({item["id"] for item in measurements}) != len(measurements) or len({item["date"] for item in measurements}) != len(measurements):
            raise ValueError()
        consent = row.get("consent")
        if consent is not None:
            parsed = MeasurementConsent.model_validate({key: consent.get(key) for key in ("purpose", "text_version", "granted")})
            recorded_at = consent.get("recorded_at")
            if not isinstance(recorded_at, str) or datetime.fromisoformat(recorded_at).tzinfo is None:
                raise ValueError()
            consent = {**parsed.model_dump(mode="json"), "recorded_at": recorded_at}
        if measurements and (not consent or consent["granted"] is not True):
            raise ValueError()
        updated = row.get("updated_at")
        if isinstance(updated, datetime):
            updated = updated.isoformat()
        if not isinstance(updated, str) or datetime.fromisoformat(updated).tzinfo is None:
            raise ValueError()
        return {"version": version, "measurements": sorted(measurements, key=lambda item: item["date"], reverse=True),
                "consent": consent, "updated_at": updated}
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        raise FitnessStorageUnavailable() from None


class MeasurementsRepository:
    """Independent consent/version; new records require saved adult preferences."""
    def __init__(self, foundation):
        self.foundation = foundation

    @staticmethod
    def available(cursor, *, required=True):
        cursor.execute("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
            pg_catalog.pg_get_userbyid(c.relowner) = current_user AS is_owner
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'roxy_home_fitness'
            AND c.relname IN ('measurements_state', 'measurements_idempotency')""")
        rows = cursor.fetchall()
        if not rows and not required:
            return False
        if {row["relname"] for row in rows} != TABLES or any(
            not row["relrowsecurity"] or not row["relforcerowsecurity"] or row["is_owner"] for row in rows
        ):
            raise FitnessStorageUnavailable()
        return True

    @staticmethod
    def read(cursor, member, *, lock=False):
        cursor.execute("SELECT version, measurements, consent, updated_at FROM roxy_home_fitness.measurements_state WHERE member_id = %s" + (" FOR UPDATE" if lock else ""), (member,))
        snapshot = _snapshot(cursor.fetchone())
        profile = PostgresFitnessRepository._read(cursor, member)["profile"]
        eligible = bool(profile and profile.get("age_band") in {"18_29", "30_44", "45_64", "65_plus"})
        return {**snapshot, "eligible": eligible, "eligibility_reason": None if eligible else "adult_profile_required"}

    def snapshot(self, member):
        with self.foundation._transaction(member) as cursor:
            self.available(cursor)
            return self.read(cursor, member)

    def export_data(self, member):
        return {"format": "roxy-home-fitness-measurements-v1", "exported_at": datetime.now(timezone.utc).isoformat(),
                "data": self.snapshot(member), "scope": "authenticated_member_only", "self_reported_measurements": True}

    def save(self, member, measurement, *, expected_version, idempotency_key):
        parsed = Measurement.model_validate(measurement.model_dump(mode="json") if isinstance(measurement, Measurement) else measurement)
        return self._mutate(member, "measurement", parsed.model_dump(mode="json"), expected_version, idempotency_key)

    def consent(self, member, consent, *, expected_version, idempotency_key):
        parsed = MeasurementConsent.model_validate(consent.model_dump(mode="json") if isinstance(consent, MeasurementConsent) else consent)
        return self._mutate(member, "consent", parsed.model_dump(mode="json"), expected_version, idempotency_key)

    def remove(self, member, measurement_id, *, expected_version, idempotency_key):
        try:
            _uuid(measurement_id)
        except ValueError as exc:
            raise FitnessInputError(str(exc)) from None
        return self._mutate(member, "remove", {"id": measurement_id}, expected_version, idempotency_key)

    def delete_data(self, member, *, expected_version, idempotency_key):
        return self._mutate(member, "delete", None, expected_version, idempotency_key)

    @staticmethod
    def erase_for_member(cursor, member):
        """Same transaction as global erasure; tombstone invalidates first writes."""
        if not MeasurementsRepository.available(cursor, required=False):
            return
        member = _member_id(member)
        cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-measurements:" + member,))
        cursor.execute("INSERT INTO roxy_home_fitness.measurements_state (member_id) VALUES (%s) ON CONFLICT (member_id) DO NOTHING", (member,))
        cursor.execute("UPDATE roxy_home_fitness.measurements_state SET version = version + 1, measurements = '[]'::jsonb, consent = NULL, updated_at = CURRENT_TIMESTAMP WHERE member_id = %s", (member,))
        cursor.execute("DELETE FROM roxy_home_fitness.measurements_idempotency WHERE member_id = %s", (member,))

    def _mutate(self, member, operation, payload, expected_version, key):
        member = _member_id(member)
        _mutation_arguments(expected_version, key)
        digest = hashlib.sha256(_dump({"operation": operation, "expected_version": expected_version, "payload": payload}).encode()).hexdigest()
        with self.foundation._transaction(member) as cursor:
            self.available(cursor)
            # Foundation erasure acquires this lock before the measurements lock.
            # The shared order also prevents preferences changing between the
            # adult eligibility check and a new consent or measurement write.
            cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-fitness:" + member,))
            cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-measurements:" + member,))
            cursor.execute("INSERT INTO roxy_home_fitness.measurements_state (member_id) VALUES (%s) ON CONFLICT (member_id) DO NOTHING", (member,))
            state = self.read(cursor, member, lock=True)
            cursor.execute("SELECT request_hash, response_version FROM roxy_home_fitness.measurements_idempotency WHERE member_id = %s AND request_key = %s", (member, key))
            previous = cursor.fetchone()
            if previous:
                if previous["request_hash"] != digest or previous["response_version"] != state["version"]:
                    raise FitnessConflict("La solicitud ya cambió. Actualiza tus mediciones antes de continuar.")
                return {**state, "idempotent_replay": True}
            if expected_version != state["version"]:
                raise FitnessConflict("Tus mediciones cambiaron en otra sesión. Actualiza antes de guardar.")
            if state["version"] == MAX_VERSION:
                raise FitnessInputError("Se alcanzó el límite de versiones del registro.")
            if (operation == "measurement" or (operation == "consent" and payload["granted"])) and not state["eligible"]:
                raise FitnessInputError("Completa primero tus preferencias de Ejercicio y confirma que tienes 18 años o más.")
            measurements, consent = state["measurements"], state["consent"]
            if operation == "measurement":
                if not consent or consent["granted"] is not True:
                    raise FitnessConsentRequired("Decide primero si quieres guardar tus mediciones personales; puedes usar Ejercicio sin añadirlas.")
                before = next((item for item in measurements if item["id"] == payload["id"]), None)
                if any(item["date"] == payload["date"] and item["id"] != payload["id"] for item in measurements):
                    raise FitnessInputError("Ya hay un registro en esa fecha. Edítalo para corregir o añadir una medida.")
                if before is None and len(measurements) >= MAX_RECORDS:
                    raise FitnessInputError("Puedes guardar hasta 500 registros. Exporta tus mediciones y elimina un registro si quieres añadir otro.")
                stamp = datetime.now(timezone.utc).isoformat()
                entry = {**payload, **Measurement.model_validate(payload).canonical(),
                         "recorded_at": before["recorded_at"] if before else stamp, "updated_at": stamp}
                measurements = [item for item in measurements if item["id"] != payload["id"]] + [entry]
            elif operation == "remove":
                if not any(item["id"] == payload["id"] for item in measurements):
                    raise FitnessInputError("Ese registro ya no existe. Actualiza tus mediciones.")
                measurements = [item for item in measurements if item["id"] != payload["id"]]
            elif operation == "consent":
                consent = {**payload, "recorded_at": datetime.now(timezone.utc).isoformat()}
                if not payload["granted"]:
                    measurements = []
            elif operation == "delete":
                measurements, consent = [], None
            else:
                raise FitnessInputError("Operación no válida.")
            version = state["version"] + 1
            cursor.execute("DELETE FROM roxy_home_fitness.measurements_idempotency WHERE member_id = %s", (member,))
            cursor.execute("UPDATE roxy_home_fitness.measurements_state SET version = %s, measurements = %s::jsonb, consent = %s::jsonb, updated_at = CURRENT_TIMESTAMP WHERE member_id = %s", (version, _dump(measurements), _dump(consent) if consent is not None else None, member))
            cursor.execute("INSERT INTO roxy_home_fitness.measurements_idempotency (member_id, request_key, request_hash, response_version) VALUES (%s, %s, %s, %s)", (member, key, digest, version))
            return self.read(cursor, member)
