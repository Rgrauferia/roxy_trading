import json
import time
from concurrent.futures import ThreadPoolExecutor
from time import struct_time

import news
import notifier


def test_save_highlights_concurrent_writers_preserve_all_links(tmp_path, monkeypatch):
    path = tmp_path / "news_highlights.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(notifier, "notify_if_changed", lambda alerts: None)

    def save(index):
        news.save_highlights(
            [{"title": f"Headline {index}", "link": f"https://example.com/{index}", "source": "Test"}],
            path=str(path),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(save, range(16)))

    rows = json.loads(path.read_text())
    assert {row["link"] for row in rows} == {f"https://example.com/{index}" for index in range(16)}
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".news_highlights.json.lock").stat().st_mode & 0o777 == 0o600


def test_fetch_news_preserves_stale_cache_when_all_feeds_fail(tmp_path, monkeypatch):
    cache_path = tmp_path / "news.json"
    old_ts = time.time() - 3600
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": news.CACHE_SCHEMA_VERSION,
                "ts": old_ts,
                "items": [
                    {
                        "title": "Cached headline",
                        "link": "https://example.com/cached",
                        "published": old_ts,
                        "summary": "Prior verified snapshot",
                        "source": "Example RSS",
                        "sentiment": 0.0,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(news, "CACHE_PATH", cache_path)
    monkeypatch.setattr(news.feedparser, "parse", lambda _url: (_ for _ in ()).throw(RuntimeError("offline")))

    items = news.fetch_news(feeds=["https://example.com/rss"], max_items=5, cache_ttl=0)

    assert items[0]["title"] == "Cached headline"
    assert json.loads(cache_path.read_text())["ts"] == old_ts


def test_fetch_news_snapshot_marks_stale_cache_as_delayed(tmp_path, monkeypatch):
    cache_path = tmp_path / "news.json"
    old_ts = time.time() - 3600
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": news.CACHE_SCHEMA_VERSION,
                "ts": old_ts,
                "items": [{"title": "Cached headline", "source": "Example RSS"}],
            }
        )
    )
    monkeypatch.setattr(news, "CACHE_PATH", cache_path)
    monkeypatch.setattr(news, "fetch_news", lambda **_kwargs: json.loads(cache_path.read_text())["items"])

    snapshot = news.fetch_news_snapshot(max_items=5, cache_ttl=300)

    assert snapshot["status"] == "DELAYED"
    assert snapshot["sources"] == ["Example RSS"]
    assert snapshot["age_seconds"] >= 3500
    assert snapshot["fetched_at"]


def test_save_cache_replaces_payload_without_leaving_temporary_file(tmp_path, monkeypatch):
    cache_path = tmp_path / "news.json"
    monkeypatch.setattr(news, "CACHE_PATH", cache_path)

    news._save_cache({"ts": 1, "items": [{"title": "One"}]})

    assert json.loads(cache_path.read_text())["items"][0]["title"] == "One"
    assert json.loads(cache_path.read_text())["schema_version"] == news.CACHE_SCHEMA_VERSION
    assert not cache_path.with_suffix(".json.tmp").exists()


def test_fetch_news_interprets_feedparser_struct_time_as_utc(tmp_path, monkeypatch):
    cache_path = tmp_path / "news.json"
    monkeypatch.setattr(news, "CACHE_PATH", cache_path)
    parsed_time = struct_time((2026, 7, 19, 3, 0, 0, 6, 200, 0))
    monkeypatch.setattr(
        news.feedparser,
        "parse",
        lambda _url: {
            "feed": {"title": "Official RSS"},
            "entries": [
                {
                    "title": "Headline",
                    "link": "https://example.com/headline",
                    "summary": "Summary",
                    "published_parsed": parsed_time,
                }
            ],
        },
    )

    items = news.fetch_news(feeds=["https://example.com/rss"], max_items=5, cache_ttl=0)

    assert items[0]["published"] == 1784430000
