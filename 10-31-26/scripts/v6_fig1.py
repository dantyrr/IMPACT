"""v6 Figure 1, the changing landscape of publishing, and Supplementary Figure S9, the publisher detail.

A, B  every large institution's share of all PubMed papers against its share of flagship papers, 2001-05 and 2021-25
C, D  regions' share of papers each year, all journals and the five flagships
E     citable items by publisher
F-I   four publishers stacked by journal group

Each paper counts once, for its first author's first-named institution: PubMed kept only that affiliation until about 2014.

Usage: python 10-31-26/scripts/v6_fig1.py   (from the IMPACT folder)
"""
import os
import pickle
import sys

os.environ["FIG_DIR"] = "v6"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alt_figures as AF  # noqa: E402
import more_figures as M  # noqa: E402
import v6_stacks as S  # noqa: E402
from make_figures import BLUE, GRAY, GREEN, INK, MUTED, PURPLE, SYSTEM_NAMES, VERMILION, DATA, inst_label, matplotlib, np, plt  # noqa: E402
from v2_common import ORANGE, SKY, save, write_csv  # noqa: E402
from v3_f11 import NOT_PLACES  # noqa: E402

PERIODS = ((2001, 2005), (2021, 2025))
REGIONS = [("USA", BLUE), ("Canada", SKY), ("Europe", ORANGE), ("Rest of world", GRAY), ("Other Asia", GREEN), ("China", VERMILION)]
COLOR = dict(REGIONS)
MIN_SHARE = 1e-4
PCT = matplotlib.ticker.PercentFormatter(1, decimals=0)
NAMES = {"stanford university": "Stanford", "university of california san francisco": "UC San Francisco", "university of oxford": "Oxford", "university of cambridge": "Cambridge",
         "chinese academy of sciences": "Chinese Acad Sci", "tsinghua university": "Tsinghua", "university of tokyo": "Tokyo", "national university of singapore": "Natl Univ Singapore"}
# Where each name sits, in axis shares, chosen to keep clear of the dots.
PLACE = {2001: {"stanford university": (0.0021, 0.024, "right"), "university of california san francisco": (0.0095, 0.02, "right"), "university of cambridge": (0.0007, 0.0215, "left"),
                "university of oxford": (0.00045, 0.0165, "left"), "university of tokyo": (0.0095, 0.0033, "right"), "chinese academy of sciences": (0.0095, 0.0014, "right"),
                "national university of singapore": (0.0095, 0.00045, "right"), "tsinghua university": (0.0026, 0.00022, "left")},
         2021: {"stanford university": (0.0034, 0.0262, "left"), "chinese academy of sciences": (0.0095, 0.02, "right"), "university of california san francisco": (0.00062, 0.0215, "left"),
                "university of oxford": (0.00045, 0.0165, "left"), "university of cambridge": (0.0066, 0.0085, "right"), "tsinghua university": (0.0095, 0.0033, "right"),
                "university of tokyo": (0.0095, 0.0017, "right"), "national university of singapore": (0.0095, 0.0004, "right")}}


def region(country):
    if country in ("USA", "Canada"):
        return country
    if country in AF.EUROPE:
        return "Europe"
    if country in AF.CHINA:
        return "China"
    if country in AF.ASIA:
        return "Other Asia"
    return "Rest of world"


def load():
    D = np.load(os.path.join(DATA, "first_author_inst.npz"))
    K = pickle.load(open(os.path.join(DATA, "first_author_inst.pkl"), "rb"))
    reg_names = [r for r, _ in REGIONS]
    code = np.array([reg_names.index(region(c)) for c in K["countries"]] + [-1], np.int8)      # index -1 = no country
    return D["year"], D["flagship"] > 0, D["inst"], code[D["country"]], D["country"], K


def home_regions(inst, country, K):
    """Region of each institution: its main country, when at least 80% of its papers name it. -1 otherwise."""
    m = (inst >= 0) & (country >= 0)
    nc = len(K["countries"])
    pair, n = np.unique(inst[m].astype(np.int64) * nc + country[m], return_counts=True)
    k, c = pair // nc, pair % nc
    tot = np.bincount(k, weights=n, minlength=len(K["keys"]))
    order = np.lexsort((n, k))
    top_c = np.full(len(K["keys"]), -1, np.int64)
    top_n = np.zeros(len(K["keys"]))
    top_c[k[order]] = c[order]
    top_n[k[order]] = n[order]
    names = [r for r, _ in REGIONS]
    out = np.full(len(K["keys"]), -1, np.int8)
    ok = (top_c >= 0) & (top_n >= 0.8 * np.maximum(tot, 1))
    for i in np.flatnonzero(ok):
        out[i] = names.index(region(K["countries"][top_c[i]]))
    return out


