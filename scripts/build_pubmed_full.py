#!/usr/bin/env python3
"""
Stream every PubMed baseline file, then every update file, into data/pubmed_full.db.

Files are applied strictly in order (baseline by name, then updates by name),
because update files re-deliver and delete records and must apply in sequence.
Each file's records are stored in chunks; a delete is applied only after the
records before it in the stream are stored. A file is marked in
processed_files only after all its rows have committed, so a run killed
mid-file reprocesses that file on resume (re-delivery is idempotent).

Usage:
    python scripts/build_pubmed_full.py [--limit N] [--min-free-gb 30]
    python scripts/build_pubmed_full.py --sample N   # size projection, separate DB

Requires a live `rebuild` lock holder (scripts/rebuild_lock.py hold).

Exit codes:
    0  done (or nothing left to do)
    1  refused: no live `rebuild` lock holder, or the holder went away mid-run
       (re-checked before each file; finished files are committed)
    2  --sample: projected author tables exceed AUTHOR_GB_LIMIT
    3  stopped: free disk below --min-free-gb (finished files are committed)
    4  stopped: a file still failed after retries (re-run resumes at that file),
       or the baseline listing was empty
    (argparse usage errors also exit 2)
"""

import argparse
import gzip
import io
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import List, Tuple

import requests

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.pipeline.config import DB_PATH, PUBMED_FULL_DB_PATH  # noqa: E402
from src.pipeline.pubmed_full_db import (delete_pmids, make_byline_scope,  # noqa: E402
                                         open_full_db, store_records,
                                         tracked_issns_from_impact)
from src.pipeline.pubmed_xml import iter_pubmed_xml  # noqa: E402
from src.pipeline.rebuild_guard import (_checkpoint, free_gb,  # noqa: E402,F401
                                        rebuild_lock_held)

logger = logging.getLogger("build_pubmed_full")

BASELINE_URL = "https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/"
UPDATE_URL = "https://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/"

IMPACT_DB_PATH = DB_PATH
FULL_DB_PATH = PUBMED_FULL_DB_PATH
DATA_DIR = os.path.dirname(PUBMED_FULL_DB_PATH)
SAMPLE_DB_PATH = os.path.join(DATA_DIR, "pubmed_full.sample.db")

CHUNK_SIZE = 5_000
CHECKPOINT_EVERY = 50
FILE_ATTEMPTS = 3
TOTAL_PAPERS = 24_900_000
AUTHOR_GB_LIMIT = 20
GB = 1e9
AUTHOR_TABLES = ("authors", "affil_strings", "affil_countries", "author_affils")


# ---- Network ----

def list_files(base_url: str, session: requests.Session) -> List[str]:
    """Return sorted .xml.gz filenames from an NCBI directory listing."""
    resp = session.get(base_url, timeout=30)
    resp.raise_for_status()
    return sorted(set(re.findall(r'href="(pubmed\d+n\d+\.xml\.gz)"', resp.text)))


def download_file(url: str, session: requests.Session, retries: int = 3) -> bytes:
    """Download one file from exactly `url` into memory, retrying on error."""
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=600, stream=True)
            resp.raise_for_status()
            buf = io.BytesIO()
            for chunk in resp.iter_content(chunk_size=131072):
                buf.write(chunk)
            return buf.getvalue()
        except Exception as e:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            logger.warning(f"  download failed ({e}), retry {attempt}/{retries} in {wait}s")
            time.sleep(wait)


# ---- Planning / environment ----

def plan_files(baseline: List[str], updates: List[str]) -> List[Tuple[str, str]]:
    """(url, filename): every baseline file by name, then every update file by name."""
    return ([(BASELINE_URL + f, f) for f in sorted(baseline)]
            + [(UPDATE_URL + f, f) for f in sorted(updates)])


# ---- Ingest ----

def process_file(conn, url: str, filename: str, in_scope, session=None) -> int:
    """Ingest one .xml.gz file in stream order; mark it processed last.

    Returns the number of records stored."""
    data = download_file(url, session)
    kind = "update" if "/updatefiles/" in url else "baseline"
    records, deletes = [], []
    n_records = 0

    def flush_records():
        if records:
            store_records(conn, records, in_scope)
            records.clear()

    def flush_deletes():
        if deletes:
            delete_pmids(conn, deletes)
            deletes.clear()

    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        for event, value in iter_pubmed_xml(f):
            if event == "record":
                flush_deletes()
                records.append(value)
                n_records += 1
                if len(records) >= CHUNK_SIZE:
                    flush_records()
            elif event == "delete":
                flush_records()
                deletes.append(value)
    flush_records()
    flush_deletes()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO processed_files (filename, kind, processed_at, record_count) "
            "VALUES (?,?,?,?)",
            (filename, kind, datetime.now(timezone.utc).isoformat(timespec="seconds"), n_records))
    return n_records


def _table_bytes(conn) -> dict:
    return dict(conn.execute(
        "SELECT m.tbl_name, SUM(s.pgsize) FROM dbstat s "
        "JOIN sqlite_master m ON s.name = m.name GROUP BY m.tbl_name"))


