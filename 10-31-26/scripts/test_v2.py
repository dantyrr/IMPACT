"""Checks for the v2 figures. Fast ones run on plain inputs; `-m data` ones read the CSVs the v2 scripts write.
Run from the IMPACT folder: python -m pytest 10-31-26/scripts/test_v2.py -q"""
import csv
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
V2 = os.path.join(os.path.dirname(__file__), "..", "v2", "data")


def rows(name):
    path = os.path.join(V2, name + ".csv")
    if not os.path.exists(path):
        pytest.fail(f"{name}.csv has not been written")
    return list(csv.DictReader(open(path)))


# ---- Task 1: journal rule
def test_stratified_takes_top_middle_bottom():
    from v2_panels import stratified
    items = [(f"j{i}", float(i)) for i in range(101)]
    got = stratified(items)
    assert [g["journal"] for g in got if g["reason"] == "top"] == ["j100", "j99", "j98"]
    assert [g["journal"] for g in got if g["reason"] == "bottom"] == ["j0", "j1", "j2"]
    assert sorted(g["journal"] for g in got if g["reason"] == "median") == ["j50", "j51"] or \
        sorted(g["journal"] for g in got if g["reason"] == "median") == ["j49", "j50"]


def test_stratified_is_repeatable_and_ties_do_not_depend_on_input_order():
    from v2_panels import stratified
    items = [("a", 1.0), ("b", 1.0), ("c", 1.0), ("d", 2.0), ("e", 0.0), ("f", 1.0), ("g", 1.0), ("h", 1.0), ("i", 1.0)]
    assert stratified(items) == stratified(list(reversed(items)))


def test_stratified_adds_reference_journals_once():
    from v2_panels import stratified
    items = [(f"j{i}", float(i)) for i in range(50)]
    got = stratified(items, reference=["j49", "ref"])
    names = [g["journal"] for g in got]
    assert names.count("j49") == 1 and "ref" in names


def test_every_set_holds_the_reference_journals():
    from v2_panels import REFERENCE
    got = rows("journal_panels")
    for s in {r["figure_set"] for r in got}:
        have = {r["journal"] for r in got if r["figure_set"] == s}
        assert set(REFERENCE) <= have, s
        assert 8 <= len(have) <= 16, (s, len(have))


# ---- Task 2: F1
def num(r, k):
    return float(r[k])


def test_f1_all_pairs_match_the_plan():
    r = {x["measure"]: x for x in rows("f1d_pairs_summary")}
    assert 0.74 <= num(r["jif_counted"], "dec_over_jan") <= 0.80
    assert 0.90 <= num(r["first_24_months"], "dec_over_jan") <= 1.04


def test_f1_overall_citations_match_the_plan():
    r = {(x["months"], x["month"]): x for x in rows("f1h_overall_by_month")}
    ratio = num(r[("60", "Dec")], "mean_citations") / num(r[("60", "Jan")], "mean_citations")
    assert 0.91 <= ratio <= 0.95


def test_f1_weighted_credit_is_consistent_with_the_curve():
    credit = {(x["series"], x["month"]): num(x, "credit") for x in rows("f1g_credit_by_month")}
    curve = {int(x["age_months"]): num(x, "mean_citations") for x in rows("f1c_age_curve")}
    from_curve = sum(curve[a] for a in range(1, 25)) / sum(curve[a] for a in range(12, 36))
    direct = credit[("Research articles", "Dec")] / credit[("Research articles", "Jan")]
    assert abs(direct - from_curve) < 0.02
    assert 0.72 <= direct <= 0.80


def test_f1_per_year_values_explain_fig3a():
    r = {x["month"]: x for x in rows("f1e_citations_per_year")}
    assert num(r["Jan"], "year_1") == pytest.approx(3.25, abs=0.03)
    assert num(r["Dec"], "year_1") == pytest.approx(1.80, abs=0.03)
    assert num(r["Dec"], "year_3") == pytest.approx(3.12, abs=0.03)


