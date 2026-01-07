import pandas as pd
import pytest

from roxy_scanner import add_trade_meta, signal_from_score, signal_tech_advanced


def test_signal_from_score():
    assert signal_from_score(60, buy=55, watch=30) == "BUY"
    assert signal_from_score(50, buy=55, watch=30) == "WATCH"
    assert signal_from_score(10, buy=55, watch=30) == "AVOID"


def test_signal_tech_advanced_buy_prebuy():
    assert signal_tech_advanced(60, 1.5, buy_score=55, min_rr_buy_tp2=1.1) == "BUY"
    assert signal_tech_advanced(52, 1.2, prebuy_score=50, prebuy_min_rr_tp2=1.1) == "PRE-BUY"
    assert signal_tech_advanced(40, 0.5, buy_score=55, watch_score=30) == "WATCH"


def test_add_trade_meta():
    df = pd.DataFrame(
        [
            {"entry": 10.0, "stop": 8.0, "tp1": 12.0, "tp2": 14.0, "score": 60},
            {"entry": 5.0, "stop": 4.0, "tp1": 6.0, "tp2": 7.0, "score": 20},
        ]
    )
    out = add_trade_meta(df, buy_score=50, watch_score=30)
    assert "rr_tp1" in out.columns
    assert "rr_tp2" in out.columns
    assert "signal" in out.columns
    assert out.loc[0, "signal"] == "BUY"
    assert out.loc[1, "signal"] == "AVOID"
