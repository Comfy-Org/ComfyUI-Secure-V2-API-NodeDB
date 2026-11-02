"""Tier-1 parity for comfyui_bitsandbytes_nf4 (pin 6c523bf1): pristine vs v2, in the gate.

    DEPS=<unpacked bitsandbytes 0.50.2 wheel> run_in_gate.sh \
        <snapshot dir holding ComfyUI_bitsandbytes_NF4-HEAD> <.../v2/tests> <results dir> \
        test_comfyui_bitsandbytes_nf4_parity.py

The pristine pack needs bitsandbytes only to import (its module scope builds
the 4-bit operations), so the pinned wheel is mounted read-only at /deps.
Nothing here loads a checkpoint: the original node needs a real bitsandbytes
NF4/FP4 checkpoint (12 GB for Flux), which is tier 2 (see TIER2.json).

The one node is REFUSED-AS-DESIGNED in v2. This test proves that:
  * the registered schema is the original's (/object_info fields, id, input,
    outputs, category), through both the guest class and the host proxy built
    from secure-nodes.json, including the host-filled checkpoint menu;
  * the refusal is exact and named, at queue time (core validation) and at
    execute;
  * the manifest is the encoder's output, the guest module imports nothing
    host-only, and the pristine files are untouched;
  * two negative controls (perturbed refusal, perturbed schema) turn it red.

Writes /results/parity.json; exits 1 on any failed check.
"""

