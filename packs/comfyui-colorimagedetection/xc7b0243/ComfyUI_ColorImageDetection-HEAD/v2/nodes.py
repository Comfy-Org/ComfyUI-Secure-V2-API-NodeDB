"""Pack-owned RGB/LAB analysis in bounded public value-mode compute."""
import math
import numbers

import cv2
import numpy as np
import torch
from comfy_api.latest import io

MAX_BATCH = 32
MAX_EDGE = 8192
MAX_PIXELS = 4_194_304
MAX_IMAGE_BYTES = 134_217_728
MAX_PARAMETER_ABS = 1_000_000


def _validate_image(image):
    if not isinstance(image, torch.Tensor) or image.ndim != 4 or image.shape[-1] not in (1, 3, 4):
        raise ValueError("image must have shape [batch, height, width, channels] with 1, 3 or 4 channels")
    batch, height, width, _ = image.shape
    if not (1 <= batch <= MAX_BATCH and 1 <= height <= MAX_EDGE and 1 <= width <= MAX_EDGE):
        raise ValueError("image batch/dimensions exceed the bounded analysis limits")
    if batch * height * width > MAX_PIXELS or image.numel() * image.element_size() > MAX_IMAGE_BYTES:
        raise ValueError("image exceeds the bounded pixel/byte limits")
    if image.device.type != "cpu":
        raise ValueError("analysis requires a CPU image, as in the upstream NumPy algorithm")
    if not image.is_floating_point() or not torch.isfinite(image).all():
        raise ValueError("image must contain finite floating-point values")


def _validate_parameter(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a real number")
    if not math.isfinite(value) or abs(value) > MAX_PARAMETER_ABS:
        raise ValueError(f"{name} exceeds the finite scalar bounds")


def _output(is_color, statistic):
    if not np.isfinite(statistic):
        raise ValueError("analysis produced a nonfinite score")
    # Normalize NumPy scalars to wire-safe Python values; keep the declared
    # custom BOOL socket (not BOOLEAN) and exact float32-derived score value.
    return io.NodeOutput(bool(is_color), float(statistic))


class ColorDetection(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="RGBColorDetection", category="Image Analysis",
            inputs=[io.Image.Input("image"), io.Float.Input("threshold", default=0.15),
                    io.Float.Input("det_pixel_percent", default=0.1)],
            outputs=[io.Custom("BOOL").Output(display_name="is_color"),
                     io.Float.Output(display_name="mean_deviation")])

    @classmethod
    @torch.no_grad()
    def execute(cls, image, threshold, det_pixel_percent):
        _validate_image(image)
        _validate_parameter(threshold, "threshold")
        _validate_parameter(det_pixel_percent, "det_pixel_percent")
        for index in range(image.shape[0]):
            img = image[index].numpy().astype(np.float32)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            deviations = np.abs(img_rgb - np.mean(img_rgb, axis=2, keepdims=True)).flatten()
            num_pixels_to_consider = int(len(deviations) * (det_pixel_percent / 100.0))
            # Preserve the legacy [-0:] full-vector case, and return only the
            # final batch member's score rather than averaging the batch.
            mean_deviation = np.mean(np.sort(deviations)[-num_pixels_to_consider:])
            is_color = mean_deviation > threshold
        return _output(is_color, mean_deviation)


class LABColorDetection(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="LABColorDetection", display_name="LAB Color Detection",
            category="Image Analysis",
            inputs=[io.Image.Input("image"), io.Float.Input("threshold", default=2.5)],
            outputs=[io.Custom("BOOL").Output(display_name="is_color"),
                     io.Float.Output(display_name="color_difference")])

    @classmethod
    @torch.no_grad()
    def execute(cls, image, threshold):
        _validate_image(image)
        _validate_parameter(threshold, "threshold")
        for index in range(image.shape[0]):
            img = image[index].numpy().astype(np.float32)
            lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            _, a_channel, b_channel = cv2.split(lab_img)
            color_difference = np.mean(np.abs(a_channel - b_channel))
            is_color = color_difference > threshold
        return _output(is_color, color_difference)


NODE_CLASS_MAPPINGS = {
    "RGBColorDetection": ColorDetection,
    "LABColorDetection": LABColorDetection,
}
# Preserve the unused/mismatched upstream RGB mapping key verbatim. The
# registered RGBColorDetection node intentionally gets no invented name.
NODE_DISPLAY_NAME_MAPPINGS = {
    "ColorDetection": "RGB Color Detection",
    "LABColorDetection": "LAB Color Detection",
}
