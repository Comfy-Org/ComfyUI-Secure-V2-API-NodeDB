"""Secure Nodes V2 bindings for WhiteRabbit's fourteen workflow nodes."""
from __future__ import annotations

from fractions import Fraction
from io import BytesIO
from pathlib import Path
from typing import Any

import torch

from comfy_api.latest import io, sdk

from .whiterabbit.domain.rife import get_rife_model_spec
from .whiterabbit.domain.watermark import WatermarkOptions
from .whiterabbit.nodes_v3.loop_autocrop import AutocropToLoopV3
from .whiterabbit.nodes_v3.looping import (
    AssembleLoopFramesV3,
    PrepareLoopFramesV3,
    RollFramesV3,
    TrimBatchEndsV3,
    UnrollFramesV3,
)
from .whiterabbit.nodes_v3.pixel_hold import PixelHoldV3
from .whiterabbit.nodes_v3.rife import (
    RifeFpsResampleV3,
    RifeSeamTimingAnalyzerV3,
    RifeVfiAdvancedV3,
    RifeVfiOptV3,
)
from .whiterabbit.nodes_v3.scaling import (
    BatchResizeWithLanczosV3,
    UpscaleWithModelAdvancedV3,
)
from .whiterabbit.nodes_v3.watermark import BatchWatermarkSingleV3
from .whiterabbit.runtime.rife_architecture import (
    LegacyRife47,
    create_core_rife,
    remap_core_state_dict,
)
from .whiterabbit.runtime.rife_interpolation import RifeInterpolationEngine
from .whiterabbit.runtime.rife_loading import LoadedRifeModel
from .whiterabbit.runtime.watermark_composite import WatermarkCompositor
from .whiterabbit.services.rife import RifeService


_RIFE_47 = sdk.HuggingFaceWeight(
    repo_id="dci05049/rife47.pth",
    filename="rife47.pth",
    folder="frame_interpolation",
    revision="40100cdd99f12af05f1e3630f8de32208d741fbc",
    sha256="6a8a825ab2750558bdd20dcced386fd82b7222c7ba58c11d3b611d9c44f1be63",
    on_demand=True,
)
_RIFE_49 = sdk.HuggingFaceWeight(
    repo_id="VMTamashii/rife49",
    filename="rife49.pth",
    folder="frame_interpolation",
    revision="6213b4f9df15a06c7883ad6c9362c44a44ba2fa4",
    sha256="e55fd00f3cc184e3c65961f4bb827a9da022e78eed36b055242c0ac30000d533",
    on_demand=True,
)
_RIFE_425 = sdk.HuggingFaceWeight(
    repo_id="Comfy-Org/frame_interpolation",
    filename="frame_interpolation/rife_v4.25.safetensors",
    folder="frame_interpolation",
    revision="f8ffff13b0df7fb55cd3fc15f0834a27979c92e1",
    sha256="1505884b9bdae956795430d2a70f7e2317b2abd8f130f8cfdb35a5759f909481",
    on_demand=True,
)
_RIFE_426 = sdk.HuggingFaceWeight(
    repo_id="Comfy-Org/frame_interpolation",
    filename="frame_interpolation/rife_v4.26.safetensors",
    folder="frame_interpolation",
    revision="f8ffff13b0df7fb55cd3fc15f0834a27979c92e1",
    sha256="151874592c877740e5db11522f4514df569eeafb0a0fcb2696f16e9e8d317c94",
    on_demand=True,
)
_RIFE_WEIGHTS = (_RIFE_47, _RIFE_49, _RIFE_425, _RIFE_426)
_RIFE_BY_NAME = {item.filename.rsplit("/", 1)[-1]: item for item in _RIFE_WEIGHTS}
_RIFE_CACHE: dict[str, LoadedRifeModel] = {}


async def _materialize(value: Any) -> Any:
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    return value


async def _wrap(kind: str, value: Any) -> Any:
    if kind == "IMAGE":
        return await sdk.ImageRef._from_raw(value)
    if kind == "MASK":
        return await sdk.MaskRef._from_raw(value)
    return value


