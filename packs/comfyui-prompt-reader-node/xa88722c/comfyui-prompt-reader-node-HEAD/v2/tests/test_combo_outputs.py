"""Tier-1 COMBO-output parity: comfyui-prompt-reader-node ORIGINAL vs V2 (CPU, no weights, synthetic fixtures).

The original's SDParameterGenerator returns Core's sampler and scheduler lists as the types of its SAMPLER_NAME
and SCHEDULER outputs (nodes.py:818-819). Its MODEL_NAME and VAE_NAME outputs (nodes.py:809-810), and
SDLoraSelector's LORA_NAME (nodes.py:1323), have the host's model-folder lists as their types. Core accepts a
list linked into a list-typed input when the lists share a value (comfy_execution/validation.py).
V2 declares the two Core-list outputs as COMBO outputs with exactly those options. The three host-catalogue
outputs declare no options, because a host list is never frozen, and Core serves them as a generic COMBO.

Run in the gate (DEPS = piexif, which the original imports):
  DEPS=<piexif> run_in_gate.sh <pack> <pack>/v2/tests <results> test_combo_outputs.py
once on each Core:
  * a Core whose Combo.Output reports declared options (comfy_api/latest/_io.py with Combo.Output.get_io_type);
  * a Core without it, where every COMBO output is the plain string "COMBO" (reported, expected to differ).

Checks:
  L. packdb.load_pack on v2/secure-nodes.json (the host's registration) succeeds, and the type each proxy's
     COMBO output reports.
  A. object_info outputs of every node: the original (V1 class) vs the V2 host proxy, as served. The three
     host-catalogue outputs serve COMBO in V2 and the host's list in the original; normalised and counted.
  B. Core's validate_prompt on synthetic prompts, with the original classes and then the V2 proxies registered
     under the same ids: same verdict, same node errors (type, input), same good outputs. Links from the
     host-catalogue outputs into Core's list-typed inputs are labelled known differences: recorded, not failed.
  C. Returned values in a REAL guest vs the original (SDLoraSelector, SDTypeConverter): their outputs are built
     from the repaired schema code in the guest.
  D. Negative controls: the comparisons must flag an output without its options and a disjoint link.
Writes /results/combo-outputs.json. Exit 0 only when everything except the labelled known differences equals
the original.
"""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
PACK = Path(os.environ.get("PROMPTREADER_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("PROMPTREADER_RESULTS", "/results"))
sys.path[:0] = [str(CORE), "/overlay", str(Path(__file__).resolve().parent)] + (
    ["/deps"] if Path("/deps").is_dir() else [])

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402
import execution  # noqa: E402
from comfy_api.latest import _execution_metadata, _sdk, io  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

import encode_manifest  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="prompt-reader-combo-"))
FOLDERS = {"checkpoints": ("model_a.safetensors", "model_b.safetensors"), "vae": ("vae_a.safetensors",),
           "loras": ("lora_a.safetensors", "lora_b.safetensors"), "configs": ("v1-inference.yaml",)}
for folder, names in FOLDERS.items():
    directory = TMP / "models" / folder
    directory.mkdir(parents=True)
    for name in names:
        (directory / name).write_bytes(b"synthetic file name only\n")
    extensions = {".yaml"} if folder == "configs" else set(folder_paths.supported_pt_extensions)
    folder_paths.folder_names_and_paths[folder] = ([str(directory)], extensions)
(TMP / "input").mkdir()
folder_paths.set_input_directory(str(TMP / "input"))
CORE_REPORTS_OPTIONS = "get_io_type" in vars(io.Combo.Output)
CATALOGUE_OUTPUTS = {("SDParameterGenerator", 0): "checkpoints", ("SDParameterGenerator", 1): "vae",
                     ("SDLoraSelector", 0): "loras"}
ROWS = []


