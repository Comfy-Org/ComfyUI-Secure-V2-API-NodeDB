"""Ultralytics detectors for Impact Pack under Secure Nodes V2 (fidelity repair r1).

Detection, SEG building, dilation, cropping and label filtering are upstream code, copied verbatim below as
AST source segments of the pristine files. The ultralytics package runs in this guest from the pack's
dependency profile. The only V2 part is load_detector at the end: the weights arrive solely through the
engine (assets.load_state_dict with metadata), and the model is rebuilt from the checkpoint's own
architecture and set up the way ultralytics' load_checkpoint and Model._load set up a loaded checkpoint.
Copied:
#   ComfyUI-Impact-Subpack/modules/utils.py L29-40 normalize_region
#   ComfyUI-Impact-Subpack/modules/utils.py L43-48 _tensor_check_image
#   ComfyUI-Impact-Subpack/modules/utils.py L51-53 tensor2pil
#   ComfyUI-Impact-Subpack/modules/utils.py L56-74 dilate_masks
#   ComfyUI-Impact-Subpack/modules/utils.py L77-94 combine_masks
#   ComfyUI-Impact-Subpack/modules/utils.py L97-123 make_crop_region
#   ComfyUI-Impact-Subpack/modules/utils.py L126-134 crop_ndarray2
#   ComfyUI-Impact-Subpack/modules/utils.py L137-145 crop_ndarray4
#   ComfyUI-Impact-Subpack/modules/utils.py L148-148 crop_tensor4
#   ComfyUI-Impact-Subpack/modules/utils.py L151-152 crop_image
#   ComfyUI-Impact-Subpack/modules/subcore.py L19-21 SEG
#   ComfyUI-Impact-Subpack/modules/subcore.py L125-134 create_segmasks
#   ComfyUI-Impact-Subpack/modules/subcore.py L320-356 inference_bbox
#   ComfyUI-Impact-Subpack/modules/subcore.py L359-409 inference_segm
#   ComfyUI-Impact-Subpack/modules/subcore.py L412-468 UltraBBoxDetector
#   ComfyUI-Impact-Subpack/modules/subcore.py L471-527 UltraSegmDetector
#   ComfyUI-Impact-Pack/modules/impact/segs_nodes.py L430-472 SEGSLabelFilter
"""
import json
import os
import tempfile
import types
from collections import namedtuple

import cv2
import numpy as np
import torch
from PIL import Image


# ---------------------------------------------------------------- upstream Impact Subpack modules/utils.py
# ComfyUI-Impact-Subpack/modules/utils.py L29-40 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
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

# ComfyUI-Impact-Subpack/modules/utils.py L43-48 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
def _tensor_check_image(image):
    if image.ndim != 4:
        raise ValueError(f"Expected NHWC tensor, but found {image.ndim} dimensions")
    if image.shape[-1] not in (1, 3, 4):
        raise ValueError(f"Expected 1, 3 or 4 channels for image, but found {image.shape[-1]} channels")
    return

# ComfyUI-Impact-Subpack/modules/utils.py L51-53 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
def tensor2pil(image):
    _tensor_check_image(image)
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(0), 0, 255).astype(np.uint8))

# ComfyUI-Impact-Subpack/modules/utils.py L56-74 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
def dilate_masks(segmasks, dilation_factor, iter=1):
    if dilation_factor == 0:
        return segmasks

    dilated_masks = []
    kernel = np.ones((abs(dilation_factor), abs(dilation_factor)), np.uint8)

    for i in range(len(segmasks)):
        cv2_mask = segmasks[i][1]

        if dilation_factor > 0:
            dilated_mask = cv2.dilate(cv2_mask, kernel, iter)
        else:
            dilated_mask = cv2.erode(cv2_mask, kernel, iter)

        item = (segmasks[i][0], dilated_mask, segmasks[i][2])
        dilated_masks.append(item)

    return dilated_masks