def _pure_binding(source: type, output_kinds: tuple[str, ...]) -> type:
    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        del cls
        values = {
            name: await _materialize(value) for name, value in kwargs.items()
        }
        await sdk.ctx().progress.update(0, 1)
        result = source.execute(**values)
        wrapped = [
            await _wrap(kind, value)
            for kind, value in zip(output_kinds, result, strict=True)
        ]
        await sdk.ctx().progress.update(1, 1)
        return io.NodeOutput(*wrapped)

    attrs = {
        "__module__": __name__,
        "SDK_REFS": True,
        "SDK_PERMISSIONS": ("raw",),
        "execute": classmethod(execute),
    }
    return type(source.__name__.removesuffix("V3") + "Secure", (source,), attrs)


PrepareLoopFrames = _pure_binding(
    PrepareLoopFramesV3, ("IMAGE", "IMAGE"))
AssembleLoopFrames = _pure_binding(AssembleLoopFramesV3, ("IMAGE",))
RollFrames = _pure_binding(RollFramesV3, ("IMAGE", "INT"))
UnrollFrames = _pure_binding(UnrollFramesV3, ("IMAGE",))
TrimBatchEnds = _pure_binding(TrimBatchEndsV3, ("IMAGE",))
AutocropToLoop = _pure_binding(
    AutocropToLoopV3, ("IMAGE", "INT", "INT", "FLOAT", "STRING"))
PixelHold = _pure_binding(PixelHoldV3, ("IMAGE", "IMAGE"))
BatchResizeWithLanczos = _pure_binding(
    BatchResizeWithLanczosV3, ("IMAGE", "INT", "INT", "MASK"))


class UpscaleWithModelAdvancedSecure(UpscaleWithModelAdvancedV3):
    SDK_REFS = True
    SDK_PERMISSIONS: tuple[str, ...] = ()

    @classmethod
    async def execute(
        cls,
        upscale_model: sdk.UpscaleModelRef,
        image: sdk.ImageRef,
        max_batch_size: int = 0,
        tile_size: int = 0,
        channels_last: bool = False,
        precision: str = "fp32",
    ) -> io.NodeOutput:
        del cls
        batch = int(max_batch_size)
        if batch == 0:
            batch = await image.batch_size()
        names = {"fp32": "float32", "fp16": "float16", "bf16": "bfloat16"}
        try:
            dtype = names[str(precision)]
        except KeyError as error:
            raise ValueError(f"unsupported upscale precision {precision!r}") from error
        result = await upscale_model.upscale(
            image,
            per_batch=batch,
            precision=dtype,
            tile_size=int(tile_size),
            channels_last=bool(channels_last),
        )
        return io.NodeOutput(result)


class _BytesWatermarkCompositor(WatermarkCompositor):
    def __init__(self, watermark: torch.Tensor) -> None:
        self._watermark = watermark

    def _load_rgba(self, _path: Path, device: torch.device) -> torch.Tensor:
        return self._watermark.to(device=device, dtype=torch.float32)


class BatchWatermarkSingleSecure(BatchWatermarkSingleV3):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "assets")

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        watermark: str,
        position: str,
        scale: int,
        transparency: int,
        rotation: int,
        padding_x: int,
        padding_y: int,
        optical_padding: bool,
        optical_strength: int,
        max_batch_size: int,
        sinc_window: int,
        precision: str,
    ) -> io.NodeOutput:
        del cls
        from PIL import Image
        import numpy

        asset = await sdk.ctx().assets.resolve("input", str(watermark))
        data = await sdk.ctx().assets.read_bytes(asset)
        try:
            with Image.open(BytesIO(data)) as opened:
                array = numpy.asarray(
                    opened.convert("RGBA"), dtype=numpy.float32) / 255.0
        except Exception as error:
            raise ValueError("selected watermark is not a valid image") from error
        overlay = torch.from_numpy(array).permute(2, 0, 1).contiguous()
        options = WatermarkOptions(
            position=position,
            scale_percent=scale,
            transparency_percent=transparency,
            rotation_degrees=rotation % 360,
            padding_x=padding_x,
            padding_y=padding_y,
            optical_padding=optical_padding,
            optical_strength=optical_strength,
            maximum_batch_size=max_batch_size,
            sinc_window=sinc_window,
            precision=precision,
        )
        result = _BytesWatermarkCompositor(overlay).apply(
            await image.raw(), Path("managed-watermark"), options)
        return io.NodeOutput(await sdk.ImageRef._from_raw(result))


class _SkipMask:
    def __init__(self, values: list[bool]) -> None:
        self._values = values

    def is_frame_skipped(self, index: int) -> bool:
        return self._values[index]


