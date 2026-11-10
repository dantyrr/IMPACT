"""Publisher stacks for v7, as v6 with Cell Press in full (Current Biology, Trends and partner titles) and publisher groups from v7_publishers.py.

Black, the flagship. Orange, journals carrying the flagship's name. Pink, review journals. Yellow, the next tier down. Light blue, newer broad journals.
Blue, the largest high-volume journal. Gray, everything else.
"""
import os
import sys

os.environ["FIG_DIR"] = "v7"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import more_figures as M  # noqa: E402
from make_figures import BLUE, DATA, GRAY, INK, PURPLE, VERMILION, con, dc, jid, matplotlib, np, pmid, plt, py, slug2id  # noqa: E402
from v2_common import ORANGE, SKY, save, write_csv  # noqa: E402

abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
YEARS, citable = M.YEARS, M.citable
NAT = {"Nature": INK, "Nature-branded research": VERMILION, "Nature Reviews": PURPLE, "Nature Communications": ORANGE, "Communications, npj, Sci Data": SKY,
       "Scientific Reports": BLUE, "Society and partner journals": GRAY}


_G = np.load(os.path.join(DATA, "publisher_groups.npz"))
GROUP_NAMES = list(_G["names"])
_code = np.full(max(int(pmid.max()), int(_G["pmid"].max())) + 1, -1, np.int8)
_code[_G["pmid"]] = _G["code"]
group = _code[pmid]
TRENDS = {j for j, a in abbr.items() if a and a.startswith("Trends ")}


def in_group(name):
    return group == GROUP_NAMES.index(name)


def split_by_size(name):
    """A publisher without a flagship: its largest journal in 2023-25, the next four, and the rest."""
    m = citable & M.is_pub(name)
    r = m & (py >= 2023) & (py <= 2025)
    u, k = np.unique(jid[r], return_counts=True)
    j = [int(u[i]) for i in np.argsort(-k)]
    a, b = M.per_year(m & np.isin(jid, j[:1])), M.per_year(m & np.isin(jid, j[1:5]))
    return [("All other journals", M.per_year(m) - a - b, GRAY), ("Next four journals", b, ORANGE), (abbr[j[0]].replace(" (Basel)", "").replace(" (Lausanne)", ""), a, BLUE)]


def layers():
    """{publisher: [(label, per-year counts, color)]}, bottom layer first."""
    nat = citable & M.is_pub("Nature Portfolio")
    tier = {int(j): M.nature_tier(M.jname[int(j)]) for j in np.unique(jid[nat])}
    out = {"Nature Portfolio": [(t, M.per_year(nat & np.isin(jid, [j for j, x in tier.items() if x == t])), c) for t, c in NAT.items()]}
    cell = citable & in_group("Cell Press")
    tiers = [(t, M.per_year(cell & np.isin(jid, [slug2id[s] for s in slugs if s in slug2id])), c) for t, slugs, c in M.CELL_TIERS]
    trends = M.per_year(cell & np.isin(jid, list(TRENDS)))
    named = sum(v for _, v, _ in tiers) + trends
    tiers.insert(2, ("Trends reviews", trends, PURPLE))
    out["Cell Press"] = tiers + [("Current Biol, partners, other", M.per_year(cell) - named, GRAY)]
    aaas = citable & in_group("AAAS")
    tiers = [(t, M.per_year(aaas & np.isin(jid, [slug2id[s] for s in slugs if s in slug2id])), c) for t, slugs, c in M.AAAS_TIERS]
    rest = M.per_year(aaas) - sum(v for _, v, _ in tiers)
    out["AAAS"] = tiers + ([("Other AAAS", rest, GRAY)] if rest.sum() else [])
    plos = citable & M.is_pub("PLOS")
    one = M.per_year(plos & (jid == slug2id["plos-one"]))
    out["PLOS"] = [("Other PLOS journals", M.per_year(plos) - one, GRAY), ("PLoS One", one, BLUE)]
    for name in ("MDPI", "Frontiers", "Hindawi"):
        out[name] = split_by_size(name)
    out["Cureus"] = [("Cureus", M.per_year(citable & M.is_pub("Cureus")), BLUE)]
    return out


def stack(ax, L, top=None, legend=True, fontsize=5.4):
    ax.stackplot(YEARS, [v for _, v, _ in L], colors=[c for *_, c in L], linewidth=0)
    ax.set_xlim(YEARS[0], YEARS[-1])
    ax.set_xticks([2005, 2015, 2025])
    ax.tick_params(labelsize=6.3, pad=1.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 1000 else f"{v:.0f}"))
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    ax.set_ylim(0, top)
    if legend:
        ax.legend(handles=[matplotlib.patches.Patch(color=c, label=t) for t, _, c in L][::-1], fontsize=fontsize, loc="upper left", handlelength=0.9, handleheight=0.7,
                  labelspacing=0.14, borderpad=0, borderaxespad=0.2, frameon=False)


if __name__ == "__main__":
    for k, L in layers().items():
        print(k, int(sum(v for _, v, _ in L).max()), [(t, int(v[-3])) for t, v, _ in L])
