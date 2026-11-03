"""Regression test for the kjnodes repair: ImageAndMaskPreview feeds a linked node like V1 (gate).

    run_in_gate.sh <snapshot dir x3f20054, or the pack folder> <.../v2/tests> <results> \
        test_image_and_mask_preview_chain.py

V1 ImageAndMaskPreview subclasses core's SaveImage. With pass_through off it returns self.save_images(...),
which on this core is {"ui": ..., "result": (images,)}, so its output 0 is the composite in both modes. The
guarded prompt: LoadImage -> LoadImageMask -> ImageAndMaskPreview(image, mask, opacity 1.0, "255, 255, 255")
-> SaveImage(images = output 0), with pass_through off and on. Synthetic images, temporary folders.
Checks, V1 (the pristine class) against V2 (host proxy from secure-nodes.json + a real guest, core's own
nodes in the host as in the cloud backend):
  * the node's outputs called directly: the composite tensor equals V1's (torch.equal), and the preview UI
    has the same shape;
  * the whole prompt through core's PromptExecutor: it succeeds, the SaveImage file's pixels equal V1's, and
    ImageAndMaskPreview's preview pixels equal V1's.
Every check records its own exception. Writes /results/image_and_mask_preview.json; exits 1 on any failure.
"""

import asyncio
import importlib
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
INPUT, TEMP, OUTPUT = Path("/tmp/kj-input"), Path("/tmp/kj-temp"), Path("/tmp/kj-output")
PARAMS = dict(mask_color="255, 255, 255", mask_opacity=1.0)
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def guarded(name, fn):
    try:
        ok, detail = fn()
    except Exception:  # noqa: BLE001
        ok, detail = False, traceback.format_exc()[-1200:]
    record(name, ok, detail)


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


def stage_folders():
    for path, setter in ((INPUT, folder_paths.set_input_directory), (TEMP, folder_paths.set_temp_directory),
                         (OUTPUT, folder_paths.set_output_directory)):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        setter(str(path))
    rng = np.random.default_rng(31)
    Image.fromarray(rng.integers(0, 256, (192, 256, 3), dtype=np.uint8)).save(INPUT / "scene_256x192.png")
    Image.fromarray(rng.integers(0, 256, (192, 256, 3), dtype=np.uint8)).save(INPUT / "mask_256x192.png")


def pristine_class(head):
    parent = types.ModuleType("kj_pristine")
    parent.__path__ = [str(head)]
    sys.modules["kj_pristine"] = parent
    return importlib.import_module("kj_pristine.nodes.image_nodes").ImageAndMaskPreview


class FakeServer:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None
        self.events = []

    def send_sync(self, event, data, sid=None):
        self.events.append(event)

    def queue_updated(self):
        pass


def prompt(pass_through, prefix):
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": "scene_256x192.png"}},
        "2": {"class_type": "LoadImageMask", "inputs": {"channel": "red", "image": "mask_256x192.png"}},
        "3": {"class_type": "ImageAndMaskPreview",
              "inputs": dict(PARAMS, image=["1", 0], mask=["2", 0], pass_through=pass_through)},
        "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["3", 0]}},
    }


def pixels(entry):
    base = {"temp": TEMP, "output": OUTPUT}[entry["type"]]
    with Image.open(base / entry.get("subfolder", "") / entry["filename"]) as image:
        return np.asarray(image.convert("RGB")).copy()


async def run_prompt(label, cls, pass_through):
    saved = core_nodes.NODE_CLASS_MAPPINGS.get("ImageAndMaskPreview")
    core_nodes.NODE_CLASS_MAPPINGS["ImageAndMaskPreview"] = cls
    try:
        executor = execution.PromptExecutor(FakeServer(), cache_type=False,
                                            cache_args={"lru": 0, "ram": 0, "ram_inactive": 0})
        await executor.execute_async(prompt(pass_through, f"kj-iamp/{label}-pt{int(pass_through)}/o0"),
                                     f"kj-iamp-{label}-{int(pass_through)}", {}, ["4"])
        errors = [m for m in executor.status_messages if m[0] == "execution_error"]
        return {"success": executor.success, "errors": errors,
                "outputs": executor.history_result.get("outputs") or {}}
    finally:
        if saved is None:
            core_nodes.NODE_CLASS_MAPPINGS.pop("ImageAndMaskPreview", None)
        else:
            core_nodes.NODE_CLASS_MAPPINGS["ImageAndMaskPreview"] = saved


def compare_prompts(pass_through, v1, v2):
    tag = f"prompt (pass_through {pass_through})"
    record(f"{tag}: V1 succeeds", v1["success"] and not v1["errors"], v1["errors"])
    record(f"{tag}: V2 succeeds", v2["success"] and not v2["errors"], json.dumps(v2["errors"], default=str))

    def saved_equal():
        a, b = v1["outputs"]["4"]["images"], v2["outputs"]["4"]["images"]
        if len(a) != 1 or len(b) != 1:
            return False, f"{len(a)} vs {len(b)} saved images"
        pa, pb = pixels(a[0]), pixels(b[0])
        return (pa.shape == pb.shape and np.array_equal(pa, pb)), f"{pa.shape} vs {pb.shape}"
    guarded(f"{tag}: SaveImage pixels == V1", saved_equal)

    def preview_equal():
        a = (v1["outputs"].get("3") or {}).get("images", [])
        b = (v2["outputs"].get("3") or {}).get("images", [])
        if len(a) != len(b) or [e["type"] for e in a] != [e["type"] for e in b]:
            return False, f"{a} vs {b}"
        for ea, eb in zip(a, b):
            pa, pb = pixels(ea), pixels(eb)
            if pa.shape != pb.shape or not np.array_equal(pa, pb):
                return False, f"preview pixels differ {pa.shape} vs {pb.shape}"
        return True, None
    guarded(f"{tag}: ImageAndMaskPreview preview == V1", preview_equal)


