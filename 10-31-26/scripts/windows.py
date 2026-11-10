"""Figure 10: would a JIF with the same window for every paper rank journals differently, and would it be better?

Three windows, all over the same citable items (ages72.npz from citation_ages_long.py; age 0 = publication month):

  jif       the calendar-year JIF: ages 13-m to 36-m for a paper published in month m
  first24   the first 24 months after publication: ages 0-23
  delayed   24 months after a 12-month wait: ages 12-35

A journal's rate for year Y is the window citations to its items from Y-2 and Y-1, per item (JIF years 2016-22).
The JIF and delayed windows differ in two ways: the JIF window depends on the month (the calendar effect, Fig 9)
and starts on average 6.5 months earlier (a speed effect: fields that cite late gain from a later window). The
month-neutral JIF (each paper credited with the mean of its twelve possible JIF windows, Fig 9B) separates them:
jif / neutral is the calendar effect, delayed / neutral the speed effect.

Tests:
  agreement    Spearman correlation of journal rates between windows, and how far journals move in percentile rank
  stability    Spearman correlation of a journal's rate for one publication-year cohort with the next cohort's
  prediction   Spearman correlation of a window's count with citations at ages 36-71 (years 4-6), which no window
               includes: per paper, and per journal (the same items, per item). Cohorts 2014-19, the last for which
               age 71 has been reached. The delayed window ends nearest the outcome, which helps it.
  forecast     what a reader at the end of year p-1 could know: each window's latest complete journal rate against
               the citations per item of the journal's next papers (published in p) in their first 36 months,
               p = 2019-21. A cohort's JIF and first-24-month windows are complete at the end of its second
               following year, the delayed window a year later, so the rates use items from p-4 and p-3 (JIF,
               first24) and p-5 and p-4 (delayed).

The site's own rate is also computed from the same papers: the reading at month t counts citations made in the
12 months to t to items published in months t-35 to t-12 (impact_calculator.py). Two journal metrics come from it,
for years 2017-22 (earlier readings need items from before 2014):

  december     the December reading of year Y: the JIF formula (citations in Y to items from Y-2 and Y-1)
  rolling      the mean of year Y's twelve monthly readings

These count citations made in one window of time rather than following each paper, so they are not over the same
papers as the cohort windows. They get the agreement, stability and forecast tests (a reader at the end of p-1 has
the readings of p-1).

June is left out: PubMed's parser assigns June to papers with no month. Citations made by errata, retraction notices
and expressions of concern are left out. So are journals for which impact.db holds under half of iCite's citations
(data/analysis/citation_coverage_sample.csv: 25 papers per journal from 2018-21 checked against iCite); since the
2026-11-02 reload there are none.

Usage: python 10-31-26/scripts/windows.py   (from the IMPACT folder)
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import BLUE, VERMILION, GREEN, PURPLE, GRAY, INK, MUTED, DATA, con, jid, pm, py, matplotlib, np, plt, save, write_csv  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

YEARS = range(2016, 2023)         # JIF years: items from Y-2 and Y-1
SNAP_YEARS = range(2017, 2023)    # years of monthly readings: January needs items from 36 months back
COHORTS = range(2014, 2022)
PREDICT = range(2014, 2020)       # outcome ages 36-71 complete
FORECAST = range(2019, 2022)      # needs cohorts from p-5
MIN_ITEMS = 100                   # per JIF year (two cohorts); for readings, items in the December reading
MIN_COHORT = 50                   # per cohort, for stability
WINDOWS = ["jif", "first24", "delayed"]
SNAPS = ["december", "rolling"]
LAG = {"jif": 3, "first24": 3, "delayed": 4}       # newest complete cohort at the end of p-1 is p - LAG
LABELS = {"jif": "Calendar JIF", "first24": "First 24 months", "delayed": "Months 12–35",
          "december": "December reading", "rolling": "12-month average"}
COLORS = {"jif": BLUE, "first24": GREEN, "delayed": VERMILION, "december": "#56B4E9", "rolling": PURPLE}
LABEL_A = {"HLA": (4, -7, "left"), "bioRxiv": (4, -7, "left"), "J Hum Reprod Sci": (-4, 3, "right"),
           "JSES Rev Rep Tech": (-4, 3, "right"), "Nature": (-4, 3, "right"), "Lancet": (-4, 3, "right"),
           "PLoS One": (-4, 3, "right")}
abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))

UNDERCOUNTED = {int(r["journal_id"]) for r in csv.DictReader(open(os.path.join(DATA, "citation_coverage_sample.csv")))
                if int(r["icite_cited_by"]) >= 50 and int(r["impact_db"]) < 0.5 * int(r["icite_cited_by"])}

A = np.load(os.path.join(DATA, "ages72.npz"))
row = A["row"]
keep = (pm[row] != 6) & ~np.isin(jid[row], list(UNDERCOUNTED))
row = row[keep]
counts = A["counts"][keep]
J, M, P = jid[row], pm[row].astype(int), py[row].astype(int)
cs = np.concatenate([np.zeros((len(row), 1), np.int64), np.cumsum(counts, axis=1, dtype=np.int64)], axis=1)
del counts
n = np.arange(len(row))
V = {"jif": cs[n, 37 - M] - cs[n, 13 - M],
     "first24": cs[:, 24] - cs[:, 0],
     "delayed": cs[:, 36] - cs[:, 12],
     "neutral": np.mean([cs[:, 37 - m] - cs[:, 13 - m] for m in range(1, 13)], axis=0),
     "outcome": cs[:, 72] - cs[:, 36],
     "first36": cs[:, 36]}
print(f"{len(row):,} papers", flush=True)

uj, jix = np.unique(J, return_inverse=True)

# the site's monthly readings: citations in months t-11..t to items from t-35..t-12, i.e. ages t-a-11..t-a
a_month = P * 12 + M - 1
READ_NUM, READ_ITEMS = {}, {}     # year -> (12, journals)
for Y in SNAP_YEARS:
    num, items = np.zeros((12, len(uj))), np.zeros((12, len(uj)))
    for k in range(12):
        d = Y * 12 + k - a_month
        i = np.flatnonzero((d >= 12) & (d <= 35))
        num[k] = np.bincount(jix[i], weights=cs[i, d[i] + 1] - cs[i, d[i] - 11], minlength=len(uj))
        items[k] = np.bincount(jix[i], minlength=len(uj))
    READ_NUM[Y], READ_ITEMS[Y] = num, items
del cs, a_month


def journal_sums(mask):
    """items and window sums per journal for the papers in mask"""
    items = np.bincount(jix[mask], minlength=len(uj))
    return items, {k: np.bincount(jix[mask], weights=v[mask], minlength=len(uj)) for k, v in V.items()}


def pct_rank(x):
    return (np.argsort(np.argsort(x)) + 0.5) / len(x) * 100


def readings(Y):
    """per journal: usable (enough items in December, items in every reading), December reading, 12-month average"""
    num, items = READ_NUM[Y], READ_ITEMS[Y]
    ok = (items[11] >= MIN_ITEMS) & (items > 0).all(axis=0)
    rate = np.divide(num, items, out=np.zeros_like(num), where=items > 0)
    return ok, {"december": rate[11], "rolling": rate.mean(axis=0)}


def main():
    rows, agree, moves = [], [], []
    by_year = {}
    for Y in YEARS:
        items, s = journal_sums((P == Y - 2) | (P == Y - 1))
        ok = items >= MIN_ITEMS
        r = {k: s[k][ok] / items[ok] for k in s}
        by_year[Y] = (uj[ok], items[ok], r)
        for a, b in [("jif", "first24"), ("jif", "delayed"), ("first24", "delayed")]:
            rho = spearmanr(r[a], r[b])[0]
            agree.append([Y, a, b, int(ok.sum()), round(rho, 4)])
        pr = {k: pct_rank(r[k]) for k in WINDOWS}
        for k in ("first24", "delayed"):
            d = np.abs(pr[k] - pr["jif"])
            moves.append([Y, k, int(ok.sum()), round(float(np.median(d)), 2), round(float((d > 10).mean()), 4),
                          round(float((d > 25).mean()), 4)])
    print("Agreement (Spearman with calendar JIF)")
    for a in agree:
        print("  ", a)
    print("Percentile-rank moves vs JIF [year, window, journals, median, >10 pts, >25 pts]")
    for m in moves:
        print("  ", m)

    # the site's readings: does the 12-month average rank journals differently from the December reading?
    snap_agree, snap_month, snap_stab = [], [], []
    for Y in SNAP_YEARS:
        ok, r = readings(Y)
        dec, roll = r["december"][ok], r["rolling"][ok]
        snap_agree.append([Y, "december", "rolling", int(ok.sum()), round(spearmanr(dec, roll)[0], 4)])
        d = np.abs(pct_rank(roll) - pct_rank(dec))
        moves.append([Y, "rolling", int(ok.sum()), round(float(np.median(d)), 2), round(float((d > 10).mean()), 4),
                      round(float((d > 25).mean()), 4)])
        pos = (dec > 0) & (roll > 0)
        snap_month.append([Y, int(pos.sum()), round(float(np.std(np.log(dec[pos] / roll[pos]))), 4),
                           round(float(np.median(dec[pos] / roll[pos])), 4)])
        size = READ_ITEMS[Y][11][ok]
        print(f"  {Y} sd of log(December / average) by items in the December reading: " + ", ".join(
            f"{lo}-{hi}: {np.std(np.log(dec[b] / roll[b])):.3f} (n={b.sum()})"
            for lo, hi in [(100, 300), (300, 1000), (1000, 10**6)]
            for b in [pos & (size >= lo) & (size < hi)]))
        if Y + 1 in SNAP_YEARS:
            ok1, r1 = readings(Y + 1)
            both = ok & ok1
            for k in SNAPS:
                snap_stab.append([Y, k, int(both.sum()), round(spearmanr(r[k][both], r1[k][both])[0], 4)])
    print("Site readings: December vs 12-month average [year, a, b, journals, Spearman]")
    for a in snap_agree:
        print("  ", a)
    print("  December vs average: [year, journals, sd of log ratio, median ratio]")
    for s in snap_month:
        print("  ", s)
    print("  Year to year [year, metric, journals, Spearman with next year] (consecutive readings share items)")
    for s in snap_stab:
        print("  ", s)

    # movers in the latest year, split into calendar and speed effects
    Y = YEARS[-1]
    js, items, r = by_year[Y]
    pos = (r["jif"] > 0) & (r["delayed"] > 0)
    js, items, r = js[pos], items[pos], {k: v[pos] for k, v in r.items()}
    ratio = r["delayed"] / r["jif"]
    cal = r["jif"] / r["neutral"]
    speed = r["delayed"] / r["neutral"]
    med = np.median(ratio)
    pr = {k: pct_rank(r[k]) for k in WINDOWS}
    mover_rows = [[int(j), abbr.get(int(j)) or "", int(i), round(float(r["jif"][k]), 3), round(float(r["delayed"][k]), 3),
                   round(float(r["first24"][k]), 3), round(float(ratio[k] / med), 4), round(float(cal[k]), 4),
                   round(float(speed[k] / np.median(speed)), 4), round(float(pr["delayed"][k] - pr["jif"][k]), 2)]
                  for k, (j, i) in enumerate(zip(js, items))]
    write_csv("fig10_journal_windows", ["journal_id", "journal", "items", f"jif_{Y}", f"delayed_{Y}", f"first24_{Y}",
                                        "delayed_vs_jif_rel_median", "calendar_effect_jif_vs_neutral",
                                        "speed_effect_rel_median", "pct_rank_change_delayed_vs_jif"], mover_rows)
    rel = ratio / med
    print(f"{Y}: {len(js):,} journals; delayed/JIF median {med:.3f}")
    print(f"  log(delayed/JIF rel median) explained by: calendar sd {np.std(np.log(cal)):.3f}, "
          f"speed sd {np.std(np.log(speed)):.3f}, total sd {np.std(np.log(rel)):.3f}")
    o = np.argsort(rel)
    for k in list(o[:8]) + list(o[-8:]):
        print(f"  {abbr.get(int(js[k])) or js[k]:40s} items {items[k]:5d} JIF {r['jif'][k]:6.2f} delayed "
              f"{r['delayed'][k]:6.2f} rel {rel[k]:.2f} calendar {cal[k]:.3f} speed {speed[k] / np.median(speed):.2f}")

    # stability: one cohort's rate vs the next cohort's
    stab = []
    for p in list(COHORTS)[:-1]:
        i0, s0 = journal_sums(P == p)
        i1, s1 = journal_sums(P == p + 1)
        ok = (i0 >= MIN_COHORT) & (i1 >= MIN_COHORT)
        for k in WINDOWS:
            a, b = s0[k][ok] / i0[ok], s1[k][ok] / i1[ok]
            good = (a > 0) & (b > 0)
            stab.append([p, k, int(ok.sum()), round(spearmanr(a, b)[0], 4),
                         round(float(np.median(np.abs(np.log(b[good] / a[good])))), 4)])
    print("Stability [cohort, window, journals, Spearman with next cohort, median |log change|]")
    for s in stab:
        print("  ", s)

    # prediction of citations at ages 36-71
    pred = []
    pm_ = (P >= PREDICT[0]) & (P <= PREDICT[-1])
    for k in WINDOWS:
        pred.append(["paper", k, int(pm_.sum()), round(spearmanr(V[k][pm_], V["outcome"][pm_])[0], 4)])
    for p in PREDICT:
        items, s = journal_sums(P == p)
        ok = items >= MIN_COHORT
        for k in WINDOWS:
            pred.append([f"journal {p}", k, int(ok.sum()),
                         round(spearmanr(s[k][ok] / items[ok], s["outcome"][ok] / items[ok])[0], 4)])
    # forecast: the latest rate each metric has at the end of p-1, against the journal's papers from p,
    # over the journals every metric covers
    for p in FORECAST:
        it, so = journal_sums(P == p)
        sums = {k: journal_sums((P == p - LAG[k]) | (P == p - LAG[k] - 1)) for k in WINDOWS}
        rok, rr = readings(p - 1)
        ok = (it >= MIN_COHORT) & np.all([sums[k][0] >= MIN_ITEMS for k in WINDOWS], axis=0) & rok
        rate = {k: sums[k][1][k] / np.maximum(sums[k][0], 1) for k in WINDOWS} | rr
        for k in WINDOWS + SNAPS:
            pred.append([f"forecast {p}", k, int(ok.sum()),
                         round(spearmanr(rate[k][ok], so["first36"][ok] / it[ok])[0], 4)])
    print("Prediction of ages 36-71 [level, window, n, Spearman]")
    for q in pred:
        print("  ", q)

    write_csv("fig10_window_tests", ["test", "year_or_level", "window", "other_window", "n", "value", "value2"],
              [["agreement", a[0], a[1], a[2], a[3], a[4], ""] for a in agree]
              + [["rank_move_median_pts", m[0], m[1], "december" if m[1] == "rolling" else "jif", m[2], m[3], m[4]]
                 for m in moves]
              + [["stability", s[0], s[1], "", s[2], s[3], s[4]] for s in stab]
              + [["prediction", q[0], q[1], "", q[2], q[3], ""] for q in pred]
              + [["agreement", a[0], a[1], a[2], a[3], a[4], ""] for a in snap_agree]
              + [["december_vs_rolling_sd_log", s[0], "december", "rolling", s[1], s[2], s[3]] for s in snap_month]
              + [["stability_readings", s[0], s[1], "", s[2], s[3], ""] for s in snap_stab])
    figure(agree, by_year, stab, pred)


def figure(agree, by_year, stab, pred):
    fig = plt.figure(figsize=(7.2, 8.8))
    gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.32, height_ratios=[1, 1, 0.55])
    Y = YEARS[-1]
    js, items, r = by_year[Y]
    pos = (r["jif"] > 0) & (r["delayed"] > 0)
    js, r = js[pos], {k: v[pos] for k, v in r.items()}

    # A: the two windows over the same items
    ax = fig.add_subplot(gs[0, 0])
    ax.scatter(r["jif"], r["delayed"], s=3, color=GRAY, alpha=0.35, linewidths=0)
    med = np.median(r["delayed"] / r["jif"])
    lim = np.array([0.03, 300])
    ax.plot(lim, lim * med, color=INK, linewidth=0.7, linestyle="--")
    for k, j in enumerate(js):
        a = abbr.get(int(j)) or ""
        if a in LABEL_A:
            ax.scatter(r["jif"][k], r["delayed"][k], s=10, color=VERMILION, linewidths=0)
            dx, dy, ha = LABEL_A[a]
            ax.annotate(a, (r["jif"][k], r["delayed"][k]), fontsize=5.5, xytext=(dx, dy), ha=ha,
                        textcoords="offset points", color=INK)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(*lim); ax.set_ylim(*lim)
    rho = [a[4] for a in agree if a[0] == Y and a[2] == "delayed" and a[1] == "jif"][0]
    ax.set_xlabel(f"Calendar JIF {Y} (citable items from {Y - 2}–{str(Y - 1)[2:]})")
    ax.set_ylabel("Months 12–35, same items")
    ax.text(0.04, 0.95, f"{len(js):,} journals\nSpearman ρ = {rho:.3f}\ndashed: median ratio {med:.2f}",
            transform=ax.transAxes, fontsize=6, va="top", color=MUTED)
    ax.set_title("A  Same papers, two windows", loc="left", fontsize=8.5)

    # B: what moves journals: publication months vs citation speed
    ax = fig.add_subplot(gs[0, 1])
    cal = np.log(r["jif"] / r["neutral"])
    sp = np.log(r["delayed"] / r["neutral"]); sp -= np.median(sp)
    bins = np.linspace(-0.4, 0.4, 61)
    for v, lab, c in [(cal, "Publication months\n(calendar JIF vs\nmonth-neutral)", BLUE),
                      (sp, "Citation speed\n(months 12–35 vs\nmonth-neutral)", VERMILION)]:
        ax.hist(np.clip(v, bins[0], bins[-1]), bins=bins, histtype="step", color=c, linewidth=1.4,
                label=f"{lab}, SD {np.std(v):.1%}")
    t = np.array([-0.3, -0.15, 0, 0.15, 0.3, 0.45])
    ax.set_xticks(np.log1p(t), [f"{x:+.0%}" if x else "0" for x in t])
    ax.set_xlabel("Effect on the journal's rate")
    ax.set_ylabel("Journals")
    ax.legend(fontsize=5.5, loc="upper right")
    ax.set_title("B  Why a journal moves between the two", loc="left", fontsize=8.5)

    # C: stability
    ax = fig.add_subplot(gs[1, 0])
    for k in WINDOWS:
        v = [(s[0], s[3]) for s in stab if s[1] == k]
        ax.plot([a for a, _ in v], [b for _, b in v], color=COLORS[k], marker="o", markersize=3, label=LABELS[k])
    ax.set_xlabel("Cohort (papers published that year) vs the next cohort")
    ax.set_ylabel("Spearman ρ, journal rate")
    ax.legend(fontsize=6, loc="lower left")
    ax.set_title("C  Year-to-year stability", loc="left", fontsize=8.5)

    # D: prediction
    ax = fig.add_subplot(gs[1, 1])
    groups = [("Same papers,\nyears 4–6,\nper paper", lambda q: q[0] == "paper"),
              ("Same papers,\nyears 4–6,\nper journal", lambda q: q[0].startswith("journal"))]
    for g, (lab, f) in enumerate(groups):
        for w, k in enumerate(WINDOWS):
            v = np.mean([q[3] for q in pred if f(q) and q[1] == k])
            x = g + (w - 1) * 0.22
            ax.scatter(x, v, s=24, color=COLORS[k], linewidths=0, zorder=3, label=LABELS[k] if g == 0 else None)
            ax.annotate(f"{v:.3f}", (x, v), fontsize=5.3, xytext=(0, 5), textcoords="offset points", ha="center",
                        va="bottom", color=MUTED)
    ax.set_xticks(range(len(groups)), [g for g, _ in groups], fontsize=6)
    ax.set_xlim(-0.5, len(groups) - 0.5); ax.set_ylim(0.7, 1.0)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Spearman ρ with citations in years 4–6")
    ax.legend(fontsize=5.5, loc="lower right")
    ax.set_title("D  Which window predicts the same papers' later citations", loc="left", fontsize=8.5)

    # E: forecast from what was available at the time
    ax = fig.add_subplot(gs[2, :])
    ks = WINDOWS + SNAPS
    names = {"jif": "Calendar JIF window, per paper", "first24": "First 24 months, per paper",
             "delayed": "Months 12–35, per paper", "december": "Site, December reading (the JIF formula)",
             "rolling": "Site, average of the year's 12 monthly readings"}
    for y, k in enumerate(ks[::-1]):
        v = [q[3] for q in pred if q[0].startswith("forecast") and q[1] == k]
        ax.plot([min(v), max(v)], [y, y], color=COLORS[k], linewidth=1, alpha=0.5)
        ax.scatter(np.mean(v), y, s=24, color=COLORS[k], linewidths=0, zorder=3)
        ax.annotate(f"{np.mean(v):.3f}", (max(v), y), fontsize=5.3, xytext=(4, 0), textcoords="offset points",
                    va="center", color=MUTED)
    ax.set_yticks(range(len(ks)), [names[k] for k in ks[::-1]], fontsize=6.5)
    ax.set_xlim(0.86, 0.96); ax.set_ylim(-0.6, len(ks) - 0.4)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Spearman ρ with the citations per item of the journal's next year of papers in their first "
                  "36 months (dot: mean of 2019–21; line: range)")
    ax.set_title("E  Forecast from the data available at the end of the year before", loc="left", fontsize=8.5)
    save(fig, "fig10_jif_windows")


if __name__ == "__main__":
    main()
