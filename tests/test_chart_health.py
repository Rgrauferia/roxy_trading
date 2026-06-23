import json
from datetime import datetime, timedelta

import pandas as pd

from chart_health import (
    active_chart_symbols_from_alerts,
    active_chart_symbols_from_payloads,
    chart_data_quality_status,
    chart_freshness_status,
    chart_health_row,
    normalize_chart_symbol,
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

    row = chart_health_row(symbol="AAPL", market="stock", timeframe="15m", chart_df=chart_df, now=now, stock_alerts_allowed=True)

    assert row["status"] == "OK"
    assert row["label"] == "Viva"
    assert row["rows"] == 60
    assert row["has_rsi"] is True
    assert row["has_macd"] is True
    assert row["data_quality_status"] == "OK"
    assert row["valid_ohlc_rows"] == 60
    assert row["expected_minutes"] == 15
    assert row["next_expected_update_in_minutes"] == 14.0
    assert row["cadence_lag_minutes"] == 0.0
    assert row["health_lag_minutes"] == 0.0


def test_normalize_chart_symbol_accepts_stocks_and_crypto_pairs():
    assert normalize_chart_symbol("$wmt") == "WMT"
    assert normalize_chart_symbol("btc/usd") == "BTC/USD"
    assert normalize_chart_symbol("-") == ""
    assert normalize_chart_symbol("not a symbol") == ""


def test_active_chart_symbols_from_payloads_prefers_current_opportunities():
    payloads = [
        {
            "top_symbol": "WMT",
            "daily_plan_top_symbol": "MDB",
            "rows": [{"symbol": "AAPL"}, {"symbol": "WMT"}],
        },
        {"opportunities": [{"symbol": "NVDA"}, {"symbol": "BTC/USD"}]},
    ]

    symbols = active_chart_symbols_from_payloads(payloads, limit=4)

    assert symbols == ["WMT", "MDB", "AAPL", "NVDA"]


def test_active_chart_symbols_from_payloads_skips_blocked_realtime_candidates():
    payloads = [
        {
            "opportunities": [
                {"symbol": "WMT", "alert_gate": "BLOCKED_REALTIME_DATA"},
                {"symbol": "KO", "state": "BLOCKED_DATA"},
                {"symbol": "BTC/USD", "alert_gate": "WAIT_15M_ENTRY"},
                {"symbol": "ETH/USD", "gate": "WAIT_15M_ENTRY"},
            ]
        },
        {"top_symbol": "BONK/USD", "top_gate": "Bloqueado por datos realtime"},
        {"rows": [{"symbol": "PEPE/USD", "blocker": "Datos realtime: Health fallo: chart realtime fail"}]},
        {"rows": [{"symbol": "SOL/USD", "gate": "WAIT_15M_ENTRY"}]},
    ]

    symbols = active_chart_symbols_from_payloads(payloads, limit=4)

    assert symbols == ["BTC/USD", "ETH/USD", "SOL/USD"]


def test_active_chart_symbols_from_alerts_reads_status_plan_and_brief(tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "roxy_status.json").write_text(json.dumps({"top_symbol": "WMT"}))
    (alerts / "roxy_daily_opportunity_plan.json").write_text(json.dumps({"rows": [{"symbol": "MDB"}]}))
    (alerts / "roxy_ai_brief.json").write_text(json.dumps({"opportunities": [{"symbol": "AAPL"}]}))

    assert active_chart_symbols_from_alerts(alerts) == ["AAPL", "WMT", "MDB"]


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


def test_chart_health_row_warns_on_flat_close_during_new_candle_grace():
    now = datetime(2026, 6, 10, 12, 3)
    chart_df = pd.DataFrame(
        {
            "ts": [now - timedelta(minutes=3 + 15 * idx) for idx in range(59, -1, -1)],
            "open": [100] * 60,
            "high": [100] * 60,
            "low": [100] * 60,
            "close": [100] * 60,
            "volume": [1000] * 60,
            "rsi14": [55] * 60,
            "macd_hist": [0.1] * 60,
        }
    )

    row = chart_health_row(
        symbol="LINK/USD",
        market="crypto",
        timeframe="15m",
        chart_df=chart_df,
        now=now,
    )

    assert row["status"] == "WARN"
    assert row["data_quality_status"] == "WARN"
    assert row["data_quality_grace"] is True
    assert row["candle_phase"] == "NEW_CANDLE"
    assert "revalidar al cierre" in row["data_quality_detail"]


def test_chart_health_row_fails_flat_close_after_new_candle_grace():
    now = datetime(2026, 6, 10, 12, 5)
    latest = now - timedelta(minutes=5)
    chart_df = pd.DataFrame(
        {
            "ts": [latest - timedelta(minutes=15 * idx) for idx in range(59, -1, -1)],
            "open": [100] * 60,
            "high": [100] * 60,
            "low": [100] * 60,
            "close": [100] * 60,
            "volume": [1000] * 60,
            "rsi14": [55] * 60,
            "macd_hist": [0.1] * 60,
        }
    )

    row = chart_health_row(
        symbol="LINK/USD",
        market="crypto",
        timeframe="15m",
        chart_df=chart_df,
        now=now,
    )

    assert row["status"] == "FAIL"
    assert row["data_quality_status"] == "FAIL"
    assert row["data_quality_grace"] is False
    assert row["candle_phase"] == "IN_PROGRESS"


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
    assert status["cadence_lag_minutes"] == 225.0
    assert status["health_lag_minutes"] > 0
    assert status["candle_phase"] == "STALE"
    assert status["candle_phase_label"] == "Sin pulso"


def test_chart_freshness_status_marks_close_soon_phase():
    now = datetime(2026, 6, 10, 12, 0)
    chart_df = pd.DataFrame({"ts": [now - timedelta(minutes=13)], "close": [100]})

    status = chart_freshness_status(chart_df, market="crypto", timeframe="15m", now=now)

    assert status["status"] == "OK"
    assert status["candle_phase"] == "CLOSE_SOON"
    assert status["candle_phase_label"] == "Cierre cerca"
    assert round(status["candle_progress_pct"], 1) == 86.7


def test_chart_freshness_status_accepts_closed_stock_market_without_lag():
    now = datetime(2026, 6, 10, 20, 30)
    chart_df = pd.DataFrame({"ts": [now - timedelta(minutes=75)], "close": [100]})

    status = chart_freshness_status(
        chart_df,
        market="stock",
        timeframe="15m",
        now=now,
        stock_alerts_allowed=False,
    )

    assert status["status"] == "OK"
    assert status["label"] == "Mercado cerrado"
    assert status["market_closed_accepted"] is True
    assert status["cadence_lag_minutes"] == 0.0
    assert status["health_lag_minutes"] == 0.0


def test_chart_freshness_status_accepts_weekend_stock_market_gap():
    now = datetime(2026, 6, 14, 0, 5)
    chart_df = pd.DataFrame({"ts": [datetime(2026, 6, 12, 16, 0)], "close": [100]})

    status = chart_freshness_status(chart_df, market="stock", timeframe="15m", now=now)

    assert status["status"] == "OK"
    assert status["label"] == "Mercado cerrado"
    assert status["market_closed_accepted"] is True
    assert status["cadence_lag_minutes"] == 0.0
    assert status["health_lag_minutes"] == 0.0


def test_summarize_chart_health_flags_failures_and_top_issue():
    rows = [
        {"symbol": "AAPL", "timeframe": "15m", "status": "OK", "label": "Viva", "indicator_status": "OK", "age_minutes": 4.0},
        {
            "symbol": "AMD",
            "timeframe": "1h",
            "status": "FAIL",
            "label": "Estancada",
            "indicator_status": "FAIL",
            "age_minutes": 92.4,
            "cadence_lag_minutes": 32.4,
            "health_lag_minutes": 0.0,
        },
    ]

    summary = summarize_chart_health(rows)

    assert summary["status"] == "FAIL"
    assert summary["fail_count"] == 1
    assert summary["stale_count"] == 1
    assert summary["missing_indicator_count"] == 1
    assert summary["top_issue"]["symbol"] == "AMD"
    assert summary["max_age_minutes"] == 92.4
    assert summary["avg_age_minutes"] == 48.2
    assert summary["max_cadence_lag_minutes"] == 32.4
    assert summary["max_health_lag_minutes"] == 0.0
    assert summary["stalest_chart"]["symbol"] == "AMD"
    assert summary["most_overdue_chart"]["symbol"] == "AMD"


def test_summarize_chart_health_omits_overdue_chart_when_lag_is_zero():
    rows = [
        {
            "symbol": "AAPL",
            "timeframe": "15m",
            "status": "OK",
            "label": "Viva",
            "indicator_status": "OK",
            "age_minutes": 4.0,
            "cadence_lag_minutes": 0.0,
            "health_lag_minutes": 0.0,
        }
    ]

    summary = summarize_chart_health(rows)

    assert summary["max_cadence_lag_minutes"] == 0.0
    assert summary["most_overdue_chart"] == {}


def test_summarize_chart_health_treats_closed_market_with_healthy_data_as_ok():
    rows = [
        {
            "symbol": "AAPL",
            "timeframe": "15m",
            "market": "stock",
            "status": "OK",
            "label": "Mercado cerrado",
            "indicator_status": "OK",
            "data_quality_status": "OK",
            "age_minutes": 23.0,
            "freshness_budget_minutes": 37.5,
            "cadence_lag_minutes": 8.0,
            "health_lag_minutes": 0.0,
            "market_closed_accepted": True,
        },
        {
            "symbol": "BTC/USD",
            "timeframe": "15m",
            "market": "crypto",
            "status": "OK",
            "label": "Viva",
            "indicator_status": "OK",
            "data_quality_status": "OK",
            "age_minutes": 33.0,
            "freshness_budget_minutes": 37.5,
            "cadence_lag_minutes": 0.0,
            "health_lag_minutes": 0.0,
            "market_closed_accepted": False,
        },
    ]

    summary = summarize_chart_health(rows)

    assert summary["status"] == "OK"
    assert summary["warn_count"] == 0
    assert summary["market_closed_ok_count"] == 1
    assert summary["operable_checked_count"] == 1
    assert summary["max_age_minutes"] == 33.0
    assert summary["operable_max_age_minutes"] == 33.0
    assert summary["operable_stalest_chart"]["symbol"] == "BTC/USD"
    assert summary["min_freshness_margin_minutes"] == 4.5
    assert summary["min_freshness_margin_ratio"] == 0.12
    assert summary["min_freshness_budget_minutes"] == 37.5
    assert summary["min_freshness_margin_chart"]["symbol"] == "BTC/USD"
    assert summary["operable_min_freshness_margin_minutes"] == 4.5
    assert summary["operable_min_freshness_margin_ratio"] == 0.12
    assert summary["operable_min_freshness_budget_minutes"] == 37.5
    assert summary["operable_freshness_margin_state"] == "WATCH"
    assert summary["operable_freshness_margin_warn_threshold_minutes"] == 7.5
    assert summary["operable_min_freshness_margin_chart"]["symbol"] == "BTC/USD"
    assert summary["top_issue"] == {}


def test_write_chart_health_report_outputs_summary(tmp_path):
    path = tmp_path / "chart_health.json"
    rows = [
        {
            "symbol": "AAPL",
            "market": "stock",
            "timeframe": "15m",
            "status": "OK",
            "label": "Viva",
            "indicator_status": "OK",
            "age_minutes": 8.0,
            "freshness_budget_minutes": 37.5,
        }
    ]

    out = write_chart_health_report(rows, path, generated_at=datetime(2026, 6, 10, 12, 0))

    payload = json.loads(out.read_text())
    assert payload["summary"]["status"] == "OK"
    assert payload["status"] == "OK"
    assert payload["checked"] == 1
    assert payload["checked_count"] == 1
    assert payload["fail_count"] == 0
    assert payload["warn_count"] == 0
    assert "max_chart_age_minutes" in payload
    assert "operable_max_chart_age_minutes" in payload
    assert "next_candle_minutes" in payload
    assert "operable_next_candle_minutes" in payload
    assert payload["min_freshness_margin_minutes"] == 29.5
    assert payload["min_freshness_budget_minutes"] == 37.5
    assert payload["operable_min_freshness_margin_minutes"] == 29.5
    assert payload["operable_min_freshness_margin_ratio"] == 0.7867
    assert payload["operable_min_freshness_budget_minutes"] == 37.5
    assert payload["operable_freshness_margin_state"] == "OK"
    assert payload["operable_freshness_margin_warn_threshold_minutes"] == 7.5
    assert payload["summary"]["operable_min_freshness_margin_minutes"] == 29.5
    assert payload["charts"][0]["symbol"] == "AAPL"
