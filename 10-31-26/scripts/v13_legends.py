"""Legends for v13 -> v13/data/figure_legends.json: the v12 legends with the panel changes of v13_figs.py and "24-month citation rate" throughout.

Usage: python 10-31-26/scripts/v13_legends.py   (from the IMPACT folder, after v13_figs.py)
"""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v13", "data")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def rng(v, pct=True):
    lo, hi = min(v), max(v)
    if pct and round(lo * 100) == round(hi * 100):
        return f"{lo * 100:.0f}%"
    return f"{lo * 100:.0f}–{hi * 100:.0f}%" if pct else f"{lo}–{hi}"


def panels(x):
    return {p: t for p, t in x["panels"]}


def below_two(rows):
    """Share of journals where 'above the dashed line' (rise > review share) matches reviews cited over twice research per item."""
    n = agree = 0
    for r in rows:
        s = float(r["review_share_items"])
        if s == 0:
            continue
        rho = float(r["review_share_citations"]) / s * float(r["rate_all"]) / float(r["rate_research"])
        n += 1
        agree += (float(r["lift_from_reviews"]) > s) == (rho > 2)
    return agree / n


def main():
    out = json.load(open(os.path.join(ROOT, "v12", "data", "figure_legends.json")))
    by = {x["stem"]: x for x in out}

    # Figure 2B
    f2 = by["Fig2_reviews"]
    old = panels(f2)["B"]
    keep = "Named journals are the three furthest above and three furthest below a straight-line fit, among journals in PubMed since at least 2017."
    assert keep in old
    agree = below_two(rd("f7ab_lift_all_journals"))
    f2["panels"] = [[p, t if p != "B" else
                     "That rise against reviews as a share of citable items. Gray dots, journals; dashed line, a rise equal to the review share. "
                     "If reviews were a journal's only non-research items, a journal on the line would have its reviews cited twice as often per item as its research articles; "
                     f"the line puts {agree:.0%} of journals on the correct side of that ratio. "
                     "Named journals are the three furthest above (blue) and three furthest below (orange) a straight-line fit, among journals in PubMed since at least 2017. "
                     "Signal Transduct Target Ther is plotted at 230%. Supplementary Figure S4 shows these six journals."] for p, t in f2["panels"]]

    # Figure 3 takes S3B and S3C
    f3, s3 = by["Fig3_few_papers"], by["S3_reliance_detail"]
    a, s = panels(f3), panels(s3)
    grid = rd("f5d_grid_journals")
    falls = sum(r["why"] == "largest falls" for r in grid)
    f3["panels"] = [
        ["A", a["A"]],
        ["B", s["B"].replace("for the journals in C", "for the journals in G").replace("median of the reference journals", "median of the eight reference journals")],
        ["C", a["B"]],
        ["D", a["C"].replace("with that paper's title and journal. Orange, the paper's share of the rate.", "with the start of that paper's title under each journal. Orange, the paper's share of the rate.")],
        ["E", a["D"]],
        ["F", a["E"]],
        ["G", f"24-month rate with all citable items, without guidelines, and without guidelines or series, for 18 journals: the {falls} with the largest fall in their December 2024 rate "
              "without guidelines or series (at least 100 citable items and 500 citations), CA Cancer J Clin (below the item minimum, shown as the extreme case) "
              "and six reference journals (JAMA, NEJM, Lancet, Nature, Science and Cell)."]]
    assert "with the start of" in f3["panels"][3][1] and "journals in G" in f3["panels"][1][1]
    s3["title"] = "The top paper's share over time."
    s3["panels"] = [["", s["A"]]]

    # Figure 4C points at the series panel, now 3E
    f4 = by["Fig4_int_j_surg"]
    f4["panels"] = [[p, t.replace("Figure 3D)", "Figure 3E)")] for p, t in f4["panels"]]

    # Figure 6
    f6 = by["Fig6_geography"]
    f6["panels"] = [[p, t.replace("based in the US (above) and Europe (below).", "based in the US (above) and Europe (below); each name says which.")
                     .replace("Blue, US journal; yellow, European journal.", "Yellow, European journal; blue, US journal.")] for p, t in f6["panels"]]
    assert "each name says which" in f6["panels"][0][1]

    # S5 without the old panel A
    s5 = by["S5_institutions_and_authors"]
    reg = {r["region"]: r for r in rd("f11b_regions")}
    china = [float(reg["China"][j]) for j in ("nature", "science", "cell", "nejm", "lancet")]
    conc, over = rd("f11c_concentration"), rd("f11d_over_representation")
    n_inst = len(rd("f11a_institutions"))
    ci = rd("s5e_100plus_authors_ci")
    old = panels(s5)
    s5["panels"] = [
        ["A", f"Each region's share of institution links, 2021–25, in all PubMed journals (diamonds) and in each of five flagships (one marker each: Nature, Science, Cell, NEJM, Lancet), "
              f"for {n_inst:,} large institutions, meaning those with at least 1,000 PubMed papers in those years. A link is one institution on one paper; links are used rather than papers "
              f"because flagship papers list more institutions. China has {float(reg['China']['all_journals']) * 100:.0f}% of links in all journals and {rng(china).replace('%', '')}% in each flagship."],
        ["B", "Share of each journal's links from the 10, 50 and 100 institutions with the most links in that journal (filled), against a random draw of the same size from all journals "
              f"(open, mean of 30 draws). The 10 institutions with the most links take {rng([float(r['most_links_10']) for r in conc])} of each journal's links, against "
              f"{rng([float(r['expected_10']) for r in conc])} in a random draw."],
        ["C", old["D"].replace("(43–71%)", f"({rng([1 - float(r['none']) for r in over])})").replace("2,190", f"{n_inst:,}")],
        ["D", old["E"]],
        ["E", old["F"] + f" Band, exact Poisson 95% interval for each year's count ({int(ci[0]['papers_100plus'])} papers in {ci[0]['year']}, {int(ci[-1]['papers_100plus']):,} in {ci[-1]['year']})."]]
    s5["note"] = (s5["note"].replace("In A–D,", "In A–C,").replace("panels A–D count", "panels A–C count")
                  + " Figure 1B shows the institutions behind flagship papers, counted by first author.")
    assert "In A–C," in s5["note"] and "panels A–C" in s5["note"]

    # S6: Hindawi in vermillion
    s6 = by["S6_retractions"]
    s6["panels"] = [[p, t.replace("with Hindawi in light blue.", "with Hindawi in orange.").replace("Light blue, Hindawi.", "Orange, Hindawi.")] for p, t in s6["panels"]]
    assert "Hindawi in orange" in s6["panels"][0][1]

    # S9: the stacks not in Figure 1
    s9 = by["S9_publishers"]
    s9["panels"] = [[p, t] for p, t in s9["panels"] if p != "D–K"] + [
        ["D–F", "Citable items per year at PLOS, Hindawi and Cureus, the three publishers or journal lists not shown in Figure 1F–J, stacked by journal group. Upper plot, its own scale; "
                "lower plot, the one scale of Figure 1F–J. Hindawi is split into its largest journal in 2023–25, the next four and all others. Cureus is one journal, bought by Springer Nature "
                "in December 2022; Wiley bought Hindawi in January 2021."]]

    # One name for the rate everywhere
    for x in out:
        for k in ("title", "note"):
            if x.get(k):
                x[k] = x[k].replace("24-month rate", "24-month citation rate")
        x["panels"] = [[p, t.replace("24-month rate", "24-month citation rate")] for p, t in x["panels"]]
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    for stem in ("Fig2_reviews", "Fig3_few_papers", "S3_reliance_detail", "S5_institutions_and_authors", "S9_publishers"):
        print(stem, json.dumps(by[stem]["panels"], ensure_ascii=False)[:1600], "\n")


if __name__ == "__main__":
    main()
