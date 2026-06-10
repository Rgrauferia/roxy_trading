import pandas as pd

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
