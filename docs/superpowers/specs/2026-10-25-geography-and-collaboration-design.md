# Geography and collaboration views (project 3)

Date: 2026-10-25
Status: building. The owner asked for implementation without a question round
("implement it like we wanted ... don't hold up the implementation for small
details"). Choices marked **(my call)** were made by Claude and are easy to change.

## What the owner asked for

- Where the people who publish in a journal are from, compared with other
  journals: "more Harvard on the east/west coast in Nature versus the middle
  of the country".
- Countries for international work ("reduce international to the country of
  origin for now"), with several maps: a global one for country-level
  collaboration, a more detailed US map by state, then Europe and maybe China.
- "My own reach": where a given researcher's collaborators are.
- A worry that hubs such as BWH, MGH and Harvard make institution-level views
  messy. This release therefore stays at country and US-state level.

## Data available

`pubmed_full.db` has every author and every affiliation string, with a parsed
country for each affiliation (`affil_countries`, several per string when a
string names several places) and US state and city (`affil_strings`). There
is no province-level parse for China or other countries yet. Before about
2014, PubMed recorded only the first author's affiliation.

## Release 1 (this build)

### A. Journal geography (Geography section)

A new per-journal export, `geo/{slug}.json` (served from R2 under `v2/geo/`),
plus `geo/_all.json` for all tracked journals together. For each journal and
publication year (2005 on), counted over citable items only (research,
review, case report, guideline) **(my call: keeps editorials and errata out,
consistent with the rate)**:

- papers with at least one parsed location;
- for each country: papers with at least one author affiliated there
  ("papers involving"), and fractional credit (each paper's credit of 1 split
  evenly over its countries);
- the same for US states, over papers with a US affiliation;
- papers with authors in two or more countries (international share);
- country pairs and US-state pairs: papers that involve both. Pairs are
  counted only for papers with at most 10 countries (or 10 states)
  **(my call: consortium papers listing 40 countries would otherwise dominate
  the pair counts)**.

The Geography section is rebuilt around a map:

- Map views: World (countries), Europe (countries), United States (states).
  China provinces are deferred (needs a province parser).
- Year range, defaulting to the last five complete years **(my call)**,
  because all-author affiliations are sparse before about 2014.
- Measure: share of papers involving each region (default) or fractional
  share.
- Compare against: nothing, all journals, or another journal. With a
  comparison, the map shows the difference in share in percentage points on a
  diverging scale. This answers "Nature versus the rest".
- Collaboration lines on the map for the strongest pairs, plus a table of the
  top pairs.
- Tables of the leading regions, and the existing "over time" chart, now from
  all authors rather than first authors.

### B. Collaboration reach for one researcher (Authors section)

Author search already pulls a researcher's PMIDs from PubMed in the browser.
A new "Collaboration reach" card fetches those papers' PubMed records
(EFetch, in the browser, batches of 200), parses each affiliation to a
country and US state with a JavaScript port of the location rules, and maps
the share of the researcher's papers involving each country or state. No
backend data is needed, so it works for anyone. **(My call: name-based
author search has the usual namesake problem; the existing tools for
excluding papers apply before the map is drawn.)**

## Deferred

- China (and other) province maps.
- Institution-level views and the hub problem (BWH/MGH/Harvard): needs ROR
  matching over the 43M distinct affiliation strings.
- Adding the geography export to the weekly job. For now it is a separate
  script; geography moves slowly.

## Done means

- `scripts/export_geography.py` writes a valid file for every journal and
  `_all.json`, with tests for the aggregation.
- The Geography section shows World, Europe and US maps with year range,
  comparison, collaboration lines and tables, verified in a browser.
- The Authors section draws a reach map for a searched author.
- The methodology page describes the counting rules.
- Upload to R2 and the push to main wait for the owner.
