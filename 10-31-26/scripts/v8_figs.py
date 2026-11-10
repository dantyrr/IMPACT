"""v8 figures: Figure 1E, 2C-E and S9B by owner; Figures 3, 4 and S3 with the full NCBI series.

Rules for the publisher panels: a band per owner, so Cell Press and Lancet sit in Elsevier, Nature Portfolio, BMC and Cureus in Springer Nature, Hindawi in Wiley.
Figure 2C-E and S9B show the seven owners with the most reviews in 2023-25.

Usage: python 10-31-26/scripts/v8_figs.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v8_base as B  # noqa: E402
import make_figures as MF  # noqa: E402
import v5_f4 as F4  # noqa: E402
import v5_fig12 as F2  # noqa: E402
import v5_reliance as R  # noqa: E402
import v7_fig1 as F1  # noqa: E402
from make_figures import BLUE, GRAY, GREEN, INK, VERMILION, dc, matplotlib, np, py  # noqa: E402
from v2_common import ORANGE, ROOT, SKY, V2, save, write_csv  # noqa: E402

M, S = B.M, B.S
# Stack order in panel E, bottom first: each owner has its own color, and neighbors were checked under simulated color blindness.
PUBLISHERS = [("Other", "#E4E4E4"), ("BMJ", "#882255"), ("RSC", "#DDCC77"), ("SAGE", "#332288"), ("Oxford UP", "#999933"), ("ACS", "#8C510A"), ("Taylor & Francis", "#AA99DD"), ("Wolters Kluwer", "#117733"),
              ("Elsevier", GRAY), ("Wiley", SKY), ("Springer Nature", VERMILION), ("AAAS", INK), ("PLOS", BLUE), ("Frontiers", GREEN), ("MDPI", ORANGE)]
COLOR = dict(PUBLISHERS)
LABEL = {"Other": "All others", "Elsevier": "Elsevier incl. Cell Press", "Wiley": "Wiley incl. Hindawi", "Springer Nature": "Springer Nature"}


def end_labels(ax, items, x, gap, fontsize=6.3):
    """Labels right of x, centered on their lines, with leader lines reaching each label."""
    items = sorted(items, key=lambda t: t[0] if t[0] == t[0] else -1)
    items = [t for t in items if t[0] == t[0]]
    ys = [items[0][0]]
    for y, *_ in items[1:]:
        ys.append(max(y, ys[-1] + gap * 0.98))
    shift = max(np.mean(ys) - np.mean([t[0] for t in items]), 0)
    shift = min(shift, ys[0])
    for yl, (y, text, col) in zip(ys, items):
        ax.annotate(text, (x, y), xytext=(x + 1.2, yl - shift), textcoords="data", fontsize=fontsize, va="center", color=INK,
                    arrowprops=dict(arrowstyle="-", color=col, linewidth=0.6, shrinkA=1.5, shrinkB=0, relpos=(0, 0.5), patchA=None))


def citing_by_issue():
    """Nucleic Acids Res citable items since 2010 that cite the NCBI series, by issue type, from the page numbers: D database issue, W web server issue."""
    q = ",".join("?" * 24)
    ids = [r[0] for r in MF.con.execute("SELECT pmid FROM papers WHERE journal_id = 122 AND title LIKE 'Database resources of the National Center%'")]
    assert len(ids) == 24
    citing = {r[0] for r in MF.con.execute(f"SELECT DISTINCT citing_pmid FROM citations WHERE cited_pmid IN ({q}) AND citing_class IS NULL", ids)}
    papers = [r[0] for r in MF.con.execute("SELECT pmid FROM papers WHERE journal_id = 122 AND pub_year >= 2010 AND pub_year <= 2025 AND doc_class IN ('research','review','case_report','guideline')")]
    full = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    tab = collections.defaultdict(lambda: [0, 0])
    for i in range(0, len(papers), 500):
        b = papers[i:i + 500]
        for p, g in full.execute(f"SELECT pmid, pagination FROM pubmed WHERE pmid IN ({','.join('?' * len(b))})", b):
            k = {"D": "database issue", "W": "web server issue"}.get((g or "").strip().upper()[:1], "other papers")
            tab[k][0] += 1
            tab[k][1] += p in citing
    write_csv("f4g_citing_by_issue", ["issue", "citable_items", "citing_the_series", "share"], [[k, a, b, round(b / a, 4)] for k, (a, b) in tab.items()])
    print(dict(tab), flush=True)


def top_for_reviews(k=7):
    r = M.citable & (dc == 1) & (py >= 2023) & (py <= 2025)
    n = {name: int((r & B.owner(name)).sum()) for name, _ in PUBLISHERS if name != "Other"}
    write_csv("f2c_owner_review_rank", ["publisher", "reviews_2023_25"], sorted(n.items(), key=lambda t: -t[1]))
    return sorted(n, key=lambda name: -n[name])[:k]


def publisher_panel(ax, title="E  Citable items by publisher"):
    tot = M.per_year(M.citable)
    vals = [M.per_year(M.citable & B.owner(n)) for n, _ in PUBLISHERS]
    assert sum(vals).sum() == tot.sum()
    ax.stackplot(M.YEARS, vals, colors=[c for _, c in PUBLISHERS], linewidth=0.25, edgecolor="white")
    write_csv("f1e_pubmed_by_publisher", ["year", *[n for n, _ in PUBLISHERS], "total"], [[int(y), *[int(v[i]) for v in vals], int(tot[i])] for i, y in enumerate(M.YEARS)])
    mid = np.cumsum([v[-1] for v in vals]) - np.array([v[-1] for v in vals]) / 2
    top = 1.72e6
    for yv, yl, (name, col) in zip(mid, F1.pack(mid, 0.0685 * top, 0.02 * top, 0.985 * top), PUBLISHERS):
        ax.annotate(LABEL.get(name, name), (M.YEARS[-1], yv), xytext=(M.YEARS[-1] + 1.0, yl), textcoords="data", fontsize=5.3, va="center", color=INK, annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=GRAY if name == "Other" else col, linewidth=0.6, shrinkA=1.5, shrinkB=0, relpos=(0, 0.5), patchA=None))
    ax.set_xlim(M.YEARS[0], M.YEARS[-1])
    ax.set_xticks([2005, 2015, 2025])
    ax.set_ylim(0, top)
    ax.tick_params(labelsize=6.3, pad=1.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1e6:.1f}M" if v else "0"))
    ax.set_ylabel("Citable items per year", fontsize=7)
    ax.set_title(title, loc="left", fontsize=8.2, pad=3)


def series_table():
    """Figure 3D's table with the NCBI row rebuilt from all 24 editions."""
    rows = list(csv.DictReader(open(os.path.join(ROOT, "10-31-26", "data", "fig2a_recurring_series_merged.csv"))))
    sid, keys = MF.series_membership()
    home = next(i for i, (_, t) in enumerate(keys) if t == "database resources of the national center for biotechnology information")
    other = [i for i, (_, t) in enumerate(keys) if t.startswith("database resources of the national center for biotechnology")]
    m = np.isin(sid, other) & (MF.jid == int(keys[home][0]))
    for r in rows:
        if r["series"].startswith("Database resources"):
            r.update(items=int(m.sum()), first_year=int(py[m].min()), last_year=int(py[m].max()), lifetime_citations=int(MF.C[m].sum()))
    rows.sort(key=lambda r: -int(r["lifetime_citations"]))
    write_csv("fig2a_recurring_series_merged", list(rows[0]), [list(r.values()) for r in rows])
    shutil.copy(os.path.join(ROOT, "10-31-26", "data", "fig11_ranked_guidelines.csv"), os.path.join(V2, "data"))
    R.OLD = os.path.join(V2, "data")
    print("NCBI", [r for r in rows if r["series"].startswith("Database")], flush=True)


def main():
    F1.publisher_panel = publisher_panel
    F2.labels = end_labels
    citing_by_issue()
    F2.PUBLISHERS = [(n, COLOR[n]) for n in top_for_reviews()]
    print(F2.PUBLISHERS, flush=True)
    fig, *_ = F1.figure1()
    save(fig, "Fig1_landscape")
    F1.s9()
    F2.figure2()
    series_table()
    R.main()
    F4.main()
    for stem in ("Fig5_timing", "Fig6_geography", "S1_publication_month", "S2_timing_detail", "S5_institutions_and_authors", "S6_retractions", "S7_citers_over_time", "S8_citers_absolute"):
        for ext in (".png", ".pdf"):
            shutil.copy(os.path.join(ROOT, "10-31-26", "v7", stem + ext), V2)


if __name__ == "__main__":
    main()
