import json
from datetime import datetime, timedelta, timezone

from alert_quality import (
    DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN,
    DEFAULT_HISTORY_BUDGET_NEXT_APPEND_GUARD_MULTIPLIER,
    DEFAULT_HISTORY_BUDGET_WARN_RATIO,
    DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO,
    append_history,
    alert_silence_diagnostic,
    alert_quality_entry,
    alert_quality_label_tone,
    alert_quality_report_status,
    chart_contract_coverage_snapshot,
    compact_history_entry_for_storage,
    market_alert_coverage_snapshot,
    opportunity_watchlist_snapshot,
    rotation_candidate_summary,
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


def test_alert_quality_entry_treats_empty_scan_as_no_setups_before_system_block():
    entry = alert_quality_entry(
        {
            "alert_gate_summary": {
                "total_opportunities": 0,
                "notifications_ready": 0,
                "alert_count": 0,
                "watch_count": 0,
            },
            "source_freshness": {"alerts_allowed": True},
            "realtime_health": {"alerts_allowed": False},
        },
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )

    assert entry["state"] == "NO_SETUPS"
    assert entry["total_opportunities"] == 0


def test_alert_quality_entry_blocks_stock_when_realtime_stock_is_disabled():
    entry = alert_quality_entry(
        {
            "alert_gate_summary": {
                "total_opportunities": 1,
                "notifications_ready": 0,
                "top_gate": "WAIT_15M_ENTRY",
                "top_blocker": "15m da entrada: WAIT",
            },
            "realtime_health": {
                "label": "Premium bloqueado",
                "alerts_allowed": True,
                "stock_alerts_allowed": False,
                "crypto_alerts_allowed": True,
                "market_realtime": {"blocked_markets": ["stock", "options"]},
            },
            "opportunities": [
                {
                    "symbol": "WMT",
                    "market": "stock",
                    "ai_action": "WATCH",
                    "alert_gate": "WAIT_15M_ENTRY",
                    "alert_readiness_score": 60,
                    "alert_quality": "C",
                    "alert_primary_blocker": "15m da entrada: WAIT",
                }
            ],
        },
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )

    assert entry["state"] == "BLOCKED_REALTIME"
    assert entry["blocked_realtime_count"] == 1
    assert entry["realtime_alerts_allowed"] is True
    assert entry["realtime_stock_alerts_allowed"] is False
    assert entry["realtime_crypto_alerts_allowed"] is True
    assert entry["session_stock_alerts_allowed"] is True
    assert entry["stock_alerts_allowed"] is False
    assert entry["crypto_alerts_allowed"] is True
    assert entry["options_alerts_allowed"] is False
    assert entry["realtime_blocked_markets"] == ["stock", "options"]
    assert entry["market_counts"] == {"stock": 1}
    assert entry["allowed_markets"] == ["crypto"]
    assert entry["missing_allowed_markets"] == ["crypto"]
    assert entry["operable_market_count"] == 0
    assert entry["blocked_market_count"] == 1
    assert entry["market_coverage_label"] == "Cripto permitido sin candidatos"


def test_market_alert_coverage_distinguishes_allowed_crypto_candidates():
    coverage = market_alert_coverage_snapshot(
        {
            "opportunities": [
                {"symbol": "WMT", "market": "stock", "ai_action": "WATCH"},
                {"symbol": "BTC/USD", "market": "crypto", "ai_action": "WATCH"},
            ]
        },
        realtime_stock_allowed=False,
        realtime_crypto_allowed=True,
        blocked_markets=["stock", "options"],
    )

    assert coverage["market_counts"] == {"crypto": 1, "stock": 1}
    assert coverage["allowed_markets"] == ["crypto"]
    assert coverage["missing_allowed_markets"] == []
    assert coverage["operable_market_count"] == 1
    assert coverage["blocked_market_count"] == 1
    assert coverage["market_coverage_label"] == "Cripto operable"
    assert "Priorizar candidatos cripto" in coverage["market_coverage_action"]


def test_chart_contract_coverage_distinguishes_live_and_blocked_charts():
    coverage = chart_contract_coverage_snapshot(
        {
            "opportunities": [
                {
                    "symbol": "ETH/USD",
                    "market": "crypto",
                    "chart_data_gate": "LIVE_DATA_OK",
                    "chart_operable": True,
                },
                {
                    "symbol": "WMT",
                    "market": "stock",
                    "chart_data_gate": "CHART_CONTRACT_MISSING",
                    "chart_operable": None,
                },
                {"symbol": "PEP", "market": "stock"},
            ]
        }
    )

    assert coverage["chart_contract_total_count"] == 3
    assert coverage["chart_contract_checked_count"] == 2
    assert coverage["chart_contract_operable_count"] == 1
    assert coverage["chart_contract_blocked_count"] == 2
    assert coverage["chart_contract_missing_count"] == 2
    assert coverage["chart_contract_blocked_markets"] == ["options", "stock"]
    assert coverage["chart_contract_market_counts"] == {"crypto": 1, "stock": 2}
    assert coverage["chart_contract_market_operable_counts"] == {"crypto": 1}
    assert coverage["chart_contract_market_blocked_counts"] == {"stock": 2}
    assert coverage["chart_contract_gate_counts"] == {"CHART_CONTRACT_MISSING": 2, "LIVE_DATA_OK": 1}
    assert coverage["chart_contract_operable_symbols"] == ["ETH/USD"]
    assert coverage["chart_contract_blocked_symbols"] == [
        "WMT: CHART_CONTRACT_MISSING",
        "PEP: CHART_CONTRACT_MISSING",
    ]
    assert coverage["chart_contract_label"] == "Graficas parciales"
    assert "LIVE_DATA_OK" in coverage["chart_contract_action"]


def test_chart_contract_coverage_counts_live_price_gates():
    coverage = chart_contract_coverage_snapshot(
        {
            "opportunities": [
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "chart_data_gate": "LIVE_PRICE_OK",
                    "chart_operable": True,
                },
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "chart_data_gate": "NO_TRADE_FROM_PUBLIC_PRICE",
                    "chart_operable": False,
                },
            ]
        }
    )

    assert coverage["chart_contract_operable_count"] == 1
    assert coverage["chart_contract_blocked_count"] == 1
    assert coverage["chart_contract_gate_counts"] == {
        "LIVE_PRICE_OK": 1,
        "NO_TRADE_FROM_PUBLIC_PRICE": 1,
    }
    assert coverage["chart_contract_operable_symbols"] == ["BTC/USD"]
    assert coverage["chart_contract_blocked_symbols"] == ["AAPL: NO_TRADE_FROM_PUBLIC_PRICE"]


def test_chart_contract_coverage_does_not_block_market_with_live_candidate():
    coverage = chart_contract_coverage_snapshot(
        {
            "opportunities": [
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "chart_data_gate": "LIVE_DATA_OK",
                    "chart_operable": True,
                },
                {
                    "symbol": "SOL/USD",
                    "market": "crypto",
                    "chart_data_gate": "CHART_CONTRACT_MISSING",
                    "chart_operable": None,
                },
                {
                    "symbol": "BAC",
                    "market": "stock",
                    "chart_data_gate": "CHART_CONTRACT_MISSING",
                    "chart_operable": None,
                },
            ]
        }
    )

    assert coverage["chart_contract_operable_count"] == 1
    assert coverage["chart_contract_blocked_count"] == 2
    assert coverage["chart_contract_blocked_markets"] == ["options", "stock"]
    assert coverage["chart_contract_market_counts"] == {"crypto": 2, "stock": 1}
    assert coverage["chart_contract_market_operable_counts"] == {"crypto": 1}
    assert coverage["chart_contract_market_blocked_counts"] == {"crypto": 1, "stock": 1}


def test_alert_quality_entry_promotes_chart_contract_coverage():
    entry = alert_quality_entry(
        {
            "alert_gate_summary": {
                "total_opportunities": 2,
                "notifications_ready": 0,
                "top_gate": "BLOCKED_REALTIME_DATA",
            },
            "opportunities": [
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "chart_data_gate": "LIVE_DATA_OK",
                    "chart_operable": True,
                },
                {
                    "symbol": "AMAT",
                    "market": "stock",
                    "chart_data_gate": "CHART_CONTRACT_MISSING",
                    "chart_operable": None,
                },
            ],
        },
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )

    assert entry["chart_contract_label"] == "Graficas parciales"
    assert entry["chart_contract_operable_count"] == 1
    assert entry["chart_contract_blocked_count"] == 1
    assert entry["chart_contract_missing_count"] == 1
    assert entry["chart_contract_blocked_markets"] == ["options", "stock"]
    assert entry["chart_contract_market_counts"] == {"crypto": 1, "stock": 1}
    assert entry["chart_contract_market_operable_counts"] == {"crypto": 1}
    assert entry["chart_contract_market_blocked_counts"] == {"stock": 1}
    assert entry["chart_contract_blocked_symbols"] == ["AMAT: CHART_CONTRACT_MISSING"]


def test_alert_quality_entry_blocks_market_when_chart_contract_is_missing():
    entry = alert_quality_entry(
        {
            "alert_gate_summary": {
                "total_opportunities": 2,
                "notifications_ready": 0,
                "blocked_realtime_count": 2,
                "top_gate": "BLOCKED_REALTIME_DATA",
                "top_blocker": "Grafica operable: CHART_CONTRACT_MISSING",
            },
            "opportunities": [
                {
                    "symbol": "ASML",
                    "market": "stock",
                    "alert_gate": "BLOCKED_REALTIME_DATA",
                    "chart_data_gate": "CHART_CONTRACT_MISSING",
                    "chart_operable": None,
                },
                {
                    "symbol": "BAC",
                    "market": "stock",
                    "alert_gate": "BLOCKED_REALTIME_DATA",
                    "chart_data_gate": "CHART_CONTRACT_MISSING",
                    "chart_operable": None,
                },
            ],
        },
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )

    assert entry["state"] == "BLOCKED_REALTIME"
    assert entry["realtime_blocked_markets"] == ["options", "stock"]
    assert entry["stock_alerts_allowed"] is False
    assert entry["options_alerts_allowed"] is False
    assert entry["crypto_alerts_allowed"] is True
    assert entry["market_coverage_label"] == "Cripto permitido sin candidatos"
    assert entry["chart_contract_label"] == "Graficas bloqueadas"


def test_summarize_quality_history_marks_stock_premium_block_as_partial_market_block():
    summary = summarize_quality_history(
        [
            {
                "state": "BLOCKED_REALTIME",
                "notifications_ready": 0,
                "total_opportunities": 3,
                "avg_readiness": 57.4,
                "realtime_alerts_allowed": True,
                "realtime_stock_alerts_allowed": False,
                "realtime_crypto_alerts_allowed": True,
                "realtime_blocked_markets": ["stock", "options"],
                "top_blocker": (
                    "Datos realtime: Premium bloqueado: chart_provider_effective: issue WMT 1h alpaca_auth, "
                    "alternate polygon_not_configured | accion Configurar POLYGON_API_KEY/POLYGON_API_TOKEN."
                ),
            }
        ]
    )

    assert summary["state"] == "BLOCKED_REALTIME"
    assert summary["diagnostic_label"] == "Bloqueo parcial"
    assert summary["diagnostic_detail"] == "stock, options bloqueado por proveedor premium; cripto sigue permitido"
    assert summary["blocker_category"] == "MARKET_PARTIAL_BLOCK"
    assert "POLYGON_API_KEY" in summary["recommended_action"]
    assert summary["silence_mode"] == "MARKET_PARTIAL_BLOCK"
    assert summary["blocked_markets"] == ["stock", "options"]
    assert "cripto sigue permitido" in summary["silence_reason"]
    assert summary["false_negative_risk"] == "MEDIUM"


