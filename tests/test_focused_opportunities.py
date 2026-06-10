import pandas as pd
from datetime import datetime, timedelta
from collections import namedtuple

from streamlit_app import (
    annotate_options_risk_budget,
    annotate_option_greek_quality,
    annotate_professional_options_contracts,
    alert_preview_table,
    alert_gate_summary_dashboard_status,
    alert_quality_report_dashboard_status,
    autoheal_dashboard_status,
    asset_type_label,
    build_realtime_refresh_script,
    build_chart_level_plan,
    build_professional_oscillator_chart,
    chart_price_domain,
    build_visual_zone_rows,
    build_command_center_summary,
    chart_realtime_dashboard_status,
    chart_freshness_status,
    chart_strategy_summary,
    command_center_checklist_rows,
    command_center_target_prices,
    center_decision_summary,
    connection_mode_label,
    operational_mode_dashboard_status,
    data_freshness_status,
    disk_dashboard_status,
    execution_blocker_label,
    focused_display_table_es,
    focused_display_table,
    focused_opportunity_table,
    greek_quality_label,
    health_history_dashboard_status,
    health_history_display_table,
    health_notify_dashboard_status,
    heartbeat_artifact_path,
    lab_daily_summary_rows,
    load_health_history,
    load_latest_ma_scan,
    live_backend_status,
    notification_channel_display,
    notification_history_display_table,
    notification_history_dashboard_status,
    normalize_realtime_refresh_interval,
    opportunity_change_label,
    opportunity_confidence_label,
    opportunity_is_trade_ready,
    output_maintenance_dashboard_status,
    opportunity_reason_label,
    prepare_chart_window,
    prepare_options_view,
    professional_options_feed_status,
    platform_badge_rows,
    platform_reason_label,
    platform_status_label,
    realtime_report_check_card,
    realtime_check_status,
    realtime_lock_dashboard_status,
    realtime_refresh_dashboard_status,
    resolve_study_strategy_choice,
    runtime_backup_dashboard_status,
    safe_key,
    stability_summary_dashboard_status,
    strategy_family_for_row,
    study_example_rows,
    study_guides_with_lab,
    trade_plan_platform_preview,
    timeframe_minutes,
    watch_movement_label,
)
import streamlit_app


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

    assert annotated.loc[0, "professional_readiness"] == "Listo para revisar"
    assert annotated.loc[0, "max_loss_per_contract"] == 500
    assert annotated.loc[0, "breakeven_price"] == 205
    assert annotated.loc[0, "professional_blockers"] == "OK"
    assert annotated.loc[1, "professional_readiness"] == "Faltan Greeks"
    assert "Spread alto" in annotated.loc[1, "professional_blockers"]


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
    assert normalize_realtime_refresh_interval("bad") == 60
    assert normalize_realtime_refresh_interval(280) == 300


def test_build_realtime_refresh_script_pauses_while_user_is_active():
    script = build_realtime_refresh_script(120)

    assert "120000" in script
    assert "__roxyRealtimeRefreshTimer" in script
    assert "clearTimeout" in script
    assert "visibilityState" in script
    assert "INPUT" in script
    assert "location.reload" in script


def test_realtime_refresh_dashboard_status_summarizes_state():
    enabled = realtime_refresh_dashboard_status({"enabled": True, "interval_seconds": 30})
    disabled = realtime_refresh_dashboard_status({"enabled": False, "interval_seconds": 30})

    assert enabled["label"] == "ON"
    assert enabled["tone"] == "buy"
    assert "30s" in enabled["detail"]
    assert disabled["label"] == "OFF"
    assert disabled["tone"] == "watch"


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
                    "removed_alert_report_count": 3,
                    "dry_run": False,
                }
            ],
        },
        {
            "prepared_dir_count": 2,
            "prepared_dir_error_count": 0,
            "output_archive_exists": True,
            "log_snapshot_dir_exists": True,
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
    assert "reportes 3" in status["detail"]


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
                    "archive_verified_paths": ["alerts", "db", "data"],
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
            "ai_brief_autoheal": {"action": "regenerated", "ok": True},
            "alert_quality_autoheal": {"action": "regenerated", "ok": True},
        }
    )

    assert status["label"] == "OK"
    assert status["tone"] == "buy"
    assert status["routine_refresh"] is True
    assert "brief regenerated" in status["detail"]
    assert "alertas regenerated" in status["detail"]


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
    assert "Traceback" not in table.loc[0, "top_detail"]
    assert "fallo Python recuperado" in table.loc[0, "top_detail"]


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
    assert "recurrente external_disk x2" in status["detail"]


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
    assert "top AMAT" in status["detail"]
    assert "Esperar gatillo BUY en 15m." in status["detail"]


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
    blocked = realtime_lock_dashboard_status({"event": "blocked", "pid": 123, "age_minutes": 4.25})
    acquired = realtime_lock_dashboard_status({"event": "acquired", "pid": 124, "generated_at": "2026-06-10T12:00:00+00:00"})
    replaced = realtime_lock_dashboard_status(
        {"event": "acquired", "pid": 125, "generated_at": "2026-06-10T12:01:00+00:00", "stale_replaced": True}
    )
    released = realtime_lock_dashboard_status({"event": "released", "released_at": "2026-06-10T12:02:00+00:00"})

    assert blocked["label"] == "Ocupado"
    assert blocked["tone"] == "watch"
    assert "age 4.2m" in blocked["detail"]
    assert acquired["label"] == "Activo"
    assert acquired["tone"] == "neutral"
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
                "stalest_chart": {"symbol": "NVDA", "timeframe": "1h"},
                "top_issue": {"symbol": "AAPL", "timeframe": "15m"},
            }
        }
    )

    assert status["label"] == "Graficas revisar"
    assert status["tone"] == "watch"
    assert "4 charts" in status["detail"]
    assert "max 24.5m" in status["detail"]
    assert "avg 11.2m" in status["detail"]
    assert "calidad 1" in status["detail"]
    assert "AAPL 15m" in status["detail"]
    assert status["max_age_minutes"] == 24.5
    assert status["avg_age_minutes"] == 11.2
    assert status["stalest_chart"] == {"symbol": "NVDA", "timeframe": "1h"}


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


def test_build_professional_oscillator_chart_returns_none_without_oscillators():
    chart_df = pd.DataFrame(
        [
            {"ts": "2026-01-01", "open": 100, "high": 102, "low": 98, "close": 101, "volume": 1000},
            {"ts": "2026-01-02", "open": 101, "high": 104, "low": 100, "close": 103, "volume": 1200},
        ]
    )

    assert build_professional_oscillator_chart(chart_df) is None
