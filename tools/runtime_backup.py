from __future__ import annotations

import argparse
import json
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TARGET_DIR = Path("/Volumes/RoxyData/projects/roxy_trading/_backup/runtime")
DEFAULT_REPORT_PATH = BASE_DIR / "alerts" / "runtime_backup.json"
DEFAULT_TEXT_PATH = BASE_DIR / "alerts" / "runtime_backup.txt"
DEFAULT_INCLUDE_PATHS = ("alerts", "db", "data")
DEFAULT_RETENTION_COUNT = 7
DEFAULT_REQUIRED_ALERT_MEMBERS = ("alerts/roxy_realtime_check.json", "alerts/runtime_backup.json")
DEFAULT_REQUIRED_DB_MEMBERS = ("db/scan_history.csv",)
DEFAULT_REQUIRED_DB_EXTENSIONS = (".db", ".sqlite", ".sqlite3")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def backup_filename(now: datetime | None = None) -> str:
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return f"roxy_runtime_{current.strftime('%Y%m%d_%H%M%S')}.tar.gz"


def archive_candidates(base_dir: Path, include_paths: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for value in include_paths:
        path = base_dir / value
        if path.exists():
            paths.append(path)
    return paths


def critical_archive_members(expected_paths: tuple[str, ...] | list[str]) -> tuple[list[str], bool]:
    expected = {str(value).strip().strip("/") for value in expected_paths if str(value).strip()}
    members: list[str] = []
    if "alerts" in expected:
        members.extend(DEFAULT_REQUIRED_ALERT_MEMBERS)
    if "db" in expected:
        members.extend(DEFAULT_REQUIRED_DB_MEMBERS)
    return members, "db" in expected


def ensure_preflight_report_member(*, root: Path, report_file: Path, include_paths: tuple[str, ...], now: datetime) -> None:
    if "alerts" not in {str(value).strip().strip("/") for value in include_paths}:
        return
    try:
        relative_report = report_file.resolve().relative_to(root.resolve())
    except ValueError:
        return
    if str(relative_report).strip("/") != "alerts/runtime_backup.json":
        return
    if report_file.exists():
        return
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "status": "BOOTSTRAP",
                "detail": "preflight marker for runtime backup archive membership",
            },
            indent=2,
            sort_keys=True,
        )
    )


def verify_archive_contents(archive_path: str | Path, expected_paths: tuple[str, ...] | list[str]) -> dict[str, Any]:
    path = Path(archive_path)
    expected = [str(value).strip().strip("/") for value in expected_paths if str(value).strip()]
    required_members, requires_db_member = critical_archive_members(expected)
    result: dict[str, Any] = {
        "archive_readable": False,
        "archive_verified": False,
        "archive_member_count": 0,
        "archive_verified_paths": [],
        "archive_missing_verified_paths": expected,
        "archive_verified_members": [],
        "archive_missing_critical_members": [
            *required_members,
            *(["db/*.db"] if requires_db_member else []),
        ],
        "archive_database_member_verified": not requires_db_member,
        "archive_verification_error": "",
    }
    if not path.exists():
        result["archive_verification_error"] = "archive missing"
        return result
    try:
        with tarfile.open(path, "r:gz") as archive:
            names = archive.getnames()
    except Exception as exc:
        result["archive_verification_error"] = f"{type(exc).__name__}: {exc}"
        return result

    verified: list[str] = []
    missing: list[str] = []
    normalized_names = {str(name).strip().strip("/") for name in names if str(name).strip()}
    for expected_path in expected:
        if any(name == expected_path or name.startswith(f"{expected_path}/") for name in normalized_names):
            verified.append(expected_path)
        else:
            missing.append(expected_path)
    verified_members = [member for member in required_members if member in normalized_names]
    missing_critical_members = [member for member in required_members if member not in set(verified_members)]
    database_member_verified = (
        not requires_db_member
        or any(
            name.startswith("db/")
            and Path(name).suffix.lower() in DEFAULT_REQUIRED_DB_EXTENSIONS
            for name in normalized_names
        )
    )
    if requires_db_member and not database_member_verified:
        missing_critical_members.append("db/*.db")
    result.update(
        {
            "archive_readable": True,
            "archive_verified": not missing and not missing_critical_members and database_member_verified,
            "archive_member_count": len(names),
            "archive_verified_paths": verified,
            "archive_missing_verified_paths": missing,
            "archive_verified_members": verified_members,
            "archive_missing_critical_members": missing_critical_members,
            "archive_database_member_verified": database_member_verified,
        }
    )
    return result


