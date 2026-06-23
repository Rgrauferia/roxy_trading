from smart_alerts import evaluate_smart_alert


def test_smart_alert_ready_requires_full_checklist():
    row = {
        "market": "stock",
        "symbol": "AAPL",
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

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is True
    assert gate["gate"] == "ALERT_READY"
    assert gate["quality"] == "A+"
    assert gate["primary_blocker"] == "Listo para preview manual"
    assert gate["next_action"].startswith("Preparar plan manual")
    assert gate["passed_count"] == gate["total_checks"]
    assert gate["blockers"] == []


def test_smart_alert_blocks_ready_setup_when_chart_contract_is_not_operable():
    row = {
        "market": "crypto",
        "symbol": "ETH/USD",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 88,
        "trend_score": 82,
        "trigger_score": 78,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.25,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "chart_data_gate": "NO_TRADE_FROM_FALLBACK",
        "chart_operable": False,
        "chart_source_label": "yfinance fallback",
        "chart_candle_phase_label": "Vela retrasada",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "BLOCKED_REALTIME_DATA"
    assert gate["quality"] == "C"
    assert gate["primary_blocker"].startswith("Grafica operable")
    assert "NO_TRADE_FROM_FALLBACK" in gate["primary_blocker"]
    assert "grafica no operable" in gate["movement"]
    assert any(item["rule"] == "Grafica operable" and not item["passed"] for item in gate["checks"])


def test_smart_alert_accepts_live_chart_contract_for_ready_crypto_setup():
    row = {
        "market": "crypto",
        "symbol": "ETH/USD",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 88,
        "trend_score": 82,
        "trigger_score": 78,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.25,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "chart_data_contract": {
            "gate": "LIVE_DATA_OK",
            "operable": True,
            "source_label": "BinanceUS API",
            "candle_phase_label": "Vela nueva",
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is True
    assert gate["gate"] == "ALERT_READY"
    assert any(
        item["rule"] == "Grafica operable" and item["passed"] and "BinanceUS API" in item["detail"]
        for item in gate["checks"]
    )


def test_smart_alert_blocks_ready_setup_when_live_price_is_public_fallback():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 88,
        "trend_score": 82,
        "trigger_score": 78,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.25,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "live_price_contract": {
            "gate": "NO_TRADE_FROM_PUBLIC_PRICE",
            "operable": False,
            "source_label": "yfinance 1m",
            "candle_phase_label": "FRESH",
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "BLOCKED_REALTIME_DATA"
    assert "NO_TRADE_FROM_PUBLIC_PRICE" in gate["primary_blocker"]
    assert "yfinance 1m" in gate["primary_blocker"]


def test_smart_alert_accepts_live_price_contract_for_ready_exchange_setup():
    row = {
        "market": "crypto",
        "symbol": "BTC/USD",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 88,
        "trend_score": 82,
        "trigger_score": 78,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.25,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "live_price_contract": {
            "gate": "LIVE_PRICE_OK",
            "operable": True,
            "source_label": "BinanceUS ticker",
            "candle_phase_label": "LIVE",
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is True
    assert gate["gate"] == "ALERT_READY"
    assert any(
        item["rule"] == "Grafica operable" and item["passed"] and "BinanceUS ticker" in item["detail"]
        for item in gate["checks"]
    )


def test_smart_alert_blocks_missing_volume():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_VOLUME"
    assert gate["quality"] == "B"
    assert gate["primary_blocker"].startswith("Volumen acompana")
    assert gate["movement"].startswith("Esperar volumen")
    assert any("Volumen acompana" in item for item in gate["blockers"])


def test_smart_alert_blocks_stock_when_provider_premium_is_blocked():
    row = {
        "market": "stock",
        "symbol": "AAPL",
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
        "realtime_health": {
            "label": "Premium bloqueado",
            "detail": "chart_provider_effective: alpaca_auth",
            "alerts_allowed": True,
            "stock_alerts_allowed": False,
            "crypto_alerts_allowed": True,
            "premium_recovery_action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "BLOCKED_REALTIME_DATA"
    assert "POLYGON_API_KEY" in gate["movement"]
    assert any("Premium bloqueado" in item for item in gate["blockers"])


def test_smart_alert_prioritizes_realtime_block_over_waiting_15m_entry():
    row = {
        "market": "stock",
        "symbol": "WMT",
        "signal": "WAIT",
        "trade_decision": "WAIT",
        "confluence_score": 82,
        "trend_score": 78,
        "trigger_score": 40,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "realtime_health": {
            "label": "Premium bloqueado",
            "detail": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
            "alerts_allowed": True,
            "stock_alerts_allowed": False,
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["gate"] == "BLOCKED_REALTIME_DATA"
    assert gate["primary_blocker"].startswith("Datos realtime")
    assert "POLYGON_API_KEY" in gate["primary_blocker"]


def test_smart_alert_blocks_no_negotiable_full_candle_or_bollinger_exposure():
    row = {
        "market": "stock",
        "symbol": "AAPL",
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
        "open": 100,
        "high": 111,
        "low": 99,
        "close": 110,
        "entry": 110,
        "bb_upper": 108,
        "bb_lower": 95,
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_FULL_CHECKLIST"
    assert gate["quality"] == "C"
    assert any("No negociable: No expuesto Bollinger" in item for item in gate["blockers"])
    assert any("No negociable: No vela llena" in item for item in gate["blockers"])
    assert "entrada limpia" in gate["movement"]


def test_smart_alert_blocks_micro_timeframe_without_parent_confirmation():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "timeframe": "1m",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_2PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "trigger_score": 72,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.02,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "higher_tf_bias": "NO_DATA",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert any("1m/5m solo timing" in item for item in gate["blockers"])
    assert any(item["rule"] == "1m/5m solo timing" and not item["passed"] for item in gate["checks"])


def test_smart_alert_blocks_bad_reward_risk():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_2PCT",
        "confluence_score": 86,
        "trend_score": 80,
        "trigger_score": 74,
        "risk_pct": 0.03,
        "recommended_target_pct": 0.02,
        "relative_volume_15m": 1.3,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_REWARD_RISK"
    assert gate["primary_blocker"].startswith("Reward/Risk viable")
    assert any(item["rule"] == "Reward/Risk viable" and item["detail"] == "0.67R" for item in gate["checks"])


def test_smart_alert_blocks_fed_event_without_strong_confirmation():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 80,
        "trigger_score": 74,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "higher_tf_bias": "CONFIRMED",
        "news_event": "FOMC statement and Powell press conference",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_MACRO_CONFIRMATION"
    assert gate["primary_blocker"].startswith("Evento FED/macro")
    assert any(item["rule"] == "Evento FED/macro" and not item["passed"] for item in gate["checks"])


def test_smart_alert_blocks_bad_memory():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
    }
    memory = {"strategy_stats": {"Pullback": {"alerts": 4, "hit_2pct": 0, "stops": 3}}}

    gate = evaluate_smart_alert(row, memory)

    assert gate["notification_ok"] is False
    assert gate["quality"] == "C"
    assert any("Filtro memoria" in item for item in gate["blockers"])


def test_smart_alert_blocks_higher_timeframe_contradiction():
    row = {
        "market": "stock",
        "symbol": "AAPL",
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
        "higher_tf_bias": "BLOCKED",
        "higher_tf_confirmations": 1,
        "higher_tf_blocks": 1,
        "htf_2h_signal": "BUY",
        "htf_4h_signal": "AVOID",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_HTF_CONFIRM"
    assert gate["quality"] == "B"
    assert any("2h/4h validan" in item for item in gate["blockers"])
    assert "2h/4h" in gate["movement"]


def test_smart_alert_blocks_explicit_missing_higher_timeframe_context():
    row = {
        "market": "stock",
        "symbol": "AAPL",
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
        "higher_tf_bias": "NO_DATA",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_HTF_CONFIRM"
    assert gate["primary_blocker"].startswith("2h/4h validan")


def test_smart_alert_blocks_when_source_freshness_disallows_alerts():
    row = {
        "market": "stock",
        "symbol": "AAPL",
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
        "source_freshness": {
            "status": "STALE",
            "label": "Estancados",
            "detail": "live/confluencia llevan 45 min sin refrescar.",
            "alerts_allowed": False,
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "BLOCKED_REALTIME_DATA"
    assert gate["primary_blocker"].startswith("Datos realtime")
    assert gate["quality"] == "C"


def test_smart_alert_blocks_when_realtime_health_disallows_alerts():
    row = {
        "market": "stock",
        "symbol": "AAPL",
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
        "realtime_health": {
            "status": "FAIL",
            "label": "Health fallo",
            "detail": "heartbeat failed",
            "alerts_allowed": False,
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "BLOCKED_REALTIME_DATA"
    assert "heartbeat failed" in gate["primary_blocker"]


def test_smart_alert_uses_shadow_memory_before_real_alert_sample():
    row = {
        "market": "stock",
        "symbol": "AAPL",
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
    memory = {
        "strategy_stats": {
            "Pullback": {
                "alerts": 0,
                "shadow_observed": 4,
                "shadow_near_2pct": 1,
                "shadow_hit_2pct": 0,
                "shadow_near_stop": 3,
            }
        }
    }

    gate = evaluate_smart_alert(row, memory)

    assert gate["notification_ok"] is False
    assert gate["quality"] == "C"
    assert gate["gate"] == "WAIT_FULL_CHECKLIST"
    assert any("shadow stop" in item for item in gate["blockers"])
