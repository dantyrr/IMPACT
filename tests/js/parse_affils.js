// Reads affiliation strings (one JSON string per line) on stdin; prints the
// JSON parse result per line. Used by tests/test_affil_location_js.py.
const fs = require('fs');
const path = require('path');
const root = path.join(__dirname, '..', '..', 'docs', 'js');
global.AFFIL_PLACES = new Function(fs.readFileSync(path.join(root, 'affil-places.js'), 'utf8') + '; return AFFIL_PLACES;')();
const AffilLocation = require(path.join(root, 'affil-location.js'));
AffilLocation.setCities(JSON.parse(fs.readFileSync(path.join(root, '..', 'geo', 'affil-cities.json'), 'utf8')));
const lines = fs.readFileSync(0, 'utf8').split('\n').filter(Boolean);
for (const line of lines) {
    const locs = AffilLocation.parseLocations(JSON.parse(line));
    console.log(JSON.stringify(locs.map(l => [l.country, l.state])));
}
