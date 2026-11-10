"""v10: Figure 1 and S5 with institution names merged, and the yearly counts behind the site's bubble plot.

Usage: python 10-31-26/scripts/v10_figs.py   (from the IMPACT folder)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v10_base as B  # noqa: E402
import v7_inst_years as Y  # noqa: E402
from v2_common import V2, save  # noqa: E402

F1 = B.F1


def main():
    F1.publisher_panel = B.V8.publisher_panel
    F1.NAMES["harvard university"] = "Harvard"
    F1.PLACE[2001]["harvard university"] = (0.0021, 0.024, "right")
    F1.PLACE[2001]["stanford university"] = (0.0095, 0.0165, "right")
    F1.PLACE[2021]["harvard university"] = (0.00062, 0.0215, "left")
    fig, *_ = F1.figure1()
    save(fig, "Fig1_landscape")
    B.F11.main()
    for ext in (".png", ".pdf"):
        os.replace(os.path.join(V2, "F11_institutions_and_authors" + ext), os.path.join(V2, "S5_institutions_and_authors" + ext))
    Y.F = F1
    Y.main()


if __name__ == "__main__":
    main()
