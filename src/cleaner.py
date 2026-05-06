import csv
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"

PLATFORM_CONFIGS = [
    {
        "name": "zhihu",
        "raw_path": RAW_DIR / "zhihu_raw.csv",
        "cleaned_path": CLEANED_DIR / "zhihu_cleaned.csv",
        "min_content_length": 100,
        "require_title": False,
    },
    {
        "name": "reddit",
        "raw_path": RAW_DIR / "reddit_raw.csv",
        "cleaned_path": CLEANED_DIR / "reddit_cleaned.csv",
        "min_content_length": 20,
        "require_title": False,
    },
    {
        "name": "weibo",
        "raw_path": RAW_DIR / "weibo_raw.csv",
        "cleaned_path": CLEANED_DIR / "weibo_cleaned.csv",
        "min_content_length": 10,
        "require_title": False,
    },
    {
        "name": "xhs",
        "raw_path": RAW_DIR / "xhs_raw.csv",
        "cleaned_path": CLEANED_DIR / "xhs_cleaned.csv",
        "min_content_length": 15,
        "require_title": True,
    },
]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def safe_int(value: object) -> int:
    try:
        return int(float(str(value or 0).strip()))
    except (TypeError, ValueError):
        return 0


def read_csv_rows(path: Path) -> tuple[list[dict], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, fieldnames


def write_csv_rows(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
        writer.writerows(rows)


def apply_common_prep(rows: list[dict]) -> list[dict]:
    prepared: list[dict] = []
    for row in rows:
        new_row = dict(row)
        new_row["content"] = normalize_space(new_row.get("content") or "")
        prepared.append(new_row)
    return prepared


def dedupe_zhihu_rows(rows: list[dict]) -> list[dict]:
    scored_rows: list[dict] = []
    for row in rows:
        new_row = dict(row)
        query_type = (new_row.get("query_type") or "").strip()
        priority = (
            {"experience": 4, "business": 3, "feature": 2, "version": 1}.get(query_type, 0) * 10
            + safe_int(new_row.get("likes"))
            + safe_int(new_row.get("comments")) * 2
        )
        new_row["_priority"] = priority
        scored_rows.append(new_row)

    dedup_map: dict[str, dict] = {}
    passthrough_rows: list[dict] = []
    for row in scored_rows:
        url = (row.get("url") or "").strip()
        if not url:
            passthrough_rows.append(row)
            continue

        current = dedup_map.get(url)
        if current is None or safe_int(row.get("_priority")) > safe_int(current.get("_priority")):
            dedup_map[url] = row

    result = list(dedup_map.values()) + passthrough_rows
    for row in result:
        row.pop("_priority", None)
    return result


def dedupe_reddit_rows(rows: list[dict]) -> list[dict]:
    seen_title_content: set[tuple[str, str]] = set()
    title_content_deduped: list[dict] = []
    for row in rows:
        key = (
            normalize_space(row.get("title") or ""),
            normalize_space(row.get("content") or ""),
        )
        if key in seen_title_content:
            continue
        seen_title_content.add(key)
        title_content_deduped.append(dict(row))

    seen_urls: set[str] = set()
    url_deduped: list[dict] = []
    for row in title_content_deduped:
        url = (row.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(row)

    return url_deduped


def dedupe_by_url_keep_first(rows: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        url = (row.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduped.append(dict(row))
    return deduped


def filter_rows(rows: list[dict], min_content_length: int, require_title: bool, platform_name: str) -> list[dict]:
    filtered: list[dict] = []
    for row in rows:
        title = normalize_space(row.get("title") or "")
        content = normalize_space(row.get("content") or "")

        if require_title and not title:
            continue

        if platform_name == "xhs":
            content_clean = compact_text(content)
        else:
            content_clean = compact_text(content)

        if len(content_clean) < min_content_length:
            continue

        filtered.append(dict(row))

    return filtered


def filter_weibo_keywords(rows: list[dict]) -> list[dict]:
    keywords = ["kimi", "k2.6", "月之暗面", "moonshot", "k2", "大模型"]
    filtered: list[dict] = []
    for row in rows:
        content = normalize_space(row.get("content") or "").lower()
        if any(keyword in content for keyword in keywords):
            filtered.append(dict(row))
    print(f"[weibo] 关键词过滤后: {len(filtered)}")
    return filtered


def print_stats(platform_name: str, before_count: int, rows: list[dict]) -> None:
    print(f"[{platform_name}] 清洗前: {before_count} -> 清洗后: {len(rows)}")
    unique_urls = len({(row.get('url') or '').strip() for row in rows if (row.get('url') or '').strip()})
    print(f"[{platform_name}] unique urls: {unique_urls}")

    period_counter = Counter((row.get("period") or "").strip() for row in rows)
    print(f"[{platform_name}] period分布:")
    for key in ["baseline", "post_launch"]:
        print(f"{key}: {period_counter.get(key, 0)}")

    query_type_counter = Counter((row.get("query_type") or "").strip() for row in rows)
    print(f"[{platform_name}] query_type分布:")
    for key in ["experience", "business", "feature", "version", "comparison"]:
        print(f"{key}: {query_type_counter.get(key, 0)}")


def clean_platform(config: dict) -> None:
    raw_path: Path = config["raw_path"]
    cleaned_path: Path = config["cleaned_path"]
    platform_name: str = config["name"]
    min_content_length: int = config["min_content_length"]
    require_title: bool = config["require_title"]

    if not raw_path.exists():
        print(f"[{platform_name}] 原始文件不存在: {raw_path}")
        return

    rows, fieldnames = read_csv_rows(raw_path)
    before_count = len(rows)

    rows = apply_common_prep(rows)

    if platform_name == "zhihu":
        rows = dedupe_zhihu_rows(rows)
    elif platform_name == "reddit":
        rows = dedupe_reddit_rows(rows)
    else:
        rows = dedupe_by_url_keep_first(rows)

    rows = filter_rows(rows, min_content_length=min_content_length, require_title=require_title, platform_name=platform_name)
    if platform_name == "weibo":
        rows = filter_weibo_keywords(rows)

    write_csv_rows(cleaned_path, rows, fieldnames)
    print_stats(platform_name, before_count, rows)
    print(f"[{platform_name}] 输出: {cleaned_path}")


def clean_raw_data() -> None:
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    for config in PLATFORM_CONFIGS:
        clean_platform(config)


if __name__ == "__main__":
    clean_raw_data()
