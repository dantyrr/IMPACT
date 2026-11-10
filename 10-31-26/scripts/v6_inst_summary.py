"""Numbers behind the first-author comparison, printed for checking. Usage: python 10-31-26/scripts/v6_inst_summary.py"""
import os, pickle, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DATA = "/Users/dtyrrell/Projects/IMPACT/data/analysis"
D = np.load(f"{DATA}/first_author_inst.npz"); K = pickle.load(open(f"{DATA}/first_author_inst.pkl", "rb"))
y, fl, inst, ctry = D["year"], D["flagship"], D["inst"], D["country"]
keys, cn = K["keys"], np.array(K["countries"] + ["?"])
print(len(y), "papers;", len(keys), "institutions;", len(cn), "countries")
for yy in (2001, 2003, 2005, 2010, 2015, 2020, 2021, 2023, 2025):
    m = y == yy
    print(yy, m.sum(), f"inst {np.mean(inst[m] >= 0):.3f} country {np.mean(ctry[m] >= 0):.3f}", "flag", (m & (fl > 0)).sum(), f"inst {np.mean(inst[m & (fl > 0)] >= 0):.3f} country {np.mean(ctry[m & (fl > 0)] >= 0):.3f}")
for lo, hi in ((2001, 2005), (2021, 2025)):
    m = (y >= lo) & (y <= hi)
    print(lo, hi, "per flagship", np.bincount(fl[m], minlength=6))
    for lab, mm in (("all", m), ("flag", m & (fl > 0))):
        c = ctry[mm]; c = c[c >= 0]
        u, n = np.unique(c, return_counts=True); o = np.argsort(-n)[:8]
        print("  ", lab, [(cn[u[i]], round(n[i] / len(c) * 100, 1)) for i in o])
    for lab, mm in (("all", m), ("flag", m & (fl > 0))):
        c = inst[mm]; c = c[c >= 0]
        u, n = np.unique(c, return_counts=True); o = np.argsort(-n)[:14]
        print("  ", lab, [(keys[u[i]], int(n[i])) for i in o])
