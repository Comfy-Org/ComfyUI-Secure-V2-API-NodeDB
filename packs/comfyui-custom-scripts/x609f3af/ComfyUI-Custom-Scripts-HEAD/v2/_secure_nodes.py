"""Secure Nodes 2.0 implementations for ComfyUI Custom Scripts."""
from __future__ import annotations

import ast
import hashlib
import math
import operator
import random
import re
from typing import Any

import numpy as np
import torch
from PIL import Image

from ._secure_runtime import bind_node, io, materialize, sdk


def _ctx():
    return sdk.ctx()


def _scalar(value: Any, default: Any = None) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else default
    return value if value is not None else default


async def _string_function(
    action: str,
    tidy_tags: str,
    text_a: str = "",
    text_b: str = "",
    text_c: str = "",
):
    tidy = tidy_tags == "yes"
    if action == "append":
        out = (", " if tidy else "").join(
            filter(None, [text_a, text_b, text_c])
        )
    elif action == "replace":
        replacement = "" if text_c is None else text_c
        if text_b.startswith("/") and text_b.endswith("/"):
            out = re.sub(text_b[1:-1], replacement, text_a)
        else:
            out = text_a.replace(text_b, replacement)
    else:
        raise ValueError(f"unknown string action {action!r}")
    if tidy:
        out = re.sub(r"\s{2,}", " ", out)
        out = re.sub(r",{2,}", ",", out.replace(" ,", ",")).strip()
    return {"ui": {"text": [out]}, "result": (out,)}


async def _system_notification(message, any, mode):
    message_value = str(_scalar(message, "Your notification has triggered."))
    mode_value = str(_scalar(mode, "always"))
    return {
        "ui": {"message": message_value, "mode": mode_value},
        "result": (list(any),),
    }


_system_notification.fingerprint_inputs = lambda **_kwargs: float("nan")


async def _play_sound(any, **_kwargs):
    return {"ui": {"a": []}, "result": (list(any),)}


_play_sound.fingerprint_inputs = lambda **_kwargs: float("nan")


async def _show_text(text):
    values = list(text)
    return {"ui": {"text": values}, "result": (values,)}


async def _reroute(value):
    return (value,)


async def _repeat(source, repeats: int, output: str, node_mode: str):
    if output != "single":
        raise ValueError(
            "secure Repeater exposes one honest list output; legacy multi "
            "outputs depended on rewriting the submitted prompt"
        )
    count = int(repeats)
    if not 0 <= count <= 100:
        raise ValueError("secure Repeater supports between 0 and 100 repeats")
    if count == 0:
        return ([],)
    if (
        not isinstance(source, (list, tuple))
        or len(source) != 2
        or not isinstance(source[0], str)
        or not isinstance(source[1], (int, float))
    ):
        raise TypeError("Repeater source must be a directly linked node output")
    if node_mode not in {"reuse", "create"}:
        raise ValueError(f"unknown Repeater node mode {node_mode!r}")

    source_output = int(source[1])
    nodes = []
    links = [list(source)]
    if node_mode == "create":
        for index in range(1, count):
            local_id = f"source_{index}"
            nodes.append({"id": local_id, "clone_input": "source"})
            links.append({"node": local_id, "output": source_output})
    else:
        links *= count

    # CreateList has ten autogrow inputs. A small tree retains the algorithm in
    # this pack while using only the generic core collection primitive.
    level = 0
    while len(links) > 1 or level == 0:
        collected = []
        for start in range(0, len(links), 10):
            group = links[start:start + 10]
            local_id = f"collect_{level}_{start // 10}"
            nodes.append({
                "id": local_id,
                "class_type": "CreateList",
                "inputs": {
                    f"input{index}": link
                    for index, link in enumerate(group)
                },
            })
            collected.append({"node": local_id, "output": 0})
        links = collected
        level += 1
    return await _ctx().graph.expand_nodes(nodes, [links[0]])


async def _load_text(root_dir: str, file: str):
    if file == "[none]" or not str(file).strip():
        raise ValueError("No file")
    ref = await _ctx().assets.resolve(str(root_dir), str(file))
    data = await _ctx().assets.read_bytes(ref)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("selected text file is not UTF-8") from exc
    return (text,)


