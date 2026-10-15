"""Pinned pure helpers; settings value is supplied by the public consumer."""
from __future__ import annotations
import logging
import os
import re
from typing import Any
logger = logging.getLogger(__name__)

def apply_lora_syntax_format(name, syntax_format):
    fmt = syntax_format
    if fmt == 'legacy':
        return name.replace('\\', '/').rstrip('/').split('/')[-1]
    return name

def extract_lora_name(lora_path, syntax_format):
    normalized = lora_path.replace('\\', '/')
    basename = os.path.basename(normalized)
    name_no_ext = os.path.splitext(basename)[0]
    dirname = os.path.dirname(normalized)
    if dirname and dirname not in ('.', '/') and (not normalized.startswith('/')):
        return apply_lora_syntax_format(f'{dirname}/{name_no_ext}', syntax_format)
    return apply_lora_syntax_format(name_no_ext, syntax_format)

def parse_lora_syntax(text: str) -> list[dict[str, Any]]:
    """Parse <lora:name:strength> syntax from text input into a list of dicts.

    Each entry contains: name, model_strength, clip_strength.
    Supports both ``<lora:name:strength>`` and ``<lora:name:model_strength:clip_strength>``.
    """
    pattern = '<lora:([^:>]+):([^:>]+)(?::([^:>]+))?>'
    matches = re.findall(pattern, text, re.IGNORECASE)
    loras = []
    for match in matches:
        model_strength = float(match[1])
        loras.append({'name': match[0], 'model_strength': model_strength, 'clip_strength': float(match[2]) if match[2] else model_strength})
    return loras

def get_loras_list(kwargs):
    """Helper to extract loras list from either old or new kwargs format"""
    if 'loras' not in kwargs:
        return []
    loras_data = kwargs['loras']
    if isinstance(loras_data, dict) and '__value__' in loras_data:
        return loras_data['__value__']
    elif isinstance(loras_data, list):
        return loras_data
    else:
        logger.warning(f'Unexpected loras format: {type(loras_data)}')
        return []


def requested_loras(loras, lora_stack, lora_syntax, syntax_format, *, convert_stack_strengths=True):
    """Prepare values only. Catalogue/model/storage authority is resolved later.

    Loader predecessor strengths are converted by native; Stacker predecessor
    values are not used for weighting and must retain their original types.
    """
    result = []
    for name, strength, clip_strength in lora_stack or []:
        display = extract_lora_name(name, syntax_format)
        normalized = name.replace('\\', '/')
        if convert_stack_strengths:
            strength, clip_strength = float(strength), float(clip_strength)
        result.append((display, normalized, strength, clip_strength))
    for row in get_loras_list({'loras': loras}):
        if not row.get('active', False):
            continue
        display = apply_lora_syntax_format(row['name'], syntax_format)
        strength = float(row['strength'])
        result.append((display, display, strength, float(row.get('clipStrength', strength))))
    for row in parse_lora_syntax(lora_syntax):
        result.append((row['name'], row['name'], row['model_strength'], row['clip_strength']))
    return result
