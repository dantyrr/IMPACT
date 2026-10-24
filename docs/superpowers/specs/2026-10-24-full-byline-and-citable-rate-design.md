# Full bylines and a citable-items rolling rate

Date: 2026-10-24
Status: draft for review
Covers projects 1 and 2 of 4. Projects 3 (geography and collaboration views) and
4 (journal fit for a paper) are designed separately, after this lands.

## Why

Two problems surfaced while building the article-type-by-year chart and the
signed influence metric, and they share one fix.

**The headline metric is not computed the way the site says it is.**
`impact_calculator.py:191` computes

    rolling_if = total_citations / n_research

so citations to reviews, editorials and letters are counted in the numerator,
while only research articles are counted in the denominator. The About section
says this "mirrors the official JIF methodology", and it does not: the JIF
denominator counts citable items, reviews included. The methodology file that
described the formula (`METHODOLOGY.md`) was deleted in `60e5b69`, contradicted
itself (line 36 says research only; the table at line 122 says reviews are in
the denominator), and is still cited by `CLAUDE.md`.

The owner's decision: the rolling rate should be the JIF method made rolling,
with research articles, reviews, case reports and guidelines as the citable
items in **both** the numerator and the denominator. Letters that report
original research, such as JAMA Research Letters, count as research.
Editorials, correspondence, highlights, news, errata, retraction notices and
similar items are out of both. This is deliberately
cleaner than Clarivate, whose numerator also counts citations to non-citable
items. Measured on the 2024-12 window, the two choices differ by about 1-8%
for named journals (Nature 26.05 vs 27.46, JACC 19.01 vs 21.34).

**Some journals' "research" is not research.** PubMed types Nature Reviews
"Research Highlights" and similar short pieces only as `Journal Article`, so
IMPACT counts them as research. Under the current formula they quietly form
the whole denominator of journals like Nature Reviews Molecular Cell Biology.
Under the new formula they would sit in the citable denominator and drag that
journal from about 77 to 35. A detector over 5,645 journals with enough of
both types found 64 affected (17 Nature Reviews, 10 Trends, 37 others). The
stored data cannot tell these pieces apart from research: there is no abstract
flag and no page count, and `pub_type` is collapsed to one value at ingestion
(`download_pubmed_bulk.py:222`).

The PubMed baseline XML has what is missing: the full publication-type list,
the abstract, the pagination, and every author with every affiliation. IMPACT
never kept those XML files. `download_pubmed_bulk.py` streams each file
through memory and keeps only the first and last author. One new pass over
the baseline and update files fixes the classification gap, and it also
captures the full bylines that project 3 needs, the same data IMPACT-NCATS
fetched through EFetch for 148,575 papers. Because both feed the same
recompute, they ship together and the 8,631-journal recompute runs once.

## Goals

1. One streaming pass over all 1,334 baseline and 360 update files that
   records, for every paper, the full publication-type list, whether it has
   an abstract, its pagination, every author in byline order with ORCID, and
   every affiliation string. Any ROR identifier PubMed supplies is recorded
   alongside the string.
2. A parsed country for every affiliation. The existing first and last author
   institution, city, state and country fields stay populated from the new
   data.
3. A derived document class for every paper that reclassifies short pieces
   without an abstract, such as highlights, out of research. The PubMed types
   are kept unchanged next to it, so every reclassification can be audited.
4. `rolling_if` = citations to citable items in the 12-month window, divided
   by citable items in the paper window. Citable items are research articles
   (including research letters), reviews, case reports and guidelines.
5. Per-journal flags for conditions that make the numbers less trustworthy,
   shown as caveats. No journal is excluded or hidden.
6. A methodology page on the live site, plus a restored `METHODOLOGY.md` in
   the repo, that match the code exactly.
7. The weekly update keeps every new field current from the first run after
   the rebuild.
8. The `official_jif` fields and the "mirrors the official JIF" claim are
   removed.

## Non-goals

- Matching affiliations to institutions (ROR), maps, and collaboration
  networks. Those are project 3. Raw affiliation strings are stored here so
  project 3 never needs another baseline pass.
- Author disambiguation and the "my own reach" view. These are project 3. The
  ORCIDs captured here are an input.
- The journal-fit feature, project 4.
- Any comparison with Clarivate JIF values.
- Moving the build off the laptop. That is deferred work, recorded in memory.

## Anti-goals (a failure even if everything technically works)

- Real research reclassified as commentary. JAMA Research Letters, for
  example, are short, have no abstract, and are genuine research.
  Misclassifying them would be worse than the bug being fixed.
