"""Native math/outputs + prior exact tag fixtures, not registered guest proof."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace, ModuleType
import cv2
import numpy as np
import pytest
import torch

V2 = Path(os.environ["AMY_READABLE_V2"])
package = "amy_readable_video_helpers"
root = ModuleType(package)
root.__path__ = [str(V2)]
root.__spec__ = importlib.util.spec_from_loader(package, loader=None, is_package=True)
sys.modules[package] = root
spec = importlib.util.spec_from_file_location(package + ".video_transport", V2 / "video_transport.py")
transport = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = transport
spec.loader.exec_module(transport)
receipt = json.loads(Path("/Users/ben/popbot/raw-chats/outputs/amy-oct8-readable-tags-tag-1.json").read_bytes())
ROWS = receipt["rows"]


def native(row):
    source = V2.parent / "Simple_Readable_Metadata_VIDEO_SG.py"
    tree = ast.parse(source.read_bytes())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name not in ("INPUT_TYPES", "IS_CHANGED", "VALIDATE_INPUTS")]
    path = row["fixture"]["path"]
    namespace = {"torch": torch, "np": np, "cv2": cv2, "os": os, "re": re, "json": json,
        "folder_paths": SimpleNamespace(get_annotated_filepath=lambda label: path)}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(source), "exec"), namespace)
    instance = namespace[cls.name]()
    # Prior measured native Pillow/ffprobe selection; no process in this test.
    # This isolates unchanged full math; tag equality is tested separately.
    instance.extract_raw_video_metadata = lambda path: row["native_selected"]
    return instance


def same(left, right):
    assert type(left) is type(right)
    if isinstance(left, torch.Tensor):
        assert left.shape == right.shape and left.dtype == right.dtype
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


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["logical"])
def test_exact_prior_native_tag_selection(row):
    blob = Path(row["fixture"]["path"]).read_bytes()
    assert hashlib.sha256(blob).hexdigest() == row["fixture"]["sha256"]
    assert transport.tags_from_bytes(blob, row["logical"]) == row["native_selected"]


VIDEO_ROWS = [row for row in ROWS if row["logical"].endswith((".mkv", ".mp4"))]
@pytest.mark.parametrize("row", VIDEO_ROWS, ids=lambda row: row["logical"])
@pytest.mark.parametrize("force,limit,resize", [(0,0,0),(7,0,0),(60,2,0),(12,3,80),(0,1,64),(0,0,32)])
@pytest.mark.parametrize("emoji", [False, True])
def test_exact_all_ten_outputs_and_ui(row, force, limit, resize, emoji):
    blob = Path(row["fixture"]["path"]).read_bytes()
    before = set(Path(transport.tempfile.gettempdir()).glob("amy-srm-video-*"))
    actual = transport.analyze_video(blob, row["logical"], force, limit, resize, emoji)
    expected = native(row).load_video_analyze(row["logical"], force, limit, resize, emoji)
    same(expected, actual)
    assert set(Path(transport.tempfile.gettempdir()).glob("amy-srm-video-*")) == before


@pytest.mark.parametrize("kind", ["bytes", "decode", "output", "error", "malformed"])
def test_cleanup_refusals_and_recovery(monkeypatch, kind):
    row = VIDEO_ROWS[0]
    blob = Path(row["fixture"]["path"]).read_bytes()
    before = set(Path(transport.tempfile.gettempdir()).glob("amy-srm-video-*"))
    with monkeypatch.context() as patch:
        if kind == "bytes":
            patch.setattr(transport, "ENCODED_MAX", 1)
        elif kind == "decode":
            patch.setattr(transport, "DECODE_FRAMES_MAX", 1)
        elif kind == "output":
            patch.setattr(transport, "OUTPUT_BYTES_MAX", 1)
            patch.setattr(transport.cv2, "cvtColor", lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("conversion must not run after budget refusal")))
            patch.setattr(transport.cv2, "resize", lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("resize must not run after budget refusal")))
        elif kind == "error":
            patch.setattr(transport.ManagedVideoAlgorithms, "selected_frame",
                lambda *args: (_ for _ in ()).throw(RuntimeError("injected after open")))
        else:
            blob = b"not a video"
        with pytest.raises((ValueError, RuntimeError)):
            transport.analyze_video(blob, row["logical"], resize_long_edge=80)
    assert set(Path(transport.tempfile.gettempdir()).glob("amy-srm-video-*")) == before
    assert transport.analyze_video(Path(row["fixture"]["path"]).read_bytes(), row["logical"], max_frames=1)["result"][3] == 1
