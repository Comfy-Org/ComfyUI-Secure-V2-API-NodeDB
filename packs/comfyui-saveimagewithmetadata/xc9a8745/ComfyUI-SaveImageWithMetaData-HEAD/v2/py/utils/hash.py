"""Model hashes (Secure Nodes V2).

The original hashed a host path from folder_paths.get_full_path (first 10 hex digits of
SHA-256) and cached the result per path for the life of the process. Here the broker
resolves the catalogue entry and computes the digest (``assets.digest``); the result and
the per-entry memory cache are the same.
"""
import os
import posixpath

from comfy_api.latest import sdk

from .._v2_capture import run_async

cache_model_hash = {}

# folder_paths.map_legacy (core 6257422b)
_LEGACY_FOLDERS = {"unet": "diffusion_models", "clip": "text_encoders"}


class AssetTarget(tuple):
    """A catalogue entry (folder, logical name); the original passed a host path."""

    __slots__ = ()

    def __new__(cls, folder, name):
        return super().__new__(cls, (folder, name))

    @property
    def folder(self):
        return self[0]

    @property
    def name(self):
        return self[1]


def asset_target(folder_type, model_name):
    """folder_paths.get_full_path, answering with a catalogue entry instead of a path:
    the same name normalisation, and None when no root holds the file."""
    folder = _LEGACY_FOLDERS.get(folder_type, folder_type)
    name = posixpath.relpath(posixpath.join("/", model_name), "/")
    if run_async(sdk.ctx().assets.exists(folder, name)):
        return AssetTarget(folder, name)
    return None


def calc_hash(filename):
    if filename in cache_model_hash:
        return cache_model_hash[filename]
    if filename is None:
        # The original then called open(None, "rb"), which raises this TypeError.
        os.fspath(filename)
    ref = run_async(sdk.ctx().assets.resolve(filename.folder, filename.name))
    model_hash = run_async(sdk.ctx().assets.digest(ref, "sha256"))[:10]

    cache_model_hash[filename] = model_hash
    return model_hash
