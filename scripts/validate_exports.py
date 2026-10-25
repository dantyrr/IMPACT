#!/usr/bin/env python3
"""
Validate exported JSON files for structure and completeness.
Run after compute_snapshots.py to ensure exports are well-formed.

Checks the v2 (citable-items) shape: every timeseries point carries
citable_papers / citable_citations / inferred_papers, journal files and index
entries carry `flags`, and classes/{slug}.json exists per journal. Journal
files whose last_updated is older than --since (default: today) fail, so
old-formula files left behind by a run cannot be uploaded under v2/.

Usage:
    python scripts/validate_exports.py [--since YYYY-MM-DD]
                                       [--data-dir DIR] [--journals-dir DIR]
Exit code: 0 passed, 1 failed.
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.pipeline.config import WEBSITE_DATA_DIR, SNAPSHOTS_DIR  # noqa: E402

POINT_KEYS = ["month", "rolling_if", "papers", "citations"]
V2_POINT_KEYS = ["citable_papers", "citable_citations", "inferred_papers"]
TIMESERIES_KEYS = ["timeseries", "timeseries_12mo", "timeseries_5yr"]


def validate_journal_file(path: Path, since: str = None, classes_dir: Path = None) -> list:
    errors = []
    with open(path) as f:
        data = json.load(f)

    required_top = ["journal", "slug", "issn", "last_updated", "latest", "timeseries", "flags"]
    for key in required_top:
        if key not in data:
            errors.append(f"{path.name}: missing top-level key '{key}'")

    latest = data.get("latest", {})
    for key in ["rolling_if", "paper_count", "citation_count"]:
        if key not in latest:
            errors.append(f"{path.name}: latest missing '{key}'")

    if not data.get("timeseries"):
        errors.append(f"{path.name}: empty timeseries")
    for ts_key in TIMESERIES_KEYS:
        for i, entry in enumerate(data.get(ts_key) or []):
            keys = (POINT_KEYS if i < 3 else []) + V2_POINT_KEYS  # base keys spot-checked
            for key in keys:
                if key not in entry:
                    errors.append(f"{path.name}: {ts_key}[{i}] missing '{key}'")

    updated = data.get("last_updated")
    if since and updated and str(updated)[:10] < since:
        errors.append(f"{path.name}: last_updated {updated} is older than --since {since} "
                      f"(stale file from an earlier export)")

    if classes_dir is not None:
        slug = data.get("slug") or path.stem
        if not (classes_dir / f"{slug}.json").exists():
            errors.append(f"{path.name}: missing classes/{slug}.json")

    return errors


def validate_index(path: Path) -> list:
    errors = []
    with open(path) as f:
        data = json.load(f)

    if "journals" not in data:
        errors.append("index.json: missing 'journals' key")
    elif not data["journals"]:
        errors.append("index.json: journals list is empty")
    else:
        for j in data["journals"]:
            for key in ["slug", "name", "issn", "latest_if"]:
                if key not in j:
                    errors.append(f"index.json: journal entry missing '{key}'")
            if "flags" not in j:
                errors.append(f"index.json: entry {j.get('slug')!r} missing 'flags'")

    return errors


def _iso_date(s: str) -> str:
    return date.fromisoformat(s).isoformat()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--since", type=_iso_date, default=date.today().isoformat(),
                    help="fail journal files with last_updated before this date (default: today)")
    ap.add_argument("--data-dir", type=Path, default=Path(WEBSITE_DATA_DIR))
    ap.add_argument("--journals-dir", type=Path, default=Path(SNAPSHOTS_DIR))
    args = ap.parse_args(argv)
    all_errors = []

    # Validate index
    index_path = args.data_dir / "index.json"
    if index_path.exists():
        all_errors.extend(validate_index(index_path))
    else:
        all_errors.append(f"Missing: {index_path}")

    # Validate journal files
    journal_files = sorted(args.journals_dir.glob("*.json"))
    if not journal_files:
        all_errors.append(f"No journal JSON files found in {args.journals_dir}")

    classes_dir = args.data_dir / "classes"
    for jf in journal_files:
        all_errors.extend(validate_journal_file(jf, args.since, classes_dir))

    # Report
    if all_errors:
        print(f"Validation FAILED ({len(all_errors)} error(s)):")
        for e in all_errors:
            print(f"  ✗ {e}")
        return 1
    print(f"Validation PASSED — {len(journal_files)} journal files (all updated since "
          f"{args.since}, v2 fields, flags, classes files), index.json ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
