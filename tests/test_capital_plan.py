from streamlit_app import (
    build_account_risk_guardrail,
    build_million_growth_plan,
    compound_steps_required,
    small_account_product_plan,
)


def test_compound_steps_required_for_500_to_million():
    assert compound_steps_required(500, 1_000_000, 0.02) == 384
    assert compound_steps_required(500, 1_000_000, 0.05) == 156
    assert compound_steps_required(500, 1_000_000, 0.10) == 80


def test_million_growth_plan_uses_small_account_risk_budget():
    plan = build_million_growth_plan(starting_capital=500, target_capital=1_000_000, risk_per_trade_pct=0.01)

    assert plan["multiplier"] == 2000
    assert plan["risk_per_trade"] == 5
    assert plan["daily_stop"] == 10
    assert plan["max_option_debit"] == 5
    assert plan["guardrail"]["status"] == "OK"
    assert plan["steps_to_target"]["5%"] == 156
    assert plan["milestones"][-1]["target"] == 1_000_000
    assert "Opciones" in " ".join(plan["rules"])


def test_account_risk_guardrail_blocks_after_daily_stop():
    guardrail = build_account_risk_guardrail(
        500,
        0.01,
        planned_risk_dollars=5,
        realized_loss_today=10,
    )

    assert guardrail["status"] == "DAILY_STOP"
    assert guardrail["allowed"] is False
    assert guardrail["remaining_daily_risk"] == 0


def test_account_risk_guardrail_reduces_oversized_trade():
    guardrail = build_account_risk_guardrail(
        500,
        0.01,
        planned_risk_dollars=12,
        realized_loss_today=0,
    )

    assert guardrail["status"] == "REDUCE_SIZE"
    assert guardrail["allowed"] is False
    assert guardrail["per_trade_budget"] == 5


def test_small_account_product_plan_blocks_expensive_option():
    plan = small_account_product_plan(
        account_equity=500,
        risk_per_trade_pct=0.01,
        market="stock",
        entry=200,
        stop=196,
        option={"contractSymbol": "AAPL260619C00200000", "max_loss_per_contract": 150},
    )

    assert plan["recommendation"] == "Solo paper"
    assert plan["allowed"] is False
    assert plan["option_allowed"] is False
    assert "supera 1R" in plan["option_message"]


def test_small_account_product_plan_uses_fractional_when_full_share_does_not_fit():
    plan = small_account_product_plan(
        account_equity=500,
        risk_per_trade_pct=0.01,
        market="stock",
        entry=900,
        stop=890,
    )

    assert plan["recommendation"] == "Accion fraccionada"
    assert plan["allowed"] is True
    assert 0 < plan["units"] < 1


def test_small_account_product_plan_allows_small_crypto_size():
    plan = small_account_product_plan(
        account_equity=500,
        risk_per_trade_pct=0.01,
        market="crypto",
        entry=100,
        stop=95,
    )

    assert plan["recommendation"] == "Crypto pequeno"
    assert plan["allowed"] is True
    assert plan["units"] == 1
