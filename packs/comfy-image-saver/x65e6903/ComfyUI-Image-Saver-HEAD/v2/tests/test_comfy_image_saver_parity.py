"""Tier-1 parity: giriss/comfy-image-saver ORIGINAL (pristine nodes.py) vs the repaired V2 pack, all 9 nodes.

Run in the gate container (the original imports piexif, supplied read-only at /deps):
  DEPS=<unpacked piexif 1.1.3> run_in_gate.sh <pack root> <pack root>/v2/tests <results> test_comfy_image_saver_parity.py

* Original side: the pristine package imported in-process, exactly as ComfyUI would call it.
* V2 side: every node runs in a REAL guest (comfy_secure_nodes GuestSession) through core's dispatch shape
  (ExecutionPlan + wrap_inputs + InProcessCtxProvider), with exactly its declared SDK permissions.
* Exact comparisons: type-strict values, float.hex, file bytes (sha256), UI payloads, error type + message.
* Harness simplification: the guest is granted exactly the node's declared SDK_PERMISSIONS (no consent filter).
* Writes /results/parity.json; exit 1 on any MISMATCH or harness failure. Includes a negative control.
"""
import asyncio
import copy
import datetime as _dt
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
PACK = Path(os.environ.get("CIS_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("CIS_RESULTS", "/results"))
sys.path[:0] = [str(CORE), "/overlay"] + (["/deps"] if Path("/deps").is_dir() else [])

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image, JpegImagePlugin  # noqa: E402

import folder_paths  # noqa: E402
from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

IDS = ["Checkpoint Selector", "Save Image w/Metadata", "Sampler Selector", "Scheduler Selector",
       "Seed Generator", "String Literal", "Width/Height Literal", "Cfg Literal", "Int Literal"]
TMP = Path(tempfile.mkdtemp(prefix="cis-parity-"))
CKPT = TMP / "models" / "checkpoints"
(CKPT / "sub").mkdir(parents=True)
(CKPT / "model_a.safetensors").write_bytes(b"giriss parity checkpoint A\n" * 2048)
(CKPT / "sub" / "model.b.ckpt").write_bytes(bytes(range(256)) * 97)
folder_paths.folder_names_and_paths["checkpoints"] = ([str(CKPT)], set(folder_paths.supported_pt_extensions))
OUT = TMP / "out"


def import_package(name, root):
    for key in list(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key)
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PRISTINE = TMP / "pristine" / PACK.name
shutil.copytree(PACK, PRISTINE, ignore=shutil.ignore_patterns("v2"))
ORIG = import_package("giriss_original", PRISTINE)
ORIG_NODES = sys.modules["giriss_original.nodes"]
SECURE = import_package("giriss_secure", V2)
SECURE_SAVER = sys.modules["giriss_secure._saver"]

CASES = []          # every comparison, in order
GUEST = {"session": None, "pids": set()}


def same(a, b):
    """Exact, type-strict equality (float bits, tensor dtype/shape/values, dict key order)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return a.hex() == b.hex()
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return list(a) == list(b) and all(same(a[k], b[k]) for k in a)
    if isinstance(a, torch.Tensor):
        return a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
    return a == b


def show(value):
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [show(v) for v in value][:8]
    if isinstance(value, str) and len(value) > 120:
        return value[:117] + "..."
    return value


def record(node, case, kind, ok, **details):
    CASES.append({"node": node, "case": case, "kind": kind, "ok": bool(ok), **details})
    if not ok:
        print("MISMATCH", node, case, json.dumps(details, default=str)[:600], flush=True)


async def session():
    if GUEST["session"] is None:
        GUEST["session"] = await GuestSession("cis-parity", guest_runtime_root=V2).start()
    return GUEST["session"]


async def run_v2(node_id, inputs, *, method="execute", prompt=None, extra=None, caps=None):
    cls = SECURE.NODE_CLASS_MAPPINGS[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS if caps is None else caps)
    refs = _sdk.InProcessRefResolver()
    prompt_id = "cis-parity"
    scope = _execution_metadata.ExecutionMetadataScope(
        prompt_id, DynamicPrompt(prompt if prompt is not None else {}), extra, observe=True)
    scope.__enter__()
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id=prompt_id, node_id="9", node_type=cls.__name__, tier="sandbox",
            node_module=cls.__module__, inputs=dict(inputs),
            input_mode="refs" if getattr(cls, "SDK_REFS", False) else "values",
            method=method, permissions=permissions,
            prompt=prompt, extra_pnginfo=extra, dynamic_prompt=DynamicPrompt(prompt or {}),
            execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        guest = await session()
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="cis-parity")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        if method != "execute":
            return result
        values = []
        for item in (result.result or ()):
            values.append(await refs.resolve(item) if isinstance(item, _sdk.Ref) else item)
        return tuple(values), result.ui
    finally:
        scope.__exit__(None, None, None)


def run_orig(node_id, inputs):
    cls = ORIG.NODE_CLASS_MAPPINGS[node_id]
    return getattr(cls(), cls.FUNCTION)(**inputs)


async def scalar_nodes():
    sets = {
        "Seed Generator": ("seed", [0, 1, 7, 2**31 - 1, 2**32, 2**53 + 1, 2**63 - 1, 0xffffffffffffffff]),
        "String Literal": ("string", ["", "x", "multi\nline\ttab ☀ \U0001d11e", "  spaced  ", "a" * 10000]),
        "Width/Height Literal": ("int", [1, 8, 512, 1024, 16376, 16384]),
        "Cfg Literal": ("float", [0.0, -0.0, 0.1, 1e-300, 3.141592653589793, 7.5, 8.0, 100.0]),
        "Int Literal": ("int", [0, 1, 123456, 999999, 1000000]),
        "Sampler Selector": ("sampler_name", list(ORIG_NODES.comfy.samplers.KSampler.SAMPLERS)),
        "Scheduler Selector": ("scheduler", list(ORIG_NODES.comfy.samplers.KSampler.SCHEDULERS)),
        "Checkpoint Selector": ("ckpt_name", folder_paths.get_filename_list("checkpoints")),
    }
    for node_id, (name, values) in sets.items():
        for value in values:
            expected = run_orig(node_id, {name: value})
            actual, ui = await run_v2(node_id, {name: value})
            record(node_id, f"{name}={show(value)!r}", "value", same(expected, actual) and ui is None,
                   expected=show(list(expected)), actual=show(list(actual)), ui=ui)


async def validation():
    """Prompt-level admission for the catalogue combos: same accept/refuse decision as core's combo check."""
    names = folder_paths.get_filename_list("checkpoints")
    for node_id, name in (("Checkpoint Selector", "ckpt_name"), ("Save Image w/Metadata", "modelname")):
        original_choices = ORIG.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES()["required"][name][0]
        record(node_id, f"{name} choices", "schema", list(original_choices) == names, original=original_choices)
        for value in names + ["missing.safetensors", "../model_a.safetensors"]:
            accepted = value in original_choices
            verdict = await run_v2(node_id, {name: value}, method="validate_inputs")
            record(node_id, f"validate {name}={value!r}", "validation", (verdict is True) == accepted,
                   original_accepts=accepted, v2=verdict,
                   note=None if accepted else "both refuse; V2 message is the pack's own (not core's 'Value not in list')")


def schema_checks():
    for node_id in IDS:
        cls_o, cls_v = ORIG.NODE_CLASS_MAPPINGS[node_id], SECURE.NODE_CLASS_MAPPINGS[node_id]
        schema = cls_v.GET_SCHEMA()
        ok = (schema.node_id == node_id and schema.display_name == node_id
              and schema.category == cls_o.CATEGORY and bool(schema.is_output_node) == bool(getattr(cls_o, "OUTPUT_NODE", False)))
        types = cls_o.INPUT_TYPES()
        original_inputs = {}
        for section in ("required", "optional"):
            for key, spec in types.get(section, {}).items():
                original_inputs[key] = (section, spec)
        v2_inputs = {item.id: item for item in schema.inputs}
        ok = ok and list(original_inputs) == list(v2_inputs)
        details = []
        for key, (section, spec) in original_inputs.items():
            item = v2_inputs.get(key)
            if item is None:
                ok = False
                continue
            options = spec[1] if len(spec) > 1 else {}
            if bool(getattr(item, "optional", False)) != (section == "optional"):
                ok = False; details.append(f"{key}: optional flag")
            if isinstance(spec[0], list):
                v2_options = list(getattr(item, "options", []) or [])
                if key in ("ckpt_name", "modelname"):
                    details.append(f"{key}: catalogue combo hydrated by web/catalogues.js + validate_inputs (V2 options [])")
                elif v2_options != list(spec[0]):
                    ok = False; details.append(f"{key}: options differ")
            else:
                if item.get_io_type() != spec[0]:
                    ok = False; details.append(f"{key}: type {item.get_io_type()} != {spec[0]}")
                for attr in ("default", "min", "max", "step", "multiline"):
                    if attr in options and getattr(item, attr, None) != options[attr]:
                        ok = False; details.append(f"{key}: {attr} {getattr(item, attr, None)!r} != {options[attr]!r}")
        hidden = sorted(h.name for h in schema.hidden)
        original_hidden = sorted(types.get("hidden", {}))
        if hidden != original_hidden:
            ok = False; details.append(f"hidden {hidden} != {original_hidden}")
        outputs = [o.get_io_type() for o in schema.outputs]
        partial = [i for i, t in enumerate(cls_o.RETURN_TYPES) if isinstance(t, list)]
        for i, t in enumerate(cls_o.RETURN_TYPES):
            if i in partial:
                details.append(f"output {i}: original returns the choice list as its type; V2 Combo.Output io_type {outputs[i]} (partial)")
            elif outputs[i] != t:
                ok = False; details.append(f"output {i}: {outputs[i]} != {t}")
        if len(outputs) != len(cls_o.RETURN_TYPES):
            ok = False; details.append("output count")
        record(node_id, "schema", "schema", ok, details=details)


def frozen_filename_algorithm():
    """make_filename/make_pathname under a frozen clock: original vs V2 module functions (pure, in-process)."""
    class Frozen(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 2, 22, 45, 7, 123456)
    saved = (ORIG_NODES.datetime, SECURE_SAVER.datetime)
    ORIG_NODES.datetime = SECURE_SAVER.datetime = Frozen
    try:
        for pattern in ["%time_%seed", "%date/%time_%counter", "%model-%seed", "", "plain", "%seed%seed"]:
            for time_format in ["%Y-%m-%d-%H%M%S", "%H%M%S", "%Q", "%"]:
                for model in ["model_a.safetensors", "sub/model.b.ckpt"]:
                    args_ = (pattern, 42, model, 3, time_format)
                    for fn in ("make_filename", "make_pathname"):
                        try:
                            expected = ("ok", getattr(ORIG_NODES, fn)(*args_))
                        except Exception as error:
                            expected = ("error", type(error).__name__, str(error))
                        try:
                            actual = ("ok", getattr(SECURE_SAVER, fn)(*args_))
                        except Exception as error:
                            actual = ("error", type(error).__name__, str(error))
                        record("Save Image w/Metadata", f"{fn}{args_!r}", "algorithm", expected == actual,
                               expected=expected, actual=actual)
    finally:
        ORIG_NODES.datetime, SECURE_SAVER.datetime = saved


def image(batch, height, width, channels, seed):
    g = torch.Generator().manual_seed(seed)
    pixels = torch.rand((batch, height, width, channels), generator=g, dtype=torch.float32)
    pixels[:, 0, 0, :] = 0.0
    pixels[:, 0, 1, :] = 1.0
    pixels[:, 1, 0, :] = 1.25   # clipped to 255 by both writers
    pixels[:, 1, 1, :] = -0.1   # clipped to 0 by both writers
    return pixels


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def riff_chunks(data):
    """WebP container layout: [(fourcc, size)] and the first 8 bytes of the EXIF payload (TIFF byte order)."""
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunks, exif_head, pos = [], None, 12
    while pos + 8 <= len(data):
        fourcc = data[pos:pos + 4].decode("latin-1")
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        chunks.append([fourcc, size, hashlib.sha256(data[pos + 8:pos + 8 + size]).hexdigest()[:16]])
        if fourcc == "EXIF":
            exif_head = data[pos + 8:pos + 16].hex()
        pos += 8 + size + (size & 1)
    return {"chunks": chunks, "exif_head": exif_head}


def decode(data):
    import io as _io
    with Image.open(_io.BytesIO(data)) as im:
        im.load()
        exif = im.getexif()
        comment = exif.get_ifd(0x8769).get(0x9286)
        return {"format": im.format, "mode": im.mode, "size": im.size,
                "pixels": hashlib.sha256(np.asarray(im).tobytes()).hexdigest(),
                "user_comment": bytes(comment) if comment is not None else None,
                "text": dict(getattr(im, "text", {}) or {})}


PROMPT = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 20, "cfg": 7.5, "sampler_name": "euler",
                                               "scheduler": "normal", "denoise": 1.0, "model": ["4", 0]}},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model_a.safetensors"}},
    "9": {"class_type": "Save Image w/Metadata", "inputs": {"images": ["8", 0], "filename": "cis"}},
}
EXTRA = {"workflow": {"last_node_id": 9, "nodes": [{"id": 9, "type": "Save Image w/Metadata", "title": "☀ save"}],
                      "links": [], "version": 0.4}}


