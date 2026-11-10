"""Who writes and who cites every journal -> data/analysis/country_matrix.npz.

For each journal's citable items from 2022-23: authors' countries, and the countries of papers citing them in 2024
(the 2024 JIF window). A paper is split equally across the distinct countries of its authors, as in citing_geography.py;
papers with no located author are left out. Notice citations are left out, as on the site.

Usage: python 10-31-26/scripts/country_matrix.py   (from the IMPACT folder)
"""
import os
import sqlite3
import time

import numpy as np
from scipy import sparse

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
t0 = time.time()
D = np.load(os.path.join(DATA, "cites.npz"))
pmid, jid, py, dc = D["pmid"], D["journal_id"], D["pub_year"], D["doc_class"]
NJ = int(jid.max()) + 1
row = np.full(pmid.max() + 1, -1, np.int32)
row[pmid] = np.arange(len(pmid), dtype=np.int32)
keep = ((py == 2022) | (py == 2023)) & (dc <= 3)

con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
cur = con.execute("SELECT cited_pmid, citing_pmid FROM citations WHERE citing_class IS NULL AND citing_year = 2024")
cj, cp, n = [], [], 0
while True:
    ch = cur.fetchmany(4_000_000)
    if not ch:
        break
    a = np.array(ch, np.int64)
    n += len(a)
    a = a[a[:, 0] < len(row)]
    r = row[a[:, 0]]
    ok = r >= 0
    a, r = a[ok], r[ok]
    ok = keep[r]
    cj.append(jid[r[ok]].astype(np.int32))
    cp.append(a[ok, 1])
    print(f"{n:,} citations read, {time.time() - t0:.0f}s", flush=True)
cj, cp = np.concatenate(cj), np.concatenate(cp)
aj, ap = jid[keep].astype(np.int32), pmid[keep]
print(f"{len(cj):,} window citations, {len(ap):,} citable items", flush=True)

papers = np.union1d(np.unique(cp), ap)
print(f"{len(papers):,} papers to locate", flush=True)
f = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
names, code = [], {}
rows_p, rows_c = [], []
for i in range(0, len(papers), 900):
    ch = papers[i:i + 900].tolist()
    q = ",".join("?" * len(ch))
    for p, c in f.execute(f"SELECT DISTINCT a.pmid, c.country FROM author_affils a JOIN affil_countries c "
                          f"ON c.affil_id = a.affil_id WHERE a.pmid IN ({q})", ch):
        k = code.get(c)
        if k is None:
            k = code[c] = len(names)
            names.append(c)
        rows_p.append(p); rows_c.append(k)
    if i % 450000 == 0:
        print(f"  {i:,} papers, {time.time() - t0:.0f}s", flush=True)
idx = np.searchsorted(papers, np.array(rows_p, np.int64))
ck = np.array(rows_c, np.int32)
per = np.bincount(idx, minlength=len(papers))
B = sparse.csr_matrix((1.0 / per[idx], (idx, ck)), shape=(len(papers), len(names)))
located = per > 0


def matrix(j, p):
    i = np.searchsorted(papers, p)
    A = sparse.csr_matrix((np.ones(len(j)), (j, i)), shape=(NJ, len(papers)))
    return (A @ B).toarray(), np.asarray(A.sum(axis=1)).ravel(), A @ located.astype(float)


cite, cite_n, cite_loc = matrix(cj, cp)
auth, auth_n, auth_loc = matrix(aj, ap)
np.savez_compressed(os.path.join(DATA, "country_matrix.npz"), countries=np.array(names), cite=cite, cite_n=cite_n,
                    cite_located=cite_loc, auth=auth, auth_n=auth_n, auth_located=auth_loc)
print(f"done, {time.time() - t0:.0f}s", flush=True)