def test_f1_reviews_track_other_items_every_year():
    for x in rows("f1f_reviews_early_by_year"):
        assert abs(num(x, "reviews_jan_mar") - num(x, "other_jan_mar")) <= 1.5, x


# ---- Task 7: F6
def test_f6_rate_matches_the_site():
    from v2_common import site_rate
    got = {x["month"]: num(x, "rate_all") for x in rows("f6b_rate")}
    for month in ("2019-06", "2022-12", "2025-11"):
        assert got[month] == pytest.approx(site_rate("international-journal-of-surgery-london-england", month), rel=0.01)


def test_f6_family_shares_match_the_plan():
    r = {x["family"]: x for x in rows("f6_family_citers")}
    assert num(r["SCARE"], "share_case_rep_and_ann_med_surg") == pytest.approx(0.91, abs=0.02)
    assert num(r["PROCESS"], "share_case_rep_and_ann_med_surg") == pytest.approx(0.49, abs=0.02)
    assert num(r["STROCSS"], "share_case_rep_and_ann_med_surg") == pytest.approx(0.35, abs=0.02)
    assert num(r["STROCSS"], "share_int_j_surg") == pytest.approx(0.28, abs=0.02)


# ---- Task 3: shift analysis
def toy():
    from v2_common import month_index as mi
    from v2_shift import Journal
    import numpy as np
    items = {1: mi(2015, 1), 2: mi(2015, 1), 3: mi(2016, 12)}
    cited = np.array([1, 1, 1, 3])
    when = np.array([mi(2016, 6), mi(2016, 7), mi(2017, 1), mi(2017, 6)])
    return Journal(items, cited, when)


def test_rolling_rate_by_hand():
    from v2_common import month_index as mi
    from v2_shift import shifted_rates
    r = shifted_rates(toy(), [], 0)
    # reading Dec 2016: citations Jan-Dec 2016 to items Jan 2014-Dec 2015: papers 1 and 2, two citations
    assert r["rolling"][mi(2016, 12)] == pytest.approx(1.0)
    # calendar 2016: citations in 2016 to items from 2014-15
    assert r["jif"][2016] == pytest.approx(1.0)
    # calendar 2017: citations in 2017 to items from 2015-16: papers 1, 2, 3 and two citations
    assert r["jif"][2017] == pytest.approx(2 / 3)


def test_shift_moves_a_paper_and_its_citations_together():
    from v2_common import month_index as mi
    from v2_shift import shifted_rates
    r = shifted_rates(toy(), [3], 1)      # paper 3 moves from Dec 2016 to Jan 2017, its citation to Jul 2017
    assert r["jif"][2017] == pytest.approx(1 / 2)   # paper 3 and its citation leave the 2017 window
    assert r["jif"][2018] == pytest.approx(0.0)
    assert r["total_citations"] == 4


def test_shift_keeps_total_citations():
    from v2_shift import shifted_rates
    base = shifted_rates(toy(), [], 0)["total_citations"]
    for k in (3, 6, 9, 11):
        assert shifted_rates(toy(), [1, 3], k)["total_citations"] == base


@pytest.mark.parametrize("slug", ["ca-a-cancer-journal-for-clinicians", "circulation", "diabetes-care"])
def test_shift_of_zero_reproduces_the_site(slug):
    from v2_common import month_index as mi, site_rate
    from v2_shift import load_journal, shifted_rates, journal_id
    r = shifted_rates(load_journal(journal_id(slug)), [], 0)
    for y, m in ((2019, 6), (2022, 12), (2025, 11)):
        assert r["rolling"][mi(y, m)] == pytest.approx(site_rate(slug, f"{y}-{m:02d}"), rel=0.01)


# ---- Task 4: F2
def test_f2_every_rotation_row_is_finite():
    import math
    for r in rows("f2d_rotated_months"):
        for k in ("jif_change_6_months_pct", "jif_change_9_months_pct"):
            assert math.isfinite(num(r, k)), r


def test_f2_zero_shift_rows_are_zero():
    for r in rows("f2f_one_report_shift"):
        if r["months_later"] == "0":
            assert num(r, "jif_change_pct") == 0 and num(r, "rate_change_pct") == 0
            assert num(r, "report_change_pct") == 0


