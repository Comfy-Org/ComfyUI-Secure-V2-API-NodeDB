"""Full bounded editable-library successor; authenticated Cloud broker pending.

Retains pinned selection arithmetic while allowing the document codec's 4 MiB
library. Candidate work is charged before aggregation/weighted allocations.
The old snapshot service is deliberately unchanged as historical evidence.
"""
from __future__ import annotations

import re

from ..secure_algorithms.bounds import bounded_json, MAX_STRING_BYTES
from ..secure_algorithms.wildcards import (
    SnapshotWildcardExpander, MAX_SCAN, _normalize_wildcard_key,
)
from .documents import _validate_tree, LIMITS, read_document, compare_and_set_document
from .managed_wildcards import KEY, FORMAT

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


async def read_library():
    record = await read_document(KEY, 'wildcard-doc')
    document = record['document']
    if document is None:
        return {'revision': record['revision'], 'entries': {}}
    if type(document) is not dict or set(document) != {'format', 'entries'} or document['format'] != FORMAT:
        raise ValueError('Wildcard library document identity is invalid')
    FullLibraryExpander(document['entries'])
    return {'revision': record['revision'], 'entries': document['entries']}


async def save_library(entries, revision):
    FullLibraryExpander(entries)
    # The codec also checks serialized UTF-8 punctuation/key overhead before
    # allocating a tensor; tree text budget alone is not the encoded limit.
    return await compare_and_set_document(KEY, 'wildcard-doc', revision,
        {'format': FORMAT, 'entries': entries})


async def expand_saved_text(text, seed=None):
    bounded_json([text, seed])
    library = await read_library()
    return FullLibraryExpander(library['entries']).expand_text(text, seed)


async def encode_saved_prompt(clip, text, seed=None, **slots):
    bounded_json([text, seed, slots])
    expanded = await expand_saved_text(text, seed)
    words = [value for key, value in slots.items() if re.match(r'^trigger_words\d+$', key) and value]
    if words:
        if all(isinstance(value, str) for value in words + [expanded]):
            projected = sum(len(value.encode('utf-8')) for value in words + [expanded]) + 2 * len(words)
            if projected > MAX_STRING_BYTES:
                raise ValueError('Composed prompt exceeds bounds')
        expanded = ', '.join(words + [expanded])
    if clip is None:
        raise RuntimeError('ERROR: clip input is invalid: None\n\nIf the clip is from a checkpoint loader node your checkpoint does not contain a valid clip or text encoder model.')
    return await clip.encode(expanded), expanded
