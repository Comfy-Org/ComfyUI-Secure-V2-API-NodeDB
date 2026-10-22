"""Restricted decode proof for LEGACY (non-zip) torch archives; the companion of _restricted_globals.py (zip archives).

A legacy archive goes through torch.load(io.BytesIO(payload), weights_only=True). That never takes the tar route, which
needs a real file, so it loads exactly five pickles with the weights_only unpickler, in order:
1. the magic number;
2. the protocol version;
3. sys_info;
4. the object (its storages are persistent ids);
5. the storage keys.
Every GLOBAL that decode can resolve is therefore named in those five pickles.

They are read here with torch's own get_globals_in_pkl, the same opcode handling and module/name mapping as
Unpickler.load. The found set must equal the per-archive pinned list. Every entry must be in torch's DEFAULT restricted
allowlist, which the unpickler consults before any user-registered safe global, so the decode cannot depend on a global
the host registers (ComfyUI registers several at import).

Fail closed:
- zip payloads are refused here (use _restricted_globals);
- the scan reads at most the first 64 MiB, even inside a single pickle (review Low-2);
- any read or scan error is one clean refusal.
"""
import io

LEGACY_PICKLES = ('magic', 'protocol', 'sys_info', 'object', 'storage_keys')
MAX_PICKLE_BYTES = 64 * 1024 * 1024


def legacy_checkpoint_pickle_globals(payload):
    from torch import _weights_only_unpickler as unpickler
    if type(payload) is not bytes or payload[:4] == b'PK\x03\x04':
        raise RuntimeError('restricted legacy decode requires a non-zip torch archive')
    # Review Low-2: only the first 64 MiB is scanned, so the bound also holds inside a single pickle; a pickle that runs
    # past it cannot be scanned, which is a refusal.
    stream, found = io.BytesIO(payload[:MAX_PICKLE_BYTES]), set()
    try:
        for _part in LEGACY_PICKLES:
            found.update(unpickler.get_globals_in_pkl(stream))
    except Exception:
        raise RuntimeError('restricted legacy decode could not scan the legacy pickles') from None
    return sorted(found)


def require_default_allowlisted_legacy(payload, pinned):
    from torch import _weights_only_unpickler as unpickler
    if type(pinned) is not list or not pinned or any(type(g) is not str for g in pinned):
        raise RuntimeError('restricted decode pinned pickle globals are unselected')
    found = legacy_checkpoint_pickle_globals(payload)
    allowed = unpickler._get_allowed_globals()
    if found != pinned or any(g not in allowed for g in found):
        raise RuntimeError('checkpoint pickle globals differ from inspection or leave the default restricted allowlist')
    return found
