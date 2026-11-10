"""F9: publishing landscape (figure_revision_plan.md, Task 9). Replaces Fig 6.

A ranked largest journals; B publishers' share; C reviews by publisher; D top 10 journals by reviews published, any publisher;
E-G publisher tiers on their own scales; H-J the same tiers on one shared scale. The article-fee panel is left out: the
publishers' own 2024 prices could not be confirmed, which was the condition for keeping it.

Usage: python 10-31-26/scripts/v2_f9.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import more_figures as M  # noqa: E402
from make_figures import BLUE, GRAY, GREEN, INK, MUTED, PURPLE, VERMILION, con, dc, jid, matplotlib, np, plt, py, slug2id  # noqa: E402
from v2_common import ORANGE, ROOT, SKY, save, write_csv  # noqa: E402

abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
YEARS, citable = M.YEARS, M.citable
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)


def panel_a(ax):
    rows = list(csv.DictReader(open(os.path.join(ROOT, "10-31-26", "data", "fig6a_ranked.csv"))))
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["journal"]][int(r["year"])] = int(r["citable_items"])
    colors = [VERMILION, BLUE, GREEN, ORANGE, PURPLE, SKY]
    order = sorted(by, key=lambda j: -max(by[j].values()))
    ends = []
    for j, c in zip(order, colors):
        ys = sorted(y for y in by[j] if y >= 2005)
        v = [by[j][y] for y in ys]
        ax.plot(ys, v, color=c, linewidth=1.6)
        ends.append((v[-1], j.replace("Int J Environ Res Public Health", "Int J Environ\nRes Public Health"), c))
    M.spread_labels(ax, ends, 2025, 3400)
    ax.set_xlim(2005, 2032)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    ax.set_ylabel("Citable items per year")
    ax.set_ylim(0, None)
    ax.set_title("A  Largest journals", loc="left", fontsize=8.5)


def panel_b(ax, rows):
    tot = M.per_year(citable)
    ends = []
    for name, col in M.OA_PUBS:
        v = M.per_year(citable & M.is_pub(name)) / tot
        ax.plot(YEARS, v, color=col, linewidth=1.6)
        ends.append((v[-1], name, col))
        rows += [["B", name, int(y), round(float(s), 5)] for y, s in zip(YEARS, v)]
    M.spread_labels(ax, ends, YEARS[-1], 0.006)
    ax.set_xlim(YEARS[0], YEARS[-1] + 7)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Share of all citable items")
    ax.set_title("B  Open-access publishers' share of PubMed", loc="left", fontsize=8.5)


def panel_c(ax, rows):
    tot = M.per_year(citable)
    ends = []
    for name, col in M.OA_PUBS[:4] + [("Elsevier", GRAY)]:
        m = citable & M.is_pub(name)
        n, r = M.per_year(m), M.per_year(m & (dc == 1))
        v = np.where(n >= 500, r / np.maximum(n, 1), np.nan)
        ax.plot(YEARS, v, color=col, linewidth=1.6)
        ends.append((v[-1], name, col))
        rows += [["C", name, int(y), round(float(s), 4)] for y, s in zip(YEARS, v) if s == s]
    allr = M.per_year(citable & (dc == 1)) / tot
    ax.plot(YEARS, allr, color=INK, linewidth=1.2, linestyle="--")
    ends.append((allr[-1], "All journals", INK))
    M.spread_labels(ax, ends, YEARS[-1], 0.025)
    ax.set_xlim(YEARS[0], YEARS[-1] + 7)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Reviews as share of citable items")
    ax.set_title("C  Reviews, by publisher", loc="left", fontsize=8.5)


def panel_d(ax, rows):
    m = citable & (py >= 2023) & (py <= 2025)
    n = np.bincount(jid[m])
    r = np.bincount(jid[m & (dc == 1)], minlength=len(n))
    top = np.argsort(-r)[:10]
    yy = np.arange(10)[::-1]
    label = []
    for y, j in zip(yy, top):
        pubs = np.bincount(M.pub[m & (jid == j)].astype(np.int64) + 1)
        name = M.PUB_NAMES[int(np.argmax(pubs)) - 1]
        label.append(f"{abbr[int(j)].replace(' (Basel)', '').replace(' (Lausanne)', '')} ({name})")
        ax.hlines(y, 0, r[j], color="#BBBBBB", linewidth=1)
        ax.scatter(r[j], y, s=20, color=BLUE, zorder=3, edgecolor="white", linewidth=0.4)
        ax.text(r[j] + 500, y, f"{r[j] / n[j]:.0%} of its {n[j]:,} items", fontsize=5.6, color=MUTED, va="center")
        rows.append(["D", abbr[int(j)], name, int(r[j]), int(n[j]), round(float(r[j] / n[j]), 4)])
    ax.set_yticks(yy, label, fontsize=6)
    ax.set_xlim(0, r[top[0]] * 1.6)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Reviews published, 2023–25")
    ax.set_title("D  Journals publishing the most reviews", loc="left", fontsize=8.5, x=-0.95)


def tier_layers():
    nat = citable & M.is_pub("Nature Portfolio")
    tier_of = {int(j): M.nature_tier(M.jname[int(j)]) for j in np.unique(jid[nat])}
    out = [("Nature Portfolio", [(t, M.per_year(nat & np.isin(jid, [j for j, x in tier_of.items() if x == t])), c) for t, c in M.NATURE_TIERS])]
    for fam, tiers in (("Cell Press", M.CELL_TIERS), ("AAAS", M.AAAS_TIERS)):
        out.append((fam, [(t, M.per_year(citable & np.isin(jid, [slug2id[s] for s in slugs if s in slug2id])), col) for t, slugs, col in tiers]))
    return out


def main():
    rows = []
    fig = plt.figure(figsize=(7.2, 11.2))
    gs = fig.add_gridspec(4, 6, height_ratios=[1.1, 1, 0.9, 0.9], hspace=0.5, wspace=1.4)
    panel_a(fig.add_subplot(gs[0, :3]))
    panel_b(fig.add_subplot(gs[0, 3:]), rows)
    panel_c(fig.add_subplot(gs[1, :3]), rows)
    panel_d(fig.add_subplot(gs[1, 4:]), rows)
    layers = tier_layers()
    top = max(sum(v for _, v, _ in L).max() for _, L in layers) * 1.05
    for k, (fam, L) in enumerate(layers):
        M.stacked(fig.add_subplot(gs[2, 2 * k:2 * k + 2]), L, f"{'EFG'[k]}  {fam}")
        ax = fig.add_subplot(gs[3, 2 * k:2 * k + 2])
        M.stacked(ax, L, f"{'HIJ'[k]}  {fam}, shared scale")
        ax.get_legend().remove()
        ax.set_ylim(0, top)
        rows += [["EFG"[k], t, int(y), int(n)] for t, v, _ in L for y, n in zip(YEARS, v)]
        if k == 0:
            ax.set_ylabel("Citable items per year")
            fig.axes[-2].set_ylabel("Citable items per year")
    write_csv("f9_landscape", ["panel", "series", "year_or_publisher", "value", "extra", "extra2"], rows)
    save(fig, "F9_landscape")


if __name__ == "__main__":
    main()
