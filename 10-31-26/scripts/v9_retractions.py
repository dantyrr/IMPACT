"""S6 with retraction rates by owner, as in Figure 1E -> v9/. Hindawi stays apart from Wiley, because its mass retraction is the finding.

Usage: python 10-31-26/scripts/v9_retractions.py   (from the IMPACT folder)
"""
import os
import sys

os.environ["FIG_DIR"] = "v9"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v2_common  # noqa: E402,F401  first import fixes V2 at v9
from v2_common import V2, write_csv  # noqa: E402
import v8_base as B  # noqa: E402
import v3_f12 as F  # noqa: E402
from make_figures import py  # noqa: E402

M = B.M
MIN_ITEMS = 20000
OTHER_PREFIXES = ("Spandidos", "Impact Journals", "AMA (JAMA)", "PNAS", "CSHL (bioRxiv)")     # named in the first list, outside Figure 1E's owners


def rows():
    m = M.citable & (py >= 2015) & (py <= 2023)
    hindawi = M.is_pub("Hindawi")
    groups = {n: B.owner(n) for n in B.OWNERS if n != "Other"}
    groups["Wiley"] = groups["Wiley"] & ~hindawi
    groups["Hindawi"] = hindawi
    groups.update({n: M.is_pub(n) for n in OTHER_PREFIXES})
    out = []
    for name, g in groups.items():
        n, r = int((m & g).sum()), int((m & g & M.retracted).sum())
        if n >= MIN_ITEMS:
            out.append([name, n, r, round(r / n * 1e4, 1)])
    both = m & B.owner("Wiley")
    print("Wiley with Hindawi", int(both.sum()), int((both & M.retracted).sum()), round((both & M.retracted).sum() / both.sum() * 1e4, 1))
    write_csv("s6c_wiley_with_hindawi", ["citable_items", "retracted", "per_10000"], [[int(both.sum()), int((both & M.retracted).sum()), round((both & M.retracted).sum() / both.sum() * 1e4, 1)]])
    return sorted(out, key=lambda r: -r[3])


def main():
    data = rows()
    write_csv("fig7c_ranked", ["publisher", "citable_items", "retracted", "per_10000"], data)
    print(data, flush=True)
    old = F.read
    F.read = lambda name: list(__import__("csv").DictReader(open(os.path.join(V2, "data", name)))) if name == "fig7c_ranked.csv" else old(name)
    F.main()
    for ext in (".png", ".pdf"):
        os.replace(os.path.join(V2, "F12_retractions" + ext), os.path.join(V2, "S6_retractions" + ext))


if __name__ == "__main__":
    main()
