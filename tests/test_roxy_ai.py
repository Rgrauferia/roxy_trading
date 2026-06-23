import json

import pandas as pd
import pytest
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
    chart_health_contract_index,
    crypto_scan_candidate_rows,
    current_prices_by_symbol,
    explain_opportunity,
    experiment_status_label,
    experiment_key,
    experiment_outcome_stats,
    extract_opportunities,
    gate_research_queue,
    learning_research_queue,
    learning_action_label,
    macro_calendar_status,
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
import roxy_ai


@pytest.fixture(autouse=True)
def _isolate_strategy_overrides(monkeypatch):
    monkeypatch.setattr(
        roxy_ai,
        "load_strategy_overrides",
        lambda: {"version": 1, "strategy_overrides": {}},
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


def test_extract_opportunities_uses_scanner_score_when_confluence_score_missing():
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "RBLX",
                "signal": "WATCH",
                "score": 82,
                "setup": "PULLBACK",
                "entry": 51.56,
                "stop": 50.5,
                "relative_volume": 1.25,
                "backtest_eligible": True,
            }
        ]
    )

    rows = extract_opportunities(confluence)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "RBLX"
    assert rows[0]["ai_action"] == "WATCH"
    assert rows[0]["ai_score"] >= 70
    assert rows[0]["risk_pct"] == 0.020559
    assert rows[0]["recommended_target_pct"] == 0.02


def test_extract_opportunities_dedupes_scanner_rows_by_market_symbol():
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "RBLX",
                "tf": "15m",
                "signal": "WATCH",
                "score": 88,
                "setup": "TREND_CONTINUATION",
                "entry": 51.56,
                "stop": 50.5,
                "relative_volume": 1.2,
                "backtest_eligible": True,
            },
            {
                "market": "stock",
                "symbol": "RBLX",
                "tf": "1h",
                "signal": "WATCH",
                "score": 82,
                "setup": "TREND_CONTINUATION",
                "entry": 51.5,
                "stop": 50.0,
                "relative_volume": 1.0,
                "backtest_eligible": True,
            },
        ]
    )

    rows = extract_opportunities(confluence)

    assert [row["symbol"] for row in rows] == ["RBLX"]
    assert rows[0]["tf"] == "15m"


def test_crypto_scan_candidate_rows_extracts_unique_high_score_crypto_watchlist():
    scan = pd.DataFrame(
        [
            {"market": "stock", "symbol": "AAPL", "tf": "15m", "score": 100, "raw_signal": "BUY"},
            {
                "market": "crypto",
                "symbol": "BTC/USD",
                "tf": "15m",
                "score": 100,
                "raw_signal": "BUY",
                "signal": "WATCH",
                "setup": "TREND_CONTINUATION",
                "entry": 100,
                "stop": 97,
                "relative_volume": 1.4,
                "backtest_eligible": False,
            },
            {"market": "crypto", "symbol": "MATIC/USD", "tf": "15m", "score": 100, "raw_signal": "BUY"},
            {"market": "crypto", "symbol": "BTC/USD", "tf": "1h", "score": 90, "raw_signal": "BUY"},
            {"market": "crypto", "symbol": "ETH/USD", "tf": "15m", "score": 54, "signal": "WATCH"},
        ]
    )

    rows = crypto_scan_candidate_rows(scan)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTC/USD"
    assert rows[0]["market"] == "crypto"
    assert rows[0]["ai_action"] == "WATCH"
    assert rows[0]["crypto_rescue_candidate"] is True
    assert rows[0]["risk_pct"] == 0.03
    assert all(row["symbol"] != "MATIC/USD" for row in rows)


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


def test_build_brief_includes_weekly_newsletter_context(monkeypatch):
    monkeypatch.setattr(
        roxy_ai,
        "newsletter_context",
        lambda: {
            "configured": True,
            "label": "Newsletter semanal",
            "detail": "IA / desarrollo",
            "risk_level": "MEDIUM",
            "watchlist_symbols": ["NVDA", "AMD"],
            "market_news": [
                {
                    "title": "Resumen de la Semana",
                    "source": "Finhabits",
                    "timestamp": "2026-06-13T11:04:00-04:00",
                    "summary": "IA / desarrollo",
                }
            ],
        },
    )

    brief = build_brief(
        confluence_df=pd.DataFrame(),
        options_df=pd.DataFrame(),
        memory={"symbols": {}, "lessons": [], "alert_history": []},
    )

    assert brief["newsletter_context"]["label"] == "Newsletter semanal"
    assert brief["market_news"][0]["source"] == "Finhabits"


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


def test_macro_calendar_status_detects_active_fed_event(tmp_path):
    path = tmp_path / "macro_events.csv"
    path.write_text(
        "date,time,event,severity,currency,notes\n"
        "2026-06-11,14:00,FOMC Rate Decision,HIGH,USD,decision FED\n"
    )
    now = datetime(2026, 6, 11, 17, 30, tzinfo=timezone.utc)

    status = macro_calendar_status(path, now=now)

    assert status["configured"] is True
    assert status["active"] is True
    assert status["label"] == "Macro activo"
    assert status["top_event"]["title"] == "FOMC Rate Decision"


def test_apply_global_alert_context_demotes_alert_during_macro_event():
    brief = {
        "opportunities": [
            {
                "market": "stock",
                "symbol": "AAPL",
                "ai_action": "ALERT",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "confluence_score": 82,
                "ai_score": 82,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "entry": 100,
                "stop": 98,
                "backtest_eligible": True,
                "relative_volume_15m": 1.2,
                "trend_score": 80,
                "trigger_score": 74,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
                "higher_tf_bias": "CONFIRMED",
            }
        ],
        "source_freshness": {"alerts_allowed": True, "label": "Frescos"},
        "realtime_health": {"alerts_allowed": True, "label": "OK"},
        "market_session": {"stock_alerts_allowed": True},
        "macro_calendar": {
            "active": True,
            "label": "Macro activo",
            "detail": "FOMC activo.",
            "top_event": {"title": "FOMC Rate Decision", "severity": "HIGH"},
        },
    }

    updated = apply_global_alert_context(brief, memory={})

    row = updated["opportunities"][0]
    assert row["ai_action"] == "WATCH"
    assert row["macro_event"] is True
    assert row["alert_gate"] == "WAIT_MACRO_CONFIRMATION"
    assert updated["alert_count"] == 0


def test_apply_global_alert_context_attaches_live_chart_contract(tmp_path, monkeypatch):
    chart_path = tmp_path / "chart_realtime_health.json"
    monkeypatch.setattr(roxy_ai, "CHART_REALTIME_HEALTH_PATH", chart_path)
    chart_path.write_text(
        json.dumps(
            {
                "charts": [
                    {
                        "symbol": "ETH/USD",
                        "timeframe": "1h",
                        "status": "OK",
                        "label": "Viva",
                        "tone": "buy",
                        "latest": "2026-06-11 13:00",
                        "age_minutes": 2.0,
                        "candle_phase": "NEW_CANDLE",
                        "candle_phase_label": "Vela nueva",
                        "candle_progress_pct": 3.3,
                    }
                ]
            }
        )
    )
    brief = {
        "opportunities": [
            {
                "market": "crypto",
                "symbol": "ETH/USD",
                "timeframe": "1h",
                "ai_action": "ALERT",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "confluence_score": 88,
                "ai_score": 88,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "backtest_eligible": True,
                "relative_volume_15m": 1.2,
                "trend_score": 82,
                "trigger_score": 76,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
            }
        ],
        "source_freshness": {"alerts_allowed": True, "label": "Frescos"},
        "realtime_health": {"alerts_allowed": True, "crypto_alerts_allowed": True, "label": "OK"},
    }

    updated = apply_global_alert_context(brief, memory={})
    row = updated["opportunities"][0]

    assert row["chart_data_gate"] == "LIVE_DATA_OK"
    assert row["chart_operable"] is True
    assert row["chart_candle_phase_label"] == "Vela nueva"
    assert row["alert_gate"] == "ALERT_READY"
    assert any(item["rule"] == "Grafica operable" and item["passed"] for item in row["smart_alert"]["checks"])


def test_apply_global_alert_context_resolves_missing_crypto_chart_contract(monkeypatch):
    monkeypatch.setattr(roxy_ai, "chart_health_contract_index", lambda: {})
    calls = []

    def fake_resolve(symbol, market, timeframe):
        calls.append((symbol, market, timeframe))
        return {
            "gate": "LIVE_DATA_OK",
            "operable": True,
            "source_label": "live-fetch",
            "timeframe": timeframe,
            "candle_phase_label": "Vela nueva",
            "age_minutes": 1.0,
        }

    monkeypatch.setattr(roxy_ai, "resolve_live_chart_contract", fake_resolve)
    brief = {
        "opportunities": [
            {
                "market": "crypto",
                "symbol": "SOL/USD",
                "timeframe": "1h",
                "ai_action": "WATCH",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 70,
                "ai_score": 70,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "backtest_eligible": True,
                "relative_volume_15m": 1.2,
                "trend_score": 82,
                "trigger_score": 55,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
            }
        ],
        "source_freshness": {"alerts_allowed": True, "label": "Frescos"},
        "realtime_health": {"alerts_allowed": True, "crypto_alerts_allowed": True, "label": "OK"},
    }

    updated = apply_global_alert_context(brief, memory={})
    row = updated["opportunities"][0]

    assert calls == [("SOL/USD", "crypto", "1h")]
    assert row["chart_data_gate"] == "LIVE_DATA_OK"
    assert row["chart_operable"] is True
    assert "CHART_CONTRACT_MISSING" not in " ".join(row["alert_blockers"])


def test_apply_global_alert_context_blocks_alert_when_chart_health_is_stale(tmp_path, monkeypatch):
    chart_path = tmp_path / "chart_realtime_health.json"
    monkeypatch.setattr(roxy_ai, "CHART_REALTIME_HEALTH_PATH", chart_path)
    chart_path.write_text(
        json.dumps(
            {
                "charts": [
                    {
                        "symbol": "ETH/USD",
                        "timeframe": "1h",
                        "status": "FAIL",
                        "label": "Estancada",
                        "tone": "avoid",
                        "latest": "2026-06-11 09:00",
                        "age_minutes": 260.0,
                        "candle_phase": "STALE",
                        "candle_phase_label": "Sin pulso",
                    }
                ]
            }
        )
    )
    brief = {
        "opportunities": [
            {
                "market": "crypto",
                "symbol": "ETH/USD",
                "timeframe": "1h",
                "ai_action": "ALERT",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "confluence_score": 88,
                "ai_score": 88,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "backtest_eligible": True,
                "relative_volume_15m": 1.2,
                "trend_score": 82,
                "trigger_score": 76,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
            }
        ],
        "source_freshness": {"alerts_allowed": True, "label": "Frescos"},
        "realtime_health": {"alerts_allowed": True, "crypto_alerts_allowed": True, "label": "OK"},
    }

    updated = apply_global_alert_context(brief, memory={})
    row = updated["opportunities"][0]

    assert row["ai_action"] == "WATCH"
    assert row["chart_data_gate"] == "NO_TRADE_STALE_DATA"
    assert row["chart_operable"] is False
    assert row["alert_gate"] == "BLOCKED_REALTIME_DATA"
    assert row["alert_primary_blocker"].startswith("Grafica operable")


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


def test_apply_global_alert_context_blocks_stock_when_premium_provider_auth_fails():
    brief = {
        "source_freshness": {"status": "FRESH", "label": "Frescos", "alerts_allowed": True},
        "realtime_health": {
            "status": "WARN",
            "label": "Premium bloqueado",
            "detail": "chart_provider_effective: 4 provider source(s), issue WMT 1h alpaca_auth",
            "alerts_allowed": True,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
        },
        "alert_count": 1,
        "watch_count": 0,
        "opportunities": [
            {
                "market": "stock",
                "symbol": "WMT",
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
    assert row["ai_action"] == "WATCH"
    assert row["alert_gate"] == "BLOCKED_REALTIME_DATA"
    assert row["realtime_health"]["stock_alerts_allowed"] is False


def test_apply_global_alert_context_rescues_crypto_scan_candidates_when_stock_premium_is_blocked():
    brief = {
        "source_freshness": {"status": "FRESH", "label": "Frescos", "alerts_allowed": True},
        "realtime_health": {
            "status": "WARN",
            "label": "Premium bloqueado",
            "alerts_allowed": True,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
            "market_realtime": {
                "blocked_markets": ["stock", "options"],
                "markets": {
                    "stock": {"alerts_allowed": False},
                    "crypto": {"alerts_allowed": True},
                },
            },
        },
        "alert_count": 1,
        "watch_count": 0,
        "opportunities": [
            {
                "market": "stock",
                "symbol": "WMT",
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
        "crypto_scan_candidates": [
            {
                "market": "crypto",
                "symbol": "BTC/USD",
                "ai_action": "WATCH",
                "signal": "BUY",
                "trade_decision": "WAIT_FOR_TRIGGER",
                "ai_score": 100,
                "confluence_score": 100,
                "trigger_score": 100,
                "trend_score": 100,
                "trigger_setup": "TREND_CONTINUATION",
                "trend_setup": "TREND_CONTINUATION",
                "entry": 100,
                "stop": 97,
                "risk_pct": 0.03,
                "recommended_target_pct": 0.02,
                "relative_volume_15m": 1.4,
                "backtest_eligible": False,
                "crypto_rescue_candidate": True,
            }
        ],
    }

    updated = apply_global_alert_context(brief)
    crypto_rows = [row for row in updated["opportunities"] if row.get("market") == "crypto"]
    stock_rows = [row for row in updated["opportunities"] if row.get("market") == "stock"]

    assert len(crypto_rows) == 1
    assert crypto_rows[0]["symbol"] == "BTC/USD"
    assert crypto_rows[0]["ai_action"] == "WATCH"
    assert crypto_rows[0]["crypto_rescue_active"] is True
    assert crypto_rows[0]["alert_gate"] != "BLOCKED_REALTIME_DATA"
    assert stock_rows[0]["alert_gate"] == "BLOCKED_REALTIME_DATA"
    assert updated["opportunities"][0]["symbol"] == "BTC/USD"
    assert updated["alert_gate_summary"]["top_gate"] == crypto_rows[0]["alert_gate"]
    assert updated["crypto_rescue"]["rescued_count"] == 1
    assert updated["alert_gate_summary"]["total_opportunities"] == 2


def test_realtime_health_status_degrades_recoverable_brief_failure_to_crypto_route(tmp_path):
    report = tmp_path / "roxy_realtime_check.json"
    report.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "generated_at": "2026-06-11T12:00:00+00:00",
                "market_realtime": {
                    "allowed_markets": ["crypto"],
                    "blocked_markets": ["stock", "options"],
                    "active_route_label": "Operar solo CRYPTO",
                    "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                },
                "checks": [
                    {
                        "name": "ai_brief",
                        "status": "FAIL",
                        "detail": "live/confluencia llevan 34 min sin refrescar.",
                    },
                    {
                        "name": "operational_summary_contract",
                        "status": "FAIL",
                        "detail": "route label mismatch",
                    },
                ],
            }
        )
    )

    status = realtime_health_status(
        report,
        now=datetime(2026, 6, 11, 12, 1, tzinfo=timezone.utc),
    )

    assert status["status"] == "WARN"
    assert status["label"] == "Health recuperando"
    assert status["alerts_allowed"] is True
    assert status["stock_alerts_allowed"] is False
    assert status["crypto_alerts_allowed"] is True
    assert status["active_route_label"] == "Operar solo CRYPTO"
    assert status["allowed_markets"] == ["crypto"]


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


def test_build_notification_lines_filters_stock_when_premium_provider_blocked_but_keeps_crypto():
    brief = {
        "source_freshness": {"status": "FRESH", "alerts_allowed": True},
        "realtime_health": {
            "status": "WARN",
            "label": "Premium bloqueado",
            "alerts_allowed": True,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
        },
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


def test_realtime_health_status_blocks_stock_on_provider_auth_warn(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    path = tmp_path / "roxy_realtime_check.json"
    path.write_text(
        json.dumps(
            {
                "status": "WARN",
                "checks": [
                    {
                        "name": "chart_provider_effective",
                        "status": "WARN",
                        "detail": "4 provider source(s), issue WMT 1h alpaca_auth, alternate polygon_not_configured",
                        "auth_fallback_count": 1,
                        "fallback_reason_counts": {"alpaca_auth": 1},
                        "premium_recovery_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                    }
                ],
                "provider_recovery": {
                    "label": "Premium bloqueado",
                    "premium_blocked": True,
                    "stock_alerts_allowed": False,
                    "polygon_missing_count": 1,
                },
                "market_realtime": {
                    "active_route": "PARTIAL_MARKET_ROUTE",
                    "active_route_label": "Operar solo CRYPTO",
                    "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                    "allowed_markets": ["crypto"],
                    "blocked_markets": ["stock", "options"],
                    "markets": {
                        "stock": {"alerts_allowed": False},
                        "crypto": {"alerts_allowed": True},
                    },
                },
            }
        )
    )

    status = realtime_health_status(path, now=now, max_age_minutes=15)

    assert status["label"] == "Premium bloqueado"
    assert status["alerts_allowed"] is True
    assert status["stock_alerts_allowed"] is False
    assert status["crypto_alerts_allowed"] is True
    assert status["active_route"] == "PARTIAL_MARKET_ROUTE"
    assert status["active_route_label"] == "Operar solo CRYPTO"
    assert status["active_route_detail"] == "Operable CRYPTO; bloqueado STOCK, OPTIONS."
    assert status["allowed_markets"] == ["crypto"]
    assert status["detail"].startswith("Operar solo CRYPTO")
    assert "alpaca_auth" in status["detail"]
    assert "Operar solo CRYPTO" in status["detail"]
    assert "POLYGON_API_KEY" in status["detail"]
    assert status["premium_recovery_action"] == "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN."
    assert status["provider_recovery"]["premium_blocked"] is True
    assert status["provider_recovery"]["polygon_missing_count"] == 1
    assert status["market_realtime"]["blocked_markets"] == ["stock", "options"]


def test_realtime_health_status_uses_provider_recovery_when_market_route_is_stale(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    path = tmp_path / "roxy_realtime_check.json"
    path.write_text(
        json.dumps(
            {
                "status": "WARN",
                "checks": [
                    {
                        "name": "alpaca_account_probe",
                        "status": "WARN",
                        "detail": "Alpaca account auth failed in paper mode.",
                    }
                ],
                "provider_recovery": {
                    "label": "Premium bloqueado",
                    "detail": "1/2 acciones caen a fallback por auth/permisos.",
                    "action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                    "premium_blocked": True,
                    "stock_alerts_allowed": False,
                    "impacted_markets": ["stock", "options"],
                },
                "market_realtime": {
                    "active_route": "ALL_MARKETS_ROUTE",
                    "active_route_label": "Operar mercados realtime",
                    "active_route_detail": "Operable STOCK, CRYPTO, OPTIONS.",
                    "allowed_markets": ["stock", "crypto", "options"],
                    "blocked_markets": [],
                },
            }
        )
    )

    status = realtime_health_status(path, now=now, max_age_minutes=15)

    assert status["label"] == "Premium bloqueado"
    assert status["stock_alerts_allowed"] is False
    assert status["crypto_alerts_allowed"] is True
    assert status["allowed_markets"] == ["crypto"]
    assert status["blocked_markets"] == ["stock", "options"]
    assert status["active_route"] == "PARTIAL_MARKET_ROUTE"
    assert status["active_route_label"] == "Operar solo CRYPTO"
    assert status["active_route_detail"] == "Operable CRYPTO; bloqueado STOCK, OPTIONS."
    assert status["detail"].startswith("Operar solo CRYPTO")


def test_realtime_health_status_treats_stability_slo_fail_as_historical_warning(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    path = tmp_path / "roxy_realtime_check.json"
    path.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "checks": [
                    {
                        "name": "health_stability_slo",
                        "status": "FAIL",
                        "detail": "OK rate 72.0% below 75.0%.",
                    }
                ],
            }
        )
    )

    status = realtime_health_status(path, now=now, max_age_minutes=15)

    assert status["status"] == "WARN"
    assert status["label"] == "Health historico"
    assert status["alerts_allowed"] is True
    assert status["stock_alerts_allowed"] is True
    assert status["crypto_alerts_allowed"] is True
    assert "health_stability_slo" in status["detail"]


def test_realtime_health_status_keeps_provider_recovery_on_slo_fail_with_premium_blocked(tmp_path):
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    path = tmp_path / "roxy_realtime_check.json"
    path.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "checks": [
                    {
                        "name": "health_stability_slo",
                        "status": "FAIL",
                        "detail": "OK rate 72.0% below 75.0%.",
                    }
                ],
                "provider_recovery": {
                    "label": "Premium bloqueado",
                    "detail": "1/4 acciones caen a fallback por auth/permisos.",
                    "action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                    "premium_blocked": True,
                    "stock_alerts_allowed": False,
                    "polygon_missing_count": 1,
                },
                "market_realtime": {
                    "blocked_markets": ["stock", "options"],
                    "markets": {
                        "stock": {"alerts_allowed": False},
                        "crypto": {"alerts_allowed": True},
                    },
                },
            }
        )
    )

    status = realtime_health_status(path, now=now, max_age_minutes=15)

    assert status["status"] == "WARN"
    assert status["label"] == "Premium bloqueado"
    assert status["alerts_allowed"] is True
    assert status["stock_alerts_allowed"] is False
    assert status["crypto_alerts_allowed"] is True
    assert "POLYGON_API_KEY" in status["detail"]
    assert status["premium_recovery_action"] == "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN."
    assert status["provider_recovery"]["premium_blocked"] is True
    assert status["market_realtime"]["markets"]["crypto"]["alerts_allowed"] is True


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


def test_write_brief_status_snapshot_uses_fresh_alert_quality_report(tmp_path, monkeypatch):
    import roxy_ai

    monkeypatch.setattr(roxy_ai, "BRIEF_TEXT_PATH", tmp_path / "brief.txt")
    monkeypatch.setattr(roxy_ai, "BRIEF_JSON_PATH", tmp_path / "brief.json")
    monkeypatch.setattr(roxy_ai, "STATUS_TEXT_PATH", tmp_path / "status.txt")
    monkeypatch.setattr(roxy_ai, "STATUS_JSON_PATH", tmp_path / "status.json")
    monkeypatch.setattr(roxy_ai, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(roxy_ai, "LEARNING_JOURNAL_PATH", tmp_path / "journal.csv")
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", tmp_path / "missing_alert_quality.json")
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "alert_count": 0,
        "watch_count": 1,
        "memory_symbols": 1,
        "realtime_health": {
            "label": "Premium bloqueado",
            "detail": "stocks/options bloqueados por proveedor premium",
            "alerts_allowed": True,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
            "market_realtime": {"blocked_markets": ["stock", "options"]},
        },
        "market_session": {
            "stock_session": "Abierto",
            "crypto_session": "24h",
            "stock_alerts_allowed": True,
        },
        "opportunities": [
            {
                "symbol": "WMT",
                "market": "stock",
                "ai_action": "WATCH",
                "alert_gate": "BLOCKED_REALTIME_DATA",
                "alert_quality": "C",
                "alert_readiness_score": 61.1,
                "alert_primary_blocker": "Datos realtime: Premium bloqueado",
                "alert_next_action": "Configurar proveedor premium.",
                "alert_blockers": ["Datos realtime: Premium bloqueado"],
            }
        ],
        "memory": {"symbols": {}, "strategy_stats": {}, "lessons": [], "alert_history": [], "signal_journal": []},
    }

    write_brief(brief)

    status = json.loads((tmp_path / "status.json").read_text())
    status_text = (tmp_path / "status.txt").read_text()
    assert (tmp_path / "alert_quality.json").exists()
    assert status["alert_quality_state"] == "BLOCKED_REALTIME"
    assert status["alert_quality_diagnostic_label"] == "Bloqueo parcial"
    assert status["alert_quality_blocker_category"] == "MARKET_PARTIAL_BLOCK"
    assert status["alert_quality_false_negative_risk"] == "MEDIUM"
    assert status["alert_quality_blocked_markets"] == ["stock", "options"]
    assert "Alert quality: Bloqueo parcial | MARKET_PARTIAL_BLOCK | risk MEDIUM" in status_text


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


def test_learning_journal_compacts_repeated_fingerprints_on_duplicate_append(tmp_path):
    brief = {
        "generated_at": "2026-06-14T00:15:00+00:00",
        "alert_count": 0,
        "watch_count": 2,
        "memory_symbols": 13,
        "opportunities": [
            {
                "symbol": "BNB/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "signal": "WATCH",
                "strategy_family": "Pullback",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_quality": "C",
                "alert_readiness_score": 68.4,
                "alert_next_action": "Esperar gatillo BUY en 15m.",
                "alert_blockers": ["15m da entrada: WAIT", "falta volumen"],
                "learning_bias": "learning",
            }
        ],
        "learning_profiles": [
            {
                "bias": "learning",
                "lesson": "Pullback: todavia no hay suficientes alertas cerradas para subir o bajar peso.",
                "recommendation": "Seguir observando y exigir confirmacion 1h + entrada 15m.",
            }
        ],
        "learning_plan": [{"strategy_family": "Pullback", "proposed_rule": "Exigir una vela BUY fresca."}],
        "experiment_registry": [{"status": "Shadow test"}],
    }
    path = tmp_path / "journal.csv"
    base_row = build_learning_journal_row(brief)
    base_row["fingerprint"] = roxy_ai._learning_journal_fingerprint(base_row)
    existing = []
    for minute in (0, 5, 10):
        row = dict(base_row)
        row["generated_at"] = f"2026-06-14T00:{minute:02d}:00+00:00"
        existing.append(row)
    pd.DataFrame(existing).to_csv(path, index=False)

    returned = append_learning_journal(brief, path=path, max_rows=10)

    journal = pd.read_csv(path)
    assert returned["fingerprint"] == base_row["fingerprint"]
    assert len(journal) == 2
    assert list(journal["generated_at"]) == [
        "2026-06-14T00:00:00+00:00",
        "2026-06-14T00:10:00+00:00",
    ]
    assert journal["fingerprint"].nunique() == 1


def test_status_snapshot_summarizes_top_setup(tmp_path, monkeypatch):
    import roxy_ai

    monkeypatch.setattr(roxy_ai, "STATUS_TEXT_PATH", tmp_path / "status.txt")
    monkeypatch.setattr(roxy_ai, "STATUS_JSON_PATH", tmp_path / "status.json")
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", tmp_path / "missing_alert_quality.json")
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
    assert status["system_status"] == "WARN"
    assert status["market_state"] == "WAITING"
    assert status["status"] == "WARN"
    assert status["state"] == "WAITING"
    assert status["safe_mode"] == "WAIT_FOR_CONFIRMATION"
    assert status["recommended_action"] == "Esperar volumen relativo >= 0.8x."
    assert status["blocked_markets"] == []
    assert written["learning_plan_count"] == 1
    assert "Esperar volumen" in (tmp_path / "status.txt").read_text()


def test_status_snapshot_includes_matching_alert_quality_action(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "summary": {
                    "state": "WAITING",
                    "diagnostic_label": "Esperando gatillo x50",
                    "diagnostic_severity": "WATCH",
                    "blocker_category": "MARKET_TRIGGER_WAIT",
                    "false_negative_risk": "MEDIUM",
                    "avg_readiness": 57.6,
                    "latest_readiness": 61.5,
                    "readiness_delta": 4.2,
                    "readiness_trend": 4.2,
                    "silence_mode": "MISSED_TRIGGER_WATCH",
                    "silence_reason": "Esperando gatillo 15m",
                    "missed_opportunity_watch": True,
                    "missed_opportunity_risk": "MEDIUM",
                    "missed_opportunity_reason": "Setup listo, pero gatillo 15m lleva 50 ciclos pendiente",
                    "missed_opportunity_action": "Revisar manualmente candidatos rotados en 15m/1h",
                    "missed_trigger_plan": {
                        "active": True,
                        "primary_symbol": "WMT",
                        "primary_readiness": 61.5,
                        "risk": "MEDIUM",
                        "review_due": True,
                        "review_status": "OVERDUE",
                        "review_overdue_cycles": 2,
                        "review_cycles_remaining": 0,
                        "review_progress": 1.042,
                        "review_cycle_minutes": 1.4,
                        "review_eta_minutes": 0.0,
                        "review_overdue_minutes": 2.8,
                        "review_pressure": "OVERDUE",
                        "stale_candidate": False,
                        "auto_review_decision": "REVALIDATE_NOW",
                        "decision_reason": "Review overdue while the setup remains close to trigger.",
                        "decision_action": "Revalidar ahora 15m/1h.",
                        "readiness_delta": 0.0,
                        "rotation_guard_active": False,
                        "rotation_alternates": [],
                        "rotation_cooldown_cycles": 0,
                        "rotation_resume_condition": "",
                        "severity": "ATTENTION",
                        "max_watch_cycles": 48,
                        "review_action": "Revalidar manualmente el setup en 15m/1h.",
                        "exit_condition": "No alertar hasta que 15m confirme entrada.",
                    },
                    "recommended_action": "Rotar foco: WMT 61.5% C, PEP 53.8% C; no alertar hasta que 15m confirme entrada",
                    "rotation_candidates": ["WMT 61.5% C", "PEP 53.8% C"],
                    "waiting_streak": 50,
                    "dominant_blocker": {"name": "15m da entrada: WAIT", "count": 50},
                    "persistent_blocker": "15m da entrada: WAIT",
                    "persistent_blocker_minutes": 69.9,
                },
            }
        )
    )
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "opportunities": [
            {
                "symbol": "WMT",
                "market": "stock",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_quality": "C",
                "alert_readiness_score": 61.5,
                "alert_next_action": "Esperar gatillo BUY en 15m.",
                "alert_blockers": ["15m da entrada: WAIT"],
            }
        ],
    }

    status = build_status_snapshot(brief)

    assert status["alert_quality_state"] == "WAITING"
    assert status["alert_quality_diagnostic_label"] == "Esperando gatillo x50"
    assert status["alert_quality_diagnostic_severity"] == "WATCH"
    assert status["alert_quality_blocker_category"] == "MARKET_TRIGGER_WAIT"
    assert status["alert_quality_false_negative_risk"] == "MEDIUM"
    assert status["alert_quality_avg_readiness"] == 57.6
    assert status["alert_quality_latest_readiness"] == 61.5
    assert status["alert_quality_readiness_delta"] == 4.2
    assert status["alert_quality_readiness_trend"] == 4.2
    assert status["alert_quality_silence_mode"] == "MISSED_TRIGGER_WATCH"
    assert status["alert_quality_silence_reason"] == "Esperando gatillo 15m"
    assert status["alert_quality_missed_opportunity_watch"] is True
    assert status["alert_quality_missed_opportunity_risk"] == "MEDIUM"
    assert "50 ciclos" in status["alert_quality_missed_opportunity_reason"]
    assert "Revisar manualmente" in status["alert_quality_missed_opportunity_action"]
    assert status["alert_quality_missed_trigger_plan_active"] is True
    assert status["alert_quality_missed_trigger_plan_symbol"] == "WMT"
    assert status["alert_quality_missed_trigger_plan_readiness"] == 61.5
    assert status["alert_quality_missed_trigger_plan_risk"] == "MEDIUM"
    assert status["alert_quality_missed_trigger_plan_review_due"] is True
    assert status["alert_quality_missed_trigger_plan_review_status"] == "OVERDUE"
    assert status["alert_quality_missed_trigger_plan_review_overdue_cycles"] == 2
    assert status["alert_quality_missed_trigger_plan_review_cycles_remaining"] == 0
    assert status["alert_quality_missed_trigger_plan_review_progress"] == 1.042
    assert status["alert_quality_missed_trigger_plan_review_cycle_minutes"] == 1.4
    assert status["alert_quality_missed_trigger_plan_review_eta_minutes"] == 0.0
    assert status["alert_quality_missed_trigger_plan_review_overdue_minutes"] == 2.8
    assert status["alert_quality_missed_trigger_plan_review_pressure"] == "OVERDUE"
    assert status["alert_quality_missed_trigger_plan_stale_candidate"] is False
    assert status["alert_quality_missed_trigger_plan_auto_review_decision"] == "REVALIDATE_NOW"
    assert status["alert_quality_missed_trigger_plan_decision_reason"] == (
        "Review overdue while the setup remains close to trigger."
    )
    assert status["alert_quality_missed_trigger_plan_decision_action"] == "Revalidar ahora 15m/1h."
    assert status["alert_quality_missed_trigger_plan_readiness_delta"] == 0.0
    assert status["alert_quality_missed_trigger_plan_rotation_guard_active"] is False
    assert status["alert_quality_missed_trigger_plan_rotation_alternates"] == []
    assert status["alert_quality_missed_trigger_plan_rotation_cooldown_cycles"] == 0
    assert status["alert_quality_missed_trigger_plan_severity"] == "ATTENTION"
    assert status["alert_quality_missed_trigger_plan_max_watch_cycles"] == 48
    assert status["alert_quality_missed_trigger_plan_review_action"] == "Revalidar manualmente el setup en 15m/1h."
    assert "15m confirme" in status["alert_quality_missed_trigger_plan_exit"]
    assert status["alert_quality_waiting_streak"] == 50
    assert status["alert_quality_recurrent_blocker"] == "15m da entrada: WAIT"
    assert status["alert_quality_recurrent_blocker_count"] == 50
    assert status["alert_quality_persistent_blocker"] == "15m da entrada: WAIT"
    assert status["alert_quality_persistent_blocker_minutes"] == 69.9
    assert status["alert_quality_rotation_candidates"] == ["WMT 61.5% C", "PEP 53.8% C"]
    assert status["alert_quality_recommended_action"].startswith("Rotar foco: WMT")
    assert status["system_status"] == "WARN"
    assert status["market_state"] == "WAITING"
    assert status["safe_mode"] == "WAIT_FOR_CONFIRMATION"
    assert status["contract_version"] == 2
    assert status["label"] == "Esperando gatillo x50"
    assert status["tone"] == "watch"
    assert status["recommended_action"].startswith("Rotar foco: WMT")


def test_status_snapshot_uses_recurrent_blocker_when_persistent_name_missing(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "summary": {
                    "state": "WAITING",
                    "diagnostic_label": "Esperando gatillo x47",
                    "dominant_blocker": {"name": "15m da entrada: WAIT", "count": 47},
                    "persistent_blocker_minutes": 0.3,
                },
            }
        )
    )

    status = build_status_snapshot(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "opportunities": [{"symbol": "BTC/USD", "alert_gate": "WAIT_15M_ENTRY"}],
        }
    )

    assert status["alert_quality_recurrent_blocker"] == "15m da entrada: WAIT"
    assert status["alert_quality_recurrent_blocker_count"] == 47
    assert status["alert_quality_persistent_blocker"] == "15m da entrada: WAIT"
    assert status["alert_quality_persistent_blocker_minutes"] == 0.3


def test_status_snapshot_promotes_stale_single_discard_guard():
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "opportunities": [
            {
                "symbol": "PEPE/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_quality": "C",
                "alert_readiness_score": 73.7,
                "alert_next_action": "Esperar gatillo BUY en 15m.",
                "alert_blockers": ["15m da entrada: WAIT"],
            }
        ],
    }
    alert_quality_report = {
        "brief_generated_at": "2026-06-10T12:00:00+00:00",
        "state": "WAITING",
        "diagnostic_label": "Esperando gatillo x50",
        "diagnostic_severity": "WATCH",
        "blocker_category": "MARKET_TRIGGER_WAIT",
        "false_negative_risk": "MEDIUM",
        "recommended_action": "Pausar foco: PEPE/USD 73.7% C; esperar nuevo candidato o confirmacion 15m",
        "missed_trigger_plan_active": True,
        "missed_trigger_plan_symbol": "PEPE/USD",
        "missed_trigger_plan_readiness": 73.7,
        "missed_trigger_plan_risk": "MEDIUM",
        "missed_trigger_plan_review_due": True,
        "missed_trigger_plan_review_status": "OVERDUE",
        "missed_trigger_plan_review_pressure": "STALE_SINGLE",
        "missed_trigger_plan_stale_candidate": True,
        "missed_trigger_plan_auto_review_decision": "DISCARD_STALE_SINGLE",
        "missed_trigger_plan_decision_reason": (
            "Review overdue on the only visible candidate; no alternate rotation candidate is available."
        ),
        "missed_trigger_plan_decision_action": (
            "Pausar o descartar el candidato unico; esperar nuevo candidato o confirmacion 15m antes de reactivarlo."
        ),
        "missed_trigger_plan_readiness_delta": 7.9,
        "missed_trigger_plan_rotation_guard_active": False,
        "missed_trigger_plan_rotation_alternates": [],
        "missed_trigger_plan_rotation_cooldown_cycles": 0,
        "missed_trigger_plan_rotation_cooldown_eta_minutes": None,
        "missed_trigger_plan_discard_guard_active": True,
        "missed_trigger_plan_discard_symbol": "PEPE/USD",
        "missed_trigger_plan_discard_reason": (
            "Review overdue on the only visible candidate; no alternate rotation candidate is available."
        ),
        "missed_trigger_plan_discard_cooldown_cycles": 12,
        "missed_trigger_plan_discard_cooldown_eta_minutes": 15.6,
        "missed_trigger_plan_discard_resume_condition": (
            "Rehabilitar el candidato unico solo si 15m confirma entrada o aparece un alterno operable."
        ),
        "summary": {
            "state": "WAITING",
            "diagnostic_label": "Esperando gatillo x50",
            "recommended_action": "accion vieja",
        },
    }

    status = build_status_snapshot(brief, alert_quality_report=alert_quality_report)

    assert status["recommended_action"] == (
        "Pausar foco: PEPE/USD 73.7% C; esperar nuevo candidato o confirmacion 15m"
    )
    assert status["alert_quality_missed_trigger_plan_auto_review_decision"] == "DISCARD_STALE_SINGLE"
    assert status["alert_quality_missed_trigger_plan_review_pressure"] == "STALE_SINGLE"
    assert status["alert_quality_missed_trigger_plan_stale_candidate"] is True
    assert status["alert_quality_missed_trigger_plan_decision_action"].startswith("Pausar o descartar")
    assert status["alert_quality_missed_trigger_plan_rotation_guard_active"] is False
    assert status["alert_quality_missed_trigger_plan_rotation_alternates"] == []
    assert status["alert_quality_missed_trigger_plan_rotation_cooldown_cycles"] == 0
    assert status["alert_quality_missed_trigger_plan_rotation_cooldown_eta_minutes"] is None
    assert status["alert_quality_missed_trigger_plan_discard_guard_active"] is True
    assert status["alert_quality_missed_trigger_plan_discard_symbol"] == "PEPE/USD"
    assert status["alert_quality_missed_trigger_plan_discard_cooldown_cycles"] == 12
    assert status["alert_quality_missed_trigger_plan_discard_cooldown_eta_minutes"] == 15.6
    assert "alterno operable" in status["alert_quality_missed_trigger_plan_discard_resume_condition"]
    assert status["operational_focus_symbol"] == "PEPE/USD"
    assert status["operational_focus_source"] == "ALERT_QUALITY_DISCARD"
    assert status["operational_focus_reason"].startswith("Pausar o descartar")
    assert status["alert_quality_discard_handoff_status"] == "CONFIRMED"
    assert status["alert_quality_discard_handoff_expected_symbol"] == "PEPE/USD"
    assert status["alert_quality_discard_handoff_focus_symbol"] == "PEPE/USD"
    assert status["alert_quality_discard_handoff_source"] == "ALERT_QUALITY_DISCARD"
    assert status["alert_quality_rotation_handoff_status"] == "NOT_REQUESTED"
    assert status["alert_quality_rotation_handoff_expected_symbol"] == ""
    assert status["alert_quality_rotation_handoff_focus_symbol"] == ""
    assert status["alert_quality_rotation_handoff_source"] == ""
    assert status["alert_quality_confirmation_rotation_handoff_status"] == "NOT_REQUESTED"
    assert status["alert_quality_confirmation_rotation_handoff_expected_symbol"] == ""
    assert status["alert_quality_confirmation_rotation_handoff_focus_symbol"] == ""
    assert status["alert_quality_confirmation_rotation_handoff_source"] == ""


def test_status_snapshot_promotes_rotation_next_symbol():
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_quality": "B",
                "alert_readiness_score": 89.5,
                "alert_next_action": "Esperar gatillo BUY en 15m.",
                "alert_blockers": ["15m da entrada: WAIT"],
            }
        ],
    }
    alert_quality_report = {
        "brief_generated_at": "2026-06-10T12:00:00+00:00",
        "state": "WAITING",
        "diagnostic_label": "Esperando gatillo x72",
        "diagnostic_severity": "ATTENTION",
        "blocker_category": "MARKET_TRIGGER_WAIT",
        "false_negative_risk": "HIGH",
        "recommended_action": (
            "Escalar rotacion: revalidar 15m/1h ahora; si no confirma en la proxima revision, "
            "rotar foco a BTC/USD."
        ),
        "missed_trigger_plan_active": True,
        "missed_trigger_plan_symbol": "ETH/USD",
        "missed_trigger_plan_readiness": 89.5,
        "missed_trigger_plan_risk": "HIGH",
        "missed_trigger_plan_review_due": True,
        "missed_trigger_plan_review_status": "OVERDUE",
        "missed_trigger_plan_review_pressure": "OVERDUE_ESCALATED",
        "missed_trigger_plan_auto_review_decision": "ESCALATE_ROTATION",
        "missed_trigger_plan_decision_action": (
            "Escalar rotacion: revalidar 15m/1h ahora; si no confirma en la proxima revision, "
            "rotar foco a BTC/USD."
        ),
        "missed_trigger_plan_rotation_guard_active": True,
        "missed_trigger_plan_rotation_blocked_symbol": "ETH/USD",
        "missed_trigger_plan_rotation_alternates": ["BTC/USD 78.9% B", "SOL/USD 78.9% B"],
        "missed_trigger_plan_rotation_next_symbol": "BTC/USD",
        "missed_trigger_plan_rotation_cooldown_cycles": 12,
    }

    status = build_status_snapshot(brief, alert_quality_report=alert_quality_report)

    assert status["alert_quality_missed_trigger_plan_auto_review_decision"] == "ESCALATE_ROTATION"
    assert status["alert_quality_missed_trigger_plan_rotation_guard_active"] is True
    assert status["alert_quality_missed_trigger_plan_rotation_blocked_symbol"] == "ETH/USD"
    assert status["alert_quality_missed_trigger_plan_rotation_alternates"] == [
        "BTC/USD 78.9% B",
        "SOL/USD 78.9% B",
    ]
    assert status["alert_quality_missed_trigger_plan_rotation_next_symbol"] == "BTC/USD"
    assert "BTC/USD" in status["recommended_action"]
    assert status["top_symbol"] == "ETH/USD"
    assert status["operational_focus_symbol"] == "BTC/USD"
    assert status["operational_focus_source"] == "ALERT_QUALITY_ROTATION"
    assert status["operational_focus_overrides_top"] is True
    assert "ETH/USD vencido" in status["operational_focus_reason"]
    assert status["alert_quality_rotation_handoff_status"] == "CONFIRMED"
    assert status["alert_quality_rotation_handoff_expected_symbol"] == "BTC/USD"
    assert status["alert_quality_rotation_handoff_focus_symbol"] == "BTC/USD"
    assert status["alert_quality_rotation_handoff_source"] == "ALERT_QUALITY_ROTATION"
    assert status["alert_quality_discard_handoff_status"] == "NOT_REQUESTED"
    assert status["alert_quality_discard_handoff_expected_symbol"] == ""
    assert status["alert_quality_discard_handoff_focus_symbol"] == ""
    assert status["alert_quality_discard_handoff_source"] == ""
    assert status["alert_quality_confirmation_rotation_handoff_status"] == "NOT_REQUESTED"
    assert status["alert_quality_confirmation_rotation_handoff_expected_symbol"] == ""
    assert status["alert_quality_confirmation_rotation_handoff_focus_symbol"] == ""
    assert status["alert_quality_confirmation_rotation_handoff_source"] == ""


def test_status_snapshot_prefers_confirmed_rotation_handoff_action():
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_quality": "B",
                "alert_readiness_score": 89.5,
                "alert_next_action": "Esperar gatillo BUY en 15m.",
                "alert_blockers": ["15m da entrada: WAIT"],
            }
        ],
    }
    confirmed_action = (
        "Rotacion confirmada: mantener foco operativo en BTC/USD; mantener ETH/USD bloqueado "
        "hasta que 15m confirme entrada o cambie la readiness."
    )
    alert_quality_report = {
        "brief_generated_at": "2026-06-10T12:00:00+00:00",
        "state": "WAITING",
        "diagnostic_label": "Esperando gatillo x72",
        "diagnostic_severity": "ATTENTION",
        "blocker_category": "MARKET_TRIGGER_WAIT",
        "recommended_action": confirmed_action,
        "missed_trigger_plan_active": True,
        "missed_trigger_plan_symbol": "ETH/USD",
        "missed_trigger_plan_rotation_guard_active": True,
        "missed_trigger_plan_rotation_blocked_symbol": "ETH/USD",
        "missed_trigger_plan_rotation_next_symbol": "BTC/USD",
        "missed_trigger_plan_rotation_handoff_confirmed": True,
        "missed_trigger_plan_handoff_confirmed_action": confirmed_action,
    }

    status = build_status_snapshot(brief, alert_quality_report=alert_quality_report)

    assert status["operational_focus_symbol"] == "BTC/USD"
    assert status["operational_focus_source"] == "ALERT_QUALITY_ROTATION"
    assert status["operational_focus_reason"] == confirmed_action
    assert status["recommended_action"] == confirmed_action
    assert status["alert_quality_missed_trigger_plan_handoff_confirmed_action"] == confirmed_action
    assert status["alert_quality_rotation_handoff_status"] == "CONFIRMED"


