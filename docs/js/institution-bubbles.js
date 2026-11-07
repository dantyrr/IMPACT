/**
 * IMPACT moving bubble plot: every large institution's share of all PubMed papers against its share of flagship papers.
 * Data: institution_bubbles.json from scripts/export_site_extras.py, yearly counts summed here into rolling windows.
 * Drawn on one canvas, because Chart.js can't move this many dots smoothly.
 */
class InstitutionBubbles {
    static X = [4e-6, 1.3e-2];
    static Y = [3.6e-5, 3.2e-2];
    static STEP_MS = 800;
    static MAX_PICKS = 6;
    static INK = '#222222';
    static MUTED = '#666666';

    constructor(defaults) {
        this.defaults = defaults;
        this.data = null;
        this.picks = null;
        this.pos = 0;
        this.timer = null;
        this.observer = null;
    }

    /** Build the card's controls and load the data. */
    async mount(card) {
        this.card = card;
        card.insertAdjacentHTML('beforeend', `
            <div class="ib-search">
                <input type="search" class="ib-input" placeholder="Search for an institution" aria-label="Search for an institution" autocomplete="off">
                <ul class="ib-results" role="listbox" hidden></ul>
            </div>
            <div class="ib-chips"></div>
            <div class="ib-player">
                <button type="button" class="ib-play">Play</button>
                <input type="range" class="ib-slider" min="0" step="1" aria-label="Five-year window">
                <span class="ib-label"></span>
            </div>
            <div class="ib-stage"><canvas role="img" aria-label="Bubble plot of institutions' share of all PubMed papers against their share of flagship papers"></canvas><div class="ib-tip" hidden></div></div>
            <div class="ib-legend"></div>
            <div class="download-bar"><span class="download-label">Download:</span><button class="download-btn" data-fmt="png">PNG</button><button class="download-btn" data-fmt="csv">CSV</button></div>`);
        this.canvas = card.querySelector('canvas');
        this.tip = card.querySelector('.ib-tip');
        this.slider = card.querySelector('.ib-slider');
        this.label = card.querySelector('.ib-label');
        this.playBtn = card.querySelector('.ib-play');
        this.chips = card.querySelector('.ib-chips');
        this.input = card.querySelector('.ib-input');
        this.results = card.querySelector('.ib-results');
        if (!this.data) {
            this.label.textContent = 'Loading…';
            try {
                this._prepare(await dataLoader.loadInstitutionBubbles());
            } catch (e) {
                console.warn('Institution bubbles not available:', e.message);
                this.label.textContent = 'This chart could not be loaded.';
                return;
            }
        }
        this._wire();
        this._legend();
        this._chips();
        this.observer = new ResizeObserver(() => this._layout());
        this.observer.observe(card.querySelector('.ib-stage'));
        this._layout();
    }

    /** Stop the animation before the card is removed. */
    destroy() {
        this._stop();
        if (this.observer) this.observer.disconnect();
        this.observer = null;
    }

    _prepare(data) {
        this.data = data;
        const size = data.window;
        this.windows = SiteMetrics.rollingWindows(data.firstYear, data.lastYear, size);
        this.rows = data.institutions;
        this.searchRows = this.rows.map(r => [r[0], r[2].reduce((a, b) => a + b, 0)]);
        // points[w][k]: institution k in window w.
        this.points = this.windows.map(w => this.rows.map(r => SiteMetrics.windowPoint(r[2], r[3], data.denomAll, data.denomFlag, w.start, size)));
        this.pos = this.windows.length - 1;
        if (!this.picks) this.picks = this.defaults.map(n => this.rows.findIndex(r => r[0] === n)).filter(i => i >= 0);
        // China last, so its dots sit on top, as in the paper.
        this.order = data.regions.map((_, i) => i).sort((a, b) => (data.regions[a].name === 'China') - (data.regions[b].name === 'China'));
    }

