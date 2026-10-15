"""The upstream resizing math with pack-owned canonical Lanczos pixel conversion."""

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


def lanczos(samples, width, height):
    # Same canonical ComfyUI Lanczos conversion as the pinned node used.
    if samples.ndim == 4:
        samples = (
            samples.squeeze(1) if samples.shape[1] == 1 else samples.movedim(1, -1)
        )
    images = [
        Image.fromarray(np.clip(255.0 * image.cpu().numpy(), 0, 255).astype(np.uint8))
        for image in samples
    ]
    images = [
        image.resize((width, height), resample=Image.Resampling.LANCZOS)
        for image in images
    ]
    images = [
        torch.from_numpy(t).movedim(-1, 0)
        if (t := np.array(image).astype(np.float32) / 255.0).ndim == 3
        else torch.from_numpy(t)
        for image in images
    ]
    result = torch.stack(images)
    return result.to(samples.device, samples.dtype)


def resize(image, width, height, keep_proportion, interpolation="nearest"):
    if keep_proportion is True:
        _, oh, ow, _ = image.shape
        width = ow if width == 0 else width
        height = oh if height == 0 else height
        ratio = min(width / ow, height / oh)
        width = round(ow * ratio)
        height = round(oh * ratio)
    outputs = image.permute([0, 3, 1, 2])
    if interpolation == "lanczos":
        outputs = lanczos(outputs, width, height)
    else:
        outputs = F.interpolate(outputs, size=(height, width), mode=interpolation)
    outputs = outputs.permute([0, 2, 3, 1])
    return outputs, outputs.shape[2], outputs.shape[1]
