from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.ui import copy
from src.ui.text_clean import clean_content_for_display


MONITORING_COMMENT_LIMIT = 3
MIN_DISPLAY_CONTENT_LENGTH = 30
COMMENT_PREVIEW_LENGTH = 300
STATUS_PRIORITY = {
    "Newly observed this week": 0,
    "Appears more frequent recently": 1,
    "Mentioned this week": 2,
    "Not seen in this week's monitoring": 3,
    "Present in baseline": 4,
}

SIGNAL_TITLE_BY_TAG = {
    ("vibe_coding", "bug"): "Coding workflow friction showed up in bug reports",
    ("vibe_coding", "comparison"): "Coding workflow comparisons appeared in external discussion",
    ("vibe_coding", "cognition"): "Coding workflow usage questions appeared",
    ("vibe_coding", "other"): "Coding workflow discussion appeared this week",
    ("agent", "bug"): "Agent workflow failures appeared in user reports",
    ("agent", "comparison"): "Agent capability comparisons appeared",
    ("agent", "cognition"): "Agent setup or usage questions appeared",
    ("agent", "other"): "Agent workflow discussion appeared this week",
    ("pricing", "comparison"): "Pricing comparisons appeared in external discussion",
    ("pricing", "cognition"): "Pricing or plan confusion appeared",
    ("pricing", "other"): "Pricing and plan discussion appeared this week",
    ("general_chat", "bug"): "General chat quality issues appeared",
    ("general_chat", "comparison"): "General chat comparisons appeared",
    ("general_chat", "cognition"): "General chat usage questions appeared",
    ("general_chat", "other"): "General chat discussion appeared this week",
    ("other", "bug"): "Unclassified product issues appeared",
    ("other", "comparison"): "Broad product comparisons appeared",
    ("other", "cognition"): "Reasoning or usage questions appeared",
    ("other", "other"): "General external discussion appeared this week",
}


def render_metadata(df: pd.DataFrame, funnel_f1: float) -> None:
    """Render baseline mode, count, source, annotation quality, and freshness."""
    baseline_count = int((df["source_dataset"] == "baseline").sum())
    monitoring_count = int((df["source_dataset"] == "monitoring").sum())
    freshness = _latest_created_at(df)
    baseline_col, monitoring_col, f1_col, freshness_col = st.columns([2, 1, 1, 2])
    baseline_col.metric("Baseline", baseline_count)
    monitoring_col.metric("Monitoring", monitoring_count)
    f1_col.metric("Funnel F1", f"{funnel_f1:.2f}")
    freshness_col.metric("Freshness", freshness)
    st.caption(copy.METADATA_SOURCE)


def render_view_selector() -> str:
    """Tab selector for weekly_diff vs full_baseline view."""
    return st.radio(
        "View",
        options=["weekly_brief", "weekly_diff", "full_baseline"],
        format_func=lambda value: {
            "weekly_brief": copy.WEEKLY_BRIEF_LABEL,
            "weekly_diff": copy.WEEKLY_DIFF_LABEL,
            "full_baseline": copy.FULL_BASELINE_LABEL,
        }[value],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
    )


def render_weekly_diff_summary(df: pd.DataFrame) -> None:
    """Render an attention-routing summary for this week's signal changes."""
    summary = _summarize_weekly_signals(df)
    new = summary["new"]
    rising = summary["rising"]
    mentioned = summary["mentioned"]

    if not new and not rising:
        st.markdown("**This week: no newly observed or appearing-more-frequent signals.**")
    else:
        st.markdown(
            "**This week: "
            f"{len(new)} newly observed · {len(rising)} appearing more frequent.**"
        )

    flagged = new + rising
    if flagged:
        st.markdown("**Worth checking first**")
        for item in flagged[:3]:
            st.markdown(
                f"- **{item['title']}** · {item['stage']} · "
                f"This week: {item['monitoring']} · Historical: {item['baseline']}"
            )

    if mentioned:
        st.caption(f"{len(mentioned)} additional signal(s) mentioned this week — visible below.")
    st.caption("This summary routes attention only; it does not explain cause or priority.")


