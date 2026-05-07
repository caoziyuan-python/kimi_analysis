from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Signal:
    signal_key: str
    funnel_stage: str
    scenario: str
    feedback_type: str
    comment_count: int
    representative_comments: list[str]
    all_comment_ids: list[str]
    platform_breakdown: dict[str, int]
    source_dataset_breakdown: dict[str, int]


def _signal_key(funnel_stage: str, scenario: str, feedback_type: str) -> str:
    return f"{funnel_stage}__{scenario}__{feedback_type}"


def _breakdown(series: pd.Series) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in series.fillna("missing").astype(str).value_counts().sort_index().items()
    }


def _representative_comments(group: pd.DataFrame, limit: int = 8) -> list[str]:
    work = group.copy()
    work["content"] = work["content"].fillna("").astype(str).str.strip()
    work = work[work["content"] != ""]
    work["content_length"] = work["content"].str.len()
    work = work.drop_duplicates(subset=["content"], keep="first")
    work = work.sort_values("content_length", ascending=False)
    return work["content"].head(limit).tolist()


def group_signals(df: pd.DataFrame) -> list[Signal]:
    required_columns = {
        "id",
        "platform",
        "content",
        "funnel_stage",
        "scenario",
        "feedback_type",
        "source_dataset",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"df is missing required columns: {sorted(missing_columns)}")

    signals: list[Signal] = []
    group_columns = ["funnel_stage", "scenario", "feedback_type"]
    for keys, group in df.groupby(group_columns, dropna=False, sort=False):
        funnel_stage, scenario, feedback_type = [str(value) for value in keys]
        signals.append(
            Signal(
                signal_key=_signal_key(funnel_stage, scenario, feedback_type),
                funnel_stage=funnel_stage,
                scenario=scenario,
                feedback_type=feedback_type,
                comment_count=len(group),
                representative_comments=_representative_comments(group),
                all_comment_ids=group["id"].fillna("").astype(str).tolist(),
                platform_breakdown=_breakdown(group["platform"]),
                source_dataset_breakdown=_breakdown(group["source_dataset"]),
            )
        )

    return sorted(signals, key=lambda signal: signal.comment_count, reverse=True)
