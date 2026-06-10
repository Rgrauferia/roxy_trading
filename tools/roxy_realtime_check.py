from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from roxy_paths import alerts_dir as configured_alerts_dir
from roxy_paths import output_dir as configured_output_dir

OUTPUT_DIR = configured_output_dir()
ALERTS_DIR = configured_alerts_dir()
DEFAULT_JSON_PATH = ALERTS_DIR / "roxy_realtime_check.json"
DEFAULT_TEXT_PATH = ALERTS_DIR / "roxy_realtime_check.txt"
DEFAULT_HEALTH_NOTIFY_STATE_PATH = ALERTS_DIR / "roxy_health_notify_state.json"
DEFAULT_HEALTH_HISTORY_PATH = ALERTS_DIR / "roxy_realtime_history.jsonl"
DEFAULT_HEALTH_HISTORY_MAX_ENTRIES = 500
DEFAULT_LOCK_PATH = ALERTS_DIR / "roxy_realtime_check.lock"
DEFAULT_LOCK_STATUS_PATH = ALERTS_DIR / "roxy_realtime_lock.json"
DEFAULT_EXTERNAL_DISK_PATH = Path("/Volumes/RoxyData")
DEFAULT_RUNTIME_BACKUP_MAX_AGE_HOURS = 30.0
DEFAULT_RUNTIME_BACKUP_DAEMON_HEARTBEAT_PATH = ALERTS_DIR / "runtime_backup_daemon_heartbeat.json"
DEFAULT_RUNTIME_BACKUP_REQUIRED_PATHS = ("alerts", "db", "data")
DEFAULT_ALERT_QUALITY_MAX_AGE_MINUTES = 30.0
DEFAULT_OPERATIONAL_LOG_MAX_AGE_MINUTES = 90.0
DEFAULT_OPERATIONAL_LOG_TAIL_BYTES = 80_000
DEFAULT_LIVE_DATA_RECOVERY_TIMEOUT_SECONDS = 900
DEFAULT_PARALLELS_SOURCE_PATH = Path.home() / "Parallels"
DEFAULT_PARALLELS_DESTINATION_PATH = DEFAULT_EXTERNAL_DISK_PATH / "MacArchive" / Path.home().name / "Parallels"
DEFAULT_PARALLELS_MIGRATION_LOG_PATH = DEFAULT_EXTERNAL_DISK_PATH / "MacArchive" / "migration_logs" / "parallels_migration.log"
DEFAULT_RUNTIME_CACHE_SOURCE_PATH = Path.home() / ".cache" / "codex-runtimes"
DEFAULT_RUNTIME_CACHE_DESTINATION_PATH = (
    DEFAULT_EXTERNAL_DISK_PATH / "MacArchive" / Path.home().name / ".cache" / "codex-runtimes"
)
DEFAULT_LOCAL_TRAINING_MEDIA_RELATIVE_PATH = "training_videos"
DEFAULT_TRAINING_MEDIA_WARN_GB = 5.0
DEFAULT_TRAINING_MEDIA_FAIL_GB = 20.0
DEFAULT_PROJECT_STORAGE_WARN_GB = 5.0
DEFAULT_PROJECT_STORAGE_FAIL_GB = 20.0
REQUIRED_CONFLUENCE_COLUMNS = {
    "market",
    "symbol",
    "signal",
    "trade_decision",
    "confluence_score",
    "higher_tf_bias",
    "htf_2h_signal",
    "htf_4h_signal",
}

