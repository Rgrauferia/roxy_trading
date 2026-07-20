"""Simple RSS/Atom news fetcher with on-disk caching.

Uses `feedparser` to fetch feeds and caches recent items to reduce network
requests. Exported function `fetch_news()` returns a list of news dicts with
`title`, `link`, `published`, `summary`, and `source` keys.
"""
from __future__ import annotations

import json
import calendar
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import feedparser

from roxy_trader.cache_policy import cache_age_status, cache_ttl as policy_cache_ttl
from roxy_trader.api_budget import observe_api_call
from durable_storage import atomic_write_text, exclusive_file_lock

CACHE_PATH = Path(".cache/news.json")
CACHE_SCHEMA_VERSION = 2
NEWS_CACHE_TTL_SECONDS = policy_cache_ttl("news")
CACHE_PATH.parent.mkdir(exist_ok=True)

DEFAULT_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://news.google.com/rss/search?q=cryptocurrency&hl=en-US&gl=US&ceid=US:en",
    "https://finance.yahoo.com/rss/",
]


@dataclass
class NewsItem:
    title: str
    link: str
    published: float
    summary: str
    source: str


# attempt to use VADER for sentiment if available, fallback to heuristic
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    _analyzer = SentimentIntensityAnalyzer()

    def _sentiment(text: str) -> float:  # type: ignore
        if not text:
            return 0.0
        vs = _analyzer.polarity_scores(text)
        return float(vs.get("compound", 0.0))
except Exception:
    def _sentiment(text: str) -> float:
        # very small heuristic sentiment using word lists
        pos = {
            "gain",
            "bull",
            "surge",
            "rise",
            "up",
            "strong",
            "beat",
            "soar",
            "record",
            "rally",
        }
        neg = {
            "drop",
            "fall",
            "down",
            "bear",
            "weak",
            "loss",
            "miss",
            "crash",
            "plunge",
            "sell",
        }
        txt = (text or "").lower()
        words = [w.strip(".,!?:;()\"'") for w in txt.split()]
        p = sum(1 for w in words if w in pos)
        n = sum(1 for w in words if w in neg)
        if p + n == 0:
            return 0.0
        return float(p - n) / float(max(1, p + n))


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {"ts": 0, "items": []}
    try:
        payload = json.loads(CACHE_PATH.read_text())
        if payload.get("schema_version") != CACHE_SCHEMA_VERSION:
            return {"ts": 0, "items": []}
        return payload
    except Exception:
        return {"ts": 0, "items": []}


def _save_cache(data: dict) -> None:
    atomic_write_text(json.dumps({"schema_version": CACHE_SCHEMA_VERSION, **data}), CACHE_PATH)


def fetch_news(feeds: List[str] = None, max_items: int = 25, cache_ttl: int = NEWS_CACHE_TTL_SECONDS) -> List[dict]:
    """Fetch latest news items from feeds with caching.

    - `feeds`: optional list of feed URLs. If not provided uses `DEFAULT_FEEDS`.
    - `max_items`: maximum number of items to return.
    - `cache_ttl`: TTL for cache in seconds (default 5 minutes).
    """
    feeds = feeds or DEFAULT_FEEDS
    cache = _load_cache()
    now = time.time()
    if cache.get("ts", 0) + cache_ttl > now and cache.get("items"):
        return cache["items"][:max_items]

    def fetch_feed(url: str) -> List[NewsItem]:
        feed_items: List[NewsItem] = []
        try:
            with observe_api_call("rss_news", "feed") as observation:
                f = feedparser.parse(url)
                observation.set_http_status(f.get("status"))
        except Exception:
            return feed_items
        source = f.get("feed", {}).get("title") or url
        for e in f.get("entries", [])[:50]:
            title = e.get("title", "")
            link = e.get("link", "")
            summary = e.get("summary", e.get("description", ""))
            published_parsed = e.get("published_parsed") or e.get("updated_parsed")
            if published_parsed:
                published = calendar.timegm(published_parsed)
            else:
                published = now
            feed_items.append(NewsItem(title=title, link=link, published=published, summary=summary, source=source))
        return feed_items

    items: List[NewsItem] = []
    with ThreadPoolExecutor(max_workers=max(1, min(4, len(feeds)))) as executor:
        for feed_items in executor.map(fetch_feed, feeds):
            items.extend(feed_items)

    # sort by published desc and take top
    items.sort(key=lambda x: x.published, reverse=True)

    out_items = []
    for i in items[:max_items]:
        txt = (i.title or "") + " \n " + (i.summary or "")
        sent = _sentiment(txt)
        out_items.append(
            {
                "title": i.title,
                "link": i.link,
                "published": i.published,
                "summary": i.summary,
                "source": i.source,
                "sentiment": sent,
            }
        )
    out = out_items
    if out:
        _save_cache({"ts": now, "items": out})
        return out
    cached_items = cache.get("items") if isinstance(cache.get("items"), list) else []
    if cached_items:
        return cached_items[:max_items]
    _save_cache({"ts": now, "items": []})
    return []


def fetch_news_snapshot(max_items: int = 25, cache_ttl: int = NEWS_CACHE_TTL_SECONDS) -> dict:
    items = fetch_news(max_items=max_items, cache_ttl=cache_ttl)
    cache = _load_cache()
    fetched_ts = float(cache.get("ts") or 0.0)
    age_seconds = max(0.0, time.time() - fetched_ts) if fetched_ts else None
    freshness = cache_age_status("news", age_seconds, {"ROXY_CACHE_TTL_NEWS": str(cache_ttl)})
    if not items:
        status = "NO_DATA"
        detail = "Los RSS no devolvieron noticias y no existe un snapshot previo."
    elif freshness == "FRESH":
        status = "CONNECTED"
        detail = f"{len(items)} noticias RSS; snapshot vigente."
    else:
        status = "DELAYED"
        detail = f"{len(items)} noticias desde cache ({freshness.lower()}); los RSS no renovaron el snapshot."
    sources = sorted({str(item.get("source") or "-") for item in items})
    return {
        "status": status,
        "detail": detail,
        "items": items,
        "sources": sources,
        "fetched_at": datetime.fromtimestamp(fetched_ts, timezone.utc).isoformat() if fetched_ts else "",
        "age_seconds": age_seconds,
        "cache_freshness": freshness,
        "cache_policy": "news",
        "cache_path": str(CACHE_PATH),
    }


def save_highlights(items: List[dict], path: str = "alerts/news_highlights.json") -> None:
    p = Path(path)
    with exclusive_file_lock(p):
        existing = []
        if p.exists():
            try:
                existing = json.loads(p.read_text())
            except Exception:
                existing = []
        # append new items but avoid duplicates by link
        links = {e.get("link") for e in existing}
        new = [i for i in items if i.get("link") not in links]
        combined = existing + new
        atomic_write_text(json.dumps(combined, indent=2), p)
    # also write a short latest alert and notify via notifier if available
    try:
        from notifier import notify_if_changed
        alerts = [f"{i.get('source', '')} {i.get('title', '')} | {i.get('link', '')}" for i in new]
        if alerts:
            notify_if_changed(alerts)
    except Exception:
        # notifier optional; ignore failures
        pass
    try:
        # write a human-readable latest_alert.txt summarizing saved items
        latest_path = Path("alerts/latest_alert.txt")
        if new:
            text = "\n".join([f"{i.get('source','')} {i.get('title','')}" for i in new])
            atomic_write_text(text, latest_path)
    except Exception:
        pass
