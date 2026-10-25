#!/usr/bin/env python3
"""Apply pubmed_full.db to impact.db: doc_class, canonical pub_type, first/last author fields.

For every impact.db paper that has a row in pubmed_full.db this sets pub_type,
doc_class, class_source, is_research (1 iff doc_class == 'research') and the
first_author_* / last_author_* name, institution, city, state, country fields.
Gender columns and *_forename columns are never touched. Papers without a
pubmed_full row are left as they are (the summary counts them as missing; they
may include records PubMed has since deleted). An author with no affiliation in the new
data keeps the existing institution/city/state/country values.

Usage:
    python scripts/apply_pubmed_full.py [--dry-run] [--journals slug,slug] [--min-free-gb 30]

Requires a live `rebuild` lock holder (python scripts/rebuild_lock.py hold).
Exit codes: 0 done, 1 no lock holder (at start, or gone before a batch; finished
batches are committed), 3 stopped on low disk (work committed).
"""
import argparse
import logging
import os
import sqlite3
import sys
from collections import Counter

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.pipeline.class_inputs import (fetch_bylines, fetch_class_inputs, open_ro,  # noqa: E402
                                       write_bylines)
from src.pipeline.config import DB_PATH, ICITE_BULK_DB_PATH, PUBMED_FULL_DB_PATH  # noqa: E402
from src.pipeline.db_manager import ensure_doc_class_columns  # noqa: E402
from src.pipeline.doc_class import classify  # noqa: E402
from src.pipeline.rebuild_guard import _checkpoint, free_gb, rebuild_lock_held  # noqa: E402

logger = logging.getLogger("apply_pubmed_full")

IMPACT_DB_PATH = DB_PATH
FULL_DB_PATH = PUBMED_FULL_DB_PATH
ICITE_DB_PATH = ICITE_BULK_DB_PATH
BATCH_SIZE = 50_000
CHECKPOINT_EVERY = 20


def add_columns(conn) -> None:
    """Idempotent: add doc_class / class_source."""
    ensure_doc_class_columns(conn)


def create_index(conn) -> None:
    """Idempotent. Built after the updates so they do not maintain it row by row."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_journal_date_class "
                 "ON papers(journal_id, pub_date, doc_class)")
    conn.commit()


def migrate(conn) -> None:
    add_columns(conn)
    create_index(conn)


def _journal_ids(conn, slugs):
    q = ",".join("?" * len(slugs))
    return [r[0] for r in conn.execute(f"SELECT id FROM journals WHERE slug IN ({q})", slugs)]


def _updates_for_batch(inputs):
    """-> (rows for the main UPDATE, class counter)."""
    rows, counts = [], Counter()
    for pmid, d in inputs.items():
        cls, src = classify(d["pub_types"], d["has_abstract"], d["page_count"],
                            d["icite_is_research"], d["title"])
        counts[cls] += 1
        rows.append((d["pub_type"], cls, src, 1 if cls == "research" else 0, pmid))
    return rows, counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="compute and report, write nothing")
    ap.add_argument("--journals", help="comma-separated journal slugs")
    ap.add_argument("--min-free-gb", type=float, default=30.0)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if not rebuild_lock_held():
        logger.error("refusing to run: no live `rebuild` lock holder "
                     "(start: python scripts/rebuild_lock.py hold)")
        return 1

    if args.dry_run:
        conn = open_ro(IMPACT_DB_PATH)
    else:
        conn = sqlite3.connect(IMPACT_DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
    full = open_ro(FULL_DB_PATH)
    icite = open_ro(ICITE_DB_PATH) if os.path.exists(ICITE_DB_PATH) else None
    try:
        floor_dir = os.path.dirname(IMPACT_DB_PATH)

        def low_disk() -> bool:
            free = free_gb(floor_dir)
            if free < args.min_free_gb:
                conn.commit()
                _checkpoint(conn)
                logger.error(f"stopping: {free:.1f} GB free (< {args.min_free_gb}); "
                             f"re-run to resume")
                return True
            return False

        if not args.dry_run:
            if low_disk():
                return 3
            add_columns(conn)
        where, params = "", []
        if args.journals:
            ids = _journal_ids(conn, [s.strip() for s in args.journals.split(",") if s.strip()])
            if not ids:
                logger.error("no matching journals")
                return 0
            where = f"AND journal_id IN ({','.join('?' * len(ids))})"
            params = ids

        counts, seen, matched, last_pmid, n_batch = Counter(), 0, 0, 0, 0
        while True:
            if not rebuild_lock_held():
                conn.commit()
                if not args.dry_run:
                    _checkpoint(conn)
                logger.error(f"stopping: the rebuild lock holder is gone (the weekly job could "
                             f"now run); {matched} papers applied up to pmid {last_pmid}. "
                             f"Restart `rebuild_lock.py hold` and re-run.")
                return 1
            if not args.dry_run:
                free = free_gb(os.path.dirname(IMPACT_DB_PATH))
                if free < args.min_free_gb:
                    conn.commit()
                    _checkpoint(conn)
                    logger.error(f"stopping: {free:.1f} GB free (< {args.min_free_gb}); "
                                 f"{matched} papers applied, re-run to resume")
                    return 3
            pmids = [r[0] for r in conn.execute(
                f"SELECT pmid FROM papers WHERE pmid > ? {where} ORDER BY pmid LIMIT ?",
                [last_pmid, *params, BATCH_SIZE])]
            if not pmids:
                break
            last_pmid = pmids[-1]
            seen += len(pmids)
            inputs = fetch_class_inputs(full, icite, pmids)
            matched += len(inputs)
            rows, batch_counts = _updates_for_batch(inputs)
            counts.update(batch_counts)
            if not args.dry_run:
                conn.executemany("UPDATE papers SET pub_type = COALESCE(?, pub_type), doc_class = ?, "
                                 "class_source = ?, is_research = ? WHERE pmid = ?", rows)
                write_bylines(conn, fetch_bylines(full, list(inputs)))
                conn.commit()
                n_batch += 1
                if n_batch % CHECKPOINT_EVERY == 0:
                    _checkpoint(conn)
        if not args.dry_run:
            if low_disk():
                return 3
            create_index(conn)
            _checkpoint(conn)
        mode = "dry-run: would update" if args.dry_run else "updated"
        print(f"{mode} {matched} papers of {seen} examined; "
              f"missing from pubmed_full: {seen - matched} (left untouched; may include "
              f"records PubMed deleted upstream)")
        for cls, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {cls}: {n}")
        return 0
    finally:
        conn.close()
        full.close()
        if icite is not None:
            icite.close()


if __name__ == "__main__":
    sys.exit(main())
