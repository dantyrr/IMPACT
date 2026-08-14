# IMPACT-NCATS — Design Spec

**Date:** 2026-08-14
**Status:** Approved design, pending implementation plan

## Purpose

A sibling site to IMPACT that examines the NCATS grant portfolio — all activity codes
(K, R, U, T, SBIR) — and the publication impact of those awards, broken out by CTSA site,
by investigator, and by grant. Modeled on IMPACT-gender: separate repo, shared pipeline
conventions, lean SPA, static JSON on Cloudflare R2, GitHub Pages hosting.

## Feasibility (verified 2026-08-14)

Measured against a 4-hub sample of 7,166 grant-linked PMIDs pulled from the RePORTER
publications API:

| Check | Result |
|---|---|
| PMIDs matched in `impact.db.papers` | 6,863 / 7,166 (**95.8%**) |
| Of which research articles | 6,368 |
| With first-author affiliation | 6,727 (98%) |
| Distinct journals | 1,752 |
| Citation events already loaded | 224,023 |

The core build requires **no new PubMed or iCite bulk ingest**. The only new network
fetches are RePORTER (grants + publication links) and iCite RCR for linked PMIDs.

Other verified facts:

- NCATS exists in RePORTER only from **FY2012** (IC created Dec 2011). FY2008/FY2011
  return zero projects. Pre-2012 CTSA awards were NCRR `UL1RR*` and are **out of scope**
  by decision.
- Volume: ~550 NCATS awards per fiscal year (FY2020 peak 717, FY2025 526).
- `org_ipf_code` is a **stable institutional identifier**: **zero** org-name drift within
  any IPF code observed.
- **Most hubs hold more than one core project number**, because renewals are issued under
  new numbers (e.g. `UL1TR000090` → `UL1TR001070` at the same institution). Keying site
  identity on core project number would silently split most hubs.

  *Caveat on the hub count:* these two findings come from the first 500 of 1,571 total
  UL1/UM1 records (one unpaginated API page), which yielded 66 distinct IPF codes, 51 of
  them with multiple core projects. A separate FY2025-only query returned 62 distinct
  UL1/UM1 organizations, consistent with the ~60-hub CTSA program. The true all-years hub
  count is **≥66** and must be established by full pagination during implementation — it
  is not yet verified.

## Decisions

| Question | Decision |
|---|---|
| Deliverable | Standalone site, IMPACT-NCATS, sibling to IMPACT-gender |
| Grant universe | All NCATS awards, FY2012–present, all activity codes |
| Site identity | `org_ipf_code`, plus a curated `ctsa_registry.json` |
| Metrics | Output, citations, NIH RCR, journal rolling-IF, cost per pub/citation |
| Investigator attribution | Grant-linkage only; no author-name matching |
| Shared publications | Full credit to each hub, flagged with `n_linked_hubs` |

## Architecture

New repo `~/Projects/IMPACT-NCATS` → `github.com/dantyrr/IMPACT-NCATS`.

Two databases, cleanly separated:

- **`data/ncats.db`** — new, small (tens of MB). Grants, sites, investigators,
  grant→PMID links, computed metrics.
- **`data/impact.db`** — existing, 64GB, **read-only**. Papers, citations, journals.
  IMPACT-NCATS never writes to it.

The pipeline joins the two on PMID and exports static JSON. Data served from the existing
Cloudflare R2 account under a new `ncats/` prefix; `docs/data/index.json` stays committed
(small), bulk JSON is gitignored, matching IMPACT's convention.

## Data model — `ncats.db`

```sql
sites          -- one row per funded organization
  ipf_code INTEGER PK, org_name TEXT, slug TEXT, hub_name TEXT,
  city TEXT, state TEXT, is_ctsa_hub INTEGER,
  first_funded_year INTEGER, last_funded_year INTEGER

grants         -- one row per core project (renewals collapse here)
  core_project_num TEXT PK, ipf_code INTEGER FK, activity_code TEXT,
  title TEXT, first_fy INTEGER, last_fy INTEGER,
  total_award_amount REAL, is_hub_award INTEGER

grant_years    -- per-fiscal-year award records
  core_project_num TEXT FK, fiscal_year INTEGER,
  award_amount REAL, project_num TEXT,
  UNIQUE(core_project_num, fiscal_year, project_num)

investigators
  profile_id INTEGER PK, full_name TEXT, first_name TEXT, last_name TEXT

grant_pis
  core_project_num TEXT FK, profile_id INTEGER FK, is_contact_pi INTEGER,
  UNIQUE(core_project_num, profile_id)

grant_pubs
  core_project_num TEXT FK, pmid INTEGER,
  UNIQUE(core_project_num, pmid)

pub_metrics    -- materialized join against impact.db
  pmid INTEGER PK, rcr REAL, citation_count INTEGER, journal_id INTEGER,
  journal_rolling_if REAL, pub_year INTEGER, is_research INTEGER,
  n_linked_hubs INTEGER

site_metrics   -- precomputed aggregates for the frontend
  ipf_code INTEGER, year INTEGER, activity_group TEXT,
  pub_count INTEGER, citation_count INTEGER, mean_rcr REAL,
  mean_journal_if REAL, award_total REAL,
  cost_per_pub REAL, cost_per_citation REAL,
  UNIQUE(ipf_code, year, activity_group)
```

