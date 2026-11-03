"""Regression test for the kjnodes repair: LoadAndResizeImage validates and loads like V1 (gate).

    run_in_gate.sh <snapshot dir x3f20054, or the pack folder> <.../v2/tests> <results> \
        test_load_and_resize_image_validation.py

The guarded case, which core refused at validation ("Prompt outputs failed validation"): LoadAndResizeImage
reading an image from the input folder, width 96, height 64, keep_proportion off, divisible_by 8, repeat 2,
red mask channel. Synthetic images are staged in a temporary input folder. Checks:
  * validation through core, in-process (the V3 class) and through a real guest (host proxy from
    secure-nodes.json, backend mirroring CloudExecutionBackend, GuestSession): the staged file is accepted;
    for a missing file, an [input]-annotated name (existing and missing), and three names outside the input
    folder (a missing target, an existing target, and a symlink inside the folder that points outside), the
    result equals V1's own VALIDATE_INPUTS on this core, which counts any of those three as missing;
  * the load itself, in-process (core's V3 refs path) and through the guest: image, mask, width and height
    equal V1's for the case's inputs and for an RGBA file.
Every check records its own exception. Writes /results/load_and_resize.json; exits 1 on any failed check.
"""

import asyncio
import importlib
import importlib.util
import json
import os
import shutil
import sys
import traceback
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK_FOLDER = "ComfyUI-KJNodes-HEAD"
INPUT = Path("/tmp/kj-input")
OUTSIDE = Path("/tmp/kj-outside.png")
CASE = dict(background_color="#000000", divisible_by=8, height=64, keep_proportion=False, mask_channel="red",
            repeat=2, resize=True, width=96)
NAMES = ("no_such_image.png", "generic_scene_768.png [input]", "missing.png [input]", "../escape.png",
         "../kj-outside.png", "link_out.png")
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    return [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")][0]


def snapshot_dir() -> Path:
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/kj-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    return snap


def stage_inputs():
    for name, setter, path in (("input", folder_paths.set_input_directory, INPUT),
                               ("temp", folder_paths.set_temp_directory, Path("/tmp/kj-temp")),
                               ("output", folder_paths.set_output_directory, Path("/tmp/kj-output"))):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        setter(str(path))
    rng = np.random.default_rng(21)
    Image.fromarray(rng.integers(0, 256, (768, 768, 3), dtype=np.uint8)).save(INPUT / "generic_scene_768.png")
    Image.fromarray(rng.integers(0, 256, (200, 300, 4), dtype=np.uint8)).save(INPUT / "rgba_300x200.png")
    (INPUT / "notes.txt").write_text("not an image")
    Image.fromarray(rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)).save(OUTSIDE)
    (INPUT / "link_out.png").symlink_to(OUTSIDE)
    record("fixture: the outside image exists and link_out.png resolves to it",
           OUTSIDE.is_file() and (INPUT / "link_out.png").resolve() == OUTSIDE.resolve(),
           f"{OUTSIDE.is_file()} {(INPUT / 'link_out.png').resolve()}")


def pristine_class(head):
    parent = types.ModuleType("kj_pristine")
    parent.__path__ = [str(head)]
    sys.modules["kj_pristine"] = parent
    return importlib.import_module("kj_pristine.nodes.image_nodes").LoadAndResizeImage


def same(a, b):
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
            return False, f"{type(a).__name__} vs {type(b).__name__}"
        if a.dtype != b.dtype or a.shape != b.shape:
            return False, f"{a.dtype}/{tuple(a.shape)} vs {b.dtype}/{tuple(b.shape)}"
        if not torch.equal(a.cpu(), b.cpu()):
            return False, f"max abs {(a.double().cpu() - b.double().cpu()).abs().max().item()!r}"
        return True, None
    return (type(a) is type(b) and a == b), f"{a!r} vs {b!r}"


async def core_output(obj, node_id, inputs):
    if hasattr(obj, "GET_SCHEMA"):
        obj.GET_SCHEMA()
    output, _ui, _sub, _pending = await execution.get_output_data(
        "kj-load", node_id, obj, {key: [value] for key, value in inputs.items()})
    return tuple(values[0] for values in output)


def compare_load(label, want, got):
    for index, name in enumerate(("image", "mask", "width", "height")):
        ok, detail = same(want[index], got[index])
        record(f"{label}: {name} == V1", ok, detail)


def prompt(image):
    return {"22": {"class_type": "LoadAndResizeImage", "inputs": dict(CASE, image=image)}}


