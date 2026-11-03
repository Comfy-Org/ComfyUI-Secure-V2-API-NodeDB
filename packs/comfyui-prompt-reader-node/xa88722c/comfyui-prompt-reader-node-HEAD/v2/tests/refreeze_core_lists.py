"""Refresh the Core-derived choice lists in v2/_schemas.json from the ORIGINAL on this Core (gate only).

The original builds its sampler and scheduler menus, and SDParameterGenerator's SAMPLER_NAME and SCHEDULER output
types, from Core's live lists (comfy.samplers.KSampler.SAMPLERS / SCHEDULERS: nodes.py:353-355, 775-776,
818-819, 1014-1018). _schemas.json froze them on an older Core. This tool imports the pristine nodes.py on the
mounted Core and rewrites only lists that ARE Core's lists there. A list is refreshed only when the frozen one
is an order-preserving subset of the original's (a Core that added choices); anything else is reported and left
unchanged. Host catalogue lists (checkpoint, VAE, config and LoRA menus, and the MODEL_NAME, VAE_NAME and
LORA_NAME outputs) are never touched: the host serves those from its model folders.

The original package's __init__.py deletes a directory under Core's web/extensions at import, so it is not run:
nodes.py is imported under a bare package, as its own relative imports need.

  DEPS=<piexif> run_in_gate.sh <pack> <pack>/v2/tests <results> refreeze_core_lists.py
  -> /results/_schemas.json and /results/refreeze.json
"""
import ast
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
PACK = Path(os.environ.get("PROMPTREADER_PACK", "/pack"))
RESULTS = Path(os.environ.get("PROMPTREADER_RESULTS", "/results"))
sys.path[:0] = [str(CORE)] + (["/deps"] if Path("/deps").is_dir() else [])

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import comfy.samplers  # noqa: E402

CATALOGUE_OUTPUTS = {("SDParameterGenerator", 0), ("SDParameterGenerator", 1), ("SDLoraSelector", 0)}


def import_original(name="prompt_reader_original"):
    """nodes.py of a pristine copy (without v2/), under a bare package: the package __init__.py does not run."""
    root = Path(tempfile.mkdtemp(prefix="refreeze-")) / PACK.name
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    package = types.ModuleType(name)
    package.__path__ = [str(root)]
    package.__package__ = name
    sys.modules[name] = package
    spec = importlib.util.spec_from_file_location(f"{name}.nodes", root / "nodes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS


def ordered_subset(old, new):
    position = 0
    for item in old:
        try:
            position = new.index(item, position) + 1
        except ValueError:
            return False
    return True


def main():
    original = import_original()
    core_lists = {"samplers": list(comfy.samplers.KSampler.SAMPLERS),
                  "schedulers": list(comfy.samplers.KSampler.SCHEDULERS)}
    source = PACK / "v2" / "_schemas.json"
    raw = source.read_text(encoding="utf-8")
    schemas = json.loads(raw)

    def dump(value):  # the established _schemas.json format
        return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def core_list(live):
        for name, values in core_lists.items():
            if list(live) == values:
                return name
        return None

    changes, kept, equal, skipped = [], [], [], []

    def consider(where, frozen, live):
        if frozen == live:
            equal.append(where)
            return frozen
        if ordered_subset(frozen, live):
            changes.append({"where": where, "frozen": len(frozen), "original": len(live),
                            "added": [item for item in live if item not in frozen]})
            return live
        kept.append({"where": where, "frozen_head": frozen[:5], "original_head": live[:5]})
        return frozen

    for node_id, row in schemas.items():
        cls = original[node_id]
        spec = cls.INPUT_TYPES()
        declared = {**(spec.get("required") or {}), **(spec.get("optional") or {})}
        for item in row["schema"]["inputs"]:
            name = item["attrs"].get("id")
            if item["io_type"] != "COMBO" or name not in declared:
                continue
            live = declared[name][0]
            if not isinstance(live, (list, tuple)):
                continue
            which = core_list(live)
            if which is None:
                skipped.append(f"{node_id} / input {name}")
                continue
            item["attrs"]["options"] = consider(f"{node_id} / input {name} ({which})", item["attrs"]["options"],
                                                list(live))
        for index, output in enumerate(row["schema"]["outputs"]):
            frozen_type = output["io_type"]
            if not (frozen_type.startswith("[") and frozen_type.endswith("]")):
                continue
            if (node_id, index) in CATALOGUE_OUTPUTS:
                skipped.append(f"{node_id} / output {index} (host catalogue, frozen as {frozen_type})")
                continue
            live = list(cls.RETURN_TYPES[index])
            which = core_list(live)
            if which is None:
                kept.append({"where": f"{node_id} / output {index}", "reason": "not one of Core's lists"})
                continue
            frozen = ast.literal_eval(frozen_type)
            output["io_type"] = str(consider(f"{node_id} / output {index} ({which})", frozen, live))
    text = dump(schemas)
    report = {
        "core_io_sha256": hashlib.sha256((CORE / "comfy_api/latest/_io.py").read_bytes()).hexdigest(),
        "core_samplers_sha256": hashlib.sha256((CORE / "comfy/samplers.py").read_bytes()).hexdigest(),
        "core_lists": {name: len(values) for name, values in core_lists.items()},
        "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "source_format_roundtrip": raw == dump(json.loads(raw)),
        "refreshed_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "changes": changes,
        "already_equal": equal,
        "not_core_lists_untouched": skipped,
        "left_unchanged_not_a_superset": kept,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "_schemas.json").write_text(text, encoding="utf-8")
    (RESULTS / "refreeze.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0 if report["source_format_roundtrip"] and not kept else 1


if __name__ == "__main__":
    sys.exit(main())
