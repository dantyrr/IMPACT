"""v5 order: main Figure 3 and Supplementary Figure S3, from the v3 panels of F4 and F5.

Usage: python 10-31-26/scripts/v5_reliance.py   (from the IMPACT folder)
"""
import os
os.environ["FIG_DIR"] = "v5"
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import (BLUE, VERMILION, GREEN, GRAY, INK, MUTED, C, Y0, TREND, YEAR, concentration, con, dc, jid, jname, matplotlib, np, plt,  # noqa: E402
                          pmid, py, series_membership, slug2id, title, window)
from v2_common import ROOT, SKY, month_index, save, write_csv  # noqa: E402
from v2_panels import REFERENCE  # noqa: E402
from v2_shift import Journal, load_journal, FIRST, LAST, shifted_rates  # noqa: E402

OLD = os.path.join(ROOT, "10-31-26", "data")
abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
by_abbr = {v: k for k, v in abbr.items()}
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)
DASHED = (0, (3, 2))
IJS_FALL_ALL_15 = None


def lollipop(ax, y, v, color=BLUE):
    ax.hlines(y, 0, v, color="#BBBBBB", linewidth=1)
    ax.scatter(v, y, s=20, color=color, zorder=3, edgecolor="white", linewidth=0.4)


def grid_journals(sid):
    idx, c = window(YEAR)
    rem = (sid[idx] >= 0) | (dc[idx] == 3)
    J = jid[idx]
    n = J.max() + 1
    N, T = np.bincount(J, minlength=n), np.bincount(J, weights=c, minlength=n)
    Nr, Tr = np.bincount(J[rem], minlength=n), np.bincount(J[rem], weights=c[rem], minlength=n)
    ok = np.flatnonzero((N >= 100) & (T >= 500) & (N - Nr > 0))
    fall = 1 - ((T[ok] - Tr[ok]) / (N[ok] - Nr[ok])) / (T[ok] / N[ok])
    top = [int(ok[k]) for k in np.argsort(-fall)[:11]]
    fall_of = dict(zip(ok.tolist(), fall.tolist()))
    extra = [by_abbr["CA Cancer J Clin"]]
    ref = [by_abbr[a] for a in REFERENCE if by_abbr[a] not in top]
    picks = [(j, "largest falls") for j in top] + [(j, "extreme case, few items") for j in extra] + [(j, "reference") for j in ref]
    write_csv("f5d_grid_journals", ["journal", "why", "fall_2024"], [[abbr[j], w, round(fall_of.get(j, float("nan")), 4)] for j, w in picks])
    return picks, len(ok)


def rate_series(j, sid):
    J = load_journal(j)
    idx = np.flatnonzero((jid == j) & (dc <= 3))
    guides = set(pmid[idx[dc[idx] == 3]].tolist())
    both = guides | set(pmid[idx[sid[idx] >= 0]].tolist())
    out = {}
    for lab, drop in (("all", set()), ("no_guidelines", guides), ("no_guidelines_or_series", both)):
        items = {p: m for p, m in J.items.items() if p not in drop}
        out[lab] = shifted_rates(Journal(items, J.cited, J.when), [], 0)["rolling"]
    return out, len(guides), len(both)




