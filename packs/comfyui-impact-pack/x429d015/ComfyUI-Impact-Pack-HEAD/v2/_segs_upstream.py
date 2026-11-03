"""Upstream SEGS operations for Impact Pack under Secure Nodes V2 (fidelity repair r3).

MaskToSEGS and SegsToCombinedMask run upstream code, copied verbatim below as AST source segments of the
pristine files. The V2 part at the end only converts between upstream's SEG value types and the layout Impact v2
passes between nodes (masks as (1, h, w) float32 tensors, plain ints and floats instead of numpy scalars, which
cannot cross the guest wire).
Copied:
#   ComfyUI-Impact-Pack/modules/impact/utils.py L509-520 normalize_region
#   ComfyUI-Impact-Pack/modules/impact/utils.py L523-549 make_crop_region
#   ComfyUI-Impact-Pack/modules/impact/utils.py L613-620 make_2d_mask
#   ComfyUI-Impact-Pack/modules/impact/utils.py L623-630 make_3d_mask
#   ComfyUI-Impact-Pack/modules/impact/core.py L46-48 SEG
#   ComfyUI-Impact-Pack/modules/impact/core.py L1296-1407 mask_to_segs
#   ComfyUI-Impact-Pack/modules/impact/core.py L1481-1493 segs_to_combined_mask
"""
import logging
import types
from collections import namedtuple

import cv2
import numpy as np
import torch


# ---------------------------------------------------------------- upstream Impact Pack modules/impact/utils.py
# ComfyUI-Impact-Pack/modules/impact/utils.py L509-520 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def normalize_region(limit, startp, size):
    if startp < 0:
        new_endp = min(limit, size)
        new_startp = 0
    elif startp + size > limit:
        new_startp = max(0, limit - size)
        new_endp = limit
    else:
        new_startp = startp
        new_endp = min(limit, startp+size)

    return int(new_startp), int(new_endp)

# ComfyUI-Impact-Pack/modules/impact/utils.py L523-549 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def make_crop_region(w, h, bbox, crop_factor, crop_min_size=None):
    x1 = bbox[0]
    y1 = bbox[1]
    x2 = bbox[2]
    y2 = bbox[3]

    bbox_w = x2 - x1
    bbox_h = y2 - y1

    crop_w = bbox_w * crop_factor
    crop_h = bbox_h * crop_factor

    if crop_min_size is not None:
        crop_w = max(crop_min_size, crop_w)
        crop_h = max(crop_min_size, crop_h)

    kernel_x = x1 + bbox_w / 2
    kernel_y = y1 + bbox_h / 2

    new_x1 = int(kernel_x - crop_w / 2)
    new_y1 = int(kernel_y - crop_h / 2)

    # make sure position in (w,h)
    new_x1, new_x2 = normalize_region(w, new_x1, crop_w)
    new_y1, new_y2 = normalize_region(h, new_y1, crop_h)

    return [new_x1, new_y1, new_x2, new_y2]

# ComfyUI-Impact-Pack/modules/impact/utils.py L613-620 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def make_2d_mask(mask):
    if len(mask.shape) == 4:
        return mask.squeeze(0).squeeze(0)

    elif len(mask.shape) == 3:
        return mask.squeeze(0)

    return mask

# ComfyUI-Impact-Pack/modules/impact/utils.py L623-630 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def make_3d_mask(mask):
    if len(mask.shape) == 4:
        return mask.squeeze(0)

    elif len(mask.shape) == 2:
        return mask.unsqueeze(0)

    return mask


utils = types.SimpleNamespace(normalize_region=normalize_region, make_crop_region=make_crop_region,
                                make_2d_mask=make_2d_mask, make_3d_mask=make_3d_mask)


