"""Shared helpers for the v2 figures (10-31-26/v2). Light on purpose: importing this loads no citation data.

Scripts that need the citation matrix import it from make_figures, which also sets the plot style."""
import csv
import json
import os

ROOT = "/Users/dtyrrell/Projects/IMPACT"
V2 = os.path.join(ROOT, "10-31-26", os.environ.get("FIG_DIR", "v2"))   # v3 scripts set FIG_DIR=v3
JSON = os.path.join(ROOT, "docs", "data", "journals")
SETTLED = "2025-11"             # the 24-month rate is read here: export month minus 12
MONTHS = [m for m in range(1, 13) if m != 6]   # June also holds papers with no month
NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ORANGE, SKY = "#E69F00", "#56B4E9"


def save(fig, name):
    import matplotlib.pyplot as plt
    fig.savefig(os.path.join(V2, name + ".png"), bbox_inches="tight")
    fig.savefig(os.path.join(V2, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name, flush=True)


def write_csv(name, header, rows):
    os.makedirs(os.path.join(V2, "data"), exist_ok=True)
    with open(os.path.join(V2, "data", name + ".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def site_rate(slug, month):
    """The 24-month rate the site shows for a journal and month."""
    with open(os.path.join(JSON, slug + ".json")) as f:
        d = json.load(f)
    return next(e["rolling_if"] for e in d["timeseries"] if e["month"] == month)


def rate_weights():
    """How much a citation at each age counts toward the 24-month rate: a paper sits in 24 monthly readings, each counting 12
    months of its citations, so a citation k months after publication is in min(k, 12, 36 - k) readings. Sums to 24 months."""
    import numpy as np
    k = np.arange(36)
    return np.where(k >= 1, np.minimum(np.minimum(k, 12), 36 - k), 0) / 12


def swatch_label(ax, y, text, color, fontsize=6.3):
    """A name above a panel in dark text beside a color square: yellow text is hard to read on white."""
    ax.plot([0.015], [y], marker="s", markersize=fontsize * 0.62, color=color, transform=ax.transAxes, clip_on=False, linewidth=0)
    ax.annotate(text, (0, y), xycoords="axes fraction", xytext=(fontsize * 0.85, 0), textcoords="offset points", fontsize=fontsize, color="#222222", va="center")


def month_index(y, m):
    return y * 12 + m - 1


def month_label(i):
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def place_labels(ax, points, fontsize=6, color="#222222", avoid=(), radii=(7, 11, 16, 22, 30, 40, 52, 66, 84, 105, 130, 160)):
    """Label points close to them without overlapping. points: (x, y, text) in data coordinates; avoid: other points to keep
    clear of. Tries rings of positions around each point and keeps the nearest free one. Set the axis limits first."""
    import math
    from matplotlib.text import Text
    fig = ax.figure
    fig.canvas.draw()
    render = fig.canvas.get_renderer()
    scale = fig.dpi / 72
    frame = ax.get_window_extent(render)
    dots = [ax.transData.transform((x, y)) for x, y, _ in points] + [ax.transData.transform(p) for p in avoid]
    boxes = []
    for x, y, text in points:
        done = None
        for r in radii:
            for k in range(24):
                a = math.pi / 4 + k * math.pi / 12
                dx, dy = r * math.cos(a), r * math.sin(a)
                t = ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=fontsize, color=color,
                                ha="left" if dx >= 0 else "right", va="center", zorder=6,
                                arrowprops=dict(arrowstyle="-", color="#666666", linewidth=0.4, shrinkA=0, shrinkB=1) if r > 7 else None)
                t.update_positions(render)
                b = Text.get_window_extent(t, render)     # the text alone, not its leader line
                clear = (b.x0 >= frame.x0 and b.x1 <= frame.x1 and b.y0 >= frame.y0 and b.y1 <= frame.y1
                         and not any(b.overlaps(o) for o in boxes)
                         and not any(b.x0 - 2 * scale <= d[0] <= b.x1 + 2 * scale and b.y0 - 2 * scale <= d[1] <= b.y1 + 2 * scale for d in dots))
                if clear:
                    done = b
                    break
                t.remove()
            if done:
                break
        if done is None:
            raise ValueError(f"no room for label {text}")
        boxes.append(done)
    return boxes