def test_summarize_quality_history_marks_missing_chart_contract_as_market_block():
    summary = summarize_quality_history(
        [
            {
                "state": "BLOCKED_REALTIME",
                "notifications_ready": 0,
                "total_opportunities": 2,
                "realtime_alerts_allowed": True,
                "realtime_stock_alerts_allowed": True,
                "realtime_crypto_alerts_allowed": True,
                "realtime_blocked_markets": ["options", "stock"],
                "chart_contract_label": "Graficas bloqueadas",
                "chart_contract_action": "No emitir alertas hasta recuperar contrato realtime de grafica.",
                "chart_contract_blocked_count": 2,
                "chart_contract_missing_count": 2,
                "chart_contract_blocked_markets": ["options", "stock"],
                "top_blocker": "Grafica operable: CHART_CONTRACT_MISSING",
            }
        ]
    )

    assert summary["diagnostic_label"] == "Graficas bloquean"
    assert summary["diagnostic_detail"] == "Graficas sin contrato realtime: options, stock"
    assert summary["blocker_category"] == "CHART_CONTRACT_BLOCK"
    assert summary["silence_mode"] == "CHART_CONTRACT_BLOCK"
    assert summary["blocked_markets"] == ["options", "stock"]
    assert summary["false_negative_risk"] == "HIGH"


def test_summarize_quality_history_promotes_market_coverage_from_latest_entry():
    summary = summarize_quality_history(
        [
            {
                "state": "BLOCKED_REALTIME",
                "notifications_ready": 0,
                "total_opportunities": 1,
                "realtime_alerts_allowed": True,
                "realtime_stock_alerts_allowed": False,
                "realtime_crypto_alerts_allowed": True,
                "realtime_blocked_markets": ["stock", "options"],
                "market_counts": {"stock": 1},
                "allowed_markets": ["crypto"],
                "missing_allowed_markets": ["crypto"],
                "operable_market_count": 0,
                "blocked_market_count": 1,
                "market_coverage_label": "Cripto permitido sin candidatos",
                "market_coverage_action": "Mantener scan crypto activo; no forzar alertas si no hay setup cripto.",
            }
        ]
    )

    assert summary["market_counts"] == {"stock": 1}
    assert summary["allowed_markets"] == ["crypto"]
    assert summary["missing_allowed_markets"] == ["crypto"]
    assert summary["operable_market_count"] == 0
    assert summary["blocked_market_count"] == 1
    assert summary["market_coverage_label"] == "Cripto permitido sin candidatos"


def test_summarize_quality_history_promotes_chart_contract_from_latest_entry():
    summary = summarize_quality_history(
        [
            {
                "state": "WAITING",
                "notifications_ready": 0,
                "total_opportunities": 2,
                "chart_contract_total_count": 2,
                "chart_contract_checked_count": 2,
                "chart_contract_operable_count": 1,
                "chart_contract_blocked_count": 1,
                "chart_contract_missing_count": 1,
                "chart_contract_blocked_markets": ["options", "stock"],
                "chart_contract_gate_counts": {"CHART_CONTRACT_MISSING": 1, "LIVE_DATA_OK": 1},
                "chart_contract_operable_symbols": ["BTC/USD"],
                "chart_contract_blocked_symbols": ["AMAT: CHART_CONTRACT_MISSING"],
                "chart_contract_label": "Graficas parciales",
                "chart_contract_action": "Priorizar oportunidades con LIVE_DATA_OK.",
            }
        ]
    )

    assert summary["chart_contract_total_count"] == 2
    assert summary["chart_contract_checked_count"] == 2
    assert summary["chart_contract_operable_count"] == 1
    assert summary["chart_contract_blocked_count"] == 1
    assert summary["chart_contract_missing_count"] == 1
    assert summary["chart_contract_blocked_markets"] == ["options", "stock"]
    assert summary["chart_contract_gate_counts"] == {"CHART_CONTRACT_MISSING": 1, "LIVE_DATA_OK": 1}
    assert summary["chart_contract_operable_symbols"] == ["BTC/USD"]
    assert summary["chart_contract_blocked_symbols"] == ["AMAT: CHART_CONTRACT_MISSING"]
    assert summary["chart_contract_label"] == "Graficas parciales"


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


