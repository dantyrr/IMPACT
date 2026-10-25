# Full Bylines and Citable-Items Rolling Rate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-ingest the PubMed baseline with full bylines, affiliations and document-type signals; reclassify short non-research pieces; recompute every journal's rolling rate as citations to citable items over citable items; and switch the live site over atomically with a methodology page.

**Architecture:** One PubMed XML parser (`src/pipeline/pubmed_xml.py`) feeds the baseline and update-file ingest and the weekly EFetch path, writing to a new `data/pubmed_full.db`. A classifier (`src/pipeline/doc_class.py`) assigns `doc_class` to `impact.db.papers`, and the calculator, exporter, flags and frontend all read that one field. Data goes to a versioned R2 prefix (`v2/`), and the frontend switches to it in the same deploy as the methodology page.

**Tech Stack:** Python 3.11, SQLite (WAL), `xml.etree.ElementTree.iterparse`, `requests`, pytest 9; vanilla JS and Chart.js 4.4.0 in `docs/`; Cloudflare R2 through the existing `upload_to_r2.py`.

**Spec:** `docs/superpowers/specs/2026-10-24-full-byline-and-citable-rate-design.md` (approved 2026-10-24). Detector list: `docs/superpowers/specs/2026-10-24-detector-flagged-journals.csv`.

## Global Constraints

- Citable `doc_class` values: `research`, `review`, `case_report`, `guideline`. Non-citable: `commentary`, `editorial`, `letter`, `erratum`, `other`.
- `rolling_if = citations to citable / count(citable)`, symmetric. `rolling_if_no_reviews = research citations / research count`.
- iCite's `is_research_article` never sets `is_research` or `doc_class` directly. It is evidence for inference only. `is_research = 1 iff doc_class = 'research'`.
- PubMed's `pub_type` column is never overwritten with a derived class. Derived classes go in `doc_class`, and `class_source` is `'pubmed'` or `'inferred'`.
- Full bylines only for papers whose ISSN is a tracked journal's ISSN (including `ISSN_BULK_MAP` aliases) and whose `pub_year` is 2003–2026. The `pubmed` table in `pubmed_full.db` covers every record.
- The new author and affiliation tables must not exceed **20 GB**. Every long-running step stops cleanly, with work committed, if free disk falls below **30 GB**, and checkpoints the WAL between steps.
- The rebuild holds `data/.weekly_update.lock` for its whole duration, through one long-lived process whose pid is in `data/.weekly_update.lock/pid`.
- `papers` gender columns (`first_author_gender`, `first_author_gender_prob`, `last_author_gender`, `last_author_gender_prob`, `gender_pair`, `first_author_forename`, `last_author_forename`) are never dropped or overwritten.
- Flag thresholds (starting values, tuned in Task 9): `small_research_sample` < 20 research; `small_review_sample` < 15 reviews; `review_journal` reviews ≥ 50% of citable; `inferred_types` ≥ 10% of the window's items have `class_source='inferred'`.
- No time predictions for pipeline runs; report progress as fractions done.
- Commits: conventional prefixes (`feat:`, `fix:`, `docs:`, `remove:`, `data:`). **No `Co-Authored-By` line**, per the owner's standing preference.
- Frontend: no build step; bump `?v=N` on every changed asset in `docs/index.html`; Okabe-Ito colors only.
- R2 uploads and pushes to `main` each need the owner's explicit go-ahead at the time.

## Review Focus

1. **A record re-versioned in an update file with fewer authors** must leave no stale author or affiliation rows → Task 3 test `test_reversioned_record_replaces_byline`.
2. **An affiliation string naming several countries** ("…, Boston, MA, USA; …, Oxford, UK") must store every country, and keep the last as the compatible `country` → Task 3 test `test_multi_country_affiliation`.
3. **E-locator pagination** ("e0123456", PLoS ONE) must give `page_count = None`, never 0 or 1, or the short-piece rule would fire on every PLoS ONE paper → Task 1 test `test_elocator_pagination_has_no_page_count`.
4. **An ingest killed mid-file** must reprocess that file on resume without duplicate rows → Task 5 test `test_file_marked_only_after_commit`.
5. **A journal window with zero citable items** (a pure-commentary month) must produce `rolling_if = 0.0` with no division error → Task 8 test `test_zero_citable_window`.

---

### Task 1: Shared PubMed XML parser

**Files:**
- Create: `src/pipeline/pubmed_xml.py`
- Create: `tests/__init__.py` (empty), `tests/fixtures/pubmed_records.xml`
- Copy: `tests/fixtures/pubmed_authors.xml` from `/Users/dtyrrell/Projects/IMPACT-NCATS/tests/fixtures/pubmed_authors.xml`
- Test: `tests/test_pubmed_xml.py`

