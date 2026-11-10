"""F7 (reviews) and F8 (sibling and society journals): figure_revision_plan.md, Task 8.

Each journal shown gets a pair: its rate lines above its papers per year.
F7   A, B: lift from non-research items across journals. C: the review_lift set from journal_panels.csv.
F8a  each flagship and its family's largest open-access journal (v2_pairs.py).
F8b  the high-volume journals with the most reviews among those with a matched society journal. The pairs come from alt6,
     matched by hand: nothing in our data says which journals belong to a society, and a similarity rule gave odd partners.

Usage: python 10-31-26/scripts/v2_f78.py   (from the IMPACT folder)
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import alt_figures as A  # noqa: E402
from make_figures import BLUE, VERMILION, GRAY, INK, MUTED, con, dc, jid, matplotlib, np, plt, py  # noqa: E402
from v2_common import ORANGE, ROOT, SETTLED, V2, place_labels, save, write_csv  # noqa: E402
from v2_panels import REFERENCE  # noqa: E402

A.SETTLED = SETTLED
abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
slug_of = {a: s for s, a in con.execute("SELECT slug, abbreviation FROM journals")}
slug_abbr = {s: a for a, s in slug_of.items()}
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)
L = matplotlib.lines.Line2D
LEGEND = [L([], [], color=BLUE, linewidth=1.5, label="All citable items"), L([], [], color=VERMILION, linewidth=1.5, label="Research articles only"),
          matplotlib.patches.Patch(color=BLUE, label="Research papers"), matplotlib.patches.Patch(color=ORANGE, label="Reviews")]


def pair(fig, spec_rate, spec_vol, slug, ylabels, csv_rows, rate_top=None):
    s = A.series(slug)
    name = slug_abbr.get(slug, slug)
    ax = fig.add_subplot(spec_rate)
    ax.fill_between(s["x"], s["res"], s["all"], where=s["all"] >= s["res"], color=BLUE, alpha=0.15, linewidth=0)
    ax.plot(s["x"], s["all"], color=BLUE, linewidth=1.2)
    ax.plot(s["x"], s["res"], color=VERMILION, linewidth=1.2)
    last = np.flatnonzero(~np.isnan(s["all"] / s["res"]))
    lift = s["all"][last[-1]] / s["res"][last[-1]] - 1 if len(last) else float("nan")
    ax.set_title(name, loc="left", fontsize=7, pad=9)
    ax.text(0, 1.01, f"{lift:+.0%} vs research only".replace("-", "−"), transform=ax.transAxes, fontsize=5.5, color=MUTED, va="bottom")
    ax.set_ylim(0, rate_top)
    ax.set_xlim(2012, 2026)
    ax.set_xticks([2015, 2025], ["", ""])
    ax.tick_params(labelsize=5.8, pad=1)
    bx = fig.add_subplot(spec_vol)
    yrs = [y for y in sorted(s["pub"]) if 2012 <= y <= 2025]
    res = np.array([s["pub"][y].get("research", 0) for y in yrs])
    rev = np.array([s["pub"][y].get("review", 0) for y in yrs])
    bx.bar(yrs, res, color=BLUE, width=0.8)
    bx.bar(yrs, rev, bottom=res, color=ORANGE, width=0.8)
    bx.set_xlim(2011.3, 2026)
    bx.set_xticks([2015, 2025])
    bx.tick_params(labelsize=5.8, pad=1)
    bx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 10000 else f"{v:,.0f}"))
    bx.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
    share = rev[-3:].sum() / max((res[-3:] + rev[-3:]).sum(), 1)
    bx.set_ylim(0, (res + rev).max() * 1.32)     # headroom, so the label clears the bars
    bx.text(0.02, 0.99, f"reviews {share:.0%}", transform=bx.transAxes, fontsize=5.3, color=INK, va="top")
    if ylabels:
        ax.set_ylabel("24-month rate", fontsize=6)
        bx.set_ylabel("Papers per year", fontsize=6)
    csv_rows += [[name, m, round(a, 3), round(r, 3)] for m, a, r in zip(s["months"], s["all"], s["res"]) if m.endswith("-11")]
    return lift, share


def f7():
    panel = [r for r in csv.DictReader(open(os.path.join(V2, "data", "journal_panels.csv"))) if r["figure_set"].startswith("review_lift")]
    panel.append({"journal": "Cureus", "reason": "largest journal by volume not otherwise shown"})    # NEJM meets the rule twice, leaving a space
    rows = list(csv.DictReader(open(os.path.join(V2, "data", "f7ab_lift_all_journals.csv"))))
    lift = np.array([float(r["lift_from_reviews"]) for r in rows])
    share = np.array([float(r["review_share_items"]) for r in rows])
    by = {slug_abbr.get(r["slug"]): (float(r["lift_from_reviews"]), float(r["review_share_items"])) for r in rows}
    fig = plt.figure(figsize=(7.2, 12.0))
    gs = fig.add_gridspec(2, 1, hspace=0.26, height_ratios=[1, 3.5])
    top = gs[0].subgridspec(1, 2, wspace=0.32)

    ax = fig.add_subplot(top[0])
    ax.hist(np.clip(lift, -0.5, 1.5), bins=np.arange(-0.5, 1.55, 0.05), color=GRAY, edgecolor="white", linewidth=0.3)
    ymax = ax.get_ylim()[1]
    for k, (v, n) in enumerate(sorted((by[a][0], a) for a in REFERENCE)):
        y = ymax * (1.06 + 0.1 * k)
        ax.plot([v, v], [0, y], color=BLUE, linewidth=0.7)
        ax.text(v + 0.02, y, f"{n} {v:+.0%}".replace("-", "−"), fontsize=5.8, color=INK, va="center")
    ax.set_ylim(0, ymax * 1.95)
    ax.set_yticks([t for t in ax.get_yticks() if t <= ymax])
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("All-citable rate over research-only rate")
    ax.set_ylabel("Journals")
    ax.set_title("A  Lift in the rate from non-research items", loc="left", fontsize=8.5)

    ax = fig.add_subplot(top[1])
    ax.scatter(share, lift, s=4, color=GRAY, alpha=0.4, linewidth=0)
    TOP = 1.45
    pts, named = [], []
    for r in panel:
        a = r["journal"]
        if a not in by:
            continue
        lift_, share_ = by[a]
        color = BLUE if a in REFERENCE else VERMILION
        ax.scatter(share_, min(lift_, TOP), s=13, color=color, edgecolor="white", linewidth=0.4, zorder=3)
        pts.append((share_, min(lift_, TOP), a + (f" ({lift_:+.0%})" if lift_ > TOP else "")))
        named.append([a, r["reason"], round(lift_, 4), round(share_, 4)])
    write_csv("f7b_named", ["journal", "why", "lift", "review_share"], named)
    ax.set_xlim(0, 0.72); ax.set_ylim(-0.5, 1.6)
    place_labels(ax, pts, fontsize=5.6, avoid=[(a_, b_) for a_ in (0.5, 0.55, 0.6, 0.65, 0.7) for b_ in (0.25, 0.4, 0.55)])
    ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Reviews as share of citable items")
    ax.set_ylabel("Lift over research-only rate")
    ax.legend(handles=[L([], [], marker="o", linestyle="", color=BLUE, markersize=3.5, label="Reference journals"),
                       L([], [], marker="o", linestyle="", color=VERMILION, markersize=3.5, label="Top, middle and bottom\nby rule")], fontsize=5.8, loc="center right", bbox_to_anchor=(1.0, 0.42))
    ax.set_title("B  Lift against the share of reviews", loc="left", fontsize=8.5)

    names = [r["journal"] for r in panel]
    sub = gs[1].subgridspec(11, 4, hspace=0.3, wspace=0.42, height_ratios=[1, 0.62, 0.42] * 3 + [1, 0.62])
    out = []
    for k, n in enumerate(names):
        row, col = (k // 4) * 3, k % 4
        pair(fig, sub[row, col], sub[row + 1, col], slug_of[n], col == 0, out)
    write_csv("f7c_rates_november", ["journal", "month", "rate_all_citable", "rate_research"], out)
    fig.text(0.125, 0.685, "C  Rate and papers per year, journals chosen by rule", fontsize=8.5)
    fig.legend(handles=LEGEND, loc="lower center", bbox_to_anchor=(0.5, 0.075), ncol=4, fontsize=6.5, frameon=False, handlelength=1.4)
    save(fig, "F7_reviews")


def f8(name, pairs, tag_a, tag_b, title, shared):
    n = len(pairs)
    fig = plt.figure(figsize=(7.2, 6.0))
    sub = fig.add_gridspec(5, n, hspace=0.3, wspace=0.46 if n > 4 else 0.34, height_ratios=[1, 0.62, 0.4, 1, 0.62])
    out = []
    for c, (a, b) in enumerate(pairs):
        s0, s1 = A.series(slug_of[a]), A.series(slug_of[b])
        top = max(np.nanmax(s0["all"]), np.nanmax(s1["all"])) * 1.1 if shared else None
        pair(fig, sub[0, c], sub[1, c], slug_of[a], c == 0, out, rate_top=top)
        pair(fig, sub[3, c], sub[4, c], slug_of[b], c == 0, out, rate_top=top)
    write_csv(name.lower() + "_rates_november", ["journal", "month", "rate_all_citable", "rate_research"], out)
    fig.text(0.125, 0.955, title, fontsize=8.5)
    fig.text(0.03, 0.72, tag_a, fontsize=7, rotation=90, va="center", fontweight="bold", color=INK)
    fig.text(0.03, 0.29, tag_b, fontsize=7, rotation=90, va="center", fontweight="bold", color=INK)
    fig.legend(handles=LEGEND, loc="lower center", bbox_to_anchor=(0.5, -0.015), ncol=4, fontsize=6.5, frameon=False, handlelength=1.4)
    save(fig, name)


def lift_table():
    """Lift for every journal at the settled month: the rule that picks F7's journals reads this file."""
    write_csv("f7ab_lift_all_journals", ["slug", "journal", "citable_items", "rate_all", "rate_research", "lift_from_reviews", "review_share_items", "review_share_citations"],
              A.field_inflation())


def main():
    P = list(csv.DictReader(open(os.path.join(V2, "data", "f8_pairs.csv"))))
    flag = [(r["first"], r["second"]) for r in P if r["kind"] == "flagship"]
    recent = (py >= 2023) & (py <= 2025) & (dc == 1)
    reviews = np.bincount(jid[recent])
    ids = {a: j for j, a in abbr.items()}
    soc = [(slug_abbr[s], slug_abbr[o]) for s, o in A.SOCIETY]
    soc.sort(key=lambda p: -reviews[ids[p[1]]])
    print("society pairs by reviews:", [(a, b, int(reviews[ids[b]])) for a, b in soc], flush=True)
    write_csv("f8b_pairs", ["society_journal", "high_volume_journal", "reviews_2023_25", "shown"],
              [[a, b, int(reviews[ids[b]]), i < 4] for i, (a, b) in enumerate(soc)])
    f7()
    f8("F8a_siblings", flag, "Flagship", "Open-access sibling", "Flagships and their open-access siblings", False)
    f8("F8b_society", [(a, b) for a, b in soc[:4]], "Society journal", "High-volume journal", "Society journals and high-volume journals", True)


if __name__ == "__main__":
    if "lift" in sys.argv:
        lift_table()
    else:
        main()
