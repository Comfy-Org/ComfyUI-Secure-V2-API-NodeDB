"""Impact Pack repair 7 (JACK): DetailerForEach end to end through Core's real encode, sample and decode (gate).

    DEPS=<Impact dependency-profile wheels unpacked, test-only dill/piexif under _orig_only/> \
    run_in_gate.sh <root holding ComfyUI-Impact-Pack-HEAD/, or that folder> <Impact v2/tests> <results> \
        test_detailer_repair_r7.py

NED's r1 harness (test_iterative_upscale_segs_preview.py), applied to the detailers. Both sides run the same prompts
through Core's PromptExecutor:
  original  the pristine Impact Pack's node classes (a subprocess; the pack imported from a copy of the pristine
            tree, its server routes given a stand-in route table);
  v2        the manifest proxies, executed in a real out-of-process guest (core's own nodes stay in the host).
Shared test nodes supply the inputs: the tiny seeded SD1.x-architecture model, VAE and conditioning of tests/_tiny_sd.py
(Core's real encode, sample and decode run on CPU in both processes, with byte-identical weights), a CLIP stand-in
(unused: the wildcard is empty), 8-bit images and masks.
Cases: B12's highuse_detailerforeach_mask_roi (MaskToSEGS crop_factor 1.4 over a rectangle on a 768x768 image ->
DetailerForEach guide 128 bbox, max 256, force_inpaint, noise_mask, feather 4, euler/normal, 2 steps, cfg 1, denoise
0.35, the optional inputs left out as in B12's prompt), and variants that each change one thing.
The final images are compared exactly; the 8-bit difference (max, pixels > 2) is reported as on B12.
Writes /results/impact_detailer_r7.json; exits 1 on any failed check.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import traceback
import types
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path("/pack")
RESULTS = Path("/results")
DEPS = Path("/deps")
for _index, _path in enumerate(("/core", "/overlay", "/tests")):
    sys.path.insert(_index, _path)
os.environ.setdefault("HOME", "/tmp")

PACK_FOLDER = "ComfyUI-Impact-Pack-HEAD"
NODE_IDS = ("MaskToSEGS", "DetailerForEach")


def pack_head() -> Path:
    if (ROOT / "v2").is_dir():
        return ROOT
    return [d for d in sorted(ROOT.iterdir()) if d.is_dir() and not d.name.startswith(".")][0]


# ---------------------------------------------------------------- prompts (the same on both sides)
B12 = {"guide_size": 128.0, "guide_size_for": True, "max_size": 256.0, "seed": 20261102, "steps": 2, "cfg": 1.0,
       "sampler_name": "euler", "scheduler": "normal", "denoise": 0.35, "feather": 4, "noise_mask": True,
       "force_inpaint": True, "wildcard": "", "cycle": 1}


def detailer_prompt(variant):
    inputs = dict(B12, **variant.get("detailer", {}))
    for key in variant.get("drop", ()):
        inputs.pop(key, None)
    inputs.update({"image": ["photo", 0], "segs": ["segs", 0], "model": ["m", 0], "clip": ["clip", 0],
                   "vae": ["m", 1], "positive": ["c", 0], "negative": ["c", 1]})
    return {
        "m": {"class_type": "NedTinyModel", "inputs": {}},
        "c": {"class_type": "NedTinyConditioning", "inputs": {}},
        "clip": {"class_type": "JackTinyClip", "inputs": {}},
        "photo": {"class_type": "NedImage", "inputs": {"width": variant.get("size", 768),
                                                      "height": variant.get("size", 768), "seed": 7}},
        "mask": {"class_type": "JackRoiMask", "inputs": {"size": variant.get("size", 768),
                                                        "box": variant.get("box", "150,190,330,420")}},
        "segs": {"class_type": "MaskToSEGS", "inputs": {
            "mask": ["mask", 0], "combined": True, "crop_factor": variant.get("crop_factor", 1.4),
            "bbox_fill": False, "drop_size": 1, "contour_fill": False}},
        "20": {"class_type": "DetailerForEach", "inputs": inputs},
        "cap": {"class_type": "NedCapture", "inputs": {"value": ["20", 0], "key": "image"}},
    }


CASES = {
    "B12 case (force_inpaint at native size, noise mask, feather 4, optional inputs absent)": {},
    "crop a multiple of 8": {"box": "152,192,328,416", "crop_factor": 1.0},
    "noise_mask off": {"detailer": {"noise_mask": False}},
    "noise_mask_feather 20 given": {"detailer": {"noise_mask_feather": 20}},
    "denoise 0.5 (steps/denoise an integer)": {"detailer": {"denoise": 0.5}},
    "cfg 2": {"detailer": {"cfg": 2.0}},
    "upscaled (guide 384, max 768, no force_inpaint)": {"detailer": {"guide_size": 384.0, "max_size": 768.0,
                                                                     "force_inpaint": False}},
    "feather 0": {"detailer": {"feather": 0}},
}


# ---------------------------------------------------------------- shared test nodes
def register_test_nodes(core_nodes, captured):
    import torch
    import _tiny_sd

    cache = {}

    class NedTinyModel:
        RETURN_TYPES = ("MODEL", "VAE")
        FUNCTION = "load"
        CATEGORY = "ned/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {}}

        def load(self):
            if "model" not in cache:
                cache["model"], cache["vae"] = _tiny_sd.build_model(), _tiny_sd.build_vae()
            return cache["model"], cache["vae"]

    class NedTinyConditioning:
        RETURN_TYPES = ("CONDITIONING", "CONDITIONING")
        FUNCTION = "load"
        CATEGORY = "ned/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {}}

        def load(self):
            return _tiny_sd.build_conditioning(3), _tiny_sd.build_conditioning(4)

    class TinyClip:
        """A CLIP stand-in: the empty wildcard never reaches it, on either side."""

        def tokenize(self, text):
            raise RuntimeError("the test CLIP is not used")

        def encode_from_tokens(self, tokens, **_kwargs):
            raise RuntimeError("the test CLIP is not used")

    class JackTinyClip:
        RETURN_TYPES = ("CLIP",)
        FUNCTION = "load"
        CATEGORY = "jack/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {}}

        def load(self):
            return (TinyClip(),)

    class NedImage:
        RETURN_TYPES = ("IMAGE",)
        FUNCTION = "make"
        CATEGORY = "ned/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"width": ("INT", {"default": 64, "min": 8, "max": 4096}),
                                 "height": ("INT", {"default": 64, "min": 8, "max": 4096}),
                                 "seed": ("INT", {"default": 0, "min": 0, "max": 2 ** 31})}}

        def make(self, width, height, seed):
            generator = torch.Generator().manual_seed(int(seed))
            image = torch.rand((1, int(height), int(width), 3), generator=generator)
            return (torch.floor(image * 255.0) / 255.0,)  # 8-bit values, as LoadImage gives

    class JackRoiMask:
        RETURN_TYPES = ("MASK",)
        FUNCTION = "make"
        CATEGORY = "jack/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"size": ("INT", {"default": 768, "min": 8, "max": 4096}),
                                 "box": ("STRING", {"default": "150,190,330,420"})}}

        def make(self, size, box):
            top, left, bottom, right = (int(v) for v in box.split(","))
            mask = torch.zeros((1, int(size), int(size)))
            mask[:, top:bottom, left:right] = 1.0  # a plain mask, as ImageToMask gives from a white-on-black PNG
            return (mask,)

    class NedCapture:
        RETURN_TYPES = ()
        FUNCTION = "capture"
        OUTPUT_NODE = True
        INPUT_IS_LIST = True
        CATEGORY = "ned/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"value": ("*",), "key": ("STRING", {"default": "value"})}}

        @classmethod
        def VALIDATE_INPUTS(cls, input_types=None, **_kwargs):
            return True

        def capture(self, value, key):
            captured[key[0]] = value
            return {}

    for cls in (NedTinyModel, NedTinyConditioning, JackTinyClip, NedImage, JackRoiMask, NedCapture):
        core_nodes.NODE_CLASS_MAPPINGS[cls.__name__] = cls


class FakeServer:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None

    def send_sync(self, *_args, **_kwargs):
        pass

    def queue_updated(self):
        pass


async def run_prompt(execution, prompt, prompt_id):
    executor = execution.PromptExecutor(FakeServer(), cache_type=False,
                                        cache_args={"lru": 0, "ram": 0, "ram_inactive": 0})
    targets = [k for k, v in prompt.items() if v["class_type"] == "NedCapture"]
    await executor.execute_async(json.loads(json.dumps(prompt)), prompt_id, {}, targets)
    errors = [m[1] for m in executor.status_messages if m[0] == "execution_error"]
    return executor.success and not errors, errors, executor.history_result.get("outputs") or {}


def to_plain(value):
    import torch

    if isinstance(value, torch.Tensor):
        return value.detach().cpu().contiguous()
    if isinstance(value, dict) and "samples" in value:
        return {"samples": value["samples"].detach().cpu().contiguous()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


async def run_side(label, mappings, execution, core_nodes):
    captured = {}
    register_test_nodes(core_nodes, captured)
    saved = {k: core_nodes.NODE_CLASS_MAPPINGS.get(k) for k in mappings}
    core_nodes.NODE_CLASS_MAPPINGS.update(mappings)
    results = {}
    try:
        for index, (name, variant) in enumerate(CASES.items()):
            captured.clear()
            try:
                ok, errors, _outputs = await run_prompt(execution, detailer_prompt(variant), f"{label}-{index}")
                results[name] = {"ok": ok, "errors": [str(e.get("exception_message"))[:500] for e in errors],
                                 "captured": {k: to_plain(v) for k, v in captured.items()}}
            except Exception:  # noqa: BLE001
                results[name] = {"ok": False, "errors": [traceback.format_exc()[-1500:]], "captured": {}}
    finally:
        for key, value in saved.items():
            if value is None:
                core_nodes.NODE_CLASS_MAPPINGS.pop(key, None)
            else:
                core_nodes.NODE_CLASS_MAPPINGS[key] = value
    return results


# Results cross from the original-side subprocess as JSON plus one safetensors file: no pickle anywhere.
def pack_results(value, tensors):
    import numpy as np
    import torch

    if isinstance(value, np.ndarray):
        value = torch.from_numpy(np.ascontiguousarray(value))
    if isinstance(value, torch.Tensor):
        key = f"t{len(tensors)}"
        tensors[key] = value.contiguous()
        return {"__tensor__": key}
    if isinstance(value, dict):
        return {str(k): pack_results(v, tensors) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [pack_results(v, tensors) for v in value]
    return value


def unpack_results(value, tensors):
    if isinstance(value, dict):
        if set(value) == {"__tensor__"}:
            return tensors[value["__tensor__"]]
        return {k: unpack_results(v, tensors) for k, v in value.items()}
    if isinstance(value, list):
        return [unpack_results(v, tensors) for v in value]
    return value


def prepare_core(tag):
    from comfy.cli_args import args

    args.cpu = True
    import comfy.samplers  # noqa: F401
    import execution
    import folder_paths
    import nodes as core_nodes

    for name, setter in (("temp", folder_paths.set_temp_directory), ("output", folder_paths.set_output_directory)):
        path = Path(f"/tmp/jack-7-{tag}-{name}")
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        setter(str(path))
    return execution, core_nodes, folder_paths


# ---------------------------------------------------------------- the original side (a subprocess)
def original_main(out_path):
    sys.path.insert(0, str(DEPS / "_orig_only"))
    sys.path.insert(0, str(DEPS))
    execution, core_nodes, _folder_paths = prepare_core("orig")
    import server

    class Routes:
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: (lambda function: function)

    class Instance:
        routes = Routes()
        prompt_queue = types.SimpleNamespace(currently_running={})

        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: None

    server.PromptServer.instance = Instance()
    root = Path("/tmp/orig-impact-7")
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(pack_head(), root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    sys.path.insert(0, str(root / "modules"))
    import impact.config  # noqa: F401  (upstream __init__ order)
    import impact.impact_server  # noqa: F401
    import impact.impact_pack as impact_pack
    import impact.segs_nodes as segs_nodes

    mappings = {"MaskToSEGS": segs_nodes.MaskToSEGS, "DetailerForEach": impact_pack.DetailerForEach}
    import _tiny_sd
    from safetensors.torch import save_file

    digests = {"model": _tiny_sd.state_dict_digest(_tiny_sd.build_model()),
               "vae": _tiny_sd.state_dict_digest(_tiny_sd.build_vae())}
    results = asyncio.run(run_side("orig", mappings, execution, core_nodes))
    tensors = {}
    payload = pack_results({"results": results, "digests": digests}, tensors)
    save_file(tensors or {"none": __import__("torch").zeros(1)}, out_path + ".safetensors")
    Path(out_path + ".json").write_text(json.dumps(payload))


# ---------------------------------------------------------------- the v2 side (this process)
async def v2_side():
    execution, core_nodes, folder_paths = prepare_core("v2")
    from comfy_api.latest import _sdk
    from comfy_secure_nodes import packdb
    from comfy_secure_nodes.transport.host import GuestSession
    import _tiny_sd

    head = pack_head()
    snap = Path("/tmp/impact-7-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(head, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    manifest = json.loads((snap / PACK_FOLDER / "v2" / "secure-nodes.json").read_text())
    for relative in (manifest.get("asset_directories") or {}).values():
        (snap / PACK_FOLDER / "v2" / relative).mkdir(parents=True, exist_ok=True)
    loaded = packdb.load_pack(snap, mount_name="custom_nodes.impact_jack_r7", pack_id="comfyui-impact-pack/x429d015")
    for folder, directory in loaded.asset_directories.items():
        folder_paths.add_model_folder_path(folder, str(directory))
    mappings = {node_id: loaded.node_mappings[node_id] for node_id in NODE_IDS}

    class ProfileGuestSession(GuestSession):
        """The guest sees the pack's dependency profile (DEPS top level, never _orig_only)."""

        def _adjust_guest_env(self, env):
            super()._adjust_guest_env(env)
            if DEPS.is_dir():
                env["PYTHONPATH"] = os.pathsep.join(p for p in (str(DEPS), env.get("PYTHONPATH", "")) if p)

        def _extra_ro_paths(self):
            return list(super()._extra_ro_paths()) + ([str(DEPS)] if DEPS.is_dir() else [])

    session = await ProfileGuestSession("impact-jack-7").start()

    class Backend:
        async def dispatch(self, plan, local_call, runtime=None):
            if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                return await local_call()
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="impact-jack-7")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    try:
        results = await run_side("v2", mappings, execution, core_nodes)
    finally:
        _sdk.providers.register_execution_backend(previous)
        pid = session.last_guest_pid
        await session.kill()
    digests = {"model": _tiny_sd.state_dict_digest(_tiny_sd.build_model()),
               "vae": _tiny_sd.state_dict_digest(_tiny_sd.build_vae())}
    return results, digests, pid


