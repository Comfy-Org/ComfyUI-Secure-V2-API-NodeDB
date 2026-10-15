"""Bounded V2 wrappers around unchanged pinned pack algorithms."""
import math
import torch
from comfy_api.latest import ComfyExtension, io
from .image_filter_adjustments_node import KMCDEV_Image_Filter_Adjustments as Filters
from .image_processor import KMCDEV_Image_Blank_Alpha as Blank
from .image_processor import KMCDEV_Image_Blend_Mask as Blend
from .image_processor import KMCDEV_Mix_Color_By_Mask as Mix

MAX_BATCH = 64
MAX_AXIS = 8192
MAX_ELEMENTS = 16_777_216
MAX_AGGREGATE = 33_554_432
MAX_WORKSPACE = 67_108_864


def _tensor(value, mask=False):
    if not isinstance(value,torch.Tensor) or value.ndim not in ((2,3) if mask else (4,)):
        raise TypeError("expected bounded MASK or BHWC IMAGE tensor")
    if not value.is_floating_point():
        raise TypeError("tensor must have floating dtype")
    shape = tuple(value.shape)
    if not shape or any(not 1 <= n <= MAX_AXIS for n in shape) or value.numel() > MAX_ELEMENTS:
        raise ValueError("tensor exceeds bounded dimensions/elements")
    if (value.ndim in (3,4) and shape[0] > MAX_BATCH) or (not mask and shape[-1] not in (1,2,3,4)):
        raise ValueError("tensor exceeds bounded batch/channels")
    return value.numel()


def _controls(legacy, inputs):
    for name,spec in legacy.INPUT_TYPES()["required"].items():
        kind = spec[0]
        if kind in ("IMAGE","MASK"):
            continue
        value = inputs[name]
        if isinstance(kind,list):
            if value not in kind:
                raise ValueError(name + " is not a declared choice")
        elif kind == "INT":
            if type(value) is not int or not spec[1]["min"] <= value <= spec[1]["max"]:
                raise ValueError(name + " must be a bounded integer")
        elif kind == "FLOAT":
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not spec[1]["min"] <= value <= spec[1]["max"]:
                raise ValueError(name + " must be finite and within schema bounds")


def _validate(legacy, inputs):
    _controls(legacy,inputs)
    sizes = []
    for name,spec in legacy.INPUT_TYPES()["required"].items():
        if spec[0] in ("IMAGE","MASK"):
            sizes.append(_tensor(inputs[name],spec[0] == "MASK"))
    if sum(sizes) > MAX_AGGREGATE:
        raise ValueError("aggregate inputs exceed bounded limit")
    if legacy is Blank:
        projected = (inputs["width"]//8*8) * (inputs["height"]//8*8) * 4
    elif legacy is Mix:
        b,h,w,c = inputs["image"].shape
        mask = inputs["mask"]
        if mask.ndim == 3:
            b,h,w = [max(a,z) for a,z in zip((b,h,w),mask.shape)]
        projected = b*h*w*max(c,3)
    elif legacy is Filters:
        projected = inputs["image"].numel()
    else:
        projected = max(inputs["image_a"].numel(), inputs["image_b"].numel())
    # Conservative projected output+temporary arrays, before PIL/Torch allocation.
    if projected > MAX_ELEMENTS or projected*4 + sum(sizes) > MAX_WORKSPACE:
        raise ValueError("projected output/workspace exceeds bounded limit")
    for name,spec in legacy.INPUT_TYPES()["required"].items():
        if spec[0] in ("IMAGE","MASK") and not torch.isfinite(inputs[name]).all():
            raise ValueError("tensor must be finite")


def _schema(node_id, display, legacy):
    kinds = {"IMAGE":io.Image,"MASK":io.Mask,"INT":io.Int,"FLOAT":io.Float}
    inputs = []
    for name,spec in legacy.INPUT_TYPES()["required"].items():
        if isinstance(spec[0],list):
            inputs.append(io.Combo.Input(name,options=spec[0]))
        else:
            inputs.append(kinds[spec[0]].Input(name,**(spec[1] if len(spec)>1 else {})))
    return io.Schema(node_id=node_id,display_name=display,category=legacy.CATEGORY,
                     inputs=inputs,outputs=[io.Image.Output()])


class ImageFilterAdjustments(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return _schema("ImageFilterAdjustments","Image Filter Adjustments",Filters)
    @classmethod
    def execute(cls,image,brightness,contrast,saturation,sharpness,blur,gaussian_blur,edge_enhance,detail_enhance):
        inputs = dict(image=image,brightness=brightness,contrast=contrast,saturation=saturation,
                      sharpness=sharpness,blur=blur,gaussian_blur=gaussian_blur,
                      edge_enhance=edge_enhance,detail_enhance=detail_enhance)
        _validate(Filters,inputs)
        return io.NodeOutput(*Filters().apply_filters(**inputs))


class ImageBlankAlpha(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return _schema("ImageBlankAlpha","Image Blank with Alpha",Blank)
    @classmethod
    def execute(cls,width,height,red,green,blue,alpha):
        inputs = dict(width=width,height=height,red=red,green=green,blue=blue,alpha=alpha)
        _validate(Blank,inputs)
        return io.NodeOutput(*Blank().blank_image_alpha(**inputs))


class ImageBlendMask(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return _schema("ImageBlendMask","Image Blend Mask",Blend)
    @classmethod
    def execute(cls,image_a,image_b,mask,blend_percentage):
        inputs = dict(image_a=image_a,image_b=image_b,mask=mask,blend_percentage=blend_percentage)
        _validate(Blend,inputs)
        return io.NodeOutput(*Blend().image_blend_mask(**inputs))


class ImageMixColorByMask(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return _schema("ImageMixColorByMask","Image Mix Color by Mask",Mix)
    @classmethod
    def execute(cls,image,r,g,b,mask):
        inputs = dict(image=image,r=r,g=g,b=b,mask=mask)
        _validate(Mix,inputs)
        return io.NodeOutput(*Mix().mix(**inputs))


NODE_CLASS_MAPPINGS = {cls.__name__:cls for cls in
    (ImageFilterAdjustments,ImageBlankAlpha,ImageBlendMask,ImageMixColorByMask)}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageFilterAdjustments":"Image Filter Adjustments","ImageBlankAlpha":"Image Blank with Alpha",
    "ImageBlendMask":"Image Blend Mask","ImageMixColorByMask":"Image Mix Color by Mask"}


class FilterExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint():
    return FilterExtension()
