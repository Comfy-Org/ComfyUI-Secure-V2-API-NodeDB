"""Verify assigned immutable JSON payloads before the native loader runs."""
import hashlib
import json
from pathlib import Path

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_SCAN_ENTRIES = 128

def verify(root=None):
    root = Path(__file__).parent if root is None else Path(root)
    profile_path = root / '_resource_profile.json'
    if profile_path.is_symlink():
        raise ValueError('bundled resource profile symlink')
    with profile_path.open('rb') as file:
        raw = file.read(16385)
    if len(raw) > 16384:
        raise ValueError('bundled resource profile byte budget')
    profile = json.loads(raw)
    expected = profile['resources']
    if type(expected) is not dict or len(expected) != 21:
        raise ValueError('bundled resource profile inventory')
    base = root / 'data'
    if base.is_symlink() or not base.is_dir():
        raise ValueError('bundled resource directory')
    actual, scanned = set(), 0
    for group in base.iterdir():
        scanned += 1
        if scanned > MAX_SCAN_ENTRIES or group.is_symlink() or not group.is_dir():
            raise ValueError('bundled resource scan profile')
        for file in group.iterdir():
            scanned += 1
            if scanned > MAX_SCAN_ENTRIES or file.is_symlink() or not file.is_file():
                raise ValueError('bundled resource scan profile')
            actual.add(file.relative_to(root).as_posix())
    if actual != set(expected):
        raise ValueError('bundled resource inventory differs')
    total = 0
    for name, row in expected.items():
        parts = Path(name).parts
        if len(parts) != 3 or parts[0] != 'data' or any(p in ('.', '..') for p in parts):
            raise ValueError('bundled resource name profile')
        if row['bytes'] > MAX_FILE_BYTES:
            raise ValueError('bundled resource byte budget')
        path = root / name
        with path.open('rb') as file:
            data = file.read(min(row['bytes'] + 1, MAX_FILE_BYTES + 1))
        total += len(data)
        if total > MAX_TOTAL_BYTES or len(data) != row['bytes']:
            raise ValueError('bundled resource byte budget')
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('bundled resource hash differs')
    return profile
