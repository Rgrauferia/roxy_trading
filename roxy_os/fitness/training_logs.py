"""Member-private, manually entered training records with separate consent.

No calories, inferred performance, automatic completion or prescribed loads.
Importing does not connect or migrate; storage requires manual migration 004.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import math
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from .activity_plan import ActivityPlanRepository, session_instant
from .domain import FitnessInputError
from .repository import (FitnessConflict, FitnessConsentRequired, FitnessStorageUnavailable,
                         PostgresFitnessRepository, _dump, _member_id, _mutation_arguments)
from .schemas import FitnessProfileInput, StrictModel

PURPOSE = "fitness_training_logs"
CONSENT_VERSION = "fitness-training-logs-v1"
TABLES = {"training_logs_state", "training_logs_idempotency"}
MAX_RECORDS = 366
MAX_VERSION = 2**53 - 1


def _number(value):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Introduce un número finito, sin texto ni valores especiales.")
    return value


def _uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError("La sesión necesita un identificador UUID válido.") from None
    return value


class TrainingLoad(StrictModel):
    value: float = Field(ge=0, le=2500)
    unit: Literal["kg", "lb"]

    @field_validator("value", mode="before")
    @classmethod
    def finite(cls, value):
        return _number(value)

    def kilograms(self):
        value = Decimal(str(self.value)) * (Decimal("0.45359237") if self.unit == "lb" else Decimal(1))
        return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


class TrainingSet(StrictModel):
    reps: int | None = Field(default=None, ge=1, le=10000)
    seconds: float | None = Field(default=None, gt=0, le=86400)
    load: TrainingLoad | None = None

    @field_validator("seconds", mode="before")
    @classmethod
    def finite(cls, value):
        return None if value is None else _number(value)

    @model_validator(mode="after")
    def one_axis(self):
        if (self.reps is None) == (self.seconds is None):
            raise ValueError("Cada serie necesita repeticiones o segundos, sin combinar ambos.")
        return self


class TrainingExercise(StrictModel):
    exercise_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    sets: list[TrainingSet] = Field(max_length=20)
    skipped: bool

    @model_validator(mode="after")
    def explicit_result(self):
        if self.skipped and self.sets:
            raise ValueError("Un ejercicio omitido no puede tener series realizadas.")
        if not self.skipped and not self.sets:
            raise ValueError("Añade al menos una serie realizada o marca el ejercicio como omitido.")
        return self


class TrainingLog(StrictModel):
    session_id: str
    program_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    content_version: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    performed_on: str
    timezone: str
    duration_minutes: float | None = Field(default=None, gt=0, le=1440)
    exercises: list[TrainingExercise] = Field(min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def valid_id(cls, value):
        return _uuid(value)

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, value):
        return FitnessProfileInput.known_timezone(value)

    @field_validator("performed_on")
    @classmethod
    def valid_date(cls, value):
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value or not 2000 <= parsed.year <= 2100:
                raise ValueError()
        except ValueError:
            raise ValueError("Selecciona una fecha válida entre 2000 y 2100.") from None
        return value

    @field_validator("duration_minutes", mode="before")
    @classmethod
    def finite(cls, value):
        return None if value is None else _number(value)

    @model_validator(mode="after")
    def valid_session(self):
        if date.fromisoformat(self.performed_on) > datetime.now(ZoneInfo(self.timezone)).date():
            raise ValueError("El registro debe ser de hoy o de una fecha anterior.")
        if len({item.exercise_id for item in self.exercises}) != len(self.exercises):
            raise ValueError("No repitas ejercicios en el registro.")
        if all(item.skipped for item in self.exercises):
            raise ValueError("Registra al menos una serie realizada; puedes omitir los demás ejercicios.")
        return self


class StoredTrainingSet(TrainingSet):
    load_kg: float | None

    @field_validator("load_kg", mode="before")
    @classmethod
    def finite_kg(cls, value):
        return None if value is None else _number(value)

    @model_validator(mode="after")
    def consistent_load(self):
        if self.load_kg != (self.load.kilograms() if self.load else None):
            raise ValueError("La carga normalizada no coincide con su unidad.")
        return self


class StoredTrainingExercise(TrainingExercise):
    sets: list[StoredTrainingSet] = Field(max_length=20)


class StoredTrainingLog(TrainingLog):
    exercises: list[StoredTrainingExercise] = Field(min_length=1, max_length=100)
    scheduled_date: str
    scheduled_time: str
    scheduled_timezone: str
    recorded_at: str
    updated_at: str

    @model_validator(mode="after")
    def storage_dates(self):
        if self.scheduled_timezone != self.timezone or self.performed_on < self.scheduled_date:
            raise ValueError("El registro no coincide con la fecha y zona de su sesión.")
        session_instant(self.scheduled_date, self.scheduled_time, self.scheduled_timezone)
        created, updated = datetime.fromisoformat(self.recorded_at), datetime.fromisoformat(self.updated_at)
        if created.tzinfo is None or updated.tzinfo is None or updated < created:
            raise ValueError("Las fechas del registro no son válidas.")
        return self


class TrainingLogConsent(StrictModel):
    purpose: Literal["fitness_training_logs"]
    text_version: Literal["fitness-training-logs-v1"]
    granted: bool


class TrainingLogWrite(StrictModel):
    expected_version: int = Field(ge=0, le=MAX_VERSION)
    log: TrainingLog


class TrainingLogConsentWrite(StrictModel):
    expected_version: int = Field(ge=0, le=MAX_VERSION)
    consent: TrainingLogConsent


class TrainingLogDeleteWrite(StrictModel):
    expected_version: int = Field(ge=0, le=MAX_VERSION)
    confirm_delete: Literal[True]

    @field_validator("confirm_delete", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("Confirma explícitamente que quieres eliminar los registros.")
        return value


def _snapshot(row):
    if row is None:
        return {"version": 0, "logs": [], "consent": None, "updated_at": None}
    try:
        version = row["version"]
        if isinstance(version, bool) or not isinstance(version, int) or not 0 <= version <= MAX_VERSION:
            raise ValueError()
        raw = row["logs"]
        if not isinstance(raw, list) or len(raw) > MAX_RECORDS:
            raise ValueError()
        logs = [StoredTrainingLog.model_validate(item).model_dump(mode="json") for item in raw]
        if len({item["session_id"] for item in logs}) != len(logs):
            raise ValueError()
        consent = row.get("consent")
        if consent is not None:
            parsed = TrainingLogConsent.model_validate({key: consent.get(key) for key in ("purpose", "text_version", "granted")})
            recorded_at = consent.get("recorded_at")
            if not isinstance(recorded_at, str) or datetime.fromisoformat(recorded_at).tzinfo is None:
                raise ValueError()
            consent = {**parsed.model_dump(mode="json"), "recorded_at": recorded_at}
        if logs and (not consent or consent["granted"] is not True):
            raise ValueError()
        updated = row.get("updated_at")
        if isinstance(updated, datetime):
            updated = updated.isoformat()
        if not isinstance(updated, str) or datetime.fromisoformat(updated).tzinfo is None:
            raise ValueError()
        return {"version": version, "logs": sorted(logs, key=lambda item: (item["performed_on"], item["updated_at"]), reverse=True),
                "consent": consent, "updated_at": updated}
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        raise FitnessStorageUnavailable() from None


def _content_detail(program_id):
    from .training_content import training_detail, TrainingContentError
    try:
        return training_detail(program_id)
    except TrainingContentError:
        raise FitnessInputError("Esta sesión ya no está disponible. Actualiza el entrenamiento.") from None


def _validate_content(payload):
    detail = _content_detail(payload["program_id"])
    if payload["content_version"] != detail["content_version"]:
        raise FitnessConflict("Los detalles del entrenamiento cambiaron. Vuelve a abrir la sesión antes de registrar.")
    expected = {item["id"]: item for item in detail["exercises"] if item["phase"] == "work"}
    if {item["exercise_id"] for item in payload["exercises"]} != set(expected):
        raise FitnessInputError("El registro debe incluir los ejercicios de esta sesión; marca los que hayas omitido.")
    for item in payload["exercises"]:
        axis = expected[item["exercise_id"]]["tracking_unit"]
        if axis not in {"reps", "seconds"}:
            raise FitnessStorageUnavailable()
        if any(series[axis] is None for series in item["sets"]):
            raise FitnessInputError("Usa las unidades indicadas para cada ejercicio: repeticiones o segundos.")
        if expected[item["exercise_id"]].get("load_recordable") is not True and any(series["load"] is not None for series in item["sets"]):
            raise FitnessInputError("Este ejercicio se registra sin carga añadida. Revisa las series antes de guardar.")
    return detail


class TrainingLogsRepository:
    """Separate consent/version; saved adult profile and actual agenda required."""
    def __init__(self, foundation):
        self.foundation = foundation

    @staticmethod
    def available(cursor, *, required=True):
        cursor.execute("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
            pg_catalog.pg_get_userbyid(c.relowner) = current_user AS is_owner
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'roxy_home_fitness'
            AND c.relname IN ('training_logs_state', 'training_logs_idempotency')""")
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
        cursor.execute("SELECT version, logs, consent, updated_at FROM roxy_home_fitness.training_logs_state WHERE member_id = %s" + (" FOR UPDATE" if lock else ""), (member,))
        snapshot = _snapshot(cursor.fetchone())
        profile = PostgresFitnessRepository._read(cursor, member)["profile"]
        eligible = bool(profile and profile.get("age_band") in {"18_29", "30_44", "45_64", "65_plus"})
        return {**snapshot, "eligible": eligible, "eligibility_reason": None if eligible else "adult_profile_required"}

    def snapshot(self, member):
        with self.foundation._transaction(member) as cursor:
            self.available(cursor)
            return self.read(cursor, member)

    def export_data(self, member):
        return {"format": "roxy-home-fitness-training-logs-v1", "exported_at": datetime.now(timezone.utc).isoformat(),
                "data": self.snapshot(member), "scope": "authenticated_member_only", "self_reported_training": True}

    def save(self, member, log, *, expected_version, idempotency_key):
        parsed = TrainingLog.model_validate(log.model_dump(mode="json") if isinstance(log, TrainingLog) else log)
        return self._mutate(member, "log", parsed.model_dump(mode="json"), expected_version, idempotency_key)

    def consent(self, member, consent, *, expected_version, idempotency_key):
        parsed = TrainingLogConsent.model_validate(consent.model_dump(mode="json") if isinstance(consent, TrainingLogConsent) else consent)
        return self._mutate(member, "consent", parsed.model_dump(mode="json"), expected_version, idempotency_key)

    def remove(self, member, session_id, *, expected_version, idempotency_key):
        try:
            _uuid(session_id)
        except ValueError as exc:
            raise FitnessInputError(str(exc)) from None
        return self._mutate(member, "remove", {"session_id": session_id}, expected_version, idempotency_key)

    def delete_data(self, member, *, expected_version, idempotency_key):
        return self._mutate(member, "delete", None, expected_version, idempotency_key)

    @staticmethod
    def erase_for_member(cursor, member):
        """Caller holds foundation/agenda locks; same transaction, keeps tombstone."""
        if not TrainingLogsRepository.available(cursor, required=False):
            return
        member = _member_id(member)
        cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-training-logs:" + member,))
        cursor.execute("INSERT INTO roxy_home_fitness.training_logs_state (member_id) VALUES (%s) ON CONFLICT (member_id) DO NOTHING", (member,))
        cursor.execute("UPDATE roxy_home_fitness.training_logs_state SET version = version + 1, logs = '[]'::jsonb, consent = NULL, updated_at = CURRENT_TIMESTAMP WHERE member_id = %s", (member,))
        cursor.execute("DELETE FROM roxy_home_fitness.training_logs_idempotency WHERE member_id = %s", (member,))

    @staticmethod
    def guard_plan_change(cursor, member, proposed_plan, *, previous_plan=None):
        """Existing logs protect agenda identity. Caller already holds agenda lock."""
        if not TrainingLogsRepository.available(cursor, required=False):
            return
        cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-training-logs:" + member,))
        logs = TrainingLogsRepository.read(cursor, member)["logs"]
        incoming = {item["id"]: item for item in (proposed_plan or {}).get("sessions", [])}
        previous = {item["id"]: item for item in (previous_plan or {}).get("sessions", [])}
        for log in logs:
            item = incoming.get(log["session_id"])
            if (item is None or item["program_id"] != log["program_id"] or
                item["date"] != log["scheduled_date"] or item["time"] != log["scheduled_time"] or
                proposed_plan["timezone"] != log["scheduled_timezone"] or
                (item.get("content_version") is not None and item["content_version"] != log["content_version"])):
                raise FitnessInputError("Esta sesión tiene un registro de entrenamiento. Conserva su fecha y ejercicios o elimina primero ese registro de forma explícita.")
            if log["session_id"] in previous and item.get("training_targets") != previous[log["session_id"]].get("training_targets"):
                raise FitnessInputError("Esta sesión ya tiene resultados. Conserva sus objetivos para mantener el historial; prepara otra sesión para elegir nuevos objetivos.")

    def _mutate(self, member, operation, payload, expected_version, key):
        member = _member_id(member)
        _mutation_arguments(expected_version, key)
        digest = hashlib.sha256(_dump({"operation": operation, "expected_version": expected_version, "payload": payload}).encode()).hexdigest()
        with self.foundation._transaction(member) as cursor:
            self.available(cursor)
            for scope in ("fitness", "activity-plan", "training-logs"):
                cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-" + scope + ":" + member,))
            cursor.execute("INSERT INTO roxy_home_fitness.training_logs_state (member_id) VALUES (%s) ON CONFLICT (member_id) DO NOTHING", (member,))
            state = self.read(cursor, member, lock=True)
            cursor.execute("SELECT request_hash, response_version FROM roxy_home_fitness.training_logs_idempotency WHERE member_id = %s AND request_key = %s", (member, key))
            previous = cursor.fetchone()
            if previous:
                if previous["request_hash"] != digest or previous["response_version"] != state["version"]:
                    raise FitnessConflict("La solicitud ya cambió. Actualiza tus registros antes de continuar.")
                return {**state, "idempotent_replay": True}
            if expected_version != state["version"]:
                raise FitnessConflict("Tus registros cambiaron en otra sesión. Actualiza antes de guardar.")
            if state["version"] == MAX_VERSION:
                raise FitnessInputError("Se alcanzó el límite de versiones del registro.")
            if (operation == "log" or (operation == "consent" and payload["granted"])) and not state["eligible"]:
                raise FitnessInputError("Completa primero tus preferencias de Ejercicio y confirma que tienes 18 años o más.")
            logs, consent = state["logs"], state["consent"]
            if operation == "log":
                if not consent or consent["granted"] is not True:
                    raise FitnessConsentRequired("Decide primero si quieres guardar tus series y resultados personales.")
                ActivityPlanRepository.available(cursor)
                plan = ActivityPlanRepository.read(cursor, member, lock=True)["plan"]
                session = next((item for item in (plan or {}).get("sessions", []) if item["id"] == payload["session_id"]), None)
                if session is None:
                    raise FitnessInputError("Esa sesión ya no existe en tu agenda. Actualiza Mi plan.")
                if session["status"] == "skipped":
                    raise FitnessInputError("Esta sesión está omitida. Devuélvela a pendiente antes de guardar o corregir resultados.")
                if session["program_id"] != payload["program_id"]:
                    raise FitnessInputError("Los ejercicios no coinciden con esta sesión de tu agenda.")
                if plan["timezone"] != payload["timezone"] or payload["performed_on"] < session["date"]:
                    raise FitnessInputError("Usa la zona horaria de la agenda y una fecha desde el inicio de la sesión.")
                if session_instant(session["date"], session["time"], plan["timezone"]) > datetime.now(timezone.utc):
                    raise FitnessInputError("No puedes registrar resultados de una sesión futura.")
                if session.get("content_version") is not None and session["content_version"] != payload["content_version"]:
                    raise FitnessConflict("La versión de los ejercicios no coincide con tu agenda. Actualiza la sesión.")
                _validate_content(payload)
                before = next((item for item in logs if item["session_id"] == payload["session_id"]), None)
                if before is None and len(logs) >= MAX_RECORDS:
                    raise FitnessInputError("Puedes guardar hasta 366 sesiones. Exporta y elimina un registro si quieres añadir otro.")
                stamp = datetime.now(timezone.utc).isoformat()
                entry = {**payload, "scheduled_date": session["date"], "scheduled_time": session["time"],
                         "scheduled_timezone": plan["timezone"],
                         "recorded_at": before["recorded_at"] if before else stamp, "updated_at": stamp}
                for exercise in entry["exercises"]:
                    for series in exercise["sets"]:
                        series["load_kg"] = TrainingLoad.model_validate(series["load"]).kilograms() if series["load"] else None
                logs = [item for item in logs if item["session_id"] != payload["session_id"]] + [entry]
            elif operation == "remove":
                if not any(item["session_id"] == payload["session_id"] for item in logs):
                    raise FitnessInputError("Ese registro ya no existe. Actualiza tus entrenamientos.")
                logs = [item for item in logs if item["session_id"] != payload["session_id"]]
            elif operation == "consent":
                consent = {**payload, "recorded_at": datetime.now(timezone.utc).isoformat()}
                if not payload["granted"]:
                    logs = []
            elif operation == "delete":
                logs, consent = [], None
            else:
                raise FitnessInputError("Operación no válida.")
            version = state["version"] + 1
            cursor.execute("DELETE FROM roxy_home_fitness.training_logs_idempotency WHERE member_id = %s", (member,))
            cursor.execute("UPDATE roxy_home_fitness.training_logs_state SET version = %s, logs = %s::jsonb, consent = %s::jsonb, updated_at = CURRENT_TIMESTAMP WHERE member_id = %s", (version, _dump(logs), _dump(consent) if consent is not None else None, member))
            cursor.execute("INSERT INTO roxy_home_fitness.training_logs_idempotency (member_id, request_key, request_hash, response_version) VALUES (%s, %s, %s, %s)", (member, key, digest, version))
            return self.read(cursor, member)