def prune_backups(target_dir: Path, *, retention_count: int, dry_run: bool = False) -> list[str]:
    retention_count = max(1, int(retention_count))
    archives = sorted(target_dir.glob("roxy_runtime_*.tar.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    stale = archives[retention_count:]
    removed: list[str] = []
    for path in stale:
        removed.append(str(path))
        if not dry_run:
            path.unlink()
    return removed


def create_runtime_backup(
    *,
    base_dir: str | Path = BASE_DIR,
    target_dir: str | Path = DEFAULT_TARGET_DIR,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    text_path: str | Path = DEFAULT_TEXT_PATH,
    include_paths: tuple[str, ...] = DEFAULT_INCLUDE_PATHS,
    retention_count: int = DEFAULT_RETENTION_COUNT,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(base_dir)
    target = Path(target_dir)
    report_file = Path(report_path)
    text_file = Path(text_path)
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if not dry_run:
        ensure_preflight_report_member(root=root, report_file=report_file, include_paths=include_paths, now=current)
    candidates = archive_candidates(root, include_paths)
    target.mkdir(parents=True, exist_ok=True)
    archive_path = target / backup_filename(current)
    temp_archive_path = target / f".{archive_path.name}.{os.getpid()}.tmp"
    missing = [value for value in include_paths if not (root / value).exists()]
    included = [str(path.relative_to(root)) for path in candidates]

    if not dry_run:
        try:
            with tarfile.open(temp_archive_path, "w:gz") as archive:
                for path in candidates:
                    archive.add(path, arcname=path.relative_to(root))
            temp_archive_path.replace(archive_path)
        except Exception:
            temp_archive_path.unlink(missing_ok=True)
            raise
    verification = (
        {
            "archive_readable": False,
            "archive_verified": False,
            "archive_member_count": 0,
            "archive_verified_paths": [],
            "archive_missing_verified_paths": included,
            "archive_verified_members": [],
            "archive_missing_critical_members": [],
            "archive_database_member_verified": "db" not in set(included),
            "archive_verification_error": "dry run",
        }
        if dry_run
        else verify_archive_contents(archive_path, included)
    )
    removed = prune_backups(target, retention_count=retention_count, dry_run=dry_run)
    archive_size = archive_path.stat().st_size if archive_path.exists() else 0
    result = {
        "generated_at": current.isoformat(),
        "status": "DRY_RUN" if dry_run else "OK",
        "base_dir": str(root),
        "target_dir": str(target),
        "archive_path": str(archive_path),
        "archive_exists": archive_path.exists(),
        "archive_size_bytes": archive_size,
        "include_paths": included,
        "missing_paths": missing,
        "retention_count": retention_count,
        "removed": removed,
        "removed_count": len(removed),
        "dry_run": dry_run,
        **verification,
    }
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(json_safe(result), indent=2, sort_keys=True))
    text_file.parent.mkdir(parents=True, exist_ok=True)
    text_file.write_text(render_text_report(result))
    return result


def render_text_report(result: dict[str, Any]) -> str:
    lines = [
        f"Roxy runtime backup: {result.get('status', '-')}",
        f"Generated: {result.get('generated_at', '-')}",
        f"Archive: {result.get('archive_path', '-')}",
        f"Size: {int(result.get('archive_size_bytes', 0) or 0)} bytes",
        "Included: " + ", ".join(result.get("include_paths") or []),
        f"Verified: {result.get('archive_verified', False)}",
        f"Members: {int(result.get('archive_member_count', 0) or 0)}",
        f"Removed old: {result.get('removed_count', 0)}",
    ]
    if result.get("missing_paths"):
        lines.append("Missing: " + ", ".join(result.get("missing_paths") or []))
    if result.get("archive_missing_verified_paths"):
        lines.append("Archive missing: " + ", ".join(result.get("archive_missing_verified_paths") or []))
    if result.get("archive_verified_members") or result.get("archive_missing_critical_members"):
        verified_members = result.get("archive_verified_members") or []
        missing_members = result.get("archive_missing_critical_members") or []
        lines.append(f"Critical verified: {len(verified_members)}/{len(verified_members) + len(missing_members)}")
    if result.get("archive_missing_critical_members"):
        lines.append("Critical missing: " + ", ".join(result.get("archive_missing_critical_members") or []))
    if result.get("archive_verification_error") and not result.get("dry_run"):
        lines.append(f"Archive verification error: {result.get('archive_verification_error')}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Back up Roxy runtime artifacts to the external RoxyData disk.")
    parser.add_argument("--base-dir", default=str(BASE_DIR))
    parser.add_argument("--target-dir", default=str(DEFAULT_TARGET_DIR))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--text-path", default=str(DEFAULT_TEXT_PATH))
    parser.add_argument("--include", default=",".join(DEFAULT_INCLUDE_PATHS))
    parser.add_argument("--retention-count", type=int, default=DEFAULT_RETENTION_COUNT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_paths = tuple(item.strip() for item in args.include.split(",") if item.strip())
    result = create_runtime_backup(
        base_dir=args.base_dir,
        target_dir=args.target_dir,
        report_path=args.report_path,
        text_path=args.text_path,
        include_paths=include_paths,
        retention_count=args.retention_count,
        dry_run=args.dry_run,
    )
    print(render_text_report(result), end="")


if __name__ == "__main__":
    main()
