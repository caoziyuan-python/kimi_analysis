from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import BASELINE_PATH, INTERPRETATIONS_PATH, MONITORING_PATH
from src.pipeline.clean import _is_product_relevant
from src.schemas import LABELED_COLUMNS, validate_labeled_df


@st.cache_data(ttl=300)
def load_baseline_data() -> pd.DataFrame:
    baseline_df = pd.read_csv(BASELINE_PATH)
    if not validate_labeled_df(baseline_df):
        raise ValueError(f"Baseline data is invalid: {BASELINE_PATH}")
    return baseline_df[LABELED_COLUMNS]


@st.cache_data(ttl=300)
def load_combined_data() -> pd.DataFrame:
    baseline_df = load_baseline_data()
    frames = [baseline_df]
    if MONITORING_PATH.exists() and MONITORING_PATH.stat().st_size > 0:
        monitoring_df = pd.read_csv(MONITORING_PATH)
        if not monitoring_df.empty:
            if not validate_labeled_df(monitoring_df):
                st.warning("Monitoring data has schema issues, skipped.")
                return pd.concat(frames, ignore_index=True)
            monitoring_df = _filter_relevant_monitoring(monitoring_df)
            frames.append(monitoring_df[LABELED_COLUMNS])
    return pd.concat(frames, ignore_index=True)


@st.cache_data(ttl=300)
def load_interpretations() -> dict[str, Any]:
    if not INTERPRETATIONS_PATH.exists() or INTERPRETATIONS_PATH.stat().st_size == 0:
        return {}

    try:
        return json.loads(INTERPRETATIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Interpretations cache is invalid: {INTERPRETATIONS_PATH}") from exc


def _filter_relevant_monitoring(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    work = df.copy()
    text = (
        work.get("content", pd.Series("", index=work.index)).fillna("").astype(str)
        + " "
        + work.get("url", pd.Series("", index=work.index)).fillna("").astype(str)
    )
    return work[text.map(_is_product_relevant)].copy()
