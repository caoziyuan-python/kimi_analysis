import csv
import random
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"
SRC_DIR = PROJECT_ROOT / "src"
REPORT_DIR = PROJECT_ROOT / "output" / "report"
OUTPUT_FILE = RAW_DIR / "zhihu_raw.csv"


# Time windows
BASELINE_START = date.fromisoformat("2026-03-20")
BASELINE_END = date.fromisoformat("2026-04-12")
POST_START = date.fromisoformat("2026-04-21")
POST_END = date.today()


# Crawl settings
MAX_ITEMS_PER_QUERY = 20
MAX_RETRIES = 3
CHROME_DRIVER_VERSION = "140"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
]

version_keywords = [
    "Kimi K2.6",
    "月之暗面 K2.6",
    "Kimi 新版本",
    "Kimi 更新",
]

feature_keywords = [
    "Kimi 写代码",
    "Kimi 代码生成",
    "Kimi Agent",
    "Kimi 长文本",
    "Kimi Vibe Coding",
    "Kimi 自动任务",
]

experience_keywords = [
    "Kimi 好用吗",
    "Kimi 体验",
    "Kimi 踩坑",
    "Kimi 翻车",
    "Kimi 怎么样",
    "Kimi 对比",
]

business_keywords = [
    "Kimi 会员",
    "Kimi 收费",
    "Kimi 值得买",
    "Kimi 价格",
]


def ensure_directories() -> None:
    for path in [RAW_DIR, CLEANED_DIR, SRC_DIR, REPORT_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def random_sleep() -> None:
    time.sleep(random.uniform(2, 5))


def build_queries() -> List[Dict[str, object]]:
    queries: List[Dict[str, object]] = []

    for kw in version_keywords:
        queries.append(
            {
                "search_query": kw,
                "query_type": "version",
                "query_type_weight": 1.0,
            }
        )

    for kw in feature_keywords:
        queries.append(
            {
                "search_query": kw,
                "query_type": "feature",
                "query_type_weight": 1.0,
            }
        )

    for kw in experience_keywords:
        queries.append(
            {
                "search_query": kw,
                "query_type": "experience",
                "query_type_weight": 1.0,
            }
        )

    for kw in business_keywords:
        queries.append(
            {
                "search_query": kw,
                "query_type": "business",
                "query_type_weight": 0.5,
            }
        )

    return queries


def init_driver() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option(
        "debuggerAddress", "127.0.0.1:9222"
    )

    try:
        service = Service(ChromeDriverManager(driver_version="140").install())
    except Exception:
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(35)
    return driver


def rotate_user_agent(driver: webdriver.Chrome) -> None:
    ua = random.choice(USER_AGENTS)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": ua})
    except Exception:
        pass


def fetch_with_retry(driver: webdriver.Chrome, url: str, retries: int = MAX_RETRIES) -> bool:
    for attempt in range(1, retries + 1):
        try:
            rotate_user_agent(driver)
            driver.get(url)
            random_sleep()
            return True
        except (TimeoutException, WebDriverException):
            if attempt == retries:
                return False
            random_sleep()
    return False


def parse_count(text: str) -> int:
    cleaned = text.replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(万)?", cleaned)
    if not match:
        return 0
    val = float(match.group(1))
    if match.group(2) == "万":
        val *= 10000
    return int(val)


def parse_date_from_text(text: str) -> Optional[date]:
    if not text:
        return None

    text = text.strip()

    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})T", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return None


def judge_period(answer_date: date) -> Optional[str]:
    if BASELINE_START <= answer_date <= BASELINE_END:
        return "baseline"
    if POST_START <= answer_date <= POST_END:
        return "post_launch"
    return None


def detect_content_type(url: str) -> str:
    if "/answer/" in url:
        return "answer"
    if "zhihu.com/p/" in url:
        return "article"
    if "/question/" in url:
        return "question"
    return "question"


