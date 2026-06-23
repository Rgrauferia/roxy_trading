from accuracy_tracker import (
    alert_history_rows,
    build_accuracy_report,
    headline_accuracy,
    real_signal_memory_summary,
    signal_journal_rows,
    strategy_accuracy_rows,
    symbol_accuracy_rows,
    watch_progress_summary,
)


def test_headline_accuracy_needs_data_when_history_is_empty():
    report = headline_accuracy({"alert_history": [], "strategy_stats": {}}, minimum_sample=30)

    assert report["alerts"] == 0
    assert report["measured"] == 0
    assert report["sample_status"] == "NEEDS_DATA"
    assert report["sample_gap"] == 30


def test_strategy_accuracy_classifies_promising_and_risky_setups():
    memory = {
        "strategy_stats": {
            "Pullback": {"seen": 12, "alerts": 5, "hit_2pct": 4, "hit_5pct": 2, "hit_10pct": 1, "stops": 1},
            "Canal lateral": {"seen": 9, "alerts": 4, "hit_2pct": 0, "hit_5pct": 0, "hit_10pct": 0, "stops": 3},
        }
    }

    rows = strategy_accuracy_rows(memory, minimum_alerts=3)
    by_family = {row["strategy_family"]: row for row in rows}

    assert by_family["Pullback"]["status"] == "PROMISING"
    assert by_family["Canal lateral"]["status"] == "RISKY"
    assert by_family["Pullback"]["hit_2_rate"] == 0.8
    assert by_family["Canal lateral"]["stop_rate"] == 0.75


def test_alert_history_rows_detect_targets_and_stop():
    memory = {
        "alert_history": [
            {
                "symbol": "AAPL",
                "entry": 100,
                "stop": 97,
                "status": "HIT_5PCT",
                "milestones": ["2%", "5%"],
                "strategy_family": "Pullback",
                "max_gain_pct": 0.052,
                "max_drawdown_pct": 0.006,
                "progress_to_2pct": 1.0,
                "progress_to_stop": 0.2,
                "stopped_after_target": False,
            },
            {
                "symbol": "MSFT",
                "entry": 200,
                "stop": 194,
                "status": "STOP",
                "trigger_setup": "TREND_CONTINUATION",
            },
        ]
    }

    rows = alert_history_rows(memory)
    by_symbol = {row["symbol"]: row for row in rows}

    assert by_symbol["AAPL"]["status"] == "HIT_5PCT"
    assert by_symbol["AAPL"]["milestones"] == "2%, 5%"
    assert by_symbol["AAPL"]["max_gain_pct"] == 0.052
    assert by_symbol["AAPL"]["progress_to_stop"] == 0.2
    assert by_symbol["AAPL"]["stopped_after_target"] is False
    assert by_symbol["AAPL"]["outcome_state"] == "HIT_5PCT"
    assert by_symbol["MSFT"]["status"] == "STOP"
    assert by_symbol["MSFT"]["strategy_family"] == "Canal alcista"


def test_signal_journal_rows_exposes_best_target_and_reward():
    memory = {
        "signal_journal": [
            {
                "symbol": "AAPL",
                "market": "stock",
                "ai_action": "WATCH",
                "strategy_family": "Pullback",
                "entry": 100,
                "stop": 97,
                "last_price": 101,
                "max_price": 105.5,
                "best_target_hit": "5%",
                "best_target_pct": 5.0,
                "best_reward_r": 1.8333,
                "current_reward_r": 0.3333,
                "outcome_state": "HIT_5PCT",
            }
        ]
    }

    rows = signal_journal_rows(memory)

    assert rows[0]["best_target_hit"] == "5%"
    assert rows[0]["best_target_pct"] == 5.0
    assert rows[0]["best_reward_r"] == 1.8333
    assert rows[0]["outcome_state"] == "HIT_5PCT"


def test_signal_journal_rows_exposes_target_then_stop_state():
    memory = {
        "signal_journal": [
            {
                "symbol": "AAPL",
                "market": "stock",
                "ai_action": "WATCH",
                "strategy_family": "Pullback",
                "entry": 100,
                "stop": 97,
                "last_price": 96.9,
                "max_price": 105.5,
                "min_price": 96.9,
                "best_target_hit": "5%",
                "progress_to_stop": 1.0,
                "stopped_after_target": True,
                "outcome_state": "HIT_5PCT_THEN_STOP",
            }
        ]
    }

    rows = signal_journal_rows(memory)

    assert rows[0]["stopped_after_target"] is True
    assert rows[0]["stopped_before_target"] is False
    assert rows[0]["outcome_state"] == "HIT_5PCT_THEN_STOP"


