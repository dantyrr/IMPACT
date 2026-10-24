import sqlite3

import pytest

from src.pipeline.pubmed_full_db import (delete_pmids, make_byline_scope, open_full_db,
                                         store_records, tracked_issns_from_impact)

TRACKED = "1111-1111"


def author(pos, affils=(), last="Doe"):
    return {"position": pos, "last_name": last, "fore_name": "J", "initials": "J",
            "collective_name": None, "orcid": None,
            "affiliations": [{"text": t, "ror_id": None} for t in affils]}


def rec(pmid, authors, issn=TRACKED, year=2020):
    return {"pmid": pmid, "issn": issn, "issns": [issn], "pub_year": year, "pub_month": 3,
            "title": f"T{pmid}", "doi": None, "pub_types": ["Journal Article"],
            "pub_type": "Journal Article", "has_abstract": True, "pagination": "1-5",
            "page_count": 5, "first_author": None, "first_affil": None,
            "last_author": None, "last_affil": None, "authors": authors}


@pytest.fixture
def conn(tmp_path):
    c = open_full_db(str(tmp_path / "full.db"))
    yield c
    c.close()


@pytest.fixture
def scope():
    return make_byline_scope({TRACKED})


def count(conn, table, pmid=None):
    if pmid is None:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE pmid=?", (pmid,)).fetchone()[0]


def test_affiliation_deduplicated(conn, scope):
    a = "Univ A, Boston, MA, USA."
    store_records(conn, [rec(1, [author(1, [a])]), rec(2, [author(1, [a])])], scope)
    assert count(conn, "affil_strings") == 1 and count(conn, "author_affils") == 2


def test_out_of_scope_record_has_no_byline(conn, scope):
    store_records(conn, [rec(1, [author(1, ["Univ A, Boston, MA, USA."])], issn="9999-9999")], scope)
    assert count(conn, "pubmed") == 1 and count(conn, "authors") == 0
    store_records(conn, [rec(2, [author(1)], year=2002)], scope)
    assert count(conn, "authors") == 0


def test_reversioned_record_replaces_byline(conn, scope):
    five = [author(i, [f"Univ {i}, Boston, MA, USA."]) for i in range(1, 6)]
    store_records(conn, [rec(7, five)], scope)
    store_records(conn, [rec(7, five[:3])], scope)
    pos = [r[0] for r in conn.execute("SELECT position FROM authors WHERE pmid=7 ORDER BY position")]
    assert pos == [1, 2, 3]
    assert conn.execute("SELECT MAX(position) FROM author_affils WHERE pmid=7").fetchone()[0] <= 3
    assert count(conn, "pubmed") == 1


def test_multi_country_affiliation(conn, scope):
    text = "Dept X, Boston, MA, USA; Dept Y, Oxford, UK"
    store_records(conn, [rec(1, [author(1, [text])])], scope)
    aid = conn.execute("SELECT affil_id FROM affil_strings WHERE text=?", (text,)).fetchone()[0]
    countries = [r[0] for r in conn.execute(
        "SELECT country FROM affil_countries WHERE affil_id=? ORDER BY part_order", (aid,))]
    assert countries == ["USA", "United Kingdom"]
    assert conn.execute("SELECT country FROM affil_strings WHERE affil_id=?", (aid,)).fetchone()[0] \
        == "United Kingdom"


def test_delete_removes_everything(conn, scope):
    store_records(conn, [rec(1, [author(1, ["Univ A, Boston, MA, USA."])])], scope)
    delete_pmids(conn, [1])
    assert all(count(conn, t, 1) == 0 for t in ("pubmed", "authors", "author_affils"))


def test_pubmed_row_columns(conn, scope):
    store_records(conn, [rec(1, [])], scope)
    row = conn.execute("SELECT pub_types, has_abstract, pagination, page_count FROM pubmed").fetchone()
    assert row == ('["Journal Article"]', 1, "1-5", 5)


def test_scope_uses_issns_and_year_bounds():
    s = make_byline_scope({"2222-2222"})
    r = rec(1, [], issn="3333-3333")
    r["issns"] = ["2222-2222"]
    assert s(r) and not s(rec(1, [], issn="3333-3333"))
    assert not make_byline_scope({TRACKED})(rec(1, [], year=2027))


def test_separate_connections_do_not_share_cache(tmp_path, scope):
    for name in ("a.db", "b.db"):
        c = open_full_db(str(tmp_path / name))
        store_records(c, [rec(1, [author(1, ["Univ A, Boston, MA, USA."])])], scope)
        assert count(c, "author_affils") == 1
        c.close()


def test_tracked_issns_from_impact(tmp_path):
    p = str(tmp_path / "impact.db")
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE journals (id INTEGER PRIMARY KEY, issn TEXT)")
    c.execute("INSERT INTO journals (issn) VALUES ('1111-1111')")
    c.commit()
    c.close()
    got = tracked_issns_from_impact(p)
    assert got == {"1111-1111", "1545-9993", "1545-9985"}
