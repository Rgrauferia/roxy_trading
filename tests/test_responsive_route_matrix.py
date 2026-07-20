import subprocess
import sys
from pathlib import Path

from tools.responsive_route_matrix import (
    INITIAL_CONTENT_SLO_SECONDS,
    RESPONSIVE_MATRIX_CONTRACT,
    ROUTES,
    parse_names,
    responsive_result_ok,
    run_responsive_matrix,
)


def good_probe(**kwargs):
    return {
        "status": "OK",
        "detail": "render OK",
        "duration_seconds": 1.2,
        "phase_timings": {"navigation_dom_seconds": 0.4, "initial_content_ready_seconds": 1.0},
        "page_visibility": {"horizontal_overflow": 0},
        "blocking_console_error_count": 0,
        "blocking_page_error_count": 0,
        "view_persisted": True,
        "symbol_persisted": True,
        "market_persisted": True,
        "timeframe_persisted": True,
        "final_url": kwargs["url"],
        "screenshot_path": str(kwargs.get("screenshot_path") or ""),
    }


def test_responsive_matrix_counts_every_route_device_pair():
    waits = []

    def recording_probe(**kwargs):
        waits.append(kwargs["wait_seconds"])
        return good_probe(**kwargs)

    report = run_responsive_matrix(
        base_url="http://127.0.0.1:3000/",
        route_names=["news", "portfolio"],
        device_names=["desktop", "mobile"],
        probe=recording_probe,
    )

    assert report["contract_version"] == RESPONSIVE_MATRIX_CONTRACT
    assert report["status"] == "OK"
    assert report["checked"] == 4
    assert report["passed"] == 4
    assert report["performance"]["measured"] == 4
    assert report["performance"]["p95_initial_content_seconds"] == 1.0
    assert report["performance"]["within_slo"] == 4
    assert report["devices"]["mobile"] == {"checked": 2, "passed": 2}
    assert waits == [24.0, 24.0, 45.0, 45.0]


def test_diagnostics_route_has_cold_contract_scan_budget():
    waits = []

    def recording_probe(**kwargs):
        waits.append(kwargs["wait_seconds"])
        return good_probe(**kwargs)

    report = run_responsive_matrix(
        base_url="http://127.0.0.1:3000/",
        route_names=["diagnostics"],
        device_names=["desktop"],
        probe=recording_probe,
    )

    assert report["status"] == "OK"
    assert waits == [45.0]


def test_responsive_matrix_covers_daily_routes_options_context_and_true_crypto_20m_route():
    assert len(ROUTES) == 14
    assert "options_stock" in ROUTES
    assert "options_crypto" in ROUTES
    assert "symbol=AAPL&market=stock&tf=1h" in ROUTES["options_stock"]["query"]
    assert "symbol=BTC%2FUSD&market=crypto&tf=20m" in ROUTES["options_crypto"]["query"]
    assert "tf=20m" in ROUTES["crypto"]["query"]
    assert "Noticias · LINK/USD" in ROUTES["news"]["required"]
    assert {"calendar", "activity", "memory", "notifications"}.issubset(ROUTES)
    assert "CALENDAR_EVENTS_ONLY" in ROUTES["calendar"]["required"]


def test_responsive_result_rejects_overflow_or_lost_context():
    result = good_probe(url="http://localhost/")
    result["page_visibility"]["horizontal_overflow"] = 12
    assert responsive_result_ok(result) is False
    result["page_visibility"]["horizontal_overflow"] = 0
    result["symbol_persisted"] = False
    assert responsive_result_ok(result) is False


def test_responsive_result_rejects_empty_chart_extent_warning():
    result = good_probe(url="http://localhost/")
    result["soft_console_warning_unique_family_counts"] = {"empty_chart_extent": 1}

    assert responsive_result_ok(result) is False


def test_responsive_result_rejects_slow_initial_content():
    result = good_probe(url="http://localhost/")
    result["phase_timings"]["initial_content_ready_seconds"] = INITIAL_CONTENT_SLO_SECONDS + 0.1

    assert responsive_result_ok(result) is False


def test_responsive_matrix_surfaces_failed_probe_without_hiding_other_rows():
    calls = {"count": 0}

    def probe(**kwargs):
        calls["count"] += 1
        result = good_probe(**kwargs)
        if calls["count"] == 2:
            result["blocking_console_error_count"] = 1
        return result

    report = run_responsive_matrix(
        base_url="http://127.0.0.1:3000/",
        route_names=["news"],
        device_names=["desktop", "ipad", "mobile"],
        probe=probe,
    )

    assert report["status"] == "FAIL"
    assert report["checked"] == 3
    assert report["failed"] == 1
    assert [row["status"] for row in report["rows"]] == ["OK", "FAIL", "OK"]


def test_parse_names_rejects_unknown_values():
    try:
        parse_names("mobile,television", {"mobile": (390, 844)})
    except ValueError as exc:
        assert "television" in str(exc)
    else:
        raise AssertionError("Unknown responsive targets must fail closed")


def test_responsive_matrix_script_runs_directly_outside_project_cwd(tmp_path):
    script = Path(__file__).resolve().parents[1] / "tools" / "responsive_route_matrix.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Validate canonical Roxy routes" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr
