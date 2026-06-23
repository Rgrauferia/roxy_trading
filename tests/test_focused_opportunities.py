import ast
import inspect
from pathlib import Path

import pandas as pd
from datetime import datetime, timedelta, timezone
from collections import namedtuple

from streamlit_app import (
    annotate_options_risk_budget,
    annotate_option_greek_quality,
    annotate_professional_options_contracts,
    alert_preview_table,
    alert_gate_summary_dashboard_status,
    alert_live_panel_rows,
    alpaca_market_data_panel_rows,
    alert_quality_report_dashboard_status,
    alert_focus_rotation_panel_rows,
    alert_quality_rotation_candidates,
    alert_silence_kpi_status,
    autoheal_dashboard_status,
    asset_type_label,
    build_realtime_refresh_script,
    binanceus_symbol_candidates,
    backtest_memory_bias_for_opportunity,
    backtest_memory_bias_from_summary_row,
    backtest_memory_lookup_from_summary,
    build_chart_level_plan,
    build_price_hover_layers,
    build_mini_opportunity_chart,
    build_professional_oscillator_chart,
    build_professional_price_chart,
    build_professional_volume_chart,
    budget_recommendation_rows,
    chart_data_contract,
    chart_command_center_status,
    live_price_data_contract,
    chart_price_domain,
    chart_operational_confidence,
    chart_realtime_pulse_rows,
    build_visual_zone_rows,
    build_command_center_summary,
    chart_live_data_status,
    chart_provider_effective_dashboard_status,
    chart_provider_effective_display_table,
    chart_realtime_dashboard_status,
    chart_realtime_watch_rows,
    chart_freshness_status,
    chart_strategy_summary,
    compact_score_display,
    command_center_checklist_rows,
    command_center_target_prices,
    command_state_from_query_params,
    current_focused_page_state,
    combine_blocked_scanner_display,
    center_decision_summary,
    connection_mode_label,
    crypto_context_memory_bias_for_opportunity,
    crypto_context_memory_bias_from_summary_row,
    crypto_context_memory_lookup_from_summary,
    operational_mode_dashboard_status,
    priority_trade_lane_rows,
    data_freshness_status,
    dashboard_reference_patterns,
    dashboard_ui_stability_status,
    default_trade_plan_symbol,
    disk_dashboard_status,
    execution_blocker_label,
    filter_focused_opportunities,
    focused_display_table_es,
    focused_display_table,
    focused_opportunity_table,
    greek_quality_label,
    health_history_dashboard_status,
    health_history_display_table,
    health_notify_dashboard_status,
    heartbeat_artifact_path,
    hydrate_command_state_from_query_params,
    hydrate_focused_page_state,
    lab_daily_summary_rows,
    load_health_history,
    load_latest_ma_scan,
    live_candle_chart_payload,
    live_ops_strip_rows,
    live_backend_status,
    local_training_media_dashboard_status,
    market_pulse_risk_map,
    market_discovery_mood,
    market_discovery_mover_sections,
    market_discovery_sector_tiles,
    market_discovery_asset_detail,
    market_news_card_rows,
    market_realtime_route_summary,
    market_event_guard,
    merged_alert_quality_summary,
    market_pulse_rows,
    market_pulse_summary,
    notification_channel_display,
    notification_delivery_action_status,
    notification_delivery_dashboard_status,
    notification_history_display_table,
    notification_history_dashboard_status,
    normalize_realtime_refresh_interval,
    opportunity_change_label,
    opportunity_confidence_label,
    actionable_alert_state,
    actionable_alert_transition_event,
    actionable_alert_transition_messages,
    entry_proximity_alert_event,
    entry_proximity_snapshot_from_alert_rows,
    entry_proximity_status,
    entry_proximity_transition_event,
    entry_proximity_transition_messages,
    entry_transition_crypto_paper_practice_candidates,
    entry_transition_paper_practice_candidates,
    entry_exit_plan_engine,
    live_price_session_comparison,
    render_live_price_session_notice,
    render_exact_entry_plan_panel,
    opportunity_is_trade_ready,
    opportunity_has_paper_trigger,
    paper_readiness_gap_rows,
    paper_readiness_gap_status,
    opportunity_budget_fit,
    budget_expectancy_status,
    budget_filtered_opportunity_table,
    budget_strategy_allocation_rows,
    budget_wide_search_rows,
    budget_top_trade_rows,
    budget_execution_stage,
    budget_trade_plan_rows,
    opportunity_ranking_rows,
    opportunity_ranking_score,
    opportunity_data_confidence_status,
    options_liquidity_chart_frame,
    options_quality_chart_frame,
    paper_journal_operational_risk_state,
    opportunity_data_source_bucket,
    opportunity_data_source_status,
    source_memory_bias_for_opportunity,
    source_memory_bias_from_summary_row,
    source_memory_lookup_from_summary,
    strategy_source_memory_bias_for_opportunity,
    strategy_source_memory_bias_from_summary_row,
    strategy_source_memory_lookup_from_summary,
    small_account_learning_rows,
    output_maintenance_dashboard_status,
    opportunity_reason_label,
    prepare_chart_window,
    prepare_options_view,
    persist_command_query_params,
    persist_command_symbol_query_params,
    professional_options_feed_status,
    platform_badge_rows,
    platform_reason_label,
    provider_env_parity_dashboard_status,
    provider_recovery_dashboard_status,
    provider_recovery_steps_table,
    platform_status_label,
    realtime_report_check_card,
    realtime_check_status,
    realtime_lock_dashboard_status,
    realtime_refresh_dashboard_status,
    realtime_data_readiness_status,
    mac_storage_pressure_dashboard_status,
    render_chart_data_contract,
    render_chart_realtime_pulse,
    render_live_ops_strip,
    resolve_study_strategy_choice,
    runtime_backup_dashboard_status,
    _roxy_auto_altair_key,
    safe_key,
    scanner_heatmap_rows,
    scanner_leaderboard_rows,
    scanner_overview_summary,
    stock_monitor_rows,
    crypto_discovery_rows,
    stability_summary_dashboard_status,
    status_snapshot_market_gate,
    status_snapshot_route_summary,
    static_live_price_chart_svg,
    strategy_family_for_row,
    sync_dashboard_query_params,
    STUDY_PAGE_LABELS,
    study_example_rows,
    study_guides_with_lab,
    study_strategy_names,
    trade_plan_platform_preview,
    trade_desk_timeframe_pair,
    trade_decision_card_status,
    timeframe_minutes,
    watch_movement_label,
    _container_width_to_width,
)
import streamlit_app


def function_source_from_file(path, function_name: str) -> str:
    source = Path(path).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""
    return ""


def test_focused_opportunity_table_prioritizes_trade_ready_alerts():
    brief = {
        "opportunities": [
            {
                "ai_action": "WATCH",
                "symbol": "TTEK",
                "market": "stock",
                "ai_score": 95,
                "signal": "AVOID",
                "trade_decision": "NO_TRADE",
            },
            {
                "ai_action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "ai_score": 80,
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "trigger_setup": "PULLBACK",
                "risk_pct": 0.018,
                "recommended_target_pct": 0.05,
            },
        ]
    }

    table = focused_opportunity_table(brief)

    assert table.iloc[0]["symbol"] == "AAPL"
    assert opportunity_is_trade_ready(table.iloc[0].to_dict())
    assert table.iloc[0]["por_que"].startswith("BUY confirmado")
    assert "Target 5%" in table.iloc[0]["por_que"]
    assert "15m sigue BUY" in table.iloc[0]["cambia_si"]


def test_focused_opportunity_table_falls_back_to_scan_candidates_when_primary_is_empty():
    brief = {
        "opportunities": [],
        "crypto_scan_candidates": [
            {
                "symbol": "SOL/USD",
                "market": "crypto",
                "ai_action": "WATCH",
                "signal": "BUY",
                "trade_decision": "WAIT_FOR_TRIGGER",
                "entry": 71.87,
                "stop": 71.08,
                "target_2pct_price": 73.31,
                "confluence_score": 85,
                "trigger_score": 85,
                "relative_volume_15m": 1.4,
                "reasons": "15m cerca de gatillo y 1h sostiene tendencia.",
            }
        ],
    }

    table = focused_opportunity_table(brief)

    assert not table.empty
    assert table.iloc[0]["symbol"] == "SOL/USD"
    assert table.iloc[0]["market"] == "crypto"
    assert table.iloc[0]["entry"] == 71.87
    assert table.iloc[0]["ai_score"] == 85


def test_alert_live_panel_rows_classifies_ready_blocked_and_watch_states():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "alert_gate": "BLOCKED_REALTIME_DATA",
                    "chart_data_gate": "NO_TRADE_FROM_PUBLIC_PRICE",
                    "chart_operable": False,
                    "chart_source_label": "yfinance 1m",
                    "alert_primary_blocker": "Grafica operable: NO_TRADE_FROM_PUBLIC_PRICE | yfinance 1m",
                    "alert_next_action": "Confirmar en TradingView/broker.",
                    "alert_readiness_score": 92,
                    "ai_score": 88,
                },
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "alert_gate": "ALERT_READY",
                    "chart_data_gate": "LIVE_PRICE_OK",
                    "chart_operable": True,
                    "chart_source_label": "BinanceUS ticker",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100.1,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "alert_readiness_score": 100,
                    "ai_score": 94,
                },
                {
                    "symbol": "MSFT",
                    "market": "stock",
                    "alert_gate": "WAIT_15M_ENTRY",
                    "alert_primary_blocker": "15m da entrada: WAIT",
                    "alert_readiness_score": 78,
                },
            ]
        }
    )

    by_symbol = {row["Ticker"]: row for row in rows.to_dict("records")}
    assert by_symbol["BTC/USD"]["Estado"] == "Entrada en zona"
    assert by_symbol["BTC/USD"]["Estado entrada"] == "Entrada en zona"
    assert by_symbol["BTC/USD"]["Entrada"] == 100
    assert by_symbol["BTC/USD"]["Zona entrada"] == "99.8000 - 100.30"
    assert by_symbol["BTC/USD"]["Stop"] == 99
    assert by_symbol["BTC/USD"]["Target 2%"] == 102
    assert round(by_symbol["BTC/USD"]["R:R 2%"], 2) == 2.0
    assert by_symbol["BTC/USD"]["Gate datos"] == "LIVE_PRICE_OK"
    assert by_symbol["BTC/USD"]["TradingView"].endswith("symbol=BTCUSD")
    assert by_symbol["AAPL"]["Estado"] == "Confirmar externo"
    assert by_symbol["AAPL"]["Fuente"] == "yfinance 1m"
    assert by_symbol["AAPL"]["Estado datos"] == "Fallback publico"
    assert by_symbol["AAPL"]["Bucket datos"] == "Fallback"
    assert "Confirmar en Alpaca/TradingView" in by_symbol["AAPL"]["Accion datos"]
    assert "NO_TRADE_FROM_PUBLIC_PRICE" in by_symbol["AAPL"]["Razon"]
    assert by_symbol["MSFT"]["Estado"] == "No operar"
    assert by_symbol["MSFT"]["Bucket datos"] == "Sin contrato"


def test_alert_live_panel_rows_requires_live_price_before_entry_zone_alert():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "Alpaca IEX",
                        "source_mode": "BROKER_DATA",
                    },
                }
            ]
        }
    )

    row = rows.iloc[0].to_dict()
    assert row["Estado"] == "Esperar precio live"
    assert row["Estado entrada"] == "Sin precio"
    assert "precio live" in row["Siguiente accion"]


def test_alert_live_panel_rows_marks_entry_transition_for_notification():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100.1,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "Alpaca IEX",
                        "source_mode": "BROKER_DATA",
                    },
                }
            ]
        },
        previous_entry_state={"positions": {"stock:AAPL": {"state": "Cerca de entrada"}}},
    )

    row = rows.iloc[0].to_dict()
    messages = entry_proximity_transition_messages(rows)
    snapshot = entry_proximity_snapshot_from_alert_rows(rows)

    assert row["Cambio entrada"] == "Cerca de entrada -> Entrada en zona"
    assert row["Alerta entrada"] == "SI"
    assert bool(row["_entry_transition_alert"]) is True
    assert messages and "Paper/manual" in messages[0]
    assert snapshot["stock:AAPL"]["state"] == "Entrada en zona"
    assert row["Decision alerta"] == "Entra ahora"
    assert row["Cambio decision"] == "Vigilar -> Entra ahora"
    assert row["Alerta decision"] == "SI"
    action_messages = actionable_alert_transition_messages(rows)
    assert action_messages and "ENTRA AHORA" in action_messages[0]
    assert snapshot["stock:AAPL"]["actionable_state"] == "Entra ahora"


def test_alert_live_panel_rows_marks_pullback_action_transition():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 102.0,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "Alpaca IEX",
                        "source_mode": "BROKER_DATA",
                    },
                }
            ]
        },
        previous_entry_state={"positions": {"stock:AAPL": {"state": "Entrada en zona", "actionable_state": "Entra ahora"}}},
    )

    row = rows.iloc[0].to_dict()

    assert row["Decision alerta"] == "Espera pullback"
    assert row["Cambio decision"] == "Entra ahora -> Espera pullback"
    assert row["Alerta decision"] == "SI"
    assert bool(row["_action_transition_alert"]) is True


def test_alert_live_panel_rows_marks_no_operar_action_transition():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 98.0,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "Alpaca IEX",
                        "source_mode": "BROKER_DATA",
                    },
                }
            ]
        },
        previous_entry_state={"positions": {"stock:AAPL": {"state": "Entrada en zona", "actionable_state": "Entra ahora"}}},
    )

    row = rows.iloc[0].to_dict()

    assert row["Decision alerta"] == "No operar"
    assert row["Cambio decision"] == "Entra ahora -> No operar"
    assert row["Alerta decision"] == "SI"
    assert bool(row["_action_transition_alert"]) is True


def test_actionable_alert_transition_event_does_not_notify_initial_snapshot():
    transition = actionable_alert_transition_event(
        symbol="AAPL",
        market="stock",
        current_state="Entra ahora",
        previous_snapshot={},
        alert_state={"message": "AAPL | ENTRA AHORA"},
    )

    assert transition["changed"] is False
    assert transition["should_notify"] is False
    assert transition["transition"] == "Nuevo -> Entra ahora"


def test_entry_transition_paper_practice_candidates_records_ready_stock_transition():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100.1,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "strategy_family": "Pullback",
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "Alpaca IEX",
                        "source_mode": "BROKER_DATA",
                    },
                }
            ]
        },
        previous_entry_state={"positions": {"stock:AAPL": {"state": "Cerca de entrada"}}},
    )

    candidates = entry_transition_paper_practice_candidates(rows, account_equity=500, risk_pct=0.01)

    assert len(candidates) == 1
    row = candidates.iloc[0].to_dict()
    assert row["status"] == "READY_FOR_PAPER"
    assert row["symbol"] == "AAPL"
    assert row["entry"] == 100
    assert row["stop"] == 99
    assert row["target_2"] == 102
    assert row["data_bucket"] == "Live real"
    assert row["data_source"] == "Alpaca IEX"


def test_entry_transition_paper_practice_candidates_records_ready_stock_snapshot_without_prior_state():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100.1,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "strategy_family": "Pullback",
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "Alpaca IEX",
                        "source_mode": "BROKER_DATA",
                    },
                }
            ]
        },
        previous_entry_state={},
    )

    row = rows.iloc[0].to_dict()
    candidates = entry_transition_paper_practice_candidates(rows, account_equity=500, risk_pct=0.01)

    assert row["Cambio entrada"] == "Nuevo -> Entrada en zona"
    assert row["Alerta entrada"] == "NO"
    assert bool(row["_entry_transition_alert"]) is False
    assert bool(row["_entry_ready_snapshot"]) is True
    assert len(candidates) == 1
    assert candidates.iloc[0]["status"] == "READY_FOR_PAPER"
    assert candidates.iloc[0]["symbol"] == "AAPL"


def test_entry_transition_paper_practice_candidates_skip_crypto_for_alpaca_journal():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100.1,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "BinanceUS ticker",
                        "source_mode": "EXCHANGE_API",
                    },
                }
            ]
        },
        previous_entry_state={"positions": {"crypto:BTC/USD": {"state": "Cerca de entrada"}}},
    )

    candidates = entry_transition_paper_practice_candidates(rows, account_equity=500, risk_pct=0.01)

    assert candidates.empty


def test_entry_transition_crypto_paper_practice_candidates_records_crypto_transition():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100.1,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "timeframe": "1h",
                    "strategy_family": "Breakout crypto",
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "BinanceUS ticker",
                        "source_mode": "EXCHANGE_API",
                    },
                }
            ]
        },
        previous_entry_state={"positions": {"crypto:BTC/USD": {"state": "Cerca de entrada"}}},
    )

    candidates = entry_transition_crypto_paper_practice_candidates(rows, account_equity=500, risk_pct=0.01)

    assert len(candidates) == 1
    row = candidates.iloc[0].to_dict()
    assert row["status"] == "READY_FOR_PAPER"
    assert row["symbol"] == "BTC/USD"
    assert row["entry"] == 100
    assert row["stop"] == 99
    assert row["target_2"] == 102
    assert row["data_source"] == "BinanceUS ticker"
    assert row["timeframe"] == "1h"


def test_entry_transition_crypto_paper_practice_candidates_records_ready_crypto_snapshot_without_prior_state():
    rows = alert_live_panel_rows(
        {
            "opportunities": [
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "alert_gate": "ALERT_READY",
                    "action": "ALERT",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100.1,
                    "stop": 99,
                    "risk_pct": 0.01,
                    "timeframe": "15m",
                    "strategy_family": "Breakout crypto",
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "BinanceUS ticker",
                        "source_mode": "EXCHANGE_API",
                    },
                }
            ]
        },
        previous_entry_state={},
    )

    row = rows.iloc[0].to_dict()
    candidates = entry_transition_crypto_paper_practice_candidates(rows, account_equity=500, risk_pct=0.01)

    assert row["Cambio entrada"] == "Nuevo -> Entrada en zona"
    assert bool(row["_entry_ready_snapshot"]) is True
    assert len(candidates) == 1
    assert candidates.iloc[0]["status"] == "READY_FOR_PAPER"
    assert candidates.iloc[0]["symbol"] == "BTC/USD"
    assert candidates.iloc[0]["timeframe"] == "15m"


def test_opportunity_data_source_status_classifies_broker_exchange_and_fallback_sources():
    broker = opportunity_data_source_status(
        {
            "live_price_contract": {
                "gate": "LIVE_PRICE_OK",
                "source_label": "Alpaca IEX",
                "source_mode": "BROKER_DATA",
                "detail": "fuente Alpaca IEX | edad 3s",
            }
        }
    )
    crypto = opportunity_data_source_status(
        {
            "chart_data_contract": {
                "gate": "LIVE_DATA_OK",
                "source_label": "BinanceUS ticker",
                "source_mode": "EXCHANGE_API",
            }
        }
    )
    fallback = opportunity_data_source_status(
        {
            "live_price_gate": "NO_TRADE_FROM_PUBLIC_PRICE",
            "price_source_label": "yfinance 1m",
            "price_source_mode": "PUBLIC_MARKET_DATA",
        }
    )

    assert broker["state"] == "Broker/exchange live"
    assert broker["operable"] is True
    assert crypto["state"] == "Broker/exchange live"
    assert fallback["state"] == "Fallback publico"
    assert fallback["tone"] == "watch"
    assert fallback["operable"] is False


def test_opportunity_data_source_bucket_sets_priority_caps_for_alerts():
    live = opportunity_data_source_bucket({"live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"}})
    fallback = opportunity_data_source_bucket(
        {"live_price_contract": {"gate": "NO_TRADE_FROM_PUBLIC_PRICE", "source_label": "yfinance 1m"}}
    )
    blocked = opportunity_data_source_bucket(
        {"live_price_contract": {"gate": "NO_TRADE_PRICE_FAIL", "source_label": "Alpaca IEX"}}
    )
    missing = opportunity_data_source_bucket({"symbol": "AAPL"})

    assert live["bucket"] == "Live real"
    assert live["priority_cap"] == 2
    assert fallback["bucket"] == "Fallback"
    assert fallback["priority_cap"] == 1
    assert fallback["alert_state"] == "Confirmar externo"
    assert blocked["bucket"] == "Bloqueadas"
    assert blocked["priority_cap"] == 0
    assert missing["bucket"] == "Sin contrato"
    assert missing["alert_state"] == "No operar"


def test_source_memory_bias_from_summary_row_classifies_positive_negative_and_learning():
    positive = source_memory_bias_from_summary_row(
        {"data_bucket": "Live real", "data_source": "Alpaca IEX", "tracked": 5, "hit_2_rate": 0.6, "hit_5_rate": 0.2, "stop_rate": 0.2}
    )
    negative = source_memory_bias_from_summary_row(
        {"data_bucket": "Fallback", "data_source": "yfinance 1m", "tracked": 5, "hit_2_rate": 0.2, "hit_5_rate": 0.0, "stop_rate": 0.6}
    )
    learning = source_memory_bias_from_summary_row(
        {"data_bucket": "Live real", "data_source": "Alpaca IEX", "tracked": 1, "hit_2_rate": 1.0, "stop_rate": 0.0}
    )

    assert positive["label"] == "Memoria fuente positiva"
    assert positive["tone"] == "buy"
    assert negative["label"] == "Memoria fuente negativa"
    assert negative["priority_delta"] == -1
    assert learning["label"] == "Aprendiendo"
    assert "falta muestra" in learning["action"]


def test_source_memory_bias_for_opportunity_matches_bucket_and_source():
    lookup = source_memory_lookup_from_summary(
        [
            {
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "tracked": 4,
                "hit_2_rate": 0.75,
                "hit_5_rate": 0.25,
                "stop_rate": 0.0,
            }
        ]
    )

    bias = source_memory_bias_for_opportunity(
        {"live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"}},
        lookup,
    )

    assert bias["label"] == "Memoria fuente positiva"
    assert "Alpaca IEX" in bias["detail"]


def test_strategy_source_memory_bias_from_summary_row_classifies_combination():
    positive = strategy_source_memory_bias_from_summary_row(
        {
            "strategy_family": "Pullback",
            "data_bucket": "Live real",
            "data_source": "Alpaca IEX",
            "tracked": 4,
            "hit_2_rate": 0.75,
            "hit_5_rate": 0.25,
            "stop_rate": 0.0,
        }
    )
    negative = strategy_source_memory_bias_from_summary_row(
        {
            "strategy_family": "Pullback",
            "data_bucket": "Fallback",
            "data_source": "yfinance 1m",
            "tracked": 4,
            "hit_2_rate": 0.0,
            "stop_rate": 0.75,
        }
    )

    assert positive["label"] == "Memoria setup+fuente positiva"
    assert "Pullback" in positive["detail"]
    assert negative["label"] == "Memoria setup+fuente negativa"
    assert negative["priority_delta"] == -1


def test_strategy_source_memory_bias_for_opportunity_matches_strategy_bucket_source():
    lookup = strategy_source_memory_lookup_from_summary(
        [
            {
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "tracked": 5,
                "hit_2_rate": 0.2,
                "hit_5_rate": 0.0,
                "stop_rate": 0.8,
            }
        ]
    )

    bias = strategy_source_memory_bias_for_opportunity(
        {
            "strategy_family": "Pullback",
            "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
        },
        lookup,
    )

    assert bias["label"] == "Memoria setup+fuente negativa"
    assert "esta estrategia con esta fuente fallo" in bias["action"]


def test_backtest_memory_bias_from_summary_row_classifies_positive_negative_and_learning():
    positive = backtest_memory_bias_from_summary_row(
        {
            "strategy_family": "Pullback",
            "timeframe": "1h",
            "trades": 12,
            "win_rate": 0.55,
            "profit_factor": 1.8,
            "avg_r": 0.42,
            "max_drawdown_pct": 0.08,
        }
    )
    negative = backtest_memory_bias_from_summary_row(
        {
            "strategy_family": "Breakout",
            "timeframe": "15m",
            "trades": 14,
            "win_rate": 0.35,
            "profit_factor": 0.8,
            "avg_r": -0.15,
            "max_drawdown_pct": 0.18,
        }
    )
    learning = backtest_memory_bias_from_summary_row(
        {
            "strategy_family": "Pullback",
            "timeframe": "4h",
            "trades": 4,
            "profit_factor": 3.0,
            "avg_r": 1.2,
        }
    )

    assert positive["label"] == "Backtest positivo"
    assert positive["priority_delta"] == 1
    assert negative["label"] == "Backtest negativo"
    assert negative["priority_delta"] == -1
    assert learning["label"] == "Backtest aprendiendo"


def test_backtest_memory_bias_for_opportunity_matches_strategy_timeframe_fallback():
    lookup = backtest_memory_lookup_from_summary(
        [
            {
                "strategy_family": "Pullback",
                "timeframe": "1h",
                "symbol": "-",
                "source": "-",
                "trades": 12,
                "win_rate": 0.55,
                "profit_factor": 1.8,
                "avg_r": 0.42,
                "max_drawdown_pct": 0.08,
            }
        ]
    )

    bias = backtest_memory_bias_for_opportunity(
        {"symbol": "AAPL", "market": "stock", "timeframe": "1h", "strategy_family": "Pullback"},
        lookup,
    )

    assert bias["label"] == "Backtest positivo"
    assert "Pullback" in bias["detail"]


def test_opportunity_data_source_status_blocks_failed_or_missing_contracts():
    failed = opportunity_data_source_status(
        {"live_price_contract": {"gate": "NO_TRADE_PRICE_FAIL", "source_label": "Alpaca", "source_mode": "BROKER_DATA"}}
    )
    missing = opportunity_data_source_status({"symbol": "AAPL"})

    assert failed["state"] == "Datos bloqueados"
    assert failed["tone"] == "avoid"
    assert failed["operable"] is False
    assert missing["state"] == "Sin contrato"
    assert missing["action"] == "Adjuntar contrato de precio/grafica antes de alertar."


def test_focused_opportunity_table_exposes_data_source_contract_columns():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_action": "WATCH",
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "ai_score": 72,
                    "live_price_contract": {
                        "gate": "NO_TRADE_FROM_PUBLIC_PRICE",
                        "source_label": "yfinance 1m",
                        "source_mode": "PUBLIC_MARKET_DATA",
                    },
                }
            ]
        }
    )

    row = table.iloc[0].to_dict()
    assert row["data_state"] == "Fallback publico"
    assert row["data_bucket"] == "Fallback"
    assert row["data_gate"] == "NO_TRADE_FROM_PUBLIC_PRICE"
    assert row["data_source"] == "yfinance 1m"
    assert "Confirmar en Alpaca/TradingView" in row["data_source_action"]


def test_market_pulse_degrades_ready_alerts_when_data_source_is_not_operable():
    table = focused_opportunity_table(
        {
            "opportunities": [
                    {
                        "symbol": "LIVE",
                        "market": "stock",
                        "ai_action": "ALERT",
                        "signal": "BUY",
                        "trade_decision": "TRADE_FOR_2PCT",
                        "entry": 100,
                        "current_price": 100.1,
                        "stop": 99,
                        "risk_pct": 0.01,
                        "ai_score": 90,
                        "alert_readiness_score": 95,
                        "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
                },
                {
                    "symbol": "FALL",
                    "market": "stock",
                    "ai_action": "ALERT",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "ai_score": 91,
                    "alert_readiness_score": 96,
                    "live_price_contract": {"gate": "NO_TRADE_FROM_PUBLIC_PRICE", "source_label": "yfinance 1m"},
                },
                {
                    "symbol": "FAIL",
                    "market": "stock",
                    "ai_action": "ALERT",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "ai_score": 92,
                    "alert_readiness_score": 97,
                    "live_price_contract": {"gate": "NO_TRADE_PRICE_FAIL", "source_label": "Alpaca IEX"},
                },
                {
                    "symbol": "MISS",
                    "market": "stock",
                    "ai_action": "ALERT",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "ai_score": 93,
                    "alert_readiness_score": 98,
                },
            ]
        }
    )

    pulse = market_pulse_rows(table)
    by_symbol = {row["symbol"]: row for row in pulse.to_dict("records")}
    summary = market_pulse_summary(table)

    assert by_symbol["LIVE"]["bucket"] == "Operar"
    assert by_symbol["FALL"]["bucket"] == "Vigilar"
    assert by_symbol["FAIL"]["bucket"] == "Evitar"
    assert by_symbol["MISS"]["bucket"] == "Evitar"
    assert summary["ready"] == 1
    assert summary["watch"] == 1
    assert summary["avoid"] == 2
    assert summary["live_real"] == 1
    assert summary["fallback"] == 1
    assert summary["data_blocked"] == 1
    assert summary["missing_contract"] == 1


def test_focused_opportunity_table_lowers_priority_for_negative_source_memory():
    brief = {
        "source_memory_summary": [
            {
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "tracked": 5,
                "hit_2_rate": 0.2,
                "hit_5_rate": 0.0,
                "stop_rate": 0.8,
            }
        ],
        "strategy_source_memory_summary": [
            {
                "strategy_family": "Otro setup",
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "tracked": 5,
                "hit_2_rate": 0.8,
                "stop_rate": 0.0,
            }
        ],
        "opportunities": [
            {
                "symbol": "AAPL",
                "market": "stock",
                "ai_action": "ALERT",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "ai_score": 92,
                "alert_readiness_score": 95,
                "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
            }
        ],
    }

    table = focused_opportunity_table(brief)
    row = table.iloc[0].to_dict()

    assert row["source_memory_bias"] == "Memoria fuente negativa"
    assert row["focus_priority"] == 1
    assert "Bajar prioridad" in row["source_memory_action"]


def test_focused_opportunity_table_adds_backtest_memory_from_brief_summary():
    table = focused_opportunity_table(
        {
            "backtest_memory_summary": [
                {
                    "strategy_family": "Pullback",
                    "timeframe": "1h",
                    "symbol": "-",
                    "source": "-",
                    "trades": 12,
                    "win_rate": 0.55,
                    "profit_factor": 1.8,
                    "avg_r": 0.42,
                    "max_drawdown_pct": 0.08,
                }
            ],
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_action": "ALERT",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "ai_score": 92,
                    "alert_readiness_score": 95,
                    "timeframe": "1h",
                    "strategy_family": "Pullback",
                    "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
                }
            ],
        }
    )

    row = table.iloc[0].to_dict()

    assert row["backtest_memory_bias"] == "Backtest positivo"
    assert row["backtest_memory_action"].startswith("Subir prioridad")
    assert row["focus_priority"] == 3


def test_focused_opportunity_table_adds_tradingview_webhook_confirmation_from_brief():
    received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    table = focused_opportunity_table(
        {
            "tradingview_webhooks": [
                {
                    "webhook_id": "tv-aapl",
                    "received_at": received_at,
                    "symbol": "AAPL",
                    "symbol_key": "AAPL",
                    "timeframe": "15m",
                    "signal": "BUY",
                    "source": "TradingView webhook",
                }
            ],
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_action": "ALERT",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "ai_score": 92,
                    "alert_readiness_score": 95,
                    "timeframe": "15m",
                    "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
                }
            ],
        }
    )

    row = table.iloc[0].to_dict()

    assert row["tradingview_confirmation"] == "TradingView confirma"
    assert row["tradingview_confirmation_action"].startswith("Subir prioridad")
    assert row["focus_priority"] == 3


def test_focused_opportunity_table_lowers_priority_for_negative_strategy_source_memory():
    brief = {
        "source_memory_summary": [
            {
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "tracked": 5,
                "hit_2_rate": 0.8,
                "stop_rate": 0.0,
            }
        ],
        "strategy_source_memory_summary": [
            {
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "tracked": 5,
                "hit_2_rate": 0.0,
                "hit_5_rate": 0.0,
                "stop_rate": 0.8,
            }
        ],
        "opportunities": [
            {
                "symbol": "AAPL",
                "market": "stock",
                "strategy_family": "Pullback",
                "ai_action": "ALERT",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "ai_score": 92,
                "alert_readiness_score": 95,
                "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
            }
        ],
    }

    table = focused_opportunity_table(brief)
    row = table.iloc[0].to_dict()

    assert row["strategy_source_memory_bias"] == "Memoria setup+fuente negativa"
    assert row["focus_priority"] == 1
    assert "Bajar prioridad" in row["strategy_source_memory_action"]


def test_alert_live_panel_rows_marks_ready_alert_as_negative_source_memory():
    rows = alert_live_panel_rows(
        {
            "source_memory_summary": [
                {
                    "data_bucket": "Live real",
                    "data_source": "Alpaca IEX",
                    "tracked": 5,
                    "hit_2_rate": 0.0,
                    "hit_5_rate": 0.0,
                    "stop_rate": 0.8,
                }
            ],
            "strategy_source_memory_summary": [
                {
                    "strategy_family": "Otro setup",
                    "data_bucket": "Live real",
                    "data_source": "Alpaca IEX",
                    "tracked": 5,
                    "hit_2_rate": 0.8,
                    "stop_rate": 0.0,
                }
            ],
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "alert_gate": "ALERT_READY",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "Alpaca IEX",
                        "source_mode": "BROKER_DATA",
                    },
                    "alert_readiness_score": 99,
                }
            ],
        }
    )

    row = rows.iloc[0].to_dict()
    assert row["Estado"] == "Memoria fuente negativa"
    assert row["Memoria fuente"] == "Memoria fuente negativa"
    assert "Bajar prioridad" in row["Accion memoria"]


def test_alert_live_panel_rows_marks_ready_alert_as_negative_strategy_source_memory():
    rows = alert_live_panel_rows(
        {
            "source_memory_summary": [
                {
                    "data_bucket": "Live real",
                    "data_source": "Alpaca IEX",
                    "tracked": 5,
                    "hit_2_rate": 0.8,
                    "stop_rate": 0.0,
                }
            ],
            "strategy_source_memory_summary": [
                {
                    "strategy_family": "Pullback",
                    "data_bucket": "Live real",
                    "data_source": "Alpaca IEX",
                    "tracked": 5,
                    "hit_2_rate": 0.0,
                    "hit_5_rate": 0.0,
                    "stop_rate": 0.8,
                }
            ],
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "strategy_family": "Pullback",
                    "alert_gate": "ALERT_READY",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "live_price_contract": {
                        "gate": "LIVE_PRICE_OK",
                        "source_label": "Alpaca IEX",
                        "source_mode": "BROKER_DATA",
                    },
                    "alert_readiness_score": 99,
                }
            ],
        }
    )

    row = rows.iloc[0].to_dict()
    assert row["Estado"] == "Memoria setup+fuente negativa"
    assert row["Memoria setup+fuente"] == "Memoria setup+fuente negativa"
    assert "esta estrategia con esta fuente fallo" in row["Accion setup+fuente"]


def test_trade_decision_card_status_allows_ready_live_paper_manual_entry():
    status = trade_decision_card_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 100.0,
            "stop": 99.0,
            "target_pct": 0.05,
            "risk_pct": 0.01,
            "data_bucket": "Live real",
            "data_state": "Broker/exchange live",
            "data_gate": "LIVE_PRICE_OK",
            "source_memory_bias": "Memoria fuente positiva",
            "strategy_source_memory_bias": "Memoria setup+fuente positiva",
        }
    )

    assert status["action"] == "Entrar paper/manual"
    assert status["tone"] == "buy"
    assert status["entry"] == 100.0
    assert status["stop"] == 99.0
    assert status["target_2"] == 102.0
    assert round(status["rr_to_2"], 2) == 2.0
    assert "2%" in status["partial_exit"]


def test_trade_decision_card_status_allows_tradingview_confirmed_watch_as_paper_trigger():
    row = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "WATCH",
        "signal": "WATCH",
        "decision": "WAIT_15M_ENTRY",
        "entry": 100.0,
        "current_price": 100.0,
        "stop": 99.0,
        "risk_pct": 0.01,
        "readiness": 82,
        "data_bucket": "Live real",
        "data_state": "Broker/exchange live",
        "data_gate": "LIVE_PRICE_OK",
        "tradingview_confirmation": "TradingView confirma",
        "tradingview_confirmation_action": "Subir prioridad: webhook BUY fresco confirma el setup.",
    }

    status = trade_decision_card_status(row)

    assert opportunity_is_trade_ready(row) is False
    assert opportunity_has_paper_trigger(row) is True
    assert status["action"] == "Entrar paper/manual"
    assert status["tone"] == "buy"
    assert "TradingView BUY fresco" in status["reason"]


def test_paper_readiness_gap_status_explains_missing_tradingview_for_watch_setup():
    row = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "WATCH",
        "signal": "WATCH",
        "decision": "WAIT_15M_ENTRY",
        "entry": 100.0,
        "current_price": 100.0,
        "stop": 99.0,
        "risk_pct": 0.01,
        "readiness": 82,
        "data_bucket": "Live real",
        "data_gate": "LIVE_PRICE_OK",
        "tradingview_confirmation": "Sin webhook TV",
    }

    gap = paper_readiness_gap_status(row)

    assert gap["paper_ready"] is False
    assert "falta confirmacion TradingView" in gap["blockers"]
    assert "falta BUY/ALERT o TV BUY" in " | ".join(gap["blockers"])
    assert gap["entry_proximity"] == "Entrada en zona"


def test_paper_readiness_gap_rows_marks_tradingview_confirmed_watch_ready():
    rows = paper_readiness_gap_rows(
        pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "action": "WATCH",
                    "signal": "WATCH",
                    "decision": "WAIT_15M_ENTRY",
                    "entry": 100.0,
                    "current_price": 100.0,
                    "stop": 99.0,
                    "risk_pct": 0.01,
                    "readiness": 82,
                    "data_bucket": "Live real",
                    "data_gate": "LIVE_PRICE_OK",
                    "tradingview_confirmation": "TradingView confirma",
                }
            ]
        )
    )

    row = rows.iloc[0].to_dict()
    assert row["Listo paper"] == "SI"
    assert row["Bloqueo principal"] == "Listo para paper/manual"
    assert "TradingView BUY fresco" in row["Confirmado"]


def test_trade_decision_card_status_waits_without_live_price():
    status = trade_decision_card_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "stop": 99.0,
            "risk_pct": 0.01,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
        }
    )

    assert status["entry_proximity"] == "Sin precio"
    assert status["action"] == "Esperar confirmacion"


def test_entry_exit_plan_engine_generates_entry_zone_and_targets_for_ready_trade():
    plan = entry_exit_plan_engine(
        {
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 100.2,
            "stop": 98.0,
            "risk_pct": 0.02,
            "data_bucket": "Live real",
        }
    )

    assert plan["plan_status"] == "READY"
    assert round(plan["entry_zone_low"], 2) == 99.8
    assert round(plan["entry_zone_high"], 2) == 100.3
    assert plan["target_2"] == 102.0
    assert plan["target_5"] == 105.0
    assert round(plan["target_10"], 2) == 110.0
    assert "15m" in plan["confirmation_rule"]


def test_live_price_session_comparison_exposes_regular_and_post_market_gap():
    rows = live_price_session_comparison(
        {
            "price": 169.62,
            "source": "yfinance currentPrice",
            "regular_market_price": 169.62,
            "post_market_price": 169.45,
        }
    )

    regular = next(row for row in rows if row["label"] == "Regular/current")
    post = next(row for row in rows if row["label"] == "Post-market")

    assert regular["matches_primary"] is True
    assert post["matches_primary"] is False
    assert post["diff_pct"] < 0
    assert post["tone"] == "watch"


def test_render_live_price_session_notice_keeps_price_discrepancy_visible():
    html = render_live_price_session_notice(
        {
            "price": 169.62,
            "source": "yfinance currentPrice",
            "regular_market_price": 169.62,
            "post_market_price": 169.45,
        }
    )

    assert "Chequeo de precio" in html
    assert "Precio principal" in html
    assert "169.62" in html
    assert "Post-market" in html
    assert "-0.10% vs principal" in html


def test_render_exact_entry_plan_panel_uses_live_price_for_distance_and_rr():
    html = render_exact_entry_plan_panel(
        {
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "stop": 98.0,
            "risk_pct": 0.02,
            "data_bucket": "Live real",
        },
        live_price={"price": 100.2, "source": "BinanceUS API"},
    )

    assert "Entrada exacta" in html
    assert "Entrar solo si confirma" in html
    assert "100.20" in html
    assert "98.00" in html
    assert "R:R 1.00R" in html


def test_entry_proximity_status_marks_price_inside_entry_zone():
    status = entry_proximity_status(
        {
            "entry": 100.0,
            "current_price": 100.1,
            "stop": 98.0,
            "data_bucket": "Live real",
        }
    )

    assert status["state"] == "Entrada en zona"
    assert status["tone"] == "buy"
    assert status["priority_delta"] > 0


def test_entry_proximity_alert_event_fires_only_for_ready_price_in_zone():
    event = entry_proximity_alert_event(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 100.1,
            "stop": 99.0,
            "risk_pct": 0.01,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
        }
    )

    assert event["should_alert"] is True
    assert event["state"] == "Entrada en zona"
    assert "AAPL" in event["message"]


def test_entry_proximity_alert_event_waits_without_live_price():
    event = entry_proximity_alert_event(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "stop": 99.0,
            "risk_pct": 0.01,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
        }
    )

    assert event["should_alert"] is False
    assert event["state"] == "Sin precio"


def test_entry_proximity_transition_event_notifies_when_price_enters_zone():
    event = {
        "state": "Entrada en zona",
        "should_alert": True,
        "message": "AAPL | Entrada en zona",
    }
    transition = entry_proximity_transition_event(
        symbol="AAPL",
        market="stock",
        current_state="Entrada en zona",
        previous_snapshot={"positions": {"stock:AAPL": {"state": "Cerca de entrada"}}},
        alert_event=event,
    )

    assert transition["changed"] is True
    assert transition["entered_zone"] is True
    assert transition["should_notify"] is True
    assert transition["transition"] == "Cerca de entrada -> Entrada en zona"


def test_entry_proximity_transition_event_does_not_notify_initial_snapshot():
    transition = entry_proximity_transition_event(
        symbol="AAPL",
        market="stock",
        current_state="Entrada en zona",
        previous_snapshot={},
        alert_event={"state": "Entrada en zona", "should_alert": True},
    )

    assert transition["changed"] is False
    assert transition["should_notify"] is False
    assert transition["transition"] == "Nuevo -> Entrada en zona"


def test_entry_proximity_status_marks_price_near_entry_zone():
    status = entry_proximity_status(
        {
            "entry": 100.0,
            "current_price": 99.4,
            "stop": 98.0,
            "data_bucket": "Live real",
        }
    )

    assert status["state"] == "Cerca de entrada"
    assert status["tone"] == "watch"
    assert "15m" in status["action"]


def test_entry_proximity_status_blocks_chasing_far_above_entry_zone():
    status = entry_proximity_status(
        {
            "entry": 100.0,
            "current_price": 102.0,
            "stop": 98.0,
            "data_bucket": "Live real",
        }
    )

    assert status["state"] == "No perseguir"
    assert status["tone"] == "avoid"
    assert status["priority_delta"] < 0


def test_entry_proximity_status_invalidates_price_below_stop():
    status = entry_proximity_status(
        {
            "entry": 100.0,
            "current_price": 97.9,
            "stop": 98.0,
            "data_bucket": "Live real",
        }
    )

    assert status["state"] == "Invalida"
    assert status["tone"] == "avoid"
    assert "stop" in status["detail"]


def test_entry_exit_plan_engine_blocks_chasing_when_price_is_extended():
    plan = entry_exit_plan_engine(
        {
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 102.0,
            "stop": 97.0,
            "data_bucket": "Live real",
        }
    )

    assert plan["plan_status"] == "BLOCKED"
    assert "precio alejado de entrada" in plan["blockers"]
    assert "No perseguir" in plan["do_not_chase_rule"]


def test_trade_decision_card_status_waits_when_price_is_near_but_not_inside_zone():
    status = trade_decision_card_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 99.4,
            "stop": 98.0,
            "risk_pct": 0.02,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
        }
    )

    assert status["entry_proximity"] == "Cerca de entrada"
    assert status["action"] == "Esperar confirmacion"


def test_entry_exit_plan_engine_blocks_missing_stop():
    plan = entry_exit_plan_engine(
        {
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "data_bucket": "Live real",
        }
    )

    assert plan["plan_status"] == "BLOCKED"
    assert "falta stop" in plan["blockers"]


def test_entry_exit_plan_engine_blocks_when_target_2pays_less_than_one_r():
    plan = entry_exit_plan_engine(
        {
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "stop": 95.0,
            "target_2": 101.0,
            "data_bucket": "Live real",
        }
    )

    assert plan["plan_status"] == "BLOCKED"
    assert "target 2% paga menos de 1R" in plan["blockers"]


def test_paper_journal_operational_risk_state_allows_clean_day():
    state = paper_journal_operational_risk_state(
        pd.DataFrame(
            [
                {
                    "status": "READY_FOR_PAPER",
                    "closed_outcome": None,
                    "risk_dollars": 5.0,
                }
            ]
        ),
        pd.DataFrame(),
        account_equity=500,
        risk_per_trade_pct=0.01,
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )

    assert state["state"] == "Puede operar"
    assert state["allowed"] is True
    assert state["open_signals"] == 1
    assert state["remaining_daily_risk"] == 5.0


def test_paper_journal_operational_risk_state_blocks_after_two_stops_today():
    now = datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)
    alpaca = pd.DataFrame(
        [
            {
                "status": "CLOSED_STOP",
                "closed_at": "2026-06-15T13:00:00+00:00",
                "closed_outcome": "STOP",
                "risk_dollars": 5.0,
            },
            {
                "status": "CLOSED_STOP",
                "closed_at": "2026-06-15T14:00:00+00:00",
                "closed_outcome": "STOP",
                "risk_dollars": 5.0,
            },
        ]
    )

    state = paper_journal_operational_risk_state(
        alpaca,
        pd.DataFrame(),
        account_equity=500,
        risk_per_trade_pct=0.01,
        now=now,
    )

    assert state["state"] == "Modo proteccion"
    assert state["allowed"] is False
    assert state["stops_today"] == 2
    assert "stops paper hoy" in state["reason"]


def test_paper_journal_operational_risk_state_blocks_too_many_open_signals():
    open_rows = pd.DataFrame(
        [
            {"status": "READY_FOR_PAPER", "closed_outcome": None, "risk_dollars": 2.0},
            {"status": "READY_FOR_PAPER", "closed_outcome": None, "risk_dollars": 2.0},
            {"status": "READY_FOR_PAPER", "closed_outcome": None, "risk_dollars": 2.0},
        ]
    )

    state = paper_journal_operational_risk_state(
        open_rows,
        pd.DataFrame(),
        account_equity=500,
        risk_per_trade_pct=0.01,
        max_open_signals=3,
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )

    assert state["state"] == "Modo proteccion"
    assert state["allowed"] is False
    assert state["open_signals"] == 3
    assert "señales paper abiertas" in state["reason"]


def test_paper_journal_operational_risk_state_warns_near_open_limit():
    open_rows = pd.DataFrame(
        [
            {"status": "READY_FOR_PAPER", "closed_outcome": None, "risk_dollars": 1.0},
            {"status": "READY_FOR_PAPER", "closed_outcome": None, "risk_dollars": 1.0},
        ]
    )

    state = paper_journal_operational_risk_state(
        open_rows,
        pd.DataFrame(),
        account_equity=500,
        risk_per_trade_pct=0.01,
        max_open_signals=3,
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )

    assert state["state"] == "Riesgo alto"
    assert state["allowed"] is True
    assert "cerca del máximo" in state["reason"]


def test_market_event_guard_blocks_active_macro_context():
    guard = market_event_guard(
        {"symbol": "AAPL", "market": "stock"},
        {
            "active": True,
            "detail": "FOMC activo.",
            "active_events": [{"title": "FOMC Rate Decision", "severity": "HIGH", "minutes_to_event": 0}],
            "top_event": {"title": "FOMC Rate Decision", "severity": "HIGH", "minutes_to_event": 0},
        },
        now=datetime(2026, 6, 15, 18, 0, tzinfo=timezone.utc),
    )

    assert guard["state"] == "Evento macro activo"
    assert guard["tone"] == "avoid"
    assert guard["priority_delta"] == -2
    assert "No abrir" in guard["action"]


def test_market_event_guard_warns_upcoming_high_impact_macro():
    guard = market_event_guard(
        {"symbol": "AAPL", "market": "stock"},
        {
            "active": False,
            "detail": "FOMC en 45 min.",
            "upcoming_events": [{"title": "FOMC Rate Decision", "severity": "HIGH", "minutes_to_event": 45}],
            "top_event": {"title": "FOMC Rate Decision", "severity": "HIGH", "minutes_to_event": 45},
        },
        now=datetime(2026, 6, 15, 17, 15, tzinfo=timezone.utc),
    )

    assert guard["state"] == "Evento macro proximo"
    assert guard["tone"] == "watch"
    assert guard["priority_delta"] == -1


def test_market_event_guard_blocks_near_earnings_for_stock():
    guard = market_event_guard(
        {"symbol": "MSFT", "market": "stock", "next_earnings_date": "2026-06-16T20:00:00+00:00"},
        {},
        now=datetime(2026, 6, 15, 20, 0, tzinfo=timezone.utc),
    )

    assert guard["state"] == "Earnings cercanos"
    assert guard["tone"] == "avoid"
    assert "earnings" in guard["action"].lower()


def test_trade_decision_card_status_blocks_active_market_event():
    status = trade_decision_card_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 100.0,
            "stop": 97.0,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
            "market_event_state": "Evento macro activo",
            "market_event_detail": "FOMC activo.",
            "market_event_action": "No operar hasta reacción post-evento.",
        }
    )

    assert status["action"] == "No operar"
    assert status["tone"] == "avoid"
    assert "FOMC" in status["reason"]


def test_focused_opportunity_table_adds_market_event_guard_from_brief_macro():
    table = focused_opportunity_table(
        {
            "macro_calendar": {
                "active": True,
                "detail": "FOMC activo.",
                "active_events": [{"title": "FOMC Rate Decision", "severity": "HIGH", "minutes_to_event": 0}],
                "top_event": {"title": "FOMC Rate Decision", "severity": "HIGH", "minutes_to_event": 0},
            },
            "opportunities": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_action": "ALERT",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100,
                    "stop": 98,
                    "ai_score": 90,
                    "alert_readiness_score": 90,
                    "risk_pct": 0.02,
                    "data_bucket": "Live real",
                    "data_source": "Alpaca IEX",
                }
            ],
        }
    )

    row = table.iloc[0].to_dict()

    assert row["market_event_state"] == "Evento macro activo"
    assert row["market_event_action"] == "No abrir entrada nueva durante ventana macro."
    assert row["focus_priority"] == 0


def test_trade_decision_card_status_requires_external_confirmation_for_fallback():
    status = trade_decision_card_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "stop": 97.0,
            "data_bucket": "Fallback",
            "data_state": "Fallback publico",
            "data_gate": "NO_TRADE_FROM_PUBLIC_PRICE",
            "data_source_action": "Confirmar en Alpaca/TradingView antes de entrada paper/manual.",
        }
    )

    assert status["action"] == "Confirmar externo"
    assert status["tone"] == "watch"
    assert "fallback" in status["reason"].lower()
    assert "TradingView" in status["next_step"]


def test_trade_decision_card_status_blocks_negative_strategy_source_memory():
    status = trade_decision_card_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "stop": 97.0,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
            "strategy_source_memory_bias": "Memoria setup+fuente negativa",
            "strategy_source_memory_action": "Bajar prioridad: esta estrategia con esta fuente fallo en paper.",
        }
    )

    assert status["action"] == "No operar"
    assert status["tone"] == "avoid"
    assert "estrategia + fuente" in status["reason"]
    assert "Bajar prioridad" in status["next_step"]


def test_crypto_context_memory_bias_labels_positive_negative_and_learning():
    positive = crypto_context_memory_bias_from_summary_row(
        {
            "symbol": "BTC/USD",
            "timeframe": "1h",
            "strategy_family": "Pullback",
            "data_source": "Binance",
            "tracked": 4,
            "hit_2_rate": 0.75,
            "hit_5_rate": 0.25,
            "hit_10_rate": 0.0,
            "stop_rate": 0.25,
            "open": 1,
        }
    )
    negative = crypto_context_memory_bias_from_summary_row(
        {
            "symbol": "ETH/USD",
            "timeframe": "15m",
            "strategy_family": "Breakout",
            "data_source": "CoinGecko",
            "tracked": 5,
            "hit_2_rate": 0.2,
            "stop_rate": 0.6,
        }
    )
    learning = crypto_context_memory_bias_from_summary_row(
        {
            "symbol": "SOL/USD",
            "timeframe": "1h",
            "strategy_family": "Pullback",
            "data_source": "CoinGecko",
            "tracked": 2,
            "hit_2_rate": 1.0,
            "stop_rate": 0.0,
        }
    )

    assert positive["label"] == "Memoria crypto positiva"
    assert positive["priority_delta"] == 1
    assert negative["label"] == "Memoria crypto negativa"
    assert negative["priority_delta"] == -1
    assert learning["label"] == "Aprendiendo crypto"


def test_crypto_context_memory_bias_for_opportunity_uses_exact_and_fallback_context():
    lookup = crypto_context_memory_lookup_from_summary(
        [
            {
                "symbol": "BTC/USD",
                "timeframe": "1h",
                "strategy_family": "Pullback",
                "data_source": "Binance",
                "tracked": 4,
                "hit_2_rate": 0.75,
                "hit_5_rate": 0.25,
                "hit_10_rate": 0.0,
                "stop_rate": 0.25,
                "open": 0,
            }
        ]
    )

    exact = crypto_context_memory_bias_for_opportunity(
        {
            "symbol": "BTC/USD",
            "market": "crypto",
            "timeframe": "1h",
            "strategy_family": "Pullback",
            "data_bucket": "Live real",
            "data_source": "Binance",
        },
        lookup,
    )
    source_fallback = crypto_context_memory_bias_for_opportunity(
        {
            "symbol": "BTC/USD",
            "market": "crypto",
            "timeframe": "1h",
            "strategy_family": "Pullback",
            "data_bucket": "Live real",
            "data_source": "Coinbase",
        },
        lookup,
    )
    stock = crypto_context_memory_bias_for_opportunity({"symbol": "AAPL", "market": "stock"}, lookup)

    assert exact["label"] == "Memoria crypto positiva"
    assert source_fallback["label"] == "Memoria crypto positiva"
    assert stock["label"] == "No aplica crypto"


def test_trade_decision_card_status_waits_on_negative_crypto_memory():
    status = trade_decision_card_status(
        {
            "symbol": "BTC/USD",
            "market": "crypto",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 100.0,
            "stop": 97.0,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
            "crypto_context_memory_bias": "Memoria crypto negativa",
            "crypto_context_memory_action": "Bajar prioridad: este contexto crypto fallo en paper.",
        }
    )

    assert status["action"] == "Esperar"
    assert status["tone"] == "watch"
    assert "memoria crypto" in status["reason"].lower()
    assert "Bajar prioridad" in status["next_step"]


def test_trade_decision_card_status_waits_on_negative_backtest_memory():
    status = trade_decision_card_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 100.0,
            "stop": 97.0,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
            "backtest_memory_bias": "Backtest negativo",
            "backtest_memory_action": "Bajar prioridad: historicamente este setup/timeframe fue debil.",
        }
    )

    assert status["action"] == "Esperar"
    assert status["tone"] == "watch"
    assert "backtest" in status["reason"].lower()
    assert "Bajar prioridad" in status["next_step"]


def test_trade_decision_card_status_waits_when_tradingview_contradicts():
    status = trade_decision_card_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 100.0,
            "current_price": 100.0,
            "stop": 97.0,
            "data_bucket": "Live real",
            "data_gate": "LIVE_PRICE_OK",
            "tradingview_confirmation": "TradingView contradice",
            "tradingview_confirmation_action": "Esperar: webhook TradingView contradice o marca salida.",
        }
    )

    assert status["action"] == "Esperar"
    assert status["tone"] == "watch"
    assert "tradingview" in status["reason"].lower()
    assert "contradice" in status["next_step"]


def test_trade_decision_card_status_blocks_missing_contract():
    status = trade_decision_card_status(
        {
            "symbol": "MSFT",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 200.0,
            "stop": 195.0,
            "data_bucket": "Sin contrato",
            "data_gate": "-",
        }
    )

    assert status["action"] == "No operar"
    assert status["tone"] == "avoid"
    assert "contrato" in status["reason"]


def test_opportunity_ranking_score_prefers_live_positive_memory_over_fallback():
    live = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "ALERT",
        "signal": "BUY",
        "decision": "TRADE_FOR_2PCT",
        "entry": 100,
        "stop": 97,
        "ai_score": 80,
        "readiness": 82,
        "risk_pct": 0.02,
        "data_bucket": "Live real",
        "data_gate": "LIVE_PRICE_OK",
        "source_memory_bias": "Memoria fuente positiva",
        "strategy_source_memory_bias": "Memoria setup+fuente positiva",
    }
    fallback = {
        **live,
        "symbol": "MSFT",
        "data_bucket": "Fallback",
        "data_gate": "NO_TRADE_FROM_PUBLIC_PRICE",
        "source_memory_bias": "Aprendiendo",
        "strategy_source_memory_bias": "Aprendiendo setup+fuente",
    }

    assert opportunity_ranking_score(live) > opportunity_ranking_score(fallback)


def test_opportunity_ranking_score_prefers_entry_zone_over_chasing():
    in_zone = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "ALERT",
        "signal": "BUY",
        "decision": "TRADE_FOR_2PCT",
        "entry": 100,
        "current_price": 100.1,
        "stop": 98,
        "ai_score": 80,
        "readiness": 82,
        "risk_pct": 0.02,
        "data_bucket": "Live real",
        "data_gate": "LIVE_PRICE_OK",
    }
    chasing = {**in_zone, "symbol": "MSFT", "current_price": 102.0}

    assert opportunity_ranking_score(in_zone) > opportunity_ranking_score(chasing)


def test_opportunity_ranking_score_penalizes_negative_crypto_memory():
    positive = {
        "symbol": "BTC/USD",
        "market": "crypto",
        "action": "ALERT",
        "signal": "BUY",
        "decision": "TRADE_FOR_2PCT",
        "entry": 100,
        "current_price": 100,
        "stop": 98,
        "ai_score": 80,
        "readiness": 82,
        "risk_pct": 0.02,
        "data_bucket": "Live real",
        "data_gate": "LIVE_PRICE_OK",
        "crypto_context_memory_bias": "Memoria crypto positiva",
    }
    negative = {**positive, "symbol": "ETH/USD", "crypto_context_memory_bias": "Memoria crypto negativa"}

    assert opportunity_ranking_score(positive) > opportunity_ranking_score(negative)


def test_opportunity_ranking_score_rewards_positive_backtest_memory():
    positive = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "ALERT",
        "signal": "BUY",
        "decision": "TRADE_FOR_2PCT",
        "entry": 100,
        "current_price": 100,
        "stop": 98,
        "ai_score": 80,
        "readiness": 82,
        "risk_pct": 0.02,
        "data_bucket": "Live real",
        "data_gate": "LIVE_PRICE_OK",
        "backtest_memory_bias": "Backtest positivo",
    }
    negative = {**positive, "symbol": "MSFT", "backtest_memory_bias": "Backtest negativo"}

    assert opportunity_ranking_score(positive) > opportunity_ranking_score(negative)


def test_opportunity_ranking_score_rewards_tradingview_confirmation():
    positive = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "ALERT",
        "signal": "BUY",
        "decision": "TRADE_FOR_2PCT",
        "entry": 100,
        "current_price": 100,
        "stop": 98,
        "ai_score": 80,
        "readiness": 82,
        "risk_pct": 0.02,
        "data_bucket": "Live real",
        "data_gate": "LIVE_PRICE_OK",
        "tradingview_confirmation": "TradingView confirma",
    }
    negative = {**positive, "symbol": "MSFT", "tradingview_confirmation": "TradingView contradice"}

    assert opportunity_ranking_score(positive) > opportunity_ranking_score(negative)


def test_focused_opportunity_table_adds_crypto_context_memory_from_brief_summary():
    table = focused_opportunity_table(
        {
            "crypto_context_memory_summary": [
                {
                    "symbol": "BTC/USD",
                    "timeframe": "1h",
                    "strategy_family": "Pullback",
                    "data_source": "Binance",
                    "tracked": 4,
                    "hit_2_rate": 0.75,
                    "hit_5_rate": 0.25,
                    "hit_10_rate": 0.0,
                    "stop_rate": 0.25,
                    "open": 0,
                }
            ],
            "opportunities": [
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "ai_action": "ALERT",
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "entry": 100,
                    "current_price": 100,
                    "stop": 98,
                    "ai_score": 80,
                    "alert_readiness_score": 82,
                    "risk_pct": 0.02,
                    "timeframe": "1h",
                    "strategy_family": "Pullback",
                    "data_bucket": "Live real",
                    "data_source": "Binance",
                }
            ],
        }
    )

    row = table.iloc[0].to_dict()

    assert row["crypto_context_memory_bias"] == "Memoria crypto positiva"
    assert row["crypto_context_memory_action"].startswith("Subir prioridad")
    assert row["timeframe"] == "1h"


def test_opportunity_ranking_rows_orders_live_positive_before_negative_and_missing_contract():
    table = pd.DataFrame(
        [
            {
                "symbol": "MISS",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 200,
                "stop": 195,
                "ai_score": 99,
                "readiness": 99,
                "risk_pct": 0.01,
                "data_bucket": "Sin contrato",
                "strategy_source_memory_bias": "Aprendiendo setup+fuente",
            },
            {
                "symbol": "GOOD",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 100,
                "current_price": 100,
                "stop": 99,
                "ai_score": 80,
                "readiness": 82,
                "risk_pct": 0.02,
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_gate": "LIVE_PRICE_OK",
                "source_memory_bias": "Memoria fuente positiva",
                "strategy_source_memory_bias": "Memoria setup+fuente positiva",
            },
            {
                "symbol": "BAD",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 120,
                "stop": 116,
                "ai_score": 95,
                "readiness": 96,
                "risk_pct": 0.02,
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_gate": "LIVE_PRICE_OK",
                "source_memory_bias": "Memoria fuente positiva",
                "strategy_source_memory_bias": "Memoria setup+fuente negativa",
            },
        ]
    )

    rows = opportunity_ranking_rows(table, limit=3)

    assert rows.iloc[0]["Ticker"] == "GOOD"
    assert rows.iloc[-1]["Ticker"] == "MISS"
    assert rows.iloc[0]["Accion"] == "Entrar paper/manual"
    assert "Abrir plan" not in rows.iloc[0]["Activo"]


def test_opportunity_ranking_rows_includes_levels_memory_and_links():
    table = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 100,
                "current_price": 100,
                "stop": 97,
                "ai_score": 80,
                "readiness": 82,
                "risk_pct": 0.02,
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_gate": "LIVE_PRICE_OK",
                "strategy_source_memory_bias": "Memoria setup+fuente positiva",
            }
        ]
    )

    row = opportunity_ranking_rows(table, limit=1).iloc[0].to_dict()

    assert row["Entrada"] == 100
    assert row["Zona entrada"] == "99.8000 - 100.30"
    assert row["Estado entrada"] == "Entrada en zona"
    assert row["Distancia entrada"] == 0
    assert row["Stop"] == 97
    assert row["Target 2%"] == 102
    assert round(row["R:R 2%"], 2) == 0.67
    assert "15m" in row["Confirmacion"]
    assert row["Memoria setup+fuente"] == "Memoria setup+fuente positiva"
    assert row["Activo"].startswith("?view=Activo&symbol=AAPL")
    assert row["TradingView"].endswith("symbol=AAPL")


def test_opportunity_ranking_prefers_best_budget_fit_for_small_account():
    table = pd.DataFrame(
        [
            {
                "symbol": "HIGH",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 100,
                "current_price": 100,
                "stop": 95,
                "ai_score": 90,
                "readiness": 90,
                "risk_pct": 0.02,
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_gate": "LIVE_PRICE_OK",
                "strategy_source_memory_bias": "Memoria setup+fuente positiva",
            },
            {
                "symbol": "FIT",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 10,
                "current_price": 10,
                "stop": 9.95,
                "ai_score": 90,
                "readiness": 90,
                "risk_pct": 0.02,
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_gate": "LIVE_PRICE_OK",
                "strategy_source_memory_bias": "Memoria setup+fuente positiva",
            },
        ]
    )

    rows = opportunity_ranking_rows(table, limit=2, account_equity=100, risk_pct=0.01)

    assert rows.iloc[0]["Ticker"] == "FIT"
    assert rows.iloc[0]["Capital fit"] == "Cabe"
    assert rows.iloc[0]["Producto"] == "Accion"
    assert rows.iloc[0]["Ganancia 2% $"] > rows.iloc[1]["Ganancia 2% $"]


def test_opportunity_budget_fit_blocks_missing_stop_for_small_account():
    fit = opportunity_budget_fit(
        {
            "symbol": "NOSTOP",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 25,
            "current_price": 25,
            "ai_score": 92,
            "readiness": 91,
            "data_bucket": "Live real",
        },
        account_equity=100,
        risk_pct=0.01,
    )

    assert fit["allowed"] is False
    assert fit["recommendation"] == "Solo paper"
    assert "stop" in fit["message"].lower()


def test_budget_recommendation_rows_groups_by_account_fit():
    table = pd.DataFrame(
        [
            {
                "symbol": "WHOLE",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 10,
                "current_price": 10,
                "stop": 9.95,
                "ai_score": 88,
                "readiness": 90,
                "risk_pct": 0.02,
                "data_bucket": "Live real",
            },
            {
                "symbol": "FRAC",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 250,
                "current_price": 250,
                "stop": 249,
                "ai_score": 95,
                "readiness": 95,
                "risk_pct": 0.02,
                "data_bucket": "Live real",
            },
            {
                "symbol": "WAIT",
                "market": "stock",
                "action": "WATCH",
                "signal": "WATCH",
                "decision": "WAIT",
                "entry": 20,
                "current_price": 20,
                "ai_score": 80,
                "readiness": 70,
                "data_bucket": "Live real",
            },
        ]
    )

    rows = budget_recommendation_rows(table, account_equity=100, risk_pct=0.01, limit=3)

    assert rows.iloc[0]["symbol"] == "WHOLE"
    assert rows.iloc[0]["bucket"] == "Operable"
    assert rows.iloc[1]["bucket"] == "Presupuesto pequeño"
    assert rows.iloc[2]["bucket"] == "Solo vigilar"
    assert rows.iloc[0]["capital_used"] <= 100
    assert rows.iloc[0]["risk_dollars"] <= 1.01


def test_budget_expectancy_status_calculates_expected_r_for_small_account():
    status = budget_expectancy_status(
        {
            "symbol": "EVOK",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 10,
            "current_price": 10,
            "stop": 9.95,
            "target_price": 10.2,
            "ai_score": 88,
            "readiness": 92,
            "data_bucket": "Live real",
            "strategy_source_memory_bias": "Memoria setup+fuente positiva",
            "backtest_memory_bias": "Backtest positivo",
        },
        account_equity=100,
        risk_pct=0.01,
    )

    assert status["lane"] == "Mejor uso"
    assert status["budget"]["allowed"] is True
    assert status["expected_r"] > 1.0
    assert status["expected_value"] > 0
    assert status["quality_label"] in {"Alta", "Media"}


def test_budget_expectancy_status_penalizes_bad_liquidity_and_stale_price():
    good = {
        "symbol": "GOOD",
        "market": "stock",
        "action": "ALERT",
        "signal": "BUY",
        "decision": "TRADE_FOR_2PCT",
        "entry": 20,
        "current_price": 20,
        "stop": 19.8,
        "target_price": 20.4,
        "ai_score": 88,
        "readiness": 90,
        "data_bucket": "Live real",
        "relative_volume": 1.8,
        "spread_pct": 0.01,
        "strategy_source_memory_bias": "Memoria setup+fuente positiva",
    }
    weak = {
        **good,
        "symbol": "WEAK",
        "data_bucket": "Fallback",
        "freshness": "STALE",
        "relative_volume": 0.32,
        "spread_pct": 0.16,
        "stop": 18.8,
        "strategy_source_memory_bias": "Memoria setup+fuente negativa",
    }

    good_status = budget_expectancy_status(good, account_equity=100, risk_pct=0.01)
    weak_status = budget_expectancy_status(weak, account_equity=100, risk_pct=0.01)

    assert good_status["budget_score"] > weak_status["budget_score"]
    assert good_status["win_probability"] > weak_status["win_probability"]
    assert weak_status["quality_label"] == "Baja"
    assert any("spread" in reason for reason in weak_status["quality_reasons"])


def test_budget_strategy_allocation_rows_prioritizes_capital_efficiency():
    table = pd.DataFrame(
        [
            {
                "symbol": "EXPENSIVE",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 400,
                "current_price": 400,
                "stop": 397,
                "target_price": 408,
                "ai_score": 96,
                "readiness": 96,
                "data_bucket": "Live real",
            },
            {
                "symbol": "EFFICIENT",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 20,
                "current_price": 20,
                "stop": 19.9,
                "target_price": 20.4,
                "ai_score": 88,
                "readiness": 90,
                "data_bucket": "Live real",
                "strategy_source_memory_bias": "Memoria setup+fuente positiva",
            },
            {
                "symbol": "NOSTOP",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 15,
                "current_price": 15,
                "ai_score": 95,
                "readiness": 95,
                "data_bucket": "Live real",
            },
        ]
    )

    rows = budget_strategy_allocation_rows(table, account_equity=100, risk_pct=0.01, limit=3)

    assert rows.iloc[0]["symbol"] == "EFFICIENT"
    assert rows.iloc[0]["lane"] == "Mejor uso"
    assert rows.iloc[0]["expected_value"] > 0
    assert rows[rows["symbol"] == "NOSTOP"].iloc[0]["lane"] == "Solo vigilar"


def test_budget_filtered_opportunity_table_limits_by_scope_and_max_trades():
    table = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 20,
                "current_price": 20,
                "stop": 19.9,
                "target_price": 20.4,
                "ai_score": 90,
                "readiness": 92,
                "data_bucket": "Live real",
            },
            {
                "symbol": "BTC/USD",
                "market": "crypto",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 100,
                "current_price": 100,
                "stop": 99.5,
                "target_price": 102,
                "ai_score": 95,
                "readiness": 95,
                "data_bucket": "Live real",
            },
            {
                "symbol": "TSLA",
                "market": "stock",
                "product": "Opcion",
                "option": {"contractSymbol": "TSLA260717C00400000", "max_loss_per_contract": 0.8},
                "action": "WATCH",
                "signal": "BUY",
                "decision": "WATCH",
                "entry": 3,
                "current_price": 3,
                "stop": 2.98,
                "target_price": 3.3,
                "ai_score": 80,
                "readiness": 75,
                "data_bucket": "Live real",
            },
        ]
    )

    stock_rows = budget_filtered_opportunity_table(
        table, account_equity=100, risk_pct=0.01, market_scope="Acciones", max_trades=1
    )
    crypto_rows = budget_filtered_opportunity_table(
        table, account_equity=100, risk_pct=0.01, market_scope="Crypto", max_trades=2
    )
    option_rows = budget_filtered_opportunity_table(
        table, account_equity=100, risk_pct=0.01, market_scope="Opciones", max_trades=2
    )

    assert len(stock_rows) == 1
    assert stock_rows.iloc[0]["symbol"] == "AAPL"
    assert crypto_rows["symbol"].tolist() == ["BTC/USD"]
    assert option_rows["symbol"].tolist() == ["TSLA"]


def test_budget_filtered_opportunity_table_expands_when_capital_can_cover_risk():
    table = pd.DataFrame(
        [
            {
                "symbol": "TSLA",
                "market": "stock",
                "product": "Opcion",
                "option": {"contractSymbol": "TSLA260717C00400000", "max_loss_per_contract": 4.0},
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 4.0,
                "current_price": 4.0,
                "stop": 3.96,
                "target_price": 4.4,
                "ai_score": 92,
                "readiness": 94,
                "data_bucket": "Live real",
                "relative_volume": 1.6,
                "spread_pct": 0.01,
            }
        ]
    )

    small_budget = budget_filtered_opportunity_table(
        table, account_equity=100, risk_pct=0.01, market_scope="Opciones", max_trades=3
    )
    larger_budget = budget_filtered_opportunity_table(
        table, account_equity=500, risk_pct=0.01, market_scope="Opciones", max_trades=3
    )

    assert small_budget.empty
    assert larger_budget["symbol"].tolist() == ["TSLA"]


def test_budget_wide_search_rows_keeps_stocks_and_crypto_visible_for_small_budget():
    table = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 295,
                "current_price": 295,
                "stop": 293,
                "target_price": 301,
                "ai_score": 93,
                "readiness": 92,
                "data_bucket": "Live real",
                "relative_volume": 1.7,
                "spread_pct": 0.01,
            },
            {
                "symbol": "BTC/USD",
                "market": "crypto",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 66000,
                "current_price": 66000,
                "stop": 65400,
                "target_price": 67320,
                "ai_score": 91,
                "readiness": 90,
                "data_bucket": "Live real",
                "relative_volume": 1.5,
                "spread_pct": 0.002,
            },
            {
                "symbol": "NOISE",
                "market": "stock",
                "action": "WATCH",
                "signal": "AVOID",
                "decision": "NO_TRADE",
                "entry": 20,
                "current_price": 20,
                "stop": 19,
                "target_price": 20.4,
                "ai_score": 30,
                "readiness": 20,
                "data_bucket": "Fallback",
            },
        ]
    )

    rows = budget_wide_search_rows(table, account_equity=50, risk_pct=0.01, market_scope="Todos", limit=4)

    assert {"stock", "crypto"}.issubset(set(rows["market"]))
    assert "NOISE" not in rows.head(2)["symbol"].tolist()
    assert set(rows["symbol"]).issuperset({"AAPL", "BTC/USD"})


def test_budget_wide_search_rows_uses_fallback_candidates_for_budget_watchlist():
    table = focused_opportunity_table(
        {
            "opportunities": [],
            "crypto_scan_candidates": [
                {
                    "symbol": "SOL/USD",
                    "market": "crypto",
                    "ai_action": "WATCH",
                    "signal": "BUY",
                    "trade_decision": "WAIT_FOR_TRIGGER",
                    "entry": 71.87,
                    "stop": 71.08,
                    "confluence_score": 85,
                    "trigger_score": 85,
                    "relative_volume_15m": 1.4,
                    "data_bucket": "Sin contrato",
                }
            ],
        }
    )

    rows = budget_wide_search_rows(table, account_equity=600, risk_pct=0.01, market_scope="Todos", limit=4)

    assert not rows.empty
    assert rows.iloc[0]["symbol"] == "SOL/USD"
    assert rows.iloc[0]["capital_used"] <= 600
    assert bool(rows.iloc[0]["budget_allowed"]) is True


def test_opportunity_budget_fit_caps_crypto_position_to_account_equity():
    row = {
        "symbol": "DOGE/USD",
        "market": "crypto",
        "action": "WATCH",
        "signal": "BUY",
        "decision": "WAIT_FOR_TRIGGER",
        "entry": 0.08197,
        "current_price": 0.08197,
        "stop": 0.0819685,
        "target_price": 0.08361,
        "ai_score": 70,
        "readiness": 70,
        "data_bucket": "Live real",
    }

    budget = opportunity_budget_fit(row, account_equity=600, risk_pct=0.01)

    assert budget["notional"] <= 600.01
    assert budget["risk_dollars"] < budget["risk_budget"]
    assert "capado por capital" in budget["message"]


def test_budget_trade_plan_rows_returns_qty_targets_and_verdict():
    table = pd.DataFrame(
        [
            {
                "symbol": "EFFICIENT",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 20,
                "current_price": 20,
                "stop": 19.9,
                "target_price": 20.4,
                "target_5": 21,
                "ai_score": 90,
                "readiness": 94,
                "data_bucket": "Live real",
                "strategy_source_memory_bias": "Memoria setup+fuente positiva",
            }
        ]
    )

    rows = budget_trade_plan_rows(table, account_equity=100, risk_pct=0.01, market_scope="Todos", max_trades=3)

    assert len(rows) == 1
    row = rows.iloc[0]
    assert row["symbol"] == "EFFICIENT"
    assert row["qty"] > 0
    assert row["entry"] == 20
    assert row["stop"] == 19.9
    assert row["target_1"] == 20.4
    assert row["risk_dollars"] <= 1.01
    assert row["reward_1_dollars"] > 0
    assert "Vale la pena" in row["verdict"]


def test_budget_top_trade_rows_returns_ranked_top_three():
    table = pd.DataFrame(
        [
            {
                "symbol": "BEST",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 20,
                "current_price": 20,
                "stop": 19.9,
                "target_price": 20.4,
                "ai_score": 95,
                "readiness": 96,
                "data_bucket": "Live real",
                "relative_volume": 1.9,
                "spread_pct": 0.01,
            },
            {
                "symbol": "ALT",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 25,
                "current_price": 25,
                "stop": 24.85,
                "target_price": 25.5,
                "ai_score": 90,
                "readiness": 90,
                "data_bucket": "Live real",
                "relative_volume": 1.2,
                "spread_pct": 0.02,
            },
            {
                "symbol": "WAIT",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 12,
                "current_price": 12,
                "stop": 11.94,
                "target_price": 12.24,
                "ai_score": 82,
                "readiness": 80,
                "data_bucket": "Live real",
                "relative_volume": 0.9,
                "spread_pct": 0.03,
            },
            {
                "symbol": "EXTRA",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 15,
                "current_price": 15,
                "stop": 14.9,
                "target_price": 15.3,
                "ai_score": 80,
                "readiness": 78,
                "data_bucket": "Fallback",
                "relative_volume": 0.4,
                "spread_pct": 0.15,
            },
        ]
    )

    rows = budget_top_trade_rows(table, account_equity=100, risk_pct=0.01, market_scope="Acciones", max_trades=3)

    assert rows["rank"].tolist() == [1, 2, 3]
    assert rows["rank_label"].tolist() == ["Mejor oportunidad", "Alternativa", "Solo si confirma"]
    assert "EXTRA" not in rows["symbol"].tolist()
    assert rows.iloc[0]["symbol"] == "BEST"
    assert rows.iloc[0]["stage"] == "OPERAR_AHORA"
    assert rows.iloc[0]["stage_label"] == "Operar ahora"


def test_budget_execution_stage_separates_ready_wait_and_no_trade():
    ready = budget_expectancy_status(
        {
            "symbol": "READY",
            "market": "stock",
            "action": "ALERT",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 20,
            "current_price": 20,
            "stop": 19.9,
            "target_price": 20.4,
            "ai_score": 95,
            "readiness": 96,
            "data_bucket": "Live real",
            "relative_volume": 1.8,
            "spread_pct": 0.01,
        },
        account_equity=100,
        risk_pct=0.01,
    )
    wait = budget_expectancy_status(
        {
            "symbol": "WAIT",
            "market": "stock",
            "action": "WATCH",
            "signal": "WATCH",
            "decision": "WAIT",
            "entry": 20,
            "current_price": 20,
            "stop": 19.8,
            "target_price": 20.4,
            "ai_score": 86,
            "readiness": 76,
            "data_bucket": "Live real",
            "relative_volume": 1.4,
        },
        account_equity=100,
        risk_pct=0.01,
    )
    avoid = budget_expectancy_status(
        {
            "symbol": "AVOID",
            "market": "stock",
            "action": "WATCH",
            "signal": "WATCH",
            "decision": "WAIT",
            "entry": 200,
            "current_price": 200,
            "stop": 170,
            "target_price": 204,
            "ai_score": 70,
            "readiness": 55,
            "data_bucket": "Fallback",
            "relative_volume": 0.2,
            "spread_pct": 0.18,
        },
        account_equity=100,
        risk_pct=0.01,
    )

    assert budget_execution_stage(ready)["code"] == "OPERAR_AHORA"
    assert budget_execution_stage(wait)["code"] == "ESPERAR_CONFIRMACION"
    assert budget_execution_stage(avoid)["code"] == "NO_OPERAR"


def test_budget_top_trade_rows_prefers_waiting_setup_over_no_trade_noise():
    table = pd.DataFrame(
        [
            {
                "symbol": "NOISY",
                "market": "stock",
                "action": "WATCH",
                "signal": "WATCH",
                "decision": "WAIT",
                "entry": 200,
                "current_price": 200,
                "stop": 170,
                "target_price": 204,
                "ai_score": 98,
                "readiness": 80,
                "data_bucket": "Fallback",
                "relative_volume": 0.1,
                "spread_pct": 0.20,
            },
            {
                "symbol": "CLEAN",
                "market": "stock",
                "action": "WATCH",
                "signal": "WATCH",
                "decision": "WAIT",
                "entry": 20,
                "current_price": 20,
                "stop": 19.8,
                "target_price": 20.4,
                "ai_score": 82,
                "readiness": 72,
                "data_bucket": "Live real",
                "relative_volume": 1.2,
                "spread_pct": 0.02,
            },
        ]
    )

    rows = budget_top_trade_rows(table, account_equity=100, risk_pct=0.01, market_scope="Acciones", max_trades=1)

    assert rows.iloc[0]["symbol"] == "CLEAN"
    assert rows.iloc[0]["stage"] == "ESPERAR_CONFIRMACION"


def test_opportunity_data_confidence_status_flags_mixed_price_and_chart_sources():
    status = opportunity_data_confidence_status(
        {
            "symbol": "AAPL",
            "market": "stock",
            "data_bucket": "Live real",
            "live_price_contract": {
                "gate": "LIVE_PRICE_OK",
                "source_label": "Alpaca IEX",
                "source_mode": "BROKER_DATA",
                "candle_phase_label": "LIVE",
            },
            "chart_data_contract": {
                "gate": "LIVE_DATA_OK",
                "source_label": "yfinance fallback",
                "source_mode": "PUBLIC_MARKET_DATA",
                "freshness_status": "OK",
            },
        }
    )

    assert status["label"] == "Fuentes mixtas"
    assert status["tone"] == "watch"
    assert status["mixed_sources"] is True
    assert status["score"] <= 60
    assert "Alpaca IEX" in status["detail"]
    assert "yfinance fallback" in status["detail"]


def test_opportunity_ranking_score_prioritizes_aligned_live_data_over_fallback():
    aligned = {
        "symbol": "LIVE",
        "market": "stock",
        "action": "ALERT",
        "signal": "BUY",
        "decision": "TRADE_FOR_2PCT",
        "entry": 20,
        "current_price": 20,
        "stop": 19.9,
        "target_price": 20.4,
        "ai_score": 82,
        "readiness": 82,
        "data_bucket": "Live real",
        "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX", "source_mode": "BROKER_DATA"},
        "chart_data_contract": {"gate": "LIVE_DATA_OK", "source_label": "Alpaca IEX", "source_mode": "BROKER_DATA"},
    }
    fallback = {
        **aligned,
        "symbol": "FALLBACK",
        "ai_score": 96,
        "readiness": 96,
        "data_bucket": "Fallback",
        "live_price_contract": {
            "gate": "NO_TRADE_FROM_PUBLIC_PRICE",
            "source_label": "yfinance 1m",
            "source_mode": "PUBLIC_MARKET_DATA",
        },
        "chart_data_contract": {
            "gate": "NO_TRADE_FROM_PUBLIC_PRICE",
            "source_label": "yfinance 1m",
            "source_mode": "PUBLIC_MARKET_DATA",
        },
    }

    assert opportunity_ranking_score(aligned, account_equity=100, risk_pct=0.01) > opportunity_ranking_score(
        fallback, account_equity=100, risk_pct=0.01
    )


def test_opportunity_ranking_rows_exposes_data_confidence_detail():
    table = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "stock",
                "action": "ALERT",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 20,
                "current_price": 20,
                "stop": 19.9,
                "target_price": 20.4,
                "ai_score": 88,
                "readiness": 88,
                "data_bucket": "Live real",
                "live_price_contract": {
                    "gate": "LIVE_PRICE_OK",
                    "source_label": "Alpaca IEX",
                    "source_mode": "BROKER_DATA",
                },
                "chart_data_contract": {
                    "gate": "LIVE_DATA_OK",
                    "source_label": "Alpaca IEX",
                    "source_mode": "BROKER_DATA",
                },
            }
        ]
    )

    rows = opportunity_ranking_rows(table, account_equity=100, risk_pct=0.01, limit=1)

    assert rows.iloc[0]["Confianza datos"] == "Fuente alineada"
    assert "precio Alpaca IEX" in rows.iloc[0]["Detalle datos"]


def test_small_account_learning_rows_prioritizes_high_hit_low_stop():
    alpaca_summary = pd.DataFrame(
        [
            {
                "strategy_family": "Pullback",
                "tracked": 8,
                "hit_2_rate": 0.68,
                "stop_rate": 0.12,
            },
            {
                "strategy_family": "Breakout",
                "tracked": 7,
                "hit_2_rate": 0.18,
                "stop_rate": 0.58,
            },
        ]
    )

    rows = small_account_learning_rows(alpaca_summary=alpaca_summary, crypto_summary=pd.DataFrame(), limit=2)

    assert rows.iloc[0]["strategy"] == "Pullback"
    assert rows.iloc[0]["tone"] == "buy"
    assert rows[rows["strategy"] == "Breakout"].iloc[0]["tone"] == "avoid"


def test_alpaca_market_data_panel_rows_keep_real_orders_off_when_ready():
    rows = alpaca_market_data_panel_rows(
        {
            "status": "OK",
            "error_category": "",
            "configured": True,
            "credential_keys": ["ALPACA_API_KEY", "ALPACA_API_SECRET"],
            "feed": "IEX",
            "mode": "paper",
            "effective_endpoint": "https://paper-api.alpaca.markets",
            "endpoint_mismatch": False,
            "safe_for_signals": True,
            "live_orders_allowed": False,
            "paper_only": True,
            "summary": "Alpaca market data responde.",
            "next_action": "Usar como fuente broker read-only.",
        }
    )

    by_control = {row["Control"]: row for row in rows.to_dict("records")}
    assert by_control["Estado Alpaca"]["Estado"] == "OK"
    assert by_control["Feed"]["Estado"] == "IEX"
    assert by_control["Senales"]["Estado"] == "PERMITIDAS"
    assert by_control["Ordenes reales"]["Estado"] == "OFF"
    assert "no coloca ordenes" in by_control["Ordenes reales"]["Detalle"]


def test_alpaca_market_data_panel_rows_blocks_signals_on_auth_invalid():
    rows = alpaca_market_data_panel_rows(
        {
            "status": "FAIL",
            "error_category": "AUTH_INVALID",
            "configured": True,
            "credential_keys": ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
            "feed": "IEX",
            "mode": "paper",
            "effective_endpoint": "https://paper-api.alpaca.markets",
            "safe_for_signals": False,
            "live_orders_allowed": False,
            "paper_only": True,
            "summary": "Alpaca rechazo credenciales.",
            "next_action": "Rotar credenciales.",
        }
    )

    by_control = {row["Control"]: row for row in rows.to_dict("records")}
    assert by_control["Estado Alpaca"]["Detalle"] == "AUTH_INVALID"
    assert by_control["Credenciales"]["Estado"] == "CONFIGURADO"
    assert by_control["Senales"]["Estado"] == "BLOQUEADAS"
    assert by_control["Senales"]["_tone"] == "avoid"
    assert by_control["Ordenes reales"]["Estado"] == "OFF"


def test_prepare_options_view_adds_human_percent_columns():
    options = prepare_options_view(
        pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "contractSymbol": "AAPL260619C00200000",
                    "option_decision": "OPTION_CANDIDATE",
                    "option_score": "88",
                    "spread_pct": "0.12",
                    "breakeven_pct": "0.034",
                    "volume": "200",
                    "openInterest": "900",
                }
            ]
        )
    )

    assert options.loc[0, "spread_pct"] == 0.12
    assert options.loc[0, "spread_pct_display"] == 12.0
    assert options.loc[0, "breakeven_pct_display"] == 3.4000000000000004


def test_options_quality_chart_frame_filters_non_numeric_or_zero_liquidity_rows():
    view = pd.DataFrame(
        [
            {
                "contractSymbol": "AAPL260619C00200000",
                "spread_pct_display": None,
                "option_score": 80,
                "liquidity": 100,
            },
            {
                "contractSymbol": "AAPL260619C00210000",
                "spread_pct_display": 12.5,
                "option_score": 82,
                "liquidity": 0,
            },
            {
                "contractSymbol": "AAPL260619C00220000",
                "spread_pct_display": 9.5,
                "option_score": 88,
                "liquidity": 240,
            },
        ]
    )

    filtered = options_quality_chart_frame(view)

    assert filtered["contractSymbol"].tolist() == ["AAPL260619C00220000"]


def test_options_liquidity_chart_frame_skips_empty_value_bars():
    view = pd.DataFrame(
        [
            {"contractSymbol": "AAPL260619C00200000", "volume": None, "openInterest": 0},
            {"contractSymbol": "AAPL260619C00210000", "volume": 12, "openInterest": 30},
        ]
    )

    filtered = options_liquidity_chart_frame(view)

    assert filtered["contractSymbol"].tolist() == ["AAPL260619C00210000", "AAPL260619C00210000"]
    assert filtered["value"].tolist() == [12.0, 30.0]


def test_annotate_options_risk_budget_marks_contracts_that_do_not_fit_1r():
    options = pd.DataFrame(
        [
            {"contractSymbol": "AAPL260619C00100000", "max_loss_per_contract": 4},
            {"contractSymbol": "AAPL260619C00200000", "max_loss_per_contract": 150},
        ]
    )

    annotated = annotate_options_risk_budget(options, account_equity=500, risk_per_trade_pct=0.01)

    assert bool(annotated.loc[0, "fits_1r"]) is True
    assert annotated.loc[0, "small_account_label"] == "Cabe en 1R"
    assert bool(annotated.loc[1, "fits_1r"]) is False
    assert annotated.loc[1, "risk_multiple"] == 30
    assert annotated.loc[1, "small_account_label"] == "Solo paper / reducir riesgo"


def test_professional_options_feed_status_detects_configured_provider():
    basic = professional_options_feed_status({})
    ready = professional_options_feed_status({"POLYGON_API_KEY": "token"})

    assert basic["status"] == "BASIC"
    assert basic["source"] == "Yahoo/basic"
    assert ready["status"] == "READY"
    assert ready["source"] == "Polygon"


def test_annotate_professional_options_contracts_marks_greek_and_risk_readiness():
    options = pd.DataFrame(
        [
            {
                "contractSymbol": "AAPL260619C00200000",
                "side": "CALL",
                "strike": 200,
                "underlying_price": 198,
                "bid": 4.9,
                "ask": 5.0,
                "dte": 21,
                "spread_pct": 0.02,
                "volume": 500,
                "openInterest": 1200,
                "delta": 0.52,
                "gamma": 0.03,
                "theta": -0.04,
                "vega": 0.12,
                "fits_1r": True,
            },
            {
                "contractSymbol": "AAPL260619C00240000",
                "side": "CALL",
                "strike": 240,
                "underlying_price": 198,
                "bid": 1.0,
                "ask": 1.8,
                "dte": 60,
                "spread_pct": 0.50,
                "volume": 1,
                "openInterest": 2,
                "fits_1r": False,
            },
        ]
    )

    annotated = annotate_professional_options_contracts(options)

    assert annotated.loc[0, "professional_readiness"] == "Solo paper"
    assert annotated.loc[0, "max_loss_per_contract"] == 500
    assert annotated.loc[0, "breakeven_price"] == 205
    assert "Cabe en 1R" in annotated.loc[0, "professional_blockers"]
    assert annotated.loc[1, "professional_readiness"] == "Bloqueado"
    assert "Spread" in annotated.loc[1, "professional_blockers"]


def test_focused_opportunity_table_keeps_watch_above_avoid():
    brief = {
        "opportunities": [
            {
                "ai_action": "WATCH",
                "symbol": "MSFT",
                "market": "stock",
                "ai_score": 90,
                "signal": "AVOID",
                "trade_decision": "NO_TRADE",
            },
            {
                "ai_action": "WATCH",
                "symbol": "NVDA",
                "market": "stock",
                "ai_score": 70,
                "signal": "WATCH",
                "trade_decision": "WAIT",
            },
        ]
    }

    table = focused_opportunity_table(brief)

    assert table.iloc[0]["symbol"] == "NVDA"
    assert not opportunity_is_trade_ready(table.iloc[0].to_dict())
    assert "Esperar" in table.iloc[0]["waiting_for"]


def test_watch_movement_label_names_pullback_trigger():
    label = watch_movement_label(
        {
            "ai_action": "WATCH",
            "signal": "WATCH",
            "trade_decision": "WAIT",
            "trigger_setup": "PULLBACK",
            "trend_setup": "TREND_CONTINUATION",
        }
    )

    assert "SMA20/SMA40" in label
    assert "volumen" in label.lower()


def test_watch_movement_label_uses_smart_gate_movement():
    label = watch_movement_label(
        {
            "ai_action": "WATCH",
            "signal": "WATCH",
            "trade_decision": "WAIT",
            "alert_movement": "Esperar gatillo BUY en 15m mientras 1h sigue valido.",
        }
    )

    assert label == "Esperar gatillo BUY en 15m mientras 1h sigue valido."


def test_watch_movement_label_explains_buy_and_avoid():
    buy_label = watch_movement_label(
        {
            "ai_action": "ALERT",
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
        }
    )
    avoid_label = watch_movement_label(
        {
            "ai_action": "WATCH",
            "signal": "AVOID",
            "trade_decision": "NO_TRADE",
            "trigger_setup": "DOWNTREND",
        }
    )

    assert buy_label.startswith("BUY porque")
    assert "riesgo" in buy_label
    assert avoid_label.startswith("AVOID porque")
    assert "SMA200" in avoid_label


def test_opportunity_reason_and_change_label_explain_avoid():
    row = {
        "ai_action": "WATCH",
        "signal": "AVOID",
        "trade_decision": "NO_TRADE",
        "trigger_setup": "DOWNTREND",
        "trend_setup": "DOWNTREND",
    }

    reason = opportunity_reason_label(row)
    change = opportunity_change_label(row)

    assert reason.startswith("AVOID:")
    assert "bajista" in reason
    assert "recupera SMA200" in change


def test_focused_opportunity_table_adds_reason_columns_for_watchlist():
    brief = {
        "opportunities": [
            {
                "ai_action": "WATCH",
                "symbol": "NVDA",
                "market": "stock",
                "ai_score": 70,
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "risk_pct": 0.05,
                "recommended_target_pct": None,
                "alert_readiness_score": 55,
            }
        ]
    }

    table = focused_opportunity_table(brief)

    assert {"por_que", "cambia_si", "waiting_for", "confidence"}.issubset(table.columns)
    assert table.iloc[0]["por_que"].startswith("Esperar")


def test_platform_badge_rows_exposes_expected_platform_identity():
    rows = platform_badge_rows(env={})

    names = {row["name"] for row in rows}
    abbrs = {row["abbr"] for row in rows}

    assert {"Crypto.com", "Charles Schwab", "Webull"}.issubset(names)
    assert {"CRO", "CS", "WB"}.issubset(abbrs)
    assert all(row["mode"] for row in rows)


def test_study_guides_merge_lab_evidence():
    guides = study_guides_with_lab(
        [
            {
                "strategy_family": "Pullback",
                "lab_state": "Promote",
                "evidence_score": 0.73,
                "adaptive_weight": 1.2,
            }
        ]
    )

    pullback = next(row for row in guides if row["strategy"] == "Pullback")

    assert pullback["lab_state"] == "Promote"
    assert pullback["evidence_score"] == 0.73
    assert "SMA20/SMA40" in pullback["entry"]


def test_study_guides_include_masterclass_moving_average_training():
    names = study_strategy_names()
    guides = study_guides_with_lab([])
    masterclass = next(row for row in guides if row["strategy"] == "Masterclass de medias moviles")

    assert "Masterclass de medias moviles" in names
    assert names.count("Masterclass de medias moviles") == 1
    assert names.index("Masterclass de medias moviles") < names.index("Salto por cruce de EMA en horas")
    assert masterclass["direction"] == "structure"
    assert "SMA20/SMA40" in masterclass["works_when"]
    assert "SMA200" in masterclass["requirements_text"]
    assert {"15m", "1h", "4h", "1d"}.issubset(set(masterclass["confirmation_timeframes"]))


def test_study_example_rows_matches_strategy_from_confluence():
    confluence = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
                "confluence_score": 80,
            },
            {
                "symbol": "MSFT",
                "signal": "AVOID",
                "trade_decision": "NO_TRADE",
                "trigger_setup": "DOWNTREND",
                "confluence_score": 90,
            },
        ]
    )

    examples = study_example_rows(confluence, {"opportunities": []}, "Pullback")

    assert strategy_family_for_row(confluence.iloc[0].to_dict()) == "Pullback"
    assert examples["symbol"].tolist() == ["AAPL"]


def test_resolve_study_strategy_choice_prefers_lab_request():
    names = ["Canal alcista", "Pullback", "Tendencia bajista"]

    assert resolve_study_strategy_choice(names, "Canal alcista", requested="Pullback", current="Tendencia bajista") == "Pullback"
    assert resolve_study_strategy_choice(names, "Canal alcista", requested="Cruce", current="Tendencia bajista") == "Tendencia bajista"
    assert resolve_study_strategy_choice(names, "Canal alcista", requested="Cruce", current="Nada") == "Canal alcista"


def test_safe_key_makes_button_keys_stable():
    assert safe_key("Canal alcista / Pullback") == "canal_alcista_pullback"
    assert safe_key("") == "item"


def test_roxy_auto_altair_key_uses_stable_callsite():
    key = _roxy_auto_altair_key(inspect.currentframe())

    assert key.startswith("roxy_altair_test_focused_opportunities_")
    assert key.endswith(str(inspect.currentframe().f_lineno - 3))
    assert "test_roxy_auto_altair_key_uses_stable_callsite" in key


def test_chart_strategy_summary_explains_pullback_watch():
    chart_df = pd.DataFrame(
        [
            {
                "ts": pd.Timestamp("2026-06-07 10:00"),
                "close": 100,
                "sma20": 99,
                "sma40": 98,
                "sma200": 90,
            }
        ]
    )
    summary = chart_strategy_summary(
        {"setup": "PULLBACK", "entry": 100, "stop": 97, "sma20": 99, "sma40": 98},
        {"signal": "WATCH", "trade_decision": "WAIT", "trigger_setup": "PULLBACK", "risk_pct": 0.03},
        {"action": "WAIT", "decision": "Esperar"},
        chart_df,
    )

    assert summary["family"] == "Pullback"
    assert summary["tone"] == "watch"
    assert "SMA20/SMA40" in summary["movement"]


def test_compact_score_display_accepts_percent_and_score_domains():
    assert compact_score_display(0.72) == "72.00%"
    assert compact_score_display(70) == "70/100"
    assert compact_score_display(None) == "-"


def test_operational_chart_includes_live_tick_overlay():
    source = function_source_from_file("streamlit_app.py", "render_operational_chart_first")
    browser_source = function_source_from_file("streamlit_app.py", "render_browser_live_candle_chart")
    panel_source = function_source_from_file("streamlit_app.py", "render_browser_live_candle_chart_panel")
    payload_source = function_source_from_file("streamlit_app.py", "live_candle_chart_payload")

    assert "live_price:" in source
    assert "Tick live" in source
    assert "render_browser_live_candle_chart(" in source
    assert "fig.add_hline(" in source
    assert "markers+text" in source
    assert "2 GRAFICAS LIVE" in browser_source
    assert "TRADE_DESK_CHART_HEIGHT = 520" in Path("streamlit_app.py").read_text()
    assert "height: int = TRADE_DESK_CHART_HEIGHT" in browser_source
    assert "st.columns([1, 1]" in browser_source
    assert "render_browser_live_candle_chart_panel(" in browser_source
    assert "LightweightCharts.createChart" in panel_source
    assert "height: int = TRADE_DESK_CHART_HEIGHT" in panel_source
    assert "#roxy-live-chart { position:relative; z-index:1; height:100%; min-height:0;" in panel_source
    assert "Charts</b><b>WatchLists" in panel_source
    assert ".rlc-menu { display:none;" in panel_source
    assert "data-indicator=\"Labels\"" in panel_source
    assert "payload.defaultIndicators" in panel_source
    assert "const payloadLivePrice = finitePrice(payload.live && payload.live.price)" in panel_source
    assert "let currentLiveLinePrice = payloadLivePrice || latestCandleClose || 0" in panel_source
    assert "priceLineVisible: false" in panel_source
    assert "lastValueVisible: false" in panel_source
    assert "lineVisible: false" in panel_source
    assert 'liveLine.applyOptions({ title: labelsVisible ? "Tick live" : "", axisLabelVisible: true })' in panel_source
    assert "closeReferenceLine.applyOptions" in panel_source
    assert "window.lucide.createIcons" in panel_source
    assert "new WebSocket(url)" in panel_source
    assert "wss://stream.binance.us:9443" in payload_source
    assert "@kline_" in panel_source
    assert "openKlineSocket()" in panel_source
    assert "window.setInterval(pollTicker" in panel_source
    assert "candleSeries.update" in panel_source
    assert "api.binance.us/api/v3/ticker/price" in panel_source
    for tool in [
        'data-tool="trend"',
        'data-tool="horizontal"',
        'data-tool="rect"',
        'data-tool="channel"',
        'data-tool="fib"',
        'data-tool="arrow"',
        'data-tool="measure"',
        'data-tool="text"',
        'data-tool="eraser"',
        'data-tool="clear"',
    ]:
        assert tool in panel_source
    assert "localStorage.setItem(drawingKey" in panel_source


def test_trade_desk_prioritizes_chart_visibility_over_secondary_controls():
    chart_source = function_source_from_file("streamlit_app.py", "render_operational_chart_first")
    controls_source = function_source_from_file("streamlit_app.py", "render_command_center_controls")
    live_home_source = function_source_from_file("streamlit_app.py", "render_focused_home_live")
    compact_header_source = function_source_from_file("streamlit_app.py", "render_dashboard_compact_header")
    command_panel_source = function_source_from_file("streamlit_app.py", "render_command_center_panel")
    command_analysis_source = function_source_from_file("streamlit_app.py", "render_command_center_analysis")
    live_command_source = function_source_from_file("streamlit_app.py", "render_command_center_live_panel")
    top_budget_source = function_source_from_file("streamlit_app.py", "render_budget_top_trades_panel")
    budget_fit_source = function_source_from_file("streamlit_app.py", "render_budget_recommendation_strip")
    budget_plan_source = function_source_from_file("streamlit_app.py", "render_budget_trade_plan_panel")
    budget_split_source = function_source_from_file("streamlit_app.py", "render_budget_split_opportunities_panel")
    budget_market_cards_source = function_source_from_file("streamlit_app.py", "render_budget_market_cards")
    app_source = function_source_from_file("streamlit_app.py", "show_focused_roxy_app")

    assert chart_source.find("render_browser_live_candle_chart(") < chart_source.find("render_operational_trade_snapshot(")
    assert 'class="trade-desk-order-note"' in controls_source
    assert 'control_cols = st.columns([1.08, 0.62, 0.56, 0.72, 0.50], gap="small")' in controls_source
    assert 'with st.expander("Mas filtros de presupuesto y vista", expanded=False):' in controls_source
    assert controls_source.find('control_cols = st.columns([1.08, 0.62, 0.56, 0.72, 0.50], gap="small")') < controls_source.find(
        'with st.expander("Mas filtros de presupuesto y vista", expanded=False):'
    )
    assert 'with st.expander("Cambiar activo, mercado, timeframe y riesgo", expanded=False)' not in controls_source
    assert 'with st.expander("Plan detallado: confirmaciones, vigilancia y salidas", expanded=False)' in live_home_source
    assert 'with st.expander("Paper labs y medicion", expanded=False)' in live_home_source
    assert live_home_source.find('with st.expander("Paper labs y medicion", expanded=False)') < live_home_source.find("render_alpaca_paper_practice_lab(")
    assert 'with st.expander("Decision detallada: entrada, stop, salida e invalidacion", expanded=False)' in compact_header_source
    assert compact_header_source.find("render_dashboard_action_queue(table)") < compact_header_source.find("render_trade_decision_card(best)")
    assert 'class="command-quick-strip command-quick-strip-' in command_panel_source
    assert 'with st.expander("Detalles operativos: checklist, espera y validaciones", expanded=False)' in command_panel_source
    assert 'render_kpi_card("Esperamos", summary["movement"], tone="watch")' in command_panel_source
    assert command_analysis_source.find('with st.expander("Detalles: por que Roxy toma esta decision", expanded=False):') < command_analysis_source.find("render_operation_gate(trade_brief)")
    assert command_analysis_source.find("render_operation_gate(trade_brief)") < command_analysis_source.find("render_trade_plan_platform_preview(ticket)")
    assert 'if not render_side_panel:' in live_command_source
    assert live_command_source.find("if not render_side_panel:") < live_command_source.find("st.columns([1.6, 0.72])")
    assert live_command_source.find("render_symbol_context(symbol, market)") < live_command_source.find("st.columns([1.6, 0.72])")
    assert "compact-empty-budget" in top_budget_source
    assert "budget-empty-card" in top_budget_source
    assert "Sin entrada lista para tu presupuesto" in top_budget_source
    assert "if rows.empty:\n        return" in budget_fit_source
    assert "if rows.empty:\n        return" in budget_plan_source
    assert "has_budget_candidates = isinstance(budget_live_best, pd.DataFrame) and not budget_live_best.empty" in app_source
    assert "Acciones disponibles para trabajar" in budget_split_source
    assert "Criptomonedas disponibles para trabajar" in budget_split_source
    assert "Cargar en graficas" in budget_market_cards_source
    assert "render_budget_split_opportunities_panel(" in live_home_source
    assert "render_budget_split_opportunities_panel(" in app_source
    assert "render_budget_top_trades_panel(" not in live_home_source
    assert "render_budget_trade_plan_panel(" not in live_home_source
    assert "render_budget_top_trades_panel(" not in app_source
    assert "render_budget_trade_plan_panel(" not in app_source
    assert "render_budget_wide_search_panel(" in app_source


def test_live_chart_panel_keeps_bollinger_cloud_brand_and_nonblocking_tools():
    panel_source = function_source_from_file("streamlit_app.py", "render_browser_live_candle_chart_panel")

    assert 'id="rlc-bb-fill-layer"' in panel_source
    assert "drawBollingerCloud" in panel_source
    assert "BB Upper" in panel_source
    assert "BB Lower" in panel_source
    assert '"BBand": True' in function_source_from_file("streamlit_app.py", "live_candle_chart_payload")
    assert "chart.timeScale().subscribeVisibleTimeRangeChange" in panel_source
    assert ".rlc-body { position:relative; display:flex; flex:1 1 auto; min-height:0; flex-direction:column;" in panel_source
    assert ".rlc-toolbox { position:absolute; left:0; right:0; top:0; bottom:auto; display:flex;" in panel_source
    assert "pointer-events:auto;" in panel_source
    assert "border:1px solid rgba(226,232,240,.40)" in panel_source
    assert "border-left:1px solid rgba(226,232,240,.42)" not in panel_source
    assert 'ctx.fillStyle = "rgba(248,250,252,.035)"' in panel_source
    assert 'ctx.strokeStyle = "rgba(248,250,252,.30)"' in panel_source
    assert "#roxy-live-chart { position:relative; z-index:1;" in panel_source
    assert "#rlc-bb-fill-layer { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:0;" in panel_source
    assert "#rlc-drawing-layer.chart-pan-mode { pointer-events:none;" in panel_source
    assert "#rlc-drawing-layer.active, #rlc-drawing-layer.drawing-mode { pointer-events:auto;" in panel_source
    assert 'attributionLogo: false' in panel_source
    assert "handleScroll: { mouseWheel: true, pressedMouseMove: true" in panel_source
    assert "handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true }" in panel_source
    assert "navigateToTimeframe" in panel_source
    assert 'url.searchParams.set("tf", cleanTimeframe)' in panel_source
    assert 'link.target = "_parent"' in panel_source
    assert "targetWindow.document.createElement(\"script\")" not in panel_source
    assert "window.location.assign" in panel_source
    assert 'button.addEventListener("click", () => navigateToTimeframe(button.dataset.fasttf))' in panel_source
    assert 'data-fasttf="1m"' in panel_source
    assert 'data-fasttf="5m"' in panel_source
    assert 'data-fasttf="1w"' in panel_source
    assert 'data-indicator="Plan"' in panel_source
    assert 'data-indicator="Info"' in panel_source
    assert 'data-indicator="Scale"' in panel_source
    assert 'data-preset="naked"' in panel_source
    assert 'data-preset="clean"' in panel_source
    assert 'data-preset="full"' in panel_source
    assert "roxy-chart-settings:v4" in panel_source
    assert 'tabindex="0"' in panel_source
    assert 'chartWrap.addEventListener("keydown"' in panel_source
    assert 'key === "escape"' in panel_source
    assert "deleteDrawing(selectedDrawingIndex)" in panel_source
    assert "zoomChartFromCenter(1)" in panel_source
    assert "fitChartToContent()" in panel_source
    assert 'root.dataset.activeToolLabel = activeTool' in panel_source
    assert 'data-tool="select"' in panel_source
    assert 'title="Editar dibujos"' in panel_source
    assert 'const navigationTools = new Set(["cursor", "crosshair"])' in panel_source
    assert 'const drawingEditTools = new Set(["select", "eraser"])' in panel_source
    assert 'const drawingEditMode = drawingEditTools.has(activeTool)' in panel_source
    assert 'drawLayer.addEventListener("wheel"' in panel_source
    assert 'manualNavDrag = { pointerId: event.pointerId, x: event.clientX }' in panel_source
    assert 'if (navigationTools.has(activeTool)) return;' in panel_source
    assert 'node.setAttribute("pointer-events", preview ? "none" : "all")' in panel_source
    assert "smartAutoScaleRange" in panel_source
    assert "autoscaleInfoProvider" in panel_source
    assert "if (!indicatorSettings.Scale) return original()" in panel_source
    assert '[class*="tv-"]' not in panel_source
    assert '[class*="tradingview"]' not in panel_source
    assert "@media (max-width: 760px)" not in panel_source
    assert 'drawLayer.addEventListener("pointermove"' in panel_source
    assert "previewNode = addDrawingNode(shape, false, true)" in panel_source
    assert "coordinateToTime" in panel_source
    assert "coordinateToPrice" in panel_source
    assert "timeToCoordinate" in panel_source
    assert "priceToCoordinate" in panel_source
    assert "renderDrawings" in panel_source
    assert "requestAnimationFrame(renderDrawings)" in panel_source
    assert "version: 2" in panel_source
    assert 'id="rlc-hover-card"' in panel_source
    assert 'id="rlc-cursor-v"' in panel_source
    assert 'id="rlc-cursor-h"' in panel_source
    assert 'id="rlc-mode-badge"' in panel_source
    assert "NAV · rueda zoom · arrastra pan" in panel_source
    assert "DIBUJO · ${activeTool} · arrastra en la grafica" in panel_source
    assert 'data-action="pan-left"' in panel_source
    assert 'data-action="zoom-in"' in panel_source
    assert 'data-action="zoom-out"' in panel_source
    assert 'data-action="pan-right"' in panel_source
    assert "zoomChartFromCenter" in panel_source
    assert "panChartByFraction" in panel_source
    assert "root.dataset.drawingCount" in panel_source
    assert "root.dataset.activeTool" in panel_source
    assert 'toolbox.querySelectorAll("[data-tool]")' in panel_source
    assert 'toolbox.querySelectorAll("[data-action]")' in panel_source
    assert 'toolbox.querySelectorAll("[data-quicklevel]")' in panel_source
    assert 'toolbox.querySelectorAll("button[data-tool]")' not in panel_source
    assert ".rlc-toolbox button, .rlc-toolbox [data-tool], .rlc-toolbox [data-action], .rlc-toolbox [data-quicklevel]" in panel_source
    assert 'chartEl.addEventListener("pointermove"' in panel_source
    assert "showRoxyCursor(event)" in panel_source
    assert 'id="rlc-quote-line"' in panel_source
    assert ".rlc-quote-line { position:absolute;" in panel_source
    assert "candleChange" in panel_source
    assert "renderQuoteLine" in panel_source
    assert "renderQuoteLine(candles[candles.length - 1], \"Ultima vela\")" in panel_source
    assert "renderQuoteLine(candles[candles.length - 1], `Cierre ${payload.timeframe}`)" in panel_source
    assert "renderQuoteLine(candle, date.toLocaleString())" in panel_source
    assert "Rango ${Number.isFinite(range) ? fmt(range) : \"--\"}" not in panel_source
    assert "showRoxyCursor" in panel_source
    assert "hideRoxyCursor" in panel_source
    assert "nearestCandleByX" in panel_source
    assert "Cursor ${Number.isFinite(Number(yPrice))" in panel_source
    assert "chart.subscribeCrosshairMove" in panel_source
    assert "O ${fmt(Number(candle.open))}" in panel_source
    assert 'id="rlc-snap-cue"' in panel_source
    assert "setSnapCue(drawStart)" in panel_source
    assert "setSnapCue(end)" in panel_source
    assert "selectedDrawingIndex" in panel_source
    assert "addSelectionHandles" in panel_source
    assert "deleteDrawing(targetIndex)" in panel_source
    assert "Borrador: toca una linea" in panel_source
    assert "let editDrag = null" in panel_source
    assert "pointFromPixel" in panel_source
    assert "updateShapePoint" in panel_source
    assert "moveShapeByPixels" in panel_source
    assert "measureSummaryFromPoints" in panel_source
    assert "spanLabelFromSeconds" in panel_source
    assert '"data-measure-summary": "true"' in panel_source
    assert "`${summary.pctText} | ${summary.priceText} | ${summary.barsText}`" in panel_source
    assert 'shape.tool === "measure"' in panel_source
    assert "Precio ${summary.priceText}" in panel_source
    assert "data-selection-handle" in panel_source
    assert "Editando punto" in panel_source
    assert "Moviendo dibujo" in panel_source
    assert "Dibujo actualizado" in panel_source
    assert "const syncToolInteractionMode = () =>" in panel_source
    assert 'root.dataset.toolMode = chartNavigationMode ? "navigate" : drawingEditMode ? "edit" : "draw"' in panel_source
    assert 'drawLayer.classList.toggle("chart-pan-mode", chartNavigationMode)' in panel_source
    assert 'drawLayer.classList.toggle("drawing-mode", !chartNavigationMode && !drawingEditMode)' in panel_source
    assert "pressedMouseMove: chartNavigationMode" in panel_source
    assert "syncToolInteractionMode();" in panel_source
    assert "updateVisibleRangeTelemetry" in panel_source
    assert "root.dataset.visibleFrom" in panel_source
    assert "root.dataset.visibleTo" in panel_source
    assert "root.dataset.visibleSpan" in panel_source
    assert "applyManualVisibleRange" in panel_source
    assert "zoomManualVisibleRange" in panel_source
    assert "panManualVisibleRange" in panel_source
    assert 'chartEl.addEventListener("wheel"' in panel_source
    assert 'chartEl.addEventListener("pointerdown"' in panel_source
    assert 'chartEl.addEventListener("pointermove"' in panel_source
    assert 'data-quicklevel="entry"' in panel_source
    assert 'data-quicklevel="stop"' in panel_source
    assert 'data-quicklevel="target2"' in panel_source
    assert 'data-quicklevel="plan"' in panel_source
    assert 'data-action="undo"' in panel_source
    assert 'data-action="redo"' in panel_source
    assert 'data-action="lock"' in panel_source
    assert 'data-action="clear-plan"' in panel_source
    assert 'data-action="fit"' in panel_source
    assert 'data-action="fullscreen"' in panel_source
    assert 'tool: "priceLevel"' in panel_source
    assert 'tool: "entryZone"' in panel_source
    assert "addPriceLevel" in panel_source
    assert "applyTradePlanLevels" in panel_source
    assert "undoDrawings" in panel_source
    assert "redoDrawings" in panel_source
    assert "toggleDrawingLock" in panel_source
    assert "clearAppliedPlanLevels" in panel_source
    assert "fitChartToContent" in panel_source
    assert "toggleFullscreenChart" in panel_source
    assert "resizeChartNow" in panel_source
    assert "requestFullscreen" in panel_source
    assert "fitContent()" in panel_source
    assert "rlc-fullscreen" in panel_source
    assert "Vista ajustada" in panel_source
    assert "pushDrawingHistory" in panel_source
    assert "shapeFromPriceLevel" in panel_source
    assert "planShapes" in panel_source
    assert "updatePlanBadge" in panel_source
    assert "if (indicatorSettings.Plan)" in panel_source
    assert "referencePrice" in panel_source
    assert "marcado @ ${fmt(price)}" in panel_source
    assert "Plan Roxy aplicado" in panel_source
    assert "Plan editable quitado" in panel_source
    assert "Dibujos bloqueados" in panel_source
    assert "Desbloquea para borrar" in panel_source
    assert "roxyPlanApplied" in panel_source
    assert 'id="rlc-plan-badge"' in panel_source
    assert "Target 2%" in panel_source
    assert 'shape.tool === "priceLevel"' in panel_source
    assert 'shape.tool === "entryZone"' in panel_source
    assert "const initialRange =" in panel_source
    assert 'setVisibleRange(initialRange)' in panel_source
    assert 'setVisibleRange(candles.length > 600 ? "1M" : "ALL")' not in panel_source
    assert "rlc-tool-readout" in panel_source
    assert "rlc-brand-mark" in panel_source
    assert "<strong>Roxy</strong><span>AI Trading</span>" in panel_source
    assert 'aria-label="Linea de tendencia"' in panel_source
    assert 'aria-label="Borrador"' in panel_source
    assert 'aria-label="Deshacer ultimo cambio"' in panel_source
    assert "trade_plan=trade_plan" in function_source_from_file("streamlit_app.py", "render_browser_live_candle_chart")
    assert "trade_plan=chart_trade_plan" in function_source_from_file("streamlit_app.py", "render_operational_chart_first")


def test_trade_desk_timeframe_pair_prioritizes_trend_and_entry_views():
    assert trade_desk_timeframe_pair("1m") == ("5m", "1m")
    assert trade_desk_timeframe_pair("5m") == ("15m", "5m")
    assert trade_desk_timeframe_pair("1h") == ("1h", "15m")
    assert trade_desk_timeframe_pair("15m") == ("1h", "15m")
    assert trade_desk_timeframe_pair("4h") == ("4h", "1h")
    assert trade_desk_timeframe_pair("1d") == ("1d", "1h")
    assert trade_desk_timeframe_pair("1w") == ("1w", "1d")


def test_live_candle_chart_payload_keeps_deep_history_and_crypto_stream_route():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for idx in range(720):
        close = 100 + idx * 0.5
        rows.append(
            {
                "ts": start + timedelta(hours=idx),
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.3,
                "close": close,
                "volume": 1000 + idx,
                "sma20": close - 1,
                "bb_upper": close + 2,
                "bb_mid": close,
                "bb_lower": close - 2,
            }
        )
    payload = live_candle_chart_payload(
        pd.DataFrame(rows),
        symbol="BTC/USD",
        market="crypto",
        timeframe="1h",
        live_price={"price": 66000, "freshness": "LIVE", "source": "BinanceUS ticker", "age_seconds": 1},
    )

    assert len(payload["candles"]) == 720
    assert payload["stream"]["enabled"] is True
    assert payload["stream"]["mode"] == "WEBSOCKET_MARKET_STREAM"
    assert payload["stream"]["wsBase"] == "wss://stream.binance.us:9443"
    assert payload["stream"]["interval"] == "1h"
    assert "BTCUSD" in payload["stream"]["symbols"]
    assert payload["lines"]["SMA20"]
    assert payload["lines"]["BB Upper"]
    assert payload["lines"]["BB Lower"]
    assert payload["defaultIndicators"]["Labels"] is False
    assert payload["defaultIndicators"]["Plan"] is False
    assert payload["defaultIndicators"]["Info"] is False
    assert payload["defaultIndicators"]["Scale"] is True
    assert payload["defaultIndicators"]["SMA100"] is False
    assert payload["defaultIndicators"]["SMA200"] is False
    assert payload["defaultIndicators"]["BB Upper"] is True
    assert payload["defaultIndicators"]["BB Mid"] is False
    assert payload["live"]["price"] == 66000
    assert payload["tradePlan"]["entry"] is None


def test_binanceus_symbol_candidates_prefers_usd_and_usdt_pairs():
    assert binanceus_symbol_candidates("BTC/USD")[:2] == ["BTCUSD", "BTCUSDT"]
    assert binanceus_symbol_candidates("ETH/USDT")[:2] == ["ETHUSDT", "ETHUSD"]


def test_command_center_target_prices_uses_ladder_before_fallbacks():
    targets = command_center_target_prices(
        {
            "entry": 100,
            "target_ladder": [
                {"target": "2%", "target_price": 103},
                {"target": "5%", "target_price": 108},
            ],
        }
    )

    assert targets["target_2"] == 103
    assert targets["target_5"] == 108
    assert round(targets["target_10"], 2) == 110


def test_priority_trade_lane_rows_separates_operate_and_watch():
    table = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "stock",
                "timeframe": "1h",
                "signal": "BUY",
                "decision": "TRADE_FOR_STOCK",
                "action": "ALERT",
                "entry": 100,
                "stop": 97,
                "target": 104,
                "readiness": 88,
                "strategy_family": "Canal alcista",
            },
            {
                "symbol": "BTC/USD",
                "market": "crypto",
                "timeframe": "15m",
                "signal": "WATCH",
                "decision": "WAIT",
                "entry": 65000,
                "stop": 64000,
                "target": 67000,
                "readiness": 68,
                "strategy_family": "Pullback",
            },
        ]
    )

    lanes = priority_trade_lane_rows(table)

    assert lanes["operate"][0]["symbol"] == "AAPL"
    assert lanes["operate"][0]["entry"] == "100.00"
    assert lanes["watch"][0]["symbol"] == "BTC/USD"
    assert lanes["watch"][0]["href"].startswith("?view=Activo&symbol=BTC%2FUSD")


def test_command_center_checklist_translates_condition_checks():
    rows = command_center_checklist_rows(
        {
            "condition_checks": [
                {"label": "1h confirma", "passed": True, "detail": "Score tendencia 80"},
                {"label": "15m da entrada", "passed": False, "detail": "WAIT"},
            ]
        }
    )

    assert rows[0]["status"] == "OK"
    assert rows[0]["tone"] == "buy"
    assert rows[1]["status"] == "Falta"
    assert rows[1]["tone"] == "avoid"


def test_build_command_center_summary_names_buy_stock_decision():
    summary = build_command_center_summary(
        {
            "symbol": "AAPL",
            "market": "stock",
            "timeframe": "1h",
            "action": "BUY_STOCK",
            "decision": "Comprar accion",
            "strategy_family": "Canal alcista",
            "entry": 200,
            "stop": 196,
            "risk_pct": 0.02,
            "decision_reason": {"summary": "SMA20 sostiene la tendencia y el riesgo esta medido."},
        }
    )

    assert summary["status"] == "Operar"
    assert summary["tone"] == "buy"
    assert summary["decision"] == "Comprar accion"
    assert summary["strategy"] == "Canal alcista"


def test_focused_display_table_keeps_only_actionable_columns():
    brief = {
        "opportunities": [
            {
                "ai_action": "WATCH",
                "symbol": "AAPL",
                "market": "stock",
                "ai_score": 88,
                "signal": "WATCH",
                "trade_decision": "WAIT",
            }
        ]
    }

    table = focused_opportunity_table(brief)
    display = focused_display_table(table)

    assert "focus_priority" not in display.columns
    assert {"symbol", "confidence", "por_que", "waiting_for", "cambia_si"}.issubset(display.columns)


def test_focused_display_table_es_renames_and_formats_columns():
    brief = {
        "opportunities": [
            {
                "ai_action": "WATCH",
                "symbol": "AAPL",
                "market": "stock",
                "ai_score": 88,
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "entry": 200,
                "stop": 196,
                "risk_pct": 0.02,
                "recommended_target_pct": 0.05,
                "recommended_target_price": 210,
            }
        ]
    }

    table = focused_display_table_es(focused_opportunity_table(brief))

    assert {"simbolo", "entrada", "riesgo", "target", "esperamos"}.issubset(table.columns)
    assert table.loc[0, "entrada"] == "200.00"
    assert table.loc[0, "riesgo"] == "2.00%"
    assert table.loc[0, "target"] == "5.00%"


def test_market_pulse_summary_groups_actionable_dashboard_state():
    brief = {
        "opportunities": [
            {
                "ai_action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "ai_score": 91,
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "entry": 100,
                "current_price": 100.1,
                "stop": 99,
                "risk_pct": 0.018,
                "alert_gate": "ready",
                "alert_readiness_score": 86,
                "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
            },
            {
                "ai_action": "WATCH",
                "symbol": "NVDA",
                "market": "stock",
                "ai_score": 77,
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "risk_pct": 0.042,
                "alert_gate": "risk",
                "alert_readiness_score": 64,
                "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
            },
            {
                "ai_action": "NO_TRADE",
                "symbol": "BTC/USD",
                "market": "crypto",
                "ai_score": 32,
                "signal": "AVOID",
                "trade_decision": "NO_TRADE",
                "alert_gate": "risk",
                "alert_readiness_score": 20,
                "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "BinanceUS ticker", "source_mode": "EXCHANGE_API"},
            },
        ]
    }

    table = focused_opportunity_table(brief)
    rows = market_pulse_rows(table)
    summary = market_pulse_summary(table)

    assert rows["bucket"].tolist() == ["Operar", "Vigilar", "Evitar"]
    assert summary["ready"] == 1
    assert summary["watch"] == 1
    assert summary["avoid"] == 1
    assert summary["top_gate"] == "Risk"
    assert summary["top_market"] == "stock"
    assert summary["risk_alerts"] == 1


def test_dashboard_reference_patterns_capture_user_screenshots_modules():
    patterns = dashboard_reference_patterns()
    modules = {row["module"] for row in patterns}

    assert {"Market Movers", "Stock Monitor", "Sector Heatmap", "Discover Crypto 24/7", "Stats + Trading Trends"}.issubset(
        modules
    )
    assert any("Robinhood" in row["platform"] for row in patterns)
    assert any("Webull" in row["platform"] for row in patterns)


def test_market_discovery_extractors_build_live_dashboard_sections():
    brief = {
        "opportunities": [
            {
                "ai_action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "ai_score": 94,
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "strategy_family": "Ruptura 52 week high",
                "relative_volume": 2.3,
                "current_price": 210,
                "recommended_target_pct": 0.05,
                "risk_pct": 0.018,
                "alert_readiness_score": 88,
                "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
            },
            {
                "ai_action": "WATCH",
                "symbol": "BTC/USD",
                "market": "crypto",
                "ai_score": 81,
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "strategy_family": "Canal alcista",
                "relative_volume": 3.1,
                "recommended_target_pct": 0.04,
                "risk_pct": 0.024,
                "alert_readiness_score": 70,
                "live_price_contract": {
                    "gate": "LIVE_PRICE_OK",
                    "source_label": "BinanceUS ticker",
                    "source_mode": "EXCHANGE_API",
                },
            },
            {
                "ai_action": "NO_TRADE",
                "symbol": "TSLA",
                "market": "stock",
                "ai_score": 36,
                "signal": "AVOID",
                "trade_decision": "NO_TRADE",
                "strategy_family": "Debilidad",
                "relative_volume": 1.1,
                "risk_pct": 0.055,
                "alert_readiness_score": 25,
                "live_price_contract": {"gate": "LIVE_PRICE_OK", "source_label": "Alpaca IEX"},
            },
        ]
    }
    table = focused_opportunity_table(brief)
    scan_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "signal": "BUY", "score": 92, "relative_volume": 2.2},
            {"symbol": "BTC/USD", "signal": "WATCH", "score": 78, "relative_volume": 3.0},
        ]
    )
    confluence_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "signal": "BUY", "trade_decision": "TRADE_FOR_2PCT", "confluence_score": 93},
            {"symbol": "BTC/USD", "signal": "WATCH", "trade_decision": "WAIT", "confluence_score": 77},
        ]
    )

    mood = market_discovery_mood(table, scan_df, confluence_df)
    sections = market_discovery_mover_sections(table, confluence_df, limit=3)
    monitor = stock_monitor_rows(table, scan_df, limit=3)
    crypto = crypto_discovery_rows(table, confluence_df, limit=3)
    sectors = market_discovery_sector_tiles(table, limit=3)
    asset = market_discovery_asset_detail(table, confluence_df, symbol="AAPL", market="stock")

    assert mood["label"] in {"Neutral", "Greed"}
    assert "AAPL" in [row["symbol"] for row in sections["Top Gainers"]]
    assert "TSLA" in [row["symbol"] for row in sections["Top Losers"]]
    assert monitor.loc[0, "type"] in {"Rising Volume", "Setup Confirmado", "Setup Watch"}
    assert crypto["symbol"].tolist() == ["BTC/USD"]
    assert sectors
    assert asset["symbol"] == "AAPL"
    assert asset["price"] == 210


def test_market_news_cards_expose_openable_sources_for_news_tickers_and_ipos():
    rows = market_news_card_rows(
        [
            {
                "title": "COIN expands institutional trading",
                "tickers": ["COIN"],
                "impact": "HIGH",
                "published_at": "2026-06-16T10:00:00Z",
                "source": "benzinga",
                "url": "https://example.com/coin-news",
            }
        ],
        [
            {
                "symbol": "SPCX",
                "headline": "Space Exploration Technologies starts trading",
                "reason": "Ticker nuevo detectado",
                "source": "market news",
                "tradingview_url": "https://www.tradingview.com/symbols/SPCX/",
            }
        ],
        [
            {
                "symbol": "ABCD",
                "company": "ABCD Robotics",
                "exchange": "NASDAQ",
                "date": "2026-06-20",
                "price": "$18",
                "shares": "10M",
            }
        ],
    )

    assert [row["kind"] for row in rows] == ["Noticia", "Ticker nuevo", "IPO"]
    assert rows[0]["url"] == "https://example.com/coin-news"
    assert rows[1]["url"].endswith("/SPCX/")
    assert rows[2]["url"] == "https://finance.yahoo.com/quote/ABCD/news"


def test_market_news_cards_do_not_emit_indented_markdown_code_blocks():
    source = function_source_from_file("streamlit_app.py", "render_market_news_cards")

    assert '<article class="market-news-card">' in source
    assert '<section class="market-news-grid">' in source
    assert 'f"""' not in source
    assert "unsafe_allow_html=True" in source


def test_filter_focused_opportunities_applies_dashboard_controls():
    brief = {
        "opportunities": [
            {
                "ai_action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "ai_score": 91,
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "alert_readiness_score": 86,
            },
            {
                "ai_action": "WATCH",
                "symbol": "NVDA",
                "market": "stock",
                "ai_score": 77,
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "alert_readiness_score": 64,
            },
            {
                "ai_action": "WATCH",
                "symbol": "BTC/USD",
                "market": "crypto",
                "ai_score": 72,
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "alert_readiness_score": 78,
            },
        ]
    }

    table = focused_opportunity_table(brief)
    stock_watch = filter_focused_opportunities(table, bucket="Vigilar", market="stock", min_readiness=60)
    ready_only = filter_focused_opportunities(table, bucket="Operar", market="Todos", min_readiness=80)
    crypto_high = filter_focused_opportunities(table, bucket="Todos", market="crypto", min_readiness=75)

    assert stock_watch["symbol"].tolist() == ["NVDA"]
    assert ready_only["symbol"].tolist() == ["AAPL"]
    assert crypto_high["symbol"].tolist() == ["BTC/USD"]


def test_market_pulse_risk_map_keeps_numeric_risk_and_readiness():
    brief = {
        "opportunities": [
            {
                "ai_action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "ai_score": 91,
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "risk_pct": 0.018,
                "alert_readiness_score": 86,
            },
            {
                "ai_action": "WATCH",
                "symbol": "MSFT",
                "market": "stock",
                "ai_score": 66,
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "risk_pct": None,
                "alert_readiness_score": 55,
            },
        ]
    }

    risk_map = market_pulse_risk_map(focused_opportunity_table(brief))

    assert risk_map["symbol"].tolist() == ["AAPL"]
    assert risk_map.loc[0, "risk_pct_display"] == 1.7999999999999998
    assert risk_map.loc[0, "readiness"] == 86


def test_scanner_cockpit_summary_heatmap_and_leaderboard_prioritize_setups():
    brief = {
        "market_session": {"stock_session": "Regular"},
        "source_freshness": {"label": "Frescos"},
        "opportunities": [
            {
                "ai_action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "ai_score": 91,
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "strategy_family": "Pullback",
                "trigger_setup": "PULLBACK",
                "risk_pct": 0.018,
                "alert_gate": "ready",
                "alert_readiness_score": 86,
            },
            {
                "ai_action": "WATCH",
                "symbol": "NVDA",
                "market": "stock",
                "ai_score": 77,
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "strategy_family": "Canal alcista",
                "trigger_setup": "CANAL_ALCISTA",
                "risk_pct": 0.042,
                "alert_gate": "risk",
                "alert_readiness_score": 64,
            },
        ],
    }
    table = focused_opportunity_table(brief)
    options = pd.DataFrame([{"option_decision": "OPTION_CANDIDATE"}, {"option_decision": "REJECTED"}])

    summary = scanner_overview_summary(table, pd.DataFrame([{"symbol": "AAPL"}]), options, brief)
    heatmap = scanner_heatmap_rows(table)
    leaderboard = scanner_leaderboard_rows(table, bucket="Todos", limit=2)

    assert summary["top_symbol"] == "AAPL"
    assert summary["option_candidates"] == 1
    assert summary["session"] == "Regular"
    assert {"Pullback", "Canal alcista"}.issubset(set(heatmap["strategy"]))
    assert leaderboard["symbol"].tolist() == ["AAPL", "NVDA"]
    assert leaderboard.loc[0, "status"] == "Operar"


def test_combine_blocked_scanner_display_ignores_empty_sources():
    columns = ["symbol", "status"]
    empty = pd.DataFrame(columns=columns)
    avoid = pd.DataFrame([{"symbol": "TSLA", "status": "Evitar"}])

    combined = combine_blocked_scanner_display(empty, avoid, limit=12)
    combined_empty = combine_blocked_scanner_display(empty, empty, limit=12)

    assert combined["symbol"].tolist() == ["TSLA"]
    assert list(combined_empty.columns) == columns
    assert combined_empty.empty


def test_container_width_kwargs_are_normalized_for_streamlit_compat():
    kwargs = _container_width_to_width({"use_container_width": True, "height": 300})

    assert kwargs == {"width": "stretch", "height": 300}


def test_platform_labels_hide_internal_statuses():
    assert platform_status_label("READY_TO_PREVIEW") == "Listo para preparar"
    assert platform_status_label("BLOCKED_MARKET_CLOSED") == "Mercado cerrado"
    assert asset_type_label("option") == "Opcion"
    assert connection_mode_label("PREVIEW_ONLY") == "Solo preview"
    assert "buying power" in platform_reason_label("Roxy allows preview only after platform buying-power check.")
    assert "Estado Roxy" in execution_blocker_label("Roxy status is NO_TRADE; only READY_TO_PREVIEW can be armed.")
    assert "seguridad" in execution_blocker_label("ROXY_ENABLE_LIVE_BROKER_EXECUTION=1 is not set.")


def test_notification_channel_display_uses_spanish_statuses():
    table = notification_channel_display(
        [
            {
                "channel": "macos",
                "configured": True,
                "requirements": "MACOS_NOTIFICATIONS=1",
                "notes": "Local desktop notification on this Mac.",
            },
            {
                "channel": "email",
                "configured": False,
                "requirements": "SMTP_HOST",
                "notes": "Best for phone delivery if your email pushes notifications.",
            },
        ]
    )

    assert list(table["Canal"]) == ["Mac local", "Email"]
    assert list(table["Estado"]) == ["Listo", "Falta configurar"]
    assert "Notificacion local" in table.loc[0, "Notas"]


def test_center_decision_summary_separates_operar_esperar_no_operar():
    buy = center_decision_summary({"ai_action": "ALERT", "signal": "BUY", "trade_decision": "TRADE_FOR_2PCT"})
    watch = center_decision_summary({"ai_action": "WATCH", "signal": "WATCH", "trade_decision": "WAIT"})
    avoid = center_decision_summary({"ai_action": "WATCH", "signal": "AVOID", "trade_decision": "NO_TRADE"})

    assert buy["status"] == "Operar"
    assert watch["status"] == "Esperar"
    assert avoid["status"] == "No operar"


def test_alert_preview_table_keeps_alerts_and_adds_target_ladder():
    brief = {
        "opportunities": [
            {
                "ai_action": "WATCH",
                "symbol": "MSFT",
                "market": "stock",
                "entry": 300,
            },
            {
                "ai_action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "entry": 200,
                "stop": 196,
                "risk_pct": 0.02,
                "alert_readiness_score": 88,
                "alert_gate": "ALERT_READY",
                "strategy_family": "PULLBACK",
            },
        ]
    }

    table = alert_preview_table(brief)

    assert list(table["symbol"]) == ["AAPL"]
    assert table.loc[0, "target_2"] == 204
    assert table.loc[0, "target_5"] == 210
    assert round(table.loc[0, "target_10"], 2) == 220
    assert table.loc[0, "confianza"].startswith("Media")
    assert table.loc[0, "por_que"].startswith("BUY confirmado")
    assert table.loc[0, "filtro"] == "Listo para operar manual"


def test_trade_plan_platform_preview_routes_call_to_option_ticket():
    brief = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "WATCH_CALL",
        "operation_status": "Operar",
        "trade_decision": "TRADE_FOR_5PCT",
        "decision": "Mirar call",
        "entry": 100,
        "stop": 98,
        "recommended_target_pct": 0.05,
        "recommended_target_price": 105,
        "option": {
            "contractSymbol": "AAPL260619C00100000",
            "bid": 1.9,
            "ask": 2.1,
            "max_loss_per_contract": 150,
            "dte": 14,
            "delta": 0.45,
        },
    }

    ticket = trade_plan_platform_preview(
        brief,
        account_equity=500,
        risk_per_trade_pct=0.01,
        market_session={"stock_alerts_allowed": True},
    )

    assert ticket["platform_id"] == "schwab"
    assert ticket["asset_type"] == "option"
    assert ticket["order_symbol"] == "AAPL260619C00100000"
    assert ticket["entry"] == 2.0
    assert ticket["stop"] == 0.5
    assert ticket["quantity"] == 3
    assert ticket["manual_only"] is True
    assert ticket["risk_guardrail"]["status"] == "OK"
    assert ticket["small_account_plan"]["recommendation"] == "Solo paper"
    assert ticket["small_account_plan"]["option_allowed"] is False
    assert ticket["option_quality"]["delta"] == 0.45


def test_trade_plan_platform_preview_blocks_ready_stock_when_market_closed():
    brief = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "BUY_STOCK",
        "operation_status": "Operar",
        "trade_decision": "TRADE_FOR_2PCT",
        "decision": "Comprar accion",
        "entry": 200,
        "stop": 197.5,
        "recommended_target_pct": 0.02,
        "recommended_target_price": 204,
        "option": {},
    }

    ticket = trade_plan_platform_preview(
        brief,
        account_equity=500,
        risk_per_trade_pct=0.01,
        market_session={"stock_session": "Cerrado", "stock_alerts_allowed": False},
    )

    assert ticket["asset_type"] == "stock"
    assert ticket["status"] == "BLOCKED_MARKET_CLOSED"
    assert ticket["execution_enabled"] is False


def test_opportunity_confidence_labels_memory_quality():
    assert opportunity_confidence_label({"learning_bias": "positive", "alert_readiness_score": 90}).startswith("Alta:")
    assert opportunity_confidence_label({"learning_bias": "negative", "alert_readiness_score": 90}).startswith("Baja:")
    assert opportunity_confidence_label({"learning_bias": "learning"}).startswith("Aprendiendo:")


def test_data_freshness_status_handles_missing_files():
    status = data_freshness_status(["missing_live.csv", None])

    assert status["label"] == "Sin datos"
    assert status["tone"] == "avoid"


def test_data_freshness_status_marks_recent_files_fresh(tmp_path):
    now = datetime(2026, 6, 7, 12, 0)
    live = tmp_path / "live.csv"
    confluence = tmp_path / "confluence.csv"
    live.write_text("symbol,signal\nAAPL,BUY\n")
    confluence.write_text("symbol,signal\nAAPL,BUY\n")
    mtime = (now - timedelta(minutes=3)).timestamp()
    for path in (live, confluence):
        path.touch()
        import os

        os.utime(path, (mtime, mtime))

    status = data_freshness_status([str(live), str(confluence)], max_age_minutes=10.0, now=now)

    assert status["label"] == "Frescos"
    assert status["tone"] == "buy"
    assert status["age_minutes"] == 3.0


def test_data_freshness_status_uses_oldest_file_as_gate(tmp_path):
    now = datetime(2026, 6, 7, 12, 0)
    live = tmp_path / "live.csv"
    confluence = tmp_path / "confluence.csv"
    live.write_text("symbol,signal\nAAPL,BUY\n")
    confluence.write_text("symbol,signal\nAAPL,BUY\n")

    import os

    fresh_mtime = (now - timedelta(minutes=5)).timestamp()
    stale_mtime = (now - timedelta(minutes=45)).timestamp()
    os.utime(live, (fresh_mtime, fresh_mtime))
    os.utime(confluence, (stale_mtime, stale_mtime))

    status = data_freshness_status([str(live), str(confluence)], max_age_minutes=10.0, now=now)

    assert status["label"] == "Estancados"
    assert status["tone"] == "avoid"
    assert status["age_minutes"] == 45.0


def test_load_latest_live_scan_prefers_heartbeat_artifact(tmp_path, monkeypatch):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    output.mkdir()
    alerts.mkdir()
    heartbeat_scan = output / "ma_live_strategy_stocks_20260608_120000.csv"
    generic_scan = output / "ma_live_strategy_both_20260608_120100.csv"
    heartbeat_scan.write_text("symbol,tf\nAAPL,4h\n")
    generic_scan.write_text("symbol,tf\nMSFT,15m\n")
    (alerts / "ma_live_heartbeat.json").write_text(f'{{"scan_path": "{heartbeat_scan}"}}')
    monkeypatch.setattr(streamlit_app, "OUTPUT_DIR", output)
    monkeypatch.setattr(streamlit_app, "ALERTS_DIR", alerts)

    path = heartbeat_artifact_path("scan_path")
    loaded_path, loaded_df = load_latest_ma_scan("ma_live_strategy")

    assert path == str(heartbeat_scan)
    assert loaded_path == str(heartbeat_scan)
    assert loaded_df.iloc[0]["symbol"] == "AAPL"


def test_load_latest_live_scan_uses_configured_output_and_alerts_dirs(tmp_path, monkeypatch):
    output = tmp_path / "configured_output"
    alerts = tmp_path / "configured_alerts"
    output.mkdir()
    alerts.mkdir()
    scan = output / "ma_live_strategy_both_20260608_120100.csv"
    scan.write_text("symbol,tf\nMSFT,15m\n")
    monkeypatch.setattr(streamlit_app, "OUTPUT_DIR", output)
    monkeypatch.setattr(streamlit_app, "ALERTS_DIR", alerts)

    loaded_path, loaded_df = load_latest_ma_scan("ma_live_strategy")

    assert loaded_path == str(scan)
    assert loaded_df.iloc[0]["symbol"] == "MSFT"


def test_live_backend_status_marks_loaded_fresh_service_operational(tmp_path):
    now = datetime(2026, 6, 7, 12, 0)
    live = tmp_path / "live.csv"
    confluence = tmp_path / "confluence.csv"
    live.write_text("symbol,signal\nAAPL,BUY\n")
    confluence.write_text("symbol,signal\nAAPL,BUY\n")

    import os

    mtime = (now - timedelta(minutes=2)).timestamp()
    os.utime(live, (mtime, mtime))
    os.utime(confluence, (mtime, mtime))

    status = live_backend_status(
        str(live),
        str(confluence),
        service_state={"installed": "yes", "loaded": "yes", "label": "com.roxy.ma_live", "path": "/tmp/job.plist"},
        now=now,
    )

    assert status["label"] == "Operativo"
    assert status["tone"] == "buy"
    assert status["loaded"] is True


def test_live_backend_status_warns_when_backend_off_but_files_are_fresh(tmp_path):
    now = datetime(2026, 6, 7, 12, 0)
    live = tmp_path / "live.csv"
    confluence = tmp_path / "confluence.csv"
    live.write_text("symbol,signal\nAAPL,BUY\n")
    confluence.write_text("symbol,signal\nAAPL,BUY\n")

    import os

    mtime = (now - timedelta(minutes=2)).timestamp()
    os.utime(live, (mtime, mtime))
    os.utime(confluence, (mtime, mtime))

    status = live_backend_status(
        str(live),
        str(confluence),
        service_state={"installed": "no", "loaded": "no", "label": "com.roxy.ma_live", "path": "-"},
        now=now,
    )

    assert status["label"] == "Manual fresco"
    assert status["tone"] == "watch"
    assert status["loaded"] is False


def test_live_backend_status_prioritizes_failed_heartbeat(tmp_path):
    now = datetime(2026, 6, 7, 12, 0)
    live = tmp_path / "live.csv"
    confluence = tmp_path / "confluence.csv"
    live.write_text("symbol,signal\nAAPL,BUY\n")
    confluence.write_text("symbol,signal\nAAPL,BUY\n")

    status = live_backend_status(
        str(live),
        str(confluence),
        service_state={"installed": "yes", "loaded": "yes", "label": "com.roxy.ma_live", "path": "/tmp/job.plist"},
        heartbeat={"status": "FAILED", "error": "Command failed with exit code 1"},
        now=now,
    )

    assert status["label"] == "Fallo"
    assert status["tone"] == "avoid"
    assert "exit code 1" in status["detail"]


def test_live_backend_status_includes_success_duration(tmp_path):
    now = datetime(2026, 6, 7, 12, 0)
    live = tmp_path / "live.csv"
    confluence = tmp_path / "confluence.csv"
    live.write_text("symbol,signal\nAAPL,BUY\n")
    confluence.write_text("symbol,signal\nAAPL,BUY\n")

    import os

    mtime = (now - timedelta(minutes=2)).timestamp()
    os.utime(live, (mtime, mtime))
    os.utime(confluence, (mtime, mtime))

    status = live_backend_status(
        str(live),
        str(confluence),
        service_state={"installed": "yes", "loaded": "yes", "label": "com.roxy.ma_live", "path": "/tmp/job.plist"},
        heartbeat={"status": "SUCCESS", "duration_seconds": 12.34},
        now=now,
    )

    assert status["label"] == "Operativo"
    assert status["tone"] == "buy"
    assert "12.3s" in status["detail"]


def test_realtime_check_status_maps_report_to_ui_tone():
    assert realtime_check_status({})["label"] == "No corrido"
    ok = realtime_check_status({"status": "OK", "checks": [{"status": "OK"}]})
    warn = realtime_check_status(
        {"status": "WARN", "checks": [{"name": "disk_space", "status": "WARN", "detail": "0.80 GiB free"}]}
    )
    fail = realtime_check_status(
        {"status": "FAIL", "checks": [{"name": "heartbeat", "status": "FAIL", "detail": "network unavailable"}]}
    )

    assert ok["tone"] == "buy"
    assert warn["label"] == "Revisar"
    assert "disk_space" in warn["detail"]
    assert fail["tone"] == "avoid"
    assert "network unavailable" in fail["detail"]


def test_normalize_realtime_refresh_interval_picks_supported_value():
    assert normalize_realtime_refresh_interval(60) == 60
    assert normalize_realtime_refresh_interval("75") == 60
    assert normalize_realtime_refresh_interval("bad") == 5
    assert normalize_realtime_refresh_interval(280) == 300


def test_build_realtime_refresh_script_pauses_while_user_is_active():
    script = build_realtime_refresh_script(120)

    assert "__roxyRealtimeRefreshSeconds = 120" in script
    assert "__roxyRealtimeRefreshTimer" in script
    assert "clearTimeout" in script
    assert "clearInterval" in script
    assert "__roxyRealtimeRefreshReloadBlocked = true" in script
    assert "streamlit-fragment" in script
    assert "location.reload" not in script
    assert "setTimeout" not in script
    assert "setInterval" not in script


def test_realtime_refresh_dashboard_status_summarizes_state():
    enabled = realtime_refresh_dashboard_status(
        {"enabled": True, "interval_seconds": 30, "mode": "streamlit_fragment"}
    )
    disabled = realtime_refresh_dashboard_status({"enabled": False, "interval_seconds": 30})

    assert enabled["label"] == "Live sin reload"
    assert enabled["tone"] == "buy"
    assert "30s" in enabled["detail"]
    assert "streamlit_fragment" in enabled["detail"]
    assert "sin recargar" in enabled["detail"]
    assert "pantalla negra" in enabled["detail"]
    assert disabled["label"] == "OFF"
    assert disabled["tone"] == "watch"
    assert "manual" in disabled["detail"]


def test_live_ops_strip_rows_summarize_visible_realtime_status():
    rows = live_ops_strip_rows(
        operational_mode_status={"label": "Premium bloqueado", "tone": "watch", "detail": "crypto permitido"},
        freshness_status={"label": "Frescos", "tone": "buy", "detail": "age 1m"},
        realtime_refresh_status={"label": "Live sin reload", "tone": "buy", "detail": "15s"},
        dashboard_ui_status={"label": "UI estable", "tone": "buy", "detail": "AAPL stock 1h"},
        chart_health_status={"label": "Graficas vivas", "tone": "buy", "detail": "16 charts"},
        chart_provider_status={"label": "Fallback auth", "tone": "watch", "detail": "alpaca_auth"},
        market_route_status={"label": "Operar solo CRYPTO", "tone": "watch", "detail": "stock/options bloqueado"},
        alert_quality_status={"label": "Bloqueo parcial", "tone": "watch", "detail": "stock bloqueado"},
        operational_logs_status={"label": "Limpios", "tone": "buy", "detail": "0 warnings"},
        check_status={"label": "WARN", "tone": "watch", "detail": "premium"},
        generated_at="2026-06-11T12:00:00Z",
    )

    by_label = {row["label"]: row for row in rows}
    assert by_label["Modo"]["value"] == "Premium bloqueado"
    assert by_label["Datos"]["tone"] == "buy"
    assert by_label["Refresh"]["value"] == "Live sin reload"
    assert by_label["UI live"]["value"] == "UI estable"
    assert by_label["UI live"]["detail"] == "AAPL stock 1h"
    assert by_label["Proveedor"]["detail"] == "alpaca_auth"
    assert by_label["Ruta"]["value"] == "Operar solo CRYPTO"
    assert by_label["Ruta"]["tone"] == "watch"
    assert by_label["Check"]["detail"] == "2026-06-11T12:00:00Z"


def test_dashboard_ui_stability_status_requires_search_probe_state_persistence():
    report = {
        "checks": [
            {
                "name": "dashboard_render_probe",
                "status": "OK",
                "detail": "render OK",
                "age_minutes": 34.1,
                "max_age_minutes": 90.0,
                "text_length": 4631,
                "soft_console_warning_dominant_family": "browser_feature_policy",
                "soft_console_warning_dominant_family_count": 8,
                "soft_console_warning_dominant_family_unique_count": 8,
                "actionable_soft_console_warning_count": 0,
                "black_screen": False,
                "live_no_reload": True,
                "view_persisted": True,
                "selected_view_persisted": True,
                "symbol_persisted": True,
                "market_persisted": True,
                "timeframe_persisted": True,
            },
            {
                "name": "dashboard_search_render_probe",
                "status": "OK",
                "detail": "search OK",
                "age_minutes": 33.9,
                "max_age_minutes": 90.0,
                "text_length": 16519,
                "soft_console_warning_dominant_family": "vega_lite_version",
                "soft_console_warning_dominant_family_count": 19,
                "soft_console_warning_dominant_family_unique_count": 1,
                "actionable_soft_console_warning_count": 0,
                "black_screen": False,
                "live_no_reload": True,
                "view_persisted": True,
                "selected_view_persisted": True,
                "symbol_persisted": True,
                "market_persisted": True,
                "timeframe_persisted": True,
                "final_symbol": "AAPL",
                "final_market": "stock",
                "final_timeframe": "1h",
            },
        ]
    }

    status = dashboard_ui_stability_status(report)

    assert status["label"] == "UI estable"
    assert status["tone"] == "buy"
    assert "AAPL stock 1h" in status["detail"]
    assert "render text 4631 age 34.1m/90m margen 55.9m soft browser_feature_policy 8/8u" in status["detail"]
    assert "busqueda text 16519 age 33.9m/90m margen 56.1m soft vega_lite_version 19/1u" in status["detail"]
    assert status["render_age_minutes"] == 34.1
    assert status["search_age_minutes"] == 33.9
    assert status["render_text_length"] == 4631
    assert status["search_text_length"] == 16519


def test_dashboard_ui_stability_status_flags_search_state_loss():
    report = {
        "checks": [
            {
                "name": "dashboard_render_probe",
                "status": "OK",
                "black_screen": False,
                "live_no_reload": True,
                "view_persisted": True,
                "selected_view_persisted": True,
                "symbol_persisted": True,
                "market_persisted": True,
                "timeframe_persisted": True,
            },
            {
                "name": "dashboard_search_render_probe",
                "status": "FAIL",
                "black_screen": False,
                "live_no_reload": True,
                "view_persisted": True,
                "selected_view_persisted": True,
                "symbol_persisted": True,
                "market_persisted": False,
                "timeframe_persisted": False,
            },
        ]
    }

    status = dashboard_ui_stability_status(report)

    assert status["label"] == "UI falla"
    assert status["tone"] == "avoid"
    assert "busqueda perdio mercado" in status["detail"]
    assert "busqueda perdio tf" in status["detail"]


def test_dashboard_ui_stability_status_flags_actionable_soft_warnings():
    report = {
        "checks": [
            {
                "name": "dashboard_render_probe",
                "status": "OK",
                "age_minutes": 12.0,
                "max_age_minutes": 90.0,
                "text_length": 4000,
                "actionable_soft_console_warning_count": 2,
                "soft_console_warning_dominant_family": "react_warning",
                "soft_console_warning_dominant_family_count": 2,
                "soft_console_warning_dominant_family_unique_count": 1,
                "black_screen": False,
                "live_no_reload": True,
                "view_persisted": True,
                "selected_view_persisted": True,
                "symbol_persisted": True,
                "market_persisted": True,
                "timeframe_persisted": True,
            },
            {
                "name": "dashboard_search_render_probe",
                "status": "OK",
                "age_minutes": 10.0,
                "max_age_minutes": 90.0,
                "text_length": 16000,
                "black_screen": False,
                "live_no_reload": True,
                "view_persisted": True,
                "selected_view_persisted": True,
                "symbol_persisted": True,
                "market_persisted": True,
                "timeframe_persisted": True,
            },
        ]
    }

    status = dashboard_ui_stability_status(report)

    assert status["label"] == "UI revisar"
    assert status["tone"] == "watch"
    assert "render soft warnings accionables 2" in status["detail"]
    assert "render text 4000 age 12.0m/90m margen 78.0m soft react_warning 2/1u" in status["detail"]


def test_render_live_ops_strip_outputs_escaped_compact_strip():
    html = render_live_ops_strip(
        [
            {"label": "Modo", "value": "OK<script>", "tone": "buy", "detail": "sin reload"},
            {"label": "Proveedor", "value": "Fallback", "tone": "watch", "detail": "alpaca_auth"},
        ]
    )

    assert "Operacion en vivo" in html
    assert "live-ops-card-buy" in html
    assert "live-ops-card-watch" in html
    assert "alpaca_auth" in html
    assert "<script>" not in html


def test_live_refresh_keeps_command_center_inputs_outside_fragment():
    source = function_source_from_file("streamlit_app.py", "show_focused_roxy_app")

    controls_index = source.index("render_command_center_controls")
    fragment_index = source.index("@st.fragment")
    assert controls_index < fragment_index
    assert '"defer_command_analysis": True' in source
    assert "def _render_trade_desk_static(" in source
    assert "def _render_trade_lanes(" in source
    assert "def _live_trade_lanes()" in source
    assert "render_command_center_live_panel(" in source
    assert "show_spinner=False" in source
    assert "render_side_panel=False" in source
    assert "chart_interactive=True" in source
    assert "render_priority_trade_lanes(" in source
    assert "render_command_center_live_panel(" not in source.split("@st.fragment", 1)[1]
    assert "render_focused_page_content(live_context, selected_page" not in source
    assert "render_focused_live_workspace(realtime, selected_page=selected_page)" not in source


def test_live_refresh_rehydrates_current_page_inside_fragment():
    source = function_source_from_file("streamlit_app.py", "show_focused_roxy_app")
    fragment_source = source.split("def _live_workspace()", 1)[1]

    assert "live_selected_page = current_focused_page_state(" in fragment_source
    assert "hydrate_focused_page_state(" not in fragment_source
    assert 'live_selected_page == "Dashboard"' in fragment_source
    assert "render_focused_live_status_workspace(live_context, realtime)" in fragment_source


def test_current_focused_page_state_reads_without_mutating_session():
    session = {"roxy_focused_page": "Opciones"}

    page = current_focused_page_state({"view": "Centro"}, session, "AAPL")

    assert page == "Opciones"
    assert session == {"roxy_focused_page": "Opciones"}


def test_live_status_fragment_disables_sidebar_widgets():
    status_source = function_source_from_file("streamlit_app.py", "show_ai_status_cards")
    workspace_source = function_source_from_file("streamlit_app.py", "render_focused_live_status_workspace")

    assert "show_technical_reports: bool | None = None" in status_source
    assert "if show_technical_reports is None:" in status_source
    assert "st.sidebar.toggle(" in status_source
    assert "show_technical_reports=False" in workspace_source


def test_focused_page_content_reuses_stable_home_controls():
    source = function_source_from_file("streamlit_app.py", "render_focused_page_content")

    assert "home_controls: dict[str, Any] | None = None" in source
    assert "render_focused_home_live(scan_df, confluence_df, options_df, brief, home_controls)" in source
    assert "show_focused_home(scan_df, confluence_df, options_df, brief)" in source


def test_live_home_defers_only_command_analysis_to_fragment():
    home_source = function_source_from_file("streamlit_app.py", "render_focused_home_live")
    panel_source = function_source_from_file("streamlit_app.py", "render_command_center_live_panel")

    assert 'defer_command_analysis = bool(controls.get("defer_command_analysis"))' in home_source
    clean_mode_source = home_source.split("if clean_mode:", 1)[1].split("else:", 1)[0]
    assert "if not defer_command_analysis:" in clean_mode_source
    assert "render_command_center_live_panel(confluence_df, options_df, brief, controls)" in home_source
    assert "render_command_center_analysis(" in panel_source
    assert "load_symbol_trade_context(" in panel_source


def test_focused_page_navigation_lives_in_sidebar():
    source = function_source_from_file("streamlit_app.py", "render_focused_page_navigation")

    assert "st.sidebar.selectbox(" in source
    assert "st.selectbox(" not in source


def test_command_center_controls_persist_url_on_change():
    source = function_source_from_file("streamlit_app.py", "render_command_center_controls")

    assert source.count("on_change=persist_command_query_params") >= 2
    assert "on_change=persist_command_symbol_query_params" in source


def test_persist_command_query_params_syncs_current_widget_state(monkeypatch):
    captured = {}
    persisted = {}

    class Params(dict):
        pass

    monkeypatch.setattr(streamlit_app.st, "query_params", Params({"view": "Centro"}), raising=False)
    monkeypatch.setattr(
        streamlit_app.st,
        "session_state",
        {
            "command_symbol": "tsla",
            "command_market": "stock",
            "command_timeframe": "15m",
            "roxy_focused_page": "Centro",
        },
        raising=False,
    )

    def fake_sync(params, *, symbol, market, timeframe, page):
        captured.update({"params": params, "symbol": symbol, "market": market, "timeframe": timeframe, "page": page})
        return True

    monkeypatch.setattr(streamlit_app, "sync_dashboard_query_params", fake_sync)
    monkeypatch.setattr(streamlit_app, "write_dashboard_ui_state", lambda **kwargs: persisted.update(kwargs))

    persist_command_query_params()

    assert captured == {
        "params": {"view": "Centro"},
        "symbol": "tsla",
        "market": "stock",
        "timeframe": "15m",
        "page": "Centro",
    }
    assert persisted["symbol"] == "tsla"
    assert persisted["timeframe"] == "15m"


def test_persist_command_symbol_query_params_infers_market(monkeypatch):
    captured = {}
    persisted = {}

    class Params(dict):
        pass

    session = {
        "command_symbol": "AAPL",
        "command_market": "crypto",
        "command_timeframe": "1h",
        "roxy_focused_page": "Centro",
    }
    monkeypatch.setattr(streamlit_app.st, "query_params", Params({"view": "Centro"}), raising=False)
    monkeypatch.setattr(streamlit_app.st, "session_state", session, raising=False)

    def fake_sync(params, *, symbol, market, timeframe, page):
        captured.update({"params": params, "symbol": symbol, "market": market, "timeframe": timeframe, "page": page})
        return True

    monkeypatch.setattr(streamlit_app, "sync_dashboard_query_params", fake_sync)
    monkeypatch.setattr(streamlit_app, "write_dashboard_ui_state", lambda **kwargs: persisted.update(kwargs))

    persist_command_symbol_query_params()

    assert session["command_market"] == "stock"
    assert captured["symbol"] == "AAPL"
    assert captured["market"] == "stock"
    assert persisted["market"] == "stock"


def test_command_state_from_query_params_restores_symbol_view_and_timeframe():
    state = command_state_from_query_params(
        {"symbol": ["amd"], "market": "crypto", "tf": "4h", "view": "Plan de trade"},
        default_symbol="WMT",
    )

    assert state == {
        "symbol": "AMD",
        "market": "crypto",
        "timeframe": "4h",
        "page": "Activo",
    }


def test_command_state_from_query_params_restores_persisted_state_when_url_is_empty():
    state = command_state_from_query_params(
        {},
        default_symbol="AAPL",
        persisted_state={"symbol": "sol/usd", "market": "crypto", "timeframe": "15m", "page": "Estudios"},
    )

    assert state == {
        "symbol": "SOL/USD",
        "market": "crypto",
        "timeframe": "15m",
        "page": "Estudios",
    }


def test_hydrate_command_state_from_query_params_overrides_stale_widget_state():
    session = {
        "command_symbol": "BTC/USD",
        "command_market": "crypto",
        "command_timeframe": "15m",
        "command_query_signature": ("BTC/USD", "crypto", "15m", "Centro"),
    }

    state = hydrate_command_state_from_query_params(
        {"symbol": "ETH/USD", "market": "crypto", "tf": "1h", "view": "Centro"},
        session,
        "AAPL",
    )

    assert state["symbol"] == "ETH/USD"
    assert session["command_symbol"] == "ETH/USD"
    assert session["command_market"] == "crypto"
    assert session["command_timeframe"] == "1h"
    assert session["command_query_signature"] == ("ETH/USD", "crypto", "1h", "Dashboard")


def test_hydrate_focused_page_state_preserves_selected_page_over_live_refresh():
    session = {"roxy_focused_page": "Opciones"}
    page = hydrate_focused_page_state({"view": "Centro"}, session, "AAPL")

    assert page == "Opciones"
    assert session["roxy_focused_page"] == "Opciones"


def test_hydrate_focused_page_state_uses_query_page_on_first_load():
    session = {}
    page = hydrate_focused_page_state({"view": "Estudios"}, session, "AAPL")

    assert page == "Estudios"
    assert session["roxy_focused_page"] == "Estudios"


def test_hydrate_command_state_uses_persisted_state_after_blank_reload(monkeypatch):
    monkeypatch.setattr(
        streamlit_app,
        "read_dashboard_ui_state",
        lambda: {"symbol": "ETH/USD", "market": "crypto", "timeframe": "1h", "page": "Centro"},
    )
    session = {}

    state = hydrate_command_state_from_query_params({}, session, "AAPL")

    assert state["symbol"] == "ETH/USD"
    assert session["command_symbol"] == "ETH/USD"
    assert session["command_market"] == "crypto"
    assert session["command_timeframe"] == "1h"


def test_command_state_from_query_params_falls_back_to_safe_defaults():
    state = command_state_from_query_params(
        {"symbol": "", "market": "bad", "tf": "bad", "view": "Missing"},
        default_symbol="NVDA",
    )

    assert state == {
        "symbol": "NVDA",
        "market": "stock",
        "timeframe": "1h",
        "page": "Dashboard",
    }


def test_sync_dashboard_query_params_writes_normalized_trade_context_only():
    params = {"symbol": "AMD", "market": "stock", "tf": "1h", "view": "Centro"}

    unchanged = sync_dashboard_query_params(
        params,
        symbol="amd",
        market="stock",
        timeframe="1h",
        page="Centro",
    )
    changed = sync_dashboard_query_params(
        params,
        symbol="btc/usd",
        market="bad",
        timeframe="75m",
        page="Opciones",
    )

    assert unchanged is True
    assert changed is True
    assert params == {"symbol": "BTC/USD", "market": "crypto", "tf": "1h", "view": "Opciones"}


def test_dashboard_ui_state_round_trips_to_disk(tmp_path):
    path = tmp_path / "dashboard_ui_state.json"

    streamlit_app.write_dashboard_ui_state(
        symbol="btc/usd",
        market="bad",
        timeframe="4h",
        page="Opciones",
        path=path,
    )

    assert streamlit_app.read_dashboard_ui_state(path) == {
        "symbol": "BTC/USD",
        "market": "crypto",
        "timeframe": "4h",
        "page": "Opciones",
    }


def test_study_center_uses_persistent_navigation_for_live_refresh():
    source = function_source_from_file("streamlit_app.py", "show_strategy_study_center")

    assert STUDY_PAGE_LABELS == ["Manual", "Ejemplo con grafica", "Laboratorio"]
    assert 'key="roxy_study_page"' in source
    assert "st.radio" in source
    assert "st.tabs" not in source


def test_output_maintenance_dashboard_status_uses_realtime_check():
    status = output_maintenance_dashboard_status(
        {
            "status": "OK",
            "checks": [
                {
                    "name": "output_maintenance_report",
                    "status": "OK",
                    "age_hours": 0.4,
                    "removed_count": 522,
                    "output_archive_count": 11,
                    "output_archive_dir": "/Volumes/RoxyData/MacArchive/roxy_trading/output_archive",
                    "stale_output_removed_count": 9,
                    "trimmed_log_count": 2,
                    "trimmed_history_count": 1,
                    "trimmed_history_removed_lines": 250,
                    "history_budget_near_limit_count": 3,
                    "history_budget_over_limit_count": 0,
                    "history_budget_at_cap_count": 1,
                    "history_budget_top_name": "roxy_learning_journal.csv",
                    "history_budget_top_status": "NEAR_LIMIT",
                    "history_budget_top_line_ratio": 0.976,
                    "history_budget_top_byte_ratio": 0.051,
                    "history_budget_top_line_margin": 12,
                    "history_budget_top_byte_margin": 7119832,
                    "dashboard_history_after_rows": 41,
                    "dashboard_history_max_rows": 5000,
                    "dashboard_history_removed_rows": 3,
                    "dashboard_history_reason": "deduped",
                    "removed_alert_report_count": 3,
                    "local_cache_cleanup_status": "DONE",
                    "local_cache_cleanup_plan_state": "SAFE_CACHE_REVIEW_READY",
                    "local_cache_cleanup_enabled": True,
                    "local_cache_cleanup_removed_count": 4,
                    "local_cache_cleanup_removed_mb": 18.113,
                    "local_cache_cleanup_eligible_count": 9,
                    "local_cache_cleanup_eligible_mb": 32.456,
                    "sqlite_db_size_mb": 181.3,
                    "sqlite_db_reclaimable_mb": 0.0,
                    "sqlite_db_optimized": True,
                    "sqlite_db_vacuumed": False,
                    "runtime_footprint_mb": 53.5,
                    "max_runtime_footprint_mb": 512.0,
                    "footprint_budget_status": "OK",
                    "footprint_budget_issues": [],
                    "hygiene_label": "Protegido",
                    "hygiene_protected": True,
                    "hygiene_detail": "archive OK | snapshots OK",
                    "maintenance_next_action": "Monitorear",
                    "external_archive_ready": True,
                    "dry_run": False,
                }
            ],
        },
        {
            "prepared_dir_count": 2,
            "prepared_dir_error_count": 0,
            "output_archive_exists": True,
            "log_snapshot_dir_exists": True,
            "operation_summary": {
                "label": "Limpieza aplicada",
                "detail": "acciones 42 | recuperado 8.0MB",
                "action_count": 42,
                "reclaimed_mb": 8.0,
            },
        },
    )

    assert status["label"] == "OK"
    assert status["tone"] == "buy"
    assert "0.4h" in status["detail"]
    assert "stale 9" in status["detail"]
    assert "removidos 522" in status["detail"]
    assert "archivados 11" in status["detail"]
    assert "dirs OK" in status["detail"]
    assert status["output_archive_count"] == 11
    assert status["output_archive_dir"] == "/Volumes/RoxyData/MacArchive/roxy_trading/output_archive"
    assert status["prepared_dir_count"] == 2
    assert status["output_archive_exists"] is True
    assert status["log_snapshot_dir_exists"] is True
    assert "logs 2" in status["detail"]
    assert "hist 1" in status["detail"]
    assert "hist lines 250" in status["detail"]
    assert status["trimmed_history_removed_lines"] == 250
    assert (
        "hist budget near 3 over 0 cap 1 top roxy_learning_journal.csv near_limit "
        "lines 97.6% bytes 5.1% line_margin 12 byte_margin 6.79MB"
    ) in status["detail"]
    assert status["history_budget_near_limit_count"] == 3
    assert status["history_budget_over_limit_count"] == 0
    assert status["history_budget_at_cap_count"] == 1
    assert status["history_budget_top_name"] == "roxy_learning_journal.csv"
    assert status["history_budget_top_status"] == "NEAR_LIMIT"
    assert status["history_budget_top_line_ratio"] == 0.976
    assert status["history_budget_top_byte_ratio"] == 0.051
    assert status["history_budget_top_line_margin"] == 12
    assert status["history_budget_top_byte_margin"] == 7119832
    assert "dash hist 41/5000 -3 deduped" in status["detail"]
    assert status["dashboard_history_after_rows"] == 41
    assert status["dashboard_history_max_rows"] == 5000
    assert status["dashboard_history_removed_rows"] == 3
    assert status["dashboard_history_reason"] == "deduped"
    assert "reportes 3" in status["detail"]
    assert "cache local done" in status["detail"]
    assert "plan cache safe_cache_review_ready" in status["detail"]
    assert "cache activo" in status["detail"]
    assert "cache removidos 4" in status["detail"]
    assert "cache 18.1MB" in status["detail"]
    assert "cache elegible 9" in status["detail"]
    assert "cache elegible 32.5MB" in status["detail"]
    assert status["local_cache_cleanup_status"] == "DONE"
    assert status["local_cache_cleanup_plan_state"] == "SAFE_CACHE_REVIEW_READY"
    assert status["local_cache_cleanup_enabled"] is True
    assert status["local_cache_cleanup_removed_count"] == 4
    assert status["local_cache_cleanup_removed_mb"] == 18.113
    assert status["local_cache_cleanup_eligible_count"] == 9
    assert status["local_cache_cleanup_eligible_mb"] == 32.456
    assert "DB 181MB" in status["detail"]
    assert "huella 53.5MB/512MB OK" in status["detail"]
    assert status["runtime_footprint_mb"] == 53.5
    assert status["max_runtime_footprint_mb"] == 512.0
    assert status["footprint_budget_status"] == "OK"
    assert "higiene Protegido" in status["detail"]
    assert "operacion Limpieza aplicada" in status["detail"]
    assert "acciones 42" in status["detail"]
    assert "recuperado 8.0MB" in status["detail"]
    assert "accion Monitorear" in status["detail"]
    assert status["hygiene_label"] == "Protegido"
    assert status["hygiene_protected"] is True
    assert status["operation_label"] == "Limpieza aplicada"
    assert status["operation_action_count"] == 42
    assert status["operation_reclaimed_mb"] == 8.0
    assert status["maintenance_next_action"] == "Monitorear"
    assert status["external_archive_ready"] is True
    assert status["sqlite_label"] == "181 MB"
    assert status["sqlite_detail"] == "reclaimable 0.0 MB | optimize OK"
    assert status["sqlite_tone"] == "buy"


def test_output_maintenance_dashboard_status_warns_when_sqlite_has_reclaimable_space():
    status = output_maintenance_dashboard_status(
        {
            "checks": [
                {
                    "name": "output_maintenance_report",
                    "status": "OK",
                    "sqlite_db_size_mb": 320.0,
                    "sqlite_db_reclaimable_mb": 80.0,
                    "sqlite_db_optimized": True,
                }
            ]
        },
        {},
    )

    assert status["label"] == "OK"
    assert status["tone"] == "buy"
    assert status["sqlite_label"] == "320 MB"
    assert status["sqlite_tone"] == "watch"
    assert "DB reclaim 80.0MB" in status["detail"]


def test_output_maintenance_dashboard_status_surfaces_current_history_budget_pressure():
    status = output_maintenance_dashboard_status(
        {
            "checks": [
                {
                    "name": "output_maintenance_report",
                    "status": "OK",
                    "history_budget_status": "OK",
                    "history_budget_pressure": "CLEAR",
                    "history_budget_near_limit_count": 0,
                    "current_history_budget_status": "WARN",
                    "current_history_budget_pressure": "NEAR_LIMIT",
                    "current_history_budget_near_limit_count": 1,
                    "current_history_budget_over_limit_count": 0,
                    "current_history_budget_at_cap_count": 0,
                    "current_history_budget_top_name": "alert_quality_history.jsonl",
                    "current_history_budget_top_status": "NEAR_LIMIT",
                    "current_history_budget_top_line_ratio": 0.852,
                    "current_history_budget_top_byte_ratio": 0.613,
                    "current_history_budget_top_line_margin": 74,
                    "current_history_budget_top_byte_margin": 765433,
                }
            ]
        },
        {},
    )

    assert status["label"] == "Revisar"
    assert status["tone"] == "watch"
    assert (
        "hist actual warn near 1 over 0 cap 0 near_limit top alert_quality_history.jsonl "
        "near_limit lines 85.2% bytes 61.3% line_margin 74 byte_margin 0.73MB"
    ) in status["detail"]
    assert status["current_history_budget_status"] == "WARN"
    assert status["current_history_budget_pressure"] == "NEAR_LIMIT"
    assert status["current_history_budget_near_limit_count"] == 1
    assert status["current_history_budget_over_limit_count"] == 0
    assert status["current_history_budget_at_cap_count"] == 0
    assert status["current_history_budget_top_name"] == "alert_quality_history.jsonl"
    assert status["current_history_budget_top_status"] == "NEAR_LIMIT"
    assert status["current_history_budget_top_line_ratio"] == 0.852
    assert status["current_history_budget_top_byte_ratio"] == 0.613
    assert status["current_history_budget_top_line_margin"] == 74
    assert status["current_history_budget_top_byte_margin"] == 765433


def test_output_maintenance_dashboard_status_surfaces_disabled_cache_preview():
    status = output_maintenance_dashboard_status(
        {
            "status": "OK",
            "checks": [
                {
                    "name": "output_maintenance_report",
                    "status": "OK",
                    "local_cache_cleanup_status": "SKIPPED",
                    "local_cache_cleanup_plan_state": "SAFE_CACHE_REVIEW_READY",
                    "local_cache_cleanup_enabled": False,
                    "local_cache_cleanup_removed_count": 0,
                    "local_cache_cleanup_removed_mb": 0.0,
                    "local_cache_cleanup_eligible_count": 2730,
                    "local_cache_cleanup_eligible_mb": 76.118,
                    "maintenance_next_action": "Activar limpieza cache local",
                }
            ],
        },
        {"operation_summary": {"label": "Limpieza aplicada"}},
    )

    assert status["label"] == "OK"
    assert "cache local skipped" in status["detail"]
    assert "plan cache safe_cache_review_ready" in status["detail"]
    assert "cache apagado" in status["detail"]
    assert "cache removidos 0" in status["detail"]
    assert "cache elegible 2730" in status["detail"]
    assert "cache elegible 76.1MB" in status["detail"]
    assert "accion Activar limpieza cache local" in status["detail"]
    assert status["local_cache_cleanup_status"] == "SKIPPED"
    assert status["local_cache_cleanup_enabled"] is False
    assert status["local_cache_cleanup_eligible_count"] == 2730
    assert status["local_cache_cleanup_eligible_mb"] == 76.118


def test_output_maintenance_dashboard_status_surfaces_footprint_budget_warning():
    status = output_maintenance_dashboard_status(
        {
            "checks": [
                {
                    "name": "output_maintenance_report",
                    "status": "WARN",
                    "runtime_footprint_mb": 90.0,
                    "max_runtime_footprint_mb": 200.0,
                    "footprint_budget_status": "WARN",
                    "footprint_budget_issues": ["alerts 70.0>64.0MB"],
                }
            ]
        },
        {},
    )

    assert status["label"] == "Revisar"
    assert status["tone"] == "watch"
    assert status["footprint_budget_status"] == "WARN"
    assert status["footprint_budget_issues"] == ["alerts 70.0>64.0MB"]
    assert "huella 90.0MB/200MB WARN" in status["detail"]
    assert "alerts 70.0>64.0MB" in status["detail"]


def test_output_maintenance_dashboard_status_warns_on_dry_run_report():
    now = datetime(2026, 6, 8, 12, 0)
    status = output_maintenance_dashboard_status(
        {},
        {
            "generated_at": "2026-06-08T10:00:00+00:00",
            "dry_run": True,
            "removed_count": 0,
        },
        now=now,
    )

    assert status["label"] == "Revisar"
    assert status["tone"] == "watch"
    assert status["dry_run"] is True
    assert "dry-run" in status["detail"]


def test_output_maintenance_dashboard_status_warns_on_archive_errors():
    status = output_maintenance_dashboard_status(
        {
            "checks": [
                {
                    "name": "output_maintenance_report",
                    "status": "WARN",
                    "output_archive_count": 0,
                    "output_archive_error_count": 2,
                }
            ],
        },
        {},
    )

    assert status["label"] == "Revisar"
    assert status["tone"] == "watch"
    assert status["output_archive_error_count"] == 2
    assert "errores archivo 2" in status["detail"]


def test_output_maintenance_dashboard_status_warns_on_prepared_dir_errors():
    status = output_maintenance_dashboard_status(
        {},
        {
            "generated_at": "2026-06-08T10:00:00+00:00",
            "prepared_dir_error_count": 1,
            "output_archive_exists": False,
            "log_snapshot_dir_exists": False,
        },
        now=datetime(2026, 6, 8, 12, 0),
    )

    assert status["label"] == "Revisar"
    assert status["tone"] == "watch"
    assert status["prepared_dir_error_count"] == 1
    assert "errores dirs 1" in status["detail"]


def test_output_maintenance_dashboard_status_surfaces_next_action_from_hygiene_summary():
    status = output_maintenance_dashboard_status(
        {},
        {
            "generated_at": "2026-06-08T10:00:00+00:00",
            "output_archive_exists": False,
            "log_snapshot_dir_exists": False,
            "hygiene_summary": {
                "label": "Parcial",
                "protected": False,
                "next_action": "Conectar RoxyData y preparar carpetas",
                "external_archive_ready": False,
            },
        },
        now=datetime(2026, 6, 8, 12, 0),
    )

    assert status["maintenance_next_action"] == "Conectar RoxyData y preparar carpetas"
    assert status["external_archive_ready"] is False
    assert "accion Conectar RoxyData y preparar carpetas" in status["detail"]
    assert "archivo externo no listo" in status["detail"]


def test_output_maintenance_dashboard_status_handles_missing_report():
    status = output_maintenance_dashboard_status({}, {})

    assert status["label"] == "Sin reporte"
    assert status["tone"] == "watch"


def test_runtime_backup_dashboard_status_uses_realtime_check():
    status = runtime_backup_dashboard_status(
        {
            "status": "OK",
            "checks": [
                {
                    "name": "runtime_backup_report",
                    "status": "OK",
                    "age_hours": 0.5,
                    "archive_size_bytes": 25 * 1024 * 1024,
                    "removed_count": 1,
                    "archive_exists": True,
                    "dry_run": False,
                }
            ],
        },
        {},
    )

    assert status["label"] == "OK"
    assert status["tone"] == "buy"
    assert "0.5h" in status["detail"]
    assert "25.0 MB" in status["detail"]
    assert "rotados 1" in status["detail"]


def test_runtime_backup_dashboard_status_warns_on_dry_run_report():
    now = datetime(2026, 6, 10, 12, 0)
    status = runtime_backup_dashboard_status(
        {},
        {
            "generated_at": "2026-06-10T11:00:00+00:00",
            "status": "DRY_RUN",
            "dry_run": True,
            "archive_exists": False,
            "archive_size_bytes": 0,
        },
        now=now,
    )

    assert status["label"] == "Revisar"
    assert status["tone"] == "watch"
    assert status["dry_run"] is True
    assert "dry-run" in status["detail"]


def test_runtime_backup_dashboard_status_includes_daemon_schedule():
    now = datetime(2026, 6, 10, 12, 0)
    status = runtime_backup_dashboard_status(
        {
            "status": "OK",
            "checks": [
                {
                    "name": "runtime_backup_report",
                    "status": "OK",
                    "age_hours": 1.0,
                    "archive_size_bytes": 10 * 1024 * 1024,
                    "archive_exists": True,
                    "archive_verified": True,
                    "archive_verified_members": [
                        "alerts/roxy_realtime_check.json",
                        "alerts/runtime_backup.json",
                        "db/scan_history.csv",
                    ],
                    "archive_verified_paths": ["alerts", "db", "data"],
                    "archive_verification_source": "runtime",
                    "archive_database_member_verified": True,
                    "archive_missing_critical_members": [],
                    "archive_missing_verified_paths": [],
                },
                {
                    "name": "runtime_backup_service",
                    "status": "OK",
                    "daemon_running": True,
                },
            ],
        },
        {},
        {
            "status": "RUNNING",
            "last_backup_at": "2026-06-10T10:00:00+00:00",
            "next_backup_at": "2026-06-11T10:00:00+00:00",
        },
        now=now,
    )

    assert status["label"] == "OK"
    assert status["tone"] == "buy"
    assert status["daemon_running"] is True
    assert "daemon running" in status["detail"]
    assert "last 2.0h" in status["detail"]
    assert "next 22.0h" in status["detail"]
    assert "miembros 3" in status["detail"]
    assert "fuente runtime" in status["detail"]
    assert "db verificada" in status["detail"]
    assert status["archive_verified_members"] == [
        "alerts/roxy_realtime_check.json",
        "alerts/runtime_backup.json",
        "db/scan_history.csv",
    ]
    assert status["archive_verification_source"] == "runtime"
    assert status["archive_database_member_verified"] is True
    assert status["archive_missing_critical_members"] == []
    assert status["archive_missing_verified_paths"] == []


def test_runtime_backup_dashboard_status_warns_on_missing_critical_members():
    status = runtime_backup_dashboard_status(
        {
            "checks": [
                {
                    "name": "runtime_backup_report",
                    "status": "OK",
                    "age_hours": 1.0,
                    "archive_size_bytes": 10 * 1024 * 1024,
                    "archive_exists": True,
                    "archive_verified": True,
                    "archive_verified_paths": ["alerts", "db"],
                    "archive_verified_members": ["alerts/runtime_backup.json"],
                    "archive_missing_critical_members": ["db/scan_history.csv"],
                    "archive_missing_verified_paths": ["data"],
                    "archive_database_member_verified": False,
                }
            ],
        },
        {},
    )

    assert status["label"] == "Revisar"
    assert status["tone"] == "watch"
    assert status["archive_missing_critical_members"] == ["db/scan_history.csv"]
    assert status["archive_missing_verified_paths"] == ["data"]
    assert status["archive_database_member_verified"] is False
    assert "criticos faltan 1" in status["detail"]
    assert "rutas faltan 1" in status["detail"]
    assert "db sin verificar" in status["detail"]


def test_runtime_backup_dashboard_status_handles_missing_report():
    status = runtime_backup_dashboard_status({}, {})

    assert status["label"] == "Sin reporte"
    assert status["tone"] == "watch"


def test_autoheal_dashboard_status_summarizes_healthy_state():
    status = autoheal_dashboard_status(
        {
            "launchd_autoheal": {"status": "OK", "service_count": 4, "recovered": [], "failed": []},
            "runtime_backup_autoheal": {"action": "healthy", "status": {"healthy": True}},
            "live_data_autoheal": {"action": "skipped_running_service", "ok": True},
        }
    )

    assert status["label"] == "OK"
    assert status["tone"] == "buy"
    assert "servicios 4" in status["detail"]
    assert "backup healthy" in status["detail"]
    assert "live skipped_running_service" in status["detail"]


def test_autoheal_dashboard_status_treats_routine_refresh_as_healthy():
    status = autoheal_dashboard_status(
        {
            "status": "OK",
            "launchd_autoheal": {"status": "OK", "service_count": 5, "recovered": [], "failed": []},
            "runtime_backup_autoheal": {"action": "healthy", "status": {"healthy": True}},
            "live_data_autoheal": {"action": "skipped_running_service", "ok": True},
            "daily_opportunity_plan_autoheal": {"action": "regenerated", "ok": True},
            "status_snapshot_autoheal": {"action": "regenerated", "ok": True},
            "ai_brief_autoheal": {"action": "regenerated", "ok": True},
            "alert_quality_autoheal": {"action": "regenerated", "ok": True},
        }
    )

    assert status["label"] == "OK"
    assert status["tone"] == "buy"
    assert status["routine_refresh"] is True
    assert "plan 24h regenerated" in status["detail"]
    assert "status regenerated" in status["detail"]
    assert "brief regenerated" in status["detail"]
    assert "alertas regenerated" in status["detail"]


def test_autoheal_dashboard_status_handles_ok_without_autoheal_actions():
    status = autoheal_dashboard_status(
        {
            "status": "OK",
            "checks": [
                {"name": "heartbeat", "status": "OK", "detail": "running"},
                {"name": "streamlit_service_24h", "status": "OK", "detail": "loaded"},
            ],
        }
    )

    assert status["label"] == "Sin acciones"
    assert status["tone"] == "buy"
    assert status["routine_refresh"] is True
    assert "no hizo falta autoheal" in status["detail"]


def test_autoheal_dashboard_status_surfaces_recovery_and_failures():
    recovered = autoheal_dashboard_status(
        {
            "launchd_autoheal": {"status": "OK", "service_count": 4, "recovered": ["streamlit"], "failed": []},
            "runtime_backup_autoheal": {"action": "restarted", "status": {"healthy": True}},
            "runtime_backup_report_autoheal": {"action": "regenerated", "ok": True},
            "streamlit_app_autoheal": {"action": "restart", "ok": True},
            "chart_health_autoheal": {"action": "regenerated", "ok": True},
            "live_data_autoheal": {"action": "ran_live_scan", "ok": True},
            "storage_migration_autoheal": {"action": "created_missing_destination", "ok": True},
            "output_maintenance_autoheal": {"action": "regenerated", "ok": True},
            "daily_opportunity_plan_autoheal": {"action": "regenerated", "ok": True},
            "status_snapshot_autoheal": {"action": "regenerated", "ok": True},
            "ai_brief_autoheal": {"action": "regenerated", "ok": True},
            "alert_quality_autoheal": {"action": "regenerated", "ok": True},
            "yfinance_cache_autoheal": {"action": "recovered", "ok": True},
        }
    )
    failed = autoheal_dashboard_status(
        {
            "launchd_autoheal": {"status": "WARN", "service_count": 4, "recovered": [], "failed": ["ma_live"]},
            "runtime_backup_autoheal": {"action": "healthy", "status": {"healthy": True}},
        }
    )

    assert recovered["label"] == "Recupero 1"
    assert recovered["tone"] == "watch"
    assert "web restart" in recovered["detail"]
    assert "backup report regenerated" in recovered["detail"]
    assert "graficas regenerated" in recovered["detail"]
    assert "live ran_live_scan" in recovered["detail"]
    assert "storage created_missing_destination" in recovered["detail"]
    assert "limpieza regenerated" in recovered["detail"]
    assert "plan 24h regenerated" in recovered["detail"]
    assert "status regenerated" in recovered["detail"]
    assert "brief regenerated" in recovered["detail"]
    assert "alertas regenerated" in recovered["detail"]
    assert "cache yf recovered" in recovered["detail"]
    assert failed["label"] == "Falla"
    assert failed["tone"] == "avoid"


def test_autoheal_report_keys_include_all_recovery_channels():
    keys = set(streamlit_app.AUTOHEAL_REPORT_KEYS)

    assert "storage_migration_autoheal" in keys
    assert "yfinance_cache_autoheal" in keys
    assert "live_data_autoheal" in keys
    assert "alert_quality_autoheal" in keys


def test_health_history_dashboard_status_summarizes_recent_stability():
    stable = health_history_dashboard_status(
        [
            {"status": "OK", "warn_count": 0, "fail_count": 0},
            {"status": "OK", "warn_count": 0, "fail_count": 0},
        ]
    )
    unstable = health_history_dashboard_status(
        [
            {"status": "OK", "warn_count": 0, "fail_count": 0},
            {"status": "FAIL", "warn_count": 0, "fail_count": 1, "top_issue": {"name": "heartbeat"}},
        ]
    )
    recovered = health_history_dashboard_status(
        [
            {"status": "FAIL", "warn_count": 0, "fail_count": 1, "top_issue": {"name": "external_disk"}},
            {"status": "OK", "warn_count": 0, "fail_count": 0},
            {"status": "OK", "warn_count": 0, "fail_count": 0},
            {"status": "OK", "warn_count": 0, "fail_count": 0},
        ]
    )
    sync_warn = health_history_dashboard_status(
        [
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "status_snapshot_alert_quality_sync_checked": True,
                    "status_snapshot_alert_quality_issue_count": 1,
                    "alert_quality_missed_trigger_plan_review_due": True,
                },
            },
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "status_snapshot_alert_quality_sync_checked": True,
                    "status_snapshot_alert_quality_issue_count": 0,
                    "alert_quality_missed_trigger_plan_review_due": False,
                },
            },
        ]
    )
    drift_warn = health_history_dashboard_status(
        [
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "health_stability_slo_latest_status_snapshot_alert_quality_blocker_issue_count": 1,
                },
            }
        ]
    )
    premium_core = health_history_dashboard_status(
        [
            {"status": "WARN", "warn_count": 3, "fail_count": 0, "top_issue": {"name": "older_report"}},
            {
                "status": "WARN",
                "warn_count": 3,
                "fail_count": 0,
                "top_issue": {"name": "alert_quality_report"},
                "metrics": {
                    "health_stability_slo_core_ok_rate": 0.72,
                    "health_stability_slo_core_streak_status": "OK",
                    "health_stability_slo_core_streak_count": 48,
                },
            },
            {
                "status": "WARN",
                "warn_count": 3,
                "fail_count": 0,
                "top_issue": {"name": "alert_quality_report"},
                "metrics": {
                    "health_stability_slo_core_ok_rate": 0.74,
                    "health_stability_slo_core_streak_status": "OK",
                    "health_stability_slo_core_streak_count": 49,
                },
            },
        ]
    )
    provider_recovering = health_history_dashboard_status(
        [
            {
                "status": "FAIL",
                "warn_count": 3,
                "fail_count": 1,
                "top_issue": {"name": "health_stability_slo"},
                "metrics": {
                    "health_stability_slo_core_streak_status": "WARN",
                    "health_stability_slo_core_streak_count": 0,
                    "provider_recovery_premium_blocked": True,
                    "provider_recovery_primary_provider_issue": "alpaca_auth",
                },
            },
            {
                "status": "WARN",
                "warn_count": 2,
                "fail_count": 0,
                "top_issue": {"name": "alpaca_account_probe"},
                "metrics": {
                    "health_stability_slo_core_ok_rate": 0.76,
                    "health_stability_slo_core_streak_status": "OK",
                    "health_stability_slo_core_streak_count": 2,
                    "health_stability_slo_core_recovery_required_streak": 10,
                    "health_stability_slo_core_recovery_cycles_remaining": 8,
                    "health_stability_slo_core_recovery_progress": 0.2,
                    "health_stability_slo_core_recovery_state": "PENDING",
                    "provider_recovery_premium_blocked": True,
                    "provider_recovery_primary_provider_issue": "alpaca_auth",
                    "status_snapshot_alert_quality_sync_checked": True,
                    "health_stability_slo_latest_status_snapshot_alert_quality_blocker_issue_count": 0,
                    "alert_quality_missed_trigger_plan_review_due": False,
                },
            },
        ]
    )
    budget_ok = health_history_dashboard_status(
        [
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "health_history_budget_status": "OK",
                    "health_history_budget_pressure": False,
                    "health_history_budget_ratio": 0.8764,
                    "health_history_budget_margin_bytes": 926628,
                    "health_history_size_bytes": 6573372,
                    "health_history_max_bytes": 7500000,
                    "health_history_line_count": 150,
                },
            }
        ]
    )
    budget_warn = health_history_dashboard_status(
        [
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "health_stability_slo_latest_health_history_budget_status": "WARN",
                    "health_stability_slo_latest_health_history_budget_pressure": True,
                    "health_stability_slo_latest_health_history_budget_ratio": 0.94,
                    "health_stability_slo_latest_health_history_budget_margin_bytes": 450000,
                    "health_stability_slo_latest_health_history_size_bytes": 7050000,
                    "health_stability_slo_latest_health_history_max_bytes": 7500000,
                    "health_stability_slo_latest_health_history_line_count": 180,
                },
            }
        ]
    )
    budget_trimmed = health_history_dashboard_status(
        [
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "health_history_budget_status": "OK",
                    "health_history_budget_pressure": False,
                    "health_history_budget_ratio": 0.859,
                    "health_history_budget_margin_bytes": 1010000,
                    "health_history_size_bytes": 6490000,
                    "health_history_max_bytes": 7500000,
                    "health_history_line_count": 135,
                    "health_history_post_append_maintenance_action": "trimmed",
                    "health_history_post_append_maintenance_ok": True,
                    "health_history_post_append_maintenance_target_bytes": 6450000,
                    "health_history_post_append_maintenance_removed_lines": 3,
                    "health_history_post_append_maintenance_removed_bytes": 129711,
                    "health_history_post_append_maintenance_after_budget_ratio": 0.859,
                },
            }
        ]
    )
    alert_history_watch = health_history_dashboard_status(
        [
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "alert_quality_history_budget_status": "OK",
                    "alert_quality_history_budget_pressure": "CLEAR",
                    "alert_quality_history_budget_watch": True,
                    "alert_quality_history_budget_ratio": 0.8306,
                    "alert_quality_history_budget_projected_next_ratio": 0.836,
                    "alert_quality_history_budget_projected_pressure": "CLEAR",
                    "alert_quality_history_budget_margin_bytes": 320902,
                    "alert_quality_history_size_bytes": 1679098,
                    "alert_quality_history_max_bytes": 2000000,
                },
            }
        ]
    )
    health_history_watch = health_history_dashboard_status(
        [
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "health_history_budget_status": "OK",
                    "health_history_budget_pressure": False,
                    "health_history_maintenance_watch": True,
                    "health_history_budget_ratio": 0.804,
                    "health_history_projected_next_budget_ratio": 0.813,
                    "health_history_budget_margin_bytes": 1_400_000,
                    "health_history_size_bytes": 6_030_000,
                    "health_history_max_bytes": 7_500_000,
                    "health_history_line_count": 85,
                },
            }
        ]
    )
    current_report_watch = health_history_dashboard_status(
        [{"generated_at": "2026-06-10T11:59:00+00:00", "status": "OK", "warn_count": 0, "fail_count": 0}],
        current_report={
            "generated_at": "2026-06-10T12:00:00+00:00",
            "status": "OK",
            "warn_count": 0,
            "fail_count": 0,
            "metrics": {
                "alert_quality_history_budget_status": "OK",
                "alert_quality_history_budget_pressure": "CLEAR",
                "alert_quality_history_budget_watch": True,
                "alert_quality_history_budget_ratio": 0.8306,
                "alert_quality_history_budget_projected_next_ratio": 0.836,
                "alert_quality_history_budget_projected_pressure": "CLEAR",
            },
        },
    )
    budget_cleanup_failed = health_history_dashboard_status(
        [
            {
                "status": "OK",
                "warn_count": 0,
                "fail_count": 0,
                "metrics": {
                    "health_stability_slo_latest_health_history_post_append_maintenance_action": "error",
                    "health_stability_slo_latest_health_history_post_append_maintenance_ok": False,
                    "health_stability_slo_latest_health_history_post_append_maintenance_target_bytes": 6450000,
                },
            }
        ]
    )

    assert stable["label"] == "Estable"
    assert stable["tone"] == "buy"
    assert stable["ok_rate"] == 1.0
    assert "racha OK x2" in stable["detail"]
    assert unstable["label"] == "Inestable"
    assert unstable["tone"] == "avoid"
    assert "ultimo heartbeat" in unstable["detail"]
    assert recovered["label"] == "Recuperado"
    assert recovered["tone"] == "watch"
    assert recovered["recovered"] is True
    assert sync_warn["label"] == "Con avisos"
    assert sync_warn["tone"] == "watch"
    assert sync_warn["status_alert_quality_sync_issue_count"] == 1
    assert sync_warn["latest_status_alert_quality_issue_count"] == 0
    assert "sync status/calidad resuelto 1 recientes" in sync_warn["detail"]
    assert sync_warn["missed_trigger_review_due_count"] == 1
    assert sync_warn["recent_missed_trigger_review_due_count"] == 1
    assert sync_warn["latest_missed_trigger_review_due"] == False
    assert "revision gatillo resuelta 1 recientes" in sync_warn["detail"]
    assert drift_warn["label"] == "Con avisos"
    assert drift_warn["tone"] == "watch"
    assert drift_warn["status_snapshot_alert_quality_blocker_drift_count"] == 1
    assert drift_warn["latest_status_snapshot_alert_quality_blocker_drift_count"] == 1
    assert "drift snapshot/calidad activo 1" in drift_warn["detail"]
    assert premium_core["label"] == "Con avisos"
    assert premium_core["core_ok_rate"] == 1.0
    assert premium_core["current_core_streak_status"] == "OK"
    assert premium_core["current_core_streak_count"] == 49
    assert "core OK 100.0%" in premium_core["detail"]
    assert "core OK x49" in premium_core["detail"]
    assert provider_recovering["label"] == "Core recuperando"
    assert provider_recovering["tone"] == "watch"
    assert provider_recovering["known_provider_core_degraded"] is True
    assert provider_recovering["provider_recovery_premium_blocked"] is True
    assert provider_recovering["provider_recovery_primary_provider_issue"] == "alpaca_auth"
    assert provider_recovering["core_recovery_required_streak"] == 10
    assert provider_recovering["core_recovery_cycles_remaining"] == 8
    assert provider_recovering["core_recovery_progress"] == 0.2
    assert provider_recovering["core_recovery_state"] == "PENDING"
    assert "core recovery 2/10 faltan 8 20%" in provider_recovering["detail"]
    assert "externo premium bloqueado" in provider_recovering["detail"]
    assert budget_ok["label"] == "Estable"
    assert budget_ok["health_history_budget_status"] == "OK"
    assert budget_ok["health_history_budget_pressure"] is False
    assert budget_ok["health_history_budget_ratio"] == 0.8764
    assert budget_ok["health_history_budget_margin_bytes"] == 926628
    assert budget_ok["health_history_size_bytes"] == 6573372
    assert budget_ok["health_history_max_bytes"] == 7500000
    assert budget_ok["health_history_line_count"] == 150
    assert "health hist 6.27MB/7.15MB 87.6% OK margen 0.88MB lineas 150" in budget_ok["detail"]
    assert budget_warn["label"] == "Con avisos"
    assert budget_warn["tone"] == "watch"
    assert budget_warn["health_history_budget_status"] == "WARN"
    assert budget_warn["health_history_budget_pressure"] is True
    assert "health hist 6.72MB/7.15MB 94.0% WARN margen 0.43MB lineas 180" in budget_warn["detail"]
    assert budget_trimmed["label"] == "Estable"
    assert budget_trimmed["tone"] == "buy"
    assert budget_trimmed["health_history_post_append_maintenance_action"] == "trimmed"
    assert budget_trimmed["health_history_post_append_maintenance_ok"] is True
    assert budget_trimmed["health_history_post_append_maintenance_target_bytes"] == 6450000
    assert budget_trimmed["health_history_post_append_maintenance_removed_lines"] == 3
    assert budget_trimmed["health_history_post_append_maintenance_removed_bytes"] == 129711
    assert budget_trimmed["health_history_post_append_maintenance_after_budget_ratio"] == 0.859
    assert "post_append trimmed removed 3/129711B after 85.9%" in budget_trimmed["detail"]
    assert alert_history_watch["label"] == "Con avisos"
    assert alert_history_watch["tone"] == "watch"
    assert alert_history_watch["alert_quality_history_budget_status"] == "OK"
    assert alert_history_watch["alert_quality_history_budget_pressure"] == "CLEAR"
    assert alert_history_watch["alert_quality_history_budget_watch"] is True
    assert alert_history_watch["alert_quality_history_budget_ratio"] == 0.8306
    assert alert_history_watch["alert_quality_history_budget_projected_next_ratio"] == 0.836
    assert alert_history_watch["alert_quality_history_budget_projected_pressure"] == "CLEAR"
    assert alert_history_watch["alert_quality_history_budget_margin_bytes"] == 320902
    assert alert_history_watch["alert_quality_history_size_bytes"] == 1679098
    assert alert_history_watch["alert_quality_history_max_bytes"] == 2000000
    assert "alert hist 1.60MB/1.91MB 83.1% next 83.6% OK watch projected clear margen 0.31MB" in alert_history_watch["detail"]
    assert health_history_watch["label"] == "Con avisos"
    assert health_history_watch["tone"] == "watch"
    assert health_history_watch["health_history_maintenance_watch"] is True
    assert health_history_watch["health_history_budget_ratio"] == 0.804
    assert health_history_watch["health_history_projected_next_budget_ratio"] == 0.813
    assert "health hist 5.75MB/7.15MB 80.4% next 81.3% OK watch margen 1.34MB lineas 85" in health_history_watch["detail"]
    assert current_report_watch["sample_size"] == 2
    assert current_report_watch["label"] == "Con avisos"
    assert current_report_watch["alert_quality_history_budget_watch"] is True
    assert current_report_watch["alert_quality_history_budget_projected_next_ratio"] == 0.836
    assert "alert hist 83.1% next 83.6% OK watch projected clear" in current_report_watch["detail"]
    assert budget_cleanup_failed["label"] == "Con avisos"
    assert budget_cleanup_failed["tone"] == "watch"
    assert budget_cleanup_failed["health_history_post_append_maintenance_action"] == "error"
    assert budget_cleanup_failed["health_history_post_append_maintenance_ok"] is False


def test_health_history_display_table_sanitizes_recovered_traceback_details():
    table = health_history_display_table(
        [
            {
                "generated_at": "2026-06-10T18:51:18+00:00",
                "status": "FAIL",
                "ok": False,
                "fail_count": 1,
                "warn_count": 0,
                "operational_mode": "SYSTEM_FAIL",
                "operational_label": "Sistema falla",
                "metrics": {
                    "health_stability_slo_core_ok_rate": 0.74,
                    "health_stability_slo_core_streak_status": "OK",
                    "health_stability_slo_core_streak_count": 50,
                    "live_scan_freshness_status": "OK",
                    "live_scan_freshness_age_minutes": 3.24,
                    "confluence_freshness_status": "OK",
                    "confluence_freshness_age_minutes": 3.56,
                    "dashboard_render_probe_status": "OK",
                    "dashboard_render_text_length": 5170,
                    "dashboard_search_render_probe_status": "OK",
                    "dashboard_search_render_text_length": 15374,
                    "health_stability_slo_latest_dashboard_probes_fresh": True,
                    "health_stability_slo_dashboard_probes_fresh_streak": 9,
                    "health_stability_slo_latest_dashboard_render_age_minutes": 4.24,
                    "health_stability_slo_latest_dashboard_search_render_age_minutes": 4.68,
                    "chart_health_checked_count": 16,
                    "chart_health_warn_count": 1,
                    "chart_health_fail_count": 0,
                    "chart_health_max_age_minutes": 24.54,
                    "chart_health_max_cadence_lag_minutes": 3.24,
                    "status_snapshot_active_route_label": "Operar solo CRYPTO",
                    "status_snapshot_safe_mode": "NO_STOCK_OR_OPTIONS_ALERTS",
                    "provider_recovery_primary_provider_issue": "alpaca_auth",
                    "alpaca_account_error_category": "AUTH_INVALID",
                    "status_snapshot_alert_quality_sync_checked": True,
                    "status_snapshot_alert_quality_issue_count": 2,
                    "status_snapshot_alert_quality_false_negative_risk": "LOW",
                    "health_stability_slo_latest_status_snapshot_alert_quality_blocker_issue_count": 1,
                    "health_stability_slo_latest_status_snapshot_alert_quality_recurrent_blocker": (
                        "15m da entrada: WAIT"
                    ),
                    "health_stability_slo_latest_status_snapshot_alert_quality_recurrent_blocker_count": 47,
                    "health_stability_slo_latest_status_snapshot_alert_quality_persistent_blocker": (
                        "15m da entrada: WAIT"
                    ),
                    "health_stability_slo_latest_status_snapshot_alert_quality_persistent_blocker_minutes": 3.4,
                    "status_snapshot_daily_top_symbol": "LINK/USD",
                    "status_snapshot_daily_top_stage": "PROXIMA_ENTRADA",
                    "status_snapshot_daily_top_probability": 61,
                    "alert_quality_state": "WAITING",
                    "alert_quality_top_gate": "Esperar volumen",
                    "alert_quality_top_blocker": "1h confirma: Score tendencia 60",
                    "alert_quality_waiting_streak": 50,
                    "alert_quality_blocker_streak": 44,
                    "output_maintenance_operation_action_count": 71,
                    "output_maintenance_stale_output_removed_count": 67,
                    "output_maintenance_output_archive_count": 67,
                    "output_maintenance_operation_reclaimed_mb": 5.521,
                    "output_maintenance_local_cache_cleanup_status": "DONE",
                    "output_maintenance_local_cache_cleanup_removed_count": 4,
                    "output_maintenance_local_cache_cleanup_removed_mb": 18.113,
                    "output_maintenance_local_cache_cleanup_eligible_count": 9,
                    "output_maintenance_local_cache_cleanup_eligible_mb": 32.456,
                    "output_maintenance_runtime_footprint_mb": 47.031,
                    "output_maintenance_footprint_budget_status": "OK",
                    "output_maintenance_current_history_budget_status": "WARN",
                    "output_maintenance_current_history_budget_pressure": "NEAR_LIMIT",
                    "output_maintenance_current_history_budget_near_limit_count": 1,
                    "output_maintenance_current_history_budget_over_limit_count": 0,
                    "output_maintenance_current_history_budget_at_cap_count": 0,
                    "output_maintenance_current_history_budget_top_name": "alert_quality_history.jsonl",
                    "output_maintenance_current_history_budget_top_line_ratio": 0.852,
                    "output_maintenance_hygiene_label": "Protegido",
                    "output_maintenance_hygiene_protected": True,
                    "output_maintenance_external_archive_ready": True,
                    "health_stability_slo_latest_output_maintenance_protected": True,
                    "health_stability_slo_output_maintenance_protected_streak": 100,
                    "health_stability_slo_latest_dashboard_history_rows": 43,
                    "health_stability_slo_latest_output_maintenance_dashboard_history_rows": 41,
                    "health_stability_slo_latest_output_maintenance_dashboard_history_max_rows": 5000,
                    "health_stability_slo_latest_output_maintenance_dashboard_history_row_drift": 2,
                    "health_stability_slo_latest_output_maintenance_dashboard_history_drift_ratio": 0.0465,
                    "health_stability_slo_latest_output_maintenance_dashboard_history_drift_state": "OK",
                    "chart_realtime_health_status": "OK",
                    "chart_realtime_health_healthy": True,
                    "health_stability_slo_latest_chart_realtime_healthy": True,
                    "health_stability_slo_chart_realtime_healthy_streak": 88,
                    "alert_quality_missed_trigger_plan_active": True,
                    "alert_quality_missed_trigger_plan_symbol": "ETH/USD",
                    "alert_quality_missed_trigger_plan_readiness": 84.24,
                    "alert_quality_missed_trigger_plan_risk": "HIGH",
                    "alert_quality_missed_trigger_plan_review_due": True,
                    "alert_quality_missed_trigger_plan_review_status": "OVERDUE",
                    "alert_quality_missed_trigger_plan_review_overdue_cycles": 2,
                    "alert_quality_missed_trigger_plan_review_cycles_remaining": 0,
                    "alert_quality_missed_trigger_plan_review_cycle_minutes": 3.2,
                    "alert_quality_missed_trigger_plan_review_eta_minutes": 0.0,
                    "alert_quality_missed_trigger_plan_review_overdue_minutes": 6.4,
                    "alert_quality_missed_trigger_plan_review_progress": 1.042,
                    "alert_quality_missed_trigger_plan_severity": "ATTENTION",
                    "health_stability_slo_missed_trigger_plan_active": True,
                    "health_stability_slo_missed_trigger_plan_symbol": "ETH/USD",
                    "health_stability_slo_missed_trigger_plan_readiness": 84.24,
                    "health_stability_slo_missed_trigger_plan_streak": 10,
                    "health_stability_slo_missed_trigger_plan_count": 12,
                    "health_stability_slo_missed_trigger_plan_risk": "HIGH",
                    "health_stability_slo_missed_trigger_plan_review_due": True,
                    "health_stability_slo_missed_trigger_plan_review_status": "OVERDUE",
                    "health_stability_slo_missed_trigger_plan_review_overdue_cycles": 2,
                    "health_stability_slo_missed_trigger_plan_review_cycles_remaining": 0,
                    "health_stability_slo_missed_trigger_plan_review_cycle_minutes": 3.2,
                    "health_stability_slo_missed_trigger_plan_review_eta_minutes": 0.0,
                    "health_stability_slo_missed_trigger_plan_review_overdue_minutes": 6.4,
                    "health_stability_slo_missed_trigger_plan_review_progress": 1.042,
                    "health_stability_slo_missed_trigger_plan_severity": "ATTENTION",
                    "health_stability_slo_transient_lock_contention_count": 4,
                    "health_stability_slo_recent_transient_lock_contention_count": 2,
                    "realtime_lock_event": "blocked",
                    "realtime_lock_blocked_age_minutes": 0.2,
                },
                "top_issue": {
                    "name": "streamlit_app",
                    "detail": "HTTP 200, recent Streamlit log critical: Traceback (most recent call last):",
                },
            },
            {
                "generated_at": "2026-06-10T18:54:10+00:00",
                "status": "OK",
                "ok": True,
                "fail_count": 0,
                "warn_count": 0,
                "operational_mode": "MARKET_WAITING",
                "operational_label": "Mercado espera",
                "top_issue": {},
            },
        ]
    )

    assert list(table["status"]) == ["FAIL", "OK"]
    assert table.loc[0, "top_issue"] == "streamlit_app"
    assert table.loc[0, "core_ok_rate"] == 74.0
    assert table.loc[0, "core_streak"] == "OK x50"
    assert table.loc[0, "live_scan_freshness"] == "OK"
    assert table.loc[0, "confluence_freshness"] == "OK"
    assert table.loc[0, "live_scan_age_m"] == 3.2
    assert table.loc[0, "confluence_age_m"] == 3.6
    assert table.loc[0, "route"] == "Operar solo CRYPTO"
    assert table.loc[0, "safe_mode"] == "NO_STOCK_OR_OPTIONS_ALERTS"
    assert table.loc[0, "provider_issue"] == "alpaca_auth"
    assert table.loc[0, "alpaca_error"] == "AUTH_INVALID"
    assert table.loc[0, "render_probe"] == "OK"
    assert table.loc[0, "search_probe"] == "OK"
    assert table.loc[0, "render_chars"] == 5170
    assert table.loc[0, "search_chars"] == 15374
    assert table.loc[0, "ui_probe_fresh"] == True
    assert table.loc[0, "ui_probe_streak"] == 9
    assert table.loc[0, "ui_probe_age_m"] == 4.2
    assert table.loc[0, "ui_probe_search_age_m"] == 4.7
    assert table.loc[0, "chart_checked"] == 16
    assert table.loc[0, "chart_warn"] == 1
    assert table.loc[0, "chart_fail"] == 0
    assert table.loc[0, "chart_max_age_m"] == 24.5
    assert table.loc[0, "chart_lag_m"] == 3.2
    assert table.loc[0, "sync_checked"] == True
    assert table.loc[0, "sync_issues"] == 2
    assert table.loc[0, "snapshot_blocker_drift"] == 1
    assert table.loc[0, "snapshot_recurrent_blocker"] == "15m da entrada: WAIT"
    assert table.loc[0, "snapshot_recurrent_count"] == 47
    assert table.loc[0, "snapshot_persistent_blocker"] == "15m da entrada: WAIT"
    assert table.loc[0, "snapshot_persistent_m"] == 3.4
    assert table.loc[0, "cleanup_actions"] == 71
    assert table.loc[0, "cleanup_stale"] == 67
    assert table.loc[0, "cleanup_archived"] == 67
    assert table.loc[0, "cleanup_reclaimed_mb"] == 5.5
    assert table.loc[0, "cleanup_local_cache"] == "DONE"
    assert table.loc[0, "cleanup_local_cache_removed"] == 4
    assert table.loc[0, "cleanup_local_cache_mb"] == 18.1
    assert table.loc[0, "cleanup_local_cache_eligible"] == 9
    assert table.loc[0, "cleanup_local_cache_eligible_mb"] == 32.5
    assert table.loc[0, "runtime_mb"] == 47.0
    assert table.loc[0, "cleanup_budget"] == "OK"
    assert table.loc[0, "cleanup_current_history_budget"] == "WARN"
    assert table.loc[0, "cleanup_current_history_pressure"] == "NEAR_LIMIT"
    assert table.loc[0, "cleanup_current_history_near"] == 1
    assert table.loc[0, "cleanup_current_history_over"] == 0
    assert table.loc[0, "cleanup_current_history_cap"] == 0
    assert table.loc[0, "cleanup_current_history_top"] == "alert_quality_history.jsonl"
    assert table.loc[0, "cleanup_current_history_top_pct"] == 85.2
    assert table.loc[0, "cleanup_hygiene"] == "Protegido"
    assert table.loc[0, "cleanup_protected"] == True
    assert table.loc[0, "cleanup_archive_ready"] == True
    assert table.loc[0, "cleanup_slo_protected"] == True
    assert table.loc[0, "cleanup_slo_streak"] == 100
    assert table.loc[0, "dashboard_history_rows"] == 43
    assert table.loc[0, "cleanup_dashboard_history_rows"] == 41
    assert table.loc[0, "cleanup_dashboard_history_max_rows"] == 5000
    assert table.loc[0, "dashboard_history_drift"] == 2
    assert table.loc[0, "dashboard_history_drift_pct"] == 4.7
    assert table.loc[0, "dashboard_history_drift_state"] == "OK"
    assert table.loc[0, "chart_realtime_status"] == "OK"
    assert table.loc[0, "chart_realtime_report_healthy"] == True
    assert table.loc[0, "chart_realtime_healthy"] == True
    assert table.loc[0, "chart_realtime_streak"] == 88
    assert table.loc[0, "alert_quality_state"] == "WAITING"
    assert table.loc[0, "alert_quality_gate"] == "Esperar volumen"
    assert table.loc[0, "alert_quality_blocker"] == "1h confirma: Score tendencia 60"
    assert table.loc[0, "alert_waiting_streak"] == 50
    assert table.loc[0, "alert_blocker_streak"] == 44
    assert table.loc[0, "alert_false_negative_risk"] == "LOW"
    assert table.loc[0, "daily_plan_top_symbol"] == "LINK/USD"
    assert table.loc[0, "daily_plan_top_stage"] == "PROXIMA_ENTRADA"
    assert table.loc[0, "daily_plan_top_probability"] == 61.0
    assert table.loc[0, "alert_plan_active"] == True
    assert table.loc[0, "alert_plan_symbol"] == "ETH/USD"
    assert table.loc[0, "alert_plan_readiness"] == 84.2
    assert table.loc[0, "alert_plan_streak"] == 10
    assert table.loc[0, "alert_plan_count"] == 12
    assert table.loc[0, "alert_fn_risk"] == "HIGH"
    assert table.loc[0, "alert_review_due"] == True
    assert table.loc[0, "alert_review_status"] == "OVERDUE"
    assert table.loc[0, "alert_review_cycles_remaining"] == 0
    assert table.loc[0, "alert_review_eta_m"] == 0.0
    assert table.loc[0, "alert_review_overdue_m"] == 6.4
    assert table.loc[0, "alert_review_progress"] == 1.04
    assert table.loc[0, "alert_plan_severity"] == "ATTENTION"
    assert table.loc[0, "lock_event"] == "blocked"
    assert table.loc[0, "lock_age_m"] == 0.2
    assert table.loc[0, "lock_overlap_recent"] == 2
    assert table.loc[0, "lock_overlap_count"] == 4
    assert table.loc[1, "alert_plan_active"] == False
    assert table.loc[1, "route"] == "-"
    assert table.loc[1, "safe_mode"] == "-"
    assert table.loc[1, "provider_issue"] == "-"
    assert table.loc[1, "alpaca_error"] == "-"
    assert table.loc[1, "live_scan_freshness"] == "-"
    assert table.loc[1, "confluence_freshness"] == "-"
    assert pd.isna(table.loc[1, "live_scan_age_m"])
    assert pd.isna(table.loc[1, "confluence_age_m"])
    assert table.loc[1, "alert_plan_symbol"] == "-"
    assert pd.isna(table.loc[1, "alert_plan_readiness"])
    assert table.loc[1, "alert_review_due"] == False
    assert table.loc[1, "alert_review_status"] == "-"
    assert pd.isna(table.loc[1, "alert_review_cycles_remaining"])
    assert pd.isna(table.loc[1, "alert_review_eta_m"])
    assert pd.isna(table.loc[1, "alert_review_overdue_m"])
    assert pd.isna(table.loc[1, "alert_review_progress"])
    assert table.loc[1, "alert_plan_severity"] == "-"
    assert pd.isna(table.loc[1, "alert_plan_streak"])
    assert pd.isna(table.loc[1, "alert_plan_count"])
    assert table.loc[1, "render_probe"] == "-"
    assert table.loc[1, "search_probe"] == "-"
    assert pd.isna(table.loc[1, "render_chars"])
    assert pd.isna(table.loc[1, "search_chars"])
    assert table.loc[1, "ui_probe_fresh"] == False
    assert pd.isna(table.loc[1, "ui_probe_streak"])
    assert pd.isna(table.loc[1, "ui_probe_age_m"])
    assert pd.isna(table.loc[1, "ui_probe_search_age_m"])
    assert pd.isna(table.loc[1, "chart_checked"])
    assert pd.isna(table.loc[1, "chart_warn"])
    assert pd.isna(table.loc[1, "chart_fail"])
    assert pd.isna(table.loc[1, "chart_max_age_m"])
    assert pd.isna(table.loc[1, "chart_lag_m"])
    assert table.loc[1, "alert_false_negative_risk"] == "-"
    assert pd.isna(table.loc[1, "cleanup_actions"])
    assert table.loc[1, "cleanup_budget"] == "-"
    assert table.loc[1, "cleanup_hygiene"] == "-"
    assert table.loc[1, "cleanup_protected"] == False
    assert table.loc[1, "cleanup_archive_ready"] == False
    assert table.loc[1, "cleanup_slo_protected"] == False
    assert pd.isna(table.loc[1, "cleanup_slo_streak"])
    assert table.loc[1, "chart_realtime_healthy"] == False
    assert pd.isna(table.loc[1, "chart_realtime_streak"])
    assert table.loc[1, "alert_quality_state"] == "-"
    assert table.loc[1, "alert_quality_gate"] == "-"
    assert table.loc[1, "alert_quality_blocker"] == "-"
    assert pd.isna(table.loc[1, "alert_waiting_streak"])
    assert pd.isna(table.loc[1, "alert_blocker_streak"])
    assert table.loc[1, "daily_plan_top_symbol"] == "-"
    assert table.loc[1, "daily_plan_top_stage"] == "-"
    assert pd.isna(table.loc[1, "daily_plan_top_probability"])
    assert table.loc[1, "alert_fn_risk"] == "-"
    assert "Traceback" not in table.loc[0, "top_detail"]
    assert "fallo Python recuperado" in table.loc[0, "top_detail"]


def test_health_history_display_table_uses_slo_cache_eligible_aliases():
    table = health_history_display_table(
        [
            {
                "generated_at": "2026-06-10T18:55:10+00:00",
                "status": "WARN",
                "metrics": {
                    "output_maintenance_local_cache_cleanup_status": "SKIPPED",
                    "health_stability_slo_latest_output_maintenance_local_cache_cleanup_eligible_count": 2730,
                    "health_stability_slo_latest_output_maintenance_local_cache_cleanup_eligible_mb": 76.118,
                },
            }
        ]
    )

    assert table.loc[0, "cleanup_local_cache"] == "SKIPPED"
    assert table.loc[0, "cleanup_local_cache_eligible"] == 2730
    assert table.loc[0, "cleanup_local_cache_eligible_mb"] == 76.1


def test_stability_summary_dashboard_status_uses_official_health_summary():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 17,
            "ok_rate": 0.8824,
            "fail_count": 2,
            "warn_count": 0,
            "current_streak_status": "OK",
            "current_streak_count": 3,
            "incident_free_minutes": 18.5,
            "current_streak_minutes": 12.0,
            "last_issue": {"name": "external_disk"},
            "dominant_issue": {"name": "external_disk", "count": 2},
        }
    )

    assert status["label"] == "Recuperado"
    assert status["tone"] == "watch"
    assert status["recovered"] is True
    assert status["incident_free_minutes"] == 18.5
    assert status["dominant_issue"] == {"name": "external_disk", "count": 2}
    assert "OK 88.2%" in status["detail"]
    assert "racha OK x3" in status["detail"]
    assert "recuperado 18.5m" in status["detail"]
    assert "hist external_disk x2" in status["detail"]


def test_stability_summary_dashboard_status_flags_current_failure():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 17,
            "ok_rate": 0.8824,
            "fail_count": 2,
            "warn_count": 0,
            "current_streak_status": "FAIL",
            "current_streak_count": 1,
            "last_issue": {"name": "external_disk"},
        }
    )

    assert status["label"] == "Inestable"
    assert status["tone"] == "avoid"
    assert "ultimo external_disk" in status["detail"]


def test_stability_summary_dashboard_status_surfaces_known_premium_issue():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 100,
            "ok_rate": 0.52,
            "core_ok_rate": 0.98,
            "fail_count": 6,
            "warn_count": 42,
            "current_streak_status": "WARN",
            "current_streak_count": 17,
            "current_core_streak_status": "OK",
            "current_core_streak_count": 88,
            "dominant_issue": {"name": "chart_provider_effective", "count": 24},
            "known_issue": "PROVIDER_PREMIUM_BLOCKED",
            "known_issue_label": "Premium bloqueado",
            "known_issue_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN",
            "current_premium_blocked_streak": 24,
            "latest_output_maintenance_protected": True,
            "current_output_maintenance_protected_streak": 9,
            "latest_output_maintenance_label": "Limpieza aplicada",
            "latest_output_maintenance_budget_status": "OK",
            "latest_output_maintenance_runtime_mb": 47.0,
            "latest_live_data_fresh": True,
            "current_live_data_fresh_streak": 11,
            "latest_live_scan_age_minutes": 2.4,
            "latest_confluence_age_minutes": 2.6,
            "latest_notification_delivery_healthy": True,
            "current_notification_delivery_healthy_streak": 12,
            "latest_notification_delivery_mode": "local_file",
            "latest_notification_channel_count": 0,
            "latest_notification_actionable_ready_count": 0,
            "latest_dashboard_probes_fresh": True,
            "current_dashboard_probes_fresh_streak": 6,
            "latest_dashboard_render_age_minutes": 4.2,
            "latest_dashboard_search_render_age_minutes": 4.4,
            "latest_dashboard_render_text_length": 4532,
            "latest_dashboard_search_render_text_length": 13163,
            "latest_chart_realtime_healthy": True,
            "current_chart_realtime_healthy_streak": 8,
            "latest_chart_realtime_checked_count": 16,
            "latest_chart_realtime_max_age_minutes": 24.5,
            "latest_chart_realtime_operable_max_age_minutes": 8.5,
            "latest_chart_realtime_max_lag_minutes": 3.2,
            "latest_chart_realtime_operable_max_lag_minutes": 0.5,
            "latest_missed_trigger_plan_active": True,
            "latest_missed_trigger_plan_symbol": "ETH/USD",
            "latest_missed_trigger_plan_readiness": 84.2,
            "latest_missed_trigger_plan_risk": "HIGH",
            "latest_missed_trigger_plan_review_due": True,
            "latest_missed_trigger_plan_review_status": "OVERDUE",
            "latest_missed_trigger_plan_review_pressure": "OVERDUE",
            "latest_missed_trigger_plan_review_overdue_cycles": 2,
            "latest_missed_trigger_plan_review_cycles_remaining": 0,
            "latest_missed_trigger_plan_review_cycle_minutes": 3.2,
            "latest_missed_trigger_plan_review_eta_minutes": 0.0,
            "latest_missed_trigger_plan_review_overdue_minutes": 6.4,
            "latest_missed_trigger_plan_review_progress": 1.042,
            "latest_missed_trigger_plan_stale_candidate": False,
            "latest_missed_trigger_plan_auto_review_decision": "REVALIDATE_NOW",
            "latest_missed_trigger_plan_decision_action": "Revalidar ahora 15m/1h.",
            "latest_missed_trigger_plan_readiness_delta": 0.2,
            "latest_missed_trigger_plan_severity": "ATTENTION",
            "current_missed_trigger_plan_streak": 10,
            "missed_trigger_plan_count": 12,
            "missed_trigger_review_due_count": 3,
            "recent_missed_trigger_review_due_count": 2,
            "unresolved_missed_trigger_review_due_count": 2,
            "transient_lock_contention_count": 4,
            "recent_transient_lock_contention_count": 2,
            "lock_contention_profile": "SHORT_CHURN",
            "lock_contention_recommended_action": (
                "Stagger health/watchdog schedules if this persists; avoid manual lock cleanup while operable."
            ),
            "recent_lock_window": 20,
            "latest_realtime_lock_clear": True,
            "current_realtime_lock_clear_streak": 7,
            "latest_realtime_lock_operable": True,
            "current_realtime_lock_operable_streak": 9,
            "latest_realtime_lock_event": "released",
            "latest_realtime_lock_acquired_age_minutes": 0.2,
        }
    )

    assert status["label"] == "Premium bloqueado"
    assert status["tone"] == "watch"
    assert status["known_issue_streak"] == 24
    assert status["known_external_degraded"] is True
    assert status["latest_output_maintenance_protected"] is True
    assert status["current_output_maintenance_protected_streak"] == 9
    assert status["latest_output_maintenance_label"] == "Limpieza aplicada"
    assert status["latest_output_maintenance_budget_status"] == "OK"
    assert status["latest_output_maintenance_runtime_mb"] == 47.0
    assert status["latest_live_data_fresh"] is True
    assert status["current_live_data_fresh_streak"] == 11
    assert status["latest_live_scan_age_minutes"] == 2.4
    assert status["latest_confluence_age_minutes"] == 2.6
    assert status["latest_notification_delivery_healthy"] is True
    assert status["current_notification_delivery_healthy_streak"] == 12
    assert status["latest_notification_delivery_mode"] == "local_file"
    assert status["latest_notification_channel_count"] == 0
    assert status["latest_notification_actionable_ready_count"] == 0
    assert status["latest_dashboard_probes_fresh"] is True
    assert status["current_dashboard_probes_fresh_streak"] == 6
    assert status["latest_dashboard_render_age_minutes"] == 4.2
    assert status["latest_dashboard_search_render_age_minutes"] == 4.4
    assert status["latest_dashboard_render_text_length"] == 4532
    assert status["latest_dashboard_search_render_text_length"] == 13163
    assert status["latest_chart_realtime_healthy"] is True
    assert status["current_chart_realtime_healthy_streak"] == 8
    assert status["latest_chart_realtime_checked_count"] == 16
    assert status["latest_chart_realtime_max_age_minutes"] == 24.5
    assert status["latest_chart_realtime_operable_max_age_minutes"] == 8.5
    assert status["latest_chart_realtime_max_lag_minutes"] == 3.2
    assert status["latest_chart_realtime_operable_max_lag_minutes"] == 0.5
    assert "graficas OK x8 16 operable age 8.5m age 24.5m operable lag 0.5m lag 3.2m" in status["detail"]
    assert status["core_ok_rate"] == 0.98
    assert status["current_core_streak_status"] == "OK"
    assert status["current_core_streak_count"] == 88
    assert status["latest_missed_trigger_plan_active"] is True
    assert status["latest_missed_trigger_plan_symbol"] == "ETH/USD"
    assert status["latest_missed_trigger_plan_readiness"] == 84.2
    assert status["latest_missed_trigger_plan_risk"] == "HIGH"
    assert status["latest_missed_trigger_plan_review_due"] is True
    assert status["latest_missed_trigger_plan_review_status"] == "OVERDUE"
    assert status["latest_missed_trigger_plan_review_pressure"] == "OVERDUE"
    assert status["latest_missed_trigger_plan_review_overdue_cycles"] == 2
    assert status["latest_missed_trigger_plan_review_cycles_remaining"] == 0
    assert status["latest_missed_trigger_plan_review_cycle_minutes"] == 3.2
    assert status["latest_missed_trigger_plan_review_eta_minutes"] == 0.0
    assert status["latest_missed_trigger_plan_review_overdue_minutes"] == 6.4
    assert status["latest_missed_trigger_plan_review_progress"] == 1.042
    assert status["latest_missed_trigger_plan_stale_candidate"] is False
    assert status["latest_missed_trigger_plan_auto_review_decision"] == "REVALIDATE_NOW"
    assert status["latest_missed_trigger_plan_decision_action"] == "Revalidar ahora 15m/1h."
    assert status["latest_missed_trigger_plan_readiness_delta"] == 0.2
    assert status["latest_missed_trigger_plan_severity"] == "ATTENTION"
    assert status["current_missed_trigger_plan_streak"] == 10
    assert status["missed_trigger_plan_count"] == 12
    assert status["missed_trigger_review_due_count"] == 3
    assert status["recent_missed_trigger_review_due_count"] == 2
    assert status["unresolved_missed_trigger_review_due_count"] == 2
    assert status["transient_lock_contention_count"] == 4
    assert status["recent_transient_lock_contention_count"] == 2
    assert status["lock_contention_profile"] == "SHORT_CHURN"
    assert "presion OVERDUE" in status["detail"]
    assert "trend +0.2" in status["detail"]
    assert "decision REVALIDATE_NOW" in status["detail"]
    assert "Stagger health/watchdog schedules" in status["lock_contention_recommended_action"]
    assert status["recent_lock_window"] == 20
    assert status["latest_realtime_lock_clear"] is True
    assert status["current_realtime_lock_clear_streak"] == 7
    assert status["latest_realtime_lock_operable"] is True
    assert status["current_realtime_lock_operable_streak"] == 9
    assert status["latest_realtime_lock_event"] == "released"
    assert status["latest_realtime_lock_acquired_age_minutes"] == 0.2
    assert "core OK 98.0%" in status["detail"]
    assert "core interno estable" in status["detail"]
    assert "conocido Premium bloqueado x24" in status["detail"]
    assert "limpieza protegida x9 Limpieza aplicada budget OK 47.0MB" in status["detail"]
    assert "datos live OK x11 scan 2.4m conf 2.6m" in status["detail"]
    assert "notificaciones OK x12 local" in status["detail"]
    assert "UI probes OK x6 render 4532 search 13163 age 4.2m/4.4m" in status["detail"]
    assert "graficas OK x8 16 operable age 8.5m age 24.5m operable lag 0.5m lag 3.2m" in status["detail"]
    assert (
        "alerta watch ETH/USD x10 84.2% HIGH revision overdue +2/6.4m progreso 1.04 "
        "presion OVERDUE trend +0.2 decision REVALIDATE_NOW ATTENTION"
    ) in status["detail"]
    assert "revision gatillo activa 2" in status["detail"]
    assert "locks recientes 2/hist 4 en 20 SHORT_CHURN" in status["detail"]
    assert "accion lock Stagger health/watchdog schedules" in status["detail"]
    assert "lock limpio x7 released" in status["detail"]
    assert "accion Configurar POLYGON_API_KEY/POLYGON_API_TOKEN" in status["detail"]


def test_stability_summary_dashboard_status_treats_current_core_streak_as_external_degraded():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 100,
            "ok_rate": 0.0,
            "core_ok_rate": 0.70,
            "fail_count": 11,
            "warn_count": 89,
            "current_streak_status": "WARN",
            "current_streak_count": 18,
            "current_core_streak_status": "OK",
            "current_core_streak_count": 16,
            "dominant_issue": {"name": "alert_quality_report", "count": 44},
            "known_issue": "PROVIDER_PREMIUM_BLOCKED",
            "known_issue_label": "Premium bloqueado",
            "known_issue_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN",
            "current_premium_blocked_streak": 29,
        }
    )

    assert status["label"] == "Premium bloqueado"
    assert status["tone"] == "watch"
    assert status["known_external_degraded"] is True
    assert "core OK 70.0%" in status["detail"]
    assert "core OK x16" in status["detail"]
    assert "core interno estable" in status["detail"]


def test_stability_summary_dashboard_status_uses_external_blocking_recovery_label():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 100,
            "ok_rate": 0.0,
            "core_ok_rate": 0.95,
            "fail_count": 1,
            "warn_count": 99,
            "current_streak_status": "WARN",
            "current_streak_count": 3,
            "current_core_streak_status": "OK",
            "current_core_streak_count": 1,
            "core_recovery_required_streak": 10,
            "core_recovery_cycles_remaining": 9,
            "core_recovery_progress": 0.1,
            "core_recovery_state": "PENDING",
            "known_issue": "PROVIDER_PREMIUM_BLOCKED",
            "known_issue_label": "Premium bloqueado",
            "known_issue_action": "Corregir credenciales/permisos del proveedor premium antes de operar acciones.",
            "current_premium_blocked_streak": 85,
            "external_blocking": True,
            "operational_slo_label": "Core recuperando / externo bloqueado",
        }
    )

    assert status["label"] == "Premium bloqueado"
    assert status["tone"] == "watch"
    assert status["known_external_degraded"] is True
    assert status["external_blocking"] is True
    assert status["operational_slo_label"] == "Core recuperando / externo bloqueado"
    assert status["core_recovery_required_streak"] == 10
    assert status["core_recovery_cycles_remaining"] == 9
    assert status["core_recovery_progress"] == 0.1
    assert status["core_recovery_state"] == "PENDING"
    assert "core OK 95.0%" in status["detail"]
    assert "core OK x1" in status["detail"]
    assert "core recovery 1/10 faltan 9 10%" in status["detail"]
    assert "core interno estable" in status["detail"]
    assert "operativo Core recuperando / externo bloqueado" in status["detail"]


def test_stability_summary_dashboard_status_prioritizes_disk_attention():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 100,
            "ok_rate": 0.0,
            "core_ok_rate": 0.91,
            "fail_count": 4,
            "warn_count": 96,
            "current_streak_status": "WARN",
            "current_streak_count": 1,
            "current_core_streak_status": "OK",
            "current_core_streak_count": 1,
            "known_issue": "PROVIDER_PREMIUM_BLOCKED",
            "known_issue_label": "Premium bloqueado",
            "known_issue_action": "Corregir credenciales Alpaca.",
            "external_blocking": True,
            "operational_slo_label": "Core recuperando / externo bloqueado",
            "disk_free_drop_pressure": "ATTENTION",
            "disk_free_drop_source": "OUTSIDE_PROJECT",
            "disk_free_drop_gb": 51.1,
            "latest_disk_free_gb": 49.3,
            "latest_disk_free_pct": 21.6,
            "disk_free_drop_recommended_action": (
                "Inspect system storage, Downloads, VM/cache writers, or external ingest."
            ),
        }
    )

    assert status["label"] == "Disco bajo"
    assert status["tone"] == "watch"
    assert status["disk_free_drop_pressure"] == "ATTENTION"
    assert status["disk_free_drop_source"] == "outside_project"
    assert status["disk_free_drop_gb"] == 51.1
    assert status["latest_disk_free_gb"] == 49.3
    assert status["latest_disk_free_pct"] == 21.6
    assert "conocido Premium bloqueado" in status["detail"]
    assert "disco attention -51.1GB outside_project libre 49.3GB/21.6%" in status["detail"]
    assert "accion disco Inspect system storage" in status["detail"]


def test_mac_storage_pressure_dashboard_status_surfaces_top_source():
    status = mac_storage_pressure_dashboard_status(
        {
            "checks": [
                {
                    "name": "disk_space",
                    "status": "OK",
                    "detail": "49.30 GiB free",
                    "free_gb": 49.3,
                    "free_pct": 21.6,
                },
                {
                    "name": "local_storage_pressure_sources",
                    "status": "INFO",
                    "detail": "Local storage pressure sources: Downloads 36.63 GiB",
                    "pressure_active": True,
                    "cached": True,
                    "cache_age_minutes": 0.5,
                    "top_entries": [
                        {
                            "name": "Downloads",
                            "size_gb": 36.6346,
                            "cleanup_policy": "MANUAL_REVIEW_REQUIRED",
                        },
                        {
                            "name": "Library/Caches",
                            "size_gb": 1.6845,
                            "cleanup_policy": "SAFE_CACHE_REVIEW",
                        },
                    ],
                    "safe_cleanup_entries": [{"name": "Library/Caches", "size_gb": 1.6845}],
                    "cleanup_plan_state": "MANUAL_REVIEW_REQUIRED",
                    "cleanup_priority": "manual_review",
                    "cleanup_automation_ready": False,
                    "cleanup_automation_blocked_reason": "manual_top_source",
                    "cleanup_action": (
                        "Review user storage manually: Downloads 36.6GiB. "
                        "Safe cache candidates: Library/Caches 1.7GiB."
                    ),
                },
            ]
        },
        {"label": "OK", "tone": "buy", "detail": "50GB libres"},
    )

    assert status["label"] == "Downloads 36.6GB"
    assert status["tone"] == "watch"
    assert status["top_name"] == "Downloads"
    assert status["top_gb"] == 36.6346
    assert status["free_gb"] == 49.3
    assert status["free_pct"] == 21.6
    assert status["cached"] is True
    assert status["top_cleanup_policy"] == "MANUAL_REVIEW_REQUIRED"
    assert status["safe_cleanup_name"] == "Library/Caches"
    assert status["safe_cleanup_gb"] == 1.6845
    assert status["cleanup_action"].startswith("Review user storage manually")
    assert status["cleanup_plan_state"] == "MANUAL_REVIEW_REQUIRED"
    assert status["cleanup_priority"] == "manual_review"
    assert status["cleanup_automation_ready"] is False
    assert status["cleanup_automation_blocked_reason"] == "manual_top_source"
    assert "top Downloads 36.6GB" in status["detail"]
    assert "politica manual_review_required" in status["detail"]
    assert "cache segura Library/Caches 1.7GB" in status["detail"]
    assert "plan manual_review_required" in status["detail"]
    assert "prioridad manual_review" in status["detail"]
    assert "auto bloqueada" in status["detail"]
    assert "bloqueo manual_top_source" in status["detail"]
    assert "accion Review user storage manually" in status["detail"]
    assert "siguiente Library/Caches 1.7GB" in status["detail"]
    assert "cache 0.5m" in status["detail"]


def test_stability_summary_dashboard_status_surfaces_status_quality_sync_issues():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 50,
            "ok_rate": 0.94,
            "fail_count": 0,
            "warn_count": 3,
            "current_streak_status": "WARN",
            "current_streak_count": 2,
            "status_alert_quality_sync_issue_count": 5,
            "recent_status_alert_quality_sync_issue_count": 2,
            "latest_status_alert_quality_issue_count": 1,
            "latest_status_alert_quality_sync_checked": True,
        }
    )

    assert status["label"] == "Con avisos"
    assert status["status_alert_quality_sync_issue_count"] == 5
    assert status["recent_status_alert_quality_sync_issue_count"] == 2
    assert status["unresolved_status_alert_quality_sync_issue_count"] == 2
    assert status["latest_status_alert_quality_sync_checked"] is True
    assert "sync status/calidad activo 2" in status["detail"]


def test_stability_summary_dashboard_status_treats_active_sync_issue_as_warning():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 12,
            "ok_rate": 1.0,
            "fail_count": 0,
            "warn_count": 0,
            "current_streak_status": "OK",
            "current_streak_count": 12,
            "status_alert_quality_sync_issue_count": 1,
            "recent_status_alert_quality_sync_issue_count": 1,
            "latest_status_alert_quality_issue_count": 1,
            "latest_status_alert_quality_sync_checked": True,
        }
    )

    assert status["label"] == "Con avisos"
    assert status["tone"] == "watch"
    assert "sync status/calidad activo 1" in status["detail"]


def test_stability_summary_dashboard_status_surfaces_snapshot_blocker_drift():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 12,
            "ok_rate": 1.0,
            "fail_count": 0,
            "warn_count": 0,
            "current_streak_status": "OK",
            "current_streak_count": 12,
            "latest_status_alert_quality_sync_checked": True,
            "latest_status_snapshot_alert_quality_blocker_issue_count": 2,
        }
    )

    assert status["label"] == "Con avisos"
    assert status["tone"] == "watch"
    assert status["latest_status_snapshot_alert_quality_blocker_issue_count"] == 2
    assert "drift snapshot/calidad 2" in status["detail"]


def test_stability_summary_dashboard_status_surfaces_dashboard_history_drift():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 12,
            "ok_rate": 1.0,
            "fail_count": 0,
            "warn_count": 0,
            "current_streak_status": "OK",
            "current_streak_count": 12,
            "latest_output_maintenance_protected": True,
            "current_output_maintenance_protected_streak": 4,
            "latest_output_maintenance_label": "Limpieza aplicada",
            "latest_output_maintenance_budget_status": "OK",
            "latest_output_maintenance_runtime_mb": 31.0,
            "latest_dashboard_history_rows": 56,
            "latest_output_maintenance_dashboard_history_rows": 54,
            "latest_output_maintenance_dashboard_history_max_rows": 5000,
            "latest_output_maintenance_dashboard_history_row_drift": 2,
            "latest_output_maintenance_dashboard_history_drift_ratio": 0.0357,
            "latest_output_maintenance_dashboard_history_drift_state": "OK",
        }
    )

    assert status["label"] == "Estable"
    assert status["latest_dashboard_history_rows"] == 56
    assert status["latest_output_maintenance_dashboard_history_rows"] == 54
    assert status["latest_output_maintenance_dashboard_history_max_rows"] == 5000
    assert status["latest_output_maintenance_dashboard_history_row_drift"] == 2
    assert status["latest_output_maintenance_dashboard_history_drift_ratio"] == 0.0357
    assert status["latest_output_maintenance_dashboard_history_drift_state"] == "OK"
    assert "hist dash 54/live 56 drift +2 ok/5000" in status["detail"]


def test_stability_summary_dashboard_status_marks_resolved_sync_history_stable():
    status = stability_summary_dashboard_status(
        {
            "sample_size": 12,
            "ok_rate": 1.0,
            "fail_count": 0,
            "warn_count": 0,
            "current_streak_status": "OK",
            "current_streak_count": 12,
            "status_alert_quality_sync_issue_count": 1,
            "recent_status_alert_quality_sync_issue_count": 0,
            "latest_status_alert_quality_issue_count": 0,
            "latest_status_alert_quality_sync_checked": True,
        }
    )

    assert status["label"] == "Estable"
    assert status["tone"] == "buy"
    assert "sync status/calidad resuelto hist 1" in status["detail"]


def test_load_health_history_reads_valid_jsonl(tmp_path, monkeypatch):
    history = tmp_path / "alerts" / "roxy_realtime_history.jsonl"
    history.parent.mkdir()
    history.write_text('{"status":"OK"}\nnot-json\n{"status":"WARN"}\n')
    monkeypatch.setattr(streamlit_app, "ALERTS_DIR", tmp_path / "alerts")

    rows = load_health_history(limit=3)

    assert [row["status"] for row in rows] == ["OK", "WARN"]


def test_disk_dashboard_status_maps_free_space_to_tone(tmp_path, monkeypatch):
    Usage = namedtuple("usage", "total used free")

    monkeypatch.setattr(streamlit_app.shutil, "disk_usage", lambda path: Usage(total=100 * 1024**3, used=92 * 1024**3, free=8 * 1024**3))
    low = disk_dashboard_status(tmp_path, warn_free_gb=20, fail_free_gb=5)

    monkeypatch.setattr(streamlit_app.shutil, "disk_usage", lambda path: Usage(total=100 * 1024**3, used=40 * 1024**3, free=60 * 1024**3))
    ok = disk_dashboard_status(tmp_path, warn_free_gb=20, fail_free_gb=5)

    assert low["label"] == "Bajo"
    assert low["tone"] == "watch"
    assert ok["label"] == "OK"
    assert ok["tone"] == "buy"


def test_local_training_media_dashboard_status_maps_realtime_check():
    small = local_training_media_dashboard_status(
        {
            "checks": [
                {
                    "name": "local_training_media",
                    "status": "OK",
                    "state": "LOCAL_SMALL",
                    "size_gb": 0.02,
                    "detail": "training_videos ocupa 0.02 GiB local",
                }
            ]
        }
    )
    growing = local_training_media_dashboard_status(
        {
            "checks": [
                {
                    "name": "local_training_media",
                    "status": "WARN",
                    "state": "LOCAL_GROWING",
                    "size_gb": 6.0,
                    "detail": "training_videos ocupa 6.00 GiB local; preparar migracion",
                    "external_suggestion": "/Volumes/RoxyData/MacArchive/roxy_trading/training_videos",
                }
            ]
        }
    )
    linked = local_training_media_dashboard_status(
        {
            "checks": [
                {
                    "name": "local_training_media",
                    "status": "OK",
                    "state": "EXTERNAL_LINKED",
                    "detail": "training_videos esta enlazado a /Volumes/RoxyData/MacArchive/roxy_trading/training_videos",
                }
            ]
        }
    )

    assert small["label"] == "0.02 GB"
    assert small["tone"] == "buy"
    assert "0.02 GiB" in small["detail"]
    assert growing["label"] == "Crece"
    assert growing["tone"] == "watch"
    assert growing["external_suggestion"].endswith("/roxy_trading/training_videos")
    assert linked["label"] == "Externa"
    assert linked["tone"] == "buy"


def test_alert_gate_summary_dashboard_status_flags_realtime_blocks():
    status = alert_gate_summary_dashboard_status(
        {
            "total_opportunities": 3,
            "notifications_ready": 0,
            "blocked_realtime_count": 2,
            "top_gate_label": "Bloqueado por datos realtime",
            "avg_readiness": 64.4,
        }
    )

    assert status["label"] == "Datos bloquean"
    assert status["tone"] == "avoid"
    assert "readiness 64%" in status["detail"]


def test_alert_quality_report_dashboard_status_tracks_waiting_streak():
    status = alert_quality_report_dashboard_status(
        {
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 8,
                "waiting_streak": 4,
                "avg_readiness": 61.3,
                "readiness_delta": -6.4,
                "latest_top_blocker": "15m da entrada: WAIT",
                "dominant_blocker": {"name": "Volumen acompana", "count": 8},
                "blocker_category": "MARKET_TRIGGER_WAIT",
                "recommended_action": "Mantener watchlist; no alertar hasta que 15m confirme entrada",
                "rotation_candidates": ["AMAT 63.6% C", "NVDA 59.0% B"],
                "missed_opportunity_watch": True,
                "missed_opportunity_risk": "MEDIUM",
                "missed_trigger_plan": {
                    "active": True,
                    "primary_symbol": "AMAT",
                    "primary_readiness": 63.6,
                    "risk": "MEDIUM",
                    "exit_condition": "No alertar hasta que 15m confirme entrada y la grafica realtime siga operable.",
                },
            },
            "latest_entry": {
                "top_symbol": "AMAT",
                "top_next_action": "Esperar gatillo BUY en 15m.",
            },
        }
    )

    assert status["label"] == "Esperando"
    assert status["tone"] == "watch"
    assert "racha espera 4" in status["detail"]
    assert "readiness 61%" in status["detail"]
    assert "trend -6.4" in status["detail"]
    assert "recurrente Volumen acompana x8" in status["detail"]
    assert status["readiness_delta"] == -6.4
    assert status["dominant_blocker"] == {"name": "Volumen acompana", "count": 8}
    assert status["blocker_category"] == "MARKET_TRIGGER_WAIT"
    assert "tipo MARKET_TRIGGER_WAIT" in status["detail"]
    assert "vigilar oportunidad MEDIUM" in status["detail"]
    assert "plan AMAT 63.6%" in status["detail"]
    assert "salida No alertar hasta que 15m confirme entrada" in status["detail"]
    assert status["missed_trigger_plan"]["primary_symbol"] == "AMAT"
    assert "Mantener watchlist" in status["detail"]
    assert status["rotation_candidates"] == [
        {"symbol": "AMAT", "readiness": 63.6, "quality": "C", "label": "AMAT 63.6% C"},
        {"symbol": "NVDA", "readiness": 59.0, "quality": "B", "label": "NVDA 59.0% B"},
    ]
    assert "top AMAT" in status["detail"]
    assert "Esperar gatillo BUY en 15m." in status["detail"]


def test_alert_quality_report_dashboard_status_uses_top_level_recurrent_blocker_aliases():
    status = alert_quality_report_dashboard_status(
        {
            "state": "WAITING",
            "notifications_ready": 0,
            "total_opportunities": 7,
            "waiting_streak": 34,
            "latest_top_blocker_streak": 34,
            "recurrent_blocker": "15m da entrada: WAIT",
            "recurrent_blocker_count": 40,
            "persistent_blocker": "15m da entrada: WAIT",
            "persistent_blocker_minutes": 28.5,
            "blocker_category": "MARKET_TRIGGER_WAIT",
            "false_negative_risk": "LOW",
            "history_count": 500,
            "history_min_entries": 120,
            "history_size_bytes": 1696044,
            "history_max_bytes": 2000000,
        }
    )

    assert status["label"] == "Esperando"
    assert status["tone"] == "watch"
    assert status["waiting_streak"] == 34
    assert status["dominant_blocker"] == {"name": "15m da entrada: WAIT", "count": 40}
    assert "0/7 listas" in status["detail"]
    assert "racha espera 34" in status["detail"]
    assert "bloqueador x34" in status["detail"]
    assert "persistente 28.5m" in status["detail"]
    assert "recurrente 15m da entrada: WAIT x40" in status["detail"]
    assert "historial 500/min 120 1.62MB/1.91MB" in status["detail"]
    assert status["history_count"] == 500
    assert status["history_min_entries"] == 120
    assert status["history_size_bytes"] == 1696044
    assert status["history_max_bytes"] == 2000000
    assert status["history_budget_status"] == "OK"
    assert status["history_size_budget_ratio"] == 0.848022
    assert status["history_size_budget_margin"] == 303956
    assert "historial 500/min 120 1.62MB/1.91MB 84.8% margen 0.29MB" in status["detail"]


def test_alert_quality_report_dashboard_status_warns_on_history_budget_pressure():
    status = alert_quality_report_dashboard_status(
        {
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 7,
                "waiting_streak": 9,
            },
            "history_count": 500,
            "history_min_entries": 120,
            "history_size_bytes": 2200000,
            "history_max_bytes": 2000000,
        }
    )

    assert status["label"] == "Historial revisar"
    assert status["tone"] == "watch"
    assert status["history_budget_status"] == "WARN"
    assert status["history_count"] == 500
    assert status["history_size_budget_ratio"] == 1.1
    assert status["history_size_budget_margin"] == -200000
    assert "historial 500/min 120 2.10MB/1.91MB WARN 110.0% margen -0.19MB" in status["detail"]


def test_alert_quality_report_dashboard_status_accepts_top_level_missed_trigger_aliases():
    status = alert_quality_report_dashboard_status(
        {
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 3,
                "waiting_streak": 50,
                "silence_mode": "MISSED_TRIGGER_WATCH",
                "false_negative_risk": "HIGH",
                "missed_opportunity_watch": True,
                "missed_opportunity_risk": "HIGH",
            },
            "missed_trigger_plan_active": True,
            "missed_trigger_plan_symbol": "BNB/USD",
            "missed_trigger_plan_readiness": 84.2,
            "missed_trigger_plan_risk": "HIGH",
            "missed_trigger_plan_review_due": True,
            "missed_trigger_plan_review_status": "OVERDUE",
            "missed_trigger_plan_review_pressure": "STALE_OVERDUE",
            "missed_trigger_plan_review_overdue_cycles": 2,
            "missed_trigger_plan_review_cycles_remaining": 0,
            "missed_trigger_plan_review_cycle_minutes": 3.2,
            "missed_trigger_plan_review_eta_minutes": 0.0,
            "missed_trigger_plan_review_overdue_minutes": 6.4,
            "missed_trigger_plan_review_progress": 1.042,
            "missed_trigger_plan_stale_candidate": True,
            "missed_trigger_plan_auto_review_decision": "ROTATE_OR_DISCARD",
            "missed_trigger_plan_decision_action": "Rotar o descartar el candidato.",
            "missed_trigger_plan_readiness_delta": 0.0,
            "missed_trigger_plan_review_cadence": "manual_15m_1h_revalidation",
            "missed_trigger_plan_review_action": "Revalidar manualmente 15m/1h.",
            "missed_trigger_plan_severity": "ATTENTION",
            "missed_trigger_plan_exit": "No alertar hasta que 15m confirme entrada.",
        }
    )

    assert status["missed_trigger_plan"]["active"] is True
    assert status["missed_trigger_plan"]["primary_symbol"] == "BNB/USD"
    assert status["missed_trigger_plan"]["primary_readiness"] == 84.2
    assert status["missed_trigger_plan"]["review_due"] is True
    assert status["missed_trigger_plan"]["review_status"] == "OVERDUE"
    assert status["missed_trigger_plan"]["review_pressure"] == "STALE_OVERDUE"
    assert status["missed_trigger_plan"]["review_overdue_cycles"] == 2
    assert status["missed_trigger_plan"]["review_cycle_minutes"] == 3.2
    assert status["missed_trigger_plan"]["review_eta_minutes"] == 0.0
    assert status["missed_trigger_plan"]["review_overdue_minutes"] == 6.4
    assert status["missed_trigger_plan"]["stale_candidate"] is True
    assert status["missed_trigger_plan"]["auto_review_decision"] == "ROTATE_OR_DISCARD"
    assert status["missed_trigger_plan"]["decision_action"] == "Rotar o descartar el candidato."
    assert status["missed_trigger_plan"]["readiness_delta"] == 0.0
    assert status["missed_trigger_review_action"] == "Revalidar manualmente 15m/1h."
    assert status["missed_trigger_review_cadence"] == "manual_15m_1h_revalidation"
    assert status["missed_trigger_review_progress"] == 1.042
    assert status["missed_trigger_review_due"] is True
    assert status["missed_trigger_review_overdue"] is True
    assert status["missed_trigger_review_status"] == "OVERDUE"
    assert status["missed_trigger_review_pressure"] == "STALE_OVERDUE"
    assert status["missed_trigger_review_overdue_cycles"] == 2
    assert status["missed_trigger_review_cycles_remaining"] == 0
    assert status["missed_trigger_review_eta_minutes"] == 0.0
    assert status["missed_trigger_review_overdue_minutes"] == 6.4
    assert status["missed_trigger_review_severity"] == "ATTENTION"
    assert status["missed_trigger_stale_candidate"] is True
    assert status["missed_trigger_auto_review_decision"] == "ROTATE_OR_DISCARD"
    assert status["missed_trigger_decision_action"] == "Rotar o descartar el candidato."
    assert status["missed_trigger_readiness_delta"] == 0.0
    assert "plan BNB/USD 84.2%" in status["detail"]
    assert "revision overdue +2/6.4m" in status["detail"]
    assert "progreso revision 1.04" in status["detail"]
    assert "presion STALE_OVERDUE" in status["detail"]
    assert "decision ROTATE_OR_DISCARD" in status["detail"]
    assert "accion decision Rotar o descartar el candidato." in status["detail"]
    assert "cadencia manual_15m_1h_revalidation" in status["detail"]
    assert "accion revision Revalidar manualmente 15m/1h." in status["detail"]
    assert "severidad ATTENTION" in status["detail"]


def test_alert_quality_report_dashboard_status_accepts_top_level_confirmation_wait_aliases():
    status = alert_quality_report_dashboard_status(
        {
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 4,
                "waiting_streak": 50,
                "silence_mode": "HEALTHY_WAIT",
                "false_negative_risk": "LOW",
            },
            "confirmation_wait_plan_active": True,
            "confirmation_wait_plan_symbol": "ETH/USD",
            "confirmation_wait_plan_readiness": 89.5,
            "confirmation_wait_plan_risk": "LOW",
            "confirmation_wait_plan_review_due": True,
            "confirmation_wait_plan_review_status": "OVERDUE",
            "confirmation_wait_plan_review_overdue_cycles": 2,
            "confirmation_wait_plan_review_cycles_remaining": 0,
            "confirmation_wait_plan_review_progress": 1.042,
            "confirmation_wait_plan_review_cycle_minutes": 1.0,
            "confirmation_wait_plan_review_eta_minutes": 0.0,
            "confirmation_wait_plan_review_overdue_minutes": 2.0,
            "confirmation_wait_plan_severity": "ATTENTION",
            "confirmation_wait_plan_max_watch_cycles": 48,
            "confirmation_wait_plan_review_action": "Revalidar manualmente 2h/4h.",
            "confirmation_wait_plan_exit": "No alertar hasta que 2h/4h confirme.",
        }
    )

    assert status["confirmation_wait_plan"]["active"] is True
    assert status["confirmation_wait_plan"]["primary_symbol"] == "ETH/USD"
    assert status["confirmation_wait_plan"]["primary_readiness"] == 89.5
    assert status["confirmation_wait_plan"]["review_due"] is True
    assert status["confirmation_wait_plan"]["review_status"] == "OVERDUE"
    assert status["confirmation_wait_plan"]["review_overdue_cycles"] == 2
    assert status["confirmation_wait_plan"]["review_cycle_minutes"] == 1.0
    assert status["confirmation_wait_plan"]["review_eta_minutes"] == 0.0
    assert status["confirmation_wait_plan"]["review_overdue_minutes"] == 2.0
    assert status["confirmation_wait_plan"]["review_action"] == "Revalidar manualmente 2h/4h."
    assert "confirmacion ETH/USD 89.5%" in status["detail"]
    assert "revision confirmacion overdue +2/2.0m" in status["detail"]
    assert "confirmacion severidad ATTENTION" in status["detail"]
    assert "salida confirmacion No alertar hasta que 2h/4h confirme." in status["detail"]


def test_alert_silence_kpi_status_marks_healthy_wait():
    status = alert_silence_kpi_status(
        {
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 3,
                "silence_mode": "HEALTHY_WAIT",
                "silence_reason": "Mercado cerrado; la entrada debe revalidarse en apertura",
                "false_negative_risk": "LOW",
            }
        }
    )

    assert status["label"] == "Espera sana"
    assert status["tone"] == "watch"
    assert "HEALTHY_WAIT" in status["detail"]
    assert "FN LOW" in status["detail"]


def test_alert_silence_kpi_status_marks_missed_trigger_watch():
    status = alert_silence_kpi_status(
        {
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 3,
                "silence_mode": "MISSED_TRIGGER_WATCH",
                "silence_reason": "Setup listo, pero gatillo 15m lleva 41 ciclos pendiente",
                "false_negative_risk": "MEDIUM",
                "missed_opportunity_watch": True,
                "missed_opportunity_risk": "MEDIUM",
            },
            "missed_trigger_plan_active": True,
            "missed_trigger_plan_symbol": "SOL/USD",
            "missed_trigger_plan_readiness": 73.7,
            "missed_trigger_plan_review_due": True,
            "missed_trigger_plan_review_status": "OVERDUE",
            "missed_trigger_plan_review_overdue_cycles": 2,
            "missed_trigger_plan_review_cycles_remaining": 0,
            "missed_trigger_plan_review_eta_minutes": 0.0,
            "missed_trigger_plan_review_overdue_minutes": 1.2,
            "missed_trigger_plan_review_action": "Revalidar manualmente 15m/1h.",
        }
    )

    assert status["label"] == "Vigilar gatillo"
    assert status["tone"] == "watch"
    assert "MISSED_TRIGGER_WATCH" in status["detail"]
    assert "FN MEDIUM" in status["detail"]
    assert "revision OVERDUE +2/1.2m" in status["detail"]
    assert "Revalidar manualmente 15m/1h." in status["detail"]


def test_alert_silence_kpi_status_marks_suspicious_silence():
    status = alert_silence_kpi_status(
        {
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 6,
                "diagnostic_severity": "ATTENTION",
                "diagnostic_label": "Bloqueador x14",
                "silence_mode": "SUSPICIOUS_SILENCE",
                "silence_reason": "Bloqueador persistente sin clasificacion operativa",
                "false_negative_risk": "HIGH",
            }
        }
    )

    assert status["label"] == "Sospechoso"
    assert status["tone"] == "avoid"
    assert "SUSPICIOUS_SILENCE" in status["detail"]
    assert "FN HIGH" in status["detail"]


def test_alert_silence_kpi_status_marks_partial_market_block():
    status = alert_silence_kpi_status(
        {
            "summary": {
                "state": "BLOCKED_REALTIME",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 3,
                "silence_mode": "MARKET_PARTIAL_BLOCK",
                "silence_reason": "stock, options bloqueado por proveedor premium; cripto sigue permitido",
                "false_negative_risk": "MEDIUM",
                "market_counts": {"stock": 3},
                "allowed_markets": ["crypto"],
                "missing_allowed_markets": ["crypto"],
                "market_coverage_label": "Cripto permitido sin candidatos",
                "market_coverage_action": "Mantener scan crypto activo; no forzar alertas si no hay setup cripto.",
            }
        }
    )

    assert status["label"] == "Bloqueo parcial"
    assert status["tone"] == "avoid"
    assert "MARKET_PARTIAL_BLOCK" in status["detail"]
    assert "FN MEDIUM" in status["detail"]


def test_alert_quality_rotation_candidates_falls_back_to_setup_watchlist():
    candidates = alert_quality_rotation_candidates(
        {},
        {
            "setup_watchlist": [
                {"symbol": "WMT", "readiness": 61.5, "quality": "C"},
                {"symbol": "PEP", "readiness": 53.8, "quality": "C"},
                {"symbol": "WMT", "readiness": 60.0, "quality": "C"},
            ]
        },
    )

    assert candidates == [
        {"symbol": "WMT", "readiness": 61.5, "quality": "C", "label": "WMT 61.5% C"},
        {"symbol": "PEP", "readiness": 53.8, "quality": "C", "label": "PEP 53.8% C"},
    ]


def test_alert_quality_rotation_candidates_skip_closed_market_wait():
    candidates = alert_quality_rotation_candidates(
        {"blocker_category": "MARKET_CLOSED_WAIT"},
        {
            "setup_watchlist": [
                {"symbol": "WMT", "readiness": 61.5, "quality": "C"},
                {"symbol": "PEP", "readiness": 53.8, "quality": "C"},
            ]
        },
    )

    assert candidates == []


def test_alert_focus_rotation_panel_rows_exposes_closed_market_action_without_rotation():
    panel = alert_focus_rotation_panel_rows(
        {
            "summary": {
                "state": "WAITING",
                "blocker_category": "MARKET_CLOSED_WAIT",
                "recommended_action": "Mercado cerrado; mantener watchlist y revalidar entrada en la apertura",
                "rotation_candidates": [],
                "waiting_streak": 50,
            },
            "latest_entry": {
                "setup_watchlist": [
                    {"symbol": "WMT", "readiness": 61.5, "quality": "C"},
                ]
            },
        }
    )

    assert panel["visible"] is True
    assert panel["mode"] == "SESSION_WAIT"
    assert panel["candidates"] == []
    assert panel["recommended_action"].startswith("Mercado cerrado")


def test_alert_focus_rotation_panel_rows_exposes_visible_candidates():
    panel = alert_focus_rotation_panel_rows(
        {
            "summary": {
                "state": "WAITING",
                "recommended_action": "Rotar foco: WMT 61.5% C, PEP 53.8% C; no alertar hasta que 15m confirme entrada",
                "rotation_candidates": ["WMT 61.5% C", "PEP 53.8% C"],
                "waiting_streak": 50,
            }
        }
    )

    assert panel["visible"] is True
    assert panel["waiting_streak"] == 50
    assert panel["recommended_action"].startswith("Rotar foco")
    assert [item["symbol"] for item in panel["candidates"]] == ["WMT", "PEP"]


def test_chart_realtime_watch_rows_prioritizes_stale_and_overdue_charts():
    rows = chart_realtime_watch_rows(
        {
            "charts": [
                {
                    "symbol": "WMT",
                    "timeframe": "15m",
                    "status": "OK",
                    "label": "Viva",
                    "age_minutes": 4.2,
                    "next_expected_update_in_minutes": 10.8,
                    "cadence_lag_minutes": 0.0,
                    "health_lag_minutes": 0.0,
                    "detail": "vela fresca",
                },
                {
                    "symbol": "AAPL",
                    "timeframe": "1h",
                    "status": "WARN",
                    "label": "Estancada",
                    "age_minutes": 92.0,
                    "next_expected_update_in_minutes": None,
                    "cadence_lag_minutes": 32.0,
                    "health_lag_minutes": 0.0,
                    "detail": "revisar feed",
                },
                {
                    "symbol": "PEP",
                    "timeframe": "15m",
                    "status": "FAIL",
                    "label": "Sin data",
                    "age_minutes": None,
                    "cadence_lag_minutes": None,
                    "detail": "sin velas",
                },
            ]
        }
    )

    assert [row["symbol"] for row in rows] == ["PEP", "AAPL", "WMT"]
    assert rows[0]["tone"] == "avoid"
    assert rows[1]["lag_min"] == 32.0
    assert rows[2]["proxima_vela_min"] == 10.8


def test_alert_quality_report_dashboard_status_flags_persistent_blocker():
    status = alert_quality_report_dashboard_status(
        {
            "summary": {
                "state": "WAITING",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 8,
                "waiting_streak": 14,
                "latest_top_blocker_streak": 14,
                "diagnostic_severity": "ATTENTION",
                "diagnostic_label": "Bloqueador x14",
                "diagnostic_detail": "15m da entrada: WAIT",
                "persistent_blocker_minutes": 18.5,
                "avg_readiness": 61.3,
                "latest_top_blocker": "15m da entrada: WAIT",
                "dominant_blocker": {"name": "15m da entrada: WAIT", "count": 14},
            }
        }
    )

    assert status["label"] == "Bloqueador x14"
    assert status["tone"] == "avoid"
    assert "bloqueador x14" in status["detail"]
    assert "persistente 18.5m" in status["detail"]
    assert "recurrente 15m da entrada: WAIT x14" in status["detail"]


def test_operational_mode_dashboard_status_uses_realtime_summary():
    status = operational_mode_dashboard_status(
        {
            "operational_summary": {
                "mode": "MARKET_WAITING",
                "label": "Mercado espera",
                "tone": "watch",
                "detail": "Bloqueador x14 | 15m da entrada: WAIT",
            }
        }
    )

    assert status["label"] == "Mercado espera"
    assert status["tone"] == "watch"
    assert status["mode"] == "MARKET_WAITING"


def test_operational_mode_dashboard_status_falls_back_to_system_failure():
    status = operational_mode_dashboard_status(
        {"status": "FAIL", "checks": [{"name": "streamlit_app", "status": "FAIL", "detail": "HTTP timeout"}]},
        {"summary": {"state": "READY", "latest_notifications_ready": 2}},
    )

    assert status["label"] == "Sistema falla"
    assert status["tone"] == "avoid"
    assert status["mode"] == "SYSTEM_FAIL"


def test_alert_quality_report_dashboard_status_flags_ready_and_blocked():
    ready = alert_quality_report_dashboard_status(
        {"summary": {"state": "READY", "latest_notifications_ready": 2, "latest_total_opportunities": 5}}
    )
    blocked = alert_quality_report_dashboard_status(
        {"summary": {"state": "BLOCKED_DATA", "latest_notifications_ready": 0, "latest_total_opportunities": 5}}
    )

    assert ready["label"] == "2 lista(s)"
    assert ready["tone"] == "buy"
    assert blocked["label"] == "Datos bloquean"
    assert blocked["tone"] == "avoid"


def test_alert_quality_report_dashboard_status_flags_partial_market_block():
    status = alert_quality_report_dashboard_status(
        {
            "summary": {
                "state": "BLOCKED_REALTIME",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 3,
                "silence_mode": "MARKET_PARTIAL_BLOCK",
                "silence_reason": "stock, options bloqueado por proveedor premium; cripto sigue permitido",
                "false_negative_risk": "MEDIUM",
                "market_counts": {"stock": 3},
                "allowed_markets": ["crypto"],
                "missing_allowed_markets": ["crypto"],
                "market_coverage_label": "Cripto permitido sin candidatos",
                "market_coverage_action": "Mantener scan crypto activo; no forzar alertas si no hay setup cripto.",
            }
        }
    )

    assert status["label"] == "Bloqueo parcial"
    assert status["tone"] == "avoid"
    assert "cripto sigue permitido" in status["detail"]
    assert "mercado Cripto permitido sin candidatos" in status["detail"]
    assert "cobertura stock:3" in status["detail"]
    assert "sin candidatos crypto" in status["detail"]
    assert "scan crypto activo" in status["detail"]
    assert status["market_coverage_label"] == "Cripto permitido sin candidatos"
    assert status["missing_allowed_markets"] == ["crypto"]
    assert "tipo -" not in status["detail"]


def test_alert_quality_report_dashboard_status_marks_operable_partial_market_as_watch():
    status = alert_quality_report_dashboard_status(
        {
            "summary": {
                "state": "BLOCKED_REALTIME",
                "latest_notifications_ready": 0,
                "latest_total_opportunities": 11,
                "silence_mode": "MARKET_PARTIAL_BLOCK",
                "silence_reason": "stock, options bloqueado por proveedor premium; cripto sigue permitido",
                "false_negative_risk": "MEDIUM",
                "market_counts": {"crypto": 3, "stock": 8},
                "allowed_markets": ["crypto"],
                "missing_allowed_markets": [],
                "operable_market_count": 3,
                "market_coverage_label": "Cripto operable",
                "market_coverage_action": "Priorizar candidatos cripto mientras stock/opciones recuperan proveedor premium.",
            }
        }
    )

    assert status["label"] == "Cripto operable"
    assert status["tone"] == "watch"
    assert status["operable_market_count"] == 3
    assert "mercado Cripto operable" in status["detail"]
    assert "cobertura crypto:3, stock:8" in status["detail"]
    assert "Priorizar candidatos cripto" in status["detail"]


def test_merged_alert_quality_summary_prefers_top_level_contract():
    summary = merged_alert_quality_summary(
        {
            "state": "BLOCKED_REALTIME",
            "diagnostic_label": "Bloqueo parcial",
            "blocker_category": "MARKET_PARTIAL_BLOCK",
            "recommended_action": "Configurar proveedor premium.",
            "false_negative_risk": "MEDIUM",
            "silence_mode": "MARKET_PARTIAL_BLOCK",
            "silence_reason": "stock, options bloqueado por proveedor premium; cripto sigue permitido",
            "blocked_markets": ["stock", "options"],
            "market_counts": {"stock": 3},
            "allowed_markets": ["crypto"],
            "missing_allowed_markets": ["crypto"],
            "market_coverage_label": "Cripto permitido sin candidatos",
            "chart_contract_label": "Graficas bloqueadas",
            "chart_contract_operable_count": 0,
            "chart_contract_blocked_count": 3,
            "chart_contract_missing_count": 3,
            "chart_contract_blocked_symbols": ["WMT: CHART_CONTRACT_MISSING"],
            "confirmation_wait_plan_active": True,
            "confirmation_wait_plan_symbol": "ETH/USD",
            "confirmation_wait_plan_readiness": 83.0,
            "confirmation_wait_plan_review_due": True,
            "confirmation_wait_plan_review_status": "OVERDUE",
            "confirmation_wait_plan_review_action": "Revalidar manualmente 2h/4h.",
            "latest_notifications_ready": 0,
            "latest_total_opportunities": 3,
            "summary": {
                "state": "WAITING",
                "diagnostic_label": "Stale summary",
                "blocker_category": "MARKET_TRIGGER_WAIT",
            },
        }
    )

    assert summary["state"] == "BLOCKED_REALTIME"
    assert summary["diagnostic_label"] == "Bloqueo parcial"
    assert summary["blocker_category"] == "MARKET_PARTIAL_BLOCK"
    assert summary["blocked_markets"] == ["stock", "options"]
    assert summary["market_counts"] == {"stock": 3}
    assert summary["missing_allowed_markets"] == ["crypto"]
    assert summary["market_coverage_label"] == "Cripto permitido sin candidatos"
    assert summary["chart_contract_label"] == "Graficas bloqueadas"
    assert summary["chart_contract_blocked_count"] == 3
    assert summary["chart_contract_blocked_symbols"] == ["WMT: CHART_CONTRACT_MISSING"]
    assert summary["confirmation_wait_plan"]["active"] is True
    assert summary["confirmation_wait_plan"]["primary_symbol"] == "ETH/USD"
    assert summary["confirmation_wait_plan"]["primary_readiness"] == 83.0
    assert summary["confirmation_wait_plan"]["review_due"] is True
    assert summary["confirmation_wait_plan"]["review_status"] == "OVERDUE"
    assert summary["confirmation_wait_plan"]["review_action"] == "Revalidar manualmente 2h/4h."
    assert summary["latest_total_opportunities"] == 3


def test_alert_quality_dashboard_status_uses_top_level_contract_without_summary():
    status = alert_quality_report_dashboard_status(
        {
            "state": "BLOCKED_REALTIME",
            "diagnostic_label": "Bloqueo parcial",
            "diagnostic_severity": "ATTENTION",
            "blocker_category": "MARKET_PARTIAL_BLOCK",
            "silence_mode": "MARKET_PARTIAL_BLOCK",
            "silence_reason": "stock, options bloqueado por proveedor premium; cripto sigue permitido",
            "false_negative_risk": "MEDIUM",
            "latest_notifications_ready": 0,
            "latest_total_opportunities": 3,
            "recommended_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
            "market_counts": {"stock": 3},
            "missing_allowed_markets": ["crypto"],
            "market_coverage_label": "Cripto permitido sin candidatos",
            "market_coverage_action": "Mantener scan crypto activo; no forzar alertas si no hay setup cripto.",
            "chart_contract_label": "Graficas bloqueadas",
            "chart_contract_action": "No emitir alertas hasta recuperar contrato realtime de grafica.",
            "chart_contract_operable_count": 0,
            "chart_contract_blocked_count": 3,
            "chart_contract_missing_count": 3,
            "chart_contract_blocked_symbols": ["WMT: CHART_CONTRACT_MISSING"],
        }
    )
    silence = alert_silence_kpi_status(
        {
            "state": "BLOCKED_REALTIME",
            "silence_mode": "MARKET_PARTIAL_BLOCK",
            "silence_reason": "stock, options bloqueado por proveedor premium; cripto sigue permitido",
            "false_negative_risk": "MEDIUM",
            "latest_notifications_ready": 0,
            "latest_total_opportunities": 3,
        }
    )

    assert status["label"] == "Bloqueo parcial"
    assert status["tone"] == "avoid"
    assert status["blocker_category"] == "MARKET_PARTIAL_BLOCK"
    assert "riesgo FN MEDIUM" in status["detail"]
    assert "Configurar POLYGON_API_KEY" in status["detail"]
    assert "Cripto permitido sin candidatos" in status["detail"]
    assert "sin candidatos crypto" in status["detail"]
    assert status["chart_contract_label"] == "Graficas bloqueadas"
    assert status["chart_contract_blocked_count"] == 3
    assert status["chart_contract_missing_count"] == 3
    assert status["chart_contract_blocked_symbols"] == ["WMT: CHART_CONTRACT_MISSING"]
    assert "graficas Graficas bloqueadas live:0 bloqueadas:3" in status["detail"]
    assert "sin contrato grafica 3" in status["detail"]
    assert silence["label"] == "Bloqueo parcial"
    assert silence["tone"] == "avoid"
    assert "FN MEDIUM" in silence["detail"]


def test_notification_history_dashboard_status_surfaces_cooldown():
    status = notification_history_dashboard_status(
        {
            "sample_size": 5,
            "sent_count": 2,
            "cooldown_skipped": 3,
            "last_reason": "cooldown",
        }
    )

    assert status["label"] == "3 cooldown"
    assert status["tone"] == "watch"
    assert "ultimo cooldown" in status["detail"]


def test_notification_history_dashboard_status_surfaces_local_fallback():
    status = notification_history_dashboard_status(
        {
            "sample_size": 8,
            "line_count": 407,
            "max_lines": 500,
            "size_bytes": 195574,
            "max_bytes": 1000000,
            "sent_count": 0,
            "local_recorded_count": 6,
            "cooldown_skipped": 1,
            "channel_count": 0,
            "last_reason": "recorded_local",
            "last_age_minutes": 4.5,
        }
    )

    assert status["label"] == "Local"
    assert status["tone"] == "watch"
    assert status["channel_count"] == 0
    assert status["local_recorded_count"] == 6
    assert status["line_count"] == 407
    assert status["max_lines"] == 500
    assert status["line_budget_ratio"] == 0.814
    assert status["line_budget_margin"] == 93
    assert status["line_budget_status"] == "OK"
    assert status["size_bytes"] == 195574
    assert status["max_bytes"] == 1000000
    assert status["byte_budget_ratio"] == 0.195574
    assert status["byte_budget_margin"] == 804426
    assert status["budget_status"] == "OK"
    assert "local 6" in status["detail"]
    assert "sin canal externo" in status["detail"]
    assert "hace 4.5m" in status["detail"]
    assert "lineas 407/500 81.4% margen 93" in status["detail"]
    assert "hist 0.19MB/0.95MB 19.6% margen 0.77MB" in status["detail"]


def test_notification_history_dashboard_status_warns_on_history_budget_pressure():
    status = notification_history_dashboard_status(
        {
            "sample_size": 50,
            "line_count": 520,
            "max_lines": 500,
            "size_bytes": 1200000,
            "max_bytes": 1000000,
            "sent_count": 0,
            "local_recorded_count": 50,
            "channel_count": 0,
            "last_reason": "recorded_local",
        }
    )

    assert status["label"] == "Historial revisar"
    assert status["tone"] == "watch"
    assert status["line_budget_status"] == "WARN"
    assert status["budget_status"] == "WARN"
    assert status["line_budget_ratio"] == 1.04
    assert status["line_budget_margin"] == -20
    assert status["byte_budget_ratio"] == 1.2
    assert status["byte_budget_margin"] == -200000
    assert "lineas 520/500 104.0% margen -20 WARN" in status["detail"]
    assert "hist 1.14MB/0.95MB 120.0% margen -0.19MB WARN" in status["detail"]


def test_notification_delivery_dashboard_status_surfaces_local_operational_mode():
    report = {
        "checks": [
            {
                "name": "notification_delivery",
                "status": "INFO",
                "detail": "No external channels configured; local alert files are writable",
                "channel_count": 0,
                "local_file_fallback": True,
                "actionable_ready_count": 0,
                "delivery_mode": "local_file",
            }
        ]
    }

    status = notification_delivery_dashboard_status(report, {"delivery_mode": "local_file", "channel_count": 0})

    assert status["label"] == "Solo local"
    assert status["tone"] == "watch"
    assert status["delivery_mode"] == "local_file"
    assert status["channel_count"] == 0
    assert status["actionable_ready_count"] == 0
    assert "archivo local operativo" in status["detail"]


def test_notification_delivery_dashboard_status_escalates_ready_alerts_without_channel():
    report = {
        "checks": [
            {
                "name": "notification_delivery",
                "status": "WARN",
                "detail": "2 actionable alert(s) ready but no external/macOS channel configured",
                "channel_count": 0,
                "local_file_fallback": True,
                "actionable_ready_count": 2,
                "delivery_mode": "local_file",
            }
        ]
    }

    status = notification_delivery_dashboard_status(report)

    assert status["label"] == "Listas sin canal"
    assert status["tone"] == "avoid"
    assert status["actionable_ready_count"] == 2
    assert "2 alerta(s) listas" in status["detail"]


def test_notification_delivery_dashboard_status_accepts_external_channels():
    report = {
        "checks": [
            {
                "name": "notification_delivery",
                "status": "OK",
                "detail": "Configured channels: macos, email",
                "channels": ["macos", "email"],
                "channel_count": 2,
                "actionable_ready_count": 0,
                "delivery_mode": "external",
            }
        ]
    }

    status = notification_delivery_dashboard_status(report)

    assert status["label"] == "2 canales"
    assert status["tone"] == "buy"
    assert status["channel_count"] == 2
    assert "macos, email" in status["detail"]


def test_notification_delivery_action_status_recommends_setup_without_ready_alerts():
    status = notification_delivery_action_status(
        {"channel_count": 0, "actionable_ready_count": 0},
        [
            {"channel": "macos", "configured": False},
            {"channel": "discord", "configured": False},
        ],
        ready_count=0,
        cooldown_minutes=60,
    )

    assert status["label"] == "Preparar delivery"
    assert status["tone"] == "watch"
    assert status["configured_count"] == 0
    assert status["missing_channels"] == ["macos", "discord"]
    assert "sin alertas listas" in status["detail"]


def test_notification_delivery_action_status_escalates_ready_alerts_without_external_channel():
    status = notification_delivery_action_status(
        {"channel_count": 0, "actionable_ready_count": 2},
        [{"channel": "macos", "configured": False}],
        cooldown_minutes=30,
    )

    assert status["label"] == "Conectar canal ahora"
    assert status["tone"] == "avoid"
    assert "2 alerta(s) listas" in status["detail"]
    assert "Activar Mac" in status["action"]


def test_notification_delivery_action_status_accepts_configured_channel():
    status = notification_delivery_action_status(
        {"channel_count": 1, "actionable_ready_count": 0},
        [
            {"channel": "macos", "configured": True},
            {"channel": "email", "configured": False},
        ],
        cooldown_minutes=45,
    )

    assert status["label"] == "Salida externa lista"
    assert status["tone"] == "buy"
    assert status["configured_count"] == 1
    assert status["missing_channels"] == ["email"]
    assert "1 canal" in status["detail"]


def test_notification_history_display_table_uses_effective_sent_for_legacy_rows():
    table = notification_history_display_table(
        [
            {
                "ts": "2026-06-10T00:00:00+00:00",
                "sent": True,
                "channels": [],
                "reason": "health_watchdog",
                "message": "line 1\nline 2",
            },
            {
                "ts": "2026-06-10T00:01:00+00:00",
                "sent": True,
                "channels": ["macos"],
                "reason": "test_macos",
                "message": "ok",
            },
        ]
    )

    assert bool(table.loc[0, "effective_sent"]) is False
    assert bool(table.loc[1, "effective_sent"]) is True
    assert table.loc[0, "message"] == "line 1 | line 2"


def test_realtime_report_check_card_maps_named_check_statuses():
    report = {
        "checks": [
            {"name": "streamlit_service_24h", "status": "OK", "detail": "loaded"},
            {"name": "live_service_24h", "status": "FAIL", "detail": "not loaded"},
            {"name": "notification_delivery", "status": "INFO", "detail": "No external channels; local alert files are writable"},
        ]
    }

    ok = realtime_report_check_card(report, "streamlit_service_24h", ok_label="24h ON")
    fail = realtime_report_check_card(report, "live_service_24h")
    missing = realtime_report_check_card(report, "missing")
    delivery = realtime_report_check_card(report, "notification_delivery", ok_label="Lista")

    assert ok == {"label": "24h ON", "tone": "buy", "detail": "loaded"}
    assert fail["label"] == "Falla"
    assert fail["tone"] == "avoid"
    assert missing["tone"] == "watch"
    assert delivery == {"label": "Info", "tone": "neutral", "detail": "No external channels; local alert files are writable"}
    assert "local alert files" in delivery["detail"]


def test_health_notify_dashboard_status_summarizes_ok_and_sent_states():
    assert health_notify_dashboard_status({})["label"] == "Sin estado"
    ok = health_notify_dashboard_status({"last_status": "OK", "last_message": ""})
    sent = health_notify_dashboard_status(
        {
            "last_status": "FAIL",
            "last_message": "ROXY HEALTH FAIL | heartbeat failed",
            "last_result": {"sent": True, "reason": "health_watchdog"},
        }
    )
    cooldown = health_notify_dashboard_status(
        {
            "last_status": "WARN",
            "last_message": "ROXY HEALTH WARN | disk low",
            "last_result": {"sent": False, "reason": "cooldown"},
        }
    )
    recorded = health_notify_dashboard_status(
        {
            "last_status": "WARN",
            "last_message": "ROXY HEALTH WARN | local only",
            "last_result": {"sent": False, "reason": "recorded_local"},
        }
    )

    assert ok["label"] == "Silencioso"
    assert ok["tone"] == "buy"
    assert sent["label"] == "Avisado"
    assert sent["tone"] == "avoid"
    assert cooldown["label"] == "Cooldown"
    assert recorded["label"] == "Registrado"


def test_realtime_lock_dashboard_status_summarizes_lock_states():
    assert realtime_lock_dashboard_status({})["label"] == "Sin dato"
    blocked = realtime_lock_dashboard_status(
        {
            "event": "blocked",
            "pid": 123,
            "blocked_age_minutes": 0.5,
            "transient_blocked_minutes": 2.0,
            "lock_overlap_benign": True,
            "lock_overlap_profile": "SHARED_REPORT_WORK",
            "lock_overlap_shared_flags": ["--ensure-alert-quality-report", "--no-fail"],
            "lock_overlap_owner_only_flags": ["--dashboard-probe-refresh-minutes"],
            "lock_overlap_blocked_only_flags": ["--notify-health", "--ensure-live-data"],
        }
    )
    acquired = realtime_lock_dashboard_status(
        {
            "event": "acquired",
            "pid": 124,
            "acquired_age_minutes": 0.6,
            "max_acquired_minutes": 30.0,
            "lock_overlap_profile": "NO_BLOCKED_OVERLAP",
            "generated_at": "2026-06-10T12:00:00+00:00",
        }
    )
    replaced = realtime_lock_dashboard_status(
        {"event": "acquired", "pid": 125, "generated_at": "2026-06-10T12:01:00+00:00", "stale_replaced": True}
    )
    released = realtime_lock_dashboard_status({"event": "released", "released_at": "2026-06-10T12:02:00+00:00"})

    assert blocked["label"] == "Solape benigno"
    assert blocked["tone"] == "watch"
    assert blocked["lock_overlap_benign"] is True
    assert blocked["lock_overlap_profile"] == "SHARED_REPORT_WORK"
    assert blocked["lock_overlap_shared_count"] == 2
    assert blocked["lock_overlap_owner_only_count"] == 1
    assert blocked["lock_overlap_blocked_only_count"] == 2
    assert "age 0.5m/transient 2m" in blocked["detail"]
    assert "profile shared_report_work" in blocked["detail"]
    assert "shared 2" in blocked["detail"]
    assert acquired["label"] == "Activo"
    assert acquired["tone"] == "neutral"
    assert acquired["age_minutes"] == 0.6
    assert acquired["max_acquired_minutes"] == 30.0
    assert "age 0.6m/30m" in acquired["detail"]
    assert "profile no_blocked_overlap" in acquired["detail"]
    assert replaced["label"] == "Reemplazo"
    assert released["label"] == "Libre"
    assert released["tone"] == "buy"


def test_timeframe_minutes_supports_intraday_and_daily():
    assert timeframe_minutes("15m") == 15
    assert timeframe_minutes("2h") == 120
    assert timeframe_minutes("4h") == 240
    assert timeframe_minutes("1d") == 1440


def test_chart_freshness_status_marks_recent_crypto_live():
    now = datetime(2026, 6, 8, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=20), now - timedelta(minutes=3)],
            "close": [100, 101],
        }
    )

    status = chart_freshness_status(chart_df, market="crypto", timeframe="15m", now=now)

    assert status["label"] == "Viva"
    assert status["tone"] == "buy"


def test_chart_live_data_status_is_honest_when_alpaca_ready_but_stock_chart_uses_fallback():
    now = datetime(2026, 6, 8, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=20), now - timedelta(minutes=3)],
            "open": [100, 101],
            "high": [101, 102],
            "low": [99, 100],
            "close": [100.5, 101.5],
            "volume": [1000, 1200],
        }
    )

    status = chart_live_data_status(
        chart_df,
        market="stock",
        timeframe="15m",
        now=now,
        stock_alerts_allowed=True,
        provider_summary={"mode": "PAPER_LIVE_READY", "status": "Paper/live listo", "tone": "buy"},
    )

    assert status["status"] == "Premium listo / grafica fallback"
    assert status["tone"] == "watch"
    assert status["source"] == "yfinance"
    assert status["source_mode"] == "FALLBACK"
    assert status["fallback_reason"] == "-"
    assert status["cadence_lag_minutes"] == 0.0
    assert status["next_expected_update_in_minutes"] == 12.0
    assert "conectar Alpaca directo" in status["action"]


def test_chart_live_data_status_allows_crypto_exchange_when_fresh():
    now = datetime(2026, 6, 8, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=15), now - timedelta(minutes=2)],
            "open": [50, 51],
            "high": [52, 53],
            "low": [49, 50],
            "close": [51, 52],
            "volume": [20, 30],
        }
    )

    status = chart_live_data_status(
        chart_df,
        market="crypto",
        timeframe="15m",
        now=now,
        provider_summary={"mode": "FALLBACK_ONLY", "status": "Fallback activo", "tone": "watch"},
    )

    assert status["status"] == "Grafica viva"
    assert status["tone"] == "buy"
    assert status["source"] == "ccxt:binanceus"
    assert status["source_mode"] == "EXCHANGE_API"
    assert status["checked_at"] == "2026-06-08T12:00:00"
    assert status["candle_phase"] == "NEW_CANDLE"
    assert status["candle_phase_label"] == "Vela nueva"


def test_chart_live_data_status_marks_alpaca_source_as_premium_live():
    now = datetime(2026, 6, 8, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=15), now - timedelta(minutes=2)],
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [5000, 5200],
        }
    )

    status = chart_live_data_status(
        chart_df,
        market="stock",
        timeframe="15m",
        now=now,
        stock_alerts_allowed=True,
        provider_summary={"mode": "PAPER_LIVE_READY", "status": "Paper/live listo", "tone": "buy"},
        source_meta={
            "provider": "Alpaca",
            "source": "alpaca_iex",
            "mode": "BROKER_DATA",
            "label": "Alpaca IEX",
            "detail": "Velas de acciones desde Alpaca/IEX.",
        },
    )

    assert status["status"] == "Grafica premium viva"
    assert status["tone"] == "buy"
    assert status["source"] == "alpaca_iex"
    assert status["source_label"] == "Alpaca IEX"
    assert status["source_mode"] == "BROKER_DATA"
    assert status["fallback_reason"] == "-"


def test_chart_live_data_status_preserves_fallback_reason_from_source_meta():
    now = datetime(2026, 6, 8, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=15), now - timedelta(minutes=2)],
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [5000, 5200],
        }
    )

    status = chart_live_data_status(
        chart_df,
        market="stock",
        timeframe="15m",
        now=now,
        stock_alerts_allowed=True,
        provider_summary={"mode": "FALLBACK_ONLY", "status": "Fallback activo", "tone": "watch"},
        source_meta={
            "provider": "yfinance",
            "source": "yfinance",
            "mode": "FALLBACK",
            "label": "yfinance fallback",
            "detail": "Velas de acciones desde yfinance fallback.",
            "fallback_reason": "alpaca_not_configured",
            "fallback_detail": "El servicio no tiene credenciales Alpaca disponibles.",
            "fallback_action": "Configurar credenciales Alpaca.",
        },
    )

    assert status["status"] == "Grafica fallback"
    assert status["tone"] == "watch"
    assert status["fallback_reason"] == "alpaca_not_configured"
    assert "credenciales Alpaca" in status["fallback_detail"]


def test_chart_live_data_status_downgrades_provider_when_alpaca_auth_falls_back():
    now = datetime(2026, 6, 8, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=15), now - timedelta(minutes=2)],
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [5000, 5200],
        }
    )

    status = chart_live_data_status(
        chart_df,
        market="stock",
        timeframe="15m",
        now=now,
        stock_alerts_allowed=True,
        provider_summary={"mode": "PAPER_LIVE_READY", "status": "Credenciales presentes", "tone": "buy"},
        source_meta={
            "provider": "yfinance",
            "source": "yfinance",
            "mode": "FALLBACK",
            "label": "yfinance fallback",
            "detail": "Velas de acciones desde yfinance fallback.",
            "fallback_reason": "alpaca_auth",
            "fallback_detail": "Alpaca rechazo las credenciales o el token.",
            "fallback_action": "Revisar credenciales Alpaca.",
        },
    )

    assert status["status"] == "Grafica fallback"
    assert status["tone"] == "watch"
    assert status["provider_mode"] == "PROVIDER_FALLBACK"
    assert status["provider_status"] == "Proveedor en fallback"
    assert status["provider_tone"] == "avoid"
    assert status["fallback_reason"] == "alpaca_auth"


def test_chart_live_data_status_blocks_empty_chart():
    status = chart_live_data_status(
        pd.DataFrame(),
        market="stock",
        timeframe="15m",
        provider_summary={"mode": "PAPER_LIVE_READY", "status": "Paper/live listo", "tone": "buy"},
    )

    assert status["status"] == "Grafica no operable"
    assert status["tone"] == "avoid"
    assert "No tomar entrada" in status["action"]


def test_chart_operational_confidence_accepts_premium_live_chart():
    confidence = chart_operational_confidence(
        {
            "status": "Grafica premium viva",
            "source_mode": "BROKER_DATA",
            "source_label": "Alpaca IEX",
            "freshness_status": "OK",
            "age_minutes": 2.0,
            "cadence_lag_minutes": 0.0,
            "market_closed_accepted": False,
        }
    )

    assert confidence["label"] == "Analisis OK"
    assert confidence["tone"] == "buy"
    assert confidence["mode"] == "LIVE_CONFIRMED"
    assert "Alpaca IEX" in confidence["detail"]


def test_chart_operational_confidence_requires_external_confirmation_for_fallback():
    confidence = chart_operational_confidence(
        {
            "status": "Grafica fallback",
            "source_mode": "FALLBACK",
            "source_label": "yfinance fallback",
            "freshness_status": "OK",
            "age_minutes": 4.0,
            "cadence_lag_minutes": 0.0,
            "fallback_reason": "alpaca_not_configured",
        }
    )

    assert confidence["label"] == "Confirmar externo"
    assert confidence["tone"] == "watch"
    assert confidence["mode"] == "FALLBACK_CONFIRM"
    assert "alpaca_not_configured" in confidence["detail"]


def test_chart_operational_confidence_blocks_non_operable_chart():
    confidence = chart_operational_confidence(
        {
            "status": "Grafica no operable",
            "source_mode": "BROKER_DATA",
            "freshness_status": "FAIL",
            "age_minutes": 90.0,
            "cadence_lag_minutes": 75.0,
        }
    )

    assert confidence["label"] == "No usar"
    assert confidence["tone"] == "avoid"
    assert confidence["mode"] == "BLOCKED_STALE"
    assert "recuperar velas" in confidence["detail"]


def test_chart_operational_confidence_requires_revalidation_after_market_close():
    confidence = chart_operational_confidence(
        {
            "status": "Mercado cerrado OK",
            "source_mode": "BROKER_DATA",
            "freshness_status": "OK",
            "age_minutes": 240.0,
            "market_closed_accepted": True,
        }
    )

    assert confidence["label"] == "Revalidar apertura"
    assert confidence["tone"] == "watch"
    assert confidence["mode"] == "CLOSED_REVALIDATE"


def test_chart_data_contract_blocks_auth_fallback_as_no_trade():
    contract = chart_data_contract(
        {
            "status": "Grafica fallback",
            "source_mode": "FALLBACK",
            "source_label": "yfinance fallback",
            "freshness_status": "OK",
            "age_minutes": 4.0,
            "cadence_lag_minutes": 0.0,
            "latest": "2026-06-08 12:00",
            "fallback_reason": "alpaca_auth",
            "action": "Confirmar externo antes de operar.",
        }
    )

    assert contract["gate"] == "NO_TRADE_FROM_FALLBACK"
    assert contract["decision"] == "Bloqueada para entrada"
    assert contract["operable"] is False
    assert "fallback alpaca_auth" in contract["detail"]


def test_chart_data_contract_marks_exchange_api_as_operable_analysis():
    contract = chart_data_contract(
        {
            "status": "Grafica viva",
            "source_mode": "EXCHANGE_API",
            "source_label": "BinanceUS API",
            "freshness_status": "OK",
            "age_minutes": 2.0,
            "cadence_lag_minutes": 0.0,
            "candle_phase_label": "Vela nueva",
            "candle_progress_pct": 13.3,
            "latest": "2026-06-08 12:00",
            "action": "Data apta para analisis.",
        }
    )

    assert contract["gate"] == "LIVE_DATA_OK"
    assert contract["decision"] == "Analisis permitido"
    assert contract["operable"] is True
    assert "BinanceUS API" in contract["detail"]
    assert "fase Vela nueva 13%" in contract["detail"]


def test_live_price_data_contract_blocks_public_stock_fallback():
    contract = live_price_data_contract(
        {
            "freshness": "FRESH",
            "source_mode": "PUBLIC_MARKET_DATA",
            "source": "yfinance 1m",
            "age_seconds": 42,
            "price_timestamp": "2026-06-15T12:00:00+00:00",
            "provider_issue": "alpaca_auth",
        }
    )

    assert contract["gate"] == "NO_TRADE_FROM_PUBLIC_PRICE"
    assert contract["decision"] == "Solo referencia"
    assert contract["operable"] is False
    assert "provider alpaca_auth" in contract["detail"]


def test_live_price_data_contract_allows_confirmed_exchange_price():
    contract = live_price_data_contract(
        {
            "freshness": "LIVE",
            "source_mode": "EXCHANGE_TICKER",
            "source": "BinanceUS ticker",
            "age_seconds": 3,
            "price_timestamp": "2026-06-15T12:00:00+00:00",
        }
    )

    assert contract["gate"] == "LIVE_PRICE_OK"
    assert contract["decision"] == "Analisis permitido"
    assert contract["operable"] is True
    assert "BinanceUS ticker" in contract["detail"]


def test_chart_command_center_status_marks_crypto_exchange_as_operable():
    now = datetime(2026, 6, 8, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=15), now - timedelta(minutes=2)],
            "open": [50, 51],
            "high": [52, 53],
            "low": [49, 50],
            "close": [51, 52],
            "volume": [20, 30],
        }
    )

    status = chart_command_center_status(chart_df, market="crypto", timeframe="15m", now=now)

    assert status["headline"] == "Grafica operable"
    assert status["tone"] == "buy"
    assert status["gate"] == "LIVE_DATA_OK"
    assert status["operable"] is True
    assert status["source"] == "BinanceUS API"


def test_chart_command_center_status_blocks_stock_auth_fallback_entry():
    now = datetime(2026, 6, 8, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=15), now - timedelta(minutes=2)],
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [5000, 5200],
        }
    )

    status = chart_command_center_status(
        chart_df,
        market="stock",
        timeframe="15m",
        now=now,
        source_meta={
            "provider": "yfinance",
            "source": "yfinance",
            "mode": "FALLBACK",
            "label": "yfinance fallback",
            "detail": "Velas de acciones desde fallback.",
            "fallback_reason": "alpaca_auth",
            "fallback_detail": "Alpaca rechazo credenciales.",
            "fallback_action": "Revisar credenciales Alpaca.",
        },
    )

    assert status["headline"] == "Entrada bloqueada"
    assert status["tone"] == "watch"
    assert status["gate"] == "NO_TRADE_FROM_FALLBACK"
    assert status["operable"] is False
    assert status["source"] == "yfinance fallback"


def test_render_chart_data_contract_outputs_visible_gate_and_safe_html():
    html = render_chart_data_contract(
        {
            "label": "Confirmar externo",
            "tone": "watch",
            "decision": "Solo referencia",
            "gate": "EXTERNAL_CONFIRM_REQUIRED",
            "source_mode": "FALLBACK",
            "latest": "2026-06-08 12:00",
            "detail": "fuente yfinance fallback | edad 4m",
            "action": "Confirmar con Finviz antes de operar.",
        }
    )

    assert "chart-data-contract-watch" in html
    assert "Contrato de datos" in html
    assert "EXTERNAL_CONFIRM_REQUIRED" in html
    assert "Confirmar con Finviz" in html


def test_chart_realtime_pulse_rows_show_interval_source_and_candle_age():
    rows = chart_realtime_pulse_rows(
        {
            "tone": "buy",
            "source_label": "BinanceUS API",
            "source_mode": "EXCHANGE_API",
            "age_minutes": 2.0,
            "next_expected_update_in_minutes": 13.0,
            "candle_phase_label": "Vela nueva",
            "candle_progress_pct": 13.3,
            "checked_at": "2026-06-08T12:00:00",
            "latest": "2026-06-08 11:58",
            "provider_status": "Exchange directo",
            "provider_tone": "buy",
            "provider_detail": "Crypto live.",
        },
        symbol="BTC/USD",
        timeframe="15m",
        interval_seconds=15,
    )

    by_label = {row["label"]: row for row in rows}
    assert by_label["Pulso"]["value"] == "15s"
    assert "2026-06-08T12:00:00" in by_label["Pulso"]["detail"]
    assert by_label["Simbolo"]["value"] == "BTC/USD"
    assert by_label["Fuente"]["value"] == "BinanceUS API"
    assert by_label["Fuente"]["tone"] == "buy"
    assert by_label["Vela"]["value"] == "2m"
    assert "prox 13m" in by_label["Vela"]["detail"]
    assert by_label["Fase"]["value"] == "Vela nueva"
    assert "progreso 13%" in by_label["Fase"]["detail"]


def test_render_chart_realtime_pulse_outputs_compact_live_panel():
    html = render_chart_realtime_pulse(
        {
            "tone": "watch",
            "source_label": "yfinance fallback",
            "source_mode": "FALLBACK",
            "age_minutes": 5.0,
            "next_expected_update_in_minutes": 10.0,
            "candle_phase_label": "Vela en curso",
            "candle_progress_pct": 33.3,
            "checked_at": "2026-06-08T12:00:00",
            "latest": "2026-06-08 11:55",
            "fallback_reason": "alpaca_auth",
            "provider_status": "Proveedor en fallback",
            "provider_tone": "avoid",
            "provider_detail": "Alpaca rechazo credenciales.",
        },
        symbol="AAPL<script>",
        timeframe="15m",
        interval_seconds=15,
    )

    assert "Pulso realtime" in html
    assert "live-pulse-card-watch" in html
    assert "yfinance fallback" in html
    assert "alpaca_auth" in html
    assert "<script>" not in html


def test_chart_realtime_dashboard_status_summarizes_report():
    status = chart_realtime_dashboard_status(
        {
            "summary": {
                "label": "Graficas revisar",
                "tone": "watch",
                "checked_count": 4,
                "fail_count": 0,
                "warn_count": 1,
                "stale_count": 0,
                "data_quality_issue_count": 1,
                "max_age_minutes": 24.5,
                "avg_age_minutes": 11.2,
                "operable_checked_count": 2,
                "operable_max_age_minutes": 8.5,
                "operable_avg_age_minutes": 5.2,
                "max_cadence_lag_minutes": 9.5,
                "operable_max_cadence_lag_minutes": 1.5,
                "max_health_lag_minutes": 0.0,
                "operable_max_health_lag_minutes": 0.0,
                "next_expected_update_in_minutes": 3.0,
                "operable_next_expected_update_in_minutes": 1.0,
                "operable_min_freshness_margin_minutes": 30.2,
                "operable_min_freshness_margin_ratio": 0.8049,
                "operable_freshness_margin_state": "OK",
                "operable_freshness_margin_warn_threshold_minutes": 7.5,
                "operable_min_freshness_margin_chart": {"symbol": "AAPL", "timeframe": "15m"},
                "stalest_chart": {"symbol": "NVDA", "timeframe": "1h"},
                "operable_stalest_chart": {"symbol": "BTC/USD", "timeframe": "1h"},
                "most_overdue_chart": {"symbol": "AAPL", "timeframe": "15m"},
                "operable_most_overdue_chart": {"symbol": "ETH/USD", "timeframe": "15m"},
                "top_issue": {"symbol": "AAPL", "timeframe": "15m"},
            }
        }
    )

    assert status["label"] == "Graficas revisar"
    assert status["tone"] == "watch"
    assert "4 charts" in status["detail"]
    assert "operables 2" in status["detail"]
    assert "operable max 8.5m" in status["detail"]
    assert "max 24.5m" in status["detail"]
    assert "operable avg 5.2m" in status["detail"]
    assert "avg 11.2m" in status["detail"]
    assert "operable lag 1.5m" in status["detail"]
    assert "margen operable 30.2m/80% ok warn<=7.5m AAPL 15m" in status["detail"]
    assert "lag max 9.5m" in status["detail"]
    assert "calidad 1" in status["detail"]
    assert "AAPL 15m" in status["detail"]
    assert status["max_age_minutes"] == 24.5
    assert status["avg_age_minutes"] == 11.2
    assert status["operable_checked_count"] == 2
    assert status["operable_max_age_minutes"] == 8.5
    assert status["operable_avg_age_minutes"] == 5.2
    assert status["max_cadence_lag_minutes"] == 9.5
    assert status["operable_max_cadence_lag_minutes"] == 1.5
    assert status["max_health_lag_minutes"] == 0.0
    assert status["operable_max_health_lag_minutes"] == 0.0
    assert status["next_expected_update_in_minutes"] == 3.0
    assert status["operable_next_expected_update_in_minutes"] == 1.0
    assert status["operable_min_freshness_margin_minutes"] == 30.2
    assert status["operable_min_freshness_margin_ratio"] == 0.8049
    assert status["operable_freshness_margin_state"] == "OK"
    assert status["operable_freshness_margin_warn_threshold_minutes"] == 7.5
    assert status["operable_min_freshness_margin_chart"] == {"symbol": "AAPL", "timeframe": "15m"}
    assert status["stalest_chart"] == {"symbol": "NVDA", "timeframe": "1h"}
    assert status["operable_stalest_chart"] == {"symbol": "BTC/USD", "timeframe": "1h"}
    assert status["most_overdue_chart"] == {"symbol": "AAPL", "timeframe": "15m"}
    assert status["operable_most_overdue_chart"] == {"symbol": "ETH/USD", "timeframe": "15m"}


def test_chart_realtime_dashboard_status_avoids_overdue_copy_without_lag():
    status = chart_realtime_dashboard_status(
        {
            "summary": {
                "label": "Graficas vivas",
                "tone": "buy",
                "checked_count": 12,
                "fail_count": 0,
                "warn_count": 0,
                "max_age_minutes": 2.1,
                "avg_age_minutes": 2.1,
                "operable_checked_count": 12,
                "operable_max_age_minutes": 1.2,
                "operable_avg_age_minutes": 1.0,
                "max_cadence_lag_minutes": 0.0,
                "operable_max_cadence_lag_minutes": 0.0,
                "next_expected_update_in_minutes": 12.9,
                "operable_next_expected_update_in_minutes": 4.5,
                "stalest_chart": {"symbol": "AAPL", "timeframe": "15m"},
                "operable_stalest_chart": {"symbol": "BTC/USD", "timeframe": "15m"},
                "most_overdue_chart": {},
                "operable_most_overdue_chart": {},
            }
        }
    )

    assert "operable next 4.5m" in status["detail"]
    assert "next vela 12.9m" in status["detail"]
    assert "operable vieja BTC/USD 15m" in status["detail"]


def test_chart_realtime_dashboard_status_derives_margin_from_chart_rows():
    status = chart_realtime_dashboard_status(
        {
            "summary": {
                "label": "Graficas vivas",
                "tone": "buy",
                "checked_count": 2,
                "fail_count": 0,
                "warn_count": 0,
            },
            "charts": [
                {
                    "symbol": "AAPL",
                    "market": "stock",
                    "timeframe": "15m",
                    "status": "OK",
                    "age_minutes": 7.3,
                    "freshness_budget_minutes": 37.5,
                },
                {
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "timeframe": "1h",
                    "status": "OK",
                    "age_minutes": 52.3,
                    "freshness_budget_minutes": 150.0,
                },
            ],
        }
    )

    assert status["operable_min_freshness_margin_minutes"] == 30.2
    assert status["operable_min_freshness_margin_ratio"] == 0.8053
    assert status["operable_freshness_margin_warn_threshold_minutes"] == 7.5
    assert status["operable_freshness_margin_state"] == "OK"
    assert status["operable_min_freshness_margin_chart"]["symbol"] == "AAPL"
    assert "margen operable 30.2m/81% ok warn<=7.5m AAPL 15m" in status["detail"]
    assert "atrasada" not in status["detail"]
    assert "tarde" not in status["detail"]


def test_chart_provider_effective_dashboard_status_summarizes_expected_fallback():
    status = chart_provider_effective_dashboard_status(
        {
            "checks": [
                {
                    "name": "chart_provider_effective",
                    "status": "INFO",
                    "checked_count": 4,
                    "fallback_count": 3,
                    "auth_fallback_count": 0,
                    "fallback_reason_counts": {"alpaca_not_configured": 3},
                    "detail": "4 provider source(s), fallback 3",
                }
            ]
        }
    )

    assert status["label"] == "Fallback"
    assert status["tone"] == "watch"
    assert status["fallback_count"] == 3
    assert "alpaca_not_configured x3" in status["detail"]


def test_chart_provider_effective_dashboard_status_escalates_auth_fallback():
    status = chart_provider_effective_dashboard_status(
        {
            "checks": [
                {
                    "name": "chart_provider_effective",
                    "status": "WARN",
                    "checked_count": 2,
                    "fallback_count": 1,
                    "auth_fallback_count": 1,
                    "polygon_missing_count": 1,
                    "fallback_reason_counts": {"alpaca_auth": 1},
                    "alternate_reason_counts": {"polygon_not_configured": 1},
                    "premium_recovery_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                    "detail": "issue WMT 1h alpaca_auth",
                }
            ]
        }
    )

    assert status["label"] == "Auth/permisos"
    assert status["tone"] == "avoid"
    assert status["auth_fallback_count"] == 1
    assert status["polygon_missing_count"] == 1
    assert "alpaca_auth x1" in status["detail"]
    assert "Polygon falta 1" in status["detail"]
    assert "alterno polygon_not_configured x1" in status["detail"]
    assert "POLYGON_API_KEY" in status["detail"]


def test_chart_provider_effective_dashboard_status_marks_crypto_operable_when_stock_blocked():
    status = chart_provider_effective_dashboard_status(
        {
            "checks": [
                {
                    "name": "chart_provider_effective",
                    "status": "WARN",
                    "checked_count": 2,
                    "fallback_count": 1,
                    "auth_fallback_count": 1,
                    "polygon_missing_count": 1,
                    "stock_issue_count": 1,
                    "crypto_issue_count": 0,
                    "operable_market_issue_count": 0,
                    "blocked_market_issue_count": 1,
                    "route_focus_label": "Crypto operable; stock/options bloqueado",
                    "fallback_reason_counts": {"alpaca_auth": 1},
                    "alternate_reason_counts": {"polygon_not_configured": 1},
                    "premium_recovery_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                    "detail": "issue WMT 1h alpaca_auth",
                }
            ]
        }
    )

    assert status["label"] == "Crypto operable"
    assert status["tone"] == "watch"
    assert status["operable_market_issue_count"] == 0
    assert status["blocked_market_issue_count"] == 1
    assert "Crypto operable; stock/options bloqueado" in status["detail"]
    assert "issues crypto 0, stock 1" in status["detail"]


def test_chart_provider_effective_display_table_lists_sources_and_reasons():
    table = chart_provider_effective_display_table(
        {
            "checks": [
                {
                    "name": "chart_provider_effective",
                    "results": [
                        {
                            "symbol": "WMT",
                            "market": "stock",
                            "timeframe": "1h",
                            "status": "WARN",
                            "provider": "yfinance",
                            "source": "yfinance",
                            "source_mode": "FALLBACK",
                            "fallback": True,
                            "fallback_reason": "alpaca_auth",
                            "fallback_action": "Revisar credenciales Alpaca.",
                            "polygon_fallback_reason": "polygon_not_configured",
                            "premium_recovery_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                        },
                        {
                            "symbol": "ETH/USD",
                            "market": "crypto",
                            "timeframe": "1h",
                            "status": "OK",
                            "provider": "ccxt",
                            "source": "ccxt:binanceus",
                            "source_mode": "EXCHANGE_API",
                            "fallback": False,
                        },
                    ],
                }
            ]
        }
    )

    assert list(table["Simbolo"]) == ["WMT", "ETH/USD"]
    assert table.loc[0, "Fallback"] == "Si"
    assert table.loc[0, "Motivo"] == "alpaca_auth"
    assert table.loc[0, "Alterno"] == "polygon_not_configured"
    assert "credenciales" in table.loc[0, "Accion"]
    assert "POLYGON_API_KEY" in table.loc[0, "Recuperacion"]
    assert table.loc[1, "Fallback"] == "No"


def test_provider_env_parity_dashboard_status_marks_service_env():
    status = provider_env_parity_dashboard_status(
        {
            "checks": [
                {
                    "name": "provider_env_parity",
                    "status": "INFO",
                    "detail": "LaunchAgent env has Alpaca credentials; current process env does not. Provider checks load LaunchAgent .env as effective service context.",
                    "launchd_alpaca_configured": True,
                    "process_alpaca_configured": False,
                    "effective_alpaca_configured": True,
                    "launchd_only_provider_keys": ["ALPACA_API_KEY", "ALPACA_API_SECRET"],
                    "process_only_provider_keys": [],
                }
            ]
        }
    )

    assert status["label"] == "Env efectivo"
    assert status["tone"] == "buy"
    assert status["launchd_alpaca_configured"] is True
    assert status["effective_alpaca_configured"] is True
    assert "launchd-only ALPACA_API_KEY" in status["detail"]


def test_provider_env_parity_dashboard_status_surfaces_alpaca_auth_probe():
    status = provider_env_parity_dashboard_status(
        {
            "checks": [
                {
                    "name": "provider_env_parity",
                    "status": "OK",
                    "detail": "LaunchAgent env has premium provider credentials; current process env does not.",
                    "launchd_alpaca_configured": True,
                    "process_alpaca_configured": False,
                    "effective_alpaca_configured": True,
                    "launchd_premium_configured": True,
                    "process_premium_configured": False,
                    "effective_premium_configured": True,
                    "launchd_only_provider_keys": ["ALPACA_API_KEY", "ALPACA_API_SECRET", "ALPACA_PAPER"],
                    "process_only_provider_keys": [],
                },
                {
                    "name": "alpaca_account_probe",
                    "status": "WARN",
                    "auth_ok": False,
                    "error_category": "AUTH_INVALID",
                    "mode": "paper",
                    "expected_endpoint": "https://paper-api.alpaca.markets",
                },
            ]
        }
    )

    assert status["label"] == "Env efectivo"
    assert status["tone"] == "watch"
    assert status["alpaca_account_auth_ok"] is False
    assert status["alpaca_account_probe_status"] == "WARN"
    assert status["alpaca_account_error_category"] == "AUTH_INVALID"
    assert "Alpaca auth no valida" in status["detail"]
    assert "error AUTH_INVALID" in status["detail"]
    assert "endpoint https://paper-api.alpaca.markets" in status["detail"]


def test_provider_env_parity_dashboard_status_marks_polygon_service_env():
    status = provider_env_parity_dashboard_status(
        {
            "checks": [
                {
                    "name": "provider_env_parity",
                    "status": "INFO",
                    "detail": "LaunchAgent env has premium provider credentials; current process env does not.",
                    "launchd_alpaca_configured": False,
                    "process_alpaca_configured": False,
                    "effective_alpaca_configured": False,
                    "launchd_premium_configured": True,
                    "process_premium_configured": False,
                    "effective_premium_configured": True,
                    "launchd_only_provider_keys": ["POLYGON_API_KEY"],
                    "process_only_provider_keys": [],
                }
            ]
        }
    )

    assert status["label"] == "Env efectivo"
    assert status["tone"] == "buy"
    assert status["launchd_premium_configured"] is True
    assert status["effective_premium_configured"] is True
    assert "POLYGON_API_KEY" in status["detail"]


def test_provider_env_parity_dashboard_status_escalates_local_only_env():
    status = provider_env_parity_dashboard_status(
        {
            "checks": [
                {
                    "name": "provider_env_parity",
                    "status": "WARN",
                    "detail": "Current process has Alpaca credentials but LaunchAgent env does not.",
                    "launchd_alpaca_configured": False,
                    "process_alpaca_configured": True,
                    "launchd_only_provider_keys": [],
                    "process_only_provider_keys": ["ALPACA_SECRET_KEY"],
                }
            ]
        }
    )

    assert status["label"] == "Env local"
    assert status["tone"] == "avoid"
    assert "process-only ALPACA_SECRET_KEY" in status["detail"]


def test_provider_env_parity_dashboard_status_accepts_aligned_env():
    status = provider_env_parity_dashboard_status(
        {
            "checks": [
                {
                    "name": "provider_env_parity",
                    "status": "OK",
                    "detail": "LaunchAgent env and current process both expose Alpaca credential names.",
                    "launchd_alpaca_configured": True,
                    "process_alpaca_configured": True,
                }
            ]
        }
    )

    assert status["label"] == "Env alineado"
    assert status["tone"] == "buy"


def test_provider_recovery_dashboard_status_surfaces_action():
    status = provider_recovery_dashboard_status(
        {
            "provider_recovery": {
                "label": "Premium bloqueado",
                "tone": "avoid",
                "detail": "3/4 acciones caen a fallback por auth/permisos.",
                "action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                "premium_blocked": True,
                "stock_alerts_allowed": False,
                "polygon_missing_count": 3,
                "auth_fallback_count": 3,
                "impacted_markets": ["stock", "options"],
                "safe_mode": "NO_STOCK_OR_OPTIONS_ALERTS",
                "confirmation_gate": "NO_TRADE_FROM_FALLBACK",
                "credential_scope": "launchd_only",
                "credential_diagnosis": "Alpaca esta configurado en LaunchAgent, pero cae en auth/permisos.",
                "primary_provider_issue": "alpaca_auth",
                "alternate_provider_issue": "polygon_not_configured",
                "alpaca_account_auth_ok": False,
                "alpaca_account_probe_status": "WARN",
                "alpaca_account_error_category": "AUTH_INVALID",
                "alpaca_account_mode": "paper",
                "alpaca_expected_endpoint": "https://paper-api.alpaca.markets",
                "recovery_priority": ["rotate_or_correct_alpaca_credentials", "configure_polygon_alternate"],
            }
        }
    )

    assert status["label"] == "Premium bloqueado"
    assert status["tone"] == "avoid"
    assert status["premium_blocked"] is True
    assert status["stock_alerts_allowed"] is False
    assert "Polygon falta 3" in status["detail"]
    assert "auth/perms 3" in status["detail"]
    assert "causa alpaca_auth" in status["detail"]
    assert "alterno polygon_not_configured" in status["detail"]
    assert "Alpaca auth no valida" in status["detail"]
    assert "error AUTH_INVALID" in status["detail"]
    assert "modo paper" in status["detail"]
    assert "endpoint https://paper-api.alpaca.markets" in status["detail"]
    assert "rotate_or_correct_alpaca_credentials" in status["detail"]
    assert "scope launchd_only" in status["detail"]
    assert "diagnostico Alpaca esta configurado en LaunchAgent" in status["detail"]
    assert "stock, options" in status["detail"]
    assert "NO_STOCK_OR_OPTIONS_ALERTS" in status["detail"]
    assert "NO_TRADE_FROM_FALLBACK" in status["detail"]
    assert "POLYGON_API_KEY" in status["detail"]
    assert status["credential_scope"] == "launchd_only"
    assert status["primary_provider_issue"] == "alpaca_auth"
    assert status["alternate_provider_issue"] == "polygon_not_configured"
    assert status["alpaca_account_auth_ok"] is False
    assert status["alpaca_account_error_category"] == "AUTH_INVALID"
    assert status["alpaca_account_mode"] == "paper"
    assert status["alpaca_expected_endpoint"] == "https://paper-api.alpaca.markets"


def test_provider_recovery_steps_table_turns_premium_blocker_into_action_plan():
    table = provider_recovery_steps_table(
        {
            "provider_recovery": {
                "status": "WARN",
                "label": "Premium bloqueado",
                "tone": "avoid",
                "detail": "3/4 acciones caen a fallback por auth/permisos.",
                "action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                "premium_blocked": True,
                "stock_alerts_allowed": False,
                "missing_provider_keys": ["POLYGON_API_KEY", "POLYGON_API_TOKEN"],
                "impacted_markets": ["stock", "options"],
                "safe_mode": "NO_STOCK_OR_OPTIONS_ALERTS",
                "confirmation_gate": "NO_TRADE_FROM_FALLBACK",
                "credential_scope": "launchd_only",
                "credential_diagnosis": "Alpaca esta configurado en LaunchAgent, pero cae en auth/permisos.",
                "primary_provider_issue": "alpaca_auth",
                "alpaca_account_auth_ok": False,
                "alpaca_account_probe_status": "WARN",
                "alpaca_account_error_category": "AUTH_INVALID",
                "alpaca_account_mode": "paper",
                "alpaca_expected_endpoint": "https://paper-api.alpaca.markets",
                "recovery_priority": ["rotate_or_correct_alpaca_credentials", "configure_polygon_alternate"],
                "recovery_steps": [
                    "Validar credenciales Alpaca.",
                    "Reejecutar tools/roxy_realtime_check.py --no-fail.",
                ],
            }
        }
    )

    assert not table.empty
    assert list(table.columns) == ["Prioridad", "Bloque", "Estado", "Accion", "Evidencia"]
    assert table.iloc[0]["Bloque"] == "Proteccion"
    assert "NO_TRADE_FROM_FALLBACK" in table.iloc[0]["Evidencia"]
    assert any(table["Bloque"] == "Credenciales")
    assert any(table["Bloque"] == "Alpaca probe")
    alpaca_row = table[table["Bloque"] == "Alpaca probe"].iloc[0]
    assert alpaca_row["Estado"] == "AUTH_INVALID"
    assert "ALPACA_API_KEY" in alpaca_row["Accion"]
    assert "endpoint https://paper-api.alpaca.markets" in alpaca_row["Evidencia"]
    assert any("POLYGON_API_KEY" in value for value in table["Evidencia"])
    assert any("rotate_or_correct_alpaca_credentials" in value for value in table["Estado"])
    assert any("Finviz/TradingView" in value for value in table["Accion"])
    assert table.iloc[-1]["Bloque"] == "Mercados"
    assert "stock, options" in table.iloc[-1]["Accion"]


def test_provider_recovery_steps_table_marks_confirmed_premium_as_ok():
    table = provider_recovery_steps_table(
        {
            "provider_recovery": {
                "status": "OK",
                "label": "Premium activo",
                "tone": "buy",
                "detail": "4 fuente(s) efectivas sin fallback premium.",
                "premium_blocked": False,
                "stock_alerts_allowed": True,
            }
        }
    )

    assert table.iloc[0]["Estado"] == "OK"
    assert "Proveedor premium confirmado" in table.iloc[0]["Accion"]
    assert "4 fuente(s)" in table.iloc[0]["Evidencia"]


def test_market_realtime_route_summary_forces_crypto_only_when_provider_blocks_premium():
    status = market_realtime_route_summary(
        {
            "provider_recovery": {
                "premium_blocked": True,
                "action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                "safe_mode": "NO_STOCK_OR_OPTIONS_ALERTS",
                "confirmation_gate": "NO_TRADE_FROM_FALLBACK",
                "alpaca_account_auth_ok": False,
                "alpaca_account_probe_status": "WARN",
                "alpaca_account_probe_diagnosis": "alpaca_account_auth_failed",
                "impacted_markets": ["stock", "options"],
            },
            "market_realtime": {
                "rows": [
                    {"market": "stock", "tone": "buy", "alerts_allowed": True, "label": "Acciones realtime"},
                    {"market": "crypto", "tone": "buy", "alerts_allowed": True, "label": "Cripto realtime"},
                    {"market": "options", "tone": "buy", "alerts_allowed": True, "label": "Opciones listas"},
                ]
            },
        }
    )

    assert status["label"] == "Operar solo CRYPTO"
    assert status["tone"] == "watch"
    assert status["allowed_markets"] == ["CRYPTO"]
    assert status["blocked_markets"] == ["STOCK", "OPTIONS"]
    assert "Realtime parcial" in status["detail"]
    assert "NO_STOCK_OR_OPTIONS_ALERTS" in status["detail"]
    assert "NO_TRADE_FROM_FALLBACK" in status["detail"]
    assert "Alpaca auth falla" in status["detail"]
    assert "POLYGON_API_KEY" in status["detail"]


def test_market_realtime_route_summary_prefers_operational_contract_over_provider_map():
    status = market_realtime_route_summary(
        {
            "provider_recovery": {
                "premium_blocked": False,
                "safe_mode": "PREMIUM_CONFIRMED",
                "confirmation_gate": "LIVE_CONFIRMED",
                "alpaca_account_auth_ok": False,
                "alpaca_account_probe_status": "WARN",
                "alpaca_account_probe_diagnosis": "alpaca_account_auth_failed",
                "alpaca_account_error_category": "AUTH_INVALID",
                "alpaca_account_mode": "paper",
                "alpaca_expected_endpoint": "https://paper-api.alpaca.markets",
            },
            "market_realtime": {
                "rows": [
                    {"market": "stock", "tone": "buy", "alerts_allowed": True, "label": "Acciones realtime"},
                    {"market": "crypto", "tone": "buy", "alerts_allowed": True, "label": "Cripto realtime"},
                    {"market": "options", "tone": "buy", "alerts_allowed": True, "label": "Opciones listas"},
                ]
            },
            "operational_summary": {
                "active_route_label": "Operar solo CRYPTO",
                "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                "allowed_markets": ["crypto"],
                "blocked_markets": ["stock", "options"],
                "safe_mode": "NO_STOCK_OR_OPTIONS_ALERTS",
                "confirmation_gate": "LIVE_CONFIRMED",
                "recommended_action": "Mantener watchlist; no alertar hasta que 15m confirme entrada",
            },
        }
    )

    assert status["label"] == "Operar solo CRYPTO"
    assert status["tone"] == "watch"
    assert status["allowed_markets"] == ["CRYPTO"]
    assert status["blocked_markets"] == ["STOCK", "OPTIONS"]
    assert "Operable CRYPTO" in status["detail"]
    assert "NO_STOCK_OR_OPTIONS_ALERTS" in status["detail"]
    assert "AUTH_INVALID" in status["detail"]
    assert "paper-api.alpaca.markets" in status["detail"]


def test_market_realtime_route_summary_closes_route_if_provider_blocks_all_markets():
    status = market_realtime_route_summary(
        {
            "provider_recovery": {
                "premium_blocked": True,
                "safe_mode": "NO_ALERTS_UNTIL_DATA_OK",
                "impacted_markets": ["stock", "options", "crypto"],
            },
            "market_realtime": {
                "rows": [
                    {"market": "stock", "tone": "buy", "alerts_allowed": True},
                    {"market": "crypto", "tone": "buy", "alerts_allowed": True},
                    {"market": "options", "tone": "buy", "alerts_allowed": True},
                ]
            },
        }
    )

    assert status["label"] == "Realtime bloqueado"
    assert status["tone"] == "avoid"
    assert status["allowed_markets"] == []
    assert status["blocked_markets"] == ["STOCK", "OPTIONS", "CRYPTO"]


def test_status_snapshot_route_summary_surfaces_crypto_only_route():
    status = status_snapshot_route_summary(
        {
            "active_route_label": "Operar solo CRYPTO",
            "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
            "allowed_markets": ["crypto"],
            "blocked_markets": ["stock", "options"],
            "safe_mode": "WAIT_FOR_CONFIRMATION",
            "recommended_action": "Mantener watchlist; no alertar hasta que 15m confirme entrada",
            "top_symbol": "BTC/USD",
            "top_gate": "WAIT_15M_ENTRY",
            "daily_plan_top_symbol": "BTC/USD",
            "daily_plan_top_stage": "PROXIMA_ENTRADA",
            "daily_plan_top_probability": 77,
            "daily_plan_operar_ahora": 0,
            "daily_plan_proxima_entrada": 7,
            "daily_plan_vigilar": 0,
            "daily_plan_total": 7,
        }
    )

    assert status["label"] == "Operar solo CRYPTO"
    assert status["tone"] == "watch"
    assert status["allowed_markets"] == ["CRYPTO"]
    assert status["blocked_markets"] == ["STOCK", "OPTIONS"]
    assert "Operable CRYPTO" in status["detail"]
    assert "WAIT_FOR_CONFIRMATION" in status["detail"]
    assert "Mantener watchlist" in status["detail"]
    assert "BTC/USD" in status["detail"]
    assert "Plan BTC/USD | PROXIMA_ENTRADA | 77% | alineado" in status["detail"]
    assert "Plan 24h operar 0, proximas 7, vigilar 0 / total 7" in status["detail"]
    assert status["daily_plan_top_symbol"] == "BTC/USD"
    assert status["daily_plan_top_stage"] == "PROXIMA_ENTRADA"
    assert status["daily_plan_top_probability"] == 77.0
    assert status["daily_plan_operar_ahora"] == 0
    assert status["daily_plan_proxima_entrada"] == 7
    assert status["daily_plan_vigilar"] == 0
    assert status["daily_plan_total"] == 7
    assert status["daily_plan_matches_top"] is True
    assert status["daily_plan_matches_focus"] is False


def test_status_snapshot_route_summary_falls_back_without_route_label():
    status = status_snapshot_route_summary(
        {
            "allowed_markets": ["crypto"],
            "blocked_markets": ["stock", "options"],
        }
    )

    assert status["label"] == "Operar solo CRYPTO"
    assert status["tone"] == "watch"
    assert "Operable CRYPTO" in status["detail"]


def test_status_snapshot_route_summary_flags_daily_plan_snapshot_mismatch():
    status = status_snapshot_route_summary(
        {
            "allowed_markets": ["crypto"],
            "top_symbol": "ETH/USD",
            "top_gate": "WAIT_15M_ENTRY",
            "status_snapshot_daily_top_symbol": "SOL/USD",
            "status_snapshot_daily_top_stage": "PROXIMA_ENTRADA",
            "status_snapshot_daily_top_probability": 82,
            "status_snapshot_daily_operar_ahora": 1,
            "status_snapshot_daily_proxima_entrada": 3,
            "status_snapshot_daily_total": 5,
        }
    )

    assert status["tone"] == "buy"
    assert status["daily_plan_top_symbol"] == "SOL/USD"
    assert status["daily_plan_matches_top"] is False
    assert status["daily_plan_matches_focus"] is False
    assert "Top ETH/USD | WAIT_15M_ENTRY" in status["detail"]
    assert "Plan SOL/USD | PROXIMA_ENTRADA | 82% | distinto al top snapshot" in status["detail"]
    assert "Plan 24h operar 1, proximas 3 / total 5" in status["detail"]


def test_status_snapshot_route_summary_surfaces_operational_focus_override():
    status = status_snapshot_route_summary(
        {
            "allowed_markets": ["crypto"],
            "top_symbol": "ETH/USD",
            "top_gate": "WAIT_15M_ENTRY",
            "operational_focus_symbol": "BTC/USD",
            "operational_focus_source": "ALERT_QUALITY_ROTATION",
            "operational_focus_reason": "Rotacion activa: ETH/USD vencido; siguiente foco BTC/USD.",
            "operational_focus_overrides_top": True,
            "daily_plan_top_symbol": "ETH/USD",
            "daily_plan_top_stage": "PROXIMA_ENTRADA",
            "daily_plan_top_probability": 85,
        }
    )

    assert status["operational_focus_symbol"] == "BTC/USD"
    assert status["operational_focus_source"] == "ALERT_QUALITY_ROTATION"
    assert status["operational_focus_overrides_top"] is True
    assert "Foco BTC/USD | ALERT_QUALITY_ROTATION" in status["detail"]
    assert "ETH/USD vencido" in status["detail"]
    assert status["daily_plan_matches_top"] is True
    assert status["daily_plan_matches_focus"] is False
    assert "Plan ETH/USD | PROXIMA_ENTRADA | 85% | distinto al foco operativo" in status["detail"]


def test_status_snapshot_route_summary_marks_daily_plan_aligned_to_operational_focus():
    status = status_snapshot_route_summary(
        {
            "allowed_markets": ["crypto"],
            "top_symbol": "ETH/USD",
            "top_gate": "WAIT_15M_ENTRY",
            "operational_focus_symbol": "BTC/USD",
            "operational_focus_source": "ALERT_QUALITY_ROTATION",
            "operational_focus_reason": "Rotacion activa: ETH/USD vencido; siguiente foco BTC/USD.",
            "operational_focus_overrides_top": True,
            "daily_plan_top_symbol": "BTC/USD",
            "daily_plan_top_stage": "PROXIMA_ENTRADA",
            "daily_plan_top_probability": 85,
        }
    )

    assert status["daily_plan_matches_top"] is False
    assert status["daily_plan_matches_focus"] is True
    assert "Foco BTC/USD | ALERT_QUALITY_ROTATION" in status["detail"]
    assert "Plan BTC/USD | PROXIMA_ENTRADA | 85% | alineado al foco" in status["detail"]


def test_default_trade_plan_symbol_prefers_operational_rotation_focus(monkeypatch):
    monkeypatch.setattr(
        streamlit_app,
        "read_summary_json",
        lambda path: {
            "operational_focus_symbol": "BTC/USD",
            "operational_focus_source": "ALERT_QUALITY_ROTATION",
        }
        if path == "alerts/roxy_status.json"
        else {},
    )
    brief = {
        "opportunities": [
            {"symbol": "ETH/USD", "market": "crypto", "ai_score": 90, "ai_action": "WATCH"},
            {"symbol": "BTC/USD", "market": "crypto", "ai_score": 82, "ai_action": "WATCH"},
        ]
    }

    symbol = default_trade_plan_symbol(pd.DataFrame(), brief)

    assert symbol == "BTC/USD"


def test_default_trade_plan_symbol_ignores_stale_operational_focus(monkeypatch):
    monkeypatch.setattr(
        streamlit_app,
        "read_summary_json",
        lambda path: {
            "operational_focus_symbol": "SOL/USD",
            "operational_focus_source": "ALERT_QUALITY_ROTATION",
        }
        if path == "alerts/roxy_status.json"
        else {},
    )
    brief = {
        "opportunities": [
            {"symbol": "ETH/USD", "market": "crypto", "ai_score": 90, "ai_action": "WATCH"},
            {"symbol": "BTC/USD", "market": "crypto", "ai_score": 82, "ai_action": "WATCH"},
        ]
    }

    symbol = default_trade_plan_symbol(pd.DataFrame(), brief)

    assert symbol == "ETH/USD"


def test_status_snapshot_market_gate_blocks_stock_outside_crypto_route():
    gate = status_snapshot_market_gate(
        {
            "active_route_label": "Operar solo CRYPTO",
            "allowed_markets": ["crypto"],
            "blocked_markets": ["stock", "options"],
            "safe_mode": "WAIT_FOR_CONFIRMATION",
        },
        "stock",
        "AAPL",
    )

    assert gate["blocked"] is True
    assert gate["allowed"] is False
    assert gate["label"] == "Mercado bloqueado"
    assert gate["tone"] == "avoid"
    assert gate["market"] == "STOCK"
    assert "AAPL esta en STOCK" in gate["detail"]
    assert gate["route_label"] == "Operar solo CRYPTO"


def test_status_snapshot_market_gate_allows_crypto_inside_crypto_route():
    gate = status_snapshot_market_gate(
        {
            "active_route_label": "Operar solo CRYPTO",
            "allowed_markets": ["crypto"],
            "blocked_markets": ["stock", "options"],
        },
        "crypto",
        "BTC/USD",
    )

    assert gate["blocked"] is False
    assert gate["allowed"] is True
    assert gate["label"] == "Ruta permitida"
    assert gate["tone"] == "buy"
    assert "BTC/USD puede analizarse" in gate["detail"]


def test_command_center_side_panel_renders_status_route():
    source = function_source_from_file("streamlit_app.py", "render_command_center_live_panel")

    assert "route_status = status_snapshot_route_summary(status)" in source
    assert '"Ruta RT"' in source
    assert 'route_status["label"]' in source


def test_command_center_blocks_market_before_loading_context():
    source = function_source_from_file("streamlit_app.py", "render_command_center_live_panel")
    gate_index = source.index("market_gate = status_snapshot_market_gate(")
    load_index = source.index("load_symbol_trade_context(")

    assert gate_index < load_index
    assert 'if market_gate.get("blocked"):' in source
    assert "st.warning(market_gate[\"detail\"])" in source
    assert '"Ruta operativa"' in source


def test_realtime_data_readiness_blocks_premium_claim_on_auth_fallback():
    status = realtime_data_readiness_status(
        {"label": "Frescos", "tone": "buy", "detail": "2 min"},
        {
            "label": "Auth/permisos",
            "tone": "avoid",
            "checked_count": 4,
            "fallback_count": 4,
            "auth_fallback_count": 4,
            "detail": "alpaca_auth x4",
        },
        {"label": "Env alineado", "tone": "buy"},
    )

    assert status["label"] == "Premium bloqueado"
    assert status["tone"] == "avoid"
    assert "4/4" in status["detail"]
    assert "fallback" in status["detail"]


def test_realtime_data_readiness_blocks_premium_claim_on_account_auth_probe():
    status = realtime_data_readiness_status(
        {"label": "Frescos", "tone": "buy", "detail": "2 min"},
        {
            "label": "Fuente OK",
            "tone": "buy",
            "checked_count": 6,
            "fallback_count": 0,
            "auth_fallback_count": 0,
            "detail": "6 provider source(s), fallback 0",
        },
        {
            "label": "Env efectivo",
            "tone": "watch",
            "detail": "LaunchAgent env cargado. Alpaca auth no valida.",
            "alpaca_account_auth_ok": False,
            "alpaca_account_probe_status": "WARN",
            "alpaca_account_error_category": "AUTH_INVALID",
            "alpaca_account_mode": "paper",
            "alpaca_expected_endpoint": "https://paper-api.alpaca.markets",
        },
    )

    assert status["label"] == "Premium revisar"
    assert status["tone"] == "watch"
    assert "AUTH_INVALID" in status["detail"]
    assert "paper" in status["detail"]
    assert "Premium live" not in status["detail"]


def test_realtime_data_readiness_distinguishes_fresh_fallback_from_premium_live():
    fallback = realtime_data_readiness_status(
        {"label": "Frescos", "tone": "buy", "detail": "1 min"},
        {
            "label": "Fallback",
            "tone": "watch",
            "checked_count": 3,
            "fallback_count": 2,
            "auth_fallback_count": 0,
        },
        {"label": "Sin premium", "tone": "watch"},
    )
    premium = realtime_data_readiness_status(
        {"label": "Frescos", "tone": "buy", "detail": "1 min"},
        {"label": "Fuente OK", "tone": "buy", "checked_count": 3, "fallback_count": 0},
        {"label": "Env alineado", "tone": "buy"},
    )

    assert fallback["label"] == "Fallback live"
    assert fallback["tone"] == "watch"
    assert premium["label"] == "Premium live"
    assert premium["tone"] == "buy"


def test_realtime_data_readiness_keeps_crypto_operable_when_stock_is_blocked():
    status = realtime_data_readiness_status(
        {"label": "Frescos", "tone": "buy", "detail": "1 min"},
        {
            "label": "Crypto operable",
            "tone": "watch",
            "checked_count": 2,
            "fallback_count": 1,
            "auth_fallback_count": 1,
            "operable_market_issue_count": 0,
            "blocked_market_issue_count": 1,
            "route_focus_label": "Crypto operable; stock/options bloqueado",
        },
        {"label": "LaunchAgent premium", "tone": "watch"},
    )

    assert status["label"] == "Crypto operable"
    assert status["tone"] == "watch"
    assert "stock/options" in status["detail"]
    assert "Roxy opera en fallback" not in status["detail"]


def test_realtime_data_readiness_prioritizes_stale_files():
    status = realtime_data_readiness_status(
        {"label": "Estancados", "tone": "avoid", "detail": "95 min"},
        {"label": "Fuente OK", "tone": "buy", "checked_count": 2},
        {"label": "Env alineado", "tone": "buy"},
    )

    assert status["label"] == "Datos parados"
    assert status["tone"] == "avoid"
    assert "95 min" in status["detail"]


def test_build_chart_level_plan_includes_trade_levels():
    chart_df = pd.DataFrame(
        [
            {
                "ts": pd.Timestamp("2026-06-07 10:00"),
                "close": 100,
                "range_low_60": 96,
                "range_high_60": 106,
                "sma20": 99,
                "sma40": 98,
                "sma100": 95,
                "sma200": 90,
            }
        ]
    )
    rows = build_chart_level_plan(
        chart_df,
        {"entry": 100, "stop": 97},
        {},
        {"target_ladder": [{"target": "2%", "target_price": 102}, {"target": "5%", "target_price": 105}]},
    )
    by_level = {row["nivel"]: row for row in rows}

    assert by_level["Entrada"]["precio"] == 100
    assert by_level["Stop"]["precio"] == 97
    assert by_level["Objetivo 2%"]["precio"] == 102
    assert round(by_level["Objetivo 10%"]["precio"], 2) == 110
    assert by_level["Soporte"]["precio"] == 96
    assert by_level["SMA200"]["precio"] == 90


def test_build_visual_zone_rows_marks_entry_stop_and_range_zones():
    chart_df = pd.DataFrame(
        [
            {
                "ts": pd.Timestamp("2026-06-07 10:00"),
                "close": 100,
                "range_low_60": 96,
                "range_high_60": 106,
                "atr_pct": 0.02,
            },
            {
                "ts": pd.Timestamp("2026-06-07 11:00"),
                "close": 101,
                "range_low_60": 97,
                "range_high_60": 107,
                "atr_pct": 0.02,
            },
        ]
    )

    rows = build_visual_zone_rows(chart_df, {"entry": 101, "stop": 98}, {}, {})
    by_zone = {row["zone"]: row for row in rows}

    assert by_zone["Zona entrada"]["tone"] == "buy"
    assert by_zone["Zona stop"]["tone"] == "avoid"
    assert by_zone["Soporte"]["center"] == 97
    assert by_zone["Resistencia"]["center"] == 107


def test_build_visual_zone_rows_ignores_far_range_outliers():
    chart_df = pd.DataFrame(
        [
            {
                "ts": pd.Timestamp("2026-06-07 10:00"),
                "close": 100,
                "range_low_60": 20,
                "range_high_60": 800,
                "atr_pct": 0.02,
            },
            {
                "ts": pd.Timestamp("2026-06-07 11:00"),
                "close": 101,
                "range_low_60": 19,
                "range_high_60": 820,
                "atr_pct": 0.02,
            },
        ]
    )

    rows = build_visual_zone_rows(chart_df, {"entry": 101, "stop": 98}, {}, {})
    zones = {row["zone"] for row in rows}

    assert {"Zona entrada", "Zona stop"}.issubset(zones)
    assert "Soporte" not in zones
    assert "Resistencia" not in zones


def test_greek_quality_label_distinguishes_full_estimated_and_missing_data():
    full = greek_quality_label({"delta": 0.45, "gamma": 0.02, "theta": -0.04, "vega": 0.11})
    estimated = greek_quality_label({"delta": 0.45, "impliedVolatility": 0.5})
    missing = greek_quality_label({})

    assert full[0] == "Completo"
    assert estimated[0] == "Basico estimado"
    assert missing[0] == "Incompleto"


def test_annotate_option_greek_quality_adds_human_columns():
    options = pd.DataFrame(
        [
            {"contractSymbol": "AAPL260619C00200000", "delta": 0.44, "impliedVolatility": 0.50},
            {"contractSymbol": "AAPL260619C00205000"},
        ]
    )

    annotated = annotate_option_greek_quality(options)

    assert annotated.loc[0, "greek_quality"] == "Basico estimado"
    assert annotated.loc[1, "greek_quality"] == "Incompleto"


def test_lab_daily_summary_rows_selects_operational_focus():
    rows = lab_daily_summary_rows(
        [
            {"strategy_family": "Pullback", "lab_state": "Promote", "evidence_score": 0.72, "production_action": "Subir ranking"},
            {"strategy_family": "Canal lateral", "lab_state": "Tighten filter", "evidence_score": 0.22, "lab_decision": "Exigir volumen"},
            {"strategy_family": "Cruce de medias", "lab_state": "Collect data", "evidence_score": 0.30},
        ]
    )
    by_label = {row["label"]: row for row in rows}

    assert by_label["Promover"]["strategy"] == "Pullback"
    assert by_label["Endurecer"]["strategy"] == "Canal lateral"
    assert by_label["Estudiar"]["strategy"] == "Cruce de medias"


def test_prepare_chart_window_cleans_and_repairs_price_columns():
    raw = pd.DataFrame(
        [
            {"ts": "bad-date", "close": 100, "open": 101, "high": 102, "low": 99},
            {"ts": "2026-01-02", "close": "101", "open": None, "high": 100, "low": 103},
            {"ts": "2026-01-01", "close": "100", "volume": "1000"},
        ]
    )

    cleaned = prepare_chart_window(raw)

    assert cleaned["ts"].is_monotonic_increasing
    assert len(cleaned) == 2
    assert cleaned.loc[0, "open"] == 100
    assert cleaned.loc[1, "high"] >= cleaned.loc[1, "close"]
    assert cleaned.loc[1, "low"] <= cleaned.loc[1, "close"]


def test_chart_price_domain_includes_trade_levels_with_padding():
    chart_window = prepare_chart_window(
        pd.DataFrame(
            [
                {"ts": "2026-01-01", "open": 100, "high": 102, "low": 98, "close": 101, "volume": 1000},
                {"ts": "2026-01-02", "open": 101, "high": 104, "low": 100, "close": 103, "volume": 1200},
            ]
        )
    )

    domain = chart_price_domain(
        chart_window,
        {"entry": 103, "stop": 99},
        {"recommended_target_price": 108},
        {"target_ladder": [{"target": "10%", "target_price": 113}]},
    )

    assert domain is not None
    assert domain[0] < 99
    assert domain[1] > 113


def test_chart_price_domain_ignores_far_high_low_and_channel_outliers():
    chart_window = prepare_chart_window(
        pd.DataFrame(
            [
                {
                    "ts": "2026-01-01",
                    "open": 100,
                    "high": 900,
                    "low": 20,
                    "close": 101,
                    "range_high_60": 900,
                    "range_low_60": 20,
                    "volume": 1000,
                },
                {
                    "ts": "2026-01-02",
                    "open": 101,
                    "high": 850,
                    "low": 18,
                    "close": 103,
                    "range_high_60": 850,
                    "range_low_60": 18,
                    "volume": 1200,
                },
            ]
        )
    )

    domain = chart_price_domain(chart_window, {"entry": 103, "stop": 99}, {"recommended_target_price": 108}, {})

    assert domain is not None
    assert 70 < domain[0] < 99
    assert 108 < domain[1] < 150


def test_build_price_hover_layers_adds_crosshair_and_media_tooltips():
    chart_window = prepare_chart_window(
        pd.DataFrame(
            [
                {
                    "ts": "2026-01-01 10:00",
                    "open": 100,
                    "high": 102,
                    "low": 98,
                    "close": 101,
                    "volume": 1000,
                    "ema9": 100.5,
                    "sma20": 99.5,
                    "sma40": 98.5,
                    "sma100": 96,
                    "sma200": 92,
                },
                {
                    "ts": "2026-01-01 11:00",
                    "open": 101,
                    "high": 104,
                    "low": 100,
                    "close": 103,
                    "volume": 1200,
                    "ema9": 101.5,
                    "sma20": 100,
                    "sma40": 99,
                    "sma100": 97,
                    "sma200": 93,
                },
            ]
        )
    )

    layers = build_price_hover_layers(chart_window)
    specs = [layer.to_dict() for layer in layers]
    joined = str(specs)

    assert len(layers) == 4
    assert "candle_hover" in joined
    assert sum(1 for spec in specs if spec.get("mark", {}).get("type") == "rule") == 2
    assert "transform" not in joined
    assert "Rango precio" in joined
    assert "Cuerpo precio" in joined
    assert "EMA9" in joined
    assert "SMA200" in joined


def test_build_professional_price_chart_includes_hover_cursor():
    chart_df = pd.DataFrame(
        [
            {"ts": "2026-01-01", "open": 100, "high": 102, "low": 98, "close": 101, "volume": 1000, "sma20": 99},
            {
                "ts": "2026-01-02",
                "open": 101,
                "high": 104,
                "low": 100,
                "close": 103,
                "volume": 1200,
                "volume_sma20": 600,
                "sma20": 100,
            },
        ]
    )

    chart = build_professional_price_chart(chart_df, {"entry": 103, "stop": 99}, {}, {})
    spec = chart.to_dict()

    assert "params" in spec
    assert any(param.get("name") == "candle_hover" for param in spec["params"])
    assert "candle_hover" in str(spec)
    assert "2026-01-01T00:00:00" in str(spec)
    assert "2026-01-02T00:00:00" in str(spec)
    assert "RVol 2.00x" in str(spec)
    assert "Volumen confirma" in str(spec)
    assert "Cerca de resistencia visible" in str(spec)
    assert "Zona alta" in str(spec)
    assert "No perseguir: cerca de resistencia" in str(spec)
    assert "Siguiente paso" in str(spec)
    assert "watch" in str(spec)
    assert "#f59e0b" in str(spec)
    latest_tones = []
    for layer in spec.get("layer", []):
        encoding = layer.get("encoding", {})
        if encoding.get("color", {}).get("field") == "tone":
            data_name = layer.get("data", {}).get("name")
            latest_tones.extend(row.get("tone") for row in spec.get("datasets", {}).get(data_name, []))
    assert "watch" in latest_tones
    assert "En entrada" in str(spec)
    assert "Stop -3.9%" in str(spec)
    assert "Target +2.0%" in str(spec)
    assert "R/R" in str(spec)
    level_labels = []
    for layer in spec.get("layer", []):
        mark = layer.get("mark", {})
        encoding = layer.get("encoding", {})
        if isinstance(mark, dict) and mark.get("type") == "text" and encoding.get("text", {}).get("field") == "label_text":
            data_name = layer.get("data", {}).get("name")
            level_labels.extend(row.get("label_text", "") for row in spec.get("datasets", {}).get(data_name, []))
    assert any("Objetivo 5%" in label for label in level_labels)
    assert any("Objetivo 10%" in label for label in level_labels)


def test_build_professional_price_chart_can_disable_hover_for_live_refresh():
    chart_df = pd.DataFrame(
        [
            {"ts": "2026-01-01", "open": 100, "high": 102, "low": 98, "close": 101, "volume": 1000, "sma20": 99},
            {"ts": "2026-01-02", "open": 101, "high": 104, "low": 100, "close": 103, "volume": 1200, "sma20": 100},
        ]
    )

    chart = build_professional_price_chart(chart_df, {"entry": 103, "stop": 99}, {}, {}, hover_interactive=False)
    spec = chart.to_dict()

    assert "candle_hover" not in str(spec)
    assert "2026-01-01T00:00:00" in str(spec)
    assert "2026-01-02T00:00:00" in str(spec)


def test_static_live_price_chart_svg_renders_candles_without_vega_runtime():
    chart_df = pd.DataFrame(
        [
            {"ts": "2026-01-01", "open": 100, "high": 102, "low": 98, "close": 101, "sma20": 99},
            {"ts": "2026-01-02", "open": 101, "high": 104, "low": 100, "close": 103, "sma20": 100},
        ]
    )

    svg = static_live_price_chart_svg(chart_df, symbol="LINK/USD<script>", height=320)

    assert "<svg" in svg
    assert "<rect" in svg
    assert "<polyline" in svg
    assert "vega" not in svg.lower()
    assert "LINK/USD&lt;script&gt;" in svg


def test_build_professional_price_chart_zone_overlays_do_not_infer_time_extent():
    chart_df = pd.DataFrame(
        [
            {
                "ts": "2026-01-01",
                "open": 100,
                "high": 102,
                "low": 98,
                "close": 101,
                "volume": 1000,
                "range_low_60": 99,
                "range_high_60": 105,
            },
            {
                "ts": "2026-01-02",
                "open": 101,
                "high": 104,
                "low": 100,
                "close": 103,
                "volume": 1200,
                "range_low_60": 100,
                "range_high_60": 106,
            },
        ]
    )

    chart = build_professional_price_chart(chart_df, {"entry": 103, "stop": 99}, {}, {})
    spec_text = str(chart.to_dict())

    assert "ts2" in spec_text
    assert "ts_start" in spec_text
    assert "ts_end" in spec_text
    assert "label_ts" not in spec_text


def test_build_professional_oscillator_chart_uses_rsi_and_macd():
    chart_df = pd.DataFrame(
        [
            {
                "ts": f"2026-01-{day:02d}",
                "open": 100 + day,
                "high": 101 + day,
                "low": 99 + day,
                "close": 100 + day,
                "volume": 1000,
                "rsi14": 45 + day,
                "macd_hist": (-1) ** day * 0.05,
            }
            for day in range(1, 8)
        ]
    )

    chart = build_professional_oscillator_chart(chart_df)

    assert chart is not None
    spec = chart.to_dict()
    assert "layer" in spec
    assert "resolve" in spec
    assert "2026-01-01T00:00:00" in str(spec)
    assert "2026-01-07T00:00:00" in str(spec)


def test_build_professional_volume_chart_pins_time_domain():
    chart_df = pd.DataFrame(
        [
            {"ts": "2026-01-01", "open": 100, "high": 102, "low": 98, "close": 101, "volume": 1000},
            {"ts": "2026-01-02", "open": 101, "high": 104, "low": 100, "close": 103, "volume": 1200},
        ]
    )

    chart = build_professional_volume_chart(chart_df)

    assert chart is not None
    spec_text = str(chart.to_dict())
    assert "2026-01-01T00:00:00" in spec_text
    assert "2026-01-02T00:00:00" in spec_text


def test_build_mini_opportunity_chart_pins_time_domain():
    chart_df = pd.DataFrame(
        [
            {"ts": "2026-01-01", "open": 100, "high": 102, "low": 98, "close": 101, "volume": 1000},
            {"ts": "2026-01-02", "open": 101, "high": 104, "low": 100, "close": 103, "volume": 1200},
        ]
    )

    chart = build_mini_opportunity_chart(chart_df)
    spec_text = str(chart.to_dict())

    assert "2026-01-01T00:00:00" in spec_text
    assert "2026-01-02T00:00:00" in spec_text


def test_build_professional_oscillator_chart_returns_none_without_oscillators():
    chart_df = pd.DataFrame(
        [
            {"ts": "2026-01-01", "open": 100, "high": 102, "low": 98, "close": 101, "volume": 1000},
            {"ts": "2026-01-02", "open": 101, "high": 104, "low": 100, "close": 103, "volume": 1200},
        ]
    )

    assert build_professional_oscillator_chart(chart_df) is None