**Interfaces:**
- Produces:
  - `iter_pubmed_xml(fileobj) -> Iterator[tuple[str, object]]`, which yields `("record", dict)` per `PubmedArticle` and `("delete", int)` per PMID inside `DeleteCitation`. Streams with `iterparse` and clears elements.
  - `parse_article(elem) -> dict | None`. The record dict keys are: `pmid:int`, `issn:str|None` (ISSNLinking, as today), `issns:list[str]` (every `Journal/ISSN` value, used by the weekly ISSN fallback), `pub_year:int|None`, `pub_month:int`, `title:str`, `doi:str|None`, `pub_types:list[str]`, `pub_type:str` (= `canonical_pub_type(pub_types)`), `has_abstract:bool`, `pagination:str|None`, `page_count:int|None`, `first_author`, `first_affil`, `last_author`, `last_affil`, and `authors:list[dict]`. Each author dict has `position`, `last_name`, `fore_name`, `initials`, `collective_name`, `orcid`, and `affiliations:list[{"text":str,"ror_id":str|None}]`.
  - `normalize_orcid(raw:str|None) -> str|None` and `parse_page_count(medline_pgn:str|None) -> int|None`.

The fixture `pubmed_records.xml` holds seven `PubmedArticle`s plus one `DeleteCitation`:

| PMID | Types | Abstract | `MedlinePgn` | Purpose |
|---|---|---|---|---|
| 1001 | Journal Article | yes | `123-130` | research |
| 1002 | Journal Article | no | `5` | Nature Reviews-style highlight |
| 1003 | Letter | no | `1801-1802` | JAMA-style research letter |
| 1004 | Review, Practice Guideline | yes | `e1-e40` | |
| 1005 | Journal Article | yes | `e0123456` | |
| 1006 | Journal Article | yes | | group author plus a `ValidYN="N"` author; an `AffiliationInfo` with `<Identifier Source="ROR">https://ror.org/03vek6s52</Identifier>` |
| 1007 | Journal Article | yes | `1-10` | `AffiliationInfo` text "Dept X, Boston, MA, USA; Dept Y, Oxford, UK" |

`<DeleteCitation><PMID Version="1">999</PMID></DeleteCitation>`

- [ ] **Step 1: Write failing tests**

```python
def test_record_fields(records):        # records: {pmid: dict} from the fixture
    r = records[1001]
    assert r["pub_types"] == ["Journal Article"] and r["has_abstract"] is True
    assert r["page_count"] == 8 and r["pub_type"] == "Journal Article"

def test_highlight_signals(records):
    assert records[1002]["has_abstract"] is False and records[1002]["page_count"] == 1

def test_full_type_list_kept(records):
    assert records[1004]["pub_types"] == ["Review", "Practice Guideline"]

def test_elocator_pagination_has_no_page_count(records):
    assert records[1005]["pagination"] == "e0123456"
    assert records[1005]["page_count"] is None

def test_group_author_and_invalid_name(records):
    a = records[1006]["authors"]
    assert [x["position"] for x in a] == list(range(1, len(a) + 1))
    assert any(x["collective_name"] for x in a)
    assert any(f["ror_id"] == "03vek6s52" for x in a for f in x["affiliations"])

def test_delete_citation_yields_delete(events):
    assert ("delete", 999) in events

def test_ncats_fixture_parity():
    # Every author NCATS's parser reads from pubmed_authors.xml, this parser reads identically
    # (position, names, orcid, affiliation text).
    ...
```

`test_ncats_fixture_parity` gets its expected values by importing `parse_authors` from the NCATS repo path, or by hardcoding the values read once.

- [ ] **Step 2: Run, expect FAIL**: `python -m pytest tests/test_pubmed_xml.py -v` fails with `ModuleNotFoundError: src.pipeline.pubmed_xml`.

- [ ] **Step 3: Implement** `src/pipeline/pubmed_xml.py`. Move `_parse_month`, `_get_date` and the title, DOI and ISSN logic out of `scripts/download_pubmed_bulk.py` unchanged. Port the author rules from NCATS `scripts/fetch_authors.py` (`_parse_author`, `normalize_orcid`, skip `ValidYN="N"`, `InvestigatorList` not read). Read `has_abstract` from any non-empty `Abstract/AbstractText`. `parse_page_count` parses `start-end` with numeric ends, expanding an abbreviated end ("1801-2" → 2). A single number gives 1. Anything starting with a letter gives None. Normalize ROR from URL to bare id.

- [ ] **Step 4: Run, expect PASS**: `python -m pytest tests/test_pubmed_xml.py -v`.

