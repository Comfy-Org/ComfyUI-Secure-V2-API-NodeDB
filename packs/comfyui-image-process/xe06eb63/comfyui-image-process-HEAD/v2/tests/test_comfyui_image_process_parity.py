"""comfyui-image-process: the V2 pack against the original, side by side (tier-1 parity, gate).

    run_in_gate.sh <snapshot dir, or the pack folder> <.../v2/tests> <results> test_comfyui_image_process_parity.py

Original side: the pristine classes, defined from image_process.py, image_helper.py and define.py exactly as
written (each class definition is taken with ast and executed; the modules themselves import scipy, scikit-image
and piexif at import, which these classes never call). V2 side: the proxies packdb builds from secure-nodes.json,
registered in Core, with every node body in a real guest process (GuestSession). Both sides run the same prompts
through Core's PromptExecutor; validation goes through Core's validate_inputs.

Checks:
- all 18 schemas: the manifest rows encode exactly as the original classes' schemas (LoadICCProfile with an empty
  profile folder, as on a fresh install);
- SaveImageBMP: same outcome, same UI, same file names and decoded pixels; the files differ only in the BMP
  header's resolution fields (the original passes dpi=(72, 72); the SDK writer has no dpi option and Pillow writes
  its default 96 dpi). Cases: defaults, batches with %batch_num% and subfolders, clipping, RGBA, exact levels, the
  pack's filename tokens, a 1x1 image, a second run (counter), 1/2/5-channel images, a prefix outside the output
  folder, a %batch_num% prefix run twice (2 channels and the last two are documented known differences, each
  checked to differ in exactly that way);
- SaveImageJPG and the 16 other refused nodes: validation fails with "comfyui-image-process/<id> is not yet
  converted to Secure Nodes V2: <reason>", and execution raises the same message;
- negative control: a one-byte change in a V2 output file turns the BMP comparison red.
Writes /results/parity.json; exits 1 on any failed check.
"""

import ast
import asyncio
import copy
import json
import os
import shutil
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]

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
from comfy_secure_nodes import packdb, packmanifest  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK = "comfyui-image-process"
PACK_FOLDER = "comfyui-image-process-HEAD"
KEY = "xe06eb63"
RESULTS = Path("/results")
CONVERTED = ["SaveImageBMP"]
REFUSED = ["ColorPatchFlatten", "ColorPatchMerge", "AchromaticStabilizer", "LoadICCProfile", "SaveImageAdvancedCustom",
           "SaveImageJPG", "SaveImageAdvancedJPG", "SaveImageAdvancedBMP", "SaveImageTIFF", "SaveImageAdvancedTIFF",
           "SaveImageTGA", "SaveImageAdvancedTGA", "SaveImageAVIF", "SaveImageAdvancedAVIF", "SaveImageICO",
           "SaveImageAdvancedICO", "ICOPacker"]
# The ids the original's comfy_entrypoint registers, in its order.
ALL_IDS = ["ColorPatchFlatten", "ColorPatchMerge", "AchromaticStabilizer", "LoadICCProfile", "SaveImageAdvancedCustom",
           "SaveImageJPG", "SaveImageAdvancedJPG", "SaveImageBMP", "SaveImageAdvancedBMP", "SaveImageTIFF",
           "SaveImageAdvancedTIFF", "SaveImageTGA", "SaveImageAdvancedTGA", "SaveImageAVIF", "SaveImageAdvancedAVIF",
           "SaveImageICO", "SaveImageAdvancedICO", "ICOPacker"]
assert sorted(ALL_IDS) == sorted(REFUSED + CONVERTED)
# BITMAPINFOHEADER biXPelsPerMeter / biYPelsPerMeter (file offsets 38..45).
PPM = slice(38, 46)
checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:2000]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:600]}"), flush=True)


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    return next(d for d in sorted(root.iterdir()) if (d / "v2").is_dir())


def snapshot_dir() -> Path:
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/cip-snapshot") / PACK / KEY
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    return snap


