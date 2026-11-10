"""Publisher stacks in the v4 scheme: flagship black, journal groups in full Okabe-Ito colors, one meaning per color across publishers.

Black, the flagship. Orange, journals carrying the flagship's name. Pink, review journals. Yellow, the next tier down. Light blue, newer broad journals.
Blue, the largest high-volume journal. Gray, everything else.
"""
import os
import sys

os.environ["FIG_DIR"] = "v6"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import more_figures as M  # noqa: E402
from make_figures import BLUE, GRAY, INK, PURPLE, VERMILION, con, dc, jid, matplotlib, np, plt, py, slug2id  # noqa: E402
from v2_common import ORANGE, SKY, save, write_csv  # noqa: E402

abbr = dict(con.execute("SELECT id, abbreviation FROM journals"))
YEARS, citable = M.YEARS, M.citable
NAT = {"Nature": INK, "Nature-branded research": VERMILION, "Nature Reviews": PURPLE, "Nature Communications": ORANGE, "Communications, npj, Sci Data": SKY,
       "Scientific Reports": BLUE, "Society and partner journals": GRAY}


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
    for fam, tiers in (("Cell Press", M.CELL_TIERS), ("AAAS", M.AAAS_TIERS)):
        out[fam] = [(t, M.per_year(citable & np.isin(jid, [slug2id[s] for s in slugs if s in slug2id])), c) for t, slugs, c in tiers]
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
