from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

RAW_COLUMNS = ["id", "platform", "url", "author", "content", "created_at", "collected_at"]
ALGOLIA_ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"
QUERIES = [
    "kimi",
    "k2",
    "k2.6",
    "moonshot",
    "moonshot ai",
    "kimi code",
    "kimi coding",
    "kimi agent",
    "kimi k2",
    "kimi k2.6",
    "kimi 2.6",
    "ollama kimi",
    "ollama k2",
    "vibe coding kimi",
]
HEADERS = {"User-Agent": "kimi-analysis-monitor/1.0"}
REQUEST_TIMEOUT = (5, 10)


def collect(since: datetime, limit: int = 100) -> pd.DataFrame:
    """Collect HN stories/comments mentioning Kimi via Algolia API."""
    since_utc = _ensure_utc(since)
    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for query in QUERIES:
        if len(rows) >= limit:
            break
        for tag in ["story", "comment"]:
            if len(rows) >= limit:
                break
            try:
                payload = _fetch_hits(query, tag, since_utc, limit)
                for hit in payload.get("hits", []):
                    if not isinstance(hit, dict):
                        continue
                    record = _normalize_hit(hit, since_utc)
                    if record is None or record["id"] in seen_ids:
                        continue
                    seen_ids.add(record["id"])
                    rows.append(record)
                    if len(rows) >= limit:
                        break
            except Exception as exc:
                print(f"HackerNews: request failed for query={query} tag={tag}: {exc}")

    print(f"HackerNews: collected {len(rows)} items")
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def _fetch_hits(query: str, tag: str, since: datetime, limit: int) -> dict[str, Any]:
    params = {
        "query": query,
        "tags": tag,
        "numericFilters": f"created_at_i>={int(since.timestamp())}",
        "hitsPerPage": limit,
    }
    response = requests.get(
        ALGOLIA_ENDPOINT,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _normalize_hit(hit: dict[str, Any], since: datetime) -> dict[str, str] | None:
    object_id = str(hit.get("objectID") or "").strip()
    created_at = _parse_created_at(hit)
    if not object_id or created_at is None or created_at < since:
        return None

    content = _content_from_hit(hit)
    if not content:
        return None

    url = f"https://news.ycombinator.com/item?id={object_id}"
    author = str(hit.get("author") or "").strip()
    return {
        "id": _stable_id(url, content),
        "platform": "hackernews",
        "url": url,
        "author": author,
        "content": content,
        "created_at": created_at.isoformat(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse_created_at(hit: dict[str, Any]) -> datetime | None:
    created_at = str(hit.get("created_at") or "").strip()
    if created_at:
        normalized = created_at.replace("Z", "+00:00")
        try:
            return _ensure_utc(datetime.fromisoformat(normalized))
        except ValueError:
            pass

    created_at_i = hit.get("created_at_i")
    if created_at_i is None:
        return None
    try:
        return datetime.fromtimestamp(int(created_at_i), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _content_from_hit(hit: dict[str, Any]) -> str:
    title = str(hit.get("title") or hit.get("story_title") or "").strip()
    text = str(hit.get("comment_text") or hit.get("story_text") or "").strip()
    content = _strip_html(text) or title
    return re.sub(r"\s+", " ", content).strip()


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).replace("&amp;", "&").strip()


def _stable_id(url: str, content: str) -> str:
    payload = f"{url}|{content[:100]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
