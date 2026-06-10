import json
from datetime import datetime, timedelta

import pandas as pd

from chart_health import (
    chart_data_quality_status,
    chart_freshness_status,
    chart_health_row,
    summarize_chart_health,
    write_chart_health_report,
)


def test_chart_health_row_requires_fresh_candles_and_indicators():
    now = datetime(2026, 6, 10, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=idx) for idx in range(60, 0, -1)],
            "open": [100 + idx for idx in range(60)],
            "high": [101 + idx for idx in range(60)],
            "low": [99 + idx for idx in range(60)],
            "close": [100.5 + idx for idx in range(60)],
            "volume": [1000 + idx for idx in range(60)],
            "rsi14": [55] * 60,
            "macd_hist": [0.1] * 60,
        }
    )

    row = chart_health_row(symbol="AAPL", market="stock", timeframe="15m", chart_df=chart_df, now=now)

    assert row["status"] == "OK"
    assert row["label"] == "Viva"
    assert row["rows"] == 60
    assert row["has_rsi"] is True
    assert row["has_macd"] is True
    assert row["data_quality_status"] == "OK"
    assert row["valid_ohlc_rows"] == 60


def test_chart_data_quality_status_rejects_missing_ohlc_columns():
    now = datetime(2026, 6, 10, 12, 0)
    chart_df = pd.DataFrame({"ts": [now], "close": [100]})

    status = chart_data_quality_status(chart_df)

    assert status["status"] == "FAIL"
    assert "Faltan columnas" in status["detail"]


def test_chart_data_quality_status_rejects_flat_close_feed():
    now = datetime(2026, 6, 10, 12, 0)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=idx) for idx in range(60, 0, -1)],
            "open": [100] * 60,
            "high": [100] * 60,
            "low": [100] * 60,
            "close": [100] * 60,
            "volume": [1000] * 60,
        }
    )

    status = chart_data_quality_status(chart_df)

    assert status["status"] == "FAIL"
    assert status["flat_close"] is True
    assert "cierre plano" in status["detail"]


def test_chart_data_quality_status_warns_on_duplicate_timestamps():
    now = datetime(2026, 6, 10, 12, 0)
    timestamps = [now - timedelta(minutes=idx) for idx in range(59, 0, -1)] + [now - timedelta(minutes=1)]
    chart_df = pd.DataFrame(
        {
            "ts": timestamps,
            "open": [100 + idx for idx in range(60)],
            "high": [101 + idx for idx in range(60)],
            "low": [99 + idx for idx in range(60)],
            "close": [100.5 + idx for idx in range(60)],
            "volume": [1000] * 60,
        }
    )

    status = chart_data_quality_status(chart_df)

    assert status["status"] == "WARN"
    assert status["duplicate_ts_count"] == 1


def test_chart_freshness_status_marks_stale_chart():
    now = datetime(2026, 6, 10, 12, 0)
    chart_df = pd.DataFrame({"ts": [now - timedelta(hours=4)], "close": [100]})

    status = chart_freshness_status(chart_df, market="crypto", timeframe="15m", now=now)

    assert status["status"] == "FAIL"
    assert status["label"] == "Estancada"


def test_summarize_chart_health_flags_failures_and_top_issue():
    rows = [
        {"symbol": "AAPL", "timeframe": "15m", "status": "OK", "label": "Viva", "indicator_status": "OK", "age_minutes": 4.0},
        {"symbol": "AMD", "timeframe": "1h", "status": "FAIL", "label": "Estancada", "indicator_status": "FAIL", "age_minutes": 92.4},
    ]

    summary = summarize_chart_health(rows)

    assert summary["status"] == "FAIL"
    assert summary["fail_count"] == 1
    assert summary["stale_count"] == 1
    assert summary["missing_indicator_count"] == 1
    assert summary["top_issue"]["symbol"] == "AMD"
    assert summary["max_age_minutes"] == 92.4
    assert summary["avg_age_minutes"] == 48.2
    assert summary["stalest_chart"]["symbol"] == "AMD"


def test_write_chart_health_report_outputs_summary(tmp_path):
    path = tmp_path / "chart_health.json"
    rows = [{"symbol": "AAPL", "status": "OK", "label": "Viva", "indicator_status": "OK"}]

    out = write_chart_health_report(rows, path, generated_at=datetime(2026, 6, 10, 12, 0))

    payload = json.loads(out.read_text())
    assert payload["summary"]["status"] == "OK"
    assert payload["charts"][0]["symbol"] == "AAPL"
