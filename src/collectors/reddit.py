from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import pandas as pd
import requests

from config.settings import REDDIT_RSS_URLS


RAW_COLUMNS = ["id", "platform", "url", "author", "content", "created_at", "collected_at"]
HEADERS = {"User-Agent": "kimi-analysis-monitor/1.0"}
KEYWORDS = (
    "kimi",
    "k2",
    "k2.6",
    "k 2.6",
    "moonshot",
    "moonshot ai",
    "kimi code",
    "kimi coding",
    "kimi coding plan",
    "kimi agent",
    "kimi cli",
    "kimi k2",
    "kimi k2.6",
    "kimi 2.6",
    "kimi-k2",
    "kimi-k2.6",
    "kimi vs",
    "k2 vs",
    "k2.6 vs",
    "ollama kimi",
    "ollama k2",
    "vibe coding kimi",
    "vibecoding kimi",
)
REQUEST_TIMEOUT = (5, 10)


def collect(since: datetime, limit: int = 100) -> pd.DataFrame:
    """Collect Reddit posts/comments mentioning Kimi via RSS."""
    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    since_utc = _ensure_utc(since)

    for feed_url in REDDIT_RSS_URLS:
        if len(rows) >= limit:
            break
        try:
            print(f"Reddit: fetching {feed_url}")
            for entry in _fetch_entries(feed_url):
                record = _normalize_entry(entry, since_utc)
                if record is None or record["id"] in seen_ids:
                    continue
                seen_ids.add(record["id"])
                rows.append(record)
                if len(rows) >= limit:
                    break
        except Exception as exc:
            print(f"Reddit: request failed for {feed_url}: {exc}")

    print(f"Reddit: collected {len(rows)} items")
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def _fetch_entries(feed_url: str) -> list[Any]:
    response = requests.get(feed_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    feed = feedparser.parse(response.text)
    return list(feed.entries)


def _normalize_entry(entry: Any, since: datetime) -> dict[str, str] | None:
    title = str(getattr(entry, "title", "") or "").strip()
    content = _strip_html(str(getattr(entry, "summary", "") or "").strip()) or title
    if not _contains_keyword(f"{title} {content}"):
        return None

    created_at = _parse_entry_datetime(entry)
    if created_at is None or created_at < since:
        return None

    url = str(getattr(entry, "link", "") or "").strip()
    if not url:
        return None

    author = str(getattr(entry, "author", "") or "").strip()
    return {
        "id": _stable_id(url, content),
        "platform": "reddit",
        "url": url,
        "author": author,
        "content": content,
        "created_at": created_at.isoformat(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse_entry_datetime(entry: Any) -> datetime | None:
    published = str(getattr(entry, "published", "") or getattr(entry, "updated", "") or "").strip()
    if published:
        try:
            return _ensure_utc(parsedate_to_datetime(published))
        except (TypeError, ValueError):
            pass

    published_parsed = getattr(entry, "published_parsed", None)
    if published_parsed:
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)
    return None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).replace("&amp;", "&").strip()


def _contains_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in KEYWORDS)


def _stable_id(url: str, content: str) -> str:
    payload = f"{url}|{content[:100]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
