from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import MONITORING_PATH
from src.pipeline.label import label
from src.pipeline.merge import merge_into_monitoring
from src.schemas import LABELED_COLUMNS


PENDING_CLEANED_PATH = PROJECT_ROOT / "data" / "monitoring" / "pending_cleaned.csv"
FAILED_LABELING_PATH = PROJECT_ROOT / "data" / "monitoring" / "failed_labeling.csv"


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Label cleaned monitoring rows in small batches and merge successes."
    )
    parser.add_argument("--pending", type=Path, default=PENDING_CLEANED_PATH)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--sleep-seconds", type=float, default=10.0)
    parser.add_argument("--max-rows", type=int, default=100)
    return parser.parse_args()


def _read_csv_or_empty(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns)


def _already_labeled_ids() -> set[str]:
    monitoring_df = _read_csv_or_empty(MONITORING_PATH, LABELED_COLUMNS)
    if monitoring_df.empty or "id" not in monitoring_df.columns:
        return set()
    return set(monitoring_df["id"].astype(str))


def _write_remaining(path: Path, original_df: pd.DataFrame, labeled_ids: set[str]) -> None:
    if "id" not in original_df.columns:
        original_df.to_csv(path, index=False, encoding="utf-8-sig")
        return

    remaining_df = original_df[~original_df["id"].astype(str).isin(labeled_ids)].copy()
    remaining_df.to_csv(path, index=False, encoding="utf-8-sig")
    log(f"remaining pending rows: {len(remaining_df)} -> {path}")


def _append_failed(failed_df: pd.DataFrame) -> None:
    if failed_df.empty:
        return

    existing_df = _read_csv_or_empty(FAILED_LABELING_PATH)
    combined_df = pd.concat([existing_df, failed_df], ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset=["id"], keep="last") if "id" in combined_df.columns else combined_df
    FAILED_LABELING_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(FAILED_LABELING_PATH, index=False, encoding="utf-8-sig")
    log(f"failed rows saved: {len(failed_df)} -> {FAILED_LABELING_PATH}")


def main() -> int:
    args = parse_args()
    pending_df = _read_csv_or_empty(args.pending)
    if pending_df.empty:
        raise RuntimeError(f"No pending cleaned rows found: {args.pending}")

    pending_df["source_dataset"] = "monitoring"
    existing_ids = _already_labeled_ids()
    if "id" in pending_df.columns:
        work_df = pending_df[~pending_df["id"].astype(str).isin(existing_ids)].copy()
    else:
        work_df = pending_df.copy()

    work_df = work_df.head(args.max_rows).copy()
    log(f"pending rows loaded: {len(pending_df)}")
    log(f"rows selected for labeling: {len(work_df)}")
    if work_df.empty:
        log("nothing to label")
        return 0

    all_labeled: list[pd.DataFrame] = []
    failed_batches: list[pd.DataFrame] = []
    for start in range(0, len(work_df), args.batch_size):
        batch_df = work_df.iloc[start : start + args.batch_size].copy()
        batch_number = start // args.batch_size + 1
        log(f"labeling batch {batch_number}: {len(batch_df)} rows")
        try:
            labeled_df = label(batch_df)
        except Exception as exc:
            log(f"batch {batch_number} failed: {exc}")
            failed_batches.append(batch_df)
            time.sleep(args.sleep_seconds)
            continue

        if not labeled_df.empty:
            merged_df = merge_into_monitoring(labeled_df, MONITORING_PATH)
            all_labeled.append(labeled_df)
            log(f"batch {batch_number} merged: labeled={len(labeled_df)} monitoring_total={len(merged_df)}")

        time.sleep(args.sleep_seconds)

    labeled_ids: set[str] = set()
    if all_labeled:
        labeled_ids = set(pd.concat(all_labeled, ignore_index=True)["id"].astype(str))
    _write_remaining(args.pending, pending_df, labeled_ids)

    if failed_batches:
        _append_failed(pd.concat(failed_batches, ignore_index=True))

    log(f"labeling complete: success={sum(len(df) for df in all_labeled)} failed_batches={len(failed_batches)}")
    return 0 if all_labeled else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log(f"pending labeling failed: {exc}")
        raise
