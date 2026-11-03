"""mikey_nodes (pin a5aa9cf637c4): tier-1 parity in the lane gate, original vs Secure Nodes V2.

run_in_gate.sh <pack root mikey_nodes-HEAD (pristine + v2/)> <v2/tests> <results> test_mikey_nodes_parity.py

Original: the pristine mikey_nodes.py under Core (comfy_extras.nodes_model_merging loaded first, as ComfyUI does).
v2: the converted classes with a fake SDK context. Both sides run every converted node on generated cases and
synthetic fixtures (a seeded image, wildcard files, a small checkpoint file, a synthetic workflow for %Node.widget%
replacement) with the clock frozen at the same instant. Compared exactly: strings, numbers (float.hex), tensors
(bytes), saved PNG files (bytes, names and folders), error type and message.

Engine boundary: the engine samples, encodes, decodes, loads checkpoints and runs upscale models in V2. Both sides
use the same deterministic stand-ins for those: VAE encode (8x8 pool), decode (8x nearest), a seeded sampler that
reads every sampling argument, an upscale model (2x nearest plus a fixed tint) and a checkpoint loader returning
tagged objects. The v2 side writes PNGs the engine's way (comfy_api _png_text_metadata, PIL PNG, compress_level,
optimize off, no overwrite) and lists/tests output files with the engine's own _InProcessAssets.
"""
import asyncio
import datetime as _real_datetime
import glob
import hashlib
import importlib.abc
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import types
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter("ignore")
PACK = "/pack"
RESULTS = "/results"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
for _index, _path in enumerate((BASE, "/core", "/overlay")):
    sys.path.insert(_index, _path)
os.environ.setdefault("HOME", "/tmp")
FROZEN = _real_datetime.datetime(2026, 11, 3, 4, 5, 6)
FX = "/tmp/fx"
WILDCARDS = {
    "colors.txt": b"red\ngreen\nblue\nyellow\n",
    "animals.txt": b"cat\ndog with a red hat\nbird\n",
    "nested.txt": b"__colors__ __animals__\n{big|small} __colors__\n",
    "sub/places.txt": b"forest\r\ncity\r\nbeach\r\n",
    "notes.md": b"not a wildcard\n",
}
EXTRA_PNGINFO = {"workflow": {"nodes": [{"id": 5, "properties": {"Node name for S&R": "KSampler"}},
                                        {"id": 9, "properties": {"Node name for S&R": "Saver"}}]},
                 "parameters": "Steps: 20, Sampler: euler été",
                 "extra": {"note": "café", "n": 3}}
PROMPT = {"5": {"inputs": {"seed": 123456, "steps": 20, "sampler_name": "euler"}},
          "9": {"inputs": {"filename_text_1": "x"}}, "12": {"inputs": {}}}