`ctsa_registry.json` — curated, ~66+ entries (exact count TBD by full pagination, see the
caveat under Feasibility), mirroring the existing `journal_registry.json`
pattern. Supplies hub display name (e.g. "Harvard Catalyst"), slug, and the renewal
core-project chain for each IPF code.

## Pipeline — `scripts/ncats/`

All scripts idempotent and re-runnable, following existing IMPACT script conventions.

| Script | Responsibility |
|---|---|
| `fetch_grants.py` | RePORTER projects API, NCATS FY2012–present → `grants`, `grant_years`, `investigators`, `grant_pis`, `sites`. Adapts `grant_scraper/src/nih_reporter.py`. |
| `build_site_registry.py` | Derive hub sites from UL1/UM1 awards keyed on `org_ipf_code`; merge renewal chains; emit/refresh `ctsa_registry.json`. |
| `fetch_publications.py` | RePORTER publications API per core project → `grant_pubs`. Paginated at 500/page. |
| `fetch_rcr.py` | iCite API for RCR on linked PMIDs only. Batch max 200 PMIDs per request (414 above that). |
| `compute_ncats_metrics.py` | Join to `impact.db`; materialize `pub_metrics` and `site_metrics`. |
| `export_ncats_json.py` | Static JSON → `docs/data/`. |
| `upload_to_r2.py` | Lifted from IMPACT, retargeted to the `ncats/` prefix. |
| `validate_ncats.py` | Assertions, see Testing. |

## Attribution rules

1. **Site roll-up.** Every NCATS award whose `org_ipf_code` matches a hub's IPF rolls up
   to that site. Awards at non-hub organizations are retained with `is_ctsa_hub = 0`, so
   NCATS-wide questions remain answerable.
2. **Investigator publications** = the papers RePORTER links to grants that investigator
   holds. No author-name matching. This credits all of a hub's linked papers to the hub
   PI and misses papers written outside the NCATS award — stated explicitly in the methods.
3. **Shared publications.** A paper linked to grants at multiple hubs counts fully in each
   hub's totals and carries `n_linked_hubs`. Consortium-wide totals de-duplicate on PMID.
   Per-site totals therefore sum to more than the unique consortium count; this is stated
   on the site rather than hidden.

## Metrics

Computed per site, per grant, per activity-code group, per investigator, per year:

- Publication count (all, and research-articles-only)
- Total and mean citations
- Mean NIH RCR (iCite)
- Mean rolling-IF of journals published in (the existing IMPACT metric)
- Award total, **cost per publication**, **cost per citation**

## Frontend

Lean SPA, ~700-line `app.js` matching IMPACT-gender's scale. Chart.js 4.4.0, Okabe-Ito
colorblind-safe palette, no build step.

| Section | Content |
|---|---|
| Sites | Hub leaderboard, US map, per-hub detail with output/citation trend |
| Grants | Browse and filter by activity code, fiscal year, site; output per award |
| Investigators | PI search → their grants, publications, journals |
| Compare | Overlay multiple hubs on any metric |
| About | Methods, limitations, data sources |

## Testing

`validate_ncats.py` asserts:

- PMID match rate against `impact.db` stays ≥ 95%
- Every CTSA hub resolves to exactly one `ipf_code`
- All renewal core-project numbers are covered by the registry
- Per-site totals reconcile to de-duplicated consortium totals given `n_linked_hubs`
- No grant references a missing site; no `grant_pubs` row references a missing grant

Unit tests for the registry merge logic and the metric aggregation, following the existing
`tests/` layout.

## Documented limitations

`METHODS_ncats.md` states plainly:

1. **Grant→publication linkage depends on authors citing their grant.** Counts are a
   floor, not a census.
2. **FY2012 floor.** The 2006–2011 NCRR era of the CTSA program is excluded, so early hub
   output is invisible and trend lines must not be read as program inception.
3. **Grant-linkage attribution** credits hub PIs broadly and misses non-NCATS work.
4. **Full-credit double counting** inflates per-site sums relative to unique totals.
5. ~4% of grant-linked PMIDs are absent from `impact.db` (non-indexed or out-of-range
   journals) and are excluded from journal-quality metrics.

## Out of scope

- Pre-2012 NCRR CTSA awards
- Author-name matching for investigator profiles
- Co-authorship / inter-hub collaboration networks
- Trainee (KL2/TL1) career-outcome tracking

These are deliberate deferrals, not oversights, and can each become a follow-on spec.
