from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.schemas import LABELED_COLUMNS, validate_labeled_df


def merge_into_monitoring(new_labeled_df: pd.DataFrame, monitoring_path: Path) -> pd.DataFrame:
    if not validate_labeled_df(new_labeled_df):
        raise ValueError("new_labeled_df does not conform to labeled schema")

    if monitoring_path.exists() and monitoring_path.stat().st_size > 0:
        existing_df = pd.read_csv(monitoring_path)
    else:
        existing_df = pd.DataFrame(columns=LABELED_COLUMNS)

    if not existing_df.empty and not validate_labeled_df(existing_df):
        raise ValueError(f"existing monitoring file is invalid: {monitoring_path}")

    merged_df = pd.concat([existing_df, new_labeled_df], ignore_index=True)
    merged_df = merged_df.drop_duplicates(subset=["id"], keep="last")
    merged_df = merged_df[LABELED_COLUMNS].sort_values("created_at", ascending=False)

    monitoring_path.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_csv(monitoring_path, index=False, encoding="utf-8-sig")
    return merged_df.reset_index(drop=True)
