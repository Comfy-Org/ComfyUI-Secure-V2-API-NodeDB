"""Secure Nodes 2.0 implementations for the pinned Easy Use snapshot.

The original pack mixes useful tensor/value helpers with model loading,
sampling, server routes, arbitrary filesystem access, and several third-party
plugin bridges.  This module is the only Python entrypoint named by the sealed
manifest.  It preserves the frozen node schemas while routing heavyweight
objects and side effects through the Secure Nodes SDK.
"""
from __future__ import annotations

import ast
import asyncio
import base64
import io as bytes_io
import itertools
import json
import math
import operator
import random
import re
from decimal import Decimal, getcontext
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from ._image_ops import common_upscale
from . import _ipadapter
from ._secure_runtime import SCHEMAS, bind_node, materialize, sdk, unsupported
from ._wildcard_runtime import load_catalogue as _load_wildcard_catalogue
from ._wildcard_runtime import matrix as _wildcard_matrix_values
from ._wildcard_runtime import populate as _populate_catalogue_wildcards


MAX_FLOW_NUM = 20
_LORA_PATTERN = re.compile(r"<lora:([^:>]+)(?::(-?\d+(?:\.\d+)?))?>")

_IC_LIGHT_REVISION = "17f0c4319dcf84939b81066edb7abccc18832abd"
_IC_LIGHT_WEIGHTS = {
    "Foreground": sdk.HuggingFaceWeight(
        repo_id="huchenlei/IC-Light-ldm",
        filename="iclight_sd15_fc_unet_ldm.safetensors",
        folder="model_patches",
        revision=_IC_LIGHT_REVISION,
        sha256="9f91f1fc8ad2a2073c5a605fcd70cc70b2e7d2321b30aadca2a247d6490cd780",
        on_demand=True,
    ),
    "Foreground&Background": sdk.HuggingFaceWeight(
        repo_id="huchenlei/IC-Light-ldm",
        filename="iclight_sd15_fbc_unet_ldm.safetensors",
        folder="model_patches",
        revision=_IC_LIGHT_REVISION,
        sha256="97a662b8076504e0abad3b3a20b0e91d3312f2a5f19ffcef9059dab6d6679700",
        on_demand=True,
    ),
}

_IPADAPTER_REVISION = "018e402774aeeddd60609b4ecdb7e298259dc729"
_IPADAPTER_CLIP_WEIGHTS = {
    "vit_h": sdk.HuggingFaceWeight(
        repo_id="h94/IP-Adapter",
        filename="models/image_encoder/model.safetensors",
        folder="clip_vision",
        revision=_IPADAPTER_REVISION,
        sha256="6ca9667da1ca9e0b0f75e46bb030f7e011f44f86cbfb8d5a36590fcd7507b030",
        on_demand=True,
    ),
    "vit_g": sdk.HuggingFaceWeight(
        repo_id="h94/IP-Adapter",
        filename="sdxl_models/image_encoder/model.safetensors",
        folder="clip_vision",
        revision=_IPADAPTER_REVISION,
        sha256="657723e09f46a7c3957df651601029f66b1748afb12b419816330f16ed45d64d",
        on_demand=True,
    ),
}
_IPADAPTER_WEIGHTS = {
    ("STANDARD (medium strength)", "sd1"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="models/ip-adapter_sd15.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="289b45f16d043d0bf542e45831f971dcdaabe18b656f11e86d9dfba7e9ee3369",
            on_demand=True,
        ),
        "vit_h",
    ),
    ("STANDARD (medium strength)", "sdxl"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="sdxl_models/ip-adapter_sdxl_vit-h.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="ebf05d918348aec7abb02a5e9ecef77e0aaea6914a5c4ea13f50d45eb1681831",
            on_demand=True,
        ),
        "vit_h",
    ),
    ("VIT-G (medium strength)", "sd1"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="models/ip-adapter_sd15_vit-G.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="a26f736af07bb341a83dfea23713531d0575760e8ed947c68cb31a4c62d9c90b",
            on_demand=True,
        ),
        "vit_g",
    ),
    ("VIT-G (medium strength)", "sdxl"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="sdxl_models/ip-adapter_sdxl.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="ba1002529e783604c5f326d49f0122025392d1d20ac8d573b3eeb3e6dea4ebb6",
            on_demand=True,
        ),
        "vit_g",
    ),
    ("PLUS (high strength)", "sd1"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="models/ip-adapter-plus_sd15.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="a1c250be40455cc61a43da1201ec3f1edaea71214865fb47f57927e06cbe4996",
            on_demand=True,
        ),
        "vit_h",
    ),
    ("PLUS (high strength)", "sdxl"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="3f5062b8400c94b7159665b21ba5c62acdcd7682262743d7f2aefedef00e6581",
            on_demand=True,
        ),
        "vit_h",
    ),
    ("PLUS FACE (portraits)", "sd1"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="models/ip-adapter-plus-face_sd15.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="1c9edc21af6f737dc1d6e0e734190e976cfacf802d6b024b77aa3be922f7569b",
            on_demand=True,
        ),
        "vit_h",
    ),
    ("PLUS FACE (portraits)", "sdxl"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="677ad8860204f7d0bfba12d29e6c31ded9beefdf3e4bbd102518357d31a292c1",
            on_demand=True,
        ),
        "vit_h",
    ),
    ("FULL FACE - SD1.5 only (portraits stronger)", "sd1"): (
        sdk.HuggingFaceWeight(
            repo_id="h94/IP-Adapter",
            filename="models/ip-adapter-full-face_sd15.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_REVISION,
            sha256="f4a17fb643bf876235a45a0e87a49da2855be6584b28ca04c62a97ab5ff1c6f3",
            on_demand=True,
        ),
        "vit_h",
    ),
}
_IPADAPTER_COMPOSITION_REVISION = "0d2ed55c441a20c20e09da4dc086097703f26b61"
_IPADAPTER_WEIGHTS.update({
    ("COMPOSITION", "sd1"): (
        sdk.HuggingFaceWeight(
            repo_id="ostris/ip-composition-adapter",
            filename="ip_plus_composition_sd15.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_COMPOSITION_REVISION,
            sha256="4a02c9f4d2ade7c0e14db7471377ce5d326a2bfda7777231c79dc861c93f2c12",
            on_demand=True,
        ),
        "vit_h",
    ),
    ("COMPOSITION", "sdxl"): (
        sdk.HuggingFaceWeight(
            repo_id="ostris/ip-composition-adapter",
            filename="ip_plus_composition_sdxl.safetensors",
            folder="ipadapter",
            revision=_IPADAPTER_COMPOSITION_REVISION,
            sha256="e92dc36cc273bac3200b2e41807ebdc174076185d95a45238558d4c236b6da74",
            on_demand=True,
        ),
        "vit_h",
    ),
})
_IPADAPTER_REQUIRED_WEIGHTS = tuple(dict.fromkeys(
    [item[0] for item in _IPADAPTER_WEIGHTS.values()]
    + list(_IPADAPTER_CLIP_WEIGHTS.values())
))

_BRUSHNET_SD1_REVISION = "41dfa80ede7ef52722adfb3c8478abb4cc35397e"
_BRUSHNET_SDXL_REVISION = "84c7f9d8b4e90e8ba73eb39d01fe57e2bf757409"
_BRUSHNET_WEIGHTS = {
    ("brushnet_random", "sd1"): sdk.HuggingFaceWeight(
        repo_id="Kijai/BrushNet-fp16",
        filename="brushnet_random_mask_fp16.safetensors",
        folder="inpaint",
        revision=_BRUSHNET_SD1_REVISION,
        sha256="806712fe35c27c8401e30af788b111ead056043ff092f33a651397803320023b",
        on_demand=True,
    ),
    ("brushnet_segmentation", "sd1"): sdk.HuggingFaceWeight(
        repo_id="Kijai/BrushNet-fp16",
        filename="brushnet_segmentation_mask_fp16.safetensors",
        folder="inpaint",
        revision=_BRUSHNET_SD1_REVISION,
        sha256="68080b5e3f5228ed6272e78512ebb884b6247084d825312d6ab20d7f0ed2acc8",
        on_demand=True,
    ),
    ("brushnet_random", "sdxl"): sdk.HuggingFaceWeight(
        repo_id="yolain/brushnet",
        filename="brushnet_random_mask_sdxl.safetensors",
        folder="inpaint",
        revision=_BRUSHNET_SDXL_REVISION,
        sha256="d968334b1e1553bbc450dd1876840732ef8726593bde51f1f79a19dc82770a55",
        on_demand=True,
    ),
    ("brushnet_segmentation", "sdxl"): sdk.HuggingFaceWeight(
        repo_id="yolain/brushnet",
        filename="brushnet_segmentation_mask_sdxl.safetensors",
        folder="inpaint",
        revision=_BRUSHNET_SDXL_REVISION,
        sha256="a0f186ec0351102527d462d349d6dc844e11c8f004e5513cf921b156f7fff3ac",
        on_demand=True,
    ),
}
_BRUSHNET_REQUIRED_WEIGHTS = tuple(_BRUSHNET_WEIGHTS.values())

_FOOOCUS_REVISION = "74bbcc070e55219adb9b6c3b0d035b34e3697d1d"
_FOOOCUS_HEAD_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="lllyasviel/fooocus_inpaint",
    filename="fooocus_inpaint_head.pth",
    folder="inpaint",
    revision=_FOOOCUS_REVISION,
    sha256="32f7f838e0c6d8f13437ba8411e77a4688d77a2e34df8857e4ef4d51f6b97692",
    on_demand=True,
)
_FOOOCUS_PATCH_WEIGHTS = {
    "inpaint_v26 (1.32GB)": sdk.HuggingFaceWeight(
        repo_id="lllyasviel/fooocus_inpaint",
        filename="inpaint_v26.fooocus.patch",
        folder="inpaint",
        revision=_FOOOCUS_REVISION,
        sha256="f8657a025104e22d70f9c060635d8e8c2196f433871a2f68dc40abd2171f0d59",
        on_demand=True,
    ),
    "inpaint_v25 (2.58GB)": sdk.HuggingFaceWeight(
        repo_id="lllyasviel/fooocus_inpaint",
        filename="inpaint_v25.fooocus.patch",
        folder="inpaint",
        revision=_FOOOCUS_REVISION,
        sha256="640e480158e8a8e0aa673c77d19f8b4095a562ac72e2f2a146b445f78ed0febc",
        on_demand=True,
    ),
    "inpaint (1.32GB)": sdk.HuggingFaceWeight(
        repo_id="lllyasviel/fooocus_inpaint",
        filename="inpaint.fooocus.patch",
        folder="inpaint",
        revision=_FOOOCUS_REVISION,
        sha256="ba2a82dec0151105cb593ba7254f58548ec6810aeb9e081c4533fb227d654476",
        on_demand=True,
    ),
}
_FOOOCUS_REQUIRED_WEIGHTS = (
    _FOOOCUS_HEAD_WEIGHT, *_FOOOCUS_PATCH_WEIGHTS.values())

_POWERPAINT_MODEL_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="JunhaoZhuang/PowerPaint-v2-1",
    filename="PowerPaint_Brushnet/diffusion_pytorch_model.safetensors",
    folder="inpaint",
    revision="5ae2be3ac38b162df209b7ad5de036d339081e33",
    sha256="530f2886ef5bcdf199269ec344155a517639ba64219b85eeb23fd86aab93147f",
    on_demand=True,
)
_POWERPAINT_CLIP_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="JunhaoZhuang/PowerPaint-v1",
    filename="text_encoder/text_encoder.safetensors",
    folder="inpaint",
    revision="b4174b7cade590ab185dbdcfa09eee2c0f63410b",
    sha256="16410ea003cd5b3494c7e64b91b6669a40bad2b413e8255510dff8c3db5adfd7",
    on_demand=True,
)
_POWERPAINT_BASE_CLIP_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="runwayml/stable-diffusion-v1-5",
    filename="text_encoder/model.fp16.safetensors",
    folder="text_encoders",
    revision="451f4fe16113bff5a5d2269ed5ad43b0592e9a14",
    sha256="77795e2023adcf39bc29a884661950380bd093cf0750a966d473d1718dc9ef4e",
    on_demand=True,
)
_POWERPAINT_REQUIRED_WEIGHTS = (
    _POWERPAINT_MODEL_WEIGHT,
    _POWERPAINT_CLIP_WEIGHT,
    _POWERPAINT_BASE_CLIP_WEIGHT,
)

_LAYER_DIFFUSION_REVISION = "e337e9d7a0f2a6fee6c3580374327380f88d065b"


def _layer_diffusion_weight(filename: str, sha256: str, folder: str):
    return sdk.HuggingFaceWeight(
        repo_id="LayerDiffusion/layerdiffusion-v1",
        filename=filename,
        folder=folder,
        revision=_LAYER_DIFFUSION_REVISION,
        sha256=sha256,
        on_demand=True,
    )


_LAYER_DIFFUSION_WEIGHTS = {
    ("Attention Injection", "sd1"): _layer_diffusion_weight(
        "layer_sd15_transparent_attn.safetensors",
        "cc9ee87452bf1ccdd419035bf9618f6bdcaac1a2d3e23694d62e5a9c721da295",
        "model_patches",
    ),
    ("Attention Injection", "sdxl"): _layer_diffusion_weight(
        "layer_xl_transparent_attn.safetensors",
        "b7919c5b4837fb64f24c97a7abdf1a9c6e8d60de080a5dae089dde098266df95",
        "model_patches",
    ),
    ("Conv Injection", "sdxl"): _layer_diffusion_weight(
        "layer_xl_transparent_conv.safetensors",
        "5ee958d80dcd515fa7ac915274c536fadd3db5d919adeb5ff45107b6169aacc7",
        "model_patches",
    ),
    ("Everything", "sd1"): _layer_diffusion_weight(
        "layer_sd15_joint.safetensors",
        "2cc81c33c1a786bdc376c6d1bfb43dbdffda2f610f7c6b4ebd776505a29712bd",
        "model_patches",
    ),
    ("Foreground", "sd1"): _layer_diffusion_weight(
        "layer_sd15_fg2bg.safetensors",
        "5bade856ec3e55d6ceb0e35bbc97cea7fa4953f7776c8032f2fe52ba740ed580",
        "model_patches",
    ),
    ("Foreground to Background", "sd1"): _layer_diffusion_weight(
        "layer_sd15_fg2bg.safetensors",
        "5bade856ec3e55d6ceb0e35bbc97cea7fa4953f7776c8032f2fe52ba740ed580",
        "model_patches",
    ),
    ("Background", "sd1"): _layer_diffusion_weight(
        "layer_sd15_bg2fg.safetensors",
        "8367f976da1cc4275e513c7fb40f977ca312e79e720d7db7ae94978a9359fb62",
        "model_patches",
    ),
    ("Background to Foreground", "sd1"): _layer_diffusion_weight(
        "layer_sd15_bg2fg.safetensors",
        "8367f976da1cc4275e513c7fb40f977ca312e79e720d7db7ae94978a9359fb62",
        "model_patches",
    ),
    ("Foreground", "sdxl"): _layer_diffusion_weight(
        "layer_xl_fg2ble.safetensors",
        "50a29851ad56308f14d6c9ed375be17df6921efeca240b31f567f6b8c76d1e70",
        "model_patches",
    ),
    ("Foreground to Background", "sdxl"): _layer_diffusion_weight(
        "layer_xl_fgble2bg.safetensors",
        "179a61fdcdb149af1897b2840f24ba09466ab6265b2c792b0e99df557f0439be",
        "model_patches",
    ),
    ("Background", "sdxl"): _layer_diffusion_weight(
        "layer_xl_bg2ble.safetensors",
        "2901d1353cc4ca763c8bedc48453b36e88680605f417c7f7ec730a7c36845d7c",
        "model_patches",
    ),
    ("Background to Foreground", "sdxl"): _layer_diffusion_weight(
        "layer_xl_bgble2fg.safetensors",
        "1688f0c17447f74662686fadd431f24d26a1ba8ffea322c6f56c8b5ed581b78d",
        "model_patches",
    ),
}
_LAYER_DIFFUSION_DECODERS = {
    "sd1": _layer_diffusion_weight(
        "layer_sd15_vae_transparent_decoder.safetensors",
        "6df4712dfbb3783231b22f869a5da5cbfea782ebb05f782bd9e8744bfb0cdf03",
        "vae",
    ),
    "sdxl": _layer_diffusion_weight(
        "vae_transparent_decoder.safetensors",
        "59dc8feefe40d26b6cb7186aed7af70c60d94ac4f9db8ebe7f121a01ba27a2fc",
        "vae",
    ),
}
_LAYER_DIFFUSION_REQUIRED_WEIGHTS = tuple(dict.fromkeys(
    [*_LAYER_DIFFUSION_WEIGHTS.values(), *_LAYER_DIFFUSION_DECODERS.values()]
))

_SEGFORMER_PROFILES = {
    "segformer_b3_clothes": (
        sdk.HuggingFaceWeight(
            repo_id="sayeed99/segformer_b3_clothes",
            filename="model.safetensors",
            folder="semantic_segmentation",
            revision="6c12f0e4edd353fb65d4e3f9d90fdabaefea6d9e",
            sha256=(
                "f70ae566c5773fb335796ebaa8acc924ac25eb97222c2b2967d44d2fc11568e6"
            ),
            on_demand=True,
        ),
        "b3",
        18,
    ),
    "segformer_b3_fashion": (
        sdk.HuggingFaceWeight(
            repo_id="sayeed99/segformer-b3-fashion",
            filename="model.safetensors",
            folder="semantic_segmentation",
            revision="e2474a9e7643d349ac6c525549b736b736e7e216",
            sha256=(
                "f3f5b30179f1480d329224d089f6d286580142c2b12846d08de814a48a81f42f"
            ),
            on_demand=True,
        ),
        "b3",
        47,
    ),
    "face_parsing": (
        sdk.HuggingFaceWeight(
            repo_id="jonathandinu/face-parsing",
            filename="model.safetensors",
            folder="semantic_segmentation",
            revision="758b82e15a0178c9db39c1ff666a8b56e3a550c8",
            sha256=(
                "c2bec795a8c243db71bd95be538fd62559003566466c71237e45c99b920f4b62"
            ),
            on_demand=True,
        ),
        "b5",
        19,
    ),
}
_SEGFORMER_REQUIRED_WEIGHTS = tuple(
    profile[0] for profile in _SEGFORMER_PROFILES.values())

for _input in SCHEMAS["easy humanSegmentation"]["schema"]["inputs"]:
    if _input["attrs"]["id"] == "method":
        _input["attrs"]["options"] = list(_SEGFORMER_PROFILES)
        _input["attrs"]["default"] = "segformer_b3_clothes"
        break

_IMAGE_INTERROGATOR_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="Comfy-Org/Krea-2",
    filename="text_encoders/qwen3vl_4b_fp8_scaled.safetensors",
    folder="text_encoders",
    revision="e5ea8b4dd7f38f348b138eb0fe29f92c0e367e96",
    sha256=(
        "54bd5144df0bbc25dd6ccadfcb826b521445a1b06ae5a42570bdd2974ca87094"
    ),
    on_demand=True,
)

_SD3_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="Comfy-Org/stable-diffusion-3.5-fp8",
    filename="sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors",
    folder="checkpoints",
    revision="30c81ae3f16f4271e29824eda47f1de31b4d8422",
    sha256=(
        "1778e8857679042c176c21cd8a0da7b29bded68be018557477f84419df79bacf"
    ),
    on_demand=True,
)

_RT_DETR_WEIGHT = sdk.HuggingFaceWeight(
    repo_id="Comfy-Org/RT-DETR",
    filename="diffusion_models/rt_detr_v4-x-hgnet_fp16.safetensors",
    folder="diffusion_models",
    revision="0a2c5132e800b2bb51388984d9527dc02d6dcfab",
    sha256=(
        "581f9af9bbabb664d1891cbccd823308b176ecd409146f954dfa39af3bec2476"
    ),
    on_demand=True,
)

for _input in SCHEMAS["easy ultralyticsDetectorPipe"]["schema"]["inputs"]:
    if _input["attrs"]["id"] == "model_name":
        _input["attrs"]["options"] = ["RT-DETR v4 COCO (SafeTensor)"]
        _input["attrs"]["default"] = "RT-DETR v4 COCO (SafeTensor)"
        break

for _input in SCHEMAS["easy applyPowerPaint"]["schema"]["inputs"]:
    if _input["attrs"]["id"] == "powerpaint_model":
        _input["attrs"]["options"] = ["PowerPaint v2.1 (official)"]
        _input["attrs"]["default"] = "PowerPaint v2.1 (official)"
    elif _input["attrs"]["id"] == "powerpaint_clip":
        _input["attrs"]["options"] = ["PowerPaint token encoder (official)"]
        _input["attrs"]["default"] = "PowerPaint token encoder (official)"

for _node_id in {"easy instantIDApply", "easy instantIDApplyADV"}:
    for _input in SCHEMAS[_node_id]["schema"]["inputs"]:
        if _input["attrs"]["id"] == "instantid_file":
            _input["attrs"]["options"] = [
                "Secure portrait identity (CLIP Vision)"]
            _input["attrs"]["default"] = (
                "Secure portrait identity (CLIP Vision)")
        elif _input["attrs"]["id"] == "control_net_name":
            _input["attrs"]["options"] = [
                "None (optional input may supply ControlNet)"]
            _input["attrs"]["default"] = (
                "None (optional input may supply ControlNet)")

for _node_id in {"easy pulIDApply", "easy pulIDApplyADV"}:
    for _input in SCHEMAS[_node_id]["schema"]["inputs"]:
        if _input["attrs"]["id"] == "pulid_file":
            _input["attrs"]["options"] = [
                "Secure portrait identity (CLIP Vision)"]
            _input["attrs"]["default"] = (
                "Secure portrait identity (CLIP Vision)")


def _ctx():
    return sdk.ctx()


def _output_types(node_id: str) -> list[str]:
    return [item["io_type"] for item in SCHEMAS[node_id]["schema"]["outputs"]]


async def _raw(value: Any) -> Any:
    return await materialize(value)


async def _raw_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: await _raw(value) for key, value in kwargs.items()}


def _one(value: Any) -> tuple[Any]:
    return (value,)


def _first(value: Any) -> Any:
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return value[0]
    return value


def _safe_asset_name(value: Any) -> str:
    name = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or "://" in name
        or ":" in path.parts[0]
    ):
        raise ValueError("model and input names must come from a host catalogue")
    return path.as_posix()


_ASSET_CATALOGUES = {
    "input", "output", "temp", "checkpoints", "diffusion_models",
    "text_encoders", "clip", "clip_vision", "controlnet", "loras", "vae",
    "upscale_models",
}


def _asset_query(
    file_path: Any, file_name: Any, file_extension: Any,
) -> tuple[str, str]:
    directory = str(file_path or "").replace("\\", "/").strip()
    if not directory:
        raise ValueError("easy isFileExist needs file_path")
    filename = str(file_name or "").replace("\\", "/").strip()
    logical = (
        f"{directory.rstrip('/')}/{filename.lstrip('/')}"
        if filename else directory
    )
    extension = str(file_extension or "").strip().lstrip(".")
    if extension:
        if "/" in extension or "\\" in extension or "\x00" in extension:
            raise ValueError("easy isFileExist file_extension must be a suffix")
        logical += "." + extension
    name = _safe_asset_name(logical)
    parts = PurePosixPath(name).parts
    if len(parts) > 1 and parts[0] in _ASSET_CATALOGUES:
        return parts[0], PurePosixPath(*parts[1:]).as_posix()
    return "input", name


# -------------------------------------------------------------------------
# Safe arithmetic used by the two Easy formula nodes.
# -------------------------------------------------------------------------

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_}
_COMPARE = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_FUNCTIONS = {
    "abs": abs,
    "ceil": math.ceil,
    "floor": math.floor,
    "max": max,
    "min": min,
    "pow": pow,
    "round": round,
    "sqrt": math.sqrt,
}


def _formula(text: str, values: dict[str, Any]) -> Any:
    tree = ast.parse(str(text), mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(
            node.value, (int, float, bool)
        ):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return _BINARY[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](visit(node.operand))
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            operation = _COMPARE.get(type(node.ops[0]))
            if operation is not None:
                return operation(visit(node.left), visit(node.comparators[0]))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCTIONS
            and not node.keywords
        ):
            return _FUNCTIONS[node.func.id](*(visit(item) for item in node.args))
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) <= 4096:
            return [visit(item) for item in node.elts]
        raise ValueError(f"formula construct {type(node).__name__} is not allowed")

    return visit(tree)


# -------------------------------------------------------------------------
# Logic and flow/value nodes.
# -------------------------------------------------------------------------

async def _identity(**kwargs):
    for name in ("value", "seed", "positive", "negative", "anything", "any"):
        if name in kwargs:
            return _one(kwargs[name])
    return _one(next(iter(kwargs.values()), None))


async def _float(value, **_kwargs):
    return _one(round(float(value), 3))


async def _range_int(range_mode, start, stop, step, num_steps, end_mode, **_kwargs):
    range_mode, start, stop, step, num_steps, end_mode = map(
        _first, (range_mode, start, stop, step, num_steps, end_mode)
    )
    if range_mode == "step":
        if int(step) == 0:
            values = [int(start)]
        else:
            end = int(stop) + (1 if end_mode == "Inclusive" else 0)
            values = list(range(int(start), end, int(step)))
    else:
        count = max(0, int(num_steps))
        direction = 1 if stop > start else -1
        end = stop - direction if end_mode == "Exclusive" else stop
        values = np.rint(np.linspace(start, end, count)).astype(int).tolist()
    return values, [len(values)]


