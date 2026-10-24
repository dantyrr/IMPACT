"""
IMPACT Calculator
Computes rolling 24-month impact factors, author metrics, and paper trajectories.

Rolling IF formula (JIF-equivalent):
    IF(month M, year Y) =
        Citations received in year Y by papers published in years Y-1 and Y-2
        ÷ Number of citable (research) articles published in Y-1 and Y-2

For our ROLLING monthly version:
    IF(YYYY-MM) =
        Citations received in the 12 months ending YYYY-MM
        by papers published in the 24 months before that 12-month window
        ÷ Number of research articles in that 24-month window
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from src.pipeline.db_manager import DatabaseManager
from src.pipeline.doc_class import CITABLE, class_for_types

logger = logging.getLogger(__name__)

# Display categories. Citable ones (research, review, case_report, guideline)
# are defined in doc_class.CITABLE.
ARTICLE_CATEGORIES = ('research', 'review', 'case_report', 'guideline', 'commentary',
                      'editorial', 'letter', 'erratum', 'other')

# Priority order when PubMed reports several types for one paper. PubMed
# usually lists "Journal Article" first even for a review, so taking the first
# entry mislabels reviews as research; the specific type has to win.
_REVIEW_TYPES = ('Systematic Review', 'Meta-Analysis', 'Review')
_GUIDELINE_TYPES = ('Practice Guideline', 'Guideline', 'Consensus Development Conference')
_NON_RESEARCH_TYPES = (
    'Editorial', 'Editorial Comment', 'Letter', 'Comment', 'Case Reports',
    'Published Erratum', 'Retraction of Publication', 'Expression of Concern',
    'News', 'Biography', 'Obituary',
)


def classify_pub_type(pub_type: Optional[str]) -> str:
    """Map a raw PubMed pub_type string to one of our display categories."""
    if not pub_type:
        return 'research'
    return class_for_types([pub_type])


def category_of(doc_class: Optional[str], pub_type: Optional[str]) -> str:
    """Display category: doc_class when set, else derived from pub_type (rows not
    yet classified by the pubmed_full rebuild have doc_class NULL)."""
    return doc_class if doc_class else classify_pub_type(pub_type)


def canonical_pub_type(pub_types) -> str:
    """Pick the most specific PubMed type from a paper's type list and return it
    in canonical Title Case, so it matches the doc_class groups and the strings the
    bulk pipeline writes.

    Priority: review > guideline > editorial/letter/other non-research >
    journal article. Matching is case-insensitive, so it accepts both the
    Title Case strings from the bulk path and the lowercased ones from the
    weekly path."""
    if not pub_types:
        return 'Journal Article'
    if isinstance(pub_types, str):
        pub_types = [pub_types]

    present = {str(pt).strip().lower(): str(pt).strip() for pt in pub_types if pt}
    for group in (_REVIEW_TYPES, _GUIDELINE_TYPES, _NON_RESEARCH_TYPES):
        for canonical in group:
            if canonical.lower() in present:
                return canonical
    if 'journal article' in present:
        return 'Journal Article'
    # Unknown type: preserve the original spelling for the first entry.
    return next(iter(present.values()))


def _month_offset(year: int, month: int, offset: int) -> Tuple[int, int]:
    """Add offset months to a (year, month) pair."""
    total = (year * 12 + month - 1) + offset
    return total // 12, total % 12 + 1


def _month_to_date(year: int, month: int, day: int = 1) -> str:
    """Convert year/month to ISO date string."""
    return f"{year}-{month:02d}-{day:02d}"


def _end_of_month(year: int, month: int) -> str:
    """Last day of a given month as ISO date string."""
    if month == 12:
        return f"{year}-12-31"
    next_month = datetime(year, month + 1, 1) - timedelta(days=1)
    return next_month.strftime("%Y-%m-%d")


class ImpactCalculator:
    """Computes rolling impact factors and related metrics."""

    def __init__(self, db: DatabaseManager, window_months: int = 24):
        self.db = db
        self.window_months = window_months

    # ------------------------------------------------------------------ #
    #  Journal-level rolling IF
    # ------------------------------------------------------------------ #

    def compute_rolling_if(self, journal_id: int,
                           target_year: int,
                           target_month: int,
                           paper_window_months: int = 24,
                           paper_skip_months: int = 0) -> Dict:
        """
        Compute rolling citation rate for a journal at a specific month.

        Citation window: 12 months ending at target_month.

        Paper window: `paper_window_months` months ending `paper_skip_months`
        months before the citation window start.
          - Standard 24-mo:  window=24, skip=0  → papers 13-36 months before target
          - 12-mo:           window=12, skip=0  → papers 13-24 months before target
          - 5-yr yr2-6:      window=60, skip=12 → papers 25-84 months before target

        Returns dict with rolling_if, paper counts, citation counts, by_type.
        """
        # Citation counting window: 12 months ending at target
        cite_end_y, cite_end_m = target_year, target_month
        cite_start_y, cite_start_m = _month_offset(target_year, target_month, -11)

        cite_start_date = _month_to_date(cite_start_y, cite_start_m)
        cite_end_date = _end_of_month(cite_end_y, cite_end_m)

        # Paper publication window
        paper_end_y, paper_end_m = _month_offset(
            cite_start_y, cite_start_m, -(1 + paper_skip_months)
        )
        paper_start_y, paper_start_m = _month_offset(
            paper_end_y, paper_end_m, -(paper_window_months - 1)
        )

        paper_start_date = _month_to_date(paper_start_y, paper_start_m)
        paper_end_date = _end_of_month(paper_end_y, paper_end_m)

        # Get papers in the publication window
        papers = self.db.get_papers_in_window(journal_id, paper_start_date, paper_end_date)

        if not papers:
            return self._empty_snapshot(target_year, target_month)

        # One grouped query gives papers and citations per (doc_class, pub_type);
        # every total below is derived from it so they cannot disagree.
        raw_by_type = self.db.count_papers_and_citations_by_type(
            journal_id, paper_start_date, paper_end_date,
            cite_start_date, cite_end_date
        )
        warned = set()
        by_type = {cat: {"papers": 0, "citations": 0} for cat in ARTICLE_CATEGORIES}
        for row in raw_by_type:
            cat = self._known_category(row.get("doc_class"), row["pub_type"], journal_id, warned)
            by_type[cat]["papers"] += row["paper_count"]
            by_type[cat]["citations"] += row["citation_count"]

        n_all = sum(v["papers"] for v in by_type.values())
        total_citations = sum(v["citations"] for v in by_type.values())
        n_citable = sum(by_type[c]["papers"] for c in CITABLE)
        citable_citations = sum(by_type[c]["citations"] for c in CITABLE)
        n_research = by_type["research"]["papers"]
        research_citations = by_type["research"]["citations"]
        n_reviews = by_type["review"]["papers"]
        n_inferred = sum(1 for p in papers if p.get("class_source") == 'inferred')

        rolling_if = citable_citations / n_citable if n_citable > 0 else 0.0
        rolling_if_no_reviews = research_citations / n_research if n_research > 0 else 0.0

        # Actual papers published this month (not rolling window)
        raw_pub = self.db.count_papers_by_type_in_month(
            journal_id, target_year, target_month
        )
        pub_by_type = {}
        for row in raw_pub:
            cat = self._known_category(row.get("doc_class"), row["pub_type"], journal_id, warned)
            pub_by_type[cat] = pub_by_type.get(cat, 0) + row["paper_count"]

        return {
            "month": f"{target_year}-{target_month:02d}",
            "rolling_if": round(rolling_if, 3),
            "rolling_if_no_reviews": round(rolling_if_no_reviews, 3),
            "paper_count": n_all,
            "research_count": n_research,
            "review_count": n_reviews,
            "citation_count": total_citations,
            "research_citation_count": research_citations,
            "citable_papers": n_citable,
            "citable_citations": citable_citations,
            "inferred_papers": n_inferred,
            "by_type": by_type,
            "pub_by_type": pub_by_type,
            "paper_window": f"{paper_start_date} to {paper_end_date}",
            "citation_window": f"{cite_start_date} to {cite_end_date}",
        }

    @staticmethod
    def _known_category(doc_class, pub_type, journal_id, warned) -> str:
        """category_of, but a doc_class outside ARTICLE_CATEGORIES becomes 'other'
        (warned once per value per call) instead of breaking the timeseries."""
        cat = category_of(doc_class, pub_type)
        if cat not in ARTICLE_CATEGORIES:
            if cat not in warned:
                warned.add(cat)
                logger.warning("journal %s: unknown doc_class %r mapped to 'other'",
                               journal_id, cat)
            return 'other'
        return cat

    def compute_journal_timeseries(self, journal_id: int,
                                    start_year: int, start_month: int,
                                    end_year: int, end_month: int,
                                    paper_window_months: int = 24,
                                    paper_skip_months: int = 0) -> List[Dict]:
        """
        Compute rolling citation rate for every month in a range.
        Returns list of monthly snapshots.
        """
        timeseries = []
        y, m = start_year, start_month

        while (y, m) <= (end_year, end_month):
            snapshot = self.compute_rolling_if(
                journal_id, y, m, paper_window_months, paper_skip_months
            )
            timeseries.append(snapshot)
            y, m = _month_offset(y, m, 1)

        return timeseries

    def compute_all_window_timeseries(self, journal_id: int,
                                       start_year: int, start_month: int,
                                       end_year: int, end_month: int) -> Dict:
        """
        Compute timeseries for all three window variants and store the default
        (24-mo) to the DB.

        Returns dict:
            'default'  → 24-mo paper window (standard)
            '12mo'     → 12-mo paper window
            '5yr'      → 60-mo paper window skipping year 1 (years 2-6)
        """
        windows = [
            ("default", 24, 0),
            ("12mo",    12, 0),
            ("5yr",     60, 12),
        ]
        results = {}
        for key, window_months, skip_months in windows:
            logger.info(
                f"  Journal {journal_id}: computing {key} window "
                f"({window_months}-mo, skip={skip_months})..."
            )
            ts = self.compute_journal_timeseries(
                journal_id, start_year, start_month, end_year, end_month,
                paper_window_months=window_months,
                paper_skip_months=skip_months,
            )
            results[key] = ts

        # Store default (24-mo) snapshots to DB for reference
        for snap in results["default"]:
            self.db.save_snapshot(
                journal_id=journal_id,
                snapshot_month=snap["month"],
                rolling_if=snap["rolling_if"],
                rolling_if_no_reviews=snap["rolling_if_no_reviews"],
                paper_count=snap["paper_count"],
                citation_count=snap["citation_count"],
                review_count=snap["review_count"],
            )

        logger.info(
            f"Journal {journal_id}: stored {len(results['default'])} snapshots"
        )
        return results

    def compute_and_store_timeseries(self, journal_id: int,
                                      start_year: int, start_month: int,
                                      end_year: int, end_month: int):
        """Compute default (24-mo) timeseries and store snapshots to DB."""
        timeseries = self.compute_journal_timeseries(
            journal_id, start_year, start_month, end_year, end_month
        )

        for snap in timeseries:
            self.db.save_snapshot(
                journal_id=journal_id,
                snapshot_month=snap["month"],
                rolling_if=snap["rolling_if"],
                rolling_if_no_reviews=snap["rolling_if_no_reviews"],
                paper_count=snap["paper_count"],
                citation_count=snap["citation_count"],
                review_count=snap["review_count"],
            )

        logger.info(
            f"Journal {journal_id}: stored {len(timeseries)} monthly snapshots"
        )
        return timeseries

    # ------------------------------------------------------------------ #
    #  Author-level metrics
    # ------------------------------------------------------------------ #

    def compute_author_metrics(self, pmid_list: List[int]) -> Dict:
        """
        Compute metrics for an author given their list of PMIDs.
        Returns average citations per paper, total citations, per-paper breakdown.
        """
        papers_data = []
        total_cites = 0

        for pmid in pmid_list:
            paper = self.db.get_paper(pmid)
            if not paper:
                continue

            cite_count = self.db.get_citation_count_for_paper(pmid)
            total_cites += cite_count

            papers_data.append({
                "pmid": pmid,
                "title": paper["title"],
                "pub_date": paper["pub_date"],
                "pub_type": paper["pub_type"],
                "citations": cite_count,
            })

        n_papers = len(papers_data)
        avg_cites = total_cites / n_papers if n_papers > 0 else 0

        return {
            "paper_count": n_papers,
            "total_citations": total_cites,
            "avg_citations_per_paper": round(avg_cites, 2),
            "papers": sorted(papers_data, key=lambda x: -x["citations"]),
        }

    # ------------------------------------------------------------------ #
    #  Paper-level trajectory
    # ------------------------------------------------------------------ #

    def compute_paper_trajectory(self, pmid: int) -> Optional[Dict]:
        """
        Get month-by-month citation trajectory for a single paper.
        Returns dict with paper info and monthly citation counts.
        """
        paper = self.db.get_paper(pmid)
        if not paper:
            return None

        citations = self.db.get_citations_for_paper(pmid)

        # Aggregate by month
        monthly = {}
        for cite in citations:
            key = f"{cite['citing_year']}-{cite['citing_month']:02d}"
            monthly[key] = monthly.get(key, 0) + 1

        # Sort chronologically
        sorted_months = sorted(monthly.items())

        # Build cumulative
        cumulative = []
        running_total = 0
        for month_str, count in sorted_months:
            running_total += count
            cumulative.append({
                "month": month_str,
                "citations": count,
                "cumulative": running_total,
            })

        return {
            "pmid": pmid,
            "title": paper["title"],
            "pub_date": paper["pub_date"],
            "pub_type": paper["pub_type"],
            "total_citations": len(citations),
            "trajectory": cumulative,
        }

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _empty_snapshot(self, year: int, month: int) -> Dict:
        return {
            "month": f"{year}-{month:02d}",
            "rolling_if": 0.0,
            "rolling_if_no_reviews": 0.0,
            "paper_count": 0,
            "research_count": 0,
            "review_count": 0,
            "citation_count": 0,
            "research_citation_count": 0,
            "citable_papers": 0,
            "citable_citations": 0,
            "inferred_papers": 0,
            "paper_window": "",
            "citation_window": "",
        }
