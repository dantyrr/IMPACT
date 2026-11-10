"""F1 (v3): publication month and rate windows. Takes in panels A, C and D of v2's Figure 3, following the comments on
figure_legends_v2.docx.

A, B  two papers, every year to 2025, with the years a JIF counts marked
C     mean citations by month of age, with the January and December JIF windows shaded
D     matched January and December papers, by month since the start of the publication year
E     research articles 2014-19: citations in each calendar year after publication, and the 24-month rate, by publication month
F     share of reviews and of other citable items published Jan-Mar
G     JIF credit for the same paper published in each month
H     citations by publication month at matched ages
I     JIF-style rate for 2022 against the mean of the year's twelve 24-month readings
J     year-to-year consistency of journal rates
K     correlation of each rate with later citations

Usage: python 10-31-26/scripts/v3_f1.py   (from the IMPACT folder)
"""
import os
import sys
import textwrap

os.environ.setdefault("FIG_DIR", "v3")
sys.path.insert(0, os.path.dirname(__file__))
import windows as W  # noqa: E402
from make_figures import BLUE, VERMILION, GREEN, GRAY, INK, MUTED, DATA, C, Y0, con, dc, jid, matplotlib, np, plt, pm, pmid, py  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from v2_common import MONTHS, NAMES, ORANGE, SKY, place_labels, rate_weights, save, write_csv  # noqa: E402
import v2_f1  # noqa: E402
from v2_f1 import COHORT, agree, month_axis, pair_stats, paper_panel, twin_pairs  # noqa: E402
from v2_f3 import COVID_SQL  # noqa: E402
from v2_panels import REFERENCE  # noqa: E402

LIGHT, DARK = "#DDDDDD", MUTED
v2_f1.LIGHT, v2_f1.DARK = LIGHT, DARK
PCT1 = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0%}".replace("-", "−") if abs(v) > 1e-9 else "0%")
RATE = "24-month rate"
JIF = "JIF-style rate"


def stability(mask=None):
    out = []
    for p in list(W.COHORTS)[:-1]:
        m0, m1 = W.P == p, W.P == p + 1
        if mask is not None:
            m0, m1 = m0 & mask, m1 & mask
        i0, s0 = W.journal_sums(m0)
        i1, s1 = W.journal_sums(m1)
        ok = (i0 >= W.MIN_COHORT) & (i1 >= W.MIN_COHORT)
        for k in ("jif", "rate24"):
            out.append([p, k, int(ok.sum()), round(spearmanr(s0[k][ok] / i0[ok], s1[k][ok] / i1[ok])[0], 4)])
    return out


def prediction():
    rows = []
    for k in ("jif", "rate24"):
        paper, journal = [], []
        for p in W.PREDICT:
            m = W.P == p
            paper.append(spearmanr(W.V[k][m], W.V["outcome"][m])[0])
            i, s = W.journal_sums(m)
            ok = i >= W.MIN_COHORT
            journal.append(spearmanr(s[k][ok] / i[ok], s["outcome"][ok] / i[ok])[0])
        rows += [["Per paper", k, round(float(np.mean(paper)), 4)], ["Per journal", k, round(float(np.mean(journal)), 4)]]
    return rows


def panel_c(ax, curve):
    top = curve.max()
    ax.axvspan(12, 35, color=BLUE, alpha=0.15, linewidth=0)
    ax.axvspan(1, 24, color=ORANGE, alpha=0.15, linewidth=0)
    ax.plot(np.arange(60), curve, color=INK, linewidth=1.6)
    ax.text(1.3, top * 1.33, f"December paper: JIF counts\nmonths 1–24, {curve[1:25].sum():.1f} citations", fontsize=6, color=INK, va="top")
    ax.text(35.5, top * 1.33, f"January paper: JIF counts\nmonths 12–35, {curve[12:36].sum():.1f} citations", fontsize=6, color=INK, va="top")
    ax.set_ylim(0, top * 1.36)
    ax.set_xlim(0, 59)
    ax.set_xticks([0, 12, 24, 36, 48])
    ax.set_xlabel("Months since publication")
    ax.set_ylabel("Mean citations per month")
    ax.set_title("C  Citations by months since publication", loc="left", fontsize=8.5)


