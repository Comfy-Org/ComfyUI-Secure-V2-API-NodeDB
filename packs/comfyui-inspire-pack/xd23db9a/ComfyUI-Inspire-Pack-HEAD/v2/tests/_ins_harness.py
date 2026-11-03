"""Shared gate harness for the Inspire tests (pristine vs v2, CPU).

Mounts (run_in_gate.sh):
- /pack: the snapshot dir holding ComfyUI-Inspire-Pack-HEAD, or that folder itself.
- /tests: this folder.
- /deps: opencv-python-headless, unpacked. The pristine inspire/libs/utils.py imports cv2 at import
  time; v2 never imports it.

Fixtures are synthetic: images drawn from seeded random numbers, written into temporary input and
output folders. Nothing reads the snapshot's own media or example files.
"""

import asyncio
import gc
import importlib
import importlib.util
import os
import shutil
import sys
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]
sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402,F401
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

PACK_FOLDER = "ComfyUI-Inspire-Pack-HEAD"
SLUG = "comfyui-inspire-pack"
PIN = "d23db9aa544de9a6d4c609cb7005fa9e0d42031d"
KEY = "xd23db9a"
INPUT = Path("/tmp/ins-input")
OUTPUT = Path("/tmp/ins-output")
V1_DISPLAY = {
    "LoadImagesFromDir //Inspire": "Load Image Batch From Dir (Inspire)",
    "LoadImageListFromDir //Inspire": "Load Image List From Dir (Inspire)",
    "ChangeImageBatchSize //Inspire": "Change Image Batch Size (Inspire)",
}


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


def snapshot_dir() -> Path:
    """A directory holding exactly one pack folder, as packdb.load_pack requires."""
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/ins-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return snap


