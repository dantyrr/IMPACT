"""F2: do journals use timing? Replaces Fig 9 B-D and Fig 9E-G (figure_revision_plan.md, Task 4).

A   how much each journal's JIF gains from which papers land early in the year, 4,813 journals
B   the same, named journals: top and bottom 4 (2,000+ items, |z| >= 3) and the reference journals
C   reviews against other items published Jan-Mar, journals labelled by rank
D   what rotating each paper's month 6 or 9 later, in the same year, would do to those journals' JIF-counted citations
E   the month each big annual report comes out, sized by its citations in its first 24 months
F   the journal's rate in a report's biggest year if that one report had come out 0-11 months later
G   the same for a late-year paper moved earlier, in the four journals that lose most from timing

Usage: python 10-31-26/scripts/v2_f2.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import BLUE, VERMILION, GRAY, INK, MUTED, DATA, C, Y0, con, jid, matplotlib, np, plt, pm, pmid, py  # noqa: E402
from v2_common import ROOT, NAMES, ORANGE, month_index, place_labels, save, write_csv  # noqa: E402
from v2_panels import REFERENCE  # noqa: E402
from v2_shift import load_journal, shifted_rates  # noqa: E402
from v2_timing import rotated_change  # noqa: E402

OLD = os.path.join(ROOT, "10-31-26", "data")
by_abbr = {a: j for j, a in con.execute("SELECT id, abbreviation FROM journals")}
PCT = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%".replace("-", "−") if abs(v) > 1e-9 else "0%")


def read(name):
    with open(os.path.join(OLD, name)) as f:
        return list(csv.DictReader(f))


def panel_a(ax, T):
    g = np.array([float(r["placement_gain"]) * 100 for r in T])
    ax.hist(np.clip(g, -10, 10), bins=np.arange(-10, 10.5, 0.5), color=GRAY, edgecolor="white", linewidth=0.4)
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.text(0.98, 0.96, f"{len(g):,} journals\nmedian {np.median(g):+.2f}%\ngain 2%+: {(g >= 2).sum()}\nlose 2%+: {(g <= -2).sum()}".replace("-", "−"),
            transform=ax.transAxes, ha="right", va="top", fontsize=6.3, color=INK)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("JIF change from which papers land early")
    ax.set_ylabel("Journals")
    ax.set_title("A  JIF change from publication months, by journal", loc="left", fontsize=8.5)


def panel_b(ax, T):
    big = sorted((r for r in T if int(r["items_2014_21"]) >= 2000 and abs(float(r["placement_z"])) >= 3), key=lambda r: -float(r["placement_gain"]))
    by = {r["abbreviation"]: r for r in T}
    ends = {r["abbreviation"] for r in big[:4] + big[-4:]}
    groups = [("Largest gains", big[:4]), ("Reference journals", [by[a] for a in REFERENCE if a in by and a not in ends]), ("Largest losses", big[-4:])]
    rows, y, ticks, names = [], 0, [], []
    for lab, rs in groups:
        rs = sorted(rs, key=lambda r: -float(r["placement_gain"]))
        ax.text(-0.02, y - 0.1, lab, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=6.2, fontweight="bold", color=INK)
        y += 1
        for r in rs:
            v = float(r["placement_gain"]) * 100
            ax.plot([0, v], [y, y], color="#BBBBBB", linewidth=0.9, zorder=1)
            ax.scatter([v], [y], s=16, color=BLUE if lab == "Reference journals" else VERMILION, zorder=2, edgecolor="white", linewidth=0.4)
            ticks.append(y); names.append(r["abbreviation"])
            rows.append([lab, r["abbreviation"], r["items_2014_21"], round(v, 2), r["placement_z"]])
            y += 1
        y += 0.4
    write_csv("f2b_named_journals", ["group", "journal", "items_2014_21", "jif_change_pct", "z"], rows)
    ax.axvline(0, color=INK, linewidth=0.7)
    ax.set_yticks(ticks, names, fontsize=6)
    ax.set_ylim(y - 0.5, -0.7)
    ax.grid(axis="y", visible=False)
    ax.set_xticks([-8, -6, -4, -2, 0, 2, 4])
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("JIF change from which papers land early")
    ax.set_title("B  Largest JIF changes, and reference journals", loc="left", fontsize=8.5)


def review_ranks(T, n=6):
    """Journals with 100+ reviews and 100+ other items, significant at FDR 5%, ranked by the gap."""
    has = [r for r in T if r["reviews_fdr_q"] and int(r["reviews"]) >= 100 and int(r["items_2014_21"]) - int(r["reviews"]) >= 100]
    gap = lambda r: float(r["reviews_jan_mar"]) - float(r["other_jan_mar"])  # noqa: E731
    sig = [r for r in has if float(r["reviews_fdr_q"]) < 0.05]
    early = sorted((r for r in sig if gap(r) > 0), key=gap, reverse=True)[:n]
    late = sorted((r for r in sig if gap(r) < 0), key=gap)[:n]
    return early, late


def panel_c(ax, T, early, late):
    has = [r for r in T if r["reviews_fdr_q"]]
    ro = np.array([float(r["reviews_jan_mar"]) * 100 for r in has])
    oo = np.array([float(r["other_jan_mar"]) * 100 for r in has])
    ax.scatter(oo, ro, s=4, color=GRAY, alpha=0.3, linewidths=0)
    ax.plot([0, 100], [0, 100], color=INK, linewidth=0.7, linestyle=(0, (3.5, 2.5)))
    pts = []
    for rs, color in ((early, VERMILION), (late, BLUE)):
        for r in rs:
            x, y = float(r["other_jan_mar"]) * 100, float(r["reviews_jan_mar"]) * 100
            ax.scatter([x], [y], s=14, color=color, zorder=3, edgecolor="white", linewidth=0.4)
            if x <= 60:
                pts.append((x, y, r["abbreviation"]))
    ax.set_xlim(0, 60); ax.set_ylim(0, 100)
    place_labels(ax, pts, fontsize=5.8, avoid=[(x, y) for x in range(42, 60, 2) for y in (2, 5, 8)] + [(x, y) for x in range(42, 60, 2) for y in (91, 94, 97)])
    ax.text(59, 98, "Above the line:\nmore reviews Jan–Mar", fontsize=6.3, ha="right", va="top", color=INK)
    ax.text(59, 1.5, "Below the line:\nmore research Jan–Mar", fontsize=6.3, ha="right", va="bottom", color=INK)
    ax.set_xlim(0, 60); ax.set_ylim(0, 100)
    ax.set_xlabel("Other citable items published Jan–Mar (%)")
    ax.set_ylabel("Reviews published Jan–Mar (%)")
    ax.set_title("C  Reviews and other items published January to March", loc="left", fontsize=8.5)


def panel_d(ax, early, late):
    """Each journal's JIF-counted citations if its months rotated later, each paper staying in its year."""
    A = np.load(os.path.join(DATA, "ages72.npz"))
    row, K = A["row"], A["counts"]
    ok = (pm[row] >= 1) & (pm[row] != 6) & (py[row] >= 2014) & (py[row] <= 2021)
    early, late = early[:4], late[:4]
    names = [r["abbreviation"] for r in early] + REFERENCE + [r["abbreviation"] for r in late]
    rows = []
    for n in names:
        s = np.flatnonzero(ok & (jid[row] == by_abbr[n]))
        months = pm[row[s]].astype(int)
        rows.append([n, len(s), round(100 * rotated_change(K[s], months, 6), 2), round(100 * rotated_change(K[s], months, 9), 2)])
    write_csv("f2d_rotated_months", ["journal", "items_2014_21", "jif_change_6_months_pct", "jif_change_9_months_pct"], rows)
    print(rows, flush=True)
    ys = list(range(len(rows)))
    for y, r in zip(ys, rows):
        ax.plot([r[2], r[3]], [y, y], color="#BBBBBB", linewidth=0.8, zorder=1)
    ax.scatter([r[2] for r in rows], ys, s=16, color=BLUE, zorder=2, label="6 months later", linewidths=0)
    ax.scatter([r[3] for r in rows], ys, s=16, color=ORANGE, marker="D", zorder=2, label="9 months later", linewidths=0)
    ax.axvline(0, color=INK, linewidth=0.7)
    for b in (len(early) - 0.5, len(early) + len(REFERENCE) - 0.5):
        ax.axhline(b, color="#BBBBBB", linewidth=0.5)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.xaxis.set_major_formatter(PCT)
    ax.grid(axis="y", visible=False)
    ax.set_yticks(ys, [r[0] for r in rows], fontsize=5.8)
    ax.set_xlabel("Change in JIF-counted citations")
    ax.legend(fontsize=5.8, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, handletextpad=0.1, columnspacing=0.8, frameon=False)
    ax.set_title("D  JIF change if publication months moved later", loc="left", fontsize=8.5, x=-0.75)


