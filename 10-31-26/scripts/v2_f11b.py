"""F11b: very long author lists. Fig 4 without its Autophagy Guidelines panel (figure_revision_plan.md, Task 11).

Usage: python 10-31-26/scripts/v2_f11b.py   (from the IMPACT folder)
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from v2_common import ROOT, save, write_csv

BLUE, VERMILION, GRAY, INK = "#0072B2", "#D55E00", "#8C8C8C", "#222222"
plt.rcParams.update({"font.family": "Arial", "font.size": 8, "axes.edgecolor": "#666666", "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.5, "axes.axisbelow": True, "xtick.color": "#666666", "ytick.color": "#666666",
                     "xtick.labelcolor": INK, "ytick.labelcolor": INK, "legend.frameon": False, "savefig.dpi": 300, "pdf.fonttype": 42})
OLD = os.path.join(ROOT, "10-31-26", "data")


def read(name):
    return list(csv.DictReader(open(os.path.join(OLD, name))))


def main():
    a, b = read("fig4a_author_count_buckets.csv"), read("fig4b_papers_100plus_authors_by_year.csv")
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.9), gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.34})
    ax = axes[0]
    x = np.arange(len(a))
    for key, color, lab in (("share_of_papers", GRAY, "Papers"), ("share_of_citations", BLUE, "Citations"), ("share_of_author_credited_citations", VERMILION, "Citations credited to authors")):
        ax.plot(x, [float(r[key]) for r in a], color=color, marker="o", markersize=3.5, linewidth=1.4, label=lab)
    ax.set_yscale("log")
    ticks = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1]
    ax.set_yticks(ticks, ["0.0001%", "0.001%", "0.01%", "0.1%", "1%", "10%", "100%"])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks(x, [r["authors"] for r in a], fontsize=6.5)
    ax.set_xlabel("Authors per paper")
    ax.set_ylabel("Share of total (log scale)")
    ax.legend(fontsize=6, loc="lower left")
    ax.set_title("A  Papers and citations by author count, 2003–2026", loc="left", fontsize=8.5)
    ax = axes[1]
    ax.plot([int(r["year"]) for r in b], [float(r["per_10000_papers"]) for r in b], color=BLUE, linewidth=1.6)
    ax.set_ylim(0, None)
    ax.set_xticks([2005, 2015, 2025])
    ax.set_xlabel("Year published")
    ax.set_ylabel("Per 10,000 papers")
    ax.set_title("B  Papers with 100+ authors over time", loc="left", fontsize=8.5)
    save(fig, "F11b_author_counts")
    write_csv("f11b_author_counts", list(a[0]), [list(r.values()) for r in a])


if __name__ == "__main__":
    main()
