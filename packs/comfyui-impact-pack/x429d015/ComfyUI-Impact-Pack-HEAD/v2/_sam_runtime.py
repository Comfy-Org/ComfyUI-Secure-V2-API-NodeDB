"""SAM (Segment Anything) for Impact Pack under Secure Nodes V2 (fidelity repair r2).

The SAM model is built in this guest with segment_anything (the pack's dependency profile) from a state dict that
only the engine reads (assets.load_state_dict). SAMLoader's rules, the SAMWrapper predictor, detection hints,
mask selection, combining, dilation and the SEGS-and-mask operations are upstream code, copied verbatim below as
AST source segments of the pristine files. Boundary stand-ins (not upstream code): `comfy.model_management`
answers this guest's own torch device and memory; `config` answers upstream's default configuration
(disable_gpu_opencv = True, impact/config.py); SAM2Wrapper is a name only (SAM2 is refused by name).
Copied:
#   ComfyUI-Impact-Pack/modules/impact/utils.py L296-298 center_of_bbox
#   ComfyUI-Impact-Pack/modules/impact/utils.py L321-338 combine_masks2
#   ComfyUI-Impact-Pack/modules/impact/utils.py L364-365 use_gpu_opencv
#   ComfyUI-Impact-Pack/modules/impact/utils.py L368-388 dilate_mask
#   ComfyUI-Impact-Pack/modules/impact/utils.py L613-620 make_2d_mask
#   ComfyUI-Impact-Pack/modules/impact/utils.py L623-630 make_3d_mask
#   ComfyUI-Impact-Pack/modules/impact/utils.py L643-646 is_same_device
#   ComfyUI-Impact-Pack/modules/impact/core.py L46-48 SEG
#   ComfyUI-Impact-Pack/modules/impact/core.py L211-230 gen_detection_hints_from_mask_area
#   ComfyUI-Impact-Pack/modules/impact/core.py L233-247 gen_negative_hints
#   ComfyUI-Impact-Pack/modules/impact/core.py L587-614 sam_predict
#   ComfyUI-Impact-Pack/modules/impact/core.py L617-636 SAMWrapper
#   ComfyUI-Impact-Pack/modules/impact/core.py L777-902 make_sam_mask
#   ComfyUI-Impact-Pack/modules/impact/core.py L905-963 generate_detection_hints
#   ComfyUI-Impact-Pack/modules/impact/core.py L966-979 convert_and_stack_masks
#   ComfyUI-Impact-Pack/modules/impact/core.py L982-997 merge_and_stack_masks
#   ComfyUI-Impact-Pack/modules/impact/core.py L1052-1129 make_sam_mask_segmented
#   ComfyUI-Impact-Pack/modules/impact/core.py L1133-1156 segs_bitwise_and_mask
#   ComfyUI-Impact-Pack/modules/impact/core.py L1159-1182 segs_bitwise_subtract_mask
#   ComfyUI-Impact-Pack/modules/impact/core.py L2352-2368 SafeToGPU
#   ComfyUI-Impact-Pack/modules/impact/core.py L2371-2373 SafeToGPU_stub
#   ComfyUI-Impact-Pack/modules/impact/impact_pack.py L97-106 sam2_config_table
"""
import logging
import types
from collections import namedtuple

import cv2
import numpy as np
import psutil
import torch
from segment_anything import SamPredictor, sam_model_registry


# ---------------------------------------------------------------- boundary stand-ins
def _guest_device():
    return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


def _free_memory(memory_required, device, keep_loaded=()):
    return None  # Comfy's free_memory unloads Comfy's cached models; this guest holds none


def _get_free_memory(dev=None, torch_free_too=False):
    dev = torch.device(dev) if dev is not None else _guest_device()
    if dev.type == "cuda":
        return torch.cuda.mem_get_info(dev)[0]
    return psutil.virtual_memory().available


model_management = types.SimpleNamespace(get_torch_device=_guest_device, free_memory=_free_memory,
                                         get_free_memory=_get_free_memory)
comfy = types.SimpleNamespace(model_management=model_management)
config = types.SimpleNamespace(get_config=lambda: {"disable_gpu_opencv": True})


class SAM2Wrapper:
    """Name only: make_sam_mask checks isinstance against it; SAM2 models are refused by name."""


