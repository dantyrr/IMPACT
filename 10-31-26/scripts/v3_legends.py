"""Figure legends for the v3 figures -> v3/data/figure_legends.json, and replies to the comments on figure_legends_v2.docx ->
v3/data/comment_replies.json. Unchanged legends come from v2; changed numbers are read from the CSV behind each panel.

Usage: python 10-31-26/scripts/v3_legends.py   (from the IMPACT folder)
"""
import csv
import json
import os
import statistics as st

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v3", "data")


def rd(name):
    return list(csv.DictReader(open(os.path.join(V, name + ".csv"))))


def sg(x, d=1):
    return f"{x:+.{d}f}%".replace("-", "−")


def main():
    old = {x["stem"]: x for x in json.load(open(os.path.join(ROOT, "v2", "data", "figure_legends.json")))}
    P = {s: dict((p, t) for p, t in old[s]["panels"]) for s in old}

    # F1
    e = rd("f1e_citations_per_year")
    jan, dec = e[0], e[-1]
    drop = {k: float(dec[k]) / float(jan[k]) - 1 for k in ("year_1", "year_2", "year_3", "rate_24_month")}
    n = sum(int(r["research_articles"]) for r in e)
    pairs = {r["measure"]: r for r in rd("f1d_pairs_summary")}
    j = {(r["cohort"], r["window"]): r for r in rd("f1j_stability")}
    k = {(r["level"], r["window"]): float(r["mean_spearman"]) for r in rd("f1k_prediction")}
    F1 = ("Publication month changes how much of a paper's citations a JIF-style rate counts, while the 24-month rate ranks journals the same way.", [
        ("A, B", P["F1_publication_month"]["A, B"]),
        ("C", f"Mean citations per month by months since publication, for {n:,} research articles published 2014–19. Shading marks the months a calendar-year JIF counts for a paper published in December (months 1–24, yellow) or January (months 12–35, blue), with the mean citations in each window."),
        ("D", f"Mean citations per month for {int(pairs['jif_counted']['pairs']):,} pairs of a January and a December paper from the same journal, year and article type (research or review), matched within 8% on citations at months 36–71 (at least 20 citations), by month since the start of the publication year. Gray, the two calendar years a JIF counts. December papers have {100 * float(pairs['jif_counted']['dec_over_jan']):.0f}% of January papers' citations in those years, and {100 * float(pairs['first_24_months']['dec_over_jan']):.0f}% in each paper's own first 24 months."),
        ("E", f"Mean citations in the first, second and third calendar year after publication, by publication month, and the 24-month rate's citations per year, for the same {n:,} research articles. Each citation in the 24-month rate is weighted by how many of the paper's 24 monthly readings include it. Percentages, December compared with January: {sg(100 * drop['year_1'], 0)} in the first JIF year and {sg(100 * drop['rate_24_month'], 0)} in the 24-month rate."),
        ("F", "Of all reviews published each year, 2005–24, the share published January to March, and the same for all other citable items, across 8,505 journals. The two lines are separate shares: the rest of each group is published April to December. With June omitted, an even spread over the year gives 3 of 11 months, 27% (dotted)."),
        ("G", P["F1_publication_month"]["G"]),
        ("H", P["F1_publication_month"]["H"]),
        ("I", "JIF-style rate for 2022 against the mean of the twelve monthly readings of the 24-month rate in 2022, for 4,748 journals with at least 100 items, on log axes (Spearman ρ = 0.991). The December reading alone equals the JIF-style rate. Dashed line, equal rates. Orange, the six journals with the largest differences among those with at least 500 items; blue, reference journals."),
        ("J", f"Spearman correlation of journals' rates between one year's papers and the next year's, for journals with at least 50 items in both years. Each point is labelled by the first year of the pair, so the point at 2019 compares 2019's papers with 2020's. Dashed lines leave out COVID-19 papers, identified by title; that comparison rises from {float(j[('2019', 'jif')]['spearman_all_papers']):.3f} to {float(j[('2019', 'jif')]['spearman_without_covid_papers']):.3f} for the JIF-style rate and from {float(j[('2019', 'rate24')]['spearman_all_papers']):.3f} to {float(j[('2019', 'rate24')]['spearman_without_covid_papers']):.3f} for the 24-month rate."),
        ("K", f"Spearman correlation of each rate's citations with citations in years 4–6 (months 36–71) to the same papers, per paper and per journal, averaged over papers published 2014–19: {k[('Per paper', 'jif')]:.3f} and {k[('Per journal', 'jif')]:.3f} for the JIF-style rate, {k[('Per paper', 'rate24')]:.3f} and {k[('Per journal', 'rate24')]:.3f} for the 24-month rate."),
    ], "June is omitted from all month panels. No panel uses Clarivate's JIF.")

    # F2
    f = rd("f2f_one_report_shift")
    D = [r for r in f if r["moved_to"] == "Dec"]
    g = {}
    for r in rd("f2g_moved_earlier"):
        g[r["journal"]] = r
    lo, hi = (lambda key, S: (min(float(r[key]) for r in S), max(float(r[key]) for r in S))), None
    a, b = lo("jif_change_pct", D)
    c, d = lo("report_change_pct", D)
    ga, gb = lo("jif_change_pct", g.values())
    gc, gd = lo("report_change_pct", g.values())
    T = P["F2_timing"]
    F2 = ("Journals gain little overall from publication timing, though moving a single large report changes its journal's JIF-style rate in its biggest year.", [
        ("A", T["A"].replace("the change in JIF-counted citations from which of a journal's own papers fall in which month", "the change in citations counted by the JIF-style rate from which of a journal's own papers fall in which month")),
        ("B", T["B"]),
        ("C", T["C"].replace("Orange, more reviews early; blue, more reviews late.", "Blue, more reviews early; yellow, more reviews late.")),
        ("D", T["D"].replace("Change in JIF-counted citations", "Change in citations counted by the JIF-style rate")),
        ("E", T["E"].replace("Orange, January to March.", "Blue, January to March.")),
        ("F", f"For each series in E, its report with the most citations counted by the JIF-style rate, moved to each month of its own year along with its citations. Dot, the actual month; lines are changes from that month. Solid blue, the journal's JIF-style rate in the report's biggest year; orange, the mean 24-month rate in that year; dashed blue, the report's own counted citations. Moved to December, the journal's JIF-style rate changes by {sg(a)} to {abs(b):.1f}% and the report's own counted citations by {sg(c)} to {sg(d)}."),
        ("G", f"The same for one paper moved to earlier months of its year, in the four journals with the largest losses in B. The paper is the one gaining most in counted citations among each journal's 40 most-cited items published July to December 2014–21. Moved to January, the paper's own counted citations rise {gc:.0f}–{gd:.0f}% and the journal's JIF-style rate {ga:.1f}–{gb:.1f}%."),
    ], "June is omitted from A–D. This figure stays on the JIF-style rate because the effect depends on calendar years: over its 24 monthly readings, the 24-month rate treats a paper the same whatever its month.")

    # F4, F5
    T = P["F4_top_paper"]
    F4 = (old["F4_top_paper"]["title"], [
        ("A", "Share of each journal's 24-month rate at December 2024 (citations in 2024 to citable items from 2022–23) that comes from its single most-cited paper, for 5,528 journals with at least 50 citable items and 100 citations. Log scale."),
        ("B", "The same share at each December reading from 2007 to 2025. Line, median journal; shading, the middle 95% of journals (2.5th to 97.5th percentiles)."),
        ("C", "24-month rate at each December with and without that year's top paper, for CA Cancer J Clin (high), Cell (at the median) and Nat Commun (low)."),
        ("D", "The eight journals with at least 500 citable items most reliant on one paper at December 2024, with that paper's title and journal. Orange, the paper's share of the rate."),
    ], "")
    T = P["F5_recurring_papers"]
    F5 = (old["F5_recurring_papers"]["title"], [
        ("A", T["A"]),
        ("B", T["B"].replace(" Open circle, Int J Surg with its 15 SCARE, PROCESS and STROCSS papers removed (Figure 6), 12 of which PubMed does not tag as guidelines.", "")),
        ("C", T["C"].replace("Share of each journal's JIF-style citations going to recurring series", "Share of each journal's December 24-month rate going to recurring series")),
        ("D", T["D"].replace("in their 2024 JIF-style rate", "in their December 2024 24-month rate")),
    ], "")

    # F6, F6b
    T = old["F6_int_j_surg"]
    own = {r["journal"]: float(r["own_journal_share"]) for r in rd("f6b_own_journal_share")}
    y = rd("f6b_nar_by_year")
    tot, nar = sum(int(r["citations"]) for r in y), sum(int(r["from_nucleic_acids_res"]) for r in y)
    F6b = ("Citations to the NCBI database resources series come mostly from outside its own journal.", [
        ("A", "Share of citable items citing the series \"Database resources of the National Center for Biotechnology Information\" (20 papers, Nucleic Acids Res), by quarter from 2010, in Nucleic Acids Res and in the next two largest citing journals, for quarters with at least 15 items. Peaks fall in the fourth and first quarters, around the journal's annual database issue."),
        ("B", f"Share of the series' citations each year that come from Nucleic Acids Res, 2005–25: {100 * float(y[1]['share']):.0f}% in 2006 and {100 * float(y[-1]['share']):.0f}% in 2025."),
        ("C", f"Share of lifetime citations coming from the series' own journal, for the 10 most-cited series and Int J Surg's guidelines. Orange, this series, at {100 * own['Nucleic Acids Res']:.1f}%."),
    ], "")

    # F7
    pr = {r["first"]: r for r in rd("f7de_pair_summary")}
    F7 = ("Non-research items lift most journals' rates, and flagships keep far higher rates than their open-access siblings.", [
        ("A", "Lift: the 24-month rate for all citable items over the rate for research articles only, at November 2025, for 2,533 journals (at least 200 citable items, 100 research articles and a rate of 1). Median +10%. Reference journals are marked, and the highest journal, Signal Transduct Target Ther (+343%), is marked at the edge. Values beyond the axis are shown at the edge."),
        ("B", "Lift against reviews as a share of citable items. Named journals are the three furthest above and three furthest below a straight-line fit, among journals in PubMed since at least 2017. Points above the axis are plotted at 230%, with their value in the label. Corners describe each direction: a high lift means reviews and other non-research items are cited well above the journal's research articles."),
        ("C", "For the six journals named in B: 24-month rate for all citable items and for research articles only (shading, the lift), above research papers and reviews published per year. Above each pair, the lift at November 2025; in each bar panel, reviews as a share of research papers and reviews in 2023–25."),
        ("D", "Six flagships and their main open-access research journal in the same family: 24-month rates for all citable items on one axis, above citable items per year. A rate is drawn once a journal's 24-month window has filled."),
        ("E", "The same for the six high-volume journals publishing the most reviews in 2023–25 among eight pairs, each with a society journal in the same field. The high-volume journal has the higher rate in three of the six pairs. Pairs were matched by hand, because the data do not record which journals belong to a society."),
    ], "")

    # F9
    F9 = (old["F9_landscape"]["title"], [
        ("A", P["F9_landscape"]["A"]),
        ("B", P["F9_landscape"]["B"]),
        ("C", "Reviews per year by publisher."),
        ("D", "Reviews as a share of citable items by publisher, for years with at least 500 items. Dashed line, all journals."),
        ("E", "Reviews per year, 2005–25, for the five journals publishing the most reviews in 2023–25, any publisher."),
        ("F–H", P["F9_landscape"]["E–G"]),
        ("I–K", P["F9_landscape"]["H–J"]),
    ], "")

    # F10 alternative, absolute
    a10 = rd("f10alt_citations_by_region_by_year")
    tot10 = lambda yr, key: sum(float(r[key]) for r in a10 if r["citation_year"] == yr)  # noqa: E731
    F10abs = ("Citations to society journals by region, in numbers.", [
        ("", f"Citations in each year, to citable items from the two previous years, by the country or region of the citing authors, for the 11 pairs in Figure 10A, 2014–25. Each journal has its own scale. Citations are split as in Figure 10A, and citations with no located author are left out. Across these 22 journals, citations from China rose from {tot10('2014', 'China'):,.0f} in 2014 to {tot10('2024', 'China'):,.0f} in 2024, and citations from the USA fell from {tot10('2014', 'USA'):,.0f} to {tot10('2024', 'USA'):,.0f}. Arthritis Rheumatol starts in 2015 because it took that name in 2014. 2025 citations are still arriving."),
    ], "")

    def recolor(t):
        return (t.replace("gold, European journal", "yellow, European journal").replace("with Hindawi in orange", "with Hindawi in light blue")
                 .replace("Orange, Hindawi", "Light blue, Hindawi"))

    def keep(stem, label):
        x = old[stem]
        return {"stem": stem, "label": label, "title": x["title"], "panels": [(p, recolor(t)) for p, t in x["panels"]], "note": recolor(x["note"])}

    def new(stem, label, v):
        return {"stem": stem, "label": label, "title": v[0], "panels": v[1], "note": v[2]}

    out = [new("F1_publication_month", "Figure 1", F1), new("F2_timing", "Figure 2", F2), new("F4_top_paper", "Figure 4", F4), new("F5_recurring_papers", "Figure 5", F5),
           keep("F6_int_j_surg", "Figure 6"), new("F6b_nucleic_acids_res", "Figure 6b", F6b), new("F7_reviews", "Figure 7", F7), new("F9_landscape", "Figure 9", F9),
           keep("F10_geography", "Figure 10"), keep("F11_institutions_and_authors", "Figure 11"), keep("F12_retractions", "Figure 12"),
           {**keep("F10_alt_citers_over_time", "Supplementary Figure S1"), "title": "Where citations to society journals come from, by year."},
           new("F10_alt_citers_absolute", "Supplementary Figure S2", F10abs)]
    json.dump(out, open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(len(out), "legends")


if __name__ == "__main__":
    main()
