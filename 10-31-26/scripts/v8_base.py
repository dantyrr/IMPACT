"""Shared set-up for v8: publishers grouped by owner, and the NCBI series with all 24 editions.

Import this before any older figure script. It fixes the output folder and patches, in memory, the two things v8 changes, so the older scripts and their outputs stay as they were.
"""
import os
import sys

os.environ["FIG_DIR"] = "v8"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v2_common  # noqa: E402,F401  first import fixes V2 at v8, whatever older scripts set later
import make_figures as MF  # noqa: E402

NCBI_LABEL = "Database resources of the National Center for…"
NCBI_2003 = 12519941              # titled without "Information", so it never joined the series
MF.SERIES_GROUPS.append(("nucleic-acids-research", "database resources of the national center for biotechnology", NCBI_LABEL))
_membership = MF.series_membership


def series_membership():
    """As before, with the 2003 edition joined to the series. The 'in 2023' titles join through SERIES_GROUPS."""
    sid, keys = _membership()
    sid = sid.copy()
    home = next(i for i, (_, t) in enumerate(keys) if t == "database resources of the national center for biotechnology information")
    sid[MF.pmid == NCBI_2003] = home
    return sid, keys


MF.series_membership = series_membership

import more_figures as M  # noqa: E402
import v7_stacks as S  # noqa: E402

# Publisher totals go by owner. Cell Press and Nature Portfolio keep their own stacks, where the family is the point.
OWNERS = {"Elsevier": ("Elsevier", "Cell Press"), "Springer Nature": ("Springer, BMC, Cureus", "Nature Portfolio"), "Wiley": ("Wiley, Hindawi",)}
OWNERS.update({n: (n,) for n in ("MDPI", "Frontiers", "PLOS", "AAAS", "Wolters Kluwer", "Taylor & Francis", "Oxford UP", "SAGE", "ACS", "RSC", "BMJ", "Other")})
_is_pub = M.is_pub


def owner(name):
    m = S.in_group(OWNERS[name][0])
    for g in OWNERS[name][1:]:
        m = m | S.in_group(g)
    return m


def is_pub(name):
    return owner(name) if name in OWNERS else _is_pub(name)


M.is_pub = is_pub
