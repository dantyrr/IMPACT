"""v15: Figure 2B after the v14 comments.

  Fig 2B   every journal with over 58% reviews or a rise over 100% is named; PLoS One is no longer marked; reference journals are named beside their dots, JAMA below and Cell above
  Fig 2    the middle row gains citations per year by publisher (D) and to each publisher's top journal (G): C-G, then H and I for the journal pairs
  Fig 2    A's y axis stops at the first tick over the tallest bar; B says change, not rise; D and G count citations to reviews; C-G are shorter
  Fig 3A   y axis as in 2A
  Fig 5F   its key is back (orange, largest differences; blue, reference journals)
Everything else is copied from v14.

Usage (from the IMPACT folder): python 10-31-26/scripts/v15_figs.py
"""
import os
import shutil
import sys

os.environ["FIG_DIR"] = "v15"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v13_base  # noqa: E402,F401  first import fixes V2 at v15
from v2_common import ROOT, V2  # noqa: E402

V14 = os.path.join(ROOT, "10-31-26", "v14")
SHARE_CUT, RISE_CUT = 0.58, 1.0

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
    extreme = [r["slug"] for r in rows if (by[r["slug"]][1] > SHARE_CUT or by[r["slug"]][0] > RISE_CUT) and r["slug"] not in picks]
    write_csv("f2b_named_extremes", ["slug", "review_share", "rise"], [[s_, round(by[s_][1], 4), round(by[s_][0], 4)] for s_ in extreme])
    named = list(picks) + extreme
    refs = sorted((N.slug_of[a] for a in N.REFERENCE if a != "PLoS One" and N.slug_of[a] not in named), key=lambda s_: by[s_][1])
    for slug in named + refs:
        l_, s_ = by[slug]
        ax.scatter(s_, min(l_, TOP), s=14, color=color_of(slug), edgecolor=INK if slug in refs else "white", linewidth=0.5 if slug in refs else 0.4, zorder=4)
    SHORT = {"medcomm": "MedComm", "bundesgesundheitsblatt-gesundheitsforschung-gesundheitsschutz": "Bundesgesundheitsblatt"}
    lab = lambda slug: SHORT.get(slug, N.slug_abbr.get(slug, slug))  # noqa: E731
    PLACE = {"signal-transduction-and-targeted-therapy": (0.43, 2.36, "left"), "trends-in-plant-science": (0.625, 2.0, "right"),
             "archives-of-toxicology": (0.245, 1.6, "left"), "medcomm": (0.36, 1.8, "left"),
             "diabetes-care": (0.165, 1.17, "left"), "discover-nano": (0.26, 1.03, "left"),
             "experimental-molecular-medicine": (0.33, 1.36, "left"), "genes-diseases": (0.44, 1.24, "left"),
             "trends-in-ecology-evolution": (0.565, 1.65, "right"), "trends-in-biotechnology": (0.715, 1.3, "right"),
             "current-neuropharmacology": (0.60, 0.88, "right"), "sports-medicine-auckland-n-z": (0.715, 0.95, "right"),
             "cardiology-in-review": (0.665, 0.27, "left"),
             "antioxidants-redox-signaling": (0.64, -0.36, "center"), "current-medicinal-chemistry": (0.715, -0.12, "right"),
             "science-robotics": (0.34, -0.27, "left"), "bundesgesundheitsblatt-gesundheitsforschung-gesundheitsschutz": (0.395, -0.43, "center"),
             }
    for slug in named:
        l_, s_ = by[slug]
        x0, y0, ha = PLACE.get(slug, (s_ + 0.02, min(l_, TOP), "left"))
        ax.annotate(lab(slug), (s_, min(l_, TOP)), xytext=(x0, y0), fontsize=5.4, color=INK, ha=ha, va="center", zorder=6,
                    arrowprops=dict(arrowstyle="-", color="#888888", linewidth=0.4, shrinkA=1, shrinkB=2))
    REF_PLACE = {"Sci Rep": (0.004, 1.06, (0, 0)), "Nature": (0.03, 0.94, (0, 0)), "Science": (0.056, 0.82, (0, 0)),
                 "Cell": (0.17, 0.86, (0.5, 0)), "JAMA": (0.15, -0.40, (0.5, 1)), "NEJM": (0.045, -0.395, (0.5, 1)), "Lancet": (0.235, -0.33, (0.5, 1))}
    for slug in refs:
        l_, s_ = by[slug]
        x0, y0, rp = REF_PLACE[lab(slug)]
        ax.annotate(lab(slug), (s_, min(l_, TOP)), xytext=(x0, y0), fontsize=5.4, color=INK, ha={0: "left", 0.5: "center"}[rp[0]],
                    va={0: "bottom", 1: "top"}[rp[1]], zorder=6, arrowprops=dict(arrowstyle="-", color="#888888", linewidth=0.4, shrinkA=0.5, shrinkB=2, relpos=rp))
    ax.set_xlim(0, 0.72); ax.set_ylim(-0.5, 2.5)
    L = matplotlib.lines.Line2D
    ax.legend(handles=[L([], [], marker="o", linestyle="", color=BLUE, markersize=3.5, label=f"Over 1 SD above the line ({int(hi_.sum())})"),
                       L([], [], marker="o", linestyle="", color=ORANGE, markersize=3.5, label=f"Over 1 SD below the line ({int(lo_.sum())})"),
                       L([], [], color=INK, linewidth=0.7, linestyle=(0, (3.5, 2.5)), label="Change equal to review share")],
              fontsize=5.4, loc="upper left", handlelength=1.6, borderaxespad=0.3, labelspacing=0.35)
    ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Reviews as share of citable items")
    ax.set_ylabel("Change in 24-month citation rate")
    ax.set_title("B  Change in rate against the share of reviews", loc="left", fontsize=8.5)
