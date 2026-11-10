"""v13: the figures after the comments on v12/figure_legends_v12.docx.

Every figure says "24-month citation rate" (v13_base). Panel changes:
  Fig 2B   gray dots, named journals in color (blue above the trend, orange below), dashed line where the rise equals the review share
  Fig 3    wider; S3B joins as B, the reliance, series and guideline panels share a row, and the rate grid is 6 wide by 3 rows
  S3       only the trend panel is left
  Fig 6    A's journal names say USA or Europe; C's legend reads European journal then US journal and sits above the plot
  S1       the color key for A and B sits below them
  S5       A is dropped (Figure 1B shows the same thing); region panel labels on the left with one marker per flagship;
           "top" institutions renamed by what ranks them; Poisson 95% intervals on the 100+ author series
  S6       Hindawi in vermillion
  S9       stacks already in Figure 1 (Nature Portfolio, Cell Press, AAAS, MDPI, Frontiers) are dropped
Figure 1 has no 24-month label and is copied from v12.

Usage (from the IMPACT folder), one job per process because older scripts fix module state at import:
  python 10-31-26/scripts/v13_figs.py setup
  python 10-31-26/scripts/v13_figs.py fig2|fig3|fig4|timing|fig6|s5|s6|s9
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v13_base as B13  # noqa: E402  must come first
from v2_common import ROOT, V2  # noqa: E402

V12 = os.path.join(ROOT, "10-31-26", "v12")


def setup():
    """v13 starts as a copy of v12's figures and data; each job then redraws its figures."""
    os.makedirs(os.path.join(V2, "data"), exist_ok=True)
    for f in os.listdir(V12):
        if f.endswith((".png", ".pdf")) and not f.startswith("figure_legends"):
            shutil.copy(os.path.join(V12, f), V2)
    for f in os.listdir(os.path.join(V12, "data")):
        shutil.copy(os.path.join(V12, "data", f), os.path.join(V2, "data"))


def title_at(fig, spec, ax, text, fontsize=8.5):
    """A panel title starting at the left edge of a grid cell (where the tick labels begin), level with the axes' top."""
    ax.set_title("", loc="left")
    x0 = spec.get_position(fig).x0
    fig.text(x0, ax.get_position().y1 + 0.006, text, fontsize=fontsize, ha="left", va="bottom")


# ---------------------------------------------------------------- Figure 2 and S4
def fig2():
    import v8_figs as V8
    F2, F1 = V8.F2, V8.F1
    F1.publisher_panel = V8.publisher_panel
    F2.labels = V8.end_labels
    F2.PUBLISHERS = [(n, V8.COLOR[n]) for n in V8.top_for_reviews()]
    B13.patch(F2.figure2,
              ("ax.scatter(share, np.minimum(lift, TOP), s=4, color=BLUE, alpha=0.3, linewidth=0)",
               "ax.scatter(share, np.minimum(lift, TOP), s=4, color=GRAY, alpha=0.3, linewidth=0)\n"
               "    ax.plot([0, 1], [0, 1], color=INK, linewidth=0.7, linestyle=(0, (3.5, 2.5)), zorder=2)"),
              ("    for slug in picks:\n        l_, s_ = by[slug]\n        ax.scatter(s_, min(l_, TOP), s=13, color=BLUE,",
               "    for k_, slug in enumerate(picks):\n        l_, s_ = by[slug]\n        ax.scatter(s_, min(l_, TOP), s=14, color=BLUE if k_ < 3 else ORANGE,"),
              ('ax.text(x, y, t, transform=ax.transAxes, ha=ha, va=va, fontsize=6, color=INK, fontweight="bold")', "pass"),
              ("ax.set_xlim(0, 0.72); ax.set_ylim(-0.5, 2.5)",
               "ax.set_xlim(0, 0.72); ax.set_ylim(-0.5, 2.5)\n"
               '    ax.text(0.03, 0.64, "Above the line:\\nrise larger than review share", transform=ax.transAxes, ha="left", va="top", fontsize=6.3, color=INK)\n'
               '    ax.text(0.97, 0.03, "Below the line:\\nrise smaller than review share", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.3, color=INK)'))
    F2.figure2()


# ---------------------------------------------------------------- Figure 3 and S3
RATE_GRID_DROP = ("PLoS One", "Sci Rep")      # 18 panels: the 11 largest falls, CA Cancer J Clin and the six flagships


