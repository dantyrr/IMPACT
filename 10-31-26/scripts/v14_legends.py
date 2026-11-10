"""Legends for v14 -> v14/data/figure_legends.json: v13's, with the new Figure 2B, S3 dropped and S4-S9 renumbered S3-S8.

Usage: python 10-31-26/scripts/v14_legends.py   (from the IMPACT folder, after v14_figs.py)
"""
import csv
import json
import os
import re

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v14", "data")
RENAME = {"S4_outlier_journals": "S3_outlier_journals", "S5_institutions_and_authors": "S4_institutions_and_authors", "S6_retractions": "S5_retractions",
          "S7_citers_over_time": "S6_citers_over_time", "S8_citers_absolute": "S7_citers_absolute", "S9_publishers": "S8_publishers"}


def renumber(t):
    """S4-S9 become S3-S8 wherever a supplementary figure is named, as in 'Supplementary Figure S4' or '(S9C)'."""
    return re.sub(r"\bS([4-9])(?=[A-K\s,.;:)–]|$)", lambda m: f"S{int(m.group(1)) - 1}", t)


def main():
    out = json.load(open(os.path.join(ROOT, "v13", "data", "figure_legends.json")))
    out = [x for x in out if x["stem"] != "S3_reliance_detail"]
    g = next(csv.DictReader(open(os.path.join(V, "f2b_sd_groups.csv"))))
    for x in out:
        if x["stem"] == "Fig2_reviews":
            x["panels"] = [[p, t if p != "B" else
                            "That rise against reviews as a share of citable items. Dashed line, a rise equal to the review share. If reviews were a journal's only non-research items, "
                            "a journal on the line would have its reviews cited twice as often per item as its research articles; the line puts 93% of journals on the correct side of "
                            f"that ratio. A straight-line fit is almost the same line (slope {float(g['fit_slope']):.2f}, intercept {float(g['fit_intercept']) * 100:.1f}%). ".replace("intercept -", "intercept −")
                            + f"Blue and orange, the {int(g['above_1sd'])} and {int(g['below_1sd'])} journals whose height above the line is more than 1 SD "
                            f"({float(g['sd']) * 100:.0f} points) above or below the mean height ({float(g['mean_rise_minus_share']) * 100:+.1f} points). "
                            "Named: the reference journals (black outline) and the three journals furthest above and three furthest below the straight-line fit, "
                            "among journals in PubMed since at least 2017. Signal Transduct Target Ther is plotted at 230%. Supplementary Figure S4 shows these six journals."]
                           for p, t in x["panels"]]
            assert "1 SD" in x["panels"][1][1]
        x["stem"] = RENAME.get(x["stem"], x["stem"])
        x["label"] = renumber(x["label"])
        x["panels"] = [[p, renumber(t)] for p, t in x["panels"]]
        if x.get("note"):
            x["note"] = renumber(x["note"])
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    for x in out:
        hits = re.findall(r"S\d[A-K]?\b", " ".join(t for _, t in x["panels"]) + " " + (x.get("note") or ""))
        print(x["label"], x["stem"], sorted(set(hits)))


if __name__ == "__main__":
    main()