def panel_e(ax, P):
    series = list(dict.fromkeys(r["series"] for r in P))
    months = NAMES + ["No month"]
    rows = []
    groups = collections.defaultdict(list)
    for r in P:
        groups[(r["series"], r["month"])].append(float(r["citations_first_24_months"]))
    biggest_mean = max(float(np.mean(v)) for v in groups.values())
    for k, s in enumerate(series):
        y = len(series) - 1 - k
        by = collections.defaultdict(list)
        for r in P:
            if r["series"] == s:
                by[r["month"]].append(float(r["citations_first_24_months"]))
        for m, v in by.items():
            x = months.index(m.replace("\n", " ")) + 1 if m in months else 13
            mean = float(np.mean(v))
            size = 4 + 135 * np.sqrt(mean / biggest_mean)
            ax.scatter(x, y, s=size, color=VERMILION if x <= 3 else BLUE, alpha=0.85, linewidths=0)
            ax.annotate(f"{mean:,.0f}", (x, y), xytext=(np.sqrt(size) / 2 + 2, 0), textcoords="offset points", fontsize=5.2, color=MUTED, va="center")
            rows.append([s, m, len(v), round(mean, 1)])
    write_csv("f2e_annual_reports", ["series", "month", "papers", "mean_citations_first_24_months"], rows)
    ax.set_yticks(range(len(series) - 1, -1, -1), series, fontsize=6)
    ax.set_xticks(range(1, 14), NAMES + ["No\nmonth"], fontsize=6.5)
    ax.set_xlim(0.4, 13.8); ax.set_ylim(-0.7, len(series) - 0.3)
    ax.axvline(12.5, color=MUTED, linewidth=0.5, linestyle=":")
    ax.set_xlabel("Publication month, 2010–22 (dot size and number: mean citations per report in its first 24 months)")
    ax.set_title("E  When the big annual reports come out, and how much they draw", loc="left", fontsize=8.5)


