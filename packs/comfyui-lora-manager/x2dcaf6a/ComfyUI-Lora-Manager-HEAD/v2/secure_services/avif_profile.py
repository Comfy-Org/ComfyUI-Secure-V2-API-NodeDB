"""Bounded raw AVIF brob metadata over managed image bytes.

Compressed brob remains a dependency-profile gap. No decompressor is imported.
"""
from __future__ import annotations

import json

from ..secure_algorithms.bounds import bounded_json
from .documents import _preflight_json_depth

MAX_TOP_LEVEL_BOXES = 4096
MAX_RAW_JSON_BYTES = 1024 * 1024


def read_raw_avif_brob(data: bytes) -> dict[str, str | None] | None:
    """Project the first raw comf box, preserving native EXIF fallback rules.

    Match the pinned reader's finite 32-bit box scan, including its stop at
    zero, short, extended-size and truncated boxes. The caller bounds encoded
    bytes and identifies the image. Bounds reject rather than skip metadata.
    """
    offset = boxes = 0
    first_brob: tuple[int, int] | None = None
    avif_brand = False
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset:offset + 4], 'big')
        if size < 8 or offset + size > len(data):
            break
        boxes += 1
        if boxes > MAX_TOP_LEVEL_BOXES:
            raise ValueError('AVIF metadata container exceeds box work bounds')
        kind = data[offset + 4:offset + 8]
        if kind == b'ftyp' and b'avif' in data[offset + 8:offset + size]:
            avif_brand = True
        if kind == b'brob' and first_brob is None:
            first_brob = (offset + 8, offset + size)
        offset += size
    if len(data) < 16 or not avif_brand or first_brob is None:
        return None
    start, end = first_brob
    if data[start:start + 4] != b'comf' or end - start < 4:
        return None
    start += 4
    if end - start > MAX_RAW_JSON_BYTES:
        raise ValueError('AVIF raw metadata exceeds encoded JSON bounds')
    try:
        text = data[start:end].decode('utf-8')
    except UnicodeDecodeError as error:
        raise NotImplementedError('AVIF brob compressed/binary metadata needs a qualified Brotli profile') from error
    stripped = text.lstrip()
    if stripped and stripped[0] not in '{["-0123456789tfn':
        raise NotImplementedError('AVIF brob compressed/binary metadata needs a qualified Brotli profile')
    _preflight_json_depth(text)
    try:
        meta = json.loads(text)
    except (ValueError, RecursionError):
        # The native reader falls back to ordinary EXIF on invalid raw JSON.
        return None
    bounded_json(meta)
    result: dict[str, str | None] = dict.fromkeys(('parameters', 'prompt', 'workflow', 'comment'))
    # Keep the original AttributeError for a valid non-object JSON root.
    for key in ('prompt', 'workflow'):
        value = meta.get(key)
        if isinstance(value, (dict, list)):
            result[key] = json.dumps(value)
        elif isinstance(value, str):
            result[key] = value
    return result