class _FixedLoader:
    def __init__(self, loaded: LoadedRifeModel) -> None:
        self._loaded = loaded

    def load(
        self, filename: str, frame_shape: tuple[int, ...] | None = None,
        scale_factor: float = 1.0,
    ) -> LoadedRifeModel:
        del frame_shape, scale_factor
        if filename != self._loaded.spec.filename:
            raise ValueError("RIFE loader received the wrong declared model")
        return self._loaded


async def _loaded_rife(filename: str) -> LoadedRifeModel:
    cached = _RIFE_CACHE.get(filename)
    if cached is not None:
        return cached
    try:
        weight = _RIFE_BY_NAME[filename]
    except KeyError as error:
        raise ValueError(f"unsupported RIFE checkpoint {filename!r}") from error
    logical = await sdk.ctx().models.download_huggingface_weights(
        repo_id=weight.repo_id,
        filename=weight.filename,
        folder=weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )
    if logical != weight.catalogue_name:
        raise RuntimeError("RIFE weight broker returned the wrong asset")
    asset = await sdk.ctx().assets.resolve(weight.folder, logical)
    state = await sdk.ctx().assets.load_state_dict(asset)
    if type(state) is not dict or not state:
        raise ValueError("RIFE checkpoint did not contain a state dictionary")
    state = {
        str(name): tensor.detach().cpu() for name, tensor in state.items()
        if isinstance(name, str) and isinstance(tensor, torch.Tensor)
    }
    spec = get_rife_model_spec(filename)
    if spec.architecture == "legacy47":
        module = LegacyRife47()
        module.load_state_dict(state, strict=True)
    else:
        module = create_core_rife(remap_core_state_dict(state))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device.type == "cuda" else torch.float32
    module.eval().to(device=device, dtype=dtype)
    loaded = LoadedRifeModel(module, None, device, dtype, spec)
    _RIFE_CACHE[filename] = loaded
    return loaded


async def _rife_service(filename: str) -> RifeService:
    engine = RifeInterpolationEngine(_FixedLoader(await _loaded_rife(filename)))
    return RifeService(engine)


async def _states(
    value: sdk.InterpolationStatesRef | dict[str, Any] | None, pair_count: int,
) -> _SkipMask | None:
    if value is None:
        return None
    if isinstance(value, sdk.InterpolationStatesRef):
        return _SkipMask(await value.skip_mask(pair_count))
    if type(value) is not dict or set(value) != {"frame_indices", "is_skip_list"}:
        raise TypeError("INTERPOLATION_STATES has an unsupported data shape")
    indices = value["frame_indices"]
    mode = value["is_skip_list"]
    if type(indices) is not list or len(indices) > 100_000:
        raise TypeError("INTERPOLATION_STATES frame_indices must be a bounded list")
    if type(mode) is not bool or any(
        isinstance(index, bool) or not isinstance(index, int) or index < 0
        for index in indices
    ):
        raise TypeError("INTERPOLATION_STATES data contains invalid values")
    selected = set(indices)
    return _SkipMask([
        (index in selected) if mode else (index not in selected)
        for index in range(pair_count)
    ])


class _RifeNode:
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "assets", "models.download")
    SDK_REQUIRED_WEIGHTS = _RIFE_WEIGHTS


class RifeVfiOptSecure(_RifeNode, RifeVfiOptV3):
    @classmethod
    async def execute(cls, ckpt_name: str, frames: sdk.ImageRef, multiplier: int = 2,
                      scale_factor: float = 1.0, ensemble: bool = True,
                      clear_cache_after_n_frames: int = 10,
                      optional_interpolation_states: sdk.InterpolationStatesRef | None = None,
                      ) -> io.NodeOutput:
        del cls
        if int(multiplier) <= 1:
            return io.NodeOutput(frames)
        values = await frames.raw()
        service = await _rife_service(ckpt_name)
        result = service.interpolate(
            ckpt_name, values, multiplier, scale_factor, ensemble,
            clear_cache_after_n_frames,
            await _states(optional_interpolation_states, values.shape[0] - 1),
        )[0]
        return io.NodeOutput(await sdk.ImageRef._from_raw(result))


