from __future__ import annotations

import pandas as pd
from pathlib import Path

from weekly_ai import WEEKLY_RESEARCH_CONTRACT, atomic_write_text, run_weekly, to_text, weekly_technical_snapshot


def test_weekly_module_does_not_import_legacy_streamlit_dashboard():
    source = Path("weekly_ai.py").read_text(encoding="utf-8")

    assert "from dashboard import" not in source


def history_frame(rows: int = 100) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=rows, freq="D"),
            "open": range(rows),
            "high": [value + 2 for value in range(rows)],
            "low": [value - 1 for value in range(rows)],
            "close": [value + 1 for value in range(rows)],
            "volume": [1_000 + value for value in range(rows)],
        }
    )


def setup_score(_frame: pd.DataFrame) -> dict:
    return {
        "score": 72,
        "reasons": ["Precio > EMA200"],
        "entry": 100.0,
        "stop": 95.0,
        "tp1": 105.0,
        "tp2": 110.0,
    }


def test_weekly_snapshot_labels_fallback_as_research_only():
    def fetcher(*_args, **_kwargs):
        return history_frame(), {"provider": "yfinance", "mode": "FALLBACK", "fallback": True}

    result = weekly_technical_snapshot("AAPL", history_fetcher=fetcher, setup_scorer=setup_score)

    assert result["status"] == "OK"
    assert result["signal"] == "BUY"
    assert result["data_provider"] == "yfinance"
    assert result["usage"] == "RESEARCH_ONLY_FALLBACK"
    assert result["alert_eligible"] is False


def test_weekly_snapshot_rejects_insufficient_history_with_source():
    def fetcher(*_args, **_kwargs):
        return history_frame(25), {"provider": "Polygon", "mode": "PREMIUM_DATA"}

    result = weekly_technical_snapshot("MSFT", history_fetcher=fetcher, setup_scorer=setup_score)

    assert result["status"] == "NO_DATA"
    assert "25 filas" in result["detail"]
    assert result["source"]["provider"] == "Polygon"


def test_weekly_report_counts_analyzed_and_skipped_without_silent_empty_result():
    def fetcher(symbol: str, **_kwargs):
        if symbol == "EMPTY":
            return pd.DataFrame(), {"provider": "Polygon", "mode": "PREMIUM_DATA"}
        return history_frame(), {"provider": "Polygon", "mode": "PREMIUM_DATA", "fallback": False}

    report = run_weekly(
        ["AAPL", "EMPTY"],
        history_fetcher=fetcher,
        setup_scorer=setup_score,
        news_fetcher=lambda *_args, **_kwargs: [],
    )

    assert report["total_scanned"] == 2
    assert report["contract_version"] == WEEKLY_RESEARCH_CONTRACT
    assert report["status"] == "OK"
    assert report["total_analyzed"] == 1
    assert report["total_skipped"] == 1
    assert report["top_all"][0]["symbol"] == "AAPL"
    assert report["top_all"][0]["usage"] == "RESEARCH_ONLY"
    assert report["skipped"][0]["status"] == "NO_DATA"
    assert "Polygon / PREMIUM_DATA / RESEARCH_ONLY" in to_text(report)


def test_weekly_report_write_is_atomic_and_replaces_previous_content(tmp_path: Path):
    target = tmp_path / "weekly.json"
    atomic_write_text(target, "old")
    atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "new"
    assert list(tmp_path.glob("*.tmp")) == []
