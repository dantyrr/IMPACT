"""Which universities do hospitals' authors list alongside them? -> data/analysis/hospital_links.pkl.

For every citable paper whose first author's first-named institution looks like a hospital, this counts the other institutions named in the same affiliation.
PubMed's affiliation text is the only evidence: it needs no outside list of who is affiliated with whom.

Usage: python 10-31-26/scripts/v11_hospital_links.py   (from the IMPACT folder)
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from institutions import DATA, ROOT, canon  # noqa: E402
from src.pipeline.affil_institution import describe, institution_key  # noqa: E402

CLINICAL = re.compile(r"\b(hospitals?|hospital|clinics?|medical cent(?:er|re)s?|cancer cent(?:er|re)|cancer institute|health system|health care|healthcare|infirmary|nhs|klinikum|klinik|klinika|uniklinik\w*|universitatsklinik\w*|hopitaux|hopital|ospedale|policlinico|chu|chru|ziekenhuis|sjukhus\w*|sygehus|rigshospitalet|umc|irccs)\b")
MIN_PAPERS = 100


ACADEMIC = re.compile(r"universi|institutet|medical school|school of medicine|college of medicine|medical college|faculty of medicine|medizinische hochschule|polytechnic", re.I)


def others(text):
    """The first-named institution, then every academic name in the affiliation: describe() keeps one per semicolon section, so comma pieces are read as well."""
    try:
        keys = [canon(p.institution.key) for p in describe(text) if p.institution]
        for seg in re.split(r"[,;]", text):
            seg = seg.strip(" .")
            if ACADEMIC.search(seg):
                k = institution_key(seg)
                if k:
                    keys.append(canon(k))
    except Exception:
        return ()
    return tuple(dict.fromkeys(keys))


def main():
    t0 = time.time()
    D = np.load(os.path.join(DATA, "first_author_inst.npz"))
    K = pickle.load(open(os.path.join(DATA, "first_author_inst.pkl"), "rb"))
    keys, inst, pm = K["keys"], D["inst"], D["pmid"]
    n = np.bincount(inst[inst >= 0], minlength=len(keys))
    pick = np.array([n[i] >= MIN_PAPERS and bool(CLINICAL.search(k)) for i, k in enumerate(keys)])
    sel = pm[(inst >= 0) & pick[np.maximum(inst, 0)]]
    print(int(pick.sum()), "clinical names;", len(sel), "papers", flush=True)
    con = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    pairs, total = collections.Counter(), collections.Counter()
    with Pool(12) as pool:
        for s in range(0, len(sel), 200000):
            ids = sel[s:s + 200000].tolist()
            texts = []
            for i in range(0, len(ids), 900):
                b = ids[i:i + 900]
                texts += [r[0] for r in con.execute(f"SELECT first_affil FROM pubmed WHERE pmid IN ({','.join('?' * len(b))})", b) if r[0]]
            for ks in pool.imap(others, texts, chunksize=2000):
                if not ks:
                    continue
                total[ks[0]] += 1
                for o in ks[1:]:
                    pairs[ks[0], o] += 1
            print(s, f"{time.time() - t0:.0f}s", flush=True)
    pickle.dump({"pairs": pairs, "total": total}, open(os.path.join(DATA, "hospital_links.pkl"), "wb"))
    print("done", len(pairs), f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