# ComfyUI-Impact-Subpack/modules/utils.py L77-94 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
def combine_masks(masks):
    if len(masks) == 0:
        return None
    else:
        initial_cv2_mask = np.array(masks[0][1])
        combined_cv2_mask = initial_cv2_mask

        for i in range(1, len(masks)):
            cv2_mask = np.array(masks[i][1])

            if combined_cv2_mask.shape == cv2_mask.shape:
                combined_cv2_mask = cv2.bitwise_or(combined_cv2_mask, cv2_mask)
            else:
                # do nothing - incompatible mask
                pass

        mask = torch.from_numpy(combined_cv2_mask)
        return mask

# ComfyUI-Impact-Subpack/modules/utils.py L97-123 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
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

# ComfyUI-Impact-Subpack/modules/utils.py L126-134 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
def crop_ndarray2(npimg, crop_region):
    x1 = crop_region[0]
    y1 = crop_region[1]
    x2 = crop_region[2]
    y2 = crop_region[3]

    cropped = npimg[y1:y2, x1:x2]

    return cropped

# ComfyUI-Impact-Subpack/modules/utils.py L137-145 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
def crop_ndarray4(npimg, crop_region):
    x1 = crop_region[0]
    y1 = crop_region[1]
    x2 = crop_region[2]
    y2 = crop_region[3]

    cropped = npimg[:, y1:y2, x1:x2, :]

    return cropped

# ComfyUI-Impact-Subpack/modules/utils.py L148-148 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
crop_tensor4 = crop_ndarray4

# ComfyUI-Impact-Subpack/modules/utils.py L151-152 (pristine sha256 24ce981e1ee6d42d85c96764615f32cdbdc488f263cdc1e71f868728aea9ab01)
def crop_image(image, crop_region):
    return crop_tensor4(image, crop_region)


utils = types.SimpleNamespace(tensor2pil=tensor2pil, dilate_masks=dilate_masks, combine_masks=combine_masks,
                                make_crop_region=make_crop_region, crop_image=crop_image,
                                crop_ndarray2=crop_ndarray2)


# ---------------------------------------------------------------- upstream Impact Subpack modules/subcore.py
# ComfyUI-Impact-Subpack/modules/subcore.py L19-21 (pristine sha256 a2dd6366aed5bb48c8f1d693da6939bdb56dc49a93190c4fc0f2c2913a591536)
SEG = namedtuple("SEG",
                 ['cropped_image', 'cropped_mask', 'confidence', 'crop_region', 'bbox', 'label', 'control_net_wrapper'],
                 defaults=[None])

# ComfyUI-Impact-Subpack/modules/subcore.py L125-134 (pristine sha256 a2dd6366aed5bb48c8f1d693da6939bdb56dc49a93190c4fc0f2c2913a591536)
def create_segmasks(results):
    bboxs = results[1]
    segms = results[2]
    confidence = results[3]

    results = []
    for i in range(len(segms)):
        item = (bboxs[i], segms[i].astype(np.float32), confidence[i])
        results.append(item)
    return results