def panel_reliant(ax, r, R):
    """Each journal's top paper as its share of the rate; the paper's title sits in the gray part of its bar."""
    big = sorted(((v["top1"], k) for k, v in r.items() if v["items"] >= 500), reverse=True)[:8]
    yy = R.np.arange(len(big))[::-1]
    vals = [s for s, _ in big]
    ax.barh(yy, vals, color=R.VERMILION, height=0.72, edgecolor="white", linewidth=0.5)
    ax.barh(yy, [1 - v for v in vals], left=vals, color="#E4E4E4", height=0.72, edgecolor="white", linewidth=0.5)
    labels = []
    for y, (v, k) in zip(yy, big):
        t = R.title(r[k]["top_pmid"]).strip("[]. ")
        name = R.abbr[k].replace(" (Engl)", "").replace("Zhonghua Yi Xue Yi Chuan Xue Za Zhi", "Zhonghua Yi Xue Yi Chuan")
        labels.append(f"{name}\n{t[:30]}{'…' if len(t) > 30 else ''}")
        ax.text(1.02, y, f"{v:.0%}", va="center", fontsize=5.6, color=R.MUTED)
    ax.set_yticks(yy, labels, fontsize=5.3, linespacing=1.15)
    ax.xaxis.set_major_formatter(R.PCT)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.5, 1])
    ax.set_xlabel(f"Top paper's share of the rate, Dec {R.YEAR}")
    ax.grid(axis="y", visible=False)


def fig3():
    import v8_figs as V8
    R = V8.R
    V8.series_table()
    plt, np = R.plt, R.np
    r = R.concentration(R.YEAR)
    share = np.array([v["top1"] for v in r.values()])
    med = float(np.median(share))
    sid, keys = R.series_membership()
    picks, eligible = R.grid_journals(sid)

    fig = plt.figure(figsize=(8.6, 13.4))
    gs = fig.add_gridspec(4, 1, left=0.065, right=0.975, top=0.975, bottom=0.04, hspace=0.42, height_ratios=[1.05, 0.62, 1.05, 2.05])

    row = gs[0].subgridspec(1, 3, wspace=0, width_ratios=[1.62, 0.6, 0.92])
    ax = fig.add_subplot(row[0])
    R.panel_hist(ax, r, share, med)
    ax.set_title(f"A  Share of each journal's rate from its top paper, December {R.YEAR}", loc="left", fontsize=8.5)
    ax.set_xlabel(f"Top paper's share of the journal's 24-month rate, December {R.YEAR}")
    ax = fig.add_subplot(row[2])
    R.series_summary(ax, picks, sid, "B  Citations going to recurring series")
    title_at(fig, row[1], ax, "B  Citations going to recurring series")

    R.panels_with_without(fig, gs[1].subgridspec(1, 3, wspace=0.28))
    t = fig.axes[-3]._left_title
    t.set_text(t.get_text().replace("B  ", "C  "))

    row = gs[2].subgridspec(1, 6, wspace=0, width_ratios=[1.2, 1.45, 2.05, 0.85, 1.1, 0.95])
    ax = fig.add_subplot(row[1])
    panel_reliant(ax, r, R)
    title_at(fig, row[0], ax, "D  Most reliant on one paper (500+ items)")
    ax = fig.add_subplot(row[3])
    B13.patch(R.panel_series, ('t if len(t) <= 36 else t[:35] + "…"', 't if len(t) <= 31 else t[:30] + "…"'), ("fontsize=5.6)", "fontsize=5.4)"))
    R.panel_series(ax)
    title_at(fig, row[2], ax, "E  Series: titles repeating year after year")
    ax = fig.add_subplot(row[5])
    R.panel_guidelines(ax)
    title_at(fig, row[4], ax, "F  Guidelines: items tagged as guidelines")

    grid = [p for p in picks if R.abbr[p[0]] not in RATE_GRID_DROP]
    assert len(grid) == 18, len(grid)
    sub = gs[3].subgridspec(3, 6, hspace=0.55, wspace=0.34)
    ax = R.rate_grid(fig, sub, grid, sid, 6, "G  Rate with and without guidelines and series")
    h, l = ax.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, 0.004))
    R.save(fig, "Fig3_few_papers")

    # S3: the trend panel alone
    fig, ax = plt.subplots(figsize=(4.0, 2.9))
    rows = []
    for Y in R.TREND:
        a = np.array([v["top1"] for v in R.concentration(Y).values()])
        rows.append([Y, float(np.median(a)), float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))])
    yrs = [x[0] for x in rows]
    ax.fill_between(yrs, [x[2] for x in rows], [x[3] for x in rows], color=R.BLUE, alpha=0.15, linewidth=0, label="Middle 95% of journals")
    ax.plot(yrs, [x[1] for x in rows], color=R.BLUE, label="Median journal")
    ax.legend(fontsize=6, loc="upper left", handlelength=1.3)
    ax.set_ylim(0, None); ax.set_xlim(yrs[0], yrs[-1])
    ax.set_xticks([2010, 2015, 2020, 2025])
    ax.yaxis.set_major_formatter(R.PCT)
    ax.set_ylabel("Top paper's share of the rate")
    ax.set_xlabel("December reading")
    ax.set_title("Top paper's share, 2007–25", loc="left", fontsize=8.5)
    R.write_csv("s3_top_paper_share_trend", ["year", "median", "p2_5", "p97_5"], [[y, round(a, 4), round(b, 4), round(c, 4)] for y, a, b, c in rows])
    R.save(fig, "S3_reliance_detail")


