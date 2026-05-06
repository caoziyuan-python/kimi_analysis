import csv
import random
import re
import time
from datetime import date, datetime, timedelta
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
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "xhs_raw.csv"
CHROME_DRIVER_VERSION = "140"

BASELINE_START = "2026-03-20"
BASELINE_END = "2026-04-12"
POST_START = "2026-04-21"
TODAY = date(2026, 4, 23)

KEYWORDS = [
    "Kimi",
    "KimiK2.6",
    "Kimi AI",
    "月之暗面",
    "Kimi好用吗",
    "Kimi踩坑",
    "Kimi会员",
    "AI编程",
    "Kimi代码",
    "大模型测评",
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
        f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}"
        "&source=web_explore_feed&sort=time_descending"
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
    if answer_date < BASELINE_START:
        return None
    if answer_date >= POST_START:
        return "post_launch"
    return "post_launch"


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


def parse_xhs_date(raw_text: str) -> str | None:
    text = normalize_space(raw_text)
    if not text:
        return None

    if "分钟前" in text or "小时前" in text:
        return TODAY.isoformat()

    if "昨天" in text:
        return (TODAY - timedelta(days=1)).isoformat()

    days_ago_match = re.search(r"(\d+)\s*天前", text)
    if days_ago_match:
        days_ago = int(days_ago_match.group(1))
        return (TODAY - timedelta(days=days_ago)).isoformat()

    month_day_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if month_day_match:
        month = int(month_day_match.group(1))
        day = int(month_day_match.group(2))
        return date(2026, month, day).isoformat()

    full_date_match = re.search(r"(2026)[-/](\d{1,2})[-/](\d{1,2})", text)
    if full_date_match:
        year = int(full_date_match.group(1))
        month = int(full_date_match.group(2))
        day = int(full_date_match.group(3))
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


def absolutize_xhs_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"https://www.xiaohongshu.com{url}"
    return url


def extract_note_cards(driver: webdriver.Chrome):
    selectors = [
        "section.note-item",
        ".feeds-container .note-item",
        "[data-v] a.title",
    ]

    for selector in selectors:
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            cards = []
        if cards:
            return cards
    return []


def click_latest_if_present(driver: webdriver.Chrome) -> None:
    selectors = [
        (By.CSS_SELECTOR, ".filter-item"),
        (By.CSS_SELECTOR, "[data-type='time']"),
        (By.XPATH, "//button[contains(., '最新')]"),
        (By.XPATH, "//*[contains(@class, 'filter-item') and contains(., '最新')]"),
        (By.XPATH, "//*[contains(., '最新') and (self::button or self::div or self::span or self::a)]"),
    ]

    for by, selector in selectors:
        try:
            elements = driver.find_elements(by, selector)
        except Exception:
            elements = []

        for element in elements:
            text = normalize_space(element.text)
            data_type = normalize_space(element.get_attribute("data-type") or "")
            if selector == "[data-type='time']" or "最新" in text or data_type == "time":
                try:
                    driver.execute_script("arguments[0].click();", element)
                    time.sleep(3)
                    return
                except Exception:
                    continue


def collect_note_summaries(driver: webdriver.Chrome, keyword: str) -> List[dict]:
    driver.get(build_search_url(keyword))
    time.sleep(12)
    click_latest_if_present(driver)

    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(5)

    cards = extract_note_cards(driver)
    note_summaries: List[dict] = []
    seen_note_urls: set[str] = set()

    for card in cards:
        if len(note_summaries) >= 15:
            break

        title = extract_first_text(card, [".title", "a.title"])
        url = absolutize_xhs_url(
            extract_first_href(
                card,
                [
                    "a.title",
                    "a[href*='/explore/']",
                    "a[href*='/discovery/item/']",
                    "a",
                ],
            )
        )

        if not title or not url or url in seen_note_urls:
            continue

        seen_note_urls.add(url)
        note_summaries.append({"title": title, "url": url})

    return note_summaries


def build_record(keyword: str, title: str, content: str, answer_date: str, likes: int, url: str) -> dict | None:
    period = get_period(answer_date)
    if period is None:
        return None

    clean_title = normalize_space(title)
    clean_content = normalize_space(content) or clean_title
    if not clean_title or not clean_content or not url:
        return None

    return {
        "title": clean_title,
        "content": clean_content,
        "answer_created_time": answer_date,
        "likes": likes,
        "comments": 0,
        "url": url,
        "content_type": "xhs_post",
        "subreddit": "xiaohongshu",
        "search_query": keyword,
        "query_type": get_query_type(keyword),
        "query_type_weight": 1.0,
        "source": "xhs",
        "period": period,
        "crawl_time": datetime.now().isoformat(timespec="seconds"),
    }


def collect_note_detail(driver: webdriver.Chrome, keyword: str, title: str, note_url: str) -> dict | None:
    driver.get(note_url)
    time.sleep(5)

    content = extract_first_text(
        driver,
        [
            ".note-content",
            "#detail-desc",
            ".content",
        ],
    )
    if not content:
        content = title

    raw_date = extract_first_text(
        driver,
        [
            ".date",
            ".publish-date",
        ],
    )
    answer_date = parse_xhs_date(raw_date)
    if not answer_date:
        answer_date = TODAY.isoformat()

    likes_text = extract_first_text(
        driver,
        [
            ".like-wrapper .count",
            ".interactions",
        ],
    )
    likes = parse_count(likes_text)

    return build_record(keyword, title, content, answer_date, likes, note_url)


def collect_keyword_rows(driver: webdriver.Chrome, keyword: str, seen_urls: set[str]) -> List[dict]:
    note_summaries = collect_note_summaries(driver, keyword)
    rows: List[dict] = []

    for note in note_summaries:
        note_url = str(note["url"]).strip()
        if not note_url or note_url in seen_urls:
            continue

        record = collect_note_detail(driver, keyword, str(note["title"]), note_url)
        if record is None:
            continue

        seen_urls.add(note_url)
        rows.append(record)
        time.sleep(random.uniform(3, 6))

    return rows


def collect_xhs() -> None:
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

            time.sleep(random.uniform(8, 15))
    finally:
        driver.quit()


if __name__ == "__main__":
    collect_xhs()
