import json
from datetime import datetime, timezone

from alert_quality import (
    alert_quality_entry,
    summarize_quality_history,
    top_opportunity_snapshot,
    waiting_diagnostic_category,
    write_alert_quality_report,
)


def test_alert_quality_entry_classifies_ready_and_waiting_states():
    ready = alert_quality_entry(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "alert_gate_summary": {
                "total_opportunities": 3,
                "notifications_ready": 1,
                "alert_count": 1,
                "watch_count": 2,
                "avg_readiness": 88.4,
                "top_gate": "ALERT_READY",
                "top_gate_label": "Listo para operar manual",
            },
        },
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    waiting = alert_quality_entry(
        {
            "alert_gate_summary": {
                "total_opportunities": 3,
                "notifications_ready": 0,
                "top_gate": "WAIT_15M_ENTRY",
                "top_blocker": "15m da entrada: WAIT",
            }
        },
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )

    assert ready["state"] == "READY"
    assert ready["notifications_ready"] == 1
    assert waiting["state"] == "WAITING"
    assert waiting["top_blocker"] == "15m da entrada: WAIT"


def test_summarize_quality_history_tracks_waiting_streak():
    summary = summarize_quality_history(
        [
            {"state": "READY", "notifications_ready": 1, "avg_readiness": 90},
            {"state": "WAITING", "notifications_ready": 0, "avg_readiness": 60},
            {"state": "WAITING", "notifications_ready": 0, "avg_readiness": 62, "top_blocker": "Volumen acompana"},
        ]
    )

    assert summary["ready_rate"] == 0.3333
    assert summary["waiting_streak"] == 2
    assert summary["current_streak_state"] == "WAITING"
    assert summary["avg_readiness"] == 70.7
    assert summary["latest_readiness"] == 62.0
    assert summary["readiness_delta"] == -28.0
    assert summary["dominant_blocker"] == {"name": "Volumen acompana", "count": 1}


def test_summarize_quality_history_flags_persistent_blocker():
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 8,
            "avg_readiness": 61,
            "top_blocker": "15m da entrada: WAIT",
            "top_gate_label": "Esperar entrada 15m",
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(12)
    ]

    summary = summarize_quality_history(rows)

    assert summary["latest_top_blocker_streak"] == 12
    assert summary["latest_top_gate_streak"] == 12
    assert summary["persistent_blocker"] == "15m da entrada: WAIT"
    assert summary["diagnostic_severity"] == "WATCH"
    assert summary["diagnostic_label"] == "Esperando gatillo x12"
    assert summary["blocker_category"] == "MARKET_TRIGGER_WAIT"
    assert "15m confirme" in summary["recommended_action"]
    assert summary["persistent_blocker_minutes"] == 11.0
    assert summary["readiness_delta"] == 0.0
    assert summary["dominant_blocker"] == {"name": "15m da entrada: WAIT", "count": 12}
    assert summary["dominant_gate"] == {"name": "Esperar entrada 15m", "count": 12}


def test_summarize_quality_history_escalates_unclassified_persistent_blocker():
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 8,
            "avg_readiness": 51,
            "top_blocker": "Filtro historico: no elegible",
            "top_gate": "FILTERED_HISTORY",
            "top_gate_label": "Filtro historico",
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(12)
    ]

    summary = summarize_quality_history(rows)

    assert summary["diagnostic_severity"] == "ATTENTION"
    assert summary["diagnostic_label"] == "Bloqueador x12"
    assert summary["blocker_category"] == "UNCLASSIFIED_WAIT"
    assert summary["diagnostic_detail"] == "Filtro historico: no elegible"


def test_waiting_diagnostic_category_detects_realtime_block_before_market_wait():
    category = waiting_diagnostic_category(
        {
            "state": "WAITING",
            "blocked_realtime_count": 2,
            "data_alerts_allowed": True,
            "realtime_alerts_allowed": True,
            "top_gate": "WAIT_15M_ENTRY",
        },
        "15m da entrada: WAIT",
        "Esperar entrada 15m",
        blocker_streak=12,
    )

    assert category["category"] == "REALTIME_BLOCK"
    assert category["severity"] == "ATTENTION"


def test_top_opportunity_snapshot_extracts_compact_diagnostic_fields():
    snapshot = top_opportunity_snapshot(
        {
            "top_opportunities": [
                {
                    "symbol": "AMAT",
                    "market": "stock",
                    "ai_action": "WATCH",
                    "trade_decision": "WAIT",
                    "alert_gate": "WAIT_15M_ENTRY",
                    "alert_readiness_score": 63.6,
                    "alert_quality": "C",
                    "alert_primary_blocker": "15m da entrada: WAIT",
                    "alert_next_action": "Esperar gatillo BUY en 15m.",
                    "alert_blockers": ["15m da entrada: WAIT", "Volumen acompana: 0.31x"],
                }
            ]
        }
    )

    assert snapshot["symbol"] == "AMAT"
    assert snapshot["gate"] == "WAIT_15M_ENTRY"
    assert snapshot["readiness"] == 63.6
    assert snapshot["primary_blocker"] == "15m da entrada: WAIT"
    assert snapshot["blockers"] == ["15m da entrada: WAIT", "Volumen acompana: 0.31x"]


def test_write_alert_quality_report_persists_report_and_history(tmp_path):
    report_path = tmp_path / "alert_quality.json"
    history_path = tmp_path / "alert_quality_history.jsonl"

    report = write_alert_quality_report(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "alert_gate_summary": {
                "total_opportunities": 2,
                "notifications_ready": 0,
                "avg_readiness": 61.3,
                "top_gate_label": "Esperar entrada 15m",
            },
            "top_opportunities": [
                {
                    "symbol": "AMAT",
                    "alert_gate": "WAIT_15M_ENTRY",
                    "alert_primary_blocker": "15m da entrada: WAIT",
                    "alert_next_action": "Esperar gatillo BUY en 15m.",
                    "alert_readiness_score": 63.6,
                }
            ],
        },
        report_path=report_path,
        history_path=history_path,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )

    assert report["summary"]["state"] == "WAITING"
    assert report["latest_entry"]["top_symbol"] == "AMAT"
    assert report["entry"]["top_setup"]["primary_blocker"] == "15m da entrada: WAIT"
    assert json.loads(report_path.read_text())["history_count"] == 1
    assert json.loads(report_path.read_text())["latest_entry"]["top_next_action"] == "Esperar gatillo BUY en 15m."
    assert len(history_path.read_text().splitlines()) == 1
