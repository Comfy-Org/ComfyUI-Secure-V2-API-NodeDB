"""Restricted torch decode that provably cannot resolve a host-registered safe global.

The ComfyUI host registers extra torch safe globals at import (comfy/utils.py), so the
in-process route can never satisfy "no registered safe globals". What the guard needs is
that the decode of THIS sealed checkpoint cannot depend on them. torch's weights_only
unpickler resolves every referenced GLOBAL from its DEFAULT allowlist before consulting
user additions. So every global the checkpoint's single data.pkl references must be in
the default allowlist, and the referenced set must equal the one pinned by inspection.
Nothing generic: the pinned list is per checkpoint; legacy (non-zip) archives are refused.
"""
import io
import zipfile


def checkpoint_pickle_globals(payload):
    from torch import _weights_only_unpickler as unpickler
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        raise RuntimeError('restricted decode requires a zip torch archive') from None
    with archive:
        records = [n for n in archive.namelist() if n.rsplit('/', 1)[-1] == 'data.pkl']
        if len(records) != 1:
            raise RuntimeError('restricted torch archive must hold exactly one data.pkl record')
        return sorted(unpickler.get_globals_in_pkl(io.BytesIO(archive.read(records[0]))))


def require_default_allowlisted(payload, pinned):
    from torch import _weights_only_unpickler as unpickler
    if type(pinned) is not list or not pinned or any(type(g) is not str for g in pinned):
        raise RuntimeError('restricted decode pinned pickle globals are unselected')
    found = checkpoint_pickle_globals(payload)
    allowed = unpickler._get_allowed_globals()
    if found != pinned or any(g not in allowed for g in found):
        raise RuntimeError('checkpoint pickle globals differ from inspection or leave the default restricted allowlist')
    return found
