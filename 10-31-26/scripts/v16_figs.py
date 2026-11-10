"""v16: figures renumbered to follow manuscript v3, with the figure edits its comments ask for.

Main figures: old Fig 5 (timing) becomes Fig 2; old Figs 2-4 become Figs 3-5. No panel moves.
Supplementary figures, in the order the text cites them:
  S1  institutions (old S4 A-C). "Links" are now "institutions on papers"; the author-count panels (old S4 D, E) leave the paper
  S2  publishers (old S8)
  S3  publication month (old S1), panels now A, B (Hirsch, Hanahan), C matched ages (old D), D correlation (old E), E Jan-Mar (old C)
  S4  timing detail (old S2); D gains a key, and the journal's two rates move to a right-hand axis so their small changes show
  S5  outlier journals (old S3); S6, S7 unchanged; S8 retractions (old S5)

Usage (from the IMPACT folder), one job per process because older scripts fix module state at import:
  python 10-31-26/scripts/v16_figs.py setup
  python 10-31-26/scripts/v16_figs.py s1
  python 10-31-26/scripts/v16_figs.py timing
"""
import inspect
import os
import shutil
import sys

os.environ["FIG_DIR"] = "v16"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v13_base as B13  # noqa: E402  first import fixes V2 at v16
from v2_common import ROOT, V2  # noqa: E402

V15 = os.path.join(ROOT, "10-31-26", "v15")
RENAME = {"Fig5_timing": "Fig2_timing", "Fig2_reviews": "Fig3_reviews", "Fig3_few_papers": "Fig4_few_papers", "Fig4_int_j_surg": "Fig5_int_j_surg",
          "S8_publishers": "S2_publishers", "S1_publication_month": "S3_publication_month", "S2_timing_detail": "S4_timing_detail",
          "S3_outlier_journals": "S5_outlier_journals", "S5_retractions": "S8_retractions"}
DROP = {"S4_institutions_and_authors"}          # rebuilt as S1_institutions


def setup():
    os.makedirs(os.path.join(V2, "data"), exist_ok=True)
    for f in os.listdir(V15):
        stem, ext = os.path.splitext(f)
        if ext in (".png", ".pdf") and stem not in DROP:
            shutil.copy(os.path.join(V15, f), os.path.join(V2, RENAME.get(stem, stem) + ext))
    for f in os.listdir(os.path.join(V15, "data")):
        shutil.copy(os.path.join(V15, "data", f), os.path.join(V2, "data"))


def s1():
    """Old S4 A-C on one row, worded as institutions on papers."""
    import v13_figs as F13
    src = inspect.getsource(F13.s5)
    a = src.index("    # D, E: author lists")
    b = src.index('    F11.save(fig, "S5_institutions_and_authors")\n')
    src = src[:a] + '    F11.save(fig, "S1_institutions")\n'
    swaps = (
        ("""    fig = plt.figure(figsize=(7.2, 7.4))
    gs = fig.add_gridspec(2, 1, hspace=0.38, height_ratios=[1, 0.82])
    top = gs[0].subgridspec(1, 2, wspace=0.32, width_ratios=[1, 1])
""", """    fig = plt.figure(figsize=(7.2, 3.35))
    top = fig.add_gridspec(1, 3, wspace=0.5, width_ratios=[1.12, 1.0, 0.78], left=0.115, right=0.99, top=0.9, bottom=0.17)
"""),
        ('ax.set_xlabel("Share of institution links")', 'ax.set_xlabel("Share of institutions on papers")'),
        ('"A  Share of links by region"', '"A  Institutions on papers, by region"'),
        ('"100 with most links"', '"100 with most papers"'),
        ('"50 with most links"', '"50 with most papers"'),
        ('"10 with most links"', '"10 with most papers"'),
        ('"Open: a same-sized random draw"', '"Open: random draw"'),
        ('ax.set_ylabel("Share of links to large institutions")', 'ax.set_ylabel("Share of institutions on papers")'),
        ('"B  How concentrated each journal\'s links are"', '"B  Concentration of institutions"'),
        ("fontsize=5.8, loc=\"upper left\", ncol=2, handletextpad=0.1, columnspacing=0.7)", "fontsize=5.4, loc=\"upper left\", ncol=2, handletextpad=0.1, columnspacing=0.5)"),
        ("    low = gs[1].subgridspec(1, 3, wspace=0.6, width_ratios=[1, 1.15, 0.85])\n", ""),
        ("    ax = fig.add_subplot(low[0])\n", "    ax = fig.add_subplot(top[2])\n"),
        ('title="Journal share vs all-journal share", title_fontsize=5.4, fontsize=5.4,', 'title="Journal share ÷ all-journal share", title_fontsize=5.2, fontsize=5.2,'),
        ("ax.set_ylim(0, 0.95)", "ax.set_ylim(0, 1.13); ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0]); ax.spines['left'].set_bounds(0, 1.0)"),
    )
    for old, new in swaps:
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    exec(src, F13.s5.__globals__)
    F13.s5.__globals__["s5"]()


