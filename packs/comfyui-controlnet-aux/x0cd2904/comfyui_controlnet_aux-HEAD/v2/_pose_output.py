"""Source JSON/counter semantics over confined managed output names."""
import json
import posixpath
import time

from comfy_api.latest import sdk



def _json_text(value):
    return json.dumps(value)


def prepare(pose_kps, filename_prefix):
    width = pose_kps[0]['canvas_width']
    height = pose_kps[0]['canvas_height']
    text = _json_text(pose_kps)
    if '%' in filename_prefix:
        now = time.localtime()
        replacements = {'width': str(width), 'height': str(height),
                        'year': str(now.tm_year), 'month': str(now.tm_mon).zfill(2),
                        'day': str(now.tm_mday).zfill(2), 'hour': str(now.tm_hour).zfill(2),
                        'minute': str(now.tm_min).zfill(2), 'second': str(now.tm_sec).zfill(2)}
        for key, replacement in replacements.items():
            filename_prefix = filename_prefix.replace('%' + key + '%', replacement)
    normalized = posixpath.normpath(filename_prefix)
    if ('\0' in normalized or posixpath.isabs(normalized)
            or normalized == '..' or normalized.startswith('../')):
        raise ValueError('pose prefix must stay in the managed output namespace')
    folder, filename = posixpath.split(normalized)
    return text, folder, filename


def counter(names, filename):
    prefix_len = len(filename)
    matches = []
    for name in names:
        prefix = name[:prefix_len + 1]
        try:
            digits = int(name[prefix_len + 1:].split('.')[0].split('_')[0])
        except ValueError:
            digits = 0
        if prefix[:-1] == filename and prefix[-1:] == '_':
            matches.append((digits, prefix))
    return max(matches)[0] + 1 if matches else 1


async def execute(pose_kps, filename_prefix):
    text, folder, filename = prepare(pose_kps, filename_prefix)
    names = await sdk.ctx().assets.list('output', prefix=folder, recursive=False)
    marker = folder + '/' if folder else ''
    immediate = [name[len(marker):] for name in names]
    next_counter = counter(immediate, filename)
    offset = 0
    while True:
        leaf = f'{filename}_{next_counter + offset:05}.json'
        target = marker + leaf
        try:
            await sdk.ctx().output.write_text(text, target, folder='output', mode='new_only')
            return
        except FileExistsError:
            offset += 1
