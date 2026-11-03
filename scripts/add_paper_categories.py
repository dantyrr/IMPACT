#!/usr/bin/env python3
"""Add each paper's rate category ("k") to existing docs/data/papers/{slug}.json files.

export_journal_papers now writes "k": the category the rate's by_type counts the
paper under (doc_class, else derived from pub_type; json_exporter). Files exported
before that lack it; this fills it in from impact.db without recomputing anything.
Safe to re-run: every entry's "k" is rewritten from the database. Upload afterwards
with upload_to_r2.py.

Usage:
    python scripts/add_paper_categories.py [--dry-run] [--slug SLUG ...]
"""
import argparse
import glob
import json
import logging
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.pipeline.config import DB_PATH, WEBSITE_DATA_DIR  # noqa: E402
from src.pipeline.db_manager import DatabaseManager  # noqa: E402
from src.pipeline.impact_calculator import ARTICLE_CATEGORIES, category_of  # noqa: E402

logger = logging.getLogger("add_paper_categories")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="count changes, write nothing")
    ap.add_argument("--slug", nargs="+", help="only these journals")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    db = DatabaseManager(DB_PATH)
    paths = sorted(glob.glob(os.path.join(WEBSITE_DATA_DIR, "papers", "*.json")))
    if args.slug:
        paths = [p for p in paths if os.path.basename(p)[:-5] in set(args.slug)]
    files = entries = changed = 0
    for path in paths:
        with open(path) as f:
            data = json.load(f)
        papers = data.get("papers") or []
        if not papers:
            continue
        pmids = [p["pmid"] for p in papers]
        rows = {}
        for i in range(0, len(pmids), 900):
            chunk = pmids[i:i + 900]
            rows.update({r[0]: (r[1], r[2]) for r in db.conn.execute(
                f"SELECT pmid, doc_class, pub_type FROM papers WHERE pmid IN ({','.join('?' * len(chunk))})", chunk)})
        n = 0
        for p in papers:
            doc_class, pub_type = rows.get(p["pmid"], (None, p.get("pt")))
            k = category_of(doc_class, pub_type)
            k = k if k in ARTICLE_CATEGORIES else "other"
            if p.get("k") != k:
                p["k"] = k
                n += 1
        files += 1
        entries += len(papers)
        changed += n
        if n and not args.dry_run:
            with open(path, "w") as f:
                json.dump(data, f, separators=(",", ":"))
    db.close()
    logger.info(f"{files:,} files, {entries:,} papers, {changed:,} categories "
                f"{'would be ' if args.dry_run else ''}written")


if __name__ == "__main__":
    main()
