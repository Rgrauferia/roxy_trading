"""Fail-closed JSON/media persistence shared only by Home's private stores.

An initialized marker is not a backup. It prevents a disappeared state file
from being silently treated as a new account after the first attempted commit.
No recovery, copying between households or fallback path is performed here.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterator


class HomePrivateStorageError(RuntimeError):
    def __init__(self, code: str = "unavailable") -> None:
        self.code = code
        self.committed = False
        super().__init__("No se pueden leer o guardar estos datos ahora. No los hemos reemplazado por una lista vacía; necesitan revisión.")

    def __str__(self) -> str:
        if self.committed:
            return "El cambio puede haberse guardado, pero no pudimos confirmar el almacenamiento. Actualiza la sección antes de volver a enviarlo para evitar duplicados."
        return super().__str__()


@contextmanager
def storage_io(error_type: type[HomePrivateStorageError]) -> Iterator[None]:
    try:
        yield
    except OSError as exc:
        raise error_type("io_error") from exc


def initialized_marker(path: Path) -> Path:
    return path.with_name(path.name + ".initialized")


def _exists_strict(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> None:
    raise ValueError("Non-finite JSON number")


def read_private_json(path: Path, empty: Callable[[], dict[str, Any]], valid: Callable[[Any], bool], error_type: type[HomePrivateStorageError]) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        with storage_io(error_type):
            if _exists_strict(initialized_marker(path)) or _exists_strict(path):
                raise error_type("missing_initialized") from exc
        return empty(), "NEW"
    except (OSError, UnicodeError) as exc:
        raise error_type("unreadable") from exc
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except ValueError as exc:
        raise error_type("invalid_json") from exc
    if not valid(value):
        raise error_type("invalid_structure")
    return value, "READY"


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_private_json(path: Path, value: dict[str, Any], valid: Callable[[Any], bool], error_type: type[HomePrivateStorageError]) -> None:
    if not valid(value):
        raise error_type("invalid_structure")
    # Serialize before creating anything. Never partially serialize the live file.
    try:
        encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise error_type("invalid_structure") from exc
    with storage_io(error_type):
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            marker = initialized_marker(path)
            try:
                descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                    stream.write("1\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            # A crash after this point must not make the store look brand new.
            _sync_directory(path.parent)
            os.replace(temporary, path)
            try:
                _sync_directory(path.parent)
            except OSError as exc:
                error = error_type("commit_confirmation_failed")
                error.committed = True
                raise error from exc
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def write_new_private_media(path: Path, raw: bytes, error_type: type[HomePrivateStorageError]) -> None:
    """Write one unique new media file; never overwrite an existing photograph."""
    created = False
    try:
        with storage_io(error_type):
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            _sync_directory(path.parent)
    except Exception:
        if created:
            discard_new_media(path)
        raise


def discard_new_media(path: Path) -> None:
    """Best-effort rollback for an exact newly-created, uncommitted media path."""
    try:
        path.unlink()
    except OSError:
        pass
