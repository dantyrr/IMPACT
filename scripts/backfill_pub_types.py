#!/usr/bin/env python3
"""
Re-fetch and correct article types for papers added by the weekly update.

Two defects in run_weekly_update.py (fixed 2026-10-22) corrupted pub_type for
every paper it inserted:

  1. It stored pubtypes[0].lower() -> "journal article", while
     ARTICLE_TYPE_MAP is keyed in Title Case. The lookup missed, so
     classify_pub_type() returned 'other' for all of them.
  2. It took pubtypes[0], but PubMed lists "Journal Article" first even for
     reviews. The specific type was never recorded, so reviews, editorials
     and letters are indistinguishable from research in the stored data.

Defect 1 is fixed retroactively by the now case-insensitive classifier.
Defect 2 is not recoverable from what was stored -- the real type has to come
back from PubMed. This script re-fetches ESummary for the affected rows and
rewrites pub_type (canonical Title Case) and is_research.

Affected rows are identified by their all-lowercase pub_type, which only the
weekly path produced. The PMID list is cached so the scan happens once, and
progress is checkpointed so the run can be interrupted and resumed.

Usage:
    python scripts/backfill_pub_types.py --dry-run   # scan + report, no writes
    python scripts/backfill_pub_types.py             # run (resumable)
    python scripts/backfill_pub_types.py --reset     # discard checkpoint
"""

import os
import sys
import json
import time
import sqlite3
import logging
import argparse
from pathlib import Path
from collections import Counter

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.config import DB_PATH, PUBMED_BASE_URL, PUBMED_API_KEY, PUBMED_EMAIL, PUBMED_RATE_LIMIT
from src.pipeline.impact_calculator import canonical_pub_type, classify_pub_type

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_types")

STATE_DIR = REPO_ROOT / "data"
PMID_CACHE = STATE_DIR / "backfill_pub_types_pmids.txt"
CHECKPOINT = STATE_DIR / "backfill_pub_types_state.json"
LOCK_DIR = STATE_DIR / ".weekly_update.lock"
BATCH_SIZE = 200          # ESummary's practical ceiling
COMMIT_EVERY = 25         # batches between commits


def find_affected_pmids(con) -> list:
    """PMIDs whose pub_type is all lowercase -- the weekly update's signature.

    The bulk pipeline always wrote Title Case, so case alone separates them
    cleanly without needing an insertion timestamp the schema doesn't have.
    """
    logger.info("Scanning papers for lowercase pub_type (one full pass)...")
    rows = con.execute("""
        SELECT pmid, pub_type FROM papers
        WHERE pub_type IS NOT NULL
          AND pub_type <> ''
          AND pub_type = lower(pub_type)
    """).fetchall()
    kinds = Counter(r[1] for r in rows)
    logger.info(f"  {len(rows):,} affected rows")
    for k, n in kinds.most_common(10):
        logger.info(f"    {k!r}: {n:,}")
    return [r[0] for r in rows]


def load_pmids(con, reset: bool) -> list:
    if reset:
        PMID_CACHE.unlink(missing_ok=True)
        CHECKPOINT.unlink(missing_ok=True)
    if PMID_CACHE.exists():
        pmids = [int(x) for x in PMID_CACHE.read_text().split() if x.strip()]
        logger.info(f"Loaded {len(pmids):,} PMIDs from cache {PMID_CACHE.name}")
        return pmids
    pmids = find_affected_pmids(con)
    PMID_CACHE.write_text("\n".join(str(p) for p in pmids))
    logger.info(f"Cached PMID list to {PMID_CACHE.name}")
    return pmids


