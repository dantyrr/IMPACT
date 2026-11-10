"""
Alternative examples for the draft's Figures 1-7 (10-31-26). Each alt figure keeps
the point of the draft figure and offers other journals or papers to make it,
plus a whole-field panel where one helps. Output: 10-31-26/alt/altN_*.png/.pdf
and 10-31-26/alt/data/*.csv.

Monthly rolling rates come from the site's own exports (docs/data/journals/*.json,
the 24-month window), drawn through the settled month (export month - 12).
JIF-style yearly rates come from the citation matrix, as in make_figures.py.

Usage:
    python 10-31-26/scripts/alt_figures.py            # all
    python 10-31-26/scripts/alt_figures.py 1 3        # only alt1 and alt3
"""

import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import (BLUE, VERMILION, GREEN, PURPLE, GRAY, INK, MUTED, Y0, C, con, dc, jid,  # noqa: E402
                          matplotlib, np, plt, pm, pmid, py, series_membership, slug2id, OUT, ROOT)

ALT = os.path.join(OUT, "alt")
os.makedirs(os.path.join(ALT, "data"), exist_ok=True)
JSON = os.path.join(ROOT, "docs", "data", "journals")
SETTLED = "2025-10"
START = "2012-01"
ORANGE, SKY = "#E69F00", "#56B4E9"

SHORT = {
    "nature": "Nature", "nature-communications": "Nat Commun", "scientific-reports": "Sci Rep",
    "science": "Science", "science-advances": "Sci Adv", "cell": "Cell", "cell-reports": "Cell Rep",
    "iscience": "iScience", "circulation": "Circulation", "jaha": "JAHA", "jama": "JAMA",
    "jama-network-open": "JAMA Netw Open", "bmj": "BMJ", "bmj-open": "BMJ Open", "lancet": "Lancet",
    "nejm": "NEJM", "immunity": "Immunity", "neuron": "Neuron",
    "journal-of-immunology-baltimore-md-1950": "J Immunol", "frontiers-in-immunology": "Front Immunol",
    "cancer-research": "Cancer Res", "cancers": "Cancers", "journal-of-virology": "J Virol", "viruses": "Viruses",
    "the-journal-of-biological-chemistry": "J Biol Chem", "international-journal-of-molecular-sciences": "Int J Mol Sci",
    "the-journal-of-neuroscience-the-official-journal-of-the-society-for-neuroscience": "J Neurosci",
    "frontiers-in-neuroscience": "Front Neurosci", "the-journal-of-physiology": "J Physiol",
    "frontiers-in-physiology": "Front Physiol", "endocrinology": "Endocrinology",
    "frontiers-in-endocrinology": "Front Endocrinol", "circulation-research": "Circ Res",
    "frontiers-in-cardiovascular-medicine": "Front Cardiovasc Med", "mbio": "mBio",
    "frontiers-in-microbiology": "Front Microbiol", "diabetes-care": "Diabetes Care",
    "ca-a-cancer-journal-for-clinicians": "CA Cancer J Clin", "autophagy": "Autophagy",
    "journal-of-the-american-college-of-cardiology": "JACC", "european-heart-journal": "Eur Heart J",
    "alzheimer-s-dementia-the-journal-of-the-alzheimer-s-association": "Alzheimers Dement",
    "nucleic-acids-research": "Nucleic Acids Res", "journal-of-hypertension": "J Hypertens",
    "international-journal-of-surgery-london-england": "Int J Surg",
    "journal-of-the-american-geriatrics-society": "J Am Geriatr Soc", "cells": "Cells",
    "signal-transduction-and-targeted-therapy": "Signal Transduct Target Ther", "molecular-cancer": "Mol Cancer",
    "proceedings-of-the-national-academy-of-sciences-of-the-united-states-of-america": "PNAS",
    "nutrients": "Nutrients", "frontiers-in-pharmacology": "Front Pharmacol", "pnas-nexus": "PNAS Nexus", "eclinicalmedicine": "eClinicalMedicine",
}


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(ALT, f"{name}.{ext}"), bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)