def panel_d(ax, K, P, ja, jb, fa, fb):
    n = 60
    jan = K[P[:, 0], :n].astype(np.float64).mean(axis=0)
    dec = K[P[:, 1], :n - 11].astype(np.float64).mean(axis=0)
    write_csv("f1d_pairs_by_month", ["month_since_start_of_publication_year", "january_paper", "december_paper"],
              [[m, round(float(jan[m]), 4), round(float(dec[m - 11]), 4) if m >= 11 else ""] for m in range(n)])
    ax.axvspan(12, 36, color="#DDDDDD", alpha=0.6, linewidth=0)
    ax.plot(np.arange(n), jan, color=BLUE, linewidth=1.6, label="January paper")
    ax.plot(np.arange(11, n), dec, color=ORANGE, linewidth=1.6, label="December paper")
    top = jan.max()
    ax.text(24, top * 1.5, "The two years a JIF counts", ha="center", va="top", fontsize=6.3, color=INK)
    ax.text(24, top * 1.38, f"December papers have {jb.sum() / ja.sum():.0%} of\nJanuary papers' citations here", ha="center", va="top", fontsize=6.3, color=INK)
    ax.set_ylim(0, top * 1.55)
    ax.set_xlim(0, n - 1)
    ax.set_xticks([0, 12, 24, 36, 48], ["Published", "+1 year", "+2", "+3", "+4"], fontsize=6.5)
    ax.set_xlabel("Calendar year, from January of the publication year")
    ax.set_ylabel("Mean citations per month")
    ax.legend(fontsize=5.8, loc="lower right", handlelength=1.4)
    ax.set_title("D  Matched January and December papers", loc="left", fontsize=8.5)


def panel_e(ax, K, row, in_cohort):
    """Research articles in the cohort. Calendar year k after publication covers ages 13-m+12(k-1) to 24-m+12(k-1)."""
    w = rate_weights()
    rc = dc[row]
    table = []
    for m in MONTHS:
        s = np.flatnonzero(in_cohort & (rc == 0) & (pm[row] == m))
        k = K[s, :72].astype(np.float64)
        years = [k[:, 13 - m + 12 * j:25 - m + 12 * j].sum(axis=1).mean() for j in range(3)]
        table.append([NAMES[m - 1], len(s), *[round(float(v), 3) for v in years], round(float((k[:, :36] @ w).mean() / 2), 3)])
    write_csv("f1e_citations_per_year", ["month", "research_articles", "year_1", "year_2", "year_3", "rate_24_month"], table)
    x = np.array(MONTHS)
    for i, color, lab in ((4, GRAY, "3rd year, not included in JIF"), (3, GREEN, "2nd year of JIF calculation"), (2, BLUE, "1st year of JIF calculation"),
                          (5, VERMILION, "24-month rate")):
        v = np.array([r[i] for r in table])
        ax.plot(x, v, color=color, marker="o", markersize=3, linewidth=1.5, label=lab)
        ax.text(12.25, v[-1] + {4: 0.16, 3: 0.0, 2: 0, 5: -0.18}[i], f"{v[-1] / v[0] - 1:+.0%}".replace("-", "−"), fontsize=6.3, color=INK, va="center")
    ax.set_ylim(0, 5.3)
    ax.set_xlim(0.5, 13.4)
    month_axis(ax)
    ax.set_ylabel("Mean citations per year")
    ax.legend(fontsize=5.8, loc="upper left", handlelength=1.8, labelspacing=0.25, ncol=2, columnspacing=0.9)
    ax.set_title("E  Citations per year, by publication month", loc="left", fontsize=8.5)
    return table


def panel_f(ax):
    rows, journals = [], set()
    for Y in range(2005, 2025):
        s = (py == Y) & (dc <= 3) & (pm >= 1) & (pm != 6)
        r, o = s & (dc == 1), s & (dc != 1)
        journals |= set(np.unique(jid[s]).tolist())
        rows.append([Y, int(r.sum()), int(o.sum()), round(100 * np.isin(pm[r], (1, 2, 3)).mean(), 2), round(100 * np.isin(pm[o], (1, 2, 3)).mean(), 2)])
    write_csv("f1f_reviews_early_by_year", ["year", "reviews", "other_citable_items", "reviews_jan_mar", "other_jan_mar"], rows)
    ax.plot([r[0] for r in rows], [r[3] for r in rows], color=ORANGE, linewidth=1.6, label="Reviews")
    ax.plot([r[0] for r in rows], [r[4] for r in rows], color=GRAY, linewidth=1.6, linestyle=(0, (3, 2)), label="Other citable items")
    even = 100 * 3 / 11
    ax.axhline(even, color=GRAY, linewidth=0.8, linestyle=":")
    ax.text(2024, even + 1.6, "Even spread over the year: 3 of 11 months, 27%", ha="right", fontsize=6, color=INK)
    ax.set_ylim(0, 40)
    ax.set_xlim(2005, 2024)
    ax.set_xticks([2005, 2010, 2015, 2020])
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(100, decimals=0))
    ax.set_xlabel("Year published")
    ax.set_ylabel("Share of each group\npublished Jan–Mar")
    ax.legend(fontsize=6, loc="lower left")
    ax.set_title("F  Items published January to March", loc="left", fontsize=8.5)
    return len(journals)


