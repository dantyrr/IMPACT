/**
 * IMPACT Data Loader
 * Fetches JSON data from Cloudflare R2 (production) or local data/ (dev).
 *
 * Detection: if the page is served from localhost/file://, uses local data/.
 * Otherwise uses R2_BASE_URL.
 */

const R2_BASE_URL = 'https://pub-4368cf00a45748488f64d2b648550d4d.r2.dev';
// Update this after deploying the Cloudflare Worker (npx wrangler deploy --config workers/wrangler.toml)
const PROFILE_WORKER_URL = 'https://impact-profiles.dantyrr.workers.dev';

class DataLoader {
    constructor() {
        const isLocal = location.hostname === 'localhost' ||
                        location.hostname === '127.0.0.1' ||
                        location.protocol === 'file:';
        this.baseUrl = isLocal ? 'data' : R2_BASE_URL;
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

    async loadProfile(slug) {
        // Try Worker first (has freshest data), fall back to R2 public URL
        if (this.workerUrl) {
            try {
                const resp = await fetch(`${this.workerUrl}/profiles/${encodeURIComponent(slug)}`);
                if (resp.ok) return await resp.json();
            } catch { /* fall through */ }
        }
        const url = `${this.baseUrl}/profiles/${slug}.json`;
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
