"""Shared set-up for v10: the v8 publisher rules plus institution names merged by data/analysis/institution_merge.csv (see v10_merge.py).

Import this first. It patches, in memory, how Figure 1, S5 and the site's yearly counts read institutions, so older scripts and outputs stay as they were.
"""
import collections
import csv
import inspect
import os
import pickle
import sys

os.environ.setdefault("FIG_DIR", "v10")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v2_common  # noqa: E402,F401  first import fixes V2 at v10
import v8_figs as V8  # noqa: E402
import v7_fig1 as F1  # noqa: E402
import v3_f11 as F11  # noqa: E402
from make_figures import DATA, SYSTEM_NAMES, np  # noqa: E402

MERGES = {r["name"]: r["merged_into"] for r in csv.DictReader(open(os.path.join(DATA, os.environ.get("INST_MERGE", "institution_merge.csv"))))}
_load = F1.load
SMALL = {"of", "and", "the", "at", "in", "for", "de", "di", "du"}
UPPER = {"eth", "ku", "cnrs", "inserm", "md", "ucl", "nyu"}


def display(key):
    """A plain name for a merged parent: the raw names hold whichever variant came first, such as 'Harvard University Medical School'."""
    words = key.replace(" s ", "'s ").split()
    return " ".join(w.upper() if w in UPPER else w if i and w in SMALL else w.capitalize() for i, w in enumerate(words))


def load():
    """Figure 1's data with each merged name's papers moved to its parent."""
    year, flag, inst, code, country, K = _load()
    index = {k: i for i, k in enumerate(K["keys"])}
    to = np.arange(len(K["keys"]) + 1, dtype=np.int64)
    for child, parent in MERGES.items():
        if child in index and parent in index:
            to[index[child]] = index[parent]
    to[-1] = -1
    for parent in set(MERGES.values()):
        K["names"][parent] = display(parent)
    return year, flag, to[inst], code, country, K


F1.load = load


def institutions():
    """S5's links with merged names added together. A paper naming both a parent and a merged name counts twice, as it did before."""
    links = os.environ.get("INST_LINKS")          # already merged, once per paper
    d = pickle.load(open(os.path.join(DATA, links or "institutions.pkl"), "rb"))
    c = pickle.load(open(os.path.join(DATA, "inst_country.pkl"), "rb"))["countries"]
    keys = d["keys"]
    index = {k: i for i, k in enumerate(keys)}
    for child, parent in MERGES.items():
        if child in index and parent in index:
            a, b = index[child], index[parent]
            if not links:
                d["all"][b] += d["all"][a]
                d["all"][a] = 0
                for v in d["j"].values():
                    v[b] += v[a]
                    v[a] = 0
            if child in c:
                c.setdefault(parent, collections.Counter()).update(c[child])
    N = sum(d["j"].values())
    rows = []
    for i in np.flatnonzero(d["all"] >= 1000):
        k = keys[i]
        if k in SYSTEM_NAMES or k in F11.NOT_PLACES or k not in c:
            continue
        country, n = c[k].most_common(1)[0]
        if n / sum(c[k].values()) < 0.8:
            continue
        rows.append((i, k, country, F11.region(country)))
    return d, N, rows


F11.institutions = institutions
# S5A now names six institutions above the line: the labels sit to the left of the dots, clear of them and of the equal-share line.
_src = inspect.getsource(F11.main)
_new = (_src.replace("(high, 0.0062, np.geomspace(0.075, 0.021, len(high)))", "(high, 0.003, np.geomspace(0.1, 0.021, len(high)))").replace("relpos=(0, 0.5)", "relpos=(1 if x0 < 0.004 else 0, 0.5), patchA=None")
        .replace('fontsize=6, color=INK, va="center", zorder=6', 'fontsize=6, color=INK, va="center", ha="right" if x0 < 0.004 else "left", zorder=6').replace("if y[i] / x[i] >= 1.5), key=lambda i: x[i])", "if y[i] / x[i] >= 1.5), key=lambda i: -y[i])"))
assert _new.count("patchA=None") == 1 and 'ha="right"' in _new and "0.003, np.geomspace" in _new and "key=lambda i: -y[i])" in _new
exec(_new, F11.__dict__)
