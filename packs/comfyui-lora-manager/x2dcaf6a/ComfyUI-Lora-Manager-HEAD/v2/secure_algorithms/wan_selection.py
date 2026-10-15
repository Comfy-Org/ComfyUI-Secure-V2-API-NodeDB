"""Native LoRA Manager WAN selector values, with resolution kept separate.

These helpers do not read a library or manufacture metadata. The caller must
resolve each requested entry and supply its actual trigger words and verified
relative display name. They add no SDK, route or node registration, and do
not implement JACK's consumer. Nonfinite/wire behavior remains unverified.
"""
from __future__ import annotations

import logging
import os

from .lora_requests import get_loras_list

logger = logging.getLogger(__name__)


def begin_widget_selection(low_mem_load=False, merge_loras=True, **kwargs):
    loras_list = []
    prev_lora = kwargs.get('prev_lora', None)
    if prev_lora is not None:
        loras_list.extend(prev_lora)
    if not merge_loras:
        low_mem_load = False
    blocks = kwargs.get('blocks', {})
    return {'loras_list': loras_list, 'all_trigger_words': [], 'active_loras': [],
            'selected_blocks': blocks.get('selected_blocks', {}),
            'layer_filter': blocks.get('layer_filter', ''),
            'low_mem_load': low_mem_load, 'merge_loras': merge_loras}


def begin_text_selection(low_mem_load=False, merge_lora=True, **kwargs):
    # Native text producer examines blocks before extending the predecessor;
    # the widget producer does the reverse. Preserve their error precedence.
    blocks = kwargs.get('blocks', {})
    selected_blocks = blocks.get('selected_blocks', {})
    layer_filter = blocks.get('layer_filter', '')
    loras_list = []
    prev_lora = kwargs.get('prev_lora', None)
    if prev_lora is not None:
        loras_list.extend(prev_lora)
    if not merge_lora:
        low_mem_load = False
    return {'loras_list': loras_list, 'all_trigger_words': [], 'active_loras': [],
            'selected_blocks': selected_blocks, 'layer_filter': layer_filter,
            'low_mem_load': low_mem_load, 'merge_loras': merge_lora}


def iter_widget_requests(loras):
    # Yield lazily: native resolution occurs between successive float
    # conversions. Preflighting all entries would change failure precedence.
    for row in get_loras_list({'loras': loras}):
        if not row.get('active', False):
            continue
        name = row['name']
        strength = float(row['strength'])
        clip_strength = float(row.get('clipStrength', strength))
        yield name, strength, clip_strength


def iter_text_requests(lora_syntax):
    # This producer's native parser is case-sensitive, strips names, skips
    # invalid strengths, and ignores fields beyond the model/clip strengths.
    # Its behavior differs from the shared regex parser used by other nodes.
    for part in lora_syntax.split('<lora:')[1:]:
        end_index = part.find('>')
        if end_index == -1:
            continue
        pieces = part[:end_index].split(':')
        if len(pieces) == 2:
            name = pieces[0].strip()
            try:
                strength = float(pieces[1])
                clip_strength = strength
            except (ValueError, IndexError):
                logger.warning("Invalid strength for LoRA '%s'. Skipping.", name)
                continue
        elif len(pieces) >= 3:
            name = pieces[0].strip()
            try:
                strength = float(pieces[1])
                clip_strength = float(pieces[2])
            except (ValueError, IndexError):
                logger.warning("Invalid strengths for LoRA '%s'. Skipping.", name)
                continue
        else:
            continue
        yield name, strength, clip_strength


def append_resolved_entry(state, request, path, relative_name, trigger_words):
    """Append one resolved entry using caller-owned identity/metadata values.

    The proposed production path is a public logical catalogue selector.
    relative_name must already reflect a verified native name projection.
    Supplying plain strings/lists in pure tests is not resolver/metadata proof.
    """
    name, strength, clip_strength = request
    item = {'path': path, 'strength': strength,
            'name': os.path.splitext(relative_name)[0],
            'blocks': state['selected_blocks'], 'layer_filter': state['layer_filter'],
            'low_mem_load': state['low_mem_load'], 'merge_loras': state['merge_loras']}
    state['loras_list'].append(item)
    state['active_loras'].append((name, strength, clip_strength))
    state['all_trigger_words'].extend(trigger_words)


def finish_selection(state):
    words = state['all_trigger_words']
    trigger_words = ',, '.join(words) if words else ''
    formatted = []
    for name, strength, clip_strength in state['active_loras']:
        if abs(strength - clip_strength) > 0.001:
            formatted.append(f'<lora:{name}:{str(strength).strip()}:{str(clip_strength).strip()}>')
        else:
            formatted.append(f'<lora:{name}:{str(strength).strip()}>')
    return state['loras_list'], trigger_words, ' '.join(formatted)