- The headline numbers change on the live site without the methodology page
  going live at the same moment. Visitors would read a 93%-of-journals drop
  as breakage.
- Running out of disk on the laptop, or leaving tens of gigabytes of
  temporary files behind.
- A weekly run during the rebuild writing to the database at the same time.
- Two parsers for PubMed records. The lowercase `pub_type` bug fixed on
  2026-10-22 came from the weekly path parsing ESummary differently from the
  bulk path. The rebuild must leave one parser for the baseline, the update
  files and the weekly EFetch path.

## Constraints

- **Disk.** 141 GB free after the WAL checkpoint on 2026-10-24.
  `impact.db` is 65 GB, `pubmed_bulk.db` 15 GB, `icite_bulk.db` 8.9 GB.
  Extrapolating IMPACT-NCATS's per-year densities to IMPACT's 24.9 million
  papers from 2003-2026 gives about 233 million author rows, 207 million
  affiliation rows and 27 GB of raw affiliation text. Stored as NCATS stores
  it (one text row each) that is about 40 GB. Affiliation strings must
  therefore be deduplicated into a lookup table. Only 40% of NCATS's
  affiliation strings are distinct, and the share will be lower at IMPACT's
  scale. Target: 15-20 GB for the new author and affiliation tables. That
  cap covers only those tables. Peak additional use, worst case, is
  roughly: the replacement `pubmed` table (about 16 GB), the new tables
  (20 GB or less), the old `pubmed_bulk.db` (15 GB, kept until step 9), and
  `impact.db` write-ahead-log growth while 25M rows gain `doc_class` and
  author fields (the last full recompute grew it to 17 GB). That is about
  70 GB against 141 GB free. Every long step must stop cleanly if free space
  falls below 30 GB, and checkpoint the WAL between steps.
- **Rate limits.** The baseline and update files are bulk HTTPS downloads,
  outside the E-utilities 10 requests/second budget. EFetch is used only by
  the weekly update, for about 30,000 new papers a week (about 150 requests).
- **Concurrency.** The rebuild must take `data/.weekly_update.lock`, the lock
  the launchd job checks (`weekly_auto_update.sh:22`), for its whole run.
  The next scheduled run is Monday 2026-10-26. The wrapper treats the lock as
  stale and removes it once the pid stored inside it has exited
  (`weekly_auto_update.sh:124`). The rebuild runs as several processes with
  pauses for owner review, so one long-lived process must hold the lock for
  the whole rebuild, and its pid must be the one written into the lock.
- **Existing columns.** `papers` holds gender columns written by the
  IMPACT-gender work (`first_author_gender`, `last_author_gender`,
  `gender_pair` and others). The rebuild must not drop or overwrite them.
- **No build step on the frontend.** Vanilla JS. Bump the `?v=N` query on
  every changed asset in `docs/index.html`.
- **Owner preferences.** No time predictions for pipeline runs; report
  progress as fractions. Conventional commit prefixes. Commit messages follow
  the session's attribution rule.

## What was decided, and by whom

Decided by the owner:

- Citable items are research articles, reviews, case reports and guidelines,
  in both numerator and denominator (the symmetric version, not Clarivate's
  asymmetric one). Case reports and guidelines are included because they are
  cited regularly, large clinical guidelines especially.
- Letters that report original research (JAMA Research Letters and similar)
  are research and therefore citable.
- Editorials, highlights, retraction notices and "weird stuff" are not
  citable.
- Retire `pubmed_bulk.db` once nothing needs it.
- No minimum-volume exclusions. Flag instead.
- No Clarivate JIF comparison.
- Full bylines and affiliations captured now, at full detail, so later views
  need no second pass.
- The order: data rebuild and metric fix first, then views, then journal fit.

My calls, marked so the owner can check them:

- **Storage shape.** New tables live in a new database file
  (`data/pubmed_full.db`), not in `impact.db`. This keeps `impact.db` from
  growing and keeps the new data movable as a unit if the build moves to a
  server. The pipeline reads it with `ATTACH`.
