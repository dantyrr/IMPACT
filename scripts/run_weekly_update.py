#!/usr/bin/env python3
"""
IMPACT Weekly Update

Incrementally adds papers published in the last N days and the citations
they create, then updates affected journals' JSON snapshots.

Three phases:
  1. Discover new PubMed papers via ESearch → full records via EFetch →
     pubmed_full.db (record + byline) → classify → add to impact.db
  2. Fetch iCite for new papers → re-classify with iCite evidence → get their
     reference lists → cross-reference against papers already in the DB → add
     citation events
  3. Recompute current month's rolling IF for affected journals → update JSONs,
     classes files, flags and index.json

Usage:
    python scripts/run_weekly_update.py              # last 10 days (default)
    python scripts/run_weekly_update.py --days 14    # last 14 days
    python scripts/run_weekly_update.py --dry-run    # show plan without changes
    python scripts/run_weekly_update.py --skip-snapshots  # phases 1-2 only
"""

import sys
import os
import json
import time
import logging
import argparse
import io
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.config import (
    DB_PATH, PUBMED_BASE_URL, PUBMED_API_KEY, PUBMED_EMAIL,
    ICITE_BASE_URL, ICITE_RATE_LIMIT, PUBMED_RATE_LIMIT,
    WEBSITE_DATA_DIR, PUBMED_FULL_DB_PATH, ISSN_BULK_MAP,
)
from src.pipeline.class_inputs import fetch_bylines, write_bylines
from src.pipeline.db_manager import DatabaseManager
from src.pipeline.doc_class import classify, icite_evidence
from src.pipeline.json_exporter import JSONExporter
from src.pipeline.journal_flags import flags_for_timeseries
from src.pipeline.impact_calculator import ImpactCalculator
from src.pipeline.pubmed_full_db import (
    make_byline_scope, open_full_db, store_records, tracked_issns_from_impact,
)
from src.pipeline.pubmed_xml import iter_pubmed_xml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("weekly")


# ------------------------------------------------------------------ #
#  HTTP helpers
# ------------------------------------------------------------------ #

FAILED_PMIDS = {"efetch": [], "icite": []}


def request_with_retry(url, params, timeout, attempts=6, label="", method="get"):
    """GET (or POST, with params as the form body) with exponential backoff.
    Returns the response, or None if every attempt failed. Transient
    5xx/timeouts are the norm against NCBI at volume, so a dropped batch must
    never be silently skipped."""
    for attempt in range(1, attempts + 1):
        try:
            if method == "post":
                resp = requests.post(url, data=params, timeout=timeout)
            else:
                resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            if attempt == attempts:
                logger.error(f"  FAILED after {attempt} attempts {label}: {e}")
                return None
            wait = min(2 ** attempt, 30)
            logger.warning(f"  retry {attempt} {label} in {wait}s: {e}")
            time.sleep(wait)
    return None


MAX_UID = 99999999


def esearch_ids(term, retmax=9999):
    """One ESearch. Returns (count, ids). count is the true total, which may
    exceed len(ids) when the result set is over the 9,999 retrieval cap."""
    params = {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "xml"}
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY
    if PUBMED_EMAIL:
        params["email"] = PUBMED_EMAIL

    resp = request_with_retry(
        f"{PUBMED_BASE_URL}/esearch.fcgi", params, timeout=60, label=term,
    )
    time.sleep(1.0 / PUBMED_RATE_LIMIT)
    if resp is None:
        return None, []
    root = ET.fromstring(resp.text)
    return (int(root.findtext("Count", "0")),
            [int(el.text) for el in root.findall(".//IdList/Id")])


def esearch_all(base_term, lo=0, hi=MAX_UID, depth=0):
    """Retrieve every PMID for a term, bisecting on [UID] ranges to keep each
    subquery under the 9,999 cap. PubMed enforces that cap on ESearch and on
    EFetch-from-History alike, so partitioning the query is the only way to
    read a day with more than 9,999 papers. UID ranges are disjoint and
    exhaustive, so the union is complete."""
    term = base_term if (lo == 0 and hi == MAX_UID) else f"{base_term} AND {lo}:{hi}[UID]"
    count, ids = esearch_ids(term)

    if count is None:
        logger.error(f"  esearch failed for {term}")
        return []
    if count <= 9999:
        return ids
    if lo >= hi or depth > 30:
        logger.warning(f"  cannot split further: {term} ({count:,}) — "
                       f"keeping {len(ids):,}")
        return ids

    mid = (lo + hi) // 2
    return (esearch_all(base_term, lo, mid, depth + 1)
            + esearch_all(base_term, mid + 1, hi, depth + 1))


