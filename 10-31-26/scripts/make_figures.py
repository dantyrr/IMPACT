"""
Figures for the JIF paper (10-31-26). Reads the per-paper citation matrix built by
build_matrix.py (data/analysis/cites.npz) and author counts from author_counts.py
(data/analysis/author_counts.npz); writes PNG (300 dpi) + PDF figures and a CSV of
every plotted value into 10-31-26/.

JIF-style window throughout: citation year Y, citable items (research, review,
case report, guideline) published in Y-1 and Y-2. Citations are those between
PubMed-indexed papers (iCite).

Usage:
    python 10-31-26/scripts/make_figures.py            # all figures
    python 10-31-26/scripts/make_figures.py 1 3        # only figures 1 and 3
"""

import collections
import csv
import os
import re
import sqlite3
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
OUT = os.path.join(ROOT, "10-31-26")
DATA = os.path.join(ROOT, "data", "analysis")
Y0 = 2003                       # first column of the citation matrix
YEAR = 2024                     # headline JIF-style year (citations in 2024)
TREND = range(2007, 2026)

# Okabe-Ito, fixed order; gray for context
BLUE, VERMILION, GREEN, PURPLE = "#0072B2", "#D55E00", "#009E73", "#CC79A7"
GRAY, INK, MUTED = "#8C8C8C", "#222222", "#666666"

plt.rcParams.update({
    "font.family": "Arial", "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.5,
    "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK,
    "ytick.labelcolor": INK, "legend.frameon": False, "lines.linewidth": 2, "savefig.dpi": 300,
    "pdf.fonttype": 42,
})

D = np.load(os.path.join(DATA, "cites.npz"))
pmid, jid, py, pm, dc, C = D["pmid"], D["journal_id"], D["pub_year"], D["pub_month"], D["doc_class"], D["counts"]
citable = dc <= 3
con = sqlite3.connect(f"file:{os.path.join(ROOT, 'data', 'impact.db')}?mode=ro", uri=True)
jname = dict(con.execute("SELECT id, name FROM journals"))
slug2id = dict(con.execute("SELECT slug, id FROM journals"))

SHORT = {"autophagy": "Autophagy", "circulation": "Circulation", "ca-a-cancer-journal-for-clinicians": "CA Cancer J Clin",
         "cell": "Cell", "nature": "Nature", "science": "Science", "nejm": "NEJM", "lancet": "Lancet",
         "european-heart-journal": "Eur Heart J", "nature-communications": "Nat Commun", "plos-one": "PLOS ONE",
         "arteriosclerosis-thrombosis-and-vascular-biology": "ATVB", "frontiers-in-immunology": "Front Immunol",
         "diabetes-care": "Diabetes Care", "journal-of-the-american-college-of-cardiology": "JACC",
         "nucleic-acids-research": "Nucleic Acids Res"}


