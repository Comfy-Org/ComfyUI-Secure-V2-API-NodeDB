"""Exact native full Prompt composition over the selected durable text library."""
import re
from ..secure_algorithms.bounds import bounded_json, MAX_STRING_BYTES
from .durable_wildcard_library import expand_saved_text

async def encode_saved_prompt(clip, text, seed=None, **slots):
    bounded_json([text, seed, slots])
    expanded = await expand_saved_text(text, seed)
    words = [value for key, value in slots.items() if re.match(r'^trigger_words\d+$', key) and value]
    if words:
        if all(isinstance(value, str) for value in words + [expanded]):
            projected = sum(len(value.encode('utf-8')) for value in words + [expanded]) + 2 * len(words)
            if projected > MAX_STRING_BYTES:
                raise ValueError('Composed prompt exceeds bounds')
        expanded = ', '.join(words + [expanded])
    if clip is None:
        raise RuntimeError('ERROR: clip input is invalid: None\n\nIf the clip is from a checkpoint loader node your checkpoint does not contain a valid clip or text encoder model.')
    return await clip.encode(expanded), expanded
