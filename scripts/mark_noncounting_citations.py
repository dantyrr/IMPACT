#!/usr/bin/env python3
"""Mark stored citations whose citing paper is an erratum, retraction notice or
expression of concern (doc_class.NONCOUNTING_CITING), so no metric counts them.

The weekly update and the bulk pipeline mark such citations as they insert
them; this backfills rows stored before that, and rows from the API pipeline
(run_pipeline.py), which never sees the citing paper's types. Rows are only
marked, never deleted. Safe to re-run: a row already marked is not rewritten.

Reads the citing papers' types from pubmed_full.db (one full scan).
Snapshots and JSON are not recomputed: run compute_snapshots.py afterwards.

Usage:
    python scripts/mark_noncounting_citations.py [--dry-run] [--db PATH] [--full PATH]
"""
import argparse
import json
import logging
import os
import sqlite3
import sys
from collections import Counter

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.pipeline.config import DB_PATH, PUBMED_FULL_DB_PATH  # noqa: E402
from src.pipeline.db_manager import DatabaseManager  # noqa: E402
from src.pipeline.doc_class import citing_class  # noqa: E402

logger = logging.getLogger("mark_noncounting_citations")

# Cheap prefilter for the scan; citing_class() makes the actual decision.
_LIKE = ("%Erratum%", "%Retraction%", "%Expression of Concern%")


def noncounting_pmids(full_path: str) -> dict:
    """{pmid: citing_class} for every pubmed_full paper whose citations do not count."""
    full = sqlite3.connect(f"file:{full_path}?mode=ro", uri=True)
    try:
        where = " OR ".join("pub_types LIKE ?" for _ in _LIKE)
        out = {}
        for pmid, types in full.execute(f"SELECT pmid, pub_types FROM pubmed WHERE {where}", _LIKE):
            cls = citing_class(json.loads(types) if types else [])
            if cls:
                out[pmid] = cls
        return out
    finally:
        full.close()


def count_citations_by(db_path: str, pmids: list) -> int:
    """Stored citations made by these citing PMIDs."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        n = 0
        for i in range(0, len(pmids), 900):
            chunk = pmids[i:i + 900]
            n += con.execute(f"SELECT COUNT(*) FROM citations WHERE citing_pmid IN "
                             f"({','.join('?' * len(chunk))})", chunk).fetchone()[0]
        return n
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", default=DB_PATH, help="impact.db (default: config DB_PATH)")
    parser.add_argument("--full", default=PUBMED_FULL_DB_PATH,
                        help="pubmed_full.db (default: config PUBMED_FULL_DB_PATH)")
    parser.add_argument("--dry-run", action="store_true",
                        help="count the citations that would be marked, change nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    classes = noncounting_pmids(args.full)
    logger.info(f"{len(classes):,} papers in pubmed_full.db whose citations do not count "
                f"({dict(Counter(classes.values()))})")

    if args.dry_run:
        n = count_citations_by(args.db, list(classes))
        logger.info(f"[DRY RUN] {n:,} stored citations are made by them")
        return

    db = DatabaseManager(args.db)  # adds citations.citing_class if missing
    db.conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_citing_pmid ON citations(citing_pmid)")
    changed = db.mark_citing_class(classes)
    db.close()
    logger.info(f"Marked {changed:,} citations. Run compute_snapshots.py to apply them to the rates.")


if __name__ == "__main__":
    main()