- [ ] **Step 5: Commit**: `git commit -m "feat: one PubMed XML parser with full bylines and type signals"`

### Task 2: Affiliation location and institution parser

**Files:**
- Create: `src/pipeline/affil_location.py`, `src/pipeline/affil_institution.py`, by porting NCATS `src/ncats/affil_location.py` (self-contained) and `src/ncats/affil_institution.py`. Port the two helpers it imports from `src/ncats/hub_matching.py` (`normalize`, `institution_segments`) into `affil_institution.py`. Port no other hub code.
- Test: `tests/test_affil_location.py`, `tests/test_affil_institution.py`, ported from NCATS with imports changed to `src.pipeline`.

**Interfaces:**
- Produces: `parse_locations(text) -> list[Location]`, `parse_location(text) -> Location` (with fields `country, state, zip, how, city`), `NOWHERE`, and `describe(affiliation) -> InstitutionDescription` (with at least `name` and `type`).

- [ ] **Step 1:** Copy the NCATS tests, change the imports, and run them: `python -m pytest tests/test_affil_location.py tests/test_affil_institution.py -v`. Expect FAIL (module missing).
- [ ] **Step 2:** Port the modules. Add a header comment naming the NCATS source commit (`git -C ../IMPACT-NCATS log -1 --format=%h -- src/ncats/affil_location.py`).
- [ ] **Step 3:** Run again and expect PASS. Then add one test: `parse_locations("Dept X, Boston, MA, USA; Dept Y, Oxford, UK")` returns countries `["USA", "United Kingdom"]` in that order.
- [ ] **Step 4: Commit**: `git commit -m "feat: port NCATS affiliation location and institution parsers"`

### Task 3: `pubmed_full.db` schema and writer

**Files:**
- Create: `src/pipeline/pubmed_full_db.py`
- Modify: `src/pipeline/config.py:244` to add `PUBMED_FULL_DB_PATH = os.path.join(_REPO_ROOT, "data", "pubmed_full.db")`
- Test: `tests/test_pubmed_full_db.py`

**Interfaces:**
- Consumes: Task 1 record dict; Task 2 `parse_locations`, `describe`.
- Produces:
  - `open_full_db(path:str) -> sqlite3.Connection` (WAL; creates the tables below)
  - `make_byline_scope(tracked_issns:set[str], first_year:int=2003, last_year:int=2026) -> Callable[[dict], bool]`
  - `store_records(conn, records:list[dict], in_scope:Callable[[dict],bool]) -> None`
  - `delete_pmids(conn, pmids:list[int]) -> None`
  - `tracked_issns_from_impact(impact_db_path:str) -> set[str]`, which returns `journals.issn` plus `ISSN_BULK_MAP` keys and values.

Tables:
- `pubmed`: the current `pubmed_bulk.db` columns, plus `pub_types TEXT` (JSON array), `has_abstract INTEGER`, `pagination TEXT`, `page_count INTEGER`
- `authors(pmid, position, last_name, fore_name, initials, collective_name, orcid, PRIMARY KEY(pmid, position))`
- `affil_strings(affil_id INTEGER PRIMARY KEY, text TEXT UNIQUE, ror_id, country, state, city, institution, institution_type)`
- `affil_countries(affil_id, part_order, country, PRIMARY KEY(affil_id, part_order))`
- `author_affils(pmid, position, affil_order, affil_id, PRIMARY KEY(pmid, position, affil_order))`
- `processed_files(filename PRIMARY KEY, kind, processed_at, record_count)`

Each affiliation string is parsed once, on first insert. `country`, `state` and `city` come from `parse_location` (the last place in the string). `affil_countries` gets one row per `parse_locations` entry. `institution` and `institution_type` come from `describe`.

- [ ] **Step 1: Write failing tests**

```python
def test_affiliation_deduplicated(conn):        # same text on two authors, two papers
    assert count(conn, "affil_strings") == 1 and count(conn, "author_affils") == 2

def test_out_of_scope_record_has_no_byline(conn):  # issn not tracked
    assert count(conn, "pubmed") == 1 and count(conn, "authors") == 0

def test_reversioned_record_replaces_byline(conn):  # store 5 authors, then the same pmid with 3
    assert positions(conn, pmid) == [1, 2, 3]
    assert max_affil_position(conn, pmid) <= 3

def test_multi_country_affiliation(conn):
    assert countries(conn, "Dept X, Boston, MA, USA; Dept Y, Oxford, UK") == ["USA", "United Kingdom"]
    assert compat_country(conn, same_text) == "United Kingdom"

def test_delete_removes_everything(conn):
    delete_pmids(conn, [pmid])
    assert all(count_for(conn, t, pmid) == 0 for t in ("pubmed", "authors", "author_affils"))
```

