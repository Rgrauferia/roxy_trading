import numpy as np
from tools import modeling


def test_train_baseline_on_synthetic():
    # create synthetic price series trending up
    n = 200
    prices = np.cumprod(1 + 0.001 * np.ones(n)) * 100.0
    import pandas as pd
    df = pd.DataFrame({"ts": pd.date_range("2020-01-01", periods=n), "close": prices})
    df["ret"] = df["close"].pct_change().fillna(0)
    df["sma3"] = df["close"].rolling(3).mean().bfill()
    df["sma10"] = df["close"].rolling(10).mean().bfill()
    df["sma30"] = df["close"].rolling(30).mean().bfill()
    df["momentum"] = df["close"] / df["sma10"] - 1.0

    X, y = modeling.prepare_training_data(df, label_horizon=1)
    assert X.shape[0] == y.shape[0]
    model, metrics = modeling.train_baseline_model(X, y)
    assert metrics.accuracy >= 0.0
