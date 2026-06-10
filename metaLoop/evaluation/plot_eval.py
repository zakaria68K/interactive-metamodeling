import json, sys
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 plot_eval.py <eval_json>")
        sys.exit(1)

    rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    methods = list(dict.fromkeys(r["method"] for r in rows))

    concept_scores  = defaultdict(list)
    relation_scores = defaultdict(list)
    for r in rows:
        m = r["method"]
        concept_scores[m].append(float(r.get("concept_f1", r.get("f1", 0.0))))
        relation_scores[m].append(float(r.get("relation_precision", 0.0)))

    avg_concept  = [sum(concept_scores[m])  / len(concept_scores[m])  for m in methods]
    avg_relation = [sum(relation_scores[m]) / len(relation_scores[m]) for m in methods]

    labels = [m.replace("_", "\n") for m in methods]
    colors = ["#1a1a2e", "#00569D", "#c0392b"]
    x = range(len(methods))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5), constrained_layout=True)
    fig.suptitle("Average Evaluation Results", fontsize=14, fontweight="bold")

    for ax, vals, title, ylabel in [
        (ax1, avg_concept,  "Concept Coverage — Avg F1",       "F1 Score"),
        (ax2, avg_relation, "Relation Accuracy — Avg Precision","Precision"),
    ]:
        bars = ax.bar(list(x), vals, color=colors[:len(methods)], width=0.4, alpha=0.88, zorder=3)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, v + 0.02,
                    f"{v:.3f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
        ax.set_ylim(0, 1.15)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.set_axisbelow(True)

    out = Path(sys.argv[1]).parent / (Path(sys.argv[1]).stem + "_avg_plot.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot saved → {out}")

if __name__ == "__main__":
    main()