def classify_signal_status(
    baseline_n: int,
    monitoring_n: int,
    baseline_total: int,
    monitoring_total: int,
) -> str:
    """Classify signal status based on baseline vs monitoring counts."""
    if baseline_n == 0 and monitoring_n > 0:
        return "Newly observed this week"
    if monitoring_n == 0:
        return "Not seen in this week's monitoring"
    if monitoring_n < 3:
        return "Mentioned this week"
    if baseline_n >= 50 and monitoring_n < 10:
        return "Mentioned this week"
    if monitoring_n > 0:
        baseline_rate = baseline_n / max(1, baseline_total)
        monitoring_rate = monitoring_n / max(1, monitoring_total)
        if monitoring_rate > baseline_rate * 1.5:
            return "Appears more frequent recently"
        if monitoring_rate < baseline_rate * 0.5:
            return "Mentioned this week"
    return "Present in baseline"


def render_funnel_selector() -> str:
    """Render the funnel-stage selector and return the selected stage."""
    default_index = copy.FUNNEL_STAGE_LABELS.index(copy.DEFAULT_FUNNEL_STAGE)
    return st.radio(
        "Funnel stage",
        options=copy.FUNNEL_STAGE_LABELS,
        index=default_index,
        horizontal=True,
        label_visibility="collapsed",
    )


def render_signal_list(
    df: pd.DataFrame,
    selected_stage: str,
    interpretations: dict[str, Any],
    view_mode: str,
) -> str | None:
    """Render selectable signals and return the selected signal key."""
    stage_df = df[df["funnel_stage"] == selected_stage].copy()
    if stage_df.empty:
        st.markdown(copy.NO_RECORDS_IN_STAGE)
        return None

    signal_rows = _build_signal_rows(stage_df, selected_stage, view_mode)
    if not signal_rows:
        message = copy.NO_NEW_SIGNALS_THIS_WEEK if view_mode == "weekly_diff" else copy.NO_RECORDS_IN_STAGE
        st.markdown(message)
        return None

    state_key = f"selected_signal__{selected_stage}__{view_mode}"
    valid_keys = [row["signal_key"] for row in signal_rows]
    if st.session_state.get(state_key) not in valid_keys:
        st.session_state[state_key] = valid_keys[0]

    st.caption("Signals")
    if view_mode == "weekly_diff":
        flagged_rows = [row for row in signal_rows if _is_flagged_status(str(row["status"]))]
        other_rows = [row for row in signal_rows if not _is_flagged_status(str(row["status"]))]
        rows_to_show = flagged_rows if flagged_rows else signal_rows[:1]
        if not flagged_rows:
            other_rows = signal_rows[1:]
        for row in rows_to_show:
            _render_signal_row(row, state_key, view_mode)
        if other_rows:
            with st.expander("Show all signals", expanded=False):
                for row in other_rows:
                    _render_signal_row(row, state_key, view_mode)
    else:
        for row in signal_rows:
            _render_signal_row(row, state_key, view_mode)

    return str(st.session_state[state_key])


def render_signal_detail(
    df: pd.DataFrame,
    signal_key: str,
    interpretations: dict[str, Any],
) -> None:
    """Render raw comments and cached interpretation for one signal."""
    stage, scenario, feedback_type = _parse_signal_key(signal_key)
    signal_df = df[
        (df["funnel_stage"] == stage)
        & (df["scenario"] == scenario)
        & (df["feedback_type"] == feedback_type)
    ].copy()

    st.subheader(copy.SELECTED_SIGNAL_HEADER)
    st.markdown(_signal_title(scenario, feedback_type))
    with st.expander(copy.TAXONOMY_EXPANDER_LABEL, expanded=False):
        st.caption(
            copy.SELECTED_SIGNAL_META_FORMAT.format(
                stage=stage,
                scenario=scenario,
                feedback_type=feedback_type,
            )
        )

    _render_recent_voices(signal_df)
    interpretation = interpretations.get(signal_key)
    st.subheader(copy.INTERPRETATION_HEADER)
    if not isinstance(interpretation, dict):
        st.markdown(copy.NO_INTERPRETATION_FOR_VIEW)
        return

    text = str(interpretation.get("how_i_interpret_this", "")).strip()
    if not text:
        st.markdown(copy.NO_INTERPRETATION_FOR_VIEW)
        return

    st.markdown(f"> {text}")
    _render_internal_checks(interpretation)
    _render_boundary(interpretation)