# ---------------------------------------------------------------- comparison
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def image_metrics(a, b):
    """Exact comparison plus B12's 8-bit metrics (the SaveImage PNG values)."""
    import torch

    if a.shape != b.shape or a.dtype != b.dtype:
        return {"exact": False, "detail": f"{a.dtype}{tuple(a.shape)} vs {b.dtype}{tuple(b.shape)}"}
    exact = torch.equal(a, b)
    # SaveImage: np.clip(255. * i, 0, 255).astype(np.uint8), a truncation
    a8 = torch.clamp(a * 255.0, 0, 255).to(torch.uint8).to(torch.int16)
    b8 = torch.clamp(b * 255.0, 0, 255).to(torch.uint8).to(torch.int16)
    diff = (a8 - b8).abs()
    pixel = diff.amax(dim=-1)
    over = (pixel > 2).nonzero()
    box = None
    if len(over):
        box = [int(over[:, 2].min()), int(over[:, 1].min()), int(over[:, 2].max()), int(over[:, 1].max())]
    return {"exact": bool(exact), "max_float_diff": float((a.double() - b.double()).abs().max()),
            "max_abs_diff_255": int(diff.max()), "differing_values": int((diff > 0).sum()),
            "pixels_diff_gt2": int(len(over)), "bbox_diff_gt2_xyxy": box}


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "--original":
        original_main(sys.argv[2])
        return 0
    facts = {}
    try:
        from safetensors.torch import load_file

        out = "/tmp/impact-7-original"
        completed = subprocess.run([sys.executable, __file__, "--original", out], capture_output=True, text=True,
                                   timeout=3000)
        (RESULTS / "side-original.log").write_text(completed.stdout[-200000:] + "\n" + completed.stderr[-200000:])
        if completed.returncode != 0 or not Path(out + ".json").is_file():
            raise RuntimeError(f"original side failed: {completed.stderr[-3000:]}")
        original = unpack_results(json.loads(Path(out + ".json").read_text()), load_file(out + ".safetensors"))
        v2_results, v2_digests, pid = asyncio.run(v2_side())
        facts["guest_pid"] = pid
        record("guest: out-of-process", pid not in (None, os.getpid()), pid)
        record("tiny model and VAE are byte-identical on both sides", original["digests"] == v2_digests,
               (original["digests"], v2_digests))
        for case, want in original["results"].items():
            got = v2_results.get(case, {"ok": False, "errors": ["missing"], "captured": {}})
            if not want["ok"]:
                same = (not got["ok"]) and bool(want["errors"]) and bool(got["errors"]) and all(
                    a.strip().splitlines()[-1] in b for a, b in zip(want["errors"], got["errors"]))
                record(f"{case}: fails like the original", same, {"original": want["errors"], "v2": got["errors"]})
                continue
            record(f"{case}: v2 runs", got["ok"], got["errors"])
            if not got["ok"]:
                continue
            a = want["captured"].get("image")
            b = got["captured"].get("image")
            if not (isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 1):
                record(f"{case}: one image on both sides", False, (type(a), type(b)))
                continue
            metrics = image_metrics(a[0], b[0])
            facts[case] = metrics
            record(f"{case}: image == the original's", metrics["exact"], metrics)
    except Exception:  # noqa: BLE001
        record("session", False, traceback.format_exc()[-3000:])
    failed = [c["check"] for c in checks if not c["ok"]]
    result = {"pack": "comfyui-impact-pack", "repair": "JACK repair 7 (DetailerForEach end to end)",
              "checks": checks, "failed": failed, "facts": facts, "verdict": "PASS" if not failed else "FAIL"}
    (RESULTS / "impact_detailer_r7.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed[:40]}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
