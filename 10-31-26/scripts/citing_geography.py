"""Where a journal's citations come from -> data/analysis/citing_geo.pkl.

For each journal: citations made in 2024 to its citable items from 2022-2023 (the
2024 JIF window). Each citation is split equally across the distinct countries of
the citing paper's authors; citing papers with no located author are left out.

Usage: python 10-31-26/scripts/citing_geography.py   (from the IMPACT folder)
"""
import collections
import os
import pickle
import sqlite3
import time

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
YEAR = 2024
JOURNALS = [
    "circulation", "european-heart-journal", "circulation-research", "cardiovascular-research",
    "arteriosclerosis-thrombosis-and-vascular-biology", "atherosclerosis",
    "journal-of-clinical-oncology-official-journal-of-the-american-society-of-clinical-oncology", "annals-of-oncology",
    "gastroenterology", "gut", "hepatology-baltimore-md", "journal-of-hepatology", "diabetes-care", "diabetologia",
    "american-journal-of-respiratory-and-critical-care-medicine", "the-european-respiratory-journal",
    "journal-of-the-american-society-of-nephrology-jasn",
    "nephrology-dialysis-transplantation-official-publication-of-the-european-dialysis-and-transplant-association-european-renal-association",
    "arthritis-rheumatology-hoboken-n-j", "annals-of-the-rheumatic-diseases", "blood", "haematologica",
    "neurology", "european-journal-of-neurology",
]


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    t = time.time()
    D = np.load(os.path.join(DATA, "cites.npz"))
    pmid, jid, py, dc = D["pmid"], D["journal_id"], D["pub_year"], D["doc_class"]
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    slug2id = dict(con.execute("SELECT slug, id FROM journals"))
    citing = {}
    for s in JOURNALS:
        cited = pmid[(jid == slug2id[s]) & (dc <= 3) & ((py == YEAR - 1) | (py == YEAR - 2))].tolist()
        out = []
        for ch in chunks(cited, 500):
            q = ",".join("?" * len(ch))
            out += [r for r, in con.execute(f"SELECT citing_pmid FROM citations INDEXED BY idx_citations_cited WHERE cited_pmid IN ({q}) "
                                           f"AND citing_year = ? AND citing_class IS NULL", (*ch, YEAR))]
        citing[s] = (len(cited), out)
        print(f"  {s[:40]:40s} {len(cited):5,} items, {len(out):7,} citations, {time.time()-t:.0f}s", flush=True)

    f = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    every = sorted({p for _, ps in citing.values() for p in ps})
    countries = collections.defaultdict(set)
    for ch in chunks(every, 900):
        q = ",".join("?" * len(ch))
        for p, c in f.execute(f"SELECT a.pmid, c.country FROM author_affils a JOIN affil_countries c "
                              f"ON c.affil_id = a.affil_id WHERE a.pmid IN ({q})", ch):
            countries[p].add(c)
    print(f"{len(every):,} citing papers, {len(countries):,} located, {time.time()-t:.0f}s", flush=True)

    res = {}
    for s, (n_items, ps) in citing.items():
        share = collections.Counter()
        located = 0
        for p in ps:
            cs = countries.get(p)
            if not cs:
                continue
            located += 1
            for c in cs:
                share[c] += 1 / len(cs)
        res[s] = dict(items=n_items, citations=len(ps), located=located, countries=dict(share))
    pickle.dump(dict(year=YEAR, journals=res), open(os.path.join(DATA, "citing_geo.pkl"), "wb"))
    print(f"done, {time.time()-t:.0f}s")


if __name__ == "__main__":
    main()
