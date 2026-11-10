"""Publisher groups for v7 -> data/analysis/publisher_groups.npz and v7/data/publisher_prefixes.csv.

Each paper's publisher comes from its DOI prefix, with a publisher's imprints and bought-in lists under the owner (Hindawi under Wiley, Dove under Taylor & Francis).
Society prefixes stay apart even when a commercial house prints the journal. Cell Press is split out of Elsevier by journal, and Nature Portfolio from the rest of Springer Nature by prefix.
A paper with no DOI takes its journal's publisher when at least 80% of that journal's DOIs share one.

Usage: python 10-31-26/scripts/v7_publishers.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import sqlite3

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
OUT = os.path.join(ROOT, "10-31-26", "v7", "data")
OWNERS = {
    "Elsevier": "10.1016 10.1053 10.1067 10.1006 10.1054 10.1078 10.1383",
    "Springer, BMC, Cureus": "10.1007 10.1186 10.7759 10.1245 10.2165 10.1208 10.3758 10.1023 10.1057 10.1140",
    "Nature Portfolio": "10.1038",
    "Wiley, Hindawi": "10.1002 10.1111 10.1155 10.1113 10.1118 10.1046 10.1034 10.1196",
    "MDPI": "10.3390", "Frontiers": "10.3389", "PLOS": "10.1371", "AAAS": "10.1126",
    "Wolters Kluwer": "10.1097 10.4103 10.1213 10.1227 10.1519 10.1249",
    "Taylor & Francis": "10.1080 10.2147 10.3109 10.4161 10.1517 10.1586 10.1179 10.2217 10.4155",
    "Oxford UP": "10.1093", "SAGE": "10.1177 10.1258", "ACS": "10.1021", "RSC": "10.1039", "BMJ": "10.1136",
}
PREFIX = {p: k for k, v in OWNERS.items() for p in v.split()}
# Cell Press journals: the Cell family, Current Biology, Structure, Trends and partner titles.
CELL_PRESS = {"Cell", "Immunity", "Neuron", "Mol Cell", "Cell Metab", "Cell Stem Cell", "Cancer Cell", "Dev Cell", "Cell Host Microbe", "Cell Chem Biol", "Chem Biol", "Cell Syst", "Chem", "Cell Rep",
              "Cell Rep Med", "Cell Rep Methods", "Cell Rep Phys Sci", "Cell Rep Sustain", "Cell Genom", "iScience", "Heliyon", "STAR Protoc", "Curr Biol", "Structure", "Joule", "Matter", "Patterns (N Y)",
              "Med", "One Earth", "Device", "Newton", "Am J Hum Genet", "Biophys J", "Mol Ther", "Mol Ther Nucleic Acids", "Mol Ther Methods Clin Dev", "Mol Ther Oncol", "Stem Cell Reports", "Mol Plant",
              "Plant Commun", "HGG Adv", "Biophys Rep (N Y)", "Trends Biochem Sci", "Trends Biotechnol", "Trends Cancer", "Trends Cell Biol", "Trends Chem", "Trends Cogn Sci", "Trends Ecol Evol",
              "Trends Endocrinol Metab", "Trends Genet", "Trends Immunol", "Trends Microbiol", "Trends Mol Med", "Trends Neurosci", "Trends Parasitol", "Trends Pharmacol Sci", "Trends Plant Sci"}
GROUPS = ["Cell Press", *OWNERS, "Other"]


def prefix(doi):
    return doi.split("/", 1)[0].strip().lower() if doi else ""


def main():
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
    cell = {j for j, a in abbr.items() if a in CELL_PRESS}
    print("Cell Press journals found", len(cell), "of", len(CELL_PRESS), "missing", sorted(CELL_PRESS - {abbr[j] for j in cell}))
    code = {g: i for i, g in enumerate(GROUPS)}
    pm, jd, pc, raw = [], [], [], []
    names = {"": 0}
    cur = con.execute("SELECT pmid, journal_id, doi FROM papers")
    while rows := cur.fetchmany(2_000_000):
        for p, j, d in rows:
            x = prefix(d)
            pm.append(p); jd.append(j)
            raw.append(names.setdefault(x, len(names)))
            pc.append(-1 if not x else code["Cell Press"] if x == "10.1016" and j in cell else code[PREFIX.get(x, "Other")])
    pm, jd, pc, raw = np.array(pm, np.int64), np.array(jd, np.int32), np.array(pc, np.int8), np.array(raw, np.int32)

    # No DOI: the journal's publisher, when one holds at least 80% of its DOIs.
    has = pc >= 0
    pair, n = np.unique(jd[has].astype(np.int64) * len(GROUPS) + pc[has], return_counts=True)
    j, g = pair // len(GROUPS), pair % len(GROUPS)
    tot = np.bincount(j, weights=n, minlength=jd.max() + 1)
    best = np.full(jd.max() + 1, code["Other"], np.int8)
    order = np.argsort(n)                       # the largest group is written last
    ok = n[order] >= 0.8 * tot[j[order]]
    best[j[order][ok]] = g[order][ok]
    filled = best[jd[~has]]
    print("no DOI", int((~has).sum()), "given a publisher", int((filled != code["Other"]).sum()))
    pc[~has] = filled
    np.savez(os.path.join(DATA, "publisher_groups.npz"), pmid=pm, code=pc, names=np.array(GROUPS), raw=raw)

    # Every prefix with its publisher, largest journal and citable items.
    D = np.load(os.path.join(DATA, "cites.npz"))
    year = np.zeros(int(max(D["pmid"].max(), pm.max())) + 1, np.int16)
    m = (D["doc_class"] <= 3) & (D["pub_year"] >= 2005) & (D["pub_year"] <= 2025)
    year[D["pmid"][m]] = D["pub_year"][m]
    y = year[pm]
    label = {v: k for k, v in names.items()}
    rows = []
    a = np.bincount(raw[y > 0], minlength=len(names))
    b = np.bincount(raw[y >= 2021], minlength=len(names))
    top = collections.defaultdict(collections.Counter)
    pair, n = np.unique(raw[y >= 2005].astype(np.int64) * (jd.max() + 1) + jd[y >= 2005], return_counts=True)
    for k, v in zip(pair, n):
        top[int(k // (jd.max() + 1))][int(k % (jd.max() + 1))] = int(v)
    for i in np.argsort(-a):
        if a[i]:
            t = label[int(i)]
            rows.append([t or "no DOI", PREFIX.get(t, "Other") if t else "journal's publisher, else Other", abbr.get(top[int(i)].most_common(1)[0][0], ""), int(a[i]), int(b[i])])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "publisher_prefixes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doi_prefix", "publisher", "largest_journal", "citable_items_2005_25", "citable_items_2021_25"])
        w.writerows(rows)
    c = pc[y > 0]
    n = np.bincount(c, minlength=len(GROUPS))
    n5 = np.bincount(pc[y >= 2021], minlength=len(GROUPS))
    n25 = np.bincount(pc[y == 2025], minlength=len(GROUPS))
    for g in np.argsort(-n5):
        print(f"{GROUPS[g]:24s} {n[g]:>9,} {n[g] / n.sum():6.1%}   2021-25 {n5[g]:>9,} {n5[g] / n5.sum():6.1%}   2025 {n25[g]:>8,} {n25[g] / n25.sum():6.1%}")


if __name__ == "__main__":
    main()
