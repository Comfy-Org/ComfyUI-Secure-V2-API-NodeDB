"""Secure Nodes 2.0 implementations for Efficiency Nodes' pinned surface.

The original pack mixes workflow data helpers with global monkey patches,
filesystem scans, model loading and sampling.  This module keeps the workflow
algorithms here while expressing host-owned work through small SDK operations.
"""
from __future__ import annotations

import ast
import copy
import math
import operator
import posixpath
import random
import re
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont, ImageOps

from ._secure_runtime import SCHEMAS, bind_node, sdk


_NATIVE_SCHEDULERS = {
    "normal", "karras", "exponential", "sgm_uniform", "simple",
    "ddim_uniform", "beta", "linear_quadratic", "kl_optimal",
}
_MODEL_EXTENSIONS = {
    "checkpoints": {".safetensors", ".ckpt"},
    "loras": {".safetensors", ".ckpt"},
    "vae": {".safetensors", ".ckpt", ".pt"},
}


def _frozen_combo_options(node_id: str, input_id: str) -> frozenset[str]:
    """Read one immutable option list captured from the pinned upstream UI."""
    for item in SCHEMAS[node_id]["schema"]["inputs"]:
        attrs = item.get("attrs", {})
        if attrs.get("id") == input_id:
            return frozenset(str(value) for value in attrs.get("options", ()))
    return frozenset()


_SAMPLER_OPTIONS = _frozen_combo_options(
    "XY Input: Sampler/Scheduler", "sampler_1"
) - {"None"}
_SCHEDULER_OPTIONS = _frozen_combo_options(
    "XY Input: Sampler/Scheduler", "scheduler_1"
) - {"None"}

_CITY96_REVISION = "99c65021fa947dfe3d71ec4e24793fe7533a3322"
_CITY96_HASHES = {
    ("v1", "1.25"): "13d41af7abb2b39b0c35742ac6d9e68137de933b188192bed9e00ff0f5dc6143",
    ("v1", "1.5"): "5681a6263c97a7b0b3c5051229d4438b270cff5ed95891a984e98cd193896a57",
    ("v1", "2.0"): "57ab5fe3429cafafe21aafe80c661ab2739ad837f58012a44e1f656670cd35f8",
    ("xl", "1.25"): "331db5b11494d4a3dd66f569d8c9531eca2302f4de4d03688665a62cc6a327de",
    ("xl", "1.5"): "af84a4cc658069c46115bb28bd156a798289dd42f3dc72f1da6cf8bb0760aef2",
    ("xl", "2.0"): "cedf7806b0b27f883ae3c0d0466d63594d431fa5468d7ef41e55a1bffe38fe1e",
}
_CITY96_WEIGHTS = {
    key: sdk.HuggingFaceWeight(
        repo_id="city96/SD-Latent-Upscaler",
        filename=f"latent-upscaler-v2.1_SD{key[0]}-x{key[1]}.safetensors",
        folder="latent_upscale_models",
        revision=_CITY96_REVISION,
        sha256=digest,
        on_demand=True,
    )
    for key, digest in _CITY96_HASHES.items()
}

_TTL_REVISION = "5f1b2c44497aeef555e44c9e1d035ad186fcecb2"
_TTL_FILENAMES = {
    "SD 1.x": (
        "src/comfyui/custom_nodes/efficiency-nodes-comfyui/py/sd15_resizer.pt",
        "8fa1cb8168b305d556f2e8178c820b0a6956f4ba84ebc9443fac69be43ffd6fe",
    ),
    "SDXL": (
        "src/comfyui/custom_nodes/efficiency-nodes-comfyui/py/sdxl_resizer.pt",
        "0bca261c96e136cb9e2f330f40386e6cbcaaf464cd39e9f7752c9e7b32e825e8",
    ),
}
_TTL_WEIGHTS = {
    version: sdk.HuggingFaceWeight(
        repo_id="Peter-Young/workerflux",
        filename=filename,
        folder="latent_upscale_models",
        revision=_TTL_REVISION,
        sha256=digest,
        on_demand=True,
    )
    for version, (filename, digest) in _TTL_FILENAMES.items()
}
_HIRES_REQUIRED_WEIGHTS = tuple((*_CITY96_WEIGHTS.values(), *_TTL_WEIGHTS.values()))


def _ctx():
    return sdk.ctx()


async def _download_declared_weight(weight: sdk.HuggingFaceWeight) -> str:
    """Request one sealed, hash-pinned declaration from the host cache."""
    return await _ctx().models.download_huggingface_weights(
        weight.repo_id,
        weight.filename,
        weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )


async def _load_declared_state(catalogue_name: str) -> dict[str, torch.Tensor]:
    asset = await _ctx().assets.resolve(
        "latent_upscale_models", _safe_asset_name(catalogue_name)
    )
    state = await _ctx().assets.load_state_dict(asset)
    if not isinstance(state, dict) or not state:
        raise ValueError("latent upscaler weight file did not contain a state dict")
    if not all(isinstance(key, str) and isinstance(value, torch.Tensor)
               for key, value in state.items()):
        raise ValueError("latent upscaler state dict contains unsupported values")
    return state