# ------------------------------------------------------------------ #
#  Phase 1: Discover new papers from PubMed
# ------------------------------------------------------------------ #

def esearch_recent(days: int) -> list:
    """Search PubMed for all papers added in the last N days.
    Splits into per-day queries to stay under the 9999-result ESearch limit.
    Returns list of integer PMIDs (deduplicated)."""
    today = datetime.now()
    all_pmids = set()

    for d in range(days):
        day = today - timedelta(days=d)
        day_str = day.strftime("%Y/%m/%d")
        term = f'"{day_str}"[EDAT]'

        count, _ = esearch_ids(term, retmax=0)
        if count is None:
            logger.error(f"  {day_str}: SKIPPED — esearch failed")
            continue

        if count > 9999:
            logger.info(f"  {day_str}: {count:,} papers — splitting by UID range")
        ids = esearch_all(term)

        all_pmids.update(ids)
        logger.info(f"  {day_str}: {len(ids):,} PMIDs (total {count:,})")
        if len(set(ids)) < count:
            logger.warning(
                f"  {day_str}: retrieved {len(set(ids)):,} of {count:,} — "
                f"{count - len(set(ids)):,} missing"
            )

    return list(all_pmids)


def efetch_batch(pmids: list, batch_size: int = 200) -> list:
    """Fetch full PubMed records (EFetch, XML) for a list of PMIDs.

    POSTs 200 ids per request and parses each PubmedArticle with
    pubmed_xml.parse_article. Returns the record dicts plus "pub_date"
    ("YYYY-MM-01"). A batch that fails every retry, or whose XML cannot be
    parsed, adds all its pmids to FAILED_PMIDS["efetch"] and contributes no
    records. A requested pmid the response does not return as a usable record
    (missing, an <ERROR> body, or rejected by parse_article) is added to
    FAILED_PMIDS["efetch"] too, so nothing is dropped silently."""
    papers = []

    for i in range(0, len(pmids), batch_size):
        chunk = pmids[i:i + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(str(p) for p in chunk),
            "retmode": "xml",
        }
        if PUBMED_API_KEY:
            params["api_key"] = PUBMED_API_KEY
        if PUBMED_EMAIL:
            params["email"] = PUBMED_EMAIL

        resp = request_with_retry(
            f"{PUBMED_BASE_URL}/efetch.fcgi", params, timeout=120,
            label=f"efetch batch at {i}", method="post",
        )
        if resp is None:
            FAILED_PMIDS["efetch"].extend(chunk)
            continue
        try:
            batch = [rec for kind, rec in iter_pubmed_xml(io.BytesIO(resp.content))
                     if kind == "record"]
        except Exception as e:
            logger.error(f"  EFetch unparseable at {i}: {e}")
            FAILED_PMIDS["efetch"].extend(chunk)
            continue

        requested = set(chunk)
        batch = [rec for rec in batch if rec["pmid"] in requested]
        returned = {rec["pmid"] for rec in batch}
        missing = [p for p in chunk if p not in returned]
        if missing:
            logger.warning(f"  EFetch batch at {i}: {len(missing):,} of {len(chunk):,} "
                           f"PMIDs not returned as usable records")
            FAILED_PMIDS["efetch"].extend(missing)

        for rec in batch:
            rec["pub_date"] = f"{rec['pub_year']}-{rec['pub_month']:02d}-01"
        papers.extend(batch)

        done = i + len(chunk)
        if done % 2000 < batch_size or done >= len(pmids):
            logger.info(f"  EFetch: {len(papers):,} parsed ({done:,}/{len(pmids):,})")

        time.sleep(1.0 / PUBMED_RATE_LIMIT)

    return papers


def class_fields(rec: dict, icite_is_research=None) -> dict:
    """doc_class, class_source and is_research (1 iff research) for a record."""
    cls, src = classify(rec.get("pub_types"), rec.get("has_abstract"),
                        rec.get("page_count"), icite_is_research, rec.get("title"))
    return {"doc_class": cls, "class_source": src,
            "is_research": 1 if cls == "research" else 0}


