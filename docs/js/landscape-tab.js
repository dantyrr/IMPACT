/**
 * IMPACT Landscape tab: the JIF paper's site-wide figures as live charts.
 * Data: landscape.json and journal_measures.json from scripts/export_site_extras.py,
 * a snapshot that the weekly update doesn't refresh.
 */
class LandscapeTab {
    constructor(app) {
        this.app = app;
        this.data = null;
        this.measures = null;
        this.group = null;
        this.slug = null;
        this.reports = null;
    }

    /** Pick a journal: loads its guidelines and recurring series for the annual reports chart. */
    async _pick(slug) {
        this.slug = slug;
        let reports = null;
        if (slug) {
            const cache = this.app.papersDataCache;
            const [papers, series] = await Promise.all([
                cache[slug] !== undefined ? cache[slug] : dataLoader.loadPapers(slug).catch(() => null),
                dataLoader.loadSeries(slug).catch(() => null),
            ]);
            cache[slug] = papers;
            if (this.slug !== slug) return;
            const pmids = ((series && series.series) || []).flatMap(s => s.pmids);
            reports = papers ? SiteMetrics.reportMonths(papers.papers, pmids, 2010, 2022) : [];
        }
        this.reports = reports;
        this.render();
    }

    _name() {
        return (this.app.journals.find(j => j.slug === this.slug) || {}).name || '';
    }

    /** A line drawn on the chart, so a downloaded figure says which journal it marks. */
    _subtitle(text) {
        return { display: !!text, text, color: '#444444', font: { size: 12, weight: 'normal' }, padding: { bottom: 10 } };
    }

    /** The annual reports chart with a bottom row for the picked journal. */
    _withJournal(spec) {
        if (spec.type !== 'bubble' || !this.slug || !this.reports) return spec;
        const j = this.app.journals.find(x => x.slug === this.slug) || {};
        if (!this.reports.length) return { ...spec, subtitle: `${this._name()}: no guidelines or recurring series among its 2,000 most-cited papers, 2010–22` };
        const y = spec.yLabels.length;
        return {
            ...spec,
            yLabels: [...spec.yLabels, `Guidelines and series (${j.abbreviation || j.name})`],
            points: [...spec.points, ...this.reports.map(r => ({ ...r, y }))],
            subtitle: `Bottom row: ${this._name()}, guidelines and recurring series among its 2,000 most-cited papers`,
        };
    }

    async show() {
        if (this.data) return this.render();
        const hint = document.getElementById('landscape-hint');
        try {
            [this.data, this.measures] = await Promise.all([dataLoader.loadLandscape(), dataLoader.loadMeasures()]);
        } catch (e) {
            console.warn('Landscape data not available:', e.message);
            hint.textContent = 'These charts could not be loaded.';
            return;
        }
        hint.style.display = 'none';
        this.group = this.data.groups[0].id;
        document.getElementById('landscape-asof').textContent = `Data as of ${this.data.asOf}.`;
        const toggle = document.getElementById('landscape-groups');
        toggle.innerHTML = this.data.groups.map(g => `<button class="toggle-btn" data-group="${g.id}">${g.label}</button>`).join('');
        toggle.querySelectorAll('.toggle-btn').forEach(btn => {
            btn.onclick = () => { this.group = btn.dataset.group; this.render(); };
        });
        new SingleJournalPicker('landscape-journal-picker', this.app.journals, slug => this._pick(slug));
        this.render();
    }

    render() {
        document.querySelectorAll('#landscape-groups .toggle-btn').forEach(b => b.classList.toggle('active', b.dataset.group === this.group));
        const wrap = document.getElementById('landscape-charts');
        wrap.innerHTML = '';
        Object.keys(chartManager.charts).filter(id => id.startsWith('landscape-')).forEach(id => chartManager._destroy(id));
        this.data.groups.find(g => g.id === this.group).charts.forEach(spec => this._renderCard(wrap, spec));
    }

