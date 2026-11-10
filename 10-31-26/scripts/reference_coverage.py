"""How many of each journal's recent citable items have a reference list in the data -> data/analysis/reference_coverage.npz.

A paper counts if it appears at least once as a citing paper. Items from 2022-24, the years behind the Nov 2025 settled
rate and the 2024 JIF-style rate. A journal whose papers have no reference lists makes no citations in the data, so it and
the journals it cites lose them.

Usage: python 10-31-26/scripts/reference_coverage.py   (from the IMPACT folder)
"""
import os
import sqlite3
import time

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
t0 = time.time()
D = np.load(os.path.join(DATA, "cites.npz"))
pmid, jid, py, dc = D["pmid"], D["journal_id"], D["pub_year"], D["doc_class"]
keep = (py >= 2022) & (py <= 2024) & (dc <= 3)
pmid, jid = pmid[keep], jid[keep]
print(f"{len(pmid):,} citable items, 2022-24", flush=True)
LO = int(np.percentile(pmid, 0.5))
has = np.zeros(int(pmid.max()) + 1, bool)
con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
cur = con.execute("SELECT DISTINCT citing_pmid FROM citations WHERE citing_pmid >= ?", (LO,))
n = 0
while True:
    ch = cur.fetchmany(2_000_000)
    if not ch:
        break
    a = np.array(ch, np.int64).ravel()
    n += len(a)
    has[a[a < len(has)]] = True
    print(f"{n:,} citing papers, {time.time() - t0:.0f}s", flush=True)
low = pmid[pmid < LO].tolist()
for i in range(0, len(low), 900):
    ch = low[i:i + 900]
    for (p,) in con.execute(f"SELECT DISTINCT citing_pmid FROM citations WHERE citing_pmid IN ({','.join('?' * len(ch))})", ch):
        has[p] = True
NJ = int(D["journal_id"].max()) + 1
items = np.bincount(jid, minlength=NJ)
with_refs = np.bincount(jid, weights=has[pmid], minlength=NJ).astype(np.int64)
np.savez_compressed(os.path.join(DATA, "reference_coverage.npz"), items=items, with_refs=with_refs)
print(f"done: {with_refs.sum():,} of {items.sum():,} items have references, {time.time() - t0:.0f}s", flush=True)
