"""Institution name merges for v10 -> data/analysis/institution_merge.csv.

Merged: spelling variants; schools, colleges and faculties inside a university; "X University Medical Center" into X University; a trailing city; joint names, which go to the first-named institution.
Kept apart: anything named as a hospital, and institutes of national bodies such as Max Planck and the NIH institutes.
Each merge needs both names to have the same main country.

Usage: python 10-31-26/scripts/v10_merge.py   (from the IMPACT folder)
"""
import csv
import os
import pickle
import re
import sys

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
MIN_CHILD, MIN_PARENT = 30, 200
SCHOOL = (r"(?:graduate school of (?:medicine|medical sciences?|biomedical sciences?)|school of (?:medicine|public health|nursing|dental medicine|dentistry|pharmacy|engineering|law|veterinary medicine|biomedical sciences?|medical sciences?)"
          r"|college of (?:medicine|public health|nursing|dentistry|pharmacy|veterinary medicine|engineering)|faculty of (?:medicine|dentistry|pharmacy|science|health sciences?)|medical school|medical college|medical faculty|medical sciences campus|health sciences? center)")
TAIL = re.compile(rf"^(.+?) {SCHOOL}$")
HEAD = re.compile(rf"^(?:.* )?(?:medical school|medical college|school of medicine|college of medicine|faculty of medicine) (?:of|at) (?:the )?(.+)$")
BARE = re.compile(r"^(.+?) school of (?:medicine|public health|nursing|dental medicine|dentistry)$")     # "yale school of medicine": may add "university"
MEDCENTER = re.compile(r"^(.*\buniversity\b.*|university of .*) medical cent(?:er|re)$")
# Named by hand, after reading the largest names the rules left behind.
TABLE = {
    "harvard medical school": "harvard university", "harvard school of public health": "harvard university", "harvard t h chan school of public health": "harvard university", "harvard th chan school of public health": "harvard university",
    "harvard school of dental medicine": "harvard university", "johns hopkins bloomberg school of public health": "johns hopkins university", "johns hopkins university bloomberg": "johns hopkins university", "johns hopkins school of medicine": "johns hopkins university",
    "johns hopkins medical institutions": "johns hopkins university", "johns hopkins medicine": "johns hopkins university", "johns hopkins school of public health": "johns hopkins university", "johns hopkins school of nursing": "johns hopkins university",
    "johns hopkins university applied physics laboratory": "johns hopkins university",
    "columbia university vagelos": "columbia university", "columbia university mailman": "columbia university", "college of physicians and surgeons of columbia university": "columbia university", "columbia university irving medical center": "columbia university",
    "weill cornell medical college": "cornell university", "weill medical college of cornell university": "cornell university", "weill cornell medicine": "cornell university", "weill cornell medical center": "cornell university", "weill cornell medical college of cornell university": "cornell university",
    "washington university in st louis": "washington university", "washington university in saint louis": "washington university", "washington university medical center": "washington university",
    "mayo clinic college of medicine": "mayo clinic", "mayo clinic arizona": "mayo clinic", "mayo clinic and foundation": "mayo clinic", "mayo clinic rochester": "mayo clinic", "mayo clinic and mayo foundation": "mayo clinic", "mayo clinic florida": "mayo clinic",
    "mayo clinic college of medicine and science": "mayo clinic", "mayo clinic alix school of medicine": "mayo clinic", "mayo clinic jacksonville": "mayo clinic", "mayo clinic hospital": "mayo clinic", "mayo clinic scottsdale": "mayo clinic", "mayo clinic health system": "mayo clinic",
    "ucsf school of medicine": "university of california san francisco", "university of california san francisco medical center": "university of california san francisco",
    "chinese academy of science": "chinese academy of sciences", "cnrs umr": "cnrs", "umr cnrs": "cnrs", "inserm u": "inserm", "inserm umr": "inserm",
    "brown medical school": "brown university", "university of texas southwestern": "university of texas southwestern medical center", "ucl": "university college london", "ucl institute of neurology": "university college london",
    "ucl institute of child health": "university college london", "ucl institute of ophthalmology": "university college london", "imperial college": "imperial college london", "imperial college of science technology and medicine": "imperial college london",
    "king s college": "king s college london", "massachusetts general hospital harvard medical school": "massachusetts general hospital", "massachusetts general hospital cancer center": "massachusetts general hospital",
    "western university": "university of western ontario", "radboud university nijmegen": "radboud university", "radboud university nijmegen medical centre": "radboud university", "radboud university nijmegen medical center": "radboud university",
    "radboud university medical centre": "radboud university", "technion": "technion israel institute of technology", "city of hope": "city of hope national medical center",
    "david geffen school of medicine at ucla": "university of california los angeles", "ucla school of medicine": "university of california los angeles", "david geffen school of medicine": "university of california los angeles", "ucla medical center": "university of california los angeles",
    "david geffen school of medicine at university of california": "university of california los angeles",
    "nyu langone health": "new york university", "nyu grossman school of medicine": "new york university", "nyu school of medicine": "new york university", "new york university langone medical center": "new york university", "nyu langone medical center": "new york university",
    "new york university langone health": "new york university", "swiss federal institute of technology": "eth zurich", "swiss federal institute of technology zurich": "eth zurich", "university and eth zurich": "eth zurich",
    "swiss federal institute of technology lausanne": "ecole polytechnique federale de lausanne", "epfl": "ecole polytechnique federale de lausanne", "katholieke universiteit leuven": "ku leuven", "university of leuven": "ku leuven", "catholic university of leuven": "ku leuven",
    "ku leuven university of leuven": "ku leuven", "ludwig maximilians universitat munchen": "ludwig maximilians university munich", "ludwig maximilians university": "ludwig maximilians university munich", "university of munich": "ludwig maximilians university munich",
    "ludwig maximilians universitat": "ludwig maximilians university munich", "technical university munich": "technical university of munich", "universitat heidelberg": "university of heidelberg", "ruprecht karls universitat heidelberg": "university of heidelberg",
    "scripps research": "scripps research institute", "sloan kettering institute": "memorial sloan kettering cancer center",
    "mount sinai school of medicine": "icahn school of medicine at mount sinai", "northwestern university feinberg": "northwestern university", "university of miami miller": "university of miami", "medical university vienna": "medical university of vienna",
    "university of texas m d anderson cancer center": "university of texas md anderson cancer center", "md anderson cancer center": "university of texas md anderson cancer center", "m d anderson cancer center": "university of texas md anderson cancer center",
    "cleveland clinic foundation": "cleveland clinic", "technische universitat munchen": "technical university of munich", "university of texas houston": "university of texas health science center at houston", "university medical centre utrecht": "university medical center utrecht",
    "university hospital of zurich": "university hospital zurich", "university of newcastle upon tyne": "newcastle university", "university of rome la sapienza": "sapienza university of rome", "university of athens": "national and kapodistrian university of athens",
}
CITIES = {"munchen": "munich", "koln": "cologne", "wien": "vienna", "firenze": "florence", "milano": "milan", "torino": "turin", "napoli": "naples", "padova": "padua", "goteborg": "gothenburg", "kobenhavn": "copenhagen", "geneve": "geneva", "bern": "bern", "basel": "basel",
          "zurich": "zurich", "roma": "rome", "genova": "genoa", "lisboa": "lisbon", "sevilla": "seville", "coimbra": "coimbra", "porto": "porto"}
