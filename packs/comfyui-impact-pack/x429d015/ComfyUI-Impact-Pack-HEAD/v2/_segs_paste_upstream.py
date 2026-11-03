"""SEGSPaste for Impact Pack under Secure Nodes V2 (fidelity repair r4).

SEGSPaste.doit and the helpers it calls are upstream code, copied verbatim below as AST source segments of the
pristine files. Boundary stand-ins (not upstream code): `comfy.model_management` answers this guest's torch device;
`comfy.utils.common_upscale` is the pack's own copy of Core's (_image_ops.py); `args` answers Core's default launch
arguments (no --highvram, no --gpu-only), so the result lands on the CPU as upstream's does by default.
Copied:
#   ComfyUI-Impact-Pack/modules/impact/utils.py L14-22 TensorBatchBuilder
#   ComfyUI-Impact-Pack/modules/impact/utils.py L119-124 general_tensor_resize
#   ComfyUI-Impact-Pack/modules/impact/utils.py L128-128 LANCZOS
#   ComfyUI-Impact-Pack/modules/impact/utils.py L129-143 tensor_resize
#   ComfyUI-Impact-Pack/modules/impact/utils.py L153-155 tensor2pil
#   ComfyUI-Impact-Pack/modules/impact/utils.py L158-159 pil2tensor
#   ComfyUI-Impact-Pack/modules/impact/utils.py L201-206 _tensor_check_image
#   ComfyUI-Impact-Pack/modules/impact/utils.py L209-214 _tensor_check_mask
#   ComfyUI-Impact-Pack/modules/impact/utils.py L227-293 tensor_paste
#   ComfyUI-Impact-Pack/modules/impact/utils.py L442-478 tensor_gaussian_blur_mask
#   ComfyUI-Impact-Pack/modules/impact/utils.py L552-560 crop_ndarray4
#   ComfyUI-Impact-Pack/modules/impact/utils.py L563-563 crop_tensor4
#   ComfyUI-Impact-Pack/modules/impact/utils.py L588-589 crop_image
#   ComfyUI-Impact-Pack/modules/impact/utils.py L633-640 make_4d_mask
#   ComfyUI-Impact-Pack/modules/impact/utils.py L661-664 resize_mask
#   ComfyUI-Impact-Pack/modules/impact/core.py L46-48 SEG
#   ComfyUI-Impact-Pack/modules/impact/core.py L1000-1042 segs_scale_match
#   ComfyUI-Impact-Pack/modules/impact/segs_nodes.py L170-243 SEGSPaste
"""
import types
from collections import namedtuple

import numpy as np
import torch
import torchvision
from PIL import Image

from . import _image_ops


# ---------------------------------------------------------------- boundary stand-ins
def _guest_device():
    return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


comfy = types.SimpleNamespace(model_management=types.SimpleNamespace(get_torch_device=_guest_device),
                              utils=types.SimpleNamespace(common_upscale=_image_ops.common_upscale))
args = types.SimpleNamespace(highvram=False, gpu_only=False)


# ---------------------------------------------------------------- upstream Impact Pack modules/impact/utils.py
# ComfyUI-Impact-Pack/modules/impact/utils.py L14-22 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
class TensorBatchBuilder:
    def __init__(self):
        self.tensor = None

    def concat(self, new_tensor):
        if self.tensor is None:
            self.tensor = new_tensor
        else:
            self.tensor = torch.concat((self.tensor, new_tensor), dim=0)

# ComfyUI-Impact-Pack/modules/impact/utils.py L119-124 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def general_tensor_resize(image, w: int, h: int):
    _tensor_check_image(image)
    image = image.permute(0, 3, 1, 2)
    image = torch.nn.functional.interpolate(image, size=(h, w), mode="bilinear")
    image = image.permute(0, 2, 3, 1)
    return image

# ComfyUI-Impact-Pack/modules/impact/utils.py L128-128 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
LANCZOS = (Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)

# ComfyUI-Impact-Pack/modules/impact/utils.py L129-143 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def tensor_resize(image, w: int, h: int):
    _tensor_check_image(image)
    if image.shape[3] >= 3:
        scaled_images = TensorBatchBuilder()
        for single_image in image:
            single_image = single_image.unsqueeze(0)
            single_pil = tensor2pil(single_image)
            scaled_pil = single_pil.resize((w, h), resample=LANCZOS)

            single_image = pil2tensor(scaled_pil)
            scaled_images.concat(single_image)

        return scaled_images.tensor
    else:
        return general_tensor_resize(image, w, h)

