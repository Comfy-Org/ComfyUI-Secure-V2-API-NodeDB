"""comfy_mtb: the converted V2 nodes against the original, side by side (tier-1 parity, gate).

    DEPS=<folder holding _orig_only/ (scikit-image 0.25.2, lazy_loader 0.4)> \
        run_in_gate.sh <snapshot dir, or the pack folder> <.../v2/tests> <results> test_comfy_mtb_parity.py

Original side: the pristine pack's own modules (nodes/graph_utils.py, number.py, image_utils.py, image_processing.py,
crop.py, model.py, video.py and the root utils.py / log.py they import), imported in this process as a package. The
pack's __init__.py is not run (it registers server routes). image_processing.py imports scikit-image at import;
it comes from /deps/_orig_only, on this process's path only.
V2 side: the proxies packdb builds from secure-nodes.json, called through Core's execution functions; every node body
runs in a real guest process (GuestSession, started with the production guest patch fixr1_compat applied, see
_mtb_sealed_guest_entry.py), which never sees /deps.

Per converted node, generated cases (defaults, options, edges, seeded tensors, errors) compare exactly: tensors by
dtype, shape and bytes; numbers by type and float.hex; strings; None; errors by type and message. Cases where V2
refuses by name (documented known differences) are checked to differ in exactly that way. The schemas the proxies
serve are compared with the original classes' INPUT_TYPES and outputs. Negative control: a one-element change in a
V2 output is caught. Writes /results/parity.json; exits 1 on any failed check.
"""

import asyncio
import importlib
import io as _bytes_io
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
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK = "comfy-mtb"
PACK_FOLDER = "comfy_mtb-HEAD"
KEY = "xb35b5d8"
RESULTS = Path("/results")
DEPS_ORIG = Path("/deps/_orig_only")
ORIGINAL = {
    "Any To String (mtb)": ("graph_utils", "MTB_AnyToString"),
    "String Replace (mtb)": ("graph_utils", "MTB_StringReplace"),
    "Int To Number (mtb)": ("number", "MTB_IntToNumber"),
    "Pick From Batch (mtb)": ("image_utils", "MTB_PickFromBatch"),
    "Color Correct (mtb)": ("image_processing", "MTB_ColorCorrect"),
    "Image Compare (mtb)": ("image_processing", "MTB_ImageCompare"),
    "Sharpen (mtb)": ("image_processing", "MTB_Sharpen"),
    "Uncrop (mtb)": ("crop", "MTB_Uncrop"),
    "Vae Decode (mtb)": ("model", "MTB_VaeDecode"),
    "Load Image Sequence (mtb)": ("video", "MTB_LoadImageSequence"),
}
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:2000]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:500]}"), flush=True)


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    return next(d for d in sorted(root.iterdir()) if (d / "v2").is_dir())


def snapshot_dir() -> Path:
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/mtb-snapshot") / PACK / KEY
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    return snap


def original_classes(head: Path) -> dict:
    """The pristine modules, as the package `_mtb_orig` (its __init__.py is not run)."""
    sys.path.insert(0, str(DEPS_ORIG))
    package = types.ModuleType("_mtb_orig")
    package.__path__ = [str(head)]
    package.__package__ = "_mtb_orig"
    sys.modules["_mtb_orig"] = package
    out = {}
    for node_id, (module, cls) in ORIGINAL.items():
        out[node_id] = getattr(importlib.import_module(f"_mtb_orig.nodes.{module}"), cls)
    sys.path.remove(str(DEPS_ORIG))
    return out