- **How `pubmed_bulk.db` is retired** (retiring it is the owner's decision).
  The new file carries every column of the current `pubmed` table, so
  `config.py`, `build_journal_registry.py`, `fix_citation_months.py` and
  `run_pipeline_bulk.py` can switch paths. The old 15 GB file is deleted only
  after those consumers are switched and verified.
- **The derived class sits beside PubMed's types and does not replace them.**
  `pub_type` keeps PubMed's canonical value. A new `doc_class` column on
  `papers` holds the category used for metrics, and `class_source` records
  whether the class came from PubMed directly or was inferred.
- **Country now, institutions later.** Country is parsed during ingestion
  because the current Geography exports already use it. ROR matching waits
  for project 3 and runs over the distinct strings without a re-download.
- **Field names in the JSON are additive.** New fields
  (`citable_papers`, `citable_citations`) are added. Existing fields keep
  their names; `rolling_if` changes meaning.
- **Byline scope.** Full authors and affiliations are captured for papers in
  the 8,631 tracked journals published 2003-2026 (24.9M papers, the basis of
  the size estimate). The replacement `pubmed` table still covers every
  record, because it is the source of citing-paper dates. Projects 3 and 4
  only look at authors of tracked-journal papers.
- **iCite no longer sets `is_research`.** Today both the bulk and weekly paths
  overwrite `is_research` with iCite's `is_research_article`
  (`run_pipeline_bulk.py:213-218`, `run_weekly_update.py:592-599`), so the
  current denominator is iCite's research count, and "reviews" in
  `compute_rolling_if` means "everything iCite calls non-research". From here,
  every metric uses one definition, `doc_class`. iCite's flag becomes one
  piece of evidence for the inference rule (section 4). This also changes
  `rolling_if_no_reviews` and `research_count` for every journal. The
  2024-12 estimates in this document were computed from `by_type`, which
  already groups by PubMed type, so they match the new definition.
- **Every country in an affiliation is kept.** Older records often list
  several institutions in one string joined by semicolons. A child table
  stores every country found; the string's single `country` column holds the
  last one, matching the NCATS parser, for compatibility.
- **One country parser.** The first and last author country fields are
  repopulated with the same parser as the new tables, with names mapped to
  the ones the Geography choropleth already uses. Geography values may
  therefore shift slightly in this release, and the methodology page says so.
  Running two country parsers side by side would recreate the two-parser
  problem the anti-goals rule out.
- **Go-live is atomic.** The new data is uploaded under a new versioned R2
  prefix while the live site keeps reading the old one. A single frontend
  deploy then switches `R2_BASE_URL`, the formula code and the methodology
  page together. The old prefix stays for rollback and is deleted after the
  owner confirms the new site. This rules out the mismatch window that an
  in-place upload of 8,631 files would create.
- **How research letters are recovered** (that they count is the owner's
  decision). JAMA's 672 `Letter` items from
  2022-2024 mix correspondence ("…-Reply") with Research Letters. The
  validation gate (section 4) tries to recover Research Letters as
  `research`. If they cannot be separated reliably, they stay `letter`, and
  the methodology page states this as a known undercount.

## Design

### 1. Ingestion: one parser, three entry points

Factor the per-article extraction out of `download_pubmed_bulk.py` into one
module (for example `src/pipeline/pubmed_xml.py`). It takes a `PubmedArticle`
element and returns one record with:

- every current `pubmed` column, unchanged in meaning
- `pub_types`: the full PublicationTypeList, in order
- `has_abstract`: true if `Abstract/AbstractText` has any non-empty text
- `pagination`: `MedlinePgn` as written, plus a derived page count where it
  parses as a range. Unknown stays null, because e-locator journals such as
  PLoS ONE have no page range.
- `authors`: byline order, last, fore and initials, collective name, ORCID
  (normalized to `0000-0000-0000-000X`), and for each affiliation the string
  plus any `Identifier Source="ROR"`

Author handling follows IMPACT-NCATS `fetch_authors.py`: drop entries with
`ValidYN="N"`, exclude `InvestigatorList`, and store a group author as one row
with a collective name. NCATS's parser and its test fixture
(`tests/fixtures/pubmed_authors.xml`) are the reference implementation.
Reuse them; do not redesign them.

The three entry points that use the parser:

1. Baseline files, streamed through memory as today.
2. Update files, applied in order after the baseline. A newer version of a
   record replaces the older one. `DeleteCitation` entries delete. The
   current code handles neither. `download_pubmed_bulk.py` never reads
   `DeleteCitation`. Its `--updates` path is also broken: the update-file URL
   is computed at line 354 and never used, so every download goes to
   `BASE_URL`. Both need fixing, not reuse.
3. The weekly update, which switches its metadata fetch from ESummary to
   EFetch XML (`run_weekly_update.py:162` and `:542`) and inserts through the
   same parser. ESummary returns no affiliations, so without this switch every
   paper after the rebuild would have first and last author only.

The pass is resumable per file, as `processed_files` already allows, and
reports progress as files done out of total.

### 2. Storage (`data/pubmed_full.db`)

Sketch only. The builder settles the exact columns and indexes and measures
size on a sample before the full run.

- `pubmed`: the current columns plus `pub_types`, `has_abstract`,
  `pagination`, `page_count`
- `authors (pmid, position, last_name, fore_name, initials, collective_name, orcid)`
- `affil_strings (affil_id, text, country, ror_id)`, with text unique;
  `country` is the last country found, for compatibility
- `affil_countries (affil_id, part_order, country)`: every country found in
  the string
- `author_affils (pmid, position, affil_order, affil_id)`
- `processed_files` as today

Before the full run, ingest a sample of baseline files spread across years,
measure bytes per paper, and project the total. If the projection exceeds
20 GB, stop and report rather than run.

### 3. Country parsing

Port the country step of IMPACT-NCATS `build_nonhub_collaboration.py`. Run it
once per distinct string, not once per row. Fold US states into USA, matching
the frontend's `_normalizeCountry()`. Record a match rate per year, because
PubMed recorded only the first author's affiliation before about 2014 and
older years will be thin for middle authors.

Repopulate the existing `first_author_*` and `last_author_*` institution,
city, state and country fields from positions 1 and N, so current exports
keep working unchanged.

### 4. Document class

`doc_class` takes one of: `research`, `review`, `commentary`, `editorial`,
`letter`, `case_report`, `guideline`, `erratum`, `other`. Citable means
`research`, `review`, `case_report` or `guideline`.

Rules, in order:

1. Fix the priority bug in `canonical_pub_type`: `_REVIEW_TYPES` is checked
   before `_GUIDELINE_TYPES`, so anything typed both Review and Practice
   Guideline becomes a review. Only 10 papers from 2022-2024 landed as
   guidelines. Decide the priority deliberately and document it.
2. Map PubMed's canonical type to a class with the existing case-insensitive
   map.
3. Inference: a paper whose class is `research` becomes `commentary`, with
   `class_source='inferred'`, when it has no abstract and the other signals
   agree. The rule is not settled here; it is set by the validation gate
   below. Page count is supporting evidence only, because it is often
   missing. iCite's `is_research_article` is also evidence: in the
   affected Nature Reviews and Trends titles it disputes 31-85% of the
   `Journal Article` items, against 2-6% in Nature, Circulation and ATVB. It
   is not decisive on its own; it disputes only 1.6% in Nature Reviews
   Disease Primers.
4. Recovery: a `Letter` that reports original research (for example a JAMA
   Research Letter) becomes `research`, with `class_source='inferred'`, if
   the validation gate finds a signal that separates it reliably from
   correspondence.

**The detector.** This is the analysis that found the affected journals, run
over the exported journal JSON on 2026-10-23. For each journal it averages,
over the 24 monthly windows 2023-01 to 2024-12, the per-window review rate
and research rate from `by_type`. Windows count only when they hold at least
20 research and 5 review papers, and a journal needs at least 12 qualifying
windows. Over 2021-2024 papers it computes the review share (reviews over
reviews plus `Journal Article`) and the share of `Journal Article` items iCite
calls non-research. A journal is flagged when

    review rate / research rate >= 4
    AND (review share >= 30%  OR  iCite non-research share >= 25%)

That flags 64 of 5,645 journals. The list, with each measure, is in
`2026-10-24-detector-flagged-journals.csv` next to this document. It is
analysis, not production logic. If the fallback below makes it production
logic, it is reimplemented over `doc_class` data in the pipeline, it runs on
every recompute including the weekly one, and its rule and thresholds go on
the methodology page.

**Validation gate.** Before the inference rule is applied anywhere:

- Measure, per journal, the share of research items it would reclassify, for
  at least: the 64 detector-flagged journals, Nature, Science, Cell, NEJM,
  The Lancet, JAMA, Circulation, JACC, ATVB, PLoS ONE and Nature
  Communications.
- Read at least 30 reclassified titles each from JAMA, NEJM, The Lancet,
  Nature and two Nature Reviews titles.
- Check the type mapping as well as the inference rule. Sample at least 30
  `Letter` items each from JAMA, NEJM and The Lancet, and report how many
  report original research.
- Pass: JAMA Research Letters and comparable short research formats end up
  `research` (or, if they cannot be recovered, the undercount is measured
  and reported), and Nature Reviews highlights become `commentary`.
- If one global rule cannot pass, the fallback is to apply inference only to
  journals whose detector flag fires. Report which outcome happened.

`is_research` is kept for backward compatibility and set to
`doc_class = 'research'`.

### 5. Metric

In `compute_rolling_if`:

    citable    = papers in window with doc_class in
                 (research, review, case_report, guideline)
    rolling_if = citations to citable / count(citable)

The 2024-12 estimates earlier in this document counted research and reviews
only. Case reports are 0.13% of items and guidelines are almost empty, so
the estimates should still hold to within rounding.

`rolling_if_no_reviews` stays research citations over research count.

`count_papers_and_citations_by_type` groups by `doc_class`, so `by_type`
gains a `commentary` bucket and the per-type rates come from the same
classes as the headline. Add `citable_papers` and `citable_citations` to each
timeseries point. Keep `citations`, `research` and `reviews` for
compatibility.

### 6. Frontend changes that must ship with the data

- `_computeAdjIf` (`docs/js/app.js:1804`) recomputes the counterfactual rate
  on the client from `point.citations / point.research`, which is the old
  formula. It must use `citable_citations / citable_papers`. A seed paper
  should come out of the numerator and the denominator only if it is
  citable (research, review, case report or guideline). Today the code subtracts every seed's
  citations from the numerator regardless of type, and decides denominator
  membership from iCite's `is_research_article`, which is false for reviews.
- The seed's class must be available for **any** PMID, since looking up any
  paper was an explicit owner requirement. The client can currently see a
  type only in `papers/{slug}.json`, which holds each journal's top 2,000
  papers. How the class reaches the client for every other paper is left to
  the builder (one option is to fetch it live, as the iCite fallback does
  today). Falling back to iCite's flag would misclassify reviews, so it is
  not an acceptable fallback.
- The journal metric cards near lines 610-745 add up `research`, `review`,
  `editorial`, `letter` and `other`. Add `commentary`.
- The article-type-by-year chart and table show `commentary` as its own type.
- Flags (below) appear as short caveat lines on the journal page.
- Deploy order: see "Go-live is atomic" above. The new frontend reads the new
  versioned R2 prefix only, so it never meets old-shape data and needs no
  fallback path.

### 7. Flags

Exported per journal, computed over the latest settled 24-month window.
Starting thresholds; tune them on the real distribution and document the
final values:

- `small_research_sample`: fewer than 20 research items in the window
- `small_review_sample`: fewer than 15 reviews, so review rates are noisy
- `review_journal`: reviews are at least 50% of citable items
- `inferred_types`: at least 10% of the window's items were reclassified by
  inference

### 8. Methodology

Restore `METHODOLOGY.md` from `60e5b69^`, rewritten to match the code: the
formula, the citable classes, the inference rule and its validation result,
the windows, the flags, and the difference from Clarivate (numerator
symmetry). Add a Methodology section to the site, linked from About. Remove
the "mirrors the official JIF methodology" claim. Point `CLAUDE.md` at the
restored file.

### 9. Removing the JIF field

Remove `official_jif_2024` from `json_exporter.py:72` and `official_jif` from
`compute_snapshots.py` (`:35`, `:78`, `:100`), `backfill_snapshots.py:138` and
`rebuild_index_from_journals.py:45`. It is null for all 8,631 journals, and
the frontend does not read it.

## Sequence

1. Pause the weekly job by taking `data/.weekly_update.lock`.
2. Sample ingest; report bytes per paper and projected size. Stop if over
   20 GB.
3. Full baseline and update-file pass into `pubmed_full.db`.
4. Country parsing; repopulate the first and last author fields; report
   match rates by year.
5. Document class: priority fix, mapping, inference, and the validation
   gate. Report the gate's outcome to the owner before continuing.
6. Metric and export changes; switch the weekly update to EFetch.
7. Full recompute of all 8,631 journals; `validate_exports.py`; spot-check
   named journals against the 2024-12 estimates in this document.
8. Upload to a new versioned R2 prefix (owner authorizes). Then, in one
   deploy, switch `R2_BASE_URL`, ship the frontend changes and the
   methodology page (owner authorizes the push to `main`).
9. Release the lock. Point `pubmed_bulk.db` consumers at the new file,
   verify them, then delete the old file.

## Left to the builder

- Exact table columns, indexes and `PRAGMA` settings, within the 20 GB budget
- How deletions and versions in the update files are applied
- The exact inference rule, within the validation gate
- The final flag thresholds
- Tests. The project has no test suite (`tests/` holds only `__pycache__`).
  At minimum: parser tests against the NCATS fixture plus a fixture
  containing a highlight, a JAMA research letter and a group author; and a
  formula test on a hand-built window.

## Open questions for the owner

None. Case reports and guidelines were settled on 2026-10-24: both are
citable.
