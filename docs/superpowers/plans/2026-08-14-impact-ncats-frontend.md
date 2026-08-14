# IMPACT-NCATS Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A vanilla-JS SPA for IMPACT-NCATS that renders the CTSA grant/publication data produced by the data-layer plan, following the IMPACT site's existing patterns closely enough that the two feel like one family.

**Architecture:** Static `docs/` directory served by GitHub Pages, no build step. An `NCATSApp` controller class mirrors IMPACT's `IMPACTApp`: hash-based nav, `showSection()`, per-section setup methods. A `DataLoader` fetches static JSON from Cloudflare R2 in production and local `data/` in dev, exactly as IMPACT does. Chart.js renders every chart via a `ChartManager` sharing IMPACT's Okabe-Ito palette.

**Tech Stack:** Vanilla JS (ES2020, no framework, no bundler), Chart.js 4.4.0 and jsPDF 2.5.1 from CDN, CSS custom properties. Matches IMPACT exactly.

**Prerequisite:** The data-layer pipeline must have produced `docs/data/index.json` and `docs/data/sites/*.json`. Task 1 can proceed without them; Tasks 3+ need real files.

## Global Constraints

- **No build step and no framework.** Edit HTML/CSS/JS directly in `docs/`, matching IMPACT.
- **Naming:** JS camelCase methods/variables, PascalCase classes, UPPER_SNAKE_CASE constants. CSS kebab-case classes. HTML IDs kebab-case.
- **Palette:** reuse IMPACT's colorblind-safe Okabe-Ito array verbatim (see Task 2). Never introduce ad-hoc chart colors.
- **CSS custom properties** copied from IMPACT's `:root` block so the two sites share a visual identity.
- **Section pattern:** `<section id="x" class="section">`, nav `<a class="nav-link" data-section="x">`, `.active` toggled by `showSection()`.
- **Every dollar figure** formatted with thousands separators; every metric that can be null must render as `—`, never `null` or `NaN`.
- **Every chart** gets a download bar (PNG / JPG / PDF / CSV), matching IMPACT's `.download-bar` pattern.
- **Methods honesty:** the About section must surface the `METHODS_ncats.md` limitations, especially full-credit double counting and the FY2012 floor. Numbers must not be presented as a census.
- Commit style: conventional commits, **no `Co-Authored-By` line**.

## Verification approach

IMPACT has no JS test framework (`tests/` holds only Python tests), so this plan does not invent one. Each task is verified by serving `docs/` locally and confirming (a) the rendered result matches the described behavior and (b) **the browser console is free of errors**. Every task's verification step states both.

```bash
python -m http.server -d ~/Projects/IMPACT-NCATS/docs 8000
```

## File Structure

| File | Responsibility |
|---|---|
| `docs/index.html` | Shell: header, nav, five section containers, CDN script tags |
| `docs/css/style.css` | All styling; `:root` tokens copied from IMPACT |
| `docs/js/data-loader.js` | R2-vs-local routing, fetch + in-memory cache |
| `docs/js/site-picker.js` | `SitePicker` (multi-select) and `SingleSitePicker`, adapted from IMPACT's journal pickers |
| `docs/js/chart-manager.js` | Palette, Chart.js construction, download helpers |
| `docs/js/app.js` | `NCATSApp` controller, one setup method per section |

Six files, each with one clear job — mirroring IMPACT's split so the codebases stay legible side by side.

---

### Task 1: Shell, styles, and navigation

**Files:**
- Create: `docs/index.html`
- Create: `docs/css/style.css`
- Create: `docs/js/app.js`

**Interfaces:**
- Consumes: nothing.
- Produces: `NCATSApp` class with `setupNavigation()` and `showSection(sectionId)`; five empty sections with IDs `sites`, `grants`, `investigators`, `compare`, `about`.

- [ ] **Step 1: Copy IMPACT's stylesheet as the baseline**

```bash
cp ~/Projects/IMPACT/docs/css/style.css ~/Projects/IMPACT-NCATS/docs/css/style.css
```

This inherits the `:root` tokens, header gradient, nav, `.section`, `.chart-container`, `.download-bar`, `.toggle-group`, and table styling. Do not restyle — the goal is family resemblance.

- [ ] **Step 2: Write `docs/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IMPACT-NCATS — Publication Impact of the NCATS Portfolio</title>
    <link rel="stylesheet" href="css/style.css?v=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
</head>
<body>

<header>
    <div class="header-content">
        <h1>IMPACT-NCATS</h1>
        <p class="subtitle">Publication impact of the NCATS grant portfolio, by CTSA site, investigator, and grant</p>
    </div>
    <nav>
        <a href="#sites" class="nav-link active" data-section="sites">Sites</a>
        <a href="#grants" class="nav-link" data-section="grants">Grants</a>
        <a href="#investigators" class="nav-link" data-section="investigators">Investigators</a>
        <a href="#compare" class="nav-link" data-section="compare">Compare</a>
        <a href="#about" class="nav-link" data-section="about">About</a>
    </nav>
</header>

<main>
    <section id="sites" class="section active">
        <h2>CTSA Sites</h2>
        <p class="data-note" id="sites-summary">Loading…</p>
        <div id="sites-table-container"></div>
        <div id="site-detail" class="detail-panel" style="display:none;"></div>
    </section>

    <section id="grants" class="section">
        <h2>Grants</h2>
        <div id="grants-controls"></div>
        <div id="grants-table-container"></div>
    </section>

    <section id="investigators" class="section">
        <h2>Investigators</h2>
        <input type="text" id="investigator-search" placeholder="Search by name…" autocomplete="off">
        <div id="investigator-results"></div>
        <div id="investigator-detail" class="detail-panel" style="display:none;"></div>
    </section>

    <section id="compare" class="section">
        <h2>Compare Sites</h2>
        <div id="compare-picker"></div>
        <div id="compare-controls"></div>
        <div class="chart-container" id="compare-chart-container" style="display:none;">
            <canvas id="compare-chart"></canvas>
        </div>
        <p id="compare-hint" class="data-note">Select one or more sites to compare.</p>
    </section>

    <section id="about" class="section">
        <h2>About</h2>
        <div id="about-content"></div>
    </section>
</main>

<script src="js/data-loader.js?v=1"></script>
<script src="js/site-picker.js?v=1"></script>
<script src="js/chart-manager.js?v=1"></script>
<script src="js/app.js?v=1"></script>
</body>
</html>
```

