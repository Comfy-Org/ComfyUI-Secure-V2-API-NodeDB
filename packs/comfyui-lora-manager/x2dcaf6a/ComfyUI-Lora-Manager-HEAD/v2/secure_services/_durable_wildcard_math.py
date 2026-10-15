"""Exact predecessor FullLibraryExpander; no storage or Prompt caller."""
import re
from ..secure_algorithms.bounds import MAX_STRING_BYTES
from ..secure_algorithms.wildcards import SnapshotWildcardExpander, MAX_SCAN, _normalize_wildcard_key
from ._wildcard_document_bounds import _validate_tree

LIMITS = {'wildcard-doc': 4 * 1024**2}
MAX_CANDIDATE_BYTES = 32 * 1024**2
MAX_CANDIDATE_VISITS = 262144

class FullLibraryExpander(SnapshotWildcardExpander):
    def __init__(self, table):
        _validate_tree(table, LIMITS['wildcard-doc'])
        if type(table) is not dict:
            raise ValueError('Wildcard library must be an object')
        for key, values in table.items():
            if type(key) is not str or not key or len(key) > 128 or type(values) is not list or not values:
                raise ValueError('Wildcard library requires bounded keys and nonempty string arrays')
            for value in values:
                if type(value) is not str or len(value.encode('utf-8')) > MAX_STRING_BYTES:
                    raise ValueError('Wildcard candidate exceeds string bounds')
        self.table = table
        self.scan_work = self.replacements = 0
        self.candidate_bytes = self.candidate_visits = 0

    def expand_text(self, text, seed=None):
        self.candidate_bytes = self.candidate_visits = 0
        return super().expand_text(text, seed)

    def _charge_candidates(self, values, passes):
        # Conservatively account the membership, weight and choice scans.
        # No RNG call or projected weighted/aggregate list is made first.
        for value in values:
            self.candidate_visits += passes
            self.candidate_bytes += passes * len(value.encode('utf-8'))
            if self.candidate_bytes > MAX_CANDIDATE_BYTES or self.candidate_visits > MAX_CANDIDATE_VISITS:
                raise ValueError('Wildcard candidate work exceeds bounds')

    def _pick_weighted_or_plain(self, values, rng):
        self._charge_candidates(values, 3)
        return super()._pick_weighted_or_plain(values, rng)

    def _resolve_wildcard_match(self, raw_key, rng, wildcard_dict):
        keyword = _normalize_wildcard_key(raw_key)
        if keyword in wildcard_dict:
            return self._pick_weighted_or_plain(wildcard_dict[keyword], rng)
        if len(keyword) > 128 or keyword.count('*') > 1:
            raise ValueError('Wildcard lookup pattern exceeds bounded glob policy')
        if '*' in keyword:
            # Preserve the pinned regex treatment, including unescaped dots.
            compiled = re.compile('^' + keyword.replace('*', '.*').replace('+', r'\+') + '$')
            aggregated = []
            for key, values in wildcard_dict.items():
                self.scan_work += len(key)
                if self.scan_work > MAX_SCAN:
                    raise ValueError('Wildcard lookup work exceeds bounds')
                if compiled.match(key):
                    self._charge_candidates(values, 1)
                    aggregated.extend(values)
            if aggregated:
                return self._pick_weighted_or_plain(aggregated, rng)
        if '/' not in keyword:
            fallback = _normalize_wildcard_key('*/' + keyword)
            if fallback != keyword:
                return self._resolve_wildcard_match(fallback, rng, wildcard_dict)
        return None
