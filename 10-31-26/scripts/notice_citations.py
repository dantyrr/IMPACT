"""Citations made by retraction notices. A retraction notice in PubMed often cites the paper it retracts, and IMPACT
(like iCite) counts that as a citation. For each journal and JIF-style year Y, counts notice citations in Y to its
citable items from Y-1 and Y-2, and the rate with and without them. Writes data/notice_citations.csv.

Usage: python 10-31-26/scripts/notice_citations.py   (from the IMPACT folder)
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import C, DATA, ROOT, Y0, dc, jid, jname, np, pmid, py, write_csv  # noqa: E402

YEARS = range(2015, 2025)
# cites.npz built without notice citations: add them back so "rate" is the rate with them, as the site had it
NOTICES_EXCLUDED = "noncounting_excluded" in np.load(os.path.join(DATA, "cites.npz")).files


def notice_citations():
    """(cited row in cites.npz, citing year) for every citation made by a retraction notice."""
    f = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    notes = [p for (p,) in f.execute("SELECT pmid FROM pubmed WHERE pub_types LIKE '%Retraction Notice%'")]
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    pairs = []
    for i in range(0, len(notes), 500):
        pairs += con.execute("SELECT cited_pmid, citing_year FROM citations INDEXED BY idx_citations_citing_pmid "
                             f"WHERE citing_pmid IN ({','.join(map(str, notes[i:i + 500]))})").fetchall()
    print(f"{len(notes):,} retraction notices made {len(pairs):,} citations", flush=True)
    a = np.array(pairs, np.int64)
    row = np.full(pmid.max() + 1, -1, np.int64)
    row[pmid] = np.arange(len(pmid))
    r = row[np.where(a[:, 0] <= pmid.max(), a[:, 0], 0)]
    ok = r >= 0
    return r[ok], a[ok, 1]


def main():
    r, cy = notice_citations()
    rows = []
    for Y in YEARS:
        m = (cy == Y) & ((py[r] == Y - 1) | (py[r] == Y - 2)) & (dc[r] <= 3)
        nj = np.bincount(jid[r[m]], minlength=jid.max() + 1)
        win = ((py == Y - 1) | (py == Y - 2)) & (dc <= 3)
        tot = np.bincount(jid[win], weights=C[win, Y - Y0], minlength=jid.max() + 1)
        if NOTICES_EXCLUDED:
            tot += nj
        items = np.bincount(jid[win], minlength=jid.max() + 1)
        print(f"{Y}: {m.sum():,} notice citations to citable items from {Y - 2}-{Y - 1}, in {(nj > 0).sum():,} journals; "
              f"notices are 5%+ of window citations in {((nj >= 0.05 * tot) & (tot >= 100) & (nj > 0)).sum()}")
        for j in np.flatnonzero(nj):
            rows.append([Y, jname[int(j)], int(items[j]), int(tot[j]), int(nj[j]), round(nj[j] / tot[j], 4),
                         round(tot[j] / items[j], 3), round((tot[j] - nj[j]) / items[j], 3)])
    rows.sort(key=lambda x: (x[0], -x[4]))
    write_csv("notice_citations", ["year", "journal", "citable_items", "window_citations", "notice_citations",
                                   "notice_share", "rate", "rate_without_notices"], rows)


if __name__ == "__main__":
    main()
