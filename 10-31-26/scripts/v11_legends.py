"""Legends for v11 -> v11/data/figure_legends.json: the v10 legends with hospitals in their universities.

Usage: python 10-31-26/scripts/v11_legends.py   (from the IMPACT folder)
"""
import csv
import json
import os
import re

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v11", "data")
OLD_RULE = ("Name variants are merged by rule: spellings and languages; schools, colleges and faculties inside a university; a medical center carrying the university's name; and joint names, which go to the first-named institution. Hospitals with their own names stay separate, as do institutes of national bodies such as Max Planck and the NIH institutes.")
RULE = ("Name variants are merged by rule: spellings and languages; schools, colleges and faculties inside a university; and joint names, which go to the first-named institution. Hospitals count with their university when their name carries the university's name, or when at least 10% of their papers list that university in the same affiliation and it is listed at least five times as often as any other. "
        "Hospitals that pass neither test, such as Memorial Sloan Kettering, Mayo Clinic and NewYork-Presbyterian, keep their own dots, as do institutes of national bodies such as Max Planck and the NIH institutes.")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def rng(values):
    return f"{min(values) * 100:.0f}–{max(values) * 100:.0f}%"


def main():
    out = json.load(open(os.path.join(ROOT, "v10", "data", "figure_legends.json")))
    by = {x["stem"]: x for x in out}
    inst = rd("f1ab_institutions")
    a, b = "2001-2005", "2021-2025"
    n = {p: sum(r["period"] == p for r in inst) for p in (a, b)}
    none = {p: sum(r["period"] == p and r["flagship_papers"] == "0" for r in inst) for p in n}
    p = next(q for q in by["Fig1_landscape"]["panels"] if q[0] == "A, B")
    assert OLD_RULE in p[1]
    p[1] = p[1].replace(OLD_RULE, RULE)
    p[1] = re.sub(r"\([\d,]+ institutions in 2001–05, [\d,]+ in 2021–25\)", f"({n[a]:,} institutions in 2001–05, {n[b]:,} in 2021–25)", p[1])
    p[1] = re.sub(r"are not drawn \([\d,]+ and [\d,]+\)", f"are not drawn ({none[a]:,} and {none[b]:,})", p[1])
    assert f"{n[a]:,}" in p[1] and f"{none[b]:,}" in p[1]

    s5 = by["S5_institutions_and_authors"]
    rows = rd("f11a_institutions")
    zero = sum(r["flagship_papers"] == "0" for r in rows)
    c, d, reg = rd("f11c_concentration"), rd("f11d_over_representation"), {r["region"]: r for r in rd("f11b_regions")}
    has = [1 - float(r["none"]) for r in d]
    china = [float(reg["China"][j]) for j in ("nature", "science", "cell", "nejm", "lancet")]
    for q in s5["panels"]:
        q[1] = re.sub(r"[\d,]+(?= large institutions)", f"{len(rows):,}", q[1])
        q[1] = re.sub(r"holds [\d,]+", f"holds {zero:,}", q[1])
        if q[0] == "B":
            q[1] = f"Each region's share of institution links in all journals (diamonds) and in each flagship (dots). China has {float(reg['China']['all_journals']) * 100:.0f}% of links in all journals and {rng(china).replace('%', '')}% in each flagship."
        if q[0] == "C":
            q[1] = re.sub(r"take \d+–\d+%", "take " + rng([float(r["top_10"]) for r in c]), q[1])
        if q[0] == "D":
            q[1] = re.sub(r"\(\d+–\d+%\)", f"({rng(has)})", q[1])
    old = "Names are merged as in Figure 1A and B; a paper naming both a university and one of its schools counts as two links."
    assert old in s5["note"]
    s5["note"] = s5["note"].replace(old, "Names are merged as in Figure 1A and B before links are counted, so a paper naming a university and its hospitals is one link for that university.")
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(p[1][300:1100])
    print([q[1][:200] for q in s5["panels"] if q[0] in "ABCD"])


if __name__ == "__main__":
    main()
