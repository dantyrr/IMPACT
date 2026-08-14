# IMPACT-NCATS Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `ncats.db` — every NCATS award FY2012–present, the CTSA site registry keyed on `org_ipf_code`, grant→PMID publication links, and computed publication-impact metrics — then export it as static JSON ready for a frontend.

**Architecture:** A new standalone repo `IMPACT-NCATS` following the IMPACT-gender sibling pattern. A thin RePORTER API client feeds a small SQLite database (`data/ncats.db`); a metrics step joins that database against the existing read-only `impact.db` (24.9M papers, citations, journals) on PMID; an export step writes static JSON. No writes ever occur against `impact.db`.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), `requests`, `pytest`, `boto3` (R2 upload only). No ORM, no build step — matching existing IMPACT conventions.

**Scope note:** This plan covers the data layer only. The SPA frontend described in the spec is a separate plan, written after this one produces real JSON to render.

## Global Constraints

- Grant universe: **NCATS only, FY2012–present**, all activity codes. Pre-2012 NCRR `UL1RR*` awards are out of scope.
- Site identity key: **`org_ipf_code`** (integer). Never key a site on core project number.
- Investigator attribution: **grant-linkage only**. No author-name matching anywhere in this plan.
- Shared publications: **full credit to each hub**, with `n_linked_hubs` recorded. Consortium totals de-duplicate on PMID.
- `impact.db` is opened **read-only** (`file:...?mode=ro` URI). Any write is a bug.
- RePORTER API: **1 request/second** max, `limit` max 500 per page, paginate on `meta.total`.
- iCite API: **max 200 PMIDs per request** (414 errors above that).
- Python naming: snake_case functions/variables, PascalCase classes, UPPER_SNAKE_CASE constants.
- Commit style: conventional commits (`feat:`, `fix:`, `docs:`, `test:`). **No `Co-Authored-By` line.**
- All scripts idempotent — re-running must not duplicate rows.

---

### Task 1: Repo scaffold, config, and schema

