from src.schemas import FUNNEL_STAGE_VALUES


APP_TITLE = "K2.6 External Feedback Monitor"

METADATA_MODE = "Mode: Baseline only"
METADATA_BASELINE_TEMPLATE = "Baseline records: {baseline_count}"
METADATA_SOURCE = "Data source: 5 platforms, static baseline"
METADATA_F1_TEMPLATE = "Annotation F1: {funnel_f1:.2f}"
METADATA_FRESHNESS_TEMPLATE = "Data freshness: {freshness}"

WEEKLY_BRIEF_LABEL = "Weekly Brief"
WEEKLY_DIFF_LABEL = "Signal Explorer"
FULL_BASELINE_LABEL = "Full baseline"
WEEKLY_DIFF_SUMMARY = (
    "**This week:** {m} new records from Reddit + HN + GitHub. "
    "Comparing against baseline of {b} records."
)
NO_NEW_SIGNALS_THIS_WEEK = (
    "No new signals in this funnel stage this week. "
    "Switch to 'Full baseline' to browse all signals."
)

FUNNEL_STAGE_LABELS = ["activation", "success", "conversion", "retention", "other"]
assert set(FUNNEL_STAGE_LABELS) == FUNNEL_STAGE_VALUES, (
    "copy.py FUNNEL_STAGE_LABELS out of sync with schemas.FUNNEL_STAGE_VALUES"
)
DEFAULT_FUNNEL_STAGE = "success"

SIGNAL_META_FORMAT = "Status: {status} · tags: {feedback_type} / {scenario}"
STAGE_COUNT_TEMPLATE = "{stage}: {count} records"
PLATFORM_COUNTS_HEADER = "Platform counts"
RAW_COMMENTS_HEADER = "Raw comments"
RECENT_VOICES_HEADER = "Recent voices"
SELECTED_SIGNAL_HEADER = "Selected signal"
SELECTED_SIGNAL_META_FORMAT = "Funnel: {stage} · Scenario: {scenario} · Feedback type: {feedback_type}"
TAXONOMY_EXPANDER_LABEL = "Taxonomy"
INTERPRETATION_HEADER = "Note from analyst"
INTERNAL_CHECKS_HEADER = "Possible things I would check internally"
BOUNDARY_HEADER = "Boundary"
NO_RECORDS_IN_STAGE = "No records in this funnel stage."
NO_COMMENTS_IN_STAGE = "No raw comments found for this funnel stage."
NO_INTERPRETATION_FOR_VIEW = "No generated interpretation is available for this view yet."
NO_SIGNAL_SELECTED = "Select a signal to inspect raw voices."
WEEKLY_BRIEF_HEADER = "本周外部反馈简报"
WEEKLY_BRIEF_MISSING = "Weekly brief has not been generated yet. Run `python scripts/generate_weekly_brief.py`."
WEEKLY_BRIEF_BOUNDARY = "以上内容基于外部公开讨论，所有结论需结合内部数据验证。"

COMMENT_META_FORMAT = "{platform} · {date}"
SHOW_FULL_TEXT = "Show full text"

FOOTER_TEXT = (
    "This tool surfaces external signals only. All conclusions require internal data validation. "
    "Chinese platforms (知乎/小红书/微博) are baseline-only due to anti-scraping limits."
)
