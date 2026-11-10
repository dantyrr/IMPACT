"""Shared set-up for v13: output to 10-31-26/v13, and every "24-month rate" in a figure reads "24-month citation rate".

Import this before any older figure script. The first import of v2_common fixes the output folder, whatever older scripts set later.
The label change patches matplotlib's Text.set_text, so titles, axis labels, legends and annotations all change before layout.
"""
import os
import sys

os.environ.setdefault("FIG_DIR", "v13")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v2_common  # noqa: E402,F401  first import fixes V2 at v13
import matplotlib  # noqa: E402
matplotlib.use("Agg")
from matplotlib.text import Text  # noqa: E402

OLD_TERM, NEW_TERM = "24-month rate", "24-month citation rate"
_set_text = Text.set_text


def set_text(self, s):
    if isinstance(s, str):
        s = s.replace(OLD_TERM, NEW_TERM)
    return _set_text(self, s)


Text.set_text = set_text


def patch(func, *pairs):
    """Re-run a function's source with exact text swaps, in its own module. Each old text must appear exactly once."""
    import inspect
    src = inspect.getsource(func)
    for old, new in pairs:
        assert src.count(old) == 1, (func.__name__, old, src.count(old))
        src = src.replace(old, new)
    exec(src, func.__globals__)
