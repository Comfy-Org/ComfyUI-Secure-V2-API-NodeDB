"""SEGSPreview for Impact Pack under Secure Nodes V2 (fidelity repair NED r1).

SEGSPreview.doit and the helpers it calls are upstream code, copied verbatim below as AST source segments of the
pristine files (tools: extract_segs_preview.py). The only changes are at the boundary, in `doit`:
- it is a coroutine taking a `save_preview` coroutine;
- upstream's `folder_paths.get_save_image_path(...)` line is dropped;
- upstream's `cropped_pil.save(<temp folder>/<name>.webp)` plus its `results.append({...})` become
  `results.extend(await save_preview(cropped_pil))`, so the preview goes through the SDK.
Everything else is upstream's, line for line: scale match, crop, combined/binary masks, min_alpha, alpha preview,
masked outputs, and the early return with no result.
Copied:
#   ComfyUI-Impact-Pack/modules/impact/utils.py L14-22 TensorBatchBuilder
#   ComfyUI-Impact-Pack/modules/impact/utils.py L119-124 general_tensor_resize
#   ComfyUI-Impact-Pack/modules/impact/utils.py L128-128 LANCZOS
#   ComfyUI-Impact-Pack/modules/impact/utils.py L129-143 tensor_resize
#   ComfyUI-Impact-Pack/modules/impact/utils.py L153-155 tensor2pil
#   ComfyUI-Impact-Pack/modules/impact/utils.py L158-159 pil2tensor
#   ComfyUI-Impact-Pack/modules/impact/utils.py L162-163 numpy2pil
#   ComfyUI-Impact-Pack/modules/impact/utils.py L166-173 to_pil
#   ComfyUI-Impact-Pack/modules/impact/utils.py L201-206 _tensor_check_image
#   ComfyUI-Impact-Pack/modules/impact/utils.py L355-361 to_binary_mask
#   ComfyUI-Impact-Pack/modules/impact/utils.py L552-560 crop_ndarray4
#   ComfyUI-Impact-Pack/modules/impact/utils.py L563-563 crop_tensor4
#   ComfyUI-Impact-Pack/modules/impact/utils.py L588-589 crop_image
#   ComfyUI-Impact-Pack/modules/impact/utils.py L623-630 make_3d_mask
#   ComfyUI-Impact-Pack/modules/impact/core.py L46-48 SEG
#   ComfyUI-Impact-Pack/modules/impact/core.py L1000-1042 segs_scale_match
#   ComfyUI-Impact-Pack/modules/impact/segs_nodes.py L293-427 SEGSPreview
"""
import types
from collections import namedtuple

import numpy as np
import torch
from PIL import Image


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


# ComfyUI-Impact-Pack/modules/impact/utils.py L162-163 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def numpy2pil(image):
    return Image.fromarray(np.clip(255. * image.squeeze(0), 0, 255).astype(np.uint8))


# ComfyUI-Impact-Pack/modules/impact/utils.py L166-173 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def to_pil(image):
    if isinstance(image, Image.Image):
        return image
    if isinstance(image, torch.Tensor):
        return tensor2pil(image)
    if isinstance(image, np.ndarray):
        return numpy2pil(image)
    raise ValueError(f"Cannot convert {type(image)} to PIL.Image")


# ComfyUI-Impact-Pack/modules/impact/utils.py L201-206 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def _tensor_check_image(image):
    if image.ndim != 4:
        raise ValueError(f"Expected NHWC tensor, but found {image.ndim} dimensions")
    if image.shape[-1] not in (1, 3, 4):
        raise ValueError(f"Expected 1, 3 or 4 channels for image, but found {image.shape[-1]} channels")
    return


# ComfyUI-Impact-Pack/modules/impact/utils.py L355-361 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def to_binary_mask(mask, threshold=0):
    mask = make_3d_mask(mask)

    mask = mask.clone().cpu()
    mask[mask > threshold] = 1.
    mask[mask <= threshold] = 0.
    return mask


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


# ComfyUI-Impact-Pack/modules/impact/utils.py L623-630 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def make_3d_mask(mask):
    if len(mask.shape) == 4:
        return mask.squeeze(0)

    elif len(mask.shape) == 2:
        return mask.unsqueeze(0)

    return mask


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


