import pandas as pd
from tools import features


def test_compute_indicators_on_synthetic():
    # build synthetic OHLCV
    n = 100
    import numpy as np
    ts = pd.date_range("2020-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.normal(0, 1, n))
    df = pd.DataFrame({"ts": ts, "open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1000})
    out = features.compute_technical_indicators(df)
    # expect some indicator columns
    assert "sma_10" in out.columns
    assert "ema_10" in out.columns
    assert "atr_14" in out.columns
    assert "rsi_14" in out.columns
    assert "vol_10" in out.columns
    assert not out.empty