- [ ] **Step 3: Write the navigation core of `docs/js/app.js`**

```javascript
/**
 * IMPACT-NCATS — main controller.
 * Mirrors IMPACT's IMPACTApp: hash nav, showSection, per-section setup.
 */

class NCATSApp {
    constructor() {
        this.loader = new DataLoader();
        this.index = null;
        this.siteCache = {};
        this.init();
    }

    async init() {
        this.setupNavigation();
        try {
            this.index = await this.loader.loadIndex();
        } catch (e) {
            document.getElementById('sites-summary').textContent =
                'Could not load data. If running locally, make sure docs/data/index.json exists.';
            console.error('Failed to load index.json', e);
            return;
        }
        this.renderSitesSummary();
    }

    setupNavigation() {
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.showSection(link.dataset.section);
            });
        });
        const initial = location.hash.replace('#', '') || 'sites';
        this.showSection(initial);
    }

    showSection(sectionId) {
        document.querySelectorAll('.section').forEach(s =>
            s.classList.toggle('active', s.id === sectionId));
        document.querySelectorAll('.nav-link').forEach(l =>
            l.classList.toggle('active', l.dataset.section === sectionId));
        history.replaceState(null, '', `#${sectionId}`);
    }

    renderSitesSummary() {
        const d = this.index;
        document.getElementById('sites-summary').textContent =
            `${d.total_sites} CTSA sites · ${d.total_grants.toLocaleString()} NCATS grants · ` +
            `${d.total_publications.toLocaleString()} linked publications · ` +
            `$${Math.round(d.total_award_amount).toLocaleString()} awarded`;
    }
}

document.addEventListener('DOMContentLoaded', () => { window.app = new NCATSApp(); });
```

- [ ] **Step 4: Verify in the browser**

Run: `python -m http.server -d ~/Projects/IMPACT-NCATS/docs 8000`, open `http://localhost:8000`.
Expected: header and five nav tabs render; clicking each tab swaps the visible section and updates the URL hash; **console shows no errors** (a failed `index.json` fetch is expected at this point and must surface as the friendly message, not an uncaught exception).

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add docs/index.html docs/css/style.css docs/js/app.js
git commit -m "feat: add SPA shell, styles, and section navigation"
```

---

### Task 2: Data loader, palette, and chart manager

**Files:**
- Create: `docs/js/data-loader.js`
- Create: `docs/js/chart-manager.js`

**Interfaces:**
- Consumes: static JSON produced by the data-layer pipeline.
- Produces:
  - `DataLoader.loadIndex() -> Promise<object>`, `loadSite(slug)`, `loadInvestigator(profileId)`
  - `ChartManager.PALETTE: string[]`
  - `ChartManager.lineChart(canvasId, labels, datasets, opts) -> Chart`
  - `ChartManager.barChart(canvasId, labels, datasets, opts) -> Chart`
  - `ChartManager.download(chart, format, filename) -> void`

- [ ] **Step 1: Write `docs/js/data-loader.js`**

The R2 base URL is IMPACT's bucket; NCATS data lives under the `ncats/` prefix written by `upload_to_r2.py`.

```javascript
/**
 * IMPACT-NCATS Data Loader
 * Fetches JSON from Cloudflare R2 (production) or local data/ (dev).
 */

const R2_BASE_URL = 'https://pub-4368cf00a45748488f64d2b648550d4d.r2.dev/ncats';

class DataLoader {
    constructor() {
        const isLocal = location.hostname === 'localhost' ||
                        location.hostname === '127.0.0.1' ||
                        location.protocol === 'file:';
        this.baseUrl = isLocal ? 'data' : R2_BASE_URL;
        this.cache = {};
    }

    async loadIndex() {
        return this._fetch(`${this.baseUrl}/index.json`);
    }

    async loadSite(slug) {
        return this._fetch(`${this.baseUrl}/sites/${slug}.json`);
    }

    async loadInvestigator(profileId) {
        return this._fetch(`${this.baseUrl}/investigators/${profileId}.json`);
    }

    async _fetch(url) {
        if (this.cache[url]) return this.cache[url];
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`Failed to load ${url}: ${resp.status}`);
        const data = await resp.json();
        this.cache[url] = data;
        return data;
    }
}
```

- [ ] **Step 2: Write `docs/js/chart-manager.js`**

The palette is copied verbatim from IMPACT's `chart-manager.js` — colorblind-safe Okabe-Ito, with yellow and black swapped for purple and gray for legibility on white.

```javascript
/**
 * IMPACT-NCATS Chart Manager
 * Chart.js construction and download helpers.
 */

class ChartManager {
    // Okabe-Ito colorblind-safe palette (matches IMPACT).
    static PALETTE = [
        '#0072B2', // 1 blue
        '#D55E00', // 2 vermilion
        '#009E73', // 3 bluish green
        '#56B4E9', // 4 sky blue
        '#E69F00', // 5 orange/amber
        '#CC79A7', // 6 reddish purple
        '#7B2D8B', // 7 purple
        '#7f7f7f', // 8 gray
        '#44AA99', // 9 teal
        '#AA4499', // 10 mauve
    ];

    static color(i) {
        return ChartManager.PALETTE[i % ChartManager.PALETTE.length];
    }

    static _destroy(canvasId) {
        const existing = Chart.getChart(canvasId);
        if (existing) existing.destroy();
    }

