import pandas as pd

from trade_brief import (
    build_symbol_trade_brief,
    risk_sizing,
    summarize_backtest_by_strategy,
    summarize_backtest_performance,
)


def test_build_symbol_trade_brief_recommends_call_when_stock_and_option_confirm():
    setup = {
        "signal": "BUY",
        "setup": "PULLBACK",
        "score": 88,
        "entry": 100,
        "stop": 98,
        "relative_volume": 1.2,
        "backtest_eligible": True,
        "close": 100,
        "sma20": 98,
        "sma40": 95,
        "sma100": 90,
        "sma200": 82,
    }
    confluence = {
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 86,
        "entry": 100,
        "stop": 98,
        "risk_pct": 0.02,
        "relative_volume_15m": 1.1,
        "recommended_target_pct": 0.05,
        "recommended_target_price": 105,
        "backtest_eligible": True,
        "trend_setup": "TREND_CONTINUATION",
    }
    options = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "contractSymbol": "AAPL260117C00100000",
                "option_decision": "OPTION_CANDIDATE",
                "option_score": 82,
                "option_type": "call",
                "expiry": "2026-01-17",
                "dte": 21,
                "strike": 100,
                "bid": 0.85,
                "ask": 0.90,
                "mid": 0.875,
                "spread_pct": 0.0571,
                "volume": 400,
                "openInterest": 1200,
                "delta": 0.45,
                "gamma": 0.03,
                "theta": -0.04,
                "vega": 0.12,
                "underlying_price": 100,
                "breakeven_price": 100.90,
                "breakeven_pct": 0.009,
                "max_loss_per_contract": 90,
            }
        ]
    )

    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="15m",
        setup=setup,
        confluence=confluence,
        options_df=options,
        account_equity=10000,
        account_risk_pct=0.01,
    )

    assert brief["decision"] == "Mirar call"
    assert brief["direct_plan"]["status"] == "Mirar Call"
    assert brief["direct_plan"]["product"] == "Call"
    assert "delta" in brief["direct_plan"]["summary"].lower()
    assert "dte" in brief["direct_plan"]["summary"].lower()
    assert "break-even" in brief["direct_plan"]["summary"].lower()
    assert brief["option"]["professional_decision"] == "MIRAR_CALL"
    assert brief["option"]["contracts_by_risk"] == 1
    assert brief["operation_status"] == "Operar"
    assert {item["label"] for item in brief["condition_checks"]} >= {
        "1h confirma",
        "15m da entrada",
        "Volumen acompana",
        "Riesgo bajo",
        "Target 2% viable",
    }
    assert brief["sizing"]["shares"] == 50
    assert brief["sizing"]["contracts"] == 1
    assert brief["target_ladder"][1]["target_price"] == 105
    assert brief["decision_reason"]["title"] == "Por que mirar CALL"
    assert "riesgo" in brief["decision_reason"]["summary"].lower()
    assert any("SMA20" in item for item in brief["decision_reason"]["bullets"])
    assert brief["decision_transition"]["title"] == "Que invalidaria BUY"
    assert any("stop" in item.lower() for item in brief["decision_transition"]["items"])
    explanation = " ".join(brief["strategy_explanation"])
    assert "Roxy esta leyendo AAPL" in explanation
    assert "SMA20" in explanation


def test_build_symbol_trade_brief_waits_when_confluence_not_confirmed():
    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="1h",
        setup={"signal": "BUY", "setup": "TREND_CONTINUATION", "entry": 100, "stop": 97, "score": 90},
        confluence={"signal": "AVOID", "trade_decision": "NO_TRADE", "backtest_eligible": True},
        options_df=pd.DataFrame(),
    )

    assert brief["decision"] == "Esperar"
    assert brief["direct_plan"]["status"] == "Esperar"
    assert "confluencia" in " ".join(brief["reasons"]).lower()
    assert brief["watch_plan"]["movement"]
    assert brief["reasons"][0].startswith("Movimiento esperado:")
    assert brief["decision_reason"]["title"] == "Por que AVOID"
    assert brief["decision_transition"]["title"] == "Que falta para BUY"
    assert any("15m" in item for item in brief["decision_transition"]["items"])


def test_build_symbol_trade_brief_waits_when_higher_timeframes_block():
    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="15m",
        setup={"signal": "BUY", "setup": "TREND_CONTINUATION", "entry": 100, "stop": 98, "score": 90},
        confluence={
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "confluence_score": 88,
            "entry": 100,
            "stop": 98,
            "risk_pct": 0.02,
            "relative_volume_15m": 1.2,
            "recommended_target_pct": 0.05,
            "backtest_eligible": True,
            "trend_score": 82,
            "trigger_score": 78,
            "higher_tf_bias": "BLOCKED",
            "higher_tf_confirmations": 1,
            "higher_tf_blocks": 1,
            "htf_2h_signal": "BUY",
            "htf_4h_signal": "AVOID",
        },
        options_df=pd.DataFrame(),
    )

    assert brief["decision"] == "Esperar"
    assert brief["operation_status"] == "No operar"
    assert brief["higher_tf_bias"] == "BLOCKED"
    assert any(item["label"] == "2h/4h validan" and not item["passed"] for item in brief["condition_checks"])
    assert any("2h/4h" in blocker for blocker in brief["blockers"])


