import pandas as pd

from options_strategy import OptionSelectionConfig
from tools.options_scan import actionable_rows, build_options_candidates, build_summary


def test_actionable_rows_only_uses_stock_buy_trade_plans():
    df = pd.DataFrame(
        [
            {"market": "stock", "symbol": "AAPL", "signal": "BUY", "trade_decision": "TRADE_FOR_5PCT"},
            {"market": "stock", "symbol": "MSFT", "signal": "WATCH", "trade_decision": "WAIT"},
            {"market": "crypto", "symbol": "ETH/USD", "signal": "BUY", "trade_decision": "TRADE_FOR_5PCT"},
        ]
    )

    out = actionable_rows(df)

    assert list(out["symbol"]) == ["AAPL"]


def test_build_options_candidates_adds_underlying_context(monkeypatch):
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "AAPL",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "entry": 100.0,
                "recommended_target_pct": 0.05,
                "confluence_score": 90,
                "stop": 99.0,
                "risk_pct": 0.01,
            }
        ]
    )

    def fake_fetch(symbol, *, underlying_price, target_pct, option_type, config):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "contractSymbol": "AAPL_CALL",
                    "option_decision": "OPTION_CANDIDATE",
                    "option_score": 90,
                    "spread_pct": 0.05,
                }
            ]
        )

    monkeypatch.setattr("tools.options_scan.fetch_scored_option_candidates", fake_fetch)

    out = build_options_candidates(confluence, OptionSelectionConfig())

    assert out.loc[0, "contractSymbol"] == "AAPL_CALL"
    assert out.loc[0, "underlying_trade_decision"] == "TRADE_FOR_5PCT"
    assert out.loc[0, "underlying_confluence_score"] == 90


def test_build_summary_counts_candidates():
    df = pd.DataFrame(
        [
            {"symbol": "AAPL", "option_decision": "OPTION_CANDIDATE", "option_score": 90, "spread_pct": 0.05},
            {"symbol": "AAPL", "option_decision": "REJECT", "option_score": 40, "spread_pct": 0.4},
        ]
    )

    summary = build_summary(df, "source.csv", limit=5)

    assert summary["rows"] == 2
    assert summary["candidate_count"] == 1
    assert summary["symbols"] == ["AAPL"]