def project_size(conn, sampled_papers: int, total_papers: int,
                 sampled_files: int, total_files: int) -> dict:
    """Project full-build sizes (GB) from a sample: author tables scale with
    in-scope papers, the pubmed table with files."""
    sizes = _table_bytes(conn)
    author_bytes = sum(sizes.get(t, 0) for t in AUTHOR_TABLES)
    return {
        "author_tables_gb": author_bytes * total_papers / max(sampled_papers, 1) / GB,
        "pubmed_gb": sizes.get("pubmed", 0) * total_files / max(sampled_files, 1) / GB,
    }


def _counting(in_scope, seen: set):
    """Wrap a scope predicate so it also records the in-scope pmids it sees."""
    def wrapped(rec):
        ok = in_scope(rec)
        if ok:
            seen.add(rec["pmid"])
        return ok
    return wrapped


def _ingest_with_retries(conn, url, filename, in_scope, session) -> bool:
    for attempt in range(1, FILE_ATTEMPTS + 1):
        try:
            process_file(conn, url, filename, in_scope, session)
            return True
        except Exception as e:
            logger.warning(f"{filename}: attempt {attempt}/{FILE_ATTEMPTS} failed: {e}")
            if attempt < FILE_ATTEMPTS:
                time.sleep(2 ** attempt)
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sample", type=int, metavar="N",
                    help="ingest N evenly spread baseline files into a separate sample DB "
                         "and project full sizes")
    ap.add_argument("--limit", type=int, metavar="N", help="process at most N unprocessed files")
    ap.add_argument("--min-free-gb", type=float, default=30.0)
    args = ap.parse_args(argv)
    if args.sample is not None and args.sample < 1:
        ap.error("--sample must be >= 1")

    if not rebuild_lock_held():
        logger.error("refusing to run: no live `rebuild` lock holder "
                     "(start: python scripts/rebuild_lock.py hold)")
        return 1

    in_scope = make_byline_scope(tracked_issns_from_impact(IMPACT_DB_PATH))
    session = requests.Session()
    baseline = list_files(BASELINE_URL, session)
    if not baseline:
        # Never apply update files without the baseline beneath them.
        logger.error(f"no baseline files listed at {BASELINE_URL}; stopping")
        return 4

    if args.sample is not None:
        n = min(args.sample, len(baseline))
        picked = [baseline[i * len(baseline) // n] for i in range(n)]
        plan = plan_files(picked, [])
        db_path = SAMPLE_DB_PATH
        sampled = set()
        in_scope = _counting(in_scope, sampled)
    else:
        plan = plan_files(baseline, list_files(UPDATE_URL, session))
        db_path = FULL_DB_PATH

    conn = open_full_db(db_path)
    try:
        done = {r[0] for r in conn.execute("SELECT filename FROM processed_files")}
        # A sample re-ingests every picked file so the in-scope count is complete.
        todo = plan if args.sample is not None else [p for p in plan if p[1] not in done]
        if args.limit is not None:
            todo = todo[:args.limit]
        total = len(plan)
        n_done = 0 if args.sample is not None else total - len(todo)
        logger.info(f"{n_done} / {total} files already processed; {len(todo)} to do this run")

        for i, (url, filename) in enumerate(todo, 1):
            if not rebuild_lock_held():
                conn.commit()
                _checkpoint(conn)
                logger.error(f"stopping before {filename}: the rebuild lock holder is gone "
                             f"(the weekly job could now run); {n_done} / {total} files done. "
                             f"Restart `rebuild_lock.py hold` and re-run to resume.")
                return 1
            free = free_gb(DATA_DIR)
            if free < args.min_free_gb:
                conn.commit()
                _checkpoint(conn)
                logger.error(f"stopping: {free:.1f} GB free in {DATA_DIR} "
                             f"(< --min-free-gb {args.min_free_gb}); "
                             f"{n_done} / {total} files done")
                return 3
            if not _ingest_with_retries(conn, url, filename, in_scope, session):
                _checkpoint(conn)
                logger.error(f"stopping at {filename}: still failing after retries; "
                             f"{n_done} / {total} files done. Re-run to resume there.")
                return 4
            n_done += 1
            logger.info(f"{n_done} / {total} files ({filename})")
            if i % CHECKPOINT_EVERY == 0:
                _checkpoint(conn)
        _checkpoint(conn)

        if args.sample is not None:
            proj = project_size(conn, len(sampled), TOTAL_PAPERS, len(plan), len(baseline))
            author_bytes = sum(_table_bytes(conn).get(t, 0) for t in AUTHOR_TABLES)
            print(f"in-scope papers sampled: {len(sampled)}")
            print(f"bytes per in-scope paper (author tables): "
                  f"{author_bytes / max(len(sampled), 1):.1f}")
            print(f"projected author_tables_gb for {TOTAL_PAPERS:,} papers: "
                  f"{proj['author_tables_gb']:.2f} (limit {AUTHOR_GB_LIMIT})")
            print(f"projected pubmed_gb for {len(baseline)} baseline files: "
                  f"{proj['pubmed_gb']:.2f}")
            if proj["author_tables_gb"] > AUTHOR_GB_LIMIT:
                logger.error("projected author tables exceed the limit")
                return 2
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