    _renderCard(wrap, spec) {
        const card = document.createElement('div');
        card.className = 'authors-chart-card extras-card';
        card.innerHTML = `<h4>${spec.title}</h4><p class="section-note">${spec.note}</p>`;
        wrap.appendChild(card);
        const id = `landscape-${spec.id}`;
        if (spec.type === 'set') return this._renderSet(card, spec, id);
        const shown = this._withJournal(spec);
        this._draw(card, id, shown, this._height(shown));
        this.app.extras._downloads(card, id, 'landscape', this._rows(shown));
    }

    _height(spec) {
        const n = spec.labels ? spec.labels.length : 0;
        if (spec.type === 'hbar') return Math.max(220, 60 + n * (spec.series ? 15 * spec.series.length + 6 : 22));
        if (spec.type === 'bubble') return 40 + 40 * spec.yLabels.length;
        if (spec.type === 'hist') return 260;
        if (spec.type === 'scatter') return 460;
        return 340;
    }

    _renderSet(card, spec, id) {
        const names = Object.keys(spec.sets);
        const bar = document.createElement('div');
        bar.className = 'chart-controls';
        bar.innerHTML = `<select class="range-select" style="min-width:240px;" aria-label="${spec.title}">${names.map(n => `<option>${n}</option>`).join('')}</select>` +
            (spec.sharedScale ? '<label class="geo-check"><input type="checkbox"> Shared scale</label>' : '');
        card.appendChild(bar);
        const select = bar.querySelector('select');
        const shared = bar.querySelector('input');
        const box = document.createElement('div');
        card.appendChild(box);
        const total = (s) => Math.max(...s.labels.map((_, i) => s.series.reduce((a, x) => a + (x.data[i] || 0), 0)));
        const draw = () => {
            box.innerHTML = '';
            const one = { ...spec.sets[select.value], id: spec.id };
            if (shared && shared.checked) one.max = Math.ceil(Math.max(...names.map(n => total(spec.sets[n]))) * 1.05);
            this._draw(box, id, one, 340);
            this.app.extras._downloads(box, id, 'landscape', this._rows(one));
        };
        select.onchange = draw;
        if (shared) shared.onchange = draw;
        draw();
    }

    _draw(parent, id, spec, height) {
        const box = document.createElement('div');
        box.className = 'chart-container';
        box.style.height = `${height}px`;
        box.innerHTML = `<canvas id="${id}"></canvas>`;
        parent.appendChild(box);
        chartManager._destroy(id);
        chartManager.charts[id] = new Chart(box.firstChild, this[`_${spec.type}`](spec, parent));
    }

    _base(extra = {}) {
        return {
            responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
            plugins: { legend: { position: 'bottom' } }, ...extra,
        };
    }

    _axis(text, extra = {}) {
        return { title: { display: !!text, text }, ...extra };
    }

    _line(spec) {
        const mark = spec.mark == null ? [] : [{
            id: 'mark',
            afterDatasetsDraw: (chart) => {
                const x = chart.scales.x.getPixelForValue(spec.labels.indexOf(spec.mark));
                const { top, bottom } = chart.chartArea, c = chart.ctx;
                c.save(); c.strokeStyle = '#222222'; c.setLineDash([5, 4]); c.beginPath(); c.moveTo(x, top); c.lineTo(x, bottom); c.stroke(); c.restore();
            },
        }];
        return {
            type: 'line',
            plugins: mark,
            data: {
                labels: spec.labels,
                datasets: spec.series.map(s => ({
                    label: s.label, data: s.data, borderColor: s.color, backgroundColor: s.fill ? `${s.color}44` : s.color,
                    fill: s.fill || false, pointRadius: spec.labels.length > 40 ? 0 : 2, borderWidth: 2, tension: 0, spanGaps: true,
                })),
            },
            options: this._base({
                scales: {
                    x: this._axis(spec.x, { ticks: { maxTicksLimit: 14 } }),
                    y: this._axis(spec.y, { type: spec.yLog ? 'logarithmic' : 'linear', min: spec.yMin, max: spec.yMax }),
                },
            }),
        };
    }