- [ ] **Step 2:** Run, expect FAIL.
- [ ] **Step 3:** Implement. `store_records` runs in one transaction per call. For an in-scope pmid it deletes the existing `authors` and `author_affils` rows, then inserts. It keeps an in-process `dict[text -> affil_id]` cache, bounded by clearing past 2M entries, and falls back to `SELECT` on a miss.
- [ ] **Step 4:** Run, expect PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat: pubmed_full.db with deduplicated affiliations"`

### Task 4: Rebuild lock holder

**Files:**
- Create: `scripts/rebuild_lock.py`
- Test: `tests/test_rebuild_lock.py`

**Interfaces:**
- Produces: CLI `python scripts/rebuild_lock.py hold|release|status`. `hold` creates `data/.weekly_update.lock/`, writes its own pid to `pid`, writes `owner` = `rebuild`, and sleeps until SIGTERM, removing the lock on exit. It refuses to start if the lock exists with a live pid. `release` sends SIGTERM to the pid in the lock, but only if `owner` is `rebuild`. `status` prints holder pid, owner, and whether the pid is alive.

- [ ] **Step 1: Write failing tests**, using a temp directory via a `--lock-dir` option: `test_hold_writes_live_pid`, `test_refuses_when_held_by_live_pid`, `test_release_only_own_lock`, `test_weekly_wrapper_sees_lock_as_held`. The last one runs the stale check from `weekly_auto_update.sh:120-127` (`kill -0 "$(cat pid)"`) against the held lock and asserts it reports "lock held".
- [ ] **Step 2:** Run, expect FAIL. **Step 3:** Implement. **Step 4:** Run, expect PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat: long-lived lock holder for the rebuild"`

### Task 5: Baseline and update-file ingest

**Files:**
- Create: `scripts/build_pubmed_full.py`
- Test: `tests/test_build_pubmed_full.py`

**Interfaces:**
- Consumes: Task 1 `iter_pubmed_xml`; Task 3 `open_full_db`, `store_records`, `delete_pmids`, `make_byline_scope`, `tracked_issns_from_impact`.
- Produces: CLI `python scripts/build_pubmed_full.py [--sample N] [--limit N] [--min-free-gb 30]`. Functions:
  - `plan_files(baseline:list[str], updates:list[str]) -> list[tuple[str,str]]`, which returns `(url, filename)` with every baseline file in name order, then every update file in name order, each with its own directory URL
  - `free_gb(path) -> float`
  - `project_size(conn, sampled_papers:int, total_papers:int) -> dict` with keys `author_tables_gb` and `pubmed_gb`
  - `process_file(conn, url, filename, in_scope) -> int`

Behavior:
- Refuses to run unless `rebuild_lock.py status` shows a live `rebuild` holder.
- `--sample N` picks N baseline files spread evenly across the list, ingests them into `data/pubmed_full.sample.db`, prints bytes per in-scope paper and the projected `author_tables_gb` for 24.9M papers, and exits non-zero if the projection is over 20.
- Before each file, checks `free_gb(data/) >= --min-free-gb`; otherwise commits, logs, and exits with code 3.
- Marks a file processed only after its rows commit. Logs `files done / total` after each file.
- Runs `PRAGMA wal_checkpoint(TRUNCATE)` every 50 files.

- [ ] **Step 1: Write failing tests**

```python
def test_update_files_use_update_url():
    plan = plan_files(["pubmed26n0001.xml.gz"], ["pubmed26n1335.xml.gz"])
    assert plan[0][0].endswith("/pubmed/baseline/pubmed26n0001.xml.gz")
    assert plan[1][0].endswith("/pubmed/updatefiles/pubmed26n1335.xml.gz")

def test_file_marked_only_after_commit(tmp_path, monkeypatch):
    # process_file raises midway through a fixture file -> processed_files has no row,
    # and a second run stores each pmid exactly once
    ...

def test_low_disk_stops_cleanly(monkeypatch):
    monkeypatch.setattr(mod, "free_gb", lambda p: 10.0)
    assert run_main(["--limit", "1"]) == 3
```

Network is mocked in all tests. Downloads go through `requests` and stream into `io.BytesIO`, as `download_pubmed_bulk.download_file` does today.

- [ ] **Step 2:** Run, expect FAIL. **Step 3:** Implement. **Step 4:** Run, expect PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat: resumable baseline and update-file ingest into pubmed_full.db"`

### Task 6: Document classifier

**Files:**
- Create: `src/pipeline/doc_class.py`
- Modify: `src/pipeline/impact_calculator.py:26-66` so that `ARTICLE_CATEGORIES` becomes `('research','review','case_report','guideline','commentary','editorial','letter','erratum','other')`. `classify_pub_type` stays for callers that only have a type string, and maps through `doc_class.class_for_types([pub_type])`.
- Test: `tests/test_doc_class.py`

