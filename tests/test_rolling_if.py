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
        set_class=True, citing_class=None):
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
            "citing_month, citing_class) VALUES (?,?,?,?,?,?)",
            (pmid, 900000 + pmid * 10 + i, CITE_DATE, 2024, 6, citing_class))
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


def test_papers_export_carries_rate_category(db, tmp_path):
    db.migrate_add_author_columns()
    jid = build_window(db)
    guideline = add(db, jid, "guideline", 3, pub_type="Review")     # classed by title, PubMed says Review
    unclassified = add(db, jid, None, 1, pub_type="Review", set_class=False)
    exp = JSONExporter(data_dir=str(tmp_path / "d"), journals_dir=str(tmp_path / "j"))
    path = exp.export_journal_papers("hand-built", db.get_papers_for_export(jid))
    k = {p["pmid"]: p["k"] for p in json.load(open(path))["papers"]}
    assert k[guideline] == "guideline"          # the class the rate counts it under, not PubMed's type
    assert k[unclassified] == "review"          # no doc_class yet: derived from pub_type, as in by_type
    assert set(k.values()) <= set(ARTICLE_CATEGORIES)


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


def test_unknown_doc_class_maps_to_other(db, caplog):
    jid = db.add_journal("6666-6666", "Bogus", slug="bogus")
    add(db, jid, "research", 1)
    add(db, jid, "bogus", 4)
    with caplog.at_level("WARNING"):
        s = ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)
    assert s["by_type"]["other"] == {"papers": 1, "citations": 4}
    assert s["citable_papers"] == 1 and s["paper_count"] == 2
    assert "bogus" in caplog.text


def test_weekly_format_snapshot_has_new_fields(db):
    import importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "run_weekly_update",
        os.path.join(os.path.dirname(__file__), "..", "scripts", "run_weekly_update.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    jid = build_window(db)
    pt = mod.format_snapshot(ImpactCalculator(db).compute_rolling_if(jid, 2024, 12))
    assert (pt["citable_papers"], pt["citable_citations"], pt["inferred_papers"]) == (5, 11, 0)


def test_notice_citations_count_toward_no_metric(db):
    db.migrate_add_author_columns()
    jid = build_window(db)
    retracted = add(db, jid, "research", 3, citing_class="erratum")  # cited only by notices
    s = ImpactCalculator(db).compute_rolling_if(jid, 2024, 12)
    assert s["citable_papers"] == 6 and s["citable_citations"] == 11  # paper counts, cites do not
    assert s["citation_count"] == 16
    assert db.get_citation_count_for_paper(retracted) == 0
    assert db.get_citations_for_paper(retracted) == []
    assert db.count_citations_for_papers([retracted], "2024-01-01", "2024-12-31") == 0
    assert db.get_citations_by_year_for_pmids([retracted]) == {}
    assert db.get_citations_by_month_for_pmids([retracted]) == {}
    assert db.get_journal_monthly_citations(jid) == {"2024-06": 16}
    top = {r["pmid"]: r["citation_count"] for r in db.get_papers_for_export(jid)}
    assert top[retracted] == 0


def test_mark_citing_class_and_insert(db):
    jid = db.add_journal("7777-7777", "Marks", slug="marks")
    p = add(db, jid, "research", 0)
    db.add_citations_bulk([
        {"cited_pmid": p, "citing_pmid": 1, "citing_date": CITE_DATE, "citing_year": 2024,
         "citing_month": 6},
        {"cited_pmid": p, "citing_pmid": 2, "citing_date": CITE_DATE, "citing_year": 2024,
         "citing_month": 6, "citing_class": "erratum"},
        {"cited_pmid": p, "citing_pmid": 3, "citing_date": CITE_DATE, "citing_year": 2024,
         "citing_month": 6}])
    assert db.get_citation_count_for_paper(p) == 2
    assert db.mark_citing_class({3: "erratum", 2: "erratum"}) == 1  # 2 already marked
    assert db.get_citation_count_for_paper(p) == 1
    assert db.mark_citing_class({3: "erratum"}) == 0


def test_ensure_citing_class_column_migrates(tmp_path):
    path = str(tmp_path / "old.db")
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE citations (id INTEGER PRIMARY KEY, cited_pmid INTEGER, "
              "citing_pmid INTEGER, citing_date TEXT, citing_year INTEGER, citing_month INTEGER)")
    c.execute("INSERT INTO citations VALUES (1, 10, 20, '2024-01-01', 2024, 1)")
    c.commit()
    c.close()
    d = DatabaseManager(path)
    assert d.conn.execute("SELECT citing_class FROM citations").fetchone()[0] is None
    d.close()
    DatabaseManager(path).close()  # idempotent