def write_csv(name, header, rows):
    with open(os.path.join(ALT, "data", name + ".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _bt(e, t, f):
    return e.get("by_type", {}).get(t, {}).get(f, 0)


def series(slug):
    """Monthly 24-month rolling rates START..SETTLED, and papers published per year by type."""
    d = json.load(open(os.path.join(JSON, slug + ".json")))
    ts = d["timeseries"]
    rows = [e for e in ts if START <= e["month"] <= SETTLED]

    def rate(t):
        return np.array([_bt(e, t, "citations") / _bt(e, t, "papers") if _bt(e, t, "papers") else np.nan for e in rows])

    pub = {}
    for e in ts:
        y = int(e["month"][:4])
        if y <= 2025:
            p = pub.setdefault(y, {})
            for t, n in e.get("pub_by_type", {}).items():
                p[t] = p.get(t, 0) + n
    # A new journal's rate means little until its 24-month paper window has filled.
    first = next((i for i, e in enumerate(ts) if e["citable_papers"] > 0), len(ts))
    ok = np.array([ts.index(e) >= first + 24 and e["citable_papers"] >= 30 for e in rows])
    blank = lambda a: np.where(ok, a, np.nan)
    return dict(name=d["journal"], months=[e["month"] for e in rows],
                x=np.array([int(e["month"][:4]) + (int(e["month"][5:]) - 0.5) / 12 for e in rows]),
                all=blank(np.array([e["rolling_if"] for e in rows], float)), res=blank(rate("research")),
                rev=blank(rate("review")),
                rev_share=np.array([_bt(e, "review", "papers") / e["citable_papers"] if e["citable_papers"] else np.nan
                                    for e in rows]), pub=pub)


def rate_panel(ax, s, slug, title, legend=False, ylim=None):
    ax.fill_between(s["x"], s["res"], s["all"], where=s["all"] >= s["res"], color=BLUE, alpha=0.15, linewidth=0)
    ax.plot(s["x"], s["all"], color=BLUE, linewidth=1.5, label="All citable items")
    ax.plot(s["x"], s["res"], color=VERMILION, linewidth=1.5, label="Research articles only")
    ax.set_title(title, loc="left", fontsize=8.5, pad=12)
    ax.set_ylim(0, ylim)
    ax.set_xlim(2012, 2026)
    ax.set_xticks([2013, 2017, 2021, 2025])
    ax.tick_params(labelsize=7)
    infl = s["all"][-1] / s["res"][-1] - 1
    ax.text(0, 1.02, f"{SETTLED[:4]}: {infl:+.0%} vs research only", transform=ax.transAxes, fontsize=6.2,
            color=MUTED, va="bottom")
    if legend:
        ax.figure.legend(*ax.get_legend_handles_labels(), loc="lower center", bbox_to_anchor=(0.5, 0.99), ncol=2,
                         fontsize=7, handlelength=1.5)


def rate_rows(name, slugs):
    rows = []
    for slug in slugs:
        s = series(slug)
        for m, a, r, v, sh in zip(s["months"], s["all"], s["res"], s["rev"], s["rev_share"]):
            rows.append([SHORT.get(slug, slug), m, round(a, 3), round(r, 3), round(v, 3), round(sh, 4)])
    write_csv(name, ["journal", "month", "rate_all_citable", "rate_research", "rate_reviews", "review_share_of_items"], rows)


def volume_panel(ax, s, title, legend=False):
    yrs = [y for y in sorted(s["pub"]) if 2010 <= y <= 2025]
    res = np.array([s["pub"][y].get("research", 0) for y in yrs])
    rev = np.array([s["pub"][y].get("review", 0) for y in yrs])
    ax.bar(yrs, res, color=BLUE, width=0.8, label="Research")
    ax.bar(yrs, rev, bottom=res, color=ORANGE, width=0.8, label="Reviews")
    ax.set_title(title, loc="left", fontsize=8.5, pad=12)
    ax.set_xticks([2010, 2015, 2020, 2025])
    ax.tick_params(labelsize=7)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    share = rev[-3:].sum() / max((res[-3:] + rev[-3:]).sum(), 1)
    ax.text(0, 1.02, f"Reviews 2023–25: {share:.0%}", transform=ax.transAxes, fontsize=6.2, color=MUTED, va="bottom")
    if legend:
        ax.figure.legend(*ax.get_legend_handles_labels(), loc="lower center", bbox_to_anchor=(0.5, 0.99), ncol=2,
                         fontsize=7, handlelength=1.2)
    return [[SHORT.get(title, title), y, int(a), int(b)] for y, a, b in zip(yrs, res, rev)]


# ---------------------------------------------------------------- alt 1: timing
def monthly(p):
    return con.execute("SELECT citing_year, citing_month, COUNT(*) FROM citations WHERE cited_pmid = ? "
                       "AND citing_month IS NOT NULL AND citing_class IS NULL GROUP BY 1, 2", (int(p),)).fetchall()


def timeline_panel(ax, p, y0, m0, label, years):
    """Monthly citations of one paper, the months each JIF counts, and its first 24 months."""
    cnt = {(y, m): n for y, m, n in monthly(p)}
    xs = [(y, m) for y in years for m in range(1, 13) if (y, m) >= (y0, m0)]
    x = np.arange(len(xs))
    v = np.array([cnt.get(k, 0) for k in xs])
    first24 = (x < 24)
    jif = {y0 + 1: v[[k[0] == y0 + 1 for k in xs]].sum(), y0 + 2: v[[k[0] == y0 + 2 for k in xs]].sum()}
    colors = [BLUE if k[0] == y0 + 1 else (GREEN if k[0] == y0 + 2 else GRAY) for k in xs]
    top = max(v) * 1.45
    ax.bar(x, v, color=colors, width=0.85)
    ax.set_ylim(0, top)
    ax.plot([-0.4, 23.4], [top * 0.9] * 2, color=VERMILION, linewidth=2.5, solid_capstyle="butt")
    ax.text(11.5, top * 0.92, f"First 24 months: {v[first24].sum():,}", ha="center", va="bottom",
            fontsize=6.5, color=INK)
    for y in (y0 + 1, y0 + 2):
        idx = [i for i, k in enumerate(xs) if k[0] == y]
        ax.text(np.mean(idx), top * 0.66, f"JIF {y}:\n{jif[y]:,}", ha="center", fontsize=6.5, color=INK)
    first = v[[k[0] == y0 for k in xs]].sum()
    n0 = sum(k[0] == y0 for k in xs)
    ax.text(-0.5, top * 0.42, f"{y0}: {first:,}\nnot counted", fontsize=6, color=MUTED, ha="left")
    ticks = [i for i, k in enumerate(xs) if k[1] == 1]
    ax.set_xticks(ticks, [str(xs[i][0]) for i in ticks])
    ax.set_xlim(-1, len(xs))
    ax.set_ylabel("Citations per month")
    ax.set_title(label, loc="left", fontsize=8.5)
    ax.grid(axis="x", visible=False)
    return [[p, f"{k[0]}-{k[1]:02d}", int(n)] for k, n in zip(xs, v)], dict(pub_year_cites=int(first), **{f"jif_{k}": int(n) for k, n in jif.items()},
                                                                               first24=int(v[first24].sum()))


def age_curve(n=6000, seed=1):
    """Mean citations by month of age (0-47) for research articles from 2012-2016 with a known
    month and at least one citation, sampled across all journals."""
    rng = np.random.default_rng(seed)
    tot = C.sum(axis=1)
    cand = np.flatnonzero((dc == 0) & (py >= 2012) & (py <= 2016) & (pm >= 1) & (pm != 6) & (tot > 0))
    pick = rng.choice(cand, n, replace=False)
    curve = np.zeros(48)
    for i in pick:
        for y, m, k in monthly(pmid[i]):
            a = (y - py[i]) * 12 + (m - pm[i])
            if 0 <= a < 48:
                curve[a] += k
    return curve / n


def alt1():
    print("alt1: publication timing")
    fig = plt.figure(figsize=(7.2, 7.0))
    gs = fig.add_gridspec(3, 2, hspace=0.6, wspace=0.3)
    rows, summ = [], []
    for k, (p, y0, m0, lab, yrs) in enumerate([
            (16275915, 2005, 11, "A  Hirsch, PNAS, Nov 2005 (h-index)", range(2005, 2009)),
            (21376230, 2011, 3, "B  Hanahan & Weinberg, Cell, Mar 2011 (Hallmarks)", range(2011, 2015))]):
        r, s = timeline_panel(fig.add_subplot(gs[0, k]), p, y0, m0, lab, yrs)
        rows += r
        summ.append([p, y0, m0, s["pub_year_cites"], s[f"jif_{y0+1}"], s[f"jif_{y0+2}"], s["first24"]])
    write_csv("alt1ab_monthly_citations", ["pmid", "month", "citations"], rows)
    write_csv("alt1ab_summary", ["pmid", "pub_year", "pub_month", "citations_in_pub_year_never_counted",
                                 "citations_counted_jif_year1", "citations_counted_jif_year2", "first_24_months"], summ)

    # C: same paper, any month: expected counted citations by publication month
    curve = age_curve()
    months = np.arange(1, 13)
    counted = np.array([curve[12 - m + 1:12 - m + 25].sum() for m in months])   # calendar years P+1, P+2
    lost = np.array([curve[:12 - m + 1].sum() for m in months])                 # year of publication
    first24 = curve[:24].sum()
    ax = fig.add_subplot(gs[1, 0])
    ax.bar(months, counted / counted[0], color=BLUE, width=0.7)
    ax.axhline(first24 / counted[0], color=VERMILION, linewidth=1.2, linestyle="--")
    ax.text(12.6, first24 / counted[0] - 0.02, "First 24\nmonths,\nany month", fontsize=6.5, va="top", color=INK)
    ax.set_xticks(months, ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_ylim(0, 1.15)
    ax.set_xlim(0.3, 15)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_ylabel("JIF-counted citations\n(relative to January)")
    ax.set_xlabel("Publication month")
    ax.set_title("C  The same typical paper, published in each month", loc="left", fontsize=8.5)
    ax.grid(axis="x", visible=False)
    ax.text(12, counted[-1] / counted[0] + 0.03, f"{counted[-1] / counted[0]:.0%}", ha="center", fontsize=6.5)

    ax = fig.add_subplot(gs[1, 1])
    ax.plot(np.arange(48), curve, color=BLUE, linewidth=1.5)
    ax.set_xlabel("Months since publication")
    ax.set_ylabel("Mean citations per month")
    ax.set_xticks([0, 12, 24, 36, 48])
    ax.set_xlim(0, 47)
    ax.set_ylim(0, None)
    ax.set_title("D  Citation curve used in C (6,000 articles, 2012–16)", loc="left", fontsize=8.5)
    write_csv("alt1cd_model", ["pub_month", "counted_rel_jan", "counted", "lost_in_pub_year", "first24"],
              [[m, round(c / counted[0], 4), round(c, 4), round(l, 4), round(first24, 4)] for m, c, l in zip(months, counted, lost)])
    write_csv("alt1d_age_curve", ["age_months", "mean_citations"], [[a, round(v, 5)] for a, v in enumerate(curve)])

    # E: December vs January twins: lifetime citations alike, JIF-counted citations not
    ax = fig.add_subplot(gs[2, :])
    tot = C[:, :2026 - Y0].astype(np.int64).sum(axis=1)
    pairs = []
    for s in ["nature", "science", "cell", "nejm", "lancet", "circulation"]:
        j = slug2id[s]
        best = None
        for P in range(2008, 2019):
            m = (jid == j) & (py == P) & (dc <= 1)
            jan = np.flatnonzero(m & (pm == 1) & (tot >= 500))
            dec_ = np.flatnonzero(m & (pm == 12) & (tot >= 500))
            for a in jan:
                for b in dec_:
                    if abs(tot[a] - tot[b]) / max(tot[a], tot[b]) > 0.08:
                        continue
                    ca = int(C[a, P + 1 - Y0]) + int(C[a, P + 2 - Y0])
                    cb = int(C[b, P + 1 - Y0]) + int(C[b, P + 2 - Y0])
                    if (best is None or ca / cb > best[0]) and _dates_agree(pmid[a]) and _dates_agree(pmid[b]):
                        best = (ca / cb, P, a, b, ca, cb)
        if best:
            pairs.append((s, *best))
    labels, xs = [], np.arange(len(pairs))
    for i, (s, ratio, P, a, b, ca, cb) in enumerate(pairs):
        ax.bar(i - 0.18, ca, width=0.34, color=BLUE, label="January paper" if i == 0 else None)
        ax.bar(i + 0.18, cb, width=0.34, color=ORANGE, label="December paper" if i == 0 else None)
        labels.append(f"{SHORT[s]} {P}\nlifetime {int(tot[a]):,} vs {int(tot[b]):,}")
    ax.set_xticks(xs, labels, fontsize=6.5)
    ax.set_ylabel("JIF-counted citations")
    ax.legend(fontsize=6.5, loc="upper left")
    ax.grid(axis="x", visible=False)
    ax.set_title("E  Twins: same journal and year, lifetime citations within 8%, published January vs December",
                 loc="left", fontsize=8.5)
    write_csv("alt1e_twins", ["journal", "pub_year", "jan_pmid", "jan_title", "jan_lifetime", "jan_counted",
                              "dec_pmid", "dec_title", "dec_lifetime", "dec_counted"],
              [[SHORT[s], P, int(pmid[a]), _title(pmid[a]), int(tot[a]), ca, int(pmid[b]), _title(pmid[b]), int(tot[b]), cb]
               for s, r, P, a, b, ca, cb in pairs])
    save(fig, "alt1_publication_timing")


_FULL = None


def _dates_agree(p):
    """True when impact.db and pubmed_full.db give the paper the same year and month
    (they differ for ~0.3% of papers, mostly online-in-December, issue-in-January)."""
    global _FULL
    if _FULL is None:
        import sqlite3
        _FULL = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    a = con.execute("SELECT pub_year, pub_month FROM papers WHERE pmid = ?", (int(p),)).fetchone()
    b = _FULL.execute("SELECT pub_year, pub_month FROM pubmed WHERE pmid = ?", (int(p),)).fetchone()
    return a == b


def _title(p):
    return con.execute("SELECT title FROM papers WHERE pmid = ?", (int(p),)).fetchone()[0]


# ---------------------------------------------------------------- alt 2: reviews lift rates
def field_inflation():
    rows = []
    for f in os.listdir(JSON):
        d = json.load(open(os.path.join(JSON, f)))
        e = next((x for x in d["timeseries"] if x["month"] == SETTLED), None)
        if not e or e["citable_papers"] < 200 or _bt(e, "research", "papers") < 100 or e["rolling_if"] < 1:
            continue
        rr = _bt(e, "research", "citations") / _bt(e, "research", "papers")
        if rr <= 0:
            continue
        rows.append([d["slug"], d["journal"], e["citable_papers"], round(e["rolling_if"], 3), round(rr, 3),
                     round(e["rolling_if"] / rr - 1, 4), round(_bt(e, "review", "papers") / e["citable_papers"], 4),
                     round(_bt(e, "review", "citations") / max(e["citable_citations"], 1), 4)])
    return rows


def alt2():
    print("alt2: reviews lift journal rates")
    rows = field_inflation()
    write_csv("alt2ab_review_lift_all_journals", ["slug", "journal", "citable_items", "rate_all", "rate_research",
                                                  "lift_from_reviews", "review_share_items", "review_share_citations"], rows)
    lift = np.array([r[5] for r in rows])
    share = np.array([r[6] for r in rows])
    by = {r[0]: r for r in rows}
    fig = plt.figure(figsize=(7.2, 6.6))
    gs = fig.add_gridspec(3, 4, hspace=0.75, wspace=0.6)

    ax = fig.add_subplot(gs[0, :2])
    ax.hist(np.clip(lift, -0.5, 1.5), bins=np.arange(-0.5, 1.55, 0.05), color=GRAY)
    marks = ["nejm", "nature", "science", "lancet", "journal-of-immunology-baltimore-md-1950", "cell",
             "frontiers-in-immunology", "circulation", "international-journal-of-molecular-sciences"]
    ymax = ax.get_ylim()[1]
    for k, s in enumerate(sorted(marks, key=lambda s: by[s][5])):
        v = by[s][5]
        ax.axvline(v, color=BLUE, linewidth=0.8)
        ax.text(v, ymax * (0.98 - 0.105 * (k % 9)), " " + SHORT[s], fontsize=6, color=INK, va="top")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_xlabel(f"All-citable rate over research-only rate ({SETTLED})")
    ax.set_ylabel("Journals")
    ax.set_title(f"A  {len(rows):,} journals, median {np.median(lift):+.0%}", loc="left", fontsize=8.5)

    ax = fig.add_subplot(gs[0, 2:])
    ax.scatter(share, lift, s=4, color=GRAY, alpha=0.4, linewidth=0)
    offs = {"nature": (-4, 6), "science": (-3, -10), "nejm": (5, -3), "journal-of-immunology-baltimore-md-1950": (4, 3),
            "circulation": (-4, 4), "international-journal-of-molecular-sciences": (4, 3),
            "frontiers-in-immunology": (4, -8)}
    for s in marks:
        ax.scatter(by[s][6], by[s][5], s=14, color=BLUE, edgecolor="white", linewidth=0.6, zorder=3)
        ax.annotate(SHORT[s], (by[s][6], by[s][5]), xytext=offs.get(s, (3, 2)), textcoords="offset points",
                    fontsize=6, ha="right" if offs.get(s, (1,))[0] < 0 else "left")
    ax.set_xlim(0, 0.6)
    ax.set_ylim(-0.5, 1.5)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_xlabel("Reviews as share of citable items")
    ax.set_ylabel("Lift over research-only rate")
    ax.set_title("B  More reviews, bigger lift", loc="left", fontsize=8.5)

    lifted = ["cell", "immunity", "neuron", "circulation", "jama", "cancers", "frontiers-in-immunology",
              "international-journal-of-molecular-sciences"]
    flat = ["nature", "science", "lancet", "nejm"]
    for k, s in enumerate(lifted):
        rate_panel(fig.add_subplot(gs[1 + k // 4, k % 4]), series(s), s, ("C  " if k == 0 else "") + SHORT[s],
                   legend=k == 0)
    fig.legends[0].set_bbox_to_anchor((0.5, 0.925))
    save(fig, "alt2_review_lift")
    rate_rows("alt2c_rates", lifted + flat)

    fig, axes = plt.subplots(1, 4, figsize=(7.2, 1.9))
    for k, s in enumerate(flat):
        rate_panel(axes[k], series(s), s, ("D  " if k == 0 else "") + SHORT[s], legend=k == 0)
    fig.suptitle("Flagships where reviews add little, or lower the rate (NEJM)", x=0.06, ha="left", fontsize=8.5, y=1.2)
    fig.subplots_adjust(wspace=0.4)
    save(fig, "alt2d_little_lift")


# ---------------------------------------------------------------- alt 3/4: flagship vs open-access sibling
PAIRS = [("cell", "cell-reports"), ("circulation", "jaha"), ("jama", "jama-network-open"), ("lancet", "eclinicalmedicine"),
         ("nature", "nature-communications"), ("nature", "scientific-reports"), ("science", "science-advances"),
         ("cell", "iscience")]


def alt3():
    print("alt3/4: flagship vs open-access sibling")
    for part, pairs in [("a", PAIRS[:4]), ("b", PAIRS[4:])]:
        fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.9))
        for c, (f, o) in enumerate(pairs):
            sf, so = series(f), series(o)
            top = np.nanmax(sf["all"]) * 1.08
            rate_panel(axes[0, c], sf, f, SHORT[f], legend=c == 0, ylim=top)
            rate_panel(axes[1, c], so, o, SHORT[o])
        axes[0, 0].set_ylabel("24-month rate (flagship)")
        axes[1, 0].set_ylabel("Open-access sibling")
        fig.subplots_adjust(hspace=0.5, wspace=0.35)
        save(fig, f"alt3{part}_flagship_vs_open_access")

        fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.9))
        rows = []
        for c, (f, o) in enumerate(pairs):
            rows += volume_panel(axes[0, c], series(f), SHORT[f], legend=c == 0)
            rows += volume_panel(axes[1, c], series(o), SHORT[o])
        axes[0, 0].set_ylabel("Papers per year")
        axes[1, 0].set_ylabel("Papers per year")
        fig.subplots_adjust(hspace=0.5, wspace=0.45)
        save(fig, f"alt4{part}_volume_flagship_vs_open_access")
        write_csv(f"alt4{part}_volume", ["journal", "year", "research", "reviews"], rows)
    rate_rows("alt3_rates", sorted({s for p in PAIRS for s in p}))


# ---------------------------------------------------------------- alt 5: named recurring papers
# Per journal: what is removed, and title patterns (SQL LIKE) that find it. Named by hand
# because edition titles drift ("ESC/ESH" to "ESH", "AGS Beers Criteria®").
FLAGGED = [
    ("autophagy", "Autophagy assay guidelines", ["Guidelines for the use and interpretation of assays for monitoring autophagy%"]),
    ("circulation", "Statistics, ACC/AHA guidelines", ["%Heart Disease and Stroke Statistics%", "%ACC/AHA%Guideline%", "%AHA/ACC%Guideline%"]),
    ("ca-a-cancer-journal-for-clinicians", "Cancer statistics", ["%cancer statistics%", "%GLOBOCAN%"]),
    ("diabetes-care", "Standards of Care in Diabetes", ["%Standards of%Care in Diabetes%"]),
    ("journal-of-the-american-college-of-cardiology", "ACC/AHA guidelines", ["%ACC/AHA%Guideline%", "%AHA/ACC%Guideline%"]),
    ("european-heart-journal", "ESC guidelines", ["%ESC Guidelines%", "%ESC/%Guidelines%"]),
    ("alzheimer-s-dementia-the-journal-of-the-alzheimer-s-association", "Facts and Figures", ["%facts and figures%"]),
    ("journal-of-hypertension", "ESH guidelines", ["%ESH Guidelines%", "%ESH/%Guidelines%", "%ESC/ESH Guidelines%"]),
    ("international-journal-of-surgery-london-england", "SCARE, PROCESS, STROCSS", ["%SCARE%", "%PROCESS%guideline%", "%STROCSS%"]),
    ("journal-of-the-american-geriatrics-society", "Beers Criteria", ["%Beers Criteria%"]),
    ("cell", "\"Hallmarks of ...\" reviews", ["Hallmarks of%"]),
    ("lancet", "Global Burden of Disease", ["%Global Burden of Disease%", "%GBD 20%"]),
]


def alt5():
    print("alt5: rates with and without named recurring papers")
    row = np.full(pmid.max() + 1, -1, np.int64)
    row[pmid] = np.arange(len(pmid))
    fig, axes = plt.subplots(3, 4, figsize=(7.2, 6.2))
    rows, found = [], []
    for k, (s, label, pats) in enumerate(FLAGGED):
        j = slug2id[s]
        hits = set()
        for pat in pats:
            hits |= {r for r, in con.execute("SELECT pmid FROM papers WHERE journal_id = ? AND title LIKE ? AND doc_class IN "
                                            "('research','review','case_report','guideline')", (j, pat))}
        found += [[SHORT[s], p, _title(p)] for p in sorted(hits)]
        special = np.zeros(len(pmid), bool)
        special[row[list(hits)]] = True
        ax = axes.flat[k]
        yrs, full, wo, share = [], [], [], []
        for Y in range(2007, 2026):
            idx = np.flatnonzero((jid == j) & (dc <= 3) & ((py == Y - 1) | (py == Y - 2)))
            if len(idx) < 20:
                continue
            c = C[idx, Y - Y0].astype(np.int64)
            sp = special[idx]
            if c.sum() == 0:
                continue
            yrs.append(Y); full.append(c.sum() / len(c)); wo.append(c[~sp].sum() / (~sp).sum())
            share.append(c[sp].sum() / c.sum())
            rows.append([SHORT[s], Y, len(c), int(sp.sum()), int(c.sum()), int(c[sp].sum()), round(full[-1], 3), round(wo[-1], 3)])
        ax.fill_between(yrs, wo, full, color=BLUE, alpha=0.15, linewidth=0)
        ax.plot(yrs, full, color=BLUE, linewidth=1.5, label="All citable items")
        ax.plot(yrs, wo, color=VERMILION, linewidth=1.5, label="Without the named papers")
        ax.set_title(SHORT[s], loc="left", fontsize=8.5, pad=19)
        ax.text(0.0, 1.02, f"{label}\nup to {max(share):.0%} of citations", transform=ax.transAxes, fontsize=5.8, color=MUTED,
                va="bottom")
        ax.set_ylim(0, max(full) * 1.12)
        ax.set_xticks([2010, 2015, 2020, 2025])
        ax.tick_params(labelsize=6.5)
        if k == 0:
            ax.legend(fontsize=5.8, loc="lower right", handlelength=1.1)
            ax.set_ylabel("JIF-style rate")
    fig.subplots_adjust(hspace=0.75, wspace=0.35)
    save(fig, "alt5_named_recurring_papers")
    write_csv("alt5_rates", ["journal", "citation_year", "citable_items", "named_items", "citations",
                             "citations_to_named", "rate", "rate_without"], rows)
    write_csv("alt5_named_papers", ["journal", "pmid", "title"], found)


# ---------------------------------------------------------------- alt 6: society journal vs high-volume publisher
SOCIETY = [("journal-of-immunology-baltimore-md-1950", "frontiers-in-immunology"), ("cancer-research", "cancers"),
           ("journal-of-virology", "viruses"), ("the-journal-of-biological-chemistry", "international-journal-of-molecular-sciences"),
           ("the-journal-of-neuroscience-the-official-journal-of-the-society-for-neuroscience", "frontiers-in-neuroscience"),
           ("the-journal-of-physiology", "frontiers-in-physiology"), ("endocrinology", "frontiers-in-endocrinology"),
           ("circulation-research", "frontiers-in-cardiovascular-medicine")]


def alt6():
    print("alt6: society journal vs high-volume open-access journal")
    for part, pairs in [("a", SOCIETY[:4]), ("b", SOCIETY[4:])]:
        fig, axes = plt.subplots(4, 4, figsize=(7.2, 7.0))
        rows = []
        for c, (soc, oa) in enumerate(pairs):
            ss, so = series(soc), series(oa)
            top = max(np.nanmax(ss["all"]), np.nanmax(so["all"])) * 1.1
            rate_panel(axes[0, c], ss, soc, SHORT[soc], ylim=top)
            rate_panel(axes[1, c], so, oa, SHORT[oa], ylim=top)
            rows += volume_panel(axes[2, c], ss, SHORT[soc])
            rows += volume_panel(axes[3, c], so, SHORT[oa])
        axes[0, 0].set_ylabel("Society journal\n24-month rate")
        axes[1, 0].set_ylabel("Open-access journal\n24-month rate")
        axes[2, 0].set_ylabel("Society journal\npapers per year")
        axes[3, 0].set_ylabel("Open-access journal\npapers per year")
        h1, l1 = axes[0, 0].get_legend_handles_labels()
        h2, l2 = axes[2, 0].get_legend_handles_labels()
        fig.legend(h1 + h2, l1 + ["Research papers", "Review papers"], loc="lower center", bbox_to_anchor=(0.5, 0.97),
                   ncol=4, fontsize=7, handlelength=1.3)
        fig.subplots_adjust(hspace=0.55, wspace=0.4)
        save(fig, f"alt6{part}_society_vs_open_access")
        write_csv(f"alt6{part}_volume", ["journal", "year", "research", "reviews"], rows)
    rate_rows("alt6_rates", sorted({s for p in SOCIETY for s in p}))


# ---------------------------------------------------------------- alt 7: US vs European society journals
SOCIETY_PAIRS = [
    ("circulation", "european-heart-journal", "Cardiology flagship"),
    ("circulation-research", "cardiovascular-research", "Basic cardiovascular"),
    ("arteriosclerosis-thrombosis-and-vascular-biology", "atherosclerosis", "Vascular biology"),
    ("journal-of-clinical-oncology-official-journal-of-the-american-society-of-clinical-oncology", "annals-of-oncology", "Oncology"),
    ("gastroenterology", "gut", "Gastroenterology"),
    ("hepatology-baltimore-md", "journal-of-hepatology", "Hepatology"),
    ("diabetes-care", "diabetologia", "Diabetes"),
    ("american-journal-of-respiratory-and-critical-care-medicine", "the-european-respiratory-journal", "Respiratory"),
    ("arthritis-rheumatology-hoboken-n-j", "annals-of-the-rheumatic-diseases", "Rheumatology"),
    ("blood", "haematologica", "Hematology"),
    ("neurology", "european-journal-of-neurology", "Neurology"),
]
SHORT.update({
    "european-heart-journal": "Eur Heart J", "cardiovascular-research": "Cardiovasc Res",
    "arteriosclerosis-thrombosis-and-vascular-biology": "ATVB", "atherosclerosis": "Atherosclerosis",
    "journal-of-clinical-oncology-official-journal-of-the-american-society-of-clinical-oncology": "J Clin Oncol",
    "annals-of-oncology": "Ann Oncol", "gastroenterology": "Gastroenterology", "gut": "Gut",
    "hepatology-baltimore-md": "Hepatology", "journal-of-hepatology": "J Hepatol", "diabetologia": "Diabetologia",
    "american-journal-of-respiratory-and-critical-care-medicine": "Am J Respir Crit Care Med",
    "the-european-respiratory-journal": "Eur Respir J", "journal-of-the-american-society-of-nephrology-jasn": "J Am Soc Nephrol",
    "nephrology-dialysis-transplantation-official-publication-of-the-european-dialysis-and-transplant-association-european-renal-association": "Nephrol Dial Transplant",
    "arthritis-rheumatology-hoboken-n-j": "Arthritis Rheumatol", "annals-of-the-rheumatic-diseases": "Ann Rheum Dis",
    "blood": "Blood", "haematologica": "Haematologica", "neurology": "Neurology",
    "european-journal-of-neurology": "Eur J Neurol",
})
EUROPE = set("""Albania Andorra Austria Belarus Belgium Bosnia and Herzegovina Bulgaria Croatia Cyprus Czech Republic Denmark
Estonia Finland France Germany Greece Hungary Iceland Ireland Italy Kosovo Latvia Liechtenstein Lithuania Luxembourg Malta
Moldova Monaco Montenegro Netherlands North Macedonia Norway Poland Portugal Romania Russia San Marino Serbia Slovakia
Slovenia Spain Sweden Switzerland Ukraine United Kingdom Vatican City Czechia Macedonia""".replace("Bosnia and Herzegovina", "Bosnia_and_Herzegovina")
             .replace("Czech Republic", "Czech_Republic").replace("North Macedonia", "North_Macedonia").replace("San Marino", "San_Marino")
             .replace("United Kingdom", "United_Kingdom").replace("Vatican City", "Vatican_City").split())
EUROPE = {c.replace("_", " ") for c in EUROPE}
CHINA = {"China", "Hong Kong", "Macau", "Macao"}
ASIA = set("""Japan|South Korea|North Korea|Taiwan|India|Pakistan|Bangladesh|Sri Lanka|Nepal|Bhutan|Singapore|Malaysia|
Thailand|Vietnam|Indonesia|Philippines|Cambodia|Laos|Myanmar|Mongolia|Kazakhstan|Uzbekistan|Kyrgyzstan|Tajikistan|
Turkmenistan|Brunei|Maldives|Afghanistan""".replace("\n", "").split("|"))
REGIONS = [("USA", BLUE), ("Canada", SKY), ("Europe", ORANGE), ("China", VERMILION), ("Other Asia", GREEN), ("Rest of world", GRAY)]


def region(c):
    if c == "USA":
        return "USA"
    if c == "Canada":
        return "Canada"
    if c in EUROPE:
        return "Europe"
    if c in CHINA:
        return "China"
    if c in ASIA:
        return "Other Asia"
    return "Rest of world"


def alt7():
    print("alt7: US vs European society journals, where citations come from")
    import pickle
    g = pickle.load(open(os.path.join(ROOT, "data", "analysis", "citing_geo.pkl"), "rb"))
    J = g["journals"]

    def shares(s):
        tot = collections.Counter()
        for c, v in J[s]["countries"].items():
            tot[region(c)] += v
        n = sum(tot.values())
        return {r: tot[r] / n for r, _ in REGIONS}

    rows = []
    fig = plt.figure(figsize=(7.2, 7.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.6, 1], wspace=0.08)
    ax = fig.add_subplot(gs[0, 0])
    labels, y = [], 0
    ypos = []
    for us, eu, field in SOCIETY_PAIRS:
        for s in (us, eu):
            sh = shares(s)
            left = 0
            for r, col in REGIONS:
                ax.barh(y, sh[r], left=left, color=col, height=0.8, edgecolor="white", linewidth=0.5)
                if sh[r] >= 0.08:
                    ax.text(left + sh[r] / 2, y, f"{sh[r]:.0%}", ha="center", va="center", fontsize=5.8,
                            color="white" if col in (BLUE, VERMILION, GREEN, GRAY) else INK)
                left += sh[r]
            labels.append(SHORT[s]); ypos.append(y)
            rows.append([field, SHORT[s], J[s]["items"], J[s]["citations"], J[s]["located"]] + [round(sh[r], 4) for r, _ in REGIONS])
            y -= 1
        y -= 0.6
    ax.set_yticks(ypos, labels, fontsize=6.5)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel(f"Share of {g['year']} citations to {g['year'] - 2}–{g['year'] - 1} items, by citing authors' country")
    ax.set_title("A  Where citations come from (US journal above, European below)", loc="left",
                 fontsize=8.5, pad=22)
    handles = [matplotlib.patches.Patch(color=c, label=r) for r, c in REGIONS]
    ax.legend(handles=handles, ncol=6, fontsize=6.2, loc="lower left", bbox_to_anchor=(0, 1.0), handlelength=1,
              columnspacing=0.8, borderaxespad=0.2)
    write_csv("alt7a_citing_regions", ["field", "journal", "items", "citations", "citations_located"] + [r for r, _ in REGIONS], rows)

    # B: 24-month rate at the settled month, each pair
    ax = fig.add_subplot(gs[0, 1])
    rrows = []
    for yy, (us, eu, field) in zip(ypos[::2], SOCIETY_PAIRS):
        a, b = series(us)["all"][-1], series(eu)["all"][-1]
        ax.barh(yy, a, color=BLUE, height=0.8)
        ax.barh(yy - 1, b, color=ORANGE, height=0.8)
        for v, yv in ((a, yy), (b, yy - 1)):
            ax.text(v + 0.3, yv, f"{v:.1f}", va="center", fontsize=6.2)
        rrows.append([field, SHORT[us], round(a, 3), SHORT[eu], round(b, 3)])
    ax.set_yticks([])
    ax.set_ylim(*fig.axes[0].get_ylim())
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel(f"24-month rate, {SETTLED}")
    ax.set_title("B  Citation rate", loc="left", fontsize=8.5, pad=22)
    write_csv("alt7b_rates", ["field", "us_journal", "us_rate", "eu_journal", "eu_rate"], rrows)
    save(fig, "alt7_us_vs_european_society_journals")


if __name__ == "__main__":
    want = set(sys.argv[1:]) or {"1", "2", "3", "5", "6", "7"}
    for k in sorted(want):
        {"1": alt1, "2": alt2, "3": alt3, "5": alt5, "6": alt6, "7": alt7}[k]()
