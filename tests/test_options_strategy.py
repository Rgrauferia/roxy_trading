from datetime import date

import pandas as pd

from options_strategy import (
    OptionSelectionConfig,
    analyze_option_contract,
    best_option_contract,
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


def test_analyze_option_contract_requires_professional_call_quality():
    row = {
        "symbol": "AAPL",
        "contractSymbol": "AAPL260220C00101000",
        "option_type": "call",
        "option_decision": "OPTION_CANDIDATE",
        "option_score": 88,
        "dte": 20,
        "strike": 101,
        "bid": 1.15,
        "ask": 1.20,
        "spread_pct": 0.043,
        "volume": 700,
        "openInterest": 2000,
        "underlying_price": 100,
        "target_pct": 0.05,
        "breakeven_price": 102.20,
        "breakeven_pct": 0.022,
        "max_loss_per_contract": 120,
        "delta": 0.48,
        "gamma": 0.03,
        "theta": -0.04,
        "vega": 0.12,
        "greek_quality": "FULL_GREEKS",
    }

    brief = analyze_option_contract(row, account_equity=20000, risk_pct=0.01)

    assert brief["professional_decision"] == "MIRAR_CALL"
    assert brief["human_decision"] == "Mirar Call"
    assert brief["contracts_by_risk"] == 1
    assert brief["risk_budget"] == 200
    assert not brief["blockers"]
    assert "DTE 20" in brief["summary"]
    assert "break-even 102.20" in brief["summary"]
    assert any(item["label"] == "Open interest" and item["passed"] for item in brief["checks"])


def test_best_option_contract_blocks_missing_greeks_and_bad_liquidity():
    options = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "contractSymbol": "AAPL_BAD",
                "option_type": "call",
                "option_decision": "OPTION_CANDIDATE",
                "option_score": 90,
                "dte": 20,
                "strike": 101,
                "bid": 1.0,
                "ask": 1.05,
                "spread_pct": 0.05,
                "volume": 5,
                "openInterest": 10,
                "underlying_price": 100,
                "breakeven_price": 102.05,
                "breakeven_pct": 0.0205,
                "max_loss_per_contract": 105,
            }
        ]
    )

    brief = best_option_contract(options, "AAPL", account_equity=20000, risk_pct=0.01, target_pct=0.05)

    assert brief["professional_decision"] == "NO_OPERAR"
    assert any("Delta" in item for item in brief["blockers"])
    assert any("Volumen" in item for item in brief["blockers"])
    assert any("Open interest" in item for item in brief["blockers"])
