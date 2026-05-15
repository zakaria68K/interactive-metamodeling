import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "metaLoop" / "evaluation" / "results"
OUTPUT_PATH = RESULTS_DIR / "concept_eval_summary.png"

REPORT_FILES = [
    RESULTS_DIR / "concept_eval_report.json",
    RESULTS_DIR / "concept_eval_report_third_baseline.json",
]


def load_rows(report_files: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in report_files:
        if path.exists():
            rows.extend(json.loads(path.read_text(encoding="utf-8")))
    return rows


def load_summary(rows: list[dict]) -> dict[str, dict[str, float]]:
    by_method: dict[str, dict[str, float]] = defaultdict(
        lambda: {"precision_sum": 0.0, "recall_sum": 0.0, "f1_sum": 0.0, "count": 0.0}
    )
    for row in rows:
        method = row["method"]
        by_method[method]["precision_sum"] += float(row["precision"])
        by_method[method]["recall_sum"] += float(row["recall"])
        by_method[method]["f1_sum"] += float(row["f1"])
        by_method[method]["count"] += 1.0

    summary: dict[str, dict[str, float]] = {}
    for method, stats in by_method.items():
        count = stats["count"] or 1.0
        summary[method] = {
            "avg_precision": stats["precision_sum"] / count,
            "avg_recall": stats["recall_sum"] / count,
            "avg_f1": stats["f1_sum"] / count,
        }
    return summary


def plot_summary(summary: dict[str, dict[str, float]], output_path: Path, total_profiles: int) -> Path:
    methods = ["interactive", "generate_then_validate", "one_shot"]
    labels = ["Interactive", "Gen + Validate", "One Shot"]
    x_positions = [0, 0.35, 0.70]
    colors = ["#000000", "#888888", "#00569D"]

    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    fig.suptitle("Concept Evaluation — Average F1 Score", fontsize=14, fontweight="bold")

    f1_values = [summary.get(m, {}).get("avg_f1", 0.0) for m in methods]

    bars = ax.bar(x_positions, f1_values, color=colors, width=0.15, alpha=0.88, zorder=3)
    for bar, value in zip(bars, f1_values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.015,
                f"{value:.3f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_ylim(0, 1.15)
    ax.set_ylabel("F1 Score", fontsize=11)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_xlim(-0.2, 0.90)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    ax.text(
        0.98, 0.97,
        f"n = {total_profiles} profiles\n5 users / domain",
        transform=ax.transAxes,
        ha="right", va="top",
        fontsize=8.5,
        color="#444444",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#cccccc", alpha=0.8),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> None:
    rows = load_rows(REPORT_FILES)
    total_profiles = len({r["profile_id"] for r in rows if r["method"] == "interactive"} or
                         {r["profile_id"] for r in rows})
    summary = load_summary(rows)
    output_path = plot_summary(summary, OUTPUT_PATH, total_profiles)
    print(output_path)


if __name__ == "__main__":
    main()