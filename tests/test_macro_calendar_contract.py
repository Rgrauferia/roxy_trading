import csv
from datetime import datetime, timezone

from macro_calendar import macro_calendar_status


def _write_calendar(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("date", "time", "event", "severity", "source", "source_url", "fetched_at"),
        )
        writer.writeheader()
        writer.writerows(rows)


def test_missing_calendar_fails_closed_for_calendar_alerts(tmp_path):
    status = macro_calendar_status(
        tmp_path / "missing.csv",
        now=datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
    )

    assert status["data_status"] == "NOT_CONFIGURED"
    assert status["alerts_allowed"] is False
    assert status["alert_scope"] == "CALENDAR_EVENTS_ONLY"
    assert status["market_signal_gate"] == "CONTEXT_ONLY"


def test_empty_calendar_fails_closed_for_calendar_alerts(tmp_path):
    path = tmp_path / "events.csv"
    _write_calendar(path, [])

    status = macro_calendar_status(path, now=datetime(2026, 7, 19, 12, tzinfo=timezone.utc))

    assert status["data_status"] == "NO_DATA"
    assert status["alerts_allowed"] is False


def test_official_schedule_allows_calendar_notifications_but_not_market_signals(tmp_path):
    path = tmp_path / "events.csv"
    _write_calendar(
        path,
        [
            {
                "date": "2026-07-20",
                "time": "08:30",
                "event": "GDP release",
                "severity": "MEDIUM",
                "source": "Official source",
                "source_url": "https://example.gov/schedule",
                "fetched_at": "2026-07-19T11:00:00+00:00",
            }
        ],
    )

    status = macro_calendar_status(
        path,
        now=datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
        upcoming_hours=48,
    )

    assert status["data_status"] == "CONNECTED"
    assert status["alerts_allowed"] is True
    assert status["market_signal_gate"] == "CONTEXT_ONLY"
