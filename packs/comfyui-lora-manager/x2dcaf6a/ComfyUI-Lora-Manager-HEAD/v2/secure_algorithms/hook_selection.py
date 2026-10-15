"""Pinned Create Hook pure values; genuine hook/model operations remain outside.

Iteration is lazy: the owner resolves/loads/combines each yielded request before
advancing. Record a success only after actual clone_and_combine has succeeded.
These helpers neither invent HookGroups nor substitute authored library data.
"""
from __future__ import annotations

from .lora_requests import apply_lora_syntax_format, get_loras_list


def iter_hook_requests(text, loras, syntax_format):
    del text  # Native text is a frontend widget value, never an execution parser.
    for lora in get_loras_list({'loras': loras}):
        if not lora.get('active', False):
            continue
        lora_name = apply_lora_syntax_format(lora['name'], syntax_format)
        model_strength = float(lora['strength'])
        clip_strength = float(lora.get('clipStrength', model_strength))
        if model_strength == 0.0 and clip_strength == 0.0:
            continue
        yield lora_name, model_strength, clip_strength


def hook_validation_names(loras, syntax_format):
    # Queue validation differs deliberately: it ignores malformed row objects,
    # coerces missing names to empty strings, and includes active zero rows.
    if not loras:
        return []
    active_names = []
    for lora in get_loras_list({'loras': loras}):
        if not isinstance(lora, dict):
            continue
        if not lora.get('active', False):
            continue
        active_names.append(apply_lora_syntax_format(str(lora.get('name') or ''), syntax_format))
    return active_names


def append_hook_success(active_loras, all_trigger_words, request, trigger_words):
    lora_name, model_strength, clip_strength = request
    active_loras.append((lora_name, model_strength, clip_strength))
    all_trigger_words.extend(trigger_words)


def finish_hook_summaries(active_loras, all_trigger_words):
    trigger_words_text = ',, '.join(all_trigger_words) if all_trigger_words else ''
    formatted_loras = []
    for name, model_s, clip_s in active_loras:
        if abs(model_s - clip_s) > 0.001:
            formatted_loras.append(f'<lora:{name}:{model_s}:{clip_s}>')
        else:
            formatted_loras.append(f'<lora:{name}:{model_s}>')
    return trigger_words_text, ' '.join(formatted_loras)
