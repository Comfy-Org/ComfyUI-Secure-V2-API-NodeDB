"""Prompt composition/CLIP broker over an explicitly supplied library snapshot.

Authenticated library selection, cache invalidation and node/frontend adapters
remain separate pending work. This helper never substitutes shipped defaults.
"""
import re

from ..secure_algorithms.bounds import bounded_json, MAX_STRING_BYTES
from ..secure_algorithms.wildcards import expand_from_snapshot

_TRIGGER_WORD_PATTERN = re.compile(r'^trigger_words\d+$')


def compose_from_snapshot(text, table, seed=None, **kwargs):
    bounded_json(kwargs)
    expanded = expand_from_snapshot(text, table, seed)
    # Pinned Prompt.encode preserves kwargs insertion order, not numeric slot
    # ordering, and ignores falsy trigger values and unrelated optional inputs.
    words = [value for key, value in kwargs.items()
             if _TRIGGER_WORD_PATTERN.match(key) and value]
    if not words:
        return expanded
    # Retain native join TypeError for bounded inert non-string trigger/text.
    values = words + [expanded]
    if all(type(value) is str for value in values):
        size = sum(len(value.encode('utf-8')) for value in values) + 2 * (len(values) - 1)
        if size > MAX_STRING_BYTES:
            raise ValueError('Composed prompt exceeds UTF-8 bounds')
    return ', '.join(values)


async def encode_from_snapshot(clip, text, table, seed=None, **kwargs):
    prompt = compose_from_snapshot(text, table, seed, **kwargs)
    if clip is None:
        raise RuntimeError('ERROR: clip input is invalid: None\n\nIf the clip is from a checkpoint loader node your checkpoint does not contain a valid clip or text encoder model.')
    # Public ClipRef.encode uses tokenize + encode_from_tokens_scheduled on
    # the host; token tensors and scheduled conditioning never become JSON.
    # No tokenize/encode_from_tokens(return_pooled=True) substitution is used.
    conditioning = await clip.encode(prompt)
    return conditioning, prompt