def panel_f(fig, gs, P):
    series = list(dict.fromkeys(r["series"] for r in P))
    head = fig.add_subplot(gs[0, :])
    head.axis("off")
    head.text(0, 0.5, "F  One annual report moved later", fontsize=8.5, va="center", transform=head.transAxes)
    rows = []
    for i, s in enumerate(series):
        ax = fig.add_subplot(gs[1 + i // 4, i % 4])
        best = max((r for r in P if r["series"] == s), key=lambda r: float(r["citations_jif_window"]))
        p, P0 = int(best["pmid"]), int(best["pub_year"])
        j, = con.execute("SELECT journal_id FROM papers WHERE pmid = ?", (p,)).fetchone()
        i0 = int(np.flatnonzero(pmid == p)[0])
        Y = P0 + 1 if C[i0, P0 + 1 - Y0] >= C[i0, P0 + 2 - Y0] else P0 + 2
        J = load_journal(j)
        when = J.when[J.cited == p]
        pub = J.items[p]
        out = []
        for k in range(12):
            r = shifted_rates(J, [p], k)
            y1 = (pub + k) // 12
            own = int((((when + k) // 12 == y1 + 1) | ((when + k) // 12 == y1 + 2)).sum())
            out.append((r["jif"][Y], float(np.mean([v for t, v in r["rolling"].items() if month_index(Y, 1) <= t <= month_index(Y, 12)])), own))
        out = np.array(out, float)
        change = 100 * (out / out[0] - 1)
        rows += [[s, p, best["month"], P0, Y, k, *[round(float(v), 3) for v in out[k]], *[round(float(v), 2) for v in change[k]]] for k in range(12)]
        ax.plot(range(12), change[:, 0], color=VERMILION, linewidth=1.4)
        ax.plot(range(12), change[:, 1], color=BLUE, linewidth=1.4)
        ax.plot(range(12), change[:, 2], color=VERMILION, linewidth=1.1, linestyle=(0, (3, 2)))
        ax.axhline(0, color=GRAY, linewidth=0.6)
        ax.set_xticks([0, 3, 6, 9])
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.3g}%".replace("-", "−") if abs(v) > 1e-9 else "0%"))
        ax.tick_params(labelsize=6)
        short = s.rsplit("(", 1)[1].rstrip(")")
        ax.set_title(short, loc="left", fontsize=7.5)
        ax.text(0.03, 0.04, f"{best['month']} {P0}; biggest year {Y}", transform=ax.transAxes, fontsize=5.2, color=MUTED, va="bottom")
        if i % 4 == 0:
            ax.set_ylabel("Change in rate", fontsize=6.5)
        if i // 4 == 1:
            ax.set_xlabel("Months later", fontsize=6.5)
    L = matplotlib.lines.Line2D
    head.legend(handles=[L([], [], color=VERMILION, linewidth=1.4, label="Journal's JIF-style rate, report's biggest year"), L([], [], color=BLUE, linewidth=1.4, label="Journal's 24-month rate, same year"),
                         L([], [], color=VERMILION, linewidth=1.1, linestyle=(0, (3, 2)), label="The report's own JIF-counted citations")],
                fontsize=5.8, ncol=2, loc="center right", frameon=False, handlelength=1.8, columnspacing=1)
    write_csv("f2f_one_report_shift", ["series", "pmid", "month", "pub_year", "rate_year", "months_later", "jif_style_biggest_year", "rate_24_month_biggest_year",
                                       "report_jif_counted", "jif_change_pct", "rate_change_pct", "report_change_pct"], rows)


LOSERS = ["J Med Virol", "Radiology", "Lancet", "IEEE Trans Vis Comput Graph"]


def panel_g(fig, gs):
    """The four journals that lose most from their timing (panel B): their late-year paper that gains most from January."""
    head = fig.add_subplot(gs[0, :])
    head.axis("off")
    head.text(0, 0.5, "G  One late-year paper moved earlier, up to January (lines as in F)", fontsize=8.5, va="center", transform=head.transAxes)
    rows = []
    for i, ab in enumerate(LOSERS):
        J = load_journal(by_abbr[ab])
        cand = con.execute("SELECT pmid, title, pub_year, pub_month FROM papers WHERE journal_id = ? AND doc_class IN ('research','review','case_report','guideline') "
                           "AND pub_year BETWEEN 2014 AND 2021 AND pub_month BETWEEN 7 AND 12", (by_abbr[ab],)).fetchall()
        u, c = np.unique(J.cited, return_counts=True)
        n = dict(zip(u.tolist(), c.tolist()))
        best = None
        for p, t, y, m in sorted(cand, key=lambda r: -n.get(r[0], 0))[:40]:
            w = J.when[J.cited == p]
            own = int(((w // 12 == y + 1) | (w // 12 == y + 2)).sum())
            k = m - 1
            gain = int((((w - k) // 12 == y + 1) | ((w - k) // 12 == y + 2)).sum()) - own
            if best is None or gain > best[0]:
                best = (gain, p, t, y, m, own)
        _, p, t, y, m, own = best
        w = J.when[J.cited == p]
        i0 = int(np.flatnonzero(pmid == p)[0])
        Y = y + 1 if C[i0, y + 1 - Y0] >= C[i0, y + 2 - Y0] else y + 2
        out = []
        for k in range(m):
            r = shifted_rates(J, [p], -k)
            c_ = int((((w - k) // 12 == y + 1) | ((w - k) // 12 == y + 2)).sum())
            out.append((r["jif"][Y], float(np.mean([v for q, v in r["rolling"].items() if month_index(Y, 1) <= q <= month_index(Y, 12)])), c_))
        out = np.array(out, float)
        change = 100 * (out / out[0] - 1)
        rows += [[ab, p, t, NAMES[m - 1], y, Y, k, *[round(float(v), 3) for v in out[k]], *[round(float(v), 2) for v in change[k]]] for k in range(m)]
        ax = fig.add_subplot(gs[1, i])
        ax.plot(range(m), change[:, 0], color=VERMILION, linewidth=1.4)
        ax.plot(range(m), change[:, 1], color=BLUE, linewidth=1.4)
        ax.plot(range(m), change[:, 2], color=VERMILION, linewidth=1.1, linestyle=(0, (3, 2)))
        ax.axhline(0, color=GRAY, linewidth=0.6)
        ax.set_xticks([0, 3, 6, 9] if m > 9 else [0, 2, 4, 6])
        ax.set_xlim(0, m - 1)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.3g}%".replace("-", "−") if abs(v) > 1e-9 else "0%"))
        ax.tick_params(labelsize=6)
        ax.set_title(ab.replace("IEEE Trans Vis Comput Graph", "IEEE TVCG"), loc="left", fontsize=7.5, pad=9)
        ax.text(0, 1.01, f"{NAMES[m - 1]} {y}: {t[:26]}…", transform=ax.transAxes, fontsize=5.1, color=MUTED, va="bottom")
        ax.set_xlabel("Months earlier", fontsize=6.5)
        if i == 0:
            ax.set_ylabel("Change in rate", fontsize=6.5)
    write_csv("f2g_moved_earlier", ["journal", "pmid", "title", "month", "pub_year", "rate_year", "months_earlier", "jif_style", "rate_24_month", "report_jif_counted",
                                    "jif_change_pct", "rate_change_pct", "report_change_pct"], rows)


def main():
    T = read("fig9_journal_timing.csv")
    P = read("fig9fg_annual_report_papers.csv")
    early, late = review_ranks(T)
    print("early", [r["abbreviation"] for r in early], "late", [r["abbreviation"] for r in late], flush=True)
    fig = plt.figure(figsize=(7.2, 14.2))
    gs = fig.add_gridspec(5, 1, hspace=0.42, height_ratios=[1, 1.2, 0.8, 1.3, 0.62])
    top = gs[0].subgridspec(1, 2, wspace=0.42)
    panel_a(fig.add_subplot(top[0]), T)
    panel_b(fig.add_subplot(top[1]), T)
    mid = gs[1].subgridspec(1, 2, wspace=0.62, width_ratios=[1.3, 1])
    panel_c(fig.add_subplot(mid[0]), T, early, late)
    panel_d(fig.add_subplot(mid[1]), early, late)
    panel_e(fig.add_subplot(gs[2]), P)
    panel_f(fig, gs[3].subgridspec(3, 4, wspace=0.42, hspace=0.8, height_ratios=[0.16, 1, 1]), P)
    panel_g(fig, gs[4].subgridspec(2, 4, wspace=0.42, hspace=0.95, height_ratios=[0.1, 1]))
    save(fig, "F2_timing")


if __name__ == "__main__":
    main()