# ---------------------------------------------------------------- Figure 4
def fig4():
    import v8_figs as V8
    V8.F4.main()


# ---------------------------------------------------------------- Figure 5, S1, S2
def timing():
    import v5_timing as T
    B13.patch(T.main,
              ("gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.3)", "gs = fig.add_gridspec(3, 2, hspace=0.78, wspace=0.3)"),
              ('fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=4,',
               'fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, fig.axes[-1].get_position().y0 - 0.052), ncol=4,'))
    T.main()


# ---------------------------------------------------------------- Figure 6, S7, S8
def fig6():
    from make_figures import PURPLE
    import v3_f10_alt as ABS
    import v3_f10_alt_share as SHARE
    import v3_f10_combined as GEO
    B13.patch(GEO.panels_ab,
              ('labels.append(r["journal"].replace("Am J Respir Crit Care Med", "AJRCCM"))',
               'labels.append(r["journal"].replace("Am J Respir Crit Care Med", "AJRCCM") + (" (USA)" if i % 2 == 0 else " (Europe)"))'))
    B13.patch(GEO.panels_cd,
              ('for n, c in (("US journal", BLUE), ("European journal", GOLD))', 'for n, c in (("European journal", GOLD), ("US journal", BLUE))'),
              ("bbox_to_anchor=(-0.02, 0.985)", "bbox_to_anchor=(-0.02, 1.015)"),
              ('ax.set_title("C  Citing share, 17 pairs", x=-1.3, pad=14, **T)', 'ax.set_title("C  Citing share, 17 pairs", x=-1.3, pad=21, **T)'),
              ('bx.set_title("D  Rate", pad=14, **T)', 'bx.set_title("D  Rate", pad=21, **T)'))
    B13.patch(GEO.main, ("hspace=0.17", "hspace=0.2"))
    B13.patch(GEO.panel_e, ('ax.set_title("E  Top journals of each region", x=-0.82, pad=14, **T)', 'ax.set_title("E  Top journals of each region", x=-0.82, pad=21, **T)'))
    names = {"F10_geography": "Fig6_geography", "F10_alt_citers_over_time": "S7_citers_over_time", "F10_alt_citers_absolute": "S8_citers_absolute"}
    for mod in (ABS, SHARE, GEO):
        mod.REGIONS = [(n, PURPLE if n == "Canada" else c) for n, c in mod.REGIONS]
        mod.main()
    for old, new in names.items():
        for ext in (".png", ".pdf"):
            os.replace(os.path.join(V2, old + ext), os.path.join(V2, new + ext))


# ---------------------------------------------------------------- S5
FLAG_MARK = {"nature": "o", "science": "s", "cell": "^", "nejm": "v", "lancet": "P"}


