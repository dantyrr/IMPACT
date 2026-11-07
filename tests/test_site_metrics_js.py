"""docs/js/site-metrics.js: the calculations behind the paper's figures on the site."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def run(fn, *args):
    out = subprocess.run(["node", str(ROOT / "tests" / "js" / "site_metrics.js")], input=json.dumps({"fn": fn, "args": list(args)}) + "\n",
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def reading(month, papers, citations):
    return {"month": month, "citable_papers": papers, "citable_citations": citations}


TS = [reading("2020-12", 100, 200), reading("2021-12", 100, 300), reading("2022-12", 100, 400)]


def test_jif_share_counts_two_years_after_publication():
    assert run("jifShare", {"2010": 5, "2011": 10, "2012": 20, "2013": 65}, 2010) == {"counted": 30, "total": 100, "share": 0.3}


def test_jif_share_with_no_citations_is_null():
    assert run("jifShare", {}, 2010)["share"] is None


def test_early_share_leaves_out_june():
    ts = [{"month": "2015-01", "pub_by_type": {"review": 10, "research": 40}}, {"month": "2015-06", "pub_by_type": {"review": 30}},
          {"month": "2015-07", "pub_by_type": {"review": 10, "research": 60}}]
    got = run("earlyShare", ts)[0]
    assert got["reviewsEarly"] == 0.5 and got["otherEarly"] == 0.4 and got["reviews"] == 20


def test_moved_jif_of_zero_months_changes_nothing():
    r = run("movedJif", TS, {"2020-03": 5, "2021-03": 9}, "2019-11", 0, 2021)
    assert r["before"] == r["after"] and r["ownBefore"] == r["ownAfter"]


def test_moved_jif_crossing_the_year_moves_the_window():
    # a December 2019 paper moved 1 month later counts in 2021-22, not 2020-21
    r = run("movedJif", TS, {"2020-12": 10, "2022-06": 4}, "2019-12", 1, 2022)
    assert r["ownBefore"] == 10 and r["ownAfter"] == 14


def test_moved_jif_adjusts_the_journal_rate():
    # In 2021's window at first (items 2019-20). Moved into 2021 it leaves that window: one item and its 5 citations go.
    r = run("movedJif", TS, {"2021-06": 5}, "2020-06", 12, 2021)
    assert r["before"] == 3 and r["after"] == pytest.approx(295 / 99)


def test_moved_jif_earlier_uses_negative_months():
    r = run("movedJif", TS, {"2021-01": 8}, "2019-12", -11, 2021)   # Jan 2019: its citation moves to Feb 2020
    assert r["ownBefore"] == 8 and r["ownAfter"] == 8


def test_moved_jif_with_no_december_reading_is_null():
    assert run("movedJif", TS, {}, "2019-12", 1, 2030) is None


def test_top_paper_series_uses_the_two_previous_years():
    papers = [{"pmid": 1, "y": 2019, "k": "research", "t": "A", "cy": {"2021": 30}}, {"pmid": 2, "y": 2021, "k": "research", "t": "B", "cy": {"2021": 90}},
              {"pmid": 3, "y": 2020, "k": "editorial", "t": "C", "cy": {"2021": 80}}]
    got = {r["year"]: r for r in run("topPaperSeries", papers, TS)}[2021]
    assert got["pmid"] == 1 and got["share"] == 0.1 and got["rate"] == 3 and got["rateWithout"] == pytest.approx(270 / 99)


@pytest.mark.skipif(not (DATA / "papers" / "cell.json").exists(), reason="local data not present")
def test_top_paper_series_matches_the_paper_for_cell():
    papers = json.load(open(DATA / "papers" / "cell.json"))["papers"]
    ts = [e for e in json.load(open(DATA / "journals" / "cell.json"))["timeseries"] if e["month"].endswith("-12")]
    row = next(x for x in run("topPaperSeries", papers, ts) if x["year"] == 2024)
    assert abs(row["share"] - 0.047) < 0.002


def test_lift_with_no_research_is_null():
    assert run("liftAt", {"by_type": {}}) is None


def test_lift():
    assert run("liftAt", {"rolling_if": 3, "by_type": {"research": {"papers": 10, "citations": 20}}}) == 0.5


@pytest.mark.parametrize("country,region", [("USA", "USA"), ("United Kingdom", "Europe"), ("Hong Kong", "China"), ("South Korea", "Other Asia"), ("Brazil", "Rest of world")])
def test_region_of(country, region):
    assert run("regionOf", country) == region


def test_region_shares_sum_to_one_each_year():
    countries = {"USA": {"2015": [10, 6.0]}, "France": {"2015": [4, 2.0], "2016": [1, 1.0]}, "Brazil": {"2015": [2, 2.0]}}
    got = run("regionShares", countries, [2015, 2016])
    assert got["USA"] == [0.6, 0.0] and got["Europe"] == [0.2, 1.0] and got["Rest of world"] == [0.2, 0.0]
    assert sum(got[r][0] for r in got) == pytest.approx(1)


def test_region_shares_year_with_no_data_is_null():
    assert run("regionShares", {"USA": {"2015": [1, 1.0]}}, [2014])["USA"] == [None]


def test_banner_for_a_dated_retraction():
    b = run("retractionBanner", {"y": 2022, "m": 4, "r": ["paper_mill", "image"], "s": "rw", "st": "retracted"})
    assert b["split"] == 2022 and "Retracted April 2022" in b["text"] and "Retraction Watch" in b["text"] and "paper mill" in b["text"]


def test_banner_for_an_undated_retraction_has_no_split():
    b = run("retractionBanner", {"y": None, "m": None, "r": [], "s": "pubmed", "st": "retracted"})
    assert b["split"] is None and b["text"].startswith("Retracted, date not known")


def test_banner_for_a_reinstated_paper_never_says_plain_retracted():
    b = run("retractionBanner", {"y": 2020, "m": 2, "r": [], "s": "rw", "st": "reinstated"})
    assert "later reinstated" in b["text"] and b["split"] is None


def test_no_record_no_banner():
    assert run("retractionBanner", None) is None


def test_before_and_after():
    assert run("beforeAfter", {"2018": 5, "2019": 7, "2020": 9, "2021": 1, "2022": 2}, 2020) == {"before": 12, "during": 9, "after": 3}


def test_rate_without_nothing_keeps_the_rate():
    ts = [{"month": "2020-12", "citable_papers": 10, "citable_citations": 40, "rolling_if": 4}]
    got = run("rateWithout", ts, [], [])
    assert got["rows"][0]["rate"] == 4 and got["missing"] == 0


def test_rate_without_removes_a_paper_in_the_window():
    # reading Dec 2020: items Jan 2018 - Dec 2019, citations Jan - Dec 2020
    ts = [{"month": "2020-12", "citable_papers": 10, "citable_citations": 40, "rolling_if": 4}]
    papers = [{"pmid": 1, "y": 2019, "m": 3, "k": "research", "cm": {"2020-05": 13, "2021-01": 99}}]
    got = run("rateWithout", ts, papers, [1])
    assert got["rows"][0]["rate"] == pytest.approx(27 / 9)


def test_rate_without_leaves_a_paper_outside_the_window():
    ts = [{"month": "2020-12", "citable_papers": 10, "citable_citations": 40, "rolling_if": 4}]
    papers = [{"pmid": 1, "y": 2020, "m": 1, "k": "research", "cm": {"2020-05": 13}}]
    assert run("rateWithout", ts, papers, [1])["rows"][0]["rate"] == 4


def test_rate_without_counts_papers_it_cannot_find():
    assert run("rateWithout", [], [], [5, 6])["missing"] == 2


def test_reason_labels_claim_no_more_than_the_source():
    text = run("retractionBanner", {"y": 2020, "m": 2, "r": ["peer_review", "honest_error"], "s": "rw", "st": "retracted"})["text"]
    assert "concerns about peer review" in text and "reported errors" in text
    assert "fake" not in text and "honest" not in text


def test_uncited_papers_are_still_removed():
    ts = [reading("2020-12", 10, 20)]
    got = run("rateWithout", ts, [{"pmid": 1, "y": 2018, "m": 6}], [1])
    assert (got["removed"], got["missing"]) == (1, 0)
    assert got["rows"][0]["rate"] == pytest.approx(20 / 9)


@pytest.mark.parametrize("pct,phrase", [(99.7, "among the highest"), (0.2, "among the lowest"), (42.4, "higher than 42%")])
def test_rank_phrase_never_says_100_percent(pct, phrase):
    assert run("rankPhrase", pct) == phrase


@pytest.mark.parametrize("month,shares", [(1, [1, 1, 0]), (7, [0.5, 1, 0.5]), (12, [1 / 12, 1, 11 / 12])])
def test_paper_window_is_the_24_months_from_publication(month, shares):
    got = [run("paperWindowShare", 2020, month, y) for y in (2020, 2021, 2022)]
    assert got == pytest.approx(shares) and sum(got) == pytest.approx(2)
    assert run("paperWindowShare", 2020, month, 2019) == 0 and run("paperWindowShare", 2020, month, 2023) == 0


def test_report_months_groups_guidelines_and_series_by_month():
    papers = [
        {"pmid": 1, "y": 2015, "m": 3, "k": "guideline", "cm": {"2015-03": 10, "2017-02": 5, "2017-03": 100}},
        {"pmid": 2, "y": 2016, "m": 3, "k": "research", "cm": {"2016-05": 20}},
        {"pmid": 3, "y": 2016, "m": 0, "k": "guideline"},
        {"pmid": 4, "y": 2016, "m": 3, "k": "research", "cm": {"2016-05": 999}},
        {"pmid": 5, "y": 2005, "m": 3, "k": "guideline", "cm": {"2005-05": 999}},
    ]
    assert run("reportMonths", papers, [2], 2010, 2022) == [{"x": 2, "n": 2, "v": 17.5}, {"x": 12, "n": 1, "v": 0}]


def test_rank_drivers_sorts_by_share_or_lifetime():
    rows = [{"id": 1, "share": 0.5, "p": {"c": 10}}, {"id": 2, "share": 0.2, "p": {"c": 900}},
            {"id": 3, "share": 0.1, "p": {}}, {"id": 4, "share": 0, "p": {"c": 5000}}]
    assert [r["id"] for r in run("rankDrivers", rows, "share", 2)] == [1, 2]
    assert [r["id"] for r in run("rankDrivers", rows, "lifetime", 3)] == [2, 1, 3]


def test_rolling_windows_step_one_year():
    w = run("rollingWindows", 2001, 2025, 5)
    assert len(w) == 21 and w[0] == {"start": 0, "from": 2001, "to": 2005, "label": "2001–05"} and w[-1]["label"] == "2021–25"


def test_window_point_uses_the_five_years_of_that_window():
    p = run("windowPoint", [1, 2, 3, 4, 5, 6], [0, 1, 0, 0, 1, 1], [10, 10, 10, 10, 10, 10], [4, 4, 4, 4, 4, 4], 1, 5)
    assert p == {"papers": 20, "flagship": 3, "x": 0.4, "y": 0.15}


def test_window_point_with_no_flagship_list():
    assert run("windowPoint", [1, 1], [], [2, 2], [1, 1], 0, 2) == {"papers": 2, "flagship": 0, "x": 0.5, "y": 0}


def test_search_ignores_accents_case_and_order():
    names = [["Universite de Lausanne", 50], ["Université de Montréal", 90], ["Stanford University", 200], ["University of Tokyo", 100]]
    assert run("searchInstitutions", names, "montreal", 5) == [1]
    assert run("searchInstitutions", names, "TOKYO univ", 5) == [3]


def test_search_puts_names_starting_with_the_query_first_then_larger():
    names = [["East Stanford Clinic", 500], ["Stanford University", 200], ["Stanford Health", 300]]
    assert run("searchInstitutions", names, "stan", 2) == [2, 1]


def test_search_with_no_query_returns_nothing():
    assert run("searchInstitutions", [["Stanford University", 200]], "  ", 5) == []
