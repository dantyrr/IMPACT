"""Legends for v15 -> v15/data/figure_legends.json: v14's, with Figure 2B's new labels and citation panels in Figure 2 (now A-I).

Usage: python 10-31-26/scripts/v15_legends.py   (from the IMPACT folder, after v15_figs.py)
"""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v15", "data")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def main():
    out = json.load(open(os.path.join(ROOT, "v14", "data", "figure_legends.json")))
    g = rd("f2b_sd_groups")[0]
    n_ext = len(rd("f2b_named_extremes")) + 4          # four of the six fit outliers also pass a cut-off
    pub = {(r["publisher"], r["year"]): int(r["citations_to_reviews"]) for r in rd("f2d_citations_by_publisher")}
    top = {r["journal"]: int(r["citations_to_reviews"]) for r in rd("f2g_citations_top_review_journals") if r["year"] == "2025"}
    for x in out:
        if x["stem"] == "Fig2_reviews":
            p = dict(x["panels"])
            b = ("The change in A against reviews as a share of citable items. Dashed line, a change equal to the review share. If reviews were a journal's only non-research items, "
                 "a journal on the line would have its reviews cited twice as often per item as its research articles; the line puts 93% of journals on the correct side of "
                 f"that ratio. A straight-line fit is almost the same line (slope {float(g['fit_slope']):.2f}, intercept {float(g['fit_intercept']) * 100:.1f}%). ".replace("intercept -", "intercept −")
                 + f"Blue and orange, the {int(g['above_1sd'])} and {int(g['below_1sd'])} journals whose height above the line is more than 1 SD "
                 f"({float(g['sd']) * 100:.0f} points) above or below the mean height ({float(g['mean_rise_minus_share']) * 100:+.1f} points). "
                 f"Named: the reference journals except PLoS One (black outline), the {n_ext} journals with over 58% reviews or a change over +100%, and the three journals furthest above "
                 "and three furthest below the straight-line fit among journals in PubMed since at least 2017 (Supplementary Figure S3 shows these six). "
                 "Signal Transduct Target Ther is plotted at 230%.")
            x["panels"] = [
                ["A", p["A"].replace("How much higher the 24-month citation rate is for all citable items than for research articles only",
                                     "Change in the 24-month citation rate when all citable items are counted rather than research articles only")],
                ["B", b],
                ["C", p["C"]],
                ["D", "Citations received each year by those publishers' reviews, whatever year the reviews were published. In 2025, Elsevier's received "
                      f"{pub[('Elsevier', '2025')] / 1e6:.1f} million and Springer Nature's {pub[('Springer Nature', '2025')] / 1e6:.1f} million."],
                ["E", p["D"]],
                ["F", p["E"]],
                ["G", f"Citations received each year by the reviews in the journals in F. In 2025, Int J Mol Sci received {top['Int J Mol Sci'] / 1000:.0f}k."],
                ["H", p["F"]],
                ["I", p["G"]]]
        if x["stem"] == "S3_outlier_journals":
            x["panels"] = [[k, t.replace("Above each pair, the rise at November 2025", "Above each pair, the change at November 2025")] for k, t in x["panels"]]
            assert any("the change at November" in t for _, t in x["panels"])
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    for x in out:
        if x["stem"] == "Fig2_reviews":
            for k, t in x["panels"]:
                print(k, ":", t[:300])


if __name__ == "__main__":
    main()
