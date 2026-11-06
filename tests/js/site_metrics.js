// Reads {"fn": name, "args": [...]} per line on stdin; prints each result as JSON.
// Used by tests/test_site_metrics_js.py.
const fs = require('fs');
const path = require('path');
const SiteMetrics = require(path.join(__dirname, '..', '..', 'docs', 'js', 'site-metrics.js'));
for (const line of fs.readFileSync(0, 'utf8').split('\n').filter(Boolean)) {
    const { fn, args } = JSON.parse(line);
    const out = SiteMetrics[fn](...args);
    console.log(JSON.stringify(out === undefined ? null : out));
}
