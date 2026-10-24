"""Citable-items rolling rate: numerator and denominator both count citable items."""
import json
import sqlite3

import pytest

from src.pipeline.db_manager import DatabaseManager
from src.pipeline.impact_calculator import ARTICLE_CATEGORIES, ImpactCalculator
from src.pipeline.json_exporter import JSONExporter

# Target 2024-12: citation window 2024-01..2024-12, paper window 2022-01..2023-12.
PAPER_DATE = "2023-03-15"
CITE_DATE = "2024-06-10"


@pytest.fixture
def db(tmp_path):
    d = DatabaseManager(str(tmp_path / "impact.db"))
    d.init_schema()
    yield d
    d.close()


_next = [1000]


def add(db, jid, cls, n_cites, pub_type="Journal Article", source="rule", date=PAPER_DATE,
        set_class=True):
    _next[0] += 1
    pmid = _next[0]
    db.conn.execute(
        "INSERT INTO papers (pmid, journal_id, title, pub_date, pub_year, pub_month, pub_type, "
        "is_research, doc_class, class_source) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (pmid, jid, "T", date, int(date[:4]), int(date[5:7]), pub_type, 1,
         cls if set_class else None, source if set_class else None))
    for i in range(n_cites):
        db.conn.execute(
            "INSERT INTO citations (cited_pmid, citing_pmid, citing_date, citing_year, "
            "citing_month) VALUES (?,?,?,?,?)", (pmid, 900000 + pmid * 10 + i, CITE_DATE, 2024, 6))
    db.conn.commit()
    return pmid


def build_window(db):
    jid = db.add_journal("1111-1111", "Hand Built", slug="hand-built")
    for n in (2, 2, 2):
        add(db, jid, "research", n)                      # 3 research, 6 cites
    add(db, jid, "review", 4, pub_type="Review")         # review, 4
    add(db, jid, "case_report", 1, pub_type="Case Reports")
    add(db, jid, "commentary", 0, pub_type="Comment")
    add(db, jid, "commentary", 0, pub_type="Comment")
    add(db, jid, "editorial", 5, pub_type="Editorial")   # excluded from the rate
    return jid


def test_symmetric_citable_rate(db):
    jid = build_window(db)
    s = ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)
    assert s["citable_papers"] == 5 and s["citable_citations"] == 11
    assert s["rolling_if"] == round(11 / 5, 3)
    assert s["rolling_if_no_reviews"] == round(6 / 3, 3)
    assert s["research_count"] == 3 and s["review_count"] == 1
    assert s["paper_count"] == 8
    assert s["by_type"]["commentary"] == {"papers": 2, "citations": 0}
    assert s["by_type"]["editorial"] == {"papers": 1, "citations": 5}
    assert set(s["by_type"]) == set(ARTICLE_CATEGORIES)
    assert s["inferred_papers"] == 0


def test_zero_citable_window(db):
    jid = db.add_journal("2222-2222", "Only Comments", slug="only-comments")
    add(db, jid, "commentary", 3, pub_type="Comment")
    add(db, jid, "letter", 2, pub_type="Letter")
    s = ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)
    assert s["rolling_if"] == 0.0 and s["rolling_if_no_reviews"] == 0.0
    assert s["citable_papers"] == 0 and s["citable_citations"] == 0
    assert s["paper_count"] == 2


def test_null_doc_class_falls_back_to_pub_type(db):
    jid = db.add_journal("3333-3333", "Mixed", slug="mixed")
    add(db, jid, "research", 2)                                        # doc_class set
    add(db, jid, None, 3, pub_type="Journal Article", set_class=False)  # NULL -> research
    add(db, jid, None, 1, pub_type="Review", set_class=False)           # NULL -> review
    add(db, jid, None, 7, pub_type="Editorial", set_class=False)        # NULL -> editorial
    add(db, jid, "case_report", 2, pub_type="Journal Article", source="inferred")
    s = ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)
    assert s["citable_papers"] == 4 and s["citable_citations"] == 8
    assert s["research_count"] == 2 and s["review_count"] == 1
    assert s["rolling_if"] == 2.0
    assert s["rolling_if_no_reviews"] == round(5 / 2, 3)
    assert s["by_type"]["editorial"] == {"papers": 1, "citations": 7}
    assert s["by_type"]["case_report"] == {"papers": 1, "citations": 2}
    assert s["inferred_papers"] == 1


def test_pub_by_type_uses_doc_class_with_fallback(db):
    jid = db.add_journal("4444-4444", "Pub", slug="pub")
    add(db, jid, "research", 0)   # in-window paper so the snapshot is not empty
    add(db, jid, "letter", 0, pub_type="Journal Article", date="2024-12-05")
    add(db, jid, None, 0, pub_type="Editorial", date="2024-12-06", set_class=False)
    s = ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)
    assert s["pub_by_type"] == {"letter": 1, "editorial": 1}


def test_new_fields_exported_per_point(db, tmp_path):
    jid = build_window(db)
    ts = [ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)]
    exp = JSONExporter(data_dir=str(tmp_path / "d"), journals_dir=str(tmp_path / "j"))
    path = exp.export_journal("hand-built", "Hand Built", "1111-1111", ts)
    pt = json.load(open(path))["timeseries"][0]
    assert pt["citable_papers"] == 5 and pt["citable_citations"] == 11
    assert pt["inferred_papers"] == 0
    for k in ("papers", "research", "reviews", "citations", "by_type", "pub_by_type"):
        assert k in pt


def test_no_official_jif_in_export(db, tmp_path):
    jid = build_window(db)
    ts = [ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)]
    exp = JSONExporter(data_dir=str(tmp_path / "d"), journals_dir=str(tmp_path / "j"))
    path = exp.export_journal("hand-built", "Hand Built", "1111-1111", ts)
    assert "official_jif_2024" not in json.load(open(path))


def test_empty_snapshot_has_new_fields(db):
    jid = db.add_journal("5555-5555", "Empty", slug="empty")
    s = ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)
    assert (s["citable_papers"], s["citable_citations"], s["inferred_papers"]) == (0, 0, 0)


def test_ensure_doc_class_columns_migrates_and_is_idempotent(tmp_path):
    path = str(tmp_path / "old.db")
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE papers (pmid INTEGER PRIMARY KEY, journal_id INTEGER, title TEXT, "
              "pub_date TEXT, pub_year INTEGER, pub_month INTEGER, pub_type TEXT, "
              "is_research INTEGER, doi TEXT)")
    c.commit()
    c.close()
    d = DatabaseManager(path)
    cols = lambda: [r[1] for r in d.conn.execute("PRAGMA table_info(papers)")]
    assert "doc_class" in cols() and "class_source" in cols()
    before = cols()
    d.ensure_doc_class_columns()
    d.close()
    d2 = DatabaseManager(path)
    assert [r[1] for r in d2.conn.execute("PRAGMA table_info(papers)")] == before
    d2.close()


def test_fresh_db_has_columns(db):
    cols = [r[1] for r in db.conn.execute("PRAGMA table_info(papers)")]
    assert cols.count("doc_class") == 1 and cols.count("class_source") == 1
