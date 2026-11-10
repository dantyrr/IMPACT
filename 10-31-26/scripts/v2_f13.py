"""F13: citations from outside PubMed, a three-paper OpenAlex pilot (figure_revision_plan.md, Task 13). Replaces Fig 8.

Papers: Hallmarks of Cancer, and the most-cited research article of 2010-12 in NEJM and in Lancet. Hirsch's paper is left out:
its physics and information-science citers are outside PubMed for good reason.

For each paper: citing works by type and whether they have a PMID. For the 20 largest non-PubMed journals citing each paper,
a sample of 50 of their cited papers: what share of the citations to those papers comes from PubMed papers. The same for the
5 largest PubMed journals citing the paper, as a benchmark. A low share in the first group is the one-way street.
Responses are cached in data/analysis/openalex_pilot/. No API key or personal details are sent.

Usage: python 10-31-26/scripts/v2_f13.py   (from the IMPACT folder)
"""
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from v2_common import ORANGE, ROOT, SKY, save, write_csv  # noqa: E402

CACHE = os.path.join(ROOT, "data", "analysis", "openalex_pilot")
BASE = "https://api.openalex.org/"
SAMPLE, TOP_OUTSIDE, TOP_INSIDE = 50, 20, 5
calls = 0


def get(path, **params):
    global calls
    q = urllib.parse.urlencode(params, safe=":|,>")
    url = f"{BASE}{path}?{q}"
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")
    if os.path.exists(f):
        return json.load(open(f))
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "impact-citation-pilot"})
            d = json.load(urllib.request.urlopen(req, timeout=40))
            calls += 1
            json.dump(d, open(f, "w"))
            time.sleep(0.15)
            return d
        except Exception as e:
            print("  retry", url[:90], e, flush=True)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("OpenAlex request failed: " + url)


def groups(filt, by, n=50):
    d = get("works", filter=filt, group_by=by, per_page=n)
    return d["group_by"]


def pmid_share(source):
    """Of citations to a sample of this journal's cited papers, the share made by works with a PMID."""
    w = get("works", filter=f"primary_location.source.id:{source},cited_by_count:>0", sample=SAMPLE, seed=1, select="id,cited_by_count", per_page=SAMPLE)["results"]
    if len(w) < 10:
        return None
    ids = "|".join(x["id"].rsplit("/", 1)[1] for x in w)
    g = {x["key"]: x["count"] for x in groups(f"cites:{ids}", "has_pmid")}
    yes, no = g.get("true", 0), g.get("false", 0)
    return (yes / (yes + no), yes + no) if yes + no >= 20 else None


def pilot(name, doi):
    w = get("works", filter=f"doi:{doi}", select="id,cited_by_count,publication_year")["results"][0]
    wid = w["id"].rsplit("/", 1)[1]
    has = {x["key"]: x["count"] for x in groups(f"cites:{wid}", "has_pmid")}
    outside = f"cites:{wid},has_pmid:false"
    types = {x["key_display_name"]: x["count"] for x in groups(outside, "type")}
    lang = {x["key_display_name"]: x["count"] for x in groups(outside + ",type:article", "language", 8)}
    country = {x["key_display_name"]: x["count"] for x in groups(outside + ",type:article", "authorships.countries", 10)}
    src_out = [x for x in groups(outside + ",type:article,primary_location.source.type:journal", "primary_location.source.id", TOP_OUTSIDE + 5)][:TOP_OUTSIDE]
    src_in = [x for x in groups(f"cites:{wid},has_pmid:true,type:article,primary_location.source.type:journal", "primary_location.source.id", TOP_INSIDE)][:TOP_INSIDE]
    rows = []
    for kind, src in (("outside", src_out), ("inside", src_in)):
        for s in src:
            sid = s["key"].rsplit("/", 1)[-1]
            r = pmid_share(sid)
            meta = get(f"sources/{sid}", select="display_name,country_code,is_in_doaj,is_core,type,works_count")
            rows.append(dict(paper=name, kind=kind, journal=meta.get("display_name"), citing_this_paper=s["count"], country=meta.get("country_code"), doaj=meta.get("is_in_doaj"),
                             core=meta.get("is_core"), share_from_pubmed=None if r is None else round(r[0], 4), sampled_citations=None if r is None else r[1]))
    print(name, w["cited_by_count"], has, types, lang, flush=True)
    return dict(name=name, total=w["cited_by_count"], has=has, types=types, lang=lang, country=country), rows


def main():
    import sqlite3
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    papers = [("Hallmarks of Cancer (Cell, 2011)", "10.1016/j.cell.2011.02.013")]
    for slug, tag in (("nejm", "NEJM"), ("lancet", "Lancet")):
        p, t, y, d = con.execute("""SELECT p.pmid, p.title, p.pub_year, p.doi FROM papers p JOIN journals j ON j.id = p.journal_id
            JOIN (SELECT cited_pmid, COUNT(*) n FROM citations c JOIN papers q ON q.pmid = c.cited_pmid JOIN journals k ON k.id = q.journal_id
                  WHERE k.slug = ? AND q.pub_year BETWEEN 2010 AND 2012 AND q.doc_class = 'research' GROUP BY 1 ORDER BY n DESC LIMIT 1) z ON z.cited_pmid = p.pmid""", (slug,)).fetchone()
        print(tag, p, t, y, d, flush=True)
        papers.append((f"{t[:48]}… ({tag}, {y})", d))
    summary, rows = [], []
    for name, doi in papers:
        s, r = pilot(name, doi)
        summary.append(s); rows += r
    json.dump(summary, open(os.path.join(CACHE, "summary.json"), "w"), indent=1)
    write_csv("f13_journals", list(rows[0]), [list(r.values()) for r in rows])
    write_csv("f13_papers", ["paper", "openalex_citing_works", "with_pmid", "without_pmid", "article", "book_chapter", "dissertation", "preprint", "other"],
              [[s["name"], s["total"], s["has"].get("true", 0), s["has"].get("false", 0), s["types"].get("article", 0), s["types"].get("book-chapter", 0),
                s["types"].get("dissertation", 0), s["types"].get("preprint", 0),
                sum(v for k, v in s["types"].items() if k not in ("article", "book-chapter", "dissertation", "preprint"))] for s in summary])
    print("calls", calls)


