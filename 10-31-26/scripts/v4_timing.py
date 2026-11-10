"""The six-figure set: main Figure 1 and Supplementary Figures S1 and S2, from the v3 panels of F1 and F2.

Usage: python 10-31-26/scripts/v4_timing.py   (from the IMPACT folder)
"""
import os
import sys

os.environ["FIG_DIR"] = "v4"
sys.path.insert(0, os.path.dirname(__file__))
import v3_f1 as A  # noqa: E402  (imports windows, which builds the arrays)
import v3_f2 as B  # noqa: E402
from make_figures import BLUE, GREEN, DATA, dc, jid, matplotlib, np, plt, pm, py  # noqa: E402
from v2_common import place_labels, save, write_csv  # noqa: E402


def reference_labels(ax, points, fontsize, avoid):
    """Panel F is narrow in Figure 1, so it names the eight reference journals only."""
    place_labels(ax, points[-8:], fontsize=5.2, avoid=[])


A.place_labels = reference_labels


def relabel(ax, text):
    ax._left_title.set_text(text)


def main():
    E = np.load(os.path.join(DATA, "ages72.npz"))
    row, K = E["row"], E["counts"]
    keep = (pm[row] != 6) & ~np.isin(jid[row], list(A.W.UNDERCOUNTED))
    A.W.V["rate24"] = K[keep, :36].astype(np.float64) @ A.rate_weights()
    ry, rm, rc = py[row], pm[row], dc[row]
    in_cohort = (ry >= A.COHORT[0]) & (ry <= A.COHORT[1]) & (rm >= 1) & (rm != 6)
    curves = {}
    for lab, cls in (("Research articles", 0), ("Reviews", 1)):
        s = np.flatnonzero(in_cohort & (rc == cls))
        curves[lab] = (K[s, :60].sum(axis=0, dtype=np.float64) / len(s), len(s))
    curve = curves["Research articles"][0]
    P = A.twin_pairs(row, K)
    ja, jb = K[P[:, 0], 12:36].astype(float).sum(axis=1), K[P[:, 1], 1:25].astype(float).sum(axis=1)
    fa, fb = K[P[:, 0], 0:24].astype(float).sum(axis=1), K[P[:, 1], 0:24].astype(float).sum(axis=1)
    T, R = B.read("fig9_journal_timing.csv"), B.read("fig9fg_annual_report_papers.csv")

    # Figure 1
    fig = plt.figure(figsize=(7.2, 11.9))
    gs = fig.add_gridspec(4, 1, hspace=0.42, height_ratios=[1, 1, 1, 1.42])
    r0, r1 = gs[0].subgridspec(1, 2, wspace=0.3), gs[1].subgridspec(1, 2, wspace=0.3)
    r2 = gs[2].subgridspec(1, 3, wspace=0.5)
    ax = fig.add_subplot(r0[0]); A.panel_c(ax, curve); relabel(ax, "A  Citations by months since publication")
    ax = fig.add_subplot(r0[1]); A.panel_d(ax, K, P, ja, jb, fa, fb); relabel(ax, "B  Matched January and December papers")
    ax = fig.add_subplot(r1[0]); A.panel_e(ax, K, row, in_cohort); relabel(ax, "C  Citations per year, by publication month")
    ax = fig.add_subplot(r1[1]); A.panel_g(ax, curves); relabel(ax, "D  JIF credit by publication month")
    ax = fig.add_subplot(r2[0]); B.panel_a(ax, T); relabel(ax, "E  Effect of timing on journals")
    ax = fig.add_subplot(r2[1]); print("F", A.panel_i(ax), flush=True); relabel(ax, "F  JIF-style and 24-month rates"); ax.get_legend().remove()
    ax = fig.add_subplot(r2[2]); A.panel_j(ax); relabel(ax, "G  Consistency of journal rates")
    B.panel_f(fig, gs[3].subgridspec(3, 4, wspace=0.42, hspace=1.05, height_ratios=[0.16, 1, 1]), R, label="H  Moving one report")
    save(fig, "Fig1_timing")

    # Supplementary Figure S1
    fig = plt.figure(figsize=(7.2, 8.0))
    gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.3)
    rows = []
    A.paper_panel(fig.add_subplot(gs[0, 0]), 16275915, 2005, 11, "A  Hirsch, PNAS, Nov 2005 (h-index)", rows)
    A.paper_panel(fig.add_subplot(gs[0, 1]), 21376230, 2011, 3, "B  Hanahan & Weinberg, Cell, Mar 2011 (Hallmarks)", rows)
    handles = [matplotlib.patches.Patch(color=c, label=t) for c, t in
               ((A.DARK, "Year published (no JIF counts it)"), (BLUE, "First JIF year"), (GREEN, "Second JIF year"), (A.LIGHT, "Later years (no JIF counts them)"))]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=4, fontsize=6.5, frameon=False, handlelength=1.1, columnspacing=1.2)
    ax = fig.add_subplot(gs[1, 0]); A.panel_f(ax); relabel(ax, "C  Items published January to March")
    ax = fig.add_subplot(gs[1, 1]); A.panel_h(ax, K, row, in_cohort); relabel(ax, "D  All citations by publication month, at matched ages")
    ax = fig.add_subplot(gs[2, 0]); A.panel_k(ax); relabel(ax, "E  Correlation of each rate with later citations")
    A.key(fig.add_subplot(gs[2, 1]))
    save(fig, "S1_publication_month")

    # Supplementary Figure S2
    early, late = B.review_ranks(T)
    fig = plt.figure(figsize=(7.2, 9.4))
    gs = fig.add_gridspec(3, 1, hspace=0.42, height_ratios=[1.15, 1.3, 0.8])
    top = gs[0].subgridspec(1, 2, wspace=0.5)
    ax = fig.add_subplot(top[0]); B.panel_b(ax, T); relabel(ax, "A  Largest changes, and reference journals")
    ax.set_title(ax._left_title.get_text(), loc="left", fontsize=8.5, x=-0.5)
    ax = fig.add_subplot(top[1]); B.panel_c(ax, T, early, late); relabel(ax, "B  Reviews and other items, January to March")
    mid = gs[1].subgridspec(1, 2, wspace=0.42, width_ratios=[0.9, 1.1])
    ax = fig.add_subplot(mid[0]); B.panel_d(ax, early, late); relabel(ax, "C  If publication months moved later")
    ax.set_title(ax._left_title.get_text(), loc="left", fontsize=8.5, x=-0.75)
    B.panel_g(fig, mid[1].subgridspec(3, 2, wspace=0.5, hspace=0.95, height_ratios=[0.1, 1, 1]), label="D  One late-year paper moved earlier", cols=2)
    for ax in fig.axes[-4:-2]:
        ax.set_xlabel("")
    ax = fig.add_subplot(gs[2].subgridspec(1, 2, width_ratios=[0.28, 0.72], wspace=0)[1]); B.panel_e(ax, R); relabel(ax, "E  When the big annual reports come out, and how much they draw")
    save(fig, "S2_timing_detail")


if __name__ == "__main__":
    main()
