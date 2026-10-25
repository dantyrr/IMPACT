#!/usr/bin/env python3
"""Validation-gate report for the doc_class reclassification. Read-only on every DB.

Runs `classify` over impact.db papers (dry-run semantics) and writes a markdown
report: current INFERENCE values, overall reclassification and class transitions,
the per-journal share of research reclassified to commentary, a per-journal
breakdown of those research -> commentary changes by the inference signal that
fired (short pages only / iCite only / both) and by pagination shape (bare
number vs page range), samples of reclassified titles, and samples of `letter` titles with research-letter signals.

Usage:
    python scripts/validate_doc_class.py [--out PATH]
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.pipeline.class_inputs import fetch_class_inputs, open_ro  # noqa: E402
from src.pipeline.config import DB_PATH, ICITE_BULK_DB_PATH, PUBMED_FULL_DB_PATH  # noqa: E402
from src.pipeline.doc_class import INFERENCE, class_for_types, classify  # noqa: E402

IMPACT_DB_PATH = DB_PATH
FULL_DB_PATH = PUBMED_FULL_DB_PATH
ICITE_DB_PATH = ICITE_BULK_DB_PATH
DETECTOR_CSV = os.path.join(_REPO_ROOT, "docs", "superpowers", "specs",
                            "2026-10-24-detector-flagged-journals.csv")
DEFAULT_OUT = os.path.join(_REPO_ROOT, "docs", "superpowers", "specs",
                           "2026-10-24-doc-class-validation.md")
SAMPLE_N = 30
BATCH = 50_000

# label -> (slug candidates, journals.name candidates, lower-case)
EXTRA = {
    "nature": (["nature"], ["nature"]),
    "science": (["science"], ["science"]),
    "cell": (["cell"], ["cell"]),
    "nejm": (["the-new-england-journal-of-medicine", "new-england-journal-of-medicine"],
             ["the new england journal of medicine", "new england journal of medicine"]),
    "lancet": (["the-lancet", "lancet"],
               ["the lancet", "lancet", "lancet (london, england)"]),
    "jama": (["jama"], ["jama"]),
    "circulation": (["circulation"], ["circulation"]),
    "jacc": (["journal-of-the-american-college-of-cardiology"],
             ["journal of the american college of cardiology"]),
    "atvb": (["arteriosclerosis-thrombosis-and-vascular-biology"],
             ["arteriosclerosis, thrombosis, and vascular biology"]),
    "plos-one": (["plos-one"], ["plos one"]),
    "nat-commun": (["nature-communications"], ["nature communications"]),
    "sci-rep": (["scientific-reports"], ["scientific reports"]),
    "cell-rep": (["cell-reports"], ["cell reports"]),
    "nrmcb": (["nature-reviews-molecular-cell-biology"],
              ["nature reviews. molecular cell biology", "nature reviews molecular cell biology"]),
    "nrc": (["nature-reviews-cancer"],
            ["nature reviews. cancer", "nature reviews cancer"]),
}
SAMPLE_JOURNALS = ["jama", "nejm", "lancet", "nature", "nrmcb", "nrc"]
LETTER_JOURNALS = ["jama", "nejm", "lancet"]


def resolve(journals_by_slug, journals_by_name, key):
    slugs, names = EXTRA[key]
    for s in slugs:
        if s in journals_by_slug:
            return s
    for n in names:
        if n in journals_by_name:
            return journals_by_name[n]
    return None


SIGNALS = ("short_only", "icite_only", "both")
PAGINATIONS = ("bare", "range", "other")
_RANGE_RE = re.compile(r"\d+\s*-\s*\d+")


def rc_signal(d):
    """Which inference signal(s) turned a paper into commentary, mirroring
    doc_class.classify (commentary only ever comes from that inference)."""
    pages = d["page_count"]
    short = pages is not None and pages <= INFERENCE["max_pages"]
    icite = bool(INFERENCE["use_icite"]) and d["icite_is_research"] is False
    if short and icite:
        return "both"
    return "short_only" if short else "icite_only"


def pagination_shape(pgn):
    """'bare' (digits only, e.g. "5"), 'range' ("101-5"), or 'other' (none, e-locator)."""
    s = (pgn or "").strip()
    if s.isdigit():
        return "bare"
    if _RANGE_RE.fullmatch(s):
        return "range"
    return "other"


def fetch_paginations(full, pmids):
    out = {}
    for i in range(0, len(pmids), 900):
        part = pmids[i:i + 900]
        q = ",".join("?" * len(part))
        out.update(full.execute(f"SELECT pmid, pagination FROM pubmed WHERE pmid IN ({q})", part))
    return out


def is_reply(title):
    t = (title or "").strip().rstrip(".").lower()
    return t.endswith("-reply") or t.endswith("reply")


def evenly(items, n):
    if len(items) <= n:
        return list(items)
    return [items[i * len(items) // n] for i in range(n)]


def md_cell(s):
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def build_report(impact, full, icite):
    journals = impact.execute("SELECT id, slug, name FROM journals").fetchall()
    slug_of = {i: s for i, s, _ in journals}
    by_slug = {s: i for i, s, _ in journals}
    by_name = {(n or "").lower(): s for _, s, n in journals}

    with open(DETECTOR_CSV, newline="") as f:
        detector = [r["slug"] for r in csv.DictReader(f)]
    named = {k: resolve(by_slug, by_name, k) for k in EXTRA}
    wanted = list(dict.fromkeys(detector + [s for s in named.values() if s]))
    wanted_set = set(wanted)
    wanted_ids = {by_slug[s] for s in wanted if s in by_slug}

    transitions, seen, missing = Counter(), 0, 0
    jr = defaultdict(lambda: [0, 0])      # slug -> [old research, research->commentary]
    rc = defaultdict(Counter)             # slug -> research->commentary by signal / pagination
    reclass = defaultdict(list)           # slug -> [(pmid, title, old, new)]
    letters = defaultdict(list)           # slug -> [(pmid, title, pub_date, icite)]
    nonletter_first = defaultdict(dict)   # slug -> title -> earliest pub_date (non-letter)
    sample_slugs = {named[k] for k in SAMPLE_JOURNALS + LETTER_JOURNALS if named[k]}

    last = 0
    while True:
        rows = impact.execute(
            "SELECT pmid, journal_id, title, pub_date, pub_type FROM papers WHERE pmid > ? "
            "ORDER BY pmid LIMIT ?", (last, BATCH)).fetchall()
        if not rows:
            break
        last = rows[-1][0]
        inputs = fetch_class_inputs(full, icite, [r[0] for r in rows])
        pgn = fetch_paginations(full, [r[0] for r in rows if r[1] in wanted_ids])
        for pmid, jid, title, pub_date, pub_type in rows:
            seen += 1
            d = inputs.get(pmid)
            if d is None:
                missing += 1
                continue
            slug = slug_of.get(jid)
            old = class_for_types([pub_type] if pub_type else [])
            new, _ = classify(d["pub_types"], d["has_abstract"], d["page_count"],
                              d["icite_is_research"], d["title"])
            transitions[(old, new)] += 1
            if slug in wanted_set and old == "research":
                jr[slug][0] += 1
                jr[slug][1] += new == "commentary"
                if new == "commentary":
                    sig, shape = rc_signal(d), pagination_shape(pgn.get(pmid))
                    rc[slug][sig] += 1
                    rc[slug][shape] += 1
                    rc[slug][(sig, shape)] += 1
            if slug in sample_slugs:
                if old != new:
                    reclass[slug].append((pmid, title, old, new))
                if new == "letter":
                    letters[slug].append((pmid, title, pub_date, d["icite_is_research"]))
                else:
                    cur = nonletter_first[slug].get(title)
                    if title and (cur is None or (pub_date or "") < cur):
                        nonletter_first[slug][title] = pub_date or ""

    total_changed = sum(n for (o, nw), n in transitions.items() if o != nw)
    out = ["# doc_class validation report", "",
           "Generated by `scripts/validate_doc_class.py` (read-only). Old class = class of the "
           "stored `pub_type` alone; new class = `classify` on the full PubMed type list, "
           "abstract, page count, iCite evidence and title.", "",
           "## Current INFERENCE values", "", "```"]
    out += [f"{k} = {v!r}" for k, v in INFERENCE.items()]
    out += ["```", "", "## Overall", "",
            f"- papers examined: {seen}",
            f"- no row in pubmed_full (skipped): {missing}",
            f"- would be reclassified: {total_changed}", "",
            "### Class transitions (old -> new, changed only)", "",
            "| transition | papers |", "|---|---|"]
    for (o, nw), n in sorted(transitions.items(), key=lambda kv: -kv[1]):
        if o != nw:
            out.append(f"| {o} -> {nw} | {n} |")
    out += ["", "## Per-journal share", "",
            "Share of each journal's old-`research` papers reclassified to `commentary`.", "",
            "| slug | status | research papers | research -> commentary | share |",
            "|---|---|---|---|---|"]
    for slug in wanted:
        if slug not in by_slug:
            out.append(f"| {md_cell(slug)} | absent | | | |")
            continue
        n, c = jr[slug]
        share = f"{100 * c / n:.1f}%" if n else "n/a"
        out.append(f"| {md_cell(slug)} | present | {n} | {c} | {share} |")
    out += ["", "### Research -> commentary by signal and pagination", "",
            "Each journal's research -> commentary papers split by the signal that fired: "
            "`short only` (no abstract and page count <= max_pages, iCite not against), "
            "`iCite only` (no abstract and iCite says not research, pages not short), or `both`. "
            "Pagination: `bare` = MedlinePgn is digits only (e.g. \"5\", counted as 1 page "
            "by parse_page_count, which may be a start page only or a genuine one-page item), "
            "`range` = start-end, `other` = none or an e-locator. `short & bare` = short-only "
            "papers whose pagination was a bare number.", "",
            "| slug | research -> commentary | short only | iCite only | both "
            "| bare | range | other | short & bare |",
            "|---|---|---|---|---|---|---|---|---|"]
    for slug in wanted:
        if slug not in by_slug:
            out.append(f"| {md_cell(slug)} | absent | | | | | | | |")
            continue
        c = rc[slug]
        cells = [jr[slug][1]] + [c[k] for k in SIGNALS] + [c[k] for k in PAGINATIONS] \
            + [c[("short_only", "bare")]]
        out.append(f"| {md_cell(slug)} | " + " | ".join(str(v) for v in cells) + " |")
    unresolved = [k for k, v in named.items() if v is None]
    if unresolved:
        out += ["", "Named journals not found (absent): " + ", ".join(unresolved)]

    out += ["", "## Reclassified title samples", ""]
    for k in SAMPLE_JOURNALS:
        slug = named[k]
        out += [f"### {k} ({slug or 'absent'})", ""]
        if not slug:
            out += ["absent", ""]
            continue
        out += ["| pmid | old -> new | title |", "|---|---|---|"]
        for pmid, title, o, nw in evenly(sorted(reclass[slug]), SAMPLE_N):
            out.append(f"| {pmid} | {o} -> {nw} | {md_cell(title)} |")
        out.append("")

    out += ["## Letter samples with research-letter signals", "",
            "Signals: `icite_is_research` (iCite flag; blank when unknown), `reply_title` "
            "(title ends with Reply), `dup_of_earlier_non_letter` (same title as an earlier "
            "non-letter paper in the journal).", ""]
    for k in LETTER_JOURNALS:
        slug = named[k]
        out += [f"### {k} ({slug or 'absent'})", ""]
        if not slug:
            out += ["absent", ""]
            continue
        out += ["| pmid | title | icite_is_research | reply_title | dup_of_earlier_non_letter |",
                "|---|---|---|---|---|"]
        for pmid, title, pub_date, ic in evenly(sorted(letters[slug]), SAMPLE_N):
            first = nonletter_first[slug].get(title)
            dup = first is not None and first < (pub_date or "")
            icv = "" if ic is None else ("yes" if ic else "no")
            out.append(f"| {pmid} | {md_cell(title)} | {icv} | "
                       f"{'yes' if is_reply(title) else 'no'} | {'yes' if dup else 'no'} |")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    impact, full = open_ro(IMPACT_DB_PATH), open_ro(FULL_DB_PATH)
    icite = open_ro(ICITE_DB_PATH) if os.path.exists(ICITE_DB_PATH) else None
    try:
        text = build_report(impact, full, icite)
    finally:
        impact.close()
        full.close()
        if icite is not None:
            icite.close()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(text)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
