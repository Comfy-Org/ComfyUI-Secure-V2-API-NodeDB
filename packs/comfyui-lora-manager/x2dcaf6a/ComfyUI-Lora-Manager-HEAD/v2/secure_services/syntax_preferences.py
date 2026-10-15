"""Actual whole-record syntax-setting author through public durable read/CAS.

This is the one-key profile of native SettingsHandler.update_settings. It creates
no editor, revision input, migration, cache epoch or temporary storage fallback.
"""
from __future__ import annotations

from comfy_api.latest import sdk
from .preview_preferences import KEY, FORMAT, encode, read_preferences

FIELD = 'lora_syntax_format'
DEFAULT = 'legacy'


def next_document(document, value):
    """Pinned equality/assignment semantics; preserve unrelated field values."""
    values = {} if document is None else document['preferences']
    # Native handler skips equal values before calling SettingsManager.set.
    # Python equality (including bool/number equality) is deliberately retained.
    if value == values.get(FIELD, DEFAULT):
        return None
    changed = values.copy()
    changed[FIELD] = value
    return {'format': FORMAT, 'preferences': changed}


async def save_syntax_preference(value):
    # Validate the authored value before reading storage. The whole prospective
    # document is separately encoded below, including all unrelated fields.
    encode({'format': FORMAT, 'preferences': {FIELD: value}})
    current = await read_preferences()
    document = next_document(current['document'], value)
    if document is None:
        return {'updated': True, 'changed': False, 'revision': current['revision']}
    text = encode(document)  # <=1MiB encoded whole record; never truncate/reset.
    result = await sdk.ctx().storage.compare_and_set(KEY, current['revision'], text)
    # A genuine competing write is surfaced; no hidden read/retry or overwrite.
    return {'updated': result['updated'], 'changed': result['updated'],
            'revision': result['revision']}