'''.replace("SHARE_CUT", repr(SHARE_CUT)).replace("RISE_CUT", repr(RISE_CUT))


def middle_row(fig, spec):
    """C-G: reviews and citations by publisher, the review share, and each publisher's top journal by reviews and by citations.
    Citations are those received each year by the citable items of the publisher or journal (counting citations only).
    Names sit right of the citation panels; the panel to the left of each uses the same colors."""
    import v5_fig12 as F2
    import v8_figs as V8
    from v5_fig12 import INK, PCT, matplotlib, np, write_csv
    M, dc, jid, py, C = F2.M, F2.dc, F2.jid, F2.py, F2.M.C
    YEARS, cols = F2.YEARS, F2.YEARS - 2003
    cit = lambda m: C[m][:, cols].sum(0).astype(float)  # noqa: E731
    mil = matplotlib.ticker.FuncFormatter(lambda v, _: (f"{v / 1e6:.0f}M" if v >= 1e7 or v % 1e6 == 0 else f"{v / 1e6:.1f}M") if v else "0")
    k1 = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v else "0")
    grid = spec.subgridspec(1, 5, wspace=0.6, width_ratios=[0.95, 1.8, 0.95, 0.95, 1.8])
    axes = [fig.add_subplot(grid[i]) for i in range(5)]
    PUB = F2.PUBLISHERS

    def frame(ax, right, title, ylabel, fmt):
        ax.set_xlim(YEARS[0], YEARS[-1] + right)
        ax.set_xticks([2005, 2015, 2025])
        ax.set_ylim(0, None)
        ax.tick_params(labelsize=6.3, pad=1.5)
        ax.yaxis.set_major_formatter(fmt)
        ax.set_ylabel(ylabel, fontsize=6.5, labelpad=1.5)
        ax.set_title(title, loc="left", fontsize=7.8, pad=4)

    ax, out, out2, ends = axes[0], [], [], []
    for name, col in PUB:
        v = M.per_year(M.citable & M.is_pub(name) & (dc == 1))
        ax.plot(YEARS, v, color=col, linewidth=1.3)
        out += [[name, int(y), int(n)] for y, n in zip(YEARS, v)]
        c = cit(M.citable & M.is_pub(name) & (dc == 1))
        axes[1].plot(YEARS, c, color=col, linewidth=1.3)
        ends.append((c[-1], V8.LABEL.get(name, name).replace(" incl. Cell Press", "").replace(" incl. Hindawi", ""), col))
        out2 += [[name, int(y), int(n)] for y, n in zip(YEARS, c)]
    write_csv("f2c_reviews_by_publisher", ["publisher", "year", "reviews"], out)
    write_csv("f2d_citations_by_publisher", ["publisher", "year", "citations_to_reviews"], out2)
    frame(ax, 0.5, "C  Reviews,\n    by publisher", "Reviews per year", k1)
    frame(axes[1], 17, "D  Citations to\n    those reviews", "Citations per year", mil)
    V8.end_labels(axes[1], ends, YEARS[-1], axes[1].get_ylim()[1] * 0.075, 5.4)

    ax, out, ends = axes[2], [], []
    for name, col in PUB:
        m = M.citable & M.is_pub(name)
        n, r = M.per_year(m), M.per_year(m & (dc == 1))
        v = np.where(n >= 500, r / np.maximum(n, 1), np.nan)
        ax.plot(YEARS, v, color=col, linewidth=1.3)
        out += [[name, int(y), round(float(s_), 4)] for y, s_ in zip(YEARS, v) if s_ == s_]
    allr = M.per_year(M.citable & (dc == 1)) / M.per_year(M.citable)
    ax.plot(YEARS, allr, color=INK, linewidth=1.5)
    write_csv("f2d_review_share", ["publisher", "year", "share"], out)
    frame(ax, 0.5, "E  Reviews as a\n    share of items", "Share of items", PCT)
    ax.annotate("All\njournals", (YEARS[-1], allr[-1]), xytext=(2020.5, 0.04), fontsize=5.6, color=INK, ha="center", va="center",
                arrowprops=dict(arrowstyle="-", color=INK, linewidth=0.6, shrinkA=1, shrinkB=1))

    ax, out, out2, ends = axes[3], [], [], []
    for name, col in PUB:
        m = M.citable & M.is_pub(name) & (dc == 1)
        r = m & (py >= 2023) & (py <= 2025)
        u, k = np.unique(jid[r], return_counts=True)
        j = int(u[np.argmax(k)])
        lab = F2.abbr[j].replace(" (Basel)", "").replace(" (Lausanne)", "")
        v = M.per_year(m & (jid == j))
        ax.plot(YEARS, v, color=col, linewidth=1.3)
        out += [[name, lab, int(y), int(n)] for y, n in zip(YEARS, v)]
        c = cit(M.citable & (jid == j) & (dc == 1))
        axes[4].plot(YEARS, c, color=col, linewidth=1.3)
        ends.append((c[-1], lab, col))
        out2 += [[name, lab, int(y), int(n)] for y, n in zip(YEARS, c)]
    write_csv("f2e_top_review_journals", ["publisher", "journal", "year", "reviews"], out)
    write_csv("f2g_citations_top_review_journals", ["publisher", "journal", "year", "citations_to_reviews"], out2)
    frame(ax, 0.5, "F  Top journal of\n    each publisher", "Reviews per year", matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.1f}k" if v else "0"))
    frame(axes[4], 17, "G  Citations to\n    those reviews", "Citations per year", k1)
    V8.end_labels(axes[4], ends, YEARS[-1], axes[4].get_ylim()[1] * 0.075, 5.4)
    for a_ in (axes[1], axes[4]):          # keep the lowest name clear of the x axis
        low = min(t.xyann[1] for t in a_.texts)
        floor = a_.get_ylim()[1] * 0.045
        for t in a_.texts:
            t.xyann = (t.xyann[0], t.xyann[1] + max(floor - low, 0))


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
    old_mid = """    mid = gs[1].subgridspec(1, 3, wspace=0.46)
    reviews_counts(fig.add_subplot(mid[0]))
    reviews_share(fig.add_subplot(mid[1]))
    reviews_top_journal(fig.add_subplot(mid[2]))
"""
    for old, new in ((old_mid, "    middle_row(fig, gs[1])\n"), ('"F  Flagships', '"H  Flagships'), ('"G  Society', '"I  Society'),
                     ("figsize=(7.2, 12.2)", "figsize=(7.2, 11.85)"), ("height_ratios=[1.15, 0.85, 0.72, 0.72]", "height_ratios=[1.15, 0.72, 0.72, 0.72]"),
                     ('    ax.set_title("A  How much non-research items raise the rate", loc="left", fontsize=8.5)\n',
                      '    ax.set_title("A  How much non-research items change the rate", loc="left", fontsize=8.5)\n    tidy_hist(ax)\n')):
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    F2.figure2.__globals__.update(middle_row=middle_row, tidy_hist=tidy_hist)
    exec(src, F2.figure2.__globals__)
    F2.figure2()
    os.replace(os.path.join(V2, "S4_outlier_journals.png"), os.path.join(V2, "S3_outlier_journals.png"))
    os.replace(os.path.join(V2, "S4_outlier_journals.pdf"), os.path.join(V2, "S3_outlier_journals.pdf"))


def tidy_hist(ax):
    """The y axis of a histogram whose labels sit above the bars: ticks and the axis line stop at the first tick over the tallest bar."""
    import matplotlib
    hmax = max(p.get_height() for p in ax.patches)
    ticks = matplotlib.ticker.MaxNLocator(nbins=4, steps=[1, 2, 2.5, 5, 10]).tick_values(0, hmax)
    top = min(t for t in ticks if t >= hmax)
    ax.set_yticks([t for t in ticks if 0 <= t <= top])
    ax.spines["left"].set_bounds(0, top)


def fig3():
    """Fig 3 as in v13, with A's y axis stopping at the first tick over the tallest bar. v13's S3 is not kept."""
    import v13_figs as F13
    v13_base.patch(F13.fig3, ("    R.panel_hist(ax, r, share, med)\n", "    R.panel_hist(ax, r, share, med)\n    tidy_hist(ax)\n"))
    F13.fig3.__globals__["tidy_hist"] = tidy_hist
    F13.fig3()
    for ext in (".png", ".pdf"):
        os.remove(os.path.join(V2, "S3_reliance_detail" + ext))


def timing():
    """Fig 5F with its key: v13's layout, without removing panel F's legend."""
    import v5_timing as T
    v13_base.patch(T.main,
                   ("gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.3)", "gs = fig.add_gridspec(3, 2, hspace=0.78, wspace=0.3)"),
                   ('fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=4,',
                    'fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, fig.axes[-1].get_position().y0 - 0.052), ncol=4,'),
                   ('relabel(ax, "F  JIF-style and 24-month rates"); ax.get_legend().remove()',
                    'relabel(ax, "F  JIF-style and 24-month rates"); ax.legend(ax.get_legend_handles_labels()[0], ["Largest gaps (500+ items)", "Reference journals"], fontsize=5.6, loc="lower right", handletextpad=0.1, borderaxespad=0.2)'))
    T.main()


def setup():
    os.makedirs(os.path.join(V2, "data"), exist_ok=True)
    for f in os.listdir(V14):
        if os.path.splitext(f)[1] in (".png", ".pdf") and not f.startswith("figure_legends"):
            shutil.copy(os.path.join(V14, f), os.path.join(V2, f))
    for f in os.listdir(os.path.join(V14, "data")):
        shutil.copy(os.path.join(V14, "data", f), os.path.join(V2, "data"))


if __name__ == "__main__":
    job = sys.argv[1] if len(sys.argv) > 1 else "all"
    if job in ("all", "setup"):
        setup()
    if job in ("all", "fig2"):
        fig2()
    if job in ("all", "fig3"):
        fig3()
    if job in ("all", "timing"):
        timing()
