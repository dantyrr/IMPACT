#!/usr/bin/env python3
"""
Save an author profile JSON and optionally upload to R2.

Creates a profile JSON file containing a name and list of PMIDs,
then places it in docs/data/profiles/ for R2 upload.

Usage:
    # From a file of PMIDs (one per line):
    python scripts/save_profile.py "Daniel Tyrrell" pmids.txt

    # From a downloaded profile JSON (e.g. from the site's Save Profile button):
    python scripts/save_profile.py --from-json Daniel_Tyrrell.json

    # Upload to R2 immediately after saving:
    python scripts/save_profile.py "Daniel Tyrrell" pmids.txt --upload
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROFILES_DIR = Path(__file__).parent.parent / "docs" / "data" / "profiles"


def slug_from_name(name: str) -> str:
    return name.strip().replace(" ", "_")


def save_profile(name: str, pmids: list[str], slug: str | None = None):
    slug = slug or slug_from_name(name)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    out_path = PROFILES_DIR / f"{slug}.json"
    today = date.today().isoformat()

    # Preserve created date if profile already exists
    created = today
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
            created = existing.get("created", today)
        except Exception:
            pass

    profile = {
        "name": name,
        "slug": slug,
        "pmids": pmids,
        "created": created,
        "updated": today,
    }

    out_path.write_text(json.dumps(profile, indent=2) + "\n")
    print(f"Saved {len(pmids)} PMIDs → {out_path}")
    return out_path


def upload_profile(path: Path):
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3")
        sys.exit(1)

    from src.pipeline.config import (
        R2_ACCOUNT_ID, R2_BUCKET_NAME, R2_ACCESS_KEY_ID,
        R2_SECRET_ACCESS_KEY, R2_PUBLIC_URL,
    )

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )

    key = f"profiles/{path.name}"
    client.upload_file(
        str(path), R2_BUCKET_NAME, key,
        ExtraArgs={"ContentType": "application/json", "CacheControl": "public, max-age=3600"},
    )
    url = f"{R2_PUBLIC_URL}/{key}" if R2_PUBLIC_URL else key
    print(f"Uploaded to R2: {url}")


def main():
    parser = argparse.ArgumentParser(description="Save an author profile")
    parser.add_argument("name", nargs="?", help="Author name (e.g. 'Daniel Tyrrell')")
    parser.add_argument("pmid_file", nargs="?", help="File with PMIDs (one per line or comma-separated)")
    parser.add_argument("--from-json", help="Import from a downloaded profile JSON file")
    parser.add_argument("--upload", action="store_true", help="Upload to R2 after saving")
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(Path(args.from_json).read_text())
        name = data.get("name", "")
        slug = data.get("slug", slug_from_name(name))
        pmids = [str(p) for p in data.get("pmids", [])]
        if not pmids:
            print("ERROR: No PMIDs found in JSON file"); sys.exit(1)
        path = save_profile(name, pmids, slug)
    elif args.name and args.pmid_file:
        text = Path(args.pmid_file).read_text()
        pmids = list(dict.fromkeys(
            p.strip() for p in text.replace(",", "\n").splitlines()
            if p.strip() and p.strip().isdigit()
        ))
        if not pmids:
            print("ERROR: No valid PMIDs found in file"); sys.exit(1)
        path = save_profile(args.name, pmids)
    else:
        parser.print_help()
        sys.exit(1)

    if args.upload:
        upload_profile(path)
    else:
        print(f"To upload: python scripts/upload_to_r2.py  (or re-run with --upload)")


if __name__ == "__main__":
    main()
