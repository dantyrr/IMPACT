"""One parser for PubMed XML, shared by the baseline/update-file ingest and the
weekly EFetch path.

iter_pubmed_xml() streams a PubmedArticleSet; parse_article() turns one
PubmedArticle element into a flat record dict. PubMed's publication types are
recorded as-is in ``pub_types``; ``pub_type`` is the canonical single type
derived from them.
"""

import re
import xml.etree.ElementTree as ET
from typing import Iterator, Optional, Tuple

from src.pipeline.impact_calculator import canonical_pub_type

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

ORCID_RE = re.compile(r"(\d{4})-?(\d{4})-?(\d{4})-?(\d{3}[\dX])$", re.IGNORECASE)
ROR_RE = re.compile(r"([0-9a-z]{9})\s*$", re.IGNORECASE)


def normalize_orcid(raw: Optional[str]) -> Optional[str]:
    """Reduce the forms PubMed uses (bare, URL, unhyphenated) to 0000-0000-0000-000X."""
    m = ORCID_RE.search(re.sub(r"\s", "", raw or ""))
    if not m:
        return None
    return "-".join(m.groups()).upper()


def _normalize_ror(raw: Optional[str]) -> Optional[str]:
    """https://ror.org/03vek6s52 -> 03vek6s52."""
    m = ROR_RE.search((raw or "").strip().rstrip("/"))
    return m.group(1).lower() if m else None


def parse_page_count(medline_pgn: Optional[str]) -> Optional[int]:
    """Pages from a ``start-end`` MedlinePgn with numeric ends; an abbreviated
    end ("1801-2") is expanded from the start. A single number is 1 page.
    Anything else (e-locators, "e1-e40") gives None."""
    s = (medline_pgn or "").strip()
    if not s:
        return None
    if s.isdigit():
        return 1
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", s)
    if not m:
        return None
    start, end = m.group(1), m.group(2)
    if len(end) < len(start):
        end = start[: len(start) - len(end)] + end
    n = int(end) - int(start) + 1
    return n if n >= 1 else None


def _parse_month(text: str) -> Optional[int]:
    if not text:
        return None
    text = text.strip()
    if text.isdigit():
        v = int(text)
        return v if 1 <= v <= 12 else None
    # Handle "Jan-Feb" -> "Jan"
    return MONTH_MAP.get(text.split("-")[0][:3])


