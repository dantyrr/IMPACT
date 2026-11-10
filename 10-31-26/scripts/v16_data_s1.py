"""Data S1 for the Science submission: the data behind each figure panel of v16, one sheet per panel or group of panels,
with a Contents sheet. Reads v16/data (and, for panels drawn from them, the older 10-31-26/data files), changes no values.

Usage: python 10-31-26/scripts/v16_data_s1.py "<out.xlsx>"   (from the IMPACT folder, after v16_data_s1_extra.py)
"""
import csv
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

ROOT = "/Users/dtyrrell/Projects/IMPACT/10-31-26"
V16, OLD = os.path.join(ROOT, "v16", "data"), os.path.join(ROOT, "data")

# sheet, panels, what the sheet holds, source file(s); a source is (dir, file, row filter or None, header renames or None)
S = lambda f, keep=None, ren=None: (V16, f, keep, ren)  # noqa: E731
O = lambda f, keep=None, ren=None: (OLD, f, keep, ren)  # noqa: E731
LINKS = {"links": "institutions_on_papers", "most_links_10": "share_top_10", "most_links_50": "share_top_50", "most_links_100": "share_top_100",
         "expected_10": "random_draw_10", "expected_50": "random_draw_50", "expected_100": "random_draw_100"}
SHEETS = [
    ("Fig1AB_institutions", "Fig. 1A, B", "Each institution's share of all and of flagship citable items, by period (first author's first-named institution).", [S("f1ab_institutions.csv")]),
    ("Fig1AB_country_tables", "Fig. 1A, B", "Country shares of all and of flagship papers shown in the tables.", [S("f1ab_region_totals.csv")]),
    ("Fig1CD_region_share", "Fig. 1C, D", "Each region's share of citable items per year, all journals and the five flagships.", [S("f1cd_region_share.csv")]),
    ("Fig1E_publishers", "Fig. 1E", "Citable items per year by publisher (current owner).", [S("f1e_pubmed_by_publisher.csv")]),
    ("Fig1FJ_publisher_groups", "Fig. 1F to J", "Citable items per year at five publishers, by journal group.", [S("f1fj_publisher_groups.csv")]),
    ("Fig2A_age_curve", "Fig. 2A", "Mean citations per month by months since publication, research articles 2014–19.", [S("f1c_age_curve.csv")]),
    ("Fig2B_matched_pairs", "Fig. 2B", "Mean citations per month for matched January and December papers, by month since the start of the publication year.", [S("f1d_pairs_by_month.csv")]),
    ("Fig2B_pairs_summary", "Fig. 2B", "Summary of the matched pairs.", [S("f1d_pairs_summary.csv")]),
    ("Fig2C_calendar_years", "Fig. 2C", "Mean citations in each calendar year after publication and in the 24-month rate, by publication month.", [S("f1e_citations_per_year.csv")]),
    ("Fig2D_credit_by_month", "Fig. 2D", "Citations a JIF would count by publication month, relative to the average month.", [S("f1g_credit_by_month.csv")]),
    ("Fig2E_figS4B_journals", "Fig. 2E; fig. S4A, B", "Per journal: change from the months of its papers against shuffled months (z), and shares published January to March.", [O("fig9_journal_timing.csv")]),
    ("Fig2F_all_journals", "Fig. 2F", "JIF-style rate for 2022 and the mean of 2022's twelve 24-month rates, every journal plotted.", [S("ds1_fig2f_all_journals.csv")]),
    ("Fig2F_labelled", "Fig. 2F", "The labelled journals.", [S("f1i_jif_style_vs_24_month.csv")]),
    ("Fig2G_stability", "Fig. 2G", "Spearman correlation of journals' rates between consecutive years' papers, with and without COVID-19 papers.", [S("f1j_stability.csv")]),
    ("Fig2H_report_moves", "Fig. 2H", "Changes in rates when each series' top report moves to each month of its year.", [S("f2f_one_report_shift.csv")]),
    ("Fig2H_figS4E_reports", "Fig. 2H; fig. S4E", "The reports of the eight annual series, with publication month and citations.", [O("fig9fg_annual_report_papers.csv")]),
    ("Fig3AB_review_lift", "Fig. 3A, B", "Per journal: rate with all citable items, research-only rate, the change, and review share.", [S("f7ab_lift_all_journals.csv")]),
    ("Fig3B_named", "Fig. 3B", "Named journals and the 1 SD bands.", [S("f2b_named_extremes.csv"), S("f7b_named.csv"), S("f2b_sd_groups.csv")]),
    ("Fig3C_reviews_by_publisher", "Fig. 3C", "Reviews per year by publisher.", [S("f2c_reviews_by_publisher.csv")]),
    ("Fig3D_review_citations", "Fig. 3D", "Citations received each year by each publisher's reviews.", [S("f2d_citations_by_publisher.csv")]),
    ("Fig3E_review_share", "Fig. 3E", "Reviews as a share of citable items, by publisher and year.", [S("f2d_review_share.csv")]),
    ("Fig3F_top_review_journals", "Fig. 3F", "Reviews per year in each publisher's journal with the most reviews.", [S("f2e_top_review_journals.csv")]),
    ("Fig3G_top_journal_citations", "Fig. 3G", "Citations received each year by the reviews in those journals.", [S("f2g_citations_top_review_journals.csv")]),
    ("Fig3HI_figS5_rates", "Fig. 3H, I; fig. S5", "Monthly 24-month rates, all citable items and research only, for each journal drawn.", [S("ds1_pair_rates.csv")]),
    ("Fig3HI_figS5_items", "Fig. 3H, I; fig. S5", "Research articles, reviews and citable items per year for each journal drawn.", [S("ds1_pair_items.csv")]),
    ("Fig4A_top_paper_share", "Fig. 4A", "Per journal: share of the December 2024 rate from its most-cited paper.", [O("fig1a_top_paper_share_2024.csv")]),
    ("Fig4B_series_share", "Fig. 4B", "Share of each journal's December rate going to recurring series, by year, and its summary.", [S("f5c_series_share.csv"), S("f5c_series_share_summary.csv")]),
    ("Fig4C_with_without_top", "Fig. 4C", "December rates with and without that year's top paper.", [S("f4c_rate_with_without_top_paper.csv")]),
    ("Fig4D_most_concentrated", "Fig. 4D", "The journals most reliant on one paper.", [S("f4d_most_concentrated.csv")]),
    ("Fig4E_series", "Fig. 4E", "The most-cited recurring series.", [S("fig2a_recurring_series_merged.csv")]),
    ("Fig4F_guidelines", "Fig. 4F", "Rates with and without guidelines, ranked by the fall (the figure shows the first 15).", [S("fig11_ranked_guidelines.csv")]),
    ("Fig4G_rates", "Fig. 4G", "Monthly rates with all citable items, without guidelines, and without guidelines or series, and why each journal is shown.", [S("f5d_rates.csv"), S("f5d_grid_journals.csv")]),
    ("Fig5A_two_screens", "Fig. 5A", "Per journal: share from the largest outside citing journal and share to the top paper.", [S("f6a_two_screens.csv")]),
    ("Fig5B_int_j_surg_rate", "Fig. 5B", "Int J Surg's monthly rate with all items, without its guidelines, and without the two citing journals.", [S("f6b_rate.csv")]),
    ("Fig5C_who_cites", "Fig. 5C", "The three largest citing journals of each series.", [S("f6c_who_cites.csv")]),
    ("Fig5DF_share_citing", "Fig. 5D to F", "Share of each journal's citable items citing each guideline, by quarter.", [S("f6def_share_citing.csv"), S("f6_citations_per_paper.csv")]),
    ("Fig5G_nar_share", "Fig. 5G", "Share of citable items citing the NCBI series, by journal and quarter.", [S("f6b_nar_share_citing.csv")]),
    ("Fig5H_nar_by_year", "Fig. 5H", "Share of the NCBI series' citations from Nucleic Acids Res, by year.", [S("f6b_nar_by_year.csv")]),
    ("Fig5I_own_journal", "Fig. 5I", "Share of each series' lifetime citations from its own journal.", [S("f6b_own_journal_share.csv")]),
    ("Fig6A_citing_regions", "Fig. 6A", "Citations to each society journal by citing region.", [S("f10a_alt7a_citing_regions.csv")]),
    ("Fig6B_rates", "Fig. 6B", "24-month rate of each society journal.", [S("f10a_alt7b_rates.csv")]),
    ("Fig6CD_us_vs_europe", "Fig. 6C, D", "Shares from the USA and Europe and rates, for flagship and sister pairs.", [S("f10b_fig13_us_vs_europe.csv")]),
    ("Fig6E_home_region", "Fig. 6E", "The highest-rate journals of each home region, and each region's qualifying journals.", [S("f10c_regional_journals.csv"), S("f10c_region_counts.csv")]),
    ("figS1_large_institutions", "fig. S1A to C", "The 2,190 large institutions, 2021–25.", [S("f11a_institutions.csv")]),
    ("figS1A_regions", "fig. S1A", "Each region's share of institutions on papers, all journals and each flagship.", [S("f11b_regions.csv")]),
    ("figS1B_concentration", "fig. S1B", "Share of institutions on papers from each journal's top 10, 50 and 100 institutions, and from random draws.", [S("f11c_concentration.csv", ren=LINKS)]),
    ("figS1C_over_representation", "fig. S1C", "Large institutions by share in each journal relative to all journals.", [S("f11d_over_representation.csv")]),
    ("figS2A_largest_journals", "fig. S2A", "Citable items per year in the largest journals.", [S("s9a_largest_journals.csv")]),
    ("figS2B_publisher_share", "fig. S2B", "Each publisher's share of citable items per year.", [S("s9b_publisher_share.csv")]),
    ("figS2C_all_others", "fig. S2C", "The largest publishers inside \"all others\".", [S("s9c_largest_of_all_others.csv")]),
    ("figS2DF_publisher_groups", "fig. S2D to F", "Citable items per year at PLOS, Hindawi and Cureus, by journal group.", [S("s9dk_publisher_groups.csv")]),
    ("figS3AB_two_papers", "fig. S3A, B", "Citations per year to the two papers.", [S("f1ab_paper_citations_by_year.csv")]),
    ("figS3C_matched_ages", "fig. S3C", "Citations by publication month at matched ages.", [S("f1h_overall_by_month.csv")]),
    ("figS3D_prediction", "fig. S3D", "Correlation of each rate with later citations.", [S("f1k_prediction.csv")]),
    ("figS3E_reviews_early", "fig. S3E", "Reviews and other citable items published January to March, by year.", [S("f1f_reviews_early_by_year.csv")]),
    ("figS4A_named", "fig. S4A", "The journals shown, with their change and z.", [S("f2b_named_journals.csv")]),
    ("figS4C_months_moved", "fig. S4C", "Change in counted citations if publication months moved 6 or 9 months later.", [S("f2d_rotated_months.csv"), S("f2d_shift_all_items.csv")]),
    ("figS4D_moved_earlier", "fig. S4D", "One paper per journal moved to earlier months.", [S("f2g_moved_earlier.csv")]),
    ("figS4E_annual_reports", "fig. S4E", "Reports of each series by publication month, with mean citations in the first 24 months.", [S("f2e_annual_reports.csv")]),
    ("figS6_citing_share_by_year", "fig. S6", "Share of citations by citing region and year, society journal pairs.", [S("f10alt_citing_regions_by_year.csv")]),
    ("figS7_citations_by_year", "fig. S7", "Citations by citing region and year, society journal pairs.", [S("f10alt_citations_by_region_by_year.csv")]),
    ("figS8ABD_retractions", "fig. S8A, B, D", "Retracted papers by year published and year retracted (A, B) and by journal (D).", [O("fig7_retractions.csv", keep=lambda r: r["panel"] in ("A", "B", "D"))]),
    ("figS8C_by_publisher", "fig. S8C", "Retractions per 10,000 citable items by publisher, and Wiley with Hindawi.", [S("fig7c_ranked.csv"), S("s6c_wiley_with_hindawi.csv")]),
    ("figS8E_around_retraction", "fig. S8E", "Citations per paper per year around retraction, retracted papers and controls.", [S("f12e_around_retraction.csv")]),
    ("figS8F_by_age", "fig. S8F", "Citations per paper by year since publication and year of retraction, with controls.", [S("f12h_by_age.csv"), S("f12fg_late_retraction.csv")]),
]


