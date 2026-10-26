/**
 * IMPACT Geography tab: where a journal's authors are, compared with another
 * journal or with all journals, and which regions collaborate.
 *
 * Data: geo/{slug}.json and geo/_all.json from scripts/export_geography.py.
 * Counts are per publication year: papers (citable items with a located
 * affiliation), papers involving each country or US state, fractional credit,
 * and co-occurring pairs.
 */

const WORLD_TOPO_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json';
const US_STATES_URL = 'geo/us-states.json';

// Parser country name -> world-atlas name, where they differ.
const ATLAS_NAMES = {
    'USA': 'United States of America', 'Antigua and Barbuda': 'Antigua and Barb.',
    'Bosnia and Herzegovina': 'Bosnia and Herz.', 'Cayman Islands': 'Cayman Is.',
    'Central African Republic': 'Central African Rep.', "Cote d'Ivoire": "Côte d'Ivoire",
    'Curacao': 'Curaçao', 'Czech Republic': 'Czechia', 'Democratic Republic of the Congo': 'Dem. Rep. Congo',
    'Dominican Republic': 'Dominican Rep.', 'Equatorial Guinea': 'Eq. Guinea', 'Eswatini': 'eSwatini',
    'Faroe Islands': 'Faeroe Is.', 'French Polynesia': 'Fr. Polynesia', 'Macau': 'Macao',
    'Marshall Islands': 'Marshall Is.', 'North Macedonia': 'Macedonia',
    'Saint Kitts and Nevis': 'St. Kitts and Nevis', 'Solomon Islands': 'Solomon Is.', 'South Sudan': 'S. Sudan',
};

const EUROPE = new Set([
    'Albania', 'Andorra', 'Austria', 'Belarus', 'Belgium', 'Bosnia and Herzegovina', 'Bulgaria', 'Croatia',
    'Cyprus', 'Czech Republic', 'Denmark', 'Estonia', 'Faroe Islands', 'Finland', 'France', 'Germany', 'Greece',
    'Hungary', 'Iceland', 'Ireland', 'Italy', 'Kosovo', 'Latvia', 'Liechtenstein', 'Lithuania', 'Luxembourg',
    'Malta', 'Moldova', 'Monaco', 'Montenegro', 'Netherlands', 'North Macedonia', 'Norway', 'Poland',
    'Portugal', 'Romania', 'San Marino', 'Serbia', 'Slovakia', 'Slovenia', 'Spain', 'Sweden', 'Switzerland',
    'Ukraine', 'United Kingdom',
]);

const GEO_SCOPES = {
    world: { label: 'World', level: 'countries', pairs: 'country_pairs', denom: 'papers' },
    europe: { label: 'Europe', level: 'countries', pairs: 'country_pairs', denom: 'papers' },
    us: { label: 'United States', level: 'states', pairs: 'state_pairs', denom: 'us_papers' },
};

const GEO_BLUE = '#0072B2';
const GEO_VERMILION = '#D55E00';
const GEO_EMPTY = '#eef0f2';
const GEO_LINES = 25;

class GeoTab {
    /**
     * opts.prefix: element-id prefix ('geo' for the Geography section).
     * opts.picker: build the journal pickers (false for a view fed by show()).
     */
    constructor(app, opts = {}) {
        this.app = app;
        this.prefix = opts.prefix || 'geo';
        this.slug = null;
        this.compareMode = opts.compareMode || 'all';   // 'none' | 'all' | 'journal'
        this.compareSlug = null;
        this.scope = 'world';
        this.measure = 'n';            // 'n' papers involving | 'f' fractional credit
        this.showLines = true;
        this.y0 = null;
        this.y1 = null;
        this.cache = {};
        this._shapes = null;

        if (opts.picker !== false) {
            this.picker = new SingleJournalPicker(`${this.prefix}-journal-picker`, app.journals, slug => {
                this.slug = slug;
                if (slug) this.load(); else this._showHint('Select a journal above to see where its authors are.');
            });
            this.comparePicker = new SingleJournalPicker(`${this.prefix}-compare-picker`, app.journals, slug => {
                this.compareSlug = slug;
                this._refreshComparison();
            });
        }
        this._wireControls();
    }

