#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from durable_storage import atomic_write_text

DEFAULT_URL = "http://127.0.0.1:3000/?view=Opciones&symbol=ETH%2FUSD&market=crypto&tf=1h"
DEFAULT_JSON_PATH = BASE_DIR / "alerts" / "dashboard_render_probe.json"
DIAGNOSTIC_PROBE_PARAM = "rx_probe"
DIAGNOSTIC_PROBE_SECRET_PATH = Path.home() / "Library" / "Application Support" / "RoxyTrading" / "dashboard_probe_secret"
DEFAULT_FORBIDDEN_TEXT = [
    "Traceback:",
    "Traceback (most recent call last):",
    "StreamlitFragmentWidgetsNotAllowedOutsideError",
    "StreamlitAPIException",
]
VIEW_LABELS = {
    "Dashboard": "Inicio",
    "Capital": "Portafolio y operaciones",
    "Plataformas": "Integraciones",
    "Backtest": "Backtesting",
    "Precision": "Rendimiento",
    "Tareas": "Tareas personales",
    "Compras": "Lista de compras",
    "Hogar": "Roxy Home",
}
SOFT_CONSOLE_ERROR_PATTERNS = [
    "Unrecognized data set",
]
SOFT_CONSOLE_ERROR_FAMILY_PATTERNS = {
    "vega_unrecognized_dataset": ["Unrecognized data set"],
}
SOFT_CONSOLE_WARNING_PATTERNS = [
    "Unrecognized feature:",
    "An iframe which has both allow-scripts and allow-same-origin",
    'Invalid color passed for widgetBackgroundColor in theme.sidebar: ""',
    'Invalid color passed for widgetBorderColor in theme.sidebar: ""',
    'Invalid color passed for skeletonBackgroundColor in theme.sidebar: ""',
    "GL Driver Message",
    "The input spec uses Vega-Lite",
    "WARN Infinite extent for field",
    'WARN Dropping "fit-x" because spec has discrete width',
]
SOFT_CONSOLE_WARNING_FAMILY_PATTERNS = {
    "browser_feature_policy": ["Unrecognized feature:"],
    "iframe_sandbox_policy": ["An iframe which has both allow-scripts and allow-same-origin"],
    "streamlit_optional_sidebar_theme": [
        'Invalid color passed for widgetBackgroundColor in theme.sidebar: ""',
        'Invalid color passed for widgetBorderColor in theme.sidebar: ""',
        'Invalid color passed for skeletonBackgroundColor in theme.sidebar: ""',
    ],
    "headless_webgl_readback": ["GL Driver Message"],
    "vega_lite_version": ["The input spec uses Vega-Lite"],
    "empty_chart_extent": ["WARN Infinite extent for field"],
    "vega_fit_width": ['WARN Dropping "fit-x" because spec has discrete width'],
}
FATAL_CONSOLE_ERROR_PATTERNS = [
    "Traceback",
    "Error running app",
    "StreamlitAPIException",
    "StreamlitFragmentWidgetsNotAllowedOutsideError",
    "SyntaxError",
    "ReferenceError",
    "TypeError",
    "Uncaught",
]
MAX_FRONTEND_ERROR_SAMPLES = 8
MAX_FRONTEND_ERROR_STACK_LENGTH = 1200


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def diagnostic_probe_secret(path: str | Path = DIAGNOSTIC_PROBE_SECRET_PATH) -> bytes:
    target = Path(path)
    try:
        existing = target.read_bytes()
    except OSError:
        existing = b""
    if len(existing) >= 32:
        return existing
    target.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_bytes(48)
    target.write_bytes(value)
    target.chmod(0o600)
    return value