# ---------------------------------------------------------------- upstream Impact Pack modules/impact/core.py
# ComfyUI-Impact-Pack/modules/impact/core.py L46-48 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
SEG = namedtuple("SEG",
                 ['cropped_image', 'cropped_mask', 'confidence', 'crop_region', 'bbox', 'label', 'control_net_wrapper'],
                 defaults=[None])

# ComfyUI-Impact-Pack/modules/impact/core.py L1296-1407 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def mask_to_segs(mask, combined, crop_factor, bbox_fill, drop_size=1, label='A', crop_min_size=None, detailer_hook=None, is_contour=True):
    drop_size = max(drop_size, 1)
    if mask is None:
        logging.info("[mask_to_segs] Cannot operate: MASK is empty.")
        return ([],)

    if isinstance(mask, np.ndarray):
        pass  # `mask` is already a NumPy array
    else:
        try:
            mask = mask.numpy()
        except AttributeError:
            logging.info("[mask_to_segs] Cannot operate: MASK is not a NumPy array or Tensor.")
            return ([],)

    if mask is None:
        logging.info("[mask_to_segs] Cannot operate: MASK is empty.")
        return ([],)

    result = []

    if len(mask.shape) == 2:
        mask = np.expand_dims(mask, axis=0)

    for i in range(mask.shape[0]):
        mask_i = mask[i]

        if combined:
            indices = np.nonzero(mask_i)
            if len(indices[0]) > 0 and len(indices[1]) > 0:
                bbox = (
                    np.min(indices[1]),
                    np.min(indices[0]),
                    np.max(indices[1]),
                    np.max(indices[0]),
                )
                crop_region = utils.make_crop_region(
                    mask_i.shape[1], mask_i.shape[0], bbox, crop_factor
                )
                x1, y1, x2, y2 = crop_region

                if detailer_hook is not None:
                    crop_region = detailer_hook.post_crop_region(mask_i.shape[1], mask_i.shape[0], bbox, crop_region)

                if x2 - x1 > 0 and y2 - y1 > 0:
                    cropped_mask = mask_i[y1:y2, x1:x2]

                    if bbox_fill:
                        bx1, by1, bx2, by2 = bbox
                        cropped_mask = cropped_mask.copy()
                        cropped_mask[by1:by2, bx1:bx2] = 1.0

                    if cropped_mask is not None:
                        item = SEG(None, cropped_mask, 1.0, crop_region, bbox, label, None)
                        result.append(item)

        else:
            mask_i_uint8 = (mask_i * 255.0).astype(np.uint8)
            contours, ctree = cv2.findContours(mask_i_uint8, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            for j, contour in enumerate(contours):
                hierarchy = ctree[0][j]
                if hierarchy[3] != -1:
                    continue

                separated_mask = np.zeros_like(mask_i_uint8)
                cv2.drawContours(separated_mask, [contour], 0, 255, -1)
                separated_mask = np.array(separated_mask / 255.0).astype(np.float32)

                x, y, w, h = cv2.boundingRect(contour)
                bbox = x, y, x + w, y + h
                crop_region = utils.make_crop_region(
                    mask_i.shape[1], mask_i.shape[0], bbox, crop_factor, crop_min_size
                )

                if detailer_hook is not None:
                    crop_region = detailer_hook.post_crop_region(mask_i.shape[1], mask_i.shape[0], bbox, crop_region)

                if w > drop_size and h > drop_size:
                    if is_contour:
                        mask_src = separated_mask
                    else:
                        mask_src = mask_i * separated_mask

                    cropped_mask = np.array(
                        mask_src[
                            crop_region[1]: crop_region[3],
                            crop_region[0]: crop_region[2],
                        ]
                    )

                    if bbox_fill:
                        cx1, cy1, _, _ = crop_region
                        bx1 = x - cx1
                        bx2 = x+w - cx1
                        by1 = y - cy1
                        by2 = y+h - cy1
                        cropped_mask[by1:by2, bx1:bx2] = 1.0

                    if cropped_mask is not None:
                        cropped_mask = torch.clip(torch.from_numpy(cropped_mask), 0, 1.0)
                        item = SEG(None, cropped_mask.numpy(), 1.0, crop_region, bbox, label, None)
                        result.append(item)

    if not result:
        logging.info("[mask_to_segs] Empty mask.")

    logging.info(f"# of Detected SEGS: {len(result)}")
    # for r in result:
    #     print(f"\tbbox={r.bbox}, crop={r.crop_region}, label={r.label}")

    # shape: (b,h,w) -> (h,w)
    return (mask.shape[1], mask.shape[2]), result

# ComfyUI-Impact-Pack/modules/impact/core.py L1481-1493 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def segs_to_combined_mask(segs):
    shape = segs[0]
    h = shape[0]
    w = shape[1]

    mask = np.zeros((h, w), dtype=np.uint8)

    for seg in segs[1]:
        cropped_mask = seg.cropped_mask
        crop_region = seg.crop_region
        mask[crop_region[1]:crop_region[3], crop_region[0]:crop_region[2]] |= (cropped_mask * 255).astype(np.uint8)

    return torch.from_numpy(mask.astype(np.float32) / 255.0)


# ---------------------------------------------------------------- V2: Impact v2's SEGS layout
def _plain(value):
    """A numpy scalar as the Python int or float with the same value."""
    return value.item() if isinstance(value, np.generic) else value


def to_upstream_segs(segs):
    """Impact v2's SEGS in upstream's value types: cropped masks as 2-D float32 numpy arrays, and bboxes as float32
    arrays where v2 carries floats (Ultralytics detections, which upstream holds as float32) or as given otherwise."""
    shape, items = segs
    converted = []
    for item in items:
        mask = item.cropped_mask
        if isinstance(mask, torch.Tensor):
            mask = mask.detach().cpu().numpy()
        mask = np.asarray(mask, dtype=np.float32)
        if mask.ndim == 3 and mask.shape[0] == 1:
            mask = mask[0]
        bbox = item.bbox
        if len(bbox) and all(isinstance(value, float) for value in bbox):
            bbox = np.asarray(bbox, dtype=np.float32)
        converted.append(SEG(item.cropped_image, mask, item.confidence, item.crop_region, bbox, item.label,
                             item.control_net_wrapper))
    return shape, converted


def to_v2_segs(segs, seg_type):
    """Upstream SEG values in Impact v2's layout; every value is upstream's, only its container changes."""
    shape, items = segs
    converted = []
    for item in items:
        mask = torch.from_numpy(np.ascontiguousarray(item.cropped_mask, dtype=np.float32))
        if mask.ndim == 2:
            mask = mask.unsqueeze(0)
        bbox = item.bbox
        bbox = tuple(bbox.tolist()) if isinstance(bbox, np.ndarray) else tuple(_plain(value) for value in bbox)
        confidence = item.confidence
        if isinstance(confidence, (np.ndarray, np.generic)):
            confidence = float(np.asarray(confidence, dtype=np.float32).reshape(-1)[0])
        converted.append(seg_type(item.cropped_image, mask, confidence, [int(_plain(v)) for v in item.crop_region], bbox,
                                  item.label, item.control_net_wrapper))
    return (int(shape[0]), int(shape[1])), converted


def mask_to_segs_node(mask, combined, crop_factor, bbox_fill, drop_size, contour_fill, seg_type):
    # Impact Pack segs_nodes.py, MaskToSEGS.doit:
    mask = utils.make_2d_mask(mask)
    result = mask_to_segs(mask, combined, crop_factor, bbox_fill, drop_size, is_contour=contour_fill)
    return to_v2_segs(result, seg_type)


def segs_to_combined_mask_node(segs):
    # Impact Pack segs_nodes.py, SegsToCombinedMask.doit:
    mask = segs_to_combined_mask(to_upstream_segs(segs))
    mask = utils.make_3d_mask(mask)
    return mask
