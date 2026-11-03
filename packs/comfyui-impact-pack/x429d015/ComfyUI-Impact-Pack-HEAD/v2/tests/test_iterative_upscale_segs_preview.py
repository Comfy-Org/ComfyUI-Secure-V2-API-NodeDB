"""Impact Pack repair (NED r1): iterative upscaling with a denoise-schedule hook, and SEGSPreview (gate).

    DEPS=<Impact dependency-profile wheels unpacked, test-only dill/piexif under _orig_only/> \
    run_in_gate.sh <root holding ComfyUI-Impact-Pack-HEAD/, or that folder> <Impact v2/tests> <results> \
        test_iterative_upscale_segs_preview.py

Both sides run the same prompts through Core's PromptExecutor:
  original  the pristine Impact Pack's node classes (a subprocess; the pack imported from a copy of the pristine
            tree, its server routes given a stand-in route table);
  v2        the manifest proxies, executed in a real guest (core's own nodes stay in the host, as in the cloud
            backend).
Shared test nodes supply the inputs: a tiny seeded SD1.x-architecture model, VAE and conditioning built from
Core's own classes (tests/_tiny_sd.py: Core's real encode, sample and decode run, on CPU, in both processes,
with byte-identical weights), 8-bit images and masks. Captured outputs are compared exactly.
Cases:
  iterative  DenoiseScheduleHookProvider -> PixelKSampleUpscalerProvider -> IterativeLatentUpscale and
             IterativeImageUpscale (the reported case's parameters, plus geometric/3-step/1.5x/scale-method and
             sampler variants, and a provider without the hook);
  segs       MaskToSEGS -> SEGSPreview over masks (one rectangle, two soft blobs, a half-size mask), alpha_mode,
             min_alpha and with/without fallback image; the output images and the preview files' RGBA pixels.
Writes /results/impact_ned_r1.json; exits 1 on any failed check.
"""

import asyncio
import glob
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
NODE_IDS = ("DenoiseScheduleHookProvider", "PixelKSampleUpscalerProvider", "IterativeLatentUpscale",
            "IterativeImageUpscale", "MaskToSEGS", "SEGSPreview")
LATENT_TOLERANCE = 1.0 / 255


def pack_head() -> Path:
    if (ROOT / "v2").is_dir():
        return ROOT
    return [d for d in sorted(ROOT.iterdir()) if d.is_dir() and not d.name.startswith(".")][0]


# ---------------------------------------------------------------- prompts (the same on both sides)
def iterative_prompt(variant):
    hook = variant.get("hook", True)
    prompt = {
        "m": {"class_type": "NedTinyModel", "inputs": {}},
        "c": {"class_type": "NedTinyConditioning", "inputs": {}},
        "photo": {"class_type": "NedImage", "inputs": {"width": 96, "height": 64, "seed": 5}},
        "encoded": {"class_type": "VAEEncode", "inputs": {"pixels": ["photo", 0], "vae": ["m", 1]}},
        "21": {"class_type": "PixelKSampleUpscalerProvider", "inputs": {
            "scale_method": variant.get("scale_method", "bilinear"), "model": ["m", 0], "vae": ["m", 1],
            "seed": 20261102, "steps": variant.get("sample_steps", 2), "cfg": 2.0,
            "sampler_name": variant.get("sampler", "euler"), "scheduler": variant.get("scheduler", "normal"),
            "positive": ["c", 0], "negative": ["c", 1], "denoise": 0.35, "use_tiled_vae": False, "tile_size": 512}},
        "22": {"class_type": "IterativeLatentUpscale", "inputs": {
            "samples": ["encoded", 0], "upscale_factor": variant.get("factor", 2.0), "steps": variant.get("steps", 2),
            "temp_prefix": "", "upscaler": ["21", 0], "step_mode": variant.get("step_mode", "simple"),
            "vae_compression": 8}},
        "23": {"class_type": "IterativeImageUpscale", "inputs": {
            "pixels": ["photo", 0], "upscale_factor": variant.get("factor", 2.0), "steps": variant.get("steps", 2),
            "temp_prefix": "", "upscaler": ["21", 0], "vae": ["m", 1], "step_mode": variant.get("step_mode", "simple"),
            "vae_compression": 8}},
        "cap_latent": {"class_type": "NedCapture", "inputs": {"value": ["22", 0], "key": "latent"}},
        "cap_image": {"class_type": "NedCapture", "inputs": {"value": ["23", 0], "key": "image"}},
    }
    if hook:
        prompt["20"] = {"class_type": "DenoiseScheduleHookProvider",
                        "inputs": {"schedule_for_iteration": "simple", "target_denoise": 0.6}}
        prompt["21"]["inputs"]["pk_hook_opt"] = ["20", 0]
    return prompt


