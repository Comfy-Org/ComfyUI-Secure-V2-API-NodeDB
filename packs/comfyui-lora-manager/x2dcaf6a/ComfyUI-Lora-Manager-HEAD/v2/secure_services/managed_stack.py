"""Workflow-owned stack production over admitted catalogue identities.

No model application, filesystem scanner or provider network authority. Library
records use the existing local tested service; Cloud identity remains pending.
"""
from __future__ import annotations

from . import managed_library as library
from .catalogue_cache import cached_metadata


async def stack_managed_loras(loras, lora_stack=None):
    # Keep predecessor entries and their scalar types in the returned stack.
    # Value preparation retains native predecessor types; asset authority is separate.
    requested = library._requested(loras, lora_stack, '', await library._syntax_format(),
        convert_stack_strengths=False)
    stack = list(lora_stack or [])
    if not requested:
        return stack, '', ''
    catalogue = await library.sdk.ctx().assets.list('loras')
    for name in catalogue:
        library._logical(name)
    triggers, active = [], []
    incoming = len(stack)
    for index, (display, name, strength, clip_strength) in enumerate(requested):
        # Pinned predecessor trigger lookup uses extract_lora_name (which may
        # discard folders in legacy syntax), not direct absolute-path lookup.
        lookup = display if index < incoming else name
        logical = library._match(lookup, catalogue)
        metadata = await cached_metadata(logical)
        civitai = (metadata.get('civitai') or {}) if metadata is not None else {}
        words = civitai.get('trainedWords', [])
        triggers.extend(words)
        if index >= incoming:
            # Logical registered names replace legacy host paths; this is a
            # deliberate authority boundary, never an absolute path alias.
            stack.append((logical, strength, clip_strength))
            active.append(f'<lora:{display}:{strength}:{clip_strength}>'
                if abs(strength - clip_strength) > .001 else f'<lora:{display}:{strength}>')
    return stack, ',, '.join(triggers), ' '.join(active)
