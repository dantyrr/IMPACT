#!/usr/bin/env python3
"""Small site files for the paper's figures, reformatted from existing analysis files.

Reads data/analysis/ (a snapshot, not refreshed by the weekly update) and impact.db read-only, with no pass over the
citations table, and writes under docs/data/.

Usage: python scripts/export_site_extras.py [retractions|measures|citers|series|landscape|bubbles ...]   (all if none given)
"""
import collections
import csv
import json
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS = os.path.join(ROOT, "data", "analysis")
OUT = os.path.join(ROOT, "docs", "data")
RW_CSV = os.path.join(ROOT, "data", "retraction_watch", "retraction_watch.csv")
Y0 = 2003                     # first column of the citation matrix
SHARDS = 64
_cache = {}


def db():
    if "db" not in _cache:
        _cache["db"] = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    return _cache["db"]


def matrix():
    if "m" not in _cache:
        D = np.load(os.path.join(ANALYSIS, "cites.npz"))
        _cache["m"] = {k: D[k] for k in ("pmid", "journal_id", "pub_year", "doc_class", "counts")}
    return _cache["m"]


def write_json(out_dir, name, data):
    path = os.path.join(out_dir, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))


def reinstated(pmids):
    """The listed PMIDs that Retraction Watch records as reinstated, by PMID or DOI."""
    rows = {}
    with open(RW_CSV, encoding="latin-1", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["RetractionNature"] == "Reinstatement":
                rows[r["OriginalPaperPubMedID"].strip()] = True
                rows[r["OriginalPaperDOI"].strip().lower()] = True
    out = {int(p) for p in rows if p.isdigit() and int(p) in pmids}
    ids = sorted(pmids)
    for i in range(0, len(ids), 900):
        ch = ids[i:i + 900]
        q = ",".join("?" * len(ch))
        out |= {p for p, d in db().execute(f"SELECT pmid, doi FROM papers WHERE pmid IN ({q}) AND doi IS NOT NULL", ch) if d.strip().lower() in rows}
    return out


def export_retractions(out_dir=OUT):
    """retractions/{pmid % 64}.json and retractions/summary.json. Returns {"papers": n, "with_counts": n, "journals": n}."""
    R = np.load(os.path.join(ANALYSIS, "retractions.npz"), allow_pickle=True)
    M = matrix()
    pmid, jid, py, dc, C = M["pmid"], M["journal_id"], M["pub_year"], M["doc_class"], M["counts"]
    row = np.full(pmid.max() + 1, -1, np.int64)
    row[pmid] = np.arange(len(pmid))
    names = [str(n) for n in R["reason_names"]]
    back = reinstated({int(p) for p in R["pmid"]})
    shards = collections.defaultdict(dict)
    with_counts = 0
    retracted_rows = []
    for p, y, m, src, flags in zip(R["pmid"].tolist(), R["notice_year"].tolist(), R["notice_month"].tolist(), R["date_source"].tolist(), R["reasons"]):
        rec = {"y": y or None, "m": (m or None) if y else None, "r": [n for n, f in zip(names, flags) if f], "s": "rw" if src == 1 else "pubmed",
               "st": "reinstated" if p in back else "retracted"}
        i = int(row[p]) if p <= pmid.max() else -1
        if i >= 0:
            rec["py"] = int(py[i])
            rec["cy"] = {str(Y0 + int(k)): int(C[i, k]) for k in np.flatnonzero(C[i])}
            with_counts += 1
            if p not in back:
                retracted_rows.append((i, y))
        shards[p % SHARDS][str(p)] = rec
    for n, rows in shards.items():
        write_json(out_dir, f"retractions/{n}.json", rows)

    slug = dict(db().execute("SELECT id, slug FROM journals"))
    window = (dc <= 3) & (py >= 2015) & (py <= 2023)
    items = np.bincount(jid[window], minlength=int(jid.max()) + 1)
    summary = {}
    for i, y in retracted_rows:
        j = int(jid[i])
        if j not in slug:
            continue
        s = summary.setdefault(slug[j], {"pub": collections.Counter(), "ret": collections.Counter(), "retracted": 0, "items": int(items[j]), "win": 0})
        s["retracted"] += 1
        s["pub"][str(int(py[i]))] += 1
        if y:
            s["ret"][str(y)] += 1
        s["win"] += int(window[i])
    for s in summary.values():
        s["per10k"] = round(s.pop("win") / s["items"] * 1e4, 1) if s["items"] else None
    write_json(out_dir, "retractions/summary.json", summary)
    return {"papers": len(R["pmid"]), "with_counts": with_counts, "journals": len(summary)}


def read_csv(path):
    with open(os.path.join(ROOT, "10-31-26", path), newline="") as f:
        return list(csv.DictReader(f))


def histogram(values, bins=40):
    """Equal-width bins between the 1st and 99th percentiles; values beyond them count in the end bins."""
    v = np.asarray(values, float)
    lo, hi = np.percentile(v, [1, 99])
    edges = np.linspace(lo, hi, bins + 1)
    counts = np.histogram(np.clip(v, lo, hi), bins=edges)[0]
    return [round(float(e), 5) for e in edges], [int(c) for c in counts]


def export_measures(out_dir=OUT):
    """journal_measures.json: where each journal sits on four of the paper's measures. Per journal, [value, percentile]."""
    rows = db().execute("SELECT name, abbreviation, slug FROM journals").fetchall()
    # A few journals share a name or abbreviation. Those stay in each histogram but get no per-journal value.
    def unique(key):
        seen = collections.Counter(r[key] for r in rows)
        return {r[key]: r[2] for r in rows if seen[r[key]] == 1}
    name2slug, abbr2slug = unique(0), unique(1)
    sets = {
        "top_paper": ("Citations from its single top paper, 2024", "percent",
                      [(name2slug.get(r["journal"]), float(r["top_paper_share"])) for r in read_csv("data/fig1a_top_paper_share_2024.csv")]),
        "lift": ("Lift from non-research items, Nov 2025", "signed",
                 [(r["slug"], float(r["lift_from_reviews"])) for r in read_csv("v2/data/f7ab_lift_all_journals.csv")]),
        "outside_journal": ("Citations from its largest outside journal, 2024", "percent",
                            [(abbr2slug.get(r["journal"]), float(r["share_from_largest_outside_journal"])) for r in read_csv("v2/data/f6a_two_screens.csv")]),
        "timing": ("JIF change from papers published in early months, 2014\u201321", "signed",
                   [(name2slug.get(r["journal"]), float(r["placement_gain"])) for r in read_csv("data/fig9_journal_timing.csv")]),
    }
    measures, journals = {}, collections.defaultdict(dict)
    for key, (label, unit, pairs) in sets.items():
        rows = pairs
        values = np.array([v for _, v in rows])
        order = np.sort(values)
        edges, counts = histogram(values)
        measures[key] = {"label": label, "signed": unit == "signed", "n": len(rows), "bins": edges, "counts": counts, "median": round(float(np.median(values)), 5)}
        for slug, v in rows:
            if slug:
                pct = 100 * np.searchsorted(order, v, side="left") / len(order)
                journals[slug][key] = [round(v, 5), round(float(pct), 1)]
    write_json(out_dir, "journal_measures.json", {"asOf": "Nov 2026", "measures": measures, "journals": journals})
    return {k: v["n"] for k, v in measures.items()}


def export_citers(out_dir=OUT):
    """citers/{slug}.json: citing and author countries (2024 citations to 2022-23 items), and the top 10 citing journals."""
    Z = np.load(os.path.join(ANALYSIS, "country_matrix.npz"))
    names = Z["countries"].astype(str)
    cite, auth, cite_n, located = Z["cite"], Z["auth"], Z["cite_n"], Z["cite_located"]   # NpzFile re-reads on every access
    S = np.load(os.path.join(ANALYSIS, "citing_screen_2024.npz"))
    u, k, NJ = S["u"], S["k"], int(S["NJ"])
    cited, citing = u // NJ, u % NJ
    keep = (cited != citing) & (citing != NJ - 1)
    order = np.lexsort((-k[keep], cited[keep]))
    cited, citing, k = cited[keep][order], citing[keep][order], k[keep][order]
    starts = np.searchsorted(cited, np.arange(NJ + 1))
    meta = {j: (s, a) for j, s, a in db().execute("SELECT id, slug, abbreviation FROM journals")}

    def shares(row):
        total = row.sum()
        if not total:
            return {}
        return {str(n): round(float(v / total), 4) for n, v in zip(names, row) if v / total >= 0.0005}

    n = 0
    for j, (slug, _) in meta.items():
        if j >= len(cite) or not cite_n[j]:
            write_json(out_dir, f"citers/{slug}.json", {"year": 2024, "citations": 0, "located": 0, "countries": {}, "authors": {}, "journals": []})
            continue
        top = [{"slug": meta[int(c)][0], "name": meta[int(c)][1], "citations": int(v)}
               for c, v in zip(citing[starts[j]:starts[j + 1]], k[starts[j]:starts[j + 1]]) if int(c) in meta][:10]
        write_json(out_dir, f"citers/{slug}.json", {"year": 2024, "citations": int(cite_n[j]), "located": int(located[j]),
                                                    "countries": shares(cite[j]), "authors": shares(auth[j]), "journals": top})
        n += 1
    return {"journals": n}


def export_series(out_dir=OUT):
    """series/{slug}.json for journals with recurring series: each series' title, citable PMIDs and lifetime citations."""
    Z = np.load(os.path.join(ANALYSIS, "series_v2.npz"), allow_pickle=True)
    sid, keys = Z["sid"].copy(), Z["keys"]
    M = matrix()
    pmid, py, dc, C = M["pmid"], M["pub_year"], M["doc_class"], M["counts"]
    # The NCBI series under its three titles: "...Information", "...Information in 2023" and, in 2003, "...Biotechnology".
    titles = [str(t) for _, t in keys]
    home = titles.index("database resources of the national center for biotechnology information")
    sid[sid == titles.index("database resources of the national center for biotechnology information in")] = home
    sid[pmid == 12519941] = home
    idx = np.flatnonzero(sid >= 0)
    groups = collections.defaultdict(list)
    for i, s in zip(idx.tolist(), sid[idx].tolist()):
        groups[s].append(i)
    slug = dict(db().execute("SELECT id, slug FROM journals"))
    out = collections.defaultdict(list)
    for s, rows in groups.items():
        rows.sort(key=lambda i: py[i])
        newest = int(pmid[rows[-1]])
        title = db().execute("SELECT title FROM papers WHERE pmid = ?", (newest,)).fetchone()[0]
        citable = [int(pmid[i]) for i in rows if dc[i] <= 3]
        out[slug[int(keys[s][0])]].append({"title": title, "items": len(rows), "pmids": citable, "citations": int(C[rows].sum())})
    for sl, series in out.items():
        series.sort(key=lambda x: -x["citations"])
        write_json(out_dir, f"series/{sl}.json", {"asOf": "Nov 2026", "series": series})
    write_json(out_dir, "series/index.json", sorted(out))
    return {"series": len(groups), "papers": len(idx), "journals": len(out)}


BLUE, VERMILION, GREEN, ORANGE, SKY, PURPLE, GRAY, INK = "#0072B2", "#D55E00", "#009E73", "#E69F00", "#56B4E9", "#CC79A7", "#8C8C8C", "#222222"
REGION_COLORS = [("USA", BLUE), ("Canada", PURPLE), ("Europe", ORANGE), ("China", VERMILION), ("Other Asia", GREEN), ("Rest of world", GRAY)]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NO_JUNE = [m for m in MONTHS if m != "Jun"]
NO_JUNE_NOTE = "June is left out, because papers with no month are dated June."


def num(r, k):
    return float(r[k])


def line(cid, title, note, labels, series, x, y, **kw):
    if labels is NO_JUNE:     # keep June on the axis, with no value
        labels = MONTHS
        series = [{**one, "data": one["data"][:5] + [None] + one["data"][5:]} for one in series]
    return {"id": cid, "type": "line", "title": title, "note": note, "labels": labels, "series": series, "x": x, "y": y, **kw}


def hbar(cid, title, note, labels, values, x, **kw):
    return {"id": cid, "type": "hbar", "title": title, "note": note, "labels": labels, "values": values, "x": x, **kw}


def s(label, data, color, **kw):
    return {"label": label, "data": data, "color": color, **kw}


def timing_charts():
    age = read_csv("v2/data/f1c_age_curve.csv")
    e = read_csv("v2/data/f1e_citations_per_year.csv")
    g = read_csv("v2/data/f1g_credit_by_month.csv")
    h = read_csv("v2/data/f1h_overall_by_month.csv")
    p = {r["measure"]: r for r in read_csv("v2/data/f1d_pairs_summary.csv")}
    ann = read_csv("v2/data/f2e_annual_reports.csv")
    credit = lambda who: [round(100 * (num(r, "credit") - 1), 2) for r in g if r["series"] == who and r["month"] != "Jun"]
    aged = lambda m: [round(100 * num(r, "vs_average_month"), 2) for r in h if r["months"] == m]
    series = list(dict.fromkeys(r["series"] for r in ann))
    month_axis = MONTHS + ["No month"]
    return [
        line("age_curve", "Citations by months since publication", "Mean citations per month for research articles published 2014\u201319. A JIF counts months 12\u201335 of a January paper and months 1\u201324 of a December paper.",
             [int(r["age_months"]) for r in age], [s("Research articles", [num(r, "mean_citations") for r in age], BLUE)], "Months since publication", "Mean citations per month"),
        line("per_year_by_month", "Citations per year, by publication month", "Research articles published 2010\u201322. A JIF counts the first two years after the publication year. " + NO_JUNE_NOTE,
             NO_JUNE, [s("First year", [num(r, "year_1") for r in e], BLUE), s("Second year", [num(r, "year_2") for r in e], GREEN), s("Third year (not counted)", [num(r, "year_3") for r in e], GRAY)],
             "Publication month", "Mean citations per year", yMin=0),
        line("jif_credit", "JIF credit by publication month", "What a JIF would count if the same paper came out in each month, against the average month. Papers published 2014\u201319, so highly cited papers weigh more, as in a JIF. " + NO_JUNE_NOTE,
             NO_JUNE, [s("Research articles", credit("Research articles"), BLUE), s("Reviews", credit("Reviews"), VERMILION)], "Publication month", "% vs the average month"),
        line("matched_age", "All citations by publication month, at matched ages", "Research articles published 2014\u201319, at the same age for every month, against the average month. " + NO_JUNE_NOTE,
             NO_JUNE, [s("First year", aged("12"), SKY), s("First 2 years", aged("24"), BLUE), s("First 3 years", aged("36"), GREEN), s("First 5 years", aged("60"), VERMILION)], "Publication month", "% vs the average month", yMin=-20, yMax=20),
        {"id": "pairs", "type": "hbar", "title": "Matched January and December papers", "note": f"{int(p['jif_counted']['pairs']):,} pairs from the same journal, year and article type, matched on citations at months 36\u201371. Mean citations per paper.",
         "labels": ["Citations a JIF counts", "First 24 months"], "series": [s("January paper", [num(p["jif_counted"], "jan_mean"), num(p["first_24_months"], "jan_mean")], BLUE), s("December paper", [num(p["jif_counted"], "dec_mean"), num(p["first_24_months"], "dec_mean")], ORANGE)], "x": "Mean citations per paper"},
        {"id": "timing_hist", "type": "hist", "measure": "timing", "title": "JIF change from papers published in early months, by journal", "note": "How much a journal's JIF-counted citations change because of which papers it published early in the year, compared with the same papers given shuffled months in each year. Items from 2014\u201321."},
        {"id": "annual_reports", "type": "bubble", "title": "When big annual reports come out", "note": "Publication month of eight annual reports and guideline series, 2010\u201322. Dot size shows mean citations per report in its first 24 months.",
         "xLabels": month_axis, "yLabels": series, "points": [{"x": month_axis.index(r["month"].replace("\n", " ")) if r["month"].replace("\n", " ") in month_axis else 12, "y": series.index(r["series"]), "v": num(r, "mean_citations_first_24_months"), "n": int(r["papers"])} for r in ann]},
    ]


def reliance_charts():
    t = read_csv("v2/data/f4b_top_paper_share_trend.csv")
    d = read_csv("v2/data/f4d_most_concentrated.csv")
    a = read_csv("v8/data/fig2a_recurring_series_merged.csv")
    g = read_csv("data/fig11_ranked_guidelines.csv")[:15]
    abbr = dict(db().execute("SELECT name, abbreviation FROM journals"))
    pct = lambda k: [round(100 * num(r, k), 2) for r in t]
    return [
        {"id": "top_paper_hist", "type": "hist", "measure": "top_paper", "title": "Share of citations from each journal's top paper", "note": "2024 citations to citable items from 2022\u201323, for journals with at least 50 items and 100 citations."},
        line("top_paper_trend", "Top paper's share of citations, by year", "The shaded area holds the middle 95% of journals.", [int(r["citation_year"]) for r in t],
             [s("97.5th percentile", pct("p97_5"), SKY, fill="+1"), s("2.5th percentile", pct("p2_5"), SKY), s("Median journal", pct("median"), BLUE)], "Citation year", "Share of citations (%)", yMin=0),
        hbar("most_reliant", "Journals most reliant on one paper", "Journals with at least 500 citable items, 2024. Hover to see the paper.", [r["journal"] for r in d], [round(100 * num(r, "top_paper_share"), 1) for r in d], "Top paper's share of 2024 citations (%)", hover=[r["top_title"] for r in d]),
        hbar("top_series", "Most-cited recurring series", "Titles repeating in at least three years of one journal, by lifetime citations.", [f"{r['series']} ({r['journal']})" for r in a], [int(r["lifetime_citations"]) for r in a], "Lifetime citations"),
        hbar("guideline_falls", "Largest falls in the rate without guidelines", "Journals with at least 300 citable items and reference lists for most of them, at November 2025, without items PubMed tags as guidelines.",
             [abbr.get(r["journal"], r["journal"]) for r in g], [round(-100 * num(r, "change"), 1) for r in g], "Fall in the 24-month rate (%)"),
    ]


OWNER_NOTE = "One entry per current owner: Elsevier includes Cell Press and the Lancet journals; Springer Nature includes Nature Portfolio, BMC and Cureus; Wiley includes Hindawi."
OWNER_COLORS = {"Other": "#E4E4E4", "BMJ": "#882255", "RSC": "#DDCC77", "SAGE": "#332288", "Oxford UP": "#999933", "ACS": "#8C510A", "Taylor & Francis": "#AA99DD", "Wolters Kluwer": "#117733",
                "Elsevier": GRAY, "Wiley": SKY, "Springer Nature": VERMILION, "AAAS": INK, "PLOS": BLUE, "Frontiers": GREEN, "MDPI": ORANGE}
OWNED = {"Hindawi": "Hindawi (Wiley)", "Cureus": "Cureus (Springer Nature)"}
TIER_COLORS = {"Nature": INK, "Cell": INK, "Science": INK, "Nature-branded research": VERMILION, "Cell-family research": VERMILION, "Science-branded": VERMILION, "Nature Reviews": PURPLE, "Trends reviews": PURPLE,
               "Nature Communications": ORANGE, "Cell Reports family": ORANGE, "Next four journals": ORANGE, "Communications, npj, Sci Data": SKY, "iScience": SKY,
               "Society and partner journals": GRAY, "Current Biol, partners, other": GRAY, "All other journals": GRAY, "Other PLOS journals": GRAY, "Other AAAS": GRAY}


def tier_color(group):
    """As in the paper's stacks: black flagship, orange flagship-named, pink reviews, yellow next tier, light blue newer broad, blue largest journal, gray the rest."""
    return TIER_COLORS.get(group, BLUE)


def publishing_charts():
    L = read_csv("v2/data/f7ab_lift_all_journals.csv")
    A = read_csv("data/fig6a_ranked.csv")
    F = read_csv("v2/data/f9_landscape.csv")
    def by_series(panel, scale=1):
        rows = [r for r in F if r["panel"] == panel]
        names = list(dict.fromkeys(r["series"] for r in rows))
        years = sorted({int(r["year_or_publisher"]) for r in rows})
        look = {(r["series"], int(r["year_or_publisher"])): num(r, "value") for r in rows}
        return names, years, lambda n: [round(look[(n, y)] * scale, 3) if (n, y) in look else None for y in years]
    colors = [VERMILION, BLUE, GREEN, ORANGE, PURPLE, SKY, GRAY, INK]
    names = sorted({r["journal"] for r in A}, key=lambda j: -max(int(r["citable_items"]) for r in A if r["journal"] == j))
    years = sorted({int(r["year"]) for r in A if int(r["year"]) >= 2005})
    look = {(r["journal"], int(r["year"])): int(r["citable_items"]) for r in A}
    largest = line("largest", "Largest journals", "Citable items per year, for the six largest journals by peak year, preprint servers left out.", years,
                   [s(n, [look.get((n, y)) for y in years], c) for n, c in zip(names, colors)], "Year", "Citable items per year", yMin=0)
    def owners(path, value, scale=100):
        rows = read_csv(path)
        names = list(dict.fromkeys(r["publisher"] for r in rows))
        years = sorted({int(r["year"]) for r in rows})
        look = {(r["publisher"], int(r["year"])): num(r, value) for r in rows}
        return years, [s(n, [round(look[(n, y)] * scale, 3) if (n, y) in look else None for y in years], OWNER_COLORS[n]) for n in names]
    sy, ss = owners("v8/data/s9b_publisher_share.csv", "share_of_citable_items")
    share = line("publisher_share", "Publishers' share of PubMed", f"Share of all PubMed citable items per year, for the seven publishers with the most reviews in 2023\u201325. {OWNER_NOTE}", sy, ss, "Year", "Share of citable items (%)", yMin=0)
    ry, rs = owners("v8/data/f2d_review_share.csv", "share")
    review = line("review_share", "Reviews, by publisher", f"Reviews as a share of citable items, for years with at least 500 items. {OWNER_NOTE}", ry, rs, "Year", "Reviews (%)", yMin=0)
    E = read_csv("v8/data/f1e_pubmed_by_publisher.csv")
    total = {"id": "by_publisher", "type": "stack", "title": "Citable items by publisher", "x": "Year", "y": "Citable items per year", "labels": [int(r["year"]) for r in E],
             "note": f"From each paper's DOI prefix. {OWNER_NOTE} A society's own prefix stays with the society, and \u201cAll others\u201d also holds papers with no DOI in journals with no clear publisher.",
             "series": [s("All others" if n == "Other" else n, [int(r[n]) for r in E], OWNER_COLORS[n]) for n in OWNER_COLORS]}
    D = [r for r in F if r["panel"] == "D"]
    G = read_csv("v8/data/s9dk_publisher_groups.csv")
    tiers = {}
    for fam in dict.fromkeys(r["publisher"] for r in G):
        rows = [r for r in G if r["publisher"] == fam]
        years = sorted({int(r["year"]) for r in rows})
        look = {(r["group"], int(r["year"])): int(r["citable_items"]) for r in rows}
        groups = list(dict.fromkeys(r["group"] for r in rows))
        tiers[OWNED.get(fam, fam)] = {"type": "stack", "labels": years, "series": [s(g, [look.get((g, y)) for y in years], tier_color(g)) for g in groups], "x": "Year", "y": "Citable items per year"}
    return [
        {"id": "lift_hist", "type": "hist", "measure": "lift", "title": "How much non-research items raise the rate", "note": "The 24-month rate for all citable items over the rate for research articles alone, at November 2025."},
        {"id": "lift_scatter", "type": "scatter", "title": "That rise against the share of reviews", "note": "Each dot is a journal, at November 2025. A few journals with a rise above 200% are off the chart.", "x": "Reviews as a share of citable items (%)", "y": "Rise over research-only rate (%)",
         "points": [{"x": round(100 * num(r, "review_share_items"), 1), "y": round(100 * num(r, "lift_from_reviews"), 1), "label": r["journal"], "slug": r["slug"]} for r in L], "yMin": -60, "yMax": 200},
        total, largest, share, review,
        hbar("review_journals", "Journals publishing the most reviews", "Reviews published 2023\u201325, any publisher.", [f"{r['series']} ({OWNED.get(r['year_or_publisher'], r['year_or_publisher']).replace('Cureus (Springer Nature)', 'Springer Nature')})" for r in D], [int(num(r, "value")) for r in D], "Reviews published, 2023\u201325"),
        {"id": "tiers", "type": "set", "title": "Publisher tiers", "note": "Citable items per year, stacked by journal group. Nature Portfolio is part of Springer Nature and Cell Press of Elsevier; Cell Press includes Current Biology, the Trends journals, Heliyon and partner titles. Cureus is one journal. The scale changes with the publisher unless shared scale is ticked.", "sets": tiers, "sharedScale": True},
    ]


def people_charts():
    I = read_csv("v10/data/f11a_institutions.csv")
    R = read_csv("v10/data/f11b_regions.csv")
    C = read_csv("v10/data/f11c_concentration.csv")
    D = read_csv("v10/data/f11d_over_representation.csv")
    A = read_csv("data/fig4a_author_count_buckets.csv")
    B = read_csv("data/fig4b_papers_100plus_authors_by_year.csv")
    journals = ["nature", "science", "cell", "nejm", "lancet"]
    names = ["Nature", "Science", "Cell", "NEJM", "Lancet"]
    colors = dict(zip(["North America", "Europe", "China", "Other Asia", "Rest of world"], [BLUE, ORANGE, VERMILION, GREEN, GRAY]))
    with_flagship = [r for r in I if int(r["flagship_papers"]) > 0]
    return [
        {"id": "institution_moves", "type": "institutions", "title": "Where flagship papers came from, 2001\u20132025",
         "note": "Each dot is an institution with at least 200 first-author papers in 2001\u201325, and moves through five-year windows, one year apart. Across, its share of all PubMed papers; up, its share of papers in Nature, Science, Cell, NEJM and Lancet. Dot size is its flagship papers. Each paper counts once, for its first author's first-named institution, because PubMed kept only that affiliation until about 2014. Name variants are merged by rule: schools and medical centers carrying a university's name count with that university, joint names go to the first-named institution, and hospitals with their own names stay separate. Search for an institution to follow it, or click a dot.",
         "defaults": ["Stanford University", "Chinese Academy of Sciences", "Tsinghua University"]},
        {"id": "institutions", "type": "scatter", "title": "Institution links in all journals and in five flagships", "note": "Each dot is an institution with at least 1,000 PubMed papers in 2021\u201325 and a paper in Nature, Science, Cell, NEJM or Lancet. A link is one institution on one paper. Log scales.",
         "x": "Share of links, all PubMed journals (%)", "y": "Share of links, five flagships (%)", "log": True, "diagonal": True,
         "points": [{"x": round(100 * num(r, "share_all"), 5), "y": round(100 * num(r, "share_flagship"), 5), "label": r["institution"].title(), "color": colors[r["region"]]} for r in with_flagship], "groups": colors},
        {"id": "institution_regions", "type": "hbar", "title": "Share of links by region", "note": "Links to large institutions, 2021\u201325.", "labels": [r["region"] for r in R],
         "series": [s("All journals", [round(100 * num(r, "all_journals"), 1) for r in R], INK)] + [s(n, [round(100 * num(r, j), 1) for r in R], c) for n, j, c in zip(names, journals, [BLUE, SKY, GREEN, ORANGE, VERMILION])], "x": "Share of links (%)"},
        {"id": "concentration", "type": "hbar", "title": "Share of links from each journal's top institutions", "note": "Each journal's top 10, 50 and 100 institutions, against a random draw of the same size from all journals.", "labels": [r["journal"] for r in C],
         "series": [s("Top 100", [round(100 * num(r, "top_100"), 1) for r in C], VERMILION), s("Top 100, random draw", [round(100 * num(r, "expected_top_100"), 1) for r in C], "#F0B896"),
                    s("Top 10", [round(100 * num(r, "top_10"), 1) for r in C], BLUE), s("Top 10, random draw", [round(100 * num(r, "expected_top_10"), 1) for r in C], "#9CC7E0")], "x": "Share of links (%)"},
        {"id": "with_a_paper", "type": "stack", "title": "Large institutions with a paper in each journal", "note": "Split by the institution's share of the journal's links against its share of all links.", "labels": [r["journal"] for r in D],
         "series": [s("Under 1\u00d7", [round(100 * num(r, "under_1x"), 1) for r in D], SKY), s("1\u20135\u00d7", [round(100 * num(r, "from_1_to_5x"), 1) for r in D], BLUE), s("Over 5\u00d7", [round(100 * num(r, "over_5x"), 1) for r in D], VERMILION)],
         "bars": True, "x": "Journal", "y": "Share of large institutions (%)"},
        line("author_counts", "Papers and citations by author count", "Biomedical citable items, 2003\u20132026. Citations credited to authors are each paper's citations multiplied by its authors.", [r["authors"] for r in A],
             [s("Papers", [num(r, "share_of_papers") * 100 for r in A], GRAY), s("Citations", [num(r, "share_of_citations") * 100 for r in A], BLUE), s("Citations credited to authors", [num(r, "share_of_author_credited_citations") * 100 for r in A], VERMILION)],
             "Authors per paper", "Share of total (%, log scale)", yLog=True),
        line("author_trend", "Papers with 100+ authors", "Per 10,000 biomedical citable items, by year published.", [int(r["year"]) for r in B], [s("Papers with 100+ authors", [num(r, "per_10000_papers") for r in B], BLUE)], "Year published", "Per 10,000 papers", yMin=0),
    ]


def geography_charts():
    b = read_csv("v2/data/f10b_fig13_us_vs_europe.csv")
    c = read_csv("v2/data/f10c_regional_journals.csv")
    t = read_csv("v2/data/f10alt_citing_regions_by_year.csv")
    sets = {}
    for name in dict.fromkeys(r["journal"] for r in t):
        rows = [r for r in t if r["journal"] == name]
        sets[name] = {"type": "stack", "labels": [int(r["citation_year"]) for r in rows], "series": [s(g, [round(100 * num(r, g), 1) for r in rows], col) for g, col in REGION_COLORS], "x": "Citation year", "y": "Share of citations (%)", "max": 100}
    return [
        {"id": "home_gap", "type": "hbar", "title": "USA minus Europe citing share, US and European journal pairs", "note": "Share of 2024 citations from the USA minus share from Europe, for 17 pairs.", "labels": [f"{r['us_journal']} / {r['european_journal']}" for r in b],
         "series": [s("US journal", [round(100 * (num(r, "us_journal_us_share") - num(r, "us_journal_europe_share")), 1) for r in b], BLUE), s("European journal", [round(100 * (num(r, "european_journal_us_share") - num(r, "european_journal_europe_share")), 1) for r in b], "#B97F00")], "x": "Points"},
        {"id": "regional_journals", "type": "hbar", "title": "Top journals of each region", "note": "The five highest-rate journals of each region. A journal's home region is the one with at least half of its authors, not where it is based.", "labels": [f"{r['journal']} ({r['region']})" for r in c],
         "series": [s("Authors from home", [round(100 * num(r, "author_share"), 1) for r in c], GREEN), s("Citers from home", [round(100 * num(r, "citing_share"), 1) for r in c], VERMILION)], "x": "Share from the home region (%)"},
        {"id": "citers_over_time", "type": "set", "title": "Citing authors over time, society journals in the US and Europe", "note": "Citations in each year to citable items from the two previous years, by country or region of the citing authors, from 2014, when PubMed began recording every author's affiliation. 2025 citations are still arriving.", "sets": sets},
    ]


def retraction_charts():
    T = read_csv("data/fig7_retractions.csv")
    P = read_csv("v9/data/fig7c_ranked.csv")
    E = read_csv("v2/data/f12e_around_retraction.csv")
    H = read_csv("v2/data/f12h_by_age.csv")
    def stack(panel, cid, title, note):
        r = [x for x in T if x["panel"] == panel]
        return {"id": cid, "type": "stack", "title": title, "note": note, "labels": [int(x["year"]) for x in r], "bars": True, "x": "Year", "y": "Papers",
                "series": [s("Other publishers", [num(x, "a") for x in r], GRAY), s("Hindawi", [num(x, "b") for x in r], VERMILION)]}
    D = sorted((x for x in T if x["panel"] == "D"), key=lambda x: -num(x, "a"))
    sets = {}
    for y in sorted({int(r["retracted_in_year"]) for r in H}):
        r = [x for x in H if int(x["retracted_in_year"]) == y]
        sets[f"Retracted in year {y}"] = {"type": "line", "labels": [int(x["year_since_publication"]) for x in r], "series": [s("Retracted papers", [num(x, "retracted_mean") for x in r], VERMILION), s("Matched controls", [num(x, "controls_mean") for x in r], BLUE)],
                                          "x": "Year since publication (1 = year published)", "y": "Citations per paper", "yMin": 0, "mark": y}
    return [
        stack("A", "by_year_published", "Retracted papers, by year published", "Retracted papers in PubMed journals. Sources: Retraction Watch and PubMed."),
        stack("B", "by_year_retracted", "Retracted papers, by year retracted", "Dated retractions only."),
        hbar("publisher_rate", "Retraction rate by publisher", "Retracted papers per 10,000 citable items published 2015\u201323, for every publisher with at least 20,000 items, by current owner. Hindawi, bought by Wiley in January 2021, is shown apart from the rest of Wiley.", [OWNED.get(r["publisher"], r["publisher"]) for r in P], [num(r, "per_10000") for r in P], "Retracted per 10,000 citable items"),
        hbar("most_retractions", "Journals with the most retractions", "All years. The hover text gives retracted papers as a share of the journal's citable items.", [r["series"].split(" : ")[0] for r in D], [int(num(r, "a")) for r in D], "Retracted papers", hover=[f"{100 * num(r, 'b'):.1f}% of citable items" for r in D]),
        line("around_retraction", "Citations per year before and after retraction", f"Mean citations per paper for {int(E[0]['papers']):,} papers retracted 2010\u201319, at least 4 years after publication, against controls from the same journal, year and article type with similar citations before retraction.",
             [int(r["years_from_retraction"]) for r in E], [s("Retracted papers", [num(r, "retracted_mean") for r in E], VERMILION), s("Matched controls", [num(r, "controls_mean") for r in E], BLUE)], "Years from retraction (0 = year retracted)", "Citations per paper per year", yMin=0),
        {"id": "by_age", "type": "set", "title": "Citations by paper age, by the year of retraction", "note": "Mean citations per paper with the same controls. Later years hold fewer, older papers; points with fewer than 100 papers aren't shown.", "sets": sets},
    ]


def export_landscape(out_dir=OUT):
    """landscape.json: chart specs for the site-wide figures, from the CSVs behind the paper's figures."""
    groups = [("timing", "Publication timing", timing_charts), ("reliance", "Reliance on few papers", reliance_charts), ("publishing", "Publishing", publishing_charts),
              ("people", "Institutions and authors", people_charts), ("geography", "Geography", geography_charts), ("retractions", "Retractions", retraction_charts)]
    data = {"asOf": "Nov 2026", "groups": [{"id": i, "label": label, "charts": build()} for i, label, build in groups]}
    write_json(out_dir, "landscape.json", data)
    return {g["id"]: len(g["charts"]) for g in data["groups"]}


def export_bubbles(out_dir=OUT):
    """institution_bubbles.json: first-author papers per institution per year, from data/analysis/institution_years.npz (10-31-26/scripts/v7_inst_years.py)."""
    D = np.load(os.path.join(ANALYSIS, "institution_years.npz"))
    first = int(D["first_year"])
    years = D["all"].shape[1]
    rows = [[str(n).removeprefix("The "), int(r), a.tolist(), f.tolist() if f.any() else []] for n, r, a, f in zip(D["names"], D["region"], D["all"], D["flag"])]
    data = {"asOf": "Nov 2026", "firstYear": first, "lastYear": first + years - 1, "window": 5, "regions": [{"name": str(n), "color": str(c)} for n, c in zip(D["regions"], D["colors"])],
            "denomAll": D["denom_all"].tolist(), "denomFlag": D["denom_flag"].tolist(), "regionAll": D["reg_all"].tolist(), "regionFlag": D["reg_flag"].tolist(), "institutions": rows}
    write_json(out_dir, "institution_bubbles.json", data)
    return len(rows)


def main():
    jobs = {"retractions": export_retractions, "measures": export_measures, "citers": export_citers, "series": export_series, "landscape": export_landscape, "bubbles": export_bubbles}
    for name in sys.argv[1:] or list(jobs):
        print(name, jobs[name](), flush=True)


if __name__ == "__main__":
    main()