    _el(id) {
        return document.getElementById(`${this.prefix}-${id}`);
    }

    _all(groupId) {
        return document.querySelectorAll(`#${this.prefix}-${groupId} .toggle-btn`);
    }

    /** Show data already in hand (same shape as a geo export), e.g. one researcher's papers. */
    async show(data, slug) {
        this.slug = slug;
        this._showHint('Loading maps…');
        try {
            await this._loadShapes();
            this.data = data;
            await this._loadComparison();
            this._setYears();
            this._el('hint').style.display = 'none';
            this._el('content').style.display = '';
            this.render();
        } catch (e) {
            console.error('Geo error:', e);
            this._showHint('Could not draw the maps.');
        }
    }

    async _loadComparison() {
        const cmpSlug = this.compareMode === 'all' ? '_all'
            : this.compareMode === 'journal' ? this.compareSlug : null;
        this.cmp = null;
        if (cmpSlug && cmpSlug !== this.slug) {
            try { this.cmp = await this._data(cmpSlug); } catch (e) { console.warn('No comparison data:', e); }
        }
        this.cmpName = this.cmp ? (cmpSlug === '_all' ? 'all journals' : this.cmp.journal) : null;
    }

    // ---- data ----

    /**
     * Geo-export-shaped counts from papers in hand: [{year, countries, states}],
     * with the counting rules of src/pipeline/geo_aggregate.py.
     */
    static aggregate(papers, label, maxPair = 10) {
        const out = { journal: label, papers: {}, intl: {}, us_papers: {}, countries: {}, states: {},
                      country_pairs: {}, state_pairs: {} };
        const bump = (o, k) => { o[k] = (o[k] || 0) + 1; };
        const add = (table, pairs, y, regions) => {
            const share = 1 / regions.length;
            for (const r of regions) {
                const cell = ((table[r] = table[r] || {})[y] = table[r][y] || [0, 0]);
                cell[0] += 1;
                cell[1] = +(cell[1] + share).toFixed(6);
            }
            if (regions.length > 1 && regions.length <= maxPair) {
                for (let i = 0; i < regions.length; i++) {
                    for (let j = i + 1; j < regions.length; j++) {
                        bump((pairs[`${regions[i]}|${regions[j]}`] = pairs[`${regions[i]}|${regions[j]}`] || {}), y);
                    }
                }
            }
        };
        for (const p of papers) {
            const countries = [...new Set(p.countries)].sort();
            if (!countries.length || !p.year) continue;
            const y = String(p.year);
            bump(out.papers, y);
            if (countries.length > 1) bump(out.intl, y);
            add(out.countries, out.country_pairs, y, countries);
            const states = [...new Set(p.states)].sort();
            if (states.length) {
                bump(out.us_papers, y);
                add(out.states, out.state_pairs, y, states);
            }
        }
        return out;
    }

    /** PubMed affiliation strings per PMID, all authors, via EFetch (batches of 200). */
    static async fetchAffiliations(pmids, onProgress) {
        const out = new Map();
        const BATCH = 200;
        for (let i = 0; i < pmids.length; i += BATCH) {
            const ids = pmids.slice(i, i + BATCH);
            const body = new URLSearchParams({ db: 'pubmed', retmode: 'xml', id: ids.join(','),
                                               tool: 'IMPACT', email: 'impact-tool@umich.edu' });
            let resp;
            for (let attempt = 0; attempt < 3; attempt++) {
                resp = await fetch('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi', { method: 'POST', body });
                if (resp.ok) break;
                await new Promise(r => setTimeout(r, 1500 * (attempt + 1)));
            }
            if (!resp.ok) throw new Error(`PubMed EFetch failed (${resp.status})`);
            const doc = new DOMParser().parseFromString(await resp.text(), 'text/xml');
            for (const art of doc.querySelectorAll('PubmedArticle')) {
                const pmid = art.querySelector('MedlineCitation > PMID')?.textContent;
                if (!pmid) continue;
                const affils = [...art.querySelectorAll('AuthorList > Author')]
                    .filter(a => a.getAttribute('ValidYN') !== 'N')
                    .flatMap(a => [...a.querySelectorAll('AffiliationInfo > Affiliation')].map(x => x.textContent));
                out.set(pmid, affils);
            }
            if (onProgress) onProgress(Math.min(i + BATCH, pmids.length), pmids.length);
            await new Promise(r => setTimeout(r, 400));   // stay under PubMed's 3 requests/second
        }
        return out;
    }

