"""Legends for the v5 order -> v5/data/figure_legends.json, from the v4 legends, with the new Figures 1 and 2 read from their CSVs.

Usage: python 10-31-26/scripts/v5_legends.py   (from the IMPACT folder)
"""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v5", "data")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def main():
    old = {x["stem"]: x for x in json.load(open(os.path.join(ROOT, "v4", "data", "figure_legends.json")))}
    P = {s: {p: t for p, t in x["panels"]} for s, x in old.items()}

    def sub(t, *pairs):
        for a, b in pairs:
            assert a in t, a
            t = t.replace(a, b)
        return t

    y = {r["year"]: r for r in rd("f1a_pubmed_by_publisher")}
    t05, t25 = int(y["2005"]["total"]), int(y["2025"]["total"])
    r4 = P["Fig4_reviews"]
    s4 = P["S4_nucleic_acids_res"]
    f5 = P["Fig5_publishing"]
    f1 = P["Fig1_timing"]
    out = [
        ("Fig1_publishing", "Figure 1", "Open-access and high-volume publishing have reshaped PubMed.", [
            ("A", f"Citable items (research articles, reviews, case reports and guidelines) in PubMed each year, stacked by publisher, identified by DOI prefix: {t05:,} in 2005 and {t25:,} in 2025. Wiley, Springer, BMC and other publishers are in \"all other publishers\"."),
            ("B", "Citable items per year for the five largest journals by peak year, preprint servers left out, each in its publisher's color."),
            ("C", "Each publisher's share of all PubMed citable items per year."),
            ("D–K", "Citable items per year at eight publishers, stacked by journal group. Black, the flagship journal; a publisher's other groups are tints of its color. Upper plot, the publisher's own scale; lower plot, one scale for all eight. MDPI, Frontiers and Hindawi are split into the largest journal in 2023–25, the next four and all others. Cell Press, including Heliyon, is part of Elsevier."),
        ], "Each publisher has the same color in every panel."),
        ("Fig2_reviews", "Figure 2", "Non-research items raise most journals' rates, and flagships keep far higher rates than their open-access siblings.", [
            ("A", "How much higher the 24-month rate is for all citable items than for research articles only, at November 2025, for 2,533 journals (at least 200 citable items, 100 research articles and a rate of 1). Median +10%. Reference journals are marked, and the highest journal, Signal Transduct Target Ther (+343%), is marked at the edge. Values beyond the axis are shown at the edge."),
            ("B", "That rise against reviews as a share of citable items. Named journals are the three furthest above and three furthest below a straight-line fit, among journals in PubMed since at least 2017. Signal Transduct Target Ther is plotted at 230%. Corners describe each direction: a high rise means reviews and other non-research items are cited well above the journal's research articles. Supplementary Figure S4 shows these six journals."),
            ("C", "Reviews per year for the publishers in Figure 1C."),
            ("D", "Reviews as a share of citable items, for years with at least 500 items. Black, all journals."),
            ("E", "Reviews per year for each publisher's journal with the most reviews in 2023–25, in the publisher's color."),
            ("F", "Six flagships and their main open-access research journal in the same family. Above, 24-month rates for all citable items (solid) and research articles only (dashed). Below, research papers (dark) and reviews (light) per year. A rate is drawn once a journal's 24-month window has filled."),
            ("G", "The same for the six high-volume journals publishing the most reviews in 2023–25 among eight pairs, each with a society journal in the same field. The high-volume journal has the higher rate in three of the six pairs. Pairs were matched by hand, because the data do not record which journals belong to a society."),
        ], ""),
        ("Fig3_few_papers", "Figure 3", old["Fig2_few_papers"]["title"], old["Fig2_few_papers"]["panels"], ""),
        ("Fig4_int_j_surg", "Figure 4", "Citations to Int J Surg's reporting guidelines come largely from two linked journals, unlike other recurring series.", [(p, t.replace("(Figure 2D)", "(Figure 3D)")) for p, t in old["Fig3_int_j_surg"]["panels"]] + [
            ("G", sub(s4["A"], ("Peaks fall in the fourth and first quarters, around the journal's annual database issue.", "Peaks fall in the fourth and first quarters, around the journal's annual database issue."))),
            ("H", s4["B"]),
            ("I", s4["C"]),
        ], ""),
        ("Fig5_timing", "Figure 5", old["Fig1_timing"]["title"], [(p, sub(t, ("blue and named, reference journals", "blue, reference journals")) if p == "F" else t) for p, t in old["Fig1_timing"]["panels"]], old["Fig1_timing"]["note"]),
        ("Fig6_geography", "Figure 6", old["Fig6_geography"]["title"], old["Fig6_geography"]["panels"], old["Fig6_geography"]["note"]),
        ("S1_publication_month", "Supplementary Figure S1", old["S1_publication_month"]["title"], [(p, t.replace("Figure 1A", "Figure 5A")) for p, t in old["S1_publication_month"]["panels"]], old["S1_publication_month"]["note"]),
        ("S2_timing_detail", "Supplementary Figure S2", old["S2_timing_detail"]["title"], [(p, t.replace("Figure 1E", "Figure 5E").replace("Figure 1H", "Figure 5H")) for p, t in old["S2_timing_detail"]["panels"]], old["S2_timing_detail"]["note"]),
        ("S3_reliance_detail", "Supplementary Figure S3", old["S3_reliance_detail"]["title"], [(p, t.replace("Figure 2A", "Figure 3A").replace("light bars, the range", "bars, the range")) for p, t in old["S3_reliance_detail"]["panels"]], ""),
        ("S4_outlier_journals", "Supplementary Figure S4", "Rates and papers per year for the six journals named in Figure 2B.", [("", "For the six journals named in Figure 2B: 24-month rate for all citable items and for research articles only (shading, the difference), above research papers and reviews published per year. Above each pair, the rise at November 2025; in each bar panel, reviews as a share of research papers and reviews in 2023–25.")], ""),
        ("S5_institutions_and_authors", "Supplementary Figure S5", old["S7_institutions_and_authors"]["title"], old["S7_institutions_and_authors"]["panels"], old["S7_institutions_and_authors"]["note"]),
        ("S6_retractions", "Supplementary Figure S6", old["S8_retractions"]["title"], old["S8_retractions"]["panels"], old["S8_retractions"]["note"]),
        ("S7_citers_over_time", "Supplementary Figure S7", old["S9_citers_over_time"]["title"], old["S9_citers_over_time"]["panels"], ""),
        ("S8_citers_absolute", "Supplementary Figure S8", old["S10_citers_absolute"]["title"], old["S10_citers_absolute"]["panels"], ""),
    ]
    data = [{"stem": s, "label": l, "title": t, "panels": p, "note": n} for s, l, t, p, n in out]
    txt = json.dumps(data, ensure_ascii=False)
    assert "Lift" not in txt and " lift" not in txt
    json.dump(data, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(len(data), "legends", t05, t25)


if __name__ == "__main__":
    main()
