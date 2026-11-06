/**
 * Cards from the JIF paper, shown for any journal or paper: reliance on one paper,
 * the publication calendar and moving a paper. Calculations are in site-metrics.js.
 */
class JournalExtras {
    constructor(app) {
        this.app = app;
        this.token = 0;
    }

    /** Journal page: build every card this journal has data for. */
    async render(data) {
        const wrap = document.getElementById('journal-extras');
        if (!wrap) return;
        wrap.innerHTML = '';
        Object.keys(chartManager.charts).filter(id => id.startsWith('extras-')).forEach(id => chartManager._destroy(id));
        const token = ++this.token;
        const cache = this.app.papersDataCache;
        let papers = cache[data.slug];
        if (papers === undefined) {
            try { papers = await dataLoader.loadPapers(data.slug); } catch (e) { papers = null; }
            cache[data.slug] = papers;
        }
        if (token !== this.token) return;
        const settled = this.app._settledMonth(data);
        const ts = (data.timeseries || []).filter(e => !settled || e.month <= settled);
        this._renderReliance(wrap, data, ts, papers);
        this._renderCalendar(wrap, data);
        const [summary, measures, citers, series] = await Promise.all([dataLoader.loadRetractionSummary(), dataLoader.loadMeasures(),
            dataLoader.loadCiters(data.slug), dataLoader.loadSeries(data.slug)]);
        if (token !== this.token) return;
        this._renderSeries(wrap, data, ts, papers, series);
        this._renderRetractions(wrap, data, summary && summary[data.slug]);
        this._renderCompare(wrap, data, measures);
        this._renderCiters(wrap, data, citers);
    }

    // ---- shared ----

    _card(wrap, id, title, note) {
        const el = document.createElement('div');
        el.className = 'authors-chart-card extras-card';
        el.id = id;
        el.innerHTML = `<h4>${title}</h4>${note ? `<p class="section-note">${note}</p>` : ''}`;
        wrap.appendChild(el);
        return el;
    }

    _chartBox(card, canvasId, height = 300) {
        const box = document.createElement('div');
        box.className = 'chart-container';
        box.style.height = `${height}px`;
        box.innerHTML = `<canvas id="${canvasId}"></canvas>`;
        card.appendChild(box);
        return box.firstChild;
    }

    _draw(canvas, config) {
        chartManager._destroy(canvas.id);
        chartManager.charts[canvas.id] = new Chart(canvas, config);
    }

    _downloads(card, canvasId, slug, csvRows) {
        const bar = document.createElement('div');
        bar.className = 'download-bar';
        bar.innerHTML = '<span class="download-label">Download:</span>' +
            '<button class="download-btn" data-fmt="png">PNG</button><button class="download-btn" data-fmt="csv">CSV</button>';
        bar.querySelector('[data-fmt="png"]').onclick = () => this.app._downloadDetailChart(canvasId, slug, 'png');
        bar.querySelector('[data-fmt="csv"]').onclick = () => {
            const text = csvRows.map(r => r.map(v => (typeof v === 'string' ? `"${v.replace(/"/g, '""')}"` : (v ?? ''))).join(',')).join('\n');
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
            a.download = `${canvasId}-${slug}.csv`;
            a.click();
            URL.revokeObjectURL(a.href);
        };
        card.appendChild(bar);
    }

    _paperLink(pmid, text) {
        return `<a href="#papers" class="extras-paper-link" data-pmid="${pmid}">${UIHelpers.escapeHtml(text)}</a>`;
    }

    _wirePaperLinks(el) {
        el.querySelectorAll('.extras-paper-link').forEach(a => {
            a.onclick = (e) => {
                e.preventDefault();
                document.getElementById('network-pmid-input').value = a.dataset.pmid;
                this.app.showSection('papers');
                this.app.loadCitationNetwork();
            };
        });
    }

    // ---- journal cards ----

