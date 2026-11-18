"""Write JOURNALS.csv at the repo root: every journal IMPACT tracks.

Reads docs/data/index.json, so it needs no pipeline run. GitHub shows the CSV as a
searchable table; the site's About page links to it.

    python scripts/export_journal_list.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    index = json.loads((ROOT / "docs/data/index.json").read_text())
    journals = sorted(index["journals"], key=lambda j: j["name"].casefold())
    out = ROOT / "JOURNALS.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Journal", "Abbreviation", "ISSN"])
        for j in journals:
            writer.writerow([j["name"], j.get("abbreviation") or "", j.get("issn") or ""])
    print(f"Wrote {len(journals)} journals to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