async def _load_text_fingerprint(root_dir: str, file: str, **_kwargs):
    if file == "[none]" or not str(file).strip():
        return "none"
    ref = await _ctx().assets.resolve(str(root_dir), str(file))
    return hashlib.sha256(await _ctx().assets.read_bytes(ref)).hexdigest()


_load_text.fingerprint_inputs = _load_text_fingerprint


async def _save_text(
    root_dir: str,
    file: str,
    append: str,
    insert: bool,
    text: str,
):
    if root_dir not in {"output", "temp"}:
        raise PermissionError(
            "Save Text cannot modify the input/upload area; choose output or temp"
        )
    mode = "new_only" if append == "new only" else append
    logical = await _ctx().output.write_text(
        str(text),
        filename=str(file),
        folder=root_dir,
        mode=mode,
        insert_newline=bool(insert and mode == "append"),
    )
    ref = await _ctx().assets.resolve(root_dir, logical)
    return ((await _ctx().assets.read_bytes(ref)).decode("utf-8"),)


_save_text.fingerprint_inputs = lambda **_kwargs: float("nan")


async def _checkpoint_loader(ckpt_name: str, prompt: str = ""):
    model, clip, vae = await _ctx().models.load_checkpoint(str(ckpt_name))
    return model, clip, vae, prompt or ""


async def _lora_loader(
    model: sdk.ModelRef,
    clip: sdk.ClipRef,
    lora_name: str,
    strength_model: float,
    strength_clip: float,
    prompt: str = "",
):
    asset = await _ctx().assets.resolve("loras", str(lora_name))
    patched_model, patched_clip = await model.apply_lora(
        asset,
        clip,
        float(strength_model),
        float(strength_clip),
    )
    return patched_model, patched_clip, prompt or ""


def _constrained_size(
    width: int,
    height: int,
    max_width: int,
    max_height: int,
    min_width: int,
    min_height: int,
    crop: bool,
) -> tuple[int, int, tuple[int, int, int, int] | None]:
    if width < 1 or height < 1:
        raise ValueError("images must have positive dimensions")
    max_width = int(max_width)
    max_height = int(max_height)
    min_width = max(0, int(min_width))
    min_height = max(0, int(min_height))
    upper_width = max_width if max_width > 0 else max(width, min_width)
    upper_height = max_height if max_height > 0 else max(height, min_height)

    constrained_width = min(max(width, min_width), upper_width)
    constrained_height = min(max(height, min_height), upper_height)
    aspect_ratio = width / height
    if constrained_width / constrained_height > aspect_ratio:
        constrained_width = max(
            1, max(int(constrained_height * aspect_ratio), min_width)
        )
        if crop:
            constrained_height = max(
                1, int(height / (width / constrained_width))
            )
    else:
        constrained_height = max(
            1, max(int(constrained_width / aspect_ratio), min_height)
        )
        if crop:
            constrained_width = max(
                1, int(width / (height / constrained_height))
            )

    crop_box = None
    if crop and (
        (max_width > 0 and constrained_width > max_width)
        or (max_height > 0 and constrained_height > max_height)
    ):
        target_width = min(constrained_width, upper_width)
        target_height = min(constrained_height, upper_height)
        left = max((constrained_width - target_width) // 2, 0)
        top = max((constrained_height - target_height) // 2, 0)
        crop_box = (left, top, left + target_width, top + target_height)
    return constrained_width, constrained_height, crop_box


def _constrain_batch(
    images: torch.Tensor,
    max_width: int,
    max_height: int,
    min_width: int,
    min_height: int,
    crop_if_required: str,
) -> list[torch.Tensor]:
    if not isinstance(images, torch.Tensor) or images.ndim != 4:
        raise TypeError("images must be a BHWC tensor")
    crop = crop_if_required == "yes"
    results = []
    for image in images:
        array = np.clip(255.0 * image.detach().cpu().numpy(), 0, 255)
        pil = Image.fromarray(array.astype(np.uint8)).convert("RGB")
        width, height, crop_box = _constrained_size(
            pil.width,
            pil.height,
            max_width,
            max_height,
            min_width,
            min_height,
            crop,
        )
        resized = pil.resize((width, height), Image.Resampling.LANCZOS)
        if crop_box is not None:
            resized = resized.crop(crop_box)
        value = np.asarray(resized, dtype=np.float32) / 255.0
        results.append(torch.from_numpy(value.copy()).unsqueeze(0))
    return results


async def _constrain_image(
    images,
    max_width: int,
    max_height: int,
    min_width: int,
    min_height: int,
    crop_if_required: str,
):
    values = _constrain_batch(
        await materialize(images),
        max_width,
        max_height,
        min_width,
        min_height,
        crop_if_required,
    )
    return (values,)


async def _constrain_image_for_video(
    images,
    max_width: int,
    max_height: int,
    min_width: int,
    min_height: int,
    crop_if_required: str,
):
    values = _constrain_batch(
        await materialize(images),
        max_width,
        max_height,
        min_width,
        min_height,
        crop_if_required,
    )
    if not values:
        raise ValueError("images batch cannot be empty")
    shapes = {tuple(value.shape[1:]) for value in values}
    if len(shapes) != 1:
        raise ValueError("video frames must resolve to one common size")
    return (torch.cat(values, dim=0),)


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.BitXor: operator.xor,
    ast.Mod: operator.mod,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.RShift: operator.rshift,
    ast.LShift: operator.lshift,
}
_UNARY = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Invert: operator.invert,
    ast.Not: lambda value: 0 if value else 1,
}
_COMPARE = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
}
_FUNCTIONS = {
    "round": (1, 2, round),
    "ceil": (1, 1, math.ceil),
    "floor": (1, 1, math.floor),
    "min": (2, None, min),
    "max": (2, None, max),
    "randomint": (2, 2, random.randint),
    "randomchoice": (2, None, lambda *values: random.choice(values)),
    "sqrt": (1, 1, math.sqrt),
    "int": (1, 1, int),
    "iif": (3, 3, lambda condition, yes, no: yes if condition else no),
}


