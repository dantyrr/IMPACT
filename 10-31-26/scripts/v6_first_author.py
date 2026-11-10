"""First author's institution for every citable paper, 2001-2025 -> data/analysis/first_author_inst.npz + .pkl.

PubMed held one affiliation per paper, the first author's, until about 2014, so this is the one measure that means the same
thing in 2001 and in 2025. Each paper counts once, for the first institution named in its first author's affiliation.
pubmed.first_affil reaches back to 2001; author_affils does not.

Usage: python 10-31-26/scripts/v6_first_author.py   (from the IMPACT folder)
"""
import json
import os
import pickle
import sqlite3
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from institutions import DATA, ROOT, canon  # noqa: E402
from src.pipeline.affil_institution import describe  # noqa: E402
from src.pipeline.doc_class import CITABLE, classify  # noqa: E402

FLAGSHIPS = {"0028-0836": 1, "0036-8075": 2, "0092-8674": 3, "0028-4793": 4, "0140-6736": 5}   # Nature, Science, Cell, NEJM, Lancet
YEARS = (2001, 2025)


def first_part(text):
    """(institution key, name as written, country) of the first part that names an institution."""
    if not text:
        return None
    parts = describe(text)
    country = next((p.location.country for p in parts if p.location.country), None)
    for p in parts:
        if p.institution:
            return canon(p.institution.key), p.institution.name, p.location.country or country
    return (None, None, country) if country else None


def job(row):
    pmid, issn, year, types, has_abstract, pages, title, affil = row
    try:
        t = json.loads(types) if types else []
    except ValueError:
        t = []
    cls, _ = classify(t, None if has_abstract is None else bool(has_abstract), pages, None, title)
    if cls not in CITABLE:
        return None
    return pmid, year, FLAGSHIPS.get(issn, 0), first_part(affil)


def main():
    t0 = time.time()
    f = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    cur = f.execute("SELECT pmid, issn, pub_year, pub_types, has_abstract, page_count, title, first_affil FROM pubmed WHERE pub_year BETWEEN ? AND ?", YEARS)
    keys, names, countries = {}, {}, {}
    P, Y, F, K, C = [], [], [], [], []
    with Pool(12) as pool:
        while rows := cur.fetchmany(1_000_000):
            for r in pool.imap(job, rows, chunksize=4000):
                if r is None:
                    continue
                pmid, year, flag, found = r
                k = c = -1
                if found:
                    key, name, country = found
                    if key:
                        k = keys.setdefault(key, len(keys))
                        names.setdefault(key, name)
                    if country:
                        c = countries.setdefault(country, len(countries))
                P.append(pmid); Y.append(year); F.append(flag); K.append(k); C.append(c)
            print(f"  {len(P):,} citable papers, {len(keys):,} institutions, {time.time() - t0:.0f}s", flush=True)
    np.savez_compressed(os.path.join(DATA, "first_author_inst.npz"), pmid=np.array(P, np.int64), year=np.array(Y, np.int16), flagship=np.array(F, np.int8),
                        inst=np.array(K, np.int32), country=np.array(C, np.int16))
    pickle.dump({"keys": list(keys), "names": names, "countries": list(countries)}, open(os.path.join(DATA, "first_author_inst.pkl"), "wb"))
    print("done", len(P), flush=True)


if __name__ == "__main__":
    main()
