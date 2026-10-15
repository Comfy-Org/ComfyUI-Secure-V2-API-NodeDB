"""Pack-owned metadata edits; authored fields never confer asset/path authority.

The caller still needs a validated catalogue identity before choosing a record.
HTTP routing, cache sorting and frontend identity are not implemented here.
"""
from __future__ import annotations

import copy
import re

from .documents import LIMITS, _validate_tree


def apply_metadata_updates(metadata, updates):
    """Preserve pinned shallow-dict merge and normalized replacement-tag rules."""
    if type(metadata) is not dict or type(updates) is not dict:
        raise ValueError('Model metadata and updates must be JSON objects')
    _validate_tree([metadata, updates], LIMITS['model-edits'])
    result = copy.deepcopy(metadata)
    for key, value in updates.items():
        if key == 'tags' and isinstance(value, list):
            normalized = []
            seen = set()
            for tag in value:
                if isinstance(tag, str):
                    text = tag.strip().lower()
                    if text and text not in seen:
                        normalized.append(text)
                        seen.add(text)
            result[key] = normalized
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key].update(copy.deepcopy(value))
        else:
            result[key] = copy.deepcopy(value)
    _validate_tree(result, LIMITS['model-edits'])
    return result


def append_metadata_tags(metadata, new_tags):
    """Keep existing spelling/order; deduplicate additions case-insensitively."""
    if type(metadata) is not dict or type(new_tags) is not list:
        raise ValueError('Model metadata must be an object and tags an array')
    _validate_tree([metadata, new_tags], LIMITS['model-edits'])
    result = copy.deepcopy(metadata)
    raw_tags = result.get('tags', [])
    existing_tags = list(raw_tags) if isinstance(raw_tags, list) else []
    # Preserve native malformed-existing-tag failure rather than inventing data.
    existing_lower = [tag.lower() for tag in existing_tags]
    for tag in new_tags:
        if isinstance(tag, str) and tag.strip():
            normalized = tag.strip().lower()
            if normalized not in existing_lower:
                existing_tags.append(normalized)
                existing_lower.append(normalized)
    result['tags'] = existing_tags
    _validate_tree(result, LIMITS['model-edits'])
    return result


async def update_model_document(key, updates):
    # Materialize caller data once. CAS retries reapply a PURE transform to the
    # newest record; no provider/cache/file side effects occur inside retries.
    updates = apply_metadata_updates({}, updates)
    return await _edit_model_record(key, updates,
        lambda old: apply_metadata_updates(old, updates))


async def append_model_document_tags(key, tags):
    _validate_tree(tags, LIMITS['model-edits'])
    if type(tags) is not list:
        raise ValueError('Tags must be an array')
    tags = copy.deepcopy(tags)
    return await _edit_model_record(key, {'tags': tags},
        lambda old: append_metadata_tags(old, tags))


async def _edit_model_record(key, submitted, transform):
    """Retry only the existing pure edit transform, never storage failures.

    The selected-asset caller owns digest authority. Validate its closed key
    before I/O, then preserve and validate the whole identity-bound envelope.
    These internal edits retain the existing eight-conflict retry policy; the
    note editor's explicit expected-revision CAS remains a separate operation.
    """
    from .durable_model_records import (compare_and_set_document, encode_record,
                                        read_document, validate_record)
    from .managed_library import FORMAT

    if type(key) is not str or not re.fullmatch(r'model\.digest\.[0-9a-f]{64}', key):
        raise ValueError('Model record key must contain the selected SHA-256')
    digest = key[len('model.digest.'):]
    # Refuse oversized submitted data before any read. The complete transformed
    # envelope is checked again before CAS; no truncation or temporary fallback.
    encode_record({'format': FORMAT, 'sha256': digest, 'metadata': submitted})
    for _ in range(8):
        state = await read_document(key, 'model-edits')
        document = state['document']
        if document is None:
            document = {'format': FORMAT, 'sha256': digest, 'metadata': {}}
        else:
            validate_record(document, digest)
        updated = {**document, 'metadata': transform(document['metadata'])}
        result = await compare_and_set_document(key, 'model-edits', state['revision'], updated)
        if result['updated']:
            # Return only the durable CAS receipt, not an unnecessary copy of
            # authored notes or a temporary VALUE handle from the old adapter.
            return result
    raise RuntimeError('Model record CAS conflict after eight attempts')