**Interfaces:**
- Produces:
  - `CITABLE = frozenset({'research','review','case_report','guideline'})`
  - `class_for_types(pub_types:list[str]) -> str`
  - `classify(pub_types:list[str], has_abstract:bool|None, page_count:int|None, icite_is_research:bool|None, title:str|None) -> tuple[str, str]`, which returns `(doc_class, class_source)`
  - `INFERENCE`, a dict of the rule's tunable parameters, set in Task 7

Type priority is applied to the full list, first group that matches wins, case-insensitive:
1. `erratum`: Published Erratum, Retraction of Publication, Retraction Notice, Expression of Concern
2. `guideline`: Practice Guideline, Guideline, Consensus Development Conference
3. `review`: Systematic Review, Meta-Analysis, Review
4. `case_report`: Case Reports
5. `editorial`: Editorial
6. `letter`: Letter, Comment, Editorial Comment
7. `other`: News, Biography, Obituary, Interview, Portrait, Congress
8. `research`: Journal Article
9. else `other`

Guideline outranks review deliberately. A guideline also tagged Review is a guideline, and both are citable, so the order only affects labels. This fixes the current ordering that left the guideline bucket empty. Record the reason in a comment.

The candidate inference rule, which Task 7 may change: `research` → `commentary` (`inferred`) when `has_abstract is False` and (`page_count` is not None and `page_count <= 2`, or `icite_is_research is False`). Research-letter recovery for `letter` → `research` (`inferred`) is off by default (`INFERENCE["recover_letters"] = False`) until Task 7 validates a signal.

- [ ] **Step 1: Write failing tests** against the Task 1 fixture records:
  - 1001 → `("research","pubmed")`
  - 1002 → `("commentary","inferred")`
  - 1004 → `("guideline","pubmed")`
  - 1005 → `("research","pubmed")`, since e-locator gives `page_count` None and no abstract signal fires
  - 1003 → `("letter","pubmed")` while `recover_letters` is False
  - `CITABLE` exactly equals the four classes
- [ ] **Step 2:** Run, expect FAIL. **Step 3:** Implement. **Step 4:** Run, expect PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat: doc_class classifier with deliberate type priority"`

### Task 7: Apply classes to `impact.db`, and the validation gate

**Files:**
- Create: `scripts/apply_pubmed_full.py`, `scripts/validate_doc_class.py`
- Test: `tests/test_apply_pubmed_full.py`
- Output: `docs/superpowers/specs/2026-10-24-doc-class-validation.md`, the gate report

**Interfaces:**
- Consumes: Task 3 DB; Task 6 `classify`; Task 2 parsers (through `affil_strings` fields); `data/icite_bulk.db` `metadata.is_research_article`.
- Produces:
  - Migration: `papers.doc_class TEXT`, `papers.class_source TEXT`, index `(journal_id, pub_date, doc_class)`
  - `apply_pubmed_full.py [--dry-run] [--journals slug,...]`, which updates, per pmid, `pub_type` (canonical), `doc_class`, `class_source`, `is_research`, and the `first_author_*`/`last_author_*` `name`, `institution`, `city`, `state` and `country` from positions 1 and N through `affil_strings`. It never touches the gender columns.
  - `validate_doc_class.py`, which writes the gate report

- [ ] **Step 1: Write failing tests** on a temp `impact.db` copy holding 3 papers, including gender values:
  - after apply, `doc_class` and `class_source` match `classify`
  - `is_research == (doc_class=='research')`
  - gender columns are byte-identical to before (`test_gender_columns_untouched`)
  - `--dry-run` writes nothing
- [ ] **Step 2:** Run, expect FAIL. **Step 3:** Implement. Process in batches of 50,000 pmids, check the WAL every 20 batches, and apply the 30 GB floor as in Task 5. **Step 4:** Run, expect PASS.
- [ ] **Step 5:** Implement `validate_doc_class.py`. It runs `classify` read-only (`--dry-run` semantics) and reports:
  - per-journal share of `research` reclassified to `commentary`, for the 64 detector slugs plus `nature, science, cell, the-new-england-journal-of-medicine` (resolve The Lancet's and NEJM's real slugs from `journals.name`), `jama, circulation, journal-of-the-american-college-of-cardiology, arteriosclerosis-thrombosis-and-vascular-biology, plos-one, nature-communications`
  - 30 reclassified titles each from JAMA, NEJM, The Lancet, Nature, Nature Reviews Molecular Cell Biology and Nature Reviews Cancer
  - 30 `letter` titles each from JAMA, NEJM and The Lancet, with the candidate research-letter signals beside each: iCite `is_research_article`, title ends with "-Reply" or "Reply", and title equal to an earlier non-letter paper's title in the same journal
