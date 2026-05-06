import os
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LABELED_DIR = PROJECT_ROOT / "data" / "labeled"
REPORT_DIR = PROJECT_ROOT / "output" / "report"
REPORT_PATH = REPORT_DIR / "analysis_results.txt"

LABELED_FILES = [
    ("zhihu", LABELED_DIR / "zhihu_labeled.csv"),
    ("reddit", LABELED_DIR / "reddit_labeled.csv"),
    ("weibo", LABELED_DIR / "weibo_labeled.csv"),
    ("xhs", LABELED_DIR / "xhs_labeled.csv"),
]

TOP_SCENARIOS = ["vibe_coding", "agent", "pricing"]
FUNNEL_STAGES = ["activation", "success", "conversion", "retention"]

# 战略权重计算方法：
# 三个可观测信号，每个信号赋值1分：
# 1. paid: 是否在付费墙后（直接影响收入）
# 2. official: 是否为官方重点功能（资源投入信号）
# 3. competition: 是否存在竞品压力（外部威胁信号）
#
# 总分映射规则：
# 3分 -> 0.9
# 2分 -> 0.8
# 1分 -> 0.7
# 0分 -> 0.5
#
# 各场景评分：
# vibe_coding: paid=1, official=1, competition=1 -> 3分 -> 0.9
# agent: paid=1, official=1, competition=0 -> 2分 -> 0.8
# pricing: paid=0, official=0, competition=0 -> 0分
#          但pricing直接作用于Conversion节点，业务上调至0.7
# general_chat: paid=0, official=0, competition=0 -> 0分 -> 0.5
STRATEGY_WEIGHT = {
    "vibe_coding": 0.9,
    "agent": 0.8,
    "pricing": 0.7,
    "general_chat": 0.5,
}