def panel_g(ax, curves):
    rows = []
    for lab, color in (("Research articles", SKY), ("Reviews", ORANGE)):
        c, n = curves[lab]
        w = np.array([c[13 - m:37 - m].sum() for m in range(1, 13)])
        credit = w / w.mean()
        rows += [[lab, NAMES[m - 1], round(float(credit[m - 1]), 4), n] for m in range(1, 13)]
        ax.plot(MONTHS, [credit[m - 1] - 1 for m in MONTHS], color=color, marker="o", markersize=3, linewidth=1.5, label=f"{lab} (n = {n:,})")
    write_csv("f1g_credit_by_month", ["series", "month", "credit", "papers"], rows)
    ax.axhline(0, color=GRAY, linewidth=0.7)
    month_axis(ax)
    ax.set_ylim(-0.2, 0.2)
    ax.yaxis.set_major_formatter(PCT1)
    ax.set_ylabel("JIF credit vs average month")
    ax.legend(fontsize=5.8, loc="lower left")
    ax.set_title("G  JIF credit by publication month", loc="left", fontsize=8.5)


def panel_h(ax, K, row, in_cohort):
    rc, ry, rm = dc[row], py[row], pm[row]
    s = np.flatnonzero(in_cohort & (rc == 0) & (rm != 6))
    mo = rm[s]
    key = jid[row[s]].astype(np.int64) * 10000 + ry[s]
    _, grp = np.unique(key, return_inverse=True)
    rows = []
    for months, color in ((12, SKY), (24, BLUE), (36, GREEN), (60, VERMILION)):
        v = K[s, :months].sum(axis=1, dtype=np.float64)
        adj = v - (np.bincount(grp, v) / np.bincount(grp))[grp] + v.mean()
        by = np.array([v[mo == m].mean() for m in MONTHS])
        within = np.array([adj[mo == m].mean() for m in MONTHS])
        rel = by / by.mean() - 1
        rows += [[months, NAMES[m - 1], round(float(a), 3), round(float(r), 4), round(float(w), 3)] for m, a, r, w in zip(MONTHS, by, rel, within)]
        ax.plot(MONTHS, rel, color=color, marker="o", markersize=2.5, linewidth=1.3, label=f"First {months // 12} year{'s' if months > 12 else ''}")
    write_csv("f1h_overall_by_month", ["months", "month", "mean_citations", "vs_average_month", "mean_within_journal_and_year"], rows)
    ax.axhline(0, color=GRAY, linewidth=0.7)
    month_axis(ax)
    ax.set_ylim(-0.2, 0.2)
    ax.yaxis.set_major_formatter(PCT1)
    ax.set_ylabel("All citations vs average month")
    ax.legend(fontsize=5.8, loc="lower left", ncol=2, columnspacing=0.8, handlelength=1.4)
    ax.set_title("H  All citations by publication month, at matched ages", loc="left", fontsize=8.5)