def fetch_types(pmids: list) -> dict:
    """ESummary for a batch -> {pmid: canonical pub_type}."""
    import requests
    params = {
        "db": "pubmed",
        "id": ",".join(str(p) for p in pmids),
        "retmode": "json",
    }
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY
    if PUBMED_EMAIL:
        params["email"] = PUBMED_EMAIL

    for attempt in range(1, 7):
        try:
            resp = requests.get(f"{PUBMED_BASE_URL}/esummary.fcgi",
                                params=params, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            if attempt == 6:
                logger.error(f"  batch failed after {attempt} attempts: {e}")
                return {}
            wait = min(2 ** attempt, 30)
            logger.warning(f"  retry {attempt} in {wait}s: {e}")
            time.sleep(wait)

    out = {}
    result = data.get("result", {})
    for uid in result.get("uids", []):
        article = result.get(uid, {})
        if not article or "error" in article:
            continue
        out[int(uid)] = canonical_pub_type(article.get("pubtype", []))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="scan and report only")
    ap.add_argument("--reset", action="store_true", help="discard cached list and checkpoint")
    ap.add_argument("--limit", type=int, help="stop after N papers (for testing)")
    args = ap.parse_args()

    # Never write to the database alongside the weekly update.
    if os.system("pgrep -f run_weekly_update.py > /dev/null 2>&1") == 0:
        logger.error("run_weekly_update.py is running -- refusing to write concurrently")
        return 1
    if LOCK_DIR.exists() and not args.dry_run:
        logger.error(f"{LOCK_DIR} exists -- an update may be in progress")
        return 1

    con = sqlite3.connect(str(DB_PATH), timeout=60)
    con.execute("PRAGMA journal_mode=WAL")

    pmids = load_pmids(con, args.reset)
    if not pmids:
        logger.info("Nothing to do.")
        return 0

    done = 0
    if CHECKPOINT.exists() and not args.reset:
        done = json.loads(CHECKPOINT.read_text()).get("done", 0)
        logger.info(f"Resuming from checkpoint: {done:,} already processed")

    if args.dry_run:
        logger.info("[DRY RUN] sampling one batch to show what would change")
        sample = pmids[done:done + 20]
        got = fetch_types(sample)
        for pmid in sample[:20]:
            old = con.execute("SELECT pub_type FROM papers WHERE pmid=?", (pmid,)).fetchone()
            new = got.get(pmid)
            if new:
                logger.info(f"    {pmid}: {old[0]!r} -> {new!r} "
                            f"[{classify_pub_type(old[0])} -> {classify_pub_type(new)}]")
        con.close()
        return 0

    todo = pmids[done:]
    if args.limit:
        todo = todo[:args.limit]
    total = len(todo)
    logger.info(f"Backfilling {total:,} papers in batches of {BATCH_SIZE}")

    changed = Counter()
    updated = missing = 0
    min_interval = 1.0 / PUBMED_RATE_LIMIT

    for i in range(0, total, BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        started = time.time()
        got = fetch_types(batch)

        rows = []
        for pmid in batch:
            new_type = got.get(pmid)
            if not new_type:
                missing += 1
                continue
            rows.append((new_type, 1 if new_type == "Journal Article" else 0, pmid))
            changed[classify_pub_type(new_type)] += 1

        if rows:
            con.executemany(
                "UPDATE papers SET pub_type=?, is_research=? WHERE pmid=?", rows)
            updated += len(rows)

        batch_no = i // BATCH_SIZE + 1
        if batch_no % COMMIT_EVERY == 0 or i + BATCH_SIZE >= total:
            con.commit()
            CHECKPOINT.write_text(json.dumps({"done": done + i + len(batch)}))
            pct = (i + len(batch)) / total * 100
            logger.info(f"  {i + len(batch):,} / {total:,} ({pct:.1f}%) — "
                        f"{updated:,} updated, {missing:,} not returned")
            logger.info(f"    categories so far: {dict(changed.most_common())}")

        elapsed = time.time() - started
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

    con.commit()
    con.close()
    logger.info("=" * 60)
    logger.info(f"Done. {updated:,} papers updated, {missing:,} not returned by ESummary.")
    logger.info(f"Final categories: {dict(changed.most_common())}")
    logger.info("")
    logger.info("Next: recompute snapshots for affected journals, then upload_to_r2.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
