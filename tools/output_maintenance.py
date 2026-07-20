from __future__ import annotations

import argparse
import csv
import fnmatch
import io
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from typing import Mapping


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from roxy_paths import alerts_dir, output_dir
from durable_storage import atomic_write_text, exclusive_file_lock

OUTPUT_DIR = output_dir()
ALERTS_DIR = alerts_dir()
LOG_DIR = BASE_DIR / "logs"
LAUNCHD_LOG_DIR = Path.home() / "Library" / "Logs" / "RoxyTrading"
DEFAULT_EXTERNAL_DISK_PATH = Path("/Volumes/RoxyData")
DEFAULT_LOG_SNAPSHOT_DIR = Path("/Volumes/RoxyData/MacArchive/log_snapshots")
DEFAULT_OUTPUT_ARCHIVE_DIR = DEFAULT_EXTERNAL_DISK_PATH / "MacArchive" / "roxy_trading" / "output_archive"
DEFAULT_LOCAL_OUTPUT_ARCHIVE_DIR = OUTPUT_DIR / "maintenance_archive"
DEFAULT_JSON_PATH = ALERTS_DIR / "output_maintenance.json"
DEFAULT_TEXT_PATH = ALERTS_DIR / "output_maintenance.txt"
DEFAULT_DB_PATH = BASE_DIR / "db" / "roxy.db"
DEFAULT_DASHBOARD_HISTORY_PATH = BASE_DIR / "db" / "scan_history.csv"

LIVE_RETENTION_PATTERNS = (
    "ma_live_strategy_*.csv",
    "ma_confluence_*.csv",
    "options_candidates_*.csv",
)

DAILY_RETENTION_PATTERNS = (
    "ma_strategy_*.csv",
    "ma_backtest_summary_*.csv",
    "ma_backtest_trades_*.csv",
)

APP_SCAN_RETENTION_PATTERNS = (
    "stocks_tech_*.csv",
    "stocks_growth_*.csv",
    "crypto_tech_*.csv",
)
STALE_OUTPUT_MAX_AGE_DAYS_RULES: dict[str, float] = {
    "fine_sweep_*": 7.0,
    "sweep_summary*": 7.0,
    "synthetic_ohlcv.csv": 7.0,
    "analysis_best_runs.csv": 7.0,
    "ma_ai_development_test_*.csv": 7.0,
    "ma_crypto_ai_development_test_*.csv": 7.0,
    "plots/fine_sweep_*.png": 7.0,
    "plots/sweep_*.png": 7.0,
    "plots/analysis_fine_sweep_*.png": 30.0,
    "backtests/fine_sweep_*.json": 30.0,
    "backtest_batch_summary_*.json": 30.0,
}

DEFAULT_RETENTION_RULES: dict[str, int] = {
    **{pattern: 96 for pattern in LIVE_RETENTION_PATTERNS},
    **{pattern: 30 for pattern in DAILY_RETENTION_PATTERNS},
    **{pattern: 48 for pattern in APP_SCAN_RETENTION_PATTERNS},
}

DEFAULT_LOG_PATTERNS = ("*.log", "*.out", "*.err")
DEFAULT_HISTORY_FILES = (
    "alert_quality_history.jsonl",
    "notification_history.jsonl",
    "roxy_realtime_history.jsonl",
    "roxy_learning_journal.csv",
)
DEFAULT_ALERT_REPORT_RETENTION_RULES: dict[str, int] = {
    "weekly_report_*.json": 12,
    "weekly_report_*.txt": 12,
}
DEFAULT_MAX_LOG_BYTES = 2_000_000
DEFAULT_MAX_HISTORY_LINES = 500
DEFAULT_MAX_HISTORY_BYTES = 7_500_000
DEFAULT_HISTORY_FILE_MAX_BYTES: dict[str, int] = {
    "alert_quality_history.jsonl": 2_000_000,
    "notification_history.jsonl": 1_000_000,
    "roxy_realtime_history.jsonl": DEFAULT_MAX_HISTORY_BYTES,
}
DEFAULT_MIN_HISTORY_LINES = 120
DEFAULT_HISTORY_BUDGET_WARN_RATIO = 0.85
DEFAULT_HISTORY_CAP_TARGET_RATIO = 0.80
DEFAULT_HISTORY_LOW_LINE_MARGIN_RATIO = 0.02
DEFAULT_HISTORY_BYTE_PROJECTION_LINES = 4
DEFAULT_HISTORY_MIN_APPENDS_UNTIL_WARN = 8
DEFAULT_HISTORY_APPEND_GUARD_TARGET_BUFFER = 4
DEFAULT_HISTORY_MIN_LINE_FLOOR_RATIO = 0.50
DEFAULT_LOG_SNAPSHOT_KEEP_COUNT = 20
DEFAULT_LOG_SNAPSHOT_SCAN_TIMEOUT_SECONDS = 5.0
DEFAULT_SQLITE_VACUUM_MIN_RECLAIM_MB = 64.0
DEFAULT_DASHBOARD_HISTORY_MAX_ROWS = 5000
DEFAULT_DASHBOARD_HISTORY_MIN_INTERVAL_SECONDS = 55.0
DEFAULT_LOCAL_STORAGE_PRESSURE_REPORT_PATH = ALERTS_DIR / "local_storage_pressure_sources.json"
DEFAULT_LOCAL_CACHE_CLEANUP_MIN_AGE_DAYS = 7.0
DEFAULT_LOCAL_CACHE_CLEANUP_MAX_BYTES = 512 * 1024 * 1024
DEFAULT_TRAINING_VIDEOS_PATH = BASE_DIR / "training_videos"


def effective_history_max_bytes(name: str, configured_max_bytes: int | None) -> int:
    configured = max(0, int(configured_max_bytes or 0))
    file_limit = max(0, int(DEFAULT_HISTORY_FILE_MAX_BYTES.get(str(name), 0) or 0))
    if configured and file_limit:
        return min(configured, file_limit)
    if configured:
        return configured
    return file_limit


def effective_history_min_lines_for_byte_target(
    history_path: str | Path,
    *,
    max_lines: int,
    min_lines: int,
    target_bytes: int,
    floor_ratio: float = DEFAULT_HISTORY_MIN_LINE_FLOOR_RATIO,
) -> dict[str, Any]:
    max_lines = max(1, int(max_lines))
    min_lines = max(1, min(int(min_lines), max_lines))
    target_bytes = max(0, int(target_bytes))
    floor_ratio = max(0.0, min(float(floor_ratio), 1.0))
    floor_lines = max(1, min(min_lines, int(min_lines * floor_ratio)))
    if min_lines > 1 and floor_lines >= min_lines:
        floor_lines = min_lines - 1
    path = Path(history_path)
    if not path.exists() or not path.is_file() or target_bytes <= 0:
        return {
            "configured_min_lines": min_lines,
            "effective_min_lines": min_lines,
            "min_line_floor": floor_lines,
            "target_fit_lines": None,
            "target_fit_bytes": None,
            "min_lines_relaxed": False,
        }
    lines = path.read_text(errors="replace").splitlines()[-max_lines:]
    fit_count = 0
    fit_bytes = 1
    for line in reversed(lines):
        line_bytes = len(line.encode()) + 1
        if fit_count and fit_bytes + line_bytes > target_bytes:
            break
        fit_count += 1
        fit_bytes += line_bytes
    effective_min_lines = min_lines
    if fit_count and fit_count < min_lines:
        effective_min_lines = max(floor_lines, fit_count)
    return {
        "configured_min_lines": min_lines,
        "effective_min_lines": effective_min_lines,
        "min_line_floor": floor_lines,
        "target_fit_lines": fit_count,
        "target_fit_bytes": fit_bytes if fit_count else None,
        "min_lines_relaxed": effective_min_lines < min_lines,
    }
SAFE_LOCAL_CACHE_CLEANUP_NAMES = (".cache", "Library/Caches")


def directory_footprint(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    files = 0
    ignored_lock_files = 0
    bytes_total = 0
    if not root.exists():
        return {"path": str(root), "exists": False, "files": 0, "bytes": 0, "mb": 0.0}
    if root.is_file():
        try:
            bytes_total = root.stat().st_size
        except OSError:
            bytes_total = 0
        return {"path": str(root), "exists": True, "files": 1, "bytes": bytes_total, "mb": round(bytes_total / (1024**2), 3)}
    for child in root.rglob("*"):
        if not child.is_file():
            continue
        try:
            child_size = child.stat().st_size
            if child.name.startswith(".") and child.name.endswith(".lock") and child_size == 0:
                ignored_lock_files += 1
                continue
            bytes_total += child_size
            files += 1
        except OSError:
            continue
    return {
        "path": str(root),
        "exists": True,
        "files": files,
        "ignored_lock_files": ignored_lock_files,
        "bytes": bytes_total,
        "mb": round(bytes_total / (1024**2), 3),
    }


def runtime_footprint(
    *,
    output_dir: str | Path = OUTPUT_DIR,
    alerts_path: str | Path = ALERTS_DIR,
    log_dirs: list[str | Path] | None = None,
) -> dict[str, Any]:
    selected_log_dirs = log_dirs or [LOG_DIR, LAUNCHD_LOG_DIR]
    output = directory_footprint(output_dir)
    alerts = directory_footprint(alerts_path)
    logs = [directory_footprint(path) for path in selected_log_dirs]
    total_bytes = int(output["bytes"]) + int(alerts["bytes"]) + sum(int(item["bytes"]) for item in logs)
    total_files = int(output["files"]) + int(alerts["files"]) + sum(int(item["files"]) for item in logs)
    return {
        "output": output,
        "alerts": alerts,
        "logs": logs,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024**2), 3),
    }


