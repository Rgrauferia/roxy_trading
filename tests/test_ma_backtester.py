import pandas as pd
import pytest
import ma_backtester
import moving_average_strategy

from ma_backtester import (
    BacktestEligibilityConfig,
    MovingAverageBacktestConfig,
    evaluate_backtest_eligibility,
    run_ma_backtest,
)


def ohlcv_from_closes(closes):
    return pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=len(closes), freq="D"),
            "open": closes,
            "high": [value * 1.01 for value in closes],
            "low": [value * 0.99 for value in closes],
            "close": closes,
            "volume": [1000] * len(closes),
        }
    )


def test_ma_backtest_generates_profitable_trade_in_uptrend():
    df = ohlcv_from_closes([100 + idx * 0.5 for idx in range(320)])

    result = run_ma_backtest(
        df,
        symbol="UP",
        backtest_config=MovingAverageBacktestConfig(starting_capital=10000, position_size_pct=0.5),
    )

    assert result["symbol"] == "UP"
    assert result["trades"] >= 1
    assert result["final_equity"] > 10000
    assert result["total_return_pct"] > 0
    assert "buy_hold_account_return_pct" in result
    assert "buy_hold_edge_pct" in result
    assert result["trades_detail"][0]["entry_price"] < result["trades_detail"][0]["exit_price"]


def test_ma_backtest_avoids_clean_downtrend():
    df = ohlcv_from_closes([260 - idx * 0.5 for idx in range(320)])

    result = run_ma_backtest(df, symbol="DOWN")

    assert result["symbol"] == "DOWN"
    assert result["trades"] == 0
    assert result["final_equity"] == 10000
    assert result["total_return_pct"] == 0


def test_ma_backtest_returns_empty_metrics_with_insufficient_data():
    df = ohlcv_from_closes([100 + idx * 0.5 for idx in range(100)])

    result = run_ma_backtest(df, symbol="SHORT")

    assert result["trades"] == 0
    assert result["equity_curve"] == []
    assert result["engine_version"].startswith("roxy-ma-backtest/")


def test_trailing_stop_from_current_close_only_applies_to_next_candle(monkeypatch):
    frame = ohlcv_from_closes([100.0] * 203)
    frame.loc[201, "low"] = 90.0

    def add_known_averages(df):
        out = df.copy()
        for column in ("sma20", "sma40", "sma100", "sma200"):
            out[column] = 100.0
        return out

    monkeypatch.setattr(ma_backtester, "add_moving_averages", add_known_averages)
    monkeypatch.setattr(
        ma_backtester,
        "analyze_moving_average_setup",
        lambda *_args, **_kwargs: {
            "signal": "BUY",
            "stop": 50.0,
            "score": 80,
            "setup": "TEST",
            "sma100": 100.0,
        },
    )

    result = run_ma_backtest(frame, symbol="NO_LOOKAHEAD")

    assert result["trades"] == 1
    assert result["trades_detail"][0]["exit_reason"] == "END_OF_DATA"
    assert result["trades_detail"][0]["exit_index"] == 202


def test_backtest_eligibility_accepts_strong_metrics():
    metrics = {
        "trades": 12,
        "profit_factor": 1.8,
        "total_return_pct": 0.12,
        "max_drawdown_pct": 0.08,
        "buy_hold_return_pct": 0.05,
        "buy_hold_edge_pct": 0.07,
    }

    result = evaluate_backtest_eligibility(metrics, BacktestEligibilityConfig(min_buy_hold_edge_pct=0.02))

    assert result["eligible"] is True
    assert result["eligibility_reasons"] == []


def test_backtest_eligibility_rejects_weak_metrics():
    metrics = {
        "trades": 3,
        "profit_factor": 0.8,
        "total_return_pct": -0.01,
        "max_drawdown_pct": 0.22,
        "buy_hold_return_pct": 0.05,
    }

    result = evaluate_backtest_eligibility(metrics)

    assert result["eligible"] is False
    assert "trades<8" in result["eligibility_reasons"]
    assert "profit_factor<1.2" in result["eligibility_reasons"]


def test_annualization_matches_market_and_timeframe():
    frame = ohlcv_from_closes([100 + idx * 0.2 for idx in range(320)])

    crypto = run_ma_backtest(frame, symbol="BTC/USD", market="crypto", timeframe="15m")
    stock = run_ma_backtest(frame, symbol="AAPL", market="stock", timeframe="1d")

    assert crypto["annualization_periods"] == 365 * 96
    assert stock["annualization_periods"] == 252
    assert "sortino" in crypto
    assert "annualized_return_pct" in crypto


def test_gap_through_stop_fills_at_open_not_at_stale_stop(monkeypatch):
    frame = ohlcv_from_closes([100.0] * 204)
    frame.loc[202, ["open", "high", "low", "close"]] = [90.0, 92.0, 88.0, 91.0]

    def add_known_averages(df):
        out = df.copy()
        for column in ("sma20", "sma40", "sma100", "sma200"):
            out[column] = 100.0
        return out

    monkeypatch.setattr(ma_backtester, "add_moving_averages", add_known_averages)
    monkeypatch.setattr(
        ma_backtester,
        "analyze_moving_average_setup",
        lambda *_args, **_kwargs: {
            "signal": "BUY",
            "stop": 95.0,
            "score": 80,
            "setup": "TEST",
            "sma100": 100.0,
        },
    )

    result = run_ma_backtest(frame, symbol="GAP")

    assert result["trades"] == 1
    assert result["trades_detail"][0]["exit_reason"] == "STOP_GAP"
    assert result["trades_detail"][0]["exit_price"] == pytest.approx(90.0 * (1.0 - 0.0005))


@pytest.mark.parametrize(
    "config",
    [
        MovingAverageBacktestConfig(starting_capital=0),
        MovingAverageBacktestConfig(position_size_pct=0),
        MovingAverageBacktestConfig(position_size_pct=1.1),
        MovingAverageBacktestConfig(fee_pct=-0.01),
        MovingAverageBacktestConfig(slippage_pct=-0.01),
    ],
)
def test_invalid_execution_assumptions_are_rejected(config):
    with pytest.raises(ValueError):
        run_ma_backtest(ohlcv_from_closes([100.0] * 220), backtest_config=config)


def test_precomputed_indicator_path_is_signal_equivalent_and_does_not_recalculate(monkeypatch):
    frame = ohlcv_from_closes([100 + idx * 0.08 + ((idx % 17) - 8) * 0.15 for idx in range(360)])
    enriched = moving_average_strategy.add_moving_averages(frame)
    expected = moving_average_strategy.analyze_moving_average_setup(frame)

    monkeypatch.setattr(
        moving_average_strategy,
        "add_moving_averages",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected indicator recalculation")),
    )
    actual = moving_average_strategy.analyze_moving_average_setup(
        enriched,
        precomputed_indicators=True,
    )

    assert actual == expected


def test_precomputed_indicator_path_rejects_incomplete_contract():
    with pytest.raises(ValueError, match="Missing precomputed columns"):
        moving_average_strategy.analyze_moving_average_setup(
            ohlcv_from_closes([100.0] * 220),
            precomputed_indicators=True,
        )