def _get_date(article_elem) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract (year, month) from an Article element.
    Prefer ArticleDate (electronic pub) over JournalIssue/PubDate.
    """
    # 1. Electronic pub date (most precise - when paper was first citable)
    art_date = article_elem.find("ArticleDate[@DateType='Electronic']")
    if art_date is not None:
        y = art_date.findtext("Year")
        if y and y.isdigit():
            return int(y), _parse_month(art_date.findtext("Month", ""))

    # 2. Journal issue pub date
    ji = article_elem.find("Journal/JournalIssue/PubDate")
    if ji is not None:
        y = ji.findtext("Year")
        if y and y.isdigit():
            return int(y), _parse_month(ji.findtext("Month", ""))
        # MedlineDate fallback e.g. "2023 Jan-Feb"
        ml = ji.findtext("MedlineDate", "")
        if ml:
            parts = ml.strip().split()
            if parts and parts[0].isdigit():
                month = _parse_month(parts[1]) if len(parts) > 1 else None
                return int(parts[0]), month

    return None, None


def _text(el) -> Optional[str]:
    """All text inside an element, including inline markup like <i>."""
    if el is None:
        return None
    return "".join(el.itertext()).strip() or None


def _parse_author(a, position: int) -> dict:
    affiliations = []
    for ai in a.findall("AffiliationInfo"):
        text = _text(ai.find("Affiliation"))
        if not text:
            continue
        ror = next((r for r in (_normalize_ror(i.text)
                                for i in ai.findall("Identifier[@Source='ROR']")) if r), None)
        affiliations.append({"text": text, "ror_id": ror})
    return {
        "position": position,
        "last_name": _text(a.find("LastName")),
        "fore_name": _text(a.find("ForeName")),
        "initials": _text(a.find("Initials")),
        "collective_name": _text(a.find("CollectiveName")),
        "orcid": next((o for o in (normalize_orcid(i.text)
                                   for i in a.findall("Identifier[@Source='ORCID']"))
                       if o), None),
        "affiliations": affiliations,
    }


def _author_name(author: dict) -> Optional[str]:
    if author["last_name"]:
        return f"{author['last_name']}, {author['fore_name'] or ''}".strip(", ")
    return author["collective_name"]


def _author_affil(author: dict) -> Optional[str]:
    return author["affiliations"][0]["text"][:500] if author["affiliations"] else None


def parse_article(article_elem) -> Optional[dict]:
    """Parse one PubmedArticle element into a flat dict (None if unusable)."""
    mc = article_elem.find("MedlineCitation")
    if mc is None:
        return None

    pmid_el = mc.find("PMID")
    if pmid_el is None or not pmid_el.text:
        return None
    try:
        pmid = int(pmid_el.text.strip())
    except ValueError:
        return None

    art = mc.find("Article")
    if art is None:
        return None

    # ISSN - ISSNLinking is most reliable (same as what ESearch uses)
    issn = None
    mji = mc.find("MedlineJournalInfo")
    if mji is not None:
        issn = (mji.findtext("ISSNLinking") or "").strip() or None
    journal = art.find("Journal")
    if not issn:
        if journal is not None:
            for issn_type in ("Electronic", "Print"):
                el = journal.find(f"ISSN[@IssnType='{issn_type}']")
                if el is not None and el.text:
                    issn = el.text.strip()
                    break
    issns = []
    if journal is not None:
        issns = [e.text.strip() for e in journal.findall("ISSN") if e.text and e.text.strip()]

    # Dates
    pub_year, pub_month = _get_date(art)
    if not pub_year:
        return None  # skip records with no date at all

    # Title
    title_el = art.find("ArticleTitle")
    title = ""
    if title_el is not None:
        # Flatten any nested XML tags (e.g. <i>, <sub>) to plain text
        title = "".join(title_el.itertext()).strip().rstrip(".")[:500]

    # Authors: ValidYN="N" is a name PubMed later corrected; positions are
    # numbered among the valid authors. InvestigatorList is not read.
    author_list = art.find("AuthorList")
    authors = []
    for a in (author_list.findall("Author") if author_list is not None else []):
        if a.get("ValidYN") == "N":
            continue
        authors.append(_parse_author(a, len(authors) + 1))
    first_author = first_affil = last_author = last_affil = None
    if authors:
        first, last = authors[0], authors[-1]
        first_author, first_affil = _author_name(first), _author_affil(first)
        last_author, last_affil = _author_name(last), _author_affil(last)

    # Publication types, as PubMed records them
    pub_types = [pt.text.strip() for pt in art.findall("PublicationTypeList/PublicationType")
                 if pt.text and pt.text.strip()]

    # Abstract / pagination signals
    has_abstract = any((_text(t) or "") for t in art.findall("Abstract/AbstractText"))
    pagination = (art.findtext("Pagination/MedlinePgn") or "").strip() or None

    # DOI (in PubmedData, sibling of MedlineCitation)
    doi = None
    pd_data = article_elem.find("PubmedData")
    if pd_data is not None:
        for ai in pd_data.findall("ArticleIdList/ArticleId"):
            if ai.get("IdType") == "doi" and ai.text:
                doi = ai.text.strip()[:200]
                break

    return {
        "pmid":         pmid,
        "issn":         issn,
        "issns":        issns,
        "pub_year":     pub_year,
        "pub_month":    pub_month if pub_month is not None else 6,
        "title":        title,
        "doi":          doi,
        "pub_types":    pub_types,
        "pub_type":     canonical_pub_type(pub_types),
        "has_abstract": has_abstract,
        "pagination":   pagination,
        "page_count":   parse_page_count(pagination),
        "first_author": first_author,
        "first_affil":  first_affil,
        "last_author":  last_author,
        "last_affil":   last_affil,
        "authors":      authors,
    }


def iter_pubmed_xml(fileobj) -> Iterator[Tuple[str, object]]:
    """Stream a PubmedArticleSet, yielding ("record", dict) per parsable
    PubmedArticle and ("delete", pmid) per PMID inside DeleteCitation."""
    for _, elem in ET.iterparse(fileobj, events=("end",)):
        if elem.tag == "PubmedArticle":
            rec = parse_article(elem)
            if rec:
                yield "record", rec
            elem.clear()
        elif elem.tag == "DeleteCitation":
            for p in elem.findall("PMID"):
                if p.text and p.text.strip().isdigit():
                    yield "delete", int(p.text.strip())
            elem.clear()