def title(p):
    return con.execute("SELECT title FROM papers WHERE pmid = ?", (int(p),)).fetchone()[0]


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".png"), bbox_inches="tight")
    fig.savefig(os.path.join(OUT, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)


def write_csv(name, header, rows):
    with open(os.path.join(OUT, "data", name + ".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def window(Y, mask=None):
    """Indices of citable items published Y-1, Y-2 and their citations in year Y."""
    m = citable & ((py == Y - 1) | (py == Y - 2))
    if mask is not None:
        m &= mask
    idx = np.flatnonzero(m)
    return idx, C[idx, Y - Y0].astype(np.int64)


def concentration(Y, min_items=50, min_cites=100):
    """Per journal: items, citations, rate, top-paper share, top-5 share, rate without top paper."""
    idx, c = window(Y)
    j = jid[idx]
    o = np.lexsort((-c, j))
    j, c, idx = j[o], c[o], idx[o]
    starts = np.flatnonzero(np.r_[True, j[1:] != j[:-1]])
    ends = np.r_[starts[1:], len(j)]
    out = {}
    for s, e in zip(starts, ends):
        n, tot = e - s, c[s:e].sum()
        if n < min_items or tot < min_cites:
            continue
        out[int(j[s])] = dict(items=n, cites=int(tot), rate=tot / n, top1=c[s] / tot, top5=c[s:s + 5].sum() / tot,
                              rate_wo=(tot - c[s]) / (n - 1), top_pmid=int(pmid[idx[s]]), top_cites=int(c[s]))
    return out


# ---------------------------------------------------------------- Figure 1
def fig1():
    print("Figure 1: how much a journal's rate rests on its top paper")
    r = concentration(YEAR)
    ids = list(r)
    share = np.array([r[k]["top1"] for k in ids])
    write_csv("fig1a_top_paper_share_2024", ["journal", "citable_items", "citations_2024", "rate", "top_paper_share",
                                             "top5_share", "rate_without_top_paper", "top_pmid", "top_paper_citations"],
              [[jname[k], r[k]["items"], r[k]["cites"], round(r[k]["rate"], 3), round(r[k]["top1"], 4),
                round(r[k]["top5"], 4), round(r[k]["rate_wo"], 3), r[k]["top_pmid"], r[k]["top_cites"]] for k in ids])

    fig = plt.figure(figsize=(7.2, 8.6))
    gs = fig.add_gridspec(3, 6, height_ratios=[1.15, 0.85, 1.0], hspace=0.62, wspace=1.1)

    # A: distribution, log x, labeled journals
    ax = fig.add_subplot(gs[0, :4])
    bins = np.logspace(-3.3, 0, 45)
    ax.hist(share, bins=bins, color=GRAY, edgecolor="white", linewidth=0.5)
    ax.set_xscale("log")
    ax.set_xlabel("Share of a journal's 2024 citations from its single top paper")
    ax.set_ylabel("Journals")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0%}" if v >= 0.01 else f"{v:.1%}"))
    marks = ["nature-communications", "nature", "nejm", "cell", "autophagy", "circulation", "ca-a-cancer-journal-for-clinicians"]
    top = ax.get_ylim()[1]
    pts = sorted((r[slug2id[s]]["top1"], s) for s in marks if slug2id.get(s) in r)
    for i, (x, s) in enumerate(pts):
        y = top * (1.04 + 0.1 * i)
        ax.plot([x, x], [0, y], color=BLUE, linewidth=0.8)
        ax.plot(x, y, "o", color=BLUE, markersize=4, markeredgecolor="white", markeredgewidth=0.6)
        ax.text(x, y * 1.03, f"{SHORT[s]} {x:.1%}", ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.set_ylim(0, top * 1.8)
    ax.set_yticks([t for t in ax.get_yticks() if t <= top])
    med = np.median(share)
    ax.set_title(f"A  {len(share):,} journals, citations in {YEAR} to {YEAR - 2}–{YEAR - 1} items", loc="left")
    ax.text(0.02, 0.98, f"median {med:.1%}\n{(share >= .25).sum()} journals ≥25%\n{(share >= .5).sum()} journals ≥50%",
            transform=ax.transAxes, fontsize=7, color=INK, va="top")

    # B: trend of median and 90th percentile
    ax = fig.add_subplot(gs[0, 4:])
    rows = []
    for Y in TREND:
        a = np.array([v["top1"] for v in concentration(Y).values()])
        rows.append([Y, len(a), np.median(a), np.percentile(a, 90), np.percentile(a, 99)])
    write_csv("fig1b_top_paper_share_trend", ["citation_year", "journals", "median", "p90", "p99"],
              [[a, b, round(c, 4), round(d, 4), round(e, 4)] for a, b, c, d, e in rows])
    yrs = [x[0] for x in rows]
    for col, lab, color in [(3, "90th percentile", VERMILION), (2, "Median", BLUE)]:
        vals = [x[col] for x in rows]
        ax.plot(yrs, vals, color=color)
        ax.text(yrs[-1] + 0.3, vals[-1], lab, color=INK, fontsize=7, va="center")
    ax.set_ylim(0, None)
    ax.set_xlim(yrs[0], yrs[-1] + 7)
    ax.set_xticks([2010, 2015, 2020, 2025])
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_ylabel("Top paper's share of citations")
    ax.set_xlabel("Citation year (JIF-style window)")
    ax.set_title("B  Over time", loc="left")

    # C: small multiples, rate with and without top paper
    ser_rows = []
    for k, s in enumerate(["autophagy", "circulation", "ca-a-cancer-journal-for-clinicians"]):
        ax = fig.add_subplot(gs[1, 2 * k:2 * k + 2])
        j = slug2id[s]
        full, wo, years = [], [], []
        for Y in TREND:
            idx, c = window(Y, jid == j)
            if not len(c) or c.sum() == 0:
                continue
            t = np.argmax(c)
            full.append(c.sum() / len(c)); wo.append((c.sum() - c[t]) / (len(c) - 1)); years.append(Y)
            ser_rows.append([SHORT[s], Y, len(c), int(c.sum()), round(full[-1], 3), round(wo[-1], 3), int(pmid[idx[t]]), title(pmid[idx[t]])])
        ax.fill_between(years, wo, full, color=BLUE, alpha=0.15, linewidth=0)
        ax.plot(years, full, color=BLUE, linewidth=1.5, label="All citable items")
        ax.plot(years, wo, color=VERMILION, linewidth=1.5, label="Without the top paper")
        ax.set_title(("C  " if k == 0 else "") + SHORT[s], loc="left")
        ax.set_ylim(0, None)
        ax.set_xticks([2010, 2020])
        ax.tick_params(labelsize=7)
        if k == 0:
            ax.set_ylabel("JIF-style rate")
            ax.legend(fontsize=6.5, loc="upper left", handlelength=1.2)
    write_csv("fig1c_rate_with_without_top_paper", ["journal", "citation_year", "citable_items", "citations", "rate",
                                                   "rate_without_top_paper", "top_pmid", "top_title"], ser_rows)

    # D: most concentrated large journals
    ax = fig.add_subplot(gs[2, 1:])
    big = sorted(((v["top1"], k) for k, v in r.items() if v["items"] >= 500), reverse=True)[:8]
    labels, vals, rows = [], [], []
    for sh, k in big:
        t = title(r[k]["top_pmid"])
        labels.append(f"{jname[k][:40]}\n{t[:62]}{'…' if len(t) > 62 else ''}")
        vals.append(sh)
        rows.append([jname[k], r[k]["items"], round(r[k]["rate"], 3), round(r[k]["rate_wo"], 3), round(sh, 4), r[k]["top_pmid"], t])
    write_csv("fig1d_most_concentrated_journals_2024", ["journal", "citable_items", "rate", "rate_without_top_paper",
                                                        "top_paper_share", "top_pmid", "top_title"], rows)
    yy = np.arange(len(vals))[::-1]
    ax.barh(yy, vals, color=BLUE, height=0.65)
    ax.set_yticks(yy, labels, fontsize=6.3)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    for y, v in zip(yy, vals):
        ax.text(v + 0.005, y, f"{v:.0%}", va="center", fontsize=6.5, color=INK)
    ax.set_xlabel("Top paper's share of 2024 citations")
    ax.grid(axis="y", visible=False)
    ax.set_title("D  Most dependent on one paper, among journals with ≥500 citable items (2024)", loc="left", x=-0.75)
    save(fig, "fig1_top_paper_dependence")


# ---------------------------------------------------------------- Figure 2
DROP = r"\b(update|updated|edition|revised|revision|version|part|report|annual|year|th|st|nd|rd|i{1,3}|iv|v|vi{0,3}|ix|x)\b"


def norm_title(t):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", t.lower())
    t = re.sub(r"[^a-z ]", " ", re.sub(r"\d+", " ", t))
    return " ".join(re.sub(DROP, " ", t).split())


def series_membership():
    """Series id per paper (-1 = none): citable items whose normalized title repeats in 3+ years of one journal
    (5+ years for titles of two or three words, such as "Cancer statistics, 2024")."""
    path = os.path.join(DATA, "series_v2.npz")
    if os.path.exists(path):
        z = np.load(path, allow_pickle=True)
        return z["sid"], list(z["keys"])
    row = np.full(pmid.max() + 1, -1, np.int64)
    row[pmid] = np.arange(len(pmid))
    groups = collections.defaultdict(list)
    cur = con.execute("SELECT pmid, journal_id, pub_year, title FROM papers "
                      "WHERE doc_class IN ('research','review','case_report','guideline')")
    while rows := cur.fetchmany(1_000_000):
        for p, j, y, t in rows:
            k = norm_title(t or "")
            if len(k.split()) >= 2:
                groups[(j, k)].append((y, p))
    sid = np.full(len(pmid), -1, np.int32)
    keys = []
    for (j, k), v in groups.items():
        if len({y for y, _ in v}) >= (3 if len(k.split()) >= 4 else 5):
            sid[row[[p for _, p in v]]] = len(keys)
            keys.append((j, k))
    np.savez(path, sid=sid, keys=np.array(keys, dtype=object))
    return sid, keys


SERIES_GROUPS = [   # (journal slug, phrase in the normalized title, display title)
    ("ca-a-cancer-journal-for-clinicians", "global cancer statistics", "Global Cancer Statistics (GLOBOCAN)"),
    ("ca-a-cancer-journal-for-clinicians", "cancer treatment and survivorship", "Cancer Treatment and Survivorship Statistics"),
    ("ca-a-cancer-journal-for-clinicians", "colorectal cancer statistics", "Colorectal Cancer Statistics"),
    ("ca-a-cancer-journal-for-clinicians", "breast cancer statistics", "Breast Cancer Statistics"),
    ("ca-a-cancer-journal-for-clinicians", "cancer statistics", "Cancer Statistics (annual, US)"),
    ("circulation", "heart disease and stroke statistics", "Heart Disease and Stroke Statistics"),
    ("diabetes-care", "standards of medical care in diabetes", "Standards of Medical Care in Diabetes"),
    ("diabetes-care", "standards of care in diabetes", "Standards of Medical Care in Diabetes"),
    ("neuro-oncology", "cbtrus statistical", "CBTRUS Statistical Report (brain tumors)"),
]


def series_title(j, key):
    """Readable title of a series: its newest item's title without years, editions and trailing punctuation."""
    t = con.execute("SELECT title FROM papers WHERE journal_id = ? ORDER BY pub_year DESC", (j,)).fetchall()
    for (ti,) in t:
        if norm_title(ti or "") == key:
            ti = re.sub(r"\b(19|20)\d\d(\s*[-–]\s*(19|20)?\d\d)?\b|\b\d+(st|nd|rd|th)?\s+(edition|update)\b|\bupdate\b", " ", ti)
            ti = re.sub(r"\s*[:,.;]\s*(?=[:,.;]|$)", "", " ".join(ti.split())).strip(" :,.;-–")
            ti = re.sub(r"(\s+(in|for|of|the|and|to))+$", "", ti, flags=re.I).strip(" :,.;-–")
            return ti if len(ti) <= 60 else ti[:57].rsplit(" ", 1)[0] + "…"
    return key


def fig2():
    print("Figure 2: recurring series")
    sid, keys = series_membership()
    tot = C.sum(axis=1).astype(np.int64)
    in_s = sid >= 0
    per = np.bincount(sid[in_s], weights=tot[in_s], minlength=len(keys))
    n_items = np.bincount(sid[in_s], minlength=len(keys))
    yr_min = np.full(len(keys), 9999); yr_max = np.zeros(len(keys), int)
    np.minimum.at(yr_min, sid[in_s], py[in_s]); np.maximum.at(yr_max, sid[in_s], py[in_s])
    order = np.argsort(-per)
    write_csv("fig2a_recurring_series", ["journal", "series_title_normalized", "items", "first_year", "last_year", "lifetime_citations"],
              [[jname[keys[i][0]], keys[i][1], int(n_items[i]), int(yr_min[i]), int(yr_max[i]), int(per[i])] for i in order])

    # One bar per report: title variants of the same series are merged, labels use the real title
    groups = collections.defaultdict(list)
    for i in range(len(keys)):
        j, t = keys[i]
        label = next((lab for slug, sub, lab in SERIES_GROUPS if slug2id.get(slug) == j and sub in t), None)
        groups[(j, label or t)].append(i)
    gl = list(groups)
    g_per = np.array([per[groups[g]].sum() for g in gl])
    g_items = np.array([n_items[groups[g]].sum() for g in gl])
    g_min = np.array([yr_min[groups[g]].min() for g in gl]); g_max = np.array([yr_max[groups[g]].max() for g in gl])
    k = 15
    sel = np.argsort(-g_per)[:k]
    abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
    labels = [g[1] if any(g[1] == lab for *_, lab in SERIES_GROUPS) else series_title(g[0], keys[groups[g][0]][1])
              for g in (gl[i] for i in sel)]
    write_csv("fig2a_recurring_series_merged", ["series", "journal", "items", "first_year", "last_year", "lifetime_citations"],
              [[lab, abbr[gl[i][0]], int(g_items[i]), int(g_min[i]), int(g_max[i]), int(g_per[i])] for lab, i in zip(labels, sel)])

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.8), gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.3})
    ax = axes[0]
    yy = np.arange(k)[::-1]
    ax.barh(yy, g_per[sel] / 1000, color=BLUE, height=0.65)
    ax.set_yticks(yy, labels, fontsize=6)
    for y, i in zip(yy, sel):
        ax.text(g_per[i] / 1000 + 3, y, f"{abbr[gl[i][0]]} · {g_items[i]} items, {g_min[i]}–{g_max[i]}",
                va="center", fontsize=5.8, color=MUTED)
    ax.set_xlabel("Lifetime citations (thousands)")
    ax.set_xlim(0, g_per[sel].max() / 1000 * 1.55)
    ax.grid(axis="y", visible=False)
    ax.set_title("A  Most-cited recurring series", loc="left")

    ax = axes[1]
    rows = []
    for s, color in [("circulation", BLUE), ("diabetes-care", VERMILION), ("european-heart-journal", GREEN)]:
        j = slug2id[s]
        xs, ys = [], []
        for Y in TREND:
            idx, c = window(Y, jid == j)
            if c.sum() == 0:
                continue
            v = c[in_s[idx]].sum() / c.sum()
            xs.append(Y); ys.append(v); rows.append([SHORT[s], Y, int(c.sum()), int(c[in_s[idx]].sum()), round(v, 4)])
        ax.plot(xs, ys, color=color)
        ax.text(xs[-1] + 0.3, ys[-1], SHORT[s], fontsize=7, color=INK, va="center")
    write_csv("fig2b_series_share_by_year", ["journal", "citation_year", "citations", "citations_to_series_items", "share"], rows)
    ax.set_xlim(TREND[0], TREND[-1] + 6)
    ax.set_xticks([2010, 2015, 2020, 2025])
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_ylabel("Share of JIF-style citations")
    ax.set_xlabel("Citation year")
    ax.set_title("B  Citations to recurring series", loc="left")
    save(fig, "fig2_recurring_series")