# ---------------------------------------------------------------- the original classes, from the pristine source
def original_classes(head: Path) -> dict:
    import datetime as _datetime
    import json as _json
    import logging
    import random
    import re
    import time

    from PIL import ImageCms
    from PIL.Image import Image as PILImage
    from PIL.PngImagePlugin import PngInfo
    from comfy_api.latest import io, ui

    def classes_of(path: Path, namespace: dict, names=None) -> dict:
        source = path.read_text(encoding="utf-8")
        found = {}
        for node in ast.parse(source).body:
            if isinstance(node, ast.ClassDef) and (names is None or node.name in names):
                exec(compile(ast.get_source_segment(source, node), str(path), "exec"), namespace)  # noqa: S102
                found[node.name] = namespace[node.name]
        return found

    define = classes_of(head / "define.py", {})["define"]
    helper_ns = {"io": io, "ui": ui, "Image": Image, "PILImage": PILImage, "PngInfo": PngInfo, "np": np,
                 "torch": torch, "folder_paths": folder_paths, "os": os, "re": re, "json": _json, "time": time,
                 "random": random, "datetime": _datetime.datetime}
    helper = classes_of(head / "image_helper.py", helper_ns, {"ImageSaveHelperExt"})["ImageSaveHelperExt"]
    namespace = {"io": io, "ui": ui, "np": np, "logging": logging, "time": time, "Image": Image,
                 "ImageCms": ImageCms, "torch": torch, "folder_paths": folder_paths, "os": os,
                 "ImageSaveHelperExt": helper, "define": define,
                 "logger": logging.getLogger(define.logger_name)}
    return classes_of(head / "image_process.py", namespace)


# ---------------------------------------------------------------- prompts
FIXTURES = {}


def fixtures():
    g = torch.Generator().manual_seed(20261103)
    levels = torch.tensor([v / 255.0 for v in range(256)] + [(v + 0.5) / 255.0 for v in range(255)] + [1.0],
                          dtype=torch.float32)
    FIXTURES.update({
        "rgb": torch.rand(1, 24, 32, 3, generator=g),
        "batch3": torch.rand(3, 16, 20, 3, generator=g),
        "clip": torch.randn(1, 17, 13, 3, generator=g) * 1.5,
        "rgba": torch.rand(2, 12, 10, 4, generator=g),
        "levels": levels.reshape(1, 16, 32, 1).expand(1, 16, 32, 3).contiguous(),
        "tiny": torch.rand(1, 1, 1, 3, generator=g),
        "c1": torch.rand(1, 8, 8, 1, generator=g),
        "c2": torch.rand(1, 8, 8, 2, generator=g),
        "c5": torch.rand(1, 8, 8, 5, generator=g),
    })


BMP_CASES = {
    "defaults (one RGB image, prefix ComfyUI)": ("rgb", "ComfyUI", 1),
    "batch of 3, subfolder, %batch_num%": ("batch3", "sub/dir/shot_%batch_num%", 1),
    "values outside [0, 1] (clipping)": ("clip", "clip", 1),
    "RGBA images (convert drops alpha)": ("rgba", "rgba", 1),
    "exact and half-step 8-bit levels": ("levels", "levels", 1),
    "pack tokens %width% %height% %date:yyyy-MM-dd% %year%": ("rgb", "tok_%width%x%height%_%date:yyyy-MM-dd%_%year%", 1),
    "1x1 image": ("tiny", "tiny", 1),
    "second run continues the counter": ("rgb", "again", 2),
    "1-channel image (Pillow cannot read it)": ("c1", "c1", 1),
    "5-channel image (Pillow cannot read it)": ("c5", "c5", 1),
    "2-channel image (grey + alpha)": ("c2", "c2", 1),
    "prefix outside the output folder": ("rgb", "../escape", 1),
    "%batch_num% prefix, second run": ("batch3", "dup_%batch_num%", 2),
}


def _errors(side, run):
    return " | ".join(f"{e['type']}: {e['message']}" for e in side["runs"][run]["errors"])


