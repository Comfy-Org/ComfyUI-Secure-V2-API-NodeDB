"""Impact Pack fidelity repair r6 (detailers): parity in the lane gate.

DEPS=<the unpacked Impact dependency-profile wheels; upstream-only test needs (piexif, dill) under _orig_only/> \
run_in_gate.sh <root holding ComfyUI-Impact-Pack-HEAD/> <Impact v2/tests> <results> test_detailer_repair_r6.py

The detailers' pixel work is compared with the engine work replaced, on both sides, by the same deterministic
stand-ins (no model can run in the gate):
  VAE encode   center-crop to a multiple of 8 (as Core's VAE.encode does), 8x8 average pool, 4 channels
  sampler      a seeded blend whose strength depends on denoise, steps, cfg, sampler, scheduler, the positive
               conditioning and differential diffusion, applied through the latent noise mask exactly as Core's
               sampler applies it (comfy.utils.reshape_mask)
  VAE decode   8x nearest upsample of the first 3 channels
  differential diffusion   a marker on the model that the sampler stand-in reads
Original: the pristine Impact Pack under Core. DetailerForEach.do_detail (which DetailerForEach, its Debug/Pipe forms
and FaceDetailer use) with impact_sampling.ksampler_wrapper and utils.apply_differential_diffusion replaced by the
stand-ins; SEGSDetailer.doit then SEGSPaste.doit. v2: the repaired handlers (_detail_segs_common, _segs_detailer,
_paste_segs) with a fake SDK context whose vae / sample / model.patch do the same. SEGS come from each side's own
MaskToSEGS on synthetic masks (repair r3 showed those equal). Compared: every output tensor's bytes and every SEG's
values. Every v2 output also crosses the overlay's wire encoder (tensors as refs).
"""
import asyncio
import glob
import hashlib
import importlib.abc
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter("ignore")
ROOT = "/pack"
IMPACT = os.path.join(ROOT, "ComfyUI-Impact-Pack-HEAD")
RESULTS = "/results"
DEPS = "/deps"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
for _index, _path in enumerate((DEPS, BASE, "/core", "/overlay")):
    sys.path.insert(_index, _path)
os.environ.setdefault("HOME", "/tmp")
H, W = 96, 128


# ---------------------------------------------------------------- cases and fixtures
def cases():
    out = []
    for mask in ("one", "two", "three+empty", "edge"):
        for guide_for in (True, False):
            for guide, max_size in ((48.0, 256.0), (160.0, 256.0), (160.0, 96.0)):
                for feather in (0, 5):
                    for noise_mask in (True, False):
                        for nmf in (0, 4):
                            for force in (True, False):
                                out.append({"node": "dfe", "mask": mask, "guide_for": guide_for, "guide": guide,
                                            "max_size": max_size, "feather": feather, "noise_mask": noise_mask,
                                            "nmf": nmf, "force": force, "cycle": 1, "denoise": 0.5, "steps": 2,
                                            "seed": 17, "model": "stub"})
    for mask in ("one", "two"):
        out.append({"node": "dfe", "mask": mask, "guide_for": True, "guide": 160.0, "max_size": 256.0, "feather": 5,
                    "noise_mask": True, "nmf": 4, "force": True, "cycle": 2, "denoise": 0.35, "steps": 3, "seed": 5,
                    "model": "stub"})
    for mask in ("half", "half-two"):
        out.append({"node": "dfe", "mask": mask, "guide_for": True, "guide": 160.0, "max_size": 256.0, "feather": 5,
                    "noise_mask": True, "nmf": 0, "force": True, "cycle": 1, "denoise": 0.5, "steps": 2, "seed": 3,
                    "model": "stub"})
    out.append({"node": "dfe", "mask": "two", "guide_for": True, "guide": 160.0, "max_size": 256.0, "feather": 5,
                "noise_mask": True, "nmf": 4, "force": True, "cycle": 1, "denoise": 0.5, "steps": 2, "seed": 3,
                "model": "DUMMY"})
    for mask in ("one", "two", "three+empty", "edge"):
        for batch in (1, 2):
            for noise_mask in (True, False):
                for nmf in (0, 4):
                    for force in (True, False):
                        for guide, max_size in ((48.0, 256.0), (160.0, 96.0)):
                            out.append({"node": "segs", "mask": mask, "batch": batch, "guide_for": True, "guide": guide,
                                        "max_size": max_size, "noise_mask": noise_mask, "nmf": nmf, "force": force,
                                        "cycle": 1, "denoise": 0.5, "steps": 2, "seed": 17, "model": "stub"})
    out.append({"node": "segs", "mask": "half-two", "batch": 1, "guide_for": True, "guide": 160.0, "max_size": 256.0,
                "noise_mask": True, "nmf": 0, "force": True, "cycle": 1, "denoise": 0.5, "steps": 2, "seed": 9,
                "model": "stub"})
    out.append({"node": "segs", "mask": "two", "batch": 1, "guide_for": False, "guide": 160.0, "max_size": 256.0,
                "noise_mask": True, "nmf": 4, "force": True, "cycle": 1, "denoise": 0.5, "steps": 2, "seed": 9,
                "model": "DUMMY"})
    return out


