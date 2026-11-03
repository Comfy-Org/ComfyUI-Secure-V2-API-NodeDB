"""Upstream helpers for Impact Pack's detailers under Secure Nodes V2 (fidelity repair r6).

The functions below are upstream code, copied verbatim as AST source segments of the pristine utils.py. The resize,
blur, paste, crop and SEGS scale-match helpers come verbatim from _segs_paste_upstream.py (repair r4). The detailer
loops that call them are ported line for line in _secure_nodes.py, where the engine does the VAE encode, the
sampling and the VAE decode.
Copied here:
#   ComfyUI-Impact-Pack/modules/impact/utils.py L25-44 tensor_convert_rgba
#   ComfyUI-Impact-Pack/modules/impact/utils.py L47-68 tensor_convert_rgb
#   ComfyUI-Impact-Pack/modules/impact/utils.py L146-150 tensor_get_size
#   ComfyUI-Impact-Pack/modules/impact/utils.py L176-183 to_tensor
#   ComfyUI-Impact-Pack/modules/impact/utils.py L186-193 to_numpy
#   ComfyUI-Impact-Pack/modules/impact/utils.py L195-198 tensor_putalpha
#   ComfyUI-Impact-Pack/modules/impact/utils.py L609-610 empty_pil_tensor
"""
import types

import numpy as np
import torch
from PIL import Image

from ._segs_paste_upstream import (_tensor_check_image, _tensor_check_mask, crop_ndarray4,
                                   general_tensor_resize, segs_scale_match, tensor_gaussian_blur_mask,
                                   tensor_paste, tensor_resize)


# ---------------------------------------------------------------- upstream Impact Pack modules/impact/utils.py
# ComfyUI-Impact-Pack/modules/impact/utils.py L25-44 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def tensor_convert_rgba(image, prefer_copy=True):
    """Assumes NHWC format tensor with 1, 3 or 4 channels."""
    _tensor_check_image(image)
    n_channel = image.shape[-1]
    if n_channel == 4:
        return image

    if n_channel == 3:
        alpha = torch.ones((*image.shape[:-1], 1))
        return torch.cat((image, alpha), axis=-1)

    if n_channel == 1:
        if prefer_copy:
            image = image.repeat(1, -1, -1, 4)
        else:
            image = image.expand(1, -1, -1, 3)
        return image

    # NOTE: Similar error message as in PIL, for easier googling :P
    raise ValueError(f"illegal conversion (channels: {n_channel} -> 4)")

# ComfyUI-Impact-Pack/modules/impact/utils.py L47-68 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def tensor_convert_rgb(image, prefer_copy=True):
    """Assumes NHWC format tensor with 1, 3 or 4 channels."""
    _tensor_check_image(image)
    n_channel = image.shape[-1]
    if n_channel == 3:
        return image

    if n_channel == 4:
        image = image[..., :3]
        if prefer_copy:
            image = image.copy()
        return image

    if n_channel == 1:
        if prefer_copy:
            image = image.repeat(1, -1, -1, 4)
        else:
            image = image.expand(1, -1, -1, 3)
        return image

    # NOTE: Same error message as in PIL, for easier googling :P
    raise ValueError(f"illegal conversion (channels: {n_channel} -> 3)")

# ComfyUI-Impact-Pack/modules/impact/utils.py L146-150 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def tensor_get_size(image):
    """Mimicking `PIL.Image.size`"""
    _tensor_check_image(image)
    _, h, w, _ = image.shape
    return (w, h)

# ComfyUI-Impact-Pack/modules/impact/utils.py L176-183 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def to_tensor(image):
    if isinstance(image, Image.Image):
        return torch.from_numpy(np.array(image)) / 255.0
    if isinstance(image, torch.Tensor):
        return image
    if isinstance(image, np.ndarray):
        return torch.from_numpy(image)
    raise ValueError(f"Cannot convert {type(image)} to torch.Tensor")

# ComfyUI-Impact-Pack/modules/impact/utils.py L186-193 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def to_numpy(image):
    if isinstance(image, Image.Image):
        return np.array(image)
    if isinstance(image, torch.Tensor):
        return image.numpy()
    if isinstance(image, np.ndarray):
        return image
    raise ValueError(f"Cannot convert {type(image)} to numpy.ndarray")

# ComfyUI-Impact-Pack/modules/impact/utils.py L195-198 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def tensor_putalpha(image, mask):
    _tensor_check_image(image)
    _tensor_check_mask(mask)
    image[..., -1] = mask[..., 0]

# ComfyUI-Impact-Pack/modules/impact/utils.py L609-610 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def empty_pil_tensor(w=64, h=64):
    return torch.zeros((1, h, w, 3), dtype=torch.float32)


utils = types.SimpleNamespace(
    tensor_convert_rgba=tensor_convert_rgba, tensor_convert_rgb=tensor_convert_rgb,
    tensor_get_size=tensor_get_size, to_tensor=to_tensor, to_numpy=to_numpy, tensor_putalpha=tensor_putalpha,
    empty_pil_tensor=empty_pil_tensor, crop_ndarray4=crop_ndarray4, tensor_resize=tensor_resize,
    general_tensor_resize=general_tensor_resize, tensor_gaussian_blur_mask=tensor_gaussian_blur_mask,
    tensor_paste=tensor_paste)


# ---------------------------------------------------------------- V2: SEGS scale match in Impact v2's layout
def scale_match(segs, image_shape, seg_type):
    """Upstream core.segs_scale_match for Impact v2 SEGS.

    When the SEGS already match the image (or have a zero size), upstream returns them unchanged, and so does this.
    Otherwise they are scaled by upstream's own function in upstream's value types and come back in v2's layout
    (cropped images as tensors, since numpy arrays cannot cross the guest wire).
    """
    (h, w), _items = segs
    th = image_shape[1]
    tw = image_shape[2]
    if (h == th and w == tw) or h == 0 or w == 0:
        return segs
    from . import _segs_upstream

    shape, items = _segs_upstream.to_v2_segs(segs_scale_match(_segs_upstream.to_upstream_segs(segs), image_shape),
                                             seg_type)
    items = [item._replace(cropped_image=torch.from_numpy(np.ascontiguousarray(item.cropped_image)))
             if isinstance(item.cropped_image, np.ndarray) else item for item in items]
    return shape, items
