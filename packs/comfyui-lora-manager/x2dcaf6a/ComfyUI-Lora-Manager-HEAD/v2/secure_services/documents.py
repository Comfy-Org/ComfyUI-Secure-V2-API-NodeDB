"""Pack-side versioned JSON/preview envelopes over the public scoped VALUE store.

No tenant/pack override, path, model ref, pickle or local-file persistence.
Local backing tests do not prove deployed cloud identity or durable volumes.
"""
from __future__ import annotations

import json
import math

import torch
from comfy_api.latest import sdk

LIMITS = {'model-edits': 4 * 1024**2, 'wildcard-doc': 4 * 1024**2,
          'recipe-doc': 8 * 1024**2, 'usage-history': 4 * 1024**2}
PREVIEW_LIMIT = 8 * 1024**2
MAX_NODES = 65536
MAX_DEPTH = 32
FORMAT = 'loramanager.document.v1'
ENVELOPE_KEYS = {'format', 'kind', 'json_utf8', 'preview', 'preview_media'}


def _limit(kind):
    if type(kind) is not str or kind not in LIMITS:
        raise ValueError('Unknown LoRA Manager document kind')
    return LIMITS[kind]


def _validate_tree(document, limit):
    pending = [(document, 0)]
    count = total = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('Document exceeds work/depth bounds')
        if value is None or type(value) is bool:
            continue
        if type(value) is int:
            if value.bit_length() > 64:
                raise ValueError('Document integer exceeds bounds')
        elif type(value) is float:
            if not math.isfinite(value):
                raise ValueError('Document numbers must be finite')
        elif type(value) is str:
            if len(value) > limit:
                raise ValueError('Document string exceeds bounds')
            total += len(value.encode('utf-8'))
            if total > limit:
                raise ValueError('Document text exceeds byte bounds')
        elif type(value) is dict:
            if any(type(key) is not str for key in value):
                raise ValueError('Document keys must be text')
            if 2 * len(value) > MAX_NODES - count - len(pending):
                raise ValueError('Document dictionary exceeds bounds')
            for key, item in value.items():
                pending.extend(((key, depth + 1), (item, depth + 1)))
        elif type(value) is list:
            if len(value) > MAX_NODES - count - len(pending):
                raise ValueError('Document array exceeds bounds')
            pending.extend((item, depth + 1) for item in value)
        else:
            raise ValueError('Document must contain only closed JSON data')


def _preflight_json_depth(text):
    quoted = escaped = False
    depth = 0
    for char in text:
        if quoted:
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif char == '"': quoted = False
        elif char == '"': quoted = True
        elif char in '[{':
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError('Stored document exceeds depth bounds')
        elif char in ']}': depth -= 1


def _buffer(data):
    return torch.frombuffer(bytearray(data), dtype=torch.uint8).clone() if data else torch.empty(0, dtype=torch.uint8)


def _bytes(tensor, limit):
    if type(tensor) is not torch.Tensor or tensor.dtype != torch.uint8 or tensor.device.type != 'cpu' or tensor.ndim != 1:
        raise ValueError('Document buffer must be a CPU uint8 vector')
    if tensor.numel() > limit:
        raise ValueError('Stored document buffer exceeds bounds')
    return tensor.contiguous().numpy().tobytes()


def encode_document(kind, document, preview=None):
    limit = _limit(kind)
    if type(document) is not dict:
        raise ValueError('LoRA Manager document must be an object')
    _validate_tree(document, limit)
    if preview is not None:
        if kind != 'recipe-doc' or type(preview) is not bytes or len(preview) > PREVIEW_LIMIT:
            raise ValueError('Invalid or oversized recipe preview')
        if len(preview) < 12 or preview[:4] != b'RIFF' or preview[8:12] != b'WEBP':
            raise ValueError('Recipe preview must contain encoded WebP bytes')
    data = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    for chunk in encoder.iterencode(document):
        part = chunk.encode('utf-8')
        if len(data) + len(part) > limit:
            raise ValueError('Encoded document exceeds byte bounds')
        data.extend(part)
    # All projected document/preview limits are checked before tensor allocation.
    return {'format': FORMAT, 'kind': kind, 'json_utf8': _buffer(data),
            'preview': None if preview is None else _buffer(preview),
            'preview_media': None if preview is None else 'image/webp'}


def decode_document(kind, envelope):
    limit = _limit(kind)
    if type(envelope) is not dict or set(envelope) != ENVELOPE_KEYS or envelope['format'] != FORMAT or envelope['kind'] != kind:
        raise ValueError('Stored document envelope identity is invalid')
    data = _bytes(envelope['json_utf8'], limit)
    text = data.decode('utf-8', errors='strict')
    _preflight_json_depth(text)
    document = json.loads(text, parse_constant=lambda name: (_ for _ in ()).throw(ValueError('Nonfinite stored JSON')))
    if type(document) is not dict:
        raise ValueError('Stored document must be an object')
    _validate_tree(document, limit)
    preview = None
    if envelope['preview'] is not None:
        if kind != 'recipe-doc' or envelope['preview_media'] != 'image/webp':
            raise ValueError('Stored preview identity is invalid')
        preview = _bytes(envelope['preview'], PREVIEW_LIMIT)
        if len(preview) < 12 or preview[:4] != b'RIFF' or preview[8:12] != b'WEBP':
            raise ValueError('Stored preview is not encoded WebP')
    elif envelope['preview_media'] is not None:
        raise ValueError('Stored preview media exists without bytes')
    return {'document': document, 'preview': preview}


async def read_document(key, kind):
    _limit(kind)
    record = await sdk.ctx().storage.read_value(key)
    if record['value'] is None:
        return {'revision': record['revision'], 'document': None, 'preview': None}
    data = decode_document(kind, await record['value'].value())
    return {'revision': record['revision'], **data}


async def compare_and_set_document(key, kind, revision, document, preview=None, *, ttl_seconds=None):
    envelope = encode_document(kind, document, preview)
    value = await sdk.ValueRef.from_value(envelope)
    # Optional lifetime is a request, never an SDK/pack grant. Refusal propagates
    # unchanged; there is no clamp, automatic retry or durable-library claim.
    return await sdk.ctx().storage.compare_and_set_value(key, revision, value, ttl_seconds=ttl_seconds)


async def edit_document(key, kind, edit, *, attempts=8, ttl_seconds=None):
    """Retry a pure pack-side edit against a fresh private snapshot on conflict."""
    if type(attempts) is not int or not 1 <= attempts <= 8:
        raise ValueError('Document retry count must be 1..8')
    for _ in range(attempts):
        current = await read_document(key, kind)
        next_document, preview = edit(current['document'], current['preview'])
        result = await compare_and_set_document(key, kind, current['revision'], next_document, preview, ttl_seconds=ttl_seconds)
        if result['updated']:
            return result
    raise RuntimeError('Document update conflict retry budget exhausted')
