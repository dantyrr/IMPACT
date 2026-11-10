"""F7 (v3): lift from non-research items, with v2's Figures 8a and 8b folded in, following the comments on figure_legends_v2.docx.

A   lift across journals, reference journals and the highest journal marked
B   lift against the share of reviews, with the journals furthest from the trend labelled and the corners described
C   those six journals: 24-month rate above papers per year
D   each flagship and its open-access sibling on one plot
E   society journals and high-volume open-access journals on one plot

The six in B and C: the three furthest above and three furthest below a straight-line fit of lift on review share, among journals
with papers in PubMed since at least 2017. That leaves out MedComm, which started in 2020.

Usage: python 10-31-26/scripts/v3_f7.py   (from the IMPACT folder)
"""
import csv
import os
import sys

os.environ.setdefault("FIG_DIR", "v3")
sys.path.insert(0, os.path.dirname(__file__))
import alt_figures as A  # noqa: E402
from make_figures import BLUE, GRAY, INK, VERMILION, con, matplotlib, np, plt  # noqa: E402
from v2_common import ORANGE, SETTLED, SKY, V2, place_labels, save, swatch_label, write_csv  # noqa: E402
from v2_f78 import slug_abbr, slug_of  # noqa: E402
from v2_panels import REFERENCE  # noqa: E402

A.SETTLED = SETTLED
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)
L = matplotlib.lines.Line2D
FIRST_BY = 2017
FIRST, SECOND = BLUE, ORANGE


def clean(name):
    return name.replace(" (Basel)", "").replace(" (Lausanne)", "")


LEGEND = [L([], [], color=BLUE, linewidth=1.5, label="All citable items"), L([], [], color=VERMILION, linewidth=1.5, label="Research articles only"),
          matplotlib.patches.Patch(color=SKY, label="Research papers"), matplotlib.patches.Patch(color=ORANGE, label="Reviews")]


def pair(fig, spec_rate, spec_vol, slug, ylabels, csv_rows):
    """One journal: its rates above its research papers and reviews per year."""
    s = A.series(slug)
    name = slug_abbr.get(slug, slug)
    ax = fig.add_subplot(spec_rate)
    ax.fill_between(s["x"], s["res"], s["all"], where=s["all"] >= s["res"], color=BLUE, alpha=0.15, linewidth=0)
    ax.plot(s["x"], s["all"], color=BLUE, linewidth=1.2)
    ax.plot(s["x"], s["res"], color=VERMILION, linewidth=1.2)
    last = np.flatnonzero(~np.isnan(s["all"] / s["res"]))
    lift = s["all"][last[-1]] / s["res"][last[-1]] - 1 if len(last) else float("nan")
    ax.set_title(name, loc="left", fontsize=7, pad=9)
    ax.text(0, 1.01, f"{lift:+.0%} vs research only".replace("-", "−"), transform=ax.transAxes, fontsize=5.5, color="#666666", va="bottom")
    ax.set_ylim(0, None)
    ax.set_xlim(2012, 2026)
    ax.set_xticks([2015, 2025], ["", ""])
    ax.tick_params(labelsize=5.8, pad=1)
    bx = fig.add_subplot(spec_vol)
    yrs = [y for y in sorted(s["pub"]) if 2012 <= y <= 2025]
    res = np.array([s["pub"][y].get("research", 0) for y in yrs])
    rev = np.array([s["pub"][y].get("review", 0) for y in yrs])
    bx.bar(yrs, res, color=SKY, width=0.8)
    bx.bar(yrs, rev, bottom=res, color=ORANGE, width=0.8)
    bx.set_xlim(2011.3, 2026)
    bx.set_xticks([2015, 2025])
    bx.tick_params(labelsize=5.8, pad=1)
    bx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 10000 else f"{v:,.0f}"))
    bx.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
    share = rev[-3:].sum() / max((res[-3:] + rev[-3:]).sum(), 1)
    bx.set_ylim(0, (res + rev).max() * 1.32)
    bx.text(0.02, 0.99, f"reviews {share:.0%}", transform=bx.transAxes, fontsize=5.3, color=INK, va="top")
    if ylabels:
        ax.set_ylabel("24-month rate", fontsize=6)
        bx.set_ylabel("Papers per year", fontsize=6)
    csv_rows += [[name, m, round(a, 3), round(r, 3)] for m, a, r in zip(s["months"], s["all"], s["res"]) if m.endswith("-11")]