def period_shares(year, flag, inst, lo, hi, n_keys):
    m = (year >= lo) & (year <= hi) & (inst >= 0)
    a = np.bincount(inst[m], minlength=n_keys)
    f = np.bincount(inst[m & flag], minlength=n_keys)
    return a, f


def bubbles(ax, a, f, home, keep, title, legend=False, note=None):
    x = a / a.sum()
    y = f / f.sum()
    sel = keep & (x >= MIN_SHARE)
    drawn = sel & (f > 0)
    for r, (name, col) in enumerate(REGIONS):
        m = drawn & (home == r)
        ax.scatter(x[m], y[m], s=4 + 5.6 * np.sqrt(f[m]), color=col, alpha=0.6, linewidths=0, label=name, zorder=4 if name == "China" else 3)
    lim = np.array([1e-4, 1e-2])
    ax.plot(lim, lim, color=INK, linewidth=0.7, linestyle=(0, (3, 2)), zorder=2, label="Equal share")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(*lim); ax.set_ylim(3.6e-5, 3.2e-2)
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:g}%")
    ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
    ax.tick_params(labelsize=6.8)
    ax.set_xlabel("Share of all PubMed papers", fontsize=7.5)
    ax.set_title(title, loc="left", fontsize=8.5)
    if legend:
        ax.legend(fontsize=6, loc="upper left", handletextpad=0.1, labelspacing=0.3, borderaxespad=0.2)
        for h in ax.get_legend().legend_handles:
            if hasattr(h, "set_sizes"):
                h.set_sizes([22]); h.set_alpha(1)
    if note:
        for row, cells in zip((0.125, 0.08, 0.035), note):
            for xa, text, ha in zip((0.665, 0.845, 0.985), cells, ("left", "right", "right")):
                ax.text(xa, row, text, transform=ax.transAxes, ha=ha, va="bottom", fontsize=6.2, color=INK, fontweight="bold" if row == 0.125 else "normal")
    return sel, x, y


def region_shares(year, flag, code):
    ys = np.arange(2001, 2026)
    out = {}
    for lab, base in (("all", np.ones(len(year), bool)), ("flag", flag)):
        m = base & (code >= 0)
        tab = np.zeros((len(REGIONS), len(ys)))
        idx = (year[m].astype(int) - 2001) * len(REGIONS) + code[m]
        tab = np.bincount(idx, minlength=len(ys) * len(REGIONS)).reshape(len(ys), len(REGIONS)).T.astype(float)
        out[lab] = tab / tab.sum(axis=0)
    return ys, out


def region_stack(ax, ys, tab, title, ylabel=False):
    ax.stackplot(ys, tab, colors=[c for _, c in REGIONS], linewidth=0.3, edgecolor="white")
    ax.set_xlim(2001, 2025); ax.set_ylim(0, 1)
    ax.set_xticks([2001, 2013, 2025])
    ax.yaxis.set_major_formatter(PCT)
    ax.tick_params(labelsize=6.3, pad=1.5)
    ax.grid(False)
    if ylabel:
        ax.set_ylabel("Share of papers", fontsize=7)
    ax.set_title(title, loc="left", fontsize=8.2, pad=3)
    base = 0
    items = []
    for (name, col), v in zip(REGIONS, tab[:, -1]):
        items.append((base + v / 2, f"{name} {v * 100:.0f}%", col))
        base += v
    last = -1
    for yv, text, col in items:
        yl = max(yv, last + 0.078)
        ax.annotate(text, (2025, yv), xytext=(2026.2, yl), textcoords="data", fontsize=5.6, va="center", color=INK, annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=col, linewidth=0.6, shrinkA=0, shrinkB=0, relpos=(0, 0.5)))
        last = yl


