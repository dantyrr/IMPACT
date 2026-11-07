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
    assert info["series"] == 3514 and info["papers"] == 24479


def test_ncbi_series_has_all_24_editions(series):
    out, _ = series
    s = json.load(open(out / "series" / "nucleic-acids-research.json"))["series"]
    ncbi = next(x for x in s if x["title"].lower().startswith("database resources of the national center"))
    assert ncbi["items"] == 24 and ncbi["citations"] == 12500


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
          "publishing": {"lift_hist", "lift_scatter", "by_publisher", "largest", "publisher_share", "review_share", "review_journals", "tiers"},
          "people": {"institution_moves", "institutions", "institution_regions", "concentration", "with_a_paper", "author_counts", "author_trend"},
          "geography": {"home_gap", "regional_journals", "citers_over_time"},
          "retractions": {"by_year_published", "by_year_retracted", "publisher_rate", "most_retractions", "around_retraction", "by_age"}}


def test_every_chart_is_present_in_its_group(landscape):
    got = {g["id"]: {c["id"] for c in g["charts"]} for g in landscape["groups"]}
    assert got == WANTED


def test_every_chart_has_a_title_and_note(landscape):
    for g in landscape["groups"]:
        for c in g["charts"]:
            assert c["title"] and c["note"] and c["type"] in {"line", "hbar", "stack", "bubble", "scatter", "hist", "set", "institutions"}


def test_text_is_neutral_and_stands_alone(landscape):
    import re
    text = json.dumps(landscape)
    assert "gaming" not in text.lower() and not re.search(r"Figure \d", text)


def chart(landscape, cid):
    return next(c for g in landscape["groups"] for c in g["charts"] if c["id"] == cid)


def test_values_match_their_source_files(landscape):
    c = chart(landscape, "publisher_rate")
    assert c["labels"][0] == "Hindawi (Wiley)" and c["values"][0] == 645.7
    assert len(chart(landscape, "lift_scatter")["points"]) == 2533
    assert len(chart(landscape, "top_series")["labels"]) == 15
    assert len(chart(landscape, "citers_over_time")["sets"]) == 22
    trend = chart(landscape, "top_paper_trend")
    assert trend["labels"][0] == 2007 and len(trend["series"]) == 3


def test_publisher_charts_go_by_owner(landscape):
    total = chart(landscape, "by_publisher")
    names = [x["label"] for x in total["series"]]
    assert {"Elsevier", "Springer Nature", "Wiley", "AAAS"} <= set(names) and not {"Cureus", "Hindawi", "Cell Press"} & set(names)
    assert len({x["color"] for x in total["series"]}) == len(names)
    for cid in ("publisher_share", "review_share"):
        shown = [x["label"] for x in chart(landscape, cid)["series"]]
        assert shown[:3] == ["Elsevier", "Springer Nature", "MDPI"] and len(shown) == 7


def test_tiers_hold_all_of_cell_press_and_name_owners(landscape):
    sets = chart(landscape, "tiers")["sets"]
    assert "Hindawi (Wiley)" in sets and "Cureus (Springer Nature)" in sets
    assert "Trends reviews" in [x["label"] for x in sets["Cell Press"]["series"]]


def test_top_series_uses_all_ncbi_editions(landscape):
    c = chart(landscape, "top_series")
    assert 12500 in c["values"]


def test_no_chart_calls_cureus_a_publisher(landscape):
    c = chart(landscape, "review_journals")
    assert "Cureus (Springer Nature)" in c["labels"] and "Cureus (Cureus)" not in c["labels"]


def test_retraction_rates_go_by_owner(landscape):
    labels = chart(landscape, "publisher_rate")["labels"]
    assert "Springer Nature" in labels and "Wiley" in labels and not {"BMC", "Dove", "Springer", "Nature Portfolio"} & set(labels)
    assert not any(x.startswith("Cureus") for x in labels)