def test_status_snapshot_marks_daily_plan_focus_alignment():
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_quality": "C",
                "alert_readiness_score": 73.7,
                "alert_next_action": "Esperar gatillo BUY en 15m.",
            }
        ],
        "daily_opportunity_plan": {
            "mode": "DAILY_OPPORTUNITY_PLAN_24H",
            "operar_ahora": 0,
            "proxima_entrada": 1,
            "vigilar": 0,
            "top_symbol": "LINK/USD",
            "top_stage": "PROXIMA_ENTRADA",
            "top_probability": 74,
        },
    }
    alert_quality_report = {
        "brief_generated_at": "2026-06-10T12:00:00+00:00",
        "state": "WAITING",
        "diagnostic_label": "Esperando gatillo x72",
        "diagnostic_severity": "ATTENTION",
        "blocker_category": "MARKET_TRIGGER_WAIT",
        "false_negative_risk": "MEDIUM",
        "recommended_action": "Escalar rotacion a LINK/USD.",
        "missed_trigger_plan_active": True,
        "missed_trigger_plan_symbol": "ETH/USD",
        "missed_trigger_plan_review_due": True,
        "missed_trigger_plan_review_status": "OVERDUE",
        "missed_trigger_plan_review_pressure": "STALE_OVERDUE_ESCALATED",
        "missed_trigger_plan_auto_review_decision": "ESCALATE_ROTATION",
        "missed_trigger_plan_rotation_guard_active": True,
        "missed_trigger_plan_rotation_blocked_symbol": "ETH/USD",
        "missed_trigger_plan_rotation_next_symbol": "LINK/USD",
    }

    status = build_status_snapshot(brief, alert_quality_report=alert_quality_report)

    assert status["top_symbol"] == "ETH/USD"
    assert status["operational_focus_symbol"] == "LINK/USD"
    assert status["daily_plan_top_symbol"] == "LINK/USD"
    assert status["daily_plan_matches_top"] is False
    assert status["daily_plan_matches_focus"] is True
    assert status["daily_plan_alignment"] == "FOCUS_ALIGNED"


def test_status_snapshot_marks_daily_plan_focus_supported_when_rotation_is_listed():
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_HTF_CONFIRM",
                "alert_quality": "B",
                "alert_readiness_score": 89.5,
                "alert_next_action": "Esperar confirmacion 2h/4h.",
            },
            {
                "symbol": "SOL/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_HTF_CONFIRM",
                "alert_quality": "C",
                "alert_readiness_score": 73.7,
                "alert_next_action": "Alterno de rotacion.",
            },
        ],
        "daily_opportunity_plan": {
            "mode": "DAILY_OPPORTUNITY_PLAN_24H",
            "operar_ahora": 0,
            "proxima_entrada": 2,
            "vigilar": 0,
            "top_symbol": "ETH/USD",
            "top_stage": "PROXIMA_ENTRADA",
            "top_probability": 81,
            "rows": [
                {"symbol": "ETH/USD", "stage": "PROXIMA_ENTRADA", "probability": 81},
                {"symbol": "SOL/USD", "stage": "PROXIMA_ENTRADA", "probability": 73},
            ],
        },
    }
    alert_quality_report = {
        "brief_generated_at": "2026-06-10T12:00:00+00:00",
        "state": "WAITING",
        "diagnostic_label": "Esperando confirmacion",
        "diagnostic_severity": "ATTENTION",
        "blocker_category": "MARKET_CONFIRMATION_WAIT",
        "recommended_action": "Escalar rotacion a SOL/USD.",
        "confirmation_wait_plan_active": True,
        "confirmation_wait_plan_symbol": "ETH/USD",
        "confirmation_wait_plan_review_due": True,
        "confirmation_wait_plan_review_status": "OVERDUE",
        "confirmation_wait_plan_review_pressure": "OVERDUE_ESCALATED",
        "confirmation_wait_plan_rotation_guard_active": True,
        "confirmation_wait_plan_rotation_blocked_symbol": "ETH/USD",
        "confirmation_wait_plan_rotation_next_symbol": "SOL/USD",
    }

    status = build_status_snapshot(brief, alert_quality_report=alert_quality_report)

    assert status["top_symbol"] == "ETH/USD"
    assert status["operational_focus_symbol"] == "SOL/USD"
    assert status["daily_plan_top_symbol"] == "ETH/USD"
    assert status["daily_plan_focus_symbol"] == "SOL/USD"
    assert status["daily_plan_focus_stage"] == "PROXIMA_ENTRADA"
    assert status["daily_plan_supports_focus"] is True
    assert status["daily_plan_matches_top"] is True
    assert status["daily_plan_matches_focus"] is True
    assert status["daily_plan_alignment"] == "FOCUS_SUPPORTED"


def test_status_snapshot_includes_confirmation_wait_plan(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "summary": {
                    "status": "WARN",
                    "status_reason": "Alert quality requires manual review or attention.",
                    "state": "WAITING",
                    "diagnostic_label": "Esperando confirmacion x50",
                    "diagnostic_severity": "ATTENTION",
                    "blocker_category": "MARKET_CONFIRMATION_WAIT",
                    "false_negative_risk": "LOW",
                    "silence_mode": "HEALTHY_WAIT",
                    "silence_reason": "2h/4h aun no validan el gatillo",
                    "confirmation_wait_plan": {
                        "active": True,
                        "primary_symbol": "ETH/USD",
                        "primary_readiness": 89.5,
                        "risk": "LOW",
                        "review_due": True,
                        "review_status": "OVERDUE",
                        "review_overdue_cycles": 2,
                        "review_cycles_remaining": 0,
                        "review_progress": 1.042,
                        "review_cycle_minutes": 1.0,
                        "review_eta_minutes": 0.0,
                        "review_overdue_minutes": 2.0,
                        "severity": "ATTENTION",
                        "max_watch_cycles": 48,
                        "review_action": "Revalidar manualmente 2h/4h antes de alertar.",
                        "exit_condition": "No alertar hasta que 2h/4h confirme.",
                    },
                    "recommended_action": "Esperar confirmacion de volumen/target antes de alertar",
                    "waiting_streak": 50,
                    "persistent_blocker_minutes": 2.7,
                },
            }
        )
    )
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_HTF_CONFIRM",
                "alert_quality": "B",
                "alert_readiness_score": 89.5,
                "alert_next_action": "Esperar que 2h/4h confirmen o dejen de bloquear el gatillo.",
                "alert_blockers": ["2h/4h validan: 2h/4h contradicen el gatillo"],
            }
        ],
    }

    status = build_status_snapshot(brief)

    assert status["alert_quality_blocker_category"] == "MARKET_CONFIRMATION_WAIT"
    assert status["alert_quality_report_status"] == "WARN"
    assert status["alert_quality_status_reason"] == "Alert quality requires manual review or attention."
    assert status["alert_quality_confirmation_wait_plan_active"] is True
    assert status["alert_quality_confirmation_wait_plan_symbol"] == "ETH/USD"
    assert status["alert_quality_confirmation_wait_plan_readiness"] == 89.5
    assert status["alert_quality_confirmation_wait_plan_risk"] == "LOW"
    assert status["alert_quality_confirmation_wait_plan_review_due"] is True
    assert status["alert_quality_confirmation_wait_plan_review_status"] == "OVERDUE"
    assert status["alert_quality_confirmation_wait_plan_review_pressure"] == "OVERDUE"
    assert status["alert_quality_confirmation_wait_plan_review_overdue_cycles"] == 2
    assert status["alert_quality_confirmation_wait_plan_review_cycles_remaining"] == 0
    assert status["alert_quality_confirmation_wait_plan_review_progress"] == 1.042
    assert status["alert_quality_confirmation_wait_plan_review_cycle_minutes"] == 1.0
    assert status["alert_quality_confirmation_wait_plan_review_eta_minutes"] == 0.0
    assert status["alert_quality_confirmation_wait_plan_review_overdue_minutes"] == 2.0
    assert status["alert_quality_confirmation_wait_plan_severity"] == "ATTENTION"
    assert status["alert_quality_confirmation_wait_plan_max_watch_cycles"] == 48
    assert status["alert_quality_confirmation_wait_plan_review_action"] == (
        "Revalidar manualmente 2h/4h antes de alertar."
    )
    assert "2h/4h confirme" in status["alert_quality_confirmation_wait_plan_exit"]
    assert status["system_status"] == "WARN"
    assert status["market_state"] == "WAITING"
    assert status["safe_mode"] == "WAIT_FOR_CONFIRMATION"


def test_status_snapshot_promotes_confirmation_wait_rotation(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "summary": {
                    "state": "WAITING",
                    "diagnostic_label": "Esperando confirmacion x72",
                    "diagnostic_severity": "ATTENTION",
                    "blocker_category": "MARKET_CONFIRMATION_WAIT",
                    "false_negative_risk": "LOW",
                    "silence_mode": "HEALTHY_WAIT",
                    "confirmation_wait_plan": {
                        "active": True,
                        "primary_symbol": "ETH/USD",
                        "primary_readiness": 83.0,
                        "risk": "LOW",
                        "review_due": True,
                        "review_status": "OVERDUE",
                        "review_pressure": "OVERDUE_ESCALATED",
                        "review_overdue_cycles": 24,
                        "review_cycles_remaining": 0,
                        "rotation_guard_active": True,
                        "rotation_blocked_symbol": "ETH/USD",
                        "rotation_alternates": ["BTC/USD 77.5% B"],
                        "rotation_next_symbol": "BTC/USD",
                        "rotation_cooldown_cycles": 12,
                        "rotation_resume_condition": (
                            "Rehabilitar el simbolo solo si 2h/4h, volumen/target y grafica realtime confirman."
                        ),
                        "decision_action": (
                            "Escalar rotacion de confirmacion: revalidar 2h/4h, volumen y target ahora; "
                            "si no mejora, rotar foco a BTC/USD."
                        ),
                        "severity": "ATTENTION",
                        "max_watch_cycles": 48,
                    },
                    "recommended_action": "Escalar rotacion de confirmacion: rotar foco a BTC/USD.",
                },
            }
        )
    )
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_HTF_CONFIRM",
                "alert_quality": "B",
                "alert_readiness_score": 83.0,
                "alert_next_action": "Esperar que 2h/4h confirmen.",
                "alert_blockers": ["2h/4h validan: contradicen"],
            }
        ],
    }

    status = build_status_snapshot(brief)

    assert status["alert_quality_confirmation_wait_plan_review_pressure"] == "OVERDUE_ESCALATED"
    assert status["alert_quality_confirmation_wait_plan_rotation_guard_active"] is True
    assert status["alert_quality_confirmation_wait_plan_rotation_blocked_symbol"] == "ETH/USD"
    assert status["alert_quality_confirmation_wait_plan_rotation_alternates"] == ["BTC/USD 77.5% B"]
    assert status["alert_quality_confirmation_wait_plan_rotation_next_symbol"] == "BTC/USD"
    assert status["alert_quality_confirmation_wait_plan_rotation_cooldown_cycles"] == 12
    assert status["operational_focus_symbol"] == "BTC/USD"
    assert status["operational_focus_source"] == "ALERT_QUALITY_CONFIRMATION_ROTATION"
    assert status["operational_focus_overrides_top"] is True
    assert "rotar foco a BTC/USD" in status["operational_focus_reason"]
    assert status["alert_quality_confirmation_rotation_handoff_status"] == "CONFIRMED"
    assert status["alert_quality_confirmation_rotation_handoff_expected_symbol"] == "BTC/USD"
    assert status["alert_quality_confirmation_rotation_handoff_focus_symbol"] == "BTC/USD"
    assert status["alert_quality_confirmation_rotation_handoff_source"] == (
        "ALERT_QUALITY_CONFIRMATION_ROTATION"
    )
    assert status["alert_quality_rotation_handoff_status"] == "NOT_REQUESTED"
    assert status["alert_quality_rotation_handoff_expected_symbol"] == ""
    assert status["alert_quality_rotation_handoff_focus_symbol"] == ""
    assert status["alert_quality_rotation_handoff_source"] == ""
    assert status["alert_quality_discard_handoff_status"] == "NOT_REQUESTED"
    assert status["alert_quality_discard_handoff_expected_symbol"] == ""
    assert status["alert_quality_discard_handoff_focus_symbol"] == ""
    assert status["alert_quality_discard_handoff_source"] == ""