# ComfyUI-Impact-Subpack/modules/subcore.py L320-356 (pristine sha256 a2dd6366aed5bb48c8f1d693da6939bdb56dc49a93190c4fc0f2c2913a591536)
def inference_bbox(
    model,
    image: Image.Image,
    confidence: float = 0.3,
    device: str = "",
):
    pred = model(image, conf=confidence, device=device)

    bboxes = pred[0].boxes.xyxy.cpu().numpy()
    cv2_image = np.array(image)
    if len(cv2_image.shape) == 3:
        cv2_image = cv2_image[:, :, ::-1].copy()  # Convert RGB to BGR for cv2 processing
    else:
        # Handle the grayscale image here
        # For example, you might want to convert it to a 3-channel grayscale image for consistency:
        cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_GRAY2BGR)
    cv2_gray = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)

    segms = []
    for x0, y0, x1, y1 in bboxes:
        cv2_mask = np.zeros(cv2_gray.shape, np.uint8)
        cv2.rectangle(cv2_mask, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
        cv2_mask_bool = cv2_mask.astype(bool)
        segms.append(cv2_mask_bool)

    n, m = bboxes.shape
    if n == 0:
        return [[], [], [], []]

    results = [[], [], [], []]
    for i in range(len(bboxes)):
        results[0].append(pred[0].names[int(pred[0].boxes[i].cls.item())])
        results[1].append(bboxes[i])
        results[2].append(segms[i])
        results[3].append(pred[0].boxes[i].conf.cpu().numpy())

    return results

# ComfyUI-Impact-Subpack/modules/subcore.py L359-409 (pristine sha256 a2dd6366aed5bb48c8f1d693da6939bdb56dc49a93190c4fc0f2c2913a591536)
def inference_segm(
    model,
    image: Image.Image,
    confidence: float = 0.3,
    device: str = "",
):
    pred = model(image, conf=confidence, device=device)

    bboxes = pred[0].boxes.xyxy.cpu().numpy()
    n, m = bboxes.shape
    if n == 0:
        return [[], [], [], []]

    # NOTE: masks.data will be None when n == 0
    segms = pred[0].masks.data.cpu().numpy()

    h_segms = segms.shape[1]
    w_segms = segms.shape[2]
    h_orig = image.size[1]
    w_orig = image.size[0]
    ratio_segms = h_segms / w_segms
    ratio_orig = h_orig / w_orig

    if ratio_segms == ratio_orig:
        h_gap = 0
        w_gap = 0
    elif ratio_segms > ratio_orig:
        h_gap = int((ratio_segms - ratio_orig) * h_segms)
        w_gap = 0
    else:
        h_gap = 0
        ratio_segms = w_segms / h_segms
        ratio_orig = w_orig / h_orig
        w_gap = int((ratio_segms - ratio_orig) * w_segms)

    results = [[], [], [], []]
    for i in range(len(bboxes)):
        results[0].append(pred[0].names[int(pred[0].boxes[i].cls.item())])
        results[1].append(bboxes[i])

        mask = torch.from_numpy(segms[i])
        mask = mask[h_gap:mask.shape[0] - h_gap, w_gap:mask.shape[1] - w_gap]

        scaled_mask = torch.nn.functional.interpolate(mask.unsqueeze(0).unsqueeze(0), size=(image.size[1], image.size[0]),
                                                      mode='bilinear', align_corners=False)
        scaled_mask = scaled_mask.squeeze().squeeze()

        results[2].append(scaled_mask.numpy())
        results[3].append(pred[0].boxes[i].conf.cpu().numpy())

    return results

# ComfyUI-Impact-Subpack/modules/subcore.py L412-468 (pristine sha256 a2dd6366aed5bb48c8f1d693da6939bdb56dc49a93190c4fc0f2c2913a591536)
class UltraBBoxDetector:
    bbox_model = None

    def __init__(self, bbox_model):
        self.bbox_model = bbox_model

    def detect(self, image, threshold, dilation, crop_factor, drop_size=1, detailer_hook=None):
        drop_size = max(drop_size, 1)
        detected_results = inference_bbox(self.bbox_model, utils.tensor2pil(image), threshold)
        segmasks = create_segmasks(detected_results)

        if dilation > 0:
            segmasks = utils.dilate_masks(segmasks, dilation)

        items = []
        h = image.shape[1]
        w = image.shape[2]

        for x, label in zip(segmasks, detected_results[0]):
            item_bbox = x[0]
            item_mask = x[1]

            y1, x1, y2, x2 = item_bbox

            if x2 - x1 > drop_size and y2 - y1 > drop_size:  # minimum dimension must be (2,2) to avoid squeeze issue
                crop_region = utils.make_crop_region(w, h, item_bbox, crop_factor)

                if detailer_hook is not None:
                    crop_region = detailer_hook.post_crop_region(w, h, item_bbox, crop_region)

                cropped_image = utils.crop_image(image, crop_region)
                cropped_mask = utils.crop_ndarray2(item_mask, crop_region)
                confidence = x[2]
                # bbox_size = (item_bbox[2]-item_bbox[0],item_bbox[3]-item_bbox[1]) # (w,h)

                item = SEG(cropped_image, cropped_mask, confidence, crop_region, item_bbox, label, None)

                items.append(item)

        shape = image.shape[1], image.shape[2]
        segs = shape, items

        if detailer_hook is not None and hasattr(detailer_hook, "post_detection"):
            segs = detailer_hook.post_detection(segs)

        return segs

    def detect_combined(self, image, threshold, dilation):
        detected_results = inference_bbox(self.bbox_model, utils.tensor2pil(image), threshold)
        segmasks = create_segmasks(detected_results)
        if dilation > 0:
            segmasks = utils.dilate_masks(segmasks, dilation)

        return utils.combine_masks(segmasks)

    def setAux(self, x):
        pass

# ComfyUI-Impact-Subpack/modules/subcore.py L471-527 (pristine sha256 a2dd6366aed5bb48c8f1d693da6939bdb56dc49a93190c4fc0f2c2913a591536)
class UltraSegmDetector:
    bbox_model = None

    def __init__(self, bbox_model):
        self.bbox_model = bbox_model

    def detect(self, image, threshold, dilation, crop_factor, drop_size=1, detailer_hook=None):
        drop_size = max(drop_size, 1)
        detected_results = inference_segm(self.bbox_model, utils.tensor2pil(image), threshold)
        segmasks = create_segmasks(detected_results)

        if dilation > 0:
            segmasks = utils.dilate_masks(segmasks, dilation)

        items = []
        h = image.shape[1]
        w = image.shape[2]

        for x, label in zip(segmasks, detected_results[0]):
            item_bbox = x[0]
            item_mask = x[1]

            y1, x1, y2, x2 = item_bbox

            if x2 - x1 > drop_size and y2 - y1 > drop_size:  # minimum dimension must be (2,2) to avoid squeeze issue
                crop_region = utils.make_crop_region(w, h, item_bbox, crop_factor)

                if detailer_hook is not None:
                    crop_region = detailer_hook.post_crop_region(w, h, item_bbox, crop_region)

                cropped_image = utils.crop_image(image, crop_region)
                cropped_mask = utils.crop_ndarray2(item_mask, crop_region)
                confidence = x[2]
                # bbox_size = (item_bbox[2]-item_bbox[0],item_bbox[3]-item_bbox[1]) # (w,h)

                item = SEG(cropped_image, cropped_mask, confidence, crop_region, item_bbox, label, None)

                items.append(item)

        shape = image.shape[1], image.shape[2]
        segs = shape, items

        if detailer_hook is not None and hasattr(detailer_hook, "post_detection"):
            segs = detailer_hook.post_detection(segs)

        return segs

    def detect_combined(self, image, threshold, dilation):
        detected_results = inference_segm(self.bbox_model, utils.tensor2pil(image), threshold)
        segmasks = create_segmasks(detected_results)
        if dilation > 0:
            segmasks = utils.dilate_masks(segmasks, dilation)

        return utils.combine_masks(segmasks)

    def setAux(self, x):
        pass


# ---------------------------------------------------------------- upstream Impact Pack segs_nodes.py
# ComfyUI-Impact-Pack/modules/impact/segs_nodes.py L430-472 (pristine sha256 51e4b938627fb4f7958c220940747476cafc7f424f87035a886e8a0686e1ac8a)
class SEGSLabelFilter:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
                        "segs": ("SEGS", ),
                        "preset": (['all'] + defs.detection_labels, ),
                        "labels": ("STRING", {"multiline": True, "placeholder": "List the types of segments to be allowed, separated by commas"}),
                     },
                }

    RETURN_TYPES = ("SEGS", "SEGS",)
    RETURN_NAMES = ("filtered_SEGS", "remained_SEGS",)
    FUNCTION = "doit"

    CATEGORY = "ImpactPack/Util"

    @staticmethod
    def filter(segs, labels):
        labels = set([label.strip() for label in labels])

        if 'all' in labels:
            return (segs, (segs[0], []), )
        else:
            res_segs = []
            remained_segs = []

            for x in segs[1]:
                if x.label in labels:
                    res_segs.append(x)
                elif 'eyes' in labels and x.label in ['left_eye', 'right_eye']:
                    res_segs.append(x)
                elif 'eyebrows' in labels and x.label in ['left_eyebrow', 'right_eyebrow']:
                    res_segs.append(x)
                elif 'pupils' in labels and x.label in ['left_pupil', 'right_pupil']:
                    res_segs.append(x)
                else:
                    remained_segs.append(x)

        return ((segs[0], res_segs), (segs[0], remained_segs), )

    def doit(self, segs, preset, labels):
        labels = labels.split(',')
        return SEGSLabelFilter.filter(segs, labels)