def test_build_symbol_trade_brief_watch_plan_names_specific_movement():
    setup = {
        "signal": "WATCH",
        "setup": "PULLBACK",
        "entry": 100,
        "close": 100,
        "stop": 97,
        "score": 64,
        "sma20": 101,
        "sma40": 98,
        "sma100": 94,
        "sma200": 88,
        "relative_volume": 0.6,
        "backtest_eligible": False,
    }
    confluence = {
        "signal": "WATCH",
        "trade_decision": "WAIT",
        "confluence_score": 64,
        "entry": 100,
        "stop": 97,
        "risk_pct": 0.03,
        "relative_volume_15m": 0.6,
        "recommended_target_pct": None,
        "backtest_eligible": False,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
    }

    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="15m",
        setup=setup,
        confluence=confluence,
    )

    assert brief["decision"] == "Esperar"
    assert "rebote" in brief["watch_plan"]["movement"].lower()
    assert "SMA20/SMA40" in brief["watch_plan"]["movement"]
    assert any("15m debe dar BUY" in item for item in brief["watch_plan"]["confirmations"])
    assert any("Volumen relativo" in item for item in brief["watch_plan"]["confirmations"])


def test_build_symbol_trade_brief_avoid_explains_blockers():
    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="1h",
        setup={
            "signal": "AVOID",
            "setup": "DOWNTREND",
            "entry": 100,
            "close": 100,
            "stop": 102,
            "score": 20,
            "sma20": 95,
            "sma40": 96,
            "sma100": 98,
            "sma200": 105,
            "relative_volume": 0.5,
            "backtest_eligible": False,
        },
        confluence={
            "signal": "AVOID",
            "trade_decision": "NO_TRADE",
            "confluence_score": 20,
            "entry": 100,
            "stop": 102,
            "risk_pct": None,
            "relative_volume_15m": 0.5,
            "recommended_target_pct": None,
            "backtest_eligible": False,
            "trigger_setup": "DOWNTREND",
            "trend_setup": "DOWNTREND",
        },
    )

    assert brief["decision"] == "No operar"
    assert brief["direct_plan"]["status"] == "No operar"
    assert brief["decision_reason"]["title"] == "Por que AVOID"
    assert "evita" in brief["decision_reason"]["summary"].lower()
    assert any("debajo de SMA200" in item for item in brief["decision_reason"]["bullets"])
    assert brief["decision_transition"]["tone"] == "avoid"


def test_risk_sizing_uses_account_risk():
    sizing = risk_sizing(account_equity=10000, account_risk_pct=0.01, entry=50, stop=48)

    assert sizing["risk_dollars"] == 100
    assert sizing["shares"] == 50
    assert sizing["stock_notional"] == 2500


def test_summarize_backtest_by_strategy_groups_entry_setups():
    trades = pd.DataFrame(
        [
            {"entry_setup": "PULLBACK", "pnl": 100, "return_pct": 0.05},
            {"entry_setup": "PULLBACK", "pnl": -50, "return_pct": -0.02, "exit_reason": "STOP"},
            {"entry_setup": "EARLY_UPTREND", "pnl": 25, "return_pct": 0.10, "exit_reason": "SMA20_BELOW_SMA40"},
        ]
    )

    summary = summarize_backtest_by_strategy(trades)

    families = set(summary["strategy_family"])
    assert "Pullback" in families
    assert "Cruce de medias" in families
    pullback = summary[summary["strategy_family"] == "Pullback"].iloc[0]
    assert pullback["hit_2pct"] == 1
    assert pullback["stops"] == 1


def test_summarize_backtest_performance_reports_serious_metrics_by_timeframe():
    trades = pd.DataFrame(
        [
            {
                "entry_setup": "PULLBACK",
                "timeframe": "15m",
                "symbol": "AAPL",
                "source": "ma_backtest",
                "pnl": 120.0,
                "return_pct": 0.04,
                "risk_dollars": 60.0,
            },
            {
                "entry_setup": "PULLBACK",
                "timeframe": "15m",
                "symbol": "AAPL",
                "source": "ma_backtest",
                "pnl": -60.0,
                "return_pct": -0.02,
                "risk_dollars": 60.0,
                "exit_reason": "STOP",
            },
            {
                "entry_setup": "PULLBACK",
                "timeframe": "1h",
                "symbol": "AAPL",
                "source": "ma_backtest",
                "pnl": 90.0,
                "return_pct": 0.03,
                "risk_dollars": 45.0,
            },
        ]
    )

    summary = summarize_backtest_performance(trades, group_cols=["strategy_family", "timeframe"], starting_equity=10_000)

    by_tf = {row["timeframe"]: row for row in summary.to_dict("records")}
    assert by_tf["15m"]["strategy_family"] == "Pullback"
    assert by_tf["15m"]["trades"] == 2
    assert by_tf["15m"]["win_rate"] == 0.5
    assert by_tf["15m"]["profit_factor"] == 2.0
    assert by_tf["15m"]["max_drawdown"] == 60.0
    assert by_tf["15m"]["avg_r"] == 0.5
    assert by_tf["15m"]["total_r"] == 1.0
    assert by_tf["1h"]["profit_factor"] == float("inf")


