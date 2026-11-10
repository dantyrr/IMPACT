"""F10: geography (figure_revision_plan.md, Task 10). Replaces alt7, Fig 13 and Fig 15.

F10a  alt7, read at Nov 2025. F10b  Fig 13 with no journal picked out. F10c  Fig 15 by region, not hand-picked countries.
A journal's home region is the region with 50%+ of its authors, not where it is based.

Usage: python 10-31-26/scripts/v2_f10.py   (from the IMPACT folder)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import alt_figures as A  # noqa: E402
import ranked_figures as RF  # noqa: E402
import regional_figures as G  # noqa: E402
from make_figures import GRAY, GREEN, INK, MUTED, VERMILION, matplotlib, np, plt  # noqa: E402
from v2_common import SETTLED, save, write_csv  # noqa: E402

SOUTH_AMERICA = {"Brazil", "Argentina", "Chile", "Colombia", "Peru", "Ecuador", "Venezuela", "Uruguay", "Bolivia", "Paraguay", "Guyana", "Suriname"}
SOUTH_ASIA = {"India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Bhutan", "Maldives", "Afghanistan"}
EAST_ASIA = set(A.CHINA) | {"Japan", "South Korea", "North Korea", "Taiwan", "Mongolia"}
REGIONS = {"North America": {"USA", "Canada", "Mexico"}, "Europe": set(A.EUROPE), "East Asia": EAST_ASIA, "South Asia": SOUTH_ASIA,
           "South America": SOUTH_AMERICA, "Oceania": {"Australia", "New Zealand", "Fiji", "Papua New Guinea"}, "Africa": G.AFRICA}


PADS = {"alt7_us_vs_european_society_journals": 22, "fig13_us_vs_europe": 18}
TITLES = {"A  Where citations come from (US journal above, European below)": "A  Country or region of citing authors",
          "A  Where citations come from": "A  Country or region of citing authors", "B  Citation rate": "B  24-month citation rate"}


def rename(mapping):
    def out(fig, name):
        for ax in fig.axes:
            t = ax.get_title(loc="left")
            if t in TITLES:
                ax.set_title(TITLES[t], loc="left", fontsize=8.5, pad=PADS.get(name, 6))
        save(fig, mapping.get(name, name))
    return out


def f10c():
    fig, ax = plt.subplots(figsize=(6.0, 8.8))
    y, ticks, labels, rows, counts = 0, [], [], [], []
    for region, s in REGIONS.items():
        a, c = G.share(G.auth, s), G.share(G.cite, s)
        ids = np.flatnonzero(G.OK & (a >= 0.5))
        r24 = {int(j): G.rate24(j) for j in ids}
        top = sorted(r24, key=lambda j: -r24[j])[:5]
        w = G.world(s)
        counts.append([region, len(ids), round(w, 4)])
        ax.text(-0.02, y, f"{region}: {len(ids):,} journal{'' if len(ids) == 1 else 's'}", transform=ax.get_yaxis_transform(), fontsize=7, fontweight="bold",
                color=INK, ha="right", va="center", clip_on=False)
        ax.scatter([w], [y], marker="v", s=22, color=INK, zorder=3)
        ax.text(w + 0.012, y, f"{w:.1%} of all citations", fontsize=6, color=INK, va="center")
        y += 1
        y0 = y
        for j in top:
            ax.plot([a[j], c[j]], [y, y], color=GRAY, linewidth=1.1, zorder=1)
            ax.scatter(a[j], y, color=GREEN, s=26, zorder=2, edgecolor="white", linewidth=0.5)
            ax.scatter(c[j], y, color=VERMILION, s=26, zorder=2, edgecolor="white", linewidth=0.5)
            ticks.append(y); labels.append(f"({r24[j]:.1f}) {G.abbr[j]}")
            rows.append([region, G.abbr[j], int(G.an[j]), round(r24[j], 3), round(float(a[j]), 4), round(float(c[j]), 4), round(w, 4)])
            y += 1
        ax.plot([w, w], [y0 - 0.5, y - 0.5], color=INK, linewidth=0.7, linestyle=(0, (2, 2)), zorder=1)
        y += 0.5
    ax.set_yticks(ticks, labels, fontsize=6.4)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share from the journal's home region (home: the region of 50%+ of its authors)")
    ax.text(-0.02, 1.012, "(24-month rate, Nov 2025) Journal", transform=ax.transAxes, fontsize=6.5, color=MUTED, ha="right", va="bottom")
    ax.scatter([], [], color=GREEN, s=26, label="Authors")
    ax.scatter([], [], color=VERMILION, s=26, label="Citers")
    ax.scatter([], [], marker="v", s=22, color=INK, label="Region's share of all citations, the same for every journal in it")
    ax.legend(fontsize=6.2, loc="lower right", bbox_to_anchor=(1.02, 1.0), ncol=3, handletextpad=0.2, columnspacing=0.9, frameon=False)
    write_csv("f10c_regional_journals", ["region", "journal", "citable_items", "rate_24_month", "author_share", "citing_share", "world_citing_share"], rows)
    write_csv("f10c_region_counts", ["region", "journals", "world_citing_share"], counts)
    print(counts, flush=True)
    save(fig, "F10c_regions")


def main():
    A.SETTLED = SETTLED
    A.save = rename({"alt7_us_vs_european_society_journals": "F10a_us_vs_europe_by_field"})
    A.write_csv = lambda n, h, r: write_csv("f10a_" + n, h, r)
    A.alt7()
    RF.HIGHLIGHT = set()
    RF.save = rename({"fig13_us_vs_europe": "F10b_home_region_gap"})
    RF.write_csv = lambda n, h, r: write_csv("f10b_" + n, h, r)
    RF.fig13()
    f10c()


if __name__ == "__main__":
    main()
