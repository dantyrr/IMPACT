"""Ranks the journals, papers and publishers the figures name, so each example can rest on a stated rule rather than on
a hand-picked list. Reads the same data as the figures; changes no figure. Prints to stdout and writes
data/audit_*.csv. Usage: python 10-31-26/scripts/audit_examples.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import (C, DATA, TREND, citable, con, concentration, dc, jid, jname, np, pmid, py, slug2id, window,
                          write_csv)

CHECK = ["ca-a-cancer-journal-for-clinicians", "circulation", "autophagy", "cell", "nejm", "nature", "nature-communications",
         "diabetes-care", "european-heart-journal", "international-journal-of-surgery-london-england",
         "journal-of-the-american-geriatrics-society"]
abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
name = lambda j: abbr.get(j) or jname[j]


def show(title, rows, n=12):
    print(f"\n## {title}")
    for i, r in enumerate(rows[:n], 1):
        print(f"{i:3}", *r)


def rank_of(sorted_ids, slugs):
    pos = {j: i + 1 for i, j in enumerate(sorted_ids)}
    return {s: pos.get(slug2id[s]) for s in slugs}


# Figure 1: single-paper dependence, one year and sustained
r24 = concentration(2024)
for floor in (200, 500):
    ids = sorted((k for k in r24 if r24[k]["items"] >= floor), key=lambda k: -r24[k]["top1"])
    show(f"Fig 1: 2024 top-paper share, journals with {floor}+ citable items (of {len(ids)})",
         [[name(k), r24[k]["items"], f"{r24[k]['rate']:.1f}->{r24[k]['rate_wo']:.1f}", f"{r24[k]['top1']:.0%}"] for k in ids])
    print("  ranks:", rank_of(ids, CHECK))
years = range(2012, 2025)
share = collections.defaultdict(dict)
for Y in years:
    for k, v in concentration(Y).items():
        share[k][Y] = (v["top1"], v["rate"], v["rate_wo"], v["items"])
full = {k: v for k, v in share.items() if len(v) == len(years)}
mean = {k: np.mean([x[0] for x in v.values()]) for k, v in full.items()}
for floor in (0, 200):
    ids = sorted((k for k in mean if np.mean([x[3] for x in full[k].values()]) >= floor), key=lambda k: -mean[k])
    show(f"Fig 1C: mean top-paper share 2012-24, every year qualifying, mean items {floor}+ (of {len(ids)})",
         [[name(k), f"{mean[k]:.0%}", f"min {min(x[0] for x in full[k].values()):.0%}",
           f"items {np.mean([x[3] for x in full[k].values()]):.0f}"] for k in ids])
    print("  ranks:", rank_of(ids, CHECK))
write_csv("audit_top_paper_sustained", ["journal", "mean_top_paper_share_2012_24"], [[jname[k], round(mean[k], 4)] for k in sorted(mean, key=lambda k: -mean[k])])

# Figure 2B: share of citations going to series items
sid = np.load(os.path.join(DATA, "series_v2.npz"), allow_pickle=True)["sid"]
in_s = sid >= 0
rows = {}
for Y in range(2015, 2025):
    idx, c = window(Y)
    tot = np.bincount(jid[idx], weights=c)
    ser = np.bincount(jid[idx], weights=c * in_s[idx], minlength=len(tot))
    n = np.bincount(jid[idx], minlength=len(tot))
    for k in np.flatnonzero((n >= 100) & (tot >= 500)):
        rows.setdefault(int(k), {})[Y] = ser[k] / tot[k]
m = {k: np.mean(list(v.values())) for k, v in rows.items() if len(v) == 10}
ids = sorted(m, key=lambda k: -m[k])
show(f"Fig 2B: mean series share of citations 2015-24, 100+ items and 500+ citations every year (of {len(ids)})",
     [[name(k), f"{m[k]:.0%}", f"2024 {rows[k][2024]:.0%}"] for k in ids], 15)
print("  ranks:", rank_of(ids, ["circulation", "diabetes-care", "european-heart-journal"]))

# Figure 4C: most authors
a = np.load(os.path.join(DATA, "author_counts.npz"))
o = np.argsort(-a["n"])[:60]
big = [(int(a["pmid"][i]), int(a["n"][i])) for i in o]
marks = ",".join("?" * len(big))
t = {r[0]: r[1:] for r in con.execute(f"SELECT pmid, journal_id, pub_year, title FROM papers WHERE pmid IN ({marks})", [b[0] for b in big])}
show("Fig 4C: papers with the most authors (all journals)", [[n, name(t[p][0]), t[p][1], t[p][2][:70]] for p, n in big if p in t], 30)

# Figure 6A and 6H: largest journals
yrs = np.arange(2010, 2026)
tot = np.zeros((len(yrs), int(jid.max()) + 1), np.int64)
for i, Y in enumerate(yrs):
    tot[i] = np.bincount(jid[citable & (py == Y)], minlength=tot.shape[1])
peak = tot.max(axis=0)
ids = np.argsort(-peak)[:12]
show("Fig 6A: journals by peak citable items in one year, 2010-25",
     [[name(int(k)), int(peak[k]), int(yrs[tot[:, k].argmax()]), f"2024: {tot[-2, k]}", f"2025: {tot[-1, k]}"] for k in ids], 12)
ids = np.argsort(-tot[-2])[:12]
show("Fig 6H: journals by 2024 citable items", [[name(int(k)), int(tot[-2, k])] for k in ids], 12)

# Figure 7: retractions by publisher (every named prefix) and by journal
R = np.load(os.path.join(DATA, "retractions.npz"))
P = np.load(os.path.join(DATA, "publishers.npz"), allow_pickle=True)
retr = np.isin(pmid, R["pmid"])
assert (P["pmid"] == pmid).all()
m = citable & (py >= 2015) & (py <= 2023)
out = []
for i, nm in enumerate(P["names"]):
    s = m & (P["code"] == i)
    if s.sum() >= 20000:
        out.append((nm, int(s.sum()), int((s & retr).sum()), (s & retr).sum() / s.sum() * 1e4))
out.sort(key=lambda r: -r[3])
show("Fig 7C: retracted per 10,000 citable items 2015-23, publishers with 20,000+ items", [[r[0], r[1], r[2], f"{r[3]:.0f}"] for r in out], 26)
n_all = np.bincount(jid[citable], minlength=tot.shape[1])
n_r = np.bincount(jid[citable & retr], minlength=tot.shape[1])
ids = np.argsort(-n_r)[:12]
show("Fig 7D: journals by retracted papers", [[name(int(k)), int(n_r[k]), f"{n_r[k] / n_all[k]:.1%}"] for k in ids], 12)
hind = P["names"].tolist().index("Hindawi")
hj = np.bincount(jid[citable & (P["code"] == hind)], minlength=tot.shape[1])
hr = np.bincount(jid[citable & (P["code"] == hind) & retr], minlength=tot.shape[1])
ids = sorted(np.flatnonzero(hj >= 500), key=lambda k: -hr[k])
show("Fig 7E-F: Hindawi journals by retracted papers (500+ items)", [[name(int(k)), int(hr[k]), f"{hr[k] / hj[k]:.1%}", int(hj[k])] for k in ids], 10)
ids = sorted(np.flatnonzero(hj >= 500), key=lambda k: -hr[k] / hj[k])
show("Fig 7E-F: Hindawi journals by retracted share (500+ items)", [[name(int(k)), f"{hr[k] / hj[k]:.1%}", int(hr[k])] for k in ids], 10)

# Figure 9: labelled journals
T = list(csv.DictReader(open("10-31-26/data/fig9_journal_timing.csv")))
num = lambda r, k: float(r[k]) if r[k] not in ("", "nan") else None
b = sorted((r for r in T if num(r, "placement_gain") is not None and int(r["items_2014_21"]) >= 2000),
           key=lambda r: -abs(num(r, "placement_gain")))
show("Fig 9B: largest placement gain or loss, journals with 2,000+ items (2014-21)",
     [[r["abbreviation"], r["items_2014_21"], f"{num(r, 'placement_gain'):+.1%}", f"z {r['placement_z']}"] for r in b], 12)
c = [r for r in T if r["reviews_fdr_q"] and float(r["reviews_fdr_q"]) < 0.05 and int(r["reviews"]) >= 100]
c.sort(key=lambda r: -(float(r["reviews_jan_mar"]) - float(r["other_jan_mar"])))
show("Fig 9C: reviews most front-loaded vs other items, FDR<5%, 100+ reviews",
     [[r["abbreviation"], r["reviews"], f"{float(r['reviews_jan_mar']):.0%} vs {float(r['other_jan_mar']):.0%}"] for r in c], 12)

# Figure 10: labelled outliers
W = list(csv.DictReader(open("10-31-26/data/fig10_journal_windows.csv")))
W.sort(key=lambda r: -abs(float(r["pct_rank_change_delayed_vs_jif"])))
show("Fig 10A: largest rank moves", [[r["journal"], r["items"], r["pct_rank_change_delayed_vs_jif"]] for r in W], 10)

# Figure 11: guideline lift among large journals
G = []
import glob
import json
from type_effect import CITABLE, JSON, rate, settled_month, without
for path in glob.glob(os.path.join(JSON, "*.json")):
    d = json.load(open(path))
    if not d.get("timeseries"):
        continue
    end = settled_month(d)
    e = next(p for p in d["timeseries"] if p["month"] == end)
    n = sum(e.get("by_type", {}).get(t, {}).get("papers", 0) for t in CITABLE)
    f, w = rate(e, CITABLE), rate(e, without("guideline"))
    if f and w is not None and n >= 300:
        G.append((d["journal"][:48], n, e["by_type"].get("guideline", {}).get("papers", 0), round(f, 2), round(w, 2), (w - f) / f))
G.sort(key=lambda r: r[5])
show("Fig 11: largest fall without guidelines, 300+ citable items", [[*r[:5], f"{r[5]:.0%}"] for r in G], 15)
print("  Circulation rank:", next((i + 1 for i, r in enumerate(G) if r[0] == "Circulation"), None), "of", len(G))
