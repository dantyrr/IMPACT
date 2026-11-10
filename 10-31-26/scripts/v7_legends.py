"""Legends for v7 -> v7/data/figure_legends.json: the v6 legends with Figure 1 and S9 rewritten for the new publisher groups.

Usage: python 10-31-26/scripts/v7_legends.py   (from the IMPACT folder)
"""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v7", "data")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def main():
    old = json.load(open(os.path.join(ROOT, "v6", "data", "figure_legends.json")))
    y = {r["year"]: r for r in rd("f1e_pubmed_by_publisher")}
    share = {k: int(y[k]["Other"]) / int(y[k]["total"]) for k in ("2005", "2025")}
    pre = [r for r in rd("publisher_prefixes") if r["publisher"] == "Other" and r["doi_prefix"] != "no DOI"]
    top = rd("s9c_largest_of_all_others")
    out = json.loads(json.dumps(old))
    fig1, s9 = out[0], out[-1]
    assert fig1["stem"] == "Fig1_landscape" and s9["stem"] == "S9_publishers"
    fig1["panels"][2] = ["E", f"Citable items in PubMed each year by publisher, from the DOI prefix: {int(y['2005']['total']):,} in 2005 and {int(y['2025']['total']):,} in 2025. Imprints and bought-in lists sit under their owner: Springer with BMC and Cureus, Wiley with Hindawi, Taylor & Francis with Dove. Nature Portfolio and Springer are both Springer Nature; Cell Press, split out by journal, is part of Elsevier. A paper with no DOI takes its journal's publisher where one holds at least 80% of that journal's DOIs. All others, {share['2005'] * 100:.0f}% of items in 2005 and {share['2025'] * 100:.0f}% in 2025, are {len(pre):,} smaller prefixes, none above {float(top[0]['share']) * 100:.1f}% of items in 2021–25 (Supplementary Figure S9C), and papers with no DOI in journals with no clear publisher, which explain most of the larger share in early years."]
    fig1["panels"][3] = ["F–J", "Citable items per year at five publishers, stacked by journal group. Upper plots, each publisher's own scale; lower plots, one scale for all five, to compare size. Black, the flagship journal; orange, journals carrying the flagship's name; pink, review journals; yellow, the next tier (for MDPI and Frontiers, the next four journals by size in 2023–25); light blue, newer broad journals; blue, the largest high-volume journal; gray, all others. Supplementary Figure S9 adds PLOS, Hindawi and Cureus."]
    s9["panels"] = [
        ["A", "Citable items per year for the five largest journals by peak year, preprint servers left out, each in its publisher's color."],
        ["B", "Share of all PubMed citable items per year. Elsevier here includes Cell Press; Hindawi (Wiley) and Cureus (Springer Nature) are shown on their own."],
        ["C", f"The twelve largest publishers inside \"all others\" in Figure 1E, as a share of all citable items in 2021–25. Each is one DOI prefix, named from its largest journals; Cold Spring Harbor is mostly bioRxiv."],
        ["D–K", "Citable items per year at eight publishers and journal lists, stacked by journal group, colored as in Figure 1F–J. Upper plot, its own scale; lower plot, one scale for all eight. MDPI, Frontiers and Hindawi are split into the largest journal in 2023–25, the next four and all others. Cell Press includes Current Biology, the Trends journals, Heliyon and partner titles. Cureus is one journal, bought by Springer Nature in December 2022; Wiley bought Hindawi in January 2021."],
    ]
    txt = json.dumps(out, ensure_ascii=False)
    assert "Lift" not in txt and " lift" not in txt
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(len(out), "legends\n", fig1["panels"][2][1])


if __name__ == "__main__":
    main()
