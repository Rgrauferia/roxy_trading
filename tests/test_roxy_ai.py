import pandas as pd
from datetime import datetime, timedelta, timezone

from roxy_ai import (
    append_learning_journal,
    alert_gate_label,
    autonomous_learning_plan,
    alert_confidence_text,
    alert_targets_text,
    apply_global_alert_context,
    apply_memory_lessons,
    build_brief,
    build_learning_journal_row,
    build_notification_lines,
    build_status_snapshot,
    build_strategy_lab,
    current_prices_by_symbol,
    explain_opportunity,
    experiment_status_label,
    experiment_key,
    experiment_outcome_stats,
    extract_opportunities,
    gate_research_queue,
    learning_research_queue,
    learning_action_label,
    market_session_status,
    human_alert_reason,
    human_trade_action,
    realtime_health_status,
    refresh_strategy_shadow_stats,
    risk_size_text,
    safety_mode_label,
    source_freshness_status,
    summarize_alert_gates,
    strategy_learning_profile,
    summarize_strategy_learning,
    update_alert_outcomes,
    update_experiment_registry,
    update_memory_from_opportunities,
    update_trade_progress,
    write_brief,
    write_status_snapshot,
)


def test_extract_opportunities_alerts_only_confirmed_low_risk_buy():
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "AAPL",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "confluence_score": 82,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "entry": 100,
                "stop": 98,
                "backtest_eligible": True,
                "relative_volume_15m": 1.2,
                "trend_score": 80,
            },
            {
                "market": "stock",
                "symbol": "MSFT",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "confluence_score": 82,
                "risk_pct": 0.08,
                "recommended_target_pct": 0.05,
                "entry": 100,
                "stop": 92,
                "backtest_eligible": True,
            },
        ]
    )

    rows = extract_opportunities(confluence)

    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["ai_action"] == "ALERT"
    assert all(row["symbol"] != "MSFT" or row["ai_action"] != "ALERT" for row in rows)


def test_build_brief_updates_memory_and_formats_notification():
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "NVDA",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_10PCT",
                "confluence_score": 88,
                "risk_pct": 0.018,
                "recommended_target_pct": 0.10,
                "entry": 200,
                "stop": 196.4,
                "backtest_eligible": True,
                "trigger_setup": "PULLBACK",
                "relative_volume_15m": 1.4,
                "trend_score": 86,
            }
        ]
    )
    options = pd.DataFrame(
        [
            {
                "symbol": "NVDA",
                "contractSymbol": "NVDA260117C00200000",
                "option_decision": "WATCH",
                "option_score": 75,
            }
        ]
    )

    brief = build_brief(confluence_df=confluence, options_df=options, memory={"symbols": {}, "lessons": [], "alert_history": []})
    lines = build_notification_lines(brief)

    assert brief["alert_count"] == 1
    assert brief["memory"]["symbols"]["NVDA"]["alerts"] == 1
    assert brief["learning_profiles"]
    assert brief["research_queue"]
    assert brief["strategy_lab"]
    assert "Roxy" in brief["opportunities"][0]["explanation"]
    assert "NVDA" in lines[0]
    assert "option NVDA260117C00200000" in lines[0]
    assert "size" in lines[0]
    assert "confianza" in lines[0]
    assert "calidad" in lines[0]
    assert "targets 2% 204.00 / 5% 210.00 / 10% 220.00" in lines[0]
    assert "Operar" in lines[0]
    assert "razon" in lines[0]
    assert "filtro" in lines[0]
    assert brief["alert_gate_summary"]["notifications_ready"] == 1
    assert brief["alert_gate_summary"]["gate_counts"]["ALERT_READY"] == 1


def test_build_brief_does_not_alert_when_higher_timeframe_blocks():
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "NVDA",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_10PCT",
                "confluence_score": 88,
                "risk_pct": 0.018,
                "recommended_target_pct": 0.10,
                "entry": 200,
                "stop": 196.4,
                "backtest_eligible": True,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
                "relative_volume_15m": 1.4,
                "trend_score": 86,
                "trigger_score": 82,
                "higher_tf_bias": "BLOCKED",
                "higher_tf_blocks": 1,
                "htf_4h_signal": "AVOID",
            }
        ]
    )

    brief = build_brief(
        confluence_df=confluence,
        options_df=pd.DataFrame(),
        memory={"symbols": {}, "lessons": [], "alert_history": []},
    )

    assert brief["alert_count"] == 0
    assert brief["watch_count"] == 1
    assert brief["opportunities"][0]["ai_action"] == "WATCH"
    assert brief["opportunities"][0]["alert_gate"] == "WAIT_HTF_CONFIRM"
    assert "2h/4h" in brief["opportunities"][0]["alert_primary_blocker"]