# name: (what differs, the verdict it gives, a predicate that it differs in exactly that way)
KNOWN_DIFFERENCE_CASES = {
    "2-channel image (grey + alpha)": (
        "the original saves the grey channel as RGB; V2 refuses it by name", "MISMATCH",
        lambda o, v: o["runs"][0]["ok"] and not v["runs"][0]["ok"]
        and f"{PACK}/SaveImageBMP: a 2-channel IMAGE (mode LA) is not supported" in _errors(v, 0)),
    "prefix outside the output folder": (
        "both refuse; the messages differ (Core's vs the SDK writer's)", "BOTH-FAIL-MESSAGE-DIFFERS",
        lambda o, v: "Saving image outside the output folder is not allowed" in _errors(o, 0)
        and "output name must stay inside the output directory" in _errors(v, 0)),
    "%batch_num% prefix, second run": (
        "Core's counter can't see %batch_num% names, so the second run reuses them: the original overwrites its "
        "files, the SDK writer refuses to", "MISMATCH",
        lambda o, v: all(r["ok"] for r in o["runs"]) and v["runs"][0]["ok"] and not v["runs"][1]["ok"]
        and "output image already exists" in _errors(v, 1)
        and not compare_bmp_files(o["files"], v["files"])),
}


def register_test_nodes():
    class NedImage:
        RETURN_TYPES = ("IMAGE",)
        FUNCTION = "make"
        CATEGORY = "ned/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"key": ("STRING", {"default": "rgb"})}}

        def make(self, key):
            return (FIXTURES[key].clone(),)

    class NedAny:
        RETURN_TYPES = ("*",)
        FUNCTION = "make"
        CATEGORY = "ned/test"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {}}

        def make(self):
            return (None,)

    core_nodes.NODE_CLASS_MAPPINGS["NedImage"] = NedImage
    core_nodes.NODE_CLASS_MAPPINGS["NedAny"] = NedAny


class FakeServer:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None

    def send_sync(self, *_args, **_kwargs):
        pass

    def queue_updated(self):
        pass


def bmp_prompt(key, prefix, node_id="SaveImageBMP"):
    return {"1": {"class_type": "NedImage", "inputs": {"key": key}},
            "2": {"class_type": node_id, "inputs": {"images": ["1", 0], "filename_prefix": prefix}}}


async def run_prompt(prompt, prompt_id):
    executor = execution.PromptExecutor(FakeServer(), cache_type=False,
                                        cache_args={"lru": 0, "ram": 0, "ram_inactive": 0})
    await executor.execute_async(json.loads(json.dumps(prompt)), prompt_id, {"extra_pnginfo": {"workflow": {}}}, ["2"])
    errors = [m[1] for m in executor.status_messages if m[0] == "execution_error"]
    outputs = executor.history_result.get("outputs") or {}
    return {"ok": bool(executor.success and not errors),
            "errors": [{"type": str(e.get("exception_type")), "message": str(e.get("exception_message"))}
                       for e in errors],
            "ui": json.loads(json.dumps(outputs.get("2"), default=str))}


