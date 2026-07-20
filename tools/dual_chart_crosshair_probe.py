#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tools.dashboard_render_probe import url_with_diagnostic_probe_token, wait_for_http
from durable_storage import atomic_write_text


DEFAULT_URL = (
    "http://127.0.0.1:3000/?view=Dashboard&module=acciones-operar&tab=analisis"
    "&symbol=BTC%2FUSD&market=crypto&tf=15m"
)


def evaluate_crosshair_contract(states: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    indexed = {str(item.get("timeframe") or ""): item for item in states}
    source = indexed.get("15m") or {}
    target = indexed.get("1h") or {}
    if set(indexed) != {"15m", "1h"}:
        issues.append(f"timeframes esperados 15m/1h; recibidos {sorted(indexed)}")
    for timeframe, state in (("15m", source), ("1h", target)):
        if state.get("channel_state") != "ready":
            issues.append(f"canal {timeframe} no listo")
    if source.get("linked_timeframe"):
        issues.append(f"eco detectado en 15m desde {source.get('linked_timeframe')}")
    if target.get("linked_timeframe") != "15m":
        issues.append("1h no recibio cursor desde 15m")
    if target.get("label") != "Cursor 15m ↔ 1h":
        issues.append("etiqueta enlazada de 1h incorrecta")
    return not issues, issues


def run_probe(*, url: str, screenshot_path: Path, wait_seconds: float = 30.0) -> dict[str, Any]:
    started = time.time()
    http_ok, http_detail = wait_for_http(url, timeout_seconds=wait_seconds)
    result: dict[str, Any] = {
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "http_detail": http_detail,
        "states": [],
        "issues": [],
        "console_errors": [],
    }
    if not http_ok:
        result.update(status="FAIL", ok=False, detail=f"App no disponible: {http_detail}")
        return result
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 1400})
            page.on("console", lambda message: result["console_errors"].append(message.text) if message.type == "error" else None)
            page.goto(url_with_diagnostic_probe_token(url), wait_until="domcontentloaded", timeout=int(wait_seconds * 1000))
            page.get_by_text("Graficas operativas", exact=True).wait_for(timeout=int(wait_seconds * 1000))
            deadline = time.time() + wait_seconds
            chart_frames = []
            while time.time() < deadline:
                chart_frames = [frame for frame in page.frames if frame.locator("#roxy-live-chart-root").count()]
                if len(chart_frames) >= 2:
                    break
                page.wait_for_timeout(250)
            if len(chart_frames) != 2:
                result["issues"].append(f"se esperaban 2 graficas; encontradas {len(chart_frames)}")
            else:
                frames_by_timeframe = {}
                for frame in chart_frames:
                    title = frame.locator("#rlc-title").inner_text()
                    timeframe = "15m" if "· 15m ·" in title else "1h" if "· 1h ·" in title else ""
                    frames_by_timeframe[timeframe] = frame
                source = frames_by_timeframe.get("15m")
                if source is None:
                    result["issues"].append("grafica 15m ausente")
                else:
                    source.locator("#roxy-live-chart").hover(position={"x": 650, "y": 220})
                    page.wait_for_timeout(800)
                states = []
                for timeframe in ("15m", "1h"):
                    frame = frames_by_timeframe.get(timeframe)
                    if frame is None:
                        continue
                    state = frame.locator("#roxy-live-chart-root").evaluate(
                        """root => ({
                            channel_state: root.dataset.crosshairLinkState || '',
                            linked_timeframe: root.dataset.linkedTimeframe || '',
                            label: root.querySelector('#rlc-crosshair-link')?.textContent || ''
                        })"""
                    )
                    states.append({"timeframe": timeframe, **state})
                result["states"] = states
                valid, contract_issues = evaluate_crosshair_contract(states)
                result["issues"].extend(contract_issues)
                if not valid:
                    result["issues"].append("contrato de cursor dual invalido")
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), full_page=True)
            result["screenshot_path"] = str(screenshot_path)
            browser.close()
    except Exception as exc:
        result["issues"].append(f"{type(exc).__name__}: {exc}")
    if result["console_errors"]:
        result["issues"].append(f"errores de consola {len(result['console_errors'])}")
    ok = not result["issues"]
    result.update(
        status="OK" if ok else "FAIL",
        ok=ok,
        detail="cursor 15m→1h enlazado sin eco" if ok else "; ".join(result["issues"]),
        duration_seconds=round(time.time() - started, 3),
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verifica el cursor enlazado de las graficas Roxy 15m/1h.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--json-path", default=str(BASE_DIR / "alerts" / "dual_chart_crosshair_probe.json"))
    parser.add_argument("--screenshot-path", default=str(BASE_DIR / "output" / "playwright" / "dual_chart_crosshair_probe.png"))
    parser.add_argument("--wait-seconds", type=float, default=30.0)
    parser.add_argument("--no-fail", action="store_true")
    args = parser.parse_args()
    result = run_probe(url=args.url, screenshot_path=Path(args.screenshot_path), wait_seconds=args.wait_seconds)
    target = Path(args.json_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(json.dumps(result, indent=2, sort_keys=True), target)
    print(f"Dual chart crosshair probe: {result['status']} | {result['detail']}")
    print(f"JSON: {target}")
    if result["status"] == "FAIL" and not args.no_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