# ---- Task 5: F3
def test_f3_covid_test_recorded():
    r = {(x["cohort"], x["window"]): x for x in rows("f3c_stability")}
    got = r[("2019", "jif")]
    assert num(got, "spearman_without_covid_papers") > num(got, "spearman_all_papers") + 0.03


# ---- Task 6: F4, F5
def test_f4_panel_c_uses_the_rule():
    names = {x["journal"] for x in rows("f4c_rate_with_without_top_paper")}
    assert names >= {"CA Cancer J Clin", "Nat Commun"} and len(names) == 3


def test_f5_grid_follows_the_rule_and_leaves_out_autophagy():
    from v2_panels import REFERENCE
    got = rows("f5d_grid_journals")
    names = [x["journal"] for x in got]
    assert len(names) == len(set(names)) and "Autophagy" not in names
    assert set(REFERENCE) <= set(names)


def test_f5_all_line_matches_the_site():
    from v2_common import site_rate
    r = {(x["journal"], x["month"]): x for x in rows("f5d_rates")}
    assert num(r[("Circulation", "2025-11")], "rate") == pytest.approx(site_rate("circulation", "2025-11"), rel=0.01)


# ---- Task 12: F12
def test_f12_drop_after_retraction_matches_fig7k():
    r = {x["years_from_retraction"]: x for x in rows("f12e_around_retraction")}
    assert 0.18 <= num(r["5"], "ratio") <= 0.30
    assert num(r["-2"], "ratio") == pytest.approx(1.0, abs=0.1)


def test_f12_no_point_below_the_minimum():
    assert all(int(x["papers_observed"]) >= 100 for x in rows("f12h_by_age"))


# ---- Final review fixes
def test_f1_pairs_are_matched_outside_the_windows_compared():
    got = rows("f1d_pairs_summary")
    assert all(x["matched_on"] == "citations at months 36-71" for x in got)


def test_rotating_months_of_an_even_journal_changes_nothing():
    import numpy as np
    from v2_timing import rotated_change
    rng = np.random.default_rng(0)
    counts = rng.poisson(1.0, (1, 36)).repeat(12, axis=0)      # the same paper in all twelve months
    months = np.arange(1, 13)
    assert rotated_change(counts, months, 6) == pytest.approx(0.0, abs=1e-9)


def test_rotation_hurts_a_january_journal():
    import numpy as np
    from v2_timing import rotated_change
    curve = np.r_[np.linspace(0, 1, 12), np.ones(24)]
    counts = np.tile(curve, (5, 1))
    assert rotated_change(counts, np.ones(5, int), 6) < 0


def test_f2_d_has_no_rate_column():
    assert not any("rate_change" in k for k in rows("f2d_rotated_months")[0])


def test_f11_shares_are_link_shares():
    got = rows("f11a_institutions")
    assert sum(num(x, "share_all") for x in got) == pytest.approx(1.0, abs=0.01)
    assert sum(num(x, "share_flagship") for x in got) == pytest.approx(1.0, abs=0.01)


def test_f11_d_counts_every_institution():
    for x in rows("f11d_over_representation"):
        assert sum(num(x, k) for k in ("none", "under_1x", "from_1_to_5x", "over_5x")) == pytest.approx(1.0, abs=0.002)


def test_f12_g_is_a_ratio_to_controls():
    for x in rows("f12fg_late_retraction"):
        if int(x["papers"]) >= 100:
            assert 0.25 <= num(x, "after_vs_controls") <= 0.6


def test_f6_stops_before_the_2026_reference_gap():
    assert max(num(x, "quarter") for x in rows("f6def_share_citing")) < 2026


# ---- Round 2 of comments
def test_labels_do_not_overlap_in_a_crowd():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from v2_common import place_labels
    fig, ax = plt.subplots(figsize=(3, 3))
    rng = np.random.default_rng(0)
    pts = [(float(a), float(b), f"Journal number {i}") for i, (a, b) in enumerate(rng.uniform(0.35, 0.65, (10, 2)))]
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    boxes = place_labels(ax, pts)
    assert len(boxes) == 10
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not a.overlaps(b)