def files_for_pattern(output_dir: Path, pattern: str) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted(
        [path for path in output_dir.glob(pattern) if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def default_output_archive_dir() -> Path | None:
    configured = str(os.getenv("ROXY_OUTPUT_ARCHIVE_DIR") or "").strip()
    # A removable/network volume must never be an implicit dependency of the
    # health watchdog. Operators can opt in with an explicit path.
    return Path(configured).expanduser() if configured else DEFAULT_LOCAL_OUTPUT_ARCHIVE_DIR


def resolve_output_archive_dir(
    requested_dir: str | Path | None,
    *,
    fallback_dir: str | Path | None = DEFAULT_LOCAL_OUTPUT_ARCHIVE_DIR,
    dry_run: bool = False,
) -> dict[str, Any]:
    requested = Path(requested_dir) if requested_dir else None
    fallback = Path(fallback_dir) if fallback_dir else None
    if requested is None:
        return {
            "requested_dir": "",
            "effective_dir": "",
            "fallback": False,
            "fallback_reason": "",
            "writable": False,
        }
    if dry_run:
        return {
            "requested_dir": str(requested),
            "effective_dir": str(requested),
            "fallback": False,
            "fallback_reason": "dry-run: write probe skipped",
            "writable": requested.exists() and requested.is_dir(),
        }
    requested_probe_root = requested
    while not requested_probe_root.exists() and requested_probe_root.parent != requested_probe_root:
        requested_probe_root = requested_probe_root.parent
    probe = requested_probe_root / f".roxy_maintenance_write_test_{os.getpid()}"
    try:
        if not requested_probe_root.is_dir():
            raise OSError(f"archive ancestor is not a directory: {requested_probe_root}")
        probe.write_text("ok")
        if probe.read_text() != "ok":
            raise OSError("archive write verification failed")
        return {
            "requested_dir": str(requested),
            "effective_dir": str(requested),
            "fallback": False,
            "fallback_reason": "",
            "writable": True,
        }
    except OSError as exc:
        if fallback is None:
            return {
                "requested_dir": str(requested),
                "effective_dir": str(requested),
                "fallback": False,
                "fallback_reason": f"{type(exc).__name__}: {exc}",
                "writable": False,
            }
        fallback_probe_root = fallback
        while not fallback_probe_root.exists() and fallback_probe_root.parent != fallback_probe_root:
            fallback_probe_root = fallback_probe_root.parent
        fallback_probe = fallback_probe_root / f".roxy_maintenance_write_test_{os.getpid()}"
        try:
            if not fallback_probe_root.is_dir():
                raise OSError(f"fallback archive ancestor is not a directory: {fallback_probe_root}")
            fallback_probe.write_text("ok")
            if fallback_probe.read_text() != "ok":
                raise OSError("fallback archive write verification failed")
        except OSError as fallback_exc:
            return {
                "requested_dir": str(requested),
                "effective_dir": str(requested),
                "fallback": False,
                "fallback_reason": (
                    f"primary {type(exc).__name__}: {exc}; "
                    f"fallback {type(fallback_exc).__name__}: {fallback_exc}"
                ),
                "writable": False,
            }
        finally:
            try:
                fallback_probe.unlink(missing_ok=True)
            except OSError:
                pass
        return {
            "requested_dir": str(requested),
            "effective_dir": str(fallback),
            "fallback": True,
            "fallback_reason": f"{type(exc).__name__}: {exc}",
            "writable": True,
        }
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(1, 10_000):
        candidate = path.with_name(f"{stem}.{idx}{suffix}")
        if not candidate.exists():
            return candidate
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return path.with_name(f"{stem}.{timestamp}{suffix}")


def archive_removed_file(path: Path, *, output_root: Path, archive_dir: str | Path | None) -> str | None:
    if not archive_dir:
        return None
    archive_root = Path(archive_dir)
    try:
        relative = path.relative_to(output_root)
    except ValueError:
        relative = Path(path.name)
    destination = unique_destination(archive_root / relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(destination))
    return str(destination)


def prepare_maintenance_dirs(
    *,
    output_archive_dir: str | Path | None = None,
    log_snapshot_dir: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    targets = {
        "output_archive_dir": Path(output_archive_dir) if output_archive_dir else None,
        "log_snapshot_dir": Path(log_snapshot_dir) if log_snapshot_dir else None,
    }
    created: list[str] = []
    existing: dict[str, bool] = {}
    errors: dict[str, str] = {}
    for key, path in targets.items():
        if path is None:
            existing[key] = False
            continue
        if path.exists():
            existing[key] = path.is_dir()
            if not path.is_dir():
                errors[key] = "path exists but is not a directory"
            continue
        existing[key] = False
        if dry_run:
            continue
        try:
            path.mkdir(parents=True, exist_ok=True)
            existing[key] = path.is_dir()
            created.append(str(path))
        except Exception as exc:
            errors[key] = f"{type(exc).__name__}: {exc}"
    return {
        "created_dirs": created,
        "created_dir_count": len(created),
        "dir_exists": existing,
        "dir_errors": errors,
        "dir_error_count": len(errors),
        "dry_run": dry_run,
    }


def cleanup_output_files(
    *,
    output_dir: str | Path = OUTPUT_DIR,
    retention_rules: Mapping[str, int] | None = None,
    archive_dir: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    root = Path(output_dir)
    rules = dict(retention_rules or DEFAULT_RETENTION_RULES)
    removed: list[str] = []
    archived: list[str] = []
    kept_counts: dict[str, int] = {}
    removed_counts: dict[str, int] = {}
    archive_error_count = 0

    for pattern, keep_count in rules.items():
        keep_count = max(0, int(keep_count))
        files = files_for_pattern(root, pattern)
        kept_counts[pattern] = min(len(files), keep_count)
        stale = files[keep_count:]
        removed_counts[pattern] = len(stale)
        for path in stale:
            if dry_run:
                removed.append(str(path))
                continue
            try:
                archived_path = archive_removed_file(path, output_root=root, archive_dir=archive_dir)
                if archived_path:
                    archived.append(archived_path)
                else:
                    path.unlink()
                removed.append(str(path))
            except Exception:
                archive_error_count += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(root),
        "dry_run": dry_run,
        "removed": removed,
        "removed_count": len(removed),
        "archived": archived,
        "archived_count": len(archived),
        "archive_dir": str(archive_dir) if archive_dir else "",
        "archive_error_count": archive_error_count,
        "kept_counts": kept_counts,
        "removed_counts": removed_counts,
    }


def cleanup_stale_output_files(
    *,
    output_dir: str | Path = OUTPUT_DIR,
    max_age_days_rules: Mapping[str, float] | None = None,
    archive_dir: str | Path | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(output_dir)
    rules = dict(max_age_days_rules or STALE_OUTPUT_MAX_AGE_DAYS_RULES)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    removed: list[str] = []
    archived: list[str] = []
    removed_counts: dict[str, int] = {}
    kept_counts: dict[str, int] = {}
    archive_error_count = 0
    if not root.exists():
        return {
            "output_dir": str(root),
            "removed": removed,
            "removed_count": 0,
            "archived": archived,
            "archived_count": 0,
            "archive_dir": str(archive_dir) if archive_dir else "",
            "archive_error_count": 0,
            "removed_counts": removed_counts,
            "kept_counts": kept_counts,
            "exists": False,
        }
    for pattern, max_age_days in rules.items():
        max_age_seconds = max(0.0, float(max_age_days)) * 86400.0
        removed_counts[pattern] = 0
        kept_counts[pattern] = 0
        for path in sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            age_seconds = max(0.0, (current - modified).total_seconds())
            if age_seconds > max_age_seconds:
                removed_counts[pattern] += 1
                if dry_run:
                    removed.append(str(path))
                    continue
                try:
                    archived_path = archive_removed_file(path, output_root=root, archive_dir=archive_dir)
                    if archived_path:
                        archived.append(archived_path)
                    else:
                        path.unlink()
                    removed.append(str(path))
                except Exception:
                    archive_error_count += 1
            else:
                kept_counts[pattern] += 1
    return {
        "output_dir": str(root),
        "removed": removed,
        "removed_count": len(removed),
        "archived": archived,
        "archived_count": len(archived),
        "archive_dir": str(archive_dir) if archive_dir else "",
        "archive_error_count": archive_error_count,
        "removed_counts": removed_counts,
        "kept_counts": kept_counts,
        "exists": True,
        "max_age_days_rules": rules,
    }


def trim_file_tail(path: Path, *, max_bytes: int, dry_run: bool = False) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    size = path.stat().st_size
    max_bytes = max(0, int(max_bytes))
    if max_bytes <= 0 or size <= max_bytes:
        return None
    marker = f"\n--- trimmed by Roxy output maintenance at {datetime.now(timezone.utc).isoformat()} ---\n".encode()
    tail_bytes = max(0, max_bytes - len(marker))
    with path.open("rb") as fh:
        if tail_bytes > 0:
            fh.seek(-tail_bytes, 2)
        else:
            fh.seek(0, 2)
        data = fh.read()
    if not dry_run:
        path.write_bytes(marker + data)
    return {
        "path": str(path),
        "before_bytes": size,
        "after_bytes": len(marker) + len(data),
    }


def trim_log_files(
    *,
    log_dirs: list[str | Path] | None = None,
    patterns: tuple[str, ...] = DEFAULT_LOG_PATTERNS,
    max_bytes: int = DEFAULT_MAX_LOG_BYTES,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for root_value in log_dirs or [LOG_DIR, LAUNCHD_LOG_DIR]:
        root = Path(root_value)
        if not root.exists():
            continue
        for pattern in patterns:
            for path in sorted(root.glob(pattern)):
                result = trim_file_tail(path, max_bytes=max_bytes, dry_run=dry_run)
                if result:
                    trimmed.append(result)
    return trimmed


def _compact_learning_journal_history_file_unlocked(
    path: Path, *, dry_run: bool = False
) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".csv":
        return None
    before_bytes = path.stat().st_size
    lines = path.read_text(errors="replace").splitlines()
    if len(lines) <= 2:
        return None
    reader = csv.DictReader(lines)
    fieldnames = list(reader.fieldnames or [])
    if "fingerprint" not in fieldnames:
        return None
    rows = list(reader)
    if not rows:
        return None
    first_seen: dict[str, int] = {}
    last_seen: dict[str, int] = {}
    keep_indexes: set[int] = set()
    for idx, row in enumerate(rows):
        fingerprint = str(row.get("fingerprint") or "").strip()
        if not fingerprint:
            keep_indexes.add(idx)
            continue
        first_seen.setdefault(fingerprint, idx)
        last_seen[fingerprint] = idx
    for fingerprint, first_idx in first_seen.items():
        keep_indexes.add(first_idx)
        keep_indexes.add(last_seen[fingerprint])
    if len(keep_indexes) >= len(rows):
        return None
    kept_rows = [row for idx, row in enumerate(rows) if idx in keep_indexes]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(kept_rows)
    payload = buffer.getvalue()
    if not dry_run:
        atomic_write_text(payload, path)
    after_bytes = len(payload.encode())
    return {
        "path": str(path),
        "before_lines": len(lines),
        "after_lines": len(kept_rows) + 1,
        "removed_lines": len(rows) - len(kept_rows),
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "removed_bytes": max(0, before_bytes - after_bytes),
        "preserved_header": True,
        "compaction_type": "learning_journal_duplicate_fingerprint",
        "duplicate_fingerprint_count": len(rows) - len(first_seen),
    }


def compact_learning_journal_history_file(path: Path, *, dry_run: bool = False) -> dict[str, Any] | None:
    with exclusive_file_lock(path):
        return _compact_learning_journal_history_file_unlocked(path, dry_run=dry_run)


def _trim_history_file_unlocked(
    path: Path,
    *,
    max_lines: int,
    max_bytes: int | None = DEFAULT_MAX_HISTORY_BYTES,
    min_lines: int = DEFAULT_MIN_HISTORY_LINES,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    lines = path.read_text(errors="replace").splitlines()
    max_lines = max(1, int(max_lines))
    max_bytes = max(0, int(max_bytes)) if max_bytes is not None else 0
    min_lines = max(1, min(int(min_lines), max_lines))
    before_bytes = path.stat().st_size
    if len(lines) <= max_lines and (not max_bytes or before_bytes <= max_bytes):
        return None
    preserve_header = bool(path.suffix.lower() == ".csv" and len(lines) > 1 and "," in lines[0])
    header_line = lines[0] if preserve_header else None
    data_lines = lines[1:] if preserve_header else lines
    data_max_lines = max(0, max_lines - 1) if preserve_header else max_lines
    kept_data = data_lines[-data_max_lines:] if data_max_lines else []
    kept = ([header_line] if header_line is not None else []) + kept_data
    if max_bytes:
        kept_data_by_bytes: list[str] = []
        header_bytes = len(header_line.encode()) + 1 if header_line is not None else 0
        total_bytes = 1 + header_bytes
        for line in reversed(kept_data if preserve_header else kept):
            line_bytes = len(line.encode()) + 1
            projected_line_count = len(kept_data_by_bytes) + (1 if header_line is not None else 0)
            if kept_data_by_bytes and projected_line_count >= min_lines and total_bytes + line_bytes > max_bytes:
                break
            kept_data_by_bytes.append(line)
            total_bytes += line_bytes
        kept = ([header_line] if header_line is not None else []) + list(reversed(kept_data_by_bytes))
    if not dry_run:
        atomic_write_text("\n".join(kept) + "\n", path)
    after_bytes = len(("\n".join(kept) + "\n").encode()) if kept else 0
    return {
        "path": str(path),
        "before_lines": len(lines),
        "after_lines": len(kept),
        "removed_lines": len(lines) - len(kept),
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "removed_bytes": max(0, before_bytes - after_bytes),
        "max_bytes": max_bytes,
        "min_lines": min_lines,
        "preserved_header": preserve_header,
    }


def trim_history_file(
    path: Path,
    *,
    max_lines: int,
    max_bytes: int | None = DEFAULT_MAX_HISTORY_BYTES,
    min_lines: int = DEFAULT_MIN_HISTORY_LINES,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    with exclusive_file_lock(path):
        return _trim_history_file_unlocked(
            path,
            max_lines=max_lines,
            max_bytes=max_bytes,
            min_lines=min_lines,
            dry_run=dry_run,
        )


def trim_history_files(
    *,
    alerts_path: str | Path = ALERTS_DIR,
    history_files: tuple[str, ...] = DEFAULT_HISTORY_FILES,
    max_lines: int = DEFAULT_MAX_HISTORY_LINES,
    max_bytes: int | None = DEFAULT_MAX_HISTORY_BYTES,
    min_lines: int = DEFAULT_MIN_HISTORY_LINES,
    cap_target_ratio: float = DEFAULT_HISTORY_CAP_TARGET_RATIO,
    low_line_margin_ratio: float = DEFAULT_HISTORY_LOW_LINE_MARGIN_RATIO,
    line_warn_ratio: float = DEFAULT_HISTORY_BUDGET_WARN_RATIO,
    byte_margin_warn_ratio: float = DEFAULT_HISTORY_BUDGET_WARN_RATIO,
    byte_projection_lines: int = DEFAULT_HISTORY_BYTE_PROJECTION_LINES,
    min_appends_until_warn: int = DEFAULT_HISTORY_MIN_APPENDS_UNTIL_WARN,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    root = Path(alerts_path)
    trimmed: list[dict[str, Any]] = []
    max_lines = max(1, int(max_lines))
    configured_max_bytes = max(0, int(max_bytes)) if max_bytes is not None else 0
    min_lines = max(1, min(int(min_lines), max_lines))
    cap_target_ratio = max(0.0, min(float(cap_target_ratio), 1.0))
    line_warn_ratio = max(0.0, float(line_warn_ratio))
    line_warn_threshold = int(max_lines * line_warn_ratio)
    low_line_margin_ratio = max(0.0, float(low_line_margin_ratio))
    low_line_margin_threshold = int(max_lines * low_line_margin_ratio)
    byte_margin_warn_ratio = max(0.0, float(byte_margin_warn_ratio))
    byte_projection_lines = max(0, int(byte_projection_lines))
    min_appends_until_warn = max(0, int(min_appends_until_warn))
    projected_line_window = max(1, byte_projection_lines)
    line_warn_append_guard_window = max(projected_line_window, min_appends_until_warn)
    byte_warn_append_guard_window = max(byte_projection_lines, min_appends_until_warn)
    byte_warn_append_guard_target_window = byte_warn_append_guard_window + DEFAULT_HISTORY_APPEND_GUARD_TARGET_BUFFER
    for name in history_files:
        path = root / name
        if name == "roxy_learning_journal.csv":
            learning_compaction = compact_learning_journal_history_file(path, dry_run=dry_run)
            if learning_compaction:
                learning_compaction["name"] = name
                learning_compaction["configured_max_lines"] = max_lines
                learning_compaction["configured_max_bytes"] = effective_history_max_bytes(name, configured_max_bytes)
                learning_compaction["global_configured_max_bytes"] = configured_max_bytes
                learning_compaction["cap_target_ratio"] = cap_target_ratio
                trimmed.append(learning_compaction)
        effective_configured_max_bytes = effective_history_max_bytes(name, configured_max_bytes)
        byte_margin_threshold = (
            int(effective_configured_max_bytes * byte_margin_warn_ratio)
            if effective_configured_max_bytes
            else 0
        )
        effective_max_lines = max_lines
        effective_max_bytes = effective_configured_max_bytes or None
        effective_min_lines = min_lines
        byte_min_line_plan: dict[str, Any] = {
            "configured_min_lines": min_lines,
            "effective_min_lines": min_lines,
            "min_line_floor": max(1, int(min_lines * DEFAULT_HISTORY_MIN_LINE_FLOOR_RATIO)),
            "target_fit_lines": None,
            "target_fit_bytes": None,
            "min_lines_relaxed": False,
        }
        proactive_line_cap_trim = False
        proactive_line_warn_trim = False
        proactive_projected_line_warn_trim = False
        proactive_append_guard_line_warn_trim = False
        proactive_low_line_margin_trim = False
        proactive_byte_margin_trim = False
        proactive_projected_byte_margin_trim = False
        proactive_append_guard_byte_margin_trim = False
        projected_byte_margin_threshold = 0
        projected_next_bytes = None
        projected_append_guard_next_bytes = None
        byte_append_guard_target_bytes = None
        projected_average_line_bytes = None
        if cap_target_ratio and path.exists() and path.is_file():
            current_history_lines = path.read_text(errors="replace").splitlines()
            current_lines = len(current_history_lines)
            current_size_bytes = path.stat().st_size
            target_lines = max(min_lines, int(max_lines * cap_target_ratio))
            if current_lines == max_lines:
                effective_max_lines = target_lines
                proactive_line_cap_trim = effective_max_lines < max_lines
            elif low_line_margin_threshold and current_lines < max_lines:
                line_margin = max_lines - current_lines
                if line_margin <= low_line_margin_threshold and current_lines > target_lines:
                    effective_max_lines = target_lines
                    proactive_low_line_margin_trim = effective_max_lines < max_lines
            if (
                not proactive_line_cap_trim
                and not proactive_low_line_margin_trim
                and line_warn_threshold
                and current_lines >= line_warn_threshold
                and current_lines > target_lines
            ):
                effective_max_lines = target_lines
                proactive_line_warn_trim = effective_max_lines < max_lines
            if (
                not proactive_line_cap_trim
                and not proactive_low_line_margin_trim
                and not proactive_line_warn_trim
                and line_warn_threshold
                and current_lines < line_warn_threshold
                and current_lines + projected_line_window >= line_warn_threshold
                and current_lines > target_lines
            ):
                effective_max_lines = target_lines
                proactive_projected_line_warn_trim = effective_max_lines < max_lines
            if (
                not proactive_line_cap_trim
                and not proactive_low_line_margin_trim
                and not proactive_line_warn_trim
                and not proactive_projected_line_warn_trim
                and line_warn_threshold
                and line_warn_append_guard_window > projected_line_window
                and current_lines < line_warn_threshold
                and current_lines + line_warn_append_guard_window >= line_warn_threshold
                and current_lines > target_lines
            ):
                effective_max_lines = target_lines
                proactive_append_guard_line_warn_trim = effective_max_lines < max_lines
            if (
                effective_configured_max_bytes
                and byte_margin_threshold
                and current_size_bytes >= byte_margin_threshold
            ):
                target_bytes = int(effective_configured_max_bytes * cap_target_ratio)
                if target_bytes and target_bytes < effective_configured_max_bytes:
                    byte_min_line_plan = effective_history_min_lines_for_byte_target(
                        path,
                        max_lines=max_lines,
                        min_lines=min_lines,
                        target_bytes=target_bytes,
                    )
                    effective_min_lines = int(byte_min_line_plan.get("effective_min_lines") or min_lines)
                    effective_max_bytes = target_bytes
                    proactive_byte_margin_trim = True
            elif (
                effective_configured_max_bytes
                and byte_margin_threshold
                and byte_projection_lines
                and current_history_lines
            ):
                sample_lines = current_history_lines[-byte_projection_lines:]
                sample_bytes = sum(len(line.encode()) + 1 for line in sample_lines)
                projected_average_line_bytes = sample_bytes / max(1, len(sample_lines))
                projected_next_bytes = int(
                    current_size_bytes + round(projected_average_line_bytes * byte_projection_lines)
                )
                projected_byte_margin_threshold = byte_margin_threshold
                byte_append_guard_target_bytes = int(
                    byte_margin_threshold
                    - round(projected_average_line_bytes * byte_warn_append_guard_target_window)
                )
                if byte_append_guard_target_bytes <= 0:
                    byte_append_guard_target_bytes = None
                if projected_next_bytes >= byte_margin_threshold:
                    target_bytes = int(effective_configured_max_bytes * cap_target_ratio)
                    if byte_append_guard_target_bytes:
                        target_bytes = min(target_bytes, byte_append_guard_target_bytes)
                    if target_bytes and target_bytes < effective_configured_max_bytes:
                        byte_min_line_plan = effective_history_min_lines_for_byte_target(
                            path,
                            max_lines=max_lines,
                            min_lines=min_lines,
                            target_bytes=target_bytes,
                        )
                        effective_min_lines = int(byte_min_line_plan.get("effective_min_lines") or min_lines)
                        if current_lines > effective_min_lines:
                            effective_max_bytes = target_bytes
                            proactive_projected_byte_margin_trim = True
                elif byte_warn_append_guard_window > byte_projection_lines:
                    projected_append_guard_next_bytes = int(
                        current_size_bytes
                        + round(projected_average_line_bytes * byte_warn_append_guard_window)
                    )
                    if projected_append_guard_next_bytes >= byte_margin_threshold:
                        target_bytes = int(effective_configured_max_bytes * cap_target_ratio)
                        if byte_append_guard_target_bytes:
                            target_bytes = min(target_bytes, byte_append_guard_target_bytes)
                        if target_bytes and target_bytes < effective_configured_max_bytes:
                            byte_min_line_plan = effective_history_min_lines_for_byte_target(
                                path,
                                max_lines=max_lines,
                                min_lines=min_lines,
                                target_bytes=target_bytes,
                            )
                            effective_min_lines = int(byte_min_line_plan.get("effective_min_lines") or min_lines)
                            if current_lines > effective_min_lines:
                                effective_max_bytes = target_bytes
                                proactive_append_guard_byte_margin_trim = True
        result = trim_history_file(
            path,
            max_lines=effective_max_lines,
            max_bytes=effective_max_bytes,
            min_lines=effective_min_lines,
            dry_run=dry_run,
        )
        if result:
            result["name"] = name
            result["configured_max_lines"] = max_lines
            result["configured_max_bytes"] = effective_configured_max_bytes
            result["global_configured_max_bytes"] = configured_max_bytes
            result["cap_target_ratio"] = cap_target_ratio
            result["proactive_line_cap_trim"] = proactive_line_cap_trim
            result["line_warn_ratio"] = line_warn_ratio
            result["line_warn_threshold"] = line_warn_threshold
            result["min_appends_until_warn"] = min_appends_until_warn
            result["line_warn_append_guard_window"] = line_warn_append_guard_window
            result["byte_warn_append_guard_window"] = byte_warn_append_guard_window
            result["byte_warn_append_guard_target_window"] = byte_warn_append_guard_target_window
            result["proactive_line_warn_trim"] = proactive_line_warn_trim
            result["proactive_projected_line_warn_trim"] = proactive_projected_line_warn_trim
            result["proactive_append_guard_line_warn_trim"] = proactive_append_guard_line_warn_trim
            result["low_line_margin_ratio"] = low_line_margin_ratio
            result["low_line_margin_threshold"] = low_line_margin_threshold
            result["proactive_low_line_margin_trim"] = proactive_low_line_margin_trim
            result["byte_margin_warn_ratio"] = byte_margin_warn_ratio
            result["byte_margin_threshold"] = byte_margin_threshold
            result["proactive_byte_margin_trim"] = proactive_byte_margin_trim
            result["byte_projection_lines"] = byte_projection_lines
            result["projected_line_window"] = projected_line_window
            result["configured_min_lines"] = min_lines
            result["effective_min_lines"] = effective_min_lines
            result["min_line_floor"] = byte_min_line_plan.get("min_line_floor")
            result["target_fit_lines"] = byte_min_line_plan.get("target_fit_lines")
            result["target_fit_bytes"] = byte_min_line_plan.get("target_fit_bytes")
            result["min_lines_relaxed"] = bool(byte_min_line_plan.get("min_lines_relaxed"))
            result["projected_byte_margin_threshold"] = projected_byte_margin_threshold
            result["projected_next_bytes"] = projected_next_bytes
            result["projected_append_guard_next_bytes"] = projected_append_guard_next_bytes
            result["byte_append_guard_target_bytes"] = byte_append_guard_target_bytes
            result["projected_average_line_bytes"] = projected_average_line_bytes
            result["proactive_projected_byte_margin_trim"] = proactive_projected_byte_margin_trim
            result["proactive_append_guard_byte_margin_trim"] = proactive_append_guard_byte_margin_trim
            trimmed.append(result)
    return trimmed


def history_file_budget_reports(
    *,
    alerts_path: str | Path = ALERTS_DIR,
    history_files: tuple[str, ...] = DEFAULT_HISTORY_FILES,
    max_lines: int = DEFAULT_MAX_HISTORY_LINES,
    max_bytes: int | None = DEFAULT_MAX_HISTORY_BYTES,
    warn_ratio: float = DEFAULT_HISTORY_BUDGET_WARN_RATIO,
    byte_projection_lines: int = DEFAULT_HISTORY_BYTE_PROJECTION_LINES,
) -> list[dict[str, Any]]:
    root = Path(alerts_path)
    max_lines = max(1, int(max_lines))
    max_bytes = max(0, int(max_bytes)) if max_bytes is not None else 0
    warn_ratio = max(0.0, float(warn_ratio))
    byte_projection_lines = max(0, int(byte_projection_lines))
    line_warn_threshold = int(max_lines * warn_ratio) if max_lines > 0 else 0
    reports: list[dict[str, Any]] = []
    for name in history_files:
        path = root / name
        effective_max_bytes = effective_history_max_bytes(name, max_bytes)
        if not path.exists() or not path.is_file():
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
            line_count = len(lines)
            size_bytes = path.stat().st_size
        except OSError:
            reports.append({"path": str(path), "name": name, "status": "ERROR"})
            continue
        line_ratio = line_count / max_lines if max_lines > 0 else None
        byte_ratio = size_bytes / effective_max_bytes if effective_max_bytes > 0 else None
        line_margin = max_lines - line_count if max_lines > 0 else None
        byte_margin = effective_max_bytes - size_bytes if effective_max_bytes > 0 else None
        projection_sample = lines[-byte_projection_lines:] if byte_projection_lines and lines else []
        average_recent_line_bytes = (
            sum(len(line.encode()) + 1 for line in projection_sample) / len(projection_sample)
            if projection_sample
            else None
        )
        projected_next_line_count = (
            line_count + byte_projection_lines if byte_projection_lines else line_count
        )
        projected_next_line_ratio = (
            projected_next_line_count / max_lines if max_lines > 0 else None
        )
        projected_next_bytes = (
            int(size_bytes + round(average_recent_line_bytes * byte_projection_lines))
            if average_recent_line_bytes is not None
            else size_bytes
        )
        projected_next_byte_ratio = (
            projected_next_bytes / effective_max_bytes if effective_max_bytes > 0 else None
        )
        projected_next_byte_margin = (
            effective_max_bytes - projected_next_bytes if effective_max_bytes > 0 else None
        )
        estimated_appends_until_line_warn = (
            max(0, line_warn_threshold - line_count)
            if line_warn_threshold > 0
            else None
        )
        byte_warn_threshold = (
            int(effective_max_bytes * warn_ratio)
            if effective_max_bytes > 0
            else 0
        )
        estimated_appends_until_byte_warn = None
        if byte_warn_threshold and average_recent_line_bytes and average_recent_line_bytes > 0:
            estimated_appends_until_byte_warn = max(
                0,
                int(math.ceil((byte_warn_threshold - size_bytes) / average_recent_line_bytes)),
            )
        append_estimates = [
            value
            for value in (
                estimated_appends_until_line_warn,
                estimated_appends_until_byte_warn,
            )
            if value is not None
        ]
        estimated_appends_until_warn = min(append_estimates) if append_estimates else None
        line_at_cap = bool(
            line_ratio is not None
            and line_margin == 0
            and line_count == max_lines
            and (byte_ratio is None or byte_ratio < warn_ratio)
        )
        over_limit = bool(
            (line_ratio is not None and line_ratio > 1.0)
            or (byte_ratio is not None and byte_ratio > 1.0)
        )
        near_limit = bool(
            not over_limit
            and not line_at_cap
            and (
                (line_ratio is not None and line_ratio >= warn_ratio)
                or (byte_ratio is not None and byte_ratio >= warn_ratio)
            )
        )
        status = "OVER_LIMIT" if over_limit else "NEAR_LIMIT" if near_limit else "AT_CAP" if line_at_cap else "OK"
        projected_over_limit = bool(
            (projected_next_line_ratio is not None and projected_next_line_ratio > 1.0)
            or (projected_next_byte_ratio is not None and projected_next_byte_ratio > 1.0)
        )
        projected_near_limit = bool(
            not projected_over_limit
            and (
                (projected_next_line_ratio is not None and projected_next_line_ratio >= warn_ratio)
                or (projected_next_byte_ratio is not None and projected_next_byte_ratio >= warn_ratio)
            )
        )
        projected_next_status = "OVER_LIMIT" if projected_over_limit else "NEAR_LIMIT" if projected_near_limit else "OK"
        reports.append(
            {
                "path": str(path),
                "name": name,
                "status": status,
                "projected_next_status": projected_next_status,
                "line_at_cap": line_at_cap,
                "line_count": line_count,
                "max_lines": max_lines,
                "line_ratio": round(line_ratio, 4) if line_ratio is not None else None,
                "line_margin": line_margin,
                "projected_next_line_count": projected_next_line_count,
                "projected_next_line_ratio": (
                    round(projected_next_line_ratio, 4)
                    if projected_next_line_ratio is not None
                    else None
                ),
                "size_bytes": size_bytes,
                "max_bytes": effective_max_bytes,
                "global_max_bytes": max_bytes,
                "byte_ratio": round(byte_ratio, 4) if byte_ratio is not None else None,
                "byte_margin": byte_margin,
                "byte_projection_lines": byte_projection_lines,
                "average_recent_line_bytes": (
                    round(average_recent_line_bytes, 3)
                    if average_recent_line_bytes is not None
                    else None
                ),
                "line_warn_threshold": line_warn_threshold,
                "byte_warn_threshold": byte_warn_threshold or None,
                "estimated_appends_until_line_warn": estimated_appends_until_line_warn,
                "estimated_appends_until_byte_warn": estimated_appends_until_byte_warn,
                "estimated_appends_until_warn": estimated_appends_until_warn,
                "projected_next_bytes": projected_next_bytes,
                "projected_next_byte_ratio": (
                    round(projected_next_byte_ratio, 4)
                    if projected_next_byte_ratio is not None
                    else None
                ),
                "projected_next_byte_margin": projected_next_byte_margin,
                "warn_ratio": warn_ratio,
            }
        )
    return reports


def maintenance_hygiene_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    dry_run = bool(result.get("dry_run"))
    archive_errors = int(result.get("output_archive_error_count") or 0)
    prepared_errors = int(result.get("prepared_dir_error_count") or 0)
    output_archive_exists = bool(result.get("output_archive_exists"))
    output_archive_fallback = bool(result.get("output_archive_fallback"))
    output_archive_writable = bool(result.get("output_archive_writable", output_archive_exists))
    output_archive_requested_dir = str(result.get("output_archive_requested_dir") or "")
    output_archive_effective_dir = str(
        result.get("output_archive_effective_dir") or result.get("output_archive_dir") or ""
    )
    output_archive_local = bool(
        output_archive_effective_dir
        and Path(output_archive_effective_dir).expanduser().resolve()
        == DEFAULT_LOCAL_OUTPUT_ARCHIVE_DIR.expanduser().resolve()
    )
    log_snapshot_dir_exists = bool(result.get("log_snapshot_dir_exists"))
    log_snapshot_counts = (
        result.get("log_snapshot_counts")
        if isinstance(result.get("log_snapshot_counts"), Mapping)
        else {}
    )
    log_snapshot_scan_status = str(log_snapshot_counts.get("scan_status") or "OK").upper()
    log_snapshot_scan_errors = (
        log_snapshot_counts.get("scan_errors")
        if isinstance(log_snapshot_counts.get("scan_errors"), Mapping)
        else {}
    )
    sqlite_info = result.get("sqlite_maintenance") if isinstance(result.get("sqlite_maintenance"), Mapping) else {}
    sqlite_status = str(sqlite_info.get("status") or "")
    sqlite_reclaimable = float(result.get("sqlite_db_reclaimable_mb") or sqlite_info.get("reclaimable_mb") or 0.0)
    max_history_lines = int(result.get("max_history_lines") or DEFAULT_MAX_HISTORY_LINES)
    max_log_bytes = int(result.get("max_log_bytes") or DEFAULT_MAX_LOG_BYTES)
    dashboard_history = (
        result.get("dashboard_history_maintenance")
        if isinstance(result.get("dashboard_history_maintenance"), Mapping)
        else {}
    )
    dashboard_rows = int(result.get("dashboard_history_after_rows") or dashboard_history.get("after_rows") or 0)
    dashboard_max_rows = int(result.get("dashboard_history_max_rows") or DEFAULT_DASHBOARD_HISTORY_MAX_ROWS)
    trimmed_history_count = int(result.get("trimmed_history_count") or 0)
    trimmed_history_removed_lines = int(result.get("trimmed_history_removed_lines") or 0)
    trimmed_history_min_lines_relaxed_count = int(result.get("trimmed_history_min_lines_relaxed_count") or 0)
    history_budget_near_limit_count = int(result.get("history_budget_near_limit_count") or 0)
    history_budget_over_limit_count = int(result.get("history_budget_over_limit_count") or 0)
    history_budget_at_cap_count = int(result.get("history_budget_at_cap_count") or 0)
    history_budget_projected_near_limit_count = int(
        result.get("history_budget_projected_near_limit_count") or 0
    )
    history_budget_projected_over_limit_count = int(
        result.get("history_budget_projected_over_limit_count") or 0
    )
    history_budget_status = str(result.get("history_budget_status") or "")
    history_budget_pressure = str(result.get("history_budget_pressure") or "")
    history_budget_attention_file_count = int(result.get("history_budget_attention_file_count") or 0)
    history_budget_top = (
        result.get("history_budget_top") if isinstance(result.get("history_budget_top"), Mapping) else {}
    )
    history_budget_top_name = str(result.get("history_budget_top_name") or history_budget_top.get("name") or "")
    history_budget_top_status = str(
        result.get("history_budget_top_status") or history_budget_top.get("status") or ""
    )
    history_budget_top_line_ratio = result.get("history_budget_top_line_ratio", history_budget_top.get("line_ratio"))
    history_budget_top_byte_ratio = result.get("history_budget_top_byte_ratio", history_budget_top.get("byte_ratio"))
    history_budget_top_line_margin = result.get("history_budget_top_line_margin", history_budget_top.get("line_margin"))
    history_budget_top_byte_margin = result.get("history_budget_top_byte_margin", history_budget_top.get("byte_margin"))
    history_budget_projected_top = (
        result.get("history_budget_projected_top")
        if isinstance(result.get("history_budget_projected_top"), Mapping)
        else {}
    )
    history_budget_projected_top_name = str(
        result.get("history_budget_projected_top_name") or history_budget_projected_top.get("name") or ""
    )
    history_budget_projected_top_status = str(
        result.get("history_budget_projected_top_status")
        or history_budget_projected_top.get("projected_next_status")
        or ""
    )
    history_budget_projected_top_byte_ratio = result.get(
        "history_budget_projected_top_byte_ratio",
        history_budget_projected_top.get("projected_next_byte_ratio"),
    )
    local_cache_status = str(result.get("local_cache_cleanup_status") or "")
    local_cache_plan_state = str(result.get("local_cache_cleanup_plan_state") or "")
    local_cache_removed_mb = float(result.get("local_cache_cleanup_removed_mb") or 0.0)
    local_cache_eligible_count = int(result.get("local_cache_cleanup_eligible_count") or 0)
    local_cache_eligible_mb = float(result.get("local_cache_cleanup_eligible_mb") or 0.0)
    local_cache_fresh_protected_count = int(result.get("local_cache_cleanup_fresh_protected_count") or 0)
    local_cache_fresh_protected_mb = float(result.get("local_cache_cleanup_fresh_protected_mb") or 0.0)
    local_cache_blocked_reason = str(result.get("local_cache_cleanup_blocked_reason") or "")
    local_cache_skipped_count = int(result.get("local_cache_cleanup_skipped_count") or 0)
    local_cache_skipped_mb = float(result.get("local_cache_cleanup_skipped_mb") or 0.0)
    local_cache_skipped_top_reason = str(result.get("local_cache_cleanup_skipped_top_reason") or "")
    local_cache_skip_state = str(result.get("local_cache_cleanup_skip_state") or "")
    local_cache_retry_recommended = bool(result.get("local_cache_cleanup_retry_recommended"))
    runtime_after = result.get("runtime_footprint_after") if isinstance(result.get("runtime_footprint_after"), Mapping) else {}
    runtime_mb = float(runtime_after.get("total_mb") or 0.0)
    runtime_files = int(runtime_after.get("total_files") or 0)
    reclaimed_bytes = int(result.get("runtime_footprint_reclaimed_bytes") or 0)
    removed_total = (
        int(result.get("removed_count") or 0)
        + int(result.get("stale_output_removed_count") or 0)
        + int(result.get("trimmed_log_count") or 0)
        + int(result.get("trimmed_history_count") or 0)
        + int(result.get("removed_alert_report_count") or 0)
        + int(result.get("removed_log_snapshot_count") or 0)
        + int(result.get("dashboard_history_removed_rows") or 0)
    )
    sqlite_vacuum_min_reclaim_mb = float(
        sqlite_info.get("vacuum_min_reclaim_mb") or DEFAULT_SQLITE_VACUUM_MIN_RECLAIM_MB
    )
    internal_protected = bool(
        output_archive_exists
        and output_archive_writable
        and archive_errors == 0
        and prepared_errors == 0
        and not dry_run
        and sqlite_status != "ERROR"
        and dashboard_rows <= dashboard_max_rows
    )
    external_snapshot_degraded = bool(
        internal_protected
        and log_snapshot_dir_exists
        and log_snapshot_scan_status == "WARN"
    )
    protected = bool(
        internal_protected
        and log_snapshot_dir_exists
        and log_snapshot_scan_status == "OK"
    )
    issues: list[str] = []
    if dry_run:
        issues.append("last run dry-run")
    if not output_archive_exists:
        issues.append("output archive dir missing")
    if not log_snapshot_dir_exists:
        issues.append("log snapshot dir missing")
    if log_snapshot_scan_status != "OK":
        issues.append(f"log snapshot scan {log_snapshot_scan_status.lower()}")
    if archive_errors:
        issues.append(f"archive errors {archive_errors}")
    if prepared_errors:
        issues.append(f"prepared dir errors {prepared_errors}")
    if sqlite_status == "ERROR":
        issues.append("sqlite maintenance error")
    if dashboard_rows > dashboard_max_rows:
        issues.append(f"dashboard history {dashboard_rows}>{dashboard_max_rows}")
    if history_budget_over_limit_count:
        issues.append(f"history budget over {history_budget_over_limit_count}")
    if local_cache_skipped_count:
        issue = f"local cache skipped {local_cache_skipped_count}"
        if local_cache_skipped_mb:
            issue += f"/{local_cache_skipped_mb:.3f}MB"
        if local_cache_skipped_top_reason:
            issue += f" {local_cache_skipped_top_reason}"
        if local_cache_skip_state and local_cache_skip_state != "CLEAR":
            issue += f" {local_cache_skip_state.lower()}"
        if local_cache_retry_recommended:
            issue += " retry"
        issues.append(issue)
    external_archive_ready = bool(
        not output_archive_fallback
        and not output_archive_local
        and output_archive_exists
        and output_archive_writable
        and log_snapshot_dir_exists
        and log_snapshot_scan_status == "OK"
        and archive_errors == 0
        and prepared_errors == 0
    )
    if dry_run:
        next_action = "Ejecutar limpieza real"
    elif not output_archive_exists or not log_snapshot_dir_exists:
        next_action = "Conectar RoxyData y preparar carpetas"
    elif log_snapshot_scan_status != "OK":
        next_action = "Revisar acceso a snapshots en RoxyData"
    elif archive_errors or prepared_errors or not output_archive_writable:
        next_action = "Revisar permisos de RoxyData"
    elif sqlite_status == "ERROR":
        next_action = "Reparar SQLite"
    elif dashboard_rows > dashboard_max_rows:
        next_action = "Compactar historial dashboard"
    elif history_budget_over_limit_count:
        next_action = "Recortar historiales"
    elif sqlite_reclaimable >= sqlite_vacuum_min_reclaim_mb:
        next_action = "Vacuum SQLite"
    elif local_cache_status.upper() == "SKIPPED" and local_cache_plan_state.upper() == "SAFE_CACHE_REVIEW_READY" and local_cache_eligible_count:
        next_action = "Activar limpieza cache local"
    elif removed_total or reclaimed_bytes:
        next_action = "Limpieza aplicada"
    elif history_budget_near_limit_count or history_budget_at_cap_count:
        next_action = "Monitorear historiales"
    elif history_budget_projected_near_limit_count or history_budget_projected_over_limit_count:
        next_action = "Monitorear historiales"
    else:
        next_action = "Monitorear"
    if output_archive_fallback and next_action == "Monitorear":
        next_action = "Autorizar RoxyData; respaldo local activo"
    if protected:
        label = "Protegido"
        tone = "buy"
        status = "OK"
    elif external_snapshot_degraded:
        label = "Interno protegido / snapshots degradados"
        tone = "watch"
        status = "WARN"
    elif archive_errors or prepared_errors or sqlite_status == "ERROR":
        label = "Revisar limpieza"
        tone = "avoid"
        status = "WARN"
    else:
        label = "Parcial"
        tone = "watch"
        status = "WARN"
    detail_parts = [
        f"archive {'local fallback' if output_archive_fallback else 'local' if output_archive_local else 'external' if output_archive_exists else 'missing'}",
        f"snapshots {log_snapshot_scan_status.lower() if log_snapshot_dir_exists else 'missing'}",
        f"hist max {max_history_lines}",
        f"logs max {round(max_log_bytes / (1024**2), 1)}MB",
        f"dashboard {dashboard_rows}/{dashboard_max_rows}",
        f"sqlite reclaim {sqlite_reclaimable:.1f}MB",
        f"runtime {runtime_mb:.1f}MB/{runtime_files} files",
        f"accion {next_action}",
    ]
    if output_archive_fallback:
        detail_parts.append("external archive permission required")
    if trimmed_history_count:
        detail_parts.append(f"hist trimmed {trimmed_history_count}/{trimmed_history_removed_lines} lines")
    if trimmed_history_min_lines_relaxed_count:
        detail_parts.append(f"hist min relaxed {trimmed_history_min_lines_relaxed_count}")
    if history_budget_status:
        detail_parts.append(f"hist status {history_budget_status.lower()}")
    if history_budget_near_limit_count or history_budget_over_limit_count or history_budget_at_cap_count:
        budget_text = (
            f"hist budget near {history_budget_near_limit_count}"
            f" over {history_budget_over_limit_count}"
        )
        if history_budget_at_cap_count:
            budget_text += f" cap {history_budget_at_cap_count}"
        if history_budget_top_name:
            budget_text += f" top {history_budget_top_name}"
        if history_budget_top_status:
            budget_text += f" {history_budget_top_status.lower()}"
        ratios = []
        try:
            if history_budget_top_line_ratio is not None:
                ratios.append(f"lines {float(history_budget_top_line_ratio) * 100:.1f}%")
        except (TypeError, ValueError):
            pass
        try:
            if history_budget_top_byte_ratio is not None:
                ratios.append(f"bytes {float(history_budget_top_byte_ratio) * 100:.1f}%")
        except (TypeError, ValueError):
            pass
        if ratios:
            budget_text += " " + " ".join(ratios)
        if history_budget_top_line_margin is not None:
            budget_text += f" line_margin {history_budget_top_line_margin}"
        try:
            if history_budget_top_byte_margin is not None:
                budget_text += f" byte_margin {float(history_budget_top_byte_margin) / (1024**2):.2f}MB"
        except (TypeError, ValueError):
            pass
        detail_parts.append(budget_text)
    if history_budget_projected_near_limit_count or history_budget_projected_over_limit_count:
        projected_text = (
            f"hist projected near {history_budget_projected_near_limit_count}"
            f" over {history_budget_projected_over_limit_count}"
        )
        if history_budget_projected_top_name:
            projected_text += f" top {history_budget_projected_top_name}"
        if history_budget_projected_top_status:
            projected_text += f" {history_budget_projected_top_status.lower()}"
        try:
            if history_budget_projected_top_byte_ratio is not None:
                projected_text += f" next_bytes {float(history_budget_projected_top_byte_ratio) * 100:.1f}%"
        except (TypeError, ValueError):
            pass
        detail_parts.append(projected_text)
    if local_cache_status:
        detail_parts.append(f"local cache {local_cache_status.lower()}")
        if local_cache_plan_state:
            detail_parts.append(f"local plan {local_cache_plan_state.lower()}")
        if local_cache_eligible_count:
            detail_parts.append(f"local eligible {local_cache_eligible_count}/{local_cache_eligible_mb:.1f}MB")
        if local_cache_fresh_protected_count:
            detail_parts.append(
                f"local fresh protected {local_cache_fresh_protected_count}/{local_cache_fresh_protected_mb:.1f}MB"
            )
        if local_cache_removed_mb:
            detail_parts.append(f"local reclaimed {local_cache_removed_mb:.1f}MB")
        if local_cache_blocked_reason and local_cache_status.upper() == "BLOCKED":
            detail_parts.append(f"local blocked {local_cache_blocked_reason}")
        if local_cache_skipped_count:
            skipped_text = f"local skipped {local_cache_skipped_count}"
            if local_cache_skipped_mb:
                skipped_text += f"/{local_cache_skipped_mb:.3f}MB"
            if local_cache_skipped_top_reason:
                skipped_text += f" {local_cache_skipped_top_reason}"
            if local_cache_skip_state and local_cache_skip_state != "CLEAR":
                skipped_text += f" {local_cache_skip_state.lower()}"
            if local_cache_retry_recommended:
                skipped_text += " retry"
            detail_parts.append(skipped_text)
    if issues:
        detail_parts.append("issues " + "; ".join(issues))
    return {
        "status": status,
        "label": label,
        "tone": tone,
        "protected": protected,
        "internal_protected": internal_protected,
        "external_snapshot_degraded": external_snapshot_degraded,
        "detail": " | ".join(detail_parts),
        "issues": issues,
        "next_action": next_action,
        "external_archive_ready": external_archive_ready,
        "archive_ready": output_archive_exists and output_archive_writable and archive_errors == 0,
        "archive_fallback": output_archive_fallback,
        "archive_local": output_archive_local,
        "archive_writable": output_archive_writable,
        "archive_requested_dir": output_archive_requested_dir,
        "archive_effective_dir": output_archive_effective_dir,
        "log_snapshots_ready": log_snapshot_dir_exists and log_snapshot_scan_status == "OK",
        "log_snapshot_scan_status": log_snapshot_scan_status,
        "log_snapshot_scan_errors": dict(log_snapshot_scan_errors),
        "history_max_lines": max_history_lines,
        "max_log_bytes": max_log_bytes,
        "dashboard_history_rows": dashboard_rows,
        "dashboard_history_max_rows": dashboard_max_rows,
        "trimmed_history_count": trimmed_history_count,
        "trimmed_history_removed_lines": trimmed_history_removed_lines,
        "trimmed_history_min_lines_relaxed_count": trimmed_history_min_lines_relaxed_count,
        "history_budget_near_limit_count": history_budget_near_limit_count,
        "history_budget_over_limit_count": history_budget_over_limit_count,
        "history_budget_at_cap_count": history_budget_at_cap_count,
        "history_budget_projected_near_limit_count": history_budget_projected_near_limit_count,
        "history_budget_projected_over_limit_count": history_budget_projected_over_limit_count,
        "history_budget_status": history_budget_status,
        "history_budget_pressure": history_budget_pressure,
        "history_budget_attention_file_count": history_budget_attention_file_count,
        "history_budget_top_name": history_budget_top_name,
        "history_budget_top_status": history_budget_top_status,
        "history_budget_top_line_ratio": history_budget_top_line_ratio,
        "history_budget_top_byte_ratio": history_budget_top_byte_ratio,
        "history_budget_top_line_margin": history_budget_top_line_margin,
        "history_budget_top_byte_margin": history_budget_top_byte_margin,
        "history_budget_projected_top_name": history_budget_projected_top_name,
        "history_budget_projected_top_status": history_budget_projected_top_status,
        "history_budget_projected_top_byte_ratio": history_budget_projected_top_byte_ratio,
        "local_cache_skipped_count": local_cache_skipped_count,
        "local_cache_skipped_mb": round(local_cache_skipped_mb, 3),
        "local_cache_skipped_top_reason": local_cache_skipped_top_reason,
        "sqlite_reclaimable_mb": round(sqlite_reclaimable, 3),
        "sqlite_vacuum_min_reclaim_mb": sqlite_vacuum_min_reclaim_mb,
        "runtime_footprint_mb": round(runtime_mb, 3),
        "runtime_footprint_files": runtime_files,
        "runtime_footprint_reclaimed_bytes": reclaimed_bytes,
    }


def maintenance_operation_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    hygiene = result.get("hygiene_summary") if isinstance(result.get("hygiene_summary"), Mapping) else {}
    runtime_after = result.get("runtime_footprint_after") if isinstance(result.get("runtime_footprint_after"), Mapping) else {}
    local_cache_removed_bytes = int(result.get("local_cache_cleanup_removed_bytes") or 0)
    partial_video_reclaimed_bytes = int(result.get("partial_video_artifact_cleanup_reclaimed_bytes") or 0)
    reclaimed_bytes = (
        int(result.get("runtime_footprint_reclaimed_bytes") or 0)
        + local_cache_removed_bytes
        + partial_video_reclaimed_bytes
    )
    removed_files = (
        int(result.get("removed_count") or 0)
        + int(result.get("stale_output_removed_count") or 0)
        + int(result.get("removed_alert_report_count") or 0)
        + int(result.get("removed_log_snapshot_count") or 0)
    )
    trimmed_items = int(result.get("trimmed_log_count") or 0) + int(result.get("trimmed_history_count") or 0)
    trimmed_history_min_lines_relaxed_count = int(result.get("trimmed_history_min_lines_relaxed_count") or 0)
    dashboard_rows_removed = int(result.get("dashboard_history_removed_rows") or 0)
    local_cache_removed_count = int(result.get("local_cache_cleanup_removed_count") or 0)
    partial_video_removed_count = int(result.get("partial_video_artifact_cleanup_removed_count") or 0)
    action_count = (
        removed_files
        + trimmed_items
        + dashboard_rows_removed
        + local_cache_removed_count
        + partial_video_removed_count
    )
    archive_count = int(result.get("output_archive_count") or 0)
    protected = bool(hygiene.get("protected"))
    internal_protected = bool(hygiene.get("internal_protected", protected))
    external_snapshot_degraded = bool(hygiene.get("external_snapshot_degraded"))
    hygiene_status = str(hygiene.get("status") or "").upper()
    dry_run = bool(result.get("dry_run"))
    if dry_run:
        label = "Simulacion"
        tone = "watch"
        status = "WARN"
    elif hygiene_status == "OK" and protected and action_count:
        label = "Limpieza aplicada"
        tone = "buy"
        status = "OK"
    elif hygiene_status == "OK" and protected:
        label = "Protegido"
        tone = "buy"
        status = "OK"
    elif hygiene_status == "WARN" and internal_protected and external_snapshot_degraded:
        label = "Interno protegido / snapshots degradados"
        tone = "watch"
        status = "WARN"
    elif hygiene_status == "WARN":
        label = "Revisar limpieza"
        tone = str(hygiene.get("tone") or "watch")
        status = "WARN"
    else:
        label = str(hygiene.get("label") or "Sin resumen")
        tone = str(hygiene.get("tone") or "watch")
        status = hygiene_status or "UNKNOWN"
    detail_parts = [
        f"acciones {action_count}",
        f"archivados {archive_count}",
        f"recuperado {reclaimed_bytes / (1024**2):.1f}MB",
        f"huella {float(runtime_after.get('total_mb') or 0.0):.1f}MB",
        f"accion {hygiene.get('next_action') or '-'}",
    ]
    local_cache_status = str(result.get("local_cache_cleanup_status") or "")
    if local_cache_status:
        detail_parts.append(f"cache local {local_cache_status.lower()}")
        if local_cache_removed_count:
            detail_parts.append(f"cache removidos {local_cache_removed_count}")
    partial_video_status = str(result.get("partial_video_artifact_cleanup_status") or "")
    if partial_video_status:
        detail_parts.append(f"video parciales {partial_video_status.lower()}")
        if partial_video_removed_count:
            detail_parts.append(f"video parciales removidos {partial_video_removed_count}")
    if trimmed_history_min_lines_relaxed_count:
        detail_parts.append(f"hist min relajado {trimmed_history_min_lines_relaxed_count}")
    issues = hygiene.get("issues") if isinstance(hygiene.get("issues"), list) else []
    if issues:
        detail_parts.append("issues " + "; ".join(str(item) for item in issues[:3]))
    return {
        "status": status,
        "label": label,
        "tone": tone if tone in {"buy", "watch", "avoid", "neutral"} else "watch",
        "detail": " | ".join(detail_parts),
        "protected": protected,
        "internal_protected": internal_protected,
        "external_snapshot_degraded": external_snapshot_degraded,
        "action_count": action_count,
        "removed_file_count": removed_files,
        "trimmed_item_count": trimmed_items,
        "trimmed_history_min_lines_relaxed_count": trimmed_history_min_lines_relaxed_count,
        "dashboard_history_removed_rows": dashboard_rows_removed,
        "local_cache_removed_count": local_cache_removed_count,
        "local_cache_removed_bytes": local_cache_removed_bytes,
        "partial_video_artifact_removed_count": partial_video_removed_count,
        "partial_video_artifact_reclaimed_bytes": partial_video_reclaimed_bytes,
        "archive_count": archive_count,
        "reclaimed_bytes": reclaimed_bytes,
        "reclaimed_mb": round(reclaimed_bytes / (1024**2), 3),
        "runtime_footprint_mb": round(float(runtime_after.get("total_mb") or 0.0), 3),
        "next_action": str(hygiene.get("next_action") or ""),
        "issues": [str(item) for item in issues],
    }


def maintenance_top_level_aliases(result: Mapping[str, Any]) -> dict[str, Any]:
    hygiene = result.get("hygiene_summary") if isinstance(result.get("hygiene_summary"), Mapping) else {}
    operation = result.get("operation_summary") if isinstance(result.get("operation_summary"), Mapping) else {}
    local_cache = result.get("local_cache_cleanup") if isinstance(result.get("local_cache_cleanup"), Mapping) else {}
    history_reports = result.get("history_budget_reports") if isinstance(result.get("history_budget_reports"), list) else []
    history_budget_attention_files = (
        result.get("history_budget_attention_files")
        if isinstance(result.get("history_budget_attention_files"), list)
        else []
    )
    history_budget_projected_attention_files = (
        result.get("history_budget_projected_attention_files")
        if isinstance(result.get("history_budget_projected_attention_files"), list)
        else []
    )
    byte_margins: list[int] = []
    projected_ratios: list[float] = []
    projected_statuses: list[str] = []
    append_estimates: list[int] = []
    append_estimate_items: list[tuple[int, Mapping[str, Any]]] = []
    for item in history_reports:
        if not isinstance(item, Mapping):
            continue
        try:
            if item.get("byte_margin") is not None:
                byte_margins.append(int(item.get("byte_margin") or 0))
        except (TypeError, ValueError):
            pass
        try:
            if item.get("estimated_appends_until_warn") is not None:
                append_estimate = int(item.get("estimated_appends_until_warn") or 0)
                append_estimates.append(append_estimate)
                append_estimate_items.append((append_estimate, item))
        except (TypeError, ValueError):
            pass
        for key in ("projected_next_line_ratio", "projected_next_byte_ratio"):
            try:
                if item.get(key) is not None:
                    projected_ratios.append(float(item.get(key) or 0.0))
            except (TypeError, ValueError):
                pass
        projected_status = str(item.get("projected_next_status") or "").upper()
        if projected_status:
            projected_statuses.append(projected_status)
    if "OVER_LIMIT" in projected_statuses:
        projected_pressure = "OVER_LIMIT"
    elif "NEAR_LIMIT" in projected_statuses:
        projected_pressure = "NEAR_LIMIT"
    else:
        projected_pressure = "CLEAR"
    top_append_estimate_item = (
        min(append_estimate_items, key=lambda entry: entry[0])[1]
        if append_estimate_items
        else {}
    )
    history_budget_report_count = int(result.get("history_budget_report_count") or len(history_reports))
    history_budget_available = isinstance(result.get("history_budget_reports"), list) or (
        "history_budget_report_count" in result
    )
    history_budget_top = (
        result.get("history_budget_top") if isinstance(result.get("history_budget_top"), Mapping) else {}
    )
    history_budget_top_name = str(result.get("history_budget_top_name") or history_budget_top.get("name") or "")
    history_budget_top_status = str(
        result.get("history_budget_top_status") or history_budget_top.get("status") or ""
    )
    history_budget_top_line_ratio = result.get("history_budget_top_line_ratio", history_budget_top.get("line_ratio"))
    history_budget_top_byte_ratio = result.get("history_budget_top_byte_ratio", history_budget_top.get("byte_ratio"))
    history_budget_top_line_margin = result.get("history_budget_top_line_margin", history_budget_top.get("line_margin"))
    history_budget_top_byte_margin = result.get("history_budget_top_byte_margin", history_budget_top.get("byte_margin"))
    history_budget_projected_top = (
        result.get("history_budget_projected_top")
        if isinstance(result.get("history_budget_projected_top"), Mapping)
        else {}
    )
    history_budget_projected_top_name = str(
        result.get("history_budget_projected_top_name") or history_budget_projected_top.get("name") or ""
    )
    history_budget_projected_top_status = str(
        result.get("history_budget_projected_top_status")
        or history_budget_projected_top.get("projected_next_status")
        or ""
    )
    history_budget_projected_top_line_ratio = result.get(
        "history_budget_projected_top_line_ratio",
        history_budget_projected_top.get("projected_next_line_ratio"),
    )
    history_budget_projected_top_byte_ratio = result.get(
        "history_budget_projected_top_byte_ratio",
        history_budget_projected_top.get("projected_next_byte_ratio"),
    )
    history_budget_projected_top_line_count = result.get(
        "history_budget_projected_top_line_count",
        history_budget_projected_top.get("projected_next_line_count"),
    )
    history_budget_projected_top_bytes = result.get(
        "history_budget_projected_top_bytes",
        history_budget_projected_top.get("projected_next_bytes"),
    )
    history_budget_projected_top_byte_margin = result.get(
        "history_budget_projected_top_byte_margin",
        history_budget_projected_top.get("projected_next_byte_margin"),
    )
    history_budget_min_estimated_appends_until_warn = min(append_estimates) if append_estimates else None
    history_budget_min_estimated_appends_until_warn_name = (
        str(
            top_append_estimate_item.get("name")
            or Path(str(top_append_estimate_item.get("path") or "")).name
        )
        if top_append_estimate_item
        else ""
    )
    history_budget_min_estimated_appends_until_line_warn = (
        top_append_estimate_item.get("estimated_appends_until_line_warn")
    )
    history_budget_min_estimated_appends_until_byte_warn = (
        top_append_estimate_item.get("estimated_appends_until_byte_warn")
    )
    trimmed_history_files = [
        str(item.get("name") or Path(str(item.get("path") or "")).name)
        for item in (result.get("trimmed_histories") if isinstance(result.get("trimmed_histories"), list) else [])
        if isinstance(item, Mapping) and (item.get("name") or item.get("path"))
    ]
    trimmed_history_min_lines_relaxed_files = [
        str(item.get("name") or Path(str(item.get("path") or "")).name)
        for item in (result.get("trimmed_histories") if isinstance(result.get("trimmed_histories"), list) else [])
        if isinstance(item, Mapping)
        and item.get("min_lines_relaxed") is True
        and (item.get("name") or item.get("path"))
    ]
    return {
        "operation": str(operation.get("label") or ""),
        "operation_status": str(operation.get("status") or ""),
        "operation_detail": str(operation.get("detail") or ""),
        "operation_action_count": int(operation.get("action_count") or 0),
        "operation_reclaimed_mb": operation.get("reclaimed_mb"),
        "hygiene_status": str(hygiene.get("status") or ""),
        "hygiene_label": str(hygiene.get("label") or ""),
        "hygiene_detail": str(hygiene.get("detail") or ""),
        "hygiene_protected": bool(hygiene.get("protected", False)),
        "hygiene_internal_protected": bool(hygiene.get("internal_protected", False)),
        "hygiene_external_snapshot_degraded": bool(hygiene.get("external_snapshot_degraded", False)),
        "history_budget_margin_bytes": min(byte_margins) if byte_margins else None,
        "history_budget_min_estimated_appends_until_warn": history_budget_min_estimated_appends_until_warn,
        "history_budget_min_estimated_appends_until_warn_name": history_budget_min_estimated_appends_until_warn_name,
        "history_budget_min_estimated_appends_until_line_warn": (
            history_budget_min_estimated_appends_until_line_warn
        ),
        "history_budget_min_estimated_appends_until_byte_warn": (
            history_budget_min_estimated_appends_until_byte_warn
        ),
        "history_budget_files": [
            str(item.get("name") or Path(str(item.get("path") or "")).name)
            for item in history_budget_attention_files
            if isinstance(item, Mapping) and (item.get("name") or item.get("path"))
        ],
        "history_budget_projected_pressure": projected_pressure,
        "history_budget_projected_near_count": int(result.get("history_budget_projected_near_limit_count") or 0),
        "history_budget_projected_over_count": int(result.get("history_budget_projected_over_limit_count") or 0),
        "history_budget_projected_files": [
            str(item.get("name") or Path(str(item.get("path") or "")).name)
            for item in history_budget_projected_attention_files
            if isinstance(item, Mapping) and (item.get("name") or item.get("path"))
        ],
        "top_projected_history_budget_file": str(result.get("history_budget_projected_top_name") or ""),
        "history_budget_max_projected_usage_ratio": (
            round(max(projected_ratios), 4) if projected_ratios else None
        ),
        "current_history_budget_available": history_budget_available,
        "current_history_budget_report_count": history_budget_report_count,
        "current_history_budget_near_limit_count": int(result.get("history_budget_near_limit_count") or 0),
        "current_history_budget_over_limit_count": int(result.get("history_budget_over_limit_count") or 0),
        "current_history_budget_at_cap_count": int(result.get("history_budget_at_cap_count") or 0),
        "current_history_budget_projected_near_limit_count": int(
            result.get("history_budget_projected_near_limit_count") or 0
        ),
        "current_history_budget_projected_over_limit_count": int(
            result.get("history_budget_projected_over_limit_count") or 0
        ),
        "current_history_budget_status": str(result.get("history_budget_status") or ""),
        "current_history_budget_pressure": str(result.get("history_budget_pressure") or ""),
        "current_history_budget_attention_file_count": int(
            result.get("history_budget_attention_file_count") or 0
        ),
        "current_history_budget_projected_attention_file_count": int(
            result.get("history_budget_projected_attention_file_count") or 0
        ),
        "current_history_budget_top_name": history_budget_top_name,
        "current_history_budget_top_status": history_budget_top_status,
        "current_history_budget_top_line_ratio": history_budget_top_line_ratio,
        "current_history_budget_top_byte_ratio": history_budget_top_byte_ratio,
        "current_history_budget_top_line_margin": history_budget_top_line_margin,
        "current_history_budget_top_byte_margin": history_budget_top_byte_margin,
        "current_history_budget_projected_top_name": history_budget_projected_top_name,
        "current_history_budget_projected_top_status": history_budget_projected_top_status,
        "current_history_budget_projected_top_line_ratio": history_budget_projected_top_line_ratio,
        "current_history_budget_projected_top_byte_ratio": history_budget_projected_top_byte_ratio,
        "current_history_budget_projected_top_line_count": history_budget_projected_top_line_count,
        "current_history_budget_projected_top_bytes": history_budget_projected_top_bytes,
        "current_history_budget_projected_top_byte_margin": history_budget_projected_top_byte_margin,
        "current_history_budget_min_estimated_appends_until_warn": (
            history_budget_min_estimated_appends_until_warn
        ),
        "current_history_budget_min_estimated_appends_until_warn_name": (
            history_budget_min_estimated_appends_until_warn_name
        ),
        "current_history_budget_min_estimated_appends_until_line_warn": (
            history_budget_min_estimated_appends_until_line_warn
        ),
        "current_history_budget_min_estimated_appends_until_byte_warn": (
            history_budget_min_estimated_appends_until_byte_warn
        ),
        "dashboard_history_rows": result.get("dashboard_history_after_rows"),
        "trimmed_history_files": trimmed_history_files,
        "trimmed_history_lines": int(result.get("trimmed_history_removed_lines") or 0),
        "trimmed_history_bytes": int(result.get("trimmed_history_removed_bytes") or 0),
        "trimmed_history_min_lines_relaxed_count": int(
            result.get("trimmed_history_min_lines_relaxed_count") or len(trimmed_history_min_lines_relaxed_files)
        ),
        "trimmed_history_min_lines_relaxed_files": trimmed_history_min_lines_relaxed_files,
        "top_min_lines_relaxed_history_file": (
            str(result.get("trimmed_history_min_lines_relaxed_top_name") or "")
            or (trimmed_history_min_lines_relaxed_files[0] if trimmed_history_min_lines_relaxed_files else "")
        ),
        "local_cache_plan": (
            result.get("local_cache_cleanup_plan_state")
            or str(
                result.get("local_cache_cleanup_blocked_reason")
                or local_cache.get("reason")
                or ""
            ).upper()
        ),
        "local_cache_status": result.get("local_cache_cleanup_status"),
        "local_cache_eligible_count": int(result.get("local_cache_cleanup_eligible_count") or 0),
        "local_cache_removed_count": int(result.get("local_cache_cleanup_removed_count") or 0),
        "partial_video_artifact_cleanup_status": result.get("partial_video_artifact_cleanup_status"),
        "partial_video_artifact_removed_count": int(result.get("partial_video_artifact_cleanup_removed_count") or 0),
        "partial_video_artifact_reclaimed_mb": result.get("partial_video_artifact_cleanup_reclaimed_mb"),
    }


def cleanup_alert_report_files(
    *,
    alerts_path: str | Path = ALERTS_DIR,
    retention_rules: Mapping[str, int] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(alerts_path)
    rules = dict(retention_rules or DEFAULT_ALERT_REPORT_RETENTION_RULES)
    removed: list[str] = []
    kept_counts: dict[str, int] = {}
    removed_counts: dict[str, int] = {}
    if not root.exists():
        return {
            "alerts_dir": str(root),
            "removed": removed,
            "removed_count": 0,
            "kept_counts": kept_counts,
            "removed_counts": removed_counts,
            "exists": False,
        }
    for pattern, keep_count in rules.items():
        keep_count = max(0, int(keep_count))
        files = sorted(
            [path for path in root.glob(pattern) if path.is_file()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        kept_counts[pattern] = min(len(files), keep_count)
        stale = files[keep_count:]
        removed_counts[pattern] = len(stale)
        for path in stale:
            removed.append(str(path))
            if not dry_run:
                path.unlink()
    return {
        "alerts_dir": str(root),
        "removed": removed,
        "removed_count": len(removed),
        "kept_counts": kept_counts,
        "removed_counts": removed_counts,
        "exists": True,
    }


def cleanup_log_snapshots(
    *,
    snapshot_dir: str | Path = DEFAULT_LOG_SNAPSHOT_DIR,
    patterns: tuple[str, ...] = ("*.err.*", "*.out.*", "*.log.*"),
    keep_count: int = DEFAULT_LOG_SNAPSHOT_KEEP_COUNT,
    scan_timeout_seconds: float = DEFAULT_LOG_SNAPSHOT_SCAN_TIMEOUT_SECONDS,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(snapshot_dir)
    removed: list[str] = []
    kept_counts: dict[str, int] = {}
    removed_counts: dict[str, int] = {}
    scan_errors: dict[str, str] = {}
    keep_count = max(0, int(keep_count))
    if not root.exists():
        return {
            "snapshot_dir": str(root),
            "removed": removed,
            "removed_count": 0,
            "kept_counts": kept_counts,
            "removed_counts": removed_counts,
            "exists": False,
        }
    try:
        scan = subprocess.run(
            [
                "/usr/bin/find",
                str(root),
                "-maxdepth",
                "1",
                "-type",
                "f",
                "-print0",
            ],
            capture_output=True,
            check=False,
            timeout=max(0.1, float(scan_timeout_seconds)),
        )
    except subprocess.TimeoutExpired:
        scan = None
        scan_error = f"timeout>{float(scan_timeout_seconds):.1f}s"
    else:
        scan_error = ""
        if scan.returncode != 0:
            detail = scan.stderr.decode("utf-8", errors="replace").strip()
            scan_error = detail or f"find_exit_{scan.returncode}"
    candidates = (
        [Path(os.fsdecode(item)) for item in scan.stdout.split(b"\0") if item]
        if scan is not None and not scan_error
        else []
    )
    for pattern in patterns:
        if scan_error:
            scan_errors[pattern] = scan_error
            kept_counts[pattern] = 0
            removed_counts[pattern] = 0
            continue
        files = sorted(
            [path for path in candidates if fnmatch.fnmatch(path.name, pattern) and path.is_file()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        kept_counts[pattern] = min(len(files), keep_count)
        stale = files[keep_count:]
        removed_counts[pattern] = len(stale)
        for path in stale:
            removed.append(str(path))
            if not dry_run:
                path.unlink()
    return {
        "snapshot_dir": str(root),
        "removed": removed,
        "removed_count": len(removed),
        "kept_counts": kept_counts,
        "removed_counts": removed_counts,
        "scan_status": "WARN" if scan_errors else "OK",
        "scan_errors": scan_errors,
        "scan_timeout_seconds": float(scan_timeout_seconds),
        "exists": True,
    }


def compact_dashboard_history_file(
    scan_history_path: str | Path | None = DEFAULT_DASHBOARD_HISTORY_PATH,
    *,
    min_interval_seconds: float = DEFAULT_DASHBOARD_HISTORY_MIN_INTERVAL_SECONDS,
    max_rows: int = DEFAULT_DASHBOARD_HISTORY_MAX_ROWS,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not scan_history_path:
        return {"path": "", "enabled": False, "compacted": False, "reason": "disabled"}
    path = Path(scan_history_path)
    if not path.exists():
        return {
            "path": str(path),
            "enabled": True,
            "exists": False,
            "compacted": False,
            "reason": "missing",
            "before_rows": 0,
            "after_rows": 0,
            "removed_rows": 0,
            "dry_run": dry_run,
        }
    try:
        from dashboard_history import compact_scan_history
    except Exception as exc:
        return {
            "path": str(path),
            "enabled": True,
            "exists": True,
            "compacted": False,
            "reason": f"import_error:{type(exc).__name__}",
            "error": str(exc),
            "dry_run": dry_run,
        }
    if dry_run:
        try:
            import pandas as pd

            before_rows = len(pd.read_csv(path))
        except Exception as exc:
            return {
                "path": str(path),
                "enabled": True,
                "exists": True,
                "compacted": False,
                "reason": f"unreadable:{type(exc).__name__}",
                "before_rows": 0,
                "after_rows": 0,
                "removed_rows": 0,
                "dry_run": dry_run,
            }
        return {
            "path": str(path),
            "enabled": True,
            "exists": True,
            "compacted": False,
            "reason": "dry_run",
            "before_rows": before_rows,
            "after_rows": before_rows,
            "removed_rows": 0,
            "dry_run": dry_run,
            "max_rows": int(max_rows),
            "min_interval_seconds": float(min_interval_seconds),
        }
    result = compact_scan_history(
        path,
        min_interval_seconds=float(min_interval_seconds),
        max_rows=int(max_rows),
    )
    result.update(
        {
            "path": str(path),
            "enabled": True,
            "exists": True,
            "dry_run": dry_run,
            "max_rows": int(max_rows),
            "min_interval_seconds": float(min_interval_seconds),
        }
    )
    return result


def sqlite_db_maintenance(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    dry_run: bool = False,
    vacuum_min_reclaim_mb: float = DEFAULT_SQLITE_VACUUM_MIN_RECLAIM_MB,
) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "status": "MISSING",
            "size_bytes": 0,
            "size_mb": 0.0,
            "page_count": 0,
            "freelist_count": 0,
            "page_size": 0,
            "reclaimable_bytes": 0,
            "reclaimable_mb": 0.0,
            "optimized": False,
            "vacuumed": False,
            "dry_run": dry_run,
        }
    before_size = path.stat().st_size
    try:
        with sqlite3.connect(str(path), timeout=2.0) as conn:
            page_count = int(conn.execute("PRAGMA page_count").fetchone()[0] or 0)
            freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0] or 0)
            page_size = int(conn.execute("PRAGMA page_size").fetchone()[0] or 0)
            reclaimable_bytes = freelist_count * page_size
            reclaimable_mb = round(reclaimable_bytes / (1024**2), 3)
            optimized = False
            vacuumed = False
            if not dry_run:
                conn.execute("PRAGMA optimize")
                optimized = True
                if reclaimable_mb >= float(vacuum_min_reclaim_mb) and freelist_count > 0:
                    conn.execute("VACUUM")
                    vacuumed = True
                    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0] or 0)
                    freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0] or 0)
                    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0] or 0)
                    reclaimable_bytes = freelist_count * page_size
                    reclaimable_mb = round(reclaimable_bytes / (1024**2), 3)
    except sqlite3.Error as exc:
        return {
            "path": str(path),
            "exists": True,
            "status": "ERROR",
            "error": str(exc),
            "size_bytes": before_size,
            "size_mb": round(before_size / (1024**2), 3),
            "optimized": False,
            "vacuumed": False,
            "dry_run": dry_run,
        }
    after_size = path.stat().st_size
    return {
        "path": str(path),
        "exists": True,
        "status": "OK",
        "size_bytes": after_size,
        "size_mb": round(after_size / (1024**2), 3),
        "before_size_bytes": before_size,
        "page_count": page_count,
        "freelist_count": freelist_count,
        "page_size": page_size,
        "reclaimable_bytes": reclaimable_bytes,
        "reclaimable_mb": reclaimable_mb,
        "reclaimed_bytes": max(0, before_size - after_size),
        "optimized": optimized,
        "vacuumed": vacuumed,
        "vacuum_min_reclaim_mb": float(vacuum_min_reclaim_mb),
        "dry_run": dry_run,
    }


def load_local_storage_pressure_check(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    report_path = Path(path)
    try:
        payload = json.loads(report_path.read_text())
    except FileNotFoundError:
        return {"name": "local_storage_pressure_sources", "status": "MISSING", "path": str(report_path)}
    except Exception as exc:
        return {
            "name": "local_storage_pressure_sources",
            "status": "MALFORMED",
            "path": str(report_path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    if isinstance(payload, dict) and isinstance(payload.get("check"), dict):
        check = dict(payload["check"])
    elif isinstance(payload, dict):
        check = dict(payload)
    else:
        return {
            "name": "local_storage_pressure_sources",
            "status": "MALFORMED",
            "path": str(report_path),
            "error": "payload is not an object",
        }
    check.setdefault("path", str(report_path))
    return normalize_local_storage_pressure_check(check)


def normalize_local_storage_pressure_check(check: dict[str, Any]) -> dict[str, Any]:
    if check.get("cleanup_plan_state"):
        return check
    top_entries = check.get("top_entries") if isinstance(check.get("top_entries"), list) else []
    safe_entries = check.get("safe_cleanup_entries") if isinstance(check.get("safe_cleanup_entries"), list) else []
    manual_entries = check.get("manual_review_entries") if isinstance(check.get("manual_review_entries"), list) else []
    pressure_active = bool(check.get("pressure_active"))
    top_entry = top_entries[0] if top_entries and isinstance(top_entries[0], dict) else {}
    top_policy = str(top_entry.get("cleanup_policy") or "").upper()
    if not pressure_active:
        plan_state = "CLEAR"
        priority = "none"
        ready = False
        blocked = ""
    elif top_policy == "MANUAL_REVIEW_REQUIRED":
        plan_state = "MANUAL_REVIEW_REQUIRED"
        priority = "manual_review"
        ready = False
        blocked = "manual_top_source"
    elif safe_entries:
        plan_state = "SAFE_CACHE_REVIEW_READY"
        priority = "safe_cache"
        ready = True
        blocked = ""
    elif manual_entries:
        plan_state = "MANUAL_REVIEW_REQUIRED"
        priority = "manual_review"
        ready = False
        blocked = "manual_candidates_present"
    else:
        plan_state = "INSPECT_MANUALLY"
        priority = "inspect"
        ready = False
        blocked = "no_safe_candidates"
    check["cleanup_plan_state"] = plan_state
    check["cleanup_priority"] = priority
    check["cleanup_automation_ready"] = ready
    check["cleanup_automation_blocked_reason"] = blocked
    return check


def is_child_path(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def local_safe_cache_cleanup_candidates(
    safe_entries: list[Any],
    *,
    min_age_days: float = DEFAULT_LOCAL_CACHE_CLEANUP_MIN_AGE_DAYS,
    max_bytes: int = DEFAULT_LOCAL_CACHE_CLEANUP_MAX_BYTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    cutoff = (now or datetime.now(timezone.utc)).timestamp() - (float(min_age_days) * 86400.0)
    allowed_names = {name.lower() for name in SAFE_LOCAL_CACHE_CLEANUP_NAMES}
    skipped: list[dict[str, str]] = []
    candidates: list[Path] = []
    fresh_protected_count = 0
    fresh_protected_bytes = 0
    for raw_entry in safe_entries:
        if not isinstance(raw_entry, dict):
            continue
        name = str(raw_entry.get("name") or "").strip()
        root = Path(str(raw_entry.get("path") or ""))
        if name.lower() not in allowed_names:
            skipped.append({"path": str(root), "reason": "unsafe_name"})
            continue
        if not root.exists() or not root.is_dir() or root.is_symlink():
            skipped.append({"path": str(root), "reason": "not_directory"})
            continue
        for child in sorted(root.rglob("*"), key=lambda item: str(item)):
            if not child.is_file() or child.is_symlink() or not is_child_path(child, root):
                continue
            try:
                stat = child.stat()
            except OSError:
                skipped.append({"path": str(child), "reason": "stat_error"})
                continue
            if stat.st_mtime > cutoff:
                fresh_protected_count += 1
                fresh_protected_bytes += int(stat.st_size)
                continue
            candidates.append(child)

    selected: list[Path] = []
    selected_bytes = 0
    for path in sorted(candidates, key=lambda item: item.stat().st_mtime):
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append({"path": str(path), "reason": "stat_error"})
            continue
        if selected_bytes + size > int(max(0, max_bytes)):
            skipped.append({"path": str(path), "reason": "byte_budget"})
            continue
        selected.append(path)
        selected_bytes += size
    return {
        "candidates": selected,
        "candidate_count": len(selected),
        "candidate_bytes": selected_bytes,
        "candidate_mb": round(selected_bytes / (1024**2), 3),
        "fresh_protected_count": fresh_protected_count,
        "fresh_protected_bytes": fresh_protected_bytes,
        "fresh_protected_mb": round(fresh_protected_bytes / (1024**2), 3),
        "skipped": skipped,
        "skipped_count": len(skipped),
    }


def cleanup_local_safe_cache_from_pressure_report(
    *,
    report_path: str | Path | None = DEFAULT_LOCAL_STORAGE_PRESSURE_REPORT_PATH,
    enabled: bool = False,
    dry_run: bool = False,
    min_age_days: float = DEFAULT_LOCAL_CACHE_CLEANUP_MIN_AGE_DAYS,
    max_bytes: int = DEFAULT_LOCAL_CACHE_CLEANUP_MAX_BYTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    check = load_local_storage_pressure_check(report_path)
    plan_state = str(check.get("cleanup_plan_state") or "").upper()
    automation_ready = bool(check.get("cleanup_automation_ready"))
    blocked_reason = str(check.get("cleanup_automation_blocked_reason") or "")
    safe_entries = check.get("safe_cleanup_entries") if isinstance(check.get("safe_cleanup_entries"), list) else []
    result: dict[str, Any] = {
        "enabled": bool(enabled),
        "dry_run": bool(dry_run),
        "report_path": str(report_path or ""),
        "check_status": check.get("status", ""),
        "plan_state": plan_state,
        "automation_ready": automation_ready,
        "blocked_reason": blocked_reason,
        "candidate_count": len(safe_entries),
        "eligible_count": 0,
        "eligible_bytes": 0,
        "eligible_mb": 0.0,
        "fresh_protected_count": 0,
        "fresh_protected_bytes": 0,
        "fresh_protected_mb": 0.0,
        "removed": [],
        "removed_count": 0,
        "removed_bytes": 0,
        "max_bytes": int(max(0, max_bytes)),
        "min_age_days": float(min_age_days),
        "skipped": [],
        "skipped_count": 0,
        "skipped_bytes": 0,
        "skipped_mb": 0.0,
        "skipped_top_reason": "",
        "skipped_top_path": "",
        "skipped_ratio": None,
        "skip_state": "CLEAR",
        "retry_recommended": False,
    }
    if not check:
        result.update({"status": "MISSING", "reason": "pressure_report_missing"})
        return result
    if check.get("status") in {"MISSING", "MALFORMED"}:
        result.update({"status": "BLOCKED", "reason": str(check.get("status")).lower()})
        return result
    if not automation_ready or plan_state != "SAFE_CACHE_REVIEW_READY":
        result.update({"status": "BLOCKED", "reason": blocked_reason or "automation_not_ready"})
        return result

    candidate_plan = local_safe_cache_cleanup_candidates(
        safe_entries,
        min_age_days=min_age_days,
        max_bytes=max_bytes,
        now=now,
    )
    candidates = candidate_plan["candidates"]
    skipped = list(candidate_plan["skipped"])
    result.update(
        {
            "eligible_count": candidate_plan["candidate_count"],
            "eligible_bytes": candidate_plan["candidate_bytes"],
            "eligible_mb": candidate_plan["candidate_mb"],
            "fresh_protected_count": candidate_plan["fresh_protected_count"],
            "fresh_protected_bytes": candidate_plan["fresh_protected_bytes"],
            "fresh_protected_mb": candidate_plan["fresh_protected_mb"],
            "skipped": skipped,
            "skipped_count": candidate_plan["skipped_count"],
            "skipped_bytes": cleanup_skipped_bytes({"skipped": skipped}),
            "skipped_mb": round(cleanup_skipped_bytes({"skipped": skipped}) / (1024**2), 3),
            "skipped_top_reason": first_cleanup_skip_metadata({"skipped": skipped})["reason"],
            "skipped_top_path": first_cleanup_skip_metadata({"skipped": skipped})["path"],
        }
    )
    result.update(local_cache_cleanup_skip_summary(result))
    if not enabled:
        result.update({"status": "SKIPPED", "reason": "disabled"})
        return result

    removed: list[str] = []
    removed_bytes = 0
    for path in candidates:
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append({"path": str(path), "reason": "stat_error"})
            continue
        if not dry_run:
            try:
                path.unlink()
            except OSError:
                skipped.append({"path": str(path), "reason": "unlink_error", "bytes": int(size)})
                continue
        removed.append(str(path))
        removed_bytes += size

    result.update(
        {
            "status": "DRY_RUN" if dry_run else "DONE",
            "reason": "",
            "removed": removed,
            "removed_count": len(removed),
            "removed_bytes": removed_bytes,
            "removed_mb": round(removed_bytes / (1024**2), 3),
            "skipped": skipped,
            "skipped_count": len(skipped),
            "skipped_bytes": cleanup_skipped_bytes({"skipped": skipped}),
            "skipped_mb": round(cleanup_skipped_bytes({"skipped": skipped}) / (1024**2), 3),
            "skipped_top_reason": first_cleanup_skip_metadata({"skipped": skipped})["reason"],
            "skipped_top_path": first_cleanup_skip_metadata({"skipped": skipped})["path"],
        }
    )
    result.update(local_cache_cleanup_skip_summary(result))
    return result


def first_cleanup_skip_metadata(cleanup_result: Mapping[str, Any]) -> dict[str, str]:
    skipped = cleanup_result.get("skipped") if isinstance(cleanup_result.get("skipped"), list) else []
    for item in skipped:
        if not isinstance(item, Mapping):
            continue
        return {
            "reason": str(item.get("reason") or ""),
            "path": str(item.get("path") or ""),
        }
    return {"reason": "", "path": ""}


def cleanup_skipped_bytes(cleanup_result: Mapping[str, Any]) -> int:
    skipped = cleanup_result.get("skipped") if isinstance(cleanup_result.get("skipped"), list) else []
    total = 0
    for item in skipped:
        if not isinstance(item, Mapping):
            continue
        try:
            total += max(0, int(item.get("bytes") or 0))
        except (TypeError, ValueError):
            continue
    return total


def local_cache_cleanup_skip_summary(cleanup_result: Mapping[str, Any]) -> dict[str, Any]:
    try:
        eligible_bytes = int(cleanup_result.get("eligible_bytes") or 0)
    except (TypeError, ValueError):
        eligible_bytes = 0
    try:
        skipped_bytes = int(cleanup_result.get("skipped_bytes") or 0)
    except (TypeError, ValueError):
        skipped_bytes = 0
    try:
        eligible_mb = float(cleanup_result.get("eligible_mb") or 0.0)
    except (TypeError, ValueError):
        eligible_mb = 0.0
    try:
        skipped_mb = float(cleanup_result.get("skipped_mb") or 0.0)
    except (TypeError, ValueError):
        skipped_mb = 0.0
    try:
        skipped_count = int(cleanup_result.get("skipped_count") or 0)
    except (TypeError, ValueError):
        skipped_count = 0
    skipped_positive = skipped_bytes > 0 or skipped_mb > 0 or skipped_count > 0
    skipped_ratio = None
    skip_state = "CLEAR"
    if eligible_bytes > 0:
        skipped_ratio = round(max(skipped_bytes, 0) / eligible_bytes, 4)
        if skipped_positive and skipped_bytes >= eligible_bytes:
            skip_state = "ALL_ELIGIBLE_SKIPPED"
        elif skipped_positive:
            skip_state = "PARTIAL_SKIPPED"
    elif eligible_mb > 0:
        skipped_ratio = round(max(skipped_mb, 0.0) / eligible_mb, 4)
        if skipped_positive and skipped_mb + 0.0005 >= eligible_mb:
            skip_state = "ALL_ELIGIBLE_SKIPPED"
        elif skipped_positive:
            skip_state = "PARTIAL_SKIPPED"
    elif skipped_positive:
        skip_state = "SKIPPED_UNKNOWN_ELIGIBLE"
    return {
        "skipped_ratio": skipped_ratio,
        "skip_state": skip_state,
        "retry_recommended": skip_state in {"ALL_ELIGIBLE_SKIPPED", "SKIPPED_UNKNOWN_ELIGIBLE"},
    }


def cleanup_partial_video_learning_artifacts(
    *,
    training_videos_path: str | Path = DEFAULT_TRAINING_VIDEOS_PATH,
    enabled: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(training_videos_path)
    result: dict[str, Any] = {
        "enabled": bool(enabled),
        "path": str(root),
        "exists": root.exists(),
        "dry_run": bool(dry_run),
        "removed_count": 0,
        "removed": [],
        "skipped_count": 0,
        "skipped": [],
        "reclaimed_bytes": 0,
        "reclaimed_mb": 0.0,
    }
    if not enabled:
        result["status"] = "DISABLED"
        return result
    if not root.exists():
        result["status"] = "MISSING"
        return result
    try:
        from tools.video_learning_ingest import cleanup_partial_artifacts, load_json, update_index

        index = load_json(root / "video_learning_index.json", {"updated_at": None, "videos": [], "materials": []})
        cleanup = cleanup_partial_artifacts(root, index, dry_run=dry_run)
        result.update(cleanup)
        result["status"] = "DRY_RUN" if dry_run else "DONE"
        if int(cleanup.get("removed_count") or 0) and not dry_run:
            update_index(root, [], [])
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def cleanup_runtime_artifacts(
    *,
    output_dir: str | Path = OUTPUT_DIR,
    alerts_path: str | Path = ALERTS_DIR,
    log_dirs: list[str | Path] | None = None,
    retention_rules: Mapping[str, int] | None = None,
    stale_output_rules: Mapping[str, float] | None = None,
    output_archive_dir: str | Path | None = None,
    fallback_output_archive_dir: str | Path | None = DEFAULT_LOCAL_OUTPUT_ARCHIVE_DIR,
    dry_run: bool = False,
    max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
    max_history_lines: int = DEFAULT_MAX_HISTORY_LINES,
    max_history_bytes: int | None = DEFAULT_MAX_HISTORY_BYTES,
    min_history_lines: int = DEFAULT_MIN_HISTORY_LINES,
    alert_report_retention_rules: Mapping[str, int] | None = None,
    log_snapshot_dir: str | Path = DEFAULT_LOG_SNAPSHOT_DIR,
    log_snapshot_keep_count: int = DEFAULT_LOG_SNAPSHOT_KEEP_COUNT,
    sqlite_db_path: str | Path | None = DEFAULT_DB_PATH,
    sqlite_vacuum_min_reclaim_mb: float = DEFAULT_SQLITE_VACUUM_MIN_RECLAIM_MB,
    dashboard_history_path: str | Path | None = DEFAULT_DASHBOARD_HISTORY_PATH,
    dashboard_history_max_rows: int = DEFAULT_DASHBOARD_HISTORY_MAX_ROWS,
    dashboard_history_min_interval_seconds: float = DEFAULT_DASHBOARD_HISTORY_MIN_INTERVAL_SECONDS,
    local_storage_pressure_report_path: str | Path | None = None,
    enable_local_cache_cleanup: bool = False,
    local_cache_cleanup_min_age_days: float = DEFAULT_LOCAL_CACHE_CLEANUP_MIN_AGE_DAYS,
    local_cache_cleanup_max_bytes: int = DEFAULT_LOCAL_CACHE_CLEANUP_MAX_BYTES,
    training_videos_path: str | Path = DEFAULT_TRAINING_VIDEOS_PATH,
    enable_partial_video_artifact_cleanup: bool = True,
) -> dict[str, Any]:
    archive_resolution = resolve_output_archive_dir(
        output_archive_dir,
        fallback_dir=fallback_output_archive_dir,
        dry_run=dry_run,
    )
    requested_output_archive_dir = str(archive_resolution.get("requested_dir") or "")
    effective_output_archive_dir = str(archive_resolution.get("effective_dir") or "")
    output_archive_dir = effective_output_archive_dir or None
    footprint_before = runtime_footprint(output_dir=output_dir, alerts_path=alerts_path, log_dirs=log_dirs)
    prepared_dirs = prepare_maintenance_dirs(
        output_archive_dir=output_archive_dir,
        log_snapshot_dir=log_snapshot_dir,
        dry_run=dry_run,
    )
    result = cleanup_output_files(
        output_dir=output_dir,
        retention_rules=retention_rules,
        archive_dir=output_archive_dir,
        dry_run=dry_run,
    )
    stale_output = cleanup_stale_output_files(
        output_dir=output_dir,
        max_age_days_rules=stale_output_rules,
        archive_dir=output_archive_dir,
        dry_run=dry_run,
    )
    trimmed_logs = trim_log_files(log_dirs=log_dirs, max_bytes=max_log_bytes, dry_run=dry_run)
    trimmed_histories = trim_history_files(
        alerts_path=alerts_path,
        max_lines=max_history_lines,
        max_bytes=max_history_bytes,
        min_lines=min_history_lines,
        dry_run=dry_run,
    )
    history_budget_reports = history_file_budget_reports(
        alerts_path=alerts_path,
        max_lines=max_history_lines,
        max_bytes=max_history_bytes,
    )
    history_budget_near_limit = [
        item for item in history_budget_reports if item.get("status") == "NEAR_LIMIT"
    ]
    history_budget_over_limit = [
        item for item in history_budget_reports if item.get("status") == "OVER_LIMIT"
    ]
    history_budget_at_cap = [
        item for item in history_budget_reports if item.get("status") == "AT_CAP"
    ]
    history_budget_projected_near_limit = [
        item
        for item in history_budget_reports
        if item.get("status") == "OK" and item.get("projected_next_status") == "NEAR_LIMIT"
    ]
    history_budget_projected_over_limit = [
        item
        for item in history_budget_reports
        if item.get("status") == "OK" and item.get("projected_next_status") == "OVER_LIMIT"
    ]
    history_budget_attention = history_budget_over_limit or history_budget_near_limit or history_budget_at_cap
    history_budget_attention_files = history_budget_over_limit + history_budget_at_cap + history_budget_near_limit
    history_budget_projected_attention_files = (
        history_budget_projected_over_limit + history_budget_projected_near_limit
    )
    if history_budget_over_limit:
        history_budget_status = "FAIL"
        history_budget_pressure = "OVER_LIMIT"
    elif history_budget_at_cap:
        history_budget_status = "WARN"
        history_budget_pressure = "AT_CAP"
    elif history_budget_near_limit:
        history_budget_status = "WARN"
        history_budget_pressure = "NEAR_LIMIT"
    else:
        history_budget_status = "OK"
        history_budget_pressure = "CLEAR"
    history_budget_top = max(
        history_budget_attention,
        key=lambda item: max(float(item.get("line_ratio") or 0.0), float(item.get("byte_ratio") or 0.0)),
        default={},
    )
    history_budget_projected_top = max(
        history_budget_projected_attention_files,
        key=lambda item: max(
            float(item.get("projected_next_line_ratio") or 0.0),
            float(item.get("projected_next_byte_ratio") or 0.0),
        ),
        default={},
    )
    trimmed_history_removed_lines = sum(int(item.get("removed_lines") or 0) for item in trimmed_histories)
    trimmed_history_removed_bytes = sum(int(item.get("removed_bytes") or 0) for item in trimmed_histories)
    trimmed_history_min_lines_relaxed = [
        item for item in trimmed_histories if isinstance(item, Mapping) and item.get("min_lines_relaxed") is True
    ]
    trimmed_history_min_lines_relaxed_files = [
        str(item.get("name") or Path(str(item.get("path") or "")).name)
        for item in trimmed_history_min_lines_relaxed
        if item.get("name") or item.get("path")
    ]
    alert_reports = cleanup_alert_report_files(
        alerts_path=alerts_path,
        retention_rules=alert_report_retention_rules,
        dry_run=dry_run,
    )
    log_snapshots = cleanup_log_snapshots(
        snapshot_dir=log_snapshot_dir,
        keep_count=log_snapshot_keep_count,
        dry_run=dry_run,
    )
    dashboard_history = compact_dashboard_history_file(
        dashboard_history_path,
        min_interval_seconds=dashboard_history_min_interval_seconds,
        max_rows=dashboard_history_max_rows,
        dry_run=dry_run,
    )
    sqlite_maintenance = (
        sqlite_db_maintenance(
            sqlite_db_path,
            dry_run=dry_run,
            vacuum_min_reclaim_mb=sqlite_vacuum_min_reclaim_mb,
        )
        if sqlite_db_path
        else {}
    )
    pressure_report_path = (
        Path(local_storage_pressure_report_path)
        if local_storage_pressure_report_path is not None
        else Path(alerts_path) / DEFAULT_LOCAL_STORAGE_PRESSURE_REPORT_PATH.name
    )
    local_cache_cleanup = cleanup_local_safe_cache_from_pressure_report(
        report_path=pressure_report_path,
        enabled=enable_local_cache_cleanup,
        dry_run=dry_run,
        min_age_days=local_cache_cleanup_min_age_days,
        max_bytes=local_cache_cleanup_max_bytes,
    )
    partial_video_cleanup = cleanup_partial_video_learning_artifacts(
        training_videos_path=training_videos_path,
        enabled=enable_partial_video_artifact_cleanup,
        dry_run=dry_run,
    )
    local_cache_skip = first_cleanup_skip_metadata(local_cache_cleanup)
    local_cache_skip_summary = local_cache_cleanup_skip_summary(local_cache_cleanup)
    local_cache_cleanup = {**local_cache_cleanup, **local_cache_skip_summary}
    footprint_after = runtime_footprint(output_dir=output_dir, alerts_path=alerts_path, log_dirs=log_dirs)
    result.update(
        {
            "alerts_dir": str(alerts_path),
            "log_dirs": [str(path) for path in (log_dirs or [LOG_DIR, LAUNCHD_LOG_DIR])],
            "stale_output_removed": stale_output["removed"],
            "stale_output_removed_count": stale_output["removed_count"],
            "stale_output_archived": stale_output["archived"],
            "stale_output_archived_count": stale_output["archived_count"],
            "stale_output_removed_counts": stale_output["removed_counts"],
            "stale_output_kept_counts": stale_output["kept_counts"],
            "stale_output_max_age_days_rules": stale_output.get("max_age_days_rules", {}),
            "output_archive_dir": str(output_archive_dir) if output_archive_dir else "",
            "output_archive_requested_dir": requested_output_archive_dir,
            "output_archive_effective_dir": effective_output_archive_dir,
            "output_archive_fallback": bool(archive_resolution.get("fallback")),
            "output_archive_fallback_reason": str(archive_resolution.get("fallback_reason") or ""),
            "output_archive_writable": bool(archive_resolution.get("writable")),
            "output_archive_count": int(result.get("archived_count") or 0) + int(stale_output.get("archived_count") or 0),
            "output_archive_error_count": int(result.get("archive_error_count") or 0) + int(stale_output.get("archive_error_count") or 0),
            "prepared_dirs": prepared_dirs,
            "prepared_dir_count": prepared_dirs["created_dir_count"],
            "prepared_dir_error_count": prepared_dirs["dir_error_count"],
            "output_archive_exists": bool(prepared_dirs["dir_exists"].get("output_archive_dir")),
            "log_snapshot_dir_exists": bool(prepared_dirs["dir_exists"].get("log_snapshot_dir")),
            "trimmed_logs": trimmed_logs,
            "trimmed_log_count": len(trimmed_logs),
            "trimmed_histories": trimmed_histories,
            "trimmed_history_count": len(trimmed_histories),
            "trimmed_history_removed_lines": trimmed_history_removed_lines,
            "trimmed_history_removed_bytes": trimmed_history_removed_bytes,
            "trimmed_history_min_lines_relaxed_count": len(trimmed_history_min_lines_relaxed),
            "trimmed_history_min_lines_relaxed_files": trimmed_history_min_lines_relaxed_files[:5],
            "trimmed_history_min_lines_relaxed_top_name": (
                trimmed_history_min_lines_relaxed_files[0] if trimmed_history_min_lines_relaxed_files else None
            ),
            "history_budget_reports": history_budget_reports,
            "history_budget_report_count": len(history_budget_reports),
            "history_budget_near_limit_count": len(history_budget_near_limit),
            "history_budget_over_limit_count": len(history_budget_over_limit),
            "history_budget_at_cap_count": len(history_budget_at_cap),
            "history_budget_projected_near_limit_count": len(history_budget_projected_near_limit),
            "history_budget_projected_over_limit_count": len(history_budget_projected_over_limit),
            "history_budget_status": history_budget_status,
            "history_budget_pressure": history_budget_pressure,
            "history_budget_attention_files": history_budget_attention_files[:5],
            "history_budget_attention_file_count": len(history_budget_attention_files),
            "history_budget_projected_attention_files": history_budget_projected_attention_files[:5],
            "history_budget_projected_attention_file_count": len(history_budget_projected_attention_files),
            "history_budget_top": history_budget_top,
            "history_budget_top_name": history_budget_top.get("name"),
            "history_budget_top_status": history_budget_top.get("status"),
            "history_budget_top_line_ratio": history_budget_top.get("line_ratio"),
            "history_budget_top_byte_ratio": history_budget_top.get("byte_ratio"),
            "history_budget_top_line_margin": history_budget_top.get("line_margin"),
            "history_budget_top_byte_margin": history_budget_top.get("byte_margin"),
            "history_budget_projected_top": history_budget_projected_top,
            "history_budget_projected_top_name": history_budget_projected_top.get("name"),
            "history_budget_projected_top_status": history_budget_projected_top.get("projected_next_status"),
            "history_budget_projected_top_line_ratio": history_budget_projected_top.get(
                "projected_next_line_ratio"
            ),
            "history_budget_projected_top_byte_ratio": history_budget_projected_top.get(
                "projected_next_byte_ratio"
            ),
            "history_budget_projected_top_line_count": history_budget_projected_top.get(
                "projected_next_line_count"
            ),
            "history_budget_projected_top_bytes": history_budget_projected_top.get("projected_next_bytes"),
            "history_budget_projected_top_byte_margin": history_budget_projected_top.get(
                "projected_next_byte_margin"
            ),
            "removed_alert_reports": alert_reports["removed"],
            "removed_alert_report_count": alert_reports["removed_count"],
            "alert_report_kept_counts": alert_reports["kept_counts"],
            "alert_report_removed_counts": alert_reports["removed_counts"],
            "log_snapshot_dir": str(log_snapshot_dir),
            "log_snapshot_keep_count": log_snapshot_keep_count,
            "removed_log_snapshots": log_snapshots["removed"],
            "removed_log_snapshot_count": log_snapshots["removed_count"],
            "log_snapshot_counts": log_snapshots,
            "dashboard_history_maintenance": dashboard_history,
            "dashboard_history_compacted": bool(dashboard_history.get("compacted")),
            "dashboard_history_removed_rows": int(dashboard_history.get("removed_rows") or 0),
            "dashboard_history_before_rows": dashboard_history.get("before_rows"),
            "dashboard_history_after_rows": dashboard_history.get("after_rows"),
            "dashboard_history_reason": dashboard_history.get("reason"),
            "sqlite_maintenance": sqlite_maintenance,
            "sqlite_db_size_mb": sqlite_maintenance.get("size_mb"),
            "sqlite_db_reclaimable_mb": sqlite_maintenance.get("reclaimable_mb"),
            "sqlite_db_optimized": sqlite_maintenance.get("optimized"),
            "sqlite_db_vacuumed": sqlite_maintenance.get("vacuumed"),
            "local_cache_cleanup": local_cache_cleanup,
            "local_cache_cleanup_status": local_cache_cleanup.get("status"),
            "local_cache_cleanup_enabled": local_cache_cleanup.get("enabled"),
            "local_cache_cleanup_plan_state": local_cache_cleanup.get("plan_state"),
            "local_cache_cleanup_automation_ready": local_cache_cleanup.get("automation_ready"),
            "local_cache_cleanup_blocked_reason": local_cache_cleanup.get("blocked_reason")
            or local_cache_cleanup.get("reason"),
            "local_cache_cleanup_removed_count": local_cache_cleanup.get("removed_count"),
            "local_cache_cleanup_removed_bytes": local_cache_cleanup.get("removed_bytes"),
            "local_cache_cleanup_removed_mb": local_cache_cleanup.get("removed_mb"),
            "local_cache_cleanup_eligible_count": local_cache_cleanup.get("eligible_count"),
            "local_cache_cleanup_eligible_bytes": local_cache_cleanup.get("eligible_bytes"),
            "local_cache_cleanup_eligible_mb": local_cache_cleanup.get("eligible_mb"),
            "local_cache_cleanup_fresh_protected_count": local_cache_cleanup.get("fresh_protected_count"),
            "local_cache_cleanup_fresh_protected_bytes": local_cache_cleanup.get("fresh_protected_bytes"),
            "local_cache_cleanup_fresh_protected_mb": local_cache_cleanup.get("fresh_protected_mb"),
            "local_cache_cleanup_skipped_count": local_cache_cleanup.get("skipped_count"),
            "local_cache_cleanup_skipped_bytes": local_cache_cleanup.get("skipped_bytes"),
            "local_cache_cleanup_skipped_mb": local_cache_cleanup.get("skipped_mb"),
            "local_cache_cleanup_skipped_top_reason": local_cache_skip["reason"],
            "local_cache_cleanup_skipped_top_path": local_cache_skip["path"],
            "local_cache_cleanup_skipped_ratio": local_cache_cleanup.get("skipped_ratio"),
            "local_cache_cleanup_skip_state": local_cache_cleanup.get("skip_state"),
            "local_cache_cleanup_retry_recommended": local_cache_cleanup.get("retry_recommended"),
            "partial_video_artifact_cleanup": partial_video_cleanup,
            "partial_video_artifact_cleanup_status": partial_video_cleanup.get("status"),
            "partial_video_artifact_cleanup_enabled": partial_video_cleanup.get("enabled"),
            "partial_video_artifact_cleanup_path": partial_video_cleanup.get("path"),
            "partial_video_artifact_cleanup_removed_count": partial_video_cleanup.get("removed_count"),
            "partial_video_artifact_cleanup_reclaimed_bytes": partial_video_cleanup.get("reclaimed_bytes"),
            "partial_video_artifact_cleanup_reclaimed_mb": partial_video_cleanup.get("reclaimed_mb"),
            "partial_video_artifact_cleanup_skipped_count": partial_video_cleanup.get("skipped_count"),
            "partial_video_artifact_cleanup_error": partial_video_cleanup.get("error"),
            "runtime_footprint_before": footprint_before,
            "runtime_footprint_after": footprint_after,
            "runtime_footprint_reclaimed_bytes": max(
                0,
                int(footprint_before.get("total_bytes") or 0) - int(footprint_after.get("total_bytes") or 0),
            ),
            "max_log_bytes": max_log_bytes,
            "max_history_lines": max_history_lines,
            "max_history_bytes": max_history_bytes,
            "min_history_lines": min_history_lines,
            "dashboard_history_max_rows": dashboard_history_max_rows,
        }
    )
    result["hygiene_summary"] = maintenance_hygiene_summary(result)
    result["operation_summary"] = maintenance_operation_summary(result)
    result["status"] = result["operation_summary"].get("status")
    result["label"] = result["operation_summary"].get("label")
    result["tone"] = result["operation_summary"].get("tone")
    result["protected"] = result["operation_summary"].get("protected")
    result["maintenance_next_action"] = result["hygiene_summary"].get("next_action")
    result["external_archive_ready"] = result["hygiene_summary"].get("external_archive_ready")
    result.update(maintenance_top_level_aliases(result))
    return result


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def render_text_report(result: Mapping[str, Any]) -> str:
    lines = [
        f"Roxy output maintenance: {'DRY RUN' if result.get('dry_run') else 'DONE'}",
        f"Generated: {result.get('generated_at', '-')}",
        f"Output: {result.get('output_dir', '-')}",
        f"Removed: {result.get('removed_count', 0)}",
        f"Archived output: {result.get('output_archive_count', 0)}",
        f"Removed stale output: {result.get('stale_output_removed_count', 0)}",
        f"Trimmed logs: {result.get('trimmed_log_count', 0)}",
        f"Trimmed histories: {result.get('trimmed_history_count', 0)} | removed lines {result.get('trimmed_history_removed_lines', 0)} | removed bytes {result.get('trimmed_history_removed_bytes', 0)}",
        (
            "History min-lines relaxed: "
            f"{result.get('trimmed_history_min_lines_relaxed_count', 0)} | "
            f"files {', '.join(result.get('trimmed_history_min_lines_relaxed_files') or []) or '-'}"
        ),
        (
            "History budget: "
            f"{result.get('history_budget_status', '-')} | "
            f"pressure {result.get('history_budget_pressure', '-')} | "
            f"attention {result.get('history_budget_attention_file_count', 0)}"
        ),
        f"Removed alert reports: {result.get('removed_alert_report_count', 0)}",
        f"Removed log snapshots: {result.get('removed_log_snapshot_count', 0)}",
        f"Dashboard history: {result.get('dashboard_history_after_rows', 0)} rows | removed {result.get('dashboard_history_removed_rows', 0)}",
        f"SQLite DB: {result.get('sqlite_db_size_mb', 0)} MB | reclaimable {result.get('sqlite_db_reclaimable_mb', 0)} MB | vacuumed {bool(result.get('sqlite_db_vacuumed'))}",
        (
            "Local cache cleanup: "
            f"{result.get('local_cache_cleanup_status', '-')} | "
            f"plan {result.get('local_cache_cleanup_plan_state', '-')} | "
            f"eligible {result.get('local_cache_cleanup_eligible_count', 0)} | "
            f"fresh protected {result.get('local_cache_cleanup_fresh_protected_count', 0)} | "
            f"removed {result.get('local_cache_cleanup_removed_count', 0)} | "
            f"skipped {result.get('local_cache_cleanup_skipped_count', 0)} | "
            f"skip_state {result.get('local_cache_cleanup_skip_state', 'CLEAR')} | "
            f"retry {bool(result.get('local_cache_cleanup_retry_recommended'))}"
        ),
        (
            "Partial video artifacts: "
            f"{result.get('partial_video_artifact_cleanup_status', '-')} | "
            f"removed {result.get('partial_video_artifact_cleanup_removed_count', 0)} | "
            f"reclaimed {result.get('partial_video_artifact_cleanup_reclaimed_mb', 0)} MB"
        ),
        f"Prepared external dirs: {result.get('prepared_dir_count', 0)}",
        f"Runtime footprint: {dict(result.get('runtime_footprint_after') or {}).get('total_mb', 0)} MB",
        f"Reclaimed runtime bytes: {result.get('runtime_footprint_reclaimed_bytes', 0)}",
        "",
    ]
    hygiene = result.get("hygiene_summary") if isinstance(result.get("hygiene_summary"), Mapping) else {}
    if hygiene:
        lines.insert(2, f"Hygiene: {hygiene.get('label', '-')} | {hygiene.get('detail', '-')}")
        lines.insert(3, f"Next action: {hygiene.get('next_action', '-')}")
    operation = result.get("operation_summary") if isinstance(result.get("operation_summary"), Mapping) else {}
    if operation:
        lines.insert(4, f"Operation: {operation.get('label', '-')} | {operation.get('detail', '-')}")
    for pattern, count in dict(result.get("removed_counts") or {}).items():
        lines.append(f"- {pattern}: removed {count}, kept {dict(result.get('kept_counts') or {}).get(pattern, 0)}")
    for path in result.get("archived") or []:
        lines.append(f"- archived output: {path}")
    for path in result.get("stale_output_archived") or []:
        lines.append(f"- archived stale output: {path}")
    if result.get("output_archive_error_count"):
        lines.append(f"- output archive errors: {result.get('output_archive_error_count')}")
    prepared = result.get("prepared_dirs") if isinstance(result.get("prepared_dirs"), dict) else {}
    for path in prepared.get("created_dirs") or []:
        lines.append(f"- prepared dir: {path}")
    for key, error in dict(prepared.get("dir_errors") or {}).items():
        lines.append(f"- prepared dir error {key}: {error}")
    for pattern, count in dict(result.get("stale_output_removed_counts") or {}).items():
        if count:
            days = dict(result.get("stale_output_max_age_days_rules") or {}).get(pattern, "-")
            lines.append(f"- stale {pattern}: removed {count}, max age {days}d")
    for item in result.get("trimmed_logs") or []:
        lines.append(f"- log trimmed: {item.get('path')} {item.get('before_bytes')} -> {item.get('after_bytes')} bytes")
    for item in result.get("trimmed_histories") or []:
        lines.append(
            f"- history trimmed: {item.get('path')} "
            f"{item.get('before_lines')} -> {item.get('after_lines')} lines "
            f"(removed {item.get('removed_lines', 0)}, "
            f"bytes {item.get('before_bytes', 0)} -> {item.get('after_bytes', 0)})"
        )
    for pattern, count in dict(result.get("alert_report_removed_counts") or {}).items():
        lines.append(
            f"- alert report {pattern}: removed {count}, kept {dict(result.get('alert_report_kept_counts') or {}).get(pattern, 0)}"
        )
    for path in result.get("removed_log_snapshots") or []:
        lines.append(f"- log snapshot removed: {path}")
    dashboard_history = result.get("dashboard_history_maintenance") if isinstance(result.get("dashboard_history_maintenance"), dict) else {}
    if dashboard_history:
        lines.append(
            "- dashboard history: "
            f"{dashboard_history.get('reason')} | "
            f"{dashboard_history.get('before_rows', 0)} -> {dashboard_history.get('after_rows', 0)} rows"
        )
    sqlite_info = result.get("sqlite_maintenance") if isinstance(result.get("sqlite_maintenance"), dict) else {}
    if sqlite_info.get("status") == "ERROR":
        lines.append(f"- sqlite maintenance error: {sqlite_info.get('error')}")
    elif sqlite_info:
        lines.append(
            "- sqlite maintenance: "
            f"{sqlite_info.get('status')} | optimized {bool(sqlite_info.get('optimized'))} | "
            f"freelist {sqlite_info.get('freelist_count', 0)} pages | "
            f"reclaimable {sqlite_info.get('reclaimable_mb', 0)} MB"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    result: Mapping[str, Any],
    *,
    json_path: str | Path = DEFAULT_JSON_PATH,
    text_path: str | Path = DEFAULT_TEXT_PATH,
) -> tuple[Path, Path]:
    json_file = Path(json_path)
    text_file = Path(text_path)
    atomic_write_text(json.dumps(json_safe(dict(result)), indent=2, sort_keys=True), json_file)
    atomic_write_text(render_text_report(result), text_file)
    return json_file, text_file


def parse_rule(value: str) -> tuple[str, int]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("rules must use PATTERN=COUNT")
    pattern, count = value.split("=", 1)
    pattern = pattern.strip()
    if not pattern:
        raise argparse.ArgumentTypeError("pattern cannot be empty")
    try:
        keep_count = int(count)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("count must be an integer") from exc
    return pattern, keep_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean old generated Roxy output files by retention pattern.")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument(
        "--archive-dir",
        default=str(default_output_archive_dir() or ""),
        help="Move removed output files here before deleting from the active output directory.",
    )
    parser.add_argument(
        "--fallback-archive-dir",
        default=str(DEFAULT_LOCAL_OUTPUT_ARCHIVE_DIR),
        help="Verified local fallback when the requested archive is mounted but this process cannot write to it.",
    )
    parser.add_argument("--rule", action="append", type=parse_rule, help="Retention rule like 'ma_live_strategy_*.csv=96'. Can be repeated.")
    parser.add_argument(
        "--stale-output-rule",
        action="append",
        type=parse_rule,
        help="Stale output rule like 'fine_sweep_*=7'. Removes matching files older than N days.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-log-bytes", type=int, default=DEFAULT_MAX_LOG_BYTES)
    parser.add_argument("--max-history-lines", type=int, default=DEFAULT_MAX_HISTORY_LINES)
    parser.add_argument("--max-history-bytes", type=int, default=DEFAULT_MAX_HISTORY_BYTES)
    parser.add_argument("--min-history-lines", type=int, default=DEFAULT_MIN_HISTORY_LINES)
    parser.add_argument(
        "--alert-report-rule",
        action="append",
        type=parse_rule,
        help="Alert report retention rule like 'weekly_report_*.txt=12'. Can be repeated.",
    )
    parser.add_argument("--log-snapshot-dir", default=str(DEFAULT_LOG_SNAPSHOT_DIR))
    parser.add_argument("--log-snapshot-keep-count", type=int, default=DEFAULT_LOG_SNAPSHOT_KEEP_COUNT)
    parser.add_argument("--sqlite-db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--sqlite-vacuum-min-reclaim-mb", type=float, default=DEFAULT_SQLITE_VACUUM_MIN_RECLAIM_MB)
    parser.add_argument("--dashboard-history-path", default=str(DEFAULT_DASHBOARD_HISTORY_PATH))
    parser.add_argument("--dashboard-history-max-rows", type=int, default=DEFAULT_DASHBOARD_HISTORY_MAX_ROWS)
    parser.add_argument("--local-storage-pressure-report-path", default=str(DEFAULT_LOCAL_STORAGE_PRESSURE_REPORT_PATH))
    parser.add_argument("--enable-local-cache-cleanup", action="store_true")
    parser.add_argument("--local-cache-cleanup-min-age-days", type=float, default=DEFAULT_LOCAL_CACHE_CLEANUP_MIN_AGE_DAYS)
    parser.add_argument("--local-cache-cleanup-max-mb", type=float, default=DEFAULT_LOCAL_CACHE_CLEANUP_MAX_BYTES / (1024**2))
    parser.add_argument("--training-videos-path", default=str(DEFAULT_TRAINING_VIDEOS_PATH))
    parser.add_argument("--no-partial-video-artifact-cleanup", action="store_true")
    parser.add_argument("--json-path", default=str(DEFAULT_JSON_PATH))
    parser.add_argument("--text-path", default=str(DEFAULT_TEXT_PATH))
    parser.add_argument("--no-report", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rules = dict(args.rule or DEFAULT_RETENTION_RULES.items())
    stale_output_rules = {pattern: float(days) for pattern, days in (args.stale_output_rule or STALE_OUTPUT_MAX_AGE_DAYS_RULES.items())}
    alert_report_rules = dict(args.alert_report_rule or DEFAULT_ALERT_REPORT_RETENTION_RULES.items())
    result = cleanup_runtime_artifacts(
        output_dir=args.output_dir,
        retention_rules=rules,
        stale_output_rules=stale_output_rules,
        output_archive_dir=args.archive_dir or None,
        fallback_output_archive_dir=args.fallback_archive_dir or None,
        dry_run=args.dry_run,
        max_log_bytes=args.max_log_bytes,
        max_history_lines=args.max_history_lines,
        max_history_bytes=args.max_history_bytes,
        min_history_lines=args.min_history_lines,
        alert_report_retention_rules=alert_report_rules,
        log_snapshot_dir=args.log_snapshot_dir,
        log_snapshot_keep_count=args.log_snapshot_keep_count,
        sqlite_db_path=args.sqlite_db_path or None,
        sqlite_vacuum_min_reclaim_mb=args.sqlite_vacuum_min_reclaim_mb,
        dashboard_history_path=args.dashboard_history_path or None,
        dashboard_history_max_rows=args.dashboard_history_max_rows,
        local_storage_pressure_report_path=args.local_storage_pressure_report_path or None,
        enable_local_cache_cleanup=args.enable_local_cache_cleanup,
        local_cache_cleanup_min_age_days=args.local_cache_cleanup_min_age_days,
        local_cache_cleanup_max_bytes=int(max(0.0, args.local_cache_cleanup_max_mb) * 1024 * 1024),
        training_videos_path=args.training_videos_path,
        enable_partial_video_artifact_cleanup=not args.no_partial_video_artifact_cleanup,
    )
    if not args.no_report:
        json_path, text_path = write_report(result, json_path=args.json_path, text_path=args.text_path)
    else:
        json_path, text_path = None, None
    action = "Would remove" if args.dry_run else "Removed"
    print(f"{action} {result['removed_count']} old output file(s).")
    for pattern, count in result["removed_counts"].items():
        if count:
            print(f"- {pattern}: {count}")
    if result.get("trimmed_log_count"):
        print(f"Trimmed logs: {result['trimmed_log_count']}")
    if result.get("stale_output_removed_count"):
        print(f"Removed stale output: {result['stale_output_removed_count']}")
    if result.get("output_archive_count"):
        print(f"Archived output: {result['output_archive_count']}")
    if result.get("trimmed_history_count"):
        print(f"Trimmed histories: {result['trimmed_history_count']}")
    if result.get("removed_alert_report_count"):
        print(f"Removed alert reports: {result['removed_alert_report_count']}")
    if result.get("removed_log_snapshot_count"):
        print(f"Removed log snapshots: {result['removed_log_snapshot_count']}")
    if result.get("dashboard_history_removed_rows"):
        print(f"Compacted dashboard history: {result['dashboard_history_removed_rows']} row(s)")
    if result.get("sqlite_maintenance"):
        print(
            "SQLite DB: "
            f"{result.get('sqlite_db_size_mb')} MB, reclaimable {result.get('sqlite_db_reclaimable_mb')} MB"
        )
    if result.get("local_cache_cleanup_status"):
        print(
            "Local cache cleanup: "
            f"{result.get('local_cache_cleanup_status')} "
            f"plan={result.get('local_cache_cleanup_plan_state')} "
            f"removed={result.get('local_cache_cleanup_removed_count')}"
        )
    if json_path and text_path:
        print(f"JSON: {json_path}")
        print(f"Text: {text_path}")


if __name__ == "__main__":
    main()
