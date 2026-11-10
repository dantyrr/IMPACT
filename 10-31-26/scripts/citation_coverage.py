"""Citation coverage check: for 25 papers per journal from 2018-21, citations in impact.db vs the cited_by
lists in the local iCite file -> data/analysis/citation_coverage_sample.csv. Journals far below 1 are missing
citations (windows.py leaves out any journal under half).

Usage: python 10-31-26/scripts/citation_coverage.py   (from the IMPACT folder)
"""
import sqlite3, csv
ic = sqlite3.connect("file:data/icite_bulk.db?mode=ro", uri=True)
im = sqlite3.connect("file:data/impact.db?mode=ro", uri=True)
rows = []
for j, slug in im.execute("SELECT id, slug FROM journals").fetchall():
    ps = [p for p, in im.execute("SELECT pmid FROM papers WHERE journal_id=? AND pub_year BETWEEN 2018 AND 2021 ORDER BY pmid % 97 LIMIT 25", (j,))]
    a = b = 0
    for p in ps:
        r = ic.execute("SELECT cited_by FROM metadata WHERE pmid=?", (p,)).fetchone()
        if r and r[0]:
            a += len(r[0].split())
        b += im.execute("SELECT COUNT(*) FROM citations INDEXED BY idx_citations_cited WHERE cited_pmid=?", (p,)).fetchone()[0]
    rows.append([j, slug, len(ps), a, b])
with open("data/analysis/citation_coverage_sample.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["journal_id", "slug", "papers", "icite_cited_by", "impact_db"]); w.writerows(rows)
print("done", len(rows))
