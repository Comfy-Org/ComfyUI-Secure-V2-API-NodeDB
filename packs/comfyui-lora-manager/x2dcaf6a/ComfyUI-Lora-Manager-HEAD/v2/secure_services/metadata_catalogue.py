"""Actual managed asset names plus owned editable aliases for metadata joins.

Authored model records use the shared pack durable text adapter. This consumer
does not prove legacy import, sealed installation or Cloud permanence.
"""
from __future__ import annotations

import re
from comfy_api.latest import sdk

from ..secure_algorithms.metadata_recovery import CATALOGUE_FOLDERS, validate_catalogue
from .managed_library import _logical
from .durable_model_records import read_document, validate_record

MAX_FOLDER_ROWS = 2048


async def read_metadata_catalogue():
    """Read bounded current registered names; no host path or scanner cast."""
    rows = []
    for folder, subtype in CATALOGUE_FOLDERS.items():
        names = await sdk.ctx().assets.list(folder)
        if type(names) is not list or len(names) > MAX_FOLDER_ROWS:
            raise ValueError("Metadata folder catalogue exceeds bounds")
        if len(set(names)) != len(names):
            raise ValueError("Duplicate managed catalogue name")
        for name in names:
            name = _logical(name)
            try:
                asset = await sdk.ctx().assets.resolve(folder, name)
                digest = await sdk.ctx().assets.digest(asset)
            except FileNotFoundError:
                # A stale registered entry must never win the name join.
                continue
            if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError("Managed model identity is not SHA-256")
            result = await read_document('model.digest.' + digest, 'model-edits')
            record = result['document']
            if record is not None:
                validate_record(record, digest)
                metadata = record['metadata']
            else:
                metadata = {}
            # Pinned scanner file_name is the on-disk stem, not provider title.
            basename = name.rsplit('/', 1)[-1]
            stem = basename.rsplit('.', 1)[0] if '.' in basename else basename
            alias = metadata.get('model_name', stem)
            if type(alias) is not str:
                raise ValueError("Stored model alias must be text")
            rows.append({'folder': folder, 'name': name, 'sub_type': subtype,
                         'file_name': stem, 'model_name': alias})
    validate_catalogue(rows)
    return rows
