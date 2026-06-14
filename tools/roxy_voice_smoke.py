from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


DEFAULT_VOICE_BASE = "http://127.0.0.1:8010"
DEFAULT_TRADE_URL = "http://127.0.0.1:8501/?view=Activo&symbol=SPY&market=stock&tf=1h"


@dataclass(frozen=True)
class SmokeTarget:
    name: str
    url: str


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    url: str
    ok: bool
    status_code: int | None = None
    detail: str = ""
    elapsed_ms: float = 0.0


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def build_targets(voice_base: str = DEFAULT_VOICE_BASE, trade_url: str = DEFAULT_TRADE_URL) -> list[SmokeTarget]:
    base = normalize_base_url(voice_base)
    return [
        SmokeTarget("health", f"{base}/health"),
        SmokeTarget("roxy_live", f"{base}/roxy-live"),
        SmokeTarget("sessions", f"{base}/v1/assist/sessions?language=es&limit=1"),
        SmokeTarget("trade_dashboard", trade_url),
    ]


def fetch_url(url: str, timeout: float = 5.0) -> tuple[int, str, float]:
    started = time.perf_counter()
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), body, (time.perf_counter() - started) * 1000
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body, (time.perf_counter() - started) * 1000


def _loads_json(body: str) -> dict[str, Any]:
    payload = json.loads(body)
    return payload if isinstance(payload, dict) else {}


def _check_payload(name: str, body: str) -> tuple[bool, str]:
    lowered = body.lower()
    if name == "health":
        payload = _loads_json(body)
        if payload.get("status") == "ok":
            return True, "Roxy Live health OK"
        return False, "health JSON did not report status=ok"

    if name == "roxy_live":
        if "roxy live" in lowered or "roxy" in lowered:
            return True, "Roxy Live page loaded"
        return False, "Roxy Live page signature missing"

    if name == "sessions":
        payload = _loads_json(body)
        has_sessions = isinstance(payload.get("recent_sessions"), list)
        has_actions = isinstance(payload.get("suggested_actions"), list)
        has_count = "session_count" in payload
        if has_sessions and (has_actions or has_count):
            return True, "Roxy session context available"
        return False, "session context JSON missing expected fields"

    if name == "trade_dashboard":
        if "<html" in lowered and ("streamlit" in lowered or "roxy" in lowered):
            return True, "Roxy Trade dashboard loaded"
        return False, "dashboard HTML signature missing"

    return False, f"unknown smoke target: {name}"


def run_check(target: SmokeTarget, timeout: float = 5.0) -> SmokeCheck:
    try:
        status_code, body, elapsed_ms = fetch_url(target.url, timeout=timeout)
        if status_code != 200:
            return SmokeCheck(
                name=target.name,
                url=target.url,
                ok=False,
                status_code=status_code,
                detail=f"unexpected HTTP status {status_code}",
                elapsed_ms=elapsed_ms,
            )
        ok, detail = _check_payload(target.name, body)
        return SmokeCheck(
            name=target.name,
            url=target.url,
            ok=ok,
            status_code=status_code,
            detail=detail,
            elapsed_ms=elapsed_ms,
        )
    except (TimeoutError, URLError, json.JSONDecodeError, OSError) as exc:
        return SmokeCheck(name=target.name, url=target.url, ok=False, detail=str(exc))


def run_smoke(
    voice_base: str = DEFAULT_VOICE_BASE,
    trade_url: str = DEFAULT_TRADE_URL,
    timeout: float = 5.0,
) -> list[SmokeCheck]:
    return [run_check(target, timeout=timeout) for target in build_targets(voice_base=voice_base, trade_url=trade_url)]


def summarize_checks(checks: list[SmokeCheck]) -> dict[str, Any]:
    passed = sum(1 for check in checks if check.ok)
    failed = len(checks) - passed
    return {
        "ok": failed == 0,
        "passed": passed,
        "failed": failed,
        "checks": [asdict(check) for check in checks],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke check Roxy Live voice endpoints and the Roxy Trade dashboard.")
    parser.add_argument("--voice-base", default=DEFAULT_VOICE_BASE)
    parser.add_argument("--trade-url", default=DEFAULT_TRADE_URL)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    checks = run_smoke(voice_base=args.voice_base, trade_url=args.trade_url, timeout=args.timeout)
    summary = summarize_checks(checks)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        status = "OK" if summary["ok"] else "FAIL"
        print(f"Roxy smoke: {status} | passed {summary['passed']} | failed {summary['failed']}")
        for check in checks:
            marker = "OK" if check.ok else "FAIL"
            status_code = check.status_code if check.status_code is not None else "-"
            print(f"{marker} {check.name} HTTP {status_code} {check.elapsed_ms:.0f}ms | {check.detail}")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