# ---------------------------------------------------------------- Figure 3
def fig3():
    print("Figure 3: publication month")
    MONTHS = [m for m in range(1, 13) if m != 6]   # June holds papers with no month (parser default)
    NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    m = (dc == 0) & (py >= 2010) & (py <= 2022)
    idx = np.flatnonzero(m)
    counted = C[idx, py[idx] - Y0 + 1].astype(np.int64) + C[idx, py[idx] - Y0 + 2]
    later = C[idx, py[idx] - Y0 + 3].astype(np.float64)
    mo = pm[idx]
    rows, mc, ml, ec, el = [], [], [], [], []
    for k in MONTHS:
        s = mo == k
        a, b = counted[s], later[s]
        mc.append(a.mean()); ml.append(b.mean())
        ec.append(1.96 * a.std() / np.sqrt(len(a))); el.append(1.96 * b.std() / np.sqrt(len(b)))
        rows.append([NAMES[k - 1], int(s.sum()), round(a.mean(), 3), round(ec[-1], 3), round(b.mean(), 3), round(el[-1], 3)])
    write_csv("fig3a_citations_by_publication_month", ["month", "research_articles", "mean_citations_jif_years_P1_P2",
                                                       "ci95", "mean_citations_year_P3", "ci95_P3"], rows)
    cm = citable & (py >= 2010) & (py <= 2022)
    rev = [[NAMES[k - 1], int((cm & (pm == k)).sum()), round(float(np.mean(dc[cm & (pm == k)] == 1)), 4)] for k in MONTHS]
    write_csv("fig3b_review_share_by_month", ["month", "citable_items", "review_share"], rev)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"width_ratios": [1.6, 1], "wspace": 0.28})
    ax = axes[0]
    x = np.array(MONTHS)
    ax.errorbar(x, mc, yerr=ec, color=BLUE, marker="o", markersize=4, capsize=0, linewidth=2)
    ax.errorbar(x, ml, yerr=el, color=VERMILION, marker="o", markersize=4, capsize=0, linewidth=2)
    ax.text(1, mc[0] + 0.45, "Citations in the 2 years a JIF counts", fontsize=7, color=INK)
    ax.text(1, ml[0] + 0.45, "Citations in the 3rd year (not counted)", fontsize=7, color=INK)
    ax.text(12.2, mc[-1], f"−{1 - mc[-1] / mc[0]:.0%}\nvs Jan", fontsize=7, color=INK, va="center")
    ax.text(12.2, ml[-1], f"−{1 - ml[-1] / ml[0]:.0%}", fontsize=7, color=INK, va="center")
    ax.set_xticks(range(1, 13), [n[0] for n in NAMES])
    ax.set_xlim(0.5, 13.3)
    ax.set_ylim(0, mc[0] + 1.2)
    ax.set_ylim(0, None)
    ax.set_ylabel("Mean citations per research article")
    ax.set_xlabel("Publication month (June omitted: it also holds papers with no month)")
    ax.set_title(f"A  Research articles, 2010–2022 (n = {len(idx) - int((mo == 6).sum()) - int((mo == 0).sum()):,})", loc="left")

    ax = axes[1]
    ax.plot(x, [v[2] for v in rev], color=BLUE, marker="o", markersize=4)
    ax.set_xticks(range(1, 13), [n[0] for n in NAMES])
    ax.set_ylim(0, 0.2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_ylabel("Reviews among citable items")
    ax.set_xlabel("Publication month")
    ax.set_title("B  Review share by month", loc="left")
    save(fig, "fig3_publication_month")


# ---------------------------------------------------------------- Figure 4
def fig4():
    print("Figure 4: author counts")
    A = np.load(os.path.join(DATA, "author_counts.npz"))
    amap = np.zeros(pmid.max() + 1, np.int32)
    ok = A["pmid"] <= pmid.max()
    amap[A["pmid"][ok]] = A["n"][ok]
    n = amap[pmid]
    tot = C.sum(axis=1).astype(np.int64)
    phys = np.array([any(w in jname.get(j, "").lower() for w in ("physic", "phys.", "high energy", "nuclear", "astro"))
                     for j in range(jid.max() + 1)])
    bio = citable & ~phys[jid]
    buckets = [(1, 10), (11, 50), (51, 100), (101, 500), (501, 1000), (1001, 10 ** 6)]
    names = ["1–10", "11–50", "51–100", "101–500", "501–1,000", ">1,000"]
    rows, sp, sc, sa = [], [], [], []
    for (lo, hi), nm in zip(buckets, names):
        s = bio & (n >= lo) & (n <= hi)
        sp.append(s.sum() / bio.sum()); sc.append(tot[s].sum() / tot[bio].sum())
        sa.append((tot[s] * n[s]).sum() / (tot[bio] * n[bio]).sum())
        rows.append([nm, int(s.sum()), round(float(tot[s].mean()), 2), sp[-1], sc[-1], sa[-1]])
    write_csv("fig4a_author_count_buckets", ["authors", "papers", "mean_citations", "share_of_papers",
                                             "share_of_citations", "share_of_author_credited_citations"], rows)

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 3.0), gridspec_kw={"width_ratios": [1.7, 1, 1], "wspace": 0.5})
    ax = axes[0]
    x = np.arange(len(names))
    w = 0.26
    for off, vals, color, lab in [(-w, sp, GRAY, "Papers"), (0, sc, BLUE, "Citations"), (w, sa, VERMILION, "Author-credited citations")]:
        ax.bar(x + off, vals, w * 0.9, color=color, label=lab)
    ax.set_yscale("log")
    ax.set_ylim(1e-7, 1.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:g}%"))
    ax.set_xticks(x, names, fontsize=6.5, rotation=35, ha="right")
    ax.set_xlabel("Authors per paper")
    ax.set_ylabel("Share of total (log scale)")
    ax.legend(fontsize=6.5, loc="upper left", bbox_to_anchor=(0, 1.0), ncol=3, columnspacing=0.8, handlelength=1)
    ticks = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1]
    ax.set_yticks(ticks, ["0.0001%", "0.001%", "0.01%", "0.1%", "1%", "10%", "100%"])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_ylim(3e-7, 12)
    ax.set_title("A  Biomedical citable items, 2003–2026", loc="left")

    ax = axes[1]
    yrs = list(range(2005, 2026))
    v = [float(np.mean(n[bio & (py == y)] >= 100)) * 1e4 for y in yrs]
    ax.plot(yrs, v, color=BLUE)
    write_csv("fig4b_papers_100plus_authors_by_year", ["year", "per_10000_papers"], [[y, round(a, 3)] for y, a in zip(yrs, v)])
    ax.set_ylim(0, None)
    ax.set_ylabel("Papers with ≥100 authors\nper 10,000")
    ax.set_xlabel("Publication year")
    ax.set_title("B  Large author lists", loc="left")

    ax = axes[2]
    eds = [(18188003, "2008"), (22966490, "2012"), (26799652, "2016"), (33634751, "2021")]
    auth = [int(amap[p]) for p, _ in eds]
    ax.bar(range(4), auth, color=BLUE, width=0.6)
    for i, a in enumerate(auth):
        ax.text(i, a + 50, f"{a:,}", ha="center", fontsize=6.5, color=INK)
    ax.set_xticks(range(4), [e[1] for e in eds])
    ax.set_ylabel("Authors")
    ax.set_title("C  Autophagy Guidelines editions", loc="left")
    ax.grid(axis="x", visible=False)
    write_csv("fig4c_autophagy_guidelines", ["pmid", "edition", "authors", "citations_in_pubmed"],
              [[p, e, int(amap[p]), int(tot[np.searchsorted(pmid, p)]) if pmid[np.searchsorted(pmid, p)] == p else ""]
               for p, e in eds])
    save(fig, "fig4_author_counts")


