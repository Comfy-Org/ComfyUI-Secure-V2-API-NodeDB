"""Finite source/V2 differentials. Run only through the lane gate.

The original source modules mix pure nodes with server-route decorators and
host-only imports. This test executes the unchanged original class/function AST
for the selected pure paths, without the unrelated import-time server code.
The converted side uses the real SDK resolver, context, operations and refs.
No host module is stubbed. Fixtures are generated, and every tensor comparison
checks dtype, shape and exact bytes. Guest smoke is a separate script.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import dataclasses
import datetime
import importlib.util
import inspect
import itertools
import json
import math
import os
import random
import re
import shutil
import signal
import sys
import traceback
import types
from pathlib import Path
from typing import Literal, Optional

sys.path[:0] = ["/core", "/overlay", "/tests"]
from comfy.cli_args import args
args.cpu = True

import numpy as np
import torch
import yaml
from PIL import Image
from comfy_api.latest import io, _sdk
from comfy_api.latest._execution_metadata import ExecutionMetadataScope
from comfy_execution.graph import DynamicPrompt
from comfy_secure_nodes import packmanifest, packruntime

PACK = Path("/pack")
V2 = PACK / "v2"
RESULTS = Path("/results")
SEED = 78901234
NOW = datetime.datetime(2026, 1, 2, 3, 4, 5)
PROMPT = {
    "17": {"inputs": {"seed": 81, "text": "linked"}, "_meta": {"title": "Source"}},
    "24": {"inputs": {"value": "unicode \u2603"}, "_meta": {"title": "Text"}},
}
REPORT = {"environment": "gate, B13 sources 38f28c98; core 6257422b; engine SDK 038019fa",
          "comparison": "source AST / V2 with real in-process refs; guest smoke reported separately",
          "nodes": {}, "checks": [], "negative_control_red": False}
BACKEND_IDS = {
    "D2 Refiner Steps", "D2 Refiner Steps A1111", "D2 Refiner Steps Tester",
    "D2 Image Resize", "D2 Resize Calculator", "D2 Get Image Size", "D2 Size Selector",
    "D2 Regex Switcher", "D2 Regex Replace", "D2 Multi Output", "D2 List To String",
    "D2 Text Concat", "D2 Filename Template", "D2 Filename Template2", "D2 Prompt",
    "D2 Prompt Sanitizer", "D2 Convert NAI Prompt", "D2 XY Model List",
    "D2 XY Prompt SR", "D2 XY Prompt SR2", "D2 XY List To Plot",
    "D2 XY String To Plot", "D2 XY Seed", "D2 XY Seed2",
}
RNG_REFUSAL_XY = (
    'd2-nodes-comfyui/D2 XY Seed: seeds containing int(-1) require the source '
    'host-global Python RNG; this branch is not yet converted to Secure Nodes V2')
RNG_REFUSAL_INITIAL = (
    'd2-nodes-comfyui/D2 XY Seed2: initial_number int(-1) requires the source '
    'host-global Python RNG; this branch is not yet converted to Secure Nodes V2')
RNG_REFUSAL_RANDOMIZE = (
    "d2-nodes-comfyui/D2 XY Seed2: mode='randomize' with count > 0 requires the "
    'source host-global Python RNG; this branch is not yet converted to Secure Nodes V2')


class FrozenDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.replace(tzinfo=tz)


class VAE:
    """Recording CPU stand-in for the generic engine-owned VAE boundary."""
    def __init__(self, expected_pixel_stride=None):
        self.calls = []
        self.expected_pixel_stride = expected_pixel_stride

    def encode(self, pixels):
        if self.expected_pixel_stride is not None:
            assert pixels.stride(-2) == self.expected_pixel_stride, pixels.stride()
        self.calls.append(("encode", tuple(pixels.stride()), pixels.clone()))
        return pixels[:, ::2, ::2, :3].movedim(-1, 1).contiguous()

    def encode_tiled(self, pixels, **kwargs):
        assert kwargs == {"tile_x": 512, "tile_y": 512, "overlap": 64,
                          "tile_t": 64, "overlap_t": 8}, kwargs
        if self.expected_pixel_stride is not None:
            assert pixels.stride(-2) == self.expected_pixel_stride, pixels.stride()
        self.calls.append(("encode_tiled", tuple(pixels.stride()), pixels.clone(), dict(kwargs)))
        return pixels[:, ::2, ::2, :3].movedim(-1, 1).contiguous() + 0.125

    def decode(self, samples):
        raise AssertionError("this test does not decode")


def source_ast(rel):
    return ast.parse((PACK / rel).read_text())


def original_module(name, rel, chosen, namespace):
    """Execute exact source AST nodes, retaining their original file/line info."""
    module = types.ModuleType(name)
    module.__file__ = str(PACK / rel)
    module.__dict__.update(namespace)
    sys.modules[name] = module
    selected = []
    for node in source_ast(rel).body:
        key = node.name if isinstance(node, (ast.ClassDef, ast.FunctionDef)) else (
            node.targets[0].id if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name) else None)
        if key in chosen:
            selected.append(node)
    assert {getattr(x, "name", None) or x.targets[0].id for x in selected} == set(chosen)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PACK / rel), "exec",
                 flags=__import__("__future__").annotations.compiler_flag), module.__dict__)
    return module


def load_v2():
    name = "d2_recovery_v2"
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source_classes(converted):
    util_names = {
        "MAX_RESOLUTION", "MAX_SEED", "LINE_BREAK", "SEPARATOR", "SEPARATOR_CHARS",
        "COMMENT_TYPES", "COMMENT_TYPE_ALL", "COMMENT_TYPE_NONE", "create_seed",
        "get_separator_str", "list_to_text", "delete_comment",
    }
    namespace = {"re": re, "random": random, "Path": Path, "Literal": Literal}
    util = original_module("_d2_original_util", "nodes/modules/util.py", util_names, namespace)
    # Original config loader works in a temporary copy, as it creates a local
    # config from the shipped sample on first use. Its functions stay unchanged.
    cfg = Path("/tmp/d2-original-config")
    cfg.mkdir(exist_ok=True)
    shutil.copytree(PACK / "config", cfg / "config", dirs_exist_ok=True)
    cfg_util = original_module(
        "_d2_original_config", "nodes/modules/util.py",
        {"load_config", "get_root_path", "get_config_path"},
        {"os": os, "shutil": shutil, "yaml": yaml, "Path": Path})
    cfg_util.__file__ = str(cfg / "nodes/modules/util.py")
    template_names = {x.name for x in source_ast("nodes/modules/template_util.py").body
                      if isinstance(x, ast.FunctionDef)}
    template = original_module(
        "_d2_original_template", "nodes/modules/template_util.py", template_names,
        {"re": re, "datetime": FrozenDateTime, "util": cfg_util})
    image = original_module(
        "_d2_original_image", "nodes/modules/image_util.py",
        {"tensor2pil", "pil2tensor"}, {"torch": torch, "np": np, "Image": Image})
    size = original_module(
        "_d2_original_size", "nodes/modules/size_util.py",
        {"D2_TResizeMethod", "RESAMPLE_FILTERS", "get_size_preset", "number_adjust",
         "rescale_calc", "get_new_size", "apply_resize_image", "apply_resize_mask"},
        {"math": math, "Literal": Literal, "Image": Image, "util": cfg_util, "image_util": image})
    size.SIZE_LIST, size.SIZE_DICT = size.get_size_preset()
    text_names = {x.name for x in source_ast("nodes/modules/text_util.py").body
                  if isinstance(x, ast.FunctionDef)}
    text = original_module(
        "_d2_original_text", "nodes/modules/text_util.py", text_names, {"re": re})
    nai_names = set()
    for x in source_ast("nodes/modules/nai_prompt_util.py").body:
        if isinstance(x, ast.FunctionDef):
            nai_names.add(x.name)
        elif isinstance(x, ast.Assign) and isinstance(x.targets[0], ast.Name):
            nai_names.add(x.targets[0].id)
    nai = original_module("_d2_original_nai", "nodes/modules/nai_prompt_util.py",
                          nai_names, {"re": re, "math": math})
    common = {"io": io, "torch": torch, "math": math, "re": re, "util": util,
              "size_util": size, "image_util": image, "text_util": text,
              "nai_prompt_util": nai, "delete_comment": util.delete_comment,
              "replace_template": template.replace_template}
    by_module = {}
    for node_id, cls in converted.NODE_CLASS_MAPPINGS.items():
        if node_id in BACKEND_IDS:
            by_module.setdefault(cls.__module__.split(".")[-1], set()).add(cls.__name__)
    result = {}
    for mod, classes in by_module.items():
        loaded = original_module("_d2_original_" + mod, "nodes/" + mod + ".py", classes, common)
        for node_id, cls in converted.NODE_CLASS_MAPPINGS.items():
            if cls.__name__ in classes:
                result[node_id] = getattr(loaded, cls.__name__)
    return result


def tensor(shape=(1, 9, 11, 3), dtype=torch.float32):
    generator = torch.Generator().manual_seed(SEED)
    return torch.rand(shape, generator=generator, dtype=torch.float64).to(dtype)


def defaults(cls):
    result = {}
    for field in cls.define_schema().inputs:
        if getattr(field, "optional", False):
            continue
        kind = field.io_type
        value = getattr(field, "default", None)
        if value is None:
            options = getattr(field, "options", None)
            if options:
                value = options[0]
            elif kind == "IMAGE":
                value = tensor()
            elif kind == "LIST":
                value = ["one", "two"]
            else:
                value = {"INT": 0, "FLOAT": 0.0, "BOOLEAN": False, "STRING": ""}.get(kind)
        result[field.id] = value
    return result


def cases(classes):
    rows = {node_id: [("defaults", defaults(cls))] for node_id, cls in classes.items()
            if node_id in BACKEND_IDS}
    def add(node, name, **overrides):
        rows[node].append((name, defaults(classes[node]) | overrides))
    # Every static COMBO option is exercised, with finite small fixtures.
    for node_id in rows:
        for field in classes[node_id].define_schema().inputs:
            if field.io_type != "COMBO":
                continue
            for i, option in enumerate(getattr(field, "options", None) or []):
                add(node_id, f"option:{field.id}:{i}", **{field.id: option})
    for method in ["Floor", "Round", "Ceil", "None"]:
        for scale in [0.1, 1.0, 16.0]:
            add("D2 Resize Calculator", f"round-edge:{method}:{scale}", width=65, height=79,
                rescale_factor=scale, round_method=method)
    for width, height in [(64, 64), (8192, 64), (64, 8192), (0, 1)]:
        add("D2 Resize Calculator", f"dimensions:{width}:{height}", width=width, height=height)
    add("D2 Resize Calculator", "invalid-method", round_method="invalid")
    for width, height in [(64, 64), (8192, 64), (64, 8192)]:
        add("D2 Size Selector", f"dimensions:{width}:{height}", width=width, height=height)
    for b in [1, 2, 64]:
        add("D2 Size Selector", f"batch:{b}", width=64, height=64, batch_size=b)
    for scale in [0.1, 16.0]:
        add("D2 Size Selector", f"prescale:{scale}", width=64, height=64,
            prescale_factor=scale, round_method="None")
    add("D2 Size Selector", "swap", width=64, height=80, swap_dimensions=True)
    add("D2 Size Selector", "invalid-preset", preset="absent")
    for dtype in [torch.float16, torch.float32, torch.float64]:
        add("D2 Size Selector", f"image:{dtype}", images=tensor(dtype=dtype))
        for shape in [(1, 9, 11, 3), (2, 8, 10, 4), (1, 1, 8, 3)]:
            add("D2 Get Image Size", f"shape:{shape}:{dtype}", images=tensor(shape, dtype))
        add("D2 Image Resize", f"image:{dtype}", image=tensor(dtype=dtype), round_method="None")
    add("D2 Get Image Size", "display-ignored", display="ignored")
    for mask in [tensor((9, 11)), tensor((1, 9, 11)), tensor((2, 9, 11))]:
        add("D2 Image Resize", f"mask:{tuple(mask.shape)}", mask=mask, round_method="None")
    add("D2 Image Resize", "rgba-batch", image=tensor((2, 9, 11, 4)), round_method="None")
    add("D2 Image Resize", "vae-normal", image=tensor((2, 9, 11, 4)),
        round_method="None", vae=VAE(expected_pixel_stride=4), use_tiled_vae=False)
    add("D2 Image Resize", "vae-tiled", image=tensor((2, 9, 11, 4)),
        round_method="None", vae=VAE(expected_pixel_stride=4), use_tiled_vae=True)
    add("D2 Image Resize", "width-max", mode="resize", resize_width=48000, resize_height=1,
        round_method="None")
    add("D2 Image Resize", "height-max", mode="resize", resize_width=1, resize_height=48000,
        round_method="None")
    add("D2 Image Resize", "invalid-round", round_method="invalid")
    add("D2 Image Resize", "invalid-resampling", resampling="invalid")
    # Text paths: defaults, exact failures, unicode, ordering and every option.
    add("D2 Regex Switcher", "match", text="PONY", prefix="A", suffix="B")
    add("D2 Regex Switcher", "none-prefix", text="unmatched", prefix=None, suffix=None)
    add("D2 Regex Switcher", "invalid-regex", text="x", regex_and_output="[--bad")
    for mode in ["Tag", "Advanced"]:
        add("D2 Regex Replace", "replace:" + mode, text="one, two\none", mode=mode,
            regex_replace="one\n--\nTHREE")
        add("D2 Regex Replace", "invalid-regex:" + mode, text="x", mode=mode,
            regex_replace="[\n--\nreplacement")
    for kind, value in [("INT", "1\n-2\n18446744073709551615"), ("SEED", "-1\n0\n42"),
                        ("FLOAT", "-0.0\n1.25\n-3.5"), ("STRING", "one\n\u2603")]:
        add("D2 Multi Output", "typed:" + kind, type=kind, parameter=value)
        if kind != "STRING":
            add("D2 Multi Output", "bad:" + kind, type=kind, parameter="not-a-number")
    for mode in ["# + // + /**/", "# only", "// only", "/* */ only", "None"]:
        add("D2 Prompt", "comment:" + mode, prompt="#a\n//b\nc /* block\nline */ d",
            comment_type=mode, insert_lora="CHOOSE", token_count=True)
    for values in [[], [""], ["a", "", "b"], ["\u2603", "a\nb"], ("a", "b")]:
        add("D2 List To String", "list:" + repr(values), LIST=values)
        add("D2 XY List To Plot", "list:" + repr(values), LIST=values)
    add("D2 List To String", "native-list-error", LIST=[1, 2])
    add("D2 XY List To Plot", "native-list-error", LIST=[1, 2])
    for skip in [False, True]:
        add("D2 Text Concat", f"whitespace:{skip}", text_count=4, skip_empty=skip,
            text_1="  a  ", text_2="", text_3=" \n", text_4="\u2603\nx")
    for count in [1, 50]:
        add("D2 Text Concat", f"count:{count}", text_count=count,
            **{f"text_{i}": str(i) for i in range(1, count + 1)})
        add("D2 XY String To Plot", f"count:{count}", string_count=count,
            **{f"string_{i}": str(i) + "\n" for i in range(1, count + 1)})
    formats = ["%arg_1%", "%arg_1:ckpt_name%", "%exec_1[0]%", "%exec_1['key']%",
               "%exec_1.missing%", "%node:17.seed%", "%Source.seed%", "%Text.value%",
               "%date:yyyy/MM/dd-hhmmss%", "bad:<name>|?*"]
    for node in ["D2 Filename Template", "D2 Filename Template2"]:
        for i, fmt in enumerate(formats):
            for norm in [False, True]:
                add(node, f"format:{i}:{norm}", format=fmt, arg_count=3, normalization=norm,
                    arg_1={"key": "\u2603", "other": 2})
        add(node, "args-50-order", format="/".join(f"%arg_{i}%" for i in range(1, 51)),
            arg_count=50, **{f"arg_{i}": str(i) for i in range(1, 51)})
        add(node, "ckpt-name", format="%arg_1:ckpt_name%", arg_1="test.safetensors")
        add(node, "list-index", format="%exec_1[0]%", arg_1=["first", "last"])
        add(node, "missing-node-native-error", format="%node:999.missing%")
        add(node, "snapshot-preset", format="%arg_1:preset.a1111%", arg_1={"positive": "p"})
    prompt = "score_9, a_b,, <lora:a_b:1>\r\n#a comment\nA_B, a_b, (cat:1.25), "
    for newline in ["keep", "add_comma", "to_comma", "to_space", "remove"]:
        for comment in ["# + // + /**/", "# only", "// only", "/* */ only", "None"]:
            add("D2 Prompt Sanitizer", f"sanitizer:{newline}:{comment}", prompt=prompt,
                newline_mode=newline, comment_type=comment, remove_duplicate_tags=True)
    for flag in ["underscore_to_space", "space_after_comma", "remove_extra_comma",
                 "protect_lora", "protect_score", "remove_duplicate_tags", "strip_trailing_comma"]:
        for value in [False, True]:
            add("D2 Prompt Sanitizer", f"bool:{flag}:{value}", prompt=prompt, **{flag: value})
    for direction, mode, remove in itertools.product(["sd_to_nai", "nai_to_sd"],
                                                     ["number", "brace"], [False, True]):
        for text in ["(cat:1.25), (dog:-0.5)\n\u2603", "1.2::cat ::, -1::dog ::", "{{cat}} [dog]"]:
            add("D2 Convert NAI Prompt", f"nai:{direction}:{mode}:{remove}:{text}", prompt=text,
                convert=direction, mode=mode, remove_negative=remove)
    for text in ["", "\n", "a\nb", "a\nb\n", "\u2603, x"]:
        add("D2 XY Model List", "model-list:" + repr(text), model_list=text)
    for prompt, search, replace in [("", "", ""), ("a\nb", "a", "x\ny"),
                                    ("aaaa", "aa", "b\nc"), ("\u2603", "\u2603", "X")]:
        add("D2 XY Prompt SR", "replace:" + repr((prompt, search, replace)),
            prompt=prompt, search=search, replace=replace)
        add("D2 XY Prompt SR2", "replace:" + repr((prompt, search, replace)),
            prompt=prompt, search=search, x_y=replace)
    for text in ["0\n1\n18446744073709551615", "-1\n-1", " 42 \n7", "", "bad"]:
        add("D2 XY Seed", "seeds:" + repr(text), seeds=text)
    for initial, count, mode in itertools.product([-1, 0, 2**64 - 1], [0, 1, 4],
                                                 ["fixed", "increment", "decrement", "randomize"]):
        add("D2 XY Seed2", f"seed2:{initial}:{count}:{mode}",
            initial_number=initial, count=count, mode=mode)
    add("D2 XY String To Plot", "missing", string_count=3, string_2=None)
    add("D2 XY String To Plot", "newlines", string_count=3,
        string_1="a\nb", string_2="\u2603", string_3="c")
    for values in [(0, 0, 0), (25, 0, 5), (1, 1, 0), (10000, 3, 9999)]:
        add("D2 Refiner Steps", "steps:" + repr(values),
            steps=values[0], start=values[1], end=values[2])
    for steps, denoise, switch in [(0, 1, 0), (25, 0, 0.2), (25, 1, 0), (25, 1, 1),
                                   (17, 0.37, 0.63), (10000, 1, 1)]:
        add("D2 Refiner Steps A1111", f"refiner:{steps}:{denoise}:{switch}",
            steps=steps, denoise=denoise, switch_at=switch)
    add("D2 Refiner Steps Tester", "all-inputs", steps=25, start=3, end=9,
        refiner_start=10, text="ignored")
    # A few deterministic random values exercise arithmetic and text parsing.
    rng = random.Random(SEED)
    for i in range(8):
        add("D2 Resize Calculator", f"random:{i}", width=rng.randrange(64, 512),
            height=rng.randrange(64, 512), rescale_factor=rng.uniform(0.1, 3.0),
            round_method=rng.choice(["Floor", "Round", "Ceil", "None"]))
    return rows


def equal(a, b, path="output"):
    assert type(a) is type(b), f"{path}: {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, torch.Tensor):
        assert a.dtype == b.dtype and a.shape == b.shape, f"{path}: tensor metadata"
        assert torch.equal(a.contiguous().reshape(-1).view(torch.uint8),
                           b.contiguous().reshape(-1).view(torch.uint8)), f"{path}: tensor bits"
    elif isinstance(a, float):
        assert math.isfinite(a) and math.isfinite(b), f"{path}: finite fixture required"
        assert a.hex() == b.hex(), f"{path}: float bits {a.hex()} != {b.hex()}"
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b), f"{path}: length"
        for i, (x, y) in enumerate(zip(a, b)):
            equal(x, y, f"{path}[{i}]")
    elif isinstance(a, dict):
        assert list(a) == list(b), f"{path}: keys/order"
        for k in a:
            equal(a[k], b[k], f"{path}[{k!r}]")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def outcome(result=None, error=None):
    if error is not None:
        return ("error", type(error).__name__, str(error))
    return ("value", result.result, result.ui, result.expand, result.block_execution)


async def converted_call(cls, node_id, inputs):
    refs = _sdk.InProcessRefResolver()
    plan = _sdk.ExecutionPlan("d2-source-parity", "17", node_id,
                              permissions=tuple(getattr(cls, "SDK_PERMISSIONS", ())),
                              prompt=PROMPT)
    plan.execution_metadata = ExecutionMetadataScope(
        plan.prompt_id, DynamicPrompt(copy.deepcopy(PROMPT)), {})
    cls.hidden = types.SimpleNamespace(prompt=PROMPT, extra_pnginfo={}, unique_id="17")
    with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()):
        wrapped = await _sdk.wrap_inputs(refs, inputs)
        result = cls.execute(**wrapped)
        if inspect.isawaitable(result):
            result = await result
        return await _sdk.unwrap_outputs(refs, result)


def source_call(cls, inputs):
    cls.hidden = types.SimpleNamespace(prompt=PROMPT, extra_pnginfo={}, unique_id="17")
    return cls.execute(**inputs)


def encode(module):
    rows = {}
    for node_id, cls in module.NODE_CLASS_MAPPINGS.items():
        schema = cls.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        methods = {key: key in cls.__dict__
                   for key in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")}
        row = {
            "module": cls.__module__.removeprefix(module.__name__ + "."),
            "class": cls.__name__, "sdk_refs": bool(cls.SDK_REFS),
            "permissions": list(getattr(cls, "SDK_PERMISSIONS", ())),
            "methods": methods,
            "schema": packmanifest.encode_schema(copy.deepcopy(schema)),
        }
        if methods["validate_inputs"]:
            row["validation_inputs"] = packmanifest.encode_validation_inputs(cls)
        rows[node_id] = row
    manifest = {"format": packmanifest.FORMAT, "runtime": packruntime.manifest_declaration(V2),
                "nodes": rows, "web_directory": None, "frontend_permissions": []}
    data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    (RESULTS / "secure-nodes.json").write_bytes(data)
    return data


async def main():
    RESULTS.mkdir(exist_ok=True)
    from guest_import_guard import install as install_import_seal
    os.environ.setdefault("TMPDIR", "/tmp")
    install_import_seal()
    new = load_v2()
    encode(new)
    old = source_classes(new)
    # Freeze the time source on both sides; no production behavior is changed.
    sys.modules[new.__name__ + ".nodes.modules.template_util"].datetime = FrozenDateTime
    rows = cases(new.NODE_CLASS_MAPPINGS)
    count = sum(len(values) for values in rows.values())
    assert count == 403, "all R1 finite inputs must remain present"
    print(f"PLAN: {len(rows)} backend nodes, {count} retained cases "
          "(380 differential + 23 named RNG refusals), "
          f"{len(new.NODE_CLASS_MAPPINGS) - len(rows)} named refusal checks", flush=True)
    if "--negative-control" in sys.argv:
        expected = source_call(old["D2 Multi Output"], {"type": "STRING", "parameter": "a\nb"})
        actual = await converted_call(new.NODE_CLASS_MAPPINGS["D2 Multi Output"], "D2 Multi Output",
                                      {"type": "STRING", "parameter": "a\nb"})
        actual.result[0][0] = "perturbed"
        equal(outcome(expected), outcome(actual))
        raise AssertionError("negative control did not turn red")
    failures = 0
    rng_refusals = 0
    for node_id, node_cases in rows.items():
        record = {"verdict": "EXACT", "case_count": len(node_cases), "cases": []}
        for name, inputs in node_cases:
            random.seed(SEED)
            source_rng_before = random.getstate()
            try:
                expected = outcome(source_call(old[node_id], copy.deepcopy(inputs)))
            except Exception as error:
                expected = outcome(error=error)
            source_rng_changed = random.getstate() != source_rng_before
            random.seed(SEED)
            converted_rng_before = random.getstate()
            validation = None
            validation_rng_unchanged = None
            if source_rng_changed:
                assert node_id in {"D2 XY Seed", "D2 XY Seed2"}
                validation = new.NODE_CLASS_MAPPINGS[node_id].validate_inputs(**copy.deepcopy(inputs))
                validation_rng_unchanged = random.getstate() == converted_rng_before
            try:
                actual = outcome(await converted_call(new.NODE_CLASS_MAPPINGS[node_id], node_id,
                                                      copy.deepcopy(inputs)))
            except Exception as error:
                actual = outcome(error=error)
            try:
                if source_rng_changed:
                    message = RNG_REFUSAL_XY if node_id == "D2 XY Seed" else (
                        RNG_REFUSAL_INITIAL if int(inputs["initial_number"]) == -1
                        else RNG_REFUSAL_RANDOMIZE)
                    assert validation == message, (validation, message)
                    assert validation_rng_unchanged, "validation consumed Python RNG"
                    assert random.getstate() == converted_rng_before, "execution consumed Python RNG"
                    equal(("error", "SecureConversionRefusal", message), actual)
                    assert expected[0] == "value", "retain original RNG evidence"
                    rng_refusals += 1
                    record["verdict"] = "PARTIAL"
                    entry = {"name": name, "verdict": "NAMED-RNG-REFUSAL",
                             "original_outcome": expected[0], "source_rng_changed": True,
                             "validation_rng_unchanged": True, "execution_rng_unchanged": True,
                             "message": message}
                else:
                    equal(expected, actual)
                    entry = {"name": name, "verdict": "EXACT", "outcome": expected[0]}
            except Exception as error:
                failures += 1
                record["verdict"] = "MISMATCH"
                entry = {"name": name, "verdict": "MISMATCH", "detail": str(error),
                         "original": repr(expected)[:1200], "converted": repr(actual)[:1200]}
                print(f"FAIL {node_id}/{name}: {error}", flush=True)
            record["cases"].append(entry)
        REPORT["nodes"][node_id] = record
        print(f"{record['verdict']} {node_id}: {len(node_cases)} cases", flush=True)
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        if node_id in rows:
            continue
        message = f"d2-nodes-comfyui/{node_id} is not yet converted to Secure Nodes V2"
        assert cls.validate_inputs() == message
        try:
            await cls.execute()
        except RuntimeError as error:
            assert type(error).__name__ == "SecureConversionRefusal"
            assert str(error).startswith(message + ": ")
        else:
            raise AssertionError(f"{node_id}: missing execute refusal")
        REPORT["nodes"][node_id] = {"verdict": "REFUSED-AS-DESIGNED", "case_count": 1}
    # Intentional output corruption must fail the same comparator.
    try:
        equal(("value", ["expected"]), ("value", ["perturbed"]))
    except AssertionError:
        REPORT["negative_control_red"] = True
    assert REPORT["negative_control_red"]
    assert rng_refusals == 23
    REPORT["retained_case_count"] = count
    REPORT["differential_case_count"] = count - rng_refusals
    REPORT["rng_refusal_case_count"] = rng_refusals
    REPORT["refusal_case_count"] = len(new.NODE_CLASS_MAPPINGS) - len(rows)
    REPORT["failure_count"] = failures
    (RESULTS / "parity.json").write_text(json.dumps(REPORT, indent=2, sort_keys=True) + "\n")
    assert failures == 0, f"{failures} differential failures"
    print(f"DONE: {count-rng_refusals} EXACT differential cases, {rng_refusals} named RNG refusals, "
          f"{REPORT['refusal_case_count']} whole-node refusals; "
          "negative control detected", flush=True)


if __name__ == "__main__":
    def timed_out(signum, frame):
        raise TimeoutError("finite gate budget exceeded: 240 seconds")
    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(240)
    try:
        asyncio.run(main())
    except BaseException as error:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "failure.json").write_text(json.dumps({
            "error_type": type(error).__name__, "message": str(error),
            "traceback": traceback.format_exc(),
            "partial_report": REPORT,
            "negative_control_requested": "--negative-control" in sys.argv,
        }, indent=2, sort_keys=True) + "\n")
        raise
    finally:
        signal.alarm(0)