    _stack(spec) {
        const bars = !!spec.bars;
        return {
            type: bars ? 'bar' : 'line',
            data: {
                labels: spec.labels,
                datasets: spec.series.map(s => ({ label: s.label, data: s.data, backgroundColor: s.color, borderColor: s.color, fill: !bars, pointRadius: 0, borderWidth: bars ? 0 : 1, tension: 0 })),
            },
            options: this._base({
                scales: {
                    x: this._axis(spec.x, { stacked: bars }),
                    y: this._axis(spec.y, { stacked: true, min: 0, max: spec.max }),
                },
            }),
        };
    }

    _hbar(spec) {
        const series = spec.series || [{ label: spec.x, data: spec.values, color: '#0072B2' }];
        const hover = spec.hover;
        return {
            type: 'bar',
            data: { labels: spec.labels, datasets: series.map(s => ({ label: s.label, data: s.data, backgroundColor: s.color })) },
            options: this._base({
                indexAxis: 'y',
                interaction: { intersect: false, mode: 'index', axis: 'y' },
                plugins: {
                    legend: { display: !!spec.series, position: 'bottom' },
                    tooltip: { callbacks: hover ? { afterLabel: c => hover[c.dataIndex] } : {} },
                },
                scales: {
                    x: this._axis(spec.x),
                    y: {
                        ticks: {
                            autoSkip: false, font: { size: 11 },
                            callback: function (v) {
                                const l = this.getLabelForValue(v);
                                return window.innerWidth < 640 && l.length > 22 ? `${l.slice(0, 21)}…` : l;
                            },
                        },
                    },
                },
            }),
        };
    }