def panel_hist(ax, r, share, med):
    ax.hist(share, bins=np.logspace(-3.3, 0, 45), color=GRAY, edgecolor="white", linewidth=0.5)
    ax.set_xscale("log")
    ax.set_xlabel(f"Share of a journal's 24-month rate from its single top paper, December {YEAR}")
    ax.set_ylabel("Journals")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0%}" if v >= 0.01 else f"{v:.1%}"))
    marks = ["Nat Commun", "Nature", "NEJM", "Cell", "Circulation", "CA Cancer J Clin"]
    top = ax.get_ylim()[1]
    for i, (x, n) in enumerate(sorted((r[by_abbr[m]]["top1"], m) for m in marks)):
        y = top * (1.04 + 0.1 * i)
        ax.plot([x, x], [0, y], color=BLUE, linewidth=0.8)
        ax.plot(x, y, "o", color=BLUE, markersize=4, markeredgecolor="white", markeredgewidth=0.6)
        ax.text(x, y * 1.03, f"{n} {x:.1%}", ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.set_ylim(0, top * 1.72)
    ax.set_yticks([t for t in ax.get_yticks() if t <= top])
    ax.set_title(f"A  Share of the 24-month rate from each journal's top paper, December {YEAR}", loc="left", fontsize=8.5)
    ax.text(0.02, 0.98, f"median {med:.1%}\n{(share >= .25).sum()} journals ≥25%\n{(share >= .5).sum()} journals ≥50%", transform=ax.transAxes, fontsize=7, color=INK, va="top")


def panels_with_without(fig, spec):
    middle = by_abbr["Cell"]
    for k, j in enumerate((by_abbr["CA Cancer J Clin"], middle, by_abbr["Nat Commun"])):
        ax = fig.add_subplot(spec[k])
        full, wo, years = [], [], []
        for Y in TREND:
            idx, c = window(Y, jid == j)
            if len(c) < 2 or c.sum() == 0:
                continue
            t = np.argmax(c)
            full.append(c.sum() / len(c)); wo.append((c.sum() - c[t]) / (len(c) - 1)); years.append(Y)
        ax.fill_between(years, wo, full, color=BLUE, alpha=0.15, linewidth=0)
        ax.plot(years, full, color=BLUE, linewidth=1.5, label="All citable items")
        ax.plot(years, wo, color=VERMILION, linewidth=1.5, label="Without the top paper")
        ax.set_title(("B  " if k == 0 else "") + abbr[j], loc="left", fontsize=8.5)
        ax.set_ylim(0, max(full) * 1.2)
        ax.set_xticks([2010, 2020])
        ax.tick_params(labelsize=7)
        if k == 0:
            ax.set_ylabel("24-month rate")
        if k == 2:
            ax.legend(fontsize=6, loc="lower right", handlelength=1.2)


def panel_reliant(ax, r):
    big = sorted(((v["top1"], k) for k, v in r.items() if v["items"] >= 500), reverse=True)[:8]
    labels, vals = [], []
    for sh, k in big:
        t = title(r[k]["top_pmid"])
        labels.append(f"{t[:44]}{'…' if len(t) > 44 else ''} ({abbr[k]})")
        vals.append(sh)
    yy = np.arange(len(vals))[::-1]
    ax.barh(yy, vals, color=VERMILION, height=0.68, edgecolor="white", linewidth=0.5)
    ax.barh(yy, [1 - v for v in vals], left=vals, color="#DDDDDD", height=0.68, edgecolor="white", linewidth=0.5)
    ax.set_yticks(yy, labels, fontsize=6)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlim(0, 1)
    for y, v in zip(yy, vals):
        ax.text(1.01, y, f"{v:.0%}", va="center", fontsize=5.8, color=MUTED)
    ax.set_xlabel(f"Top paper's share of the 24-month rate, December {YEAR}")
    ax.grid(axis="y", visible=False)
    ax.set_title("C  Journals most reliant on one paper (500+ citable items)", loc="left", fontsize=8.5, x=-1.0)


def panel_series(ax):
    S = list(csv.DictReader(open(os.path.join(OLD, "fig2a_recurring_series_merged.csv"))))
    yy = np.arange(len(S))[::-1]
    lollipop(ax, yy, [int(r["lifetime_citations"]) / 1000 for r in S])
    short = lambda t: t if len(t) <= 36 else t[:35] + "…"  # noqa: E731
    ax.set_yticks(yy, [f"{short(r['series'])} ({r['journal']})" for r in S], fontsize=5.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 240)
    ax.set_xlabel("Lifetime citations (thousands)")
    ax.set_title("D  Series: titles repeating year after year", loc="left", fontsize=8.5, x=-2.0)


def panel_guidelines(ax):
    G = list(csv.DictReader(open(os.path.join(OLD, "fig11_ranked_guidelines.csv"))))[:15]
    name2 = dict(con.execute("SELECT name, abbreviation FROM journals"))
    yy = np.arange(len(G))[::-1]
    lollipop(ax, yy, [-float(r["change"]) for r in G])
    ax.set_yticks(yy, [name2.get(r["journal"], r["journal"]) for r in G], fontsize=5.8)
    for y, r in zip(yy, G):
        ax.text(-float(r["change"]) + 0.04, y, f"{float(r['rate']):.1f} → {float(r['rate_without_guidelines']):.1f}", va="center", fontsize=5.4, color=MUTED)
    ax.set_xlim(0, 0.72)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Fall in 24-month rate")
    ax.set_title("E  Guidelines: items PubMed tags as guidelines", loc="left", fontsize=8.5, x=-0.75)


def rate_grid(fig, sub, picks, sid, cols, label):
    t0 = month_index(2012, 1)
    ts = list(range(t0, LAST + 1))
    x = [t / 12 for t in ts]
    for k, (j, why) in enumerate(picks):
        ax = fig.add_subplot(sub[k // cols, k % cols])
        r, ng, nb = rate_series(j, sid)
        a = [r["all"][t] for t in ts]
        b = [r["no_guidelines"][t] for t in ts]
        c = [r["no_guidelines_or_series"][t] for t in ts]
        ax.fill_between(x, c, a, color=BLUE, alpha=0.15, linewidth=0)
        ax.plot(x, a, color=BLUE, linewidth=1.2, label="All citable items")
        ax.plot(x, b, color=GREEN, linewidth=0.9, label="Without guidelines")
        ax.plot(x, c, color=VERMILION, linewidth=1.1, label="Without guidelines or series")
        ax.set_title(abbr[j].replace(" (Engl Ed)", ""), loc="left", fontsize=6.5, pad=2)
        if k == 0:
            ax.text(-0.2, 1.3, label, transform=ax.transAxes, fontsize=8.5)
        ax.set_ylim(0, np.nanmax(a) * 1.12)
        ax.set_xlim(2012, 2026)
        ax.set_xticks([2015, 2025])
        ax.tick_params(labelsize=5.6, pad=1)
        if k % cols == 0:
            ax.set_ylabel("24-month rate", fontsize=6)
    return ax


def series_summary(ax, picks, sid, label):
    years = list(range(2015, 2026))
    in_series = sid >= 0
    table = []
    for j, why in picks:
        v = []
        for Y in years:
            idx, c = window(Y, jid == j)
            if len(c) and c.sum():
                v.append((Y, c[in_series[idx]].sum() / c.sum()))
        table.append((abbr[j], float(np.mean([x for Y, x in v if Y >= 2021])), min(x for _, x in v), max(x for _, x in v), why))
    named = sorted((r for r in table if r[4] != "reference"), key=lambda r: r[1])
    refs = [r for r in table if r[4] == "reference"]
    rows = [("Reference journals (median)", float(np.median([r[1] for r in refs])), float(np.median([r[2] for r in refs])), float(np.median([r[3] for r in refs])), "reference")] + named
    yy = np.arange(len(rows))
    ax.hlines(yy, [r[2] for r in rows], [r[3] for r in rows], color=SKY, linewidth=2.6, zorder=1)
    ax.scatter([r[1] for r in rows], yy, s=20, color=BLUE, zorder=3, edgecolor="white", linewidth=0.4)
    ax.set_yticks(yy, [r[0].replace(" (Engl Ed)", "") for r in rows], fontsize=5.8)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share of citations")
    ax.set_title(label, loc="left", fontsize=8.5, x=-0.6)


def main():
    r = concentration(YEAR)
    share = np.array([v["top1"] for v in r.values()])
    med = float(np.median(share))
    sid, keys = series_membership()
    picks, eligible = grid_journals(sid)

    # Figure 2
    fig = plt.figure(figsize=(7.8, 12.0))
    gs = fig.add_gridspec(5, 1, left=0.08, right=0.97, top=0.975, bottom=0.05, hspace=0.54, height_ratios=[1.15, 0.72, 0.85, 1.25, 0.56])
    panel_hist(fig.add_subplot(gs[0]), r, share, med)
    panels_with_without(fig, gs[1].subgridspec(1, 3, wspace=0.28))
    panel_reliant(fig.add_subplot(gs[2].subgridspec(1, 2, width_ratios=[0.5, 0.5], wspace=0)[1]), r)
    row = gs[3].subgridspec(1, 4, wspace=0, width_ratios=[1.35, 0.62, 0.68, 0.72])
    panel_series(fig.add_subplot(row[1]))
    panel_guidelines(fig.add_subplot(row[3]))
    sub = gs[4].subgridspec(1, 5, wspace=0.3)
    ax = rate_grid(fig, sub, [p for p in picks if p[1] == "largest falls"][:5], sid, 5, "F  Rate with and without guidelines and series: the five largest falls")
    h, l = ax.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, 0.005))
    save(fig, "Fig3_few_papers")

    # Supplementary Figure S3
    fig = plt.figure(figsize=(7.8, 9.0))
    gs = fig.add_gridspec(2, 1, left=0.07, right=0.98, top=0.965, bottom=0.075, hspace=0.3, height_ratios=[0.6, 1.5])
    top = gs[0].subgridspec(1, 3, wspace=0, width_ratios=[1, 0.62, 1])
    ax = fig.add_subplot(top[0])
    rows = []
    for Y in TREND:
        a = np.array([v["top1"] for v in concentration(Y).values()])
        rows.append([Y, float(np.median(a)), float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))])
    yrs = [x[0] for x in rows]
    ax.fill_between(yrs, [x[2] for x in rows], [x[3] for x in rows], color=BLUE, alpha=0.15, linewidth=0, label="Middle 95% of journals")
    ax.plot(yrs, [x[1] for x in rows], color=BLUE, label="Median journal")
    ax.legend(fontsize=6, loc="upper left", handlelength=1.3)
    ax.set_ylim(0, None); ax.set_xlim(yrs[0], yrs[-1])
    ax.set_xticks([2010, 2015, 2020, 2025])
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Top paper's share of the rate")
    ax.set_xlabel("December reading")
    ax.set_title("A  Top paper's share, 2007–25", loc="left", fontsize=8.5)
    series_summary(fig.add_subplot(top[2]), picks, sid, "B  Citations going to recurring series")
    sub = gs[1].subgridspec(4, 5, hspace=0.5, wspace=0.3)
    ax = rate_grid(fig, sub, picks, sid, 5, "C  Rate with and without guidelines and series")
    h, l = ax.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, 0.01))
    save(fig, "S3_reliance_detail")


if __name__ == "__main__":
    main()
