"""Bounded overwrite collection; execution provenance remains a caller seam.

Manual strings are user-authored metadata, not host file/model authority.
Opaque refs never enter this helper. A caller must project wired identity through
a sanctioned host operation before supplying its name; this module does not
read patcher/function objects or claim such an operation is implemented.
"""
from __future__ import annotations

from typing import Any

from ..secure_algorithms.bounds import bounded_json

CLIP_SKIP_SENTINEL = -25
FIELDS = ('prompt', 'negative_prompt', 'seed', 'steps', 'cfg_scale', 'sampler',
          'scheduler', 'model', 'loras', 'size', 'clip_skip', 'additional_data')


def collect_overwrites(values: dict[str, Any], *, model_name: str | None = None,
                       sampler_name: str | None = None) -> dict[str, Any]:
    """Pinned truthy-field filtering and sentinel behavior over closed inputs.

    For a non-string model/sampler slot, the corresponding supplied name replaces
    its inert marker. Missing identity preserves the pinned skip path. This seam
    is not a substitute for actual ModelRef/SamplerRef identity acquisition.
    """
    if type(values) is not dict:
        raise ValueError('Metadata overwrite input must be an object')
    if any(name is not None and type(name) is not str for name in (model_name, sampler_name)):
        raise ValueError('Projected identity must be a string or null')
    return _collect(values, model_name, sampler_name)


def _collect(values: dict[str, Any], model_name: str | None,
             sampler_name: str | None) -> dict[str, Any]:
    result = {}
    for key in FIELDS:
        value = values.get(key)
        if key == 'model' and not isinstance(value, str):
            value = model_name
        elif key == 'sampler' and not isinstance(value, str):
            value = sampler_name
        if key == 'clip_skip':
            if value != CLIP_SKIP_SENTINEL:
                result[key] = value
        elif value:
            result[key] = value
    return result


def sampler_name_from_function_name(name: str | None) -> str | None:
    """Pinned name-only transform, NOT host sampler-function access."""
    bounded_json(name)
    if not isinstance(name, str) or not name:
        return None
    if name == 'dpm_fast_function':
        return 'dpm_fast'
    if name == 'dpm_adaptive_function':
        return 'dpm_adaptive'
    if name.startswith('sample_'):
        result = name[len('sample_'):]
        if result == 'unipc':
            return 'uni_pc'
        if result == 'unipc_bh2':
            return 'uni_pc_bh2'
        return result or None
    return None
