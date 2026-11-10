"""Why do paper-mill, fake-peer-review and computer-generated papers get more citations than their controls in the
year they are retracted (Fig 7M)? Two checks:

1. Retraction month: if these retractions come late in the year, most of "the year retracted" is before retraction.
   Citations are counted by month relative to the retraction month instead of by calendar year.
2. Retraction Watch's referencing reason ("Concerns/Issues about Referencing/Attributions", the closest it has to
   citation manipulation): are the papers with it the ones with the excess?

Same papers and prior-matched controls as Fig 7M. Writes data/retraction_month_check.csv and
data/retraction_month_profile.csv.

Usage: python 10-31-26/scripts/retraction_year_check.py   (from the IMPACT folder)
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import more_figures as mf  # noqa: E402
import publishers_retractions as pr  # noqa: E402
from make_figures import C, Y0, con, np, pmid, py, write_csv  # noqa: E402

LAST = 2024
REFERENCING = "Concerns/Issues about Referencing/Attributions"
MASS = ["paper_mill", "peer_review", "generated_content"]


def monthly(p, lo, hi):
    """Citations to pmid p by absolute month (year * 12 + month - 1), for months lo..hi."""
    out = np.zeros(hi - lo + 1, np.int64)
    for y, m, n in con.execute("SELECT citing_year, citing_month, COUNT(*) FROM citations INDEXED BY idx_citations_cited "
                               "WHERE cited_pmid = ? AND citing_month >= 1 AND citing_class IS NULL GROUP BY citing_year, citing_month", (int(p),)):
        k = y * 12 + m - 1 - lo
        if 0 <= k < len(out):
            out[k] += n
    return out


def main():
    rows_r, ry, fl, src = mf.retracted_rows(2022, LAST)
    later = ry > py[rows_r]
    rows_r, ry, fl, src = rows_r[later], ry[later], fl[later], src[later]
    ctrl, _ = mf.prior_matched_controls(rows_r, ry)
    keep = np.array([i in ctrl for i in rows_r])
    rows_r, ry, fl, src = rows_r[keep], ry[keep], fl[keep], src[keep]
    month_of = dict(zip(mf.R["pmid"].tolist(), mf.R["notice_month"].tolist()))
    rm = np.array([month_of[int(pmid[i])] for i in rows_r])

    rw = pr.retraction_watch()
    doi = dict(con.execute(f"SELECT pmid, lower(doi) FROM papers WHERE pmid IN ({','.join(str(int(pmid[i])) for i in rows_r)})"))
    reason = [(rw.get(int(pmid[i])) or rw.get(doi.get(int(pmid[i])) or "") or (0, 0, ""))[2] for i in rows_r]
    ref = np.array([REFERENCING in r for r in reason])

    names = list(mf.R["reason_names"])
    mass = fl[:, [names.index(n) for n in MASS]].any(axis=1)
    groups = {"mass (paper mill, peer review, generated)": mass, "other reasons": (src == 1) & ~mass}

    print("Retraction month (share in each quarter)")
    for g, m in groups.items():
        q = np.bincount((rm[m] - 1) // 3, minlength=4) / m.sum()
        print(f"  {g:44s} n={m.sum():,}  Q1 {q[0]:.0%}  Q2 {q[1]:.0%}  Q3 {q[2]:.0%}  Q4 {q[3]:.0%}  "
              f"median month {np.median(rm[m]):.0f}")
    print(f"Referencing reason: {ref[mass].mean():.0%} of mass retractions, {ref[groups['other reasons']].mean():.0%} "
          "of others")

    # citations by month relative to the retraction month, retracted vs the mean of its controls
    W = 12
    t0 = ry * 12 + rm - 1
    ok = t0 + W - 1 <= LAST * 12 + 11                    # full year after retraction observed
    prof_r = np.zeros((len(rows_r), 2 * W))
    prof_c = np.zeros((len(rows_r), 2 * W))
    for k in np.flatnonzero(ok):
        lo, hi = t0[k] - W, t0[k] + W - 1
        prof_r[k] = monthly(pmid[rows_r[k]], lo, hi)
        prof_c[k] = np.mean([monthly(pmid[c], lo, hi) for c in ctrl[rows_r[k]]], axis=0)
        if k % 2000 == 0:
            print(f"  {k:,} papers", flush=True)

    sets = collections.OrderedDict()
    for g, m in groups.items():
        sets[g] = m
    sets["mass, with referencing reason"] = mass & ref
    sets["mass, without referencing reason"] = mass & ~ref
    for cat in MASS:
        sets[cat] = fl[:, names.index(cat)]
    yr0 = lambda i: C[rows_r[i], ry[i] - Y0]                                       # noqa: E731
    yr0c = lambda i: np.mean(C[ctrl[rows_r[i]], ry[i] - Y0])                       # noqa: E731
    out = []
    print("\nRetracted ÷ controls")
    print(f"  {'':44s} {'n':>6s} {'cal. year':>9s} {'12 mo before':>12s} {'12 mo after':>11s} {'1-3 mo before':>13s}")
    for g, m in sets.items():
        m = m & ok
        if m.sum() < 30:
            continue
        cy = np.mean([yr0(i) for i in np.flatnonzero(m)]) / np.mean([yr0c(i) for i in np.flatnonzero(m)])
        before = prof_r[m, :W].sum() / prof_c[m, :W].sum()
        after = prof_r[m, W:].sum() / prof_c[m, W:].sum()
        last3 = prof_r[m, W - 3:W].sum() / prof_c[m, W - 3:W].sum()
        print(f"  {g:44s} {m.sum():6,d} {cy:9.2f} {before:12.2f} {after:11.2f} {last3:13.2f}")
        out.append([g, int(m.sum()), round(cy, 3), round(before, 3), round(after, 3), round(last3, 3)])
    write_csv("retraction_month_check", ["group", "papers", "ratio_calendar_year_retracted", "ratio_12mo_before",
                                         "ratio_12mo_after", "ratio_3mo_before"], out)
    prof = []
    for g, m in sets.items():
        m = m & ok
        if m.sum() >= 30:
            prof += [[g, int(t - W), round(float(prof_r[m, t].mean()), 4), round(float(prof_c[m, t].mean()), 4)]
                     for t in range(2 * W)]
    write_csv("retraction_month_profile", ["group", "months_from_retraction", "retracted_mean", "controls_mean"], prof)


if __name__ == "__main__":
    main()