def saver_inputs(**over):
    base = dict(images=image(1, 48, 64, 3, 1), filename="cis_%seed_%counter", path="", extension="png", steps=30,
                cfg=7.5, modelname="model_a.safetensors", sampler_name="euler", scheduler="normal",
                positive="a cat,\n on a mat\twith ☀ ", negative=" lowres, bad ", seed_value=123456789,
                width=512, height=768, lossless_webp=True, quality_jpeg_or_webp=100, counter=7,
                time_format="%Y-%m-%d-%H%M%S")
    base.update(over)
    return base


async def save_pair(case, inputs, prompt, extra):
    """Run the original and V2 saver into fresh output roots; return both sides."""
    roots = {}
    sides = {}
    for side in ("orig", "v2"):
        root = OUT / case / side
        root.mkdir(parents=True)
        folder_paths.set_output_directory(str(root))
        roots[side] = root
        try:
            if side == "orig":
                ui = run_orig("Save Image w/Metadata", dict(inputs, prompt=prompt, extra_pnginfo=extra))["ui"]
                sides[side] = ("ok", {"images": list(ui["images"])})
            else:
                values, ui = await run_v2("Save Image w/Metadata", dict(inputs), prompt=prompt, extra=extra)
                sides[side] = ("ok", ui, values)
        except Exception as error:
            sides[side] = ("error", type(error).__name__, str(error))
    return sides, {k: tree(v) for k, v in roots.items()}, roots


