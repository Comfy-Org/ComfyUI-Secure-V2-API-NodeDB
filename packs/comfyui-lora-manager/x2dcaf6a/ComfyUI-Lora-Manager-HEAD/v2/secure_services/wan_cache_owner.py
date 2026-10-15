"""Explicit import of genuine exported native cache data into owned storage.

This module does not acquire legacy scanner/config state or invent a snapshot.
The importer requires exported ordered rows, original roots and operator-
established catalogue bindings. Business paths remain metadata, never authority
to read the host filesystem. Actual assets resolve only by logical names.
"""
import json
from comfy_api.latest import sdk

from .documents import _validate_tree, _preflight_json_depth
from .wan_selection import _append_request
from ..secure_algorithms.wan_selection import (begin_widget_selection, begin_text_selection,
    iter_widget_requests, iter_text_requests, finish_selection)

KEY = 'manager.native-wan-selector-cache'
FORMAT = 'loramanager.native-wan-cache.v1'
MAX_DOCUMENT_BYTES = 1024 * 1024


def validate_native_cache_document(value):
    expected = {'format', 'original_commit', 'cache_rows', 'catalogue_bindings',
                'loras_roots', 'extra_loras_roots'}
    if (type(value) is not dict or set(value) != expected or value['format'] != FORMAT
        or value['original_commit'] != '2dcaf6a30e50e6eace230c8311f25890a23473f0'
        or type(value['cache_rows']) is not list
        or any(type(row) is not dict for row in value['cache_rows'])
        or type(value['catalogue_bindings']) is not dict
        or any(type(path) is not str or type(name) is not str
               for path, name in value['catalogue_bindings'].items())
        or any(type(value[key]) is not list or any(type(root) is not str for root in value[key])
               for key in ('loras_roots', 'extra_loras_roots'))):
        raise ValueError('Invalid imported native WAN cache document')
    _validate_tree(value, MAX_DOCUMENT_BYTES)
    return value


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate imported native WAN cache field')
        value[key] = item
    return value


async def import_native_cache_document(document):
    # Import operates on an actual caller-supplied export. No fallback cache,
    # source-directory scan, mutable revision retry or fabricated root layout.
    validate_native_cache_document(document)
    raw = json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    if len(raw.encode('utf-8')) > MAX_DOCUMENT_BYTES:
        raise ValueError('Imported native WAN cache exceeds storage document limit')
    # The verified runtime exposes get/set only. Atomic import/revision
    # semantics are not consumed or promised by the native selectors.
    await sdk.ctx().storage.set(KEY, raw)
    return await sdk.ctx().storage.get(KEY) == raw


async def read_native_cache_document():
    raw = await sdk.ctx().storage.get(KEY)
    if raw is None:
        raise NotImplementedError('Native WAN cache and root layout have not been imported')
    if type(raw) is not str or len(raw.encode('utf-8')) > MAX_DOCUMENT_BYTES:
        raise ValueError('Imported native WAN cache exceeds storage document limit')
    _preflight_json_depth(raw)
    return validate_native_cache_document(json.loads(raw, object_pairs_hook=_unique_pairs))


async def _finish_owned_selection(state, requests):
    owner = None
    for request in requests:
        # Preserve native lazy error order and predecessor-only behavior:
        # blocks and request float parsing precede the first cache read.
        if owner is None:
            owner = await read_native_cache_document()
        await _append_request(state, request, cache_rows=owner['cache_rows'],
            catalogue_bindings=owner['catalogue_bindings'], loras_roots=owner['loras_roots'],
            extra_loras_roots=owner['extra_loras_roots'])
    return finish_selection(state)


async def select_owned_widget(loras, low_mem_load=False, merge_loras=True, **kwargs):
    state = begin_widget_selection(low_mem_load, merge_loras, **kwargs)
    return await _finish_owned_selection(state, iter_widget_requests(loras))


async def select_owned_text(lora_syntax, low_mem_load=False, merge_lora=True, **kwargs):
    state = begin_text_selection(low_mem_load, merge_lora, **kwargs)
    return await _finish_owned_selection(state, iter_text_requests(lora_syntax))
