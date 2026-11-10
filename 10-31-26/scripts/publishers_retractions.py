"""Publisher per paper and retractions -> data/analysis/publishers.npz, data/analysis/retractions.npz.

Publisher comes from the DOI prefix (10.3390 is MDPI, 10.3389 Frontiers, ...).
Retracted papers are those PubMed tags "Retracted Publication" plus those the
Retraction Watch database (Crossref; data/retraction_watch/retraction_watch.csv)
lists as retracted, matched by PMID or DOI. The retraction date is Retraction
Watch's; failing that, the date of a PubMed retraction notice ("Retraction Notice")
linked to the paper by title ("Retracted: <title>", "Retraction note to: <title>")
within the same ISSN or, failing that, anywhere. Retraction Watch reasons are
grouped into a few flags (REASONS).

Usage: python 10-31-26/scripts/publishers_retractions.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import re
import sqlite3
import sys
import time

import numpy as np

ROOT = "/Users/dtyrrell/Projects/IMPACT"
DATA = os.path.join(ROOT, "data", "analysis")
PREFIXES = {"10.3390": "MDPI", "10.3389": "Frontiers", "10.1371": "PLOS", "10.1155": "Hindawi", "10.7759": "Cureus",
            "10.1038": "Nature Portfolio", "10.1186": "BMC", "10.1007": "Springer", "10.1016": "Elsevier",
            "10.1002": "Wiley", "10.1111": "Wiley", "10.1093": "Oxford UP", "10.1097": "Wolters Kluwer",
            "10.1080": "Taylor & Francis", "10.1177": "SAGE", "10.1136": "BMJ", "10.1001": "AMA (JAMA)",
            "10.1126": "AAAS (Science)", "10.1073": "PNAS", "10.1101": "CSHL (bioRxiv)", "10.2147": "Dove",
            "10.1021": "ACS", "10.1039": "RSC", "10.3892": "Spandidos", "10.18632": "Impact Journals"}
RW_CSV = os.path.join(ROOT, "data", "retraction_watch", "retraction_watch.csv")
REASONS = {   # flag -> phrases in Retraction Watch's "Reason" field
    "paper_mill": ["Paper Mill"],
    "peer_review": ["Compromised Peer Review", "Fake Peer Review", "Concerns/Issues about Peer Review", "Rogue Editor"],
    "image": ["Duplication of/in Image", "Concerns/Issues about Image", "Manipulation of Images"],
    "plagiarism_duplication": ["Plagiarism", "Duplication of/in Article", "Euphemisms for Plagiarism", "Euphemisms for Duplication"],
    "fabrication_misconduct": ["Fabrication", "Falsification", "Misconduct by Author", "Misconduct - Official Investigation"],
    "honest_error": ["Error in Data", "Error in Analyses", "Error in Results", "Error in Methods", "Error by Journal/Publisher"],
    "generated_content": ["Computer-Aided Content or Computer-Generated Content"],
}
PUBLISHERS = sorted(set(PREFIXES.values())) + ["Other", "No DOI"]
_LEAD = re.compile(r"^(?:notice of retraction|retraction notice|retraction note|retraction statement|retraction|retracted"
                   r"|withdrawn|expression of concern and retraction)\s*(?:to|of|for|on)?\s*(?:the\s+)?(?:article|paper)?"
                   r"\s*[:.\-–]*\s*", re.I)


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def publishers(t):
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    code = {p: i for i, p in enumerate(PUBLISHERS)}
    pm, pc = [], []
    cur = con.execute("SELECT pmid, doi FROM papers")
    while rows := cur.fetchmany(2_000_000):
        for p, doi in rows:
            pm.append(p)
            if not doi:
                pc.append(code["No DOI"])
            else:
                pre = doi.split("/", 1)[0].strip().lower()
                pc.append(code[PREFIXES.get(pre, "Other")])
    np.savez(os.path.join(DATA, "publishers.npz"), pmid=np.array(pm, np.int64), code=np.array(pc, np.int8),
             names=np.array(PUBLISHERS))
    print(f"publishers: {len(pm):,} papers, {time.time()-t:.0f}s", flush=True)


def retraction_watch():
    """Retraction Watch retractions: {pmid or doi: (year, month, reason text)}, earliest retraction per paper."""
    out = {}
    with open(RW_CSV, encoding="latin-1", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["RetractionNature"] != "Retraction":
                continue
            m, _, y = r["RetractionDate"].split()[0].split("/")
            v = (int(y), int(m), r["Reason"])
            for k in (r["OriginalPaperPubMedID"], r["OriginalPaperDOI"].strip().lower()):
                if k and k not in ("0", "unavailable") and (k not in out or v[:2] < out[k][:2]):
                    out[int(k) if k.isdigit() else k] = v
    return out


def retractions(t):
    f = sqlite3.connect(f"file:{ROOT}/data/pubmed_full.db?mode=ro", uri=True)
    ret = f.execute("SELECT pmid, issn, pub_year, title FROM pubmed WHERE pub_types LIKE '%Retracted Publication%'").fetchall()
    notes = f.execute("SELECT pmid, issn, pub_year, pub_month, title FROM pubmed "
                      "WHERE pub_types LIKE '%Retraction Notice%'").fetchall()
    by_title = collections.defaultdict(list)
    for p, issn, y, ti in ret:
        by_title[norm(ti)].append((p, issn))
    notice = {}                              # retracted pmid -> (notice pmid, year, month)
    for n, issn, y, m, ti in notes:
        k = norm(_LEAD.sub("", (ti or "").strip()).strip(" \"'“”"))
        cands = by_title.get(k, [])
        same = [p for p, i in cands if i == issn] or [p for p, _ in cands]
        if len(same) == 1 and y:
            p = same[0]
            if p not in notice or (y, m or 6) < notice[p][1:]:
                notice[p] = (n, y, m or 6)

    rw = retraction_watch()
    rw_pmid = {}                             # pmid -> (year, month, reasons) from Retraction Watch
    for k, v in rw.items():
        if isinstance(k, int):
            rw_pmid[k] = v
    dois = {k for k in rw if isinstance(k, str)}
    con = sqlite3.connect(f"file:{ROOT}/data/impact.db?mode=ro", uri=True)
    cur = con.execute("SELECT pmid, doi FROM papers WHERE doi IS NOT NULL")
    while rows := cur.fetchmany(2_000_000):
        for p, doi in rows:
            d = doi.strip().lower()
            if d in dois and p not in rw_pmid:
                rw_pmid[p] = rw[d]
    print(f"Retraction Watch: {len(rw_pmid):,} retracted papers with a PMID or a DOI in IMPACT, {time.time()-t:.0f}s", flush=True)

    rp = np.array(sorted({p for p, *_ in ret} | set(rw_pmid)), np.int64)
    year, month, src = [], [], []
    flags = np.zeros((len(rp), len(REASONS)), bool)
    for i, p in enumerate(rp):
        if p in rw_pmid:
            y, m, reason = rw_pmid[p]
            year.append(y); month.append(m); src.append(1)
            flags[i] = [any(x in reason for x in phrases) for phrases in REASONS.values()]
        elif p in notice:
            year.append(notice[p][1]); month.append(notice[p][2]); src.append(2)
        else:
            year.append(0); month.append(0); src.append(0)
    np.savez(os.path.join(DATA, "retractions.npz"), pmid=rp, notice_year=np.array(year, np.int16),
             notice_month=np.array(month, np.int8), date_source=np.array(src, np.int8),
             pubmed_flag=np.isin(rp, [p for p, *_ in ret]), reasons=flags, reason_names=np.array(list(REASONS)))
    ny = np.array(year)
    print(f"retractions: {len(rp):,} retracted ({len(ret):,} PubMed-flagged), {int((ny > 0).sum()):,} dated "
          f"({src.count(1):,} Retraction Watch, {src.count(2):,} PubMed notice), {time.time()-t:.0f}s", flush=True)


if __name__ == "__main__":
    t = time.time()
    retractions(t)
    if "--retractions-only" not in sys.argv:
        publishers(t)
