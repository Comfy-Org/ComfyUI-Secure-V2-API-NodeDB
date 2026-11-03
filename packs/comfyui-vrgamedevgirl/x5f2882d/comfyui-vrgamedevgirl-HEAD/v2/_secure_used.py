"""Secure Nodes V2 classes for comfyui-vrgamedevgirl's six converted node types (pin 5f2882d835bf).

Each schema is the original's, frozen in the lane gate (_frozen_schema.py). Each execute calls the
original method in _vrgdg_used_original.py, which holds the verbatim class bodies.
  - FastFilmGrain, ColorMatchToReference, FastUnsharpSharpen, FastLaplacianSharpen: public V2 value
    mode (IMAGE arrives and returns as a tensor; precedent comfyui-advanced-photo-grain v2), "raw".
  - VRGDG_MultiStringConcat: strings only, no permissions.
  - VRGDG_LUTS: the original read user-supplied .cube files from the pack's own LUTS folder. Here the
    file comes from the "vrgdg_luts" asset kind (declared in secure-nodes.json `asset_directories`;
    precedent: comfyui_essentials v2 image.py:1793, "essentials_luts"), and a LUT the host does not
    have is a named refusal at queue time, never a silent pass-through.
"""
from comfy_api.latest import io, sdk

from . import _vrgdg_used_original as _orig
from ._frozen_schema import schema_for

PACK = "comfyui-vrgamedevgirl"
LUT_KIND = "vrgdg_luts"
NO_LUTS = "No LUT files found"


class LutUnavailableError(RuntimeError):
    """The selected LUT is not available from the host's vrgdg_luts asset kind."""


class FastFilmGrain(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("FastFilmGrain")

    @classmethod
    async def execute(cls, images, grain_intensity, saturation_mix, batch_size):
        return io.NodeOutput(*_orig.FastFilmGrain().apply_grain(images, grain_intensity, saturation_mix, batch_size))


class ColorMatchToReference(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("ColorMatchToReference")

    @classmethod
    async def execute(cls, images, reference_image, match_strength, batch_size):
        return io.NodeOutput(*_orig.ColorMatchToReference().match_color(images, reference_image, match_strength, batch_size))


class FastUnsharpSharpen(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("FastUnsharpSharpen")

    @classmethod
    async def execute(cls, images, strength, use_gpu):
        return io.NodeOutput(*_orig.FastUnsharpSharpen().apply_unsharp(images, strength, use_gpu))


class FastLaplacianSharpen(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return schema_for("FastLaplacianSharpen")

    @classmethod
    async def execute(cls, images, strength, use_gpu):
        return io.NodeOutput(*_orig.FastLaplacianSharpen().apply_laplacian(images, strength, use_gpu))


class VRGDG_MultiStringConcat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schema_for("VRGDG_MultiStringConcat")

    @classmethod
    async def execute(cls, string_count, delimiter, **kwargs):
        return io.NodeOutput(*_orig.VRGDG_MultiStringConcat().concat(string_count, delimiter, **kwargs))


async def _lut_asset(lut_name):
    """The resolved asset, or a refusal message naming what the host lacks."""
    assets = sdk.ctx().assets
    try:
        if not await assets.exists(LUT_KIND, lut_name):
            return None, (f"{PACK}/VRGDG_LUTS: LUT {lut_name!r} is not in the host's {LUT_KIND} asset folder "
                          "(the original read it from the pack's own LUTS folder)")
        return await assets.resolve(LUT_KIND, lut_name), None
    except PermissionError:
        raise
    except Exception as exc:
        return None, (f"{PACK}/VRGDG_LUTS: the host has no {LUT_KIND} asset kind for LUT files "
                      f"({type(exc).__name__}: {exc})")


class VRGDG_LUTS(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "assets")

    @classmethod
    def define_schema(cls):
        return schema_for("VRGDG_LUTS")

    @classmethod
    async def validate_inputs(cls, lut_name=None):
        # Taking lut_name here stops Core checking a saved name against the frozen menu; the host's
        # LUT folder decides instead. The original's "No LUT files found" entry passes validation and
        # raises at execution, as before.
        if lut_name is None or lut_name == NO_LUTS:
            return True
        _asset, problem = await _lut_asset(lut_name)
        return problem if problem is not None else True

    @classmethod
    async def fingerprint_inputs(cls, image=None, lut_name=None, device=None, strength=None):
        # The original keyed re-execution on the LUTS folder's file times and sizes; the LUT's content
        # digest answers the same question.
        if lut_name is None or lut_name == NO_LUTS:
            return f"missing|{device}|{strength}"
        asset, problem = await _lut_asset(lut_name)
        if problem is not None:
            return f"missing|{lut_name}|{device}|{strength}"
        return f"{lut_name}|{await sdk.ctx().assets.digest(asset)}|{device}|{strength}"

    @classmethod
    async def execute(cls, image, lut_name, device, strength):
        content = b""
        if lut_name != NO_LUTS:
            asset, problem = await _lut_asset(lut_name)
            if problem is not None:
                raise LutUnavailableError(problem)
            content = await sdk.ctx().assets.read_bytes(asset)
        value = await image.raw()
        call = type("VRGDG_LUTS", (_orig.VRGDG_LUTS,), {"_lut_bytes": content})
        (output,) = call().apply_lut(value, lut_name, device, strength)
        return io.NodeOutput(await sdk.ImageRef.from_value(output))


NODE_CLASS_MAPPINGS = {
    "FastFilmGrain": FastFilmGrain,
    "ColorMatchToReference": ColorMatchToReference,
    "FastUnsharpSharpen": FastUnsharpSharpen,
    "FastLaplacianSharpen": FastLaplacianSharpen,
    "VRGDG_LUTS": VRGDG_LUTS,
    "VRGDG_MultiStringConcat": VRGDG_MultiStringConcat,
}
