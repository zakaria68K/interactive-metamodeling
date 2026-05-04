import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "metaLoop" / "evaluation" / "results" / "concept_eval_report.json"
OUTPUT_PATH = ROOT / "metaLoop" / "evaluation" / "results" / "concept_eval_summary.png"


def load_summary(report_path: Path) -> dict[str, dict[str, float]]:
    rows = json.loads(report_path.read_text(encoding="utf-8"))
    by_method: dict[str, dict[str, float]] = defaultdict(lambda: {"f1_sum": 0.0, "count": 0.0})

    for row in rows:
        method = row["method"]
        by_method[method]["f1_sum"] += float(row["f1"])
        by_method[method]["count"] += 1.0

    summary: dict[str, dict[str, float]] = {}
    for method, stats in by_method.items():
        count = stats["count"] or 1.0
        summary[method] = {
            "avg_f1": stats["f1_sum"] / count,
        }
    return summary


def plot_summary(summary: dict[str, dict[str, float]], output_path: Path) -> Path:
    methods = ["interactive", "no_elicitation", "one_shot"]
    labels = [name.replace("_", " ") for name in methods]
    avg_f1 = [summary.get(name, {}).get("avg_f1", 0.0) for name in methods]
    colors = ["#1b9e77", "#7570b3", "#d95f02"]

    fig, ax = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    fig.suptitle("Concept Evaluation Summary", fontsize=16, fontweight="bold")

    bars = ax.bar(labels, avg_f1, color=colors, width=0.62)
    ax.set_title("Average F1")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    for tick in ax.get_xticklabels():
        tick.set_rotation(12)
        tick.set_ha("right")
    for bar, value in zip(bars, avg_f1):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.02,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> None:
    summary = load_summary(REPORT_PATH)
    output_path = plot_summary(summary, OUTPUT_PATH)
    print(output_path)


if __name__ == "__main__":
    main()