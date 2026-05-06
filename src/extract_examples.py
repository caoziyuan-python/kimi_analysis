from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LABELED_DIR = PROJECT_ROOT / "data" / "labeled"
REPORT_DIR = PROJECT_ROOT / "output" / "report"
OUTPUT_PATH = REPORT_DIR / "example_quotes.txt"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LABELED_FILES = [
    ("zhihu", LABELED_DIR / "zhihu_labeled.csv"),
    ("reddit", LABELED_DIR / "reddit_labeled.csv"),
    ("weibo", LABELED_DIR / "weibo_labeled.csv"),
    ("xhs", LABELED_DIR / "xhs_labeled.csv"),
]

GROUPS = [
    {
        "name": "组合1",
        "filters": {
            "scenario": "vibe_coding",
            "funnel_stage": "success",
            "sentiment": "negative",
        },
    },
    {
        "name": "组合2",
        "filters": {
            "scenario": "pricing",
            "funnel_stage": "conversion",
            "sentiment": "negative",
        },
    },
    {
        "name": "组合3",
        "filters": {
            "scenario": "vibe_coding",
            "funnel_stage": "activation",
        },
    },
    {
        "name": "组合4",
        "filters": {
            "scenario": "pricing",
            "funnel_stage": "retention",
            "sentiment": "negative",
        },
    },
    {
        "name": "组合5",
        "filters": {
            "scenario": "agent",
            "funnel_stage": "success",
            "sentiment": "negative",
        },
    },
]


def load_labeled_data() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source_name, path in LABELED_FILES:
        df = pd.read_csv(path)
        if "source" not in df.columns:
            df["source"] = source_name
        else:
            df["source"] = df["source"].fillna("").replace("", source_name)
        frames.append(df)

    df = pd.concat(frames, ignore_index=True)
    df = df[df["funnel_stage"] != "error"]
    df = df[df["sentiment"] != "error"]
    df["content_short"] = df["content"].astype(str).str[:80]
    df["likes"] = pd.to_numeric(df.get("likes", 0), errors="coerce").fillna(0)
    df = df.drop_duplicates(subset="content_short", keep="first")
    df = df[df["content"].astype(str).str.len() >= 20]
    return df


def filter_group(df: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    result = df
    for column, value in filters.items():
        result = result[result[column] == value]
    return result.sort_values(by="likes", ascending=False)


def sample_group(group: pd.DataFrame) -> pd.DataFrame:
    if group.empty:
        return group

    sorted_group = group.sort_values("likes", ascending=False)
    top = sorted_group.head(5)
    start = len(sorted_group) // 3
    mid = sorted_group.iloc[start : start + 3]
    low = sorted_group.tail(2)
    sample = pd.concat([top, mid, low]).drop_duplicates()
    return sample


def format_content(content: str) -> str:
    return str(content or "").replace("\r", " ").replace("\n", " ").strip()[:150]


def build_output(df: pd.DataFrame) -> str:
    sections: list[str] = []

    for group in GROUPS:
        name = group["name"]
        filtered = filter_group(df, group["filters"])
        sampled = sample_group(filtered)

        sections.append(f"=== {name} | 总条数: {len(filtered)} ===")
        sections.append("---")

        for idx, row in enumerate(sampled.itertuples(index=False), start=1):
            sections.append(f"[{idx}] source={row.source} | likes={int(row.likes)}")
            sections.append(format_content(row.content))
            sections.append("---")

        if sampled.empty:
            sections.append("(empty)")
            sections.append("---")

        sections.append("")

    return "\n".join(sections).rstrip() + "\n"


def extract() -> None:
    df = load_labeled_data()
    output = build_output(df)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    extract()