def _build_signal_rows(stage_df: pd.DataFrame, selected_stage: str, view_mode: str) -> list[dict[str, Any]]:
    baseline_total = int((stage_df["source_dataset"] == "baseline").sum())
    monitoring_total = int((stage_df["source_dataset"] == "monitoring").sum())
    rows: list[dict[str, Any]] = []

    for (scenario, feedback_type), group in stage_df.groupby(["scenario", "feedback_type"], sort=False):
        baseline_n = int((group["source_dataset"] == "baseline").sum())
        monitoring_n = int((group["source_dataset"] == "monitoring").sum())
        if view_mode == "weekly_diff" and monitoring_n == 0:
            continue

        total_n = len(group)
        status = classify_signal_status(baseline_n, monitoring_n, baseline_total, monitoring_total)
        signal_key = f"{selected_stage}__{scenario}__{feedback_type}"
        title = _signal_title(str(scenario), str(feedback_type))
        meta = copy.SIGNAL_META_FORMAT.format(
            status=status if view_mode == "weekly_diff" else "Present in baseline",
            feedback_type=feedback_type,
            scenario=scenario,
        )
        rows.append(
            {
                "signal_key": signal_key,
                "title": title,
                "meta": meta,
                "status": status,
                "total": total_n,
                "monitoring": monitoring_n,
                "baseline": baseline_n,
            }
        )

    if view_mode == "weekly_diff":
        return sorted(rows, key=lambda row: (STATUS_PRIORITY.get(row["status"], 9), -row["monitoring"], -row["total"]))
    return sorted(rows, key=lambda row: row["total"], reverse=True)


def _render_signal_row(row: dict[str, Any], state_key: str, view_mode: str) -> None:
    title_col, monitoring_col, baseline_col = st.columns([6, 1.2, 1.2])
    if title_col.button(
        str(row["title"]),
        key=f"signal_button__{row['signal_key']}__{view_mode}",
        use_container_width=True,
    ):
        st.session_state[state_key] = row["signal_key"]
    title_col.caption(row["meta"])
    monitoring_col.caption("This week")
    monitoring_col.markdown(f"**{row['monitoring']}**")
    baseline_col.caption("Historical")
    baseline_col.markdown(f"**{row['baseline']}**")


def _is_flagged_status(status: str) -> bool:
    return status in {"Newly observed this week", "Appears more frequent recently"}


