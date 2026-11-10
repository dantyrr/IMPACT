"""F1: publication month. Replaces alt1, Fig 3 and Fig 9A (see figure_revision_plan.md, Task 2).

A, B   two papers, every year to 2025, with the years a JIF counts marked
C      mean citations by month of age, research articles 2014-19, with the January and December JIF windows
D      every January/December pair: same journal, year and article type, citations at months 36-71 within 8%
E      real research articles 2010-22: citations in each year after publication, by publication month
F      share of reviews and of other citable items published Jan-Mar, each year 2005-24
G      JIF credit for the same paper published in each month, weighted by citations (sums, as a JIF is a sum)
H      citations by publication month at matched ages: 1, 2, 3 and 5 years after publication

June is left out of month panels: it also holds papers with no month.

Usage: python 10-31-26/scripts/v2_f1.py   (from the IMPACT folder)
"""
import os
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import (BLUE, VERMILION, GREEN, GRAY, INK, MUTED, DATA, ROOT, C, Y0, con, dc, jid, matplotlib, np, plt, pm,  # noqa: E402
                          pmid, py)
from v2_common import MONTHS, NAMES, ORANGE, SKY, save, write_csv  # noqa: E402

LAST_YEAR = 2025
COHORT = (2014, 2019)            # every paper has reached age 60 months
LIGHT, DARK = "#C9C9C9", "#6B6B6B"
LETTERS = [n[0] for n in NAMES]


def monthly(p):
    return con.execute("SELECT citing_year, citing_month, COUNT(*) FROM citations WHERE cited_pmid = ? "
                       "AND citing_month IS NOT NULL AND citing_class IS NULL GROUP BY 1, 2", (int(p),)).fetchall()


