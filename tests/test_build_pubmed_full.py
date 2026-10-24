"""Tests for scripts/build_pubmed_full.py. All network I/O is mocked; DBs live in tmp_path."""
import gzip
import importlib.util
import logging
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_pubmed_full.py"
_spec = importlib.util.spec_from_file_location("build_pubmed_full", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

TRACKED = "1111-1111"


def article(pmid, issn=TRACKED, year=2020, n_authors=2):
    authors = "".join(
        f'<Author ValidYN="Y"><LastName>L{pmid}x{i}</LastName><ForeName>F</ForeName>'
        f'<Initials>F</Initials><AffiliationInfo><Affiliation>Univ {i}, Boston, MA, USA.'
        f'</Affiliation></AffiliationInfo></Author>' for i in range(n_authors))
    return (f'<PubmedArticle><MedlineCitation Status="MEDLINE" Owner="NLM">'
            f'<PMID Version="1">{pmid}</PMID><Article PubModel="Print"><Journal>'
            f'<ISSN IssnType="Print">{issn}</ISSN><JournalIssue CitedMedium="Print"><PubDate>'
            f'<Year>{year}</Year><Month>Mar</Month></PubDate></JournalIssue></Journal>'
            f'<ArticleTitle>T{pmid}</ArticleTitle><AuthorList CompleteYN="Y">{authors}</AuthorList>'
            f'<PublicationTypeList><PublicationType>Journal Article</PublicationType>'
            f'</PublicationTypeList></Article><MedlineJournalInfo><ISSNLinking>{issn}'
            f'</ISSNLinking></MedlineJournalInfo></MedlineCitation></PubmedArticle>')


def delete(*pmids):
    return "<DeleteCitation>" + "".join(f"<PMID Version=\"1\">{p}</PMID>" for p in pmids) \
        + "</DeleteCitation>"


def gz(*parts):
    return gzip.compress(("<?xml version=\"1.0\"?><PubmedArticleSet>" + "".join(parts)
                          + "</PubmedArticleSet>").encode())


def scope():
    return mod.make_byline_scope({TRACKED})


def count(conn, table, pmid=None):
    if pmid is None:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE pmid=?", (pmid,)).fetchone()[0]


class FakeFTP:
    """Directory listings + file bodies keyed by URL; records every download."""

    def __init__(self, baseline, updates=None):
        self.files = {mod.BASELINE_URL + k: v for k, v in baseline.items()}
        self.files.update({mod.UPDATE_URL + k: v for k, v in (updates or {}).items()})
        self.listing = {mod.BASELINE_URL: sorted(baseline), mod.UPDATE_URL: sorted(updates or {})}
        self.downloads = []
        self.fail = set()

    def list_files(self, base_url, session):
        return list(self.listing[base_url])

    def download_file(self, url, session, retries=3):
        self.downloads.append(url)
        if url.rsplit("/", 1)[1] in self.fail:
            raise OSError("simulated download failure")
        return self.files[url]


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(mod, "DATA_DIR", str(data))
    monkeypatch.setattr(mod, "FULL_DB_PATH", str(data / "pubmed_full.db"))
    monkeypatch.setattr(mod, "SAMPLE_DB_PATH", str(data / "pubmed_full.sample.db"))
    monkeypatch.setattr(mod, "rebuild_lock_held", lambda: True)
    monkeypatch.setattr(mod, "tracked_issns_from_impact", lambda p: {TRACKED})
    monkeypatch.setattr(mod, "free_gb", lambda p: 1000.0)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return data


def install(monkeypatch, ftp):
    monkeypatch.setattr(mod, "list_files", ftp.list_files)
    monkeypatch.setattr(mod, "download_file", ftp.download_file)
    return ftp


def run_main(argv):
    return mod.main(argv)


def full_conn(env):
    return sqlite3.connect(str(env / "pubmed_full.db"))


# ---- plan_files ----

def test_update_files_use_update_url():
    plan = mod.plan_files(["pubmed26n0001.xml.gz"], ["pubmed26n1335.xml.gz"])
    assert plan[0][0].endswith("/pubmed/baseline/pubmed26n0001.xml.gz")
    assert plan[1][0].endswith("/pubmed/updatefiles/pubmed26n1335.xml.gz")


def test_plan_orders_baseline_then_updates_by_name():
    plan = mod.plan_files(["b2.xml.gz", "b1.xml.gz"], ["u2.xml.gz", "u1.xml.gz"])
    assert [f for _, f in plan] == ["b1.xml.gz", "b2.xml.gz", "u1.xml.gz", "u2.xml.gz"]
    assert all(url.endswith("/" + f) for url, f in plan)


# ---- download_file ----

def test_download_file_fetches_the_given_url_with_retries(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"ab"
            yield b"cd"

    class Session:
        def get(self, url, timeout, stream):
            calls.append(url)
            if len(calls) == 1:
                raise OSError("reset")
            return Resp()

    url = mod.UPDATE_URL + "pubmed26n1335.xml.gz"
    assert mod.download_file(url, Session()) == b"abcd"
    assert calls == [url, url]


# ---- process_file ----

def test_file_marked_only_after_commit(tmp_path, monkeypatch):
    conn = mod.open_full_db(str(tmp_path / "full.db"))
    monkeypatch.setattr(mod, "CHUNK_SIZE", 2)
    body = gz(*(article(p) for p in range(1, 6)))
    monkeypatch.setattr(mod, "download_file", lambda url, session, retries=3: body)
    real_store = mod.store_records
    calls = []

    def dying_store(c, records, in_scope):
        calls.append(len(records))
        if len(calls) == 2:
            raise KeyboardInterrupt("killed mid-file")
        real_store(c, records, in_scope)

    monkeypatch.setattr(mod, "store_records", dying_store)
    url = mod.BASELINE_URL + "f1.xml.gz"
    with pytest.raises(KeyboardInterrupt):
        mod.process_file(conn, url, "f1.xml.gz", scope())
    assert count(conn, "processed_files") == 0
    assert count(conn, "pubmed") == 2  # first chunk committed

    monkeypatch.setattr(mod, "store_records", real_store)
    assert mod.process_file(conn, url, "f1.xml.gz", scope()) == 5
    assert conn.execute("SELECT COUNT(*), COUNT(DISTINCT pmid) FROM pubmed").fetchone() == (5, 5)
    assert all(count(conn, "authors", p) == 2 for p in range(1, 6))
    assert conn.execute("SELECT filename, kind, record_count FROM processed_files").fetchall() \
        == [("f1.xml.gz", "baseline", 5)]
    conn.close()


def test_record_then_delete_in_one_file_leaves_pmid_absent(tmp_path, monkeypatch):
    conn = mod.open_full_db(str(tmp_path / "full.db"))
    body = gz(article(1), article(2), delete(1))
    monkeypatch.setattr(mod, "download_file", lambda url, session, retries=3: body)
    mod.process_file(conn, mod.UPDATE_URL + "u1.xml.gz", "u1.xml.gz", scope())
    assert count(conn, "pubmed", 1) == 0 and count(conn, "authors", 1) == 0
    assert count(conn, "pubmed", 2) == 1
    assert conn.execute("SELECT kind FROM processed_files").fetchone() == ("update",)
    conn.close()


def test_delete_then_record_in_one_file_leaves_pmid_present(tmp_path, monkeypatch):
    conn = mod.open_full_db(str(tmp_path / "full.db"))
    body = gz(delete(1), article(1))
    monkeypatch.setattr(mod, "download_file", lambda url, session, retries=3: body)
    mod.process_file(conn, mod.UPDATE_URL + "u1.xml.gz", "u1.xml.gz", scope())
    assert count(conn, "pubmed", 1) == 1 and count(conn, "authors", 1) == 2
    conn.close()


# ---- main ----

def test_refuses_without_live_rebuild_lock(env, monkeypatch):
    install(monkeypatch, FakeFTP({"b1.xml.gz": gz(article(1))}))
    monkeypatch.setattr(mod, "rebuild_lock_held", lambda: False)
    assert run_main([]) == 1
    assert not (env / "pubmed_full.db").exists()


def test_low_disk_stops_cleanly(env, monkeypatch):
    ftp = install(monkeypatch, FakeFTP({"b1.xml.gz": gz(article(1))}))
    monkeypatch.setattr(mod, "free_gb", lambda p: 10.0)
    assert run_main(["--limit", "1"]) == 3
    assert ftp.downloads == []


def test_low_disk_midway_keeps_finished_files(env, monkeypatch):
    install(monkeypatch, FakeFTP({"b1.xml.gz": gz(article(1)), "b2.xml.gz": gz(article(2))}))
    free = iter([100.0, 5.0])
    monkeypatch.setattr(mod, "free_gb", lambda p: next(free))
    assert run_main(["--min-free-gb", "30"]) == 3
    c = full_conn(env)
    assert [r[0] for r in c.execute("SELECT filename FROM processed_files")] == ["b1.xml.gz"]
    c.close()


def test_full_run_applies_baseline_then_updates_and_logs_progress(env, monkeypatch, caplog):
    ftp = install(monkeypatch, FakeFTP(
        {"b2.xml.gz": gz(article(2)), "b1.xml.gz": gz(article(1), article(3))},
        {"u1.xml.gz": gz(delete(3)), "u2.xml.gz": gz(article(3, year=2021))}))
    with caplog.at_level(logging.INFO, logger=mod.logger.name):
        assert run_main([]) == 0
    assert [u.rsplit("/", 1)[1] for u in ftp.downloads] == \
        ["b1.xml.gz", "b2.xml.gz", "u1.xml.gz", "u2.xml.gz"]
    c = full_conn(env)
    assert c.execute("SELECT pub_year FROM pubmed WHERE pmid=3").fetchone() == (2021,)
    assert c.execute("SELECT filename, kind FROM processed_files ORDER BY filename").fetchall() \
        == [("b1.xml.gz", "baseline"), ("b2.xml.gz", "baseline"),
            ("u1.xml.gz", "update"), ("u2.xml.gz", "update")]
    c.close()
    assert "4 / 4 files" in caplog.text

    ftp.downloads.clear()
    assert run_main([]) == 0  # resume: nothing left to do
    assert ftp.downloads == []


def test_limit_processes_only_n_unprocessed_files(env, monkeypatch):
    ftp = install(monkeypatch, FakeFTP({f"b{i}.xml.gz": gz(article(i)) for i in range(1, 4)}))
    assert run_main(["--limit", "1"]) == 0
    assert run_main(["--limit", "1"]) == 0
    assert [u.rsplit("/", 1)[1] for u in ftp.downloads] == ["b1.xml.gz", "b2.xml.gz"]


def test_failed_file_stops_run_and_resumes_there(env, monkeypatch):
    ftp = install(monkeypatch, FakeFTP(
        {f"b{i}.xml.gz": gz(article(i)) for i in range(1, 4)}, {"u1.xml.gz": gz(delete(1))}))
    ftp.fail.add("b2.xml.gz")
    assert run_main([]) == 4
    names = [u.rsplit("/", 1)[1] for u in ftp.downloads]
    assert "b3.xml.gz" not in names and "u1.xml.gz" not in names
    c = full_conn(env)
    assert [r[0] for r in c.execute("SELECT filename FROM processed_files")] == ["b1.xml.gz"]
    assert count(c, "pubmed", 3) == 0 and count(c, "pubmed", 1) == 1
    c.close()

    ftp.fail.clear()
    ftp.downloads.clear()
    assert run_main([]) == 0
    assert [u.rsplit("/", 1)[1] for u in ftp.downloads] == ["b2.xml.gz", "b3.xml.gz", "u1.xml.gz"]
    c = full_conn(env)
    assert [r[0] for r in c.execute("SELECT pmid FROM pubmed ORDER BY pmid")] == [2, 3]
    c.close()


def test_unparsable_file_stops_run_with_code_4(env, monkeypatch):
    ftp = install(monkeypatch, FakeFTP({"b1.xml.gz": b"not gzip", "b2.xml.gz": gz(article(2))}))
    assert run_main([]) == 4
    assert all(not u.endswith("b2.xml.gz") for u in ftp.downloads)


# ---- sample / projection ----

def test_project_size_scales_by_papers_and_files(tmp_path):
    conn = mod.open_full_db(str(tmp_path / "full.db"))
    mod.store_records(conn, [mod_rec(p) for p in range(1, 201)], scope())
    sizes = dict(conn.execute(
        "SELECT m.tbl_name, SUM(s.pgsize) FROM dbstat s JOIN sqlite_master m ON s.name = m.name "
        "GROUP BY m.tbl_name"))
    author_bytes = sum(sizes.get(t, 0) for t in
                       ("authors", "affil_strings", "affil_countries", "author_affils"))
    out = mod.project_size(conn, sampled_papers=200, total_papers=2000,
                           sampled_files=2, total_files=10)
    assert out["author_tables_gb"] == pytest.approx(author_bytes * 10 / 1e9)
    assert out["pubmed_gb"] == pytest.approx(sizes["pubmed"] * 5 / 1e9)
    assert out["author_tables_gb"] > 0
    conn.close()


def mod_rec(pmid):
    from src.pipeline.pubmed_xml import iter_pubmed_xml
    import io
    return next(r for k, r in iter_pubmed_xml(io.BytesIO(gzip.decompress(gz(article(pmid))))))


def test_sample_uses_separate_db_and_spreads_files(env, monkeypatch, capsys):
    ftp = install(monkeypatch, FakeFTP({f"b{i}.xml.gz": gz(article(i)) for i in range(1, 9)},
                                       {"u1.xml.gz": gz(article(99))}))
    monkeypatch.setattr(mod, "TOTAL_PAPERS", 2)  # tiny DBs are mostly page overhead
    assert run_main(["--sample", "2"]) == 0
    assert [u.rsplit("/", 1)[1] for u in ftp.downloads] == ["b1.xml.gz", "b5.xml.gz"]
    assert (env / "pubmed_full.sample.db").exists()
    assert not (env / "pubmed_full.db").exists()
    out = capsys.readouterr().out
    assert "bytes per in-scope paper" in out and "author_tables_gb" in out


def test_sample_over_budget_exits_2(env, monkeypatch):
    install(monkeypatch, FakeFTP({f"b{i}.xml.gz": gz(article(i)) for i in range(1, 3)}))
    monkeypatch.setattr(mod, "TOTAL_PAPERS", 10**15)
    assert run_main(["--sample", "1"]) == 2


def test_empty_baseline_listing_never_applies_updates(env, monkeypatch):
    ftp = install(monkeypatch, FakeFTP({}, {"u1.xml.gz": gz(article(1))}))
    assert run_main([]) == 4
    assert ftp.downloads == []