class FrozenDateTime(_real_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fromtimestamp(FROZEN.timestamp(), tz) if tz else cls(*FROZEN.timetuple()[:6])


FROZEN_MODULE = types.SimpleNamespace(datetime=FrozenDateTime, date=_real_datetime.date, timedelta=_real_datetime.timedelta)


def write_fixtures():
    for name, data in WILDCARDS.items():
        path = os.path.join(FX, "user", "wildcards", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
    os.makedirs(os.path.join(FX, "models", "checkpoints", "sdxl"), exist_ok=True)
    for name, size in (("fx.safetensors", 4096), ("sdxl/fx2.safetensors", 9000)):
        with open(os.path.join(FX, "models", "checkpoints", name), "wb") as handle:
            handle.write(hashlib.sha256(name.encode()).digest() * (size // 32))


def image(seed, h, w, batch=1):
    import torch
    g = torch.Generator().manual_seed(seed)
    return torch.floor(torch.rand((batch, h, w, 3), generator=g) * 255.0) / 255.0


# ---------------------------------------------------------------- the engine stand-ins (same on both sides)
def stub_encode(pixels):
    import torch
    x = pixels[..., :3].movedim(-1, 1).float()
    h8, w8 = (x.shape[2] // 8) * 8, (x.shape[3] // 8) * 8
    x = x[:, :, :h8, :w8]
    lat = torch.nn.functional.avg_pool2d(x, 8)
    return torch.cat([lat, lat.mean(1, keepdim=True)], 1)


def stub_decode(samples):
    import torch
    return torch.nn.functional.interpolate(samples[:, :3].float(), scale_factor=8, mode="nearest").movedim(1, -1).clamp(0, 1)


def stub_sample(samples, model, seed, steps, cfg, sampler_name, scheduler, positive, start_step, last_step, force_full):
    import torch
    g = torch.Generator().manual_seed(int(seed) % (1 << 63))
    noise = torch.randn(samples.shape, generator=g)
    start = 0 if start_step is None else int(start_step)
    last = int(steps) if last_step is None else min(int(last_step), int(steps))
    share = max(0, last - start) / max(1, int(steps))
    k = share * (0.5 + 0.01 * float(cfg)) * (0.9 if force_full else 1.0) * (0.8 if sampler_name != "euler" else 1.0)
    k *= 0.95 if scheduler != "normal" else 1.0
    tag = float(sum(ord(c) for c in str(model))) % 7 / 100.0 + float(positive[0][0].mean())
    return samples * (1 - k) + (0.1 * noise + tag) * k


def stub_upscale(image_value, name):
    import torch
    out = torch.nn.functional.interpolate(image_value.movedim(-1, 1), scale_factor=2, mode="nearest").movedim(1, -1)
    return (out * 0.9 + (len(name) % 5) / 50.0).clamp(0, 1)


def conditioning(sign):
    import torch
    return [[torch.full((1, 4, 8), 0.2 * sign), {"pooled_output": torch.zeros((1, 8))}]]


# ---------------------------------------------------------------- cases
def cases():
    out = []
    for value in (0, 7, 1234567, 2 ** 63 - 1, 0xffffffffffffffff):
        for commas in ("true", "false"):
            out.append({"node": "Int to String", "args": {"int_": value, "use_commas": commas}})
    for start, end, step, seed in ((0, 10, 1, 3), (5, 50, 5, 123), (0, 0, 1, 0), (3, 100, 7, 2 ** 40), (0, 10, 0, 1),
                                   (10, 0, 1, 5)):
        out.append({"node": "Range Integer", "args": {"start": start, "end": end, "step": step, "seed": seed}})
    for seed in (0, 42, 0xffffffffffffffff):
        out.append({"node": "Seed String", "args": {"seed": seed}})
    for delimiter in (" ", ", ", ""):
        out.append({"node": "TextConcat", "args": {"delimiter": delimiter, "text1": "a", "text2": "", "text3": "c",
                                                    "text4": "d e", "text5": ""}})
    out.append({"node": "TextConcat", "args": {"delimiter": "-", "text1": "a"}})
    for text, start, end in (("<think>hidden</think> shown", "<think>", "</think>"),
                             ("a <think>x</think> b <think>y</think> c", "<think>", "</think>"),
                             ("no tags here", "<think>", "</think>"), ("[[a]] keep [[b\nc]]", "[[", "]]")):
        out.append({"node": "RemoveTextBetween", "args": {"text": text, "start": start, "end": end}})
    for node in ("FileNamePrefix", "FileNamePrefixDateDirFirst"):
        for date in ("true", "false"):
            for date_directory in ("true", "false"):
                for custom_directory, custom_text in (("", ""), ("run_%KSampler.seed%", "img:%KSampler.steps%?"),
                                                      ("%date:yyyy-MM-dd%", "x/y\\z")):
                    out.append({"node": node, "args": {"date": date, "date_directory": date_directory,
                                                       "custom_directory": custom_directory, "custom_text": custom_text}})
    for h, w in ((64, 96), (128, 128), (40, 200)):
        for tile in (8, 64, 512):
            out.append({"node": "Upscale Tile Calculator", "args": {"image": ["img", 1, h, w], "tile_resolution": tile}})
        for method in ("nearest-exact", "bilinear", "area", "bicubic"):
            for crop in ("disabled", "center"):
                out.append({"node": "Resize Image for SDXL", "args": {"image": ["img", 2, h, w],
                                                                     "upscale_method": method, "crop": crop}})
    for ratio in ("1:1 [1024x1024 square]", "16:9 [1344x768 landscape]", "2:3 [832x1216 portrait]"):
        for batch in (1, 3):
            out.append({"node": "Empty Latent Ratio Select SDXL", "args": {"ratio_selected": ratio, "batch_size": batch}})
    prompts = ["plain text", "{red|green|blue} car", "a <random:0.5:1.5> b", "__colors__ house", "__2$$colors__",
               "__colors|blue|red__ and __animals|red__", "__nested__", "__sub/places__ __!colors__ __colors__",
               "__+colors__ __-colors__ __*colors__ __colors__", "%KSampler.seed% __missing__ x",
               "%date:yyyyMMdd-hhmmss% __animals__"]
    for text in prompts:
        for seed in (0, 1, 987654321):
            out.append({"node": "Wildcard Processor", "args": {"prompt": text, "seed": seed}})
            out.append({"node": "WildcardOobaPrompt", "args": {"input_prompt": text, "seed": seed}})
    for text in ("x <llm:prompt:describe a cat> y",):
        out.append({"node": "WildcardOobaPrompt", "designed": "llm refused", "args": {"input_prompt": text, "seed": 3}})
    for name in ("fx.safetensors", "sdxl/fx2.safetensors"):
        out.append({"node": "Checkpoint Loader Simple Mikey", "args": {"ckpt_name": name}})
    # The tiler needs an upscaled image larger than the tile (upstream divides by zero otherwise: the last case).
    for denoise, tile, upscale_by, optional, size, sampler in (
            (1.0, 256, 1.0, False, (320, 448), "euler"), (0.5, 256, 1.5, False, (320, 448), "dpmpp_2m"),
            (0.3, 512, 1.0, True, (640, 768), "euler"), (0.75, 256, 1.0, True, (320, 448), "euler"),
            (0.0, 256, 1.0, False, (320, 448), "euler"), (1.0, 256, 1.0, False, (96, 128), "euler")):
        out.append({"node": "MikeySamplerTiledAdvancedBaseOnly", "size": list(size),
                    "args": {"seed": 7, "model_name": "fx_upscaler.pth", "denoise_image": denoise, "steps": 6,
                             "cfg": 5.5, "sampler_name": sampler, "scheduler": "normal", "upscale_by": upscale_by,
                             "tiler_denoise": 0.4, "tile_size": tile, "image_optional": optional}})
    base = {"sub_directory": "", "filename_text_1": "Filename Text 1", "filename_text_2": "Filename Text 2",
            "filename_text_3": "Filename Text 3", "filename_separator": "_", "timestamp": "true",
            "counter_type": "folder", "filename_text_1_pos": 0, "filename_text_2_pos": 2, "filename_text_3_pos": 4,
            "timestamp_pos": 1, "timestamp_type": "save_time", "counter_pos": 3, "extra_metadata": "Extra Metadata"}
    variants = [
        {},
        {"counter_type": "filename", "filename_text_1": "cat", "filename_text_2": "%KSampler.seed%"},
        {"counter_type": "none", "timestamp": "true", "batch": 2},
        {"counter_type": "folder", "sub_directory": "run_%KSampler.seed%/deep", "batch": 2},
        {"timestamp": "false", "timestamp_type": "job", "filename_separator": "-", "extra_metadata": ""},
        {"filename_text_1_pos": 1},  # duplicate positions
        {"filename_text_1": "x" * 150, "filename_text_2": "y" * 40},
        {"sub_directory": "a<b>c|d?e*f", "filename_text_3": "q:w\"e"},
        # the counter scan stops at the first unparsable name, so this case keeps the listing order irrelevant
        {"existing": ["Filename Text 1_20261103040506_Filename Text 2_00007_Filename Text 3.png", "other.png"]},
        {"existing": ["cat_x_1.png"], "counter_type": "filename", "filename_text_1": "cat"},
    ]
    for node in ("Save Images Mikey", "Save Images No Display"):
        for i, variant in enumerate(variants):
            args = {**base, **{k: v for k, v in variant.items() if k not in ("batch", "existing")}}
            out.append({"node": node, "case": i, "batch": variant.get("batch", 1), "existing": variant.get("existing", []),
                        "args": args})
    out.append({"node": "Save Images Mikey", "case": "collision", "designed": "no overwrite", "batch": 1,
                "existing": ["plain.png"], "args": {**base, "counter_type": "none", "timestamp": "false",
                                                    "filename_text_1": "plain", "filename_text_2": "",
                                                    "filename_text_3": "", "extra_metadata": ""}})
    out.append({"node": "Batch Load Images", "designed": "refused", "args": {"image_directory": "/tmp/anything",
                                                                            "subdirectories": "false"}})
    return out


def digest(value):
    import numpy as np
    import torch
    if isinstance(value, torch.Tensor):
        value = value.detach().cpu()
        return ["tensor", list(value.shape), str(value.dtype), hashlib.sha256(value.contiguous().numpy().tobytes()).hexdigest()]
    if isinstance(value, dict) and "samples" in value:
        return {"latent": digest(value["samples"]), "keys": sorted(value)}
    if isinstance(value, (np.integer,)):
        return ["int", int(value)]
    if isinstance(value, float):
        return ["float", value.hex()]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, (list, tuple)):
        return [digest(v) for v in value]
    return value


def outcome(fn):
    try:
        return ["value", fn()]
    except Exception as exc:
        return ["error", type(exc).__name__, str(exc)]


def output_tree(root):
    found = {}
    for d, _dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            found[os.path.relpath(p, root).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return found


def prepare_output(root, case):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)
    for name in case.get("existing", []):
        target = os.path.join(root, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(b"existing")


# ---------------------------------------------------------------- original side
class StubVae:
    def __repr__(self):
        return "vae"


def run_original(plan, out_path):
    import torch
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import comfy.sd  # mikey_nodes calls comfy.sd.load_checkpoint_guess_config; replaced below by the stand-in
    import folder_paths
    import importlib as _importlib
    _importlib.import_module("comfy_extras.nodes_model_merging")
    write_fixtures()
    folder_paths.set_user_directory(os.path.join(FX, "user"))
    folder_paths.set_temp_directory("/tmp/orig-temp")
    os.makedirs("/tmp/orig-temp", exist_ok=True)
    folder_paths.folder_names_and_paths["checkpoints"] = ([os.path.join(FX, "models", "checkpoints")], {".safetensors"})
    root = "/tmp/orig-mikey"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2", "__pycache__", ".git"))
    spec = importlib.util.spec_from_file_location("orig_mikey", os.path.join(root, "__init__.py"),
                                                  submodule_search_locations=[root])
    package = importlib.util.module_from_spec(spec)
    sys.modules["orig_mikey"] = package
    spec.loader.exec_module(package)
    mk = sys.modules["orig_mikey.mikey_nodes"]
    mk.datetime = FROZEN_MODULE
    calls = []

    def common_ksampler(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent, denoise=1.0,
                        disable_noise=False, start_step=None, last_step=None, force_full_denoise=False):
        calls.append([seed, steps, start_step, last_step, force_full_denoise, denoise, disable_noise])
        out = latent.copy()
        out["samples"] = stub_sample(latent["samples"], model, seed, steps, cfg, sampler_name, scheduler, positive,
                                     start_step, last_step, force_full_denoise)
        return (out,)

    class VAEEncode:
        def encode(self, vae, pixels):
            return ({"samples": stub_encode(pixels)},)

    class VAEDecode:
        def decode(self, vae, samples):
            return (stub_decode(samples["samples"]),)

    class UpscaleModelLoader:
        def load_model(self, model_name):
            return (types.SimpleNamespace(name=model_name),)

    class ImageUpscaleWithModel:
        def upscale(self, upscale_model, image):
            return (stub_upscale(image, upscale_model.name),)

    mk.common_ksampler, mk.VAEEncode, mk.VAEDecode = common_ksampler, VAEEncode, VAEDecode
    mk.UpscaleModelLoader, mk.ImageUpscaleWithModel = UpscaleModelLoader, ImageUpscaleWithModel
    mk.comfy.sd.load_checkpoint_guess_config = lambda path, **_k: ("model:" + os.path.basename(path), "clip", "vae", None)
    classes = mk.NODE_CLASS_MAPPINGS
    records = []
    for case in plan:
        node, args = case["node"], dict(case["args"])
        if case.get("designed"):
            records.append(["designed", case["designed"]])
            continue

        def run():
            cls = classes[node]
            obj = cls()
            if node in ("Upscale Tile Calculator", "Resize Image for SDXL"):
                _tag, seed, h, w = args["image"]
                args["image"] = image(seed, h, w)
            if node == "Empty Latent Ratio Select SDXL":
                cls.INPUT_TYPES()
            if node in ("Wildcard Processor",):
                return digest(obj.process(args["prompt"], args["seed"], prompt_=json.loads(json.dumps(PROMPT)),
                                          extra_pnginfo=json.loads(json.dumps(EXTRA_PNGINFO))))
            if node == "WildcardOobaPrompt":
                random.seed(4242)
                return digest(obj.process(args["input_prompt"], args["seed"], prompt=json.loads(json.dumps(PROMPT)),
                                          unique_id="12", extra_pnginfo=json.loads(json.dumps(EXTRA_PNGINFO))))
            if node in ("FileNamePrefix", "FileNamePrefixDateDirFirst"):
                return digest(obj.get_filename_prefix(**args, prompt=PROMPT, extra_pnginfo=EXTRA_PNGINFO))
            if node == "Checkpoint Loader Simple Mikey":
                return digest(obj.load_checkpoint(args["ckpt_name"]))
            if node == "MikeySamplerTiledAdvancedBaseOnly":
                calls.clear()
                h, w = case["size"]
                latent = {"samples": stub_encode(image(11, h, w))}
                optional = image(12, h, w) if args.pop("image_optional") else None
                result = obj.run(base_model="base", vae=StubVae(), samples=latent,
                                 positive_cond_base=conditioning(1), negative_cond_base=conditioning(-1),
                                 image_optional=optional, **args)
                return {"out": digest(result), "calls": calls[:]}
            if node in ("Save Images Mikey", "Save Images No Display"):
                folder = "/tmp/orig-out"
                prepare_output(folder, case)
                obj.output_dir = folder
                imgs = image(21, 48, 64, case["batch"])
                method = obj.save_images if node == "Save Images Mikey" else obj.save_images_no_display
                result = method(imgs, **args, prompt=json.loads(json.dumps(PROMPT)),
                                extra_pnginfo=json.loads(json.dumps(EXTRA_PNGINFO)))
                files = output_tree(folder)
                for name in case.get("existing", []):
                    files.pop(name, None)
                return {"result": result, "files": files}
            method = getattr(obj, cls.FUNCTION)
            return digest(method(**args))
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
        if frame is not None and not frame.f_code.co_filename.startswith("/pack/"):
            return None
        self.blocked.add(fullname)
        raise ModuleNotFoundError(f"blocked in guest emulation: {fullname}", name=fullname)


class FakeRef:
    def __init__(self, value):
        self.value = value

    async def raw(self):
        return self.value


class FakeImageRef(FakeRef):
    @classmethod
    async def from_value(cls, value):
        return cls(value)


class FakeLatentRef(FakeRef):
    @classmethod
    async def from_value(cls, value):
        return cls(value)


class FakeVae:
    def __repr__(self):
        return "vae"

    async def encode(self, image_ref):
        return FakeLatentRef({"samples": stub_encode(image_ref.value)})

    async def decode(self, latent_ref):
        return FakeImageRef(stub_decode(latent_ref.value["samples"]))


class FakeUpscaleModel:
    def __init__(self, name):
        self.name = name

    async def upscale(self, images):
        return FakeImageRef(stub_upscale(images.value, self.name))


def run_v2(plan, out_path):
    import torch
    write_fixtures()
    finder = GuestImports(GUEST_BASE | {"mikey_v2"})
    sys.meta_path.insert(0, finder)
    v2 = os.path.join(PACK, "v2")
    spec = importlib.util.spec_from_file_location("mikey_v2", os.path.join(v2, "__init__.py"),
                                                  submodule_search_locations=[v2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["mikey_v2"] = package
    spec.loader.exec_module(package)
    used = sys.modules["mikey_v2._secure_used"]
    upstream = sys.modules["mikey_v2._mikey_upstream"]
    sys.meta_path.remove(finder)  # the stand-ins below use Core's own helpers (the engine side)
    import folder_paths
    from comfy_api.latest import _sdk as engine_sdk
    from comfy_api.latest import sdk as public_sdk
    from PIL import Image as PILImage
    import numpy as np
    wire_spec = importlib.util.spec_from_file_location("overlay_wire", "/overlay/comfy_secure_nodes/transport/wire.py")
    wire = importlib.util.module_from_spec(wire_spec)
    wire_spec.loader.exec_module(wire)
    upstream.datetime = FROZEN_MODULE
    used.datetime = FROZEN_MODULE
    out_root = "/tmp/v2-out"
    folder_paths.set_output_directory(out_root)
    folder_paths.folder_names_and_paths["checkpoints"] = ([os.path.join(FX, "models", "checkpoints")], {".safetensors"})
    engine_assets = engine_sdk._InProcessAssets()
    state = {"kind": True, "calls": []}

    class Assets:
        async def list(self, folder, prefix="", recursive=True):
            if folder == "mikey_wildcards":
                if not state["kind"]:
                    raise ValueError("unknown asset kind 'mikey_wildcards'")
                return sorted(WILDCARDS)
            return await engine_assets.list(folder, prefix=prefix, recursive=recursive)

        async def resolve(self, folder, name):
            if folder == "mikey_wildcards":
                return ("wildcard", name)
            if folder == "checkpoints":
                return ("checkpoint", name)
            raise AssertionError(folder)

        async def read_bytes(self, ref):
            return WILDCARDS[ref[1]]

        async def exists(self, folder, name):
            return await engine_assets.exists(folder, name)

        async def digest(self, ref, algorithm="sha256"):
            assert algorithm == "sha256"
            return hashlib.sha256(open(os.path.join(FX, "models", "checkpoints", ref[1]), "rb").read()).hexdigest()

    class Output:
        async def save_images(self, images, filenames=None, compress_level=4, save_metadata=True, png_text=None, **extra):
            assert not extra and not save_metadata and png_text is not None and len(filenames) == images.value.shape[0]
            results = []
            for value, logical in zip(images.value, filenames):
                target, _logical, file, subfolder = engine_sdk._InProcessOutput._logical_output_target(
                    out_root, logical, frozenset({".png"}))
                if os.path.lexists(target):
                    raise FileExistsError("an exact output image already exists")
                rendered = PILImage.fromarray(np.clip(255.0 * value.detach().cpu().numpy(), 0, 255).astype(np.uint8))
                with open(target, "xb") as stream:
                    rendered.save(stream, format="PNG", pnginfo=engine_sdk._png_text_metadata(png_text),
                                  optimize=False, compress_level=int(compress_level))
                results.append({"filename": file, "subfolder": subfolder, "type": "output"})
            return {"images": results}

    class Models:
        async def load_checkpoint(self, name):
            return ("model:" + os.path.basename(name), "clip", "vae")

        async def load_upscale_model(self, name):
            return FakeUpscaleModel(name)

    class Context:
        assets, output, models = Assets(), Output(), Models()

        async def sample(self, *, latent, steps, model, positive, negative, cfg, seed, sampler_name, scheduler,
                         denoise=1.0, force_full_denoise=False, start_step=None, last_step=None, disable_noise=False):
            state["calls"].append([seed, steps, start_step, last_step, force_full_denoise, denoise, disable_noise])
            value = dict(latent.value)
            value["samples"] = stub_sample(value["samples"], model, seed, steps, cfg, sampler_name, scheduler, positive,
                                           start_step, last_step, force_full_denoise)
            return FakeLatentRef(value)

    context = Context()
    used.sdk = types.SimpleNamespace(ctx=lambda: context, ImageRef=FakeImageRef, LatentRef=FakeLatentRef)

    def through_wire(value):
        def refs(v):
            if isinstance(v, torch.Tensor):
                return public_sdk.ImageRef(kind="IMAGE", id="t")
            if isinstance(v, (FakeImageRef, FakeLatentRef)):
                return public_sdk.ImageRef(kind="IMAGE", id="t")
            if isinstance(v, (list, tuple)):
                return [refs(x) for x in v]
            if isinstance(v, dict):
                return {k: refs(x) for k, x in v.items()}
            return v
        return wire.decode(json.loads(json.dumps(wire.encode(refs(value)))))

    def unref(value):
        if isinstance(value, FakeLatentRef):
            return value.value
        if isinstance(value, FakeImageRef):
            return value.value
        return value

    records, wire_failures = [], []
    for index, case in enumerate(plan):
        node, args = case["node"], dict(case["args"])
        cls = used.NODE_CLASS_MAPPINGS[node]
        cls.hidden = types.SimpleNamespace(prompt=json.loads(json.dumps(PROMPT)),
                                           extra_pnginfo=json.loads(json.dumps(EXTRA_PNGINFO)), unique_id="12")
        state["kind"] = True

        def run():
            if node == "Batch Load Images":
                return ["validate", cls.validate_inputs(**args)]
            if node in ("Upscale Tile Calculator", "Resize Image for SDXL"):
                _tag, seed, h, w = args["image"]
                args["image"] = image(seed, h, w)
            if node == "WildcardOobaPrompt":
                random.seed(4242)
            if node == "MikeySamplerTiledAdvancedBaseOnly":
                state["calls"].clear()
                h, w = case["size"]
                optional = FakeImageRef(image(12, h, w)) if args.pop("image_optional") else None
                result = asyncio.run(cls.execute(base_model="base", vae=FakeVae(),
                                                 samples=FakeLatentRef({"samples": stub_encode(image(11, h, w))}),
                                                 positive_cond_base=conditioning(1),
                                                 negative_cond_base=conditioning(-1), image_optional=optional, **args))
                outputs = tuple(unref(v) for v in result.args)
                through_wire(outputs)
                return {"out": digest(outputs), "calls": state["calls"][:]}
            if node in ("Save Images Mikey", "Save Images No Display"):
                prepare_output(out_root, case)
                result = asyncio.run(cls.execute(FakeImageRef(image(21, 48, 64, case["batch"])), **args))
                files = output_tree(out_root)
                for name in case.get("existing", []):
                    files.pop(name, None)
                ui = result.ui if node == "Save Images Mikey" else None
                return {"result": {"ui": ui} if ui is not None else [None], "files": files}
            result = asyncio.run(cls.execute(**args))
            outputs = tuple(unref(v) for v in result.args)
            through_wire(outputs)
            return digest(outputs)
        try:
            records.append(outcome(run))
        except Exception as exc:
            records.append(["error", type(exc).__name__, str(exc)])
            wire_failures.append(index)
    # designed: the wildcard kind is missing on the host
    no_kind = []
    for text in ("plain {a|b} text", "__colors__ x"):
        cls = used.NODE_CLASS_MAPPINGS["Wildcard Processor"]
        state["kind"] = False
        no_kind.append([text, outcome(lambda: digest(tuple(asyncio.run(cls.execute(prompt=text, seed=1)).args)))])
    with open(out_path, "w") as handle:
        json.dump({"records": records, "wire_failures": wire_failures, "blocked_imports": sorted(finder.blocked),
                   "no_kind": no_kind}, handle)


def manifest_text():
    """secure-nodes.json from the v2 classes with the real encoder (comfy_secure_nodes.packmanifest, /overlay)."""
    import copy
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    from comfy_secure_nodes.packmanifest import FORMAT, encode_schema, encode_validation_inputs
    from comfy_secure_nodes.packruntime import manifest_declaration
    v2 = os.path.join(PACK, "v2")
    spec = importlib.util.spec_from_file_location("mikey_v2", os.path.join(v2, "__init__.py"),
                                                  submodule_search_locations=[v2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["mikey_v2"] = package
    spec.loader.exec_module(package)
    nodes = {}
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        row = {
            "class": cls.__name__,
            "methods": {name: name in cls.__dict__ for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
            "module": cls.__module__.removeprefix("mikey_v2."),
            "permissions": list(cls.SDK_PERMISSIONS),
            "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
            "sdk_refs": cls.SDK_REFS is True,
        }
        if "validate_inputs" in cls.__dict__:
            row["validation_inputs"] = encode_validation_inputs(cls)
        nodes[node_id] = row
    manifest = {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(v2)}
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main(argv):
    if argv[:1] == ["side"]:
        plan = json.load(open(argv[2]))
        return (run_original if argv[1] == "original" else run_v2)(plan, argv[3]) or 0
    if argv[:1] in (["generate-manifest"], ["manifest-only"]):
        text = manifest_text()
        out = os.path.join("/tmp" if argv[0] == "manifest-only" else RESULTS, "secure-nodes.json")
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"wrote {out}")
        return 0
    with open(os.path.join(RESULTS, "manifest-check.log"), "w") as log:
        subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), "manifest-only"], stdout=log,
                       stderr=subprocess.STDOUT, timeout=600, check=True)
    committed = os.path.join(PACK, "v2", "secure-nodes.json")
    manifest_equal = os.path.exists(committed) and open(committed, encoding="utf-8").read() == open(
        "/tmp/secure-nodes.json", encoding="utf-8").read()
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
    by_node, mismatches, designed = {}, [], []
    for case, want, got in zip(plan, original["records"], v2["records"]):
        row = by_node.setdefault(case["node"], {"cases": 0, "mismatches": 0, "errors": 0, "designed": 0})
        row["cases"] += 1
        if want[0] == "designed":
            row["designed"] += 1
            designed.append({"case": case, "v2": got})
            continue
        row["errors"] += want[0] == "error"
        if want != got:
            row["mismatches"] += 1
            mismatches.append({"case": case, "original": want, "v2": got})
    for row in by_node.values():
        row["verdict"] = "EXACT" if not row["mismatches"] else "MISMATCH"
    designed_ok = []
    for item in designed:
        kind, got = item["case"]["designed"], item["v2"]
        if kind == "llm refused":
            ok = got[0] == "error" and got[1] == "LlmSyntaxRefused" and "network" in got[2]
        elif kind == "no overwrite":
            ok = got[0] == "error" and got[1] == "FileExistsError" and "never overwrites" in got[2]
        else:
            ok = got[0] == "value" and isinstance(got[1][1], str) and "is not yet converted" in got[1][1]
        designed_ok.append({"designed": kind, "ok": ok, "v2": got})
    no_kind = v2["no_kind"]
    no_kind_ok = (no_kind[0][1][0] == "value" and no_kind[1][1][0] == "error"
                  and no_kind[1][1][1] == "WildcardsUnavailableError")
    unexpected = sorted(set(v2["blocked_imports"]) - {"accimage", "defusedxml"})
    want_probe, got_probe = next((w, g) for w, g in zip(original["records"], v2["records"])
                                 if w[0] == "value" and w == g and isinstance(w[1], list) and w[1])
    perturbed = json.loads(json.dumps(got_probe))
    perturbed[1][0] = ["perturbed", perturbed[1][0]]
    negative_red = perturbed != want_probe
    ok = (not mismatches and not v2["wire_failures"] and not unexpected and all(d["ok"] for d in designed_ok)
          and no_kind_ok and manifest_equal)
    parity = {"status": "PASS" if ok else "FAIL", "nodes": by_node, "designed": designed_ok,
              "manifest_equals_real_encoder": manifest_equal,
              "no_wildcard_kind": {"ok": no_kind_ok, "runs": no_kind}, "wire_failures": v2["wire_failures"],
              "guest_blocked_imports": v2["blocked_imports"], "guest_blocked_imports_unexpected": unexpected,
              "negative_control": {"perturbation": "one v2 record replaced", "turned_red": negative_red}}
    with open(os.path.join(RESULTS, "parity.json"), "w") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w") as handle:
        json.dump(mismatches[:40], handle, indent=1)
        handle.write("\n")
    print(json.dumps({k: parity[k] for k in ("status", "nodes", "wire_failures", "guest_blocked_imports_unexpected",
                                             "manifest_equals_real_encoder", "negative_control")}, indent=1))
    print(json.dumps({"designed": [[d["designed"], d["ok"]] for d in designed_ok], "no_kind_ok": no_kind_ok}))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
