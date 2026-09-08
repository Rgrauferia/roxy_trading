"""PostgreSQL-only, member-isolated preference persistence.

No connection, schema creation, migration or fallback file is performed on import.
Provision the SQL migration separately with an administrator role. The runtime
role must be different from the owner and must not bypass row-level security.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

from .domain import FitnessInputError
from .schemas import CONSENT_PURPOSE, CONSENT_VERSION, FitnessConsentInput, FitnessProfileInput


class FitnessStorageUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("El almacenamiento privado de Ejercicio no está disponible. No se guardaron preferencias.")


class FitnessConflict(ValueError):
    pass


class FitnessConsentRequired(ValueError):
    pass


def _member_id(value: str) -> str:
    # This is the authenticated MEMBER id, never a submitted or household id.
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,128}", value):
        raise FitnessInputError("La identidad personal no es válida.")
    return value


def _mutation_arguments(version: int, key: str) -> None:
    if isinstance(version, bool) or not isinstance(version, int) or not 0 <= version < 2**53:
        raise FitnessInputError("La versión no es válida.")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", key):
        raise FitnessInputError("Se requiere una clave de idempotencia válida.")


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _snapshot(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {"version": 0, "profile": None, "consent": None, "updated_at": None}
    profile = row.get("profile")
    consent = row.get("consent")
    # Corruption is not treated as an empty profile that can be overwritten.
    if profile is not None:
        profile = FitnessProfileInput.model_validate(profile).model_dump(mode="json")
    if consent is not None:
        if not isinstance(consent, dict):
            raise FitnessStorageUnavailable()
        consent_values = {key: consent.get(key) for key in ("purpose", "text_version", "granted")}
        consent = {**FitnessConsentInput.model_validate(consent_values).model_dump(mode="json"),
                   "recorded_at": consent.get("recorded_at")}
    if profile is not None and (not consent or consent.get("granted") is not True):
        raise FitnessStorageUnavailable()
    updated = row.get("updated_at")
    if isinstance(updated, datetime):
        updated = updated.isoformat()
    return {"version": int(row["version"]), "profile": profile, "consent": consent, "updated_at": updated}


class PostgresFitnessRepository:
    def __init__(self, dsn: str | None = None, *, connection_factory: Callable[..., Any] | None = None):
        self._dsn = dsn or ""
        # Injection is for synthetic tests; production uses psycopg exclusively.
        self._connection_factory = connection_factory

    @classmethod
    def from_env(cls) -> "PostgresFitnessRepository":
        return cls(os.environ.get("ROXY_HOME_FITNESS_DATABASE_URL"))

    def configuration_status(self) -> dict[str, Any]:
        if not self._dsn:
            code = "storage_not_configured"
        else:
            try:
                parsed = urlsplit(self._dsn)
                valid = parsed.scheme in {"postgres", "postgresql"} and bool(parsed.hostname) and bool(parsed.path.strip("/"))
            except ValueError:
                valid = False
            if not valid:
                code = "invalid_storage_configuration"
            elif self._connection_factory is None and importlib.util.find_spec("psycopg") is None:
                code = "postgres_driver_unavailable"
            else:
                code = "storage_configured_not_verified"
        return {"status": code, "configured": code == "storage_configured_not_verified",
                "storage": "postgresql", "verified": False, "automatic_migrations": False,
                "personal_data_fallback": False}

    @contextmanager
    def _transaction(self, member_id: str):
        member_id = _member_id(member_id)
        if not self.configuration_status()["configured"]:
            raise FitnessStorageUnavailable()
        try:
            factory = self._connection_factory
            if factory is None:
                import psycopg
                from psycopg.rows import dict_row
                # Fail TLS/certificate negotiation before authenticating. A
                # DSN cannot downgrade this to prefer/allow/disable. Provision
                # a trusted sslrootcert for the Home database when required.
                connection = psycopg.connect(self._dsn, connect_timeout=5, sslmode="verify-full",
                                            application_name="roxy-home-fitness", row_factory=dict_row)
            else:
                connection = factory(self._dsn)
            with connection as conn:
                with conn.transaction():
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT pg_catalog.set_config('statement_timeout', '5000', TRUE), pg_catalog.set_config('lock_timeout', '3000', TRUE)")
                        cursor.execute("SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid = pg_catalog.pg_backend_pid()")
                        tls = cursor.fetchone()
                        if not tls or tls["ssl"] is not True:
                            raise FitnessStorageUnavailable()
                        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_catalog.pg_roles WHERE rolname = current_user")
                        role = cursor.fetchone()
                        if not role or role["rolsuper"] or role["rolbypassrls"]:
                            raise FitnessStorageUnavailable()
                        cursor.execute("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                            pg_catalog.pg_get_userbyid(c.relowner) = current_user AS is_owner
                            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                            WHERE n.nspname = 'roxy_home_fitness' AND c.relname IN ('member_state', 'idempotency')""")
                        tables = cursor.fetchall()
                        if {row["relname"] for row in tables} != {"member_state", "idempotency"} or any(
                            not row["relrowsecurity"] or not row["relforcerowsecurity"] or row["is_owner"] for row in tables
                        ):
                            raise FitnessStorageUnavailable()
                        cursor.execute("SELECT version FROM roxy_home_fitness.schema_version WHERE singleton = TRUE")
                        marker = cursor.fetchone()
                        if not marker or marker["version"] != 1:
                            raise FitnessStorageUnavailable()
                        cursor.execute("SELECT pg_catalog.set_config('roxy_home.member_id', %s, TRUE)", (member_id,))
                        yield cursor
        except (FitnessStorageUnavailable, FitnessConflict, FitnessConsentRequired, FitnessInputError):
            raise
        except Exception:
            # Do not expose DSN, SQL, provider errors or member data in UI/logs.
            raise FitnessStorageUnavailable() from None

    @staticmethod
    def _read(cursor: Any, member_id: str, *, lock: bool = False) -> dict[str, Any]:
        cursor.execute("SELECT version, profile, consent, updated_at FROM roxy_home_fitness.member_state WHERE member_id = %s" + (" FOR UPDATE" if lock else ""), (member_id,))
        return _snapshot(cursor.fetchone())

    def snapshot(self, member_id: str) -> dict[str, Any]:
        with self._transaction(member_id) as cursor:
            return self._read(cursor, member_id)

    def export_data(self, member_id: str) -> dict[str, Any]:
        return {"format": "roxy-home-fitness-preferences-v1", "exported_at": datetime.now(timezone.utc).isoformat(),
                "data": self.snapshot(member_id),
                "scope": "authenticated_member_only", "contains_clinical_records": False}

    def save_profile(self, member_id: str, profile: FitnessProfileInput | dict[str, Any], *, expected_version: int, idempotency_key: str) -> dict[str, Any]:
        parsed = profile if isinstance(profile, FitnessProfileInput) else FitnessProfileInput.model_validate(profile)
        return self._mutate(member_id, "profile", parsed.model_dump(mode="json"), expected_version, idempotency_key)

    def set_consent(self, member_id: str, consent: FitnessConsentInput | dict[str, Any], *, expected_version: int, idempotency_key: str) -> dict[str, Any]:
        parsed = consent if isinstance(consent, FitnessConsentInput) else FitnessConsentInput.model_validate(consent)
        return self._mutate(member_id, "consent", parsed.model_dump(mode="json"), expected_version, idempotency_key)

    def delete_data(self, member_id: str, *, expected_version: int, idempotency_key: str) -> dict[str, Any]:
        """Clear active preferences/consent. Retain only a version tombstone for races.

        The API must require explicit confirmation. Backup expiry is infrastructure
        policy, not instantaneous erasure claimed by this operation.
        """
        return self._mutate(member_id, "delete", None, expected_version, idempotency_key)

    def _mutate(self, member_id: str, operation: str, payload: Any, expected_version: int, key: str) -> dict[str, Any]:
        member_id = _member_id(member_id)
        _mutation_arguments(expected_version, key)
        digest = hashlib.sha256(_dump({"operation": operation, "expected_version": expected_version, "payload": payload}).encode()).hexdigest()
        with self._transaction(member_id) as cursor:
            # Lock serializes the first write too; a row lock alone cannot lock absence.
            cursor.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(%s, 0))", ("roxy-home-fitness:" + member_id,))
            cursor.execute("INSERT INTO roxy_home_fitness.member_state (member_id) VALUES (%s) ON CONFLICT (member_id) DO NOTHING", (member_id,))
            state = self._read(cursor, member_id, lock=True)
            cursor.execute("SELECT request_hash, response_version FROM roxy_home_fitness.idempotency WHERE member_id = %s AND request_key = %s", (member_id, key))
            previous = cursor.fetchone()
            if previous:
                if previous["request_hash"] != digest or previous["response_version"] != state["version"]:
                    raise FitnessConflict("La solicitud ya cambió. Actualiza la sección antes de continuar.")
                return {**state, "idempotent_replay": True}
            if expected_version != state["version"]:
                raise FitnessConflict("Las preferencias cambiaron en otra sesión. Actualiza antes de guardar.")
            profile, consent = state["profile"], state["consent"]
            if operation == "profile":
                if not consent or consent.get("granted") is not True or consent.get("purpose") != CONSENT_PURPOSE or consent.get("text_version") != CONSENT_VERSION:
                    raise FitnessConsentRequired("Necesitas otorgar el consentimiento vigente para guardar preferencias.")
                profile = payload
            elif operation == "consent":
                consent = {**payload, "recorded_at": datetime.now(timezone.utc).isoformat()}
                if not payload["granted"]:
                    profile = None
            elif operation == "delete":
                profile, consent = None, None
            else:
                raise FitnessInputError("Operación no válida.")
            version = state["version"] + 1
            # Older responses cannot re-expose a revoked/deleted profile. They store
            # hashes and versions only; clearing them also bounds retention and size.
            cursor.execute("DELETE FROM roxy_home_fitness.idempotency WHERE member_id = %s", (member_id,))
            cursor.execute("""UPDATE roxy_home_fitness.member_state SET version = %s, profile = %s::jsonb,
                consent = %s::jsonb, updated_at = CURRENT_TIMESTAMP WHERE member_id = %s""",
                (version, _dump(profile) if profile is not None else None, _dump(consent) if consent is not None else None, member_id))
            cursor.execute("""INSERT INTO roxy_home_fitness.idempotency
                (member_id, request_key, request_hash, response_version) VALUES (%s, %s, %s, %s)""",
                (member_id, key, digest, version))
            return self._read(cursor, member_id)
