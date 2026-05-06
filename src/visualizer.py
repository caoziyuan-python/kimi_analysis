from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analyzer import FUNNEL_STAGES, REPORT_DIR, STRATEGY_WEIGHT, TOP_SCENARIOS, load_labeled_data


CHART1_PATH = REPORT_DIR / "chart1_funnel_negative_rate.png"
CHART2_PATH = REPORT_DIR / "chart2_priority_matrix.png"


def prepare_dataframe() -> pd.DataFrame:
    df = load_labeled_data()
    df = df[df["funnel_stage"] != "error"]
    df = df[df["sentiment"] != "error"]
    return df


def get_high_confidence_df(df: pd.DataFrame) -> pd.DataFrame:
    df_high = df[df["confidence"] == "high"]
    if len(df_high) == 0:
        print("Warning: no high confidence data, fallback to full dataset")
        return df
    return df_high


def configure_style() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def build_negative_ratio_df(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for funnel_stage in FUNNEL_STAGES:
        for scenario in TOP_SCENARIOS:
            subset = df[
                (df["funnel_stage"] == funnel_stage)
                & (df["scenario"] == scenario)
            ]
            neg = (subset["sentiment"] == "negative").sum()
            pos = (subset["sentiment"] == "positive").sum()
            total = neg + pos
            if total < 3:
                continue

            rows.append(
                {
                    "funnel_stage": funnel_stage,
                    "scenario": scenario,
                    "negative_ratio": neg / total,
                }
            )

    return pd.DataFrame(rows)


def plot_funnel_negative_rate(df: pd.DataFrame) -> None:
    plot_df = build_negative_ratio_df(df)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    if plot_df.empty:
        ax.set_title("各漏斗阶段负面率（按业务场景）")
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        fig.savefig(CHART1_PATH, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return

    sns.barplot(
        data=plot_df,
        x="funnel_stage",
        y="negative_ratio",
        hue="scenario",
        order=FUNNEL_STAGES,
        hue_order=TOP_SCENARIOS,
        ax=ax,
    )

    ax.set_ylim(0, 1)
    ax.set_xlabel("funnel_stage")
    ax.set_ylabel("negative_ratio")
    ax.set_title("各漏斗阶段负面率（按业务场景）")

    for container in ax.containers:
        labels = []
        for bar in container:
            height = bar.get_height()
            labels.append(f"{height:.2f}" if height == height else "")
        ax.bar_label(container, labels=labels, padding=3, fontsize=9)

    fig.savefig(CHART1_PATH, dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_priority_matrix(df_high: pd.DataFrame) -> pd.DataFrame:
    matrix = pd.DataFrame(0.0, index=TOP_SCENARIOS, columns=FUNNEL_STAGES)
    total = len(df_high)
    if total == 0:
        return matrix

    focus_df = df_high[
        df_high["scenario"].isin(TOP_SCENARIOS) & df_high["funnel_stage"].isin(FUNNEL_STAGES)
    ].copy()

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
            user_signal = (count / total) * negative_ratio
            priority_score = user_signal * STRATEGY_WEIGHT.get(scenario, 0.5)
            matrix.loc[scenario, funnel_stage] = priority_score

    return matrix


def plot_priority_matrix(df_high: pd.DataFrame) -> None:
    matrix = build_priority_matrix(df_high)

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(
        matrix,
        annot=True,
        fmt=".4f",
        cmap="Reds",
        cbar=True,
        linewidths=0.5,
        linecolor="white",
        ax=ax,
    )
    ax.set_title("产品优化优先级矩阵")
    ax.set_xlabel("funnel_stage")
    ax.set_ylabel("scenario")

    fig.savefig(CHART2_PATH, dpi=200, bbox_inches="tight")
    plt.close(fig)


def visualize() -> None:
    configure_style()
    df = prepare_dataframe()
    df_high = get_high_confidence_df(df)

    plot_funnel_negative_rate(df)
    plot_priority_matrix(df_high)

    print(f"Saved: {CHART1_PATH}")
    print(f"Saved: {CHART2_PATH}")


if __name__ == "__main__":
    visualize()
