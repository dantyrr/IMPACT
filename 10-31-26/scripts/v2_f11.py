"""F11: institutions and authors (figure_revision_plan.md, Task 11). Replaces Fig 5 and Fig 4.

Institutions with 1,000+ papers, 2021-25, pooled across Nature, Science, Cell, NEJM and Lancet.
A  every institution: share of links, all journals against flagships; size, flagship papers; colour, region. Links, not papers,
   because flagship papers list more institutions
B  each region's share of institution links, all journals against each flagship
C  how concentrated each journal is, against a same-sized random draw from all journals
D  share of large institutions with a paper in each journal, by how their share there compares with their share of all links
E, F  very long author lists (Fig 4 without its Autophagy Guidelines panel)

Usage: python 10-31-26/scripts/v2_f11.py   (from the IMPACT folder)
"""
import csv
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(__file__))
import alt_figures as AF  # noqa: E402
from make_figures import BLUE, VERMILION, GREEN, GRAY, INK, MUTED, DATA, SYSTEM_NAMES, inst_label, matplotlib, np, plt  # noqa: E402
from v2_common import ORANGE, ROOT, SKY, save, write_csv  # noqa: E402

NOT_PLACES = {"independent researcher", "private practice", "independent consultant", "london", "melbourne", "sao paulo", "internal medicine", "mc",
              "dentistry and pharmaceutical sciences", "ciudad universitaria", "irccs", "partner site munich heart alliance"}
REGIONS = [("North America", BLUE), ("Europe", ORANGE), ("China", VERMILION), ("Other Asia", GREEN), ("Rest of world", GRAY)]
COLOR = dict(REGIONS)
NAMES = {"nature": "Nature", "science": "Science", "cell": "Cell", "nejm": "NEJM", "lancet": "Lancet"}


def region(country):
    if country in ("USA", "Canada"):
        return "North America"
    if country in AF.EUROPE:
        return "Europe"
    if country in AF.CHINA:
        return "China"
    if country in AF.ASIA:
        return "Other Asia"
    return "Rest of world"


def institutions():
    d = pickle.load(open(os.path.join(DATA, "institutions.pkl"), "rb"))
    c = pickle.load(open(os.path.join(DATA, "inst_country.pkl"), "rb"))["countries"]
    keys, A = d["keys"], d["all"]
    N = sum(d["j"].values())
    rows = []
    for i in np.flatnonzero(A >= 1000):
        k = keys[i]
        if k in SYSTEM_NAMES or k in NOT_PLACES or k not in c:
            continue
        country, n = c[k].most_common(1)[0]
        if n / sum(c[k].values()) < 0.8:
            continue
        rows.append((i, k, country, region(country)))
    return d, N, rows


