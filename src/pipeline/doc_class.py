"""
Document classifier: the single source of truth for whether a paper is citable.

doc_class is derived from PubMed publication types (full list, not one string),
with a small, tunable inference step for records PubMed typed as "Journal
Article" that look like front-matter (no abstract and very short, or iCite says
not a research article). PubMed's own pub_type column is never overwritten.
"""
from typing import List, Optional, Tuple

CITABLE = frozenset({'research', 'review', 'case_report', 'guideline'})

# Tunable parameters of the inference rule (validated/adjusted in Task 7).
INFERENCE = {
    'max_pages': 2,            # no-abstract research with page_count <= this -> commentary
    'use_icite': True,         # icite_is_research is False counts as evidence
    'recover_letters': False,  # letter -> research recovery; off until a signal is validated
}

# Priority groups, first group with any match wins. Matching is case-insensitive
# (the weekly path once stored lowercase types).
#
# Guideline outranks review deliberately: a guideline also tagged Review is a
# guideline. Both are citable, so the order only affects labels, but putting
# review first left the guideline bucket empty.
#
# "Retracted Publication" is PubMed's tag on the retracted paper itself, so it
# is NOT in the erratum group; only the notices are.
#
# The old ARTICLE_TYPE_MAP mapped Clinical Trial / Randomized Controlled Trial
# to research. Because we classify the whole type list and PubMed tags such
# papers "Journal Article" as well, they land in research via that entry, so no
# explicit mapping is needed (a trial type alone is 'other').
_GROUPS = (
    ('erratum', ('Published Erratum', 'Retraction of Publication',
                 'Retraction Notice', 'Expression of Concern')),
    ('guideline', ('Practice Guideline', 'Guideline', 'Consensus Development Conference')),
    ('review', ('Systematic Review', 'Meta-Analysis', 'Review')),
    ('case_report', ('Case Reports',)),
    ('editorial', ('Editorial',)),
    ('letter', ('Letter', 'Comment', 'Editorial Comment')),
    ('other', ('News', 'Biography', 'Obituary', 'Interview', 'Portrait', 'Congress')),
    ('research', ('Journal Article',)),
)
_GROUPS_CI = tuple((cls, frozenset(t.lower() for t in types)) for cls, types in _GROUPS)


def class_for_types(pub_types: List[str]) -> str:
    """Class implied by PubMed publication types alone."""
    present = {str(t).strip().lower() for t in (pub_types or []) if t}
    for cls, types in _GROUPS_CI:
        if present & types:
            return cls
    return 'other'


def icite_evidence(value) -> Optional[bool]:
    """iCite's is_research_article as evidence: True/False, or None when unknown.

    The API has returned booleans and "Yes"/"No" strings; a missing value is no
    evidence (None), never False."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("yes", "true", "1"):
            return True
        if v in ("no", "false", "0"):
            return False
        return None
    return bool(value)


def classify(pub_types: List[str], has_abstract: Optional[bool],
             page_count: Optional[int], icite_is_research: Optional[bool],
             title: Optional[str]) -> Tuple[str, str]:
    """Return (doc_class, class_source). source is 'pubmed' or 'inferred'.

    iCite's is_research_article is evidence for inference only; it never sets
    doc_class by itself."""
    cls = class_for_types(pub_types)
    if cls == 'research' and has_abstract is False:
        short = page_count is not None and page_count <= INFERENCE['max_pages']
        not_research = INFERENCE['use_icite'] and icite_is_research is False
        if short or not_research:
            return 'commentary', 'inferred'
    return cls, 'pubmed'