def test_f2_moved_earlier_starts_at_zero_and_radiology_gains():
    got = rows("f2g_moved_earlier")
    assert all(num(r, "report_change_pct") == 0 for r in got if r["months_earlier"] == "0")
    rad = [r for r in got if r["journal"] == "Radiology"]
    assert max(num(r, "report_change_pct") for r in rad) > 50


def test_f4_middle_journal_is_cell():
    assert "Cell" in {x["journal"] for x in rows("f4c_rate_with_without_top_paper")}


def test_f11_names_eight_to_ten_institutions():
    assert 8 <= len(rows("f11a_labelled")) <= 10


# ---- Round 3 of comments
def test_f4_band_is_the_middle_95_percent():
    for x in rows("f4b_top_paper_share_trend"):
        assert num(x, "p2_5") < num(x, "median") < num(x, "p97_5")


def test_f12_no_longer_plots_before_and_after_panels():
    src = open(os.path.join(os.path.dirname(__file__), "v2_f12.py")).read()
    assert "G  Citations after it" not in src and "F  Citations before it" not in src


def test_f7_names_every_coloured_journal():
    assert len(rows("f7b_named")) >= 14


# ---- Legends
def test_every_figure_has_a_legend_with_no_blanks():
    import json
    d = json.load(open(os.path.join(V2, "figure_legends.json")))
    png = {x[:-4] for x in os.listdir(os.path.join(V2, "..")) if x.startswith("F") and x.endswith(".png")}
    assert {x["stem"] for x in d} == png - {"F13_outside_pubmed", "F10a_us_vs_europe_by_field", "F10b_home_region_gap", "F10c_regions"}
    for x in d:
        for _, text in x["panels"]:
            assert text and "nan" not in text and "{" not in text


def test_legends_name_every_panel_drawn():
    import json
    d = {x["stem"]: "".join(p[0] for p in x["panels"]) for x in json.load(open(os.path.join(V2, "figure_legends.json")))}
    assert all(k in d["F1_publication_month"] for k in "ABCDEFGH")
    assert all(k in d["F2_timing"] for k in "ABCDEFG")
    assert "G" not in d["F12_retractions"]


# ---- Round 4 of comments
def test_f8a_uses_the_branded_siblings():
    got = {x["first"]: x["second"] for x in rows("f8_pairs") if x["kind"] == "flagship"}
    assert got["Nature"] == "Nat Commun" and got["Cell"] == "Cell Rep"


def test_f7_has_sixteen_journals_with_cureus():
    assert "Cureus" in {x["journal"] for x in rows("f7b_named")}
    assert len(rows("f7b_named")) == 16


def test_f5_c_is_a_lollipop_table():
    got = rows("f5c_series_share_summary")
    assert len(got) >= 12 and all(num(x, "low") <= num(x, "mean_2021_25") + 1e-9 for x in got)


def test_rate_weights_add_up_to_24_months():
    from v2_common import rate_weights
    w = rate_weights()
    assert len(w) == 36 and w[0] == 0 and abs(w.sum() - 24) < 1e-9
    assert w[12] == 1 and w[24] == 1 and w[1] == 1 / 12 and w[35] == 1 / 12


def test_v3_figures_use_one_yellow():
    import glob
    import os
    for f in glob.glob(os.path.join(os.path.dirname(__file__), "v3_*.py")):
        assert "#B97F00" not in open(f).read().replace('"#B97F00")', "") or f.endswith("v3_legends.py"), f


def test_first_author_keeps_one_institution_and_reads_old_country_names():
    from v6_first_author import first_part
    key, _, country = first_part("Institute of Biophysics, Chinese Academy of Sciences, Beijing 100101, People's Republic of China.")
    assert key == "chinese academy of sciences" and country == "China"
    assert first_part("Department of Biology, Massachusetts Institute of Technology, Cambridge, MA, USA. x@mit.edu; Howard Hughes Medical Institute, Chevy Chase, MD, USA")[0] == "massachusetts institute of technology"
    assert first_part(None) is None


