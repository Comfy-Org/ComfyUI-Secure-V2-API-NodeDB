"""Pack-owned native IMAGE result projection using permissioned raw refs.

This is a result helper, not a registered Save node. Callers require raw/tensor
capability and output capability for the separate writer. Native collection,
recipe/storage, writer failures and supported format branches remain separate.
"""
from comfy_api.latest import io, sdk


async def image_result_body(images, saved_ui):
    import numpy as np

    raw_images = await images.raw()
    # Keep the native process_image normalization, including ndarray behavior.
    if isinstance(raw_images, (list, np.ndarray)):
        pass
    else:
        if len(raw_images.shape) == 3:
            raw_images = [raw_images]
        else:
            raw_images = [frame for frame in raw_images]
    # Publish the native list/container through the existing public VALUE
    # bridge, preserving HWC rank rather than coercing each frame to BHWC.
    frames = await sdk.ValueRef.from_value(raw_images)
    return io.NodeOutput(frames, ui=saved_ui)
