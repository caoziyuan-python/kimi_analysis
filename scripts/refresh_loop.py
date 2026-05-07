from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.refresh_now import main as refresh_once


LOG_DIR = PROJECT_ROOT / "logs"
LOG_PATH = LOG_DIR / "refresh_loop.log"


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{timestamp}] {message}"
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated local refresh jobs in the background.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--sleep-minutes", type=int, default=10)
    return parser.parse_args()


def run_round(days: int, limit: int) -> None:
    original_argv = sys.argv[:]
    try:
        sys.argv = ["refresh_now.py", "--days", str(days), "--limit", str(limit)]
        refresh_once()
    finally:
        sys.argv = original_argv


def main() -> int:
    args = parse_args()
    log(
        "refresh loop starting "
        f"rounds={args.rounds} days={args.days} limit={args.limit} sleep_minutes={args.sleep_minutes}"
    )

    successful_rounds = 0
    for round_index in range(1, args.rounds + 1):
        log(f"round {round_index}/{args.rounds} starting")
        try:
            run_round(days=args.days, limit=args.limit)
            successful_rounds += 1
            log(f"round {round_index}/{args.rounds} complete")
        except Exception as exc:
            log(f"round {round_index}/{args.rounds} failed: {exc}")

        if round_index < args.rounds:
            sleep_seconds = args.sleep_minutes * 60
            log(f"sleeping {args.sleep_minutes} minutes before next round")
            time.sleep(sleep_seconds)

    log(f"refresh loop finished successful_rounds={successful_rounds}/{args.rounds}")
    return 0 if successful_rounds > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