def test_summarize_quality_history_recommends_rotation_after_long_15m_wait():
    watchlist = [
        {"symbol": "WMT", "readiness": 61.5, "quality": "C", "blocker": "15m da entrada: WAIT"},
        {"symbol": "PEP", "readiness": 53.8, "quality": "C", "blocker": "15m da entrada: WAIT"},
        {"symbol": "COST", "readiness": 53.8, "quality": "C", "blocker": "15m da entrada: WAIT"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 3,
            "avg_readiness": 56.4,
            "top_blocker": "15m da entrada: WAIT",
            "top_gate_label": "Esperar entrada 15m",
            "setup_watchlist": watchlist,
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(24)
    ]

    summary = summarize_quality_history(rows)

    assert summary["blocker_category"] == "MARKET_TRIGGER_WAIT"
    assert summary["rotation_candidates"] == ["WMT 61.5% C", "PEP 53.8% C", "COST 53.8% C"]
    assert summary["recommended_action"].startswith("Rotar foco: WMT 61.5% C")
    assert "no alertar hasta que 15m confirme entrada" in summary["recommended_action"]


def test_summarize_quality_history_marks_high_readiness_trigger_wait_as_missed_watch():
    watchlist = [
        {"symbol": "BTC/USD", "readiness": 78.9, "quality": "B", "blocker": "15m da entrada: WAIT"},
        {"symbol": "ETH/USD", "readiness": 78.9, "quality": "B", "blocker": "15m da entrada: WAIT"},
        {"symbol": "SOL/USD", "readiness": 78.9, "quality": "B", "blocker": "15m da entrada: WAIT"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 3,
            "avg_readiness": 78.9,
            "top_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "setup_watchlist": watchlist,
            "chart_contract_total_count": 3,
            "chart_contract_operable_count": 3,
            "chart_contract_blocked_count": 0,
            "stock_alerts_allowed": False,
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(30)
    ]

    summary = summarize_quality_history(rows)

    assert summary["blocker_category"] == "MARKET_TRIGGER_WAIT"
    assert summary["silence_mode"] == "MISSED_TRIGGER_WATCH"
    assert summary["silence_severity"] == "WATCH"
    assert summary["false_positive_guard"] is True
    assert summary["false_negative_risk"] == "MEDIUM"
    assert summary["missed_opportunity_watch"] is True
    assert summary["missed_opportunity_risk"] == "MEDIUM"
    assert "gatillo 15m lleva 30 ciclos" in summary["missed_opportunity_reason"]
    assert "mantener alerta bloqueada" in summary["missed_opportunity_action"]
    assert summary["rotation_candidates"] == ["BTC/USD 78.9% B", "ETH/USD 78.9% B", "SOL/USD 78.9% B"]
    assert summary["missed_trigger_plan"]["active"] is True
    assert summary["missed_trigger_plan"]["mode"] == "MISSED_TRIGGER_WATCH"
    assert summary["missed_trigger_plan"]["primary_symbol"] == "BTC/USD"
    assert summary["missed_trigger_plan"]["primary_readiness"] == 78.9
    assert summary["missed_trigger_plan"]["primary_quality"] == "B"
    assert summary["missed_trigger_plan"]["waiting_streak"] == 30
    assert summary["missed_trigger_plan"]["blocker_streak"] == 30
    assert summary["missed_trigger_plan"]["review_cycle_minutes"] == 1.0
    assert summary["missed_trigger_plan"]["review_eta_minutes"] == 18.0
    assert summary["missed_trigger_plan"]["review_overdue_minutes"] == 0.0
    assert summary["missed_trigger_plan"]["rotation_candidates"] == [
        "BTC/USD 78.9% B",
        "ETH/USD 78.9% B",
        "SOL/USD 78.9% B",
    ]
    assert "15m confirme" in summary["missed_trigger_plan"]["exit_condition"]


def test_summarize_quality_history_escalates_long_missed_trigger_watch_for_manual_review():
    watchlist = [
        {"symbol": "ETH/USD", "readiness": 84.2, "quality": "B", "blocker": "15m da entrada: WAIT"},
        {"symbol": "BTC/USD", "readiness": 78.9, "quality": "B", "blocker": "15m da entrada: WAIT"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 81.5,
            "top_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "setup_watchlist": watchlist,
            "chart_contract_total_count": 2,
            "chart_contract_operable_count": 2,
            "chart_contract_blocked_count": 0,
            "stock_alerts_allowed": False,
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(50)
    ]

    summary = summarize_quality_history(rows)

    assert summary["silence_mode"] == "MISSED_TRIGGER_WATCH"
    assert summary["silence_severity"] == "ATTENTION"
    assert summary["false_negative_risk"] == "HIGH"
    assert summary["missed_opportunity_review_due"] is True
    assert summary["missed_opportunity_max_watch_cycles"] == 48
    assert summary["missed_trigger_plan"]["review_due"] is True
    assert summary["missed_trigger_plan"]["review_status"] == "OVERDUE"
    assert summary["missed_trigger_plan"]["review_overdue_cycles"] == 2
    assert summary["missed_trigger_plan"]["review_cycles_remaining"] == 0
    assert summary["missed_trigger_plan"]["review_progress"] == 1.042
    assert summary["missed_trigger_plan"]["review_cycle_minutes"] == 1.0
    assert summary["missed_trigger_plan"]["review_eta_minutes"] == 0.0
    assert summary["missed_trigger_plan"]["review_overdue_minutes"] == 2.0
    assert summary["missed_trigger_plan"]["review_pressure"] == "OVERDUE"
    assert summary["missed_trigger_plan"]["stale_candidate"] is False
    assert summary["missed_trigger_plan"]["auto_review_decision"] == "REVALIDATE_NOW"
    assert summary["missed_trigger_plan"]["readiness_delta"] == 0.0
    assert summary["missed_trigger_plan"]["severity"] == "ATTENTION"
    assert summary["missed_trigger_plan"]["max_watch_cycles"] == 48
    assert "Revalidar ahora" in summary["missed_trigger_plan"]["review_action"]
    assert "Revalidar ahora" in summary["recommended_action"]


def test_summarize_quality_history_escalates_repeated_overdue_trigger_watch_to_rotation():
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    watchlist = [
        {"symbol": "ETH/USD", "readiness": 84.2, "quality": "B", "blocker": "15m da entrada: WAIT"},
        {"symbol": "BTC/USD", "readiness": 78.9, "quality": "B", "blocker": "15m da entrada: WAIT"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 81.5,
            "top_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "setup_watchlist": watchlist,
            "chart_contract_total_count": 2,
            "chart_contract_operable_count": 2,
            "chart_contract_blocked_count": 0,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
            "recorded_at": (base_time + timedelta(minutes=idx)).isoformat(),
        }
        for idx in range(72)
    ]

    summary = summarize_quality_history(rows)
    plan = summary["missed_trigger_plan"]

    assert summary["waiting_streak"] == 72
    assert summary["current_streak_count"] == 72
    assert summary["latest_top_blocker_streak"] == 72
    assert plan["waiting_streak"] == 72
    assert plan["review_overdue_cycles"] == 24
    assert plan["review_pressure"] == "OVERDUE_ESCALATED"
    assert plan["auto_review_decision"] == "ESCALATE_ROTATION"
    assert plan["rotation_guard_active"] is True
    assert plan["rotation_blocked_symbol"] == "ETH/USD"
    assert plan["rotation_alternates"] == ["BTC/USD 78.9% B"]
    assert plan["rotation_next_symbol"] == "BTC/USD"
    assert plan["rotation_cooldown_cycles"] == 12
    assert "Escalar rotacion" in plan["decision_action"]
    assert "BTC/USD" in plan["decision_action"]
    assert "Escalar rotacion" in summary["recommended_action"]
    assert "BTC/USD" in summary["recommended_action"]


def test_summarize_quality_history_reviews_near_ready_trigger_wait_after_long_streak():
    watchlist = [
        {"symbol": "BTC/USD", "readiness": 73.7, "quality": "C", "blocker": "15m da entrada: WAIT"},
        {"symbol": "SHIB/USD", "readiness": 73.7, "quality": "C", "blocker": "15m da entrada: WAIT"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 68.4,
            "top_blocker": "15m da entrada: WAIT",
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "setup_watchlist": watchlist,
            "chart_contract_total_count": 2,
            "chart_contract_operable_count": 2,
            "chart_contract_blocked_count": 0,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(50)
    ]

    summary = summarize_quality_history(rows)

    assert summary["blocker_category"] == "MARKET_TRIGGER_WAIT"
    assert summary["silence_mode"] == "MISSED_TRIGGER_WATCH"
    assert summary["silence_severity"] == "ATTENTION"
    assert summary["false_negative_risk"] == "MEDIUM"
    assert summary["missed_opportunity_watch"] is True
    assert summary["missed_opportunity_review_due"] is True
    assert "Setup casi listo" in summary["missed_opportunity_reason"]
    assert summary["missed_trigger_plan"]["active"] is True
    assert summary["missed_trigger_plan"]["review_due"] is True
    assert summary["missed_trigger_plan"]["primary_symbol"] == "BTC/USD"
    assert summary["missed_trigger_plan"]["primary_readiness"] == 73.7
    assert summary["missed_trigger_plan"]["risk"] == "MEDIUM"
    assert summary["missed_trigger_plan"]["severity"] == "ATTENTION"
    assert summary["missed_trigger_plan"]["review_pressure"] == "STALE_OVERDUE"
    assert summary["missed_trigger_plan"]["stale_candidate"] is True
    assert summary["missed_trigger_plan"]["auto_review_decision"] == "ROTATE_OR_DISCARD"
    assert summary["missed_trigger_plan"]["readiness_delta"] == 0.0
    assert summary["missed_trigger_plan"]["rotation_guard_active"] is True
    assert summary["missed_trigger_plan"]["rotation_blocked_symbol"] == "BTC/USD"
    assert summary["missed_trigger_plan"]["rotation_alternates"] == [
        "SHIB/USD 73.7% C",
    ]
    assert summary["missed_trigger_plan"]["rotation_cooldown_cycles"] == 12
    assert summary["missed_trigger_plan"]["rotation_cooldown_eta_minutes"] == 12.0
    assert "15m confirma" in summary["missed_trigger_plan"]["rotation_resume_condition"]
    assert "Rotar o descartar" in summary["missed_trigger_plan"]["decision_action"]
    assert "Rotar o descartar" in summary["recommended_action"]
    assert "15m confirme" in summary["missed_trigger_plan"]["exit_condition"]


def test_summarize_quality_history_escalates_stale_trigger_after_rotation_cooldown():
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    watchlist = [
        {"symbol": "ETH/USD", "readiness": 73.7, "quality": "C", "blocker": "15m da entrada: WAIT"},
        {"symbol": "LINK/USD", "readiness": 73.7, "quality": "C", "blocker": "15m da entrada: WAIT"},
        {"symbol": "LTC/USD", "readiness": 73.7, "quality": "C", "blocker": "15m da entrada: WAIT"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 3,
            "avg_readiness": 70.4,
            "top_blocker": "15m da entrada: WAIT",
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "setup_watchlist": watchlist,
            "chart_contract_total_count": 3,
            "chart_contract_operable_count": 3,
            "chart_contract_blocked_count": 0,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
            "recorded_at": (base_time + timedelta(minutes=idx)).isoformat(),
        }
        for idx in range(72)
    ]

    summary = summarize_quality_history(rows)
    plan = summary["missed_trigger_plan"]

    assert plan["review_overdue_cycles"] == 24
    assert plan["review_pressure"] == "STALE_OVERDUE_ESCALATED"
    assert plan["stale_candidate"] is True
    assert plan["auto_review_decision"] == "ESCALATE_ROTATION"
    assert plan["rotation_guard_active"] is True
    assert plan["rotation_blocked_symbol"] == "ETH/USD"
    assert plan["rotation_next_symbol"] == "LINK/USD"
    assert plan["rotation_alternates"] == ["LINK/USD 73.7% C", "LTC/USD 73.7% C"]
    assert "Escalar rotacion" in plan["decision_action"]
    assert "LINK/USD" in plan["decision_action"]
    assert "Escalar rotacion" in summary["recommended_action"]


def test_summarize_quality_history_discards_stale_single_trigger_candidate():
    watchlist = [
        {"symbol": "PEPE/USD", "readiness": 73.7, "quality": "C", "blocker": "15m da entrada: WAIT"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 1,
            "avg_readiness": 68.4,
            "top_blocker": "15m da entrada: WAIT",
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "setup_watchlist": watchlist,
            "chart_contract_total_count": 1,
            "chart_contract_operable_count": 1,
            "chart_contract_blocked_count": 0,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(50)
    ]

    summary = summarize_quality_history(rows)
    plan = summary["missed_trigger_plan"]

    assert summary["recommended_action"] == (
        "Pausar o descartar el candidato unico; esperar nuevo candidato o confirmacion 15m antes de reactivarlo."
    )
    assert plan["active"] is True
    assert plan["review_due"] is True
    assert plan["review_pressure"] == "STALE_SINGLE"
    assert plan["stale_candidate"] is True
    assert plan["auto_review_decision"] == "DISCARD_STALE_SINGLE"
    assert plan["decision_reason"] == (
        "Review overdue on the only visible candidate; no alternate rotation candidate is available."
    )
    assert "Pausar o descartar" in plan["decision_action"]
    assert plan["rotation_guard_active"] is False
    assert plan["rotation_alternates"] == []
    assert plan["rotation_cooldown_eta_minutes"] is None
    assert plan["discard_guard_active"] is True
    assert plan["discard_symbol"] == "PEPE/USD"
    assert plan["discard_cooldown_cycles"] == 12
    assert plan["discard_cooldown_eta_minutes"] == 12.0
    assert "alterno operable" in plan["discard_resume_condition"]


def test_summarize_quality_history_keeps_missed_watch_when_trigger_wait_is_recurrent():
    rows = []
    for idx in range(30):
        rows.append(
            {
                "state": "WAITING",
                "notifications_ready": 0,
                "total_opportunities": 3,
                "avg_readiness": 78.9,
                "top_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
                "top_gate": "WAIT_15M_ENTRY",
                "top_gate_label": "Esperar entrada 15m",
                "chart_contract_total_count": 3,
                "chart_contract_operable_count": 3,
                "chart_contract_blocked_count": 0,
                "stock_alerts_allowed": False,
                "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
            }
        )
    rows.append(
        {
            "state": "NO_SETUPS",
            "notifications_ready": 0,
            "total_opportunities": 0,
            "avg_readiness": 0,
            "top_blocker": "-",
            "recorded_at": "2026-06-10T12:30:00+00:00",
        }
    )
    for idx in range(31, 33):
        rows.append(
            {
                "state": "WAITING",
                "notifications_ready": 0,
                "total_opportunities": 3,
                "avg_readiness": 78.9,
                "top_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
                "top_gate": "WAIT_15M_ENTRY",
                "top_gate_label": "Esperar entrada 15m",
                "chart_contract_total_count": 3,
                "chart_contract_operable_count": 3,
                "chart_contract_blocked_count": 0,
                "stock_alerts_allowed": False,
                "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
            }
        )

    summary = summarize_quality_history(rows)

    assert summary["waiting_streak"] == 2
    assert summary["latest_top_blocker_streak"] == 2
    assert summary["dominant_blocker"] == {"name": "15m da entrada: WAIT_FOR_TRIGGER", "count": 32}
    assert summary["silence_mode"] == "MISSED_TRIGGER_WATCH"
    assert summary["false_negative_risk"] == "MEDIUM"
    assert "32 ciclos" in summary["missed_opportunity_reason"]


def test_summarize_quality_history_treats_closed_market_wait_as_session_wait_not_rotation():
    watchlist = [
        {"symbol": "WMT", "readiness": 61.5, "quality": "C", "blocker": "15m da entrada: WAIT"},
        {"symbol": "PEP", "readiness": 53.8, "quality": "C", "blocker": "15m da entrada: WAIT"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 56.4,
            "top_blocker": "15m da entrada: WAIT",
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "stock_session": "Cerrado",
            "stock_alerts_allowed": False,
            "top_setup": {"symbol": "WMT", "market": "stock"},
            "setup_watchlist": watchlist,
            "recorded_at": f"2026-06-10T22:{idx:02d}:00+00:00",
        }
        for idx in range(30)
    ]

    summary = summarize_quality_history(rows)

    assert summary["blocker_category"] == "MARKET_CLOSED_WAIT"
    assert summary["diagnostic_label"] == "Mercado cerrado"
    assert summary["diagnostic_severity"] == "WATCH"
    assert summary["latest_top_blocker_streak"] == 0
    assert summary["persistent_blocker"] == ""
    assert summary["persistent_blocker_minutes"] is None
    assert summary["dominant_blocker"] == {}
    assert summary["rotation_candidates"] == []
    assert summary["recommended_action"] == "Mercado cerrado; mantener watchlist y revalidar entrada en la apertura"
    assert summary["silence_mode"] == "HEALTHY_WAIT"
    assert summary["silence_severity"] == "WATCH"
    assert summary["false_positive_guard"] is True
    assert summary["false_negative_risk"] == "LOW"


def test_summarize_quality_history_classifies_wait_volume_gate_as_confirmation_wait():
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 1,
            "avg_readiness": 68.4,
            "top_blocker": "1h confirma: Score tendencia 54",
            "top_gate": "WAIT_VOLUME",
            "top_gate_label": "Esperar volumen",
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(8)
    ]

    summary = summarize_quality_history(rows)

    assert summary["blocker_category"] == "MARKET_CONFIRMATION_WAIT"
    assert summary["diagnostic_label"] == "Esperando volumen x8"
    assert summary["diagnostic_detail"] == "1h confirma: Score tendencia 54"
    assert summary["recommended_action"] == "Esperar confirmacion de volumen/target antes de alertar"
    assert summary["silence_mode"] == "HEALTHY_WAIT"
    assert summary["false_positive_guard"] is True


def test_summarize_quality_history_reviews_long_confirmation_wait_without_alerting():
    watchlist = [
        {"symbol": "ETH/USD", "readiness": 83.0, "quality": "B", "blocker": "2h/4h validan: contradicen"},
        {"symbol": "BTC/USD", "readiness": 77.5, "quality": "B", "blocker": "2h/4h validan: contradicen"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 80.2,
            "top_blocker": "2h/4h validan: contradicen",
            "top_gate": "WAIT_HTF_CONFIRM",
            "top_gate_label": "Esperar confirmacion 2h/4h",
            "setup_watchlist": watchlist,
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(50)
    ]

    summary = summarize_quality_history(rows)

    assert summary["blocker_category"] == "MARKET_CONFIRMATION_WAIT"
    assert summary["silence_mode"] == "HEALTHY_WAIT"
    assert summary["false_positive_guard"] is True
    assert summary["false_negative_risk"] == "MEDIUM"
    assert summary["missed_trigger_plan"]["active"] is False
    assert summary["confirmation_wait_plan"]["active"] is True
    assert summary["confirmation_wait_plan"]["mode"] == "CONFIRMATION_WAIT_REVIEW"
    assert summary["confirmation_wait_plan"]["primary_symbol"] == "ETH/USD"
    assert summary["confirmation_wait_plan"]["primary_readiness"] == 83.0
    assert summary["confirmation_wait_plan"]["review_due"] is True
    assert summary["confirmation_wait_plan"]["review_status"] == "OVERDUE"
    assert summary["confirmation_wait_plan"]["review_pressure"] == "OVERDUE"
    assert summary["confirmation_wait_plan"]["review_overdue_cycles"] == 2
    assert summary["confirmation_wait_plan"]["review_cycles_remaining"] == 0
    assert summary["confirmation_wait_plan"]["review_progress"] == 1.042
    assert summary["confirmation_wait_plan"]["review_eta_minutes"] == 0.0
    assert summary["confirmation_wait_plan"]["review_overdue_minutes"] == 2.0
    assert summary["confirmation_wait_plan"]["severity"] == "WATCH"
    assert "2h/4h" in summary["confirmation_wait_plan"]["exit_condition"]
    assert "Revalidar manualmente 2h/4h" in summary["confirmation_wait_plan"]["review_action"]
    assert "Revalidar manualmente 2h/4h" in summary["recommended_action"]


def test_summarize_quality_history_escalates_confirmation_wait_to_rotation():
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    watchlist = [
        {"symbol": "ETH/USD", "readiness": 83.0, "quality": "B", "blocker": "2h/4h validan: contradicen"},
        {"symbol": "BTC/USD", "readiness": 77.5, "quality": "B", "blocker": "2h/4h validan: contradicen"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 80.2,
            "top_blocker": "2h/4h validan: contradicen",
            "top_gate": "WAIT_HTF_CONFIRM",
            "top_gate_label": "Esperar confirmacion 2h/4h",
            "setup_watchlist": watchlist,
            "recorded_at": (base_time + timedelta(minutes=idx)).isoformat(),
        }
        for idx in range(72)
    ]

    summary = summarize_quality_history(rows)
    plan = summary["confirmation_wait_plan"]

    assert plan["review_overdue_cycles"] == 24
    assert plan["review_pressure"] == "OVERDUE_ESCALATED"
    assert plan["severity"] == "ATTENTION"
    assert plan["rotation_guard_active"] is True
    assert plan["rotation_blocked_symbol"] == "ETH/USD"
    assert plan["rotation_candidates"] == ["ETH/USD 83.0% B", "BTC/USD 77.5% B"]
    assert plan["rotation_alternates"] == ["BTC/USD 77.5% B"]
    assert plan["rotation_next_symbol"] == "BTC/USD"
    assert plan["rotation_cooldown_cycles"] == 12
    assert "Escalar rotacion de confirmacion" in plan["decision_action"]
    assert "BTC/USD" in plan["review_action"]
    assert "BTC/USD" in summary["recommended_action"]


def test_summarize_quality_history_skips_daily_blocked_confirmation_rotation():
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    watchlist = [
        {"symbol": "ETH/USD", "readiness": 89.5, "quality": "B", "blocker": "2h/4h validan: contradicen"},
        {"symbol": "LINK/USD", "readiness": 78.5, "quality": "B", "blocker": "2h/4h validan: contradicen"},
        {"symbol": "SOL/USD", "readiness": 74.5, "quality": "C", "blocker": "2h/4h validan: contradicen"},
    ]
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 3,
            "avg_readiness": 80.8,
            "top_blocker": "2h/4h validan: contradicen",
            "top_gate": "WAIT_HTF_CONFIRM",
            "top_gate_label": "Esperar confirmacion 2h/4h",
            "setup_watchlist": watchlist,
            "daily_plan_rotation_blocked_symbols": ["LINK/USD"],
            "recorded_at": (base_time + timedelta(minutes=idx)).isoformat(),
        }
        for idx in range(72)
    ]

    plan = summarize_quality_history(rows)["confirmation_wait_plan"]

    assert plan["review_pressure"] == "OVERDUE_ESCALATED"
    assert plan["rotation_candidates"] == [
        "ETH/USD 89.5% B",
        "LINK/USD 78.5% B",
        "SOL/USD 74.5% C",
    ]
    assert plan["rotation_blocked_by_daily_plan"] == ["LINK/USD"]
    assert plan["rotation_alternates"] == ["SOL/USD 74.5% C"]
    assert plan["rotation_next_symbol"] == "SOL/USD"


def test_summarize_quality_history_classifies_risk_target_blocker_as_confirmation_wait():
    rows = [
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 71.0,
            "top_blocker": "Reward/Risk viable: falta riesgo/target",
            "top_gate": "WAIT_FULL_CHECKLIST",
            "top_gate_label": "Esperar checklist completo",
            "recorded_at": f"2026-06-10T12:{idx:02d}:00+00:00",
        }
        for idx in range(4)
    ]

    summary = summarize_quality_history(rows)

    assert summary["blocker_category"] == "MARKET_CONFIRMATION_WAIT"
    assert summary["diagnostic_label"] == "Esperando riesgo/target x4"
    assert summary["diagnostic_detail"] == "Reward/Risk viable: falta riesgo/target"
    assert summary["silence_mode"] == "HEALTHY_WAIT"


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
    assert summary["silence_mode"] == "SUSPICIOUS_SILENCE"
    assert summary["silence_severity"] == "ATTENTION"
    assert summary["false_positive_guard"] is False
    assert summary["false_negative_risk"] == "HIGH"


def test_alert_silence_diagnostic_marks_no_setup_silence_after_long_empty_scan():
    silence = alert_silence_diagnostic(
        {"data_alerts_allowed": True, "realtime_alerts_allowed": True},
        latest_state="NO_SETUPS",
        latest_ready=0,
        latest_total=0,
        waiting_streak=14,
        blocker_category="",
        diagnostic_severity="OK",
    )

    assert silence["silence_mode"] == "NO_SETUP_SILENCE"
    assert silence["silence_severity"] == "WATCH"
    assert silence["false_positive_guard"] is True
    assert silence["false_negative_risk"] == "MEDIUM"


def test_alert_quality_label_tone_keeps_waiting_state_as_watch_when_severity_is_ok():
    label_tone = alert_quality_label_tone(
        {"state": "WAITING", "diagnostic_label": "Esperando confirmacion", "diagnostic_severity": "OK"},
        {"state": "WAITING"},
    )

    assert label_tone == {"label": "Esperando confirmacion", "tone": "watch"}


def test_alert_quality_report_status_warns_on_manual_review_due():
    assert alert_quality_report_status(
        {
            "diagnostic_severity": "WATCH",
            "silence_severity": "ATTENTION",
            "missed_trigger_plan": {"review_due": True},
        }
    ) == {
        "status": "WARN",
        "status_reason": "Alert quality requires manual review or attention.",
    }
    assert alert_quality_report_status(
        {
            "diagnostic_severity": "WATCH",
            "silence_severity": "ATTENTION",
            "false_negative_risk": "HIGH",
            "missed_trigger_plan": {
                "review_due": True,
                "rotation_guard_active": True,
                "rotation_handoff_status": "CONFIRMED",
                "rotation_handoff_confirmed": True,
            },
        }
    ) == {
        "status": "OK",
        "status_reason": "Alert quality operating within current guardrails.",
    }
    assert alert_quality_report_status(
        {
            "diagnostic_severity": "WATCH",
            "silence_severity": "WATCH",
            "false_negative_risk": "LOW",
            "confirmation_wait_plan": {
                "review_due": True,
                "review_pressure": "OVERDUE",
                "risk": "LOW",
            },
        }
    ) == {
        "status": "OK",
        "status_reason": "Alert quality operating within current guardrails.",
    }
    assert alert_quality_report_status(
        {
            "diagnostic_severity": "WATCH",
            "silence_severity": "WATCH",
            "false_negative_risk": "LOW",
            "confirmation_wait_plan": {
                "review_due": True,
                "review_pressure": "OVERDUE_ESCALATED",
                "risk": "LOW",
                "rotation_guard_active": True,
            },
        }
    ) == {
        "status": "WARN",
        "status_reason": "Alert quality requires manual review or attention.",
    }
    assert alert_quality_report_status(
        {
            "diagnostic_severity": "OK",
            "silence_severity": "WATCH",
            "false_negative_risk": "LOW",
        }
    ) == {
        "status": "OK",
        "status_reason": "Alert quality operating within current guardrails.",
    }
    assert alert_quality_report_status(
        {
            "diagnostic_severity": "ATTENTION",
            "silence_severity": "ATTENTION",
            "blocker_category": "MARKET_PARTIAL_BLOCK",
            "silence_mode": "MARKET_PARTIAL_BLOCK",
            "operable_market_count": 3,
            "missing_allowed_markets": [],
            "market_coverage_label": "Cripto operable",
        }
    ) == {
        "status": "OK",
        "status_reason": "Alert quality operating within current guardrails.",
    }


def test_alert_silence_diagnostic_marks_persistent_high_readiness_trigger_wait():
    silence = alert_silence_diagnostic(
        {
            "data_alerts_allowed": True,
            "realtime_alerts_allowed": True,
            "stock_alerts_allowed": False,
            "avg_readiness": 78.9,
            "chart_contract_operable_count": 3,
            "chart_contract_blocked_count": 0,
        },
        latest_state="WAITING",
        latest_ready=0,
        latest_total=3,
        waiting_streak=41,
        blocker_category="MARKET_TRIGGER_WAIT",
        diagnostic_severity="WATCH",
    )

    assert silence["silence_mode"] == "MISSED_TRIGGER_WATCH"
    assert silence["silence_severity"] == "WATCH"
    assert silence["false_positive_guard"] is True
    assert silence["false_negative_risk"] == "MEDIUM"
    assert silence["missed_opportunity_watch"] is True
    assert "41 ciclos" in silence["missed_opportunity_reason"]


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


def test_opportunity_watchlist_snapshot_extracts_ranked_unique_symbols():
    watchlist = opportunity_watchlist_snapshot(
        {
            "top_opportunities": [
                {
                    "symbol": "WMT",
                    "ai_action": "WATCH",
                    "alert_gate": "WAIT_15M_ENTRY",
                    "alert_readiness_score": 61.5,
                    "alert_quality": "C",
                    "alert_primary_blocker": "15m da entrada: WAIT",
                },
                {
                    "symbol": "WMT",
                    "alert_readiness_score": 60.0,
                    "alert_quality": "C",
                },
                {
                    "symbol": "PEP",
                    "alert_readiness_score": 53.8,
                    "alert_quality": "C",
                    "alert_primary_blocker": "15m da entrada: WAIT",
                },
            ]
        }
    )

    assert [row["symbol"] for row in watchlist] == ["WMT", "PEP"]
    assert rotation_candidate_summary(watchlist) == ["WMT 61.5% C", "PEP 53.8% C"]


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
    assert report["contract_version"] == 3
    assert report["symbol"] == "AMAT"
    assert report["top_symbol"] == "AMAT"
    assert report["top_gate"] == "Esperar entrada 15m"
    assert report["top_blocker"] == "15m da entrada: WAIT"
    assert report["operational_focus_symbol"] == "AMAT"
    assert report["operational_focus_source"] == "TOP_SETUP"
    assert report["history_budget_status"] == "OK"
    assert report["history_budget_ratio"] is not None
    assert report["history_budget_margin_bytes"] is not None
    assert report["history_average_entry_bytes"] is not None
    assert report["history_budget_projected_next_ratio"] is not None
    assert report["history_budget_projected_pressure"] == "CLEAR"
    assert report["history_budget_min_appends_until_warn"] == DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN
    assert report["history_estimated_appends_until_warn"] is not None
    assert report["history_budget_watch"] is False
    assert report["history_budget_watch_margin_ratio"] == DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO
    history_summary_fields = [
        "history_count",
        "history_size_bytes",
        "history_max_bytes",
        "history_min_entries",
        "history_budget_status",
        "history_budget_pressure",
        "history_budget_warn_ratio",
        "history_budget_min_appends_until_warn",
        "history_budget_watch",
        "history_budget_watch_margin_ratio",
        "history_budget_ratio",
        "history_budget_margin_bytes",
        "history_average_entry_bytes",
        "history_estimated_appends_until_warn",
        "history_budget_projected_next_ratio",
        "history_budget_projected_pressure",
    ]
    assert report["summary"]["history_entries"] == report["history_count"]
    for field in history_summary_fields:
        assert report["summary"][field] == report[field]
    assert report["latest_entry"]["top_symbol"] == "AMAT"
    assert report["latest_entry"]["symbol"] == "AMAT"
    assert report["entry"]["top_setup"]["primary_blocker"] == "15m da entrada: WAIT"
    saved = json.loads(report_path.read_text())
    assert saved["history_count"] == 1
    assert saved["history_size_bytes"] == history_path.stat().st_size
    assert saved["history_max_bytes"] == 2000000
    assert saved["history_min_entries"] == 120
    assert saved["history_budget_status"] == "OK"
    assert saved["history_budget_ratio"] == report["history_budget_ratio"]
    assert saved["history_average_entry_bytes"] == report["history_average_entry_bytes"]
    assert saved["history_budget_min_appends_until_warn"] == DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN
    assert saved["history_estimated_appends_until_warn"] == report["history_estimated_appends_until_warn"]
    assert saved["history_budget_projected_next_ratio"] == report["history_budget_projected_next_ratio"]
    assert saved["history_budget_projected_pressure"] == "CLEAR"
    assert saved["history_budget_watch"] is False
    assert saved["summary"]["history_entries"] == saved["history_count"]
    for field in history_summary_fields:
        assert saved["summary"][field] == saved[field]
    assert saved["symbol"] == "AMAT"
    assert saved["top_symbol"] == "AMAT"
    assert saved["top_gate"] == "Esperar entrada 15m"
    assert saved["top_blocker"] == "15m da entrada: WAIT"
    assert saved["operational_focus_symbol"] == "AMAT"
    assert saved["operational_focus_source"] == "TOP_SETUP"
    assert saved["latest_entry"]["top_next_action"] == "Esperar gatillo BUY en 15m."
    history_lines = history_path.read_text().splitlines()
    assert len(history_lines) == 1
    history_entry = json.loads(history_lines[-1])
    assert history_entry["contract_version"] == 3
    assert history_entry["symbol"] == "AMAT"
    assert history_entry["top_symbol"] == "AMAT"
    assert history_entry["top_blocker"] == "15m da entrada: WAIT"
    assert history_entry["diagnostic_category"] == "MARKET_TRIGGER_WAIT"
    assert history_entry["action"] == saved["recommended_action"]
    assert history_entry["operational_focus_symbol"] == "AMAT"
    assert history_entry["operational_focus_source"] == "TOP_SETUP"


def test_write_alert_quality_report_compacts_redundant_history_plan_storage(tmp_path):
    history_path = tmp_path / "alert_quality_history.jsonl"
    report_path = tmp_path / "alert_quality.json"
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    brief = {
        "generated_at": now.isoformat(),
        "status": "OK",
        "alert_gate_summary": {
            "total_opportunities": 1,
            "notifications_ready": 0,
            "alert_count": 0,
            "watch_count": 1,
            "avg_readiness": 89.5,
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "top_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
            "top_quality": "B",
            "top_readiness": 89.5,
        },
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_readiness_score": 89.5,
                "alert_quality": "B",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_primary_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
                "alert_next_action": "Esperar gatillo BUY en 15m.",
                "chart_data_gate": "LIVE_DATA_OK",
                "chart_operable": True,
                "stock_session": "Abierto",
                "stock_alerts_allowed": True,
                "data_alerts_allowed": True,
                "realtime_alerts_allowed": True,
                "smart_alert": {
                    "gate": "WAIT_15M_ENTRY",
                    "readiness_score": 89.5,
                    "primary_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
                },
            }
        ],
    }
    for idx in range(49):
        entry = alert_quality_entry(
            brief,
            now=now - timedelta(minutes=49 - idx),
        )
        history_path.write_text(
            (history_path.read_text() if history_path.exists() else "")
            + json.dumps(entry, sort_keys=True)
            + "\n"
        )

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        now=now,
        history_min_entries=1,
    )
    stored = json.loads(history_path.read_text().splitlines()[-1])

    assert isinstance(report["missed_trigger_plan"], dict)
    assert report["missed_trigger_plan"]["active"] is True
    assert report["summary"]["missed_trigger_plan"]["active"] is True
    assert report["entry"]["confirmation_wait_plan_active"] is False
    assert report["entry"]["missed_trigger_plan_discard_guard_active"] is False
    assert isinstance(report["entry"]["top_setup"], dict)
    assert isinstance(report["entry"]["setup_watchlist"], list)
    assert stored["storage_compacted"] is True
    assert stored["storage_removed_key_count"] > len(stored["storage_removed_key_sample"])
    assert "storage_removed_keys" not in stored
    assert "missed_trigger_plan" in stored["storage_removed_key_sample"]
    assert "top_setup" in stored["storage_removed_key_sample"]
    assert "setup_watchlist" in stored["storage_removed_key_sample"]
    assert "recommended_action" in stored["storage_removed_key_sample"]
    assert "operational_focus_reason" in stored["storage_removed_key_sample"]
    assert "missed_trigger_plan_review_action" in stored["storage_removed_key_sample"]
    assert "missed_trigger_plan_decision_action" in stored["storage_removed_key_sample"]
    assert "confirmation_wait_plan_active" in stored["storage_removed_key_sample"]
    assert "missed_trigger_plan" not in stored
    assert "top_setup" not in stored
    assert "setup_watchlist" not in stored
    assert "recommended_action" not in stored
    assert "operational_focus_reason" not in stored
    assert "missed_trigger_plan_review_action" not in stored
    assert "missed_trigger_plan_decision_action" not in stored
    assert "confirmation_wait_plan_active" not in stored
    assert "confirmation_wait_plan_symbol" not in stored
    assert "missed_trigger_plan_discard_guard_active" not in stored
    assert "missed_trigger_plan_discard_symbol" not in stored
    assert stored["action"] == report["action"]
    assert "rotation_candidates" in stored
    assert stored["top_symbol"] == "ETH/USD"
    assert stored["top_readiness"] == 89.5
    assert stored["top_quality"] == "B"
    assert stored["top_blocker"] == "15m da entrada: WAIT_FOR_TRIGGER"
    assert stored["missed_trigger_plan_active"] is True
    assert stored["missed_trigger_plan_symbol"] == "ETH/USD"
    assert stored["missed_trigger_plan_readiness"] == 89.5
    assert stored["missed_trigger_plan_review_status"] == "OVERDUE"
    first_stored = json.loads(history_path.read_text().splitlines()[0])
    assert "top_setup" not in first_stored
    assert "setup_watchlist" not in first_stored