async def _range_float(range_mode, start, stop, step, num_steps, end_mode, **_kwargs):
    range_mode, start, stop, step, num_steps, end_mode = map(
        _first, (range_mode, start, stop, step, num_steps, end_mode)
    )
    getcontext().prec = 12
    start = Decimal(str(start))
    stop = Decimal(str(stop))
    step = Decimal(str(step))
    values: list[float] = []
    if range_mode == "step":
        if step == 0:
            values = [float(start)]
        else:
            limit = stop + step if end_mode == "Inclusive" else stop
            direction = 1 if step > 0 else -1
            value = start
            while (value - limit) * direction < 0:
                values.append(float(value))
                value += step
                if len(values) > 100000:
                    raise ValueError("Easy rangeFloat exceeded 100000 values")
    else:
        count = max(0, int(num_steps))
        if count == 1:
            values = [float(start)]
        elif count > 1:
            divisor = count - 1 if end_mode == "Inclusive" else count
            delta = (stop - start) / Decimal(divisor)
            values = [float(start + delta * index) for index in range(count)]
    return values, [len(values)]


async def _switch(index=0, **kwargs):
    for prefix in ("value", "image", "text", "cond"):
        key = f"{prefix}{int(index)}"
        if key in kwargs:
            return _one(kwargs.get(key))
    return _one(None)


def _index_switch_lazy(prefix):
    async def check(index=0, **kwargs):
        key = f"{prefix}{int(index)}"
        return [key] if kwargs.get(key) is None else []

    return check


async def _inverse_switch(index, **kwargs):
    value = kwargs.get("in")
    result = []
    for position in range(20):
        result.append(
            value if position == int(index) else await _ctx().graph.block()
        )
    return tuple(result)


async def _ab(**kwargs):
    value = kwargs.get("in")
    block = await _ctx().graph.block()
    return (value, block) if kwargs.get("A or B") else (block, value)


async def _image_switch(image_a, image_b, boolean, **_kwargs):
    return _one(image_a if boolean else image_b)


async def _text_switch(input, text1=None, text2=None, **_kwargs):
    return _one(text1 if int(input) == 1 else text2)


async def _math_int(a, b, operation, **_kwargs):
    operations = {
        "add": operator.add,
        "subtract": operator.sub,
        "multiply": operator.mul,
        "divide": operator.floordiv,
        "modulo": operator.mod,
        "power": operator.pow,
    }
    return _one(int(operations[operation](int(a), int(b))))


async def _math_float(a, b, operation, **_kwargs):
    operations = {
        "add": operator.add,
        "subtract": operator.sub,
        "multiply": operator.mul,
        "divide": operator.truediv,
        "modulo": operator.mod,
        "power": operator.pow,
    }
    return _one(round(float(operations[operation](float(a), float(b))), 3))


async def _math_string(a, b, operation, case_sensitive, **_kwargs):
    a, b = str(a), str(b)
    if not case_sensitive:
        a, b = a.lower(), b.lower()
    if operation == "a == b":
        value = a == b
    elif operation == "a != b":
        value = a != b
    elif operation == "a IN b":
        value = a in b
    elif operation == "a MATCH REGEX(b)":
        try:
            value = re.match(b, a) is not None
        except re.error:
            value = False
    elif operation == "a BEGINSWITH b":
        value = a.startswith(b)
    else:
        value = a.endswith(b)
    return _one(value)


async def _simple_math(value, a=0, b=0, c=0, **_kwargs):
    try:
        result = _formula(value, {"a": a, "b": b, "c": c})
        if isinstance(result, list):
            return [int(item) for item in result], result, [bool(item) for item in result]
        return int(result), float(result), bool(int(result))
    except Exception:
        return 0, 0.0, False


async def _simple_math_dual(value1, value2, a=0, b=0, c=0, d=0, **_kwargs):
    values = {"a": a, "b": b, "c": c, "d": d}
    results = []
    for expression in (value1, value2):
        try:
            value = _formula(expression, values)
            results.extend((int(value), float(value)))
        except Exception:
            results.extend((0, 0.0))
    return tuple(results)


async def _compare(a=0, b=0, comparison="a == b", **_kwargs):
    operations = {
        "a == b": lambda: a == b,
        "a != b": lambda: a != b,
        "a < b": lambda: a < b,
        "a > b": lambda: a > b,
        "a <= b": lambda: a <= b,
        "a >= b": lambda: a >= b,
        "a > 0": lambda: a > 0,
        "a <= 0": lambda: a <= 0,
        "b > 0": lambda: b > 0,
        "b <= 0": lambda: b <= 0,
    }
    return _one(bool(operations[comparison]()))


async def _if_else(boolean, on_true=None, on_false=None, **_kwargs):
    return _one(on_true if boolean else on_false)


async def _if_else_lazy(boolean=True, on_true=None, on_false=None, **_kwargs):
    key = "on_true" if bool(boolean) else "on_false"
    return [key] if (on_true if bool(boolean) else on_false) is None else []


async def _blocker(**kwargs):
    return _one(
        kwargs.get("in")
        if kwargs.get("continue") else await _ctx().graph.block()
    )


async def _mask_empty(mask, **_kwargs):
    value = await _raw(mask)
    return _one(value is None or not bool(torch.any(value != 0)))


async def _is_none(any, **_kwargs):
    value = await _raw(any)
    return _one(
        value is None
        or (isinstance(value, str) and value == "")
        or (isinstance(value, (int, float)) and value == 0)
    )


async def _is_sdxl(optional_pipe=None, optional_clip=None, **_kwargs):
    pipe = optional_pipe if isinstance(optional_pipe, dict) else {}
    settings = pipe.get("loader_settings", {})
    family = str(settings.get("model_type", settings.get("ckpt_name", ""))).lower()
    return _one("sdxl" in family or "xl" in PurePosixPath(family).name.lower())


async def _pixels(resolution, width, height, scale, **kwargs):
    if resolution not in ("自定义 x 自定义", "width x height (custom)"):
        try:
            width, height = map(int, str(resolution).split(" x ")[:2])
        except ValueError as error:
            raise ValueError("invalid Easy base resolution") from error
    width, height = float(width) * float(scale), float(height) * float(scale)
    width_norm, height_norm = int(width) // 8 * 8, int(height) // 8 * 8
    if kwargs.get("flip_w/h", False):
        width, height = height, width
        width_norm, height_norm = height_norm, width_norm
    return width_norm, height_norm, width, height, scale


async def _length(any, **_kwargs):
    value = await _raw(any)
    if value is None:
        return _one(0)
    return _one(len(value))


async def _index(any, index, **_kwargs):
    value = await _raw(any)
    if isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if value is None or len(value) == 0:
        return _one(None)
    position = max(-len(value), min(int(_first(index)), len(value) - 1))
    if isinstance(value, torch.Tensor):
        return _one(value[position:position + 1].clone())
    return _one(value[position])


async def _batch(any_1, any_2, **_kwargs):
    left, right = await _raw(any_1), await _raw(any_2)
    if left is None:
        return _one(right)
    if right is None:
        return _one(left)
    if isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor):
        if left.shape[1:] != right.shape[1:]:
            if left.ndim == 4 and left.shape[-1] in (1, 3, 4):
                right = common_upscale(
                    right.movedim(-1, 1), left.shape[2], left.shape[1],
                    "bilinear", "center"
                ).movedim(1, -1)
            else:
                right = common_upscale(
                    right, left.shape[-1], left.shape[-2], "bilinear", "center"
                )
        return _one(torch.cat((left, right), dim=0))
    if isinstance(left, dict) and isinstance(right, dict) and "samples" in left:
        result = dict(left)
        result["samples"] = torch.cat((left["samples"], right["samples"]), dim=0)
        return _one(result)
    if isinstance(left, list):
        return _one(left + (right if isinstance(right, list) else [right]))
    if isinstance(right, list):
        return _one(([left] + right))
    try:
        return _one(left + right)
    except TypeError:
        return _one([left, right])


async def _convert(**kwargs):
    value = await _raw(kwargs.get("*"))
    converters = {"string": str, "int": int, "float": float, "boolean": bool}
    return _one(converters[kwargs["output_type"]](value))


async def _show(anything=None, **_kwargs):
    value = await _raw(anything)
    if isinstance(value, list):
        display = [str(item) for item in value]
    elif isinstance(value, sdk.Ref):
        display = [f"<{value.kind} ref>"]
    else:
        try:
            display = [json.dumps(value, ensure_ascii=False)]
        except (TypeError, ValueError):
            display = [str(value)]
    result = display[0] if len(display) == 1 else display
    return {"ui": {"text": display}, "result": (result,)}


async def _show_shape(tensor, **_kwargs):
    value = await _raw(tensor)
    shapes = []

    def collect(item):
        if isinstance(item, dict):
            for nested in item.values():
                collect(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                collect(nested)
        elif hasattr(item, "shape"):
            shapes.append(list(item.shape))

    collect(value)
    return {"ui": {"text": shapes}, "result": ()}


def _graph_link(node, output):
    return {"node": str(node), "output": int(output)}


def _is_graph_link(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], (int, float))
    )


async def _while_start(condition, **kwargs):
    values = [kwargs.get(f"initial_value{i}") for i in range(20)]
    if not bool(condition):
        block = await _ctx().graph.block()
        values = [block] * 20
    return ("secure-loop-flow", *values)


async def _while_end(condition, **kwargs):
    values = [kwargs.get(f"initial_value{i}") for i in range(20)]
    if not bool(condition):
        return tuple(values)
    return await _ctx().graph.expand_loop(kwargs.get("flow"), values)


async def _for_start(total, **kwargs):
    total = int(total)
    index = int(kwargs.get("initial_value0") or 0)
    values = [kwargs.get(f"initial_value{i}") for i in range(1, 20)]
    if total <= 0:
        block = await _ctx().graph.block()
        return ("secure-loop-flow", *([block] * 20))
    return ("secure-loop-flow", index, *values)


async def _for_end(**kwargs):
    flow = kwargs.get("flow")
    if not _is_graph_link(flow) or int(flow[1]) != 0:
        raise ValueError("Easy for-loop flow must be the start node's raw link")
    start_id = str(flow[0])
    start = await _ctx().graph.widget_values(node_id=start_id)
    skipped = {
        f"initial_value{index}": start.get(f"initial_value{index}")
        for index in range(1, 20)
    }
    total = start.get("total")
    nodes = []
    if total is None and "directory" in start:
        nodes.append({
            "id": "count",
            "class_type": "easy imagesCountInDirectory",
            "inputs": {
                "directory": start.get("directory"),
                "limit": start.get("limit", 0),
                "start_index": start.get("start_index", 0),
                "extension": "*",
            },
        })
        total = _graph_link("count", 0)
        skipped = {}
    if total is None:
        raise ValueError("Easy for-loop start has no total or image directory")

    if skipped and not _is_graph_link(total) and int(total) <= 0:
        nodes.append({
            "id": "skip_close",
            "class_type": "easy whileLoopEnd",
            "inputs": {
                "flow": flow,
                "condition": False,
                "initial_value0": 0,
                **skipped,
            },
        })
        outputs = [
            _graph_link("skip_close", index) for index in range(1, 20)
        ]
        return await _ctx().graph.expand_nodes(nodes, outputs)

    nodes.extend([
        {
            "id": "next_index",
            "class_type": "easy mathInt",
            "inputs": {
                "operation": "add", "a": [start_id, 1], "b": 1,
            },
        },
        {
            "id": "continue_loop",
            "class_type": "easy compare",
            "inputs": {
                "a": _graph_link("next_index", 0),
                "b": total,
                "comparison": "a < b",
            },
        },
        {
            "id": "while_close",
            "class_type": "easy whileLoopEnd",
            "inputs": {
                "flow": flow,
                "condition": _graph_link("continue_loop", 0),
                "initial_value0": _graph_link("next_index", 0),
                **{
                    f"initial_value{index}": kwargs.get(
                        f"initial_value{index}")
                    for index in range(1, 20)
                },
            },
        },
    ])
    outputs = [
        _graph_link("while_close", index) for index in range(1, 20)
    ]
    if skipped and _is_graph_link(total):
        nodes.append({
            "id": "has_iterations",
            "class_type": "easy compare",
            "inputs": {"a": total, "b": 0, "comparison": "a > b"},
        })
        for index in range(1, 20):
            fallback = skipped[f"initial_value{index}"]
            if fallback is None:
                continue
            node_id = f"result_{index}"
            nodes.append({
                "id": node_id,
                "class_type": "easy ifElse",
                "inputs": {
                    "boolean": _graph_link("has_iterations", 0),
                    "on_true": _graph_link("while_close", index),
                    "on_false": fallback,
                },
            })
            outputs[index - 1] = _graph_link(node_id, 0)
    return await _ctx().graph.expand_nodes(nodes, outputs)


async def _xy_any(X, Y=None, direction="X", **_kwargs):
    x_values = list(X) if isinstance(X, (list, tuple)) else [X]
    y_values = list(Y) if isinstance(Y, (list, tuple)) else [Y]
    if direction == "X":
        return x_values * len(y_values), [item for item in y_values for _ in x_values]
    return [item for item in x_values for _ in y_values], y_values * len(x_values)


async def _save_text(text, file_name="text", file_extension="txt", image=None, **_kwargs):
    extension = ".csv" if file_extension == "csv" else ".txt"
    saved = await _ctx().output.save_text(
        str(text), filename_prefix=str(file_name or "text"), extension=extension
    )
    return {"ui": {"text": [saved]}, "result": (str(text), image)}


async def _is_file_exist(file_path, file_name="", file_extension="", **_kwargs):
    folder, name = _asset_query(file_path, file_name, file_extension)
    return _one(await _ctx().assets.exists(folder, name))


async def _sleep(any, delay, **_kwargs):
    delay = float(delay)
    if not 0 <= delay <= 60:
        raise ValueError("secure Easy sleep is bounded to 60 seconds")
    await asyncio.sleep(delay)
    return _one(any)


async def _string_to_int_list(string, **_kwargs):
    return _one([int(item.strip()) for item in str(string).split(",")])


async def _string_to_float_list(string, **_kwargs):
    return _one([float(item.strip()) for item in str(string).split(",")])


async def _string_join_lines(string, delimiter, **_kwargs):
    return _one(delimiter.join(
        line.strip() for line in str(string).splitlines() if line.strip()
    ))


async def _output_to_list(tuple, **_kwargs):
    return _one(tuple)


async def _clean_gpu(anything, **_kwargs):
    await _ctx().models.memory_cleanup(
        empty_cache=True, collect_cycles=True, unload_all_models=False
    )
    return _one(anything)


_LOGIC_HANDLERS = {
    "easy string": _identity,
    "easy int": _identity,
    "easy rangeInt": _range_int,
    "easy float": _float,
    "easy rangeFloat": _range_float,
    "easy boolean": _identity,
    "easy mathString": _math_string,
    "easy mathInt": _math_int,
    "easy mathFloat": _math_float,
    "easy simpleMath": _simple_math,
    "easy simpleMathDual": _simple_math_dual,
    "easy compare": _compare,
    "easy imageSwitch": _image_switch,
    "easy textSwitch": _text_switch,
    "easy imageIndexSwitch": _switch,
    "easy textIndexSwitch": _switch,
    "easy conditioningIndexSwitch": _switch,
    "easy anythingIndexSwitch": _switch,
    "easy ab": _ab,
    "easy anythingInversedSwitch": _inverse_switch,
    "easy whileLoopStart": _while_start,
    "easy whileLoopEnd": _while_end,
    "easy forLoopStart": _for_start,
    "easy forLoopEnd": _for_end,
    "easy xyAny": _xy_any,
    "easy blocker": _blocker,
    "easy ifElse": _if_else,
    "easy isMaskEmpty": _mask_empty,
    "easy isNone": _is_none,
    "easy isSDXL": _is_sdxl,
    "easy pixels": _pixels,
    "easy lengthAnything": _length,
    "easy indexAnything": _index,
    "easy batchAnything": _batch,
    "easy convertAnything": _convert,
    "easy showAnything": _show,
    "easy showTensorShape": _show_shape,
    "easy stringToIntList": _string_to_int_list,
    "easy stringToFloatList": _string_to_float_list,
    "easy stringJoinLines": _string_join_lines,
    "easy outputToList": _output_to_list,
    "easy cleanGpuUsed": _clean_gpu,
    "easy clearCacheKey": _identity,
    "easy clearCacheAll": _identity,
    "easy saveText": _save_text,
    "easy sleep": _sleep,
    "easy isFileExist": _is_file_exist,
}


# -------------------------------------------------------------------------
# Seed, prompt, and small utility nodes.
# -------------------------------------------------------------------------

async def _seed_list(min_num, max_num, method, total, seed=0, **_kwargs):
    minimum, maximum = sorted((int(min_num), int(max_num)))
    count = int(total)
    generator = random.Random(int(seed))
    if method == "random":
        values = [generator.randint(minimum, maximum) for _ in range(count)]
    elif method == "increment":
        values = [min(minimum + index, maximum) for index in range(count)]
    else:
        values = [max(maximum - index, minimum) for index in range(count)]
    return values, count


async def _no_output(**_kwargs):
    return ()


async def _wildcards(text, seed, multiline_mode=False, **_kwargs):
    catalogue = await _load_wildcard_catalogue(
        _ctx(), "easy_wildcards", style="easy"
    )
    source = str(text).split("\n") if multiline_mode else [str(text)]
    populated = [
        _populate_catalogue_wildcards(
            line, int(seed), catalogue, style="easy"
        )
        for line in source
    ]
    return {"ui": {"value": [seed]}, "result": (source, populated)}


async def _wildcards_matrix(text, offset, output_limit=1, **_kwargs):
    catalogue = await _load_wildcard_catalogue(
        _ctx(), "easy_wildcards", style="easy"
    )
    values, total, factors = _wildcard_matrix_values(
        str(text), catalogue, int(offset), int(output_limit)
    )
    return {"ui": {"value": [offset]}, "result": (values, total, factors)}


async def _prompt(text, **_kwargs):
    return _one(str(text))


async def _prompt_list(
    prompt_1="", prompt_2="", prompt_3="", prompt_4="", prompt_5="",
    optional_prompt_list=None, **_kwargs,
):
    prompts = list(optional_prompt_list or ())
    prompts.extend(
        value for value in (prompt_1, prompt_2, prompt_3, prompt_4, prompt_5)
        if isinstance(value, str) and value
    )
    return prompts, prompts


async def _prompt_line(prompt, start_index, max_rows, remove_empty_lines=True, **_kwargs):
    lines = str(prompt).splitlines()
    if remove_empty_lines:
        lines = [line for line in lines if line.strip()]
    if not lines:
        return [], []
    start = min(max(0, int(start_index)), len(lines) - 1)
    values = lines[start:start + int(max_rows)]
    return values, values