def build_issn_lookup(journals: list) -> dict:
    """ISSN → journal dict, plus the ISSN_BULK_MAP aliases of tracked ISSNs."""
    lookup = {j["issn"]: j for j in journals}
    for issn, alias in ISSN_BULK_MAP.items():
        if issn in lookup:
            lookup.setdefault(alias, lookup[issn])
    return lookup


def match_journal(rec: dict, issn_lookup: dict):
    """The record's ISSN (ISSNLinking) first, then each Journal/ISSN."""
    for issn in [rec.get("issn")] + list(rec.get("issns") or []):
        if issn and issn in issn_lookup:
            return issn_lookup[issn]
    return None


# ------------------------------------------------------------------ #
#  Phase 2: Citation events via iCite references
# ------------------------------------------------------------------ #

def fetch_icite_references(pmids: list, batch_size: int = 200) -> dict:
    """Fetch iCite for PMIDs.
    Returns {pmid: {"references": [...], "icite_is_research": bool|None}}.
    Papers not yet indexed by iCite will be missing from the result."""
    results = {}
    min_interval = 1.0 / ICITE_RATE_LIMIT
    last_req = 0.0

    for i in range(0, len(pmids), batch_size):
        chunk = pmids[i:i + batch_size]
        chunk_str = ",".join(str(p) for p in chunk)

        # Rate limit
        elapsed = time.time() - last_req
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        last_req = time.time()

        resp = request_with_retry(
            ICITE_BASE_URL,
            {"pmids": chunk_str, "format": "json"},
            timeout=120,
            label=f"icite batch at {i}",
        )
        if resp is None:
            FAILED_PMIDS["icite"].extend(chunk)
            continue
        try:
            data = resp.json()
        except Exception as e:
            logger.error(f"  iCite unparseable at {i}: {e}")
            FAILED_PMIDS["icite"].extend(chunk)
            continue

        for record in data.get("data", []):
            pmid = record.get("pmid")
            if pmid is None:
                continue
            pmid = int(pmid)

            refs_raw = record.get("references", [])
            if isinstance(refs_raw, str):
                refs = [int(x) for x in refs_raw.split() if x.strip()]
            elif isinstance(refs_raw, list):
                refs = [int(x) for x in refs_raw if x]
            else:
                refs = []

            results[pmid] = {
                "references": refs,
                # evidence for classify() only; None when iCite gives no value
                "icite_is_research": icite_evidence(record.get("is_research_article")),
            }

        done = i + len(chunk)
        if done % 2000 < batch_size or done >= len(pmids):
            logger.info(
                f"  iCite: {len(results):,} records ({done:,}/{len(pmids):,})"
            )

    return results


# ------------------------------------------------------------------ #
#  Phase 3: Update snapshots for affected journals
# ------------------------------------------------------------------ #

def format_snapshot(s: dict) -> dict:
    """Format a raw compute_rolling_if() result for the JSON timeseries."""
    return JSONExporter._format_timeseries([s])[0]