class RifeVfiAdvancedSecure(_RifeNode, RifeVfiAdvancedV3):
    @classmethod
    async def execute(cls, ckpt_name: str, frames: sdk.ImageRef, multiplier: int = 2,
                      t_mode: str = "linear", t_gamma: float = 1.0,
                      t_min: float = 0.0, t_max: float = 1.0,
                      scale_factor: float = 1.0, ensemble: bool = True,
                      clear_cache_after_n_frames: int = 10,
                      custom_t_list_csv: str = "",
                      optional_interpolation_states: sdk.InterpolationStatesRef | None = None,
                      ) -> io.NodeOutput:
        del cls
        if int(multiplier) <= 0:
            return io.NodeOutput(frames)
        values = await frames.raw()
        service = await _rife_service(ckpt_name)
        result = service.interpolate_advanced(
            ckpt_name, values, multiplier, t_mode, t_gamma, t_min, t_max,
            scale_factor, ensemble, clear_cache_after_n_frames,
            custom_t_list_csv,
            await _states(optional_interpolation_states, values.shape[0] - 1),
        )[0]
        return io.NodeOutput(await sdk.ImageRef._from_raw(result))


class RifeFpsResampleSecure(_RifeNode, RifeFpsResampleV3):
    @classmethod
    async def execute(cls, ckpt_name: str, frames: sdk.ImageRef, fps_in: float,
                      fps_out: float, **options: Any) -> io.NodeOutput:
        del cls
        values = await frames.raw()
        input_rate = Fraction(str(float(fps_in)))
        output_rate = Fraction(str(float(fps_out)))
        ratio = input_rate / output_rate
        needs_model = not (
            input_rate == output_rate
            or (ratio.denominator == 1 and ratio.numerator > 1)
            or values.shape[0] <= 1
        )
        if needs_model:
            service = await _rife_service(ckpt_name)
        else:
            # The exact no-inference branches return before touching this loader.
            service = RifeService(RifeInterpolationEngine(None))
        result = service.resample_fps(
            ckpt_name, fps_in, fps_out, values,
            options.get("scale_factor", 1.0), options.get("ensemble", True),
            options.get("linearize", False), options.get("lf_guardrail", False),
            options.get("lf_sigma", 13.0), options.get("source_pair_match", False),
            options.get("match_a_cap", 0.02), options.get("match_b_cap", 2.0 / 255.0),
            options.get("edge_band_lock", False), options.get("tau_low", 1.5 / 255.0),
            options.get("tau_high", 6.0 / 255.0), options.get("band_radius", 4),
            options.get("band_soft_sigma", 2.0),
            options.get("clear_cache_after_n_frames", 10),
        )[0]
        return io.NodeOutput(await sdk.ImageRef._from_raw(result))


class RifeSeamTimingAnalyzerSecure(_RifeNode, RifeSeamTimingAnalyzerV3):
    @classmethod
    async def execute(cls, ckpt_name: str, scale_factor: float, ensemble: bool,
                      full_clip: sdk.ImageRef, multiplier: int,
                      use_first_two: bool, use_last_two: bool,
                      use_global_median: bool, calibrate_metric: str,
                      calibrate_iters: int, t_min: float, t_max: float,
                      auto_tmax: bool = False, t_cap: float = 0.995,
                      ) -> io.NodeOutput:
        del cls
        if int(multiplier) <= 0:
            return io.NodeOutput("", 0)
        values = await full_clip.raw()
        service = await _rife_service(ckpt_name)
        return io.NodeOutput(*service.analyze_seam(
            ckpt_name, scale_factor, ensemble, values, multiplier,
            use_first_two, use_last_two, use_global_median, calibrate_metric,
            calibrate_iters, t_min, t_max, auto_tmax, t_cap,
        ))


NODE_CLASS_MAPPINGS = {
    "PrepareLoopFrames": PrepareLoopFrames,
    "AssembleLoopFrames": AssembleLoopFrames,
    "RollFrames": RollFrames,
    "UnrollFrames": UnrollFrames,
    "AutocropToLoop": AutocropToLoop,
    "TrimBatchEnds": TrimBatchEnds,
    "RIFE_VFI_Opt": RifeVfiOptSecure,
    "RIFE_VFI_Advanced": RifeVfiAdvancedSecure,
    "RIFE_SeamTimingAnalyzer": RifeSeamTimingAnalyzerSecure,
    "RIFE_FPS_Resample": RifeFpsResampleSecure,
    "PixelHold": PixelHold,
    "UpscaleWithModelAdvanced": UpscaleWithModelAdvancedSecure,
    "BatchResizeWithLanczos": BatchResizeWithLanczos,
    "BatchWatermarkSingle": BatchWatermarkSingleSecure,
}

NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