def panel_i(ax):
    """JIF-style rate for 2022 against the mean of 2022's twelve monthly 24-month readings, same journals."""
    Y = 2022
    items = W.READ_ITEMS[Y][11]
    with np.errstate(divide="ignore", invalid="ignore"):
        read = np.nanmean(W.READ_NUM[Y] / W.READ_ITEMS[Y], axis=0)
        jif = W.READ_NUM[Y][11] / items          # December's reading: citations in Y to items from Y-2 and Y-1
    ok = (items >= W.MIN_ITEMS) & (jif > 0) & (read > 0)
    js, n, a, b = W.uj[ok], items[ok], jif[ok], read[ok]
    rho = spearmanr(a, b)[0]
    lim = np.array([0.1, 300])
    ax.scatter(a, b, s=3, color=GRAY, alpha=0.35, linewidths=0)
    ax.plot(lim, lim, color=INK, linewidth=0.7, linestyle=(0, (3.5, 2.5)))
    rel = np.log(b / a)
    big = np.flatnonzero(n >= 500)
    o = big[np.argsort(rel[big])]
    picks = list(o[:3]) + list(o[-3:])
    ref = [k for k, j in enumerate(js) if W.abbr.get(int(j)) in REFERENCE]
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(*lim); ax.set_ylim(*lim)
    ax.scatter(a[picks], b[picks], s=11, color=VERMILION, linewidths=0, zorder=3, label="Largest differences (500+ items)")
    ax.scatter(a[ref], b[ref], s=11, color=BLUE, linewidths=0, zorder=3, label="Reference journals")
    clear = [(x, y) for x in (0.13, 0.2, 0.3, 0.5, 0.8) for y in (70, 110, 170, 250)] + [(x, y) for x in (12, 20, 35, 60, 100, 170, 250) for y in (0.12, 0.16, 0.2, 0.28)]
    short = lambda t: t if len(t) <= 22 else t[:20] + "…"  # noqa: E731
    place_labels(ax, [(a[k], b[k], short(W.abbr[int(js[k])])) for k in picks + ref], fontsize=5.6, avoid=clear[:20])
    write_csv("f1i_jif_style_vs_24_month", ["journal", "items", "jif_style_2022", "rate_24_month_mean_2022", "ratio", "why_marked"],
              [[W.abbr[int(js[k])], int(n[k]), round(float(a[k]), 3), round(float(b[k]), 3), round(float(b[k] / a[k]), 3), why]
               for k, why in [(k, "largest gap, 500+ items") for k in picks] + [(k, "reference") for k in ref]])
    ax.set_xlabel(f"{JIF}, {Y}")
    ax.set_ylabel(f"{RATE},\nmean of {Y}'s 12 readings")
    ax.text(0.04, 0.95, f"{len(a):,} journals\nSpearman ρ = {rho:.3f}\ndashed: equal", transform=ax.transAxes, fontsize=6, va="top", color=MUTED)
    ax.legend(fontsize=5.8, loc="lower right")
    ax.set_title(f"I  {JIF} and {RATE}", loc="left", fontsize=8.5)
    return len(a), rho


def panel_j(ax):
    covid = np.array([r[0] for r in con.execute(COVID_SQL)], np.int64)
    not_covid = ~np.isin(pmid[W.row], covid)
    every, clean = stability(), stability(not_covid)
    write_csv("f1j_stability", ["cohort", "window", "journals", "spearman_all_papers", "spearman_without_covid_papers"],
              [[a[0], a[1], a[2], a[3], b[3]] for a, b in zip(every, clean)])
    for k, color, lab in (("jif", BLUE, JIF), ("rate24", VERMILION, RATE)):
        ax.plot([a[0] for a in every if a[1] == k], [a[3] for a in every if a[1] == k], color=color, marker="o", markersize=3, linewidth=1.5, label=lab)
        ax.plot([a[0] for a in clean if a[1] == k], [a[3] for a in clean if a[1] == k], color=color, linewidth=0.9, linestyle=(0, (3, 2)))
    ax.plot([], [], color=MUTED, linewidth=0.9, linestyle=(0, (3, 2)), label="Dashed: COVID papers left out")
    ax.set_ylim(0, 1)
    ax.set_xlabel("Each year's papers vs the next year's")
    ax.set_ylabel("Spearman ρ between journals' rates")
    ax.text(0.97, 0.72, "2019 dip due to COVID", transform=ax.transAxes, ha="right", fontsize=6, color=INK)
    ax.legend(fontsize=5.8, loc="lower left")
    ax.set_title("J  Year-to-year consistency of journal rates", loc="left", fontsize=8.5)


def panel_k(ax):
    rows = prediction()
    write_csv("f1k_prediction", ["level", "window", "mean_spearman"], rows)
    for g, lab in enumerate(("Per paper", "Per journal")):
        for w, (k, color, name) in enumerate((("jif", BLUE, JIF), ("rate24", VERMILION, RATE))):
            v = next(r[2] for r in rows if r[0] == lab and r[1] == k)
            x = g + (w - 0.5) * 0.3
            ax.scatter(x, v, s=24, color=color, linewidths=0, zorder=3, label=name if g == 0 else None)
            ax.annotate(f"{v:.3f}", (x, v), fontsize=5.3, xytext=(0, 5), textcoords="offset points", ha="center", va="bottom", color=MUTED)
    ax.set_xticks(range(2), ["Per paper", "Per journal"], fontsize=6.5)
    ax.set_xlim(-0.5, 1.5); ax.set_ylim(0.7, 1.0)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Spearman ρ with citations,\nyears 4–6")
    ax.legend(fontsize=5.8, loc="lower right")
    ax.set_title("K  Correlation of each rate with later citations", loc="left", fontsize=8.5)


