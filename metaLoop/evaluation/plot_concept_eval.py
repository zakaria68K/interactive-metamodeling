import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "metaLoop" / "evaluation" / "results" / "concept_eval_report.json"
OUTPUT_DIR = ROOT / "metaLoop" / "evaluation" / "results"
OUTPUT_PATH = OUTPUT_DIR / "concept_eval_summary.png"


def load_summary(report_path: Path) -> dict[str, dict[str, float]]:
    rows = json.loads(report_path.read_text(encoding="utf-8"))
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


def plot_summary(summary: dict[str, dict[str, float]], output_path: Path) -> Path:
    methods = ["interactive", "no_elicitation", "one_shot"]
    labels = [name.replace("_", " ") for name in methods]
    x_positions = list(range(len(methods)))
    precision_values = [summary.get(name, {}).get("avg_precision", 0.0) for name in methods]
    recall_values = [summary.get(name, {}).get("avg_recall", 0.0) for name in methods]
    f1_values = [summary.get(name, {}).get("avg_f1", 0.0) for name in methods]
    series = [
        ("Precision", precision_values, "#1b9e77", -0.18),
        ("Recall", recall_values, "#7570b3", 0.0),
        ("F1", f1_values, "#d95f02", 0.18),
    ]

    fig, ax = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    fig.suptitle("Concept Evaluation Summary", fontsize=16, fontweight="bold")

    for label, values, color, offset in series:
        shifted_positions = [x + offset for x in x_positions]
        ax.vlines(shifted_positions, 0, values, color=color, linewidth=2.2, alpha=0.95, label=label)
        ax.scatter(shifted_positions, values, color=color, s=38, zorder=3)

    ax.set_title("Average Metrics by Method")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.set_xticks(x_positions, labels)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    for tick in ax.get_xticklabels():
        tick.set_rotation(12)
        tick.set_ha("right")

    for _label, values, color, offset in series:
        for x_pos, value in zip(x_positions, values):
            ax.text(x_pos + offset, value + 0.02, f"{value:.3f}", ha="center", va="bottom", fontsize=9, color=color)

    ax.legend(frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.02))

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