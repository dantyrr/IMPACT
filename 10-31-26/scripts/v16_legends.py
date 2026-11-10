"""Legends for v16 -> v16/data/figure_legends.json: v15's, renumbered to follow manuscript v3, with S1 (institutions on papers),
S3 (panels reordered) and S4D (key and right-hand axis) rewritten. The author-count panels are no longer in the paper.

Usage: python 10-31-26/scripts/v16_legends.py   (from the IMPACT folder, after v16_figs.py)
"""
import json
import os
import re

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v16", "data")

MAIN = {"5": "2", "2": "3", "3": "4", "4": "5", "1": "1", "6": "6"}
SUPP = {"S1": "S3", "S2": "S4", "S3": "S5", "S4": "S1", "S5": "S8", "S6": "S6", "S7": "S7", "S8": "S2"}
ORDER = [("Fig1_landscape", "Fig1_landscape"), ("Fig5_timing", "Fig2_timing"), ("Fig2_reviews", "Fig3_reviews"), ("Fig3_few_papers", "Fig4_few_papers"),
         ("Fig4_int_j_surg", "Fig5_int_j_surg"), ("Fig6_geography", "Fig6_geography"), ("S4_institutions_and_authors", "S1_institutions"),
         ("S8_publishers", "S2_publishers"), ("S1_publication_month", "S3_publication_month"), ("S2_timing_detail", "S4_timing_detail"),
         ("S3_outlier_journals", "S5_outlier_journals"), ("S6_citers_over_time", "S6_citers_over_time"), ("S7_citers_absolute", "S7_citers_absolute"),
         ("S5_retractions", "S8_retractions")]


def renum(t):
    t = re.sub(r"Supplementary Figure (S\d)", lambda m: "Supplementary Figure " + SUPP[m.group(1)], t)
    return re.sub(r"(?<!Supplementary )Figure (\d)", lambda m: "Figure " + MAIN[m.group(1)], t)


def main():
    old = {x["stem"]: x for x in json.load(open(os.path.join(ROOT, "v15", "data", "figure_legends.json")))}
    out = []
    for o, n in ORDER:
        x = json.loads(json.dumps(old[o]))
        x["stem"] = n
        num = re.match(r"(Fig|S)(\d)", n)
        x["label"] = f"Figure {num.group(2)}" if num.group(1) == "Fig" else f"Supplementary Figure S{num.group(2)}"
        x["panels"] = [[k, renum(t)] for k, t in x["panels"]]
        x["title"] = renum(x["title"])
        if x.get("note"):
            x["note"] = renum(x["note"])
        p = dict(x["panels"])
        if n == "S1_institutions":
            x["title"] = "Flagship journals draw on a narrow set of institutions."
            x["panels"] = [
                ["A", "Each region's share of institutions on papers, 2021–25, in all PubMed journals (diamonds) and in each of five flagships "
                      "(one marker each: Nature, Science, Cell, NEJM, Lancet), for 2,190 large institutions, meaning those with at least 1,000 PubMed papers "
                      "in those years. Each institution counts once on each paper that lists it, so a paper with three institutions counts three times; "
                      "this is used rather than papers because flagship papers list more institutions. China has 22% in all journals and 3–16% in each flagship."],
                ["B", "Share of each journal's institutions on papers that belong to the 10, 50 and 100 institutions with the most papers in that journal (filled), "
                      "against a random draw of the same size from all journals (open, mean of 30 draws). The 10 institutions with the most papers take 13–19% "
                      "in each journal, against 6% in a random draw."],
                ["C", "Share of the 2,190 large institutions with at least one paper in each journal in 2021–25 (43–71%), split by the institution's share in "
                      "that journal divided by its share in all journals: under 1×, 1–5× and over 5×. An institution's share is its part of all institutions on "
                      "papers, as in A."]]
            x["note"] = ("Region is the country most often given with the institution's name. Unlike Figure 1A and B, these panels count every author's "
                         "institution, which PubMed records only from about 2014, so they cover 2021–25 alone. Names are merged as in Figure 1A and B before "
                         "counting, so a paper naming a university and its hospitals counts once for that university. Figure 1B shows the institutions behind "
                         "flagship papers, counted by first author.")
            assert "D" in p and "E" in p
        if n == "S3_publication_month":
            x["panels"] = [["A, B", p["A, B"]], ["C", p["D"]], ["D", p["E"]], ["E", p["C"]]]
            x["note"] = "June is omitted from C and E. The key defines each rate."
        if n == "S4_timing_detail":
            d = p["D"]
            assert d.startswith("As in Figure 2H, for one paper"), d
            x["panels"] = [[k, (t + " Dashed, the paper's own citations counted by the JIF-style rate (left axis); solid blue and orange, the journal's "
                                "JIF-style rate in that year and its 24-month citation rate averaged over the same year (right axis). Zero is at the same height "
                                "on both axes; black dot, the actual month.") if k == "D" else t] for k, t in x["panels"]]
        out.append(x)
    txt = json.dumps(out, ensure_ascii=False)
    assert "Supplementary Figure S9" not in txt and "links" not in json.dumps([y for y in out if y["stem"] == "S1_institutions"])
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    for x in out:
        print(x["label"], x["stem"], [k for k, _ in x["panels"]])
        for k, t in x["panels"]:
            for m in re.finditer(r"(?:Supplementary )?Figure S?\d[A-Z]?", t):
                print("   ", k, m.group(0))


if __name__ == "__main__":
    main()
