import csv
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
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "xhs_raw.csv"
CHROME_DRIVER_VERSION = "140"
TODAY = "2026-04-23"
LOCAL_CHROMEDRIVER = Path.home() / ".wdm" / "drivers" / "chromedriver" / "win64" / "140" / "chromedriver-win32" / "chromedriver.exe"

POST_URLS = [
    ("https://www.xiaohongshu.com/explore/69de6b41000000002300771d?xsec_token=AB0qKNX7PZxVWpVxaMV7fJFnP01E63hBVK-DPACzEG6UA=&xsec_source=pc_search&source=web_note_detail_r10", "kimi2.6好用吗", "experience"),
    ("https://www.xiaohongshu.com/explore/69dcc37600000000200381c4?xsec_token=AB14iaNaPrjlODOyktCUWvQSesAwNJexAVYW7lmfiAp-I=&xsec_source=pc_search&source=web_note_detail_r10", "kimi2.6好用吗", "experience"),
    ("https://www.xiaohongshu.com/explore/69e6cf810000000021038551?xsec_token=ABlDAwrR6BzacCB4gvPJROMPszJyfgLWV1lLcn5kfWLY0=&xsec_source=pc_search&source=web_note_detail_r10", "kimi2.6好用吗", "experience"),
    ("https://www.xiaohongshu.com/explore/69e1831f000000001f0029aa?xsec_token=ABgvXKKtdyH_9PeXDqOyw0rw7iikUdql1LvWfAuES8D2U=&xsec_source=pc_search&source=web_note_detail_r10", "kimi2.6好用吗", "experience"),
    ("https://www.xiaohongshu.com/explore/69dde5f8000000001a03657b?xsec_token=ABEF47bwcpN2MWI2IrnWQtoxtcqoU86Mj1fmqlQSAx2ps=&xsec_source=pc_search&source=web_note_detail_r10", "kimi2.6好用吗", "experience"),
    ("https://www.xiaohongshu.com/explore/69de1a69000000002200ce87?xsec_token=AB0qKNX7PZxVWpVxaMV7fJFhbF3Auj8jQVhx6ENIXoLlU=&xsec_source=pc_search&source=web_note_detail_r10", "kimi2.6好用吗", "experience"),
    ("https://www.xiaohongshu.com/explore/69e6519f0000000021007841?xsec_token=ABlDAwrR6BzacCB4gvPJROMPQkXJf-z-7JlC4l_UII_1I=&xsec_source=pc_search&source=web_note_detail_r10", "kimi2.6好用吗", "experience"),
    ("https://www.xiaohongshu.com/explore/69dfa7a4000000002200d109?xsec_token=ABSB65ZLoj_0d4pJ62TgIqZBPPrKzO506sBwdhCFsEnFU=&xsec_source=pc_search&source=web_note_detail_r10", "kimi2.6好用吗", "experience"),
    ("https://www.xiaohongshu.com/explore/69e760ca000000002103b3f9?xsec_token=AB_6hUBIMJ3LrfGVe4U8b-xS-PnSCvWljTFN7aDQXtBKk=&xsec_source=pc_search&source=web_search_result_notes", "kimi2.6怎么用", "feature"),
    ("https://www.xiaohongshu.com/explore/69e65e1c000000001a02a0a5?xsec_token=ABlDAwrR6BzacCB4gvPJROMHuxBAH4eI11BvNIbkH4Y7s=&xsec_source=pc_search&source=web_search_result_notes", "kimi2.6怎么用", "feature"),
    ("https://www.xiaohongshu.com/explore/69dde5f8000000001a03657b?xsec_token=ABEF47bwcpN2MWI2IrnWQtoxtcqoU86Mj1fmqlQSAx2ps=&xsec_source=pc_search&source=web_search_result_notes", "kimi2.6怎么用", "feature"),
    ("https://www.xiaohongshu.com/explore/69e678f3000000001f00062f?xsec_token=ABlDAwrR6BzacCB4gvPJROME95kz3yIiVrrdJbNKpSOvc=&xsec_source=pc_search&source=web_search_result_notes", "kimi2.6怎么用", "feature"),
    ("https://www.xiaohongshu.com/explore/69e6dee2000000000803da57?xsec_token=ABlDAwrR6BzacCB4gvPJROMPU8j78qhIgi5V1C6t8lZCQ=&xsec_source=pc_search&source=web_search_result_notes", "kimi2.6怎么用", "feature"),
    ("https://www.xiaohongshu.com/explore/69e64d82000000001f00063f?xsec_token=ABlDAwrR6BzacCB4gvPJROMAjEWAa4Pgtfk907wD8sVoI=&xsec_source=pc_search&source=web_search_result_notes", "kimi multiagent", "feature"),
    ("https://www.xiaohongshu.com/explore/69e8ca88000000001e00c605?xsec_token=AB_y3ixjVvOs9xQY5I-HdbR4ESzucBuHR1qs1jn8EeR0g=&xsec_source=pc_search&source=web_search_result_notes", "kimi token", "business"),
    ("https://www.xiaohongshu.com/explore/69e371c1000000002100497a?xsec_token=ABNa7MrUcKe8oY4Yve7U0qcw2MXChuuMlm-o-XE1goO50=&xsec_source=pc_search&source=web_search_result_notes", "kimi token", "business"),
    ("https://www.xiaohongshu.com/explore/69e1ccf30000000023025533?xsec_token=ABgvXKKtdyH_9PeXDqOyw0rw0091FXY_32kZDvcmv1Bws=&xsec_source=pc_search&source=web_search_result_notes", "kimi token", "business"),
    ("https://www.xiaohongshu.com/explore/69e441b000000000210134c9?xsec_token=ABpwpaJdDxM6rNupSRwTV0_Pq1s_MPdLkyrp5F-Gt9Sjg=&xsec_source=pc_search&source=web_search_result_notes", "kimi token", "business"),
    ("https://www.xiaohongshu.com/explore/69e836a00000000021010aff?xsec_token=AB_y3ixjVvOs9xQY5I-HdbRxUV_Ae1TTVwUUGsVD6RFBA=&xsec_source=pc_search&source=web_search_result_notes", "kimi token", "business"),
    ("https://www.xiaohongshu.com/explore/69e85145000000002301d51c?xsec_token=AB_y3ixjVvOs9xQY5I-HdbRyZ4KFFbNL7Lzj6fFteF0Uc=&xsec_source=pc_search&source=web_search_result_notes", "kimi vibecoding", "feature"),
    ("https://www.xiaohongshu.com/explore/69e678f3000000001f00062f?xsec_token=ABlDAwrR6BzacCB4gvPJROME95kz3yIiVrrdJbNKpSOvc=&xsec_source=pc_search&source=web_search_result_notes", "agent怎么开", "feature"),
    ("https://www.xiaohongshu.com/explore/69e1831f000000001f0029aa?xsec_token=ABgvXKKtdyH_9PeXDqOyw0rw7iikUdql1LvWfAuES8D2U=&xsec_source=pc_search&source=web_search_result_notes", "agent怎么开", "feature"),
    ("https://www.xiaohongshu.com/explore/69e65e1c000000001a02a0a5?xsec_token=ABlDAwrR6BzacCB4gvPJROMHuxBAH4eI11BvNIbkH4Y7s=&xsec_source=pc_search&source=web_search_result_notes", "agent怎么开", "feature"),
    ("https://www.xiaohongshu.com/explore/69e95cd3000000001a02603e?xsec_token=ABQ7DhK3zZzcpqtmYPa_EuWwCuph8W2_N7jKlZ2jSSxDM=&xsec_source=pc_search&source=web_search_result_notes", "kimi额度套餐", "business"),
    ("https://www.xiaohongshu.com/explore/69e836a00000000021010aff?xsec_token=AB_y3ixjVvOs9xQY5I-HdbRxUV_Ae1TTVwUUGsVD6RFBA=&xsec_source=pc_search&source=web_search_result_notes", "kimi额度套餐", "business"),
    ("https://www.xiaohongshu.com/explore/69e39a450000000023013ffb?xsec_token=ABNa7MrUcKe8oY4Yve7U0qc65GBCUEMbOPIy4tmj8KoSQ=&xsec_source=pc_search&source=web_search_result_notes", "kimi额度套餐", "business"),
    ("https://www.xiaohongshu.com/explore/69e4f7eb00000000230218a2?xsec_token=ABpwpaJdDxM6rNupSRwTV0_LsJWinyqJHyqq_JCwedoG8=&xsec_source=pc_search&source=web_search_result_notes", "kimi额度套餐", "business"),
    ("https://www.xiaohongshu.com/explore/69e0dfdc0000000021004884?xsec_token=ABB-sv1l_3PFuO1ZB2qEN1SyOpCwtKypLnLoaXo-uJcuY=&xsec_source=pc_search&source=web_search_result_notes", "kimi降智", "experience"),
    ("https://www.xiaohongshu.com/explore/69e2b71f000000001b003e6c?xsec_token=ABNGqUuqKlwGNyEO_PRng3-TNNQA3HYbcxHhDW7IUFfag=&xsec_source=pc_search&source=web_search_result_notes", "kimi降智", "experience"),
    ("https://www.xiaohongshu.com/explore/69e9934c0000000023004705?xsec_token=ABQ7DhK3zZzcpqtmYPa_EuW3xwAzIqp3qzi8-wKVjlp48=&xsec_source=pc_search&source=web_search_result_notes", "kimi降智", "experience"),
    ("https://www.xiaohongshu.com/explore/69e87367000000002103a9c4?xsec_token=AB_y3ixjVvOs9xQY5I-HdbR_lS32Rgj6DQDF3zQwETDbE=&xsec_source=pc_search&source=web_search_result_notes", "kimi不如GLM", "experience"),
    ("https://www.xiaohongshu.com/explore/69e6c3b1000000002102fd8f?xsec_token=ABlDAwrR6BzacCB4gvPJROMJteBuur6uAO_PrA2WgRq6M=&xsec_source=pc_search&source=web_search_result_notes", "kimi不如GLM", "experience"),
    ("https://www.xiaohongshu.com/explore/69e7488d000000001a0356cc?xsec_token=AB_6hUBIMJ3LrfGVe4U8b-xcXHeljWQJE5SSk9JrundP4=&xsec_source=pc_search&source=web_search_result_notes", "kimi不如GLM", "experience"),
    ("https://www.xiaohongshu.com/explore/69e9e5d40000000012029804?xsec_token=ABQ7DhK3zZzcpqtmYPa_EuWxL9ufcVGzpspx07gwLVIYI=&xsec_source=pc_search&source=web_search_result_notes", "kimi不如GLM", "experience"),
    ("https://www.xiaohongshu.com/explore/69e72b51000000002003a174?xsec_token=AB_6hUBIMJ3LrfGVe4U8b-xbXUKQ-ySQKy2__kYE9Y_nw=&xsec_source=pc_search&source=web_search_result_notes", "kimi不如GLM", "experience"),
    ("https://www.xiaohongshu.com/explore/69e78abb00000000230060c3?xsec_token=AB_6hUBIMJ3LrfGVe4U8b-xYLLo48JW4d4EwAKP0-Yyu4=&xsec_source=pc_search&source=web_search_result_notes", "kimi不如GLM", "experience"),
    ("https://www.xiaohongshu.com/explore/69e6f69e000000001b003710?xsec_token=ABlDAwrR6BzacCB4gvPJROMONhTeXYQSys10vAPKF8-Uk=&xsec_source=pc_search&source=web_search_result_notes", "kimi不如GLM", "experience"),
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
        if LOCAL_CHROMEDRIVER.exists():
            service = Service(str(LOCAL_CHROMEDRIVER))
        else:
            service = Service(ChromeDriverManager(driver_version=CHROME_DRIVER_VERSION).install())
    except Exception:
        service = Service(ChromeDriverManager(driver_version=CHROME_DRIVER_VERSION).install())

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(35)
    return driver


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


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


def extract_first_text(driver: webdriver.Chrome, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []

        for element in elements:
            text = normalize_space(element.text)
            if text:
                return text
    return ""


def dedupe_texts(texts: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []

    for text in texts:
        normalized = normalize_space(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    return result


def extract_comment_texts(driver: webdriver.Chrome) -> List[str]:
    selectors = [
        ".comment-item:not(.comment-item-sub) .content",
        ".comment-item:not(.comment-item-sub)",
    ]
    texts: List[str] = []

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []

        for element in elements:
            text = normalize_space(element.text)
            if text:
                texts.append(text)

    return dedupe_texts(texts)


def collect_post_comments(driver: webdriver.Chrome, post_url: str, search_query: str, query_type: str) -> List[dict]:
    driver.get(post_url)
    time.sleep(8)

    post_content = extract_first_text(
        driver,
        [
            "#detail-desc",
            ".note-content",
            ".content",
        ],
    )
    title = normalize_space(post_content[:30]) if post_content else "小红书笔记评论"

    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(2)

    script = """
    var results = [];
    var all = document.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
        var el = all[i];
        var style = window.getComputedStyle(el);
        var overflow = style.overflow + style.overflowY;
        if ((overflow.includes('scroll') || overflow.includes('auto'))
           && el.scrollHeight > el.clientHeight) {
            results.push(el.className + ' | scrollHeight:' + el.scrollHeight);
        }
    }
    return results.slice(0, 15);
    """
    scrollable = driver.execute_script(script)
    for item in scrollable:
        print("可滚动:", item)

    all_comments: set[str] = set()
    previous_count = 0
    no_change_count = 0
    for i in range(80):
        try:
            result = driver.execute_script(
                """
                var el = document.querySelector('.note-scroller');
                if (el) {
                    el.scrollTop += 600;
                    return 'scrollTop:' + el.scrollTop + ' scrollHeight:' + el.scrollHeight;
                }
                return 'element not found';
                """
            )
            print(f"滚动结果: {result}")
            time.sleep(3)

            elements = driver.find_elements(By.CSS_SELECTOR, ".comment-item:not(.comment-item-sub)")
            for element in elements:
                text = normalize_space(element.text)
                if text and len(text) > 5:
                    all_comments.add(text)

            print(f"第{i + 1}次，累计收集: {len(all_comments)}条")

            if i > 5 and len(all_comments) == previous_count:
                no_change_count += 1
            else:
                no_change_count = 0

            if no_change_count >= 5:
                break
            previous_count = len(all_comments)
        except Exception as exc:
            print(f"异常: {exc}")

    elements = driver.find_elements(By.XPATH, "//*[contains(@class,'comment')]")
    for element in elements[:10]:
        print(element.get_attribute("class"), "|", normalize_space(element.text)[:50])

    comment_texts = list(all_comments)
    crawl_time = datetime.now().isoformat(timespec="seconds")

    rows: List[dict] = []
    for index, comment_text in enumerate(comment_texts, start=1):
        rows.append(
            {
                "title": title,
                "content": comment_text,
                "answer_created_time": TODAY,
                "likes": 0,
                "comments": 0,
                "url": f"{post_url}#comment_{index}",
                "content_type": "xhs_comment",
                "subreddit": "xiaohongshu",
                "search_query": search_query,
                "query_type": query_type,
                "query_type_weight": 1.0,
                "source": "xhs",
                "period": "post_launch",
                "crawl_time": crawl_time,
            }
        )

    return rows


def collect_xhs_posts() -> None:
    ensure_output_dir()
    driver = init_driver()

    try:
        for post_url, search_query, query_type in POST_URLS:
            try:
                rows = collect_post_comments(driver, post_url, search_query, query_type)
                append_rows(rows)
                print(f"{post_url}: collected {len(rows)} comments")
            except WebDriverException as exc:
                print(f"{post_url}: selenium failed - {exc}")
            except Exception as exc:
                print(f"{post_url}: parse failed - {exc}")
    finally:
        driver.quit()


if __name__ == "__main__":
    collect_xhs_posts()
