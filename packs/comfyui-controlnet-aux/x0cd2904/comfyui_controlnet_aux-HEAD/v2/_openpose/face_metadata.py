"""Restore the observed original Face mapping attributes after tensor transport."""
import hashlib
import json
from collections import OrderedDict
from pathlib import Path

METADATA_SHA256 = '05d479b5bdbee7d6c53584a7bfeb9a74eb3788b33cb78f026c1ed8ff0854c026'
CHECKPOINT_SHA256 = '8beb52e548624ffcc4aed12af7aee7dcbfaeea420c75609fee999fe7add79d43'

def restore_face_metadata(value, record):
    if record.get('kind') != 'face' or record.get('sha256') != CHECKPOINT_SHA256:
        raise RuntimeError('OpenPose Face metadata requires the exact original checkpoint')
    if record.get('raw_metadata_policy') != 'exact-original-ordered-metadata' or record.get('raw_metadata_sha256') != METADATA_SHA256:
        raise RuntimeError('OpenPose Face exact metadata artifact is unselected')
    raw = Path(__file__).with_name('original-face-metadata.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != METADATA_SHA256:
        raise RuntimeError('OpenPose Face original metadata artifact bytes differ')
    metadata = json.loads(raw)
    if metadata['checkpoint_sha256'] != CHECKPOINT_SHA256 or metadata['original_reader_evidence_sha256'] != record.get('restricted_shape_evidence_sha256'):
        raise RuntimeError('OpenPose Face metadata original reader binding differs')
    if not isinstance(value, dict) or list(value) != record['raw_top_level_keys']:
        raise RuntimeError('OpenPose Face original mapping order differs')
    entries = metadata['metadata_entries']
    original_metadata = OrderedDict((key, dict(attrs)) for key, attrs in entries)
    if hasattr(value, '_metadata'):
        existing = value._metadata
        if type(existing) is not OrderedDict or list(existing.items()) != list(original_metadata.items()):
            raise RuntimeError('OpenPose Face public reader metadata differs from original')
    restored = OrderedDict(value.items())
    restored._metadata = original_metadata
    return restored