def test_build_accuracy_report_returns_actions_and_symbol_rows():
    memory = {
        "symbols": {"AAPL": {"seen": 8, "alerts": 1, "best_ai_score": 82, "last_signal": "BUY"}},
        "strategy_stats": {"Pullback": {"seen": 8, "alerts": 1, "hit_2pct": 1, "stops": 0}},
        "alert_history": [
            {
                "symbol": "AAPL",
                "entry": 100,
                "stop": 98,
                "status": "HIT_2PCT",
                "milestones": ["2%"],
                "strategy_family": "Pullback",
                "max_gain_pct": 0.025,
                "progress_to_2pct": 1.0,
            }
        ],
        "signal_journal": [
            {
                "symbol": "AAPL",
                "market": "stock",
                "ai_action": "WATCH",
                "signal": "WATCH",
                "entry": 100,
                "stop": 98,
                "status": "HIT_2PCT",
                "milestones": ["2%"],
                "strategy_family": "Pullback",
                "max_gain_pct": 0.021,
                "progress_to_2pct": 1.0,
            }
        ],
    }

    report = build_accuracy_report(memory, minimum_sample=3, minimum_strategy_alerts=3)
    symbols = symbol_accuracy_rows(memory)
    journal = signal_journal_rows(memory)

    assert report["headline"]["alerts"] == 1
    assert report["headline"]["sample_status"] == "NEEDS_DATA"
    assert any("Collect" in item for item in report["next_actions"])
    assert report["signal_journal_rows"]
    assert symbols[0]["symbol"] == "AAPL"
    assert symbols[0]["hit_2_rate"] == 1.0
    assert journal[0]["ai_action"] == "WATCH"
    assert journal[0]["max_gain_pct"] == 0.021
    assert report["watch_progress"]["tracked"] == 1
    assert report["watch_progress"]["hit_2_count"] == 1


def test_watch_progress_summary_counts_near_target_and_near_stop():
    memory = {
        "signal_journal": [
            {
                "symbol": "AAPL",
                "ai_action": "WATCH",
                "status": "OPEN",
                "progress_to_2pct": 0.80,
                "progress_to_stop": 0.10,
            },
            {
                "symbol": "MSFT",
                "ai_action": "WATCH",
                "status": "OPEN",
                "progress_to_2pct": 0.20,
                "progress_to_stop": 0.90,
            },
            {
                "symbol": "NVDA",
                "ai_action": "WATCH",
                "status": "OPEN",
            },
        ]
    }

    summary = watch_progress_summary(memory)

    assert summary["tracked"] == 3
    assert summary["observed"] == 2
    assert summary["near_2pct_count"] == 1
    assert summary["danger_stop_count"] == 1
    assert summary["avg_progress_to_2pct"] == 0.5
    assert summary["max_progress_to_stop"] == 0.9


def test_real_signal_memory_summary_counts_targets_and_stops_across_sources():
    memory = {
        "alert_history": [
            {
                "symbol": "AAPL",
                "strategy_family": "Pullback",
                "status": "HIT_10PCT",
                "milestones": ["2%", "5%", "10%"],
                "entry": 100,
                "stop": 97,
                "opened_at": "2026-06-01T10:00:00",
            }
        ],
        "signal_journal": [
            {
                "symbol": "MSFT",
                "strategy_family": "Pullback",
                "status": "STOP",
                "entry": 200,
                "stop": 194,
                "opened_at": "2026-06-01T11:00:00",
            }
        ],
    }

    summary = real_signal_memory_summary(memory, strategy_family="Pullback")

    assert summary["alerts"] == 2
    assert summary["measured"] == 2
    assert summary["hit_2pct"] == 1
    assert summary["hit_5pct"] == 1
    assert summary["hit_10pct"] == 1
    assert summary["stops"] == 1
    assert summary["hit_2_rate"] == 0.5
    assert summary["stop_rate"] == 0.5