    static lineChart(canvasId, labels, datasets, opts = {}) {
        ChartManager._destroy(canvasId);
        return new Chart(document.getElementById(canvasId), {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'nearest', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 14 } },
                    tooltip: { enabled: true },
                },
                scales: {
                    y: { beginAtZero: true, title: { display: !!opts.yLabel, text: opts.yLabel } },
                    x: { title: { display: !!opts.xLabel, text: opts.xLabel } },
                },
                ...opts.chartOptions,
            },
        });
    }

    static barChart(canvasId, labels, datasets, opts = {}) {
        ChartManager._destroy(canvasId);
        return new Chart(document.getElementById(canvasId), {
            type: 'bar',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { boxWidth: 14 } } },
                scales: {
                    y: { beginAtZero: true, stacked: !!opts.stacked,
                         title: { display: !!opts.yLabel, text: opts.yLabel } },
                    x: { stacked: !!opts.stacked },
                },
                ...opts.chartOptions,
            },
        });
    }

    static download(chart, format, filename) {
        if (format === 'png' || format === 'jpg') {
            const mime = format === 'png' ? 'image/png' : 'image/jpeg';
            const a = document.createElement('a');
            a.href = chart.canvas.toDataURL(mime, 1.0);
            a.download = `${filename}.${format}`;
            a.click();
            return;
        }
        if (format === 'pdf') {
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({ orientation: 'landscape' });
            pdf.addImage(chart.canvas.toDataURL('image/png', 1.0), 'PNG', 10, 10, 275, 150);
            pdf.save(`${filename}.pdf`);
        }
    }

    static downloadCSV(rows, filename) {
        const csv = rows.map(r => r.map(c => {
            const s = c === null || c === undefined ? '' : String(c);
            return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        }).join(',')).join('\n');
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
        a.download = `${filename}.csv`;
        a.click();
    }
}

/** Format a possibly-null metric for display. Never shows "null" or "NaN". */
function fmt(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    return Number(value).toFixed(digits);
}

/** Format a dollar amount with thousands separators. */
function fmtMoney(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    return `$${Math.round(value).toLocaleString()}`;
}
```

- [ ] **Step 3: Verify the loader against real data**

Run the local server, then in the browser console:
```javascript
new DataLoader().loadIndex().then(d => console.log(d.total_sites, d.sites[0]));
```
Expected: the site count (72 at time of writing) and a site object with `slug`, `hub_name`, `state`. **No console errors.**

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add docs/js/data-loader.js docs/js/chart-manager.js
git commit -m "feat: add data loader and chart manager with Okabe-Ito palette"
```

---

### Task 3: Sites section — leaderboard and detail

**Files:**
- Modify: `docs/js/app.js` (add `setupSites`, `renderSitesTable`, `showSiteDetail`, `_siteTotals`)

**Interfaces:**
- Consumes: `DataLoader.loadIndex`, `DataLoader.loadSite`, `ChartManager`.
- Produces: `NCATSApp.showSiteDetail(slug)` — renders a hub's trend chart and grant list; `NCATSApp._siteTotals(siteData)` returning `{pubCount, citationCount, meanRcr, awardTotal}` aggregated across all years.

The leaderboard is the landing view, so it must be sortable and must state the double-counting caveat inline rather than burying it in About.

- [ ] **Step 1: Add the sites table to `app.js`**

```javascript
    async setupSites() {
        const sites = this.index.sites;
        // Load every site file once so the leaderboard can show real totals.
        const loaded = await Promise.all(
            sites.map(s => this.loader.loadSite(s.slug).catch(() => null))
        );
        this.siteSummaries = sites.map((s, i) => {
            const data = loaded[i];
            if (data) this.siteCache[s.slug] = data;
            return { ...s, ...this._siteTotals(data) };
        });
        this.sitesSort = { key: 'pubCount', dir: 'desc' };
        this.renderSitesTable();
    }

    _siteTotals(siteData) {
        if (!siteData) return { pubCount: 0, citationCount: 0, meanRcr: null, awardTotal: 0 };
        let pubCount = 0, citationCount = 0, awardTotal = 0;
        let rcrSum = 0, rcrN = 0;
        for (const m of siteData.metrics) {
            pubCount += m.pub_count || 0;
            citationCount += m.citation_count || 0;
            awardTotal += m.award_total || 0;
            if (m.mean_rcr !== null && m.mean_rcr !== undefined) {
                rcrSum += m.mean_rcr * (m.pub_count || 0);
                rcrN += m.pub_count || 0;
            }
        }
        return {
            pubCount, citationCount, awardTotal,
            meanRcr: rcrN > 0 ? rcrSum / rcrN : null,
        };
    }

    renderSitesTable() {
        const { key, dir } = this.sitesSort;
        const rows = [...this.siteSummaries].sort((a, b) => {
            const av = a[key], bv = b[key];
            if (typeof av === 'string') return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
            return dir === 'asc' ? (av ?? 0) - (bv ?? 0) : (bv ?? 0) - (av ?? 0);
        });

        const cols = [
            ['hub_name', 'Site'], ['state', 'State'],
            ['pubCount', 'Publications'], ['citationCount', 'Citations'],
            ['meanRcr', 'Mean RCR'], ['awardTotal', 'Awarded'],
        ];

        const html = `
            <p class="data-note">
                A publication linked to grants at several hubs is counted in full at each one,
                so this column sums to more than the ${this.index.total_publications.toLocaleString()}
                unique publications in the portfolio. See <a href="#about">About</a>.
            </p>
            <table class="data-table">
                <thead><tr>${cols.map(([k, label]) =>
                    `<th class="sortable" data-key="${k}">${label}${key === k ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>`
                ).join('')}</tr></thead>
                <tbody>${rows.map(r => `
                    <tr class="site-row" data-slug="${r.slug}">
                        <td><a href="#" class="site-link">${r.hub_name}</a></td>
                        <td>${r.state || '—'}</td>
                        <td>${r.pubCount.toLocaleString()}</td>
                        <td>${r.citationCount.toLocaleString()}</td>
                        <td>${fmt(r.meanRcr)}</td>
                        <td>${fmtMoney(r.awardTotal)}</td>
                    </tr>`).join('')}
                </tbody>
            </table>`;

        const container = document.getElementById('sites-table-container');
        container.innerHTML = html;

        container.querySelectorAll('th.sortable').forEach(th => {
            th.addEventListener('click', () => {
                const k = th.dataset.key;
                this.sitesSort = { key: k, dir: this.sitesSort.key === k && this.sitesSort.dir === 'desc' ? 'asc' : 'desc' };
                this.renderSitesTable();
            });
        });
        container.querySelectorAll('.site-row').forEach(tr => {
            tr.addEventListener('click', (e) => {
                e.preventDefault();
                this.showSiteDetail(tr.dataset.slug);
            });
        });
    }
```

