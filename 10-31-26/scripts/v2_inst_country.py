"""Country and type of each large institution -> data/analysis/inst_country.pkl (figure_revision_plan.md, Task 11).

Re-reads every affiliation string with institutions.py's parser and tallies, for institutions with 500+ papers, the
country and institution_type stored on the strings that name them. A multi-institution string counts only when its
own country list has one country, so a collaboration can't assign an institution to its partner's country.

Usage: python 10-31-26/scripts/v2_inst_country.py   (from the IMPACT folder)
"""
import collections
import os
import pickle
import sqlite3
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from institutions import DATA, ROOT, parse  # noqa: E402


def job(row):
    aid, text, country, kind = row
    return parse((aid, text))[1], country, kind


def main():
    d = pickle.load(open(os.path.join(DATA, "institutions.pkl"), "rb"))
    keep = {k for k, n in zip(d["keys"], d["all"]) if n >= 500}
    print(len(keep), "institutions", flush=True)
    f = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    countries = collections.defaultdict(collections.Counter)
    kinds = collections.defaultdict(collections.Counter)
    cur = f.execute("SELECT affil_id, text, country, institution_type FROM affil_strings WHERE country IS NOT NULL AND country != ''")
    n = 0
    with Pool(12) as pool:
        while rows := cur.fetchmany(1_000_000):
            for found, country, kind in pool.imap_unordered(job, rows, chunksize=2000):
                if len(found) == 1:
                    k = found[0][0]
                    if k in keep:
                        countries[k][country] += 1
                        if kind:
                            kinds[k][kind] += 1
            n += len(rows)
            print(f"  {n:,} strings", flush=True)
    pickle.dump({"countries": dict(countries), "kinds": dict(kinds)}, open(os.path.join(DATA, "inst_country.pkl"), "wb"))
    print("done", len(countries), flush=True)


if __name__ == "__main__":
    main()
