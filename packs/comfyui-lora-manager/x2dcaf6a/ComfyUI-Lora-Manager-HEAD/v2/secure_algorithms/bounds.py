"""Preflight JSON work bounds for workflow-owned configuration.

Validate before legacy algorithms format/log/copy or iterate a large input.
This is not a durable storage implementation and never grants host authority.
"""
from __future__ import annotations

import math

MAX_ITEMS = 16384
MAX_STRING_BYTES = 262144
MAX_TOTAL_STRING_BYTES = 1048576
MAX_DEPTH = 16


def bounded_json(value, *, allow_tuples=False):
    pending = [(value, 0)]
    items = 0
    text_bytes = 0
    while pending:
        current, depth = pending.pop()
        items += 1
        if items > MAX_ITEMS or depth > MAX_DEPTH:
            raise ValueError('LoRA Manager configuration exceeds work/depth bounds')
        if current is None or type(current) is bool:
            continue
        if type(current) in (int, float):
            if type(current) is int and current.bit_length() > 64:
                raise ValueError('LoRA Manager integer exceeds 64 bits')
            if type(current) is float and not math.isfinite(current):
                raise ValueError('LoRA Manager configuration must be finite')
            continue
        if type(current) is str:
            if len(current) > MAX_STRING_BYTES:
                raise ValueError('LoRA Manager string exceeds bounds')
            length = len(current.encode('utf-8'))
            text_bytes += length
            if length > MAX_STRING_BYTES or text_bytes > MAX_TOTAL_STRING_BYTES:
                raise ValueError('LoRA Manager text exceeds byte bounds')
            continue
        if type(current) is dict:
            if len(current) > MAX_ITEMS - items - len(pending):
                raise ValueError('LoRA Manager dictionary exceeds work bounds')
            if any(type(key) is not str for key in current):
                raise ValueError('LoRA Manager JSON keys must be strings')
            if 2 * len(current) > MAX_ITEMS - items - len(pending):
                raise ValueError('LoRA Manager dictionary exceeds work bounds')
            for key, item in current.items():
                pending.extend(((key, depth + 1), (item, depth + 1)))
            continue
        if type(current) is list or (allow_tuples and type(current) is tuple):
            if len(current) > MAX_ITEMS - items - len(pending):
                raise ValueError('LoRA Manager list exceeds work bounds')
            pending.extend((item, depth + 1) for item in current)
            continue
        raise ValueError('LoRA Manager configuration must be closed JSON')
    return value