async def direct_outputs(cls, inputs):
    if hasattr(cls, "GET_SCHEMA"):
        cls.GET_SCHEMA()
    output, ui, _sub, _pending = await execution.get_output_data(
        "kj-iamp", "3", cls, {key: [value] for key, value in inputs.items()})
    return output, ui


async def run() -> dict:
    facts = {}
    head = pack_head()
    stage_folders()
    V1 = pristine_class(head)
    image = core_nodes.LoadImage().load_image("scene_256x192.png")[0]
    loader = core_nodes.LoadImageMask()
    mask = getattr(loader, loader.FUNCTION)("mask_256x192.png", "red")[0]
    v1_direct = {}
    for pass_through in (False, True):
        returned = V1().execute(pass_through=pass_through, image=image, mask=mask, **PARAMS)
        v1_direct[pass_through] = returned if isinstance(returned, dict) else {"result": returned}
    v1_prompts = {pt: await run_prompt("v1", V1, pt) for pt in (False, True)}

    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.kj_iamp_proxy",
                              pack_id="comfyui-kjnodes/x3f20054")
    proxy = loaded.node_mappings["ImageAndMaskPreview"]
    session = await GuestSession("kj-iamp").start()
    facts["sandbox_kind"] = session.sandbox_kind

    class Backend:
        async def dispatch(self, plan, local_call, runtime=None):
            # As CloudExecutionBackend: core's own nodes run in the host; pack nodes go to the guest.
            if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                return await local_call()
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="kj-iamp")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    try:
        for pass_through in (False, True):
            tag = f"direct (pass_through {pass_through})"
            want = v1_direct[pass_through]
            try:
                output, ui = await direct_outputs(proxy, dict(PARAMS, image=image, mask=mask,
                                                              pass_through=pass_through))
            except Exception:  # noqa: BLE001
                record(f"{tag}: V2 runs", False, traceback.format_exc()[-1200:])
                continue
            want_tensor = want["result"][0]
            got_tensor = output[0][0] if output and output[0] else None
            ok = (isinstance(got_tensor, torch.Tensor) and got_tensor.shape == want_tensor.shape
                  and got_tensor.dtype == want_tensor.dtype and torch.equal(got_tensor.cpu(), want_tensor.cpu()))
            record(f"{tag}: output 0 == V1 composite", ok,
                   f"{len(output)} outputs; {type(got_tensor).__name__} "
                   f"{getattr(got_tensor, 'shape', None)} vs {tuple(want_tensor.shape)}")
            want_ui = want.get("ui") or {}
            got_ui = ui or {}

            def preview_images_equal(want_ui=want_ui, got_ui=got_ui):
                a, b = want_ui.get("images", []), got_ui.get("images", [])
                if len(a) != len(b) or [e["type"] for e in a] != [e["type"] for e in b]:
                    return False, f"{a} vs {b}"
                for ea, eb in zip(a, b):
                    pa, pb = pixels(ea), pixels(eb)
                    if pa.shape != pb.shape or not np.array_equal(pa, pb):
                        return False, f"preview pixels differ {pa.shape} vs {pb.shape}"
                return True, None
            guarded(f"{tag}: preview images == V1 (count, type, pixels)", preview_images_equal)
            # The SDK's preview helper also reports core's V3 'animated' flag (False for a still image); V1's
            # SaveImage UI has no such key. Any other difference in UI keys fails.
            extra = sorted(set(got_ui) - set(want_ui))
            record(f"{tag}: UI keys == V1's, apart from the SDK's animated=False flag",
                   set(want_ui) <= set(got_ui) and extra in ([], ["animated"])
                   and all(flag is False for flag in got_ui.get("animated", [])) if want_ui or got_ui else True,
                   f"{sorted(want_ui)} vs {sorted(got_ui)}: {got_ui.get('animated')}")
        for pass_through in (False, True):
            try:
                v2 = await run_prompt("v2", proxy, pass_through)
            except Exception:  # noqa: BLE001
                record(f"prompt (pass_through {pass_through}): V2 runs", False, traceback.format_exc()[-1200:])
                continue
            compare_prompts(pass_through, v1_prompts[pass_through], v2)
    finally:
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
    result = {"pack": "comfyui-kjnodes", "repair": "r1 (ImageAndMaskPreview output with pass_through off)",
              "checks": checks, "failed": failed, "facts": facts, "verdict": "PASS" if not failed else "FAIL"}
    Path("/results/image_and_mask_preview.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