def test_f1_region_shares_add_up_to_one():
    rows = list(csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "v6", "data", "f1ab_region_totals.csv"))))
    rows += list(csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "v6", "data", "f1cd_region_share.csv"))))
    for r in rows:
        assert abs(sum(float(r[k]) for k in ("USA", "Canada", "Europe", "Rest of world", "Other Asia", "China")) - 1) < 0.001


def test_f1_period_panels_use_one_rule():
    rows = list(csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "v6", "data", "f1ab_institutions.csv"))))
    for p in ("2001-2005", "2021-2025"):
        assert min(float(r["share_all"]) for r in rows if r["period"] == p) >= 0.0001


def test_v7_publisher_groups():
    """Panel E: each group once, the groups add up to every year's total, every color used once."""
    here = os.path.dirname(os.path.abspath(__file__))
    rows = list(csv.DictReader(open(os.path.join(here, "..", "v7", "data", "f1e_pubmed_by_publisher.csv"))))
    names = [k for k in rows[0] if k not in ("year", "total")]
    assert {"Cell Press", "AAAS", "Wiley, Hindawi", "Springer, BMC, Cureus", "Elsevier"} <= set(names) and "Cureus" not in names
    for r in rows:
        assert sum(int(r[k]) for k in names) == int(r["total"])
    assert float(rows[-1]["Other"]) / float(rows[-1]["total"]) < 0.2
    src = open(os.path.join(here, "v7_fig1.py")).read()
    block = src[src.index("PUBLISHERS = ["):src.index("PCT = matplotlib")]
    hexes = re.findall(r'"#[0-9A-F]{6}"', block)
    assert len(hexes) == len(set(hexes)) == 9                     # eight added hues and the light gray; the rest are named Okabe-Ito constants


def test_v7_prefix_table_owners():
    """Bought-in lists sit under their owners, and nothing in All others is above 0.6% of 2021-25 items."""
    here = os.path.dirname(os.path.abspath(__file__))
    rows = {r["doi_prefix"]: r for r in csv.DictReader(open(os.path.join(here, "..", "v7", "data", "publisher_prefixes.csv")))}
    assert rows["10.7759"]["publisher"] == "Springer, BMC, Cureus" and rows["10.1155"]["publisher"] == "Wiley, Hindawi" and rows["10.2147"]["publisher"] == "Taylor & Francis"
    tot = sum(int(r["citable_items_2021_25"]) for r in rows.values())
    assert max(int(r["citable_items_2021_25"]) for k, r in rows.items() if r["publisher"] == "Other" and k != "no DOI") / tot < 0.0065


def test_v7_canada_is_pink():
    here = os.path.dirname(os.path.abspath(__file__))
    assert '("Canada", PURPLE)' in open(os.path.join(here, "v7_fig1.py")).read()
    assert 'PURPLE if n == "Canada"' in open(os.path.join(here, "v7_recolor.py")).read()


def v8_rows(name):
    here = os.path.dirname(os.path.abspath(__file__))
    return list(csv.DictReader(open(os.path.join(here, "..", "v8", "data", name + ".csv"))))


def test_v8_publishers_are_owners():
    """Panel E has one band per owner and adds up; Cureus, Hindawi and Cell Press are inside their owners."""
    rows = v8_rows("f1e_pubmed_by_publisher")
    names = [k for k in rows[0] if k not in ("year", "total")]
    assert {"Elsevier", "Springer Nature", "Wiley"} <= set(names) and not {"Cureus", "Hindawi", "Cell Press", "Nature Portfolio"} & set(names)
    for r in rows:
        assert sum(int(r[k]) for k in names) == int(r["total"])


def test_v8_figure_2_uses_the_seven_owners_with_most_reviews():
    rank = [r["publisher"] for r in v8_rows("f2c_owner_review_rank")]
    shown = list(dict.fromkeys(r["publisher"] for r in v8_rows("f2c_reviews_by_publisher")))
    assert shown == rank[:7] and "Cureus" not in shown and "Hindawi" not in shown