def test_compact_history_entry_for_storage_converts_legacy_removed_keys_metadata():
    legacy = {
        "status": "WARN",
        "storage_compacted": True,
        "storage_removed_keys": [f"legacy_key_{idx}" for idx in range(20)],
        "action": "wait",
        "recommended_action": "wait",
    }

    stored = compact_history_entry_for_storage(legacy)

    assert stored["storage_compacted"] is True
    assert "storage_removed_keys" not in stored
    assert stored["storage_removed_key_count"] == 21
    assert stored["storage_removed_key_sample"] == [f"legacy_key_{idx}" for idx in range(12)]
    assert "recommended_action" not in stored


def test_compact_history_entry_for_storage_removes_rotation_handoff_action_aliases():
    action = (
        "Rotacion confirmada: mantener foco operativo en BTC/USD; mantener ETH/USD bloqueado "
        "hasta que 15m confirme entrada o cambie la readiness."
    )
    decision_action = (
        "Escalar rotacion: revalidar 15m/1h ahora; si no confirma en la proxima revision, "
        "rotar foco a BTC/USD."
    )
    entry = {
        "status": "WARN",
        "action": action,
        "missed_trigger_plan_handoff_confirmed_action": action,
        "missed_trigger_plan_decision_action": decision_action,
        "missed_trigger_plan_review_action": decision_action,
    }

    stored = compact_history_entry_for_storage(entry)

    assert stored["storage_compacted"] is True
    assert stored["action"] == action
    assert stored["missed_trigger_plan_decision_action"] == decision_action
    assert "missed_trigger_plan_handoff_confirmed_action" not in stored
    assert "missed_trigger_plan_review_action" not in stored
    assert "missed_trigger_plan_handoff_confirmed_action" in stored["storage_removed_key_sample"]
    assert "missed_trigger_plan_review_action" in stored["storage_removed_key_sample"]


