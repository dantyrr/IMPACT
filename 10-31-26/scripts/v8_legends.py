"""Legends for v8 -> v8/data/figure_legends.json: the v7 legends with publishers by owner and the NCBI series in full.

Usage: python 10-31-26/scripts/v8_legends.py   (from the IMPACT folder)
"""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v8", "data")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def panel(x, key):
    return next(p for p in x["panels"] if p[0] == key)


def main():
    old = json.load(open(os.path.join(ROOT, "v7", "data", "figure_legends.json")))
    by = {x["stem"]: x for x in old}
    y = {r["year"]: r for r in rd("f1e_pubmed_by_publisher")}
    pc = lambda year, name: int(y[year][name]) / int(y[year]["total"]) * 100  # noqa: E731
    pre = [r for r in rd("publisher_prefixes") if r["publisher"] == "Other" and r["doi_prefix"] != "no DOI"]
    top = rd("s9c_largest_of_all_others")
    seven = [r["publisher"] for r in rd("f2c_owner_review_rank")][:7]
    issue = {r["issue"]: r for r in rd("f4g_citing_by_issue")}
    citing = sum(int(r["citing_the_series"]) for r in issue.values())
    db, other = issue["database issue"], issue["other papers"]
    nar = {r["citation_year"]: r for r in rd("f6b_nar_by_year")}
    own = next(r for r in rd("f6b_own_journal_share") if "Database resources" in r["series"])

    f1 = by["Fig1_landscape"]
    panel(f1, "E")[1] = (f"Citable items in PubMed each year by publisher, from the DOI prefix: {int(y['2005']['total']):,} in 2005 and {int(y['2025']['total']):,} in 2025. One band per current owner, in every year: Elsevier includes its imprint Cell Press and the Lancet journals; "
                         f"Springer Nature includes Nature Portfolio, Springer, BMC and Cureus, a single journal it bought in December 2022; Wiley includes Hindawi, bought in January 2021; Taylor & Francis includes Dove; Wolters Kluwer includes Medknow. In 2025 Springer Nature held {pc('2025', 'Springer Nature'):.1f}% of items and Elsevier {pc('2025', 'Elsevier'):.1f}%. "
                         f"A society's own DOI prefix stays with the society, even when a commercial house prints the journal. A paper with no DOI takes its journal's publisher where one holds at least 80% of that journal's DOIs. All others, {pc('2005', 'Other'):.0f}% of items in 2005 and {pc('2025', 'Other'):.0f}% in 2025, are {len(pre):,} smaller prefixes, none above {float(top[0]['share']) * 100:.1f}% of items in 2021–25 (Supplementary Figure S9C), "
                         "and papers with no DOI in journals with no clear publisher, which explain most of the larger share in early years.")
    p = next(q for q in f1["panels"] if q[0] == "F–J")
    p[1] = ("Citable items per year at five publishers, stacked by journal group. Upper plots, each publisher's own scale; lower plots, one scale for all five, to compare size. Nature Portfolio and Cell Press sit inside Springer Nature and Elsevier in panel E, and have panels here because each is a family built around a flagship journal. "
            "Cell Press is listed by journal and includes Current Biology, the Trends journals, Heliyon and partner titles. Black, the flagship journal; orange, journals carrying the flagship's name; pink, review journals; yellow, the next tier (for MDPI and Frontiers, the next four journals by size in 2023–25); light blue, newer broad journals; blue, the largest high-volume journal; gray, all others. Supplementary Figure S9 adds PLOS, Hindawi and Cureus.")

    f2 = by["Fig2_reviews"]
    panel(f2, "C")[1] = f"Reviews per year for the seven publishers with the most reviews in 2023–25 ({', '.join(seven[:-1])} and {seven[-1]}), grouped by owner as in Figure 1E."
    panel(f2, "E")[1] = "Reviews per year for each of those publishers' journal with the most reviews in 2023–25, in the publisher's color. Cureus is Springer Nature's journal here and Heliyon is Elsevier's."

    f4 = by["Fig4_int_j_surg"]
    panel(f4, "G")[1] = (f"Share of citable items citing the series \"Database resources of the National Center for Biotechnology Information\" (24 editions, 2003–26, Nucleic Acids Res), by quarter from 2010, in Nucleic Acids Res and in the next two largest citing journals, for quarters with at least 15 items. "
                         f"Each tall spike is the journal's annual database issue, about 180 papers describing databases, many of which build on NCBI resources. Of the journal's {citing} citable items citing the series in 2010–25, {int(db['citing_the_series'])} ({int(db['citing_the_series']) / citing * 100:.0f}%) are in that issue, where {float(db['share']) * 100:.0f}% of items cite it, against {float(other['share']) * 100:.1f}% of the journal's papers outside its database and web server issues. "
                         "Most smaller bumps are its web server issue. Spikes fall in the fourth quarter through 2016 and the first quarter from 2018 because PubMed dates the issue to about November through the 2017 issue and to January after it, which also leaves 2017 without a spike. This reflects the recorded date, not a change in citing.")
    panel(f4, "H")[1] = f"Share of the series' citations each year that come from Nucleic Acids Res, 2005–25: {float(nar['2006']['share']) * 100:.0f}% in 2006 and {float(nar['2025']['share']) * 100:.0f}% in 2025."
    panel(f4, "I")[1] = f"Share of lifetime citations coming from the series' own journal, for the 10 most-cited series and Int J Surg's guidelines. Orange, this series, at {float(own['own_journal_share']) * 100:.1f}%."

    s9 = by["S9_publishers"]
    panel(s9, "A")[1] = "Citable items per year for the five largest journals by peak year, preprint servers left out, each in its own color."
    panel(s9, "B")[1] = "Each publisher's share of all PubMed citable items per year, for the seven publishers in Figure 2C, grouped by owner as in Figure 1E."
    panel(s9, "D–K")[1] = panel(s9, "D–K")[1].replace("Figure 1F–J", "Figure 1F–J")
    txt = json.dumps(old, ensure_ascii=False)
    assert "Lift" not in txt and " lift" not in txt and "(20 papers" not in txt
    json.dump(old, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(panel(f4, "G")[1], "\n", panel(f2, "C")[1], "\n", panel(f4, "H")[1], panel(f4, "I")[1])


if __name__ == "__main__":
    main()
