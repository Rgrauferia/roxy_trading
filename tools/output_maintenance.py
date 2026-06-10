from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from typing import Mapping


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from roxy_paths import alerts_dir, output_dir

OUTPUT_DIR = output_dir()
ALERTS_DIR = alerts_dir()
LOG_DIR = BASE_DIR / "logs"
LAUNCHD_LOG_DIR = Path.home() / "Library" / "Logs" / "RoxyTrading"
DEFAULT_EXTERNAL_DISK_PATH = Path("/Volumes/RoxyData")
DEFAULT_LOG_SNAPSHOT_DIR = Path("/Volumes/RoxyData/MacArchive/log_snapshots")
DEFAULT_OUTPUT_ARCHIVE_DIR = DEFAULT_EXTERNAL_DISK_PATH / "MacArchive" / "roxy_trading" / "output_archive"
DEFAULT_JSON_PATH = ALERTS_DIR / "output_maintenance.json"
DEFAULT_TEXT_PATH = ALERTS_DIR / "output_maintenance.txt"

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
DEFAULT_LOG_SNAPSHOT_KEEP_COUNT = 20


def files_for_pattern(output_dir: Path, pattern: str) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted(
        [path for path in output_dir.glob(pattern) if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def default_output_archive_dir() -> Path | None:
    if DEFAULT_EXTERNAL_DISK_PATH.exists() and DEFAULT_EXTERNAL_DISK_PATH.is_dir():
        return DEFAULT_OUTPUT_ARCHIVE_DIR
    return None


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


def trim_history_file(path: Path, *, max_lines: int, dry_run: bool = False) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    lines = path.read_text(errors="replace").splitlines()
    max_lines = max(1, int(max_lines))
    if len(lines) <= max_lines:
        return None
    kept = lines[-max_lines:]
    if not dry_run:
        path.write_text("\n".join(kept) + "\n")
    return {
        "path": str(path),
        "before_lines": len(lines),
        "after_lines": len(kept),
    }


def trim_history_files(
    *,
    alerts_path: str | Path = ALERTS_DIR,
    history_files: tuple[str, ...] = DEFAULT_HISTORY_FILES,
    max_lines: int = DEFAULT_MAX_HISTORY_LINES,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    root = Path(alerts_path)
    trimmed: list[dict[str, Any]] = []
    for name in history_files:
        result = trim_history_file(root / name, max_lines=max_lines, dry_run=dry_run)
        if result:
            trimmed.append(result)
    return trimmed


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
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(snapshot_dir)
    removed: list[str] = []
    kept_counts: dict[str, int] = {}
    removed_counts: dict[str, int] = {}
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
    for pattern in patterns:
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
        "snapshot_dir": str(root),
        "removed": removed,
        "removed_count": len(removed),
        "kept_counts": kept_counts,
        "removed_counts": removed_counts,
        "exists": True,
    }


def cleanup_runtime_artifacts(
    *,
    output_dir: str | Path = OUTPUT_DIR,
    alerts_path: str | Path = ALERTS_DIR,
    log_dirs: list[str | Path] | None = None,
    retention_rules: Mapping[str, int] | None = None,
    stale_output_rules: Mapping[str, float] | None = None,
    output_archive_dir: str | Path | None = None,
    dry_run: bool = False,
    max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
    max_history_lines: int = DEFAULT_MAX_HISTORY_LINES,
    alert_report_retention_rules: Mapping[str, int] | None = None,
    log_snapshot_dir: str | Path = DEFAULT_LOG_SNAPSHOT_DIR,
    log_snapshot_keep_count: int = DEFAULT_LOG_SNAPSHOT_KEEP_COUNT,
) -> dict[str, Any]:
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
    trimmed_histories = trim_history_files(alerts_path=alerts_path, max_lines=max_history_lines, dry_run=dry_run)
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
            "removed_alert_reports": alert_reports["removed"],
            "removed_alert_report_count": alert_reports["removed_count"],
            "alert_report_kept_counts": alert_reports["kept_counts"],
            "alert_report_removed_counts": alert_reports["removed_counts"],
            "log_snapshot_dir": str(log_snapshot_dir),
            "log_snapshot_keep_count": log_snapshot_keep_count,
            "removed_log_snapshots": log_snapshots["removed"],
            "removed_log_snapshot_count": log_snapshots["removed_count"],
            "log_snapshot_counts": log_snapshots,
            "max_log_bytes": max_log_bytes,
            "max_history_lines": max_history_lines,
        }
    )
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
        f"Trimmed histories: {result.get('trimmed_history_count', 0)}",
        f"Removed alert reports: {result.get('removed_alert_report_count', 0)}",
        f"Removed log snapshots: {result.get('removed_log_snapshot_count', 0)}",
        f"Prepared external dirs: {result.get('prepared_dir_count', 0)}",
        "",
    ]
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
        lines.append(f"- history trimmed: {item.get('path')} {item.get('before_lines')} -> {item.get('after_lines')} lines")
    for pattern, count in dict(result.get("alert_report_removed_counts") or {}).items():
        lines.append(
            f"- alert report {pattern}: removed {count}, kept {dict(result.get('alert_report_kept_counts') or {}).get(pattern, 0)}"
        )
    for path in result.get("removed_log_snapshots") or []:
        lines.append(f"- log snapshot removed: {path}")
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    result: Mapping[str, Any],
    *,
    json_path: str | Path = DEFAULT_JSON_PATH,
    text_path: str | Path = DEFAULT_TEXT_PATH,
) -> tuple[Path, Path]:
    json_file = Path(json_path)
    text_file = Path(text_path)
    json_file.parent.mkdir(parents=True, exist_ok=True)
    text_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(json.dumps(json_safe(dict(result)), indent=2, sort_keys=True))
    text_file.write_text(render_text_report(result))
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
    parser.add_argument(
        "--alert-report-rule",
        action="append",
        type=parse_rule,
        help="Alert report retention rule like 'weekly_report_*.txt=12'. Can be repeated.",
    )
    parser.add_argument("--log-snapshot-dir", default=str(DEFAULT_LOG_SNAPSHOT_DIR))
    parser.add_argument("--log-snapshot-keep-count", type=int, default=DEFAULT_LOG_SNAPSHOT_KEEP_COUNT)
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
        dry_run=args.dry_run,
        max_log_bytes=args.max_log_bytes,
        max_history_lines=args.max_history_lines,
        alert_report_retention_rules=alert_report_rules,
        log_snapshot_dir=args.log_snapshot_dir,
        log_snapshot_keep_count=args.log_snapshot_keep_count,
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
    if json_path and text_path:
        print(f"JSON: {json_path}")
        print(f"Text: {text_path}")


if __name__ == "__main__":
    main()