# ---------------------------------------------------------------- comparison
def same(a, b, path="value"):
    """None when a and b are exactly equal, else a description of the first difference."""
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
            return f"{path}: {type(a).__name__} vs {type(b).__name__}"
        if a.dtype != b.dtype or tuple(a.shape) != tuple(b.shape):
            return f"{path}: {a.dtype}{tuple(a.shape)} vs {b.dtype}{tuple(b.shape)}"
        ca, cb = a.detach().cpu().contiguous(), b.detach().cpu().contiguous()
        if torch.equal(ca, cb) or ca.numpy().tobytes() == cb.numpy().tobytes():
            return None
        diff = (ca.double() - cb.double()).abs()
        return f"{path}: values differ (max abs {float(diff.nan_to_num(0).max()):.3g})"
    if type(a) is not type(b):
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and type(a).__name__ == type(b).__name__:
            pass
        else:
            return f"{path}: {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, float):
        return None if a.hex() == b.hex() or (a != a and b != b) else f"{path}: {a!r} vs {b!r}"
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            problem = same(x, y, f"{path}[{i}]")
            if problem:
                return problem
        return None
    if isinstance(a, dict):
        if list(a) != list(b):
            return f"{path}: keys {list(a)} vs {list(b)}"
        for k in a:
            problem = same(a[k], b[k], f"{path}[{k!r}]")
            if problem:
                return problem
        return None
    return None if a == b else f"{path}: {a!r} vs {b!r}"


def error_of(error):
    kind = getattr(error, "remote_type", None) or type(error).__name__
    message = str(error)
    for prefix in (f"{kind}: ",):
        while message.startswith(prefix):
            message = message[len(prefix):]
    return kind, message.strip()


# ---------------------------------------------------------------- the two sides
async def run_original(cls, inputs):
    try:
        method = getattr(cls(), cls.FUNCTION)
        return {"ok": True, "value": tuple(method(**inputs))}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": error_of(error)}


async def run_v2(proxy, inputs, prompt_id):
    try:
        output, _ui, _sub, _pending = await execution.get_output_data(
            prompt_id, "1", proxy, {k: [v] for k, v in inputs.items()})
        return {"ok": True, "value": tuple(slot[0] for slot in output)}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": error_of(error)}


def verdict_of(orig, v2):
    if orig["ok"] != v2["ok"]:
        return "MISMATCH", {"original": orig.get("error") or "ok", "v2": v2.get("error") or "ok"}
    if not orig["ok"]:
        return ("EXACT" if orig["error"] == v2["error"] else "MISMATCH"), {"original": orig["error"],
                                                                           "v2": v2["error"]}
    problem = same(orig["value"], v2["value"])
    return ("EXACT", None) if problem is None else ("MISMATCH", problem)


# ---------------------------------------------------------------- cases
def g(seed):
    return torch.Generator().manual_seed(seed)