def test_status_snapshot_uses_market_coverage_action_when_rotation_action_missing(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "state": "WAITING",
                "blocker_category": "UNCLASSIFIED_WAIT",
                "false_negative_risk": "MEDIUM",
                "blocked_markets": ["stock", "options"],
                "allowed_markets": ["crypto"],
                "rotation_candidates": ["ETH/USD 73.7% C"],
                "market_coverage_action": "Priorizar candidatos cripto mientras stock/opciones recuperan proveedor premium.",
            }
        )
    )

    status = build_status_snapshot(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "realtime_health": {
                "active_route": "PARTIAL_MARKET_ROUTE",
                "active_route_label": "Operar solo CRYPTO",
                "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                "allowed_markets": ["crypto"],
            },
            "opportunities": [
                {
                    "symbol": "ETH/USD",
                    "market": "crypto",
                    "ai_action": "WATCH",
                    "alert_gate": "WAIT_FULL_CHECKLIST",
                    "alert_quality": "C",
                    "alert_readiness_score": 73.7,
                    "alert_next_action": "Esperar checklist completo.",
                    "alert_blockers": ["1h confirma: Score tendencia 54"],
                }
            ],
        }
    )

    assert status["alert_quality_rotation_candidates"] == ["ETH/USD 73.7% C"]
    assert status["alert_quality_recommended_action"] == (
        "Priorizar candidatos cripto mientras stock/opciones recuperan proveedor premium."
    )
    assert status["alert_quality_market_coverage_action"] == (
        "Priorizar candidatos cripto mientras stock/opciones recuperan proveedor premium."
    )
    assert status["recommended_action"] == (
        "Priorizar candidatos cripto mientras stock/opciones recuperan proveedor premium."
    )
    assert status["safe_mode"] == "NO_STOCK_OR_OPTIONS_ALERTS"


def test_status_snapshot_downgrades_buy_tone_for_waiting_alert_quality(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "state": "WAITING",
                "label": "Esperando confirmacion",
                "tone": "buy",
                "diagnostic_label": "Esperando confirmacion",
                "diagnostic_severity": "OK",
                "blocker_category": "MARKET_CONFIRMATION_WAIT",
                "false_negative_risk": "LOW",
                "blocked_markets": ["stock", "options"],
                "allowed_markets": ["crypto"],
            }
        )
    )

    status = build_status_snapshot(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "realtime_health": {
                "active_route": "PARTIAL_MARKET_ROUTE",
                "active_route_label": "Operar solo CRYPTO",
                "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                "allowed_markets": ["crypto"],
            },
            "opportunities": [
                {
                    "symbol": "ETH/USD",
                    "market": "crypto",
                    "ai_action": "WATCH",
                    "alert_gate": "WAIT_FULL_CHECKLIST",
                    "alert_readiness_score": 68.4,
                    "alert_quality": "C",
                    "alert_next_action": "Esperar checklist completo.",
                }
            ],
        }
    )

    assert status["state"] == "WAITING"
    assert status["label"] == "Esperando confirmacion"
    assert status["tone"] == "watch"


def test_status_snapshot_prefers_alert_quality_top_level_contract(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "status": "WARN",
                "status_reason": "Alert quality requires manual review or attention.",
                "state": "BLOCKED_REALTIME",
                "diagnostic_label": "Bloqueo parcial",
                "diagnostic_severity": "ATTENTION",
                "blocker_category": "MARKET_PARTIAL_BLOCK",
                "false_negative_risk": "MEDIUM",
                "silence_mode": "MARKET_PARTIAL_BLOCK",
                "silence_reason": "stock, options bloqueado por proveedor premium; cripto sigue permitido",
                "blocked_markets": ["stock", "options"],
                "blocked_route_markets": ["stock", "options"],
                "blocked_route_market_count": 2,
                "blocked_opportunity_market_count": 1,
                "stock_alerts_allowed": False,
                "crypto_alerts_allowed": True,
                "options_alerts_allowed": False,
                "session_stock_alerts_allowed": True,
                "recommended_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                "chart_contract_label": "Graficas parciales",
                "chart_contract_action": "Priorizar oportunidades con LIVE_DATA_OK.",
                "chart_contract_operable_count": 1,
                "chart_contract_blocked_count": 2,
                "chart_contract_missing_count": 2,
                "chart_contract_blocked_symbols": ["WMT: CHART_CONTRACT_MISSING", "PEP: CHART_CONTRACT_MISSING"],
                "summary": {
                    "state": "WAITING",
                    "diagnostic_label": "Stale summary",
                    "recommended_action": "Accion vieja",
                },
            }
        )
    )

    status = build_status_snapshot(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "realtime_health": {
                "label": "Premium bloqueado",
                "detail": "Operar solo CRYPTO: Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                "active_route": "PARTIAL_MARKET_ROUTE",
                "active_route_label": "Operar solo CRYPTO",
                "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                "allowed_markets": ["crypto"],
            },
            "opportunities": [
                {
                    "symbol": "WMT",
                    "market": "stock",
                    "ai_action": "WATCH",
                    "alert_gate": "BLOCKED_REALTIME_DATA",
                    "alert_quality": "C",
                    "alert_readiness_score": 61.1,
                    "alert_next_action": "Configurar proveedor premium.",
                    "alert_blockers": ["Datos realtime: Premium bloqueado"],
                }
            ],
        }
    )

    assert status["alert_quality_state"] == "BLOCKED_REALTIME"
    assert status["alert_quality_diagnostic_label"] == "Bloqueo parcial"
    assert status["alert_quality_report_status"] == "WARN"
    assert status["alert_quality_status_reason"] == "Alert quality requires manual review or attention."
    assert status["alert_quality_blocker_category"] == "MARKET_PARTIAL_BLOCK"
    assert status["alert_quality_false_negative_risk"] == "MEDIUM"
    assert status["alert_quality_silence_mode"] == "MARKET_PARTIAL_BLOCK"
    assert status["alert_quality_blocked_markets"] == ["stock", "options"]
    assert status["alert_quality_blocked_route_markets"] == ["stock", "options"]
    assert status["alert_quality_blocked_route_market_count"] == 2
    assert status["alert_quality_blocked_opportunity_market_count"] == 1
    assert status["alert_quality_recommended_action"] == "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN."
    assert status["alert_quality_chart_contract_label"] == "Graficas parciales"
    assert status["alert_quality_chart_contract_action"] == "Priorizar oportunidades con LIVE_DATA_OK."
    assert status["alert_quality_chart_contract_operable_count"] == 1
    assert status["alert_quality_chart_contract_blocked_count"] == 2
    assert status["alert_quality_chart_contract_missing_count"] == 2
    assert status["alert_quality_chart_contract_blocked_symbols"] == [
        "WMT: CHART_CONTRACT_MISSING",
        "PEP: CHART_CONTRACT_MISSING",
    ]
    assert status["system_status"] == "WARN"
    assert status["market_state"] == "BLOCKED_REALTIME"
    assert status["status"] == "WARN"
    assert status["state"] == "BLOCKED_REALTIME"
    assert status["route"] == "Operar solo CRYPTO"
    assert status["contract_version"] == 2
    assert status["label"] == "Bloqueo parcial"
    assert status["tone"] == "avoid"
    assert status["safe_mode"] == "NO_STOCK_OR_OPTIONS_ALERTS"
    assert status["active_route"] == "PARTIAL_MARKET_ROUTE"
    assert status["active_route_label"] == "Operar solo CRYPTO"
    assert status["active_route_detail"] == "Operable CRYPTO; bloqueado STOCK, OPTIONS."
    assert status["allowed_markets"] == ["crypto"]
    assert status["blocked_markets"] == ["stock", "options"]
    assert status["blocked_route_markets"] == ["stock", "options"]
    assert status["blocked_route_market_count"] == 2
    assert status["blocked_opportunity_market_count"] == 1
    assert status["stock_alerts_allowed"] is False
    assert status["crypto_alerts_allowed"] is True
    assert status["options_alerts_allowed"] is False
    assert status["session_stock_alerts_allowed"] is True
    assert status["recommended_action"] == "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN."