- [ ] **Step 2: Add the site detail view**

```javascript
    async showSiteDetail(slug) {
        const data = this.siteCache[slug] || await this.loader.loadSite(slug);
        this.siteCache[slug] = data;

        const years = [...new Set(data.metrics.map(m => m.year))].sort();
        const groups = [...new Set(data.metrics.map(m => m.activity_group))].sort();

        const datasets = groups.map((g, i) => ({
            label: `${g} awards`,
            data: years.map(y => {
                const row = data.metrics.find(m => m.year === y && m.activity_group === g);
                return row ? row.pub_count : 0;
            }),
            backgroundColor: ChartManager.color(i),
            borderColor: ChartManager.color(i),
        }));

        const totals = this._siteTotals(data);
        const panel = document.getElementById('site-detail');
        panel.style.display = 'block';
        panel.innerHTML = `
            <h3>${data.hub_name}</h3>
            <p class="data-note">${data.org_name} · ${data.city || ''} ${data.state || ''}</p>
            <div class="metric-row">
                <div class="metric"><span class="metric-value">${totals.pubCount.toLocaleString()}</span><span class="metric-label">Publications</span></div>
                <div class="metric"><span class="metric-value">${totals.citationCount.toLocaleString()}</span><span class="metric-label">Citations</span></div>
                <div class="metric"><span class="metric-value">${fmt(totals.meanRcr)}</span><span class="metric-label">Mean RCR</span></div>
                <div class="metric"><span class="metric-value">${fmtMoney(totals.awardTotal)}</span><span class="metric-label">Awarded</span></div>
            </div>
            <div class="chart-container"><canvas id="site-detail-chart"></canvas></div>
            <div class="download-bar">
                <span>Download:</span>
                <button class="download-btn" data-fmt="png">PNG</button>
                <button class="download-btn" data-fmt="jpg">JPG</button>
                <button class="download-btn" data-fmt="pdf">PDF</button>
                <button class="download-btn" data-fmt="csv">CSV data</button>
            </div>
            <h4>Grants (${data.grants.length})</h4>
            <table class="data-table">
                <thead><tr><th>Core project</th><th>Activity</th><th>Title</th><th>Years</th><th>Awarded</th></tr></thead>
                <tbody>${data.grants.map(g => `
                    <tr>
                        <td><a href="https://reporter.nih.gov/search/?projectNums=${g.core_project_num}" target="_blank" rel="noopener">${g.core_project_num}</a></td>
                        <td>${g.activity_code || '—'}</td>
                        <td>${g.title || '—'}</td>
                        <td>${g.first_fy}–${g.last_fy}</td>
                        <td>${fmtMoney(g.total_award_amount)}</td>
                    </tr>`).join('')}
                </tbody>
            </table>`;

        const chart = ChartManager.barChart('site-detail-chart', years, datasets,
            { stacked: true, yLabel: 'Publications' });

        panel.querySelectorAll('.download-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const f = btn.dataset.fmt;
                if (f === 'csv') {
                    ChartManager.downloadCSV(
                        [['year', 'activity_group', 'pub_count', 'citation_count', 'mean_rcr', 'award_total'],
                         ...data.metrics.map(m => [m.year, m.activity_group, m.pub_count, m.citation_count, m.mean_rcr, m.award_total])],
                        `${slug}-metrics`);
                } else {
                    ChartManager.download(chart, f, `${slug}-publications`);
                }
            });
        });
        panel.scrollIntoView({ behavior: 'smooth' });
    }
```

- [ ] **Step 3: Call `setupSites()` from `init()`**

In `init()`, replace the `this.renderSitesSummary();` line with:

```javascript
        this.renderSitesSummary();
        await this.setupSites();
```

- [ ] **Step 4: Add the table and metric styles to `docs/css/style.css`**

```css
/* ---- Data tables ---- */
.data-table { width: 100%; border-collapse: collapse; background: var(--surface);
              border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }
.data-table th, .data-table td { padding: 0.6rem 0.8rem; text-align: left;
                                 border-bottom: 1px solid var(--border); font-size: 0.9rem; }
.data-table th { background: var(--primary); color: #fff; font-weight: 600; }
.data-table th.sortable { cursor: pointer; user-select: none; }
.data-table th.sortable:hover { background: var(--primary-light); }
.data-table tbody tr:hover { background: #f1f6fa; }
.site-row { cursor: pointer; }

/* ---- Metric tiles ---- */
.metric-row { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }
.metric { background: var(--surface); border-radius: var(--radius); padding: 0.8rem 1.2rem;
          box-shadow: var(--shadow); min-width: 130px; }
.metric-value { display: block; font-size: 1.5rem; font-weight: 700; color: var(--primary); }
.metric-label { display: block; font-size: 0.8rem; color: var(--text-light); }
```

- [ ] **Step 5: Verify in the browser**