# ---------------------------------------------------------------- Figure 5
# Names shared by several campuses, left over when the campus was not written
SYSTEM_NAMES = {"university of california", "university of texas", "university of colorado", "university of maryland",
                "university of massachusetts", "university of wisconsin", "university of illinois",
                "university of north carolina", "university of missouri", "university of nebraska",
                "university of tennessee", "university of alabama", "state university of new york",
                "city university of new york", "university of hawaii", "university of arkansas",
                "university of south carolina", "university of louisiana"}
INST_LABEL = {"cnrs": "CNRS", "inserm": "INSERM", "harvard medical school": "Harvard Medical School",
              "massachusetts institute of technology": "MIT", "california institute of technology": "Caltech",
              "university of california san francisco": "UC San Francisco", "university of california berkeley": "UC Berkeley",
              "university of california san diego": "UC San Diego", "university of california los angeles": "UCLA",
              "howard hughes medical institute": "HHMI", "eth zurich": "ETH Zurich", "mayo clinic": "Mayo Clinic",
              "brigham and women s hospital": "Brigham and Women's Hospital", "king s college london": "King's College London",
              "university college london": "University College London", "national institutes of health": "NIH",
              "london school of hygiene and tropical medicine": "London School of Hygiene & Tropical Med",
              "university of chinese academy of sciences": "University of Chinese Academy of Sciences"}