def paper_panel(ax, p, y0, m0, title, csv_rows):
    i = int(np.flatnonzero(pmid == p)[0])
    years = np.arange(y0, LAST_YEAR + 1)
    v = C[i, years - Y0].astype(int)
    colors = [DARK if y == y0 else BLUE if y == y0 + 1 else GREEN if y == y0 + 2 else LIGHT for y in years]
    ax.bar(years, v, color=colors, width=0.8)
    first24 = sum(n for y, m, n in monthly(p) if 0 <= (y - y0) * 12 + m - m0 < 24)
    counted = int(v[1] + v[2])
    total = int(v.sum())
    top = v.max() * 1.42
    start = y0 + (m0 - 1) / 12 - 0.5
    ax.plot([start, start + 2], [v.max() * 1.1] * 2, color=VERMILION, linewidth=2.5, solid_capstyle="butt")
    ax.text(start + 2.2, v.max() * 1.1, f"First 24 months: {first24:,}", color=INK, fontsize=6.5, va="center")
    ax.text(0.02, 0.99, f"Citations through {LAST_YEAR}: {total:,}\nThe two JIF years count {counted:,} ({counted / total:.1%})",
            transform=ax.transAxes, fontsize=6.5, va="top", color=INK)
    ax.set_ylim(0, top)
    ax.set_xlim(y0 - 0.8, LAST_YEAR + 0.8)
    ax.set_xticks(range((y0 // 5 + 1) * 5, LAST_YEAR + 1, 5))
    ax.set_ylabel("Citations per year")
    ax.set_xlabel("Year")
    ax.grid(axis="x", visible=False)
    ax.set_title(title, loc="left", fontsize=8.5)
    csv_rows += [[p, int(y), int(n), "published" if y == y0 else "JIF year" if y in (y0 + 1, y0 + 2) else "later"]
                 for y, n in zip(years, v)]
    return first24, counted, total


def agree(ids):
    """PMIDs whose year and month match between impact.db and pubmed_full.db."""
    full = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    ok = set()
    ids = [int(x) for x in ids]
    for s in range(0, len(ids), 900):
        ch = ids[s:s + 900]
        q = ",".join("?" * len(ch))
        a = {r[0]: r[1:] for r in con.execute(f"SELECT pmid, pub_year, pub_month FROM papers WHERE pmid IN ({q})", ch)}
        b = {r[0]: r[1:] for r in full.execute(f"SELECT pmid, pub_year, pub_month FROM pubmed WHERE pmid IN ({q})", ch)}
        ok |= {k for k, v in a.items() if b.get(k) == v}
    return ok


def twin_pairs(row, K):
    """January and December papers: same journal, year and class, with citations at months 36-71 within 8%, at least 20.
    Matching uses only months after both windows compared, so neither result is built in. Pairs are made by walking both
    lists in order of citations, so each paper is used once."""
    ry, rm, rc = py[row], pm[row], dc[row]
    s = np.flatnonzero((rc <= 1) & (ry >= COHORT[0]) & (ry <= COHORT[1]) & ((rm == 1) | (rm == 12)))
    T = K[s, 36:72].astype(np.int64).sum(axis=1)
    keep = T >= 20
    s, T = s[keep], T[keep]
    groups = defaultdict(lambda: ([], []))
    for i, t in zip(s, T):
        groups[(int(jid[row[i]]), int(ry[i]), int(rc[i]))][0 if rm[i] == 1 else 1].append((int(t), int(i)))
    pairs = []
    for a, b in groups.values():
        a.sort(); b.sort()
        ia = ib = 0
        while ia < len(a) and ib < len(b):
            ta, tb = a[ia][0], b[ib][0]
            if abs(ta - tb) / max(ta, tb) <= 0.08:
                pairs.append((a[ia][1], b[ib][1])); ia += 1; ib += 1
            elif ta < tb:
                ia += 1
            else:
                ib += 1
    return np.array(pairs)


def pair_stats(name, a, b):
    return [name, "citations at months 36-71", len(a), round(a.mean(), 3), round(b.mean(), 3), round(b.sum() / a.sum(), 4), float(np.median(a)), float(np.median(b)),
            round(float(np.median(a - b)), 2), round(float((a > b).mean()), 4), round(float((a < b).mean()), 4)]


def box(ax, x, v, color):
    q = np.percentile(v, [5, 25, 50, 75, 95])
    ax.bxp([dict(med=q[2], q1=q[1], q3=q[3], whislo=q[0], whishi=q[4], fliers=[])], positions=[x], widths=0.62, showfliers=False,
           patch_artist=True, boxprops=dict(facecolor=color, edgecolor=color, alpha=0.3), medianprops=dict(color=color, linewidth=1.6),
           whiskerprops=dict(color=color, linewidth=0.9), capprops=dict(color=color, linewidth=0.9))
    ax.scatter([x], [v.mean()], marker="D", s=20, color=color, zorder=4, edgecolor="white", linewidth=0.5)


def month_axis(ax):
    ax.set_xticks(range(1, 13), LETTERS)
    ax.set_xlabel("Publication month (June omitted)")


def main():
    fig = plt.figure(figsize=(7.2, 10.2))
    gs = fig.add_gridspec(4, 2, hspace=0.52, wspace=0.27, height_ratios=[1, 1, 1, 1])

    # A, B
    rows = []
    a = paper_panel(fig.add_subplot(gs[0, 0]), 16275915, 2005, 11, "A  Hirsch, PNAS, Nov 2005 (h-index)", rows)
    b = paper_panel(fig.add_subplot(gs[0, 1]), 21376230, 2011, 3, "B  Hanahan & Weinberg, Cell, Mar 2011 (Hallmarks)", rows)
    print("A", a, "B", b, flush=True)
    write_csv("f1ab_paper_citations_by_year", ["pmid", "year", "citations", "status"], rows)
    handles = [matplotlib.patches.Patch(color=c, label=t) for c, t in
               ((DARK, "Year published (no JIF counts it)"), (BLUE, "First JIF year"), (GREEN, "Second JIF year"),
                (LIGHT, "Later years (no JIF counts them)"))]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=4, fontsize=6.5, frameon=False,
               handlelength=1.1, columnspacing=1.2)

    # data by month of age
    E = np.load(os.path.join(DATA, "ages72.npz"))
    row, K = E["row"], E["counts"]
    ry, rm, rc = py[row], pm[row], dc[row]
    in_cohort = (ry >= COHORT[0]) & (ry <= COHORT[1]) & (rm >= 1) & (rm != 6)
    curves = {}
    for lab, cls in (("Research articles", 0), ("Reviews", 1)):
        s = np.flatnonzero(in_cohort & (rc == cls))
        curves[lab] = (K[s, :60].sum(axis=0, dtype=np.float64) / len(s), len(s))
    curve, n_research = curves["Research articles"]
    write_csv("f1c_age_curve", ["age_months", "mean_citations", "papers"], [[i, round(v, 5), n_research] for i, v in enumerate(curve)])

    # C
    ax = fig.add_subplot(gs[1, 0])
    ax.plot(np.arange(60), curve, color=BLUE, linewidth=1.8)
    top = curve.max()
    for y, (lo, hi), lab, color in ((top * 1.5, (12, 35), "January paper: JIF counts months 12–35", BLUE),
                                    (top * 1.22, (1, 24), "December paper: JIF counts months 1–24", ORANGE)):
        ax.plot([lo, hi], [y, y], color=color, linewidth=3, solid_capstyle="butt")
        ax.text(hi + 1, y, f"{curve[lo:hi + 1].sum():.1f} citations", fontsize=6.3, color=INK, va="center")
        ax.text(lo, y + top * 0.06, lab, fontsize=6.3, color=INK, va="bottom")
    ax.set_ylim(0, top * 1.72)
    ax.set_xlim(0, 59)
    ax.set_xticks([0, 12, 24, 36, 48])
    ax.set_xlabel("Months since publication")
    ax.set_ylabel("Mean citations per month")
    ax.set_title("C  Citations by months since publication", loc="left", fontsize=8.5)

    # D
    P = twin_pairs(row, K)
    ja, jb = K[P[:, 0], 12:36].astype(float).sum(axis=1), K[P[:, 1], 1:25].astype(float).sum(axis=1)
    fa, fb = K[P[:, 0], 0:24].astype(float).sum(axis=1), K[P[:, 1], 0:24].astype(float).sum(axis=1)
    ok_ids = agree(np.r_[pmid[row[P[:, 0]]], pmid[row[P[:, 1]]]])
    both = np.array([int(pmid[row[x]]) in ok_ids and int(pmid[row[y]]) in ok_ids for x, y in P])
    write_csv("f1d_pairs_summary", ["measure", "matched_on", "pairs", "jan_mean", "dec_mean", "dec_over_jan", "jan_median", "dec_median", "median_jan_minus_dec",
                                    "share_jan_higher", "share_dec_higher"],
              [pair_stats("jif_counted", ja, jb), pair_stats("first_24_months", fa, fb),
               pair_stats("jif_counted_dates_agree", ja[both], jb[both]), pair_stats("first_24_months_dates_agree", fa[both], fb[both])])
    ax = fig.add_subplot(gs[1, 1])
    box(ax, 0, ja, BLUE); box(ax, 0.8, jb, ORANGE); box(ax, 2.2, fa, BLUE); box(ax, 3.0, fb, ORANGE)
    ax.set_xticks([0.4, 2.6], ["Citations a JIF counts", "First 24 months"])
    ax.set_xlim(-0.6, 3.6)
    hi = np.percentile(np.r_[ja, jb, fa, fb], 95) * 1.6
    ax.set_ylim(0, hi)
    ax.text(0.4, hi * 0.97, f"December gets {jb.sum() / ja.sum():.1%}", ha="center", va="top", fontsize=6.5, color=INK)
    ax.text(2.6, hi * 0.97, f"December gets {fb.sum() / fa.sum():.1%}", ha="center", va="top", fontsize=6.5, color=INK)
    ax.set_ylabel("Citations per paper")
    ax.grid(axis="x", visible=False)
    ax.legend(handles=[matplotlib.patches.Patch(color=BLUE, alpha=0.5, label="January paper"), matplotlib.patches.Patch(color=ORANGE, alpha=0.5, label="December paper"),
                       matplotlib.lines.Line2D([], [], marker="D", color=MUTED, linestyle="", markersize=3.5, label="Mean")],
              fontsize=5.8, loc="upper center", bbox_to_anchor=(0.5, 0.92), ncol=3, handlelength=1, columnspacing=0.9)
    ax.set_title("D  Citations of matched January and December papers", loc="left", fontsize=8.5)

    # E
    idx = np.flatnonzero((dc == 0) & (py >= 2010) & (py <= 2022))
    y = py[idx].astype(int) - Y0
    yr = [C[idx, y + k].astype(np.float64) for k in (1, 2, 3)]
    mo = pm[idx]
    table = [[NAMES[m - 1], int((mo == m).sum())] + [round(v[mo == m].mean(), 3) for v in yr] for m in MONTHS]
    write_csv("f1e_citations_per_year", ["month", "research_articles", "year_1", "year_2", "year_3"], table)
    ax = fig.add_subplot(gs[2, 0])
    x = np.array(MONTHS)
    for k, color, lab in ((4, GRAY, "Third year after publication (no JIF counts it)"), (3, GREEN, "Second year (JIF counts it)"), (2, BLUE, "First year (JIF counts it)")):
        v = np.array([r[k] for r in table])
        ax.plot(x, v, color=color, marker="o", markersize=3, linewidth=1.5, label=lab)
        ax.text(12.25, v[-1] + {4: 0.13, 3: -0.13, 2: 0}[k], f"−{1 - v[-1] / v[0]:.0%}", fontsize=6.3, color=INK, va="center")
    ax.set_ylim(0, 5.3)
    ax.set_xlim(0.5, 13.4)
    month_axis(ax)
    ax.set_ylabel("Mean citations per year")
    ax.legend(fontsize=5.8, loc="upper left", handlelength=1.6, labelspacing=0.25)
    ax.set_title("E  Citations per year, by publication month", loc="left", fontsize=8.5)

    # F
    rows, journals = [], set()
    for Y in range(2005, 2025):
        s = (py == Y) & (dc <= 3) & (pm >= 1) & (pm != 6)
        r, o = s & (dc == 1), s & (dc != 1)
        journals |= set(np.unique(jid[s]).tolist())
        rows.append([Y, int(r.sum()), int(o.sum()), round(100 * np.isin(pm[r], (1, 2, 3)).mean(), 2), round(100 * np.isin(pm[o], (1, 2, 3)).mean(), 2)])
    write_csv("f1f_reviews_early_by_year", ["year", "reviews", "other_citable_items", "reviews_jan_mar", "other_jan_mar"], rows)
    ax = fig.add_subplot(gs[2, 1])
    ax.plot([r[0] for r in rows], [r[3] for r in rows], color=VERMILION, linewidth=1.6, label="Reviews")
    ax.plot([r[0] for r in rows], [r[4] for r in rows], color=BLUE, linewidth=1.6, linestyle=(0, (3, 2)), label="Other citable items")
    ax.set_ylim(0, 40)
    ax.set_xlim(2005, 2024)
    ax.set_xticks([2005, 2010, 2015, 2020])
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(100, decimals=0))
    ax.set_xlabel("Year published")
    ax.set_ylabel("Share published Jan–Mar")
    ax.legend(fontsize=6, loc="lower left")
    ax.set_title("F  Share of items published January to March", loc="left", fontsize=8.5)

    # G
    ax = fig.add_subplot(gs[3, 0])
    rows = []
    for lab, color in (("Research articles", BLUE), ("Reviews", VERMILION)):
        c, n = curves[lab]
        w = np.array([c[13 - m:37 - m].sum() for m in range(1, 13)])
        credit = w / w.mean()
        rows += [[lab, NAMES[m - 1], round(float(credit[m - 1]), 4), n] for m in range(1, 13)]
        ax.plot(MONTHS, [credit[m - 1] - 1 for m in MONTHS], color=color, marker="o", markersize=3, linewidth=1.5, label=f"{lab} (n = {n:,})")
    write_csv("f1g_credit_by_month", ["series", "month", "credit", "papers"], rows)
    ax.axhline(0, color=GRAY, linewidth=0.7)
    month_axis(ax)
    ax.set_ylim(-0.2, 0.2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0%}".replace("-", "−") if abs(v) > 1e-9 else "0%"))
    ax.set_ylabel("JIF credit vs average month")
    ax.legend(fontsize=5.8, loc="lower left")
    ax.set_title("G  JIF credit by publication month", loc="left", fontsize=8.5)

    # H
    s = np.flatnonzero(in_cohort & (rc == 0) & (rm != 6))
    mo = rm[s]
    key = jid[row[s]].astype(np.int64) * 10000 + ry[s]
    _, grp = np.unique(key, return_inverse=True)
    ax = fig.add_subplot(gs[3, 1])
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
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0%}".replace("-", "−") if abs(v) > 1e-9 else "0%"))
    ax.set_ylabel("All citations vs average month")
    ax.legend(fontsize=5.8, loc="lower left", ncol=2, columnspacing=0.8, handlelength=1.4)
    ax.set_title("H  All citations by publication month, at matched ages", loc="left", fontsize=8.5)
    save(fig, "F1_publication_month")


if __name__ == "__main__":
    main()