**Files:**
- Create: `~/Projects/IMPACT-NCATS/requirements.txt`
- Create: `~/Projects/IMPACT-NCATS/.gitignore`
- Create: `~/Projects/IMPACT-NCATS/.env.example`
- Create: `~/Projects/IMPACT-NCATS/src/ncats/__init__.py`
- Create: `~/Projects/IMPACT-NCATS/src/ncats/config.py`
- Create: `~/Projects/IMPACT-NCATS/src/ncats/schema.py`
- Create: `~/Projects/IMPACT-NCATS/scripts/init_db.py`
- Test: `~/Projects/IMPACT-NCATS/tests/test_schema.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `config.NCATS_DB_PATH: Path`, `config.IMPACT_DB_PATH: Path`, `config.REPORTER_PROJECTS_URL: str`, `config.REPORTER_PUBS_URL: str`, `config.ICITE_BASE_URL: str`, `config.REPORTER_RATE_LIMIT: float`, `config.FIRST_FISCAL_YEAR: int`, `config.HUB_ACTIVITY_CODES: list[str]`; `schema.create_schema(conn: sqlite3.Connection) -> None`; `schema.connect_ncats() -> sqlite3.Connection`; `schema.connect_impact_readonly() -> sqlite3.Connection`.

- [ ] **Step 1: Create the repo directory and git init**

```bash
mkdir -p ~/Projects/IMPACT-NCATS/{src/ncats,scripts,tests,data,docs/data}
cd ~/Projects/IMPACT-NCATS
git init -b main
```

- [ ] **Step 2: Write `requirements.txt`, `.gitignore`, `.env.example`**

`requirements.txt`:
```
requests>=2.28.0
python-dotenv>=1.0.0
pytest>=7.0.0
boto3>=1.34.0
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
data/*.db
data/*.db-shm
data/*.db-wal
docs/data/sites/
docs/data/grants/
docs/data/investigators/
.DS_Store
```

`.env.example`:
```
# Path to the existing read-only IMPACT database
IMPACT_DB_PATH=/Users/dtyrrell/Projects/IMPACT/data/impact.db

# Cloudflare R2 (same account as IMPACT, new prefix)
R2_ACCOUNT_ID=
R2_BUCKET_NAME=impact-data
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_PUBLIC_URL=
R2_PREFIX=ncats
```

- [ ] **Step 3: Write `src/ncats/config.py`**

```python
"""IMPACT-NCATS configuration: paths, API endpoints, rate limits."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
WEBSITE_DATA_DIR = PROJECT_ROOT / "docs" / "data"

NCATS_DB_PATH = DATA_DIR / "ncats.db"
IMPACT_DB_PATH = Path(
    os.getenv("IMPACT_DB_PATH", Path.home() / "Projects/IMPACT/data/impact.db")
)

# --- APIs ---
REPORTER_PROJECTS_URL = "https://api.reporter.nih.gov/v2/projects/search"
REPORTER_PUBS_URL = "https://api.reporter.nih.gov/v2/publications/search"
ICITE_BASE_URL = "https://icite.od.nih.gov/api/pubs"

# RePORTER documents a 1 req/sec ceiling.
REPORTER_RATE_LIMIT = 1.0
REPORTER_PAGE_SIZE = 500
ICITE_RATE_LIMIT = 5.0
ICITE_MAX_BATCH = 200

# --- Scope ---
AGENCY = "NCATS"
FIRST_FISCAL_YEAR = 2012
HUB_ACTIVITY_CODES = ["UL1", "UM1"]

# --- R2 ---
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "impact-data")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")
R2_PREFIX = os.getenv("R2_PREFIX", "ncats")
```

- [ ] **Step 4: Write the failing test**

`tests/test_schema.py`:
```python
import sqlite3
import pytest
from src.ncats.schema import create_schema

EXPECTED_TABLES = {
    "sites", "grants", "grant_years", "investigators",
    "grant_pis", "grant_pubs", "pub_metrics", "site_metrics",
}


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    yield c
    c.close()


def test_all_tables_created(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    assert EXPECTED_TABLES <= {r[0] for r in rows}


def test_create_schema_is_idempotent(conn):
    create_schema(conn)  # second call must not raise
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    assert EXPECTED_TABLES <= {r[0] for r in rows}


def test_grant_pubs_rejects_duplicate_link(conn):
    conn.execute("INSERT INTO sites (ipf_code, org_name) VALUES (1, 'X')")
    conn.execute(
        "INSERT INTO grants (core_project_num, ipf_code, activity_code) "
        "VALUES ('UL1TR000001', 1, 'UL1')"
    )
    conn.execute("INSERT INTO grant_pubs (core_project_num, pmid) VALUES ('UL1TR000001', 42)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO grant_pubs (core_project_num, pmid) VALUES ('UL1TR000001', 42)"
        )


def test_site_is_keyed_on_ipf_code(conn):
    conn.execute("INSERT INTO sites (ipf_code, org_name) VALUES (7, 'A')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sites (ipf_code, org_name) VALUES (7, 'B')")
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ncats.schema'`

- [ ] **Step 6: Write `src/ncats/schema.py`**

```python
"""ncats.db schema definition and connection helpers."""

import sqlite3
from src.ncats.config import NCATS_DB_PATH, IMPACT_DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sites (
    ipf_code          INTEGER PRIMARY KEY,
    org_name          TEXT NOT NULL,
    slug              TEXT,
    hub_name          TEXT,
    city              TEXT,
    state             TEXT,
    is_ctsa_hub       INTEGER NOT NULL DEFAULT 0,
    first_funded_year INTEGER,
    last_funded_year  INTEGER
);

CREATE TABLE IF NOT EXISTS grants (
    core_project_num   TEXT PRIMARY KEY,
    ipf_code           INTEGER REFERENCES sites(ipf_code),
    activity_code      TEXT,
    title              TEXT,
    first_fy           INTEGER,
    last_fy            INTEGER,
    total_award_amount REAL DEFAULT 0,
    is_hub_award       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS grant_years (
    core_project_num TEXT NOT NULL REFERENCES grants(core_project_num),
    fiscal_year      INTEGER NOT NULL,
    project_num      TEXT NOT NULL,
    award_amount     REAL DEFAULT 0,
    UNIQUE(core_project_num, fiscal_year, project_num)
);

CREATE TABLE IF NOT EXISTS investigators (
    profile_id INTEGER PRIMARY KEY,
    full_name  TEXT,
    first_name TEXT,
    last_name  TEXT
);

CREATE TABLE IF NOT EXISTS grant_pis (
    core_project_num TEXT NOT NULL REFERENCES grants(core_project_num),
    profile_id       INTEGER NOT NULL REFERENCES investigators(profile_id),
    is_contact_pi    INTEGER NOT NULL DEFAULT 0,
    UNIQUE(core_project_num, profile_id)
);

CREATE TABLE IF NOT EXISTS grant_pubs (
    core_project_num TEXT NOT NULL REFERENCES grants(core_project_num),
    pmid             INTEGER NOT NULL,
    UNIQUE(core_project_num, pmid)
);

CREATE TABLE IF NOT EXISTS pub_metrics (
    pmid               INTEGER PRIMARY KEY,
    rcr                REAL,
    citation_count     INTEGER DEFAULT 0,
    journal_id         INTEGER,
    journal_name       TEXT,
    journal_rolling_if REAL,
    pub_year           INTEGER,
    is_research        INTEGER,
    in_impact_db       INTEGER NOT NULL DEFAULT 0,
    n_linked_hubs      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS site_metrics (
    ipf_code          INTEGER NOT NULL REFERENCES sites(ipf_code),
    year              INTEGER NOT NULL,
    activity_group    TEXT NOT NULL,
    pub_count         INTEGER DEFAULT 0,
    research_count    INTEGER DEFAULT 0,
    citation_count    INTEGER DEFAULT 0,
    mean_rcr          REAL,
    mean_journal_if   REAL,
    award_total       REAL DEFAULT 0,
    cost_per_pub      REAL,
    cost_per_citation REAL,
    UNIQUE(ipf_code, year, activity_group)
);

CREATE INDEX IF NOT EXISTS idx_grants_ipf ON grants(ipf_code);
CREATE INDEX IF NOT EXISTS idx_grants_activity ON grants(activity_code);
CREATE INDEX IF NOT EXISTS idx_grant_years_fy ON grant_years(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_grant_pubs_pmid ON grant_pubs(pmid);
CREATE INDEX IF NOT EXISTS idx_grant_pubs_core ON grant_pubs(core_project_num);
CREATE INDEX IF NOT EXISTS idx_site_metrics_site ON site_metrics(ipf_code, year);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes. Safe to call repeatedly."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def connect_ncats() -> sqlite3.Connection:
    """Open (creating if needed) the writable ncats.db."""
    NCATS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(NCATS_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    create_schema(conn)
    return conn


def connect_impact_readonly() -> sqlite3.Connection:
    """Open the existing impact.db strictly read-only."""
    if not IMPACT_DB_PATH.exists():
        raise FileNotFoundError(
            f"impact.db not found at {IMPACT_DB_PATH}. Set IMPACT_DB_PATH in .env"
        )
    return sqlite3.connect(f"file:{IMPACT_DB_PATH}?mode=ro", uri=True)
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_schema.py -v`
Expected: PASS — 4 passed

- [ ] **Step 8: Write `scripts/init_db.py`**

```python
#!/usr/bin/env python3
"""Create an empty ncats.db with the full schema."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ncats.schema import connect_ncats
from src.ncats.config import NCATS_DB_PATH

if __name__ == "__main__":
    conn = connect_ncats()
    conn.close()
    print(f"Initialized {NCATS_DB_PATH}")
```

- [ ] **Step 9: Verify it runs**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/init_db.py`
Expected: `Initialized /Users/dtyrrell/Projects/IMPACT-NCATS/data/ncats.db`

- [ ] **Step 10: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add requirements.txt .gitignore .env.example src/ scripts/init_db.py tests/
git commit -m "feat: scaffold IMPACT-NCATS repo with config and ncats.db schema"
```

---

### Task 2: RePORTER API client

**Files:**
- Create: `~/Projects/IMPACT-NCATS/src/ncats/reporter_client.py`
- Test: `~/Projects/IMPACT-NCATS/tests/test_reporter_client.py`

**Interfaces:**
- Consumes: `config.REPORTER_PROJECTS_URL`, `config.REPORTER_PUBS_URL`, `config.REPORTER_RATE_LIMIT`, `config.REPORTER_PAGE_SIZE`, `config.AGENCY`.
- Produces:
  - `ReporterClient.fetch_projects(fiscal_year: int) -> list[dict]` — all NCATS project records for one FY, fully paginated.
  - `ReporterClient.fetch_publications(core_project_num: str) -> list[int]` — all linked PMIDs, fully paginated, de-duplicated.

Pagination is the critical behavior here: the spec's hub-count caveat exists precisely because an earlier probe read only the first page.

- [ ] **Step 1: Write the failing test**

`tests/test_reporter_client.py`:
```python
from unittest.mock import patch, MagicMock
from src.ncats.reporter_client import ReporterClient


def _resp(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


def test_fetch_projects_paginates_past_first_page():
    """total=1200 must produce 3 requests and 1200 records, not 500."""
    pages = [
        _resp({"meta": {"total": 1200},
               "results": [{"core_project_num": f"A{i}"} for i in range(500)]}),
        _resp({"meta": {"total": 1200},
               "results": [{"core_project_num": f"B{i}"} for i in range(500)]}),
        _resp({"meta": {"total": 1200},
               "results": [{"core_project_num": f"C{i}"} for i in range(200)]}),
    ]
    with patch("src.ncats.reporter_client.requests.post", side_effect=pages) as p:
        client = ReporterClient(rate_limit=1000)
        out = client.fetch_projects(2024)
    assert len(out) == 1200
    assert p.call_count == 3
    offsets = [c.kwargs["json"]["offset"] for c in p.call_args_list]
    assert offsets == [0, 500, 1000]


def test_fetch_projects_sends_ncats_and_fiscal_year():
    with patch("src.ncats.reporter_client.requests.post",
               return_value=_resp({"meta": {"total": 0}, "results": []})) as p:
        ReporterClient(rate_limit=1000).fetch_projects(2019)
    crit = p.call_args.kwargs["json"]["criteria"]
    assert crit["agencies"] == ["NCATS"]
    assert crit["fiscal_years"] == [2019]


def test_fetch_publications_returns_deduped_pmids():
    pages = [
        _resp({"meta": {"total": 3},
               "results": [{"pmid": 11}, {"pmid": 22}, {"pmid": 11}]}),
    ]
    with patch("src.ncats.reporter_client.requests.post", side_effect=pages):
        out = ReporterClient(rate_limit=1000).fetch_publications("UL1TR001881")
    assert sorted(out) == [11, 22]


def test_fetch_projects_stops_on_empty_results_guard():
    """A server that reports a huge total but returns nothing must not loop forever."""
    pages = [
        _resp({"meta": {"total": 99999}, "results": []}),
    ]
    with patch("src.ncats.reporter_client.requests.post", side_effect=pages) as p:
        out = ReporterClient(rate_limit=1000).fetch_projects(2024)
    assert out == []
    assert p.call_count == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_reporter_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ncats.reporter_client'`

- [ ] **Step 3: Write `src/ncats/reporter_client.py`**

```python
"""NIH RePORTER v2 API client (projects + publications)."""

import time
import logging
import requests

from src.ncats.config import (
    REPORTER_PROJECTS_URL, REPORTER_PUBS_URL,
    REPORTER_RATE_LIMIT, REPORTER_PAGE_SIZE, AGENCY,
)

logger = logging.getLogger(__name__)

PROJECT_FIELDS = [
    "ProjectNum", "CoreProjectNum", "ActivityCode", "ProjectTitle",
    "Organization", "PrincipalInvestigators", "AwardAmount", "FiscalYear",
]


class ReporterClient:
    """Paginating, rate-limited client for the NIH RePORTER v2 API."""

    def __init__(self, rate_limit: float = REPORTER_RATE_LIMIT):
        self.min_interval = 1.0 / rate_limit
        self.last_request_time = 0.0

    def _wait(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _paginate(self, url: str, criteria: dict, include_fields=None) -> list[dict]:
        """Fetch every page for a query. Returns the concatenated results."""
        results, offset = [], 0
        while True:
            payload = {
                "criteria": criteria,
                "offset": offset,
                "limit": REPORTER_PAGE_SIZE,
            }
            if include_fields:
                payload["include_fields"] = include_fields

            self._wait()
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            batch = data.get("results") or []
            results.extend(batch)

            total = data.get("meta", {}).get("total", 0)
            offset += REPORTER_PAGE_SIZE

            # Guard: stop on an empty page even if `total` claims more,
            # so a bad total can never cause an infinite loop.
            if not batch or offset >= total:
                break
        return results

    def fetch_projects(self, fiscal_year: int) -> list[dict]:
        """All NCATS project records for one fiscal year."""
        criteria = {"agencies": [AGENCY], "fiscal_years": [fiscal_year]}
        out = self._paginate(REPORTER_PROJECTS_URL, criteria, PROJECT_FIELDS)
        logger.info("FY%s: %d project records", fiscal_year, len(out))
        return out

    def fetch_publications(self, core_project_num: str) -> list[int]:
        """All PMIDs linked to a core project, de-duplicated."""
        criteria = {"core_project_nums": [core_project_num]}
        rows = self._paginate(REPORTER_PUBS_URL, criteria)
        pmids = {r["pmid"] for r in rows if r.get("pmid")}
        logger.info("%s: %d linked PMIDs", core_project_num, len(pmids))
        return sorted(pmids)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_reporter_client.py -v`
Expected: PASS — 4 passed

- [ ] **Step 5: Smoke-test against the live API**

Run:
```bash
cd ~/Projects/IMPACT-NCATS && python -c "
from src.ncats.reporter_client import ReporterClient
c = ReporterClient()
p = c.fetch_projects(2024)
print('FY2024 projects:', len(p))
print('sample:', p[0]['core_project_num'], p[0]['activity_code'])
"
```
Expected: `FY2024 projects: 550` (±small drift as RePORTER updates), then a sample core project number and activity code.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add src/ncats/reporter_client.py tests/test_reporter_client.py
git commit -m "feat: add paginating rate-limited RePORTER v2 client"
```

---

### Task 3: Ingest grants into ncats.db

**Files:**
- Create: `~/Projects/IMPACT-NCATS/src/ncats/grant_ingest.py`
- Create: `~/Projects/IMPACT-NCATS/scripts/fetch_grants.py`
- Test: `~/Projects/IMPACT-NCATS/tests/test_grant_ingest.py`

**Interfaces:**
- Consumes: `schema.create_schema`, `ReporterClient.fetch_projects`.
- Produces: `grant_ingest.ingest_projects(conn: sqlite3.Connection, records: list[dict]) -> dict` returning counts `{"sites": int, "grants": int, "grant_years": int, "investigators": int}`.

Ingest must be idempotent: `total_award_amount` and `first_fy`/`last_fy` are recomputed from `grant_years` rather than accumulated, so re-running never double-counts money.

- [ ] **Step 1: Write the failing test**

`tests/test_grant_ingest.py`:
```python
import sqlite3
import pytest
from src.ncats.schema import create_schema
from src.ncats.grant_ingest import ingest_projects


def _record(core="UL1TR001881", fy=2024, amount=1000.0, ipf=577504,
            org="UCLA", act="UL1", proj=None):
    return {
        "core_project_num": core,
        "project_num": proj or f"5{core}-01",
        "activity_code": act,
        "project_title": "Test Award",
        "fiscal_year": fy,
        "award_amount": amount,
        "organization": {
            "org_name": org, "org_city": "LOS ANGELES",
            "org_state": "CA", "org_ipf_code": ipf,
        },
        "principal_investigators": [
            {"profile_id": 1, "first_name": "Ada", "last_name": "Lovelace",
             "full_name": "Ada Lovelace", "is_contact_pi": True},
        ],
    }


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    yield c
    c.close()


def test_ingest_creates_site_grant_and_pi(conn):
    ingest_projects(conn, [_record()])
    assert conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM investigators").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM grant_pis").fetchone()[0] == 1


def test_award_amounts_sum_across_fiscal_years(conn):
    ingest_projects(conn, [
        _record(fy=2023, amount=100.0, proj="5UL1TR001881-01"),
        _record(fy=2024, amount=250.0, proj="5UL1TR001881-02"),
    ])
    total, first, last = conn.execute(
        "SELECT total_award_amount, first_fy, last_fy FROM grants"
    ).fetchone()
    assert total == 350.0
    assert (first, last) == (2023, 2024)


def test_ingest_is_idempotent(conn):
    recs = [_record(fy=2023, amount=100.0, proj="5UL1TR001881-01"),
            _record(fy=2024, amount=250.0, proj="5UL1TR001881-02")]
    ingest_projects(conn, recs)
    ingest_projects(conn, recs)  # re-run
    assert conn.execute("SELECT COUNT(*) FROM grant_years").fetchone()[0] == 2
    assert conn.execute("SELECT total_award_amount FROM grants").fetchone()[0] == 350.0


def test_hub_awards_are_flagged(conn):
    ingest_projects(conn, [
        _record(core="UL1TR001881", act="UL1"),
        _record(core="R01TR009999", act="R01", ipf=999999, org="OTHER"),
    ])
    flags = dict(conn.execute(
        "SELECT core_project_num, is_hub_award FROM grants"))
    assert flags["UL1TR001881"] == 1
    assert flags["R01TR009999"] == 0


def test_record_with_no_ipf_code_is_skipped(conn):
    bad = _record()
    bad["organization"]["org_ipf_code"] = None
    counts = ingest_projects(conn, [bad])
    assert counts["grants"] == 0
    assert conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0] == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_grant_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ncats.grant_ingest'`

- [ ] **Step 3: Write `src/ncats/grant_ingest.py`**

```python
"""Transform RePORTER project records into ncats.db rows."""

import logging
import sqlite3

from src.ncats.config import HUB_ACTIVITY_CODES

logger = logging.getLogger(__name__)


def ingest_projects(conn: sqlite3.Connection, records: list[dict]) -> dict:
    """Insert/refresh sites, grants, grant_years, investigators, grant_pis.

    Idempotent: award totals and FY ranges are recomputed from grant_years,
    never accumulated in place.
    """
    counts = {"sites": 0, "grants": 0, "grant_years": 0, "investigators": 0}
    touched_cores = set()

    for rec in records:
        org = rec.get("organization") or {}
        ipf = org.get("org_ipf_code")
        core = rec.get("core_project_num")
        if not ipf or not core:
            logger.warning("Skipping record with no IPF or core project: %s", core)
            continue

        cur = conn.execute(
            "INSERT INTO sites (ipf_code, org_name, city, state) VALUES (?,?,?,?) "
            "ON CONFLICT(ipf_code) DO UPDATE SET org_name=excluded.org_name",
            (ipf, org.get("org_name"), org.get("org_city"), org.get("org_state")),
        )
        counts["sites"] += cur.rowcount

        activity = rec.get("activity_code")
        is_hub = 1 if activity in HUB_ACTIVITY_CODES else 0
        cur = conn.execute(
            "INSERT INTO grants (core_project_num, ipf_code, activity_code, title, is_hub_award) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(core_project_num) DO UPDATE SET "
            "  ipf_code=excluded.ipf_code, activity_code=excluded.activity_code",
            (core, ipf, activity, rec.get("project_title"), is_hub),
        )
        counts["grants"] += cur.rowcount

        cur = conn.execute(
            "INSERT OR IGNORE INTO grant_years "
            "(core_project_num, fiscal_year, project_num, award_amount) VALUES (?,?,?,?)",
            (core, rec.get("fiscal_year"), rec.get("project_num") or core,
             rec.get("award_amount") or 0),
        )
        counts["grant_years"] += cur.rowcount
        touched_cores.add(core)

        for pi in rec.get("principal_investigators") or []:
            pid = pi.get("profile_id")
            if not pid:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO investigators "
                "(profile_id, full_name, first_name, last_name) VALUES (?,?,?,?)",
                (pid, (pi.get("full_name") or "").strip(),
                 pi.get("first_name"), pi.get("last_name")),
            )
            counts["investigators"] += cur.rowcount
            conn.execute(
                "INSERT OR IGNORE INTO grant_pis "
                "(core_project_num, profile_id, is_contact_pi) VALUES (?,?,?)",
                (core, pid, 1 if pi.get("is_contact_pi") else 0),
            )

    # Recompute rollups from grant_years so re-runs stay correct.
    for core in touched_cores:
        conn.execute(
            "UPDATE grants SET "
            "  total_award_amount = (SELECT COALESCE(SUM(award_amount),0) "
            "                        FROM grant_years WHERE core_project_num=?),"
            "  first_fy = (SELECT MIN(fiscal_year) FROM grant_years WHERE core_project_num=?),"
            "  last_fy  = (SELECT MAX(fiscal_year) FROM grant_years WHERE core_project_num=?) "
            "WHERE core_project_num=?",
            (core, core, core, core),
        )

    conn.commit()
    return counts
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_grant_ingest.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Write `scripts/fetch_grants.py`**

```python
#!/usr/bin/env python3
"""Fetch all NCATS grants FY2012-present into ncats.db.

Usage:
    python scripts/fetch_grants.py
    python scripts/fetch_grants.py --start-year 2020 --end-year 2026
"""

import sys, os, argparse, logging
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ncats.config import FIRST_FISCAL_YEAR
from src.ncats.schema import connect_ncats
from src.ncats.reporter_client import ReporterClient
from src.ncats.grant_ingest import ingest_projects

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=FIRST_FISCAL_YEAR)
    ap.add_argument("--end-year", type=int, default=date.today().year + 1)
    args = ap.parse_args()

    conn = connect_ncats()
    client = ReporterClient()
    totals = {"sites": 0, "grants": 0, "grant_years": 0, "investigators": 0}

    for fy in range(args.start_year, args.end_year + 1):
        records = client.fetch_projects(fy)
        if not records:
            log.info("FY%d: no records", fy)
            continue
        counts = ingest_projects(conn, records)
        for k in totals:
            totals[k] += counts[k]
        log.info("FY%d: +%s", fy, counts)

    log.info("DONE new rows: %s", totals)
    for label, q in [
        ("sites", "SELECT COUNT(*) FROM sites"),
        ("grants", "SELECT COUNT(*) FROM grants"),
        ("hub awards", "SELECT COUNT(*) FROM grants WHERE is_hub_award=1"),
        ("hub sites", "SELECT COUNT(DISTINCT ipf_code) FROM grants WHERE is_hub_award=1"),
        ("investigators", "SELECT COUNT(*) FROM investigators"),
    ]:
        log.info("%-14s %s", label, conn.execute(q).fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the real ingest**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/fetch_grants.py`
Expected: ~15 fiscal years processed; final counts printed. **Record the "hub sites" number** — this resolves the spec's open question about the true hub count (expected ≥66).

- [ ] **Step 7: Verify idempotency by re-running**

Run:
```bash
cd ~/Projects/IMPACT-NCATS
sqlite3 data/ncats.db "SELECT COUNT(*), ROUND(SUM(total_award_amount)) FROM grants" > /tmp/before.txt
python scripts/fetch_grants.py >/dev/null 2>&1
sqlite3 data/ncats.db "SELECT COUNT(*), ROUND(SUM(total_award_amount)) FROM grants" > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt && echo "IDEMPOTENT OK"
```
Expected: `IDEMPOTENT OK` — identical grant count and identical dollar total.

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add src/ncats/grant_ingest.py scripts/fetch_grants.py tests/test_grant_ingest.py
git commit -m "feat: ingest NCATS grants FY2012-present into ncats.db"
```

---

### Task 4: CTSA site registry

**Files:**
- Create: `~/Projects/IMPACT-NCATS/src/ncats/site_registry.py`
- Create: `~/Projects/IMPACT-NCATS/scripts/build_site_registry.py`
- Create: `~/Projects/IMPACT-NCATS/data/ctsa_registry.json` (generated, then hand-edited)
- Test: `~/Projects/IMPACT-NCATS/tests/test_site_registry.py`

**Interfaces:**
- Consumes: populated `sites` and `grants` tables from Task 3.
- Produces:
  - `site_registry.slugify(name: str) -> str`
  - `site_registry.mark_ctsa_hubs(conn) -> int` — sets `is_ctsa_hub`, `first_funded_year`, `last_funded_year`, `slug` from hub awards; returns hub count.
  - `site_registry.export_registry(conn, path: Path) -> list[dict]` — writes `ctsa_registry.json`, preserving any hand-edited `hub_name` already in the file.

- [ ] **Step 1: Write the failing test**

`tests/test_site_registry.py`:
```python
import json
import sqlite3
import pytest
from src.ncats.schema import create_schema
from src.ncats.site_registry import slugify, mark_ctsa_hubs, export_registry


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    c.execute("INSERT INTO sites (ipf_code, org_name) VALUES (1, 'UNIVERSITY OF CALIFORNIA LOS ANGELES')")
    c.execute("INSERT INTO sites (ipf_code, org_name) VALUES (2, 'INSIGHTFIL')")
    # Hub with two renewal core projects at the same IPF
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code, is_hub_award) VALUES ('UL1TR000090',1,'UL1',1)")
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code, is_hub_award) VALUES ('UL1TR001070',1,'UL1',1)")
    c.execute("INSERT INTO grant_years (core_project_num, fiscal_year, project_num) VALUES ('UL1TR000090',2012,'a')")
    c.execute("INSERT INTO grant_years (core_project_num, fiscal_year, project_num) VALUES ('UL1TR001070',2024,'b')")
    # Non-hub award
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code, is_hub_award) VALUES ('R44TR003071',2,'R44',0)")
    c.execute("INSERT INTO grant_years (core_project_num, fiscal_year, project_num) VALUES ('R44TR003071',2024,'c')")
    yield c
    c.close()


def test_slugify():
    assert slugify("UNIVERSITY OF CALIFORNIA LOS ANGELES") == "university-of-california-los-angeles"
    assert slugify("Mayo Clinic  Rochester") == "mayo-clinic-rochester"
    assert slugify("St. Jude's & Co.") == "st-judes-co"


def test_only_hub_sites_are_flagged(conn):
    assert mark_ctsa_hubs(conn) == 1
    flags = dict(conn.execute("SELECT ipf_code, is_ctsa_hub FROM sites"))
    assert flags[1] == 1
    assert flags[2] == 0


def test_renewal_chain_collapses_to_one_site(conn):
    mark_ctsa_hubs(conn)
    rows = conn.execute("SELECT COUNT(*) FROM sites WHERE is_ctsa_hub=1").fetchone()[0]
    assert rows == 1, "two core projects at one IPF must be one site, not two"


def test_funded_year_span_covers_all_renewals(conn):
    mark_ctsa_hubs(conn)
    first, last = conn.execute(
        "SELECT first_funded_year, last_funded_year FROM sites WHERE ipf_code=1"
    ).fetchone()
    assert (first, last) == (2012, 2024)


def test_export_preserves_hand_edited_hub_name(conn, tmp_path):
    mark_ctsa_hubs(conn)
    path = tmp_path / "ctsa_registry.json"
    path.write_text(json.dumps([{"ipf_code": 1, "hub_name": "UCLA CTSI"}]))
    out = export_registry(conn, path)
    entry = [e for e in out if e["ipf_code"] == 1][0]
    assert entry["hub_name"] == "UCLA CTSI"
    assert entry["core_project_nums"] == ["UL1TR000090", "UL1TR001070"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_site_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ncats.site_registry'`

- [ ] **Step 3: Write `src/ncats/site_registry.py`**

```python
"""CTSA site registry: hub identification keyed on org_ipf_code."""

import json
import re
import sqlite3
from pathlib import Path


def slugify(name: str) -> str:
    """Lowercase kebab-case slug, matching IMPACT journal-slug conventions."""
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")


def mark_ctsa_hubs(conn: sqlite3.Connection) -> int:
    """Flag every site holding a hub award, and set its slug and funded span.

    Because identity is the IPF code, a site with several renewal core
    projects collapses into exactly one hub row.
    """
    conn.execute("UPDATE sites SET is_ctsa_hub = 0")
    conn.execute(
        "UPDATE sites SET is_ctsa_hub = 1 "
        "WHERE ipf_code IN (SELECT DISTINCT ipf_code FROM grants WHERE is_hub_award = 1)"
    )
    conn.execute(
        "UPDATE sites SET "
        "  slug = ?, "
        "  first_funded_year = ("
        "    SELECT MIN(gy.fiscal_year) FROM grant_years gy "
        "    JOIN grants g ON g.core_project_num = gy.core_project_num "
        "    WHERE g.ipf_code = sites.ipf_code), "
        "  last_funded_year = ("
        "    SELECT MAX(gy.fiscal_year) FROM grant_years gy "
        "    JOIN grants g ON g.core_project_num = gy.core_project_num "
        "    WHERE g.ipf_code = sites.ipf_code) "
        "WHERE 1=1",
        ("",),
    )
    # Slug per row (SQLite cannot call Python in bulk UPDATE).
    for ipf, org in conn.execute("SELECT ipf_code, org_name FROM sites").fetchall():
        conn.execute("UPDATE sites SET slug=? WHERE ipf_code=?", (slugify(org), ipf))

    conn.commit()
    return conn.execute(
        "SELECT COUNT(*) FROM sites WHERE is_ctsa_hub = 1"
    ).fetchone()[0]


def export_registry(conn: sqlite3.Connection, path: Path) -> list[dict]:
    """Write ctsa_registry.json, preserving hand-edited hub_name values."""
    path = Path(path)
    existing = {}
    if path.exists():
        try:
            for e in json.loads(path.read_text()):
                if e.get("hub_name"):
                    existing[e["ipf_code"]] = e["hub_name"]
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    entries = []
    rows = conn.execute(
        "SELECT ipf_code, org_name, slug, city, state, "
        "       first_funded_year, last_funded_year "
        "FROM sites WHERE is_ctsa_hub = 1 ORDER BY org_name"
    ).fetchall()
    for ipf, org, slug, city, state, first, last in rows:
        cores = [r[0] for r in conn.execute(
            "SELECT core_project_num FROM grants "
            "WHERE ipf_code=? AND is_hub_award=1 ORDER BY core_project_num", (ipf,))]
        entries.append({
            "ipf_code": ipf,
            "org_name": org,
            "slug": slug,
            "hub_name": existing.get(ipf, org.title()),
            "city": city,
            "state": state,
            "first_funded_year": first,
            "last_funded_year": last,
            "core_project_nums": cores,
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))
    return entries
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_site_registry.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Write `scripts/build_site_registry.py`**

```python
#!/usr/bin/env python3
"""Identify CTSA hub sites and write data/ctsa_registry.json."""

import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ncats.config import DATA_DIR
from src.ncats.schema import connect_ncats
from src.ncats.site_registry import mark_ctsa_hubs, export_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

if __name__ == "__main__":
    conn = connect_ncats()
    n_hubs = mark_ctsa_hubs(conn)
    entries = export_registry(conn, DATA_DIR / "ctsa_registry.json")
    log.info("CTSA hub sites: %d", n_hubs)
    log.info("Registry entries written: %d", len(entries))
    multi = [e for e in entries if len(e["core_project_nums"]) > 1]
    log.info("Hubs with multiple core projects (renewals): %d", len(multi))
    conn.close()
```

- [ ] **Step 6: Run it and record the true hub count**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/build_site_registry.py`
Expected: `CTSA hub sites: N` where N ≥ 66. This is the number the spec flagged as unverified — write it down and update the spec's caveat.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add src/ncats/site_registry.py scripts/build_site_registry.py tests/test_site_registry.py data/ctsa_registry.json
git commit -m "feat: build IPF-keyed CTSA site registry with renewal-chain merging"
```

---

### Task 5: Fetch grant→publication links

**Files:**
- Create: `~/Projects/IMPACT-NCATS/scripts/fetch_publications.py`
- Test: `~/Projects/IMPACT-NCATS/tests/test_fetch_publications.py`

**Interfaces:**
- Consumes: `ReporterClient.fetch_publications`, populated `grants` table.
- Produces: `fetch_publications.ingest_pubs_for_grant(conn, core_project_num, pmids) -> int` (new rows inserted); populated `grant_pubs` table.

- [ ] **Step 1: Write the failing test**

`tests/test_fetch_publications.py`:
```python
import sqlite3
import pytest
from src.ncats.schema import create_schema
from scripts.fetch_publications import ingest_pubs_for_grant


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    c.execute("INSERT INTO sites (ipf_code, org_name) VALUES (1,'X')")
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code) VALUES ('UL1TR000090',1,'UL1')")
    yield c
    c.close()


def test_inserts_links(conn):
    assert ingest_pubs_for_grant(conn, "UL1TR000090", [1, 2, 3]) == 3
    assert conn.execute("SELECT COUNT(*) FROM grant_pubs").fetchone()[0] == 3


def test_rerun_inserts_nothing_new(conn):
    ingest_pubs_for_grant(conn, "UL1TR000090", [1, 2, 3])
    assert ingest_pubs_for_grant(conn, "UL1TR000090", [1, 2, 3]) == 0
    assert conn.execute("SELECT COUNT(*) FROM grant_pubs").fetchone()[0] == 3


def test_partial_overlap_adds_only_new(conn):
    ingest_pubs_for_grant(conn, "UL1TR000090", [1, 2])
    assert ingest_pubs_for_grant(conn, "UL1TR000090", [2, 3]) == 1
    assert conn.execute("SELECT COUNT(*) FROM grant_pubs").fetchone()[0] == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_fetch_publications.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.fetch_publications'`

- [ ] **Step 3: Write `scripts/fetch_publications.py`**

```python
#!/usr/bin/env python3
"""Fetch RePORTER publication links for every NCATS grant.

Usage:
    python scripts/fetch_publications.py
    python scripts/fetch_publications.py --hubs-only
    python scripts/fetch_publications.py --resume
"""

import sys, os, argparse, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ncats.schema import connect_ncats
from src.ncats.reporter_client import ReporterClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def ingest_pubs_for_grant(conn, core_project_num: str, pmids: list[int]) -> int:
    """Insert grant→PMID links. Returns the number of NEW rows."""
    inserted = 0
    for pmid in pmids:
        cur = conn.execute(
            "INSERT OR IGNORE INTO grant_pubs (core_project_num, pmid) VALUES (?,?)",
            (core_project_num, pmid),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hubs-only", action="store_true",
                    help="Only fetch for UL1/UM1 hub awards")
    ap.add_argument("--resume", action="store_true",
                    help="Skip grants that already have links")
    args = ap.parse_args()

    conn = connect_ncats()
    q = "SELECT core_project_num FROM grants"
    where = []
    if args.hubs_only:
        where.append("is_hub_award = 1")
    if args.resume:
        where.append("core_project_num NOT IN (SELECT DISTINCT core_project_num FROM grant_pubs)")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY core_project_num"

    cores = [r[0] for r in conn.execute(q)]
    log.info("Fetching publications for %d grants", len(cores))

    client = ReporterClient()
    total_new = 0
    for i, core in enumerate(cores, 1):
        try:
            pmids = client.fetch_publications(core)
        except Exception as e:
            log.error("FAILED %s: %s", core, e)
            continue
        total_new += ingest_pubs_for_grant(conn, core, pmids)
        if i % 50 == 0:
            log.info("[%d/%d] %d new links so far", i, len(cores), total_new)

    log.info("DONE. New links: %d", total_new)
    log.info("Total links: %s",
             conn.execute("SELECT COUNT(*) FROM grant_pubs").fetchone()[0])
    log.info("Distinct PMIDs: %s",
             conn.execute("SELECT COUNT(DISTINCT pmid) FROM grant_pubs").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_fetch_publications.py -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Run hub publications first (fast, high value)**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/fetch_publications.py --hubs-only`
Expected: progress every 50 grants; final distinct-PMID count in the low hundreds of thousands.

- [ ] **Step 6: Run the full ingest**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/fetch_publications.py --resume`
Expected: covers the remaining non-hub grants; `--resume` makes this safely restartable if interrupted.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add scripts/fetch_publications.py tests/test_fetch_publications.py
git commit -m "feat: fetch grant-to-publication links from RePORTER"
```

---

### Task 6: Fetch iCite RCR

**Files:**
- Create: `~/Projects/IMPACT-NCATS/src/ncats/icite_client.py`
- Create: `~/Projects/IMPACT-NCATS/scripts/fetch_rcr.py`
- Test: `~/Projects/IMPACT-NCATS/tests/test_icite_client.py`

**Interfaces:**
- Consumes: distinct PMIDs from `grant_pubs`.
- Produces: `icite_client.IciteClient.fetch_rcr(pmids: list[int]) -> dict[int, float | None]`; `pub_metrics.rcr` populated.

- [ ] **Step 1: Write the failing test**

`tests/test_icite_client.py`:
```python
from unittest.mock import patch, MagicMock
from src.ncats.icite_client import IciteClient


def _resp(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


def test_chunks_at_200_pmids():
    pmids = list(range(1, 451))  # 450 -> 3 requests
    with patch("src.ncats.icite_client.requests.get",
               return_value=_resp({"data": []})) as g:
        IciteClient(rate_limit=1000).fetch_rcr(pmids)
    assert g.call_count == 3
    first = g.call_args_list[0].kwargs["params"]["pmids"]
    assert len(first.split(",")) == 200


def test_returns_rcr_by_pmid():
    payload = {"data": [
        {"pmid": 1, "relative_citation_ratio": 2.5},
        {"pmid": 2, "relative_citation_ratio": None},
    ]}
    with patch("src.ncats.icite_client.requests.get", return_value=_resp(payload)):
        out = IciteClient(rate_limit=1000).fetch_rcr([1, 2])
    assert out == {1: 2.5, 2: None}


def test_failed_batch_does_not_abort_run():
    import requests as rq
    with patch("src.ncats.icite_client.requests.get",
               side_effect=[rq.RequestException("boom"),
                            _resp({"data": [{"pmid": 300, "relative_citation_ratio": 1.1}]})]):
        out = IciteClient(rate_limit=1000).fetch_rcr(list(range(1, 201)) + [300])
    assert out == {300: 1.1}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_icite_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ncats.icite_client'`

- [ ] **Step 3: Write `src/ncats/icite_client.py`**

```python
"""Minimal iCite client for Relative Citation Ratio lookups."""

import time
import logging
import requests

from src.ncats.config import ICITE_BASE_URL, ICITE_RATE_LIMIT, ICITE_MAX_BATCH

logger = logging.getLogger(__name__)


class IciteClient:
    """Fetches RCR values. Batches at 200 PMIDs to avoid 414 errors."""

    def __init__(self, rate_limit: float = ICITE_RATE_LIMIT):
        self.min_interval = 1.0 / rate_limit
        self.last_request_time = 0.0

    def _wait(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def fetch_rcr(self, pmids: list[int]) -> dict:
        """Return {pmid: rcr_or_None}. A failed batch is logged and skipped."""
        out = {}
        for i in range(0, len(pmids), ICITE_MAX_BATCH):
            chunk = pmids[i: i + ICITE_MAX_BATCH]
            self._wait()
            try:
                resp = requests.get(
                    ICITE_BASE_URL,
                    params={"pmids": ",".join(str(p) for p in chunk),
                            "format": "json"},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                logger.error("iCite batch at offset %d failed: %s", i, e)
                continue
            for rec in data.get("data") or []:
                pmid = rec.get("pmid")
                if pmid is not None:
                    out[pmid] = rec.get("relative_citation_ratio")
        return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_icite_client.py -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Write `scripts/fetch_rcr.py`**

```python
#!/usr/bin/env python3
"""Populate pub_metrics.rcr from iCite for all grant-linked PMIDs.

Usage:
    python scripts/fetch_rcr.py
    python scripts/fetch_rcr.py --resume
"""

import sys, os, argparse, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ncats.schema import connect_ncats
from src.ncats.icite_client import IciteClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CHUNK = 2000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true",
                    help="Skip PMIDs already present in pub_metrics")
    args = ap.parse_args()

    conn = connect_ncats()
    q = "SELECT DISTINCT pmid FROM grant_pubs"
    if args.resume:
        q += " WHERE pmid NOT IN (SELECT pmid FROM pub_metrics)"
    pmids = [r[0] for r in conn.execute(q)]
    log.info("Fetching RCR for %d PMIDs", len(pmids))

    client = IciteClient()
    done = 0
    for i in range(0, len(pmids), CHUNK):
        batch = pmids[i: i + CHUNK]
        rcr_map = client.fetch_rcr(batch)
        conn.executemany(
            "INSERT INTO pub_metrics (pmid, rcr) VALUES (?,?) "
            "ON CONFLICT(pmid) DO UPDATE SET rcr=excluded.rcr",
            [(p, rcr_map.get(p)) for p in batch],
        )
        conn.commit()
        done += len(batch)
        log.info("[%d/%d] RCR rows written", done, len(pmids))

    log.info("PMIDs with a non-null RCR: %s",
             conn.execute("SELECT COUNT(*) FROM pub_metrics WHERE rcr IS NOT NULL").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run it**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/fetch_rcr.py`
Expected: progress every 2000 PMIDs; final non-null RCR count reported. RCR is undefined for very recent papers, so expect meaningfully fewer non-null values than total PMIDs.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add src/ncats/icite_client.py scripts/fetch_rcr.py tests/test_icite_client.py
git commit -m "feat: fetch iCite RCR for grant-linked publications"
```

---

### Task 7: Compute metrics by joining impact.db

**Files:**
- Create: `~/Projects/IMPACT-NCATS/src/ncats/metrics.py`
- Create: `~/Projects/IMPACT-NCATS/scripts/compute_ncats_metrics.py`
- Test: `~/Projects/IMPACT-NCATS/tests/test_metrics.py`

**Interfaces:**
- Consumes: `grant_pubs`, `grants`, `sites`, `pub_metrics.rcr`; read-only `impact.db`.
- Produces:
  - `metrics.activity_group(activity_code: str) -> str` — maps e.g. `R01`→`R`, `UL1`→`U`, `KL2`→`K`, `TL1`→`T`.
  - `metrics.compute_n_linked_hubs(conn) -> None`
  - `metrics.enrich_from_impact(conn, impact_conn, batch_size=5000) -> dict`
  - `metrics.compute_site_metrics(conn) -> int`

The key correctness rule: `n_linked_hubs` counts **distinct hub sites**, not distinct grants — two awards at one hub is one hub.

- [ ] **Step 1: Write the failing test**

`tests/test_metrics.py`:
```python
import sqlite3
import pytest
from src.ncats.schema import create_schema
from src.ncats.metrics import (
    activity_group, compute_n_linked_hubs, enrich_from_impact, compute_site_metrics,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    for ipf, name in [(1, "HUB A"), (2, "HUB B")]:
        c.execute("INSERT INTO sites (ipf_code, org_name, is_ctsa_hub) VALUES (?,?,1)", (ipf, name))
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code, is_hub_award, total_award_amount) VALUES ('UL1TR000001',1,'UL1',1,1000)")
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code, is_hub_award, total_award_amount) VALUES ('KL2TR000002',1,'KL2',0,500)")
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code, is_hub_award, total_award_amount) VALUES ('UL1TR000003',2,'UL1',1,2000)")
    c.execute("INSERT INTO grant_years (core_project_num, fiscal_year, project_num, award_amount) VALUES ('UL1TR000001',2020,'a',1000)")
    c.execute("INSERT INTO grant_years (core_project_num, fiscal_year, project_num, award_amount) VALUES ('UL1TR000003',2020,'c',2000)")
    yield c
    c.close()


@pytest.fixture
def impact_conn():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE journals (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE papers (pmid INTEGER PRIMARY KEY, journal_id INTEGER,
                             pub_year INTEGER, is_research INTEGER);
        CREATE TABLE citations (id INTEGER PRIMARY KEY, cited_pmid INTEGER,
                                citing_pmid INTEGER);
    """)
    c.execute("INSERT INTO journals VALUES (10,'Nature')")
    c.execute("INSERT INTO papers VALUES (100,10,2020,1)")
    c.execute("INSERT INTO papers VALUES (200,10,2020,1)")
    c.execute("INSERT INTO citations VALUES (1,100,901)")
    c.execute("INSERT INTO citations VALUES (2,100,902)")
    yield c
    c.close()


def test_activity_group():
    assert activity_group("R01") == "R"
    assert activity_group("UL1") == "U"
    assert activity_group("KL2") == "K"
    assert activity_group("TL1") == "T"
    assert activity_group("R44") == "R"
    assert activity_group(None) == "other"


def test_n_linked_hubs_counts_sites_not_grants(conn):
    # PMID 100 is linked to two grants at the SAME hub -> 1 hub
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',100)")
    conn.execute("INSERT INTO grant_pubs VALUES ('KL2TR000002',100)")
    # PMID 200 is linked to grants at TWO different hubs -> 2 hubs
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',200)")
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000003',200)")
    compute_n_linked_hubs(conn)
    got = dict(conn.execute("SELECT pmid, n_linked_hubs FROM pub_metrics"))
    assert got[100] == 1
    assert got[200] == 2


def test_enrich_marks_missing_pmids_as_not_in_impact_db(conn, impact_conn):
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',100)")
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',999)")  # absent
    compute_n_linked_hubs(conn)
    stats = enrich_from_impact(conn, impact_conn)
    rows = dict(conn.execute("SELECT pmid, in_impact_db FROM pub_metrics"))
    assert rows[100] == 1
    assert rows[999] == 0
    assert stats["matched"] == 1
    assert stats["total"] == 2


def test_enrich_pulls_citation_count_and_journal(conn, impact_conn):
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',100)")
    compute_n_linked_hubs(conn)
    enrich_from_impact(conn, impact_conn)
    cites, jname, yr = conn.execute(
        "SELECT citation_count, journal_name, pub_year FROM pub_metrics WHERE pmid=100"
    ).fetchone()
    assert cites == 2
    assert jname == "Nature"
    assert yr == 2020


def test_site_metrics_give_full_credit_to_each_hub(conn, impact_conn):
    # One shared paper, linked to a grant at each of two hubs.
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',100)")
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000003',100)")
    compute_n_linked_hubs(conn)
    enrich_from_impact(conn, impact_conn)
    compute_site_metrics(conn)
    counts = dict(conn.execute(
        "SELECT ipf_code, pub_count FROM site_metrics WHERE year=2020 AND activity_group='U'"))
    assert counts[1] == 1
    assert counts[2] == 1  # full credit to BOTH, not 0.5 each


def test_cost_per_pub_is_award_total_over_pubs(conn, impact_conn):
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',100)")
    compute_n_linked_hubs(conn)
    enrich_from_impact(conn, impact_conn)
    compute_site_metrics(conn)
    cost = conn.execute(
        "SELECT cost_per_pub FROM site_metrics "
        "WHERE ipf_code=1 AND year=2020 AND activity_group='U'").fetchone()[0]
    assert cost == 1000.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ncats.metrics'`

- [ ] **Step 3: Write `src/ncats/metrics.py`**

```python
"""Join grant data against impact.db and compute site-level metrics."""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def activity_group(activity_code: str) -> str:
    """Collapse an activity code to its NIH mechanism letter (R, K, U, T, F, P)."""
    if not activity_code:
        return "other"
    first = activity_code[0].upper()
    return first if first in {"R", "K", "U", "T", "F", "P"} else "other"


def compute_n_linked_hubs(conn: sqlite3.Connection) -> None:
    """Populate pub_metrics with every linked PMID and its distinct hub count.

    Counts distinct CTSA hub SITES, not grants: two awards at one hub is one hub.
    """
    conn.execute("""
        INSERT INTO pub_metrics (pmid, n_linked_hubs)
        SELECT gp.pmid,
               COUNT(DISTINCT CASE WHEN s.is_ctsa_hub = 1 THEN s.ipf_code END)
        FROM grant_pubs gp
        JOIN grants g ON g.core_project_num = gp.core_project_num
        JOIN sites  s ON s.ipf_code = g.ipf_code
        GROUP BY gp.pmid
        ON CONFLICT(pmid) DO UPDATE SET n_linked_hubs = excluded.n_linked_hubs
    """)
    conn.commit()


def enrich_from_impact(conn, impact_conn, batch_size: int = 5000) -> dict:
    """Pull journal, year, research flag, and citation count from impact.db.

    impact_conn is read-only. PMIDs absent from impact.db get in_impact_db = 0.
    """
    pmids = [r[0] for r in conn.execute("SELECT pmid FROM pub_metrics ORDER BY pmid")]
    stats = {"total": len(pmids), "matched": 0}

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i: i + batch_size]
        marks = ",".join("?" * len(batch))

        rows = impact_conn.execute(
            f"SELECT p.pmid, p.journal_id, j.name, p.pub_year, p.is_research, "
            f"       (SELECT COUNT(*) FROM citations c WHERE c.cited_pmid = p.pmid) "
            f"FROM papers p LEFT JOIN journals j ON j.id = p.journal_id "
            f"WHERE p.pmid IN ({marks})",
            batch,
        ).fetchall()

        conn.executemany(
            "UPDATE pub_metrics SET journal_id=?, journal_name=?, pub_year=?, "
            "  is_research=?, citation_count=?, in_impact_db=1 WHERE pmid=?",
            [(jid, jname, yr, isr, cites, pmid)
             for pmid, jid, jname, yr, isr, cites in rows],
        )
        stats["matched"] += len(rows)
        conn.commit()
        logger.info("enriched %d/%d", min(i + batch_size, len(pmids)), len(pmids))

    conn.execute("UPDATE pub_metrics SET in_impact_db=0 WHERE in_impact_db IS NULL")
    conn.commit()
    stats["match_rate"] = stats["matched"] / stats["total"] if stats["total"] else 0.0
    return stats


def compute_site_metrics(conn: sqlite3.Connection) -> int:
    """Aggregate publication metrics per (site, year, activity_group).

    Full credit: a paper shared across hubs counts once in EACH hub's totals.
    """
    conn.execute("DELETE FROM site_metrics")
    conn.execute("""
        INSERT INTO site_metrics (
            ipf_code, year, activity_group, pub_count, research_count,
            citation_count, mean_rcr, mean_journal_if, award_total)
        SELECT g.ipf_code,
               pm.pub_year,
               CASE WHEN SUBSTR(g.activity_code,1,1) IN ('R','K','U','T','F','P')
                    THEN SUBSTR(g.activity_code,1,1) ELSE 'other' END,
               COUNT(DISTINCT pm.pmid),
               COUNT(DISTINCT CASE WHEN pm.is_research=1 THEN pm.pmid END),
               SUM(pm.citation_count),
               AVG(pm.rcr),
               AVG(pm.journal_rolling_if),
               0
        FROM grant_pubs gp
        JOIN grants g   ON g.core_project_num = gp.core_project_num
        JOIN pub_metrics pm ON pm.pmid = gp.pmid
        WHERE pm.pub_year IS NOT NULL
        GROUP BY 1, 2, 3
    """)

    # Award dollars for the same (site, year, mechanism) slice.
    conn.execute("""
        UPDATE site_metrics SET award_total = COALESCE((
            SELECT SUM(gy.award_amount)
            FROM grant_years gy
            JOIN grants g2 ON g2.core_project_num = gy.core_project_num
            WHERE g2.ipf_code = site_metrics.ipf_code
              AND gy.fiscal_year = site_metrics.year
              AND (CASE WHEN SUBSTR(g2.activity_code,1,1) IN ('R','K','U','T','F','P')
                        THEN SUBSTR(g2.activity_code,1,1) ELSE 'other' END)
                  = site_metrics.activity_group
        ), 0)
    """)
    conn.execute("""
        UPDATE site_metrics
        SET cost_per_pub = CASE WHEN pub_count > 0
                                THEN award_total * 1.0 / pub_count END,
            cost_per_citation = CASE WHEN citation_count > 0
                                     THEN award_total * 1.0 / citation_count END
    """)
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM site_metrics").fetchone()[0]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_metrics.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Write `scripts/compute_ncats_metrics.py`**

```python
#!/usr/bin/env python3
"""Join ncats.db against impact.db and compute all metrics."""

import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ncats.schema import connect_ncats, connect_impact_readonly
from src.ncats.metrics import (
    compute_n_linked_hubs, enrich_from_impact, compute_site_metrics,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

if __name__ == "__main__":
    conn = connect_ncats()
    impact = connect_impact_readonly()

    log.info("Computing hub linkage counts...")
    compute_n_linked_hubs(conn)

    log.info("Enriching from impact.db...")
    stats = enrich_from_impact(conn, impact)
    log.info("PMIDs: %d | matched in impact.db: %d (%.1f%%)",
             stats["total"], stats["matched"], stats["match_rate"] * 100)

    log.info("Computing site metrics...")
    n = compute_site_metrics(conn)
    log.info("site_metrics rows: %d", n)

    shared = conn.execute(
        "SELECT COUNT(*) FROM pub_metrics WHERE n_linked_hubs > 1").fetchone()[0]
    log.info("Publications shared across >1 hub: %d", shared)

    impact.close()
    conn.close()
```

- [ ] **Step 6: Run it against the real databases**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/compute_ncats_metrics.py`
Expected: a match rate near **95.8%** (the sampled figure). A match rate below 95% means something is wrong with the join — investigate before continuing.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add src/ncats/metrics.py scripts/compute_ncats_metrics.py tests/test_metrics.py
git commit -m "feat: compute publication metrics by joining impact.db"
```

---

### Task 8: Export static JSON

**Files:**
- Create: `~/Projects/IMPACT-NCATS/src/ncats/json_exporter.py`
- Create: `~/Projects/IMPACT-NCATS/scripts/export_ncats_json.py`
- Test: `~/Projects/IMPACT-NCATS/tests/test_json_exporter.py`

**Interfaces:**
- Consumes: fully populated `ncats.db`.
- Produces: `json_exporter.export_index(conn, out_dir) -> Path`, `json_exporter.export_sites(conn, out_dir) -> int`, `json_exporter.export_investigators(conn, out_dir) -> int`. Writes `docs/data/index.json`, `docs/data/sites/<slug>.json`, `docs/data/investigators/<profile_id>.json`.

- [ ] **Step 1: Write the failing test**

`tests/test_json_exporter.py`:
```python
import json
import sqlite3
import pytest
from src.ncats.schema import create_schema
from src.ncats.json_exporter import export_index, export_sites


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    c.execute("INSERT INTO sites (ipf_code, org_name, slug, hub_name, city, state, is_ctsa_hub, first_funded_year, last_funded_year) "
              "VALUES (1,'HUB A','hub-a','Hub A CTSI','BOSTON','MA',1,2012,2025)")
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code, title, is_hub_award, total_award_amount, first_fy, last_fy) "
              "VALUES ('UL1TR000001',1,'UL1','Award',1,1000,2012,2025)")
    c.execute("INSERT INTO site_metrics (ipf_code, year, activity_group, pub_count, research_count, citation_count, mean_rcr, award_total, cost_per_pub) "
              "VALUES (1,2020,'U',10,8,100,1.5,1000,100.0)")
    yield c
    c.close()


def test_index_lists_only_hub_sites(conn, tmp_path):
    conn.execute("INSERT INTO sites (ipf_code, org_name, slug, is_ctsa_hub) VALUES (2,'SMALL CO','small-co',0)")
    path = export_index(conn, tmp_path)
    data = json.loads(path.read_text())
    slugs = [s["slug"] for s in data["sites"]]
    assert slugs == ["hub-a"]
    assert data["total_grants"] == 1


def test_site_file_has_metrics_by_year(conn, tmp_path):
    assert export_sites(conn, tmp_path) == 1
    data = json.loads((tmp_path / "sites" / "hub-a.json").read_text())
    assert data["hub_name"] == "Hub A CTSI"
    assert data["metrics"][0]["year"] == 2020
    assert data["metrics"][0]["pub_count"] == 10
    assert data["grants"][0]["core_project_num"] == "UL1TR000001"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_json_exporter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ncats.json_exporter'`

- [ ] **Step 3: Write `src/ncats/json_exporter.py`**

```python
"""Export ncats.db to static JSON for the frontend."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _write(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return path


def export_index(conn, out_dir) -> Path:
    """Top-level index: hub site list plus portfolio-wide totals."""
    out_dir = Path(out_dir)
    sites = [
        {"ipf_code": r[0], "slug": r[1], "hub_name": r[2], "org_name": r[3],
         "city": r[4], "state": r[5],
         "first_funded_year": r[6], "last_funded_year": r[7]}
        for r in conn.execute(
            "SELECT ipf_code, slug, hub_name, org_name, city, state, "
            "       first_funded_year, last_funded_year "
            "FROM sites WHERE is_ctsa_hub=1 ORDER BY hub_name")
    ]
    payload = {
        "sites": sites,
        "total_sites": len(sites),
        "total_grants": conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0],
        "total_publications": conn.execute(
            "SELECT COUNT(DISTINCT pmid) FROM grant_pubs").fetchone()[0],
        "total_award_amount": conn.execute(
            "SELECT COALESCE(SUM(total_award_amount),0) FROM grants").fetchone()[0],
    }
    return _write(out_dir / "index.json", payload)


def export_sites(conn, out_dir) -> int:
    """One JSON file per CTSA hub site."""
    out_dir = Path(out_dir)
    n = 0
    for ipf, slug, hub_name, org, city, state in conn.execute(
        "SELECT ipf_code, slug, hub_name, org_name, city, state "
        "FROM sites WHERE is_ctsa_hub=1"
    ).fetchall():
        metrics = [
            {"year": r[0], "activity_group": r[1], "pub_count": r[2],
             "research_count": r[3], "citation_count": r[4], "mean_rcr": r[5],
             "mean_journal_if": r[6], "award_total": r[7],
             "cost_per_pub": r[8], "cost_per_citation": r[9]}
            for r in conn.execute(
                "SELECT year, activity_group, pub_count, research_count, "
                "       citation_count, mean_rcr, mean_journal_if, award_total, "
                "       cost_per_pub, cost_per_citation "
                "FROM site_metrics WHERE ipf_code=? ORDER BY year, activity_group",
                (ipf,))
        ]
        grants = [
            {"core_project_num": r[0], "activity_code": r[1], "title": r[2],
             "first_fy": r[3], "last_fy": r[4], "total_award_amount": r[5],
             "is_hub_award": r[6]}
            for r in conn.execute(
                "SELECT core_project_num, activity_code, title, first_fy, last_fy, "
                "       total_award_amount, is_hub_award "
                "FROM grants WHERE ipf_code=? ORDER BY activity_code, core_project_num",
                (ipf,))
        ]
        _write(out_dir / "sites" / f"{slug}.json", {
            "ipf_code": ipf, "slug": slug, "hub_name": hub_name,
            "org_name": org, "city": city, "state": state,
            "metrics": metrics, "grants": grants,
        })
        n += 1
    return n


def export_investigators(conn, out_dir) -> int:
    """One JSON file per PI, listing their grants and publication totals."""
    out_dir = Path(out_dir)
    n = 0
    for pid, name in conn.execute(
        "SELECT profile_id, full_name FROM investigators"
    ).fetchall():
        grants = [
            {"core_project_num": r[0], "activity_code": r[1], "title": r[2],
             "total_award_amount": r[3], "is_contact_pi": r[4]}
            for r in conn.execute(
                "SELECT g.core_project_num, g.activity_code, g.title, "
                "       g.total_award_amount, gp.is_contact_pi "
                "FROM grant_pis gp JOIN grants g "
                "  ON g.core_project_num = gp.core_project_num "
                "WHERE gp.profile_id=?", (pid,))
        ]
        pub_count, cites = conn.execute(
            "SELECT COUNT(DISTINCT pm.pmid), COALESCE(SUM(pm.citation_count),0) "
            "FROM grant_pis gp "
            "JOIN grant_pubs gpub ON gpub.core_project_num = gp.core_project_num "
            "JOIN pub_metrics pm ON pm.pmid = gpub.pmid "
            "WHERE gp.profile_id=?", (pid,)).fetchone()
        _write(out_dir / "investigators" / f"{pid}.json", {
            "profile_id": pid, "full_name": name, "grants": grants,
            "pub_count": pub_count, "citation_count": cites,
        })
        n += 1
    return n
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_json_exporter.py -v`
Expected: PASS — 2 passed

- [ ] **Step 5: Write `scripts/export_ncats_json.py`**

```python
#!/usr/bin/env python3
"""Export ncats.db to docs/data/ as static JSON."""

import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ncats.config import WEBSITE_DATA_DIR
from src.ncats.schema import connect_ncats
from src.ncats.json_exporter import export_index, export_sites, export_investigators

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

if __name__ == "__main__":
    conn = connect_ncats()
    log.info("index.json -> %s", export_index(conn, WEBSITE_DATA_DIR))
    log.info("site files: %d", export_sites(conn, WEBSITE_DATA_DIR))
    log.info("investigator files: %d", export_investigators(conn, WEBSITE_DATA_DIR))
    conn.close()
```

- [ ] **Step 6: Run it and inspect the output**

Run:
```bash
cd ~/Projects/IMPACT-NCATS && python scripts/export_ncats_json.py
python -c "
import json
d=json.load(open('docs/data/index.json'))
print('sites:',d['total_sites'],'grants:',d['total_grants'],'pubs:',d['total_publications'])
print('\$total:',f\"{d['total_award_amount']:,.0f}\")
print('first site:',d['sites'][0]['hub_name'])
"
```
Expected: hub-site count ≥66, grant count in the thousands, publication count in the hundreds of thousands, and a plausible dollar total.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add src/ncats/json_exporter.py scripts/export_ncats_json.py tests/test_json_exporter.py
git commit -m "feat: export ncats.db to static JSON"
```

---

### Task 9: Validation, methods doc, and R2 upload

**Files:**
- Create: `~/Projects/IMPACT-NCATS/scripts/validate_ncats.py`
- Create: `~/Projects/IMPACT-NCATS/scripts/upload_to_r2.py`
- Create: `~/Projects/IMPACT-NCATS/METHODS_ncats.md`
- Create: `~/Projects/IMPACT-NCATS/README.md`
- Test: `~/Projects/IMPACT-NCATS/tests/test_validate.py`

**Interfaces:**
- Consumes: fully populated `ncats.db`.
- Produces: `validate_ncats.run_checks(conn) -> list[tuple[str, bool, str]]` — `(check_name, passed, detail)`. Exit code 1 if any check fails.

- [ ] **Step 1: Write the failing test**

`tests/test_validate.py`:
```python
import sqlite3
import pytest
from src.ncats.schema import create_schema
from scripts.validate_ncats import run_checks


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    c.execute("INSERT INTO sites (ipf_code, org_name, slug, is_ctsa_hub) VALUES (1,'A','a',1)")
    c.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code, is_hub_award) VALUES ('UL1TR000001',1,'UL1',1)")
    c.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',100)")
    c.execute("INSERT INTO pub_metrics (pmid, in_impact_db, n_linked_hubs) VALUES (100,1,1)")
    yield c
    c.close()


def _result(results, name):
    return [r for r in results if r[0] == name][0]


def test_all_checks_pass_on_clean_db(conn):
    results = run_checks(conn)
    assert all(passed for _, passed, _ in results), results


def test_low_match_rate_fails(conn):
    conn.execute("INSERT INTO grant_pubs VALUES ('UL1TR000001',200)")
    conn.execute("INSERT INTO pub_metrics (pmid, in_impact_db, n_linked_hubs) VALUES (200,0,1)")
    # 1 of 2 matched = 50%, below the 95% floor
    assert _result(run_checks(conn), "impact_db_match_rate")[1] is False


def test_orphan_grant_pub_fails(conn):
    conn.execute("INSERT INTO grant_pubs VALUES ('NOSUCHGRANT',300)")
    assert _result(run_checks(conn), "no_orphan_grant_pubs")[1] is False


def test_grant_with_missing_site_fails(conn):
    conn.execute("INSERT INTO grants (core_project_num, ipf_code, activity_code) VALUES ('R01TR000009',999,'R01')")
    assert _result(run_checks(conn), "no_orphan_grants")[1] is False


def test_hub_without_slug_fails(conn):
    conn.execute("UPDATE sites SET slug=NULL WHERE ipf_code=1")
    assert _result(run_checks(conn), "all_hubs_have_slug")[1] is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.validate_ncats'`

- [ ] **Step 3: Write `scripts/validate_ncats.py`**

```python
#!/usr/bin/env python3
"""Validate ncats.db integrity. Exit code 1 if any check fails."""

import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ncats.schema import connect_ncats

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

MATCH_RATE_FLOOR = 0.95


def run_checks(conn) -> list[tuple[str, bool, str]]:
    """Return [(check_name, passed, detail)]."""
    results = []
    q = lambda sql: conn.execute(sql).fetchone()[0]

    total = q("SELECT COUNT(*) FROM pub_metrics")
    matched = q("SELECT COUNT(*) FROM pub_metrics WHERE in_impact_db=1")
    rate = matched / total if total else 0.0
    results.append((
        "impact_db_match_rate",
        rate >= MATCH_RATE_FLOOR,
        f"{matched}/{total} = {rate:.1%} (floor {MATCH_RATE_FLOOR:.0%})",
    ))

    orphan_pubs = q(
        "SELECT COUNT(*) FROM grant_pubs WHERE core_project_num NOT IN "
        "(SELECT core_project_num FROM grants)")
    results.append(("no_orphan_grant_pubs", orphan_pubs == 0,
                    f"{orphan_pubs} links to unknown grants"))

    orphan_grants = q(
        "SELECT COUNT(*) FROM grants WHERE ipf_code NOT IN "
        "(SELECT ipf_code FROM sites)")
    results.append(("no_orphan_grants", orphan_grants == 0,
                    f"{orphan_grants} grants with unknown site"))

    no_slug = q("SELECT COUNT(*) FROM sites WHERE is_ctsa_hub=1 AND (slug IS NULL OR slug='')")
    results.append(("all_hubs_have_slug", no_slug == 0,
                    f"{no_slug} hubs missing a slug"))

    dup_slug = q(
        "SELECT COUNT(*) FROM (SELECT slug FROM sites WHERE is_ctsa_hub=1 "
        "GROUP BY slug HAVING COUNT(*)>1)")
    results.append(("hub_slugs_unique", dup_slug == 0,
                    f"{dup_slug} duplicated hub slugs"))

    bad_hub_count = q(
        "SELECT COUNT(*) FROM pub_metrics WHERE n_linked_hubs < 0")
    results.append(("n_linked_hubs_sane", bad_hub_count == 0,
                    f"{bad_hub_count} negative hub counts"))

    return results


if __name__ == "__main__":
    conn = connect_ncats()
    results = run_checks(conn)
    failed = 0
    for name, passed, detail in results:
        log.info("%-24s %-6s %s", name, "PASS" if passed else "FAIL", detail)
        failed += 0 if passed else 1
    conn.close()
    if failed:
        log.error("%d check(s) failed", failed)
        sys.exit(1)
    log.info("All checks passed.")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/test_validate.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Run validation against the real database**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/validate_ncats.py`
Expected: all checks PASS, with `impact_db_match_rate` near 95.8%.

- [ ] **Step 6: Write `scripts/upload_to_r2.py`**

Copy IMPACT's uploader and retarget it at the `ncats/` prefix:

```bash
cd ~/Projects/IMPACT-NCATS
cp ~/Projects/IMPACT/scripts/upload_to_r2.py scripts/upload_to_r2.py
```

Then change its import block from `src.pipeline.config` to `src.ncats.config`, and prefix every object key with `R2_PREFIX`. The key-building line becomes:

```python
from src.ncats.config import (
    R2_ACCOUNT_ID, R2_BUCKET_NAME, R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY, R2_PUBLIC_URL, R2_PREFIX, WEBSITE_DATA_DIR,
)

# When computing the destination key for a local file:
key = f"{R2_PREFIX}/{local_path.relative_to(WEBSITE_DATA_DIR).as_posix()}"
```

- [ ] **Step 7: Dry-run the upload**

Run: `cd ~/Projects/IMPACT-NCATS && python scripts/upload_to_r2.py --dry-run`
Expected: a list of `ncats/...`-prefixed keys that would be written. **Confirm every key starts with `ncats/`** before running a real upload — a missing prefix would overwrite IMPACT's live data.

- [ ] **Step 8: Write `METHODS_ncats.md`**

Document, in prose, each item from the spec's "Documented limitations" section:

1. Grant→publication linkage depends on authors citing their grant; counts are a floor, not a census.
2. FY2012 floor — the 2006–2011 NCRR era of the CTSA program is excluded, so early hub output is absent and trend lines must not be read as program inception.
3. Investigator attribution is grant-linkage only: it credits hub PIs broadly and misses their non-NCATS work.
4. Shared publications receive full credit at each hub, so per-site sums exceed the de-duplicated consortium total.
5. Roughly 4% of grant-linked PMIDs are absent from `impact.db` and are excluded from journal-quality metrics.

Include the measured match rate and hub count from the real run.

- [ ] **Step 9: Write `README.md`**

Cover: what IMPACT-NCATS is, its relationship to IMPACT and IMPACT-gender, data sources (RePORTER, iCite, impact.db), setup (`pip install -r requirements.txt`, copy `.env.example` to `.env`), and the pipeline run order:

```bash
python scripts/fetch_grants.py
python scripts/build_site_registry.py
python scripts/fetch_publications.py
python scripts/fetch_rcr.py
python scripts/compute_ncats_metrics.py
python scripts/export_ncats_json.py
python scripts/validate_ncats.py
python scripts/upload_to_r2.py
```

- [ ] **Step 10: Run the full test suite**

Run: `cd ~/Projects/IMPACT-NCATS && python -m pytest tests/ -v`
Expected: PASS — 28 tests passed across all 7 test files.

- [ ] **Step 11: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add scripts/validate_ncats.py scripts/upload_to_r2.py tests/test_validate.py METHODS_ncats.md README.md
git commit -m "feat: add validation, R2 upload, and project documentation"
```

---

## Deferred: publishing

Creating the GitHub repository and enabling GitHub Pages are outward-facing actions **and are deliberately not steps in this plan**. Confirm with the user first, specifically:

- repository visibility (public, matching IMPACT and IMPACT-gender, or private to start)
- whether R2 uploads should go to the existing `impact-data` bucket under the `ncats/` prefix or to a new bucket

Only then run `gh repo create` and configure Pages.

## Deferred: frontend

The SPA (Sites / Grants / Investigators / Compare / About) is a separate plan, written once this pipeline has produced real JSON to design against.

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Repo scaffold, sibling pattern | 1 |
| `ncats.db` schema (8 tables) | 1 |
| NCATS FY2012–present, all activity codes | 2, 3 |
| IPF-keyed site identity | 3, 4 |
| `ctsa_registry.json`, renewal merging | 4 |
| Resolve the unverified hub count | 3 (step 6), 4 (step 6) |
| Grant→PMID linkage | 5 |
| iCite RCR | 6 |
| Join to `impact.db`, ≥95% match | 7, 9 |
| Full-credit double counting + `n_linked_hubs` | 7 |
| Cost per publication / citation | 7 |
| Static JSON export | 8 |
| Validation checks | 9 |
| `METHODS_ncats.md` limitations | 9 |
| R2 upload under `ncats/` prefix | 9 |
| Frontend SPA | Deferred — separate plan |

**Gap accepted:** `pub_metrics.journal_rolling_if` has a column and is averaged into `site_metrics.mean_journal_if`, but nothing populates it — `monthly_snapshots` needs a snapshot-month choice per paper that the spec does not pin down. `AVG` over all-NULL yields NULL, so this degrades cleanly rather than producing wrong numbers. Resolve the snapshot-selection rule with the user, then add it as Task 10.

**Placeholder scan:** no TBDs; every code step carries complete code; every command has an expected result.

**Type consistency:** verified `activity_group`, `compute_n_linked_hubs`, `enrich_from_impact`, `compute_site_metrics`, `mark_ctsa_hubs`, `export_registry`, `ingest_projects`, `ingest_pubs_for_grant`, `run_checks`, and `fetch_rcr` are named identically at definition and every call site. Column names in the schema match every query that references them.