def cases(tiny_vae):
    img = torch.rand(2, 16, 16, 3, generator=g(1))
    batch5 = torch.rand(5, 16, 16, 3, generator=g(2))
    mask5 = torch.rand(5, 16, 16, generator=g(3))
    a = torch.rand(2, 24, 20, 3, generator=g(4))
    b = torch.rand(2, 24, 20, 3, generator=g(5))
    sharp = torch.rand(1, 20, 24, 3, generator=g(6))
    bg = torch.rand(1, 96, 80, 3, generator=g(7))
    fg = torch.rand(1, 32, 40, 3, generator=g(8))
    latent_small = {"samples": torch.randn(1, 4, 24, 20, generator=g(9))}
    latent_big = {"samples": torch.randn(1, 4, 72, 80, generator=g(10))}
    c = {}
    c["Any To String (mtb)"] = {
        "string": dict(input="hello"), "empty string": dict(input=""), "int": dict(input=42),
        "negative int": dict(input=-7), "float": dict(input=3.5), "bool": dict(input=True),
        "IMAGE tensor": dict(input=img), "float16 tensor": dict(input=img.half()),
        "LATENT dict": dict(input=latent_small), "list": dict(input=[1, 2, 3]),
    }
    c["String Replace (mtb)"] = {
        "plain": dict(string="a-b-c", old="-", new="+", use_regex=False),
        "regex": dict(string="a1b22c333", old=r"\d+", new="#", use_regex=True),
        "regex group": dict(string="abc", old="(b)", new=r"[\1]", use_regex=True),
        "invalid regex": dict(string="abc", old="(", new="x", use_regex=True),
        "empty old": dict(string="", old="", new="x", use_regex=False),
        "unicode": dict(string="café ☕", old="☕", new="tea", use_regex=False),
        "regex not plain": dict(string="a.b", old=".", new="-", use_regex=True),
    }
    c["Int To Number (mtb)"] = {"zero": dict(int=0), "negative": dict(int=-5), "max": dict(int=10 ** 9),
                                "beyond max (linked)": dict(int=2 ** 40)}
    c["Pick From Batch (mtb)"] = {}
    for direction in ("start", "end"):
        for count in (2, 9, -1) if direction == "start" else (2, 0, 9, -1):
            c["Pick From Batch (mtb)"][f"{direction} {count}"] = dict(image=batch5, from_direction=direction,
                                                                     count=count)
        c["Pick From Batch (mtb)"][f"{direction} 3 with mask"] = dict(image=batch5, from_direction=direction,
                                                                      count=3, mask=mask5)
    base = dict(image=img, clamp=True, gamma=1.0, contrast=1.0, exposure=0.0, offset=0.0, hue=0.0, saturation=1.0,
                value=1.0)
    c["Color Correct (mtb)"] = {"defaults": dict(base)}
    for name, change in (("gamma 0.5", {"gamma": 0.5}), ("gamma 2.2", {"gamma": 2.2}),
                         ("contrast 0.5", {"contrast": 0.5}), ("contrast 1.7", {"contrast": 1.7}),
                         ("exposure 1", {"exposure": 1.0}), ("exposure -1.5", {"exposure": -1.5}),
                         ("offset 0.1", {"offset": 0.1}), ("offset -0.2", {"offset": -0.2}),
                         ("hue 0.25", {"hue": 0.25}), ("hue -0.3", {"hue": -0.3}),
                         ("saturation 0", {"saturation": 0.0}), ("saturation 2", {"saturation": 2.0}),
                         ("value 0.5", {"value": 0.5}), ("value 1.5", {"value": 1.5}),
                         ("clamp off, exposure 1", {"clamp": False, "exposure": 1.0}),
                         ("everything", {"gamma": 1.3, "contrast": 1.2, "exposure": 0.3, "offset": -0.05,
                                         "hue": 0.1, "saturation": 1.4, "value": 0.9}),
                         ("mask (batch 1)", {"mask": (torch.rand(1, 16, 16, generator=g(11)) > 0.5).float()}),
                         ("mask (batch 2)", {"mask": torch.rand(2, 16, 16, generator=g(12)), "hue": 0.2}),
                         ("gamma 0 (division by zero)", {"gamma": 0.0}),
                         ("RGBA image", {"image": torch.rand(1, 8, 8, 4, generator=g(13))})):
        c["Color Correct (mtb)"][name] = {**base, **change}
    c["Image Compare (mtb)"] = {}
    for mode in ("checkerboard", "diff", "blend"):
        c["Image Compare (mtb)"][mode] = dict(imageA=a, imageB=b, mode=mode)
        c["Image Compare (mtb)"][f"{mode}, RGB vs RGBA"] = dict(
            imageA=a, imageB=torch.rand(2, 24, 20, 4, generator=g(14)), mode=mode)
        c["Image Compare (mtb)"][f"{mode}, sizes differ"] = dict(
            imageA=a, imageB=torch.rand(2, 20, 20, 3, generator=g(15)), mode=mode)
    c["Image Compare (mtb)"]["checkerboard 13x11 (not divisible by 8)"] = dict(
        imageA=torch.rand(1, 13, 11, 3, generator=g(16)), imageB=torch.rand(1, 13, 11, 3, generator=g(17)),
        mode="checkerboard")
    c["Sharpen (mtb)"] = {}
    for radius, sx, sy, alpha in ((1, 1.0, 1.0, 1.0), (2, 1.0, 1.0, 1.0), (5, 0.5, 2.0, 1.0), (3, 1.0, 1.0, 0.0),
                                  (2, 2.0, 2.0, 3.5), (15, 1.0, 1.0, 1.0), (31, 1.0, 1.0, 1.0)):
        c["Sharpen (mtb)"][f"r{radius} s{sx}/{sy} a{alpha}"] = dict(image=sharp, sharpen_radius=radius, sigma_x=sx,
                                                                   sigma_y=sy, alpha=alpha)
    c["Sharpen (mtb)"]["RGBA"] = dict(image=torch.rand(1, 12, 12, 4, generator=g(18)), sharpen_radius=2,
                                      sigma_x=1.0, sigma_y=1.0, alpha=1.0)
    c["Uncrop (mtb)"] = {}
    for name, bbox in (("bbox = crop size", (10, 12, 40, 32)), ("resize to bbox", (10, 12, 50, 30)),
                       ("negative x/y", (-8, -6, 40, 32)), ("past right/bottom", (60, 70, 40, 32)),
                       ("entirely outside", (200, 200, 40, 32))):
        for blend in (0.0, 0.25, 1.0):
            c["Uncrop (mtb)"][f"{name}, blend {blend}"] = dict(image=bg, crop_image=fg, bbox=bbox,
                                                              border_blending=blend)
    c["Uncrop (mtb)"]["bbox as a list"] = dict(image=bg, crop_image=fg, bbox=[10, 12, 40, 32], border_blending=0.25)
    c["Uncrop (mtb)"]["background batch 1, crops 3"] = dict(
        image=bg, crop_image=torch.rand(3, 32, 40, 3, generator=g(19)), bbox=(10, 12, 40, 32), border_blending=0.25)
    c["Uncrop (mtb)"]["batches 2 and 3 (error)"] = dict(
        image=torch.rand(2, 96, 80, 3, generator=g(20)), crop_image=torch.rand(3, 32, 40, 3, generator=g(21)),
        bbox=(10, 12, 40, 32), border_blending=0.25)
    c["Vae Decode (mtb)"] = {
        "plain decode": dict(vae=tiny_vae, samples=latent_small, seamless_model=False, use_tiling_decoder=False,
                             tile_size=512),
        "tiled 512": dict(vae=tiny_vae, samples=latent_big, seamless_model=False, use_tiling_decoder=True,
                          tile_size=512),
        "tiled 640": dict(vae=tiny_vae, samples=latent_big, seamless_model=False, use_tiling_decoder=True,
                          tile_size=640),
        "tiled 512, small latent": dict(vae=tiny_vae, samples=latent_small, seamless_model=False,
                                        use_tiling_decoder=True, tile_size=512),
    }
    c["Load Image Sequence (mtb)"] = {
        "RGB png, frame 3": dict(path="videos/####.png", current_frame=3, range=""),
        "RGBA png (mask), frame 4": dict(path="videos/####.png", current_frame=4, range=""),
        "grey png, frame 5": dict(path="videos/####.png", current_frame=5, range=""),
        "16-bit png, frame 6": dict(path="videos/####.png", current_frame=6, range=""),
        "jpeg with EXIF orientation": dict(path="clips/####.jpg", current_frame=12, range=""),
        "no # in path": dict(path="single.png", current_frame=0, range=""),
        "[output] annotation": dict(path="renders/##.png [output]", current_frame=7, range=""),
    }
    return c