Reload `http://localhost:8000`.
Expected: the leaderboard lists all sites sorted by publications descending; clicking a column header re-sorts; clicking a row opens the detail panel with a stacked bar chart by mechanism, four metric tiles, and the grant table; the double-counting note is visible above the table; **console shows no errors**.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add docs/js/app.js docs/css/style.css
git commit -m "feat: add sites leaderboard and per-site detail view"
```

---

### Task 4: Grants section

**Files:**
- Modify: `docs/js/app.js` (add `setupGrants`, `renderGrantsTable`)

**Interfaces:**
- Consumes: `this.siteCache` populated by Task 3 (every site file holds its grants).
- Produces: `NCATSApp.renderGrantsTable()` filtered by activity group, fiscal year, and free-text search.

- [ ] **Step 1: Add the grants section**

```javascript
    setupGrants() {
        // Every grant already arrived with its site file in setupSites().
        this.allGrants = [];
        for (const [slug, data] of Object.entries(this.siteCache)) {
            for (const g of data.grants) {
                this.allGrants.push({ ...g, site_slug: slug, hub_name: data.hub_name, state: data.state });
            }
        }

        const groups = [...new Set(this.allGrants.map(g => (g.activity_code || '?')[0]))].sort();
        document.getElementById('grants-controls').innerHTML = `
            <div class="controls-row">
                <input type="text" id="grants-search" placeholder="Search title, project number, or site…">
                <select id="grants-group">
                    <option value="">All mechanisms</option>
                    ${groups.map(g => `<option value="${g}">${g} awards</option>`).join('')}
                </select>
                <label><input type="checkbox" id="grants-hubs-only"> Hub awards only</label>
            </div>
            <p class="data-note" id="grants-count"></p>`;

        ['grants-search', 'grants-group', 'grants-hubs-only'].forEach(id =>
            document.getElementById(id).addEventListener('input', () => this.renderGrantsTable()));

        this.renderGrantsTable();
    }

    renderGrantsTable() {
        const term = document.getElementById('grants-search').value.toLowerCase().trim();
        const group = document.getElementById('grants-group').value;
        const hubsOnly = document.getElementById('grants-hubs-only').checked;

        const rows = this.allGrants.filter(g => {
            if (hubsOnly && !g.is_hub_award) return false;
            if (group && (g.activity_code || '?')[0] !== group) return false;
            if (term) {
                const hay = `${g.core_project_num} ${g.title || ''} ${g.hub_name}`.toLowerCase();
                if (!hay.includes(term)) return false;
            }
            return true;
        }).sort((a, b) => (b.total_award_amount || 0) - (a.total_award_amount || 0));

        document.getElementById('grants-count').textContent =
            `${rows.length.toLocaleString()} of ${this.allGrants.length.toLocaleString()} grants`;

        document.getElementById('grants-table-container').innerHTML = `
            <table class="data-table">
                <thead><tr><th>Core project</th><th>Activity</th><th>Site</th><th>Title</th><th>Years</th><th>Awarded</th></tr></thead>
                <tbody>${rows.slice(0, 500).map(g => `
                    <tr>
                        <td><a href="https://reporter.nih.gov/search/?projectNums=${g.core_project_num}" target="_blank" rel="noopener">${g.core_project_num}</a></td>
                        <td>${g.activity_code || '—'}</td>
                        <td>${g.hub_name}</td>
                        <td>${g.title || '—'}</td>
                        <td>${g.first_fy}–${g.last_fy}</td>
                        <td>${fmtMoney(g.total_award_amount)}</td>
                    </tr>`).join('')}
                </tbody>
            </table>
            ${rows.length > 500 ? '<p class="data-note">Showing the 500 largest awards. Narrow the search to see more.</p>' : ''}`;
    }
```

- [ ] **Step 2: Call `setupGrants()` after `setupSites()` in `init()`**

```javascript
        await this.setupSites();
        this.setupGrants();
```

- [ ] **Step 3: Add control-row styles to `docs/css/style.css`**

```css
.controls-row { display: flex; gap: 0.8rem; align-items: center; flex-wrap: wrap; margin-bottom: 0.8rem; }
.controls-row input[type="text"], .controls-row select {
    padding: 0.5rem 0.7rem; border: 1px solid var(--border);
    border-radius: var(--radius); font-size: 0.9rem; }
.controls-row input[type="text"] { flex: 1; min-width: 220px; }
```

- [ ] **Step 4: Verify in the browser**

Open the Grants tab.
Expected: the count line reports the full grant total; typing filters live; the mechanism dropdown and hub-only checkbox both narrow results; project numbers link to RePORTER; **console shows no errors**.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add docs/js/app.js docs/css/style.css
git commit -m "feat: add filterable grants browser"
```

---

### Task 5: Investigators section

**Files:**
- Modify: `docs/js/app.js` (add `setupInvestigators`, `renderInvestigatorResults`, `showInvestigatorDetail`)
- Modify: `docs/index.html` (add the investigator index note)

**Interfaces:**
- Consumes: `DataLoader.loadInvestigator(profileId)`; investigator names from grant PI data.
- Produces: `NCATSApp.showInvestigatorDetail(profileId)`.

Because `index.json` does not carry an investigator list, this task adds one to the exporter first — a small data-layer change that belongs with the feature that needs it.

- [ ] **Step 1: Add an investigator index to the exporter**

In `~/Projects/IMPACT-NCATS/src/ncats/json_exporter.py`, inside `export_index`, add before `payload`:

```python
    investigators = [
        {"profile_id": r[0], "full_name": r[1], "n_grants": r[2]}
        for r in conn.execute(
            "SELECT i.profile_id, i.full_name, COUNT(gp.core_project_num) "
            "FROM investigators i "
            "JOIN grant_pis gp ON gp.profile_id = i.profile_id "
            "GROUP BY i.profile_id, i.full_name "
            "ORDER BY i.full_name")
    ]
```

and add `"investigators": investigators,` to the `payload` dict.

- [ ] **Step 2: Re-run the export and confirm the new key**

```bash
cd ~/Projects/IMPACT-NCATS && python scripts/export_ncats_json.py
python -c "import json; d=json.load(open('docs/data/index.json')); print(len(d['investigators']), d['investigators'][0])"
```
Expected: the investigator count (1,771 at time of writing) and a sample record.

- [ ] **Step 3: Add the investigator section to `app.js`**

