"""
Compute rolling 24-month citation rates by gender pair.

Uses the same formula as the main IMPACT rolling IF:
  For target year Y:
    Paper window:   publications in years Y-2 and Y-1
    Citation window: citations received in year Y
    Rolling rate = citations_in_window / papers_in_window

This is computed separately for each gender pair (WW, WM, MW, MM)
to compare citation rates controlling for publication age.

Usage:
  python scripts/gender/compute_gender_snapshots.py                    # All journals + aggregate
  python scripts/gender/compute_gender_snapshots.py --aggregate-only   # Just aggregate
  python scripts/gender/compute_gender_snapshots.py --limit 100        # Top 100 journals
  python scripts/gender/compute_gender_snapshots.py --workers 4        # Parallel
"""
import argparse
import sqlite3
import json
import logging
import sys
import os
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.gender.config import IMPACT_DB, START_YEAR, END_YEAR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GENDER_PAIRS = ["WW", "WM", "MW", "MM"]
# First valid snapshot year needs 2 prior years of papers
SNAPSHOT_START = START_YEAR + 2  # 2007
# Skip last 2 years (incomplete citation data)
SNAPSHOT_END = END_YEAR - 2      # 2024


def compute_journal_rolling_if(conn, journal_id, start_year=SNAPSHOT_START,
                                end_year=SNAPSHOT_END):
    """
    Compute yearly rolling 24-month citation rate by gender pair for one journal.

    Uses 2 efficient SQL queries (paper counts + citation counts), then assembles in Python.
    Returns dict: {year_str: {pair: {"p": N, "c": N, "if": float}}}
    """
    # Step 1: Paper counts by gender_pair and pub_year
    paper_counts = {}
    rows = conn.execute("""
        SELECT gender_pair, pub_year, COUNT(*) as cnt
        FROM papers
        WHERE journal_id = ?
          AND gender_pair IN ('WW','WM','MW','MM')
          AND is_research = 1
          AND pub_year BETWEEN ? AND ?
        GROUP BY gender_pair, pub_year
    """, (journal_id, start_year - 2, end_year - 1)).fetchall()

    if not rows:
        return {}

    for pair, year, cnt in rows:
        paper_counts[(pair, year)] = cnt

    # Step 2: Citation counts — citations in year Y to papers published in Y-2 or Y-1
    cite_counts = {}
    rows = conn.execute("""
        SELECT p.gender_pair, c.citing_year, COUNT(*) as cnt
        FROM papers p
        JOIN citations c ON c.cited_pmid = p.pmid
        WHERE p.journal_id = ?
          AND p.gender_pair IN ('WW','WM','MW','MM')
          AND p.is_research = 1
          AND p.pub_year BETWEEN ? AND ?
          AND c.citing_year BETWEEN ? AND ?
          AND (c.citing_year - p.pub_year) IN (1, 2)
        GROUP BY p.gender_pair, c.citing_year
    """, (journal_id, start_year - 2, end_year - 1, start_year, end_year)).fetchall()

    for pair, citing_year, cnt in rows:
        cite_counts[(pair, citing_year)] = cnt

    # Step 3: Assemble results
    result = {}
    for year in range(start_year, end_year + 1):
        year_data = {}
        for pair in GENDER_PAIRS:
            p_count = (paper_counts.get((pair, year - 2), 0) +
                       paper_counts.get((pair, year - 1), 0))
            c_count = cite_counts.get((pair, year), 0)

            rolling_if = round(c_count / p_count, 3) if p_count > 0 else 0
            year_data[pair] = {
                "p": p_count,
                "c": c_count,
                "if": rolling_if,
            }

        total_papers = sum(d["p"] for d in year_data.values())
        if total_papers >= 5:
            mm_if = year_data["MM"]["if"]
            for pair in GENDER_PAIRS:
                if mm_if > 0 and year_data[pair]["p"] > 0:
                    year_data[pair]["norm"] = round(year_data[pair]["if"] / mm_if, 4)
                else:
                    year_data[pair]["norm"] = None
            result[str(year)] = year_data

    return result