# ---------------------------------------------------------------- upstream Impact Pack modules/impact/utils.py
# ComfyUI-Impact-Pack/modules/impact/utils.py L296-298 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def center_of_bbox(bbox):
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    return bbox[0] + w/2, bbox[1] + h/2

# ComfyUI-Impact-Pack/modules/impact/utils.py L321-338 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def combine_masks2(masks):
    if len(masks) == 0:
        return None
    else:
        initial_cv2_mask = np.array(masks[0]).astype(np.uint8)
        combined_cv2_mask = initial_cv2_mask

        for i in range(1, len(masks)):
            cv2_mask = np.array(masks[i]).astype(np.uint8)

            if combined_cv2_mask.shape == cv2_mask.shape:
                combined_cv2_mask = cv2.bitwise_or(combined_cv2_mask, cv2_mask)
            else:
                # do nothing - incompatible mask
                pass

        mask = torch.from_numpy(combined_cv2_mask)
        return mask

# ComfyUI-Impact-Pack/modules/impact/utils.py L364-365 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def use_gpu_opencv():
    return not config.get_config()['disable_gpu_opencv']

# ComfyUI-Impact-Pack/modules/impact/utils.py L368-388 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def dilate_mask(mask, dilation_factor, iter=1):
    if dilation_factor == 0:
        return make_2d_mask(mask)

    mask = make_2d_mask(mask)

    kernel = np.ones((abs(dilation_factor), abs(dilation_factor)), np.uint8)

    if use_gpu_opencv():
        mask = cv2.UMat(mask)
        kernel = cv2.UMat(kernel)

    if dilation_factor > 0:
        result = cv2.dilate(mask, kernel, iter)
    else:
        result = cv2.erode(mask, kernel, iter)

    if use_gpu_opencv():
        return result.get()
    else:
        return result

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

# ComfyUI-Impact-Pack/modules/impact/utils.py L643-646 (pristine sha256 dac304171388f0209191c00a90086c16836956a323eba609ab876fd571659873)
def is_same_device(a, b):
    a_device = torch.device(a) if isinstance(a, str) else a
    b_device = torch.device(b) if isinstance(b, str) else b
    return a_device.type == b_device.type and a_device.index == b_device.index


utils = types.SimpleNamespace(center_of_bbox=center_of_bbox, combine_masks2=combine_masks2,
                                dilate_mask=dilate_mask, make_2d_mask=make_2d_mask, make_3d_mask=make_3d_mask,
                                is_same_device=is_same_device)


# ---------------------------------------------------------------- upstream Impact Pack modules/impact/core.py
# ComfyUI-Impact-Pack/modules/impact/core.py L46-48 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
SEG = namedtuple("SEG",
                 ['cropped_image', 'cropped_mask', 'confidence', 'crop_region', 'bbox', 'label', 'control_net_wrapper'],
                 defaults=[None])

# ComfyUI-Impact-Pack/modules/impact/core.py L211-230 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def gen_detection_hints_from_mask_area(x, y, mask, threshold, use_negative):
    mask = utils.make_2d_mask(mask)

    points = []
    plabs = []

    # minimum sampling step >= 3
    y_step = max(3, int(mask.shape[0] / 20))
    x_step = max(3, int(mask.shape[1] / 20))

    for i in range(0, len(mask), y_step):
        for j in range(0, len(mask[i]), x_step):
            if mask[i][j] > threshold:
                points.append((x + j, y + i))
                plabs.append(1)
            elif use_negative and mask[i][j] == 0:
                points.append((x + j, y + i))
                plabs.append(0)

    return points, plabs

# ComfyUI-Impact-Pack/modules/impact/core.py L233-247 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def gen_negative_hints(w, h, x1, y1, x2, y2):
    npoints = []
    nplabs = []

    # minimum sampling step >= 3
    y_step = max(3, int(w / 20))
    x_step = max(3, int(h / 20))

    for i in range(10, h - 10, y_step):
        for j in range(10, w - 10, x_step):
            if not (x1 - 10 <= j and j <= x2 + 10 and y1 - 10 <= i and i <= y2 + 10):
                npoints.append((j, i))
                nplabs.append(0)

    return npoints, nplabs

