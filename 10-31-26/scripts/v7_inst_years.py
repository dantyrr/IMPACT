"""Yearly first-author paper counts per institution -> data/analysis/institution_years.npz, for the site's moving bubble plot.

Same rules as Figure 1A and B: citable items, each paper once for its first author's first-named institution, institutions placed in a region by the 80% rule.
Listed: every institution with at least 200 papers in 2001-25, so every dot in Figure 1 is included.

Usage: python 10-31-26/scripts/v7_inst_years.py   (from the IMPACT folder)
"""
import os
import sys

os.environ["FIG_DIR"] = "v7"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v7_fig1 as F  # noqa: E402
from make_figures import DATA, SYSTEM_NAMES, np  # noqa: E402
from v3_f11 import NOT_PLACES  # noqa: E402

MIN_PAPERS = 200
Y0, Y1 = 2001, 2025


def main():
    year, flag, inst, code, country, K = F.load()
    keys = K["keys"]
    n = len(keys)
    ny = Y1 - Y0 + 1
    home = F.home_regions(inst, country, K)
    bad = np.array([k in SYSTEM_NAMES or k in NOT_PLACES for k in keys])
    named = (inst >= 0) & (year >= Y0) & (year <= Y1)
    total = np.bincount(inst[named], minlength=n)
    keep = np.flatnonzero((home >= 0) & ~bad & (total >= MIN_PAPERS))
    slot = np.full(n, -1, np.int64)
    slot[keep] = np.arange(len(keep))
    y = year.astype(np.int64) - Y0

    def table(mask):
        m = mask & (slot[np.maximum(inst, 0)] >= 0)
        return np.bincount(slot[inst[m]] * ny + y[m], minlength=len(keep) * ny).reshape(len(keep), ny).astype(np.int32)

    def by_region(mask):
        m = mask & (code >= 0) & (year >= Y0) & (year <= Y1)
        return np.bincount(code[m].astype(np.int64) * ny + y[m], minlength=len(F.REGIONS) * ny).reshape(len(F.REGIONS), ny).astype(np.int32)

    every = np.ones(len(year), bool)
    np.savez_compressed(os.path.join(DATA, "institution_years.npz"), names=np.array([K["names"][keys[i]] for i in keep]), keys=np.array([keys[i] for i in keep]), region=home[keep], all=table(named), flag=table(named & flag),
                        denom_all=np.bincount(y[named], minlength=ny), denom_flag=np.bincount(y[named & flag], minlength=ny), reg_all=by_region(every), reg_flag=by_region(flag),
                        regions=np.array([r for r, _ in F.REGIONS]), colors=np.array([c for _, c in F.REGIONS]), first_year=Y0)
    print(len(keep), "institutions;", int((table(named & flag).sum(axis=1) > 0).sum()), "with a flagship paper")


if __name__ == "__main__":
    main()
