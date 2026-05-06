import csv
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "reddit_raw.csv"

BASELINE_START = "2026-03-20"
BASELINE_END = "2026-04-12"
POST_START = "2026-04-21"

KEYWORDS = [
    "kimi k2.6",
    "kimi k2",
    "moonshot kimi",
    "moonshot AI",
    "kimi agent",
    "kimi coding",
    "kimi vs claude",
    "kimi vs gpt",
    "kimi agentic",
    "kimi open source",
    "kimi vibe coding",
    "kimi agent swarm",
    "kimi worth it",
    "kimi review",
    "kimi benchmark",
]

FIELDNAMES = [
    "title",
    "content",
    "answer_created_time",
    "likes",
    "comments",
    "url",
    "content_type",
    "subreddit",
    "search_query",
    "query_type",
    "query_type_weight",
    "source",
    "period",
    "crawl_time",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


def ensure_output_dir() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_query_type(keyword: str) -> str:
    lowered = keyword.lower()
    if "coding" in lowered or "agent" in lowered:
        return "feature"
    if "vs" in lowered:
        return "comparison"
    return "version"


def get_query_type_weight(query_type: str) -> float:
    if query_type == "comparison":
        return 0.8
    return 1.0


def get_period(answer_date: str) -> str | None:
    if BASELINE_START <= answer_date <= BASELINE_END:
        return "baseline"
    if answer_date >= POST_START:
        return "post_launch"
    return None


def build_search_url(keyword: str) -> str:
    return f"https://hn.algolia.com/api/v1/search?query={quote(keyword)}&hitsPerPage=100"


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def append_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    ensure_output_dir()
    file_exists = OUTPUT_FILE.exists()
    with OUTPUT_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def normalize_hit(hit: dict[str, Any], keyword: str) -> dict[str, Any] | None:
    title = str(hit.get("title") or hit.get("story_title") or "").strip()
    object_id = hit.get("objectID")
    created_at = str(hit.get("created_at") or "").strip()
    if not object_id or len(created_at) < 10:
        return None

    answer_date = created_at[:10]
    period = get_period(answer_date)
    if period is None:
        return None

    query_type = get_query_type(keyword)
    raw_content = str(hit.get("story_text") or hit.get("comment_text") or "").strip()
    content = strip_html(raw_content) or title or "HN comment"
    title = title or "HN comment"
    hit_tags = [str(tag).lower() for tag in hit.get("_tags", []) if tag is not None]
    content_type = "hn_comment" if "comment" in hit_tags else "hn_post"

    return {
        "title": title,
        "content": content,
        "answer_created_time": answer_date,
        "likes": int(hit.get("points", 0) or 0),
        "comments": int(hit.get("num_comments", 0) or 0),
        "url": f"https://news.ycombinator.com/item?id={object_id}",
        "content_type": content_type,
        "subreddit": "hackernews",
        "search_query": keyword,
        "query_type": query_type,
        "query_type_weight": get_query_type_weight(query_type),
        "source": "hackernews",
        "period": period,
        "crawl_time": datetime.now().isoformat(timespec="seconds"),
    }


def fetch_keyword_hits(session: requests.Session, keyword: str) -> list[dict[str, Any]]:
    response = session.get(
        build_search_url(keyword),
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    records: list[dict[str, Any]] = []
    for hit in payload.get("hits", []):
        if not isinstance(hit, dict):
            continue
        record = normalize_hit(hit, keyword)
        if record is not None:
            records.append(record)

    return records


def collect_hn() -> None:
    ensure_output_dir()
    session = requests.Session()
    seen_urls: set[str] = set()

    for keyword in KEYWORDS:
        collected_rows: list[dict[str, Any]] = []
        try:
            records = fetch_keyword_hits(session, keyword)
            for record in records:
                url = str(record["url"]).strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                collected_rows.append(record)
            append_rows(collected_rows)
        except requests.RequestException as exc:
            print(f"{keyword}: request failed - {exc}")
        except ValueError as exc:
            print(f"{keyword}: invalid response - {exc}")
        finally:
            print(f"{keyword}: collected {len(collected_rows)} items")
            time.sleep(random.uniform(1, 2))


if __name__ == "__main__":
    collect_hn()
