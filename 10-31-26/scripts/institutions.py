"""Institutions per paper, citable items 2021-2025 -> data/analysis/institutions.pkl.

Each affiliation string is re-read with the pipeline's own parser
(src.pipeline.affil_institution.describe), so every semicolon-separated part
counts and multi-campus systems keep their campus ("University of California
San Francisco"). The institution column in pubmed_full.db holds only the last
part's name as written, which is why the text is re-read.

A paper counts once for each distinct institution among its authors.

Usage: python 10-31-26/scripts/institutions.py   (from the IMPACT folder)
"""
import collections
import os
import pickle
import re
import sqlite3
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
sys.path.insert(0, ROOT)
from src.pipeline.affil_institution import describe  # noqa: E402

DATA = os.path.join(ROOT, "data", "analysis")
JOURNALS = ("nature", "science", "cell", "nejm", "lancet")
YEARS = (2021, 2025)

_ALIASES = {
    "mit": "massachusetts institute of technology",
    "caltech": "california institute of technology",
    "ucla": "university of california los angeles",
    "ucsf": "university of california san francisco",
    "uc san diego": "university of california san diego",
    "ucsd": "university of california san diego",
    "uc berkeley": "university of california berkeley",
    "uc davis": "university of california davis",
    "uc irvine": "university of california irvine",
    "eth zurich": "eth zurich",
    "university of oxford": "university of oxford",
    "oxford university": "university of oxford",
    "university of cambridge": "university of cambridge",
    "cambridge university": "university of cambridge",
    "harvard university": "harvard university",
    "stanford university": "stanford university",
    "stanford university medical center": "stanford university",
    "stanford medicine": "stanford university",
    "chinese academy of sciences cas": "chinese academy of sciences",
    "howard hughes medical institute hhmi": "howard hughes medical institute",
}
_AT = re.compile(r"^(university of (?:california|texas|maryland|massachusetts|wisconsin|illinois|"
                 r"colorado|missouri|north carolina|nebraska|tennessee|hawaii|michigan|alabama)) at ")


# Names the parser treats as multi-campus systems, but where almost every
# paper comes from one main campus: "University of Michigan, Ann Arbor" and
# "University of Michigan Medical School" are one institution.
_ONE_CAMPUS = re.compile(r"^(university of (?:michigan|washington|minnesota|pittsburgh|virginia)|"
                         r"indiana university|purdue university|rutgers university|"
                         r"pennsylvania state university|penn state)\b.*")


def canon(key):
    key = _AT.sub(r"\1 ", key)
    key = _ONE_CAMPUS.sub(r"\1", key)
    if key == "penn state":
        key = "pennsylvania state university"
    return _ALIASES.get(key, key)


def parse(item):
    aid, text = item
    out = {}
    for part in describe(text):
        if part.institution:
            out.setdefault(canon(part.institution.key), part.institution.name)
    return aid, tuple(out.items())


def main():
    t = time.time()
    D = np.load(os.path.join(DATA, "cites.npz"))
    pmid, jid, py, dc = D["pmid"], D["journal_id"], D["pub_year"], D["doc_class"]
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    slug2id = dict(con.execute("SELECT slug, id FROM journals"))
    sel = (dc <= 3) & (py >= YEARS[0]) & (py <= YEARS[1])
    tag = np.zeros(pmid.max() + 1, np.int8)        # 1 = in window; 2 + i = JOURNALS[i]
    tag[pmid[sel]] = 1
    for i, s in enumerate(JOURNALS):
        tag[pmid[sel & (jid == slug2id[s])]] = 2 + i
    lo = int(pmid[sel].min())

    f = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    pa, aa = [], []
    cur = f.execute("SELECT pmid, affil_id FROM author_affils WHERE pmid >= ?", (lo,))
    while rows := cur.fetchmany(5_000_000):
        a = np.array(rows, np.int64)
        a = a[a[:, 0] < len(tag)]
        a = a[tag[a[:, 0]] > 0]
        pa.append(a[:, 0]); aa.append(a[:, 1])
    pa, aa = np.concatenate(pa), np.concatenate(aa)
    print(f"{len(pa):,} author-affiliation rows, {time.time()-t:.0f}s", flush=True)

    want = np.zeros(aa.max() + 1, bool)
    want[aa] = True
    key_ids, names = {}, collections.defaultdict(collections.Counter)
    aff_keys = {}                                   # affil_id -> tuple of key ids
    cur = f.execute("SELECT affil_id, text FROM affil_strings")
    with Pool(12) as pool:
        while rows := cur.fetchmany(1_000_000):
            rows = [r for r in rows if r[0] < len(want) and want[r[0]]]
            for aid, found in pool.map(parse, rows, chunksize=2000):
                ids = []
                for k, name in found:
                    ids.append(key_ids.setdefault(k, len(key_ids)))
                    names[k][name] += 1
                if ids:
                    aff_keys[aid] = tuple(ids)
            print(f"  {len(aff_keys):,} strings with an institution, {time.time()-t:.0f}s", flush=True)

    # (pmid, key) pairs, one per paper and institution
    pp, kk = [], []
    for p, a in zip(pa.tolist(), aa.tolist()):
        for k in aff_keys.get(a, ()):
            pp.append(p); kk.append(k)
    pair = np.unique(np.array(pp, np.int64) * len(key_ids) + np.array(kk, np.int64))
    pp, kk = pair // len(key_ids), pair % len(key_ids)
    tg = tag[pp]
    papers = np.unique(pp)
    out = dict(keys=list(key_ids), names={k: c.most_common(1)[0][0] for k, c in names.items()},
               journals=JOURNALS, years=YEARS,
               n_all=len(papers), all=np.bincount(kk, minlength=len(key_ids)),
               n_j={}, j={})
    ptag = tag[papers]
    for i, s in enumerate(JOURNALS):
        out["n_j"][s] = int((ptag == 2 + i).sum())
        out["j"][s] = np.bincount(kk[tg == 2 + i], minlength=len(key_ids))
    pickle.dump(out, open(os.path.join(DATA, "institutions.pkl"), "wb"))
    print(f"done: {out['n_all']:,} papers, {len(key_ids):,} institutions, "
          f"{out['n_j']} , {time.time()-t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