def figure():
    import csv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    BLUE, VERMILION, GREEN, GRAY, INK, MUTED = "#0072B2", "#D55E00", "#009E73", "#8C8C8C", "#222222", "#666666"
    plt.rcParams.update({"font.family": "Arial", "font.size": 8, "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.5, "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED,
                         "xtick.labelcolor": INK, "ytick.labelcolor": INK, "legend.frameon": False, "savefig.dpi": 300, "pdf.fonttype": 42})
    data = os.path.join(ROOT, "10-31-26", "v2", "data")
    P = list(csv.DictReader(open(os.path.join(data, "f13_papers.csv"))))
    J = list(csv.DictReader(open(os.path.join(data, "f13_journals.csv"))))
    short = ["Hallmarks (Cell, 2011)", "Ipilimumab (NEJM, 2010)", "Global Burden of Disease\n(Lancet, 2012)"]
    fig = plt.figure(figsize=(7.2, 6.4))
    gs = fig.add_gridspec(2, 1, hspace=0.42, height_ratios=[0.75, 1])
    ax = fig.add_subplot(gs[0])
    parts = [("with_pmid", "In PubMed", BLUE), ("article", "Journal articles outside PubMed", VERMILION), ("book_chapter", "Book chapters", ORANGE),
             ("dissertation", "Dissertations", GREEN), ("preprint", "Preprints", SKY), ("other", "Other", GRAY)]
    yy = np.arange(len(P))[::-1]
    for y, r in zip(yy, P):
        tot = sum(int(r[k]) for k, _, _ in parts)
        left = 0
        for k, _, c in parts:
            v = int(r[k]) / tot
            ax.barh(y, v, left=left, color=c, height=0.62, edgecolor="white", linewidth=0.5)
            if v >= 0.045:
                ax.text(left + v / 2, y, f"{v:.0%}", ha="center", va="center", fontsize=6.3, color="white" if c in (BLUE, VERMILION, GREEN) else INK)
            left += v
        ax.text(1.01, y, f"{tot:,}", fontsize=6.3, color=MUTED, va="center")
    ax.set_yticks(yy, short, fontsize=6.8)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share of everything citing the paper in OpenAlex (number at right: total)")
    ax.legend(handles=[matplotlib.patches.Patch(color=c, label=l) for _, l, c in parts], fontsize=6, ncol=3, loc="lower center", bbox_to_anchor=(0.45, 1.0), handlelength=1, columnspacing=1)
    ax.set_title("A  Who cites three highly cited papers", loc="left", fontsize=8.5, x=-0.28, y=1.13)
    ax = fig.add_subplot(gs[1])
    rng = np.random.default_rng(1)
    names = [r["paper"] for r in P]
    rows = []
    for g, name in enumerate(names):
        for kind, dx, color in (("outside", -0.2, VERMILION), ("inside", 0.2, BLUE)):
            v = np.array([float(r["share_from_pubmed"]) for r in J if r["paper"] == name and r["kind"] == kind and r["share_from_pubmed"]])
            ax.boxplot(v, positions=[g + dx], widths=0.3, showfliers=False, patch_artist=True, boxprops=dict(facecolor=color, edgecolor=color, alpha=0.25),
                       medianprops=dict(color=color, linewidth=1.8), whiskerprops=dict(color=color, linewidth=0.9), capprops=dict(color=color, linewidth=0.9))
            ax.scatter(g + dx + rng.uniform(-0.07, 0.07, len(v)), v, s=9, color=color, alpha=0.7, linewidths=0, zorder=3)
            rows.append([name, kind, len(v), round(float(np.median(v)), 3)])
    write_csv("f13b_summary", ["paper", "group", "journals", "median_share_from_pubmed"], rows)
    print(rows)
    ax.set_xticks(range(len(names)), short, fontsize=6.8)
    ax.set_xlim(-0.6, len(names) - 0.4)
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Citations to the journal that come from PubMed papers")
    ax.legend(handles=[matplotlib.patches.Patch(color=VERMILION, alpha=0.5, label="20 largest citing journals outside PubMed"),
                       matplotlib.patches.Patch(color=BLUE, alpha=0.5, label="5 largest citing journals in PubMed")], fontsize=6, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_title("B  Does PubMed cite the journals that cite these papers?", loc="left", fontsize=8.5, x=-0.08, y=1.09)
    ax.text(0, -0.17, "Each dot is one journal. For 50 of its papers, the dot height is the share of everything citing them that is in PubMed. Near 0%: PubMed ignores that journal.",
            transform=ax.transAxes, fontsize=6, color=MUTED, va="top")
    save(fig, "F13_outside_pubmed")


if __name__ == "__main__":
    if "plot" not in sys.argv:
        main()
    figure()