async def saver_cases():
    exact_cases = [
        ("png-basic", saver_inputs(), PROMPT, EXTRA),
        ("png-batch3-subfolder-karras", saver_inputs(images=image(3, 40, 56, 3, 2), path="sub/%model",
         modelname="sub/model.b.ckpt", sampler_name="dpmpp_2m", scheduler="karras", filename="b_%counter_%seed",
         positive="红色 ☀ prompt", counter=0), PROMPT, EXTRA),
        ("png-rgba-no-extra", saver_inputs(images=image(1, 33, 31, 4, 3), filename="rgba"), PROMPT, None),
        ("png-empty-prompts", saver_inputs(filename="empty", positive="", negative="", cfg=0.0, steps=1), PROMPT, EXTRA),
        ("png-colon-names", saver_inputs(filename="t:%seed", path="sub:%counter"), PROMPT, EXTRA),
        ("webp-lossless-batch2", saver_inputs(images=image(2, 40, 40, 3, 4), extension="webp", filename="w_%seed"), PROMPT, EXTRA),
        ("webp-lossy-q80-rgba", saver_inputs(images=image(1, 37, 45, 4, 5), extension="webp", lossless_webp=False,
         quality_jpeg_or_webp=80, filename="wl"), PROMPT, EXTRA),
    ]
    for case, inputs, prompt, extra in exact_cases:
        sides, trees, _ = await save_pair(case, inputs, prompt, extra)
        o, v = sides["orig"], sides["v2"]
        if o[0] != "ok" or v[0] != "ok":
            record("Save Image w/Metadata", case, "file", False, orig=o, v2=v[:3] if v[0] == "error" else "ok")
            continue
        ui_ok = same(o[1], v[1]) and v[2] == ()
        same_names = list(trees["orig"]) == list(trees["v2"])
        bytes_equal = same_names and all(trees["orig"][k] == trees["v2"][k] for k in trees["orig"])
        decoded = same_names and all(decode(trees["orig"][k]) == decode(trees["v2"][k]) for k in trees["orig"])
        ext = inputs["extension"]
        record("Save Image w/Metadata", case, "file", ui_ok and same_names and (bytes_equal if ext == "png" else decoded),
               files=list(trees["orig"]), v2_files=list(trees["v2"]), ui_equal=ui_ok, bytes_equal=bytes_equal,
               decoded_equal=decoded,
               sha256={k: [hashlib.sha256(trees["orig"][k]).hexdigest()[:16],
                           hashlib.sha256(trees["v2"].get(k, b"")).hexdigest()[:16]] for k in trees["orig"]},
               riff=None if ext == "png" else {k: [riff_chunks(trees["orig"][k]), riff_chunks(trees["v2"].get(k, b""))]
                                               for k in trees["orig"]},
               non_exif_chunks_equal=None if ext == "png" else all(
                   [c for c in riff_chunks(trees["orig"][k])["chunks"] if c[0] not in ("EXIF", "VP8X")]
                   == [c for c in riff_chunks(trees["v2"].get(k, b""))["chunks"] if c[0] not in ("EXIF", "VP8X")]
                   for k in trees["orig"]),
               note=None if ext == "png" else "WebP: pixels and EXIF UserComment payload compared after decoding; container bytes listed in bytes_equal")

    # Refused as designed: the original's behaviour V2 cannot reproduce exactly, refused with a named error.
    refusals = [
        ("jpeg", saver_inputs(extension="jpeg", filename="j"), PROMPT, EXTRA, "JPEG output is not available"),
        ("duplicate-text-key", saver_inputs(filename="dup"), PROMPT, {"parameters": "x", "workflow": {}}, "occurs more than once"),
        ("path-escape", saver_inputs(path="../escape", filename="esc"), PROMPT, EXTRA, "escapes the output folder"),
        ("backslash-name", saver_inputs(filename="a\\b"), PROMPT, EXTRA, "backslash in an output name is not supported"),
    ]
    for case, inputs, prompt, extra, needle in refusals:
        sides, trees, roots = await save_pair(case, inputs, prompt, extra)
        o, v = sides["orig"], sides["v2"]
        detail = {"orig": o if o[0] == "error" else ("ok", list(trees["orig"])), "v2": v if v[0] == "error" else "ok"}
        if case == "jpeg" and o[0] == "ok":
            jpg = next(iter(trees["orig"].values()))
            import io as _io
            with Image.open(_io.BytesIO(jpg)) as im:
                detail["original_jpeg_sampling"] = JpegImagePlugin.get_sampling(im)  # 2 == 4:2:0
            detail["v2_writer_jpeg"] = "core _sdk.py save_images: subsampling=0 (4:4:4)"
        record("Save Image w/Metadata", case, "refused", v[0] == "error" and needle in v[2] and trees["v2"] == {}, **detail)

    # Overwrite: the original overwrites an existing file; V2 refuses and leaves the first file untouched.
    case = "overwrite"
    inputs = saver_inputs(filename="same")
    for side in ("orig", "v2"):
        (OUT / case / side).mkdir(parents=True)
    results = {}
    for attempt in (1, 2):
        for side in ("orig", "v2"):
            folder_paths.set_output_directory(str(OUT / case / side))
            data = dict(inputs, images=image(1, 48, 64, 3, 10 + attempt))
            try:
                if side == "orig":
                    run_orig("Save Image w/Metadata", dict(data, prompt=PROMPT, extra_pnginfo=EXTRA))
                    results[(side, attempt)] = "ok"
                else:
                    await run_v2("Save Image w/Metadata", data, prompt=PROMPT, extra=EXTRA)
                    results[(side, attempt)] = "ok"
            except Exception as error:
                results[(side, attempt)] = f"{type(error).__name__}: {error}"
    first = tree(OUT / case / "v2")
    record("Save Image w/Metadata", case, "refused",
           results[("orig", 2)] == "ok" and results[("v2", 1)] == "ok"
           and "FileExistsError" in results[("v2", 2)] and "comfy-image-saver/Save Image w/Metadata" in results[("v2", 2)]
           and "never overwrites" in results[("v2", 2)] and len(first) == 1,
           results={f"{k[0]}#{k[1]}": v for k, v in results.items()})

    # %time naming through the real guest: same structure (the exact algorithm is checked under a frozen clock).
    sides, trees, _ = await save_pair("time-token", saver_inputs(filename="%time_%seed", time_format="%Y%m%d"), PROMPT, EXTRA)
    names = [list(trees[s]) for s in ("orig", "v2")]
    record("Save Image w/Metadata", "time-token", "file",
           sides["orig"][0] == "ok" and sides["v2"][0] == "ok" and names[0] == names[1], files=names,
           note="same calendar day expected; exact clock-independent algorithm checked separately")