# ComfyUI-Impact-Pack/modules/impact/segs_nodes.py L293-427 (SEGSPreview.doit, boundary-adapted as described above) (pristine sha256 51e4b938627fb4f7958c220940747476cafc7f424f87035a886e8a0686e1ac8a)
async def segs_preview_doit(segs, alpha_mode=True, min_alpha=0.0, fallback_image_opt=None, *, save_preview):

    results = list()
    result_image_list = []

    if fallback_image_opt is not None:
        segs = core.segs_scale_match(segs, fallback_image_opt.shape)

    if min_alpha != 0:
        min_alpha = int(255 * min_alpha)

    if len(segs[1]) > 0:
        if segs[1][0].cropped_image is not None:
            batch_count = len(segs[1][0].cropped_image)
        elif fallback_image_opt is not None:
            batch_count = len(fallback_image_opt)
        else:
            return {"ui": {"images": results}}

        for seg in segs[1]:
            result_image_batch = None
            cached_mask = None

            def get_combined_mask():
                nonlocal cached_mask

                if cached_mask is not None:
                    return cached_mask
                else:
                    if isinstance(seg.cropped_mask, np.ndarray):
                        masks = torch.tensor(seg.cropped_mask)
                    else:
                        masks = seg.cropped_mask

                    cached_mask = (masks[0] * 255).to(torch.uint8)
                    for x in masks[1:]:
                        cached_mask |= (x * 255).to(torch.uint8)
                    cached_mask = (cached_mask/255.0).to(torch.float32)
                    cached_mask = utils.to_binary_mask(cached_mask, 0.1)
                    cached_mask = cached_mask.numpy()

                    return cached_mask

            def stack_image(image, mask=None):
                nonlocal result_image_batch

                if isinstance(image, np.ndarray):
                    image = torch.from_numpy(image)

                if mask is not None:
                    image *= torch.tensor(mask)[None, ..., None]

                if result_image_batch is None:
                    result_image_batch = image
                else:
                    result_image_batch = torch.concat((result_image_batch, image), dim=0)

            for i in range(batch_count):
                cropped_image = None

                if seg.cropped_image is not None:
                    cropped_image = seg.cropped_image[i, None]
                elif fallback_image_opt is not None:
                    # take from original image
                    ref_image = fallback_image_opt[i].unsqueeze(0)
                    cropped_image = utils.crop_image(ref_image, seg.crop_region)

                if cropped_image is not None:
                    if isinstance(cropped_image, np.ndarray):
                        cropped_image = torch.from_numpy(cropped_image)

                    cropped_image = cropped_image.clone()
                    cropped_pil = utils.to_pil(cropped_image)

                    if alpha_mode:
                        if isinstance(seg.cropped_mask, np.ndarray):
                            cropped_mask = seg.cropped_mask
                        else:
                            if seg.cropped_image is not None and len(seg.cropped_image) != len(seg.cropped_mask):
                                cropped_mask = get_combined_mask()
                            else:
                                cropped_mask = seg.cropped_mask[i].numpy()

                        mask_array = (cropped_mask * 255).astype(np.uint8)

                        if min_alpha != 0:
                            mask_array[mask_array < min_alpha] = min_alpha

                        mask_pil = Image.fromarray(mask_array, mode='L').resize(cropped_pil.size)
                        cropped_pil.putalpha(mask_pil)
                        stack_image(cropped_image, cropped_mask)
                    else:
                        stack_image(cropped_image)

                    results.extend(await save_preview(cropped_pil))

            if result_image_batch is not None:
                result_image_list.append(result_image_batch)

    return {"ui": {"images": results}, "result": (result_image_list,) }


# ---------------------------------------------------------------- the V2 part (not upstream code)
utils = types.SimpleNamespace(tensor_resize=tensor_resize, crop_image=crop_image, to_pil=to_pil,
                              to_binary_mask=to_binary_mask)
core = types.SimpleNamespace(segs_scale_match=segs_scale_match)


def to_upstream_segs(segs):
    """Impact v2's SEGS value as upstream SEG values (the same fields, in the same order)."""
    shape, items = segs
    return tuple(shape), [SEG(*item) for item in items]
