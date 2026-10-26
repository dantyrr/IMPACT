#!/usr/bin/env python3
"""
Learn src/pipeline/affil_cities.json: the place a city or institution name
stands for, from affiliation strings that do name their country.

Many affiliations stop at the city ("University of Michigan, Ann Arbor."), so
affil_location reads no place from them. Strings that go on to the country
("..., Ann Arbor, MI 48109, USA") show where each such name is. For every
located affiliation part, the one or two segments before the place
("Ann Arbor", "University of Michigan") are counted against its country and US
state. A name is kept only when it is common and nearly always the same place,
so ambiguous names (Cambridge, Columbia, Department of Medicine) are dropped.

Usage:
    python scripts/build_affil_cities.py [--min-count 30] [--min-share 0.95]
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline import affil_location as al
from src.pipeline.config import PUBMED_FULL_DB_PATH

OUT = al.CITIES_PATH
WORKERS = 8


def _count(bounds):
    lo, hi = bounds
    con = sqlite3.connect(f"file:{PUBMED_FULL_DB_PATH}?mode=ro", uri=True)
    counts = defaultdict(Counter)
    for (text,) in con.execute("SELECT text FROM affil_strings WHERE affil_id >= ? AND affil_id < ?", (lo, hi)):
        for part in al.split_parts(text or ""):
            loc, head = al.parse_part(part, text, cities=False)
            if not loc.country:
                continue
            for seg in head[-2:]:
                k = al.city_key(seg)
                if k:
                    counts[k][(loc.country, loc.state)] += 1
    con.close()
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-count", type=int, default=30)
    ap.add_argument("--min-share", type=float, default=0.95)
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{PUBMED_FULL_DB_PATH}?mode=ro", uri=True)
    top = con.execute("SELECT MAX(affil_id) FROM affil_strings").fetchone()[0] + 1
    con.close()
    step = 250_000
    chunks = [(lo, min(lo + step, top)) for lo in range(0, top, step)]
    total = defaultdict(Counter)
    with Pool(WORKERS) as pool:
        for i, counts in enumerate(pool.imap_unordered(_count, chunks), 1):
            for k, c in counts.items():
                total[k].update(c)
            if i % 20 == 0:
                print(f"  {i}/{len(chunks)} chunks, {len(total):,} names", flush=True)

    cities = {}
    for k, c in total.items():
        n = sum(c.values())
        (place, top_n), = c.most_common(1)
        if n >= args.min_count and top_n / n >= args.min_share:
            cities[k] = list(place)
    with open(OUT, "w") as f:
        json.dump(dict(sorted(cities.items())), f, separators=(",", ":"))
    print(f"kept {len(cities):,} of {len(total):,} names -> {OUT} ({os.path.getsize(OUT):,} bytes)")


if __name__ == "__main__":
    main()