def test_status_snapshot_keeps_stock_options_blocked_while_crypto_waits(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "state": "WAITING",
                "diagnostic_label": "Esperando gatillo 15m",
                "blocker_category": "MARKET_TRIGGER_WAIT",
                "false_negative_risk": "MEDIUM",
                "blocked_markets": ["stock", "options"],
                "blocked_route_markets": ["stock", "options"],
                "blocked_route_market_count": 2,
                "blocked_opportunity_market_count": 0,
                "allowed_markets": ["crypto"],
                "recommended_action": "Mantener watchlist; no alertar hasta que 15m confirme entrada",
            }
        )
    )

    status = build_status_snapshot(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "realtime_health": {
                "active_route": "PARTIAL_MARKET_ROUTE",
                "active_route_label": "Operar solo CRYPTO",
                "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                "allowed_markets": ["crypto"],
            },
            "opportunities": [
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "ai_action": "WATCH",
                    "alert_gate": "WAIT_15M_ENTRY",
                    "alert_quality": "B",
                    "alert_readiness_score": 78.9,
                }
            ],
        }
    )

    assert status["market_state"] == "WAITING"
    assert status["safe_mode"] == "NO_STOCK_OR_OPTIONS_ALERTS"
    assert status["active_route_label"] == "Operar solo CRYPTO"
    assert status["allowed_markets"] == ["crypto"]
    assert status["blocked_markets"] == ["stock", "options"]
    assert status["blocked_route_markets"] == ["stock", "options"]
    assert status["blocked_route_market_count"] == 2
    assert status["blocked_opportunity_market_count"] == 0
    assert status["stock_alerts_allowed"] is False
    assert status["crypto_alerts_allowed"] is True
    assert status["options_alerts_allowed"] is False


def test_status_snapshot_routes_around_chart_blocked_markets(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "state": "BLOCKED_REALTIME",
                "diagnostic_label": "Graficas bloquean",
                "blocker_category": "CHART_CONTRACT_BLOCK",
                "false_negative_risk": "HIGH",
                "blocked_markets": ["stock", "options"],
                "recommended_action": "No emitir alertas hasta recuperar contrato realtime de grafica.",
                "chart_contract_label": "Graficas bloqueadas",
                "chart_contract_blocked_count": 2,
            }
        )
    )

    status = build_status_snapshot(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "realtime_health": {
                "active_route": "ALL_MARKETS_ROUTE",
                "active_route_label": "Operar mercados realtime",
                "active_route_detail": "Operable STOCK, CRYPTO, OPTIONS.",
                "allowed_markets": ["stock", "crypto", "options"],
            },
            "opportunities": [
                {
                    "symbol": "ASML",
                    "market": "stock",
                    "ai_action": "WATCH",
                    "alert_gate": "BLOCKED_REALTIME_DATA",
                    "alert_quality": "C",
                    "alert_readiness_score": 60,
                }
            ],
        }
    )

    assert status["safe_mode"] == "NO_STOCK_OR_OPTIONS_ALERTS"
    assert status["allowed_markets"] == ["crypto"]
    assert status["blocked_markets"] == ["stock", "options"]
    assert status["active_route"] == "PARTIAL_MARKET_ROUTE"
    assert status["active_route_label"] == "Operar solo CRYPTO"
    assert status["active_route_detail"] == "Operable CRYPTO; bloqueado STOCK, OPTIONS."


def test_status_snapshot_closes_route_when_chart_blocks_all_markets(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T12:00:00+00:00",
                "state": "BLOCKED_REALTIME",
                "diagnostic_label": "Graficas bloquean",
                "blocker_category": "CHART_CONTRACT_BLOCK",
                "false_negative_risk": "HIGH",
                "blocked_markets": ["crypto", "stock", "options"],
                "recommended_action": "No emitir alertas hasta recuperar contrato realtime de grafica.",
            }
        )
    )

    status = build_status_snapshot(
        {
            "generated_at": "2026-06-10T12:00:00+00:00",
            "realtime_health": {
                "active_route": "ALL_MARKETS_ROUTE",
                "active_route_label": "Operar mercados realtime",
                "active_route_detail": "Operable STOCK, CRYPTO, OPTIONS.",
                "allowed_markets": ["stock", "crypto", "options"],
            },
            "opportunities": [{"symbol": "ETH/USD", "market": "crypto", "alert_gate": "BLOCKED_REALTIME_DATA"}],
        }
    )

    assert status["safe_mode"] == "NO_ALERTS_UNTIL_DATA_OK"
    assert status["allowed_markets"] == []
    assert status["blocked_markets"] == ["crypto", "stock", "options"]
    assert status["active_route"] == "NO_MARKET_ROUTE"
    assert status["active_route_label"] == "No operar realtime"
    assert status["active_route_detail"] == "Bloqueado STOCK, CRYPTO, OPTIONS."


def test_write_status_snapshot_outputs_active_market_route(tmp_path, monkeypatch):
    import roxy_ai

    monkeypatch.setattr(roxy_ai, "STATUS_TEXT_PATH", tmp_path / "status.txt")
    monkeypatch.setattr(roxy_ai, "STATUS_JSON_PATH", tmp_path / "status.json")
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", tmp_path / "missing_alert_quality.json")
    brief = {
        "generated_at": "2026-06-10T12:00:00+00:00",
        "realtime_health": {
            "label": "Premium bloqueado",
            "detail": "Operar solo CRYPTO: Operable CRYPTO; bloqueado STOCK, OPTIONS.",
            "active_route": "PARTIAL_MARKET_ROUTE",
            "active_route_label": "Operar solo CRYPTO",
            "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
            "allowed_markets": ["crypto"],
        },
        "opportunities": [
            {
                "symbol": "ETH/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "alert_gate": "WAIT_15M_ENTRY",
                "alert_quality": "B",
                "alert_readiness_score": 88.9,
                "alert_next_action": "Esperar gatillo BUY en 15m.",
                "alert_blockers": ["15m da entrada: WAIT"],
            }
        ],
    }

    status = write_status_snapshot(brief)
    status_text = (tmp_path / "status.txt").read_text()
    status_json = json.loads((tmp_path / "status.json").read_text())

    assert status["active_route_label"] == "Operar solo CRYPTO"
    assert status_json["active_route_detail"] == "Operable CRYPTO; bloqueado STOCK, OPTIONS."
    assert "Route: Operar solo CRYPTO | Operable CRYPTO; bloqueado STOCK, OPTIONS." in status_text


def test_status_snapshot_ignores_stale_alert_quality_action(tmp_path, monkeypatch):
    import roxy_ai

    quality_path = tmp_path / "alert_quality.json"
    monkeypatch.setattr(roxy_ai, "ALERT_QUALITY_JSON_PATH", quality_path)
    quality_path.write_text(
        json.dumps(
            {
                "brief_generated_at": "2026-06-10T11:59:00+00:00",
                "summary": {
                    "state": "WAITING",
                    "recommended_action": "Rotar foco viejo",
                    "rotation_candidates": ["OLD 50.0% C"],
                    "waiting_streak": 50,
                },
            }
        )
    )

    status = build_status_snapshot({"generated_at": "2026-06-10T12:00:00+00:00", "opportunities": []})

    assert status["alert_quality_recommended_action"] == "-"
    assert status["alert_quality_rotation_candidates"] == []
    assert status["alert_quality_waiting_streak"] == 0
    assert status["system_status"] == "WARN"
    assert status["market_state"] == "NO_SETUPS"
    assert status["safe_mode"] == "NO_SETUPS"
    assert status["recommended_action"] == "-"


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
    assert row["best_target_hit"] == "-"
    assert row["best_reward_r"] == 0.5
    assert row["stopped_after_target"] is False
    assert row["stopped_before_target"] is False
    assert row["outcome_state"] == "NEAR_2PCT"


def test_update_alert_outcomes_uses_max_price_for_target_memory():
    memory = {
        "symbols": {},
        "lessons": [],
        "strategy_stats": {"Pullback": {"seen": 1, "alerts": 1}},
        "alert_history": [
            {
                "symbol": "AAPL",
                "entry": 100,
                "stop": 97,
                "max_price": 106,
                "status": "OPEN",
                "milestones": [],
                "strategy_family": "Pullback",
            }
        ],
    }

    updated = update_alert_outcomes(memory, {"AAPL": 101})
    alert = updated["alert_history"][0]

    assert alert["status"] == "HIT_5PCT"
    assert alert["best_target_hit"] == "5%"
    assert alert["best_target_pct"] == 5.0
    assert alert["best_reward_r"] == 2.0
    assert alert["outcome_state"] == "HIT_5PCT"
    assert updated["strategy_stats"]["Pullback"]["hit_2pct"] == 1
    assert updated["strategy_stats"]["Pullback"]["hit_5pct"] == 1


def test_update_trade_progress_marks_target_then_stop_separately():
    row = {"max_price": 105.5, "min_price": 100}

    update_trade_progress(row, current=96.9, entry=100, stop=97)

    assert row["best_target_hit"] == "5%"
    assert row["progress_to_stop"] == 1.0
    assert row["stopped_after_target"] is True
    assert row["stopped_before_target"] is False
    assert row["outcome_state"] == "HIT_5PCT_THEN_STOP"


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
