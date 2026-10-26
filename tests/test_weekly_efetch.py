"""Tests for the weekly update's EFetch path (scripts/run_weekly_update.py).

All network calls are mocked; every database and data directory lives in tmp_path.
"""
import importlib.util
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from src.pipeline.db_manager import DatabaseManager
from src.pipeline.journal_flags import decode_deltas

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "pubmed_records.xml"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


weekly = _load("run_weekly_update")


def _resp(content: bytes):
    r = mock.Mock()
    r.content = content
    r.text = content.decode()
    r.raise_for_status = mock.Mock()
    return r


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    for k in list(weekly.FAILED_PMIDS):
        weekly.FAILED_PMIDS[k] = []
    monkeypatch.setattr(weekly.time, "sleep", lambda *_: None)


# ------------------------------------------------------------------ #
#  efetch_batch
# ------------------------------------------------------------------ #

def test_failed_pmids_has_efetch_key_not_esummary():
    assert "efetch" in weekly.FAILED_PMIDS
    assert "esummary" not in weekly.FAILED_PMIDS
    assert "icite" in weekly.FAILED_PMIDS


def test_efetch_batch_returns_full_records():
    with mock.patch.object(weekly.requests, "post",
                           return_value=_resp(FIXTURE.read_bytes())) as post:
        recs = weekly.efetch_batch([1001, 1002])
    assert post.call_count == 1
    url = post.call_args.args[0]
    assert url.endswith("/efetch.fcgi")
    data = post.call_args.kwargs["data"]
    assert data["retmode"] == "xml" and data["db"] == "pubmed"
    assert data["id"] == "1001,1002"
    by = {r["pmid"]: r for r in recs}
    assert by[1001]["has_abstract"] is True
    assert by[1002]["has_abstract"] is False
    assert [a["last_name"] for a in by[1001]["authors"]] == ["Adams", "Baker"]
    assert by[1001]["pub_date"] == "2020-03-01"
    assert by[1001]["issns"] == ["1234-5678"]
    assert weekly.FAILED_PMIDS["efetch"] == []


def test_efetch_batch_chunks_at_200():
    pmids = list(range(1, 451))
    with mock.patch.object(weekly.requests, "post",
                           return_value=_resp(b"<PubmedArticleSet/>")) as post:
        weekly.efetch_batch(pmids)
    sizes = [len(c.kwargs["data"]["id"].split(",")) for c in post.call_args_list]
    assert sizes == [200, 200, 50]


def test_failed_batch_goes_to_failed_pmids():
    with mock.patch.object(weekly.requests, "post", side_effect=RuntimeError("503")):
        recs = weekly.efetch_batch([1001, 1002])
    assert recs == []
    assert weekly.FAILED_PMIDS["efetch"] == [1001, 1002]


def test_unparseable_batch_goes_to_failed_pmids():
    with mock.patch.object(weekly.requests, "post",
                           return_value=_resp(b"<PubmedArticleSet><PubmedArticle>")):
        recs = weekly.efetch_batch([1001, 1002])
    assert recs == []
    assert weekly.FAILED_PMIDS["efetch"] == [1001, 1002]


def test_no_script_lets_icite_set_is_research():
    """iCite's is_research_article is evidence for classify() only."""
    for name in ("run_weekly_update.py", "run_pipeline_bulk.py"):
        src = (SCRIPTS / name).read_text()
        assert not re.search(r"UPDATE papers SET is_research\b", src), name
        for line in src.splitlines():
            if "is_research_article" in line:
                assert not re.search(r"(\bis_research\s*=|[\"']is_research[\"']\s*:)", line), \
                    f"{name}: {line.strip()}"


def test_no_pubmed_bulk_readers_remain():
    for path in list((ROOT / "src").rglob("*.py")) + list(SCRIPTS.glob("*.py")):
        for line in path.read_text().splitlines():
            if "pubmed_bulk" in line or "PUBMED_BULK" in line:
                assert line.strip().startswith("#"), f"{path.name}: {line.strip()}"


# ------------------------------------------------------------------ #
#  End to end: main() against temp DBs
# ------------------------------------------------------------------ #