def update_journal_snapshot(db, calc, journal_id, slug, name, issn,
                            now, data_dir):
    """Recompute current month, update the journal's JSON file (including its
    flags) and rewrite its classes/{slug}.json.
    Returns the raw 24-month snapshot dict plus "flags", or None if no
    existing JSON."""
    journals_dir = os.path.join(data_dir, "journals")
    filepath = os.path.join(journals_dir, f"{slug}.json")

    if not os.path.exists(filepath):
        # No existing file — can't do partial update.
        # This journal needs a full compute_snapshots.py run.
        return None

    with open(filepath) as f:
        existing = json.load(f)

    current_month_str = f"{now.year}-{now.month:02d}"

    # Compute current month for all 3 window variants
    variants = [
        ("timeseries",      24,  0),
        ("timeseries_12mo", 12,  0),
        ("timeseries_5yr",  60, 12),
    ]

    raw_snapshots = {}
    for key, window, skip in variants:
        raw_snapshots[key] = calc.compute_rolling_if(
            journal_id, now.year, now.month,
            paper_window_months=window, paper_skip_months=skip,
        )

    # Update each timeseries in the JSON
    for key, _, _ in variants:
        ts = existing.get(key, [])
        new_entry = format_snapshot(raw_snapshots[key])

        if ts and ts[-1]["month"] == current_month_str:
            ts[-1] = new_entry
        else:
            ts.append(new_entry)
        existing[key] = ts

    # Update "latest" block
    latest = raw_snapshots["timeseries"]
    existing["latest"] = {
        "month": latest["month"],
        "rolling_if": latest["rolling_if"],
        "rolling_if_no_reviews": latest["rolling_if_no_reviews"],
        "paper_count": latest["paper_count"],
        "research_count": latest.get("research_count", 0),
        "review_count": latest["review_count"],
        "citation_count": latest["citation_count"],
    }
    existing["last_updated"] = now.strftime("%Y-%m-%d")
    flags = flags_for_timeseries(existing["timeseries"], now.date())
    existing["flags"] = flags

    os.makedirs(journals_dir, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(existing, f, indent=2)

    exporter = JSONExporter(data_dir=data_dir, journals_dir=journals_dir)
    exporter.export_journal_classes(slug, db.get_paper_classes_for_journal(journal_id))

    return {**raw_snapshots["timeseries"], "flags": flags}


def update_index(data_dir, dirty_journals_data):
    """Patch index.json with updated latest_if for dirty journals."""
    index_path = os.path.join(data_dir, "index.json")
    if not os.path.exists(index_path):
        logger.warning("index.json not found — skipping")
        return

    with open(index_path) as f:
        index = json.load(f)

    slug_to_idx = {
        j["slug"]: i for i, j in enumerate(index.get("journals", []))
    }

    updated = 0
    for slug, snapshot in dirty_journals_data.items():
        if slug in slug_to_idx:
            entry = index["journals"][slug_to_idx[slug]]
            entry["latest_if"] = snapshot["rolling_if"]
            entry["latest_if_no_reviews"] = snapshot["rolling_if_no_reviews"]
            entry["paper_count"] = snapshot["paper_count"]
            entry["latest_month"] = snapshot["month"]
            if "flags" in snapshot:
                entry["flags"] = snapshot["flags"]
            updated += 1

    index["generated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)

    logger.info(f"  Updated {updated:,} entries in index.json")


# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--days", type=int, default=10,
        help="Look back N days for new papers (default: 10)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show plan without making changes",
    )
    parser.add_argument(
        "--skip-snapshots", action="store_true",
        help="Run phases 1-2 only (add papers + citations, skip JSON updates)",
    )
    args = parser.parse_args()

    start_time = datetime.now()
    logger.info(f"IMPACT Weekly Update — {start_time.strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Looking back {args.days} days")

    # ==================================================================
    #  PHASE 1: Discover new PubMed papers
    # ==================================================================
    logger.info("=" * 60)
    logger.info("PHASE 1: Discovering new PubMed papers")

    all_pmids = esearch_recent(args.days)
    logger.info(f"  Total from ESearch: {len(all_pmids):,} PMIDs")

    if not all_pmids:
        logger.info("No papers found. Done.")
        return

    # Filter out PMIDs already in our DB
    db = DatabaseManager(DB_PATH)
    existing_pmids = set()
    for i in range(0, len(all_pmids), 5000):
        chunk = all_pmids[i:i + 5000]
        placeholders = ",".join("?" * len(chunk))
        rows = db.conn.execute(
            f"SELECT pmid FROM papers WHERE pmid IN ({placeholders})", chunk
        ).fetchall()
        existing_pmids.update(r[0] for r in rows)

    new_pmids = [p for p in all_pmids if p not in existing_pmids]
    logger.info(
        f"  {len(existing_pmids):,} already in DB, "
        f"{len(new_pmids):,} new"
    )

    if args.dry_run:
        logger.info(f"[DRY RUN] Would fetch metadata for {len(new_pmids):,} papers")
        db.close()
        return

    inserted_count = 0

    # Build ISSN → journal lookup from all journals in the DB
    all_journals = db.get_all_journals()
    issn_lookup = build_issn_lookup(all_journals)  # ISSN → journal dict
    journal_by_id = {j["id"]: j for j in all_journals}

    dirty_journal_ids = set()
    # Keep metadata in memory for Phase 2 (even unmatched papers cite
    # tracked papers, so we need their pub dates for citation events)
    pmid_meta = {}  # pmid → {pub_year, pub_month, ...}
    matched = []

    if new_pmids:
        logger.info(f"  Fetching EFetch records for {len(new_pmids):,} papers...")
        papers_meta = efetch_batch(new_pmids)
        logger.info(f"  Parsed {len(papers_meta):,} papers from EFetch")

        # Store all metadata for Phase 2
        for p in papers_meta:
            pmid_meta[p["pmid"]] = p

        # Every record goes to pubmed_full.db; bylines for the same scope as
        # the bulk ingest (tracked ISSNs incl. aliases, FIRST_YEAR..last_year())
        if papers_meta:
            full = open_full_db(PUBMED_FULL_DB_PATH)
            try:
                store_records(full, papers_meta,
                              make_byline_scope(tracked_issns_from_impact(DB_PATH)))
            finally:
                full.close()
            logger.info(f"  Stored {len(papers_meta):,} records in pubmed_full.db")

        # Match ISSN to journals and insert
        unmatched_count = 0

        for p in papers_meta:
            journal = match_journal(p, issn_lookup)
            if journal:
                p["journal_id"] = journal["id"]
                # iCite is not consulted yet: classified again after Phase 2
                p.update(class_fields(p))
                matched.append(p)
                dirty_journal_ids.add(journal["id"])
            else:
                unmatched_count += 1

        logger.info(
            f"  {len(matched):,} matched to tracked journals, "
            f"{unmatched_count:,} from untracked journals"
        )

        if matched:
            # First/last author fields from the stored byline
            full = open_full_db(PUBMED_FULL_DB_PATH)
            try:
                bylines = fetch_bylines(full, [p["pmid"] for p in matched])
            finally:
                full.close()

            # Papers and their author fields in one transaction: a paper row
            # without its byline would never be revisited (it is then in
            # existing_pmids), so a failure rolls both back.
            try:
                db.add_papers_bulk(matched, commit=False)
                write_bylines(db.conn, bylines)
                db.conn.commit()
            except Exception:
                db.conn.rollback()
                raise
            inserted_count = len(matched)
            logger.info(f"  Inserted {inserted_count:,} new papers into DB "
                        f"({len(bylines):,} with author fields)")
    else:
        logger.info("  No new papers to fetch")

    # ==================================================================
    #  PHASE 2: Citation events from new papers' reference lists
    # ==================================================================
    logger.info("=" * 60)
    logger.info("PHASE 2: Fetching iCite references for new papers")

    if not new_pmids:
        logger.info("  No new papers — skipping iCite")
    else:
        logger.info(f"  Fetching iCite for {len(new_pmids):,} papers...")
        icite_data = fetch_icite_references(new_pmids)

        n_missing = len(new_pmids) - len(icite_data)
        logger.info(
            f"  iCite returned data for {len(icite_data):,} papers "
            f"({n_missing:,} not yet indexed — will be caught next run)"
        )

        # Re-classify this run's papers with iCite's is_research_article as
        # evidence; doc_class, class_source and is_research change together.
        updates = []
        for p in matched:
            record = icite_data.get(p["pmid"])
            if record is None or record.get("icite_is_research") is None:
                continue
            f = class_fields(p, record["icite_is_research"])
            updates.append((f["doc_class"], f["class_source"], f["is_research"], p["pmid"]))
        if updates:
            db.conn.executemany(
                "UPDATE papers SET doc_class = ?, class_source = ?, is_research = ? "
                "WHERE pmid = ?", updates
            )
            db.conn.commit()
            logger.info(f"  Re-classified {len(updates):,} papers with iCite evidence")

        # Collect all referenced PMIDs across all new papers
        all_refs = set()
        paper_refs = {}  # citing_pmid → [referenced_pmids]
        for pmid, record in icite_data.items():
            refs = record.get("references", [])
            if refs:
                paper_refs[pmid] = refs
                all_refs.update(refs)

        logger.info(
            f"  {len(all_refs):,} unique referenced PMIDs "
            f"across {len(paper_refs):,} papers"
        )

        # Find which referenced PMIDs exist in our papers table
        # (these are the papers that gain a new citation)
        tracked_refs = {}  # pmid → journal_id
        ref_list = list(all_refs)
        for i in range(0, len(ref_list), 5000):
            chunk = ref_list[i:i + 5000]
            placeholders = ",".join("?" * len(chunk))
            rows = db.conn.execute(
                f"SELECT pmid, journal_id FROM papers "
                f"WHERE pmid IN ({placeholders})",
                chunk,
            ).fetchall()
            for r in rows:
                tracked_refs[r[0]] = r[1]

        logger.info(
            f"  {len(tracked_refs):,} referenced papers are in tracked journals"
        )

        # Create citation events
        citation_events = []
        for citing_pmid, refs in paper_refs.items():
            # Get citing paper's pub date — from in-memory metadata if available,
            # otherwise from DB (for papers that matched a tracked journal)
            meta = pmid_meta.get(citing_pmid)
            if meta:
                citing_year = meta["pub_year"]
                citing_month = meta["pub_month"]
            else:
                paper = db.get_paper(citing_pmid)
                if paper:
                    citing_year = paper["pub_year"]
                    citing_month = paper["pub_month"] or 1
                else:
                    continue  # shouldn't happen

            citing_date = f"{citing_year}-{citing_month:02d}-01"

            for ref_pmid in refs:
                if ref_pmid in tracked_refs:
                    citation_events.append({
                        "cited_pmid": ref_pmid,
                        "citing_pmid": citing_pmid,
                        "citing_date": citing_date,
                        "citing_year": citing_year,
                        "citing_month": citing_month,
                    })
                    dirty_journal_ids.add(tracked_refs[ref_pmid])

        if citation_events:
            db.add_citations_bulk(citation_events)
            logger.info(f"  Added {len(citation_events):,} new citation events")
        else:
            logger.info("  No new citation events")

    # ==================================================================
    #  PHASE 3: Update snapshots for affected journals
    # ==================================================================
    if args.skip_snapshots:
        logger.info("=" * 60)
        logger.info("Skipping Phase 3 (--skip-snapshots)")
        db.close()
        _print_summary(start_time, new_pmids, dirty_journal_ids, {})
        return

    logger.info("=" * 60)
    logger.info(
        f"PHASE 3: Updating snapshots for "
        f"{len(dirty_journal_ids):,} affected journals"
    )

    if not dirty_journal_ids:
        logger.info("  No journals affected — nothing to update")
        db.close()
        _print_summary(start_time, new_pmids, dirty_journal_ids, {})
        return

    now = datetime.now()
    calc = ImpactCalculator(db)

    dirty_journals_data = {}  # slug → latest snapshot (for index update)
    skipped = 0

    for i, jid in enumerate(sorted(dirty_journal_ids)):
        journal = journal_by_id.get(jid)
        if not journal:
            continue

        slug = journal["slug"]
        name = journal["name"]
        issn = journal["issn"]

        result = update_journal_snapshot(
            db, calc, jid, slug, name, issn, now, WEBSITE_DATA_DIR,
        )

        if result:
            dirty_journals_data[slug] = result
        else:
            skipped += 1

        if (i + 1) % 500 == 0 or (i + 1) == len(dirty_journal_ids):
            logger.info(
                f"  Progress: {i + 1:,}/{len(dirty_journal_ids):,} journals"
            )

    logger.info(
        f"  Updated {len(dirty_journals_data):,} journal JSONs"
        + (f" (skipped {skipped} without existing JSON)" if skipped else "")
    )

    # Update index.json
    update_index(WEBSITE_DATA_DIR, dirty_journals_data)

    db.close()
    _print_summary(start_time, new_pmids, dirty_journal_ids,
                   dirty_journals_data, inserted=inserted_count)


def _print_summary(start_time, new_pmids, dirty_journal_ids, dirty_journals_data,
                   inserted=None):
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info(f"Weekly update complete in {elapsed:.0f}s ({elapsed / 60:.1f} min)")
    logger.info(f"  New PMIDs fetched:    {len(new_pmids):,}")
    if inserted is not None:
        logger.info(f"  Papers inserted:      {inserted:,}")
    logger.info(f"  Journals affected:    {len(dirty_journal_ids):,}")
    logger.info(f"  Snapshots updated:    {len(dirty_journals_data):,}")

    for phase, pmids in FAILED_PMIDS.items():
        if not pmids:
            continue
        out = REPO_ROOT / "data" / f"failed_pmids_{phase}.txt"
        out.write_text("\n".join(str(x) for x in pmids) + "\n")
        logger.warning(
            f"  {len(pmids):,} PMIDs permanently failed in {phase} — "
            f"written to {out}"
        )

    logger.info("")
    logger.info("Next step: python scripts/upload_to_r2.py")


if __name__ == "__main__":
    main()