# ---------------------------------------------------------------- V2: the detector weight, read through the engine
os.environ.setdefault("YOLO_AUTOINSTALL", "False")  # never pip-install from the guest
os.environ.setdefault("YOLO_OFFLINE", "True")  # the guest has no network
os.environ.setdefault("YOLO_CONFIG_DIR", os.path.join(tempfile.gettempdir(), "Ultralytics"))

# Impact Subpack's provider (v2) passes the selected weight as a descriptor: catalogue, name and the menu value.
KINDS = {"impact.ultralytics_bbox": "bbox", "impact.ultralytics_segm": "segm"}
FOLDERS = frozenset({"ultralytics", "ultralytics_bbox", "ultralytics_segm"})
# Checkpoint model classes this loader rebuilds, each with an Ultralytics-packaged yaml for the throwaway
# Model object whose model is then replaced (as Model._load replaces it).
_TOP_CLASSES = {
    "ultralytics.nn.tasks.DetectionModel": ("DetectionModel", "yolov8n.yaml"),
    "ultralytics.nn.tasks.SegmentationModel": ("SegmentationModel", "yolov8n-seg.yaml"),
}
_MODELS = {}  # (catalogue, name) -> YOLO, as upstream reuses the provider's loaded model


class DetectorWeightError(ValueError):
    """The selected detector weight is not available as converted safetensors with Ultralytics metadata."""


