from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from durable_storage import atomic_write_csv, exclusive_file_lock


HISTORY_IDENTITY_FIELDS = ("market", "symbol", "tf", "signal", "score")
HISTORY_VALUE_FIELDS = ("rr_tp2", "entry", "stop", "tp2")


def parse_history_timestamp(value: Any) -> datetime | None:
    try:
        dt = pd.to_datetime(value, utc=True, errors="coerce")
    except Exception:
        return None
    if pd.isna(dt):
        return None
    try:
        return dt.to_pydatetime()
    except Exception:
        return None


def normalize_history_timestamp(value: Any | None = None) -> str:
    dt = parse_history_timestamp(value)
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _same_text(left: Any, right: Any) -> bool:
    return str(left or "").strip().upper() == str(right or "").strip().upper()


def _same_number(left: Any, right: Any, *, tolerance: float = 1e-6) -> bool:
    left_value = pd.to_numeric(left, errors="coerce")
    right_value = pd.to_numeric(right, errors="coerce")
    if pd.isna(left_value) and pd.isna(right_value):
        return True
    if pd.isna(left_value) or pd.isna(right_value):
        return False
    return abs(float(left_value) - float(right_value)) <= tolerance


def scan_history_duplicate(
    previous: dict[str, Any] | pd.Series | None,
    current: dict[str, Any],
    *,
    min_interval_seconds: float = 55.0,
) -> bool:
    if previous is None:
        return False
    if isinstance(previous, pd.Series):
        previous = previous.to_dict()
    previous_ts = parse_history_timestamp(previous.get("ts"))
    current_ts = parse_history_timestamp(current.get("ts"))
    if previous_ts is None or current_ts is None:
        return False
    if abs((current_ts - previous_ts).total_seconds()) > float(min_interval_seconds):
        return False
    for field in HISTORY_IDENTITY_FIELDS:
        if field == "score":
            if not _same_number(previous.get(field), current.get(field), tolerance=0.5):
                return False
        elif not _same_text(previous.get(field), current.get(field)):
            return False
    return all(_same_number(previous.get(field), current.get(field)) for field in HISTORY_VALUE_FIELDS)


def append_scan_history(
    scan_db: str | Path,
    row: dict[str, Any],
    *,
    min_interval_seconds: float = 55.0,
    max_rows: int = 5000,
) -> dict[str, Any]:
    path = Path(scan_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(row)
    record["ts"] = normalize_history_timestamp(record.get("ts"))
    incoming = pd.DataFrame([record])
    with exclusive_file_lock(path):
        existing = pd.DataFrame()
        if path.exists():
            try:
                existing = pd.read_csv(path)
            except EmptyDataError:
                existing = pd.DataFrame()
            except Exception as exc:
                return {
                    "appended": False,
                    "reason": f"unreadable:{type(exc).__name__}",
                    "rows": None,
                }
        if not existing.empty and scan_history_duplicate(
            existing.iloc[-1],
            record,
            min_interval_seconds=min_interval_seconds,
        ):
            return {"appended": False, "reason": "duplicate_recent", "rows": len(existing)}
        combined = incoming if existing.empty else pd.concat([existing, incoming], ignore_index=True)
        if max_rows > 0 and len(combined) > int(max_rows):
            combined = combined.tail(int(max_rows))
        atomic_write_csv(combined, path)
        return {"appended": True, "reason": "new_sample", "rows": len(combined)}


def compact_scan_history(
    scan_db: str | Path,
    *,
    min_interval_seconds: float = 55.0,
    max_rows: int = 5000,
) -> dict[str, Any]:
    path = Path(scan_db)
    if not path.exists():
        return {"compacted": False, "reason": "missing", "before_rows": 0, "after_rows": 0, "removed_rows": 0}
    with exclusive_file_lock(path):
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            return {
                "compacted": False,
                "reason": f"unreadable:{type(exc).__name__}",
                "before_rows": 0,
                "after_rows": 0,
                "removed_rows": 0,
            }
        if df.empty:
            return {"compacted": False, "reason": "empty", "before_rows": 0, "after_rows": 0, "removed_rows": 0}
        kept: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            current = row.to_dict()
            previous = kept[-1] if kept else None
            if previous is not None and scan_history_duplicate(
                previous,
                current,
                min_interval_seconds=min_interval_seconds,
            ):
                continue
            kept.append(current)
        compacted = pd.DataFrame(kept)
        if max_rows > 0 and len(compacted) > int(max_rows):
            compacted = compacted.tail(int(max_rows))
        atomic_write_csv(compacted, path)
        removed = len(df) - len(compacted)
        return {
            "compacted": removed > 0,
            "reason": "deduped" if removed > 0 else "unchanged",
            "before_rows": len(df),
            "after_rows": len(compacted),
            "removed_rows": removed,
        }