# ComfyUI-Impact-Pack/modules/impact/utils.py L153-155 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def tensor2pil(image):
    _tensor_check_image(image)
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(0), 0, 255).astype(np.uint8))

# ComfyUI-Impact-Pack/modules/impact/utils.py L158-159 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

# ComfyUI-Impact-Pack/modules/impact/utils.py L201-206 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def _tensor_check_image(image):
    if image.ndim != 4:
        raise ValueError(f"Expected NHWC tensor, but found {image.ndim} dimensions")
    if image.shape[-1] not in (1, 3, 4):
        raise ValueError(f"Expected 1, 3 or 4 channels for image, but found {image.shape[-1]} channels")
    return

# ComfyUI-Impact-Pack/modules/impact/utils.py L209-214 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def _tensor_check_mask(mask):
    if mask.ndim != 4:
        raise ValueError(f"Expected NHWC tensor, but found {mask.ndim} dimensions")
    if mask.shape[-1] != 1:
        raise ValueError(f"Expected 1 channel for mask, but found {mask.shape[-1]} channels")
    return

# ComfyUI-Impact-Pack/modules/impact/utils.py L227-293 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def tensor_paste(image1, image2, left_top, mask):
    """
    Pastes image2 onto image1 at position left_top using mask.
    Supports both RGB and RGBA images.
    """
    _tensor_check_image(image1)
    _tensor_check_image(image2)
    _tensor_check_mask(mask)

    if image2.shape[1:3] != mask.shape[1:3]:
        mask = resize_mask(mask.squeeze(dim=3), image2.shape[1:3]).unsqueeze(dim=3)

    x, y = left_top
    _, h1, w1, c1 = image1.shape
    _, h2, w2, c2 = image2.shape

    # Calculate image patch size
    w = min(w1, x + w2) - x
    h = min(h1, y + h2) - y

    # If the patch is out of bound, nothing to do!
    if w <= 0 or h <= 0:
        return

    mask = mask[:, :h, :w, :]

    # Get the region to be modified
    region1 = image1[:, y:y+h, x:x+w, :]
    region2 = image2[:, :h, :w, :]

    # Handle RGB and RGBA cases
    if c1 == 3 and c2 == 3:
        # Both RGB - simple case
        image1[:, y:y+h, x:x+w, :] = (1 - mask) * region1 + mask * region2

    elif c1 == 4 and c2 == 4:
        # Both RGBA - need to handle alpha channel separately
        # RGB channels
        image1[:, y:y+h, x:x+w, :3] = (
            (1 - mask) * region1[:, :, :, :3] +
            mask * region2[:, :, :, :3]
        )

        # Alpha channel - use "over" composition
        a1 = region1[:, :, :, 3:4]
        a2 = region2[:, :, :, 3:4] * mask
        new_alpha = a1 + a2 * (1 - a1)
        image1[:, y:y+h, x:x+w, 3:4] = new_alpha

    elif c1 == 4 and c2 == 3:
        # Target is RGBA, source is RGB - assume source is fully opaque
        image1[:, y:y+h, x:x+w, :3] = (
            (1 - mask) * region1[:, :, :, :3] +
            mask * region2
        )
        # Alpha channel - reduce alpha where mask is applied
        image1[:, y:y+h, x:x+w, 3:4] = region1[:, :, :, 3:4] * (1 - mask) + mask

    elif c1 == 3 and c2 == 4:
        # Target is RGB, source is RGBA - apply source alpha to mask
        effective_mask = mask * region2[:, :, :, 3:4]
        image1[:, y:y+h, x:x+w, :] = (
            (1 - effective_mask) * region1 +
            effective_mask * region2[:, :, :, :3]
        )

    return

