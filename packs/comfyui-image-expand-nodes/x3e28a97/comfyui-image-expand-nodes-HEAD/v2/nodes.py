import math
import torch
from comfy_api.latest import io
from .algorithms import MergerAlgorithm, NoiserAlgorithm

ExpandOption = io.Custom("EXPAND_OPTION")
MAX_ELEMENTS = 16_777_216
MAX_INPUT_ELEMENTS = 33_554_432
MAX_WORK_ELEMENTS = 67_108_864


def _bounded_inputs(*values):
    total = 0
    for value in values:
        if not isinstance(value, torch.Tensor):
            continue  # Native malformed-call errors belong to the algorithm.
        if value.ndim not in (2, 3, 4):
            continue
        shape = tuple(value.shape)
        batch = shape[0] if value.ndim >= 3 else 1
        spatial = shape[-3:-1] if value.ndim == 4 else shape[-2:]
        if not 1 <= batch <= 64 or any(not 1 <= axis <= 4096 for axis in spatial):
            raise ValueError("input tensor dimensions exceed the resource bounds")
        if value.ndim == 4 and not 1 <= shape[-1] <= 4:
            raise ValueError("image channels exceed the resource bounds")
        count = value.numel()
        if count > MAX_ELEMENTS:
            raise ValueError("input tensor exceeds the element budget")
        total += count
    if total > MAX_INPUT_ELEMENTS:
        raise ValueError("inputs exceed the aggregate element budget")
    return total


def _noiser_budget(image, options, percentage, mask):
    total = _bounded_inputs(image, mask)
    # Preserve key/rank/ceil errors; inspect only shapes and scalar values before
    # interpolation, cloning, rand, or mask allocation in the original algorithm.
    direction = options["direction"]
    options["mode"]
    b, h, w, c = image.shape
    amount = math.ceil((h if direction in ("top", "bottom") else w) * percentage)
    noise = b * abs(amount) * (w if direction in ("top", "bottom") else h) * c
    if abs(amount) > 8192 or noise > MAX_ELEMENTS:
        raise ValueError("projected noise exceeds the element budget")
    # Includes input, output, mask interpolation/broadcast materialization, and
    # noise allocation. Do not allocate a huge resized mask before enforcing it.
    work = total + image.numel() + max(image.numel(), noise) + 3 * b * h * w
    if mask is not None and isinstance(mask, torch.Tensor) and mask.ndim == 3:
        work += mask.shape[0] * h * w
    if work > MAX_WORK_ELEMENTS:
        raise ValueError("projected noiser workspace exceeds the element budget")


def _merger_budget(image1, image2, mask, options):
    total = _bounded_inputs(image1, image2, mask)
    direction = options["direction"]
    mode = options["mode"]
    # Let malformed ranks/types reach their original errors without allocating.
    if not all(isinstance(v, torch.Tensor) for v in (image1, image2, mask)):
        return
    if image1.ndim != 4 or image2.ndim != 4 or mask.ndim not in (2, 3):
        # A rank-4 mask can create a rank-5 broadcast workspace. Reject that
        # out-of-contract case before arithmetic rather than undercounting it.
        if mask.ndim not in (2, 3):
            raise ValueError("mask rank exceeds the supported resource bounds")
        return
    b1, h1, w1, c1 = image1.shape
    b2, h2, w2, c2 = image2.shape
    bm, hm, wm = (1, *mask.shape) if mask.ndim == 2 else mask.shape
    b, c = max(b1, b2, bm), max(c1, c2)
    if mode == "outside":
        h = h1 + h2 if direction in ("top", "bottom") else max(h1, h2)
        w = w1 + w2 if direction not in ("top", "bottom") else max(w1, w2)
    else:
        h, w = max(h1, h2, hm), max(w1, w2, wm)
    projected = b * h * w * c
    if projected > MAX_ELEMENTS:
        raise ValueError("projected merged image exceeds the element budget")
    # RGBA promotion, device copies, mask arithmetic, and composite temporaries.
    if total + 6 * projected > MAX_WORK_ELEMENTS:
        raise ValueError("projected merger workspace exceeds the element budget")


class ImageExpandNoiser(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ImageExpandNoiser",
            display_name="Image Expand Noiser",
            category="Image/Processing",
            inputs=[
                io.Image.Input("image"),
                ExpandOption.Input("expand_options"),
                io.Float.Input("percentage", default=0.2, min=0.1, max=0.5, step=0.01),
                io.Mask.Input("mask", optional=True),
            ],
            outputs=[io.Image.Output(), io.Mask.Output()],
        )

    @classmethod
    def execute(cls, image, expand_options, percentage, mask=None):
        _noiser_budget(image, expand_options, percentage, mask)
        return io.NodeOutput(
            *NoiserAlgorithm().expand_image(image, expand_options, percentage, mask)
        )


class ImageExpandMerger(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ImageExpandMerger",
            display_name="Image Expand Merger",
            category="Image/Processing",
            inputs=[
                io.Image.Input("image1"),
                io.Image.Input("image2"),
                io.Mask.Input("mask"),
                ExpandOption.Input("expand_options"),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(cls, image1, image2, mask, expand_options):
        _merger_budget(image1, image2, mask, expand_options)
        return io.NodeOutput(
            *MergerAlgorithm().merge_images(image1, image2, mask, expand_options)
        )


class ImageExpandOption(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ImageExpandOption",
            display_name="Image Expand Option",
            category="Image/Processing",
            inputs=[
                io.Combo.Input("direction", options=["top", "bottom", "left", "right"]),
                io.Combo.Input("mode", options=["outside", "inside"]),
            ],
            outputs=[ExpandOption.Output(display_name="expand_options")],
        )

    @classmethod
    def execute(cls, direction, mode):
        return io.NodeOutput({"direction": direction, "mode": mode})
