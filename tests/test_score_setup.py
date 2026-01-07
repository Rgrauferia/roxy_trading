import numpy as np
import pandas as pd

from roxy_scanner import add_indicators, score_setup


def make_ohlcv(n=300):
    # synthetic increasing price series with volume spikes
    ts = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="H")
    base = np.linspace(1.0, 100.0, n)
    high = base * (1 + np.random.rand(n) * 0.01)
    low = base * (1 - np.random.rand(n) * 0.01)
    open_ = base * (1 + (np.random.rand(n) - 0.5) * 0.005)
    close = base
    volume = np.random.randint(100, 1000, size=n).astype(float)
    df = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
    return df


def test_score_setup_runs_and_returns_keys():
    df = make_ohlcv(300)
    df2 = add_indicators(df).dropna()
    res = score_setup(df2)
    assert isinstance(res, dict)
    for k in ("score", "reasons", "entry", "stop", "tp1", "tp2"):
        assert k in res
    assert isinstance(res["score"], int)
    assert res["entry"] == float(df2.iloc[-1]["close"])
