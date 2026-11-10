"""New figures whose examples come from a stated ranking rule. Each writes new files and replaces no existing figure.
Rules and ranks: example_audit.md. Needs data/analysis/citing_screen_2024.npz (citing_screen.py),
citing_geo.pkl and citing_geo_tiers.pkl.

Usage: python 10-31-26/scripts/ranked_figures.py [1a 1c 2b 6a 6h 7c 9 11 12 13 14]   (from the IMPACT folder)
"""
import collections
import csv
import glob
import json
import os
import pickle
import re
import sqlite3
import matplotlib.transforms  # noqa: E402
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import (BLUE, C, DATA, GRAY, GREEN, INK, MUTED, OUT, PURPLE, ROOT, SHORT, TREND, VERMILION, Y0, citable,
                          con, concentration, jid, jname, matplotlib, np, plt, pmid, py, save, slug2id, title, window,
                          write_csv)
from type_effect import CITABLE, JSON, DASHED, in_window, load, rate, settled_month, stats_papers, without

ORANGE, SKY = "#E69F00", "#56B4E9"
DARK_ORANGE = "#B97F00"   # the Okabe-Ito orange, darkened so journal names in it stay readable
abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
by_abbr = {v: k for k, v in abbr.items()}
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)


def end_labels(ax, items, gap, x, fontsize=6.5):
    """Labels at the right edge, pushed apart so they do not collide, each with a mark in its line's color.
    items: (y, text, color)."""
    last = -1e9
    trans = matplotlib.transforms.offset_copy(ax.transData, fig=ax.figure, x=-5, y=0, units="points")
    for y, text, color in sorted(items):
        y2 = max(y, last + gap)
        last = y2
        ax.plot([x], [y2], "s", color=color, markersize=3.5, clip_on=False, transform=trans)
        ax.text(x, y2, text, fontsize=fontsize, color=INK, va="center", clip_on=False)


# ---------------------------------------------------------------- 1A: top journals marked on the distribution
def fig1a():
    r = concentration(2024)
    share = np.array([v["top1"] for v in r.values()])
    top = sorted((k for k in r if r[k]["items"] >= 500), key=lambda k: -r[k]["top1"])[:3]
    anchors = [slug2id[s] for s in ("nature", "nejm", "cell", "circulation", "ca-a-cancer-journal-for-clinicians")]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    bins = np.logspace(-3.3, 0, 45)
    ax.hist(share, bins=bins, color=GRAY, edgecolor="white", linewidth=0.5)
    ax.set_xscale("log")
    ymax = ax.get_ylim()[1]
    pts = sorted([(r[k]["top1"], k, VERMILION) for k in top] + [(r[k]["top1"], k, BLUE) for k in anchors if k in r],
                 key=lambda p: p[0])
    for i, (x, k, color) in enumerate(pts):
        y = ymax * (1.04 + 0.11 * i)
        ax.plot([x, x], [0, y], color=color, linewidth=0.8)
        ax.plot(x, y, "o", color=color, markersize=4, markeredgecolor="white", markeredgewidth=0.6)
        ax.text(x * 0.93, y, f"{abbr[k]} {x:.1%}", ha="right", va="center", fontsize=6.5, color=INK)
    ax.set_ylim(0, ymax * 2.0)
    ax.set_yticks([t for t in ax.get_yticks() if t <= ymax])
    ax.plot([], [], "o", color=VERMILION, markersize=4, label="Top 3 of journals with 500+ citable items")
    ax.plot([], [], "o", color=BLUE, markersize=4, label="Reference journals")
    ax.legend(fontsize=6.5, loc="upper left")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0%}" if v >= 0.01 else f"{v:.1%}"))
    ax.set_xlabel("Share of a journal's 2024 citations from its single top paper")
    ax.set_ylabel("Journals")
    ax.set_title(f"{len(share):,} journals, citations in 2024 to 2022–23 items", loc="left")
    save(fig, "fig1a_ranked")


# ---------------------------------------------------------------- 1C: journals most dependent on one paper for years
def fig1c():
    names = ["Mol Biol Evol", "Int J Surg", "Cancer Res Treat", "Alzheimers Dement", "CA Cancer J Clin"]
    fig, axes = plt.subplots(1, 5, figsize=(7.2, 2.3))
    rows = []
    for k, (ax, n) in enumerate(zip(axes, names)):
        j = by_abbr[n]
        full, wo, years = [], [], []
        for Y in TREND:
            if Y > 2024:
                continue
            idx, c = window(Y, jid == j)
            if not len(c) or c.sum() == 0:
                continue
            t = np.argmax(c)
            full.append(c.sum() / len(c)); wo.append((c.sum() - c[t]) / (len(c) - 1)); years.append(Y)
            rows.append([n, Y, len(c), int(c.sum()), round(full[-1], 3), round(wo[-1], 3), round(c[t] / c.sum(), 4),
                         int(pmid[idx[t]]), title(pmid[idx[t]])])
        ax.fill_between(years, wo, full, color=BLUE, alpha=0.15, linewidth=0)
        ax.plot(years, full, color=BLUE, linewidth=1.5, label="All citable items")
        ax.plot(years, wo, color=VERMILION, linewidth=1.5, label="Without the top paper")
        ax.set_title(n, loc="left", fontsize=7.5)
        ax.set_ylim(0, None)
        ax.set_xticks([2010, 2020])
        ax.tick_params(labelsize=6.5)
    axes[0].set_ylabel("JIF-style rate")
    fig.subplots_adjust(wspace=0.42)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=2)
    write_csv("fig1c_ranked", ["journal", "citation_year", "citable_items", "citations", "rate", "rate_without_top_paper",
                               "top_paper_share", "top_pmid", "top_title"], rows)
    save(fig, "fig1c_ranked")