def test_alert_gate_and_decision_helpers_are_human_readable():
    watch = {
        "ai_action": "WATCH",
        "signal": "WATCH",
        "trade_decision": "WAIT",
        "alert_gate": "WAIT_VOLUME",
        "alert_blockers": ["Volumen acompana: 0.60x"],
    }
    buy = {"ai_action": "ALERT", "signal": "BUY", "trade_decision": "TRADE_FOR_5PCT", "alert_gate": "ALERT_READY"}
    avoid = {"signal": "AVOID", "trade_decision": "NO_TRADE", "alert_gate": "NO_TRADE_STRUCTURE"}

    assert alert_gate_label("WAIT_15M_ENTRY") == "Esperar entrada 15m"
    assert alert_gate_label("WAIT_HTF_CONFIRM") == "Esperar confirmacion 2h/4h"
    assert alert_gate_label("BLOCKED_REALTIME_DATA") == "Bloqueado por datos realtime"
    assert human_trade_action(watch) == "Esperar"
    assert human_trade_action(buy) == "Operar"
    assert human_trade_action(avoid) == "No operar"
    assert "volumen" in human_alert_reason(watch).lower()
    assert "BUY confirmado" in human_alert_reason(buy)
    assert "No operar" in human_alert_reason(avoid)
    assert learning_action_label("COLLECT_MORE_DATA") == "Recolectar mas datos"
    assert safety_mode_label("PAPER_ONLY") == "Solo paper"
    assert experiment_status_label("SHADOW_TEST") == "Prueba en laboratorio"
    assert "BUY confirmado" in human_alert_reason(buy)
    assert "No operar" in human_alert_reason(avoid)


def test_alert_targets_text_uses_explicit_target_columns_when_present():
    text = alert_targets_text(
        {
            "entry": 100,
            "target_2pct_price": 101.8,
            "target_5pct_price": 104.9,
            "target_10pct_price": 110.5,
        }
    )

    assert text == "targets 2% 101.80 / 5% 104.90 / 10% 110.50"


def test_alert_targets_text_falls_back_to_entry_ladder():
    assert alert_targets_text({"entry": 50}) == "targets 2% 51.00 / 5% 52.50 / 10% 55.00"


def test_risk_size_text_uses_500_dollar_default_account():
    text = risk_size_text(100, 98)

    assert text.startswith("size 2 sh")
    assert "$5.00 risk" in text


def test_alert_confidence_text_combines_memory_and_readiness():
    assert alert_confidence_text({"learning_bias": "positive", "alert_readiness_score": 88}) == "alta memoria / checklist 88%"
    assert alert_confidence_text({"learning_bias": "learning"}).startswith("aprendiendo")
    assert alert_confidence_text({"learning_bias": "shadow_positive"}).startswith("laboratorio positivo")


def test_source_freshness_status_blocks_stale_data(tmp_path):
    import os

    now = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    scan = tmp_path / "scan.csv"
    confluence = tmp_path / "confluence.csv"
    scan.write_text("symbol,signal\nAAPL,BUY\n")
    confluence.write_text("symbol,signal\nAAPL,BUY\n")
    fresh_mtime = (now - timedelta(minutes=4)).timestamp()
    stale_mtime = (now - timedelta(minutes=45)).timestamp()
    os.utime(scan, (fresh_mtime, fresh_mtime))
    os.utime(confluence, (stale_mtime, stale_mtime))

    status = source_freshness_status({"scan": str(scan), "confluence": str(confluence)}, now=now)

    assert status["status"] == "STALE"
    assert status["label"] == "Estancados"
    assert status["alerts_allowed"] is False


def test_build_notification_lines_pauses_when_data_is_stale():
    brief = {
        "source_freshness": {"status": "STALE", "label": "Estancados", "alerts_allowed": False},
        "opportunities": [
            {
                "ai_action": "ALERT",
                "market": "stock",
                "symbol": "AAPL",
                "trade_decision": "TRADE_FOR_5PCT",
                "ai_score": 90,
                "entry": 100,
                "stop": 98,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
            }
        ],
    }

    assert build_notification_lines(brief) == []


def test_apply_global_alert_context_rechecks_opportunities_when_data_is_stale():
    brief = {
        "source_freshness": {
            "status": "STALE",
            "label": "Estancados",
            "detail": "live/confluencia llevan 45 min sin refrescar.",
            "alerts_allowed": False,
        },
        "realtime_health": {"status": "OK", "alerts_allowed": True},
        "alert_count": 1,
        "watch_count": 0,
        "opportunities": [
            {
                "market": "stock",
                "symbol": "AAPL",
                "ai_action": "ALERT",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "confluence_score": 82,
                "trend_score": 78,
                "trigger_score": 72,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "relative_volume_15m": 1.2,
                "backtest_eligible": True,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
            }
        ],
    }

    updated = apply_global_alert_context(brief)

    row = updated["opportunities"][0]
    assert updated["alert_count"] == 0
    assert updated["watch_count"] == 1
    assert row["ai_action"] == "WATCH"
    assert row["alert_gate"] == "BLOCKED_REALTIME_DATA"
    assert row["source_freshness"]["alerts_allowed"] is False


def test_build_notification_lines_pauses_when_realtime_health_failed():
    brief = {
        "source_freshness": {"status": "FRESH", "alerts_allowed": True},
        "realtime_health": {"status": "FAIL", "alerts_allowed": False, "detail": "heartbeat failed"},
        "opportunities": [
            {
                "ai_action": "ALERT",
                "market": "stock",
                "symbol": "AAPL",
                "trade_decision": "TRADE_FOR_5PCT",
                "ai_score": 90,
                "entry": 100,
                "stop": 98,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
            }
        ],
    }

    assert build_notification_lines(brief) == []


