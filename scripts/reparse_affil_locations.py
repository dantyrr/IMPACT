#!/usr/bin/env python3
"""
Re-run src/pipeline/affil_location.py over every stored affiliation string in
pubmed_full.db and write back the strings whose place changed: country, state
and city in affil_strings, and the per-part countries in affil_countries.
Run after changing the parser or its tables (affil_cities.json), then
re-export geography (scripts/export_geography.py).

Usage:
    python scripts/reparse_affil_locations.py [--dry-run]
"""

import argparse
import os
import sqlite3
import sys
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline.affil_location import parse_location, parse_locations
from src.pipeline.config import PUBMED_FULL_DB_PATH

WORKERS = 8
STEP = 250_000


def _diff(bounds):
    """Changed strings in [lo, hi): (affil_id, country, state, city, [part countries])."""
    lo, hi = bounds
    con = sqlite3.connect(f"file:{PUBMED_FULL_DB_PATH}?mode=ro", uri=True)
    old_parts = {}
    for aid, c in con.execute("SELECT affil_id, country FROM affil_countries "
                              "WHERE affil_id >= ? AND affil_id < ? ORDER BY affil_id, part_order", (lo, hi)):
        old_parts.setdefault(aid, []).append(c)
    changes = []
    for aid, text, country, state, city in con.execute(
            "SELECT affil_id, text, country, state, city FROM affil_strings "
            "WHERE affil_id >= ? AND affil_id < ?", (lo, hi)):
        loc = parse_location(text or "")
        parts = [l.country for l in parse_locations(text or "")]
        if (loc.country, loc.state, loc.city) != (country, state, city) or parts != old_parts.get(aid, []):
            changes.append((aid, loc.country, loc.state, loc.city, parts, country))
    con.close()
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="count changes, write nothing")
    args = ap.parse_args()

    con = sqlite3.connect(PUBMED_FULL_DB_PATH, timeout=60)
    top = con.execute("SELECT MAX(affil_id) FROM affil_strings").fetchone()[0] + 1
    chunks = [(lo, min(lo + STEP, top)) for lo in range(0, top, STEP)]
    changed = gained = lost = 0
    moved = Counter()
    with Pool(WORKERS) as pool:
        for i, changes in enumerate(pool.imap_unordered(_diff, chunks), 1):
            for aid, country, state, city, parts, old_country in changes:
                changed += 1
                if old_country is None and country is not None:
                    gained += 1
                    moved[country] += 1
                elif old_country is not None and country is None:
                    lost += 1
            if not args.dry_run and changes:
                with con:
                    con.executemany("UPDATE affil_strings SET country = ?, state = ?, city = ? WHERE affil_id = ?",
                                    [(c, s, ci, aid) for aid, c, s, ci, _, _ in changes])
                    con.executemany("DELETE FROM affil_countries WHERE affil_id = ?",
                                    [(aid,) for aid, *_ in changes])
                    con.executemany("INSERT INTO affil_countries (affil_id, part_order, country) VALUES (?,?,?)",
                                    [(aid, j, c) for aid, _, _, _, parts, _ in changes for j, c in enumerate(parts)])
            if i % 20 == 0 or i == len(chunks):
                print(f"  {i}/{len(chunks)} chunks: {changed:,} changed, {gained:,} newly located, {lost:,} lost",
                      flush=True)
    con.close()
    print(f"{'Would change' if args.dry_run else 'Changed'} {changed:,} strings: "
          f"{gained:,} newly located, {lost:,} no longer located")
    print("Newly located by country:", ", ".join(f"{c} {n:,}" for c, n in moved.most_common(15)))


if __name__ == "__main__":
    main()
