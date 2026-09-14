"""Private, voluntarily chosen educational agenda and self-reported completion.

No prescription, medical assessment, provider calls or shared household writes.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from .schemas import StrictModel, FitnessProfileInput, ConfirmedTrainingRequirements
from .training_selection import TRAINING_IDS, validate_new_training_session
from .training_targets import TrainingTargets, validate_training_targets
from .repository import (FitnessConflict, FitnessConsentRequired, FitnessStorageUnavailable,
                         _member_id, _mutation_arguments, _dump)
from .domain import FitnessInputError
from .programs import program_detail
import hashlib

PURPOSE = "fitness_activity_plan"
CONSENT_VERSION = "fitness-activity-plan-v1"
TABLES = {"activity_plan_state", "activity_plan_idempotency"}
SESSION_FIELDS = ("id", "program_id", "date", "time", "content_version", "confirmed_requirements", "reserved_minutes", "travel_minutes", "training_targets")


class ActivityConsent(StrictModel):
    purpose: Literal["fitness_activity_plan"]
    text_version: Literal["fitness-activity-plan-v1"]
    granted: bool


class ActivitySession(StrictModel):
    id: str
    program_id: str
    date: str
    time: str
    content_version: str | None = Field(default=None, min_length=1, max_length=80)
    confirmed_requirements: ConfirmedTrainingRequirements | None = None
    reserved_minutes: int | None = Field(default=None, ge=5, le=180)
    travel_minutes: int | None = Field(default=None, ge=0, le=180)
    training_targets: TrainingTargets | None = None

    @model_validator(mode="after")
    def program_contract(self):
        fields = (self.content_version, self.confirmed_requirements, self.reserved_minutes, self.travel_minutes)
        if self.program_id in TRAINING_IDS:
            if any(value is None for value in fields):
                raise ValueError("Revisa la rutina y confirma sus requisitos antes de añadirla al plan.")
        elif self.program_id in {"gentle-strength", "gentle-balance", "gentle-flexibility"}:
            if any(value is not None for value in fields) or self.training_targets is not None:
                raise ValueError("La guía original no admite requisitos de otra rutina.")
        else:
            raise ValueError("No existe esa rutina o guía.")
        return self

    @field_validator("id")
    @classmethod
    def valid_id(cls, value):
        try:
            if str(UUID(value)) != value:
                raise ValueError()
        except (ValueError, AttributeError):
            raise ValueError("La actividad necesita un identificador UUID válido.") from None
        return value

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value or not 2000 <= parsed.year <= 2100:
                raise ValueError()
        except ValueError:
            raise ValueError("Selecciona una fecha válida entre 2000 y 2100.") from None
        return value

    @field_validator("time")
    @classmethod
    def valid_time(cls, value):
        from .schemas import TimeWindow
        return TimeWindow.valid_clock(value)


def session_instant(day, clock, zone):
    local = datetime.fromisoformat(day + "T" + clock)
    tz = ZoneInfo(zone)
    candidates = []
    for fold in (0, 1):
        stamp = local.replace(tzinfo=tz, fold=fold).astimezone(timezone.utc)
        if stamp.astimezone(tz).replace(tzinfo=None) == local and stamp not in candidates:
            candidates.append(stamp)
    if len(candidates) != 1:
        raise ValueError("Esa hora local no existe o se repite por el cambio de horario. Elige otra hora para esa fecha.")
    return candidates[0]


class ActivityPlan(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    timezone: str = Field(min_length=1, max_length=64)
    sessions: list[ActivitySession] = Field(max_length=366)

    @field_validator("title")
    @classmethod
    def valid_title(cls, value):
        if not value.strip() or any(ord(ch) < 32 for ch in value):
            raise ValueError("Escribe un nombre para tu plan.")
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        return FitnessProfileInput.known_timezone(value)

    @model_validator(mode="after")
    def no_duplicates(self):
        if len({item.id for item in self.sessions}) != len(self.sessions):
            raise ValueError("No repitas identificadores de actividades.")
        if len({(item.program_id, item.date, item.time) for item in self.sessions}) != len(self.sessions):
            raise ValueError("Ya elegiste esa guía para la misma fecha y hora.")
        for item in self.sessions:
            session_instant(item.date, item.time, self.timezone)
        return self


class ActivityPlanWrite(StrictModel):
    expected_version: int = Field(ge=0, le=2**53 - 1)
    expected_profile_version: int | None = Field(default=None, ge=0, le=2**53 - 1)
    plan: ActivityPlan


class ActivityConsentWrite(StrictModel):
    expected_version: int = Field(ge=0, le=2**53 - 1)
    consent: ActivityConsent


class ActivityStatusWrite(StrictModel):
    expected_version: int = Field(ge=0, le=2**53 - 1)
    status: Literal["planned", "completed", "skipped"]


def _plan_input(parsed):
    """Omit absent session features while keeping nullable target axes canonical."""
    value = parsed.model_dump(mode="json")
    for item in value["sessions"]:
        for key in SESSION_FIELDS[4:]:
            if item.get(key) is None:
                item.pop(key, None)
    return value


def _snapshot(row):
    if row is None:
        return {"version": 0, "plan": None, "consent": None, "updated_at": None,
                "progress": {"planned": 0, "completed": 0, "skipped": 0, "total": 0}}
    consent, plan = row.get("consent"), row.get("plan")
    if consent is not None:
        parsed = ActivityConsent.model_validate({key: consent.get(key) for key in ("purpose", "text_version", "granted")})
        consent = {**parsed.model_dump(mode="json"), "recorded_at": consent.get("recorded_at")}
    progress = {"planned": 0, "completed": 0, "skipped": 0, "total": 0}
    if plan is not None:
        if not consent or consent["granted"] is not True:
            raise FitnessStorageUnavailable()
        parsed = ActivityPlan.model_validate({**plan, "sessions": [
            {key: item[key] for key in SESSION_FIELDS if key in item}
            for item in plan.get("sessions", [])]})
        clean = _plan_input(parsed)
        for item, source in zip(clean["sessions"], plan["sessions"]):
            status, completed_at = source.get("status"), source.get("completed_at")
            if status not in {"planned", "completed", "skipped"}:
                raise FitnessStorageUnavailable()
            if status == "completed":
                if not isinstance(completed_at, str):
                    raise FitnessStorageUnavailable()
                stamp = datetime.fromisoformat(completed_at)
                if stamp.tzinfo is None:
                    raise FitnessStorageUnavailable()
            elif completed_at is not None:
                raise FitnessStorageUnavailable()
            item.update(status=status, completed_at=completed_at, starts_at=session_instant(item["date"], item["time"], clean["timezone"]).isoformat())
            progress[status] += 1
        progress["total"] = len(clean["sessions"])
        plan = clean
    updated = row.get("updated_at")
    return {"version": int(row["version"]), "plan": plan, "consent": consent,
            "updated_at": updated.isoformat() if isinstance(updated, datetime) else updated,
            "progress": progress}


class ActivityPlanRepository:
    """Shares Home's verified PostgreSQL connection; separate member state/version."""
    def __init__(self, foundation):
        self.foundation = foundation

    @staticmethod
    def available(cursor, *, required=True):
        cursor.execute("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
            pg_catalog.pg_get_userbyid(c.relowner) = current_user AS is_owner
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'roxy_home_fitness'
            AND c.relname IN ('activity_plan_state', 'activity_plan_idempotency')""")
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
        cursor.execute("SELECT version, plan, consent, updated_at FROM roxy_home_fitness.activity_plan_state WHERE member_id = %s" + (" FOR UPDATE" if lock else ""), (member,))
        return _snapshot(cursor.fetchone())

    def snapshot(self, member):
        with self.foundation._transaction(member) as cursor:
            self.available(cursor)
            return self.read(cursor, member)

    def export_data(self, member):
        from .training_logs import TrainingLogsRepository
        with self.foundation._transaction(member) as cursor:
            self.available(cursor)
            result = {"format": "roxy-home-activity-plan-v1", "exported_at": datetime.now(timezone.utc).isoformat(),
                      "data": self.read(cursor, member), "scope": "authenticated_member_only", "contains_clinical_records": False}
            if TrainingLogsRepository.available(cursor, required=False):
                result["training_logs"] = TrainingLogsRepository.read(cursor, member)
            return result

    def save(self, member, plan, *, expected_version, idempotency_key, expected_profile_version=None):
        parsed = plan if isinstance(plan, ActivityPlan) else ActivityPlan.model_validate(plan)
        # Validate the actual bundled source before recording a new selection.
        for program_id in {item.program_id for item in parsed.sessions}:
            if program_id not in TRAINING_IDS:
                program_detail(program_id)
        return self._mutate(member, "plan", _plan_input(parsed), expected_version, idempotency_key, expected_profile_version=expected_profile_version)

    def consent(self, member, consent, *, expected_version, idempotency_key):
        parsed = consent if isinstance(consent, ActivityConsent) else ActivityConsent.model_validate(consent)
        return self._mutate(member, "consent", parsed.model_dump(mode="json"), expected_version, idempotency_key)

    def set_status(self, member, session_id, status, *, expected_version, idempotency_key):
        ActivitySession.valid_id(session_id)
        if status not in {"planned", "completed", "skipped"}:
            raise FitnessInputError("Estado de actividad inválido.")
        return self._mutate(member, "status", {"id": session_id, "status": status}, expected_version, idempotency_key)

    def delete_data(self, member, *, expected_version, idempotency_key):
        return self._mutate(member, "delete", None, expected_version, idempotency_key)

    @staticmethod
    def erase_for_member(cursor, member):
        """Called inside the foundation DELETE transaction; no partial erasure."""
        if not ActivityPlanRepository.available(cursor, required=False):
            return
        cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-activity-plan:" + member,))
        # A global erasure must invalidate an in-flight first consent as well.
        # Lock and create a tombstone even if no agenda row has existed yet.
        cursor.execute("INSERT INTO roxy_home_fitness.activity_plan_state (member_id) VALUES (%s) ON CONFLICT (member_id) DO NOTHING", (member,))
        cursor.execute("UPDATE roxy_home_fitness.activity_plan_state SET version = version + 1, plan = NULL, consent = NULL, updated_at = CURRENT_TIMESTAMP WHERE member_id = %s", (member,))
        cursor.execute("DELETE FROM roxy_home_fitness.activity_plan_idempotency WHERE member_id = %s", (member,))
        from .training_logs import TrainingLogsRepository
        TrainingLogsRepository.erase_for_member(cursor, member)

    def _mutate(self, member, operation, payload, expected_version, key, *, expected_profile_version=None):
        member = _member_id(member)
        _mutation_arguments(expected_version, key)
        fingerprint = {"operation": operation, "expected_version": expected_version, "payload": payload}
        if expected_profile_version is not None:
            _mutation_arguments(expected_profile_version, key)
            fingerprint["expected_profile_version"] = expected_profile_version
        digest = hashlib.sha256(_dump(fingerprint).encode()).hexdigest()
        with self.foundation._transaction(member) as cursor:
            self.available(cursor)
            cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-fitness:" + member,))
            cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-activity-plan:" + member,))
            cursor.execute("INSERT INTO roxy_home_fitness.activity_plan_state (member_id) VALUES (%s) ON CONFLICT (member_id) DO NOTHING", (member,))
            state = self.read(cursor, member, lock=True)
            cursor.execute("SELECT request_hash, response_version FROM roxy_home_fitness.activity_plan_idempotency WHERE member_id = %s AND request_key = %s", (member, key))
            previous = cursor.fetchone()
            if previous:
                if previous["request_hash"] != digest or previous["response_version"] != state["version"]:
                    raise FitnessConflict("La solicitud ya cambió. Actualiza Mi plan antes de continuar.")
                return {**state, "idempotent_replay": True}
            if expected_version != state["version"]:
                raise FitnessConflict("Mi plan cambió en otra sesión. Actualiza antes de guardar.")
            plan, consent = state["plan"], state["consent"]
            if operation in {"plan", "status"} and (not consent or not consent["granted"]):
                raise FitnessConsentRequired("Decide primero si quieres guardar tu agenda personal y las actividades que marques como realizadas.")
            if operation == "plan":
                old = {item["id"]: item for item in plan["sessions"]} if plan else {}
                previous_zone = plan["timezone"] if plan else None
                incoming = {item["id"]: item for item in payload["sessions"]}
                history = [item for item in old.values() if item["status"] in {"completed", "skipped"}]
                if history and previous_zone != payload["timezone"]:
                    raise FitnessInputError("No puedes cambiar la zona horaria mientras haya actividades realizadas u omitidas. Conserva la zona del historial o devuelve esas actividades a pendientes explícitamente.")
                for before in history:
                    after = incoming.get(before["id"])
                    if after is None or any(before.get(key) != after.get(key) for key in SESSION_FIELDS):
                        raise FitnessInputError("No puedes mover ni quitar una actividad realizada u omitida al guardar el plan. Devuélvela primero a pendiente si quieres cambiarla.")
                from .training_logs import TrainingLogsRepository
                TrainingLogsRepository.guard_plan_change(cursor, member, payload, previous_plan=plan)
                changed = [item for item in payload["sessions"] if item["program_id"] in TRAINING_IDS and (
                    previous_zone != payload["timezone"] or not old.get(item["id"]) or any(
                        old[item["id"]].get(key) != item.get(key) for key in SESSION_FIELDS))]
                if changed:
                    foundation = self.foundation._read(cursor, member)
                    if expected_profile_version is None or expected_profile_version != foundation["version"]:
                        raise FitnessConflict("Tus preferencias cambiaron. Revisa de nuevo esta rutina antes de guardar fechas.")
                    if not foundation["profile"] or (foundation["consent"] or {}).get("granted") is not True:
                        raise FitnessConsentRequired("Guarda primero tus preferencias y disponibilidad para organizar esta rutina.")
                    others = [{**item, "status": old.get(item["id"], {}).get("status", "planned")} for item in payload["sessions"]]
                    for item in changed:
                        validate_new_training_session(foundation["profile"], item, payload, others)
                        targets = validate_training_targets(item["program_id"], item["content_version"], item.get("training_targets"))
                        if targets is not None:
                            item["training_targets"] = targets
                plan = payload
                for item in plan["sessions"]:
                    before = old.get(item["id"])
                    same = previous_zone == plan["timezone"] and before and all(before.get(key) == item.get(key) for key in SESSION_FIELDS)
                    item.update(status=before["status"] if same else "planned", completed_at=before["completed_at"] if same else None)
            elif operation == "status":
                session = next((item for item in (plan or {}).get("sessions", []) if item["id"] == payload["id"]), None)
                if session is None:
                    raise FitnessInputError("Esa actividad ya no existe en tu plan. Actualiza la sección.")
                now = datetime.now(timezone.utc)
                if payload["status"] == "completed":
                    local_time = session_instant(session["date"], session["time"], plan["timezone"])
                    if local_time > now:
                        raise FitnessInputError("No puedes marcar como realizada una actividad futura. Revisa la fecha y la hora.")
                    stamp = session["completed_at"] or now.isoformat()
                else:
                    stamp = None
                session.update(status=payload["status"], completed_at=stamp)
            elif operation == "consent":
                consent = {**payload, "recorded_at": datetime.now(timezone.utc).isoformat()}
                if not payload["granted"]:
                    plan = None
            elif operation == "delete":
                plan, consent = None, None
            if operation == "delete" or operation == "consent" and not payload["granted"]:
                from .training_logs import TrainingLogsRepository
                TrainingLogsRepository.erase_for_member(cursor, member)
            if plan:
                for item in plan["sessions"]:
                    item.pop("starts_at", None)
            version = state["version"] + 1
            cursor.execute("DELETE FROM roxy_home_fitness.activity_plan_idempotency WHERE member_id = %s", (member,))
            cursor.execute("UPDATE roxy_home_fitness.activity_plan_state SET version = %s, plan = %s::jsonb, consent = %s::jsonb, updated_at = CURRENT_TIMESTAMP WHERE member_id = %s", (version, _dump(plan) if plan is not None else None, _dump(consent) if consent is not None else None, member))
            cursor.execute("INSERT INTO roxy_home_fitness.activity_plan_idempotency (member_id, request_key, request_hash, response_version) VALUES (%s, %s, %s, %s)", (member, key, digest, version))
            return self.read(cursor, member)
