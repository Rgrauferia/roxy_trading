from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


DOCUMENT_VAULT_CONTRACT = "roxy-document-vault/1.1.0"
ALLOWED_DOCUMENT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".pdf", ".docx", ".xlsx"}
TEXT_PREVIEW_SUFFIXES = {".txt", ".md", ".csv", ".json"}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ENCRYPTED_OBJECT_HEADER = b"ROXYDOC1"
ENCRYPTION_ALGORITHM = "AES-256-GCM"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_document_user(value: Any) -> str:
    user = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value or "local_user").strip().lower()).strip("_")
    return user[:96] or "local_user"


def sanitize_document_name(value: Any) -> str:
    raw = Path(str(value or "").replace("\\", "/")).name
    name = re.sub(r"[^a-zA-Z0-9ÁÉÍÓÚÜÑáéíóúüñ._() -]+", "_", raw).strip(" .")[:180]
    if not name or name in {".", ".."}:
        raise ValueError("El documento necesita un nombre valido.")
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_SUFFIXES:
        raise ValueError("Tipo de documento no permitido.")
    return name


class DocumentVault:
    """Private local document registry with recoverable metadata lifecycle."""

    def __init__(self, root: str | Path = "data/roxy_documents", *, key_path: str | Path | None = None) -> None:
        self.root = Path(root)
        self.index_path = self.root / "index.json"
        self.lock_path = self.root / "index.lock"
        self.objects = self.root / "objects"
        configured_key_path = str(os.environ.get("ROXY_DOCUMENT_VAULT_KEY_FILE") or "").strip()
        self.key_path = Path(key_path or configured_key_path or Path.home() / "Library" / "Application Support" / "RoxyTrading" / "document_vault.key")

    def _encryption_key(self) -> bytes:
        self.key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.key_path.is_symlink():
            raise RuntimeError("La ruta de la clave documental no puede ser un enlace simbolico.")
        key_lock_path = self.key_path.with_suffix(self.key_path.suffix + ".lock")
        try:
            with key_lock_path.open("a+b") as key_lock:
                try:
                    key_lock_path.chmod(0o600)
                except OSError:
                    pass
                if fcntl is not None:
                    fcntl.flock(key_lock.fileno(), fcntl.LOCK_EX)
                if self.key_path.is_symlink():
                    raise RuntimeError("La ruta de la clave documental no puede ser un enlace simbolico.")
                try:
                    key = self.key_path.read_bytes()
                except FileNotFoundError:
                    key = AESGCM.generate_key(bit_length=256)
                    handle, temp_name = tempfile.mkstemp(prefix=".document-vault-key.", dir=str(self.key_path.parent))
                    try:
                        with os.fdopen(handle, "wb") as stream:
                            stream.write(key)
                            stream.flush()
                            os.fsync(stream.fileno())
                        os.chmod(temp_name, 0o600)
                        os.replace(temp_name, self.key_path)
                    finally:
                        try:
                            os.unlink(temp_name)
                        except FileNotFoundError:
                            pass
                finally:
                    if fcntl is not None:
                        fcntl.flock(key_lock.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise RuntimeError("No se pudo leer la clave privada del repositorio documental.") from exc
        if len(key) != 32:
            raise RuntimeError("La clave documental debe contener exactamente 32 bytes.")
        try:
            self.key_path.chmod(0o600)
        except OSError:
            pass
        return key

    @staticmethod
    def _encrypt(data: bytes, digest: str, key: bytes) -> bytes:
        nonce = os.urandom(12)
        return ENCRYPTED_OBJECT_HEADER + nonce + AESGCM(key).encrypt(nonce, data, digest.encode("ascii"))

    @staticmethod
    def _decrypt(data: bytes, digest: str, key: bytes) -> bytes:
        if not data.startswith(ENCRYPTED_OBJECT_HEADER):
            return data
        offset = len(ENCRYPTED_OBJECT_HEADER)
        nonce, ciphertext = data[offset:offset + 12], data[offset + 12:]
        if len(nonce) != 12 or not ciphertext:
            raise ValueError("El objeto cifrado esta incompleto.")
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, digest.encode("ascii"))
        except InvalidTag as exc:
            raise ValueError("La autenticacion del contenido cifrado no coincide.") from exc

    def _replace_object(self, path: Path, data: bytes) -> None:
        handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.objects.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.root.chmod(0o700)
            self.objects.chmod(0o700)
        except OSError:
            pass

    def _empty(self) -> dict[str, Any]:
        return {"contract_version": DOCUMENT_VAULT_CONTRACT, "updated_at": _now_iso(), "encryption_key_id": "", "documents": []}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
            return self._empty()
        payload["documents"] = [row for row in payload["documents"] if isinstance(row, dict)]
        payload["contract_version"] = DOCUMENT_VAULT_CONTRACT
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self._prepare()
        payload["contract_version"] = DOCUMENT_VAULT_CONTRACT
        payload["updated_at"] = _now_iso()
        handle, temp_name = tempfile.mkstemp(prefix=".index.", suffix=".tmp", dir=str(self.root))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.index_path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _mutate(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self._prepare()
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

    def ingest(
        self,
        user_id: Any,
        filename: Any,
        content: bytes,
        *,
        content_type: Any = "application/octet-stream",
        source: Any = "upload",
    ) -> dict[str, Any]:
        user = normalize_document_user(user_id)
        name = sanitize_document_name(filename)
        data = bytes(content or b"")
        if not data:
            raise ValueError("El documento esta vacio.")
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValueError("El documento supera el limite de 10 MB.")
        digest = hashlib.sha256(data).hexdigest()
        self.migrate_plaintext_objects()

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for row in payload["documents"]:
                if row.get("user_id") == user and row.get("sha256") == digest and row.get("status") == "ACTIVE":
                    return deepcopy(row)
            object_dir = self.objects / digest[:2]
            object_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            object_path = object_dir / digest
            key = self._encryption_key()
            payload["encryption_key_id"] = hashlib.sha256(key).hexdigest()[:16]
            if not object_path.exists():
                handle, temp_name = tempfile.mkstemp(prefix=f".{digest}.", suffix=".tmp", dir=str(object_dir))
                try:
                    with os.fdopen(handle, "wb") as stream:
                        stream.write(self._encrypt(data, digest, key))
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.chmod(temp_name, 0o600)
                    os.replace(temp_name, object_path)
                finally:
                    try:
                        os.unlink(temp_name)
                    except FileNotFoundError:
                        pass
            now = _now_iso()
            row = {
                "id": uuid4().hex,
                "user_id": user,
                "name": name,
                "suffix": Path(name).suffix.lower(),
                "content_type": str(content_type or "application/octet-stream")[:120],
                "size_bytes": len(data),
                "sha256": digest,
                "status": "ACTIVE",
                "source": str(source or "upload")[:64],
                "created_at": now,
                "updated_at": now,
                "archived_at": None,
                "encryption": ENCRYPTION_ALGORITHM,
            }
            payload["documents"].append(row)
            return deepcopy(row)

        return self._mutate(apply)

    def list_documents(self, user_id: Any, *, include_archived: bool = False, limit: int = 200) -> list[dict[str, Any]]:
        user = normalize_document_user(user_id)
        rows = [
            deepcopy(row)
            for row in self._read_unlocked().get("documents", [])
            if row.get("user_id") == user and (include_archived or row.get("status") != "ARCHIVED")
        ]
        rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        return rows[: max(1, min(int(limit), 1000))]

    def archive(self, user_id: Any, document_id: Any, *, restore: bool = False) -> dict[str, Any]:
        user = normalize_document_user(user_id)
        target = str(document_id or "")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for row in payload["documents"]:
                if row.get("id") != target or row.get("user_id") != user:
                    continue
                now = _now_iso()
                row["status"] = "ACTIVE" if restore else "ARCHIVED"
                row["updated_at"] = now
                row["archived_at"] = None if restore else now
                return deepcopy(row)
            raise KeyError("Documento no encontrado para este usuario.")

        return self._mutate(apply)

    def read(self, user_id: Any, document_id: Any) -> tuple[dict[str, Any], bytes]:
        user = normalize_document_user(user_id)
        target = str(document_id or "")
        payload = self._read_unlocked()
        key = self._encryption_key()
        expected_key_id = str(payload.get("encryption_key_id") or "")
        if expected_key_id and expected_key_id != hashlib.sha256(key).hexdigest()[:16]:
            raise RuntimeError("La clave documental activa no corresponde a este repositorio.")
        for row in payload.get("documents", []):
            if row.get("id") == target and row.get("user_id") == user and row.get("status") == "ACTIVE":
                path = self.objects / str(row.get("sha256") or "")[:2] / str(row.get("sha256") or "")
                try:
                    stored = path.read_bytes()
                except OSError as exc:
                    raise FileNotFoundError("El contenido del documento no esta disponible.") from exc
                data = self._decrypt(stored, str(row.get("sha256") or ""), key)
                if hashlib.sha256(data).hexdigest() != row.get("sha256"):
                    raise ValueError("La integridad SHA-256 del documento no coincide.")
                return deepcopy(row), data
        raise KeyError("Documento activo no encontrado para este usuario.")

    def migrate_plaintext_objects(self) -> dict[str, Any]:
        """Atomically encrypt legacy objects; safe to run repeatedly."""
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            key = self._encryption_key()
            key_id = hashlib.sha256(key).hexdigest()[:16]
            expected_key_id = str(payload.get("encryption_key_id") or "")
            if expected_key_id and expected_key_id != key_id:
                raise RuntimeError("La clave documental activa no corresponde a este repositorio.")
            payload["encryption_key_id"] = key_id
            encrypted = 0
            already_encrypted = 0
            missing = 0
            for digest in sorted({str(row.get("sha256") or "") for row in payload["documents"] if row.get("sha256")}):
                path = self.objects / digest[:2] / digest
                try:
                    stored = path.read_bytes()
                except OSError:
                    missing += 1
                    continue
                if stored.startswith(ENCRYPTED_OBJECT_HEADER):
                    self._decrypt(stored, digest, key)
                    already_encrypted += 1
                else:
                    if hashlib.sha256(stored).hexdigest() != digest:
                        raise ValueError(f"La integridad del objeto {digest[:12]} no coincide; migracion detenida.")
                    self._replace_object(path, self._encrypt(stored, digest, key))
                    encrypted += 1
                for row in payload["documents"]:
                    if row.get("sha256") == digest:
                        row["encryption"] = ENCRYPTION_ALGORITHM
                        row["updated_at"] = _now_iso()
            return {"encrypted": encrypted, "already_encrypted": already_encrypted, "missing": missing}

        return self._mutate(apply)

    def snapshot(self, user_id: Any, *, limit: int = 50) -> dict[str, Any]:
        payload = self._read_unlocked()
        documents = self.list_documents(user_id, limit=limit)
        all_rows = [row for row in payload.get("documents", []) if row.get("user_id") == normalize_document_user(user_id)]
        encrypted_count = sum(1 for row in all_rows if row.get("encryption") == ENCRYPTION_ALGORITHM)
        try:
            key_id = hashlib.sha256(self._encryption_key()).hexdigest()[:16]
            key_status = "READY" if not payload.get("encryption_key_id") or payload.get("encryption_key_id") == key_id else "KEY_MISMATCH"
        except RuntimeError:
            key_status = "UNAVAILABLE"
        encryption_ready = encrypted_count == len(all_rows) and key_status == "READY"
        return {
            "contract_version": DOCUMENT_VAULT_CONTRACT,
            "source": "local_private_filesystem",
            "sync_state": "LOCAL_ENCRYPTED" if encryption_ready else "LOCAL_MIXED_ENCRYPTION",
            "at_rest_encryption": encryption_ready,
            "encryption_algorithm": ENCRYPTION_ALGORITHM,
            "encryption_key_status": key_status,
            "encrypted_count": encrypted_count,
            "unencrypted_count": len(all_rows) - encrypted_count,
            "updated_at": payload.get("updated_at"),
            "active_count": len(documents),
            "documents": documents,
        }