def pick_text(driver: webdriver.Chrome, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = element.text.strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def pick_time_text(driver: webdriver.Chrome, content_type: str) -> str:
    answer_time_selectors = [
        ".AnswerItem time",
        ".AnswerCard time",
        ".List-item .AnswerItem time",
        "time[itemprop='dateCreated']",
        "meta[itemprop='dateCreated']",
    ]

    article_time_selectors = [
        "time",
        "meta[itemprop='datePublished']",
        ".ContentItem-time",
    ]

    selectors = answer_time_selectors if content_type in {"answer", "question"} else article_time_selectors

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = (element.get_attribute("datetime") or element.get_attribute("content") or element.text or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def extract_likes_comments(driver: webdriver.Chrome, page_text: str) -> Dict[str, int]:
    likes = 0
    comments = 0
    likes_selectors = [
        "[class*='voteCount']",
        ".VoteButton span",
        "button[aria-label*='赞同'] span",
    ]
    comments_selectors = [
        "[class*='commentCount']",
    ]

    likes_patterns = [
        r"(\d+(?:\.\d+)?\s*万?)\s*赞同",
        r"(\d+(?:\.\d+)?\s*万?)\s*点赞",
    ]
    comments_patterns = [
        r"(\d+(?:\.\d+)?\s*万?)\s*评论",
        r"(\d+(?:\.\d+)?\s*万?)\s*条评论",
        r"(\d+(?:\.\d+)?\s*万?)\s*条回答",
        r"(\d+(?:\.\d+)?\s*万?)\s*回答",
        r"\"commentCount\":(\d+)",
        r"\"totalItems\":(\d+)",
    ]

    for selector in likes_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []
        for element in elements:
            text = (element.text or element.get_attribute("aria-label") or "").strip()
            m = re.search(r"\d+(?:\.\d+)?\s*万?", text)
            if m:
                likes = parse_count(m.group(0))
                break
        if likes > 0:
            break

    for selector in comments_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []
        for element in elements:
            text = (element.text or element.get_attribute("aria-label") or "").strip()
            m = re.search(r"\d+(?:\.\d+)?\s*万?", text)
            if m:
                comments = parse_count(m.group(0))
                break
        if comments > 0:
            break

    for pattern in likes_patterns:
        if likes > 0:
            break
        m = re.search(pattern, page_text)
        if m:
            likes = parse_count(m.group(1))
            break

    for pattern in comments_patterns:
        if comments > 0:
            break
        m = re.search(pattern, page_text)
        if m:
            if "commentCount" in pattern or "totalItems" in pattern:
                comments = int(m.group(1))
            else:
                comments = parse_count(m.group(1))
            break

    return {"likes": likes, "comments": comments}


def parse_detail_page(
    driver: webdriver.Chrome,
    url: str,
    query: str,
    query_type: str,
    query_type_weight: float,
) -> Optional[Dict[str, object]]:
    print(f"[详情] 正在抓取: {url}")
    if not fetch_with_retry(driver, url):
        return None

    content_type = detect_content_type(url)

    title = pick_text(
        driver,
        [
            "h1.Post-Title",
            "h1.QuestionHeader-title",
            "h1",
            "title",
        ],
    )

    # Prefer answer body for Q&A pages.
    content = pick_text(
        driver,
        [
            ".AnswerItem .RichContent-inner",
            ".AnswerCard .RichContent-inner",
            ".RichText.ztext",
            ".Post-RichTextContainer",
            ".QuestionRichText",
            ".ContentItem .RichText",
        ],
    )

    if not content:
        content = pick_text(driver, ["body"])
    content = re.sub(r"\s+", " ", content.replace("\n", " ")).strip()

    answer_time_text = pick_time_text(driver, content_type)
    answer_date = parse_date_from_text(answer_time_text)
    if not answer_date:
        return None

    period = judge_period(answer_date)
    if not period:
        print(f"[跳过] 时间窗口外: {url} | 日期: {answer_date}")
        return None

    # 等待点赞数元素出现，最多等10秒
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".VoteButton, .Button--plain, [class*='voteCount']")
            )
        )
    except Exception:
        pass

    print("[调试] page_source片段:")
    print(driver.page_source[:2000])
    engagement = extract_likes_comments(driver, driver.page_source)

    record = {
        "title": title,
        "content": content,
        "answer_created_time": answer_date.isoformat(),
        "likes": engagement["likes"],
        "comments": engagement["comments"],
        "url": url,
        "content_type": content_type,
        "search_query": query,
        "query_type": query_type,
        "query_type_weight": query_type_weight,
        "period": period,
        "crawl_time": datetime.now().isoformat(timespec="seconds"),
    }
    print(f"[成功] 写入记录: {url}")
    return record