PANEL_G_SWAPS = (
    ('    head.text(0, 0.5, label, fontsize=8.5, va="center", transform=head.transAxes)\n',
     '''    head.text(0, 1.0, label, fontsize=8.5, va="top", transform=head.transAxes)
    L2 = matplotlib.lines.Line2D
    head.legend(handles=[L2([], [], color=BLUE, linewidth=1.1, linestyle=(0, (3, 2)), label="Paper's own citations in the JIF-style rate (left axis)"),
                         L2([], [], color=BLUE, linewidth=1.4, label="Journal's JIF-style rate (right axis)"),
                         L2([], [], color=VERMILION, linewidth=1.4, label="Journal's 24-month rate (right axis)"),
                         L2([], [], marker="o", color=INK, linestyle="", markersize=3.2, label="Actual month")],
                loc="upper left", bbox_to_anchor=(0, 0.6), ncol=2, fontsize=5.4, frameon=False, handlelength=2.2, columnspacing=1.0, labelspacing=0.3)
'''),
    ('''        ax.plot(x, change[:, 0], color=BLUE, linewidth=1.4)
        ax.plot(x, change[:, 1], color=VERMILION, linewidth=1.4)
''', '''        rx = ax.twinx()
        rx.plot(x, change[:, 0], color=BLUE, linewidth=1.4)
        rx.plot(x, change[:, 1], color=VERMILION, linewidth=1.4)
'''),
    ('''        ax.set_xlim(1, m)
''', '''        ax.set_xlim(1, m)
        lo1, hi1 = min(0.0, float(change[:, 2].min())), max(0.0, float(change[:, 2].max()))
        lo2, hi2 = min(0.0, float(change[:, :2].min())), max(0.0, float(change[:, :2].max()))
        hi2 = max(hi2, 0.5)                 # at least +0.5% of room, so a flat journal line still reads as flat
        p1 = hi1 / (hi1 - lo1) if hi1 > lo1 else 1.0   # zero sits at the same height on both axes
        p2 = hi2 / (hi2 - lo2) if hi2 > lo2 else 1.0
        p = max(p1, p2)
        span1 = max(hi1 / p if p else 0, -lo1 / (1 - p) if p < 1 else 0)
        span2 = max(hi2 / p if p else 0, -lo2 / (1 - p) if p < 1 else 0)
        ax.set_ylim(-(1 - p) * span1 * 1.08, p * span1 * 1.08)
        rx.set_ylim(-(1 - p) * span2 * 1.08, p * span2 * 1.08)
        rx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.2g}%".replace("-", "−") if abs(v) > 1e-9 else "0%"))
        rx.tick_params(labelsize=6)
        rx.grid(False)
        rx.spines["right"].set_visible(True)
        if i % cols == cols - 1:
            rx.set_ylabel("Journal's rate", fontsize=6.5)
'''),
    ('            ax.set_ylabel("Change in rate", fontsize=6.5)\n', '            ax.set_ylabel("Paper\'s citations", fontsize=6.5)\n'),
)

S3_SWAPS = (
    ('ax = fig.add_subplot(gs[1, 0]); A.panel_f(ax); relabel(ax, "C  Items published January to March")',
     'ax = fig.add_subplot(gs[2, 0]); A.panel_f(ax); relabel(ax, "E  Items published January to March")'),
    ('ax = fig.add_subplot(gs[1, 1]); A.panel_h(ax, K, row, in_cohort); relabel(ax, "D  All citations by publication month, at matched ages")',
     'ax = fig.add_subplot(gs[1, 0]); A.panel_h(ax, K, row, in_cohort); relabel(ax, "C  All citations by publication month, at matched ages")'),
    ('ax = fig.add_subplot(gs[2, 0]); A.panel_k(ax); relabel(ax, "E  Correlation of each rate with later citations")',
     'ax = fig.add_subplot(gs[1, 1]); A.panel_k(ax); relabel(ax, "D  Correlation of each rate with later citations")'),
    ("B.panel_g(fig, mid[1].subgridspec(3, 2, wspace=0.5, hspace=0.95, height_ratios=[0.1, 1, 1]), label=",
     "B.panel_g(fig, mid[1].subgridspec(3, 2, wspace=0.95, hspace=0.95, height_ratios=[0.62, 1, 1]), label="),
    ("    for ax in fig.axes[-4:-2]:\n        ax.set_xlabel(\"\")\n",
     "    for ax in [a for a in fig.axes if a.get_xlabel() == \"Month published\"][:2]:\n        ax.set_xlabel(\"\")\n"),
)

# v15's patches for main Figure 5 (now Figure 2), so the rerun draws it as v15 did
FIG5_SWAPS = (
    ("gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.3)", "gs = fig.add_gridspec(3, 2, hspace=0.78, wspace=0.3)"),
    ('fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=4,',
     'fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, fig.axes[-1].get_position().y0 - 0.052), ncol=4,'),
    ('relabel(ax, "F  JIF-style and 24-month rates"); ax.get_legend().remove()',
     'relabel(ax, "F  JIF-style and 24-month rates"); ax.legend(ax.get_legend_handles_labels()[0], ["Largest gaps (500+ items)", "Reference journals"], fontsize=5.6, loc="lower right", handletextpad=0.1, borderaxespad=0.2)'),
)


def timing():
    """Supplementary Figures S3 (old S1, reordered) and S4 (old S2, panel D with a key and a right-hand axis). Main Figure 2 is kept from v15."""
    import v5_timing as T
    B13.patch(T.B.panel_g, *PANEL_G_SWAPS)
    T.B.panel_g = T.B.__dict__["panel_g"]
    B13.patch(T.main, *(FIG5_SWAPS + S3_SWAPS))
    T.main()
    for ext in (".png", ".pdf"):
        os.remove(os.path.join(V2, "Fig5_timing" + ext))                      # identical to v15's, which setup copied as Fig2_timing
        os.replace(os.path.join(V2, "S1_publication_month" + ext), os.path.join(V2, "S3_publication_month" + ext))
        os.replace(os.path.join(V2, "S2_timing_detail" + ext), os.path.join(V2, "S4_timing_detail" + ext))


JOBS = {"setup": setup, "s1": s1, "timing": timing}

if __name__ == "__main__":
    for job in sys.argv[1:]:
        JOBS[job]()
