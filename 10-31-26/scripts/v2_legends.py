"""Figure legends for the v2 figures -> v2/data/figure_legends.json. Every number is read from the CSV behind the panel.

Usage: python 10-31-26/scripts/v2_legends.py   (from the IMPACT folder)
"""
import csv
import json
import math
import os
import re
import statistics as st

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V = os.path.join(ROOT, "v2", "data")
OLD = os.path.join(ROOT, "data")


def rd(name, base=V):
    return list(csv.DictReader(open(os.path.join(base, name + ".csv"))))


def f(r, k):
    return float(r[k])


def pct(x, d=0):
    return f"{100 * x:.{d}f}%"


def rng(lo, hi, d=0):
    return f"{100 * lo:.{d}f}–{100 * hi:.{d}f}%"


def sg(x, d=1):
    return f"{x:+.{d}f}%".replace("-", "−")


def main():
    # F1
    ab = rd("f1ab_paper_citations_by_year")
    def paper(p):
        r = [x for x in ab if x["pmid"] == p]
        return sum(int(x["citations"]) for x in r if x["status"] == "JIF year") / sum(int(x["citations"]) for x in r)
    pairs = {x["measure"]: x for x in rd("f1d_pairs_summary")}
    n_pairs = int(pairs["jif_counted"]["pairs"])
    c = rd("f1c_age_curve")
    n_res = int(c[0]["papers"])
    e = rd("f1e_citations_per_year")
    n_e = sum(int(x["research_articles"]) for x in e)
    g = {(x["series"], x["month"]): x for x in rd("f1g_credit_by_month")}
    n_rev = int(g[("Reviews", "Jan")]["papers"])
    h = {(x["months"], x["month"]): f(x, "mean_citations") for x in rd("f1h_overall_by_month")}
    F1 = ("Publication month changes how much of a paper's citations the JIF counts, and has much less effect on its citations overall.",
          [("A, B", f"Citations per year through 2025 to two highly cited papers: Hirsch (PNAS, November 2005; PMID 16275915) and Hanahan and Weinberg (Cell, March 2011; PMID 21376230). Dark gray, publication year, which no JIF counts; blue and green, the first and second JIF years; light gray, later years, which no JIF counts. The red bar marks the first 24 months after publication. The two JIF years hold {pct(paper('16275915'), 1)} and {pct(paper('21376230'), 1)} of each paper's citations through 2025."),
           ("C", f"Mean citations per month by months since publication, for {n_res:,} research articles published 2014–19. Bars mark the months a calendar-year JIF counts for a paper published in January (months 12–35) or December (months 1–24), with the mean citations in each window."),
           ("D", f"{n_pairs:,} pairs of a January and a December paper from the same journal, year and article type (research or review), matched within 8% on citations at months 36–71, after both windows compared (at least 20 citations). Boxes, 25th to 75th percentiles; center line, median; whiskers, 5th to 95th percentiles; diamonds, means. December papers receive {pct(f(pairs['jif_counted'], 'dec_over_jan'), 1)} of January papers' JIF-counted citations and {pct(f(pairs['first_24_months'], 'dec_over_jan'), 1)} of their citations in the first 24 months."),
           ("E", f"Mean citations in the first, second and third calendar year after publication, by publication month, for {n_e:,} research articles published 2010–22. A JIF counts the first two years. Percentages, December compared with January."),
           ("F", "Share of reviews and of other citable items published January to March, each year from 2005 to 2024, across 8,505 journals."),
           ("G", f"Citations a JIF would count if the same paper were published in each month, relative to the average month, calculated from the mean citation curves of {n_res:,} research articles and {n_rev:,} reviews published 2014–19. Curves are means, so highly cited papers weigh more, as they do in a JIF. For research articles, January is {100 * (f(g[('Research articles', 'Jan')], 'credit') - 1):+.0f}% and December {100 * (f(g[('Research articles', 'Dec')], 'credit') - 1):+.0f}%.".replace("-", "−")),
           ("H", f"Mean citations in the first 1, 2, 3 and 5 years after publication, by publication month, relative to the average month, for {n_res:,} research articles published 2014–19. Paper age is matched, so every month has had the same time to be cited. At 5 years, December papers have {pct(h[('60', 'Dec')] / h[('60', 'Jan')])} of January papers' citations."),
           ], "June is omitted from all month panels.")

    # F2
    T = rd("fig9_journal_timing", OLD)
    gains = [f(r, "placement_gain") * 100 for r in T]
    n_c = sum(1 for r in T if r["reviews_fdr_q"])
    ff = rd("f2f_one_report_shift")
    last = {r["series"]: r for r in ff if r["months_later"] == "11"}
    gg = rd("f2g_moved_earlier")
    lastg = {}
    for r in gg:
        lastg[r["journal"]] = r
    jif_g = sorted(f(r, "jif_change_pct") for r in lastg.values())
    rep = sorted(f(r, "report_change_pct") for r in lastg.values())
    F2 = ("Journals gain little overall from publication timing, though moving a single large report changes its journal's rate in its biggest year.",
          [("A", f"For {len(T):,} journals with at least 300 citable items in 2014–21: the change in JIF-counted citations from which of a journal's own papers fall in which month, compared with the same papers given shuffled months within each publication year. Median {st.median(gains):+.2f}%; {sum(x >= 2 for x in gains)} journals gain 2% or more and {sum(x <= -2 for x in gains)} lose 2% or more. Values beyond ±10% are shown at the edge.".replace("-0", "−0")),
           ("B", "The same measure for the four largest gains and losses among journals with at least 2,000 items and |z| ≥ 3, and for the reference journals. Lancet appears among the largest losses."),
           ("C", f"Share of reviews against share of other citable items published January to March, 2014–21, for {n_c:,} journals with at least 20 reviews. Dashed line, equal shares. Named journals have the largest differences among those with at least 100 reviews and 100 other items and a significant difference (Fisher's exact test, false discovery rate below 5%). Red, more reviews early; blue, more reviews late. Journals beyond 60% on the x axis are not shown."),
           ("D", "Change in JIF-counted citations if each paper's publication month moved 6 or 9 months later, wrapping within its publication year, with its citations by age unchanged. Top, the four journals with the most reviews published early in C; middle, reference journals; bottom, the four with the most reviews published late. Items published 2014–21."),
           ("E", "Publication month of eight annual reports and guideline series, 2010–22. Dot size and number show mean citations per report in its first 24 months. Red, January to March. No month, PubMed record has no publication month."),
           ("F", f"For each series in E, its report with the most JIF-counted citations, moved 0–11 months later along with its citations. Solid red, the journal's JIF-style rate in the report's biggest JIF year; blue, the mean 24-month rate in that year; dashed, the report's own JIF-counted citations. At 11 months the journal's JIF-style rate changes by {sg(min(f(r, 'jif_change_pct') for r in last.values()))} to {sg(max(f(r, 'jif_change_pct') for r in last.values()))}, and the report's own counted citations by {sg(min(f(r, 'report_change_pct') for r in last.values()))} to {sg(max(f(r, 'report_change_pct') for r in last.values()))}."),
           ("G", f"The same for one paper moved earlier, up to January of its publication year, in the four journals with the largest losses in B. The paper is the one gaining most in JIF-counted citations among each journal's 40 most-cited items published July to December 2014–21. Moved to January, the paper's own counted citations rise {rep[0]:.0f}–{rep[-1]:.0f}% and the journal's JIF-style rate {jif_g[0]:.1f}–{jif_g[-1]:.1f}%."),
           ], "June is omitted from A–D.")

    # F3
    w = rd("fig10_journal_windows", OLD)
    cal = [math.log(f(r, "calendar_effect_jif_vs_neutral")) for r in w]
    sp = [math.log(f(r, "speed_effect_rel_median")) for r in w]
    stab = {(x["cohort"], x["window"]): x for x in rd("f3c_stability")}
    s19 = stab[("2019", "jif")]
    F3 = ("Windows fixed to paper age rank journals much as the JIF does.",
          [("A", f"JIF-style rate for 2022 against citations at months 12–35 for the same citable items from 2020–21, {len(w):,} journals with at least 100 items, on log axes. Dashed line, the median ratio. Red, the six journals with the largest differences among those with at least 500 items; blue, reference journals."),
           ("B", f"Why journals differ between the two windows in A. Blue, the effect of which months a journal publishes in: its JIF-style rate against a month-neutral rate, in which each paper gets the mean of its twelve possible JIF windows (SD {pct(st.pstdev(cal), 1)}). Red, the effect of how fast its papers are cited: months 12–35 against the month-neutral rate, centered on the median (SD {pct(st.pstdev(sp), 1)})."),
           ("C", f"Spearman correlation of journals' rates between one year's papers and the next year's, for journals with at least 50 items in both years. Dashed lines leave out COVID-19 papers, identified by title; the comparison of 2019 with 2020 papers rises from {f(s19, 'spearman_all_papers'):.3f} to {f(s19, 'spearman_without_covid_papers'):.3f} for the JIF-style window."),
           ("D", "Spearman correlation of each window with citations in years 4–6 (months 36–71) to the same papers, per paper and per journal, averaged over papers published 2014–19. The months 12–35 window ends closest to the outcome, which helps it."),
           ], "June is omitted. The key defines each measure; none is Clarivate's JIF.")

    # F4
    t = rd("fig1a_top_paper_share_2024", OLD)
    sh = [f(r, "top_paper_share") for r in t]
    F4 = ("Some journals depend heavily on a single paper.",
          [("A", f"Share of each journal's 2024 citations, to citable items from 2022–23, that went to its single most-cited paper, for {len(t):,} journals with at least 50 citable items and 100 citations. Log scale."),
           ("B", "The same share for each citation year from 2007 to 2025. Line, median journal; shading, the middle 95% of journals (2.5th to 97.5th percentiles)."),
           ("C", "JIF-style rate with and without that year's top paper, for CA Cancer J Clin (high), Cell (at the median) and Nat Commun (low). Percentages, the journal's top-paper share in 2024."),
           ("D", "The eight journals with at least 500 citable items most reliant on one paper in 2024, with that paper's title."),
           ], "")

    # F5
    ov = rd("f5_series_vs_guidelines")[0]
    grid = rd("f5d_grid_journals")
    F5 = ("A few recurring papers and guidelines hold up some journals' rates.",
          [("A", "The 15 most-cited recurring series by lifetime citations. A series is a title that repeats in at least three different years in the same journal, once years, numbers and words such as \"update\" are removed (at least five years for titles of two or three words). Title variants of one report are merged. 3,515 series were found, covering 24,478 papers."),
           ("B", f"The 15 journals whose 24-month rate falls most, at November 2025, when items PubMed tags as guidelines are removed, among 1,847 journals with at least 300 citable items and reference lists for at least half of them. Numbers, the rate before and after. Open circle, Int J Surg with its 15 SCARE, PROCESS and STROCSS papers removed (Figure 6), 12 of which PubMed does not tag as guidelines. Series and guidelines barely overlap: {int(ov['both']):,} items, {pct(f(ov, 'share_of_guidelines_in_a_series'), 1)} of guidelines."),
           ("C", "Share of each journal's JIF-style citations going to recurring series, for the journals in D. Dots, the mean for 2021–25; light bars, the range from 2015 to 2025. The bottom row is the median of the reference journals."),
           ("D", f"24-month rate with all citable items, without guidelines, and without guidelines or series. Journals are the 11 with the largest fall in their 2024 JIF-style rate without guidelines or series (at least 100 citable items and 500 citations), CA Cancer J Clin (below the item minimum, shown as the extreme case) and the reference journals, {len(grid)} in all."),
           ], "")

    # F6
    fam = {x["family"]: x for x in rd("f6_family_citers")}
    a6 = rd("f6a_two_screens")
    one = rd("f6_citations_per_paper")[0]
    F6 = ("Citations to Int J Surg's reporting guidelines come largely from two linked journals.",
          [("A", f"For {len(a6):,} journals with at least 100 citable items and 500 citations: share of 2024 citations from the largest outside citing journal against share going to the single top paper. Dashed lines, medians. Named journals are the top three on the x axis, the top two on the y axis and the top two on both together. Int J Surg alone is high on both."),
           ("B", "Int J Surg's 24-month rate with all citable items, without its 15 SCARE, PROCESS and STROCSS papers, and without citations from Int J Surg Case Rep and Ann Med Surg."),
           ("C", f"Share of lifetime citations from the three largest citing journals, for these guidelines and for the 10 most-cited series (Figure 5A). The largest citing journal is named at right. Int J Surg Case Rep and Ann Med Surg supply {pct(f(fam['SCARE'], 'share_case_rep_and_ann_med_surg'))} of citations to SCARE, {pct(f(fam['PROCESS'], 'share_case_rep_and_ann_med_surg'))} to PROCESS and {pct(f(fam['STROCSS'], 'share_case_rep_and_ann_med_surg'))} to STROCSS."),
           ("D–F", f"Share of citable items citing each guideline, by quarter through 2025, for quarters with at least 15 items. J Surg Case Rep, from another publisher, is the comparison. Dashed line, May 2025, when SCARE 2025 appeared in Premier Journal of Science, outside PubMed, so citations to it are not in these data. {pct(f(one, 'share'))} of Int J Surg Case Rep papers citing these guidelines cite exactly one of them."),
           ], "")

    # F7, F8
    L = rd("f7ab_lift_all_journals")
    lift = [f(r, "lift_from_reviews") for r in L]
    pan = [r for r in rd("journal_panels") if r["figure_set"].startswith("review_lift")]
    F7 = ("Non-research items lift most journals' rates, and the size of the lift varies widely.",
          [("A", f"Lift: the 24-month rate for all citable items over the rate for research articles only, at November 2025, for {len(L):,} journals (at least 200 citable items, 100 research articles and a rate of 1). Median {100 * st.median(lift):+.0f}%. Reference journals are marked. Values beyond the axis are shown at the edge."),
           ("B", "Lift against reviews as a share of citable items. Red, the top three journals, the two nearest the median, the bottom three and Cureus, the second-largest journal after Sci Rep; blue, reference journals. Points above the axis are plotted at 145%, with their value in the label."),
           ("C", f"For those {len(pan) + 1} journals: 24-month rate for all citable items and for research articles only (shading, the lift), above research papers and reviews published per year. Above each pair, the lift at November 2025; in each bar panel, reviews as a share of research papers and reviews in 2023–25."),
           ], "")
    p8 = [x for x in rd("f8_pairs") if x["kind"] == "flagship"]
    F8a = ("Flagship journals and their open-access siblings.",
           [("", f"Six flagships (top) above their main open-access research journal in the same family (bottom). For each journal: 24-month rate for all citable items and for research articles only, above research papers and reviews published per year, as in Figure 7C. Rates in each pair are on separate scales. A rate is drawn once a journal's 24-month window has filled.")], "")
    F8b = ("Society journals and high-volume open-access journals in the same fields.",
           [("", "The four high-volume journals publishing the most reviews in 2023–25 among eight pairs, each below a society journal in the same field. Panels as in Figure 8a; rates in each pair share a scale. Pairs were matched by hand, because the data do not record which journals belong to a society.")], "")

    # F9
    d9 = [r for r in rd("f9_landscape") if r["panel"] == "D"]
    F9 = ("High-volume publishing has reshaped PubMed.",
          [("A", "Citable items per year for the six largest journals by peak year, preprint servers left out."),
           ("B", "Share of all PubMed citable items per year from selected open-access publishers, identified by DOI prefix."),
           ("C", "Reviews as a share of citable items by publisher, for years with at least 500 items. Dashed line, all journals."),
           ("D", "The 10 journals publishing the most reviews in 2023–25, any publisher. Labels, reviews as a share of the journal's citable items and its number of items."),
           ("E–G", "Citable items per year in Nature Portfolio, Cell Press and AAAS journals, stacked by tier."),
           ("H–J", "The same on one scale, to show the publishers' relative size."),
           ], "")

    # F10
    cnt = {x["region"]: x for x in rd("f10c_region_counts")}
    alt = rd("f10alt_citing_regions_by_year")
    ch = lambda y: st.median(f(r, "China") for r in alt if r["citation_year"] == y)  # noqa: E731
    us = lambda y: st.median(f(r, "USA") for r in alt if r["citation_year"] == y)  # noqa: E731
    F10 = ("Journals are cited most from their home region.",
           [("A", "Share of 2024 citations, to citable items from 2022–23, by the country or region of the citing authors, for 11 pairs of society journals based in the US (above) and Europe (below). Each citation is split equally across the countries of its authors; citing papers with no located author are left out."),
            ("B", "24-month rate of each journal in A."),
            ("C", "Share of citations from the USA minus share from Europe, for 10 pairs of flagship journals and 7 pairs of sister journals, citations as in A. Blue, US journal; gold, European journal."),
            ("D", "24-month rate of each journal in C, log scale."),
            ("E", f"The five highest-rate journals of each region. A journal's home region is the one with at least 50% of its authors, not where it is based. Green, share of authors from home; red, share of citing authors from home; triangle and dotted line, the region's share of all citations, the same for every journal in that region. Numbers in brackets, 24-month rate; after each region, its qualifying journals. Journals needed at least 100 citable items, 200 citations, 80% of authors and citers located, and reference lists for at least half of their items. Africa has only {cnt['Africa']['journals']} qualifying journals and Oceania {cnt['Oceania']['journals']}."),
            ], "")
    F10alt = ("Alternative to Figure 10A: where citations to society journals come from, by year.",
              [("", f"Share of citations in each year, to citable items from the two previous years, by the country or region of the citing authors, for the 11 pairs in Figure 10A, 2014–25. Citations are split as in Figure 10A. Years before 2014 are left out because PubMed then recorded only the first author's affiliation. Across these 22 journals the median share from China rose from {pct(ch('2014'))} in 2014 to {pct(ch('2024'))} in 2024, and the median share from the USA fell from {pct(us('2014'))} to {pct(us('2024'))}. Arthritis Rheumatol starts in 2015 because it took that name in 2014. 2025 citations are still arriving.")], "")

    # F11
    a11 = rd("f11a_institutions")
    b11 = {x["region"]: x for x in rd("f11b_regions")}
    c11 = rd("f11c_concentration")
    d11 = rd("f11d_over_representation")
    china = [f(b11["China"], k) for k in ("nature", "science", "cell", "nejm", "lancet")]
    n_big = len(a11)
    with_paper = [1 - f(r, "none") for r in d11]
    F11 = ("Flagship journals draw on a narrow set of institutions, and very long author lists are growing.",
           [("A", f"Share of institution links, 2021–25, in all PubMed journals and in five flagships (Nature, Science, Cell, NEJM, Lancet), for {n_big:,} large institutions, meaning those with at least 1,000 PubMed papers in those years. A link is one institution on one paper; links are used rather than papers because flagship papers list more institutions. Dashed line, equal shares. Dot color, region; dot size, flagship papers. Named institutions are the top ones on both axes together, on the x axis and on the y axis. The bottom row holds {sum(int(r['flagship_papers']) == 0 for r in a11)} institutions with no flagship paper, plotted at a floor value."),
            ("B", f"Each region's share of institution links in all journals (diamonds) and in each flagship (dots). China has {pct(f(b11['China'], 'all_journals'))} of links in all journals and {rng(min(china), max(china))} in each flagship."),
            ("C", f"Share of each journal's links from its top 10, 50 and 100 institutions (filled), against a random draw of the same size from all journals (open, mean of 30 draws). Its top 10 institutions take {rng(min(f(r, 'top_10') for r in c11), max(f(r, 'top_10') for r in c11))}, against {pct(min(f(r, 'expected_top_10') for r in c11))} in a random draw."),
            ("D", f"Share of the {n_big:,} large institutions with at least one paper in each journal in 2021–25 ({rng(min(with_paper), max(with_paper))}), split by the institution's share of that journal's links relative to its share of all links: under 1×, 1–5× and over 5×."),
            ("E", "Share of papers, citations and citations credited to authors (each paper's citations multiplied by its authors) by authors per paper, for biomedical citable items, 2003–2026. Log scale."),
            ("F", "Papers with at least 100 authors per 10,000 biomedical citable items, by year published."),
            ], "In A–D, shares are of links to these large institutions, and region is the country most often given with the institution's name.")

    # F12
    r7 = {x["publisher"]: x for x in rd("fig7c_ranked", OLD)}
    e12 = {x["years_from_retraction"]: x for x in rd("f12e_around_retraction")}
    late = [r for r in rd("f12fg_late_retraction") if int(r["papers"]) >= 100]
    F12 = ("Retracted papers lose most of their citations, but not all of them.",
           [("A, B", "Retracted papers by year published and by year retracted, with Hindawi in red. Retraction dates come from Retraction Watch or a PubMed retraction notice matched by title."),
            ("C", "Retracted papers per 10,000 citable items published 2015–23, for every publisher with at least 20,000 items."),
            ("D", "The 15 journals with the most retractions. Labels, retracted papers as a share of the journal's citable items. Red, Hindawi."),
            ("E", f"Mean citations per paper per year around retraction for {int(e12['0']['papers']):,} papers retracted 2010–19, at least 4 years after publication, so the same papers appear at every point. Controls are up to five papers from the same journal, year and article type with similar citations before retraction. Dots, means; lines, 95% CI; shading, 25th to 75th percentiles. Five years after retraction, papers have {pct(f(e12['5'], 'ratio'))} of their controls' citations."),
            ("F", f"Mean citations per paper by year since publication (year 1, the year published), by the year of retraction, with the same controls. Dashed line, year retracted; bands, 95% CI. Points with fewer than 100 papers are not drawn, and later years hold fewer, older papers. In the 3 years after retraction, papers get {rng(min(f(r, 'after_vs_controls') for r in late), max(f(r, 'after_vs_controls') for r in late))} of their controls' citations, whichever year it came."),
            ], "")

    out = [("F1_publication_month", "Figure 1", F1), ("F2_timing", "Figure 2", F2), ("F3_windows", "Figure 3", F3), ("F4_top_paper", "Figure 4", F4),
           ("F5_recurring_papers", "Figure 5", F5), ("F6_int_j_surg", "Figure 6", F6), ("F7_reviews", "Figure 7", F7), ("F8a_siblings", "Figure 8a", F8a),
           ("F8b_society", "Figure 8b", F8b), ("F9_landscape", "Figure 9", F9), ("F10_geography", "Figure 10", F10), ("F10_alt_citers_over_time", "Figure 10 alternative", F10alt), ("F11_institutions_and_authors", "Figure 11", F11), ("F12_retractions", "Figure 12", F12)]
    def colors(t):
        return re.sub(r"\bred\b", "orange", re.sub(r"\bRed\b", "Orange", t))
    out = [(s, l, (colors(v[0]), [(p, colors(t)) for p, t in v[1]], colors(v[2]))) for s, l, v in out]
    json.dump([{"stem": s, "label": l, "title": v[0], "panels": v[1], "note": v[2]} for s, l, v in out], open(os.path.join(V, "figure_legends.json"), "w"), ensure_ascii=False, indent=1)
    print(len(out), "legends")


if __name__ == "__main__":
    main()
