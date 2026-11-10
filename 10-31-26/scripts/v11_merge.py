"""Hospitals into their universities for v11 -> data/analysis/institution_merge_v11.csv: the v10 merges plus the rules below.

By name: the hospital's name carries the university's name ("First Affiliated Hospital of Zhejiang University", "Copenhagen University Hospital").
By listing: at least 10% of the hospital's papers also list one university in the same affiliation, and that university is listed at least five times as often as any other.
A hospital that passes neither stays apart, so shared and independent hospitals keep their own dots. Both names must have the same main country.

Usage: python 10-31-26/scripts/v11_merge.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import pickle
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v10_merge as V  # noqa: E402

DATA = V.DATA
MIN_SHARE, MIN_LEAD, MIN_LISTED = 0.10, 5, 100
CLINICAL = re.compile(r"\b(hospitals?|clinics?|medical cent(?:er|re)s?|cancer cent(?:er|re)|cancer institute|health system|health care|healthcare|health sciences cent(?:er|re)|infirmary|nhs|klinikum|klinik|klinika|uniklinik\w*|universitatsklinik\w*|hopitaux|hopital|ospedale|policlinico|chu|chru|ziekenhuis|sjukhus\w*|sygehus|rigshospitalet|umc|irccs)\b")
ACADEMIC = re.compile(r"universi|chinese academy of medical sciences|dartmouth college|institutet|medical school|school of medicine|medical college|institute of technology|imperial college|king s college|university college london|rockefeller|baylor college|albert einstein college")
ADDRESS = re.compile(r"\b(avenue|ave|road|rd|street|st|drive|dr|blvd|boulevard|way|place|square|hospitals?|department|division|center|centre|clinic)\s*\w*$")
ALIASES = {"peking union medical college": "chinese academy of medical sciences", "universidade de sao paulo": "university of sao paulo", "goteborg university": "university of gothenburg", "imperial college school of medicine": "imperial college london",
           "imperial college faculty of medicine": "imperial college london", "king s and st thomas school of medicine": "king s college london", "geisel school of medicine at dartmouth": "dartmouth college", "dartmouth medical school": "dartmouth college",
           "universitat de barcelona": "university of barcelona", "ut southwestern medical center": "university of texas southwestern medical center", "national yang ming university": "national yang ming chiao tung university", "national university of singapore yong loo lin": "national university of singapore",
           "shanghai jiaotong university": "shanghai jiao tong university", "university of nijmegen": "radboud university", "university of wuerzburg": "university of wurzburg"}
GENERIC = {"children s hospital", "national university", "queen elizabeth hospital", "st mary s hospital", "st vincent s hospital", "city hospital", "people s hospital", "royal infirmary", "military hospital", "university hospital", "university hospitals", "general hospital", "teaching hospital", "university medical center", "university clinic", "university medical centre", "school of medicine", "college of medicine", "medical school", "university", "medical college"}
TABLE = {"johns hopkins hospital": "johns hopkins university", "johns hopkins bayview medical center": "johns hopkins university", "johns hopkins all children s hospital": "johns hopkins university", "sidney kimmel comprehensive cancer center at johns hopkins": "johns hopkins university",
         "stanford health care": "stanford university", "stanford hospital and clinics": "stanford university", "duke cancer institute": "duke university", "yale cancer center": "yale university", "university hospitals leuven": "ku leuven", "university hospital leuven": "ku leuven",
         "karolinska hospital": "karolinska institutet", "karolinska universitetssjukhuset": "karolinska institutet", "karolinska university hospital": "karolinska institutet", "karolinska university hospital huddinge": "karolinska institutet", "karolinska university hospital solna": "karolinska institutet",
         "rigshospitalet": "university of copenhagen", "copenhagen university hospital rigshospitalet": "university of copenhagen", "university medical center hamburg eppendorf": "university of hamburg", "university medical center rotterdam": "erasmus university",
         "king s college hospital": "king s college london", "tufts medical center": "tufts university", "dartmouth hitchcock medical center": "dartmouth college", "academic medical center": "university of amsterdam",
         "imperial college healthcare nhs trust": "imperial college london", "harvard business school": "harvard university", "harvard pilgrim health care institute": "harvard university"}
NOT_THIS = {"university hospital coventry", "university hospitals coventry and warwickshire", "university hospital of wales", "washington hospital center"}
NAMED = (re.compile(r"\b(?:hospital|center|centre|institute|clinic)s? (?:affiliated (?:to|with) |of |at )(?:the )?(.*university(?: of [\w ]+)?)$"), re.compile(r"^(.+?) university (?:teaching )?(?:hospitals?|medical cent(?:er|re)|clinics?)\b"),
         re.compile(r"^university (?:teaching )?(?:hospitals?|clinics?|medical cent(?:er|re))(?: of)? (\w+)$"), re.compile(r"^(?:universitatsklinikum|uniklinik|klinikum der universitat|chu de|hopitaux universitaires de) (\w+)$"))


def main():
    D, K = V.load()
    keys = list(K["keys"])
    index = {k: i for i, k in enumerate(keys)}
    inst = D["inst"]
    base = {r["name"]: r["merged_into"] for r in csv.DictReader(open(os.path.join(DATA, "institution_merge.csv")))}
    base = {k: ALIASES.get(v, v) for k, v in base.items()}
    base.update(ALIASES)
    root = lambda k: base.get(k, k)  # noqa: E731
    n = collections.Counter()
    cnt = np.bincount(inst[inst >= 0], minlength=len(keys))
    for k, v in zip(keys, cnt):
        if v:
            n[root(k)] += int(v)
    home_all = V.main_countries(D, K)
    home = {k: home_all[index[k]] for k in n if k in index}
    # A hospital's name must point to one place: hospitals called Prince of Wales or Queen Elizabeth exist in several countries.
    m = (inst >= 0) & (D["country"] >= 0)
    with_country = np.bincount(inst[m], minlength=len(keys))
    in_home = np.bincount(inst[m & (D["country"] == home_all[np.maximum(inst, 0)])], minlength=len(keys))
    one_place = lambda k: with_country[index[k]] > 0 and in_home[index[k]] >= 0.8 * with_country[index[k]]  # noqa: E731
    same = lambda a, b: home.get(a, -1) == home.get(b, -2)  # noqa: E731
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from make_figures import SYSTEM_NAMES
    unis = {k for k, v in n.items() if v >= V.MIN_PARENT and ACADEMIC.search(k) and not CLINICAL.search(k) and not ADDRESS.search(k) and k not in GENERIC and k not in V.NEVER_PARENT and k not in SYSTEM_NAMES}
    prefixes = sorted(unis | set(base), key=len, reverse=True)
    lookup = {p: (p if p in unis else root(p)) for p in prefixes}

    def partner(b):
        """A listed name as a university: itself, its merge, or the longest name it starts with ('harvard medical school boston')."""
        b = root(b)
        if b in unis:
            return b
        w = b.split()
        for cut in range(len(w) - 1, 1, -1):
            p = " ".join(w[:cut])
            if p in lookup and lookup[p] in unis:
                return lookup[p]
        return None

    def university(stem):
        for c in (stem, stem + " university", "university of " + stem, "university of " + V.CITIES.get(stem, stem), V.CITIES.get(stem, stem) + " university"):
            if root(c) in unis:
                return root(c)
        return None

    H = pickle.load(open(os.path.join(DATA, "hospital_links.pkl"), "rb"))
    total, listed = collections.Counter(), collections.defaultdict(collections.Counter)
    for k, v in H["total"].items():
        total[root(k)] += v
    for (a, b), v in H["pairs"].items():
        p = partner(b)
        if p and p != root(a):
            listed[root(a)][p] += v

    out = {}
    for k, v in n.items():
        if v < V.MIN_CHILD or k in unis or k in GENERIC or k in NOT_THIS or not CLINICAL.search(k) or k in V.NEVER_PARENT or k not in index or not one_place(k):
            continue
        p, rule = TABLE.get(k), "hospital table"
        if not p:
            for pat in NAMED:
                m = pat.search(k)
                if m:
                    p = university(m.group(1).strip()) or partner(m.group(1).strip())
                    if p:
                        rule = "hospital name"
                        break
        if not p:              # the university's name opens the hospital's: "fudan university shanghai cancer center"
            w = k.split()
            for cut in range(len(w) - 1, 0, -1):
                c = " ".join(w[:cut])
                if root(c) in unis and "universi" in c:
                    p, rule = root(c), "hospital name"
                    break
        if not p and total[k] >= MIN_LISTED and listed[k]:
            top = listed[k].most_common(2)
            lead = top[0][1] / max(top[1][1] if len(top) > 1 else 0, 1)
            if top[0][1] / total[k] >= MIN_SHARE and lead >= MIN_LEAD:
                p, rule = top[0][0], "hospital listed"
        if p and p != k and same(k, p):
            out[k] = (p, rule, round(listed[k][p] / total[k], 3) if total[k] else "")
    # Names whose left part is a merged name: "harvard medical school and harvard pilgrim health care".
    for k in n:
        if " and " in k and k not in out:
            a = k.split(" and ")[0]
            r = out.get(a, (root(a),))[0]
            if r != a and r in unis and same(k, r):
                out[k] = (r, "joint", "")
    rows = [[a, out.get(root(b), (root(b),))[0], r, "", ""] for a, b, r in ((x["name"], x["merged_into"], x["rule"]) for x in csv.DictReader(open(os.path.join(DATA, "institution_merge.csv"))))]
    rows += [[a, b, "table", "", ""] for a, b in ALIASES.items() if a not in {r[0] for r in rows}]
    f = np.bincount(inst[(inst >= 0) & (D["flagship"] > 0)], minlength=len(keys))
    fr = collections.Counter()
    for k, v in zip(keys, f):
        if v:
            fr[root(k)] += int(v)
    rows = [[a, b, r, int(cnt[index[a]]), int(f[index[a]]), ""] for a, b, r, *_ in rows if a in index]
    rows += [[k, p, r, n[k], fr[k], s] for k, (p, r, s) in out.items()]
    rows.sort(key=lambda x: -x[3])
    with open(os.path.join(DATA, "institution_merge_v11.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "merged_into", "rule", "papers", "flagship_papers", "listed_share"])
        w.writerows(rows)
    print(len(rows), {x: sum(1 for r in rows if r[2] == x) for x in ("hospital table", "hospital name", "hospital listed")}, "hospital papers", sum(r[3] for r in rows if str(r[2]).startswith("hospital")))
    kept = sorted(((n[k], fr[k], k, listed[k].most_common(2), total[k]) for k in n if n[k] >= 1500 and CLINICAL.search(k) and k not in out and k not in unis), reverse=True)
    pickle.dump(kept, open(os.path.join(DATA, "hospital_kept.pkl"), "wb"))


if __name__ == "__main__":
    main()