def is_descriptor(value, kind):
    return (isinstance(value, dict) and KINDS.get(value.get("secure_kind")) == kind
            and value.get("folder") in FOLDERS and isinstance(value.get("name"), str) and bool(value.get("name")))


def label_filter(segs, labels):
    # Impact Pack modules/impact/detectors.py, BboxDetectorForEach.doit / SegmDetectorForEach.doit:
    if labels is not None and labels != '':
        labels = labels.split(',')
        if len(labels) > 0:
            segs, _ = SEGSLabelFilter.filter(segs, labels)
    return segs


def _build(state, metadata, name):
    from ultralytics import YOLO
    from ultralytics.cfg import DEFAULT_CFG_DICT
    from ultralytics.engine.model import Model
    from ultralytics.nn import tasks

    try:
        class_name, stand_in = _TOP_CLASSES[metadata["top_class"]]
        cfg = json.loads(metadata["yaml"])
        names = {int(key): value for key, value in json.loads(metadata["names"]).items()}
        train_args = json.loads(metadata.get("train_args") or "{}")
    except (KeyError, TypeError, ValueError) as error:
        raise DetectorWeightError(
            f"[Impact Pack] '{name}' has no usable Ultralytics metadata (top_class, yaml, names): "
            f"{type(error).__name__}: {error}") from error
    # Building modules draws initial weights from torch's global generator; loading a checkpoint does not.
    with torch.random.fork_rng(devices=[]):
        model = getattr(tasks, class_name)(cfg, verbose=False)
        yolo = YOLO(stand_in)
    model.load_state_dict(state, strict=True)
    # ultralytics.nn.tasks.load_checkpoint, after it has the checkpoint's model (fuse=False, inplace=True):
    model = model.float()
    model.args = {**DEFAULT_CFG_DICT, **train_args}
    model.pt_path = str(name)
    model.task = getattr(model, "task", tasks.guess_model_task(model))
    if not hasattr(model, "stride"):
        model.stride = torch.tensor([32.0])
    model.names = names  # the checkpoint model's own class names
    model = model.eval()
    for m in model.modules():
        if hasattr(m, "inplace"):
            m.inplace = True
        elif isinstance(m, torch.nn.Upsample) and not hasattr(m, "recompute_scale_factor"):
            m.recompute_scale_factor = None
    # ultralytics.engine.model.Model._load, after load_checkpoint:
    yolo.model, yolo.ckpt, yolo.cfg, yolo.predictor = model, {}, None, None
    yolo.task = model.task
    yolo.overrides = model.args = Model._reset_ckpt_args(model.args)
    yolo.ckpt_path = model.pt_path
    yolo.overrides["model"] = str(name)
    yolo.overrides["task"] = yolo.task
    yolo.model_name = str(name)
    return yolo


