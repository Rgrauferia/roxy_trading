from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


SHOPPING_STORE_VERSION = 1
SHOPPING_STATUSES = {"PENDING", "PURCHASED", "ARCHIVED"}
SHOPPING_CATEGORIES = {"GENERAL", "FOOD", "HOUSEHOLD", "HEALTH", "PERSONAL", "OTHER"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_shopping_user(value: Any) -> str:
    user = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value or "local_user").strip().lower()).strip("_")
    return user[:96] or "local_user"


def normalize_shopping_name(value: Any) -> str:
    name = " ".join(str(value or "").strip().split())
    if not name:
        raise ValueError("El articulo necesita un nombre.")
    return name[:120]


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_shopping_name(value))
    return " ".join(normalized.encode("ascii", "ignore").decode("ascii").lower().split())


def normalize_quantity(value: Any) -> float:
    try:
        quantity = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("La cantidad debe ser numerica.") from exc
    if not 0 < quantity <= 100_000:
        raise ValueError("La cantidad debe ser mayor que cero y razonable.")
    return round(quantity, 4)


class ShoppingListStore:
    """Atomic local household list shared by UI, voice and text."""

    def __init__(self, path: str | Path = "data/roxy_shopping_list.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": SHOPPING_STORE_VERSION, "updated_at": _now_iso(), "items": [], "user_revisions": {}}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            return self._empty()
        payload["schema_version"] = SHOPPING_STORE_VERSION
        payload["items"] = [item for item in payload["items"] if isinstance(item, dict)]
        if not isinstance(payload.get("user_revisions"), dict):
            payload["user_revisions"] = {}
        return payload

    @staticmethod
    def _revision(payload: dict[str, Any], user: str) -> int:
        revisions = payload.setdefault("user_revisions", {})
        try:
            return max(0, int(revisions.get(user) or 0))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _bump_revision(cls, payload: dict[str, Any], user: str) -> int:
        revision = cls._revision(payload, user) + 1
        payload.setdefault("user_revisions", {})[user] = revision
        return revision

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = SHOPPING_STORE_VERSION
        payload["updated_at"] = _now_iso()
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
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

    def add(
        self,
        user_id: Any,
        name: Any,
        *,
        quantity: Any = 1,
        unit: Any = "unidad",
        category: Any = "GENERAL",
        notes: Any = "",
        source: Any = "ui",
    ) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        display_name = normalize_shopping_name(name)
        item_identity = _identity(display_name)
        amount = normalize_quantity(quantity)
        normalized_category = str(category or "GENERAL").strip().upper()
        if normalized_category not in SHOPPING_CATEGORIES:
            raise ValueError("Categoria de compra no valida.")
        normalized_unit = " ".join(str(unit or "unidad").strip().split())[:32] or "unidad"

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            now = _now_iso()
            for item in payload["items"]:
                if (
                    normalize_shopping_user(item.get("user_id")) == user
                    and str(item.get("identity") or _identity(item.get("name"))) == item_identity
                    and str(item.get("unit") or "unidad").casefold() == normalized_unit.casefold()
                    and str(item.get("status") or "PENDING") == "PENDING"
                ):
                    item["quantity"] = round(float(item.get("quantity") or 0) + amount, 4)
                    item["updated_at"] = now
                    item["source"] = str(source or "ui")[:64]
                    if str(notes or "").strip():
                        item["notes"] = str(notes).strip()[:1000]
                    self._bump_revision(payload, user)
                    return deepcopy(item)
            item = {
                "id": uuid4().hex,
                "user_id": user,
                "name": display_name,
                "identity": item_identity,
                "quantity": amount,
                "unit": normalized_unit,
                "category": normalized_category,
                "notes": str(notes or "").strip()[:1000],
                "status": "PENDING",
                "source": str(source or "ui").strip()[:64] or "ui",
                "created_at": now,
                "updated_at": now,
                "purchased_at": None,
            }
            payload["items"].append(item)
            self._bump_revision(payload, user)
            return deepcopy(item)

        return self._mutate(apply)

    def list_items(
        self,
        user_id: Any,
        *,
        statuses: set[str] | None = None,
        include_archived: bool = False,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        user = normalize_shopping_user(user_id)
        allowed = {str(value).upper() for value in statuses} if statuses else None
        if allowed is not None and not allowed <= SHOPPING_STATUSES:
            raise ValueError("Filtro de compras no valido.")
        rows = []
        for raw in self._read_unlocked().get("items", []):
            if normalize_shopping_user(raw.get("user_id")) != user:
                continue
            status = str(raw.get("status") or "PENDING").upper()
            if allowed is not None and status not in allowed:
                continue
            if not include_archived and status == "ARCHIVED":
                continue
            rows.append(deepcopy(raw))
        rows.sort(
            key=lambda item: (
                str(item.get("status")) != "PENDING",
                str(item.get("category") or "GENERAL"),
                str(item.get("name") or "").casefold(),
            )
        )
        return rows[: max(1, min(int(limit), 1000))]

    def transition(self, user_id: Any, item_id: Any, status: Any) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        target_id = str(item_id or "").strip()
        target = str(status or "").strip().upper()
        if target not in SHOPPING_STATUSES:
            raise ValueError("Estado de compra no valido.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for item in payload["items"]:
                if item.get("id") != target_id or normalize_shopping_user(item.get("user_id")) != user:
                    continue
                current = str(item.get("status") or "PENDING").upper()
                allowed = {
                    "PENDING": {"PURCHASED", "ARCHIVED"},
                    "PURCHASED": {"PENDING", "ARCHIVED"},
                    "ARCHIVED": {"PENDING"},
                }
                if target != current and target not in allowed.get(current, set()):
                    raise ValueError(f"Transicion de {current} a {target} no permitida.")
                now = _now_iso()
                item["status"] = target
                item["updated_at"] = now
                item["purchased_at"] = now if target == "PURCHASED" else None
                if target != current:
                    self._bump_revision(payload, user)
                return deepcopy(item)
            raise KeyError("Articulo no encontrado para este usuario.")

        return self._mutate(apply)

    @staticmethod
    def _normalize_sync_item(raw: Any, user: str) -> dict[str, Any] | None:
        row = raw if isinstance(raw, dict) else {}
        try:
            name = normalize_shopping_name(row.get("name"))
            quantity = normalize_quantity(row.get("quantity") or 1)
        except ValueError:
            return None
        status = str(row.get("status") or "PENDING").upper()
        category = str(row.get("category") or "GENERAL").upper()
        if status not in SHOPPING_STATUSES or category not in SHOPPING_CATEGORIES:
            return None
        item_id = str(row.get("id") or "").lower()
        if not re.fullmatch(r"[a-f0-9]{32}", item_id):
            item_id = uuid4().hex
        unit = " ".join(str(row.get("unit") or "unidad").strip().split())[:32] or "unidad"
        return {
            "id": item_id,
            "user_id": user,
            "name": name,
            "identity": _identity(name),
            "quantity": quantity,
            "unit": unit,
            "category": category,
            "notes": str(row.get("notes") or "")[:1000],
            "status": status,
            "source": str(row.get("source") or "device_sync")[:64],
            "created_at": str(row.get("created_at") or _now_iso())[:64],
            "updated_at": str(row.get("updated_at") or _now_iso())[:64],
            "purchased_at": str(row.get("purchased_at") or "")[:64] or None,
        }

    def replace_user_snapshot(self, user_id: Any, snapshot: Any, *, expected_revision: int) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        incoming = snapshot if isinstance(snapshot, dict) else {}
        raw_items = incoming.get("items") if isinstance(incoming.get("items"), list) else []
        normalized = [item for raw in raw_items[:1000] if (item := self._normalize_sync_item(raw, user)) is not None]

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            current_revision = self._revision(payload, user)
            expected = max(0, int(expected_revision))
            if current_revision != expected:
                return {
                    "updated": False,
                    "conflict": True,
                    "expected_revision": expected,
                    "current_revision": current_revision,
                }
            current = [row for row in payload["items"] if normalize_shopping_user(row.get("user_id")) == user]
            changed = current != normalized
            if changed:
                payload["items"] = [
                    row for row in payload["items"] if normalize_shopping_user(row.get("user_id")) != user
                ] + normalized
                current_revision = self._bump_revision(payload, user)
            return {
                "updated": True,
                "conflict": False,
                "revision": current_revision,
                "items": deepcopy(normalized),
            }

        return self._mutate(apply)

    def snapshot(self, user_id: Any, *, limit: int = 100) -> dict[str, Any]:
        payload = self._read_unlocked()
        items = self.list_items(user_id, include_archived=False, limit=limit)
        return {
            "source": "local_durable",
            "sync_state": "LOCAL_ONLY",
            "updated_at": payload.get("updated_at"),
            "revision": self._revision(payload, normalize_shopping_user(user_id)),
            "pending_count": sum(item.get("status") == "PENDING" for item in items),
            "purchased_count": sum(item.get("status") == "PURCHASED" for item in items),
            "items": items,
        }
