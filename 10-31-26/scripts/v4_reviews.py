"""The six-figure set: main Figure 4 and Supplementary Figure S5, from the v3 panels of F7.

Usage: python 10-31-26/scripts/v4_reviews.py   (from the IMPACT folder)
"""
import csv
import os
import sys

os.environ["FIG_DIR"] = "v4"
sys.path.insert(0, os.path.dirname(__file__))
import v3_f7 as N  # noqa: E402
from v3_f7 import BLUE, FIRST, GRAY, INK, LEGEND, PCT, REFERENCE, SECOND, V2, foot, head, matplotlib, np, outliers, overlay, pair, place_labels, plt, save, slug_abbr, slug_of, write_csv  # noqa: E402


def main():
    rows = list(csv.DictReader(open(os.path.join(V2, "data", "f7ab_lift_all_journals.csv"))))
    picks, res = outliers(rows)
    for slug in picks:
        if len(slug_abbr.get(slug, slug)) > 30:
            slug_abbr[slug] = slug_abbr[slug].split()[0]
    lift = np.array([float(r["lift_from_reviews"]) for r in rows])
    share = np.array([float(r["review_share_items"]) for r in rows])
    by = {r["slug"]: (float(r["lift_from_reviews"]), float(r["review_share_items"])) for r in rows}
    fig = plt.figure(figsize=(7.2, 8.8))
    gs = fig.add_gridspec(3, 1, hspace=0.62, height_ratios=[1.25, 0.72, 0.72])
    top = gs[0].subgridspec(1, 2, wspace=0.32)

    ax = fig.add_subplot(top[0])
    ax.hist(np.clip(lift, -0.5, 1.5), bins=np.arange(-0.5, 1.55, 0.05), color=GRAY, edgecolor="white", linewidth=0.3)
    ymax = ax.get_ylim()[1]
    for k, (v, n) in enumerate(sorted((by[slug_of[a]][0], a) for a in REFERENCE)):
        y = ymax * (1.06 + 0.1 * k)
        ax.plot([v, v], [0, y], color=BLUE, linewidth=0.7)
        ax.text(v + 0.02, y, f"{n} {v:+.0%}".replace("-", "−"), fontsize=5.8, color=INK, va="center")
    best = int(np.argmax(lift))
    name = slug_abbr.get(rows[best]["slug"], rows[best]["journal"])
    ax.plot([1.47, 1.47], [0, ymax * 0.42], color=INK, linewidth=0.7)
    ax.text(1.45, ymax * 0.44, f"Highest:\n{name}\n{lift[best]:+.0%} (off the axis)", fontsize=5.8, color=INK, va="bottom", ha="right")
    ax.set_ylim(0, ymax * 1.95)
    ax.set_yticks([t for t in ax.get_yticks() if t <= ymax])
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("All-citable rate over research-only rate")
    ax.set_ylabel("Journals")
    ax.set_title("A  Lift in the rate from non-research items", loc="left", fontsize=8.5)

    ax = fig.add_subplot(top[1])
    TOP = 2.3
    ax.scatter(share, np.minimum(lift, TOP), s=4, color=BLUE, alpha=0.3, linewidth=0)
    pts = []
    for slug in picks:
        l_, s_ = by[slug]
        a = slug_abbr.get(slug, slug)
        ax.scatter(s_, min(l_, TOP), s=13, color=BLUE, edgecolor="white", linewidth=0.4, zorder=3)
        pts.append((s_, min(l_, TOP), a + (f" ({l_:+.0%})" if l_ > TOP else "")))
    ax.set_xlim(0, 0.72); ax.set_ylim(-0.5, 2.5)
    for x, y, ha, va, t in ((0.03, 0.97, "left", "top", "Few reviews,\nhighly cited"), (0.97, 0.97, "right", "top", "Many reviews,\nhighly cited"),
                            (0.97, 0.03, "right", "bottom", "Many reviews,\nless cited"), (0.03, 0.03, "left", "bottom", "Few reviews,\nless cited")):
        ax.text(x, y, t, transform=ax.transAxes, ha=ha, va=va, fontsize=6, color=INK, fontweight="bold")
    keep = [(a_, b_) for a_ in (0.02, 0.06, 0.1, 0.14) for b_ in (2.2, 2.35, -0.3, -0.42)] + [(a_, b_) for a_ in (0.56, 0.6, 0.64, 0.68) for b_ in (2.2, 2.35, -0.3, -0.42)]
    place_labels(ax, pts, fontsize=5.6, avoid=keep)
    ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Reviews as share of citable items")
    ax.set_ylabel("Lift over research-only rate")
    ax.set_title("B  Lift against the share of reviews", loc="left", fontsize=8.5)

    P = list(csv.DictReader(open(os.path.join(V2, "data", "f8_pairs.csv"))))
    flag = [(r["first"], r["second"]) for r in P if r["kind"] == "flagship"]
    sub = gs[1].subgridspec(2, len(flag), hspace=0.3, wspace=0.5, height_ratios=[1, 0.62])
    out = []
    for c, (a, b) in enumerate(flag):
        overlay(fig, sub[0, c], sub[1, c], a, b, c == 0, out)
    head(fig, fig.axes[-2], "C  Flagships and their open-access siblings")
    foot(fig, fig.axes[-1], [matplotlib.patches.Patch(color=FIRST, label="Flagship"), matplotlib.patches.Patch(color=SECOND, label="Open-access sibling")], 2)
    S = list(csv.DictReader(open(os.path.join(V2, "data", "f8b_pairs.csv"))))[:6]
    sub = gs[2].subgridspec(2, len(flag), hspace=0.3, wspace=0.5, height_ratios=[1, 0.62])
    for c, r in enumerate(S):
        overlay(fig, sub[0, c], sub[1, c], r["society_journal"], r["high_volume_journal"], c == 0, out)
    head(fig, fig.axes[-2], "D  Society journals and high-volume open-access journals")
    foot(fig, fig.axes[-1], [matplotlib.patches.Patch(color=FIRST, label="Society journal"), matplotlib.patches.Patch(color=SECOND, label="High-volume journal")], 2)
    save(fig, "Fig4_reviews")

    fig = plt.figure(figsize=(7.2, 2.9))
    sub = fig.add_gridspec(2, 6, hspace=0.3, wspace=0.5, height_ratios=[1, 0.62], top=0.84, bottom=0.17)
    out = []
    for c, slug in enumerate(picks):
        pair(fig, sub[0, c], sub[1, c], slug, c == 0, out)
        t = fig.axes[-2]._left_title
        t.set_fontsize(5.0 if len(t.get_text()) > 22 else 6.3)
    fig.legend(handles=LEGEND, loc="lower center", ncol=4, fontsize=6, frameon=False, handlelength=1.4)
    save(fig, "S5_outlier_journals")


if __name__ == "__main__":
    main()
