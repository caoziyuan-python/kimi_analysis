from pathlib import Path
import sys

import pandas as pd
from sklearn.metrics import classification_report, f1_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LABELED_DIR = PROJECT_ROOT / "data" / "labeled"
EVAL_DIMS = ["sentiment", "funnel_stage", "scenario", "feedback_type"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def evaluate() -> None:
    zhihu = pd.read_csv(LABELED_DIR / "zhihu_labeled.csv")
    reddit = pd.read_csv(LABELED_DIR / "reddit_labeled.csv")
    weibo = pd.read_csv(LABELED_DIR / "weibo_labeled.csv")
    xhs = pd.read_csv(LABELED_DIR / "xhs_labeled.csv")
    manual = pd.read_csv(LABELED_DIR / "manual_sample_100.csv")

    all_labeled = pd.concat([zhihu, reddit, weibo, xhs], ignore_index=True)

    all_labeled["key"] = all_labeled["content"].astype(str).str[:50]
    manual["key"] = manual["content"].astype(str).str[:50]

    merged = manual.merge(
        all_labeled[["key", "sentiment", "funnel_stage", "scenario", "feedback_type"]],
        on="key",
        suffixes=("_manual", "_llm"),
    )

    print(f"匹配条数: {len(merged)}")

    scores: dict[str, float] = {}
    for dim in EVAL_DIMS:
        y_true = merged[f"{dim}_manual"]
        y_pred = merged[f"{dim}_llm"]
        f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
        scores[dim] = f1

        print(f"\n=== {dim} ===")
        print(f"weighted F1: {f1:.3f}")
        print(classification_report(y_true, y_pred, zero_division=0))

    print("\n=== 总结 ===")
    for dim in EVAL_DIMS:
        f1 = scores[dim]
        mark = "✅" if f1 >= 0.8 else "⚠️" if f1 >= 0.6 else "❌"
        print(f"{dim}: {f1:.3f} {mark}")


if __name__ == "__main__":
    evaluate()
