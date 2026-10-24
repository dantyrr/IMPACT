"""Journal reliability flags and per-journal citable PMID class files."""
import json
from datetime import date

import pytest

from src.pipeline.db_manager import DatabaseManager
from src.pipeline.journal_flags import compute_flags, decode_deltas, encode_deltas, settled_point
from src.pipeline.json_exporter import JSONExporter


def pt(month="2024-01", research=100, reviews=30, citable=120, papers=130, inferred=0):
    return {"month": month, "papers": papers, "citable_papers": citable,
            "inferred_papers": inferred,
            "by_type": {"research": {"papers": research, "citations": 0},
                        "review": {"papers": reviews, "citations": 0}}}


def test_clean_point_has_no_flags():
    assert compute_flags(pt()) == []


@pytest.mark.parametrize("n,flagged", [(19, True), (20, False)])
def test_small_research_sample_boundary(n, flagged):
    assert ("small_research_sample" in compute_flags(pt(research=n))) is flagged


@pytest.mark.parametrize("n,flagged", [(14, True), (15, False)])
def test_small_review_sample_boundary(n, flagged):
    assert ("small_review_sample" in compute_flags(pt(reviews=n))) is flagged


@pytest.mark.parametrize("reviews,flagged", [(49, False), (50, True)])
def test_review_journal_boundary(reviews, flagged):
    # 100 citable items: 49% reviews is not flagged, 50% is
    p = pt(reviews=reviews, citable=100, research=40, papers=100)
    assert ("review_journal" in compute_flags(p)) is flagged


@pytest.mark.parametrize("inferred,flagged", [(9, False), (10, True)])
def test_inferred_types_boundary(inferred, flagged):
    p = pt(papers=100, inferred=inferred)
    assert ("inferred_types" in compute_flags(p)) is flagged


def test_zero_denominators_are_safe():
    p = pt(research=0, reviews=0, citable=0, papers=0, inferred=0)
    flags = compute_flags(p)
    assert "review_journal" not in flags and "inferred_types" not in flags
    assert "small_research_sample" in flags and "small_review_sample" in flags


def test_missing_by_type_tolerated():
    flags = compute_flags({"month": "2024-01", "papers": 0, "citable_papers": 0})
    assert "small_research_sample" in flags


def test_delta_round_trip():
    vals = [3, 7, 8, 1000, 1001, 99999999]
    assert encode_deltas(vals) == [3, 4, 1, 992, 1, 99998998]
    assert decode_deltas(encode_deltas(vals)) == vals
    assert encode_deltas([]) == [] and decode_deltas([]) == []
    assert encode_deltas([5, 2, 9]) == [2, 3, 4]  # sorts first


AS_OF = date(2026, 10, 24)  # export month 2026-10 -> cutoff 2025-10


def test_settled_point_selection():
    ts = [{"month": "2025-09"}, {"month": "2025-10"}, {"month": "2025-11"}, {"month": "2026-10"}]
    assert settled_point(ts, AS_OF)["month"] == "2025-10"      # exactly 12 months back qualifies
    assert settled_point(ts[:1] + ts[2:3], AS_OF)["month"] == "2025-09"
    assert settled_point([{"month": "2025-11"}, {"month": "2026-10"}], AS_OF) is None  # 11 back does not
    assert settled_point([], AS_OF) is None


def test_settled_point_year_wrap():
    assert settled_point([{"month": "2025-01"}, {"month": "2025-02"}], date(2026, 1, 5))["month"] == "2025-01"


def test_no_qualifying_point_gives_no_flags(tmp_path):
    ex = JSONExporter(data_dir=str(tmp_path), journals_dir=str(tmp_path / "j"))
    ts = [{"month": "2026-09", "rolling_if": 1, "rolling_if_no_reviews": 1, "paper_count": 1,
           "review_count": 0, "citation_count": 0}]
    path = ex.export_journal("x", "X", "1111-1111", ts, as_of=AS_OF)
    assert json.load(open(path))["flags"] == []


