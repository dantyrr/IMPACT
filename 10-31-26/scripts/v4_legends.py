"""Legends for the six-figure set -> v4/data/figure_legends.json, from the v3 legends with panels re-lettered.

Usage: python 10-31-26/scripts/v4_legends.py   (from the IMPACT folder)
"""
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"


def main():
    old = {x["stem"]: x for x in json.load(open(os.path.join(ROOT, "v3", "data", "figure_legends.json")))}
    P = {s: {p: t for p, t in x["panels"]} for s, x in old.items()}
    f1, f2, f4, f5, f7, f9 = (P[k] for k in ("F1_publication_month", "F2_timing", "F4_top_paper", "F5_recurring_papers", "F7_reviews", "F9_landscape"))

    def sub(t, *pairs):
        for a, b in pairs:
            assert a in t, a
            t = t.replace(a, b)
        return t

    out = [
        ("Fig1_timing", "Figure 1", "Publication month changes how much of a paper's citations a JIF-style rate counts, while journals gain little overall and the 24-month rate ranks them the same way.", [
            ("A", f1["C"]), ("B", f1["D"]),
            ("C", sub(f1["E"], ("for the same 4,366,703 research articles", "for the 4,366,703 research articles in A"))),
            ("D", sub(f1["G"], ("calculated from the mean citation curves of 4,366,703 research articles and", "calculated from the mean citation curves of the research articles in A and"))),
            ("E", f2["A"]),
            ("F", sub(f1["I"], ("Orange, the six journals with the largest differences among those with at least 500 items; blue, reference journals.", "Orange, the six journals with the largest differences among those with at least 500 items; blue and named, reference journals."))), ("G", f1["J"]),
            ("H", sub(f2["F"], ("For each series in E, its report", "For each of eight annual reports and guideline series (Supplementary Figure S2E), its report"))),
        ], "June is omitted from A–E and G. No panel uses Clarivate's JIF. The JIF-style rate is used here because the effect depends on calendar years: over its 24 monthly readings, the 24-month rate treats a paper the same whatever its month."),
        ("Fig2_few_papers", "Figure 2", "A few papers, and the recurring reports and guidelines among them, hold up some journals' rates.", [
            ("A", f4["A"]),
            ("B", f4["C"]),
            ("C", f4["D"]),
            ("D", f5["A"]),
            ("E", f5["B"]),
            ("F", "24-month rate with all citable items, without guidelines, and without guidelines or series, for the five journals with the largest fall in their December 2024 rate without guidelines or series (at least 100 citable items and 500 citations). Supplementary Figure S3C shows 20 journals."),
        ], ""),
        ("Fig3_int_j_surg", "Figure 3", old["F6_int_j_surg"]["title"], [(p, t.replace("(Figure 5A)", "(Figure 2D)")) for p, t in old["F6_int_j_surg"]["panels"]], ""),
        ("Fig4_reviews", "Figure 4", old["F7_reviews"]["title"], [
            ("A", f7["A"]),
            ("B", f7["B"] + " Supplementary Figure S5 shows these six journals."),
            ("C", f7["D"]),
            ("D", f7["E"]),
        ], ""),
        ("Fig5_publishing", "Figure 5", old["F9_landscape"]["title"], [(k, f9[k]) for k in "ABCDE"], ""),
        ("Fig6_geography", "Figure 6", old["F10_geography"]["title"], old["F10_geography"]["panels"], old["F10_geography"]["note"]),
        ("S1_publication_month", "Supplementary Figure S1", "Further detail on publication month.", [
            ("A, B", f1["A, B"]),
            ("C", f1["F"]),
            ("D", sub(f1["H"], ("for 4,366,703 research articles published 2014–19", "for the 4,366,703 research articles in Figure 1A"))),
            ("E", f1["K"]),
        ], "June is omitted from C and D. The key defines each rate."),
        ("S2_timing_detail", "Supplementary Figure S2", "Further detail on publication timing.", [
            ("A", sub(f2["B"], ("The same measure", "The measure in Figure 1E"))),
            ("B", f2["C"]),
            ("C", sub(f2["D"], ("most reviews published early in C", "most reviews published early in B"), ("most reviews published late", "most reviews published late"))),
            ("D", sub(f2["G"], ("The same for one paper", "As in Figure 1H, for one paper"), ("largest losses in B", "largest losses in A"))),
            ("E", f2["E"]),
        ], "June is omitted from A–C."),
        ("S3_reliance_detail", "Supplementary Figure S3", "Further detail on reliance on a few papers.", [
            ("A", sub(f4["B"], ("The same share at each December reading", "The top paper's share of the 24-month rate (Figure 2A) at each December reading"))),
            ("B", sub(f5["C"], ("for the journals in D", "for the journals in C"))),
            ("C", f5["D"]),
        ], ""),
        ("S4_nucleic_acids_res", "Supplementary Figure S4", old["F6b_nucleic_acids_res"]["title"], old["F6b_nucleic_acids_res"]["panels"], ""),
        ("S5_outlier_journals", "Supplementary Figure S5", "Rates and papers per year for the six journals named in Figure 4B.", [("", sub(f7["C"], ("For the six journals named in B:", "For the six journals named in Figure 4B:")))], ""),
        ("S6_publisher_tiers", "Supplementary Figure S6", "Publisher tiers.", [("A–C", f9["F–H"]), ("D–F", f9["I–K"])], ""),
        ("S7_institutions_and_authors", "Supplementary Figure S7", old["F11_institutions_and_authors"]["title"], old["F11_institutions_and_authors"]["panels"], old["F11_institutions_and_authors"]["note"]),
        ("S8_retractions", "Supplementary Figure S8", old["F12_retractions"]["title"], old["F12_retractions"]["panels"], old["F12_retractions"]["note"]),
        ("S9_citers_over_time", "Supplementary Figure S9", old["F10_alt_citers_over_time"]["title"], [(p, t.replace("Figure 10A", "Figure 6A")) for p, t in old["F10_alt_citers_over_time"]["panels"]], ""),
        ("S10_citers_absolute", "Supplementary Figure S10", old["F10_alt_citers_absolute"]["title"], [(p, t.replace("Figure 10A", "Figure 6A")) for p, t in old["F10_alt_citers_absolute"]["panels"]], ""),
    ]
    data = [{"stem": s, "label": l, "title": t, "panels": p, "note": n} for s, l, t, p, n in out]
    txt = json.dumps(data, ensure_ascii=False)
    for bad in ("Figure 10", "Figure 11", "Figure 12", "Figure 7", "Figure 8", "Figure 9"):
        assert bad not in txt, bad
    json.dump(data, open(os.path.join(ROOT, "v4", "data", "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(len(data), "legends")


if __name__ == "__main__":
    main()