def test_compact_history_entry_for_storage_removes_duplicate_scalar_aliases():
    entry = {
        "state": "WAITING",
        "top_blocker": "15m da entrada: WAIT",
        "latest_top_blocker": "15m da entrada: WAIT",
        "recurrent_blocker": "15m da entrada: WAIT",
        "persistent_blocker": "15m da entrada: WAIT",
        "diagnostic_detail": "15m da entrada: WAIT",
        "top_gate": "Esperar entrada 15m",
        "latest_top_gate": "Esperar entrada 15m",
        "recurrent_gate": "Esperar entrada 15m",
        "silence_reason": "Setup listo, pero gatillo 15m lleva 40 ciclos pendiente",
        "missed_opportunity_reason": "Setup listo, pero gatillo 15m lleva 40 ciclos pendiente",
    }

    stored = compact_history_entry_for_storage(entry)

    assert stored["storage_compacted"] is True
    assert stored["top_blocker"] == "15m da entrada: WAIT"
    assert stored["top_gate"] == "Esperar entrada 15m"
    assert stored["silence_reason"] == "Setup listo, pero gatillo 15m lleva 40 ciclos pendiente"
    for key in (
        "latest_top_blocker",
        "recurrent_blocker",
        "persistent_blocker",
        "diagnostic_detail",
        "latest_top_gate",
        "recurrent_gate",
        "missed_opportunity_reason",
    ):
        assert key not in stored


def test_compact_history_entry_for_storage_keeps_distinct_scalar_aliases():
    entry = {
        "state": "WAITING",
        "top_blocker": "15m da entrada: WAIT",
        "diagnostic_detail": "Setup casi listo, falta volumen.",
        "silence_reason": "Setup listo, pero gatillo 15m lleva 40 ciclos pendiente",
        "missed_opportunity_reason": "Setup casi listo, falta volumen.",
    }

    stored = compact_history_entry_for_storage(entry)

    assert stored == entry
    assert stored["diagnostic_detail"] == "Setup casi listo, falta volumen."
    assert stored["missed_opportunity_reason"] == "Setup casi listo, falta volumen."


def test_append_history_trims_to_byte_budget_with_recent_minimum(tmp_path):
    history_path = tmp_path / "alert_quality_history.jsonl"

    for idx in range(6):
        count = append_history(
            history_path,
            {
                "recorded_at": f"2026-06-10T12:0{idx}:00+00:00",
                "state": "WAITING",
                "top_blocker": "15m da entrada: WAIT",
                "diagnostic": "x" * 180,
            },
            limit=6,
            max_bytes=520,
            min_entries=2,
        )

    lines = history_path.read_text().splitlines()
    payloads = [json.loads(line) for line in lines]
    assert count == 2
    assert len(lines) == 2
    assert payloads[0]["recorded_at"] == "2026-06-10T12:04:00+00:00"
    assert payloads[-1]["recorded_at"] == "2026-06-10T12:05:00+00:00"
    assert len(history_path.read_bytes()) > 520


