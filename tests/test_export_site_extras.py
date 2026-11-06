"""scripts/export_site_extras.py: small site files from existing analysis files. Skips without the local analysis data."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "data" / "analysis" / "cites.npz").exists(), reason="local analysis data not present")


@pytest.fixture(scope="session")
def retractions(tmp_path_factory):
    from scripts.export_site_extras import export_retractions
    out = tmp_path_factory.mktemp("site")
    return out, export_retractions(str(out))


def shards(out):
    rows = {}
    for f in (out / "retractions").glob("[0-9]*.json"):
        rows.update(json.load(open(f)))
    return rows


def test_every_listed_paper_is_exported_once(retractions):
    out, info = retractions
    assert info["papers"] == 37389 and len(shards(out)) == 37389


def test_a_pmid_sits_in_its_shard(retractions):
    out, _ = retractions
    for f in (out / "retractions").glob("[0-9]*.json"):
        n = int(f.stem)
        assert all(int(p) % 64 == n for p in json.load(open(f)))


def test_reinstated_papers_are_marked(retractions):
    out, _ = retractions
    assert sum(r["st"] == "reinstated" for r in shards(out).values()) >= 21


def test_undated_papers_have_no_date(retractions):
    out, _ = retractions
    rows = shards(out).values()
    assert sum(r["y"] is None for r in rows) == 3602
    assert all(r["m"] is None for r in rows if r["y"] is None)


def test_counts_match_the_matrix(retractions):
    import numpy as np
    out, _ = retractions
    rows = shards(out)
    D = np.load(ROOT / "data" / "analysis" / "cites.npz")
    i = int(np.argmax(D["counts"].sum(axis=1) * np.isin(D["pmid"], [int(p) for p in rows])))
    row = rows[str(int(D["pmid"][i]))]
    assert sum(row["cy"].values()) == int(D["counts"][i].sum())


def test_summary_covers_journals_with_retractions(retractions):
    out, _ = retractions
    s = json.load(open(out / "retractions" / "summary.json"))
    assert s["plos-one"]["retracted"] >= 1000 and sum(s["plos-one"]["pub"].values()) == s["plos-one"]["retracted"]
    assert s["journal-of-healthcare-engineering"]["per10k"] > 100


@pytest.fixture(scope="session")
def measures(tmp_path_factory):
    from scripts.export_site_extras import export_measures
    out = tmp_path_factory.mktemp("m")
    export_measures(str(out))
    return json.load(open(out / "journal_measures.json"))


def test_measures_have_the_expected_journal_counts(measures):
    want = {"top_paper": 5528, "lift": 2533, "outside_journal": 2457, "timing": 4813}
    assert {k: v["n"] for k, v in measures["measures"].items()} == want
    for key, m in measures["measures"].items():
        assert sum(m["counts"]) == m["n"]
        assert 0.97 * m["n"] <= sum(key in j for j in measures["journals"].values()) <= m["n"]    # shared names get no value


def test_measure_values_match_the_paper(measures):
    assert measures["journals"]["international-journal-of-surgery-london-england"]["outside_journal"][0] == pytest.approx(0.3281, abs=1e-3)
    assert measures["journals"]["cell"]["top_paper"][0] == pytest.approx(0.047, abs=1e-3)
    assert 0 <= measures["journals"]["cell"]["top_paper"][1] <= 100


@pytest.fixture(scope="session")
def citers(tmp_path_factory):
    from scripts.export_site_extras import export_citers
    out = tmp_path_factory.mktemp("c")
    return out, export_citers(str(out))


def test_citers_match_the_paper(citers):
    out, _ = citers
    c = json.load(open(out / "citers" / "circulation.json"))
    assert c["countries"]["USA"] == pytest.approx(0.3057, abs=0.005)
    assert sum(c["countries"].values()) == pytest.approx(1, abs=0.02)
    i = json.load(open(out / "citers" / "international-journal-of-surgery-london-england.json"))
    assert i["journals"][0]["name"] == "Int J Surg Case Rep" and i["journals"][0]["citations"] == 1514
    assert len(i["journals"]) <= 10


@pytest.fixture(scope="session")
def series(tmp_path_factory):
    from scripts.export_site_extras import export_series
    out = tmp_path_factory.mktemp("s")
    return out, export_series(str(out))


def test_series_totals_match_the_paper(series):
    out, info = series
    assert info["series"] == 3515 and info["papers"] == 24478


def test_series_file_shape(series):
    out, _ = series
    s = json.load(open(out / "series" / "circulation.json"))["series"]
    assert any("stroke statistics" in x["title"].lower() for x in s)
    assert all(x["pmids"] and x["citations"] >= 0 for x in s)


@pytest.fixture(scope="session")
def landscape(tmp_path_factory):
    from scripts.export_site_extras import export_landscape
    out = tmp_path_factory.mktemp("l")
    export_landscape(str(out))
    return json.load(open(out / "landscape.json"))


WANTED = {"timing": {"age_curve", "per_year_by_month", "jif_credit", "matched_age", "pairs", "timing_hist", "annual_reports"},
          "reliance": {"top_paper_hist", "top_paper_trend", "most_reliant", "top_series", "guideline_falls"},
          "publishing": {"lift_hist", "lift_scatter", "largest", "publisher_share", "review_share", "review_journals", "tiers"},
          "people": {"institutions", "institution_regions", "concentration", "with_a_paper", "author_counts", "author_trend"},
          "geography": {"home_gap", "regional_journals", "citers_over_time"},
          "retractions": {"by_year_published", "by_year_retracted", "publisher_rate", "most_retractions", "around_retraction", "by_age"}}


def test_every_chart_is_present_in_its_group(landscape):
    got = {g["id"]: {c["id"] for c in g["charts"]} for g in landscape["groups"]}
    assert got == WANTED


def test_every_chart_has_a_title_and_note(landscape):
    for g in landscape["groups"]:
        for c in g["charts"]:
            assert c["title"] and c["note"] and c["type"] in {"line", "hbar", "stack", "bubble", "scatter", "hist", "set"}


def test_text_is_neutral_and_stands_alone(landscape):
    import re
    text = json.dumps(landscape)
    assert "gaming" not in text.lower() and not re.search(r"Figure \d", text)


def chart(landscape, cid):
    return next(c for g in landscape["groups"] for c in g["charts"] if c["id"] == cid)


def test_values_match_their_source_files(landscape):
    c = chart(landscape, "publisher_rate")
    assert c["labels"][0] == "Hindawi" and c["values"][0] == 645.7
    assert len(chart(landscape, "lift_scatter")["points"]) == 2533
    assert len(chart(landscape, "top_series")["labels"]) == 15
    assert len(chart(landscape, "citers_over_time")["sets"]) == 22
    trend = chart(landscape, "top_paper_trend")
    assert trend["labels"][0] == 2007 and len(trend["series"]) == 3


def test_by_age_has_one_set_per_retraction_year(landscape):
    assert set(chart(landscape, "by_age")["sets"]) == {f"Retracted in year {y}" for y in range(2, 8)}


def test_month_charts_show_june_with_no_value(landscape):
    for cid in ("per_year_by_month", "jif_credit", "matched_age"):
        c = chart(landscape, cid)
        assert c["labels"][5] == "Jun" and len(c["labels"]) == 12 and "June is left out" in c["note"]
        assert all(s["data"][5] is None and len(s["data"]) == 12 for s in c["series"])


def test_timing_chart_is_named_plainly(landscape):
    assert chart(landscape, "timing_hist")["title"] == "JIF change from papers published in early months, by journal"