# ComfyUI-Impact-Pack/modules/impact/utils.py L442-478 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def tensor_gaussian_blur_mask(mask, kernel_size, sigma=10.0):
    """Return NHWC torch.Tenser from ndim == 2 or 4 `np.ndarray` or `torch.Tensor`"""
    if isinstance(mask, np.ndarray):
        mask = torch.from_numpy(mask)

    if mask.ndim == 2:
        mask = mask[None, ..., None]
    elif mask.ndim == 3:
        mask = mask[..., None]

    _tensor_check_mask(mask)

    if kernel_size <= 0:
        return mask

    kernel_size = kernel_size*2+1

    shortest = min(mask.shape[1], mask.shape[2])
    if shortest <= kernel_size:
        kernel_size = int(shortest/2)
        if kernel_size % 2 == 0:
            kernel_size += 1
        if kernel_size < 3:
            return mask  # skip feathering

    prev_device = mask.device
    device = comfy.model_management.get_torch_device()
    mask.to(device)

    # apply gaussian blur
    mask = mask[:, None, ..., 0]
    blurred_mask = torchvision.transforms.GaussianBlur(kernel_size=kernel_size, sigma=sigma)(mask)
    blurred_mask = blurred_mask[:, 0, ..., None]

    blurred_mask.to(prev_device)

    return blurred_mask

# ComfyUI-Impact-Pack/modules/impact/utils.py L552-560 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def crop_ndarray4(npimg, crop_region):
    x1 = crop_region[0]
    y1 = crop_region[1]
    x2 = crop_region[2]
    y2 = crop_region[3]

    cropped = npimg[:, y1:y2, x1:x2, :]

    return cropped

# ComfyUI-Impact-Pack/modules/impact/utils.py L563-563 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
crop_tensor4 = crop_ndarray4

# ComfyUI-Impact-Pack/modules/impact/utils.py L588-589 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def crop_image(image, crop_region):
    return crop_tensor4(image, crop_region)

# ComfyUI-Impact-Pack/modules/impact/utils.py L633-640 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def make_4d_mask(mask):
    if len(mask.shape) == 3:
        return mask.unsqueeze(0)

    elif len(mask.shape) == 2:
        return mask.unsqueeze(0).unsqueeze(0)

    return mask

# ComfyUI-Impact-Pack/modules/impact/utils.py L661-664 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def resize_mask(mask, size):
    mask = make_4d_mask(mask)
    resized_mask = torch.nn.functional.interpolate(mask, size=size, mode='bilinear', align_corners=False)
    return resized_mask.squeeze(0)


utils = types.SimpleNamespace(tensor_resize=tensor_resize, crop_image=crop_image, tensor_paste=tensor_paste,
                                tensor_gaussian_blur_mask=tensor_gaussian_blur_mask, resize_mask=resize_mask)


# ---------------------------------------------------------------- upstream Impact Pack modules/impact/core.py
# ComfyUI-Impact-Pack/modules/impact/core.py L46-48 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
SEG = namedtuple("SEG",
                 ['cropped_image', 'cropped_mask', 'confidence', 'crop_region', 'bbox', 'label', 'control_net_wrapper'],
                 defaults=[None])

# ComfyUI-Impact-Pack/modules/impact/core.py L1000-1042 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def segs_scale_match(segs, target_shape):
    h = segs[0][0]
    w = segs[0][1]

    th = target_shape[1]
    tw = target_shape[2]

    if (h == th and w == tw) or h == 0 or w == 0:
        return segs

    rh = th / h
    rw = tw / w

    new_segs = []
    for seg in segs[1]:
        cropped_image = seg.cropped_image
        cropped_mask = seg.cropped_mask
        x1, y1, x2, y2 = seg.crop_region
        bx1, by1, bx2, by2 = seg.bbox

        crop_region = int(x1*rw), int(y1*rw), int(x2*rh), int(y2*rh)
        bbox = int(bx1*rw), int(by1*rw), int(bx2*rh), int(by2*rh)
        new_w = crop_region[2] - crop_region[0]
        new_h = crop_region[3] - crop_region[1]

        if isinstance(cropped_mask, np.ndarray):
            cropped_mask = torch.from_numpy(cropped_mask)

        if isinstance(cropped_mask, torch.Tensor) and len(cropped_mask.shape) == 3:
            cropped_mask = torch.nn.functional.interpolate(cropped_mask.unsqueeze(0), size=(new_h, new_w), mode='bilinear', align_corners=False)
            cropped_mask = cropped_mask.squeeze(0)
        else:
            cropped_mask = torch.nn.functional.interpolate(cropped_mask.unsqueeze(0).unsqueeze(0), size=(new_h, new_w), mode='bilinear', align_corners=False)
            cropped_mask = cropped_mask.squeeze(0).squeeze(0).numpy()

        if cropped_image is not None:
            cropped_image = utils.tensor_resize(cropped_image if isinstance(cropped_image, torch.Tensor) else torch.from_numpy(cropped_image), new_w, new_h)
            cropped_image = cropped_image.numpy()

        new_seg = SEG(cropped_image, cropped_mask, seg.confidence, crop_region, bbox, seg.label, seg.control_net_wrapper)
        new_segs.append(new_seg)

    return (th, tw), new_segs