def test_write_alert_quality_report_preemptively_trims_history_near_limit(tmp_path):
    report_path = tmp_path / "alert_quality.json"
    history_path = tmp_path / "alert_quality_history.jsonl"
    existing_rows = [
        {
            "recorded_at": f"2026-06-10T11:{idx:02d}:00+00:00",
            "state": "WAITING",
            "top_blocker": "15m da entrada: WAIT",
            "diagnostic": "x" * 700,
        }
        for idx in range(11)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")

    report = write_alert_quality_report(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "alert_gate_summary": {
                "total_opportunities": 1,
                "notifications_ready": 0,
                "top_gate": "WAIT_15M_ENTRY",
                "top_blocker": "15m da entrada: WAIT",
            },
        },
        report_path=report_path,
        history_path=history_path,
        history_limit=20,
        history_max_bytes=10_000,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    saved = json.loads(report_path.read_text())

    assert report["history_budget_status"] == "OK"
    assert report["history_budget_pressure"] == "NEAR_LIMIT"
    assert report["history_budget_warn_ratio"] == 0.85
    assert report["history_budget_ratio"] < 0.85
    assert report["history_budget_margin_bytes"] >= 0
    assert len(history_path.read_text().splitlines()) < len(existing_rows) + 1
    assert saved["history_budget_pressure"] == "NEAR_LIMIT"


def test_write_alert_quality_report_surfaces_history_budget_watch_before_warn(tmp_path):
    report_path = tmp_path / "alert_quality.json"
    history_path = tmp_path / "alert_quality_history.jsonl"
    existing_rows = [
        {
            "recorded_at": f"2026-06-10T11:{idx:02d}:00+00:00",
            "state": "WAITING",
            "top_blocker": "15m da entrada: WAIT",
            "diagnostic": "x" * 700,
        }
        for idx in range(400)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "alert_gate_summary": {
            "total_opportunities": 1,
            "notifications_ready": 0,
            "top_gate": "WAIT_15M_ENTRY",
            "top_blocker": "15m da entrada: WAIT",
        },
    }
    write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_limit=500,
        history_max_bytes=None,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    projected_size = history_path.stat().st_size
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")
    max_bytes = int(projected_size / (DEFAULT_HISTORY_BUDGET_WARN_RATIO - 0.019))

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_limit=500,
        history_max_bytes=max_bytes,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    saved = json.loads(report_path.read_text())

    assert report["history_budget_status"] == "OK"
    assert report["history_budget_pressure"] == "CLEAR"
    assert report["history_budget_ratio"] < DEFAULT_HISTORY_BUDGET_WARN_RATIO
    assert report["history_budget_ratio"] >= DEFAULT_HISTORY_BUDGET_WARN_RATIO - DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO
    assert report["history_budget_watch"] is True
    assert report["history_budget_watch_margin_ratio"] == DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO
    assert report["history_average_entry_bytes"] > 0
    assert report["history_budget_projected_next_ratio"] >= report["history_budget_ratio"]
    assert report["history_budget_projected_pressure"] in {"CLEAR", "NEAR_LIMIT"}
    assert saved["history_budget_watch"] is True
    assert saved["history_budget_projected_next_ratio"] == report["history_budget_projected_next_ratio"]


def test_write_alert_quality_report_trims_watch_history_before_next_append_pressure(tmp_path):
    report_path = tmp_path / "alert_quality.json"
    history_path = tmp_path / "alert_quality_history.jsonl"
    existing_rows = [
        {
            "recorded_at": f"2026-06-10T11:{idx:02d}:00+00:00",
            "state": "WAITING",
            "top_blocker": "15m da entrada: WAIT",
            "diagnostic": "x" * 700,
        }
        for idx in range(18)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "alert_gate_summary": {
            "total_opportunities": 1,
            "notifications_ready": 0,
            "top_gate": "WAIT_15M_ENTRY",
            "top_blocker": "15m da entrada: WAIT",
        },
    }
    write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_limit=50,
        history_max_bytes=None,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    projected_size = history_path.stat().st_size
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")
    max_bytes = int(projected_size / (DEFAULT_HISTORY_BUDGET_WARN_RATIO - 0.01))

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_limit=50,
        history_max_bytes=max_bytes,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )

    assert DEFAULT_HISTORY_BUDGET_NEXT_APPEND_GUARD_MULTIPLIER == 3.0
    assert report["history_budget_status"] == "OK"
    assert report["history_budget_pressure"] == "NEAR_LIMIT"
    assert report["history_budget_ratio"] < DEFAULT_HISTORY_BUDGET_WARN_RATIO - DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO
    assert report["history_budget_watch"] is False
    assert len(history_path.read_text().splitlines()) < len(existing_rows) + 1


def test_write_alert_quality_report_trims_history_with_low_append_margin_before_watch(tmp_path):
    report_path = tmp_path / "alert_quality.json"
    history_path = tmp_path / "alert_quality_history.jsonl"
    existing_rows = [
        {
            "recorded_at": f"2026-06-10T10:{idx % 60:02d}:00+00:00",
            "state": "WAITING",
            "top_blocker": "15m da entrada: WAIT",
            "diagnostic": "x" * 900,
        }
        for idx in range(100)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "alert_gate_summary": {
            "total_opportunities": 1,
            "notifications_ready": 0,
            "top_gate": "WAIT_15M_ENTRY",
            "top_blocker": "15m da entrada: WAIT",
        },
    }
    write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_limit=200,
        history_max_bytes=None,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    projected_size = history_path.stat().st_size
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")
    max_bytes = int(projected_size / 0.82)

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_limit=200,
        history_max_bytes=max_bytes,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )

    assert DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN == 8
    assert report["history_budget_status"] == "OK"
    assert report["history_budget_pressure"] == "NEAR_LIMIT"
    assert report["history_budget_ratio"] < DEFAULT_HISTORY_BUDGET_WARN_RATIO - DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO
    assert report["history_budget_watch"] is False
    assert len(history_path.read_text().splitlines()) < len(existing_rows) + 1


def test_write_alert_quality_report_marks_low_append_margin_as_near_limit(tmp_path):
    report_path = tmp_path / "alert_quality.json"
    history_path = tmp_path / "alert_quality_history.jsonl"
    existing_rows = [
        {
            "recorded_at": f"2026-06-10T10:{idx % 60:02d}:00+00:00",
            "state": "WAITING",
            "top_blocker": "15m da entrada: WAIT",
            "diagnostic": "x" * 1800,
        }
        for idx in range(30)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "alert_gate_summary": {
            "total_opportunities": 1,
            "notifications_ready": 0,
            "top_gate": "WAIT_15M_ENTRY",
            "top_blocker": "15m da entrada: WAIT",
        },
    }
    write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_limit=100,
        history_max_bytes=None,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    projected_size = history_path.stat().st_size
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in existing_rows) + "\n")
    max_bytes = int(projected_size / 0.79)

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_limit=100,
        history_max_bytes=max_bytes,
        history_min_entries=1,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    saved = json.loads(report_path.read_text())

    assert report["history_budget_status"] == "OK"
    assert report["history_budget_ratio"] < DEFAULT_HISTORY_BUDGET_WARN_RATIO - DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO
    assert report["history_estimated_appends_until_warn"] <= DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN
    assert report["history_budget_pressure"] == "NEAR_LIMIT"
    assert saved["history_budget_pressure"] == "NEAR_LIMIT"
    assert saved["summary"]["history_budget_pressure"] == "NEAR_LIMIT"


def test_write_alert_quality_report_promotes_diagnostic_contract_top_level(tmp_path):
    report_path = tmp_path / "alert_quality.json"
    history_path = tmp_path / "alert_quality_history.jsonl"

    report = write_alert_quality_report(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "alert_gate_summary": {
                "total_opportunities": 1,
                "notifications_ready": 0,
                "top_gate": "WAIT_15M_ENTRY",
                "top_blocker": "15m da entrada: WAIT",
            },
            "realtime_health": {
                "label": "Premium bloqueado",
                "alerts_allowed": True,
                "stock_alerts_allowed": False,
                "crypto_alerts_allowed": True,
                "market_realtime": {"blocked_markets": ["stock", "options"]},
            },
            "opportunities": [
                {
                    "symbol": "WMT",
                    "market": "stock",
                    "ai_action": "WATCH",
                    "alert_gate": "WAIT_15M_ENTRY",
                    "alert_readiness_score": 60,
                    "alert_quality": "C",
                    "alert_primary_blocker": (
                        "Datos realtime: Premium bloqueado: issue WMT 1h alpaca_auth "
                        "| accion Configurar POLYGON_API_KEY/POLYGON_API_TOKEN."
                    ),
                }
            ],
        },
        report_path=report_path,
        history_path=history_path,
        now=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
    )
    saved = json.loads(report_path.read_text())

    assert report["contract_version"] == 3
    assert report["label"] == "Bloqueo parcial"
    assert report["tone"] == "avoid"
    assert report["state"] == "BLOCKED_REALTIME"
    assert report["top_symbol"] == "WMT"
    assert report["top_gate"] == "WAIT_15M_ENTRY"
    assert report["top_blocker"] == "15m da entrada: WAIT"
    assert report["recurrent_blocker"] == report["summary"]["dominant_blocker"]["name"]
    assert report["recurrent_blocker_count"] == report["summary"]["dominant_blocker"]["count"]
    assert report["operational_focus_symbol"] == "WMT"
    assert report["operational_focus_source"] == "TOP_SETUP"
    assert report["history_budget_status"] == "OK"
    assert report["history_budget_ratio"] is not None
    assert report["diagnostic_label"] == "Bloqueo parcial"
    assert report["blocker_category"] == "MARKET_PARTIAL_BLOCK"
    assert report["diagnostic_category"] == "MARKET_PARTIAL_BLOCK"
    assert report["blocked_markets"] == ["stock", "options"]
    assert report["summary"]["blocked_route_markets"] == ["stock", "options"]
    assert report["summary"]["blocked_route_market_count"] == 2
    assert report["summary"]["blocked_opportunity_market_count"] == 1
    assert report["blocked_route_markets"] == ["stock", "options"]
    assert report["blocked_route_market_count"] == 2
    assert report["blocked_opportunity_market_count"] == 1
    assert report["stock_alerts_allowed"] is False
    assert report["crypto_alerts_allowed"] is True
    assert report["options_alerts_allowed"] is False
    assert report["session_stock_alerts_allowed"] is True
    assert report["notifications_ready"] == 0
    assert report["total_opportunities"] == 1
    assert report["alert_count"] == 0
    assert report["watch_count"] == 0
    assert report["market_counts"] == {"stock": 1}
    assert report["allowed_markets"] == ["crypto"]
    assert report["missing_allowed_markets"] == ["crypto"]
    assert report["market_coverage_label"] == "Cripto permitido sin candidatos"
    assert "scan crypto activo" in report["market_coverage_action"]
    assert report["chart_contract_label"] == "Graficas bloqueadas"
    assert report["chart_contract_total_count"] == 1
    assert report["chart_contract_blocked_count"] == 1
    assert report["chart_contract_missing_count"] == 1
    assert report["chart_contract_gate_counts"] == {"CHART_CONTRACT_MISSING": 1}
    assert report["latest_notifications_ready"] == 0
    assert report["latest_total_opportunities"] == 1
    assert report["ready_count"] == 0
    assert report["ready_rate"] == 0.0
    assert "POLYGON_API_KEY" in report["recommended_action"]
    assert "cripto sigue permitido" in report["silence_reason"]
    assert report["false_negative_risk"] == "MEDIUM"
    assert saved["state"] == report["summary"]["state"]
    assert saved["contract_version"] == 3
    assert saved["label"] == "Bloqueo parcial"
    assert saved["tone"] == "avoid"
    assert saved["diagnostic_label"] == report["summary"]["diagnostic_label"]
    assert saved["diagnostic_category"] == report["summary"]["blocker_category"]
    assert saved["recommended_action"] == report["summary"]["recommended_action"]
    assert saved["action"] == report["summary"]["recommended_action"]
    assert saved["top_symbol"] == "WMT"
    assert saved["top_gate"] == "WAIT_15M_ENTRY"
    assert saved["top_blocker"] == "15m da entrada: WAIT"
    assert saved["recurrent_blocker"] == report["summary"]["dominant_blocker"]["name"]
    assert saved["operational_focus_symbol"] == "WMT"
    assert saved["operational_focus_source"] == "TOP_SETUP"
    assert saved["history_budget_status"] == "OK"
    assert saved["notifications_ready"] == 0
    assert saved["total_opportunities"] == 1
    assert saved["alert_count"] == 0
    assert saved["watch_count"] == 0
    assert saved["market_counts"] == {"stock": 1}
    assert saved["missing_allowed_markets"] == ["crypto"]
    assert saved["blocked_route_markets"] == ["stock", "options"]
    assert saved["blocked_route_market_count"] == 2
    assert saved["blocked_opportunity_market_count"] == 1
    assert saved["chart_contract_label"] == "Graficas bloqueadas"
    assert saved["chart_contract_blocked_symbols"] == ["WMT: CHART_CONTRACT_MISSING"]
    assert saved["stock_alerts_allowed"] is False
    assert saved["crypto_alerts_allowed"] is True
    assert saved["options_alerts_allowed"] is False


