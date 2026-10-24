"""Inputs for doc_class classification and the byline written into impact.db."""
import json
import sqlite3
from typing import Dict, Iterable, List, Optional, Tuple

CHUNK = 500


def chunks(seq: List, n: int = CHUNK):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def open_ro(path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def fetch_class_inputs(full, icite, pmids: List[int]) -> Dict[int, dict]:
    """pmid -> {pub_types, has_abstract, page_count, title, pub_type, icite_is_research}.

    pmids absent from pubmed_full are absent from the result. icite is a
    connection (or None); icite_is_research is None when iCite lacks the pmid."""
    out: Dict[int, dict] = {}
    for part in chunks(pmids):
        q = ",".join("?" * len(part))
        for pmid, types, abs_, pages, title, pub_type in full.execute(
                f"SELECT pmid, pub_types, has_abstract, page_count, title, pub_type "
                f"FROM pubmed WHERE pmid IN ({q})", part):
            out[pmid] = {"pub_types": json.loads(types) if types else [],
                         "has_abstract": None if abs_ is None else bool(abs_),
                         "page_count": pages, "title": title, "pub_type": pub_type,
                         "icite_is_research": None}
        if icite is not None:
            for pmid, flag in icite.execute(
                    f"SELECT pmid, is_research_article FROM metadata WHERE pmid IN ({q})", part):
                if pmid in out:
                    out[pmid]["icite_is_research"] = bool(flag)
    return out


def format_author(last_name, fore_name, collective) -> Optional[str]:
    """'Last, Fore' ; collective name alone; last name alone if no fore name."""
    if collective:
        return collective
    if not last_name:
        return None
    return f"{last_name}, {fore_name}" if fore_name else last_name



def fetch_bylines(full, pmids: List[int]) -> Dict[int, Dict[str, tuple]]:
    """pmid -> {'first': (name, affil|None), 'last': (name, affil|None)}.

    affil is (institution, city, state, country) from the author's lowest
    affil_order, or None when the author has no affiliation row."""
    out: Dict[int, Dict[str, tuple]] = {}
    for part in chunks(pmids):
        q = ",".join("?" * len(part))
        authors: Dict[int, List[tuple]] = {}
        for row in full.execute(
                f"SELECT pmid, position, last_name, fore_name, collective_name FROM authors "
                f"WHERE pmid IN ({q}) ORDER BY pmid, position", part):
            authors.setdefault(row[0], []).append(row[1:])
        affils: Dict[Tuple[int, int], tuple] = {}
        for pmid, pos, inst, city, state, country in full.execute(
                f"SELECT aa.pmid, aa.position, s.institution, s.city, s.state, s.country "
                f"FROM author_affils aa JOIN affil_strings s ON s.affil_id = aa.affil_id "
                f"WHERE aa.pmid IN ({q}) ORDER BY aa.pmid, aa.position, aa.affil_order DESC", part):
            affils[(pmid, pos)] = (inst, city, state, country)  # lowest order written last
        for pmid, rows in authors.items():
            ends = {}
            for key, row in (("first", rows[0]), ("last", rows[-1])):
                ends[key] = (format_author(row[1], row[2], row[3]), affils.get((pmid, row[0])))
            out[pmid] = ends
    return out
