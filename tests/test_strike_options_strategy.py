from pathlib import Path
import json

from roxy_trader.strike_options_strategy import (
    SIGNAL_NO,
    SIGNAL_NO_TRADE,
    SIGNAL_YES,
    analyze_strike_option,
    format_roxy_strike_response,
    log_strike_signal,
    score_signal_result,
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
    assert result["profit_loss"] > 0


def test_summarize_strike_signal_history_groups_results():
    rows = [
        {"signal": SIGNAL_YES, "expiration": "20 minutos", "result": "WIN", "profit_loss": 0.8},
        {"signal": SIGNAL_NO, "expiration": "20 minutos", "result": "LOSS", "profit_loss": -0.5},
        {"signal": SIGNAL_NO_TRADE, "expiration": "20 minutos", "result": "NO_TRADE", "profit_loss": 0},
        {"signal": SIGNAL_YES, "expiration": "2 horas", "result": "WIN", "profit_loss": 1.0},
    ]

    summary = summarize_strike_signal_history(rows)

    assert summary["signals"] == 3
    assert summary["closed"] == 3
    assert summary["wins"] == 2
    assert summary["win_rate"] == 0.6667
    assert summary["by_expiration"]["20 minutos"]["signals"] == 2