def key(ax):
    ax.axis("off")
    items = [("Clarivate JIF", "the commercial metric, from Web of Science citations. Not used here."),
             (JIF, "the JIF formula with PubMed citations: citations in one calendar year to citable items from the two years before."),
             (RATE, "the same formula read every month: citations in the last 12 months to items from the 24 months before those. "
                    "Its December reading equals the JIF-style rate.")]
    y = 0.97
    for a, b in items:
        ax.text(0, y, a, fontsize=6.6, fontweight="bold", color=INK, va="top", transform=ax.transAxes)
        lines = textwrap.wrap(b, 62)
        ax.text(0, y - 0.075, "\n".join(lines), fontsize=6.3, color=INK, va="top", linespacing=1.25, transform=ax.transAxes)
        y -= 0.13 + 0.07 * len(lines)


def main():
    A = np.load(os.path.join(DATA, "ages72.npz"))
    row, K = A["row"], A["counts"]
    keep = (pm[row] != 6) & ~np.isin(jid[row], list(W.UNDERCOUNTED))
    W.V["rate24"] = K[keep, :36].astype(np.float64) @ rate_weights()

    fig = plt.figure(figsize=(7.2, 15.0))
    gs = fig.add_gridspec(6, 2, hspace=0.52, wspace=0.3)
    rows = []
    a = paper_panel(fig.add_subplot(gs[0, 0]), 16275915, 2005, 11, "A  Hirsch, PNAS, Nov 2005 (h-index)", rows)
    b = paper_panel(fig.add_subplot(gs[0, 1]), 21376230, 2011, 3, "B  Hanahan & Weinberg, Cell, Mar 2011 (Hallmarks)", rows)
    print("A", a, "B", b, flush=True)
    write_csv("f1ab_paper_citations_by_year", ["pmid", "year", "citations", "status"], rows)
    handles = [matplotlib.patches.Patch(color=c, label=t) for c, t in
               ((DARK, "Year published (no JIF counts it)"), (BLUE, "First JIF year"), (GREEN, "Second JIF year"), (LIGHT, "Later years (no JIF counts them)"))]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.905), ncol=4, fontsize=6.5, frameon=False, handlelength=1.1, columnspacing=1.2)

    ry, rm, rc = py[row], pm[row], dc[row]
    in_cohort = (ry >= COHORT[0]) & (ry <= COHORT[1]) & (rm >= 1) & (rm != 6)
    curves = {}
    for lab, cls in (("Research articles", 0), ("Reviews", 1)):
        s = np.flatnonzero(in_cohort & (rc == cls))
        curves[lab] = (K[s, :60].sum(axis=0, dtype=np.float64) / len(s), len(s))
    curve, n_research = curves["Research articles"]
    write_csv("f1c_age_curve", ["age_months", "mean_citations", "papers"], [[i, round(v, 5), n_research] for i, v in enumerate(curve)])
    panel_c(fig.add_subplot(gs[1, 0]), curve)

    P = twin_pairs(row, K)
    ja, jb = K[P[:, 0], 12:36].astype(float).sum(axis=1), K[P[:, 1], 1:25].astype(float).sum(axis=1)
    fa, fb = K[P[:, 0], 0:24].astype(float).sum(axis=1), K[P[:, 1], 0:24].astype(float).sum(axis=1)
    ok_ids = agree(np.r_[pmid[row[P[:, 0]]], pmid[row[P[:, 1]]]])
    both = np.array([int(pmid[row[x]]) in ok_ids and int(pmid[row[y]]) in ok_ids for x, y in P])
    write_csv("f1d_pairs_summary", ["measure", "matched_on", "pairs", "jan_mean", "dec_mean", "dec_over_jan", "jan_median", "dec_median", "median_jan_minus_dec",
                                    "share_jan_higher", "share_dec_higher"],
              [pair_stats("jif_counted", ja, jb), pair_stats("first_24_months", fa, fb),
               pair_stats("jif_counted_dates_agree", ja[both], jb[both]), pair_stats("first_24_months_dates_agree", fa[both], fb[both])])
    panel_d(fig.add_subplot(gs[1, 1]), K, P, ja, jb, fa, fb)

    panel_e(fig.add_subplot(gs[2, 0]), K, row, in_cohort)
    panel_f(fig.add_subplot(gs[2, 1]))
    panel_g(fig.add_subplot(gs[3, 0]), curves)
    panel_h(fig.add_subplot(gs[3, 1]), K, row, in_cohort)
    print("I", panel_i(fig.add_subplot(gs[4, 0])), flush=True)
    panel_j(fig.add_subplot(gs[4, 1]))
    panel_k(fig.add_subplot(gs[5, 0]))
    key(fig.add_subplot(gs[5, 1]))
    save(fig, "F1_publication_month")


if __name__ == "__main__":
    main()
