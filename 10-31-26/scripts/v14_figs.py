"""v14: after the comments on v13/figure_legends_v13.docx.

  Fig 2B   dots more than 1 SD above (blue) or below (orange) the dashed line (rise equal to review share; a straight-line fit is almost
           the same line, slope 1.06, intercept -0.2%) are colored; the reference journals marked in A are named in a column with leader lines
  S3       dropped, so S4-S9 become S3-S8 (files renamed here; legends in v14_legends.py)
Everything else is copied from v13.

Usage (from the IMPACT folder): python 10-31-26/scripts/v14_figs.py
"""
import os
import shutil
import sys

os.environ["FIG_DIR"] = "v14"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v13_base  # noqa: E402,F401  first import fixes V2 at v14
from v2_common import ROOT, V2  # noqa: E402

V13 = os.path.join(ROOT, "10-31-26", "v13")
RENAME = {"S4_outlier_journals": "S3_outlier_journals", "S5_institutions_and_authors": "S4_institutions_and_authors", "S6_retractions": "S5_retractions",
          "S7_citers_over_time": "S6_citers_over_time", "S8_citers_absolute": "S7_citers_absolute", "S9_publishers": "S8_publishers"}

PANEL_B = '''    ax = fig.add_subplot(top[1])
    TOP = 2.3
    res = lift - share                      # distance above the dashed line; a straight-line fit is almost the same line
    fit = np.polyfit(share, lift, 1)
    mu, sd = float(res.mean()), float(res.std())
    hi_, lo_ = res > mu + sd, res < mu - sd
    mid_ = ~(hi_ | lo_)
    ax.scatter(share[mid_], np.minimum(lift[mid_], TOP), s=4, color=GRAY, alpha=0.3, linewidth=0)
    ax.scatter(share[hi_], np.minimum(lift[hi_], TOP), s=5, color=BLUE, alpha=0.6, linewidth=0)
    ax.scatter(share[lo_], np.minimum(lift[lo_], TOP), s=5, color=ORANGE, alpha=0.8, linewidth=0)
    ax.plot([0, 1], [0, 1], color=INK, linewidth=0.7, linestyle=(0, (3.5, 2.5)), zorder=2)
    write_csv("f2b_sd_groups", ["fit_slope", "fit_intercept", "mean_rise_minus_share", "sd", "above_1sd", "below_1sd", "journals"],
              [[round(float(fit[0]), 4), round(float(fit[1]), 4), round(mu, 4), round(sd, 4), int(hi_.sum()), int(lo_.sum()), len(rows)]])
    pos = {r["slug"]: i for i, r in enumerate(rows)}
    color_of = lambda slug: BLUE if hi_[pos[slug]] else ORANGE if lo_[pos[slug]] else GRAY  # noqa: E731
    refs = sorted((N.slug_of[a] for a in N.REFERENCE if N.slug_of[a] not in picks), key=lambda s_: by[s_][1])   # column top to bottom by review share, so leader lines fan out without crossing
    for slug in list(picks) + refs:
        l_, s_ = by[slug]
        ax.scatter(s_, min(l_, TOP), s=14, color=color_of(slug), edgecolor=INK if slug in refs else "white", linewidth=0.5 if slug in refs else 0.4, zorder=4)
    lab = lambda slug: (lambda t: t.split()[0] if len(t) > 30 else t)(N.slug_abbr.get(slug, slug))  # noqa: E731
    PLACE = {"signal-transduction-and-targeted-therapy": (0.43, 2.36, "left"), "trends-in-plant-science": (0.625, 2.0, "right"),
             "archives-of-toxicology": (0.245, 1.6, "left"), "science-robotics": (0.345, -0.27, "left"),
             "bundesgesundheitsblatt-gesundheitsforschung-gesundheitsschutz": (0.505, -0.13, "left"), "current-medicinal-chemistry": (0.715, 0.3, "right")}
    for slug in picks:
        l_, s_ = by[slug]
        x0, y0, ha = PLACE.get(slug, (s_ + 0.02, min(l_, TOP), "left"))
        ax.annotate(lab(slug), (s_, min(l_, TOP)), xytext=(x0, y0), fontsize=5.4, color=INK, ha=ha, va="center", zorder=6,
                    arrowprops=dict(arrowstyle="-", color="#888888", linewidth=0.4, shrinkA=1, shrinkB=2))
    for k, slug in enumerate(refs):
        l_, s_ = by[slug]
        ax.annotate(lab(slug), (s_, min(l_, TOP)), xytext=(0.135, 1.62 - 0.105 * k), fontsize=5.4, color=INK, ha="left", va="center", zorder=6,
                    arrowprops=dict(arrowstyle="-", color="#888888", linewidth=0.4, shrinkA=1, shrinkB=2, relpos=(0, 0.5)))
    ax.set_xlim(0, 0.72); ax.set_ylim(-0.5, 2.5)
    L = matplotlib.lines.Line2D
    ax.legend(handles=[L([], [], marker="o", linestyle="", color=BLUE, markersize=3.5, label=f"Over 1 SD above the line ({int(hi_.sum())})"),
                       L([], [], marker="o", linestyle="", color=ORANGE, markersize=3.5, label=f"Over 1 SD below the line ({int(lo_.sum())})"),
                       L([], [], color=INK, linewidth=0.7, linestyle=(0, (3.5, 2.5)), label="Rise equal to review share")],
              fontsize=5.4, loc="upper left", handlelength=1.6, borderaxespad=0.3, labelspacing=0.35)
    ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Reviews as share of citable items")
    ax.set_ylabel("Rise over research-only rate")
    ax.set_title("B  That rise against the share of reviews", loc="left", fontsize=8.5)
'''


def fig2():
    import inspect
    import v8_figs as V8
    F2, F1 = V8.F2, V8.F1
    F1.publisher_panel = V8.publisher_panel
    F2.labels = V8.end_labels
    F2.PUBLISHERS = [(n, V8.COLOR[n]) for n in V8.top_for_reviews()]
    src = inspect.getsource(F2.figure2)
    a = src.index("    ax = fig.add_subplot(top[1])\n    TOP = 2.3")
    b = src.index('    ax.set_title("B  That rise against the share of reviews", loc="left", fontsize=8.5)\n')
    b = src.index("\n", b) + 1
    src = src[:a] + PANEL_B + src[b:]
    exec(src, F2.figure2.__globals__)
    F2.figure2()
    os.replace(os.path.join(V2, "S4_outlier_journals.png"), os.path.join(V2, "S3_outlier_journals.png"))
    os.replace(os.path.join(V2, "S4_outlier_journals.pdf"), os.path.join(V2, "S3_outlier_journals.pdf"))


def setup():
    os.makedirs(os.path.join(V2, "data"), exist_ok=True)
    for f in os.listdir(V13):
        stem, ext = os.path.splitext(f)
        if ext in (".png", ".pdf") and not f.startswith(("figure_legends", "S3_reliance")):
            shutil.copy(os.path.join(V13, f), os.path.join(V2, RENAME.get(stem, stem) + ext))
    for f in os.listdir(os.path.join(V13, "data")):
        shutil.copy(os.path.join(V13, "data", f), os.path.join(V2, "data"))


if __name__ == "__main__":
    setup()
    fig2()
