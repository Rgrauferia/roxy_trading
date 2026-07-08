from pathlib import Path
import json

from roxy_trader.strike_options_strategy import (
    SIGNAL_NO,
    SIGNAL_NO_TRADE,
    SIGNAL_YES,
    analyze_strike_option,
    build_strike_dashboard_model,
    build_strike_learning_report,
    compare_deriv_strike_contracts,
    format_roxy_strike_response,
    is_strike_signal_expired,
    log_strike_signal,
    score_signal_result,
    settle_expired_strike_signal_history,
    settle_expired_strike_signal_rows,
    settle_strike_signal_history,
    settle_strike_signal_rows,
    strike_signal_expiration_time,
    normalize_strike_timeframe,
    strike_timeframe_profile,
    summarize_strike_signal_history,
)


def _candles(start=60000.0, step=12.0, count=40, volume_start=1000):
    rows = []
    price = start
    for index in range(count):
        open_price = price
        close = price + step
        high = max(open_price, close) + abs(step) * 0.45
        low = min(open_price, close) - abs(step) * 0.25
        rows.append(
            {
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume_start + index * 20,
            }
        )
        price = close
    return rows


def test_bullish_momentum_returns_yes_signal():
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60480,
        strike=60390,
        time_remaining_seconds=540,
        expiration_label="9 min",
        yes_cost=0.42,
        no_cost=0.58,
        payout=1.0,
        candles=_candles(step=13.0),
    )

    assert signal.signal == SIGNAL_YES
    assert signal.color == "green"
    assert signal.confidence >= 70
    assert signal.deriv_contract["direction"] == "YES"
    assert signal.max_recommended_amount > 0


def test_timeframe_profile_normalization_and_thresholds():
    assert normalize_strike_timeframe("20 minutos") == "20m"
    assert normalize_strike_timeframe("2 horas") == "2h"
    assert normalize_strike_timeframe("Daily") == "daily"

    profile = strike_timeframe_profile("2H")
    assert profile.key == "2h"
    assert profile.min_confidence > strike_timeframe_profile("20m").min_confidence
    assert profile.min_edge > strike_timeframe_profile("20m").min_edge


def test_signal_includes_operational_state_checklist_and_score_breakdown():
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60480,
        strike=60390,
        time_remaining_seconds=540,
        expiration_label="9 min",
        yes_cost=0.42,
        no_cost=0.58,
        payout=1.0,
        candles=_candles(step=13.0),
    )

    assert signal.decision_state == "OPERAR AHORA"
    assert signal.data_quality == "live_ready"
    assert signal.market_regime == "tendencia_alcista"
    assert "Ventana rapida" in signal.entry_window
    assert signal.score_breakdown["yes_score"] > signal.score_breakdown["no_score"]
    assert signal.score_breakdown["blockers"] == []
    checklist = {item["id"]: item for item in signal.checklist}
    assert checklist["ema"]["status"] == "pass"
    assert checklist["timer"]["status"] == "pass"
    assert checklist["edge"]["status"] == "pass"
    assert signal.score_breakdown["timeframe_profile"] == "20m"
    assert signal.deriv_contract["profile_label"] == "20 minutos"
    assert "Strike Options" in signal.deriv_contract["contract_instruction"]


def test_2h_profile_blocks_when_timer_is_too_short():
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60480,
        strike=60390,
        time_remaining_seconds=120,
        expiration_label="2 horas",
        timeframe_profile="2h",
        yes_cost=0.42,
        no_cost=0.58,
        payout=1.0,
        candles=_candles(step=13.0),
    )

    assert signal.signal == SIGNAL_NO_TRADE
    assert signal.score_breakdown["timeframe_profile"] == "2h"
    assert any("2 horas" in flag for flag in signal.warning_flags)


def test_daily_profile_adds_macro_contract_instructions():
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60480,
        strike=60390,
        time_remaining_seconds=3600,
        expiration_label="daily",
        timeframe_profile="daily",
        yes_cost=0.42,
        no_cost=0.58,
        payout=1.0,
        candles=_candles(step=13.0, count=80),
    )

    assert signal.score_breakdown["timeframe_profile"] == "daily"
    assert signal.deriv_contract["profile_label"] == "daily"
    assert "periodo daily" in signal.deriv_contract["contract_instruction"]


def test_bearish_momentum_returns_no_signal():
    signal = analyze_strike_option(
        asset="BTC",
        current_price=59620,
        strike=59730,
        time_remaining_seconds=600,
        expiration_label="10 min",
        yes_cost=0.55,
        no_cost=0.45,
        payout=1.0,
        candles=_candles(start=60100, step=-12.0),
    )

    assert signal.signal == SIGNAL_NO
    assert signal.confidence >= 65
    assert signal.deriv_contract["direction"] == "NO"
    assert "debajo" in " ".join(signal.reasons)


