"""Per-journal geography counts: countries, US states and their co-occurring pairs.

Each paper contributes its distinct countries (and, when it has a US affiliation,
its distinct US states). A region gets one "papers involving" count per paper
and a fractional credit of 1/k, where k is the paper's number of regions at that
level. Pairs count papers that involve both regions; papers with more than
max_pair_regions regions are left out of the pairs so consortium papers do not
dominate them.
"""

from collections import defaultdict
from itertools import combinations
from typing import Dict, Hashable, Iterable, List

MAX_PAIR_REGIONS = 10


def _region_table():
    return defaultdict(lambda: defaultdict(lambda: [0, 0.0]))


class _Bucket:
    __slots__ = ("papers", "intl", "us", "countries", "states", "cpairs", "spairs")

    def __init__(self):
        self.papers = defaultdict(int)
        self.intl = defaultdict(int)
        self.us = defaultdict(int)
        self.countries = _region_table()
        self.states = _region_table()
        self.cpairs = defaultdict(lambda: defaultdict(int))
        self.spairs = defaultdict(lambda: defaultdict(int))


def _add_regions(table, pairs, year, regions, max_pair):
    share = 1.0 / len(regions)
    for r in regions:
        cell = table[r][year]
        cell[0] += 1
        cell[1] += share
    if 1 < len(regions) <= max_pair:
        for a, b in combinations(regions, 2):
            pairs[f"{a}|{b}"][year] += 1


def _counts(d):
    return {str(y): n for y, n in sorted(d.items())}


def _regions(table):
    return {r: {str(y): [c[0], round(c[1], 3)] for y, c in sorted(by_year.items())}
            for r, by_year in sorted(table.items())}


def _pairs(table):
    return {p: _counts(by_year) for p, by_year in sorted(table.items())}


class GeoAggregator:
    def __init__(self, max_pair_regions: int = MAX_PAIR_REGIONS):
        self.max_pair = max_pair_regions
        self._buckets: Dict[Hashable, _Bucket] = {}

    def add(self, key: Hashable, year: int, countries: Iterable[str], states: Iterable[str]) -> None:
        """Record one paper. countries and states are its distinct regions."""
        countries = sorted(set(countries))
        if not countries:
            return
        b = self._buckets.get(key)
        if b is None:
            b = self._buckets[key] = _Bucket()
        b.papers[year] += 1
        if len(countries) > 1:
            b.intl[year] += 1
        _add_regions(b.countries, b.cpairs, year, countries, self.max_pair)
        states = sorted(set(states))
        if states:
            b.us[year] += 1
            _add_regions(b.states, b.spairs, year, states, self.max_pair)

    def keys(self) -> List[Hashable]:
        return list(self._buckets)

    def export(self, key: Hashable) -> Dict:
        b = self._buckets.get(key) or _Bucket()
        return {
            "papers": _counts(b.papers),
            "intl": _counts(b.intl),
            "us_papers": _counts(b.us),
            "countries": _regions(b.countries),
            "states": _regions(b.states),
            "country_pairs": _pairs(b.cpairs),
            "state_pairs": _pairs(b.spairs),
        }
