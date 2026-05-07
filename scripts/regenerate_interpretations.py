from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import BASELINE_PATH, INTERPRETATIONS_PATH, MONITORING_PATH
from src.schemas import LABELED_COLUMNS, validate_labeled_df
from src.interpretation.grouper import Signal, group_signals
from src.interpretation.interpreter import interpret


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}")


def content_hash(signal: Signal) -> str:
    payload = json.dumps(signal.representative_comments, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_cache() -> dict:
    if not INTERPRETATIONS_PATH.exists() or INTERPRETATIONS_PATH.stat().st_size == 0:
        return {}
    return json.loads(INTERPRETATIONS_PATH.read_text(encoding="utf-8"))


def status_for_signal(cache: dict, signal: Signal) -> str:
    cached = cache.get(signal.signal_key)
    if isinstance(cached, dict) and cached.get("content_hash") == content_hash(signal):
        return "cached"
    return "regenerated"


def load_combined_data() -> pd.DataFrame:
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(f"baseline file not found: {BASELINE_PATH}")

    baseline_df = pd.read_csv(BASELINE_PATH)
    if not validate_labeled_df(baseline_df):
        raise ValueError(f"baseline file is invalid: {BASELINE_PATH}")

    frames = [baseline_df[LABELED_COLUMNS]]
    if MONITORING_PATH.exists() and MONITORING_PATH.stat().st_size > 0:
        monitoring_df = pd.read_csv(MONITORING_PATH)
        if not monitoring_df.empty:
            if not validate_labeled_df(monitoring_df):
                raise ValueError(f"monitoring file is invalid: {MONITORING_PATH}")
            frames.append(monitoring_df[LABELED_COLUMNS])

    return pd.concat(frames, ignore_index=True)


def main() -> int:
    try:
        df = load_combined_data()
    except Exception as exc:
        log(str(exc))
        return 1

    signals = group_signals(df)
    if not signals:
        log("no signals found")
        return 1

    processed = 0
    cache_before = read_cache()
    total = len(signals)

    for index, signal in enumerate(signals, start=1):
        planned_status = status_for_signal(cache_before, signal)
        try:
            interpret(signal)
            processed += 1
            print(f"[{index}/{total}] {signal.signal_key} - {planned_status}")
        except Exception as exc:
            print(f"[{index}/{total}] {signal.signal_key} - failed: {exc}")

    log(f"Generated/cached {processed} interpretations to interpretations.json")
    return 0 if processed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
