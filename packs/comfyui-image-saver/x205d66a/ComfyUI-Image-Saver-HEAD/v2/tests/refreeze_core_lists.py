"""Refresh the Core-derived choice lists in v2/_schemas.json from the ORIGINAL on this Core (gate only).

The original builds its sampler/scheduler menus and selector output types from Core's live lists
(comfy.samplers.KSampler.SAMPLERS / SCHEDULERS, plus the pack's own extras: nodes_selectors.py:4-5).
_schemas.json froze them on an older Core. This tool imports the pristine package on the mounted Core and
rewrites only those lists, so every COMBO input and every list-typed output matches what the original
exposes on this Core. A list is refreshed only when the frozen one is an order-preserving subset of the
original's (a Core that added choices); anything else is reported and left unchanged. Catalogue inputs
(checkpoint/UNet names, served from the host's model folders) are not touched.

  run_in_gate.sh <pack> <pack>/v2/tests <results> refreeze_core_lists.py
  -> /results/_schemas.json and /results/refreeze.json
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
PACK = Path(os.environ.get("IMAGESAVER_PACK", "/pack"))
RESULTS = Path(os.environ.get("IMAGESAVER_RESULTS", "/results"))
sys.path[:0] = [str(CORE)] + (["/deps"] if Path("/deps").is_dir() else [])

from comfy.cli_args import args  # noqa: E402

args.cpu = True
CATALOGUE_INPUTS = {("Checkpoint Loader with Name (Image Saver)", "ckpt_name"),
                    ("UNet loader with Name (Image Saver)", "unet_name")}


def import_original():
    root = Path(tempfile.mkdtemp(prefix="refreeze-")) / "ComfyUI-Image-Saver-HEAD"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    spec = importlib.util.spec_from_file_location("imagesaver_original", root / "__init__.py",
                                                  submodule_search_locations=[str(root)])
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
    source = PACK / "v2" / "_schemas.json"
    raw = source.read_text(encoding="utf-8")
    schemas = json.loads(raw)

    def dump(value):  # the established _schemas.json format
        return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    changes, kept = [], []

    def consider(where, frozen, live):
        if frozen == live:
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
            if item["io_type"] != "COMBO" or (node_id, name) in CATALOGUE_INPUTS:
                continue
            live = declared[name][0]
            if not isinstance(live, (list, tuple)):
                continue
            item["attrs"]["options"] = consider(f"{node_id} / input {name}", item["attrs"]["options"], list(live))
        for index, output in enumerate(row["schema"]["outputs"]):
            frozen_type = output["io_type"]
            if not (frozen_type.startswith("[") and frozen_type.endswith("]")):
                continue
            live = cls.RETURN_TYPES[index]
            import ast
            frozen = ast.literal_eval(frozen_type)
            output["io_type"] = str(consider(f"{node_id} / output {index}", frozen, list(live)))
    text = dump(schemas)
    report = {
        "core_io_sha256": hashlib.sha256((CORE / "comfy_api/latest/_io.py").read_bytes()).hexdigest(),
        "core_samplers_sha256": hashlib.sha256((CORE / "comfy/samplers.py").read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "source_format_roundtrip": raw == dump(json.loads(raw)),
        "refreshed_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "changes": changes,
        "left_unchanged_not_a_superset": kept,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "_schemas.json").write_text(text, encoding="utf-8")
    (RESULTS / "refreeze.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0 if report["source_format_roundtrip"] and not kept else 1


if __name__ == "__main__":
    sys.exit(main())
