from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.prompts import WEEKLY_BRIEF_PROMPT
from config.settings import (
    BASELINE_PATH,
    MAX_RETRIES,
    MOONSHOT_BASE_URL,
    MOONSHOT_MODEL,
    MONITORING_PATH,
    REQUEST_TIMEOUT_SECONDS,
    WEEKLY_BRIEF_PATH,
)
from src.pipeline.clean import _is_product_relevant
from src.schemas import LABELED_COLUMNS, validate_labeled_df
from src.ui.views import _signal_title, classify_signal_status


MAX_SIGNALS = 8


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}")


def load_combined_data() -> pd.DataFrame:
    baseline_df = pd.read_csv(BASELINE_PATH)
    if not validate_labeled_df(baseline_df):
        raise ValueError(f"baseline file is invalid: {BASELINE_PATH}")

    frames = [baseline_df[LABELED_COLUMNS]]
    if MONITORING_PATH.exists() and MONITORING_PATH.stat().st_size > 0:
        monitoring_df = pd.read_csv(MONITORING_PATH)
        if not monitoring_df.empty:
            if not validate_labeled_df(monitoring_df):
                raise ValueError(f"monitoring file is invalid: {MONITORING_PATH}")
            frames.append(_filter_relevant_monitoring(monitoring_df)[LABELED_COLUMNS])

    return pd.concat(frames, ignore_index=True)


def load_interpretations() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "interpretations" / "interpretations.json"
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _filter_relevant_monitoring(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    text = (
        work.get("content", pd.Series("", index=work.index)).fillna("").astype(str)
        + " "
        + work.get("url", pd.Series("", index=work.index)).fillna("").astype(str)
    )
    return work[text.map(_is_product_relevant)].copy()


def collect_signal_entries(df: pd.DataFrame, interpretations: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for stage, stage_df in df.groupby("funnel_stage", sort=False):
        baseline_total = int((stage_df["source_dataset"] == "baseline").sum())
        monitoring_total = int((stage_df["source_dataset"] == "monitoring").sum())
        for (scenario, feedback_type), group in stage_df.groupby(["scenario", "feedback_type"], sort=False):
            baseline_n = int((group["source_dataset"] == "baseline").sum())
            monitoring_n = int((group["source_dataset"] == "monitoring").sum())
            if monitoring_n == 0:
                continue

            status = classify_signal_status(baseline_n, monitoring_n, baseline_total, monitoring_total)
            signal_key = f"{stage}__{scenario}__{feedback_type}"
            interpretation = interpretations.get(signal_key, {})
            entries.append(
                {
                    "signal_key": signal_key,
                    "stage": stage,
                    "title": _signal_title(str(scenario), str(feedback_type)),
                    "status": status,
                    "this_week": monitoring_n,
                    "historical": baseline_n,
                    "interpretation": str(interpretation.get("how_i_interpret_this", "")).strip()
                    if isinstance(interpretation, dict)
                    else "",
                    "checks": interpretation.get("possible_internal_checks", [])
                    if isinstance(interpretation, dict)
                    else [],
                }
            )

    flagged = [
        entry
        for entry in entries
        if entry["status"] in {"Newly observed this week", "Appears more frequent recently"}
    ]
    if flagged:
        return sorted(flagged, key=_entry_sort_key)[:MAX_SIGNALS]

    fallback = [
        entry
        for entry in entries
        if entry["status"] == "Mentioned this week" and int(entry["historical"]) < 50
    ]
    return sorted(fallback, key=_entry_sort_key)[:3]


def _entry_sort_key(entry: dict[str, Any]) -> tuple[int, int, int]:
    priority = {
        "Newly observed this week": 0,
        "Appears more frequent recently": 1,
        "Mentioned this week": 2,
    }.get(str(entry["status"]), 3)
    return priority, -int(entry["this_week"]), int(entry["historical"])


def build_signals_text(entries: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, entry in enumerate(entries, start=1):
        checks = entry.get("checks", [])
        checks_text = "、".join(str(check).strip() for check in checks if str(check).strip()) or "暂无缓存指标建议"
        interpretation = entry["interpretation"] or "暂无缓存解读。"
        blocks.append(
            "\n".join(
                [
                    f"[signal {index}]",
                    f"标题：{entry['title']}",
                    f"阶段：{entry['stage']}",
                    f"状态：{entry['status']}",
                    f"本周出现：{entry['this_week']}条，历史：{entry['historical']}条",
                    f"解读：{interpretation}",
                    f"可检查指标：{checks_text}",
                ]
            )
        )
    return "\n\n".join(blocks)


def generate_brief(signals_text: str) -> str:
    load_dotenv()
    api_key = os.getenv("MOONSHOT_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MOONSHOT_API_KEY is required")

    payload = {
        "model": MOONSHOT_MODEL,
        "messages": [{"role": "user", "content": WEEKLY_BRIEF_PROMPT.format(signals=signals_text)}],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                MOONSHOT_BASE_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"]).strip()
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError("Moonshot weekly brief failed after retries") from exc
            time.sleep(10 * attempt)

    raise RuntimeError("Moonshot weekly brief failed")


def write_brief(content: str, entries: list[dict[str, Any]]) -> None:
    WEEKLY_BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "content": content,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MOONSHOT_MODEL,
        "signal_count": len(entries),
        "signals": [
            {
                "signal_key": entry["signal_key"],
                "title": entry["title"],
                "stage": entry["stage"],
                "status": entry["status"],
                "this_week": entry["this_week"],
                "historical": entry["historical"],
            }
            for entry in entries
        ],
    }
    WEEKLY_BRIEF_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    df = load_combined_data()
    interpretations = load_interpretations()
    entries = collect_signal_entries(df, interpretations)
    if not entries:
        raise RuntimeError("No monitoring signals found for weekly brief")

    log(f"generating weekly brief from {len(entries)} signal(s)")
    content = generate_brief(build_signals_text(entries))
    write_brief(content, entries)
    log(f"weekly brief written to {WEEKLY_BRIEF_PATH}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log(f"weekly brief generation failed: {exc}")
        raise