# ---------------------------------------------------------------- 2B: journals with the largest series share
def fig2b():
    sid = np.load(os.path.join(DATA, "series_v2.npz"), allow_pickle=True)["sid"]
    in_s = sid >= 0
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    rows, ends = [], []
    for n, color in [("J Natl Compr Canc Netw", VERMILION), ("Cancer Res Treat", GREEN), ("Diabetes Care", PURPLE),
                     ("Circulation", BLUE)]:
        xs, ys = [], []
        for Y in TREND:
            if Y > 2024:
                continue
            idx, c = window(Y, jid == by_abbr[n])
            if c.sum() == 0:
                continue
            v = c[in_s[idx]].sum() / c.sum()
            xs.append(Y); ys.append(v); rows.append([n, Y, int(c.sum()), int(c[in_s[idx]].sum()), round(v, 4)])
        ax.plot(xs, ys, color=color, linewidth=1.6)
        ends.append((ys[-1], n, color))
    end_labels(ax, ends, 0.03, 2024.8)
    ax.set_xlim(TREND[0], 2024)
    ax.set_xticks([2010, 2015, 2020])
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Share of JIF-style citations")
    ax.set_xlabel("Citation year")
    ax.set_title("Citations to recurring series: top 3, and Circulation (7th)", loc="left", fontsize=8)
    write_csv("fig2b_ranked", ["journal", "citation_year", "citations", "citations_to_series_items", "share"], rows)
    save(fig, "fig2b_ranked")


# ---------------------------------------------------------------- 6A: largest journals by peak year
def fig6a():
    names = [("Sci Rep", VERMILION), ("PLoS One", BLUE), ("Cureus", GREEN), ("Heliyon", PURPLE),
             ("Int J Environ Res Public Health", SKY), ("Int J Mol Sci", ORANGE)]
    years = np.arange(2006, 2026)
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    rows, ends = [], []
    for n, color in names:
        v = np.array([(citable & (jid == by_abbr[n]) & (py == y)).sum() for y in years])
        keep = np.flatnonzero(v > 0)
        ax.plot(years[keep], v[keep] / 1000, color=color, linewidth=1.6)
        ends.append((v[-1] / 1000, f"{'IJERPH' if n.startswith('Int J Env') else n} {v[-1] / 1000:.1f}k", color))
        rows += [[n, int(y), int(c)] for y, c in zip(years, v)]
    end_labels(ax, ends, 2.1, 2025.8)
    ax.set_xlim(2006, 2025)
    ax.set_xticks(range(2006, 2026, 3))
    ax.set_ylim(0, None)
    ax.set_ylabel("Citable items per year (thousands)")
    ax.set_title("The six largest journals by peak year, preprint servers left out", loc="left", fontsize=8)
    write_csv("fig6a_ranked", ["journal", "year", "citable_items"], rows)
    save(fig, "fig6a_ranked")


# ---------------------------------------------------------------- 6H: largest journals by items x list fee
def fig6h():
    fees = [("Sci Rep", 2850, "DOAJ listing, 2025"), ("Nat Commun", 6790, "DOAJ listing, 2025"),
            ("PLoS One", 2477, "plos.org/publish/fees"), ("Int J Mol Sci", round(2900 * 1.15), "CHF 2,900, third-party listing"),
            ("Heliyon", 2100, "highest listing found: sources give $1,250-2,100"),
            ("Cureus", 300, "no APC; top of the $0-300 editing fee")]
    rows = []
    for n, fee, src in fees:
        items = int((citable & (jid == by_abbr[n]) & (py == 2024)).sum())
        rows.append([n, items, fee, items * fee / 1e6, src])
    rows.sort(key=lambda r: r[3])
    fig, ax = plt.subplots(figsize=(5.2, 2.5))
    yy = np.arange(len(rows))
    ax.barh(yy, [r[3] for r in rows], color=BLUE, height=0.65)
    ax.set_yticks(yy, [r[0] for r in rows])
    for y, r in zip(yy, rows):
        ax.text(r[3] + 1, y, f"\\${r[3]:.0f}M  ({r[1]:,} × \\${r[2]:,})", va="center", fontsize=6.3, color=INK)
    ax.set_xlim(0, max(r[3] for r in rows) * 1.45)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("2024 citable items × one list fee, \\$ millions (a ceiling)")
    ax.set_title("Six largest fee-charging journals of 2024", loc="left", fontsize=8)
    write_csv("fig6h_ranked", ["journal", "items_2024", "list_fee_usd", "ceiling_usd_millions", "fee_source"],
              [[r[0], r[1], r[2], round(r[3], 1), r[4]] for r in rows])
    save(fig, "fig6h_ranked")


