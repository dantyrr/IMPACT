import os

import pytest

from src.pipeline.pubmed_xml import iter_pubmed_xml, normalize_orcid, parse_page_count

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="module")
def events():
    with open(os.path.join(FIX, "pubmed_records.xml"), "rb") as f:
        return list(iter_pubmed_xml(f))


@pytest.fixture(scope="module")
def records(events):
    return {r["pmid"]: r for kind, r in events if kind == "record"}


def test_record_fields(records):
    r = records[1001]
    assert r["pub_types"] == ["Journal Article"] and r["has_abstract"] is True
    assert r["page_count"] == 8 and r["pub_type"] == "Journal Article"
    assert r["issn"] == "1234-5679" and r["issns"] == ["1234-5678"]
    assert r["pub_year"] == 2020 and r["pub_month"] == 3
    assert r["title"] == "Title of paper 1001"
    assert r["doi"] == "10.1/a"
    assert r["first_author"] == "Adams, Ann" and r["last_author"] == "Baker, Bo"
    assert r["first_affil"] == "Univ A, Town, USA." and r["last_affil"] is None


def test_seven_records(records):
    assert sorted(records) == [1001, 1002, 1003, 1004, 1005, 1006, 1007]


def test_highlight_signals(records):
    assert records[1002]["has_abstract"] is False and records[1002]["page_count"] == 1


def test_letter(records):
    assert records[1003]["pub_type"] == "Letter" and records[1003]["page_count"] == 2


def test_full_type_list_kept(records):
    assert records[1004]["pub_types"] == ["Review", "Practice Guideline"]
    assert records[1004]["pub_type"] == "Review"


def test_elocator_pagination_has_no_page_count(records):
    assert records[1005]["pagination"] == "e0123456"
    assert records[1005]["page_count"] is None


def test_group_author_and_invalid_name(records):
    a = records[1006]["authors"]
    assert [x["position"] for x in a] == list(range(1, len(a) + 1))
    assert [x["last_name"] for x in a] == ["Chen", None, "Diaz"]
    assert any(x["collective_name"] for x in a)
    assert any(f["ror_id"] == "03vek6s52" for x in a for f in x["affiliations"])
    assert records[1006]["pagination"] is None and records[1006]["page_count"] is None


def test_affiliation_text_kept_whole(records):
    aff = records[1007]["authors"][0]["affiliations"]
    assert aff == [{"text": "Dept X, Boston, MA, USA; Dept Y, Oxford, UK", "ror_id": None}]


def test_delete_citation_yields_delete(events):
    assert ("delete", 999) in events


def test_parse_page_count():
    assert parse_page_count("123-130") == 8
    assert parse_page_count("1801-2") == 2
    assert parse_page_count("5") == 1
    assert parse_page_count("e1-e40") is None
    assert parse_page_count("e0123456") is None
    assert parse_page_count("") is None and parse_page_count(None) is None


def test_normalize_orcid():
    assert normalize_orcid("https://orcid.org/0000-0002-1825-009x") == "0000-0002-1825-009X"
    assert normalize_orcid("0000000218250097") == "0000-0002-1825-0097"
    assert normalize_orcid("nope") is None and normalize_orcid(None) is None


def test_ncats_fixture_parity():
    # Expected values were read once from NCATS fetch_authors.parse_authors on
    # pubmed_authors.xml; hardcoded so this repo does not depend on that path.
    with open(os.path.join(FIX, "pubmed_authors.xml"), "rb") as f:
        got = {r["pmid"]: r["authors"] for k, r in iter_pubmed_xml(f) if k == "record"}
    a = lambda pos, last, fore, ini, coll, orcid, affs: {
        "position": pos, "last_name": last, "fore_name": fore, "initials": ini,
        "collective_name": coll, "orcid": orcid, "affiliations": affs}
    expected = {
        31000001: [
            a(1, "Smith", "Jane A", "JA", None, "0000-0002-1825-0097",
              ["Department of Medicine, University of Michigan, Ann Arbor, MI, USA.",
               "Michigan Institute for Clinical & Health Research, Ann Arbor, MI, USA."]),
            a(2, "Jones", "Robert", "R", None, "0000-0002-1825-0097",
              ["Duke Clinical Research Institute, Durham, NC, USA; "
               "Department of Biostatistics, Duke University, Durham, NC, USA."]),
            a(3, "Lee", "Min", "M", None, None, []),
        ],
        23000002: [
            a(1, "Garcia", "Ana", "A", None, None, ["University of Rochester, Rochester, NY."]),
            a(2, None, None, None, "CTSA Consortium Working Group", None, []),
        ],
        35000003: [],
    }
    assert sorted(got) == sorted(expected)
    for pmid, exp in expected.items():
        sliced = [{**x, "affiliations": [f["text"] for f in x["affiliations"]]}
                  for x in got[pmid]]
        assert sliced == exp