import ast
import asyncio
import copy
import hashlib
import json
import platform
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]
if Path("/deps").is_dir():
    sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402  (ComfyUI's nodes.py, not the pack)
import execution  # noqa: E402
from comfy_api.latest import io  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from encode_manifest import build_manifest, load_package, pack_head, serialize  # noqa: E402

PACK_SLUG = "comfyui_bitsandbytes_nf4"
NODE_ID = "CheckpointLoaderNF4"
PIN = "6c523bf1ee37900757ee538e6683f1312b8f425c"
# Git blob ids of the pristine files at the pin (INTAKE.json).
PRISTINE_BLOBS = {
    "LICENSE.txt": "62713ef770425f6bb892f5a87c05b2c277064df4",
    "README.md": "be7a1028d3c220765a692e9568d9b48415ad79a0",
    "__init__.py": "8b72c7f92a09877c3d88788a78375070c069f3de",
    "requirements.txt": "f2b85c54209779dc1a201afb4dcc259b428ef099",
}
EXPECTED_REFUSAL = (
    "comfyui_bitsandbytes_nf4/CheckpointLoaderNF4 is not yet converted to Secure "
    "Nodes V2: it loads bitsandbytes NF4/FP4 (4-bit) checkpoints, which needs "
    "bitsandbytes 4-bit layers inside the host's model loader, and the Secure "
    "Nodes model loader has no 4-bit option yet. Use a GGUF or FP8 version of "
    "the model with the standard loaders instead."
)
CKPT_DIR = Path("/tmp/nf4-parity-checkpoints")
CKPT_NAMES = [
    "flux1-dev-bnb-nf4-v2.safetensors",
    "sub/flux1-schnell-bnb-nf4.safetensors",
    "plain-sd15.ckpt",
    "z-model.sft",
]
# Identity-style /object_info fields compared exactly between the original
# and v2. python_module is the mount path and differs by design.
INFO_FIELDS = ("name", "display_name", "category", "description", "output",
               "output_is_list", "output_name", "output_node", "is_input_list",
               "input_order", "has_intermediate_output")
# Fields where None, missing, [] and all-None lists all mean "not set".
UNSET_FIELDS = ("deprecated", "experimental", "dev_only", "api_node",
                "search_aliases", "output_tooltips", "essentials_category",
                "price_badge", "output_matchtypes")

checks = []


def record(name, ok, detail=None, cases=1):
    checks.append({"check": name, "ok": bool(ok), "cases": cases,
                   "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))
    return ok


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def v1_node_info(node_class: str, obj_class, display_mappings: dict) -> dict:
    """Core's /object_info for a V1 class: server.py:839-884 at ComfyUI 6257422b."""
    info = {}
    info["input"] = obj_class.INPUT_TYPES()
    info["input_order"] = {key: list(value.keys())
                           for (key, value) in obj_class.INPUT_TYPES().items()}
    info["is_input_list"] = getattr(obj_class, "INPUT_IS_LIST", False)
    info["output"] = obj_class.RETURN_TYPES
    info["output_is_list"] = (obj_class.OUTPUT_IS_LIST
                              if hasattr(obj_class, "OUTPUT_IS_LIST")
                              else [False] * len(obj_class.RETURN_TYPES))
    info["output_name"] = (obj_class.RETURN_NAMES
                           if hasattr(obj_class, "RETURN_NAMES") else info["output"])
    info["name"] = node_class
    info["display_name"] = display_mappings.get(node_class, node_class)
    info["description"] = (obj_class.DESCRIPTION
                           if hasattr(obj_class, "DESCRIPTION") else "")
    info["python_module"] = getattr(obj_class, "RELATIVE_PYTHON_MODULE", "nodes")
    info["category"] = "sd"
    info["output_node"] = bool(hasattr(obj_class, "OUTPUT_NODE")
                               and obj_class.OUTPUT_NODE is True)
    info["has_intermediate_output"] = bool(
        hasattr(obj_class, "HAS_INTERMEDIATE_OUTPUT")
        and obj_class.HAS_INTERMEDIATE_OUTPUT is True)
    if hasattr(obj_class, "CATEGORY"):
        info["category"] = obj_class.CATEGORY
    if hasattr(obj_class, "OUTPUT_TOOLTIPS"):
        info["output_tooltips"] = obj_class.OUTPUT_TOOLTIPS
    if getattr(obj_class, "DEPRECATED", False):
        info["deprecated"] = True
    if getattr(obj_class, "EXPERIMENTAL", False):
        info["experimental"] = True
    if getattr(obj_class, "DEV_ONLY", False):
        info["dev_only"] = True
    if hasattr(obj_class, "API_NODE"):
        info["api_node"] = obj_class.API_NODE
    info["search_aliases"] = getattr(obj_class, "SEARCH_ALIASES", [])
    if hasattr(obj_class, "ESSENTIALS_CATEGORY"):
        info["essentials_category"] = obj_class.ESSENTIALS_CATEGORY
    return info


def plain(value):
    """Tuples to lists, so V1 tuples compare equal to V2 lists."""
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    return value


def unset(value) -> bool:
    if value is None or value is False or value == [] or value == {}:
        return True
    return isinstance(value, (list, tuple)) and all(item is None for item in value)


def info_differences(v1: dict, v2: dict) -> list:
    diffs = []
    for field in INFO_FIELDS:
        if plain(v1.get(field)) != plain(v2.get(field)):
            diffs.append((field, plain(v1.get(field)), plain(v2.get(field))))
    for field in UNSET_FIELDS:
        a, b = v1.get(field), v2.get(field)
        if not (unset(a) and unset(b)) and plain(a) != plain(b):
            diffs.append((field, plain(a), plain(b)))
    # Input names, kinds and widget options, minus the dropdown list itself.
    for section in ("required", "optional", "hidden"):
        a = v1["input"].get(section, {})
        b = v2["input"].get(section, {})
        if list(a) != list(b):
            diffs.append((f"input.{section}", list(a), list(b)))
            continue
        for name in a:
            ta, tb = a[name], b[name]
            kind_a = "COMBO" if isinstance(ta[0], (list, tuple)) else ta[0]
            if kind_a != tb[0]:
                diffs.append((f"input.{section}.{name}.type", kind_a, tb[0]))
            opts_a = dict(ta[1]) if len(ta) > 1 else {}
            opts_b = dict(tb[1]) if len(tb) > 1 else {}
            opts_b.pop("options", None)
            opts_b.pop("remote", None)
            # A V3 Combo always serializes its default multiselect=False; a V1
            # combo omits the key. Both mean a single-choice dropdown.
            if opts_b.get("multiselect") is False and "multiselect" not in opts_a:
                opts_b.pop("multiselect")
            opts_b = {k: v for k, v in opts_b.items() if v is not None}
            if plain(opts_a) != plain(opts_b):
                diffs.append((f"input.{section}.{name}.options", opts_a, opts_b))
    return diffs


def combo_options(info: dict, name: str):
    entry = info["input"]["required"][name]
    if isinstance(entry[0], (list, tuple)):
        return list(entry[0])
    return list(entry[1].get("options", []))


def main() -> int:
    head = pack_head()
    v2 = head / "v2"
    environment = {"python": platform.python_version(), "pack_head": str(head)}

    # 1. Pristine files are the pinned upstream bytes; v2 keeps the copies.
    for name, blob in PRISTINE_BLOBS.items():
        data = (head / name).read_bytes()
        record(f"pristine/{name}", blob_id(data) == blob, blob_id(data))
    for name in ("LICENSE.txt", "README.md", "requirements.txt"):
        record(f"v2-copy/{name}", (v2 / name).read_bytes() == (head / name).read_bytes())

    # 2. The guest module imports nothing host-only.
    allowed = {"comfy_api.latest"}
    for name in ("__init__.py", "nodes.py"):
        tree = ast.parse((v2 / name).read_bytes())
        bad = []
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                bad += [alias.name for alias in item.names]
            elif isinstance(item, ast.ImportFrom) and item.level == 0:
                if item.module not in allowed:
                    bad.append(item.module)
        record(f"guest-imports/{name}", not bad, bad)

    # 3. Checkpoint menu fixture: names only, empty files, never loaded.
    for name in CKPT_NAMES:
        path = CKPT_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    folder_paths.add_model_folder_path("checkpoints", str(CKPT_DIR), is_default=True)

    # 4. Load both packs. The pristine module scope needs bitsandbytes.
    try:
        old = load_package("nf4_pristine", head)
        import bitsandbytes
        environment["bitsandbytes"] = bitsandbytes.__version__
        record("pristine-imports", True, f"bitsandbytes {bitsandbytes.__version__}")
    except Exception:
        record("pristine-imports", False, traceback.format_exc())
        return finish(environment)
    new = load_package("nf4_v2", v2)
    new_nodes = sys.modules["nf4_v2.nodes"]
    old_cls = old.NODE_CLASS_MAPPINGS[NODE_ID]
    new_cls = new.NODE_CLASS_MAPPINGS[NODE_ID]

    manifest = json.loads((v2 / "secure-nodes.json").read_bytes())
    record("ids", list(old.NODE_CLASS_MAPPINGS) == list(new.NODE_CLASS_MAPPINGS)
           == list(manifest["nodes"]) == [NODE_ID],
           [list(old.NODE_CLASS_MAPPINGS), list(new.NODE_CLASS_MAPPINGS),
            list(manifest["nodes"])])
    record("pristine-display-mappings-absent",
           not hasattr(old, "NODE_DISPLAY_NAME_MAPPINGS"))

    # 5. The committed manifest is the encoder's output.
    regenerated = serialize(build_manifest(v2, "nf4_v2_regen"))
    record("manifest-is-encoder-output",
           regenerated == (v2 / "secure-nodes.json").read_text(),
           "secure-nodes.json differs from the encoder")

    # 6. /object_info: original vs guest class vs host proxy.
    v1_info = v1_node_info(NODE_ID, old_cls, getattr(old, "NODE_DISPLAY_NAME_MAPPINGS", {}))
    v2_info = new_cls.GET_NODE_INFO_V1()
    record("object-info/guest-class", not info_differences(v1_info, v2_info),
           info_differences(v1_info, v2_info), cases=len(INFO_FIELDS) + len(UNSET_FIELDS) + 1)

    loaded = packdb.load_pack(Path("/pack"), mount_name="custom_nodes.nf4_parity_proxy",
                              pack_id=f"{PACK_SLUG}/x{PIN[:7]}")
    proxy = loaded.node_mappings[NODE_ID]
    proxy_info = proxy.GET_NODE_INFO_V1()
    record("object-info/host-proxy", not info_differences(v1_info, proxy_info),
           info_differences(v1_info, proxy_info), cases=len(INFO_FIELDS) + len(UNSET_FIELDS) + 1)
    record("proxy/display-mapping", loaded.display_mappings == {NODE_ID: NODE_ID},
           loaded.display_mappings)
    record("proxy/flags", proxy.SDK_REFS is True and tuple(proxy.SDK_PERMISSIONS) == (),
           [proxy.SDK_REFS, proxy.SDK_PERMISSIONS])

    # 7. Checkpoint menu: the host fills the same names the original lists.
    v1_menu = combo_options(v1_info, "ckpt_name")
    proxy_menu = combo_options(proxy_info, "ckpt_name")
    expected_menu = folder_paths.get_filename_list("checkpoints")
    record("ckpt-menu/original-lists-fixture", set(CKPT_NAMES) <= set(v1_menu), v1_menu)
    record("ckpt-menu/host-proxy-equals-original", proxy_menu == v1_menu == list(expected_menu),
           [v1_menu, proxy_menu], cases=len(v1_menu))
    record("ckpt-menu/guest-class-sentinel", combo_options(v2_info, "ckpt_name") == [],
           combo_options(v2_info, "ckpt_name"))
    remote = v2_info["input"]["required"]["ckpt_name"][1].get("remote")
    record("ckpt-menu/remote-route", remote == {"route": "/models/checkpoints",
           "refresh_button": True, "control_after_refresh": "first"}, remote)

    # 8. The refusal: exact, named, at validate and at execute.
    record("refusal/module-text", new_nodes.REFUSAL == EXPECTED_REFUSAL, new_nodes.REFUSAL)
    values = list(v1_menu) + ["", "missing.safetensors"]
    got = [new_cls.validate_inputs(ckpt_name=value) for value in values]
    record("refusal/validate_inputs", all(item == EXPECTED_REFUSAL for item in got),
           got, cases=len(values))
    raised = []
    for value in values:
        try:
            asyncio.run(new_cls.execute(ckpt_name=value))
            raised.append(None)
        except Exception as error:  # noqa: BLE001
            raised.append((type(error).__name__, isinstance(error, RuntimeError), str(error)))
    record("refusal/execute-named-error",
           all(item == ("NF4LoaderUnavailableError", True, EXPECTED_REFUSAL) for item in raised),
           raised, cases=len(values))

    # 9. Queue-time result in core: what the user sees for a saved workflow.
    previous = core_nodes.NODE_CLASS_MAPPINGS.get(NODE_ID)
    core_nodes.NODE_CLASS_MAPPINGS[NODE_ID] = new_cls
    try:
        prompt = {"4": {"class_type": NODE_ID,
                        "inputs": {"ckpt_name": "flux1-dev-bnb-nf4-v2.safetensors"}}}
        ok, errors, _ = asyncio.run(
            execution.validate_inputs("nf4-parity", prompt, "4", {}))
        record("core-validation/refused", ok is False and errors == [{
            "type": "custom_validation_failed",
            "message": "Custom validation failed for node",
            "details": f"ckpt_name - {EXPECTED_REFUSAL}",
            "extra_info": {"input_name": "ckpt_name"}}], errors)
        prompt["4"]["inputs"]["ckpt_name"] = "not-in-menu.safetensors"
        ok, errors, _ = asyncio.run(
            execution.validate_inputs("nf4-parity", prompt, "4", {}))
        record("core-validation/refusal-not-masked-by-menu-check",
               ok is False and [e["type"] for e in errors] == ["custom_validation_failed"],
               errors)
    finally:
        if previous is None:
            core_nodes.NODE_CLASS_MAPPINGS.pop(NODE_ID, None)
        else:
            core_nodes.NODE_CLASS_MAPPINGS[NODE_ID] = previous

    # 10. The host proxy never runs pack code itself.
    host_refusals = []
    for method in ("validate_inputs", "execute"):
        try:
            result = getattr(proxy, method)(ckpt_name="x")
            if asyncio.iscoroutine(result):
                asyncio.run(result)
            host_refusals.append((method, None))
        except Exception as error:  # noqa: BLE001
            host_refusals.append((method, str(error)))
    record("proxy/host-refuses-local-calls",
           all(text == "third-party node proxy cannot execute in the host"
               for _, text in host_refusals), host_refusals, cases=2)

    # 11. Negative controls: each perturbation must turn a comparator red.
    controls = {}
    saved = new_nodes.REFUSAL
    new_nodes.REFUSAL = EXPECTED_REFUSAL + " (perturbed)"
    try:
        controls["perturbed-refusal-detected"] = (
            new_cls.validate_inputs(ckpt_name=values[0]) != EXPECTED_REFUSAL)
    finally:
        new_nodes.REFUSAL = saved
    original_define = new_cls.__dict__["define_schema"]

    def perturbed(cls):
        schema = original_define.__func__(cls)
        schema.outputs[0].display_name = "MODEL_PERTURBED"
        return schema

    new_cls.define_schema = classmethod(perturbed)
    try:
        controls["perturbed-schema-detected"] = bool(
            info_differences(v1_info, new_cls.GET_NODE_INFO_V1()))
    finally:
        new_cls.define_schema = original_define
    controls["schema-restored"] = not info_differences(v1_info, new_cls.GET_NODE_INFO_V1())
    for name, ok in controls.items():
        record(f"negative-control/{name}", ok)
    return finish(environment, controls)


def finish(environment, controls=None) -> int:
    failed = [item for item in checks if not item["ok"]]
    cases = sum(item["cases"] for item in checks
                if not item["check"].startswith("negative-control/"))
    verdict = "REFUSED-AS-DESIGNED" if not failed else "MISMATCH"
    result = {
        "pack": PACK_SLUG,
        "pin": PIN,
        "nodes": {NODE_ID: {
            "verdict": verdict,
            "cases": cases,
            "schema": "EXACT" if not any(
                item["check"].startswith(("object-info/", "ckpt-menu/", "ids"))
                for item in failed) else "MISMATCH",
            "original_execution": "NOT-RUNNABLE-CPU (needs a real bitsandbytes "
                                  "NF4/FP4 checkpoint, 12 GB for Flux, over the "
                                  "gate's 4-8 GiB; upstream targets CUDA; see "
                                  "TIER2.json)",
        }},
        "negative_control": controls,
        "checks": checks,
        "failed": [item["check"] for item in failed],
        "environment": environment,
    }
    Path("/results/parity.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": verdict, "cases": cases, "failed": result["failed"]}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