def _article(pmid, pub_types, abstract, pgn, authors_xml):
    types = "".join(f"<PublicationType>{t}</PublicationType>" for t in pub_types)
    abs_xml = "<Abstract><AbstractText>Text.</AbstractText></Abstract>" if abstract else ""
    pg = f"<Pagination><MedlinePgn>{pgn}</MedlinePgn></Pagination>" if pgn else ""
    return f"""<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID>
<Article><Journal><ISSN IssnType="Print">1234-5678</ISSN>
<JournalIssue><PubDate><Year>2026</Year><Month>Sep</Month></PubDate></JournalIssue></Journal>
<ArticleTitle>Paper {pmid}</ArticleTitle>{pg}{abs_xml}
<AuthorList>{authors_xml}</AuthorList>
<PublicationTypeList>{types}</PublicationTypeList></Article>
<MedlineJournalInfo><ISSNLinking>1234-5679</ISSNLinking></MedlineJournalInfo>
</MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.9/{pmid}</ArticleId>
</ArticleIdList></PubmedData></PubmedArticle>"""


AUTH = ('<Author><LastName>Adams</LastName><ForeName>Ann</ForeName>'
        '<AffiliationInfo><Affiliation>Dept X, Harvard University, Boston, MA, USA.'
        '</Affiliation></AffiliationInfo></Author>'
        '<Author><CollectiveName>Study Group</CollectiveName></Author>'
        '<Author><LastName>Zed</LastName></Author>')

XML = ("<PubmedArticleSet>"
       # Journal Article, no abstract, 10 pages: research until iCite says no
       + _article(3001, ["Journal Article"], False, "1-10", AUTH)
       # same shape but iCite has no record: stays research
       + _article(3002, ["Journal Article"], False, "1-10", AUTH)
       # ordinary research paper with abstract
       + _article(3003, ["Journal Article"], True, "1-10", AUTH)
       # review, cited by 3003
       + _article(3004, ["Journal Article", "Review"], True, "1-20", AUTH)
       + "</PubmedArticleSet>").encode()