BENIGN_OPERATIONAL_LOG_PATTERNS = (
    "NotOpenSSLWarning: urllib3 v2 only supports OpenSSL",
    "warnings.warn(",
    "Please replace `use_container_width` with `width`.",
    "`use_container_width` will be removed after 2025-12-31.",
    "For `use_container_width=True`, use `width='stretch'`.",
    "Failed to get ticker 'MATIC/USD' reason:",
    "HTTP Error 500: <!DOCTYPE html>",
    "HTTP Error 502: <!DOCTYPE html>",
    "YFException(\"Failed to parse json response from Yahoo Finance:",
    "YAHOO! FINANCE IS CURRENTLY DOWN!",
)
CRITICAL_OPERATIONAL_LOG_PATTERNS = (
    r"\bTraceback \(most recent call last\):",
    r"\bTypeError\b",
    r"\bPermissionError\b",
    r"\bOperation not permitted\b",
    r"\bcan't open file\b",
    r"\bModuleNotFoundError\b",
    r"\bImportError\b",
    r"\bFileNotFoundError\b",
    r"\blaunchctl .*failed\b",
)
WARNING_OPERATIONAL_LOG_PATTERNS = (
    r"\bERROR\b",
    r"\bException\b",
    r"\bFailed download\b",
    r"\bTimeout\(",
)
YFINANCE_CACHE_ERROR_PATTERN = re.compile(
    r"OperationalError\([^)]*unable to open database file",
    flags=re.IGNORECASE,
)
YFINANCE_CACHE_PATHS = (
    Path.home() / ".cache" / "py-yfinance",
    Path.home() / "Library" / "Caches" / "py-yfinance",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def latest_file(pattern: str, *, base_dir: Path = BASE_DIR) -> Path | None:
    matches = sorted(
        [path for path in base_dir.glob(pattern) if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def runtime_dirs(base_dir: Path) -> tuple[Path, Path]:
    try:
        is_project_base = base_dir.resolve() == BASE_DIR.resolve()
    except Exception:
        is_project_base = base_dir == BASE_DIR
    if is_project_base:
        return OUTPUT_DIR, ALERTS_DIR
    return base_dir / "output", base_dir / "alerts"


def latest_output_file(pattern: str, *, output_path: Path) -> Path | None:
    matches = sorted(
        [path for path in output_path.glob(pattern) if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def file_age_minutes(path: Path, *, now: datetime | None = None) -> float:
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return max(0.0, (current - modified).total_seconds() / 60.0)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def read_csv(path: Path | None) -> pd.DataFrame:
    if not path or not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def heartbeat_artifact_path(heartbeat: dict[str, Any], key: str) -> Path | None:
    value = heartbeat.get(key)
    if not value:
        return None
    path = Path(str(value))
    return path if path.exists() else None


def check(name: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, **extra}


def overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status")) for item in checks}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "OK"


def pid_is_running(pid: Any) -> bool:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
    except OSError:
        return False
    return True


def freshness_check(name: str, path: Path | None, *, max_age_minutes: float, now: datetime | None = None) -> dict[str, Any]:
    if path is None:
        return check(name, "FAIL", "File not found")
    age = file_age_minutes(path, now=now)
    if age <= max_age_minutes:
        status = "OK"
    elif age <= max_age_minutes * 3:
        status = "WARN"
    else:
        status = "FAIL"
    return check(name, status, f"{path} age {age:.0f} min", path=str(path), age_minutes=age)


def heartbeat_check(
    heartbeat_path: Path,
    heartbeat: dict[str, Any],
    *,
    now: datetime | None = None,
    running_warn_minutes: float = 15.0,
    running_fail_minutes: float = 30.0,
) -> tuple[dict[str, Any], str]:
    if not heartbeat:
        return check("heartbeat", "WARN", "Heartbeat not found", path=str(heartbeat_path)), ""

    hb_status = str(heartbeat.get("status") or "").upper()
    if hb_status == "SUCCESS":
        return (
            check(
                "heartbeat",
                "OK",
                f"Last live run succeeded in {heartbeat.get('duration_seconds', '-')}s",
                path=str(heartbeat_path),
            ),
            hb_status,
        )
    if hb_status == "RUNNING":
        current = now or utc_now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        started_at = parse_utc_datetime(heartbeat.get("started_at"))
        if started_at is None:
            return check("heartbeat", "WARN", "Live backend is running; started_at missing", path=str(heartbeat_path)), hb_status
        running_minutes = max(0.0, (current - started_at).total_seconds() / 60.0)
        if running_minutes >= running_fail_minutes:
            status = "FAIL"
            detail = f"Live backend running for {running_minutes:.0f} min; likely stuck"
        elif running_minutes >= running_warn_minutes:
            status = "WARN"
            detail = f"Live backend running for {running_minutes:.0f} min"
        else:
            status = "OK"
            detail = f"Live backend running normally for {running_minutes:.0f} min"
        return (
            check(
                "heartbeat",
                status,
                detail,
                path=str(heartbeat_path),
                running_minutes=running_minutes,
                running_warn_minutes=running_warn_minutes,
                running_fail_minutes=running_fail_minutes,
            ),
            hb_status,
        )

    return (
        check(
            "heartbeat",
            "FAIL",
            str(heartbeat.get("error") or hb_status or "Live backend failed"),
            path=str(heartbeat_path),
        ),
        hb_status,
    )


def normalize_tf(value: Any) -> str:
    return str(value or "").strip().lower()


def validate_app_url(
    url: str,
    *,
    timeout: float = 5.0,
    log_paths: list[Path] | None = None,
    max_log_age_minutes: float = DEFAULT_OPERATIONAL_LOG_MAX_AGE_MINUTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not url:
        return check("streamlit_app", "WARN", "App URL not provided")
    try:
        req = Request(url, method="HEAD")
        with urlopen(req, timeout=timeout) as response:
            status_code = int(getattr(response, "status", 0) or 0)
    except Exception:
        try:
            with urlopen(url, timeout=timeout) as response:
                status_code = int(getattr(response, "status", 0) or 0)
        except URLError as exc:
            return check("streamlit_app", "FAIL", f"App not reachable: {exc}", url=url)
        except Exception as exc:
            return check("streamlit_app", "FAIL", f"App check failed: {exc}", url=url)
    status = "OK" if 200 <= status_code < 400 else "FAIL"
    if status != "OK":
        return check("streamlit_app", status, f"HTTP {status_code}", url=url, status_code=status_code)

    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    recent_critical: list[dict[str, Any]] = []
    recent_logs = 0
    for path in log_paths if log_paths is not None else default_streamlit_log_paths():
        if not path.exists():
            continue
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except OSError:
            continue
        age_minutes = max(0.0, (current - modified).total_seconds() / 60.0)
        if age_minutes > max_log_age_minutes:
            continue
        recent_logs += 1
        critical, _, _ = operational_log_signals(read_log_tail(path))
        for line in critical:
            recent_critical.append({"path": str(path), "line": line, "age_minutes": age_minutes})
    if recent_critical:
        first = recent_critical[0]
        return check(
            "streamlit_app",
            "FAIL",
            f"HTTP {status_code}, recent Streamlit log critical: {first['line']}",
            url=url,
            status_code=status_code,
            recent_log_count=recent_logs,
            recent_critical=recent_critical[:10],
        )

    return check("streamlit_app", status, f"HTTP {status_code}", url=url, status_code=status_code, recent_log_count=recent_logs)


def validate_chart(symbol: str, market: str, timeframe: str) -> dict[str, Any]:
    if not symbol:
        return check("chart_indicators", "WARN", "No symbol available for chart check")
    try:
        from symbol_detail import fetch_symbol_history, prepare_symbol_chart_data

        history = fetch_symbol_history(symbol, market=market, timeframe=timeframe)
        chart_df = prepare_symbol_chart_data(history)
    except Exception as exc:
        return check("chart_indicators", "FAIL", f"Chart data failed for {symbol}: {exc}", symbol=symbol)
    if chart_df.empty:
        return check("chart_indicators", "FAIL", f"No chart rows for {symbol}", symbol=symbol)
    has_rsi = "rsi14" in chart_df.columns and chart_df["rsi14"].notna().any()
    has_macd = "macd_hist" in chart_df.columns and chart_df["macd_hist"].notna().any()
    status = "OK" if len(chart_df) >= 40 and has_rsi and has_macd else "FAIL"
    detail = f"{symbol} {timeframe}: rows={len(chart_df)}, RSI={has_rsi}, MACD={has_macd}"
    return check(
        "chart_indicators",
        status,
        detail,
        symbol=symbol,
        market=market,
        timeframe=timeframe,
        rows=len(chart_df),
        has_rsi=has_rsi,
        has_macd=has_macd,
    )


def choose_chart_symbol(scan_df: pd.DataFrame, explicit_symbol: str | None) -> tuple[str, str]:
    if explicit_symbol:
        return explicit_symbol.upper(), "stock"
    if scan_df.empty or "symbol" not in scan_df.columns:
        return "", "stock"
    row = scan_df.iloc[0].to_dict()
    return str(row.get("symbol") or "").upper(), str(row.get("market") or "stock").lower()


def sample_salto_chart() -> pd.DataFrame:
    rows = []
    for idx in range(240):
        close = 50.0 + idx * 0.22
        rows.append(
            {
                "ts": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=idx),
                "open": close - 0.05,
                "high": close + 0.15,
                "low": close - 0.20,
                "close": close,
                "volume": 1_000_000 + idx * 1_000,
            }
        )
    try:
        from symbol_detail import prepare_symbol_chart_data

        return prepare_symbol_chart_data(pd.DataFrame(rows))
    except Exception:
        return pd.DataFrame(rows)


def validate_salto_integration() -> dict[str, Any]:
    try:
        from roxy_ai import build_strategy_lab
        from salto_strategies import SALTO_STRATEGIES, SALTO_STRATEGY_FAMILIES, detect_salto_setups
        from trade_brief import CORE_STRATEGIES, strategy_family_from_setup

        families = set(SALTO_STRATEGY_FAMILIES)
        core_missing = sorted(families - set(CORE_STRATEGIES))
        lab_rows = build_strategy_lab({"strategy_stats": {}, "signal_journal": []})
        lab_families = {str(row.get("strategy_family")) for row in lab_rows}
        lab_missing = sorted(families - lab_families)
        key_mapping_ok = all(strategy_family_from_setup(item.key) == item.family for item in SALTO_STRATEGIES)
        detected = detect_salto_setups(sample_salto_chart(), {"setup": "TREND_CONTINUATION", "signal": "WATCH"})
        active_or_watch = [row for row in detected if row.get("status") in {"ACTIVE", "WATCH"}]
        issues = []
        if len(SALTO_STRATEGIES) < 5:
            issues.append("expected at least 5 salto definitions")
        if core_missing:
            issues.append(f"missing in CORE_STRATEGIES: {', '.join(core_missing)}")
        if lab_missing:
            issues.append(f"missing in strategy lab: {', '.join(lab_missing)}")
        if not key_mapping_ok:
            issues.append("strategy_family_from_setup does not map every salto key")
        if not active_or_watch:
            issues.append("synthetic chart did not produce active/watch salto setup")
        status = "OK" if not issues else "FAIL"
        detail = (
            f"{len(SALTO_STRATEGIES)} definitions, {len(active_or_watch)} synthetic active/watch"
            if not issues
            else "; ".join(issues)
        )
        return check(
            "salto_integration",
            status,
            detail,
            definitions=len(SALTO_STRATEGIES),
            active_or_watch=len(active_or_watch),
            core_missing=core_missing,
            lab_missing=lab_missing,
        )
    except Exception as exc:
        return check("salto_integration", "FAIL", f"Salto integration check failed: {exc}")


def command_has_timeframes(command: str, option: str, required_timeframes: set[str]) -> bool:
    marker = f"{option} "
    if marker not in command:
        return False
    value = command.split(marker, 1)[1].split(" ", 1)[0]
    present = {item.strip().lower() for item in value.split(",") if item.strip()}
    return required_timeframes.issubset(present)


def command_option_int(command: str, option: str) -> int | None:
    marker = f"{option} "
    if marker not in command:
        return None
    value = command.split(marker, 1)[1].split(" ", 1)[0]
    try:
        return int(value)
    except ValueError:
        return None


def command_has_flag(command: str, flag: str) -> bool:
    return flag in str(command or "").split()


def validate_disk_space(base_dir: Path, *, warn_free_gb: float, fail_free_gb: float) -> dict[str, Any]:
    usage = shutil.disk_usage(base_dir)
    free_gb = usage.free / (1024**3)
    total_gb = usage.total / (1024**3)
    free_pct = (usage.free / usage.total * 100.0) if usage.total else 0.0
    if free_gb < fail_free_gb:
        status = "FAIL"
    elif free_gb < warn_free_gb:
        status = "WARN"
    else:
        status = "OK"
    return check(
        "disk_space",
        status,
        f"{free_gb:.2f} GiB free ({free_pct:.1f}% of {total_gb:.0f} GiB)",
        free_gb=free_gb,
        free_pct=free_pct,
        warn_free_gb=warn_free_gb,
        fail_free_gb=fail_free_gb,
    )


def validate_external_disk(
    disk_path: str | Path,
    *,
    warn_free_gb: float = 100.0,
    fail_free_gb: float = 20.0,
    operational_report_path: str | Path | None = None,
    operational_max_age_hours: float = DEFAULT_RUNTIME_BACKUP_MAX_AGE_HOURS,
    now: datetime | None = None,
) -> dict[str, Any]:
    path = Path(disk_path)
    if not path.exists() or not path.is_dir():
        return check("external_disk", "FAIL", f"{path} is not mounted", path=str(path), mounted=False, writable=False)
    try:
        usage = shutil.disk_usage(path)
    except Exception as exc:
        return check("external_disk", "FAIL", f"Cannot read {path}: {exc}", path=str(path), mounted=True, writable=False)

    test_file = path / f".roxy_write_test_{os.getpid()}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    writable = False
    try:
        test_file.write_text("ok")
        writable = test_file.read_text() == "ok"
    except Exception:
        writable = False
    finally:
        try:
            if test_file.exists():
                test_file.unlink()
        except Exception:
            pass

    free_gb = usage.free / (1024**3)
    total_gb = usage.total / (1024**3)
    free_pct = (usage.free / usage.total * 100.0) if usage.total else 0.0
    operational_write_verified = False
    operational_age_hours = None
    operational_archive_path = ""
    if not writable and operational_report_path:
        payload = read_json(Path(operational_report_path))
        generated_at = parse_utc_datetime(payload.get("generated_at"))
        current = now or utc_now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        if generated_at is not None:
            operational_age_hours = max(0.0, (current - generated_at).total_seconds() / 3600.0)
        archive_value = str(payload.get("archive_path") or "")
        archive = Path(archive_value) if archive_value else None
        try:
            archive_on_disk = bool(archive and archive.exists() and archive.stat().st_size > 0 and archive.resolve().is_relative_to(path.resolve()))
        except AttributeError:
            archive_on_disk = bool(archive and archive.exists() and archive.stat().st_size > 0 and str(archive.resolve()).startswith(str(path.resolve())))
        except Exception:
            archive_on_disk = False
        operational_write_verified = bool(
            archive_on_disk
            and operational_age_hours is not None
            and operational_age_hours <= operational_max_age_hours
            and str(payload.get("status") or "").upper() == "OK"
        )
        operational_archive_path = archive_value

    if not writable and not operational_write_verified:
        status = "FAIL"
    elif free_gb < fail_free_gb:
        status = "FAIL"
    elif free_gb < warn_free_gb:
        status = "WARN"
    else:
        status = "OK"
    detail = f"{path} mounted, {free_gb:.2f} GiB free ({free_pct:.1f}% of {total_gb:.0f} GiB)"
    if not writable:
        if operational_write_verified:
            detail = f"{path} mounted, backup write verified, {free_gb:.2f} GiB free"
        else:
            detail = f"{path} mounted but not writable"
    return check(
        "external_disk",
        status,
        detail,
        path=str(path),
        mounted=True,
        writable=writable,
        operational_write_verified=operational_write_verified,
        operational_age_hours=operational_age_hours,
        operational_archive_path=operational_archive_path,
        free_gb=free_gb,
        free_pct=free_pct,
        warn_free_gb=warn_free_gb,
        fail_free_gb=fail_free_gb,
    )


def path_size_bytes(path: Path) -> int | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return None
    total = 0
    try:
        for child in path.rglob("*"):
            try:
                if child.is_file() and not child.is_symlink():
                    total += child.stat().st_size
            except OSError:
                continue
    except OSError:
        return None
    return total


def read_tail(path: Path, max_bytes: int = 6000) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as fh:
            if path.stat().st_size > max_bytes:
                fh.seek(-max_bytes, os.SEEK_END)
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def validate_local_training_media(
    media_path: str | Path,
    *,
    external_disk_path: str | Path = DEFAULT_EXTERNAL_DISK_PATH,
    warn_size_gb: float = DEFAULT_TRAINING_MEDIA_WARN_GB,
    fail_size_gb: float = DEFAULT_TRAINING_MEDIA_FAIL_GB,
) -> dict[str, Any]:
    path = Path(media_path)
    external_disk = Path(external_disk_path)
    external_suggestion = external_disk / "MacArchive" / Path.home().name / "roxy_trading" / path.name
    exists = path.exists() or path.is_symlink()
    is_symlink = path.is_symlink()
    symlink_target = resolve_symlink_target(path) if is_symlink else ""
    size_bytes = path_size_bytes(path) if exists and not is_symlink else None
    size_gb = (size_bytes or 0) / (1024**3)

    if not exists:
        status = "OK"
        state = "ABSENT"
        detail = f"{path.name} no esta presente localmente"
    elif is_symlink:
        status = "OK"
        state = "EXTERNAL_LINKED" if symlink_target.startswith(str(external_disk.resolve(strict=False))) else "LINKED"
        detail = f"{path.name} esta enlazado a {symlink_target}"
    elif size_gb >= fail_size_gb:
        status = "FAIL"
        state = "LOCAL_TOO_LARGE"
        detail = f"{path.name} ocupa {size_gb:.2f} GiB local; mover a {external_suggestion}"
    elif size_gb >= warn_size_gb:
        status = "WARN"
        state = "LOCAL_GROWING"
        detail = f"{path.name} ocupa {size_gb:.2f} GiB local; preparar migracion a {external_suggestion}"
    else:
        status = "OK"
        state = "LOCAL_SMALL"
        detail = f"{path.name} ocupa {size_gb:.2f} GiB local"

    return check(
        "local_training_media",
        status,
        detail,
        state=state,
        path=str(path),
        exists=exists,
        is_symlink=is_symlink,
        symlink_target=symlink_target,
        size_bytes=size_bytes,
        size_gb=round(size_gb, 4),
        warn_size_gb=warn_size_gb,
        fail_size_gb=fail_size_gb,
        external_suggestion=str(external_suggestion),
    )


def project_storage_entries(base_dir: str | Path, *, exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    root = Path(base_dir)
    excluded = exclude_names or {".git"}
    entries: list[dict[str, Any]] = []
    if not root.exists() or not root.is_dir():
        return entries
    for child in root.iterdir():
        if child.name in excluded:
            continue
        size = path_size_bytes(child)
        if size is None:
            continue
        entries.append(
            {
                "name": child.name,
                "path": str(child),
                "size_bytes": size,
                "size_gb": round(size / (1024**3), 4),
                "is_dir": child.is_dir(),
                "is_symlink": child.is_symlink(),
            }
        )
    return sorted(entries, key=lambda item: int(item.get("size_bytes") or 0), reverse=True)


def project_storage_top_entries(base_dir: str | Path, *, limit: int = 5, exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    return project_storage_entries(base_dir, exclude_names=exclude_names)[: max(1, int(limit))]


def validate_project_storage_footprint(
    base_dir: str | Path,
    *,
    warn_size_gb: float = DEFAULT_PROJECT_STORAGE_WARN_GB,
    fail_size_gb: float = DEFAULT_PROJECT_STORAGE_FAIL_GB,
    top_limit: int = 5,
) -> dict[str, Any]:
    root = Path(base_dir)
    entries = project_storage_entries(root)
    if root.exists() and root.is_dir():
        size_bytes = sum(int(item.get("size_bytes") or 0) for item in entries)
    else:
        size_bytes = path_size_bytes(root)
    if size_bytes is None:
        return check("project_storage_footprint", "WARN", f"No se pudo medir {root}", path=str(root), exists=root.exists())
    size_gb = size_bytes / (1024**3)
    if size_gb >= fail_size_gb:
        status = "FAIL"
    elif size_gb >= warn_size_gb:
        status = "WARN"
    else:
        status = "OK"
    top_entries = entries[: max(1, int(top_limit))]
    leaders = ", ".join(f"{item['name']} {float(item['size_gb']):.2f} GiB" for item in top_entries[:3]) or "sin entradas"
    return check(
        "project_storage_footprint",
        status,
        f"{root.name} ocupa {size_gb:.2f} GiB local; top: {leaders}",
        path=str(root),
        size_bytes=size_bytes,
        size_gb=round(size_gb, 4),
        warn_size_gb=warn_size_gb,
        fail_size_gb=fail_size_gb,
        top_entries=top_entries,
    )


def validate_storage_migration(
    *,
    source_path: str | Path = DEFAULT_PARALLELS_SOURCE_PATH,
    destination_path: str | Path = DEFAULT_PARALLELS_DESTINATION_PATH,
    log_path: str | Path = DEFAULT_PARALLELS_MIGRATION_LOG_PATH,
    external_disk_path: str | Path = DEFAULT_EXTERNAL_DISK_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    source = Path(source_path)
    destination = Path(destination_path)
    log = Path(log_path)
    external_disk = Path(external_disk_path)
    source_exists = source.exists() or source.is_symlink()
    destination_exists = destination.exists()
    source_is_symlink = source.is_symlink()
    source_broken_symlink = source_is_symlink and not source.exists()
    symlink_target = str(source.resolve()) if source_is_symlink and source_exists else ""
    source_size = path_size_bytes(source) if source_exists and not source_is_symlink else None
    destination_size = path_size_bytes(destination) if destination_exists else None
    log_tail = read_tail(log)
    log_age_minutes = file_age_minutes(log, now=now) if log.exists() else None
    waiting_for_parallels = "Parallels sigue corriendo" in log_tail
    completed = source_is_symlink and destination_exists and str(destination.resolve()) == symlink_target

    if not external_disk.exists():
        status = "FAIL"
        state = "EXTERNAL_MISSING"
        detail = f"{external_disk} no esta montado; no se puede completar la migracion"
    elif source_broken_symlink and not destination_exists:
        status = "WARN"
        state = "BROKEN_SYMLINK"
        detail = f"Parallels apunta a {destination}, pero el destino externo no existe"
    elif completed:
        status = "OK"
        state = "MIGRATED"
        detail = f"Parallels apunta al disco externo ({destination})"
    elif destination_exists and not source_exists:
        status = "INFO"
        state = "DESTINATION_ONLY"
        detail = f"Destino existe en {destination}, pero fuente local no esta como symlink"
    elif source_exists and destination_exists:
        status = "INFO"
        state = "COPY_PRESENT"
        detail = "Fuente local y destino externo existen; falta completar symlink/limpieza"
    elif source_exists and waiting_for_parallels:
        status = "INFO"
        state = "WAITING_FOR_PARALLELS"
        detail = "Migracion pendiente: Parallels sigue abierto; se movera al cerrar la app"
    elif source_exists:
        status = "INFO"
        state = "LOCAL_ONLY"
        detail = "Parallels sigue ocupando espacio local; migracion externa pendiente"
    elif not source_exists and not destination_exists:
        status = "OK"
        state = "NOT_PRESENT"
        detail = "No se encontro carpeta Parallels local para migrar"
    else:
        status = "INFO"
        state = "UNKNOWN"
        detail = "Estado de migracion Parallels no concluyente"

    return check(
        "storage_migration",
        status,
        detail,
        state=state,
        source_path=str(source),
        destination_path=str(destination),
        log_path=str(log),
        source_exists=source_exists,
        destination_exists=destination_exists,
        source_is_symlink=source_is_symlink,
        source_broken_symlink=source_broken_symlink,
        symlink_target=symlink_target,
        source_size_bytes=source_size,
        destination_size_bytes=destination_size,
        log_exists=log.exists(),
        log_age_minutes=log_age_minutes,
        waiting_for_parallels=waiting_for_parallels,
    )


def resolve_symlink_target(path: Path) -> str:
    if not path.is_symlink():
        return ""
    try:
        raw_target = Path(os.readlink(path))
    except OSError:
        return ""
    if not raw_target.is_absolute():
        raw_target = path.parent / raw_target
    return str(raw_target.resolve(strict=False))


def validate_runtime_cache_migration(
    *,
    source_path: str | Path = DEFAULT_RUNTIME_CACHE_SOURCE_PATH,
    destination_path: str | Path = DEFAULT_RUNTIME_CACHE_DESTINATION_PATH,
    external_disk_path: str | Path = DEFAULT_EXTERNAL_DISK_PATH,
) -> dict[str, Any]:
    source = Path(source_path)
    destination = Path(destination_path)
    external_disk = Path(external_disk_path)
    source_exists = source.exists() or source.is_symlink()
    destination_exists = destination.exists()
    source_is_symlink = source.is_symlink()
    source_broken_symlink = source_is_symlink and not source.exists()
    symlink_target = resolve_symlink_target(source)
    expected_target = str(destination.resolve(strict=False))
    completed = source_is_symlink and destination_exists and symlink_target == expected_target
    source_size = path_size_bytes(source) if source_exists and not source_is_symlink else None
    destination_size = path_size_bytes(destination) if destination_exists else None

    if not external_disk.exists():
        status = "FAIL"
        state = "EXTERNAL_MISSING"
        detail = f"{external_disk} no esta montado; cache runtime externa no disponible"
    elif source_broken_symlink and symlink_target == expected_target:
        status = "WARN"
        state = "BROKEN_SYMLINK"
        detail = f"Cache runtime apunta a {destination}, pero el destino externo no existe"
    elif completed:
        status = "OK"
        state = "MIGRATED"
        detail = f"Cache runtime Codex apunta al disco externo ({destination})"
    elif destination_exists and not source_exists:
        status = "INFO"
        state = "DESTINATION_ONLY"
        detail = f"Cache runtime existe en {destination}, pero la fuente local no esta enlazada"
    elif source_exists and destination_exists:
        status = "WARN"
        state = "COPY_PRESENT"
        detail = "Cache runtime existe local y externa; falta completar enlace/limpieza"
    elif source_exists:
        status = "WARN"
        state = "LOCAL_ONLY"
        detail = "Cache runtime sigue ocupando espacio local; migracion externa pendiente"
    else:
        status = "OK"
        state = "NOT_PRESENT"
        detail = "No se encontro cache runtime local para migrar"

    return check(
        "runtime_cache_migration",
        status,
        detail,
        state=state,
        source_path=str(source),
        destination_path=str(destination),
        external_disk_path=str(external_disk),
        source_exists=source_exists,
        destination_exists=destination_exists,
        source_is_symlink=source_is_symlink,
        source_broken_symlink=source_broken_symlink,
        symlink_target=symlink_target,
        expected_target=expected_target,
        source_size_bytes=source_size,
        destination_size_bytes=destination_size,
    )


def storage_migration_needs_recovery(report: dict[str, Any]) -> bool:
    item = named_check(report, "storage_migration")
    return str(item.get("state") or "").upper() == "BROKEN_SYMLINK"


def ensure_storage_migration_target(
    *,
    source_path: str | Path = DEFAULT_PARALLELS_SOURCE_PATH,
    destination_path: str | Path = DEFAULT_PARALLELS_DESTINATION_PATH,
    external_disk_path: str | Path = DEFAULT_EXTERNAL_DISK_PATH,
    log_path: str | Path = DEFAULT_PARALLELS_MIGRATION_LOG_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    source = Path(source_path)
    destination = Path(destination_path)
    external_disk = Path(external_disk_path)
    log = Path(log_path)
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    status = validate_storage_migration(
        source_path=source,
        destination_path=destination,
        log_path=log,
        external_disk_path=external_disk,
        now=current,
    )
    if str(status.get("state") or "").upper() != "BROKEN_SYMLINK":
        return {"action": "not_needed", "ok": True, "status": status}
    if not external_disk.exists():
        return {"action": "error", "ok": False, "error": f"{external_disk} is not mounted", "status": status}
    expected_target = str(destination.resolve(strict=False))
    symlink_target = str(status.get("symlink_target") or "")
    if symlink_target != expected_target:
        return {
            "action": "error",
            "ok": False,
            "error": "source symlink does not point to expected destination",
            "symlink_target": symlink_target,
            "expected_target": expected_target,
            "status": status,
        }
    try:
        destination.mkdir(parents=True, exist_ok=True)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as handle:
            handle.write(f"{current.isoformat()} Recreated missing Parallels destination {destination}\n")
    except Exception as exc:
        return {"action": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}", "status": status}
    after = validate_storage_migration(
        source_path=source,
        destination_path=destination,
        log_path=log,
        external_disk_path=external_disk,
        now=current,
    )
    return {
        "action": "created_missing_destination",
        "ok": str(after.get("status") or "").upper() == "OK",
        "destination_path": str(destination),
        "before": status,
        "after": after,
    }


def validate_live_service(required_timeframes: set[str]) -> dict[str, Any]:
    try:
        from tools import ma_live_launchd

        info = ma_live_launchd.status()
    except Exception as exc:
        return check("live_service_24h", "WARN", f"Could not inspect LaunchAgent: {exc}")

    command = str(info.get("command") or "")
    issues = []
    if not info.get("installed"):
        issues.append("not installed")
    if not info.get("loaded"):
        issues.append("not loaded")
    if not info.get("keep_alive"):
        issues.append("KeepAlive disabled")
    if not command_has_timeframes(command, "--stock-intervals", required_timeframes):
        issues.append("stock intervals missing 2h/4h")
    if not command_has_timeframes(command, "--crypto-timeframes", required_timeframes):
        issues.append("crypto timeframes missing 2h/4h")
    retention_count = command_option_int(command, "--retention-count")
    if retention_count is None:
        issues.append("retention missing")
    elif retention_count <= 0 or retention_count > 288:
        issues.append(f"retention count out of range: {retention_count}")
    if not command_has_flag(command, "--health-check"):
        issues.append("continuous health check missing")
    status = "OK" if not issues else "FAIL"
    detail = "LaunchAgent live 24h loaded with full timeframes, retention, and health check" if not issues else "; ".join(issues)
    return check(
        "live_service_24h",
        status,
        detail,
        installed=bool(info.get("installed")),
        loaded=bool(info.get("loaded")),
        keep_alive=bool(info.get("keep_alive")),
        command=command,
        retention_count=retention_count,
        health_check=command_has_flag(command, "--health-check"),
    )


def validate_streamlit_service(expected_port: int | None = 8501) -> dict[str, Any]:
    try:
        from tools import streamlit_launchd

        info = streamlit_launchd.status()
    except Exception as exc:
        return check("streamlit_service_24h", "WARN", f"Could not inspect Streamlit LaunchAgent: {exc}")

    command = str(info.get("command") or "")
    port = info.get("port")
    issues = []
    if not info.get("installed"):
        issues.append("not installed")
    if not info.get("loaded"):
        issues.append("not loaded")
    if not info.get("keep_alive"):
        issues.append("KeepAlive disabled")
    if "streamlit_app.py" not in command:
        issues.append("command does not run streamlit_app.py")
    if expected_port is not None and port != expected_port:
        issues.append(f"port mismatch: {port or '-'}")
    status = "OK" if not issues else "FAIL"
    detail = "Streamlit LaunchAgent loaded with KeepAlive" if not issues else "; ".join(issues)
    return check(
        "streamlit_service_24h",
        status,
        detail,
        installed=bool(info.get("installed")),
        loaded=bool(info.get("loaded")),
        keep_alive=bool(info.get("keep_alive")),
        address=str(info.get("address") or "-"),
        port=port,
        command=command,
    )


def validate_daily_service() -> dict[str, Any]:
    try:
        from tools import ma_daily_launchd

        info = ma_daily_launchd.status()
    except Exception as exc:
        return check("daily_service", "WARN", f"Could not inspect daily LaunchAgent: {exc}")

    command = str(info.get("command") or "")
    schedule = dict(info.get("schedule") or {})
    issues = []
    if not info.get("installed"):
        issues.append("not installed")
    if not info.get("loaded"):
        issues.append("not loaded")
    if "ma_daily.py" not in command:
        issues.append("command does not run ma_daily.py")
    if "Hour" not in schedule or "Minute" not in schedule:
        issues.append("daily schedule missing")
    retention_count = command_option_int(command, "--retention-count")
    if retention_count is None:
        issues.append("retention missing")
    elif retention_count <= 0 or retention_count > 120:
        issues.append(f"retention count out of range: {retention_count}")
    status = "OK" if not issues else "FAIL"
    detail = "Daily LaunchAgent loaded with schedule and retention" if not issues else "; ".join(issues)
    return check(
        "daily_service",
        status,
        detail,
        installed=bool(info.get("installed")),
        loaded=bool(info.get("loaded")),
        command=command,
        schedule=schedule,
        retention_count=retention_count,
    )


def validate_health_watchdog_service() -> dict[str, Any]:
    try:
        from tools import roxy_health_launchd

        info = roxy_health_launchd.status()
    except Exception as exc:
        return check("health_watchdog_service", "WARN", f"Could not inspect health watchdog LaunchAgent: {exc}")

    command = str(info.get("command") or "")
    interval_seconds = info.get("interval_seconds")
    issues = []
    if not info.get("installed"):
        issues.append("not installed")
    if not info.get("loaded"):
        issues.append("not loaded")
    if "roxy_realtime_check.py" not in command:
        issues.append("command does not run roxy_realtime_check.py")
    if "--no-fail" not in command:
        issues.append("--no-fail missing")
    required_flags = [
        "--notify-health",
        "--ensure-runtime-backup-daemon",
        "--ensure-runtime-backup-report",
        "--ensure-core-launchagents",
        "--ensure-storage-migration",
        "--ensure-live-data",
        "--ensure-yfinance-cache",
        "--ensure-streamlit-app",
        "--ensure-chart-health-report",
        "--ensure-output-maintenance-report",
        "--ensure-alert-quality-report",
    ]
    missing_flags = [flag for flag in required_flags if not command_has_flag(command, flag)]
    for flag in missing_flags:
        issues.append(f"{flag} missing")
    try:
        interval_value = int(interval_seconds or 0)
    except (TypeError, ValueError):
        interval_value = 0
    if interval_value <= 0:
        issues.append("StartInterval missing")
    elif interval_value > 900:
        issues.append(f"interval too slow: {interval_value}s")
    status = "OK" if not issues else "FAIL"
    detail = "Health watchdog LaunchAgent loaded with periodic realtime checks" if not issues else "; ".join(issues)
    return check(
        "health_watchdog_service",
        status,
        detail,
        installed=bool(info.get("installed")),
        loaded=bool(info.get("loaded")),
        command=command,
        interval_seconds=interval_value or interval_seconds,
        run_at_load=bool(info.get("run_at_load")),
        required_flags=required_flags,
        missing_flags=missing_flags,
    )


def validate_notification_delivery(alerts_path: Path = ALERTS_DIR) -> dict[str, Any]:
    try:
        import notifier

        channels = notifier.configured_channels()
        channel_status = notifier.notification_channel_status()
        history_summary = notifier.notification_history_summary(limit=50)
    except Exception as exc:
        return check("notification_delivery", "WARN", f"Could not inspect notification channels: {exc}")

    alerts_writable = False
    probe_error = ""
    if alerts_path.exists() and alerts_path.is_dir():
        probe = alerts_path / f".roxy_notification_probe_{os.getpid()}_{int(time.time() * 1000)}"
        try:
            probe.write_text("ok")
            alerts_writable = probe.read_text() == "ok"
        except Exception as exc:
            probe_error = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                if probe.exists():
                    probe.unlink()
            except Exception:
                pass
    malformed_recent_lines = int(history_summary.get("malformed_recent_lines") or 0)
    sample_size = int(history_summary.get("sample_size") or 0)
    sent_count = int(history_summary.get("sent_count") or 0)
    suppressed_count = int(history_summary.get("suppressed_count") or 0)
    local_recorded_count = int(history_summary.get("local_recorded_count") or 0)
    cooldown_skipped = int(history_summary.get("cooldown_skipped") or 0)
    if channels:
        status = "OK"
        detail = "Configured channels: " + ", ".join(channels)
    elif alerts_writable:
        status = "INFO"
        detail = "No external channels configured; local alert files are writable"
        last_reason = str(history_summary.get("last_reason") or "")
        last_age_minutes = history_summary.get("last_age_minutes")
        if last_reason and last_reason != "-":
            detail += f"; last local event {last_reason}"
            if last_age_minutes is not None:
                detail += f" {float(last_age_minutes):.1f}m ago"
    else:
        status = "FAIL"
        detail = "No notification channels configured and local alerts path is not writable"
        if probe_error:
            detail += f": {probe_error}"
    if sample_size:
        detail += f"; history sample {sample_size}, sent {sent_count}, local {local_recorded_count}"
        if suppressed_count:
            detail += f", suppressed {suppressed_count}"
        if cooldown_skipped:
            detail += f", cooldown skipped {cooldown_skipped}"
    if malformed_recent_lines and status != "FAIL":
        status = "WARN"
        detail = f"Notification history has {malformed_recent_lines} malformed recent line(s); {detail}"
    return check(
        "notification_delivery",
        status,
        detail,
        channels=channels,
        channel_count=len(channels),
        local_file_fallback=alerts_writable,
        channel_status=channel_status,
        history_summary=history_summary,
        malformed_recent_lines=malformed_recent_lines,
        sample_size=sample_size,
        sent_count=sent_count,
        suppressed_count=suppressed_count,
        local_recorded_count=local_recorded_count,
        cooldown_skipped=cooldown_skipped,
        last_reason=history_summary.get("last_reason"),
        last_age_minutes=history_summary.get("last_age_minutes"),
        delivery_mode=history_summary.get("delivery_mode"),
        probe_error=probe_error,
    )


def validate_ai_brief_report(brief_path: str | Path) -> dict[str, Any]:
    path = Path(brief_path)
    brief = read_json(path)
    if not brief:
        return check("ai_brief", "FAIL", "AI brief not found or unreadable", path=str(path))

    freshness = brief.get("source_freshness") or {}
    allowed = bool(freshness.get("alerts_allowed", True))
    gate_summary = brief.get("alert_gate_summary") or {}
    alert_count = int(brief.get("alert_count", gate_summary.get("alert_count", 0)) or 0)
    watch_count = int(brief.get("watch_count", gate_summary.get("watch_count", 0)) or 0)
    total_opportunities = int(gate_summary.get("total_opportunities", alert_count + watch_count) or 0)
    notifications_ready = int(gate_summary.get("notifications_ready", alert_count) or 0)
    avg_readiness = gate_summary.get("avg_readiness")
    top_gate = str(gate_summary.get("top_gate_label") or gate_summary.get("top_gate") or "")
    top_blocker = str(gate_summary.get("top_blocker") or "")
    top_quality = str(gate_summary.get("top_quality") or "")

    detail = str(freshness.get("detail") or "AI brief readable")
    detail += f"; alerts {alert_count}, watch {watch_count}, ready {notifications_ready}/{total_opportunities}"
    if avg_readiness is not None:
        detail += f", avg readiness {float(avg_readiness):.1f}"
    if top_quality:
        detail += f", top quality {top_quality}"
    if top_gate:
        detail += f", gate {top_gate}"
    if top_blocker:
        detail += f", blocker {top_blocker}"

    return check(
        "ai_brief",
        "OK" if allowed else "FAIL",
        detail,
        path=str(path),
        alerts_allowed=allowed,
        alert_count=alert_count,
        watch_count=watch_count,
        total_opportunities=total_opportunities,
        notifications_ready=notifications_ready,
        avg_readiness=avg_readiness,
        top_gate=top_gate,
        top_blocker=top_blocker,
        top_quality=top_quality,
        source_freshness=freshness,
    )


def default_operational_log_paths(base_dir: Path = BASE_DIR) -> list[Path]:
    user_log_dir = Path.home() / "Library" / "Logs" / "RoxyTrading"
    local_log_dir = base_dir / "logs"
    names = (
        "streamlit_launchd.err",
        "ma_live.err",
        "ma_daily.err",
        "weekly.err",
        "roxy_launchd.err",
        "roxy_health_watchdog.err",
        "runtime_backup.err",
        "runtime_backup_daemon.err",
    )
    paths: list[Path] = []
    try:
        include_user_logs = base_dir.resolve() == BASE_DIR.resolve()
    except Exception:
        include_user_logs = base_dir == BASE_DIR
    log_dirs = (user_log_dir, local_log_dir) if include_user_logs else (local_log_dir,)
    for log_dir in log_dirs:
        for name in names:
            path = log_dir / name
            if path not in paths:
                paths.append(path)
    return paths


def default_streamlit_log_paths(base_dir: Path = BASE_DIR) -> list[Path]:
    user_log_dir = Path.home() / "Library" / "Logs" / "RoxyTrading"
    local_log_dir = base_dir / "logs"
    paths: list[Path] = []
    try:
        include_user_logs = base_dir.resolve() == BASE_DIR.resolve()
    except Exception:
        include_user_logs = base_dir == BASE_DIR
    log_dirs = (user_log_dir, local_log_dir) if include_user_logs else (local_log_dir,)
    for log_dir in log_dirs:
        path = log_dir / "streamlit_launchd.err"
        if path not in paths:
            paths.append(path)
    return paths


def read_log_tail(path: Path, *, tail_bytes: int = DEFAULT_OPERATIONAL_LOG_TAIL_BYTES) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > tail_bytes:
                handle.seek(-tail_bytes, os.SEEK_END)
            data = handle.read()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def operational_log_signals(text: str) -> tuple[list[str], list[str], int]:
    critical: list[str] = []
    warnings_found: list[str] = []
    ignored = 0
    benign_streamlit_websocket_close = (
        "tornado.websocket.WebSocketClosedError" in text
        and "StreamClosedError: Stream is closed" in text
        and "TypeError" not in text
    )
    yfinance_cache_error = bool(YFINANCE_CACHE_ERROR_PATTERN.search(text))
    benign_yfinance_provider_noise = (
        not yfinance_cache_error
        and (
            "Failed to get ticker" in text
            or "HTTP Error 500: <!DOCTYPE html>" in text
            or "HTTP Error 502: <!DOCTYPE html>" in text
            or "Failed to parse json response from Yahoo Finance" in text
            or "YAHOO! FINANCE IS CURRENTLY DOWN!" in text
        )
    )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if benign_streamlit_websocket_close and (
            line == "Traceback (most recent call last):"
            or line == "During handling of the above exception, another exception occurred:"
            or "Task exception was never retrieved" in line
            or "WebSocketProtocol13.write_message" in line
            or "tornado.websocket.WebSocketClosedError" in line
            or "StreamClosedError: Stream is closed" in line
            or "raise WebSocketClosedError()" in line
            or "/tornado/websocket.py" in line
        ):
            ignored += 1
            continue
        if any(pattern in line for pattern in BENIGN_OPERATIONAL_LOG_PATTERNS):
            ignored += 1
            continue
        if benign_yfinance_provider_noise and (
            re.search(r"^\d{4}-\d{2}-\d{2} .*ERROR\s*$", line)
            or line == "1 Failed download:"
        ):
            ignored += 1
            continue
        for pattern in CRITICAL_OPERATIONAL_LOG_PATTERNS:
            if re.search(pattern, line, flags=re.IGNORECASE):
                critical.append(line[:240])
                break
        else:
            for pattern in WARNING_OPERATIONAL_LOG_PATTERNS:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    warnings_found.append(line[:240])
                    break
    return critical, warnings_found, ignored


def validate_operational_logs(
    log_paths: list[Path] | None = None,
    *,
    base_dir: Path = BASE_DIR,
    max_age_minutes: float = DEFAULT_OPERATIONAL_LOG_MAX_AGE_MINUTES,
    tail_bytes: int = DEFAULT_OPERATIONAL_LOG_TAIL_BYTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    paths = log_paths if log_paths is not None else default_operational_log_paths(base_dir)
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    checked: list[dict[str, Any]] = []
    critical_issues: list[dict[str, Any]] = []
    warning_issues: list[dict[str, Any]] = []
    yfinance_cache_issues: list[dict[str, Any]] = []
    ignored_line_count = 0
    active_count = 0
    existing_count = 0

    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        existing_count += 1
        try:
            stat = path.stat()
        except OSError as exc:
            warning_issues.append({"path": str(path), "line": f"could not stat log: {exc}"})
            continue
        age_minutes = max(0.0, (current - datetime.fromtimestamp(stat.st_mtime, timezone.utc)).total_seconds() / 60.0)
        entry = {"path": str(path), "size_bytes": stat.st_size, "age_minutes": age_minutes}
        checked.append(entry)
        if stat.st_size <= 0 or age_minutes > max_age_minutes:
            continue
        active_count += 1
        critical, warnings_found, ignored = operational_log_signals(read_log_tail(path, tail_bytes=tail_bytes))
        ignored_line_count += ignored
        for line in critical[:5]:
            critical_issues.append({"path": str(path), "line": line})
        for line in warnings_found[:5]:
            issue = {"path": str(path), "line": line}
            warning_issues.append(issue)
            if YFINANCE_CACHE_ERROR_PATTERN.search(line):
                yfinance_cache_issues.append(issue)

    status = "FAIL" if critical_issues else "WARN" if warning_issues else "OK"
    detail = (
        f"{existing_count} logs found, {active_count} active, "
        f"{len(critical_issues)} critical, {len(warning_issues)} warnings"
    )
    if ignored_line_count:
        detail += f", ignored {ignored_line_count} benign lines"
    return check(
        "operational_logs",
        status,
        detail,
        existing_count=existing_count,
        active_count=active_count,
        max_age_minutes=max_age_minutes,
        tail_bytes=tail_bytes,
        critical_issues=critical_issues[:10],
        warning_issues=warning_issues[:10],
        yfinance_cache_issues=yfinance_cache_issues[:10],
        yfinance_cache_issue_count=len(yfinance_cache_issues),
        ignored_line_count=ignored_line_count,
        checked_logs=checked,
    )


def validate_alert_quality_report(
    report_path: Path,
    *,
    max_age_minutes: float = DEFAULT_ALERT_QUALITY_MAX_AGE_MINUTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = read_json(report_path)
    if not payload:
        return check("alert_quality_report", "WARN", "Alert quality report not found or unreadable", path=str(report_path))

    generated_at = parse_utc_datetime(payload.get("generated_at"))
    if generated_at is None:
        return check("alert_quality_report", "FAIL", "Alert quality generated_at missing or invalid", path=str(report_path))

    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age_minutes = max(0.0, (current - generated_at).total_seconds() / 60.0)
    age_status = "OK" if age_minutes <= max_age_minutes else "WARN" if age_minutes <= max_age_minutes * 3 else "FAIL"
    brief_generated_at = parse_utc_datetime(payload.get("brief_generated_at"))
    if brief_generated_at is None:
        entry_payload = payload.get("latest_entry") if isinstance(payload.get("latest_entry"), dict) else {}
        if not entry_payload:
            entry_payload = payload.get("entry") if isinstance(payload.get("entry"), dict) else {}
        brief_generated_at = parse_utc_datetime(entry_payload.get("generated_at"))
    if brief_generated_at is None:
        brief_age_minutes = None
        brief_age_status = "WARN"
    else:
        brief_age_minutes = max(0.0, (current - brief_generated_at).total_seconds() / 60.0)
        brief_age_status = (
            "OK"
            if brief_age_minutes <= max_age_minutes
            else "WARN"
            if brief_age_minutes <= max_age_minutes * 3
            else "FAIL"
        )
    report_status = str(payload.get("status") or "OK").upper()
    if report_status not in {"OK", "WARN", "FAIL"}:
        report_status = "WARN"
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    entry = payload.get("entry") if isinstance(payload.get("entry"), dict) else {}
    state = str(summary.get("state") or entry.get("state") or "UNKNOWN").upper()
    ready = int(summary.get("latest_notifications_ready") or entry.get("notifications_ready") or 0)
    total = int(summary.get("latest_total_opportunities") or entry.get("total_opportunities") or 0)
    waiting_streak = int(summary.get("waiting_streak") or 0)
    blocker_streak = int(summary.get("latest_top_blocker_streak") or 0)
    persistent_blocker_minutes = summary.get("persistent_blocker_minutes")
    avg_readiness = summary.get("avg_readiness", entry.get("avg_readiness"))
    readiness_delta = summary.get("readiness_delta")
    dominant_blocker = summary.get("dominant_blocker") if isinstance(summary.get("dominant_blocker"), dict) else {}
    blocker_category = str(summary.get("blocker_category") or "")
    recommended_action = str(summary.get("recommended_action") or "")
    status = status_max(age_status, brief_age_status, report_status)
    detail = f"age {age_minutes:.0f}m"
    if brief_age_minutes is None:
        detail += ", brief age missing"
    else:
        detail += f", brief age {brief_age_minutes:.0f}m"
    detail += f", state {state}, ready {ready}/{total}"
    if waiting_streak:
        detail += f", waiting streak {waiting_streak}"
    if blocker_streak:
        detail += f", blocker streak {blocker_streak}"
    if persistent_blocker_minutes is not None:
        detail += f", persistent {float(persistent_blocker_minutes):.1f}m"
    if avg_readiness is not None:
        detail += f", avg readiness {float(avg_readiness):.1f}"
    if readiness_delta is not None:
        detail += f", readiness trend {float(readiness_delta):+.1f}"
    if dominant_blocker.get("name"):
        detail += f", recurrent blocker {dominant_blocker.get('name')} x{dominant_blocker.get('count', 0)}"
    if blocker_category:
        detail += f", category {blocker_category}"
    top_blocker = str(summary.get("latest_top_blocker") or entry.get("top_blocker") or "")
    if top_blocker and top_blocker != "-":
        detail += f", blocker {top_blocker}"
    if recommended_action:
        detail += f", action {recommended_action}"
    return check(
        "alert_quality_report",
        status,
        detail,
        path=str(report_path),
        generated_at=generated_at.isoformat(),
        brief_generated_at=brief_generated_at.isoformat() if brief_generated_at else "",
        age_minutes=age_minutes,
        brief_age_minutes=brief_age_minutes,
        state=state,
        notifications_ready=ready,
        total_opportunities=total,
        waiting_streak=waiting_streak,
        latest_top_blocker_streak=blocker_streak,
        persistent_blocker_minutes=persistent_blocker_minutes,
        avg_readiness=avg_readiness,
        readiness_delta=readiness_delta,
        dominant_blocker=dominant_blocker,
        blocker_category=blocker_category,
        recommended_action=recommended_action,
        top_blocker=top_blocker,
    )


def validate_output_maintenance_service() -> dict[str, Any]:
    try:
        from tools import output_maintenance_launchd

        info = output_maintenance_launchd.status()
    except Exception as exc:
        return check("output_maintenance_service", "WARN", f"Could not inspect output maintenance LaunchAgent: {exc}")

    command = str(info.get("command") or "")
    schedule = dict(info.get("schedule") or {})
    issues = []
    if not info.get("installed"):
        issues.append("not installed")
    if not info.get("loaded"):
        issues.append("not loaded")
    if "output_maintenance.py" not in command:
        issues.append("command does not run output_maintenance.py")
    if "Hour" not in schedule or "Minute" not in schedule:
        issues.append("daily schedule missing")
    status = "OK" if not issues else "FAIL"
    detail = "Output maintenance LaunchAgent loaded with daily schedule" if not issues else "; ".join(issues)
    return check(
        "output_maintenance_service",
        status,
        detail,
        installed=bool(info.get("installed")),
        loaded=bool(info.get("loaded")),
        command=command,
        schedule=schedule,
    )


def validate_runtime_backup_service() -> dict[str, Any]:
    daemon_heartbeat = read_json(DEFAULT_RUNTIME_BACKUP_DAEMON_HEARTBEAT_PATH)
    daemon_generated_at = parse_utc_datetime(daemon_heartbeat.get("generated_at")) if daemon_heartbeat else None
    current = utc_now()
    daemon_age_minutes = (
        max(0.0, (current - daemon_generated_at).total_seconds() / 60.0)
        if daemon_generated_at is not None
        else None
    )
    daemon_running = bool(
        daemon_heartbeat
        and daemon_age_minutes is not None
        and daemon_age_minutes <= 15.0
        and pid_is_running(daemon_heartbeat.get("pid"))
        and str(daemon_heartbeat.get("status") or "").upper() in {"RUNNING", "DEGRADED"}
    )
    daemon_ok = bool(daemon_running and str(daemon_heartbeat.get("last_backup_status") or "").upper() in {"OK", "DRY_RUN"})

    try:
        from tools import runtime_backup_launchd

        info = runtime_backup_launchd.status()
    except Exception as exc:
        if daemon_ok:
            return check(
                "runtime_backup_service",
                "OK",
                "Runtime backup daemon active; LaunchAgent inspection unavailable",
                daemon_running=daemon_running,
                daemon_age_minutes=daemon_age_minutes,
                daemon_pid=daemon_heartbeat.get("pid") if daemon_heartbeat else None,
                daemon_status=daemon_heartbeat.get("status") if daemon_heartbeat else None,
                daemon_last_backup_status=daemon_heartbeat.get("last_backup_status") if daemon_heartbeat else None,
                daemon_last_backup_at=daemon_heartbeat.get("last_backup_at") if daemon_heartbeat else None,
                daemon_next_backup_at=daemon_heartbeat.get("next_backup_at") if daemon_heartbeat else None,
            )
        return check("runtime_backup_service", "WARN", f"Could not inspect runtime backup LaunchAgent: {exc}")

    command = str(info.get("command") or "")
    schedule = dict(info.get("schedule") or {})
    issues = []
    if not info.get("installed"):
        issues.append("not installed")
    if not info.get("loaded"):
        issues.append("not loaded")
    if "runtime_backup.py" not in command:
        issues.append("command does not run runtime_backup.py")
    if "Hour" not in schedule or "Minute" not in schedule:
        issues.append("daily schedule missing")
    launchd_ok = not issues
    status = "OK" if launchd_ok or daemon_ok else "FAIL"
    if daemon_ok and launchd_ok:
        detail = "Runtime backup LaunchAgent and daemon active"
    elif daemon_ok:
        detail = "Runtime backup daemon active; LaunchAgent not primary"
    elif launchd_ok:
        detail = "Runtime backup LaunchAgent loaded with daily schedule"
    else:
        detail = "; ".join(issues)
    return check(
        "runtime_backup_service",
        status,
        detail,
        installed=bool(info.get("installed")),
        loaded=bool(info.get("loaded")),
        command=command,
        schedule=schedule,
        daemon_running=daemon_running,
        daemon_age_minutes=daemon_age_minutes,
        daemon_pid=daemon_heartbeat.get("pid") if daemon_heartbeat else None,
        daemon_status=daemon_heartbeat.get("status") if daemon_heartbeat else None,
        daemon_last_backup_status=daemon_heartbeat.get("last_backup_status") if daemon_heartbeat else None,
        daemon_last_backup_at=daemon_heartbeat.get("last_backup_at") if daemon_heartbeat else None,
        daemon_next_backup_at=daemon_heartbeat.get("next_backup_at") if daemon_heartbeat else None,
    )


def status_max(*statuses: str) -> str:
    rank = {"OK": 0, "WARN": 1, "FAIL": 2}
    return max((status for status in statuses if status), key=lambda status: rank.get(status, 0), default="OK")


def validate_output_maintenance_report(
    report_path: Path,
    *,
    max_age_hours: float = 36.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = read_json(report_path)
    if not payload:
        return check("output_maintenance_report", "WARN", "Maintenance report not found or unreadable", path=str(report_path))

    generated_at = parse_utc_datetime(payload.get("generated_at"))
    if generated_at is None:
        return check("output_maintenance_report", "FAIL", "Maintenance report generated_at missing or invalid", path=str(report_path))

    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (current - generated_at).total_seconds() / 3600.0)
    if age_hours <= max_age_hours:
        age_status = "OK"
    elif age_hours <= max_age_hours * 2:
        age_status = "WARN"
    else:
        age_status = "FAIL"

    output_value = str(payload.get("output_dir") or "")
    output_path = Path(output_value) if output_value else None
    output_exists = bool(output_path and output_path.exists())
    output_status = "OK" if output_exists else "FAIL"
    dry_run = bool(payload.get("dry_run"))
    dry_run_status = "WARN" if dry_run else "OK"
    output_archive_error_count = int(payload.get("output_archive_error_count", 0) or 0)
    archive_status = "WARN" if output_archive_error_count else "OK"
    status = status_max(age_status, output_status, dry_run_status, archive_status)

    details = [f"age {age_hours:.1f}h"]
    if not output_exists:
        details.append("output_dir missing")
    if dry_run:
        details.append("last run was dry-run")
    removed_count = int(payload.get("removed_count", 0) or 0)
    output_archive_count = int(payload.get("output_archive_count", 0) or 0)
    stale_output_removed_count = int(payload.get("stale_output_removed_count", 0) or 0)
    trimmed_log_count = int(payload.get("trimmed_log_count", 0) or 0)
    trimmed_history_count = int(payload.get("trimmed_history_count", 0) or 0)
    removed_alert_report_count = int(payload.get("removed_alert_report_count", 0) or 0)
    runtime_footprint_after = dict(payload.get("runtime_footprint_after") or {})
    runtime_footprint_mb = runtime_footprint_after.get("total_mb")
    runtime_footprint_reclaimed_bytes = int(payload.get("runtime_footprint_reclaimed_bytes", 0) or 0)
    kept_counts = dict(payload.get("kept_counts") or {})
    details.append(f"removed {removed_count}")
    details.append(f"archived output {output_archive_count}")
    if output_archive_error_count:
        details.append(f"archive errors {output_archive_error_count}")
    details.append(f"removed stale output {stale_output_removed_count}")
    details.append(f"trimmed logs {trimmed_log_count}")
    details.append(f"trimmed histories {trimmed_history_count}")
    details.append(f"removed alert reports {removed_alert_report_count}")
    if runtime_footprint_mb is not None:
        details.append(f"runtime footprint {float(runtime_footprint_mb):.1f} MB")
    if runtime_footprint_reclaimed_bytes:
        details.append(f"reclaimed {runtime_footprint_reclaimed_bytes} bytes")
    return check(
        "output_maintenance_report",
        status,
        ", ".join(details),
        path=str(report_path),
        generated_at=generated_at.isoformat(),
        age_hours=age_hours,
        max_age_hours=max_age_hours,
        output_dir=output_value,
        output_exists=output_exists,
        dry_run=dry_run,
        removed_count=removed_count,
        output_archive_count=output_archive_count,
        output_archive_error_count=output_archive_error_count,
        output_archive_dir=str(payload.get("output_archive_dir") or payload.get("archive_dir") or ""),
        stale_output_removed_count=stale_output_removed_count,
        stale_output_removed_counts=dict(payload.get("stale_output_removed_counts") or {}),
        trimmed_log_count=trimmed_log_count,
        trimmed_history_count=trimmed_history_count,
        removed_alert_report_count=removed_alert_report_count,
        runtime_footprint_after=runtime_footprint_after,
        runtime_footprint_mb=runtime_footprint_mb,
        runtime_footprint_reclaimed_bytes=runtime_footprint_reclaimed_bytes,
        kept_counts=kept_counts,
    )


def validate_runtime_backup_report(
    report_path: Path,
    *,
    max_age_hours: float = DEFAULT_RUNTIME_BACKUP_MAX_AGE_HOURS,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = read_json(report_path)
    if not payload:
        return check("runtime_backup_report", "WARN", "Runtime backup report not found or unreadable", path=str(report_path))

    generated_at = parse_utc_datetime(payload.get("generated_at"))
    if generated_at is None:
        return check("runtime_backup_report", "FAIL", "Runtime backup generated_at missing or invalid", path=str(report_path))

    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (current - generated_at).total_seconds() / 3600.0)
    if age_hours <= max_age_hours:
        age_status = "OK"
    elif age_hours <= max_age_hours * 2:
        age_status = "WARN"
    else:
        age_status = "FAIL"

    archive_value = str(payload.get("archive_path") or "")
    archive_path = Path(archive_value) if archive_value else None
    archive_exists = bool(archive_path and archive_path.exists())
    archive_size_bytes = int(payload.get("archive_size_bytes") or 0)
    if archive_exists and archive_path:
        try:
            archive_size_bytes = archive_path.stat().st_size
        except OSError:
            archive_exists = False
            archive_size_bytes = 0
    dry_run = bool(payload.get("dry_run"))
    archive_status = "OK" if dry_run or (archive_exists and archive_size_bytes > 0) else "FAIL"
    dry_run_status = "WARN" if dry_run else "OK"
    payload_status = str(payload.get("status") or "OK").upper()
    if payload_status not in {"OK", "DRY_RUN"}:
        report_status = "FAIL"
    else:
        report_status = "WARN" if payload_status == "DRY_RUN" else "OK"

    expected_paths = [str(value).strip().strip("/") for value in (payload.get("include_paths") or DEFAULT_RUNTIME_BACKUP_REQUIRED_PATHS) if str(value).strip()]
    archive_readable = bool(payload.get("archive_readable"))
    reported_archive_readable = archive_readable
    reported_archive_verified = bool(payload.get("archive_verified"))
    archive_member_count = int(payload.get("archive_member_count") or 0)
    archive_verified_paths = [str(value) for value in (payload.get("archive_verified_paths") or [])]
    archive_missing_verified_paths = [str(value) for value in (payload.get("archive_missing_verified_paths") or [])]
    archive_verification_error = str(payload.get("archive_verification_error") or "")
    archive_verification_source = "report" if reported_archive_verified else "runtime"
    if archive_exists and archive_path and not dry_run:
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                names = archive.getnames()
            archive_readable = True
            archive_member_count = len(names)
            archive_verified_paths = [
                expected_path
                for expected_path in expected_paths
                if any(name == expected_path or name.startswith(f"{expected_path}/") for name in names)
            ]
            archive_missing_verified_paths = [path for path in expected_paths if path not in set(archive_verified_paths)]
            archive_verification_error = ""
            archive_verification_source = "runtime"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            reported_verified_set = {str(value) for value in archive_verified_paths}
            expected_set = set(expected_paths)
            can_trust_report_verification = (
                isinstance(exc, PermissionError)
                and reported_archive_readable
                and reported_archive_verified
                and expected_set.issubset(reported_verified_set)
                and not archive_missing_verified_paths
                and archive_size_bytes > 0
            )
            if can_trust_report_verification:
                archive_verification_error = error
                archive_verification_source = "report"
            else:
                archive_readable = False
                archive_member_count = 0
                archive_verified_paths = []
                archive_missing_verified_paths = expected_paths
                archive_verification_error = error
                archive_verification_source = "runtime"
    archive_verified = bool(dry_run or (archive_readable and not archive_missing_verified_paths))
    verification_status = "OK" if dry_run or archive_verified else "FAIL"
    status = status_max(age_status, archive_status, dry_run_status, report_status, verification_status)

    details = [f"age {age_hours:.1f}h"]
    if archive_exists:
        details.append(f"archive {archive_size_bytes} bytes")
    else:
        details.append("archive missing")
    if archive_verified:
        details.append(f"verified {len(archive_verified_paths)}/{len(expected_paths)}")
    elif not dry_run:
        details.append("archive not verified")
    removed_count = int(payload.get("removed_count", 0) or 0)
    details.append(f"removed {removed_count}")
    if dry_run:
        details.append("dry-run")

    return check(
        "runtime_backup_report",
        status,
        ", ".join(details),
        path=str(report_path),
        generated_at=generated_at.isoformat(),
        age_hours=age_hours,
        max_age_hours=max_age_hours,
        archive_path=archive_value,
        archive_exists=archive_exists,
        archive_size_bytes=archive_size_bytes,
        target_dir=str(payload.get("target_dir") or ""),
        dry_run=dry_run,
        removed_count=removed_count,
        archive_readable=archive_readable,
        archive_verified=archive_verified,
        archive_member_count=archive_member_count,
        archive_verified_paths=archive_verified_paths,
        archive_missing_verified_paths=archive_missing_verified_paths,
        archive_verification_error=archive_verification_error,
        archive_verification_source=archive_verification_source,
    )


def validate_chart_health_report(
    report_path: Path,
    *,
    max_age_minutes: float = 30.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = read_json(report_path)
    if not payload:
        return check("chart_realtime_health_report", "WARN", "Chart realtime report not found or unreadable", path=str(report_path))

    generated_at = parse_utc_datetime(payload.get("generated_at"))
    if generated_at is None:
        return check("chart_realtime_health_report", "FAIL", "Chart realtime report generated_at missing or invalid", path=str(report_path))

    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age_minutes = max(0.0, (current - generated_at).total_seconds() / 60.0)
    age_status = "OK" if age_minutes <= max_age_minutes else "WARN" if age_minutes <= max_age_minutes * 3 else "FAIL"
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    summary_status = str(summary.get("status") or "WARN").upper()
    if summary_status not in {"OK", "WARN", "FAIL"}:
        summary_status = "WARN"
    status = status_max(age_status, summary_status)
    checked_count = int(summary.get("checked_count", 0) or 0)
    fail_count = int(summary.get("fail_count", 0) or 0)
    warn_count = int(summary.get("warn_count", 0) or 0)
    max_chart_age_minutes = summary.get("max_age_minutes")
    avg_chart_age_minutes = summary.get("avg_age_minutes")
    max_cadence_lag_minutes = summary.get("max_cadence_lag_minutes")
    max_health_lag_minutes = summary.get("max_health_lag_minutes")
    next_expected_update_in_minutes = summary.get("next_expected_update_in_minutes")
    stalest_chart = summary.get("stalest_chart") if isinstance(summary.get("stalest_chart"), dict) else {}
    most_overdue_chart = summary.get("most_overdue_chart") if isinstance(summary.get("most_overdue_chart"), dict) else {}
    details = [f"age {age_minutes:.0f}m", f"checked {checked_count}", f"fail {fail_count}", f"warn {warn_count}"]
    if max_chart_age_minutes is not None:
        details.append(f"max chart age {float(max_chart_age_minutes):.1f}m")
    if max_cadence_lag_minutes is not None and float(max_cadence_lag_minutes) > 0:
        details.append(f"cadence lag {float(max_cadence_lag_minutes):.1f}m")
    elif next_expected_update_in_minutes is not None:
        details.append(f"next candle {float(next_expected_update_in_minutes):.1f}m")
    if max_health_lag_minutes is not None and float(max_health_lag_minutes) > 0:
        details.append(f"health lag {float(max_health_lag_minutes):.1f}m")
    if stalest_chart:
        details.append(f"stalest {stalest_chart.get('symbol', '-')} {stalest_chart.get('timeframe', '-')}")
    if most_overdue_chart and max_cadence_lag_minutes is not None and float(max_cadence_lag_minutes) > 0:
        details.append(f"overdue {most_overdue_chart.get('symbol', '-')} {most_overdue_chart.get('timeframe', '-')}")
    return check(
        "chart_realtime_health_report",
        status,
        ", ".join(details),
        path=str(report_path),
        generated_at=generated_at.isoformat(),
        age_minutes=age_minutes,
        checked_count=checked_count,
        fail_count=fail_count,
        warn_count=warn_count,
        max_chart_age_minutes=max_chart_age_minutes,
        avg_chart_age_minutes=avg_chart_age_minutes,
        max_cadence_lag_minutes=max_cadence_lag_minutes,
        max_health_lag_minutes=max_health_lag_minutes,
        next_expected_update_in_minutes=next_expected_update_in_minutes,
        stalest_chart=stalest_chart,
        most_overdue_chart=most_overdue_chart,
    )


def evaluate_realtime_health(
    *,
    base_dir: Path = BASE_DIR,
    max_age_minutes: float = 10.0,
    maintenance_max_age_hours: float = 36.0,
    required_timeframes: set[str] | None = None,
    app_url: str = "",
    chart_symbol: str | None = None,
    chart_timeframe: str = "1h",
    skip_chart_fetch: bool = False,
    skip_service_check: bool = False,
    warn_free_gb: float = 1.0,
    fail_free_gb: float = 0.25,
    running_warn_minutes: float = 15.0,
    running_fail_minutes: float = 30.0,
    external_disk_path: str | Path | None = None,
    external_warn_free_gb: float = 100.0,
    external_fail_free_gb: float = 20.0,
    storage_migration_source_path: str | Path | None = None,
    storage_migration_destination_path: str | Path | None = None,
    storage_migration_log_path: str | Path | None = None,
    runtime_cache_source_path: str | Path | None = None,
    runtime_cache_destination_path: str | Path | None = None,
    training_media_path: str | Path | None = None,
    training_media_warn_gb: float = DEFAULT_TRAINING_MEDIA_WARN_GB,
    training_media_fail_gb: float = DEFAULT_TRAINING_MEDIA_FAIL_GB,
    project_storage_warn_gb: float = DEFAULT_PROJECT_STORAGE_WARN_GB,
    project_storage_fail_gb: float = DEFAULT_PROJECT_STORAGE_FAIL_GB,
    now: datetime | None = None,
) -> dict[str, Any]:
    required_timeframes = required_timeframes or {"15m", "1h", "2h", "4h"}
    output_path, alerts_path = runtime_dirs(base_dir)
    checks: list[dict[str, Any]] = []
    checks.append(validate_disk_space(base_dir, warn_free_gb=warn_free_gb, fail_free_gb=fail_free_gb))
    local_training_path = Path(training_media_path) if training_media_path is not None else Path(base_dir) / DEFAULT_LOCAL_TRAINING_MEDIA_RELATIVE_PATH
    checks.append(
        validate_local_training_media(
            local_training_path,
            external_disk_path=external_disk_path or DEFAULT_EXTERNAL_DISK_PATH,
            warn_size_gb=training_media_warn_gb,
            fail_size_gb=training_media_fail_gb,
        )
    )
    checks.append(
        validate_project_storage_footprint(
            base_dir,
            warn_size_gb=project_storage_warn_gb,
            fail_size_gb=project_storage_fail_gb,
        )
    )
    if external_disk_path:
        checks.append(
            validate_external_disk(
                external_disk_path,
                warn_free_gb=external_warn_free_gb,
                fail_free_gb=external_fail_free_gb,
                operational_report_path=alerts_path / "runtime_backup.json",
                now=now,
            )
        )
        checks.append(
            validate_storage_migration(
                source_path=storage_migration_source_path or DEFAULT_PARALLELS_SOURCE_PATH,
                destination_path=storage_migration_destination_path or DEFAULT_PARALLELS_DESTINATION_PATH,
                log_path=storage_migration_log_path or DEFAULT_PARALLELS_MIGRATION_LOG_PATH,
                external_disk_path=external_disk_path,
                now=now,
            )
        )
        checks.append(
            validate_runtime_cache_migration(
                source_path=runtime_cache_source_path or DEFAULT_RUNTIME_CACHE_SOURCE_PATH,
                destination_path=runtime_cache_destination_path or DEFAULT_RUNTIME_CACHE_DESTINATION_PATH,
                external_disk_path=external_disk_path,
            )
        )

    heartbeat_path = alerts_path / "ma_live_heartbeat.json"
    heartbeat = read_json(heartbeat_path)
    heartbeat_status, hb_status = heartbeat_check(
        heartbeat_path,
        heartbeat,
        now=now,
        running_warn_minutes=running_warn_minutes,
        running_fail_minutes=running_fail_minutes,
    )
    checks.append(heartbeat_status)
    freshness_max_age_minutes = max_age_minutes
    if hb_status == "RUNNING" and heartbeat_status.get("status") == "OK":
        freshness_max_age_minutes += float(heartbeat_status.get("running_minutes") or 0.0)

    use_heartbeat_paths_only = bool(heartbeat) and hb_status in {"SUCCESS", "NO_SCAN"}
    scan_path = heartbeat_artifact_path(heartbeat, "scan_path")
    confluence_path = heartbeat_artifact_path(heartbeat, "confluence_path")
    options_path = heartbeat_artifact_path(heartbeat, "options_path")
    if not use_heartbeat_paths_only:
        scan_path = scan_path or latest_output_file("ma_live_strategy_*.csv", output_path=output_path)
        confluence_path = confluence_path or latest_output_file("ma_confluence_*.csv", output_path=output_path)
        options_path = options_path or latest_output_file("options_candidates_*.csv", output_path=output_path)
    checks.append(freshness_check("live_scan_freshness", scan_path, max_age_minutes=freshness_max_age_minutes, now=now))
    checks.append(freshness_check("confluence_freshness", confluence_path, max_age_minutes=freshness_max_age_minutes, now=now))

    scan_df = read_csv(scan_path)
    if scan_df.empty:
        checks.append(check("live_scan_rows", "FAIL", "Live scan is empty or unreadable"))
    else:
        checks.append(check("live_scan_rows", "OK", f"{len(scan_df)} live scan rows", rows=len(scan_df)))
        if "tf" not in scan_df.columns:
            checks.append(check("timeframe_coverage", "FAIL", "Live scan has no tf column"))
        else:
            present = {normalize_tf(value) for value in scan_df["tf"].dropna().unique().tolist()}
            missing = sorted(required_timeframes - present)
            status = "OK" if not missing else "FAIL"
            detail = "All required live timeframes present" if not missing else f"Missing timeframes: {', '.join(missing)}"
            checks.append(check("timeframe_coverage", status, detail, present=sorted(present), missing=missing))

    confluence_df = read_csv(confluence_path)
    if confluence_df.empty:
        checks.append(check("confluence_rows", "FAIL", "Confluence file is empty or unreadable"))
    else:
        missing_cols = sorted(REQUIRED_CONFLUENCE_COLUMNS - set(confluence_df.columns))
        checks.append(check("confluence_rows", "OK", f"{len(confluence_df)} confluence rows", rows=len(confluence_df)))
        checks.append(
            check(
                "higher_timeframe_confluence",
                "OK" if not missing_cols else "FAIL",
                "2h/4h confluence columns present" if not missing_cols else f"Missing columns: {', '.join(missing_cols)}",
                missing_columns=missing_cols,
            )
        )

    brief_path = alerts_path / "roxy_ai_brief.json"
    checks.append(validate_ai_brief_report(brief_path))
    checks.append(validate_alert_quality_report(alerts_path / "alert_quality.json", now=now))

    if options_path is None:
        options_summary = read_json(alerts_path / "options_summary.json")
        if options_summary:
            count = int(options_summary.get("candidate_count", 0) or 0)
            checks.append(check("options_candidates", "OK", f"{count} options candidate(s) in latest summary", rows=count))
        else:
            checks.append(check("options_candidates", "WARN", "Options candidates file not found"))
    else:
        options_df = read_csv(options_path)
        checks.append(check("options_candidates", "OK" if not options_df.empty else "WARN", f"{len(options_df)} options rows", path=str(options_path), rows=len(options_df)))

    if skip_chart_fetch:
        checks.append(check("chart_indicators", "WARN", "Chart fetch skipped"))
    else:
        symbol, market = choose_chart_symbol(scan_df, chart_symbol)
        checks.append(validate_chart(symbol, market, chart_timeframe))
    checks.append(validate_chart_health_report(alerts_path / "chart_realtime_health.json", now=now))

    checks.append(validate_salto_integration())

    if app_url:
        checks.append(validate_app_url(app_url))

    maintenance_report_path = alerts_path / "output_maintenance.json"
    checks.append(validate_output_maintenance_report(maintenance_report_path, max_age_hours=maintenance_max_age_hours, now=now))
    runtime_backup_report_path = alerts_path / "runtime_backup.json"
    checks.append(validate_runtime_backup_report(runtime_backup_report_path, now=now))
    checks.append(validate_notification_delivery(alerts_path))
    checks.append(validate_operational_logs(base_dir=base_dir, now=now))

    if skip_service_check:
        checks.append(check("live_service_24h", "WARN", "LaunchAgent check skipped"))
        checks.append(check("streamlit_service_24h", "WARN", "LaunchAgent check skipped"))
        checks.append(check("daily_service", "WARN", "LaunchAgent check skipped"))
        checks.append(check("health_watchdog_service", "WARN", "LaunchAgent check skipped"))
        checks.append(check("output_maintenance_service", "WARN", "LaunchAgent check skipped"))
        checks.append(check("runtime_backup_service", "WARN", "LaunchAgent check skipped"))
    else:
        checks.append(validate_live_service(required_timeframes))
        checks.append(validate_streamlit_service())
        checks.append(validate_daily_service())
        checks.append(validate_health_watchdog_service())
        checks.append(validate_output_maintenance_service())
        checks.append(validate_runtime_backup_service())

    status = overall_status(checks)
    report = {
        "generated_at": (now or utc_now()).isoformat(),
        "status": status,
        "ok": status == "OK",
        "checks": checks,
        "paths": {
            "scan": str(scan_path) if scan_path else None,
            "confluence": str(confluence_path) if confluence_path else None,
            "options": str(options_path) if options_path else None,
            "heartbeat": str(heartbeat_path),
            "brief": str(brief_path),
            "alert_quality": str(alerts_path / "alert_quality.json"),
            "output_maintenance": str(maintenance_report_path),
            "runtime_backup": str(runtime_backup_report_path),
        },
    }
    report["operational_summary"] = build_operational_summary(
        report,
        alert_quality_report=read_json(alerts_path / "alert_quality.json"),
    )
    return report


def build_operational_summary(
    report: dict[str, Any],
    *,
    alert_quality_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = str(report.get("status") or "UNKNOWN").upper()
    issue = top_health_issue(report)
    if status == "FAIL":
        return {
            "mode": "SYSTEM_FAIL",
            "label": "Sistema falla",
            "tone": "avoid",
            "detail": f"{issue.get('name')}: {issue.get('detail')}" if issue else "Health FAIL",
            "system_status": status,
            "market_state": "UNKNOWN",
        }
    if status == "WARN":
        return {
            "mode": "SYSTEM_WARN",
            "label": "Sistema revisar",
            "tone": "watch",
            "detail": f"{issue.get('name')}: {issue.get('detail')}" if issue else "Health WARN",
            "system_status": status,
            "market_state": "UNKNOWN",
        }

    quality = alert_quality_report or {}
    summary = quality.get("summary") if isinstance(quality.get("summary"), dict) else {}
    entry = quality.get("entry") if isinstance(quality.get("entry"), dict) else {}
    market_state = str(summary.get("state") or entry.get("state") or "UNKNOWN").upper()
    ready = int(summary.get("latest_notifications_ready") or entry.get("notifications_ready") or 0)
    total = int(summary.get("latest_total_opportunities") or entry.get("total_opportunities") or 0)
    diagnostic_label = str(summary.get("diagnostic_label") or "")
    diagnostic_detail = str(summary.get("diagnostic_detail") or summary.get("latest_top_blocker") or entry.get("top_blocker") or "")
    diagnostic_severity = str(summary.get("diagnostic_severity") or "OK").upper()
    blocker_category = str(summary.get("blocker_category") or "")
    recommended_action = str(summary.get("recommended_action") or "")
    blocker_streak = int(summary.get("latest_top_blocker_streak") or 0)

    if ready > 0 or market_state == "READY":
        mode = "READY_TO_REVIEW"
        label = "Alertas listas"
        tone = "buy"
        detail = f"{ready}/{total} listas"
    elif market_state in {"BLOCKED_DATA", "BLOCKED_REALTIME"}:
        mode = "DATA_BLOCKED"
        label = "Datos bloquean"
        tone = "avoid"
        detail = diagnostic_detail or market_state
    elif market_state == "NO_SETUPS":
        mode = "MARKET_NO_SETUPS"
        label = "Sin setups"
        tone = "neutral"
        detail = "Sistema OK; mercado sin setups"
    elif market_state == "WAITING":
        mode = "MARKET_WAITING"
        label = "Mercado espera"
        tone = "watch"
        detail = diagnostic_label or "Sistema OK; esperando entrada"
        if blocker_streak and f"x{blocker_streak}" not in detail:
            detail += f" | bloqueador x{blocker_streak}"
        if diagnostic_detail and diagnostic_detail not in detail:
            detail += f" | {diagnostic_detail}"
        if recommended_action and recommended_action not in detail:
            detail += f" | {recommended_action}"
    else:
        mode = "SYSTEM_OK"
        label = "Sistema OK"
        tone = "buy"
        detail = "Pipeline realtime operativo"

    return {
        "mode": mode,
        "label": label,
        "tone": tone,
        "detail": detail,
        "system_status": status,
        "market_state": market_state,
        "notifications_ready": ready,
        "total_opportunities": total,
        "diagnostic_severity": diagnostic_severity,
        "diagnostic_label": diagnostic_label,
        "diagnostic_detail": diagnostic_detail,
        "blocker_category": blocker_category,
        "recommended_action": recommended_action,
        "blocker_streak": blocker_streak,
    }


def render_text_report(report: dict[str, Any]) -> str:
    lines = [
        f"Roxy realtime check: {report.get('status', '-')}",
        f"Generated: {report.get('generated_at', '-')}",
    ]
    operational = report.get("operational_summary") if isinstance(report.get("operational_summary"), dict) else {}
    if operational:
        lines.append(
            "Operational: "
            f"{operational.get('label', '-')} | {operational.get('mode', '-')} | {operational.get('detail', '-')}"
        )
    stability = report.get("stability_summary") if isinstance(report.get("stability_summary"), dict) else {}
    if stability:
        ok_rate = stability.get("ok_rate")
        ok_pct = f"{float(ok_rate) * 100:.1f}%" if ok_rate is not None else "-"
        recovery_detail = ""
        incident_free = stability.get("incident_free_minutes")
        if incident_free is not None:
            recovery_detail = f" | recovered {float(incident_free):.1f}m"
        dominant_issue = stability.get("dominant_issue") if isinstance(stability.get("dominant_issue"), dict) else {}
        issue_detail = ""
        if dominant_issue.get("name"):
            current_streak_status = str(stability.get("current_streak_status") or "").upper()
            issue_label = "hist issue" if current_streak_status == "OK" else "top issue"
            issue_detail = f" | {issue_label} {dominant_issue.get('name')} x{dominant_issue.get('count', 0)}"
        lines.append(
            "Stability: "
            f"OK {ok_pct} over {stability.get('sample_size', 0)} checks | "
            f"streak {stability.get('current_streak_status', '-')} x{stability.get('current_streak_count', 0)}"
            f"{recovery_detail}{issue_detail}"
        )
    lines.append("")
    for item in report.get("checks") or []:
        lines.append(f"- {item.get('status', '-')}: {item.get('name', '-')} | {item.get('detail', '-')}")
    return "\n".join(lines).rstrip() + "\n"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def write_report(report: dict[str, Any], *, json_path: str | Path, text_path: str | Path) -> tuple[Path, Path]:
    json_file = Path(json_path)
    text_file = Path(text_path)
    json_file.parent.mkdir(parents=True, exist_ok=True)
    text_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(json.dumps(json_safe(report), indent=2, sort_keys=True))
    text_file.write_text(render_text_report(report))
    return json_file, text_file


def top_health_issue(report: dict[str, Any]) -> dict[str, Any]:
    checks = report.get("checks") or []
    return next(
        (
            item
            for item in checks
            if str(item.get("status") or "").upper() in {"FAIL", "WARN"}
        ),
        {},
    )


def health_history_entry(report: dict[str, Any]) -> dict[str, Any]:
    checks = report.get("checks") or []
    status_counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    named_statuses: dict[str, str] = {}
    for item in checks:
        name = str(item.get("name") or "")
        status = str(item.get("status") or "").upper()
        if status in status_counts:
            status_counts[status] += 1
        if name:
            named_statuses[name] = status or "UNKNOWN"
    issue = top_health_issue(report)
    top_issue = {
        "name": issue.get("name"),
        "status": issue.get("status"),
        "detail": issue.get("detail"),
    } if issue else {}
    operational = report.get("operational_summary") if isinstance(report.get("operational_summary"), dict) else {}
    return {
        "generated_at": report.get("generated_at") or utc_now().isoformat(),
        "status": str(report.get("status") or "UNKNOWN").upper(),
        "ok": str(report.get("status") or "").upper() == "OK",
        "operational_mode": operational.get("mode"),
        "operational_label": operational.get("label"),
        "market_state": operational.get("market_state"),
        "check_count": len(checks),
        "ok_count": status_counts["OK"],
        "warn_count": status_counts["WARN"],
        "fail_count": status_counts["FAIL"],
        "top_issue": top_issue,
        "checks": named_statuses,
    }


def read_health_history_entries(history_path: str | Path, *, limit: int = DEFAULT_HEALTH_HISTORY_MAX_ENTRIES) -> list[dict[str, Any]]:
    history_file = Path(history_path)
    if not history_file.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = history_file.read_text(errors="replace").splitlines()
    except Exception:
        return []
    for line in lines[-max(1, int(limit)) :]:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def summarize_health_history_entries(entries: list[dict[str, Any]], *, limit: int = 100) -> dict[str, Any]:
    rows = list(entries or [])[-max(1, int(limit)) :]
    if not rows:
        return {
            "sample_size": 0,
            "status": "UNKNOWN",
            "ok_rate": None,
            "warn_rate": None,
            "fail_rate": None,
            "current_streak_status": "UNKNOWN",
            "current_streak_count": 0,
            "last_incident_at": "",
            "last_issue": {},
        }
    status_counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    for row in rows:
        status = str(row.get("status") or "").upper()
        if status in status_counts:
            status_counts[status] += 1
    total = len(rows)
    latest_status = str(rows[-1].get("status") or "UNKNOWN").upper()
    latest_at = parse_utc_datetime(rows[-1].get("generated_at"))
    streak_count = 0
    streak_started_at = ""
    for row in reversed(rows):
        if str(row.get("status") or "").upper() == latest_status:
            streak_count += 1
            streak_started_at = str(row.get("generated_at") or "")
        else:
            break
    last_incident = next((row for row in reversed(rows) if str(row.get("status") or "").upper() in {"WARN", "FAIL"}), {})
    last_issue = last_incident.get("top_issue") if isinstance(last_incident.get("top_issue"), dict) else {}
    last_incident_at = str(last_incident.get("generated_at") or "")
    last_incident_dt = parse_utc_datetime(last_incident_at)
    streak_started_dt = parse_utc_datetime(streak_started_at)
    incident_issue_counts = Counter(
        str((row.get("top_issue") or {}).get("name") or "unknown")
        for row in rows
        if str(row.get("status") or "").upper() in {"WARN", "FAIL"} and isinstance(row.get("top_issue"), dict)
    )
    dominant_issue_name = ""
    dominant_issue_count = 0
    if incident_issue_counts:
        dominant_issue_name, dominant_issue_count = incident_issue_counts.most_common(1)[0]
    current_streak_minutes = None
    if latest_at is not None and streak_started_dt is not None:
        current_streak_minutes = round(max(0.0, (latest_at - streak_started_dt).total_seconds() / 60.0), 1)
    incident_free_minutes = None
    if latest_status == "OK" and latest_at is not None and last_incident_dt is not None:
        incident_free_minutes = round(max(0.0, (latest_at - last_incident_dt).total_seconds() / 60.0), 1)
    return {
        "sample_size": total,
        "status": latest_status,
        "ok_count": status_counts["OK"],
        "warn_count": status_counts["WARN"],
        "fail_count": status_counts["FAIL"],
        "ok_rate": round(status_counts["OK"] / total, 4),
        "warn_rate": round(status_counts["WARN"] / total, 4),
        "fail_rate": round(status_counts["FAIL"] / total, 4),
        "current_streak_status": latest_status,
        "current_streak_count": streak_count,
        "current_streak_started_at": streak_started_at,
        "current_streak_minutes": current_streak_minutes,
        "incident_free_minutes": incident_free_minutes,
        "last_incident_at": last_incident_at,
        "last_issue": last_issue or {},
        "dominant_issue": {"name": dominant_issue_name, "count": dominant_issue_count} if dominant_issue_name else {},
    }


def append_health_history(
    report: dict[str, Any],
    *,
    history_path: str | Path = DEFAULT_HEALTH_HISTORY_PATH,
    max_entries: int = DEFAULT_HEALTH_HISTORY_MAX_ENTRIES,
) -> tuple[Path, int]:
    history_file = Path(history_path)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    max_entries = max(1, int(max_entries))
    line = json.dumps(json_safe(health_history_entry(report)), sort_keys=True)
    existing = history_file.read_text(errors="replace").splitlines() if history_file.exists() else []
    lines = [item for item in existing if item.strip()]
    lines.append(line)
    lines = lines[-max_entries:]
    history_file.write_text("\n".join(lines) + "\n")
    return history_file, len(lines)


def ensure_runtime_backup_daemon(
    *,
    interval_hours: float = 24.0,
    poll_seconds: float = 300.0,
    stale_minutes: float = 15.0,
) -> dict[str, Any]:
    try:
        from tools import runtime_backup_screen

        return runtime_backup_screen.ensure(
            interval_hours=interval_hours,
            poll_seconds=poll_seconds,
            stale_minutes=stale_minutes,
        )
    except Exception as exc:
        return {"action": "error", "error": f"{type(exc).__name__}: {exc}"}


def ensure_runtime_backup_report(
    *,
    base_dir: str | Path,
    target_dir: str | Path | None,
    report_path: str | Path,
    text_path: str | Path | None = None,
) -> dict[str, Any]:
    try:
        from tools import runtime_backup

        target = Path(target_dir) if target_dir else runtime_backup.DEFAULT_TARGET_DIR
        result = runtime_backup.create_runtime_backup(
            base_dir=base_dir,
            target_dir=target,
            report_path=report_path,
            text_path=text_path or Path(report_path).with_suffix(".txt"),
        )
        return {
            "action": "regenerated",
            "ok": str(result.get("status") or "").upper() == "OK",
            "status": result.get("status"),
            "archive_path": result.get("archive_path"),
            "archive_exists": result.get("archive_exists"),
            "archive_size_bytes": result.get("archive_size_bytes"),
            "archive_verified": result.get("archive_verified"),
            "archive_member_count": result.get("archive_member_count"),
            "archive_verified_paths": result.get("archive_verified_paths"),
            "archive_missing_verified_paths": result.get("archive_missing_verified_paths"),
            "removed_count": result.get("removed_count"),
            "report_path": str(report_path),
            "target_dir": str(target),
        }
    except Exception as exc:
        return {"action": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}", "report_path": str(report_path)}


def ensure_core_launchagents() -> dict[str, Any]:
    try:
        from tools.launchd_recovery import ensure_core_launch_agents

        return ensure_core_launch_agents()
    except Exception as exc:
        return {"status": "WARN", "error": f"{type(exc).__name__}: {exc}"}


def ensure_chart_health_report(
    *,
    report_path: str | Path,
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
) -> dict[str, Any]:
    try:
        from chart_health import summarize_chart_health
        from tools import chart_realtime_health

        selected_symbols = symbols or list(chart_realtime_health.DEFAULT_STOCK_SYMBOLS + chart_realtime_health.DEFAULT_CRYPTO_SYMBOLS)
        selected_timeframes = timeframes or list(chart_realtime_health.DEFAULT_TIMEFRAMES)
        rows = chart_realtime_health.collect_chart_health(symbols=selected_symbols, timeframes=selected_timeframes)
        path = chart_realtime_health.write_chart_health_report(rows, report_path)
        summary = summarize_chart_health(rows)
        return {
            "action": "regenerated",
            "ok": summary.get("status") != "FAIL",
            "status": summary.get("status"),
            "checked_count": summary.get("checked_count"),
            "fail_count": summary.get("fail_count"),
            "warn_count": summary.get("warn_count"),
            "report_path": str(path),
        }
    except Exception as exc:
        return {"action": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}", "report_path": str(report_path)}


def ensure_output_maintenance_report(
    *,
    output_path: str | Path,
    alerts_path: str | Path,
    report_path: str | Path,
    text_path: str | Path | None = None,
    log_dirs: list[str | Path] | None = None,
    output_archive_dir: str | Path | None = None,
) -> dict[str, Any]:
    try:
        from tools import output_maintenance

        archive_dir = output_archive_dir if output_archive_dir is not None else output_maintenance.default_output_archive_dir()
        result = output_maintenance.cleanup_runtime_artifacts(
            output_dir=output_path,
            alerts_path=alerts_path,
            log_dirs=log_dirs,
            output_archive_dir=archive_dir,
        )
        json_path, output_text_path = output_maintenance.write_report(
            result,
            json_path=report_path,
            text_path=text_path or Path(alerts_path) / "output_maintenance.txt",
        )
        return {
            "action": "regenerated",
            "ok": True,
            "report_path": str(json_path),
            "text_path": str(output_text_path),
            "removed_count": result.get("removed_count"),
            "output_archive_count": result.get("output_archive_count"),
            "output_archive_error_count": result.get("output_archive_error_count"),
            "output_archive_dir": result.get("output_archive_dir"),
            "trimmed_log_count": result.get("trimmed_log_count"),
            "trimmed_history_count": result.get("trimmed_history_count"),
            "removed_alert_report_count": result.get("removed_alert_report_count"),
            "removed_log_snapshot_count": result.get("removed_log_snapshot_count"),
        }
    except Exception as exc:
        return {"action": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}", "report_path": str(report_path)}


def ensure_alert_quality_report(
    *,
    brief_path: str | Path,
    report_path: str | Path,
    history_path: str | Path,
) -> dict[str, Any]:
    try:
        import alert_quality

        report = alert_quality.update_from_brief_file(
            brief_path=Path(brief_path),
            report_path=Path(report_path),
            history_path=Path(history_path),
        )
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        return {
            "action": "regenerated",
            "ok": str(report.get("status") or "").upper() != "FAIL",
            "status": report.get("status"),
            "state": summary.get("state"),
            "waiting_streak": summary.get("waiting_streak"),
            "diagnostic_label": summary.get("diagnostic_label"),
            "report_path": str(report_path),
            "history_path": str(history_path),
        }
    except Exception as exc:
        return {"action": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}", "report_path": str(report_path)}


def ensure_ai_brief_report(
    *,
    base_dir: str | Path,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    script = BASE_DIR / "tools" / "roxy_ai_watch.py"
    _, alerts_path = runtime_dirs(Path(base_dir))
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(base_dir),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
        return {
            "action": "regenerated",
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "brief_path": str(alerts_path / "roxy_ai_brief.json"),
            "output_tail": output[-4000:],
        }
    except Exception as exc:
        return {"action": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def named_check(report: dict[str, Any], name: str) -> dict[str, Any]:
    for item in report.get("checks") or []:
        if str(item.get("name") or "") == name:
            return dict(item)
    return {}


def streamlit_app_needs_recovery(report: dict[str, Any]) -> bool:
    item = named_check(report, "streamlit_app")
    return str(item.get("status") or "").upper() == "FAIL"


def chart_health_report_needs_recovery(report: dict[str, Any]) -> bool:
    item = named_check(report, "chart_realtime_health_report")
    return str(item.get("status") or "").upper() in {"WARN", "FAIL"}


def output_maintenance_report_needs_recovery(report: dict[str, Any]) -> bool:
    item = named_check(report, "output_maintenance_report")
    return str(item.get("status") or "").upper() in {"WARN", "FAIL"}


def runtime_backup_report_needs_recovery(report: dict[str, Any]) -> bool:
    item = named_check(report, "runtime_backup_report")
    return str(item.get("status") or "").upper() in {"WARN", "FAIL"}


def alert_quality_report_needs_recovery(report: dict[str, Any]) -> bool:
    item = named_check(report, "alert_quality_report")
    return str(item.get("status") or "").upper() in {"WARN", "FAIL"}


def yfinance_cache_issues_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    item = named_check(report, "operational_logs")
    issues = item.get("yfinance_cache_issues")
    if isinstance(issues, list) and issues:
        return [dict(issue) for issue in issues if isinstance(issue, dict)]
    found: list[dict[str, Any]] = []
    for key in ("warning_issues", "critical_issues"):
        for issue in item.get(key) or []:
            if not isinstance(issue, dict):
                continue
            line = str(issue.get("line") or "")
            if YFINANCE_CACHE_ERROR_PATTERN.search(line):
                found.append(dict(issue))
    return found


def yfinance_cache_needs_recovery(report: dict[str, Any]) -> bool:
    return bool(yfinance_cache_issues_from_report(report))


def ensure_yfinance_cache_recovery(
    report: dict[str, Any] | None = None,
    *,
    cache_paths: tuple[Path, ...] = YFINANCE_CACHE_PATHS,
    restart_services: bool = True,
    rotate_logs: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    timestamp = current.strftime("%Y%m%d_%H%M%S")
    created_paths: list[str] = []
    cache_errors: list[str] = []
    for path in cache_paths:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / f".roxy_cache_probe_{os.getpid()}"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            created_paths.append(str(path))
        except Exception as exc:
            cache_errors.append(f"{path}: {type(exc).__name__}: {exc}")

    rotated_logs: list[str] = []
    issues = yfinance_cache_issues_from_report(report or {})
    paths_with_issues = {str(issue.get("path") or "") for issue in issues if issue.get("path")}
    if rotate_logs:
        for value in sorted(paths_with_issues):
            path = Path(value)
            if not path.exists() or not path.is_file():
                continue
            tail = read_log_tail(path)
            if not YFINANCE_CACHE_ERROR_PATTERN.search(tail):
                continue
            rotated = path.with_name(f"{path.name}.{timestamp}.before_yfinance_cache_recovery")
            try:
                path.replace(rotated)
                path.touch()
                rotated_logs.append(str(rotated))
            except Exception as exc:
                cache_errors.append(f"{path}: {type(exc).__name__}: {exc}")

    service_results: dict[str, Any] = {}
    if restart_services:
        try:
            from tools.launchd_recovery import restart_launch_agent

            for service_name, module_name in {
                "ma_live": "tools.ma_live_launchd",
                "streamlit": "tools.streamlit_launchd",
            }.items():
                service_results[service_name] = restart_launch_agent(module_name)
        except Exception as exc:
            cache_errors.append(f"restart: {type(exc).__name__}: {exc}")

    service_ok = all(bool(result.get("ok")) for result in service_results.values()) if service_results else True
    ok = not cache_errors and service_ok
    return {
        "action": "recovered" if ok else "error",
        "ok": ok,
        "created_cache_paths": created_paths,
        "rotated_logs": rotated_logs,
        "issue_count": len(issues),
        "services": service_results,
        "errors": cache_errors,
    }


LIVE_DATA_RECOVERY_CHECKS = {
    "heartbeat",
    "live_scan_freshness",
    "confluence_freshness",
    "live_scan_rows",
    "timeframe_coverage",
    "confluence_rows",
    "higher_timeframe_confluence",
    "ai_brief",
}


def live_data_needs_recovery(report: dict[str, Any]) -> bool:
    for name in LIVE_DATA_RECOVERY_CHECKS:
        item = named_check(report, name)
        if str(item.get("status") or "").upper() in {"WARN", "FAIL"}:
            return True
    return False


def live_data_recovery_should_wait_for_service(report: dict[str, Any]) -> bool:
    live_service = named_check(report, "live_service_24h")
    heartbeat = named_check(report, "heartbeat")
    if str(live_service.get("status") or "").upper() != "OK":
        return False
    if str(heartbeat.get("status") or "").upper() != "OK":
        return False
    detail = str(heartbeat.get("detail") or "").lower()
    return "running normally" in detail


def ensure_live_data_run(
    *,
    base_dir: str | Path = BASE_DIR,
    timeout_seconds: int = DEFAULT_LIVE_DATA_RECOVERY_TIMEOUT_SECONDS,
    stock_intervals: str = "15m,1h,2h,4h",
    crypto_timeframes: str = "15m,1h,2h,4h",
    retention_count: int = 96,
) -> dict[str, Any]:
    root = Path(base_dir)
    cmd = [
        sys.executable,
        str(root / "tools" / "ma_live.py"),
        "--once",
        "--market",
        "both",
        "--stock-intervals",
        stock_intervals,
        "--crypto-timeframes",
        crypto_timeframes,
        "--retention-count",
        str(retention_count),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=max(60, int(timeout_seconds)),
        )
        output_tail = "\n".join((result.stdout or "").splitlines()[-20:])
        error_tail = "\n".join((result.stderr or "").splitlines()[-20:])
        return {
            "action": "ran_live_scan",
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "command": " ".join(cmd),
            "stdout_tail": output_tail,
            "stderr_tail": error_tail,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "action": "timeout",
            "ok": False,
            "timeout_seconds": timeout_seconds,
            "command": " ".join(cmd),
            "stdout_tail": "\n".join((exc.stdout or "").splitlines()[-20:]) if isinstance(exc.stdout, str) else "",
            "stderr_tail": "\n".join((exc.stderr or "").splitlines()[-20:]) if isinstance(exc.stderr, str) else "",
        }
    except Exception as exc:
        return {"action": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}", "command": " ".join(cmd)}


def recover_streamlit_app(*, wait_seconds: float = 5.0, app_url: str = "http://127.0.0.1:8501") -> dict[str, Any]:
    try:
        from tools.launchd_recovery import restart_launch_agent

        result = restart_launch_agent("tools.streamlit_launchd")
    except Exception as exc:
        return {"action": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    deadline = time.time() + max(0.0, float(wait_seconds))
    ready = False
    last_error = ""
    while time.time() <= deadline:
        probe = validate_app_url(app_url, timeout=2.0, log_paths=[], max_log_age_minutes=0)
        if str(probe.get("status") or "").upper() == "OK":
            ready = True
            break
        last_error = str(probe.get("detail") or "")
        time.sleep(1.0)
    result["ready"] = ready
    result["app_url"] = app_url
    if last_error and not ready:
        result["last_probe"] = last_error
    return result


def acquire_run_lock(
    lock_path: str | Path,
    *,
    stale_minutes: float = 30.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    lock_dir = Path(lock_path)
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    metadata_path = lock_dir / "metadata.json"
    payload = {
        "pid": os.getpid(),
        "started_at": current.isoformat(),
        "lock_path": str(lock_dir),
    }
    try:
        lock_dir.mkdir(parents=True, exist_ok=False)
        metadata_path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True))
        return {"acquired": True, **payload}
    except FileExistsError:
        metadata = read_json(metadata_path)
        started_at = parse_utc_datetime(metadata.get("started_at"))
        age_minutes = None
        if started_at is not None:
            age_minutes = max(0.0, (current - started_at).total_seconds() / 60.0)
        if age_minutes is not None and age_minutes >= stale_minutes:
            shutil.rmtree(lock_dir, ignore_errors=True)
            lock_dir.mkdir(parents=True, exist_ok=False)
            metadata_path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True))
            return {"acquired": True, "stale_replaced": True, "stale_age_minutes": age_minutes, **payload}
        return {
            "acquired": False,
            "lock_path": str(lock_dir),
            "pid": metadata.get("pid"),
            "started_at": metadata.get("started_at"),
            "age_minutes": age_minutes,
            "stale_minutes": stale_minutes,
        }


def release_run_lock(lock_info: dict[str, Any] | None) -> None:
    if not lock_info or not lock_info.get("acquired"):
        return
    lock_path = lock_info.get("lock_path")
    if not lock_path:
        return
    shutil.rmtree(Path(str(lock_path)), ignore_errors=True)


def write_run_lock_status(
    lock_info: dict[str, Any] | None,
    status_path: str | Path,
    *,
    event: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    info = dict(lock_info or {})
    payload = {
        "generated_at": current.isoformat(),
        "event": event,
        "acquired": bool(info.get("acquired")),
        "lock_path": str(info.get("lock_path") or ""),
        "pid": info.get("pid"),
        "started_at": info.get("started_at"),
        "age_minutes": info.get("age_minutes"),
        "stale_minutes": info.get("stale_minutes"),
        "stale_replaced": bool(info.get("stale_replaced")),
        "stale_age_minutes": info.get("stale_age_minutes"),
    }
    if event == "released":
        payload["released_at"] = current.isoformat()
    path = Path(status_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True))
    return payload


def health_notification_message(report: dict[str, Any], previous_state: dict[str, Any] | None = None) -> str:
    status = str(report.get("status") or "").upper()
    previous_status = str((previous_state or {}).get("last_status") or "").upper()
    if status == "OK":
        if previous_status and previous_status != "OK":
            return "ROXY HEALTH OK | realtime pipeline recovered"
        return ""
    if status not in {"WARN", "FAIL"}:
        return ""
    issue = top_health_issue(report)
    name = str(issue.get("name") or "health")
    detail = str(issue.get("detail") or "check requires attention")
    return f"ROXY HEALTH {status} | {name}: {detail}"


def should_send_health_notification(
    *,
    message: str,
    state: dict[str, Any],
    now: datetime,
    cooldown_minutes: float,
) -> bool:
    if not message:
        return False
    last_message = str(state.get("last_message") or "")
    if message != last_message:
        return True
    last_event_at = parse_utc_datetime(state.get("last_sent_at")) or parse_utc_datetime(state.get("last_attempt_at"))
    if last_event_at is None:
        return True
    age_minutes = (now - last_event_at).total_seconds() / 60.0
    return age_minutes >= cooldown_minutes


def notify_health_if_needed(
    report: dict[str, Any],
    *,
    state_path: str | Path = DEFAULT_HEALTH_NOTIFY_STATE_PATH,
    cooldown_minutes: float = 30.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    state_file = Path(state_path)
    state = read_json(state_file)
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    message = health_notification_message(report, state)
    should_send = should_send_health_notification(message=message, state=state, now=current, cooldown_minutes=cooldown_minutes)

    if not should_send:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state.update(
            {
                "last_status": str(report.get("status") or ""),
                "last_checked_at": current.isoformat(),
                "last_message": message or state.get("last_message", ""),
            }
        )
        state_file.write_text(json.dumps(json_safe(state), indent=2, sort_keys=True))
        return {"sent": False, "reason": "ok" if not message else "cooldown", "message": message}

    try:
        import notifier

        result = notifier.send_notification_message(message, reason="health_watchdog", header="ROXY HEALTH")
    except Exception as exc:
        result = {"sent": False, "reason": "send_failed", "message": message, "error": str(exc)}

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_update = {
        "last_status": str(report.get("status") or ""),
        "last_checked_at": current.isoformat(),
        "last_attempt_at": current.isoformat(),
        "last_message": message,
        "last_result": result,
    }
    if bool(result.get("sent")):
        state_update["last_sent_at"] = current.isoformat()
    state.update(
        state_update
    )
    state_file.write_text(json.dumps(json_safe(state), indent=2, sort_keys=True))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Roxy realtime pipeline, data freshness, confluence, charts, and app health.")
    parser.add_argument("--base-dir", default=str(BASE_DIR))
    parser.add_argument("--max-age-minutes", type=float, default=10.0)
    parser.add_argument("--maintenance-max-age-hours", type=float, default=36.0)
    parser.add_argument("--required-timeframes", default="15m,1h,2h,4h")
    parser.add_argument("--app-url", default="")
    parser.add_argument("--chart-symbol")
    parser.add_argument("--chart-timeframe", default="1h")
    parser.add_argument("--skip-chart-fetch", action="store_true")
    parser.add_argument("--skip-service-check", action="store_true")
    parser.add_argument("--warn-free-gb", type=float, default=1.0)
    parser.add_argument("--fail-free-gb", type=float, default=0.25)
    parser.add_argument("--external-disk-path", default=str(DEFAULT_EXTERNAL_DISK_PATH))
    parser.add_argument("--external-warn-free-gb", type=float, default=100.0)
    parser.add_argument("--external-fail-free-gb", type=float, default=20.0)
    parser.add_argument("--running-warn-minutes", type=float, default=15.0)
    parser.add_argument("--running-fail-minutes", type=float, default=30.0)
    parser.add_argument("--json-path", default=str(DEFAULT_JSON_PATH))
    parser.add_argument("--text-path", default=str(DEFAULT_TEXT_PATH))
    parser.add_argument("--history-path", default=str(DEFAULT_HEALTH_HISTORY_PATH))
    parser.add_argument("--history-max-entries", type=int, default=DEFAULT_HEALTH_HISTORY_MAX_ENTRIES)
    parser.add_argument("--no-history", action="store_true", help="Do not append this run to the compact JSONL health history.")
    parser.add_argument("--lock-path", default=str(DEFAULT_LOCK_PATH))
    parser.add_argument("--lock-status-path", default=str(DEFAULT_LOCK_STATUS_PATH))
    parser.add_argument("--lock-stale-minutes", type=float, default=30.0)
    parser.add_argument("--no-lock", action="store_true", help="Allow overlapping realtime health checks.")
    parser.add_argument("--notify-health", action="store_true", help="Notify configured channels when health is WARN/FAIL or recovers.")
    parser.add_argument("--health-notify-state-path", default=str(DEFAULT_HEALTH_NOTIFY_STATE_PATH))
    parser.add_argument("--health-notify-cooldown-minutes", type=float, default=30.0)
    parser.add_argument("--ensure-runtime-backup-daemon", action="store_true", help="Start or restart the screen-based runtime backup daemon before checking health.")
    parser.add_argument("--runtime-backup-interval-hours", type=float, default=24.0)
    parser.add_argument("--runtime-backup-poll-seconds", type=float, default=300.0)
    parser.add_argument("--runtime-backup-stale-minutes", type=float, default=15.0)
    parser.add_argument("--ensure-runtime-backup-report", action="store_true", help="Create a runtime backup immediately if its report is missing, stale, or failing.")
    parser.add_argument("--ensure-core-launchagents", action="store_true", help="Reload installed core Roxy LaunchAgents when they are not loaded.")
    parser.add_argument("--ensure-storage-migration", action="store_true", help="Repair safe external-storage migration drift such as a broken Parallels symlink target.")
    parser.add_argument("--ensure-live-data", action="store_true", help="Run one live scan immediately if heartbeat or live data checks are stale or failing.")
    parser.add_argument("--live-data-recovery-timeout-seconds", type=int, default=DEFAULT_LIVE_DATA_RECOVERY_TIMEOUT_SECONDS)
    parser.add_argument("--ensure-yfinance-cache", action="store_true", help="Recreate yfinance cache directories and restart live services if recent logs show a SQLite cache open failure.")
    parser.add_argument("--ensure-streamlit-app", action="store_true", help="Restart Streamlit LaunchAgent and re-check once if the app URL is down.")
    parser.add_argument("--streamlit-recovery-wait-seconds", type=float, default=5.0)
    parser.add_argument("--ensure-chart-health-report", action="store_true", help="Regenerate chart realtime health report once if it is missing, stale, or failing.")
    parser.add_argument("--ensure-output-maintenance-report", action="store_true", help="Run output maintenance once if its report is missing, stale, or failing.")
    parser.add_argument("--ensure-alert-quality-report", action="store_true", help="Regenerate alert quality report once if it is missing, stale, or failing.")
    parser.add_argument("--no-fail", action="store_true", help="Always exit 0 after writing the report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lock_info = None
    try:
        if not args.no_lock:
            lock_info = acquire_run_lock(args.lock_path, stale_minutes=args.lock_stale_minutes)
            if not lock_info.get("acquired"):
                write_run_lock_status(lock_info, args.lock_status_path, event="blocked")
                print(
                    "Roxy realtime check: SKIPPED "
                    f"active lock {lock_info.get('lock_path')} "
                    f"pid={lock_info.get('pid') or '-'} age={lock_info.get('age_minutes') or '-'}m"
                )
                return
            write_run_lock_status(lock_info, args.lock_status_path, event="acquired")
        required_timeframes = {item.strip().lower() for item in args.required_timeframes.split(",") if item.strip()}
        backup_autoheal = None
        if args.ensure_runtime_backup_daemon:
            backup_autoheal = ensure_runtime_backup_daemon(
                interval_hours=args.runtime_backup_interval_hours,
                poll_seconds=args.runtime_backup_poll_seconds,
                stale_minutes=args.runtime_backup_stale_minutes,
            )
        launchd_autoheal = ensure_core_launchagents() if args.ensure_core_launchagents else None
        report = evaluate_realtime_health(
            base_dir=Path(args.base_dir),
            max_age_minutes=args.max_age_minutes,
            maintenance_max_age_hours=args.maintenance_max_age_hours,
            required_timeframes=required_timeframes,
            app_url=args.app_url,
            chart_symbol=args.chart_symbol,
            chart_timeframe=args.chart_timeframe,
            skip_chart_fetch=args.skip_chart_fetch,
            skip_service_check=args.skip_service_check,
            warn_free_gb=args.warn_free_gb,
            fail_free_gb=args.fail_free_gb,
            running_warn_minutes=args.running_warn_minutes,
            running_fail_minutes=args.running_fail_minutes,
            external_disk_path=args.external_disk_path,
            external_warn_free_gb=args.external_warn_free_gb,
            external_fail_free_gb=args.external_fail_free_gb,
        )
        chart_health_autoheal = None
        live_data_autoheal = None
        storage_migration_autoheal = None
        if args.ensure_storage_migration and storage_migration_needs_recovery(report):
            storage_migration_autoheal = ensure_storage_migration_target(
                source_path=DEFAULT_PARALLELS_SOURCE_PATH,
                destination_path=DEFAULT_PARALLELS_DESTINATION_PATH,
                external_disk_path=args.external_disk_path,
                log_path=DEFAULT_PARALLELS_MIGRATION_LOG_PATH,
            )
            report = evaluate_realtime_health(
                base_dir=Path(args.base_dir),
                max_age_minutes=args.max_age_minutes,
                maintenance_max_age_hours=args.maintenance_max_age_hours,
                required_timeframes=required_timeframes,
                app_url=args.app_url,
                chart_symbol=args.chart_symbol,
                chart_timeframe=args.chart_timeframe,
                skip_chart_fetch=args.skip_chart_fetch,
                skip_service_check=args.skip_service_check,
                warn_free_gb=args.warn_free_gb,
                fail_free_gb=args.fail_free_gb,
                running_warn_minutes=args.running_warn_minutes,
                running_fail_minutes=args.running_fail_minutes,
                external_disk_path=args.external_disk_path,
                external_warn_free_gb=args.external_warn_free_gb,
                external_fail_free_gb=args.external_fail_free_gb,
            )
        yfinance_cache_autoheal = None
        if args.ensure_yfinance_cache and yfinance_cache_needs_recovery(report):
            yfinance_cache_autoheal = ensure_yfinance_cache_recovery(report)
            report = evaluate_realtime_health(
                base_dir=Path(args.base_dir),
                max_age_minutes=args.max_age_minutes,
                maintenance_max_age_hours=args.maintenance_max_age_hours,
                required_timeframes=required_timeframes,
                app_url=args.app_url,
                chart_symbol=args.chart_symbol,
                chart_timeframe=args.chart_timeframe,
                skip_chart_fetch=args.skip_chart_fetch,
                skip_service_check=args.skip_service_check,
                warn_free_gb=args.warn_free_gb,
                fail_free_gb=args.fail_free_gb,
                running_warn_minutes=args.running_warn_minutes,
                running_fail_minutes=args.running_fail_minutes,
                external_disk_path=args.external_disk_path,
                external_warn_free_gb=args.external_warn_free_gb,
                external_fail_free_gb=args.external_fail_free_gb,
            )
        if args.ensure_live_data and live_data_needs_recovery(report):
            if live_data_recovery_should_wait_for_service(report):
                live_data_autoheal = {
                    "action": "skipped_running_service",
                    "ok": True,
                    "detail": "Live service is already running normally; waiting for the current 24h cycle instead of launching a duplicate scan.",
                }
            else:
                live_data_autoheal = ensure_live_data_run(
                    base_dir=Path(args.base_dir),
                    timeout_seconds=args.live_data_recovery_timeout_seconds,
                    stock_intervals=args.required_timeframes,
                    crypto_timeframes=args.required_timeframes,
                )
                report = evaluate_realtime_health(
                    base_dir=Path(args.base_dir),
                    max_age_minutes=args.max_age_minutes,
                    maintenance_max_age_hours=args.maintenance_max_age_hours,
                    required_timeframes=required_timeframes,
                    app_url=args.app_url,
                    chart_symbol=args.chart_symbol,
                    chart_timeframe=args.chart_timeframe,
                    skip_chart_fetch=args.skip_chart_fetch,
                    skip_service_check=args.skip_service_check,
                    warn_free_gb=args.warn_free_gb,
                    fail_free_gb=args.fail_free_gb,
                    running_warn_minutes=args.running_warn_minutes,
                    running_fail_minutes=args.running_fail_minutes,
                    external_disk_path=args.external_disk_path,
                    external_warn_free_gb=args.external_warn_free_gb,
                    external_fail_free_gb=args.external_fail_free_gb,
                )
        if args.ensure_chart_health_report and chart_health_report_needs_recovery(report):
            _, chart_alerts_path = runtime_dirs(Path(args.base_dir))
            chart_health_autoheal = ensure_chart_health_report(
                report_path=chart_alerts_path / "chart_realtime_health.json"
            )
            report = evaluate_realtime_health(
                base_dir=Path(args.base_dir),
                max_age_minutes=args.max_age_minutes,
                maintenance_max_age_hours=args.maintenance_max_age_hours,
                required_timeframes=required_timeframes,
                app_url=args.app_url,
                chart_symbol=args.chart_symbol,
                chart_timeframe=args.chart_timeframe,
                skip_chart_fetch=args.skip_chart_fetch,
                skip_service_check=args.skip_service_check,
                warn_free_gb=args.warn_free_gb,
                fail_free_gb=args.fail_free_gb,
                running_warn_minutes=args.running_warn_minutes,
                running_fail_minutes=args.running_fail_minutes,
                external_disk_path=args.external_disk_path,
                external_warn_free_gb=args.external_warn_free_gb,
                external_fail_free_gb=args.external_fail_free_gb,
            )
        streamlit_app_autoheal = None
        output_maintenance_autoheal = None
        if args.ensure_output_maintenance_report and output_maintenance_report_needs_recovery(report):
            output_path, alerts_path = runtime_dirs(Path(args.base_dir))
            output_maintenance_autoheal = ensure_output_maintenance_report(
                output_path=output_path,
                alerts_path=alerts_path,
                report_path=alerts_path / "output_maintenance.json",
            )
            report = evaluate_realtime_health(
                base_dir=Path(args.base_dir),
                max_age_minutes=args.max_age_minutes,
                maintenance_max_age_hours=args.maintenance_max_age_hours,
                required_timeframes=required_timeframes,
                app_url=args.app_url,
                chart_symbol=args.chart_symbol,
                chart_timeframe=args.chart_timeframe,
                skip_chart_fetch=args.skip_chart_fetch,
                skip_service_check=args.skip_service_check,
                warn_free_gb=args.warn_free_gb,
                fail_free_gb=args.fail_free_gb,
                running_warn_minutes=args.running_warn_minutes,
                running_fail_minutes=args.running_fail_minutes,
                external_disk_path=args.external_disk_path,
                external_warn_free_gb=args.external_warn_free_gb,
                external_fail_free_gb=args.external_fail_free_gb,
            )
        runtime_backup_report_autoheal = None
        if args.ensure_runtime_backup_report and runtime_backup_report_needs_recovery(report):
            _, alerts_path = runtime_dirs(Path(args.base_dir))
            current_backup_report = read_json(alerts_path / "runtime_backup.json")
            runtime_backup_report_autoheal = ensure_runtime_backup_report(
                base_dir=Path(args.base_dir),
                target_dir=current_backup_report.get("target_dir"),
                report_path=alerts_path / "runtime_backup.json",
                text_path=alerts_path / "runtime_backup.txt",
            )
            report = evaluate_realtime_health(
                base_dir=Path(args.base_dir),
                max_age_minutes=args.max_age_minutes,
                maintenance_max_age_hours=args.maintenance_max_age_hours,
                required_timeframes=required_timeframes,
                app_url=args.app_url,
                chart_symbol=args.chart_symbol,
                chart_timeframe=args.chart_timeframe,
                skip_chart_fetch=args.skip_chart_fetch,
                skip_service_check=args.skip_service_check,
                warn_free_gb=args.warn_free_gb,
                fail_free_gb=args.fail_free_gb,
                running_warn_minutes=args.running_warn_minutes,
                running_fail_minutes=args.running_fail_minutes,
                external_disk_path=args.external_disk_path,
                external_warn_free_gb=args.external_warn_free_gb,
                external_fail_free_gb=args.external_fail_free_gb,
            )
        alert_quality_autoheal = None
        if args.ensure_alert_quality_report and alert_quality_report_needs_recovery(report):
            _, alerts_path = runtime_dirs(Path(args.base_dir))
            alert_quality_autoheal = ensure_alert_quality_report(
                brief_path=alerts_path / "roxy_ai_brief.json",
                report_path=alerts_path / "alert_quality.json",
                history_path=alerts_path / "alert_quality_history.jsonl",
            )
            report = evaluate_realtime_health(
                base_dir=Path(args.base_dir),
                max_age_minutes=args.max_age_minutes,
                maintenance_max_age_hours=args.maintenance_max_age_hours,
                required_timeframes=required_timeframes,
                app_url=args.app_url,
                chart_symbol=args.chart_symbol,
                chart_timeframe=args.chart_timeframe,
                skip_chart_fetch=args.skip_chart_fetch,
                skip_service_check=args.skip_service_check,
                warn_free_gb=args.warn_free_gb,
                fail_free_gb=args.fail_free_gb,
                running_warn_minutes=args.running_warn_minutes,
                running_fail_minutes=args.running_fail_minutes,
                external_disk_path=args.external_disk_path,
                external_warn_free_gb=args.external_warn_free_gb,
                external_fail_free_gb=args.external_fail_free_gb,
            )
        if args.ensure_streamlit_app and args.app_url and streamlit_app_needs_recovery(report):
            streamlit_app_autoheal = recover_streamlit_app(wait_seconds=args.streamlit_recovery_wait_seconds, app_url=args.app_url)
            report = evaluate_realtime_health(
                base_dir=Path(args.base_dir),
                max_age_minutes=args.max_age_minutes,
                maintenance_max_age_hours=args.maintenance_max_age_hours,
                required_timeframes=required_timeframes,
                app_url=args.app_url,
                chart_symbol=args.chart_symbol,
                chart_timeframe=args.chart_timeframe,
                skip_chart_fetch=args.skip_chart_fetch,
                skip_service_check=args.skip_service_check,
                warn_free_gb=args.warn_free_gb,
                fail_free_gb=args.fail_free_gb,
                running_warn_minutes=args.running_warn_minutes,
                running_fail_minutes=args.running_fail_minutes,
                external_disk_path=args.external_disk_path,
                external_warn_free_gb=args.external_warn_free_gb,
                external_fail_free_gb=args.external_fail_free_gb,
            )
        ai_brief_autoheal = None
        if args.ensure_alert_quality_report:
            write_report(report, json_path=args.json_path, text_path=args.text_path)
            _, alerts_path = runtime_dirs(Path(args.base_dir))
            ai_brief_autoheal = ensure_ai_brief_report(base_dir=Path(args.base_dir))
            alert_quality_autoheal = ensure_alert_quality_report(
                brief_path=alerts_path / "roxy_ai_brief.json",
                report_path=alerts_path / "alert_quality.json",
                history_path=alerts_path / "alert_quality_history.jsonl",
            )
            report = evaluate_realtime_health(
                base_dir=Path(args.base_dir),
                max_age_minutes=args.max_age_minutes,
                maintenance_max_age_hours=args.maintenance_max_age_hours,
                required_timeframes=required_timeframes,
                app_url=args.app_url,
                chart_symbol=args.chart_symbol,
                chart_timeframe=args.chart_timeframe,
                skip_chart_fetch=args.skip_chart_fetch,
                skip_service_check=args.skip_service_check,
                warn_free_gb=args.warn_free_gb,
                fail_free_gb=args.fail_free_gb,
                running_warn_minutes=args.running_warn_minutes,
                running_fail_minutes=args.running_fail_minutes,
                external_disk_path=args.external_disk_path,
                external_warn_free_gb=args.external_warn_free_gb,
                external_fail_free_gb=args.external_fail_free_gb,
            )
        if backup_autoheal is not None:
            report["runtime_backup_autoheal"] = json_safe(backup_autoheal)
        if launchd_autoheal is not None:
            report["launchd_autoheal"] = json_safe(launchd_autoheal)
        if streamlit_app_autoheal is not None:
            report["streamlit_app_autoheal"] = json_safe(streamlit_app_autoheal)
        if chart_health_autoheal is not None:
            report["chart_health_autoheal"] = json_safe(chart_health_autoheal)
        if live_data_autoheal is not None:
            report["live_data_autoheal"] = json_safe(live_data_autoheal)
        if storage_migration_autoheal is not None:
            report["storage_migration_autoheal"] = json_safe(storage_migration_autoheal)
        if yfinance_cache_autoheal is not None:
            report["yfinance_cache_autoheal"] = json_safe(yfinance_cache_autoheal)
        if output_maintenance_autoheal is not None:
            report["output_maintenance_autoheal"] = json_safe(output_maintenance_autoheal)
        if runtime_backup_report_autoheal is not None:
            report["runtime_backup_report_autoheal"] = json_safe(runtime_backup_report_autoheal)
        if ai_brief_autoheal is not None:
            report["ai_brief_autoheal"] = json_safe(ai_brief_autoheal)
        if alert_quality_autoheal is not None:
            report["alert_quality_autoheal"] = json_safe(alert_quality_autoheal)
        history_result = None
        if not args.no_history:
            existing_history = read_health_history_entries(args.history_path, limit=args.history_max_entries)
            report["stability_summary"] = summarize_health_history_entries([*existing_history, health_history_entry(report)])
        json_path, text_path = write_report(report, json_path=args.json_path, text_path=args.text_path)
        if not args.no_history:
            history_result = append_health_history(report, history_path=args.history_path, max_entries=args.history_max_entries)
        notify_result = None
        if args.notify_health:
            notify_result = notify_health_if_needed(
                report,
                state_path=args.health_notify_state_path,
                cooldown_minutes=args.health_notify_cooldown_minutes,
            )
        print(render_text_report(report), end="")
        print(f"JSON: {json_path}")
        print(f"Text: {text_path}")
        if history_result is not None:
            print(f"History: {history_result[0]} entries={history_result[1]}")
        if notify_result is not None:
            print(f"Notify: {notify_result.get('reason')} sent={notify_result.get('sent')}")
        if report["status"] == "FAIL" and not args.no_fail:
            raise SystemExit(1)
    finally:
        if lock_info and lock_info.get("acquired"):
            release_run_lock(lock_info)
            write_run_lock_status(lock_info, args.lock_status_path, event="released")


if __name__ == "__main__":
    main()
