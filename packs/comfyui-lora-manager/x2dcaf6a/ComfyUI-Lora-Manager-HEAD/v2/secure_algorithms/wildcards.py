"""Bounded pinned expansion math over a caller-supplied library snapshot.

This is NOT a replacement for the manager's editable wildcard library. The
authenticated snapshot selection, import/search routes and durable backing are
still unwired. No files, global service singleton or process cache are used.
"""
from __future__ import annotations

import random
import re

from .bounds import bounded_json, MAX_STRING_BYTES

_WILDCARD_PATTERN = re.compile(r"__([\w\s.\-+/*\\]+?)__")
_OPTION_PATTERN = re.compile(r"{([^{}]*?)}")
_WEIGHTED_OPTION_PATTERN = re.compile(r"^\s*-?\d+(\.\d+)?::")
_NUMERIC_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")
MAX_SCAN = 8 * 1024**2
MAX_DRAWS = 32768
MAX_REPLACEMENTS = 4096


def _normalize_wildcard_key(value):
    return value.replace("\\", "/").strip("/").lower()


def _is_numeric_string(value):
    return bool(_NUMERIC_PATTERN.match(value))


class _BudgetRandom:
    """Delegate exact seeded draws, but cap a legacy duplicate-pick loop."""
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.draws = 0

    def _draw(self, method, *args):
        self.draws += 1
        if self.draws > MAX_DRAWS:
            raise ValueError('Wildcard random work exceeds bounds')
        return getattr(self.rng, method)(*args)

    def choice(self, values):
        return self._draw('choice', values)

    def randint(self, lo, hi):
        return self._draw('randint', lo, hi)

    def randrange(self, stop):
        return self._draw('randrange', stop)

    def uniform(self, lo, hi):
        return self._draw('uniform', lo, hi)


