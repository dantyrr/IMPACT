#!/usr/bin/env python3
"""
Export per-journal geography files: docs/data/geo/{slug}.json and geo/_all.json.

Counts citable items (research, review, case report, guideline) published from
2005 on, by the countries and US states of all their authors' affiliations
(pubmed_full.db), per publication year. See src/pipeline/geo_aggregate.py for
the counting rules.

Usage:
    python scripts/export_geography.py              # every journal + _all.json
    python scripts/export_geography.py --slug nature cell
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline.config import DB_PATH, PUBMED_FULL_DB_PATH, WEBSITE_DATA_DIR
from src.pipeline.geo_aggregate import GeoAggregator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

CITABLE = ("research", "review", "case_report", "guideline")
START_YEAR = 2005
ALL_KEY = "_all"
CHUNK = 500_000


def load_papers(slugs):
    """pmid -> journal id and year arrays (0 = not exported), plus id -> (slug, name)."""
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    journals = {jid: (slug, name) for jid, slug, name in
                con.execute("SELECT id, slug, name FROM journals WHERE slug IS NOT NULL")}
    if slugs:
        journals = {j: v for j, v in journals.items() if v[0] in slugs}
    max_pmid = con.execute("SELECT MAX(pmid) FROM papers").fetchone()[0]
    pjid = np.zeros(max_pmid + 1, dtype=np.int16)
    pyear = np.zeros(max_pmid + 1, dtype=np.int16)
    q = (f"SELECT pmid, journal_id, pub_year FROM papers WHERE pub_year >= {START_YEAR} "
         f"AND doc_class IN ({','.join('?' * len(CITABLE))})")
    cur = con.execute(q, CITABLE)
    while rows := cur.fetchmany(CHUNK):
        a = np.array(rows, dtype=np.int64)
        keep = np.isin(a[:, 1], list(journals))
        a = a[keep]
        pjid[a[:, 0]] = a[:, 1]
        pyear[a[:, 0]] = a[:, 2]
    con.close()
    log.info(f"  {int((pjid > 0).sum()):,} citable papers in {len(journals):,} journals")
    return pjid, pyear, journals


def load_affil_places(con):
    """affil_id -> country codes (CSR arrays) and -> US state code; code -> name lists."""
    max_affil = con.execute("SELECT MAX(affil_id) FROM affil_strings").fetchone()[0]
    country_names, country_code = [], {}
    id_parts, code_parts = [], []
    cur = con.execute("SELECT affil_id, country FROM affil_countries ORDER BY affil_id, part_order")
    while rows := cur.fetchmany(CHUNK):
        for _, c in rows:
            if c not in country_code:
                country_code[c] = len(country_names)
                country_names.append(c)
        id_parts.append(np.fromiter((r[0] for r in rows), dtype=np.int32, count=len(rows)))
        code_parts.append(np.fromiter((country_code[r[1]] for r in rows), dtype=np.int16, count=len(rows)))
    ids = np.concatenate(id_parts)
    codes = np.concatenate(code_parts)
    ptr = np.searchsorted(ids, np.arange(max_affil + 2), side="left").astype(np.int64)
    log.info(f"  {len(ids):,} affiliation-country rows, {len(country_names)} countries")

    state_names, state_code = [""], {}
    astate = np.zeros(max_affil + 1, dtype=np.int8)
    cur = con.execute("SELECT affil_id, state FROM affil_strings WHERE state IS NOT NULL")
    while rows := cur.fetchmany(CHUNK):
        for aid, s in rows:
            code = state_code.get(s)
            if code is None:
                code = state_code[s] = len(state_names)
                state_names.append(s)
            astate[aid] = code
    log.info(f"  {len(state_names) - 1} US states/territories")
    return ptr, codes, country_names, astate, state_names


def aggregate(pjid, pyear, places, agg):
    ptr, codes, country_names, astate, state_names = places
    con = sqlite3.connect(f"file:{PUBMED_FULL_DB_PATH}?mode=ro", uri=True)
    max_pmid = len(pjid) - 1
    cur = con.execute("SELECT pmid, affil_id FROM author_affils WHERE pmid <= ?", (max_pmid,))
    carry = None
    papers = 0
    next_log = 0
    while True:
        rows = cur.fetchmany(CHUNK)
        if not rows and carry is None:
            break
        a = np.array(rows, dtype=np.int64).reshape(-1, 2) if rows else np.empty((0, 2), np.int64)
        a = a[pjid[a[:, 0]] > 0] if len(a) else a
        if carry is not None:
            a = np.concatenate([carry, a])
            carry = None
        if rows and len(a):
            # hold back the last pmid: its rows may continue in the next chunk
            last = a[-1, 0]
            cut = np.searchsorted(a[:, 0], last, side="left")
            carry, a = a[cut:], a[:cut]
        if not len(a):
            if not rows:
                break
            continue
        pm, af = a[:, 0], a[:, 1]
        bounds = np.flatnonzero(np.diff(pm)) + 1
        starts = np.concatenate([[0], bounds])
        ends = np.concatenate([bounds, [len(pm)]])
        for s, e in zip(starts, ends):
            pmid = int(pm[s])
            countries, states = set(), set()
            for aid in af[s:e]:
                for c in codes[ptr[aid]:ptr[aid + 1]]:
                    countries.add(country_names[c])
                st = astate[aid]
                if st:
                    states.add(state_names[st])
            if not countries:
                continue
            year = int(pyear[pmid])
            agg.add(int(pjid[pmid]), year, countries, states)
            agg.add(ALL_KEY, year, countries, states)
            papers += 1
        if pm[-1] >= next_log:
            log.info(f"  pmid {int(pm[-1]):,} / {max_pmid:,}: {papers:,} papers with locations")
            next_log = pm[-1] + 2_000_000
        if not rows:
            break
    con.close()
    log.info(f"  {papers:,} papers with at least one located affiliation")


def write(agg, journals, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    generated = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    written = 0
    for jid, (slug, name) in journals.items():
        data = {"slug": slug, "journal": name, "generated": generated, **agg.export(jid)}
        with open(os.path.join(out_dir, f"{slug}.json"), "w") as f:
            json.dump(data, f, separators=(",", ":"))
        written += 1
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", nargs="+", default=None, help="only these journals (no _all.json)")
    args = parser.parse_args()

    out_dir = os.path.join(WEBSITE_DATA_DIR, "geo")
    log.info("Loading papers...")
    pjid, pyear, journals = load_papers(set(args.slug) if args.slug else None)
    log.info("Loading affiliation places...")
    con = sqlite3.connect(f"file:{PUBMED_FULL_DB_PATH}?mode=ro", uri=True)
    places = load_affil_places(con)
    con.close()
    log.info("Aggregating bylines...")
    agg = GeoAggregator()
    aggregate(pjid, pyear, places, agg)
    n = write(agg, journals, out_dir)
    if not args.slug:
        data = {"slug": ALL_KEY, "journal": "All tracked journals",
                "generated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), **agg.export(ALL_KEY)}
        with open(os.path.join(out_dir, f"{ALL_KEY}.json"), "w") as f:
            json.dump(data, f, separators=(",", ":"))
    log.info(f"Wrote {n:,} journal files to {out_dir}")


if __name__ == "__main__":
    main()