def publisher_panel(ax, title="E  Citable items by publisher"):
    order = [("Elsevier", GRAY), ("PLOS", BLUE), ("Nature Portfolio", VERMILION), ("Hindawi", SKY), ("Cureus", PURPLE), ("Frontiers", GREEN), ("MDPI", ORANGE)]
    tot = M.per_year(M.citable)
    vals = [M.per_year(M.citable & M.is_pub(n)) for n, _ in order]
    rest = tot - sum(vals)
    ax.stackplot(M.YEARS, [rest] + vals, colors=["#DDDDDD"] + [c for _, c in order], linewidth=0.2, edgecolor="white")
    write_csv("f1e_pubmed_by_publisher", ["year", "all_other_publishers", *[n for n, _ in order], "total"],
              [[int(y), int(rest[i]), *[int(v[i]) for v in vals], int(tot[i])] for i, y in enumerate(M.YEARS)])
    base, items = 0, []
    for name, v, col in zip(["All others"] + [n for n, _ in order], [rest] + vals, ["#DDDDDD"] + [c for _, c in order]):
        items.append((base + v[-1] / 2, name, col))
        base += v[-1]
    last = 1.62e6 + 112000
    for yv, name, col in items[::-1]:
        yl = min(yv, last - 112000)
        ax.annotate(name, (M.YEARS[-1], yv), xytext=(M.YEARS[-1] + 1.0, yl), textcoords="data", fontsize=5.6, va="center", color=INK, annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=col, linewidth=0.6, shrinkA=0, shrinkB=0, relpos=(0, 0.5)))
        last = yl
    ax.set_xlim(M.YEARS[0], M.YEARS[-1])
    ax.set_xticks([2005, 2015, 2025])
    ax.set_ylim(0, 1.65e6)
    ax.tick_params(labelsize=6.3, pad=1.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1e6:.1f}M" if v else "0"))
    ax.set_ylabel("Citable items per year", fontsize=7)
    ax.set_title(title, loc="left", fontsize=8.2, pad=3)


def figure1():
    year, flag, inst, code, country, K = load()
    keys = K["keys"]
    home = home_regions(inst, country, K)
    bad = np.array([k in SYSTEM_NAMES or k in NOT_PLACES for k in keys])
    keep = (home >= 0) & ~bad
    (a0, f0), (a1, f1) = [period_shares(year, flag, inst, lo, hi, len(keys)) for lo, hi in PERIODS]

    # Region totals for the notes and the legend.
    stats = {}
    for (lo, hi) in PERIODS:
        m = (year >= lo) & (year <= hi) & (code >= 0)
        for lab, mm in (("all", m), ("flag", m & flag)):
            n = np.bincount(code[mm], minlength=len(REGIONS))
            stats[lo, lab] = n / n.sum()
    write_csv("f1ab_region_totals", ["period", "journals", *[r for r, _ in REGIONS]],
              [[f"{lo}-{hi}", lab, *[round(float(v), 4) for v in stats[lo, lab]]] for lo, hi in PERIODS for lab in ("all", "flag")])

    # The two institutions with the most flagship papers in 2021-25 in each of four regions are named in both panels.
    names = [r for r, _ in REGIONS]
    picks = []
    for r in ("USA", "Europe", "China", "Other Asia"):
        c = np.flatnonzero(keep & (home == names.index(r)))
        picks += [int(i) for i in c[np.argsort(-f1[c])][:2]]
    print([(keys[i], int(f0[i]), int(f1[i]), int(a0[i]), int(a1[i])) for i in picks])

    fig = plt.figure(figsize=(7.3, 8.9))
    gs = fig.add_gridspec(3, 1, hspace=0.3, height_ratios=[1.62, 0.9, 0.9], left=0.075, right=0.985, top=0.975, bottom=0.04)
    top = gs[0].subgridspec(1, 2, wspace=0.16)

    def note(lo):
        u, c = names.index("USA"), names.index("China")
        pct = lambda v: f"{v * 100:.0f}%" if v >= 0.1 else f"{v * 100:.1f}%"  # noqa: E731
        return [("", "All", "Flagship"), ("USA", pct(stats[lo, "all"][u]), pct(stats[lo, "flag"][u])), ("China", pct(stats[lo, "all"][c]), pct(stats[lo, "flag"][c]))]

    rows = []
    axes = []
    for k, ((lo, hi), a, f) in enumerate(zip(PERIODS, (a0, a1), (f0, f1))):
        ax = fig.add_subplot(top[k])
        sel, x, y = bubbles(ax, a, f, home, keep, f"{'AB'[k]}  Where flagship papers came from, {lo}–{str(hi)[2:]}", legend=k == 0, note=note(lo))
        axes.append((ax, x, y, sel, lo))
        rows += [[f"{lo}-{hi}", keys[i], names[home[i]], int(a[i]), int(f[i]), round(float(x[i]), 6), round(float(y[i]), 6)] for i in np.flatnonzero(sel)]
        print(lo, "institutions", int(sel.sum()), "with no flagship paper", int((sel & (f == 0)).sum()))
    axes[0][0].set_ylabel("Share of papers in Nature, Science, Cell, NEJM and Lancet", fontsize=7.5)
    write_csv("f1ab_institutions", ["period", "institution", "region", "papers_all_journals", "flagship_papers", "share_all", "share_flagship"], rows)

    for ax, x, y, sel, lo in axes:
        for i in picks:
            ax.scatter([x[i]], [y[i]], s=9, facecolors="none", edgecolors=INK, linewidth=0.55, zorder=6)
            tx, ty, ha = PLACE[lo][keys[i]]
            ax.annotate(NAMES[keys[i]], (x[i], y[i]), xytext=(tx, ty), textcoords="data", fontsize=6, color=INK, va="center", ha=ha, zorder=7,
                        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.4, shrinkA=1, shrinkB=1, relpos=(1 if tx < x[i] else 0, 0.5)))
    mid = gs[1].subgridspec(1, 3, wspace=0.62)
    ys, sh = region_shares(year, flag, code)
    region_stack(fig.add_subplot(mid[0]), ys, sh["all"], "C  All PubMed journals", ylabel=True)
    region_stack(fig.add_subplot(mid[1]), ys, sh["flag"], "D  Five flagship journals")
    write_csv("f1cd_region_share", ["journals", "year", *[r for r, _ in REGIONS]],
              [[lab, int(y), *[round(float(v), 4) for v in sh[lab][:, i]]] for lab in ("all", "flag") for i, y in enumerate(ys)])
    publisher_panel(fig.add_subplot(mid[2]))

    L = S.layers()
    bot = gs[2].subgridspec(1, 4, wspace=0.32)
    out = []
    for k, name in enumerate(("Nature Portfolio", "Cell Press", "MDPI", "Frontiers")):
        ax = fig.add_subplot(bot[k])
        S.stack(ax, L[name], sum(v for _, v, _ in L[name]).max() * 1.08)
        ax.set_title(f"{'FGHI'[k]}  {name}", loc="left", fontsize=8.2, pad=3)
        if k == 0:
            ax.set_ylabel("Citable items per year", fontsize=7)
        out += [[name, t, int(y), int(n)] for t, v, _ in L[name] for y, n in zip(M.YEARS, v)]
    write_csv("f1fi_publisher_groups", ["publisher", "group", "year", "citable_items"], out)
    return fig, axes, picks, keys


