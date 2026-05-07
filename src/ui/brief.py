from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st

from config.settings import WEEKLY_BRIEF_PATH
from src.ui import copy


@st.cache_data(ttl=300)
def load_weekly_brief() -> dict[str, Any]:
    """Load the cached weekly brief artifact without calling any API."""
    if not WEEKLY_BRIEF_PATH.exists() or WEEKLY_BRIEF_PATH.stat().st_size == 0:
        return {}

    try:
        return json.loads(WEEKLY_BRIEF_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Weekly brief cache is invalid: {WEEKLY_BRIEF_PATH}") from exc


def render_weekly_brief() -> None:
    """Render the cached weekly brief as the first analyst entry point."""
    brief = load_weekly_brief()
    st.subheader(copy.WEEKLY_BRIEF_HEADER)

    generated_at = str(brief.get("generated_at") or "").strip()
    if generated_at:
        st.caption(f"Generated: {_display_generated_date(generated_at)}")

    content = str(brief.get("content") or "").strip()
    if not content:
        st.markdown(copy.WEEKLY_BRIEF_MISSING)
        st.caption(copy.WEEKLY_BRIEF_BOUNDARY)
        return

    st.markdown(content)
    st.divider()
    st.caption(copy.WEEKLY_BRIEF_BOUNDARY)


def _display_generated_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value