def test_build_notification_lines_allows_realtime_health_warning():
    brief = {
        "source_freshness": {"status": "FRESH", "alerts_allowed": True},
        "realtime_health": {"status": "WARN", "alerts_allowed": True, "detail": "disk low"},
        "market_session": {"stock_alerts_allowed": True},
        "opportunities": [
            {
                "ai_action": "ALERT",
                "market": "stock",
                "symbol": "AAPL",
                "trade_decision": "TRADE_FOR_5PCT",
                "ai_score": 90,
                "entry": 100,
                "stop": 98,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
            }
        ],
    }

    assert build_notification_lines(brief)


def test_realtime_health_status_blocks_stale_report(tmp_path):
    import os

    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    path = tmp_path / "roxy_realtime_check.json"
    path.write_text('{"status": "OK", "checks": []}')
    stale = (now - timedelta(minutes=40)).timestamp()
    os.utime(path, (stale, stale))

    status = realtime_health_status(path, now=now, max_age_minutes=15)

    assert status["status"] == "STALE"
    assert status["alerts_allowed"] is False


def test_market_session_status_marks_weekend_closed():
    status = market_session_status(now=datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc))

    assert status["stock_session"] == "Cerrado"
    assert status["stock_alerts_allowed"] is False
    assert status["crypto_session"] == "24h"


def test_market_session_status_marks_regular_hours_open():
    status = market_session_status(now=datetime(2026, 6, 8, 15, 0, tzinfo=timezone.utc))

    assert status["stock_session"] == "Mercado abierto"
    assert status["stock_alerts_allowed"] is True


def test_build_notification_lines_allows_crypto_when_stocks_closed():
    brief = {
        "market_session": {
            "stock_session": "Cerrado",
            "stock_alerts_allowed": False,
            "crypto_session": "24h",
        },
        "opportunities": [
            {
                "ai_action": "ALERT",
                "market": "stock",
                "symbol": "AAPL",
                "trade_decision": "TRADE_FOR_5PCT",
                "ai_score": 90,
                "entry": 100,
                "stop": 98,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
            },
            {
                "ai_action": "ALERT",
                "market": "crypto",
                "symbol": "BTC/USD",
                "trade_decision": "TRADE_FOR_5PCT",
                "ai_score": 90,
                "entry": 100,
                "stop": 98,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
            },
        ],
    }

    lines = build_notification_lines(brief)

    assert len(lines) == 1
    assert "BTC/USD" in lines[0]
    assert "AAPL" not in lines[0]


def test_write_brief_reports_stale_source_freshness(tmp_path, monkeypatch):
    import roxy_ai

    monkeypatch.setattr(roxy_ai, "BRIEF_TEXT_PATH", tmp_path / "brief.txt")
    monkeypatch.setattr(roxy_ai, "BRIEF_JSON_PATH", tmp_path / "brief.json")
    monkeypatch.setattr(roxy_ai, "STATUS_TEXT_PATH", tmp_path / "status.txt")
    monkeypatch.setattr(roxy_ai, "STATUS_JSON_PATH", tmp_path / "status.json")
    monkeypatch.setattr(roxy_ai, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(roxy_ai, "LEARNING_JOURNAL_PATH", tmp_path / "journal.csv")
    brief = {
        "generated_at": "2026-06-07T00:00:00+00:00",
        "alert_count": 1,
        "watch_count": 0,
        "memory_symbols": 1,
        "source_freshness": {
            "status": "STALE",
            "label": "Estancados",
            "detail": "live/confluencia llevan 45 min sin refrescar.",
            "alerts_allowed": False,
        },
        "opportunities": [
            {
                "ai_action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "trade_decision": "TRADE_FOR_5PCT",
                "entry": 100,
                "stop": 98,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
            }
        ],
        "memory": {"symbols": {}, "strategy_stats": {}, "lessons": [], "alert_history": [], "signal_journal": []},
    }

    write_brief(brief)

    text = (tmp_path / "brief.txt").read_text()
    status_text = (tmp_path / "status.txt").read_text()
    assert "Datos: Estancados" in text
    assert "Alertas pausadas" in text
    assert "ROXY STATUS" in status_text
    assert "Data: Estancados" in status_text
    assert (tmp_path / "journal.csv").exists()
    assert (tmp_path / "alert_quality.json").exists()
    assert (tmp_path / "alert_quality_history.jsonl").exists()


def test_update_memory_keeps_lesson_for_no_alerts():
    memory = update_memory_from_opportunities([], memory={"symbols": {}, "lessons": [], "alert_history": []})

    assert memory["lessons"]
    assert "solo alertar BUY" in memory["lessons"][0]


def test_watch_opportunity_is_tracked_in_signal_journal_without_alert():
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "AAPL",
                "signal": "WATCH",
                "trade_decision": "NO_TRADE",
                "confluence_score": 82,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "entry": 100,
                "stop": 98,
                "backtest_eligible": True,
                "trigger_setup": "PULLBACK",
                "relative_volume_15m": 0.7,
                "trend_score": 70,
            }
        ]
    )

    brief = build_brief(
        confluence_df=confluence,
        options_df=pd.DataFrame(),
        memory={"symbols": {}, "lessons": [], "alert_history": [], "signal_journal": []},
    )

    assert brief["alert_count"] == 0
    assert brief["signal_journal_count"] == 1
    assert brief["memory"]["alert_history"] == []
    assert brief["memory"]["signal_journal"][0]["symbol"] == "AAPL"
    assert brief["memory"]["signal_journal"][0]["status"] == "WATCHING"
    assert brief["memory"]["signal_journal"][0]["alert_gate"]