ITERATIVE = {
    "case (hook, simple, 2 steps, x2, bilinear)": {},
    "no hook": {"hook": False},
    "geometric, 3 steps, x2": {"step_mode": "geometric", "steps": 3},
    "simple, 3 steps, x1.5, nearest-exact": {"steps": 3, "factor": 1.5, "scale_method": "nearest-exact"},
    "simple, 1 step, x2, lanczos": {"steps": 1, "scale_method": "lanczos"},
    "simple, 2 steps, x2, area": {"scale_method": "area"},
    "uni_pc sampler, 4 sampling steps": {"sampler": "uni_pc", "sample_steps": 4},
    "dpmpp_2m sampler, karras, 3 sampling steps": {"sampler": "dpmpp_2m", "scheduler": "karras", "sample_steps": 3},
}


def segs_prompt(variant):
    prompt = {
        "photo": {"class_type": "NedImage", "inputs": {"width": 192, "height": 128, "seed": 11}},
        "mask": {"class_type": "NedMask", "inputs": {"kind": variant["mask"]}},
        "segs": {"class_type": "MaskToSEGS", "inputs": {
            "mask": ["mask", 0], "combined": variant.get("combined", True), "crop_factor": variant.get("crop", 1.0),
            "bbox_fill": False, "drop_size": 1, "contour_fill": False}},
        "20": {"class_type": "SEGSPreview", "inputs": {
            "segs": ["segs", 0], "alpha_mode": variant.get("alpha", True), "min_alpha": variant.get("min_alpha", 0.1)}},
        "cap": {"class_type": "NedCapture", "inputs": {"value": ["20", 0], "key": "images"}},
    }
    if variant.get("fallback", True):
        prompt["20"]["inputs"]["fallback_image_opt"] = ["photo", 0]
    return prompt


