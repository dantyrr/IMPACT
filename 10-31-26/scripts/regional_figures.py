"""Who writes and who cites journals outside the US-Europe comparison. Reads data/analysis/country_matrix.npz
(country_matrix.py): citable items from 2022-23 and the citations they got in 2024, each paper split equally across its
authors' countries. Journals need 100+ items, 200+ citations, and located authors on 80%+ of items and citing papers
(records from some publishers, such as IEEE, have no affiliations), and reference lists on 50%+ of their 2022-24 items
(reference_coverage.py).

A journal's home region is the region with 50%+ of its author share. Comparison is with the region's share of all citations.

fig15_regional_journals   the five journals of each region with the highest 24-month rate
fig16_home_citing         every region's journals, home citing share against the world share
fig17_china_cites         China's share of authors and of citers: Cell Press, flagships, and the largest gaps

Usage: python 10-31-26/scripts/regional_figures.py   (from the IMPACT folder)
"""
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
OUT = os.path.join(ROOT, "10-31-26")
AFRICA = set("Algeria Angola Benin Botswana Burundi Cameroon Chad Comoros Congo Djibouti Egypt Eritrea Eswatini Ethiopia Gabon "
             "Gambia Ghana Guinea Kenya Lesotho Liberia Libya Madagascar Malawi Mali Mauritania Mauritius Morocco Mozambique "
             "Namibia Niger Nigeria Rwanda Senegal Seychelles Somalia Sudan Tanzania Togo Tunisia Uganda Zambia "
             "Zimbabwe".split()) | {"Burkina Faso", "Cabo Verde", "Central African Republic", "Cote d'Ivoire",
                                    "Democratic Republic of the Congo", "Equatorial Guinea", "Guinea-Bissau", "Sierra Leone",
                                    "South Africa", "South Sudan"}
src = open(os.path.join(os.path.dirname(__file__), "alt_figures.py")).read()
ns = {}
exec(src[re.search(r"^EUROPE *=", src, re.M).start():src.index("REGIONS = [")], ns)
REGIONS = {"China": set(ns["CHINA"]), "Japan": {"Japan"}, "South Korea": {"South Korea"}, "India": {"India"},
           "Brazil": {"Brazil"}, "Africa": AFRICA}
ALL = {**REGIONS, "USA": {"USA"}, "Europe": set(ns["EUROPE"])}

from type_effect import CITABLE, JSON, rate as rolling_rate, settled_month  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
plt.rcParams.update({"font.family": "Arial", "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "axes.edgecolor": "#666666",
                     "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#E6E6E6", "grid.linewidth": 0.5, "axes.axisbelow": True, "xtick.color": "#666666",
                     "ytick.color": "#666666", "xtick.labelcolor": "#222222", "ytick.labelcolor": "#222222",
                     "legend.frameon": False, "savefig.dpi": 300, "pdf.fonttype": 42})
BLUE, VERMILION, GREEN, GRAY, INK, MUTED = "#0072B2", "#D55E00", "#009E73", "#8C8C8C", "#222222", "#666666"
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)

z = np.load(os.path.join(ROOT, "data", "analysis", "country_matrix.npz"))
names = z["countries"].astype(str)
cite, auth, cn, an, cl, al = z["cite"], z["auth"], z["cite_n"], z["auth_n"], z["cite_located"], z["auth_located"]
con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
abbr = {r[0]: r[1] for r in con.execute("SELECT id, abbreviation FROM journals")}
slug = {r[0]: r[1] for r in con.execute("SELECT id, slug FROM journals")}
by = {v: k for k, v in abbr.items()}
rate = np.divide(cn, an, out=np.zeros(len(cn)), where=an > 0)
located = (al >= 0.8 * an) & (cl >= 0.8 * cn) & (an > 0)
cov = np.load(os.path.join(ROOT, "data", "analysis", "reference_coverage.npz"))
refs = np.divide(cov["with_refs"][:len(cn)], cov["items"][:len(cn)], out=np.zeros(len(cn)), where=cov["items"][:len(cn)] > 0)
OK = (an >= 100) & (cn >= 200) & located & (refs >= 0.5)


def share(M, s):
    t = M.sum(axis=1)
    return np.divide(M[:, np.isin(names, list(s))].sum(axis=1), t, out=np.zeros(len(t)), where=t > 0)


def world(s):
    return cite[:, np.isin(names, list(s))].sum() / cite.sum()


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".png"), bbox_inches="tight")
    fig.savefig(os.path.join(OUT, name + ".pdf"), bbox_inches="tight")
    print("  wrote", name)


