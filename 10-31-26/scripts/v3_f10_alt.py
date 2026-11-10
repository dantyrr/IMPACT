"""F10 alternative, absolute numbers (v3): citations to each society journal by the region of the citing authors, by year.
As v2_f10_alt.py, with citations in place of shares, each journal on its own scale.

Citations in year Y to citable items from Y-2 and Y-1, 2014-25. Earlier years are left out because PubMed stored only the first
author's affiliation before 2014, so shares from those years aren't comparable. 2025 is from citations so far.

Usage: python 10-31-26/scripts/v2_f10_alt.py   (after v2_citing_by_year.py, from the IMPACT folder)
"""
import collections
import os
import pickle
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

os.environ.setdefault("FIG_DIR", "v3")
from v2_common import ORANGE, ROOT, SKY, save, swatch_label, write_csv

BLUE, VERMILION, GREEN, GRAY, INK, MUTED = "#0072B2", "#D55E00", "#009E73", "#8C8C8C", "#222222", "#666666"
plt.rcParams.update({"font.family": "Arial", "font.size": 7.5, "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "xtick.color": MUTED,
                     "ytick.color": MUTED, "xtick.labelcolor": INK, "ytick.labelcolor": INK, "legend.frameon": False, "savefig.dpi": 300, "pdf.fonttype": 42})
FIRST, LAST = 2014, 2025
REGIONS = [("USA", BLUE), ("Canada", SKY), ("Europe", ORANGE), ("China", VERMILION), ("Other Asia", GREEN), ("Rest of world", GRAY)]
PAIRS = [("circulation", "Circulation", "european-heart-journal", "Eur Heart J"), ("circulation-research", "Circ Res", "cardiovascular-research", "Cardiovasc Res"),
         ("arteriosclerosis-thrombosis-and-vascular-biology", "ATVB", "atherosclerosis", "Atherosclerosis"),
         ("journal-of-clinical-oncology-official-journal-of-the-american-society-of-clinical-oncology", "J Clin Oncol", "annals-of-oncology", "Ann Oncol"),
         ("gastroenterology", "Gastroenterology", "gut", "Gut"), ("hepatology-baltimore-md", "Hepatology", "journal-of-hepatology", "J Hepatol"), ("diabetes-care", "Diabetes Care", "diabetologia", "Diabetologia"),
         ("american-journal-of-respiratory-and-critical-care-medicine", "AJRCCM", "the-european-respiratory-journal", "Eur Respir J"),
         ("arthritis-rheumatology-hoboken-n-j", "Arthritis Rheumatol", "annals-of-the-rheumatic-diseases", "Ann Rheum Dis"), ("blood", "Blood", "haematologica", "Haematologica"),
         ("neurology", "Neurology", "european-journal-of-neurology", "Eur J Neurol")]


def regions():
    src = open(os.path.join(os.path.dirname(__file__), "alt_figures.py")).read()
    ns = {}
    exec(src[re.search(r"^EUROPE *=", src, re.M).start():src.index("REGIONS = [")], ns)
    return ns


def main():
    R = pickle.load(open(os.path.join(ROOT, "data", "analysis", "citing_geo_by_year.pkl"), "rb"))
    ns = regions()

    def region(c):
        return c if c in ("USA", "Canada") else "Europe" if c in ns["EUROPE"] else "China" if c in ns["CHINA"] else "Other Asia" if c in ns["ASIA"] else "Rest of world"

    years = np.arange(FIRST, LAST + 1)
    fig = plt.figure(figsize=(7.6, 8.8))
    gs = fig.add_gridspec(4, 6, left=0.07, right=0.99, top=0.925, bottom=0.04, hspace=0.42, wspace=0.42)
    rows = []
    for k, (us, a, eu, b) in enumerate(PAIRS):
        for i, (slug, name) in enumerate(((us, a), (eu, b))):
            ax = fig.add_subplot(gs[k // 3, (k % 3) * 2 + i])
            M = np.zeros((len(REGIONS), len(years)))
            for t, y in enumerate(years):
                r = R.get((slug, int(y)))
                if not r:
                    continue
                c = collections.Counter()
                for country, v in r["countries"].items():
                    c[region(country)] += v
                M[:, t] = [c[g] for g, _ in REGIONS]
                rows.append([name, int(y), r["citations"], r["located"], *[round(float(v), 1) for v in M[:, t]]])
            has = M.sum(axis=0) > 0            # Arthritis Rheumatol has no items before its 2014 change of name
            ax.stackplot(years[has], M[:, has], colors=[c for _, c in REGIONS], linewidth=0)
            ax.set_xlim(FIRST, LAST)
            ax.set_ylim(0, None)
            ax.set_xticks([2015, 2025], ["2015", "2025"])
            ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
            ax.tick_params(labelsize=6.3, pad=1.5)
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 10000 else f"{v:,.0f}"))
            swatch_label(ax, 1.06, name, BLUE if i == 0 else ORANGE, fontsize=7.3)
    write_csv("f10alt_citations_by_region_by_year", ["journal", "citation_year", "citations", "located", *[g for g, _ in REGIONS]], rows)
    fig.legend(handles=[matplotlib.patches.Patch(color=c, label=n) for n, c in REGIONS][::-1], ncol=6, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.53, 0.995), handlelength=1, columnspacing=1.2)
    fig.text(0.53, 0.955, "US journal (blue square) beside European journal (yellow square)", fontsize=7, color=MUTED, ha="center")
    save(fig, "F10_alt_citers_absolute")


if __name__ == "__main__":
    main()
