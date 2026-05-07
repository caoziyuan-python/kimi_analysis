from __future__ import annotations

import pandas as pd
from sklearn.metrics import f1_score


EVAL_DIMS = ["sentiment", "funnel_stage", "scenario", "feedback_type"]


def _content_key(series: pd.Series) -> pd.Series:
    return series.astype(str).str[:50]


def compute_f1(labeled_df: pd.DataFrame, manual_df: pd.DataFrame) -> dict[str, float]:
    labeled = labeled_df.copy()
    manual = manual_df.copy()

    labeled["key"] = _content_key(labeled["content"])
    manual["key"] = _content_key(manual["content"])

    merged = manual.merge(
        labeled[["key", *EVAL_DIMS]],
        on="key",
        suffixes=("_manual", "_llm"),
    )

    if merged.empty:
        return {dimension: 0.0 for dimension in EVAL_DIMS}

    scores: dict[str, float] = {}
    for dimension in EVAL_DIMS:
        y_true = merged[f"{dimension}_manual"]
        y_pred = merged[f"{dimension}_llm"]
        scores[dimension] = f1_score(y_true, y_pred, average="weighted", zero_division=0)

    return scores