def test_write_alert_quality_report_promotes_missed_trigger_aliases_top_level(tmp_path):
    report_path = tmp_path / "alert_quality.json"
    history_path = tmp_path / "alert_quality_history.jsonl"
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    brief = {
        "generated_at": base_time.isoformat(),
        "alert_gate_summary": {
            "total_opportunities": 2,
            "notifications_ready": 0,
            "watch_count": 2,
            "avg_readiness": 81.5,
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "top_blocker": "15m da entrada: WAIT_FOR_TRIGGER",
        },
        "realtime_health": {
            "alerts_allowed": True,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
            "market_realtime": {"blocked_markets": ["stock", "options"]},
        },
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_readiness_score": 84.2,
                "alert_quality": "B",
                "alert_primary_blocker": "15m da entrada: WAIT",
                "chart_data_gate": "LIVE_DATA_OK",
                "chart_operable": True,
            },
            {
                "symbol": "BTC/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_readiness_score": 78.9,
                "alert_quality": "B",
                "alert_primary_blocker": "15m da entrada: WAIT",
                "chart_data_gate": "LIVE_DATA_OK",
                "chart_operable": True,
            },
        ],
    }
    previous = [
        alert_quality_entry(brief, now=base_time + timedelta(minutes=idx))
        for idx in range(49)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in previous) + "\n")

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        now=base_time + timedelta(minutes=49),
    )
    saved = json.loads(report_path.read_text())

    assert report["status"] == "WARN"
    assert saved["status"] == "WARN"
    assert report["status_reason"] == "Alert quality requires manual review or attention."
    assert report["silence_mode"] == "MISSED_TRIGGER_WATCH"
    assert report["missed_trigger_plan"]["review_due"] is True
    assert report["missed_trigger_plan_active"] is True
    assert report["missed_trigger_plan_symbol"] == "ETH/USD"
    assert report["missed_trigger_plan_readiness"] == 84.2
    assert report["missed_trigger_plan_risk"] == "HIGH"
    assert report["missed_trigger_plan_review_due"] is True
    assert report["missed_trigger_plan_review_status"] == "OVERDUE"
    assert report["missed_trigger_plan_review_overdue_cycles"] == 2
    assert report["missed_trigger_plan_review_cycles_remaining"] == 0
    assert report["missed_trigger_plan_review_progress"] == 1.042
    assert report["missed_trigger_plan_review_cycle_minutes"] == 1.0
    assert report["missed_trigger_plan_review_eta_minutes"] == 0.0
    assert report["missed_trigger_plan_review_overdue_minutes"] == 2.0
    assert report["missed_trigger_plan_review_pressure"] == "OVERDUE"
    assert report["missed_trigger_plan_stale_candidate"] is False
    assert report["missed_trigger_plan_auto_review_decision"] == "REVALIDATE_NOW"
    assert report["readiness_delta"] == 0.0
    assert report["readiness_trend"] == 0.0
    assert report["missed_trigger_plan_readiness_delta"] == 0.0
    assert report["missed_trigger_plan_severity"] == "ATTENTION"
    assert report["missed_trigger_plan_max_watch_cycles"] == 48
    assert "Revalidar ahora" in report["missed_trigger_plan_review_action"]
    assert "Revalidar ahora" in report["recommended_action"]
    assert "15m confirme" in report["missed_trigger_plan_exit"]
    assert saved["missed_trigger_plan_active"] is True
    assert saved["missed_trigger_plan_symbol"] == "ETH/USD"
    assert saved["missed_trigger_plan_review_due"] is True
    assert saved["missed_trigger_plan_review_status"] == "OVERDUE"
    assert saved["missed_trigger_plan_review_overdue_cycles"] == 2
    assert saved["readiness_trend"] == 0.0
    assert saved["missed_trigger_plan_review_cycles_remaining"] == 0
    assert saved["missed_trigger_plan_review_cycle_minutes"] == 1.0
    assert saved["missed_trigger_plan_review_eta_minutes"] == 0.0
    assert saved["missed_trigger_plan_review_overdue_minutes"] == 2.0
    assert saved["missed_trigger_plan_auto_review_decision"] == "REVALIDATE_NOW"
    assert report["summary"]["missed_trigger_plan_active"] is True
    assert report["summary"]["missed_trigger_plan_symbol"] == "ETH/USD"
    assert report["summary"]["missed_trigger_plan_readiness"] == 84.2
    assert report["summary"]["missed_trigger_plan_risk"] == "HIGH"
    assert report["summary"]["missed_trigger_plan_review_due"] is True
    assert report["summary"]["missed_trigger_plan_review_status"] == "OVERDUE"
    assert report["summary"]["missed_trigger_plan_review_pressure"] == "OVERDUE"
    assert report["summary"]["missed_trigger_plan_auto_review_decision"] == "REVALIDATE_NOW"
    assert saved["summary"]["missed_trigger_plan_symbol"] == "ETH/USD"
    assert saved["summary"]["missed_trigger_plan_review_status"] == "OVERDUE"


def test_write_alert_quality_report_promotes_rotation_guard_top_level(tmp_path):
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    history_path = tmp_path / "alert_quality_history.jsonl"
    report_path = tmp_path / "alert_quality.json"
    brief = {
        "generated_at": base_time.isoformat(),
        "alert_gate_summary": {
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 68.4,
            "top_gate_label": "Esperar entrada 15m",
            "top_blocker": "15m da entrada: WAIT",
            "watch_count": 2,
        },
        "source_freshness": {"alerts_allowed": True},
        "realtime_health": {"alerts_allowed": True, "stock_alerts_allowed": False, "crypto_alerts_allowed": True},
        "opportunities": [
            {
                "symbol": "BTC/USD",
                "readiness": 73.7,
                "alert_quality": "C",
                "blocker": "15m da entrada: WAIT",
                "market": "crypto",
                "chart_data_gate": "LIVE_DATA_OK",
                "chart_operable": True,
            },
            {
                "symbol": "DOGE/USD",
                "readiness": 68.4,
                "alert_quality": "C",
                "blocker": "15m da entrada: WAIT",
                "market": "crypto",
                "chart_data_gate": "LIVE_DATA_OK",
                "chart_operable": True,
            },
        ],
    }
    previous = [
        alert_quality_entry(brief, now=base_time + timedelta(minutes=idx))
        for idx in range(49)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in previous) + "\n")

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        now=base_time + timedelta(minutes=49),
    )
    saved = json.loads(report_path.read_text())

    assert report["status"] == "OK"
    assert report["status_reason"] == "Alert quality operating within current guardrails."
    assert saved["status"] == "OK"
    assert report["missed_trigger_plan_auto_review_decision"] == "ROTATE_OR_DISCARD"
    assert report["missed_trigger_plan_rotation_guard_active"] is True
    assert report["missed_trigger_plan_rotation_blocked_symbol"] == "BTC/USD"
    assert report["missed_trigger_plan_rotation_alternates"] == ["DOGE/USD 68.4% C"]
    assert report["missed_trigger_plan_rotation_next_symbol"] == "DOGE/USD"
    assert report["missed_trigger_plan_rotation_cooldown_cycles"] == 12
    assert report["missed_trigger_plan_rotation_cooldown_eta_minutes"] == 12.0
    assert report["missed_trigger_plan"]["rotation_handoff_status"] == "CONFIRMED"
    assert report["missed_trigger_plan"]["rotation_handoff_expected_symbol"] == "DOGE/USD"
    assert report["missed_trigger_plan"]["rotation_handoff_focus_symbol"] == "DOGE/USD"
    assert report["missed_trigger_plan"]["rotation_handoff_source"] == "ALERT_QUALITY_ROTATION"
    assert report["missed_trigger_plan"]["rotation_handoff_confirmed"] is True
    assert report["missed_trigger_plan_rotation_handoff_status"] == "CONFIRMED"
    assert report["missed_trigger_plan_rotation_handoff_symbol"] == "DOGE/USD"
    assert report["missed_trigger_plan_rotation_handoff_source"] == "ALERT_QUALITY_ROTATION"
    assert report["summary"]["top_symbol"] == "BTC/USD"
    assert report["summary"]["operational_focus_symbol"] == "DOGE/USD"
    assert report["summary"]["operational_focus_source"] == "ALERT_QUALITY_ROTATION"
    assert report["summary"]["missed_trigger_plan_symbol"] == "BTC/USD"
    assert report["summary"]["missed_trigger_plan_auto_review_decision"] == "ROTATE_OR_DISCARD"
    assert report["summary"]["missed_trigger_plan"]["rotation_handoff_status"] == "CONFIRMED"
    assert report["summary"]["missed_trigger_plan"]["rotation_handoff_focus_symbol"] == "DOGE/USD"
    assert report["summary"]["missed_trigger_plan_rotation_handoff_status"] == "CONFIRMED"
    assert report["summary"]["missed_trigger_plan_rotation_handoff_symbol"] == "DOGE/USD"
    assert report["recommended_action"].startswith("Rotacion confirmada")
    assert "DOGE/USD" in report["recommended_action"]
    assert "BTC/USD" in report["recommended_action"]
    assert report["action"] == report["recommended_action"]
    assert report["summary"]["recommended_action"] == report["recommended_action"]
    assert report["operational_focus_reason"] == report["recommended_action"]
    assert report["summary"]["operational_focus_reason"] == report["recommended_action"]
    assert report["missed_trigger_plan_handoff_confirmed_action"] == report["recommended_action"]
    assert report["summary"]["missed_trigger_plan_handoff_confirmed_action"] == report["recommended_action"]
    assert "15m confirma" in report["missed_trigger_plan_rotation_resume_condition"]
    assert saved["missed_trigger_plan_rotation_guard_active"] is True
    assert saved["missed_trigger_plan_rotation_blocked_symbol"] == "BTC/USD"
    assert saved["missed_trigger_plan_rotation_alternates"] == ["DOGE/USD 68.4% C"]
    assert saved["missed_trigger_plan_rotation_handoff_status"] == "CONFIRMED"
    assert saved["missed_trigger_plan_rotation_handoff_symbol"] == "DOGE/USD"
    assert saved["missed_trigger_plan_handoff_confirmed_action"] == report["recommended_action"]
    assert saved["summary"]["operational_focus_symbol"] == "DOGE/USD"
    assert saved["summary"]["operational_focus_source"] == "ALERT_QUALITY_ROTATION"
    assert saved["summary"]["missed_trigger_plan_symbol"] == "BTC/USD"
    assert saved["summary"]["missed_trigger_plan_auto_review_decision"] == "ROTATE_OR_DISCARD"
    assert saved["summary"]["missed_trigger_plan_rotation_handoff_status"] == "CONFIRMED"
    assert saved["summary"]["recommended_action"] == report["recommended_action"]


def test_write_alert_quality_report_promotes_stale_single_discard_guard_top_level(tmp_path):
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    history_path = tmp_path / "alert_quality_history.jsonl"
    report_path = tmp_path / "alert_quality.json"
    brief = {
        "generated_at": base_time.isoformat(),
        "alert_gate_summary": {
            "notifications_ready": 0,
            "total_opportunities": 1,
            "avg_readiness": 68.4,
            "top_gate": "WAIT_15M_ENTRY",
            "top_gate_label": "Esperar entrada 15m",
            "top_blocker": "15m da entrada: WAIT",
            "watch_count": 1,
        },
        "source_freshness": {"alerts_allowed": True},
        "realtime_health": {"alerts_allowed": True, "stock_alerts_allowed": False, "crypto_alerts_allowed": True},
        "opportunities": [
            {
                "symbol": "PEPE/USD",
                "readiness": 73.7,
                "alert_quality": "C",
                "blocker": "15m da entrada: WAIT",
                "market": "crypto",
                "chart_data_gate": "LIVE_DATA_OK",
                "chart_operable": True,
            },
        ],
    }
    previous = [
        alert_quality_entry(brief, now=base_time + timedelta(minutes=idx))
        for idx in range(49)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in previous) + "\n")

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        now=base_time + timedelta(minutes=49),
    )
    saved = json.loads(report_path.read_text())

    assert report["status"] == "WARN"
    assert report["missed_trigger_plan_review_pressure"] == "STALE_SINGLE"
    assert report["missed_trigger_plan_auto_review_decision"] == "DISCARD_STALE_SINGLE"
    assert report["missed_trigger_plan_rotation_guard_active"] is False
    assert report["missed_trigger_plan_rotation_alternates"] == []
    assert report["missed_trigger_plan_rotation_cooldown_eta_minutes"] is None
    assert report["missed_trigger_plan_discard_guard_active"] is True
    assert report["missed_trigger_plan_discard_symbol"] == "PEPE/USD"
    assert report["missed_trigger_plan_discard_cooldown_cycles"] == 12
    assert report["missed_trigger_plan_discard_cooldown_eta_minutes"] == 12.0
    assert report["operational_focus_symbol"] == "PEPE/USD"
    assert report["operational_focus_source"] == "ALERT_QUALITY_DISCARD"
    assert report["operational_focus_reason"].startswith("Pausar o descartar")
    assert "Pausar o descartar" in report["recommended_action"]
    assert "alterno operable" in report["missed_trigger_plan_discard_resume_condition"]
    assert saved["missed_trigger_plan_discard_guard_active"] is True
    assert saved["missed_trigger_plan_discard_symbol"] == "PEPE/USD"
    assert saved["missed_trigger_plan_auto_review_decision"] == "DISCARD_STALE_SINGLE"
    assert saved["operational_focus_source"] == "ALERT_QUALITY_DISCARD"


