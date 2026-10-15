"""Source-shaped managed pool option counts and models-only folder tree.

This is not a scanner, remote base-model catalogue, or empty-folder listing.
Published assets + durable authored records provide the current managed rows.
"""
from ..secure_algorithms.bounds import bounded_json
from .pool_catalogue import MAX_ROWS, read_pool_catalogue
from .info_note_routes import _request, _reply


def option_data(rows, kind, limit):
    bounded_json(rows)
    if len(rows) > MAX_ROWS:
        raise ValueError('Pool options exceed row bounds')
    if kind not in ('base-models', 'tags', 'folders') or type(limit) is not int:
        raise ValueError('Invalid closed pool options operation')
    if kind == 'folders':
        if limit != 0:
            raise ValueError('Folder tree accepts no count limit')
        # Pinned cache.folders is a unique, case-insensitively sorted list.
        folders = sorted({row.get('folder', '') for row in rows}, key=lambda x: x.lower())
        tree = {}
        for folder in folders:
            if not folder:
                continue
            if folder.count('/') + 1 > 14:
                raise ValueError('Pool option folder tree exceeds depth bounds')
            level = tree
            for part in folder.split('/'):
                level = level.setdefault(part, {})
        result = {'success': True, 'tree': tree}
    else:
        # Source handler normalizes an out-of-range limit, while zero means all.
        maximum = 100 if kind == 'base-models' else 200
        if limit < 0 or limit > maximum:
            limit = 20
        counts = {}
        for row in rows:
            values = [row['base_model']] if kind == 'base-models' and row.get('base_model') else (
                row.get('tags') or [] if kind == 'tags' else [])
            for value in values:
                counts[value] = counts.get(value, 0) + 1
        field = 'name' if kind == 'base-models' else 'tag'
        values = sorted([{field: name, 'count': count} for name, count in counts.items()],
                        key=lambda row: row['count'], reverse=True)
        if limit != 0:
            values = values[:limit]
        result = {'success': True, 'base_models' if kind == 'base-models' else 'tags': values}
    bounded_json(result)
    return result


async def _get(request, kind, default):
    _request(request, 'GET')
    if request['body'] != '' or set(request['query']) - {'limit'}:
        raise ValueError('Pool options accept only a count limit')
    if kind == 'folders' and request['query']:
        raise ValueError('Models-only folder tree accepts no overrides')
    raw = request['query'].get('limit', str(default))
    if type(raw) is not str or len(raw) > 32:
        raise ValueError('Pool options limit exceeds input bounds')
    limit = int(raw)
    rows, _ = await read_pool_catalogue()
    return _reply(200, option_data(rows, kind, limit))


async def base_models(request):
    return await _get(request, 'base-models', 20)


async def top_tags(request):
    return await _get(request, 'tags', 20)


async def folder_tree(request):
    return await _get(request, 'folders', 0)
