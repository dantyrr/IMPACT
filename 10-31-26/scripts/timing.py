"""Figure 9: does publishing early in the year raise a journal's JIF, and do journals exploit it?

A calendar-year JIF counts a paper's citations in the two calendar years after it is
published. In months of age that is ages 13-m to 36-m for a paper published in
month m: a January paper is counted from 12 to 35 months old, a December paper from
1 to 24 months. IMPACT's rolling 24-month window gives every paper the same window.

For every citable item published 2014-2021 (ages.npz from citation_ages.py), W[i, m]
is the citations the JIF would count if paper i had been published in month m. Then:

  credit(m)       mean over papers of W[i, m] / mean_m W[i, m]    (the month's structural advantage)
  journal gain    sum W[i, actual month] / sum mean_m W[i, m] - 1 (how much the journal's JIF gains from
                  its papers' actual months vs the same papers spread evenly over the year)
  placement gain  gain minus its mean under months shuffled among the journal's own papers within each
                  publication year: whether the journal puts its most-cited papers in its early months,
                  beyond publishing more in those months

Reviews in January-March: per journal, share of reviews vs share of other citable items
published Jan-Mar (Fisher's exact test, Benjamini-Hochberg across journals).

June is left out throughout: PubMed's parser assigns June to papers with no month.

Usage: python 10-31-26/scripts/timing.py   (from the IMPACT folder)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import (BLUE, VERMILION, GREEN, GRAY, INK, MUTED, DATA, con, dc, jid, pm, pmid, py, slug2id, jname,  # noqa: E402
                          matplotlib, np, plt, save, write_csv)
from scipy.stats import fisher_exact  # noqa: E402

MONTHS = [m for m in range(1, 13) if m != 6]
NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MIN_ITEMS = 300                  # journals with at least this many items (2014-2021, June excluded)
PERMS = 200
abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))

A = np.load(os.path.join(DATA, "ages.npz"))
row, counts = A["row"], A["counts"].astype(np.int32)
keep = pm[row] != 6
row, counts = row[keep], counts[keep]
J, M, P, K = jid[row], pm[row].astype(int), py[row], dc[row]
cs = np.concatenate([np.zeros((len(row), 1), np.int64), np.cumsum(counts, axis=1)], axis=1)
W = np.stack([cs[:, 37 - m] - cs[:, 13 - m] for m in range(1, 13)], axis=1).astype(np.float64)   # n x 12
W = W[:, [m - 1 for m in MONTHS]]                                       # months a paper can be assigned
col = {m: k for k, m in enumerate(MONTHS)}
mcol = np.array([col[m] for m in M])
actual = W[np.arange(len(W)), mcol]
neutral = W.mean(axis=1)
c24 = counts[:, :24].sum(axis=1)                                        # month-neutral citability
print(f"{len(row):,} papers", flush=True)


def credit_by_month(mask):
    w, n = W[mask], neutral[mask]
    ok = n > 0
    return (w[ok] / n[ok, None]).mean(axis=0), int(ok.sum())


def journal_stats():
    rng = np.random.default_rng(0)
    order = np.lexsort((P, J))
    Js, Ps = J[order], P[order]
    starts = np.flatnonzero(np.r_[True, (Js[1:] != Js[:-1])])
    out = []
    for a, b in zip(starts, np.r_[starts[1:], len(order)]):
        if b - a < MIN_ITEMS:
            continue
        idx = order[a:b]
        den = neutral[idx].sum()
        if den < 500:
            continue
        gain = actual[idx].sum() / den - 1
        # shuffle months among the journal's papers within each publication year
        grp = np.flatnonzero(np.r_[True, Ps[a + 1:b] != Ps[a:b - 1]])
        bounds = list(zip(grp, np.r_[grp[1:], b - a]))
        null = np.empty(PERMS)
        for k in range(PERMS):
            perm = mcol[idx].copy()
            for s, e in bounds:
                perm[s:e] = rng.permutation(perm[s:e])
            null[k] = W[idx, perm].sum() / den - 1
        rev = K[idx] == 1
        q1 = M[idx] <= 3
        nr, no = int(rev.sum()), int((~rev).sum())
        table = [[int((rev & q1).sum()), int((rev & ~q1).sum())], [int((~rev & q1).sum()), int((~rev & ~q1).sum())]]
        p_rev = fisher_exact(table)[1] if nr >= 20 else np.nan
        top = np.zeros(len(idx), bool)
        for s, e in bounds:
            v = c24[idx[s:e]]
            if e - s >= 10:
                top[s:e] = v >= np.quantile(v, 0.9)
        out.append(dict(j=int(Js[a]), items=int(b - a), gain=gain, null_mean=null.mean(), null_sd=null.std(),
                        placement=gain - null.mean(), z=(gain - null.mean()) / max(null.std(), 1e-9),
                        reviews=nr, rev_q1=table[0][0] / max(nr, 1), other_q1=table[1][0] / max(no, 1), p_rev=p_rev,
                        top_q1=float(q1[top].mean()) if top.any() else np.nan, rest_q1=float(q1[~top].mean()),
                        q1=float(q1.mean())))
    return out


def bh(p):
    p = np.asarray(p, float)
    ok = ~np.isnan(p)
    q = np.full(len(p), np.nan)
    ps = p[ok]
    o = np.argsort(ps)
    r = ps[o] * len(ps) / np.arange(1, len(ps) + 1)
    r = np.minimum.accumulate(r[::-1])[::-1]
    qq = np.empty(len(ps)); qq[o] = np.minimum(r, 1)
    q[ok] = qq
    return q


SERIES = [   # (journal slug, SQL title pattern, label)
    ("ca-a-cancer-journal-for-clinicians", "Cancer statistics, 2%", "Cancer Statistics (CA Cancer J Clin)"),
    ("circulation", "Heart Disease and Stroke Statistics%", "Heart Disease and Stroke Statistics (Circulation)"),
    ("diabetes-care", "%Standards of %Care in Diabetes%", "ADA Standards of Care (Diabetes Care)"),
    ("alzheimer-s-dementia-the-journal-of-the-alzheimer-s-association", "%Alzheimer%s disease facts and figures%",
     "Alzheimer's Facts and Figures (Alzheimers Dement)"),
    ("neuro-oncology", "CBTRUS Statistical Report%", "CBTRUS Statistical Report (Neuro Oncol)"),
    ("nucleic-acids-research", "%Database resources of the National Center%", "NCBI database resources (Nucleic Acids Res)"),
    ("european-heart-journal", "%ESC Guidelines%", "ESC Guidelines (Eur Heart J)"),
    ("journal-of-the-american-college-of-cardiology", "%ACC/AHA%Guideline%", "ACC/AHA Guidelines (JACC)"),
]


def series_rows(slug, pat, years=(2014, 2021)):
    j = slug2id[slug]
    ps = {p for p, in con.execute("SELECT pmid FROM papers WHERE journal_id = ? AND title LIKE ? AND pub_year BETWEEN ? AND ?",
                                  (j, pat, *years))}
    return np.flatnonzero(np.isin(pmid[row], list(ps)))


LABEL_C = ["Cell", "J Clin Invest", "Value Health", "J Exp Biol", "Diabetes Care", "J Nanosci Nanotechnol"]
LABEL_C_OFFSET = {"Cell": (-6, 4), "J Clin Invest": (16, -10), "Diabetes Care": (14, 8)}
LABEL_B = ["Diabetes Care", "Lancet", "Nature", "PLoS One", "J Transl Med"]


def main():
    fig = plt.figure(figsize=(7.2, 6.6))
    gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.3)
    rows = []
    x = np.array(MONTHS)

    # A: structural advantage by month
    ax = fig.add_subplot(gs[0, 0])
    for lab, mask, color in [("Research articles", K == 0, BLUE), ("Reviews", K == 1, VERMILION)]:
        cr, n = credit_by_month(mask)
        ax.plot(x, cr, color=color, marker="o", markersize=3.5, label=f"{lab} (n = {n:,})")
        rows += [["A", lab, NAMES[m - 1], round(float(v), 4)] for m, v in zip(MONTHS, cr)]
    ax.axhline(1, color=GRAY, linewidth=0.8)
    ax.set_xticks(range(1, 13), [n[0] for n in NAMES])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v - 1:+.0%}"))
    ax.set_ylabel("JIF-counted citations vs month-neutral")
    ax.set_xlabel("Publication month (June omitted)")
    ax.legend(fontsize=6, loc="lower left")
    ax.set_title("A  The same paper, published in each month", loc="left", fontsize=8.5)

    # B: do journals place their most-cited papers early? placement gain per journal
    st = journal_stats()
    print(f"{len(st):,} journals", flush=True)
    ax = fig.add_subplot(gs[0, 1])
    pl = np.array([s["placement"] for s in st]) * 100
    bins = np.arange(-8, 8.01, 0.5)
    ax.hist(np.clip(pl, -7.99, 7.99), bins=bins, color=GRAY, edgecolor="white", linewidth=0.4)
    ax.axvline(0, color=INK, linewidth=0.8)
    hi, lo = int((pl >= 2).sum()), int((pl <= -2).sum())
    ax.text(0.98, 0.97, f"gain ≥ 2%: {hi} journals\nlose ≥ 2%: {lo} journals\nmedian {np.median(pl):+.2f}%",
            transform=ax.transAxes, ha="right", va="top", fontsize=6.3, color=INK)
    by_abbr = {abbr[s["j"]]: v for s, v in zip(st, pl)}
    top = ax.get_ylim()[1]
    for k, name in enumerate(LABEL_B):
        if name in by_abbr:
            v = float(np.clip(by_abbr[name], -7.9, 7.9))
            tx = -4.5 if v < 0 else 4.5
            ax.annotate(f"{name} {by_abbr[name]:+.1f}%", (v, top * 0.02), xytext=(tx, top * (0.55 - 0.09 * k)),
                        fontsize=5.6, ha="right" if v < 0 else "left", va="center",
                        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.5, shrinkA=1, shrinkB=0))
    ax.set_xlabel("JIF change from which papers land in early months (%)")
    ax.set_ylabel("Journals")
    ax.set_title(f"B  Placement of cited papers, {len(st):,} journals", loc="left", fontsize=8.5)
    rows += [["B", "placement_gain_hist", float(b), int(c)] for b, c in zip(bins[:-1], np.histogram(np.clip(pl, -7.99, 7.99), bins)[0])]

    # C: reviews published Jan-Mar vs other citable items
    ax = fig.add_subplot(gs[1, 0])
    q = bh([s["p_rev"] for s in st])
    ro = np.array([s["rev_q1"] for s in st]); oo = np.array([s["other_q1"] for s in st])
    has = ~np.isnan(q)
    sig_hi = has & (q < 0.05) & (ro > oo)
    sig_lo = has & (q < 0.05) & (ro < oo)
    ax.scatter(oo[has] * 100, ro[has] * 100, s=4, color=GRAY, alpha=0.35, linewidths=0)
    ax.scatter(oo[sig_hi] * 100, ro[sig_hi] * 100, s=8, color=VERMILION, linewidths=0,
               label=f"More reviews early (FDR < 5%): {int(sig_hi.sum())}")
    ax.scatter(oo[sig_lo] * 100, ro[sig_lo] * 100, s=8, color=BLUE, linewidths=0,
               label=f"Fewer reviews early: {int(sig_lo.sum())}")
    ax.plot([0, 100], [0, 100], color=INK, linewidth=0.7, linestyle="--")
    for i, s in enumerate(st):
        name = abbr[s["j"]]
        if name in LABEL_C and has[i]:
            dx, dy = LABEL_C_OFFSET.get(name, (4, 0))
            ax.annotate(name, (oo[i] * 100, ro[i] * 100), fontsize=5.6, xytext=(dx, dy), textcoords="offset points",
                        va="center", ha="right" if dx < 0 else "left",
                        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.4) if abs(dy) > 3 else None)
    ax.set_xlim(0, 60); ax.set_ylim(0, 100)
    ax.set_xlabel("Other citable items published Jan–Mar (%)")
    ax.set_ylabel("Reviews published Jan–Mar (%)")
    ax.legend(fontsize=6, loc="upper left")
    ax.set_title(f"C  Reviews early in the year ({int(has.sum()):,} journals)", loc="left", fontsize=8.5)

    # D: month credit for annual reports, against all research articles
    ax = fig.add_subplot(gs[1, 1])
    cr, _ = credit_by_month(K == 0)
    ax.plot(x, cr, color=GRAY, linewidth=1.5, label="All research articles")
    for (slug, pat, lab), color in [(SERIES[2], VERMILION), (SERIES[6], BLUE), (SERIES[7], GREEN)]:
        idx = series_rows(slug, pat)
        mask = np.zeros(len(row), bool); mask[idx] = True
        c, n = credit_by_month(mask)
        ax.plot(x, c, color=color, marker="o", markersize=3, linewidth=1.5, label=f"{lab.split(' (')[0]} (n = {n})")
        rows += [["D", lab, NAMES[m - 1], round(float(v), 4)] for m, v in zip(MONTHS, c)]
    ax.axhline(1, color=GRAY, linewidth=0.6, linestyle=":")
    ax.set_xticks(range(1, 13), [n[0] for n in NAMES])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v - 1:+.0%}"))
    ax.set_xlabel("Publication month (June omitted)")
    ax.legend(fontsize=6, loc="upper right")
    ax.set_title("D  Annual reports replaced each year", loc="left", fontsize=8.5)
    save(fig, "fig9_publication_timing")

    # E-G (own figures): annual_reports.py
    write_csv("fig9_publication_timing", ["panel", "series", "x", "value"], rows)
    write_csv("fig9_journal_timing", ["journal", "abbreviation", "items_2014_21", "jif_gain_from_months",
                                      "gain_if_months_shuffled", "placement_gain", "placement_z", "share_items_jan_mar",
                                      "reviews", "reviews_jan_mar", "other_jan_mar", "reviews_fdr_q",
                                      "top10pct_jan_mar", "rest_jan_mar"],
              [[jname[s["j"]], abbr[s["j"]], s["items"], round(s["gain"], 4), round(s["null_mean"], 4),
                round(s["placement"], 4), round(s["z"], 2), round(s["q1"], 4), s["reviews"], round(s["rev_q1"], 4),
                round(s["other_q1"], 4), "" if np.isnan(qq) else round(float(qq), 5),
                "" if np.isnan(s["top_q1"]) else round(s["top_q1"], 4), round(s["rest_q1"], 4)]
               for s, qq in sorted(zip(st, q), key=lambda t: -t[0]["placement"])])


if __name__ == "__main__":
    main()