def num(v):
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def main(out):
    wb = Workbook()
    toc = wb.active
    toc.title = "Contents"
    toc.append(["Data S1. Data behind each figure panel"])
    toc["A1"].font = Font(bold=True, size=12)
    toc.append(["Each sheet holds the values plotted in the panels named, as computed for the figures. Rates are 24-month citation rates "
                "unless named otherwise; shares are fractions (0.25 = 25%). Journal names are NLM abbreviations or titles. Where a sheet "
                "holds more than one table, each table starts with its own header row in bold."])
    toc.append([])
    toc.append(["Sheet", "Figure panels", "Contents", "Rows"])
    for c in toc[4]:
        c.font = Font(bold=True)
    assert len({s[0] for s in SHEETS}) == len(SHEETS)
    for name, panels, what, sources in SHEETS:
        assert len(name) <= 31, name
        ws = wb.create_sheet(name)
        n = 0
        for i, (d, f, keep, ren) in enumerate(sources):
            rows = list(csv.reader(open(os.path.join(d, f), newline="")))
            head, data = rows[0], rows[1:]
            if keep:
                data = [r for r in data if keep(dict(zip(head, r)))]
            if ren:
                head = [ren.get(h, h) for h in head]
            if i:
                ws.append([])
            ws.append(head)
            for c in ws[ws.max_row]:
                c.font = Font(bold=True)
            for r in data:
                ws.append([num(v) for v in r])
            n += len(data)
            assert data, (name, f)
        ws.freeze_panes = "A2"
        for k in range(1, ws.max_column + 1):
            width = max(len(str(c.value or "")) for c in ws[get_column_letter(k)][:200])
            ws.column_dimensions[get_column_letter(k)].width = min(max(width + 2, 8), 48)
        toc.append([name, panels, what, n])
        toc.cell(toc.max_row, 1).hyperlink = f"#'{name}'!A1"
        toc.cell(toc.max_row, 1).font = Font(color="0563C1", underline="single")
    for col, w in zip("ABCD", (30, 22, 100, 8)):
        toc.column_dimensions[col].width = w
    toc["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    toc.merge_cells("A2:D2")
    toc.row_dimensions[2].height = 48
    wb.save(out)
    print("wrote", out, len(SHEETS), "sheets")


if __name__ == "__main__":
    main(sys.argv[1])
