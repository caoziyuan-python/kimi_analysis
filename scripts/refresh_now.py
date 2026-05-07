from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import MONITORING_PATH
from src.collectors import github, hackernews, reddit
from src.pipeline.clean import clean
from src.pipeline.label import label
from src.pipeline.merge import merge_into_monitoring


DEFAULT_DAYS = 7
DEFAULT_LIMIT_PER_COLLECTOR = 50
PENDING_CLEANED_PATH = PROJECT_ROOT / "data" / "monitoring" / "pending_cleaned.csv"


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual one-shot refresh: collect -> clean -> label -> merge."
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT_PER_COLLECTOR)
    parser.add_argument(
        "--max-label",
        type=int,
        default=100,
        help="Maximum cleaned rows to send to Moonshot in this run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    log(f"refresh starting since={since.isoformat()} limit_per_collector={args.limit}")

    reddit_df = reddit.collect(since=since, limit=args.limit)
    hn_df = hackernews.collect(since=since, limit=args.limit)
    github_df = github.collect(since=since, limit=args.limit)
    raw_df = pd.concat([reddit_df, hn_df, github_df], ignore_index=True)
    log(
        "collected raw rows: "
        f"reddit={len(reddit_df)} hackernews={len(hn_df)} github={len(github_df)} total={len(raw_df)}"
    )
    if raw_df.empty:
        raise RuntimeError("No raw rows collected; aborting before labeling")

    cleaned_df = clean(raw_df)
    log(f"cleaned rows: {len(cleaned_df)}")
    if cleaned_df.empty:
        raise RuntimeError("No rows remaining after cleaning; aborting before labeling")

    cleaned_df["source_dataset"] = "monitoring"
    PENDING_CLEANED_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(PENDING_CLEANED_PATH, index=False, encoding="utf-8-sig")
    log(f"saved cleaned pending rows: {len(cleaned_df)} -> {PENDING_CLEANED_PATH}")

    labeling_df = cleaned_df.head(args.max_label).copy()
    log(f"labeling rows this run: {len(labeling_df)}")
    labeled_df = label(labeling_df)
    labeled_df["source_dataset"] = "monitoring"
    log(f"labeled rows: {len(labeled_df)}")
    if labeled_df.empty:
        raise RuntimeError("No rows labeled successfully; aborting before merge")

    merged_df = merge_into_monitoring(labeled_df, MONITORING_PATH)
    log(f"merged monitoring rows: {len(merged_df)} -> {MONITORING_PATH}")
    log("refresh complete")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log(f"refresh failed: {exc}")
        raise
