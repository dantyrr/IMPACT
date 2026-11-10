"""F3: would another window be better? Replaces Fig 10 (figure_revision_plan.md, Task 5).

Uses the arrays windows.py builds on import. A-D as in Fig 10, without its panel E, plus a key to the measures.
Panel C also shows each window with COVID papers left out, to test why the 2019 comparison dips.

Usage: python 10-31-26/scripts/v2_f3.py   (from the IMPACT folder)
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import windows as W  # noqa: E402
from make_figures import BLUE, VERMILION, GRAY, INK, MUTED, con, np, plt, pmid  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from v2_common import ROOT, place_labels, save, write_csv  # noqa: E402
from v2_panels import REFERENCE  # noqa: E402

LABELS = {**W.LABELS, "jif": "JIF-style (calendar years)"}
COVID_SQL = ("SELECT pmid FROM papers WHERE pub_year BETWEEN 2019 AND 2022 AND (title LIKE '%covid%' OR title LIKE '%sars-cov-2%' "
             "OR title LIKE '%coronavirus%' OR title LIKE '%pandemic%' OR title LIKE '%2019-ncov%')")


def stability(mask=None):
    out = []
    for p in list(W.COHORTS)[:-1]:
        m0, m1 = W.P == p, W.P == p + 1
        if mask is not None:
            m0, m1 = m0 & mask, m1 & mask
        i0, s0 = W.journal_sums(m0)
        i1, s1 = W.journal_sums(m1)
        ok = (i0 >= W.MIN_COHORT) & (i1 >= W.MIN_COHORT)
        for k in W.WINDOWS:
            out.append([p, k, int(ok.sum()), round(spearmanr(s0[k][ok] / i0[ok], s1[k][ok] / i1[ok])[0], 4)])
    return out


def main():
    covid = np.array([r[0] for r in con.execute(COVID_SQL)], np.int64)
    not_covid = ~np.isin(pmid[W.row], covid)
    print(f"{len(covid):,} COVID papers by title, {(~not_covid).sum():,} of them citable items in the window data", flush=True)
    every, clean = stability(), stability(not_covid)
    write_csv("f3c_stability", ["cohort", "window", "journals", "spearman_all_papers", "spearman_without_covid_papers"],
              [[a[0], a[1], a[2], a[3], b[3]] for a, b in zip(every, clean)])
    tests = list(csv.DictReader(open(os.path.join(ROOT, "10-31-26", "data", "fig10_window_tests.csv"))))

    fig = plt.figure(figsize=(7.2, 8.2))
    gs = fig.add_gridspec(3, 2, hspace=0.42, wspace=0.32, height_ratios=[1, 1, 0.36])
    Y = W.YEARS[-1]
    items, s = W.journal_sums((W.P == Y - 2) | (W.P == Y - 1))
    ok = items >= W.MIN_ITEMS
    js, n = W.uj[ok], items[ok]
    r = {k: s[k][ok] / n for k in s}
    pos = (r["jif"] > 0) & (r["delayed"] > 0)
    js, n, r = js[pos], n[pos], {k: v[pos] for k, v in r.items()}

    # A
    ax = fig.add_subplot(gs[0, 0])
    ax.scatter(r["jif"], r["delayed"], s=3, color=GRAY, alpha=0.35, linewidths=0)
    med = np.median(r["delayed"] / r["jif"])
    lim = np.array([0.1, 300])
    ax.plot(lim, lim * med, color=INK, linewidth=0.7, linestyle=(0, (3.5, 2.5)))
    rel = np.log(r["delayed"] / r["jif"] / med)
    big = np.flatnonzero(n >= 500)
    o = big[np.argsort(rel[big])]
    picks = [(k, "low") for k in o[:3]] + [(k, "high") for k in o[-3:]]
    ref = [k for k, j in enumerate(js) if W.abbr.get(int(j)) in REFERENCE]
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(*lim); ax.set_ylim(*lim)
    ax.scatter(r["jif"][[k for k, _ in picks]], r["delayed"][[k for k, _ in picks]], s=11, color=VERMILION, linewidths=0, zorder=3, label="Largest differences (500+ items)")
    ax.scatter(r["jif"][ref], r["delayed"][ref], s=11, color=BLUE, linewidths=0, zorder=3, label="Reference journals")
    keep_clear = [(a_, b_) for a_ in (0.13, 0.2, 0.3, 0.5, 0.8) for b_ in (70, 110, 170, 250)] + [(a_, b_) for a_ in (12, 20, 35, 60, 100, 170, 250) for b_ in (0.12, 0.16, 0.22)]
    place_labels(ax, [(r["jif"][k], r["delayed"][k], W.abbr[int(js[k])]) for k in [k for k, _ in picks] + ref], fontsize=5.6, avoid=keep_clear)
    write_csv("f3a_windows", ["journal", "items", "jif_style", "months_12_35", "ratio_vs_median", "why_marked"],
              [[W.abbr[int(js[k])], int(n[k]), round(r["jif"][k], 3), round(r["delayed"][k], 3), round(float(np.exp(rel[k])), 3), why]
               for k, why in [(k, "largest gap, 500+ items") for k, _ in picks] + [(k, "reference") for k in ref]])
    rho = next(float(t["value"]) for t in tests if t["test"] == "agreement" and t["year_or_level"] == str(Y) and t["window"] == "jif" and t["other_window"] == "delayed")
    ax.set_xlabel(f"JIF-style rate {Y} (citable items from {Y - 2}–{str(Y - 1)[2:]})")
    ax.set_ylabel("Months 12–35, same items")
    ax.text(0.04, 0.95, f"{len(js):,} journals\nSpearman ρ = {rho:.3f}\ndashed: median ratio {med:.2f}", transform=ax.transAxes, fontsize=6, va="top", color=MUTED)
    ax.legend(fontsize=5.8, loc="lower right")
    ax.set_title("A  JIF-style rate and citations at months 12–35", loc="left", fontsize=8.5)

    # B
    ax = fig.add_subplot(gs[0, 1])
    cal = np.log(r["jif"] / r["neutral"])
    sp = np.log(r["delayed"] / r["neutral"]); sp -= np.median(sp)
    bins = np.linspace(-0.4, 0.4, 61)
    for v, lab, c in ((cal, "Which months a journal publishes in", BLUE), (sp, "How fast its papers get cited", VERMILION)):
        ax.hist(np.clip(v, bins[0], bins[-1]), bins=bins, histtype="step", color=c, linewidth=1.4, label=f"{lab} (SD {np.std(v):.1%})")
    t = np.array([-0.3, -0.15, 0, 0.15, 0.3])
    ax.set_xticks(np.log1p(t), [f"{x:+.0%}".replace("-", "−") if x else "0%" for x in t])
    ax.set_xlabel("Effect on the journal's rate")
    ax.set_ylabel("Journals")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.22)
    ax.legend(fontsize=5.8, loc="upper center", handlelength=1.4)
    ax.set_title("B  Sources of the differences between windows in A", loc="left", fontsize=8.5)

    # C
    ax = fig.add_subplot(gs[1, 0])
    for k in W.WINDOWS:
        ax.plot([a[0] for a in every if a[1] == k], [a[3] for a in every if a[1] == k], color=W.COLORS[k], marker="o", markersize=3, linewidth=1.5, label=LABELS[k])
        ax.plot([a[0] for a in clean if a[1] == k], [a[3] for a in clean if a[1] == k], color=W.COLORS[k], linewidth=0.9, linestyle=(0, (3, 2)))
    ax.plot([], [], color=MUTED, linewidth=0.9, linestyle=(0, (3, 2)), label="Dashed: COVID papers left out")
    ax.set_ylim(0, 1)
    ax.set_xlabel("Each year's papers vs the next year's")
    ax.set_ylabel("Spearman ρ between journals' rates")
    ax.text(0.97, 0.6, "2019 dip: COVID papers,\nwhich only 2020 has", transform=ax.transAxes, ha="right", fontsize=6, color=INK)
    ax.legend(fontsize=5.8, loc="lower left")
    ax.set_title("C  Year-to-year consistency of journal rates", loc="left", fontsize=8.5)

    # D
    ax = fig.add_subplot(gs[1, 1])
    pred = [t for t in tests if t["test"] == "prediction"]
    groups = [("Per paper", lambda q: q["year_or_level"] == "paper"), ("Per journal", lambda q: q["year_or_level"].startswith("journal"))]
    rows = []
    for g, (lab, f) in enumerate(groups):
        for w, k in enumerate(W.WINDOWS):
            v = float(np.mean([float(q["value"]) for q in pred if f(q) and q["window"] == k]))
            x = g + (w - 1) * 0.22
            ax.scatter(x, v, s=24, color=W.COLORS[k], linewidths=0, zorder=3, label=LABELS[k] if g == 0 else None)
            ax.annotate(f"{v:.3f}", (x, v), fontsize=5.3, xytext=(0, 5), textcoords="offset points", ha="center", va="bottom", color=MUTED)
            rows.append([lab, k, round(v, 4)])
    write_csv("f3d_prediction", ["level", "window", "mean_spearman"], rows)
    ax.set_xticks(range(2), [g for g, _ in groups], fontsize=6.5)
    ax.set_xlim(-0.5, 1.5); ax.set_ylim(0.7, 1.0)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Spearman ρ with citations in years 4–6")
    ax.legend(fontsize=5.5, loc="lower right")
    ax.set_title("D  Correlation of each window with later citations", loc="left", fontsize=8.5)

    # key
    ax = fig.add_subplot(gs[2, :])
    ax.axis("off")
    key = [("Clarivate JIF", "the commercial metric. Web of Science citations, not used here."),
           ("JIF-style rate", "the JIF formula with PubMed citations: citations in one calendar year to citable items from the two years before."),
           ("First 24 months", "each paper's citations in the 24 months from publication, the same for every paper."),
           ("Months 12–35", "the same length of window after a 12-month wait."),
           ("IMPACT 24-month rate", "the JIF formula read every month: citations in the last 12 months to items from the 24 months before those.")]
    for i, (a, b) in enumerate(key):
        y = 0.98 - i * 0.2
        ax.text(0, y, a, fontsize=6.6, fontweight="bold", color=INK, va="top", transform=ax.transAxes)
        ax.text(0.2, y, b, fontsize=6.6, color=INK, va="top", transform=ax.transAxes)
    save(fig, "F3_windows")


if __name__ == "__main__":
    main()