# ComfyUI-Impact-Pack/modules/impact/core.py L587-614 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def sam_predict(predictor, points, plabs, bbox, threshold):
    point_coords = None if not points else np.array(points)
    point_labels = None if not plabs else np.array(plabs)

    box = np.array([bbox]) if bbox is not None else None

    cur_masks, scores, _ = predictor.predict(point_coords=point_coords, point_labels=point_labels, box=box)

    total_masks = []

    selected = False
    max_score = 0
    max_mask = None
    for idx in range(len(scores)):
        if scores[idx] > max_score:
            max_score = scores[idx]
            max_mask = cur_masks[idx]

        if scores[idx] >= threshold:
            selected = True
            total_masks.append(cur_masks[idx])
        else:
            pass

    if not selected and max_mask is not None:
        total_masks.append(max_mask)

    return total_masks

# ComfyUI-Impact-Pack/modules/impact/core.py L617-636 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
class SAMWrapper:
    def __init__(self, model, is_auto_mode, safe_to_gpu=None):
        self.model = model
        self.safe_to_gpu = safe_to_gpu if safe_to_gpu is not None else SafeToGPU_stub()
        self.is_auto_mode = is_auto_mode

    def prepare_device(self):
        if self.is_auto_mode:
            device = comfy.model_management.get_torch_device()
            self.safe_to_gpu.to_device(self.model, device=device)

    def release_device(self):
        if self.is_auto_mode:
            self.model.to(device="cpu")

    def predict(self, image, points, plabs, bbox, threshold):
        predictor = SamPredictor(self.model)
        predictor.set_image(image, "RGB")

        return sam_predict(predictor, points, plabs, bbox, threshold)

# ComfyUI-Impact-Pack/modules/impact/core.py L777-902 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def make_sam_mask(sam, segs, image, detection_hint, dilation,
                  threshold, bbox_expansion, mask_hint_threshold, mask_hint_use_negative):

    if not hasattr(sam, 'sam_wrapper') and not isinstance(sam, SAM2Wrapper):
        raise Exception("[Impact Pack] Invalid SAMLoader is connected. Make sure 'SAMLoader (Impact)'.\nKnown issue: The ComfyUI-YOLO node overrides the SAMLoader (Impact), making it unusable. You need to uninstall ComfyUI-YOLO.\n\n\n")


    if isinstance(sam, SAM2Wrapper):
        sam_obj = sam
    else:
        sam_obj = sam.sam_wrapper

    sam_obj.prepare_device()

    try:
        image = np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8)

        total_masks = []

        use_small_negative = mask_hint_use_negative == "Small"

        # seg_shape = segs[0]
        segs = segs[1]
        if detection_hint == "mask-points":
            points = []
            plabs = []

            for i in range(len(segs)):
                bbox = segs[i].bbox
                center = utils.center_of_bbox(segs[i].bbox)
                points.append(center)

                # small point is background, big point is foreground
                if use_small_negative and bbox[2] - bbox[0] < 10:
                    plabs.append(0)
                else:
                    plabs.append(1)

            detected_masks = sam_obj.predict(image, points, plabs, None, threshold)
            total_masks += detected_masks

        else:
            for i in range(len(segs)):
                bbox = segs[i].bbox
                center = utils.center_of_bbox(bbox)

                x1 = max(bbox[0] - bbox_expansion, 0)
                y1 = max(bbox[1] - bbox_expansion, 0)
                x2 = min(bbox[2] + bbox_expansion, image.shape[1])
                y2 = min(bbox[3] + bbox_expansion, image.shape[0])

                dilated_bbox = [x1, y1, x2, y2]

                points = []
                plabs = []
                if detection_hint == "center-1":
                    points.append(center)
                    plabs = [1]  # 1 = foreground point, 0 = background point

                elif detection_hint == "horizontal-2":
                    gap = (x2 - x1) / 3
                    points.append((x1 + gap, center[1]))
                    points.append((x1 + gap * 2, center[1]))
                    plabs = [1, 1]

                elif detection_hint == "vertical-2":
                    gap = (y2 - y1) / 3
                    points.append((center[0], y1 + gap))
                    points.append((center[0], y1 + gap * 2))
                    plabs = [1, 1]

                elif detection_hint == "rect-4":
                    x_gap = (x2 - x1) / 3
                    y_gap = (y2 - y1) / 3
                    points.append((x1 + x_gap, center[1]))
                    points.append((x1 + x_gap * 2, center[1]))
                    points.append((center[0], y1 + y_gap))
                    points.append((center[0], y1 + y_gap * 2))
                    plabs = [1, 1, 1, 1]

                elif detection_hint == "diamond-4":
                    x_gap = (x2 - x1) / 3
                    y_gap = (y2 - y1) / 3
                    points.append((x1 + x_gap, y1 + y_gap))
                    points.append((x1 + x_gap * 2, y1 + y_gap))
                    points.append((x1 + x_gap, y1 + y_gap * 2))
                    points.append((x1 + x_gap * 2, y1 + y_gap * 2))
                    plabs = [1, 1, 1, 1]

                elif detection_hint == "mask-point-bbox":
                    center = utils.center_of_bbox(segs[i].bbox)
                    points.append(center)
                    plabs = [1]

                elif detection_hint == "mask-area":
                    points, plabs = gen_detection_hints_from_mask_area(segs[i].crop_region[0], segs[i].crop_region[1],
                                                                       segs[i].cropped_mask,
                                                                       mask_hint_threshold, use_small_negative)

                if mask_hint_use_negative == "Outter":
                    npoints, nplabs = gen_negative_hints(image.shape[0], image.shape[1],
                                                         segs[i].crop_region[0], segs[i].crop_region[1],
                                                         segs[i].crop_region[2], segs[i].crop_region[3])

                    points += npoints
                    plabs += nplabs

                detected_masks = sam_obj.predict(image, points, plabs, dilated_bbox, threshold)
                total_masks += detected_masks

        # merge every collected masks
        mask = utils.combine_masks2(total_masks)

    finally:
        sam_obj.release_device()

    if mask is not None:
        mask = mask.float()
        mask = utils.dilate_mask(mask.cpu().numpy(), dilation)
        mask = torch.from_numpy(mask)
    else:
        size = image.shape[0], image.shape[1]
        mask = torch.zeros(size, dtype=torch.float32, device="cpu")  # empty mask

    mask = utils.make_3d_mask(mask)
    return mask