def test_too_close_and_short_time_returns_no_trade():
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60000.0,
        strike=60003.0,
        time_remaining_seconds=35,
        yes_cost=0.50,
        no_cost=0.50,
        payout=1.0,
        candles=_candles(step=0.5),
    )

    assert signal.signal == SIGNAL_NO_TRADE
    assert signal.max_recommended_amount == 0
    assert any("tiempo" in flag or "Strike" in flag for flag in signal.warning_flags)


def test_lateral_market_returns_no_trade_with_regime_warning():
    flat_candles = _candles(start=60000, step=0.0, count=30)
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60000.0,
        strike=60080.0,
        time_remaining_seconds=540,
        yes_cost=0.50,
        no_cost=0.50,
        payout=1.0,
        candles=flat_candles,
    )

    assert signal.signal == SIGNAL_NO_TRADE
    assert signal.market_regime in {"lateral_mixto", "sin_confirmacion"}
    assert signal.decision_state in {"ESPERAR CONFIRMACION", "NO OPERAR"}
    assert any("lateral" in flag for flag in signal.warning_flags)
    assert signal.score_breakdown["blockers"]


def test_bad_edge_blocks_trade_even_with_direction():
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60480,
        strike=60390,
        time_remaining_seconds=540,
        yes_cost=0.92,
        no_cost=0.08,
        payout=1.0,
        candles=_candles(step=13.0),
    )

    assert signal.signal == SIGNAL_NO_TRADE
    assert any("edge" in flag for flag in signal.warning_flags)


def test_format_and_log_signal(tmp_path: Path):
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60480,
        strike=60390,
        time_remaining_seconds=540,
        yes_cost=0.42,
        no_cost=0.58,
        payout=1.0,
        candles=_candles(step=13.0),
    )

    text = format_roxy_strike_response(signal)
    assert "Activo: BTC" in text
    assert "Senal:" in text

    log_path = log_strike_signal(signal, tmp_path / "signals.jsonl")
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["asset"] == "BTC"
    assert rows[0]["strike"] == 60390
    assert "confidence" in rows[0]


def test_score_signal_result_marks_yes_win():
    signal = analyze_strike_option(
        asset="BTC",
        current_price=60480,
        strike=60390,
        time_remaining_seconds=540,
        yes_cost=0.42,
        no_cost=0.58,
        payout=1.0,
        candles=_candles(step=13.0),
    )

    result = score_signal_result(signal, final_price=60420, payout=1.0)
    assert result["result"] == "WIN"
    assert result["was_correct"] is True
    assert result["profit_loss"] > 0
    assert result["final_distance_pct"] > 0
    assert result["settled_at"]


def test_settle_strike_signal_rows_closes_pending_rows():
    rows = [
        {"asset": "BTC", "signal": SIGNAL_YES, "strike": 60000, "max_loss": 0.40},
        {"asset": "ETH", "signal": SIGNAL_NO, "strike": 1600, "max_loss": 0.35},
        {"asset": "SOL", "signal": SIGNAL_NO_TRADE, "strike": 70, "result": None},
    ]

    result = settle_strike_signal_rows(
        rows,
        {"BTC": 60125, "ETH": 1590},
        payout_by_asset={"BTC": 1.0, "ETH": 1.0},
        settled_at="2026-07-06T12:00:00+00:00",
    )

    assert result["settled"] == 2
    assert result["rows"][0]["result"] == "WIN"
    assert result["rows"][1]["result"] == "WIN"
    assert result["rows"][2]["result"] == "NO_TRADE"
    assert result["summary"]["closed"] == 2
    assert result["summary"]["win_rate"] == 1.0