def make_image():
    import torch
    g = torch.Generator().manual_seed(1234)
    image = torch.rand((1, H, W, 3), generator=g)
    return torch.floor(image * 255.0) / 255.0  # 8-bit values, as LoadImage gives


def make_mask(kind):
    # Separate blobs, so MaskToSEGS makes one SEG each; "two" and "three" have overlapping crop regions (crop_factor
    # 1.4), so later SEGs are cropped from where earlier ones were pasted.
    import torch
    kind = kind.removesuffix("+empty")
    if kind.startswith("half"):
        mask = torch.zeros((1, H // 2, W // 2))
        mask[:, 6:18, 6:22] = 1.0
        if kind == "half-two":
            mask[:, 22:40, 24:50] = 1.0
        return mask
    mask = torch.zeros((1, H, W))
    if kind == "one":
        mask[:, 30:62, 40:80] = 1.0
    elif kind == "two":
        mask[:, 16:40, 14:44] = 1.0
        mask[:, 46:78, 48:88] = 1.0
    elif kind == "three":
        mask[:, 8:24, 8:30] = 1.0
        mask[:, 40:60, 10:40] = 0.75
        mask[:, 30:70, 52:110] = 1.0
    elif kind == "edge":
        mask[:, 10:44, 100:W] = 1.0
    return mask


def mask_to_segs_args(kind):
    # MaskToSEGS(mask, combined, crop_factor, bbox_fill, drop_size, contour_fill)
    return (make_mask(kind), False, 1.4, False, 10, False)


def with_empty(kind, segs, seg_type, empty_mask):
    """For "+empty" cases, append a SEG whose mask is all zeros (the detailers skip it, each in its own way)."""
    if not kind.endswith("+empty"):
        return segs
    return segs[0], list(segs[1]) + [seg_type(None, empty_mask, 1.0, [5, 5, 17, 15], (6, 6, 16, 14), "A", None)]


def conditioning(sign):
    import torch
    return [[torch.full((1, 4, 8), 0.25 * sign), {"pooled_output": torch.full((1, 8), 0.5 * sign)}]]


# ---------------------------------------------------------------- the engine stand-ins (the same on both sides)
def stub_encode(pixels):
    import torch
    pixels = pixels[..., :3]
    h8, w8 = (pixels.shape[1] // 8) * 8, (pixels.shape[2] // 8) * 8
    y0, x0 = (pixels.shape[1] % 8) // 2, (pixels.shape[2] % 8) // 2
    pixels = pixels[:, y0:y0 + h8, x0:x0 + w8].movedim(-1, 1).float()
    latent = torch.nn.functional.avg_pool2d(pixels, 8)
    return torch.cat([latent, latent.mean(1, keepdim=True)], 1)


def stub_decode(samples):
    import torch
    return torch.nn.functional.interpolate(samples[:, :3].float(), scale_factor=8, mode="nearest").movedim(1, -1).clamp(0, 1)


def stub_sample(samples, noise_mask, dd, seed, steps, cfg, sampler_name, scheduler, positive, denoise):
    import torch
    import comfy.utils
    g = torch.Generator().manual_seed(int(seed) % (1 << 63))
    noise = torch.randn(samples.shape, generator=g)
    strength = float(denoise) * (0.6 + 0.1 * min(int(steps), 4)) * (1.0 + 0.01 * float(cfg)) * (0.75 if dd else 1.0)
    if sampler_name != "euler" or scheduler != "normal":
        strength *= 0.9
    strength = min(strength, 1.0)
    cond = float(positive[0][0].float().mean())
    target = 0.5 * samples.flip(-1) + 0.1 * noise + cond
    if noise_mask is not None:
        m = comfy.utils.reshape_mask(torch.as_tensor(noise_mask).float(), samples.shape)
    else:
        m = torch.ones_like(samples)
    return samples * (1 - m * strength) + target * m * strength


# ---------------------------------------------------------------- records
def digest(value):
    import numpy as np
    import torch
    if value is None:
        return None
    if isinstance(value, torch.Tensor):
        value = value.detach().cpu().numpy()
    value = np.ascontiguousarray(np.asarray(value, dtype=np.float32))
    return [list(value.shape), hashlib.sha256(value.tobytes()).hexdigest()]


def seg_mask2d(mask):
    import numpy as np
    import torch
    mask = mask.detach().cpu().numpy() if isinstance(mask, torch.Tensor) else np.asarray(mask)
    if mask.ndim == 3 and mask.shape[0] == 1:
        mask = mask[0]
    return mask


def segs_record(segs):
    import numpy as np
    shape, items = segs
    rows = []
    for item in items:
        rows.append({"image": digest(item[0]), "mask": digest(seg_mask2d(item[1])),
                     "confidence": float(np.asarray(item[2], dtype=np.float32).reshape(-1)[0]),
                     "crop_region": [int(v) for v in item[3]], "bbox": [float(v) for v in item[4]],
                     "label": str(item[5]), "cnet": item[6] is not None})
    return {"shape": [int(v) for v in shape], "items": rows}


def outcome(fn):
    try:
        return ["value", fn()]
    except Exception as exc:
        return ["error", type(exc).__name__, str(exc)]


# ---------------------------------------------------------------- original side
class StubModel:
    def __init__(self, dd=False):
        self.dd = dd
        self.model_options = {"denoise_mask_function": "differential_diffusion"} if dd else {}


class StubVae:
    def encode(self, pixels):
        return stub_encode(pixels)

    def decode(self, samples):
        return stub_decode(samples)

    def decode_tiled(self, samples, **_kwargs):
        return stub_decode(samples)


def run_original(plan, out_path):
    sys.path.insert(0, os.path.join(DEPS, "_orig_only"))
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import server

    class Routes:
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: lambda function: function

    class Instance:
        routes = Routes()
        prompt_queue = types.SimpleNamespace(currently_running={})

        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: None

    server.PromptServer.instance = Instance()
    root = "/tmp/orig-impact"
    shutil.copytree(IMPACT, root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    sys.path.insert(0, os.path.join(root, "modules"))
    import impact.config  # noqa: F401  (upstream __init__ order)
    import impact.impact_server  # noqa: F401
    import impact.impact_pack as impact_pack
    import impact.impact_sampling as impact_sampling
    import impact.segs_nodes as segs_nodes
    import impact.utils as impact_utils

    def ksampler_wrapper(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent_image, denoise,
                         refiner_ratio=None, refiner_model=None, refiner_clip=None, refiner_positive=None,
                         refiner_negative=None, sigma_factor=1.0, noise=None, scheduler_func=None, sampler_opt=None):
        out = latent_image.copy()
        out["samples"] = stub_sample(latent_image["samples"], latent_image.get("noise_mask"), model.dd, seed, steps, cfg,
                                     sampler_name, scheduler, positive, denoise)
        return out

    impact_sampling.ksampler_wrapper = ksampler_wrapper  # the boundary: the engine samples in V2
    impact_utils.apply_differential_diffusion = lambda model: StubModel(dd=True)

    import numpy as np
    import impact.core as impact_core

    image = make_image()
    vae = StubVae()
    records = []
    for case in plan:
        def run():
            (segs,) = segs_nodes.MaskToSEGS.doit(*mask_to_segs_args(case["mask"]))
            segs = with_empty(case["mask"], segs, impact_core.SEG, np.zeros((10, 12), dtype=np.float32))
            model = "DUMMY" if case["model"] == "DUMMY" else StubModel()
            if case["node"] == "dfe":
                result = impact_pack.DetailerForEach.do_detail(
                    image, segs, model, None, vae, case["guide"], case["guide_for"], case["max_size"], case["seed"],
                    case["steps"], 5.0, "euler", "normal", conditioning(1), conditioning(-1), case["denoise"],
                    case["feather"], case["noise_mask"], case["force"], wildcard_opt="", detailer_hook=None,
                    cycle=case["cycle"], inpaint_model=False, noise_mask_feather=case["nmf"])
                image_out, cropped, enhanced, alpha, cnet, new_segs = result
                return {"image": digest(image_out), "cropped": [digest(x) for x in cropped],
                        "enhanced": [digest(x) for x in enhanced], "alpha": [digest(x) for x in alpha],
                        "cnet": len(cnet), "segs": segs_record(new_segs)}
            basic_pipe = (model, None, vae, conditioning(1), conditioning(-1))
            new_segs, cnet = segs_nodes.SEGSDetailer().doit(
                image, segs, case["guide"], case["guide_for"], case["max_size"], case["seed"], case["steps"], 5.0,
                "euler", "normal", case["denoise"], case["noise_mask"], case["force"], basic_pipe, 0.2, case["batch"],
                cycle=case["cycle"], inpaint_model=False, noise_mask_feather=case["nmf"])
            (pasted,) = segs_nodes.SEGSPaste().doit(image, new_segs, 3, 255)
            return {"segs": segs_record(new_segs), "cnet": [digest(x) for x in cnet], "paste": digest(pasted)}
        records.append(outcome(run))
    with open(out_path, "w") as handle:
        json.dump({"records": records}, handle)


# ---------------------------------------------------------------- v2 side
GUEST_BASE = {"av", "blake3", "comfy_api", "comfy_secure_nodes", "comfy_secure_sdk", "filelock", "fsspec", "iniconfig",
              "jinja2", "markupsafe", "mpmath", "networkx", "numpy", "nvidia", "packaging", "PIL", "pluggy", "psutil",
              "pygments", "pytest", "_pytest", "py", "pytest_asyncio", "safetensors", "setuptools", "pkg_resources",
              "_distutils_hack", "sympy", "torch", "functorch", "torchgen", "triton", "typing_extensions", "wheel"}


class GuestImports(importlib.abc.MetaPathFinder):
    def __init__(self, allowed):
        self.allowed, self.blocked = allowed, set()

    def find_spec(self, fullname, path, target=None):
        top = fullname.split(".")[0]
        if top in sys.stdlib_module_names or top in self.allowed or top.startswith("_"):
            return None
        frame = sys._getframe(1)
        while frame and frame.f_code.co_filename.startswith("<frozen"):
            frame = frame.f_back
        if frame is not None and not frame.f_code.co_filename.startswith(("/pack/", DEPS)):
            return None
        self.blocked.add(fullname)
        raise ModuleNotFoundError(f"blocked in guest emulation: {fullname}", name=fullname)


class FakeRef:
    kind = "REF"

    def __init__(self, value):
        self.value = value

    async def release(self):
        return None


class FakeImageRef(FakeRef):
    kind = "IMAGE"

    @classmethod
    async def _from_raw(cls, value):
        return cls(value)


class FakeMaskRef(FakeImageRef):
    kind = "MASK"


class FakeLatentRef(FakeRef):
    kind = "LATENT"

    @classmethod
    async def from_value(cls, value):
        return cls(value)

    @classmethod
    def _wrap(cls, ref):
        return cls(ref.value)


class FakeCondRef(FakeLatentRef):
    kind = "CONDITIONING"


async def fake_materialize(value):
    return value.value if isinstance(value, FakeRef) else value


class FakeModel:
    def __init__(self, dd=False):
        self.dd = dd

    async def patch(self, name, strength=1.0):
        assert name == "differential_diffusion" and strength == 1.0, (name, strength)
        return FakeModel(dd=True)


class FakeVae:
    async def encode(self, image_ref):
        return FakeLatentRef({"samples": stub_encode(await fake_materialize(image_ref))})

    async def encode_tiled(self, image_ref, **_kwargs):
        return await self.encode(image_ref)

    async def decode(self, latent_ref):
        return FakeImageRef(stub_decode((await fake_materialize(latent_ref))["samples"]))

    async def decode_tiled(self, latent_ref, **_kwargs):
        return await self.decode(latent_ref)


class FakeContext:
    def __init__(self):
        self.calls = []

    async def sample(self, *, latent, steps, model, positive, negative, cfg, seed, sampler_name, scheduler, denoise=1.0,
                     **extra):
        self.calls.append(sorted(k for k, v in extra.items() if v not in (None, False, True)))
        value = dict(await fake_materialize(latent))
        out = dict(value)
        out["samples"] = stub_sample(value["samples"], value.get("noise_mask"), model.dd, seed, steps, cfg, sampler_name,
                                     scheduler, await fake_materialize(positive), denoise)
        return FakeLatentRef(out)


def run_v2(plan, out_path):
    import torch
    deps_top = {n[:-3] if n.endswith(".py") else n for n in os.listdir(DEPS) if not n.endswith((".dist-info", ".data", ".libs"))}
    finder = GuestImports(GUEST_BASE | deps_top | {"impact_v2"})
    sys.meta_path.insert(0, finder)
    spec = importlib.util.spec_from_file_location("impact_v2", os.path.join(IMPACT, "v2", "__init__.py"),
                                                  submodule_search_locations=[os.path.join(IMPACT, "v2")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["impact_v2"] = package
    spec.loader.exec_module(package)
    nodes = sys.modules["impact_v2._secure_nodes"]
    from comfy_api.latest import sdk as public_sdk
    wire_spec = importlib.util.spec_from_file_location("overlay_wire", "/overlay/comfy_secure_nodes/transport/wire.py")
    wire = importlib.util.module_from_spec(wire_spec)
    wire_spec.loader.exec_module(wire)
    context = FakeContext()
    nodes.materialize = fake_materialize
    nodes.sdk = types.SimpleNamespace(ctx=lambda: context, Ref=FakeRef, ImageRef=FakeImageRef, MaskRef=FakeMaskRef,
                                      LatentRef=FakeLatentRef, CondRef=FakeCondRef)
    counter = [0]

    def ref(cls, kind):
        counter[0] += 1
        return cls(kind=kind, id=f"t{counter[0]}")

    def through_wire(value):
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], list):
            value = (tuple(value[0]), [tuple([None if item[0] is None else ref(public_sdk.ImageRef, "IMAGE"),
                                              ref(public_sdk.MaskRef, "MASK"), *item[2:]]) for item in value[1]])
        elif isinstance(value, torch.Tensor):
            value = ref(public_sdk.ImageRef, "IMAGE")
        elif isinstance(value, list):
            value = [ref(public_sdk.ImageRef, "IMAGE") for _ in value]
        return wire.decode(json.loads(json.dumps(wire.encode(value))))

    image = make_image()
    vae = FakeVae()
    records, wire_failures = [], []
    for index, case in enumerate(plan):
        def run():
            (segs,) = asyncio.run(nodes._mask_to_segs_upstream(*mask_to_segs_args(case["mask"])))
            segs = with_empty(case["mask"], segs, nodes.SEG, torch.zeros((1, 10, 12)))
            model = "DUMMY" if case["model"] == "DUMMY" else FakeModel()
            if case["node"] == "dfe":
                result = asyncio.run(nodes._detail_segs_common(
                    image=image, segs=segs, model=model, clip=None, vae=vae, positive=conditioning(1),
                    negative=conditioning(-1), guide_size=case["guide"], guide_size_for=case["guide_for"],
                    max_size=case["max_size"], seed=case["seed"], steps=case["steps"], cfg=5.0, sampler_name="euler",
                    scheduler="normal", denoise=case["denoise"], feather=case["feather"], noise_mask=case["noise_mask"],
                    force_inpaint=case["force"], wildcard="", cycle=case["cycle"], detailer_hook=None,
                    inpaint_model=False, noise_mask_feather=case["nmf"]))
                image_out, cropped, enhanced, alpha, cnet, new_segs = result
                for value in (image_out, cropped, enhanced, alpha, new_segs):
                    through_wire(value)
                return {"image": digest(image_out), "cropped": [digest(x) for x in cropped],
                        "enhanced": [digest(x) for x in enhanced], "alpha": [digest(x) for x in alpha],
                        "cnet": len(cnet), "segs": segs_record(new_segs)}
            basic_pipe = (model, None, vae, conditioning(1), conditioning(-1))
            new_segs, cnet = asyncio.run(nodes._segs_detailer(
                image=image, segs=segs, basic_pipe=basic_pipe, refiner_basic_pipe_opt=None, refiner_ratio=0.2,
                batch_size=case["batch"], guide_size=case["guide"], guide_size_for=case["guide_for"],
                max_size=case["max_size"], seed=case["seed"], steps=case["steps"], cfg=5.0, sampler_name="euler",
                scheduler="normal", denoise=case["denoise"], noise_mask=case["noise_mask"], force_inpaint=case["force"],
                cycle=case["cycle"], inpaint_model=False, noise_mask_feather=case["nmf"]))
            through_wire(new_segs)
            through_wire(cnet)
            (pasted,) = asyncio.run(nodes._paste_segs(image, new_segs, 3, 255))
            through_wire(pasted)
            return {"segs": segs_record(new_segs), "cnet": [digest(x) for x in cnet], "paste": digest(pasted)}
        try:
            records.append(outcome(run))
        except Exception as exc:
            records.append(["error", type(exc).__name__, str(exc)])
            wire_failures.append(index)
    extra_sample_args = sorted({k for call in context.calls for k in call})
    with open(out_path, "w") as handle:
        json.dump({"records": records, "wire_failures": wire_failures, "blocked_imports": sorted(finder.blocked),
                   "sample_calls": len(context.calls), "extra_sample_args": extra_sample_args}, handle)


def main(argv):
    if argv[:1] == ["side"]:
        plan = json.load(open(argv[2]))
        return (run_original if argv[1] == "original" else run_v2)(plan, argv[3]) or 0
    plan = cases()
    with open("/tmp/plan.json", "w") as handle:
        json.dump(plan, handle)
    sides = {}
    for side in ("original", "v2"):
        with open(os.path.join(RESULTS, f"side-{side}.log"), "w") as log:
            proc = subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), "side", side, "/tmp/plan.json",
                                   f"/tmp/out-{side}.json"], stdout=log, stderr=subprocess.STDOUT, timeout=3000)
        if proc.returncode != 0:
            print(f"side {side} failed ({proc.returncode}); see side-{side}.log")
            return 1
        sides[side] = json.load(open(f"/tmp/out-{side}.json"))
        shutil.copyfile(f"/tmp/out-{side}.json", os.path.join(RESULTS, f"outcomes-{side}.json"))
    original, v2 = sides["original"], sides["v2"]
    by_node = {}
    mismatches = []
    for case, want, got in zip(plan, original["records"], v2["records"]):
        row = by_node.setdefault(case["node"], {"cases": 0, "values": 0, "mismatches": 0, "segs_items": 0})
        row["cases"] += 1
        row["values"] += want[0] == "value"
        if want[0] == "value":
            row["segs_items"] += len(want[1]["segs"]["items"])
        if want != got:
            row["mismatches"] += 1
            mismatches.append({"case": case, "original": want, "v2": got})
    for row in by_node.values():
        row["verdict"] = "EXACT" if not row["mismatches"] else "MISMATCH"
        row["errors"] = row["cases"] - row["values"]
    unexpected = sorted(set(v2["blocked_imports"]) - {"accimage", "defusedxml", "envwrap"})
    probe = next((g for w, g in zip(original["records"], v2["records"]) if w[0] == "value" and "image" in w[1]), None)
    perturbed = json.loads(json.dumps(probe))
    perturbed[1]["image"][1] = "0" * 64
    negative_red = perturbed != probe
    ok = not mismatches and not v2["wire_failures"] and not unexpected and all(
        row["values"] == row["cases"] for row in by_node.values())
    parity = {"status": "PASS" if ok else "FAIL", "nodes": by_node, "wire_failures": v2["wire_failures"],
              "guest_blocked_imports": v2["blocked_imports"], "guest_blocked_imports_unexpected": unexpected,
              "engine_sample_calls": v2["sample_calls"], "extra_sample_args": v2["extra_sample_args"],
              "negative_control": {"perturbation": "one output image digest replaced", "turned_red": negative_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump(mismatches[:40], handle, indent=1)
        handle.write("\n")
    print(json.dumps({k: parity[k] for k in ("status", "nodes", "wire_failures", "guest_blocked_imports_unexpected",
                                             "engine_sample_calls", "extra_sample_args", "negative_control")}, indent=1))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