def test_signal_journal_updates_existing_key_with_latest_gate():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "WATCH",
        "trade_decision": "NO_TRADE",
        "entry": 100,
        "stop": 98,
        "recommended_target_pct": 0.05,
        "ai_action": "WATCH",
        "ai_score": 70,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "alert_gate": "WAIT_VOLUME",
        "alert_readiness_score": 66.7,
        "alert_movement": "Wait for volume.",
        "alert_blockers": ["Volumen acompana: 0.60x"],
    }
    memory = update_memory_from_opportunities(
        [row],
        memory={"symbols": {}, "strategy_stats": {}, "lessons": [], "alert_history": [], "signal_journal": []},
    )
    updated_row = dict(row)
    updated_row["ai_score"] = 80
    updated_row["alert_gate"] = "WAIT_15M_ENTRY"
    updated_row["alert_readiness_score"] = 77.8
    updated = update_memory_from_opportunities([updated_row], memory=memory)

    assert len(updated["signal_journal"]) == 1
    assert updated["signal_journal"][0]["ai_score"] == 80
    assert updated["signal_journal"][0]["alert_gate"] == "WAIT_15M_ENTRY"


def test_signal_journal_initializes_progress_from_current_row_price():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "WATCH",
        "trade_decision": "WAIT",
        "entry": 100,
        "stop": 97,
        "close_15m": 101,
        "ai_action": "WATCH",
        "ai_score": 70,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "alert_gate": "WAIT_VOLUME",
        "alert_readiness_score": 77.8,
    }

    memory = update_memory_from_opportunities(
        [row],
        memory={"symbols": {}, "strategy_stats": {}, "lessons": [], "alert_history": [], "signal_journal": []},
    )

    journal = memory["signal_journal"][0]
    assert journal["last_price"] == 101
    assert journal["max_gain_pct"] == 0.01
    assert journal["progress_to_2pct"] == 0.5


