"""Tests for scripts/apply_pubmed_full.py and scripts/validate_doc_class.py (temp DBs only)."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from src.pipeline.doc_class import classify
from src.pipeline.pubmed_full_db import open_full_db

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


apply_mod = _load("apply_pubmed_full")
val_mod = _load("validate_doc_class")

PAPER_COLS = ("pmid, journal_id, title, pub_date, pub_year, pub_month, pub_type, is_research, doi, "
              "first_author_name, first_author_institution, first_author_city, first_author_state, "
              "first_author_country, last_author_name, last_author_institution, last_author_city, "
              "last_author_state, last_author_country, first_author_forename, last_author_forename, "
              "first_author_gender, first_author_gender_prob, last_author_gender, "
              "last_author_gender_prob, gender_pair")
GENDER = ("first_author_forename, last_author_forename, first_author_gender, "
          "first_author_gender_prob, last_author_gender, last_author_gender_prob, gender_pair")


def make_impact(path, papers, journals=((1, "1111-1111", "Jour One", "J1", "jour-one"),)):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE journals (id INTEGER PRIMARY KEY, issn TEXT, name TEXT, "
              "abbreviation TEXT, slug TEXT)")
    c.executemany("INSERT INTO journals VALUES (?,?,?,?,?)", journals)
    c.execute(f"CREATE TABLE papers ({PAPER_COLS.replace('pmid,', 'pmid INTEGER PRIMARY KEY,', 1)})")
    for p in papers:
        c.execute(f"INSERT INTO papers ({PAPER_COLS}) VALUES ({','.join('?' * 26)})",
                  _row(p))
    c.commit()
    c.close()


def _row(p):
    d = {"pmid": p["pmid"], "journal_id": p.get("journal_id", 1), "title": p.get("title", "T"),
         "pub_date": p.get("pub_date", "2020-01-01"), "pub_year": 2020, "pub_month": 1,
         "pub_type": p.get("pub_type", "Journal Article"), "is_research": 1, "doi": None,
         "first_author_name": "Old, First", "first_author_institution": "Old Inst",
         "first_author_city": "Old City", "first_author_state": "OS",
         "first_author_country": "Oldland", "last_author_name": "Old, Last",
         "last_author_institution": "Old Inst2", "last_author_city": "Old City2",
         "last_author_state": "O2", "last_author_country": "Oldland2",
         "first_author_forename": "First", "last_author_forename": "Last",
         "first_author_gender": "female", "first_author_gender_prob": 0.97,
         "last_author_gender": "male", "last_author_gender_prob": 0.88, "gender_pair": "FM"}
    d.update(p.get("extra", {}))
    return [d[k.strip()] for k in PAPER_COLS.split(",")]


def make_full(path, records, authors=(), affils=(), author_affils=()):
    c = open_full_db(str(path))
    for r in records:
        c.execute("INSERT INTO pubmed (pmid, issn, title, pub_type, pub_types, has_abstract, "
                  "page_count) VALUES (?,?,?,?,?,?,?)",
                  (r["pmid"], "1111-1111", r.get("title", "T"), r.get("pub_type", "Journal Article"),
                   json.dumps(r.get("pub_types", ["Journal Article"])),
                   r.get("has_abstract", 1), r.get("page_count")))
    c.executemany("INSERT INTO authors VALUES (?,?,?,?,?,?,?)", authors)
    c.executemany("INSERT INTO affil_strings (affil_id, text, country, state, city, institution) "
                  "VALUES (?,?,?,?,?,?)", affils)
    c.executemany("INSERT INTO author_affils VALUES (?,?,?,?)", author_affils)
    c.commit()
    c.close()


def make_icite(path, rows):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE metadata (pmid INTEGER PRIMARY KEY, "
              "is_research_article INTEGER NOT NULL DEFAULT 1, cited_by TEXT)")
    c.executemany("INSERT INTO metadata (pmid, is_research_article) VALUES (?,?)", rows)
    c.commit()
    c.close()


@pytest.fixture
def env(tmp_path, monkeypatch):
    impact, full, icite = (tmp_path / n for n in ("impact.db", "pubmed_full.db", "icite_bulk.db"))
    monkeypatch.setattr(apply_mod, "IMPACT_DB_PATH", str(impact))
    monkeypatch.setattr(apply_mod, "FULL_DB_PATH", str(full))
    monkeypatch.setattr(apply_mod, "ICITE_DB_PATH", str(icite))
    monkeypatch.setattr(apply_mod, "rebuild_lock_held", lambda: True)
    monkeypatch.setattr(apply_mod, "free_gb", lambda p: 1000.0)
    return type("Env", (), dict(impact=impact, full=full, icite=icite, tmp=tmp_path))


def fetch(path, sql):
    c = sqlite3.connect(path)
    try:
        return c.execute(sql).fetchall()
    finally:
        c.close()


def basic_env(env):
    make_impact(env.impact, [{"pmid": 1}, {"pmid": 2, "pub_type": "Journal Article"},
                             {"pmid": 3, "pub_type": "Journal Article"}])
    make_full(env.full,
              [{"pmid": 1, "pub_types": ["Journal Article", "Review"], "pub_type": "Review"},
               {"pmid": 2, "pub_types": ["Journal Article"], "has_abstract": 0, "page_count": 1},
               {"pmid": 3, "pub_types": ["Letter"], "pub_type": "Letter"}],
              authors=[(1, 1, "Tyrrell", "Daniel J", "DJ", None, None),
                       (1, 2, "Smith", "Jo", "J", None, None),
                       (2, 1, "Solo", "Al", "A", None, None)],
              affils=[(10, "Univ A, Boston, MA, USA", "USA", "MA", "Boston", "Univ A"),
                      (11, "Univ B, Paris, France", "France", None, "Paris", "Univ B")],
              author_affils=[(1, 1, 0, 10), (1, 2, 0, 11)])
    make_icite(env.icite, [(1, 1), (2, 0)])


# ---- apply ----

def test_classes_match_classify_and_is_research(env):
    basic_env(env)
    assert apply_mod.main([]) == 0
    rows = {r[0]: r[1:] for r in fetch(env.impact, "SELECT pmid, doc_class, class_source, "
                                                   "is_research, pub_type FROM papers")}
    assert rows[1][:2] == classify(["Journal Article", "Review"], True, None, True, "T")
    assert rows[2][:2] == classify(["Journal Article"], False, 1, False, "T") == ("commentary", "inferred")
    assert rows[3][:2] == ("letter", "pubmed")
    for cls_src_isres in rows.values():
        assert cls_src_isres[2] == (1 if cls_src_isres[0] == "research" else 0)
    assert rows[1][3] == "Review" and rows[3][3] == "Letter"


def test_gender_columns_untouched(env):
    basic_env(env)
    before = fetch(env.impact, f"SELECT pmid, {GENDER} FROM papers ORDER BY pmid")
    assert apply_mod.main([]) == 0
    assert fetch(env.impact, f"SELECT pmid, {GENDER} FROM papers ORDER BY pmid") == before


def test_dry_run_writes_nothing(env):
    basic_env(env)
    before = fetch(env.impact, "SELECT * FROM papers ORDER BY pmid")
    assert apply_mod.main(["--dry-run"]) == 0
    assert fetch(env.impact, "SELECT * FROM papers ORDER BY pmid") == before
    cols = [r[1] for r in fetch(env.impact, "PRAGMA table_info(papers)")]
    assert "doc_class" not in cols


def test_byline_name_formats_and_affiliation_fields(env):
    make_impact(env.impact, [{"pmid": 1}, {"pmid": 2}, {"pmid": 3}])
    make_full(env.full,
              [{"pmid": 1}, {"pmid": 2}, {"pmid": 3}],
              authors=[(1, 1, "Tyrrell", "Daniel J", "DJ", None, None),
                       (1, 2, "Mid", "M", "M", None, None),
                       (1, 3, "Last", "Zed", "Z", None, None),
                       (2, 1, None, None, None, "The Consortium", None),
                       (2, 2, "Only", None, "O", None, None),
                       (3, 1, "Solo", "Al", "A", None, None)],
              affils=[(10, "a", "USA", "MA", "Boston", "Univ A"),
                      (11, "b", "France", None, "Paris", "Univ B"),
                      (12, "c", "Peru", None, "Lima", "Univ C")],
              author_affils=[(1, 1, 1, 11), (1, 1, 0, 10), (1, 3, 0, 12)])
    assert apply_mod.main([]) == 0
    r = {x[0]: x[1:] for x in fetch(env.impact, "SELECT pmid, first_author_name, "
         "first_author_institution, first_author_city, first_author_state, first_author_country, "
         "last_author_name, last_author_institution, last_author_country FROM papers")}
    # lowest affil_order wins; last = max position
    assert r[1] == ("Tyrrell, Daniel J", "Univ A", "Boston", "MA", "USA",
                    "Last, Zed", "Univ C", "Peru")
    assert r[2][0] == "The Consortium"            # collective author
    assert r[2][5] == "Only"                      # missing fore_name -> last name alone
    assert r[3][0] == r[3][5] == "Solo, Al"       # single author is both first and last


def test_no_new_affiliation_leaves_existing_fields(env):
    make_impact(env.impact, [{"pmid": 1}])
    make_full(env.full, [{"pmid": 1}],
              authors=[(1, 1, "New", "Name", "N", None, None), (1, 2, "Newl", "Last", "L", None, None)])
    assert apply_mod.main([]) == 0
    r = fetch(env.impact, "SELECT first_author_name, first_author_institution, first_author_city, "
              "first_author_state, first_author_country, last_author_institution FROM papers")[0]
    assert r == ("New, Name", "Old Inst", "Old City", "OS", "Oldland", "Old Inst2")


def test_papers_missing_from_full_db_untouched_and_counted(env, capsys):
    make_impact(env.impact, [{"pmid": 1}, {"pmid": 2}])
    make_full(env.full, [{"pmid": 1, "pub_types": ["Editorial"], "pub_type": "Editorial"}])
    before = fetch(env.impact, "SELECT * FROM papers WHERE pmid=2")
    assert apply_mod.main([]) == 0
    assert fetch(env.impact, "SELECT * FROM papers WHERE pmid=2")[0][:len(before[0])] == before[0]
    assert fetch(env.impact, "SELECT doc_class FROM papers WHERE pmid=2") == [(None,)]
    assert "missing from pubmed_full: 1" in capsys.readouterr().out


def test_icite_none_when_pmid_absent(env):
    make_impact(env.impact, [{"pmid": 5}])
    make_full(env.full, [{"pmid": 5, "has_abstract": 0, "page_count": 20}])
    make_icite(env.icite, [])
    assert apply_mod.main([]) == 0
    assert fetch(env.impact, "SELECT doc_class FROM papers") == [("research",)]


def test_journals_filter(env):
    make_impact(env.impact, [{"pmid": 1}, {"pmid": 2, "journal_id": 2}],
                journals=[(1, "1", "A", "A", "a"), (2, "2", "B", "B", "b")])
    make_full(env.full, [{"pmid": 1}, {"pmid": 2}])
    assert apply_mod.main(["--journals", "b"]) == 0
    assert fetch(env.impact, "SELECT pmid, doc_class FROM papers ORDER BY pmid") == \
        [(1, None), (2, "research")]


def test_migration_idempotent_and_index(env):
    make_impact(env.impact, [{"pmid": 1}])
    c = sqlite3.connect(env.impact)
    apply_mod.migrate(c)
    apply_mod.migrate(c)
    names = {r[1] for r in c.execute("PRAGMA table_info(papers)")}
    assert {"doc_class", "class_source"} <= names
    idx = c.execute("PRAGMA index_info(idx_papers_journal_date_class)").fetchall()
    assert [r[2] for r in idx] == ["journal_id", "pub_date", "doc_class"]


def _index_exists(path):
    return bool(fetch(path, "SELECT 1 FROM sqlite_master WHERE name='idx_papers_journal_date_class'"))


def test_index_built_only_after_completed_run(env, monkeypatch):
    make_impact(env.impact, [{"pmid": i} for i in (1, 2, 3, 4)])
    make_full(env.full, [{"pmid": i} for i in (1, 2, 3, 4)])
    monkeypatch.setattr(apply_mod, "BATCH_SIZE", 2)
    free = iter([100.0, 100.0, 100.0, 10.0])  # pre-migrate, batch1, batch2, pre-index
    monkeypatch.setattr(apply_mod, "free_gb", lambda p: next(free))
    assert apply_mod.main([]) == 3
    assert not _index_exists(env.impact)
    monkeypatch.setattr(apply_mod, "free_gb", lambda p: 1000.0)
    assert apply_mod.main([]) == 0
    assert _index_exists(env.impact)


def test_low_disk_before_migration_changes_nothing(env, monkeypatch):
    make_impact(env.impact, [{"pmid": 1}])
    make_full(env.full, [{"pmid": 1}])
    monkeypatch.setattr(apply_mod, "free_gb", lambda p: 5.0)
    assert apply_mod.main([]) == 3
    assert "doc_class" not in [r[1] for r in fetch(env.impact, "PRAGMA table_info(papers)")]


def test_all_null_affiliation_leaves_existing_fields(env):
    make_impact(env.impact, [{"pmid": 1}])
    make_full(env.full, [{"pmid": 1}],
              authors=[(1, 1, "New", "Name", "N", None, None)],
              affils=[(10, "garbage", None, None, None, None)],
              author_affils=[(1, 1, 0, 10)])
    assert apply_mod.main([]) == 0
    assert fetch(env.impact, "SELECT first_author_name, first_author_institution, first_author_city, "
                 "first_author_state, first_author_country FROM papers") == \
        [("New, Name", "Old Inst", "Old City", "OS", "Oldland")]


def test_dry_run_leaves_journal_mode_and_no_wal(env):
    basic_env(env)
    assert fetch(env.impact, "PRAGMA journal_mode")[0][0] != "wal"
    assert apply_mod.main(["--dry-run"]) == 0
    assert fetch(env.impact, "PRAGMA journal_mode")[0][0] != "wal"
    assert not Path(str(env.impact) + "-wal").exists()


def test_refuses_without_lock(env, monkeypatch):
    basic_env(env)
    monkeypatch.setattr(apply_mod, "rebuild_lock_held", lambda: False)
    assert apply_mod.main([]) == 1
    cols = [r[1] for r in fetch(env.impact, "PRAGMA table_info(papers)")]
    assert "doc_class" not in cols


def test_low_disk_stops_with_work_committed(env, monkeypatch):
    make_impact(env.impact, [{"pmid": i} for i in (1, 2, 3, 4)])
    make_full(env.full, [{"pmid": i} for i in (1, 2, 3, 4)])
    monkeypatch.setattr(apply_mod, "BATCH_SIZE", 2)
    free = iter([100.0, 100.0, 10.0])  # pre-migrate, batch 1, batch 2
    monkeypatch.setattr(apply_mod, "free_gb", lambda p: next(free))
    assert apply_mod.main([]) == 3
    assert fetch(env.impact, "SELECT pmid, doc_class FROM papers ORDER BY pmid") == \
        [(1, "research"), (2, "research"), (3, None), (4, None)]


# ---- validate ----

def test_validate_report(env, tmp_path, monkeypatch):
    letter_only = ["Letter"]
    papers = [{"pmid": 1, "title": "A study", "pub_date": "2019-01-01"},
              {"pmid": 2, "title": "Highlight", "pub_date": "2020-01-01"},
              {"pmid": 3, "title": "A study", "pub_date": "2020-02-01", "pub_type": "Letter"},
              {"pmid": 4, "title": "Foo-Reply", "pub_date": "2020-03-01", "pub_type": "Letter"},
              {"pmid": 6, "title": "Plain", "pub_date": "2020-04-01", "pub_type": "Letter"},
              {"pmid": 5, "title": "Other", "journal_id": 2}]
    make_impact(env.impact, papers,
                journals=[(1, "1", "JAMA", "J", "jama"), (2, "2", "Missingless", "M", "other-j")])
    make_full(env.full, [{"pmid": 1}, {"pmid": 2, "has_abstract": 0, "page_count": 1},
                         {"pmid": 3, "pub_types": letter_only, "pub_type": "Letter"},
                         {"pmid": 4, "pub_types": letter_only, "pub_type": "Letter"},
                         {"pmid": 5},
                         {"pmid": 6, "pub_types": letter_only, "pub_type": "Letter"}])
    make_icite(env.icite, [(2, 0), (3, 1), (4, 0)])
    csv = tmp_path / "flagged.csv"
    csv.write_text("slug,name\nother-j,Other\nnot-there,Nope\n")
    for k, v in (("IMPACT_DB_PATH", str(env.impact)), ("FULL_DB_PATH", str(env.full)),
                 ("ICITE_DB_PATH", str(env.icite)), ("DETECTOR_CSV", str(csv))):
        monkeypatch.setattr(val_mod, k, v)
    out = tmp_path / "report.md"
    assert val_mod.main(["--out", str(out)]) == 0
    text = out.read_text()
    assert "## Per-journal share" in text
    assert "| other-j |" in text and "| jama |" in text
    assert "not-there" in text and "absent" in text
    assert "max_pages" in text and "recover_letters" in text
    assert "icite_is_research" in text and "reply_title" in text and "dup_of_earlier_non_letter" in text
    assert "research -> commentary" in text
    # JAMA's research->commentary share: pmid 2 of research pmids {1,2} = 50.0%
    assert "50.0%" in text
    rows = {l.split("|")[1].strip(): [c.strip() for c in l.split("|")[2:-1]]
            for l in text.splitlines() if l.startswith("| ") and l.count("|") == 6}
    # columns: title, icite_is_research, reply_title, dup_of_earlier_non_letter
    assert rows["3"] == ["A study", "yes", "no", "yes"]   # dup of earlier non-letter
    assert rows["6"] == ["Plain", "", "no", "no"]         # neither signal
    assert rows["4"] == ["Foo-Reply", "no", "yes", "no"]  # reply, not a dup
    # read-only: impact.db has no doc_class column
    assert "doc_class" not in [r[1] for r in fetch(env.impact, "PRAGMA table_info(papers)")]