    /** Countries and US states named across a paper's affiliation strings. */
    static placesOf(affils) {
        const countries = new Set(), states = new Set();
        for (const a of affils) {
            for (const loc of AffilLocation.parseLocations(a)) {
                countries.add(loc.country);
                if (loc.state) states.add(loc.state);
            }
        }
        return { countries: [...countries], states: [...states] };
    }

    async _data(slug) {
        if (!this.cache[slug]) this.cache[slug] = await dataLoader.loadGeo(slug);
        return this.cache[slug];
    }

    async _loadShapes() {
        if (this._shapes) return this._shapes;
        const [world, us] = await Promise.all([
            fetch(WORLD_TOPO_URL).then(r => r.json()),
            fetch(US_STATES_URL).then(r => r.json()),
        ]);
        const countries = topojson.feature(world, world.objects.countries).features
            .filter(f => f.properties.name !== 'Antarctica');
        this._shapes = { countries, states: us.features };
        return this._shapes;
    }

    /** Totals over the selected years: {denom, regions: Map(region -> {n, f}), pairs: Map}. */
    static totals(data, scope, y0, y1) {
        const cfg = GEO_SCOPES[scope];
        const inRange = y => +y >= y0 && +y <= y1;
        const sum = byYear => Object.entries(byYear || {}).reduce((s, [y, v]) => s + (inRange(y) ? v : 0), 0);
        const regions = new Map();
        for (const [r, byYear] of Object.entries(data[cfg.level] || {})) {
            if (scope === 'europe' && !EUROPE.has(r)) continue;
            let n = 0, f = 0;
            for (const [y, [cn, cf]] of Object.entries(byYear)) {
                if (inRange(y)) { n += cn; f += cf; }
            }
            if (n > 0) regions.set(r, { n, f });
        }
        const pairs = new Map();
        for (const [p, byYear] of Object.entries(data[cfg.pairs] || {})) {
            if (scope === 'europe' && !p.split('|').every(r => EUROPE.has(r))) continue;
            const n = sum(byYear);
            if (n > 0) pairs.set(p, n);
        }
        return { denom: sum(data[cfg.denom]), papers: sum(data.papers), intl: sum(data.intl),
                 us: sum(data.us_papers), regions, pairs };
    }

    static share(t, region, measure) {
        const c = t && t.regions.get(region);
        if (!c || !t.denom) return 0;
        return (measure === 'f' ? c.f : c.n) / t.denom;
    }

    // ---- controls ----