def import_original(name="prompt_reader_original"):
    """nodes.py of a pristine copy (without v2/), under a bare package: the package __init__.py, which deletes a
    directory under Core's web/extensions at import, does not run."""
    root = TMP / "pristine" / PACK.name
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    package = types.ModuleType(name)
    package.__path__ = [str(root)]
    package.__package__ = name
    sys.modules[name] = package
    spec = importlib.util.spec_from_file_location(f"{name}.nodes", root / "nodes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return dict(module.NODE_CLASS_MAPPINGS)


def import_package(name, root):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ORIGINAL = import_original()
SECURE = dict(import_package("prompt_reader_secure", V2).NODE_CLASS_MAPPINGS)


def plain(value):
    return json.loads(json.dumps(value, default=list))


def record(check, case, ok, **details):
    ROWS.append({"check": check, "case": case, "ok": bool(ok), **details})
    if not ok and not details.get("known_difference"):
        print("DIFF", check, case, json.dumps(details, default=str)[:700], flush=True)


# --------------------------------------------------------------------------------------------------------------- #
# L. load_pack with the committed manifest
# --------------------------------------------------------------------------------------------------------------- #
def load_proxies():
    try:
        loaded = encode_manifest.load_snapshot((V2 / "secure-nodes.json").read_bytes(),
                                               "custom_nodes.prompt_reader_combo_check")
    except Exception as error:  # noqa: BLE001
        return None, {"ok": False, "error": f"{type(error).__name__}: {error}",
                      "traceback": traceback.format_exc()[-1500:]}
    reported = {}
    for node_id, proxy in sorted(loaded.node_mappings.items()):
        for index, output in enumerate(proxy.GET_SCHEMA().outputs):
            if output.io_type == "COMBO":
                kind = output.get_io_type()
                reported[f"{node_id} / output {index}"] = kind if isinstance(kind, str) else f"list[{len(kind)}]"
    return dict(loaded.node_mappings), {"ok": True, "combo_outputs_report": reported}


# --------------------------------------------------------------------------------------------------------------- #
# A. object_info outputs
# --------------------------------------------------------------------------------------------------------------- #
def v1_outputs(cls):
    """server.py node_info for a V1 class, output fields only."""
    output = list(cls.RETURN_TYPES)
    info = {
        "output": output,
        "output_is_list": list(cls.OUTPUT_IS_LIST) if hasattr(cls, "OUTPUT_IS_LIST") else [False] * len(output),
        "output_name": list(cls.RETURN_NAMES) if hasattr(cls, "RETURN_NAMES") else output,
        "output_tooltips": list(cls.OUTPUT_TOOLTIPS) if hasattr(cls, "OUTPUT_TOOLTIPS") else None,
    }
    return plain(info)


def served_outputs(cls):
    info = cls.GET_NODE_INFO_V1()
    return plain({key: info.get(key) for key in ("output", "output_is_list", "output_name", "output_tooltips")})


def normal(info):
    """V3 serves output_tooltips as a list with None for absent entries; V1 omits the key when undeclared."""
    tips = info.get("output_tooltips")
    if not tips or all(tip is None for tip in tips):
        tips = None
    return {**info, "output_tooltips": tips}


def shown(info):
    return {k: (v if k != "output" else [x if not isinstance(x, list) else f"list[{len(x)}]" for x in v])
            for k, v in info.items()}


def object_info_outputs(proxies):
    counts = {"core_list_outputs": 0, "catalogue_outputs_served_generic_combo": 0}
    for node_id in sorted(ORIGINAL):
        original = normal(v1_outputs(ORIGINAL[node_id]))
        try:
            served = normal(served_outputs(proxies[node_id]))
        except Exception as error:  # noqa: BLE001
            record("A_object_info_outputs", node_id, False, error=f"{type(error).__name__}: {error}")
            continue
        details = {"list_outputs": [i for i, v in enumerate(original["output"]) if isinstance(v, list)]}
        expected = copy.deepcopy(original)
        for (catalogue_node, index), folder in CATALOGUE_OUTPUTS.items():
            if catalogue_node != node_id:
                continue
            # The original serves this host's list for the folder; V2 serves the generic COMBO.
            assert sorted(original["output"][index]) == sorted(folder_paths.get_filename_list(folder)), node_id
            expected["output"][index] = "COMBO"
            counts["catalogue_outputs_served_generic_combo"] += served["output"][index] == "COMBO"
        counts["core_list_outputs"] += sum(1 for i in details["list_outputs"]
                                           if (node_id, i) not in CATALOGUE_OUTPUTS)
        if expected != served:
            details.update(original=shown(original), v2=shown(served),
                           differing_keys=sorted(k for k in expected if expected[k] != served.get(k)))
        record("A_object_info_outputs", node_id, expected == served, **details)
    return counts


# --------------------------------------------------------------------------------------------------------------- #
# B. Core's validate_prompt, original vs V2 under the same ids
# --------------------------------------------------------------------------------------------------------------- #
def stock():
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model_a.safetensors"}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": "a", "clip": ["ckpt", 1]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": "b", "clip": ["ckpt", 1]}},
        "lat": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "ks": {"class_type": "KSampler", "inputs": {
            "model": ["ckpt", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
            "seed": 1, "steps": 1, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
        "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["ckpt", 2]}},
        "out": {"class_type": "PreviewImage", "inputs": {"images": ["dec", 0]}},
    }


GENERATOR = {"class_type": "SDParameterGenerator", "inputs": {
    "ckpt_name": "model_a.safetensors", "vae_name": "baked VAE", "model_version": "SDv1 512px",
    "config_name": "none", "seed": 20261103, "steps": 2, "refiner_start": 0.8, "cfg": 5.0, "sampler_name": "dpmpp_2m",
    "scheduler": "karras", "positive_ascore": 6.0, "negative_ascore": 6.0, "aspect_ratio": "custom", "width": 512,
    "height": 512, "batch_size": 1}}


def prompts():
    cases = {"control_stock_prompt": stock()}

    def with_generator(ks_links, extra=None, base=None):
        prompt = base or stock()
        prompt["gen"] = copy.deepcopy(GENERATOR)
        prompt.update(copy.deepcopy(extra or {}))
        prompt["ks"]["inputs"].update(ks_links)
        return prompt

    cases["generator_sampler_scheduler_to_ksampler"] = with_generator(
        {"sampler_name": ["gen", 9], "scheduler": ["gen", 10]})
    # The generator driving the whole graph: its MODEL/CLIP/VAE and every KSampler parameter.
    full = with_generator({"model": ["gen", 2], "seed": ["gen", 5], "steps": ["gen", 6], "cfg": ["gen", 8],
                           "sampler_name": ["gen", 9], "scheduler": ["gen", 10]})
    del full["ckpt"]
    for node in ("pos", "neg"):
        full[node]["inputs"]["clip"] = ["gen", 3]
    full["lat"]["inputs"].update(width=["gen", 13], height=["gen", 14], batch_size=["gen", 15])
    full["dec"]["inputs"]["vae"] = ["gen", 4]
    cases["generator_drives_ksampler_graph"] = full
    # The pack's own consumers: Type Converter and Prompt Saver, fed by the generator and the LoRA selector.
    pack = copy.deepcopy(full)
    pack["conv"] = {"class_type": "SDTypeConverter", "inputs": {
        "model_name": ["gen", 0], "sampler_name": ["gen", 9], "scheduler": ["gen", 10]}}
    pack["conv_out"] = {"class_type": "SDPromptMerger", "inputs": {"text_g": ["conv", 1], "text_l": ["conv", 2]}}
    pack["lsel"] = {"class_type": "SDLoraSelector", "inputs": {"lora_name": "lora_a.safetensors"}}
    pack["save"] = {"class_type": "SDPromptSaver", "inputs": {
        "images": ["dec", 0], "model_name": ["gen", 0], "vae_name": ["gen", 1], "seed": ["gen", 5],
        "steps": ["gen", 6], "cfg": ["gen", 8], "sampler_name": ["gen", 9], "scheduler": ["gen", 10],
        "lora_name": ["lsel", 1], "width": ["gen", 13], "height": ["gen", 14], "positive": ["conv_out", 0],
        "negative": "", "extension": "png"}}
    del pack["out"]
    cases["generator_and_lora_selector_into_pack_nodes"] = pack
    # Known differences (host-catalogue outputs serve a generic COMBO in V2): links into Core's list inputs.
    named = with_generator({})
    named["ckpt"]["inputs"]["ckpt_name"] = ["gen", 0]
    cases["catalogue_model_name_into_core_checkpoint_loader"] = named
    lora = stock()
    lora["lsel"] = {"class_type": "SDLoraSelector", "inputs": {"lora_name": "lora_a.safetensors"}}
    lora["lora"] = {"class_type": "LoraLoader", "inputs": {
        "model": ["ckpt", 0], "clip": ["ckpt", 1], "lora_name": ["lsel", 0], "strength_model": 1.0,
        "strength_clip": 1.0}}
    lora["ks"]["inputs"]["model"] = ["lora", 0]
    cases["catalogue_lora_name_into_core_lora_loader"] = lora
    # Negative controls: refused by the original too.
    cases["negative_scheduler_list_into_sampler_input"] = with_generator({"sampler_name": ["gen", 10]})
    cases["negative_sampler_list_into_scheduler_input"] = with_generator({"scheduler": ["gen", 9]})
    return cases


def summary(result):
    valid, error, good, node_errors = result
    errors = {}
    for node_id, entry in sorted(node_errors.items()):
        errors[node_id] = sorted((item.get("type"), (item.get("extra_info") or {}).get("input_name"))
                                 for item in entry.get("errors", []))
    return {"valid": bool(valid), "error_type": (error or {}).get("type") if isinstance(error, dict) else error,
            "good_outputs": sorted(good), "node_errors": errors}


def details(result):
    return {node_id: [str(item.get("details"))[:160] for item in entry.get("errors", [])]
            for node_id, entry in sorted(result[3].items())}


async def validate_with(classes, prompt):
    saved = {node_id: core_nodes.NODE_CLASS_MAPPINGS.get(node_id) for node_id in classes}
    core_nodes.NODE_CLASS_MAPPINGS.update(classes)
    try:
        return await execution.validate_prompt("prompt-reader-combo", copy.deepcopy(prompt), None)
    finally:
        for node_id, value in saved.items():
            if value is None:
                core_nodes.NODE_CLASS_MAPPINGS.pop(node_id, None)
            else:
                core_nodes.NODE_CLASS_MAPPINGS[node_id] = value


async def prompt_validation(proxies):
    for name, prompt in prompts().items():
        original = await validate_with(ORIGINAL, prompt)
        v2 = await validate_with(proxies, prompt)
        a, b = summary(original), summary(v2)
        row = {"original": a, "v2": b}
        if a != b:
            row["original_details"], row["v2_details"] = details(original), details(v2)
        if name.startswith("negative_"):
            row["control"] = "refused by the original as well" if not a["valid"] or a["node_errors"] else "UNEXPECTED"
        if name.startswith("catalogue_"):
            row["known_difference"] = ("host-catalogue output served as a generic COMBO; Core refuses COMBO into "
                                       "a list-typed input (validation.py:239-240) on every Core")
        record("B_validate_prompt", name, a == b, **row)


# --------------------------------------------------------------------------------------------------------------- #
# C. Returned values in a real guest
# --------------------------------------------------------------------------------------------------------------- #
GUEST = {"session": None, "pids": set()}


async def run_v2(node_id, inputs):
    cls = SECURE[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope("prompt-reader-combo", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="prompt-reader-combo", node_id="9", node_type=cls.__name__, tier="sandbox",
            node_module=cls.__module__, inputs=dict(inputs),
            input_mode="refs" if getattr(cls, "SDK_REFS", False) else "values",
            method="execute", permissions=permissions, prompt=None, extra_pnginfo=None,
            dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if GUEST["session"] is None:
            GUEST["session"] = await GuestSession("prompt-reader-combo", guest_runtime_root=V2).start()
        guest = GUEST["session"]
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="prompt-reader-combo")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        values = []
        for item in (result.result or ()):
            values.append(await refs.resolve(item) if isinstance(item, _sdk.Ref) else item)
        return tuple(values)
    finally:
        scope.__exit__(None, None, None)


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return a.hex() == b.hex()
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def run_original(node_id, inputs):
    cls = ORIGINAL[node_id]
    return tuple(getattr(cls(), cls.FUNCTION)(**inputs))


async def returned_values():
    cases = [("SDLoraSelector", {"lora_name": name}) for name in FOLDERS["loras"]]
    cases.append(("SDLoraSelector", {"lora_name": "lora_b.safetensors", "last_lora": ["lora_a.safetensors"]}))
    for sampler, scheduler in (("euler", "normal"), ("dpmpp_2m", "karras")):
        cases.append(("SDTypeConverter", {"model_name": "model_a.safetensors", "sampler_name": sampler,
                                          "scheduler": scheduler}))
    for node_id, inputs in cases:
        expected = run_original(node_id, dict(inputs))
        actual = await run_v2(node_id, dict(inputs))
        record("C_returned_values", f"{node_id}:{json.dumps(inputs, sort_keys=True)}", same(expected, actual),
               expected=list(expected), actual=list(actual))


# --------------------------------------------------------------------------------------------------------------- #
# D. Negative controls
# --------------------------------------------------------------------------------------------------------------- #
def negative_controls():
    original = normal(v1_outputs(ORIGINAL["SDParameterGenerator"]))
    stripped = copy.deepcopy(original)
    stripped["output"][9] = "COMBO"
    record("D_negative_control", "object_info comparison flags an output without its options", original != stripped)
    from comfy_execution.validation import validate_node_input
    ksampler = core_nodes.NODE_CLASS_MAPPINGS["KSampler"].INPUT_TYPES()["required"]
    schedulers = ORIGINAL["SDParameterGenerator"].RETURN_TYPES[10]
    record("D_negative_control", "Core refuses a disjoint list link (schedulers into sampler_name)",
           validate_node_input(list(schedulers), ksampler["sampler_name"][0]) is False)


async def main():
    started = asyncio.get_running_loop().time()
    report = {
        "core": {"path": str(CORE),
                 "io_py_sha256": hashlib.sha256((CORE / "comfy_api/latest/_io.py").read_bytes()).hexdigest(),
                 "combo_output_reports_options": CORE_REPORTS_OPTIONS},
        "manifest_sha256": hashlib.sha256((V2 / "secure-nodes.json").read_bytes()).hexdigest(),
        "runtime_sha256": hashlib.sha256((V2 / "_secure_runtime.py").read_bytes()).hexdigest(),
        "classes": {"original": "pristine nodes.py imported in-process (package __init__ not run)",
                    "v2_served": "packdb host proxies from v2/secure-nodes.json",
                    "v2_values": "GuestSession (real guest) running the V2 classes"},
    }
    proxies, report["load_pack"] = load_proxies()
    try:
        if proxies is not None:
            report["object_info_counts"] = object_info_outputs(proxies)
            await prompt_validation(proxies)
        await returned_values()
        negative_controls()
    except Exception:  # noqa: BLE001
        report["harness_error"] = traceback.format_exc()[-3000:]
    finally:
        if GUEST["session"] is not None:
            await GUEST["session"].kill()  # GuestSession teardown: process-group kill and state scrub
        alive = [pid for pid in GUEST["pids"] if Path(f"/proc/{pid}").exists()]
        report["guest_cleanup"] = {"guest_pids": sorted(GUEST["pids"]), "alive_after_close": alive}
        shutil.rmtree(TMP, ignore_errors=True)
    totals = {}
    for row in ROWS:
        bucket = totals.setdefault(row["check"], {"ok": 0, "differ": 0, "known_difference": 0})
        bucket["ok" if row["ok"] else ("known_difference" if row.get("known_difference") else "differ")] += 1
    report["totals"] = totals
    report["seconds"] = round(asyncio.get_running_loop().time() - started, 1)
    report["rows"] = ROWS
    passed = (report["load_pack"]["ok"] and not report.get("harness_error")
              and all(row["ok"] or row.get("known_difference") for row in ROWS)
              and not report["guest_cleanup"]["alive_after_close"])
    report["verdict"] = ("EQUAL_TO_ORIGINAL_EXCEPT_KNOWN" if passed else
                         "LOAD_PACK_FAILED" if not report["load_pack"]["ok"] else "DIFFERS")
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "combo-outputs.json").write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: report.get(k) for k in ("core", "manifest_sha256", "load_pack", "object_info_counts",
                                                 "totals", "guest_cleanup", "verdict", "seconds")},
                     indent=1, default=str))
    if report.get("harness_error"):
        print(report["harness_error"])
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