# Cases where V2 refuses; each must differ in exactly this way. (what differs, what the original does: "ok" or the
# error type it raises, whether V2's message must be the pack's named refusal)
KNOWN = {
    ("Any To String (mtb)", "host object"): (
        "a live host object (here a torch module) cannot cross to the guest as a value; the runtime refuses it, where "
        "the original prints the object", "ok", False),
    ("Pick From Batch (mtb)", "start 0"): (
        "picking no images: the original returns an empty IMAGE batch, which V2 cannot pass on; refused by name",
        "ok", True),
    ("Vae Decode (mtb)", "tiled 320"): (
        "below tile_size 512 the host's tiled decode narrows the overlap; refused by name", "ok", True),
    ("Vae Decode (mtb)", "seamless"): (
        "seamless mode switches the shared host VAE to circular padding in place; refused by name", "ok", True),
    ("Load Image Sequence (mtb)", "absolute path"): (
        "both refuse an absolute path (Core's get_annotated_filepath, V2 by name)", "ValueError", True),
    ("Load Image Sequence (mtb)", "all frames (-1)"): (
        "the original globs relative to the server's working folder (here nothing matches); refused by name",
        "ValueError", True),
    ("Load Image Sequence (mtb)", "range"): ("as all frames; refused by name", "ValueError", True),
}