def read_files(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


async def run_bmp_side(label, cls, original):
    core_nodes.NODE_CLASS_MAPPINGS["SaveImageBMP"] = cls
    results = {}
    for index, (name, (key, prefix, runs)) in enumerate(BMP_CASES.items()):
        out = Path(f"/tmp/cip-{label}-out-{index}")
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        folder_paths.set_output_directory(str(out))
        if original:
            cls.output_dir = folder_paths.get_output_directory()  # a class attribute the original reads at import
        try:
            valid = await execution.validate_inputs(f"{label}-v{index}", bmp_prompt(key, prefix), "2", {})
            runs_out = [await run_prompt(bmp_prompt(key, prefix), f"{label}-{index}-{r}") for r in range(runs)]
            results[name] = {"validation_ok": bool(valid[0]), "runs": runs_out, "files": read_files(out)}
        except Exception:  # noqa: BLE001
            results[name] = {"validation_ok": None, "runs": [{"ok": False, "errors": [
                {"type": "harness", "message": traceback.format_exc()[-1500:]}], "ui": None}], "files": {}}
    return results


def decoded(data: bytes):
    import io as _io

    with Image.open(_io.BytesIO(data)) as img:
        img.load()
        return img.mode, img.size, np.asarray(img).copy(), img.info.get("dpi")


def compare_bmp_files(orig_files: dict, v2_files: dict) -> list:
    """Empty list when the files match: names, decoded mode/size/pixels, and every byte but the resolution fields
    (which must be the original's 72 dpi and Pillow's default 96 dpi)."""
    problems = []
    if sorted(orig_files) != sorted(v2_files):
        return [f"file names differ: {sorted(orig_files)} vs {sorted(v2_files)}"]
    for name in orig_files:
        a, b = orig_files[name], v2_files[name]
        ma, mb = decoded(a), decoded(b)
        if ma[0] != mb[0] or ma[1] != mb[1] or not np.array_equal(ma[2], mb[2]):
            problems.append(f"{name}: decoded image differs (mode {ma[0]}/{mb[0]}, size {ma[1]}/{mb[1]})")
        if len(a) != len(b) or a[:PPM.start] != b[:PPM.start] or a[PPM.stop:] != b[PPM.stop:]:
            problems.append(f"{name}: bytes differ outside the header resolution fields")
        ppm_a = (int.from_bytes(a[38:42], "little"), int.from_bytes(a[42:46], "little"))
        ppm_b = (int.from_bytes(b[38:42], "little"), int.from_bytes(b[42:46], "little"))
        if ppm_a != (2835, 2835) or ppm_b != (3780, 3780):
            problems.append(f"{name}: resolution fields {ppm_a} / {ppm_b}, expected (2835, 2835) / (3780, 3780)")
    return problems


def error_text(run) -> str:
    return " | ".join(f"{e['type']}: {e['message']}" for e in run["errors"])


def compare_bmp_case(name, orig, v2):
    """Returns (verdict, detail)."""
    o_runs, v_runs = orig["runs"], v2["runs"]
    if any(r["errors"] and r["errors"][0]["type"] == "harness" for r in o_runs + v_runs):
        return "HARNESS-ERROR", [error_text(r) for r in o_runs + v_runs]
    if orig["validation_ok"] != v2["validation_ok"]:
        return "MISMATCH", f"validation {orig['validation_ok']} vs {v2['validation_ok']}"
    if [r["ok"] for r in o_runs] != [r["ok"] for r in v_runs]:
        return "MISMATCH", {"original": [error_text(r) for r in o_runs], "v2": [error_text(r) for r in v_runs]}
    if not all(r["ok"] for r in o_runs):
        o_msgs = [e["message"] for r in o_runs for e in r["errors"]]
        v_msgs = [e["message"] for r in v_runs for e in r["errors"]]
        same = o_msgs == v_msgs or all(om.strip() and om.strip() in vm for om, vm in zip(o_msgs, v_msgs))
        return ("EXACT" if same else "BOTH-FAIL-MESSAGE-DIFFERS"), {"original": o_msgs, "v2": v_msgs}
    if [r["ui"] for r in o_runs] != [r["ui"] for r in v_runs]:
        return "MISMATCH", {"ui_original": [r["ui"] for r in o_runs], "ui_v2": [r["ui"] for r in v_runs]}
    problems = compare_bmp_files(orig["files"], v2["files"])
    if problems:
        return "MISMATCH", problems
    return "EXACT", {"files": sorted(orig["files"]), "ui": [r["ui"] for r in o_runs]}


# ---------------------------------------------------------------- refused nodes
WIDGETS = {"INT", "FLOAT", "BOOLEAN", "STRING"}


def refusal_prompt(proxy, node_id):
    inputs = {}
    for name, declaration in (proxy.INPUT_TYPES().get("required") or {}).items():
        kind = declaration[0]
        options = declaration[1] if len(declaration) > 1 and isinstance(declaration[1], dict) else {}
        if isinstance(kind, list):
            inputs[name] = kind[0] if kind else ""
        elif kind == "COMBO":
            values = options.get("options") or [""]
            inputs[name] = values[0]
        elif kind in WIDGETS:
            inputs[name] = options.get("default", {"INT": 0, "FLOAT": 0.0, "BOOLEAN": False, "STRING": ""}[kind])
        else:
            inputs[name] = ["1", 0]
    return {"1": {"class_type": "NedAny", "inputs": {}}, "2": {"class_type": node_id, "inputs": inputs}}


async def check_refusals(proxies, manifest):
    verdicts = {}
    for node_id in REFUSED:
        expected = (f"{PACK}/{node_id} is not yet converted to Secure Nodes V2: ")
        proxy = proxies[node_id]
        core_nodes.NODE_CLASS_MAPPINGS[node_id] = proxy
        prompt = refusal_prompt(proxy, node_id)
        ok_flag, errors, _ = await execution.validate_inputs(f"refuse-{node_id}", prompt, "2", {})
        refusal_errors = [e for e in errors if e.get("type") == "custom_validation_failed"
                          and expected in str(e.get("details"))]
        other = [e for e in errors if e not in refusal_errors]
        validation_ok = (not ok_flag) and bool(refusal_errors) and not other
        message = str(refusal_errors[0]["details"]) if refusal_errors else None
        try:
            # Widgets as validated; IMAGE and MASK links as small tensors (custom-typed links are left out).
            values = {}
            for name, value in prompt["2"]["inputs"].items():
                kind = proxy.INPUT_TYPES()["required"][name][0]
                if not isinstance(value, list):
                    values[name] = [value]
                elif kind == "IMAGE":
                    values[name] = [FIXTURES["rgb"].clone()]
                elif kind == "MASK":
                    values[name] = [torch.zeros(1, 24, 32)]
            await execution.get_output_data(f"refuse-exec-{node_id}", "2", proxy, values)
            raised = None
        except Exception as error:  # noqa: BLE001
            raised = f"{getattr(error, 'remote_type', type(error).__name__)}: {error}"
        execution_ok = raised is not None and expected in raised
        verdicts[node_id] = {"verdict": "REFUSED-AS-DESIGNED" if validation_ok and execution_ok else "MISMATCH",
                             "validation_message": message, "execution_error": raised,
                             "other_validation_errors": [str(e)[:300] for e in other]}
        record(f"refused {node_id}: validation and execution fail with the named refusal",
               validation_ok and execution_ok, verdicts[node_id])
    return verdicts


# ---------------------------------------------------------------- main
async def main_async() -> int:
    head = pack_head()
    for name in ("temp", "output", "icc"):
        path = Path(f"/tmp/cip-{name}")
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True)
    folder_paths.set_temp_directory("/tmp/cip-temp")
    # The original's __init__ registers models/icc_profiles; a fresh install has no profiles in it.
    folder_paths.add_model_folder_path("icc_profiles", "/tmp/cip-icc")
    fixtures()
    register_test_nodes()
    V1 = original_classes(head)
    record("original: the 18 registered classes are defined from the pristine source", set(ALL_IDS) <= set(V1),
           sorted(V1))

    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.cip_parity", pack_id=f"{PACK}/{KEY}")
    proxies = loaded.node_mappings
    manifest = json.loads((head / "v2" / "secure-nodes.json").read_text())
    record("manifest: the loader registers exactly the original's 18 ids", sorted(proxies) == sorted(ALL_IDS),
           sorted(proxies))
    record("manifest: declares the web directory with the original's frontend file",
           loaded.web_directory is not None and (Path(loaded.web_directory) / "image_process.js").is_file(),
           loaded.web_directory)

    schema_report = {}
    for node_id in ALL_IDS:
        want = packmanifest.encode_schema(copy.deepcopy(V1[node_id].GET_SCHEMA()))
        got = manifest["nodes"][node_id]["schema"]
        schema_report[node_id] = want == got
        record(f"schema {node_id}: the manifest row encodes exactly as the original's schema", want == got,
               {"original": json.dumps(want, sort_keys=True)[:700], "v2": json.dumps(got, sort_keys=True)[:700]})

    session = await GuestSession("cip").start()

    class Backend:
        async def dispatch(self, plan, local_call, runtime=None):
            if not str(getattr(plan, "node_module", "") or "").startswith("custom_nodes."):
                return await local_call()
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="cip")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    saved = {k: core_nodes.NODE_CLASS_MAPPINGS.get(k) for k in ALL_IDS}
    try:
        original = await run_bmp_side("orig", V1["SaveImageBMP"], original=True)
        v2 = await run_bmp_side("v2", proxies["SaveImageBMP"], original=False)
        refusals = await check_refusals(proxies, manifest)
        guest_pid = session.last_guest_pid
    finally:
        _sdk.providers.register_execution_backend(previous)
        for key, value in saved.items():
            if value is None:
                core_nodes.NODE_CLASS_MAPPINGS.pop(key, None)
            else:
                core_nodes.NODE_CLASS_MAPPINGS[key] = value
        await session.kill()

    cases = {}
    for name in BMP_CASES:
        verdict, detail = compare_bmp_case(name, original[name], v2[name])
        cases[name] = {"verdict": verdict, "detail": detail}
        if name in KNOWN_DIFFERENCE_CASES:
            what, expected, predicate = KNOWN_DIFFERENCE_CASES[name]
            ok = verdict == expected and bool(predicate(original[name], v2[name]))
            cases[name]["known_difference"] = what
            record(f"SaveImageBMP {name}: the documented known difference, and nothing else", ok, cases[name])
        else:
            record(f"SaveImageBMP {name}: {verdict}", verdict == "EXACT", cases[name])
    record("guest: node bodies ran in a separate guest process", bool(guest_pid) and guest_pid != os.getpid(),
           guest_pid)

    # Negative control: a one-byte pixel change in a V2 file must turn the comparison red.
    base = "defaults (one RGB image, prefix ComfyUI)"
    tampered = dict(v2[base]["files"])
    control = ["no V2 file to tamper with"]
    if tampered:
        first = sorted(tampered)[0]
        data = bytearray(tampered[first])
        data[-1] ^= 0x01
        tampered[first] = bytes(data)
        control = compare_bmp_files(original[base]["files"], tampered)
        record("negative control: the untampered V2 files compare clean",
               not compare_bmp_files(original[base]["files"], v2[base]["files"]))
    record("negative control: a one-byte change in a V2 BMP is caught", bool(control), control)

    exact_cases = [n for n in BMP_CASES if n not in KNOWN_DIFFERENCE_CASES]
    bmp_exact = all(cases[n]["verdict"] == "EXACT" for n in exact_cases)
    report = {
        "pack": PACK,
        "nodes": {
            "SaveImageBMP": {
                "verdict": "EXACT" if bmp_exact else "MISMATCH",
                "cases": len(BMP_CASES),
                "exact_cases": sum(cases[n]["verdict"] == "EXACT" for n in exact_cases),
                "file_bytes": "equal except the BMP header's resolution fields (72 vs 96 dpi)",
                "known_differences": {k: v[0] for k, v in KNOWN_DIFFERENCE_CASES.items()},
            },
            **{node_id: {"verdict": refusals[node_id]["verdict"], "cases": 2} for node_id in REFUSED},
        },
        "schemas_equal": schema_report,
        "bmp_cases": {k: {"verdict": v["verdict"], "detail": v["detail"]} for k, v in cases.items()},
        "refusals": refusals,
        "negative_control": {"caught": bool(control), "problems": control},
        "checks": checks,
        "failed": [c["check"] for c in checks if not c["ok"]],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "parity.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({"failed": report["failed"], "verdicts": {k: v["verdict"] for k, v in report["nodes"].items()}},
                     indent=1))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