def test_landscape_says_rise_not_lift(landscape):
    titles = " ".join(c["title"] + c["note"] for g in landscape["groups"] for c in g["charts"])
    assert "lift" not in titles.lower()


def test_by_age_has_one_set_per_retraction_year(landscape):
    assert set(chart(landscape, "by_age")["sets"]) == {f"Retracted in year {y}" for y in range(2, 8)}


def test_month_charts_show_june_with_no_value(landscape):
    for cid in ("per_year_by_month", "jif_credit", "matched_age"):
        c = chart(landscape, cid)
        assert c["labels"][5] == "Jun" and len(c["labels"]) == 12 and "June is left out" in c["note"]
        assert all(s["data"][5] is None and len(s["data"]) == 12 for s in c["series"])


def test_timing_chart_is_named_plainly(landscape):
    assert chart(landscape, "timing_hist")["title"] == "JIF change from papers published in early months, by journal"


@pytest.fixture(scope="module")
def bubbles(tmp_path_factory):
    from scripts.export_site_extras import export_bubbles
    out = tmp_path_factory.mktemp("bubbles")
    export_bubbles(str(out))
    return json.load(open(out / "institution_bubbles.json"))


def window(row, start):
    return sum(row[start:start + 5]) if row else 0


def by_name(data, name):
    return next(i for i in data["institutions"] if i[0] == name)


def test_bubbles_match_figure_1(bubbles):
    """The first and last windows are the paper's panels A and B."""
    stanford, tsinghua = by_name(bubbles, "Stanford University"), by_name(bubbles, "Tsinghua University")
    assert (window(stanford[2], 0), window(stanford[3], 0), window(stanford[2], 20), window(stanford[3], 20)) == (8941, 258, 17890, 467)
    assert (window(tsinghua[3], 0), window(tsinghua[3], 20)) == (5, 123)


def test_bubbles_regions_match_figure_1(bubbles):
    names = [r["name"] for r in bubbles["regions"]]
    china, usa = names.index("China"), names.index("USA")
    share = lambda tab, k, start: sum(tab[k][start:start + 5]) / sum(sum(row[start:start + 5]) for row in tab)  # noqa: E731
    assert round(share(bubbles["regionAll"], china, 20), 3) == 0.245 and round(share(bubbles["regionFlag"], usa, 0), 3) == 0.548
    assert {r["name"]: r["color"] for r in bubbles["regions"]}["Canada"] == "#CC79A7"


def test_bubbles_merge_name_variants(bubbles):
    harvard = by_name(bubbles, "Harvard University")
    assert (window(harvard[3], 0), window(harvard[3], 20)) == (915, 1065)
    names = {i[0] for i in bubbles["institutions"]}
    assert "Harvard Medical School" not in names and "Massachusetts General Hospital" not in names and "Peking University Third Hospital" not in names
    assert {"Memorial Sloan Kettering Cancer Center", "Mayo Clinic", "Cleveland Clinic", "Cleveland Clinic Abu Dhabi"} <= names
    assert [n for n in names if n.startswith("Wake Forest")] == ["Wake Forest University"]
    assert [n for n in names if n.startswith("Mayo ")] == ["Mayo Clinic"]
    assert "McGill University" in names and "University of Virginia" in names and "University of Virginia Medical School" not in names


def test_bubbles_names_are_unique(bubbles):
    names = [i[0] for i in bubbles["institutions"]]
    assert len(names) == len(set(names))
    assert "University of California Davis" in names and "University of California" not in names


def test_bubbles_shape(bubbles):
    n = bubbles["lastYear"] - bubbles["firstYear"] + 1
    assert n == 25 and bubbles["window"] == 5 and len(bubbles["denomAll"]) == n
    assert all(len(i[2]) == n and len(i[3]) in (0, n) for i in bubbles["institutions"])
    assert len({i[0] for i in bubbles["institutions"]}) > 6900