def _summarize_weekly_signals(df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    new: list[dict[str, Any]] = []
    rising: list[dict[str, Any]] = []
    mentioned: list[dict[str, Any]] = []

    for stage in copy.FUNNEL_STAGE_LABELS:
        stage_df = df[df["funnel_stage"] == stage].copy()
        if stage_df.empty:
            continue

        baseline_total = int((stage_df["source_dataset"] == "baseline").sum())
        monitoring_total = int((stage_df["source_dataset"] == "monitoring").sum())
        for (scenario, feedback_type), group in stage_df.groupby(["scenario", "feedback_type"], sort=False):
            baseline_n = int((group["source_dataset"] == "baseline").sum())
            monitoring_n = int((group["source_dataset"] == "monitoring").sum())
            if monitoring_n == 0:
                continue

            status = classify_signal_status(baseline_n, monitoring_n, baseline_total, monitoring_total)
            entry = {
                "stage": stage,
                "title": _signal_title(str(scenario), str(feedback_type)),
                "monitoring": monitoring_n,
                "baseline": baseline_n,
            }
            if status == "Newly observed this week":
                new.append(entry)
            elif status == "Appears more frequent recently":
                rising.append(entry)
            else:
                mentioned.append(entry)

    return {
        "new": sorted(new, key=lambda item: (-item["monitoring"], item["stage"], item["title"])),
        "rising": sorted(rising, key=lambda item: (-item["monitoring"], item["stage"], item["title"])),
        "mentioned": sorted(mentioned, key=lambda item: (-item["monitoring"], item["stage"], item["title"])),
    }


def _render_recent_voices(signal_df: pd.DataFrame) -> None:
    st.subheader(copy.RECENT_VOICES_HEADER)
    if signal_df.empty:
        st.markdown(copy.NO_COMMENTS_IN_STAGE)
        return

    work = signal_df.copy()
    work["_created_at"] = pd.to_datetime(work["created_at"], errors="coerce", utc=True)
    work = work.sort_values("_created_at", ascending=False)

    monitoring_rows = _displayable_voice_rows(
        work[work["source_dataset"] == "monitoring"],
        MONITORING_COMMENT_LIMIT,
    )
    if not monitoring_rows.empty:
        st.markdown("Monitoring voices")
        _render_voice_rows(monitoring_rows)
    else:
        st.markdown("No displayable monitoring voices found for this signal.")


def _displayable_voice_rows(rows: pd.DataFrame, limit: int) -> pd.DataFrame:
    displayable_indexes: list[Any] = []
    for index, row in rows.iterrows():
        content = clean_content_for_display(
            str(row.get("content") or "").strip(),
            str(row.get("platform") or ""),
        )
        if len(_compact_text(content)) >= MIN_DISPLAY_CONTENT_LENGTH:
            displayable_indexes.append(index)
        if len(displayable_indexes) >= limit:
            break
    return rows.loc[displayable_indexes].copy()


def _render_voice_rows(rows: pd.DataFrame) -> None:
    for _, row in rows.iterrows():
        content = clean_content_for_display(
            str(row.get("content") or "").strip(),
            str(row.get("platform") or ""),
        )
        st.markdown(_truncate(content, COMMENT_PREVIEW_LENGTH))
        if len(content) > COMMENT_PREVIEW_LENGTH:
            with st.expander(copy.SHOW_FULL_TEXT):
                st.markdown(content)

        meta = copy.COMMENT_META_FORMAT.format(
            platform=str(row.get("platform") or "unknown"),
            date=_display_date(row.get("created_at")),
        )
        dataset = str(row.get("source_dataset") or "unknown")
        url = str(row.get("url") or "").strip()
        st.caption(f"{dataset} · {meta} · [Open source]({url})" if url else f"{dataset} · {meta}")


def _signal_title(scenario: str, feedback_type: str) -> str:
    return SIGNAL_TITLE_BY_TAG.get(
        (scenario, feedback_type),
        f"{scenario.replace('_', ' ')} discussion with {feedback_type} signals",
    )


def _render_internal_checks(interpretation: dict[str, Any]) -> None:
    checks = interpretation.get("possible_internal_checks", [])
    if not isinstance(checks, list) or not checks:
        return

    st.subheader(copy.INTERNAL_CHECKS_HEADER)
    lines = [f"- `{str(check).strip()}`" for check in checks if str(check).strip()]
    if lines:
        st.markdown("\n".join(lines))


def _render_boundary(interpretation: dict[str, Any]) -> None:
    boundary = str(interpretation.get("boundary_note", "")).strip()
    if not boundary:
        return

    st.subheader(copy.BOUNDARY_HEADER)
    st.markdown(f"*{boundary}*")


def _parse_signal_key(signal_key: str) -> tuple[str, str, str]:
    parts = signal_key.split("__")
    if len(parts) != 3:
        raise ValueError(f"Invalid signal_key: {signal_key}")
    return parts[0], parts[1], parts[2]


def _latest_created_at(df: pd.DataFrame) -> str:
    dates = pd.to_datetime(df.get("created_at"), errors="coerce", utc=True)
    if dates.dropna().empty:
        return "baseline snapshot"
    return dates.max().date().isoformat()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _compact_text(text: str) -> str:
    return "".join(str(text or "").split())


def _display_date(value: object) -> str:
    date = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(date):
        return "unknown"
    return date.date().isoformat()