def compute_aggregate_rolling_if(conn, start_year=SNAPSHOT_START,
                                  end_year=SNAPSHOT_END):
    """
    Compute aggregate rolling 24-month citation rate by gender pair across ALL journals.
    Uses two efficient SQL queries: one for paper counts, one for citation counts.
    """
    # Step 1: Get paper counts by gender_pair and pub_year (single query)
    logger.info("Counting papers by gender pair and year...")
    paper_counts = {}  # (pair, year) -> count
    rows = conn.execute("""
        SELECT gender_pair, pub_year, COUNT(*) as cnt
        FROM papers
        WHERE gender_pair IN ('WW','WM','MW','MM')
          AND is_research = 1
          AND pub_year BETWEEN ? AND ?
        GROUP BY gender_pair, pub_year
    """, (start_year - 2, end_year - 1)).fetchall()
    for pair, year, cnt in rows:
        paper_counts[(pair, year)] = cnt
    logger.info(f"  Paper counts loaded for {len(rows)} (pair, year) groups")

    # Step 2: Get citation counts — citations in year Y to papers published in Y-2 or Y-1
    # Single query using a join with year arithmetic
    logger.info("Counting citations by gender pair and target year...")
    cite_counts = {}  # (pair, target_year) -> count
    rows = conn.execute("""
        SELECT p.gender_pair, c.citing_year, COUNT(*) as cnt
        FROM papers p
        JOIN citations c ON c.cited_pmid = p.pmid
        WHERE p.gender_pair IN ('WW','WM','MW','MM')
          AND p.is_research = 1
          AND p.pub_year BETWEEN ? AND ?
          AND c.citing_year BETWEEN ? AND ?
          AND (c.citing_year - p.pub_year) IN (1, 2)
        GROUP BY p.gender_pair, c.citing_year
    """, (start_year - 2, end_year - 1, start_year, end_year)).fetchall()
    for pair, citing_year, cnt in rows:
        cite_counts[(pair, citing_year)] = cnt
    logger.info(f"  Citation counts loaded for {len(rows)} (pair, year) groups")

    # Step 3: Assemble results
    result = {}
    for year in range(start_year, end_year + 1):
        year_data = {}
        for pair in GENDER_PAIRS:
            # Papers in window: published in year-2 and year-1
            p_count = (paper_counts.get((pair, year - 2), 0) +
                       paper_counts.get((pair, year - 1), 0))
            c_count = cite_counts.get((pair, year), 0)

            rolling_if = round(c_count / p_count, 3) if p_count > 0 else 0
            year_data[pair] = {
                "p": p_count,
                "c": c_count,
                "if": rolling_if,
            }

        total_papers = sum(d["p"] for d in year_data.values())
        if total_papers > 0:
            mm_if = year_data["MM"]["if"]
            for pair in GENDER_PAIRS:
                if mm_if > 0 and year_data[pair]["p"] > 0:
                    year_data[pair]["norm"] = round(year_data[pair]["if"] / mm_if, 4)
                else:
                    year_data[pair]["norm"] = None
            result[str(year)] = year_data

        logger.info(f"  Year {year}: {total_papers:,} papers in window, "
                     f"MM IF={year_data['MM']['if']:.2f}, WW IF={year_data['WW']['if']:.2f}")

    return result


def store_to_db(conn, journal_id, rolling_data):
    """Store rolling IF data in gender_citation_stats table."""
    for year_str, year_data in rolling_data.items():
        for pair, d in year_data.items():
            if pair not in GENDER_PAIRS:
                continue
            conn.execute("""
                INSERT OR REPLACE INTO gender_citation_stats
                    (journal_id, snapshot_month, gender_pair, paper_count, citation_count, rolling_if_24m)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (journal_id, year_str, pair, d["p"], d["c"], d["if"]))
    conn.commit()


def process_journal_batch(journals, db_path, output_dir):
    """Process a batch of journals. Returns count processed."""
    conn = sqlite3.connect(db_path)
    count = 0

    for i, (jid, slug, name) in enumerate(journals):
        rolling_data = compute_journal_rolling_if(conn, jid)

        if rolling_data:
            store_to_db(conn, jid, rolling_data)

            # Update per-journal JSON with rolling IF data
            json_path = Path(output_dir) / "journals" / f"{slug}.json"
            if json_path.exists():
                with open(json_path) as f:
                    journal_data = json.load(f)
                journal_data["rolling_if"] = rolling_data
                with open(json_path, "w") as f:
                    json.dump(journal_data, f, separators=(",", ":"))

        if (i + 1) % 10 == 0:
            logger.info(f"  Processed {i + 1}/{len(journals)} journals...")
        count += 1

    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate-only", action="store_true",
                        help="Only compute aggregate (skip per-journal)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit to top N journals by paper count")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers")
    parser.add_argument("--output-dir", type=str, default="docs/data/gender",
                        help="Output directory for JSON files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    conn = sqlite3.connect(IMPACT_DB)

    # ── Per-journal computation ──
    if not args.aggregate_only:
        if args.limit:
            journals = conn.execute("""
                SELECT j.id, j.slug, j.name
                FROM journals j
                JOIN (SELECT journal_id, COUNT(*) as cnt FROM papers
                      WHERE gender_pair IS NOT NULL GROUP BY journal_id) p
                  ON p.journal_id = j.id
                ORDER BY p.cnt DESC
                LIMIT ?
            """, (args.limit,)).fetchall()
        else:
            journals = conn.execute(
                "SELECT id, slug, name FROM journals ORDER BY name"
            ).fetchall()

        logger.info(f"Computing rolling IF for {len(journals)} journals...")

        if args.workers <= 1:
            process_journal_batch(journals, IMPACT_DB, args.output_dir)
        else:
            chunks = [journals[i::args.workers] for i in range(args.workers)]
            with ProcessPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(process_journal_batch, chunk, IMPACT_DB, args.output_dir): i
                    for i, chunk in enumerate(chunks)
                }
                for future in as_completed(futures):
                    wid = futures[future]
                    try:
                        n = future.result()
                        logger.info(f"Worker {wid} finished: {n} journals")
                    except Exception as e:
                        logger.error(f"Worker {wid} failed: {e}", exc_info=True)

        logger.info("Per-journal computation complete.")

    # ── Aggregate computation ──
    logger.info("Computing aggregate rolling IF...")
    agg_rolling = compute_aggregate_rolling_if(conn)

    # Update aggregate.json
    agg_path = output_dir / "aggregate.json"
    if agg_path.exists():
        with open(agg_path) as f:
            agg_data = json.load(f)
    else:
        agg_data = {}

    agg_data["rolling_if_24m"] = agg_rolling

    with open(agg_path, "w") as f:
        json.dump(agg_data, f, indent=2)

    logger.info(f"Aggregate rolling IF written to {agg_path}")
    logger.info(f"  Years: {min(agg_rolling.keys())} - {max(agg_rolling.keys())}")

    conn.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