def _to_string(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(_to_string(item) for item in value)
    return str(value)


async def _prompt_concat(prompt1="", prompt2="", separator="", **_kwargs):
    return _one(_to_string(prompt1) + _to_string(separator) + _to_string(prompt2))


async def _prompt_replace(prompt, **kwargs):
    result = str(prompt)
    for index in range(1, 4):
        find = str(kwargs.get(f"find{index}", ""))
        if find:
            result = result.replace(find, str(kwargs.get(f"replace{index}", "")))
    return _one(result)


def _style_catalogue() -> dict[str, dict[str, Any]]:
    resource = __import__("pathlib").Path(__file__).with_name(
        "resources"
    ) / "fooocus_styles.json"
    try:
        return {
            item["name"]: item
            for item in json.loads(resource.read_text(encoding="utf-8"))
            if isinstance(item, dict) and "name" in item
        }
    except (OSError, ValueError, TypeError):
        return {}


async def _styles(positive="", negative="", select_styles=None, **_kwargs):
    selected = (
        [item.strip() for item in select_styles.split(",")]
        if isinstance(select_styles, str)
        else list(select_styles or ())
    )
    catalogue = _style_catalogue()
    positive_result, negative_result = str(positive), str(negative)
    for name in selected:
        style = catalogue.get(name)
        if not style:
            continue
        template = str(style.get("prompt", ""))
        positive_result = (
            template.replace("{prompt}", positive_result)
            if "{prompt}" in template
            else ", ".join(filter(None, (positive_result, template)))
        )
        negative_result = ", ".join(
            filter(None, (negative_result, str(style.get("negative_prompt", ""))))
        )
    return positive_result, negative_result


async def _portrait(prompt_start="", prompt_additional="", prompt_end="",
                    negative_prompt="", **kwargs):
    parts = [str(prompt_start)] if prompt_start else []
    # The upstream node is a deterministic prompt formatter. Keep every
    # meaningful non-default selection without importing its server helpers.
    for key, value in kwargs.items():
        if value in (None, "", "-", 0, 0.0, "none", "disable"):
            continue
        label = key.replace("_", " ")
        if isinstance(value, (int, float)):
            parts.append(f"({label}:{round(float(value), 2)})")
        else:
            parts.append(str(value))
    parts.extend(value for value in (prompt_additional, prompt_end) if value)
    return ", ".join(parts).lower(), str(negative_prompt)


def _angle_prompt(item: dict[str, Any]) -> str:
    rotate = max(0, min(360, int(item.get("rotate", 0))))
    vertical = max(-90, min(90, int(item.get("vertical", 0))))
    zoom = max(0.0, min(10.0, float(item.get("zoom", 5))))
    horizontal = (
        "front view" if rotate < 22.5 or rotate >= 337.5 else
        "front-right view" if rotate < 67.5 else
        "right side view" if rotate < 112.5 else
        "back-right view" if rotate < 157.5 else
        "back view" if rotate < 202.5 else
        "back-left view" if rotate < 247.5 else
        "left side view" if rotate < 292.5 else "front-left view"
    )
    vertical_text = (
        "low angle" if vertical < -15 else
        "eye level" if vertical < 15 else
        "high angle" if vertical < 75 else "top-down perspective"
    )
    distance = (
        "extreme wide shot" if zoom < 2 else "wide shot" if zoom < 4 else
        "medium shot" if zoom < 6 else "close-up" if zoom < 8 else
        "extreme close-up"
    )
    return f"{horizontal}, {vertical_text}, {distance} (horizontal: {rotate}, vertical: {vertical}, zoom: {zoom:.1f})"


async def _multi_angle(multi_angle=None, **_kwargs):
    if multi_angle is None:
        return ([""], None)
    if isinstance(multi_angle, str):
        multi_angle = json.loads(multi_angle)
    values = list(multi_angle)
    return [_angle_prompt(item) for item in values], values


async def _prompt_await(now, prompt, toolbar=None, prev=None, **_kwargs):
    settings = toolbar
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except json.JSONDecodeError:
            settings = None
    if not isinstance(settings, dict):
        settings = {}
    response = await _ctx().interact.request(
        "prompt-await",
        {
            "prompt": str(prompt),
            "has_prev": prev is not None,
            "select": str(settings.get("select", "now")),
            "unlock": bool(settings.get("unlock", True)),
            "last_seed": int(settings.get("last_seed", 0)),
            "seed": int(settings.get("seed", 0)),
        },
    )
    if not isinstance(response, dict) or response.get("cancelled"):
        return now, str(prompt), False, 0
    selected = (
        prev
        if response.get("select") == "prev" and prev is not None else now
    )
    unlocked = bool(response.get("unlock", False))
    seed = int(response.get("seed" if unlocked else "last_seed", 0))
    return (
        selected,
        str(response.get("prompt", prompt)),
        int(response.get("result", -1)) != -1,
        seed,
    )


async def _loader_names(pipe, **_kwargs):
    settings = (pipe or {}).get("loader_settings", {})
    values = []
    for key in ("ckpt_name", "vae_name", "lora_name"):
        value = PurePosixPath(str(settings.get(key, "")).replace("\\", "/")).stem
        values.append(value)
    return {"ui": {"text": ["\n".join(values)]}, "result": tuple(values)}


async def _name_value(**kwargs):
    for key in ("ckpt_name", "controlnet_name", "lora_name"):
        if key in kwargs:
            return _one(kwargs[key])
    return _one(None)


async def _slider_control(**kwargs):
    return _one(str(kwargs.get("values", "")))


def _markdown_image(markdown: str) -> torch.Tensor:
    lines = str(markdown or "").splitlines() or [""]
    font = ImageFont.load_default()
    width = max(400, min(1600, max(len(line) for line in lines) * 8 + 24))
    height = max(80, min(4096, len(lines) * 18 + 24))
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines[:220]):
        draw.text((12, 12 + index * 18), line, font=font, fill="black")
    array = np.asarray(image).astype(np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


async def _table_editor(table_data=None, **_kwargs):
    if isinstance(table_data, str):
        markdown = table_data
    elif table_data is None:
        markdown = ""
    else:
        markdown = str(table_data.get("markdown", "")) if isinstance(table_data, dict) else str(table_data)
    return markdown, _markdown_image(markdown)


_PROMPT_HANDLERS = {
    "easy positive": _identity,
    "easy negative": _identity,
    "easy wildcards": _wildcards,
    "easy wildcardsMatrix": _wildcards_matrix,
    "easy prompt": _prompt,
    "easy promptList": _prompt_list,
    "easy promptLine": _prompt_line,
    "easy promptAwait": _prompt_await,
    "easy promptConcat": _prompt_concat,
    "easy promptReplace": _prompt_replace,
    "easy stylesSelector": _styles,
    "easy portraitMaster": _portrait,
    "easy multiAngle": _multi_angle,
}

_SEED_HANDLERS = {
    "easy seed": _identity,
    "easy seedList": _seed_list,
    "easy globalSeed": _no_output,
}

_UTIL_HANDLERS = {
    "easy showLoaderSettingsNames": _loader_names,
    "easy sliderControl": _slider_control,
    "easy ckptNames": _name_value,
    "easy controlnetNames": _name_value,
    "easy loraNames": _name_value,
    "easy tableEditor": _table_editor,
}


# -------------------------------------------------------------------------
# Pure image operations and brokered input/output.
# -------------------------------------------------------------------------

async def _image_count(images, **_kwargs):
    value = await _raw(images)
    return _one(int(value.shape[0]))


async def _image_inset_crop(image, measurement, left, right, top, bottom, **_kwargs):
    value = await _raw(image)
    _, height, width, _ = value.shape
    if measurement == "Percentage":
        left = int(width * float(left) / 100)
        right = int(width * float(right) / 100)
        top = int(height * float(top) / 100)
        bottom = int(height * float(bottom) / 100)
    left, right, top, bottom = (int(item) // 8 * 8 for item in (left, right, top, bottom))
    x1, x2 = left, width - right
    y1, y2 = top, height - bottom
    if x1 >= x2 or y1 >= y2:
        raise ValueError("Easy image inset crop removed the entire image")
    return _one(value[:, y1:y2, x1:x2, :])


async def _image_size(image, **_kwargs):
    value = await _raw(image)
    width, height = int(value.shape[2]), int(value.shape[1])
    return {"ui": {"text": [f"Width: {width} , Height: {height}"]}, "result": (width, height)}


async def _image_side(image, side="Longest", **_kwargs):
    value = await _raw(image)
    dimensions = (int(value.shape[2]), int(value.shape[1]))
    result = max(dimensions) if side == "Longest" else min(dimensions)
    return {"ui": {"text": [str(result)]}, "result": (result,)}


async def _image_long_side(image, **_kwargs):
    return await _image_side(image, "Longest")


def _scale_image(value: torch.Tensor, width: int, height: int, crop: str,
                 method: str = "lanczos") -> torch.Tensor:
    return common_upscale(
        value.movedim(-1, 1), max(1, int(width)), max(1, int(height)), method, crop
    ).movedim(1, -1)


async def _image_scale_down(images, width, height, crop, **_kwargs):
    value = await _raw(images)
    return _one(_scale_image(value, int(width), int(height), crop))


async def _image_scale_down_by(images, scale_by, **_kwargs):
    value = await _raw(images)
    width = max(1, int(value.shape[2] * float(scale_by)))
    height = max(1, int(value.shape[1] * float(scale_by)))
    return _one(_scale_image(value, width, height, "center"))


async def _image_scale_to_size(images, size, mode, **_kwargs):
    value = await _raw(images)
    divisor = max(value.shape[1:3]) if mode else min(value.shape[1:3])
    factor = min(float(size) / divisor, 1.0)
    return _one(_scale_image(
        value, max(1, int(value.shape[2] * factor)),
        max(1, int(value.shape[1] * factor)), "center"
    ))


async def _image_scale_norm(image, upscale_method, scale_by, **_kwargs):
    value = await _raw(image)
    width = max(8, int(value.shape[2] * float(scale_by)) // 8 * 8)
    height = max(8, int(value.shape[1] * float(scale_by)) // 8 * 8)
    return _one(_scale_image(value, width, height, "disabled", upscale_method))


async def _image_ratio(image, **_kwargs):
    value = await _raw(image)
    width, height = int(value.shape[2]), int(value.shape[1])
    divisor = math.gcd(width, height)
    x, y = width // divisor, height // divisor
    return {"ui": {"text": [f"Image Ratio is {x}:{y}"]}, "result": (x, y, float(x), float(y))}


async def _pixel_perfect(image, **_kwargs):
    value = await _raw(image)
    result = int(min(value.shape[1], value.shape[2]))
    return {"ui": {"text": [str(result)]}, "result": (result,)}


async def _join_image_batch(images, mode, **_kwargs):
    value = await _raw(images)
    count, height, width, channels = value.shape
    if mode == "vertical":
        result = value.reshape(1, count * height, width, channels)
    else:
        result = value.permute(0, 2, 1, 3).reshape(1, count * width, height, channels).permute(0, 2, 1, 3)
    return _one(result)


async def _image_list_to_batch(images, **_kwargs):
    values = await _raw(images)
    if isinstance(values, torch.Tensor):
        return _one(values)
    if not values:
        raise ValueError("Easy image list cannot be empty")
    target_height, target_width = values[0].shape[1:3]
    normalized = []
    for value in values:
        if value.shape[1:3] != (target_height, target_width):
            value = _scale_image(value, target_width, target_height, "center")
        normalized.append(value)
    return _one(torch.cat(normalized, dim=0))


async def _image_batch_to_list(image, **_kwargs):
    value = await _raw(image)
    return _one([value[index:index + 1] for index in range(len(value))])


async def _image_split_list(images, **_kwargs):
    value = await _raw(images)
    groups: list[list[torch.Tensor]] = [[], [], []]
    divisor = 3 if len(value) % 3 == 0 else 2 if len(value) % 2 == 0 else 1
    for index in range(len(value)):
        groups[index % divisor].append(value[index:index + 1])
    outputs = [torch.cat(group, dim=0) if group else None for group in groups]
    return tuple(outputs)


async def _image_split_grid(images, row, column, **_kwargs):
    value = await _raw(images)
    row, column = int(row), int(column)
    tile_height, tile_width = value.shape[1] // row, value.shape[2] // column
    tiles = [
        value[:, y * tile_height:(y + 1) * tile_height,
              x * tile_width:(x + 1) * tile_width, :]
        for y in range(row) for x in range(column)
    ]
    return _one(torch.cat(tiles, dim=0))


def _feather_mask(height: int, width: int, left: int, top: int) -> torch.Tensor:
    mask = torch.ones((height, width), dtype=torch.float32)
    if left > 0:
        mask[:, :left] *= torch.linspace(0, 1, left)
    if top > 0:
        mask[:top, :] *= torch.linspace(0, 1, top).unsqueeze(1)
    return mask


async def _image_split_tiles(
    image, overlap_ratio, overlap_offset, tiles_rows, tiles_cols, norm=True,
    **_kwargs,
):
    value = await _raw(image)
    height, width = value.shape[1:3]
    rows, cols = int(tiles_rows), int(tiles_cols)
    tile_width, tile_height = width // cols, height // rows
    overlap_width = min(tile_width // 2, int(tile_width * float(overlap_ratio)) + int(overlap_offset))
    overlap_height = min(tile_height // 2, int(tile_height * float(overlap_ratio)) + int(overlap_offset))
    overlap_width, overlap_height = max(0, overlap_width), max(0, overlap_height)
    if norm:
        overlap_width, overlap_height = overlap_width // 8 * 8, overlap_height // 8 * 8
    if rows == 1:
        overlap_height = 0
    if cols == 1:
        overlap_width = 0
    tiles, masks = [], []
    for row in range(rows):
        for col in range(cols):
            y1 = row * tile_height - (overlap_height if row else 0)
            x1 = col * tile_width - (overlap_width if col else 0)
            y2 = min(height, y1 + tile_height + overlap_height)
            x2 = min(width, x1 + tile_width + overlap_width)
            y1, x1 = max(0, y2 - tile_height - overlap_height), max(0, x2 - tile_width - overlap_width)
            tile = value[:, y1:y2, x1:x2, :]
            tiles.append(tile)
            masks.append(_feather_mask(
                tile.shape[1], tile.shape[2], overlap_width if col else 0,
                overlap_height if row else 0,
            ))
    overlap = (overlap_width, overlap_height, tile_width, tile_height, rows, cols)
    return torch.cat(tiles), torch.stack(masks), overlap, rows * cols


async def _tile_from_batch(tiles, masks, overlap, index, **_kwargs):
    tile_values, mask_values = await _raw(tiles), await _raw(masks)
    position = min(max(0, int(index)), len(tile_values) - 1)
    overlap_width, overlap_height, tile_width, tile_height, rows, cols = overlap
    x = tile_width * (position % cols) - (overlap_width if position % cols else 0)
    y = tile_height * (position // cols) - (overlap_height if position >= cols else 0)
    return tile_values[position:position + 1].clone(), mask_values[position:position + 1].clone(), x, y


async def _split_five(images, **_kwargs):
    value = await _raw(images)
    chunks = [value[index:index + 1].clone() for index in range(min(5, len(value)))]
    return tuple(chunks + [None] * (5 - len(chunks)))


async def _image_concat(image1, image2, direction, match_image_size, **_kwargs):
    left, right = await _raw(image1), await _raw(image2)
    if match_image_size:
        if direction in ("right", "left"):
            width = max(1, round(right.shape[2] * left.shape[1] / right.shape[1]))
            right = _scale_image(right, width, left.shape[1], "disabled")
        else:
            height = max(1, round(right.shape[1] * left.shape[2] / right.shape[2]))
            right = _scale_image(right, left.shape[2], height, "disabled")
    dimension = 2 if direction in ("right", "left") else 1
    values = (right, left) if direction in ("left", "up") else (left, right)
    return _one(torch.cat(values, dim=dimension))


def _ic_pil(value: torch.Tensor, mode: str) -> Image.Image:
    array = np.clip(
        torch.as_tensor(value).detach().cpu().numpy().squeeze() * 255.0,
        0,
        255,
    ).astype(np.uint8)
    return Image.fromarray(array).convert(mode)


def _ic_fit_resize(
    image: Image.Image, width: int, height: int, fit: str, mode: str
) -> Image.Image:
    image = image.convert(mode)
    source_width, source_height = image.size
    width, height = max(1, int(width)), max(1, int(height))
    if fit == "crop":
        if source_width / source_height > width / height:
            crop_width = int(source_height * width / height)
            left = (source_width - crop_width) // 2
            image = image.crop((left, 0, left + crop_width, source_height))
        else:
            crop_height = int(source_width * height / width)
            top = (source_height - crop_height) // 2
            image = image.crop((0, top, source_width, top + crop_height))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _ic_resize_pair(
    image: torch.Tensor,
    mask: torch.Tensor | None,
    width: int,
    height: int,
    fit: str = "fill",
) -> tuple[torch.Tensor, torch.Tensor | None]:
    images = []
    for item in image:
        resized = _ic_fit_resize(_ic_pil(item, "RGB"), width, height, fit, "RGB")
        images.append(torch.from_numpy(np.asarray(resized).copy()).float().div(255).unsqueeze(0))

    masks = []
    if mask is not None:
        value = torch.as_tensor(mask)
        if value.ndim == 2:
            value = value.unsqueeze(0)
        for item in value:
            resized = _ic_fit_resize(_ic_pil(item, "L"), width, height, fit, "L")
            masks.append(torch.from_numpy(np.asarray(resized).copy()).float().div(255).unsqueeze(0))

    return torch.cat(images), torch.cat(masks) if masks else None


def _ic_filled_mask(
    width: int,
    height: int,
    mask: torch.Tensor,
    position: tuple[int, int] = (0, 0),
) -> torch.Tensor:
    foreground = _ic_pil(mask, "L")
    canvas = Image.new("L", (int(width), int(height)), 0)
    # Upstream deliberately uses the mask as both source and alpha channel.
    canvas.paste(foreground, position, foreground)
    return torch.from_numpy(np.asarray(canvas).copy()).float().div(255).unsqueeze(0)


async def _make_image_for_ic_lora(
    image_1,
    direction,
    pixels,
    method,
    image_2=None,
    mask_1=None,
    mask_2=None,
    **_kwargs,
):
    first = torch.as_tensor(await _raw(image_1)).float()
    second = (
        torch.as_tensor(await _raw(image_2)).float()
        if image_2 is not None
        else torch.zeros_like(first)
    )
    first_mask = await _raw(mask_1) if mask_1 is not None else None
    second_mask = await _raw(mask_2) if mask_2 is not None else None
    if second_mask is None:
        second_mask = torch.ones(
            (1, second.shape[1], second.shape[2]), dtype=torch.float32
        )

    pixels = int(pixels)
    if pixels > 0:
        second_height, second_width = second.shape[1:3]
        if method == "uniform height":
            height = pixels
            width = int(second_width * pixels / second_height)
        elif method == "uniform width":
            width = pixels
            height = int(second_height * pixels / second_width)
        else:
            height = (
                pixels
                if direction == "left-right"
                else int(second_height * pixels / second_width)
            )
            width = (
                pixels
                if direction == "top-bottom"
                else int(second_width * pixels / second_height)
            )
        second, second_mask = _ic_resize_pair(
            second, torch.as_tensor(second_mask), width, height
        )

    first_height, first_width = first.shape[1:3]
    second_height, second_width = second.shape[1:3]
    if first_height != second_height and first_width != second_width:
        width, height = second_width, second_height
        fit = "crop"
        if method != "uniform width":
            if direction == "left-right" and first_height != second_height:
                width = round(first_width * second_height / first_height)
            elif direction == "top-bottom" and first_width != second_width:
                height = round(first_height * second_width / first_width)
            fit = "fill"
        first, first_mask = _ic_resize_pair(
            first,
            torch.as_tensor(first_mask) if first_mask is not None else None,
            width,
            height,
            fit,
        )

    if first_mask is None:
        first_mask = torch.zeros(
            (1, first.shape[1], first.shape[2]), dtype=torch.float32
        )
    else:
        first_mask = torch.as_tensor(first_mask).float()
        if first_mask.ndim == 2:
            first_mask = first_mask.unsqueeze(0)

    # tensor2pil -> pil2tensor in upstream quantizes image_1 before joining.
    first_pil = _ic_pil(first, "RGB")
    first_mask_pil = _ic_pil(first_mask, "L")
    if first_mask_pil.size != first_pil.size:
        first_mask_pil = first_mask_pil.resize(first_pil.size)
    first = torch.from_numpy(np.asarray(first_pil).copy()).float().div(255).unsqueeze(0)
    first_mask = torch.from_numpy(np.asarray(first_mask_pil).copy()).float().div(255).unsqueeze(0)

    dimension = 2 if direction == "left-right" else 1
    image = torch.cat((first, second), dim=dimension)
    x = int(first.shape[2]) if direction == "left-right" else 0
    y = int(first.shape[1]) if direction == "top-bottom" else 0
    context_mask = _ic_filled_mask(image.shape[2], image.shape[1], first_mask)
    mask = _ic_filled_mask(
        image.shape[2], image.shape[1], torch.as_tensor(second_mask), (x, y)
    )
    return image, mask, context_mask, int(second_width), int(second_height), x, y


async def _image_save(images, filename_prefix="ComfyUI", only_preview=False, **_kwargs):
    if only_preview:
        display = await _ctx().ui.preview_images(images)
    else:
        display = await _ctx().output.save_images(images, filename_prefix=str(filename_prefix))
    return {"ui": display, "result": ()}


async def _image_chooser(
    images=None, mode="Always Pause", preview_rescale=1.0, **_kwargs,
):
    if images is None:
        return _one(torch.zeros((1, 1, 1, 3), dtype=torch.float32))
    value = await _raw(images)
    if isinstance(value, (list, tuple)):
        value = torch.cat([torch.as_tensor(item) for item in value], dim=0)
    value = torch.as_tensor(value)
    if value.ndim != 4 or len(value) == 0:
        raise ValueError("easy imageChooser needs a non-empty IMAGE batch")

    scale = float(preview_rescale)
    if not 0.05 <= scale <= 1.0:
        raise ValueError("preview_rescale must be in [0.05, 1.0]")
    preview = value
    if scale < 1.0:
        preview = _scale_image(
            value,
            max(1, int(value.shape[2] * scale)),
            max(1, int(value.shape[1] * scale)),
            "center",
        )
    preview_ref = await sdk.ImageRef._from_raw(preview)
    display = await _ctx().ui.preview_images(preview_ref)
    response = await _ctx().interact.request(
        "image-choice",
        {"images": list(display.get("images", ())), "count": len(value)},
        reuse_last=str(mode) == "Keep Last Selection",
        remember=True,
    )
    if not isinstance(response, dict) or response.get("cancelled"):
        raise RuntimeError("image selection was cancelled")
    selected = response.get("selected", [])
    if not isinstance(selected, list):
        raise TypeError("image selection must be an index list")
    indices = [
        index for index in selected
        if isinstance(index, int) and not isinstance(index, bool)
        and 0 <= index < len(value)
    ]
    if not indices:
        indices = [0]
    return _one(torch.cat([value[index:index + 1] for index in indices]))


async def _color_match(image_ref, image_target, **_kwargs):
    reference, target = await _raw(image_ref), await _raw(image_target)
    reference = reference[:1]
    ref_mean = reference.mean(dim=(1, 2), keepdim=True)
    ref_std = reference.std(dim=(1, 2), keepdim=True).clamp_min(1e-6)
    target_mean = target.mean(dim=(1, 2), keepdim=True)
    target_std = target.std(dim=(1, 2), keepdim=True).clamp_min(1e-6)
    return _one(((target - target_mean) / target_std * ref_std + ref_mean).clamp(0, 1))


async def _detail_transfer(target, source, blend_factor, mask=None, **_kwargs):
    target_value, source_value = await _raw(target), await _raw(source)
    if target_value.shape[1:3] != source_value.shape[1:3]:
        source_value = _scale_image(source_value, target_value.shape[2], target_value.shape[1], "disabled")
    detail = source_value - torch.nn.functional.avg_pool2d(
        source_value.movedim(-1, 1), 5, stride=1, padding=2
    ).movedim(1, -1)
    result = (target_value + detail * float(blend_factor)).clamp(0, 1)
    if mask is not None:
        mask_value = await _raw(mask)
        while mask_value.ndim < result.ndim:
            mask_value = mask_value.unsqueeze(-1)
        result = result * mask_value + target_value * (1 - mask_value)
    return _one(result)


async def _crop_from_mask(image, mask, image_crop_multi, mask_crop_multi,
                          bbox_smooth_alpha=1.0, **_kwargs):
    images, masks = await _raw(image), await _raw(mask)
    if masks.ndim == 2:
        masks = masks.unsqueeze(0)
    cropped_images, cropped_masks, boxes = [], [], []
    for index in range(len(images)):
        selected = masks[min(index, len(masks) - 1)]
        points = torch.nonzero(selected > 0, as_tuple=False)
        if not len(points):
            y1, x1, y2, x2 = 0, 0, images.shape[1], images.shape[2]
        else:
            y1, x1 = points.min(dim=0).values.tolist()
            y2, x2 = (points.max(dim=0).values + 1).tolist()
            center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
            width = max(1, round((x2 - x1) * float(image_crop_multi)))
            height = max(1, round((y2 - y1) * float(image_crop_multi)))
            x1, x2 = max(0, round(center_x - width / 2)), min(images.shape[2], round(center_x + width / 2))
            y1, y2 = max(0, round(center_y - height / 2)), min(images.shape[1], round(center_y + height / 2))
        cropped_images.append(images[index:index + 1, y1:y2, x1:x2, :])
        cropped_masks.append(selected.unsqueeze(0)[:, y1:y2, x1:x2])
        boxes.append((x1, y1, x2 - x1, y2 - y1))
    target_height = max(item.shape[1] for item in cropped_images)
    target_width = max(item.shape[2] for item in cropped_images)
    cropped_images = [_scale_image(item, target_width, target_height, "disabled") for item in cropped_images]
    cropped_masks = [
        common_upscale(item.unsqueeze(1), target_width, target_height, "bilinear", "disabled").squeeze(1)
        for item in cropped_masks
    ]
    return torch.cat(cropped_images), torch.cat(cropped_masks), boxes


async def _uncrop(original_image, crop_image, bbox, border_blending,
                  use_square_mask, optional_mask=None, **_kwargs):
    originals, crops = await _raw(original_image), await _raw(crop_image)
    result = originals.clone()
    boxes = bbox if isinstance(bbox, (list, tuple)) and bbox and isinstance(bbox[0], (list, tuple)) else [bbox]
    optional = await _raw(optional_mask) if optional_mask is not None else None
    for index in range(min(len(result), len(crops), len(boxes))):
        x, y, width, height = map(int, boxes[index])
        width, height = min(width, result.shape[2] - x), min(height, result.shape[1] - y)
        resized = _scale_image(crops[index:index + 1], width, height, "disabled")[0]
        if optional is not None and not use_square_mask:
            blend = common_upscale(
                optional[min(index, len(optional) - 1):min(index, len(optional) - 1) + 1].unsqueeze(1),
                width, height, "bilinear", "disabled"
            )[0, 0].unsqueeze(-1)
        else:
            feather = max(0, round(min(width, height) * float(border_blending) / 2))
            blend = _feather_mask(height, width, feather, feather)
            blend = torch.minimum(blend, blend.flip(0)).minimum(blend.flip(1)).unsqueeze(-1)
        target = result[index, y:y + height, x:x + width, :]
        result[index, y:y + height, x:x + width, :] = resized * blend + target * (1 - blend)
    return _one(result)


def _pil_tensor(image: Image.Image) -> tuple[torch.Tensor, torch.Tensor]:
    rgba = np.asarray(image.convert("RGBA")).astype(np.float32) / 255.0
    pixels = torch.from_numpy(rgba[..., :3].copy()).unsqueeze(0)
    mask = torch.from_numpy(rgba[..., 3].copy()).unsqueeze(0)
    return pixels, mask


async def _load_base64(base64_data, image_output="Hide", save_prefix="ComfyUI", **_kwargs):
    payload = str(base64_data)
    if "," in payload and payload.lstrip().startswith("data:"):
        payload = payload.split(",", 1)[1]
    data = base64.b64decode(payload, validate=True)
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("base64 image exceeds 64 MiB")
    pixels, mask = _pil_tensor(Image.open(bytes_io.BytesIO(data)))
    image_ref = await sdk.ImageRef._from_raw(pixels)
    ui = {}
    if image_output in ("Save", "Hide/Save"):
        ui = await _ctx().output.save_images(image_ref, filename_prefix=save_prefix)
    elif image_output == "Preview":
        ui = await _ctx().ui.preview_images(image_ref)
    return {"ui": ui, "result": (pixels, mask)}


async def _image_to_base64(image, **_kwargs):
    value = await _raw(image)
    array = np.clip(value[0].detach().cpu().numpy() * 255, 0, 255).astype(np.uint8)
    output = bytes_io.BytesIO()
    Image.fromarray(array).save(output, format="PNG")
    return _one(base64.b64encode(output.getvalue()).decode("ascii"))


async def _remove_background(
    images, rem_mode, image_output, save_prefix,
    add_background="none", **_kwargs,
):
    mode = str(rem_mode)
    if mode not in {"RMBG-2.0", "RMBG-1.4", "Inspyrenet", "BEN2"}:
        raise ValueError(f"unknown easy imageRemBg mode {mode!r}")
    # All upstream choices express the same foreground-matting behavior.  The
    # secure conversion deliberately serves that behavior through ComfyUI's
    # one canonical SafeTensor background-removal model instead of importing
    # four pack-specific remote-code engines.
    names = await _ctx().assets.list("background_removal")
    candidates = [
        name for name in names
        if name.lower().endswith((".safetensors", ".sft"))
        and "rmbg-2.0" in name.lower().replace("_", "-")
    ]
    if not candidates:
        raise FileNotFoundError(
            "easy imageRemBg needs the official RMBG-2.0 model.safetensors "
            "under ComfyUI's background_removal model catalogue")
    weight = sorted(candidates, key=lambda name: (len(name), name))[0]
    remover = await _ctx().models.load_background_removal_model(weight)
    foreground_mask = await remover.mask(images)

    pixels = (await _raw(images)).detach().cpu().float()[..., :3]
    alpha = (await _raw(foreground_mask)).detach().cpu().float().clamp(0, 1)
    if tuple(alpha.shape) != tuple(pixels.shape[:3]):
        raise RuntimeError("background-removal mask does not match its image")
    background = str(add_background)
    if background == "none":
        output = torch.cat((pixels, alpha.unsqueeze(-1)), dim=-1)
    elif background in {"white", "black"}:
        fill = 1.0 if background == "white" else 0.0
        output = pixels * alpha.unsqueeze(-1) + fill * (
            1.0 - alpha.unsqueeze(-1))
    else:
        raise ValueError("add_background must be none, white, or black")
    output_ref = await sdk.ImageRef._from_raw(output)

    ui = {}
    output_mode = str(image_output)
    if output_mode in {"Save", "Hide/Save"}:
        if background == "none":
            rgb_ref = await sdk.ImageRef._from_raw(pixels)
            transparent = await sdk.MaskRef._from_raw(1.0 - alpha)
            ui = await _ctx().output.save_images_with_alpha(
                rgb_ref, transparent, filename_prefix=str(save_prefix))
        else:
            ui = await _ctx().output.save_images(
                output_ref, filename_prefix=str(save_prefix))
    elif output_mode == "Preview":
        ui = await _ctx().ui.preview_images(output_ref)
    return {"ui": ui, "result": (output_ref, foreground_mask)}


_SEGMENTATION_UNAVAILABLE_PROFILES = {
    "selfie_multiclass_256x256": (
        "its published model is a TFLite execution graph, not a SafeTensor "
        "weight"
    ),
    "human_parsing_lip": (
        "its published model is an ONNX execution graph, not a SafeTensor "
        "weight"
    ),
    "human_parts (deeplabv3p)": (
        "its published model is an ONNX execution graph, not a SafeTensor "
        "weight"
    ),
}


def _segmentation_classes(mask_components) -> list[int]:
    if mask_components is None or mask_components == "":
        return []
    if isinstance(mask_components, str):
        values = [
            value.strip() for value in mask_components.split(",")
            if value.strip()
        ]
    elif isinstance(mask_components, (list, tuple, set)):
        values = list(mask_components)
    else:
        values = [mask_components]
    if len(values) > 64:
        raise ValueError("easy humanSegmentation accepts at most 64 classes")
    result = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError(
                "easy humanSegmentation class IDs must be integers")
        try:
            class_id = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "easy humanSegmentation class IDs must be integers") from error
        if class_id not in result:
            result.append(class_id)
    return result


async def _human_segmentation(
    image, method, confidence, crop_multi, mask_components,
    **_kwargs,
):
    method = str(method)
    unavailable = _SEGMENTATION_UNAVAILABLE_PROFILES.get(method)
    if unavailable is not None:
        raise RuntimeError(
            f"easy humanSegmentation has no weight-only implementation for "
            f"{method!r}: {unavailable}; choose one of the SafeTensor "
            "SegFormer profiles"
        )
    profile = _SEGFORMER_PROFILES.get(method)
    if profile is None:
        raise ValueError(
            f"unknown easy humanSegmentation method {method!r}")
    confidence = float(confidence)
    crop_multi = float(crop_multi)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("easy humanSegmentation confidence must be in [0, 1]")
    if not math.isfinite(crop_multi) or not 0.0 <= crop_multi <= 10.0:
        raise ValueError("easy humanSegmentation crop_multi must be in [0, 10]")

    pixels = (await _raw(image)).detach().cpu().float()
    if pixels.ndim != 4 or pixels.shape[-1] < 3:
        raise ValueError("easy humanSegmentation needs a BHWC RGB image")
    classes = _segmentation_classes(mask_components)
    if classes:
        weight, variant, num_labels = profile
        logical = await _download_declared_weight(weight)
        segmenter = await _ctx().models.load_segformer(
            logical, variant=variant, num_labels=num_labels)
        mask = (await _raw(
            await segmenter.mask(image, classes)
        )).detach().cpu().float().clamp(0, 1)
    else:
        mask = torch.zeros(pixels.shape[:3], dtype=torch.float32)
    if tuple(mask.shape) != tuple(pixels.shape[:3]):
        raise RuntimeError("SegFormer mask does not match its input image")

    output = torch.cat((pixels[..., :3], mask.unsqueeze(-1)), dim=-1)
    if crop_multi > 0.0:
        return await _crop_from_mask(
            output, mask, crop_multi, crop_multi, 1.0)
    return output, mask, [[0, 0, 0, 0]]


_INTERROGATOR_MODES = {
    "fast": (
        "Describe this image as a concise text-to-image prompt. Include the "
        "main subject, setting, and visual style. Return only the prompt.",
        96,
    ),
    "classic": (
        "Describe this image as a text-to-image prompt. Include the subject, "
        "medium, visual style, composition, lighting, and important colors. "
        "Return only one prompt.",
        160,
    ),
    "best": (
        "Write a detailed, accurate text-to-image prompt for this image. "
        "Cover subjects, appearance, actions, setting, spatial relationships, "
        "composition, camera viewpoint, lighting, colors, texture, medium, and "
        "style. Do not invent unseen details. Return only one prompt.",
        256,
    ),
    "negative": (
        "Analyze this image and write a negative prompt for reproducing it. "
        "List defects, artifacts, conflicting styles, incorrect anatomy, bad "
        "composition, and unwanted visual qualities to avoid. Return only the "
        "comma-separated negative prompt.",
        160,
    ),
}

_JOY_CAPTION_STYLES = {
    "Descriptive": "Write a precise, factual description of the image.",
    "Descriptive (Informal)": (
        "Describe the image naturally in an informal conversational voice."
    ),
    "Training Prompt": (
        "Write a dense text-to-image training caption with subjects, setting, "
        "composition, lighting, colors, medium, and style."
    ),
    "MidJourney": (
        "Write a polished MidJourney-style prompt and return only the prompt."
    ),
    "Booru tag list": (
        "Return only a comma-separated booru tag list using concise tags."
    ),
    "Booru-like tag list": (
        "Return only a comma-separated list of short descriptive tags."
    ),
    "Art Critic": (
        "Critique the artwork's subject, composition, technique, color, "
        "lighting, style, and overall effect."
    ),
    "Product Listing": (
        "Write an accurate product-listing description without inventing "
        "features that are not visible."
    ),
    "Social Media Post": (
        "Write an engaging social-media caption grounded in the image."
    ),
}


def _joy_caption_instruction(
    caption_type: Any, caption_length: Any, extra_options: Any,
    name_input: Any, custom_prompt: Any,
) -> str:
    custom = str(custom_prompt or "").strip()
    if custom:
        instruction = custom
    else:
        style = _JOY_CAPTION_STYLES.get(str(caption_type))
        if style is None:
            raise ValueError(f"unknown JoyCaption caption_type {caption_type!r}")
        length = str(caption_length)
        if length == "any":
            length_instruction = "Use the length needed to describe it well."
        elif length.isdigit():
            length_instruction = f"Aim for about {int(length)} words."
        else:
            length_instruction = f"Make the result {length}."
        instruction = f"{style} {length_instruction}"
    extra = str(extra_options or "").strip()
    if extra:
        extra = extra.replace("{name}", str(name_input or "").strip())
        instruction += " Additional requirements: " + extra
    return instruction


async def _image_interrogator(
    image, mode, use_lowvram=False, **_kwargs,
):
    mode = str(mode)
    selected = _INTERROGATOR_MODES.get(mode)
    if selected is None:
        raise ValueError(f"unknown easy imageInterrogator mode {mode!r}")
    if type(use_lowvram) is not bool:
        raise TypeError("easy imageInterrogator use_lowvram must be a boolean")

    logical = await _download_declared_weight(_IMAGE_INTERROGATOR_WEIGHT)
    encoder = await _ctx().models.load_text_encoder(
        logical,
        model_type="krea2",
        device="cpu" if use_lowvram else "default",
    )
    pixels = (await _raw(image)).detach().cpu().float()
    if (pixels.ndim != 4 or pixels.shape[-1] < 3
            or not 1 <= len(pixels) <= 64):
        raise ValueError(
            "easy imageInterrogator needs a non-empty BHWC RGB batch")
    instruction, max_length = selected
    prompts = []
    for frame in pixels:
        frame_ref = await sdk.ImageRef._from_raw(
            frame[..., :3].unsqueeze(0))
        prompts.append(await encoder.generate_text(
            instruction,
            frame_ref,
            max_length=max_length,
            do_sample=False,
            temperature=1.0,
            top_k=50,
            top_p=0.95,
            min_p=0.0,
            repetition_penalty=1.05,
            seed=0,
            thinking=False,
            use_default_template=True,
        ))
    return _one(prompts)


async def _joy_caption(
    image, do_sample, temperature, max_tokens, caption_type,
    caption_length, extra_options, name_input, custom_prompt,
    apikey_override=None, **_kwargs,
):
    if type(do_sample) is not bool:
        raise TypeError("JoyCaption do_sample must be a boolean")
    temperature = float(temperature)
    if not math.isfinite(temperature) or not 0.0 <= temperature <= 2.0:
        raise ValueError("JoyCaption temperature must be in [0, 2]")
    max_tokens = int(max_tokens)
    if not 16 <= max_tokens <= 512:
        raise ValueError("JoyCaption max_tokens must be in [16, 512]")
    instruction = _joy_caption_instruction(
        caption_type, caption_length, extra_options, name_input, custom_prompt)
    logical = await _download_declared_weight(_IMAGE_INTERROGATOR_WEIGHT)
    encoder = await _ctx().models.load_text_encoder(
        logical, model_type="krea2", device="default")
    pixels = (await _raw(image)).detach().cpu().float()
    if (pixels.ndim != 4 or pixels.shape[-1] < 3
            or not 1 <= len(pixels) <= 64):
        raise ValueError("JoyCaption needs a non-empty BHWC RGB batch")
    captions = []
    for frame in pixels:
        frame_ref = await sdk.ImageRef._from_raw(frame[..., :3].unsqueeze(0))
        captions.append(await encoder.generate_text(
            instruction,
            frame_ref,
            max_length=max_tokens,
            do_sample=do_sample,
            temperature=temperature,
            top_k=50,
            top_p=0.95,
            min_p=0.0,
            repetition_penalty=1.05,
            seed=0,
            thinking=False,
            use_default_template=True,
        ))
    return _one("\n".join(captions))


async def _input_files(directory="", start_index=0, limit=-1) -> list[str]:
    prefix = str(directory or "").replace("\\", "/").strip("/")
    if prefix:
        _safe_asset_name(prefix)
    names = await _ctx().assets.list("input", prefix=prefix, recursive=True)
    names = sorted(name for name in names if PurePosixPath(name).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    names = names[int(start_index):]
    return names if int(limit) < 0 else names[:int(limit)]


async def _images_count_directory(directory, start_index, limit, **_kwargs):
    return _one(len(await _input_files(directory, start_index, limit)))


async def _load_images_loop(directory, start_index, limit,
                            initial_value1=None, initial_value2=None, **_kwargs):
    names = await _input_files(directory, start_index, limit)
    if not names:
        raise ValueError("no catalogue images matched the Easy loop loader")
    name = names[0]
    asset = await _ctx().assets.resolve("input", name)
    data = await _ctx().assets.read_bytes(asset)
    image, mask = _pil_tensor(Image.open(bytes_io.BytesIO(data)))
    flow = {"kind": "easy-image-loop", "names": names, "index": 0}
    return flow, 0, image, mask, name, initial_value1, initial_value2


async def _remove_local_image(any, file_name, **_kwargs):
    query = _safe_asset_name(file_name)
    names = await _ctx().assets.list("input", recursive=True)
    exact = [name for name in names if name == query]
    if exact:
        selected = exact[0]
    else:
        matches = []
        for name in names:
            path = PurePosixPath(name)
            if path.with_suffix("").as_posix() == query:
                matches.append(name)
            elif "/" not in query and (path.name == query or path.stem == query):
                matches.append(name)
        matches = sorted(set(matches))
        if not matches:
            raise FileNotFoundError(f"no input asset matches {query!r}")
        if len(matches) > 1:
            raise ValueError(
                f"input asset name {query!r} is ambiguous: {matches}")
        selected = matches[0]
    if not await _ctx().assets.delete_input(selected):
        raise FileNotFoundError(
            f"input asset {selected!r} disappeared before deletion")
    return ()


_IMAGE_HANDLERS = {
    "easy imageCount": _image_count,
    "easy imagesCountInDirectory": _images_count_directory,
    "easy imageInsetCrop": _image_inset_crop,
    "easy imageSize": _image_size,
    "easy imageSizeBySide": _image_side,
    "easy imageSizeByLongerSide": _image_long_side,
    "easy imageScaleDown": _image_scale_down,
    "easy imageScaleDownBy": _image_scale_down_by,
    "easy imageScaleDownToSize": _image_scale_to_size,
    "easy imageScaleToNormPixels": _image_scale_norm,
    "easy imageRatio": _image_ratio,
    "easy imagePixelPerfect": _pixel_perfect,
    "easy imageSave": _image_save,
    "easy joinImageBatch": _join_image_batch,
    "easy imageListToImageBatch": _image_list_to_batch,
    "easy imageBatchToImageList": _image_batch_to_list,
    "easy imageSplitList": _image_split_list,
    "easy imageSplitGrid": _image_split_grid,
    "easy imageSplitTiles": _image_split_tiles,
    "easy imageTilesFromBatch": _tile_from_batch,
    "easy imagesSplitImage": _split_five,
    "easy imageConcat": _image_concat,
    "easy imageChooser": _image_chooser,
    "easy imageColorMatch": _color_match,
    "easy imageDetailTransfer": _detail_transfer,
    "easy imageCropFromMask": _crop_from_mask,
    "easy imageUncropFromBBOX": _uncrop,
    "easy loadImageBase64": _load_base64,
    "easy imageToBase64": _image_to_base64,
    "easy loadImagesForLoop": _load_images_loop,
    "easy imageRemBg": _remove_background,
    "easy humanSegmentation": _human_segmentation,
    "easy imageInterrogator": _image_interrogator,
    "easy makeImageForICLora": _make_image_for_ic_lora,
    "easy removeLocalImage": _remove_local_image,
}


# -------------------------------------------------------------------------
# Model loading, LoRA stacks, and Easy's dictionary-based pipeline.
# -------------------------------------------------------------------------

def _resolution(kwargs: dict[str, Any]) -> tuple[int, int]:
    width = int(kwargs.get("empty_latent_width", 512))
    height = int(kwargs.get("empty_latent_height", 512))
    resolution = str(kwargs.get("resolution", ""))
    if resolution and "custom" not in resolution and " x " in resolution:
        try:
            width, height = map(int, resolution.split(" x ")[:2])
        except ValueError:
            pass
    return max(8, width // 8 * 8), max(8, height // 8 * 8)


async def _apply_lora_stack(model, clip, stack):
    if model is None:
        return model, clip
    for entry in stack or ():
        if not isinstance(entry, (list, tuple)) or len(entry) < 3:
            continue
        name, strength_model, strength_clip = entry[:3]
        if not name or name == "None":
            continue
        asset = await _ctx().assets.resolve("loras", _safe_asset_name(name))
        model, clip = await model.apply_lora(
            asset, clip, float(strength_model), float(strength_clip)
        )
    return model, clip


async def _load_easy_pipeline(node_id: str, kwargs: dict[str, Any]):
    model = kwargs.get("model_override") or kwargs.get("model")
    clip = kwargs.get("clip_override") or kwargs.get("clip")
    vae = kwargs.get("vae_override") or kwargs.get("vae")
    checkpoint = (
        kwargs.get("ckpt_name") or kwargs.get("stage_c")
        or kwargs.get("unet_name") or kwargs.get("model_name")
    )
    if model is None:
        if not checkpoint or checkpoint == "None":
            raise ValueError(f"{node_id} needs a checkpoint or model override")
        name = _safe_asset_name(checkpoint)
        if "unet_name" in kwargs and "ckpt_name" not in kwargs:
            model = await _ctx().models.load_diffusion_model(name)
        else:
            model, loaded_clip, loaded_vae = await _ctx().models.load_checkpoint(name)
            clip = clip or loaded_clip
            vae = vae or loaded_vae

    vae_name = kwargs.get("vae_name")
    if vae_name and vae_name not in ("Baked VAE", "Baked-VAE", "None"):
        vae = await _ctx().models.load_vae(_safe_asset_name(vae_name))

    stack = list(kwargs.get("optional_lora_stack") or ())
    lora_name = kwargs.get("lora_name")
    if lora_name and lora_name != "None":
        stack.append((
            lora_name,
            float(kwargs.get("lora_model_strength", 1.0)),
            float(kwargs.get("lora_clip_strength", 1.0)),
        ))
    model, clip = await _apply_lora_stack(model, clip, stack)

    positive_text = str(kwargs.get("positive", kwargs.get("optional_positive", "")) or "")
    negative_text = str(kwargs.get("negative", kwargs.get("optional_negative", "")) or "")
    positive = await clip.encode(positive_text) if clip is not None else None
    negative = await clip.encode(negative_text) if clip is not None else None
    width, height = _resolution(kwargs)
    batch = int(kwargs.get("batch_size", 1))
    latent_value = {"samples": torch.zeros((batch, 4, height // 8, width // 8))}
    latent = await sdk.LatentRef.from_value(latent_value)
    settings = {
        key: value for key, value in kwargs.items()
        if isinstance(value, (str, int, float, bool))
    }
    settings.update({
        "ckpt_name": checkpoint or "",
        "vae_name": vae_name or "Baked VAE",
        "lora_name": lora_name or "None",
        "positive": positive_text,
        "negative": negative_text,
        "batch_size": batch,
        "empty_latent_width": width,
        "empty_latent_height": height,
    })
    pipe = {
        "model": model,
        "clip": clip,
        "vae": vae,
        "positive": positive,
        "negative": negative,
        "samples": latent,
        "images": kwargs.get("init_image"),
        "seed": kwargs.get("seed"),
        "loader_settings": settings,
    }

    conditioning_index = 0
    values = []
    for io_type in _output_types(node_id):
        if io_type == "PIPE_LINE":
            values.append(pipe)
        elif io_type == "MODEL":
            values.append(model)
        elif io_type == "VAE":
            values.append(vae)
        elif io_type == "CLIP":
            values.append(clip)
        elif io_type == "CONDITIONING":
            values.append((positive, negative)[min(conditioning_index, 1)])
            conditioning_index += 1
        elif io_type == "LATENT":
            values.append(latent)
        elif io_type == "STRING":
            values.append("")
        else:
            values.append(None)
    return {"ui": {"positive": [positive_text], "negative": [negative_text]}, "result": tuple(values)}


def _loader(node_id: str):
    async def execute(**kwargs):
        return await _load_easy_pipeline(node_id, kwargs)
    return execute


async def _lora_stack(toggle, mode, num_loras, optional_lora_stack=None, **kwargs):
    stack = list(optional_lora_stack or ())
    if not toggle:
        return _one(stack or None)
    for index in range(1, int(num_loras) + 1):
        name = kwargs.get(f"lora_{index}_name")
        if not name or name == "None":
            continue
        if mode == "simple":
            strength_model = strength_clip = float(kwargs.get(f"lora_{index}_strength", 1.0))
        else:
            strength_model = float(kwargs.get(f"lora_{index}_model_strength", 1.0))
            strength_clip = float(kwargs.get(f"lora_{index}_clip_strength", 1.0))
        stack.append((_safe_asset_name(name), strength_model, strength_clip))
    return _one(stack or None)


async def _lora_switcher(toggle, select, num_loras, lora_strength,
                         optional_lora_stack=None, **kwargs):
    stack = list(optional_lora_stack or ())
    if not toggle:
        return stack or None, ""
    name = kwargs.get(f"lora_{int(select)}_name")
    if not name or name == "None":
        return stack or None, ""
    name = _safe_asset_name(name)
    stack.append((name, float(lora_strength), float(lora_strength)))
    return stack, PurePosixPath(name).stem


async def _controlnet_stack(toggle, mode, num_controlnet,
                            optional_controlnet_stack=None, **kwargs):
    stack = list(optional_controlnet_stack or ())
    if not toggle:
        return _one(stack or None)
    for index in range(1, int(num_controlnet) + 1):
        name = kwargs.get(f"controlnet_{index}")
        if not name or name == "None":
            continue
        stack.append((
            _safe_asset_name(name),
            float(kwargs.get(f"controlnet_{index}_strength", 1.0)),
            float(kwargs.get(f"start_percent_{index}", 0.0)) if mode == "advanced" else 0.0,
            float(kwargs.get(f"end_percent_{index}", 1.0)) if mode == "advanced" else 1.0,
            float(kwargs.get(f"scale_soft_weight_{index}", 1.0)),
            kwargs.get(f"image_{index}"),
            True,
        ))
    return _one(stack or None)


async def _lora_stack_apply(lora_stack, model, optional_clip=None, **_kwargs):
    return await _apply_lora_stack(model, optional_clip, lora_stack)


async def _controlnet_stack_apply(controlnet_stack, pipe, **_kwargs):
    source = dict(pipe)
    for key in ("model", "positive", "negative", "vae"):
        if key not in source:
            raise ValueError(f"Easy ControlNet stack pipe is missing {key}")
    positive, negative = source["positive"], source["negative"]
    for index, item in enumerate(controlnet_stack or (), start=1):
        if not isinstance(item, (list, tuple)) or len(item) < 6:
            raise ValueError(
                f"ControlNet stack item {index} is not a valid stack entry")
        name, strength, start, end, scale, image = item[:6]
        if image is None:
            raise ValueError(
                f"ControlNet stack item {index} requires a conditioning image")
        scale = float(scale)
        if not math.isfinite(scale) or not 0.0 <= scale <= 1.0:
            raise ValueError(
                f"ControlNet stack item {index} soft weight must be in [0, 1]")
        strength = float(strength)
        if strength == 0.0:
            continue
        keyframe = None
        if scale < 1.0:
            _weights, keyframe = await sdk.ControlNetWeightsRef.scaled_soft(
                scale)
            control_net = await _ctx().models.load_advanced_controlnet(
                _safe_asset_name(name), model=source["model"],
                timestep_keyframe=keyframe)
            positive, negative = await control_net.apply_advanced(
                positive, negative, image,
                strength=strength,
                start_percent=float(start),
                end_percent=float(end),
                vae=source["vae"],
                timestep_keyframe=keyframe,
            )
        else:
            control_net = await _ctx().models.load_controlnet(
                _safe_asset_name(name), model=source["model"])
            positive, negative = await control_net.apply(
                positive, negative, image,
                strength=strength,
                start_percent=float(start),
                end_percent=float(end),
                vae=source["vae"],
            )
    source["positive"] = positive
    source["negative"] = negative
    return _one(source)


async def _lora_prompt_apply(model, clip, positive, negative, **_kwargs):
    found = []
    for text in (str(positive), str(negative)):
        found.extend(_LORA_PATTERN.findall(text))
    seen = set()
    for name, strength in found:
        key = (name, strength)
        if key in seen:
            continue
        seen.add(key)
        value = float(strength or 1.0)
        model, clip = await _apply_lora_stack(model, clip, [(name, value, value)])
    clean_positive = _LORA_PATTERN.sub("", str(positive)).strip()
    clean_negative = _LORA_PATTERN.sub("", str(negative)).strip()
    return model, clip, clean_positive, clean_negative


async def _pipe_in(pipe=None, model=None, pos=None, neg=None, latent=None,
                   vae=None, clip=None, image=None, xyPlot=None, **_kwargs):
    source = dict(pipe or {})
    settings = dict(source.get("loader_settings") or {})
    model = model or source.get("model")
    positive = pos or source.get("positive")
    negative = neg or source.get("negative")
    vae = vae or source.get("vae")
    clip = clip or source.get("clip")
    samples = latent or source.get("samples")
    images = image or source.get("images")
    if image is not None and latent is None:
        if vae is None:
            raise ValueError("Easy pipeIn needs a VAE to encode an image")
        samples = await vae.encode(image)
    settings["xyplot"] = xyPlot if xyPlot is not None else settings.get("xyplot")
    source.update({
        "model": model, "positive": positive, "negative": negative,
        "vae": vae, "clip": clip, "samples": samples, "images": images,
        "loader_settings": settings,
    })
    return _one(source)


async def _pipe_out(pipe, **_kwargs):
    return (
        pipe, pipe.get("model"), pipe.get("positive"), pipe.get("negative"),
        pipe.get("samples"), pipe.get("vae"), pipe.get("clip"),
        pipe.get("images"), pipe.get("seed"),
    )


async def _pipe_edit(pipe=None, model=None, pos=None, neg=None, latent=None,
                     vae=None, clip=None, image=None, optional_positive="",
                     optional_negative="", **kwargs):
    source = dict(pipe or {})
    model, clip, vae = model or source.get("model"), clip or source.get("clip"), vae or source.get("vae")
    positive, negative = pos or source.get("positive"), neg or source.get("negative")
    if pos is None and optional_positive and clip is not None:
        encoded = await clip.encode(str(optional_positive))
        positive = await positive.combine(encoded) if positive is not None and kwargs.get("conditioning_mode") == "combine" else encoded
    if neg is None and optional_negative and clip is not None:
        encoded = await clip.encode(str(optional_negative))
        negative = await negative.combine(encoded) if negative is not None and kwargs.get("conditioning_mode") == "combine" else encoded
    samples = latent or source.get("samples")
    if image is not None:
        if vae is None:
            raise ValueError("Easy pipeEdit needs a VAE to encode an image")
        samples = await vae.encode(image)
    source.update({
        "model": model, "clip": clip, "vae": vae,
        "positive": positive, "negative": negative, "samples": samples,
        "images": image if image is not None else source.get("images"),
    })
    return source, model, positive, negative, samples, vae, clip, source.get("images")


async def _pipe_edit_prompt(pipe, positive, negative, **_kwargs):
    source = dict(pipe)
    clip = source.get("clip")
    if clip is None:
        raise ValueError("Easy pipeEditPrompt needs a CLIP ref in the pipe")
    source["positive"] = await clip.encode(str(positive))
    source["negative"] = await clip.encode(str(negative))
    settings = dict(source.get("loader_settings") or {})
    settings.update({"positive": str(positive), "negative": str(negative)})
    source["loader_settings"] = settings
    return _one(source)


async def _pipe_basic(pipe, **_kwargs):
    return _one((
        pipe.get("model"), pipe.get("clip"), pipe.get("vae"),
        pipe.get("positive"), pipe.get("negative"),
    ))


async def _pipe_batch(pipe, batch_index, length, **_kwargs):
    source = dict(pipe)
    latent = await _raw(source.get("samples"))
    start, count = int(batch_index), int(length)
    result = dict(latent)
    total = len(result["samples"])
    start = min(max(0, start), max(0, total - 1))
    result["samples"] = result["samples"][start:start + count].clone()
    source["samples"] = result
    return _one(source)


async def _xy_plot(pipe=None, **kwargs):
    source = dict(pipe or {})
    settings = dict(source.get("loader_settings") or {})
    settings["xyplot"] = {
        key: value for key, value in kwargs.items()
        if key not in {"pipe"}
    }
    source["loader_settings"] = settings
    return _one(source)


_CONTROLNET_UNION_TYPES = {
    "auto": None,
    "openpose": 0,
    "depth": 1,
    "hed/pidi/scribble/ted": 2,
    "canny/lineart/anime_lineart/mlsd": 3,
    "normal": 4,
    "segment": 5,
    "tile": 6,
    "repaint": 7,
}

_CONTROLNET_PLUSPLUS_TYPES = {
    "auto": "none",
    "openpose": "openpose",
    "depth": "depth",
    "hed/pidi/scribble/ted": "hed/pidi/scribble/ted",
    "canny/lineart/anime_lineart/mlsd": "canny/lineart/mlsd",
    "normal": "normal",
    "segment": "segment",
    "tile": "tile",
    "repaint": "inpaint/outpaint",
}


def _controlnet_loader(kind: str):
    async def execute(
        pipe, image, control_net_name, control_net=None, strength=1.0,
        start_percent=0.0, end_percent=1.0, scale_soft_weights=1.0,
        union_type=None, **_kwargs,
    ):
        source = dict(pipe)
        missing = [
            key for key in (
                "model", "positive", "negative", "vae", "clip", "samples",
                "images", "loader_settings",
            )
            if key not in source
        ]
        if missing:
            raise ValueError(
                "Easy ControlNet pipe is missing " + ", ".join(missing))

        scale = float(scale_soft_weights)
        if not math.isfinite(scale) or not 0.0 <= scale <= 1.0:
            raise ValueError("scale_soft_weights must be finite and in [0, 1]")
        strength_value = float(strength)
        start = 0.0 if kind == "simple" else float(start_percent)
        end = 1.0 if kind == "simple" else float(end_percent)
        positive, negative = source["positive"], source["negative"]

        if strength_value != 0.0:
            selected = control_net
            keyframe = None
            use_advanced = False
            if kind == "plusplus" and scale < 1.0:
                _weights, keyframe = await sdk.ControlNetWeightsRef.scaled_soft(
                    scale)
                selected_type = _CONTROLNET_PLUSPLUS_TYPES.get(
                    union_type or "auto")
                if selected_type is None:
                    raise ValueError(
                        f"unknown ControlNet++ union type {union_type!r}")
                selected = await _ctx().models.load_controlnet_plusplus(
                    _safe_asset_name(control_net_name), selected_type)
                use_advanced = True
            elif selected is None and scale < 1.0:
                _weights, keyframe = await sdk.ControlNetWeightsRef.scaled_soft(
                    scale)
                selected = await _ctx().models.load_advanced_controlnet(
                    _safe_asset_name(control_net_name),
                    model=source["model"], timestep_keyframe=keyframe)
                use_advanced = True
            elif selected is None:
                selected = await _ctx().models.load_controlnet(
                    _safe_asset_name(control_net_name), model=source["model"])

            if kind == "plusplus" and scale >= 1.0 and union_type is not None:
                if union_type not in _CONTROLNET_UNION_TYPES:
                    raise ValueError(
                        f"unknown ControlNet union type {union_type!r}")
                selected = await selected.with_union_type(
                    _CONTROLNET_UNION_TYPES[union_type])

            if use_advanced:
                positive, negative = await selected.apply_advanced(
                    positive, negative, image,
                    strength=strength_value,
                    start_percent=start,
                    end_percent=end,
                    vae=source["vae"],
                    timestep_keyframe=keyframe,
                )
            else:
                positive, negative = await selected.apply(
                    positive, negative, image,
                    strength=strength_value,
                    start_percent=start,
                    end_percent=end,
                    vae=source["vae"],
                )

        result = {
            "model": source["model"],
            "positive": positive,
            "negative": negative,
            "vae": source["vae"],
            "clip": source["clip"],
            "samples": source["samples"],
            "images": image if kind == "advanced" else source["images"],
            "seed": 0,
            "loader_settings": source["loader_settings"],
        }
        return result, positive, negative

    return execute


_LOADER_IDS = {
    "easy fullLoader", "easy a1111Loader", "easy comfyLoader",
    "easy cascadeLoader", "easy fluxLoader", "easy hunyuanDiTLoader",
    "easy kolorsLoader", "easy mochiLoader", "easy pixArtLoader",
    "easy sv3dLoader", "easy svdLoader", "easy zero123Loader",
}
_LOADER_HANDLERS = {node_id: _loader(node_id) for node_id in _LOADER_IDS}


async def _lllite_loader(
    model, model_name, cond_image, strength, steps,
    start_percent, end_percent, **_kwargs,
):
    return _one(await model.patch(
        "controlnet_lllite",
        adapter=_safe_asset_name(model_name),
        image=cond_image,
        strength=float(strength),
        steps=int(steps),
        start_percent=float(start_percent),
        end_percent=float(end_percent),
    ))


_LOADER_HANDLERS.update({
    "easy loraStack": _lora_stack,
    "easy loraSwitcher": _lora_switcher,
    "easy controlnetStack": _controlnet_stack,
    "easy controlnetLoader": _controlnet_loader("simple"),
    "easy controlnetLoaderADV": _controlnet_loader("advanced"),
    "easy controlnetLoader++": _controlnet_loader("plusplus"),
    "easy LLLiteLoader": _lllite_loader,
})

_PIPE_HANDLERS = {
    "easy pipeIn": _pipe_in,
    "easy pipeOut": _pipe_out,
    "easy pipeEdit": _pipe_edit,
    "easy pipeEditPrompt": _pipe_edit_prompt,
    "easy pipeToBasicPipe": _pipe_basic,
    "easy pipeBatchIndex": _pipe_batch,
    "easy XYPlot": _xy_plot,
    "easy XYPlotAdvanced": _xy_plot,
}

_ADAPTER_HANDLERS = {
    "easy loraPromptApply": _lora_prompt_apply,
    "easy loraStackApply": _lora_stack_apply,
    "easy controlnetStackApply": _controlnet_stack_apply,
}

_IPADAPTER_PRESET_ALIASES = {
    "LIGHT - SD1.5 only (low strength)": "STANDARD (medium strength)",
    "PLUS (kolors genernal)": "PLUS (high strength)",
    "FACEID": "PLUS FACE (portraits)",
    "FACEID PLUS - SD1.5 only": "PLUS FACE (portraits)",
    "FACEID PLUS KOLORS": "PLUS FACE (portraits)",
    "FACEID PLUS V2": "PLUS FACE (portraits)",
    "FACEID PORTRAIT (style transfer)": "PLUS FACE (portraits)",
    "FACEID PORTRAIT UNNORM - SDXL only (strong)": (
        "PLUS FACE (portraits)"),
}


async def _download_declared_weight(weight):
    return await _ctx().models.download_huggingface_weights(
        weight.repo_id,
        weight.filename,
        weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )


async def _easy_ipadapter_pipeline(
    model, preset, *, clip_vision=None, optional_ipadapter=None,
):
    if optional_ipadapter is not None:
        return optional_ipadapter
    requested_preset = str(preset)
    if requested_preset == "REGULAR - FLUX and SD3.5 only (high strength)":
        raise ValueError(
            "the secure API does not yet have a SafeTensor IP-Adapter "
            "implementation compatible with Flux or SD3.5")
    preset = _IPADAPTER_PRESET_ALIASES.get(
        requested_preset, requested_preset)
    family = await model.family()
    if ("KOLORS" in requested_preset.upper()
            and family not in {"sd1", "sdxl"}):
        family = "sdxl"
    selected = _IPADAPTER_WEIGHTS.get((preset, family))
    if selected is None:
        raise ValueError(
            f"Easy IP-Adapter preset {preset!r} does not support model "
            f"family {family!r}")
    adapter_weight, clip_key = selected
    adapter_name = await _download_declared_weight(adapter_weight)
    if clip_vision is None:
        clip_weight = _IPADAPTER_CLIP_WEIGHTS[clip_key]
        clip_name = await _download_declared_weight(clip_weight)
        clip_vision = await _ctx().models.load_clip_vision(clip_name)
    return await _ctx().models.load_ipadapter(adapter_name, clip_vision)


async def _ipadapter_apply(
    model, image, preset, weight, weight_faceidv2, start_at, end_at,
    use_tiled, attn_mask=None, optional_ipadapter=None, **_kwargs,
):
    pipeline = await _easy_ipadapter_pipeline(
        model, preset, optional_ipadapter=optional_ipadapter)
    if bool(use_tiled):
        patched, images, masks = await _ipadapter.apply_tiled(pipeline, 
            model,
            image,
            attn_mask=attn_mask,
            weight=float(weight),
            weight_type="linear",
            start_percent=float(start_at),
            end_percent=float(end_at),
        )
    else:
        patched = await _ipadapter.apply(pipeline, 
            model,
            image,
            attn_mask=attn_mask,
            weight=float(weight),
            weight_type="linear",
            start_percent=float(start_at),
            end_percent=float(end_at),
            weight_faceidv2=float(weight_faceidv2),
        )
        images, masks = image, None
    return patched, images, masks, pipeline


async def _ipadapter_apply_advanced(
    model, image, preset, weight, weight_faceidv2, weight_type,
    combine_embeds, start_at, end_at, embeds_scaling, use_tiled, use_batch,
    sharpening, image_negative=None, attn_mask=None, clip_vision=None,
    optional_ipadapter=None, layer_weights=None, **_kwargs,
):
    pipeline = await _easy_ipadapter_pipeline(
        model,
        preset,
        clip_vision=clip_vision,
        optional_ipadapter=optional_ipadapter,
    )
    if bool(use_tiled) and not layer_weights:
        patched, images, masks = await _ipadapter.apply_tiled(pipeline, 
            model,
            image,
            negative_image=image_negative,
            attn_mask=attn_mask,
            weight=float(weight),
            weight_type=str(weight_type),
            start_percent=float(start_at),
            end_percent=float(end_at),
            combine_embeds=str(combine_embeds),
            embeds_scaling=str(embeds_scaling),
            sharpening=float(sharpening),
            unfold_batch=bool(use_batch),
        )
    else:
        patched = await _ipadapter.apply(pipeline, 
            model,
            image,
            negative_image=image_negative,
            attn_mask=attn_mask,
            weight=float(weight),
            weight_type=str(weight_type),
            start_percent=float(start_at),
            end_percent=float(end_at),
            combine_embeds=str(combine_embeds),
            weight_faceidv2=float(weight_faceidv2),
            embeds_scaling=str(embeds_scaling),
            unfold_batch=bool(use_batch) and not bool(layer_weights),
            layer_weights=str(layer_weights) if layer_weights else None,
        )
        images, masks = image, None
    return patched, images, masks, pipeline


async def _ipadapter_style_composition(
    model, image_style, preset, weight_style, weight_composition,
    expand_style, combine_embeds, start_at, end_at, embeds_scaling,
    image_composition=None, image_negative=None, attn_mask=None,
    clip_vision=None, optional_ipadapter=None, **_kwargs,
):
    family = await model.family()
    if family != "sdxl":
        raise ValueError(
            "IP-Adapter style/composition transfer is only defined for SDXL")
    pipeline = await _easy_ipadapter_pipeline(
        model,
        preset,
        clip_vision=clip_vision,
        optional_ipadapter=optional_ipadapter,
    )
    patched = await _ipadapter.apply(pipeline, 
        model,
        image_style,
        negative_image=image_negative,
        attn_mask=attn_mask,
        style_image=image_style,
        composition_image=image_composition,
        weight=float(weight_style),
        weight_type="linear",
        start_percent=float(start_at),
        end_percent=float(end_at),
        combine_embeds=str(combine_embeds),
        weight_faceidv2=float(weight_composition),
        embeds_scaling=str(embeds_scaling),
        weight_style=float(weight_style),
        weight_composition=float(weight_composition),
        expand_style=bool(expand_style),
    )
    return patched, pipeline


async def _ipadapter_encoder(
    model, clip_vision, image1, preset, num_embeds,
    optional_ipadapter=None, pos_embeds=None, neg_embeds=None,
    combine_method="concat", **kwargs,
):
    pipeline = await _easy_ipadapter_pipeline(
        model,
        preset,
        clip_vision=clip_vision,
        optional_ipadapter=optional_ipadapter,
    )
    positive = []
    negative = []
    if pos_embeds is not None:
        if not _ipadapter.is_embeds(pos_embeds):
            raise TypeError("pos_embeds must come from a secure IP-Adapter encoder")
        positive.append(pos_embeds)
    if neg_embeds is not None:
        if not _ipadapter.is_embeds(neg_embeds):
            raise TypeError("neg_embeds must come from a secure IP-Adapter encoder")
        negative.append(neg_embeds)

    count = int(num_embeds)
    if not 1 <= count <= 4:
        raise ValueError("num_embeds must be in [1, 4]")
    for index in range(1, count + 1):
        image = image1 if index == 1 else kwargs.get(f"image{index}")
        if image is None:
            raise ValueError(f"image{index} is required")
        pos, neg = await _ipadapter.encode(
            pipeline,
            image,
            weight=float(kwargs.get(f"weight{index}", 1.0)),
            mask=kwargs.get(f"mask{index}"),
        )
        positive.append(pos)
        negative.append(neg)

    method = str(combine_method)
    pos_result = (
        positive[0]
        if len(positive) == 1 and method == "concat"
        else await _ipadapter.combine_embeds(positive[0], positive[1:], method)
    )
    neg_result = (
        negative[0]
        if len(negative) == 1 and method == "concat"
        else await _ipadapter.combine_embeds(negative[0], negative[1:], method)
    )
    return model, clip_vision, pipeline, pos_result, neg_result


async def _ipadapter_apply_embeds(
    model, ipadapter, pos_embed, weight, weight_type, start_at, end_at,
    embeds_scaling, attn_mask=None, neg_embed=None, **_kwargs,
):
    if not _ipadapter.is_pipeline(ipadapter):
        raise TypeError("ipadapter must be a secure IP-Adapter pipeline")
    if not _ipadapter.is_embeds(pos_embed):
        raise TypeError("pos_embed must come from a secure IP-Adapter encoder")
    patched = await _ipadapter.apply_embeds(
        ipadapter,
        model,
        pos_embed,
        negative=neg_embed,
        attn_mask=attn_mask,
        weight=float(weight),
        weight_type=str(weight_type),
        start_percent=float(start_at),
        end_percent=float(end_at),
        embeds_scaling=str(embeds_scaling),
    )
    return patched, ipadapter


_IPADAPTER_PARAM_KEYS = (
    "image", "attn_mask", "weight", "weight_type", "start_at", "end_at",
)


def _ipadapter_params(value):
    if not isinstance(value, dict) or set(value) != set(_IPADAPTER_PARAM_KEYS):
        raise TypeError("IPADAPTER_PARAMS has an invalid structure")
    result = {key: list(value[key]) for key in _IPADAPTER_PARAM_KEYS}
    lengths = {len(items) for items in result.values()}
    if len(lengths) != 1 or not lengths or not 1 <= lengths.pop() <= 64:
        raise ValueError("IPADAPTER_PARAMS lists must have one shared length")
    return result


async def _ipadapter_regional(
    pipe, image, positive, negative, image_weight, prompt_weight, weight_type,
    start_at, end_at, mask=None, optional_ipadapter_params=None, **_kwargs,
):
    source = dict(pipe)
    clip = source.get("clip")
    if clip is None:
        raise RuntimeError(
            "easy ipadapterApplyRegional requires the canonical CLIP encoder; "
            "the pack-specific ChatGLM encoder is not exposed to guests")
    settings = dict(source.get("loader_settings") or {})
    positive_text = str(positive or settings.get("positive") or "")
    negative_text = str(negative or settings.get("negative") or "")
    positive_cond = await clip.encode(positive_text)
    negative_cond = await clip.encode(negative_text)
    if mask is not None:
        positive_cond = await positive_cond.with_mask(
            mask, strength=float(prompt_weight), set_area_to_bounds=False)
        negative_cond = await negative_cond.with_mask(
            mask, strength=float(prompt_weight), set_area_to_bounds=False)

    params = {
        "image": [image],
        "attn_mask": [mask],
        "weight": [float(image_weight)],
        "weight_type": [str(weight_type)],
        "start_at": [float(start_at)],
        "end_at": [float(end_at)],
    }
    if optional_ipadapter_params is not None:
        previous = _ipadapter_params(optional_ipadapter_params)
        params = {
            key: previous[key] + params[key]
            for key in _IPADAPTER_PARAM_KEYS
        }
        if source.get("positive") is not None:
            positive_cond = await source["positive"].combine(positive_cond)
        if source.get("negative") is not None:
            negative_cond = await source["negative"].combine(negative_cond)
    source.update({"positive": positive_cond, "negative": negative_cond})
    return source, params, positive_cond, negative_cond


async def _ipadapter_from_params(
    model, preset, ipadapter_params, combine_embeds, embeds_scaling,
    optional_ipadapter=None, image_negative=None, **_kwargs,
):
    pipeline = await _easy_ipadapter_pipeline(
        model, preset, optional_ipadapter=optional_ipadapter)
    params = _ipadapter_params(ipadapter_params)
    method = str(combine_embeds)
    if method not in {
        "concat", "add", "subtract", "average", "norm average", "max", "min",
    }:
        raise ValueError(f"unknown IP-Adapter embedding method {method!r}")

    negative_embed = None
    if image_negative is not None:
        negative_embed, _unused = await _ipadapter.encode(pipeline, image_negative)
        if method != "concat":
            negative_embed = await _ipadapter.combine_embeds(negative_embed, [], method)

    patched = model
    for index, image in enumerate(params["image"]):
        if not isinstance(image, sdk.ImageRef):
            raise TypeError("IPADAPTER_PARAMS images must be typed image refs")
        positive_embed, default_negative = await _ipadapter.encode(pipeline, image)
        if method != "concat":
            positive_embed = await _ipadapter.combine_embeds(positive_embed, [], method)
            default_negative = await _ipadapter.combine_embeds(default_negative, [], method)
        patched = await _ipadapter.apply_embeds(
            pipeline,
            patched,
            positive_embed,
            negative=negative_embed or default_negative,
            attn_mask=params["attn_mask"][index],
            weight=float(params["weight"][index]),
            weight_type=str(params["weight_type"][index]),
            start_percent=float(params["start_at"][index]),
            end_percent=float(params["end_at"][index]),
            embeds_scaling=str(embeds_scaling),
        )
    return patched, pipeline


async def _style_aligned_batch(
    model, share_norm, share_attn, scale, **_kwargs,
):
    return _one(await model.patch(
        "style_aligned_batch",
        share_norm=str(share_norm),
        share_attention=str(share_attn),
        scale=float(scale),
    ))


async def _portrait_identity_pipeline(
    model, *, clip_vision=None, optional_ipadapter=None,
    assume_sdxl=False,
):
    if optional_ipadapter is not None:
        return optional_ipadapter
    family = await model.family()
    if family not in {"sd1", "sdxl"} and assume_sdxl:
        family = "sdxl"
    selected = _IPADAPTER_WEIGHTS.get(("PLUS FACE (portraits)", family))
    if selected is None:
        raise ValueError(
            "secure portrait identity supports SD1 and SDXL-compatible "
            f"models, not {family!r}")
    adapter_weight, clip_key = selected
    adapter_name = await _download_declared_weight(adapter_weight)
    if clip_vision is None:
        clip_weight = _IPADAPTER_CLIP_WEIGHTS[clip_key]
        clip_name = await _download_declared_weight(clip_weight)
        clip_vision = await _ctx().models.load_clip_vision(clip_name)
    return await _ctx().models.load_ipadapter(adapter_name, clip_vision)


async def _faceid_kolors(
    model, image, preset, lora_strength, provider, weight,
    weight_faceidv2, weight_kolors, weight_type, combine_embeds,
    start_at, end_at, embeds_scaling, cache_mode, use_tiled, use_batch,
    sharpening, image_negative=None, attn_mask=None, clip_vision=None,
    optional_ipadapter=None, **_kwargs,
):
    if str(preset) != "FACEID PLUS KOLORS":
        raise ValueError(f"unknown Kolors FaceID preset {preset!r}")
    pipeline = await _portrait_identity_pipeline(
        model, clip_vision=clip_vision,
        optional_ipadapter=optional_ipadapter, assume_sdxl=True)
    if bool(use_tiled):
        patched, images, masks = await _ipadapter.apply_tiled(pipeline, 
            model, image, negative_image=image_negative,
            attn_mask=attn_mask, weight=float(weight),
            weight_type=str(weight_type), start_percent=float(start_at),
            end_percent=float(end_at),
            combine_embeds=str(combine_embeds),
            embeds_scaling=str(embeds_scaling),
            sharpening=float(sharpening), unfold_batch=bool(use_batch),
        )
    else:
        patched = await _ipadapter.apply(pipeline, 
            model, image, negative_image=image_negative,
            attn_mask=attn_mask, weight=float(weight),
            weight_type=str(weight_type), start_percent=float(start_at),
            end_percent=float(end_at),
            combine_embeds=str(combine_embeds),
            weight_faceidv2=float(weight_faceidv2),
            embeds_scaling=str(embeds_scaling),
            unfold_batch=bool(use_batch),
        )
        images, masks = image, None
    return patched, images, masks, pipeline


async def _instant_id(
    pipe, image, instantid_file, insightface, control_net_name,
    cn_strength, cn_soft_weights, weight, start_at, end_at, noise,
    image_kps=None, mask=None, control_net=None, positive=None, negative=None,
    **_kwargs,
):
    source = dict(pipe or {})
    model = source.get("model")
    positive = positive if positive is not None else source.get("positive")
    negative = negative if negative is not None else source.get("negative")
    if model is None or positive is None or negative is None:
        raise ValueError(
            "easy InstantID needs model, positive, and negative in the pipe")
    for label, value, minimum, maximum in (
        ("weight", weight, 0.0, 5.0),
        ("cn_strength", cn_strength, 0.0, 10.0),
        ("cn_soft_weights", cn_soft_weights, 0.0, 1.0),
        ("noise", noise, 0.0, 1.0),
        ("start_at", start_at, 0.0, 1.0),
        ("end_at", end_at, 0.0, 1.0),
    ):
        number = float(value)
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise ValueError(
                f"InstantID {label} must be finite and in "
                f"[{minimum}, {maximum}]")
    if float(start_at) > float(end_at):
        raise ValueError("InstantID start_at must not exceed end_at")

    pipeline = await _portrait_identity_pipeline(model, assume_sdxl=True)
    patched = await _ipadapter.apply(pipeline, 
        model, image, attn_mask=mask, weight=float(weight),
        weight_type="linear", start_percent=float(start_at),
        end_percent=float(end_at), combine_embeds="average",
        embeds_scaling="K+V w/ C penalty",
    )

    selected_control = control_net
    control_name = str(control_net_name or "")
    if (selected_control is None and control_name
            and not control_name.startswith("None (")):
        if float(cn_soft_weights) < 1.0:
            _weights, keyframe = await sdk.ControlNetWeightsRef.scaled_soft(
                float(cn_soft_weights))
            selected_control = await _ctx().models.load_advanced_controlnet(
                _safe_asset_name(control_name), model=patched,
                timestep_keyframe=keyframe)
        else:
            selected_control = await _ctx().models.load_controlnet(
                _safe_asset_name(control_name), model=patched)
    if selected_control is not None and float(cn_strength) != 0.0:
        control_image = image_kps if image_kps is not None else image
        if float(cn_soft_weights) < 1.0:
            _weights, keyframe = await sdk.ControlNetWeightsRef.scaled_soft(
                float(cn_soft_weights))
            positive, negative = await selected_control.apply_advanced(
                positive, negative, control_image,
                strength=float(cn_strength),
                start_percent=float(start_at), end_percent=float(end_at),
                vae=source.get("vae"), timestep_keyframe=keyframe,
            )
        else:
            positive, negative = await selected_control.apply(
                positive, negative, control_image,
                strength=float(cn_strength),
                start_percent=float(start_at), end_percent=float(end_at),
                vae=source.get("vae"),
            )
    source.update({
        "model": patched,
        "positive": positive,
        "negative": negative,
    })
    return source, patched, positive, negative


async def _pulid(
    model, pulid_file, insightface, image, weight, start_at, end_at,
    method=None, projection=None, fidelity=8, noise=0.0, attn_mask=None,
    **_kwargs,
):
    start = float(start_at)
    end = float(end_at)
    strength = float(weight)
    if (not all(math.isfinite(value) for value in (start, end, strength))
            or not 0.0 <= start <= end <= 1.0
            or not -1.0 <= strength <= 5.0):
        raise ValueError("PuLID weight or timing range is invalid")
    pipeline = await _portrait_identity_pipeline(model, assume_sdxl=True)
    method_types = {
        "fidelity": "linear",
        "style": "style transfer",
        "neutral": "ease in-out",
    }
    weight_type = method_types.get(str(method), "linear")
    scaling = "V only" if projection == "none" else "K+V w/ C penalty"
    return _one(await _ipadapter.apply(pipeline, 
        model, image, attn_mask=attn_mask, weight=strength,
        weight_type=weight_type, start_percent=start, end_percent=end,
        combine_embeds="average", embeds_scaling=scaling,
    ))


_ADAPTER_HANDLERS.update({
    "easy ipadapterApply": _ipadapter_apply,
    "easy ipadapterApplyADV": _ipadapter_apply_advanced,
    "easy ipadapterStyleComposition": _ipadapter_style_composition,
    "easy ipadapterApplyEncoder": _ipadapter_encoder,
    "easy ipadapterApplyEmbeds": _ipadapter_apply_embeds,
    "easy ipadapterApplyRegional": _ipadapter_regional,
    "easy ipadapterApplyFromParams": _ipadapter_from_params,
    "easy styleAlignedBatchAlign": _style_aligned_batch,
    "easy ipadapterApplyFaceIDKolors": _faceid_kolors,
    "easy instantIDApply": _instant_id,
    "easy instantIDApplyADV": _instant_id,
    "easy pulIDApply": _pulid,
    "easy pulIDApplyADV": _pulid,
})


def _ic_light_gradient(
    height: int, width: int, direction: str, *, foreground: bool,
) -> torch.Tensor:
    high = 1.0 if foreground else 224.0 / 255.0
    low = 0.0 if foreground else 32.0 / 255.0
    if direction in {"Left Light", "Right Light"}:
        values = torch.linspace(high, low, width)
        if direction == "Right Light":
            values = values.flip(0)
        plane = values.unsqueeze(0).expand(height, -1)
    elif direction in {"Top Light", "Bottom Light"}:
        values = torch.linspace(high, low, height)
        if direction == "Bottom Light":
            values = values.flip(0)
        plane = values.unsqueeze(1).expand(-1, width)
    elif direction == "Circle Light" and foreground:
        x = torch.linspace(-1.0, 1.0, width)
        y = torch.linspace(-1.0, 1.0, height)
        yy, xx = torch.meshgrid(y, x, indexing="ij")
        radius = torch.sqrt(xx.square() + yy.square())
        plane = 1.0 - radius / radius.max().clamp_min(1e-8)
    elif direction == "Ambient" and not foreground:
        plane = torch.full((height, width), 64.0 / 255.0)
    else:
        return torch.zeros((1, 1, 1, 3), dtype=torch.float32)
    return plane[None, ..., None].expand(1, height, width, 3).contiguous()


async def _ic_light_apply(
    mode, model, image, vae, lighting, source, remove_bg, **_kwargs,
):
    mode = str(mode)
    if mode not in _IC_LIGHT_WEIGHTS:
        raise ValueError(f"unknown IC-Light mode {mode!r}")
    pixels = (await _raw(image)).detach().cpu().float()
    if (
        pixels.ndim != 4
        or pixels.shape[-1] not in (3, 4)
        or not 1 <= len(pixels) <= 64
        or pixels.shape[1] <= 0
        or pixels.shape[2] <= 0
    ):
        raise ValueError("easy icLightApply needs a bounded BHWC RGB(A) image")
    height, width = map(int, pixels.shape[1:3])

    foreground = pixels[:1]
    if foreground.shape[-1] == 3 and bool(remove_bg):
        removed = await _remove_background(
            image, "RMBG-2.0", "Hide", "ComfyUI")
        foreground = await _raw(removed["result"][0])
    if foreground.shape[-1] == 4:
        # Make the intended cutout visible to an RGB VAE instead of silently
        # discarding alpha at encode time.
        foreground = foreground[..., :3] * foreground[..., 3:4]
    else:
        foreground = foreground[..., :3]

    if mode == "Foreground":
        lighting_image = _ic_light_gradient(
            height, width, str(lighting), foreground=True)
        latent_pixels = foreground
    else:
        source = str(source)
        if source in {
            "Use Background Image", "Use Flipped Background Image",
        }:
            if len(pixels) < 2:
                raise ValueError(
                    f"IC-Light source {source!r} needs a second input image")
            lighting_image = pixels[1:2, ..., :3]
            if source == "Use Flipped Background Image":
                lighting_image = lighting_image.flip(2)
        else:
            lighting_image = _ic_light_gradient(
                height, width, source, foreground=False)
        if tuple(lighting_image.shape[1:3]) != (height, width):
            lighting_image = _scale_image(
                lighting_image, width, height, "center", "bilinear")
        latent_pixels = torch.cat(
            (foreground, lighting_image[..., :3]), dim=0)

    latent_image = await sdk.ImageRef._from_raw(latent_pixels)
    latent = await vae.encode(await latent_image.rgb())
    weight = _IC_LIGHT_WEIGHTS[mode]
    logical = await _ctx().models.download_huggingface_weights(
        weight.repo_id,
        weight.filename,
        weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )
    patched = await model.patch(
        "diffusion_weight_delta",
        model_patch=logical,
        strength=1.0,
        pad_input_channels=True,
    )
    patched = await patched.patch("concat_latent_input", latent=latent)
    lighting_ref = await sdk.ImageRef._from_raw(lighting_image)
    return patched, lighting_ref


_ADAPTER_HANDLERS["easy icLightApply"] = _ic_light_apply


# -------------------------------------------------------------------------
# Sampling configuration and brokered diffusion.
# -------------------------------------------------------------------------

async def _presampling(pipe, **kwargs):
    source = dict(pipe)
    settings = dict(source.get("loader_settings") or {})
    for key in (
        "steps", "cfg", "sampler_name", "scheduler", "denoise", "seed",
        "start_at_step", "end_at_step", "add_noise",
        "return_with_leftover_noise", "factor", "optional_noise_seed",
        "guider", "cfg_negative", "coeff", "sigma_max", "sigma_min",
        "rho", "beta_d", "beta_min", "eps_s", "flip_sigmas",
    ):
        if key in kwargs:
            settings[key] = kwargs[key]
    latent = kwargs.get("latent") or kwargs.get("optional_latent")
    image = kwargs.get("image_to_latent") or kwargs.get("image_to_latent_c")
    if latent is not None:
        source["samples"] = latent
    elif image is not None:
        vae = source.get("vae")
        if vae is None:
            raise ValueError("Easy preSampling needs a VAE to encode image_to_latent")
        source["samples"] = await vae.encode(image)
    source["seed"] = settings.get("seed", source.get("seed"))
    source["loader_settings"] = settings
    return _one(source)


async def _presampling_dynamic_cfg(
    pipe, cfg_mode, cfg_scale_min, **kwargs,
):
    source = dict(pipe)
    model = source.get("model")
    if model is None:
        raise ValueError("easy preSamplingDynamicCFG needs a model in the pipe")
    source["model"] = await model.patch(
        "dynamic_thresholding",
        mimic_scale=7.0,
        threshold_percentile=1.0,
        mimic_mode="Constant",
        mimic_scale_min=0.0,
        cfg_mode=str(cfg_mode),
        cfg_scale_min=float(cfg_scale_min),
        schedule_value=0.0,
        separate_feature_channels=False,
        scaling_startpoint="MEAN",
        variability_measure="AD",
        interpolate_phi=1.0,
    )
    return await _presampling(source, **kwargs)


async def _dynamic_thresholding_full(
    model, mimic_scale, threshold_percentile, mimic_mode,
    mimic_scale_min, cfg_mode, cfg_scale_min, sched_val,
    separate_feature_channels, scaling_startpoint,
    variability_measure, interpolate_phi, **_kwargs,
):
    return _one(await model.patch(
        "dynamic_thresholding",
        mimic_scale=float(mimic_scale),
        threshold_percentile=float(threshold_percentile),
        mimic_mode=str(mimic_mode),
        mimic_scale_min=float(mimic_scale_min),
        cfg_mode=str(cfg_mode),
        cfg_scale_min=float(cfg_scale_min),
        schedule_value=float(sched_val),
        separate_feature_channels=(
            str(separate_feature_channels) == "enable"),
        scaling_startpoint=str(scaling_startpoint),
        variability_measure=str(variability_measure),
        interpolate_phi=float(interpolate_phi),
    ))


async def _presampling_layer_additional(
    pipe, foreground_prompt="", background_prompt="", blended_prompt="",
    optional_fg_cond=None, optional_bg_cond=None, optional_blended_cond=None,
    **_kwargs,
):
    source = dict(pipe)
    clip = source.get("clip")
    if clip is not None:
        if optional_fg_cond is None and foreground_prompt:
            optional_fg_cond = await clip.encode(str(foreground_prompt))
        if optional_bg_cond is None and background_prompt:
            optional_bg_cond = await clip.encode(str(background_prompt))
        if optional_blended_cond is None and blended_prompt:
            optional_blended_cond = await clip.encode(str(blended_prompt))
    settings = dict(source.get("loader_settings") or {})
    settings["layer_diffusion_cond"] = (
        optional_fg_cond, optional_bg_cond, optional_blended_cond)
    source["loader_settings"] = settings
    return _one(source)


_LAYER_METHOD_ATTENTION = "Attention Injection"
_LAYER_METHOD_CONV = "Conv Injection"
_LAYER_METHOD_EVERYTHING = "Everything"
_LAYER_METHOD_FOREGROUND = "Foreground"
_LAYER_METHOD_FOREGROUND_TO_BACKGROUND = "Foreground to Background"
_LAYER_METHOD_BACKGROUND = "Background"
_LAYER_METHOD_BACKGROUND_TO_FOREGROUND = "Background to Foreground"
_LAYER_METHODS = {
    _LAYER_METHOD_ATTENTION,
    _LAYER_METHOD_CONV,
    _LAYER_METHOD_EVERYTHING,
    _LAYER_METHOD_FOREGROUND,
    _LAYER_METHOD_FOREGROUND_TO_BACKGROUND,
    _LAYER_METHOD_BACKGROUND,
    _LAYER_METHOD_BACKGROUND_TO_FOREGROUND,
}


async def _presampling_layer_diffusion(
    pipe, method, weight, steps, cfg, sampler_name, scheduler, denoise,
    seed, image=None, blended_image=None, mask=None, **_kwargs,
):
    source = dict(pipe)
    settings = dict(source.get("loader_settings") or {})
    method = str(method)
    if method not in _LAYER_METHODS:
        raise ValueError(f"unknown Easy Layer Diffusion method {method!r}")
    batch_size = int(settings.get("batch_size", 1))
    if not 1 <= batch_size <= 64:
        raise ValueError("Easy Layer Diffusion batch_size must be in [1, 64]")
    vae = source.get("vae")
    if vae is None:
        raise ValueError("Easy Layer Diffusion needs a VAE")

    blend_samples = source.get("blend_samples")
    has_blend = blend_samples is not None or blended_image is not None
    if has_blend and method == _LAYER_METHOD_BACKGROUND:
        method = _LAYER_METHOD_BACKGROUND_TO_FOREGROUND
    elif has_blend and method == _LAYER_METHOD_FOREGROUND:
        method = _LAYER_METHOD_FOREGROUND_TO_BACKGROUND

    selected_image = image if image is not None else source.get("image")
    if selected_image is not None:
        if mask is not None:
            samples = await vae.encode_for_inpaint(selected_image, mask)
        else:
            samples = await vae.encode(await selected_image.rgb())
        samples = await samples.repeat_batch(batch_size)
        images = selected_image
    elif source.get("samp_images") is not None:
        images = source["samp_images"]
        samples = await vae.encode(await images.rgb())
        samples = await samples.repeat_batch(batch_size)
    else:
        if method not in {
            _LAYER_METHOD_ATTENTION,
            _LAYER_METHOD_CONV,
            _LAYER_METHOD_EVERYTHING,
        }:
            raise ValueError(
                f"Easy Layer Diffusion method {method!r} needs an image")
        samples = source.get("samples")
        images = source.get("images")
        if samples is None:
            raise ValueError("Easy Layer Diffusion needs an input latent")

    if method in {
        _LAYER_METHOD_BACKGROUND_TO_FOREGROUND,
        _LAYER_METHOD_FOREGROUND_TO_BACKGROUND,
    }:
        if blended_image is None and blend_samples is None:
            raise ValueError(
                f"Easy Layer Diffusion method {method!r} needs blended_image")
        if blended_image is not None:
            blend_samples = await vae.encode(await blended_image.rgb())
            blend_samples = await blend_samples.repeat_batch(batch_size)

    settings.update({
        "steps": int(steps),
        "cfg": float(cfg),
        "sampler_name": str(sampler_name),
        "scheduler": str(scheduler),
        "denoise": float(denoise),
        "add_noise": "enabled",
        "layer_diffusion_method": method,
        "layer_diffusion_weight": float(weight),
    })
    result = {
        "model": source.get("model"),
        "positive": source.get("positive"),
        "negative": source.get("negative"),
        "vae": vae,
        "clip": source.get("clip"),
        "samples": samples,
        "blend_samples": blend_samples,
        "images": images,
        "seed": int(seed),
        "loader_settings": settings,
    }
    return {"ui": {"value": [int(seed)]}, "result": (result,)}


_DOWNSCALE_METHODS = {
    "bicubic", "nearest-exact", "bilinear", "area", "bislerp",
}


async def _easy_downscale_model(model, latent, **kwargs):
    mode = str(kwargs.get("downscale_mode", "Auto"))
    if mode == "None":
        return model
    if mode not in {"Auto", "Custom"}:
        raise ValueError("Easy UNet downscale mode must be None, Auto, or Custom")

    block_number = int(kwargs.get("block_number", 3))
    factor = kwargs.get("downscale_factor", 2.0)
    start_percent = float(kwargs.get("start_percent", 0.0))
    end_percent = float(kwargs.get("end_percent", 0.35))
    after_skip = kwargs.get("downscale_after_skip", True)
    downscale_method = str(kwargs.get("downscale_method", "bicubic"))
    upscale_method = str(kwargs.get("upscale_method", "bicubic"))
    if type(after_skip) is not bool:
        raise TypeError("Easy UNet downscale_after_skip must be a bool")
    if downscale_method not in _DOWNSCALE_METHODS:
        raise ValueError("unknown Easy UNet downscale method")
    if upscale_method not in _DOWNSCALE_METHODS:
        raise ValueError("unknown Easy UNet upscale method")

    if mode == "Auto":
        context_dim = await model.unet_context_dim()
        if context_dim is None:
            return model
        latent_height, latent_width = await latent.spatial_shape()
        width_factor = latent_width * 8 / context_dim
        height_factor = latent_height * 8 / context_dim
        if width_factor > 1.75:
            factor = width_factor
        elif height_factor > 1.25:
            factor = height_factor
        else:
            return model
        start_percent = 0.0
        end_percent = 0.35
        after_skip = True
        downscale_method = "bicubic"
        upscale_method = "bicubic"

    return await model.patch(
        "kohya_deep_shrink",
        block_number=block_number,
        downscale_factor=float(factor),
        start_percent=start_percent,
        end_percent=end_percent,
        downscale_after_skip=after_skip,
        downscale_method=downscale_method,
        upscale_method=upscale_method,
    )


async def _sample_pipe(pipe, *, node_id: str, **kwargs):
    source = dict(pipe)
    settings = dict(source.get("loader_settings") or {})
    model = kwargs.get("model") or kwargs.get("model_c") or source.get("model")
    positive = kwargs.get("positive") or source.get("positive")
    negative = kwargs.get("negative") or source.get("negative")
    latent = kwargs.get("latent") or source.get("samples")
    vae = kwargs.get("vae") or source.get("vae")
    clip = kwargs.get("clip") or source.get("clip")
    if not all((model, positive, negative, latent)):
        raise ValueError(f"{node_id} needs model, conditioning, and latent refs")
    if node_id == "easy kSamplerDownscaleUnet":
        model = await _easy_downscale_model(model, latent, **kwargs)
    steps = int(kwargs.get("steps", settings.get("steps", 20)))
    seed = int(kwargs.get("seed", source.get("seed", settings.get("seed", 0)) or 0))
    cfg = float(kwargs.get("cfg", settings.get("cfg", 8.0)))
    sampler_name = str(kwargs.get("sampler_name", settings.get("sampler_name", "euler")))
    scheduler = str(kwargs.get("scheduler", settings.get("scheduler", "normal")))
    denoise = float(kwargs.get("denoise", settings.get("denoise", 1.0)))
    start_step = kwargs.get("start_at_step", settings.get("start_at_step"))
    last_step = kwargs.get("end_at_step", settings.get("end_at_step"))
    add_noise = str(kwargs.get("add_noise", settings.get("add_noise", "enable"))).lower()
    leftover = str(kwargs.get(
        "return_with_leftover_noise", settings.get("return_with_leftover_noise", "disable")
    )).lower()
    sampled = await _ctx().sample(
        latent=latent,
        steps=steps,
        model=model,
        positive=positive,
        negative=negative,
        cfg=cfg,
        seed=seed,
        sampler_name=sampler_name,
        scheduler=scheduler,
        denoise=denoise,
        disable_noise=add_noise in {"disable", "false", "0"},
        start_step=None if start_step is None else int(start_step),
        last_step=None if last_step is None else int(last_step),
        force_full_denoise=leftover not in {"enable", "true", "1"},
    )
    image = None
    if vae is not None:
        if node_id == "easy kSamplerTiled":
            tile_size = int(kwargs.get("tile_size", 512))
            if not 320 <= tile_size <= 4096:
                raise ValueError("Easy tiled VAE tile_size must be in [320, 4096]")
            image = await vae.decode_tiled(sampled, tile_size=tile_size)
        else:
            image = await vae.decode(sampled)
    source.update({
        "model": model, "positive": positive, "negative": negative,
        "samples": sampled, "images": image, "vae": vae, "clip": clip,
        "seed": seed,
    })
    ui: dict[str, Any] = {}
    image_output = str(kwargs.get("image_output", "Hide"))
    if image is not None and image_output in ("Save", "Hide/Save"):
        ui = await _ctx().output.save_images(
            image, filename_prefix=str(kwargs.get("save_prefix", "ComfyUI"))
        )
    elif image is not None and image_output == "Preview":
        ui = await _ctx().ui.preview_images(image)

    conditioning_index = 0
    latent_index = 0
    image_index = 0
    values = []
    for io_type in _output_types(node_id):
        if io_type == "PIPE_LINE":
            values.append(source)
        elif io_type == "IMAGE":
            values.append(image)
            image_index += 1
        elif io_type == "MODEL":
            values.append(model)
        elif io_type == "CONDITIONING":
            values.append((positive, negative)[min(conditioning_index, 1)])
            conditioning_index += 1
        elif io_type == "LATENT":
            values.append(sampled)
            latent_index += 1
        elif io_type == "VAE":
            values.append(vae)
        elif io_type == "CLIP":
            values.append(clip)
        elif io_type == "INT":
            values.append(seed)
        elif io_type == "MASK":
            values.append([])
        else:
            values.append(None)
    return {"ui": ui, "result": tuple(values)}


def _sampler(node_id: str):
    async def execute(pipe, **kwargs):
        return await _sample_pipe(pipe, node_id=node_id, **kwargs)
    return execute


_LAYER_DIFFUSION_ALPHA_METHODS = {
    "sd1": {
        _LAYER_METHOD_ATTENTION,
        _LAYER_METHOD_EVERYTHING,
        _LAYER_METHOD_BACKGROUND,
        _LAYER_METHOD_BACKGROUND_TO_FOREGROUND,
    },
    "sdxl": {
        _LAYER_METHOD_ATTENTION,
        _LAYER_METHOD_CONV,
        _LAYER_METHOD_BACKGROUND_TO_FOREGROUND,
    },
}


async def _layer_diffusion_model_inputs(
    model, positive, negative, latent, blend_latent, image,
    additional_conditioning, method, weight,
):
    family = await model.family()
    if family not in {"sd1", "sdxl"}:
        raise ValueError(
            "Easy Layer Diffusion supports only SD1.x and SDXL models")
    selected = _LAYER_DIFFUSION_WEIGHTS.get((method, family))
    if selected is None:
        raise ValueError(
            f"Easy Layer Diffusion method {method!r} is not supported for "
            f"{family}")
    logical = await _download_declared_weight(selected)
    frames = 1

    if family == "sdxl":
        patched = await model.patch(
            "serialized_model_patch",
            model_patch=logical,
            strength=float(weight),
            pad_diff_weights=True,
        )
        if method not in {_LAYER_METHOD_ATTENTION, _LAYER_METHOD_CONV}:
            extra = (
                blend_latent
                if method in {
                    _LAYER_METHOD_FOREGROUND_TO_BACKGROUND,
                    _LAYER_METHOD_BACKGROUND_TO_FOREGROUND,
                }
                else None
            )
            positive = await positive.with_concat_latent(
                patched, latent, extra_latent=extra)
            negative = await negative.with_concat_latent(
                patched, latent, extra_latent=extra)
        return patched, positive, negative, frames, family

    first = second = third = None
    control_image = None
    additional = tuple(additional_conditioning or (None, None, None))
    if len(additional) != 3:
        raise ValueError(
            "Easy Layer Diffusion additional conditioning must have three "
            "entries")
    if method == _LAYER_METHOD_EVERYTHING:
        frames = 3
        first, second, third = additional
    elif method in {
        _LAYER_METHOD_FOREGROUND,
        _LAYER_METHOD_FOREGROUND_TO_BACKGROUND,
    }:
        frames = 2
        control_image = image
        first = additional[1]
    elif method in {
        _LAYER_METHOD_BACKGROUND,
        _LAYER_METHOD_BACKGROUND_TO_FOREGROUND,
    }:
        frames = 2
        control_image = image
        first = additional[0]
    if frames > 1 and control_image is None and method != _LAYER_METHOD_EVERYTHING:
        raise ValueError(
            f"Easy Layer Diffusion method {method!r} needs a control image")
    patched = await model.patch(
        "layer_diffusion_attention_sharing",
        model_patch=logical,
        frames=frames,
        control_image=control_image,
        first_conditioning=first,
        second_conditioning=second,
        third_conditioning=third,
    )
    return patched, positive, negative, frames, family


async def _layer_diffusion_sampler(
    pipe, image_output, link_id, save_prefix, model=None, **kwargs,
):
    source = dict(pipe)
    settings = dict(source.get("loader_settings") or {})
    method = str(settings.get("layer_diffusion_method") or "")
    if method not in _LAYER_METHODS:
        raise ValueError(
            "easy kSamplerLayerDiffusion needs a preceding Layer Diffusion "
            "pre-sampling node")
    model = model or source.get("model")
    positive = source.get("positive")
    negative = source.get("negative")
    latent = source.get("samples")
    vae = source.get("vae")
    missing = [
        name for name, value in {
            "model": model,
            "positive": positive,
            "negative": negative,
            "latent": latent,
            "vae": vae,
        }.items() if value is None
    ]
    if missing:
        raise ValueError(
            "easy kSamplerLayerDiffusion is missing " + ", ".join(missing))

    patched, positive, negative, frames, family = (
        await _layer_diffusion_model_inputs(
            model,
            positive,
            negative,
            latent,
            source.get("blend_samples"),
            source.get("images"),
            settings.get("layer_diffusion_cond"),
            method,
            float(settings.get("layer_diffusion_weight", 1.0)),
        )
    )
    batch = int(settings.get("batch_size", 1))
    width = int(settings.get("empty_latent_width", 512))
    height = int(settings.get("empty_latent_height", 512))
    if not 1 <= batch <= 64 or batch % frames:
        raise ValueError(
            f"Easy Layer Diffusion {method!r} needs a batch in [1, 64] "
            f"divisible by {frames}")
    if (
        not 64 <= width <= 16384
        or not 64 <= height <= 16384
        or width % 8
        or height % 8
        or batch * (width // 8) * (height // 8) > 4_194_304
    ):
        raise ValueError("Easy Layer Diffusion latent dimensions are invalid")
    empty = await sdk.LatentRef.empty(
        width, height, batch_size=batch, channels=4)
    run_source = dict(source)
    run_source.update({
        "model": patched,
        "positive": positive,
        "negative": negative,
        "samples": empty,
    })
    sampled = await _sample_pipe(
        run_source,
        node_id="easy kSamplerLayerDiffusion",
        model=patched,
        positive=positive,
        negative=negative,
        latent=empty,
        vae=vae,
        image_output="Hide",
        link_id=link_id,
        save_prefix=save_prefix,
        **kwargs,
    )
    result_pipe = dict(sampled["result"][0])
    regular_image = sampled["result"][1]
    final_image = regular_image
    alpha_outputs = []
    if method in _LAYER_DIFFUSION_ALPHA_METHODS[family]:
        decoder_weight = _LAYER_DIFFUSION_DECODERS[family]
        decoder_name = await _download_declared_weight(decoder_weight)
        decoder = await _ctx().models.load_transparent_vae_decoder(
            decoder_name, family)
        final_image, alpha = await decoder.decode(
            result_pipe["samples"], regular_image, frames=frames)
        alpha_outputs = [alpha]

    result_pipe.update({
        "model": patched,
        "positive": positive,
        "negative": negative,
        "images": final_image,
        "samp_images": regular_image,
        "alpha": alpha_outputs,
        "blend_samples": source.get("blend_samples"),
    })
    ui: dict[str, Any] = {}
    output_mode = str(image_output)
    if output_mode in {"Save", "Hide&Save", "Sender&Save", "Hide/Save"}:
        ui = await _ctx().output.save_images(
            final_image, filename_prefix=str(save_prefix))
    elif output_mode in {"Preview", "Sender"}:
        ui = await _ctx().ui.preview_images(final_image)
    return {
        "ui": ui,
        "result": (result_pipe, final_image, regular_image, alpha_outputs),
    }


async def _inpainting_sampler(
    pipe, grow_mask_by, additional, model=None, mask=None, **kwargs,
):
    source = dict(pipe)
    model = model or source.get("model")
    positive = source.get("positive")
    negative = source.get("negative")
    latent = source.get("samples")
    image = source.get("images")
    vae = source.get("vae")
    if latent is not None and mask is None:
        mask = await latent.noise_mask()
    missing = [
        name for name, value in {
            "model": model,
            "positive": positive,
            "negative": negative,
            "image": image,
            "vae": vae,
            "mask": mask,
        }.items() if value is None
    ]
    if missing:
        raise ValueError(
            "easy kSamplerInpainting is missing " + ", ".join(missing))

    additional = str(additional)
    if additional == "None":
        latent = await vae.encode_for_inpaint(
            image, mask, grow_mask_by=int(grow_mask_by))
    elif additional == "InpaintModelCond":
        grown = mask
        if int(grow_mask_by) > 0:
            grown = await mask.grow(int(grow_mask_by), False)
        positive, negative, latent = await vae.encode_inpaint_conditioning(
            image, grown, positive, negative, noise_mask=True)
    elif additional == "Differential Diffusion":
        positive, negative, latent = await vae.encode_inpaint_conditioning(
            image, mask, positive, negative, noise_mask=True)
        model = await model.patch("differential_diffusion", strength=1.0)
    elif additional in {"Fooocus Inpaint", "Fooocus Inpaint + DD"}:
        latent = await vae.encode_for_inpaint(
            image, mask, grow_mask_by=int(grow_mask_by))
        model = (await _apply_fooocus_inpaint(
            model, latent, "fooocus_inpaint_head",
            "inpaint_v26 (1.32GB)",
        ))[0]
        if additional.endswith("+ DD"):
            positive, negative, latent = await vae.encode_inpaint_conditioning(
                image, mask, positive, negative, noise_mask=True)
            model = await model.patch(
                "differential_diffusion", strength=1.0)
    elif additional in {
        "Brushnet Random", "Brushnet Random + DD",
        "Brushnet Segmentation", "Brushnet Segmentation + DD",
    }:
        grown = mask
        if int(grow_mask_by) > 0:
            grown = await mask.grow(int(grow_mask_by), False)
        family = await model.family()
        brush_mode = (
            "brushnet_random" if "Random" in additional
            else "brushnet_segmentation")
        selected = _BRUSHNET_WEIGHTS.get((brush_mode, family))
        if selected is None:
            raise ValueError(
                f"{additional} does not support model family {family!r}")
        brush_name = await _download_declared_weight(selected)
        brush_pipe = (await _apply_brushnet({
            "model": model,
            "vae": vae,
            "positive": positive,
            "negative": negative,
        }, image, grown, brush_name))[0]
        model = brush_pipe["model"]
        positive = brush_pipe["positive"]
        negative = brush_pipe["negative"]
        latent = brush_pipe["samples"]
        if additional.endswith("+ DD"):
            positive, negative, latent = await vae.encode_inpaint_conditioning(
                image, grown, positive, negative, noise_mask=True)
            model = await model.patch(
                "differential_diffusion", strength=1.0)
    else:
        raise ValueError(
            f"unknown easy kSamplerInpainting additional mode {additional!r}")

    source.update({
        "model": model,
        "positive": positive,
        "negative": negative,
        "samples": latent,
        "images": image,
        "vae": vae,
    })
    return await _sample_pipe(
        source,
        node_id="easy kSamplerInpainting",
        model=model,
        positive=positive,
        negative=negative,
        latent=latent,
        vae=vae,
        **kwargs,
    )


async def _unsampler(
    cfg, sampler_name, steps, end_at_step, scheduler, normalize, pipe=None,
    optional_model=None, optional_positive=None, optional_negative=None,
    optional_latent=None, **_kwargs,
):
    source = dict(pipe or {})
    model = optional_model if optional_model is not None else source.get("model")
    positive = (
        optional_positive
        if optional_positive is not None else source.get("positive")
    )
    negative = (
        optional_negative
        if optional_negative is not None else source.get("negative")
    )
    latent = (
        optional_latent
        if optional_latent is not None else source.get("samples")
    )
    missing = [
        name for name, value in {
            "model": model,
            "positive": positive,
            "negative": negative,
            "latent": latent,
        }.items() if value is None
    ]
    if missing:
        raise ValueError(
            "easy unSampler is missing " + ", ".join(missing)
        )
    result = await _ctx().unsample(
        latent=latent,
        steps=int(steps),
        model=model,
        positive=positive,
        negative=negative,
        cfg=float(cfg),
        sampler_name=str(sampler_name),
        scheduler=str(scheduler),
        end_at_step=int(end_at_step),
        normalize=str(normalize) == "enable",
    )
    source["samples"] = result
    return source, result


def _xy_handler(node_id: str):
    async def execute(**kwargs):
        spec: dict[str, Any] = {"node": node_id}
        if "batch_count" in kwargs and any(
            key in kwargs for key in ("first_cfg", "first_denoise", "first_guidance")
        ):
            first_key = next(key for key in ("first_cfg", "first_denoise", "first_guidance") if key in kwargs)
            last_key = first_key.replace("first_", "last_")
            spec["values"] = np.linspace(
                float(kwargs[first_key]), float(kwargs[last_key]),
                int(kwargs["batch_count"])
            ).tolist()
        elif "batch_count" in kwargs and "first_step" in kwargs:
            spec["values"] = np.rint(np.linspace(
                int(kwargs["first_step"]), int(kwargs["last_step"]),
                int(kwargs["batch_count"])
            )).astype(int).tolist()
        elif node_id.endswith("Seeds++ Batch"):
            spec["values"] = list(range(int(kwargs["batch_count"])))
        elif node_id.endswith("PositiveCond"):
            spec["values"] = [kwargs.get(f"positive_{index}") for index in range(1, 5) if kwargs.get(f"positive_{index}") is not None]
        elif node_id.endswith("NegativeCond"):
            spec["values"] = [kwargs.get(f"negative_{index}") for index in range(1, 5) if kwargs.get(f"negative_{index}") is not None]
        elif node_id.endswith("PositiveCondList"):
            spec["values"] = kwargs.get("positive")
        elif node_id.endswith("NegativeCondList"):
            spec["values"] = kwargs.get("negative")
        else:
            spec["values"] = {key: value for key, value in kwargs.items()}
        return _one(spec)
    return execute


_PRESAMPLING_HANDLERS = {
    "easy preSampling": _presampling,
    "easy preSamplingAdvanced": _presampling,
    "easy preSamplingCascade": _presampling,
    "easy preSamplingCustom": _presampling,
    "easy preSamplingDynamicCFG": _presampling_dynamic_cfg,
    "easy preSamplingNoiseIn": _presampling,
    "easy preSamplingSdTurbo": _presampling,
    "easy preSamplingLayerDiffusionADDTL": _presampling_layer_additional,
    "easy preSamplingLayerDiffusion": _presampling_layer_diffusion,
    "dynamicThresholdingFull": _dynamic_thresholding_full,
}

_SAMPLER_HANDLERS = {
    node_id: _sampler(node_id)
    for node_id in {
        "easy kSampler", "easy fullkSampler", "easy kSamplerCustom",
        "easy kSamplerSDTurbo", "easy cascadeKSampler", "easy fullCascadeKSampler",
    }
}
_SAMPLER_HANDLERS.update({
    "easy unSampler": _unsampler,
    "easy kSamplerDownscaleUnet": _sampler("easy kSamplerDownscaleUnet"),
    "easy kSamplerInpainting": _inpainting_sampler,
    "easy kSamplerLayerDiffusion": _layer_diffusion_sampler,
    "easy kSamplerTiled": _sampler("easy kSamplerTiled"),
})

_XYPLOT_HANDLERS = {
    node_id: _xy_handler(node_id)
    for node_id, value in SCHEMAS.items()
    if value["module"] == "py.nodes.xyplot"
}


# -------------------------------------------------------------------------
# Compatibility nodes whose safe behavior is either pure data or explicit.
# -------------------------------------------------------------------------

async def _deprecated_if(**kwargs):
    return _one(kwargs.get("if") if kwargs.get("any") else kwargs.get("else"))


async def _latent_composite_masked_with_cond(
    pipe, text_combine, source_latent, source_mask, destination_mask,
    text_combine_mode="add", replace_text="", **_kwargs,
):
    source = dict(pipe)
    clip = source.get("clip")
    destination_latent = source.get("samples")
    base_conditioning = source.get("positive")
    if clip is None or destination_latent is None or base_conditioning is None:
        raise ValueError(
            "Easy latent composite needs clip, samples, and positive conditioning")
    if not isinstance(text_combine, (list, tuple)):
        raise TypeError("Easy text_combine must be a list")
    if len(text_combine) > 4096:
        raise ValueError("Easy text_combine exceeds 4096 entries")
    mode = str(text_combine_mode)
    if mode not in {"add", "replace", "cover"}:
        raise ValueError("Easy text_combine_mode must be add, replace, or cover")

    settings = dict(source.get("loader_settings") or {})
    base_prompt = str(settings.get("positive", ""))
    replace_text = str(replace_text)
    source_conditioning = await base_conditioning.with_mask(
        source_mask, strength=1.0, set_area_to_bounds=False)
    conditionings = []
    positive_text = None
    for item in text_combine:
        item = str(item)
        if len(item) > 32768:
            raise ValueError("Easy regional prompt exceeds 32768 characters")
        if mode == "cover":
            positive_text = item
        elif mode == "replace" and replace_text:
            positive_text = base_prompt.replace(replace_text, item)
        else:
            positive_text = f"{base_prompt},{item}"
        encoded = await clip.encode(positive_text)
        destination_conditioning = await encoded.with_mask(
            destination_mask, strength=1.0, set_area_to_bounds=False)
        conditionings.append(
            await source_conditioning.combine(destination_conditioning))

    samples = await destination_latent.composite(
        source_latent, x=0, y=0, resize_source=False)
    if positive_text is not None:
        settings["positive"] = positive_text
    source["samples"] = samples
    source["loader_settings"] = settings
    return source, samples, conditionings


async def _image_to_mask(image, channel="red", **_kwargs):
    value = await _raw(image)
    index = {"red": 0, "green": 1, "blue": 2}[channel]
    return _one(value[..., index])


async def _inject_noise(
    strength, normalize, average, pipe_to_noise=None, image_to_latent=None,
    latent=None, noise=None, mask=None, mix_randn_amount=0, seed=123,
    **_kwargs,
):
    pipe = pipe_to_noise or {}
    if noise is None:
        noise = pipe.get("samples")
    if noise is None:
        raise ValueError("easy injectNoiseToLatent needs a noise latent")
    noise_value = await _raw(noise)
    if image_to_latent is not None:
        vae = pipe.get("vae")
        if vae is None:
            raise ValueError("image_to_latent needs a VAE in pipe_to_noise")
        latent = await vae.encode(image_to_latent)
    latent_value = await _raw(latent) if latent is not None else {
        "samples": noise_value["samples"].clone()
    }
    samples = dict(latent_value)
    base = samples["samples"].clone()
    noise_tensor = noise_value["samples"]
    if base.shape != noise_tensor.shape:
        raise ValueError("latent and noise shapes must match")
    result = (base + noise_tensor) / 2 if average else base + noise_tensor * float(strength)
    if normalize:
        result = result / result.std().clamp_min(1e-8)
    if mask is not None:
        mask_value = await _raw(mask)
        mask_value = torch.nn.functional.interpolate(
            mask_value.reshape((-1, 1, *mask_value.shape[-2:])),
            size=result.shape[-2:], mode="bilinear",
        ).expand(-1, result.shape[1], -1, -1)
        if len(mask_value) < len(result):
            mask_value = mask_value.repeat(math.ceil(len(result) / len(mask_value)), 1, 1, 1)[:len(result)]
        result = mask_value * result + (1 - mask_value) * base
    mix = float(mix_randn_amount)
    if mix > 0:
        generator = torch.Generator(device="cpu").manual_seed(int(seed))
        random_noise = torch.randn(result.shape, generator=generator, dtype=result.dtype)
        result = ((1 - mix) * result + mix * random_noise) / math.sqrt(mix * mix + (1 - mix) ** 2)
    samples["samples"] = result
    return _one(samples)


async def _latent_noisy(pipe=None, optional_latent=None, seed=0,
                        start_at_step=0, end_at_step=1, steps=1, **_kwargs):
    source = dict(pipe or {})
    if optional_latent is None:
        settings = source.get("loader_settings", {})
        width = int(settings.get("empty_latent_width", 512))
        height = int(settings.get("empty_latent_height", 512))
        batch = int(settings.get("batch_size", 1))
        generator = torch.Generator().manual_seed(int(seed))
        value = {"samples": torch.randn((batch, 4, height // 8, width // 8), generator=generator)}
    else:
        value = await _raw(optional_latent)
    sigma = max(0.0, (min(int(end_at_step), int(steps)) - int(start_at_step)) / max(1, int(steps)))
    result = dict(value)
    result["samples"] = result["samples"] * sigma
    source["samples"] = result
    return source, result, float(sigma)


async def _save_image_lazy(images, filename_prefix="ComfyUI", **_kwargs):
    display = await _ctx().output.save_images(images, filename_prefix=str(filename_prefix))
    return {"ui": display, "result": (images,)}


async def _show_spent(pipe, **_kwargs):
    value = str((pipe or {}).get("loader_settings", {}).get("spent_time", ""))
    return {"ui": {"text": [value]}, "result": ()}


async def _pre_detailer(pipe, **kwargs):
    source = dict(pipe)
    source["images"] = kwargs.get("optional_image") or source.get("images")
    source["detail_fix_settings"] = {
        key: value for key, value in kwargs.items()
        if key not in {"pipe", "optional_image", "bbox_segm_pipe", "sam_pipe"}
    }
    if kwargs.get("bbox_segm_pipe") is not None:
        source["bbox_segm_pipe"] = kwargs["bbox_segm_pipe"]
    if kwargs.get("sam_pipe") is not None:
        source["sam_pipe"] = kwargs["sam_pipe"]
    return _one(source)


async def _pre_mask_detailer(pipe, mask, **kwargs):
    source = dict(pipe)
    source["images"] = kwargs.get("optional_image") or source.get("images")
    source["mask"] = mask
    if kwargs.get("seed") is not None:
        source["seed"] = int(kwargs["seed"])
    source["detail_fix_settings"] = {
        key: value for key, value in kwargs.items()
        if key not in {
            "pipe", "optional_image", "mask_mode", "inpaint_model",
            "noise_mask_feather",
        }
    }
    source["mask_settings"] = {
        "mask_mode": bool(kwargs.get("mask_mode", True)),
        "inpaint_model": bool(kwargs.get("inpaint_model", False)),
        "noise_mask_feather": int(kwargs.get("noise_mask_feather", 20)),
    }
    return _one(source)


def _detailer_soft_mask(mask: torch.Tensor, radius: int) -> torch.Tensor:
    mask = mask.float().clamp(0.0, 1.0)
    radius = max(0, min(100, int(radius)))
    if radius == 0:
        return mask
    sigma = max(radius / 3.0, 0.5)
    coordinates = torch.arange(
        -radius, radius + 1, dtype=torch.float32, device=mask.device)
    kernel = torch.exp(-(coordinates ** 2) / (2.0 * sigma * sigma))
    kernel = kernel / kernel.sum()
    value = mask.unsqueeze(1)
    value = torch.nn.functional.conv2d(
        value, kernel.view(1, 1, 1, -1), padding=(0, radius))
    value = torch.nn.functional.conv2d(
        value, kernel.view(1, 1, -1, 1), padding=(radius, 0))
    return value[:, 0].clamp(0.0, 1.0)


def _detailer_box(
    mask: torch.Tensor, crop_factor: float, image_width: int,
    image_height: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int]] | None:
    points = torch.nonzero(mask > 0, as_tuple=False)
    if not len(points):
        return None
    top, left = points.min(dim=0).values.tolist()
    bottom, right = (points.max(dim=0).values + 1).tolist()
    bbox_width, bbox_height = int(right - left), int(bottom - top)
    factor = max(1.0, min(10.0, float(crop_factor)))
    target_width = max(1, round(bbox_width * factor))
    target_height = max(1, round(bbox_height * factor))
    center_x, center_y = (left + right) / 2.0, (top + bottom) / 2.0
    crop_left = max(0, round(center_x - target_width / 2.0))
    crop_top = max(0, round(center_y - target_height / 2.0))
    crop_right = min(image_width, crop_left + target_width)
    crop_bottom = min(image_height, crop_top + target_height)
    crop_left = max(0, crop_right - target_width)
    crop_top = max(0, crop_bottom - target_height)
    return (
        (int(crop_left), int(crop_top), int(crop_right), int(crop_bottom)),
        (bbox_width, bbox_height),
    )


def _detailer_target_size(
    crop_width: int, crop_height: int, bbox_size: tuple[int, int],
    guide_size: float, guide_size_for: bool, max_size: float,
) -> tuple[int, int]:
    basis = max(bbox_size if guide_size_for else (crop_width, crop_height))
    factor = float(guide_size) / max(1.0, float(basis))
    width = max(8, round(crop_width * factor / 8.0) * 8)
    height = max(8, round(crop_height * factor / 8.0) * 8)
    largest = max(width, height)
    limit = max(64.0, float(max_size))
    if largest > limit:
        factor = limit / largest
        width = max(8, math.floor(width * factor / 8.0) * 8)
        height = max(8, math.floor(height * factor / 8.0) * 8)
    return int(width), int(height)


async def _detailer_latent_with_mask(latent, mask: torch.Tensor):
    value = dict(await _raw(latent))
    value["noise_mask"] = mask
    return await sdk.LatentRef.from_value(value)


async def _easy_mask_detailer(
    source: dict[str, Any], model, settings: dict[str, Any],
) -> tuple[torch.Tensor, list[torch.Tensor], list[torch.Tensor]]:
    image = source.get("images")
    mask = source.get("mask")
    vae = source.get("vae")
    positive = source.get("positive")
    negative = source.get("negative")
    missing = [
        name for name, value in {
            "images": image, "mask": mask, "vae": vae,
            "positive": positive, "negative": negative,
        }.items() if value is None
    ]
    if missing:
        raise ValueError(
            "easy detailerFix mask mode needs " + ", ".join(missing))
    pixels = torch.as_tensor(await _raw(image)).detach().cpu().float()
    masks = torch.as_tensor(await _raw(mask)).detach().cpu().float()
    if pixels.ndim != 4 or pixels.shape[-1] < 3 or pixels.shape[0] != 1:
        raise ValueError("easy detailerFix mask mode accepts one BHWC image")
    if masks.ndim == 2:
        masks = masks.unsqueeze(0)
    if masks.ndim == 4 and masks.shape[1] == 1:
        masks = masks[:, 0]
    if masks.ndim != 3:
        raise ValueError("easy detailerFix mask must be HW or BHW")
    if tuple(masks.shape[-2:]) != tuple(pixels.shape[1:3]):
        masks = common_upscale(
            masks.unsqueeze(1), pixels.shape[2], pixels.shape[1],
            "bilinear", "disabled")[:, 0]
    selected = masks.amax(dim=0)
    box_info = _detailer_box(
        selected, float(settings.get("crop_factor", 3.0)),
        int(pixels.shape[2]), int(pixels.shape[1]))
    if box_info is None:
        return pixels[..., :3], [], []
    (left, top, right, bottom), bbox_size = box_info
    if (bbox_size[0] <= int(settings.get("drop_size", 10))
            or bbox_size[1] <= int(settings.get("drop_size", 10))):
        return pixels[..., :3], [], []

    crop = pixels[:, top:bottom, left:right, :3].clone()
    crop_mask = selected[None, top:bottom, left:right].clone()
    target_width, target_height = _detailer_target_size(
        right - left, bottom - top, bbox_size,
        float(settings.get("guide_size", 384)),
        bool(settings.get("guide_size_for", True)),
        float(settings.get("max_size", 1024)),
    )
    encoded_pixels = _scale_image(
        crop, target_width, target_height, "disabled", "lanczos")
    encoded_mask = common_upscale(
        crop_mask.unsqueeze(1), target_width, target_height,
        "bilinear", "disabled")[:, 0].clamp(0.0, 1.0)
    mask_settings = dict(source.get("mask_settings") or {})
    mask_mode = bool(mask_settings.get("mask_mode", True))
    inpaint_model = bool(mask_settings.get("inpaint_model", False))
    noise_feather = int(mask_settings.get("noise_mask_feather", 20))
    sample_mask = _detailer_soft_mask(encoded_mask, noise_feather)
    paste_mask = _detailer_soft_mask(
        crop_mask, int(settings.get("feather", 5)))
    detail_model = model
    if mask_mode and noise_feather > 0 and not inpaint_model:
        detail_model = await model.patch(
            "differential_diffusion", strength=1.0)

    batch_size = max(1, min(100, int(settings.get("batch_size", 1))))
    cycles = max(1, min(10, int(settings.get("cycle", 1))))
    output_images: list[torch.Tensor] = []
    enhanced: list[torch.Tensor] = []
    enhanced_alpha: list[torch.Tensor] = []
    for batch_index in range(batch_size):
        image_ref = await sdk.ImageRef._from_raw(encoded_pixels)
        if inpaint_model:
            mask_ref = await sdk.MaskRef._from_raw(sample_mask)
            sampled_positive, sampled_negative, latent = (
                await vae.encode_inpaint_conditioning(
                    image_ref, mask_ref, positive, negative,
                    noise_mask=mask_mode))
        else:
            sampled_positive, sampled_negative = positive, negative
            latent = await vae.encode(image_ref)
            if mask_mode:
                latent = await _detailer_latent_with_mask(latent, sample_mask)
        for cycle_index in range(cycles):
            latent = await _ctx().sample(
                latent=latent,
                steps=int(settings.get("steps", 20)),
                model=detail_model,
                positive=sampled_positive,
                negative=sampled_negative,
                cfg=float(settings.get("cfg", 8.0)),
                seed=int(settings.get("seed", source.get("seed", 0) or 0))
                + batch_index + cycle_index,
                sampler_name=str(settings.get("sampler_name", "euler")),
                scheduler=str(settings.get("scheduler", "normal")),
                denoise=float(settings.get("denoise", 0.5)),
                force_full_denoise=True,
            )
        decoded = torch.as_tensor(
            await _raw(await vae.decode(latent))).detach().cpu().float()
        decoded = _scale_image(
            decoded[..., :3], right - left, bottom - top,
            "disabled", "lanczos")
        composite = pixels[..., :3].clone()
        alpha = paste_mask.unsqueeze(-1)
        target = composite[:, top:bottom, left:right, :]
        target[:] = decoded * alpha + target * (1.0 - alpha)
        output_images.append(composite)
        enhanced.append(decoded)
        enhanced_alpha.append(torch.cat((decoded, alpha), dim=-1))
    return torch.cat(output_images, dim=0), enhanced, enhanced_alpha


async def _easy_detector_detailer(
    source: dict[str, Any], model, settings: dict[str, Any],
) -> tuple[torch.Tensor, list[torch.Tensor], list[torch.Tensor]]:
    image = source.get("images")
    detector_pipe = source.get("bbox_segm_pipe")
    if image is None or not isinstance(detector_pipe, dict):
        raise ValueError(
            "easy detailerFix detector mode needs images and bbox_segm_pipe")
    detector = detector_pipe.get("detector")
    if detector is None:
        raise ValueError("easy detailerFix detector pipe has no detector")
    detections = await detector.detect(
        image,
        threshold=float(detector_pipe.get("threshold", 0.5)),
        class_name=str(detector_pipe.get("class_name", "all")),
        max_detections=100,
    )
    pixels = torch.as_tensor(await _raw(image)).detach().cpu().float()
    if pixels.ndim != 4 or pixels.shape[0] != 1 or pixels.shape[-1] < 3:
        raise ValueError("easy detailerFix detector mode accepts one BHWC image")
    if not detections or not detections[0]:
        return pixels[..., :3], [], []
    height, width = map(int, pixels.shape[1:3])
    dilation = int(detector_pipe.get("dilation", 0))
    sam_pipe = source.get("sam_pipe")
    sam_model = sam_pipe.get("sam_model") if isinstance(sam_pipe, dict) else None
    sam_expansion = (
        int(sam_pipe.get("bbox_expansion", 0))
        if isinstance(sam_pipe, dict) else 0
    )
    boxes: list[list[float]] = []
    for detection in detections[0]:
        expansion = dilation + sam_expansion
        left = max(0, math.floor(float(detection["x"])) - expansion)
        top = max(0, math.floor(float(detection["y"])) - expansion)
        right = min(
            width,
            math.ceil(float(detection["x"]) + float(detection["width"]))
            + expansion,
        )
        bottom = min(
            height,
            math.ceil(float(detection["y"]) + float(detection["height"]))
            + expansion,
        )
        if right > left and bottom > top:
            boxes.append([float(left), float(top), float(right), float(bottom)])
    if not boxes:
        return pixels[..., :3], [], []

    masks: list[torch.Tensor] = []
    if sam_model is not None:
        mask_ref, scores = await sam_model.segment(image, boxes)
        candidates = torch.as_tensor(await _raw(mask_ref)).detach().cpu().float()
        threshold = float(sam_pipe.get("threshold", 0.93))
        for index in range(len(boxes)):
            query_scores = scores[index]
            best = max(range(len(query_scores)), key=query_scores.__getitem__)
            mask = candidates[index, best]
            masks.append(mask if query_scores[best] >= threshold else mask * 0.0)
    else:
        for left, top, right, bottom in boxes:
            mask = torch.zeros((height, width), dtype=torch.float32)
            mask[int(top):int(bottom), int(left):int(right)] = 1.0
            masks.append(mask)

    current = pixels[..., :3]
    enhanced: list[torch.Tensor] = []
    enhanced_alpha: list[torch.Tensor] = []
    detail_settings = {
        **settings,
        "crop_factor": float(detector_pipe.get("crop_factor", 3.0)),
    }
    for mask in masks:
        if not bool(torch.any(mask > 0)):
            continue
        current_ref = await sdk.ImageRef._from_raw(current[:1])
        mask_ref = await sdk.MaskRef._from_raw(mask.unsqueeze(0))
        detail_source = {
            **source,
            "images": current_ref,
            "mask": mask_ref,
            "mask_settings": {
                "mask_mode": bool(settings.get("noise_mask", True)),
                "inpaint_model": False,
                "noise_mask_feather": int(settings.get("feather", 5)),
            },
        }
        detailed, crops, alpha_crops = await _easy_mask_detailer(
            detail_source, model, detail_settings)
        current = detailed[:1]
        enhanced.extend(crops)
        enhanced_alpha.extend(alpha_crops)
    return current, enhanced, enhanced_alpha


async def _easy_detailer_fix(
    pipe, image_output="Preview", save_prefix="ComfyUI", model=None,
    **_kwargs,
):
    source = dict(pipe or {})
    model = model or source.get("model")
    if model is None:
        raise ValueError("easy detailerFix needs a model")
    settings = dict(source.get("detail_fix_settings") or {})
    if not settings:
        raise ValueError("easy detailerFix needs detail_fix_settings")
    if "mask_settings" in source:
        result, enhanced, enhanced_alpha = await _easy_mask_detailer(
            source, model, settings)
    else:
        result, enhanced, enhanced_alpha = await _easy_detector_detailer(
            source, model, settings)
    result_ref = await sdk.ImageRef._from_raw(result)
    source.update({
        "model": model,
        "images": result_ref,
        "samples": None,
        "loader_settings": {
            **dict(source.get("loader_settings") or {}),
            "spent_time": "Fix: secure-mask-detailer",
        },
    })
    ui: dict[str, Any] = {}
    output_mode = str(image_output)
    if output_mode in {"Save", "Hide&Save", "Sender&Save"}:
        ui = await _ctx().output.save_images(
            result_ref, filename_prefix=str(save_prefix))
    elif output_mode in {"Preview", "Sender"}:
        ui = await _ctx().ui.preview_images(result_ref)
    return {
        "ui": ui,
        "result": (source, result_ref, enhanced, enhanced_alpha),
    }


async def _easy_sam_loader(
    model_name, device_mode="AUTO", sam_detection_hint="center-1",
    sam_dilation=0, sam_threshold=0.93, sam_bbox_expansion=0,
    sam_mask_hint_threshold=0.7, sam_mask_hint_use_negative="False",
    **_kwargs,
):
    logical = str(model_name).replace("\\", "/").lstrip("/")
    lowered = logical.lower()
    if not lowered.endswith((".safetensors", ".sft")):
        raise ValueError(
            "easy samLoaderPipe accepts SafeTensor SAM weights only; legacy "
            ".pt/.pth files require executable pickle deserialization")
    stem = re.sub(r"\.(?:safetensors|sft)$", "", lowered)
    sam2 = {
        "sam2_hiera_tiny", "sam2_hiera_small", "sam2_hiera_base_plus",
        "sam2_hiera_large", "sam2.1_hiera_tiny", "sam2.1_hiera_small",
        "sam2.1_hiera_base_plus", "sam2.1_hiera_large",
    }
    if stem in sam2:
        architecture = stem
    elif "sam2" in stem:
        raise ValueError(
            "SAM2 filename must identify a supported Hiera architecture")
    elif "vit_h" in stem:
        architecture = "vit_h"
    elif "vit_l" in stem:
        architecture = "vit_l"
    else:
        architecture = "vit_b"
    mode = {
        "auto": "AUTO", "prefer gpu": "Prefer GPU", "cpu": "CPU",
    }.get(str(device_mode).strip().lower())
    if mode is None:
        raise ValueError("unknown Easy SAM device mode")
    sam_model = await _ctx().models.load_sam(
        logical, architecture=architecture, device_mode=mode)
    return _one({
        "sam_model": sam_model,
        "detection_hint": str(sam_detection_hint),
        "dilation": int(sam_dilation),
        "threshold": float(sam_threshold),
        "bbox_expansion": int(sam_bbox_expansion),
        "mask_hint_threshold": float(sam_mask_hint_threshold),
        "mask_hint_use_negative": str(sam_mask_hint_use_negative),
    })


async def _detailer_provider(node_id: str, **kwargs):
    pipe = dict(kwargs.get("pipe") or {})
    pipe[node_id] = {key: value for key, value in kwargs.items() if key != "pipe"}
    return _one(pipe)


def _provider(node_id: str):
    async def execute(**kwargs):
        return await _detailer_provider(node_id, **kwargs)
    return execute


async def _hires_fix(pipe=None, image=None, vae=None, rescale_after_model=True,
                     rescale_method="lanczos", rescale="by percentage",
                     percent=100, width=1024, height=1024, longer_side=1024,
                     crop="disabled", image_output="Hide", save_prefix="ComfyUI",
                     **_kwargs):
    source = dict(pipe or {})
    image = image or source.get("images")
    vae = vae or source.get("vae")
    if image is None or vae is None:
        raise ValueError("easy hiresFix needs an image and VAE")
    value = await _raw(image)
    if rescale_after_model:
        source_height, source_width = value.shape[1:3]
        if rescale == "by percentage":
            width = round(source_width * int(percent) / 100)
            height = round(source_height * int(percent) / 100)
        elif rescale == "to longer side - maintain aspect":
            factor = int(longer_side) / max(source_width, source_height)
            width, height = round(source_width * factor), round(source_height * factor)
        width, height = max(8, int(width) // 8 * 8), max(8, int(height) // 8 * 8)
        value = _scale_image(value, width, height, crop, rescale_method)
    image_ref = await sdk.ImageRef._from_raw(value)
    latent = await vae.encode(image_ref)
    source.update({"images": image_ref, "samples": latent, "vae": vae})
    ui = {}
    if image_output in ("Save", "Hide&Save", "Sender&Save"):
        ui = await _ctx().output.save_images(image_ref, filename_prefix=save_prefix)
    elif image_output in ("Preview", "Sender"):
        ui = await _ctx().ui.preview_images(image_ref)
    return {"ui": ui, "result": (source, value, latent)}


_SD3_ASPECT_RATIOS = {
    "16:9": (1344, 768),
    "1:1": (1024, 1024),
    "21:9": (1536, 640),
    "2:3": (832, 1216),
    "3:2": (1216, 832),
    "4:5": (896, 1152),
    "5:4": (1152, 896),
    "9:16": (768, 1344),
    "9:21": (640, 1536),
}


async def _stable_diffusion_3(
    positive, negative, model, aspect_ratio, seed, denoise,
    optional_image=None, **_kwargs,
):
    if str(model) not in {"sd3", "sd3-turbo"}:
        raise ValueError(f"unknown Stable Diffusion 3 model {model!r}")
    dimensions = _SD3_ASPECT_RATIOS.get(str(aspect_ratio))
    if dimensions is None:
        raise ValueError(f"unknown Stable Diffusion 3 aspect ratio {aspect_ratio!r}")
    denoise = float(denoise)
    if not math.isfinite(denoise) or not 0.0 <= denoise <= 1.0:
        raise ValueError("Stable Diffusion 3 denoise must be in [0, 1]")
    logical = await _download_declared_weight(_SD3_WEIGHT)
    loaded_model, clip, vae = await _ctx().models.load_checkpoint(logical)
    if clip is None or vae is None:
        raise RuntimeError(
            "the declared Stable Diffusion 3 checkpoint must include CLIP and VAE")
    positive_cond = await clip.encode(str(positive))
    negative_cond = await clip.encode(str(negative))
    if optional_image is None:
        latent = await sdk.LatentRef.empty(
            dimensions[0], dimensions[1], channels=16)
        sample_denoise = 1.0
    else:
        latent = await vae.encode(optional_image)
        sample_denoise = denoise
    turbo = str(model) == "sd3-turbo"
    sampled = await _ctx().sample(
        latent=latent,
        steps=8 if turbo else 30,
        model=loaded_model,
        positive=positive_cond,
        negative=negative_cond,
        cfg=1.0 if turbo else 5.45,
        seed=int(seed),
        sampler_name="euler",
        scheduler="sgm_uniform",
        denoise=sample_denoise,
        force_full_denoise=True,
    )
    return _one(await vae.decode(sampled))


async def _ultralytics_detector_pipe(
    model_name, bbox_threshold, bbox_dilation, bbox_crop_factor, **_kwargs,
):
    threshold = float(bbox_threshold)
    crop_factor = float(bbox_crop_factor)
    dilation = int(bbox_dilation)
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("Easy detector threshold must be in [0, 1]")
    if not -512 <= dilation <= 512:
        raise ValueError("Easy detector dilation must be in [-512, 512]")
    if not math.isfinite(crop_factor) or not 1.0 <= crop_factor <= 10.0:
        raise ValueError("Easy detector crop factor must be in [1, 10]")
    logical = await _download_declared_weight(_RT_DETR_WEIGHT)
    detector = await _ctx().models.load_object_detector(logical)
    requested = str(model_name or "")
    return _one({
        "detector": detector,
        "threshold": threshold,
        "dilation": dilation,
        "crop_factor": crop_factor,
        "class_name": (
            "person" if any(
                term in requested.lower() for term in ("face", "person")
            ) else "all"
        ),
        "requested_model": requested,
    })


_DEPRECATED_HANDLERS = {
    "easy if": _deprecated_if,
    "easy imageToMask": _image_to_mask,
    "easy injectNoiseToLatent": _inject_noise,
    "easy latentNoisy": _latent_noisy,
    "easy poseEditor": _no_output,
    "easy saveImageLazy": _save_image_lazy,
    "easy saveTextLazy": _save_text,
    "easy showAnythingLazy": _show,
    "easy showSpentTime": _show_spent,
    "easy latentCompositeMaskedWithCond": _latent_composite_masked_with_cond,
    "easy stableDiffusion3API": _stable_diffusion_3,
}

_FIX_HANDLERS = {
    "easy hiresFix": _hires_fix,
    "easy preDetailerFix": _pre_detailer,
    "easy preMaskDetailerFix": _pre_mask_detailer,
    "easy samLoaderPipe": _easy_sam_loader,
    "easy ultralyticsDetectorPipe": _ultralytics_detector_pipe,
    "easy detailerFix": _easy_detailer_fix,
}

for _node_id in set(SCHEMAS) - set(_ADAPTER_HANDLERS):
    if SCHEMAS[_node_id]["module"] == "py.nodes.adapter":
        _ADAPTER_HANDLERS[_node_id] = unsupported(
            _node_id,
            "this adapter installs guest callbacks into host models; it needs a closed core transform",
        )

_INPAINT_HANDLERS = {
    node_id: unsupported(
        node_id,
        "Easy inpaint patches currently require direct host model mutation",
    )
    for node_id, value in SCHEMAS.items()
    if value["module"] == "py.nodes.inpaint"
}


async def _apply_brushnet(
    pipe, image, mask, brushnet, dtype="float16", scale=1.0,
    start_at=0, end_at=10000, **_kwargs,
):
    source = dict(pipe or {})
    required = {
        "model": source.get("model"),
        "vae": source.get("vae"),
        "positive": source.get("positive"),
        "negative": source.get("negative"),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            "easy applyBrushNet needs " + ", ".join(missing) + " in the pipe")
    brushnet_model = await _ctx().models.load_brushnet(
        str(brushnet), dtype=str(dtype))
    model, positive, negative, latent = await brushnet_model.apply(
        required["model"], required["vae"], image, mask,
        required["positive"], required["negative"],
        scale=float(scale), start_step=int(start_at), end_step=int(end_at),
    )
    source.update({
        "model": model,
        "positive": positive,
        "negative": negative,
        "samples": latent,
    })
    return _one(source)


async def _apply_fooocus_inpaint(model, latent, head, patch, **_kwargs):
    if str(head) != "fooocus_inpaint_head":
        raise ValueError(f"unknown Easy Fooocus inpaint head {head!r}")
    selected = _FOOOCUS_PATCH_WEIGHTS.get(str(patch))
    if selected is None:
        raise ValueError(f"unknown Easy Fooocus inpaint patch {patch!r}")
    head_name = await _download_declared_weight(_FOOOCUS_HEAD_WEIGHT)
    patch_name = await _download_declared_weight(selected)
    return _one(await model.patch(
        "fooocus_inpaint",
        latent=latent,
        head=head_name,
        patch=patch_name,
    ))


async def _apply_powerpaint(
    pipe, image, mask, powerpaint_model=None, powerpaint_clip=None,
    dtype="float16", fitting=1.0, function="text guided", scale=1.0,
    start_at=0, end_at=10000, save_memory="none", **_kwargs,
):
    source = dict(pipe or {})
    required = {
        "model": source.get("model"),
        "vae": source.get("vae"),
        "positive": source.get("positive"),
        "negative": source.get("negative"),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            "easy applyPowerPaint needs " + ", ".join(missing)
            + " in the pipe")
    family = await required["model"].family()
    if family != "sd1":
        raise ValueError(
            f"PowerPaint v2.1 supports SD1 models, not {family!r}")

    if powerpaint_model in (None, "", "PowerPaint v2.1 (official)"):
        model_name = await _download_declared_weight(_POWERPAINT_MODEL_WEIGHT)
    else:
        model_name = _safe_asset_name(powerpaint_model)
    if powerpaint_clip in (
        None, "", "PowerPaint token encoder (official)",
    ):
        clip_name = await _download_declared_weight(_POWERPAINT_CLIP_WEIGHT)
    else:
        clip_name = _safe_asset_name(powerpaint_clip)
    base_name = await _download_declared_weight(
        _POWERPAINT_BASE_CLIP_WEIGHT)
    powerpaint = await _ctx().models.load_powerpaint(
        model_name, base_name, clip_name, dtype=str(dtype))
    model, positive, negative, latent = await powerpaint.apply(
        required["model"], required["vae"], image, mask,
        required["positive"], required["negative"],
        fitting=float(fitting), function=str(function), scale=float(scale),
        start_step=int(start_at), end_step=int(end_at),
        save_memory=str(save_memory),
    )
    source.update({
        "model": model,
        "positive": positive,
        "negative": negative,
        "samples": latent,
    })
    return _one(source)


async def _apply_inpaint(
    pipe, image, mask, inpaint_mode, encode, grow_mask_by,
    dtype="float16", fitting=1.0, function="text guided", scale=1.0,
    start_at=0, end_at=10000, noise_mask=True, **_kwargs,
):
    source = dict(pipe)
    mode = str(inpaint_mode)
    if mode not in {
        "normal", "fooocus_inpaint", "brushnet_random",
        "brushnet_segmentation", "powerpaint",
    }:
        raise ValueError(f"unknown easy applyInpaint mode {mode!r}")

    if mode.startswith("brushnet_"):
        model = source.get("model")
        if model is None:
            raise ValueError("easy applyInpaint BrushNet mode needs a model")
        family = await model.family()
        selected = _BRUSHNET_WEIGHTS.get((mode, family))
        if selected is None:
            raise ValueError(
                f"easy applyInpaint {mode!r} does not support model family "
                f"{family!r}")
        logical = await _download_declared_weight(selected)
        source = (await _apply_brushnet(
            source, image, mask, logical, dtype=dtype, scale=scale,
            start_at=start_at, end_at=end_at,
        ))[0]
    elif mode == "powerpaint":
        source = (await _apply_powerpaint(
            source, image, mask,
            dtype=dtype, fitting=fitting, function=function, scale=scale,
            start_at=start_at, end_at=end_at,
        ))[0]

    encode = str(encode)
    if encode == "none":
        pass
    else:
        vae = source.get("vae")
        if vae is None:
            raise ValueError("easy applyInpaint needs a VAE in the pipe")
        if encode == "vae_encode_inpaint":
            source["samples"] = await vae.encode_for_inpaint(
                image, mask, grow_mask_by=int(grow_mask_by))
        elif encode in {"inpaint_model_conditioning", "different_diffusion"}:
            positive = source.get("positive")
            negative = source.get("negative")
            if positive is None or negative is None:
                raise ValueError(
                    "easy applyInpaint conditioning mode needs positive and "
                    "negative")
            grown = mask
            if int(grow_mask_by) > 0:
                grown = await mask.grow(int(grow_mask_by), False)
            positive, negative, latent = await vae.encode_inpaint_conditioning(
                image, grown, positive, negative,
                noise_mask=bool(noise_mask))
            source.update({
                "positive": positive,
                "negative": negative,
                "samples": latent,
            })
        else:
            raise ValueError(f"unknown easy applyInpaint encode mode {encode!r}")

    if mode == "fooocus_inpaint":
        model = source.get("model")
        latent = source.get("samples")
        if model is None or latent is None:
            raise ValueError(
                "easy applyInpaint Fooocus mode needs model and samples in "
                "the pipe")
        source["model"] = (await _apply_fooocus_inpaint(
            model, latent, "fooocus_inpaint_head",
            "inpaint_v26 (1.32GB)",
        ))[0]
    if encode == "different_diffusion":
        model = source.get("model")
        if model is None:
            raise ValueError("easy applyInpaint different_diffusion needs a model")
        source["model"] = await model.patch(
            "differential_diffusion", strength=1.0)
    return _one(source)


_INPAINT_HANDLERS["easy applyBrushNet"] = _apply_brushnet
_INPAINT_HANDLERS["easy applyFooocusInpaint"] = _apply_fooocus_inpaint
_INPAINT_HANDLERS["easy applyPowerPaint"] = _apply_powerpaint
_INPAINT_HANDLERS["easy applyInpaint"] = _apply_inpaint

_API_HANDLERS = {
    "easy joyCaption2API": _joy_caption,
    "easy joyCaption3API": _joy_caption,
}


_HANDLERS: dict[str, tuple[Any, tuple[str, ...]]] = {}
for _group in (
    _LOGIC_HANDLERS, _PROMPT_HANDLERS, _SEED_HANDLERS, _UTIL_HANDLERS,
    _IMAGE_HANDLERS, _LOADER_HANDLERS, _PIPE_HANDLERS, _ADAPTER_HANDLERS,
    _PRESAMPLING_HANDLERS, _SAMPLER_HANDLERS, _XYPLOT_HANDLERS,
    _DEPRECATED_HANDLERS, _FIX_HANDLERS, _INPAINT_HANDLERS, _API_HANDLERS,
):
    for _node_id, _handler in _group.items():
        if _node_id in _HANDLERS:
            raise RuntimeError(f"duplicate Easy secure handler for {_node_id}")
        _HANDLERS[_node_id] = (_handler, ())


def _permissions(node_ids, *permissions):
    for node_id in node_ids:
        handler, _old = _HANDLERS[node_id]
        _HANDLERS[node_id] = (handler, tuple(permissions))


_permissions({
    "easy isMaskEmpty", "easy isNone", "easy lengthAnything",
    "easy indexAnything", "easy batchAnything", "easy showAnything",
    "easy showTensorShape",
}, "raw")
_permissions({"easy cleanGpuUsed"}, "models.manage")
_permissions({"easy saveText"}, "output")
_permissions({"easy isFileExist"}, "assets")
_permissions({"easy tableEditor"}, "raw")

_UNSUPPORTED_IMAGE_IDS = set()
_permissions(
    set(_IMAGE_HANDLERS) - _UNSUPPORTED_IMAGE_IDS - {
        "easy imageSave", "easy imagesCountInDirectory", "easy loadImagesForLoop",
        "easy loadImageBase64",
    },
    "raw",
)
_permissions({"easy imageSave"}, "output", "ui")
_permissions({"easy imagesCountInDirectory"}, "assets")
_permissions({"easy loadImagesForLoop"}, "assets", "raw")
_permissions({"easy removeLocalImage"}, "assets", "assets.delete")
_permissions({"easy loadImageBase64"}, "output", "raw", "ui")
_permissions(
    {"easy imageRemBg"}, "assets", "models", "output", "raw", "ui")
_permissions({"easy humanSegmentation"}, "models", "raw")
_permissions({"easy imageInterrogator"}, "models", "raw")
_permissions({"easy joyCaption2API", "easy joyCaption3API"}, "models", "raw")
_permissions({"easy imageChooser"}, "raw", "ui", "ui.interact")
_permissions({"easy promptAwait"}, "ui.interact")
_permissions({"easy wildcards", "easy wildcardsMatrix"}, "assets")
_permissions({"easy ab", "easy anythingInversedSwitch", "easy blocker"}, "graph.block")
_permissions({"easy whileLoopStart", "easy forLoopStart"}, "graph.block")
_permissions({"easy whileLoopEnd"}, "graph.expand")
_permissions({"easy forLoopEnd"}, "graph", "graph.expand")

_permissions(_LOADER_IDS, "assets", "models", "raw")
_permissions({
    "easy controlnetLoader", "easy controlnetLoaderADV",
    "easy controlnetLoader++", "easy LLLiteLoader",
}, "models")
_permissions({"easy controlnetStackApply"}, "models")
_permissions({"easy loraPromptApply", "easy loraStackApply"}, "assets")
_permissions({"easy icLightApply"}, "assets", "models", "raw")
_permissions({
    "easy ipadapterApply", "easy ipadapterApplyADV",
    "easy ipadapterStyleComposition", "easy ipadapterApplyEncoder",
    "easy ipadapterApplyFromParams", "easy ipadapterApplyFaceIDKolors",
    "easy instantIDApply", "easy instantIDApplyADV",
    "easy pulIDApply", "easy pulIDApplyADV",
}, "models")
_permissions({"easy pipeBatchIndex"}, "raw")
_permissions(set(_SAMPLER_HANDLERS) & {
    "easy kSampler", "easy fullkSampler", "easy kSamplerCustom",
    "easy kSamplerSDTurbo", "easy cascadeKSampler", "easy fullCascadeKSampler",
    "easy kSamplerTiled", "easy kSamplerDownscaleUnet",
    "easy kSamplerInpainting", "easy kSamplerLayerDiffusion",
}, "output", "sample", "ui")
_permissions({"easy unSampler"}, "sample")
_permissions(
    {"easy kSamplerLayerDiffusion"},
    "models", "output", "sample", "ui",
)
_permissions(
    {"easy kSamplerInpainting"},
    "models", "output", "sample", "ui",
)
_permissions({
    "easy applyBrushNet", "easy applyFooocusInpaint",
    "easy applyPowerPaint", "easy applyInpaint",
}, "models")

_permissions({"easy hiresFix"}, "output", "raw", "ui")
_permissions({"easy samLoaderPipe"}, "models")
_permissions({"easy ultralyticsDetectorPipe"}, "models")
_permissions({"easy detailerFix"}, "output", "raw", "sample", "ui")
_permissions({
    "easy imageToMask", "easy injectNoiseToLatent", "easy latentNoisy",
    "easy showAnythingLazy",
}, "raw")
_permissions({"easy saveImageLazy"}, "output")
_permissions({"easy saveTextLazy"}, "output")
_permissions({"easy stableDiffusion3API"}, "models", "sample")

if set(_HANDLERS) != set(SCHEMAS):
    raise RuntimeError(
        "Easy Use secure conversion coverage changed: "
        f"missing={sorted(set(SCHEMAS) - set(_HANDLERS))}, "
        f"extra={sorted(set(_HANDLERS) - set(SCHEMAS))}"
    )


_LAZY_STATUS = {
    "easy anythingIndexSwitch": _index_switch_lazy("value"),
    "easy imageIndexSwitch": _index_switch_lazy("image"),
    "easy textIndexSwitch": _index_switch_lazy("text"),
    "easy conditioningIndexSwitch": _index_switch_lazy("cond"),
    "easy ifElse": _if_else_lazy,
}


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(
        node_id,
        handler,
        permissions=permissions,
        required_weights=(
            tuple(_IC_LIGHT_WEIGHTS.values())
            if node_id == "easy icLightApply"
            else _IPADAPTER_REQUIRED_WEIGHTS
            if node_id in {
                "easy ipadapterApply", "easy ipadapterApplyADV",
                "easy ipadapterStyleComposition",
                "easy ipadapterApplyEncoder",
                "easy ipadapterApplyFromParams",
                "easy ipadapterApplyFaceIDKolors",
                "easy instantIDApply", "easy instantIDApplyADV",
                "easy pulIDApply", "easy pulIDApplyADV",
            }
            else _FOOOCUS_REQUIRED_WEIGHTS
            if node_id == "easy applyFooocusInpaint"
            else _POWERPAINT_REQUIRED_WEIGHTS
            if node_id == "easy applyPowerPaint"
            else (
                _BRUSHNET_REQUIRED_WEIGHTS
                + _FOOOCUS_REQUIRED_WEIGHTS
                + _POWERPAINT_REQUIRED_WEIGHTS
            )
            if node_id == "easy applyInpaint"
            else (_BRUSHNET_REQUIRED_WEIGHTS + _FOOOCUS_REQUIRED_WEIGHTS)
            if node_id == "easy kSamplerInpainting"
            else _LAYER_DIFFUSION_REQUIRED_WEIGHTS
            if node_id == "easy kSamplerLayerDiffusion"
            else _SEGFORMER_REQUIRED_WEIGHTS
            if node_id == "easy humanSegmentation"
            else (_IMAGE_INTERROGATOR_WEIGHT,)
            if node_id in {
                "easy imageInterrogator", "easy joyCaption2API",
                "easy joyCaption3API",
            }
            else (_SD3_WEIGHT,)
            if node_id == "easy stableDiffusion3API"
            else (_RT_DETR_WEIGHT,)
            if node_id == "easy ultralyticsDetectorPipe"
            else ()),
        check_lazy_status=_LAZY_STATUS.get(node_id),
        module=__name__,
    )
    for node_id, (handler, permissions) in _HANDLERS.items()
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: SCHEMAS[node_id]["schema"]["attrs"]["display_name"]
    for node_id in NODE_CLASS_MAPPINGS
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
