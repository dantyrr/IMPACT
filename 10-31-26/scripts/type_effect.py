"""Figure 11: what each article type does to a journal's rate. The site's 24-month rate for three cardiovascular
journals, with and without guidelines (A) and reviews (B): the "Compare without" line on the site's Compare panel.
Taking a type out removes its papers and the citations to them. Also counts, across all journals, how far guidelines
and reviews move the rate at the settled month. Reads the site's exports (docs/data/journals/*.json).

--stats-line adds a dotted line to panel A: Circulation without guidelines and without the annual Heart Disease and
Stroke Statistics papers, which are classed as research or review, so no article type takes them out. It writes
fig11_article_type_effect_stats instead of fig11_article_type_effect, so either figure can be rebuilt on its own.

Usage: python 10-31-26/scripts/type_effect.py [--stats-line]   (from the IMPACT folder)
"""
import argparse
import glob
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import BLUE, GREEN, INK, MUTED, ROOT, VERMILION, np, plt, save, write_csv  # noqa: E402

JSON = os.path.join(ROOT, "docs", "data", "journals")
CITABLE = ("research", "review", "case_report", "guideline")
JOURNALS = [("circulation", "Circulation", VERMILION), ("circulation-research", "Circ Res", GREEN),
            ("arteriosclerosis-thrombosis-and-vascular-biology", "ATVB", BLUE)]
PANELS = [("guideline", "guidelines"), ("review", "reviews")]
MIN_PAPERS = 100    # citable items in the window, for the all-journals counts
DASHED, DOTTED = (0, (3.5, 2.5)), (0, (1, 1.6))


def load(slug):
    with open(os.path.join(JSON, slug + ".json")) as f:
        return json.load(f)


def settled_month(d):
    """Export month - 12, as on the site (app.js _settledMonth)."""
    y, m = int(d["last_updated"][:4]), int(d["last_updated"][5:7])
    i = y * 12 + m - 1 - 12
    cutoff = f"{i // 12:04d}-{i % 12 + 1:02d}"
    return max(p["month"] for p in d["timeseries"] if p["month"] <= cutoff)


def rate(entry, types):
    bt = entry.get("by_type", {})
    papers = sum(bt.get(t, {}).get("papers", 0) for t in types)
    cites = sum(bt.get(t, {}).get("citations", 0) for t in types)
    return cites / papers if papers else None


def without(t):
    return [c for c in CITABLE if c != t]


def journal_series(slug):
    d = load(slug)
    end = settled_month(d)
    ts = [p for p in d["timeseries"] if p["month"] <= end and p.get("papers", 0) > 0]
    return ts, end


def month_index(date):
    return int(date[:4]) * 12 + int(date[5:7]) - 1


def stats_papers():
    """Circulation's statistics papers and executive summaries, as {pmid: (pub month, {citing month: citations})}.
    Their corrections and the 2013 editorial are not citable items, so the rate never counted them."""
    db = sqlite3.connect(f"file:{os.path.join(ROOT, 'data', 'impact.db')}?mode=ro", uri=True)
    jid = db.execute("SELECT id FROM journals WHERE slug = 'circulation'").fetchone()[0]
    rows = db.execute("SELECT pmid, pub_date, doc_class FROM papers WHERE journal_id = ? AND lower(title) LIKE "
                      "'%stroke statistics%' AND doc_class IN ('research', 'review', 'case_report', 'guideline')",
                      (jid,)).fetchall()
    assert all(r[2] != "guideline" for r in rows), "a guideline would be taken out twice"
    papers = {r[0]: (month_index(r[1]), {}) for r in rows}
    marks = ",".join("?" * len(papers))
    for pmid, date, n in db.execute(
            f"SELECT cited_pmid, substr(citing_date, 1, 7), COUNT(*) FROM citations WHERE cited_pmid IN ({marks}) "
            "AND citing_class IS NULL AND citing_date IS NOT NULL GROUP BY 1, 2", list(papers)):
        papers[pmid][1][month_index(date + "-01")] = n
    db.close()
    return papers


