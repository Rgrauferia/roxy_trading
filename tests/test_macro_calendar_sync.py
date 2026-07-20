from __future__ import annotations

import json
from datetime import datetime, timezone

from tools.macro_calendar_sync import (
    CONTRACT_VERSION,
    parse_bea_schedule,
    parse_fed_schedule,
    sync_macro_calendar,
)


BEA_HTML = """
<html><body><h2>Year 2026</h2>
<table id="release-schedule-table"><tbody>
<tr class="scheduled-releases-type-press">
  <td class="scheduled-date no-wrap"><div class="release-date">July 30</div><small>8:30 AM</small></td>
  <td class="views-field">News</td>
  <td class="release-title views-field">GDP (Advance Estimate), 2nd Quarter 2026</td>
</tr>
<tr class="scheduled-releases-type-press">
  <td class="scheduled-date no-wrap"><div class="release-date">July 30</div><small>8:30 AM</small></td>
  <td class="views-field">News</td>
  <td class="release-title views-field">Personal Income and Outlays, June 2026</td>
</tr>
</tbody></table></body></html>
"""

FED_HTML = """
<html><body>
<div class="panel-heading"><h4><a id="42828">2026 FOMC Meetings</a></h4></div>
<div class="row fomc-meeting">
  <div class="fomc-meeting__month col-xs-5"><strong>July</strong></div>
  <div class="fomc-meeting__date col-xs-4">28-29</div>
</div>
<div class="fomc-meeting--shaded row fomc-meeting">
  <div class="fomc-meeting__month col-xs-5"><strong>September</strong></div>
  <div class="fomc-meeting__date col-xs-4">15-16*</div>
</div>
</body></html>
"""


def test_parse_bea_schedule_extracts_official_dates_and_severity():
    rows = parse_bea_schedule(BEA_HTML, fetched_at="2026-07-19T12:00:00+00:00", fallback_year=2025)

    assert len(rows) == 2
    assert rows[0]["date"] == "2026-07-30"
    assert rows[0]["time"] == "08:30"
    assert rows[0]["severity"] == "MEDIUM"
    assert rows[1]["severity"] == "MEDIUM"
    assert all(row["source"] == "U.S. Bureau of Economic Analysis" for row in rows)


def test_parse_fed_schedule_uses_meeting_end_date_and_high_severity():
    rows = parse_fed_schedule(FED_HTML, fetched_at="2026-07-19T12:00:00+00:00", target_year=2026)

    assert [row["date"] for row in rows] == ["2026-07-29", "2026-09-16"]
    assert all(row["time"] == "14:00" for row in rows)
    assert all(row["severity"] == "HIGH" for row in rows)
    assert rows[1]["event"] == "FOMC Rate Decision and Economic Projections"
    assert all(row["source"] == "Federal Reserve Board" for row in rows)


def test_sync_macro_calendar_writes_csv_and_versioned_report(tmp_path):
    calendar = tmp_path / "macro.csv"
    report_path = tmp_path / "report.json"

    report = sync_macro_calendar(
        calendar_path=calendar,
        report_path=report_path,
        now=datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
        fetcher=lambda: (BEA_HTML, {"last_modified": "Sat, 18 Jul 2026 12:00:00 GMT"}),
        fed_fetcher=lambda: (FED_HTML, {"etag": "fed-v1"}),
    )

    assert report["status"] == "OK"
    assert report["contract_version"] == CONTRACT_VERSION
    assert report["event_count"] == 4
    assert report["future_event_count"] == 4
    assert report["source_counts"] == {"bea": 2, "federal_reserve": 2}
    assert "GDP (Advance Estimate)" in calendar.read_text(encoding="utf-8")
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "OK"
    assert not [path for path in tmp_path.iterdir() if path.name.endswith(".tmp")]


def test_failed_sync_preserves_existing_calendar_and_reports_cache(tmp_path):
    calendar = tmp_path / "macro.csv"
    calendar.write_text("date,time,event\n2026-07-30,08:30,Existing\n", encoding="utf-8")
    report_path = tmp_path / "report.json"

    def fail_fetch():
        raise TimeoutError("upstream timeout")

    report = sync_macro_calendar(
        calendar_path=calendar,
        report_path=report_path,
        now=datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
        fetcher=fail_fetch,
        fed_fetcher=lambda: (FED_HTML, {}),
    )

    assert report["status"] == "WARN"
    assert report["cache_kept"] is True
    assert "Existing" in calendar.read_text(encoding="utf-8")
    assert "upstream timeout" not in report_path.read_text(encoding="utf-8")