# ---------------------------------------------------------------- 7C: one threshold for every publisher
def fig7c():
    R = np.load(os.path.join(DATA, "retractions.npz"))
    P = np.load(os.path.join(DATA, "publishers.npz"), allow_pickle=True)
    retr = np.isin(pmid, R["pmid"])
    m = citable & (py >= 2015) & (py <= 2023)
    rows = []
    for i, nm in enumerate(P["names"]):
        s = m & (P["code"] == i)
        if s.sum() >= 20000 and nm not in ("Other", "No DOI"):
            rows.append([str(nm), int(s.sum()), int((s & retr).sum()), (s & retr).sum() / s.sum() * 1e4])
    rows.sort(key=lambda r: r[3])
    allr = (m & retr).sum() / m.sum() * 1e4
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    yy = np.arange(len(rows))
    ax.barh(yy, [r[3] for r in rows], color=[VERMILION if r[0] == "Hindawi" else BLUE for r in rows], height=0.7)
    ax.set_yticks(yy, [r[0] for r in rows], fontsize=6.5)
    for y, r in zip(yy, rows):
        ax.text(r[3] + 6, y, f"{r[3]:.0f}", va="center", fontsize=6.3, color=INK, zorder=3,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
    ax.axvline(allr, color=INK, linewidth=0.7, linestyle="--", zorder=1)
    ax.text(70, 1.5, f"Dashed line: all journals, {allr:.0f}", fontsize=6.5, color=INK, va="center")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Retracted papers per 10,000 citable items, published 2015–23")
    ax.set_title("Every named publisher with 20,000+ citable items", loc="left", fontsize=8)
    write_csv("fig7c_ranked", ["publisher", "citable_items", "retracted", "per_10000"], [r[:3] + [round(r[3], 1)] for r in rows[::-1]])
    save(fig, "fig7c_ranked")


# ---------------------------------------------------------------- 9B-C: labels from the rankings
def fig9():
    T = list(csv.DictReader(open(os.path.join(OUT, "data", "fig9_journal_timing.csv"))))
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), gridspec_kw={"wspace": 0.3})
    ax = axes[0]
    pl = np.array([float(r["placement_gain"]) * 100 for r in T])
    bins = np.arange(-10, 8.01, 0.5)
    ax.hist(np.clip(pl, -9.99, 7.99), bins=bins, color=GRAY, edgecolor="white", linewidth=0.4)
    ax.axvline(0, color=INK, linewidth=0.8)
    big = [r for r in T if int(r["items_2014_21"]) >= 2000 and abs(float(r["placement_z"])) >= 3]
    big.sort(key=lambda r: -abs(float(r["placement_gain"])))
    pick = {r["abbreviation"]: (r, VERMILION) for r in big[:5]}
    pick.update({r["abbreviation"]: (r, BLUE) for r in T if r["abbreviation"] in ("Nature", "PLoS One")})
    place = {"J Med Virol": (760, 1), "Radiology": (620, 1), "Lancet": (480, 1), "Rev Bras Enferm": (560, 1),
             "Br J Pharmacol": (440, 1), "Nature": (1130, 1), "PLoS One": (1030, 1)}
    for n, (r, color) in pick.items():
        v = float(r["placement_gain"]) * 100
        h, side = place[n]
        ax.plot([v, v], [0, h], color=color, linewidth=0.8, zorder=3)
        ax.text(v + 0.2 * side, h, f"{n} {v:+.1f}%".replace("-", "−"), fontsize=5.8, color=INK, va="center", zorder=4,
                ha="left" if side > 0 else "right", bbox=dict(facecolor="white", edgecolor="none", pad=0.5))
    ax.set_xlim(-10, 11)
    ax.set_ylim(0, 1220)
    ax.set_xlabel("JIF change from which papers land in early months (%)")
    ax.set_ylabel("Journals")
    ax.set_title(f"A  Largest effects, 2,000+ items, |z| ≥ 3", loc="left", fontsize=8)

    ax = axes[1]
    has = [r for r in T if r["reviews_fdr_q"]]
    ro = np.array([float(r["reviews_jan_mar"]) * 100 for r in has])
    oo = np.array([float(r["other_jan_mar"]) * 100 for r in has])
    q = np.array([float(r["reviews_fdr_q"]) for r in has])
    ax.scatter(oo, ro, s=4, color=GRAY, alpha=0.35, linewidths=0)
    hi = (q < 0.05) & (ro > oo)
    ax.scatter(oo[hi], ro[hi], s=8, color=VERMILION, linewidths=0, label=f"More reviews early (FDR < 5%): {hi.sum()}")
    ax.plot([0, 100], [0, 100], color=INK, linewidth=0.7, linestyle="--")
    rank = sorted((i for i in range(len(has)) if hi[i] and int(has[i]["reviews"]) >= 100), key=lambda i: -(ro[i] - oo[i]))[:5]
    for n, i in enumerate(rank):
        ax.annotate(has[i]["abbreviation"], (oo[i], ro[i]), xytext=(44, 97 - 7 * n), fontsize=5.8, color=INK, va="center",
                    arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.4, shrinkA=0, shrinkB=1, relpos=(0, 0.5)))
    ax.set_xlim(0, 60); ax.set_ylim(0, 100)
    ax.set_xlabel("Other citable items published Jan–Mar (%)")
    ax.set_ylabel("Reviews published Jan–Mar (%)")
    ax.legend(fontsize=6, loc="upper left")
    ax.set_title("B  Largest gaps, 100+ reviews", loc="left", fontsize=8)
    write_csv("fig9bc_ranked", ["panel", "journal", "items", "value", "comparison"],
              [["A", r["abbreviation"], r["items_2014_21"], r["placement_gain"], r["placement_z"]] for r in big[:5]]
              + [["B", has[i]["abbreviation"], has[i]["reviews"], has[i]["reviews_jan_mar"], has[i]["other_jan_mar"]] for i in rank])
    save(fig, "fig9bc_ranked")


