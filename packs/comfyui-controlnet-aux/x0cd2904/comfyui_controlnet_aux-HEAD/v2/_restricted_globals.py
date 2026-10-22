"""Restricted torch decode that provably cannot resolve a host-registered safe global.

The ComfyUI host registers extra torch safe globals at import (comfy/utils.py), so the
in-process route can never satisfy "no registered safe globals". What the guard needs is
that the decode of THIS sealed checkpoint cannot depend on them. torch's weights_only
unpickler resolves every referenced GLOBAL from its DEFAULT allowlist before consulting
user additions. So every global the checkpoint's single data.pkl references must be in
the default allowlist, and the referenced set must equal the one pinned by inspection.
Nothing generic: the pinned list is per checkpoint; legacy (non-zip) archives are refused
(_restricted_legacy_globals.py is their companion proof).

Fail closed (review follow-ups L1-L3):
- L1: torch.load takes the zip route only for a payload that starts with a zip local-file header.
  Any other payload is refused: torch would decode it as a legacy archive, which this proof never
  scanned, even when a zip is appended to it.
- L2: data.pkl must be STORED, as torch.save writes it, and at most 64 MiB.
- L3: any open, read or scan error is one clean refusal.
- A-L1: the scanned bytes must be byte-identical to the record torch.load itself unpickles (torch's own zip
  reader), so a difference between the two zip parsers can never choose what is scanned.
"""
import io
import zipfile

MAX_PICKLE_BYTES = 64 * 1024 * 1024


def torch_record(payload):
    """The data.pkl bytes torch.load unpickles: torch's own reader, PyTorchFileReader.get_record('data.pkl')."""
    import torch
    return torch._C.PyTorchFileReader(io.BytesIO(payload)).get_record('data.pkl')


def checkpoint_pickle_globals(payload):
    from torch import _weights_only_unpickler as unpickler
    if type(payload) is not bytes or payload[:4] != b'PK\x03\x04':
        raise RuntimeError('restricted decode requires a zip torch archive')
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except Exception:
        raise RuntimeError('restricted decode requires a zip torch archive') from None
    with archive:
        records = [info for info in archive.infolist() if info.filename.rsplit('/', 1)[-1] == 'data.pkl']
        if len(records) != 1:
            raise RuntimeError('restricted torch archive must hold exactly one data.pkl record')
        record = records[0]
        if record.compress_type != zipfile.ZIP_STORED or record.compress_size != record.file_size or record.file_size > MAX_PICKLE_BYTES:
            raise RuntimeError('restricted torch archive data.pkl record is not stored or exceeds the scan bound')
        try:
            data = archive.read(record)
            same = torch_record(payload) == data
            found = unpickler.get_globals_in_pkl(io.BytesIO(data)) if same else None
        except Exception:
            raise RuntimeError('restricted decode could not scan data.pkl') from None
        if found is None:
            raise RuntimeError('restricted torch archive data.pkl differs from the record torch decodes')
        return sorted(found)


def require_default_allowlisted(payload, pinned):
    from torch import _weights_only_unpickler as unpickler
    if type(pinned) is not list or not pinned or any(type(g) is not str for g in pinned):
        raise RuntimeError('restricted decode pinned pickle globals are unselected')
    found = checkpoint_pickle_globals(payload)
    allowed = unpickler._get_allowed_globals()
    if found != pinned or any(g not in allowed for g in found):
        raise RuntimeError('checkpoint pickle globals differ from inspection or leave the default restricted allowlist')
    return found