@pytest.fixture
def env(tmp_path, monkeypatch):
    impact = tmp_path / "impact.db"
    db = DatabaseManager(str(impact))
    db.init_schema()
    db.migrate_add_author_columns()
    db.add_journal("1234-5678", "Jour One", "J1", "jour-one")
    jid = db.get_journal_by_issn("1234-5678")["id"]
    # an older paper already in the DB that the new paper 3003 cites
    db.add_papers_bulk([{"pmid": 500, "journal_id": jid, "title": "Old", "pub_date": "2025-01-01",
                         "pub_year": 2025, "pub_month": 1, "pub_type": "Journal Article",
                         "is_research": 1, "doi": None}])
    db.close()

    data_dir = tmp_path / "site"
    (data_dir / "journals").mkdir(parents=True)
    settled = {"month": "2020-03", "rolling_if": 1.0, "rolling_if_no_reviews": 1.0,
               "papers": 30, "research": 5, "reviews": 25, "citations": 30,
               "citable_papers": 30, "citable_citations": 30, "inferred_papers": 0,
               "by_type": {"research": {"papers": 5, "citations": 5},
                           "review": {"papers": 25, "citations": 25}},
               "pub_by_type": {}}
    (data_dir / "journals" / "jour-one.json").write_text(json.dumps({
        "journal": "Jour One", "slug": "jour-one", "issn": "1234-5678",
        "latest": {}, "flags": ["stale"],
        "timeseries": [settled], "timeseries_12mo": [], "timeseries_5yr": []}))
    (data_dir / "index.json").write_text(json.dumps({"journals": [
        {"slug": "jour-one", "name": "Jour One", "issn": "1234-5678", "latest_if": 0,
         "flags": ["stale"]}]}))

    full = tmp_path / "pubmed_full.db"
    monkeypatch.setattr(weekly, "DB_PATH", str(impact))
    monkeypatch.setattr(weekly, "PUBMED_FULL_DB_PATH", str(full))
    monkeypatch.setattr(weekly, "WEBSITE_DATA_DIR", str(data_dir))
    monkeypatch.setattr(weekly, "REPO_ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(weekly, "esearch_recent", lambda days: [3001, 3002, 3003, 3004])
    monkeypatch.setattr(weekly.requests, "post", mock.Mock(return_value=_resp(XML)))

    def fake_icite(pmids, batch_size=200):
        out = {3001: {"references": [], "icite_is_research": False},
               3003: {"references": [500, 3004], "icite_is_research": True},
               3004: {"references": [], "icite_is_research": False}}
        return {p: out[p] for p in pmids if p in out}
    monkeypatch.setattr(weekly, "fetch_icite_references", fake_icite)
    monkeypatch.setattr(sys, "argv", ["run_weekly_update.py", "--days", "3"])
    return {"impact": impact, "full": full, "data": data_dir, "jid": jid}


def _paper(env, pmid):
    c = sqlite3.connect(env["impact"])
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM papers WHERE pmid = ?", (pmid,)).fetchone()
    c.close()
    return dict(row) if row else None


def test_main_classifies_and_reclassifies_with_icite_evidence(env):
    weekly.main()
    p1 = _paper(env, 3001)  # no abstract + iCite not research -> commentary (R25)
    assert (p1["doc_class"], p1["class_source"], p1["is_research"]) == ("commentary", "inferred", 0)
    assert p1["pub_type"] == "Journal Article"  # PubMed's type is never overwritten
    p2 = _paper(env, 3002)  # iCite lacks it: no evidence, stays research
    assert (p2["doc_class"], p2["class_source"], p2["is_research"]) == ("research", "pubmed", 1)
    p4 = _paper(env, 3004)  # a review stays a review whatever iCite says
    assert (p4["doc_class"], p4["class_source"], p4["is_research"]) == ("review", "pubmed", 0)
    assert p4["pub_type"] == "Review"
    p3 = _paper(env, 3003)
    assert p3["pub_date"] == "2026-09-01" and p3["doi"] == "10.9/3003"


def test_main_writes_r4_byline_fields(env):
    weekly.main()
    p = _paper(env, 3003)
    assert p["first_author_name"] == "Adams, Ann"
    assert p["last_author_name"] == "Zed"      # last name alone when no fore name
    assert p["first_author_country"] == "USA"
    assert p["first_author_city"] == "Boston"
    assert p["last_author_institution"] is None  # no affiliation


def test_main_stores_records_and_bylines_in_pubmed_full(env):
    weekly.main()
    c = sqlite3.connect(env["full"])
    rows = dict(c.execute("SELECT pmid, has_abstract FROM pubmed").fetchall())
    assert rows == {3001: 0, 3002: 0, 3003: 1, 3004: 1}
    types = json.loads(c.execute("SELECT pub_types FROM pubmed WHERE pmid=3004").fetchone()[0])
    assert types == ["Journal Article", "Review"]
    authors = c.execute("SELECT position, last_name, fore_name, collective_name FROM authors "
                        "WHERE pmid=3003 ORDER BY position").fetchall()
    assert authors == [(1, "Adams", "Ann", None), (2, None, None, "Study Group"),
                       (3, "Zed", None, None)]
    n_aff = c.execute("SELECT COUNT(*) FROM author_affils WHERE pmid=3003").fetchone()[0]
    assert n_aff == 1


def test_main_adds_citation_events(env):
    weekly.main()
    c = sqlite3.connect(env["impact"])
    cites = c.execute("SELECT cited_pmid, citing_pmid, citing_date FROM citations "
                      "ORDER BY cited_pmid").fetchall()
    assert cites == [(500, 3003, "2026-09-01"), (3004, 3003, "2026-09-01")]


def test_main_refreshes_classes_file_and_flags(env):
    weekly.main()
    classes = json.loads((env["data"] / "classes" / "jour-one.json").read_text())
    assert decode_deltas(classes["citable"]) == [500, 3002, 3003, 3004]
    assert decode_deltas(classes["noncitable"]) == [3001]
    # Settled 2020-03 point: 5 research, 25 reviews of 30 citable
    expected = ["small_research_sample", "review_journal"]
    j = json.loads((env["data"] / "journals" / "jour-one.json").read_text())
    assert j["flags"] == expected
    now = datetime.now()
    assert j["timeseries"][-1]["month"] == f"{now.year}-{now.month:02d}"
    idx = json.loads((env["data"] / "index.json").read_text())
    assert idx["journals"][0]["flags"] == expected


def test_main_records_efetch_failures(env, monkeypatch):
    monkeypatch.setattr(weekly.requests, "post", mock.Mock(side_effect=RuntimeError("503")))
    weekly.main()
    assert weekly.FAILED_PMIDS["efetch"] == [3001, 3002, 3003, 3004]
    out = env["full"].parent / "data" / "failed_pmids_efetch.txt"
    assert out.read_text().split() == ["3001", "3002", "3003", "3004"]
    assert _paper(env, 3001) is None


# ------------------------------------------------------------------ #
#  run_pipeline_bulk: classify with iCite evidence, read pubmed_full.db
# ------------------------------------------------------------------ #

def test_pipeline_bulk_classifies_from_pubmed_full(tmp_path):
    from src.pipeline.pubmed_full_db import open_full_db, store_records
    from src.pipeline.pubmed_xml import iter_pubmed_xml
    import io

    bulk_mod = _load("run_pipeline_bulk")
    full_path = tmp_path / "pubmed_full.db"
    full = open_full_db(str(full_path))
    recs = [r for k, r in iter_pubmed_xml(io.BytesIO(XML)) if k == "record"]
    store_records(full, recs, lambda r: True)
    full.close()

    icite_path = tmp_path / "icite_bulk.db"
    c = sqlite3.connect(icite_path)
    c.execute("CREATE TABLE metadata (pmid INTEGER PRIMARY KEY, "
              "is_research_article INTEGER, cited_by TEXT)")
    c.executemany("INSERT INTO metadata VALUES (?,?,?)",
                  [(3001, 0, ""), (3003, 1, ""), (3004, 0, "")])
    c.commit()
    c.close()

    db = DatabaseManager(str(tmp_path / "impact.db"))
    db.init_schema()
    db.migrate_add_author_columns()
    bulk = bulk_mod.open_bulk_db(str(full_path))
    icite_bulk = bulk_mod.open_icite_bulk_db(str(icite_path))
    icite = mock.Mock()
    icite.fetch_batch.return_value = {}
    bulk_mod.process_journal("1234-5679", {"name": "J", "slug": "j"}, db, icite, bulk,
                             2026, 2026, icite_bulk=icite_bulk)
    got = {r[0]: tuple(r[1:]) for r in db.conn.execute(
        "SELECT pmid, doc_class, class_source, is_research, pub_type FROM papers")}
    db.close()
    assert got == {
        3001: ("commentary", "inferred", 0, "Journal Article"),
        3002: ("research", "pubmed", 1, "Journal Article"),   # not in iCite: no evidence
        3003: ("research", "pubmed", 1, "Journal Article"),
        3004: ("review", "pubmed", 0, "Review"),
    }


def test_icite_evidence_values():
    from src.pipeline.doc_class import icite_evidence
    assert [icite_evidence(v) for v in (True, False, 1, 0, "Yes", "No", None, "", "?")] == \
        [True, False, True, False, True, False, None, None, None]


def test_pipeline_bulk_author_fields_from_shared_byline(tmp_path):
    """R28: Step 5 uses the R4 byline from pubmed_full.db; no byline -> untouched."""
    from src.pipeline.pubmed_full_db import open_full_db, store_records
    from src.pipeline.pubmed_xml import iter_pubmed_xml
    import io

    bulk_mod = _load("run_pipeline_bulk")
    full_path = tmp_path / "pubmed_full.db"
    full = open_full_db(str(full_path))
    recs = [r for k, r in iter_pubmed_xml(io.BytesIO(XML)) if k == "record"]
    store_records(full, recs, lambda r: r["pmid"] != 3002)  # 3002: record, no byline
    inst, city, country = full.execute(
        "SELECT institution, city, country FROM affil_strings").fetchone()
    full.close()

    db = DatabaseManager(str(tmp_path / "impact.db"))
    db.init_schema()
    db.migrate_add_author_columns()
    jid = db.add_journal("1234-5679", "J", None, "j")
    db.add_papers_bulk([{"pmid": 3002, "journal_id": jid, "title": "P", "pub_date": "2026-09-01",
                         "pub_year": 2026, "pub_month": 9, "pub_type": "Journal Article",
                         "is_research": 1, "doi": None}])
    db.conn.execute("UPDATE papers SET first_author_name='Old, Name', "
                    "first_author_institution='Old Inst', last_author_name='Old, Last' "
                    "WHERE pmid=3002")
    db.conn.commit()
    bulk = bulk_mod.open_bulk_db(str(full_path))
    icite = mock.Mock()
    icite.fetch_batch.return_value = {}
    bulk_mod.process_journal("1234-5679", {"name": "J", "slug": "j"}, db, icite, bulk,
                             2026, 2026, icite_bulk=None)
    rows = {r["pmid"]: dict(r) for r in db.conn.execute("SELECT * FROM papers")}
    db.close()
    p = rows[3003]
    assert (p["first_author_name"], p["last_author_name"]) == ("Adams, Ann", "Zed")
    assert (p["first_author_institution"], p["first_author_city"],
            p["first_author_country"]) == (inst, city, country)
    assert p["last_author_institution"] is None
    old = rows[3002]
    assert (old["first_author_name"], old["first_author_institution"],
            old["last_author_name"]) == ("Old, Name", "Old Inst", "Old, Last")


# ------------------------------------------------------------------ #
#  Fix round 1: no silent drops; insert + byline in one transaction
# ------------------------------------------------------------------ #

def test_pmid_missing_from_successful_response_is_failed():
    one = ("<PubmedArticleSet>" + _article(3003, ["Journal Article"], True, "1-10", AUTH)
           + "</PubmedArticleSet>").encode()
    with mock.patch.object(weekly.requests, "post", return_value=_resp(one)):
        recs = weekly.efetch_batch([3003, 3009])
    assert [r["pmid"] for r in recs] == [3003]
    assert weekly.FAILED_PMIDS["efetch"] == [3009]


def test_unparsable_record_counts_as_failed():
    nodate = _article(3005, ["Journal Article"], True, "1-10", AUTH).replace(
        "<PubDate><Year>2026</Year><Month>Sep</Month></PubDate>", "<PubDate></PubDate>")
    body = ("<PubmedArticleSet>" + nodate + _article(3003, ["Journal Article"], True, "1-10", AUTH)
            + "</PubmedArticleSet>").encode()
    with mock.patch.object(weekly.requests, "post", return_value=_resp(body)):
        recs = weekly.efetch_batch([3003, 3005])
    assert [r["pmid"] for r in recs] == [3003]
    assert weekly.FAILED_PMIDS["efetch"] == [3005]


@pytest.mark.parametrize("body", [
    b"<eFetchResult><ERROR>Empty id list - nothing todo</ERROR></eFetchResult>",
    b"",
    b"<PubmedArticleSet></PubmedArticleSet>",
])
def test_error_or_empty_body_counts_whole_chunk(body):
    with mock.patch.object(weekly.requests, "post", return_value=_resp(body)):
        recs = weekly.efetch_batch([1001, 1002])
    assert recs == []
    assert weekly.FAILED_PMIDS["efetch"] == [1001, 1002]


def test_byline_failure_rolls_back_paper_insert(env, monkeypatch):
    def boom(conn, bylines):
        conn.execute("UPDATE papers SET first_author_name = 'partial'")
        raise RuntimeError("disk I/O error")
    monkeypatch.setattr(weekly, "write_bylines", boom)
    with pytest.raises(RuntimeError):
        weekly.main()
    for pmid in (3001, 3002, 3003, 3004):
        assert _paper(env, pmid) is None
    assert _paper(env, 500)["first_author_name"] is None


def test_update_index_copies_settled_rates(tmp_path):
    (tmp_path / "index.json").write_text(json.dumps(
        {"journals": [{"slug": "j", "latest_if": 1.0, "settled_if": 9.0}]}))
    weekly.update_index(str(tmp_path), {"j": {
        "rolling_if": 11.5, "rolling_if_no_reviews": 11.4, "paper_count": 10, "month": "2026-10",
        "flags": [], "settled_month": "2025-10", "settled_if": 34.5, "settled_if_no_reviews": 33.7}})
    entry = json.loads((tmp_path / "index.json").read_text())["journals"][0]
    assert entry["latest_if"] == 11.5
    assert (entry["settled_month"], entry["settled_if"], entry["settled_if_no_reviews"]) == ("2025-10", 34.5, 33.7)
