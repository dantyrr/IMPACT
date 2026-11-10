"""v11: Figure 1 and S5 with hospitals in their universities, on wider axes.

Usage: python 10-31-26/scripts/v11_figs.py [fig1|s5]   (from the IMPACT folder; both if none given)
"""
import inspect
import os
import sys

os.environ["FIG_DIR"] = "v11"
os.environ["INST_MERGE"] = "institution_merge_v11.csv"
os.environ["INST_LINKS"] = "institutions_v11.pkl"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v10_base as B  # noqa: E402
from v2_common import V2, save  # noqa: E402

F1 = B.F1
_src = inspect.getsource(F1.bubbles)
_new = _src.replace("lim = np.array([1e-4, 1e-2])", "lim = np.array([1e-4, 2e-2])").replace("ax.set_ylim(3.6e-5, 3.2e-2)", "ax.set_ylim(3.6e-5, 9e-2)")
assert _new.count("2e-2") == 1 and "9e-2" in _new
exec(_new, F1.__dict__)
NAMES = {"harvard university": "Harvard", "stanford university": "Stanford", "university of oxford": "Oxford", "university college london": "UCL", "chinese academy of sciences": "Chinese Acad Sci", "peking university": "Peking",
         "university of tokyo": "Tokyo", "national university of singapore": "Natl Univ Singapore"}
PLACE = {2001: {"harvard university": (0.0055, 0.062, "right"), "stanford university": (0.00105, 0.034, "right"), "university of oxford": (0.0005, 0.0205, "left"), "university college london": (0.00075, 0.0125, "left"),
                "university of tokyo": (0.018, 0.0034, "right"), "chinese academy of sciences": (0.018, 0.0015, "right"), "national university of singapore": (0.018, 0.0005, "right"), "peking university": (0.018, 0.00024, "right")},
         2021: {"harvard university": (0.0032, 0.066, "right"), "stanford university": (0.00105, 0.04, "right"), "university of oxford": (0.0005, 0.0245, "left"), "university college london": (0.0005, 0.0155, "left"),
                "chinese academy of sciences": (0.018, 0.027, "right"), "peking university": (0.018, 0.0048, "right"), "university of tokyo": (0.018, 0.0023, "right"), "national university of singapore": (0.018, 0.00072, "right")}}


def fig1():
    F1.publisher_panel = B.V8.publisher_panel
    F1.NAMES, F1.PLACE = NAMES, PLACE
    fig, *_ = F1.figure1()
    save(fig, "Fig1_landscape")


def s5():
    B.F11.main()
    for ext in (".png", ".pdf"):
        os.replace(os.path.join(V2, "F11_institutions_and_authors" + ext), os.path.join(V2, "S5_institutions_and_authors" + ext))


if __name__ == "__main__":
    for job in sys.argv[1:] or ("fig1", "s5"):
        {"fig1": fig1, "s5": s5}[job]()
