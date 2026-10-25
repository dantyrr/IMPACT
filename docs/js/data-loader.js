/**
 * IMPACT Data Loader
 * Fetches JSON data from Cloudflare R2 (production) or local data/ (dev).
 *
 * Detection: if the page is served from localhost/file://, uses local data/.
 * Otherwise uses R2_BASE_URL.
 */

const R2_BASE_URL = 'https://pub-4368cf00a45748488f64d2b648550d4d.r2.dev';
// Pipeline exports live under a versioned prefix in R2 (mirrors Python config.R2_DATA_PREFIX),
// so a new export format never mixes with files from the old one. Local dev paths have no prefix.
const R2_DATA_PREFIX = 'v2';
// Update this after deploying the Cloudflare Worker (npx wrangler deploy --config workers/wrangler.toml)
const PROFILE_WORKER_URL = 'https://impact-profiles.dantyrr.workers.dev';

/** Undo delta encoding: [a, b-a, c-b, ...] -> [a, b, c, ...]. Missing/empty -> []. */
function decodeDeltas(deltas) {
    const out = [];
    let total = 0;
    for (const d of deltas || []) {
        total += d;
        out.push(total);
    }
    return out;
}

class DataLoader {
    constructor() {
        const isLocal = location.hostname === 'localhost' ||
                        location.hostname === '127.0.0.1' ||
                        location.protocol === 'file:';
        this.baseUrl = isLocal ? 'data' : `${R2_BASE_URL}/${R2_DATA_PREFIX}`;
        // Author profiles are user-saved by the Worker at the bucket root (not a pipeline
        // export), so their public fallback URL is not versioned.
        this.profileBaseUrl = isLocal ? 'data' : R2_BASE_URL;
        this.workerUrl = isLocal ? null : PROFILE_WORKER_URL;
        this.cache = {};
    }

    async loadIndex() {
        return this._fetch(`${this.baseUrl}/index.json`);
    }

    async loadJournal(slug) {
        return this._fetch(`${this.baseUrl}/journals/${slug}.json`);
    }

    async loadAuthor(slug) {
        return this._fetch(`${this.baseUrl}/authors/${slug}.json`);
    }

    async loadPapers(slug) {
        return this._fetch(`${this.baseUrl}/papers/${slug}.json`);
    }

    /**
     * Per-journal citable / non-citable PMID lists, as Sets of numbers.
     * The file stores each list sorted ascending and delta-encoded
     * (first value absolute, then successive differences).
     */
    async loadClasses(slug) {
        const url = `${this.baseUrl}/classes/${slug}.json`;
        const key = `classes:${url}`;
        if (this.cache[key]) return this.cache[key];
        const raw = await this._fetch(url);
        const decoded = {
            citable: new Set(decodeDeltas(raw.citable)),
            noncitable: new Set(decodeDeltas(raw.noncitable)),
        };
        this.cache[key] = decoded;
        return decoded;
    }

    async loadProfile(slug) {
        // Try Worker first (has freshest data), fall back to R2 public URL
        if (this.workerUrl) {
            try {
                const resp = await fetch(`${this.workerUrl}/profiles/${encodeURIComponent(slug)}`);
                if (resp.ok) return await resp.json();
            } catch { /* fall through */ }
        }
        const url = `${this.profileBaseUrl}/profiles/${slug}.json`;
        const resp = await fetch(url);
        if (!resp.ok) return null;
        return await resp.json();
    }

    async saveProfile(profile) {
        if (!this.workerUrl) {
            throw new Error('Profile saving requires the Cloudflare Worker (not available in dev mode).');
        }
        const resp = await fetch(`${this.workerUrl}/profiles/${encodeURIComponent(profile.slug)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(profile),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
        return data;
    }

    async _fetch(url) {
        if (this.cache[url]) return this.cache[url];
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
        const data = await response.json();
        this.cache[url] = data;
        return data;
    }
}

const dataLoader = new DataLoader();
