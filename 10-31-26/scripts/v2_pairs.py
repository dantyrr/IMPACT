"""Pairs for F8, chosen by rule (figure_revision_plan.md, Task 8).

Flagship and sibling: the flagship's main open-access research journal. Chosen by hand: the largest title in the family gave
Sci Rep and Heliyon, which share a publisher but not the flagship's brand or field.
High-volume and partner: the four MDPI or Frontiers journals with the most reviews 2023-25, each paired with the journal
with the highest rate among the 30 whose citing journals are most alike (cosine similarity of 2024 citing profiles). Candidates
are outside MDPI and Frontiers, with 200-3,000 citable items in 2023-25 and reviews at most 10% of them: selective journals
in the same field. Similarity alone picked small general titles, so the rate step is what makes the partner selective.

Usage: python 10-31-26/scripts/v2_pairs.py   (from the IMPACT folder)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scipy.sparse as sp  # noqa: E402
from make_figures import DATA, con, dc, jid, np, py  # noqa: E402
from v2_common import write_csv  # noqa: E402

abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
slug = dict(con.execute("SELECT id, slug FROM journals"))
by_abbr = {v: k for k, v in abbr.items()}
SIBLINGS = {"Nature": "Nat Commun", "Cell": "Cell Rep", "Lancet": "EClinicalMedicine", "Science": "Sci Adv", "JAMA": "JAMA Netw Open", "Circulation": "J Am Heart Assoc"}


def main():
    recent = (py >= 2023) & (py <= 2025) & (dc <= 3)
    n = jid.max() + 1
    items = np.bincount(jid[recent], minlength=n)
    reviews = np.bincount(jid[recent & (dc == 1)], minlength=n)
    rows = []
    for f, sib in SIBLINGS.items():
        rows.append(["flagship", f, sib, int(items[by_abbr[f]]), int(items[by_abbr[sib]]), ""])

    P = np.load(os.path.join(DATA, "publishers.npz"), allow_pickle=True)
    names = list(P["names"])
    code = P["code"]
    both = np.bincount(jid.astype(np.int64) * len(names) + code, minlength=n * len(names)).reshape(n, len(names))
    pub = both.argmax(axis=1)
    hv = [names.index("MDPI"), names.index("Frontiers")]
    is_hv = np.isin(pub, hv)
    top = np.argsort(-np.where(is_hv, reviews, 0))[:4]
    z = np.load(os.path.join(DATA, "citing_screen_2024.npz"))
    u, k, NJ = z["u"], z["k"].astype(float), int(z["NJ"])
    cited, citing = u // NJ, u % NJ
    keep = (cited != citing) & (citing != NJ - 1)
    M = sp.csr_matrix((k[keep], (cited[keep], citing[keep])), shape=(NJ, NJ))
    norm = np.sqrt(np.asarray(M.multiply(M).sum(axis=1)).ravel())
    two_years = (py >= 2022) & (py <= 2023) & (dc <= 3)
    window_items = np.bincount(jid[two_years], minlength=n)
    tot = np.bincount(cited, weights=k, minlength=NJ)[:n]
    rate = tot / np.maximum(window_items, 1)
    ok = (~is_hv) & (items >= 200) & (items <= 3000) & (reviews / np.maximum(items, 1) <= 0.10) & (norm[:n] > 0) & (window_items >= 100)
    cand = np.flatnonzero(ok)
    for t in top:
        sim = (M[cand] @ M[t].T).toarray().ravel() / (norm[cand] * norm[t])
        near = np.argsort(-sim)[:30]
        o = near[np.argsort(-rate[cand[near]])][:4]
        print(abbr[t], names[pub[t]], int(reviews[t]), [(abbr[int(cand[i])], names[pub[cand[i]]], round(float(sim[i]), 3), round(float(rate[cand[i]]), 1), int(items[cand[i]])) for i in o])
        b = int(cand[o[0]])
        rows.append(["high_volume", abbr[int(t)], abbr[b], int(items[t]), int(items[b]), round(float(sim[o[0]]), 3)])
    write_csv("f8_pairs", ["kind", "first", "second", "first_items_2023_25", "second_items_2023_25", "similarity"], rows)


if __name__ == "__main__":
    main()
