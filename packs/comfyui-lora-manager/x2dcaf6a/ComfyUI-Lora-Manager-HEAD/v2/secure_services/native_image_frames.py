"""Permissioned raw image conversion, preserving native lazy frame errors.

No filesystem writer or execution collector is supplied by this helper.
"""
from __future__ import annotations

from ..secure_algorithms.image_conversion import normalize_native_images, native_frame_image


async def native_image_frames(images):
    raw = await images.raw()
    for frame in normalize_native_images(raw):
        yield frame, native_frame_image(frame)
