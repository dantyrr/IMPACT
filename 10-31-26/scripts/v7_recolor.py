"""Figure 6 and S7-S8 with Canada in pink, as in Figure 1 -> v7/. Drawn by the v3 scripts, which keep the same data; only the color changes.

Usage: python 10-31-26/scripts/v7_recolor.py   (from the IMPACT folder)
"""
import glob
import os
import shutil
import sys

os.environ["FIG_DIR"] = "v7"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_figures import PURPLE  # noqa: E402
from v2_common import ROOT, V2  # noqa: E402
import v3_f10_alt as ABS  # noqa: E402
import v3_f10_alt_share as SHARE  # noqa: E402
import v3_f10_combined as GEO  # noqa: E402

NAMES = {"F10_geography": "Fig6_geography", "F10_alt_citers_over_time": "S7_citers_over_time", "F10_alt_citers_absolute": "S8_citers_absolute"}


def pink(mod):
    mod.REGIONS = [(n, PURPLE if n == "Canada" else c) for n, c in mod.REGIONS]


def main():
    for f in glob.glob(os.path.join(ROOT, "10-31-26", "v3", "data", "f10*.csv")):
        shutil.copy(f, os.path.join(V2, "data"))
    for mod in (ABS, SHARE, GEO):
        pink(mod)
        mod.main()
    for old, new in NAMES.items():
        for ext in (".png", ".pdf"):
            os.replace(os.path.join(V2, old + ext), os.path.join(V2, new + ext))


if __name__ == "__main__":
    main()