class _City96Upscaler(torch.nn.Module):
    """City96's published v2.1 architecture; orchestration stays pack-side."""

    def __init__(self, factor: float, depth: int = 16):
        super().__init__()
        layers: list[torch.nn.Module] = [
            torch.nn.Conv2d(4, 64, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Upsample(scale_factor=float(factor), mode="nearest"),
            torch.nn.ReLU(),
        ]
        for _index in range(int(depth)):
            layers.extend((
                torch.nn.Conv2d(64, 64, kernel_size=3, padding=1),
                torch.nn.ReLU(),
            ))
        layers.append(torch.nn.Conv2d(64, 4, kernel_size=3, padding=1))
        self.sequential = torch.nn.Sequential(*layers)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.sequential(value)


def _ttl_normalization(channels: int) -> torch.nn.Module:
    return torch.nn.GroupNorm(32, channels)


def _ttl_zero_module(module: torch.nn.Module) -> torch.nn.Module:
    for parameter in module.parameters():
        parameter.detach().zero_()
    return module


class _TtlAttentionBlock(torch.nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.norm = _ttl_normalization(channels)
        self.q = torch.nn.Conv2d(channels, channels, 1)
        self.k = torch.nn.Conv2d(channels, channels, 1)
        self.v = torch.nn.Conv2d(channels, channels, 1)
        self.proj_out = torch.nn.Conv2d(channels, channels, 1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        normalized = self.norm(value)
        q, k, v = (layer(normalized) for layer in (self.q, self.k, self.v))
        batch, channels, height, width = q.shape
        flatten = lambda item: item.flatten(2).transpose(1, 2).unsqueeze(1)
        attended = F.scaled_dot_product_attention(
            flatten(q), flatten(k), flatten(v)
        )
        attended = attended.squeeze(1).transpose(1, 2).reshape(
            batch, channels, height, width
        )
        return value + self.proj_out(attended)


class _TtlResidualBlock(torch.nn.Module):
    def __init__(
        self,
        channels: int,
        embedding_channels: int,
        dropout: float = 0.0,
        out_channels: int | None = None,
        use_conv: bool = False,
        use_scale_shift_norm: bool = False,
        kernel_size: int = 3,
    ):
        super().__init__()
        self.channels = channels
        self.out_channels = out_channels or channels
        self.use_scale_shift_norm = use_scale_shift_norm
        padding = kernel_size // 2
        self.in_layers = torch.nn.Sequential(
            _ttl_normalization(channels),
            torch.nn.SiLU(),
            torch.nn.Conv2d(
                channels, self.out_channels, kernel_size, padding=padding
            ),
        )
        embedding_outputs = (
            2 * self.out_channels if use_scale_shift_norm else self.out_channels
        )
        self.emb_layers = torch.nn.Sequential(
            torch.nn.SiLU(),
            torch.nn.Linear(embedding_channels, embedding_outputs),
        )
        self.out_layers = torch.nn.Sequential(
            _ttl_normalization(self.out_channels),
            torch.nn.SiLU(),
            torch.nn.Dropout(p=float(dropout)),
            _ttl_zero_module(torch.nn.Conv2d(
                self.out_channels,
                self.out_channels,
                kernel_size,
                padding=padding,
            )),
        )
        if self.out_channels == channels:
            self.skip_connection = torch.nn.Identity()
        elif use_conv:
            self.skip_connection = torch.nn.Conv2d(
                channels, self.out_channels, kernel_size, padding=padding
            )
        else:
            self.skip_connection = torch.nn.Conv2d(
                channels, self.out_channels, 1
            )

    def forward(
        self, value: torch.Tensor, embedding: torch.Tensor
    ) -> torch.Tensor:
        hidden = self.in_layers(value)
        embedding_out = self.emb_layers(embedding).to(hidden.dtype)
        while embedding_out.ndim < hidden.ndim:
            embedding_out = embedding_out[..., None]
        if self.use_scale_shift_norm:
            scale, shift = torch.chunk(embedding_out, 2, dim=1)
            hidden = self.out_layers[0](hidden) * (1 + scale) + shift
            hidden = self.out_layers[1:](hidden)
        else:
            hidden = self.out_layers(hidden + embedding_out)
        return self.skip_connection(value) + hidden


class _TtlLatentResizer(torch.nn.Module):
    def __init__(
        self,
        in_blocks: int,
        out_blocks: int,
        channels: int,
        *,
        attention: bool,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.conv_in = torch.nn.Conv2d(4, channels, 3, padding=1)
        embedding_channels = 32
        self.embed = torch.nn.Sequential(
            torch.nn.Linear(1, embedding_channels),
            torch.nn.SiLU(),
            torch.nn.Linear(embedding_channels, embedding_channels),
        )
        self.in_blocks = torch.nn.ModuleList()
        for index in range(in_blocks):
            if attention and index in {1, in_blocks - 1}:
                self.in_blocks.append(_TtlAttentionBlock(channels))
            self.in_blocks.append(_TtlResidualBlock(
                channels, embedding_channels, dropout
            ))
        self.out_blocks = torch.nn.ModuleList()
        for index in range(out_blocks):
            if attention and index in {1, out_blocks - 1}:
                self.out_blocks.append(_TtlAttentionBlock(channels))
            self.out_blocks.append(_TtlResidualBlock(
                channels, embedding_channels, dropout
            ))
        self.norm_out = _ttl_normalization(channels)
        self.conv_out = torch.nn.Conv2d(channels, 4, 3, padding=1)

    @classmethod
    def from_state_dict(
        cls, state: dict[str, torch.Tensor]
    ) -> "_TtlLatentResizer":
        try:
            channels = int(state["conv_in.bias"].shape[0])
        except (KeyError, IndexError) as exc:
            raise ValueError("TTL latent upscaler state dict is malformed") from exc
        in_max = out_max = -1
        in_attention = out_attention = 0
        for key in state:
            parts = key.split(".")
            if len(parts) < 2 or parts[0] not in {"in_blocks", "out_blocks"}:
                continue
            try:
                index = int(parts[1])
            except ValueError:
                continue
            if parts[0] == "in_blocks":
                in_max = max(in_max, index)
                if len(parts) > 3 and parts[2:4] == ["q", "weight"]:
                    in_attention += 1
            else:
                out_max = max(out_max, index)
                if len(parts) > 3 and parts[2:4] == ["q", "weight"]:
                    out_attention += 1
        in_blocks = in_max + 1 - in_attention
        out_blocks = out_max + 1 - out_attention
        if in_blocks <= 0 or out_blocks <= 0:
            raise ValueError("TTL latent upscaler block layout is malformed")
        model = cls(
            in_blocks,
            out_blocks,
            channels,
            attention=bool(in_attention or out_attention),
        )
        model.load_state_dict(state, strict=True)
        return model.eval()

    def forward(
        self, value: torch.Tensor, *, scale: float
    ) -> torch.Tensor:
        size = tuple(round(item * float(scale)) for item in value.shape[-2:])
        if size == value.shape[-2:]:
            return value
        scale_embedding = value.new_tensor([[float(scale) - 1.0]])
        embedding = self.embed(scale_embedding)
        hidden = self.conv_in(value)
        for block in self.in_blocks:
            hidden = (
                block(hidden, embedding)
                if isinstance(block, _TtlResidualBlock)
                else block(hidden)
            )
        hidden = F.interpolate(hidden, size=size, mode="bilinear")
        for block in self.out_blocks:
            hidden = (
                block(hidden, embedding)
                if isinstance(block, _TtlResidualBlock)
                else block(hidden)
            )
        return self.conv_out(F.silu(self.norm_out(hidden)))


def _safe_asset_name(value: Any, *, allow_empty: bool = False) -> str:
    name = str(value or "").replace("\\", "/").strip().strip("/")
    if not name and allow_empty:
        return ""
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or ":" in path.parts[0]
        or "://" in name
    ):
        raise ValueError("model names must stay inside a managed catalogue")
    return path.as_posix()


def _copy_stack(value: Any) -> list:
    return [tuple(item) if isinstance(item, (tuple, list)) else item for item in (value or ())]


def _floats(count: int, first: float, last: float) -> list[float]:
    count = int(count)
    if count <= 0:
        return []
    if count == 1:
        return [float(first)]
    step = (float(last) - float(first)) / (count - 1)
    return [round(float(first) + index * step, 3) for index in range(count)]


def _ints(count: int, first: int, last: int) -> list[int]:
    count = int(count)
    if count <= 0:
        return []
    if count == 1:
        return [int(first)]
    step = (int(last) - int(first)) / (count - 1)
    return sorted({int(int(first) + index * step) for index in range(count)})


async def _catalogue_batch(
    folder: str,
    prefix: str,
    *,
    recursive: bool,
    descending: bool,
    limit: int,
) -> list[str]:
    safe_prefix = _safe_asset_name(prefix, allow_empty=True)
    values = await _ctx().assets.list(folder, prefix=safe_prefix, recursive=recursive)
    extensions = _MODEL_EXTENSIONS[folder]
    result = []
    for value in values:
        logical = _safe_asset_name(value)
        if PurePosixPath(logical).suffix.lower() not in extensions:
            continue
        if not recursive and safe_prefix:
            relative = posixpath.relpath(logical, safe_prefix)
            if "/" in relative:
                continue
        result.append(logical)
    result.sort(reverse=descending)
    return result if int(limit) == -1 else result[: max(0, int(limit))]


def _script_copy(script: Any) -> dict[str, Any]:
    return dict(script or {})


# ---------------------------------------------------------------------------
# Safe expression nodes.
# ---------------------------------------------------------------------------

_MAX_EVAL_SEQUENCE = 100_000
_MAX_EVAL_POWER = 4_000_000
_MAX_EVAL_SHIFT = 10_000


def _bounded_eval_value(value: Any) -> Any:
    if isinstance(value, (str, bytes, list, tuple)) and len(value) > _MAX_EVAL_SEQUENCE:
        raise ValueError("expression result is too large")
    if isinstance(value, int) and value.bit_length() > 1_000_000:
        raise ValueError("integer result is too large")
    return value


def _eval_add(left: Any, right: Any) -> Any:
    if hasattr(left, "__len__") and hasattr(right, "__len__"):
        if len(left) + len(right) > _MAX_EVAL_SEQUENCE:
            raise ValueError("expression result is too large")
    return operator.add(left, right)


def _eval_multiply(left: Any, right: Any) -> Any:
    if hasattr(left, "__len__") and isinstance(right, int):
        if max(0, right) * len(left) > _MAX_EVAL_SEQUENCE:
            raise ValueError("expression result is too large")
    if hasattr(right, "__len__") and isinstance(left, int):
        if max(0, left) * len(right) > _MAX_EVAL_SEQUENCE:
            raise ValueError("expression result is too large")
    return operator.mul(left, right)


def _eval_power(left: Any, right: Any) -> Any:
    if abs(float(left)) > _MAX_EVAL_POWER or abs(float(right)) > _MAX_EVAL_POWER:
        raise ValueError("power operands are too large")
    return operator.pow(left, right)


def _eval_shift(left: Any, right: Any, fn) -> Any:
    if abs(int(left)) > _MAX_EVAL_POWER or abs(int(right)) > _MAX_EVAL_SHIFT:
        raise ValueError("shift operands are too large")
    return fn(left, right)


_BINARY = {
    ast.Add: _eval_add,
    ast.Sub: operator.sub,
    ast.Mult: _eval_multiply,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: _eval_power,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.LShift: lambda left, right: _eval_shift(left, right, operator.lshift),
    ast.RShift: lambda left, right: _eval_shift(left, right, operator.rshift),
}
_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
    ast.Invert: operator.invert,
}
_COMPARE = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}

_EVAL_FUNCTIONS = {
    "abs": abs,
    "float": float,
    "int": int,
    "max": max,
    "min": min,
    "round": round,
    "str": str,
    "rand": random.random,
    "randint": lambda top: int(random.random() * int(top)),
}
_STRING_METHODS = {
    "upper", "lower", "capitalize", "title", "strip", "lstrip", "rstrip",
    "find", "replace", "count", "isnumeric", "isalpha", "isalnum",
    "startswith", "endswith", "split", "zfill",
}


def _safe_eval(expression: str, names: dict[str, Any], *, strings: bool = False) -> Any:
    if not isinstance(expression, str) or len(expression) > 1024:
        raise ValueError("expression must be at most 1024 characters")
    root = ast.parse(expression, mode="eval")
    budget = [0]

    def evaluate(node: ast.AST) -> Any:
        budget[0] += 1
        if budget[0] > 128:
            raise ValueError("expression is too complex")
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool, type(None))):
                return node.value
        if isinstance(node, ast.Name) and node.id in names:
            return names[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left, right = evaluate(node.left), evaluate(node.right)
            return _bounded_eval_value(_BINARY[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](evaluate(node.operand))
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            result = evaluate(node.values[0])
            for value in node.values[1:]:
                if isinstance(node.op, ast.And) and not result:
                    return result
                if isinstance(node.op, ast.Or) and result:
                    return result
                result = evaluate(value)
            return result
        if isinstance(node, ast.Compare):
            left = evaluate(node.left)
            for op, comparator in zip(node.ops, node.comparators, strict=True):
                right = evaluate(comparator)
                fn = _COMPARE.get(type(op))
                if fn is None or not fn(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call) and not node.keywords and len(node.args) <= 16:
            args = [evaluate(arg) for arg in node.args]
            if isinstance(node.func, ast.Name):
                if strings and node.func.id == "len" and len(args) == 1:
                    return len(args[0])
                function = _EVAL_FUNCTIONS.get(node.func.id)
                if function is not None:
                    return _bounded_eval_value(function(*args))
            if (
                strings
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _STRING_METHODS
            ):
                target = evaluate(node.func.value)
                if not isinstance(target, str):
                    raise ValueError("string methods may only be called on strings")
                return _bounded_eval_value(getattr(target, node.func.attr)(*args))
        if strings and isinstance(node, ast.Subscript):
            target = evaluate(node.value)
            if not isinstance(target, (str, list, tuple)):
                raise ValueError("only strings and simple sequences may be sliced")
            if isinstance(node.slice, ast.Slice):
                parts = [
                    None if part is None else int(evaluate(part))
                    for part in (node.slice.lower, node.slice.upper, node.slice.step)
                ]
                if parts[2] == 0:
                    raise ValueError("slice step cannot be zero")
                return _bounded_eval_value(target[slice(*parts)])
            return target[int(evaluate(node.slice))]
        if strings and isinstance(node, (ast.List, ast.Tuple)):
            values = [evaluate(item) for item in node.elts]
            return _bounded_eval_value(values if isinstance(node, ast.List) else tuple(values))
        if strings and isinstance(node, ast.JoinedStr):
            parts = []
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    parts.append(part.value)
                    continue
                if not isinstance(part, ast.FormattedValue):
                    raise ValueError("unsupported formatted string component")
                value = evaluate(part.value)
                if part.conversion == 115:
                    value = str(value)
                elif part.conversion == 114:
                    value = repr(value)
                elif part.conversion == 97:
                    value = ascii(value)
                spec = ""
                if part.format_spec is not None:
                    spec = str(evaluate(part.format_spec))
                    if len(spec) > 32:
                        raise ValueError("format specification is too long")
                parts.append(format(value, spec))
            return _bounded_eval_value("".join(parts))
        if isinstance(node, ast.IfExp):
            return evaluate(node.body if evaluate(node.test) else node.orelse)
        raise ValueError(f"expression construct {type(node).__name__} is not allowed")

    return evaluate(root)


def _evaluate_number(python_expression, print_to_console, a=0, b=0, c=0, **_kwargs):
    result = _safe_eval(python_expression, {"a": a, "b": b, "c": c})
    if print_to_console == "True":
        print(f"{python_expression} = {result}")
    return int(result), float(result), str(result)


def _evaluate_string(python_expression, print_to_console, a="", b="", c="", **_kwargs):
    result = _safe_eval(
        python_expression, {"a": str(a), "b": str(b), "c": str(c)}, strings=True
    )
    if print_to_console == "True":
        print(f"{python_expression} = {result}")
    return (str(result),)


def _information_node(**_kwargs):
    return ()


# ---------------------------------------------------------------------------
# Stack, tuple, and script helpers.
# ---------------------------------------------------------------------------

def _pack_sdxl(**kwargs):
    return ((
        kwargs["base_model"], kwargs["base_clip"], kwargs["base_positive"],
        kwargs["base_negative"], kwargs["refiner_model"], kwargs["refiner_clip"],
        kwargs["refiner_positive"], kwargs["refiner_negative"],
    ),)


def _unpack_sdxl(sdxl_tuple, **_kwargs):
    if not isinstance(sdxl_tuple, (tuple, list)) or len(sdxl_tuple) != 8:
        raise ValueError("SDXL tuple must contain eight entries")
    return tuple(sdxl_tuple)


def _lora_stacker(input_mode, lora_count, lora_stack=None, **kwargs):
    output = []
    for index in range(1, min(50, max(0, int(lora_count))) + 1):
        name = kwargs.get(f"lora_name_{index}")
        if not name or name == "None":
            continue
        name = _safe_asset_name(name)
        if input_mode == "simple":
            model_strength = clip_strength = float(kwargs.get(f"lora_wt_{index}", 1.0))
        else:
            model_strength = float(kwargs.get(f"model_str_{index}", 1.0))
            clip_strength = float(kwargs.get(f"clip_str_{index}", 1.0))
        output.append((name, model_strength, clip_strength))
    output.extend(
        tuple(item) for item in (lora_stack or ())
        if isinstance(item, (tuple, list)) and item and item[0] != "None"
    )
    return (output,)


def _lora_stack_string(lora_stack, **_kwargs):
    return (" ".join(
        f"<lora:{item[0]}:{item[1]}:{item[2]}>"
        for item in (lora_stack or ())
        if isinstance(item, (tuple, list)) and len(item) >= 3
    ),)


def _controlnet_stacker(
    control_net, image, strength, start_percent, end_percent, cnet_stack=None, **_kwargs
):
    output = _copy_stack(cnet_stack)
    output.append((
        control_net, image, float(strength), float(start_percent), float(end_percent)
    ))
    return (output,)


async def _apply_controlnet_stack(positive, negative, cnet_stack=None, **_kwargs):
    for index, entry in enumerate(cnet_stack or ()):
        if not isinstance(entry, (tuple, list)) or len(entry) < 5:
            raise ValueError(f"ControlNet stack entry {index} is malformed")
        control_net, image, strength, start, end = entry[:5]
        positive, negative = await control_net.apply(
            positive,
            negative,
            image,
            strength=float(strength),
            start_percent=float(start),
            end_percent=float(end),
        )
    return positive, negative


def _noise_script(rng_source, cfg_denoiser, add_seed_noise, seed, weight, script=None):
    output = _script_copy(script)
    output["noise"] = {
        "rng_source": str(rng_source),
        "cfg_denoiser": bool(cfg_denoiser),
        "add_seed_noise": bool(add_seed_noise),
        "seed": int(seed),
        "weight": float(weight),
    }
    return (output,)


async def _hires_script(
    upscale_type,
    hires_ckpt_name,
    latent_upscaler,
    pixel_upscaler,
    upscale_by,
    use_same_seed,
    seed,
    hires_steps,
    denoise,
    iterations,
    use_controlnet,
    control_net_name,
    strength,
    preprocessor,
    preprocessor_imgs,
    script=None,
    **_kwargs,
):
    output = _script_copy(script)
    control_net = None
    if str(use_controlnet).lower() not in {"false", "_", "none", "0"}:
        control_net = await _ctx().models.load_controlnet(_safe_asset_name(control_net_name))
    upscale_kind = str(upscale_type)
    latent_method = str(latent_upscaler)
    factor = float(upscale_by)
    latent_weight = None
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError("high-resolution upscale factor must be positive and finite")
    if upscale_kind == "both":
        # Pixel upscaling already establishes the requested dimensions.  The
        # original pack intentionally used its first canonical latent method
        # at 1x only to normalize the VAE-encoded latent before sampling.
        latent_method = "nearest-exact"
    elif upscale_kind == "latent" and int(iterations) > 0:
        if latent_method.startswith("city96."):
            version = latent_method.removeprefix("city96.")
            if version not in {"v1", "xl"}:
                raise ValueError("unknown City96 latent upscaler version")
            scale = min((1.25, 1.5, 2.0), key=lambda item: abs(item - factor))
            scale_name = f"{scale:.2f}".rstrip("0").rstrip(".")
            if scale_name == "2":
                scale_name = "2.0"
            factor = scale
            latent_weight = await _download_declared_weight(
                _CITY96_WEIGHTS[(version, scale_name)]
            )
        elif latent_method.startswith("ttl_nn."):
            version = latent_method.removeprefix("ttl_nn.")
            if version not in _TTL_WEIGHTS:
                raise ValueError("unknown TTL latent upscaler version")
            factor = min(2.0, max(1.0, factor))
            latent_weight = await _download_declared_weight(
                _TTL_WEIGHTS[version]
            )
        elif latent_method not in {
            "nearest-exact", "bilinear", "area", "bicubic", "bislerp",
        }:
            latent_method = "nearest-exact"
    output["hiresfix"] = {
        "upscale_type": upscale_kind,
        "checkpoint": None if hires_ckpt_name == "(use same)" else _safe_asset_name(hires_ckpt_name),
        "latent_upscaler": latent_method,
        "latent_weight": latent_weight,
        "pixel_upscaler": _safe_asset_name(pixel_upscaler) if pixel_upscaler else None,
        "upscale_by": factor,
        "use_same_seed": bool(use_same_seed),
        "seed": int(seed),
        "steps": int(hires_steps),
        "denoise": float(denoise),
        "iterations": int(iterations),
        "control_net": control_net,
        "control_strength": float(strength),
        "preprocessor": str(preprocessor),
        "include_preprocessor_images": bool(preprocessor_imgs),
    }
    return (output,)


async def _tile_script(
    upscale_by,
    tile_size,
    tiling_strategy,
    tiling_steps,
    seed,
    denoise,
    use_controlnet,
    tile_controlnet,
    strength,
    script=None,
):
    output = _script_copy(script)
    if tiling_strategy != "none":
        control_net = None
        if use_controlnet:
            control_net = await _ctx().models.load_controlnet(_safe_asset_name(tile_controlnet))
        output["tile"] = {
            "upscale_by": float(upscale_by),
            "tile_size": int(tile_size),
            "strategy": str(tiling_strategy),
            "steps": int(tiling_steps),
            "seed": int(seed),
            "denoise": float(denoise),
            "control_net": control_net,
            "strength": float(strength),
        }
    return (output,)


# ---------------------------------------------------------------------------
# Image Overlay remains pack code; raw pixels are the appropriate narrow tier.
# ---------------------------------------------------------------------------

def _pil_from_image(value: torch.Tensor) -> Image.Image:
    array = value.detach().float().cpu().clamp(0, 1).mul(255).byte().numpy()
    if array.ndim == 2:
        return Image.fromarray(array, "L")
    if array.shape[-1] == 1:
        return Image.fromarray(array[..., 0], "L")
    return Image.fromarray(array[..., :4] if array.shape[-1] >= 4 else array[..., :3])


def _tensor_from_pil(value: Image.Image) -> torch.Tensor:
    array = np.asarray(value.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(array.copy())


async def _image_overlay(
    base_image,
    overlay_image,
    overlay_resize,
    resize_method,
    rescale_factor,
    width,
    height,
    x_offset,
    y_offset,
    rotation,
    opacity,
    optional_mask=None,
):
    base = await base_image.raw()
    overlay = await overlay_image.raw()
    mask = await optional_mask.raw() if optional_mask is not None else None
    if base.ndim != 4 or overlay.ndim != 4 or base.shape[0] == 0 or overlay.shape[0] == 0:
        raise ValueError("Image Overlay requires non-empty BHWC image batches")
    overlay_tensor = overlay[:1]
    base_height, base_width = int(base.shape[1]), int(base.shape[2])
    if overlay_resize == "Fit":
        ratio = min(
            base_width / int(overlay.shape[2]),
            base_height / int(overlay.shape[1]),
        )
        target = (
            max(1, round(int(overlay.shape[2]) * ratio)),
            max(1, round(int(overlay.shape[1]) * ratio)),
        )
    elif overlay_resize == "Resize by rescale_factor":
        target = (
            max(1, int(int(overlay.shape[2]) * float(rescale_factor))),
            max(1, int(int(overlay.shape[1]) * float(rescale_factor))),
        )
    elif overlay_resize == "Resize to width & heigth":
        target = (max(1, int(width)), max(1, int(height)))
    else:
        target = (int(overlay.shape[2]), int(overlay.shape[1]))
    if target != (int(overlay.shape[2]), int(overlay.shape[1])):
        interpolation = str(resize_method)
        if interpolation not in {"nearest-exact", "bilinear", "area"}:
            interpolation = "bilinear"
        kwargs = {"align_corners": False} if interpolation == "bilinear" else {}
        overlay_tensor = F.interpolate(
            overlay_tensor.movedim(-1, 1).float(),
            size=(target[1], target[0]),
            mode=interpolation,
            **kwargs,
        ).movedim(1, -1)
    overlay_pil = _pil_from_image(overlay_tensor[0]).convert("RGBA")

    if mask is not None:
        mask_tensor = mask[0] if mask.ndim >= 3 else mask
        if mask_tensor.ndim == 3 and mask_tensor.shape[-1] == 1:
            mask_tensor = mask_tensor[..., 0]
        alpha = _pil_from_image(mask_tensor).resize(
            target, Image.Resampling.BICUBIC
        )
        overlay_pil.putalpha(ImageOps.invert(alpha.convert("L")))
    else:
        overlay_pil.putalpha(255)
    overlay_pil = overlay_pil.rotate(
        float(rotation), resample=Image.Resampling.BICUBIC, expand=True
    )
    alpha = overlay_pil.getchannel("A").point(
        lambda value: max(0, min(255, round(value * (1.0 - float(opacity) / 100.0))))
    )
    overlay_pil.putalpha(alpha)

    result = []
    for item in base:
        canvas = _pil_from_image(item).convert("RGBA")
        canvas.alpha_composite(overlay_pil, (int(x_offset), int(y_offset)))
        result.append(_tensor_from_pil(canvas))
    return (torch.stack(result),)


# ---------------------------------------------------------------------------
# XY input nodes.  Their values remain ordinary pack-owned workflow data.
# ---------------------------------------------------------------------------

def _xy_seed(batch_count, **_kwargs):
    values = list(range(max(0, int(batch_count))))
    return (("Seeds++ Batch", values),) if values else (None,)


def _xy_noise(XY_type, **_kwargs):
    kind = "AddNoise" if XY_type == "add_noise" else "ReturnNoise"
    return ((kind, ["enable", "disable"]),)


def _xy_steps(target_parameter, batch_count, **kwargs):
    mapping = {
        "steps": ("Steps", "first_step", "last_step"),
        "start_at_step": ("StartStep", "first_start_step", "last_start_step"),
        "end_at_step": ("EndStep", "first_end_step", "last_end_step"),
        "refine_at_step": ("RefineStep", "first_refine_step", "last_refine_step"),
    }
    kind, first, last = mapping[target_parameter]
    values = _ints(batch_count, kwargs[first], kwargs[last])
    return ((kind, values),) if values else (None,)


def _xy_cfg(batch_count, first_cfg, last_cfg, **_kwargs):
    values = _floats(batch_count, first_cfg, last_cfg)
    return (("CFG Scale", values),) if values else (None,)


def _xy_denoise(batch_count, first_denoise, last_denoise, **_kwargs):
    values = _floats(batch_count, first_denoise, last_denoise)
    return (("Denoise", values),) if values else (None,)


def _xy_sampler(target_parameter, input_count, **kwargs):
    count = min(50, max(0, int(input_count)))
    if target_parameter == "scheduler":
        values = [
            kwargs.get(f"scheduler_{index}") for index in range(1, count + 1)
            if kwargs.get(f"scheduler_{index}") != "None"
        ]
        kind = "Scheduler"
    elif target_parameter == "sampler":
        values = [
            (kwargs.get(f"sampler_{index}"), None) for index in range(1, count + 1)
            if kwargs.get(f"sampler_{index}") != "None"
        ]
        kind = "Sampler"
    else:
        values = []
        for index in range(1, count + 1):
            sampler = kwargs.get(f"sampler_{index}")
            scheduler = kwargs.get(f"scheduler_{index}")
            if sampler != "None":
                values.append((sampler, None if scheduler == "None" else scheduler))
        kind = "Sampler"
    return ((kind, values),) if values else (None,)


async def _xy_vae(
    input_mode, batch_path, subdirectories, batch_sort, batch_max, vae_count, **kwargs
):
    if "Batch" in input_mode:
        values = await _catalogue_batch(
            "vae", batch_path, recursive=bool(subdirectories),
            descending=batch_sort == "descending", limit=int(batch_max),
        )
    else:
        values = [
            kwargs.get(f"vae_name_{index}") for index in range(1, int(vae_count) + 1)
            if kwargs.get(f"vae_name_{index}") != "None"
        ]
    return (("VAE", values),) if values else (None,)


def _xy_prompt(target_prompt, search_txt, replace_count, **kwargs):
    if not search_txt:
        return (None,)
    kind = "Positive Prompt S/R" if target_prompt == "positive" else "Negative Prompt S/R"
    values = [(str(search_txt), None)]
    values.extend(
        (str(search_txt), kwargs.get(f"replace_{index}"))
        for index in range(1, min(49, max(0, int(replace_count))) + 1)
    )
    return ((kind, values),)


def _xy_ascore(target_ascore, batch_count, first_ascore, last_ascore, **_kwargs):
    kind = "AScore+" if target_ascore == "positive" else "AScore-"
    values = _floats(batch_count, first_ascore, last_ascore)
    return ((kind, values),) if values else (None,)


def _xy_refiner(refine_at_percent, **_kwargs):
    return (("Refiner On/Off", [float(refine_at_percent), 1.0]),)


def _xy_clip_skip(target_ckpt, batch_count, first_clip_skip, last_clip_skip, **_kwargs):
    kind = "Clip Skip" if target_ckpt == "Base" else "Clip Skip (Refiner)"
    values = _ints(batch_count, first_clip_skip, last_clip_skip)
    return ((kind, values),) if values else (None,)


async def _xy_checkpoint(
    target_ckpt,
    input_mode,
    batch_path,
    subdirectories,
    batch_sort,
    batch_max,
    ckpt_count,
    **kwargs,
):
    kind = "Checkpoint" if target_ckpt == "Base" else "Refiner"
    if "Batch" in input_mode:
        names = await _catalogue_batch(
            "checkpoints", batch_path, recursive=bool(subdirectories),
            descending=batch_sort == "descending", limit=int(batch_max),
        )
        values = [(name, None, None) for name in names]
    else:
        values = []
        for index in range(1, min(50, max(0, int(ckpt_count))) + 1):
            name = kwargs.get(f"ckpt_name_{index}")
            if not name or name == "None":
                continue
            clip_skip = kwargs.get(f"clip_skip_{index}") if "ClipSkip" in input_mode else None
            vae = kwargs.get(f"vae_name_{index}") if "VAE" in input_mode else None
            values.append((_safe_asset_name(name), clip_skip, vae))
    return ((kind, values),) if values else (None,)


async def _lora_batch(
    batch_path,
    subdirectories,
    batch_sort,
    model_strength,
    clip_strength,
    batch_max,
    lora_stack=None,
):
    names = await _catalogue_batch(
        "loras", batch_path, recursive=bool(subdirectories),
        descending=batch_sort == "descending", limit=int(batch_max),
    )
    tail = _copy_stack(lora_stack)
    return [[(name, float(model_strength), float(clip_strength)), *tail] for name in names]


async def _xy_lora(
    input_mode,
    batch_path,
    subdirectories,
    batch_sort,
    batch_max,
    lora_count,
    model_strength,
    clip_strength,
    lora_stack=None,
    **kwargs,
):
    tail = _copy_stack(lora_stack)
    if "Batch" in input_mode:
        values = await _lora_batch(
            batch_path, subdirectories, batch_sort, model_strength, clip_strength,
            batch_max, tail,
        )
        return (("LoRA Stacks", values),) if values else (None,)
    values = []
    for index in range(1, min(50, max(0, int(lora_count))) + 1):
        name = kwargs.get(f"lora_name_{index}")
        if not name or name == "None":
            continue
        model_value = kwargs.get(f"model_str_{index}", model_strength)
        clip_value = kwargs.get(f"clip_str_{index}", clip_strength)
        if "Weights" not in input_mode:
            model_value, clip_value = model_strength, clip_strength
        values.append([(_safe_asset_name(name), float(model_value), float(clip_value)), *tail])
    return (("LoRA", values),) if values else (None,)


async def _xy_lora_plot(
    input_mode,
    lora_name,
    model_strength,
    clip_strength,
    X_batch_count,
    X_batch_path,
    X_subdirectories,
    X_batch_sort,
    X_first_value,
    X_last_value,
    Y_batch_count,
    Y_first_value,
    Y_last_value,
    lora_stack=None,
):
    tail = _copy_stack(lora_stack)
    if "LoRA Batch" not in input_mode and lora_name in {None, "", "None"}:
        return None, None
    name = None if "LoRA Batch" in input_mode else _safe_asset_name(lora_name)
    base_model = None if "LoRA Weight" in input_mode or "Model Strength" in input_mode else float(model_strength)
    base_clip = None if "LoRA Weight" in input_mode or "Clip Strength" in input_mode else float(clip_strength)
    if "X: LoRA Batch" in input_mode:
        x_values = await _lora_batch(
            X_batch_path, X_subdirectories, X_batch_sort, base_model, base_clip,
            X_batch_count, tail,
        )
        x_type = "LoRA Batch"
    else:
        x_values = [
            [(name, value, base_clip), *tail]
            for value in _floats(X_batch_count, X_first_value, X_last_value)
        ]
        x_type = "LoRA MStr"
    y_numbers = _floats(Y_batch_count, Y_first_value, Y_last_value)
    if "Y: LoRA Weight" in input_mode:
        y_type = "LoRA Wt"
        y_values = [[(name, value, value), *tail] for value in y_numbers]
    elif "Y: Model Strength" in input_mode:
        y_type = "LoRA MStr"
        y_values = [[(name, value, base_clip), *tail] for value in y_numbers]
    else:
        y_type = "LoRA CStr"
        y_values = [[(name, base_model, value), *tail] for value in y_numbers]
    return (x_type, x_values), (y_type, y_values)


def _xy_lora_stacks(node_state, **kwargs):
    values = [kwargs.get(f"lora_stack_{index}") for index in range(1, 6)]
    values = [value for value in values if value]
    return (("LoRA Stacks", values),) if values and node_state != "Disabled" else (None,)


def _control_values(
    kind,
    control_net,
    image,
    count,
    first,
    last,
    strength,
    start,
    end,
    cnet_stack=None,
):
    if kind in {"ControlNetStart%", "ControlNetEnd%"}:
        # The upstream plot clamps the endpoints before interpolation.  That
        # differs from clamping every interpolated value for descending ranges.
        first = min(1.0, float(first))
        last = min(1.0, float(last))
    values = _floats(count, first, last)
    output = []
    for value in values:
        if kind == "ControlNetStrength":
            entry = (control_net, image, value, start, end)
        elif kind == "ControlNetStart%":
            entry = (control_net, image, strength, min(1.0, value), end)
        else:
            entry = (control_net, image, strength, start, min(1.0, value))
        output.append([entry, *_copy_stack(cnet_stack)])
    return (kind, output) if output else None


def _xy_controlnet(control_net, image, target_parameter, batch_count, cnet_stack=None, **kwargs):
    if target_parameter == "strength":
        result = _control_values(
            "ControlNetStrength", control_net, image, batch_count,
            kwargs["first_strength"], kwargs["last_strength"], kwargs["strength"],
            kwargs["start_percent"], kwargs["end_percent"], cnet_stack,
        )
    elif target_parameter == "start_percent":
        result = _control_values(
            "ControlNetStart%", control_net, image, batch_count,
            kwargs["first_start_percent"], kwargs["last_start_percent"], kwargs["strength"],
            kwargs["start_percent"], kwargs["end_percent"], cnet_stack,
        )
    else:
        result = _control_values(
            "ControlNetEnd%", control_net, image, batch_count,
            kwargs["first_end_percent"], kwargs["last_end_percent"], kwargs["strength"],
            kwargs["start_percent"], kwargs["end_percent"], cnet_stack,
        )
    return (result,) if result else (None,)


def _xy_controlnet_plot(
    control_net,
    image,
    plot_type,
    strength,
    start_percent,
    end_percent,
    X_batch_count,
    X_first_value,
    X_last_value,
    Y_batch_count,
    Y_first_value,
    Y_last_value,
    cnet_stack=None,
):
    x_axis, y_axis = [part.split(":", 1)[1].strip() for part in plot_type.split(", ")]
    kind = {"Strength": "ControlNetStrength", "Start%": "ControlNetStart%", "End%": "ControlNetEnd%"}
    x = _control_values(
        kind[x_axis], control_net, image, X_batch_count, X_first_value, X_last_value,
        strength, start_percent, end_percent, cnet_stack,
    )
    y = _control_values(
        kind[y_axis], control_net, image, Y_batch_count, Y_first_value, Y_last_value,
        strength, start_percent, end_percent, cnet_stack,
    )
    return x, y


def _xy_join(XY_1, XY_2, **_kwargs):
    kind_a, values_a = XY_1
    kind_b, values_b = XY_2
    if kind_a != kind_b:
        return (None,)
    if kind_a == "Seeds++ Batch":
        values = list(range(len(values_a) + len(values_b)))
    elif kind_a in {"Positive Prompt S/R", "Negative Prompt S/R"}:
        values = list(values_a) + [(values_a[0][0], value[1]) for value in values_b[1:]]
    else:
        values = list(values_a) + list(values_b)
    return ((kind_a, values),)


def _manual_suffixes(values: list[str]) -> list[str] | None:
    """Expand the documented `;,defaults` shortcut used by three XY types."""
    if not values or not values[-1].startswith(","):
        return values
    suffixes = [part.strip() for part in values.pop().lstrip(",").split(",")]
    if not values or not suffixes or any(part == "" for part in suffixes):
        return None
    expanded = []
    for value in values:
        parts = [part.strip() for part in value.split(",")]
        parts.extend(suffixes[len(parts) - 1:])
        expanded.append(",".join(parts))
    return expanded


async def _xy_manual(plot_type, plot_value, **_kwargs):
    source = str(plot_value).replace("\n", "").rstrip(";")
    if plot_type not in {"Positive Prompt S/R", "Negative Prompt S/R", "VAE", "Checkpoint", "LoRA", "Scheduler"}:
        source = source.replace(" ", "")
    values = source.split(";") if source else []
    if plot_type == "Nothing":
        return ((plot_type, [""]),)
    if plot_type == "Seeds++ Batch":
        if len(values) != 1:
            return (None,)
        try:
            raw_count = float(values[0])
            count = int(raw_count)
        except (TypeError, ValueError, OverflowError):
            return (None,)
        if raw_count != count or not 1 <= count <= 50:
            return (None,)
        return ((plot_type, list(range(count))),)
    if plot_type in {"Positive Prompt S/R", "Negative Prompt S/R"}:
        if not values or not values[0]:
            return (None,)
        search = values[0]
        return ((plot_type, [(search, None), *((search, value) for value in values[1:])]),)

    if plot_type in {"Sampler", "Checkpoint", "LoRA"}:
        values = _manual_suffixes(values)
        if values is None:
            return (None,)

    try:
        if plot_type in {"Steps", "StartStep", "EndStep", "Clip Skip"}:
            limits = {
                "Steps": (1, 10_000),
                "StartStep": (0, 10_000),
                "EndStep": (0, 10_000),
                "Clip Skip": (-24, -1),
            }[plot_type]
            parsed = [max(limits[0], min(limits[1], int(value))) for value in values]
        elif plot_type in {"CFG Scale", "Denoise"}:
            limits = {"CFG Scale": (0.0, 100.0), "Denoise": (0.0, 1.0)}[plot_type]
            parsed = [max(limits[0], min(limits[1], float(value))) for value in values]
        else:
            parsed = None
    except (TypeError, ValueError, OverflowError):
        return (None,)

    if plot_type == "Sampler":
        parsed = []
        for value in values:
            parts = [part.strip() for part in value.split(",")]
            sampler = parts[0]
            scheduler = parts[1].lower() if len(parts) > 1 else None
            if sampler not in _SAMPLER_OPTIONS:
                return (None,)
            if scheduler is not None and scheduler not in _SCHEDULER_OPTIONS:
                return (None,)
            parsed.append((sampler, scheduler))
    elif plot_type == "Scheduler":
        parsed = [value.strip().lower() for value in values]
        if any(value not in _SCHEDULER_OPTIONS for value in parsed):
            return (None,)
    elif plot_type == "VAE":
        available = set(await _ctx().assets.list("vae", prefix="", recursive=True))
        parsed = []
        for value in values:
            name = str(value).strip()
            if name != "Baked VAE":
                name = _safe_asset_name(name)
                if name not in available:
                    return (None,)
            parsed.append(name)
    elif plot_type == "Checkpoint":
        available = set(await _ctx().assets.list("checkpoints", prefix="", recursive=True))
        parsed = []
        for value in values:
            parts = [part.strip() for part in value.split(",")]
            name = _safe_asset_name(parts[0])
            if name not in available:
                return (None,)
            try:
                clip_skip = int(parts[1]) if len(parts) > 1 else None
            except (TypeError, ValueError, OverflowError):
                return (None,)
            if clip_skip is not None and not -24 <= clip_skip <= -1:
                return (None,)
            parsed.append((name, clip_skip, None))
    elif plot_type == "LoRA":
        available = set(await _ctx().assets.list("loras", prefix="", recursive=True))
        parsed = []
        for value in values:
            parts = [part.strip() for part in value.split(",")]
            name = _safe_asset_name(parts[0])
            if name not in available:
                return (None,)
            try:
                model_strength = float(parts[1]) if len(parts) > 1 else 1.0
                clip_strength = float(parts[2]) if len(parts) > 2 else 1.0
            except (TypeError, ValueError, OverflowError):
                return (None,)
            if not -10.0 <= model_strength <= 10.0 or not -10.0 <= clip_strength <= 10.0:
                return (None,)
            parsed.append([(name, model_strength, clip_strength)])
    return ((plot_type, parsed),) if parsed else (None,)


def _xy_plot(
    grid_spacing,
    XY_flip,
    Y_label_orientation,
    cache_models,
    ksampler_output_image,
    dependencies=None,
    X=None,
    Y=None,
    my_unique_id=None,
    **_kwargs,
):
    x_type, x_values = X if X is not None else ("Nothing", [""])
    y_type, y_values = Y if Y is not None else ("Nothing", [""])
    if x_type == y_type and x_type not in {"Positive Prompt S/R", "Negative Prompt S/R"}:
        return (None,)
    dependency_types = {
        "Checkpoint", "Refiner", "LoRA", "LoRA Stacks", "LoRA Batch", "LoRA Wt",
        "LoRA MStr", "LoRA CStr", "Positive Prompt S/R", "Negative Prompt S/R",
        "AScore+", "AScore-", "Clip Skip", "Clip Skip (Refiner)",
        "ControlNetStrength", "ControlNetStart%", "ControlNetEnd%",
    }
    if (x_type in dependency_types or y_type in dependency_types) and dependencies is None:
        return (None,)
    lora_plot_types = {"LoRA Batch", "LoRA Wt", "LoRA MStr", "LoRA CStr"}
    if (x_type in lora_plot_types) != (y_type in lora_plot_types):
        return (None,)
    if x_type in {"LoRA", "LoRA Stacks"} and y_type in {"LoRA", "LoRA Stacks"}:
        return (None,)

    x_values = copy.deepcopy(x_values)
    y_values = copy.deepcopy(y_values)
    if x_type == "Sampler" and y_type == "Scheduler":
        x_values = [(value[0], "") for value in x_values]
    elif y_type == "Sampler" and x_type == "Scheduler":
        y_values = [(value[0], "") for value in y_values]
    if x_type == "Scheduler" and y_type != "Sampler":
        x_values = [(value, None) for value in x_values]
    if y_type == "Scheduler" and x_type != "Sampler":
        y_values = [(value, None) for value in y_values]
    if x_type == "Checkpoint" and y_type == "VAE":
        x_values = [(value[0], value[1], None) for value in x_values]
    elif y_type == "Checkpoint" and x_type == "VAE":
        y_values = [(value[0], value[1], None) for value in y_values]
    if XY_flip == "True":
        x_type, y_type, x_values, y_values = y_type, x_type, y_values, x_values
    output = {
        "xyplot": {
            "x_type": x_type,
            "x_values": x_values,
            "y_type": y_type,
            "y_values": y_values,
            "grid_spacing": int(grid_spacing),
            "y_label_orientation": str(Y_label_orientation),
            "cache_models": cache_models == "True",
            "plot_as_output": ksampler_output_image == "Plot",
            "node_id": my_unique_id,
            "dependencies": dependencies,
        }
    }
    return (output,)


# Loader and sampler handlers are defined below, after their shared utilities.


# ---------------------------------------------------------------------------
# Loader prompt encoding and model composition.
# ---------------------------------------------------------------------------

def _normalise_token_weights(tokens: dict, mode: str) -> dict:
    """Apply the pack's word-length/mean normalization to public token data.

    Comfy token entries are normally ``(token, weight[, word_id])``.  Unknown
    tokenizer payloads are returned untouched so newer model families retain
    their native encoding path.
    """
    if mode == "none":
        return tokens
    output = copy.deepcopy(tokens)
    for key, chunks in output.items():
        if not isinstance(chunks, list):
            continue
        parsed = []
        for chunk in chunks:
            if not isinstance(chunk, list):
                parsed = []
                break
            row = []
            for entry in chunk:
                if not isinstance(entry, (tuple, list)) or len(entry) < 2:
                    row = []
                    break
                row.append(list(entry))
            if not row:
                parsed = []
                break
            parsed.append(row)
        if not parsed:
            continue
        if mode.startswith("length"):
            counts: dict[Any, int] = {}
            for row in parsed:
                for entry in row:
                    word_id = entry[2] if len(entry) > 2 else None
                    if word_id not in (None, 0):
                        counts[word_id] = counts.get(word_id, 0) + 1
            for row in parsed:
                for entry in row:
                    word_id = entry[2] if len(entry) > 2 else None
                    count = counts.get(word_id, 1)
                    delta = float(entry[1]) - 1.0
                    entry[1] = 1.0 + math.copysign(math.sqrt(delta * delta / count), delta)
        if mode.endswith("mean"):
            weighted = [
                float(entry[1]) for row in parsed for entry in row
                if len(entry) < 3 or entry[2] not in (None, 0)
            ]
            if weighted:
                shift = 1.0 - sum(weighted) / len(weighted)
                for row in parsed:
                    for entry in row:
                        if len(entry) < 3 or entry[2] not in (None, 0):
                            entry[1] = float(entry[1]) + shift
        output[key] = [[tuple(entry) for entry in row] for row in parsed]
    return output


def _advanced_component_data(tokenized: list) -> tuple[list, list, list]:
    tokens, weights, word_ids = [], [], []
    if not isinstance(tokenized, list) or not tokenized:
        raise ValueError("advanced prompt encoding needs token chunks")
    for chunk_index, chunk in enumerate(tokenized):
        if not isinstance(chunk, list) or not chunk:
            raise ValueError(f"advanced token chunk {chunk_index} is malformed")
        token_row, weight_row, word_row = [], [], []
        for entry_index, entry in enumerate(chunk):
            if not isinstance(entry, (tuple, list)) or len(entry) < 3:
                raise ValueError(
                    f"advanced token entry {chunk_index}:{entry_index} "
                    "does not include a word id"
                )
            token_row.append(entry[0])
            weight_row.append(float(entry[1]))
            word_row.append(entry[2])
        tokens.append(token_row)
        weights.append(weight_row)
        word_ids.append(word_row)
    return tokens, weights, word_ids


def _weighted_pairs(tokens: list, weights: list) -> list:
    return [
        [(token, float(weight)) for token, weight in zip(row, weight_row, strict=True)]
        for row, weight_row in zip(tokens, weights, strict=True)
    ]


async def _encode_component_pairs(clip, component: str, token_pairs: list):
    embedding_ref, pooled_ref = await clip.encode_token_weights_component(
        component, token_pairs
    )
    embedding = await embedding_ref.raw()
    pooled = None if pooled_ref is None else await pooled_ref.raw()
    return embedding, pooled


async def _batched_component_encode(
    clip,
    component: str,
    token_pairs: list,
    *,
    chunk_length: int,
    chunks_per_prompt: int,
) -> torch.Tensor:
    encoded = []
    for start in range(0, len(token_pairs), 32):
        batch = token_pairs[start:start + 32]
        embedding, _pooled = await _encode_component_pairs(
            clip, component, batch
        )
        encoded.append(embedding.reshape(len(batch), chunk_length, -1))
    combined = torch.cat(encoded)
    if len(token_pairs) % chunks_per_prompt:
        raise ValueError("masked prompt batch lost its token-chunk alignment")
    return combined.reshape(
        len(token_pairs) // chunks_per_prompt,
        chunk_length * chunks_per_prompt,
        -1,
    )


def _mask_word_id(
    tokens: list, word_ids: list, target: Any, mask_token: tuple[Any, float]
) -> tuple[list, np.ndarray]:
    masked = [
        [mask_token if word_id == target else token
         for token, word_id in zip(row, word_row, strict=True)]
        for row, word_row in zip(tokens, word_ids, strict=True)
    ]
    return masked, np.asarray(word_ids, dtype=object) == target


def _mask_flat_indices(
    tokens: list, indices: np.ndarray, mask_token: tuple[Any, float]
) -> list:
    chunk_length = len(tokens[0])
    selected = {int(index) for index in indices.tolist()}
    return [
        [mask_token if row_index * chunk_length + column in selected else token
         for column, token in enumerate(row)]
        for row_index, row in enumerate(tokens)
    ]


async def _down_weight_embeddings(
    clip,
    component: str,
    tokens: list,
    weights: list,
    word_ids: list,
    base_embedding: torch.Tensor,
    chunk_length: int,
    *,
    mask_token_id: int = 266,
) -> tuple[torch.Tensor, list, torch.Tensor]:
    unique, inverse = np.unique(np.asarray(weights), return_inverse=True)
    if np.sum(unique < 1) == 0:
        return (
            base_embedding,
            tokens,
            base_embedding[0, chunk_length - 1:chunk_length, :],
        )
    mask_token = (mask_token_id, 1.0)
    masked_current = tokens
    masked_prompts = []
    for index, weight in enumerate(unique):
        if weight >= 1:
            continue
        masked_current = _mask_flat_indices(
            masked_current, np.where(inverse == index)[0], mask_token
        )
        masked_prompts.extend(masked_current)
    embeddings = await _batched_component_encode(
        clip,
        component,
        masked_prompts,
        chunk_length=chunk_length,
        chunks_per_prompt=len(tokens),
    )
    embeddings = torch.cat((base_embedding, embeddings))
    bounded_weights = unique[unique <= 1.0]
    mixing = torch.as_tensor(
        np.diff([0.0] + bounded_weights.tolist()),
        dtype=embeddings.dtype,
        device=embeddings.device,
    ).reshape((-1, 1, 1))
    if mixing.shape[0] != embeddings.shape[0]:
        raise ValueError("down-weight prompt did not contain a unit-weight token")
    weighted = (mixing * embeddings).sum(dim=0, keepdim=True)
    return (
        weighted,
        masked_current,
        weighted[0, chunk_length - 1:chunk_length, :],
    )


async def _masked_word_embeddings(
    clip,
    component: str,
    tokens: list,
    weights: list,
    word_ids: list,
    base_embedding: torch.Tensor,
    chunk_length: int,
    *,
    mask_token_id: int = 266,
) -> tuple[torch.Tensor, torch.Tensor]:
    pooled_base = base_embedding[0, chunk_length - 1:chunk_length, :]
    flat_word_ids = np.asarray(word_ids, dtype=object).reshape(-1)
    flat_weights = np.asarray(weights, dtype=float).reshape(-1)
    unique_ids, first_indices = np.unique(flat_word_ids, return_index=True)
    weighted_words = [
        (word_id, float(flat_weights[index]))
        for word_id, index in zip(unique_ids, first_indices, strict=True)
        if float(flat_weights[index]) != 1.0
    ]
    if not weighted_words:
        return torch.zeros_like(base_embedding), pooled_base

    all_weights = torch.as_tensor(
        weights, dtype=base_embedding.dtype, device=base_embedding.device
    ).reshape(1, -1, 1).expand_as(base_embedding)
    mask_token = (mask_token_id, 1.0)
    masked_prompts, masks, selected_weights = [], [], []
    for word_id, weight in weighted_words:
        masked, selected = _mask_word_id(
            tokens, word_ids, word_id, mask_token
        )
        masked_prompts.extend(masked)
        masks.append(torch.as_tensor(
            selected,
            dtype=base_embedding.dtype,
            device=base_embedding.device,
        ).reshape(1, -1, 1).expand_as(base_embedding))
        selected_weights.append(weight)

    embeddings = await _batched_component_encode(
        clip,
        component,
        masked_prompts,
        chunk_length=chunk_length,
        chunks_per_prompt=len(tokens),
    )
    masks_tensor = torch.cat(masks)
    differences = base_embedding.expand_as(embeddings) - embeddings
    pooled = differences[0, chunk_length - 1:chunk_length, :]
    differences = (differences * masks_tensor).sum(dim=0, keepdim=True)

    pooled_start = pooled_base.expand(len(selected_weights), -1)
    selected = torch.as_tensor(
        selected_weights, dtype=pooled_start.dtype, device=pooled_start.device
    ).reshape(-1, 1).expand_as(pooled_start)
    pooled = ((pooled - pooled_start) * (selected - 1.0)).mean(
        dim=0, keepdim=True
    )
    return (all_weights - 1.0) * differences, pooled_base + pooled


async def _advanced_encode_component(
    clip, component: str, tokenized: list, interpretation: str
) -> tuple[torch.Tensor, torch.Tensor | None]:
    tokens, weights, word_ids = _advanced_component_data(tokenized)
    chunk_length = len(tokens[0])
    if any(len(row) != chunk_length for row in tokens):
        raise ValueError("advanced prompt token chunks have inconsistent lengths")
    unweighted = _weighted_pairs(
        tokens, [[1.0] * len(row) for row in tokens]
    )
    base_embedding, pooled_base = await _encode_component_pairs(
        clip, component, unweighted
    )

    if interpretation == "A1111":
        weight_tensor = torch.as_tensor(
            weights, dtype=base_embedding.dtype, device=base_embedding.device
        ).reshape(1, -1, 1).expand_as(base_embedding)
        weighted = base_embedding * weight_tensor
        weighted = (base_embedding.mean() / weighted.mean()) * weighted
    elif interpretation == "compel":
        positive_weights = [
            [weight if weight >= 1.0 else 1.0 for weight in row]
            for row in weights
        ]
        positive_tokens = _weighted_pairs(tokens, positive_weights)
        positive_embedding, _ = await _encode_component_pairs(
            clip, component, positive_tokens
        )
        weighted, _masked, _pooled = await _down_weight_embeddings(
            clip,
            component,
            positive_tokens,
            weights,
            word_ids,
            positive_embedding,
            chunk_length,
        )
    elif interpretation == "comfy++":
        weighted, _masked, _pooled = await _down_weight_embeddings(
            clip,
            component,
            unweighted,
            weights,
            word_ids,
            base_embedding,
            chunk_length,
        )
        up_weights = [
            [weight if weight > 1.0 else 1.0 for weight in row]
            for row in weights
        ]
        additions, _pooled = await _masked_word_embeddings(
            clip,
            component,
            unweighted,
            up_weights,
            word_ids,
            base_embedding,
            chunk_length,
        )
        weighted = weighted + additions
    elif interpretation == "down_weight":
        top = max(weight for row in weights for weight in row)
        limit = min(top, 1.0)
        if top == 0:
            raise ValueError("down-weight prompt cannot normalize zero weights")
        scaled = [
            [limit if word_id == 0 else (weight / top) * limit
             for weight, word_id in zip(row, word_row, strict=True)]
            for row, word_row in zip(weights, word_ids, strict=True)
        ]
        weighted, _masked, _pooled = await _down_weight_embeddings(
            clip,
            component,
            unweighted,
            scaled,
            word_ids,
            base_embedding,
            chunk_length,
        )
    else:
        raise ValueError(f"unknown prompt weight interpretation {interpretation!r}")
    # The frozen loader's public node always kept the encoder's original
    # pooled output (`affect_pooled` was disabled).
    return weighted, pooled_base


async def _encode_prompt(
    clip,
    text: str,
    token_normalization: str,
    weight_interpretation: str,
    *,
    add_dict: dict[str, Any] | None = None,
):
    tokens = await clip.tokenize(str(text), return_word_ids=True)
    tokens = _normalise_token_weights(tokens, str(token_normalization))
    interpretation = str(weight_interpretation)
    if interpretation == "comfy":
        return await clip.encode_from_tokens_scheduled(tokens, add_dict)
    if interpretation not in {"A1111", "compel", "comfy++", "down_weight"}:
        raise ValueError(f"unknown prompt weight interpretation {interpretation!r}")

    components = [key for key in ("l", "g") if key in tokens]
    if not components:
        raise ValueError("advanced prompt weighting supports CLIP-L/CLIP-G encoders")
    encoded = {
        component: await _advanced_encode_component(
            clip, component, tokens[component], interpretation
        )
        for component in components
    }
    if components == ["l", "g"]:
        embedding = torch.cat((encoded["l"][0], encoded["g"][0]), dim=-1)
        pooled = encoded["g"][1]
    else:
        embedding, pooled = encoded[components[0]]
    metadata = {"pooled_output": pooled}
    metadata.update(add_dict or {})
    return await sdk.CondRef.from_value([[embedding, metadata]])


async def _clip_with_skip(clip, clip_skip: int):
    if clip is None:
        raise ValueError("checkpoint did not provide a CLIP text encoder")
    return await clip.set_last_layer(int(clip_skip))


async def _apply_loras(model, clip, entries):
    for index, entry in enumerate(entries or ()):
        if not isinstance(entry, (tuple, list)) or len(entry) < 3:
            raise ValueError(f"LoRA stack entry {index} is malformed")
        name, model_strength, clip_strength = entry[:3]
        if not name or name == "None":
            continue
        asset = await _ctx().assets.resolve("loras", _safe_asset_name(name))
        model, clip = await model.apply_lora(
            asset, clip, float(model_strength), float(clip_strength)
        )
    return model, clip


async def _load_prompt_bundle(
    checkpoint: str,
    vae_name: str,
    clip_skip: int,
    positive_text: str,
    negative_text: str,
    token_normalization: str,
    weight_interpretation: str,
    loras,
    cnet_stack,
    *,
    add_positive: dict[str, Any] | None = None,
    add_negative: dict[str, Any] | None = None,
):
    model, clip, baked_vae = await _ctx().models.load_checkpoint(
        _safe_asset_name(checkpoint)
    )
    model, clip = await _apply_loras(model, clip, loras)
    clip = await _clip_with_skip(clip, clip_skip)
    positive = await _encode_prompt(
        clip, positive_text, token_normalization, weight_interpretation,
        add_dict=add_positive,
    )
    negative = await _encode_prompt(
        clip, negative_text, token_normalization, weight_interpretation,
        add_dict=add_negative,
    )
    positive, negative = await _apply_controlnet_stack(
        positive, negative, cnet_stack
    )
    vae = baked_vae
    if vae_name not in {"Baked VAE", "Baked-VAE", "None", ""}:
        vae = await _ctx().models.load_vae(_safe_asset_name(vae_name))
    if vae is None:
        raise ValueError("checkpoint did not provide a baked VAE; select a VAE")
    return model, clip, vae, positive, negative


async def _efficient_loader(
    ckpt_name,
    vae_name,
    clip_skip,
    lora_name,
    lora_model_strength,
    lora_clip_strength,
    positive,
    negative,
    token_normalization,
    weight_interpretation,
    empty_latent_width,
    empty_latent_height,
    batch_size,
    lora_stack=None,
    cnet_stack=None,
    **_kwargs,
):
    loras = []
    if lora_name and lora_name != "None":
        loras.append((lora_name, lora_model_strength, lora_clip_strength))
    loras.extend(_copy_stack(lora_stack))
    model, clip, vae, positive_cond, negative_cond = await _load_prompt_bundle(
        ckpt_name, vae_name, clip_skip, positive, negative,
        token_normalization, weight_interpretation, loras, cnet_stack,
    )
    width = max(64, int(empty_latent_width) // 8 * 8)
    height = max(64, int(empty_latent_height) // 8 * 8)
    latent = await sdk.LatentRef.empty(width, height, max(1, int(batch_size)))
    dependencies = (
        str(vae_name), str(ckpt_name), clip, int(clip_skip), "None", None, None,
        str(positive), str(negative), str(token_normalization),
        str(weight_interpretation), None, width, height, loras,
        _copy_stack(cnet_stack),
    )
    return model, positive_cond, negative_cond, latent, vae, clip, dependencies


async def _efficient_loader_sdxl(
    base_ckpt_name,
    base_clip_skip,
    refiner_ckpt_name,
    refiner_clip_skip,
    positive_ascore,
    negative_ascore,
    vae_name,
    positive,
    negative,
    token_normalization,
    weight_interpretation,
    empty_latent_width,
    empty_latent_height,
    batch_size,
    lora_stack=None,
    cnet_stack=None,
    **_kwargs,
):
    width = max(64, int(empty_latent_width) // 8 * 8)
    height = max(64, int(empty_latent_height) // 8 * 8)
    loras = _copy_stack(lora_stack)
    base_model, base_clip, vae, base_positive, base_negative = await _load_prompt_bundle(
        base_ckpt_name, vae_name, base_clip_skip, positive, negative,
        token_normalization, weight_interpretation, loras, cnet_stack,
    )
    refiner_model = refiner_clip = refiner_positive = refiner_negative = None
    if refiner_ckpt_name and refiner_ckpt_name != "None":
        refiner_model, refiner_clip, _unused_vae = await _ctx().models.load_checkpoint(
            _safe_asset_name(refiner_ckpt_name)
        )
        refiner_clip = await _clip_with_skip(refiner_clip, refiner_clip_skip)
        common = {"width": width, "height": height}
        refiner_positive = await _encode_prompt(
            refiner_clip, positive, token_normalization, weight_interpretation,
            add_dict={**common, "aesthetic_score": float(positive_ascore)},
        )
        refiner_negative = await _encode_prompt(
            refiner_clip, negative, token_normalization, weight_interpretation,
            add_dict={**common, "aesthetic_score": float(negative_ascore)},
        )
    sdxl = (
        base_model, base_clip, base_positive, base_negative,
        refiner_model, refiner_clip, refiner_positive, refiner_negative,
    )
    latent = await sdk.LatentRef.empty(width, height, max(1, int(batch_size)))
    dependencies = (
        str(vae_name), str(base_ckpt_name), base_clip, int(base_clip_skip),
        str(refiner_ckpt_name), refiner_clip, int(refiner_clip_skip),
        str(positive), str(negative), str(token_normalization),
        str(weight_interpretation), (float(positive_ascore), float(negative_ascore)),
        width, height, loras, _copy_stack(cnet_stack),
    )
    return sdxl, latent, vae, dependencies


# ---------------------------------------------------------------------------
# Sampling.  Script algorithms stay here and call the one generic host sampler.
# ---------------------------------------------------------------------------

def _scheduler_recipe(scheduler: str, denoise: float) -> tuple[str, dict | None]:
    scheduler = str(scheduler)
    if scheduler == "GITS":
        return "normal", {"kind": "gits", "coeff": 1.2, "denoise": float(denoise)}
    if scheduler.startswith("AYS "):
        return "normal", {
            "kind": "ays", "model_type": scheduler.split(" ", 1)[1],
            "denoise": float(denoise),
        }
    return scheduler, None


def _nv_noise(shape: tuple[int, ...], seed: int) -> torch.Tensor:
    """Philox 4x32/Box-Muller stream used by the original NV noise option."""
    count = int(math.prod(shape))
    counter = np.zeros((4, count), dtype=np.uint32)
    counter[2] = np.arange(count, dtype=np.uint32)
    key64 = np.full(count, np.uint64(seed), dtype=np.uint64)
    key = key64.view(np.uint32).reshape(-1, 2).T.copy()
    multipliers = (np.uint64(0xD2511F53), np.uint64(0xCD9E8D57))
    increments = (np.uint32(0x9E3779B9), np.uint32(0xBB67AE85))
    for round_index in range(10):
        first = (counter[0].astype(np.uint64) * multipliers[0]).view(np.uint32).reshape(-1, 2).T
        second = (counter[2].astype(np.uint64) * multipliers[1]).view(np.uint32).reshape(-1, 2).T
        counter[0], counter[1] = second[1] ^ counter[1] ^ key[0], second[0]
        counter[2], counter[3] = first[1] ^ counter[3] ^ key[1], first[0]
        if round_index != 9:
            key[0] = key[0] + increments[0]
            key[1] = key[1] + increments[1]
    inv = np.float32(2.3283064e-10)
    u = counter[0].astype(np.float32) * inv + inv / 2
    v = counter[1].astype(np.float32) * (inv * np.float32(2 * math.pi)) + inv * np.float32(math.pi)
    values = np.sqrt(np.float32(-2.0) * np.log(u)) * np.sin(v)
    return torch.from_numpy(values.astype(np.float32).reshape(shape))


async def _explicit_noise(latent, seed: int, recipe: dict | None):
    if not recipe or (
        recipe.get("rng_source", "cpu") == "cpu" and not recipe.get("add_seed_noise")
    ):
        return None
    value = await latent.value()
    samples = value["samples"]
    source = recipe.get("rng_source", "cpu")

    async def generate(noise_seed: int, shape: tuple[int, ...]):
        if source == "nv":
            return _nv_noise(shape, int(noise_seed)).to(samples.dtype)
        if source == "gpu":
            noise_ref = await latent.random_noise(
                int(noise_seed), "gpu", batch_size=shape[0]
            )
            return await noise_ref.raw()
        generator = torch.Generator(device="cpu").manual_seed(int(noise_seed))
        return torch.randn(shape, generator=generator, dtype=samples.dtype)

    if recipe.get("add_seed_noise"):
        single_shape = (1, *samples.shape[1:])
        base = await generate(int(seed), single_shape)
        other_seed = int(recipe.get("seed", 0))
        other = await generate(other_seed, single_shape)
        weight = max(0.0, min(1.0, float(recipe.get("weight", 0.0))))
        if samples.shape[0] == 1:
            base = base * (1.0 - weight) + other * weight
        else:
            mixed = []
            for index in range(samples.shape[0]):
                amount = weight * index
                mixed.append(
                    base[0] * (1.0 - amount) + other[0] * amount
                )
            base = torch.stack(mixed)
    else:
        base = await generate(int(seed), tuple(samples.shape))
    return await sdk.TensorRef._from_raw(base)


async def _sample_once(
    *,
    model,
    positive,
    negative,
    latent,
    seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    denoise=1.0,
    add_noise="enable",
    start_step=None,
    end_step=None,
    leftover_noise="disable",
    noise_recipe=None,
    explicit_noise=None,
):
    scheduler_name, sigma_schedule = _scheduler_recipe(scheduler, denoise)
    disable_noise = str(add_noise) == "disable"
    explicit = None
    if not disable_noise:
        explicit = explicit_noise
        if explicit is None:
            explicit = await _explicit_noise(latent, int(seed), noise_recipe)
    return await _ctx().sample(
        latent=latent,
        steps=max(1, int(steps)),
        model=model,
        positive=positive,
        negative=negative,
        cfg=float(cfg),
        seed=int(seed),
        sampler_name=str(sampler_name),
        scheduler=scheduler_name,
        denoise=float(denoise),
        disable_noise=disable_noise,
        start_step=None if start_step is None else max(0, int(start_step)),
        last_step=None if end_step is None else max(0, int(end_step)),
        force_full_denoise=str(leftover_noise) != "enable",
        noise=explicit,
        sigma_schedule=sigma_schedule,
        # The legacy CFG denoiser's intent is per-step CFG control.  V2 uses
        # the generic steering seam instead of replacing Comfy's sampler class.
        steer_cfg=bool(noise_recipe and noise_recipe.get("cfg_denoiser")),
    )


async def _resize_image_raw(
    image, factor: float, mode: str = "nearest-exact"
):
    raw = await image.raw()
    if raw.ndim != 4:
        raise ValueError("image resize requires BHWC images")
    height = max(1, round(raw.shape[1] * float(factor)))
    width = max(1, round(raw.shape[2] * float(factor)))
    mode = mode if mode in {"nearest-exact", "bilinear", "area", "bicubic"} else "nearest-exact"
    kwargs = {"align_corners": False} if mode in {"bilinear", "bicubic"} else {}
    output = F.interpolate(
        raw.movedim(-1, 1).float(), size=(height, width), mode=mode,
        **kwargs,
    ).movedim(1, -1)
    return await sdk.ImageRef._from_raw(output)


def _resize_latent_noise_mask(
    value: dict[str, Any], size: tuple[int, int], *, mode: str = "bicubic"
) -> None:
    mask = value.get("noise_mask")
    if not isinstance(mask, torch.Tensor):
        return
    original_dimensions = mask.ndim
    while mask.ndim < 4:
        mask = mask.unsqueeze(1)
    kwargs = {"align_corners": False} if mode in {"bilinear", "bicubic"} else {}
    mask = F.interpolate(mask.float(), size=size, mode=mode, **kwargs)
    while mask.ndim > original_dimensions:
        mask = mask.squeeze(1)
    value["noise_mask"] = mask


async def _city96_resize_latent(
    latent, factor: float, version: str, catalogue_name: str
):
    state = await _load_declared_state(catalogue_name)
    value = dict(await latent.value())
    samples = value.get("samples")
    if not isinstance(samples, torch.Tensor) or samples.ndim != 4:
        raise ValueError("City96 latent upscaling requires BCHW samples")
    model = _City96Upscaler(factor).eval()
    model.load_state_dict(state, strict=True)
    with torch.inference_mode():
        resized = model(samples.detach().float().cpu())
    value["samples"] = resized.to(dtype=samples.dtype)
    _resize_latent_noise_mask(value, tuple(resized.shape[-2:]))
    return await sdk.LatentRef.from_value(value)


async def _ttl_resize_latent(
    latent, factor: float, version: str, catalogue_name: str
):
    state = await _load_declared_state(catalogue_name)
    value = dict(await latent.value())
    samples = value.get("samples")
    if not isinstance(samples, torch.Tensor) or samples.ndim != 4:
        raise ValueError("TTL latent upscaling requires BCHW samples")
    model = _TtlLatentResizer.from_state_dict(state)
    scaling = 0.13025
    with torch.inference_mode():
        resized = model(
            samples.detach().float().cpu() * scaling,
            scale=float(factor),
        ) / scaling
    value["samples"] = resized.to(dtype=samples.dtype)
    _resize_latent_noise_mask(value, tuple(resized.shape[-2:]))
    return await sdk.LatentRef.from_value(value)


async def _resize_latent_raw(
    latent,
    factor: float,
    mode: str = "bilinear",
    weight_name: str | None = None,
):
    factor = float(factor)
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError("latent upscale factor must be positive and finite")
    mode = str(mode)
    if mode.startswith("city96."):
        if not weight_name:
            raise ValueError("City96 latent weights were not provisioned")
        return await _city96_resize_latent(
            latent, factor, mode.removeprefix("city96."), weight_name
        )
    if mode.startswith("ttl_nn."):
        if not weight_name:
            raise ValueError("TTL latent weights were not provisioned")
        return await _ttl_resize_latent(
            latent, factor, mode.removeprefix("ttl_nn."), weight_name
        )
    if mode not in {"nearest-exact", "bilinear", "area", "bicubic", "bislerp"}:
        mode = "nearest-exact"
    height, width = await latent.spatial_shape()
    return await latent.resize(
        max(1, round(width * factor)),
        max(1, round(height * factor)),
        mode,
    )


async def _post_scripts(
    latent,
    image,
    *,
    model,
    positive,
    negative,
    vae,
    cfg,
    sampler_name,
    scheduler,
    seed,
    vae_decode,
    script,
):
    hires = (script or {}).get("hiresfix")
    if hires and int(hires.get("iterations", 0)) > 0:
        work_model = model
        if hires.get("checkpoint"):
            work_model, _clip, _vae = await _ctx().models.load_checkpoint(hires["checkpoint"])
        work_seed = int(seed) if hires.get("use_same_seed") else int(hires["seed"])
        mode = hires["upscale_type"]
        for _index in range(max(0, int(hires["iterations"]))):
            if mode in {"pixel", "both"}:
                image = image or await (
                    vae.decode_tiled(latent, tile_size=320)
                    if "tiled" in vae_decode else vae.decode(latent)
                )
                upscaler_name = hires.get("pixel_upscaler")
                if upscaler_name:
                    upscaler = await _ctx().models.load_upscale_model(upscaler_name)
                    image = await upscaler.upscale(image)
                    # Most ESRGAN models are 4x; preserve the original node's
                    # requested final scale rather than exposing that detail.
                    current_factor = float(hires["upscale_by"]) / 4.0
                    if not math.isclose(current_factor, 1.0):
                        image = await _resize_image_raw(image, current_factor)
                else:
                    image = await _resize_image_raw(image, float(hires["upscale_by"]))
                if mode == "pixel":
                    continue
                latent = await vae.encode(await image.rgb())
                image = None
            if mode in {"latent", "both"}:
                latent = await _resize_latent_raw(
                    latent, float(hires["upscale_by"]) if mode == "latent" else 1.0,
                    str(hires.get("latent_upscaler", "bilinear")),
                    hires.get("latent_weight"),
                )
                control = hires.get("control_net")
                use_positive, use_negative = positive, negative
                if control is not None:
                    control_image = image or await vae.decode(latent)
                    use_positive, use_negative = await control.apply(
                        positive, negative, control_image,
                        strength=float(hires.get("control_strength", 1.0)),
                    )
                latent = await _sample_once(
                    model=work_model, positive=use_positive, negative=use_negative,
                    latent=latent, seed=work_seed, steps=hires["steps"], cfg=cfg,
                    sampler_name=sampler_name, scheduler=scheduler,
                    denoise=hires["denoise"],
                )
                image = None

    tile = (script or {}).get("tile")
    if tile:
        image = image or await (
            vae.decode_tiled(latent, tile_size=320)
            if "tiled" in vae_decode else vae.decode(latent)
        )
        image = await _resize_image_raw(image, float(tile["upscale_by"]))
        latent = await vae.encode(await image.rgb())
        use_positive, use_negative = positive, negative
        if tile.get("control_net") is not None:
            use_positive, use_negative = await tile["control_net"].apply(
                positive, negative, image, strength=float(tile.get("strength", 1.0))
            )
        # Tiling remains a pack algorithm.  Sampling each bounded tile and
        # feathering overlaps is implemented by the helper below.
        latent = await _sample_tiled(
            latent, model=model, positive=use_positive, negative=use_negative,
            seed=tile["seed"], steps=tile["steps"], cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler,
            denoise=tile["denoise"], tile_size=tile["tile_size"],
            strategy=tile["strategy"],
        )
        image = None
    return latent, image


async def _sample_tiled(
    latent,
    *,
    model,
    positive,
    negative,
    seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    denoise,
    tile_size,
    strategy,
):
    if float(denoise) <= 0:
        return latent
    value = dict(await latent.value())
    samples = value["samples"].clone()
    total_steps = max(int(steps), int(int(steps) / float(denoise)))
    start_step = max(0, total_steps - int(steps))
    height, width = map(int, samples.shape[-2:])
    tile_height = min(height, max(8, int(tile_size) // 8))
    tile_width = min(width, max(8, int(tile_size) // 8))
    if height <= tile_height and width <= tile_width:
        return await _sample_once(
            model=model, positive=positive, negative=negative, latent=latent,
            seed=seed, steps=total_steps, cfg=cfg, sampler_name=sampler_name,
            scheduler=scheduler, denoise=1.0, start_step=start_step,
            end_step=total_steps,
        )

    batch = int(samples.shape[0])

    source_mask = value.get("noise_mask")
    if isinstance(source_mask, torch.Tensor):
        source_mask = source_mask.detach().float().cpu()
        while source_mask.ndim < 4:
            source_mask = source_mask.unsqueeze(1)
        if source_mask.shape[1] != 1:
            source_mask = source_mask[:, :1]
        if tuple(source_mask.shape[-2:]) != (height, width):
            source_mask = F.interpolate(
                source_mask, size=(height, width), mode="bilinear",
                align_corners=False,
            )
        if source_mask.shape[0] != batch:
            repeats = math.ceil(batch / max(1, int(source_mask.shape[0])))
            source_mask = source_mask.repeat(repeats, 1, 1, 1)[:batch]
    else:
        source_mask = None

    noise_ref = await latent.random_noise(int(seed), "cpu")
    global_noise = (await noise_ref.raw()).to(dtype=samples.dtype, device="cpu")

    strategy = str(strategy)
    if strategy not in {"simple", "padded", "random", "random strict"}:
        raise ValueError(f"unknown tiled sampling strategy {strategy!r}")

    # The legacy sampler creates one full-image noise field.  Non-padded
    # strategies add it once before slicing, so overlapping/random tiles do
    # not independently reseed.  The scalar schedule query keeps all tiling
    # and mask arithmetic here while core owns the model-specific sigma scale.
    if strategy != "padded":
        scheduler_name, sigma_schedule = _scheduler_recipe(scheduler, 1.0)
        sigma = await model.sampling_sigma_delta(
            steps=total_steps,
            sampler_name=str(sampler_name),
            scheduler=scheduler_name,
            start_step=start_step,
            end_step=total_steps,
            denoise=1.0,
            sigma_schedule=sigma_schedule,
        )
        scaled_noise = global_noise * float(sigma)
        if source_mask is not None:
            scaled_noise = scaled_noise * source_mask.to(scaled_noise)
        samples.add_(scaled_noise)

    def simple_tiles():
        return [[(
            y, min(tile_height, height - y),
            x, min(tile_width, width - x), None,
        ) for y in range(0, height, tile_height)
          for x in range(0, width, tile_width)]]

    def padded_passes():
        size_h = max(4, (tile_height // 4) * 4)
        size_w = max(4, (tile_width // 4) * 4)
        quarter_h = size_h // 4
        quarter_w = size_w // 4
        ys = list(range(0, height, size_h))
        xs = list(range(0, width, size_w))
        shifted_y = list(range(
            size_h // 2, max(size_h // 2, height - size_h // 2), size_h
        ))
        shifted_x = list(range(
            size_w // 2, max(size_w // 2, width - size_w // 2), size_w
        ))

        def grid(y_values, x_values, mask_height, mask_width):
            tiles = []
            for y_index, y in enumerate(y_values):
                for x_index, x in enumerate(x_values):
                    h = min(size_h, height - y)
                    w = min(size_w, width - x)
                    mask = torch.zeros((batch, 1, h, w), dtype=torch.float32)
                    top = 0 if mask_height and y_index == 0 else quarter_h
                    bottom = (
                        h if mask_height and y_index == len(y_values) - 1
                        else min(h, size_h - quarter_h)
                    )
                    left = 0 if mask_width and x_index == 0 else quarter_w
                    right = (
                        w if mask_width and x_index == len(x_values) - 1
                        else min(w, size_w - quarter_w)
                    )
                    if top < bottom and left < right:
                        mask[:, :, top:bottom, left:right] = 1.0
                    tiles.append((y, h, x, w, mask))
            return tiles

        return [
            grid(ys, xs, True, True),
            grid(shifted_y, xs, False, True),
            grid(ys, shifted_x, True, False),
            grid(shifted_y, shifted_x, False, False),
        ]

    def random_step_tiles(generator: torch.Generator, step_index: int):
        def coordinates(length, size, jitter):
            count = int((length + jitter - 1) // size + 1)
            points = [
                int(np.clip(size * index - jitter, 0, length))
                for index in range(count + 1)
            ]
            return [
                (first, second - first)
                for first, second in zip(points, points[1:])
                if second > first
            ]

        values = torch.rand((2,), generator=generator).tolist()
        jitter_x = (
            int(values[0] * tile_width),
            int(((values[0] + 0.5) % 1.0) * tile_width),
        )
        jitter_y = (
            int(values[1] * tile_height),
            int(((values[1] + 0.5) % 1.0) * tile_height),
        )
        y_sets = [coordinates(height, tile_height, item) for item in jitter_y]
        x_sets = [coordinates(width, tile_width, item) for item in jitter_x]
        tiles = []
        if step_index % 2 == 0:
            for y_index, (y, h) in enumerate(y_sets[0]):
                for x, w in x_sets[y_index % 2]:
                    tiles.append((y, h, x, w, None))
        else:
            for x_index, (x, w) in enumerate(x_sets[0]):
                for y, h in y_sets[x_index % 2]:
                    tiles.append((y, h, x, w, None))
        return tiles

    def boundary_tile(y, h, x, w, mask):
        if ((h == tile_height or h == height)
                and (w == tile_width or w == width)):
            return y, h, x, w, mask
        offset_y = min(0, height - (y + tile_height))
        offset_x = min(0, width - (x + tile_width))
        full_mask = torch.zeros(
            (batch, 1, tile_height, tile_width), dtype=torch.float32
        )
        source = 1.0 if mask is None else mask
        full_mask[
            :, :,
            -offset_y:h if offset_y == 0 else tile_height,
            -offset_x:w if offset_x == 0 else tile_width,
        ] = source
        return (
            y + offset_y, tile_height,
            x + offset_x, tile_width,
            full_mask,
        )

    async def run_tile(source, tile, first_step, last_step, *, strict=False):
        y, h, x, w, mask = tile
        if source_mask is not None:
            sliced_source_mask = source_mask[..., y:y + h, x:x + w]
            mask = (
                sliced_source_mask
                if mask is None else mask * sliced_source_mask
            )
        if strict or strategy == "padded":
            y, h, x, w, mask = boundary_tile(y, h, x, w, mask)
        if mask is not None and not bool(mask.any()):
            return y, h, x, w, mask
        tile_value = {
            "samples": source[..., y:y + h, x:x + w].clone()
        }
        if mask is not None:
            tile_value["noise_mask"] = mask
        tile_ref = await sdk.LatentRef.from_value(tile_value)
        pos_tile = await positive.spatial_crop(
            x=x, y=y, width=w, height=h,
            source_width=width, source_height=height,
        )
        neg_tile = await negative.spatial_crop(
            x=x, y=y, width=w, height=h,
            source_width=width, source_height=height,
        )
        explicit_noise = None
        add_noise = "disable"
        if strategy == "padded":
            explicit_noise = await sdk.TensorRef._from_raw(
                global_noise[..., y:y + h, x:x + w].clone()
            )
            add_noise = "enable"
        sampled = await _sample_once(
            model=model,
            positive=pos_tile,
            negative=neg_tile,
            latent=tile_ref,
            seed=int(seed),
            steps=total_steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=1.0,
            start_step=first_step,
            end_step=last_step,
            leftover_noise=("disable" if last_step >= total_steps else "enable"),
            add_noise=add_noise,
            explicit_noise=explicit_noise,
        )
        result = (await sampled.value())["samples"]
        destination = source[..., y:y + h, x:x + w]
        if mask is None:
            destination.copy_(result)
        else:
            blend = mask.to(device=destination.device, dtype=destination.dtype)
            destination.copy_(destination * (1.0 - blend) + result * blend)
        return y, h, x, w, mask

    if strategy in {"random", "random strict"}:
        generator = torch.Generator(device="cpu").manual_seed(int(seed))
        for step_index in range(int(steps)):
            tiles = random_step_tiles(generator, step_index)
            if strategy == "random strict":
                next_samples = samples.clone()
                for tile in tiles:
                    before = samples.clone()
                    y, h, x, w, mask = await run_tile(
                        before,
                        tile,
                        start_step + step_index,
                        start_step + step_index + 1,
                        strict=True,
                    )
                    changed = before[..., y:y + h, x:x + w]
                    destination = next_samples[..., y:y + h, x:x + w]
                    if mask is None:
                        destination.copy_(changed)
                    else:
                        blend = mask.to(destination)
                        destination.copy_(
                            destination * (1.0 - blend) + changed * blend
                        )
                samples = next_samples
            else:
                for tile in tiles:
                    await run_tile(
                        samples,
                        tile,
                        start_step + step_index,
                        start_step + step_index + 1,
                    )
    else:
        passes = padded_passes() if strategy == "padded" else simple_tiles()
        for tiles in passes:
            for tile in tiles:
                await run_tile(samples, tile, start_step, total_steps)

    value["samples"] = samples
    return await sdk.LatentRef.from_value(value)


async def _decode_result(vae, latent, vae_decode):
    if vae is None or "true" not in str(vae_decode):
        return await sdk.ImageRef._from_raw(torch.zeros((1, 1, 1, 4), dtype=torch.float32))
    if "tiled" in str(vae_decode):
        return await vae.decode_tiled(latent, tile_size=320)
    return await vae.decode(latent)


async def _sampler_common(
    *,
    model,
    positive,
    negative,
    latent_image,
    seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    denoise,
    vae,
    vae_decode,
    preview_method,
    script,
    sampler_type,
    add_noise="enable",
    start_at_step=None,
    end_at_step=None,
    return_with_leftover_noise="disable",
    sdxl_tuple=None,
):
    if script and script.get("xyplot"):
        return await _sample_xy_plot(
            model=model, positive=positive, negative=negative,
            latent_image=latent_image, seed=seed, steps=steps, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler, denoise=denoise,
            vae=vae, vae_decode=vae_decode, preview_method=preview_method,
            script=script, sampler_type=sampler_type, add_noise=add_noise,
            start_at_step=start_at_step, end_at_step=end_at_step,
            return_with_leftover_noise=return_with_leftover_noise,
            sdxl_tuple=sdxl_tuple,
        )
    noise_recipe = (script or {}).get("noise")
    if sampler_type == "sdxl":
        base_model, _clip, base_positive, base_negative, refiner_model, _rclip, refiner_positive, refiner_negative = sdxl_tuple
        switch = int(steps) if int(end_at_step) == -1 else int(end_at_step)
        latent = await _sample_once(
            model=base_model, positive=base_positive, negative=base_negative,
            latent=latent_image, seed=seed, steps=steps, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler, denoise=1.0,
            add_noise="enable", start_step=start_at_step, end_step=switch,
            leftover_noise="enable", noise_recipe=noise_recipe,
        )
        if refiner_model is not None and switch < int(steps):
            latent = await _sample_once(
                model=refiner_model, positive=refiner_positive,
                negative=refiner_negative, latent=latent, seed=seed, steps=steps,
                cfg=cfg, sampler_name=sampler_name, scheduler=scheduler,
                denoise=1.0, add_noise="disable", start_step=switch,
                end_step=steps, leftover_noise="disable", noise_recipe=noise_recipe,
            )
        work_model, work_positive, work_negative = base_model, base_positive, base_negative
    else:
        if sampler_type == "regular" and float(denoise) <= 0:
            latent = latent_image
        else:
            latent = await _sample_once(
                model=model, positive=positive, negative=negative,
                latent=latent_image, seed=seed, steps=steps, cfg=cfg,
                sampler_name=sampler_name, scheduler=scheduler,
                denoise=denoise, add_noise=add_noise,
                start_step=start_at_step, end_step=end_at_step,
                leftover_noise=return_with_leftover_noise,
                noise_recipe=noise_recipe,
            )
        work_model, work_positive, work_negative = model, positive, negative
    latent, image = await _post_scripts(
        latent, None, model=work_model, positive=work_positive,
        negative=work_negative, vae=vae, cfg=cfg, sampler_name=sampler_name,
        scheduler=scheduler, seed=seed, vae_decode=vae_decode, script=script,
    )
    image = image or await _decode_result(vae, latent, vae_decode)
    ui = None
    if preview_method != "none" and not (
        preview_method == "vae_decoded_only" and "true" not in vae_decode
    ):
        ui = await _ctx().ui.preview_images(image)
    if sampler_type == "sdxl":
        result = (sdxl_tuple, latent, vae, image)
    else:
        result = (model, positive, negative, latent, vae, image)
    return {"result": result, **({"ui": ui} if ui is not None else {})}


async def _ksampler(
    model,
    seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    positive,
    negative,
    latent_image,
    denoise,
    preview_method,
    vae_decode,
    optional_vae=None,
    script=None,
    **_kwargs,
):
    return await _sampler_common(
        model=model, positive=positive, negative=negative, latent_image=latent_image,
        seed=seed, steps=steps, cfg=cfg, sampler_name=sampler_name,
        scheduler=scheduler, denoise=denoise, vae=optional_vae,
        vae_decode=vae_decode, preview_method=preview_method, script=script,
        sampler_type="regular",
    )


async def _ksampler_advanced(
    model,
    add_noise,
    noise_seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    positive,
    negative,
    latent_image,
    start_at_step,
    end_at_step,
    return_with_leftover_noise,
    preview_method,
    vae_decode,
    optional_vae=None,
    script=None,
    **_kwargs,
):
    return await _sampler_common(
        model=model, positive=positive, negative=negative, latent_image=latent_image,
        seed=noise_seed, steps=steps, cfg=cfg, sampler_name=sampler_name,
        scheduler=scheduler, denoise=1.0, vae=optional_vae,
        vae_decode=vae_decode, preview_method=preview_method, script=script,
        sampler_type="advanced", add_noise=add_noise,
        start_at_step=start_at_step, end_at_step=end_at_step,
        return_with_leftover_noise=return_with_leftover_noise,
    )


async def _ksampler_sdxl(
    sdxl_tuple,
    noise_seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    latent_image,
    start_at_step,
    refine_at_step,
    preview_method,
    vae_decode,
    optional_vae=None,
    script=None,
    **_kwargs,
):
    if not isinstance(sdxl_tuple, (tuple, list)) or len(sdxl_tuple) != 8:
        raise ValueError("KSampler SDXL requires an eight-entry SDXL tuple")
    return await _sampler_common(
        model=sdxl_tuple[0], positive=sdxl_tuple[2], negative=sdxl_tuple[3],
        latent_image=latent_image, seed=noise_seed, steps=steps, cfg=cfg,
        sampler_name=sampler_name, scheduler=scheduler, denoise=1.0,
        vae=optional_vae, vae_decode=vae_decode, preview_method=preview_method,
        script=script, sampler_type="sdxl", start_at_step=start_at_step,
        end_at_step=refine_at_step, sdxl_tuple=tuple(sdxl_tuple),
    )


# XY execution is appended next; keeping it separate makes the engine path
# above independently testable.


def _dependency_state(dependencies, *, model, positive, negative, vae, sdxl_tuple):
    state = {
        "model": model,
        "clip": None,
        "positive": positive,
        "negative": negative,
        "vae": vae,
        "vae_name": "Baked VAE",
        "checkpoint": None,
        "clip_skip": -1,
        "refiner_name": "None",
        "refiner_model": None,
        "refiner_clip": None,
        "refiner_positive": None,
        "refiner_negative": None,
        "refiner_clip_skip": -2,
        "positive_text": "",
        "negative_text": "",
        "token_normalization": "none",
        "weight_interpretation": "comfy",
        "ascore": None,
        "width": 1024,
        "height": 1024,
        "loras": [],
        "cnet_stack": [],
    }
    if isinstance(dependencies, (tuple, list)) and len(dependencies) >= 16:
        (
            state["vae_name"], state["checkpoint"], state["clip"],
            state["clip_skip"], state["refiner_name"], state["refiner_clip"],
            state["refiner_clip_skip"], state["positive_text"],
            state["negative_text"], state["token_normalization"],
            state["weight_interpretation"], state["ascore"], state["width"],
            state["height"], state["loras"], state["cnet_stack"],
        ) = dependencies[:16]
    if sdxl_tuple is not None:
        (
            state["model"], state["clip"], state["positive"], state["negative"],
            state["refiner_model"], state["refiner_clip"],
            state["refiner_positive"], state["refiner_negative"],
        ) = sdxl_tuple
    state["loras"] = _copy_stack(state["loras"])
    state["cnet_stack"] = _copy_stack(state["cnet_stack"])
    return state


def _variant_label(kind: str, value: Any) -> str:
    if kind == "Nothing":
        return ""
    if kind in {"Checkpoint", "Refiner"} and isinstance(value, (tuple, list)):
        value = PurePosixPath(str(value[0])).stem
    elif kind.startswith("LoRA") and isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, (tuple, list)) and first:
            value = f"{PurePosixPath(str(first[0])).stem} ({first[1]},{first[2]})"
    elif kind.startswith("ControlNet") and isinstance(value, list) and value:
        first = value[0]
        index = 2 if kind == "ControlNetStrength" else 3 if kind == "ControlNetStart%" else 4
        value = first[index]
    elif kind in {"Positive Prompt S/R", "Negative Prompt S/R"}:
        value = value[1] if value[1] is not None else value[0]
    elif kind == "Sampler" and isinstance(value, (tuple, list)):
        value = f"{value[0]}{f' ({value[1]})' if value[1] else ''}"
    return f"{kind}: {value}"


def _apply_variant(state: dict[str, Any], params: dict[str, Any], kind: str, value: Any):
    rebuild = False
    if kind == "Nothing":
        return rebuild
    if kind == "Seeds++ Batch":
        params["seed"] = params["base_seed"] + int(value)
    elif kind == "Steps":
        params["steps"] = int(value)
    elif kind == "StartStep":
        params["start_step"] = int(value)
    elif kind in {"EndStep", "RefineStep"}:
        params["end_step"] = int(value)
    elif kind == "AddNoise":
        params["add_noise"] = str(value)
    elif kind == "ReturnNoise":
        params["leftover"] = str(value)
    elif kind == "CFG Scale":
        params["cfg"] = float(value)
    elif kind == "Sampler":
        params["sampler_name"] = value[0]
        if len(value) > 1 and value[1]:
            params["scheduler"] = value[1]
    elif kind == "Scheduler":
        params["scheduler"] = value[0] if isinstance(value, (tuple, list)) else value
    elif kind == "Denoise":
        params["denoise"] = float(value)
    elif kind == "VAE":
        state["vae_name"] = value
        rebuild = True
    elif kind == "Checkpoint":
        state["checkpoint"] = value[0]
        if value[1] is not None:
            state["clip_skip"] = int(value[1])
        if value[2] is not None:
            state["vae_name"] = value[2]
        rebuild = True
    elif kind == "Refiner":
        state["refiner_name"] = value[0]
        if value[1] is not None:
            state["refiner_clip_skip"] = int(value[1])
        rebuild = True
    elif kind == "Clip Skip":
        state["clip_skip"] = int(value)
        rebuild = True
    elif kind == "Clip Skip (Refiner)":
        state["refiner_clip_skip"] = int(value)
        rebuild = True
    elif kind in {"LoRA", "LoRA Stacks", "LoRA Batch", "LoRA Wt", "LoRA MStr", "LoRA CStr"}:
        state["loras"] = _copy_stack(value)
        rebuild = True
    elif kind == "Positive Prompt S/R":
        search, replacement = value
        if replacement is not None:
            state["positive_text"] = str(state["positive_text"]).replace(
                str(search), str(replacement), 1
            )
        rebuild = True
    elif kind == "Negative Prompt S/R":
        search, replacement = value
        if replacement is not None:
            state["negative_text"] = str(state["negative_text"]).replace(
                str(search), str(replacement), 1
            )
        rebuild = True
    elif kind == "AScore+":
        current = state["ascore"] or (6.0, 2.0)
        state["ascore"] = (float(value), float(current[1]))
        rebuild = True
    elif kind == "AScore-":
        current = state["ascore"] or (6.0, 2.0)
        state["ascore"] = (float(current[0]), float(value))
        rebuild = True
    elif kind == "Refiner On/Off":
        params["end_step"] = round(float(value) * int(params["steps"]))
    elif kind.startswith("ControlNet"):
        state["cnet_stack"] = _copy_stack(value)
        rebuild = True
    else:
        raise ValueError(f"unsupported XY parameter type {kind!r}")
    return rebuild


async def _rebuild_variant_state(state: dict[str, Any], sampler_type: str):
    if not state.get("checkpoint"):
        raise ValueError("this XY type requires Efficient Loader dependencies")
    model, clip, vae, positive, negative = await _load_prompt_bundle(
        state["checkpoint"], state["vae_name"], state["clip_skip"],
        state["positive_text"], state["negative_text"],
        state["token_normalization"], state["weight_interpretation"],
        state["loras"], state["cnet_stack"],
    )
    state.update({
        "model": model, "clip": clip, "vae": vae,
        "positive": positive, "negative": negative,
    })
    if sampler_type == "sdxl" and state.get("refiner_name") not in {None, "", "None"}:
        refiner_model, refiner_clip, _refiner_vae = await _ctx().models.load_checkpoint(
            _safe_asset_name(state["refiner_name"])
        )
        refiner_clip = await _clip_with_skip(refiner_clip, state["refiner_clip_skip"])
        scores = state["ascore"] or (6.0, 2.0)
        common = {"width": int(state["width"]), "height": int(state["height"])}
        refiner_positive = await _encode_prompt(
            refiner_clip, state["positive_text"], state["token_normalization"],
            state["weight_interpretation"],
            add_dict={**common, "aesthetic_score": float(scores[0])},
        )
        refiner_negative = await _encode_prompt(
            refiner_clip, state["negative_text"], state["token_normalization"],
            state["weight_interpretation"],
            add_dict={**common, "aesthetic_score": float(scores[1])},
        )
        state.update({
            "refiner_model": refiner_model, "refiner_clip": refiner_clip,
            "refiner_positive": refiner_positive,
            "refiner_negative": refiner_negative,
        })


def _draw_grid(images: list[torch.Tensor], columns: int, rows: int, x_labels, y_labels, spacing: int, vertical_y: bool):
    if not images:
        raise ValueError("XY plot produced no images")
    height, width = map(int, images[0].shape[:2])
    label_height = max(24, height // 14) if any(x_labels) else 0
    label_width = max(72, width // 4) if any(y_labels) else 0
    canvas = Image.new(
        "RGB",
        (
            label_width + columns * width + max(0, columns - 1) * spacing,
            label_height + rows * height + max(0, rows - 1) * spacing,
        ),
        "white",
    )
    font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    for row in range(rows):
        for column in range(columns):
            index = row * columns + column
            image = _pil_from_image(images[index]).convert("RGB")
            x = label_width + column * (width + spacing)
            y = label_height + row * (height + spacing)
            canvas.paste(image, (x, y))
            if row == 0 and x_labels[column]:
                draw.text((x + 4, 4), str(x_labels[column]), fill="black", font=font)
            if column == 0 and y_labels[row]:
                label = str(y_labels[row])
                if vertical_y:
                    temp = Image.new("RGBA", (height, 18), (255, 255, 255, 0))
                    ImageDraw.Draw(temp).text((2, 2), label, fill="black", font=font)
                    temp = temp.rotate(90, expand=True)
                    canvas.paste(temp.convert("RGB"), (2, y + max(0, (height - temp.height) // 2)))
                else:
                    draw.text((4, y + 4), label, fill="black", font=font)
    return _tensor_from_pil(canvas).unsqueeze(0)


async def _sample_xy_plot(
    *,
    model,
    positive,
    negative,
    latent_image,
    seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    denoise,
    vae,
    vae_decode,
    preview_method,
    script,
    sampler_type,
    add_noise,
    start_at_step,
    end_at_step,
    return_with_leftover_noise,
    sdxl_tuple,
):
    recipe = script["xyplot"]
    dependencies = recipe.get("dependencies")
    base_state = _dependency_state(
        dependencies, model=model, positive=positive, negative=negative,
        vae=vae, sdxl_tuple=sdxl_tuple,
    )
    base_params = {
        "base_seed": int(seed), "seed": int(seed), "steps": int(steps),
        "cfg": float(cfg), "sampler_name": str(sampler_name),
        "scheduler": str(scheduler), "denoise": float(denoise),
        "add_noise": str(add_noise), "start_step": start_at_step,
        "end_step": end_at_step, "leftover": str(return_with_leftover_noise),
    }
    x_values = list(recipe.get("x_values") or [""])
    y_values = list(recipe.get("y_values") or [""])
    x_type, y_type = recipe["x_type"], recipe["y_type"]
    latent_value = dict(await latent_image.value())
    initial = {key: value[:1].clone() if isinstance(value, torch.Tensor) and value.ndim else value for key, value in latent_value.items()}
    images: list[torch.Tensor] = []
    latents: list[dict[str, Any]] = []

    for y_value in y_values:
        for x_value in x_values:
            state = copy.copy(base_state)
            state["loras"] = _copy_stack(base_state["loras"])
            state["cnet_stack"] = _copy_stack(base_state["cnet_stack"])
            params = dict(base_params)
            rebuild = _apply_variant(state, params, x_type, x_value)
            rebuild = _apply_variant(state, params, y_type, y_value) or rebuild
            if rebuild:
                await _rebuild_variant_state(state, sampler_type)
            cell_latent = await sdk.LatentRef.from_value(copy.deepcopy(initial))
            noise_recipe = script.get("noise")
            if sampler_type == "sdxl":
                switch = int(params["steps"]) if int(params["end_step"] or -1) == -1 else int(params["end_step"])
                sampled = await _sample_once(
                    model=state["model"], positive=state["positive"],
                    negative=state["negative"], latent=cell_latent,
                    seed=params["seed"], steps=params["steps"], cfg=params["cfg"],
                    sampler_name=params["sampler_name"], scheduler=params["scheduler"],
                    denoise=1.0, add_noise="enable", start_step=params["start_step"],
                    end_step=switch, leftover_noise="enable", noise_recipe=noise_recipe,
                )
                if state.get("refiner_model") is not None and switch < params["steps"]:
                    sampled = await _sample_once(
                        model=state["refiner_model"], positive=state["refiner_positive"],
                        negative=state["refiner_negative"], latent=sampled,
                        seed=params["seed"], steps=params["steps"], cfg=params["cfg"],
                        sampler_name=params["sampler_name"], scheduler=params["scheduler"],
                        denoise=1.0, add_noise="disable", start_step=switch,
                        end_step=params["steps"], leftover_noise="disable",
                        noise_recipe=noise_recipe,
                    )
            else:
                if sampler_type == "regular" and params["denoise"] <= 0:
                    sampled = cell_latent
                else:
                    sampled = await _sample_once(
                        model=state["model"], positive=state["positive"],
                        negative=state["negative"], latent=cell_latent,
                        seed=params["seed"], steps=params["steps"],
                        cfg=params["cfg"],
                        sampler_name=params["sampler_name"],
                        scheduler=params["scheduler"],
                        denoise=params["denoise"],
                        add_noise=params["add_noise"],
                        start_step=params["start_step"],
                        end_step=params["end_step"],
                        leftover_noise=params["leftover"],
                        noise_recipe=noise_recipe,
                    )
            sampled, cell_image = await _post_scripts(
                sampled, None, model=state["model"], positive=state["positive"],
                negative=state["negative"], vae=state["vae"], cfg=params["cfg"],
                sampler_name=params["sampler_name"], scheduler=params["scheduler"],
                seed=params["seed"], vae_decode="true", script=script,
            )
            cell_image = cell_image or await state["vae"].decode(sampled)
            image_raw = await cell_image.raw()
            images.append(image_raw[0].detach().cpu())
            latents.append(await sampled.value())

    sample_shapes = {tuple(value["samples"].shape[1:]) for value in latents}
    if len(sample_shapes) != 1:
        raise ValueError("XY variants produced incompatible latent dimensions")
    combined = dict(latents[0])
    combined["samples"] = torch.cat([value["samples"] for value in latents], dim=0)
    if all(isinstance(value.get("noise_mask"), torch.Tensor) for value in latents):
        combined["noise_mask"] = torch.cat([value["noise_mask"] for value in latents], dim=0)
    combined_ref = await sdk.LatentRef.from_value(combined)
    image_shapes = {tuple(value.shape) for value in images}
    if len(image_shapes) != 1:
        raise ValueError("XY variants produced incompatible image dimensions")
    image_batch = torch.stack(images)
    x_labels = [_variant_label(x_type, value) for value in x_values]
    y_labels = [_variant_label(y_type, value) for value in y_values]
    grid = _draw_grid(
        images, len(x_values), len(y_values), x_labels, y_labels,
        int(recipe.get("grid_spacing", 0)),
        recipe.get("y_label_orientation") == "Vertical",
    )
    output_raw = grid if recipe.get("plot_as_output") else image_batch
    output_image = await sdk.ImageRef._from_raw(output_raw)
    grid_ref = await sdk.ImageRef._from_raw(grid)
    ui = await _ctx().ui.preview_images(grid_ref)
    if sampler_type == "sdxl":
        result = (sdxl_tuple, combined_ref, vae, output_image)
    else:
        result = (model, positive, negative, combined_ref, vae, output_image)
    return {"ui": ui, "result": result}


# ---------------------------------------------------------------------------
# Complete, explicit node census.
# ---------------------------------------------------------------------------

_HANDLERS = {
    "Apply ControlNet Stack": _apply_controlnet_stack,
    "Control Net Stacker": _controlnet_stacker,
    "Eff. Loader SDXL": _efficient_loader_sdxl,
    "Efficient Loader": _efficient_loader,
    "Evaluate Floats": _evaluate_number,
    "Evaluate Integers": _evaluate_number,
    "Evaluate Strings": _evaluate_string,
    "HighRes-Fix Script": _hires_script,
    "Image Overlay": _image_overlay,
    "Join XY Inputs of Same Type": _xy_join,
    "KSampler (Efficient)": _ksampler,
    "KSampler Adv. (Efficient)": _ksampler_advanced,
    "KSampler SDXL (Eff.)": _ksampler_sdxl,
    "LoRA Stack to String converter": _lora_stack_string,
    "LoRA Stacker": _lora_stacker,
    "Manual XY Entry Info": _information_node,
    "Noise Control Script": _noise_script,
    "Pack SDXL Tuple": _pack_sdxl,
    "Simple Eval Examples": _information_node,
    "Tiled Upscaler Script": _tile_script,
    "Unpack SDXL Tuple": _unpack_sdxl,
    "XY Input: Add/Return Noise": _xy_noise,
    "XY Input: Aesthetic Score": _xy_ascore,
    "XY Input: CFG Scale": _xy_cfg,
    "XY Input: Checkpoint": _xy_checkpoint,
    "XY Input: Clip Skip": _xy_clip_skip,
    "XY Input: Control Net": _xy_controlnet,
    "XY Input: Control Net Plot": _xy_controlnet_plot,
    "XY Input: Denoise": _xy_denoise,
    "XY Input: LoRA": _xy_lora,
    "XY Input: LoRA Plot": _xy_lora_plot,
    "XY Input: LoRA Stacks": _xy_lora_stacks,
    "XY Input: Manual XY Entry": _xy_manual,
    "XY Input: Prompt S/R": _xy_prompt,
    "XY Input: Refiner On/Off": _xy_refiner,
    "XY Input: Sampler/Scheduler": _xy_sampler,
    "XY Input: Seeds++ Batch": _xy_seed,
    "XY Input: Steps": _xy_steps,
    "XY Input: VAE": _xy_vae,
    "XY Plot": _xy_plot,
}

if set(_HANDLERS) != set(SCHEMAS):
    raise RuntimeError(
        "Efficiency secure conversion coverage changed: "
        f"missing={sorted(set(SCHEMAS) - set(_HANDLERS))}, "
        f"extra={sorted(set(_HANDLERS) - set(SCHEMAS))}"
    )


_PERMISSIONS: dict[str, tuple[str, ...]] = {node_id: () for node_id in _HANDLERS}
for _node_id in {"Efficient Loader", "Eff. Loader SDXL"}:
    _PERMISSIONS[_node_id] = ("assets", "models", "raw")
for _node_id in {
    "KSampler (Efficient)", "KSampler Adv. (Efficient)", "KSampler SDXL (Eff.)",
}:
    _PERMISSIONS[_node_id] = ("assets", "models", "output", "raw", "sample", "ui")
for _node_id in {"HighRes-Fix Script", "Tiled Upscaler Script"}:
    _PERMISSIONS[_node_id] = ("models",)
_PERMISSIONS["HighRes-Fix Script"] = ("models", "models.download")
for _node_id in {
    "XY Input: VAE", "XY Input: Checkpoint", "XY Input: LoRA",
    "XY Input: LoRA Plot", "XY Input: Manual XY Entry",
}:
    _PERMISSIONS[_node_id] = ("assets",)
_PERMISSIONS["Image Overlay"] = ("raw",)


NODE_CLASS_MAPPINGS = {
    node_id: bind_node(
        node_id,
        handler,
        permissions=_PERMISSIONS[node_id],
        required_weights=(
            _HIRES_REQUIRED_WEIGHTS
            if node_id == "HighRes-Fix Script"
            else ()
        ),
    )
    for node_id, handler in _HANDLERS.items()
}
NODE_DISPLAY_NAME_MAPPINGS = {node_id: node_id for node_id in NODE_CLASS_MAPPINGS}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
