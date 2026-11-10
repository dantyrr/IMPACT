"""What a journal's rates would be if some of its papers had come out k months later (figure_revision_plan.md, Task 3).

A moved paper keeps its age pattern of citations: the paper and every citation to it move by the same k months.
Citations stay counted even if they move past the end of the data, so the total never changes; readings after the
data ends are simply not reported.

Rates are for citable items, as on the site:
  rolling[t]  citations in months t-11..t to items published t-35..t-12, per item
  jif[Y]      citations in year Y to items published in Y-2 and Y-1, per item
"""
import sqlite3
from collections import namedtuple

import numpy as np

from v2_common import ROOT, month_index

Journal = namedtuple("Journal", "items cited when")   # {pmid: publication month index}, citation arrays
CITABLE_SQL = "('research','review','case_report','guideline')"
START = month_index(1990, 1)
SIZE = 12 * 45
FIRST, LAST = month_index(2005, 1), month_index(2025, 11)
_con = None


def con():
    global _con
    if _con is None:
        _con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    return _con


def journal_id(slug):
    return con().execute("SELECT id FROM journals WHERE slug = ?", (slug,)).fetchone()[0]


def load_journal(j):
    items = {}
    for p, d in con().execute(f"SELECT pmid, pub_date FROM papers WHERE journal_id = ? AND doc_class IN {CITABLE_SQL} "
                              "AND pub_date IS NOT NULL", (j,)):
        items[p] = month_index(int(d[:4]), int(d[5:7]))
    rows = con().execute("SELECT c.cited_pmid, c.citing_year * 12 + c.citing_month - 1 FROM citations c JOIN papers q ON q.pmid = c.cited_pmid "
                         f"WHERE q.journal_id = ? AND q.doc_class IN {CITABLE_SQL} AND c.citing_class IS NULL AND c.citing_month IS NOT NULL", (j,)).fetchall()
    a = np.array(rows, dtype=np.int64).reshape(-1, 2)
    return Journal(items, a[:, 0], a[:, 1])


def shifted_rates(journal, pmids, months):
    """Returns {"rolling": {month index: rate}, "jif": {year: rate}, "total_citations": n} with pmids moved months later."""
    moved = set(int(p) for p in pmids)
    pub = {p: m + (months if p in moved else 0) for p, m in journal.items.items()}
    items = np.zeros(SIZE, np.int64)
    for m in pub.values():
        items[m - START] += 1
    keys = np.array(sorted(pub), np.int64)
    vals = np.array([pub[k] for k in keys], np.int64)
    pos = np.minimum(np.searchsorted(keys, journal.cited), len(keys) - 1)
    keep = keys[pos] == journal.cited
    cited, when, p = journal.cited[keep], journal.when[keep], vals[pos[keep]] - START
    is_moved = np.isin(cited, np.array(sorted(moved), np.int64)) if moved else np.zeros(len(cited), bool)
    w = when + np.where(is_moved, months, 0) - START
    M = np.zeros((SIZE, SIZE), np.int64)
    np.add.at(M, (p, w), 1)
    rolling = {}
    for t in range(FIRST, LAST + 1):
        i = t - START
        n = items[i - 35:i - 11].sum()
        rolling[t] = M[i - 35:i - 11, i - 11:i + 1].sum() / n if n else float("nan")
    jif = {}
    for Y in range(2005, 2026):
        a = month_index(Y - 2, 1) - START
        b = month_index(Y, 1) - START
        n = items[a:b].sum()
        jif[Y] = M[a:b, b:b + 12].sum() / n if n else float("nan")
    return {"rolling": rolling, "jif": jif, "total_citations": int(M.sum())}