def test_write_brief_explains_top_watched_setup(tmp_path, monkeypatch):
    import roxy_ai

    monkeypatch.setattr(roxy_ai, "BRIEF_TEXT_PATH", tmp_path / "brief.txt")
    monkeypatch.setattr(roxy_ai, "BRIEF_JSON_PATH", tmp_path / "brief.json")
    monkeypatch.setattr(roxy_ai, "STATUS_TEXT_PATH", tmp_path / "status.txt")
    monkeypatch.setattr(roxy_ai, "STATUS_JSON_PATH", tmp_path / "status.json")
    monkeypatch.setattr(roxy_ai, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(roxy_ai, "LEARNING_JOURNAL_PATH", tmp_path / "journal.csv")
    brief = {
        "generated_at": "2026-06-07T00:00:00+00:00",
        "alert_count": 0,
        "watch_count": 1,
        "memory_symbols": 1,
        "opportunities": [
            {
                "symbol": "AAPL",
                "alert_gate": "WAIT_VOLUME",
                "alert_quality": "B",
                "alert_readiness_score": 77.8,
                "alert_next_action": "Esperar volumen relativo >= 0.8x.",
                "alert_movement": "Wait for relative volume.",
                "alert_blockers": ["Volumen acompana: 0.60x"],
            }
        ],
        "learning_plan": [
            {
                "strategy_family": "Pullback",
                "action": "COLLECT_MORE_DATA",
                "safety_mode": "PAPER_ONLY",
                "proposed_rule": "Track WATCH outcomes before changing production ranking.",
            }
        ],
        "memory": {"symbols": {}, "strategy_stats": {}, "lessons": [], "alert_history": [], "signal_journal": []},
    }

    write_brief(brief)

    text = (tmp_path / "brief.txt").read_text()
    assert "Setups en observacion" in text
    assert "AAPL | Esperar volumen" in text
    assert "calidad B" in text
    assert "confianza" in text
    assert "Volumen acompana" in text
    assert "Plan autonomo de aprendizaje" in text
    assert "Solo paper" in text
    status = (tmp_path / "status.json").read_text()
    assert "WAIT_VOLUME" in status
    journal = pd.read_csv(tmp_path / "journal.csv")
    assert journal.iloc[-1]["top_symbol"] == "AAPL"
    assert journal.iloc[-1]["top_gate"] == "WAIT_VOLUME"
    assert (tmp_path / "alert_quality.json").exists()
    assert (tmp_path / "alert_quality_history.jsonl").exists()


def test_learning_journal_dedupes_same_cycle_and_caps_rows(tmp_path):
    brief = {
        "generated_at": "2026-06-07T00:00:00+00:00",
        "alert_count": 0,
        "watch_count": 1,
        "memory_symbols": 2,
        "opportunities": [
            {
                "symbol": "AAPL",
                "market": "stock",
                "ai_action": "WATCH",
                "signal": "WATCH",
                "strategy_family": "PULLBACK",
                "alert_gate": "WAIT_VOLUME",
                "alert_quality": "B",
                "alert_readiness_score": 78.0,
                "alert_next_action": "Esperar volumen y entrada 15m.",
                "alert_blockers": ["Volumen acompana: 0.70x"],
                "learning_bias": "learning",
            }
        ],
        "learning_profiles": [
            {
                "bias": "learning",
                "lesson": "Pullback necesita mas evidencia antes de alertar.",
                "recommendation": "Mantener en paper.",
            }
        ],
        "learning_plan": [
            {
                "strategy_family": "PULLBACK",
                "proposed_rule": "Probar filtro de volumen en 15m.",
            }
        ],
        "experiment_registry": [{"status": "Shadow test"}],
    }
    path = tmp_path / "journal.csv"

    row = build_learning_journal_row(brief)
    first = append_learning_journal(brief, path=path, max_rows=2)
    second = append_learning_journal(brief, path=path, max_rows=2)
    changed = dict(brief)
    changed["generated_at"] = "2026-06-08T00:00:00+00:00"
    append_learning_journal(changed, path=path, max_rows=2)
    changed_again = dict(changed)
    changed_again["generated_at"] = "2026-06-09T00:00:00+00:00"
    append_learning_journal(changed_again, path=path, max_rows=2)

    journal = pd.read_csv(path)
    assert row["top_symbol"] == "AAPL"
    assert first["fingerprint"] == second["fingerprint"]
    assert len(journal) == 2
    assert list(journal["date"]) == ["2026-06-08", "2026-06-09"]
    assert journal.iloc[-1]["learning_lesson"] == "Pullback necesita mas evidencia antes de alertar."


def test_status_snapshot_summarizes_top_setup(tmp_path, monkeypatch):
    import roxy_ai

    monkeypatch.setattr(roxy_ai, "STATUS_TEXT_PATH", tmp_path / "status.txt")
    monkeypatch.setattr(roxy_ai, "STATUS_JSON_PATH", tmp_path / "status.json")
    brief = {
        "generated_at": "2026-06-07T00:00:00+00:00",
        "mode": "AI_WATCH_24H",
        "alert_count": 0,
        "watch_count": 1,
        "memory_symbols": 4,
        "source_freshness": {"label": "Frescos", "detail": "live/confluencia actualizados hace 2 min.", "alerts_allowed": True},
        "market_session": {"stock_session": "Mercado abierto", "crypto_session": "24h", "stock_alerts_allowed": True},
        "opportunities": [
            {
                "symbol": "AAPL",
                "market": "stock",
                "ai_action": "WATCH",
                "signal": "WATCH",
                "alert_gate": "WAIT_VOLUME",
                "alert_quality": "B",
                "alert_readiness_score": 77.8,
                "alert_next_action": "Esperar volumen relativo >= 0.8x.",
                "alert_blockers": ["Volumen acompana: 0.60x"],
            }
        ],
        "learning_plan": [{"action": "COLLECT_MORE_DATA"}],
        "experiment_registry": [{"status": "Shadow test"}],
    }

    status = build_status_snapshot(brief)
    written = write_status_snapshot(brief)

    assert status["top_symbol"] == "AAPL"
    assert status["top_gate"] == "WAIT_VOLUME"
    assert status["top_readiness"] == 77.8
    assert written["learning_plan_count"] == 1
    assert "Esperar volumen" in (tmp_path / "status.txt").read_text()


def test_update_alert_outcomes_marks_target_milestones():
    memory = {
        "symbols": {},
        "lessons": [],
        "alert_history": [
            {
                "symbol": "AAPL",
                "entry": 100,
                "stop": 97,
                "status": "OPEN",
                "milestones": [],
            }
        ],
    }

    updated = update_alert_outcomes(memory, {"AAPL": 102.5})

    assert updated["alert_history"][0]["status"] == "HIT_2PCT"
    assert "2%" in updated["alert_history"][0]["milestones"]
    assert updated["alert_history"][0]["max_gain_pct"] == 0.025
    assert updated["alert_history"][0]["progress_to_2pct"] == 1.0


def test_update_trade_progress_tracks_partial_move_and_drawdown():
    row = {"max_price": 101, "min_price": 99}

    update_trade_progress(row, current=101.5, entry=100, stop=97)

    assert row["last_price"] == 101.5
    assert row["max_price"] == 101.5
    assert row["min_price"] == 99
    assert row["max_gain_pct"] == 0.015
    assert row["max_drawdown_pct"] == 0.01
    assert row["progress_to_2pct"] == 0.75
    assert round(row["progress_to_stop"], 4) == 0.3333


def test_current_prices_by_symbol_uses_multiple_price_columns():
    scan = pd.DataFrame(
        [
            {"symbol": "AAPL", "close": 101.5, "entry": 100.0},
            {"symbol": "MSFT", "last_price": 202.0},
        ]
    )
    confluence = pd.DataFrame(
        [
            {"symbol": "TTEK", "price": 28.1},
            {"symbol": "NVDA", "entry": 122.4},
        ]
    )

    prices = current_prices_by_symbol(scan, confluence)

    assert prices["AAPL"] == 101.5
    assert prices["MSFT"] == 202.0
    assert prices["TTEK"] == 28.1
    assert prices["NVDA"] == 122.4


def test_update_alert_outcomes_marks_signal_journal_without_strategy_hit():
    memory = {
        "symbols": {},
        "lessons": [],
        "strategy_stats": {"Pullback": {"seen": 1, "alerts": 0, "hit_2pct": 0, "stops": 0}},
        "alert_history": [],
        "signal_journal": [
            {
                "symbol": "AAPL",
                "entry": 100,
                "stop": 97,
                "status": "WATCHING",
                "milestones": [],
                "strategy_family": "Pullback",
            }
        ],
    }

    updated = update_alert_outcomes(memory, {"AAPL": 102.5})

    assert updated["signal_journal"][0]["status"] == "HIT_2PCT"
    assert "2%" in updated["signal_journal"][0]["milestones"]
    assert updated["signal_journal"][0]["max_gain_pct"] == 0.025
    assert updated["strategy_stats"]["Pullback"]["hit_2pct"] == 0


def test_update_alert_outcomes_records_strategy_stats():
    memory = {
        "symbols": {},
        "lessons": [],
        "strategy_stats": {"Pullback": {"seen": 1, "alerts": 1}},
        "alert_history": [
            {
                "symbol": "AAPL",
                "entry": 100,
                "stop": 97,
                "status": "OPEN",
                "milestones": [],
                "strategy_family": "Pullback",
            }
        ],
    }

    updated = update_alert_outcomes(memory, {"AAPL": 105.5})

    assert updated["strategy_stats"]["Pullback"]["hit_2pct"] == 1
    assert updated["strategy_stats"]["Pullback"]["hit_5pct"] == 1


def test_apply_memory_lessons_downgrades_weak_strategy_history():
    rows = [
        {
            "symbol": "AAPL",
            "trigger_setup": "TREND_CONTINUATION",
            "trend_setup": "TREND_CONTINUATION",
            "ai_score": 90,
            "ai_action": "ALERT",
        }
    ]
    memory = {"strategy_stats": {"Canal alcista": {"alerts": 4, "hit_2pct": 0, "stops": 3}}}

    adjusted = apply_memory_lessons(rows, memory)

    assert adjusted[0]["ai_action"] == "WATCH"
    assert adjusted[0]["memory_filter"] == "WEAK_STRATEGY_HISTORY"


def test_strategy_learning_profile_promotes_effective_strategy():
    profile = strategy_learning_profile(
        "Pullback",
        {"seen": 8, "alerts": 5, "hit_2pct": 4, "hit_5pct": 2, "hit_10pct": 1, "stops": 1},
    )

    assert profile["bias"] == "positive"
    assert profile["score_adjustment"] > 0
    assert profile["adaptive_weight"] > 1


def test_strategy_learning_profile_uses_shadow_watch_progress_before_alert_sample():
    profile = strategy_learning_profile(
        "Pullback",
        {
            "seen": 6,
            "alerts": 0,
            "shadow_tracked": 3,
            "shadow_observed": 3,
            "shadow_near_2pct": 2,
            "shadow_near_stop": 0,
        },
    )

    assert profile["bias"] == "shadow_positive"
    assert profile["score_adjustment"] == 3
    assert profile["shadow_target_rate"] > 0.55


def test_apply_memory_lessons_uses_shadow_memory_for_small_score_adjustment():
    rows = [
        {
            "symbol": "AAPL",
            "trigger_setup": "PULLBACK",
            "trend_setup": "TREND_CONTINUATION",
            "ai_score": 70,
            "ai_action": "WATCH",
        }
    ]
    memory = {
        "strategy_stats": {"Pullback": {"seen": 6, "alerts": 0}},
        "signal_journal": [
            {
                "symbol": "AAPL",
                "ai_action": "WATCH",
                "strategy_family": "Pullback",
                "status": "WATCHING",
                "progress_to_2pct": 0.80,
                "progress_to_stop": 0.10,
            },
            {
                "symbol": "AMD",
                "ai_action": "WATCH",
                "strategy_family": "Pullback",
                "status": "WATCHING",
                "progress_to_2pct": 0.90,
                "progress_to_stop": 0.20,
            },
            {
                "symbol": "MSFT",
                "ai_action": "WATCH",
                "strategy_family": "Pullback",
                "status": "WATCHING",
                "progress_to_2pct": 0.20,
                "progress_to_stop": 0.10,
            },
        ],
    }

    adjusted = apply_memory_lessons(rows, memory)

    assert adjusted[0]["learning_bias"] == "shadow_positive"
    assert adjusted[0]["ai_score"] == 73
    assert memory["strategy_stats"]["Pullback"]["shadow_observed"] == 3


def test_refresh_strategy_shadow_stats_recomputes_exact_counts():
    memory = {
        "strategy_stats": {"Pullback": {"shadow_observed": 99}},
        "signal_journal": [
            {
                "symbol": "AAPL",
                "ai_action": "WATCH",
                "strategy_family": "Pullback",
                "status": "HIT_2PCT",
                "milestones": ["2%"],
                "progress_to_2pct": 1.0,
                "progress_to_stop": 0.0,
            },
            {
                "symbol": "MSFT",
                "ai_action": "WATCH",
                "strategy_family": "Pullback",
                "status": "STOP",
                "progress_to_2pct": 0.0,
                "progress_to_stop": 1.0,
            },
        ],
    }

    refresh_strategy_shadow_stats(memory)

    stats = memory["strategy_stats"]["Pullback"]
    assert stats["shadow_tracked"] == 2
    assert stats["shadow_observed"] == 2
    assert stats["shadow_hit_2pct"] == 1
    assert stats["shadow_near_2pct"] == 1
    assert stats["shadow_near_stop"] == 1


def test_summarize_learning_and_research_queue_explain_next_steps():
    memory = {
        "strategy_stats": {
            "Canal alcista": {"seen": 10, "alerts": 5, "hit_2pct": 4, "hit_5pct": 2, "stops": 1},
            "Canal lateral": {"seen": 8, "alerts": 4, "hit_2pct": 0, "stops": 3},
        }
    }

    profiles = summarize_strategy_learning(memory)
    queue = learning_research_queue(memory)

    assert profiles[0]["strategy_family"] == "Canal alcista"
    assert any(item["priority"] == "promote" for item in queue)
    assert any(item["priority"] == "tighten_filter" for item in queue)


def test_gate_research_queue_summarizes_blocking_conditions():
    memory = {
        "signal_journal": [
            {
                "symbol": "AAPL",
                "strategy_family": "Pullback",
                "alert_gate": "WAIT_VOLUME",
                "alert_blockers": ["Volumen acompana: 0.60x", "15m da entrada: WAIT"],
            },
            {
                "symbol": "MSFT",
                "strategy_family": "Pullback",
                "alert_gate": "WAIT_VOLUME",
                "alert_blockers": ["Volumen acompana: 0.70x"],
            },
        ]
    }

    queue = gate_research_queue(memory)

    assert queue[0]["strategy_family"] == "Pullback"
    assert queue[0]["gate"] == "WAIT_VOLUME"
    assert queue[0]["count"] == 2
    assert "Volumen acompana" in queue[0]["top_blocker"]


def test_summarize_alert_gates_counts_blockers_and_readiness():
    brief = {
        "opportunities": [
            {
                "symbol": "AAPL",
                "ai_action": "ALERT",
                "alert_gate": "ALERT_READY",
                "alert_quality": "A+",
                "alert_readiness_score": 100,
            },
            {
                "symbol": "MSFT",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_VOLUME",
                "alert_quality": "B",
                "alert_readiness_score": 82,
                "alert_blockers": ["Volumen acompana: 0.60x"],
                "alert_primary_blocker": "Volumen acompana: 0.60x",
            },
        ]
    }

    summary = summarize_alert_gates(brief, notification_lines=["AAPL alert"])

    assert summary["total_opportunities"] == 2
    assert summary["notifications_ready"] == 1
    assert summary["avg_readiness"] == 91.0
    assert summary["gate_counts"]["ALERT_READY"] == 1
    assert summary["gate_counts"]["WAIT_VOLUME"] == 1
    assert summary["blocker_counts"]["Volumen acompana"] == 1
    assert summary["top_gate_label"] == "Listo para operar manual"


def test_build_strategy_lab_promotes_or_tightens_from_evidence():
    memory = {
        "strategy_stats": {
            "Canal alcista": {"seen": 12, "alerts": 5, "hit_2pct": 4, "hit_5pct": 2, "stops": 1},
            "Canal lateral": {"seen": 8, "alerts": 4, "hit_2pct": 0, "stops": 3},
        }
    }
    backtest_summary = pd.DataFrame(
        [
            {"strategy_family": "Canal alcista", "trades": 18, "win_rate": 0.56, "profit_factor": 1.8},
            {"strategy_family": "Canal lateral", "trades": 14, "win_rate": 0.35, "profit_factor": 0.7},
        ]
    )

    lab = build_strategy_lab(memory, backtest_summary=backtest_summary)
    by_family = {row["strategy_family"]: row for row in lab}

    assert by_family["Canal alcista"]["lab_state"] == "Promote"
    assert by_family["Canal lateral"]["lab_state"] == "Tighten filter"
    assert by_family["Canal alcista"]["evidence_score"] > by_family["Canal lateral"]["evidence_score"]


def test_build_strategy_lab_collects_data_when_memory_is_thin():
    memory = {"strategy_stats": {"Pullback": {"seen": 2, "alerts": 1, "hit_2pct": 0, "stops": 0}}}

    lab = build_strategy_lab(memory)

    assert lab[0]["strategy_family"] == "Pullback"
    assert lab[0]["lab_state"] == "Collect data"


def test_build_strategy_lab_surfaces_shadow_watch_metrics():
    memory = {
        "strategy_stats": {"Pullback": {"seen": 5, "alerts": 0}},
        "signal_journal": [
            {"strategy_family": "Pullback", "ai_action": "WATCH", "progress_to_2pct": 0.8, "progress_to_stop": 0.1},
            {"strategy_family": "Pullback", "ai_action": "WATCH", "progress_to_2pct": 0.9, "progress_to_stop": 0.2},
            {"strategy_family": "Pullback", "ai_action": "WATCH", "progress_to_2pct": 0.1, "progress_to_stop": 0.0},
        ],
    }

    lab = build_strategy_lab(memory)

    assert lab[0]["strategy_family"] == "Pullback"
    assert lab[0]["memory_bias"] == "shadow_positive"
    assert lab[0]["lab_state"] == "Watch"
    assert lab[0]["shadow_observed"] == 3
    assert lab[0]["shadow_target_rate"] > 0.55


def test_autonomous_learning_plan_promotes_only_in_paper_mode():
    memory = {
        "strategy_stats": {
            "Pullback": {
                "seen": 8,
                "alerts": 5,
                "hit_2pct": 4,
                "hit_5pct": 2,
                "hit_10pct": 1,
                "stops": 1,
            }
        },
        "signal_journal": [],
    }

    plan = autonomous_learning_plan(memory)

    assert plan[0]["strategy_family"] == "Pullback"
    assert plan[0]["action"] == "PROMOTE_IN_RANKING"
    assert plan[0]["safety_mode"] == "PAPER_ONLY"
    assert "smart gate" in plan[0]["proposed_rule"]


def test_autonomous_learning_plan_adds_shadow_test_from_gate_research():
    memory = {
        "strategy_stats": {},
        "signal_journal": [
            {
                "strategy_family": "Pullback",
                "alert_gate": "WAIT_VOLUME",
                "alert_blockers": ["Volumen acompana: 0.70x"],
            }
        ],
    }

    plan = autonomous_learning_plan(memory)

    assert any(row["action"] == "SHADOW_TEST_WAIT_VOLUME" for row in plan)
    assert all(row["safety_mode"] == "PAPER_ONLY" for row in plan)


def test_update_experiment_registry_tracks_paper_only_plan_without_duplicates():
    memory = {
        "experiment_registry": [],
        "alert_history": [
            {"strategy_family": "Pullback", "status": "HIT_2PCT", "milestones": ["2%"]},
            {"strategy_family": "Pullback", "status": "STOP"},
        ],
        "signal_journal": [
            {"strategy_family": "Pullback", "status": "WATCHING"},
        ],
    }
    plan = [
        {
            "strategy_family": "Pullback",
            "source": "strategy_lab",
            "action": "PROMOTE_IN_RANKING",
            "evidence_score": 0.72,
            "proposed_rule": "Subir peso paper-alert solo con smart gate completo.",
            "activation_rule": "Mantener stop_rate bajo.",
            "why": "Historial favorece target 2%.",
        }
    ]

    first = update_experiment_registry(memory, plan)
    second = update_experiment_registry(memory, plan)

    assert len(second) == 1
    assert first[0]["key"] == experiment_key(plan[0])
    assert second[0]["safety_mode"] == "PAPER_ONLY"
    assert second[0]["status"] == "PAPER_WEIGHT_READY"
    assert second[0]["seen_count"] == 2
    assert second[0]["promoted_to_live"] is False
    assert second[0]["sample_count"] == 3
    assert second[0]["measured_count"] == 2
    assert second[0]["hit_2_rate"] == 0.5
    assert second[0]["stop_rate"] == 0.5


def test_experiment_outcome_stats_can_filter_shadow_gate():
    memory = {
        "alert_history": [],
        "signal_journal": [
            {"strategy_family": "Pullback", "alert_gate": "WAIT_VOLUME", "status": "HIT_2PCT", "milestones": ["2%"]},
            {"strategy_family": "Pullback", "alert_gate": "WAIT_VOLUME", "status": "STOP"},
            {"strategy_family": "Pullback", "alert_gate": "WAIT_15M_ENTRY", "status": "STOP"},
        ],
    }

    stats = experiment_outcome_stats(
        memory,
        {"strategy_family": "Pullback", "action": "SHADOW_TEST_WAIT_VOLUME"},
    )

    assert stats["sample_count"] == 2
    assert stats["measured_count"] == 2
    assert stats["hit_2_rate"] == 0.5
    assert stats["stop_rate"] == 0.5


def test_build_brief_includes_experiment_registry():
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "AAPL",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "confluence_score": 84,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "entry": 100,
                "stop": 98,
                "backtest_eligible": True,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
                "relative_volume_15m": 1.2,
                "trend_score": 82,
            }
        ]
    )
    memory = {
        "symbols": {},
        "strategy_stats": {"Pullback": {"seen": 8, "alerts": 5, "hit_2pct": 4, "hit_5pct": 2, "stops": 1}},
        "lessons": [],
        "alert_history": [],
        "signal_journal": [],
        "experiment_registry": [],
    }

    brief = build_brief(confluence_df=confluence, options_df=pd.DataFrame(), memory=memory)

    assert brief["experiment_registry"]
    assert brief["memory"]["experiment_registry"]
    assert all(row["safety_mode"] == "PAPER_ONLY" for row in brief["experiment_registry"])


def test_explain_opportunity_includes_strategy_memory_and_risk():
    row = {
        "symbol": "AAPL",
        "trigger_setup": "TREND_CONTINUATION",
        "trend_setup": "TREND_CONTINUATION",
        "confluence_score": 84,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
    }
    memory = {"strategy_stats": {"Canal alcista": {"seen": 6, "alerts": 4, "hit_2pct": 3, "stops": 1}}}

    text = explain_opportunity(row, memory)

    assert "AAPL" in text
    assert "Canal alcista" in text
    assert "Riesgo medido 2.00%" in text
