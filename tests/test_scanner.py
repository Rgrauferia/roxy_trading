import pytest

from roxy_scanner import risk_reward


def test_risk_reward_normal():
    # entry=10, stop=8, tp1=12 -> risk=2 reward=2 -> rr=1.0
    assert risk_reward(10, 8, 12) == pytest.approx(1.0)


def test_risk_reward_none_inputs():
    assert risk_reward(None, 8, 12) is None
    assert risk_reward(10, None, 12) is None
    assert risk_reward(10, 8, None) is None


def test_risk_reward_nonpositive_risk():
    # stop above entry -> invalid risk
    assert risk_reward(10, 12, 12) is None