# ---------------------------------------------------------------- 11: guideline lift, ranked
def fig11():
    # Journals whose own papers mostly lack reference lists are left out (reference_coverage.py): citations from them, and
    # for non-English journals from their peers, are missing, so their rates are low estimates.
    cov = np.load(os.path.join(DATA, "reference_coverage.npz"))
    ids = {r[0]: r[1] for r in sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True).execute("SELECT slug, id FROM journals")}
    coverage = lambda slug: cov["with_refs"][ids[slug]] / max(cov["items"][ids[slug]], 1)
    G, dropped = [], 0
    for path in glob.glob(os.path.join(JSON, "*.json")):
        d = json.load(open(path))
        if not d.get("timeseries"):
            continue
        e = next(p for p in d["timeseries"] if p["month"] == settled_month(d))
        n = sum(e.get("by_type", {}).get(t, {}).get("papers", 0) for t in CITABLE)
        f, w = rate(e, CITABLE), rate(e, without("guideline"))
        if f and w is not None and n >= 300:
            slug = os.path.basename(path)[:-5]
            if coverage(slug) < 0.5:
                dropped += 1
                continue
            G.append((d["journal"], n, e["by_type"].get("guideline", {}).get("papers", 0), f, w, (w - f) / f, coverage(slug)))
    print(f"  {len(G):,} journals kept, {dropped} left out for missing reference lists")
    G.sort(key=lambda r: r[5])
    top = G[:15][::-1]
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    yy = np.arange(len(top))
    ax.barh(yy, [-r[5] for r in top], color=BLUE, height=0.7)
    ax.set_yticks(yy, [re.split(r" ?[:=;(]", r[0])[0][:38] for r in top], fontsize=6.3)
    for y, r in zip(yy, top):
        ax.text(-r[5] + 0.006, y, f"{r[3]:.1f} → {r[4]:.1f}, {r[2]} guideline{'' if r[2] == 1 else 's'}", va="center", fontsize=6, color=INK)
    ax.set_xlim(0, 0.62)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Fall in the 24-month rate without guidelines, Nov 2025")
    ax.set_title(f"Largest falls, of {len(G):,} journals with 300+ citable items and reference lists", loc="left", fontsize=8)
    write_csv("fig11_ranked_guidelines", ["journal", "citable_items", "guidelines", "rate", "rate_without_guidelines", "change", "reference_coverage"],
              [[r[0], r[1], r[2], round(r[3], 3), round(r[4], 3), round(r[5], 4), round(float(r[6]), 3)] for r in G[:50]])
    save(fig, "fig11_ranked_guidelines")


# ---------------------------------------------------------------- 12: Int J Surg guidelines and who cites them
def family(j, pats):
    out = set()
    for p in pats:
        out |= {r[0] for r in con.execute("SELECT pmid FROM papers WHERE journal_id = ? AND title LIKE ? AND doc_class IN "
                                          "('research','review','case_report','guideline')", (j, p))}
    return out


def citing_journals(pmids):
    """Citing journal counts for these papers, lifetime."""
    q = ",".join("?" * len(pmids))
    cp = [r[0] for r in con.execute(f"SELECT citing_pmid FROM citations WHERE cited_pmid IN ({q}) AND citing_class IS NULL", list(pmids))]
    n = collections.Counter()
    for i in range(0, len(cp), 900):
        ch = cp[i:i + 900]
        n.update(dict(con.execute(f"SELECT journal_id, COUNT(*) FROM papers WHERE pmid IN ({','.join('?' * len(ch))}) GROUP BY 1", ch)))
    return n


