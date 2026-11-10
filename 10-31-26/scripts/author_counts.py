"""Authors per PMID from pubmed_full.db -> data/analysis/author_counts.npz (pmid, n_authors)."""
import sqlite3, time, numpy as np
con = sqlite3.connect("file:/Users/dtyrrell/Projects/IMPACT/data/pubmed_full.db?mode=ro", uri=True)
t = time.time()
print(con.execute("SELECT MIN(position), MAX(position) FROM authors WHERE pmid = 18188003").fetchone(), flush=True)
cur = con.execute("SELECT pmid, COUNT(*) FROM authors GROUP BY pmid")
p, c = [], []
while rows := cur.fetchmany(2_000_000):
    a = np.array(rows, np.int64); p.append(a[:, 0]); c.append(a[:, 1])
np.savez("/Users/dtyrrell/Projects/IMPACT/data/analysis/author_counts.npz", pmid=np.concatenate(p), n=np.concatenate(c))
print(f"{sum(map(len, p)):,} pmids, {time.time()-t:.0f}s", flush=True)
