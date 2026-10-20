"""Pack-owned APZ Pillow decode over encoded managed-asset bytes.

Actual original pixel/mask/frame algorithm, selected fp32 purpose only. This
does not provide an input picker or counter lifecycle and is not whole-pack
qualification. The selected operator must bind original intermediate_dtype
to float32; fp16_intermediates is a separate remaining purpose.
"""
import io

import numpy as np
import torch
from PIL import Image, ImageFile, ImageOps, ImageSequence, UnidentifiedImageError


MAX_ENCODED_BYTES = 64 * 1024**2
MAX_DECODED_BYTES = 64 * 1024**2
MAX_FRAMES = 256


def _pillow(fn, arg):
    # Exact small node_helpers.pillow operation from actual Core44564 source.
    prev_value = None
    try:
        x = fn(arg)
    except (OSError, UnidentifiedImageError, ValueError):
        prev_value = ImageFile.LOAD_TRUNCATED_IMAGES
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        x = fn(arg)
    finally:
        if prev_value is not None:
            ImageFile.LOAD_TRUNCATED_IMAGES = prev_value
    return x


def _preflight_frame(width, height, retained_image_bytes, retained_mask_bytes, has_alpha):
    if width < 1 or height < 1:
        raise ValueError("APZ image dimensions must be positive")
    image_bytes = width * height * 3 * 4
    mask_bytes = (width * height if has_alpha else 64 * 64) * 4
    # Inputs, NumPy conversions, per-frame lists, and final cat coexist. The
    # admission estimate is explicit; it is not a process RSS quota.
    projected = 3 * (retained_image_bytes + image_bytes) + 3 * (retained_mask_bytes + mask_bytes)
    if projected > MAX_DECODED_BYTES:
        raise ValueError("APZ projected image/mask work exceeds 64 MiB")
    return image_bytes, mask_bytes


def decode_image_bytes(encoded):
    if type(encoded) is not bytes:
        raise TypeError("APZ encoded image must be bytes")
    if len(encoded) > MAX_ENCODED_BYTES:
        raise ValueError("APZ encoded image exceeds 64 MiB")
    source = io.BytesIO(encoded)
    img = None
    try:
        img = _pillow(Image.open, source)
        output_images = []
        output_masks = []
        w, h = None, None
        dtype = torch.float32
        image_total = mask_total = 0
        for frame_index, i in enumerate(ImageSequence.Iterator(img)):
            if frame_index >= MAX_FRAMES:
                raise ValueError("APZ image exceeds 256-frame admission")
            # Check header geometry before exif_transpose can copy pixels.
            # Codecs may allocate during seek/open; an external process cap
            # is still required. This estimate is not an allocator quota.
            _preflight_frame(i.size[0], i.size[1], image_total, mask_total, True)
            i = _pillow(ImageOps.exif_transpose, i)
            alpha = 'A' in i.getbands() or (i.mode == 'P' and 'transparency' in i.info)
            expected_width, expected_height = i.size
            image_bytes, mask_bytes = _preflight_frame(
                expected_width, expected_height, image_total, mask_total, alpha)
            if i.mode == 'I':
                i = i.point(lambda i: i * (1 / 255))
            frame = i.convert("RGB")
            if len(output_images) == 0:
                w = frame.size[0]
                h = frame.size[1]
            if frame.size[0] != w or frame.size[1] != h:
                continue
            frame_np = np.array(frame).astype(np.float32) / 255.0
            frame_tensor = torch.from_numpy(frame_np)[None,]
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            elif i.mode == 'P' and 'transparency' in i.info:
                mask = np.array(i.convert('RGBA').getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            output_images.append(frame_tensor.to(dtype=dtype))
            output_masks.append(mask.unsqueeze(0).to(dtype=dtype))
            image_total += image_bytes
            mask_total += mask_bytes
            if img.format == "MPO":
                break
        if len(output_images) > 1:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]
        return output_image, output_mask
    finally:
        if img is not None:
            img.close()
        source.close()