def in_window(papers, month):
    """Statistics papers in the 24-month window at this month, and the citations the window counts for them."""
    t = month_index(month + "-01")
    hits = [c for pub, c in papers.values() if t - 35 <= pub <= t - 12]
    return len(hits), sum(n for c in hits for m, n in c.items() if t - 11 <= m <= t)


def rate_without_stats(entry, papers):
    """The rate without guidelines and without the statistics papers."""
    kept = without("guideline")
    n, cites = in_window(papers, entry["month"])
    left = sum(entry["by_type"].get(t, {}).get("papers", 0) for t in kept) - n
    return (sum(entry["by_type"].get(t, {}).get("citations", 0) for t in kept) - cites) / left if left else None


def field_counts():
    """Share of journals whose rate falls by 5% or more, at the settled month, without each type."""
    rows, out = [], []
    for path in glob.glob(os.path.join(JSON, "*.json")):
        d = json.load(open(path))
        if not d.get("timeseries"):
            continue
        end = settled_month(d)
        e = next(p for p in d["timeseries"] if p["month"] == end)
        papers = sum(e.get("by_type", {}).get(c, {}).get("papers", 0) for c in CITABLE)
        full = rate(e, CITABLE)
        if papers < MIN_PAPERS or not full:
            continue
        drop = {}
        for t, _ in PANELS:
            r = rate(e, without(t))
            drop[t] = (r - full) / full if r is not None else None
        rows.append((d["journal"], papers, full, drop, e["by_type"].get("guideline", {}).get("papers", 0)))
    for t, name in PANELS:
        v = [r[3][t] for r in rows if r[3][t] is not None]
        n5, n10 = sum(x <= -0.05 for x in v), sum(x <= -0.10 for x in v)
        print(f"{name}: {n5:,} of {len(v):,} journals fall 5%+ without them, {n10:,} fall 10%+")
        out.append([name, len(v), n5, n10])
    g = sorted((r for r in rows if r[3]["guideline"] is not None), key=lambda r: r[3]["guideline"])
    has = sum(r[4] > 0 for r in rows)
    print(f"{has:,} of {len(rows):,} journals have a guideline in the window")
    print("most lifted by guidelines:", [(r[0][:40], r[4], f"{r[3]['guideline']:.0%}") for r in g[:10]])
    write_csv("fig11_all_journals", ["type", "journals", "fall_5pct_or_more", "fall_10pct_or_more"], out)
    write_csv("fig11_top_guideline_journals",
              ["journal", "citable_items", "guidelines", "rate", "rate_without_guidelines", "change"],
              [[r[0], r[1], r[4], round(r[2], 3), round(r[2] * (1 + r[3]["guideline"]), 3),
                round(r[3]["guideline"], 4)] for r in g[:25]])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stats-line", action="store_true",
                    help="add Circulation without guidelines and statistics papers to panel A")
    args = ap.parse_args()
    series = {slug: journal_series(slug) for slug, _, _ in JOURNALS}
    rows, table = [], []
    for slug, name, _ in JOURNALS:
        ts, end = series[slug]
        for p in ts:
            full = rate(p, CITABLE)
            assert full is None or abs(full - p["rolling_if"]) < 0.002, (slug, p["month"], full, p["rolling_if"])
            rows.append([name, p["month"], round(full, 3) if full else ""]
                        + [(lambda r: round(r, 3) if r is not None else "")(rate(p, without(t))) for t in CITABLE])
        full = rate(ts[-1], CITABLE)
        v = {t: rate(ts[-1], without(t)) for t in CITABLE}
        table.append([name, end, round(full, 3)] + [round(v[t], 3) for t in CITABLE]
                     + [ts[-1]["by_type"][t]["papers"] for t in CITABLE])
        print(name, end, f"{full:.2f}", {t: f"{v[t]:.2f} ({(v[t] - full) / full:+.0%})" for t in CITABLE})
        for t, label in PANELS:
            pct = [(rate(p, CITABLE) - rate(p, without(t))) / rate(p, CITABLE) * 100 for p in ts
                   if rate(p, CITABLE) and rate(p, without(t)) is not None]
            print(f"  {label}: mean {np.mean(pct):.1f}% of the rate, largest {max(pct, key=abs):.1f}%")
    write_csv("fig11_rates", ["journal", "month", "rate"] + [f"without_{t}" for t in CITABLE], rows)
    write_csv("fig11_settled_month", ["journal", "month", "rate"] + [f"without_{t}" for t in CITABLE]
              + [f"papers_{t}" for t in CITABLE], table)

    stats = stats_papers() if args.stats_line else None
    if stats:
        ts = series["circulation"][0]
        out = []
        for p in ts:
            n, cites = in_window(stats, p["month"])
            r = rate_without_stats(p, stats)
            out.append(["Circulation", p["month"], n, cites, round(rate(p, CITABLE), 3),
                        round(rate(p, without("guideline")), 3), round(r, 3)])
        write_csv("fig11_stats_updates", ["journal", "month", "statistics_papers_in_window", "citations_to_them",
                                          "rate", "without_guidelines", "without_guidelines_and_statistics"], out)
        pct = [(r[4] - r[6]) / r[4] * 100 for r in out]
        print(f"{len(stats)} statistics papers; Circulation without both at {out[-1][1]}: {out[-1][6]} "
              f"({out[-1][2]} papers, {out[-1][3]} citations); mean {np.mean(pct):.1f}% of the rate, "
              f"largest {max(pct):.1f}%")

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.4), sharex=True, sharey=True)
    months = sorted({p["month"] for ts, _ in series.values() for p in ts})
    pos = {m: i for i, m in enumerate(months)}
    for ax, (t, label), letter in zip(axes, PANELS, "AB"):
        ends = []
        for slug, name, color in JOURNALS:
            ts, _ = series[slug]
            x = [pos[p["month"]] for p in ts]
            full = [rate(p, CITABLE) for p in ts]
            less = [rate(p, without(t)) for p in ts]
            ax.plot(x, less, color=color, linewidth=1.3, linestyle=DASHED, zorder=2)
            if stats and t == "guideline" and slug == "circulation":
                both = [rate_without_stats(p, stats) for p in ts]
                ax.plot(x, both, color=color, linewidth=1.3, linestyle=DOTTED, zorder=2)
                ax.annotate(f"Also without statistics updates {both[-1]:.1f} ({(both[-1] - full[-1]) / full[-1]:.0%})"
                            .replace("-", "−"), (len(months) - 1, both[-1]), xytext=(6, 0),
                            textcoords="offset points", va="center", fontsize=6.5, color=INK, annotation_clip=False)
            ax.plot(x, full, color=color, linewidth=1.5, zorder=3)
            ends.append((full[-1], less[-1], name, color))
        for full, less, name, color in ends:
            change = (less - full) / full
            text = (f"{name} {full:.1f} → {less:.1f} ({'−' if change < 0 else '+'}{abs(change):.0%})"
                    if round(abs(change), 3) else f"{name} {full:.1f}, no change")
            ax.annotate(text, (len(months) - 1, (full + less) / 2), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=6.5, color=INK, annotation_clip=False)
        ax.plot([], [], color=MUTED, linewidth=1.5, label="All citable items")
        ax.plot([], [], color=MUTED, linewidth=1.3, linestyle=DASHED, label=f"Without {label}")
        if stats and t == "guideline":
            ax.plot([], [], color=MUTED, linewidth=1.3, linestyle=DOTTED,
                    label="Without guidelines and statistics updates (Circulation only)")
        ax.legend(fontsize=6.5, loc="upper left", frameon=False)
        ax.set_ylim(0, 33)
        ax.set_xlim(0, len(months) - 1)
        ax.set_ylabel("24-month citation rate")
        ax.set_title(f"{letter}  Rate with and without {label}", loc="left", fontsize=8.5)
    ticks = [pos[m] for m in months if m.endswith("-01") and int(m[:4]) % 2 == 1]
    axes[1].set_xticks(ticks, [months[i][:4] for i in ticks])
    axes[1].set_xlabel("Month of the rate")
    save(fig, "fig11_article_type_effect_stats" if stats else "fig11_article_type_effect")
    field_counts()


if __name__ == "__main__":
    main()