def diagnostic_probe_token(
    *,
    secret_path: str | Path = DIAGNOSTIC_PROBE_SECRET_PATH,
    now: int | None = None,
) -> str:
    timestamp = str(int(time.time() if now is None else now))
    nonce = secrets.token_urlsafe(24)
    message = f"{timestamp}.{nonce}"
    signature = hmac.new(diagnostic_probe_secret(secret_path), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{message}.{signature}"


def url_with_diagnostic_probe_token(
    url: str,
    *,
    secret_path: str | Path = DIAGNOSTIC_PROBE_SECRET_PATH,
    now: int | None = None,
) -> str:
    parsed = urlsplit(str(url))
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != DIAGNOSTIC_PROBE_PARAM]
    query.append((DIAGNOSTIC_PROBE_PARAM, diagnostic_probe_token(secret_path=secret_path, now=now)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def url_without_diagnostic_probe_token(url: str) -> str:
    parsed = urlsplit(str(url))
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != DIAGNOSTIC_PROBE_PARAM]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def wait_for_http(url: str, *, timeout_seconds: float = 60.0) -> tuple[bool, str]:
    deadline = time.time() + max(1.0, float(timeout_seconds))
    last_error = ""
    while time.time() <= deadline:
        try:
            with urlopen(url, timeout=3.0) as response:
                status_code = int(getattr(response, "status", 0) or 0)
            if 200 <= status_code < 400:
                return True, f"HTTP {status_code}"
            last_error = f"HTTP {status_code}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(2.0)
    return False, last_error or "timeout"


def build_result(
    *,
    status: str,
    detail: str,
    url: str,
    started_at: float,
    **extra: object,
) -> dict[str, object]:
    return {
        "generated_at": utc_now_iso(),
        "status": status,
        "ok": status == "OK",
        "url": url,
        "duration_seconds": round(max(0.0, time.time() - started_at), 3),
        "detail": detail,
        **extra,
    }


def query_value(url: str, key: str, default: str = "") -> str:
    try:
        values = parse_qs(urlsplit(str(url)).query).get(key)
    except Exception:
        return default
    if not values:
        return default
    return unquote(str(values[0] or default)).strip()


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def required_text_present(text: str, required: str) -> bool:
    needle = normalize_text(required).casefold()
    return not needle or needle in normalize_text(text).casefold()


def visible_view_from_text(text: str, expected_view: str, *, max_lines: int = 120) -> str:
    expected = normalize_text(expected_view)
    if not expected:
        return ""
    for line in str(text or "").splitlines()[: max(1, int(max_lines))]:
        if normalize_text(line).casefold() == expected.casefold():
            return expected
    return ""


def visible_label_for_view(view: str) -> str:
    canonical = normalize_text(view)
    return VIEW_LABELS.get(canonical, canonical)


def forbidden_text_excerpt(text: str, forbidden: list[str], *, radius: int = 500) -> str:
    for token in forbidden:
        if not token:
            continue
        index = text.find(token)
        if index >= 0:
            start = max(0, index - int(radius))
            end = min(len(text), index + len(token) + int(radius))
            return text[start:end]
    return ""


def collect_rendered_text(page: object, *, timeout_ms: int = 3000) -> str:
    """Collect visible text from the Streamlit document and its component frames."""
    chunks: list[str] = []
    seen: set[str] = set()
    frames = list(getattr(page, "frames", []) or [])
    main_frame = getattr(page, "main_frame", None)
    if main_frame is not None:
        frames = [main_frame] + [frame for frame in frames if frame is not main_frame]
    deadline = time.monotonic() + max(0.1, float(timeout_ms) / 1000.0)
    for frame in frames:
        remaining_ms = int(max(0.0, deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            break
        try:
            # Reading innerText through the DOM is immediate even while
            # Streamlit is replacing blocks; locator.inner_text can spend its
            # whole timeout waiting for a transient body during a rerun.
            value = str(frame.evaluate("() => document.body ? document.body.innerText : ''") or "").strip()
        except Exception:
            try:
                value = str(frame.locator("body").inner_text(timeout=min(750, remaining_ms)) or "").strip()
            except Exception:
                continue
        if not value or value in seen:
            continue
        seen.add(value)
        chunks.append(value)
    if chunks:
        return "\n\n".join(chunks)
    try:
        remaining_ms = int(max(0.1, deadline - time.monotonic()) * 1000)
        return str(page.locator("body").inner_text(timeout=min(timeout_ms, remaining_ms)) or "")
    except Exception:
        return ""


def compact_frontend_message(value: object, *, max_length: int = 500) -> str:
    text = normalize_text(value)
    if len(text) <= max_length:
        return text
    return text[: max(0, max_length - 3)].rstrip() + "..."


def message_matches_any(text: str, patterns: list[str]) -> bool:
    value = str(text or "").lower()
    return any(str(pattern or "").lower() in value for pattern in patterns)


def unique_messages(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for message in messages:
        text = compact_frontend_message(message)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def soft_console_warning_family(message: str) -> str:
    for family, patterns in SOFT_CONSOLE_WARNING_FAMILY_PATTERNS.items():
        if message_matches_any(message, patterns):
            return family
    return "other_soft_warning"


def soft_console_error_family(message: str) -> str:
    for family, patterns in SOFT_CONSOLE_ERROR_FAMILY_PATTERNS.items():
        if message_matches_any(message, patterns):
            return family
    return "other_soft_error"


def message_family_counts(messages: list[str], *, classifier=soft_console_warning_family) -> dict[str, int]:
    counts: dict[str, int] = {}
    for message in messages:
        family = classifier(message)
        counts[family] = counts.get(family, 0) + 1
    return counts


def message_family_samples(
    messages: list[str],
    *,
    limit: int = MAX_FRONTEND_ERROR_SAMPLES,
    classifier=soft_console_warning_family,
    samples: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    samples = {} if samples is None else samples
    seen: dict[str, set[str]] = {}
    for message in messages:
        text = compact_frontend_message(message)
        if not text:
            continue
        family = classifier(text)
        family_samples = samples.setdefault(family, [])
        family_seen = seen.setdefault(family, set())
        key = text.lower()
        if key in family_seen or len(family_samples) >= max(1, int(limit)):
            continue
        family_seen.add(key)
        family_samples.append(text)
    return samples


def compact_frontend_stack(value: object, *, max_length: int = MAX_FRONTEND_ERROR_STACK_LENGTH) -> str:
    lines = [
        line.strip()
        for line in str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    text = "\n".join(lines)
    if len(text) <= max_length:
        return text
    return text[: max(0, max_length - 3)].rstrip() + "..."


def frontend_stack_top_frame(stack: str) -> str:
    lines = [line.strip() for line in str(stack or "").splitlines() if line.strip()]
    if len(lines) <= 1:
        return ""
    return compact_frontend_message(lines[1], max_length=300)


def detail_value_counts(details: list[dict[str, object]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for detail in details:
        value = compact_frontend_message(detail.get(key, ""), max_length=120)
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def page_error_detail(
    exc: object,
    *,
    url: str = "",
    phase: str = "",
    elapsed_seconds: float | None = None,
) -> dict[str, object]:
    raw_message = getattr(exc, "message", "") or str(exc)
    message = compact_frontend_message(raw_message)
    name = compact_frontend_message(getattr(exc, "name", "") or type(exc).__name__, max_length=120)
    if name and message and not message.lower().startswith(f"{name.lower()}:"):
        text = compact_frontend_message(f"{name}: {message}")
    else:
        text = compact_frontend_message(message or name)
    stack = compact_frontend_stack(getattr(exc, "stack", ""))
    family = soft_console_error_family(text)
    elapsed: float | None
    try:
        elapsed = round(max(0.0, float(elapsed_seconds)), 3) if elapsed_seconds is not None else None
    except (TypeError, ValueError):
        elapsed = None
    return {
        "type": name,
        "message": message,
        "text": text,
        "family": family,
        "soft": message_matches_any(text, SOFT_CONSOLE_ERROR_PATTERNS),
        "phase": compact_frontend_message(phase, max_length=120),
        "elapsed_seconds": elapsed,
        "url": compact_frontend_message(url, max_length=500),
        "stack_top_frame": frontend_stack_top_frame(stack),
        "stack": stack,
    }


def run_probe(
    *,
    url: str = DEFAULT_URL,
    min_text_length: int = 500,
    wait_seconds: float = 45.0,
    live_pulse_wait_seconds: float = 12.0,
    required_text: list[str] | None = None,
    forbidden_text: list[str] | None = None,
    screenshot_path: str | Path | None = None,
    viewport_width: int = 1280,
    viewport_height: int = 900,
    expected_final_timeframe: str = "",
    action_button_text: str = "",
    action_wait_seconds: float = 30.0,
    post_action_required_text: list[str] | None = None,
    diagnostic_auth: bool = True,
) -> dict[str, object]:
    started = time.time()
    phase_timings: dict[str, float] = {}
    http_ok, http_detail = wait_for_http(url, timeout_seconds=min(wait_seconds, 60.0))
    phase_timings["http_ready_seconds"] = round(time.time() - started, 3)
    if not http_ok:
        return build_result(status="FAIL", detail=f"App not reachable: {http_detail}", url=url, started_at=started)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return build_result(
            status="WARN",
            detail=f"Playwright unavailable: {type(exc).__name__}: {exc}",
            url=url,
            started_at=started,
            http_detail=http_detail,
        )

    expected_view = query_value(url, "view", "Centro")
    expected_selected_view = visible_label_for_view(expected_view)
    expected_symbol = query_value(url, "symbol", "ETH/USD")
    expected_market = query_value(url, "market", "")
    initial_timeframe = query_value(url, "tf", "")
    expected_timeframe = str(expected_final_timeframe or initial_timeframe).strip()
    # Streamlit 1.59 renders the selected combobox option as an input value,
    # which is intentionally absent from body.innerText. Selection remains a
    # separate, strict DOM assertion below; these are independent shell/content
    # landmarks.
    required = required_text or ["Live sin reload", "Roxy Trading"]
    forbidden = DEFAULT_FORBIDDEN_TEXT if forbidden_text is None else [item for item in forbidden_text if item]
    final_url = ""
    title = ""
    text = ""
    selected_view = ""
    page_visibility: dict[str, object] = {}
    screenshot_saved = ""
    action_performed = False
    console_messages: list[dict[str, str]] = []
    page_errors: list[str] = []
    page_error_details: list[dict[str, object]] = []
    probe_phase = {"name": "browser_start"}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": max(320, int(viewport_width)), "height": max(480, int(viewport_height))}
            )

            def record_console_message(message: object) -> None:
                message_type = str(getattr(message, "type", "") or "").lower()
                if message_type not in {"error", "warning"}:
                    return
                console_messages.append(
                    {
                        "type": message_type,
                        "text": compact_frontend_message(getattr(message, "text", "")),
                    }
                )

            def record_page_error(exc: object) -> None:
                detail = page_error_detail(
                    exc,
                    url=getattr(page, "url", ""),
                    phase=probe_phase.get("name", ""),
                    elapsed_seconds=time.time() - started,
                )
                page_error_details.append(detail)
                page_errors.append(str(detail.get("text") or ""))

            page.on("console", record_console_message)
            page.on("pageerror", record_page_error)
            try:
                probe_phase["name"] = "navigation"
                navigation_url = url_with_diagnostic_probe_token(url) if diagnostic_auth else url
                page.goto(navigation_url, wait_until="domcontentloaded", timeout=int(max(5.0, wait_seconds) * 1000))
                phase_timings["navigation_dom_seconds"] = round(time.time() - started, 3)
                deadline = time.time() + max(1.0, float(wait_seconds))
                probe_phase["name"] = "required_text_wait"
                while time.time() <= deadline:
                    text = collect_rendered_text(page, timeout_ms=2000)
                    missing = [item for item in required if item and not required_text_present(text, item)]
                    if len(text.strip()) >= int(min_text_length) and not missing:
                        break
                    time.sleep(1.0)
                phase_timings["initial_content_ready_seconds"] = round(time.time() - started, 3)
                if action_button_text:
                    probe_phase["name"] = "action_button_click"
                    action_button = page.get_by_role("button", name=action_button_text, exact=True)
                    if action_button.count():
                        action_button.click(timeout=int(max(5.0, wait_seconds) * 1000))
                    else:
                        # Streamlit expanders expose a clickable <summary>, not an ARIA button.
                        page.get_by_text(action_button_text, exact=True).click(
                            timeout=int(max(5.0, wait_seconds) * 1000)
                        )
                    action_performed = True
                    phase_timings["action_clicked_seconds"] = round(time.time() - started, 3)
                    post_deadline = time.time() + max(1.0, float(action_wait_seconds))
                    probe_phase["name"] = "post_action_wait"
                    while time.time() <= post_deadline:
                        text = collect_rendered_text(page, timeout_ms=2000)
                        missing_post = [
                            item
                            for item in (post_action_required_text or [])
                            if item and not required_text_present(text, item)
                        ]
                        if not missing_post:
                            break
                        time.sleep(1.0)
                    phase_timings["post_action_ready_seconds"] = round(time.time() - started, 3)
                    required.extend(
                        item for item in (post_action_required_text or []) if item and item not in required
                    )
                pulse_wait = max(0.0, float(live_pulse_wait_seconds))
                if pulse_wait:
                    probe_phase["name"] = "live_pulse_wait"
                    page.wait_for_timeout(int(pulse_wait * 1000))
                    text = collect_rendered_text(page, timeout_ms=3000)
                phase_timings["final_capture_ready_seconds"] = round(time.time() - started, 3)
                probe_phase["name"] = "state_capture"
                final_url = url_without_diagnostic_probe_token(page.url)
                title = page.title()
                selected_view = page.evaluate(
                    """
                    () => {
                        const selects = Array.from(document.querySelectorAll('[role="combobox"]'));
                        for (const el of selects) {
                            const label = String(el.getAttribute('aria-label') || '');
                            if (label.trim().toLowerCase() === 'vista') {
                                const value = String(el.value || el.getAttribute('value') || '').trim();
                                if (value) return value;
                            }
                            const match = label.match(/^Selected\\s+(.+?)\\.\\s+Vista$/i);
                            if (match && match[1]) return match[1].trim();
                        }
                        const radios = Array.from(document.querySelectorAll('[role="radio"], input[type="radio"]'));
                        for (const el of radios) {
                            const checked = el.getAttribute('aria-checked') === 'true' || el.checked === true;
                            if (!checked) continue;
                            const text = el.innerText || el.getAttribute('aria-label') || el.parentElement?.innerText || '';
                            return String(text).split('\\n')[0].trim();
                        }
                        return '';
                    }
                    """
                )
                page_visibility = page.evaluate(
                    """
                    () => {
                        const body = document.body;
                        const style = window.getComputedStyle(body);
                        const rect = body.getBoundingClientRect();
                        const app = document.querySelector('[data-testid="stAppViewContainer"]')
                            || document.querySelector('.stApp');
                        const appStyle = app ? window.getComputedStyle(app) : null;
                        const appRect = app ? app.getBoundingClientRect() : null;
                        const documentElement = document.documentElement;
                        return {
                            display: style.display,
                            visibility: style.visibility,
                            opacity: Number(style.opacity || 0),
                            width: rect.width,
                            height: rect.height,
                            app_display: appStyle ? appStyle.display : '',
                            app_visibility: appStyle ? appStyle.visibility : '',
                            app_opacity: appStyle ? Number(appStyle.opacity || 0) : 0,
                            app_width: appRect ? appRect.width : 0,
                            app_height: appRect ? appRect.height : 0,
                            client_width: documentElement.clientWidth,
                            scroll_width: documentElement.scrollWidth,
                            horizontal_overflow: Math.max(0, documentElement.scrollWidth - documentElement.clientWidth),
                        };
                    }
                    """
                )
                if screenshot_path:
                    probe_phase["name"] = "screenshot"
                    target = Path(screenshot_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(target), full_page=True)
                    screenshot_saved = str(target)
                probe_phase["name"] = "complete"
            finally:
                browser.close()
    except Exception as exc:
        return build_result(
            status="FAIL",
            detail=f"Render probe failed: {type(exc).__name__}: {exc}",
            url=url,
            started_at=started,
            http_detail=http_detail,
        )

    stripped = text.strip()
    text_length = len(stripped)
    missing_required = [item for item in required if item and not required_text_present(stripped, item)]
    body_hidden = bool(
        page_visibility.get("display") == "none"
        or page_visibility.get("visibility") == "hidden"
        or float(page_visibility.get("opacity") or 0) <= 0
        or page_visibility.get("app_display") == "none"
        or page_visibility.get("app_visibility") == "hidden"
        or float(page_visibility.get("app_opacity") or 0) <= 0
        or float(page_visibility.get("app_width") or 0) <= 0
        or float(page_visibility.get("app_height") or 0) <= 0
    )
    black_screen = text_length < int(min_text_length) or body_hidden
    horizontal_overflow = float(page_visibility.get("horizontal_overflow") or 0)
    final_view = query_value(final_url, "view")
    final_symbol = query_value(final_url, "symbol")
    final_market = query_value(final_url, "market")
    final_timeframe = query_value(final_url, "tf")
    selected_view_normalized = normalize_text(selected_view)
    expected_view_normalized = normalize_text(expected_view)
    expected_selected_view_normalized = normalize_text(expected_selected_view)
    if not selected_view_normalized:
        selected_view_normalized = visible_view_from_text(stripped, expected_selected_view_normalized)
    if not selected_view_normalized and query_value(final_url, "module") and final_view == expected_view:
        selected_view_normalized = expected_selected_view_normalized
    forbidden_found = [item for item in forbidden if item and item in stripped]
    forbidden_excerpt = forbidden_text_excerpt(stripped, forbidden_found)
    all_console_error_texts = [
        item.get("text", "")
        for item in console_messages
        if item.get("type") == "error"
    ]
    all_console_warning_texts = [
        item.get("text", "")
        for item in console_messages
        if item.get("type") == "warning"
    ]
    all_soft_console_error_texts = [
        text for text in all_console_error_texts if message_matches_any(text, SOFT_CONSOLE_ERROR_PATTERNS)
    ]
    all_blocking_console_error_texts = [
        text for text in all_console_error_texts if not message_matches_any(text, SOFT_CONSOLE_ERROR_PATTERNS)
    ]
    all_fatal_console_error_texts = [
        text for text in all_blocking_console_error_texts if message_matches_any(text, FATAL_CONSOLE_ERROR_PATTERNS)
    ]
    all_soft_console_warning_texts = [
        text for text in all_console_warning_texts if message_matches_any(text, SOFT_CONSOLE_WARNING_PATTERNS)
    ]
    all_blocking_console_warning_texts = [
        text for text in all_console_warning_texts if not message_matches_any(text, SOFT_CONSOLE_WARNING_PATTERNS)
    ]
    all_soft_page_error_texts = [
        text for text in page_errors if message_matches_any(text, SOFT_CONSOLE_ERROR_PATTERNS)
    ]
    all_blocking_page_error_texts = [
        text for text in page_errors if not message_matches_any(text, SOFT_CONSOLE_ERROR_PATTERNS)
    ]
    all_soft_page_error_details = [
        detail
        for detail in page_error_details
        if message_matches_any(str(detail.get("text") or ""), SOFT_CONSOLE_ERROR_PATTERNS)
    ]
    all_blocking_page_error_details = [
        detail
        for detail in page_error_details
        if not message_matches_any(str(detail.get("text") or ""), SOFT_CONSOLE_ERROR_PATTERNS)
    ]
    page_error_phase_counts = detail_value_counts(page_error_details, "phase")
    soft_page_error_phase_counts = detail_value_counts(all_soft_page_error_details, "phase")
    blocking_page_error_phase_counts = detail_value_counts(all_blocking_page_error_details, "phase")
    all_soft_console_warning_unique_texts = unique_messages(all_soft_console_warning_texts)
    all_soft_console_error_unique_texts = unique_messages(all_soft_console_error_texts)
    all_soft_page_error_unique_texts = unique_messages(all_soft_page_error_texts)
    soft_console_warning_family_counts = message_family_counts(all_soft_console_warning_texts)
    soft_console_warning_unique_family_counts = message_family_counts(all_soft_console_warning_unique_texts)
    soft_console_warning_family_samples = message_family_samples(all_soft_console_warning_texts)
    soft_console_error_family_counts = message_family_counts(
        all_soft_console_error_texts,
        classifier=soft_console_error_family,
    )
    soft_console_error_unique_family_counts = message_family_counts(
        all_soft_console_error_unique_texts,
        classifier=soft_console_error_family,
    )
    soft_console_error_family_samples = message_family_samples(
        all_soft_console_error_texts,
        classifier=soft_console_error_family,
    )
    soft_page_error_family_counts = message_family_counts(
        all_soft_page_error_texts,
        classifier=soft_console_error_family,
    )
    soft_page_error_unique_family_counts = message_family_counts(
        all_soft_page_error_unique_texts,
        classifier=soft_console_error_family,
    )
    soft_page_error_family_samples = message_family_samples(
        all_soft_page_error_texts,
        classifier=soft_console_error_family,
    )
    console_error_samples = all_console_error_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    console_warning_samples = all_console_warning_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    soft_console_warning_samples = all_soft_console_warning_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    soft_console_warning_unique_samples = all_soft_console_warning_unique_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    blocking_console_warning_samples = all_blocking_console_warning_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    soft_console_error_samples = all_soft_console_error_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    blocking_console_error_samples = all_blocking_console_error_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    fatal_console_error_samples = all_fatal_console_error_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    page_error_samples = page_errors[:MAX_FRONTEND_ERROR_SAMPLES]
    soft_page_error_samples = all_soft_page_error_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    blocking_page_error_samples = all_blocking_page_error_texts[:MAX_FRONTEND_ERROR_SAMPLES]
    page_error_detail_samples = page_error_details[:MAX_FRONTEND_ERROR_SAMPLES]
    soft_page_error_detail_samples = all_soft_page_error_details[:MAX_FRONTEND_ERROR_SAMPLES]
    blocking_page_error_detail_samples = all_blocking_page_error_details[:MAX_FRONTEND_ERROR_SAMPLES]
    console_error_count = len(all_console_error_texts)
    console_warning_count = len(all_console_warning_texts)
    soft_console_warning_count = len(all_soft_console_warning_texts)
    soft_console_warning_unique_count = len(all_soft_console_warning_unique_texts)
    blocking_console_warning_count = len(all_blocking_console_warning_texts)
    soft_console_error_count = len(all_soft_console_error_texts)
    blocking_console_error_count = len(all_blocking_console_error_texts)
    fatal_console_error_count = len(all_fatal_console_error_texts)
    page_error_count = len(page_errors)
    soft_page_error_count = len(all_soft_page_error_texts)
    blocking_page_error_count = len(all_blocking_page_error_texts)
    view_persisted = final_view == expected_view
    selected_view_persisted = bool(
        expected_selected_view_normalized and selected_view_normalized == expected_selected_view_normalized
    )
    symbol_persisted = final_symbol.upper() == expected_symbol.upper()
    market_persisted = not expected_market or final_market.lower() == expected_market.lower()
    timeframe_persisted = not expected_timeframe or final_timeframe.lower() == expected_timeframe.lower()
    issues: list[str] = []
    if black_screen:
        if text_length < int(min_text_length):
            issues.append(f"text_length {text_length}<{int(min_text_length)}")
        if body_hidden:
            issues.append("document or app container hidden or zero-size")
    if missing_required:
        issues.append("missing text " + ", ".join(missing_required))
    if horizontal_overflow > 4:
        issues.append(f"horizontal overflow {horizontal_overflow:.0f}px")
    if not view_persisted:
        issues.append(f"view not persisted {final_view or '-'}!={expected_view}")
    if not selected_view_persisted:
        issues.append(
            f"selected view lost {selected_view_normalized or '-'}!={expected_selected_view_normalized}"
        )
    if not symbol_persisted:
        issues.append(f"symbol not persisted {final_symbol or '-'}!={expected_symbol}")
    if not market_persisted:
        issues.append(f"market not persisted {final_market or '-'}!={expected_market}")
    if not timeframe_persisted:
        issues.append(f"timeframe not persisted {final_timeframe or '-'}!={expected_timeframe}")
    if forbidden_found:
        issues.append("forbidden text " + ", ".join(forbidden_found[:3]))
    frontend_issues: list[str] = []
    if blocking_page_error_count:
        frontend_issues.append(f"page errors {blocking_page_error_count}")
    if fatal_console_error_count:
        frontend_issues.append(f"fatal console errors {fatal_console_error_count}")
    elif blocking_console_error_count:
        frontend_issues.append(f"console errors {blocking_console_error_count}")
    if soft_page_error_count:
        frontend_issues.append(f"soft page errors {soft_page_error_count}")
    if soft_console_error_count:
        frontend_issues.append(f"soft console errors {soft_console_error_count}")
    if blocking_console_warning_count:
        frontend_issues.append(f"console warnings {blocking_console_warning_count}")
    if issues:
        status = "FAIL"
        detail = "render issue: " + "; ".join(issues + frontend_issues)
    elif blocking_page_error_count or fatal_console_error_count:
        status = "FAIL"
        detail = "frontend issue: " + "; ".join(frontend_issues)
    elif blocking_console_error_count or blocking_console_warning_count:
        status = "WARN"
        detail = "frontend warning: " + "; ".join(frontend_issues)
    else:
        status = "OK"
        detail = f"render OK {text_length} chars, URL/state persisted"
        if frontend_issues:
            detail += "; " + "; ".join(frontend_issues)
    return build_result(
        status=status,
        detail=detail,
        url=url,
        started_at=started,
        http_detail=http_detail,
        final_url=final_url,
        title=title,
        text_length=text_length,
        min_text_length=int(min_text_length),
        contract_version=2,
        black_screen=black_screen,
        body_hidden=body_hidden,
        page_visibility=page_visibility,
        viewport_width=max(320, int(viewport_width)),
        viewport_height=max(480, int(viewport_height)),
        expected_view=expected_view,
        expected_selected_view=expected_selected_view_normalized,
        final_view=final_view,
        selected_view=selected_view_normalized,
        required_text=required,
        missing_required_text=missing_required,
        forbidden_text=forbidden,
        forbidden_text_found=forbidden_found,
        forbidden_text_excerpt=forbidden_excerpt,
        live_no_reload="Live sin reload" in stripped,
        live_pulse_wait_seconds=float(live_pulse_wait_seconds),
        action_button_text=action_button_text,
        action_performed=action_performed,
        action_wait_seconds=float(action_wait_seconds),
        diagnostic_auth=bool(diagnostic_auth),
        phase_timings=phase_timings,
        view_persisted=view_persisted,
        selected_view_persisted=selected_view_persisted,
        expected_symbol=expected_symbol,
        final_symbol=final_symbol,
        selected_symbol=final_symbol,
        symbol_persisted=symbol_persisted,
        expected_market=expected_market,
        final_market=final_market,
        selected_market=final_market,
        market_persisted=market_persisted,
        expected_timeframe=expected_timeframe,
        initial_timeframe=initial_timeframe,
        final_timeframe=final_timeframe,
        selected_timeframe=final_timeframe,
        timeframe_persisted=timeframe_persisted,
        frontend_error_status=(
            "FAIL"
            if blocking_page_error_count or fatal_console_error_count
            else "WARN" if blocking_console_error_count else "OK"
        ),
        console_error_count=console_error_count,
        console_warning_count=console_warning_count,
        blocking_console_warning_count=blocking_console_warning_count,
        soft_console_warning_count=soft_console_warning_count,
        soft_console_warning_unique_count=soft_console_warning_unique_count,
        soft_console_warning_family_counts=soft_console_warning_family_counts,
        soft_console_warning_unique_family_counts=soft_console_warning_unique_family_counts,
        soft_console_warning_family_samples=soft_console_warning_family_samples,
        soft_console_error_family_counts=soft_console_error_family_counts,
        soft_console_error_unique_family_counts=soft_console_error_unique_family_counts,
        soft_console_error_family_samples=soft_console_error_family_samples,
        soft_page_error_family_counts=soft_page_error_family_counts,
        soft_page_error_unique_family_counts=soft_page_error_unique_family_counts,
        soft_page_error_family_samples=soft_page_error_family_samples,
        page_error_phase_counts=page_error_phase_counts,
        soft_page_error_phase_counts=soft_page_error_phase_counts,
        blocking_page_error_phase_counts=blocking_page_error_phase_counts,
        blocking_console_error_count=blocking_console_error_count,
        soft_console_error_count=soft_console_error_count,
        fatal_console_error_count=fatal_console_error_count,
        page_error_count=page_error_count,
        blocking_page_error_count=blocking_page_error_count,
        soft_page_error_count=soft_page_error_count,
        console_error_samples=console_error_samples,
        console_warning_samples=console_warning_samples,
        blocking_console_warning_samples=blocking_console_warning_samples,
        soft_console_warning_samples=soft_console_warning_samples,
        soft_console_warning_unique_samples=soft_console_warning_unique_samples,
        blocking_console_error_samples=blocking_console_error_samples,
        soft_console_error_samples=soft_console_error_samples,
        fatal_console_error_samples=fatal_console_error_samples,
        page_error_samples=page_error_samples,
        blocking_page_error_samples=blocking_page_error_samples,
        soft_page_error_samples=soft_page_error_samples,
        page_error_detail_samples=page_error_detail_samples,
        blocking_page_error_detail_samples=blocking_page_error_detail_samples,
        soft_page_error_detail_samples=soft_page_error_detail_samples,
        text_sample=stripped[:1200],
        screenshot_path=screenshot_saved,
    )


def write_report(result: dict[str, object], path: str | Path = DEFAULT_JSON_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(result, indent=2, sort_keys=True), target)
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Roxy dashboard in a real browser and verify it is not blank.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--json-path", default=str(DEFAULT_JSON_PATH))
    parser.add_argument("--screenshot-path", default="")
    parser.add_argument("--min-text-length", type=int, default=500)
    parser.add_argument("--wait-seconds", type=float, default=45.0)
    parser.add_argument("--live-pulse-wait-seconds", type=float, default=12.0)
    parser.add_argument("--action-button-text", default="")
    parser.add_argument("--action-wait-seconds", type=float, default=30.0)
    parser.add_argument("--post-action-required-text", action="append", default=None)
    parser.add_argument("--no-diagnostic-auth", action="store_true")
    parser.add_argument("--required-text", action="append", default=None)
    parser.add_argument("--forbidden-text", action="append", default=None)
    parser.add_argument("--viewport-width", type=int, default=1280)
    parser.add_argument("--viewport-height", type=int, default=900)
    parser.add_argument(
        "--expected-final-timeframe",
        default="",
        help="Expected final tf after an intentional UI or voice navigation action.",
    )
    parser.add_argument("--no-fail", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_probe(
        url=args.url,
        min_text_length=args.min_text_length,
        wait_seconds=args.wait_seconds,
        live_pulse_wait_seconds=args.live_pulse_wait_seconds,
        required_text=args.required_text,
        forbidden_text=args.forbidden_text,
        screenshot_path=args.screenshot_path or None,
        viewport_width=args.viewport_width,
        viewport_height=args.viewport_height,
        expected_final_timeframe=args.expected_final_timeframe,
        action_button_text=args.action_button_text,
        action_wait_seconds=args.action_wait_seconds,
        post_action_required_text=args.post_action_required_text,
        diagnostic_auth=not args.no_diagnostic_auth,
    )
    path = write_report(result, args.json_path)
    print(f"Dashboard render probe: {result['status']} | {result['detail']}")
    print(f"JSON: {path}")
    if str(result.get("status")) == "FAIL" and not args.no_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