# ComfyUI-Impact-Pack/modules/impact/core.py L905-963 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def generate_detection_hints(image, seg, center, detection_hint, dilated_bbox, mask_hint_threshold, use_small_negative,
                             mask_hint_use_negative):
    [x1, y1, x2, y2] = dilated_bbox

    points = []
    plabs = []
    if detection_hint == "center-1":
        points.append(center)
        plabs = [1]  # 1 = foreground point, 0 = background point

    elif detection_hint == "horizontal-2":
        gap = (x2 - x1) / 3
        points.append((x1 + gap, center[1]))
        points.append((x1 + gap * 2, center[1]))
        plabs = [1, 1]

    elif detection_hint == "vertical-2":
        gap = (y2 - y1) / 3
        points.append((center[0], y1 + gap))
        points.append((center[0], y1 + gap * 2))
        plabs = [1, 1]

    elif detection_hint == "rect-4":
        x_gap = (x2 - x1) / 3
        y_gap = (y2 - y1) / 3
        points.append((x1 + x_gap, center[1]))
        points.append((x1 + x_gap * 2, center[1]))
        points.append((center[0], y1 + y_gap))
        points.append((center[0], y1 + y_gap * 2))
        plabs = [1, 1, 1, 1]

    elif detection_hint == "diamond-4":
        x_gap = (x2 - x1) / 3
        y_gap = (y2 - y1) / 3
        points.append((x1 + x_gap, y1 + y_gap))
        points.append((x1 + x_gap * 2, y1 + y_gap))
        points.append((x1 + x_gap, y1 + y_gap * 2))
        points.append((x1 + x_gap * 2, y1 + y_gap * 2))
        plabs = [1, 1, 1, 1]

    elif detection_hint == "mask-point-bbox":
        center = utils.center_of_bbox(seg.bbox)
        points.append(center)
        plabs = [1]

    elif detection_hint == "mask-area":
        points, plabs = gen_detection_hints_from_mask_area(seg.crop_region[0], seg.crop_region[1],
                                                           seg.cropped_mask,
                                                           mask_hint_threshold, use_small_negative)

    if mask_hint_use_negative == "Outter":
        npoints, nplabs = gen_negative_hints(image.shape[0], image.shape[1],
                                             seg.crop_region[0], seg.crop_region[1],
                                             seg.crop_region[2], seg.crop_region[3])

        points += npoints
        plabs += nplabs

    return points, plabs