FOREIGN = re.compile(r"^(?:universitat|universite de|universite|universidad de|universita di|universita degli studi di|universita degli studi|universidade de|universidade do|universiteit|universiteit van|uniwersytet|universitatea) (\w+)$")
NEVER_PARENT = {"university", "college", "hospital", "school of medicine", "institute", "department", "university college", "medical school", "research institute", "cancer center", "irccs", "auckland", "sao paulo", "ucl", "technion", "university of western",
                "university of nevada", "university of health sciences", "california state university", "state university of new york", "national university of ireland", "university of houston", "imperial college", "king s college", "baylor university"}
NEVER_CHILD = re.compile(r"\b(hospitals?|hospitalier|klinikum|clinic of|infirmary|nhs|trust|county|bicocca|hadassah|baylor)\b")
# Different institutions whose names swap into each other: University of Washington and Washington University, Miami University and University of Miami.
NOT_SWAPPED = {"washington", "miami", "ohio", "central", "western", "eastern", "southern", "northern", "national", "state", "international", "american", "open", "north", "south", "east", "west", "new", "city", "technical", "medical", "catholic", "indiana", "pennsylvania", "georgia", "virginia", "texas",
               "jinan", "shizuoka", "nagasaki", "kochi", "hyogo", "kitakyushu", "london", "paris", "wales", "california", "dublin"}


def load():
    D = np.load(os.path.join(DATA, "first_author_inst.npz"))
    K = pickle.load(open(os.path.join(DATA, "first_author_inst.pkl"), "rb"))
    return D, K