def s5():
    os.environ["INST_MERGE"] = "institution_merge_v12.csv"
    os.environ["INST_LINKS"] = "institutions_v12.pkl"
    import v10_base as B
    import make_figures as MF
    from scipy.stats import chi2
    F11 = B.F11
    np, plt, matplotlib = F11.np, F11.plt, F11.matplotlib
    INK, MUTED = F11.INK, F11.MUTED
    d, N, rows = F11.institutions()
    idx = np.array([r[0] for r in rows])
    reg = np.array([r[3] for r in rows])
    fig = plt.figure(figsize=(7.2, 7.4))
    gs = fig.add_gridspec(2, 1, hspace=0.38, height_ratios=[1, 0.82])
    top = gs[0].subgridspec(1, 2, wspace=0.32, width_ratios=[1, 1])

    # A: each region's share, one marker per flagship
    ax = fig.add_subplot(top[0])
    all_share = {n: d["all"][idx][reg == n].sum() / d["all"][idx].sum() for n, _ in F11.REGIONS}
    out = []
    yy = np.arange(len(F11.REGIONS))[::-1]
    off = dict(zip(d["journals"], np.linspace(0.22, -0.22, len(d["journals"]))))
    for y0, (name, color) in zip(yy, F11.REGIONS):
        m = reg == name
        vals = {j: d["j"][j][idx][m].sum() / d["j"][j][idx].sum() for j in d["journals"]}
        lo, hi = min(list(vals.values()) + [all_share[name]]), max(list(vals.values()) + [all_share[name]])
        ax.hlines(y0, lo, hi, color="#BBBBBB", linewidth=1)
        for j, v in vals.items():
            ax.scatter([v], [y0 + off[j]], marker=FLAG_MARK[j], s=17, color=color, edgecolor="white", linewidth=0.3, zorder=3)
        ax.scatter([all_share[name]], [y0], marker="D", s=26, color=INK, zorder=4)
        out.append([name, round(float(all_share[name]), 4), *[round(float(vals[j]), 4) for j in d["journals"]]])
    F11.write_csv("f11b_regions", ["region", "all_journals", *d["journals"]], out)
    ax.set_yticks(yy, [n for n, _ in F11.REGIONS], fontsize=6.5)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 0.62)
    ax.set_xlabel("Share of institution links")
    L = matplotlib.lines.Line2D
    ax.legend(handles=[L([], [], marker="D", color=INK, linestyle="", markersize=4, label="All journals")]
              + [L([], [], marker=FLAG_MARK[j], color=MUTED, linestyle="", markersize=4, label=F11.NAMES[j]) for j in d["journals"]],
              fontsize=6, loc="lower right", ncol=2, handletextpad=0.2, columnspacing=0.8)
    ax.set_title("A  Share of links by region", loc="left", fontsize=8.5)

    # B: links from the institutions with the most links in each journal
    ax = fig.add_subplot(top[1])
    rng = np.random.default_rng(1)
    base = d["all"][idx] / d["all"][idx].sum()
    groups = [(F11.NAMES[j], d["j"][j]) for j in d["journals"]]
    out = []
    for g, (name, v) in enumerate(groups):
        n = int(v[idx].sum())
        v = np.sort(v[idx])[::-1].astype(float)
        s = [v[:k].sum() / v.sum() for k in (10, 50, 100)]
        draws = np.sort(rng.multinomial(n, base, size=30), axis=1)[:, ::-1]
        e = [float((draws[:, :k].sum(axis=1) / n).mean()) for k in (10, 50, 100)]
        ax.vlines(g - 0.1, s[0], s[2], color="#BBBBBB", linewidth=1)
        ax.vlines(g + 0.14, e[0], e[2], color="#BBBBBB", linewidth=1)
        for val, exp_, marker, color in zip(s, e, ("o", "s", "D"), (F11.BLUE, F11.ORANGE, F11.VERMILION)):
            ax.scatter(g - 0.1, val, s=20, marker=marker, color=color, zorder=3, linewidths=0)
            ax.scatter(g + 0.14, exp_, s=16, marker=marker, facecolors="none", edgecolors=color, zorder=3, linewidth=0.8)
        out.append([name, n, *[round(float(a), 4) for a in s], *[round(a, 4) for a in e]])
    F11.write_csv("f11c_concentration", ["journal", "links", "most_links_10", "most_links_50", "most_links_100", "expected_10", "expected_50", "expected_100"], out)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups], fontsize=6.5)
    ax.set_ylim(0, 0.76)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Share of links to large institutions")
    ax.legend(handles=[L([], [], marker=m, color=c, linestyle="", markersize=4, label=t) for m, c, t in
                       (("D", F11.VERMILION, "100 with most links"), ("s", F11.ORANGE, "50 with most links"), ("o", F11.BLUE, "10 with most links"))]
              + [L([], [], marker="o", markerfacecolor="none", color=MUTED, linestyle="", markersize=4, label="Open: a same-sized random draw")],
              fontsize=5.8, loc="upper left", ncol=2, handletextpad=0.1, columnspacing=0.7)
    ax.set_title("B  How concentrated each journal's links are", loc="left", fontsize=8.5)

    low = gs[1].subgridspec(1, 3, wspace=0.6, width_ratios=[1, 1.15, 0.85])
    # C: over- and under-represented institutions
    ax = fig.add_subplot(low[0])
    bands = (("under_1x", "Under 1×", F11.SKY), ("from_1_to_5x", "1–5×", F11.BLUE), ("over_5x", "Over 5×", F11.VERMILION))
    out = []
    for g, j in enumerate(d["journals"]):
        n = d["j"][j][idx].astype(float)
        r = (n / n.sum()) / base
        shares = [float(((n > 0) & (r < 1)).mean()), float(((r >= 1) & (r <= 5)).mean()), float((r > 5).mean())]
        bottom = 0
        for v, (_, _, c) in zip(shares, bands):
            ax.bar(g, v, bottom=bottom, color=c, width=0.7, edgecolor="white", linewidth=0.5)
            if v >= 0.07:
                ax.text(g, bottom + v / 2, f"{v:.0%}", ha="center", va="center", fontsize=5.6, color="white" if c in (F11.BLUE, F11.VERMILION) else INK)
            bottom += v
        ax.text(g, bottom + 0.012, f"{bottom:.0%}", ha="center", va="bottom", fontsize=6, color=INK, fontweight="bold")
        out.append([F11.NAMES[j], round(float((n == 0).mean()), 4), *[round(v, 4) for v in shares]])
    F11.write_csv("f11d_over_representation", ["journal", "none", *[b[0] for b in bands]], out)
    ax.set_xticks(range(5), [F11.NAMES[j] for j in d["journals"]], fontsize=6.3, rotation=30)
    ax.set_ylim(0, 0.95)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="x", visible=False)
    ax.set_ylabel(f"Share of the {len(rows):,} large institutions")
    ax.legend(handles=[matplotlib.patches.Patch(color=c, label=l) for _, l, c in bands], title="Journal share vs all-journal share", title_fontsize=5.4, fontsize=5.4, ncol=3,
              loc="upper right", handlelength=0.9, columnspacing=0.6, handletextpad=0.3)
    ax.set_title("C  Large institutions in each journal", loc="left", fontsize=8.5)

    # D, E: author lists
    import csv
    a_ = list(csv.DictReader(open(os.path.join(ROOT, "10-31-26", "data", "fig4a_author_count_buckets.csv"))))
    b_ = list(csv.DictReader(open(os.path.join(ROOT, "10-31-26", "data", "fig4b_papers_100plus_authors_by_year.csv"))))
    ax = fig.add_subplot(low[1])
    xs = np.arange(len(a_))
    for key, color, lab in (("share_of_papers", F11.GRAY, "Papers"), ("share_of_citations", F11.BLUE, "Citations"), ("share_of_author_credited_citations", F11.VERMILION, "Citations credited to authors")):
        ax.plot(xs, [float(r[key]) for r in a_], color=color, marker="o", markersize=3, linewidth=1.3, label=lab)
    ax.set_yscale("log")
    ticks = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1]
    ax.set_yticks(ticks, ["0.0001%", "0.001%", "0.01%", "0.1%", "1%", "10%", "100%"])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks(xs, [r["authors"] for r in a_], fontsize=5.8, rotation=30)
    ax.set_xlabel("Authors per paper")
    ax.set_ylabel("Share of total (log scale)")
    ax.legend(fontsize=5.6, loc="lower left")
    ax.set_title("D  Papers and citations by author count", loc="left", fontsize=8.5)

    # E with exact Poisson 95% intervals, from the counts behind the per-10,000 series (make_figures.fig4)
    A = np.load(os.path.join(MF.DATA, "author_counts.npz"))
    amap = np.zeros(MF.pmid.max() + 1, np.int32)
    ok = A["pmid"] <= MF.pmid.max()
    amap[A["pmid"][ok]] = A["n"][ok]
    n_auth = amap[MF.pmid]
    phys = np.array([any(w in MF.jname.get(j, "").lower() for w in ("physic", "phys.", "high energy", "nuclear", "astro")) for j in range(MF.jid.max() + 1)])
    citable = MF.dc <= 3
    bio = citable & ~phys[MF.jid]
    yrs = np.array([int(r["year"]) for r in b_])
    k = np.array([int((bio & (MF.py == y) & (n_auth >= 100)).sum()) for y in yrs])
    tot = np.array([int((bio & (MF.py == y)).sum()) for y in yrs])
    rate = k / tot * 1e4
    assert np.allclose(rate, [float(r["per_10000_papers"]) for r in b_], atol=0.002), list(zip(rate, b_))
    lo = np.where(k > 0, chi2.ppf(0.025, 2 * k) / 2, 0) / tot * 1e4
    hi = chi2.ppf(0.975, 2 * (k + 1)) / 2 / tot * 1e4
    F11.write_csv("s5e_100plus_authors_ci", ["year", "papers_100plus", "citable_items", "per_10000", "ci_low", "ci_high"],
                  [[int(y), int(a), int(b), round(float(c), 3), round(float(e), 3), round(float(f), 3)] for y, a, b, c, e, f in zip(yrs, k, tot, rate, lo, hi)])
    ax = fig.add_subplot(low[2])
    ax.fill_between(yrs, lo, hi, color=F11.BLUE, alpha=0.18, linewidth=0, label="95% interval")
    ax.plot(yrs, rate, color=F11.BLUE, linewidth=1.5)
    ax.set_ylim(0, None)
    ax.set_xticks([2005, 2015, 2025])
    ax.set_xlabel("Year published")
    ax.set_ylabel("Per 10,000 papers")
    ax.legend(fontsize=5.8, loc="upper left")
    ax.set_title("E  Papers with 100+ authors", loc="left", fontsize=8.5)
    print("100+ authors", list(zip(yrs.tolist(), k.tolist())), flush=True)
    F11.save(fig, "S5_institutions_and_authors")


