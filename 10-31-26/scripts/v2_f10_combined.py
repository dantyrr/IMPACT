"""F10: one figure from the three geography figures, at print size, drawn from their CSVs (figure_revision_plan.md).

Usage: python 10-31-26/scripts/v2_f10_combined.py   (after v2_f10.py, from the IMPACT folder)
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from v2_common import ORANGE, SKY, V2, save

BLUE, VERMILION, GREEN, GRAY, INK, MUTED, GOLD = "#0072B2", "#D55E00", "#009E73", "#8C8C8C", "#222222", "#666666", "#B97F00"
plt.rcParams.update({"font.family": "Arial", "font.size": 7.5, "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.5, "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK,
                     "ytick.labelcolor": INK, "legend.frameon": False, "savefig.dpi": 300, "pdf.fonttype": 42, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7})
REGIONS = [("USA", BLUE), ("Canada", SKY), ("Europe", ORANGE), ("China", VERMILION), ("Other Asia", GREEN), ("Rest of world", GRAY)]
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)
T = dict(loc="left", fontsize=9)


def rd(n):
    return list(csv.DictReader(open(os.path.join(V2, "data", n + ".csv"))))


def panels_ab(fig, spec):
    a = rd("f10a_alt7a_citing_regions")
    rates = {}
    for r in rd("f10a_alt7b_rates"):
        rates[r["us_journal"]] = float(r["us_rate"]); rates[r["eu_journal"]] = float(r["eu_rate"])
    g = spec.subgridspec(1, 2, wspace=0.07, width_ratios=[4.2, 1])
    ax, bx = fig.add_subplot(g[0]), fig.add_subplot(g[1])
    y, ticks, labels = 0, [], []
    for i, r in enumerate(a):
        left = 0
        for name, color in REGIONS:
            v = float(r[name])
            ax.barh(y, v, left=left, color=color, height=0.84, edgecolor="white", linewidth=0.4)
            if v >= 0.07:
                ax.text(left + v / 2, y, f"{v:.0%}", ha="center", va="center", fontsize=6, color="white" if color in (BLUE, VERMILION, GREEN, GRAY) else INK)
            left += v
        bx.barh(y, rates[r["journal"]], color=BLUE if i % 2 == 0 else GOLD, height=0.84)
        bx.text(rates[r["journal"]] + 0.8, y, f"{rates[r['journal']]:.1f}", va="center", fontsize=6.2, color=INK)
        ticks.append(y); labels.append(r["journal"].replace("Am J Respir Crit Care Med", "AJRCCM"))
        y -= 1
        if i % 2:
            y -= 0.5
    ax.set_yticks(ticks, labels, fontsize=7)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(y + 0.9, 0.7)
    bx.set_ylim(*ax.get_ylim())
    bx.set_yticks([])
    bx.grid(axis="y", visible=False)
    bx.spines["left"].set_visible(False)
    bx.set_xlim(0, 62)
    bx.set_xlabel("24-month rate")
    ax.set_xlabel("Share of 2024 citations, by country or region of citing authors")
    ax.legend(handles=[matplotlib.patches.Patch(color=c, label=n) for n, c in REGIONS], ncol=6, fontsize=7, loc="lower left", bbox_to_anchor=(0, 1.0), handlelength=1, columnspacing=1, borderaxespad=0.1)
    ax.set_title("A  Citing authors of society journals based in the US and Europe", pad=17, **T)
    bx.set_title("B  Rate", pad=17, **T)


def panels_cd(fig, spec):
    b = rd("f10b_fig13_us_vs_europe")
    g = spec.subgridspec(1, 2, wspace=0.06, width_ratios=[1.7, 1])
    ax, bx = fig.add_subplot(g[0]), fig.add_subplot(g[1])
    y, ticks, names = 0, [], []
    for level, head in (("Flagship", "Flagship journals"), ("Sister", "Sister journals")):
        ax.text(-0.03, y, head, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=7, fontweight="bold", color=INK)
        y += 1
        for r in sorted((r for r in b if r["level"] == level), key=lambda r: -float(r["gap_points"])):
            p = float(r["us_journal_us_share"]) - float(r["us_journal_europe_share"])
            q = float(r["european_journal_us_share"]) - float(r["european_journal_europe_share"])
            ax.plot([100 * p, 100 * q], [y, y], color=GRAY, linewidth=1, zorder=1)
            ax.scatter(100 * p, y, s=20, color=BLUE, zorder=2, edgecolor="white", linewidth=0.4)
            ax.scatter(100 * q, y, s=20, color=GOLD, zorder=2, edgecolor="white", linewidth=0.4)
            a_, b_ = float(r["us_journal_rate"]), float(r["european_journal_rate"])
            bx.plot([a_, b_], [y, y], color=GRAY, linewidth=1, zorder=1)
            bx.scatter(a_, y, s=20, color=BLUE, zorder=2, edgecolor="white", linewidth=0.4)
            bx.scatter(b_, y, s=20, color=GOLD, zorder=2, edgecolor="white", linewidth=0.4)
            ticks.append(y); names.append(f"{r['us_journal']} / {r['european_journal']}")
            y += 1
        y += 0.4
    ax.set_yticks(ticks, names, fontsize=6.3)
    ax.set_ylim(y - 0.5, -0.8)
    ax.axvline(0, color=INK, linewidth=0.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(-40, 18)
    ax.set_xticks([-40, -20, 0])
    ax.set_xlabel("USA minus Europe, citing\nshare (points)")
    bx.set_xscale("log")
    bx.set_xticks([3, 10, 30], ["3", "10", "30"])
    bx.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    bx.set_ylim(*ax.get_ylim())
    bx.set_yticks([])
    bx.grid(axis="y", visible=False)
    bx.spines["left"].set_visible(False)
    bx.set_xlabel("24-month rate\n(log scale)")
    ax.legend(handles=[matplotlib.lines.Line2D([], [], marker="o", linestyle="", color=c, markersize=4, label=n) for n, c in (("US journal", BLUE), ("European journal", GOLD))],
              fontsize=6.5, loc="lower left", bbox_to_anchor=(-0.02, 0.985), ncol=2, handletextpad=0.1, columnspacing=0.8, borderaxespad=0)
    ax.set_title("C  Citing share, 17 pairs", x=-1.3, pad=14, **T)
    bx.set_title("D  Rate", pad=14, **T)


def panel_e(fig, spec):
    c = rd("f10c_regional_journals")
    counts = {x["region"]: x for x in rd("f10c_region_counts")}
    ax = fig.add_subplot(spec)
    y, ticks, labels = 0, [], []
    for region in counts:
        w = float(counts[region]["world_citing_share"])
        ax.text(-0.03, y, f"{region} ({int(counts[region]['journals']):,})", transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=7, fontweight="bold", color=INK)
        ax.scatter([w], [y], marker="v", s=14, color=INK, zorder=3)
        y += 1
        y0 = y
        for r in (x for x in c if x["region"] == region):
            a, b = float(r["author_share"]), float(r["citing_share"])
            ax.plot([a, b], [y, y], color=GRAY, linewidth=1, zorder=1)
            ax.scatter(a, y, s=17, color=GREEN, zorder=2, edgecolor="white", linewidth=0.4)
            ax.scatter(b, y, s=17, color=VERMILION, zorder=2, edgecolor="white", linewidth=0.4)
            ticks.append(y); labels.append(f"({float(r['rate_24_month']):.1f}) {r['journal']}")
            y += 1
        ax.plot([w, w], [y0 - 0.6, y - 0.5], color=INK, linewidth=0.6, linestyle=(0, (2, 2)), zorder=1)
        y += 0.35
    ax.set_yticks(ticks, labels, fontsize=6.3)
    ax.set_ylim(y - 0.5, -0.8)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share from the journal's home region")
    L = matplotlib.lines.Line2D
    ax.legend(handles=[L([], [], marker="o", linestyle="", color=GREEN, markersize=4, label="Authors"), L([], [], marker="o", linestyle="", color=VERMILION, markersize=4, label="Citers"),
                       L([], [], marker="v", linestyle="", color=INK, markersize=4, label="Region, all citations")],
              fontsize=6.5, loc="lower left", bbox_to_anchor=(-0.05, 0.985), ncol=3, handletextpad=0.1, columnspacing=0.7, borderaxespad=0)
    ax.set_title("E  Top journals of each region", x=-0.82, pad=14, **T)


def main():
    fig = plt.figure(figsize=(7.6, 11.0))
    gs = fig.add_gridspec(2, 1, left=0.135, right=0.985, top=0.945, bottom=0.05, hspace=0.17, height_ratios=[0.62, 1])
    panels_ab(fig, gs[0])
    low = gs[1].subgridspec(1, 2, wspace=0.78, width_ratios=[1.3, 1])
    panels_cd(fig, low[0])
    panel_e(fig, low[1])
    save(fig, "F10_geography")


if __name__ == "__main__":
    main()