def main():
    d, N, rows = institutions()
    idx = np.array([r[0] for r in rows])
    reg = np.array([r[3] for r in rows])
    # Link shares: flagship papers list more institutions per paper, so shares of papers would put every institution above the line.
    x = d["all"][idx] / d["all"][idx].sum()
    y = N[idx] / N[idx].sum()
    floor_n = N[idx].sum()
    print(len(rows), "institutions", flush=True)
    ratio = y / x
    write_csv("f11a_institutions", ["institution", "country", "region", "papers_all_journals", "flagship_papers", "share_all", "share_flagship", "ratio"],
              [[r[1], r[2], r[3], int(d["all"][r[0]]), int(N[r[0]]), round(float(a), 6), round(float(b), 6), round(float(q), 3)] for r, a, b, q in zip(rows, x, y, ratio)])

    fig = plt.figure(figsize=(7.2, 11.2))
    gs = fig.add_gridspec(3, 1, hspace=0.32, height_ratios=[1.35, 1, 0.72])
    top = gs[0].subgridspec(1, 2, wspace=0.1, width_ratios=[1.75, 1])

    ax = fig.add_subplot(top[0])
    floor = 0.5 / floor_n
    for name, color in REGIONS:
        m = reg == name
        yy = np.maximum(y[m], floor)
        ax.scatter(x[m], yy, s=3 + 2.2 * np.sqrt(N[idx][m]) * 1.4, color=color, alpha=0.55, linewidths=0, label=name)
    lim = np.array([1e-4, 4e-2])
    ax.plot(lim, lim, color=INK, linewidth=0.7, linestyle=(0, (3, 2)))
    ax.text(2.4e-2, 1.75e-2, "equal share", fontsize=5.8, color=MUTED, rotation=33, ha="center", va="top")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(*lim); ax.set_ylim(floor * 0.7, 0.13)
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:g}%")
    ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
    ax.set_xlabel("Share of institution links, all PubMed journals")
    ax.set_ylabel("Share of institution links, five flagship journals")
    ax.legend(fontsize=6, loc="upper left", markerscale=1, handletextpad=0.1)
    for h in ax.get_legend().legend_handles:
        h.set_sizes([24]); h.set_alpha(1)
    none = int((N[idx] == 0).sum())
    ax.text(0.98, 0.03, f"Flagships: Nature, Science, Cell, NEJM, Lancet.\nA link is one institution on one paper.\n{len(rows):,} institutions with 1,000+ papers.\nBottom row: {none:,} with no flagship paper.\nDot size: flagship papers.", transform=ax.transAxes, ha="right", va="bottom", fontsize=6, color=INK)
    order = [np.argsort(-(x * y)), np.argsort(-x), np.argsort(-y)]
    picks = []                       # the top on both, on x and on y, in turn, until ten are named
    for rank in range(len(x)):
        for o in order:
            if len(picks) < 10 and o[rank] not in picks:
                picks.append(o[rank])
    write_csv("f11a_labelled", ["institution", "country", "share_all", "share_flagship"], [[rows[i][1], rows[i][2], round(float(x[i]), 5), round(float(y[i]), 5)] for i in picks])
    # Named in the two empty corners, so the labels sit clear of the dots: well above the line top right, the rest lower right.
    high = sorted((i for i in picks if y[i] / x[i] >= 1.5), key=lambda i: x[i])
    rest = sorted((i for i in picks if y[i] / x[i] < 1.5), key=lambda i: -y[i])
    for group, x0, tops in ((high, 0.0062, np.geomspace(0.075, 0.021, len(high))), (rest, 0.0085, np.geomspace(0.0048, 0.0011, len(rest)))):
        for i, t in zip(group, tops):
            ax.scatter([x[i]], [y[i]], s=10, facecolors="none", edgecolors=INK, linewidth=0.6, zorder=5)
            name = inst_label(rows[i][1]).replace("University of Chinese Academy of Sciences", "Univ Chinese Acad Sci")
            ax.annotate(name, (x[i], y[i]), xytext=(x0, t), textcoords="data", fontsize=6, color=INK, va="center", zorder=6,
                        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.4, shrinkA=1, shrinkB=1, relpos=(0, 0.5)))
    ax.set_title("A  Institution links in all journals and in flagships, 2021–25", loc="left", fontsize=8.5)

    # B
    ax = fig.add_subplot(top[1])
    all_share = {n: d["all"][idx][reg == n].sum() / d["all"][idx].sum() for n, _ in REGIONS}
    out = []
    yy = np.arange(len(REGIONS))[::-1]
    for y0, (name, color) in zip(yy, REGIONS):
        m = reg == name
        vals = {j: d["j"][j][idx][m].sum() / d["j"][j][idx].sum() for j in d["journals"]}
        lo, hi = min(list(vals.values()) + [all_share[name]]), max(list(vals.values()) + [all_share[name]])
        ax.hlines(y0, lo, hi, color="#BBBBBB", linewidth=1)
        ax.scatter(list(vals.values()), [y0] * len(vals), s=15, color=color, alpha=0.75, linewidths=0, zorder=3)
        ax.scatter([all_share[name]], [y0], marker="D", s=26, color=INK, zorder=4)
        out.append([name, round(float(all_share[name]), 4), *[round(float(vals[j]), 4) for j in d["journals"]]])
    write_csv("f11b_regions", ["region", "all_journals", *d["journals"]], out)
    ax.set_yticks(yy, [n for n, _ in REGIONS], fontsize=6.5)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, None)
    ax.set_xlabel("Share of institution links")
    ax.scatter([], [], marker="D", s=20, color=INK, label="All journals")
    ax.scatter([], [], s=15, color=MUTED, label="Each flagship")
    ax.legend(fontsize=6, loc="lower right")
    ax.yaxis.tick_right()
    ax.set_title("B  Share of links by region", loc="left", fontsize=8.5)

    bot = gs[1].subgridspec(1, 2, wspace=0.3)
    # C
    ax = fig.add_subplot(bot[0])
    rng = np.random.default_rng(1)
    base = d["all"][idx] / d["all"][idx].sum()
    groups = [(NAMES[j], d["j"][j]) for j in d["journals"]]
    out = []
    for g, (name, v) in enumerate(groups):
        n = int(v[idx].sum())
        v = np.sort(v[idx])[::-1].astype(float)
        s = [v[:k].sum() / v.sum() for k in (10, 50, 100)]
        draws = np.sort(rng.multinomial(n, base, size=30), axis=1)[:, ::-1]
        e = [float((draws[:, :k].sum(axis=1) / n).mean()) for k in (10, 50, 100)]
        ax.vlines(g - 0.1, s[0], s[2], color="#BBBBBB", linewidth=1)
        ax.vlines(g + 0.14, e[0], e[2], color="#BBBBBB", linewidth=1)
        for val, exp_, marker, color in zip(s, e, ("o", "s", "D"), (BLUE, ORANGE, VERMILION)):
            ax.scatter(g - 0.1, val, s=20, marker=marker, color=color, zorder=3, linewidths=0)
            ax.scatter(g + 0.14, exp_, s=16, marker=marker, facecolors="none", edgecolors=color, zorder=3, linewidth=0.8)
        out.append([name, n, *[round(float(a), 4) for a in s], *[round(a, 4) for a in e]])
    write_csv("f11c_concentration", ["journal", "links", "top_10", "top_50", "top_100", "expected_top_10", "expected_top_50", "expected_top_100"], out)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups], fontsize=6.5)
    ax.set_ylim(0, 0.72)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Share of links to large institutions")
    L = matplotlib.lines.Line2D
    ax.legend(handles=[L([], [], marker=m, color=c, linestyle="", markersize=4, label=t) for m, c, t in (("D", VERMILION, "Its top 100"), ("s", ORANGE, "Top 50"), ("o", BLUE, "Top 10"))]
              + [L([], [], marker="o", markerfacecolor="none", color=MUTED, linestyle="", markersize=4, label="Open: a same-sized draw from all journals")],
              fontsize=5.8, loc="upper left", ncol=2, handletextpad=0.1, columnspacing=0.7)
    ax.set_title("C  Share of links from each journal's top institutions", loc="left", fontsize=8.5)

    # D
    ax = fig.add_subplot(bot[1])
    bands = (("under_1x", "Under 1×", SKY), ("from_1_to_5x", "1–5×", BLUE), ("over_5x", "Over 5×", VERMILION))
    out = []
    for g, j in enumerate(d["journals"]):
        n = d["j"][j][idx].astype(float)
        r = (n / n.sum()) / base
        none = float((n == 0).mean())
        shares = [float(((n > 0) & (r < 1)).mean()), float(((r >= 1) & (r <= 5)).mean()), float((r > 5).mean())]
        bottom = 0
        for v, (_, _, c) in zip(shares, bands):
            ax.bar(g, v, bottom=bottom, color=c, width=0.68, edgecolor="white", linewidth=0.5)
            if v >= 0.06:
                ax.text(g, bottom + v / 2, f"{v:.0%}", ha="center", va="center", fontsize=6, color="white" if c in (BLUE, VERMILION) else INK)
            bottom += v
        ax.text(g, bottom + 0.012, f"{bottom:.0%}", ha="center", va="bottom", fontsize=6.5, color=INK, fontweight="bold")
        out.append([NAMES[j], round(none, 4), *[round(v, 4) for v in shares]])
    write_csv("f11d_over_representation", ["journal", "none", *[b[0] for b in bands]], out)
    ax.set_xticks(range(5), [NAMES[j] for j in d["journals"]], fontsize=6.5)
    ax.set_ylim(0, 0.85)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="x", visible=False)
    ax.set_ylabel(f"Share of the {len(rows):,} large institutions")
    ax.legend(handles=[matplotlib.patches.Patch(color=c, label=l) for _, l, c in bands], title="Share in journal vs share of all links", title_fontsize=5.8, fontsize=5.8, ncol=3,
              loc="upper right", handlelength=1, columnspacing=0.8)
    ax.set_title("D  Large institutions with a paper in each journal", loc="left", fontsize=8.5)

    # E, F: author lists
    a_ = list(csv.DictReader(open(os.path.join(ROOT, "10-31-26", "data", "fig4a_author_count_buckets.csv"))))
    b_ = list(csv.DictReader(open(os.path.join(ROOT, "10-31-26", "data", "fig4b_papers_100plus_authors_by_year.csv"))))
    low = gs[2].subgridspec(1, 2, wspace=0.3, width_ratios=[1.4, 1])
    ax = fig.add_subplot(low[0])
    xs = np.arange(len(a_))
    for key, color, lab in (("share_of_papers", GRAY, "Papers"), ("share_of_citations", BLUE, "Citations"), ("share_of_author_credited_citations", VERMILION, "Citations credited to authors")):
        ax.plot(xs, [float(r[key]) for r in a_], color=color, marker="o", markersize=3.5, linewidth=1.4, label=lab)
    ax.set_yscale("log")
    ticks = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1]
    ax.set_yticks(ticks, ["0.0001%", "0.001%", "0.01%", "0.1%", "1%", "10%", "100%"])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks(xs, [r["authors"] for r in a_], fontsize=6.5)
    ax.set_xlabel("Authors per paper")
    ax.set_ylabel("Share of total (log scale)")
    ax.legend(fontsize=6, loc="lower left")
    ax.set_title("E  Papers and citations by author count, 2003–2026", loc="left", fontsize=8.5)
    ax = fig.add_subplot(low[1])
    ax.plot([int(r["year"]) for r in b_], [float(r["per_10000_papers"]) for r in b_], color=BLUE, linewidth=1.6)
    ax.set_ylim(0, None)
    ax.set_xticks([2005, 2015, 2025])
    ax.set_xlabel("Year published")
    ax.set_ylabel("Per 10,000 papers")
    ax.set_title("F  Papers with 100+ authors over time", loc="left", fontsize=8.5)
    save(fig, "F11_institutions_and_authors")


if __name__ == "__main__":
    main()