SEGS = {
    "case (rectangle, combined, crop 1.0, alpha, min 0.1)": {"mask": "rect"},
    "rectangle, alpha off": {"mask": "rect", "alpha": False},
    "two soft blobs, separate, crop 1.5, min 0.5": {"mask": "soft2", "combined": False, "crop": 1.5,
                                                    "min_alpha": 0.5},
    "two soft blobs, separate, min 0": {"mask": "soft2", "combined": False, "min_alpha": 0.0},
    "half-size mask (scale match), crop 1.2": {"mask": "half", "combined": False, "crop": 1.2},
    "no fallback image": {"mask": "rect", "fallback": False},
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

    class NedMask:
        RETURN_TYPES = ("MASK",)
        FUNCTION = "make"
        CATEGORY = "ned/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"kind": ("STRING", {"default": "rect"})}}

        def make(self, kind):
            if kind == "half":
                mask = torch.zeros((1, 64, 96))
                mask[:, 10:30, 12:40] = 1.0
                mask[:, 36:58, 50:88] = 0.6
                return (mask,)
            mask = torch.zeros((1, 128, 192))
            if kind == "rect":  # the reported case: a 64x48 solid mask added at (32, 24)
                mask[:, 24:72, 32:96] = 1.0
            elif kind == "soft2":
                mask[:, 10:50, 12:70] = 0.75
                mask[:, 60:110, 100:170] = 1.0
                mask[:, 70:90, 120:140] = 0.3
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

    for cls in (NedTinyModel, NedTinyConditioning, NedImage, NedMask, NedCapture):
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
    """Captured outputs as nested lists of tensors / plain values, for both sides alike."""
    import torch

    if isinstance(value, torch.Tensor):
        return value.detach().cpu().contiguous()
    if isinstance(value, dict) and "samples" in value:
        return {"samples": value["samples"].detach().cpu().contiguous()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def preview_pixels(ui, folders):
    """The pixels of every preview file a node reported, as stored (v2's previews are lossless PNG)."""
    import numpy as np
    from PIL import Image

    out = []
    for entry in (ui or {}).get("images", []):
        base = folders[entry.get("type", "output")]
        with Image.open(Path(base) / entry.get("subfolder", "") / entry["filename"]) as image:
            out.append({"mode": image.mode, "size": list(image.size), "type": entry.get("type"),
                        "pixels": np.asarray(image).copy()})
    return out


# The original side records each preview image as handed to PIL's WebP encoder (lossy), so v2's lossless previews
# are compared with exactly what the original encodes.
ORIGINAL_PREVIEWS = []


def record_original_previews():
    import numpy as np
    from PIL import Image

    original_save = Image.Image.save

    def recording_save(self, fp, *args, **kwargs):
        if str(fp).endswith(".webp"):
            ORIGINAL_PREVIEWS.append({"mode": self.mode, "size": list(self.size), "type": "temp",
                                      "pixels": np.asarray(self).copy()})
        return original_save(self, fp, *args, **kwargs)

    Image.Image.save = recording_save


async def run_side(label, mappings, execution, core_nodes, folder_paths):
    """Run every prompt with the given Impact classes; returns {case: outcome}."""
    captured = {}
    register_test_nodes(core_nodes, captured)
    saved = {k: core_nodes.NODE_CLASS_MAPPINGS.get(k) for k in mappings}
    core_nodes.NODE_CLASS_MAPPINGS.update(mappings)
    results = {}
    folders = {"temp": folder_paths.get_temp_directory(), "output": folder_paths.get_output_directory()}
    try:
        for group, cases, builder in (("iterative", ITERATIVE, iterative_prompt), ("segs", SEGS, segs_prompt)):
            for index, (name, variant) in enumerate(cases.items()):
                captured.clear()
                ORIGINAL_PREVIEWS.clear()
                try:
                    ok, errors, outputs = await run_prompt(execution, builder(variant), f"{label}-{group}-{index}")
                    previews = []
                    if group == "segs":
                        previews = (list(ORIGINAL_PREVIEWS) if label == "orig"
                                    else preview_pixels(outputs.get("20"), folders))
                    results[f"{group}: {name}"] = {
                        "ok": ok, "errors": [str(e.get("exception_message"))[:500] for e in errors],
                        "captured": {k: to_plain(v) for k, v in captured.items()},
                        "previews": previews,
                        "preview_ui": len(((outputs.get("20") or {}).get("images")) or []),
                    }
                except Exception:  # noqa: BLE001
                    results[f"{group}: {name}"] = {"ok": False, "errors": [traceback.format_exc()[-1500:]],
                                                   "captured": {}, "previews": []}
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
        path = Path(f"/tmp/ned-{tag}-{name}")
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        setter(str(path))
    return execution, core_nodes, folder_paths


# ---------------------------------------------------------------- the original side (a subprocess)
def original_main(out_path):
    sys.path.insert(0, str(DEPS / "_orig_only"))
    sys.path.insert(0, str(DEPS))
    execution, core_nodes, folder_paths = prepare_core("orig")
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
    record_original_previews()
    root = Path("/tmp/orig-impact")
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(pack_head(), root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    sys.path.insert(0, str(root / "modules"))
    import impact.config  # noqa: F401  (upstream __init__ order)
    import impact.impact_server  # noqa: F401
    import impact.impact_pack as impact_pack
    import impact.segs_nodes as segs_nodes

    mappings = {
        "DenoiseScheduleHookProvider": impact_pack.DenoiseScheduleHookProvider,
        "PixelKSampleUpscalerProvider": impact_pack.PixelKSampleUpscalerProvider,
        "IterativeLatentUpscale": impact_pack.IterativeLatentUpscale,
        "IterativeImageUpscale": impact_pack.IterativeImageUpscale,
        "MaskToSEGS": segs_nodes.MaskToSEGS if hasattr(segs_nodes, "MaskToSEGS") else impact_pack.MaskToSEGS,
        "SEGSPreview": segs_nodes.SEGSPreview,
    }
    import _tiny_sd
    from safetensors.torch import save_file

    digests = {"model": _tiny_sd.state_dict_digest(_tiny_sd.build_model()),
               "vae": _tiny_sd.state_dict_digest(_tiny_sd.build_vae())}
    results = asyncio.run(run_side("orig", mappings, execution, core_nodes, folder_paths))
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
    snap = Path("/tmp/impact-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(head, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    # A git snapshot drops empty folders; the manifest's declared asset folders must exist to load.
    manifest = json.loads((snap / PACK_FOLDER / "v2" / "secure-nodes.json").read_text())
    for relative in (manifest.get("asset_directories") or {}).values():
        (snap / PACK_FOLDER / "v2" / relative).mkdir(parents=True, exist_ok=True)
    loaded = packdb.load_pack(snap, mount_name="custom_nodes.impact_ned_r1", pack_id="comfyui-impact-pack/x429d015")
    for folder, directory in loaded.asset_directories.items():
        folder_paths.add_model_folder_path(folder, str(directory))
    mappings = {node_id: loaded.node_mappings[node_id] for node_id in NODE_IDS}
    # The manifest rows' permissions are the guest classes' own SDK_PERMISSIONS.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "impact_v2_rows", head / "v2" / "__init__.py", submodule_search_locations=[str(head / "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["impact_v2_rows"] = package
    spec.loader.exec_module(package)
    permissions = {node_id: [list(package.NODE_CLASS_MAPPINGS[node_id].SDK_PERMISSIONS),
                             manifest["nodes"][node_id]["permissions"]] for node_id in NODE_IDS}

    class ProfileGuestSession(GuestSession):
        """The guest sees the pack's dependency profile (DEPS top level, never _orig_only), as a guest with
        the profile installed does."""

        def _adjust_guest_env(self, env):
            super()._adjust_guest_env(env)
            if DEPS.is_dir():
                env["PYTHONPATH"] = os.pathsep.join(p for p in (str(DEPS), env.get("PYTHONPATH", "")) if p)

        def _extra_ro_paths(self):
            return list(super()._extra_ro_paths()) + ([str(DEPS)] if DEPS.is_dir() else [])

    session = await ProfileGuestSession("impact-ned").start()

    class Backend:
        async def dispatch(self, plan, local_call, runtime=None):
            if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                return await local_call()
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="impact-ned")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    try:
        loop_results = await run_side("v2", mappings, execution, core_nodes, folder_paths)
    finally:
        _sdk.providers.register_execution_backend(previous)
        pid = session.last_guest_pid
        await session.kill()
    digests = {"model": _tiny_sd.state_dict_digest(_tiny_sd.build_model()),
               "vae": _tiny_sd.state_dict_digest(_tiny_sd.build_vae())}
    return loop_results, digests, pid, permissions


# ---------------------------------------------------------------- comparison
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def compare_values(a, b, path="value"):
    """(verdict, detail): EXACT, WITHIN_TOLERANCE (max abs <= 1/255) or MISMATCH."""
    import torch

    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
            return "MISMATCH", f"{path}: {type(a).__name__} vs {type(b).__name__}"
        if a.shape != b.shape or a.dtype != b.dtype:
            return "MISMATCH", f"{path}: {a.dtype}{tuple(a.shape)} vs {b.dtype}{tuple(b.shape)}"
        if torch.equal(a, b):
            return "EXACT", None
        worst = float((a.double() - b.double()).abs().max())
        return ("WITHIN_TOLERANCE" if worst <= LATENT_TOLERANCE else "MISMATCH"), f"{path}: max abs {worst:.6g}"
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return "MISMATCH", f"{path}: keys {sorted(a)} vs {sorted(b)}"
        worst = ("EXACT", None)
        for key in a:
            verdict = compare_values(a[key], b[key], f"{path}.{key}")
            if verdict[0] != "EXACT":
                worst = verdict if verdict[0] == "MISMATCH" or worst[0] == "EXACT" else worst
        return worst
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return "MISMATCH", f"{path}: {len(a)} vs {len(b)} items"
        worst = ("EXACT", None)
        for index, (x, y) in enumerate(zip(a, b)):
            verdict = compare_values(x, y, f"{path}[{index}]")
            if verdict[0] != "EXACT":
                worst = verdict if verdict[0] == "MISMATCH" or worst[0] == "EXACT" else worst
        return worst
    return ("EXACT" if a == b else "MISMATCH"), f"{path}: {a!r} vs {b!r}"


def compare_previews(a, b):
    """The original's pre-encode preview images vs v2's stored previews: same count, mode, size, folder type
    and exactly the same bytes."""
    import numpy as np

    if len(a) != len(b):
        return False, f"{len(a)} vs {len(b)} previews"
    for index, (x, y) in enumerate(zip(a, b)):
        if x["mode"] != y["mode"] or list(x["size"]) != list(y["size"]) or x["type"] != y["type"]:
            return False, (f"preview {index}: {x['type']} {x['mode']} {x['size']} vs "
                           f"{y['type']} {y['mode']} {y['size']}")
        if not np.array_equal(np.asarray(x["pixels"]), np.asarray(y["pixels"])):
            diff = np.abs(np.asarray(x["pixels"]).astype(int) - np.asarray(y["pixels"]).astype(int)).max()
            return False, f"preview {index}: max abs {diff} (0-255)"
    return True, None


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "--original":
        original_main(sys.argv[2])
        return 0
    facts = {}
    try:
        from safetensors.torch import load_file

        out = "/tmp/impact-ned-original"
        completed = subprocess.run([sys.executable, __file__, "--original", out], capture_output=True, text=True,
                                   timeout=1800)
        (RESULTS / "side-original.log").write_text(completed.stdout[-200000:] + "\n" + completed.stderr[-200000:])
        if completed.returncode != 0 or not Path(out + ".json").is_file():
            raise RuntimeError(f"original side failed: {completed.stderr[-3000:]}")
        original = unpack_results(json.loads(Path(out + ".json").read_text()), load_file(out + ".safetensors"))
        v2_results, v2_digests, pid, permissions = asyncio.run(v2_side())
        facts["guest_pid"] = pid
        record("guest: out-of-process", pid not in (None, os.getpid()), pid)
        record("manifest: each node's permissions == its class's SDK_PERMISSIONS",
               all(a == b for a, b in permissions.values()), permissions)
        record("tiny model and VAE are byte-identical on both sides", original["digests"] == v2_digests,
               (original["digests"], v2_digests))
        for case, want in original["results"].items():
            got = v2_results.get(case, {"ok": False, "errors": ["missing"], "captured": {}, "previews": []})
            if not want["ok"]:
                # The original fails this prompt itself; v2 must fail it the same way.
                same = (not got["ok"]) and bool(want["errors"]) and bool(got["errors"]) and all(
                    a.strip().splitlines()[-1] in b for a, b in zip(want["errors"], got["errors"]))
                record(f"{case}: fails like the original", same, {"original": want["errors"], "v2": got["errors"]})
                continue
            record(f"{case}: v2 runs", got["ok"], got["errors"])
            if not got["ok"]:
                continue
            verdict, detail = compare_values(want["captured"], got["captured"], "outputs")
            facts[case] = verdict if verdict == "EXACT" else f"{verdict}: {detail}"
            record(f"{case}: outputs == the original's ({verdict})", verdict in ("EXACT", "WITHIN_TOLERANCE"), detail)
            if case.startswith("segs"):
                ok, detail = compare_previews(want["previews"], got["previews"])
                record(f"{case}: preview files == the original's (RGBA pixels)", ok, detail)
    except Exception:  # noqa: BLE001
        record("session", False, traceback.format_exc()[-3000:])
    failed = [c["check"] for c in checks if not c["ok"]]
    result = {"pack": "comfyui-impact-pack", "repair": "NED r1 (iterative upscale + denoise hook, SEGSPreview)",
              "checks": checks, "failed": failed, "facts": facts, "verdict": "PASS" if not failed else "FAIL"}
    (RESULTS / "impact_ned_r1.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed[:40]}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