def outliers(rows):
    first = dict(con.execute("SELECT j.slug, MIN(p.pub_year) FROM papers p JOIN journals j ON j.id = p.journal_id WHERE p.pub_year >= 1950 GROUP BY 1"))
    lift = np.array([float(r["lift_from_reviews"]) for r in rows])
    share = np.array([float(r["review_share_items"]) for r in rows])
    fit = np.polyfit(share, lift, 1)
    res = lift - np.polyval(fit, share)
    old = np.array([first.get(r["slug"], 2026) <= FIRST_BY for r in rows])
    order = np.argsort(res)
    below = [i for i in order if old[i]][:3]
    above = [i for i in order[::-1] if old[i]][:3]
    return [rows[i]["slug"] for i in above + below], res


def overlay(fig, spec_rate, spec_vol, a, b, ylabels, csv_rows):
    """One journal pair: both 24-month rates on one axis, above both journals' citable items per year."""
    sa, sb = A.series(slug_of[a]), A.series(slug_of[b])
    ax = fig.add_subplot(spec_rate)
    ax.plot(sa["x"], sa["all"], color=FIRST, linewidth=1.3)
    ax.plot(sb["x"], sb["all"], color=SECOND, linewidth=1.3)
    ax.set_ylim(0, None)
    ax.set_xlim(2012, 2026)
    ax.set_xticks([2015, 2025], ["", ""])
    ax.tick_params(labelsize=5.8, pad=1)
    swatch_label(ax, 1.2, clean(a), FIRST, fontsize=5.6 if len(clean(a)) > 17 else 6.3)
    swatch_label(ax, 1.06, clean(b), SECOND, fontsize=5.6 if len(clean(b)) > 17 else 6.3)
    bx = fig.add_subplot(spec_vol)
    yrs = list(range(2012, 2026))
    va = np.array([sum(sa["pub"].get(y, {}).get(k, 0) for k in ("research", "review", "case_report", "guideline")) for y in yrs])
    vb = np.array([sum(sb["pub"].get(y, {}).get(k, 0) for k in ("research", "review", "case_report", "guideline")) for y in yrs])
    bx.bar(np.array(yrs) - 0.21, va, color=FIRST, width=0.42)
    bx.bar(np.array(yrs) + 0.21, vb, color=SECOND, width=0.42)
    bx.set_xlim(2011.3, 2026)
    bx.set_xticks([2015, 2025])
    bx.tick_params(labelsize=5.8, pad=1)
    bx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 10000 else f"{v:,.0f}"))
    bx.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
    if ylabels:
        ax.set_ylabel("24-month rate", fontsize=6)
        bx.set_ylabel("Citable items\nper year", fontsize=6)
    for name, s in ((a, sa), (b, sb)):
        csv_rows += [[name, m, round(v, 3)] for m, v in zip(s["months"], s["all"]) if m.endswith("-11")]
    for y, x, z in zip(yrs, va, vb):
        csv_rows.append([f"{a} / {b}", y, f"{x} / {z}"])
    return float(np.nanmean(sa["all"][-12:])), float(np.nanmean(sb["all"][-12:])), int(va[-3:].sum() / 3), int(vb[-3:].sum() / 3)


def head(fig, ax, text):
    fig.text(0.125, ax.get_position().y1 + 0.032, text, fontsize=8.5, va="bottom")


def foot(fig, ax, handles, ncol):
    fig.legend(handles=handles, loc="center", bbox_to_anchor=(0.5, ax.get_position().y0 - 0.03), ncol=ncol, fontsize=6, frameon=False, handlelength=1.4)