def load_package(name: str, folder: Path):
    spec = importlib.util.spec_from_file_location(
        name, folder / "__init__.py", submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_pristine_image_util(head: Path):
    """inspire/image_util.py of the pristine pack, imported as the pack imports it, but without the
    pack's __init__ (that imports all thirteen modules, several of which need the Impact Pack)."""
    parent = types.ModuleType("ins_pristine")
    parent.__path__ = [str(head)]
    sys.modules["ins_pristine"] = parent
    return importlib.import_module("ins_pristine.inspire.image_util")


class _NameOrderedOS:
    """Forwards everything to os, except listdir, which returns the same names in name order."""

    def __getattr__(self, name):
        return getattr(os, name)

    @staticmethod
    def listdir(path="."):
        return sorted(os.listdir(path))


def name_ordered_listing(pristine_module):
    """Give one pristine module the listing order V2 has (name order) via its module-global os.
    The original's order is whatever the host filesystem returns; nothing else changes."""
    pristine_module.os = _NameOrderedOS()


def _image(size, mode, seed):
    width, height = size
    channels = {"RGB": 3, "RGBA": 4, "L": 1}[mode]
    data = np.random.default_rng(seed).integers(0, 256, (height, width, channels), dtype=np.uint8)
    return Image.fromarray(data[..., 0] if channels == 1 else data, mode)


def make_fixtures():
    """Synthetic image folders under the temporary input (and output) folder."""
    for root in (INPUT, OUTPUT):
        if root.exists():
            shutil.rmtree(root)
    folder_paths.set_input_directory(str(INPUT))
    folder_paths.set_output_directory(str(OUTPUT))

    def put(rel, size=(24, 16), mode="RGB", seed=0, fmt=None, **save):
        path = INPUT / rel if not rel.startswith("@out/") else OUTPUT / rel[5:]
        path.parent.mkdir(parents=True, exist_ok=True)
        _image(size, mode, seed).save(path, format=fmt, **save)

    put("mixed/img10.png", seed=1)
    put("mixed/img2.png", seed=2)
    put("mixed/img1.png", mode="RGBA", seed=3)
    put("mixed/b.jpg", size=(32, 20), seed=4, fmt="JPEG", quality=90)
    put("mixed/c.webp", seed=5, fmt="WEBP", lossless=True)
    put("mixed/UPPER.PNG", seed=6, fmt="PNG")
    exif = Image.Exif()
    exif[0x0112] = 6
    put("mixed/rot.jpg", size=(16, 24), seed=7, fmt="JPEG", quality=95, exif=exif.tobytes())
    put("mixed/a b ü.png", seed=8)
    put("mixed/sub/x.png", seed=9)
    (INPUT / "mixed/notes.txt").write_text("not an image\n")
    (INPUT / "mixed/noext").write_bytes(b"\x89PNG")
    for index, number in enumerate((3, 1, 2, 11)):
        put(f"rgb_only/f_{number}.png", seed=20 + index)
    put("alpha_sizes/a.png", size=(20, 20), mode="RGBA", seed=30)
    put("alpha_sizes/b.png", size=(30, 10), seed=31)
    put("alpha_sizes/c.png", size=(10, 30), mode="RGBA", seed=32)
    put("single/only.png", mode="RGBA", seed=40)
    (INPUT / "only_txt").mkdir(parents=True)
    (INPUT / "only_txt/a.txt").write_text("a")
    (INPUT / "only_txt/b.txt").write_text("b")
    put("only_sub/inner/i.png", seed=50)
    (INPUT / "empty").mkdir(parents=True)
    put("@out/frames/o2.png", seed=60)
    put("@out/frames/o1.png", mode="RGBA", seed=61)


def run_pristine(obj, **inputs):
    return getattr(obj(), obj.FUNCTION)(**inputs)


async def run_v2(cls, node_id="7", **inputs):
    """A v2 node through core's own V3 execution path (in-process SDK providers)."""
    cls.GET_SCHEMA()
    out = await execution._async_map_node_over_list(
        prompt_id="ins-parity", unique_id=node_id, obj=cls,
        input_data_all={key: [value] for key, value in inputs.items()},
        func=cls.FUNCTION, v3_data=None)
    first = out[0]
    if isinstance(first, asyncio.Task):
        first = await first
    if first is None:
        return None
    return tuple(first.result) if hasattr(first, "result") else tuple(first)


async def run_core(obj, node_id="8", **inputs):
    """Either side through core's full output handling (execution.get_output_data): pass a V1
    instance or a V3 class. Returns core's per-output value lists."""
    if hasattr(obj, "GET_SCHEMA"):
        obj.GET_SCHEMA()
    output, _ui, _subgraph, _pending = await execution.get_output_data(
        "ins-parity", node_id, obj, {key: [value] for key, value in inputs.items()})
    return output


def outcome(call):
    try:
        return "ok", call()
    except Exception as error:  # noqa: BLE001
        return "error", (type(error).__name__, str(error))
    finally:
        gc.collect()


def same(a, b):
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
            return False, "tensor vs non-tensor"
        if a.dtype != b.dtype or a.shape != b.shape or a.device != b.device:
            return False, f"{a.dtype}/{tuple(a.shape)}/{a.device} vs {b.dtype}/{tuple(b.shape)}/{b.device}"
        if not torch.equal(a, b):
            diff = (a.double() - b.double()).abs()
            return False, f"values differ: max abs {diff.max().item()!r}, {int((diff > 0).sum())} elements"
        return True, None
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a) != list(b):
            return False, f"keys {list(a)} vs {list(b)}"
        for key in a:
            ok, detail = same(a[key], b[key])
            if not ok:
                return False, f"[{key!r}] {detail}"
        return True, None
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False, f"{type(a).__name__}[{len(a)}] vs {type(b).__name__}[{len(b)}]"
        for index, (x, y) in enumerate(zip(a, b)):
            ok, detail = same(x, y)
            if not ok:
                return False, f"[{index}] {detail}"
        return True, None
    if type(a) is not type(b) or a != b:
        return False, f"{a!r} vs {b!r}"
    return True, None
