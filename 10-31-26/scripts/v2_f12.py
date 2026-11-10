"""F12: retractions (figure_revision_plan.md, Task 12). Replaces Fig 7, 7C ranked, 7K and 7L.

A, B   retracted papers by year published and by year retracted (counts, so bars)
C      retraction rate by publisher, every publisher with 20,000+ items
D      journals with the most retractions
E      Fig 7K with spread: mean, 95% CI and middle half of papers, by years from retraction
F      Fig 7L, by year since publication to year 12; points with fewer than 100 papers are not drawn
The late-retraction numbers (citations before, and after against controls) stay in f12fg_late_retraction.csv, without a panel

Usage: python 10-31-26/scripts/v2_f12.py   (from the IMPACT folder)
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import more_figures as M  # noqa: E402
from make_figures import BLUE, VERMILION, GRAY, INK, MUTED, C, Y0, matplotlib, np, plt, py  # noqa: E402
from v2_common import ROOT, save, write_csv  # noqa: E402

LAST = 2024
OLD = os.path.join(ROOT, "10-31-26", "data")
MIN_PAPERS = 100
CONTROL = "Matched controls (same journal, year, type and citations before retraction)"


def read(name):
    with open(os.path.join(OLD, name)) as f:
        return list(csv.DictReader(f))


def cites(i, Y):
    return float(C[i, Y - Y0]) if py[i] <= Y <= LAST else np.nan


def stats(v):
    v = np.asarray(v, float)
    v = v[~np.isnan(v)]
    return v.mean(), 1.96 * v.std() / np.sqrt(max(len(v), 1)), np.percentile(v, 25), np.percentile(v, 75), len(v)


def panels_ab(fig, gs, T):
    for k, (panel, title) in enumerate((("A", "A  Retracted papers, by year published"), ("B", "B  Retracted papers, by year retracted*"))):
        ax = fig.add_subplot(gs[k])
        r = [x for x in T if x["panel"] == panel]
        y = [int(x["year"]) for x in r]
        a = np.array([float(x["a"]) for x in r])
        b = np.array([float(x["b"]) for x in r])
        ax.bar(y, a, color=GRAY, width=0.8, label="Other publishers")
        ax.bar(y, b, bottom=a, color=VERMILION, width=0.8, label="Hindawi")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.grid(axis="x", visible=False)
        ax.set_title(title, loc="left", fontsize=8.5)
        ax.set_xlabel("Year")
        if k == 0:
            ax.set_ylabel("Papers")
            ax.legend(fontsize=6.5, loc="upper left")


def panel_c(ax):
    r = sorted(read("fig7c_ranked.csv"), key=lambda x: float(x["per_10000"]))
    v = [float(x["per_10000"]) for x in r]
    yy = np.arange(len(r))
    ax.hlines(yy, 0, v, color="#BBBBBB", linewidth=0.9)
    ax.scatter(v, yy, s=14, color=[VERMILION if x["publisher"] == "Hindawi" else BLUE for x in r], zorder=3, edgecolor="white", linewidth=0.3)
    for y, a in zip(yy, v):
        ax.text(a + 12, y, f"{a:.0f}", va="center", fontsize=5.6, color=INK)
    ax.set_yticks(yy, [x["publisher"] for x in r], fontsize=5.8)
    ax.set_xlim(0, 720)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Retracted per 10,000 citable items, 2015–23")
    ax.set_title("C  Rate by publisher (20,000+ items)", loc="left", fontsize=8.5, x=-0.28)


def panel_d(ax, T):
    r = [x for x in T if x["panel"] == "D"]
    r = r[::-1] if float(r[0]["a"]) > float(r[-1]["a"]) else r
    yy = np.arange(len(r))
    v = [float(x["a"]) for x in r]
    ax.hlines(yy, 0, v, color="#BBBBBB", linewidth=0.9)
    names = [x["series"] for x in r]
    hidx = {M.jname[int(j)] for j in np.unique(M.jid[M.is_pub("Hindawi")])}
    ax.scatter(v, yy, s=14, color=[VERMILION if n in hidx else BLUE for n in names], zorder=3, edgecolor="white", linewidth=0.3)
    for y, a, x in zip(yy, v, r):
        ax.text(a + 22, y, f"{float(x['b']):.1%}", va="center", fontsize=5.6, color=INK)
    short = lambda n: (n.split(" : ")[0].split(" = ")[0].replace("Journal of", "J").replace("journal of", "J").replace("International", "Int")
                       .replace("Computational", "Comput").replace("environmental", "environ"))
    ax.set_yticks(yy, [short(n)[:34] for n in names], fontsize=5.6)
    ax.set_xlim(0, 1750)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Retracted papers (label: % of citable items)", fontsize=7.5)
    ax.legend(handles=[matplotlib.lines.Line2D([], [], marker="o", linestyle="", color=VERMILION, markersize=4, label="Hindawi"),
                       matplotlib.lines.Line2D([], [], marker="o", linestyle="", color=BLUE, markersize=4, label="Other publishers")], fontsize=6.5, loc="lower right")
    ax.set_title("D  Journals with the most retractions", loc="left", fontsize=8.5, x=-0.55)


def main():
    rows_r, ry, _, _ = M.retracted_rows(2020, LAST)
    ctrl, dist = M.prior_matched_controls(rows_r, ry)
    keep = np.array([i in ctrl for i in rows_r])
    rows_r, ry = rows_r[keep], ry[keep]
    cm = lambda i, Y: np.nanmean([cites(c, Y) for c in ctrl[i]]) if py[i] <= Y <= LAST else np.nan  # noqa: E731
    print(len(rows_r), "papers", flush=True)

    fig = plt.figure(figsize=(7.2, 13.0))
    gs = fig.add_gridspec(4, 1, hspace=0.42, height_ratios=[0.72, 1.2, 0.72, 1.45])
    T = read("fig7_retractions.csv")
    panels_ab(fig, gs[0].subgridspec(1, 2, wspace=0.2), T)
    cd = gs[1].subgridspec(1, 2, wspace=0.62, width_ratios=[1, 1.05])
    panel_c(fig.add_subplot(cd[0]))
    panel_d(fig.add_subplot(cd[1]), T)

    # E
    ax = fig.add_subplot(gs[2])
    rel = np.arange(-4, 6)
    sel = (ry >= 2010) & (ry <= LAST - 5) & (ry - py[rows_r] >= 4)    # the same papers at every point
    rows = []
    for r in rel:
        a = [cites(i, y + r) for i, y in zip(rows_r[sel], ry[sel])]
        b = [cites(c, y + r) for i, y in zip(rows_r[sel], ry[sel]) for c in ctrl[i]]
        sa, sb = stats(a), stats(b)
        for (m, ci, q1, q3, n), dx, color in ((sa, -0.17, VERMILION), (sb, 0.17, BLUE)):
            ax.vlines(r + dx, q1, q3, color=color, alpha=0.3, linewidth=4)
            ax.errorbar(r + dx, m, yerr=ci, color=color, marker="o", markersize=3, capsize=0, linewidth=0.9)
        rows.append([int(r), round(sa[0], 3), round(sa[1], 3), sa[2], sa[3], round(sb[0], 3), round(sb[1], 3), sb[2], sb[3], round(sa[0] / sb[0], 3), sa[4]])
    write_csv("f12e_around_retraction", ["years_from_retraction", "retracted_mean", "retracted_ci95", "retracted_q1", "retracted_q3", "controls_mean", "controls_ci95",
                                         "controls_q1", "controls_q3", "ratio", "papers"], rows)
    ax.axvline(0, color=INK, linewidth=0.7, linestyle=(0, (3, 2)))
    ax.set_xticks(rel, [f"{r:+d}".replace("-", "−") if r else "0" for r in rel], fontsize=6.5)
    ax.set_ylim(0, 9.5)
    ax.set_xlabel("Years from retraction (0 = year retracted)")
    ax.set_ylabel("Citations per paper per year")
    ax.grid(axis="x", visible=False)
    L2 = matplotlib.lines.Line2D
    ax.legend(handles=[L2([], [], color=VERMILION, marker="o", markersize=3, label="Retracted"), L2([], [], color=BLUE, marker="o", markersize=3, label="Matched controls"),
                       L2([], [], color=MUTED, linewidth=4, alpha=0.3, label="Middle half of papers")], fontsize=5.8, loc="upper right")
    ax.set_title(f"E  Citations per year before and after retraction (n = {int(sel.sum()):,})", loc="left", fontsize=8.5)

    # F, G
    lag = ry - py[rows_r]
    lags = list(range(1, 11))
    out = []
    for L in lags:
        m = (lag == L) & (ry + 3 <= LAST)
        idx, ys = rows_r[m], ry[m]
        before = np.array([sum(cites(i, Y) for Y in range(int(py[i]), int(y))) for i, y in zip(idx, ys)])
        after = np.array([np.mean([cites(i, y + d) for d in (1, 2, 3)]) for i, y in zip(idx, ys)])
        after_c = np.array([np.mean([cm(i, y + d) for d in (1, 2, 3)]) for i, y in zip(idx, ys)])
        old = py[idx] <= 2011
        q = np.percentile(before, [25, 50, 75])
        boot = np.random.default_rng(L).integers(0, len(idx), (500, len(idx)))
        ratios = after[boot].mean(axis=1) / after_c[boot].mean(axis=1)
        out.append([L + 1, int(m.sum()), round(float(q[1]), 1), round(float(q[0]), 1), round(float(q[2]), 1), round(float(before.mean() / L), 2),
                    round(float(after.mean() / after_c.mean()), 3), round(float(np.percentile(ratios, 2.5)), 3), round(float(np.percentile(ratios, 97.5)), 3),
                    round(float(after[old].mean() / after_c[old].mean()), 3) if old.sum() >= 50 else ""])
    write_csv("f12fg_late_retraction", ["retracted_in_year", "papers", "citations_before_median", "before_q1", "before_q3", "before_per_year", "after_vs_controls", "ratio_ci_low", "ratio_ci_high",
                                        "after_vs_controls_papers_to_2011"], out)

    # H
    sub = gs[3].subgridspec(2, 3, hspace=0.42, wspace=0.26)
    yrs = np.arange(12)
    rows = []
    for k, L in enumerate(range(1, 7)):
        ax = fig.add_subplot(sub[k // 3, k % 3])
        m = lag == L
        idx = rows_r[m]
        A = np.array([[cites(i, py[i] + t) for t in yrs] for i in idx])
        B = np.array([[cm(i, py[i] + t) for t in yrs] for i in idx])
        n = (~np.isnan(A)).sum(axis=0)
        show = n >= MIN_PAPERS
        for M_, color in ((A, VERMILION), (B, BLUE)):
            mean = np.nanmean(M_, axis=0)
            ci = 1.96 * np.nanstd(M_, axis=0) / np.sqrt(np.maximum(n, 1))
            ax.fill_between(yrs[show] + 1, (mean - ci)[show], (mean + ci)[show], color=color, alpha=0.2, linewidth=0)
            ax.plot(yrs[show] + 1, mean[show], color=color, marker="o", markersize=2.2, linewidth=1.2)
        ax.axvline(L + 1, color=INK, linewidth=0.7, linestyle=(0, (3, 2)))
        ax.set_xlim(0.5, 12.5)
        ax.set_xticks([1, 3, 5, 7, 9, 11])
        ax.set_ylim(0, None)
        ax.tick_params(labelsize=6.5)
        ax.set_title(("F  " if k == 0 else "") + f"Retracted in year {L + 1} (n = {int(m.sum()):,})", loc="left", fontsize=7.5)
        if k % 3 == 0:
            ax.set_ylabel("Citations per paper", fontsize=7)
        if k >= 3:
            ax.set_xlabel("Year since publication", fontsize=7)
        a, b = np.nanmean(A, axis=0), np.nanmean(B, axis=0)
        rows += [[L + 1, int(t + 1), round(float(a[t]), 3), round(float(b[t]), 3), int(n[t])] for t in yrs if show[t]]
    write_csv("f12h_by_age", ["retracted_in_year", "year_since_publication", "retracted_mean", "controls_mean", "papers_observed"], rows)
    fig.text(0.125, 0.07, "*Dates from Retraction Watch, or a PubMed notice matched by title. F: year 1 = year published; bands, 95% CI; dashed, year retracted; later years hold fewer, older papers.", fontsize=6, color=MUTED)
    save(fig, "F12_retractions")


if __name__ == "__main__":
    main()