core = types.SimpleNamespace(segs_scale_match=segs_scale_match)


# ---------------------------------------------------------------- upstream Impact Pack segs_nodes.py
# ComfyUI-Impact-Pack/modules/impact/segs_nodes.py L170-243 (pristine sha256 51e4b938627fb4f7958c220940747476cafc7f424f87035a886e8a0686e1ac8a)
class SEGSPaste:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
                     "image": ("IMAGE", ),
                     "segs": ("SEGS", ),
                     "feather": ("INT", {"default": 5, "min": 0, "max": 100, "step": 1}),
                     "alpha": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1}),
                     },
                "optional": {"ref_image_opt": ("IMAGE", ), }
                }

    RETURN_TYPES = ("IMAGE", )
    FUNCTION = "doit"

    CATEGORY = "ImpactPack/Detailer"

    DESCRIPTION = "This node provides a function to paste the enhanced SEGS, improved through the SEGS detailer, back onto the original image."

    @staticmethod
    def doit(image, segs, feather, alpha=255, ref_image_opt=None):
        # Optimized SEGS paste node: preallocates result and avoids repeated concat.
        segs = core.segs_scale_match(segs, image.shape)

        batch_size, _, _, _ = image.shape
        result = torch.empty_like(image)

        with torch.no_grad():
            for i in range(batch_size):
                # avoid extra clone/unsqueeze
                image_i = image[i].unsqueeze(0).clone()

                for seg in segs[1]:
                    ref_image = None

                    # ref_image handling
                    if ref_image_opt is None and seg.cropped_image is not None:
                        cropped_image = seg.cropped_image
                        if isinstance(cropped_image, np.ndarray):
                            cropped_image = torch.from_numpy(cropped_image)
                        ref_image = cropped_image[i].unsqueeze(0)
                    elif ref_image_opt is not None:
                        ref_tensor = ref_image_opt[i].unsqueeze(0)
                        ref_image = utils.crop_image(ref_tensor, seg.crop_region)

                    if ref_image is None:
                        continue

                    # mask handling
                    cmask = seg.cropped_mask
                    if cmask.ndim == 3 and len(cmask) == batch_size:
                        mask = cmask[i]
                    elif cmask.ndim == 3 and len(cmask) > 1:
                        # statt OR-Schleife → vektorisiert
                        mask = torch.any(cmask > 0.1, dim=0).float()
                    else:  # ndim == 2
                        mask = cmask

                    # blur + alpha
                    mask = utils.tensor_gaussian_blur_mask(mask, feather) * (alpha / 255.0)

                    # ensure same device
                    mask = mask.to(image_i.device)
                    ref_image = ref_image.to(image_i.device)

                    x, y, *_ = seg.crop_region
                    utils.tensor_paste(image_i, ref_image, (x, y), mask)

                result[i] = image_i[0]

        if not args.highvram and not args.gpu_only:
            result = result.cpu()

        return (result,)


# ---------------------------------------------------------------- V2: Impact v2's SEGS into upstream SEGSPaste
def paste(image, segs, feather, alpha, ref_image_opt):
    """Upstream SEGSPaste.doit on Impact v2's SEGS: upstream SEG values (cropped images as tensors, masks as given)."""
    shape, items = segs
    upstream = (tuple(shape), [SEG(*item) for item in items])
    (result,) = SEGSPaste.doit(image, upstream, feather, alpha, ref_image_opt)
    return result
