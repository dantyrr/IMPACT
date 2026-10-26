# IMPACT Methodology

IMPACT computes a rolling monthly citation rate for every PubMed-indexed journal from public data. This document states exactly what the code does. It does not claim agreement with any proprietary metric, and IMPACT makes no comparison to Clarivate's published values.

---

## The citation rate

For a target month M:

```
Citation rate(M) =

    citations received during the 12 months ending at M
    by citable items published in the paper window

    ÷ number of citable items published in the paper window
```

Numerator and denominator are taken over the same set of papers: the citable items in the paper window. A citation to an editorial, a news item or an erratum is not counted, and those items are not in the denominator.

### Windows

The citation window is always the 12 months ending at M. The paper window ends the month before the citation window starts, plus an optional gap. Three variants are computed:

| Variant | Paper window | Papers published |
|---------|--------------|------------------|
| 24-month (default) | 24 months, no gap | the 24 months ending 12 months before M (12 to 35 months before M) |
| 12-month | 12 months, no gap | the 12 months ending 12 months before M (12 to 23 months before M) |
| 5-year (years 2-6) | 60 months, after a 12-month gap | the 60 months ending 24 months before M (24 to 83 months before M) |

Example for M = 2025-02: the citation window is 2024-03 to 2025-02; the 24-month paper window is 2022-03 to 2024-02 (35 to 12 months before M); the 12-month paper window is 2023-03 to 2024-02; the 5-year window is 2018-03 to 2023-02.

Each paper is placed in a window by its publication year and month (see "Dates" below), and each citation by the publication year and month of the citing paper.

### Why rolling and monthly

A fixed calendar-year rate changes once a year. A rolling rate can be computed at every month, so the series shows when a journal's rate moved rather than only that it differs between two years.

---

## Citable items

Every paper receives one document class. PubMed's publication-type list is read in full, not just the first type, and the first group below with any matching type wins:

| Priority | Class | PubMed publication types |
|----------|-------|--------------------------|
| 1 | erratum | Published Erratum, Retraction of Publication, Retraction Notice, Expression of Concern |
| 2 | guideline | Practice Guideline, Guideline, Consensus Development Conference |
| 3 | review | Systematic Review, Meta-Analysis, Review |
| 4 | case_report | Case Reports |
| 5 | editorial | Editorial |
| 6 | letter | Letter, Comment, Editorial Comment |
| 7 | other | News, Biography, Obituary, Interview, Portrait, Congress |
| 8 | research | Journal Article |

A paper with no match is `other`. "Retracted Publication" is the tag on the retracted paper itself and does not make it an erratum; only the notices do. A guideline that is also tagged Review is a guideline; both are citable, so the order affects labels only.

**Citable classes: research, review, case_report, guideline.** These form the numerator and denominator of the citation rate. PubMed's own publication-type column is stored unchanged; the class is stored separately.

### Inference for front matter typed as "Journal Article"

PubMed types some commentary and front matter as "Journal Article". A paper that PubMed types only as research and that has no abstract is reclassified as `commentary` (not citable, class source "inferred") if either:

- its page count is 2 or fewer, or
- iCite reports it is not a research article.

Papers with an abstract keep the PubMed class. A missing page count or a missing iCite value is not evidence. iCite's research-article flag is therefore evidence for this rule only; it no longer sets the research flag by itself. A pagination that is a single page number (for example "5") counts as one page.

### Short research formats

Items that PubMed types as "Letter" are not counted as citable. Research letters and other short original reports that a journal publishes under that type are therefore excluded, and the citation rate undercounts short research formats for journals that use them. Letters are not recovered in this release. PubMed gives research letters and ordinary correspondence the same "Letter" type, and iCite marks few of them as research articles, so neither source separates the two reliably. Separating them is planned for a later release.

### Research-only rate

IMPACT also reports a rate over research items only (`research` class in both numerator and denominator). The gap between this and the citable-items rate shows how much of a journal's rate depends on reviews, case reports and guidelines.

---

## How this differs from Clarivate's Journal Impact Factor

Clarivate's Journal Impact Factor divides all citations received in a year to a journal's items from the previous two years by the number of citable items in those years. Its numerator therefore also counts citations to non-citable items such as editorials and letters, while its denominator does not include them.

IMPACT's numerator counts only citations to citable items, so the same set of papers is in the numerator and denominator. Other differences:

| Aspect | Clarivate JIF | IMPACT |
|--------|---------------|--------|
| Numerator | Citations to all items | Citations to citable items only |
| Citation data | Web of Science (proprietary) | iCite Open Citation Collection (PubMed-indexed papers citing PubMed-indexed papers) |
| Update frequency | Annual | Monthly |
| Windows | Calendar years | Rolling months (three variants above) |
| Item classification | Editorial classification, not public | Rules above, public |
| Journal coverage | Journals selected for Web of Science | Journals indexed by PubMed |

IMPACT values are expected to differ from Clarivate's because of all of the above. They should not be read as estimates of the Clarivate figure.

---

## Reliability flags

Flags are computed on the most recent point whose 12-month citation window ended at least 12 months before the export month, so that the window is complete. A journal with no such point has no flags.

