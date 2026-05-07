from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import BASELINE_FUNNEL_F1
from src.ui import brief, copy, views
from src.ui.data_loader import load_combined_data, load_interpretations


def main() -> None:
    st.set_page_config(page_title=copy.APP_TITLE, layout="centered")
    st.title(copy.APP_TITLE)

    df = load_combined_data()
    interpretations = load_interpretations()

    views.render_metadata(df=df, funnel_f1=BASELINE_FUNNEL_F1)
    st.divider()

    view_mode = views.render_view_selector()
    if view_mode == "weekly_brief":
        brief.render_weekly_brief()
        st.divider()
        st.caption(copy.FOOTER_TEXT)
        return

    if view_mode == "weekly_diff":
        views.render_weekly_diff_summary(df)
        st.divider()

    selected_stage = views.render_funnel_selector()
    selected_signal = views.render_signal_list(
        df=df,
        selected_stage=selected_stage,
        interpretations=interpretations,
        view_mode=view_mode,
    )

    if selected_signal:
        st.divider()
        views.render_signal_detail(
            df=df,
            signal_key=selected_signal,
            interpretations=interpretations,
        )
    st.divider()
    st.caption(copy.FOOTER_TEXT)


if __name__ == "__main__":
    main()