def inst_label(k):
    if k in INST_LABEL:
        return INST_LABEL[k]
    small = {"of", "and", "for", "the", "in", "at"}
    return " ".join(w if w in small else w.capitalize() for w in k.split())


def dumbbell(ax, rows, title, n_label="Nature"):
    """rows: (label, share_all, share_journal). Gray dot = all journals, blue = this journal."""
    y = np.arange(len(rows))[::-1]
    for yy, (lab, a, b) in zip(y, rows):
        ax.plot([a, b], [yy, yy], color="#C8C8C8", linewidth=1.2, zorder=1)
        ax.text(max(a, b) * 1.08, yy, f"{b / a:.0f}×" if b / a >= 1.95 else f"{b / a:.1f}×", va="center", fontsize=6.3,
                color=INK)
    ax.scatter([r[1] for r in rows], y, s=16, color=GRAY, zorder=2, label="All journals", edgecolor="white", linewidth=0.5)
    ax.scatter([r[2] for r in rows], y, s=16, color=BLUE, zorder=3, label=n_label, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y, [r[0] for r in rows], fontsize=6.5)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=1))
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlim(0.0001, 0.25)
    ax.set_xticks([0.001, 0.01, 0.1], ["0.1%", "1%", "10%"])
    ax.grid(axis="y", visible=False)
    ax.set_title(title, loc="left", fontsize=8.5)
    ax.set_ylim(-0.7, len(rows) - 0.3)