def test_write_alert_quality_report_promotes_confirmation_wait_plan_top_level(tmp_path):
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    history_path = tmp_path / "alert_quality_history.jsonl"
    report_path = tmp_path / "alert_quality.json"
    brief = {
        "generated_at": base_time.isoformat(),
        "alert_gate_summary": {
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 80.2,
            "top_gate_label": "Esperar confirmacion 2h/4h",
            "top_blocker": "2h/4h validan: contradicen",
            "watch_count": 2,
        },
        "source_freshness": {"alerts_allowed": True},
        "realtime_health": {"alerts_allowed": True, "stock_alerts_allowed": False, "crypto_alerts_allowed": True},
        "opportunities": [
            {"symbol": "ETH/USD", "readiness": 83.0, "alert_quality": "B", "blocker": "2h/4h validan: contradicen"},
            {"symbol": "BTC/USD", "readiness": 77.5, "alert_quality": "B", "blocker": "2h/4h validan: contradicen"},
        ],
    }
    previous = [
        alert_quality_entry(brief, now=base_time + timedelta(minutes=idx))
        for idx in range(49)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in previous) + "\n")

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        now=base_time + timedelta(minutes=49),
    )
    saved = json.loads(report_path.read_text())

    assert report["status"] == "OK"
    assert saved["status"] == "OK"
    assert report["status_reason"] == "Alert quality operating within current guardrails."
    assert report["silence_mode"] == "HEALTHY_WAIT"
    assert report["diagnostic_category"] == "MARKET_CONFIRMATION_WAIT"
    assert report["action"] == report["recommended_action"]
    assert report["alert_count"] == 0
    assert report["watch_count"] == 2
    assert report["waiting_streak"] == 50
    assert report["blocker_streak"] == 50
    assert report["missed_trigger_plan_active"] is False
    assert report["confirmation_wait_plan"]["review_due"] is True
    assert report["confirmation_wait_plan_active"] is True
    assert report["confirmation_wait_plan_symbol"] == "ETH/USD"
    assert report["symbol"] == "ETH/USD"
    assert report["confirmation_wait_plan_readiness"] == 83.0
    assert report["confirmation_wait_plan_risk"] == "LOW"
    assert report["confirmation_wait_plan_review_due"] is True
    assert report["confirmation_wait_plan_review_status"] == "OVERDUE"
    assert report["confirmation_wait_plan_review_pressure"] == "OVERDUE"
    assert report["confirmation_wait_plan_review_overdue_cycles"] == 2
    assert report["confirmation_wait_plan_review_cycles_remaining"] == 0
    assert report["confirmation_wait_plan_review_progress"] == 1.042
    assert report["confirmation_wait_plan_review_cycle_minutes"] == 1.0
    assert report["confirmation_wait_plan_review_eta_minutes"] == 0.0
    assert report["confirmation_wait_plan_review_overdue_minutes"] == 2.0
    assert report["confirmation_wait_plan_severity"] == "WATCH"
    assert report["confirmation_wait_plan_max_watch_cycles"] == 48
    assert report["confirmation_wait_plan_rotation_candidates"] == ["ETH/USD 83.0% B", "BTC/USD 77.5% B"]
    assert report["confirmation_wait_plan_rotation_candidate_count"] == 2
    assert report["confirmation_wait_plan_rotation_next_symbol"] == ""
    assert report["confirmation_wait_plan_next_symbol"] == ""
    assert "Revalidar manualmente 2h/4h" in report["confirmation_wait_plan_review_action"]
    assert "2h/4h" in report["confirmation_wait_plan_exit"]
    assert saved["confirmation_wait_plan_active"] is True
    assert saved["confirmation_wait_plan_symbol"] == "ETH/USD"
    assert saved["symbol"] == "ETH/USD"
    assert saved["confirmation_wait_plan_review_due"] is True
    assert saved["confirmation_wait_plan_review_status"] == "OVERDUE"
    assert saved["confirmation_wait_plan_review_pressure"] == "OVERDUE"
    assert saved["confirmation_wait_plan_rotation_candidates"] == ["ETH/USD 83.0% B", "BTC/USD 77.5% B"]
    assert saved["confirmation_wait_plan_rotation_candidate_count"] == 2
    assert saved["confirmation_wait_plan_rotation_next_symbol"] == ""
    assert saved["confirmation_wait_plan_next_symbol"] == ""
    assert saved["diagnostic_category"] == "MARKET_CONFIRMATION_WAIT"
    assert saved["action"] == saved["recommended_action"]
    assert saved["alert_count"] == 0
    assert saved["watch_count"] == 2
    assert saved["waiting_streak"] == 50
    assert saved["blocker_streak"] == 50
    history_entry = json.loads(history_path.read_text().splitlines()[-1])
    assert history_entry["contract_version"] == 3
    assert history_entry["status"] == "OK"
    assert history_entry["status_reason"] == "Alert quality operating within current guardrails."
    assert history_entry["diagnostic_category"] == "MARKET_CONFIRMATION_WAIT"
    assert history_entry["action"] == saved["recommended_action"]
    assert history_entry["waiting_streak"] == 50
    assert history_entry["blocker_streak"] == 50
    assert history_entry["confirmation_wait_plan_active"] is True
    assert history_entry["confirmation_wait_plan_symbol"] == "ETH/USD"
    assert history_entry["symbol"] == "ETH/USD"
    assert history_entry["confirmation_wait_plan_review_pressure"] == "OVERDUE"
    assert "confirmation_wait_plan" not in history_entry
    assert history_entry["storage_compacted"] is True
    assert "storage_removed_keys" not in history_entry
    assert history_entry["storage_removed_key_count"] >= 1
    assert "confirmation_wait_plan" in history_entry["storage_removed_key_sample"]
    assert history_entry["confirmation_wait_plan_rotation_candidates"] == [
        "ETH/USD 83.0% B",
        "BTC/USD 77.5% B",
    ]
    assert history_entry["confirmation_wait_plan_rotation_candidate_count"] == 2
    assert history_entry["confirmation_wait_plan_rotation_next_symbol"] == ""
    assert history_entry["confirmation_wait_plan_next_symbol"] == ""


def test_write_alert_quality_report_promotes_confirmation_rotation_next_symbol_top_level(tmp_path):
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    history_path = tmp_path / "alert_quality_history.jsonl"
    report_path = tmp_path / "alert_quality.json"
    brief = {
        "generated_at": base_time.isoformat(),
        "alert_gate_summary": {
            "notifications_ready": 0,
            "total_opportunities": 2,
            "avg_readiness": 80.2,
            "top_gate_label": "Esperar confirmacion 2h/4h",
            "top_blocker": "2h/4h validan: contradicen",
            "watch_count": 2,
        },
        "source_freshness": {"alerts_allowed": True},
        "realtime_health": {"alerts_allowed": True, "stock_alerts_allowed": False, "crypto_alerts_allowed": True},
        "opportunities": [
            {"symbol": "ETH/USD", "readiness": 83.0, "alert_quality": "B", "blocker": "2h/4h validan: contradicen"},
            {"symbol": "BTC/USD", "readiness": 77.5, "alert_quality": "B", "blocker": "2h/4h validan: contradicen"},
        ],
    }
    previous = [
        alert_quality_entry(brief, now=base_time + timedelta(minutes=idx))
        for idx in range(71)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in previous) + "\n")

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        now=base_time + timedelta(minutes=71),
    )
    saved = json.loads(report_path.read_text())
    history_entry = json.loads(history_path.read_text().splitlines()[-1])

    assert report["confirmation_wait_plan_review_pressure"] == "OVERDUE_ESCALATED"
    assert report["confirmation_wait_plan_rotation_guard_active"] is True
    assert report["confirmation_wait_plan_rotation_next_symbol"] == "BTC/USD"
    assert report["confirmation_wait_plan_next_symbol"] == "BTC/USD"
    assert saved["confirmation_wait_plan_next_symbol"] == "BTC/USD"
    assert history_entry["confirmation_wait_plan_next_symbol"] == "BTC/USD"


def test_write_alert_quality_report_skips_daily_blocked_confirmation_rotation(tmp_path):
    base_time = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    history_path = tmp_path / "alert_quality_history.jsonl"
    report_path = tmp_path / "alert_quality.json"
    brief = {
        "generated_at": base_time.isoformat(),
        "alert_gate_summary": {
            "notifications_ready": 0,
            "total_opportunities": 3,
            "avg_readiness": 81.0,
            "top_gate_label": "Esperar confirmacion 2h/4h",
            "top_blocker": "2h/4h validan: contradicen",
            "watch_count": 3,
        },
        "source_freshness": {"alerts_allowed": True},
        "realtime_health": {"alerts_allowed": True, "stock_alerts_allowed": False, "crypto_alerts_allowed": True},
        "daily_opportunity_plan": {
            "rows": [
                {"symbol": "ETH/USD", "stage": "PROXIMA_ENTRADA"},
                {"symbol": "LINK/USD", "stage": "NO_OPERAR"},
                {"symbol": "SOL/USD", "stage": "PROXIMA_ENTRADA"},
            ]
        },
        "opportunities": [
            {"symbol": "ETH/USD", "readiness": 89.5, "alert_quality": "B", "blocker": "2h/4h validan: contradicen"},
            {"symbol": "LINK/USD", "readiness": 78.5, "alert_quality": "B", "blocker": "2h/4h validan: contradicen"},
            {"symbol": "SOL/USD", "readiness": 74.5, "alert_quality": "C", "blocker": "2h/4h validan: contradicen"},
        ],
    }
    previous = [
        alert_quality_entry(brief, now=base_time + timedelta(minutes=idx))
        for idx in range(71)
    ]
    history_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in previous) + "\n")

    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        now=base_time + timedelta(minutes=71),
    )
    saved = json.loads(report_path.read_text())
    history_entry = json.loads(history_path.read_text().splitlines()[-1])

    assert report["confirmation_wait_plan_rotation_candidates"] == [
        "ETH/USD 89.5% B",
        "LINK/USD 78.5% B",
        "SOL/USD 74.5% C",
    ]
    assert report["confirmation_wait_plan_rotation_blocked_by_daily_plan"] == ["LINK/USD"]
    assert report["confirmation_wait_plan_rotation_daily_blocked_count"] == 1
    assert report["confirmation_wait_plan_rotation_alternates"] == ["SOL/USD 74.5% C"]
    assert report["confirmation_wait_plan_rotation_next_symbol"] == "SOL/USD"
    assert saved["confirmation_wait_plan_next_symbol"] == "SOL/USD"
    assert saved["confirmation_wait_plan_rotation_blocked_by_daily_plan"] == ["LINK/USD"]
    assert history_entry["daily_plan_rotation_blocked_symbols"] == ["LINK/USD"]
    assert history_entry["confirmation_wait_plan_next_symbol"] == "SOL/USD"
    assert history_entry["confirmation_wait_plan_rotation_blocked_by_daily_plan"] == ["LINK/USD"]
