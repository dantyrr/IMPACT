"""Legends for v6 -> v6/data/figure_legends.json: the v5 legends with a new Figure 1 and Supplementary Figure S9, numbers read from their CSVs.

Usage: python 10-31-26/scripts/v6_legends.py   (from the IMPACT folder)
"""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v6", "data")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def main():
    old = json.load(open(os.path.join(ROOT, "v5", "data", "figure_legends.json")))
    by = {x["stem"]: x for x in old}
    t = {(r["period"], r["journals"]): r for r in rd("f1ab_region_totals")}
    pc = lambda p, j, r: f"{float(t[p, j][r]) * 100:.1f}%"  # noqa: E731
    inst = rd("f1ab_institutions")
    n = {p: sum(r["period"] == p for r in inst) for p in ("2001-2005", "2021-2025")}
    none = {p: sum(r["period"] == p and r["flagship_papers"] == "0" for r in inst) for p in n}
    y = {r["year"]: r for r in rd("f1e_pubmed_by_publisher")}
    a, b = "2001-2005", "2021-2025"
    fig1 = {"stem": "Fig1_landscape", "label": "Figure 1",
            "title": "In two decades, biomedical publishing has shifted toward China and toward high-volume journals, while flagship journals have changed more slowly.",
            "panels": [
                ["A, B", f"Each dot is an institution holding at least 0.01% of all PubMed citable items in that period ({n[a]:,} institutions in 2001–05, {n[b]:,} in 2021–25). Across, its share of all citable items; up, its share of citable items in Nature, Science, Cell, NEJM and Lancet (the flagships). Dot size, flagship papers, on one scale in both panels. Each paper counts once, for its first author's first-named institution, because PubMed kept only that affiliation until about 2014. Institutions with no flagship paper are not drawn ({none[a]:,} and {none[b]:,}). Named, the two institutions in each of the USA, Europe, China and Other Asia with the most flagship papers in 2021–25. Tables, each country's share of papers with a known country: China {pc(a, 'all', 'China')} of all papers and {pc(a, 'flag', 'China')} of flagship papers in 2001–05, {pc(b, 'all', 'China')} and {pc(b, 'flag', 'China')} in 2021–25; USA {pc(a, 'all', 'USA')} and {pc(a, 'flag', 'USA')}, then {pc(b, 'all', 'USA')} and {pc(b, 'flag', 'USA')}."],
                ["C, D", "Each region's share of citable items per year by first author's country, in all PubMed journals (C) and the five flagships (D). End labels give 2025. China includes Hong Kong and Macau."],
                ["E", f"Citable items in PubMed each year by publisher, identified by DOI prefix: {int(y['2005']['total']):,} in 2005 and {int(y['2025']['total']):,} in 2025. Wiley, Springer, BMC and other publishers are in \"all others\"."],
                ["F–I", "Citable items per year at four publishers, stacked by journal group, each on its own scale. Black, the flagship journal; orange, journals carrying the flagship's name; pink, review journals; yellow, the next tier (for MDPI and Frontiers, the next four journals by size in 2023–25); light blue, newer broad journals; blue, the largest high-volume journal; gray, all others. Supplementary Figure S9 shows these and four other publishers on one scale."],
            ], "note": "Citable items are research articles, reviews, case reports and guidelines. Dots are see-through, so overlaps look darker."}
    s9 = {"stem": "S9_publishers", "label": "Supplementary Figure S9", "title": "The largest journals and publishers in PubMed.", "panels": [
        ["A", "Citable items per year for the five largest journals by peak year, preprint servers left out, each in its publisher's color."],
        ["B", "Each publisher's share of all PubMed citable items per year."],
        ["C–J", "Citable items per year at eight publishers, stacked by journal group, colored as in Figure 1F–I. Upper plot, the publisher's own scale; lower plot, one scale for all eight. MDPI, Frontiers and Hindawi are split into the largest journal in 2023–25, the next four and all others. Cell Press, including Heliyon, is part of Elsevier."],
    ], "note": ""}
    out = [fig1]
    for x in old[1:]:
        x = json.loads(json.dumps(x))
        if x["stem"] == "Fig2_reviews":
            for p in x["panels"]:
                if p[0] == "C":
                    assert "Figure 1C" in p[1]
                    p[1] = p[1].replace("Figure 1C", "Figure 1E")
        if x["stem"] == "S5_institutions_and_authors":
            x["note"] += " Unlike Figure 1A and B, panels A–D count every author's institution, which PubMed records only from about 2014, so they cover 2021–25 alone."
        out.append(x)
    out.append(s9)
    txt = json.dumps(out, ensure_ascii=False)
    assert "Lift" not in txt and " lift" not in txt
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(len(out), "legends")
    print(fig1["panels"][0][1])


if __name__ == "__main__":
    main()
