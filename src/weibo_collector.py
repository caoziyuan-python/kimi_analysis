import csv
import random
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import List
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "weibo_raw.csv"
CHROME_DRIVER_VERSION = "140"

BASELINE_START = "2026-03-20"
BASELINE_END = "2026-04-12"
POST_START = "2026-04-21"
TODAY = date(2026, 4, 23)

KEYWORDS = [
    "Kimi K2.6",
    "Kimi 好用吗",
    "Kimi 踩坑",
    "Kimi 会员",
    "Kimi 代码",
    "月之暗面 K2.6",
    "Kimi 更新",
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


def ensure_output_dir() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


def init_driver() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    try:
        service = Service(ChromeDriverManager(driver_version=CHROME_DRIVER_VERSION).install())
    except Exception:
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(35)
    return driver


def build_search_url(keyword: str) -> str:
    return (
        f"https://s.weibo.com/weibo?q={quote(keyword)}&typeall=1&suball=1"
        "&timescope=custom:2026-03-20:2026-04-23&Refer=g"
    )


def get_query_type(keyword: str) -> str:
    lowered = keyword.lower()
    if "代码" in keyword or "coding" in lowered:
        return "feature"
    if "会员" in keyword or "价格" in keyword:
        return "business"
    if "踩坑" in keyword or "好用" in keyword:
        return "experience"
    return "version"


def get_period(answer_date: str) -> str | None:
    if BASELINE_START <= answer_date <= BASELINE_END:
        return "baseline"
    if answer_date >= POST_START:
        return "post_launch"
    return None


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def parse_count(text: str) -> int:
    cleaned = normalize_space(text)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(万)?", cleaned)
    if not match:
        return 0
    value = float(match.group(1))
    if match.group(2) == "万":
        value *= 10000
    return int(value)


def parse_weibo_date(raw_text: str) -> str | None:
    text = normalize_space(raw_text)
    if not text:
        return None

    if "今天" in text or "分钟前" in text or "小时前" in text:
        return TODAY.isoformat()

    month_day_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if month_day_match:
        month = int(month_day_match.group(1))
        day = int(month_day_match.group(2))
        return date(2026, month, day).isoformat()

    full_date_match = re.search(r"(2026)-(\d{1,2})-(\d{1,2})", text)
    if full_date_match:
        year = int(full_date_match.group(1))
        month = int(full_date_match.group(2))
        day = int(full_date_match.group(3))
        return date(year, month, day).isoformat()

    slash_match = re.search(r"(2026)/(\d{1,2})/(\d{1,2})", text)
    if slash_match:
        year = int(slash_match.group(1))
        month = int(slash_match.group(2))
        day = int(slash_match.group(3))
        return date(year, month, day).isoformat()

    return None


def append_rows(rows: List[dict]) -> None:
    if not rows:
        return

    ensure_output_dir()
    file_exists = OUTPUT_FILE.exists()
    with OUTPUT_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def extract_first_text(element, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            candidates = element.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            candidates = []

        for candidate in candidates:
            text = normalize_space(candidate.text)
            if text:
                return text
    return ""


def extract_first_href(element, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            candidates = element.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            candidates = []

        for candidate in candidates:
            href = (candidate.get_attribute("href") or "").strip()
            if href:
                return href
    return ""


def extract_likes(card) -> int:
    try:
        li_elements = card.find_elements(By.CSS_SELECTOR, ".card-act li")
    except Exception:
        li_elements = []

    for li in li_elements[::-1]:
        text = normalize_space(li.text)
        if text:
            count = parse_count(text)
            if count > 0:
                return count
    return 0


def build_record(keyword: str, content: str, answer_date: str, url: str, likes: int) -> dict | None:
    period = get_period(answer_date)
    if period is None:
        return None

    content = normalize_space(content)
    if not content or not url:
        return None

    return {
        "title": content[:50],
        "content": content,
        "answer_created_time": answer_date,
        "likes": likes,
        "comments": 0,
        "url": url,
        "content_type": "weibo_post",
        "subreddit": "weibo",
        "search_query": keyword,
        "query_type": get_query_type(keyword),
        "query_type_weight": 1.0,
        "source": "weibo",
        "period": period,
        "crawl_time": datetime.now().isoformat(timespec="seconds"),
    }


def extract_cards(driver: webdriver.Chrome):
    selectors = [
        ".card-wrap",
        ".WB_cardwrap",
        "[action-type='feed_list_item']",
    ]

    for selector in selectors:
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            cards = []
        if cards:
            return cards
    return []


def collect_keyword_rows(driver: webdriver.Chrome, keyword: str, seen_urls: set[str]) -> List[dict]:
    driver.get(build_search_url(keyword))
    time.sleep(5)

    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

    cards = extract_cards(driver)
    rows: List[dict] = []

    for card in cards:
        if len(rows) >= 20:
            break

        content = extract_first_text(
            card,
            [
                ".txt[node-type='feed_list_content_full']",
                ".txt[node-type='feed_list_content']",
                ".txt",
            ],
        )
        if not content:
            continue

        raw_time = extract_first_text(card, [".from a", "time"])
        answer_date = parse_weibo_date(raw_time)
        if not answer_date:
            continue

        url = extract_first_href(
            card,
            [
                ".from a",
                "a[href*='weibo.com']",
            ],
        )
        if not url or url in seen_urls:
            continue

        record = build_record(keyword, content, answer_date, url, extract_likes(card))
        if record is None:
            continue

        seen_urls.add(url)
        rows.append(record)

    return rows


def collect_weibo() -> None:
    ensure_output_dir()
    driver = init_driver()
    seen_urls: set[str] = set()

    try:
        for keyword in KEYWORDS:
            try:
                rows = collect_keyword_rows(driver, keyword, seen_urls)
                append_rows(rows)
                print(f"{keyword}: collected {len(rows)} posts")
            except WebDriverException as exc:
                print(f"{keyword}: selenium failed - {exc}")
            except Exception as exc:
                print(f"{keyword}: parse failed - {exc}")

            time.sleep(random.uniform(2, 4))
    finally:
        driver.quit()


if __name__ == "__main__":
    collect_weibo()