# ComfyUI-Impact-Pack/modules/impact/core.py L966-979 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def convert_and_stack_masks(masks):
    if len(masks) == 0:
        return None

    mask_tensors = []
    for mask in masks:
        mask_array = np.array(mask, dtype=np.uint8)
        mask_tensor = torch.from_numpy(mask_array)
        mask_tensors.append(mask_tensor)

    stacked_masks = torch.stack(mask_tensors, dim=0)
    stacked_masks = stacked_masks.unsqueeze(1)

    return stacked_masks

# ComfyUI-Impact-Pack/modules/impact/core.py L982-997 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def merge_and_stack_masks(stacked_masks, group_size):
    if stacked_masks is None:
        return None

    num_masks = stacked_masks.size(0)
    merged_masks = []

    for i in range(0, num_masks, group_size):
        subset_masks = stacked_masks[i:i + group_size]
        merged_mask = torch.any(subset_masks, dim=0)
        merged_masks.append(merged_mask)

    if len(merged_masks) > 0:
        merged_masks = torch.stack(merged_masks, dim=0)

    return merged_masks

# ComfyUI-Impact-Pack/modules/impact/core.py L1052-1129 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def make_sam_mask_segmented(sam, segs, image, detection_hint, dilation,
                            threshold, bbox_expansion, mask_hint_threshold, mask_hint_use_negative):

    if not hasattr(sam, 'sam_wrapper'):
        raise Exception("[Impact Pack] Invalid SAMLoader is connected. Make sure 'SAMLoader (Impact)'.")

    sam_obj = sam.sam_wrapper
    sam_obj.prepare_device()

    try:
        image = np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8)

        total_masks = []

        use_small_negative = mask_hint_use_negative == "Small"

        # seg_shape = segs[0]
        segs = segs[1]
        if detection_hint == "mask-points":
            points = []
            plabs = []

            for i in range(len(segs)):
                bbox = segs[i].bbox
                center = utils.center_of_bbox(bbox)
                points.append(center)

                # small point is background, big point is foreground
                if use_small_negative and bbox[2] - bbox[0] < 10:
                    plabs.append(0)
                else:
                    plabs.append(1)

            detected_masks = sam_obj.predict(image, points, plabs, None, threshold)
            total_masks += detected_masks

        else:
            for i in range(len(segs)):
                bbox = segs[i].bbox
                center = utils.center_of_bbox(bbox)
                x1 = max(bbox[0] - bbox_expansion, 0)
                y1 = max(bbox[1] - bbox_expansion, 0)
                x2 = min(bbox[2] + bbox_expansion, image.shape[1])
                y2 = min(bbox[3] + bbox_expansion, image.shape[0])

                dilated_bbox = [x1, y1, x2, y2]

                points, plabs = generate_detection_hints(image, segs[i], center, detection_hint, dilated_bbox,
                                                         mask_hint_threshold, use_small_negative,
                                                         mask_hint_use_negative)

                detected_masks = sam_obj.predict(image, points, plabs, dilated_bbox, threshold)

                total_masks += detected_masks

        # merge every collected masks
        mask = utils.combine_masks2(total_masks)

    finally:
        sam_obj.release_device()

    mask_working_device = torch.device("cpu")

    if mask is not None:
        mask = mask.float()
        mask = utils.dilate_mask(mask.cpu().numpy(), dilation)
        mask = torch.from_numpy(mask)
        mask = mask.to(device=mask_working_device)
    else:
        # Extracting batch, height and width
        height, width, _ = image.shape
        mask = torch.zeros(
            (height, width), dtype=torch.float32, device=mask_working_device
        )  # empty mask

    stacked_masks = convert_and_stack_masks(total_masks)

    return (mask, merge_and_stack_masks(stacked_masks, group_size=3))