def main():
    rows = list(csv.DictReader(open(os.path.join(V2, "data", "f7ab_lift_all_journals.csv"))))
    picks, res = outliers(rows)
    for slug in picks:
        if len(slug_abbr.get(slug, slug)) > 30:
            slug_abbr[slug] = slug_abbr[slug].split()[0]
    lift = np.array([float(r["lift_from_reviews"]) for r in rows])
    share = np.array([float(r["review_share_items"]) for r in rows])
    by = {r["slug"]: (float(r["lift_from_reviews"]), float(r["review_share_items"])) for r in rows}
    fig = plt.figure(figsize=(7.2, 11.4))
    gs = fig.add_gridspec(4, 1, hspace=0.62, height_ratios=[1.25, 0.62, 0.62, 0.62])
    top = gs[0].subgridspec(1, 2, wspace=0.32)

    # A
    ax = fig.add_subplot(top[0])
    ax.hist(np.clip(lift, -0.5, 1.5), bins=np.arange(-0.5, 1.55, 0.05), color=GRAY, edgecolor="white", linewidth=0.3)
    ymax = ax.get_ylim()[1]
    ref = {a: by[slug_of[a]][0] for a in REFERENCE}
    for k, (v, n) in enumerate(sorted((v, a) for a, v in ref.items())):
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

    # B
    ax = fig.add_subplot(top[1])
    TOP = 2.3
    ax.scatter(share, np.minimum(lift, TOP), s=4, color=BLUE, alpha=0.3, linewidth=0)
    pts, named = [], []
    for slug in picks:
        l_, s_ = by[slug]
        a = slug_abbr.get(slug, slug)
        ax.scatter(s_, min(l_, TOP), s=13, color=BLUE, edgecolor="white", linewidth=0.4, zorder=3)
        pts.append((s_, min(l_, TOP), a + (f" ({l_:+.0%})" if l_ > TOP else "")))
        named.append([a, round(l_, 4), round(s_, 4)])
    write_csv("f7b_named", ["journal", "lift", "review_share"], named)
    ax.set_xlim(0, 0.72); ax.set_ylim(-0.5, 2.5)
    corners = ((0.03, 0.97, "left", "top", "Few reviews,\nhighly cited"), (0.97, 0.97, "right", "top", "Many reviews,\nhighly cited"),
               (0.97, 0.03, "right", "bottom", "Many reviews,\nless cited"), (0.03, 0.03, "left", "bottom", "Few reviews,\nless cited"))
    for x, y, ha, va, t in corners:
        ax.text(x, y, t, transform=ax.transAxes, ha=ha, va=va, fontsize=6, color=INK, fontweight="bold")
    keep = [(a_, b_) for a_ in (0.02, 0.06, 0.1, 0.14) for b_ in (2.2, 2.35, -0.3, -0.42)] + [(a_, b_) for a_ in (0.56, 0.6, 0.64, 0.68) for b_ in (2.2, 2.35, -0.3, -0.42)]
    place_labels(ax, pts, fontsize=5.6, avoid=keep)
    ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Reviews as share of citable items")
    ax.set_ylabel("Lift over research-only rate")
    ax.set_title("B  Lift against the share of reviews", loc="left", fontsize=8.5)

    # C
    sub = gs[1].subgridspec(2, 6, hspace=0.3, wspace=0.5, height_ratios=[1, 0.62])
    out = []
    for c, slug in enumerate(picks):
        pair(fig, sub[0, c], sub[1, c], slug, c == 0, out)
        t = fig.axes[-2]._left_title
        t.set_fontsize(5.0 if len(t.get_text()) > 22 else 6.3)
    head(fig, fig.axes[-2], "C  The journals labelled in B")
    foot(fig, fig.axes[-1], LEGEND, 4)
    write_csv("f7c_rates_november", ["journal", "month", "rate_all_citable", "rate_research"], out)

    # D
    P = list(csv.DictReader(open(os.path.join(V2, "data", "f8_pairs.csv"))))
    flag = [(r["first"], r["second"]) for r in P if r["kind"] == "flagship"]
    sub = gs[2].subgridspec(2, len(flag), hspace=0.3, wspace=0.5, height_ratios=[1, 0.62])
    out, summary = [], []
    for c, (a, b) in enumerate(flag):
        summary.append(["flagship", a, b, *overlay(fig, sub[0, c], sub[1, c], a, b, c == 0, out)])
    head(fig, fig.axes[-2], "D  Flagships and their open-access siblings")
    foot(fig, fig.axes[-1], [matplotlib.patches.Patch(color=FIRST, label="Flagship"), matplotlib.patches.Patch(color=SECOND, label="Open-access sibling")], 2)

    # E
    S = list(csv.DictReader(open(os.path.join(V2, "data", "f8b_pairs.csv"))))[:6]     # already ranked by the high-volume journal's reviews
    sub = gs[3].subgridspec(2, len(flag), hspace=0.3, wspace=0.5, height_ratios=[1, 0.62])
    for c, r in enumerate(S):
        summary.append(["society", r["society_journal"], r["high_volume_journal"], *overlay(fig, sub[0, c], sub[1, c], r["society_journal"], r["high_volume_journal"], c == 0, out)])
    write_csv("f7de_pair_rates", ["journal", "month_or_year", "rate_or_items"], out)
    write_csv("f7de_pair_summary", ["kind", "first", "second", "first_rate_last_12", "second_rate_last_12", "first_items_per_year_2023_25", "second_items_per_year_2023_25"], summary)
    head(fig, fig.axes[-2], "E  Society journals and high-volume open-access journals")
    foot(fig, fig.axes[-1], [matplotlib.patches.Patch(color=FIRST, label="Society journal"), matplotlib.patches.Patch(color=SECOND, label="High-volume journal")], 2)
    print(summary, flush=True)
    save(fig, "F7_reviews")


if __name__ == "__main__":
    main()
