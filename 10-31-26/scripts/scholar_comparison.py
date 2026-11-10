"""IMPACT vs Google Scholar vs OpenAlex citations per year for a few well-known papers.

IMPACT counts citations between PubMed-indexed papers (iCite). Google Scholar counts
any document it indexes (non-PubMed journals, books, theses, preprints, conference
papers, predatory journals); OpenAlex sits in between.

Google Scholar has no API, so its per-year counts were read by hand on 2026-10-31
from the "Total citations" chart on each paper's page in an author's public Scholar
profile (URLs in GS_SOURCE). OpenAlex counts come from api.openalex.org and are cached
in data/analysis/openalex_<pmid>.json.

Writes fig8_scholar_vs_impact (PNG + PDF) and data/fig8_scholar_vs_impact.csv.

Usage: python 10-31-26/scripts/scholar_comparison.py   (from the IMPACT folder)
"""
import collections
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import BLUE, VERMILION, MUTED, DATA, con, np, plt, save, write_csv, matplotlib  # noqa: E402

ORANGE = "#E69F00"
LAST = 2024                      # last citation year complete in all three sources

PAPERS = [   # pmid, publication year, label
    (21376230, 2011, "Hallmarks of cancer: the next generation (Cell, 2011)"),
    (23746838, 2013, "The hallmarks of aging (Cell, 2013)"),
    (35022204, 2022, "Hallmarks of cancer: new dimensions (Cancer Discov, 2022)"),
    (16275915, 2005, "Hirsch's h-index paper (PNAS, 2005)"),
]
GS = {   # pmid -> {citation year: Google Scholar citations}
    21376230: dict(zip(range(2011, 2027), [818, 2722, 3858, 4853, 5385, 6038, 6239, 6552, 6971, 7656, 8537, 7790, 6788,
                                           6059, 6012, 4672])),
    23746838: dict(zip(range(2013, 2027), [84, 353, 635, 761, 987, 1202, 1421, 1796, 2045, 2240, 2277, 2054, 2214, 2224])),
    35022204: dict(zip(range(2022, 2027), [1256, 2515, 2984, 3262, 3050])),
}
GS_SOURCE = {
    21376230: "https://scholar.google.com/citations?view_op=view_citation&user=LyQJd10AAAAJ&citation_for_view=LyQJd10AAAAJ:AvfA0Oy_GE0C",
    23746838: "https://scholar.google.com/citations?view_op=view_citation&user=EhU_C4MAAAAJ&citation_for_view=EhU_C4MAAAAJ:jFemdcug13IC",
    35022204: "https://scholar.google.com/citations?view_op=view_citation&user=LyQJd10AAAAJ&citation_for_view=LyQJd10AAAAJ:9vf0nzSNQJEC",
}


def openalex(p):
    path = os.path.join(DATA, f"openalex_{p}.json")
    if not os.path.exists(path):
        with urllib.request.urlopen(f"https://api.openalex.org/works/pmid:{p}") as r, open(path, "w") as fh:
            fh.write(r.read().decode())
    w = json.load(open(path))
    return {d["year"]: d["cited_by_count"] for d in w["counts_by_year"]}


def main():
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.8))
    axes = list(axes.flat)
    rows = []
    for ax, (p, year, label) in zip(axes, PAPERS):
        imp = collections.defaultdict(int, con.execute(
            "SELECT citing_year, COUNT(*) FROM citations INDEXED BY idx_citations_cited WHERE cited_pmid = ? "
            "AND citing_class IS NULL GROUP BY citing_year", (p,)).fetchall())
        oa, gs = openalex(p), GS.get(p, {})
        yrs = list(range(year, LAST + 1))
        for name, src, color in [("Google Scholar", gs, VERMILION), ("OpenAlex", oa, ORANGE), ("IMPACT (PubMed only)", imp, BLUE)]:
            xs = [y for y in yrs if y in src]
            if xs:
                ax.plot(xs, [src[y] for y in xs], color=color, linewidth=1.6, label=name)
        both = [y for y in yrs if y in gs and imp.get(y)]
        if both:
            ratio = sum(gs[y] for y in both) / sum(imp[y] for y in both)
            sub = f"Scholar = {ratio:.1f}× IMPACT ({both[0]}–{both[-1]})"
        else:
            both = [y for y in yrs if y in oa and imp.get(y)]
            ratio = sum(oa[y] for y in both) / sum(imp[y] for y in both)
            sub = f"OpenAlex = {ratio:.1f}× IMPACT\n(no public Scholar profile)"
        ax.set_title(label, loc="left", fontsize=7.5)
        ax.text(0.02, 0.97, sub, transform=ax.transAxes, fontsize=6, color=MUTED, va="top")
        ax.set_ylim(0, max(max(gs.values(), default=0), max(oa.values()), max(imp[y] for y in yrs)) * 1.25)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.tick_params(labelsize=6.5)
        ax.set_xlim(year - 0.5, LAST + 0.5)
        ax.set_xticks(yrs if len(yrs) < 6 else [y for y in yrs if y % 5 == 0])
        for y in yrs:
            rows.append([p, label, y, gs.get(y, ""), oa.get(y, ""), imp[y]])
    axes[0].set_ylabel("Citations per year")
    axes[2].set_ylabel("Citations per year")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=3, fontsize=7, loc="upper left", bbox_to_anchor=(0.0, 1.04))
    fig.text(0.0, -0.04, f"Citation years through {LAST}. Google Scholar counts read from authors' public Scholar profiles on "
             "2026-10-31; OpenAlex from its API (per-year counts start in 2012).", fontsize=6, color=MUTED)
    fig.tight_layout()
    write_csv("fig8_scholar_vs_impact", ["pmid", "paper", "citation_year", "google_scholar", "openalex", "impact"], rows)
    save(fig, "fig8_scholar_vs_impact")


if __name__ == "__main__":
    main()
