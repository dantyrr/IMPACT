import os

import pytest

from src.pipeline.doc_class import CITABLE, INFERENCE, class_for_types, classify
from src.pipeline.impact_calculator import ARTICLE_CATEGORIES, classify_pub_type
from src.pipeline.pubmed_xml import iter_pubmed_xml

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="module")
def records():
    with open(os.path.join(FIX, "pubmed_records.xml"), "rb") as f:
        return {r["pmid"]: r for kind, r in iter_pubmed_xml(f) if kind == "record"}


def _classify(r, icite=None):
    return classify(r["pub_types"], r["has_abstract"], r["page_count"], icite, r["title"])


def test_fixture_classes(records):
    assert _classify(records[1001]) == ("research", "pubmed")
    assert _classify(records[1002]) == ("commentary", "inferred")
    assert _classify(records[1003]) == ("letter", "pubmed")
    assert _classify(records[1004]) == ("guideline", "pubmed")
    assert _classify(records[1005]) == ("research", "pubmed")


def test_recover_letters_off_by_default():
    assert INFERENCE["recover_letters"] is False


def test_citable_set():
    assert CITABLE == frozenset({"research", "review", "case_report", "guideline"})


def test_categories():
    assert ARTICLE_CATEGORIES == (
        "research", "review", "case_report", "guideline", "commentary",
        "editorial", "letter", "erratum", "other")


def test_retracted_publication_is_research_not_erratum():
    assert class_for_types(["Journal Article", "Retracted Publication"]) == "research"


@pytest.mark.parametrize("t", ["Published Erratum", "Retraction of Publication",
                               "Retraction Notice", "Expression of Concern"])
def test_erratum_group_wins(t):
    assert class_for_types(["Journal Article", "Review", t]) == "erratum"


def test_classify_pub_type_empty_stays_research():
    assert classify_pub_type(None) == "research"
    assert classify_pub_type("") == "research"
    assert class_for_types([]) == "other"


def test_case_insensitive():
    assert class_for_types(["journal article", "REVIEW"]) == "review"
    assert classify_pub_type("practice guideline") == "guideline"


def test_priority_order():
    assert class_for_types(["Journal Article", "Review", "Practice Guideline"]) == "guideline"
    assert class_for_types(["Case Reports", "Review"]) == "review"
    assert class_for_types(["Journal Article", "Case Reports"]) == "case_report"
    assert class_for_types(["Editorial", "Comment"]) == "editorial"
    assert class_for_types(["Comment", "News"]) == "letter"
    assert class_for_types(["Journal Article", "Biography"]) == "other"


def test_clinical_trial_alone_is_other_but_with_article_is_research():
    assert class_for_types(["Clinical Trial"]) == "other"
    assert class_for_types(["Journal Article", "Clinical Trial"]) == "research"
    assert class_for_types(["Journal Article", "Randomized Controlled Trial"]) == "research"


def test_inference_branches():
    assert classify(["Journal Article"], False, 2, None, "t") == ("commentary", "inferred")
    assert classify(["Journal Article"], False, None, False, "t") == ("commentary", "inferred")
    assert classify(["Journal Article"], False, 5, None, "t") == ("research", "pubmed")
    assert classify(["Journal Article"], False, None, True, "t") == ("research", "pubmed")
    assert classify(["Journal Article"], None, 1, False, "t") == ("research", "pubmed")
    assert classify(["Journal Article"], True, 1, False, "t") == ("research", "pubmed")
    assert classify(["Review"], False, 1, False, "t") == ("review", "pubmed")


def test_icite_never_sets_class_directly():
    assert classify(["Letter"], True, 9, True, "t") == ("letter", "pubmed")


def test_inference_knobs_are_read(monkeypatch):
    monkeypatch.setitem(INFERENCE, "max_pages", 0)
    assert classify(["Journal Article"], False, 2, None, "t") == ("research", "pubmed")
