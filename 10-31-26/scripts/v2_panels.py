"""The rule that picks which journals a figure names, so no figure rests on a hand-picked list.

Within a figure's own set of eligible journals: rank by that figure's measure, take the top 3, the 2 nearest the
median and the bottom 3, then add the reference journals. Ties break on the journal's name, so a list never depends
on input order. Writes v2/data/journal_panels.csv: one row per journal per set, with its rank and why it is there.

Usage: python 10-31-26/scripts/v2_panels.py   (from the IMPACT folder)
"""
import csv
import os
import sqlite3

from v2_common import ROOT, write_csv

REFERENCE = ["JAMA", "NEJM", "Lancet", "Nature", "Science", "Cell", "PLoS One", "Sci Rep"]
OLD = os.path.join(ROOT, "10-31-26")


def stratified(items, reference=(), n_top=3, n_mid=2, n_bottom=3):
    """items: (journal, value) pairs, highest value ranked 1. Returns dicts of journal, value, rank, reason."""
    ranked = sorted(items, key=lambda x: (-x[1], x[0]))
    n = len(ranked)
    mid = (n - n_mid) // 2 + (n % 2 == 0 and n_mid % 2 == 1)
    picks = [(i, "top") for i in range(min(n_top, n))]
    picks += [(i, "median") for i in range(mid, mid + n_mid)]
    picks += [(i, "bottom") for i in range(n - 1, max(n - 1 - n_bottom, -1), -1)]
    out, seen = [], set()
    for i, why in picks:
        if ranked[i][0] not in seen:
            seen.add(ranked[i][0])
            out.append({"journal": ranked[i][0], "value": ranked[i][1], "rank": i + 1, "reason": why})
    rank = {j: i + 1 for i, (j, _) in enumerate(ranked)}
    value = dict(ranked)
    for j in reference:
        if j not in seen:
            seen.add(j)
            out.append({"journal": j, "value": value.get(j, ""), "rank": rank.get(j, ""), "reason": "reference"})
    return out


def read(path):
    with open(os.path.join(OLD, path)) as f:
        return list(csv.DictReader(f))


def main():
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    by_name = dict(con.execute("SELECT name, abbreviation FROM journals"))
    by_slug = dict(con.execute("SELECT slug, abbreviation FROM journals"))
    T = read("data/fig9_journal_timing.csv")
    sets = {
        "top_paper_share (Fig 1, all 5,528 journals)":
            [(by_name[r["journal"]], float(r["top_paper_share"])) for r in read("data/fig1a_top_paper_share_2024.csv")],
        "timing_placement (Fig 9B, 2,000+ items)":
            [(r["abbreviation"], float(r["placement_gain"])) for r in T if int(r["items_2014_21"]) >= 2000],
        "reviews_early (Fig 9C, 100+ reviews)":
            [(r["abbreviation"], float(r["reviews_jan_mar"]) - float(r["other_jan_mar"]))
             for r in T if int(r["reviews"]) >= 100 and r["reviews_jan_mar"] and r["other_jan_mar"]],
        "review_lift (F7)":
            [(by_slug[r["slug"]], float(r["lift_from_reviews"])) for r in read("v2/data/f7ab_lift_all_journals.csv")],
    }
    rows = []
    for name, items in sets.items():
        for g in stratified(items, REFERENCE):
            v = g["value"]
            rows.append([name, g["journal"], g["rank"], len(items), round(v, 4) if v != "" else "", g["reason"]])
    write_csv("journal_panels", ["figure_set", "journal", "rank", "eligible_journals", "value", "reason"], rows)
    print(len(rows), "rows")


if __name__ == "__main__":
    main()
