"""Pinned core image annotations expressed as confined managed asset identities."""
from __future__ import annotations

from .managed_library import _logical

# Core 6257422 folder_paths.annotated_filepath removes the suffix plus one
# separator character. Preserve that behavior even if the caller omitted a space.
ANNOTATIONS: tuple[tuple[str, str, int], ...] = (
    ('[output]', 'output', 9),
    ('[input]', 'input', 8),
    ('[temp]', 'temp', 7),
)


def managed_image_name(value: str) -> tuple[str, str]:
    """Return only an input/output/temp folder and a confined logical name.

    Unknown annotations remain literal input filenames, as in the pinned core.
    Absolute paths, parent traversal and drive selectors remain outside the
    managed-name profile and are rejected by the shared logical-name boundary.
    """
    if type(value) is not str:
        raise ValueError('Image selection must be a managed logical name')
    for suffix, folder, trim in ANNOTATIONS:
        if value.endswith(suffix):
            return folder, _logical(value[:-trim])
    return 'input', _logical(value)