- [ ] **Step 6: GATE (owner checkpoint).** Read the report. Pass means Nature Reviews highlights become `commentary`, and JAMA Research Letters end up `research`, or their undercount is measured. If the candidate rule misclassifies real research, tighten `INFERENCE`. If no global rule passes, set `INFERENCE["journals"]` to the 64 detector slugs (the spec's fallback). Encode a letter-recovery rule only if one signal separates the 30-title samples cleanly. Add each validated example as a Task 6 test. **Stop, show the owner the report and the chosen rule, and continue only on their go-ahead.**
- [ ] **Step 7: Commit**: `git commit -m "feat: apply doc_class to impact.db, with validation report"`

### Task 8: Citable-items metric and export fields

**Files:**
- Modify: `src/pipeline/impact_calculator.py:131-228` (`compute_rolling_if`)
- Modify: `src/pipeline/db_manager.py:246-281` so that `count_papers_and_citations_by_type` and `count_papers_by_type_in_month` select and group by `doc_class`
- Modify: `src/pipeline/json_exporter.py:30-75`: add `citable_papers` and `citable_citations` to each point; remove `official_jif_2024` (`:72`)
- Modify: `scripts/compute_snapshots.py:35,78,100`, `scripts/backfill_snapshots.py:138` and `scripts/rebuild_index_from_journals.py:45` to remove `official_jif`
- Test: `tests/test_rolling_if.py`

**Interfaces:**
- Consumes: `papers.doc_class` (Task 7); `CITABLE` (Task 6).
- Produces: snapshot dict keys `citable_papers:int`, `citable_citations:int`, `inferred_papers:int` (window papers with `class_source='inferred'`). All three are also written to every exported timeseries point. `rolling_if = citable_citations / citable_papers`, or 0.0 when there are none. `by_type` is keyed by every `ARTICLE_CATEGORIES` value. `research_count` and `review_count` are counted from `doc_class`.

- [ ] **Step 1: Write failing tests** on a hand-built temp DB for one journal with a 24-month window:
  - 3 research papers with 6 citations in the window
  - 1 review with 4
  - 1 case report with 1
  - 2 commentary with 0
  - 1 editorial with 5

```python
def test_symmetric_citable_rate(calc):
    s = calc.compute_rolling_if(jid, 2024, 12)
    assert s["citable_papers"] == 5 and s["citable_citations"] == 11
    assert s["rolling_if"] == round(11 / 5, 3)          # editorial's 5 citations excluded
    assert s["rolling_if_no_reviews"] == round(6 / 3, 3)
    assert s["by_type"]["commentary"] == {"papers": 2, "citations": 0}

def test_zero_citable_window(calc):          # only commentary in the window
    assert calc.compute_rolling_if(jid2, 2024, 12)["rolling_if"] == 0.0

def test_no_official_jif_in_export(tmp_path):
    assert "official_jif_2024" not in exported_journal(tmp_path)
```

- [ ] **Step 2:** Run, expect FAIL. **Step 3:** Implement. Count citations for citable pmids with the existing `count_citations_for_papers`. **Step 4:** Run, expect PASS.
- [ ] **Step 5: Commit**: `git commit -m "feat: rolling rate over citable items in numerator and denominator"`

### Task 9: Journal flags and per-journal class files

**Files:**
- Create: `src/pipeline/journal_flags.py`
- Modify: `src/pipeline/json_exporter.py`. Add `flags: list[str]` to each journal JSON and to each `index.json` entry. Write `classes/{slug}.json`.
- Test: `tests/test_journal_flags.py`

**Interfaces:**
- Produces:
  - `compute_flags(point:dict) -> list[str]`, evaluated on the latest timeseries point whose citation window ended at least 12 months before the export date. It returns any of `small_research_sample`, `small_review_sample`, `review_journal`, `inferred_types`, using the Global Constraints thresholds. It reads `point["inferred_papers"]` (Task 8).
  - `classes/{slug}.json` = `{"v":1, "citable":[...], "noncitable":[...]}`, where each list holds the journal's 2003–2026 pmids sorted and delta-encoded (first value absolute, then differences). It is used by Task 12.
  - `decode_deltas(list[int]) -> list[int]` (Python, for tests; Task 12 mirrors it in JS).

- [ ] **Step 1: Write failing tests**, one per flag at its threshold boundary (19 vs 20 research, 14 vs 15 reviews, 49% vs 50%, 9% vs 10%), plus a delta round-trip.
- [ ] **Step 2:** Run, expect FAIL. **Step 3:** Implement. **Step 4:** Run, expect PASS.
- [ ] **Step 5:** After the Task 13 recompute, run `python -c` over the exported points to print how many journals trip each flag. If any flag fires on more than a third of journals, report this to the owner with the distribution before keeping the threshold. Record final values in `METHODOLOGY.md` (Task 11).
- [ ] **Step 6: Commit**: `git commit -m "feat: journal reliability flags and citable PMID lists"`

### Task 10: Weekly update on EFetch; retire `pubmed_bulk.db` readers

**Files:**
- Modify: `scripts/run_weekly_update.py`. Replace `esummary_batch` (`:162`) and `_parse_esummary` (`:209`) with `efetch_batch(pmids) -> list[dict]`, which POSTs to `efetch.fcgi` with `retmode=xml` and 200 per request, retries with `request_with_retry`, and parses with `pubmed_xml.parse_article`. Matching uses the record's `issn`; if that has no match, it reads ISSNs from `Journal/ISSN` as the old `essn` fallback did, so `parse_article` also returns `issns:list[str]`. Remove the iCite override at `:592-602`. New rows get `doc_class` and `class_source` from `classify`, with that paper's iCite `is_research_article` passed as evidence where iCite has the paper yet, and records go to `pubmed_full.db` through `store_records`.
- Modify: `scripts/run_pipeline_bulk.py:213-218` to remove the iCite override and set `doc_class` from `classify`.
- Modify: `src/pipeline/config.py` (`PUBMED_BULK_DB_PATH` → `PUBMED_FULL_DB_PATH`), plus `scripts/build_journal_registry.py`, `scripts/fix_citation_months.py` and `scripts/run_pipeline_bulk.py`, to read the `pubmed` table from `pubmed_full.db`
- Remove: `scripts/download_pubmed_bulk.py`, superseded by Task 5 (`git rm`, with a `remove:` commit)
- Test: `tests/test_weekly_efetch.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 6.
- Produces: `efetch_batch(pmids:list[int]) -> list[dict]` (Task 1 record dicts).

- [ ] **Step 1: Write failing tests**, with `requests.post` mocked to return `tests/fixtures/pubmed_records.xml`:
  - `efetch_batch([1001,1002])` returns records with `authors` and `has_abstract`
  - a failed batch adds its pmids to `FAILED_PMIDS["efetch"]`
  - no code path reads `is_research_article` to set `is_research` (`grep` assertion over the two scripts)
- [ ] **Step 2:** Run, expect FAIL. **Step 3:** Implement. **Step 4:** Run, expect PASS.
- [ ] **Step 5:** Run `grep -rn "pubmed_bulk" src scripts`. Expected: no hits except comments.
- [ ] **Step 6: Commit**, two commits: `git commit -m "feat: weekly update fetches full records through EFetch"`, then `git commit -m "remove: download_pubmed_bulk.py, superseded by build_pubmed_full.py"`

### Task 11: Methodology page and docs

**Files:**
- Create: `METHODOLOGY.md`. Start from `git show 60e5b69^:METHODOLOGY.md`, rewritten to match the code.
- Modify: `docs/index.html`. Add a `#methodology` section linked from About, and remove the sentence "This mirrors the official JIF methodology…" from About.
- Modify: `CLAUDE.md`. "Rolling IF formula" points at `METHODOLOGY.md` and states the citable-items formula; `pubmed_bulk.db` → `pubmed_full.db` in Key Directories and Data Flow.

`METHODOLOGY.md` and the site section state:
- the formula, symmetric over citable items, and how it differs from Clarivate (Clarivate's numerator also counts citations to non-citable items; IMPACT's does not)
- the citable classes and the type priority from Task 6
- the inference rule and the gate outcome from Task 7, including the research-letter result or measured undercount
- the three windows (24-mo, 12-mo, 5-yr skip 12)
- the four flags with their final thresholds
- that iCite no longer sets the research flag
- that PubMed recorded only the first author's affiliation before about 2014
- that Geography country values may shift because of the single parser

- [ ] **Step 1:** Write both. **Step 2:** Serve locally (`.claude/launch.json` `python3 -m http.server 8777 -d docs`) and check the section renders and the About link scrolls to it.
- [ ] **Step 3: Commit**: `git commit -m "docs: methodology for the citable-items rolling rate"`

### Task 12: Frontend: new formula, class lookup, flags, versioned data

**Files:**
- Modify: `docs/js/data-loader.js:9`. Add `const R2_DATA_PREFIX = 'v2';` and build every R2 URL as `${R2_BASE_URL}/${R2_DATA_PREFIX}/…`. Add `loadClasses(slug)` → `{citable:Set<number>, noncitable:Set<number>}`, decoding deltas and cached like the other loaders.
- Modify: `docs/js/app.js`:
  - `_computeAdjIf` (`:1804`): use `point.citable_citations` and `point.citable_papers`. A seed comes out of both numerator and denominator only if its pmid is in `classes.citable`. A seed in neither set is left in, and the paper card shows "type unknown; not removed". Remove the use of `is_research_article`.
  - Metric cards (`:610-745`) and the yearly type chart and table: add `commentary`, `erratum`, `case_report` and `guideline` where categories are listed. Okabe-Ito color for `commentary`: `#999999` (grey, listed last).
  - Journal page: render `flags` as one caveat line each, under the metrics row, using `.section-note`. Copy: `small_research_sample` "Fewer than 20 research articles in this window, so rates are noisy."; `small_review_sample` "Fewer than 15 reviews in this window, so review rates are noisy."; `review_journal` "Mostly reviews: at least half of citable items are reviews."; `inferred_types` "10% or more of this window's items were reclassified from PubMed's type (see Methodology)."
- Modify: `docs/index.html`, bumping `?v=` for `app.js` (36→37), `data-loader.js`, `chart-manager.js` if touched, and `style.css` if touched.

- [ ] **Step 1:** Implement against local data (`docs/data/`, `isLocal` path), after Task 13's local export.
- [ ] **Step 2: Verify in the browser** at `http://localhost:8777/index.html?fresh=…`:
  - ATVB loads and its rate matches the exported `rolling_if`
  - Influence for PMID 35510553: the net effect is recomputed, and the paper is found in `classes.citable`
  - a detector journal (Nature Reviews Molecular Cell Biology) shows the `commentary` bucket and any flags
  - no console errors
- [ ] **Step 3: Commit**: `git commit -m "feat: frontend on citable-items rate, class lookup and flags"`. Do **not** push.

### Task 13: Versioned upload and the run

**Files:**
- Modify: `scripts/upload_to_r2.py:86-110`. Add `--prefix PREFIX`, prepended to every key (`key = f"{prefix}/{rel}"` when set). ETag comparison works per key, unchanged.
- Test: `tests/test_upload_prefix.py`, asserting `--prefix v2` maps `journals/aging-cell.json` → `v2/journals/aging-cell.json` and that keys without the prefix are untouched (S3 client mocked).

- [ ] **Step 1–4:** Test, implement, pass, then commit: `git commit -m "feat: upload_to_r2 --prefix for versioned data"`

**Runbook.** Each item is checked off with its observed result.

> **Superseded:** run from `docs/superpowers/plans/2026-10-24-citable-rate-runbook.md`, which replaces this list (adds the R1 lock-before-fast-forward order, the gate before apply, the gap catch-up and the final-review steps).

- [ ] `python scripts/rebuild_lock.py hold &` → `status` shows a live `rebuild` holder
- [ ] `df -h` result recorded. If below 100 GB free, tell the owner before ingesting.
- [ ] `python scripts/build_pubmed_full.py --sample 12` → report the projected `author_tables_gb`. **Stop if over 20.**
- [ ] `python scripts/build_pubmed_full.py` (background) → `files done / total` reaches 1,694/1,694 (the counts were 1,334 + 360 on 2026-10-24; use whatever `list_files` returns)
- [ ] Record the size of `pubmed_full.db` and its author tables, and the country match rate per year from `affil_strings`/`author_affils`
- [ ] `python scripts/apply_pubmed_full.py` → WAL checkpoint, then the Task 7 gate (**owner checkpoint**)
- [ ] `python scripts/compute_snapshots.py --workers 4` → `validate_exports.py` PASSED
- [ ] Spot-check 2024-12 `rolling_if` against the spec's estimates (Nature ≈26.05, Circulation ≈27.37, JACC ≈19.01, ATVB ≈6.00, PLoS ONE ≈1.95; detector journals are expected to move further, toward their review rate) and report a table
- [ ] Task 9 Step 5 (flag distribution) and Task 12 browser verification
- [ ] **Owner go-ahead**, then `python scripts/upload_to_r2.py --prefix v2`
- [ ] **Owner go-ahead**, then push `main`. The Pages deploy succeeds and the live `index.html` references the bumped `?v=`. The live site loads `v2/index.json` (network panel).
- [ ] `python scripts/rebuild_lock.py release`. The next Monday weekly run completes, and its new papers have `authors` rows and `doc_class`.
- [ ] After the owner confirms the live site: delete `data/pubmed_bulk.db` (and its `-shm` and `-wal` files), then report the space freed. Deleting the old R2 root keys is a separate owner decision.
