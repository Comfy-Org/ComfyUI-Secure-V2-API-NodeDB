"""Saved-library Text/Prompt consumers; authenticated Cloud adapter pending.

Reads the complete bounded owned document on each execution, never a source
file cache or immutable replacement for editable wildcards.
"""
from __future__ import annotations

from ..secure_algorithms.bounds import bounded_json
from ..secure_algorithms.wildcards import SnapshotWildcardExpander, expand_from_snapshot
from .documents import read_document, compare_and_set_document
from .prompt import encode_from_snapshot

KEY = 'wildcard.library'
FORMAT = 'loramanager.wildcard-library.v1'


async def read_library():
    record = await read_document(KEY, 'wildcard-doc')
    document = record['document']
    if document is None:
        # New-library missing record, not proof of legacy TXT/YAML/JSON import.
        return {'revision': record['revision'], 'entries': {}}
    if set(document) != {'format', 'entries'} or document['format'] != FORMAT:
        raise ValueError('Wildcard library document identity is invalid')
    SnapshotWildcardExpander(document['entries'])
    return {'revision': record['revision'], 'entries': document['entries']}


async def save_library(entries, revision):
    SnapshotWildcardExpander(entries)
    return await compare_and_set_document(KEY, 'wildcard-doc', revision,
        {'format': FORMAT, 'entries': entries})


async def expand_saved_text(text, seed=None):
    bounded_json([text, seed])
    library = await read_library()
    return expand_from_snapshot(text, library['entries'], seed)


async def encode_saved_prompt(clip, text, seed=None, **slots):
    bounded_json([text, seed, slots])
    library = await read_library()
    return await encode_from_snapshot(clip, text, library['entries'], seed, **slots)
