from datetime import date

import pandas as pd

from options_strategy import (
    OptionSelectionConfig,
    fetch_tradier_scored_option_candidates,
    professional_options_feed_status,
    score_options_chain,
)


def test_score_options_chain_prefers_liquid_tight_spread_contract():
    chain = pd.DataFrame(
        [
            {
                "contractSymbol": "GOOD",
                "strike": 101,
                "bid": 2.0,
                "ask": 2.1,
                "volume": 500,
                "openInterest": 1500,
                "impliedVolatility": 0.45,
            },
            {
                "contractSymbol": "BAD",
                "strike": 120,
                "bid": 0.5,
                "ask": 1.0,
                "volume": 1,
                "openInterest": 2,
                "impliedVolatility": 2.0,
            },
        ]
    )

    out = score_options_chain(
        chain,
        symbol="AAPL",
        underlying_price=100,
        target_pct=0.05,
        expiry="2026-02-20",
        today=date(2026, 2, 1),
        config=OptionSelectionConfig(),
    )

    assert out.loc[0, "contractSymbol"] == "GOOD"
    assert out.loc[0, "option_decision"] == "OPTION_CANDIDATE"
    assert bool(out.loc[0, "target_reaches_strike"]) is True
    assert out.loc[0, "max_loss_per_contract"] == 210
    assert out.loc[0, "premium"] == 2.1
    assert round(out.loc[0, "spread_dollars"], 2) == 0.1
    assert out.loc[0, "data_source"] == "Yahoo/basic"
    assert 0 < out.loc[0, "delta"] < 1
    assert out.loc[0, "breakeven_price"] == 103.1
    assert out.loc[0, "risk_reward_at_target"] > 0
    assert out.loc[0, "option_score"] > out.loc[1, "option_score"]
    assert out.loc[0, "greek_quality"] == "ESTIMATED_DELTA"


def test_score_options_chain_rejects_wide_spread():
    chain = pd.DataFrame(
        [
            {
                "contractSymbol": "WIDE",
                "strike": 101,
                "bid": 1.0,
                "ask": 1.8,
                "volume": 500,
                "openInterest": 1500,
                "impliedVolatility": 0.45,
            }
        ]
    )

    out = score_options_chain(
        chain,
        symbol="AAPL",
        underlying_price=100,
        target_pct=0.05,
        expiry="2026-02-20",
        today=date(2026, 2, 1),
        config=OptionSelectionConfig(max_spread_pct=0.18),
    )

    assert out.loc[0, "option_decision"] == "REJECT"
    assert out.loc[0, "spread_pct"] > 0.18


def test_score_options_chain_preserves_reported_full_greeks():
    chain = pd.DataFrame(
        [
            {
                "contractSymbol": "FULL",
                "strike": 101,
                "bid": 2.0,
                "ask": 2.1,
                "volume": 500,
                "openInterest": 1500,
                "impliedVolatility": 0.45,
                "delta": 0.48,
                "gamma": 0.03,
                "theta": -0.04,
                "vega": 0.12,
            }
        ]
    )

    out = score_options_chain(
        chain,
        symbol="AAPL",
        underlying_price=100,
        target_pct=0.05,
        expiry="2026-02-20",
        today=date(2026, 2, 1),
        config=OptionSelectionConfig(),
    )

    assert out.loc[0, "delta"] == 0.48
    assert out.loc[0, "gamma"] == 0.03
    assert out.loc[0, "theta"] == -0.04
    assert out.loc[0, "vega"] == 0.12
    assert out.loc[0, "greek_quality"] == "FULL_GREEKS"


def test_professional_options_feed_status_detects_tradier_token():
    status = professional_options_feed_status({"TRADIER_ACCESS_TOKEN": "token"})

    assert status["status"] == "READY"
    assert status["source"] == "Tradier"
    assert "Tradier" in status["configured"]


def test_fetch_tradier_scored_option_candidates_preserves_professional_greeks():
    calls = []

    def fake_get_json(url, params, token, timeout=12):
        calls.append((url, params, token))
        if url.endswith("/markets/options/expirations"):
            return {"expirations": {"date": ["2026-02-20"]}}
        return {
            "options": {
                "option": [
                    {
                        "symbol": "AAPL260220C00101000",
                        "option_type": "call",
                        "expiration_date": "2026-02-20",
                        "strike": 101,
                        "bid": 2.0,
                        "ask": 2.1,
                        "volume": 500,
                        "open_interest": 1500,
                        "greeks": {
                            "delta": 0.48,
                            "gamma": 0.03,
                            "theta": -0.04,
                            "vega": 0.12,
                            "mid_iv": 0.45,
                        },
                    }
                ]
            }
        }

    out = fetch_tradier_scored_option_candidates(
        "AAPL",
        underlying_price=100,
        target_pct=0.05,
        option_type="call",
        token="token",
        base_url="https://api.tradier.test/v1",
        today=date(2026, 2, 1),
        config=OptionSelectionConfig(),
        http_get_json=fake_get_json,
    )

    assert calls[0][2] == "token"
    assert calls[1][1]["greeks"] == "true"
    assert out.loc[0, "contractSymbol"] == "AAPL260220C00101000"
    assert out.loc[0, "data_source"] == "Tradier"
    assert out.loc[0, "greek_quality"] == "FULL_GREEKS"
    assert out.loc[0, "openInterest"] == 1500
    assert out.loc[0, "option_decision"] == "OPTION_CANDIDATE"