    _bubble(spec) {
        const top = Math.max(...spec.points.map(p => p.v));
        const at = (labels) => (axis) => { axis.ticks = labels.map((_, i) => ({ value: i })); };
        const fmt = (p) => `${spec.yLabels[p.y]}, ${spec.xLabels[p.x]}: ${Math.round(p.v).toLocaleString()} citations (${p.n} report${p.n === 1 ? '' : 's'})`;
        const narrow = window.innerWidth < 640;
        const xText = (v) => { const l = spec.xLabels[v] || ''; return !narrow ? l : l.length > 3 ? '–' : l.slice(0, 1); };
        const yText = (v) => { const l = spec.yLabels[v] || ''; return narrow ? (l.match(/\(([^)]*)\)$/) || [0, l])[1] : l; };
        return {
            type: 'bubble',
            data: {
                datasets: [{
                    data: spec.points.map(p => ({ x: p.x, y: p.y, r: 2 + (narrow ? 6 : 14) * Math.sqrt(p.v / top), p })),
                    backgroundColor: spec.points.map(p => (p.x <= 2 ? '#D55E00bb' : '#0072B2bb')),
                }],
            },
            options: this._base({
                interaction: { mode: 'nearest', intersect: true },
                plugins: { legend: { display: false }, subtitle: this._subtitle(spec.subtitle), tooltip: { callbacks: { label: c => fmt(c.raw.p) } } },
                scales: {
                    x: { min: -0.5, max: spec.xLabels.length - 0.5, afterBuildTicks: at(spec.xLabels), ticks: { autoSkip: false, maxRotation: 0, callback: xText } },
                    y: { reverse: true, min: -0.5, max: spec.yLabels.length - 0.5, afterBuildTicks: at(spec.yLabels), ticks: { autoSkip: false, callback: yText, font: { size: 10 } } },
                },
            }),
        };
    }

    _scatter(spec) {
        const picked = spec.points.filter(p => p.slug && p.slug === this.slug);
        const powers = { callback: v => (Math.log10(v) % 1 === 0 ? `${v}` : '') };
        const rest = spec.points;
        const sets = [{
            label: 'Journals', data: rest, pointRadius: 2.5, pointHoverRadius: 5,
            backgroundColor: rest.map(p => p.color ? `${p.color}99` : '#8C8C8C66'), borderWidth: 0,
        }];
        if (picked.length) sets.unshift({ label: picked[0].label, data: picked, pointRadius: 6, backgroundColor: '#D55E00' });
        const diagonal = spec.diagonal ? [{
            id: 'diagonal',
            afterDatasetsDraw: (chart) => {
                const { x, y } = chart.scales, lo = Math.max(x.min, y.min), hi = Math.min(x.max, y.max), c = chart.ctx;
                c.save(); c.strokeStyle = '#222222'; c.setLineDash([5, 4]); c.beginPath();
                c.moveTo(x.getPixelForValue(lo), y.getPixelForValue(lo)); c.lineTo(x.getPixelForValue(hi), y.getPixelForValue(hi)); c.stroke(); c.restore();
            },
        }] : [];
        return {
            type: 'scatter',
            plugins: diagonal,
            data: { datasets: sets },
            options: this._base({
                interaction: { mode: 'nearest', intersect: true },
                plugins: {
                    legend: { display: picked.length > 0, position: 'bottom' },
                    subtitle: this._subtitle(picked.length ? `Orange dot: ${this._name()}` : ''),
                    tooltip: { callbacks: { label: c => `${c.raw.label}: ${c.raw.x}, ${c.raw.y}` } },
                },
                scales: {
                    x: this._axis(spec.x, spec.log ? { type: 'logarithmic', ticks: powers } : { min: 0 }),
                    y: this._axis(spec.y, spec.log ? { type: 'logarithmic', ticks: powers } : { min: spec.yMin, max: spec.yMax }),
                },
            }),
        };
    }

    _hist(spec, parent) {
        const m = this.measures.measures[spec.measure];
        const mine = this.slug && this.measures.journals[this.slug] && this.measures.journals[this.slug][spec.measure];
        let hit = -1;
        if (mine) {
            hit = m.bins.findIndex(b => b > mine[0]) - 1;
            if (hit < 0) hit = mine[0] >= m.bins[m.bins.length - 1] ? m.counts.length - 1 : 0;
            hit = Math.min(hit, m.counts.length - 1);
        }
        const note = document.createElement('p');
        note.className = 'section-note';
        const name = this._name();
        const pctText = (v) => `${(Math.abs(100 * v) < 0.05 ? 0 : 100 * v).toFixed(1)}%`.replace('-', '−');
        note.textContent = `${m.n.toLocaleString()} journals, median ${pctText(m.median)}.` +
            (this.slug ? (mine ? ` ${name}: ${pctText(mine[0])}, ${SiteMetrics.rankPhrase(mine[1])} of journals.` : ` ${name} isn't in this measure.`) : '');
        parent.appendChild(note);
        return {
            type: 'bar',
            data: {
                labels: m.counts.map((_, i) => `${(100 * m.bins[i]).toFixed(1)}%`),
                datasets: [{ label: 'Journals', data: m.counts, backgroundColor: m.counts.map((_, i) => (i === hit ? '#D55E00' : '#8C8C8C')), barPercentage: 1, categoryPercentage: 1 }],
            },
            options: this._base({
                plugins: { legend: { display: false }, subtitle: this._subtitle(mine ? `Orange bar: ${name}, ${pctText(mine[0])}` : '') },
                scales: { x: this._axis(m.label, { ticks: { maxTicksLimit: 10 }, grid: { display: false } }), y: this._axis('Journals') },
            }),
        };
    }

    /** CSV rows for a chart. */
    _rows(spec) {
        if (spec.type === 'hist') {
            const m = this.measures.measures[spec.measure];
            return [['bin_start', 'journals'], ...m.counts.map((c, i) => [m.bins[i], c])];
        }
        if (spec.type === 'scatter') return [['label', 'x', 'y'], ...spec.points.map(p => [p.label, p.x, p.y])];
        if (spec.type === 'bubble') return [['series', 'month', 'reports', 'mean_citations_first_24_months'], ...spec.points.map(p => [spec.yLabels[p.y], spec.xLabels[p.x], p.n, p.v])];
        const series = spec.series || [{ label: spec.x, data: spec.values }];
        return [['label', ...series.map(s => s.label)], ...spec.labels.map((l, i) => [String(l), ...series.map(s => s.data[i])])];
    }
}
