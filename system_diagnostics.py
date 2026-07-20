"""Read-only operational diagnostics for the Roxy platform.

The module deliberately avoids importing Streamlit so the same checks can be
used by the UI, tests, health jobs, and future API endpoints.
"""

from __future__ import annotations

import ast
import csv
import os
import json
import plistlib
import re
import shlex
import socket
import sqlite3
import stat
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import unquote, urlparse

from roxy_trader.auth_guard import (
    AUTH_LOCK_SECONDS,
    AUTH_MAX_FAILURES,
    AUTH_WINDOW_SECONDS,
    PASSWORD_ITERATIONS,
    PASSWORD_MIN_LENGTH,
    SESSION_MAX_AGE_SECONDS_DEFAULT,
)
from roxy_trader.cache_policy import CACHE_POLICY_VERSION, cache_policy_contract, cache_policy_issues
from roxy_trader.api_budget import (
    API_BUDGET_VERSION,
    ApiUsageLedger,
    api_budget_contract,
    api_budget_issues,
    default_api_usage_path,
)
from roxy_trader.device_sync import DEVICE_SYNC_CONTRACT_VERSION, allowed_device_sync_users


@dataclass(frozen=True)
class DiagnosticCheck:
    component: str
    status: str
    detail: str
    checked_at: str
    latency_ms: float | None = None
    source: str = "local"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_http(component: str, url: str, *, timeout: float = 1.5) -> DiagnosticCheck:
    started = time.perf_counter()
    try:
        request = Request(url, headers={"User-Agent": "Roxy-Diagnostics/1.0"})
        with urlopen(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", 200))
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        if 200 <= status_code < 400:
            return DiagnosticCheck(component, "CONNECTED", f"HTTP {status_code}", _now_iso(), latency_ms, url)
        return DiagnosticCheck(component, "ERROR", f"HTTP {status_code}", _now_iso(), latency_ms, url)
    except HTTPError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return DiagnosticCheck(component, "ERROR", f"HTTP {exc.code}", _now_iso(), latency_ms, url)
    except (URLError, TimeoutError, OSError) as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        reason = getattr(exc, "reason", exc)
        return DiagnosticCheck(component, "DISCONNECTED", str(reason)[:160], _now_iso(), latency_ms, url)


def _check_tcp(component: str, url: str, *, timeout: float = 0.25) -> DiagnosticCheck:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            return DiagnosticCheck(
                component,
                "CONNECTED",
                f"TCP {host}:{port} responde; health HTTP profundo diferido fuera del render.",
                _now_iso(),
                latency_ms,
                url,
            )
    except OSError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return DiagnosticCheck(component, "DISCONNECTED", str(exc)[:160], _now_iso(), latency_ms, url)


def database_check(path: str | Path, *, deep: bool = True) -> DiagnosticCheck:
    db_path = Path(path)
    if not db_path.exists():
        return DiagnosticCheck("Base de datos", "NOT_CONFIGURED", f"No existe {db_path}", _now_iso(), source=str(db_path))
    started = time.perf_counter()
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2) as connection:
            integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0]) if deep else "deferred"
            if not deep:
                connection.execute("SELECT 1").fetchone()
            table_count = int(
                connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        size_mb = db_path.stat().st_size / (1024 * 1024)
        status = "CONNECTED" if not deep or integrity.lower() == "ok" else "ERROR"
        detail = (
            f"quick_check={integrity}; {table_count} tablas; {size_mb:.1f} MB"
            if deep
            else f"lectura=ok; {table_count} tablas; {size_mb:.1f} MB; quick_check profundo diferido"
        )
        return DiagnosticCheck("Base de datos", status, detail, _now_iso(), latency_ms, str(db_path))
    except (OSError, sqlite3.Error) as exc:
        return DiagnosticCheck("Base de datos", "ERROR", str(exc)[:200], _now_iso(), source=str(db_path))


def _configured(env: Mapping[str, str], *keys: str) -> bool:
    return all(bool(str(env.get(key, "")).strip()) for key in keys)


SERVICE_PROVIDER_ENV_PATH = Path.home() / "Library" / "Application Support" / "RoxyTrading" / ".env"
PROVIDER_DIAGNOSTIC_KEYS = {
    "ALPACA_API_KEY",
    "ALPACA_API_SECRET",
    "ALPACA_SECRET_KEY",
    "POLYGON_API_KEY",
    "POLYGON_API_TOKEN",
    "ROXY_FINVIZ_EXPORT_URL",
    "FINNHUB_KEY",
    "FINNHUB_API_KEY",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_AGENT_ID",
    "TRADINGVIEW_WEBHOOK_SECRET",
}


def effective_diagnostic_provider_env(
    process_env: Mapping[str, str] | None = None,
    *,
    service_env_path: str | Path = SERVICE_PROVIDER_ENV_PATH,
) -> tuple[dict[str, str], list[str]]:
    """Merge allowlisted service values without ever returning unrelated secrets."""
    values = {
        key: str(value)
        for key, value in dict(process_env if process_env is not None else os.environ).items()
        if key in PROVIDER_DIAGNOSTIC_KEYS and str(value).strip()
    }
    loaded: list[str] = []
    pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
    paths = [Path(service_env_path)]
    if process_env is None:
        project_root = Path(__file__).resolve().parent
        paths.extend((project_root / ".env.local", project_root / ".env"))
    for path in paths:
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = pattern.match(raw_line)
            if not match or match.group(1) not in PROVIDER_DIAGNOSTIC_KEYS or values.get(match.group(1)):
                continue
            try:
                parts = shlex.split(match.group(2).strip(), comments=True, posix=True)
            except ValueError:
                parts = []
            value = parts[0] if parts else ""
            if value:
                values[match.group(1)] = value
                loaded.append(match.group(1))
    return values, sorted(loaded)


def provider_environment_security_check(
    project_env_path: str | Path,
    *,
    service_env_path: str | Path = SERVICE_PROVIDER_ENV_PATH,
) -> DiagnosticCheck:
    """Verify provider environment files are owner-only without reading their values."""
    project_path = Path(project_env_path)
    local_path = project_path.with_name(".env.local")
    labeled_paths = [("proyecto", project_path), ("administrado", Path(service_env_path))]
    # .env.local is optional, but when present it can have precedence for local
    # provider helpers and must be held to the same owner-only contract.
    if local_path.is_file() and local_path != project_path:
        labeled_paths.insert(0, ("local", local_path))
    paths = [path for _, path in labeled_paths]
    existing = [(label, path) for label, path in labeled_paths if path.is_file()]
    if not existing:
        return DiagnosticCheck(
            "Seguridad de entorno de proveedores",
            "NOT_CONFIGURED",
            "No existen archivos .env local ni administrado.",
            _now_iso(),
            source=", ".join(str(path) for path in paths),
        )
    insecure: list[str] = []
    modes: list[str] = []
    for label, path in existing:
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except OSError:
            insecure.append(label)
            continue
        modes.append(f"{label}={mode:04o}")
        if mode & 0o077:
            insecure.append(label)
    missing = [label for label, path in labeled_paths if label != "local" and not path.is_file()]
    if insecure:
        status = "ERROR"
        detail = (
            "Archivo(s) de credenciales legibles por grupo/otros: "
            + ", ".join(insecure)
            + ". Aplicar permisos 0600."
        )
    elif missing:
        status = "WARNING"
        detail = "Archivos existentes protegidos; falta " + ", ".join(missing) + "."
    else:
        status = "CONNECTED"
        detail = "Entorno local y administrado protegidos para el propietario (0600)."
    if modes:
        detail += " Modos: " + ", ".join(modes) + "."
    return DiagnosticCheck(
        "Seguridad de entorno de proveedores",
        status,
        detail,
        _now_iso(),
        source=", ".join(str(path) for path in paths),
    )


def provider_checks(
    env: Mapping[str, str] | None = None,
    *,
    service_env_path: str | Path = SERVICE_PROVIDER_ENV_PATH,
) -> list[DiagnosticCheck]:
    values, service_loaded = effective_diagnostic_provider_env(env, service_env_path=service_env_path)
    providers = [
        (
            "Alpaca",
            bool(str(values.get("ALPACA_API_KEY", "")).strip())
            and any(bool(str(values.get(key, "")).strip()) for key in ("ALPACA_API_SECRET", "ALPACA_SECRET_KEY")),
            "precios/velas/streaming",
        ),
        (
            "Polygon",
            any(bool(str(values.get(key, "")).strip()) for key in ("POLYGON_API_KEY", "POLYGON_API_TOKEN")),
            "velas de respaldo premium",
        ),
        ("Finviz", bool(str(values.get("ROXY_FINVIZ_EXPORT_URL", "")).strip()), "screener/sectores/noticias"),
        (
            "Finnhub",
            any(bool(str(values.get(key, "")).strip()) for key in ("FINNHUB_KEY", "FINNHUB_API_KEY")),
            "perfil corporativo y logotipos de acciones",
        ),
        ("Crypto.com", True, "ticker y velas publicas; claves solo para cuenta"),
        ("CoinGecko", True, "identidad, logotipo y metadata publica de cripto"),
        # The API key is sufficient for the current conversation-token and TTS
        # flows. An agent id is optional configuration, not evidence that the
        # provider is absent; runtime authentication is reported separately.
        ("ElevenLabs", _configured(values, "ELEVENLABS_API_KEY"), "voz"),
        (
            "TradingView webhook",
            bool(str(values.get("TRADINGVIEW_WEBHOOK_SECRET", "")).strip()),
            "confirmacion externa",
        ),
    ]
    rows: list[DiagnosticCheck] = []
    for name, configured, purpose in providers:
        if name in {"Crypto.com", "CoinGecko"}:
            rows.append(DiagnosticCheck(name, "CONNECTED_PUBLIC", purpose, _now_iso(), source="public REST"))
            continue
        if configured:
            status = "CONFIGURED"
            context = "contexto efectivo del servicio" if service_loaded else "entorno del proceso"
            detail = f"Configuracion presente en {context}; {purpose}. La respuesta se valida por solicitud."
        else:
            status = "NOT_CONFIGURED"
            detail = f"Falta configuracion; {purpose}."
        rows.append(DiagnosticCheck(name, status, detail, _now_iso(), source="effective service environment"))
    return rows


def cache_check(paths: Iterable[str | Path]) -> DiagnosticCheck:
    files = 0
    total_bytes = 0
    newest_mtime = 0.0
    readable_paths = 0
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        readable_paths += 1
        candidates = path.rglob("*") if path.is_dir() else (path,)
        for candidate in candidates:
            try:
                if candidate.is_file():
                    stat = candidate.stat()
                    files += 1
                    total_bytes += stat.st_size
                    newest_mtime = max(newest_mtime, stat.st_mtime)
            except OSError:
                continue
    if not readable_paths:
        return DiagnosticCheck("Cache/estado", "NO_DATA", "No hay rutas de cache disponibles", _now_iso())
    newest = datetime.fromtimestamp(newest_mtime, timezone.utc).isoformat() if newest_mtime else "sin archivos"
    detail = f"{files} archivos; {total_bytes / (1024 * 1024):.1f} MB; ultimo cambio {newest}"
    return DiagnosticCheck("Cache/estado", "CONNECTED", detail, _now_iso(), source="filesystem")


def normalize_identity_requirement(symbol: Any, market: Any = "") -> tuple[str, str] | None:
    raw_symbol = str(symbol or "").strip().upper().replace("-", "/")
    if not raw_symbol:
        return None
    raw_market = str(market or "").strip().lower()
    resolved_market = "crypto" if raw_market == "crypto" or "/" in raw_symbol else "stock"
    normalized = raw_symbol.split("/", 1)[0] if resolved_market == "crypto" else re.sub(r"[^A-Z0-9.]", "", raw_symbol)
    return (resolved_market, normalized) if normalized else None


def operational_asset_identity_requirements(root: str | Path) -> set[tuple[str, str]]:
    """Collect assets currently visible in live scans, briefs and durable user state."""
    root_path = Path(root)
    requirements: set[tuple[str, str]] = set()

    def add(symbol: Any, market: Any = "") -> None:
        normalized = normalize_identity_requirement(symbol, market)
        if normalized:
            requirements.add(normalized)

    live_files = sorted(
        (root_path / "output").glob("ma_live_strategy_*.csv"),
        key=lambda candidate: candidate.stat().st_mtime if candidate.exists() else 0,
        reverse=True,
    )[:4]
    for path in live_files:
        try:
            with path.open(newline="", encoding="utf-8") as stream:
                for index, row in enumerate(csv.DictReader(stream)):
                    add(row.get("symbol"), row.get("market"))
                    if index >= 499:
                        break
        except (OSError, csv.Error):
            continue

    for path in (
        root_path / "alerts" / "roxy_ai_brief.json",
        root_path / "alerts" / "opportunity_sync.json",
        root_path / "data" / "roxy_watchlists.json",
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue

        def visit(value: Any) -> None:
            if isinstance(value, Mapping):
                if value.get("symbol") or value.get("ticker"):
                    add(value.get("symbol") or value.get("ticker"), value.get("market"))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload)
    return requirements


def asset_identity_cache_check(
    path: str | Path,
    required_assets: Iterable[tuple[str, str]] | None = None,
) -> DiagnosticCheck:
    cache_path = Path(path)
    if not cache_path.is_dir():
        return DiagnosticCheck(
            "Identidad/logotipos",
            "NO_DATA",
            "Cache de identidad no creado; se generara al abrir un activo.",
            _now_iso(),
            source=str(cache_path),
        )
    valid = 0
    missing_blob = 0
    source_counts: dict[str, int] = {}
    cached_assets: set[tuple[str, str]] = set()
    newest = 0.0
    for metadata_path in cache_path.glob("*.json"):
        try:
            payload = json.loads(metadata_path.read_text())
            logo_file = cache_path / str(payload.get("logo_file") or "")
            if not logo_file.is_file():
                missing_blob += 1
                continue
            valid += 1
            normalized = normalize_identity_requirement(payload.get("symbol"), payload.get("market"))
            if normalized:
                cached_assets.add(normalized)
            source = str(payload.get("logo_source") or "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
            newest = max(newest, metadata_path.stat().st_mtime, logo_file.stat().st_mtime)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            missing_blob += 1
    required = {item for item in (required_assets or []) if item and len(item) == 2}
    missing_assets = sorted(required - cached_assets)
    coverage_detail = (
        f"; cobertura operativa {len(required) - len(missing_assets)}/{len(required)}"
        if required
        else "; cobertura operativa sin activos declarados"
    )
    if missing_assets:
        coverage_detail += "; faltan " + ", ".join(f"{market}:{symbol}" for market, symbol in missing_assets[:8])
    if not valid:
        status = "ERROR" if missing_blob else "NO_DATA"
        detail = f"0 identidades validas; inconsistencias {missing_blob}{coverage_detail}."
    else:
        status = "WARNING" if missing_blob or missing_assets else "CONNECTED"
        sources = ", ".join(f"{name}={count}" for name, count in sorted(source_counts.items()))
        newest_text = datetime.fromtimestamp(newest, timezone.utc).isoformat() if newest else "-"
        detail = (
            f"{valid} logos cacheados; inconsistencias {missing_blob}{coverage_detail}; "
            f"fuentes {sources}; actualizado {newest_text}"
        )
    return DiagnosticCheck("Identidad/logotipos", status, detail, _now_iso(), source=str(cache_path))


def operational_state_check(path: str | Path) -> DiagnosticCheck:
    state_path = Path(path)
    if not state_path.is_file():
        return DiagnosticCheck(
            "Watchlists/alertas",
            "NO_DATA",
            "Estado durable aun no creado; se inicializa con la primera lista o alerta.",
            _now_iso(),
            source=str(state_path),
        )
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        users = payload.get("users")
        if not isinstance(users, dict):
            raise ValueError("users no es un objeto")
        list_count = 0
        asset_count = 0
        active_alert_count = 0
        triggered_alert_count = 0
        archived_opportunity_count = 0
        for user in users.values():
            if not isinstance(user, dict):
                continue
            lists = user.get("lists") if isinstance(user.get("lists"), dict) else {}
            list_count += len(lists)
            for watchlist in lists.values():
                if isinstance(watchlist, dict) and isinstance(watchlist.get("items"), list):
                    asset_count += sum(isinstance(item, dict) and bool(item.get("symbol")) for item in watchlist["items"])
            alerts = user.get("alerts") if isinstance(user.get("alerts"), list) else []
            active_alert_count += sum(
                isinstance(item, dict) and item.get("status") in {"Activa", "Activada"} for item in alerts
            )
            triggered_alert_count += sum(
                isinstance(item, dict) and item.get("status") == "Activada" for item in alerts
            )
            archived_opportunity_count += sum(
                isinstance(item, dict) for item in user.get("opportunity_archive", [])
            )
        detail = (
            f"schema={payload.get('schema_version', '-')}; usuarios {len(users)}; listas {list_count}; "
            f"activos {asset_count}; alertas activas {active_alert_count}; activadas {triggered_alert_count}; "
            f"oportunidades archivadas {archived_opportunity_count}"
        )
        return DiagnosticCheck("Watchlists/alertas", "CONNECTED", detail, _now_iso(), source=str(state_path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return DiagnosticCheck(
            "Watchlists/alertas", "ERROR", f"Estado invalido: {str(exc)[:160]}", _now_iso(), source=str(state_path)
        )


def price_alert_monitor_check(
    path: str | Path,
    *,
    now: datetime | None = None,
    stale_after_minutes: float = 3.0,
) -> DiagnosticCheck:
    report_path = Path(path)
    if not report_path.is_file():
        return DiagnosticCheck(
            "Monitor de alertas",
            "NOT_CONFIGURED",
            "No existe reporte del monitor background; las reglas fuera de pantalla no estan verificadas.",
            _now_iso(),
            source=str(report_path),
        )
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("el reporte no es un objeto")
        generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        generated = generated.astimezone(timezone.utc)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return DiagnosticCheck(
            "Monitor de alertas",
            "ERROR",
            f"Reporte invalido: {str(exc)[:160]}",
            _now_iso(),
            source=str(report_path),
        )
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_minutes = max(0.0, (current - generated).total_seconds() / 60.0)
    report_status = str(payload.get("status") or "UNKNOWN").upper()
    contract = str(payload.get("contract_version") or "")
    if contract != "roxy-durable-alert-monitor/2.0.0":
        status = "ERROR"
    elif age_minutes > float(stale_after_minutes):
        status = "ERROR"
    elif report_status == "WARNING":
        status = "WARNING"
    elif report_status in {"OK", "NO_DATA"}:
        status = "CONNECTED"
    else:
        status = "ERROR"
    detail = (
        f"contrato={contract or '-'}; estado={report_status}; antiguedad {age_minutes:.1f} min; "
        f"alertas activas {int(payload.get('active_alerts') or 0)}; evaluadas {int(payload.get('evaluated') or 0)}; "
        f"bloqueadas {int(payload.get('blocked') or 0)}; activadas {int(payload.get('triggered') or 0)}; "
        f"expiradas {int(payload.get('expired') or 0)}; notificaciones {int(payload.get('notifications') or 0)}; "
        f"entregas pendientes {int(payload.get('notification_pending') or 0)}; "
        f"fallos permanentes {int(payload.get('permanent_delivery_failures') or 0)}."
    )
    if age_minutes > float(stale_after_minutes):
        detail += " El proceso background esta vencido."
    detail += " Cubre precio, cruces EMA y volumen relativo con datos verificables y entrega durable reintentable."
    return DiagnosticCheck("Monitor de alertas", status, detail, _now_iso(), source=str(report_path))


def opportunity_sync_check(
    path: str | Path,
    *,
    now: datetime | None = None,
    stale_after_minutes: float = 15.0,
) -> DiagnosticCheck:
    report_path = Path(path)
    if not report_path.is_file():
        return DiagnosticCheck(
            "Sincronizacion de oportunidades",
            "NOT_CONFIGURED",
            "No existe evidencia de sincronizacion autonoma con las watchlists.",
            _now_iso(),
            source=str(report_path),
        )
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("el reporte no es un objeto")
        generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        generated = generated.astimezone(timezone.utc)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return DiagnosticCheck(
            "Sincronizacion de oportunidades",
            "ERROR",
            f"Reporte invalido: {str(exc)[:160]}",
            _now_iso(),
            source=str(report_path),
        )
    age_minutes = max(0.0, (((now or datetime.now(timezone.utc)).astimezone(timezone.utc)) - generated).total_seconds() / 60.0)
    contract = str(payload.get("contract_version") or payload.get("contract") or "")
    report_status = str(payload.get("status") or "UNKNOWN").upper()
    if contract != "roxy-opportunity-sync/1.0.0" or age_minutes > stale_after_minutes:
        status = "ERROR"
    elif report_status == "WARNING":
        status = "WARNING"
    elif report_status == "OK":
        status = "CONNECTED"
    else:
        status = "ERROR"
    users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
    detail = (
        f"contrato={contract or '-'}; estado={report_status}; antiguedad {age_minutes:.1f} min; "
        f"candidatas {int(payload.get('candidate_count') or 0)}; listas para entrada "
        f"{int(payload.get('trade_ready_count') or 0)}; usuarios {len(users)}."
    )
    if age_minutes > stale_after_minutes:
        detail += " La sincronizacion quedo vencida."
    return DiagnosticCheck("Sincronizacion de oportunidades", status, detail, _now_iso(), source=str(report_path))


@lru_cache(maxsize=8)
def _frontend_source_ast(source_name: str, modified_ns: int, size_bytes: int) -> tuple[str, ast.Module]:
    del modified_ns, size_bytes
    source = Path(source_name).read_text(encoding="utf-8")
    return source, ast.parse(source, filename=source_name)


@lru_cache(maxsize=8)
def _ui_control_contract_scan(source_name: str, modified_ns: int, size_bytes: int) -> tuple[int, int, tuple[int, ...], int, int]:
    source, tree = _frontend_source_ast(source_name, modified_ns, size_bytes)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    buttons: list[ast.Call] = []
    link_buttons = 0
    orphan_lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in {"link_button", "page_link"}:
            link_buttons += 1
            continue
        if node.func.attr != "button":
            continue
        buttons.append(node)
        callbacks = [keyword for keyword in node.keywords if keyword.arg == "on_click"]
        disabled = [keyword for keyword in node.keywords if keyword.arg == "disabled"]
        parent = parents.get(node)
        if callbacks or disabled or not isinstance(parent, ast.Expr):
            continue
        orphan_lines.append(int(getattr(node, "lineno", 0)))

    placeholder_hrefs = source.count('href="#"') + source.count("href='#'")
    javascript_hrefs = source.lower().count('href="javascript:') + source.lower().count("href='javascript:")
    return len(buttons), link_buttons, tuple(orphan_lines), placeholder_hrefs, javascript_hrefs


def ui_control_contract_check(path: str | Path) -> DiagnosticCheck:
    """Detect Streamlit buttons that render without a handler or explicit disabled state."""
    source_path = Path(path)
    try:
        metadata = source_path.stat()
        button_count, link_buttons, orphan_lines, placeholder_hrefs, javascript_hrefs = _ui_control_contract_scan(
            str(source_path.resolve()), metadata.st_mtime_ns, metadata.st_size
        )
    except (OSError, SyntaxError, UnicodeError) as exc:
        return DiagnosticCheck(
            "Controles de interfaz",
            "ERROR",
            f"No se pudo auditar el frontend: {str(exc)[:160]}",
            _now_iso(),
            source=str(source_path),
        )
    issue_count = len(orphan_lines) + placeholder_hrefs + javascript_hrefs
    status = "CONNECTED" if issue_count == 0 else "WARNING"
    detail = (
        f"botones {button_count}; enlaces de componente {link_buttons}; acciones huerfanas {len(orphan_lines)}; "
        f"href placeholder {placeholder_hrefs}; href javascript {javascript_hrefs}."
    )
    if orphan_lines:
        detail += " Lineas: " + ", ".join(str(line) for line in orphan_lines[:8]) + "."
    return DiagnosticCheck("Controles de interfaz", status, detail, _now_iso(), source=str(source_path))


def visual_strategy_engine_check(path: str | Path) -> DiagnosticCheck:
    """Verify that the central visual detector exposes the required auditable families."""
    source_path = Path(path)
    required = {
        "UPTREND",
        "DOWNTREND",
        "EMA_BULLISH_CROSS",
        "EMA_BEARISH_CROSS",
        "BREAKOUT",
        "BREAKDOWN",
        "BULLISH_RETEST",
        "BEARISH_RETEST",
        "CONSOLIDATION",
        "SYMMETRIC_TRIANGLE",
        "ASCENDING_TRIANGLE",
        "DESCENDING_TRIANGLE",
        "RISING_WEDGE",
        "FALLING_WEDGE",
        "SUPPORT_RESISTANCE",
        "VOLUME_SURGE",
        "BULLISH_RSI_DIVERGENCE",
        "BEARISH_RSI_DIVERGENCE",
        "RSI_OVERBOUGHT",
        "RSI_OVERSOLD",
    }
    try:
        source = source_path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(source_path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        return DiagnosticCheck(
            "Motor de estrategias visuales",
            "ERROR",
            f"No se pudo validar el motor central: {str(exc)[:160]}",
            _now_iso(),
            source=str(source_path),
        )
    present = {name for name in required if f'"{name}"' in source}
    missing = sorted(required - present)
    central_indicators = "add_central_indicators" in source and "roxy_trader.indicators" in source
    version_match = re.search(r'VISUAL_STRATEGY_ENGINE_VERSION\s*=\s*"([^"]+)"', source)
    version = version_match.group(1) if version_match else "sin_version"
    status = "CONNECTED" if not missing and central_indicators and version != "sin_version" else "WARNING"
    detail = (
        f"{version}; familias {len(present)}/{len(required)}; "
        f"indicadores centrales {'si' if central_indicators else 'no'}; faltantes {', '.join(missing) if missing else 'ninguna'}."
    )
    return DiagnosticCheck(
        "Motor de estrategias visuales",
        status,
        detail,
        _now_iso(),
        source=str(source_path),
    )


def backtest_engine_contract_check(
    engine_path: str | Path,
    wrapper_path: str | Path,
) -> DiagnosticCheck:
    """Verify reproducibility, realistic execution, validation, and durable storage contracts."""
    engine = Path(engine_path)
    wrapper = Path(wrapper_path)
    try:
        engine_source = engine.read_text(encoding="utf-8")
        wrapper_source = wrapper.read_text(encoding="utf-8")
        ast.parse(engine_source, filename=str(engine))
        ast.parse(wrapper_source, filename=str(wrapper))
    except (OSError, SyntaxError, UnicodeError) as exc:
        return DiagnosticCheck(
            "Motor de backtesting",
            "ERROR",
            f"No se pudo validar el contrato: {str(exc)[:160]}",
            _now_iso(),
            source=f"{engine}; {wrapper}",
        )

    version_match = re.search(r'BACKTEST_ENGINE_VERSION\s*=\s*"([^"]+)"', engine_source)
    validation_match = re.search(r'BACKTEST_VALIDATION_VERSION\s*=\s*"([^"]+)"', wrapper_source)
    version = version_match.group(1) if version_match else "sin_version"
    validation_version = validation_match.group(1) if validation_match else "sin_version"
    contracts = {
        "gap_stop": '"STOP_GAP"' in engine_source and "gap_through_stop" in engine_source,
        "annualization": "_periods_per_year" in engine_source and '"annualization_periods"' in engine_source,
        "costs": '"total_transaction_cost"' in engine_source and "slippage_pct" in engine_source,
        "temporal_validation": "anchored_time_split_no_refit" in wrapper_source and "out_of_sample" in wrapper_source,
        "input_hash": "input_contract_hash" in wrapper_source and "hashlib.sha256" in wrapper_source,
        "atomic_store": "os.replace" in wrapper_source and "fcntl.flock" in wrapper_source,
        "single_indicator_pass": "precomputed_indicators=True" in engine_source,
    }
    missing = [name for name, present in contracts.items() if not present]
    valid_versions = version.startswith("roxy-ma-backtest/") and validation_version.startswith(
        "roxy-backtest-validation/"
    )
    status = "CONNECTED" if not missing and valid_versions else "WARNING"
    detail = (
        f"{version}; {validation_version}; contratos {sum(contracts.values())}/{len(contracts)}; "
        f"faltantes {', '.join(missing) if missing else 'ninguno'}."
    )
    return DiagnosticCheck(
        "Motor de backtesting",
        status,
        detail,
        _now_iso(),
        source=f"{engine}; {wrapper}",
    )


@lru_cache(maxsize=8)
def _navigation_route_contract_scan(
    source_name: str, modified_ns: int, size_bytes: int
) -> tuple[int, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Audit literal internal links without importing the Streamlit application."""
    del modified_ns, size_bytes
    source = Path(source_name).read_text(encoding="utf-8")
    matches = re.findall(r"(?:\?|&|&amp;)(view|module|tab)=([A-Za-z0-9_%+.-]+)", source)
    allowed = {
        "view": {
            "Dashboard", "Noticias", "Calendario", "Alertas", "Activo", "Capital",
            "Plataformas", "Opciones", "Backtest", "Precision", "Estudios", "Roxy IA",
            "Diagnostico",
        },
        "module": {
            "acciones-operar", "crypto-20m", "crypto-2h", "crypto-daily", "classroom",
            "opciones",
        },
        "tab": {
            "resumen", "escaner", "destacadas", "movers", "mapa", "analisis",
            "dividendos", "reportes", "estrategias", "watchlists", "alertas",
        },
    }
    invalid: dict[str, set[str]] = {"view": set(), "module": set(), "tab": set()}
    for key, encoded in matches:
        value = unquote(encoded.replace("+", " "))
        if value not in allowed[key]:
            invalid[key].add(value)
    return (
        len(matches),
        tuple(sorted(invalid["view"])),
        tuple(sorted(invalid["module"])),
        tuple(sorted(invalid["tab"])),
    )


def navigation_route_contract_check(path: str | Path) -> DiagnosticCheck:
    """Detect internal links that would silently fall back to another Roxy surface."""
    source_path = Path(path)
    try:
        metadata = source_path.stat()
        link_params, invalid_views, invalid_modules, invalid_tabs = _navigation_route_contract_scan(
            str(source_path.resolve()), metadata.st_mtime_ns, metadata.st_size
        )
    except (OSError, UnicodeError) as exc:
        return DiagnosticCheck(
            "Rutas de interfaz",
            "ERROR",
            f"No se pudo auditar la navegacion: {str(exc)[:160]}",
            _now_iso(),
            source=str(source_path),
        )
    issue_count = len(invalid_views) + len(invalid_modules) + len(invalid_tabs)
    status = "CONNECTED" if issue_count == 0 else "WARNING"
    detail = (
        f"parametros internos {link_params}; vistas invalidas {len(invalid_views)}; "
        f"modulos invalidos {len(invalid_modules)}; pestañas invalidas {len(invalid_tabs)}."
    )
    invalid_values = [
        *(f"view={value}" for value in invalid_views),
        *(f"module={value}" for value in invalid_modules),
        *(f"tab={value}" for value in invalid_tabs),
    ]
    if invalid_values:
        detail += " Destinos: " + ", ".join(invalid_values[:12]) + "."
    return DiagnosticCheck("Rutas de interfaz", status, detail, _now_iso(), source=str(source_path))


FRONTEND_EXTERNAL_API_ALLOWLIST = frozenset(
    {
        "_container_width_to_width",
        "roxy_welcome_card_html",
        "center_decision_summary",
        "timeframe_minutes",
        "latest_chart_timestamp",
        "chart_freshness_status",
        "alert_silence_kpi_status",
        "alert_focus_rotation_panel_rows",
        "chart_realtime_watch_rows",
        "render_budget_top_trades_panel",
        "render_budget_trade_plan_panel",
        "render_budget_recommendation_strip",
        "dashboard_reference_patterns",
        "scanner_blotter_rows",
        "render_roxy_actions_command_center",
        "show_focused_opportunities",
        "render_focused_live_workspace",
    }
)


@lru_cache(maxsize=8)
def _frontend_function_contract_scan(
    source_name: str, modified_ns: int, size_bytes: int
) -> tuple[int, int, tuple[str, ...], tuple[str, ...]]:
    _source, tree = _frontend_source_ast(source_name, modified_ns, size_bytes)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    references = {name: 0 for name in functions}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in references:
            references[node.id] += 1
    zero_reference = {name for name, count in references.items() if count == 0}
    contracted = tuple(sorted(zero_reference & FRONTEND_EXTERNAL_API_ALLOWLIST))
    uncontracted = tuple(sorted(zero_reference - FRONTEND_EXTERNAL_API_ALLOWLIST))
    return len(functions), len(functions) - len(zero_reference), contracted, uncontracted


def frontend_function_contract_check(path: str | Path) -> DiagnosticCheck:
    """Fail visibly when top-level frontend functions have no consumer or external contract."""
    source_path = Path(path)
    try:
        metadata = source_path.stat()
        total, internally_referenced, contracted, uncontracted = _frontend_function_contract_scan(
            str(source_path.resolve()), metadata.st_mtime_ns, metadata.st_size
        )
    except (OSError, SyntaxError, UnicodeError) as exc:
        return DiagnosticCheck(
            "Consumidores frontend",
            "ERROR",
            f"No se pudo auditar funciones: {str(exc)[:160]}",
            _now_iso(),
            source=str(source_path),
        )
    status = "CONNECTED" if not uncontracted else "WARNING"
    detail = (
        f"funciones top-level {total}; consumidores internos {internally_referenced}; "
        f"APIs externas declaradas {len(contracted)}; sin contrato {len(uncontracted)}."
    )
    if uncontracted:
        detail += " Definiciones: " + ", ".join(uncontracted[:16]) + "."
    return DiagnosticCheck("Consumidores frontend", status, detail, _now_iso(), source=str(source_path))


RESPONSIVE_MATRIX_CONTRACT_VERSION = "roxy-responsive-matrix/1.2.0"
RESPONSIVE_MATRIX_EXPECTED_ROUTES = 14


def responsive_matrix_check(
    path: str | Path,
    *,
    now: datetime | None = None,
    stale_after_hours: float = 24.0,
) -> DiagnosticCheck:
    """Expose the last canonical desktop/iPad/mobile render matrix in diagnostics."""
    report_path = Path(path)
    if not report_path.is_file():
        return DiagnosticCheck(
            "Matriz responsive",
            "NO_DATA",
            "No existe matriz responsive; ejecutar tools/responsive_route_matrix.py.",
            _now_iso(),
            source=str(report_path),
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("el reporte no es un objeto")
        contract = str(report.get("contract_version") or "")
        if contract != RESPONSIVE_MATRIX_CONTRACT_VERSION:
            raise ValueError(f"contrato {contract or 'ausente'}")
        generated_text = str(report.get("generated_at") or "").replace("Z", "+00:00")
        generated_at = datetime.fromisoformat(generated_text)
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        checked = int(report.get("checked") or 0)
        passed = int(report.get("passed") or 0)
        failed = int(report.get("failed") or 0)
        rows = report.get("rows")
        if not isinstance(rows, list) or checked != len(rows) or passed + failed != checked:
            raise ValueError("conteos inconsistentes")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return DiagnosticCheck(
            "Matriz responsive",
            "ERROR",
            f"Reporte invalido: {str(exc)[:160]}",
            _now_iso(),
            source=str(report_path),
        )

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (reference - generated_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
    devices = report.get("devices") if isinstance(report.get("devices"), dict) else {}
    routes = report.get("routes") if isinstance(report.get("routes"), dict) else {}
    performance = report.get("performance") if isinstance(report.get("performance"), dict) else {}
    device_detail = ", ".join(
        f"{name} {int(value.get('passed') or 0)}/{int(value.get('checked') or 0)}"
        for name, value in devices.items()
        if isinstance(value, dict)
    )
    expected_devices = {"desktop", "ipad", "mobile"}
    full_matrix = bool(
        checked == RESPONSIVE_MATRIX_EXPECTED_ROUTES * len(expected_devices)
        and set(devices) == expected_devices
        and len(routes) == RESPONSIVE_MATRIX_EXPECTED_ROUTES
        and all(
            isinstance(value, dict)
            and int(value.get("checked") or 0) == RESPONSIVE_MATRIX_EXPECTED_ROUTES
            and int(value.get("passed") or 0) == RESPONSIVE_MATRIX_EXPECTED_ROUTES
            for value in devices.values()
        )
        and all(
            isinstance(value, dict)
            and int(value.get("checked") or 0) == len(expected_devices)
            and int(value.get("passed") or 0) == len(expected_devices)
            for value in routes.values()
        )
    )
    current = age_hours <= stale_after_hours
    healthy = str(report.get("status") or "") == "OK" and failed == 0 and passed == checked and full_matrix
    status = "CONNECTED" if healthy and current else "WARNING"
    detail = (
        f"{RESPONSIVE_MATRIX_CONTRACT_VERSION}; {passed}/{checked} rutas-dispositivo; "
        f"fallos {failed}; antiguedad {age_hours:.1f}h"
    )
    if device_detail:
        detail += f"; {device_detail}"
    if performance:
        detail += (
            f"; contenido inicial p95 {float(performance.get('p95_initial_content_seconds') or 0):.1f}s"
            f"/SLO {float(performance.get('slo_seconds') or 0):.1f}s, "
            f"max {float(performance.get('max_initial_content_seconds') or 0):.1f}s"
        )
    if not full_matrix:
        expected_checks = RESPONSIVE_MATRIX_EXPECTED_ROUTES * len(expected_devices)
        detail += f"; matriz canonica incompleta (esperadas {expected_checks} comprobaciones)"
    if not current:
        detail += f"; reporte vencido (limite {stale_after_hours:.0f}h)"
    return DiagnosticCheck("Matriz responsive", status, detail + ".", _now_iso(), source=str(report_path))


def macro_calendar_data_check(path: str | Path) -> DiagnosticCheck:
    """Report file presence separately from valid, current macro coverage."""
    from macro_calendar import macro_calendar_status

    calendar_path = Path(path)
    try:
        context = macro_calendar_status(calendar_path)
    except Exception as exc:
        return DiagnosticCheck(
            "Calendario macro",
            "ERROR",
            f"No se pudo validar calendario: {type(exc).__name__}.",
            _now_iso(),
            source=str(calendar_path),
        )
    data_status = str(context.get("data_status") or "NOT_CONFIGURED").upper()
    status = "WARNING" if data_status == "DELAYED" else data_status
    detail = (
        f"estado {data_status}; eventos validos {int(context.get('valid_event_count') or 0)}; "
        f"proximos {len(context.get('upcoming_events') or [])}; cobertura {context.get('coverage') or 'UNKNOWN'}. "
        f"{context.get('detail') or ''}"
    ).strip()
    return DiagnosticCheck("Calendario macro", status, detail, _now_iso(), source=str(calendar_path))


MACRO_CALENDAR_SYNC_CONTRACT_VERSION = "roxy-macro-calendar-sync/1.0.0"


def macro_calendar_sync_check(
    path: str | Path,
    *,
    now: datetime | None = None,
    stale_after_hours: float = 48.0,
) -> DiagnosticCheck:
    """Validate the durable official-source synchronization report."""
    report_path = Path(path)
    if not report_path.is_file():
        return DiagnosticCheck(
            "Sincronizacion calendario macro",
            "NO_DATA",
            "No existe reporte de sincronizacion oficial BEA.",
            _now_iso(),
            source=str(report_path),
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("report is not an object")
        generated_at = datetime.fromisoformat(str(report.get("generated_at") or "").replace("Z", "+00:00"))
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return DiagnosticCheck(
            "Sincronizacion calendario macro",
            "ERROR",
            f"Reporte invalido: {type(exc).__name__}.",
            _now_iso(),
            source=str(report_path),
        )
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (reference.astimezone(timezone.utc) - generated_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
    contract_ok = str(report.get("contract_version") or "") == MACRO_CALENDAR_SYNC_CONTRACT_VERSION
    upstream_ok = str(report.get("status") or "").upper() == "OK"
    event_count = int(report.get("event_count") or 0)
    future_count = int(report.get("future_event_count") or 0)
    current = age_hours <= stale_after_hours
    healthy = contract_ok and upstream_ok and event_count > 0 and current
    status = "CONNECTED" if healthy else "WARNING"
    detail = (
        f"{MACRO_CALENDAR_SYNC_CONTRACT_VERSION}; fuentes oficiales {str(report.get('status') or 'UNKNOWN').upper()}; "
        f"eventos {event_count}; futuros {future_count}; antiguedad {age_hours:.1f}h"
    )
    if not contract_ok:
        detail += "; contrato incompatible"
    if not current:
        detail += f"; reporte vencido (limite {stale_after_hours:.0f}h)"
    if report.get("cache_kept"):
        detail += "; cache anterior conservado"
    return DiagnosticCheck(
        "Sincronizacion calendario macro",
        status,
        detail + ".",
        _now_iso(),
        source=str(report_path),
    )


def macro_calendar_service_check() -> DiagnosticCheck:
    """Verify that the official calendar refresh is installed and loaded."""
    try:
        from tools import macro_calendar_launchd

        info = macro_calendar_launchd.status()
    except Exception as exc:
        return DiagnosticCheck(
            "Servicio calendario macro",
            "WARNING",
            f"No se pudo inspeccionar LaunchAgent: {type(exc).__name__}.",
            _now_iso(),
        )
    installed = bool(info.get("installed"))
    loaded = bool(info.get("loaded"))
    interval = int(info.get("interval_seconds") or 0)
    command = str(info.get("command") or "")
    valid = installed and loaded and 3_600 <= interval <= 86_400 and "macro_calendar_sync.py" in command
    status = "CONNECTED" if valid else "WARNING"
    detail = (
        f"LaunchAgent instalado {installed}; cargado {loaded}; intervalo {interval}s; "
        f"comando {'valido' if 'macro_calendar_sync.py' in command else 'invalido'}."
    )
    return DiagnosticCheck(
        "Servicio calendario macro",
        status,
        detail,
        _now_iso(),
        source=str(info.get("path") or "launchd"),
    )


def realtime_report_checks(
    path: str | Path,
    *,
    now: datetime | None = None,
    stale_after_minutes: float = 15.0,
) -> list[DiagnosticCheck]:
    """Translate the watchdog report into concise, safe operational checks."""
    report_path = Path(path)
    if not report_path.is_file():
        return [
            DiagnosticCheck(
                "Salud realtime",
                "NO_DATA",
                "No existe reporte del watchdog; ejecutar tools/roxy_realtime_check.py.",
                _now_iso(),
                source=str(report_path),
            )
        ]
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("el reporte no es un objeto")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return [
            DiagnosticCheck(
                "Salud realtime",
                "ERROR",
                f"Reporte invalido: {str(exc)[:160]}",
                _now_iso(),
                source=str(report_path),
            )
        ]

    generated_raw = str(report.get("generated_at") or "").strip()
    generated_at: datetime | None = None
    try:
        generated_at = datetime.fromisoformat(generated_raw.replace("Z", "+00:00"))
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        generated_at = generated_at.astimezone(timezone.utc)
    except (TypeError, ValueError):
        generated_at = None
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_minutes = (
        max(0.0, (now_utc - generated_at).total_seconds() / 60.0)
        if generated_at is not None
        else None
    )
    stale = age_minutes is None or age_minutes > stale_after_minutes
    report_status = str(report.get("status") or "UNKNOWN").upper()
    status_map = {"OK": "CONNECTED", "WARN": "WARNING", "FAIL": "ERROR"}
    summary_status = status_map.get(report_status, "WARNING")
    if stale and summary_status == "CONNECTED":
        summary_status = "WARNING"
    age_text = f"{age_minutes:.1f} min" if age_minutes is not None else "desconocida"
    checks = [
        DiagnosticCheck(
            "Salud realtime",
            summary_status,
            f"watchdog={report_status}; antiguedad {age_text}; {'reporte vencido' if stale else 'reporte vigente'}.",
            _now_iso(),
            source=str(report_path),
        )
    ]

    watchdog_components = {
        "streamlit_app": "Frontend watchdog",
        "live_backend_process_guard": "Backend de mercado",
        "chart_realtime_health_report": "Graficas realtime",
        "notification_delivery": "Notificaciones",
        "operational_logs": "Logs operativos",
        "project_storage_footprint": "Almacenamiento",
        "heartbeat": "Heartbeat del scanner",
        "live_scan_efficiency": "Eficiencia del scanner",
        "opportunity_lifecycle": "Ciclo de oportunidades",
        "report_metrics_contract": "Contrato de telemetria",
    }
    raw_checks = report.get("checks") if isinstance(report.get("checks"), list) else []
    for raw_check in raw_checks:
        if not isinstance(raw_check, dict):
            continue
        check_name = str(raw_check.get("name") or "")
        component = watchdog_components.get(check_name)
        if not component:
            continue
        check_state = str(raw_check.get("status") or "UNKNOWN").upper()
        check_status = status_map.get(check_state, "WARNING")
        if stale and check_status == "CONNECTED":
            check_status = "WARNING"
        checks.append(
            DiagnosticCheck(
                component,
                check_status,
                str(raw_check.get("detail") or f"watchdog={check_state}")[:500],
                _now_iso(),
                source=f"watchdog:{check_name}",
            )
        )

    recovery = report.get("provider_recovery") if isinstance(report.get("provider_recovery"), dict) else {}
    if recovery:
        auth_ok = recovery.get("alpaca_account_auth_ok") is True
        probe_status = str(recovery.get("alpaca_account_probe_status") or "UNKNOWN").upper()
        error_category = str(recovery.get("alpaca_account_error_category") or "-").strip()
        detail = str(recovery.get("detail") or "Validacion runtime sin detalle.").strip()
        if auth_ok and probe_status == "OK":
            alpaca_status = "CONNECTED"
        elif probe_status in {"WARN", "FAIL"} or not auth_ok:
            alpaca_status = "ERROR" if error_category == "AUTH_INVALID" else "WARNING"
        else:
            alpaca_status = "WARNING"
        checks.append(
            DiagnosticCheck(
                "Alpaca runtime",
                alpaca_status,
                f"{detail} Categoria={error_category}; modo={recovery.get('alpaca_account_mode') or '-'}.",
                _now_iso(),
                source="watchdog paper account probe",
            )
        )

    market_realtime = report.get("market_realtime") if isinstance(report.get("market_realtime"), dict) else {}
    rows: Any = market_realtime.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            market = str(row.get("market") or "desconocido").upper()
            runtime_status = str(row.get("status") or "UNKNOWN").upper()
            market_status = status_map.get(runtime_status, "WARNING")
            if stale and market_status == "CONNECTED":
                market_status = "WARNING"
            alerts = "ON" if row.get("alerts_allowed") is True else "OFF"
            checks.append(
                DiagnosticCheck(
                    f"Mercado {market}",
                    market_status,
                    f"{row.get('label') or runtime_status}: {row.get('detail') or '-'} Alertas={alerts}.",
                    _now_iso(),
                    source="watchdog market route",
                )
            )
    return checks


def simulation_check(env: Mapping[str, str] | None = None) -> DiagnosticCheck:
    values = env if env is not None else os.environ
    live_enabled = str(values.get("ROXY_ENABLE_LIVE_BROKER_EXECUTION", "0")).strip().lower() in {"1", "true", "yes"}
    paper = str(values.get("ALPACA_PAPER", "true")).strip().lower() not in {"0", "false", "no"}
    if live_enabled:
        return DiagnosticCheck(
            "Modo de ejecucion",
            "WARNING",
            "El interruptor global de ejecucion live esta habilitado; requiere revision manual.",
            _now_iso(),
            source="environment",
        )
    detail = "Ejecucion real bloqueada; Alpaca paper activo." if paper else "Ejecucion real bloqueada; Alpaca paper no confirmado."
    return DiagnosticCheck("Modo de ejecucion", "SIMULATED", detail, _now_iso(), source="environment")


RUNTIME_SECURITY_AUDIT_MAX_AGE_HOURS = 168.0
RUNTIME_SECURITY_BUILD_ONLY_EXCEPTIONS = {
    ("setuptools", "PYSEC-2026-3447"),
}


def runtime_dependency_security_check(
    audit_path: str | Path,
    *,
    runtime_version: tuple[int, int, int] | None = None,
    now: datetime | None = None,
) -> DiagnosticCheck:
    """Expose the active Python floor and pip-audit result without network I/O."""
    path = Path(audit_path)
    version = runtime_version or tuple(int(value) for value in sys.version_info[:3])
    version_label = ".".join(str(value) for value in version)
    if version < (3, 11, 0):
        return DiagnosticCheck(
            "Runtime y dependencias",
            "ERROR",
            f"Python {version_label} no cumple el piso 3.11; actualizar antes de uso diario.",
            _now_iso(),
            source=str(path),
        )
    if not path.is_file():
        return DiagnosticCheck(
            "Runtime y dependencias",
            "NOT_CONFIGURED",
            f"Python {version_label}; falta el reporte pip-audit local.",
            _now_iso(),
            source=str(path),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        dependencies = payload.get("dependencies") if isinstance(payload, dict) else None
        if not isinstance(dependencies, list):
            raise ValueError("estructura dependencies invalida")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return DiagnosticCheck(
            "Runtime y dependencias",
            "ERROR",
            f"Python {version_label}; reporte pip-audit invalido: {str(exc)[:120]}",
            _now_iso(),
            source=str(path),
        )
    findings: list[tuple[str, str]] = []
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        name = str(dependency.get("name") or "desconocido").strip().lower()
        vulns = dependency.get("vulns") if isinstance(dependency.get("vulns"), list) else []
        for vuln in vulns:
            if isinstance(vuln, dict):
                findings.append((name, str(vuln.get("id") or "sin-id").strip()))
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age_hours = max(0.0, (reference - modified).total_seconds() / 3600.0)
    actionable = [finding for finding in findings if finding not in RUNTIME_SECURITY_BUILD_ONLY_EXCEPTIONS]
    if actionable:
        status = "ERROR"
        detail = (
            f"Python {version_label}; pip check resuelto, pero pip-audit reporta "
            f"{len(actionable)} vulnerabilidad(es) de runtime en {len({name for name, _ in actionable})} paquete(s)."
        )
    elif findings:
        status = "WARNING"
        detail = (
            f"Python {version_label}; 0 vulnerabilidades de runtime y {len(findings)} excepcion(es) build-only "
            "documentada(s) por dependencia transitiva de ccxt."
        )
    else:
        status = "CONNECTED"
        detail = f"Python {version_label}; pip check y pip-audit sin hallazgos."
    if age_hours > RUNTIME_SECURITY_AUDIT_MAX_AGE_HOURS and status == "CONNECTED":
        status = "WARNING"
    detail += f" Auditoria local hace {age_hours:.1f}h."
    return DiagnosticCheck(
        "Runtime y dependencias",
        status,
        detail,
        _now_iso(),
        source=str(path),
    )


def authentication_security_check(
    root: str | Path = ".",
    *,
    env: Mapping[str, str] | None = None,
    minimum_password_iterations: int = PASSWORD_ITERATIONS,
    minimum_password_length: int = PASSWORD_MIN_LENGTH,
) -> DiagnosticCheck:
    """Audit authentication storage without returning account identifiers or secrets."""
    root_path = Path(root)
    values = env if env is not None else os.environ
    configured_users_path = str(values.get("ROXY_USERS_PATH", "")).strip()
    user_paths = [Path(configured_users_path)] if configured_users_path else []
    fallback_users_path = root_path / "data" / "roxy_users.json"
    if fallback_users_path not in user_paths:
        user_paths.append(fallback_users_path)
    configured_db_path = str(values.get("ROXY_AUTH_ATTEMPT_DB_PATH", "")).strip()
    db_path = Path(configured_db_path) if configured_db_path else root_path / "db" / "roxy.db"

    plaintext_tokens = 0
    weak_password_hashes = 0
    password_accounts = 0
    storage_errors: list[str] = []
    insecure_permissions: list[str] = []
    readable_user_files = 0
    seen_profiles: set[tuple[str, str, str, str]] = set()

    def inspect_profile(profile: Any) -> None:
        nonlocal plaintext_tokens, weak_password_hashes, password_accounts
        if not isinstance(profile, dict):
            return
        fingerprint = (
            str(profile.get("username") or "").strip().casefold(),
            str(profile.get("password_hash") or ""),
            str(profile.get("session_token") or ""),
            str(profile.get("session_token_hash") or ""),
        )
        if fingerprint in seen_profiles:
            return
        seen_profiles.add(fingerprint)
        if str(profile.get("session_token") or "").strip():
            plaintext_tokens += 1
        if str(profile.get("password_hash") or "").strip():
            password_accounts += 1
            try:
                iterations = int(profile.get("password_iterations") or 160_000)
            except (TypeError, ValueError):
                iterations = 0
            if iterations < minimum_password_iterations:
                weak_password_hashes += 1

    for users_path in user_paths:
        if not users_path.is_file():
            continue
        readable_user_files += 1
        try:
            mode = stat.S_IMODE(users_path.stat().st_mode)
            if mode & 0o077:
                insecure_permissions.append(f"{users_path.name}={mode:04o}")
            payload = json.loads(users_path.read_text(encoding="utf-8"))
            users = payload.get("users") if isinstance(payload, dict) else None
            if not isinstance(users, dict):
                raise ValueError("estructura users invalida")
            for profile in users.values():
                inspect_profile(profile)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            storage_errors.append(f"{users_path.name}: {str(exc)[:80]}")

    attempt_guard_present = False
    db_auth_users_present = False
    oauth_result_plaintext_tokens = 0
    if db_path.is_file():
        try:
            db_mode = stat.S_IMODE(db_path.stat().st_mode)
            if db_mode & 0o077:
                insecure_permissions.append(f"{db_path.name}={db_mode:04o}")
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2) as connection:
                tables = {
                    str(row[0])
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
                attempt_guard_present = "roxy_auth_attempts" in tables
                db_auth_users_present = "roxy_auth_users" in tables
                if db_auth_users_present:
                    columns = {
                        str(row[1]) for row in connection.execute("PRAGMA table_info(roxy_auth_users)").fetchall()
                    }
                    if "session_token" in columns:
                        plaintext_tokens += int(
                            connection.execute(
                                "SELECT COUNT(*) FROM roxy_auth_users "
                                "WHERE TRIM(COALESCE(session_token, '')) <> ''"
                            ).fetchone()[0]
                        )
                    if "profile_json" in columns:
                        for (profile_json,) in connection.execute("SELECT profile_json FROM roxy_auth_users"):
                            try:
                                inspect_profile(json.loads(profile_json or "{}"))
                            except (TypeError, ValueError, json.JSONDecodeError):
                                storage_errors.append("roxy_auth_users: profile_json invalido")
                if "oauth_results" in tables:
                    oauth_columns = {
                        str(row[1]) for row in connection.execute("PRAGMA table_info(oauth_results)").fetchall()
                    }
                    if "session_token" in oauth_columns:
                        oauth_result_plaintext_tokens = int(
                            connection.execute(
                                "SELECT COUNT(*) FROM oauth_results "
                                "WHERE TRIM(COALESCE(session_token, '')) <> ''"
                            ).fetchone()[0]
                        )
                        plaintext_tokens += oauth_result_plaintext_tokens
        except (OSError, sqlite3.Error) as exc:
            storage_errors.append(f"{db_path.name}: {str(exc)[:80]}")

    raw_session_age = str(values.get("ROXY_SESSION_MAX_AGE_SECONDS", "")).strip()
    try:
        session_age_seconds = int(raw_session_age) if raw_session_age else SESSION_MAX_AGE_SECONDS_DEFAULT
    except (TypeError, ValueError):
        session_age_seconds = SESSION_MAX_AGE_SECONDS_DEFAULT
    session_age_seconds = min(365 * 24 * 60 * 60, max(60 * 60, session_age_seconds))
    session_days = session_age_seconds / (24 * 60 * 60)

    problems: list[str] = []
    if plaintext_tokens:
        problems.append(f"tokens plaintext={plaintext_tokens}")
    if weak_password_hashes:
        problems.append(f"hashes por actualizar={weak_password_hashes}")
    if insecure_permissions:
        problems.append("permisos no privados=" + ",".join(insecure_permissions))
    if not attempt_guard_present:
        problems.append("limitador persistente ausente")
    if storage_errors:
        problems.append(f"errores de lectura={len(storage_errors)}")

    if plaintext_tokens or storage_errors:
        status = "ERROR"
    elif weak_password_hashes or insecure_permissions or not attempt_guard_present:
        status = "WARNING"
    elif not readable_user_files and not db_auth_users_present:
        status = "NO_DATA"
    else:
        status = "CONNECTED"
    detail = (
        f"PBKDF2 objetivo {minimum_password_iterations:,}; longitud minima {minimum_password_length}; "
        f"sesion {session_days:g} dias; cuentas con password {password_accounts}; "
        f"archivos de usuarios {readable_user_files}; throttle={'activo' if attempt_guard_present else 'ausente'} "
        f"({AUTH_MAX_FAILURES} fallos/{AUTH_WINDOW_SECONDS // 60} min; lock {AUTH_LOCK_SECONDS // 60} min); "
        f"tokens plaintext {plaintext_tokens}."
    )
    if oauth_result_plaintext_tokens:
        detail += f" OAuth transitorio plaintext {oauth_result_plaintext_tokens}."
    if problems:
        detail += " Hallazgos: " + "; ".join(problems) + "."
    return DiagnosticCheck(
        "Seguridad de autenticacion",
        status,
        detail,
        _now_iso(),
        source="auth storage audit",
    )


def secrets_api_security_check(env: Mapping[str, str] | None = None) -> DiagnosticCheck:
    """Report whether development-only secrets API bypasses are safely disabled."""
    values = env if env is not None else os.environ
    runtime = str(values.get("ROXY_ENV") or values.get("ENVIRONMENT") or "production").strip().lower()
    development = runtime in {"dev", "development", "local", "test", "testing"}

    def enabled(name: str) -> bool:
        return str(values.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}

    mock_login = enabled("ROXY_ENABLE_MOCK_LOGIN")
    insecure_admin = enabled("ROXY_ALLOW_INSECURE_DEV_ADMIN")
    admin_configured = any(
        bool(str(values.get(name) or "").strip()) for name in ("ADMIN_TOKEN", "ADMIN_USERS", "ADMIN_ORGS")
    )
    bypasses = [
        name
        for name, active in (
            ("ROXY_ENABLE_MOCK_LOGIN", mock_login),
            ("ROXY_ALLOW_INSECURE_DEV_ADMIN", insecure_admin),
        )
        if active
    ]
    if bypasses and not development:
        status = "ERROR"
    elif bypasses:
        status = "WARNING"
    else:
        status = "CONNECTED"
    detail = (
        f"runtime {runtime}; mock login {'activo' if mock_login else 'deshabilitado'}; "
        f"admin {'configurado' if admin_configured else 'fail-closed sin credencial'}; "
        f"bypasses de desarrollo {len(bypasses)}."
    )
    if bypasses:
        detail += " Flags activas: " + ", ".join(bypasses) + "."
    return DiagnosticCheck(
        "Seguridad API de secretos",
        status,
        detail,
        _now_iso(),
        source="environment + route policy",
    )


def voice_api_security_check(env: Mapping[str, str] | None = None) -> DiagnosticCheck:
    values = env if env is not None else os.environ
    configured = bool(str(values.get("VOICE_API_KEY") or "").strip())
    if configured:
        return DiagnosticCheck(
            "Seguridad API de voz",
            "CONNECTED",
            "VOICE_API_KEY configurada; endpoints de voz exigen Bearer y comparación en tiempo constante.",
            _now_iso(),
            source="environment + route policy",
        )
    return DiagnosticCheck(
        "Seguridad API de voz",
        "CONNECTED",
        "Modo local protegido: sólo clientes loopback pueden usar voz; clientes remotos reciben 503. "
        "VOICE_API_KEY sólo es necesaria al habilitar acceso remoto seguro.",
        _now_iso(),
        source="environment + route policy",
    )


def voice_remote_access_check(
    env: Mapping[str, str] | None = None,
    *,
    launchagent_path: str | Path | None = None,
    mobile_gateway_path: str | Path | None = None,
) -> DiagnosticCheck:
    """Report remote reachability without enabling or exposing the service."""
    values = env if env is not None else os.environ
    host = str(values.get("ROXY_VOICE_BIND_HOST") or "127.0.0.1").strip().lower()
    port = str(values.get("ROXY_VOICE_PORT") or "8010").strip()
    source = "environment defaults"
    path = Path(launchagent_path).expanduser() if launchagent_path else None
    if path is not None and path.exists():
        source = str(path)
        try:
            payload = plistlib.loads(path.read_bytes())
            args = payload.get("ProgramArguments") if isinstance(payload, dict) else []
            argv = [str(item) for item in args] if isinstance(args, list) else []
            if "--host" in argv and argv.index("--host") + 1 < len(argv):
                host = argv[argv.index("--host") + 1].strip().lower()
            if "--port" in argv and argv.index("--port") + 1 < len(argv):
                port = argv[argv.index("--port") + 1].strip()
        except (OSError, ValueError, TypeError, plistlib.InvalidFileException) as exc:
            return DiagnosticCheck(
                "Acceso remoto de voz",
                "ERROR",
                f"LaunchAgent de voz ilegible: {type(exc).__name__}.",
                _now_iso(),
                source=source,
            )
    loopback = host in {"127.0.0.1", "::1", "localhost"}
    bearer = bool(str(values.get("VOICE_API_KEY") or "").strip())
    public_base_url = str(values.get("ROXY_VOICE_PUBLIC_BASE_URL") or "").strip()
    tls_terminated = str(values.get("ROXY_VOICE_TLS_TERMINATED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    secure_transport = public_base_url.lower().startswith("https://") or tls_terminated
    if loopback:
        gateway = mobile_gateway_configuration_check(mobile_gateway_path) if mobile_gateway_path else None
        if gateway is not None and gateway.status in {"CONNECTED", "WARNING"}:
            status = gateway.status
            detail = (
                f"backend intencionalmente privado en {host}:{port}; acceso remoto delegado al gateway "
                f"HTTPS/Bearer aislado. {gateway.detail}"
            )
            source = f"{source}; {gateway.source}"
        else:
            status = "NOT_CONFIGURED"
            detail = (
                f"bind {host}:{port} solo loopback; iPad/telefono no pueden alcanzar el servicio. "
                "VOICE_API_KEY por si sola no cambia el bind; requiere exposicion explicita y HTTPS/reverse proxy."
            )
    elif not bearer:
        status = "NOT_CONFIGURED"
        detail = f"bind {host}:{port} remoto, pero falta VOICE_API_KEY; acceso remoto bloqueado por politica."
    elif not secure_transport:
        status = "WARNING"
        detail = (
            f"bind {host}:{port} y Bearer configurados, pero no hay transporte HTTPS declarado; "
            "no enviar credenciales por HTTP de red."
        )
    else:
        status = "CONNECTED"
        detail = f"bind {host}:{port}; Bearer y transporte HTTPS/reverse proxy configurados."
    return DiagnosticCheck("Acceso remoto de voz", status, detail, _now_iso(), source=source)


def device_sync_configuration_check(
    env: Mapping[str, str] | None = None,
    *,
    launchagent_path: str | Path | None = None,
    mobile_gateway_path: str | Path | None = None,
) -> DiagnosticCheck:
    """Report whether the revisioned state API is safe for physical remote devices."""
    values = env if env is not None else os.environ
    bearer_configured = bool(str(values.get("VOICE_API_KEY") or "").strip())
    users = allowed_device_sync_users(values)
    remote_access = voice_remote_access_check(
        values,
        launchagent_path=launchagent_path,
        mobile_gateway_path=mobile_gateway_path,
    )
    gateway_transport = bool(mobile_gateway_path) and remote_access.status in {"CONNECTED", "WARNING"}
    if users and gateway_transport:
        status = remote_access.status
    else:
        status = "CONNECTED" if bearer_configured and users and remote_access.status == "CONNECTED" else "NOT_CONFIGURED"
    detail = (
        f"{DEVICE_SYNC_CONTRACT_VERSION}; revisiones optimistas y HTTP 409 activos; "
        "ambitos watchlists/alertas, interfaz, tareas y compras; "
        f"usuarios permitidos {len(users)}; autenticacion "
        f"{'Bearer del gateway' if gateway_transport else 'Bearer configurada' if bearer_configured else 'solo loopback'}."
    )
    if gateway_transport:
        detail += f" Backend local no expuesto; {remote_access.detail}"
    elif not bearer_configured:
        detail += " iPad/telefono remotos requieren VOICE_API_KEY, bind no-loopback y HTTPS."
    elif remote_access.status != "CONNECTED":
        detail += f" Acceso remoto no listo: {remote_access.detail}"
    return DiagnosticCheck(
        "Sincronizacion entre dispositivos",
        status,
        detail,
        _now_iso(),
        source="state sync route policy",
    )


MOBILE_GATEWAY_CHECK_CONTRACT_VERSION = "roxy-mobile-gateway/1.0.0"


def mobile_gateway_configuration_check(path: str | Path) -> DiagnosticCheck:
    """Surface the secure gateway contract without claiming a physical-device test."""
    report_path = Path(path)
    if not report_path.is_file():
        return DiagnosticCheck(
            "Gateway movil HTTPS",
            "NOT_CONFIGURED",
            "No existe evidencia del gateway; ejecutar tools/mobile_gateway_check.py.",
            _now_iso(),
            source=str(report_path),
        )
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("el reporte no es un objeto")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return DiagnosticCheck(
            "Gateway movil HTTPS",
            "ERROR",
            f"Evidencia invalida: {str(exc)[:160]}",
            _now_iso(),
            source=str(report_path),
        )
    contract_ok = payload.get("contract_version") == MOBILE_GATEWAY_CHECK_CONTRACT_VERSION
    gateway_status = str(payload.get("gateway_status") or "").upper()
    ready = gateway_status in {"READY_FOR_PHYSICAL_TEST", "CONNECTED_PHYSICAL"}
    check_ok = str(payload.get("contract_status") or "").upper() == "OK"
    physical = str(payload.get("physical_reachability") or "UNKNOWN").upper()
    secrets_safe = payload.get("secrets_exposed") is False
    if not (contract_ok and ready and check_ok and secrets_safe):
        return DiagnosticCheck(
            "Gateway movil HTTPS",
            "ERROR",
            "TLS/Bearer/allowlist no tienen evidencia valida y completa; acceso remoto no aceptado.",
            _now_iso(),
            source=str(report_path),
        )
    detail = (
        f"{MOBILE_GATEWAY_CHECK_CONTRACT_VERSION}; TLS, Bearer y allowlist verificados localmente; "
        f"alcance fisico {physical}. Instalar/confiar la CA y probar desde iPad/telefono."
    )
    return DiagnosticCheck(
        "Gateway movil HTTPS",
        "CONNECTED" if physical == "VERIFIED_REMOTE_CLIENT" else "WARNING",
        detail,
        _now_iso(),
        source=str(report_path),
    )


def cache_policy_check(env: Mapping[str, str] | None = None) -> DiagnosticCheck:
    """Report the effective cache contract without exposing environment values."""
    values = env if env is not None else os.environ
    contract = cache_policy_contract(values)
    policies = contract.get("policies") if isinstance(contract, dict) else []
    rows = policies if isinstance(policies, list) else []
    issues = cache_policy_issues(values)
    overrides = [row for row in rows if row.get("override_state") != "default"]
    fast = [int(row["effective_seconds"]) for row in rows if row.get("data_class") == "market_quote"]
    slow = [int(row["effective_seconds"]) for row in rows if row.get("data_class") == "asset_identity"]
    status = "WARNING" if issues else "CONNECTED"
    detail = (
        f"{CACHE_POLICY_VERSION}; {len(rows)} clases; overrides {len(overrides)}; "
        f"quotes {min(fast) if fast else '-'}-{max(fast) if fast else '-'}s; "
        f"identidad {min(slow) if slow else '-'}-{max(slow) if slow else '-'}s."
    )
    if issues:
        issue_keys = ", ".join(str(row.get("env_key") or "-") for row in issues)
        detail += f" Overrides invalidos/recortados: {issue_keys}."
    else:
        detail += " Todos los TTL dentro de limites; datos vencidos requieren estado explicito."
    return DiagnosticCheck("Politica de cache", status, detail, _now_iso(), source="cache policy contract")


def api_usage_check(root: str | Path = ".", env: Mapping[str, str] | None = None) -> DiagnosticCheck:
    """Report operational API budgets and observed use without exposing request data."""
    values = env if env is not None else os.environ
    contract = api_budget_contract(values)
    mode = str(contract.get("mode") or "protect")
    path = default_api_usage_path(root)
    summary = ApiUsageLedger(path).summary(env=values)
    requests = int(summary.get("request_count") or 0)
    limited = int(summary.get("rate_limited_count") or 0)
    errors = int(summary.get("error_count") or 0)
    near = int(summary.get("near_limit_count") or 0)
    requests_24h = int(summary.get("request_count_24h") or 0)
    limited_24h = int(summary.get("rate_limited_count_24h") or 0)
    errors_24h = int(summary.get("error_count_24h") or 0)
    blocks = int(summary.get("block_count") or 0)
    blocks_24h = int(summary.get("block_count_24h") or 0)
    provider_rows = summary.get("providers") if isinstance(summary.get("providers"), list) else []
    active_rows = sorted(
        (row for row in provider_rows if int(row.get("requests_24h") or 0) > 0),
        key=lambda row: int(row.get("requests_24h") or 0),
        reverse=True,
    )
    policy_count = int(contract.get("policy_count") or 0)
    policy_issues = api_budget_issues(values)
    issue_rows = [row for row in provider_rows if str(row.get("state") or "") in {"ERROR", "RATE_LIMITED"}]
    historical_issue_rows = sorted(
        (
            row
            for row in provider_rows
            if int(row.get("errors_24h") or 0) > 0 or int(row.get("rate_limited_24h") or 0) > 0
        ),
        key=lambda row: int(row.get("errors_24h") or 0) + int(row.get("rate_limited_24h") or 0),
        reverse=True,
    )
    if limited or errors or blocks or policy_issues:
        status = "WARNING"
    elif near:
        status = "WARNING"
    elif not path.exists() or requests_24h == 0:
        status = "NO_DATA"
    else:
        status = "CONNECTED"
    detail = (
        f"{API_BUDGET_VERSION}; modo {mode}; {policy_count} proveedores; "
        f"ventana actual {requests} solicitudes; 24h {requests_24h}; "
        f"rate limits {limited}/{limited_24h} (ventana/24h); cerca del limite {near}. "
        f"errores {errors}/{errors_24h} (ventana/24h). "
        f"bloqueos protectores {blocks}/{blocks_24h} (ventana/24h). "
        "Los presupuestos Roxy son guardas operativas; el plan del proveedor es autoritativo."
    )
    if issue_rows:
        detail += " Incidentes actuales: " + ", ".join(
            f"{row.get('provider')} {row.get('state')} x{int(row.get('errors') or 0)}"
            for row in issue_rows[:5]
        ) + "."
    if historical_issue_rows:
        detail += " Incidentes 24h: " + ", ".join(
            f"{row.get('provider')} errores {int(row.get('errors_24h') or 0)}"
            f"/429 {int(row.get('rate_limited_24h') or 0)}"
            for row in historical_issue_rows[:5]
        ) + "."
    if active_rows:
        detail += " Activos 24h: " + ", ".join(
            f"{row.get('provider')} {int(row.get('requests_24h') or 0)} req/24h "
            f"(presupuesto {int(row.get('budget') or 0)}/min)"
            for row in active_rows[:5]
        ) + "."
    if not path.exists():
        detail += " Telemetria aun no creada."
    elif requests_24h == 0:
        detail += " Sin eventos observados en las ultimas 24h."
    if policy_issues:
        detail += " Overrides invalidos/recortados: " + ", ".join(
            str(row.get("env_key") or "-") for row in policy_issues
        ) + "."
    return DiagnosticCheck("Uso y limites de APIs", status, detail, _now_iso(), source=str(path))


def elevenlabs_runtime_check(
    root: str | Path = ".",
    *,
    now: datetime | None = None,
    stale_after_hours: float = 24.0,
) -> DiagnosticCheck:
    """Expose the latest observed voice-provider result without probing or leaking credentials."""
    path = default_api_usage_path(root)
    if not path.is_file():
        return DiagnosticCheck(
            "ElevenLabs runtime",
            "NO_DATA",
            "No existe telemetria de solicitudes ElevenLabs.",
            _now_iso(),
            source=str(path),
        )
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2) as connection:
            row = connection.execute(
                "SELECT operation, occurred_at, status, http_status FROM api_usage_events "
                "WHERE provider = 'elevenlabs' ORDER BY id DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        return DiagnosticCheck(
            "ElevenLabs runtime",
            "ERROR",
            f"No se pudo leer telemetria: {type(exc).__name__}.",
            _now_iso(),
            source=str(path),
        )
    if not row:
        return DiagnosticCheck(
            "ElevenLabs runtime",
            "NO_DATA",
            "Configuracion separada de runtime; aun no hay solicitudes observadas.",
            _now_iso(),
            source=str(path),
        )
    try:
        observed_at = datetime.fromisoformat(str(row[1] or "").replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return DiagnosticCheck(
            "ElevenLabs runtime", "ERROR", "Timestamp de telemetria invalido.", _now_iso(), source=str(path)
        )
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (reference.astimezone(timezone.utc) - observed_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
    operation = str(row[0] or "request")
    observed_status = str(row[2] or "UNKNOWN").upper()
    http_status = int(row[3]) if row[3] is not None else None
    if age_hours > stale_after_hours:
        status = "WARNING"
        state = "TELEMETRIA_VENCIDA"
    elif observed_status == "OK" and (http_status is None or 200 <= http_status < 400):
        status = "CONNECTED"
        state = "OPERATIVO"
    elif http_status in {401, 403}:
        status = "ERROR"
        state = "AUTH_INVALID"
    elif http_status == 429:
        status = "WARNING"
        state = "RATE_LIMITED"
    else:
        status = "ERROR"
        state = "PROVIDER_ERROR"
    http_label = f"HTTP {http_status}" if http_status is not None else "sin codigo HTTP"
    detail = f"{state}; ultima operacion {operation}; {http_label}; antiguedad {age_hours:.1f}h."
    if state == "AUTH_INVALID":
        circuit_path = Path(root) / "alerts" / "elevenlabs_auth_circuit.json"
        try:
            circuit = json.loads(circuit_path.read_text(encoding="utf-8"))
            failed_at = datetime.fromisoformat(str(circuit.get("failed_at") or "").replace("Z", "+00:00"))
            if failed_at.tzinfo is None:
                failed_at = failed_at.replace(tzinfo=timezone.utc)
            retry_seconds = max(60, int(circuit.get("retry_seconds") or 21_600))
            elapsed_seconds = max(
                0,
                int(
                    (
                        reference.astimezone(timezone.utc) - failed_at.astimezone(timezone.utc)
                    ).total_seconds()
                ),
            )
            remaining_seconds = retry_seconds - elapsed_seconds
            if str(circuit.get("state") or "").upper() == "AUTH_INVALID" and remaining_seconds > 0:
                detail += (
                    f" Circuito protector activo; sin reintentos repetidos durante {remaining_seconds}s "
                    "o hasta cambiar la credencial."
                )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        detail += " Recuperar con: .venv/bin/python tools/provider_credential_setup.py elevenlabs."
    return DiagnosticCheck("ElevenLabs runtime", status, detail, _now_iso(), source=str(path))


def frontend_style_resources_check(root: str | Path) -> DiagnosticCheck:
    """Verify the route-scoped CSS resources before Streamlit needs them."""

    style_root = Path(root) / "assets" / "styles"
    paths = {
        "base": style_root / "roxy_base.css.html",
        "academy_auth": style_root / "roxy_academy_auth.css",
        "responsive": style_root / "roxy_responsive.css.html",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        return DiagnosticCheck(
            "Recursos visuales frontend",
            "ERROR",
            "Faltan recursos CSS requeridos: " + ", ".join(missing),
            _now_iso(),
            source=str(style_root),
        )
    try:
        chunks = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    except OSError as exc:
        return DiagnosticCheck(
            "Recursos visuales frontend",
            "ERROR",
            f"No se pudieron leer los recursos CSS: {exc}",
            _now_iso(),
            source=str(style_root),
        )
    issues: list[str] = []
    if not chunks["base"].lstrip().startswith("<style>"):
        issues.append("base sin apertura <style>")
    if ".roxy-academy-shell{" not in chunks["academy_auth"]:
        issues.append("Academy/auth sin marcador inicial")
    if '[data-testid="stTabs"] button{' not in chunks["responsive"]:
        issues.append("responsive sin marcador de continuidad")
    if not chunks["responsive"].rstrip().endswith("</style>"):
        issues.append("responsive sin cierre </style>")
    combined_size = sum(len(value) for value in chunks.values())
    operational_size = len(chunks["base"]) + len(chunks["responsive"])
    if combined_size < 700_000 or operational_size >= combined_size:
        issues.append("tamanos de payload inconsistentes")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else (
            f"3/3 recursos; payload operacional {operational_size:,} caracteres; "
            f"Academy/auth {len(chunks['academy_auth']):,}; cascada completa {combined_size:,}."
        )
    )
    return DiagnosticCheck(
        "Recursos visuales frontend",
        status,
        detail,
        _now_iso(),
        source=str(style_root),
    )


def frontend_voice_runtime_resource_check(root: str | Path) -> DiagnosticCheck:
    """Verify the extracted voice runtime and its safe interpolation contract."""

    root_path = Path(root)
    runtime_path = root_path / "assets" / "runtime" / "roxy_elevenlabs_assistant.js.html"
    app_path = root_path / "streamlit_app.py"
    if not runtime_path.is_file():
        return DiagnosticCheck(
            "Runtime frontend de voz",
            "ERROR",
            "Falta la plantilla requerida del asistente de voz.",
            _now_iso(),
            source=str(runtime_path),
        )
    try:
        runtime = runtime_path.read_text(encoding="utf-8")
        app_source = app_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DiagnosticCheck(
            "Runtime frontend de voz",
            "ERROR",
            f"No se pudo leer el contrato del runtime: {exc}",
            _now_iso(),
            source=str(runtime_path),
        )
    issues: list[str] = []
    if runtime.count("__ROXY_VOICE_PAYLOAD_JSON__") != 2:
        issues.append("marcador payload invalido")
    if runtime.count("__ROXY_AVATAR_MARKUP_JSON__") != 1:
        issues.append("marcador avatar invalido")
    if len(runtime) < 60_000 or "Conversation.startSession" not in runtime:
        issues.append("runtime incompleto")
    if not runtime.lstrip().startswith("<script>") or not runtime.rstrip().endswith("</script>"):
        issues.append("envoltura script invalida")
    required_source_contracts = (
        "def roxy_json_for_inline_script",
        '.replace("<", "\\\\u003c")',
        "def roxy_elevenlabs_runtime_markup",
    )
    if any(contract not in app_source for contract in required_source_contracts):
        issues.append("serializacion segura ausente")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else f"plantilla {len(runtime):,} caracteres; marcadores 3/3; JSON protegido para script."
    )
    return DiagnosticCheck(
        "Runtime frontend de voz",
        status,
        detail,
        _now_iso(),
        source=str(runtime_path),
    )


def frontend_chart_runtime_resource_check(root: str | Path) -> DiagnosticCheck:
    """Verify the professional chart template, vendor bundle and safe JSON contract."""

    root_path = Path(root)
    runtime_path = root_path / "assets" / "runtime" / "roxy_live_candle_chart.html"
    vendor_path = root_path / "assets" / "vendor" / "lightweight-charts.4.2.3.min.js"
    app_path = root_path / "streamlit_app.py"
    missing = [str(path.relative_to(root_path)) for path in (runtime_path, vendor_path, app_path) if not path.is_file()]
    if missing:
        return DiagnosticCheck(
            "Runtime frontend de graficas",
            "ERROR",
            "Faltan recursos requeridos: " + ", ".join(missing),
            _now_iso(),
            source=str(runtime_path),
        )
    try:
        runtime = runtime_path.read_text(encoding="utf-8")
        vendor = vendor_path.read_text(encoding="utf-8")
        app_source = app_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DiagnosticCheck(
            "Runtime frontend de graficas",
            "ERROR",
            f"No se pudo leer el contrato de graficas: {exc}",
            _now_iso(),
            source=str(runtime_path),
        )
    issues: list[str] = []
    if runtime.count("__ROXY_PAYLOAD__") != 1:
        issues.append("marcador payload invalido")
    if runtime.count("__LIGHTWEIGHT_INLINE__") != 1:
        issues.append("marcador vendor invalido")
    required_runtime_contracts = (
        'id="roxy-live-chart-root"',
        "LightweightCharts.createChart",
        "chart.subscribeCrosshairMove",
        "openKlineSocket()",
        "sourceCandleByTime",
        "mergeStreamKline",
        "aggregationSeconds",
        'data-fasttf="20m"',
        'data-fasttf="30m"',
        'data-fasttf="2h"',
        'data-fasttf="4h"',
        'data-indicator="EMA50"',
        'data-indicator="EMA200"',
        'data-indicator="VWAP"',
        "technicalMetrics",
        'id="rlc-rsi-chart"',
        'id="rlc-macd-chart"',
        'id="rlc-candle-countdown"',
        'id="rlc-session-legend"',
        "decorateSessionCandle",
        "roxy-chart-viewport:v1",
        "restoreViewport",
        'priceScaleMode = indicatorSettings.Scale ? "auto-visible" : "manual-axis"',
        "renderCandleCountdown",
        "subscribeVisibleTimeRangeChange",
    )
    if len(runtime) < 100_000 or any(contract not in runtime for contract in required_runtime_contracts):
        issues.append("runtime incompleto")
    if len(vendor) < 100_000 or "LightweightCharts" not in vendor:
        issues.append("bundle Lightweight Charts invalido")
    required_source_contracts = (
        "def roxy_json_for_inline_script",
        "def roxy_live_chart_runtime_markup",
        "roxy_live_chart_runtime_markup(",
        "def chart_stream_source_interval_seconds",
        '"20m": "5m"',
        '"30m": "30m"',
        '"aggregationSeconds":',
        '"oscillators":',
        '"metrics":',
        '"session": session_contract',
        '"sessionVisual":',
        "stock_candle_session_phase",
        '"viewport": dict(',
        "def chart_market_session_contract",
        "window = add_central_indicators(window)",
    )
    if any(contract not in app_source for contract in required_source_contracts):
        issues.append("carga o serializacion segura ausente")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else (
            f"plantilla {len(runtime):,} caracteres; vendor {len(vendor):,}; "
            "marcadores 2/2; JSON protegido; 20m derivado de 5m y 30m nativo; "
            "EMA50/200, VWAP y ATR desde motor central; paneles RSI/MACD sincronizados; "
            "sesion extendida, cuenta regresiva de vela, bordes PRE/POST y viewport/escala persistibles."
        )
    )
    return DiagnosticCheck(
        "Runtime frontend de graficas",
        status,
        detail,
        _now_iso(),
        source=str(runtime_path),
    )


def professional_chart_data_contract_check(path: str | Path) -> DiagnosticCheck:
    """Verify central indicator ownership and explicit-only chart targets."""

    source_path = Path(path)
    try:
        metadata = source_path.stat()
        source, tree = _frontend_source_ast(
            str(source_path.resolve()), metadata.st_mtime_ns, metadata.st_size
        )
    except (OSError, SyntaxError, UnicodeError) as exc:
        return DiagnosticCheck(
            "Contrato de datos de graficas",
            "ERROR",
            f"No se pudo auditar el constructor profesional: {str(exc)[:160]}",
            _now_iso(),
            source=str(source_path),
        )
    required_names = {
        "prepare_chart_window",
        "explicit_chart_target_rows",
        "chart_trade_direction",
        "build_chart_level_plan",
        "build_professional_price_chart",
        "build_professional_oscillator_chart",
    }
    source_lines = source.splitlines()
    functions = {
        node.name: "\n".join(source_lines[node.lineno - 1 : node.end_lineno])
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in required_names
    }
    missing = sorted(required_names - set(functions))
    issues: list[str] = []
    if missing:
        issues.append("funciones ausentes: " + ", ".join(missing))
    price_source = functions.get("build_professional_price_chart", "")
    plan_source = functions.get("build_chart_level_plan", "")
    target_source = functions.get("explicit_chart_target_rows", "")
    direction_source = functions.get("chart_trade_direction", "")
    indicator_consumers = "\n".join(
        functions.get(name, "")
        for name in ("build_professional_price_chart", "build_professional_oscillator_chart")
    )
    if "explicit_chart_target_rows(setup, confluence, brief)" not in price_source:
        issues.append("grafica no consume objetivos explícitos centrales")
    if "explicit_chart_target_rows(setup, confluence, brief)" not in plan_source:
        issues.append("panel de niveles no comparte objetivos")
    if "source" not in target_source or "target_ladder" not in target_source:
        issues.append("procedencia de objetivos ausente")
    if "SHORT" not in direction_source or "stop > entry" not in direction_source:
        issues.append("direccion LONG/SHORT no normalizada")
    inferred_fragments = ("entry * 1.02", "entry * 1.05", "entry * 1.10")
    if any(fragment in price_source or fragment in plan_source for fragment in inferred_fragments):
        issues.append("objetivos porcentuales implícitos detectados")
    if ".rolling(" in indicator_consumers or ".ewm(" in indicator_consumers:
        issues.append("indicadores recalculados dentro del renderer")
    if "prepare_chart_window(chart_df)" not in price_source:
        issues.append("normalizacion finita ausente")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else (
            "objetivos explícitos con procedencia; LONG/SHORT normalizado; "
            "indicadores centrales sin rolling/ewm local; OHLCV finito."
        )
    )
    return DiagnosticCheck(
        "Contrato de datos de graficas",
        status,
        detail,
        _now_iso(),
        source=str(source_path),
    )


def frontend_actions_pro_chart_runtime_resource_check(root: str | Path) -> DiagnosticCheck:
    """Verify the stock professional chart template, vendor and safe interpolation."""

    root_path = Path(root)
    runtime_path = root_path / "assets" / "runtime" / "roxy_actions_pro_chart.html"
    vendor_path = root_path / "assets" / "vendor" / "lightweight-charts.4.2.3.min.js"
    app_path = root_path / "streamlit_app.py"
    missing = [str(path.relative_to(root_path)) for path in (runtime_path, vendor_path, app_path) if not path.is_file()]
    if missing:
        return DiagnosticCheck(
            "Runtime grafica profesional de acciones",
            "ERROR",
            "Faltan recursos requeridos: " + ", ".join(missing),
            _now_iso(),
            source=str(runtime_path),
        )
    try:
        runtime = runtime_path.read_text(encoding="utf-8")
        vendor = vendor_path.read_text(encoding="utf-8")
        app_source = app_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DiagnosticCheck(
            "Runtime grafica profesional de acciones",
            "ERROR",
            f"No se pudo leer el contrato de grafica profesional: {exc}",
            _now_iso(),
            source=str(runtime_path),
        )
    issues: list[str] = []
    expected_markers = {"__PAYLOAD__": 1, "__LIGHTWEIGHT_INLINE__": 1, "__CHART_ID__": 2}
    for marker, count in expected_markers.items():
        if runtime.count(marker) != count:
            issues.append(f"marcador {marker} invalido")
    required_runtime_contracts = (
        'class="roxy-pro-chart"',
        "LightweightCharts.createChart",
        "chart.subscribeCrosshairMove",
        "roxy-stock-quote",
    )
    if len(runtime) < 45_000 or any(contract not in runtime for contract in required_runtime_contracts):
        issues.append("runtime incompleto")
    if len(vendor) < 100_000 or "LightweightCharts" not in vendor:
        issues.append("bundle Lightweight Charts invalido")
    required_source_contracts = (
        "def roxy_json_for_inline_script",
        "def roxy_actions_pro_chart_runtime_markup",
        "roxy_actions_pro_chart_runtime_markup(",
        're.fullmatch(r"[A-Za-z0-9_-]{1,80}"',
    )
    if any(contract not in app_source for contract in required_source_contracts):
        issues.append("carga, DOM id o serializacion segura ausente")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else (
            f"plantilla {len(runtime):,} caracteres; vendor {len(vendor):,}; "
            "marcadores 4/4; payload, vendor y DOM id protegidos."
        )
    )
    return DiagnosticCheck(
        "Runtime grafica profesional de acciones",
        status,
        detail,
        _now_iso(),
        source=str(runtime_path),
    )


def frontend_actions_reference_terminal_resource_check(root: str | Path) -> DiagnosticCheck:
    """Verify the modular Actions terminal presentation and its complete slot contract."""

    root_path = Path(root)
    template_path = root_path / "assets" / "runtime" / "roxy_actions_reference_terminal.html"
    app_path = root_path / "streamlit_app.py"
    missing = [
        str(path.relative_to(root_path)) for path in (template_path, app_path) if not path.is_file()
    ]
    if missing:
        return DiagnosticCheck(
            "Presentacion terminal de Acciones",
            "ERROR",
            "Faltan recursos requeridos: " + ", ".join(missing),
            _now_iso(),
            source=str(template_path),
        )
    try:
        template = template_path.read_text(encoding="utf-8")
        app_source = app_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DiagnosticCheck(
            "Presentacion terminal de Acciones",
            "ERROR",
            f"No se pudo leer el contrato visual: {exc}",
            _now_iso(),
            source=str(template_path),
        )
    markers = re.findall(r"__ROXY_ACTIONS_[A-Z0-9_]+?__", template)
    unique_markers = set(markers)
    issues: list[str] = []
    if len(markers) != 33 or len(unique_markers) != 33:
        issues.append(f"marcadores {len(unique_markers)}/33, usos {len(markers)}")
    required_template_contracts = (
        '<style id="roxy-actions-terminal-v3">',
        'class="roxy-actions-terminal"',
        'class="terminal-top-strip"',
        'class="terminal-chart-row"',
        'class="terminal-grid"',
        'class="strategy-terminal-section"',
        "Lightweight Charts local",
        "</style>",
    )
    if len(template) < 25_000 or any(item not in template for item in required_template_contracts):
        issues.append("plantilla incompleta")
    required_source_contracts = (
        "def roxy_actions_reference_terminal_template",
        "def roxy_actions_reference_terminal_markup",
        "ROXY_ACTIONS_REFERENCE_TERMINAL_MARKERS",
        "roxy_actions_reference_terminal_markup(",
    )
    if any(item not in app_source for item in required_source_contracts):
        issues.append("carga o contrato de slots ausente")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else f"plantilla {len(template):,} caracteres; marcadores 33/33; carga cacheada y slots completos."
    )
    return DiagnosticCheck(
        "Presentacion terminal de Acciones",
        status,
        detail,
        _now_iso(),
        source=str(template_path),
    )


def frontend_backtest_equity_runtime_resource_check(root: str | Path) -> DiagnosticCheck:
    """Verify the lightweight, interactive backtest equity chart runtime."""

    root_path = Path(root)
    runtime_path = root_path / "assets" / "runtime" / "roxy_backtest_equity_chart.html"
    vendor_path = root_path / "assets" / "vendor" / "lightweight-charts.4.2.3.min.js"
    app_path = root_path / "streamlit_app.py"
    missing = [str(path.relative_to(root_path)) for path in (runtime_path, vendor_path, app_path) if not path.is_file()]
    if missing:
        return DiagnosticCheck(
            "Runtime curva de equity backtest",
            "ERROR",
            "Faltan recursos requeridos: " + ", ".join(missing),
            _now_iso(),
            source=str(runtime_path),
        )
    try:
        runtime = runtime_path.read_text(encoding="utf-8")
        vendor = vendor_path.read_text(encoding="utf-8")
        app_source = app_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DiagnosticCheck(
            "Runtime curva de equity backtest",
            "ERROR",
            f"No se pudo leer el contrato de equity: {exc}",
            _now_iso(),
            source=str(runtime_path),
        )
    issues: list[str] = []
    if runtime.count("__ROXY_BACKTEST_EQUITY_PAYLOAD__") != 1:
        issues.append("marcador payload invalido")
    if runtime.count("__LIGHTWEIGHT_INLINE__") != 1:
        issues.append("marcador vendor invalido")
    required_runtime_contracts = (
        'id="roxy-backtest-equity-root"',
        "LightweightCharts.createChart",
        "chart.subscribeCrosshairMove",
        "ResizeObserver",
    )
    if len(runtime) < 4_000 or any(contract not in runtime for contract in required_runtime_contracts):
        issues.append("runtime incompleto")
    if len(vendor) < 100_000 or "LightweightCharts" not in vendor:
        issues.append("bundle Lightweight Charts invalido")
    required_source_contracts = (
        "def roxy_json_for_inline_script",
        "def roxy_backtest_equity_runtime_markup",
        "def render_backtest_equity_chart",
    )
    if any(contract not in app_source for contract in required_source_contracts):
        issues.append("carga o serializacion segura ausente")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else f"plantilla {len(runtime):,} caracteres; vendor {len(vendor):,}; marcadores 2/2; crosshair y JSON seguros."
    )
    return DiagnosticCheck(
        "Runtime curva de equity backtest",
        status,
        detail,
        _now_iso(),
        source=str(runtime_path),
    )


def frontend_stock_live_runtime_resource_check(root: str | Path) -> DiagnosticCheck:
    """Verify modular stock quote bridge/refresh runtimes and safe interpolation."""

    root_path = Path(root)
    runtime_path = root_path / "assets" / "runtime" / "roxy_stock_live_runtime.js.html"
    refresh_path = root_path / "assets" / "runtime" / "roxy_stock_server_refresh.js.html"
    app_path = root_path / "streamlit_app.py"
    missing = [
        str(path.relative_to(root_path))
        for path in (runtime_path, refresh_path, app_path)
        if not path.is_file()
    ]
    if missing:
        return DiagnosticCheck(
            "Runtime frontend stock live",
            "ERROR",
            "Faltan recursos requeridos: " + ", ".join(missing),
            _now_iso(),
            source=str(runtime_path),
        )
    try:
        runtime = runtime_path.read_text(encoding="utf-8")
        refresh_runtime = refresh_path.read_text(encoding="utf-8")
        app_source = app_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DiagnosticCheck(
            "Runtime frontend stock live",
            "ERROR",
            f"No se pudo leer el contrato stock live: {exc}",
            _now_iso(),
            source=str(runtime_path),
        )
    issues: list[str] = []
    if runtime.count("__ROXY_STOCK_STREAM_URL__") != 1:
        issues.append("marcador stream invalido")
    if runtime.count("__ROXY_STOCK_SNAPSHOT_URL__") != 1:
        issues.append("marcador snapshot invalido")
    required_runtime_contracts = ("new EventSource", "fetchBridgeSnapshot", "roxy-stock-quote", "</script>")
    if len(runtime) < 20_000 or any(contract not in runtime for contract in required_runtime_contracts):
        issues.append("runtime incompleto")
    required_refresh_contracts = (
        "data-roxy-stock-live-price",
        "data-roxy-stock-provider-state",
        "setRefreshMeta",
        "setTradeState",
        "roxy-stock-quote",
        "</script>",
    )
    if refresh_runtime.count("__ROXY_STOCK_QUOTES__") != 1:
        issues.append("marcador refresh invalido")
    if len(refresh_runtime) < 10_000 or any(
        contract not in refresh_runtime for contract in required_refresh_contracts
    ):
        issues.append("runtime refresh incompleto")
    required_source_contracts = (
        "def roxy_json_for_inline_script",
        "def roxy_stock_live_runtime_markup",
        "roxy_stock_live_runtime_markup(",
        "def roxy_stock_server_refresh_runtime_markup",
        "roxy_stock_server_refresh_runtime_markup(",
    )
    if any(contract not in app_source for contract in required_source_contracts):
        issues.append("carga o serializacion segura ausente")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else (
            f"stream {len(runtime):,} caracteres; refresh {len(refresh_runtime):,}; "
            "marcadores 3/3; URLs y cotizaciones protegidas para script."
        )
    )
    return DiagnosticCheck(
        "Runtime frontend stock live",
        status,
        detail,
        _now_iso(),
        source=str(runtime_path),
    )


def frontend_three_universe_runtime_resource_check(root: str | Path) -> DiagnosticCheck:
    """Verify Academy's progressive Three.js runtime and bundled vendor resource."""

    root_path = Path(root)
    runtime_path = root_path / "assets" / "runtime" / "roxy_three_universe_runtime.js.html"
    vendor_path = root_path / "assets" / "vendor" / "three.r128.min.js"
    app_path = root_path / "streamlit_app.py"
    missing = [str(path.relative_to(root_path)) for path in (runtime_path, vendor_path, app_path) if not path.is_file()]
    if missing:
        return DiagnosticCheck(
            "Runtime frontend Academy WebGL",
            "ERROR",
            "Faltan recursos requeridos: " + ", ".join(missing),
            _now_iso(),
            source=str(runtime_path),
        )
    try:
        runtime = runtime_path.read_text(encoding="utf-8")
        vendor = vendor_path.read_text(encoding="utf-8")
        app_source = app_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DiagnosticCheck(
            "Runtime frontend Academy WebGL",
            "ERROR",
            f"No se pudo leer el contrato Academy WebGL: {exc}",
            _now_iso(),
            source=str(runtime_path),
        )
    issues: list[str] = []
    if runtime.count("__ROXY_THREE_INLINE_SOURCE__") != 1:
        issues.append("marcador vendor invalido")
    required_runtime_contracts = ("MutationObserver", "roxy-three-canvas", "roxy-three-fallback-hidden", "</script>")
    if len(runtime) < 15_000 or any(contract not in runtime for contract in required_runtime_contracts):
        issues.append("runtime incompleto")
    if len(vendor) < 100_000 or "THREE" not in vendor:
        issues.append("bundle Three.js invalido")
    required_source_contracts = (
        "def roxy_json_for_inline_script",
        "def roxy_three_universe_runtime_markup",
        "roxy_three_universe_runtime_markup(",
    )
    if any(contract not in app_source for contract in required_source_contracts):
        issues.append("carga o serializacion segura ausente")
    status = "ERROR" if issues else "CONNECTED"
    detail = (
        "; ".join(issues)
        if issues
        else f"plantilla {len(runtime):,} caracteres; vendor {len(vendor):,}; marcador 1/1; carga progresiva segura."
    )
    return DiagnosticCheck(
        "Runtime frontend Academy WebGL",
        status,
        detail,
        _now_iso(),
        source=str(runtime_path),
    )


BINANCEUS_SYMBOL_COVERAGE_CONTRACT_VERSION = "roxy-binanceus-symbol-coverage/1.0.0"


def binanceus_symbol_coverage_check(
    path: str | Path,
    *,
    now: datetime | None = None,
    stale_after_minutes: float = 30.0,
) -> DiagnosticCheck:
    """Verify that the live crypto universe is valid for the configured exchange."""

    report_path = Path(path)
    if not report_path.is_file():
        return DiagnosticCheck(
            "Cobertura de simbolos BinanceUS",
            "NO_DATA",
            "No existe el reporte de cobertura; ejecutar el escaner cripto.",
            _now_iso(),
            source=str(report_path),
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("el reporte no es un objeto")
        contract = str(report.get("contract_version") or "")
        if contract != BINANCEUS_SYMBOL_COVERAGE_CONTRACT_VERSION:
            raise ValueError(f"contrato {contract or 'ausente'}")
        generated_at = datetime.fromisoformat(str(report.get("generated_at") or "").replace("Z", "+00:00"))
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        requested = int(report.get("requested_count"))
        supported = int(report.get("supported_count"))
        unsupported = int(report.get("unsupported_count"))
        exact = int(report.get("exact_count"))
        fallback = int(report.get("quote_fallback_count"))
        if min(requested, supported, unsupported, exact, fallback) < 0:
            raise ValueError("conteos negativos")
        provider_status = str(report.get("status") or "UNKNOWN")
        if provider_status == "CONNECTED":
            if supported + unsupported != requested or exact + fallback != supported:
                raise ValueError("conteos inconsistentes")
        elif supported != 0 or unsupported != 0 or exact != 0 or fallback != 0:
            raise ValueError("conteos no disponibles inconsistentes")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return DiagnosticCheck(
            "Cobertura de simbolos BinanceUS",
            "ERROR",
            f"Reporte invalido: {str(exc)[:160]}",
            _now_iso(),
            source=str(report_path),
        )

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_minutes = max(0.0, (reference - generated_at.astimezone(timezone.utc)).total_seconds() / 60.0)
    current = age_minutes <= stale_after_minutes
    healthy = provider_status == "CONNECTED" and unsupported == 0 and fallback == 0 and current
    status = "CONNECTED" if healthy else "WARNING"
    detail = (
        f"{supported}/{requested} pares disponibles; exactos {exact}; fallback {fallback}; "
        f"no soportados {unsupported}; proveedor {provider_status}; antiguedad {age_minutes:.1f} min."
    )
    return DiagnosticCheck(
        "Cobertura de simbolos BinanceUS",
        status,
        detail,
        _now_iso(),
        source=str(report_path),
    )


def collect_system_diagnostics(
    *,
    root: str | Path = ".",
    env: Mapping[str, str] | None = None,
    frontend_url: str = "http://127.0.0.1:3000",
    voice_urls: Iterable[str] = ("http://127.0.0.1:8000/health", "http://127.0.0.1:8010/health"),
    live_http_checks: bool = True,
) -> list[dict[str, object]]:
    root_path = Path(root)
    checks: list[DiagnosticCheck] = (
        [_check_http("Frontend", frontend_url)]
        if live_http_checks
        else [
            DiagnosticCheck(
                "Frontend",
                "CONNECTED",
                "La sesion Streamlit actual esta renderizando; probe HTTP recursivo omitido.",
                _now_iso(),
                source="current Streamlit session",
            )
        ]
    )
    voice_results = [
        _check_http("Backend de voz", url) if live_http_checks else _check_tcp("Backend de voz", url)
        for url in voice_urls
    ]
    connected_voice = next((row for row in voice_results if row.status == "CONNECTED"), None)
    checks.append(connected_voice or voice_results[0])
    checks.append(database_check(root_path / "db" / "roxy.db", deep=False))
    checks.append(runtime_dependency_security_check(root_path / "alerts" / "dependency_audit.json"))
    checks.append(authentication_security_check(root_path, env=env))
    checks.append(secrets_api_security_check(env))
    checks.append(voice_api_security_check(env))
    voice_launchagent_path = Path.home() / "Library" / "LaunchAgents" / "com.roxy.voice-live.plist"
    mobile_gateway_path = root_path / "alerts" / "mobile_gateway_check.json"
    checks.append(
        voice_remote_access_check(
            env,
            launchagent_path=voice_launchagent_path,
            mobile_gateway_path=mobile_gateway_path,
        )
    )
    checks.append(
        device_sync_configuration_check(
            env,
            launchagent_path=voice_launchagent_path,
            mobile_gateway_path=mobile_gateway_path,
        )
    )
    checks.append(mobile_gateway_configuration_check(mobile_gateway_path))
    checks.append(cache_policy_check(env))
    checks.append(api_usage_check(root_path, env))
    checks.append(elevenlabs_runtime_check(root_path))
    checks.append(provider_environment_security_check(root_path / ".env"))
    checks.extend(provider_checks(env))
    checks.append(cache_check((root_path / "alerts", root_path / "output", root_path / "data")))
    checks.append(
        asset_identity_cache_check(
            root_path / "output" / "asset_identity_cache",
            operational_asset_identity_requirements(root_path),
        )
    )
    checks.append(operational_state_check(root_path / "data" / "roxy_watchlists.json"))
    checks.append(price_alert_monitor_check(root_path / "alerts" / "price_alert_monitor.json"))
    checks.append(opportunity_sync_check(root_path / "alerts" / "opportunity_sync.json"))
    checks.append(frontend_style_resources_check(root_path))
    checks.append(frontend_voice_runtime_resource_check(root_path))
    checks.append(frontend_chart_runtime_resource_check(root_path))
    checks.append(professional_chart_data_contract_check(root_path / "streamlit_app.py"))
    checks.append(frontend_actions_pro_chart_runtime_resource_check(root_path))
    checks.append(frontend_actions_reference_terminal_resource_check(root_path))
    checks.append(frontend_backtest_equity_runtime_resource_check(root_path))
    checks.append(frontend_stock_live_runtime_resource_check(root_path))
    checks.append(frontend_three_universe_runtime_resource_check(root_path))
    checks.append(binanceus_symbol_coverage_check(root_path / "alerts" / "binanceus_symbol_coverage.json"))
    checks.append(ui_control_contract_check(root_path / "streamlit_app.py"))
    checks.append(visual_strategy_engine_check(root_path / "roxy_trader" / "operational_strategies.py"))
    checks.append(
        backtest_engine_contract_check(
            root_path / "ma_backtester.py",
            root_path / "roxy_trader" / "backtests.py",
        )
    )
    checks.append(navigation_route_contract_check(root_path / "streamlit_app.py"))
    checks.append(frontend_function_contract_check(root_path / "streamlit_app.py"))
    checks.append(responsive_matrix_check(root_path / "alerts" / "responsive_route_matrix.json"))
    checks.append(macro_calendar_data_check(root_path / "data" / "macro_events.csv"))
    checks.append(macro_calendar_sync_check(root_path / "alerts" / "macro_calendar_sync.json"))
    checks.append(macro_calendar_service_check())
    checks.extend(realtime_report_checks(root_path / "alerts" / "roxy_realtime_check.json"))
    checks.append(simulation_check(env))
    return [check.to_dict() for check in checks]


def diagnostic_summary(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    materialized = list(rows)
    unhealthy = {"ERROR", "DISCONNECTED", "WARNING"}
    blocked = {"NOT_CONFIGURED", "NO_DATA"}
    return {
        "checked": len(materialized),
        "unhealthy": sum(str(row.get("status")) in unhealthy for row in materialized),
        "not_configured": sum(str(row.get("status")) in blocked for row in materialized),
        "operational": sum(str(row.get("status")) not in unhealthy | blocked for row in materialized),
        "generated_at": _now_iso(),
    }