| Flag | Condition |
|------|-----------|
| `small_research_sample` | fewer than 20 research items in the paper window |
| `small_review_sample` | 1 to 14 review items in the paper window (a journal with no reviews has no review rate, so it is not flagged) |
| `review_journal` | reviews are 50% or more of citable items |
| `inferred_types` | 10% or more of the papers in the window have an inferred class |

---

## Data sources

**PubMed baseline and update files.** `scripts/build_pubmed_full.py` streams the annual baseline and then each update file in order into `data/pubmed_full.db`. Update files re-deliver and delete records, so the order matters. For each record the parser stores the journal ISSN, publication date, title, publication types, abstract presence, page count, and the author list with affiliations. The same parser serves the bulk build, the per-journal pipeline and the weekly update. Papers dated before 2003 are out of scope (they are not needed for the 24-month window of the earliest snapshot, January 2005); the upper year is the current calendar year plus one.

**iCite Open Citation Collection.** Supplies the citation links (which PMID cites which). It also supplies the research-article flag used as evidence in the inference rule above.

**PubMed E-utilities.** The weekly update finds new papers by date, fetches their full records through EFetch, and fetches iCite references for them.

### Dates

A paper's publication date is its electronic publication date when PubMed records one, otherwise the journal issue date (including the year and month taken from a free-text date such as "2023 Jan-Feb"). When only a year is given the month is set to June. The weekly update uses the same parser, so papers added weekly are dated the same way as papers in the bulk build.

### Citation months

iCite gives the year of each citation but not the month. Every citing paper is also a PubMed record, so IMPACT takes the citing paper's publication month from `pubmed_full.db`; for very recent citing papers not yet there, a PubMed lookup is used. Where a month cannot be resolved the bulk pipeline sets it to June; the weekly update uses the stored month of the citing paper, or January if none is stored.

```
Paper P published 2022-03.
iCite: cited_by = [A, B, C ...]
A is dated 2022-06, B 2022-09, C 2023-01 ...
P received one citation in each of those months.
```

This lets the rate be computed for any past month.

---

## Authors and geography

The Authors section's first-author and last-author fields come from PubMed's author list. Before about 2014, PubMed recorded only the first author's affiliation, so affiliations of other authors, and the geography counts built from them, are incomplete for earlier years.

Countries and US states are parsed from affiliation strings by one parser (`src/pipeline/affil_location.py`) used everywhere. The browser uses a port of it (`docs/js/affil-location.js`, tables generated by `scripts/build_affil_places_js.py`), checked against the Python parser by `tests/test_affil_location_js.py`. Earlier releases used a different country parser, so country counts for some journals and years may differ from earlier releases.

**Geography and collaboration.** `scripts/export_geography.py` writes one file per journal (`geo/{slug}.json`) and one for all tracked journals together (`geo/_all.json`). It counts citable items (research, review, case report, guideline) published from 2005 on, by publication year, using every author's affiliations (`src/pipeline/geo_aggregate.py`):

- A paper *involves* a country when at least one of its authors has an affiliation there. Each involved country counts the paper once ("papers involving"). Fractional credit splits the paper's credit of 1 evenly over its countries.
- US states are counted the same way over papers with a US affiliation, and the US map's shares use those papers as the denominator.
- A paper is international when it involves two or more countries.
- A pair of countries (or states) counts the papers that involve both. Papers involving more than 10 countries (or states) are left out of the pair counts, so large consortia do not dominate them; they still count for each region.
- A share is papers involving the region in the chosen years divided by papers with at least one located affiliation in those years. Comparisons show the difference in share in percentage points.

**Collaboration reach** (Authors section) applies the same rules in the browser to one researcher's included papers, reading their affiliations from PubMed EFetch. Name searches can include namesakes; excluded papers are left out.

Institutions are not resolved yet: an affiliation counts for its country and state, not for a hospital or university.

---

## Limitations

1. **PubMed is not all of science.** Coverage is strongest in biomedicine and thin in some other fields. Citations from papers outside PubMed are not counted.
2. **Classification relies on PubMed publication types.** They are assigned by publishers and indexers and are not uniform across journals. Inference corrects only the front-matter case above.
3. **Short research formats.** See "Short research formats" above.
4. **Dates.** Using the electronic date means a paper can fall in a different window than its print date would give. Papers with only a year are placed in June.
5. **Self-citations** are not excluded.
6. **Recent months.** The newest citation windows are incomplete because citing papers appear in iCite with a delay, so the rate for recent months reads low. A month is settled once its citation window ended at least 12 months before the export month. The headline rate, the research and review rates, the paper counts and the flags all come from the latest settled month; each card is that month's rolling rate for the selected window, the same value the chart shows there. The charts still draw the months after it, faded under a grey band marked Provisional.

---

## Reproducing

All code is at <https://github.com/dantyrr/IMPACT>. In outline: `scripts/build_pubmed_full.py` builds `data/pubmed_full.db`; `scripts/run_pipeline_bulk.py` fills `data/impact.db` per journal; `scripts/compute_snapshots.py` computes the rate at every month and exports JSON. The formula is `ImpactCalculator.compute_rolling_if` in `src/pipeline/impact_calculator.py`; the classes are in `src/pipeline/doc_class.py`; the flags are in `src/pipeline/journal_flags.py`.