    _wire() {
        this.slider.max = this.windows.length - 1;
        this.slider.value = this.pos;
        this.slider.oninput = () => { this._stop(); this.pos = Number(this.slider.value); this._draw(); };
        this.playBtn.onclick = () => (this.timer ? this._stop() : this._play());
        this.input.oninput = () => this._search();
        this.input.onkeydown = (e) => this._searchKey(e);
        this.input.onblur = () => setTimeout(() => { this.results.hidden = true; }, 150);
        this.canvas.onmousemove = (e) => this._hover(e);
        this.canvas.onmouseleave = () => { this.tip.hidden = true; this.canvas.style.cursor = ''; };
        this.canvas.onclick = (e) => {
            const k = this._at(e);
            if (k != null) this._toggle(k);
        };
        this.card.querySelector('[data-fmt="png"]').onclick = () => this._png();
        this.card.querySelector('[data-fmt="csv"]').onclick = () => this._csv();
    }

    _legend() {
        const box = this.card.querySelector('.ib-legend');
        this.data.regions.forEach(({ name, color }) => {
            const item = document.createElement('span');
            item.className = 'ib-key';
            item.innerHTML = '<i></i>';
            item.firstChild.style.background = color;
            item.append(name);
            box.appendChild(item);
        });
    }

    // ---- search and picks

    _search() {
        const hits = SiteMetrics.searchInstitutions(this.searchRows, this.input.value, 8);
        this.hits = hits;
        this.active = 0;
        this.results.innerHTML = '';
        hits.forEach((k, i) => {
            const li = document.createElement('li');
            li.setAttribute('role', 'option');
            li.textContent = this.rows[k][0];
            const place = document.createElement('small');
            place.textContent = ` ${this.data.regions[this.rows[k][1]].name}`;
            li.appendChild(place);
            li.classList.toggle('active', i === 0);
            li.onmousedown = (e) => { e.preventDefault(); this._choose(k); };
            this.results.appendChild(li);
        });
        if (this.input.value.trim() && !hits.length) {
            const li = document.createElement('li');
            li.className = 'ib-none';
            li.textContent = 'No match. Institutions need 200 first-author papers in 2001–25.';
            this.results.appendChild(li);
        }
        this.results.hidden = !this.input.value.trim();
    }

    _searchKey(e) {
        if (e.key === 'Escape') { this.results.hidden = true; return; }
        if (!this.hits || !this.hits.length) return;
        if (e.key === 'Enter') { e.preventDefault(); this._choose(this.hits[this.active]); return; }
        const step = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0;
        if (!step) return;
        e.preventDefault();
        this.active = (this.active + step + this.hits.length) % this.hits.length;
        [...this.results.children].forEach((li, i) => li.classList.toggle('active', i === this.active));
    }

    _choose(k) {
        this.input.value = '';
        this.results.hidden = true;
        this.hits = [];
        if (!this.picks.includes(k)) this._toggle(k);
    }

    _toggle(k) {
        const at = this.picks.indexOf(k);
        if (at >= 0) this.picks.splice(at, 1);
        else {
            this.picks.push(k);
            if (this.picks.length > InstitutionBubbles.MAX_PICKS) this.picks.shift();
        }
        this._chips();
        this._draw();
    }

