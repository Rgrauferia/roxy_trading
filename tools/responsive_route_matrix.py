#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from durable_storage import atomic_write_text
from tools.dashboard_render_probe import run_probe


RESPONSIVE_MATRIX_CONTRACT = "roxy-responsive-matrix/1.2.0"
INITIAL_CONTENT_SLO_SECONDS = 15.0
DEFAULT_REPORT = BASE_DIR / "alerts" / "responsive_route_matrix.json"
DEFAULT_SCREENSHOTS = BASE_DIR / "output" / "playwright" / "responsive_matrix"

VIEWPORTS: dict[str, tuple[int, int]] = {
    "desktop": (1440, 1000),
    "ipad": (820, 1180),
    "mobile": (390, 844),
}

ROUTES: dict[str, dict[str, Any]] = {
    "actions": {
        "query": "?view=Dashboard&module=acciones-operar&tab=escaner&symbol=AAPL&market=stock&tf=1h",
        "required": ["Escáner Finviz", "Tus Watchlists"],
    },
    "charts": {
        "query": "?view=Dashboard&module=acciones-operar&tab=analisis&symbol=LINK%2FUSD&market=crypto&tf=15m",
        "required": ["Graficas operativas", "LINK/USD"],
    },
    "watchlists": {
        "query": "?view=Dashboard&module=acciones-operar&tab=watchlists&symbol=LINK%2FUSD&market=crypto&tf=15m",
        "required": ["Watchlists conectadas", "Sincronizacion multi-dispositivo"],
    },
    "crypto": {
        "query": "?view=Dashboard&module=crypto-20m&symbol=BTC%2FUSD&market=crypto&tf=20m",
        "required": ["BTC/USD", "Crypto"],
    },
    "news": {
        "query": "?view=Noticias&symbol=LINK%2FUSD&market=crypto&tf=15m",
        "required": ["Noticias · LINK/USD", "Contexto general de mercado"],
    },
    "calendar": {
        "query": "?view=Calendario&symbol=BTC%2FUSD&market=crypto&tf=15m",
        "required": ["Calendario de mercado", "CALENDAR_EVENTS_ONLY", "BTC/USD"],
    },
    "options_stock": {
        "query": "?view=Opciones&symbol=AAPL&market=stock&tf=1h",
        "required": ["Opciones · AAPL", "Subyacente central: AAPL", "Uso permitido"],
    },
    "options_crypto": {
        "query": "?view=Opciones&symbol=BTC%2FUSD&market=crypto&tf=20m",
        "required": ["Opciones · BTC/USD", "no aplica a BTC/USD (CRYPTO)"],
    },
    "portfolio": {
        "query": "?view=Capital&symbol=LINK%2FUSD&market=crypto&tf=15m",
        "required": ["Portafolio y operaciones", "Simulador local por usuario"],
        # Capital verifies local ledgers and broker guards before rendering the
        # simulator; cold Streamlit sessions need a wider deterministic budget.
        "wait_seconds": 45.0,
    },
    "activity": {
        "query": "?view=Actividad&symbol=AAPL&market=stock&tf=1h",
        "required": ["Actividad", "No incluye órdenes reales ni actividad de otros perfiles", "AAPL"],
    },
    "memory": {
        "query": "?view=Memoria&symbol=BTC%2FUSD&market=crypto&tf=15m",
        "required": ["Memoria", "no es memoria conversacional privada", "BTC/USD"],
    },
    "notifications": {
        "query": "?view=Notificaciones&symbol=ETH%2FUSD&market=crypto&tf=20m",
        "required": ["Notificaciones", "los mensajes de otros usuarios no se exponen", "ETH/USD"],
    },
    "roxy": {
        "query": "?view=Roxy%20IA&symbol=LINK%2FUSD&market=crypto&tf=15m",
        "required": ["Roxy IA", "LINK/USD"],
    },
    "diagnostics": {
        "query": "?view=Diagnostico&symbol=LINK%2FUSD&market=crypto&tf=15m",
        "required": ["Diagnostico del sistema", "Consumidores frontend"],
        # Cold diagnostics parses the large frontend contract before the
        # result table appears. Preserve a strict requirement, with enough
        # time for the first uncached desktop session to complete.
        "wait_seconds": 45.0,
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def responsive_result_ok(result: dict[str, Any]) -> bool:
    visibility = result.get("page_visibility") if isinstance(result.get("page_visibility"), dict) else {}
    soft_warning_families = (
        result.get("soft_console_warning_unique_family_counts")
        if isinstance(result.get("soft_console_warning_unique_family_counts"), dict)
        else {}
    )
    phases = result.get("phase_timings") if isinstance(result.get("phase_timings"), dict) else {}
    initial_content_seconds = phases.get("initial_content_ready_seconds")
    performance_ok = initial_content_seconds is None or float(initial_content_seconds) <= INITIAL_CONTENT_SLO_SECONDS
    return bool(
        result.get("status") == "OK"
        and float(visibility.get("horizontal_overflow") or 0) <= 4
        and int(result.get("blocking_console_error_count") or 0) == 0
        and int(result.get("blocking_page_error_count") or 0) == 0
        and result.get("view_persisted") is True
        and result.get("symbol_persisted") is True
        and result.get("market_persisted") is True
        and result.get("timeframe_persisted") is True
        and int(soft_warning_families.get("empty_chart_extent") or 0) == 0
        and performance_ok
    )


def run_responsive_matrix(
    *,
    base_url: str,
    route_names: list[str],
    device_names: list[str],
    screenshot_dir: str | Path | None = None,
    wait_seconds: float = 24.0,
    probe: Callable[..., dict[str, Any]] = run_probe,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    screenshots = Path(screenshot_dir) if screenshot_dir else None
    if screenshots:
        screenshots.mkdir(parents=True, exist_ok=True)
    for route_name in route_names:
        route = ROUTES[route_name]
        url = urljoin(base_url.rstrip("/") + "/", str(route["query"]))
        for device_name in device_names:
            width, height = VIEWPORTS[device_name]
            screenshot_path = screenshots / f"{route_name}_{device_name}.png" if screenshots else None
            route_wait_seconds = max(float(wait_seconds), float(route.get("wait_seconds") or 0))
            result = probe(
                url=url,
                required_text=list(route["required"]),
                min_text_length=400,
                wait_seconds=route_wait_seconds,
                live_pulse_wait_seconds=2.0,
                screenshot_path=screenshot_path,
                viewport_width=width,
                viewport_height=height,
            )
            visibility = result.get("page_visibility") if isinstance(result.get("page_visibility"), dict) else {}
            phases = result.get("phase_timings") if isinstance(result.get("phase_timings"), dict) else {}
            rows.append(
                {
                    "route": route_name,
                    "device": device_name,
                    "viewport": f"{width}x{height}",
                    "status": "OK" if responsive_result_ok(result) else "FAIL",
                    "probe_status": str(result.get("status") or "UNKNOWN"),
                    "detail": str(result.get("detail") or "")[:320],
                    "duration_seconds": float(result.get("duration_seconds") or 0),
                    "navigation_dom_seconds": float(phases.get("navigation_dom_seconds") or 0),
                    "initial_content_ready_seconds": float(phases.get("initial_content_ready_seconds") or 0),
                    "horizontal_overflow": float(visibility.get("horizontal_overflow") or 0),
                    "blocking_console_errors": int(result.get("blocking_console_error_count") or 0),
                    "blocking_page_errors": int(result.get("blocking_page_error_count") or 0),
                    "soft_warning_families": result.get("soft_console_warning_unique_family_counts") or {},
                    "final_url": str(result.get("final_url") or result.get("url") or ""),
                    "screenshot_path": str(result.get("screenshot_path") or ""),
                }
            )
    passed = sum(row["status"] == "OK" for row in rows)
    measured_initial = sorted(
        float(row["initial_content_ready_seconds"])
        for row in rows
        if float(row.get("initial_content_ready_seconds") or 0) > 0
    )
    p95_index = max(0, min(len(measured_initial) - 1, int(round(0.95 * len(measured_initial) + 0.499999)) - 1)) if measured_initial else 0
    performance = {
        "slo_seconds": INITIAL_CONTENT_SLO_SECONDS,
        "measured": len(measured_initial),
        "average_initial_content_seconds": round(sum(measured_initial) / len(measured_initial), 3) if measured_initial else None,
        "p95_initial_content_seconds": round(measured_initial[p95_index], 3) if measured_initial else None,
        "max_initial_content_seconds": round(max(measured_initial), 3) if measured_initial else None,
        "within_slo": sum(value <= INITIAL_CONTENT_SLO_SECONDS for value in measured_initial),
    }
    device_summary = {
        device: {
            "checked": sum(row["device"] == device for row in rows),
            "passed": sum(row["device"] == device and row["status"] == "OK" for row in rows),
        }
        for device in device_names
    }
    route_summary = {
        route: {
            "checked": sum(row["route"] == route for row in rows),
            "passed": sum(row["route"] == route and row["status"] == "OK" for row in rows),
        }
        for route in route_names
    }
    return {
        "contract_version": RESPONSIVE_MATRIX_CONTRACT,
        "generated_at": utc_now_iso(),
        "status": "OK" if passed == len(rows) else "FAIL",
        "checked": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "performance": performance,
        "devices": device_summary,
        "routes": route_summary,
        "rows": rows,
    }


def write_report(payload: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def parse_names(value: str, allowed: dict[str, Any]) -> list[str]:
    names = [item.strip() for item in str(value or "").split(",") if item.strip()]
    invalid = [name for name in names if name not in allowed]
    if invalid:
        raise ValueError("Valores desconocidos: " + ", ".join(invalid))
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate canonical Roxy routes on desktop, iPad and phone viewports.")
    parser.add_argument("--base-url", default="http://127.0.0.1:3000/")
    parser.add_argument("--routes", default=",".join(ROUTES))
    parser.add_argument("--devices", default=",".join(VIEWPORTS))
    parser.add_argument("--json-path", default=str(DEFAULT_REPORT))
    parser.add_argument("--screenshots-dir", default=str(DEFAULT_SCREENSHOTS))
    parser.add_argument("--wait-seconds", type=float, default=24.0)
    parser.add_argument("--no-fail", action="store_true")
    args = parser.parse_args()
    payload = run_responsive_matrix(
        base_url=args.base_url,
        route_names=parse_names(args.routes, ROUTES),
        device_names=parse_names(args.devices, VIEWPORTS),
        screenshot_dir=args.screenshots_dir or None,
        wait_seconds=args.wait_seconds,
    )
    path = write_report(payload, args.json_path)
    print(
        f"Responsive route matrix: {payload['status']} | "
        f"{payload['passed']}/{payload['checked']} passed, {payload['failed']} failed"
    )
    print(f"JSON: {path}")
    if payload["status"] != "OK" and not args.no_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
