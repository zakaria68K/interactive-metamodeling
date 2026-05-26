"""
Plot interactive evaluation results: panels (a) and (d) only.

Usage:
    python3 -m metaLoop.evaluation.plot_interactive_traits \
        metaLoop/evaluation/results/concept_eval_interactive_20260526_124304.json
"""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# ── load ──────────────────────────────────────────────────────────────────────
result_file = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    sorted(Path("metaLoop/evaluation/results").glob("concept_eval_interactive_*.json"))[-1]
)
data = json.loads(result_file.read_text())

domains_u = list(dict.fromkeys(
    r["profile_id"].rsplit("_user_", 1)[0] for r in data
))
roles = ["novice", "intermediate", "expert"]

ROLE_COLORS = {
    "novice":       "#e07b54",
    "intermediate": "#5b8db8",
    "expert":       "#4caf7d",
}


def row_for(domain, role):
    for r in data:
        if r["profile_id"] == f"{domain}_user_0{roles.index(role)+1}_{role}":
            return r
    return None

# ── figure ────────────────────────────────────────────────────────────────────
fig, (ax_bar, ax_trait) = plt.subplots(1, 2, figsize=(14, 5.5))
fig.suptitle(
    "Interactive Metamodel Elicitation — Concept Recall by User Trait Profile",
    fontsize=13, fontweight="bold",
)
fig.subplots_adjust(bottom=0.22, wspace=0.35)

# ── (a) grouped bar: F1 per domain × role ─────────────────────────────────────
x = np.arange(len(domains_u))
width = 0.25

for i, role in enumerate(roles):
    f1s = [row_for(d, role)["f1"] if row_for(d, role) else 0.0 for d in domains_u]
    bars = ax_bar.bar(x + (i - 1) * width, f1s, width,
                      label=role.capitalize(), color=ROLE_COLORS[role],
                      edgecolor="white", linewidth=0.6)
    for bar, v in zip(bars, f1s):
        ax_bar.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{v:.2f}", ha="center", va="bottom", fontsize=7)

ax_bar.set_xticks(x)
ax_bar.set_xticklabels([d.replace("_", "\n") for d in domains_u], fontsize=8.5)
ax_bar.set_ylim(0, 1.15)
ax_bar.set_ylabel("F1 score")
ax_bar.set_title("(a) F1 per Domain × User Role")
ax_bar.legend(title="User role", fontsize=8, title_fontsize=8)
ax_bar.axhline(1.0, color="grey", lw=0.8, ls="--", alpha=0.5)
ax_bar.spines[["top", "right"]].set_visible(False)

# ── (b) precision & recall per role ──────────────────────────────────────────

# ── (b) precision & recall per role, averaged across domains ──────────────────
x = np.arange(len(roles))
width = 0.30

prec_avgs = [np.mean([r["precision"] for r in data if r["competency"] == role]) for role in roles]
rec_avgs  = [np.mean([r["recall"]    for r in data if r["competency"] == role]) for role in roles]

bars_p = ax_trait.bar(x - width / 2, prec_avgs, width, label="Precision",
                      color="#5b8db8", edgecolor="white", linewidth=0.6)
bars_r = ax_trait.bar(x + width / 2, rec_avgs,  width, label="Recall",
                      color="#e07b54", edgecolor="white", linewidth=0.6)

for bar, v in list(zip(bars_p, prec_avgs)) + list(zip(bars_r, rec_avgs)):
    ax_trait.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                  f"{v:.2f}", ha="center", va="bottom", fontsize=8.5)

ax_trait.set_xticks(x)
ax_trait.set_xticklabels([r.capitalize() for r in roles], fontsize=10)
ax_trait.set_ylim(0, 1.18)
ax_trait.set_ylabel("Score")
ax_trait.set_title("(b) Precision & Recall per User Role\n(averaged across domains)")
ax_trait.axhline(1.0, color="grey", lw=0.8, ls="--", alpha=0.5)
ax_trait.legend(fontsize=9)
ax_trait.spines[["top", "right"]].set_visible(False)

# trait bundle annotations below each role label
ROLE_BUNDLES = {
    "novice":        "anxious · terse\n· confirmatory",
    "intermediate":  "enthusiastic · moderate\n· exploratory",
    "expert":        "calm · verbose\n· goal-directed",
}
for xi, role in zip(x, roles):
    ax_trait.annotate(
        ROLE_BUNDLES[role],
        xy=(xi, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -46), textcoords="offset points",
        ha="center", va="top", fontsize=7, color="#555555",
        linespacing=1.4,
    )

# ── save ──────────────────────────────────────────────────────────────────────
out_pdf = result_file.parent / (result_file.stem + "_figure.pdf")
out_png = result_file.parent / (result_file.stem + "_figure.png")
fig.savefig(out_pdf, bbox_inches="tight", dpi=150)
fig.savefig(out_png, bbox_inches="tight", dpi=150)
print(f"Saved: {out_pdf}")
print(f"Saved: {out_png}")
plt.show()