def fig5():
    print("Figure 5: institutions in Nature and other flagship journals")
    import pickle
    d = pickle.load(open(os.path.join(DATA, "institutions.pkl"), "rb"))
    keys, A, na = d["keys"], d["all"], d["n_all"]
    ok = np.array([k not in SYSTEM_NAMES for k in keys])
    rows_csv = []
    for s in d["journals"]:
        N, nn = d["j"][s], d["n_j"][s]
        for i in np.flatnonzero(ok & (N >= 10)):
            rows_csv.append([s, keys[i], int(N[i]), nn, round(N[i] / nn, 5), int(A[i]), na, round(A[i] / na, 6),
                             round((N[i] / nn) / (A[i] / na), 2)])
    write_csv("fig5_institutions", ["journal", "institution", "papers_in_journal", "journal_papers", "share_journal",
                                    "papers_all_journals", "all_papers", "share_all", "ratio"], rows_csv)

    fig = plt.figure(figsize=(7.2, 10.5))
    gs = fig.add_gridspec(4, 2, height_ratios=[1.6, 1.6, 1, 1], hspace=0.5, wspace=1.15)
    N, nn = d["j"]["nature"], d["n_j"]["nature"]
    top = [i for i in np.argsort(-N) if ok[i]][:20]
    ax = fig.add_subplot(gs[0, 0])
    dumbbell(ax, [(inst_label(keys[i]), A[i] / na, N[i] / nn) for i in top], "A  Most frequent in Nature")
    ax.set_xlabel("Share of papers with an author there")

    big = [i for i in np.argsort(-A) if ok[i]][:20]
    ax = fig.add_subplot(gs[0, 1])
    dumbbell(ax, [(inst_label(keys[i]), A[i] / na, max(N[i], 0.5) / nn) for i in big], "B  Most frequent in all journals")
    ax.set_xlabel("Share of papers with an author there")

    sel = ok & (A >= 1000) & (N >= 20)
    rat = np.where(sel, (N / nn) / np.maximum(A / na, 1e-12), 0)
    over = [i for i in np.argsort(-rat)][:20]
    ax = fig.add_subplot(gs[1, 0])
    dumbbell(ax, [(inst_label(keys[i]), A[i] / na, N[i] / nn) for i in over],
             "C  Most over-represented in Nature\n     (≥1,000 papers overall, ≥20 in Nature)")
    ax.set_xlabel("Share of papers with an author there")

    for k, s in enumerate(["science", "cell", "nejm", "lancet"]):
        J, nj = d["j"][s], d["n_j"][s]
        t = [i for i in np.argsort(-J) if ok[i]][:20 if k == 0 else 10]
        ax = fig.add_subplot(gs[[(1, 1), (2, 0), (2, 1), (3, 0)][k]])
        name = SHORT.get(s, s)
        dumbbell(ax, [(inst_label(keys[i]), A[i] / na, J[i] / nj) for i in t], ("D  " if k == 0 else "") + name, n_label=name)
    ax = fig.add_subplot(gs[3, 1])
    ax.axis("off")
    ax.scatter([], [], s=16, color=GRAY, label="All journals")
    ax.scatter([], [], s=16, color=BLUE, label="The named journal")
    ax.legend(loc="upper left", fontsize=7, title="Share of papers with an author there", title_fontsize=7,
              alignment="left")
    ax.text(0, 0.45, f"Citable items 2021–2025.\n{na:,} papers with a parsed institution:\nNature {nn:,}, Science "
            f"{d['n_j']['science']:,}, Cell {d['n_j']['cell']:,},\nNEJM {d['n_j']['nejm']:,}, Lancet {d['n_j']['lancet']:,}."
            "\nRatio = journal share / all-journal share.", fontsize=6.5, color=MUTED, va="top", transform=ax.transAxes)
    save(fig, "fig5_institutions")


if __name__ == "__main__":
    want = set(sys.argv[1:]) or {"1", "2", "3", "4", "5"}
    for k, f in [("1", fig1), ("2", fig2), ("3", fig3), ("4", fig4), ("5", fig5)]:
        if k in want:
            f()
