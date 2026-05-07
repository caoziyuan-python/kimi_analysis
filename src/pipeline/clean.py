from __future__ import annotations

import re

import pandas as pd


MIN_CONTENT_LENGTH_BY_PLATFORM = {
    "zhihu": 100,
    "reddit": 20,
    "hackernews": 20,
    "weibo": 10,
    "xiaohongshu": 15,
    "xhs": 15,
}

REQUIRE_TITLE_PLATFORMS = {"xiaohongshu", "xhs"}
WEIBO_KEYWORDS = ["kimi", "k2.6", "月之暗面", "moonshot", "k2", "大模型"]
MONITORING_PLATFORMS = {"reddit", "hackernews", "github"}
PRODUCT_STRONG_KEYWORDS = [
    "kimi",
    "moonshot",
    "月之暗面",
]
PRODUCT_K2_PATTERNS = [
    r"\bk2\.6\b",
    r"\bk\s*2\.6\b",
    r"\bkimi[-\s]?k2\b",
    r"\bkimi[-\s]?2\.6\b",
]
PRODUCT_K2_CONTEXT_KEYWORDS = [
    "kimi",
    "moonshot",
    "llm",
    "ai",
    "model",
    "coding",
    "agent",
    "chatbot",
    "ollama",
]


def normalize_space(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def compact_text(text: object) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def safe_int(value: object) -> int:
    try:
        return int(float(str(value or 0).strip()))
    except (TypeError, ValueError):
        return 0


def _platform(row: pd.Series) -> str:
    value = row.get("platform", "") or row.get("source", "") or ""
    platform = normalize_space(value).lower()
    return "xiaohongshu" if platform == "xhs" else platform


def _dedupe_zhihu(df: pd.DataFrame) -> pd.DataFrame:
    if "url" not in df.columns:
        return df

    work = df.copy()
    query_type = work.get("query_type", pd.Series("", index=work.index)).fillna("")
    priority = query_type.map({"experience": 4, "business": 3, "feature": 2, "version": 1}).fillna(0) * 10
    likes = work["likes"].map(safe_int) if "likes" in work.columns else pd.Series(0, index=work.index)
    comments = work["comments"].map(safe_int) if "comments" in work.columns else pd.Series(0, index=work.index)
    priority += likes
    priority += comments * 2
    work["_priority"] = priority
    work = work.sort_values("_priority", ascending=False)
    return work.drop_duplicates(subset=["url"], keep="first").drop(columns=["_priority"])


def _dedupe_reddit(df: pd.DataFrame) -> pd.DataFrame:
    columns = [column for column in ["title", "content"] if column in df.columns]
    work = df.drop_duplicates(subset=columns, keep="first") if columns else df
    if "url" in work.columns:
        work = work.drop_duplicates(subset=["url"], keep="first")
    return work


def _dedupe_default(df: pd.DataFrame) -> pd.DataFrame:
    if "url" not in df.columns:
        return df.drop_duplicates()
    return df.drop_duplicates(subset=["url"], keep="first")


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for platform, group in df.groupby("_platform", dropna=False, sort=False):
        if platform == "zhihu":
            frames.append(_dedupe_zhihu(group))
        elif platform == "reddit":
            frames.append(_dedupe_reddit(group))
        else:
            frames.append(_dedupe_default(group))
    return pd.concat(frames, ignore_index=True) if frames else df.iloc[0:0].copy()


def _passes_platform_filters(row: pd.Series) -> bool:
    platform = str(row.get("_platform") or "")
    title = normalize_space(row.get("title") or "")
    content = normalize_space(row.get("content") or "")
    url = normalize_space(row.get("url") or "")

    if platform in REQUIRE_TITLE_PLATFORMS and not title:
        return False

    min_length = MIN_CONTENT_LENGTH_BY_PLATFORM.get(platform, 20)
    if len(compact_text(content)) < min_length:
        return False

    if platform == "weibo":
        lowered = content.lower()
        return any(keyword in lowered for keyword in WEIBO_KEYWORDS)

    if platform in MONITORING_PLATFORMS and not _is_product_relevant(f"{title} {content} {url}"):
        return False

    return True


def _is_product_relevant(text: str) -> bool:
    lowered = normalize_space(text).lower()
    compacted = compact_text(lowered)
    if any(keyword in lowered for keyword in PRODUCT_STRONG_KEYWORDS):
        return True

    if any(re.search(pattern, lowered) for pattern in PRODUCT_K2_PATTERNS):
        return True

    has_k2 = bool(re.search(r"\bk2\b", lowered)) or "k2" in compacted
    if not has_k2:
        return False

    return any(keyword in lowered for keyword in PRODUCT_K2_CONTEXT_KEYWORDS)


def clean(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df.empty:
        return raw_df.copy()

    df = raw_df.copy()
    if "content" not in df.columns:
        raise ValueError("raw_df must include a content column")

    df["content"] = df["content"].map(normalize_space)
    if "title" in df.columns:
        df["title"] = df["title"].map(normalize_space)

    df["_platform"] = df.apply(_platform, axis=1)
    df = _dedupe(df)
    df = df[df.apply(_passes_platform_filters, axis=1)].copy()
    df["platform"] = df["_platform"]
    return df.drop(columns=["_platform"]).reset_index(drop=True)
