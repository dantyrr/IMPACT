"""Legends for v10 -> v10/data/figure_legends.json: the v9 legends with institution names merged.

Usage: python 10-31-26/scripts/v10_legends.py   (from the IMPACT folder)
"""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v10", "data")
RULE = ("Name variants are merged by rule: spellings and languages; schools, colleges and faculties inside a university; a medical center carrying the university's name; and joint names, which go to the first-named institution. Hospitals with their own names stay separate, as do institutes of national bodies such as Max Planck and the NIH institutes.")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def rng(values, pct=True):
    return f"{min(values) * 100:.0f}–{max(values) * 100:.0f}%"


def main():
    out = json.load(open(os.path.join(ROOT, "v9", "data", "figure_legends.json")))
    by = {x["stem"]: x for x in out}
    inst = rd("f1ab_institutions")
    a, b = "2001-2005", "2021-2025"
    n = {p: sum(r["period"] == p for r in inst) for p in (a, b)}
    none = {p: sum(r["period"] == p and r["flagship_papers"] == "0" for r in inst) for p in n}
    f1 = by["Fig1_landscape"]
    p = next(q for q in f1["panels"] if q[0] == "A, B")
    p[1] = p[1].replace("(1,400 institutions in 2001–05, 1,569 in 2021–25)", f"({n[a]:,} institutions in 2001–05, {n[b]:,} in 2021–25)").replace("(415 and 691)", f"({none[a]:,} and {none[b]:,})")
    assert str(n[a]) not in "" and f"{n[a]:,}" in p[1] and f"{none[b]:,}" in p[1]
    p[1] = p[1].replace("Institutions with no flagship paper", RULE + " Institutions with no flagship paper")

    s5 = by["S5_institutions_and_authors"]
    rows = rd("f11a_institutions")
    zero = sum(r["flagship_papers"] == "0" for r in rows)
    c, d, reg = rd("f11c_concentration"), rd("f11d_over_representation"), {r["region"]: r for r in rd("f11b_regions")}
    has = [1 - float(r["none"]) for r in d]
    china = [float(reg["China"][j]) for j in ("nature", "science", "cell", "nejm", "lancet")]
    for q in s5["panels"]:
        q[1] = q[1].replace("2,647", f"{len(rows):,}").replace("holds 293", f"holds {zero:,}")
        if q[0] == "B":
            q[1] = f"Each region's share of institution links in all journals (diamonds) and in each flagship (dots). China has {float(reg['China']['all_journals']) * 100:.0f}% of links in all journals and {rng(china).replace('%', '')}% in each flagship."
        if q[0] == "C":
            q[1] = q[1].replace("12–16%", rng([float(r["top_10"]) for r in c]))
        if q[0] == "D":
            q[1] = q[1].replace("(44–71%)", f"({rng(has)})")
    s5["note"] = s5["note"].rstrip() + " Names are merged as in Figure 1A and B; a paper naming both a university and one of its schools counts as two links."
    txt = json.dumps(out, ensure_ascii=False)
    assert "2,647" not in txt and "1,569" not in txt
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(p[1][:900]); print([q[1][:170] for q in s5["panels"] if q[0] in "BCD"])


if __name__ == "__main__":
    main()
