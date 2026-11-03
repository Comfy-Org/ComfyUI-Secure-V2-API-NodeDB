"""The one ComfyUI core function the converted Inspire image nodes call, for use inside a guest.

A Secure Nodes V2 guest cannot import ComfyUI's `comfy` package. LoadImagesFromDir //Inspire
resizes later images to the first one with `comfy.utils.common_upscale(..., "bilinear", "center")`
(pristine inspire/image_util.py:147). This is that function, line for line, from ComfyUI's
comfy/utils.py. Only the bilinear path is reachable from the pack, so bislerp/lanczos refuse.
"""

import torch


def common_upscale(samples, width, height, upscale_method, crop):
    orig_shape = tuple(samples.shape)
    if len(orig_shape) > 4:
        samples = samples.reshape(samples.shape[0], samples.shape[1], -1, samples.shape[-2], samples.shape[-1])
        samples = samples.movedim(2, 1)
        samples = samples.reshape(-1, orig_shape[1], orig_shape[-2], orig_shape[-1])
    if crop == "center":
        old_width = samples.shape[-1]
        old_height = samples.shape[-2]
        old_aspect = old_width / old_height
        new_aspect = width / height
        x = 0
        y = 0
        if old_aspect > new_aspect:
            x = round((old_width - old_width * (new_aspect / old_aspect)) / 2)
        elif old_aspect < new_aspect:
            y = round((old_height - old_height * (old_aspect / new_aspect)) / 2)
        s = samples.narrow(-2, y, old_height - y * 2).narrow(-1, x, old_width - x * 2)
    else:
        s = samples

    if upscale_method in ("bislerp", "lanczos"):
        raise NotImplementedError(f"common_upscale: {upscale_method} is not used by the converted nodes")
    out = torch.nn.functional.interpolate(s, size=(height, width), mode=upscale_method)

    if len(orig_shape) == 4:
        return out

    out = out.reshape((orig_shape[0], -1, orig_shape[1]) + (height, width))
    return out.movedim(2, 1).reshape(orig_shape[:-2] + (height, width))