def test_summarize_backtest_performance_groups_by_symbol_and_source():
    trades = pd.DataFrame(
        [
            {"entry_setup": "BREAKOUT", "timeframe": "1h", "symbol": "AAPL", "source": "scan_a", "pnl": 50, "r_multiple": 1.0},
            {"entry_setup": "BREAKOUT", "timeframe": "1h", "symbol": "MSFT", "source": "scan_a", "pnl": -25, "r_multiple": -0.5},
            {"entry_setup": "BREAKOUT", "timeframe": "1h", "symbol": "AAPL", "source": "scan_b", "pnl": 25, "r_multiple": 0.5},
        ]
    )

    summary = summarize_backtest_performance(trades, group_cols=["symbol", "source"])

    keys = {(row["symbol"], row["source"]): row for row in summary.to_dict("records")}
    assert keys[("AAPL", "scan_a")]["trades"] == 1
    assert keys[("AAPL", "scan_b")]["avg_r"] == 0.5
    assert keys[("MSFT", "scan_a")]["tone"] == "avoid"


def test_build_symbol_trade_brief_uses_negative_strategy_memory():
    setup = {
        "signal": "BUY",
        "setup": "TREND_CONTINUATION",
        "score": 90,
        "entry": 100,
        "stop": 98,
        "relative_volume": 1.1,
        "backtest_eligible": True,
    }
    confluence = {
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_2PCT",
        "confluence_score": 82,
        "entry": 100,
        "stop": 98,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.02,
        "backtest_eligible": True,
        "trend_setup": "TREND_CONTINUATION",
    }
    memory = {"strategy_stats": {"Canal alcista": {"alerts": 4, "hit_2pct": 0, "stops": 3}}}

    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="1h",
        setup=setup,
        confluence=confluence,
        memory=memory,
    )

    assert brief["decision"] == "Esperar"
    assert brief["memory"]["bias"] == "negative"
    assert "Aprendizaje" in " ".join(brief["strategy_explanation"])


def test_trade_brief_enrichment_does_not_override_core_decision():
    setup = {
        "signal": "BUY",
        "setup": "TREND_CONTINUATION",
        "score": 92,
        "entry": 100,
        "stop": 98,
        "relative_volume": 1.3,
        "backtest_eligible": True,
        "close": 100,
        "open": 99,
        "high": 101,
        "low": 98,
        "sma20": 96,
        "sma40": 94,
        "sma100": 90,
        "sma200": 84,
        "spread_pct": 0.004,
    }
    confluence = {
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 90,
        "entry": 100,
        "stop": 98,
        "risk_pct": 0.02,
        "relative_volume_15m": 1.3,
        "recommended_target_pct": 0.05,
        "recommended_target_price": 105,
        "backtest_eligible": True,
        "trend_setup": "TREND_CONTINUATION",
    }

    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="crypto",
        timeframe="15m",
        setup=setup,
        confluence=confluence,
        memory={"strategy_stats": {"Canal alcista": {"alerts": 4, "hit_2pct": 3, "stops": 0}}},
    )

    assert brief["decision"] == "Comprar accion"
    assert brief["operation_status"] == "Operar"
    assert brief["enrichment"]["mode"] == "enrichment_only"
    assert brief["direct_plan"]["enrichment_summary"]
    assert "enriquecida" in " ".join(brief["reasons"]).lower()
    assert {item["label"] for item in brief["condition_checks"]}.isdisjoint(
        {item["label"] for item in brief["enrichment_checks"]}
    )


def test_trade_brief_enrichment_flags_short_squeeze_context():
    setup = {
        "signal": "WATCH",
        "setup": "PULLBACK",
        "score": 68,
        "entry": 105,
        "stop": 101,
        "close": 105,
        "sma20": 102,
        "sma40": 99,
        "sma100": 93,
        "sma200": 88,
        "relative_volume": 2.4,
        "short_interest_pct": 22,
        "days_to_cover": 4,
        "resistance": 100,
        "backtest_eligible": True,
    }
    confluence = {
        "signal": "WATCH",
        "trade_decision": "WAIT",
        "entry": 105,
        "stop": 101,
        "risk_pct": 0.038,
        "relative_volume_15m": 2.4,
        "recommended_target_pct": 0.05,
        "backtest_eligible": True,
        "trend_setup": "TREND_CONTINUATION",
    }

    brief = build_symbol_trade_brief(
        symbol="PLTR",
        market="stock",
        timeframe="1h",
        setup=setup,
        confluence=confluence,
    )

    layer_titles = {item["title"] for item in brief["enrichment"]["layers"]}
    assert "Momentum / short squeeze" in layer_titles
    assert any(item["label"] == "Momentum squeeze" and item["state"] == "OK" for item in brief["enrichment_checks"])
    assert brief["decision"] == "Esperar"
