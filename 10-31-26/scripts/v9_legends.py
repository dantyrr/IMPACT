"""Legends for v9 -> v9/data/figure_legends.json: the v8 legends with S6C by owner.

Usage: python 10-31-26/scripts/v9_legends.py   (from the IMPACT folder)
"""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v9", "data")


def main():
    out = json.load(open(os.path.join(ROOT, "v8", "data", "figure_legends.json")))
    rows = {r["publisher"]: r for r in csv.DictReader(open(os.path.join(V, "fig7c_ranked.csv")))}
    both = next(csv.DictReader(open(os.path.join(V, "s6c_wiley_with_hindawi.csv"))))
    s6 = next(x for x in out if x["stem"] == "S6_retractions")
    p = next(q for q in s6["panels"] if q[0] == "C")
    p[1] = (f"Retracted papers per 10,000 citable items published 2015–23, for every publisher with at least 20,000 items, grouped by owner as in Figure 1E. Hindawi ({float(rows['Hindawi']['per_10000']):.0f}) is shown apart from the rest of Wiley ({float(rows['Wiley']['per_10000']):.0f}), which bought it in January 2021, "
            f"because its mass retraction is the main event here; together they would be {float(both['per_10000']):.0f}. Spandidos, Impact Journals, AMA and PNAS are named from their DOI prefixes.")
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(p[1])


if __name__ == "__main__":
    main()