def known_cases(tiny_vae_factory):
    latent_big = {"samples": torch.randn(1, 4, 72, 80, generator=g(10))}
    return {
        ("Any To String (mtb)", "host object"): (dict(input=torch.nn.Linear(2, 2)), "is a OpaqueRef"),
        ("Pick From Batch (mtb)", "start 0"): (dict(image=torch.rand(5, 16, 16, 3, generator=g(2)),
                                                    from_direction="start", count=0), "picks no images"),
        ("Vae Decode (mtb)", "tiled 320"): (dict(vae=tiny_vae_factory(), samples=latent_big, seamless_model=False,
                                                 use_tiling_decoder=True, tile_size=320), "tile_size 320 is not "
                                                                                          "supported"),
        ("Vae Decode (mtb)", "seamless"): (dict(vae=None, samples=latent_big, seamless_model=True,
                                                use_tiling_decoder=False, tile_size=512),
                                           "seamless_model is not supported"),
        ("Load Image Sequence (mtb)", "absolute path"): (dict(path="/tmp/mtb-abs/####.png", current_frame=1,
                                                              range=""), "is outside it"),
        ("Load Image Sequence (mtb)", "all frames (-1)"): (dict(path="videos/####.png", current_frame=-1, range=""),
                                                            "loading all frames"),
        ("Load Image Sequence (mtb)", "range"): (dict(path="videos/####.png", current_frame=0, range="3-4"),
                                                 "loading all frames"),
    }


def write_frames(input_dir: Path, output_dir: Path):
    rng = np.random.default_rng(7)
    (input_dir / "videos").mkdir(parents=True)
    (input_dir / "clips").mkdir(parents=True)
    (output_dir / "renders").mkdir(parents=True)
    Image.fromarray(rng.integers(0, 256, (18, 22, 3), dtype=np.uint8), "RGB").save(input_dir / "videos/0003.png")
    Image.fromarray(rng.integers(0, 256, (18, 22, 4), dtype=np.uint8), "RGBA").save(input_dir / "videos/0004.png")
    Image.fromarray(rng.integers(0, 256, (18, 22), dtype=np.uint8), "L").save(input_dir / "videos/0005.png")
    Image.fromarray(rng.integers(0, 65536, (18, 22), dtype=np.uint16).astype(np.int32), "I").convert("I;16").save(
        input_dir / "videos/0006.png")
    jpg = Image.fromarray(rng.integers(0, 256, (16, 24, 3), dtype=np.uint8), "RGB")
    exif = jpg.getexif()
    exif[0x0112] = 6
    jpg.save(input_dir / "clips/0012.jpg", exif=exif.tobytes(), quality=90)
    Image.fromarray(rng.integers(0, 256, (9, 7, 3), dtype=np.uint8), "RGB").save(input_dir / "single.png")
    Image.fromarray(rng.integers(0, 256, (10, 12, 4), dtype=np.uint8), "RGBA").save(output_dir / "renders/07.png")
    Path("/tmp/mtb-abs").mkdir(parents=True, exist_ok=True)
    Image.fromarray(rng.integers(0, 256, (6, 6, 3), dtype=np.uint8), "RGB").save("/tmp/mtb-abs/0001.png")