def test_settle_strike_signal_history_writes_updated_jsonl(tmp_path: Path):
    path = tmp_path / "signals.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"asset": "BTC", "signal": SIGNAL_YES, "strike": 60000, "max_loss": 0.40}),
                json.dumps({"asset": "ETH", "signal": SIGNAL_NO, "strike": 1600, "max_loss": 0.35}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = settle_strike_signal_history(
        path,
        {"BTC": 59950, "ETH": 1610},
        output_path=tmp_path / "settled.jsonl",
        payout_by_asset={"BTC": 1.0, "ETH": 1.0},
    )

    rows = [json.loads(line) for line in Path(result["path"]).read_text(encoding="utf-8").splitlines()]
    assert result["settled"] == 2
    assert rows[0]["result"] == "LOSS"
    assert rows[1]["result"] == "LOSS"
    assert result["summary"]["profit_loss"] == -0.75


def test_settle_strike_signal_history_creates_backup_when_overwriting(tmp_path: Path):
    path = tmp_path / "signals.jsonl"
    original = json.dumps({"asset": "BTC", "signal": SIGNAL_YES, "strike": 60000, "max_loss": 0.40}) + "\n"
    path.write_text(original, encoding="utf-8")

    result = settle_strike_signal_history(path, {"BTC": 60100}, payout_by_asset={"BTC": 1.0})

    backup_path = Path(result["backup_path"])
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == original
    assert json.loads(path.read_text(encoding="utf-8"))["result"] == "WIN"


def test_strike_signal_expiration_detection():
    row = {
        "timestamp": "2026-07-06T12:00:00+00:00",
        "time_remaining_seconds": 120,
    }

    assert strike_signal_expiration_time(row).isoformat() == "2026-07-06T12:02:00+00:00"
    assert is_strike_signal_expired(row, now="2026-07-06T12:01:59+00:00") is False
    assert is_strike_signal_expired(row, now="2026-07-06T12:02:00+00:00") is True
    assert is_strike_signal_expired(row, now="2026-07-06T12:02:10+00:00", grace_seconds=15) is False


def test_settle_expired_strike_signal_rows_keeps_active_rows_pending():
    rows = [
        {
            "asset": "BTC",
            "signal": SIGNAL_YES,
            "strike": 60000,
            "max_loss": 0.40,
            "timestamp": "2026-07-06T12:00:00+00:00",
            "time_remaining_seconds": 60,
        },
        {
            "asset": "ETH",
            "signal": SIGNAL_NO,
            "strike": 1600,
            "max_loss": 0.35,
            "timestamp": "2026-07-06T12:05:00+00:00",
            "time_remaining_seconds": 600,
        },
    ]

    result = settle_expired_strike_signal_rows(
        rows,
        {"BTC": 60100, "ETH": 1590},
        payout_by_asset={"BTC": 1.0, "ETH": 1.0},
        now="2026-07-06T12:02:00+00:00",
    )

    assert result["settled"] == 1
    assert result["pending"] == 1
    assert result["rows"][0]["result"] == "WIN"
    assert result["rows"][1].get("result") is None


def test_settle_expired_strike_signal_history_writes_only_expired_rows(tmp_path: Path):
    path = tmp_path / "signals.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "asset": "BTC",
                        "signal": SIGNAL_YES,
                        "strike": 60000,
                        "max_loss": 0.40,
                        "timestamp": "2026-07-06T12:00:00+00:00",
                        "time_remaining_seconds": 60,
                    }
                ),
                json.dumps(
                    {
                        "asset": "ETH",
                        "signal": SIGNAL_NO,
                        "strike": 1600,
                        "max_loss": 0.35,
                        "timestamp": "2026-07-06T12:05:00+00:00",
                        "time_remaining_seconds": 600,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = settle_expired_strike_signal_history(
        path,
        {"BTC": 60100, "ETH": 1590},
        output_path=tmp_path / "settled.jsonl",
        payout_by_asset={"BTC": 1.0, "ETH": 1.0},
        now="2026-07-06T12:02:00+00:00",
    )

    rows = [json.loads(line) for line in Path(result["path"]).read_text(encoding="utf-8").splitlines()]
    assert result["settled"] == 1
    assert result["pending"] == 1
    assert rows[0]["result"] == "WIN"
    assert rows[1].get("result") is None


def test_summarize_strike_signal_history_groups_results():
    rows = [
        {
            "signal": SIGNAL_YES,
            "expiration": "20 minutos",
            "result": "WIN",
            "profit_loss": 0.8,
            "confidence": 82,
            "edge": 0.12,
            "condition_key": "YES|ema_bull|rsi_bull|vol_rising",
        },
        {
            "signal": SIGNAL_NO,
            "expiration": "20 minutos",
            "result": "LOSS",
            "profit_loss": -0.5,
            "confidence": 68,
            "edge": 0.03,
            "condition_key": "NO|ema_bear|rsi_bear|vol_flat",
        },
        {"signal": SIGNAL_NO_TRADE, "expiration": "20 minutos", "result": "NO_TRADE", "profit_loss": 0},
        {
            "signal": SIGNAL_YES,
            "expiration": "2 horas",
            "result": "WIN",
            "profit_loss": 1.0,
            "confidence": 78,
            "edge": 0.08,
            "condition_key": "YES|ema_bull|rsi_bull|vol_rising",
        },
    ]

    summary = summarize_strike_signal_history(rows)

    assert summary["signals"] == 3
    assert summary["closed"] == 3
    assert summary["no_trade"] == 1
    assert summary["wins"] == 2
    assert summary["win_rate"] == 0.6667
    assert summary["expectancy"] == 0.4333
    assert summary["average_confidence"] == 76
    assert summary["average_edge"] == 0.0767
    assert summary["recent_20"]["signals"] == 3
    assert summary["recent_20"]["win_rate"] == 0.6667
    assert summary["by_expiration"]["20 minutos"]["signals"] == 2
    assert summary["by_signal"][SIGNAL_YES]["win_rate"] == 1.0
    assert summary["best_signal"] == SIGNAL_YES
    assert summary["best_condition"] == "YES|ema_bull|rsi_bull|vol_rising"


def test_build_strike_learning_report_returns_policy_and_recommendations():
    rows = [
        {
            "signal": SIGNAL_YES,
            "expiration": "20 minutos",
            "result": "WIN",
            "profit_loss": 0.7,
            "confidence": 84,
            "edge": 0.12,
            "condition_key": "YES|ema_bull|rsi_bull|vol_rising",
        },
        {
            "signal": SIGNAL_YES,
            "expiration": "20 minutos",
            "result": "LOSS",
            "profit_loss": -0.4,
            "confidence": 66,
            "edge": 0.02,
            "condition_key": "YES|ema_flat|rsi_hot|vol_falling",
        },
        {
            "signal": SIGNAL_NO_TRADE,
            "expiration": "20 minutos",
            "result": "NO_TRADE",
            "profit_loss": 0.0,
        },
    ]

    report = build_strike_learning_report(rows)

    assert report["closed_signals"] == 2
    assert report["summary"]["win_rate"] == 0.5
    assert report["strongest_conditions"][0]["key"] == "YES|ema_bull|rsi_bull|vol_rising"
    assert report["operational_policy"]["risk_mode"] == "paper"
    assert any("muestra" in item for item in report["recommendations"])


def test_compare_deriv_contracts_selects_best_yes_contract():
    comparison = compare_deriv_strike_contracts(
        asset="BTC",
        current_price=60480,
        time_remaining_seconds=540,
        expiration_label="9 min",
        candles=_candles(step=13.0),
        target_price=60580,
        contracts=[
            {"strike": 60340, "yes_cost": 0.76, "no_cost": 0.24, "payout": 1.0},
            {"strike": 60390, "yes_cost": 0.32, "no_cost": 0.68, "payout": 1.0},
            {"strike": 60680, "yes_cost": 0.50, "no_cost": 0.50, "payout": 1.0},
        ],
    )

    assert comparison.status == "ready"
    assert comparison.signal == SIGNAL_YES
    assert comparison.best_contract is not None
    assert comparison.best_contract["strike"] == 60390
    assert comparison.best_contract["rank"] == 1
    assert len(comparison.contracts_ranked) == 3
    assert comparison.data_quality == "live_costs"


def test_compare_deriv_contracts_passes_timeframe_profile_to_ranked_signals():
    comparison = compare_deriv_strike_contracts(
        asset="BTC",
        current_price=60480,
        time_remaining_seconds=7200,
        expiration_label="2 horas",
        timeframe_profile="2h",
        candles=_candles(step=13.0, count=80),
        target_price=60580,
        contracts=[
            {"strike": 60390, "yes_cost": 0.32, "no_cost": 0.68, "payout": 1.0},
            {"strike": 60680, "yes_cost": 0.50, "no_cost": 0.50, "payout": 1.0},
        ],
    )

    assert comparison.contracts_ranked
    assert comparison.contracts_ranked[0]["score_breakdown"]["timeframe_profile"] == "2h"
    assert comparison.contracts_ranked[0]["profile_label"] == "2 horas"


def test_compare_deriv_contracts_selects_best_no_contract():
    comparison = compare_deriv_strike_contracts(
        asset="BTC",
        current_price=59620,
        time_remaining_seconds=600,
        expiration_label="10 min",
        candles=_candles(start=60100, step=-12.0),
        target_price=59540,
        contracts=[
            {"strike": 59450, "yes_cost": 0.30, "no_cost": 0.70, "payout": 1.0},
            {"strike": 59730, "yes_cost": 0.62, "no_cost": 0.38, "payout": 1.0},
            {"strike": 59950, "yes_cost": 0.88, "no_cost": 0.12, "payout": 1.0},
        ],
    )

    assert comparison.status == "ready"
    assert comparison.signal == SIGNAL_NO
    assert comparison.best_contract is not None
    assert comparison.best_contract["strike"] == 59730
    assert comparison.best_contract["roxy_signal"]["deriv_contract"]["direction"] == SIGNAL_NO


def test_compare_deriv_contracts_blocks_when_costs_are_missing():
    comparison = compare_deriv_strike_contracts(
        asset="BTC",
        current_price=60480,
        time_remaining_seconds=540,
        expiration_label="9 min",
        candles=_candles(step=13.0),
        contracts=[
            {"strike": 60390},
            {"strike": 60680},
        ],
    )

    assert comparison.status == "blocked"
    assert comparison.signal == SIGNAL_NO_TRADE
    assert comparison.data_quality == "missing_costs_estimated"
    assert "costos" in comparison.reason


def test_build_strike_dashboard_model_uses_best_contract_and_history():
    comparison = compare_deriv_strike_contracts(
        asset="BTC",
        current_price=60480,
        time_remaining_seconds=540,
        expiration_label="9 min",
        candles=_candles(step=13.0),
        target_price=60580,
        contracts=[
            {"strike": 60390, "yes_cost": 0.32, "no_cost": 0.68, "payout": 1.0},
            {"strike": 60680, "yes_cost": 0.50, "no_cost": 0.50, "payout": 1.0},
        ],
    )
    history = [
        {"signal": SIGNAL_YES, "expiration": "9 min", "result": "WIN", "profit_loss": 0.68},
        {"signal": SIGNAL_NO, "expiration": "20 min", "result": "LOSS", "profit_loss": -0.4},
    ]

    model = build_strike_dashboard_model(comparison=comparison, history=history)

    assert model["signal"] == SIGNAL_YES
    assert model["decision"] == "OPERAR AHORA"
    assert model["deriv_plan"]["strike"] == 60390
    assert model["deriv_plan"]["contracts_compared"] == 2
    assert model["win_rate"] == 0.5
    assert model["best_timeframe"] == "9 min"
    assert "EMA9" in model["best_condition"]
    assert model["market_regime"] == "tendencia_alcista"
    assert model["data_quality"] == "live_ready"
    assert model["checklist"]
    assert model["score_breakdown"]["yes_score"] > model["score_breakdown"]["no_score"]
    assert model["best_signal"] == SIGNAL_YES
    assert model["expectancy"] == 0.14


def test_build_strike_dashboard_model_downgrades_weak_historical_family():
    comparison = compare_deriv_strike_contracts(
        asset="BTC",
        current_price=60480,
        time_remaining_seconds=540,
        expiration_label="9 min",
        candles=_candles(step=13.0),
        target_price=60580,
        contracts=[
            {"strike": 60390, "yes_cost": 0.32, "no_cost": 0.68, "payout": 1.0},
            {"strike": 60680, "yes_cost": 0.50, "no_cost": 0.50, "payout": 1.0},
        ],
    )
    history = [
        {"signal": SIGNAL_YES, "expiration": "9 min", "result": "LOSS", "profit_loss": -0.32}
        for _ in range(8)
    ]

    model = build_strike_dashboard_model(comparison=comparison, history=history)

    assert model["signal"] == SIGNAL_YES
    assert model["decision"] == "ESPERAR CONFIRMACION"
    assert model["color"] == "yellow"
    assert model["history_fit"]["verdict"] == "debil"
    assert any("Memoria operativa debil" in item for item in model["warning_flags"])


def test_build_strike_dashboard_model_downgrades_weak_recent_memory():
    comparison = compare_deriv_strike_contracts(
        asset="BTC",
        current_price=60480,
        time_remaining_seconds=540,
        expiration_label="9 min",
        candles=_candles(step=13.0),
        target_price=60580,
        contracts=[
            {"strike": 60390, "yes_cost": 0.32, "no_cost": 0.68, "payout": 1.0},
            {"strike": 60680, "yes_cost": 0.50, "no_cost": 0.50, "payout": 1.0},
        ],
    )
    history = [
        {
            "signal": SIGNAL_NO,
            "expiration": "2 horas",
            "result": "LOSS",
            "profit_loss": -0.35,
            "settled_at": f"2026-07-06T12:{minute:02d}:00+00:00",
        }
        for minute in range(8)
    ]

    model = build_strike_dashboard_model(comparison=comparison, history=history)

    assert model["signal"] == SIGNAL_YES
    assert model["decision"] == "ESPERAR CONFIRMACION"
    assert model["recent_performance"]["verdict"] == "debil"
    assert any("Memoria reciente debil" in item for item in model["warning_flags"])