def negative_control():
    """The comparator must turn red on a perturbed V2 result."""
    ok_value = not same((7.5,), (7.500000000000001,))
    ok_type = not same((1,), (1.0,))
    ok_bytes = not (b"\x89PNG..." == b"\x89PNG..!")
    ok_tensor = not same(torch.zeros(2), torch.tensor([0.0, 1e-30]))
    return {"perturbed_float": ok_value, "int_vs_float": ok_type, "perturbed_bytes": ok_bytes,
            "perturbed_tensor": ok_tensor, "red_as_expected": ok_value and ok_type and ok_bytes and ok_tensor}


async def main():
    started = _dt.datetime.now(_dt.timezone.utc).isoformat()
    failure = None
    try:
        assert list(ORIG.NODE_CLASS_MAPPINGS) == IDS and list(SECURE.NODE_CLASS_MAPPINGS) == IDS
        schema_checks()
        frozen_filename_algorithm()
        await scalar_nodes()
        await validation()
        await saver_cases()
    except Exception:
        failure = traceback.format_exc()
        print(failure, flush=True)
    finally:
        if GUEST["session"] is not None:
            sandbox = getattr(GUEST["session"], "sandbox_kind", None)
            await GUEST["session"].kill()
        else:
            sandbox = None
    control = negative_control()
    nodes = {}
    for node_id in IDS:
        rows = [c for c in CASES if c["node"] == node_id]
        refused = [c for c in rows if c["kind"] == "refused"]
        bad = [c for c in rows if not c["ok"]]
        verdict = "MISMATCH" if bad else "EXACT"
        nodes[node_id] = {"verdict": verdict, "cases": len(rows), "refused_as_designed": len(refused) - len([c for c in refused if not c["ok"]]),
                          "mismatches": len(bad), "kinds": sorted({c["kind"] for c in rows})}
    report = {
        "pack": "comfy-image-saver", "key": "x65e6903", "started_utc": started,
        "finished_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "core": str(CORE), "torch": torch.__version__, "pillow": Image.__version__,
        "piexif": getattr(sys.modules.get("piexif"), "VERSION", None),
        "guest": {"pids": sorted(GUEST["pids"]), "sandbox_kind": sandbox},
        "nodes": nodes, "case_count": len(CASES), "negative_control": control,
        "harness_failure": failure, "cases": CASES,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "parity.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: report[k] for k in ("nodes", "case_count", "negative_control", "guest")}, indent=1, default=str))
    ok = failure is None and control["red_as_expected"] and all(n["verdict"] == "EXACT" for n in nodes.values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