```javascript
    setupInvestigators() {
        const input = document.getElementById('investigator-search');
        input.addEventListener('input', () => this.renderInvestigatorResults());
        this.renderInvestigatorResults();
    }

    renderInvestigatorResults() {
        const term = document.getElementById('investigator-search').value.toLowerCase().trim();
        const all = this.index.investigators || [];
        const rows = term
            ? all.filter(i => (i.full_name || '').toLowerCase().includes(term)).slice(0, 100)
            : [];

        const container = document.getElementById('investigator-results');
        if (!term) {
            container.innerHTML = `<p class="data-note">${all.length.toLocaleString()} investigators hold NCATS awards. Type a name to search.</p>`;
            return;
        }
        if (!rows.length) {
            container.innerHTML = '<p class="data-note">No investigators match that name.</p>';
            return;
        }
        container.innerHTML = `
            <table class="data-table">
                <thead><tr><th>Name</th><th>Grants</th></tr></thead>
                <tbody>${rows.map(i => `
                    <tr class="pi-row" data-pid="${i.profile_id}">
                        <td><a href="#" class="pi-link">${i.full_name || '(unnamed)'}</a></td>
                        <td>${i.n_grants}</td>
                    </tr>`).join('')}
                </tbody>
            </table>`;
        container.querySelectorAll('.pi-row').forEach(tr =>
            tr.addEventListener('click', (e) => {
                e.preventDefault();
                this.showInvestigatorDetail(tr.dataset.pid);
            }));
    }

    async showInvestigatorDetail(profileId) {
        let data;
        try {
            data = await this.loader.loadInvestigator(profileId);
        } catch (e) {
            console.error('Failed to load investigator', profileId, e);
            return;
        }
        const panel = document.getElementById('investigator-detail');
        panel.style.display = 'block';
        panel.innerHTML = `
            <h3>${data.full_name || '(unnamed)'}</h3>
            <p class="data-note">
                Publications are those linked to this investigator's NCATS grants.
                Work published outside those awards is not included.
                See <a href="#about">About</a>.
            </p>
            <div class="metric-row">
                <div class="metric"><span class="metric-value">${data.grants.length}</span><span class="metric-label">Grants</span></div>
                <div class="metric"><span class="metric-value">${data.pub_count.toLocaleString()}</span><span class="metric-label">Publications</span></div>
                <div class="metric"><span class="metric-value">${data.citation_count.toLocaleString()}</span><span class="metric-label">Citations</span></div>
            </div>
            <table class="data-table">
                <thead><tr><th>Core project</th><th>Activity</th><th>Title</th><th>Awarded</th><th>Role</th></tr></thead>
                <tbody>${data.grants.map(g => `
                    <tr>
                        <td><a href="https://reporter.nih.gov/search/?projectNums=${g.core_project_num}" target="_blank" rel="noopener">${g.core_project_num}</a></td>
                        <td>${g.activity_code || '—'}</td>
                        <td>${g.title || '—'}</td>
                        <td>${fmtMoney(g.total_award_amount)}</td>
                        <td>${g.is_contact_pi ? 'Contact PI' : 'PI'}</td>
                    </tr>`).join('')}
                </tbody>
            </table>`;
        panel.scrollIntoView({ behavior: 'smooth' });
    }
```

- [ ] **Step 4: Call `setupInvestigators()` in `init()`**

```javascript
        this.setupGrants();
        this.setupInvestigators();
```

- [ ] **Step 5: Verify in the browser**

Open the Investigators tab, type a surname present in the data.
Expected: matches appear as you type; clicking one loads their grant list and metric tiles; the attribution caveat is visible; **console shows no errors**.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add docs/js/app.js src/ncats/json_exporter.py
git commit -m "feat: add investigator search and detail view"
```

---

### Task 6: Compare section

**Files:**
- Create: `docs/js/site-picker.js`
- Modify: `docs/js/app.js` (add `setupCompare`, `renderCompareChart`)

**Interfaces:**
- Consumes: `this.siteCache`, `ChartManager`.
- Produces: `SitePicker(containerId, sites, palette, onChange)` with `getSelected() -> string[]` (slugs) and `getColorMap() -> {slug: color}`; `NCATSApp.renderCompareChart()`.

- [ ] **Step 1: Write `docs/js/site-picker.js`**

Adapted from IMPACT's `JournalPicker`: a searchable multi-select with colored chips.

```javascript
/**
 * SitePicker — searchable multi-select for CTSA sites.
 * Adapted from IMPACT's JournalPicker.
 */

class SitePicker {
    constructor(containerId, sites, palette, onChange) {
        this.container = document.getElementById(containerId);
        this.sites = sites;
        this.palette = palette;
        this.onChange = onChange;
        this.selected = [];
        this.render();
    }

    render() {
        this.container.innerHTML = `
            <div class="picker">
                <input type="text" class="picker-input" placeholder="Search sites…" autocomplete="off">
                <div class="picker-results" style="display:none;"></div>
                <div class="picker-chips"></div>
            </div>`;
        this.input = this.container.querySelector('.picker-input');
        this.results = this.container.querySelector('.picker-results');
        this.chips = this.container.querySelector('.picker-chips');

        this.input.addEventListener('input', () => this._renderResults());
        this.input.addEventListener('focus', () => this._renderResults());
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) this.results.style.display = 'none';
        });
        this._renderChips();
    }

    _renderResults() {
        const term = this.input.value.toLowerCase().trim();
        const matches = this.sites
            .filter(s => !this.selected.includes(s.slug))
            .filter(s => !term || s.hub_name.toLowerCase().includes(term)
                                || (s.state || '').toLowerCase() === term)
            .slice(0, 25);

        if (!matches.length) { this.results.style.display = 'none'; return; }
        this.results.innerHTML = matches.map(s =>
            `<div class="picker-option" data-slug="${s.slug}">${s.hub_name}
                <span class="picker-meta">${s.state || ''}</span></div>`).join('');
        this.results.style.display = 'block';
        this.results.querySelectorAll('.picker-option').forEach(el =>
            el.addEventListener('click', () => {
                this.selected.push(el.dataset.slug);
                this.input.value = '';
                this.results.style.display = 'none';
                this._renderChips();
                this.onChange();
            }));
    }

    _renderChips() {
        const map = this.getColorMap();
        this.chips.innerHTML = this.selected.map(slug => {
            const site = this.sites.find(s => s.slug === slug);
            return `<span class="picker-chip" style="background:${map[slug]}">
                        ${site ? site.hub_name : slug}
                        <button class="chip-remove" data-slug="${slug}">×</button>
                    </span>`;
        }).join('');
        this.chips.querySelectorAll('.chip-remove').forEach(btn =>
            btn.addEventListener('click', () => {
                this.selected = this.selected.filter(s => s !== btn.dataset.slug);
                this._renderChips();
                this.onChange();
            }));
    }

    getColorMap() {
        const map = {};
        this.selected.forEach((slug, i) => { map[slug] = this.palette[i % this.palette.length]; });
        return map;
    }

    getSelected() { return [...this.selected]; }
}
```

- [ ] **Step 2: Add picker styles to `docs/css/style.css`**

```css
.picker { position: relative; margin-bottom: 0.8rem; }
.picker-input { width: 100%; padding: 0.5rem 0.7rem; border: 1px solid var(--border);
                border-radius: var(--radius); font-size: 0.9rem; }
