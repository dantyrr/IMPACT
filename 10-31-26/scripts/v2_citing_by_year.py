"""Where 11 pairs of society journals' citations come from, each year -> data/analysis/citing_geo_by_year.pkl.

As citing_geography.py, for every citation year: citations in year Y to citable items from Y-2 and Y-1, each split equally
across the distinct countries of the citing paper's authors. Citing papers with no located author are left out. PubMed
stored only the first author's affiliation before 2014, so earlier years rest on fewer authors per paper.

Usage: python 10-31-26/scripts/v2_citing_by_year.py   (from the IMPACT folder)
"""
import collections
import os
import pickle
import sqlite3
import time

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
FIRST, LAST = 2008, 2025
JOURNALS = ["circulation", "european-heart-journal", "circulation-research", "cardiovascular-research", "arteriosclerosis-thrombosis-and-vascular-biology", "atherosclerosis",
            "journal-of-clinical-oncology-official-journal-of-the-american-society-of-clinical-oncology", "annals-of-oncology", "gastroenterology", "gut",
            "hepatology-baltimore-md", "journal-of-hepatology", "diabetes-care", "diabetologia", "american-journal-of-respiratory-and-critical-care-medicine",
            "the-european-respiratory-journal", "arthritis-rheumatology-hoboken-n-j", "annals-of-the-rheumatic-diseases", "blood", "haematologica", "neurology", "european-journal-of-neurology"]


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    t = time.time()
    D = np.load(os.path.join(DATA, "cites.npz"))
    pmid, jid, py, dc = D["pmid"], D["journal_id"], D["pub_year"], D["doc_class"]
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    slug2id = dict(con.execute("SELECT slug, id FROM journals"))
    pairs = {}
    every = set()
    for s in JOURNALS:
        m = (jid == slug2id[s]) & (dc <= 3) & (py >= FIRST - 2) & (py <= LAST - 1)
        year = dict(zip(pmid[m].tolist(), py[m].tolist()))
        out = []
        for ch in chunks(list(year), 500):
            q = ",".join("?" * len(ch))
            for cited, citing, y in con.execute(f"SELECT cited_pmid, citing_pmid, citing_year FROM citations INDEXED BY idx_citations_cited WHERE cited_pmid IN ({q}) "
                                                f"AND citing_year BETWEEN {FIRST} AND {LAST} AND citing_class IS NULL", ch):
                if y - year[cited] in (1, 2):
                    out.append((y, citing))
        pairs[s] = out
        every.update(c for _, c in out)
        print(f"  {s[:40]:40s} {len(out):8,} citations, {time.time()-t:.0f}s", flush=True)
    f = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    countries = collections.defaultdict(set)
    for n, ch in enumerate(chunks(sorted(every), 900)):
        q = ",".join("?" * len(ch))
        for p, c in f.execute(f"SELECT a.pmid, c.country FROM author_affils a JOIN affil_countries c ON c.affil_id = a.affil_id WHERE a.pmid IN ({q})", ch):
            countries[p].add(c)
        if n % 500 == 0:
            print(f"  {n * 900:,} of {len(every):,} citing papers, {time.time()-t:.0f}s", flush=True)
    res = {}
    for s, rows in pairs.items():
        for y, p in rows:
            r = res.setdefault((s, y), dict(citations=0, located=0, countries=collections.Counter()))
            r["citations"] += 1
            cs = countries.get(p)
            if cs:
                r["located"] += 1
                for c in cs:
                    r["countries"][c] += 1 / len(cs)
    pickle.dump(res, open(os.path.join(DATA, "citing_geo_by_year.pkl"), "wb"))
    print(f"done, {time.time()-t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
