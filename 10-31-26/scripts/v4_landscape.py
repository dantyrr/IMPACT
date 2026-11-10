"""The six-figure set: main Figure 5 and Supplementary Figure S6, from the v3 panels of F9.

Usage: python 10-31-26/scripts/v4_landscape.py   (from the IMPACT folder)
"""
import os
import sys

os.environ["FIG_DIR"] = "v4"
sys.path.insert(0, os.path.dirname(__file__))
import v3_f9 as N  # noqa: E402
from v3_f9 import M, panel_a, panel_b, panel_c, panel_counts, panel_d, plt, save, tier_layers, write_csv  # noqa: E402


def main():
    rows = []
    fig = plt.figure(figsize=(7.2, 5.9))
    gs = fig.add_gridspec(2, 6, height_ratios=[1.1, 1], hspace=0.5, wspace=1.4)
    panel_a(fig.add_subplot(gs[0, :3]))
    panel_b(fig.add_subplot(gs[0, 3:]), rows)
    panel_counts(fig.add_subplot(gs[1, :2]), rows)
    panel_c(fig.add_subplot(gs[1, 2:4]), rows)
    panel_d(fig.add_subplot(gs[1, 4:]), rows)
    save(fig, "Fig5_publishing")

    fig = plt.figure(figsize=(7.2, 5.2))
    gs = fig.add_gridspec(2, 6, hspace=0.5, wspace=1.4)
    layers = tier_layers()
    top = max(sum(v for _, v, _ in L).max() for _, L in layers) * 1.05
    for k, (fam, L) in enumerate(layers):
        M.stacked(fig.add_subplot(gs[0, 2 * k:2 * k + 2]), L, f"{'ABC'[k]}  {fam}", alpha=1)
        ax = fig.add_subplot(gs[1, 2 * k:2 * k + 2])
        M.stacked(ax, L, f"{'DEF'[k]}  {fam}, shared scale", alpha=1)
        ax.get_legend().remove()
        ax.set_ylim(0, top)
        if k == 0:
            ax.set_ylabel("Citable items per year")
            fig.axes[-2].set_ylabel("Citable items per year")
    save(fig, "S6_publisher_tiers")


if __name__ == "__main__":
    main()