def snap(month, research):
    return {"month": month, "rolling_if": 1.0, "rolling_if_no_reviews": 1.0, "paper_count": 100,
            "review_count": 20, "citation_count": 5, "citable_papers": 100,
            "inferred_papers": 0,
            "by_type": {"research": {"papers": research, "citations": 0},
                        "review": {"papers": 20, "citations": 0}}}


def test_flags_in_journal_json_from_settled_point(tmp_path):
    ex = JSONExporter(data_dir=str(tmp_path), journals_dir=str(tmp_path / "j"))
    # settled point (2025-10) has 5 research -> small; latest point has 500 (ignored)
    ts = [snap("2025-10", 5), snap("2026-10", 500)]
    data = json.load(open(ex.export_journal("x", "X", "1111-1111", ts, as_of=AS_OF)))
    assert data["flags"] == ["small_research_sample"]


def test_export_index_keeps_flags(tmp_path):
    ex = JSONExporter(data_dir=str(tmp_path), journals_dir=str(tmp_path / "j"))
    ex.export_index([{"slug": "x", "name": "X", "flags": ["review_journal"]}])
    assert json.load(open(tmp_path / "index.json"))["journals"][0]["flags"] == ["review_journal"]


def test_index_entry_flags_helper():
    from src.pipeline.journal_flags import flags_for_timeseries
    ts = [snap("2025-10", 5)]
    assert flags_for_timeseries(ts, AS_OF) == ["small_research_sample"]


@pytest.fixture
def db(tmp_path):
    d = DatabaseManager(str(tmp_path / "impact.db"))
    d.init_schema()
    yield d
    d.close()


def add_paper(db, jid, pmid, year, doc_class, pub_type="Journal Article"):
    db.conn.execute(
        "INSERT INTO papers (pmid, journal_id, title, pub_date, pub_year, pub_month, pub_type, "
        "is_research, doc_class) VALUES (?,?,?,?,?,?,?,?,?)",
        (pmid, jid, "T", f"{year}-01-01", year, 1, pub_type, 1, doc_class))
    db.conn.commit()


def test_classes_file(db, tmp_path):
    jid = db.add_journal("1111-1111", "J", slug="j")
    other = db.add_journal("2222-2222", "Other", slug="other")
    add_paper(db, jid, 50, 2010, "research")
    add_paper(db, jid, 10, 2005, "review")
    add_paper(db, jid, 11, 2005, "guideline")
    add_paper(db, jid, 12, 2020, "editorial")
    add_paper(db, jid, 13, 2020, None, "Case Reports")      # NULL -> pub_type fallback: case_report (citable)
    add_paper(db, jid, 14, 2020, None, "Comment")           # NULL -> commentary
    add_paper(db, jid, 15, 2020, None, None)                # NULL, no pub_type -> research
    add_paper(db, jid, 99, 2002, "research")                # out of range
    add_paper(db, jid, 98, 2027, "research")                # out of range
    add_paper(db, other, 1, 2010, "research")               # other journal
    ex = JSONExporter(data_dir=str(tmp_path), journals_dir=str(tmp_path / "j"))
    path = ex.export_journal_classes("j", db.get_paper_classes_for_journal(jid))
    assert path == str(tmp_path / "classes" / "j.json")
    raw = open(path).read()
    assert " " not in raw and "\n" not in raw
    data = json.loads(raw)
    assert data["v"] == 1
    assert decode_deltas(data["citable"]) == [10, 11, 13, 15, 50]
    assert decode_deltas(data["noncitable"]) == [12, 14]
    assert data["citable"] == [10, 1, 2, 2, 35]


def test_classes_file_empty(tmp_path):
    ex = JSONExporter(data_dir=str(tmp_path), journals_dir=str(tmp_path / "j"))
    path = ex.export_journal_classes("e", [])
    assert json.load(open(path)) == {"v": 1, "citable": [], "noncitable": []}
