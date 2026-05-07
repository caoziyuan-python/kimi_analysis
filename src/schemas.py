from __future__ import annotations

import pandas as pd


LABELED_COLUMNS: list[str] = [
    "id",
    "platform",
    "url",
    "author",
    "content",
    "created_at",
    "collected_at",
    "sentiment",
    "funnel_stage",
    "scenario",
    "feedback_type",
    "confidence",
    "source_dataset",
]

PLATFORM_VALUES = {"reddit", "hackernews", "github", "zhihu", "xiaohongshu", "weibo"}
SENTIMENT_VALUES = {"positive", "negative", "neutral"}
FUNNEL_STAGE_VALUES = {"activation", "success", "conversion", "retention", "other"}
SCENARIO_VALUES = {"vibe_coding", "agent", "pricing", "general_chat", "other"}
FEEDBACK_TYPE_VALUES = {"bug", "cognition", "comparison", "other"}
CONFIDENCE_VALUES = {"high", "low"}
SOURCE_DATASET_VALUES = {"baseline", "monitoring"}

VALUE_COLUMNS: dict[str, set[str]] = {
    "platform": PLATFORM_VALUES,
    "sentiment": SENTIMENT_VALUES,
    "funnel_stage": FUNNEL_STAGE_VALUES,
    "scenario": SCENARIO_VALUES,
    "feedback_type": FEEDBACK_TYPE_VALUES,
    "confidence": CONFIDENCE_VALUES,
    "source_dataset": SOURCE_DATASET_VALUES,
}

REQUIRED_NON_EMPTY_COLUMNS = [
    "id",
    "platform",
    "content",
    "created_at",
    "collected_at",
    "sentiment",
    "funnel_stage",
    "scenario",
    "feedback_type",
    "confidence",
    "source_dataset",
]


def validate_labeled_df(df: pd.DataFrame) -> bool:
    if not set(LABELED_COLUMNS).issubset(df.columns):
        return False

    for column in REQUIRED_NON_EMPTY_COLUMNS:
        values = df[column].astype("string")
        if values.isna().any() or values.str.strip().eq("").any():
            return False

    for column, allowed_values in VALUE_COLUMNS.items():
        normalized = df[column].astype("string").str.strip()
        if not normalized.isin(allowed_values).all():
            return False

    return True
