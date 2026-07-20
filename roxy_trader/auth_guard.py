from __future__ import annotations

import hashlib
import math
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


PASSWORD_LEGACY_ITERATIONS = 160_000
PASSWORD_ITERATIONS = 600_000
PASSWORD_MIN_LENGTH = 10
SESSION_MAX_AGE_SECONDS_DEFAULT = 30 * 24 * 60 * 60
AUTH_MAX_FAILURES = 5
AUTH_WINDOW_SECONDS = 15 * 60
AUTH_LOCK_SECONDS = 15 * 60


@dataclass(frozen=True)
class AuthAttemptStatus:
    allowed: bool
    failures: int = 0
    retry_after_seconds: int = 0


class AuthAttemptGuard:
    """Persistent, privacy-preserving account login throttle."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        max_failures: int = AUTH_MAX_FAILURES,
        window_seconds: int = AUTH_WINDOW_SECONDS,
        lock_seconds: int = AUTH_LOCK_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.db_path = Path(db_path)
        self.max_failures = max(1, int(max_failures))
        self.window_seconds = max(1, int(window_seconds))
        self.lock_seconds = max(1, int(lock_seconds))
        self.clock = clock
        self._initialize()

    @staticmethod
    def _key(identifier: str) -> str:
        normalized = str(identifier or "").strip().casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS roxy_auth_attempts (
                    identifier_hash TEXT PRIMARY KEY,
                    failures INTEGER NOT NULL,
                    window_started_at REAL NOT NULL,
                    locked_until REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_roxy_auth_attempts_updated "
                "ON roxy_auth_attempts(updated_at)"
            )
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def status(self, identifier: str, *, now: float | None = None) -> AuthAttemptStatus:
        current = float(self.clock() if now is None else now)
        key = self._key(identifier)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT failures, window_started_at, locked_until "
                "FROM roxy_auth_attempts WHERE identifier_hash = ?",
                (key,),
            ).fetchone()
            if row is None:
                return AuthAttemptStatus(True)
            failures, window_started_at, locked_until = int(row[0]), float(row[1]), float(row[2])
            if locked_until > current:
                return AuthAttemptStatus(
                    False,
                    failures=failures,
                    retry_after_seconds=max(1, int(math.ceil(locked_until - current))),
                )
            if current - window_started_at >= self.window_seconds:
                conn.execute("DELETE FROM roxy_auth_attempts WHERE identifier_hash = ?", (key,))
                return AuthAttemptStatus(True)
            return AuthAttemptStatus(True, failures=failures)

    def record_failure(self, identifier: str, *, now: float | None = None) -> AuthAttemptStatus:
        current = float(self.clock() if now is None else now)
        key = self._key(identifier)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT failures, window_started_at, locked_until "
                "FROM roxy_auth_attempts WHERE identifier_hash = ?",
                (key,),
            ).fetchone()
            if row is None or current - float(row[1]) >= self.window_seconds:
                failures = 1
                window_started_at = current
                locked_until = 0.0
            else:
                failures = int(row[0]) + 1
                window_started_at = float(row[1])
                locked_until = max(0.0, float(row[2]))
            if failures >= self.max_failures:
                locked_until = max(locked_until, current + self.lock_seconds)
            conn.execute(
                """
                INSERT INTO roxy_auth_attempts
                    (identifier_hash, failures, window_started_at, locked_until, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(identifier_hash) DO UPDATE SET
                    failures=excluded.failures,
                    window_started_at=excluded.window_started_at,
                    locked_until=excluded.locked_until,
                    updated_at=excluded.updated_at
                """,
                (key, failures, window_started_at, locked_until, current),
            )
        if locked_until > current:
            return AuthAttemptStatus(
                False,
                failures=failures,
                retry_after_seconds=max(1, int(math.ceil(locked_until - current))),
            )
        return AuthAttemptStatus(True, failures=failures)

    def clear(self, identifier: str) -> None:
        key = self._key(identifier)
        with self._connect() as conn:
            conn.execute("DELETE FROM roxy_auth_attempts WHERE identifier_hash = ?", (key,))

    def prune(self, *, now: float | None = None, retention_seconds: int = 24 * 60 * 60) -> int:
        current = float(self.clock() if now is None else now)
        cutoff = current - max(self.window_seconds, int(retention_seconds))
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM roxy_auth_attempts WHERE updated_at < ? AND locked_until <= ?",
                (cutoff, current),
            )
            return max(0, int(cursor.rowcount or 0))
