"""Model hashes (Secure Nodes V2).

The original hashed a host path with hashlib (first 10 hex digits of SHA-256),
kept an in-memory LRU keyed by the file's basename, and persisted a JSON cache
next to the pack (``.cache/model_hash_cache.json``). Here the broker resolves the
catalogue entry and computes the digest (``assets.digest``); the same memory
cache and key are kept. The disk cache is not kept: the pack folder is read-only,
and the digest is computed from the file's current bytes every time.
"""
import os
import threading
from collections import OrderedDict

from comfy_api.latest import sdk

from .._v2_capture import run_async
from .log import print_warning, print_error

CACHE_SIZE_LIMIT = 100

cache_model_hash = OrderedDict()
_cache_lock = threading.Lock()

# folder_paths.map_legacy
_LEGACY_FOLDERS = {"unet": "diffusion_models", "clip": "text_encoders"}


class AssetTarget:
    """A catalogue entry (folder + logical name); the original passed a host path."""

    __slots__ = ("folder", "name")

    def __init__(self, folder, name):
        self.folder = folder
        self.name = name

    def __str__(self):
        return f"{self.folder}/{self.name}"


def asset_target(folder_type, model_name):
    """folder_paths.get_full_path stand-in: raises TypeError for non-string names, as it did."""
    if not isinstance(model_name, str):
        raise TypeError(f"model name must be a string, not {type(model_name).__name__}")
    return AssetTarget(_LEGACY_FOLDERS.get(folder_type, folder_type), model_name)


def calc_hash(filename, use_only_filename=True):
    if not filename:
        print_warning(f"calc_hash: File not found or invalid path: {filename}")
        return ""
    try:
        ref = run_async(sdk.ctx().assets.resolve(filename.folder, filename.name))
    except (FileNotFoundError, ValueError):
        print_warning(f"calc_hash: File not found or invalid path: {filename}")
        return ""

    key = os.path.basename(filename.name) if use_only_filename else str(filename)

    with _cache_lock:
        # Check in-memory cache first
        if key in cache_model_hash:
            return cache_model_hash[key]

    try:
        model_hash = run_async(sdk.ctx().assets.digest(ref, "sha256"))[:10]

        with _cache_lock:
            # Update in-memory cache with size limit
            if len(cache_model_hash) >= CACHE_SIZE_LIMIT:
                cache_model_hash.popitem(last=False)  # Remove oldest item
            cache_model_hash[key] = model_hash

        return model_hash
    except Exception as e:
        print_error(f"Failed to calculate hash for {filename}: {e}")
        return ""
