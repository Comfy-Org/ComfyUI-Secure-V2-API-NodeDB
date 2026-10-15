"""Standard-model LoRA chain, not Nunchaku or library-provider parity.

An authenticated catalogue/descriptor adapter must supply these entries. This
module does not replace editable library records with header/default values.
It is not yet wired into the user-facing loader nodes.
"""
from __future__ import annotations

import math
from comfy_api.latest import sdk
from ..secure_algorithms.bounds import bounded_json

MAX_LORAS = 64


def _preflight(entries):
    bounded_json(entries)
    if type(entries) is not list or len(entries) > MAX_LORAS:
        raise ValueError('LoRA chain must contain at most 64 entries')
    for entry in entries:
        if type(entry) is not dict or set(entry) != {
            'name', 'asset_name', 'model_strength', 'clip_strength', 'trigger_words'
        }:
            raise ValueError('LoRA entry must be a closed descriptor')
        name, asset = entry['name'], entry['asset_name']
        if type(name) is not str or len(name.encode('utf-8')) > 4096:
            raise ValueError('LoRA display name exceeds bounds')
        if (type(asset) is not str or not asset or len(asset.encode('utf-8')) > 4096
                or asset.startswith(('/', '\\')) or '\\' in asset or ':' in asset
                or any(part in ('', '.', '..') for part in asset.split('/'))):
            raise ValueError('LoRA asset must be a logical registered name')
        for key in ('model_strength', 'clip_strength'):
            value = entry[key]
            if type(value) not in (float, int) or not math.isfinite(value) or not -100 <= value <= 100:
                raise ValueError('LoRA strengths must be finite in [-100,100]')
        triggers = entry['trigger_words']
        if type(triggers) is not list or len(triggers) > 256 or any(
            type(word) is not str or len(word.encode('utf-8')) > 4096 for word in triggers
        ):
            raise ValueError('LoRA trigger words exceed bounds')


async def apply_standard_entries(model, clip, entries, *, profile):
    if profile != 'standard':
        raise NotImplementedError('Nunchaku/vendor model profile is not admitted by this standard adapter')
    _preflight(entries)  # Check the entire chain before the first broker mutation.
    loaded, triggers = [], []
    for entry in entries:
        asset = await sdk.ctx().assets.resolve('loras', entry['asset_name'])
        model, clip = await model.apply_lora(
            asset, clip, entry['model_strength'],
            entry['clip_strength'] if clip is not None else 0.0,
        )
        # Keep original user strengths for formatted output even when CLIP absent.
        loaded.append({
            'name': entry['name'],
            'model_strength': entry['model_strength'],
            'clip_strength': entry['clip_strength'],
            'include_clip_strength': abs(entry['model_strength'] - entry['clip_strength']) > 0.001,
        })
        triggers.extend(entry['trigger_words'])
    formatted = []
    for item in loaded:
        if item['include_clip_strength']:
            formatted.append(f"<lora:{item['name']}:{item['model_strength']}:{item['clip_strength']}>")
        else:
            formatted.append(f"<lora:{item['name']}:{item['model_strength']}>")
    return model, clip, ',, '.join(triggers) if triggers else '', ' '.join(formatted)