class Reporter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines: list[str] = []

    def log(self, text: str = "") -> None:
        print(text)
        self.lines.append(text)

    def save(self) -> None:
        os.makedirs(self.path.parent, exist_ok=True)
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def load_labeled_data() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source_name, path in LABELED_FILES:
        df = pd.read_csv(path)
        if "source" not in df.columns:
            df["source"] = source_name
        else:
            df["source"] = df["source"].fillna("").replace("", source_name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def format_series(series: pd.Series, name: str) -> str:
    output = series.rename_axis(name).reset_index(name="count")
    return output.to_string(index=False)


def format_frame(df: pd.DataFrame) -> str:
    if df.empty:
        return "(empty)"
    return df.to_string()


def analyze_funnel_distribution(df: pd.DataFrame, reporter: Reporter) -> None:
    reporter.log("=== 分析一：漏斗节点分布 ===")
    reporter.log("全量 funnel_stage 分布：")
    reporter.log(format_series(df["funnel_stage"].fillna("missing").value_counts(dropna=False), "funnel_stage"))
    reporter.log()

    reporter.log("按 source 统计 funnel_stage：")
    by_source = pd.crosstab(df["source"].fillna("missing"), df["funnel_stage"].fillna("missing"), dropna=False)
    reporter.log(format_frame(by_source))
    reporter.log()


def analyze_negative_signal(df_high: pd.DataFrame, reporter: Reporter) -> None:
    reporter.log("=== 分析二：负面信号强度 ===")
    reporter.log("节点 | count | neg_ratio | high_conf_ratio")

    for stage in FUNNEL_STAGES:
        stage_df = df_high[df_high["funnel_stage"] == stage]
        count = len(stage_df)
        neg = (stage_df["sentiment"] == "negative").sum()
        pos = (stage_df["sentiment"] == "positive").sum()
        negative_ratio = neg / (neg + pos) if (neg + pos) > 0 else 0
        high_conf_ratio = (stage_df["confidence"] == "high").sum() / count if count > 0 else 0
        reporter.log(f"{stage} | {count} | {negative_ratio:.2f} | {high_conf_ratio:.2f}")

    reporter.log()


def analyze_business_scenarios(df_high: pd.DataFrame, reporter: Reporter) -> None:
    reporter.log("=== 分析三：业务场景分布 ===")
    scenario_df = df_high[df_high["scenario"].isin(TOP_SCENARIOS)].copy()

    reporter.log("top scenarios 分布：")
    scenario_counts = (
        scenario_df["scenario"]
        .value_counts()
        .reindex(TOP_SCENARIOS, fill_value=0)
    )
    reporter.log(format_series(scenario_counts, "scenario"))
    reporter.log()

    reporter.log("scenario x funnel_stage 热力表（排除other）：")
    heatmap_df = scenario_df[scenario_df["funnel_stage"].isin(FUNNEL_STAGES)]
    heatmap = pd.crosstab(
        heatmap_df["scenario"],
        heatmap_df["funnel_stage"],
    ).reindex(index=TOP_SCENARIOS, columns=FUNNEL_STAGES, fill_value=0)
    reporter.log(format_frame(heatmap))
    reporter.log()


def analyze_competitor_signal(df: pd.DataFrame, reporter: Reporter) -> None:
    reporter.log("=== 分析四：竞品信号 ===")
    df_comp = df[(df["feedback_type"] == "comparison") & (df["confidence"] == "high")]

    reporter.log(f"comparison 高置信样本条数: {len(df_comp)}")
    reporter.log("scenario 分布：")
    reporter.log(
        format_series(
            df_comp["scenario"].fillna("missing").value_counts(dropna=False),
            "scenario",
        )
    )
    reporter.log()

    reporter.log("sentiment 分布：")
    reporter.log(
        format_series(
            df_comp["sentiment"].fillna("missing").value_counts(dropna=False),
            "sentiment",
        )
    )
    reporter.log()


def analyze_priority_matrix(df_high: pd.DataFrame, reporter: Reporter) -> None:
    reporter.log("=== 分析五：优先级矩阵 ===")
    focus_df = df_high[
        df_high["scenario"].isin(TOP_SCENARIOS) & df_high["funnel_stage"].isin(FUNNEL_STAGES)
    ].copy()

    results: list[tuple[float, str]] = []
    total = len(df_high)

    for scenario in TOP_SCENARIOS:
        for funnel_stage in FUNNEL_STAGES:
            subset = focus_df[
                (focus_df["scenario"] == scenario) & (focus_df["funnel_stage"] == funnel_stage)
            ]
            count = len(subset)
            if count < 5:
                continue

            neg = (subset["sentiment"] == "negative").sum()
            pos = (subset["sentiment"] == "positive").sum()
            if (neg + pos) < 3:
                continue

            negative_ratio = neg / (neg + pos)
            user_signal = (count / total) * negative_ratio if total > 0 else 0
            priority_score = user_signal * STRATEGY_WEIGHT.get(scenario, 0.5)
            line = (
                f"{scenario} | {funnel_stage} | count={count} | "
                f"neg_ratio={negative_ratio:.2f} | score={priority_score:.4f}"
            )
            results.append((priority_score, line))

    if not results:
        reporter.log("(empty)")
        reporter.log()
        return

    for _, line in sorted(results, key=lambda item: item[0], reverse=True):
        reporter.log(line)

    reporter.log()


def analyze() -> None:
    reporter = Reporter(REPORT_PATH)
    df = load_labeled_data()
    df = df[df["funnel_stage"] != "error"]
    df = df[df["sentiment"] != "error"]
    df_high = df[df["confidence"] == "high"]
    if len(df_high) == 0:
        reporter.log("Warning: no high confidence data, fallback to full dataset")
        df_high = df

    analyze_funnel_distribution(df, reporter)
    analyze_negative_signal(df_high, reporter)
    analyze_business_scenarios(df_high, reporter)
    analyze_competitor_signal(df, reporter)
    analyze_priority_matrix(df_high, reporter)
    reporter.save()


if __name__ == "__main__":
    analyze()
