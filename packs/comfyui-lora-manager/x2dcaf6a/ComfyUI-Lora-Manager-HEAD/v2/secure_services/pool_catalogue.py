"""LoRA pool consumers over the actual pack-owned metadata cache.

Catalogue order is current managed host order. Folders and tie-break identities
are logical names, never OS paths. Headers are not substituted for authored data.
General backtracking regex workloads remain outside this admitted local profile.
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from comfy_api.latest import sdk

from ..secure_algorithms.bounds import bounded_json
from ..secure_algorithms.pool_license import resolve_license_info
from ..secure_algorithms.pool_service import LiteralPoolService
from ..secure_algorithms.pool_tags import PoolTagFilters
from .managed_library import _logical, _stem, _match
from .catalogue_cache import read_cache
from .randomizer import randomize_from_snapshot
from .cycler import cycle_from_snapshot

MAX_ROWS = 2048
MAX_PATTERNS = 32
MAX_MATCH_WORK = 16 * 1024 * 1024


def _regex_profile(pattern):
    """Admit finite linear atom sequences; never execute backtracking probes."""
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error:
        return  # Native source falls back to bounded substring for invalid regex.
    escaped = inside = False
    for char in pattern:
        if escaped:
            if char.isdigit():
                raise ValueError('Pool regex backreferences exceed admitted work profile')
            escaped = False
        elif char == '\\':
            escaped = True
        elif inside:
            if char == ']':
                inside = False
        elif char == '[':
            inside = True
        elif char in '*+?{}()|':
            raise ValueError('Pool regex repetitions/groups/branches exceed admitted work profile')


def preflight_filters(rows, filters):
    bounded_json([rows, filters])
    if len(rows) > MAX_ROWS:
        raise ValueError('Pool catalogue exceeds entry bounds')
    if not filters:
        return
    # Source-shaped malformed values still reach their native attribute/type
    # errors once the closed-data traversal has bounded them.
    if type(filters) is not dict:
        return
    token_fields = [filters.get('baseModels', [])]
    for section in ('tags', 'folders', 'namePatterns'):
        value = filters.get(section, {})
        if type(value) is dict:
            token_fields.extend(value.get(key, []) for key in ('include', 'exclude'))
    tokens = []
    for value in token_fields:
        if type(value) in (list, dict, str):
            # Preserve source small malformed string/dict iteration, but meter
            # its true character/key count rather than treating it as one token.
            if len(value) > 256:
                raise ValueError('Pool filter iteration exceeds entry bounds')
            tokens.extend(value)
    row_text = sum(len(value) for row in rows if type(row) is dict
                   for value in (row.get('model_name', ''), row.get('file_name', ''), row.get('folder', ''))
                   if type(value) is str)
    token_text = sum(max(1, len(value)) for value in tokens if type(value) is str)
    if row_text * token_text > MAX_MATCH_WORK:
        raise ValueError('Pool filter matching exceeds projected work bounds')
    patterns = filters.get('namePatterns', {})
    if type(patterns) is not dict:
        return
    selected = []
    for name in ('include', 'exclude'):
        value = patterns.get(name, [])
        if type(value) not in (list, str, dict):
            return
        if len(value) > MAX_PATTERNS:
            raise ValueError('Pool name patterns exceed entry bounds')
        selected.extend(value)
    if len(selected) > MAX_PATTERNS:
        raise ValueError('Pool name patterns exceed entry bounds')
    for pattern in selected:
        if type(pattern) is str:
            if len(pattern) > 128:
                raise ValueError('Pool name pattern exceeds character bounds')
            if patterns.get('useRegex', False):
                _regex_profile(pattern)
    names = [row.get(field, '') for row in rows if type(row) is dict
             for field in ('model_name', 'file_name')]
    work = sum(len(value) for value in names if type(value) is str) * sum(
        max(1, len(pattern)) for pattern in selected if type(pattern) is str)
    if work > MAX_MATCH_WORK:
        raise ValueError('Pool name matching exceeds projected work bounds')


def _project(metadata, name, digest):
    """Pinned cache fields and license precedence over a confined logical asset."""
    tags = metadata.get('tags') or []
    if type(tags) is not list:
        tags = []  # Source cache normalizes non-list JSON tags to an empty list.
    tips = metadata.get('usage_tips', '') or ''
    if type(tips) is not str:
        tips = str(tips)  # Pinned cache normalization, not recommendation parsing.
    license_source = {}
    civitai = metadata.get('civitai')
    if type(civitai) is dict and type(civitai.get('model')) is dict:
        license_source = {key: civitai['model'][key] for key in (
            'allowNoCredit', 'allowCommercialUse', 'allowDerivatives', 'allowDifferentLicense')
            if key in civitai['model']}
    for key in ('allowNoCredit', 'allowCommercialUse', 'allowDerivatives', 'allowDifferentLicense'):
        if key not in license_source and metadata.get(key) is not None:
            license_source[key] = metadata[key]
    _, flags = resolve_license_info(license_source)
    relative = _stem(name)
    model_name = metadata.get('model_name')
    # Exact pinned ModelCache._ensure_string, including False and numeric zero.
    model_name = model_name if isinstance(model_name, str) else ('' if model_name is None else str(model_name))
    row = {'file_name': relative.rsplit('/', 1)[-1],
           'model_name': model_name,
           'folder': relative.rsplit('/', 1)[0] if '/' in relative else '',
           'file_path': name,  # Inert logical tie-break token only; never published as a path.
           'base_model': metadata.get('base_model', '') or '',
           'tags': tags, 'usage_tips': tips, 'license_flags': flags,
           'favorite': bool(metadata.get('favorite', False)), 'sha256': digest}
    row['preview_nsfw_level'] = int(metadata.get('preview_nsfw_level', 0) or 0)
    bounded_json(row)
    return row


async def read_pool_catalogue():
    # Metadata comes from the real pack cache, including genuine None and
    # previous completed rows during refresh. Never reacquire authored records
    # per digest: distinct logical rows can have identical weight bytes.
    current = await read_cache()
    names = await sdk.ctx().assets.list('loras')
    if type(names) is not list or len(names) > MAX_ROWS:
        raise ValueError('Pool catalogue exceeds entry bounds')
    for name in names:
        _logical(name)
    if len(set(names)) != len(names):
        raise ValueError('Duplicate managed pool name')
    rows = []
    for cached in ([] if current['cache'] is None else current['cache']['rows']):
        rows.append(_project(cached['metadata'], cached['name'], cached['sha256']))
        bounded_json(rows)
    # Current asset identities resolve execution stacks independently of stale
    # cached metadata, as native get_lora_info checks current file liveness.
    return rows, names


def _service(rows):
    class Scanner:
        async def get_cached_data(self, *, force_refresh):
            if force_refresh is not False:
                raise ValueError('Pool consumer cannot force a scanner refresh')
            return SimpleNamespace(raw_data=rows)
    service = LiteralPoolService()
    service.scanner = Scanner()
    service.filter_set = PoolTagFilters()
    return service


async def filtered_pool(rows, filters=None):
    preflight_filters(rows, filters)
    return await _service(rows)._apply_pool_filters(rows, filters) if filters else rows


async def cycle_list(rows, filters=None, sort_by='filename'):
    preflight_filters(rows, filters)
    return await _service(rows).get_cycler_list(pool_config=filters, sort_by=sort_by)


def _resolutions(names, requested):
    result = {}
    for display in requested:
        try:
            result[display] = _match(display, names)
        except ValueError:
            # Pinned missing resolution skips that stack row. Invalid logical
            # names are refused before this helper by the boundary preflight.
            result[display] = None
    return result


async def randomize_pool(config, loras, filters=None):
    bounded_json([config, loras, filters])
    source_loras = loras['__value__'] if isinstance(loras, dict) and '__value__' in loras else loras
    for row in source_loras:
        if row.get('name') is not None:
            _logical(row['name'])
    if config.get('roll_mode', 'always') == 'fixed':
        # Source fixed mode never reads/filter/randomizes scanner metadata.
        # Only currently present logical asset identities are needed for stack.
        names = await sdk.ctx().assets.list('loras')
        if type(names) is not list or len(names) > MAX_ROWS:
            raise ValueError('Pool catalogue exceeds entry bounds')
        for name in names:
            _logical(name)
        resolved = _resolutions(names, [row['name'] for row in source_loras if 'name' in row])
        for name in set(resolved.values()) - {None}:
            try:
                await sdk.ctx().assets.resolve('loras', name)
            except FileNotFoundError:
                resolved = {key: value if value != name else None for key, value in resolved.items()}
        return randomize_from_snapshot(config, loras, [], resolved)
    rows, names = await read_pool_catalogue()
    rows = await filtered_pool(rows, filters)
    requested = [row['name'] for row in source_loras if 'name' in row]
    requested += [f"{row['folder']}/{row['file_name']}" if row.get('folder') else row['file_name'] for row in rows]
    resolved = _resolutions(names, requested)
    return randomize_from_snapshot(config, loras, rows, resolved)


async def cycle_pool(config, filters=None):
    bounded_json([config, filters])
    rows, names = await read_pool_catalogue()
    # The backend source deliberately ignores config.sort_by and uses filename.
    ordered = await cycle_list(rows, filters, 'filename')
    metadata = {f"{row['folder']}/{row['file_name']}" if row.get('folder') else row['file_name']: row for row in rows}
    return cycle_from_snapshot(config, ordered,
        _resolutions(names, [row['file_name'] for row in ordered]), metadata)
