from datetime import datetime, timezone

from tools.dual_chart_crosshair_probe import evaluate_crosshair_contract
from tools.roxy_realtime_check import validate_dual_chart_crosshair_probe_report


def test_dual_chart_crosshair_contract_accepts_one_way_link_without_echo():
    ok, issues = evaluate_crosshair_contract(
        [
            {"timeframe": "15m", "channel_state": "ready", "linked_timeframe": "", "label": "Cursor enlazado"},
            {"timeframe": "1h", "channel_state": "ready", "linked_timeframe": "15m", "label": "Cursor 15m ↔ 1h"},
        ]
    )
    assert ok is True
    assert issues == []


def test_dual_chart_crosshair_contract_rejects_echo_and_missing_target_link():
    ok, issues = evaluate_crosshair_contract(
        [
            {"timeframe": "15m", "channel_state": "ready", "linked_timeframe": "1h", "label": "Cursor 1h ↔ 15m"},
            {"timeframe": "1h", "channel_state": "unavailable", "linked_timeframe": "", "label": "Cursor local"},
        ]
    )
    assert ok is False
    assert any("eco detectado" in issue for issue in issues)
    assert any("1h no recibio" in issue for issue in issues)


def test_dual_chart_crosshair_report_is_visible_to_diagnostics(tmp_path):
    path = tmp_path / "probe.json"
    path.write_text(
        '{"generated_at":"2026-07-19T21:00:00+00:00","status":"OK","ok":true,'
        '"detail":"cursor 15m→1h enlazado sin eco","states":[],"console_errors":[]}',
        encoding="utf-8",
    )
    status = validate_dual_chart_crosshair_probe_report(
        path,
        now=datetime(2026, 7, 19, 21, 5, tzinfo=timezone.utc),
    )
    assert status["status"] == "OK"
    assert status["probe_status"] == "OK"
