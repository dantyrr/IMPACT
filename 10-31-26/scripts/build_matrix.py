"""Per-paper citation counts by citing year (2003-2026) for every paper in impact.db.
Writes data/analysis/cites.npz: pmid, journal_id, pub_year, pub_month, doc_class code, counts[n, 24].
Citations made by errata, retraction notices and expressions of concern (citing_class set) are left out, as on the site."""
import sqlite3, time, numpy as np
DB = "/Users/dtyrrell/Projects/IMPACT/data/impact.db"
OUT = "/Users/dtyrrell/Projects/IMPACT/data/analysis/cites.npz"
Y0, NY = 2003, 24
CLASSES = ["research", "review", "case_report", "guideline", "commentary", "editorial", "letter", "erratum", "other"]
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
t = time.time()
rows = con.execute("SELECT pmid, journal_id, pub_year, COALESCE(pub_month,0), doc_class FROM papers").fetchall()
n = len(rows)
pmid = np.fromiter((r[0] for r in rows), np.int64, n)
jid = np.fromiter((r[1] for r in rows), np.int32, n)
py = np.fromiter((r[2] for r in rows), np.int16, n)
pm = np.fromiter((r[3] for r in rows), np.int8, n)
code = {c: i for i, c in enumerate(CLASSES)}
dc = np.fromiter((code.get(r[4], len(CLASSES)) for r in rows), np.int8, n)
del rows
row_of = np.full(pmid.max() + 1, -1, np.int32)
row_of[pmid] = np.arange(n, dtype=np.int32)
print(f"{n:,} papers loaded in {time.time()-t:.0f}s", flush=True)
counts = np.zeros(n * NY, np.uint32)
cur = con.execute("SELECT cited_pmid, citing_year FROM citations WHERE citing_class IS NULL")
seen = 0
while True:
    chunk = cur.fetchmany(4_000_000)
    if not chunk:
        break
    a = np.array(chunk, np.int64)
    seen += len(a)
    a = a[(a[:, 0] < len(row_of)) & (a[:, 1] >= Y0) & (a[:, 1] < Y0 + NY)]
    r = row_of[a[:, 0]]
    ok = r >= 0
    flat = r[ok].astype(np.int64) * NY + (a[ok, 1] - Y0)
    u, c = np.unique(flat, return_counts=True)
    counts[u] += c.astype(np.uint32)
    if seen % 40_000_000 < 4_000_000:
        print(f"  {seen:,} citations read, {time.time()-t:.0f}s", flush=True)
np.savez(OUT, pmid=pmid, journal_id=jid, pub_year=py, pub_month=pm, doc_class=dc,
         counts=counts.reshape(n, NY), classes=np.array(CLASSES), noncounting_excluded=True)
print(f"done: {seen:,} citations, {int(counts.sum()):,} counted, {time.time()-t:.0f}s -> {OUT}", flush=True)