def fig12():
    ijs, cr, ams, jscr = (by_abbr[n] for n in ("Int J Surg", "Int J Surg Case Rep", "Ann Med Surg (Lond)", "J Surg Case Rep"))
    fam = family(ijs, ["%SCARE%", "%PROCESS%guideline%", "%PROCESS 20%", "%STROCSS%", "Preferred reporting of case series%"])
    famarr = np.array(sorted(fam))
    fig = plt.figure(figsize=(7.2, 6.2))
    gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.34)

    # A: the rate with and without the guidelines, and without the two sister journals' citations
    sis = [r[0] for r in con.execute("SELECT pmid FROM papers WHERE journal_id IN (?, ?)", (cr, ams))]
    own = {int(p): int(y) for p, y in zip(pmid[jid == ijs], py[jid == ijs])}
    from_sis = collections.Counter()
    for i in range(0, len(sis), 900):
        ch = sis[i:i + 900]
        for cited, yr in con.execute(f"SELECT cited_pmid, citing_year FROM citations WHERE citing_pmid IN ({','.join('?' * len(ch))}) "
                                     "AND citing_class IS NULL", ch):
            if cited in own and yr - own[cited] in (1, 2):
                from_sis[(yr, cited)] += 1
    rows = []
    for Y in range(2012, 2026):
        idx, c = window(Y, jid == ijs)
        isf = np.isin(pmid[idx], famarr)
        s = sum(from_sis[(Y, int(p))] for p in pmid[idx])
        rows.append([Y, len(c), int(c.sum()), int(isf.sum()), int(c[isf].sum()), s, c.sum() / len(c),
                     (c.sum() - c[isf].sum()) / (len(c) - isf.sum()), (c.sum() - s) / len(c)])
    write_csv("fig12a_int_j_surg_rate", ["citation_year", "citable_items", "citations", "guideline_items", "citations_to_guidelines",
                                         "citations_from_case_rep_and_ann_med_surg", "rate", "rate_without_guidelines",
                                         "rate_without_those_journals"], [[*r[:6], *[round(x, 3) for x in r[6:]]] for r in rows])
    ax = fig.add_subplot(gs[0, 0])
    yrs = [r[0] for r in rows]
    ax.plot(yrs, [r[6] for r in rows], color=BLUE, label="All citable items")
    ax.plot(yrs, [r[7] for r in rows], color=VERMILION, linewidth=1.5, label="Without the 15 guideline papers")
    ax.plot(yrs, [r[8] for r in rows], color=VERMILION, linewidth=1.3, linestyle=DASHED,
            label="Without citations from Int J Surg Case Rep\nand Ann Med Surg")
    ax.set_ylim(0, 24)
    ax.set_xticks([2012, 2016, 2020, 2024])
    ax.set_ylabel("JIF-style rate")
    ax.set_xlabel("Citation year")
    ax.legend(fontsize=6, loc="upper left")
    ax.set_title("A  Int J Surg's rate", loc="left", fontsize=8.5)

    # B: largest outside citing journal, all journals
    z = np.load(os.path.join(DATA, "citing_screen_2024.npz"))
    u, k, NJ = z["u"], z["k"], int(z["NJ"])
    cited, citing = u // NJ, u % NJ
    m = citable & ((py == 2022) | (py == 2023))
    items = np.bincount(jid[m], minlength=NJ)
    tot = np.bincount(cited, weights=k, minlength=NJ)
    ext = (cited != citing) & (citing != NJ - 1)
    best = np.zeros(NJ)
    np.maximum.at(best, cited[ext], k[ext])
    ok = (items >= 100) & (tot >= 500)
    sh = best[ok] / tot[ok]
    ax = fig.add_subplot(gs[0, 1])
    ax.hist(sh, bins=np.arange(0, 0.36, 0.01), color=GRAY, edgecolor="white", linewidth=0.4)
    for n, h, color, side in [("Circulation", 830, BLUE, 1), ("J Am Geriatr Soc", 760, BLUE, 1), ("Int J Surg", 130, VERMILION, -1)]:
        x = best[by_abbr[n]] / tot[by_abbr[n]]
        ax.plot([x, x], [0, h], color=color, linewidth=0.8)
        ax.text(x + 0.004 * side, h, f"{n} {x:.0%}", fontsize=6.3, color=INK, va="center", ha="left" if side > 0 else "right")
    ax.set_ylim(0, 880)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("Share of 2024 citations from the largest outside journal")
    ax.set_ylabel("Journals")
    ax.set_title(f"B  {ok.sum():,} journals (100+ items, 500+ citations)", loc="left", fontsize=8.5)

    # C: who cites each family
    sets = [("SCARE, PROCESS, STROCSS\n(Int J Surg)", fam),
            ("Beers Criteria\n(J Am Geriatr Soc)", family(by_abbr["J Am Geriatr Soc"], ["%Beers Criteria%for%"])),
            ("Heart Disease and Stroke\nStatistics (Circulation)", stats_papers().keys())]
    ax = fig.add_subplot(gs[1, 0])
    out, names = [], []
    for y, (lab, ps) in zip((2, 1, 0), sets):
        n = citing_journals(ps)
        total = sum(n.values())
        left = 0
        for rank_, ((j, v), color) in enumerate(zip(n.most_common(3), (VERMILION, ORANGE, SKY))):
            ax.barh(y, v / total, left=left, color=color, height=0.6, edgecolor="white", linewidth=0.6)
            if v / total >= 0.07:
                ax.text(left + v / total / 2, y, f"{v / total:.0%}", ha="center", va="center", fontsize=6.3, color=INK)
            out.append([lab.replace("\n", " "), rank_ + 1, abbr[j], v, round(v / total, 4)])
            left += v / total
        ax.barh(y, 1 - left, left=left, color="#DDDDDD", height=0.6, edgecolor="white", linewidth=0.6)
        names.append(f"{lab}\n{len(n):,} citing journals")
    write_csv("fig12c_who_cites", ["papers", "rank", "citing_journal", "citations", "share"], out)
    ax.set_yticks([2, 1, 0], names, fontsize=6.3)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    for lab, color in (("Largest citing journal", VERMILION), ("2nd", ORANGE), ("3rd", SKY), ("All others", "#DDDDDD")):
        ax.barh(0, 0, color=color, label=lab)
    ax.legend(fontsize=5.8, ncol=4, loc="upper center", bbox_to_anchor=(0.32, -0.16), frameon=False, handlelength=1, columnspacing=0.8)
    ax.set_xlabel("Share of lifetime citations")
    ax.set_title("C  Who cites them", loc="left", fontsize=8.5)

    # D: share of each journal's papers citing a guideline
    q = ",".join("?" * len(fam))
    cnt = {(j, y): n for j, y, n in con.execute(
        f"SELECT p.journal_id, p.pub_year, COUNT(DISTINCT ci.citing_pmid) FROM citations ci JOIN papers p ON p.pmid = ci.citing_pmid "
        f"WHERE ci.cited_pmid IN ({q}) AND p.doc_class IN ('research','review','case_report','guideline') GROUP BY 1, 2", list(fam))}
    ax = fig.add_subplot(gs[1, 1])
    rows, ends = [], []
    for j, lab, color in [(cr, "Int J Surg Case Rep", VERMILION), (ams, "Ann Med Surg", ORANGE), (jscr, "J Surg Case Rep\n(other publisher)", GRAY)]:
        xs, ys = [], []
        for y in range(2016, 2026):
            n = int((citable & (jid == j) & (py == y)).sum())
            if n >= 20:
                xs.append(y); ys.append(cnt.get((j, y), 0) / n); rows.append([abbr[j], y, cnt.get((j, y), 0), n, round(ys[-1], 4)])
        ax.plot(xs, ys, color=color, linewidth=1.7)
        ends.append((ys[-1], lab, color))
    end_labels(ax, ends, 0.1, 2025.45, 6.3)
    ax.set_xlim(2016, 2025)
    ax.set_ylim(0, 1.03)
    ax.set_xticks([2016, 2019, 2022, 2025])
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Citable items citing a guideline")
    ax.set_xlabel("Year published")
    ax.set_title("D  How often each journal cites them", loc="left", fontsize=8.5)
    write_csv("fig12d_share_citing", ["journal", "year", "citing_items", "citable_items", "share"], rows)
    save(fig, "fig12_int_j_surg_guidelines")