    _renderReliance(wrap, data, ts, papers) {
        const rows = SiteMetrics.topPaperSeries(papers && papers.papers, ts);
        if (rows.length < 2) return;
        const last = rows[rows.length - 1];
        const card = this._card(wrap, 'extras-reliance', 'Reliance on One Paper',
            'The JIF-style rate each year with and without that year\'s most-cited paper. It uses PubMed citations in one ' +
            'calendar year to citable items from the two years before.');
        const p = document.createElement('p');
        p.className = 'section-note';
        p.innerHTML = `In ${last.year}, its top paper took ${(100 * last.share).toFixed(1)}% of citations: ${this._paperLink(last.pmid, (last.title || `PMID ${last.pmid}`).replace(/\.$/, ''))}.`;
        card.appendChild(p);
        this._wirePaperLinks(p);
        const canvas = this._chartBox(card, 'extras-reliance-chart');
        this._draw(canvas, {
            type: 'line',
            data: {
                labels: rows.map(r => r.year),
                datasets: [
                    { label: 'All citable items', data: rows.map(r => +r.rate.toFixed(2)), borderColor: '#0072B2', backgroundColor: '#0072B2', pointRadius: 2, tension: 0 },
                    { label: 'Without the top paper', data: rows.map(r => (r.rateWithout == null ? null : +r.rateWithout.toFixed(2))), borderColor: '#D55E00', backgroundColor: '#D55E00', pointRadius: 2, tension: 0 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: { callbacks: { afterBody: items => { const r = rows[items[0].dataIndex]; return `Top paper: ${(100 * r.share).toFixed(1)}% of citations`; } } },
                },
                scales: { x: { title: { display: true, text: 'Citation year' } }, y: { beginAtZero: true, title: { display: true, text: 'JIF-style rate' } } },
            },
        });
        this._downloads(card, canvas.id, data.slug, [['year', 'rate', 'rate_without_top_paper', 'top_paper_share', 'top_pmid', 'top_title'],
            ...rows.map(r => [r.year, +r.rate.toFixed(3), r.rateWithout == null ? '' : +r.rateWithout.toFixed(3), +r.share.toFixed(4), r.pmid, r.title || ''])]);
    }

    _renderCalendar(wrap, data) {
        const thisYear = Number((data.last_updated || '').slice(0, 4)) || new Date().getFullYear();
        const rows = SiteMetrics.earlyShare(data.timeseries).filter(r => r.year < thisYear && r.reviews >= 5 && r.other >= 5);
        if (rows.length < 2) return;
        const card = this._card(wrap, 'extras-calendar', 'Publication Calendar',
            'Share of reviews and of other citable items published January to March, in years with at least 5 of each. ' +
            'A January paper has had longer to be cited when a JIF counts it, so this shows whether a journal puts reviews early. ' +
            'June is left out, because papers with no month are stored there.');
        const canvas = this._chartBox(card, 'extras-calendar-chart');
        this._draw(canvas, {
            type: 'line',
            data: {
                labels: rows.map(r => r.year),
                datasets: [
                    { label: 'Reviews', data: rows.map(r => +(100 * r.reviewsEarly).toFixed(1)), borderColor: '#D55E00', backgroundColor: '#D55E00', pointRadius: 2, tension: 0 },
                    { label: 'Other citable items', data: rows.map(r => +(100 * r.otherEarly).toFixed(1)), borderColor: '#0072B2', backgroundColor: '#0072B2', borderDash: [6, 4], pointRadius: 2, tension: 0 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { title: { display: true, text: 'Year published' } }, y: { min: 0, max: 100, title: { display: true, text: 'Share published Jan–Mar (%)' } } },
            },
        });
        this._downloads(card, canvas.id, data.slug, [['year', 'reviews', 'other_citable_items', 'reviews_jan_mar', 'other_jan_mar'],
            ...rows.map(r => [r.year, r.reviews, r.other, +r.reviewsEarly.toFixed(4), +r.otherEarly.toFixed(4)])]);
    }

    _renderRetractions(wrap, data, s) {
        if (!s || !s.retracted) return;
        const card = this._card(wrap, 'extras-retractions', 'Retractions',
            `${s.retracted.toLocaleString()} retracted paper${s.retracted === 1 ? '' : 's'}` +
            (s.per10k != null ? `; ${s.per10k.toLocaleString()} per 10,000 citable items published 2015–23` : '') +
            '. Sources: Retraction Watch and PubMed, as of Nov 2026. Years retracted leave out papers with no date.');
        const years = [...new Set([...Object.keys(s.pub), ...Object.keys(s.ret)])].map(Number).sort((a, b) => a - b);
        const all = [];
        for (let y = years[0]; y <= years[years.length - 1]; y++) all.push(y);
        const canvas = this._chartBox(card, 'extras-retractions-chart', 260);
        this._draw(canvas, {
            type: 'bar',
            data: {
                labels: all,
                datasets: [
                    { label: 'By year published', data: all.map(y => s.pub[y] || 0), backgroundColor: '#0072B2' },
                    { label: 'By year retracted', data: all.map(y => s.ret[y] || 0), backgroundColor: '#D55E00' },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { title: { display: true, text: 'Year' } }, y: { beginAtZero: true, title: { display: true, text: 'Retracted papers' }, ticks: { precision: 0 } } },
            },
        });
        this._downloads(card, canvas.id, data.slug, [['year', 'retracted_papers_by_year_published', 'retracted_papers_by_year_retracted'],
            ...all.map(y => [y, s.pub[y] || 0, s.ret[y] || 0])]);
    }

    _renderSeries(wrap, data, ts, papers, file) {
        if (!file || !file.series.length || !papers) return;
        const pmids = file.series.flatMap(s => s.pmids);
        if (!pmids.length) return;
        const r = SiteMetrics.rateWithout(ts, papers.papers, pmids);
        if (!r.removed) return;
        const card = this._card(wrap, 'extras-series', 'Recurring Series',
            'Titles that repeat year after year in this journal, such as annual statistics reports, and the 24-month rate with and without them. ' +
            (r.missing ? `${r.missing} of ${pmids.length} items are outside the journal's 2,000 most-cited papers, so they stay in the rate.` : ''));
        const rows = r.rows;
        const byMonth = new Map(ts.map(e => [e.month, e.rolling_if]));
        const canvas = this._chartBox(card, 'extras-series-chart', 280);
        this._draw(canvas, {
            type: 'line',
            data: {
                labels: rows.map(x => x.month),
                datasets: [
                    { label: 'All citable items', data: rows.map(x => byMonth.get(x.month)), borderColor: '#0072B2', backgroundColor: '#0072B2', pointRadius: 0, tension: 0.1, borderWidth: 2 },
                    { label: 'Without recurring series', data: rows.map(x => (x.rate == null ? null : +x.rate.toFixed(3))), borderColor: '#D55E00', backgroundColor: '#D55E00', pointRadius: 0, tension: 0.1, borderWidth: 2 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { ticks: { maxTicksLimit: 12 } }, y: { beginAtZero: true, title: { display: true, text: '24-month rate' } } },
            },
        });
        this._downloads(card, canvas.id, data.slug, [['month', 'rate', 'rate_without_series'], ...rows.map(x => [x.month, byMonth.get(x.month), x.rate == null ? '' : +x.rate.toFixed(3)])]);
        const list = document.createElement('p');
        list.className = 'section-note';
        const top = file.series.slice(0, 5).map(s => `${UIHelpers.escapeHtml(s.title.replace(/\.$/, ''))} (${s.items} items, ${s.citations.toLocaleString()} citations)`);
        list.innerHTML = `Largest: ${top.join('; ')}.${file.series.length > 5 ? ` ${file.series.length - 5} more.` : ''}`;
        card.appendChild(list);
    }

    _renderCompare(wrap, data, file) {
        const mine = file && file.journals[data.slug];
        if (!mine || !Object.keys(mine).length) return;
        const card = this._card(wrap, 'extras-compare', 'How This Journal Compares',
            `Where this journal sits among all journals with enough data, as of ${file.asOf}. The dark bar marks this journal.`);
        const grid = document.createElement('div');
        grid.className = 'extras-compare-grid';
        card.appendChild(grid);
        for (const [key, m] of Object.entries(file.measures)) {
            if (!mine[key]) continue;
            const [value, pct] = mine[key];
            const shown = `${m.signed ? (value >= 0 ? '+' : '−') : ''}${Math.abs(100 * value).toFixed(1)}%`;
            const place = SiteMetrics.rankPhrase(pct);
            const cell = document.createElement('div');
            cell.innerHTML = `<div class="extras-compare-label">${m.label}</div>` +
                `<div class="extras-compare-value">${shown} <span>${place} of ${m.n.toLocaleString()} journals</span></div>` +
                `<div class="chart-container" style="height:90px; margin:0;"><canvas id="extras-compare-${key}"></canvas></div>`;
            grid.appendChild(cell);
            const at = Math.min(m.counts.length - 1, Math.max(0, m.bins.findIndex(b => b > value) - 1));
            const hit = value >= m.bins[m.bins.length - 1] ? m.counts.length - 1 : at;
            this._draw(cell.querySelector('canvas'), {
                type: 'bar',
                data: { labels: m.counts.map((_, i) => `${(100 * m.bins[i]).toFixed(1)}%`), datasets: [{ data: m.counts, backgroundColor: m.counts.map((_, i) => (i === hit ? '#222222' : '#C9C9C9')), barPercentage: 1, categoryPercentage: 1 }] },
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { legend: { display: false } },
                    scales: { x: { ticks: { maxTicksLimit: 5, font: { size: 9 } }, grid: { display: false } }, y: { display: false } },
                },
            });
        }
    }

    _renderCiters(wrap, data, c) {
        if (!c || !Object.keys(c.countries).length) return;
        const card = this._card(wrap, 'extras-citers', 'Who Cites This Journal',
            `Citations made in ${c.year} to citable items from ${c.year - 2}–${String(c.year - 1).slice(2)}, as of Nov 2026. Each citing paper is split equally across its authors' countries; ` +
            `${c.located.toLocaleString()} of ${c.citations.toLocaleString()} citations have a located author.`);
        const regions = SiteMetrics.REGION_ORDER;
        const colors = { 'USA': '#0072B2', 'Canada': '#56B4E9', 'Europe': '#E69F00', 'China': '#D55E00', 'Other Asia': '#009E73', 'Rest of world': '#8C8C8C' };
        const sum = (shares) => { const o = Object.fromEntries(regions.map(r => [r, 0])); for (const [k, v] of Object.entries(shares)) o[SiteMetrics.regionOf(k)] += v; return o; };
        const cite = sum(c.countries), auth = sum(c.authors);
        const canvas = this._chartBox(card, 'extras-citers-chart', 170);
        this._draw(canvas, {
            type: 'bar',
            data: { labels: ['Citing authors', 'Authors in this journal'], datasets: regions.map(r => ({ label: r, data: [+(100 * cite[r]).toFixed(1), +(100 * auth[r]).toFixed(1)], backgroundColor: colors[r] })) },
            options: {
                indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: x => `${x.dataset.label}: ${x.parsed.x.toFixed(1)}%` } } },
                scales: { x: { stacked: true, max: 100, title: { display: true, text: 'Share (%)' } }, y: { stacked: true } },
            },
        });
        this._downloads(card, canvas.id, data.slug, [['region', 'citing_share', 'author_share'], ...regions.map(r => [r, +cite[r].toFixed(4), +auth[r].toFixed(4)])]);
        if (c.journals.length) {
            const box = document.createElement('div');
            box.className = 'table-scroll';
            box.innerHTML = '<table class="data-table"><thead><tr><th>Citing journal (not counting itself)</th><th>Citations</th><th>Share</th></tr></thead><tbody>' +
                c.journals.map(j => `<tr><td>${UIHelpers.escapeHtml(j.name)}</td><td>${j.citations.toLocaleString()}</td><td>${(100 * j.citations / c.citations).toFixed(1)}%</td></tr>`).join('') +
                '</tbody></table>';
            card.appendChild(box);
        }
    }

    // ---- Influence: move a paper ----

    renderMove(journalData, seeds, papersData) {
        const wrap = document.getElementById('inf-move-wrap');
        if (!wrap) return;
        wrap.style.display = 'none';
        if (seeds.length !== 1) return;
        const paper = ((papersData && papersData.papers) || []).find(p => String(p.pmid) === String(seeds[0].pmid));
        wrap.style.display = '';
        const range = document.getElementById('inf-move-range');
        const label = document.getElementById('inf-move-label');
        const metrics = document.getElementById('inf-move-metrics');
        const note = document.getElementById('inf-move-note');
        const usable = paper && paper.cm && paper.y && paper.m >= 1 && SiteMetrics.CITABLE.has(paper.k);
        range.disabled = !usable;
        range.value = 0;
        if (!usable) {
            label.textContent = '';
            metrics.innerHTML = '';
            note.textContent = 'This needs a citable item with monthly citation data, which the site keeps for each journal\'s 2,000 most-cited papers.';
            return;
        }
        const year = (paper.cy[paper.y + 1] || 0) >= (paper.cy[paper.y + 2] || 0) ? paper.y + 1 : paper.y + 2;
        const pubMonth = `${paper.y}-${String(paper.m).padStart(2, '0')}`;
        const card = (v, l) => `<div class="metric-card"><span class="metric-value">${v}</span><span class="metric-label">${l}</span></div>`;
        const signed = (a, b) => { const c = 100 * (b / a - 1); return `${c >= 0 ? '+' : '−'}${Math.abs(c).toFixed(1)}%`; };
        const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const monthAt = (k) => { const i = paper.y * 12 + paper.m - 1 + k; return `${MONTH_NAMES[i % 12]} ${Math.floor(i / 12)}`; };
        const update = () => {
            const k = Number(range.value);
            label.textContent = k === 0 ? `as published (${monthAt(0)})` : `${Math.abs(k)} month${Math.abs(k) === 1 ? '' : 's'} ${k < 0 ? 'earlier' : 'later'} (${monthAt(k)})`;
            const r = SiteMetrics.movedJif(journalData.timeseries, paper.cm, pubMonth, k, year);
            if (!r) { metrics.innerHTML = ''; note.textContent = `The journal has no December ${year} reading.`; return; }
            metrics.innerHTML = [
                card(r.before.toFixed(2), `Journal JIF-style rate, ${year}, as published`),
                card(r.after == null ? '—' : r.after.toFixed(2), `Moved (${r.after == null ? '—' : signed(r.before, r.after)})`),
                card(r.ownBefore.toLocaleString(), 'Paper\'s JIF-counted citations, as published'),
                card(r.ownAfter.toLocaleString(), `Moved (${r.ownBefore ? signed(r.ownBefore, r.ownAfter) : '—'})`),
            ].join('');
            note.textContent = `${year} is the year this paper drew the most citations a JIF counts. A paper that crosses into another calendar ` +
                'year changes which two years count it. Assumes it would have drawn the same citations at the same age.';
        };
        range.oninput = update;
        update();
    }
}