def main_countries(D, K):
    inst, country = D["inst"], D["country"]
    m = (inst >= 0) & (country >= 0)
    nc = len(K["countries"])
    pair, n = np.unique(inst[m].astype(np.int64) * nc + country[m], return_counts=True)
    k, c = pair // nc, pair % nc
    order = np.lexsort((n, k))
    top = np.full(len(K["keys"]), -1, np.int64)
    top[k[order]] = c[order]
    return top


def propose(keys, n, home, system):
    index = {k: i for i, k in enumerate(keys)}
    parents = {k for k in keys if n[index[k]] >= MIN_PARENT and k not in NEVER_PARENT and k not in system}
    same = lambda a, b: home[index[a]] == home[index[b]] and home[index[a]] >= 0  # noqa: E731

    def parent_of(stem):
        for c in (stem, stem + " university", "university of " + stem):
            if c in parents:
                return c
        return None

    out = {}
    for k, v in TABLE.items():
        if k in index:
            out[k] = (v, "table")
    for k in keys:
        i = index[k]
        if n[i] < MIN_CHILD or k in out or k in system:
            continue
        rule = None
        p = None
        if not NEVER_CHILD.search(k):
            m = TAIL.match(k)
            if m and m.group(1) in parents:
                p, rule = m.group(1), "school"
            if not p:
                m = BARE.match(k)
                if m:
                    p, rule = parent_of(m.group(1)), "school"
            if not p:
                m = HEAD.match(k)
                if m and m.group(1) in parents:
                    p, rule = m.group(1), "school"
            if not p:
                m = MEDCENTER.match(k)
                if m and m.group(1) in parents:
                    p, rule = m.group(1), "medical center"
            if not p:          # a trailing place or school name: "duke university durham", "emory university rollins"
                a, _, b = k.rpartition(" ")
                if a in parents and "university" in a and n[index[a]] >= 10 * n[i] and b not in ("of", "and", "the", "at", "in", "hospital", "system"):
                    p, rule = a, "city"
            if not p:          # the same words in another order: "heidelberg university", "university of heidelberg"
                m = re.fullmatch(r"(\w+) university", k) or re.fullmatch(r"university of (\w+)", k)
                if m and m.group(1) not in NOT_SWAPPED:
                    other = f"university of {m.group(1)}" if k.endswith(" university") else f"{m.group(1)} university"
                    if other in parents and n[index[other]] > n[i]:
                        p, rule = other, "word order"
        m = FOREIGN.match(k)
        if not p and m:        # the same university in its own language
            c = CITIES.get(m.group(1), m.group(1))
            p = parent_of(c) if parent_of(c) != k else None
            rule = "language"
        if not p and " and " in k:   # joint names: the first-named institution
            w = k.split(" and ")
            for cut in range(1, len(w)):
                a, b = " and ".join(w[:cut]), " and ".join(w[cut:])
                if a in parents and b in parents:
                    p, rule = a, "joint"
                    break
        if p and p != k and same(p, k):
            out[k] = (p, rule)
    # follow chains
    def root(k):
        seen = []
        while k in out and k not in seen:
            seen.append(k)
            k = out[k][0]
        return min(seen, key=lambda x: (-n[index[x]], x)) if k in seen else k     # a loop ends at its largest name
    resolved = {k: (root(k), r) for k, (_, r) in out.items()}
    return {k: v for k, v in resolved.items() if v[0] != k}


def main():
    D, K = load()
    keys = list(K["keys"])
    inst = D["inst"]
    n = np.bincount(inst[inst >= 0], minlength=len(keys))
    f = np.bincount(inst[(inst >= 0) & (D["flagship"] > 0)], minlength=len(keys))
    home = main_countries(D, K)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from make_figures import SYSTEM_NAMES as system
    M = propose(keys, n, home, system)
    index = {k: i for i, k in enumerate(keys)}
    rows = sorted(([k, p, r, int(n[index[k]]), int(f[index[k]])] for k, (p, r) in M.items()), key=lambda x: -x[3])
    with open(os.path.join(DATA, "institution_merge.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "merged_into", "rule", "papers", "flagship_papers"])
        w.writerows(rows)
    print(len(rows), "merges;", sum(r[3] for r in rows), "papers;", {x: sum(1 for r in rows if r[2] == x) for x in {r[2] for r in rows}})


if __name__ == "__main__":
    main()