# ---------------------------------------------------------------- 13: every US vs Europe pair
PAIRS = [   # level, US journal, European journal, slugs
    ("Flagship", "Circulation", "Eur Heart J", "circulation", "european-heart-journal"),
    ("Flagship", "J Urol", "Eur Urol", "the-journal-of-urology", "european-urology"),
    ("Flagship", "Neurology", "Eur J Neurol", "neurology", "european-journal-of-neurology"),
    ("Flagship", "J Clin Oncol", "Ann Oncol", "journal-of-clinical-oncology-official-journal-of-the-american-society-of-clinical-oncology", "annals-of-oncology"),
    ("Flagship", "Arthritis Rheumatol", "Ann Rheum Dis", "arthritis-rheumatology-hoboken-n-j", "annals-of-the-rheumatic-diseases"),
    ("Flagship", "AJRCCM", "Eur Respir J", "american-journal-of-respiratory-and-critical-care-medicine", "the-european-respiratory-journal"),
    ("Flagship", "Diabetes Care", "Diabetologia", "diabetes-care", "diabetologia"),
    ("Flagship", "Hepatology", "J Hepatol", "hepatology-baltimore-md", "journal-of-hepatology"),
    ("Flagship", "Gastroenterology", "Gut", "gastroenterology", "gut"),
    ("Flagship", "Blood", "Haematologica", "blood", "haematologica"),
    ("Sister", "Ann Am Thorac Soc", "ERJ Open Res", "annals-of-the-american-thoracic-society", "erj-open-research"),
    ("Sister", "Clin Gastroenterol Hepatol", "UEG J", "clinical-gastroenterology-and-hepatology-the-official-clinical-practice-journal-of-the-american-gastroenterological-association", "united-european-gastroenterology-journal"),
    ("Sister", "Kidney360", "Clin Kidney J", "kidney360", "clinical-kidney-journal"),
    ("Sister", "Arthritis Care Res", "RMD Open", "arthritis-care-research", "rmd-open"),
    ("Sister", "Hepatol Commun", "JHEP Rep", "hepatology-communications", "jhep-reports-innovation-in-hepatology"),
    ("Sister", "Blood Adv", "HemaSphere", "blood-advances", "hemasphere"),
    ("Sister", "JCO Glob Oncol", "ESMO Open", "jco-global-oncology", "esmo-open"),
]
HIGHLIGHT = {"Circulation"}


