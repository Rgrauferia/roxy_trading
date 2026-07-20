#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from macro_calendar import LOCAL_TZ, infer_severity, read_macro_events
from roxy_trader.api_budget import observe_api_call


CONTRACT_VERSION = "roxy-macro-calendar-sync/1.0.0"
BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CALENDAR_PATH = BASE_DIR / "data" / "macro_events.csv"
DEFAULT_REPORT_PATH = BASE_DIR / "alerts" / "macro_calendar_sync.json"
BEA_SCHEDULE_URL = "https://www.bea.gov/news/schedule"
FED_FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
CSV_FIELDS = ("date", "time", "event", "severity", "currency", "notes", "source", "source_url", "fetched_at")


class BeaScheduleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_schedule = False
        self.in_row = False
        self.cell_kind = ""
        self.cell_text: list[str] = []
        self.row: dict[str, str] = {}
        self.rows: list[dict[str, str]] = []

    @staticmethod
    def attrs_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: str(value or "") for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self.attrs_dict(attrs)
        classes = set(values.get("class", "").split())
        if tag == "table" and values.get("id") == "release-schedule-table":
            self.in_schedule = True
        elif self.in_schedule and tag == "tr":
            self.in_row = True
            self.row = {}
        elif self.in_row and tag == "td":
            if "scheduled-date" in classes:
                self.cell_kind = "date"
            elif "release-title" in classes:
                self.cell_kind = "title"
            else:
                self.cell_kind = "other"
            self.cell_text = []

    def handle_data(self, data: str) -> None:
        if self.in_row and self.cell_kind:
            text = " ".join(str(data or "").split())
            if text:
                self.cell_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self.in_row and tag == "td" and self.cell_kind:
            self.row[self.cell_kind] = " ".join(self.cell_text).strip()
            self.cell_kind = ""
            self.cell_text = []
        elif self.in_schedule and tag == "tr" and self.in_row:
            if self.row.get("date") and self.row.get("title"):
                self.rows.append(dict(self.row))
            self.row = {}
            self.in_row = False
        elif tag == "table" and self.in_schedule:
            self.in_schedule = False


class FedFomcParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.year: int | None = None
        self.in_row = False
        self.row_depth = 0
        self.cell_kind = ""
        self.cell_text: list[str] = []
        self.row: dict[str, str] = {}
        self.rows: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = set(BeaScheduleParser.attrs_dict(attrs).get("class", "").split())
        if tag == "div" and "fomc-meeting" in classes and not self.in_row:
            self.in_row = True
            self.row_depth = 1
            self.row = {"year": str(self.year or "")}
            return
        if self.in_row and tag == "div":
            self.row_depth += 1
            if "fomc-meeting__month" in classes:
                self.cell_kind = "month"
                self.cell_text = []
            elif "fomc-meeting__date" in classes:
                self.cell_kind = "date"
                self.cell_text = []

    def handle_data(self, data: str) -> None:
        text = " ".join(str(data or "").split())
        year_match = re.fullmatch(r"(20\d{2})\s+FOMC\s+Meetings", text, flags=re.IGNORECASE)
        if year_match:
            self.year = int(year_match.group(1))
        if self.in_row and self.cell_kind and text:
            self.cell_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if not self.in_row or tag != "div":
            return
        if self.cell_kind:
            self.row[self.cell_kind] = " ".join(self.cell_text).strip()
            self.cell_kind = ""
            self.cell_text = []
        self.row_depth -= 1
        if self.row_depth == 0:
            if self.row.get("year") and self.row.get("month") and self.row.get("date"):
                self.rows.append(dict(self.row))
            self.row = {}
            self.in_row = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def fetch_official_html(
    url: str,
    *,
    provider: str,
    operation: str,
    timeout: float = 15.0,
) -> tuple[str, dict[str, str]]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RoxyTrading/1.0; macro-calendar)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with observe_api_call(provider, operation):
        with urlopen(request, timeout=timeout) as response:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            body = response.read(3_000_001)
            headers = {
                "last_modified": str(response.headers.get("Last-Modified") or ""),
                "etag": str(response.headers.get("ETag") or ""),
            }
    if len(body) > 3_000_000:
        raise ValueError("BEA schedule response exceeds 3 MB")
    if "html" not in content_type:
        raise ValueError(f"Unexpected BEA content type: {content_type or 'missing'}")
    return body.decode("utf-8", errors="replace"), headers


def fetch_bea_schedule(url: str = BEA_SCHEDULE_URL, *, timeout: float = 15.0) -> tuple[str, dict[str, str]]:
    return fetch_official_html(url, provider="bea", operation="release_schedule", timeout=timeout)


def fetch_fed_schedule(url: str = FED_FOMC_URL, *, timeout: float = 15.0) -> tuple[str, dict[str, str]]:
    return fetch_official_html(url, provider="federal_reserve", operation="fomc_schedule", timeout=timeout)


def parse_bea_schedule(html_text: str, *, fetched_at: str, fallback_year: int) -> list[dict[str, str]]:
    parser = BeaScheduleParser()
    parser.feed(html_text)
    year_match = re.search(r"\bYear\s+(20\d{2})\b", html_text, flags=re.IGNORECASE)
    year = int(year_match.group(1)) if year_match else int(fallback_year)
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in parser.rows:
        match = re.search(
            r"\b([A-Za-z]+\s+\d{1,2})\b.*?\b(\d{1,2}:\d{2}\s*[AP]M)\b",
            item.get("date", ""),
            flags=re.IGNORECASE,
        )
        title = " ".join(item.get("title", "").split())
        if not match or not title:
            continue
        try:
            local_time = datetime.strptime(
                f"{match.group(1)} {year} {match.group(2).upper().replace('  ', ' ')}",
                "%B %d %Y %I:%M %p",
            ).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
        date_value = local_time.strftime("%Y-%m-%d")
        time_value = local_time.strftime("%H:%M")
        key = (date_value, time_value, title.casefold())
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "date": date_value,
                "time": time_value,
                "event": title,
                "severity": infer_severity({"event": title}),
                "currency": "USD",
                "notes": "Calendario oficial de publicaciones BEA; hora America/New_York.",
                "source": "U.S. Bureau of Economic Analysis",
                "source_url": BEA_SCHEDULE_URL,
                "fetched_at": fetched_at,
            }
        )
    return sorted(results, key=lambda row: (row["date"], row["time"], row["event"]))


