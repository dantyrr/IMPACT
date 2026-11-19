"""Write JOURNALS.csv at the repo root: every journal IMPACT tracks.

Reads docs/data/index.json, so it needs no pipeline run. The weekly update also
rewrites it. GitHub shows the CSV as a searchable table; the site's About page links to it.

    python scripts/export_journal_list.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.journal_list import CSV_PATH, REPO_ROOT, write_journal_list


if __name__ == "__main__":
    count = write_journal_list()
    print(f"Wrote {count} journals to {CSV_PATH.relative_to(REPO_ROOT)}")
