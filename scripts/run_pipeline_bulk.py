#!/usr/bin/env python3
"""
IMPACT Pipeline — Bulk DB Edition

Like run_pipeline.py but uses data/pubmed_full.db for:
  - Paper discovery by ISSN  (replaces PubMed ESearch)
  - Paper metadata           (replaces PubMed ESummary)
  - Author data: the R4 byline (authors + affil_strings), same as
    apply_pubmed_full.py and the weekly update
  - Citation month lookup    (replaces fix_citation_months)

Only contacts an external API for:
  - iCite: cited_by lists (the citation links we need for rolling IF)

Requirements:
  data/pubmed_full.db must exist (run scripts/build_pubmed_full.py first).

Usage:
    python scripts/run_pipeline_bulk.py --journal bmj
    python scripts/run_pipeline_bulk.py --journal bmj nature-cell-biology nejm
    python scripts/run_pipeline_bulk.py --years 2010-2026
    python scripts/run_pipeline_bulk.py           # all journals in config
"""

import sys
import os
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.config import JOURNALS, DB_PATH, PUBMED_FULL_DB_PATH, ISSN_BULK_MAP
from src.pipeline.class_inputs import fetch_bylines, write_bylines
from src.pipeline.db_manager import DatabaseManager
from src.pipeline.doc_class import classify, icite_evidence
from src.pipeline.icite_fetcher import IciteFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline_bulk")

