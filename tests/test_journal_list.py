import csv
import json

from src.pipeline.journal_list import write_journal_list


def test_writes_sorted_rows_with_blank_missing_fields(tmp_path):
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"journals": [
        {"slug": "b", "name": "beta Journal", "abbreviation": "Beta J", "issn": "1111-1111"},
        {"slug": "a", "name": "Alpha, Journal of", "abbreviation": None, "issn": "2222-2222"},
        {"slug": "c", "name": "Gamma \"Letters\"", "abbreviation": "Gamma Lett"},
    ]}))
    out = tmp_path / "JOURNALS.csv"

    assert write_journal_list(index, out) == 3

    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [
        ["Journal", "Abbreviation", "ISSN"],
        ["Alpha, Journal of", "", "2222-2222"],
        ["beta Journal", "Beta J", "1111-1111"],
        ["Gamma \"Letters\"", "Gamma Lett", ""],
    ]
