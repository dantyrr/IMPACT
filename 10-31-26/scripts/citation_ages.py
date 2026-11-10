"""Citations by month of age for citable papers -> data/analysis/ages.npz.

For citable items (research, review, case report, guideline) published 2014-2021,
counts the citations each received at ages 0-35 months (age 0 = the publication
month), leaving out citations made by errata, retraction notices and expressions of
concern. Ages come from the citing paper's year and month in IMPACT's citations
table. Rows follow cites.npz (`row` gives the index into it).

A calendar-year JIF counts a paper's citations at ages 13-m to 36-m, where m is its
publication month (1 = January), so 36 months covers every month's window.

Usage: python 10-31-26/scripts/citation_ages.py   (from the IMPACT folder)
"""
import os
import sqlite3
import time

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
AGES = 36
FIRST, LAST = 2014, 2021


def main():
    t = time.time()
    D = np.load(os.path.join(DATA, "cites.npz"))
    pmid, py, pm, dc = D["pmid"], D["pub_year"], D["pub_month"], D["doc_class"]
    rows = np.flatnonzero((dc <= 3) & (py >= FIRST) & (py <= LAST) & (pm >= 1) & (pm <= 12))
    look = np.full(pmid.max() + 1, -1, np.int32)
    look[pmid[rows]] = np.arange(len(rows))
    start = (py[rows].astype(np.int32) * 12 + pm[rows] - 1)
    counts = np.zeros(len(rows) * AGES, np.uint16)
    print(f"{len(rows):,} papers", flush=True)

    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    cur = con.execute("SELECT cited_pmid, citing_year, citing_month FROM citations NOT INDEXED "
                      f"WHERE citing_year BETWEEN {FIRST} AND {LAST + 3} AND citing_class IS NULL")
    n = kept = 0
    while chunk := cur.fetchmany(5_000_000):
        a = np.array(chunk, np.int64)
        n += len(a)
        cp = a[:, 0]
        cp = np.where(cp <= pmid.max(), cp, 0)
        r = look[cp]
        ok = (r >= 0) & (a[:, 2] >= 1)
        r = r[ok]
        age = a[ok, 1] * 12 + a[ok, 2] - 1 - start[r]
        ok = (age >= 0) & (age < AGES)
        flat = r[ok].astype(np.int64) * AGES + age[ok]
        u, c = np.unique(flat, return_counts=True)
        counts[u] += c.astype(np.uint16)
        kept += int(ok.sum())
        print(f"  {n:,} citations read, {kept:,} kept, {time.time()-t:.0f}s", flush=True)
    np.savez(os.path.join(DATA, "ages.npz"), row=rows, counts=counts.reshape(len(rows), AGES))
    print(f"done, {time.time()-t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
