"""Month rotation for F2 D. Moving every item later in calendar time only slides a journal along its own trend, so this
keeps each paper in its publication year and rotates its month, leaving its citations by age unchanged.

A paper published in month m has its citations counted by a JIF at ages 13-m to 36-m (age 0 = publication month)."""
import numpy as np


def jif_counted(cum, months):
    """cum: (papers, 37) cumulative citations by age, with a leading zero. months: 1-12. Citations a JIF counts."""
    n = np.arange(len(months))
    return cum[n, 37 - months] - cum[n, 13 - months]


def rotated_change(counts, months, k):
    """Change in JIF-counted citations if each paper's month moves k later, wrapping within its year."""
    cum = np.concatenate([np.zeros((len(counts), 1), np.int64), np.cumsum(counts[:, :36], axis=1, dtype=np.int64)], axis=1)
    before = jif_counted(cum, months).sum()
    after = jif_counted(cum, (months - 1 + k) % 12 + 1).sum()
    return float(after / before - 1) if before else float("nan")