# ComfyUI-Impact-Pack/modules/impact/core.py L1133-1156 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def segs_bitwise_and_mask(segs, mask):
    mask = utils.make_2d_mask(mask)

    if mask is None:
        logging.warning("[SegsBitwiseAndMask] Cannot operate: MASK is empty.")
        return ([],)

    items = []

    mask = (mask.cpu().numpy() * 255).astype(np.uint8)

    for seg in segs[1]:
        cropped_mask = (seg.cropped_mask * 255).astype(np.uint8)
        crop_region = seg.crop_region

        cropped_mask2 = mask[crop_region[1]:crop_region[3], crop_region[0]:crop_region[2]]

        new_mask = np.bitwise_and(cropped_mask.astype(np.uint8), cropped_mask2)
        new_mask = new_mask.astype(np.float32) / 255.0

        item = SEG(seg.cropped_image, new_mask, seg.confidence, seg.crop_region, seg.bbox, seg.label, None)
        items.append(item)

    return segs[0], items

# ComfyUI-Impact-Pack/modules/impact/core.py L1159-1182 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
def segs_bitwise_subtract_mask(segs, mask):
    mask = utils.make_2d_mask(mask)

    if mask is None:
        logging.warning("[SegsBitwiseSubtractMask] Cannot operate: MASK is empty.")
        return ([],)

    items = []

    mask = (mask.cpu().numpy() * 255).astype(np.uint8)

    for seg in segs[1]:
        cropped_mask = (seg.cropped_mask * 255).astype(np.uint8)
        crop_region = seg.crop_region

        cropped_mask2 = mask[crop_region[1]:crop_region[3], crop_region[0]:crop_region[2]]

        new_mask = cv2.subtract(cropped_mask.astype(np.uint8), cropped_mask2)
        new_mask = new_mask.astype(np.float32) / 255.0

        item = SEG(seg.cropped_image, new_mask, seg.confidence, seg.crop_region, seg.bbox, seg.label, None)
        items.append(item)

    return segs[0], items

# ComfyUI-Impact-Pack/modules/impact/core.py L2352-2368 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
class SafeToGPU:
    def __init__(self, size):
        self.size = size

    def to_device(self, obj, device):
        if utils.is_same_device(device, 'cpu'):
            obj.to(device)
        else:
            if utils.is_same_device(obj.device, 'cpu'):  # cpu to gpu
                model_management.free_memory(self.size * 1.3, device)
                if model_management.get_free_memory(device) > self.size * 1.3:
                    try:
                        obj.to(device)
                    except Exception:
                        logging.warning(f"[Impact Pack] The model is not moved to the '{device}' due to insufficient memory. [1]")
                else:
                    logging.warning(f"[Impact Pack] The model is not moved to the '{device}' due to insufficient memory. [2]")

# ComfyUI-Impact-Pack/modules/impact/core.py L2371-2373 (pristine sha256 7989de178999904cacf440bd6c9fd6d250ff5f8df8a4a2dad7abe33d2dfacdd5)
class SafeToGPU_stub():
    def to_device(self, obj, device):
        pass


# ---------------------------------------------------------------- upstream Impact Pack impact_pack.py
# ComfyUI-Impact-Pack/modules/impact/impact_pack.py L97-106 (pristine sha256 2bd8dd0ab70f3928f7b53cfa318c04a680f3d9d1bb235032960b869290f7df4d)
sam2_config_table = {
    'sam2.1_hiera_base_plus.pt': 'configs/sam2.1/sam2.1_hiera_b+.yaml',
    'sam2.1_hiera_large.pt': 'configs/sam2.1/sam2.1_hiera_l.yaml',
    'sam2.1_hiera_small.pt': 'configs/sam2.1/sam2.1_hiera_s.yaml',
    'sam2.1_hiera_tiny.pt': 'configs/sam2.1/sam2.1_hiera_t.yaml',
    'sam2_hiera_tiny.pt': 'configs/sam2/sam2_hiera_t.yaml',
    'sam2_hiera_small.pt': 'configs/sam2/sam2_hiera_s.yaml',
    'sam2_hiera_base_plus.pt': 'configs/sam2/sam2_hiera_b+.yaml',
    'sam2_hiera_large.pt': 'configs/sam2/sam2_hiera_l.yaml'
}


# ---------------------------------------------------------------- V2: SAMLoader's model, built in this guest
SAM_KIND = "impact.sam"
_SAMS = {}  # (model name, device mode) -> SAM model with .sam_wrapper, as upstream's SAMLoader returns it


