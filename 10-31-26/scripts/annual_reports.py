"""Figures 9E-9G: when the big annual reports are published, and where their citations come from.

E  Citable items per publication month, 2010-25.
F  Each month's share of the series' citations in the first 24 months after publication
   (month of publication = age 0, through age 23), papers published 2010-22.
G  The same papers, but counting only the citations a calendar-year JIF counts: those made in the
   two calendar years after the publication year.

Dot size is the month's share of that row's citations, so months can be compared within a series.

Only citable items (doc_class research, review, case_report or guideline) are kept, so errata,
addenda, letters and commentaries that quote a report's title are left out. PubMed records with no
publication month are stored as June; this script looks each June record up in PubMed and moves
the ones with no month to their own "No month" column (cached in data/annual_report_no_month.json).

Usage: python 10-31-26/scripts/annual_reports.py   (from the IMPACT folder)
"""
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import BLUE, VERMILION, MUTED, OUT, ROOT, con, np, plt, save, write_csv  # noqa: E402

sys.path.insert(0, ROOT)
from src.pipeline import config  # noqa: E402
from src.pipeline.pubmed_xml import _get_date  # noqa: E402

CITABLE = ("research", "review", "case_report", "guideline")
COUNTS_FROM, COUNTS_TO = 2010, 2025          # panel E
CITES_FROM, CITES_TO = 2010, 2022            # panels F and G: JIF window complete by the end of 2024
NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "No\nmonth"]
NO_MONTH = 12                                # column index
CACHE = os.path.join(OUT, "data", "annual_report_no_month.json")

SERIES = [   # (journal slug, SQL title pattern, title regex the item must also match or None, label)
    ("ca-a-cancer-journal-for-clinicians", "Cancer statistics, 2%", None, "Cancer Statistics (CA Cancer J Clin)"),
    ("circulation", "%Heart Disease and Stroke Statistics%", None, "Heart Disease and Stroke Statistics (Circulation)"),
    ("diabetes-care", "%Standards of %Care in Diabetes%",
     r"^(\d+\. |Executive summary|Introduction|Summary of Revisions|Disclosures|Professional Practice Committee"
     r"|Updates to the Standards|Standards of)", "ADA Standards of Care (Diabetes Care)"),
    ("alzheimer-s-dementia-the-journal-of-the-alzheimer-s-association", "%Alzheimer%s disease facts and figures%", None,
     "Alzheimer's Facts and Figures (Alzheimers Dement)"),
    ("neuro-oncology", "CBTRUS Statistical Report%", None, "CBTRUS Statistical Report (Neuro Oncol)"),
    ("nucleic-acids-research", "%Database resources of the National Center%", None,
     "NCBI database resources (Nucleic Acids Res)"),
    ("european-heart-journal", "20__ %ESC%uidelines%",
     r"^20\d\d (focused update of (the )?(20\d\d )?)?\S*ESC\S* guidelines (for|on)", "ESC Guidelines (Eur Heart J)"),
    ("journal-of-the-american-college-of-cardiology", "20__ %AHA%uideline%",
     r"^20\d\d ACCF?/AHA\S* (guideline (for|on|focused)|focused update)", "ACC/AHA Guidelines (JACC)"),
]


def series_items(slug, pat, rx):
    """(pmid, year, month) of a series' citable items, 2010-25. Month is 1-12 as stored (June includes no month)."""
    j, = con.execute("SELECT id FROM journals WHERE slug = ?", (slug,)).fetchone()
    rows = con.execute(f"SELECT pmid, pub_year, pub_month, title FROM papers WHERE journal_id = ? AND title LIKE ? "
                       f"AND pub_year BETWEEN ? AND ? AND doc_class IN ({','.join('?' * len(CITABLE))})",
                       (j, pat, COUNTS_FROM, COUNTS_TO, *CITABLE)).fetchall()
    return [(p, y, m) for p, y, m, t in rows if rx is None or re.match(rx, t, re.I)]


def no_month(pmids):
    """The subset of June-dated pmids whose PubMed record has no publication month (cached)."""
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [p for p in pmids if str(p) not in cache]
    if todo:
        url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml"
               f"&api_key={config.PUBMED_API_KEY}&id={','.join(map(str, todo))}")
        root = ET.fromstring(urllib.request.urlopen(url, timeout=60).read())
        for a in root.iter("PubmedArticle"):
            cache[a.findtext(".//PMID")] = _get_date(a.find(".//Article"))[1] is None
        time.sleep(0.2)
        json.dump(cache, open(CACHE, "w"), indent=1, sort_keys=True)
    return {p for p in pmids if cache.get(str(p))}


