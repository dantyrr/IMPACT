/**
 * Cloudflare Worker — IMPACT Author Profile API
 *
 * Handles saving/reading author profiles to/from R2.
 *
 * Routes:
 *   PUT /profiles/:slug  — Create or update a profile
 *   GET /profiles/:slug  — Read a profile (fallback; R2 public URL is primary)
 *
 * Environment bindings (set in wrangler.toml):
 *   BUCKET — R2 bucket binding
 */

const CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
};

const MAX_PMIDS = 5000;
const MAX_SLUG_LENGTH = 100;
const SLUG_PATTERN = /^[A-Za-z0-9_.-]+$/;

export default {
    async fetch(request, env) {
        if (request.method === 'OPTIONS') {
            return new Response(null, { status: 204, headers: CORS_HEADERS });
        }

        const url = new URL(request.url);
        const match = url.pathname.match(/^\/profiles\/([^/]+)$/);

        if (!match) {
            return json({ error: 'Not found' }, 404);
        }

        const slug = decodeURIComponent(match[1]).replace(/\.json$/, '');

        if (!SLUG_PATTERN.test(slug) || slug.length > MAX_SLUG_LENGTH) {
            return json({ error: 'Invalid profile name. Use letters, numbers, underscores, hyphens, or dots.' }, 400);
        }

        if (request.method === 'PUT') {
            return handlePut(request, env, slug);
        }

        if (request.method === 'GET') {
            return handleGet(env, slug);
        }

        return json({ error: 'Method not allowed' }, 405);
    },
};

async function handlePut(request, env, slug) {
    let body;
    try {
        body = await request.json();
    } catch {
        return json({ error: 'Invalid JSON body' }, 400);
    }

    if (!body.pmids || !Array.isArray(body.pmids) || !body.pmids.length) {
        return json({ error: 'pmids array is required' }, 400);
    }

    if (body.pmids.length > MAX_PMIDS) {
        return json({ error: `Too many PMIDs (max ${MAX_PMIDS})` }, 400);
    }

    // Validate PMIDs are numeric strings
    const pmids = body.pmids.map(String).filter(p => /^\d+$/.test(p));
    if (!pmids.length) {
        return json({ error: 'No valid PMIDs found' }, 400);
    }

    const key = `profiles/${slug}.json`;

    // Preserve created date from existing profile
    let created = new Date().toISOString().slice(0, 10);
    try {
        const existing = await env.BUCKET.get(key);
        if (existing) {
            const prev = await existing.json();
            if (prev.created) created = prev.created;
        }
    } catch {
        // No existing profile — that's fine
    }

    const profile = {
        name: (body.name || slug.replace(/_/g, ' ')).slice(0, 200),
        slug: slug,
        pmids: pmids,
        created: created,
        updated: new Date().toISOString().slice(0, 10),
    };

    await env.BUCKET.put(key, JSON.stringify(profile, null, 2), {
        httpMetadata: {
            contentType: 'application/json',
            cacheControl: 'public, max-age=3600',
        },
    });

    return json({ ok: true, slug: slug, pmids: pmids.length, url: `profiles/${slug}.json` }, 200);
}

async function handleGet(env, slug) {
    const obj = await env.BUCKET.get(`profiles/${slug}.json`);
    if (!obj) {
        return json({ error: 'Profile not found' }, 404);
    }

    const data = await obj.text();
    return new Response(data, {
        status: 200,
        headers: {
            'Content-Type': 'application/json',
            'Cache-Control': 'public, max-age=3600',
            ...CORS_HEADERS,
        },
    });
}

function json(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status,
        headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
    });
}