def fig13():
    src = open(os.path.join(os.path.dirname(__file__), "alt_figures.py")).read()
    ns = {}
    exec(src[re.search(r"^EUROPE *=", src, re.M).start():src.index("REGIONS = [")], ns)
    G = {**pickle.load(open(os.path.join(DATA, "citing_geo.pkl"), "rb"))["journals"],
         **pickle.load(open(os.path.join(DATA, "citing_geo_tiers.pkl"), "rb"))["journals"]}

    def stats(s):
        d = G[s]["countries"]
        n = sum(d.values())
        us, eu = d.get("USA", 0) / n, sum(v for c, v in d.items() if c in ns["EUROPE"]) / n
        site = json.load(open(os.path.join(JSON, s + ".json")))
        return us, eu, rate(next(e for e in site["timeseries"] if e["month"] == settled_month(site)), CITABLE)

    rows = []
    for level, a, b, sa, sb in PAIRS:
        x, y = stats(sa), stats(sb)
        rows.append((level, a, b, x, y, (x[0] - x[1]) - (y[0] - y[1])))
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 5.5), sharey=True, gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.06})
    y, ticks, labels, out = 0, [], [], []
    for level in ("Flagship", "Sister"):
        group = sorted((r for r in rows if r[0] == level), key=lambda r: -r[5])
        heads = {"Flagship": "Flagship journals", "Sister": "Sister journals"}
        axes[0].text(-0.42, y, heads[level], fontsize=7, fontweight="bold", color=INK, va="center", ha="right", clip_on=False)
        y += 1
        for _, a, b, p, q, gap in group:
            hot = a in HIGHLIGHT
            axes[0].plot([p[0] - p[1], q[0] - q[1]], [y, y], color=INK if hot else GRAY, linewidth=1.6 if hot else 1.1, zorder=1)
            axes[0].scatter(p[0] - p[1], y, color=BLUE, s=30, zorder=2, edgecolor="white", linewidth=0.5)
            axes[0].scatter(q[0] - q[1], y, color=DARK_ORANGE, s=30, zorder=2, edgecolor="white", linewidth=0.5)
            axes[0].text(0.235, y, f"{gap * 100:.0f}", fontsize=6.5, color=INK, ha="right", va="center")
            axes[1].plot([p[2], q[2]], [y, y], color=INK if hot else GRAY, linewidth=1.6 if hot else 1.1, zorder=1)
            axes[1].scatter(p[2], y, color=BLUE, s=30, zorder=2, edgecolor="white", linewidth=0.5)
            axes[1].scatter(q[2], y, color=DARK_ORANGE, s=30, zorder=2, edgecolor="white", linewidth=0.5)
            ticks.append(y); labels.append(f"{a} vs {b}")
            out.append([level, a, b, round(p[0], 4), round(p[1], 4), round(p[2], 3), round(q[0], 4), round(q[1], 4), round(q[2], 3), round(gap * 100, 1)])
            y += 1
        y += 0.6
    write_csv("fig13_us_vs_europe", ["level", "us_journal", "european_journal", "us_journal_us_share", "us_journal_europe_share",
                                     "us_journal_rate", "european_journal_us_share", "european_journal_europe_share",
                                     "european_journal_rate", "gap_points"], out)
    ax = axes[0]
    ax.set_yticks(ticks, [""] * len(ticks))
    ax.invert_yaxis()
    # Each pair's names in its dots' colors, built right to left from the axis
    rend = fig.canvas.get_renderer()
    for y, lab in zip(ticks, labels):
        us, eu = lab.split(" vs ")
        x = -6
        for text, color in ((eu, DARK_ORANGE), (" vs ", MUTED), (us, BLUE)):
            t = ax.annotate(text, (0, y), xycoords=ax.get_yaxis_transform(), xytext=(x, 0), textcoords="offset points",
                            fontsize=6.5, color=color, ha="right", va="center", annotation_clip=False,
                            fontweight="bold" if us in HIGHLIGHT and text != " vs " else "normal")
            x -= t.get_window_extent(rend).width * 72 / fig.dpi + (2.2 if text == " vs " else 0)
    ax.axvline(0, color=INK, linewidth=0.7)
    ax.set_xlim(-0.40, 0.24)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:+.0f}" if v else "0"))
    ax.set_xlabel("Citing share from the USA minus from Europe (points)\n← cited more from Europe      cited more from the USA →")
    ax.text(0.235, 0.2, "Gap", fontsize=6.5, color=MUTED, ha="right", va="center", fontweight="bold")
    ax.grid(axis="y", visible=False)
    ax.scatter([], [], color=BLUE, s=30, label="US journal")
    ax.scatter([], [], color=DARK_ORANGE, s=30, label="European journal")
    ax.legend(fontsize=6.5, loc="lower right", bbox_to_anchor=(1, 0.995), ncol=2, handletextpad=0.1, columnspacing=0.8)
    ax.set_title("A  Where citations come from", loc="left", fontsize=8.5)
    ax = axes[1]
    ax.set_xscale("log")
    ax.set_xticks([2, 5, 10, 20, 50], ["2", "5", "10", "20", "50"])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlim(1.8, 62)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("24-month rate, Nov 2025 (log scale)")
    ax.set_title("B  Citation rate", loc="left", fontsize=8.5)
    save(fig, "fig13_us_vs_europe")


