"""F6: Int J Surg's reporting guidelines (figure_revision_plan.md, Task 7). Replaces Fig 12.

A     two screens across journals: reliance on one outside journal and on one paper. Int J Surg alone is high on both
B     its 24-month rate, with and without the guideline papers and without the two linked journals' citations
C     the 10 most-cited recurring series (Fig 2A's rule) beside these guidelines: share from the top citing journals
D-F   share of each journal's citable items citing SCARE, PROCESS and STROCSS, by quarter

Usage: python 10-31-26/scripts/v2_f6.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import (BLUE, VERMILION, GRAY, INK, MUTED, DATA, C, SERIES_GROUPS, citable, con, jid, matplotlib, np, plt,  # noqa: E402
                          pmid, py, series_membership, series_title, slug2id)
from v2_common import ORANGE, SETTLED, SKY, month_index, month_label, save, write_csv  # noqa: E402

DASHED = (0, (3.5, 2.5))
abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
by_abbr = {v: k for k, v in abbr.items()}
IJS, CR, AMS, JSCR = (by_abbr[n] for n in ("Int J Surg", "Int J Surg Case Rep", "Ann Med Surg (Lond)", "J Surg Case Rep"))
PATTERNS = ["%SCARE%", "%PROCESS%guideline%", "%PROCESS 20%", "%STROCSS%", "Preferred reporting of case series%"]
CITABLE_SQL = "('research','review','case_report','guideline')"
MOVED = (2025, 5)                # SCARE 2025 published in Premier Journal of Science, which is not in PubMed


def guideline_papers():
    out = {}
    for pat in PATTERNS:
        for p, t in con.execute(f"SELECT pmid, title FROM papers WHERE journal_id = ? AND title LIKE ? AND doc_class IN {CITABLE_SQL}", (IJS, pat)):
            out[p] = "SCARE" if "SCARE" in t else "STROCSS" if "STROCSS" in t else "PROCESS"
    return out


def rolling(items, cites, skip_items=frozenset(), skip_citing=frozenset()):
    """Monthly 24-month rate. items: {pmid: month index}. cites: (cited, citing journal, month index).
    Reading t counts citations in months t-11..t to items published t-35..t-12."""
    keep = {p: m for p, m in items.items() if p not in skip_items}
    pub = np.array(sorted(keep.values()))
    cm = np.array([c[2] for c in cites if c[0] in keep and c[1] not in skip_citing])
    cp = np.array([keep[c[0]] for c in cites if c[0] in keep and c[1] not in skip_citing])
    out = {}
    for t in range(month_index(2012, 1), month_index(2025, 11) + 1):
        n = int(((pub >= t - 35) & (pub <= t - 12)).sum())
        k = int(((cm >= t - 11) & (cm <= t) & (cp >= t - 35) & (cp <= t - 12)).sum())
        out[t] = k / n if n else float("nan")
    return out


def top_paper_share():
    name2abbr = dict(con.execute("SELECT name, abbreviation FROM journals"))
    with open(os.path.join(os.path.dirname(__file__), "..", "data", "fig1a_top_paper_share_2024.csv")) as f:
        return {name2abbr[r["journal"]]: float(r["top_paper_share"]) for r in csv.DictReader(f)}


def panel_a(ax):
    z = np.load(os.path.join(DATA, "citing_screen_2024.npz"))
    u, k, NJ = z["u"], z["k"], int(z["NJ"])
    cited, citing = u // NJ, u % NJ
    m = citable & ((py == 2022) | (py == 2023))
    items = np.bincount(jid[m], minlength=NJ)
    tot = np.bincount(cited, weights=k, minlength=NJ)
    ext = (cited != citing) & (citing != NJ - 1)
    best = np.zeros(NJ)
    np.maximum.at(best, cited[ext], k[ext])
    ok = np.flatnonzero((items >= 100) & (tot >= 500))
    sh = best[ok] / tot[ok]
    top = top_paper_share()
    has = [i for i, j in enumerate(ok) if abbr[j] in top]
    x = sh[has]
    y = np.array([top[abbr[ok[i]]] for i in has])
    names = [abbr[ok[i]] for i in has]
    write_csv("f6a_two_screens", ["journal", "citations_2024", "share_from_largest_outside_journal", "top_paper_share"],
              sorted([[n, int(tot[ok[i]]), round(float(a), 4), round(float(b), 4)] for n, i, a, b in zip(names, has, x, y)], key=lambda r: -r[2] * r[3]))
    ax.scatter(x, y, s=5, color=GRAY, alpha=0.4, linewidths=0)
    labelled = {names[i] for i in np.argsort(-x)[:3]} | {names[i] for i in np.argsort(-y)[:2]} | {names[i] for i in np.argsort(-x * y)[:2]}
    for n, a, b in zip(names, x, y):
        if n in labelled:
            special = n == "Int J Surg"
            ax.scatter([a], [b], s=20 if special else 11, color=VERMILION if special else BLUE, zorder=3, edgecolor="white", linewidth=0.4)
            left = n == "Opt Lett"
            ax.annotate(n, (a, b), xytext=(-3 if left else 3, 4), textcoords="offset points", fontsize=6.3, color=INK, ha="right" if left else "left")
    ax.axvline(np.median(x), color=MUTED, linewidth=0.6, linestyle=DASHED)
    ax.axhline(np.median(y), color=MUTED, linewidth=0.6, linestyle=DASHED)
    ax.set_xlim(0, 0.42)
    ax.set_ylim(0, 0.75)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_xlabel("Citations from its largest outside journal")
    ax.set_ylabel("Citations to its single top paper")
    ax.set_title("A  Reliance on one outside journal or paper, 2024", loc="left", fontsize=8.5)
    print("labelled:", sorted(labelled), flush=True)


def panel_b(ax, fam):
    items = {}
    for p, d in con.execute(f"SELECT pmid, pub_date FROM papers WHERE journal_id = ? AND doc_class IN {CITABLE_SQL} AND pub_date IS NOT NULL", (IJS,)):
        items[p] = month_index(int(d[:4]), int(d[5:7]))
    cites = con.execute(f"""SELECT c.cited_pmid, p.journal_id, c.citing_year * 12 + c.citing_month - 1 FROM citations c
                            JOIN papers q ON q.pmid = c.cited_pmid LEFT JOIN papers p ON p.pmid = c.citing_pmid
                            WHERE q.journal_id = ? AND c.citing_class IS NULL AND c.citing_month IS NOT NULL""", (IJS,)).fetchall()
    a, b, c = rolling(items, cites), rolling(items, cites, skip_items=set(fam)), rolling(items, cites, skip_citing={CR, AMS})
    ts = sorted(a)
    write_csv("f6b_rate", ["month", "rate_all", "rate_without_guidelines", "rate_without_case_rep_and_ann_med_surg"],
              [[month_label(t), round(a[t], 3), round(b[t], 3), round(c[t], 3)] for t in ts])
    x = [t / 12 for t in ts]
    ax.plot(x, [a[t] for t in ts], color=BLUE, linewidth=1.8, label="All citable items")
    ax.plot(x, [b[t] for t in ts], color=VERMILION, linewidth=1.4, label=f"Without the {len(fam)} guideline papers")
    ax.plot(x, [c[t] for t in ts], color=VERMILION, linewidth=1.2, linestyle=DASHED, label="Without citations from Int J Surg Case Rep\nand Ann Med Surg")
    ax.set_xlim(2012, 2026)
    ax.set_xticks([2012, 2016, 2020, 2024])
    ax.set_ylim(0, 24)
    ax.set_yticks([0, 5, 10, 15, 20])
    ax.set_ylabel("24-month rate")
    ax.set_xlabel("Month")
    ax.legend(fontsize=6, loc="upper left")
    ax.set_title("B  Int J Surg's 24-month rate, with and without guidelines", loc="left", fontsize=8.5)


def citing_counts(pmids):
    q = ",".join("?" * len(pmids))
    return collections.Counter(dict(con.execute(
        f"SELECT p.journal_id, COUNT(*) FROM citations c JOIN papers p ON p.pmid = c.citing_pmid "
        f"WHERE c.cited_pmid IN ({q}) AND c.citing_class IS NULL GROUP BY 1", [int(x) for x in pmids])))


def top_series(k=10):
    """The k most-cited merged series, as Fig 2A builds them."""
    sid, keys = series_membership()
    tot = C.sum(axis=1).astype(np.int64)
    in_s = sid >= 0
    per = np.bincount(sid[in_s], weights=tot[in_s], minlength=len(keys))
    groups = collections.defaultdict(list)
    for i in range(len(keys)):
        j, t = keys[i]
        label = next((lab for slug, sub, lab in SERIES_GROUPS if slug2id.get(slug) == j and sub in t), None)
        groups[(j, label or t)].append(i)
    gl = sorted(groups, key=lambda g: -per[groups[g]].sum())[:k]
    out = []
    for g in gl:
        lab = g[1] if any(g[1] == x for *_, x in SERIES_GROUPS) else series_title(g[0], keys[groups[g][0]][1])
        out.append((f"{lab} ({abbr[g[0]]})", pmid[np.isin(sid, groups[g])]))
    return out


def panel_c(ax, fam):
    sets = [("SCARE, PROCESS, STROCSS (Int J Surg)", list(fam))] + top_series()
    rows = []
    for lab, ps in sets:
        n = citing_counts(ps)
        total = sum(n.values())
        rows.append((sum(v for _, v in n.most_common(3)) / total, lab, n, total))
    rows.sort(key=lambda r: r[0])
    out, names = [], []
    for y, (_, lab, n, total) in enumerate(rows):
        left = 0
        for r, ((j, v), color) in enumerate(zip(n.most_common(3), (VERMILION, ORANGE, SKY))):
            ax.barh(y, v / total, left=left, color=color, height=0.68, edgecolor="white", linewidth=0.5)
            out.append([lab, r + 1, abbr[j], v, round(v / total, 4), total])
            left += v / total
        ax.barh(y, 1 - left, left=left, color="#DDDDDD", height=0.68, edgecolor="white", linewidth=0.5)
        top = n.most_common(1)[0]
        ax.text(1.01, y, f"{abbr[top[0]]}", fontsize=5.8, color=MUTED, va="center")
        names.append(lab)
    write_csv("f6c_who_cites", ["papers", "rank", "citing_journal", "citations", "share", "total_citations"], out)
    ax.set_yticks(range(len(rows)), names, fontsize=6)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="y", visible=False)
    for lab, color in (("Largest citing journal (named at right)", VERMILION), ("2nd", ORANGE), ("3rd", SKY), ("All others", "#DDDDDD")):
        ax.barh(0, 0, color=color, label=lab)
    ax.legend(fontsize=5.8, ncol=4, loc="upper center", bbox_to_anchor=(0.3, -0.2), frameon=False, handlelength=1, columnspacing=0.9)
    ax.set_xlabel("Share of lifetime citations")
    ax.set_title("C  Share of citations from the three largest citing journals: these guidelines and the 10 most-cited series", loc="left", fontsize=8.5, x=-0.82)


def family_table(fam):
    q = ",".join("?" * len(fam))
    rows = con.execute(f"SELECT c.cited_pmid, c.citing_pmid, p.journal_id, p.doc_class FROM citations c LEFT JOIN papers p ON p.pmid = c.citing_pmid "
                       f"WHERE c.cited_pmid IN ({q}) AND c.citing_class IS NULL", list(fam)).fetchall()
    by = collections.defaultdict(collections.Counter)
    papers = collections.defaultdict(set)
    for cited, citing, j, _ in rows:
        f = fam[cited]
        by[f]["all"] += 1
        by[f]["linked" if j in (CR, AMS) else "own" if j == IJS else "other"] += 1
        papers[citing].add(cited)
    first = dict(con.execute(f"SELECT pmid, pub_year FROM papers WHERE pmid IN ({q})", list(fam)))
    out = []
    for f in ("SCARE", "PROCESS", "STROCSS"):
        c = by[f]
        out.append([f, min(first[p] for p, v in fam.items() if v == f), sum(v == f for v in fam.values()), c["all"], round(c["linked"] / c["all"], 4), round(c["own"] / c["all"], 4), round(c["other"] / c["all"], 4)])
    write_csv("f6_family_citers", ["family", "first_year", "papers", "citations", "share_case_rep_and_ann_med_surg", "share_int_j_surg", "share_elsewhere"], out)
    case_rep = [p for p, in con.execute("SELECT pmid FROM papers WHERE journal_id = ?", (CR,)) if p in papers]
    one = sum(len(papers[p]) == 1 for p in case_rep)
    write_csv("f6_citations_per_paper", ["journal", "citing_papers", "cite_exactly_one_guideline_paper", "share"],
              [["Int J Surg Case Rep", len(case_rep), one, round(one / len(case_rep), 4)]])


def quarterly(fam_set, j):
    q = ",".join("?" * len(fam_set))
    den = collections.Counter()
    for y, m, n in con.execute(f"SELECT pub_year, pub_month, COUNT(*) FROM papers WHERE journal_id = ? AND doc_class IN {CITABLE_SQL} AND pub_year >= 2016 AND pub_month BETWEEN 1 AND 12 GROUP BY 1, 2", (j,)):
        den[(y, (m - 1) // 3)] += n
    num = collections.Counter()
    for y, m, n in con.execute(f"SELECT p.pub_year, p.pub_month, COUNT(DISTINCT c.citing_pmid) FROM citations c JOIN papers p ON p.pmid = c.citing_pmid "
                               f"WHERE c.cited_pmid IN ({q}) AND p.journal_id = ? AND p.doc_class IN {CITABLE_SQL} AND p.pub_year >= 2016 AND p.pub_month BETWEEN 1 AND 12 GROUP BY 1, 2",
                               [*fam_set, j]):
        num[(y, (m - 1) // 3)] += n
    return [(y + (k * 3 + 1) / 12, num[(y, k)] / n, num[(y, k)], n) for (y, k), n in sorted(den.items()) if n >= 15 and y <= 2025]


def panels_def(fig, gs, fam):
    rows = []
    lines = [(CR, "Int J Surg Case Rep", VERMILION), (AMS, "Ann Med Surg", ORANGE), (JSCR, "J Surg Case Rep (Oxford)", GRAY)]
    for i, f in enumerate(("SCARE", "PROCESS", "STROCSS")):
        ax = fig.add_subplot(gs[i])
        ps = [p for p, v in fam.items() if v == f]
        for j, lab, color in lines:
            s = quarterly(ps, j)
            ax.plot([r[0] for r in s], [r[1] for r in s], color=color, linewidth=1.5, label=lab)
            rows += [[f, abbr[j], round(r[0], 3), r[2], r[3], round(r[1], 4)] for r in s]
        ax.axvline(MOVED[0] + (MOVED[1] - 1) / 12, color=GRAY, linewidth=1.0, linestyle=DASHED)
        ax.set_ylim(0, 1.03)
        ax.set_xlim(2016, 2026)
        ax.set_xticks([2016, 2019, 2022, 2025])
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
        ax.set_xlabel("Quarter published")
        if i == 0:
            ax.set_ylabel("Citable items citing it")
        else:
            ax.tick_params(labelleft=False)
        ax.set_title(f"{'DEF'[i]}  Items citing {f}", loc="left", fontsize=8.5)
        if i == 1:
            ax.legend(fontsize=5.8, loc="upper left", handlelength=1.4, labelspacing=0.25)
        if i == 0:
            ax.text(2025.1, 0.76, "May 2025: SCARE 2025 in\nPremier J Sci, no PubMed ID", fontsize=5.8, color=INK, va="top", ha="right",
                    bbox=dict(facecolor="white", edgecolor="none", pad=0.8, alpha=0.85))
    write_csv("f6def_share_citing", ["family", "journal", "quarter", "citing_items", "citable_items", "share"], rows)


def main():
    fam = guideline_papers()
    print(len(fam), collections.Counter(fam.values()), flush=True)
    family_table(fam)
    fig = plt.figure(figsize=(7.2, 8.8))
    gs = fig.add_gridspec(3, 1, hspace=0.56, height_ratios=[1, 1.15, 0.85])
    top = gs[0].subgridspec(1, 2, wspace=0.28)
    panel_a(fig.add_subplot(top[0]))
    panel_b(fig.add_subplot(top[1]), fam)
    mid = gs[1].subgridspec(1, 3, width_ratios=[1.0, 1.35, 0.14])
    panel_c(fig.add_subplot(mid[1]), fam)
    panels_def(fig, gs[2].subgridspec(1, 3, wspace=0.12), fam)
    write_csv("f6_premier_openalex", ["paper", "doi", "citing_works_openalex", "from_int_j_surg_case_rep", "from_ann_med_surg", "checked"],
              [["SCARE 2025 (Premier Journal of Science)", "10.70389/pjs.100079", 701, 559, 34, "2026-11-05"],
               ["PROCESS 2025 (Premier Journal of Science)", "10.70389/pjs.100080", 68, 26, "", "2026-11-05"]])
    save(fig, "F6_int_j_surg")


if __name__ == "__main__":
    main()