def parse_fed_schedule(html_text: str, *, fetched_at: str, target_year: int) -> list[dict[str, str]]:
    parser = FedFomcParser()
    parser.feed(html_text)
    results: list[dict[str, str]] = []
    for item in parser.rows:
        try:
            year = int(item.get("year") or 0)
        except ValueError:
            continue
        if year != int(target_year):
            continue
        days = re.findall(r"\d{1,2}", item.get("date", ""))
        month = " ".join(item.get("month", "").split())
        if not days or not month:
            continue
        try:
            local_time = datetime.strptime(
                f"{month} {days[-1]} {year} 2:00 PM",
                "%B %d %Y %I:%M %p",
            ).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
        projections = "*" in item.get("date", "")
        results.append(
            {
                "date": local_time.strftime("%Y-%m-%d"),
                "time": local_time.strftime("%H:%M"),
                "event": "FOMC Rate Decision and Economic Projections" if projections else "FOMC Rate Decision",
                "severity": "HIGH",
                "currency": "USD",
                "notes": (
                    "Fecha oficial del ultimo dia de la reunion FOMC; ventana operativa usa 2:00 PM ET, "
                    "hora habitual de publicacion del comunicado."
                ),
                "source": "Federal Reserve Board",
                "source_url": FED_FOMC_URL,
                "fetched_at": fetched_at,
            }
        )
    return sorted(results, key=lambda row: (row["date"], row["time"], row["event"]))


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def sync_macro_calendar(
    *,
    calendar_path: str | Path = DEFAULT_CALENDAR_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    now: datetime | None = None,
    fetcher: Callable[[], tuple[str, dict[str, str]]] = fetch_bea_schedule,
    fed_fetcher: Callable[[], tuple[str, dict[str, str]]] = fetch_fed_schedule,
) -> dict[str, Any]:
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    target = Path(calendar_path)
    report_target = Path(report_path)
    try:
        bea_html, response_headers = fetcher()
        fed_html, fed_headers = fed_fetcher()
        bea_rows = parse_bea_schedule(
            bea_html,
            fetched_at=generated_at.isoformat(),
            fallback_year=generated_at.year,
        )
        fed_rows = parse_fed_schedule(
            fed_html,
            fetched_at=generated_at.isoformat(),
            target_year=generated_at.year,
        )
        if not bea_rows:
            raise ValueError("BEA schedule contained no parseable releases")
        if not fed_rows:
            raise ValueError("Federal Reserve schedule contained no parseable FOMC meetings")
        rows = sorted(bea_rows + fed_rows, key=lambda row: (row["date"], row["time"], row["event"]))
        atomic_write(target, csv_bytes(rows))
        future = [
            row
            for row in rows
            if datetime.fromisoformat(f"{row['date']}T{row['time']}:00").replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            >= generated_at
        ]
        report: dict[str, Any] = {
            "contract_version": CONTRACT_VERSION,
            "generated_at": generated_at.isoformat(),
            "status": "OK",
            "source": "BEA + Federal Reserve Board",
            "source_url": BEA_SCHEDULE_URL,
            "sources": [BEA_SCHEDULE_URL, FED_FOMC_URL],
            "source_counts": {"bea": len(bea_rows), "federal_reserve": len(fed_rows)},
            "coverage": "BEA_RELEASES_AND_FOMC_MEETINGS",
            "calendar_path": str(target),
            "event_count": len(rows),
            "future_event_count": len(future),
            "next_event": future[0] if future else None,
            "upstream_last_modified": response_headers.get("last_modified", ""),
            "upstream_etag": response_headers.get("etag", ""),
            "fed_upstream_last_modified": fed_headers.get("last_modified", ""),
            "fed_upstream_etag": fed_headers.get("etag", ""),
            "cache_kept": False,
        }
    except Exception as exc:
        cached_event_count = len(read_macro_events(target))
        report = {
            "contract_version": CONTRACT_VERSION,
            "generated_at": generated_at.isoformat(),
            "status": "WARN",
            "source": "U.S. Bureau of Economic Analysis",
            "source_url": BEA_SCHEDULE_URL,
            "calendar_path": str(target),
            "event_count": cached_event_count,
            "future_event_count": 0,
            "next_event": None,
            "cache_kept": cached_event_count > 0,
            "error_category": type(exc).__name__,
            "detail": f"No se pudo actualizar BEA: {type(exc).__name__}. Se conserva el cache valido si existe.",
        }
    atomic_write(report_target, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Roxy's macro calendar from the official BEA schedule.")
    parser.add_argument("--calendar-path", default=str(DEFAULT_CALENDAR_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--no-fail", action="store_true")
    args = parser.parse_args()
    report = sync_macro_calendar(calendar_path=args.calendar_path, report_path=args.report_path)
    print(
        f"Macro calendar sync: {report['status']} | events {report['event_count']} | "
        f"future {report['future_event_count']}"
    )
    print(f"JSON: {args.report_path}")
    if report["status"] != "OK" and not args.no_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