def test_v8_cureus_is_only_a_journal_in_figure_2e():
    rows = v8_rows("f2e_top_review_journals")
    assert {r["journal"] for r in rows if r["publisher"] == "Springer Nature"} == {"Cureus"}


def test_v8_ncbi_series_has_all_editions():
    row = next(r for r in v8_rows("fig2a_recurring_series_merged") if r["series"].startswith("Database resources"))
    assert (row["items"], row["first_year"], row["last_year"]) == ("24", "2003", "2026") and int(row["lifetime_citations"]) > 12000


def test_v8_database_issue_explains_figure_4g():
    t = {r["issue"]: r for r in v8_rows("f4g_citing_by_issue")}
    assert int(t["database issue"]["citing_the_series"]) / sum(int(r["citing_the_series"]) for r in t.values()) > 0.7
    assert float(t["database issue"]["share"]) > 20 * float(t["other papers"]["share"])


def test_v8_legends_state_the_rules():
    import json
    here = os.path.dirname(os.path.abspath(__file__))
    by = {x["stem"]: json.dumps(x, ensure_ascii=False) for x in json.load(open(os.path.join(here, "..", "v8", "data", "figure_legends.json")))}
    assert "One band per current owner" in by["Fig1_landscape"] and "database issue" in by["Fig4_int_j_surg"] and "24 editions" in by["Fig4_int_j_surg"]
    assert "grouped by owner" in by["Fig2_reviews"] and "(20 papers" not in by["Fig4_int_j_surg"]


def test_v9_retraction_rates_go_by_owner():
    here = os.path.dirname(os.path.abspath(__file__))
    rows = {r["publisher"]: r for r in csv.DictReader(open(os.path.join(here, "..", "v9", "data", "fig7c_ranked.csv")))}
    assert not {"Cureus", "BMC", "Dove", "Nature Portfolio", "Springer"} & set(rows)
    assert {"Springer Nature", "Elsevier", "Wiley", "Hindawi"} <= set(rows)
    assert float(rows["Hindawi"]["per_10000"]) == 645.7 and int(rows["Hindawi"]["citable_items"]) == 107964
    assert all(int(r["citable_items"]) >= 20000 for r in rows.values())


def merges():
    here = os.path.dirname(os.path.abspath(__file__))
    return {r["name"]: r["merged_into"] for r in csv.DictReader(open(os.path.join(here, "..", "..", "data", "analysis", "institution_merge.csv")))}


def test_v10_variants_are_merged():
    m = merges()
    assert m["harvard medical school"] == "harvard university" and m["harvard t h chan school of public health"] == "harvard university"
    assert m["duke university medical center"] == "duke university" and m["weill cornell medicine"] == "cornell university"
    assert m["brigham and women s hospital and harvard medical school"] == "brigham and women s hospital"
    assert m["universite de montreal"] == "university of montreal" and m["heidelberg university"] == "university of heidelberg"
    assert m["university of texas m d anderson cancer center"] == "university of texas md anderson cancer center"


def test_v10_different_institutions_stay_apart():
    """Each of these was wrongly joined by an early draft of the rules, or looks as if it could be."""
    m = merges()
    for name in ("baylor college of medicine", "massachusetts general hospital", "johns hopkins hospital", "yale new haven hospital", "university of milan bicocca", "university of maryland baltimore county", "washington university",
                 "miami university", "university of jinan", "university of shizuoka", "new york medical college", "medical college of georgia", "university college london", "imperial college london", "duke nus medical school",
                 "national cancer institute", "second affiliated hospital of zhejiang university", "fudan university shanghai cancer center", "seoul national university hospital", "baylor university medical center", "university of chinese academy of sciences"):
        assert name not in m, name
    assert "washington state university" not in m


def test_v10_no_merge_points_at_a_merged_name():
    m = merges()
    assert not set(m.values()) & set(m)


