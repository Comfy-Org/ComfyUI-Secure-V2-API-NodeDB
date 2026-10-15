"""Pinned Randomizer math over an explicit, already-filtered catalogue snapshot.

No scanner/provider, file authority or library persistence is supplied here.
Resolved names are inert strings, not AssetRefs. Seeded draws use local RNGs.
"""
from __future__ import annotations

import math
import os
import random
from typing import Any

from ..secure_algorithms.bounds import bounded_json
from .cycler import _preflight_tips, _tip


def randomize_from_snapshot(config: dict[str, Any], loras: Any,
                            rows: list[dict[str, Any]],
                            resolved_names: dict[str, Any]) -> dict[str, Any]:
    """Preserve dual-seed and locked-item behavior; caller owns pool filtering."""
    bounded_json([config, loras, rows, resolved_names])
    loras = loras['__value__'] if isinstance(loras, dict) and '__value__' in loras else loras
    if len(rows) > 2048 or len(loras) > 2048 or len(resolved_names) > 2048:
        raise ValueError('Randomizer catalogue/input exceeds 2048 entries')
    # Native fixed mode never parses generator-only settings or pool tips.
    # Closed-data and collection-size bounds above still apply.
    if config.get('roll_mode', 'always') == 'fixed':
        return _randomize(config, loras, rows, resolved_names)
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get('usage_tips'), str):
            _preflight_tips(row['usage_tips'])
    # Reject projected count/work and numeric string infinities before sampling.
    for key, default in (('count_fixed', 5), ('count_min', 3), ('count_max', 7)):
        if abs(int(config.get(key, default))) > 2048:
            raise ValueError('Randomizer requested count exceeds 2048')
    for key, default in (('model_strength_min', 0.), ('model_strength_max', 1.),
                         ('clip_strength_min', 0.), ('clip_strength_max', 1.),
                         ('recommended_strength_scale_min', .5),
                         ('recommended_strength_scale_max', 1.)):
        value = float(config.get(key, default))
        if not math.isfinite(value) or abs(value) > 1000:
            raise ValueError('Randomizer strength/scale exceeds finite bounds')
    return _randomize(config, loras, rows, resolved_names)


def _generate(config: dict[str, Any], loras: list[dict[str, Any]],
              rows: list[dict[str, Any]], seed: Any) -> list[dict[str, Any]]:
    count_mode = config.get('count_mode', 'range')
    count_fixed = int(config.get('count_fixed', 5))
    count_min = int(config.get('count_min', 3))
    count_max = int(config.get('count_max', 7))
    strength_min = float(config.get('model_strength_min', 0.0))
    strength_max = float(config.get('model_strength_max', 1.0))
    same = config.get('use_same_clip_strength', True)
    clip_min = float(config.get('clip_strength_min', 0.0))
    clip_max = float(config.get('clip_strength_max', 1.0))
    recommended = config.get('use_recommended_strength', False)
    scale_min = float(config.get('recommended_strength_scale_min', .5))
    scale_max = float(config.get('recommended_strength_scale_max', 1.0))
    locked = [lora for lora in loras if lora.get('locked', False)]
    rng = random.Random(seed)
    target = count_fixed if count_mode == 'fixed' else rng.randint(count_min, count_max)
    slots = target - len(locked)
    if slots < 0:
        slots = 0
        locked = locked[:target]
    locked_names = {os.path.basename(lora['name']) if '/' in str(lora.get('name', ''))
                    else lora['name'] for lora in locked}
    available = [row for row in rows if row['file_name'] not in locked_names]
    if slots > len(available):
        slots = len(available)
    selected = rng.sample(available, slots) if slots > 0 else []
    result = []
    for row in selected:
        tip = _tip(row, 'strength') if recommended else None
        strength = (round(tip * rng.uniform(scale_min, scale_max), 2)
                    if tip is not None else round(rng.uniform(strength_min, strength_max), 2))
        if same:
            clip_strength = strength
        else:
            clip_tip = _tip(row, 'clipStrength') if recommended else None
            clip_strength = (round(clip_tip * rng.uniform(scale_min, scale_max), 2)
                             if clip_tip is not None else round(rng.uniform(clip_min, clip_max), 2))
        result.append({'name': f"{row['folder']}/{row['file_name']}" if row.get('folder') else row['file_name'],
                       'strength': strength, 'clipStrength': clip_strength, 'active': True,
                       'expanded': abs(strength - clip_strength) > .001, 'locked': False})
    result.extend(locked)
    return result


def _stack(loras: list[dict[str, Any]], names: dict[str, Any]) -> list[tuple[Any, ...]]:
    result = []
    for lora in loras:
        if not lora.get('active', False):
            continue
        name = names.get(lora['name'])
        if not name:
            continue
        name = name.replace('/', os.sep)
        strength = float(lora.get('strength', 1.0))
        clip_strength = float(lora.get('clipStrength', strength))
        result.append((name, strength, clip_strength))
    return result


def _randomize(config: dict[str, Any], loras: list[dict[str, Any]],
               rows: list[dict[str, Any]], names: dict[str, Any]) -> dict[str, Any]:
    if config.get('roll_mode', 'always') == 'fixed':
        ui_loras = execution_loras = loras
    else:
        seed = config.get('execution_seed')
        execution_loras = _generate(config, loras, rows, seed) if seed is not None else loras
        ui_loras = _generate(config, loras, rows, config.get('next_seed'))
    result = {'result': (_stack(execution_loras, names),),
              'ui': {'loras': ui_loras, 'last_used': execution_loras}}
    bounded_json(result, allow_tuples=True)
    return result