def open_bulk_db(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"pubmed_full.db not found at {path}\n"
            f"Run: python scripts/build_pubmed_full.py"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.execute("PRAGMA cache_size=-131072")   # 128 MB read cache
    return conn


def get_papers_from_bulk(bulk: sqlite3.Connection, issn: str,
                         year_start: int, year_end: int) -> list:
    """Return all rows for an ISSN + year range from pubmed_full.db."""
    bulk_issn = ISSN_BULK_MAP.get(issn, issn)
    return bulk.execute(
        """SELECT pmid, pub_year, pub_month, title,
                  first_author, first_affil,
                  last_author,  last_affil,
                  pub_type, doi,
                  pub_types, has_abstract, page_count
           FROM pubmed
           WHERE issn = ? AND pub_year >= ? AND pub_year <= ?
           ORDER BY pub_year, pub_month, pmid""",
        (bulk_issn, year_start, year_end),
    ).fetchall()


def get_citing_dates(bulk: sqlite3.Connection,
                     citing_pmids: set) -> dict:
    """
    Batch-lookup (year, month) for citing PMIDs from pubmed_full.db.
    Returns {pmid: (year, month)}.
    """
    if not citing_pmids:
        return {}

    # Use a temp table to avoid extremely long IN clauses
    bulk.execute("CREATE TEMP TABLE IF NOT EXISTS _c (pmid INTEGER PRIMARY KEY)")
    bulk.execute("DELETE FROM _c")
    bulk.executemany("INSERT OR IGNORE INTO _c VALUES (?)",
                     [(p,) for p in citing_pmids])
    rows = bulk.execute(
        "SELECT p.pmid, p.pub_year, p.pub_month "
        "FROM pubmed p JOIN _c c ON p.pmid = c.pmid"
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def open_icite_bulk_db(path: str) -> sqlite3.Connection:
    """Open a pre-built icite_bulk.db (from download_icite_bulk.py)."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.execute("PRAGMA cache_size=-131072")
    return conn


def get_icite_local(icite_bulk: sqlite3.Connection, pmids: list) -> dict:
    """
    Look up citation data from local icite_bulk.db.
    Returns {pmid: {"cited_by": [list], "is_research_article": bool|None}}.

    Uses a temp table + PK join on the 40M-row metadata table (fast),
    avoiding the old 893M-row citations table.
    """
    if not pmids:
        return {}

    icite_bulk.execute(
        "CREATE TEMP TABLE IF NOT EXISTS _q (pmid INTEGER PRIMARY KEY)"
    )
    icite_bulk.execute("DELETE FROM _q")
    icite_bulk.executemany("INSERT OR IGNORE INTO _q VALUES (?)",
                           [(p,) for p in pmids])

    rows = icite_bulk.execute(
        "SELECT m.pmid, m.is_research_article, m.cited_by "
        "FROM metadata m JOIN _q q ON m.pmid = q.pmid"
    ).fetchall()

    result = {}
    for pmid, is_res, cited_by_str in rows:
        cited_by = [int(x) for x in cited_by_str.split() if x] if cited_by_str else []
        result[pmid] = {"cited_by": cited_by,
                        "is_research_article": None if is_res is None else bool(is_res)}

    # Placeholder for very new papers not yet in snapshot (no iCite evidence)
    for pmid in pmids:
        if pmid not in result:
            result[pmid] = {"cited_by": [], "is_research_article": None}

    return result


def process_journal(issn: str, meta: dict, db: DatabaseManager,
                    icite: IciteFetcher, bulk: sqlite3.Connection,
                    year_start: int, year_end: int,
                    icite_bulk: sqlite3.Connection = None):
    name = meta["name"]
    logger.info("=" * 60)
    logger.info(f"Processing: {name} (ISSN: {issn})")
    logger.info(f"Year range: {year_start}–{year_end}")

    # ------------------------------------------------------------------ #
    # Step 1: Get papers from bulk DB (no API call)
    # ------------------------------------------------------------------ #
    logger.info("Step 1: Loading papers from bulk DB...")
    rows = get_papers_from_bulk(bulk, issn, year_start, year_end)
    if not rows:
        logger.warning(f"  No papers found in bulk DB for ISSN {issn}")
        return
    logger.info(f"  Found {len(rows):,} papers")

    # Ensure journal exists
    journal = db.get_journal_by_issn(issn)
    if not journal:
        journal_id = db.add_journal(
            issn, name, meta.get("abbreviation"), meta.get("slug")
        )
        logger.info(f"  Created journal record (id={journal_id})")
    else:
        journal_id = journal["id"]

    # ------------------------------------------------------------------ #
    # Step 2: Store papers
    # ------------------------------------------------------------------ #
    logger.info("Step 2: Storing papers...")
    paper_dicts = []
    class_inputs = {}  # pmid -> (pub_types, has_abstract, page_count, title)
    for (pmid, pub_year, pub_month, title,
         first_author, first_affil,
         last_author, last_affil,
         pub_type, doi,
         pub_types, has_abstract, page_count) in rows:
        pub_date = f"{pub_year}-{pub_month:02d}-01"
        class_inputs[pmid] = (json.loads(pub_types) if pub_types else [],
                              None if has_abstract is None else bool(has_abstract),
                              page_count, title)
        cls, src = classify(*class_inputs[pmid][:3], None, title)
        paper_dicts.append({
            "pmid":       pmid,
            "journal_id": journal_id,
            "title":      title or "",
            "pub_date":   pub_date,
            "pub_year":   pub_year,
            "pub_month":  pub_month,
            "pub_type":   pub_type,
            "is_research": 1 if cls == "research" else 0,
            "doi":        doi,
            "doc_class":  cls,
            "class_source": src,
        })
    db.add_papers_bulk(paper_dicts)
    stored = db.get_paper_count_for_journal(journal_id)
    logger.info(f"  {stored:,} papers in DB")

    # ------------------------------------------------------------------ #
    # Step 3: iCite — citation links (local DB preferred, API fallback)
    # ------------------------------------------------------------------ #
    pmids = [p["pmid"] for p in paper_dicts]
    if icite_bulk is not None:
        logger.info("Step 3: Loading iCite data from local bulk DB...")
        icite_data = get_icite_local(icite_bulk, pmids)
        logger.info(f"  Local DB: {len(icite_data):,} papers")
    else:
        logger.info("Step 3: Fetching iCite citation data from API...")
        icite_data = icite.fetch_batch(pmids)
        logger.info(f"  API returned data for {len(icite_data):,} papers")

    # Classify every paper, with iCite's is_research_article as evidence
    # where iCite has the paper (it never sets the class by itself)
    class_rows = []
    for pmid, (types, has_abs, pages, title) in class_inputs.items():
        evidence = icite_evidence((icite_data.get(pmid) or {}).get("is_research_article"))
        cls, src = classify(types, has_abs, pages, evidence, title)
        class_rows.append((cls, src, 1 if cls == "research" else 0, pmid))
    db.conn.executemany(
        "UPDATE papers SET doc_class = ?, class_source = ?, is_research = ? WHERE pmid = ?",
        class_rows,
    )
    db.commit()

    # ------------------------------------------------------------------ #
    # Step 4: Resolve citations using bulk DB for citing paper dates
    # ------------------------------------------------------------------ #
    logger.info("Step 4: Resolving citations...")

    # Collect all unique citing PMIDs across this journal
    all_citing: set = set()
    for record in icite_data.values():
        all_citing.update(record.get("cited_by", []))
    logger.info(f"  {len(all_citing):,} unique citing PMIDs to date")

    # Batch-lookup dates from pubmed_full.db
    citing_dates = get_citing_dates(bulk, all_citing)
    missing = all_citing - set(citing_dates)
    logger.info(
        f"  {len(citing_dates):,} dates from bulk DB, "
        f"{len(missing):,} not found (very new papers)"
    )

    # For PMIDs missing from bulk DB: fall back to iCite year + month=6
    if missing:
        missing_icite = icite.fetch_batch(list(missing))
        for pmid, rec in missing_icite.items():
            yr = rec.get("year")
            if yr:
                citing_dates[pmid] = (yr, 6)
        still_missing = missing - set(citing_dates)
        logger.info(
            f"  iCite fallback: resolved {len(missing) - len(still_missing):,} more "
            f"({len(still_missing):,} unresolvable, skipped)"
        )

    # Store citation events
    total_citations = 0
    for pmid, record in icite_data.items():
        cited_by = record.get("cited_by", [])
        if not cited_by:
            continue
        events = []
        for citing_pmid in cited_by:
            if citing_pmid not in citing_dates:
                continue
            year, month = citing_dates[citing_pmid]
            events.append({
                "cited_pmid":    pmid,
                "citing_pmid":   citing_pmid,
                "citing_date":   f"{year}-{month:02d}-01",
                "citing_year":   year,
                "citing_month":  month,
            })
        if events:
            db.add_citations_bulk(events)
            total_citations += len(events)
    logger.info(f"  {total_citations:,} citation events stored")

    # ------------------------------------------------------------------ #
    # Step 5: First/last author fields from the pubmed_full.db byline (R4)
    # ------------------------------------------------------------------ #
    logger.info("Step 5: Importing author data from pubmed_full.db bylines...")
    bylines = fetch_bylines(bulk, [p["pmid"] for p in paper_dicts])
    write_bylines(db.conn, bylines)
    db.commit()
    logger.info(f"  {len(bylines):,} papers with a byline, "
                f"{len(paper_dicts) - len(bylines):,} without (author fields left as they were)")

    logger.info(f"Done with {name}!")


def load_registry(path: str) -> dict:
    """Load journal_registry.json → {issn: meta} dict."""
    import json
    with open(path) as f:
        entries = json.load(f)
    return {e["issn"]: e for e in entries}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--journal", type=str, nargs="+",
                        help="One or more journal slugs (e.g. bmj nature-cell-biology)")
    parser.add_argument("--years", type=str, default=None,
                        help="Year range START-END (e.g. 2010-2026)")
    parser.add_argument("--registry", type=str, default=None,
                        help="Path to journal_registry.json (overrides config.JOURNALS)")
    parser.add_argument("--icite-db", type=str, default=None,
                        help="Path to icite_bulk.db (skips iCite API entirely)")
    args = parser.parse_args()

    now = datetime.now()
    if args.years:
        parts = args.years.split("-")
        year_start, year_end = int(parts[0]), int(parts[1])
    else:
        year_start, year_end = now.year - 4, now.year

    # Build journal source: registry file or hardcoded config
    all_journals = load_registry(args.registry) if args.registry else JOURNALS

    # Select journals
    if args.journal:
        slugs = set(args.journal)
        journals_to_process = {
            issn: meta for issn, meta in all_journals.items()
            if meta.get("slug") in slugs
        }
        if not journals_to_process:
            logger.error(f"Unknown slug(s): {args.journal}")
            logger.info(f"Available (first 20): {sorted(m['slug'] for m in all_journals.values())[:20]}")
            sys.exit(1)
    else:
        journals_to_process = all_journals

    db = DatabaseManager(DB_PATH)
    db.init_schema()
    db.migrate_add_author_columns()
    icite = IciteFetcher()

    logger.info(f"Opening PubMed DB: {PUBMED_FULL_DB_PATH}")
    bulk = open_bulk_db(PUBMED_FULL_DB_PATH)
    bulk_count = bulk.execute("SELECT COUNT(*) FROM pubmed").fetchone()[0]
    logger.info(f"  {bulk_count:,} records in bulk DB")

    icite_bulk = None
    icite_db_path = args.icite_db or str(REPO_ROOT / "data" / "icite_bulk.db")
    if os.path.exists(icite_db_path):
        logger.info(f"Opening local iCite bulk DB: {icite_db_path}")
        icite_bulk = open_icite_bulk_db(icite_db_path)
    else:
        logger.info("No local iCite bulk DB found — using API (run download_icite_bulk.py to speed this up)")

    for issn, meta in journals_to_process.items():
        try:
            process_journal(issn, meta, db, icite, bulk,
                            year_start, year_end, icite_bulk=icite_bulk)
        except Exception as e:
            logger.error(f"Error processing {meta['name']}: {e}", exc_info=True)
            continue

    bulk.close()
    if icite_bulk:
        icite_bulk.close()
    db.close()
    logger.info("Pipeline complete!")


if __name__ == "__main__":
    main()