class SnapshotWildcardExpander:
    def __init__(self, table):
        bounded_json(table)
        if type(table) is not dict or any(
            type(key) is not str or not key or len(key) > 128
            or type(values) is not list or not values
            or any(type(value) is not str for value in values)
            for key, values in table.items()
        ):
            raise ValueError('Wildcard snapshot must contain bounded nonempty string arrays')
        self.table = table
        self.scan_work = 0
        self.replacements = 0

    def expand_text(self, text, seed=None):
        bounded_json([text, seed])
        if seed is not None and type(seed) not in (bool, int, str, float):
            raise ValueError('Wildcard seed must be an inert bounded scalar')
        # Legacy passes inert non-string/empty text through unchanged.
        if not isinstance(text, str) or not text:
            return text
        self.scan_work = self.replacements = 0
        rng = _BudgetRandom(seed)
        current = text
        for _ in range(100):
            current, options = self._replace_options(current, rng)
            if self.table:
                current, wildcards = self._replace_wildcards(current, rng, self.table)
            else:
                wildcards = False
            if not options and not wildcards:
                break
        return current

    def _substitute(self, pattern, text, replacement):
        self.scan_work += len(text)
        if self.scan_work > MAX_SCAN:
            raise ValueError('Wildcard expansion scan work exceeds bounds')
        pieces = []
        end = 0
        output_bytes = 0
        replaced = False
        def append(piece):
            nonlocal output_bytes
            if len(piece) > MAX_STRING_BYTES:
                raise ValueError('Wildcard expanded text exceeds bounds')
            output_bytes += len(piece.encode('utf-8'))
            if output_bytes > MAX_STRING_BYTES:
                raise ValueError('Wildcard expanded text exceeds bounds')
            pieces.append(piece)
        for match in pattern.finditer(text):
            self.replacements += 1
            if self.replacements > MAX_REPLACEMENTS:
                raise ValueError('Wildcard replacement work exceeds bounds')
            value = replacement(match.group(1))
            if value is None:
                value = match.group(0)
            else:
                replaced = True
            append(text[end:match.start()])
            append(value)
            end = match.end()
        append(text[end:])
        # Check projected UTF-8 result BEFORE concatenating the pieces.
        return ''.join(pieces), replaced

    def _replace_options(self, text, rng):
        return self._substitute(_OPTION_PATTERN, text,
                                lambda group: self._resolve_option_group(group, rng))

    def _replace_wildcards(self, text, rng, wildcard_dict):
        return self._substitute(_WILDCARD_PATTERN, text,
                                lambda key: self._resolve_wildcard_match(key, rng, wildcard_dict))

    def _resolve_option_group(self, group_text, rng):
        options = group_text.split("|")
        multi_select_pattern = options[0].split("$$")
        select_range = None
        select_separator = " "
        if len(multi_select_pattern) > 1:
            count_spec = multi_select_pattern[0]
            range_match = re.match(r"(\d+)(-(\d+))?$", count_spec)
            shorthand_match = re.match(r"-(\d+)$", count_spec)
            if range_match:
                start_text = range_match.group(1)
                end_text = range_match.group(3)
                if end_text is not None and _is_numeric_string(start_text) and _is_numeric_string(end_text):
                    select_range = (int(start_text), int(end_text))
                elif _is_numeric_string(start_text):
                    value = int(start_text)
                    select_range = (value, value)
            elif shorthand_match:
                end_text = shorthand_match.group(1)
                if _is_numeric_string(end_text):
                    select_range = (1, int(end_text))
            if select_range is not None and len(multi_select_pattern) == 2:
                options[0] = multi_select_pattern[1]
            elif select_range is not None and len(multi_select_pattern) >= 3:
                select_separator = multi_select_pattern[1]
                options[0] = multi_select_pattern[2]
        weighted_options = []
        for option in options:
            weight = 1.0
            parts = option.split("::", 1)
            if len(parts) == 2 and _is_numeric_string(parts[0].strip()):
                weight = float(parts[0].strip())
            weighted_options.append((weight, option))
        selection_count = 1 if select_range is None else rng.randint(select_range[0], select_range[1])
        if selection_count <= 1:
            return self._strip_weight_prefix(self._weighted_choice(weighted_options, rng))
        selection_count = min(selection_count, len(weighted_options))
        selected = []
        used_indexes = set()
        while len(selected) < selection_count:
            picked_index = self._weighted_choice_index(weighted_options, rng)
            if picked_index in used_indexes:
                if len(used_indexes) == len(weighted_options):
                    break
                continue
            used_indexes.add(picked_index)
            selected.append(self._strip_weight_prefix(weighted_options[picked_index][1]))
        # The separator can dwarf its group. Bound the projected join first.
        projected = sum(len(value.encode('utf-8')) for value in selected)
        projected += len(select_separator.encode('utf-8')) * max(0, len(selected) - 1)
        if projected > MAX_STRING_BYTES:
            raise ValueError('Wildcard option join exceeds bounds')
        return select_separator.join(selected)

    def _weighted_choice(self, weighted_options, rng):
        return weighted_options[self._weighted_choice_index(weighted_options, rng)][1]

    def _weighted_choice_index(self, weighted_options, rng):
        total_weight = sum(max(weight, 0.0) for weight, _value in weighted_options)
        if total_weight <= 0:
            return rng.randrange(len(weighted_options))
        threshold = rng.uniform(0, total_weight)
        cumulative = 0.0
        for index, (weight, _value) in enumerate(weighted_options):
            cumulative += max(weight, 0.0)
            if threshold <= cumulative:
                return index
        return len(weighted_options) - 1

    def _strip_weight_prefix(self, value):
        return _WEIGHTED_OPTION_PATTERN.sub("", value, count=1)

    def _resolve_wildcard_match(self, raw_key, rng, wildcard_dict):
        keyword = _normalize_wildcard_key(raw_key)
        # The pinned implementation creates regex from user wildcard text.
        # Deliberately fail closed before compiling unbounded ambiguous globs.
        if keyword in wildcard_dict:
            return self._pick_weighted_or_plain(wildcard_dict[keyword], rng)
        if len(keyword) > 128 or keyword.count('*') > 1:
            raise ValueError('Wildcard lookup pattern exceeds bounded glob policy')
        if "*" in keyword:
            regex_pattern = keyword.replace("*", ".*").replace("+", r"\+")
            compiled = re.compile(f"^{regex_pattern}$")
            aggregated = []
            for key, values in wildcard_dict.items():
                self.scan_work += len(key)
                if self.scan_work > MAX_SCAN:
                    raise ValueError('Wildcard lookup work exceeds bounds')
                if compiled.match(key):
                    aggregated.extend(values)
            if aggregated:
                return self._pick_weighted_or_plain(aggregated, rng)
        if "/" not in keyword:
            fallback_keyword = _normalize_wildcard_key(f"*/{keyword}")
            if fallback_keyword != keyword:
                return self._resolve_wildcard_match(fallback_keyword, rng, wildcard_dict)
        return None

    def _pick_weighted_or_plain(self, values, rng):
        if not any("::" in value for value in values):
            return rng.choice(values)
        weighted_options = []
        for value in values:
            weight = 1.0
            parts = value.split("::", 1)
            if len(parts) == 2 and _is_numeric_string(parts[0].strip()):
                weight = float(parts[0].strip())
            weighted_options.append((weight, value))
        any_weighted = any(weight != 1.0 for weight, _ in weighted_options)
        picked = self._weighted_choice(weighted_options, rng) if any_weighted else rng.choice(values)
        return self._strip_weight_prefix(picked)


def expand_from_snapshot(text, table, seed=None):
    return SnapshotWildcardExpander(table).expand_text(text, seed)
