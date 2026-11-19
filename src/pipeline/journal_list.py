"""JOURNALS.csv: every journal IMPACT tracks, for the repo (the About page links to it).

Written from docs/data/index.json by scripts/export_journal_list.py and at the end of
each weekly update. GitHub shows the CSV as a searchable table.
"""
import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_PATH = REPO_ROOT / "docs" / "data" / "index.json"
CSV_PATH = REPO_ROOT / "JOURNALS.csv"


def write_journal_list(index_path=INDEX_PATH, out_path=CSV_PATH):
    """Write one row per journal (name, abbreviation, ISSN), sorted by name.

    Returns the number of journals written.
    """
    index = json.loads(Path(index_path).read_text())
    journals = sorted(index["journals"], key=lambda j: j["name"].casefold())
    with Path(out_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Journal", "Abbreviation", "ISSN"])
        for j in journals:
            writer.writerow([j["name"], j.get("abbreviation") or "", j.get("issn") or ""])
    return len(journals)
