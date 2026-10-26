"""Tests for scripts/validate_exports.py on a tmp data dir (v2 export shape)."""
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate_exports.py"
_spec = importlib.util.spec_from_file_location("validate_exports", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

RUN_DAY = "2026-10-20"


def point(month="2024-12", **drop):
    p = {"month": month, "rolling_if": 1.0, "papers": 10, "citations": 10,
         "citable_papers": 8, "citable_citations": 9, "inferred_papers": 1}
    for k in drop:
        p.pop(k)
    return p


def journal(slug, last_updated=RUN_DAY, points=None, flags=True):
    d = {"journal": slug.title(), "slug": slug, "issn": "1111-1111", "last_updated": last_updated,
         "latest": {"rolling_if": 1.0, "paper_count": 10, "citation_count": 10},
         "timeseries": points if points is not None else [point("2024-11"), point("2024-12")]}
    if flags:
        d["flags"] = []
    return d


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "data"
    (root / "journals").mkdir(parents=True)
    (root / "classes").mkdir()
    return root


def write(data, journals, index_flags=True, classes=None):
    for j in journals:
        (data / "journals" / f"{j['slug']}.json").write_text(json.dumps(j))
    for slug in (classes if classes is not None else [j["slug"] for j in journals]):
        (data / "classes" / f"{slug}.json").write_text('{"v":1,"citable":[],"noncitable":[]}')
    entries = []
    for j in journals:
        e = {"slug": j["slug"], "name": j["journal"], "issn": j["issn"], "latest_if": 1.0}
        if index_flags:
            e["flags"] = []
        entries.append(e)
    (data / "index.json").write_text(json.dumps({"journals": entries}))


def run(data, *args):
    return mod.main(["--data-dir", str(data), "--journals-dir", str(data / "journals"),
                     "--since", RUN_DAY, *args])


def test_valid_v2_export_passes(data, capsys):
    write(data, [journal("a"), journal("b")])
    assert run(data) == 0
    assert "PASSED" in capsys.readouterr().out


def test_missing_citable_fields_in_any_point_fail(data, capsys):
    pts = [point("2024-%02d" % m) for m in range(1, 8)] + [point("2024-08", inferred_papers=1)]
    write(data, [journal("a", points=pts)])
    assert run(data) == 1
    out = capsys.readouterr().out
    assert "a.json: timeseries[7] missing 'inferred_papers'" in out


@pytest.mark.parametrize("field", ["citable_papers", "citable_citations"])
def test_each_citable_field_required(data, capsys, field):
    write(data, [journal("a", points=[point(**{field: 1})])])
    assert run(data) == 1
    assert f"missing '{field}'" in capsys.readouterr().out


def test_journal_without_flags_fails(data, capsys):
    write(data, [journal("a", flags=False)])
    assert run(data) == 1
    assert "a.json: missing top-level key 'flags'" in capsys.readouterr().out


def test_index_entry_without_flags_fails(data, capsys):
    write(data, [journal("a")], index_flags=False)
    assert run(data) == 1
    assert "index.json: entry 'a' missing 'flags'" in capsys.readouterr().out


def test_missing_classes_file_fails(data, capsys):
    write(data, [journal("a"), journal("b")], classes=["a"])
    assert run(data) == 1
    assert "missing classes/b.json" in capsys.readouterr().out


def test_stale_journal_file_fails(data, capsys):
    write(data, [journal("a"), journal("old", last_updated="2026-03-01")])
    assert run(data) == 1
    out = capsys.readouterr().out
    assert "old.json: last_updated 2026-03-01 is older than --since 2026-10-20" in out
    assert "a.json: last_updated" not in out


def test_since_defaults_to_today(data, capsys):
    write(data, [journal("a", last_updated=RUN_DAY)])
    assert mod.main(["--data-dir", str(data), "--journals-dir", str(data / "journals")]) == \
        (0 if RUN_DAY >= date.today().isoformat() else 1)
    write(data, [journal("a", last_updated=date.today().isoformat())])
    assert mod.main(["--data-dir", str(data), "--journals-dir", str(data / "journals")]) == 0


def test_existing_checks_kept(data, capsys):
    j = journal("a")
    del j["latest"]["rolling_if"]
    write(data, [j])
    (data / "index.json").write_text(json.dumps({"journals": []}))
    assert run(data) == 1
    out = capsys.readouterr().out
    assert "latest missing 'rolling_if'" in out and "journals list is empty" in out


GEO = {"papers": {}, "intl": {}, "us_papers": {}, "countries": {}, "states": {},
       "country_pairs": {}, "state_pairs": {}}


def test_geo_files_checked_once_the_directory_exists(data, capsys):
    write(data, [journal("a"), journal("b")])
    (data / "geo").mkdir()
    (data / "geo" / "_all.json").write_text(json.dumps(GEO))
    (data / "geo" / "a.json").write_text(json.dumps(GEO))
    (data / "geo" / "b.json").write_text(json.dumps({"papers": {}}))
    assert run(data) == 1
    out = capsys.readouterr().out
    assert "geo/b.json: missing intl" in out
    (data / "geo" / "b.json").write_text(json.dumps(GEO))
    assert run(data) == 0
