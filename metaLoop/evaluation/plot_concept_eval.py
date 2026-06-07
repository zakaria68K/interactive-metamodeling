import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "metaLoop" / "evaluation" / "results"
OUTPUT_PATH = RESULTS_DIR / "concept_eval_summary.png"
OUTPUT_PER_DOMAIN = RESULTS_DIR / "concept_eval_per_domain.png"
OUTPUT_PRECISION_RECALL = RESULTS_DIR / "concept_eval_precision_recall.png"

# Always pick the most recently modified results file
def _find_report_files() -> list[Path]:
    all_files = sorted(RESULTS_DIR.glob("concept_eval_*.json"), key=lambda p: p.stat().st_mtime)
    return [all_files[-1]] if all_files else []

REPORT_FILES = _find_report_files()


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
        f"n = {total_profiles} domains\n3 methods",
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


def plot_per_domain(rows: list[dict], output_path: Path) -> Path:
    """Grouped bar chart: F1 per domain × method."""
    methods = ["interactive", "generate_then_validate", "one_shot"]
    labels = ["Interactive", "Gen + Validate", "One Shot"]
    colors = ["#000000", "#888888", "#00569D"]

    # Collect domains in insertion order
    domains = list(dict.fromkeys(r["profile_id"] for r in rows))
    # Build matrix: domain → method → f1
    scores: dict[str, dict[str, float]] = {d: {} for d in domains}
    for row in rows:
        scores[row["profile_id"]][row["method"]] = float(row["f1"])

    x = np.arange(len(domains))
    width = 0.22
    offsets = [-width, 0, width]

    fig, ax = plt.subplots(figsize=(max(10, len(domains) * 1.8), 5), constrained_layout=True)
    fig.suptitle("Concept Evaluation — F1 Score per Domain", fontsize=13, fontweight="bold")

    for method, label, color, offset in zip(methods, labels, colors, offsets):
        values = [scores[d].get(method, 0.0) for d in domains]
        bars = ax.bar(x + offset, values, width, label=label, color=color, alpha=0.88, zorder=3)
        for bar, v in zip(bars, values):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, v + 0.015,
                        f"{v:.2f}", ha="center", va="bottom", fontsize=7.5, fontweight="bold")

    ax.set_ylim(0, 1.2)
    ax.set_ylabel("F1 Score", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels([d.upper() for d in domains], fontsize=10)
    ax.legend(fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_precision_recall(rows: list[dict], output_path: Path) -> Path:
    """Scatter plot: Precision vs Recall per domain, coloured by method."""
    methods = ["interactive", "generate_then_validate", "one_shot"]
    labels = ["Interactive", "Gen + Validate", "One Shot"]
    colors = ["#000000", "#888888", "#00569D"]
    markers = ["o", "s", "^"]

    fig, ax = plt.subplots(figsize=(7, 6), constrained_layout=True)
    fig.suptitle("Concept Evaluation — Precision vs Recall", fontsize=13, fontweight="bold")

    for method, label, color, marker in zip(methods, labels, colors, markers):
        method_rows = [r for r in rows if r["method"] == method]
        xs = [float(r["recall"]) for r in method_rows]
        ys = [float(r["precision"]) for r in method_rows]
        ax.scatter(xs, ys, label=label, color=color, marker=marker, s=90, zorder=4, alpha=0.85)
        for r, x, y in zip(method_rows, xs, ys):
            ax.annotate(r["profile_id"], (x, y), textcoords="offset points",
                        xytext=(5, 4), fontsize=7, color=color)

    ax.set_xlim(-0.05, 1.1)
    ax.set_ylim(-0.05, 1.1)
    ax.set_xlabel("Recall", fontsize=11)
    ax.set_ylabel("Precision", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> None:
    rows = load_rows(REPORT_FILES)
    if not rows:
        print("No result files found.")
        return
    total_profiles = len({r["profile_id"] for r in rows})
    summary = load_summary(rows)

    p1 = plot_summary(summary, OUTPUT_PATH, total_profiles)
    print(f"Average F1 bar chart  → {p1}")

    p2 = plot_per_domain(rows, OUTPUT_PER_DOMAIN)
    print(f"Per-domain F1 chart   → {p2}")

    p3 = plot_precision_recall(rows, OUTPUT_PRECISION_RECALL)
    print(f"Precision/Recall plot → {p3}")


if __name__ == "__main__":
    main()