def extract_result_urls(driver: webdriver.Chrome) -> List[str]:
    urls: List[str] = []

    card_selectors = [
        "div.SearchResult-Card a[href]",
        "div.ContentItem a[href]",
        "div.List-item a[href]",
    ]

    for selector in card_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []

        for element in elements:
            href = (element.get_attribute("href") or "").strip()
            if not href:
                continue
            if "zhihu.com" not in href:
                continue
            if "/search?" in href:
                continue

            clean_href = href.split("?")[0]
            if clean_href not in urls:
                urls.append(clean_href)

    if urls:
        return urls

    try:
        fallback_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='zhihu.com']")
    except Exception:
        fallback_elements = []

    for element in fallback_elements:
        href = (element.get_attribute("href") or "").strip()
        if not href or "/search?" in href:
            continue
        clean_href = href.split("?")[0]
        if clean_href not in urls:
            urls.append(clean_href)

    return urls


def collect_query_records(
    driver: webdriver.Chrome,
    query: str,
    query_type: str,
    query_type_weight: float,
    max_items: int = MAX_ITEMS_PER_QUERY,
) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    seen_urls = set()

    for page in range(1, 6):
        if len(seen_urls) >= max_items:
            break

        search_url = f"https://www.zhihu.com/search?type=content&q={quote(query)}&page={page}"
        ok = fetch_with_retry(driver, search_url)
        if not ok:
            continue

        candidate_urls = extract_result_urls(driver)

        for url in candidate_urls:
            if len(seen_urls) >= max_items:
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)
            print(f"[采集] query={query} | 已找到URL: {len(seen_urls)}")

    for url in list(seen_urls)[:max_items]:
        record = parse_detail_page(driver, url, query, query_type, query_type_weight)
        if record:
            records.append(record)

    return records


def append_to_csv(records: List[Dict[str, object]]) -> None:
    if not records:
        return

    fieldnames = [
        "title",
        "content",
        "answer_created_time",
        "likes",
        "comments",
        "url",
        "content_type",
        "search_query",
        "query_type",
        "query_type_weight",
        "period",
        "crawl_time",
    ]

    file_exists = OUTPUT_FILE.exists()
    with OUTPUT_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(records)


def main(test_mode: bool = False) -> None:
    ensure_directories()
    queries = build_queries()
    if test_mode:
        queries = queries[:1]

    driver = init_driver()
    all_records: List[Dict[str, object]] = []

    try:
        for query_cfg in queries:
            query = str(query_cfg["search_query"])
            query_type = str(query_cfg["query_type"])
            query_type_weight = float(query_cfg["query_type_weight"])
            max_items = 3 if test_mode else MAX_ITEMS_PER_QUERY

            query_records = collect_query_records(driver, query, query_type, query_type_weight, max_items=max_items)
            all_records.extend(query_records)
            if test_mode:
                for idx, record in enumerate(query_records, start=1):
                    print(f"[测试记录 {idx}]")
                    for key, value in record.items():
                        print(f"{key}: {value}")

        append_to_csv(all_records)
    finally:
        driver.quit()


if __name__ == "__main__":
    main(test_mode=False)
