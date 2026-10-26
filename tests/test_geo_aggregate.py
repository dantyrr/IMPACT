"""Per-journal geography aggregation (src/pipeline/geo_aggregate.py)."""
from src.pipeline.geo_aggregate import GeoAggregator


def test_counts_papers_involving_and_fractional_credit():
    agg = GeoAggregator()
    agg.add("j", 2024, ["Germany", "USA"], ["MA"])
    agg.add("j", 2024, ["USA"], ["CA", "MA"])
    out = agg.export("j")
    assert out["papers"] == {"2024": 2}
    assert out["intl"] == {"2024": 1}
    assert out["us_papers"] == {"2024": 2}
    assert out["countries"]["USA"] == {"2024": [2, 1.5]}
    assert out["countries"]["Germany"] == {"2024": [1, 0.5]}
    assert out["states"]["MA"] == {"2024": [2, 1.5]}
    assert out["states"]["CA"] == {"2024": [1, 0.5]}
    assert out["country_pairs"] == {"Germany|USA": {"2024": 1}}
    assert out["state_pairs"] == {"CA|MA": {"2024": 1}}


def test_pairs_skip_papers_with_many_regions():
    agg = GeoAggregator(max_pair_regions=3)
    agg.add("j", 2020, ["A", "B", "C", "D"], [])
    out = agg.export("j")
    assert out["country_pairs"] == {}
    assert out["countries"]["A"] == {"2020": [1, 0.25]}
    assert out["intl"] == {"2020": 1}


def test_paper_without_location_is_ignored():
    agg = GeoAggregator()
    agg.add("j", 2020, [], [])
    assert agg.export("j")["papers"] == {}


def test_unknown_key_exports_empty_shape():
    out = GeoAggregator().export("nope")
    assert out["countries"] == {} and out["papers"] == {}


def test_keys_are_independent():
    agg = GeoAggregator()
    agg.add("a", 2021, ["France"], [])
    agg.add("b", 2021, ["Japan"], [])
    assert list(agg.export("a")["countries"]) == ["France"]
    assert sorted(agg.keys()) == ["a", "b"]
