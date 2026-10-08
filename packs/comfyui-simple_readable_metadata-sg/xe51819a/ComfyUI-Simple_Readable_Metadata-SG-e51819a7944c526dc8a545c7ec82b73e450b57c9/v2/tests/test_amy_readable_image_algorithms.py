"""Exact pinned source algorithms; no node/guest/whole-pack certification."""
import ast
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from PIL import Image, ImageOps, PngImagePlugin

V2 = Path(os.environ.get("AMY_READABLE_V2", Path(__file__).resolve().parent.parent)).resolve()
assert (V2 / "image_algorithms.py").is_file()
SOURCE = V2.parent


def load(name):
    spec = importlib.util.spec_from_file_location("amy_" + name, V2 / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


names = load("sampling_names")
limits = load("limits")
ImageAlgorithms = load("image_algorithms").ImageAlgorithms
MaxAlgorithms = load("max_algorithms").MaxAlgorithms


def pristine(filename, fixture):
    tree = ast.parse((SOURCE / filename).read_bytes())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name not in ("INPUT_TYPES", "IS_CHANGED", "VALIDATE_INPUTS", "__init__")]
    ns = {"torch": torch, "os": os, "Image": Image, "ImageOps": ImageOps, "np": np,
          "json": json, "re": re,
          "folder_paths": SimpleNamespace(get_annotated_filepath=lambda name: str(fixture / name)),
          "comfy": SimpleNamespace(samplers=SimpleNamespace(KSampler=SimpleNamespace(
              SAMPLERS=names.SAMPLERS, SCHEDULERS=names.SCHEDULERS)))}
    # TEST-ONLY source class functions: actual unmodified source algorithm AST.
    # File/enum globals are controlled fixtures, not a converted compatibility shim.
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(SOURCE / filename), "exec"), ns)
    return ns[cls.name]()


def same(left, right):
    assert type(left) is type(right)
    if isinstance(left, torch.Tensor):
        assert left.dtype == right.dtype and left.shape == right.shape
        assert torch.equal(left, right)
    elif isinstance(left, dict):
        assert list(left) == list(right)
        for key in left:
            same(left[key], right[key])
    elif isinstance(left, (list, tuple)):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            same(a, b)
    else:
        assert left == right


PROMPT = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "cat\nbright"}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "dog"}},
    "4": {"class_type": "KSampler", "inputs": {"positive": ["2", 0], "negative": ["3", 0],
          "seed": 123, "steps": 20, "cfg": 7.5, "sampler_name": "euler", "scheduler": "normal"}},
}
DATA = {
    "none": {},
    "a1111": {"parameters": "cat\nNegative prompt: dog\nSteps: 20, Sampler: Euler, CFG scale: 7, Seed: 42, Size: 6x4, Model: abc"},
    "comfy": {"prompt": json.dumps(PROMPT), "workflow": json.dumps({"nodes": []})},
    "invalid": {"prompt": "not JSON", "parameters": "cat"},
}


@pytest.mark.parametrize("family", ["sg", "max"])
@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "I"])
@pytest.mark.parametrize("metadata", list(DATA))
@pytest.mark.parametrize("emoji", [False, True])
def test_exact_pixels_metadata_types(tmp_path, family, mode, metadata, emoji):
    array = (np.arange(24, dtype=np.uint16).reshape(4, 6) * 7).astype(np.uint8)
    if mode in ("RGB", "RGBA"):
        array = np.repeat(array[:, :, None], 4 if mode == "RGBA" else 3, axis=2)
    if mode == "I":
        array = array.astype(np.int32)
    image = Image.fromarray(array)
    info = PngImagePlugin.PngInfo()
    for key, value in DATA[metadata].items():
        info.add_text(key, value)
    label = "fixture.png"
    image.save(tmp_path / label, pnginfo=info)
    data = (tmp_path / label).read_bytes()
    limits.image_work(data)
    source_name = "Simple_Readable_Metadata_SG.py" if family == "sg" else "Simple_Readable_Metadata_MAX_SG.py"
    native = pristine(source_name, tmp_path)
    converted = ImageAlgorithms() if family == "sg" else MaxAlgorithms()
    converted.input_label, converted.source_bytes = label, data
    converted.sampler_names, converted.scheduler_names = names.SAMPLERS, names.SCHEDULERS
    for show_info in (["both", "properties", "metadata", "none"] if family == "sg" else ["on", "off"]):
        kwargs = {"show_info": show_info, "emoji_in_readable_text": emoji}
        same(native.load_analyze_extract(label, **kwargs), converted.load_analyze_extract(label, **kwargs))


@pytest.mark.parametrize("family", ["sg", "max"])
@pytest.mark.parametrize("codec", ["JPEG", "WEBP", "BMP", "TIFF", "GIF"])
def test_exact_other_source_image_decoders(tmp_path, family, codec):
    image = Image.new("RGB", (6, 4), (20, 50, 70))
    label = "fixture." + codec.lower()
    image.save(tmp_path / label, format=codec)
    converted = ImageAlgorithms() if family == "sg" else MaxAlgorithms()
    converted.input_label, converted.source_bytes = label, (tmp_path / label).read_bytes()
    converted.sampler_names, converted.scheduler_names = names.SAMPLERS, names.SCHEDULERS
    source_name = "Simple_Readable_Metadata_SG.py" if family == "sg" else "Simple_Readable_Metadata_MAX_SG.py"
    same(pristine(source_name, tmp_path).load_analyze_extract(label), converted.load_analyze_extract(label))


@pytest.mark.parametrize("value", ["Euler", "Euler a", "euler", "DPM++ 2M", "not-known", "N/A", "", None])
def test_native_sampler_mapping(tmp_path, value):
    native = pristine("Simple_Readable_Metadata_MAX_SG.py", tmp_path)
    converted = MaxAlgorithms()
    converted.sampler_names, converted.scheduler_names = names.SAMPLERS, names.SCHEDULERS
    same(native.convert_sampler_string_to_comfyui_type(value), converted.convert_sampler_string_to_comfyui_type(value))
    same(native.convert_scheduler_string_to_comfyui_type(value), converted.convert_scheduler_string_to_comfyui_type(value))


@pytest.mark.parametrize("label", ["/etc/file", "../x", "a/../x", "a\\b", "a//b", "x\0y", ""])
def test_managed_label_refusal(label):
    with pytest.raises(ValueError):
        limits.logical_label(label)


def test_aggregate_metadata_limits():
    with pytest.raises(ValueError, match="item"):
        limits.container_work([""] * 4096)
    with pytest.raises(ValueError, match="text"):
        limits.container_work({"a": "x" * 32768, "b": "y" * 32768})
    with pytest.raises(ValueError, match="nesting"):
        limits.json_work("[" * 33 + "0" + "]" * 33)
    with pytest.raises(ValueError):
        limits.image_work(b"x" * (limits.ENCODED_IMAGE_BYTES + 1))
    assert limits.logical_label("subdir/name.png") == "subdir/name.png"


def test_pixel_preflight_before_decode(monkeypatch):
    class Header:
        size = (4096, 4096)
        info = {}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def load(self):
            raise AssertionError("decode must not run")
    monkeypatch.setattr(limits.Image, "open", lambda *args: Header())
    with pytest.raises(ValueError, match="allocation"):
        limits.image_work(b"header")