# ---------------------------------------------------------------- S6
def s6():
    import v9_retractions as R9
    R9.F.SKY = R9.F.VERMILION         # Hindawi's color in A-D
    R9.main()


# ---------------------------------------------------------------- S9
def s9():
    import v8_figs as V8
    F1 = V8.F1
    F1.publisher_panel = V8.publisher_panel
    V8.F2.PUBLISHERS = [(n, V8.COLOR[n]) for n in V8.top_for_reviews()]
    B13.patch(F1.s9,
              ("figsize=(7.4, 9.4)", "figsize=(7.4, 5.9)"),
              ("gs = fig.add_gridspec(3, 1, hspace=0.3, height_ratios=[1.0, 1.25, 1.25], left=0.085, right=0.985, top=0.975, bottom=0.03)",
               "gs = fig.add_gridspec(2, 1, hspace=0.3, height_ratios=[1.0, 1.25], left=0.085, right=0.985, top=0.975, bottom=0.045)"),
              ('("Nature Portfolio", "Cell Press", "AAAS", "PLOS", "MDPI", "Frontiers", "Hindawi", "Cureus")', '("PLOS", "Hindawi", "Cureus")'),
              ("block = gs[1 + k // 4].subgridspec(2, 4,", "block = gs[1].subgridspec(2, 3,"),
              ("ax = fig.add_subplot(block[0, k % 4])", "ax = fig.add_subplot(block[0, k % 3])"),
              ("bx = fig.add_subplot(block[1, k % 4])", "bx = fig.add_subplot(block[1, k % 3])"),
              ("if k % 4 == 0:", "if k % 3 == 0:"))
    F1.s9()


JOBS = {"setup": setup, "fig2": fig2, "fig3": fig3, "fig4": fig4, "timing": timing, "fig6": fig6, "s5": s5, "s6": s6, "s9": s9}

if __name__ == "__main__":
    for job in sys.argv[1:]:
        JOBS[job]()