def citations(p, y, m):
    """(first 24 months, JIF-counted) citations to pmid p published in year y, month m (m = 6 if no month)."""
    first24 = jif = 0
    for cy, cm, n in con.execute("SELECT citing_year, citing_month, COUNT(*) FROM citations INDEXED BY idx_citations_cited "
                                 "WHERE cited_pmid = ? AND citing_class IS NULL GROUP BY 1, 2", (p,)):
        if cy in (y + 1, y + 2):
            jif += n
        if cm and 1 <= cm <= 12 and 0 <= (cy * 12 + cm) - (y * 12 + m) <= 23:
            first24 += n
    return first24, jif


def dot_panel(values, labels, title, xlabel, name, fmt):
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    rows = []
    for k, (lab, v) in enumerate(zip(labels, values)):
        y = len(labels) - 1 - k
        share = v / v.sum() if v.sum() else v
        for m in range(13):
            if v[m]:
                size = 10 * np.sqrt(v[m]) + 4 if fmt is None else 450 * share[m] + 4
                ax.scatter(m + 1, y, s=size, color=VERMILION if m < 3 else BLUE, linewidths=0, alpha=0.85)
                ax.annotate(str(int(v[m])) if fmt is None else fmt(share[m]), (m + 1, y), fontsize=5.3, va="center",
                            color=MUTED, xytext=(np.sqrt(size) / 2 + 2.5, 0), textcoords="offset points")
        rows += [[lab, NAMES[m].replace("\n", " "), int(v[m]), round(float(share[m]), 4)] for m in range(13)]
    ax.set_yticks(range(len(labels) - 1, -1, -1), labels, fontsize=6.2)
    ax.set_xticks(range(1, 14), NAMES)
    ax.axvline(12.5, color=MUTED, linewidth=0.5, linestyle=":")
    ax.set_xlim(0.6, 13.7); ax.set_ylim(-0.6, len(labels) - 0.4)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontsize=8.5)
    save(fig, name)
    return rows


def main():
    items = {lab: series_items(slug, pat, rx) for slug, pat, rx, lab in SERIES}
    nm = no_month([p for its in items.values() for p, y, m in its if m == 6])
    print(f"{len(nm)} June-dated items have no month in PubMed: {sorted(nm)}")
    col = lambda p, m: NO_MONTH if p in nm else m - 1                                      # noqa: E731

    labels = list(items)
    counts, first24, jif, papers = [], [], [], []
    for lab in labels:
        c, f, g = np.zeros(13, int), np.zeros(13), np.zeros(13)
        for p, y, m in items[lab]:
            c[col(p, m)] += 1
            if CITES_FROM <= y <= CITES_TO:
                a, b = citations(p, y, m)
                f[col(p, m)] += a; g[col(p, m)] += b
                papers.append([lab, p, y, NAMES[col(p, m)].replace("\n", " "), a, b])
        counts.append(c); first24.append(f); jif.append(g)
        print(f"  {lab}: {c.sum()} items, {int(f.sum()):,} first-24-month and {int(g.sum()):,} JIF-counted citations")

    pct = lambda s: f"{s:.0%}" if s >= 0.005 else "<1%"                                    # noqa: E731
    e = dot_panel(counts, labels, "E  When the big annual reports are published",
                  f"Publication month in PubMed, {COUNTS_FROM}–{str(COUNTS_TO)[2:]} (number: citable items in that month)",
                  "fig9e_annual_report_months", None)
    f = dot_panel(first24, labels, "F  Share of each series' citations in the 24 months after publication",
                  f"Publication month, items published {CITES_FROM}–{str(CITES_TO)[2:]} "
                  "(dot size and number: month's share of the row's citations)",
                  "fig9f_annual_report_first_24_months", pct)
    g = dot_panel(jif, labels, "G  Share of each series' JIF-counted citations (two calendar years after publication)",
                  f"Publication month, items published {CITES_FROM}–{str(CITES_TO)[2:]} "
                  "(dot size and number: month's share of the row's citations)",
                  "fig9g_annual_report_jif_window", pct)
    write_csv("fig9efg_annual_reports", ["panel", "series", "month", "value", "share_of_row"],
              [["E", *r] for r in e] + [["F", *r] for r in f] + [["G", *r] for r in g])
    write_csv("fig9fg_annual_report_papers", ["series", "pmid", "pub_year", "month", "citations_first_24_months",
                                              "citations_jif_window"], papers)


if __name__ == "__main__":
    main()