async def _spatial_property(value: Any, name: str) -> int:
    if isinstance(value, sdk.ImageRef):
        height, width = await value.spatial_shape()
    elif isinstance(value, sdk.LatentRef):
        latent_height, latent_width = await value.spatial_shape()
        height, width = latent_height * 8, latent_width * 8
    else:
        raise TypeError("width and height require an IMAGE or LATENT input")
    return width if name == "width" else height


def _bounded_number(value: Any) -> int | float:
    if isinstance(value, bool):
        return int(value)
    if not isinstance(value, (int, float)):
        raise TypeError(f"math expression produced {type(value).__name__}, not a number")
    if isinstance(value, int) and value.bit_length() > 1_000_000:
        raise OverflowError("math expression integer is too large")
    if isinstance(value, float) and not math.isfinite(value):
        raise OverflowError("math expression result must be finite")
    return value


async def _math_expression(
    expression: str,
    a: Any = None,
    b: Any = None,
    c: Any = None,
):
    expression = str(expression).replace("\n", " ").replace("\r", "")
    if len(expression) > 8192:
        raise ValueError("math expression exceeds 8192 characters")
    parsed = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(parsed)) > 512:
        raise ValueError("math expression is too complex")
    lookup = {"a": a, "b": b, "c": c}

    async def evaluate(node: ast.AST):
        if isinstance(node, ast.Constant):
            return _bounded_number(node.value)
        if isinstance(node, ast.BinOp):
            left = _bounded_number(await evaluate(node.left))
            right = _bounded_number(await evaluate(node.right))
            operation = _BINARY.get(type(node.op))
            if operation is None:
                raise TypeError(f"operator {type(node.op).__name__} is not supported")
            if isinstance(node.op, ast.Pow) and abs(right) > 10_000:
                raise OverflowError("math expression exponent is too large")
            return _bounded_number(operation(left, right))
        if isinstance(node, ast.BoolOp):
            values = [await evaluate(item) for item in node.values]
            if isinstance(node.op, ast.And):
                return int(all(values))
            if isinstance(node.op, ast.Or):
                return int(any(values))
            raise TypeError(f"boolean operator {type(node.op).__name__} is not supported")
        if isinstance(node, ast.UnaryOp):
            operation = _UNARY.get(type(node.op))
            if operation is None:
                raise TypeError(f"operator {type(node.op).__name__} is not supported")
            return _bounded_number(operation(await evaluate(node.operand)))
        if isinstance(node, ast.Name):
            if node.id not in lookup:
                raise NameError(f"Name not found: {node.id}")
            return _bounded_number(lookup[node.id])
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            owner = node.value.id
            if owner in lookup and node.attr in {"width", "height"}:
                return await _spatial_property(lookup[owner], node.attr)
            values = await _ctx().graph.widget_values(node_name=owner)
            if node.attr not in values:
                raise NameError(f"Widget not found: {owner}.{node.attr}")
            value = values[node.attr]
            if isinstance(value, (list, tuple)):
                raise ValueError(
                    "converted widgets are not available by name; connect the value instead"
                )
            return _bounded_number(value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            definition = _FUNCTIONS.get(node.func.id)
            if definition is None:
                raise NameError(f"Invalid function call: {node.func.id}")
            minimum, maximum, function = definition
            if len(node.args) < minimum or (
                maximum is not None and len(node.args) > maximum
            ):
                raise SyntaxError(f"invalid argument count for {node.func.id}")
            return _bounded_number(
                function(*[await evaluate(value) for value in node.args])
            )
        if isinstance(node, ast.Compare):
            left = await evaluate(node.left)
            for operation_node, comparator in zip(
                node.ops, node.comparators, strict=True
            ):
                right = await evaluate(comparator)
                comparison = _COMPARE.get(type(operation_node))
                if comparison is None:
                    raise TypeError(
                        f"comparison {type(operation_node).__name__} is not supported"
                    )
                if not comparison(left, right):
                    return 0
                left = right
            return 1
        raise TypeError(f"expression element {type(node).__name__} is not supported")

    result = _bounded_number(await evaluate(parsed.body))
    return {"ui": {"value": [result]}, "result": (int(result), float(result))}


def _math_fingerprint(expression: str, **_kwargs):
    return float("nan") if "random" in str(expression) else str(expression)


_math_expression.fingerprint_inputs = _math_fingerprint


NODE_CLASS_MAPPINGS = {
    "CheckpointLoader|pysssss": bind_node(
        "CheckpointLoader|pysssss", _checkpoint_loader, permissions=("models",)
    ),
    "ConstrainImageforVideo|pysssss": bind_node(
        "ConstrainImageforVideo|pysssss", _constrain_image_for_video,
        permissions=("raw",),
    ),
    "ConstrainImage|pysssss": bind_node(
        "ConstrainImage|pysssss", _constrain_image, permissions=("raw",)
    ),
    "LoadText|pysssss": bind_node(
        "LoadText|pysssss", _load_text, permissions=("assets",)
    ),
    "LoraLoader|pysssss": bind_node(
        "LoraLoader|pysssss", _lora_loader, permissions=("assets",)
    ),
    "MathExpression|pysssss": bind_node(
        "MathExpression|pysssss", _math_expression, permissions=("graph",)
    ),
    "PlaySound|pysssss": bind_node("PlaySound|pysssss", _play_sound),
    "Repeater|pysssss": bind_node(
        "Repeater|pysssss", _repeat, permissions=("graph.expand",)
    ),
    "ReroutePrimitive|pysssss": bind_node(
        "ReroutePrimitive|pysssss", _reroute
    ),
    "SaveText|pysssss": bind_node(
        "SaveText|pysssss", _save_text, permissions=("assets", "output")
    ),
    "ShowText|pysssss": bind_node("ShowText|pysssss", _show_text),
    "StringFunction|pysssss": bind_node(
        "StringFunction|pysssss", _string_function
    ),
    "SystemNotification|pysssss": bind_node(
        "SystemNotification|pysssss", _system_notification
    ),
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: cls.GET_SCHEMA().display_name
    for node_id, cls in NODE_CLASS_MAPPINGS.items()
}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