    _chips() {
        this.chips.innerHTML = '';
        this.picks.forEach((k) => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'ib-chip';
            b.textContent = `${this.rows[k][0]} ×`;
            b.setAttribute('aria-label', `Remove ${this.rows[k][0]}`);
            b.onclick = () => this._toggle(k);
            this.chips.appendChild(b);
        });
    }

    // ---- layout and scales

    _layout() {
        const stage = this.canvas.parentElement;
        const w = stage.clientWidth;
        if (!w) return;
        const h = Math.max(360, Math.min(640, Math.round(w * 0.72)));
        const dpr = window.devicePixelRatio || 1;
        this.w = w;
        this.h = h;
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.height = `${h}px`;
        this.canvas.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
        const small = w < 520;
        this.small = small;
        this.tip.hidden = true;
        this.box = { left: 58, right: w - 10, top: 10, bottom: h - 66 };
        this.strip = this.box.bottom + 13;
        const unit = Math.sqrt(w / 900);
        this.dot = (f) => (f > 0 ? 1.4 + 0.42 * unit * Math.sqrt(f) : 1.2);
        // Every window's pixels, once: the animation only blends between them.
        this.px = this.points.map(p => Float32Array.from(p, q => (q.papers ? this._sx(q.x) : NaN)));
        this.py = this.points.map(p => Float32Array.from(p, q => (q.flagship ? this._sy(q.y) : this.strip)));
        this.pr = this.points.map(p => Float32Array.from(p, q => this.dot(q.flagship)));
        this._draw();
    }

    _sx(v) {
        const [a, b] = InstitutionBubbles.X, { left, right } = this.box;
        return left + (Math.log(v / a) / Math.log(b / a)) * (right - left);
    }

    _sy(v) {
        const [a, b] = InstitutionBubbles.Y, { top, bottom } = this.box;
        return bottom - (Math.log(v / a) / Math.log(b / a)) * (bottom - top);
    }

    /** Institution k at the current position, or null if it has no papers around then. */
    _where(k) {
        const i = Math.floor(this.pos), j = Math.min(i + 1, this.windows.length - 1), t = this.pos - i;
        let x0 = this.px[i][k], x1 = this.px[j][k];
        if (Number.isNaN(x0) && Number.isNaN(x1)) return null;
        if (Number.isNaN(x0)) x0 = x1;
        if (Number.isNaN(x1)) x1 = x0;
        return { x: x0 + (x1 - x0) * t, y: this.py[i][k] + (this.py[j][k] - this.py[i][k]) * t, r: this.pr[i][k] + (this.pr[j][k] - this.pr[i][k]) * t };
    }

    // ---- drawing

    _draw() {
        if (!this.w) return;
        const c = this.canvas.getContext('2d');
        c.clearRect(0, 0, this.w, this.h);
        c.fillStyle = '#ffffff';
        c.fillRect(0, 0, this.w, this.h);
        this._axes(c);
        this._dots(c);
        this._trails(c);
        this._readout(c);
        const w = this.windows[Math.round(this.pos)];
        this.label.textContent = w.label;
        if (!this.timer) this.slider.value = Math.round(this.pos);
    }

    _axes(c) {
        const { left, right, top, bottom } = this.box, { INK, MUTED } = InstitutionBubbles;
        c.font = '12px system-ui, sans-serif';
        c.lineWidth = 1;
        c.strokeStyle = '#E6E6E6';
        c.fillStyle = MUTED;
        c.textAlign = 'center';
        c.textBaseline = 'top';
        [1e-5, 1e-4, 1e-3, 1e-2].forEach((v) => {
            const x = this._sx(v);
            c.beginPath(); c.moveTo(x, top); c.lineTo(x, this.strip + 6); c.stroke();
            c.fillText(`${+(v * 100).toFixed(3)}%`, x, this.strip + 9);
        });
        c.textAlign = 'right';
        c.textBaseline = 'middle';
        [1e-4, 1e-3, 1e-2].forEach((v) => {
            const y = this._sy(v);
            c.beginPath(); c.moveTo(left, y); c.lineTo(right, y); c.stroke();
            c.fillText(`${+(v * 100).toFixed(2)}%`, left - 6, y);
        });
        c.fillText('None', left - 6, this.strip);
        c.strokeStyle = '#BBBBBB';
        c.beginPath(); c.moveTo(left, top); c.lineTo(left, this.strip + 6); c.lineTo(right, this.strip + 6); c.stroke();
        // Equal share: a dashed line where the two shares match.
        const lo = 3.6e-5, hi = 1.3e-2;
        c.strokeStyle = INK;
        c.setLineDash([5, 4]);
        c.beginPath(); c.moveTo(this._sx(lo), this._sy(lo)); c.lineTo(this._sx(hi), this._sy(hi)); c.stroke();
        c.setLineDash([]);
        c.fillStyle = INK;
        c.textAlign = 'center';
        c.textBaseline = 'alphabetic';
        c.fillText('Share of all PubMed papers', (left + right) / 2, this.h - 8);
        c.save();
        c.translate(13, (top + bottom) / 2);
        c.rotate(-Math.PI / 2);
        c.fillText('Share of papers in five flagship journals', 0, 0);
        c.restore();
    }

    _dots(c) {
        const regions = this.data.regions, { left, right, top } = this.box;
        c.save();
        c.beginPath();
        c.rect(left + 1, top, right - left, this.strip + 6 - top);
        c.clip();
        for (const r of this.order) {
            c.fillStyle = regions[r].color;
            for (const zero of [true, false]) {
                c.globalAlpha = zero ? 0.28 : 0.6;
                for (let k = 0; k < this.rows.length; k++) {
                    if (this.rows[k][1] !== r) continue;
                    const p = this._where(k);
                    if (!p || (p.y === this.strip) !== zero) continue;
                    c.beginPath();
                    c.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                    c.fill();
                }
            }
        }
        c.restore();
    }

    /** Each picked institution's path up to now, then a ring and its name. */
    _trails(c) {
        const { INK } = InstitutionBubbles;
        const labels = [];
        this.picks.forEach((k) => {
            const end = this._where(k);
            if (!end) return;
            c.strokeStyle = INK;
            c.globalAlpha = 0.55;
            c.lineWidth = 1.2;
            c.beginPath();
            let started = false;
            for (let w = 0; w <= Math.floor(this.pos); w++) {
                if (Number.isNaN(this.px[w][k])) continue;
                if (started) c.lineTo(this.px[w][k], this.py[w][k]); else c.moveTo(this.px[w][k], this.py[w][k]);
                started = true;
            }
            if (started) c.lineTo(end.x, end.y);
            c.stroke();
            c.globalAlpha = 1;
            c.lineWidth = 1.5;
            c.beginPath();
            c.arc(end.x, end.y, end.r + 1.5, 0, Math.PI * 2);
            c.stroke();
            labels.push({ text: this.rows[k][0], ...end });
        });
        c.font = '600 12px system-ui, sans-serif';
        c.textBaseline = 'middle';
        c.lineJoin = 'round';
        labels.sort((a, b) => a.y - b.y);
        let last = -Infinity;
        labels.forEach((l) => {
            const y = Math.max(l.y, last + 14);
            last = y;
            const room = this.box.right - l.x - l.r - 6 > c.measureText(l.text).width;
            c.textAlign = room ? 'left' : 'right';
            const x = room ? l.x + l.r + 6 : l.x - l.r - 6;
            c.strokeStyle = 'rgba(255,255,255,0.9)';
            c.lineWidth = 3.5;
            c.strokeText(l.text, x, y);
            c.fillStyle = INK;
            c.fillText(l.text, x, y);
        });
    }

    /** The window, and the USA's and China's shares, as in the paper's panels. */
    _readout(c) {
        const { INK, MUTED } = InstitutionBubbles, d = this.data;
        const w = this.windows[Math.round(this.pos)];
        const share = (tab, name) => {
            const r = d.regions.findIndex(x => x.name === name);
            const all = tab.reduce((n, row) => n + SiteMetrics.windowSum(row, w.start, d.window), 0);
            const v = SiteMetrics.windowSum(tab[r], w.start, d.window) / all;
            return `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`;
        };
        const col = this.small ? { all: 54, name: 118, size: 18 } : { all: 72, name: 150, size: 26 };
        const x = this.box.right - 6, y = this.box.bottom - 50;
        // A backing, so the numbers stay readable where dots run under them.
        c.fillStyle = 'rgba(255,255,255,0.85)';
        c.fillRect(x - col.name - 6, y - col.size - 20, col.name + 10, col.size + 66);
        c.textBaseline = 'alphabetic';
        c.textAlign = 'right';
        c.fillStyle = INK;
        c.font = `600 ${col.size}px system-ui, sans-serif`;
        c.fillText(w.label, x, y - 18);
        c.font = '600 12px system-ui, sans-serif';
        c.fillText('All', x - col.all, y);
        c.fillText('Flagship', x, y);
        c.font = '12px system-ui, sans-serif';
        ['USA', 'China'].forEach((name, i) => {
            const row = y + 18 * (i + 1);
            c.fillStyle = MUTED;
            c.textAlign = 'left';
            c.fillText(name, x - col.name, row);
            c.fillStyle = INK;
            c.textAlign = 'right';
            c.fillText(share(d.regionAll, name), x - col.all, row);
            c.fillText(share(d.regionFlag, name), x, row);
        });
    }

    // ---- playing

    _play() {
        if (this.pos >= this.windows.length - 1) this.pos = 0;
        const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        let then = null;   // from the first frame's own clock: it can run slightly behind performance.now()
        this.playBtn.textContent = 'Pause';
        const tick = (now) => {
            this.pos = Math.min(this.windows.length - 1, this.pos + (then == null ? 0 : now - then) / InstitutionBubbles.STEP_MS);
            then = now;
            const shown = this.pos;
            if (still) this.pos = Math.floor(this.pos);
            this.slider.value = Math.round(this.pos);
            this._draw();
            this.pos = shown;
            if (this.pos >= this.windows.length - 1) { this._stop(); return; }
            this.timer = requestAnimationFrame(tick);
        };
        this.timer = requestAnimationFrame(tick);
    }

    _stop() {
        if (this.timer) cancelAnimationFrame(this.timer);
        this.timer = null;
        if (this.playBtn) this.playBtn.textContent = 'Play';
        if (this.windows) { this.pos = Math.round(this.pos); this._draw(); }
    }

    // ---- hover

    _at(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left, y = e.clientY - rect.top;
        let best = null, dist = Infinity;
        for (let k = 0; k < this.rows.length; k++) {
            const p = this._where(k);
            if (!p) continue;
            const d = Math.hypot(p.x - x, p.y - y);
            if (d < Math.max(p.r + 2, 6) && d < dist) { best = k; dist = d; }
        }
        return best;
    }

    _hover(e) {
        const k = this._at(e);
        this.canvas.style.cursor = k == null ? '' : 'pointer';
        if (k == null) { this.tip.hidden = true; return; }
        const w = this.windows[Math.round(this.pos)], q = this.points[Math.round(this.pos)][k];
        this.tip.textContent = '';
        const name = document.createElement('strong');
        name.textContent = this.rows[k][0];
        this.tip.append(name, document.createElement('br'), `${this.data.regions[this.rows[k][1]].name}, ${w.label}`, document.createElement('br'),
            `${q.papers.toLocaleString()} papers (${(q.x * 100).toFixed(3)}%)`, document.createElement('br'), `${q.flagship.toLocaleString()} flagship papers (${(q.y * 100).toFixed(2)}%)`);
        this.tip.hidden = false;
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left, y = e.clientY - rect.top;
        this.tip.style.left = `${Math.min(x + 12, this.w - this.tip.offsetWidth - 4)}px`;
        this.tip.style.top = `${Math.max(4, y - this.tip.offsetHeight - 8)}px`;
    }

    // ---- downloads

    _save(blob, name) {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = name;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    _png() {
        this.canvas.toBlob(b => this._save(b, `institutions-${this.windows[Math.round(this.pos)].from}.png`));
    }

    /** Every listed institution in the window on show, with the picked ones in every window after them. */
    _csv() {
        const at = Math.round(this.pos), quote = t => `"${t.replace(/"/g, '""')}"`;
        const line = (k, w) => {
            const q = this.points[w][k];
            return [quote(this.rows[k][0]), this.data.regions[this.rows[k][1]].name, this.windows[w].label, q.papers, q.flagship, q.x.toFixed(6), q.y.toFixed(6)].join(',');
        };
        const rows = this.rows.map((_, k) => line(k, at));
        this.picks.forEach(k => this.windows.forEach((_, w) => { if (w !== at) rows.push(line(k, w)); }));
        const text = ['institution,region,window,papers,flagship_papers,share_all,share_flagship', ...rows].join('\n');
        this._save(new Blob([text], { type: 'text/csv' }), `institutions-${this.windows[at].from}.csv`);
    }
}