class SamWeightError(ValueError):
    """The selected SAM checkpoint cannot be used in Secure Nodes V2."""


def is_descriptor(value):
    return (isinstance(value, dict) and value.get("secure_kind") == SAM_KIND and isinstance(value.get("name"), str)
            and value.get("device_mode") in ("AUTO", "Prefer GPU", "CPU"))


def refusal(model_name):
    """A named refusal for names upstream's SAMLoader treats specially or never lists, else None."""
    if model_name == 'ESAM':
        return ("[Impact Pack] SAMLoader 'ESAM' needs the ComfyUI-YoloWorld-EfficientSAM node pack, which a Secure "
                "Nodes V2 guest does not have")
    if model_name in sam2_config_table:
        return f"[Impact Pack] SAMLoader '{model_name}' is a SAM2 model, and this pack's guest has no sam2 package"
    # impact_pack.py SAMLoader.INPUT_TYPES lists only these names; the host menu lists the whole sams catalogue.
    if 'hq' in model_name or not (model_name.endswith('.pt') or model_name.endswith('.pth')
                                  or model_name.endswith('.safetensors')):
        return f"[Impact Pack] SAMLoader '{model_name}' is not in upstream SAMLoader's model list"
    return None


def model_kind(model_name):
    # impact_pack.py SAMLoader.load_model:
    if 'vit_h' in model_name:
        model_kind = 'vit_h'
    elif 'vit_l' in model_name:
        model_kind = 'vit_l'
    else:
        model_kind = 'vit_b'
    return model_kind


async def load_sam(ctx, model_name, device_mode):
    """Upstream SAMLoader.load_model for segment-anything models. The engine reads the checkpoint (a converted
    safetensors file for a pickle-format name); nothing here parses a pickle."""
    key = (model_name, device_mode)
    if key not in _SAMS:
        problem = refusal(model_name)
        if problem is not None:
            raise SamWeightError(problem)
        try:
            ref = await ctx.assets.resolve("sams", model_name)
            state = await ctx.assets.load_state_dict(ref)
            size = int(await ctx.assets.size(ref))
        except PermissionError:
            raise
        except Exception as error:
            raise SamWeightError(f"[Impact Pack] cannot load SAM model '{model_name}' through the engine "
                                 f"({type(error).__name__}: {error})") from error
        # segment_anything build_sam(checkpoint=...) builds, puts the model in eval mode, then loads the state dict
        # strictly; building draws initial weights from torch's global generator, which a load does not.
        with torch.random.fork_rng(devices=[]):
            sam = sam_model_registry[model_kind(model_name)](checkpoint=None)
        sam.load_state_dict(state)
        # impact_pack.py SAMLoader.load_model, after building:
        safe_to = SafeToGPU(size)
        device = comfy.model_management.get_torch_device() if device_mode == "Prefer GPU" else "CPU"
        if device_mode == "Prefer GPU":
            safe_to.to_device(sam, device)
        is_auto_mode = device_mode == "AUTO"
        sam_obj = SAMWrapper(sam, is_auto_mode=is_auto_mode, safe_to_gpu=safe_to)
        sam.sam_wrapper = sam_obj
        logging.info(f"Loads SAM model: {model_name} (device:{device_mode})")
        _SAMS[key] = sam
    return _SAMS[key]


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
    """Back to Impact v2's layout: masks as (1, h, w) float32 tensors, float32 bboxes as tuples of floats."""
    shape, items = segs
    converted = []
    for item in items:
        mask = torch.from_numpy(np.ascontiguousarray(item.cropped_mask, dtype=np.float32))
        if mask.ndim == 2:
            mask = mask.unsqueeze(0)
        bbox = item.bbox
        if isinstance(bbox, np.ndarray):
            bbox = tuple(float(value) for value in bbox)
        converted.append(seg_type(item.cropped_image, mask, item.confidence, item.crop_region, bbox, item.label,
                                  item.control_net_wrapper))
    return tuple(shape), converted


def mask3(mask):
    """A MASK value as Impact v2 sends it: (B, H, W) float32."""
    mask = torch.as_tensor(mask)
    while mask.ndim > 3 and mask.shape[1] == 1:
        mask = mask.squeeze(1)
    if mask.ndim == 2:
        mask = mask.unsqueeze(0)
    return mask.float()