.picker-results { position: absolute; z-index: 20; width: 100%; max-height: 260px;
                  overflow-y: auto; background: var(--surface); border: 1px solid var(--border);
                  border-radius: var(--radius); box-shadow: var(--shadow-hover); }
.picker-option { padding: 0.5rem 0.7rem; cursor: pointer; font-size: 0.9rem; }
.picker-option:hover { background: #f1f6fa; }
.picker-meta { color: var(--text-light); font-size: 0.8rem; margin-left: 0.4rem; }
.picker-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }
.picker-chip { color: #fff; padding: 0.25rem 0.5rem; border-radius: 999px;
               font-size: 0.8rem; display: inline-flex; align-items: center; gap: 0.3rem; }
.chip-remove { background: none; border: none; color: #fff; cursor: pointer;
               font-size: 1rem; line-height: 1; padding: 0; }
```

- [ ] **Step 3: Add the compare logic to `app.js`**

```javascript
    setupCompare() {
        document.getElementById('compare-controls').innerHTML = `
            <div class="controls-row">
                <label>Metric:
                    <select id="compare-metric">
                        <option value="pub_count">Publications</option>
                        <option value="citation_count">Citations</option>
                        <option value="mean_rcr">Mean RCR</option>
                        <option value="award_total">Award dollars</option>
                        <option value="cost_per_pub">Cost per publication</option>
                    </select>
                </label>
            </div>`;
        document.getElementById('compare-metric')
            .addEventListener('change', () => this.renderCompareChart());

        this.comparePicker = new SitePicker(
            'compare-picker', this.index.sites, ChartManager.PALETTE,
            () => this.renderCompareChart());
    }

    async renderCompareChart() {
        const slugs = this.comparePicker.getSelected();
        const container = document.getElementById('compare-chart-container');
        const hint = document.getElementById('compare-hint');

        if (!slugs.length) {
            container.style.display = 'none';
            hint.style.display = 'block';
            return;
        }
        hint.style.display = 'none';
        container.style.display = 'block';

        const metric = document.getElementById('compare-metric').value;
        const colorMap = this.comparePicker.getColorMap();

        const loaded = {};
        for (const slug of slugs) {
            loaded[slug] = this.siteCache[slug] || await this.loader.loadSite(slug);
            this.siteCache[slug] = loaded[slug];
        }

        // Union of years across the selected sites, summed over mechanisms.
        const years = [...new Set(
            slugs.flatMap(s => loaded[s].metrics.map(m => m.year))
        )].sort();

        const datasets = slugs.map(slug => {
            const site = loaded[slug];
            return {
                label: site.hub_name,
                data: years.map(y => {
                    const rows = site.metrics.filter(m => m.year === y);
                    if (!rows.length) return null;
                    if (metric === 'mean_rcr' || metric === 'cost_per_pub') {
                        // Weighted mean by publication count, so a tiny mechanism
                        // cannot swing the site's value.
                        let num = 0, den = 0;
                        for (const r of rows) {
                            if (r[metric] === null || r[metric] === undefined) continue;
                            num += r[metric] * (r.pub_count || 0);
                            den += r.pub_count || 0;
                        }
                        return den > 0 ? num / den : null;
                    }
                    return rows.reduce((sum, r) => sum + (r[metric] || 0), 0);
                }),
                borderColor: colorMap[slug],
                backgroundColor: colorMap[slug],
                spanGaps: true,
            };
        });

        ChartManager.lineChart('compare-chart', years, datasets,
            { xLabel: 'Year', yLabel: document.getElementById('compare-metric').selectedOptions[0].text });
    }
```

- [ ] **Step 4: Call `setupCompare()` in `init()` and load the picker script**

Add to `init()`:
```javascript
        this.setupInvestigators();
        this.setupCompare();
```

`site-picker.js` is already referenced in `index.html` from Task 1.

- [ ] **Step 5: Verify in the browser**

Open the Compare tab, add three sites.
Expected: each site gets a distinct palette color matching its chip; switching the metric redraws; RCR and cost-per-pub use weighted means rather than naive averages; removing a chip removes its line; **console shows no errors**.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add docs/js/site-picker.js docs/js/app.js docs/css/style.css
git commit -m "feat: add site comparison with multi-select picker"
```

---

### Task 7: About section and final polish

**Files:**
- Modify: `docs/js/app.js` (add `renderAbout`)

**Interfaces:**
- Consumes: `this.index`.
- Produces: `NCATSApp.renderAbout()`.

The About section is not filler. It is where the project's honesty lives, and it must state the limitations plainly enough that a reader cannot mistake these counts for a census.

- [ ] **Step 1: Add `renderAbout()` to `app.js`**

