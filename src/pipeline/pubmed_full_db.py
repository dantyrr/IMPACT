"""pubmed_full.db: every PubMed record, plus full bylines for tracked journals.

Affiliation strings are stored once in ``affil_strings`` (parsed once, on first
insert) and referenced by integer id, which keeps the author tables compact.
"""
import json
import os
import sqlite3
from typing import Callable

from .affil_institution import describe
from .affil_location import parse_location, parse_locations
from .config import ISSN_BULK_MAP

_CACHE_LIMIT = 2_000_000

# Indexes: pubmed(issn) and pubmed(pub_year, pub_month) mirror pubmed_bulk.db.
# authors/author_affils/affil_countries need only their primary keys;
# affil_strings.text is UNIQUE (needed for dedup lookups).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS pubmed (
    pmid         INTEGER PRIMARY KEY,
    issn         TEXT,
    pub_year     INTEGER,
    pub_month    INTEGER,
    title        TEXT,
    first_author TEXT,
    first_affil  TEXT,
    last_author  TEXT,
    last_affil   TEXT,
    pub_type     TEXT,
    doi          TEXT,
    pub_types    TEXT,
    has_abstract INTEGER,
    pagination   TEXT,
    page_count   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_pubmed_issn ON pubmed(issn);
CREATE INDEX IF NOT EXISTS idx_pubmed_year ON pubmed(pub_year, pub_month);
CREATE TABLE IF NOT EXISTS authors (
    pmid            INTEGER NOT NULL,
    position        INTEGER NOT NULL,
    last_name       TEXT,
    fore_name       TEXT,
    initials        TEXT,
    collective_name TEXT,
    orcid           TEXT,
    PRIMARY KEY (pmid, position)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS affil_strings (
    affil_id         INTEGER PRIMARY KEY,
    text             TEXT UNIQUE,
    ror_id           TEXT,
    country          TEXT,
    state            TEXT,
    city             TEXT,
    institution      TEXT,
    institution_type TEXT
);
CREATE TABLE IF NOT EXISTS affil_countries (
    affil_id   INTEGER NOT NULL,
    part_order INTEGER NOT NULL,
    country    TEXT NOT NULL,
    PRIMARY KEY (affil_id, part_order)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS author_affils (
    pmid        INTEGER NOT NULL,
    position    INTEGER NOT NULL,
    affil_order INTEGER NOT NULL,
    affil_id    INTEGER NOT NULL,
    PRIMARY KEY (pmid, position, affil_order)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS processed_files (
    filename     TEXT PRIMARY KEY,
    kind         TEXT,
    processed_at TEXT NOT NULL,
    record_count INTEGER NOT NULL
);
"""

# text -> affil_id, one dict per open connection (keyed by id(conn); reset on open)
_affil_caches: dict = {}


def open_full_db(path: str) -> sqlite3.Connection:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-131072")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.executescript(_SCHEMA)
    conn.commit()
    _affil_caches[id(conn)] = {}
    return conn


def make_byline_scope(tracked_issns: set, first_year: int = 2003,
                      last_year: int = 2026) -> Callable[[dict], bool]:
    tracked = set(tracked_issns)

    def in_scope(rec: dict) -> bool:
        year = rec.get("pub_year")
        if year is None or not (first_year <= year <= last_year):
            return False
        issns = [rec.get("issn")] + list(rec.get("issns") or [])
        return any(i in tracked for i in issns if i)

    return in_scope


def tracked_issns_from_impact(impact_db_path: str) -> set:
    conn = sqlite3.connect(f"file:{impact_db_path}?mode=ro", uri=True)
    try:
        issns = {r[0] for r in conn.execute("SELECT issn FROM journals") if r[0]}
    finally:
        conn.close()
    for k, v in ISSN_BULK_MAP.items():
        issns.update((k, v))
    return issns


def _affil_id(conn, cache: dict, text: str, ror_id) -> int:
    aid = cache.get(text)
    if aid is not None:
        return aid
    row = conn.execute("SELECT affil_id FROM affil_strings WHERE text = ?", (text,)).fetchone()
    if row:
        aid = row[0]
    else:
        loc = parse_location(text)
        inst = None
        for part in describe(text):
            if part.institution is not None:
                inst = part.institution
        cur = conn.execute(
            "INSERT INTO affil_strings (text, ror_id, country, state, city, "
            "institution, institution_type) VALUES (?,?,?,?,?,?,?)",
            (text, ror_id, loc.country, loc.state, loc.city,
             inst.name if inst else None, inst.type if inst else None))
        aid = cur.lastrowid
        conn.executemany(
            "INSERT INTO affil_countries (affil_id, part_order, country) VALUES (?,?,?)",
            [(aid, i, l.country) for i, l in enumerate(parse_locations(text)) if l.country])
    if len(cache) >= _CACHE_LIMIT:
        cache.clear()
    cache[text] = aid
    return aid


def _delete_byline(conn, pmids):
    conn.executemany("DELETE FROM authors WHERE pmid = ?", [(p,) for p in pmids])
    conn.executemany("DELETE FROM author_affils WHERE pmid = ?", [(p,) for p in pmids])


def store_records(conn, records: list, in_scope: Callable[[dict], bool]) -> None:
    with conn:  # one transaction
        conn.executemany(
            "INSERT OR REPLACE INTO pubmed (pmid, issn, pub_year, pub_month, title, "
            "first_author, first_affil, last_author, last_affil, pub_type, doi, "
            "pub_types, has_abstract, pagination, page_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(r["pmid"], r.get("issn"), r.get("pub_year"), r.get("pub_month"),
              r.get("title"), r.get("first_author"), r.get("first_affil"),
              r.get("last_author"), r.get("last_affil"), r.get("pub_type"),
              r.get("doi"), json.dumps(r.get("pub_types") or []),
              int(bool(r.get("has_abstract"))), r.get("pagination"),
              r.get("page_count")) for r in records])
        scoped = [r for r in records if in_scope(r)]
        # A re-delivered record may have lost authors, so clear old rows first.
        # Also clear when a record has dropped out of scope.
        _delete_byline(conn, [r["pmid"] for r in records])
        cache = _affil_caches.setdefault(id(conn), {})
        for r in scoped:
            pmid = r["pmid"]
            conn.executemany(
                "INSERT INTO authors (pmid, position, last_name, fore_name, initials, "
                "collective_name, orcid) VALUES (?,?,?,?,?,?,?)",
                [(pmid, a["position"], a.get("last_name"), a.get("fore_name"),
                  a.get("initials"), a.get("collective_name"), a.get("orcid"))
                 for a in r.get("authors") or []])
            links = []
            for a in r.get("authors") or []:
                seen = set()
                for order, af in enumerate(a.get("affiliations") or []):
                    text = af.get("text")
                    if not text:
                        continue
                    aid = _affil_id(conn, cache, text, af.get("ror_id"))
                    if aid in seen:
                        continue
                    seen.add(aid)
                    links.append((pmid, a["position"], order, aid))
            conn.executemany(
                "INSERT INTO author_affils (pmid, position, affil_order, affil_id) "
                "VALUES (?,?,?,?)", links)


def delete_pmids(conn, pmids: list) -> None:
    with conn:
        _delete_byline(conn, pmids)
        conn.executemany("DELETE FROM pubmed WHERE pmid = ?", [(p,) for p in pmids])