def test_v10_figure_1_counts():
    here = os.path.dirname(os.path.abspath(__file__))
    rows = list(csv.DictReader(open(os.path.join(here, "..", "v10", "data", "f1ab_institutions.csv"))))
    got = {(r["period"], r["institution"]): r for r in rows}
    assert got["2021-2025", "harvard university"]["flagship_papers"] == "427" and got["2001-2005", "harvard university"]["flagship_papers"] == "428"
    assert ("2021-2025", "harvard medical school") not in got


def merges_v11():
    here = os.path.dirname(os.path.abspath(__file__))
    return {r["name"]: r["merged_into"] for r in csv.DictReader(open(os.path.join(here, "..", "..", "data", "analysis", "institution_merge_v11.csv")))}


def test_v11_hospitals_join_their_universities():
    m = merges_v11()
    for hospital, university in (("massachusetts general hospital", "harvard university"), ("brigham and women s hospital", "harvard university"), ("dana farber cancer institute", "harvard university"), ("johns hopkins hospital", "johns hopkins university"),
                                 ("first affiliated hospital of zhengzhou university", "zhengzhou university"), ("addenbrooke s hospital", "university of cambridge"), ("copenhagen university hospital", "university of copenhagen"),
                                 ("hospital of the university of pennsylvania", "university of pennsylvania"), ("rigshospitalet", "university of copenhagen"), ("peking union medical college hospital", "chinese academy of medical sciences")):
        assert m[hospital] == university, hospital


def test_v11_independent_and_shared_hospitals_stay_apart():
    m = merges_v11()
    for name in ("memorial sloan kettering cancer center", "mayo clinic", "cleveland clinic", "st jude children s research hospital", "cedars sinai medical center", "new york presbyterian hospital", "university of texas md anderson cancer center",
                 "children s hospital", "prince of wales hospital", "queen elizabeth hospital", "national cancer institute", "university hospital"):
        assert name not in m, name


def test_v11_no_merge_points_at_a_merged_name():
    m = merges_v11()
    assert not set(m.values()) & set(m)


def merges_v12():
    here = os.path.dirname(os.path.abspath(__file__))
    return {r["name"]: r["merged_into"] for r in csv.DictReader(open(os.path.join(here, "..", "..", "data", "analysis", "institution_merge_v12.csv")))}


def test_v12_one_institution_one_name():
    m = merges_v12()
    for name, parent in (("wake forest baptist medical center", "wake forest university"), ("wake forest university health sciences", "wake forest university"), ("wake forest baptist health", "wake forest university"), ("atrium health wake forest baptist", "wake forest university"),
                         ("mayo foundation", "mayo clinic"), ("mayo medical school", "mayo clinic"), ("mayo clinic in arizona", "mayo clinic"), ("mayo clinic school of graduate medical education", "mayo clinic"), ("cleveland clinic florida", "cleveland clinic"),
                         ("mcgill university health centre", "mcgill university"), ("erasmus mc university medical center", "erasmus university"), ("university of colorado anschutz medical campus", "university of colorado"), ("universita degli studi di roma la sapienza", "sapienza university of rome"),
                         ("zhongshan hospital fudan university", "fudan university"), ("federal university of sao paulo", "universidade federal de sao paulo"), ("virginia polytechnic institute and state university", "virginia tech"), ("georgia regents university", "augusta university")):
        assert m[name] == parent, name


def test_v12_different_institutions_stay_apart():
    m = merges_v12()
    for name in ("cleveland clinic abu dhabi", "duke nus medical school", "duke kunshan university", "monash university malaysia", "university of colorado boulder", "michigan state university", "baylor university", "virginia tech wake forest university", "washington university", "university of washington",
                 "miami university", "university of jinan", "memorial sloan kettering cancer center", "university of texas md anderson cancer center", "new york presbyterian hospital", "institute of postgraduate medical education and research", "anhui science and technology university",
                 "texas a and m university kingsville", "chinese academy of medical sciences"):
        assert name not in m, name
    assert m["mayo hospital"] == "king edward medical university"


def test_v12_no_merge_points_at_a_merged_name():
    m = merges_v12()
    assert not set(m.values()) & set(m)
