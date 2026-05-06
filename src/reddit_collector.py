import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import feedparser
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "reddit_raw.csv"

BASELINE_START = "2026-03-20"
BASELINE_END = "2026-04-12"
POST_START = "2026-04-21"

RSS_URLS = [
    "https://www.reddit.com/r/LocalLLaMA/.rss?limit=100",
    "https://www.reddit.com/r/MachineLearning/.rss?limit=100",
    "https://www.reddit.com/r/artificial/.rss?limit=100",
    "https://www.reddit.com/r/ChatGPT/.rss?limit=100",
]

FILTER_KEYWORDS = ["kimi", "moonshot", "k2.6"]

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
    "User-Agent": "kimi-research-bot/0.1 (by kimi_analysis)",
}


def strip_html(raw_content: str) -> str:
    return re.sub(r"<[^>]+>", "", raw_content).strip()


def get_query_type(subreddit: str) -> str:
    if subreddit == "LocalLLaMA":
        return "feature"
    return "version"


def get_query_type_weight(query_type: str) -> float:
    if query_type == "comparison":
        return 0.8
    return 1.0


def get_period(date_str: str) -> str | None:
    if BASELINE_START <= date_str <= BASELINE_END:
        return "baseline"
    if date_str >= POST_START:
        return "post_launch"
    return None


def get_subreddit(entry: Any, post_url: str) -> str:
    tags = getattr(entry, "tags", None) or []
    for tag in tags:
        term = str(getattr(tag, "term", "")).strip()
        if term:
            return term

    match = re.search(r"reddit\.com/r/([^/]+)/", post_url, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def should_keep_entry(title: str, content: str) -> bool:
    combined = f"{title} {content}".lower()
    return any(keyword in combined for keyword in FILTER_KEYWORDS)


def ensure_output_dir() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


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


def normalize_entry(entry: Any, feed_url: str) -> dict[str, Any] | None:
    published_parsed = getattr(entry, "published_parsed", None)
    if not published_parsed:
        return None

    title = str(getattr(entry, "title", "") or "").strip()
    raw_content = str(getattr(entry, "summary", "") or "").strip()
    content = strip_html(raw_content) or title
    if not should_keep_entry(title, content):
        return None

    date_str = datetime(*published_parsed[:6]).strftime("%Y-%m-%d")
    period = get_period(date_str)
    if period is None:
        return None

    url = str(getattr(entry, "link", "") or "").strip()
    if not url:
        return None

    subreddit = get_subreddit(entry, url)
    query_type = get_query_type(subreddit)
    _author = str(getattr(entry, "author", "") or "").strip()

    return {
        "title": title,
        "content": content,
        "answer_created_time": date_str,
        "likes": 0,
        "comments": 0,
        "url": url,
        "content_type": "reddit_post",
        "subreddit": subreddit,
        "search_query": feed_url,
        "query_type": query_type,
        "query_type_weight": get_query_type_weight(query_type),
        "source": "reddit",
        "period": period,
        "crawl_time": datetime.now().isoformat(timespec="seconds"),
    }


def fetch_rss_links(feed_url: str) -> list[tuple[Any, str]]:
    resp = requests.get(feed_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)

    links: list[tuple[Any, str]] = []
    for entry in feed.entries:
        url = str(getattr(entry, "link", "") or "").strip()
        if url:
            links.append((entry, url))

    return links


def collect_reddit() -> None:
    seen_urls: set[str] = set()

    for feed_url in RSS_URLS:
        collected_rows: list[dict[str, Any]] = []
        try:
            entry_links = fetch_rss_links(feed_url)
            for entry, url in entry_links:
                normalized_url = url.strip()
                if not normalized_url or normalized_url in seen_urls:
                    continue

                record = normalize_entry(entry, feed_url)
                if record is None:
                    continue

                seen_urls.add(normalized_url)
                collected_rows.append(record)

            append_rows(collected_rows)
        except requests.RequestException as exc:
            print(f"{feed_url}: request failed - {exc}")
        except Exception as exc:
            print(f"{feed_url}: parse failed - {exc}")
        finally:
            print(f"{feed_url}: collected {len(collected_rows)} posts")


if __name__ == "__main__":
    collect_reddit()
