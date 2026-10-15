"""Native Save normalization and frame construction; no invented image policy."""
from __future__ import annotations


def normalize_native_images(images):
    import numpy as np

    if isinstance(images, (list, np.ndarray)):
        return images
    if len(images.shape) == 3:
        return [images]
    return [image for image in images]


def native_frame_image(image):
    import numpy as np
    from PIL import Image

    img = 255.0 * image.cpu().numpy()
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
