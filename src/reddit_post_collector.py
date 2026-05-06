import csv
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "reddit_raw.csv"
CHROME_DRIVER_VERSION = "140"

POST_URLS = [
    "https://www.reddit.com/r/LocalLLaMA/comments/1sr8p49/kimi_k26_is_a_legit_opus_47_replacement/",
    "https://www.reddit.com/r/kimi/comments/1srin2s/whats_the_cheapest_way_to_access_kimi_k26_right/",
    "https://www.reddit.com/r/opencodeCLI/comments/1sruhrf/glm_and_kimi_vs_gpt_and_claude/",
    "https://www.reddit.com/r/kimi/comments/1ss20n6/where_to_buy_kimi_k26_ollama_vs_kimi_coding_plan/",
    "https://www.reddit.com/r/SillyTavernAI/comments/1sr2rjd/is_kimi_26_better_than_glm_51_in_rp/",
    "https://www.reddit.com/r/kimi/comments/1squ19o/cant_decide_between_codexclaude_and_kimi_plans/",
    "https://www.reddit.com/r/LocalLLaMA/comments/1sroy61/kimi_k26_as_a_replacement_for_opus_47_testing/",
    "https://www.reddit.com/r/SillyTavernAI/comments/1sreyog/kimi_26_isnt_really_worth_it/",
    "https://www.reddit.com/r/ClaudeCode/comments/1st91os/kimi_k26_is_not_an_opus_replacement_or_alternative/",
    "https://www.reddit.com/r/opencodeCLI/comments/1so29o0/kimi_k26_in_opencode_is_actually_really_damn_good/",
    "https://www.reddit.com/r/kimi/comments/1srgu3e/claude_vs_kimi/",
    "https://www.reddit.com/r/vibecoding/comments/1sslvq5/deepseek_kimi_vs_opus_47_vs_gemini_31_pro/",
    "https://www.reddit.com/r/LocalLLaMA/comments/1srd2cc/opus_47_max_subscriber_switching_to_kimi_26/",
    "https://www.reddit.com/r/kimi/comments/1so43we/kimi_26_performance/",
    "https://www.reddit.com/r/google_antigravity/comments/1srytse/kimi_26_is_needed_here_its_way_cheaper_than/",
    "https://www.reddit.com/r/singularity/comments/1sqsvrt/kimi_26_has_been_released/",
    "https://www.reddit.com/r/ollama/comments/1sr6f1j/kimi_k26_is_now_available_on_ollama_cloud/",
    "https://www.reddit.com/r/LocalLLaMA/comments/1sno8ba/kimi_k26codepreview_opus_47_glm_51_minimax_m27/",
    "https://www.reddit.com/r/kimi/comments/1slymvf/is_k26_overthinking/",
    "https://www.reddit.com/r/LocalLLM/comments/1ssc8lr/kimi_k26_what_hardware_do_i_need_to_run_it_locally/",
    "https://www.reddit.com/r/singularity/comments/1srhf2h/kimi_k26_lands_at_4_on_the_artificial_analysis/",
    "https://www.reddit.com/r/kimi/comments/1srsnv4/fireworks_k26_is_more_than_2x_faster_than/",
    "https://www.reddit.com/r/opencodeCLI/comments/1sr5jlj/k26_or_glm_51_which_model_is_better/",
    "https://www.reddit.com/r/LocalLLaMA/comments/1srs4uj/differences_between_kimi_k25_and_kimi_k26_on/",
    "https://www.reddit.com/r/opencodeCLI/comments/1srq7ot/go_plan_or_ollama_cloud_for_kimi_k26/",
    "https://www.reddit.com/r/SillyTavernAI/comments/1sqtcai/kimi_k26_released/",
    "https://www.reddit.com/r/LocalLLaMA/comments/1srxfdh/kimi_k26_unsloth_gguf_is_out/",
    "https://www.reddit.com/r/kimi/comments/1ssk6ii/kimi_k26_for_rust/",
]

POST_URLS = list(dict.fromkeys(POST_URLS))

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


def extract_subreddit(url: str) -> str:
    match = re.search(r"reddit\.com/r/([^/]+)", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def clean_title(page_title: str, subreddit: str) -> str:
    title = (page_title or "").strip()
    if not title:
        return ""

    if subreddit:
        suffix_pattern = rf"\s*:\s*r/{re.escape(subreddit)}\s*$"
        title = re.sub(suffix_pattern, "", title, flags=re.IGNORECASE)

    title = re.sub(r"\s*:\s*reddit\s*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def dedupe_texts(texts: List[str]) -> List[str]:
    seen: set[str] = set()
    cleaned: List[str] = []

    for text in texts:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    return cleaned


def extract_first_text(driver: webdriver.Chrome, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []

        for element in elements:
            text = re.sub(r"\s+", " ", (element.text or "").strip())
            if text:
                return text
    return ""


def extract_all_texts(driver: webdriver.Chrome, selectors: List[str]) -> List[str]:
    texts: List[str] = []

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []

        for element in elements:
            text = re.sub(r"\s+", " ", (element.text or "").strip())
            if text:
                texts.append(text)

    return dedupe_texts(texts)


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


def collect_post_records(driver: webdriver.Chrome, post_url: str) -> List[dict]:
    subreddit = extract_subreddit(post_url)
    crawl_time = datetime.now().isoformat(timespec="seconds")
    answer_created_time = datetime.now().strftime("%Y-%m-%d")

    driver.get(post_url)
    time.sleep(5)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)

    title = clean_title(driver.title, subreddit)
    content = extract_first_text(
        driver,
        [
            "[data-testid='post-container']",
            ".Post",
            "shreddit-post",
        ],
    )
    if not content:
        content = title

    comment_texts = extract_all_texts(
        driver,
        [
            "[data-testid='comment']",
            "shreddit-comment",
            ".Comment",
        ],
    )

    base_record = {
        "title": title,
        "answer_created_time": answer_created_time,
        "likes": 0,
        "comments": 0,
        "subreddit": subreddit,
        "search_query": "manual_collection",
        "query_type": "experience",
        "query_type_weight": 1.0,
        "source": "reddit",
        "period": "post_launch",
        "crawl_time": crawl_time,
    }

    rows: List[dict] = [
        {
            **base_record,
            "content": content,
            "url": post_url,
            "content_type": "reddit_post",
        }
    ]

    for comment_text in comment_texts:
        rows.append(
            {
                **base_record,
                "title": title,
                "content": comment_text,
                "url": post_url,
                "content_type": "reddit_comment",
            }
        )

    return rows


def collect_posts() -> None:
    driver = init_driver()

    try:
        for post_url in POST_URLS:
            try:
                rows = collect_post_records(driver, post_url)
                append_rows(rows)
                print(f"{post_url}: collected {len(rows)} rows")
            except WebDriverException as exc:
                print(f"{post_url}: selenium failed - {exc}")
            except Exception as exc:
                print(f"{post_url}: parse failed - {exc}")

            time.sleep(random.uniform(1, 2))
    finally:
        driver.quit()


if __name__ == "__main__":
    collect_posts()
