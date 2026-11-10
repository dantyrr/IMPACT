"""
Figures 6 and 7 for the JIF paper (10-31-26): open-access mega-journals and tiered
publishing, and retractions. Reads cites.npz, publishers.npz and retractions.npz
(see build_matrix.py and publishers_retractions.py).

Usage:
    python 10-31-26/scripts/more_figures.py          # both
    python 10-31-26/scripts/more_figures.py 7        # only figure 7
    python 10-31-26/scripts/more_figures.py notices  # 7I-7M without retraction-notice citations (new files)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import (BLUE, VERMILION, GREEN, PURPLE, GRAY, INK, MUTED, DATA, Y0, C, con, dc, jid,  # noqa: E402
                          matplotlib, np, plt, pm, pmid, py, save, slug2id, write_csv, jname)

ORANGE, SKY, YELLOW = "#E69F00", "#56B4E9", "#F0E442"
citable = dc <= 3
YEARS = np.arange(2005, 2026)
SUFFIX, NOTE = "", ""                    # set by exclude_notice_citations()

P = np.load(os.path.join(DATA, "publishers.npz"))
PUB_NAMES = list(P["names"])
_code = np.full(pmid.max() + 1, -1, np.int8)
_code[P["pmid"]] = P["code"]
pub = _code[pmid]

R = np.load(os.path.join(DATA, "retractions.npz"))
_ret = np.zeros(pmid.max() + 1, bool)
_ret[R["pmid"][R["pmid"] <= pmid.max()]] = True
retracted = _ret[pmid]


def is_pub(name):
    return pub == PUB_NAMES.index(name)


def per_year(mask):
    y = py[mask].astype(np.int64) - YEARS[0]
    y = y[(y >= 0) & (y < len(YEARS))]
    return np.bincount(y, minlength=len(YEARS)).astype(float)


def spread_labels(ax, items, x, gap):
    """items: [(y, text, color)]; labels right of x, nudged apart by at least gap (data units)."""
    last = -1e18
    for y, text, col in sorted(items):
        yl = max(y, last + gap)
        ax.annotate(text, (x, y), xytext=(x + 0.6, yl), textcoords="data", fontsize=6.3, va="center", color=INK,
                    arrowprops=dict(arrowstyle="-", color=col, linewidth=0.6, shrinkA=0, shrinkB=0))
        last = yl


def end_label(ax, x, y, text, dy=0, color=INK):
    ax.annotate(text, (x, y), xytext=(4, dy), textcoords="offset points", va="center", fontsize=6.5, color=color)


# ---------------------------------------------------------------- Figure 6
MEGA = [("plos-one", "PLOS ONE", BLUE), ("scientific-reports", "Scientific Reports", VERMILION),
        ("cureus", "Cureus", GREEN), ("heliyon", "Heliyon", PURPLE),
        ("international-journal-of-molecular-sciences", "Int J Mol Sci", ORANGE),
        ("nature-communications", "Nat Commun", SKY)]
OA_PUBS = [("MDPI", ORANGE), ("Frontiers", GREEN), ("Nature Portfolio", VERMILION), ("PLOS", BLUE),
           ("Cureus", PURPLE), ("Hindawi", SKY)]
# List prices for one standard article, USD. Ceilings: waivers, discounts and institutional
# deals make real revenue lower. CHF converted at 1.15 USD.
APC = [("scientific-reports", "Scientific Reports", 2850, "DOAJ listing, 2025"),
       ("nature-communications", "Nature Communications", 6790, "DOAJ listing, 2025"),
       ("plos-one", "PLOS ONE", 2477, "plos.org/publish/fees"),
       ("international-journal-of-molecular-sciences", "Int J Mol Sci", round(2900 * 1.15), "CHF 2,900, third-party listing"),
       ("cancers", "Cancers", round(2900 * 1.15), "CHF 2,900, mdpi.com/journal/cancers/apc"),
       ("frontiers-in-immunology", "Front Immunol", round(3150 * 1.15), "CHF 3,150, third-party listing")]


def nature_tier(name):
    n = name.lower()
    if n == "nature":
        return "Nature"
    if n.startswith("nature reviews"):
        return "Nature Reviews"
    if n == "nature communications":
        return "Nature Communications"
    if n.startswith("nature "):
        return "Nature-branded research"
    if n == "scientific reports":
        return "Scientific Reports"
    if n.startswith(("communications ", "npj ", "scientific data")):
        return "Communications, npj, Sci Data"
    return "Society and partner journals"


NATURE_TIERS = [("Nature", INK), ("Nature-branded research", VERMILION), ("Nature Reviews", PURPLE),
                ("Nature Communications", ORANGE), ("Communications, npj, Sci Data", SKY), ("Scientific Reports", BLUE),
                ("Society and partner journals", GRAY)]
CELL_TIERS = [("Cell", ["cell"], INK),
              ("Cell-family research", ["immunity", "neuron", "molecular-cell", "cell-metabolism", "cell-stem-cell",
                                        "cancer-cell", "developmental-cell", "cell-host-microbe", "cell-chemical-biology",
                                        "cell-systems", "chem"], VERMILION),
              ("Cell Reports family", ["cell-reports", "cell-reports-medicine", "cell-reports-methods"], ORANGE),
              ("iScience", ["iscience"], SKY), ("Heliyon", ["heliyon"], BLUE)]
AAAS_TIERS = [("Science", ["science"], INK),
              ("Science-branded", ["science-translational-medicine", "science-immunology", "science-signaling",
                                   "science-robotics"], VERMILION),
              ("Science Advances", ["science-advances"], BLUE)]


def stacked(ax, layers, title, alpha=0.9):
    """layers: [(label, counts per year, color)]; direct labels at the right edge."""
    bottom = np.zeros(len(YEARS))
    for lab, v, col in layers:
        ax.fill_between(YEARS, bottom, bottom + v, color=col, linewidth=0, alpha=alpha, step=None)
        bottom = bottom + v
    ax.set_xlim(YEARS[0], YEARS[-1])
    ax.set_title(title, loc="left", fontsize=8.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 1000 else f"{v:.0f}"))
    ax.set_xticks([2005, 2015, 2025])
    ax.tick_params(labelsize=7)
    handles = [matplotlib.patches.Patch(color=c, label=l) for l, _, c in layers][::-1]
    ax.legend(handles=handles, fontsize=5.8, loc="upper left", handlelength=0.9, borderaxespad=0.2, labelspacing=0.25)


def fig6():
    print("Figure 6: open-access mega-journals and tiered publishing")
    fig = plt.figure(figsize=(7.2, 9.2))
    gs = fig.add_gridspec(3, 6, height_ratios=[1.1, 1, 1], hspace=0.55, wspace=1.4)
    rows = []

    # A: mega-journals
    ax = fig.add_subplot(gs[0, :3])
    ends = []
    for s, lab, col in MEGA:
        v = per_year(citable & (jid == slug2id[s]))
        ax.plot(YEARS, v, color=col, linewidth=1.6)
        ends.append((v[-1], lab, col))
        rows += [["A", lab, int(y), int(n)] for y, n in zip(YEARS, v)]
    spread_labels(ax, ends, YEARS[-1], 2600)
    ax.set_xlim(YEARS[0], YEARS[-1] + 7)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    ax.set_ylabel("Citable items per year")
    ax.set_ylim(0, None)
    ax.set_title("A  Mega-journals", loc="left", fontsize=8.5)

    # B: publisher share of all PubMed citable items
    ax = fig.add_subplot(gs[0, 3:])
    tot = per_year(citable)
    ends = []
    for name, col in OA_PUBS:
        v = per_year(citable & is_pub(name)) / tot
        ax.plot(YEARS, v, color=col, linewidth=1.6)
        ends.append((v[-1], name, col))
        rows += [["B", name, int(y), round(float(s), 5)] for y, s in zip(YEARS, v)]
    spread_labels(ax, ends, YEARS[-1], 0.006)
    ax.set_xlim(YEARS[0], YEARS[-1] + 7)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_ylabel("Share of all citable items")
    ax.set_title("B  Open-access publishers' share of PubMed", loc="left", fontsize=8.5)

    # C: review share by publisher
    ax = fig.add_subplot(gs[1, :3])
    ends = []
    for name, col in OA_PUBS[:4] + [("Elsevier", GRAY)]:
        m = citable & is_pub(name)
        n, r = per_year(m), per_year(m & (dc == 1))
        ok = n >= 500
        v = np.where(ok, r / np.maximum(n, 1), np.nan)
        ax.plot(YEARS, v, color=col, linewidth=1.6)
        ends.append((v[-1], name, col))
        rows += [["C", name, int(y), round(float(s), 4)] for y, s in zip(YEARS, v) if s == s]
    allr = per_year(citable & (dc == 1)) / tot
    ax.plot(YEARS, allr, color=INK, linewidth=1.2, linestyle="--")
    ends.append((allr[-1], "All journals", INK))
    spread_labels(ax, ends, YEARS[-1], 0.025)
    ax.set_xlim(YEARS[0], YEARS[-1] + 7)
    ax.set_xticks([2005, 2010, 2015, 2020, 2025])
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_ylabel("Reviews as share of citable items")
    ax.set_title("C  Reviews, by publisher", loc="left", fontsize=8.5)

    # D: review share, largest Frontiers and MDPI journals vs the field
    ax = fig.add_subplot(gs[1, 4:])
    m25 = citable & (py >= 2023) & (py <= 2025)
    big = []
    for name, col in [("Frontiers", GREEN), ("MDPI", ORANGE)]:
        mm = m25 & is_pub(name)
        js, n = np.unique(jid[mm], return_counts=True)
        for j in js[np.argsort(-n)][:6]:
            sel = mm & (jid == j)
            big.append((float((dc[sel] == 1).mean()), jname[int(j)], col, int(sel.sum())))
    big.sort()
    yy = np.arange(len(big))
    ax.barh(yy, [b[0] for b in big], color=[b[2] for b in big], height=0.7)
    ax.axvline(float((dc[m25] == 1).mean()), color=INK, linewidth=0.9, linestyle="--")
    ax.text(float((dc[m25] == 1).mean()), len(big) - 0.3, " all journals", fontsize=6, va="bottom")
    clean = lambda n: n.replace(" (Basel, Switzerland)", "").replace("International journal of", "Int J").replace("Frontiers in", "Front")
    ax.set_yticks(yy, [f"{clean(b[1])[:28]} ({b[3]:,})" for b in big], fontsize=6)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Reviews, 2023–25")
    ax.set_title("D  Biggest Frontiers (green)\n     and MDPI (orange) journals", loc="left", fontsize=8.5, x=-1.0)
    rows += [["D", b[1], "2023-2025", round(b[0], 4)] for b in big]

    # E: tiers within publisher families
    name_by_id = jname
    nat = citable & is_pub("Nature Portfolio")
    tier_of = {int(j): nature_tier(name_by_id[int(j)]) for j in np.unique(jid[nat])}
    layers = [(t, per_year(nat & np.isin(jid, [j for j, x in tier_of.items() if x == t])), c) for t, c in NATURE_TIERS]
    stacked(fig.add_subplot(gs[2, :2]), layers, "E  Nature Portfolio")
    rows += [["E", t, int(y), int(n)] for t, v, _ in layers for y, n in zip(YEARS, v)]
    for k, (fam, tiers_) in enumerate([("Cell Press", CELL_TIERS), ("AAAS", AAAS_TIERS)]):
        layers = []
        for t, slugs, col in tiers_:
            ids = [slug2id[s] for s in slugs if s in slug2id]
            layers.append((t, per_year(citable & np.isin(jid, ids)), col))
        stacked(fig.add_subplot(gs[2, 2 + 2 * k:4 + 2 * k]), layers, f"{'F' if k == 0 else 'G'}  {fam}")
        rows += [["F" if k == 0 else "G", t, int(y), int(n)] for t, v, _ in layers for y, n in zip(YEARS, v)]
    fig.axes[-3].set_ylabel("Citable items per year")
    write_csv("fig6_open_access", ["panel", "series", "year", "value"], rows)
    save(fig, "fig6_open_access_and_tiers")

    # Fee income at list price, 2024 (its own small figure: the prices carry the most doubt)
    fig, ax = plt.subplots(figsize=(4.2, 2.2))
    vals = []
    for s, lab, apc, src in APC:
        n = int((citable & (jid == slug2id[s]) & (py == 2024)).sum())
        vals.append((n * apc, lab, n, apc, src))
    vals.sort()
    yy = np.arange(len(vals))
    ax.barh(yy, [v[0] / 1e6 for v in vals], color=BLUE, height=0.65)
    for y, v in zip(yy, vals):
        ax.text(v[0] / 1e6 + 1, y, f"${v[0] / 1e6:.0f}M  ({v[2]:,} × ${v[3]:,})", va="center", fontsize=6.3)
    ax.set_yticks(yy, [v[1] for v in vals], fontsize=7)
    ax.set_xlim(0, max(v[0] for v in vals) / 1e6 * 1.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("2024 citable items × list APC (millions USD, a ceiling)")
    ax.set_title("H  Article fees at list price, 2024", loc="left", fontsize=8.5)
    write_csv("fig6h_apc_ceiling", ["journal", "citable_items_2024", "list_apc_usd", "ceiling_usd", "apc_source"],
              [[v[1], v[2], v[3], v[0], v[4]] for v in vals])
    save(fig, "fig6h_article_fees")


# ---------------------------------------------------------------- Figure 7
HINDAWI = ["computational-intelligence-and-neuroscience", "journal-of-healthcare-engineering",
           "computational-and-mathematical-methods-in-medicine", "evidence-based-complementary-and-alternative-medicine-ecam",
           "biomed-research-international", "oxidative-medicine-and-cellular-longevity"]
SHORT_H = {"computational-intelligence-and-neuroscience": "Comput Intell Neurosci",
           "journal-of-healthcare-engineering": "J Healthc Eng",
           "computational-and-mathematical-methods-in-medicine": "Comput Math Methods Med",
           "evidence-based-complementary-and-alternative-medicine-ecam": "Evid Based Complement Altern Med",
           "biomed-research-international": "BioMed Res Int", "oxidative-medicine-and-cellular-longevity": "Oxid Med Cell Longev"}


def fig7():
    print("Figure 7: retractions")
    fig = plt.figure(figsize=(7.2, 6.4))
    gs = fig.add_gridspec(2, 6, height_ratios=[1, 1.5], hspace=0.45, wspace=1.2)
    rows = []
    hind = is_pub("Hindawi")

    # A: retracted papers by publication year; B: by year of the notice
    ax = fig.add_subplot(gs[0, :3])
    h, o = per_year(retracted & hind), per_year(retracted & ~hind)
    ax.bar(YEARS, o, color=GRAY, width=0.8, label="Other publishers")
    ax.bar(YEARS, h, bottom=o, color=VERMILION, width=0.8, label="Hindawi")
    ax.legend(fontsize=6.5, loc="upper left")
    ax.set_title("A  Retracted papers, by year published", loc="left", fontsize=8.5)
    ax.set_ylabel("Papers")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    rows += [["A", "retracted_by_pub_year", int(y), int(a), int(b)] for y, a, b in zip(YEARS, o, h)]

    ax = fig.add_subplot(gs[0, 3:])
    rp, ny = R["pmid"], R["notice_year"]
    keep = (ny >= YEARS[0]) & (rp <= pmid.max())
    row = np.full(pmid.max() + 1, -1, np.int64)
    row[pmid] = np.arange(len(pmid))
    rr = row[rp[keep]]
    okr = rr >= 0
    hy = ny[keep][okr][hind[rr[okr]]]
    oy = ny[keep][okr][~hind[rr[okr]]]
    hc = np.bincount(np.clip(hy - YEARS[0], 0, None), minlength=len(YEARS))[:len(YEARS)]
    oc = np.bincount(np.clip(oy - YEARS[0], 0, None), minlength=len(YEARS))[:len(YEARS)]
    ax.bar(YEARS, oc, color=GRAY, width=0.8)
    ax.bar(YEARS, hc, bottom=oc, color=VERMILION, width=0.8)
    ax.set_title("B  …and by year retracted*", loc="left", fontsize=8.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    rows += [["B", "retracted_by_notice_year", int(y), int(a), int(b)] for y, a, b in zip(YEARS, oc, hc)]

    # C: retraction rate by publisher, papers 2015-2023
    ax = fig.add_subplot(gs[1, :2])
    win = citable & (py >= 2015) & (py <= 2023)
    rates = []
    for k, name in enumerate(PUB_NAMES):
        m = win & (pub == k)
        if m.sum() >= 50000 and name not in ("Other", "No DOI") or name in ("Hindawi", "Spandidos", "Dove", "Cureus"):
            rates.append((retracted[m].mean(), name, int(m.sum()), int(retracted[m].sum())))
    rates.sort()
    yy = np.arange(len(rates))
    ax.barh(yy, [r[0] * 1e4 for r in rates], color=[VERMILION if r[1] == "Hindawi" else BLUE for r in rates], height=0.7)
    overall = retracted[win].mean() * 1e4
    ax.axvline(overall, color=INK, linewidth=0.9, linestyle="--")
    ax.text(overall, len(rates) - 0.4, f" all: {overall:.0f}", fontsize=6, va="bottom")
    ax.set_xscale("log")
    ax.set_yticks(yy, [r[1] for r in rates], fontsize=6.3)
    for y, r in zip(yy, rates):
        ax.text(r[0] * 1e4 * 1.1, y, f"{r[0] * 1e4:.0f}", va="center", fontsize=5.8)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Retracted per 10,000 citable items (2015–23)")
    ax.set_title("C  Retraction rate by publisher", loc="left", fontsize=8.5)
    rows += [["C", r[1], "2015-2023", r[2], r[3]] for r in rates]

    # D: journals with the most retractions
    ax = fig.add_subplot(gs[1, 4:])
    js, n = np.unique(jid[retracted], return_counts=True)
    top = js[np.argsort(-n)][:15]
    tops = []
    for j in top:
        m = jid == j
        tops.append((int(retracted[m].sum()), jname[int(j)], retracted[m & citable].sum() / max((m & citable).sum(), 1),
                     bool((hind & m).any())))
    tops = tops[::-1]
    yy = np.arange(len(tops))
    ax.barh(yy, [t[0] for t in tops], color=[VERMILION if t[3] else BLUE for t in tops], height=0.7)
    for y, t in zip(yy, tops):
        ax.text(t[0] + 15, y, f"{t[2]:.1%}", va="center", fontsize=5.8)
    short = lambda n: (n.split(" : ")[0].split(" = ")[0].replace("Journal of", "J").replace("journal of", "J")
                       .replace("International", "Int").replace("Computational", "Comput").replace("environmental", "environ"))
    ax.set_yticks(yy, [short(t[1])[:32] for t in tops], fontsize=6)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Retracted papers (label: % of citable items)")
    ax.set_title("D  Journals with the most retractions", loc="left", fontsize=8.5, x=-1.1)
    rows += [["D", t[1], "all", t[0], round(float(t[2]), 5)] for t in tops]

    fig.text(0.0, -0.01, f"*Retraction dates from Retraction Watch, or a PubMed retraction notice matched by title; "
             f"{(R['notice_year'] > 0).mean():.0%} of retracted papers are dated.",
             fontsize=6, color=MUTED)
    write_csv("fig7_retractions", ["panel", "series", "year", "a", "b"], rows)
    save(fig, "fig7_retractions")

    # E/F: Hindawi journals (own figure)
    fig = plt.figure(figsize=(7.2, 4.4))
    gs = fig.add_gridspec(2, 6, hspace=0.6, wspace=1.2)
    rows = []
    for k, s in enumerate(HINDAWI[:3]):
        ax = fig.add_subplot(gs[0, 2 * k:2 * k + 2])
        m = citable & (jid == slug2id[s])
        a, r = per_year(m & ~retracted), per_year(m & retracted)
        ax.bar(YEARS, a, color=BLUE, width=0.8, label="Not retracted")
        ax.bar(YEARS, r, bottom=a, color=VERMILION, width=0.8, label="Retracted")
        ax.set_title(("E  " if k == 0 else "") + SHORT_H[s], loc="left", fontsize=8)
        ax.set_xticks([2005, 2015, 2025])
        ax.tick_params(labelsize=6.5)
        if k == 0:
            ax.set_ylabel("Papers per year")
            ax.legend(fontsize=5.8, loc="upper left")
        rows += [["E", SHORT_H[s], int(y), int(x), int(z)] for y, x, z in zip(YEARS, a, r)]

    # F: JIF-style rate with and without retracted papers, same journals
    for k, s in enumerate(HINDAWI[:3]):
        ax = fig.add_subplot(gs[1, 2 * k:2 * k + 2])
        j = slug2id[s]
        yrs, full, wo = [], [], []
        for Y in range(2007, 2026):
            idx = np.flatnonzero((jid == j) & citable & ((py == Y - 1) | (py == Y - 2)))
            if len(idx) < 20:
                continue
            c = C[idx, Y - Y0].astype(np.int64)
            keep_ = ~retracted[idx]
            yrs.append(Y); full.append(c.sum() / len(c)); wo.append(c[keep_].sum() / max(keep_.sum(), 1))
            rows.append(["F", SHORT_H[s], Y, round(full[-1], 3), round(wo[-1], 3)])
        ax.plot(yrs, full, color=BLUE, linewidth=1.5, label="All citable items")
        ax.plot(yrs, wo, color=VERMILION, linewidth=1.5, label="Without retracted papers")
        ax.set_ylim(0, None)
        ax.set_xticks([2010, 2015, 2020, 2025])
        ax.tick_params(labelsize=6.5)
        ax.set_title(("F  " if k == 0 else "") + SHORT_H[s], loc="left", fontsize=8)
        if k == 0:
            ax.set_ylabel("JIF-style rate")
            ax.legend(fontsize=5.8, loc="upper left")
    write_csv("fig7ef_hindawi", ["panel", "journal", "year", "a", "b"], rows)
    save(fig, "fig7ef_hindawi_journals")

    retraction_vs_controls()
    retraction_by_reason()


def matched_controls(idx, n=5, seed=0):
    """For each paper row in idx: up to n non-retracted citable papers from the same journal, publication year
    and article type, same publication month where possible. Returns {row: array of control rows}."""
    rng = np.random.default_rng(seed)
    js = np.unique(jid[idx])
    pool = np.flatnonzero(citable & ~retracted & np.isin(jid, js) & (py >= py[idx].min()) & (py <= py[idx].max()))
    k3 = (jid[pool].astype(np.int64) * 100 + (py[pool] - 2000)) * 10 + dc[pool]
    k4 = k3 * 100 + pm[pool].astype(np.int64)
    o3, o4 = np.argsort(k3, kind="stable"), np.argsort(k4, kind="stable")
    s3, s4 = k3[o3], k4[o4]
    out = {}
    for i in idx:
        a = (int(jid[i]) * 100 + int(py[i]) - 2000) * 10 + int(dc[i])
        lo, hi = np.searchsorted(s4, [a * 100 + int(pm[i]), a * 100 + int(pm[i]) + 1])
        cand = pool[o4[lo:hi]]
        if len(cand) < n:
            lo, hi = np.searchsorted(s3, [a, a + 1])
            rest = np.setdiff1d(pool[o3[lo:hi]], cand)
            cand = np.concatenate([cand, rng.choice(rest, min(n - len(cand), len(rest)), replace=False)])
        else:
            cand = rng.choice(cand, n, replace=False)
        if len(cand):
            out[i] = cand
    return out


def prior_matched_controls(idx, ry, n=5, caliper=0.3, seed=0):
    """Like matched_controls, but among papers from the same journal, publication year and article type, picks the n
    whose citations before the retraction year look most like the retracted paper's: distance is the absolute
    difference in log(1 + citations from publication to the year before retraction) plus the same for the year
    before retraction alone. Controls farther than `caliper` are dropped. Needs a retraction after the publication
    year. Returns {row: array of control rows} and {row: mean distance}."""
    rng = np.random.default_rng(seed)
    js = np.unique(jid[idx])
    pool = np.flatnonzero(citable & ~retracted & np.isin(jid, js) & (py >= py[idx].min()) & (py <= py[idx].max()))
    k3 = (jid[pool].astype(np.int64) * 100 + (py[pool] - 2000)) * 10 + dc[pool]
    o3 = np.argsort(k3, kind="stable")
    s3 = k3[o3]
    out, dist = {}, {}
    for i, y in zip(idx, ry):
        if y <= py[i]:
            continue
        a = (int(jid[i]) * 100 + int(py[i]) - 2000) * 10 + int(dc[i])
        lo, hi = np.searchsorted(s3, [a, a + 1])
        cand = pool[o3[lo:hi]]
        if not len(cand):
            continue
        c0, c1 = int(py[i]) - Y0, int(y) - Y0
        Cc = C[cand, c0:c1].astype(np.float64)
        d = (np.abs(np.log1p(Cc.sum(1)) - np.log1p(float(C[i, c0:c1].sum())))
             + np.abs(np.log1p(Cc[:, -1]) - np.log1p(float(C[i, c1 - 1]))))
        d += rng.random(len(d)) * 1e-6                   # random tie-breaks
        k = min(n, len(d))
        best = np.argpartition(d, k - 1)[:k]
        best = best[d[best] <= caliper]
        if len(best):
            out[i], dist[i] = cand[best], float(d[best].mean())
    return out, dist


def retracted_rows(last_pub, LAST):
    """Dated retracted citable papers published 2005-last_pub and retracted no later than LAST - 1: their rows in
    cites.npz, retraction years, Retraction Watch reason flags and date sources (see retractions.npz)."""
    row = np.full(pmid.max() + 1, -1, np.int64)
    row[pmid] = np.arange(len(pmid))
    rp, ry, fl, src = R["pmid"], R["notice_year"], R["reasons"], R["date_source"]
    ok = (rp <= pmid.max()) & (ry > 0)
    rows_r, ry, fl, src = row[rp[ok]], ry[ok].astype(np.int64), fl[ok], src[ok]
    good = rows_r >= 0
    rows_r, ry, fl, src = rows_r[good], ry[good], fl[good], src[good]
    good = (citable[rows_r] & (py[rows_r] >= 2005) & (py[rows_r] <= last_pub) & (ry >= py[rows_r])
            & (ry <= LAST - 1))
    return rows_r[good], ry[good], fl[good], src[good]


def retraction_vs_controls():
    """Fig 7I/7J: citations to retracted papers against matched non-retracted papers, by year. Fig 7K/7L: the same
    with controls also matched on citations before retraction."""
    LAST = 2024                                         # last full citation year
    rows_r, ry, _, _ = retracted_rows(2020, LAST)

    ctrl = matched_controls(rows_r)
    keep = np.array([i in ctrl for i in rows_r])
    print(f"  {keep.sum():,} retracted papers with matched controls "
          f"(mean {np.mean([len(ctrl[i]) for i in rows_r[keep]]):.1f} controls each)", flush=True)
    plot_vs_controls(rows_r[keep], ry[keep], ctrl, LAST, "i", "j", "Matched controls (same journal, year, type)",
                     range(6))

    ctrl, dist = prior_matched_controls(rows_r, ry)
    keep = np.array([i in ctrl for i in rows_r])
    later = ry > py[rows_r]
    print(f"  {keep.sum():,} of {later.sum():,} papers retracted after their publication year have prior-matched "
          f"controls (mean {np.mean([len(ctrl[i]) for i in rows_r[keep]]):.1f} each, "
          f"mean distance {np.mean([dist[i] for i in rows_r[keep]]):.3f})", flush=True)
    plot_vs_controls(rows_r[keep], ry[keep], ctrl, LAST, "k", "l",
                     "Matched controls (same journal, year, type and citations before retraction)", range(1, 7))


REASON_LABELS = [("paper_mill", "Paper mill"), ("peer_review", "Fake or compromised peer review"),
                 ("generated_content", "Computer-generated content"), ("image", "Image problems"),
                 ("fabrication_misconduct", "Fabrication or misconduct"),
                 ("plagiarism_duplication", "Plagiarism or duplication"),
                 ("honest_error", "Honest error only (no other reason)"), ("none", "None of these reasons")]


def retraction_by_reason():
    """Fig 7M: Fig 7K split by Retraction Watch's reason for the retraction. Controls are prior-matched as in 7K.
    A paper with several reasons appears in each of their panels."""
    LAST = 2024
    rows_r, ry, fl, src = retracted_rows(2022, LAST)
    later = ry > py[rows_r]
    rows_r, ry, fl, src = rows_r[later], ry[later], fl[later], src[later]
    ctrl, _ = prior_matched_controls(rows_r, ry)
    keep = np.array([i in ctrl for i in rows_r])
    rows_r, ry, fl, src = rows_r[keep], ry[keep], fl[keep], src[keep]
    names = list(R["reason_names"])
    other = np.delete(fl, names.index("honest_error"), axis=1).any(axis=1)
    groups = {n: fl[:, k] for k, n in enumerate(names)}
    groups["honest_error"] = groups["honest_error"] & ~other
    groups["none"] = (src == 1) & ~fl.any(axis=1)
    print(f"  {len(rows_r):,} retracted papers with prior-matched controls; by reason: "
          + ", ".join(f"{n} {int(groups[n].sum()):,}" for n, _ in REASON_LABELS), flush=True)

    rel = np.arange(-3, 4)
    rows, ratio, nobs, pre = [], {}, {}, []
    for n, _ in REASON_LABELS:
        g = groups[n]
        for r in rel:
            Y = ry[g] + r
            m = (Y >= py[rows_r[g]]) & (Y <= LAST)
            ii, YY = rows_r[g][m], Y[m]
            if not len(ii):
                continue
            A = C[ii, YY - Y0].mean()
            B = np.mean([C[ctrl[i], y - Y0].mean() for i, y in zip(ii, YY)])
            ratio[n, r], nobs[n, r] = A / B, len(ii)
            if r < 0 and len(ii) >= 30:
                pre.append(A / B)
            rows.append([n, int(r), round(float(A), 3), round(float(B), 3), round(float(A / B), 3), len(ii)])
    print(f"  pre-retraction ratios (n >= 30): {min(pre):.2f}-{max(pre):.2f}", flush=True)

    # each ratio compares retracted papers with their own controls in the same years, so bars for different years
    # can come from different papers (recent retractions have only year +1 observed)
    after = [0, 1, 2, 3]
    shades = ["#C6DBEF", "#86B6DA", "#3D8CC4", "#08519C"]
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    h = 0.2
    for k, (n, label) in enumerate(REASON_LABELS):
        for j, r in enumerate(after):
            if nobs.get((n, r), 0) < 30:
                continue
            y = k + (j - 1.5) * h
            ax.barh(y, ratio[n, r] * 100, height=h * 0.9, color=shades[j],
                    label=("Year retracted" if r == 0 else f"{r} year{'s' if r > 1 else ''} after") if k == 0 else None)
            ax.text(ratio[n, r] * 100 + 1.5, y, f"{ratio[n, r]:.0%}", fontsize=5.5, va="center", color=MUTED)
    ax.axvline(100, color=INK, linewidth=0.8, linestyle="--")
    ax.set_yticks(range(len(REASON_LABELS)),
                  [f"{label}\n(n = {int(groups[n].sum()):,})" for n, label in REASON_LABELS], fontsize=6.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 185)
    ax.set_xlabel("Citations to retracted papers, % of matched controls (dashed: equal)")
    ax.grid(axis="y", visible=False)
    ax.legend(fontsize=6.3, ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2)
    ax.set_title(f"M  Citations after retraction, by reason (retracted by {LAST - 1}){NOTE}", loc="left", fontsize=8, pad=18)
    fig.text(0.0, -0.02, "Controls: same journal, year, type and citations before retraction; the groups match within "
             f"{max(abs(1 - min(pre)), abs(max(pre) - 1)):.0%} in the 3 years before retraction. A paper with several "
             "reasons counts under each.\nBars need 30+ papers observed; paper-mill, peer-review and computer-generated "
             f"retractions are mostly from 2022-23, so later years cover only the older ones.", fontsize=5.5, color=MUTED)
    write_csv("fig7m_citations_after_retraction_by_reason" + SUFFIX,
              ["reason", "years_from_retraction", "retracted_mean", "controls_mean", "ratio", "papers"], rows)
    save(fig, "fig7m_citations_after_retraction_by_reason" + SUFFIX)


def plot_vs_controls(rows_r, ry, ctrl, LAST, aligned, by_age, ctrl_label, lags):
    """Bar charts of retracted papers vs their controls: aligned on the retraction year (panel letter `aligned`)
    and by year since publication, one panel per retraction lag (panel letter `by_age`)."""
    prior = aligned != "i"
    tag = ("_prior_matched" if prior else "") + SUFFIX

    def cites(i, Y):                                     # citations in calendar year Y, or nan if not observed
        return float(C[i, Y - Y0]) if py[i] <= Y <= LAST else np.nan

    def ctrl_mean(i, Y):
        return np.nanmean([cites(c, Y) for c in ctrl[i]]) if py[i] <= Y <= LAST else np.nan

    # aligned on the retraction year, retracted vs controls in the same calendar years
    rel = np.arange(-4, 6)
    sel = (ry >= 2010) & (ry <= LAST - 5)
    R_, K_ = {r: [] for r in rel}, {r: [] for r in rel}
    for i, y in zip(rows_r[sel], ry[sel]):
        for r in rel:
            a = cites(i, y + r)
            if not np.isnan(a):
                R_[r].append(a); K_[r].append(ctrl_mean(i, y + r))
    mr = np.array([np.mean(R_[r]) for r in rel]); mk = np.array([np.mean(K_[r]) for r in rel])
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    w = 0.38
    ax.bar(rel - w / 2, mr, width=w, color=VERMILION, label="Retracted papers")
    ax.bar(rel + w / 2, mk, width=w, color=BLUE, label=ctrl_label)
    ax.axvline(0, color=INK, linewidth=0.8, linestyle="--")
    ax.set_xticks(rel, [f"{r:+d}" if r else "retracted" for r in rel])
    ax.set_xlabel("Years from retraction")
    ax.set_ylabel("Citations per paper")
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=6.3, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1 if prior else 2, borderaxespad=0.2)
    ax.set_ylim(0, max(mr.max(), mk.max()) * 1.08)
    ax.set_title(f"{aligned.upper()}  Retracted papers vs matched controls (n = {int(sel.sum()):,}, "
                 f"retracted 2010–{LAST - 5}){NOTE}", loc="left", fontsize=8, pad=28 if prior else 18)
    write_csv(f"fig7{aligned}_citations_around_retraction{tag}",
              ["years_from_retraction", "retracted_mean", "controls_mean", "ratio", "papers"],
              [[int(r), round(float(a), 3), round(float(b), 3), round(float(a / b), 3) if b else "", len(R_[r])]
               for r, a, b in zip(rel, mr, mk)])
    save(fig, f"fig7{aligned}_citations_after_retraction{tag}")

    # small multiples by the year the retraction came (year 1 = publication year)
    lag = ry - py[rows_r]
    yrs = np.arange(9)
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.4), sharey=False)
    rows = []
    for k, (ax, L) in enumerate(zip(axes.flat, lags)):
        m = lag == L
        A = np.array([[cites(i, py[i] + t) for t in yrs] for i in rows_r[m]])
        B = np.array([[ctrl_mean(i, py[i] + t) for t in yrs] for i in rows_r[m]])
        a, b = np.nanmean(A, axis=0), np.nanmean(B, axis=0)
        nobs = (~np.isnan(A)).sum(axis=0)
        show = nobs >= 30
        x = yrs + 1
        ax.bar(x[show] - w / 2, a[show], width=w, color=VERMILION, label="Retracted")
        ax.bar(x[show] + w / 2, b[show], width=w, color=BLUE, label="Matched controls")
        ax.axvline(L + 1, color=INK, linewidth=0.8, linestyle="--")
        ax.set_xticks(x)
        ax.tick_params(labelsize=6.5)
        ax.grid(axis="x", visible=False)
        ax.set_title(f"Retracted in year {L + 1} (n = {int(m.sum()):,})", loc="left", fontsize=7.5)
        if k % 3 == 0:
            ax.set_ylabel("Citations per paper")
        if k >= 3:
            ax.set_xlabel("Year since publication (1 = year published)")
        rows += [[L + 1, int(t + 1), round(float(a[t]), 3), round(float(b[t]), 3), int(nobs[t])] for t in yrs if show[t]]
    fig.suptitle(f"{by_age.upper()}  Citations by year since publication (dashed: year retracted){NOTE}", x=0.01, ha="left",
                 fontsize=8.5, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.95 if prior else 0.97))
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, ["Retracted papers", ctrl_label], fontsize=6.5, ncol=2,
               loc="upper right" if not prior else "upper left", bbox_to_anchor=(0.99, 1.0) if not prior else (0.0, 0.965))
    write_csv(f"fig7{by_age}_retracted_vs_controls_by_age{tag}",
              ["retracted_in_year", "year_since_publication", "retracted_mean", "controls_mean", "retracted_papers_observed"], rows)
    save(fig, f"fig7{by_age}_retracted_vs_controls_by_age{tag}")


def exclude_notice_citations():
    """Remove citations made by retraction notices from the citation matrix (in place, for this run) and switch
    the retraction figures 7I-7M to their _no_notices file names."""
    global SUFFIX, NOTE
    if "noncounting_excluded" in np.load(os.path.join(DATA, "cites.npz")).files:
        sys.exit("cites.npz already leaves out notice citations (build_matrix.py); the default run is the no-notice one")
    from notice_citations import notice_citations
    r, cy = notice_citations()
    ok = (cy >= Y0) & (cy < Y0 + C.shape[1])
    np.subtract.at(C, (r[ok], cy[ok] - Y0), np.uint32(1))
    SUFFIX, NOTE = "_no_notices", "; notice citations excluded"


if __name__ == "__main__":
    want = set(sys.argv[1:]) or {"6", "7"}
    if "notices" in want:                                # 7I-7M without retraction-notice citations, as new files
        exclude_notice_citations()
        retraction_vs_controls()
        retraction_by_reason()
    if "6" in want:
        fig6()
    if "7" in want:
        fig7()
