"""Freeze ORIGINAL ClownsharKSampler_Beta's option lists and V1 projection (gate only).

Writes /results/clown-frozen.json:
  sampler_names, default_sampler, schedulers -- exactly what the original's define_schema evaluates at import on
  core 6257422b with no other pack installed; and the V1 projection (INPUT_TYPES, RETURN_TYPES, RETURN_NAMES,
  OUTPUT_IS_LIST, CATEGORY, display name) that the V2 schema must reproduce.
Run: DEPS=<deps-orig> run_in_gate.sh <RES4LYF-HEAD> <this dir> <out> freeze_clown.py
"""
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE)]
if Path("/deps").is_dir():
    sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import server  # noqa: E402
from aiohttp import web  # noqa: E402

server.PromptServer.instance = types.SimpleNamespace(
    routes=web.RouteTableDef(), supports={"custom_nodes_from_web"}, send_sync=lambda *a, **k: None,
    client_id=None, last_node_id=None)

TMP = Path(tempfile.mkdtemp(prefix="res4-freeze-"))
shutil.copytree("/pack", TMP / "RES4LYF", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
import importlib  # noqa: E402

RES = importlib.import_module("RES4LYF")
SAMPLERS = importlib.import_module("RES4LYF.beta.samplers")


def jsonable(value):
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return f"<{type(value).__name__}>"


def main():
    cls = RES.NODE_CLASS_MAPPINGS["ClownsharKSampler_Beta"]
    schema = cls.GET_SCHEMA()
    inputs = {item.id: item for item in schema.inputs}
    doc = {
        "sampler_names": list(inputs["sampler_name"].options),
        "sampler_names_type": type(inputs["sampler_name"].options).__name__,
        "default_sampler": inputs["sampler_name"].default,
        "schedulers": list(inputs["scheduler"].options),
        "v1": {
            "INPUT_TYPES": jsonable(cls.INPUT_TYPES()),
            "RETURN_TYPES": jsonable(cls.RETURN_TYPES),
            "RETURN_NAMES": jsonable(cls.RETURN_NAMES),
            "OUTPUT_IS_LIST": jsonable(cls.OUTPUT_IS_LIST),
            "CATEGORY": cls.CATEGORY,
            "display_name": schema.display_name,
            "node_info": jsonable(cls.GET_NODE_INFO_V1()),
        },
        "registered_ids": sorted(RES.NODE_CLASS_MAPPINGS),
    }
    out = Path("/results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "clown-frozen.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("sampler_names_type", "default_sampler", "schedulers")}, indent=1))
    print("sampler_names", len(doc["sampler_names"]), doc["sampler_names"][:8])
    print("registered", len(doc["registered_ids"]))


if __name__ == "__main__":
    main()
