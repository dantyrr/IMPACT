"""Journal reliability flags and delta encoding for per-journal PMID class files."""

from datetime import date
from typing import Dict, List, Optional

SMALL_RESEARCH_MIN = 20     # fewer research items than this -> small_research_sample
SMALL_REVIEW_MIN = 15       # 1 to this-1 review items -> small_review_sample (none: no review rate to flag)
REVIEW_JOURNAL_SHARE = 0.5  # reviews / citable items at or above this -> review_journal
INFERRED_SHARE = 0.10       # inferred / items at or above this -> inferred_types
SETTLE_MONTHS = 12          # citation window must have ended at least this long ago


def settled_point(timeseries: List[Dict], as_of: date) -> Optional[Dict]:
    """Latest point whose month ("YYYY-MM") is <= export month minus 12 months."""
    idx = as_of.year * 12 + (as_of.month - 1) - SETTLE_MONTHS
    cutoff = f"{idx // 12:04d}-{idx % 12 + 1:02d}"
    ok = [p for p in timeseries if p["month"] <= cutoff]
    return max(ok, key=lambda p: p["month"]) if ok else None


def compute_flags(point: Dict) -> List[str]:
    by_type = point.get("by_type") or {}
    research = (by_type.get("research") or {}).get("papers", 0)
    reviews = (by_type.get("review") or {}).get("papers", 0)
    citable = point.get("citable_papers", 0)
    papers = point.get("papers", 0)
    inferred = point.get("inferred_papers", 0)

    flags = []
    if research < SMALL_RESEARCH_MIN:
        flags.append("small_research_sample")
    if 0 < reviews < SMALL_REVIEW_MIN:
        flags.append("small_review_sample")
    if citable and reviews / citable >= REVIEW_JOURNAL_SHARE:
        flags.append("review_journal")
    if papers and inferred / papers >= INFERRED_SHARE:
        flags.append("inferred_types")
    return flags


def flags_for_timeseries(timeseries: List[Dict], as_of: date) -> List[str]:
    """Flags for exported-format timeseries points; [] if none has settled."""
    point = settled_point(timeseries, as_of)
    return compute_flags(point) if point else []


def encode_deltas(values: List[int]) -> List[int]:
    """Sort ascending, then first value absolute followed by successive differences."""
    vals = sorted(values)
    return [v - (vals[i - 1] if i else 0) for i, v in enumerate(vals)]


def decode_deltas(deltas: List[int]) -> List[int]:
    out, total = [], 0
    for d in deltas:
        total += d
        out.append(total)
    return out