    _wireControls() {
        this._all('scope-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                this.scope = btn.dataset.scope;
                this._all('scope-toggle')
                    .forEach(b => b.classList.toggle('active', b === btn));
                this.render();
            });
        });
        this._all('measure-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                this.measure = btn.dataset.measure;
                this._all('measure-toggle')
                    .forEach(b => b.classList.toggle('active', b === btn));
                this.render();
            });
        });
        this._el('compare-mode').addEventListener('change', e => {
            this.compareMode = e.target.value;
            const wrap = this._el('compare-picker-wrap');
            if (wrap) wrap.style.display = this.compareMode === 'journal' ? '' : 'none';
            this._refreshComparison();
        });
        this._el('lines').addEventListener('change', e => {
            this.showLines = e.target.checked;
            this.render();
        });
        ['year-from', 'year-to'].forEach(id => {
            this._el(id).addEventListener('change', () => {
                this.y0 = +this._el('year-from').value;
                this.y1 = +this._el('year-to').value;
                if (this.y0 > this.y1) [this.y0, this.y1] = [this.y1, this.y0];
                this.render();
            });
        });
        ['png', 'pdf'].forEach(fmt => {
            this._el(`map-dl-${fmt}`).addEventListener('click', () => this._downloadMap(fmt));
        });
        this._el('regions-dl-csv').addEventListener('click', () => this._downloadRegionsCSV());
    }

    async _refreshComparison() {
        if (!this.data) return;
        await this._loadComparison();
        this.render();
    }

    _showHint(text) {
        const hint = this._el('hint');
        hint.textContent = text;
        hint.style.display = '';
        this._el('content').style.display = 'none';
    }

    async load() {
        this._showHint('Loading…');
        try {
            const [data] = await Promise.all([this._data(this.slug), this._loadShapes(), this._loadComparison()]);
            this.data = data;
            if (!data || !Object.keys(data.papers || {}).length) {
                this._showHint('No located author affiliations for this journal yet.');
                return;
            }
            this._setYears();
            this._el('hint').style.display = 'none';
            this._el('content').style.display = '';
            this.render();
        } catch (e) {
            console.error('Geo error:', e);
            this._showHint('Geographic data is not available for this journal yet.');
        }
    }

    /** Year selects span the journal's data; default to the last five complete years. */
    _setYears() {
        const years = Object.keys(this.data.papers).map(Number).sort((a, b) => a - b);
        const thisYear = new Date().getFullYear();
        const complete = years.filter(y => y < thisYear);
        const last = complete.length ? complete[complete.length - 1] : years[years.length - 1];
        const first = years[0];
        const opts = years.map(y => `<option value="${y}">${y}</option>`).join('');
        const from = this._el('year-from');
        const to = this._el('year-to');
        from.innerHTML = opts;
        to.innerHTML = opts;
        if (this.y0 == null || this.y0 < first || this.y1 > years[years.length - 1]) {
            this.y1 = last;
            this.y0 = Math.max(first, last - 4);
        }
        from.value = this.y0;
        to.value = this.y1;
    }

    // ---- rendering ----

    render() {
        if (!this.data || !this._shapes) return;
        const t = GeoTab.totals(this.data, this.scope, this.y0, this.y1);
        const c = this.cmp ? GeoTab.totals(this.cmp, this.scope, this.y0, this.y1) : null;
        this._renderMetrics(t);
        this._renderMap(t, c);
        this._renderRegionTable(t, c);
        this._renderPairTable(t);
        this._renderTrend();
        const range = this.y0 === this.y1 ? `${this.y0}` : `${this.y0}–${this.y1}`;
        const what = this.scope === 'us' ? 'US-affiliated papers involving each state'
            : `papers involving each country${this.scope === 'europe' ? ' (Europe)' : ''}`;
        const measure = this.measure === 'f' ? 'Fractional share of' : 'Share of';
        this._el('map-title').textContent = c
            ? `${this.data.journal} vs ${this.cmpName}: difference in ${measure.toLowerCase()} ${what}, ${range}`
            : `${this.data.journal}: ${measure.toLowerCase()} ${what}, ${range}`;
    }

    _renderMetrics(t) {
        const pct = (a, b) => b ? `${(100 * a / b).toFixed(1)}%` : '—';
        const top = [...t.regions.entries()].sort((a, b) => b[1].n - a[1].n)[0];
        this._el('metrics-row').innerHTML = [
            [t.papers.toLocaleString(), this.data.papersLabel || 'Citable papers with a located author'],
            [pct(t.intl, t.papers), 'International (2+ countries)'],
            [pct(t.us, t.papers), 'With a US author'],
            [top ? this._regionName(top[0]) : '—', this.scope === 'us' ? 'Leading state' : 'Leading country'],
        ].map(([v, l]) =>
            `<div class="metric-card"><span class="metric-value">${v}</span><span class="metric-label">${l}</span></div>`
        ).join('');
    }

    _regionName(r) {
        if (this.scope !== 'us') return r;
        const f = this._shapes.states.find(s => s.properties.stusps === r);
        return f ? f.properties.name : r;
    }

    _features() {
        if (this.scope === 'us') {
            return this._shapes.states.map(f => ({ key: f.properties.stusps, name: f.properties.name, f }));
        }
        const byAtlas = {};
        for (const f of this._shapes.countries) byAtlas[f.properties.name] = f;
        const keyFor = {};
        for (const [ours, atlas] of Object.entries(ATLAS_NAMES)) keyFor[atlas] = ours;
        return this._shapes.countries.map(f => {
            const key = keyFor[f.properties.name] || f.properties.name;
            return { key, name: key, f };
        });
    }

    _projection(width, height, feats) {
        if (this.scope === 'us') {
            return d3.geoAlbersUsa().fitSize([width, height], { type: 'FeatureCollection', features: feats.map(x => x.f) });
        }
        if (this.scope === 'europe') {
            const box = { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[-24, 34], [-24, 71], [42, 71], [42, 34], [-24, 34]]] } };
            return d3.geoConicConformal().rotate([-10, 0]).center([0, 52]).parallels([40, 65]).fitSize([width, height], box);
        }
        return d3.geoNaturalEarth1().fitSize([width, height], { type: 'Sphere' });
    }

    /** Centroid of a feature's largest polygon, so the USA and France land on their mainland. */
    static mainCentroid(f) {
        const g = f.geometry;
        if (g.type !== 'MultiPolygon') return d3.geoCentroid(f);
        let best = null, bestArea = -1;
        for (const coords of g.coordinates) {
            const poly = { type: 'Polygon', coordinates: coords };
            const a = d3.geoArea(poly);
            if (a > bestArea) { bestArea = a; best = poly; }
        }
        return d3.geoCentroid(best);
    }

    _renderMap(t, c) {
        const container = this._el('map');
        container.innerHTML = '';
        const width = container.clientWidth || 900;
        const height = Math.round(width * (this.scope === 'world' ? 0.5 : 0.62));
        const feats = this._features();
        const projection = this._projection(width, height, feats);
        const path = d3.geoPath(projection);

        const values = new Map();
        for (const x of feats) {
            const a = GeoTab.share(t, x.key, this.measure);
            const b = c ? GeoTab.share(c, x.key, this.measure) : null;
            const has = t.regions.has(x.key) || (c && c.regions.has(x.key));
            values.set(x.key, { a, b, has, diff: c ? a - b : null });
        }
        const inScope = x => this.scope !== 'europe' || EUROPE.has(x.key);
        let color, legend;
        if (c) {
            const m = d3.max(feats.filter(inScope), x => Math.abs(values.get(x.key).diff)) || 0.01;
            const s = d3.scaleLinear().domain([-m, 0, m]).range([GEO_VERMILION, '#f4f4f4', GEO_BLUE]).clamp(true);
            color = v => v.has ? s(v.diff) : GEO_EMPTY;
            legend = { type: 'diverging', min: -m, max: m, left: `More in ${this.cmpName}`, right: `More in ${this.data.journal}`, scale: s };
        } else {
            const m = d3.max(feats.filter(inScope), x => values.get(x.key).a) || 0.01;
            const s = d3.scaleSequentialSqrt(d3.interpolateRgb('#f0f6fb', GEO_BLUE)).domain([0, m]);
            color = v => v.has ? s(v.a) : GEO_EMPTY;
            legend = { type: 'sequential', min: 0, max: m, scale: s };
        }

        const svg = d3.select(container).append('svg')
            .attr('viewBox', `0 0 ${width} ${height}`).attr('width', '100%')
            .attr('xmlns', 'http://www.w3.org/2000/svg')
            .style('background', '#ffffff').style('display', 'block');
        const tip = d3.select(container).append('div').attr('class', 'geo-tooltip').style('display', 'none');
        const pct = v => `${(100 * v).toFixed(1)}%`;

        svg.append('g').selectAll('path')
            .data(feats.filter(x => path(x.f)))
            .join('path')
            .attr('d', x => path(x.f))
            .attr('fill', x => inScope(x) ? color(values.get(x.key)) : '#f7f7f7')
            .attr('stroke', '#ffffff').attr('stroke-width', 0.5)
            .on('mousemove', (ev, x) => {
                if (!inScope(x)) return;
                const v = values.get(x.key);
                const cnt = t.regions.get(x.key);
                let html = `<strong>${x.name}</strong><br>${this.data.journal}: ${pct(v.a)}` +
                    (cnt ? ` (${cnt.n.toLocaleString()} papers)` : '');
                if (c) html += `<br>${this.cmpName}: ${pct(v.b)}<br>Difference: ${(100 * v.diff >= 0 ? '+' : '')}${(100 * v.diff).toFixed(1)} pts`;
                const r = container.getBoundingClientRect();
                tip.style('display', '').html(html)
                    .style('left', `${Math.min(ev.clientX - r.left + 12, r.width - 220)}px`)
                    .style('top', `${ev.clientY - r.top + 12}px`);
            })
            .on('mouseleave', () => tip.style('display', 'none'));

        if (this.showLines) this._drawLines(svg, projection, feats, t);
        this._drawLegend(svg, legend, width, height);
        this._el('map-note').textContent = this.scope === 'us'
            ? 'Shares are of the journal\'s papers with at least one US-affiliated author. Lines join states that appear together on papers.'
            : 'A paper counts for every country among its authors\' affiliations. Lines join countries that appear together on papers.';
    }

    _drawLines(svg, projection, feats, t) {
        const byKey = new Map(feats.map(x => [x.key, x.f]));
        const top = [...t.pairs.entries()].sort((a, b) => b[1] - a[1]).slice(0, GEO_LINES);
        if (!top.length) return;
        const max = top[0][1];
        const g = svg.append('g').attr('fill', 'none').attr('pointer-events', 'none');
        for (const [p, n] of top) {
            const [a, b] = p.split('|');
            if (!byKey.has(a) || !byKey.has(b)) continue;
            const pa = projection(GeoTab.mainCentroid(byKey.get(a)));
            const pb = projection(GeoTab.mainCentroid(byKey.get(b)));
            if (!pa || !pb) continue;
            // A gentle arc between the projected points (great circles wrap at the map edge).
            const [mx, my] = [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2];
            const [dx, dy] = [pb[0] - pa[0], pb[1] - pa[1]];
            const bend = 0.18;
            const d = `M${pa[0]},${pa[1]} Q${mx + dy * bend},${my - dx * bend} ${pb[0]},${pb[1]}`;
            g.append('path').attr('d', d)
                .attr('stroke', '#333333').attr('stroke-opacity', 0.4)
                .attr('stroke-width', 0.6 + 4.4 * Math.sqrt(n / max))
                .attr('stroke-linecap', 'round');
        }
    }

    _drawLegend(svg, legend, width, height) {
        const w = Math.min(260, width * 0.4), h = 10, x = 16, y = height - 34;
        const id = `geo-grad-${Math.random().toString(36).slice(2, 8)}`;
        const grad = svg.append('defs').append('linearGradient').attr('id', id);
        d3.range(0, 1.0001, 0.1).forEach(s => {
            grad.append('stop').attr('offset', `${s * 100}%`)
                .attr('stop-color', legend.scale(legend.min + s * (legend.max - legend.min)));
        });
        const g = svg.append('g').attr('font-size', 11).attr('fill', '#2c3e50');
        g.append('rect').attr('x', x - 6).attr('y', y - 18).attr('width', w + 12).attr('height', 46)
            .attr('fill', '#ffffff').attr('fill-opacity', 0.85).attr('rx', 4);
        g.append('rect').attr('x', x).attr('y', y).attr('width', w).attr('height', h).attr('fill', `url(#${id})`);
        const fmt = v => `${(100 * v).toFixed(1)}%`;
        if (legend.type === 'diverging') {
            g.append('text').attr('x', x).attr('y', y - 5).text(legend.left);
            g.append('text').attr('x', x + w).attr('y', y - 5).attr('text-anchor', 'end').text(legend.right);
            g.append('text').attr('x', x).attr('y', y + h + 13).text(`−${(100 * legend.max).toFixed(1)} pts`);
            g.append('text').attr('x', x + w).attr('y', y + h + 13).attr('text-anchor', 'end').text(`+${(100 * legend.max).toFixed(1)} pts`);
        } else {
            g.append('text').attr('x', x).attr('y', y - 5).text('Share of papers');
            g.append('text').attr('x', x).attr('y', y + h + 13).text(fmt(0));
            g.append('text').attr('x', x + w).attr('y', y + h + 13).attr('text-anchor', 'end').text(fmt(legend.max));
        }
    }

    _regionRows(t, c) {
        const keys = new Set([...t.regions.keys(), ...(c ? c.regions.keys() : [])]);
        return [...keys].map(k => {
            const a = GeoTab.share(t, k, this.measure);
            const b = c ? GeoTab.share(c, k, this.measure) : null;
            return { key: k, name: this._regionName(k), papers: (t.regions.get(k) || { n: 0 }).n, a, b, diff: c ? a - b : null };
        }).sort((x, y) => y.a - x.a || (y.b || 0) - (x.b || 0));
    }

    _renderRegionTable(t, c) {
        const rows = this._regionRows(t, c).slice(0, 25);
        this._lastRegionRows = this._regionRows(t, c);
        const pct = v => v == null ? '—' : `${(100 * v).toFixed(1)}%`;
        const pts = v => v == null ? '' : `${v >= 0 ? '+' : '−'}${Math.abs(100 * v).toFixed(1)}`;
        const head = `<tr><th>${this.scope === 'us' ? 'State' : 'Country'}</th><th>Papers</th><th>Share</th>` +
            (c ? `<th>${UIHelpers.escapeHtml(this.cmpName)}</th><th>Diff (pts)</th>` : '') + '</tr>';
        const body = rows.map(r => `<tr><td>${UIHelpers.escapeHtml(r.name)}</td><td>${r.papers.toLocaleString()}</td>` +
            `<td>${pct(r.a)}</td>` + (c ? `<td>${pct(r.b)}</td><td class="${r.diff >= 0 ? 'geo-pos' : 'geo-neg'}">${pts(r.diff)}</td>` : '') + '</tr>').join('');
        this._el('region-table').innerHTML = `<table class="data-table geo-table"><thead>${head}</thead><tbody>${body}</tbody></table>`;
        this._el('region-title').textContent = this.scope === 'us' ? 'Leading states' : 'Leading countries';
    }

    _renderPairTable(t) {
        const top = [...t.pairs.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20);
        const el = this._el('pair-table');
        if (!top.length) { el.innerHTML = '<p class="data-note">No co-authored papers across regions in these years.</p>'; return; }
        const body = top.map(([p, n]) => {
            const [a, b] = p.split('|').map(r => UIHelpers.escapeHtml(this._regionName(r)));
            return `<tr><td>${a} – ${b}</td><td>${n.toLocaleString()}</td><td>${t.denom ? (100 * n / t.denom).toFixed(1) + '%' : '—'}</td></tr>`;
        }).join('');
        el.innerHTML = `<table class="data-table geo-table"><thead><tr><th>Pair</th><th>Papers</th><th>Share</th></tr></thead><tbody>${body}</tbody></table>`;
    }

    _renderTrend() {
        const cfg = GEO_SCOPES[this.scope];
        const years = Object.keys(this.data.papers).map(Number).sort((a, b) => a - b);
        const level = this.data[cfg.level] || {};
        const keys = Object.keys(level).filter(r => this.scope !== 'europe' || EUROPE.has(r));
        const tot = r => Object.values(level[r]).reduce((s, v) => s + v[0], 0);
        const top = keys.sort((a, b) => tot(b) - tot(a)).slice(0, 8);
        const denom = this.data[cfg.denom] || {};
        const datasets = top.map((r, i) => ({
            label: this._regionName(r),
            data: years.map(y => {
                const d = denom[y];
                const v = level[r][y];
                return d && v ? +(100 * (this.measure === 'f' ? v[1] : v[0]) / d).toFixed(2) : 0;
            }),
            borderColor: chartManager.palette[i % chartManager.palette.length],
            backgroundColor: chartManager.palette[i % chartManager.palette.length],
            borderWidth: 2, tension: 0.25, fill: false, pointRadius: 0, pointHoverRadius: 4,
        }));
        const chartId = `${this.prefix}-trend-chart`;
        chartManager._destroy(chartId);
        const ctx = this._el('trend-chart');
        chartManager.charts[chartId] = new Chart(ctx, {
            type: 'line',
            data: { labels: years, datasets },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    title: { display: true, text: `${this.data.journal}: share of ${this.scope === 'us' ? 'US-affiliated ' : ''}papers by year`, font: { size: 14 } },
                    subtitle: { display: true, text: 'Before about 2014 PubMed recorded only the first author\'s affiliation, so earlier years undercount collaborators.', font: { size: 11 } },
                    legend: { position: 'bottom' },
                    tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` } },
                },
                scales: {
                    x: { title: { display: true, text: 'Publication year' } },
                    y: { title: { display: true, text: '% of papers' }, beginAtZero: true },
                },
            },
        });
    }

    // ---- downloads ----

    _downloadRegionsCSV() {
        const rows = this._lastRegionRows || [];
        const cmp = this.cmp ? [`"${this.cmpName} share"`, 'diff_pts'] : [];
        const lines = [['region', 'papers', 'share', ...cmp].join(',')];
        rows.forEach(r => lines.push([`"${r.name}"`, r.papers, r.a.toFixed(4),
            ...(this.cmp ? [r.b.toFixed(4), (100 * r.diff).toFixed(2)] : [])].join(',')));
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
        a.download = `${this.prefix}-${this.scope}-${this.slug}-${this.y0}-${this.y1}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    _downloadMap(format) {
        const svgEl = this._el('map').querySelector('svg');
        if (!svgEl) return;
        const vb = svgEl.viewBox.baseVal;
        const scale = 2;
        const W = vb.width * scale, H = vb.height * scale;
        const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svgEl)], { type: 'image/svg+xml;charset=utf-8' }));
        const img = new Image();
        const title = this._el('map-title').textContent;
        const filename = `${this.prefix}-map-${this.scope}-${this.slug}`;
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = W; canvas.height = H;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, W, H);
            ctx.drawImage(img, 0, 0, W, H);
            URL.revokeObjectURL(url);
            if (format === 'pdf') {
                if (!window.jspdf) return;
                const { jsPDF } = window.jspdf;
                const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
                const pw = doc.internal.pageSize.getWidth();
                const ph = doc.internal.pageSize.getHeight();
                const imgW = pw - 20;
                const imgH = Math.min(imgW * (H / W), ph - 28);
                doc.setFontSize(10);
                doc.text(doc.splitTextToSize(`IMPACT — ${title}`, pw - 20), 10, 10);
                doc.addImage(canvas.toDataURL('image/png'), 'PNG', 10, 18, imgW, imgH);
                doc.save(`${filename}.pdf`);
                return;
            }
            const a = document.createElement('a');
            a.href = canvas.toDataURL('image/png');
            a.download = `${filename}.png`;
            a.click();
        };
        img.src = url;
    }
}
