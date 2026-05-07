from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests


RAW_COLUMNS = ["id", "platform", "url", "author", "content", "created_at", "collected_at"]
GITHUB_SEARCH_ENDPOINT = "https://api.github.com/search/issues"
QUERIES = [
    "kimi",
    "kimi k2",
    "kimi k2.6",
    "moonshot",
    "moonshot ai",
    "kimi code",
    "kimi coding",
    "kimi agent",
    "ollama kimi",
    "ollama k2",
]
REQUEST_TIMEOUT = (5, 10)


def collect(since: datetime, limit: int = 100) -> pd.DataFrame:
    """Collect public GitHub issues/PRs mentioning Kimi via Search API."""
    since_utc = _ensure_utc(since)
    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for query in QUERIES:
        if len(rows) >= limit:
            break
        try:
            payload = _fetch_items(query, since_utc, limit)
            for item in payload.get("items", []):
                if not isinstance(item, dict):
                    continue
                record = _normalize_item(item, since_utc)
                if record is None or record["id"] in seen_ids:
                    continue
                seen_ids.add(record["id"])
                rows.append(record)
                if len(rows) >= limit:
                    break
        except Exception as exc:
            print(f"GitHub: request failed for query={query}: {exc}")

    print(f"GitHub: collected {len(rows)} items")
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def _fetch_items(query: str, since: datetime, limit: int) -> dict[str, Any]:
    params = {
        "q": f"{query} in:title,body created:>={since.date().isoformat()}",
        "sort": "created",
        "order": "desc",
        "per_page": min(limit, 100),
    }
    response = requests.get(
        GITHUB_SEARCH_ENDPOINT,
        params=params,
        headers=_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "kimi-analysis-monitor/1.0",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _normalize_item(item: dict[str, Any], since: datetime) -> dict[str, str] | None:
    created_at = _parse_created_at(item.get("created_at"))
    if created_at is None or created_at < since:
        return None

    url = str(item.get("html_url") or "").strip()
    title = str(item.get("title") or "").strip()
    body = _strip_html(str(item.get("body") or "").strip())
    content = re.sub(r"\s+", " ", f"{title}. {body}".strip()).strip()
    if not url or not content:
        return None

    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    author = str(user.get("login") or "").strip()
    return {
        "id": _stable_id(url, content),
        "platform": "github",
        "url": url,
        "author": author,
        "content": content,
        "created_at": created_at.isoformat(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse_created_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return _ensure_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).replace("&amp;", "&").strip()


def _stable_id(url: str, content: str) -> str:
    payload = f"{url}|{content[:100]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
