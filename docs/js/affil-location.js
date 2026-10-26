/**
 * Browser port of src/pipeline/affil_location.py: the country (and US state)
 * named in a PubMed affiliation string. Tables come from affil-places.js,
 * generated from the Python module. Only country and state are returned; the
 * Python version also reads ZIP and city.
 *
 * AffilLocation.parseLocations(text) -> [{country, state}], one per
 * semicolon-separated affiliation that names a place.
 * AffilLocation.setCities(table) installs the city table (affil-cities.json,
 * fetched on demand because of its size); until then a part that stops before
 * the country gets no place.
 */

const AffilLocation = (() => {
    const T = AFFIL_PLACES;
    const PLACES = new Map(Object.entries(T.places));
    const CODES = new Map(Object.entries(T.codes));
    const AP = new Map(Object.entries(T.ap));
    const USA = 'USA';
    const COUNTRY_KEYS = new Set(T.countryKeys);
    const GEORGIA_COUNTRY = new Set(T.georgiaCountry);
    const LEBANON_NH = new Set(T.lebanonNH);
    let CITIES = new Map();

    const ascii = text => /^[\x00-\x7f]*$/.test(text) ? text
        : text.normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^\x00-\x7f]/g, '');
    const tokens = text => ascii(text).match(/[A-Za-z0-9]+/g) || [];
    const key = text => tokens(text).map(t => t.toLowerCase()).join(' ');

    const EMAIL = /electronic address\s*:?.*$|\S+@\S+/gi;
    const PHONE = /[.,;]?\s*\b(?:tel|telephone|phone|fax|ph)\b\.?\s*:?\s*\+?[\d(].*$/gi;
    const PARENS = /\(([^()]*)\)/g;
    const LEADING_MARK = /^\s*(?:\d+|[a-z])\s+(?=[A-Z])/;
    const CODE_ZIP = /\b([A-Z]{2})(\d{5})\b/g;

    function clean(text) {
        let t = (text || '').replace(EMAIL, ' ');
        t = t.replace(PHONE, ' ');
        t = t.replace(PARENS, (m, inner) => (PLACES.has(key(inner)) ? ', ' + inner : ' '));
        return t.replace(LEADING_MARK, '');
    }

    function splitParts(text) {
        return clean(text).split(';').map(s => s.replace(/^[ .,]+|[ .,]+$/g, '')).filter(Boolean);
    }

    const segments = part => part.replace(CODE_ZIP, '$1 $2').split(',').map(s => s.trim()).filter(Boolean);

    function stripPostcode(toks) {
        let i = toks.length;
        while (i && /\d/.test(toks[i - 1])) i--;
        const tail = toks.slice(i);
        let zip = null;
        if (tail.length && /^\d{5}$/.test(tail[0]) && (tail.length === 1 || /^\d{4}$/.test(tail[1]))) zip = tail[0];
        return [toks.slice(0, i), zip];
    }

    function place(toks) {
        const low = toks.map(t => t.toLowerCase());
        for (let n = Math.min(low.length, T.maxPlace); n > 0; n--) {
            const hit = PLACES.get(low.slice(-n).join(' '));
            if (hit) return [hit, toks.slice(0, -n)];
        }
        return [null, toks];
    }

    function code(toks) {
        if (!toks.length) return [null, toks];
        const whole = toks.join(' ');
        if (AP.has(whole)) return [[USA, AP.get(whole)], []];
        let last = toks[toks.length - 1], n = 1;
        const prev = toks[toks.length - 2];
        const isUpper = s => s === s.toUpperCase() && s !== s.toLowerCase();
        if (toks.length >= 2 && prev.length === 1 && last.length === 1 && isUpper(prev) && isUpper(last)) {
            last = prev + last; n = 2;
        }
        if (isUpper(last) && CODES.has(last)) return [CODES.get(last), toks.slice(0, -n)];
        return [null, toks];
    }

    const isJunk = toks => !toks.length || (toks.length === 1 && ['and', 'the'].includes(toks[0].toLowerCase()));

    function cityKey(segment) {
        const toks = tokens(segment).filter(t => !/\d/.test(t));
        return isJunk(toks) ? '' : toks.map(t => t.toLowerCase()).join(' ');
    }

    function zipState(zip5) {
        const p = parseInt(zip5.slice(0, 3), 10);
        for (const [lo, hi, st] of T.zipRanges) if (lo <= p && p <= hi) return st;
        return null;
    }

    function disambiguate(hit, rest, before, context) {
        if (hit[0] === USA && hit[1] === 'GA' && [...GEORGIA_COUNTRY].some(w => context.has(w))) return ['Georgia', null];
        if (hit[0] === 'Lebanon' && [...LEBANON_NH].some(w => context.has(w))) return [USA, 'NH'];
        if (hit[0] === 'China') {
            const [prev] = place(rest.length ? rest : (before.length ? tokens(before[before.length - 1]) : []));
            if (prev && (prev[0] === 'Hong Kong' || prev[0] === 'Macau')) return prev;
        }
        return hit;
    }

    function parsePart(part, whole) {
        const segs = segments(part);
        const context = new Set(tokens(whole || part).map(t => t.toLowerCase()));
        let country = null, state = null, zip = null;
        for (let i = segs.length - 1; i >= 0; i--) {
            let [toks, z] = stripPostcode(tokens(segs[i]));
            zip = zip || z;
            if (isJunk(toks)) continue;
            let found = false;
            if (country === null) {
                const [hit, rest] = place(toks);
                if (hit) {
                    [country, state] = disambiguate(hit, rest, segs.slice(0, i), context);
                    found = true;
                    [toks, z] = stripPostcode(rest);
                    zip = zip || z;
                }
            }
            if ((country === null || country === USA) && state === null && toks.length) {
                let [hit, rest] = code(toks);
                if (hit === null && country === USA) [hit, rest] = place(toks);
                if (hit && (country === null || (hit[0] === USA && hit[1]))) {
                    [country, state] = hit;
                    found = true;
                    toks = rest;
                }
            }
            if (!found) break;
            if (state || country !== USA) break;
        }
        if (country === null) {
            for (let i = segs.length - 1; i >= 0; i--) {
                const k = cityKey(segs[i]);
                if (!k) continue;
                const hit = CITIES.get(k);
                return hit ? { country: hit[0], state: hit[1] } : null;
            }
            return null;
        }
        if (country === USA && zip && state === null) state = zipState(zip);
        return { country, state: country === USA ? state : null };
    }

    function parseLocations(text) {
        return splitParts(text).map(p => parsePart(p, text)).filter(Boolean);
    }

    function setCities(table) { CITIES = new Map(Object.entries(table)); }

    return { parseLocations, clean, splitParts, setCities };
})();

if (typeof module !== 'undefined') module.exports = AffilLocation;