async def load_detector(ctx, descriptor):
    """The YOLO model for a provider descriptor. Only the engine reads the file: a converted safetensors state
    dict with its Ultralytics metadata. Nothing here parses a pickle."""
    key = (descriptor["folder"], descriptor["name"])
    if key not in _MODELS:
        menu_value = str(descriptor.get("model_name") or descriptor["name"])
        try:
            ref = await ctx.assets.resolve(*key)
            state, metadata = await ctx.assets.load_state_dict(ref, return_metadata=True)
        except PermissionError:
            raise
        except Exception as error:
            raise DetectorWeightError(
                f"[Impact Pack] cannot load '{menu_value}' through the engine ({type(error).__name__}: {error}). "
                "Secure Nodes read Ultralytics detectors only as converted safetensors with their metadata.") from error
        if not isinstance(metadata, dict):
            raise DetectorWeightError(
                f"[Impact Pack] '{menu_value}' came back without safetensors metadata; Secure Nodes need the "
                "converted file's Ultralytics metadata (top_class, yaml, names) to rebuild the model.")
        _MODELS[key] = _build(state, metadata, menu_value)
    return _MODELS[key]


def detect_segs(yolo, kind, image, threshold, dilation, crop_factor, drop_size):
    detector = UltraBBoxDetector(yolo) if kind == "bbox" else UltraSegmDetector(yolo)
    return detector.detect(image, threshold, dilation, crop_factor, drop_size, None)


def detect_combined(yolo, kind, image, threshold, dilation):
    detector = UltraBBoxDetector(yolo) if kind == "bbox" else UltraSegmDetector(yolo)
    mask = detector.detect_combined(image, threshold, dilation)
    # Impact Pack modules/impact/detectors.py, BboxDetectorCombined.doit / SegmDetectorCombined.doit:
    if mask is None:
        mask = torch.zeros((image.shape[1], image.shape[2]), dtype=torch.float32, device="cpu")
    return mask.unsqueeze(0)


def to_v2_segs(segs, seg_type):
    """Upstream SEG values in the layout Impact v2 passes between nodes: masks as (1, h, w) float32 tensors, the
    confidence as a float and the bbox as a tuple of floats (numpy values cannot cross the guest wire). Every
    value is the upstream value; only its container changes."""
    shape, items = segs
    converted = []
    for item in items:
        mask = torch.from_numpy(np.ascontiguousarray(item.cropped_mask, dtype=np.float32)).unsqueeze(0)
        confidence = float(np.asarray(item.confidence, dtype=np.float32).reshape(-1)[0])
        converted.append(seg_type(
            item.cropped_image.clone() if isinstance(item.cropped_image, torch.Tensor) else item.cropped_image,
            mask, confidence, [int(v) for v in item.crop_region], tuple(float(v) for v in item.bbox), str(item.label),
            item.control_net_wrapper))
    return (int(shape[0]), int(shape[1])), converted