# ---------------------------------------------------------------- 14: statistics papers moved to JAHA
def fig14():
    st = stats_papers()
    D = {s: load(s) for s in ("circulation", "jaha", "european-heart-journal", "journal-of-the-american-college-of-cardiology")}
    end = settled_month(D["circulation"])
    ser = {s: {p["month"]: p for p in d["timeseries"]} for s, d in D.items()}
    months = [m for m in sorted(ser["circulation"]) if "2016-01" <= m <= end]
    x = np.arange(len(months))
    tot = lambda e: (sum(e["by_type"][t]["papers"] for t in CITABLE), sum(e["by_type"][t]["citations"] for t in CITABLE))
    circ, circ_m, jaha, jaha_m, rows = [], [], [], [], []
    for m in months:
        n, c = in_window(st, m)
        pc, cc = tot(ser["circulation"][m])
        pj, cj = tot(ser["jaha"][m])
        circ.append(cc / pc); circ_m.append((cc - c) / (pc - n)); jaha.append(cj / pj); jaha_m.append((cj + c) / (pj + n))
        rows.append([m, n, c, pc, pj, round(circ[-1], 3), round(circ_m[-1], 3), round(jaha[-1], 3), round(jaha_m[-1], 3)])
    ehj = [rate(ser["european-heart-journal"][m], CITABLE) for m in months]
    jacc = [rate(ser["journal-of-the-american-college-of-cardiology"][m], CITABLE) for m in months]
    write_csv("fig14_statistics_in_jaha", ["month", "statistics_papers", "citations_to_them", "circulation_items", "jaha_items",
                                           "circulation", "circulation_after_move", "jaha", "jaha_after_move"], rows)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(x, ehj, color=GREEN, linewidth=1.1)
    ax.plot(x, jacc, color=PURPLE, linewidth=1.1)
    ax.plot(x, circ, color=VERMILION, linewidth=1.7)
    ax.plot(x, circ_m, color=VERMILION, linewidth=1.3, linestyle=DASHED)
    ax.plot(x, jaha, color=BLUE, linewidth=1.7)
    ax.plot(x, jaha_m, color=BLUE, linewidth=1.3, linestyle=DASHED)
    end_labels(ax, [(circ[-1], f"Circulation {circ[-1]:.1f}", VERMILION), (circ_m[-1], f"Circulation, moved {circ_m[-1]:.1f}", VERMILION),
                    (ehj[-1], f"Eur Heart J {ehj[-1]:.1f}", GREEN), (jacc[-1], f"JACC {jacc[-1]:.1f}", PURPLE),
                    (jaha[-1], f"JAHA {jaha[-1]:.1f}", BLUE), (jaha_m[-1], f"JAHA, moved {jaha_m[-1]:.1f}", BLUE)], 1.3, len(x) - 1 + 3)
    ax.plot([], [], color=MUTED, linewidth=1.7, label="As published")
    ax.plot([], [], color=MUTED, linewidth=1.3, linestyle=DASHED, label="Statistics papers moved to JAHA, same citations")
    ax.legend(fontsize=6.5, loc="upper left")
    ticks = [i for i, m in enumerate(months) if m.endswith("-01") and int(m[:4]) % 2 == 0]
    ax.set_xticks(ticks, [months[i][:4] for i in ticks])
    ax.set_xlim(0, len(x) - 1)
    ax.set_ylim(0, 33)
    ax.set_ylabel("24-month citation rate")
    ax.set_xlabel("Month of the rate")
    save(fig, "fig14_statistics_in_jaha")


FIGS = {"1a": fig1a, "1c": fig1c, "2b": fig2b, "6a": fig6a, "6h": fig6h, "7c": fig7c, "9": fig9, "11": fig11, "12": fig12,
        "13": fig13, "14": fig14}

if __name__ == "__main__":
    for k in sys.argv[1:] or FIGS:
        print("figure", k, flush=True)
        FIGS[k]()
