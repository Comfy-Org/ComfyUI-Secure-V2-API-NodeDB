"""Pinned cycler math over caller-supplied inert catalogue projections.

No scanner/cache/filesystem or implicit persistent catalogue is provided here.
Names are inert output strings, never path authority. This helper does not select
an authenticated library snapshot or implement the workflow/widget queue barrier.
"""
from __future__ import annotations

import json
import math
import os
from typing import Any

from ..secure_algorithms.bounds import MAX_DEPTH, bounded_json


def _tip(metadata: dict[str, Any], key: str) -> Any:
    """Exact pinned recommended-strength fallback, after bounded JSON preflight."""
    try:
        usage_tips = metadata.get('usage_tips', '')
        if not usage_tips:
            return None
        return json.loads(usage_tips).get(key)
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


def _preflight_tips(text: str) -> None:
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError('Cycler usage tips exceeds nesting bounds')
        elif char in ']}':
            depth -= 1
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return  # Preserve pinned malformed-JSON -> no recommendation fallback.
    bounded_json(parsed)


def _preflight(config: dict[str, Any], rows: list[dict[str, Any]],
               resolved_names: dict[str, Any], metadata: dict[str, Any]) -> None:
    bounded_json([config, rows, resolved_names, metadata])
    if len(rows) > 2048 or len(resolved_names) > 2048 or len(metadata) > 2048:
        raise ValueError('Cycler catalogue exceeds 2048 records')
    for row in metadata.values():
        if isinstance(row, dict) and isinstance(row.get('usage_tips'), str):
            _preflight_tips(row['usage_tips'])


def cycle_from_snapshot(config: dict[str, Any], rows: list[dict[str, Any]],
                        resolved_names: dict[str, Any],
                        metadata: dict[str, Any]) -> dict[str, Any]:
    """Preserve pinned cycle body; catalogue acquisition is an explicit caller seam.

    ``rows`` is the already-filtered/sorted original get_cycler_list projection.
    Missing/falsy resolutions preserve the pinned empty-stack path. ``None`` is
    the literal named sentinel as well as a possible missing resolution value.
    No strings are passed to a file API or turned into asset capabilities.
    """
    _preflight(config, rows, resolved_names, metadata)
    return _cycle(config, rows, resolved_names, metadata)


def _cycle(config: dict[str, Any], rows: list[dict[str, Any]],
           resolved_names: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    current_index = config.get('current_index', 1)
    model_strength = float(config.get('model_strength', 1.0))
    clip_strength = float(config.get('clip_strength', 1.0))
    use_same_clip_strength = config.get('use_same_clip_strength', True)
    use_preset_strength = config.get('use_preset_strength', False)
    preset_strength_scale = float(config.get('preset_strength_scale', 1.0))
    if not all(math.isfinite(value) and abs(value) <= 1000 for value in
               (model_strength, clip_strength, preset_strength_scale)):
        raise ValueError('Cycler strength/scale exceeds finite bounds')
    include_no_lora = config.get('include_no_lora', False)
    execution_index = config.get('execution_index')
    total_count = len(rows)
    effective_total_count = total_count + 1 if include_no_lora else total_count
    if total_count == 0 and not include_no_lora:
        return {'result': ([],), 'ui': {'current_index': [1], 'next_index': [1],
            'total_count': [0], 'current_lora_name': [''], 'current_lora_filename': [''],
            'error': ['No LoRAs available in pool']}}
    actual_index = execution_index if execution_index is not None else current_index
    clamped_index = max(1, min(actual_index, effective_total_count))
    is_no_lora = include_no_lora and clamped_index == effective_total_count
    if is_no_lora:
        stack = []
        current_name = current_filename = 'No LoRA'
    else:
        current = rows[clamped_index - 1]
        current_name = current_filename = current['file_name']
        name = None if current['file_name'] == 'None' else resolved_names.get(current['file_name'])
        if not name:
            stack = []
        else:
            name = name.replace('/', os.sep)
            if use_preset_strength:
                row = metadata.get(current['file_name'])
                if row:
                    recommended = _tip(row, 'strength')
                    if recommended is not None:
                        model_strength = round(recommended * preset_strength_scale, 2)
                    if use_same_clip_strength:
                        clip_strength = model_strength
                    else:
                        recommended_clip = _tip(row, 'clipStrength')
                        if recommended_clip is not None:
                            clip_strength = round(recommended_clip * preset_strength_scale, 2)
                elif use_same_clip_strength:
                    clip_strength = model_strength
            elif use_same_clip_strength:
                clip_strength = model_strength
            stack = [(name, model_strength, clip_strength)]
    next_index = clamped_index + 1
    if next_index > effective_total_count:
        next_index = 1
    is_next_no_lora = include_no_lora and next_index == effective_total_count
    if is_next_no_lora:
        next_name = next_filename = 'No LoRA'
    else:
        next_lora = rows[next_index - 1]
        next_name = next_filename = next_lora['file_name']
    result = {'result': (stack,), 'ui': {'current_index': [clamped_index],
        'next_index': [next_index], 'total_count': [total_count],
        'current_lora_name': [current_name], 'current_lora_filename': [current_filename],
        'next_lora_name': [next_name], 'next_lora_filename': [next_filename]}}
    bounded_json(result, allow_tuples=True)
    return result
