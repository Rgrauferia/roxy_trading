"""Simple RSS/Atom news fetcher with on-disk caching.

Uses `feedparser` to fetch feeds and caches recent items to reduce network
requests. Exported function `fetch_news()` returns a list of news dicts with
`title`, `link`, `published`, `summary`, and `source` keys.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

import feedparser

CACHE_PATH = Path(".cache/news.json")
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
        return json.loads(CACHE_PATH.read_text())
    except Exception:
        return {"ts": 0, "items": []}


def _save_cache(data: dict) -> None:
    CACHE_PATH.write_text(json.dumps(data))


def fetch_news(feeds: List[str] = None, max_items: int = 25, cache_ttl: int = 300) -> List[dict]:
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

    items: List[NewsItem] = []
    for url in feeds:
        try:
            f = feedparser.parse(url)
        except Exception:
            continue
        source = f.get("feed", {}).get("title") or url
        for e in f.get("entries", [])[:50]:
            title = e.get("title", "")
            link = e.get("link", "")
            summary = e.get("summary", e.get("description", ""))
            published_parsed = e.get("published_parsed") or e.get("updated_parsed")
            if published_parsed:
                published = time.mktime(published_parsed)
            else:
                published = now
            items.append(NewsItem(title=title, link=link, published=published, summary=summary, source=source))

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
    _save_cache({"ts": now, "items": out})
    return out


def save_highlights(items: List[dict], path: str = "alerts/news_highlights.json") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
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
    p.write_text(json.dumps(combined, indent=2))
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
            latest_path.write_text(text)
    except Exception:
        pass