def write_csv(name, header, rows):
    import csv
    with open(os.path.join(OUT, "data", name + ".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def rate24(j):
    """The 24-month rolling rate at the settled month, as on the site."""
    d = json.load(open(os.path.join(JSON, slug[int(j)] + ".json")))
    e = next(p for p in d["timeseries"] if p["month"] == settled_month(d))
    return rolling_rate(e, CITABLE) or 0.0


def fig15():
    fig, ax = plt.subplots(figsize=(6.0, 7.6))
    y, ticks, labels, rows = 0, [], [], []
    for region, s in REGIONS.items():
        a, c = share(auth, s), share(cite, s)
        ids = np.flatnonzero(OK & (a >= 0.5))
        r24 = {int(j): rate24(j) for j in ids}
        top = sorted(r24, key=lambda j: -r24[j])[:5]
        w = world(s)
        ax.text(-0.02, y, f"{region}: {len(ids)} journals, {w:.1%} of all citations", transform=ax.get_yaxis_transform(),
                fontsize=7, fontweight="bold", color=INK, ha="right", va="center", clip_on=False)
        y += 1
        y0 = y
        for j in top:
            ax.plot([a[j], c[j]], [y, y], color=GRAY, linewidth=1.1, zorder=1)
            ax.scatter(a[j], y, color=GREEN, s=26, zorder=2, edgecolor="white", linewidth=0.5)
            ax.scatter(c[j], y, color=VERMILION, s=26, zorder=2, edgecolor="white", linewidth=0.5)
            ticks.append(y); labels.append(f"({r24[j]:.1f}) {abbr[j]}")
            rows.append([region, abbr[j], int(an[j]), round(r24[j], 3), round(a[j], 4), round(c[j], 4), round(w, 4)])
            y += 1
        ax.plot([w, w], [y0 - 0.5, y - 0.5], color=INK, linewidth=1.2, zorder=3)
        y += 0.5
    ax.set_yticks(ticks, labels, fontsize=6.4)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share from the journal's home region")
    ax.text(-0.02, 1.012, "(24-month rate, Nov 2025) Journal", transform=ax.transAxes, fontsize=6.5, color=MUTED, ha="right", va="bottom")
    ax.scatter([], [], color=GREEN, s=26, label="Authors")
    ax.scatter([], [], color=VERMILION, s=26, label="Citers")
    ax.plot([], [], color=INK, linewidth=1.2, label="Region's share of all citations")
    ax.legend(fontsize=6.5, loc="lower right", bbox_to_anchor=(1.02, 1.0), ncol=3, handletextpad=0.2, columnspacing=0.9)
    write_csv("fig15_regional_journals", ["region", "journal", "citable_items", "rate_24_month", "author_share", "citing_share", "world_citing_share"], rows)
    save(fig, "fig15_regional_journals")


def fig16():
    rows = []
    for region, s in ALL.items():
        a, c = share(auth, s), share(cite, s)
        ids = np.flatnonzero(OK & (a >= 0.5))
        q1, med, q3 = np.percentile(c[ids], [25, 50, 75])
        rows.append([region, len(ids), world(s), q1, med, q3, med / world(s), np.median(a[ids]), np.median(rate[ids])])
    rows.sort(key=lambda r: r[6])
    fig, ax = plt.subplots(figsize=(6.2, 3.1))
    yy = np.arange(len(rows))
    for y, r in zip(yy, rows):
        ax.plot([r[3], r[5]], [y, y], color=VERMILION, linewidth=3, alpha=0.35, solid_capstyle="butt", zorder=1)
        ax.scatter(r[4], y, color=VERMILION, s=30, zorder=3, edgecolor="white", linewidth=0.5)
        ax.scatter(r[2], y, color=INK, s=24, marker="D", zorder=3, edgecolor="white", linewidth=0.5)
        ax.text(1.02, y, f"{r[6]:.1f}×", transform=ax.get_yaxis_transform(), fontsize=6.8, color=INK, va="center", ha="left")
    ax.text(1.02, len(rows) - 0.35, "Median ÷\nworld", transform=ax.get_yaxis_transform(), fontsize=6.2, color=MUTED, va="bottom", ha="left")
    ax.set_yticks(yy, [f"{r[0]} ({r[1]:,} journals)" for r in rows], fontsize=7)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share of a journal's citations from its home region")
    ax.scatter([], [], color=VERMILION, s=30, label="Median journal (band: middle half)")
    ax.scatter([], [], color=INK, s=24, marker="D", label="Region's share of all citations")
    ax.legend(fontsize=6.5, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handletextpad=0.2, columnspacing=1.0)
    write_csv("fig16_home_citing", ["region", "journals", "world_citing_share", "q1", "median", "q3", "median_over_world", "median_author_share", "median_rate"],
              [[r[0], r[1]] + [round(x, 4) for x in r[2:]] for r in rows[::-1]])
    save(fig, "fig16_home_citing")


CELL_PRESS = ["Cell", "Cancer Cell", "Cell Metab", "Immunity", "Cell Stem Cell", "Cell Host Microbe", "Mol Cell", "Cell Rep Med",
              "Cell Rep", "Dev Cell", "iScience", "Neuron", "Curr Biol"]
FLAGSHIPS = ["Nature", "Science", "NEJM", "Lancet", "JAMA", "Nat Commun", "Sci Adv"]
CHINA_RUN = ["Cell Res", "Cell Mol Immunol", "Cell Discov", "Protein Cell"]


def fig17():
    s = REGIONS["China"]
    a, c = share(auth, s), share(cite, s)
    w = world(s)
    big = np.flatnonzero(OK & (an >= 300) & (cn >= 1000))
    gap = big[np.argsort(-(c[big] - a[big]))][:12]
    groups = [("Cell Press journals (100+ items)", sorted([by[n] for n in CELL_PRESS if n in by], key=lambda j: -c[j])),
              ("Other flagship and sibling journals", sorted([by[n] for n in FLAGSHIPS if n in by], key=lambda j: -c[j])),
              ("China-based journals with “Cell” in the name", sorted([by[n] for n in CHINA_RUN if n in by and an[by[n]] > 0], key=lambda j: -c[j])),
              (f"Largest gaps, of {len(big):,} journals with 300+ items", [int(j) for j in gap])]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 7.4), sharey=True, gridspec_kw={"width_ratios": [1.6, 1], "wspace": 0.06})
    y, ticks, labels, rows = 0, [], [], []
    for head, ids in groups:
        axes[0].text(-0.02, y, head, transform=axes[0].get_yaxis_transform(), fontsize=7, fontweight="bold", color=INK, ha="right", va="center", clip_on=False)
        y += 1
        for j in ids:
            axes[0].plot([a[j], c[j]], [y, y], color=GRAY, linewidth=1.1, zorder=1)
            axes[0].scatter(a[j], y, color=GREEN, s=26, zorder=2, edgecolor="white", linewidth=0.5)
            axes[0].scatter(c[j], y, color=VERMILION, s=26, zorder=2, edgecolor="white", linewidth=0.5)
            axes[1].scatter(rate[j], y, color=BLUE, s=22, zorder=2, edgecolor="white", linewidth=0.5)
            ticks.append(y); labels.append(abbr[int(j)])
            rows.append([head, abbr[int(j)], int(an[j]), round(rate[j], 3), round(a[j], 4), round(c[j], 4)])
            y += 1
        y += 0.5
    ax = axes[0]
    ax.axvline(w, color=INK, linewidth=0.9, linestyle="--", zorder=0)
    ax.set_yticks(ticks, labels, fontsize=6.4)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share from China")
    ax.scatter([], [], color=GREEN, s=26, label="Authors")
    ax.scatter([], [], color=VERMILION, s=26, label="Citers")
    ax.plot([], [], color=INK, linewidth=0.9, linestyle="--", label=f"China's share of all citations, {w:.0%}")
    ax.legend(fontsize=6.5, loc="lower right", bbox_to_anchor=(1.02, 1.0), ncol=3, handletextpad=0.2, columnspacing=0.9)
    ax.set_title("A", loc="left", fontsize=8.5)
    ax = axes[1]
    ax.set_xscale("log")
    ax.set_xticks([2, 5, 10, 20, 50], ["2", "5", "10", "20", "50"])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlim(1.6, 60)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("JIF-style rate, 2024 (log scale)")
    ax.set_title("B", loc="left", fontsize=8.5)
    write_csv("fig17_china_cites", ["group", "journal", "citable_items", "rate", "china_author_share", "china_citing_share"], rows)
    save(fig, "fig17_china_cites")
    for r in rows:
        print(r[1:])
    big2 = big[a[big] < 0.25]
    print("journals with China author share under 25%:", len(big2), "median citers", np.median(c[big2]), "median authors", np.median(a[big2]))
    hi = big2[rate[big2] >= 15]; lo = big2[rate[big2] < 5]
    print("rate>=15:", len(hi), np.median(c[hi]), np.median(a[hi]), "rate<5:", len(lo), np.median(c[lo]), np.median(a[lo]))
    print(np.corrcoef(np.log(rate[big2]), c[big2])[0, 1])


if __name__ == "__main__":
    fig15(); fig16(); fig17()
