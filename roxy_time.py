"""Central UTC clock helpers for legacy-naive and explicit-aware contracts."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return an aware UTC datetime for new contracts."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """Return UTC without tzinfo for compatibility with existing SQLite text fields."""
    return utc_now().replace(tzinfo=None)


def utc_now_naive_iso() -> str:
    """Return the historical naive-UTC ISO representation without using utcnow()."""
    return utc_now_naive().isoformat()
