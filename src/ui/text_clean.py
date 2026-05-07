from __future__ import annotations

import re


REDDIT_UI_WORDS = [
    "返回",
    "转到",
    "关注帖子",
    "保存",
    "隐藏",
    "举报",
    "回复",
    "分享",
    "排序方式",
]
MEDIA_URL_PATTERN = re.compile(
    r"https?://(?:preview\.redd\.it|i\.redd\.it|external-preview\.redd\.it|v\.redd\.it|imgur\.com|i\.imgur\.com)"
    r"/[^\s)>\]]+",
    flags=re.IGNORECASE,
)
REDDIT_RSS_FOOTER_PATTERN = re.compile(
    r"\s*submitted\s+by\s+/u/[A-Za-z0-9_-]+"
    r"(?:\s+to\s+r/[A-Za-z0-9_]+)?"
    r"(?:\s+\[[^\]]+\])*"
    r"\s*$",
    flags=re.IGNORECASE,
)
MARKDOWN_MEDIA_PATTERN = re.compile(
    r"!\[[^\]]*\]\("
    r"https?://(?:preview\.redd\.it|i\.redd\.it|external-preview\.redd\.it|v\.redd\.it|imgur\.com|i\.imgur\.com)"
    r"/[^)]+"
    r"\)",
    flags=re.IGNORECASE,
)
IMAGE_EXTENSION_URL_PATTERN = re.compile(
    r"https?://[^\s)>\]]+\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s)>\]]*)?",
    flags=re.IGNORECASE,
)


def strip_media_urls(content: str) -> str:
    """Remove media URLs from display text while preserving the source URL metadata."""
    if not content:
        return content
    content = MARKDOWN_MEDIA_PATTERN.sub(" ", content)
    content = MEDIA_URL_PATTERN.sub(" ", content)
    content = IMAGE_EXTENSION_URL_PATTERN.sub(" ", content)
    return re.sub(r"\s+", " ", content).strip()


def clean_reddit_content(content: str) -> str:
    """Strip reddit web UI artifacts from comment content."""
    if not content:
        return content

    content = strip_media_urls(content)
    content = REDDIT_RSS_FOOTER_PATTERN.sub(" ", content).strip()
    content = re.sub(
        r"^\s*返回\s+转到\s+['\"“”]?[^\s'\"“”]+['\"“”]?\s+"
        r"r/[A-Za-z0-9_]+(?:\s*·\s*|\s+)"
        r"(?:\d+天前|\d+小时前|\d+分钟前|昨天|前天|刚刚)\s+"
        r"\S+\s+关注帖子\s+保存\s+隐藏\s+举报\s*",
        "",
        content,
        flags=re.IGNORECASE,
    ).strip()

    for word in REDDIT_UI_WORDS:
        content = re.sub(rf"\b{re.escape(word)}\b", " ", content, flags=re.IGNORECASE)
        content = content.replace(word, " ")

    content = re.sub(r"\s+", " ", content).strip()
    return content


def clean_xiaohongshu_content(content: str) -> str:
    """Strip xiaohongshu UI artifacts from comment content."""
    if not content:
        return content

    content = re.sub(
        r"\s*(?:\d+天前|\d+小时前|\d+分钟前|昨天|前天|刚刚)\s*"
        r"(?:\d{1,2}:\d{2})?\s*[\u4e00-\u9fa5]{2,4}\s*"
        r"(?:置顶评论\s*)?(?:(?:赞\s*)?\d*\s*)?(?:回复)?\s*\d*$",
        "",
        content,
    ).strip()
    content = re.sub(
        r"\s*(?:\d+天前|\d+小时前|\d+分钟前|昨天|前天|刚刚)\s*"
        r"(?:\d{1,2}:\d{2})?\s*[\u4e00-\u9fa5]{2,4}\s*"
        r"(?:置顶评论\s*)?(?:赞|回复)\s*\d*\s*(?:回复)?\s*\d*$",
        "",
        content,
    ).strip()
    content = re.sub(r"\s+\d+\s*\d*$", "", content).strip()
    return content


def clean_content_for_display(content: str, platform: str) -> str:
    """Apply platform-aware lightweight cleaning for UI display only."""
    if platform == "reddit":
        return clean_reddit_content(content)
    if platform == "xiaohongshu":
        return clean_xiaohongshu_content(content)
    return strip_media_urls(content)
