"""v5 order: main Figures 1 and 2 and Supplementary Figure S4.

Figure 1  the volume story: largest journals, publishers' share, and eight publishers stacked by tier
Figure 2  reviews: how much non-research items raise rates, reviews by publisher, and journal pairs

Each publisher has one color in every panel, with lighter tints for its tiers. Flagships are black.

Usage: python 10-31-26/scripts/v5_fig12.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import sys

os.environ["FIG_DIR"] = "v5"
sys.path.insert(0, os.path.dirname(__file__))
import more_figures as M  # noqa: E402
import v3_f7 as N  # noqa: E402
from make_figures import BLUE, GRAY, GREEN, INK, MUTED, PURPLE, VERMILION, con, dc, jid, matplotlib, np, plt, py, slug2id  # noqa: E402
from v2_common import ORANGE, ROOT, SKY, V2, place_labels, save, swatch_label, write_csv  # noqa: E402

abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
name_of = dict(con.execute("SELECT id, name FROM journals"))
YEARS, citable = M.YEARS, M.citable
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)
PUBLISHERS = [("Elsevier", GRAY), ("MDPI", ORANGE), ("Nature Portfolio", VERMILION), ("Frontiers", GREEN), ("Cureus", PURPLE), ("PLOS", BLUE), ("Hindawi", SKY)]
THOUSANDS = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v else "0")
TINTS = (1, 0.8, 0.62, 0.46, 0.3)


def tint(color, f):
    r = np.array(matplotlib.colors.to_rgb(color))
    return tuple(1 - f * (1 - r))


def labels(ax, items, x, gap, fontsize=6.3):
    last = -1e18
    for y, text, col in sorted(items):
        yl = max(y, last + gap)
        ax.annotate(text, (x, y), xytext=(x + 1.0, yl), textcoords="data", fontsize=fontsize, va="center", color=INK,
                    arrowprops=dict(arrowstyle="-", color=col, linewidth=0.6, shrinkA=0, shrinkB=0, relpos=(0, 0.5)))
        last = yl


def year_axis(ax, right=9):
    ax.set_xlim(YEARS[0], YEARS[-1] + right)
    ax.set_xticks([2005, 2015, 2025])
    ax.set_ylim(0, None)


def panel_largest(ax):
    """The five largest journals by peak year, colored by publisher."""
    rows = list(csv.DictReader(open(os.path.join(ROOT, "10-31-26", "data", "fig6a_ranked.csv"))))
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["journal"]][int(r["year"])] = int(r["citable_items"])
    color = {"Sci Rep": VERMILION, "PLoS One": BLUE, "Cureus": PURPLE, "Heliyon": GRAY, "Int J Mol Sci": ORANGE}
    ends, out = [], []
    for j, c in color.items():
        ys = sorted(y for y in by[j] if y >= 2005)
        v = [by[j][y] for y in ys]
        ax.plot(ys, v, color=c, linewidth=1.8)
        ends.append((v[-1], j, c))
        out += [[j, y, n] for y, n in zip(ys, v)]
    write_csv("f1b_largest_journals", ["journal", "year", "citable_items"], out)
    labels(ax, ends, 2025, 2600)
    year_axis(ax, 7)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.yaxis.set_major_formatter(THOUSANDS)
    ax.set_ylabel("Citable items per year")
    ax.set_title("B  Largest journals in PubMed", loc="left", fontsize=8.5)


def panel_share(ax):
    tot = M.per_year(citable)
    ends, out = [], []
    for name, col in PUBLISHERS:
        v = M.per_year(citable & M.is_pub(name)) / tot
        ax.plot(YEARS, v, color=col, linewidth=1.8)
        ends.append((v[-1], name, col))
        out += [[name, int(y), round(float(s), 5)] for y, s in zip(YEARS, v)]
    write_csv("f1c_publisher_share", ["publisher", "year", "share_of_citable_items"], out)
    labels(ax, ends, YEARS[-1], 0.0125)
    year_axis(ax, 9)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Share of all citable items")
    ax.set_title("C  Publishers' share of PubMed", loc="left", fontsize=8.5)


def journals_of(name):
    m = citable & M.is_pub(name) & (py >= 2023) & (py <= 2025)
    u, k = np.unique(jid[m], return_counts=True)
    return [int(u[i]) for i in np.argsort(-k)]


def split_by_size(name, color):
    """A publisher without a flagship: its largest journal, the next four, and the rest."""
    m = citable & M.is_pub(name)
    j = journals_of(name)
    top, nxt = j[:1], j[1:5]
    a, b = M.per_year(m & np.isin(jid, top)), M.per_year(m & np.isin(jid, nxt))
    return [(abbr[top[0]].replace(" (Basel)", ""), a, tint(color, 1)), ("Next four journals", b, tint(color, 0.68)), ("All other journals", M.per_year(m) - a - b, tint(color, 0.38))]


def layers():
    nat = citable & M.is_pub("Nature Portfolio")
    tier = {int(j): M.nature_tier(M.jname[int(j)]) for j in np.unique(jid[nat])}
    of = lambda *ts: M.per_year(nat & np.isin(jid, [j for j, x in tier.items() if x in ts]))  # noqa: E731
    nature = [("Nature", of("Nature"), INK), ("Nature research, Nature Reviews", of("Nature-branded research", "Nature Reviews"), tint(VERMILION, TINTS[0])),
              ("Nat Commun", of("Nature Communications"), tint(VERMILION, TINTS[1])), ("Communications, npj, Sci Data", of("Communications, npj, Sci Data"), tint(VERMILION, TINTS[2])),
              ("Sci Rep", of("Scientific Reports"), tint(VERMILION, TINTS[3])), ("Society and partner journals", of("Society and partner journals"), tint(VERMILION, TINTS[4]))]
    cell = []
    for (t, slugs, _), f in zip(M.CELL_TIERS, (None, 1, 0.8, 0.6, 0.4)):
        cell.append((t, M.per_year(citable & np.isin(jid, [slug2id[s] for s in slugs if s in slug2id])), INK if f is None else tint(GRAY, f)))
    aaas = []
    for (t, slugs, _), c in zip(M.AAAS_TIERS, (INK, "#666666", "#BBBBBB")):
        aaas.append((t, M.per_year(citable & np.isin(jid, [slug2id[s] for s in slugs if s in slug2id])), c))
    plos = citable & M.is_pub("PLOS")
    one = M.per_year(plos & (jid == slug2id["plos-one"]))
    return [("Nature Portfolio", nature), ("Cell Press", cell), ("AAAS", aaas), ("PLOS", [("PLoS One", one, tint(BLUE, 1)), ("Other PLOS journals", M.per_year(plos) - one, tint(BLUE, 0.5))]),
            ("MDPI", split_by_size("MDPI", ORANGE)), ("Frontiers", split_by_size("Frontiers", GREEN)), ("Hindawi", split_by_size("Hindawi", SKY)),
            ("Cureus", [("Cureus", M.per_year(citable & M.is_pub("Cureus")), PURPLE)])]


def stack(ax, L, top=None):
    ax.stackplot(YEARS, [v for _, v, _ in L], colors=[c for *_, c in L], linewidth=0.2, edgecolor="white")
    ax.set_xlim(YEARS[0], YEARS[-1])
    ax.set_xticks([2005, 2015, 2025])
    ax.tick_params(labelsize=6.2, pad=1.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 1000 else f"{v:.0f}"))
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    ax.set_ylim(0, top)


def panel_everything(ax):
    """Every citable item in PubMed each year, stacked by publisher, with the fast growers on top."""
    order = [("Elsevier", GRAY), ("PLOS", BLUE), ("Nature Portfolio", VERMILION), ("Hindawi", SKY), ("Cureus", PURPLE), ("Frontiers", GREEN), ("MDPI", ORANGE)]
    tot = M.per_year(citable)
    vals = [M.per_year(citable & M.is_pub(n)) for n, _ in order]
    rest = tot - sum(vals)
    ax.stackplot(YEARS, [rest] + vals, colors=["#DDDDDD"] + [c for _, c in order], linewidth=0.3, edgecolor="white")
    write_csv("f1a_pubmed_by_publisher", ["year", "all_other_publishers", *[n for n, _ in order], "total"],
              [[int(y), int(rest[i]), *[int(v[i]) for v in vals], int(tot[i])] for i, y in enumerate(YEARS)])
    base = 0
    ends = []
    for name, v, col in zip(["All other publishers"] + [n for n, _ in order], [rest] + vals, ["#DDDDDD"] + [c for _, c in order]):
        ends.append((base + v[-1] / 2, name, col))
        base += v[-1]
    labels(ax, ends, YEARS[-1], 62000, 7)
    ax.set_xlim(YEARS[0], YEARS[-1] + 4)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1e6:.1f}M" if v else "0"))
    ax.set_ylabel("Citable items per year")
    ax.set_title("A  Citable items in PubMed each year, by publisher", loc="left", fontsize=9.5)


def figure1():
    fig = plt.figure(figsize=(7.4, 12.0))
    gs = fig.add_gridspec(4, 1, hspace=0.3, height_ratios=[1.25, 1.0, 1.25, 1.25], left=0.085, right=0.985, top=0.98, bottom=0.03)
    panel_everything(fig.add_subplot(gs[0]))
    top = gs[1].subgridspec(1, 2, wspace=0.26)
    panel_largest(fig.add_subplot(top[0]))
    panel_share(fig.add_subplot(top[1]))
    pubs = layers()
    shared = max(sum(v for _, v, _ in L).max() for _, L in pubs) * 1.05
    out = []
    for k, (name, L) in enumerate(pubs):
        block = gs[2 + k // 4].subgridspec(2, 4, hspace=0.16, wspace=0.34, height_ratios=[1.32, 0.68])
        ax = fig.add_subplot(block[0, k % 4])
        stack(ax, L, sum(v for _, v, _ in L).max() * (1.2 + 0.075 * len(L)))
        ax.set_xticklabels([])
        ax.set_title(f"{'DEFGHIJK'[k]}  {name}", loc="left", fontsize=8.2, pad=3)
        ax.legend(handles=[matplotlib.patches.Patch(color=c, label=t) for t, _, c in L][::-1], fontsize=4.9, loc="upper left", handlelength=0.9, handleheight=0.7, labelspacing=0.12, borderpad=0, borderaxespad=0.2, frameon=False)
        bx = fig.add_subplot(block[1, k % 4])
        stack(bx, L, shared)
        if k % 4 == 0:
            ax.set_ylabel("Citable items\nper year", fontsize=6.3)
            bx.set_ylabel("Same scale", fontsize=6.3)
        out += [[name, t, int(y), int(n)] for t, v, _ in L for y, n in zip(YEARS, v)]
    write_csv("f1dk_publisher_tiers", ["publisher", "tier", "year", "citable_items"], out)
    save(fig, "Fig1_publishing")


def reviews_counts(ax):
    ends, out = [], []
    for name, col in PUBLISHERS:
        v = M.per_year(citable & M.is_pub(name) & (dc == 1))
        ax.plot(YEARS, v, color=col, linewidth=1.5)
        ends.append((v[-1], name, col))
        out += [[name, int(y), int(n)] for y, n in zip(YEARS, v)]
    write_csv("f2c_reviews_by_publisher", ["publisher", "year", "reviews"], out)
    labels(ax, ends, YEARS[-1], 2600, 5.8)
    year_axis(ax, 13)
    ax.yaxis.set_major_formatter(THOUSANDS)
    ax.set_ylabel("Reviews per year")
    ax.set_title("C  Reviews, by publisher", loc="left", fontsize=8.5)


def reviews_share(ax):
    ends, out = [], []
    for name, col in PUBLISHERS:
        m = citable & M.is_pub(name)
        n, r = M.per_year(m), M.per_year(m & (dc == 1))
        v = np.where(n >= 500, r / np.maximum(n, 1), np.nan)
        ax.plot(YEARS, v, color=col, linewidth=1.5)
        ends.append((v[-1], name, col))
        out += [[name, int(y), round(float(s), 4)] for y, s in zip(YEARS, v) if s == s]
    allr = M.per_year(citable & (dc == 1)) / M.per_year(citable)
    ax.plot(YEARS, allr, color=INK, linewidth=1.5)
    ends.append((allr[-1], "All journals", INK))
    write_csv("f2d_review_share", ["publisher", "year", "share"], out)
    labels(ax, ends, YEARS[-1], 0.031, 5.8)
    year_axis(ax, 13)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Share of citable items")
    ax.set_title("D  Reviews as a share of items", loc="left", fontsize=8.5)


def reviews_top_journal(ax):
    """Each publisher's journal with the most reviews in 2023-25, in the publisher's color."""
    ends, out = [], []
    for name, col in PUBLISHERS:
        m = citable & M.is_pub(name) & (dc == 1)
        r = m & (py >= 2023) & (py <= 2025)
        u, k = np.unique(jid[r], return_counts=True)
        j = int(u[np.argmax(k)])
        v = M.per_year(m & (jid == j))
        lab = abbr[j].replace(" (Basel)", "").replace(" (Lausanne)", "")
        ax.plot(YEARS, v, color=col, linewidth=1.5)
        ends.append((v[-1], lab, col))
        out += [[name, lab, int(y), int(n)] for y, n in zip(YEARS, v)]
    write_csv("f2e_top_review_journals", ["publisher", "journal", "year", "reviews"], out)
    labels(ax, ends, YEARS[-1], 310, 5.8)
    year_axis(ax, 15)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.1f}k" if v else "0"))
    ax.set_ylabel("Reviews per year")
    ax.set_title("E  Each publisher's top journal", loc="left", fontsize=8.5)


def overlay(fig, spec_rate, spec_vol, a, b, ylabels, rows):
    """A journal pair: rates for all citable items (solid) and research only (dashed), above research and reviews per year."""
    sa, sb = N.A.series(N.slug_of[a]), N.A.series(N.slug_of[b])
    ax = fig.add_subplot(spec_rate)
    for s, c in ((sa, BLUE), (sb, ORANGE)):
        ax.plot(s["x"], s["all"], color=c, linewidth=1.2)
        ax.plot(s["x"], s["res"], color=c, linewidth=0.9, linestyle=(0, (2.5, 1.5)))
    ax.set_ylim(0, None)
    ax.set_xlim(2012, 2026)
    ax.set_xticks([2015, 2025], ["", ""])
    ax.tick_params(labelsize=5.8, pad=1)
    swatch_label(ax, 1.2, N.clean(a), BLUE, fontsize=5.6 if len(N.clean(a)) > 17 else 6.3)
    swatch_label(ax, 1.06, N.clean(b), ORANGE, fontsize=5.6 if len(N.clean(b)) > 17 else 6.3)
    bx = fig.add_subplot(spec_vol)
    yrs = np.arange(2012, 2026)
    for s, c, dx in ((sa, BLUE, -0.21), (sb, ORANGE, 0.21)):
        res = np.array([s["pub"].get(int(y), {}).get("research", 0) for y in yrs])
        rev = np.array([s["pub"].get(int(y), {}).get("review", 0) for y in yrs])
        bx.bar(yrs + dx, res, color=c, width=0.42)
        bx.bar(yrs + dx, rev, bottom=res, color=tint(c, 0.42), width=0.42)
        rows += [[a if c == BLUE else b, int(y), int(p), int(q)] for y, p, q in zip(yrs, res, rev)]
    bx.set_xlim(2011.3, 2026)
    bx.set_xticks([2015, 2025])
    bx.tick_params(labelsize=5.8, pad=1)
    bx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 10000 else f"{v:,.0f}"))
    bx.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
    if ylabels:
        ax.set_ylabel("24-month rate", fontsize=6)
        bx.set_ylabel("Papers per year", fontsize=6)


def pair_legend(fig, ax, first, second):
    L, Pt = matplotlib.lines.Line2D, matplotlib.patches.Patch
    handles = [L([], [], color=MUTED, linewidth=1.2, label="All citable items"), L([], [], color=MUTED, linewidth=0.9, linestyle=(0, (2.5, 1.5)), label="Research only"),
               Pt(color=BLUE, label=f"{first}: research"), Pt(color=tint(BLUE, 0.42), label="reviews"), Pt(color=ORANGE, label=f"{second}: research"), Pt(color=tint(ORANGE, 0.42), label="reviews")]
    fig.legend(handles=handles, loc="center", bbox_to_anchor=(0.5, ax.get_position().y0 - 0.026), ncol=6, fontsize=5.8, frameon=False, handlelength=1.4, columnspacing=1.0)


def figure2():
    rows = list(csv.DictReader(open(os.path.join(V2, "data", "f7ab_lift_all_journals.csv"))))
    picks, _ = N.outliers(rows)
    lift = np.array([float(r["lift_from_reviews"]) for r in rows])
    share = np.array([float(r["review_share_items"]) for r in rows])
    by = {r["slug"]: (float(r["lift_from_reviews"]), float(r["review_share_items"])) for r in rows}
    fig = plt.figure(figsize=(7.2, 12.2))
    gs = fig.add_gridspec(4, 1, hspace=0.68, height_ratios=[1.15, 0.85, 0.72, 0.72])
    top = gs[0].subgridspec(1, 2, wspace=0.32)
    ax = fig.add_subplot(top[0])
    ax.hist(np.clip(lift, -0.5, 1.5), bins=np.arange(-0.5, 1.55, 0.05), color=GRAY, edgecolor="white", linewidth=0.3)
    ymax = ax.get_ylim()[1]
    for k, (v, n) in enumerate(sorted((by[N.slug_of[a]][0], a) for a in N.REFERENCE)):
        y = ymax * (1.06 + 0.1 * k)
        ax.plot([v, v], [0, y], color=BLUE, linewidth=0.7)
        ax.text(v + 0.02, y, f"{n} {v:+.0%}".replace("-", "−"), fontsize=5.8, color=INK, va="center")
    best = int(np.argmax(lift))
    name = N.slug_abbr.get(rows[best]["slug"], rows[best]["journal"])
    ax.plot([1.47, 1.47], [0, ymax * 0.42], color=INK, linewidth=0.7)
    ax.text(1.45, ymax * 0.44, f"Highest:\n{name}\n{lift[best]:+.0%} (off the axis)", fontsize=5.8, color=INK, va="bottom", ha="right")
    ax.set_ylim(0, ymax * 1.95)
    ax.set_yticks([t for t in ax.get_yticks() if t <= ymax])
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("Rate with all citable items, compared with research only")
    ax.set_ylabel("Journals")
    ax.set_title("A  How much non-research items raise the rate", loc="left", fontsize=8.5)

    ax = fig.add_subplot(top[1])
    TOP = 2.3
    ax.scatter(share, np.minimum(lift, TOP), s=4, color=BLUE, alpha=0.3, linewidth=0)
    pts = []
    for slug in picks:
        l_, s_ = by[slug]
        ax.scatter(s_, min(l_, TOP), s=13, color=BLUE, edgecolor="white", linewidth=0.4, zorder=3)
        lab = N.slug_abbr.get(slug, slug)
        pts.append((s_, min(l_, TOP), lab.split()[0] if len(lab) > 30 else lab))
    ax.set_xlim(0, 0.72); ax.set_ylim(-0.5, 2.5)
    for x, y, ha, va, t in ((0.03, 0.97, "left", "top", "Few reviews,\nhighly cited"), (0.97, 0.97, "right", "top", "Many reviews,\nhighly cited"),
                            (0.97, 0.03, "right", "bottom", "Many reviews,\nless cited"), (0.03, 0.03, "left", "bottom", "Few reviews,\nless cited")):
        ax.text(x, y, t, transform=ax.transAxes, ha=ha, va=va, fontsize=6, color=INK, fontweight="bold")
    keep = [(a_ / 100, b_ / 100) for a_ in range(2, 20, 2) for b_ in (215, 225, 235, 245, -25, -33, -41)] + [(a_ / 100, b_ / 100) for a_ in range(50, 71, 2) for b_ in (215, 225, 235, 245, -25, -33, -41)]
    place_labels(ax, pts, fontsize=5.6, avoid=keep)
    ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Reviews as share of citable items")
    ax.set_ylabel("Rise over research-only rate")
    ax.set_title("B  That rise against the share of reviews", loc="left", fontsize=8.5)

    mid = gs[1].subgridspec(1, 3, wspace=0.46)
    reviews_counts(fig.add_subplot(mid[0]))
    reviews_share(fig.add_subplot(mid[1]))
    reviews_top_journal(fig.add_subplot(mid[2]))

    P = list(csv.DictReader(open(os.path.join(V2, "data", "f8_pairs.csv"))))
    flag = [(r["first"], r["second"]) for r in P if r["kind"] == "flagship"]
    sub = gs[2].subgridspec(2, 6, hspace=0.3, wspace=0.5, height_ratios=[1, 0.62])
    out = []
    for c, (a, b) in enumerate(flag):
        overlay(fig, sub[0, c], sub[1, c], a, b, c == 0, out)
    N.head(fig, fig.axes[-2], "F  Flagships and their open-access siblings")
    pair_legend(fig, fig.axes[-1], "Flagship", "Sibling")
    S = list(csv.DictReader(open(os.path.join(V2, "data", "f8b_pairs.csv"))))[:6]
    sub = gs[3].subgridspec(2, 6, hspace=0.3, wspace=0.5, height_ratios=[1, 0.62])
    for c, r in enumerate(S):
        overlay(fig, sub[0, c], sub[1, c], r["society_journal"], r["high_volume_journal"], c == 0, out)
    N.head(fig, fig.axes[-2], "G  Society journals and high-volume open-access journals")
    pair_legend(fig, fig.axes[-1], "Society", "High-volume")
    write_csv("f2fg_pair_papers", ["journal", "year", "research", "reviews"], out)
    save(fig, "Fig2_reviews")

    # Supplementary Figure S4: the six journals named in panel B
    fig = plt.figure(figsize=(7.2, 2.9))
    sub = fig.add_gridspec(2, 6, hspace=0.3, wspace=0.5, height_ratios=[1, 0.62], top=0.84, bottom=0.17)
    out = []
    for slug in picks:
        if len(N.slug_abbr.get(slug, slug)) > 30:
            N.slug_abbr[slug] = N.slug_abbr[slug].split()[0]
    for c, slug in enumerate(picks):
        N.pair(fig, sub[0, c], sub[1, c], slug, c == 0, out)
        t = fig.axes[-2]._left_title
        t.set_fontsize(5.0 if len(t.get_text()) > 22 else 6.3)
    fig.legend(handles=N.LEGEND, loc="lower center", ncol=4, fontsize=6, frameon=False, handlelength=1.4)
    save(fig, "S4_outlier_journals")


if __name__ == "__main__":
    figure1()
    figure2()