```javascript
    renderAbout() {
        const d = this.index;
        document.getElementById('about-content').innerHTML = `
            <p>
                IMPACT-NCATS measures the publication output of the NIH National Center for
                Advancing Translational Sciences portfolio — ${d.total_grants.toLocaleString()}
                awards totalling ${fmtMoney(d.total_award_amount)} across
                ${d.total_sites} CTSA sites, linked to
                ${d.total_publications.toLocaleString()} publications.
            </p>

            <h3>Where the data comes from</h3>
            <ul>
                <li><strong>NIH RePORTER</strong> — awards FY2012 onward: activity code, organization, investigators, dollars.</li>
                <li><strong>RePORTER publications</strong> — the grant-to-publication linkage.</li>
                <li><strong>iCite</strong> — Relative Citation Ratio.</li>
                <li><strong>IMPACT</strong> — journals, citation events, and article types for 24.9M papers.</li>
            </ul>

            <h3>What these numbers do not mean</h3>
            <ol>
                <li>
                    <strong>Publication counts are a floor, not a census.</strong> RePORTER knows about a
                    paper only if it was reported against the award. Hubs differ in how diligently they
                    report, so cross-site comparisons partly measure reporting practice.
                </li>
                <li>
                    <strong>The timeline starts at FY2012.</strong> NCATS was created in December 2011.
                    The CTSA program itself began in 2006 under NCRR. A hub funded since 2006 will appear
                    to start in 2012 — the left edge of a trend line is not program inception.
                </li>
                <li>
                    <strong>Shared papers are counted in full at every hub.</strong> A multi-site paper
                    linked to three hubs counts once for each. Per-site totals therefore sum to more than
                    the ${d.total_publications.toLocaleString()} unique publications shown above.
                </li>
                <li>
                    <strong>Investigator publications come from grant linkage only.</strong> No author-name
                    matching is performed, so a hub's contact PI is credited with the hub's entire linked
                    output, and work published outside NCATS awards is absent.
                </li>
                <li>
                    <strong>Cost per publication is a blunt instrument.</strong> Publications lag funding by
                    years, and infrastructure and training awards fund cores and people rather than papers
                    directly. A high cost per publication is not evidence of waste.
                </li>
            </ol>

            <p class="data-note">
                Full methodology: <a href="https://github.com/dantyrr/IMPACT-NCATS/blob/main/METHODS_ncats.md"
                target="_blank" rel="noopener">METHODS_ncats.md</a>.
                Related: <a href="https://dantyrr.github.io/IMPACT">IMPACT</a> ·
                <a href="https://dantyrr.github.io/IMPACT-gender">IMPACT-gender</a>.
            </p>`;
    }
```

- [ ] **Step 2: Call `renderAbout()` in `init()`**

```javascript
        this.setupCompare();
        this.renderAbout();
```

- [ ] **Step 3: Verify every section end to end**

Reload and walk all five tabs, including a hard refresh on a deep link such as `http://localhost:8000/#compare`.
Expected: every tab renders; deep links open the right section; no metric anywhere displays `null`, `NaN`, or `undefined`; **console is free of errors across all five sections**.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/IMPACT-NCATS
git add docs/js/app.js
git commit -m "feat: add About section with data sources and limitations"
```

---

## Deferred: publishing

GitHub Pages does not serve private repositories on the free tier. Publishing to
`dantyrr.github.io/IMPACT-NCATS` requires either making the repo public or a paid plan —
**this is the user's decision and is not a step in this plan.** Until then, the site is
reviewed locally with `python -m http.server -d docs 8000`.

When the user chooses to publish:

```bash
gh api -X POST repos/dantyrr/IMPACT-NCATS/pages -f source[branch]=main -f source[path]=/docs
```

R2 data must also be uploaded (`python scripts/upload_to_r2.py`) before the deployed site can
load anything, since production reads from R2 rather than the repo.

## Deferred: rolling impact factor

`mean_journal_if` is exported but is currently always null, because attributing a rolling IF
to a paper requires choosing which `monthly_snapshots` month to use — a decision the design
spec never settled. The UI handles this correctly today: `fmt()` renders null as `—`, and the
Compare metric dropdown deliberately omits it. **Once the snapshot rule is decided, add
`mean_journal_if` as a sixth Compare option and a column in the site detail table.**

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Sites section — leaderboard, per-hub detail | 3 |
| Grants section — browse/filter by activity code | 4 |
| Investigators section — PI search → grants, publications | 5 |
| Compare section — overlay hubs on any metric | 6 |
| About/Methods section | 7 |
| Chart.js, Okabe-Ito palette, no build step | 2 |
| Download bars (PNG/JPG/PDF/CSV) | 2, 3 |
| ~700-line app.js matching IMPACT-gender's scale | Tasks 1–7 total ≈ 600 lines |

**Deviations from the spec, stated openly:**

1. **No US choropleth map.** The spec's Sites section mentioned one. IMPACT's map machinery is
   substantial and the state field alone supports only a coarse view. Sites carry `state`, so a
   map remains straightforward to add later — but it is not in this plan, and pretending
   otherwise would misrepresent the scope.
2. **Grants data is derived from site files** rather than a separate `grants.json`. This avoids a
   second export path, but it means the Grants tab shows only grants at CTSA hub sites —
   non-hub NCATS awards (roughly 380 organizations) are in the database but not in this view.
   Adding them needs a `grants.json` export; flagged rather than silently omitted.
3. **Task 5 modifies the exporter.** Investigator search needs a name index that `index.json`
   does not yet carry. The change is small and ships with the feature that requires it.

**Placeholder scan:** no TBDs; every code step carries complete code; every verification step
states both the expected rendering and the no-console-errors condition.

**Type consistency:** verified `loadIndex`/`loadSite`/`loadInvestigator`, `ChartManager.PALETTE`,
`color`, `lineChart`, `barChart`, `download`, `downloadCSV`, `fmt`, `fmtMoney`,
`SitePicker.getSelected`/`getColorMap`, and `NCATSApp.showSection`/`_siteTotals` are named
identically at definition and every call site. JSON keys (`hub_name`, `pub_count`,
`citation_count`, `mean_rcr`, `award_total`, `cost_per_pub`, `activity_group`, `total_award_amount`)
match `json_exporter.py` exactly.