def input_types_view(cls):
    """INPUT_TYPES with COMBO lists normalized, plus the outputs, for schema comparison."""
    def norm(spec):
        out = {}
        for section in ("required", "optional"):
            for name, declaration in (spec.get(section) or {}).items():
                kind = declaration[0]
                options = dict(declaration[1]) if len(declaration) > 1 and isinstance(declaration[1], dict) else {}
                if isinstance(kind, list) or kind == "COMBO":
                    values = list(kind) if isinstance(kind, list) else list(options.pop("options"))
                    options.pop("multiselect", None)
                    kind = ["COMBO", values]
                if options.get("multiline") is False:
                    options.pop("multiline")  # V2's STRING inputs state the default (single line) explicitly
                out[f"{section}.{name}"] = [kind, {k: v for k, v in options.items() if v is not None}]
        return out
    return {"inputs": norm(cls.INPUT_TYPES()), "return_types": list(cls.RETURN_TYPES),
            "return_names": list(getattr(cls, "RETURN_NAMES", None) or cls.RETURN_TYPES),
            "category": cls.CATEGORY, "output_node": bool(getattr(cls, "OUTPUT_NODE", False))}


async def main_async() -> int:
    head = pack_head()
    for name in ("input", "output", "temp"):
        path = Path(f"/tmp/mtb-{name}")
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True)
    folder_paths.set_input_directory("/tmp/mtb-input")
    folder_paths.set_output_directory("/tmp/mtb-output")
    folder_paths.set_temp_directory("/tmp/mtb-temp")
    write_frames(Path("/tmp/mtb-input"), Path("/tmp/mtb-output"))
    import _tiny_sd

    V1 = original_classes(head)
    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.mtb_parity", pack_id=f"{PACK}/{KEY}")
    proxies = loaded.node_mappings
    record("manifest: the loader registers the original's 113 ids", len(proxies) == 113, len(proxies))

    for node_id, cls in V1.items():
        want, got = input_types_view(cls), input_types_view(proxies[node_id])
        # A V2 node with no hidden inputs serves none; the original declares none for these nodes.
        record(f"schema {node_id}: inputs, options, outputs and category equal the original's", want == got,
               {"original": want, "v2": got})

    # Production pack guests run with guest/fixr1_compat.py applied (values-mode outputs are published by their
    # declared type). The gate cannot build a sealed runtime, so the session starts through
    # _mtb_sealed_guest_entry.py, which applies that patch before the guest main.
    class PatchedEntryGuestSession(GuestSession):
        def _guest_command(self, python):
            return [python, "/tests/_mtb_sealed_guest_entry.py"]

    session = await PatchedEntryGuestSession("mtb").start()

    class Backend:
        async def dispatch(self, plan, local_call, runtime=None):
            if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                return await local_call()
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="mtb")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    report_cases, verdicts, last_v2 = {}, {}, None
    try:
        vae = _tiny_sd.build_vae()
        all_cases = cases(vae)
        for node_id, node_cases in all_cases.items():
            for index, (name, inputs) in enumerate(node_cases.items()):
                orig = await run_original(V1[node_id], dict(inputs))
                v2 = await run_v2(proxies[node_id], dict(inputs), f"mtb-{node_id}-{index}")
                verdict, detail = verdict_of(orig, v2)
                report_cases.setdefault(node_id, {})[name] = {
                    "verdict": verdict, "detail": detail,
                    "outcome": "ok" if orig["ok"] else f"both raise {orig['error'][0]}" if not v2["ok"] else None}
                record(f"{node_id} / {name}: {verdict}", verdict == "EXACT", detail)
                if node_id == "Sharpen (mtb)" and orig["ok"] and v2["ok"] and last_v2 is None:
                    last_v2 = (orig["value"], v2["value"])

        # Load Image Sequence: the original's IS_CHANGED and the V2 fingerprint agree (file digest / "NONE").
        lis = V1["Load Image Sequence (mtb)"]
        for name, (path, frame) in {"existing frame": ("videos/####.png", 3), "missing frame": ("videos/####.png", 99),
                                    "[output] frame": ("renders/##.png [output]", 7)}.items():
            want = lis.IS_CHANGED(path=path, current_frame=frame, range="")
            try:
                got = await execution._async_map_node_over_list(
                    "mtb-fp", "1", proxies["Load Image Sequence (mtb)"],
                    {"path": [path], "current_frame": [frame], "range": [""]}, "fingerprint_inputs")
                got = (await execution.resolve_map_node_over_list_results(got))[0]
            except Exception as error:  # noqa: BLE001
                got = f"error: {error_of(error)}"
            report_cases.setdefault("Load Image Sequence (mtb)", {})[f"fingerprint, {name}"] = {
                "verdict": "EXACT" if got == want else "MISMATCH", "detail": None if got == want else [want, got]}
            record(f"Load Image Sequence (mtb) / fingerprint, {name}: equals IS_CHANGED", got == want, [want, got])

        # Known differences: V2 refuses by name; the original runs (or fails) as noted.
        def fresh_vae():
            return _tiny_sd.build_vae()

        for (node_id, name), (inputs, needle) in known_cases(fresh_vae).items():
            if inputs.get("vae", "absent") is None:
                inputs = {**inputs, "vae": fresh_vae()}
                orig_inputs = {**inputs, "vae": fresh_vae()}  # seamless mutates the VAE it is given
            else:
                orig_inputs = dict(inputs)
            orig = await run_original(V1[node_id], orig_inputs)
            v2 = await run_v2(proxies[node_id], dict(inputs), f"mtb-known-{name}")
            what, original_outcome, named = KNOWN[(node_id, name)]
            got_original = "ok" if orig["ok"] else orig["error"][0]
            ok = (not v2["ok"]) and needle in v2["error"][1] and got_original == original_outcome and (
                not named or v2["error"][1].startswith(f"{PACK}/{node_id}:"))
            report_cases.setdefault(node_id, {})[name] = {
                "verdict": "KNOWN-DIFFERENCE" if ok else "MISMATCH", "known_difference": what,
                "original": "ok" if orig["ok"] else orig["error"], "v2": v2.get("error")}
            record(f"{node_id} / {name}: V2 refuses by name (known difference)", ok, report_cases[node_id][name])
        guest_pid = session.last_guest_pid
    finally:
        _sdk.providers.register_execution_backend(previous)
        await session.kill()
    record("guest: node bodies ran in a separate guest process", bool(guest_pid) and guest_pid != os.getpid(),
           guest_pid)

    # Negative control: one changed element in a V2 output must be caught.
    if last_v2 is not None:
        tampered = last_v2[1][0].clone()
        tampered.view(-1)[0] += 1e-6
        caught = same(last_v2[0], (tampered,)) is not None
    else:
        caught = False
    record("negative control: a one-element change in a V2 output is caught", caught)

    for node_id, node_cases in report_cases.items():
        plain = [v["verdict"] for v in node_cases.values() if v["verdict"] != "KNOWN-DIFFERENCE"]
        verdicts[node_id] = {"verdict": "EXACT" if all(v == "EXACT" for v in plain) else "MISMATCH",
                             "cases": len(plain),
                             "known_differences": sum(v["verdict"] == "KNOWN-DIFFERENCE" for v in node_cases.values())}
    report = {"pack": PACK, "nodes": verdicts, "cases": report_cases, "checks": checks,
              "failed": [c["check"] for c in checks if not c["ok"]]}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "parity.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({"failed": report["failed"], "verdicts": verdicts}, indent=1))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
