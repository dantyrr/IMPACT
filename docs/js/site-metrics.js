/**
 * Calculations behind the paper's figures on the site. No page access here, so
 * tests/test_site_metrics_js.py can run them under node.
 *
 * "JIF-style" means the JIF formula with PubMed citations: citations in year Y to
 * citable items from Y-2 and Y-1, per item. That is the December reading of the
 * 24-month rate.
 */
const SiteMetrics = (() => {
    const CITABLE = new Set(['research', 'review', 'case_report', 'guideline']);
    const EUROPE = new Set(["Albania", "Andorra", "Austria", "Belarus", "Belgium", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Iceland", "Ireland", "Italy", "Kosovo", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Macedonia", "Malta", "Moldova", "Monaco", "Montenegro", "Netherlands", "North Macedonia", "Norway", "Poland", "Portugal", "Romania", "Russia", "San Marino", "Serbia", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "Ukraine", "United Kingdom", "Vatican City"]);
    const CHINA = new Set(["China", "Hong Kong", "Macao", "Macau"]);
    const OTHER_ASIA = new Set(["Afghanistan", "Bangladesh", "Bhutan", "Brunei", "Cambodia", "India", "Indonesia", "Japan", "Kazakhstan", "Kyrgyzstan", "Laos", "Malaysia", "Maldives", "Mongolia", "Myanmar", "Nepal", "North Korea", "Pakistan", "Philippines", "Singapore", "South Korea", "Sri Lanka", "Taiwan", "Tajikistan", "Thailand", "Turkmenistan", "Uzbekistan", "Vietnam"]);
    const REGION_ORDER = ['USA', 'Canada', 'Europe', 'China', 'Other Asia', 'Rest of world'];

    const monthIndex = (ym) => { const [y, m] = ym.split('-').map(Number); return y * 12 + m - 1; };
    const yearOf = (i) => Math.floor(i / 12);

    function regionOf(country) {
        if (country === 'USA' || country === 'Canada') return country;
        if (EUROPE.has(country)) return 'Europe';
        if (CHINA.has(country)) return 'China';
        if (OTHER_ASIA.has(country)) return 'Other Asia';
        return 'Rest of world';
    }

    /** Share of a paper's citations that fall in the two JIF years after publication. */
    function jifShare(cy, pubYear) {
        const total = Object.values(cy || {}).reduce((a, b) => a + b, 0);
        const counted = ((cy || {})[pubYear + 1] || 0) + ((cy || {})[pubYear + 2] || 0);
        return { counted, total, share: total ? counted / total : null };
    }

    /** Each December reading's JIF-style rate, with and without that year's most-cited item. */
    function topPaperSeries(papers, timeseries) {
        const out = [];
        for (const e of timeseries || []) {
            if (!e.month.endsWith('-12') || !e.citable_papers || !e.citable_citations) continue;
            const year = Number(e.month.slice(0, 4));
            let top = null, cites = 0;
            for (const p of papers || []) {
                if ((p.y !== year - 1 && p.y !== year - 2) || !CITABLE.has(p.k)) continue;
                const c = (p.cy && p.cy[year]) || 0;
                if (c > cites) { cites = c; top = p; }
            }
            if (!top) continue;
            out.push({
                year, pmid: top.pmid, title: top.t, cites,
                rate: e.citable_citations / e.citable_papers,
                rateWithout: e.citable_papers > 1 ? (e.citable_citations - cites) / (e.citable_papers - 1) : null,
                share: cites / e.citable_citations,
            });
        }
        return out;
    }

    /** Share of reviews and of other citable items published January to March, by year. June is left out of both. */
    function earlyShare(timeseries) {
        const years = new Map();
        for (const e of timeseries || []) {
            const year = Number(e.month.slice(0, 4)), month = Number(e.month.slice(5, 7));
            if (month === 6) continue;
            const t = e.pub_by_type || {};
            const reviews = t.review || 0;
            const other = (t.research || 0) + (t.case_report || 0) + (t.guideline || 0);
            const y = years.get(year) || { year, reviews: 0, other: 0, re: 0, oe: 0 };
            y.reviews += reviews; y.other += other;
            if (month <= 3) { y.re += reviews; y.oe += other; }
            years.set(year, y);
        }
        return [...years.values()].sort((a, b) => a.year - b.year).map(y => ({
            year: y.year, reviews: y.reviews, other: y.other,
            reviewsEarly: y.reviews ? y.re / y.reviews : null,
            otherEarly: y.other ? y.oe / y.other : null,
        }));
    }

    /** All-citable rate over research-only rate, minus 1. */
    function liftAt(entry) {
        const r = entry && entry.by_type && entry.by_type.research;
        if (!r || !r.papers || !r.citations || !entry.rolling_if) return null;
        return entry.rolling_if / (r.citations / r.papers) - 1;
    }

    /**
     * Moves one citable paper and all its citations by `months` (negative is earlier).
     * cm is {"YYYY-MM": count}; pubMonth is "YYYY-MM"; year is the JIF-style year to report.
     * Returns the journal's rate before and after, and the paper's own JIF-counted citations.
     */
    function movedJif(timeseries, cm, pubMonth, months, year) {
        const e = (timeseries || []).find(x => x.month === `${year}-12`);
        if (!e || !e.citable_papers) return null;
        const pub = monthIndex(pubMonth);
        const when = Object.entries(cm || {}).map(([m, n]) => [monthIndex(m), n]);
        const place = (shift) => {
            const y = yearOf(pub + shift);
            const counted = when.reduce((a, [m, n]) => a + (yearOf(m + shift) === y + 1 || yearOf(m + shift) === y + 2 ? n : 0), 0);
            const inWindow = y === year - 1 || y === year - 2;
            const here = when.reduce((a, [m, n]) => a + (yearOf(m + shift) === year ? n : 0), 0);
            return { counted, inWindow, here };
        };
        const a = place(0), b = place(months);
        const items = e.citable_papers - (a.inWindow ? 1 : 0) + (b.inWindow ? 1 : 0);
        const cites = e.citable_citations - (a.inWindow ? a.here : 0) + (b.inWindow ? b.here : 0);
        return { before: e.citable_citations / e.citable_papers, after: items ? cites / items : null, ownBefore: a.counted, ownAfter: b.counted };
    }

    /** Each region's share of fractional author credit, per year. countries is {name: {year: [papers, credit]}}. */
    function regionShares(countries, years) {
        const out = Object.fromEntries(REGION_ORDER.map(r => [r, years.map(() => 0)]));
        const totals = years.map(() => 0);
        for (const [country, byYear] of Object.entries(countries || {})) {
            const region = regionOf(country);
            years.forEach((y, i) => {
                const v = byYear[y];
                if (v) { out[region][i] += v[1]; totals[i] += v[1]; }
            });
        }
        for (const r of REGION_ORDER) out[r] = out[r].map((v, i) => (totals[i] ? v / totals[i] : null));
        return out;
    }

    const REASON_LABELS = {
        paper_mill: 'paper mill', peer_review: 'concerns about peer review', image: 'image problems',
        plagiarism_duplication: 'plagiarism or duplication', fabrication_misconduct: 'fabrication or misconduct',
        honest_error: 'reported errors', generated_content: 'computer-generated content',
    };
    const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

    /** The wording for a retraction record: {text, split}. split is the year to divide the chart at, or null. */
    function retractionBanner(record) {
        if (!record) return null;
        const when = record.y ? ` ${record.m ? `${MONTHS[record.m - 1]} ` : ''}${record.y}` : '';
        const status = record.st === 'reinstated' ? `Retracted${when}, later reinstated.`
            : record.y ? `Retracted${when}.` : 'Retracted, date not known.';
        const reasons = (record.r || []).map(r => REASON_LABELS[r] || r).join('; ');
        const source = record.s === 'rw' ? 'Retraction Watch' : 'PubMed';
        return {
            text: `${status}${reasons ? ` Reasons listed: ${reasons}.` : ''} Source: ${source}.`,
            split: record.st !== 'reinstated' && record.y ? record.y : null,
        };
    }

    /** Share of calendar `year` inside a paper's 24 months from publication. Adds up to 2 over the years. */
    function paperWindowShare(pubYear, pubMonth, year) {
        const start = pubYear * 12 + pubMonth - 1;
        const months = Math.max(0, Math.min(year * 12 + 12, start + 24) - Math.max(year * 12, start));
        return months / 12;
    }

    /**
     * A journal's guidelines and listed series papers by publication month: [{x, n, v}], where x is 0-11, or 12 for
     * no month, and v is mean citations in the first 24 months. Only papers in the journal's papers file are seen.
     */
    function reportMonths(papers, pmids, from, to) {
        const want = new Set((pmids || []).map(Number));
        const groups = new Map();
        for (const p of papers || []) {
            if ((p.k !== 'guideline' && !want.has(Number(p.pmid))) || !(p.y >= from && p.y <= to)) continue;
            const x = p.m >= 1 ? p.m - 1 : 12;
            const start = p.y * 12 + (p.m >= 1 ? p.m : 6) - 1;
            const cites = Object.entries(p.cm || {}).reduce((a, [m, n]) => {
                const t = monthIndex(m);
                return t >= start && t < start + 24 ? a + n : a;
            }, 0);
            const g = groups.get(x) || { x, n: 0, sum: 0 };
            g.n += 1;
            g.sum += cites;
            groups.set(x, g);
        }
        return [...groups.values()].sort((a, b) => a.x - b.x).map(g => ({ x: g.x, n: g.n, v: g.sum / g.n }));
    }

    /** The top n papers that count in the rate, by average share or by lifetime citations. */
    function rankDrivers(rows, sort, n) {
        const key = sort === 'lifetime' ? (r => r.p.c || 0) : (r => r.share);
        return rows.filter(r => r.share > 0).sort((x, y) => key(y) - key(x)).slice(0, n);
    }

    /** Where a percentile sits, in words that never claim a journal beats 100% of journals. */
    function rankPhrase(pct) {
        return pct >= 99.5 ? 'among the highest' : pct < 0.5 ? 'among the lowest' : `higher than ${pct.toFixed(0)}%`;
    }

    /** Citations in the years before, during and after the year retracted. */
    function beforeAfter(cy, split) {
        const out = { before: 0, during: 0, after: 0 };
        for (const [y, n] of Object.entries(cy || {})) out[Number(y) < split ? 'before' : Number(y) > split ? 'after' : 'during'] += n;
        return out;
    }

    /**
     * The 24-month rate at each reading without the listed papers. A reading at month t counts citations in
     * t-11..t to items from t-35..t-12. Papers not in the journal's papers file stay in, and are counted in `missing`.
     */
    function rateWithout(timeseries, papers, pmids) {
        const want = new Set(pmids.map(Number));
        const found = (papers || []).filter(p => want.has(Number(p.pmid)) && p.y);
        const items = found.map(p => ({
            pub: p.y * 12 + (p.m >= 1 ? p.m : 6) - 1,
            when: Object.entries(p.cm || {}).map(([m, n]) => [monthIndex(m), n]),
        }));
        const rows = (timeseries || []).filter(e => e.citable_papers).map(e => {
            const t = monthIndex(e.month);
            let n = e.citable_papers, c = e.citable_citations;
            for (const it of items) {
                if (it.pub < t - 35 || it.pub > t - 12) continue;
                n -= 1;
                for (const [m, k] of it.when) if (m >= t - 11 && m <= t) c -= k;
            }
            return { month: e.month, rate: n > 0 ? c / n : null };
        });
        return { rows, removed: found.length, missing: want.size - found.length };
    }

    return { CITABLE, REGION_ORDER, regionOf, regionShares, jifShare, topPaperSeries, earlyShare, liftAt, movedJif, retractionBanner, rankPhrase, beforeAfter, rateWithout, paperWindowShare, reportMonths, rankDrivers };
})();

if (typeof module !== 'undefined') module.exports = SiteMetrics;