async def check_validation(label, V1):
    """Core's validate_inputs for node 22, with LoadAndResizeImage mapped to the class under test."""
    title = f"validation ({label}): the staged image is accepted"
    try:
        ok_flag, errors, _ = await execution.validate_inputs("kj-load", prompt("generic_scene_768.png"), "22", {})
        record(title, ok_flag is True and not errors, errors)
    except Exception:  # noqa: BLE001
        record(title, False, traceback.format_exc()[-1200:])
    for name in NAMES:
        v1 = V1.VALIDATE_INPUTS(image=name)
        title = f"validation ({label}) {name!r} matches V1 ({v1!r})"
        try:
            ok_flag, errors, _ = await execution.validate_inputs("kj-load", prompt(name), "22", {})
        except Exception:  # noqa: BLE001
            record(title, False, traceback.format_exc()[-1200:])
            continue
        if v1 is True:
            ok = ok_flag is True and not errors
        else:
            ok = ok_flag is False and any(str(v1) in (e.get("details") or "") for e in errors)
        record(title, ok, errors)


async def run() -> dict:
    facts = {}
    head = pack_head()
    stage_inputs()
    V1 = pristine_class(head)
    wants = {}
    for name, extra in (("case", {}), ("rgba", {"keep_proportion": True})):
        image = "generic_scene_768.png" if name == "case" else "rgba_300x200.png"
        wants[name] = (image, dict(CASE, **extra), V1().load_image(image=image, **dict(CASE, **extra)))

    spec = importlib.util.spec_from_file_location(
        "kj_v2", head / "v2" / "__init__.py", submodule_search_locations=[str(head / "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["kj_v2"] = package
    spec.loader.exec_module(package)
    v2_cls = package.NODE_CLASS_MAPPINGS["LoadAndResizeImage"]
    for name, (image, params, want) in wants.items():
        try:
            compare_load(f"in-process {name}", want, await core_output(v2_cls, "22", dict(params, image=image)))
        except Exception:  # noqa: BLE001
            record(f"in-process {name}: load", False, traceback.format_exc()[-1200:])

    saved = core_nodes.NODE_CLASS_MAPPINGS.get("LoadAndResizeImage")
    try:
        core_nodes.NODE_CLASS_MAPPINGS["LoadAndResizeImage"] = v2_cls
        await check_validation("in-process", V1)
    finally:
        if saved is None:
            core_nodes.NODE_CLASS_MAPPINGS.pop("LoadAndResizeImage", None)
        else:
            core_nodes.NODE_CLASS_MAPPINGS["LoadAndResizeImage"] = saved

    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.kj_load_proxy",
                              pack_id="comfyui-kjnodes/x3f20054")
    proxy = loaded.node_mappings["LoadAndResizeImage"]
    session = await GuestSession("kj-load").start()
    facts["sandbox_kind"] = session.sandbox_kind

    class Backend:
        async def dispatch(self, plan, local_call, runtime):
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="kj-load")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    saved = core_nodes.NODE_CLASS_MAPPINGS.get("LoadAndResizeImage")
    core_nodes.NODE_CLASS_MAPPINGS["LoadAndResizeImage"] = proxy
    try:
        await check_validation("guest", V1)
        for name, (image, params, want) in wants.items():
            try:
                compare_load(f"guest {name}", want, await core_output(proxy, "22", dict(params, image=image)))
            except Exception:  # noqa: BLE001
                record(f"guest {name}: load", False, traceback.format_exc()[-1200:])
    finally:
        if saved is None:
            core_nodes.NODE_CLASS_MAPPINGS.pop("LoadAndResizeImage", None)
        else:
            core_nodes.NODE_CLASS_MAPPINGS["LoadAndResizeImage"] = saved
        _sdk.providers.register_execution_backend(previous)
        facts["guest_pid"] = session.last_guest_pid
        await session.kill()
    record("guest: out-of-process", facts.get("guest_pid") not in (None, os.getpid()), facts.get("guest_pid"))
    return facts


def main() -> int:
    try:
        facts = asyncio.run(run())
    except Exception:  # noqa: BLE001
        facts = {"error": traceback.format_exc()}
        record("session", False, facts["error"])
    failed = [c["check"] for c in checks if not c["ok"]]
    result = {"pack": "comfyui-kjnodes", "repair": "r1 (KJ rca r2 + guest validation fix + regression test)",
              "checks": checks, "failed": failed, "facts": facts, "verdict": "PASS" if not failed else "FAIL"}
    Path("/results/load_and_resize.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
