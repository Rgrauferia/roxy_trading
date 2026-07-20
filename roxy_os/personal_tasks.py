from __future__ import annotations

import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


TASK_STORE_VERSION = 1
TASK_STATUSES = {"PENDING", "IN_PROGRESS", "DONE", "ARCHIVED"}
TASK_PRIORITIES = {"LOW", "NORMAL", "HIGH", "URGENT"}
ACTIVE_TASK_STATUSES = {"PENDING", "IN_PROGRESS"}
ALLOWED_TRANSITIONS = {
    "PENDING": {"IN_PROGRESS", "DONE", "ARCHIVED"},
    "IN_PROGRESS": {"PENDING", "DONE", "ARCHIVED"},
    "DONE": {"PENDING", "ARCHIVED"},
    "ARCHIVED": {"PENDING"},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_task_user(value: Any) -> str:
    user = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value or "local_user").strip().lower()).strip("_")
    return user[:96] or "local_user"


def normalize_task_title(value: Any) -> str:
    title = " ".join(str(value or "").strip().split())
    if not title:
        raise ValueError("La tarea necesita un titulo.")
    return title[:180]


def normalize_task_due_at(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("La fecha limite debe usar formato ISO valido.") from exc
    if parsed.tzinfo is None:
        raise ValueError("La fecha limite debe incluir zona horaria.")
    return parsed.astimezone(timezone.utc).isoformat()


class PersonalTaskStore:
    """Atomic, user-isolated local task storage shared by UI, text and voice."""

    def __init__(self, path: str | Path = "data/roxy_personal_tasks.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": TASK_STORE_VERSION, "updated_at": _now_iso(), "tasks": [], "user_revisions": {}}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
            return self._empty()
        payload["schema_version"] = TASK_STORE_VERSION
        payload["tasks"] = [task for task in payload["tasks"] if isinstance(task, dict)]
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
        payload["schema_version"] = TASK_STORE_VERSION
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

    def create(
        self,
        user_id: Any,
        title: Any,
        *,
        notes: Any = "",
        due_at: Any = None,
        priority: Any = "NORMAL",
        source: Any = "ui",
    ) -> dict[str, Any]:
        user = normalize_task_user(user_id)
        normalized_priority = str(priority or "NORMAL").strip().upper()
        if normalized_priority not in TASK_PRIORITIES:
            raise ValueError("Prioridad de tarea no valida.")
        now = _now_iso()
        task = {
            "id": uuid4().hex,
            "user_id": user,
            "title": normalize_task_title(title),
            "notes": str(notes or "").strip()[:2000],
            "due_at": normalize_task_due_at(due_at),
            "priority": normalized_priority,
            "status": "PENDING",
            "source": str(source or "ui").strip()[:64] or "ui",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }

        def add(payload: dict[str, Any]) -> dict[str, Any]:
            payload["tasks"].append(task)
            self._bump_revision(payload, user)
            return deepcopy(task)

        return self._mutate(add)

    def list_tasks(
        self,
        user_id: Any,
        *,
        statuses: set[str] | None = None,
        include_archived: bool = False,
        limit: int = 200,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        user = normalize_task_user(user_id)
        allowed = {str(value).upper() for value in statuses} if statuses else None
        if allowed is not None and not allowed <= TASK_STATUSES:
            raise ValueError("Filtro de estado no valido.")
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        rows: list[dict[str, Any]] = []
        for raw in self._read_unlocked().get("tasks", []):
            if normalize_task_user(raw.get("user_id")) != user:
                continue
            status = str(raw.get("status") or "PENDING").upper()
            if allowed is not None and status not in allowed:
                continue
            if not include_archived and status == "ARCHIVED":
                continue
            task = deepcopy(raw)
            task["overdue"] = False
            if status in ACTIVE_TASK_STATUSES and task.get("due_at"):
                try:
                    due = datetime.fromisoformat(str(task["due_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)
                    task["overdue"] = due < current
                except (TypeError, ValueError):
                    task["due_at"] = None
            rows.append(task)
        priority_order = {"URGENT": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}
        rows.sort(
            key=lambda task: (
                str(task.get("status")) not in ACTIVE_TASK_STATUSES,
                task.get("due_at") is None,
                str(task.get("due_at") or "9999"),
                priority_order.get(str(task.get("priority")), 9),
                str(task.get("created_at") or ""),
            )
        )
        return rows[: max(1, min(int(limit), 1000))]

    def transition(self, user_id: Any, task_id: Any, status: Any) -> dict[str, Any]:
        user = normalize_task_user(user_id)
        target_id = str(task_id or "").strip()
        target_status = str(status or "").strip().upper()
        if target_status not in TASK_STATUSES:
            raise ValueError("Estado de tarea no valido.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for task in payload["tasks"]:
                if task.get("id") != target_id or normalize_task_user(task.get("user_id")) != user:
                    continue
                current = str(task.get("status") or "PENDING").upper()
                if target_status == current:
                    return deepcopy(task)
                if target_status not in ALLOWED_TRANSITIONS.get(current, set()):
                    raise ValueError(f"Transicion de {current} a {target_status} no permitida.")
                now = _now_iso()
                task["status"] = target_status
                task["updated_at"] = now
                task["completed_at"] = now if target_status == "DONE" else None
                self._bump_revision(payload, user)
                return deepcopy(task)
            raise KeyError("Tarea no encontrada para este usuario.")

        return self._mutate(apply)

    @staticmethod
    def _normalize_sync_task(raw: Any, user: str) -> dict[str, Any] | None:
        row = raw if isinstance(raw, dict) else {}
        try:
            title = normalize_task_title(row.get("title"))
            due_at = normalize_task_due_at(row.get("due_at"))
        except ValueError:
            return None
        status = str(row.get("status") or "PENDING").upper()
        priority = str(row.get("priority") or "NORMAL").upper()
        if status not in TASK_STATUSES or priority not in TASK_PRIORITIES:
            return None
        task_id = str(row.get("id") or "").lower()
        if not re.fullmatch(r"[a-f0-9]{32}", task_id):
            task_id = uuid4().hex
        return {
            "id": task_id,
            "user_id": user,
            "title": title,
            "notes": str(row.get("notes") or "")[:2000],
            "due_at": due_at,
            "priority": priority,
            "status": status,
            "source": str(row.get("source") or "device_sync")[:64],
            "created_at": str(row.get("created_at") or _now_iso())[:64],
            "updated_at": str(row.get("updated_at") or _now_iso())[:64],
            "completed_at": str(row.get("completed_at") or "")[:64] or None,
        }

    def replace_user_snapshot(self, user_id: Any, snapshot: Any, *, expected_revision: int) -> dict[str, Any]:
        user = normalize_task_user(user_id)
        incoming = snapshot if isinstance(snapshot, dict) else {}
        raw_tasks = incoming.get("tasks") if isinstance(incoming.get("tasks"), list) else []
        normalized = [task for raw in raw_tasks[:1000] if (task := self._normalize_sync_task(raw, user)) is not None]

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
            current = [row for row in payload["tasks"] if normalize_task_user(row.get("user_id")) == user]
            changed = current != normalized
            if changed:
                payload["tasks"] = [
                    row for row in payload["tasks"] if normalize_task_user(row.get("user_id")) != user
                ] + normalized
                current_revision = self._bump_revision(payload, user)
            return {
                "updated": True,
                "conflict": False,
                "revision": current_revision,
                "tasks": deepcopy(normalized),
            }

        return self._mutate(apply)

    def snapshot(self, user_id: Any, *, limit: int = 25) -> dict[str, Any]:
        payload = self._read_unlocked()
        tasks = self.list_tasks(user_id, include_archived=False, limit=limit)
        return {
            "source": "local_durable",
            "sync_state": "LOCAL_ONLY",
            "updated_at": payload.get("updated_at"),
            "revision": self._revision(payload, normalize_task_user(user_id)),
            "active_count": sum(task.get("status") in ACTIVE_TASK_STATUSES for task in tasks),
            "overdue_count": sum(bool(task.get("overdue")) for task in tasks),
            "tasks": tasks,
        }
