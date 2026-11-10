"""Legends for v12 -> v12/data/figure_legends.json: the v11 legends with one name per institution.

Usage: python 10-31-26/scripts/v12_legends.py   (from the IMPACT folder)
"""
import json
import os
import re

import v11_legends as L

ROOT = L.ROOT
L.V = os.path.join(ROOT, "v12", "data")
OLD = "Name variants are merged by rule: spellings and languages; schools, colleges and faculties inside a university; and joint names, which go to the first-named institution."
NEW = "Name variants are merged by rule and by a table read from the largest names: spellings and languages; former names; schools, colleges and faculties inside a university; and joint names, which go to the first-named institution."
KEPT = "keep their own dots, as do institutes of national bodies such as Max Planck and the NIH institutes."
PLACE = KEPT + " A campus whose main country differs from its parent's also keeps its own dot, such as Cleveland Clinic Abu Dhabi."


def main():
    out = json.load(open(os.path.join(ROOT, "v11", "data", "figure_legends.json")))
    by = {x["stem"]: x for x in out}
    inst = L.rd("f1ab_institutions")
    a, b = "2001-2005", "2021-2025"
    n = {p: sum(r["period"] == p for r in inst) for p in (a, b)}
    none = {p: sum(r["period"] == p and r["flagship_papers"] == "0" for r in inst) for p in n}
    p = next(q for q in by["Fig1_landscape"]["panels"] if q[0] == "A, B")
    assert OLD in p[1] and KEPT in p[1]
    p[1] = p[1].replace(OLD, NEW).replace(KEPT, PLACE)
    p[1] = re.sub(r"\([\d,]+ institutions in 2001–05, [\d,]+ in 2021–25\)", f"({n[a]:,} institutions in 2001–05, {n[b]:,} in 2021–25)", p[1])
    p[1] = re.sub(r"are not drawn \([\d,]+ and [\d,]+\)", f"are not drawn ({none[a]:,} and {none[b]:,})", p[1])

    s5 = by["S5_institutions_and_authors"]
    rows = L.rd("f11a_institutions")
    zero = sum(r["flagship_papers"] == "0" for r in rows)
    c, d, reg = L.rd("f11c_concentration"), L.rd("f11d_over_representation"), {r["region"]: r for r in L.rd("f11b_regions")}
    has = [1 - float(r["none"]) for r in d]
    china = [float(reg["China"][j]) for j in ("nature", "science", "cell", "nejm", "lancet")]
    for q in s5["panels"]:
        q[1] = re.sub(r"[\d,]+(?= large institutions)", f"{len(rows):,}", q[1])
        q[1] = re.sub(r"holds [\d,]+", f"holds {zero:,}", q[1])
        if q[0] == "B":
            q[1] = f"Each region's share of institution links in all journals (diamonds) and in each flagship (dots). China has {float(reg['China']['all_journals']) * 100:.0f}% of links in all journals and {L.rng(china).replace('%', '')}% in each flagship."
        if q[0] == "C":
            q[1] = re.sub(r"take \d+–\d+%", "take " + L.rng([float(r["top_10"]) for r in c]), q[1])
        if q[0] == "D":
            q[1] = re.sub(r"\(\d+–\d+%\)", f"({L.rng(has)})", q[1])
    json.dump(out, open(os.path.join(L.V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(p[1][:900])
    print([q[1][:220] for q in s5["panels"] if q[0] in "ABCD"])


if __name__ == "__main__":
    main()
