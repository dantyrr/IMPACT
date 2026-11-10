"""China's and the USA's share of first-author papers in each flagship, 2001-25 -> v8/data/f1d_by_flagship.csv and f1d_by_flagship_year.csv.

Same count as Figure 1: citable items, one per paper, by the first author's country, among papers with a known country.

Usage: python 10-31-26/scripts/v8_china_by_journal.py   (from the IMPACT folder)
"""
import csv
import os
import pickle

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
OUT = os.path.join(ROOT, "10-31-26", "v8", "data")
NAMES = {1: "Nature", 2: "Science", 3: "Cell", 4: "NEJM", 5: "Lancet"}
CHINA = {"China", "Hong Kong", "Macau", "Macao"}
PERIODS = ((2001, 2005), (2011, 2015), (2021, 2025))


def main():
    D = np.load(os.path.join(DATA, "first_author_inst.npz"))
    K = pickle.load(open(os.path.join(DATA, "first_author_inst.pkl"), "rb"))
    names = list(K["countries"])
    cn = np.array([n in CHINA for n in names] + [False])
    us = np.array([n == "USA" for n in names] + [False])
    year, flag, country = D["year"], D["flagship"], D["country"]
    known = country >= 0
    print(sorted(n for n in names if "china" in n.lower() or "hong" in n.lower() or "maca" in n.lower()))
    rows, by_year = [], []
    for f, name in NAMES.items():
        for lo, hi in PERIODS:
            m = (flag == f) & (year >= lo) & (year <= hi)
            k = m & known
            n, c, u = int(k.sum()), int(cn[country[k]].sum()), int(us[country[k]].sum())
            rows.append([name, f"{lo}-{hi}", int(m.sum()), n, c, round(c / n, 4), u, round(u / n, 4)])
        for y in range(2001, 2026):
            k = (flag == f) & (year == y) & known
            by_year.append([name, y, int(k.sum()), int(cn[country[k]].sum()), int(us[country[k]].sum())])
    for path, head, data in (("f1d_by_flagship", ["journal", "period", "papers", "with_country", "china", "china_share", "usa", "usa_share"], rows),
                             ("f1d_by_flagship_year", ["journal", "year", "with_country", "china", "usa"], by_year)):
        with open(os.path.join(OUT, path + ".csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(head)
            w.writerows(data)
    for r in rows:
        print(f"{r[0]:8s}{r[1]}  papers {r[2]:5d} known {r[3]:5d} ({r[3] / r[2]:.0%})  China {r[4]:4d} {r[5]:6.1%}  USA {r[6]:5d} {r[7]:6.1%}")
    last = [(n, sum(x[3] for x in by_year if x[0] == n and x[1] >= 2024), sum(x[2] for x in by_year if x[0] == n and x[1] >= 2024)) for n in NAMES.values()]
    print("2024-25", [(n, c, t, f"{c / t:.1%}") for n, c, t in last])
    top = [r for r in rows if r[1] == "2021-2025"]
    print("China flagship papers 2021-25", sum(r[4] for r in top), {r[0]: f"{r[4] / sum(x[4] for x in top):.0%}" for r in top})


if __name__ == "__main__":
    main()
