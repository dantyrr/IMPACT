"""Figure data that v16's CSVs do not hold in full, for Data S1. Writes to v16/data with the prefix ds1_.

  ds1_fig2f_all_journals   every journal in Figure 2F (the CSV f1i_ keeps only the labelled ones)
  ds1_pair_rates           monthly 24-month rates (all citable items, research only) and citable items per year for the
                           journals in Figure 3H, I and Supplementary Figure S5, read as the figures read them

Usage: python 10-31-26/scripts/v16_data_s1_extra.py pairs fig2f   (from the IMPACT folder)
"""
import os
import sys

os.environ["FIG_DIR"] = "v16"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_common import SETTLED, write_csv  # noqa: E402

PAIRS = [("Nature", "Nat Commun"), ("Cell", "Cell Rep"), ("Lancet", "EClinicalMedicine"), ("Science", "Sci Adv"), ("JAMA", "JAMA Netw Open"),
         ("Circulation", "J Am Heart Assoc"), ("J Biol Chem", "Int J Mol Sci"), ("J Immunol", "Front Immunol"), ("Cancer Res", "Cancers (Basel)"),
         ("Endocrinology", "Front Endocrinol (Lausanne)"), ("Circ Res", "Front Cardiovasc Med"), ("J Virol", "Viruses")]
CITABLE = ("research", "review", "case_report", "guideline")


def pairs():
    import csv
    import alt_figures as A
    from v2_f78 import slug_of
    from v2_common import V2
    A.SETTLED = SETTLED
    from v3_f7 import outliers, slug_abbr
    picks, _ = outliers(list(csv.DictReader(open(os.path.join(V2, "data", "f7ab_lift_all_journals.csv")))))
    names = [("Fig. 3H", n, slug_of[n]) for p in PAIRS[:6] for n in p] + [("Fig. 3I", n, slug_of[n]) for p in PAIRS[6:] for n in p]
    names += [("fig. S5", slug_abbr.get(s, s), s) for s in picks]
    rates, items = [], []
    for fig, name, slug in names:
        s = A.series(slug)
        for m, a, r in zip(s["months"], s["all"], s["res"]):
            rates.append([fig, name, m, "" if a != a else round(float(a), 3), "" if r != r else round(float(r), 3)])
        for y in range(2012, 2026):
            p = s["pub"].get(y, {})
            items.append([fig, name, y, p.get("research", 0), p.get("review", 0), sum(p.get(k, 0) for k in CITABLE)])
    write_csv("ds1_pair_rates", ["figure", "journal", "month", "rate_all_citable", "rate_research"], rates)
    write_csv("ds1_pair_items", ["figure", "journal", "year", "research", "reviews", "citable_items"], items)


def fig2f():
    import numpy as np
    import v3_f1 as A
    W = A.W
    Y = 2022
    items = W.READ_ITEMS[Y][11]
    with np.errstate(divide="ignore", invalid="ignore"):
        read = np.nanmean(W.READ_NUM[Y] / W.READ_ITEMS[Y], axis=0)
        jif = W.READ_NUM[Y][11] / items
    ok = (items >= W.MIN_ITEMS) & (jif > 0) & (read > 0)
    js, n, a, b = W.uj[ok], items[ok], jif[ok], read[ok]
    write_csv("ds1_fig2f_all_journals", ["journal", "items", "jif_style_2022", "rate_24_month_mean_2022"],
              [[W.abbr.get(int(j), str(int(j))), int(k), round(float(x), 4), round(float(y), 4)] for j, k, x, y in zip(js, n, a, b)])
    print("fig2f", len(a))


if __name__ == "__main__":
    for job in sys.argv[1:]:
        {"pairs": pairs, "fig2f": fig2f}[job]()