def s9():
    """The publisher detail: largest journals, publishers' share, and all eight publishers, each on its own scale above one shared scale."""
    import v5_fig12 as F
    from v2_common import V2
    fig = plt.figure(figsize=(7.4, 9.4))
    gs = fig.add_gridspec(3, 1, hspace=0.3, height_ratios=[1.0, 1.25, 1.25], left=0.085, right=0.985, top=0.975, bottom=0.03)
    top = gs[0].subgridspec(1, 2, wspace=0.26)
    a, b = fig.add_subplot(top[0]), fig.add_subplot(top[1])
    F.panel_largest(a)
    F.panel_share(b)
    a.set_title("A  Largest journals in PubMed", loc="left", fontsize=8.5)
    b.set_title("B  Publishers' share of PubMed", loc="left", fontsize=8.5)
    d = os.path.join(V2, "data")
    os.replace(os.path.join(d, "f1b_largest_journals.csv"), os.path.join(d, "s9a_largest_journals.csv"))
    os.replace(os.path.join(d, "f1c_publisher_share.csv"), os.path.join(d, "s9b_publisher_share.csv"))
    L = S.layers()
    shared = max(sum(v for _, v, _ in x).max() for x in L.values()) * 1.05
    out = []
    for k, name in enumerate(("Nature Portfolio", "Cell Press", "AAAS", "PLOS", "MDPI", "Frontiers", "Hindawi", "Cureus")):
        block = gs[1 + k // 4].subgridspec(2, 4, hspace=0.16, wspace=0.34, height_ratios=[1.32, 0.68])
        ax = fig.add_subplot(block[0, k % 4])
        S.stack(ax, L[name], sum(v for _, v, _ in L[name]).max() * (1.15 + 0.075 * len(L[name])), fontsize=4.9)
        ax.set_xticklabels([])
        ax.set_title(f"{'CDEFGHIJ'[k]}  {name}", loc="left", fontsize=8.2, pad=3)
        bx = fig.add_subplot(block[1, k % 4])
        S.stack(bx, L[name], shared, legend=False)
        if k % 4 == 0:
            ax.set_ylabel("Citable items\nper year", fontsize=6.3)
            bx.set_ylabel("Same scale", fontsize=6.3)
        out += [[name, t, int(y), int(n)] for t, v, _ in L[name] for y, n in zip(M.YEARS, v)]
    write_csv("s9cj_publisher_groups", ["publisher", "group", "year", "citable_items"], out)
    save(fig, "S9_publishers")


def main():
    fig, axes, picks, keys = figure1()
    save(fig, "Fig1_landscape")
    s9()


if __name__ == "__main__":
    main()
