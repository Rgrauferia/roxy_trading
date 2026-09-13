from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from roxy_os.home_demo import TRIAL_DAYS, TRIAL_AI_DAILY_LIMIT, TRIAL_MEMBER_LIMIT, DEMO_NOTICE_VERSION
from roxy_os.home_recipe_profile import (
    RecipeProfileConflictError, RecipeProfileValidationError, normalize_recipe_profile,
    recipe_onboarding_required, recipe_profile_options,
)
from roxy_os.home_private_storage import (
    HomePrivateStorageError, initialized_marker, read_private_json, write_private_json,
)

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


ACCOUNT_STORE_VERSION = 1


class HomeAccountStorageError(RuntimeError):
    """An existing identity file cannot safely be treated as a new account store."""


class HomeTrialLimitError(ValueError):
    pass


class _RecoveryRejected(Exception):
    """Leave the locked store unchanged for every invalid recovery attempt."""


def _valid_account_structure(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and all(isinstance(payload.get(key), dict) for key in ("households", "members"))
        and all(isinstance(row, dict) for key in ("households", "members") for row in payload[key].values())
    )


def _protect_existing_accounts(path: Path) -> None:
    """Mark a validated legacy file without rewriting it or its identities."""
    try:
        try:
            descriptor = os.open(initialized_marker(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write("1\n")
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise HomeAccountStorageError("No se pudo confirmar el almacenamiento de las cuentas. Conservamos los datos; inténtalo más tarde.") from exc


def trial_status(household: dict[str, Any]) -> dict[str, Any] | None:
    trial = household.get("trial")
    if not isinstance(trial, dict):
        return None
    try:
        expires = datetime.fromisoformat(trial["expires_at"])
        active = expires > datetime.now(timezone.utc)
    except (KeyError, TypeError, ValueError):
        active = False
    today = datetime.now(timezone.utc).date().isoformat()
    usage = trial.get("usage", {})
    used = int(usage.get("count", 0)) if usage.get("day") == today else 0
    return {"status": "ACTIVE" if active else "EXPIRED", "expires_at": trial.get("expires_at"),
            "days": TRIAL_DAYS, "ai_daily_limit": TRIAL_AI_DAILY_LIMIT,
            "ai_remaining_today": max(0, TRIAL_AI_DAILY_LIMIT - used), "auto_charge": False,
            "media_generation": False, "voice": False}
PASSWORD_ITERATIONS = 600_000
RECOVERY_CODE_COUNT = 8
RECOVERY_SCHEMA_VERSION = 1
MEMBER_THEMES = {"classic", "olive", "coastal", "terracotta"}
MEMBER_BACKGROUNDS = {"plant", "linen", "clean", "warm"}
MEMBER_AVATARS = {"home", "professional", "monogram"}
MEMBER_RESPONSE_STYLES = {"balanced", "brief", "close", "explanatory"}
MEMBER_TEXT_SCALES = {"compact", "standard", "large"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_version(member: dict[str, Any]) -> int:
    version = member.get("session_version", 0)
    if type(version) is not int or version < 0:
        raise HomeAccountStorageError("El estado de acceso necesita revisión. Conservamos las cuentas.")
    return version


def _recovery_state(member: dict[str, Any]) -> dict[str, Any]:
    if "recovery" not in member:
        return {"schema_version": RECOVERY_SCHEMA_VERSION, "hashes": [], "generated_at": None}
    value = member["recovery"]
    try:
        if not isinstance(member.get("id"), str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", member["id"]):
            raise ValueError("Invalid recovery member identity")
        if not isinstance(value, dict) or set(value) != {"schema_version", "hashes", "generated_at"}:
            raise ValueError("Invalid recovery structure")
        if type(value["schema_version"]) is not int or value["schema_version"] != RECOVERY_SCHEMA_VERSION:
            raise ValueError("Invalid recovery schema")
        hashes = value["hashes"]
        if not isinstance(hashes, list) or len(hashes) > RECOVERY_CODE_COUNT:
            raise ValueError("Invalid recovery hashes")
        if any(not isinstance(item, str) or not re.fullmatch(r"[a-f0-9]{64}", item) for item in hashes):
            raise ValueError("Invalid recovery hash")
        if len(set(hashes)) != len(hashes):
            raise ValueError("Duplicate recovery hash")
        generated = datetime.fromisoformat(value["generated_at"])
        if generated.tzinfo is None:
            raise ValueError("Invalid recovery timestamp")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise HomeAccountStorageError("El estado de recuperación necesita revisión. Conservamos las cuentas.") from exc
    return value


def _normalize_recovery_code(value: Any) -> str | None:
    # Only presentation separators and hex case may change. Never strip arbitrary
    # characters or accept a prefix: all 128 random bits must still be supplied.
    if not isinstance(value, str) or len(value) > 128:
        return None
    normalized = re.sub(r"[ \t\r\n-]", "", value).lower()
    return normalized if re.fullmatch(r"[a-f0-9]{32}", normalized) else None


def _recovery_digest(member_id: str, code: str) -> str:
    return hashlib.sha256(("roxy-home-recovery-v1\0" + member_id + "\0" + code).encode("utf-8")).hexdigest()


def _new_recovery_codes(member_id: str) -> tuple[dict[str, Any], list[str]]:
    codes: list[str] = []
    # A bound fails closed if the random source cannot produce distinct tokens.
    for _ in range(RECOVERY_CODE_COUNT * 4):
        code = secrets.token_hex(16)
        if not isinstance(code, str) or not re.fullmatch(r"[a-f0-9]{32}", code):
            raise HomeAccountStorageError("No se pudieron generar los códigos de recuperación. Inténtalo más tarde.")
        if code not in codes:
            codes.append(code)
        if len(codes) == RECOVERY_CODE_COUNT:
            break
    if len(codes) != RECOVERY_CODE_COUNT:
        raise HomeAccountStorageError("No se pudieron generar los códigos de recuperación. Inténtalo más tarde.")
    state = {"schema_version": RECOVERY_SCHEMA_VERSION,
             "hashes": [_recovery_digest(member_id, code) for code in codes], "generated_at": _now_iso()}
    displayed = ["-".join(code[index:index + 8] for index in range(0, 32, 8)).upper() for code in codes]
    return state, displayed


def _validate_recovery_password(value: Any) -> str:
    if not isinstance(value, str) or not 12 <= len(value) <= 128:
        raise ValueError("La contraseña nueva debe tener entre 12 y 128 caracteres.")
    return value


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
        "session_version": _session_version(member),
        "preferences": normalize_member_preferences(member.get("preferences")),
        "recipe_onboarding_required": recipe_onboarding_required(member),
        "trial": trial_status(household),
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
            payload, status = read_private_json(self.path, self._empty, _valid_account_structure, HomePrivateStorageError)
        except HomePrivateStorageError as exc:
            raise HomeAccountStorageError("No se pudieron leer las cuentas. Conservamos el archivo; inténtalo más tarde.") from exc
        for household in payload["households"].values():
            if "trial" not in household:
                continue
            try:
                trial = household["trial"]
                expires = datetime.fromisoformat(trial["expires_at"])
                usage = trial.get("usage", {})
                if expires.tzinfo is None or not isinstance(usage, dict) or not isinstance(usage.get("count", 0), int) or usage.get("count", 0) < 0:
                    raise ValueError("Invalid trial state")
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                raise HomeAccountStorageError("El estado de la demo necesita revisión. Conservamos los datos y no ampliamos el acceso.") from exc
        for member in payload["members"].values():
            _session_version(member)
            _recovery_state(member)
        if status == "READY":
            _protect_existing_accounts(self.path)
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        payload["schema_version"] = ACCOUNT_STORE_VERSION
        try:
            write_private_json(self.path, payload, _valid_account_structure, HomePrivateStorageError)
        except HomePrivateStorageError as exc:
            raise HomeAccountStorageError(str(exc)) from exc

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
        _trial_admission: str | None = None,
        _issue_recovery: bool = False,
    ) -> dict[str, Any]:
        normalized_username = normalize_username(username)
        normalized_name = normalize_display_name(display_name)
        normalized_household = normalize_display_name(household_name)
        encoded_password = hash_password(password)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if _trial_admission is not None:
                today = datetime.now(timezone.utc).date().isoformat()
                trials = [h for h in payload["households"].values() if h.get("trial")]
                # Durable caps supplement CAPTCHA; changing IP cannot exceed the pilot capacity.
                if len(trials) >= 100 or sum(str(h.get("created_at", "")).startswith(today) for h in trials) >= 20:
                    raise HomeTrialLimitError("La demo alcanzó su capacidad de registro. Vuelve a intentarlo más adelante.")
                if sum(h["trial"].get("admission_hash") == _trial_admission and str(h.get("created_at", "")).startswith(today) for h in trials) >= 3:
                    raise HomeTrialLimitError("Ya se crearon varios hogares desde esta conexión hoy. Usa tu cuenta existente.")
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
            if _trial_admission is not None:
                household["trial"] = {"expires_at": (datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)).isoformat(),
                                      "admission_hash": _trial_admission, "notice_version": DEMO_NOTICE_VERSION,
                                      "usage": {}}
            member = {
                "id": member_id,
                "household_id": household_id,
                "username": normalized_username,
                "display_name": normalized_name,
                "password_hash": encoded_password,
                "role": "OWNER",
                "active": True,
                "session_version": 0,
                "preferences": default_member_preferences(),
                "recipe_onboarding_required": True,
                "created_at": _now_iso(),
            }
            recovery_codes = None
            if _issue_recovery:
                member["recovery"], recovery_codes = _new_recovery_codes(member_id)
            payload["households"][household_id] = household
            payload["members"][member_id] = member
            result = public_member(member, household)
            if recovery_codes is not None:
                result["recovery_codes"] = recovery_codes
            return result

        return self._mutate(apply)

    def register_trial(self, *, username: Any, display_name: Any, password: Any, admission_hash: str) -> dict[str, Any]:
        # The caller cannot choose, attach to or overwrite a household namespace.
        return self.bootstrap("demo_" + uuid4().hex, household_name="Mi hogar", username=username,
                              display_name=display_name, password=password, _trial_admission=admission_hash,
                              _issue_recovery=True)

    def reserve_trial_request(self, member_id: str) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            member = payload["members"].get(member_id)
            if not member or not member.get("active", True):
                raise PermissionError("Sesión no disponible")
            household = payload["households"][member["household_id"]]
            status = trial_status(household)
            if not status or status["status"] != "ACTIVE":
                raise HomeTrialLimitError("Los cinco días de prueba terminaron. Tus datos siguen disponibles para consulta.")
            if status["ai_remaining_today"] <= 0:
                raise HomeTrialLimitError("Llegaste a las 5 solicitudes de Roxy de hoy. El límite se renueva a las 00:00 UTC.")
            household["trial"]["usage"] = {"day": datetime.now(timezone.utc).date().isoformat(),
                                           "count": TRIAL_AI_DAILY_LIMIT - status["ai_remaining_today"] + 1}
            return trial_status(household)
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
            if household.get("trial") and sum(m.get("household_id") == household["id"] for m in payload["members"].values()) >= TRIAL_MEMBER_LIMIT:
                raise HomeTrialLimitError("La demo admite hasta seis perfiles por hogar.")
            member_id = str(uuid4())
            member = {
                "id": member_id,
                "household_id": household["id"],
                "username": normalized_username,
                "display_name": normalized_name,
                "password_hash": encoded_password,
                "role": "MEMBER",
                "active": True,
                "session_version": 0,
                "preferences": default_member_preferences(),
                "recipe_onboarding_required": True,
                "created_at": _now_iso(),
            }
            payload["members"][member_id] = member
            return public_member(member, household)

        return self._mutate(apply)

    @staticmethod
    def _active_recovery_member(payload: dict[str, Any], member_id: str) -> dict[str, Any]:
        member = payload["members"].get(member_id)
        if not member or member.get("active", True) is not True or member.get("household_id") not in payload["households"]:
            raise PermissionError("No se pudo confirmar el acceso para gestionar la recuperación.")
        return member

    def recovery_status(self, member_id: str) -> dict[str, Any]:
        payload = self._read_unlocked()
        member = self._active_recovery_member(payload, member_id)
        state = _recovery_state(member)
        return {"enabled": bool(state["hashes"]), "remaining": len(state["hashes"]), "generated_at": state["generated_at"]}

    def rotate_recovery_codes(
        self, member_id: str, current_password: Any, *, expected_session_version: int | None = None,
    ) -> dict[str, Any]:
        if expected_session_version is not None and (type(expected_session_version) is not int or expected_session_version < 0):
            raise PermissionError("No se pudo confirmar el acceso para gestionar la recuperación.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            member = self._active_recovery_member(payload, member_id)
            version = _session_version(member)
            password_valid = isinstance(current_password, str) and verify_password(current_password, member.get("password_hash"))
            if not password_valid or (expected_session_version is not None and expected_session_version != version):
                raise PermissionError("No se pudo confirmar el acceso para gestionar la recuperación.")
            state, codes = _new_recovery_codes(member_id)
            member["recovery"] = state
            return {"recovery_codes": codes, "remaining": len(codes), "generated_at": state["generated_at"]}

        return self._mutate(apply)

    def reset_password_with_recovery(self, username: Any, code: Any, new_password: Any) -> bool:
        password = _validate_recovery_password(new_password)
        # Pay the same password-hash cost for unknown, inactive and valid users;
        # failed attempts never create account records or update their counters.
        encoded_password = hash_password(password)
        try:
            normalized_username = normalize_username(username) if isinstance(username, str) else None
        except ValueError:
            normalized_username = None
        normalized_code = _normalize_recovery_code(code)

        def apply(payload: dict[str, Any]) -> bool:
            member = next((row for row in payload["members"].values() if row.get("username") == normalized_username), None)
            member_id = member.get("id") if member and isinstance(member.get("id"), str) else "unknown-member"
            state = _recovery_state(member) if member else {"hashes": []}
            candidate = _recovery_digest(member_id, normalized_code or "0" * 32)
            padded_hashes = [*state["hashes"], *(["0" * 64] * (RECOVERY_CODE_COUNT - len(state["hashes"])))]
            matched = False
            for stored in padded_hashes:
                matched = hmac.compare_digest(candidate, stored) or matched
            if (not member or normalized_code is None or not matched or member.get("active", True) is not True
                    or member.get("household_id") not in payload["households"]):
                raise _RecoveryRejected()
            version = _session_version(member)
            now = _now_iso()
            member["password_hash"] = encoded_password
            member["session_version"] = version + 1
            member["recovery"] = {**state, "hashes": []}
            member["password_changed_at"] = now
            member["updated_at"] = now
            return True

        try:
            return self._mutate(apply)
        except _RecoveryRejected:
            return False

    @staticmethod
    def _recipe_profile_snapshot(payload: dict[str, Any], member_id: str) -> dict[str, Any]:
        member = payload["members"].get(member_id)
        if not member or member.get("active", True) is not True:
            raise PermissionError("Sesión no disponible")
        if member.get("household_id") not in payload["households"]:
            raise PermissionError("Sesión no disponible")
        revision = member.get("recipe_profile_revision", 0)
        if type(revision) is not int or revision < 0:
            raise HomeAccountStorageError("El perfil culinario necesita revisión. Conservamos los datos.")
        raw = member.get("recipe_profile")
        if raw is None:
            if revision:
                raise HomeAccountStorageError("El perfil culinario necesita revisión. Conservamos los datos.")
            profile = None
        else:
            try:
                profile = normalize_recipe_profile(raw)
            except RecipeProfileValidationError as exc:
                raise HomeAccountStorageError("El perfil culinario necesita revisión. Conservamos los datos.") from exc
            if revision < 1:
                raise HomeAccountStorageError("El perfil culinario necesita revisión. Conservamos los datos.")
        return {
            "member_id": member_id,
            "revision": revision,
            "profile": profile,
            "required": recipe_onboarding_required(member),
            "options": recipe_profile_options(),
        }

    def get_recipe_profile(self, member_id: str) -> dict[str, Any]:
        """Return only the authenticated member's profile via its dedicated API."""
        return self._recipe_profile_snapshot(self._read_unlocked(), member_id)

    def update_recipe_profile(
        self,
        member_id: str,
        *,
        profile: dict[str, Any],
        expected_revision: int,
    ) -> dict[str, Any]:
        normalized = normalize_recipe_profile(profile)
        if type(expected_revision) is not int or expected_revision < 0:
            raise RecipeProfileValidationError("La revisión del perfil no es válida. Recarga la página.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            before = self._recipe_profile_snapshot(payload, member_id)
            if before["revision"] != expected_revision:
                raise RecipeProfileConflictError("Tu perfil culinario cambió en otra pestaña. Recarga antes de guardar.")
            member = payload["members"][member_id]
            now = _now_iso()
            member["recipe_profile"] = deepcopy(normalized)
            member["recipe_profile_revision"] = before["revision"] + 1
            member.setdefault("recipe_profile_created_at", now)
            member["recipe_profile_updated_at"] = now
            member["recipe_profile_consented_at"] = now
            if normalized["completed"]:
                member.setdefault("recipe_profile_completed_at", now)
            return self._recipe_profile_snapshot(payload, member_id)

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
