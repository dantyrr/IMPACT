# Paper Figures on the IMPACT Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let site visitors make most of the JIF paper's figures for any journal or paper, without recomputing anything.

**Architecture:** Phase 1 is browser code only, using files already on R2. Phase 2 adds small read-only exports from analysis files that already exist, plus the cards that show them. Pure calculations go in one new file so node can test them, and the site-wide charts go in a new tab file, as `geo-tab.js` does.

**Tech Stack:** Vanilla JS, Chart.js 4.4.0 (no build step); Python 3.11 and NumPy for exports; pytest, with node for JS tests.

**Spec:** The owner's request of 2026-11-06, with the figures and legends in `10-31-26/v2/` (`figure_legends_v2.docx`, `data/figure_legends.json`).

## What "no recomputing" means here

No re-run of the pipeline, and no new pass over the `citations` table. Phase 1 reads only what the browser already fetches. Phase 2 only reformats files already in `data/analysis/` and `10-31-26/`.

Those analysis files are a snapshot from 2 Nov 2026, and the weekly update doesn't refresh them. Everything from Phase 2 is labelled "as of Nov 2026" on the site, and refreshing it later would be a separate decision.

## What each figure becomes

| Figure | On the site | Task |
|---|---|---|
| F1 A, B (one paper's history) | Paper page, for any PMID. The JIF overlay exists; adds the share the JIF counts | 3 |
| F1 C, D, E, G, H | Landscape tab | 10 |
| F1 F, F2 C (reviews by month) | New journal card, for any journal | 2 |
| F2 A, B (timing) | "How this journal compares" card, and Landscape | 7, 10 |
| F2 E | Landscape | 10 |
| F2 F, G (moving a paper) | "Move this paper" control in Influence | 4 |
| F4 A, B, D | Landscape; A also in the compare card | 7, 10 |
| F4 C (with and without top paper) | New journal card, any journal | 2 |
| F5 A, B | Landscape. Rate without guidelines already exists | 10 |
| F5 C, D (recurring series) | "Without recurring series" option on the journal chart | 9 |
| F6 A, C (who cites a journal) | "Who cites this journal" card, any journal | 8 |
| F7 A, B | Compare card and Landscape | 7, 10 |
| F7 C, F8 (rate and papers per year) | **Already on the site** (rate toggle, Compare, Article Type Mix). Adds a lift label | 2 |
| F9 (publishers) | Landscape | 10 |
| F10 A (citing countries) | "Who cites this journal" card, any journal, 2024 | 8 |
| F10 C, E, and the over-time alternative | Landscape, for the journals in the figure only | 10 |
| Authors' countries over time | Stacked view on the Geography trend chart, any journal | 5 |
| F11 (institutions, author lists) | Landscape | 10 |
| F12 A, B (retractions by year) | New journal card, any journal, and Landscape | 6, 10 |
| F12 C–F | Landscape | 10 |
| **Citations before and after retraction** | Paper page, any retracted paper | 6 |

**Left out, because they would need recomputing:**
- Citing countries by year for every journal (done for the 22 journals in F10 only).
- Matched controls for one chosen paper.
- F2 D (rotating publication months) for any journal.
- F6 D–F (who cites a guideline family, by quarter).
- F3 (window tests), which stay in the paper; its definitions are already on the Methodology page.
- F13, which you may drop.

## Findings that shape the plan

- **Retracted papers are mostly missing from the site's files.** `papers/{slug}.json` holds each journal's 2,000 most-cited papers, so PLOS One's file has 9 of its 1,430 retracted papers. The paper page can't rely on those files.
- **The live iCite counts on the paper page include citations from retraction notices.** The paper excludes those, so a retracted paper's year-of-retraction bar would disagree with the paper. Task 6 ships our own yearly counts, which are small: 2.3 MB across 35,203 papers.
- **Only 26 retracted papers are flagged in `impact.db`.** The list comes from `retractions.npz`: 37,389 papers, 33,787 of them dated.
- **21 listed papers were later reinstated,** and 62 have only a non-retraction entry in Retraction Watch. The public label must handle these.
- **The monthly `pub_by_type` in the journal JSON covers every paper,** not just the top 2,000, so month analyses work for all journals. June still holds undated papers.
- **5,681 of 8,628 journals have at most 2,000 citable items,** so `papers/{slug}.json` is complete for them. For larger journals it's complete for top papers, which is what F4 C needs, but not for every series paper.

## Global Constraints

- No build step; edit `docs/` directly, with no new outside libraries. `index.html` version strings are bumped when a file changes (currently `app.js?v=47`, `style.css?v=13`).
- Charts use Chart.js 4.4.0 and the Okabe-Ito palette through `chartManager.palette`.
- Naming: JS camelCase, CSS and HTML IDs kebab-case, Python snake_case.
- Exports read databases with `mode=ro` and don't change `impact.db`. Any citation read filters `citing_class IS NULL`.
- Every chart gets the site's PNG download bar, and a CSV download where its data is tabular.
- Site wording stays neutral. No "gaming" or similar on any page, and no journal is singled out in text. Retraction text states the date, reasons and source only.
- The Autophagy Guidelines paper is not called out by name in any site text.
- R2 uploads, commits and pushes need the owner's go-ahead. No Co-Authored-By line.
- `docs/data/` subfolders stay gitignored and are served from R2, through `dataLoader`.

## Review Focus

1. **A PMID with no retraction record, or a failed fetch of the shard:** the paper page renders as it does today, with no error.
2. **A retracted paper with no date (3,602 papers):** shows "Retracted, date not known", with no before and after split.
3. **A reinstated paper (21 papers):** shows "Retracted, later reinstated", never plain "Retracted".
4. **A journal missing from a measure (only 2,457–5,528 journals have each one):** the compare card leaves that row out, and doesn't show a percentile.
5. **A journal with no `papers` file, or under 2 years of `timeseries`:** new cards hide, and the rest of the journal page still loads.

---

## Phase 1: browser only, no new data

### Task 1: Shared calculations

**Files:**
- Create: `docs/js/site-metrics.js`
- Create: `tests/js/site_metrics.js` (node runner, as `tests/js/parse_affils.js`)
- Create: `tests/test_site_metrics_js.py` (skips if node is missing, as `tests/test_affil_location_js.py`)
- Modify: `docs/index.html` (load the script before `app.js`)

**Interfaces:**
- Produces, as globals on `SiteMetrics`:
  - `jifShare(cy, pubYear) -> {counted, total, share}`: `cy` is `{year: count}`.
  - `topPaperSeries(papers, timeseries, citable) -> [{year, rate, rateWithout, share, pmid, title}]`: reads the December reading of each year for the denominator.
  - `earlyShare(timeseries) -> [{year, reviews, other, reviewsEarly, otherEarly}]`: January to March share per year, June left out of both.
  - `liftAt(entry) -> number | null`: all-citable rate over research-only rate, minus 1.
  - `movedJif(timeseries, cm, pubMonth, months, year) -> {before, after, ownBefore, ownAfter}`: moves one paper and its monthly citations; positive `months` is later, negative earlier.
  - `regionOf(country) -> string`: the six regions of F10.

- [ ] **Step 1: Write the failing tests** in `tests/test_site_metrics_js.py`, with small fixtures:

```python
def test_jif_share_counts_two_years_after_publication():
    assert run("jifShare", {"2010": 5, "2011": 10, "2012": 20, "2013": 65}, 2010) == {"counted": 30, "total": 100, "share": 0.3}

def test_early_share_leaves_out_june():
    # 10 reviews in Jan, 10 in Jul, 30 in Jun -> 0.5, not 0.2
    assert run("earlyShare", FIXTURE_TS)[0]["reviewsEarly"] == 0.5

def test_moved_jif_of_zero_months_changes_nothing():
    r = run("movedJif", FIXTURE_TS, FIXTURE_CM, 11, 0, 2021)
    assert r["before"] == r["after"] and r["ownBefore"] == r["ownAfter"]

def test_moved_jif_crossing_the_year_moves_the_window():
    # a December 2019 paper moved 1 month later counts 2021-22, not 2020-21
    r = run("movedJif", FIXTURE_TS, {"2020-12": 10, "2022-06": 4}, 12, 1, 2022)
    assert r["ownBefore"] == 10 and r["ownAfter"] == 14

def test_top_paper_series_matches_the_paper_for_cell():
    # uses docs/data; skip if the file is absent. F4 gives Cell 4.7% for 2024
    row = next(x for x in cell_series() if x["year"] == 2024)
    assert abs(row["share"] - 0.047) < 0.002

def test_lift_with_no_research_is_null():
    assert run("liftAt", {"by_type": {}}) is None
```

- [ ] **Step 2: Run** `python -m pytest tests/test_site_metrics_js.py -v`. Expected: FAIL, `site-metrics.js` not found.
- [ ] **Step 3: Implement `docs/js/site-metrics.js`** as pure functions with no DOM access.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** with `feat: shared calculations for the paper's figures on the site`.

### Task 2: Three additions to the journal page

**Files:**
- Modify: `docs/index.html` (after `#drivers-wrap`), `docs/js/app.js` (`showJournalDetail`), `docs/js/chart-manager.js`, `docs/css/style.css`

**Interfaces:** Consumes `SiteMetrics.topPaperSeries`, `earlyShare`, `liftAt`. Adds `_renderTopPaperCard(data, papers)` and `_renderCalendarCard(data)` to `IMPACTApp`.

- [ ] **Step 1: Add the lift label** to `#detail-metrics`: "All citable items +X% vs research only", at the settled month.
- [ ] **Step 2: Add a "Reliance on one paper" card:** the JIF-style rate with and without each year's top paper (F4 C), the top paper's share, and its title linking to the paper page.
- [ ] **Step 3: Add a "Publication calendar" card:** share of reviews and of other items published January to March by year (F1 F). A note says June is left out because it holds undated papers.
- [ ] **Step 4: Hide each card** when its data is missing (Review Focus 5). Reuse `this.papersDataCache`, so no second fetch happens.
- [ ] **Step 5: Verify in the preview** (`python -m http.server -d docs`) on Cell, Circulation, a journal under 2 years old, and one with no papers file. Expected: cards match F4 C for Cell; no console errors on the others.
- [ ] **Step 6: Commit** with `feat: journal page shows reliance on one paper and the publication calendar`.

### Task 3: How much of a paper's citations the JIF counts

**Files:** Modify `docs/js/app.js` (`_renderPaperAnalytics`), `docs/index.html`

- [ ] **Step 1: Add one stat card to `#paper-analytics-stats`:** "The two JIF years hold X% of this paper's citations", from `SiteMetrics.jifShare` on the iCite yearly counts.
- [ ] **Step 2: Verify** PMID 21376230 shows about 8% and 16275915 about 1%. iCite counts differ slightly from F1, so a small difference is fine.
- [ ] **Step 3: Commit** with `feat: paper page shows the share of citations a JIF counts`.

### Task 4: Move a paper in Influence

**Files:** Modify `docs/index.html`, `docs/js/app.js` (`_renderInfluenceChart`), `docs/js/chart-manager.js`

**Interfaces:** Consumes `SiteMetrics.movedJif`.

- [ ] **Step 1: Add a "Move this paper" control** for a single seed paper: −11 to +11 months.
- [ ] **Step 2: Show the result:** the journal's JIF-style rate in the paper's biggest year, before and after, and the paper's own JIF-counted citations. The control is disabled, with a note, when the paper has no `cm` entry (it's outside the journal's top 2,000).
- [ ] **Step 3: Verify** the Radiomics paper in `f2g_moved_earlier.csv` (Radiology, Nov 2015), moved 10 months earlier. Expected: own counted citations about double, journal rate up about 2.5%, as in F2 G.
- [ ] **Step 4: Commit** with `feat: Influence can move a paper's publication date`.

### Task 5: Stacked view of authors' countries

**Files:** Modify `docs/js/geo-tab.js` (`_renderTrend`), `docs/index.html`

**Interfaces:** Consumes `SiteMetrics.regionOf`.

- [ ] **Step 1: Add a toggle on the trend chart:** Lines (today's view) or Stacked by region. Stacked sums to 100% per year using `this.data.countries`.
- [ ] **Step 2: Start the stacked view at 2014** with a note: PubMed recorded only the first author's affiliation before then. The chart title says "authors", because these aren't citers.
- [ ] **Step 3: Verify** that each year sums to 100% and that scope and year controls still work.
- [ ] **Step 4: Commit** with `feat: Geography trend can be stacked by region`.

## Phase 2: small exports from existing analysis files

All exporters live in `scripts/export_site_extras.py`, one function each, run as `python scripts/export_site_extras.py [retractions|measures|citers|series|landscape]`. Tests go in `tests/test_export_site_extras.py`. Each task's files need one upload after your go-ahead (Task 11).

### Task 6: Retractions

**Files:**
- Create: `scripts/export_site_extras.py` (`export_retractions(out_dir: str) -> dict`)
- Create: `tests/test_export_site_extras.py`
- Modify: `docs/js/data-loader.js` (`loadRetraction(pmid)`, `loadRetractionSummary()`), `docs/js/app.js` (`_renderPaperAnalytics`, `showJournalDetail`), `docs/js/chart-manager.js` (`createPaperCitationChart`), `docs/index.html`

**Interfaces:**
- Produces `retractions/{pmid % 64}.json`: `{"pmid": {"y": 2022, "m": 4, "r": ["paper_mill"], "s": "rw", "st": "retracted", "py": 2019, "cy": {"2019": 3}}}`. `y` and `m` are null if undated; `s` is `rw` or `pubmed`; `st` is `retracted` or `reinstated`; `cy` is absent for papers not in `cites.npz`.
- Produces `retractions/summary.json`: `{slug: {"pub": {year: n}, "ret": {year: n}, "items": n}}`.

- [ ] **Step 1: Write failing tests:**

```python
def test_every_listed_paper_is_exported_once(export):
    assert export["papers"] == 37389

def test_reinstated_papers_are_marked(export):
    assert sum(1 for r in export["rows"] if r["st"] == "reinstated") == 21

def test_undated_papers_have_no_date(export):
    assert sum(1 for r in export["rows"] if r["y"] is None) == 3602

def test_counts_leave_out_notices_and_match_the_matrix(export, cites):
    assert export["rows_by_pmid"][SAMPLE]["cy"] == cites.nonzero_years(SAMPLE)

def test_shards_cover_every_pmid(tmp_path, export):
    assert sum(len(json.load(open(f))) for f in shard_files(tmp_path)) == 37389
```

Reinstated comes from `RetractionNature == "Reinstatement"` in `data/retraction_watch/retraction_watch.csv`. Publisher and journal slug come from `cites.npz` and `impact.db`, read-only.

- [ ] **Step 2: Run** `python -m pytest tests/test_export_site_extras.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `export_retractions`,** run it, and check the total is about 2.3 MB.
- [ ] **Step 4: Paper page.** When a record exists: a banner with the status, date, reasons and "Source: Retraction Watch" or "Source: PubMed". The yearly chart uses our `cy`, with bars before retraction in one color, after in another, and a dashed line at the retraction year. Two stat cards: citations before and citations after. A note says citations from retraction notices are left out. If `cy` is absent, it keeps the iCite counts and says they may include notices.
- [ ] **Step 5: Journal page.** A "Retractions" card when the journal has any: retracted papers by year published and by year retracted, plus the rate per 10,000 items.
- [ ] **Step 6: Add Review Focus tests** for no record, undated and reinstated, in `tests/test_site_metrics_js.py`, through a `retractionBanner(record) -> {text, split}` function added to `site-metrics.js`.
- [ ] **Step 7: Verify in the preview** with a dated, an undated, a reinstated and a never-retracted PMID. Expected: Review Focus 1–3 hold.
- [ ] **Step 8: Commit** with `feat: citations before and after retraction on the paper page`.

### Task 7: How this journal compares

**Files:** Modify `scripts/export_site_extras.py`, `tests/test_export_site_extras.py`, `docs/js/data-loader.js`, `docs/js/app.js`, `docs/index.html`

**Interfaces:** Produces `journal_measures.json`: `{"measures": {key: {"label", "unit", "n", "bins", "counts"}}, "journals": {slug: {key: value}}}`, from `fig1a_top_paper_share_2024.csv` (top-paper share), `f7ab_lift_all_journals.csv` (lift), `f6a_two_screens.csv` (largest outside journal) and `fig9_journal_timing.csv` (timing).

- [ ] **Step 1: Write failing tests:** every measure has the expected `n` (5,528; 2,533; 2,457; 4,813), and `sum(counts) == n`.
- [ ] **Step 2: Implement the export,** then a card with one small histogram per measure and a marker at this journal, with its percentile. Rows without a value are left out (Review Focus 4).
- [ ] **Step 3: Verify** Int J Surg's outside-journal value is 33% and Cell's top-paper share 4.7%.
- [ ] **Step 4: Commit** with `feat: journal page shows how a journal compares with others`.

### Task 8: Who cites this journal

**Files:** Modify `scripts/export_site_extras.py`, `tests/test_export_site_extras.py`, `docs/js/data-loader.js`, `docs/js/app.js`, `docs/index.html`

**Interfaces:** Produces `citers/{slug}.json`: `{"year": 2024, "citations": n, "countries": {name: share}, "authors": {name: share}, "journals": [{"slug", "name", "citations"}]}`, from `country_matrix.npz` and `citing_screen_2024.npz`, top 10 citing journals.

- [ ] **Step 1: Write failing tests:** Circulation's USA citing share is 30.6%, as in F10; Int J Surg's top outside journal is Int J Surg Case Rep with 1,514 citations; shares sum to 1 within rounding.
- [ ] **Step 2: Implement the export,** then a card with a stacked bar of citing regions, authors' regions beside it, and the top 10 citing journals. Add a second journal through the existing picker, to make F10 A's pair view.
- [ ] **Step 3: Verify** on Circulation and Eur Heart J together. Expected: values match F10 A.
- [ ] **Step 4: Commit** with `feat: journal page shows who cites a journal`.

### Task 9: Recurring series

**Files:** Modify `scripts/export_site_extras.py`, `tests/test_export_site_extras.py`, `docs/js/data-loader.js`, `docs/js/app.js`, `docs/index.html`

**Interfaces:** Produces `series/{slug}.json`: `{"series": [{"title", "pmids": [...], "citations": n}]}`, from `series_v2.npz`, only for journals with a series. Adds `SiteMetrics.rateWithout(timeseries, papers, pmids, citable) -> [{month, rate}]`.

- [ ] **Step 1: Write failing tests:** 3,515 series across all files, covering 24,478 papers. In JS, removing nothing returns the original rate.
- [ ] **Step 2: Implement the export,** then a "Without recurring series" checkbox on the journal chart, with a list of the series removed. When some series papers fall outside the top 2,000, a note gives how many were left in.
- [ ] **Step 3: Verify** CA Cancer J Clin and Circulation against `f5d_rates.csv`. Expected: within 1% at Nov 2025.
- [ ] **Step 4: Commit** with `feat: journal chart can leave out recurring series`.

### Task 10: Landscape tab

**Files:**
- Create: `docs/js/landscape-tab.js`
- Modify: `scripts/export_site_extras.py` (`export_landscape(out_dir: str) -> dict`), `tests/test_export_site_extras.py`, `docs/js/data-loader.js`, `docs/js/app.js` (`setupNavigation`), `docs/index.html`, `docs/css/style.css`

**Interfaces:** Produces `landscape.json`, about 1 MB, keyed by figure, from the CSVs in `10-31-26/v2/data/` and `10-31-26/data/`. Each entry holds its rows and its legend text from `figure_legends.json`.

- [ ] **Step 1: Write failing tests:** each key in the Task table's "Landscape" rows is present, and each entry's rows match its source CSV.
- [ ] **Step 2: Build the tab** with four groups: Publication timing (F1, F2), Reliance (F4, F5), Publishing (F7, F9, F11), Retractions (F12). Charts are live Chart.js versions, with legends below and "Data as of Nov 2026".
- [ ] **Step 3: Add a journal picker** that marks a chosen journal on any journal-level chart, reusing `journal_measures.json`.
- [ ] **Step 4: Verify** each chart against its paper figure. Expected: same values, no console errors at phone width.
- [ ] **Step 5: Commit** with `feat: Landscape tab with the paper's site-wide figures`.

### Task 11: Documentation and release

**Files:** Modify `docs/index.html` (Methodology), `CLAUDE.md`, `scripts/upload_to_r2.py` only if the new folders need listing

- [ ] **Step 1: Add Methodology text** on retraction sources, the snapshot date and the citing data. Credit Retraction Watch as its terms require, after confirming them.
- [ ] **Step 2: Bump version strings,** and run the full test suite. Expected: all pass.
- [ ] **Step 3: Ask the owner** before uploading to R2, then before pushing. After uploading, check one new file of each kind on the live site.
