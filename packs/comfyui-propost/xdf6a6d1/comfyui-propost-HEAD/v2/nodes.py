"""Bounded raw-compute V2 entrypoints; the pinned algorithms stay pack-side."""
import math
import torch
from comfy_api.latest import io, sdk, ComfyExtension
from . import _algorithms as algorithms
from .utils.loading import MAX_LUT_BYTES, read_lut_bytes

MAX_ELEMENTS = 8_388_608
MAX_WORKSPACE_BYTES = 512 * 1024 * 1024

def validate_tensor(value):
    if not isinstance(value, torch.Tensor) or value.ndim != 4 or not value.is_floating_point():
        raise TypeError("expected floating BHWC IMAGE")
    if value.shape[0] > 64 or any(not 1 <= d <= 4096 for d in value.shape) or value.shape[-1] > 4 or value.numel() > MAX_ELEMENTS:
        raise ValueError("image exceeds batch/dimension/element bounds")
    if value.device.type != "cpu":
        raise ValueError("pinned NumPy/OpenCV algorithm requires CPU image")
    if not torch.isfinite(value).all():
        raise ValueError("image must be finite")
    return value.numel() * value.element_size()

def validate_inputs(legacy, inputs):
    total = 0
    for name,spec in legacy.INPUT_TYPES()["required"].items():
        kind = spec[0]
        value = inputs[name]
        if kind == "IMAGE":
            total += validate_tensor(value)
        elif isinstance(kind, list):
            if name != "lut_name" and value not in kind:
                raise ValueError(name + " is not a declared choice")
        elif kind == "BOOLEAN":
            if type(value) is not bool:
                raise TypeError(name + " must be boolean")
        elif kind in ("FLOAT", "INT"):
            maximum = (2**64-1) if name == "seed" else 1e6
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or abs(value) > maximum:
                raise ValueError(name + " must be a bounded finite scalar")
            if kind == "INT" and type(value) is not int:
                raise TypeError(name + " must be an integer")
    b,h,w,c = inputs["image"].shape
    steps = inputs.get("steps",1)
    if type(steps) is not int or not 1 <= steps <= 32:
        raise ValueError("blur steps must be bounded")
    if not 0 <= inputs.get("blur_strength",0) <= 256:
        raise ValueError("blur kernel exceeds bound")
    if not 1 <= inputs.get("mask_blur",1) <= 127:
        raise ValueError("mask kernel exceeds bound")
    work = total + b*h*w*(c*8*(steps+4)+64)
    if legacy is algorithms.ProPostFilmGrain:
        scale = inputs["scale"]
        projected_w, projected_h = int(w/scale), int(h/scale)
        if projected_w > 4096 or projected_h > 4096:
            raise ValueError("grain scaled dimensions exceed bound")
        # Fine grain creates a larger intermediate noise grid (scale 0.8).
        work += b*max(0,projected_w)*max(0,projected_h)*128
        if not 0 <= inputs["sharpen"] <= 10:
            raise ValueError("sharpen iterations exceed bound")
    if work > MAX_WORKSPACE_BYTES:
        raise ValueError("projected workspace exceeds bounded limit")

def schema(cls):
    legacy = cls.LEGACY
    kinds = {"IMAGE":io.Image,"INT":io.Int,"FLOAT":io.Float,"BOOLEAN":io.Boolean}
    inputs = []
    for name,spec in legacy.INPUT_TYPES()["required"].items():
        if name == "lut_name":
            inputs.append(io.Combo.Input(name, options=[],remote=io.RemoteOptions(
                "/secure-nodes/assets/input?kind=lut",refresh_button=True)))
        elif isinstance(spec[0],list):
            inputs.append(io.Combo.Input(name,options=spec[0]))
        else:
            inputs.append(kinds[spec[0]].Input(name,**(spec[1] if len(spec)>1 else {})))
    outputs = [({"IMAGE":io.Image,"MASK":io.Mask}[kind]).Output() for kind in legacy.RETURN_TYPES]
    return io.Schema(node_id=cls.__name__,display_name=algorithms.NODE_DISPLAY_NAME_MAPPINGS[cls.__name__],
                     category=legacy.CATEGORY,inputs=inputs,outputs=outputs)

class _Node(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return schema(cls)
    @classmethod
    async def execute(cls, **inputs):
        validate_inputs(cls.LEGACY,inputs)
        values = getattr(cls.LEGACY(),cls.LEGACY.FUNCTION)(**inputs)
        # The upstream zero-intensity Vignette returns an unwrapped tensor.
        # Normalize the declared single-output container without changing pixels.
        if isinstance(values,torch.Tensor):
            values = (values,)
        return io.NodeOutput(*values)

class ProPostVignette(_Node):
    LEGACY = algorithms.ProPostVignette
class ProPostFilmGrain(_Node):
    LEGACY = algorithms.ProPostFilmGrain
class ProPostRadialBlur(_Node):
    LEGACY = algorithms.ProPostRadialBlur
class ProPostDepthMapBlur(_Node):
    LEGACY = algorithms.ProPostDepthMapBlur

class ProPostApplyLUT(_Node):
    LEGACY = algorithms.ProPostApplyLUT
    SDK_PERMISSIONS = ("raw","assets")
    @classmethod
    async def execute(cls, image, lut_name, strength, log):
        validate_inputs(cls.LEGACY,dict(image=image,lut_name=lut_name,strength=strength,log=log))
        if not isinstance(lut_name,str) or len(lut_name)>1024 or not lut_name.lower().endswith(".cube"):
            raise ValueError("LUT must be a bounded logical cube filename")
        if lut_name.startswith(("/","\\",)) or "\\" in lut_name or any(p in ("",".","..") for p in lut_name.split("/")):
            raise ValueError("LUT must be a confined logical filename")
        asset = await sdk.ctx().assets.resolve("input",lut_name)
        size = await sdk.ctx().assets.size(asset)
        if not 0 < size <= MAX_LUT_BYTES:
            raise ValueError("LUT exceeds bounded byte limit")
        payload = await sdk.ctx().assets.read_range(asset,0,size)
        lut = read_lut_bytes(payload,lut_name.rsplit("/",1)[-1].rsplit(".",1)[0])
        return io.NodeOutput(*cls.LEGACY().lut_image(image,lut,strength,log))

NODE_CLASS_MAPPINGS = {cls.__name__:cls for cls in (
    ProPostVignette,ProPostFilmGrain,ProPostRadialBlur,ProPostDepthMapBlur,ProPostApplyLUT)}
NODE_DISPLAY_NAME_MAPPINGS = algorithms.NODE_DISPLAY_NAME_MAPPINGS

class Extension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())
async def comfy_entrypoint():
    return Extension()
