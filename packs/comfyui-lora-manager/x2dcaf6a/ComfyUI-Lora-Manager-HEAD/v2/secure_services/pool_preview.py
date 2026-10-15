"""Ordinary list-preview subset, distinct from Randomizer's pool filtering.

Pack-side native natural sort + query semantics over managed durable records.
No provider update annotation, thumbnail URL, scanner or source path export.
"""
from __future__ import annotations
from natsort import natsorted

from ..secure_algorithms.bounds import bounded_json
from ..secure_algorithms.preview_query import FilterCriteria, ModelFilterSet, LiteralPreviewFilters
from .pool_catalogue import preflight_filters, read_pool_catalogue
from .preview_preferences import read_preferences
from .info_note_routes import _request, _parse, _reply

FIELDS = {'baseModels', 'tagsInclude', 'tagsExclude', 'foldersInclude', 'foldersExclude',
    'noCreditRequired', 'allowSelling', 'namePatternsInclude', 'namePatternsExclude',
    'namePatternsUseRegex', 'page', 'pageSize'}


async def preview_rows(rows, params, preferences):
    bounded_json([rows, params, preferences])
    if type(params) is not dict or set(params) - FIELDS:
        raise ValueError('Invalid closed ordinary preview parameters')
    filters = {'baseModels': params.get('baseModels', []),
        'tags': {'include': params.get('tagsInclude', []), 'exclude': params.get('tagsExclude', [])},
        'folders': {'include': params.get('foldersInclude', []), 'exclude': params.get('foldersExclude', [])},
        'namePatterns': {'include': params.get('namePatternsInclude', []),
            'exclude': params.get('namePatternsExclude', []), 'useRegex': params.get('namePatternsUseRegex', False)}}
    preflight_filters(rows, filters)  # Before native sort, matching or result construction.
    page = params.get('page') or 1
    page_size = params.get('pageSize') or 6  # Exact source client truthy fallback.
    if type(page) is not int or abs(page) > 1_000_000 or type(page_size) is not int or abs(page_size) > 100:
        raise ValueError('Preview pagination exceeds admitted work bounds')
    mode = preferences['model_name_display']
    def display(row):
        primary, fallback = ('file_name', 'model_name') if mode == 'file_name' else ('model_name', 'file_name')
        return row.get(primary, '') or row.get(fallback, '') or ''
    items = natsorted(rows, key=lambda row: (display(row).lower(), row.get('file_path', '').lower()))
    tag_filters = {}
    for tag in filters['tags']['include']: tag_filters[tag] = 'include'
    for tag in filters['tags']['exclude']: tag_filters[tag] = 'exclude'
    items = ModelFilterSet(preferences).apply(items, FilterCriteria(
        folder_include=filters['folders']['include'], folder_exclude=filters['folders']['exclude'],
        base_models=filters['baseModels'], tags=tag_filters, search_options={'recursive': True}))
    specific = LiteralPreviewFilters()
    items = await specific._apply_specific_filters(items,
        name_pattern_include=filters['namePatterns']['include'],
        name_pattern_exclude=filters['namePatterns']['exclude'],
        name_pattern_use_regex=filters['namePatterns']['useRegex'])
    if params.get('noCreditRequired') is not None:
        items = await specific._apply_credit_required_filter(items, not params['noCreditRequired'])
    if params.get('allowSelling') is not None:
        items = await specific._apply_allow_selling_filter(items, params['allowSelling'])
    total = len(items)
    start = (page - 1) * page_size
    selected = items[start:min(start + page_size, total)]
    result = {'items': [{'key': row['file_path'], 'file_name': row['file_name'],
        'model_name': row.get('model_name') or row['file_name']} for row in selected], 'total': total}
    bounded_json(result)
    return result


async def read_preview(request):
    _request(request, 'POST')
    if request['query']:
        raise ValueError('Preview accepts no identity/query overrides')
    params = _parse(request['body'])
    if type(params) is not dict or set(params) - FIELDS:
        raise ValueError('Invalid closed ordinary preview parameters')
    current = await read_preferences()
    rows, _ = await read_pool_catalogue()
    return _reply(200, await preview_rows(rows, params, current['preferences']))
