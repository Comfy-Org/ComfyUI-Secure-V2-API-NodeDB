"""Freeze every ORIGINAL RES4LYF node declaration at 057a913e on core 6257422b (gate only).

Writes /results/res4lyf-frozen.json: for each registered id
  * api 'v1': the V1 declaration (INPUT_TYPES, RETURN_TYPES, ...), JSON-encoded with tags for non-JSON values
  * api 'v3': the V3 schema's attributes and its Input/Output objects (class path + __dict__, tagged recursively)
  * node_info: what core serves at /object_info for the original (server.py node_info logic), for the V2 check
Run: DEPS=<deps-orig> run_in_gate.sh <RES4LYF-HEAD> <this dir> <out> freeze_all.py
"""
import enum
import json
import math
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

from comfy_api.latest import io  # noqa: E402
from comfy_api.latest._io import _ComfyNodeBaseInternal  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="res4-freeze-all-"))
shutil.copytree("/pack", TMP / "RES4LYF", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
import importlib  # noqa: E402

RES = importlib.import_module("RES4LYF")
PROBLEMS = []


def enc(value, where):
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return {"$float": repr(value)}
    if isinstance(value, enum.Enum):
        return {"$enum": type(value).__name__, "name": value.name, "value": enc(value.value, where)}
    if isinstance(value, tuple):
        return {"$tuple": [enc(v, where) for v in value]}
    if isinstance(value, list):
        out = [enc(v, where) for v in value]
        if type(value) is not list:
            return {"$list": out, "class": type(value).__name__}
        return out
    if isinstance(value, dict):
        return {"$dict": [[enc(k, where), enc(v, where)] for k, v in value.items()]}
    if isinstance(value, (io.Input, io.Output)) or type(value).__module__.endswith("_io"):
        return enc_io(value, where)
    PROBLEMS.append({"where": where, "type": f"{type(value).__module__}.{type(value).__qualname__}",
                     "repr": repr(value)[:200]})
    return {"$opaque": f"{type(value).__module__}.{type(value).__qualname__}"}


def io_class_path(obj):
    cls = type(obj)
    parent = getattr(cls, "Parent", None)
    qual = cls.__qualname__
    return {"qualname": qual, "parent": getattr(parent, "__name__", None),
            "parent_io_type": getattr(parent, "io_type", None), "module": cls.__module__}


def enc_io(obj, where):
    return {"$io": io_class_path(obj), "attrs": {k: enc(v, f"{where}.{k}") for k, v in vars(obj).items()}}


def node_info_v1(node_id, cls):
    """server.py node_info for a non-V3 class (core 6257422b server.py:839-...)."""
    if issubclass(cls, _ComfyNodeBaseInternal):
        return cls.GET_NODE_INFO_V1()
    info = {}
    info['input'] = cls.INPUT_TYPES()
    info['input_order'] = {key: list(value.keys()) for (key, value) in cls.INPUT_TYPES().items()}
    _return_types = ["*" if isinstance(rt, str) and rt == "*" else rt for rt in cls.RETURN_TYPES]
    info['output'] = _return_types
    info['output_is_list'] = cls.OUTPUT_IS_LIST if hasattr(cls, 'OUTPUT_IS_LIST') else [False] * len(cls.RETURN_TYPES)
    info['output_name'] = cls.RETURN_NAMES if hasattr(cls, 'RETURN_NAMES') else info['output']
    info['name'] = node_id
    info['display_name'] = RES.NODE_DISPLAY_NAME_MAPPINGS.get(node_id, node_id)
    info['description'] = cls.DESCRIPTION if hasattr(cls, 'DESCRIPTION') else ''
    info['python_module'] = getattr(cls, "RELATIVE_PYTHON_MODULE", "nodes")
    info['category'] = 'sd'
    info['output_node'] = bool(getattr(cls, 'OUTPUT_NODE', False) is True)
    if hasattr(cls, 'CATEGORY'):
        info['category'] = cls.CATEGORY
    if hasattr(cls, 'OUTPUT_TOOLTIPS'):
        info['output_tooltips'] = cls.OUTPUT_TOOLTIPS
    if getattr(cls, "DEPRECATED", False):
        info['deprecated'] = True
    if getattr(cls, "EXPERIMENTAL", False):
        info['experimental'] = True
    if hasattr(cls, 'API_NODE'):
        info['api_node'] = cls.API_NODE
    info['search_aliases'] = getattr(cls, 'SEARCH_ALIASES', [])
    return info


def main():
    nodes = {}
    counts = {"v1": 0, "v3": 0}
    for node_id in sorted(RES.NODE_CLASS_MAPPINGS):
        cls = RES.NODE_CLASS_MAPPINGS[node_id]
        row = {"class": cls.__name__, "module": cls.__module__.replace("RES4LYF.", "", 1),
               "display_name": RES.NODE_DISPLAY_NAME_MAPPINGS.get(node_id)}
        if issubclass(cls, _ComfyNodeBaseInternal):
            counts["v3"] += 1
            schema = cls.GET_SCHEMA()
            attrs = {k: enc(v, f"{node_id}.schema.{k}") for k, v in vars(schema).items()
                     if k not in ("inputs", "outputs", "hidden")}
            row["api"] = "v3"
            row["schema"] = {"attrs": attrs,
                             "inputs": [enc_io(i, f"{node_id}.in.{i.id}") for i in schema.inputs],
                             "outputs": [enc_io(o, f"{node_id}.out.{n}") for n, o in enumerate(schema.outputs)],
                             "hidden": [h.name for h in schema.hidden]}
        else:
            counts["v1"] += 1
            row["api"] = "v1"
            v1 = {"INPUT_TYPES": enc(cls.INPUT_TYPES(), f"{node_id}.INPUT_TYPES")}
            for attr in ("RETURN_TYPES", "RETURN_NAMES", "OUTPUT_IS_LIST", "OUTPUT_TOOLTIPS", "OUTPUT_NODE",
                         "CATEGORY", "DESCRIPTION", "DEPRECATED", "EXPERIMENTAL", "INPUT_IS_LIST", "FUNCTION",
                         "SEARCH_ALIASES", "NOT_IDEMPOTENT", "API_NODE"):
                if hasattr(cls, attr):
                    v1[attr] = enc(getattr(cls, attr), f"{node_id}.{attr}")
            row["v1"] = v1
        row["node_info"] = enc(node_info_v1(node_id, cls), f"{node_id}.node_info")
        nodes[node_id] = row
    doc = {"pin": "057a913ed3c04cbfb756e1a3dbfc398a6bd4044f", "counts": counts, "problems": PROBLEMS,
           "nodes": nodes}
    out = Path("/results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "res4lyf-frozen.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"counts": counts, "problems": len(PROBLEMS)}, indent=1))
    print("v3 nodes:", [k for k, v in nodes.items() if v["api"] == "v3"])
    for p in PROBLEMS[:30]:
        print("PROBLEM", p)


if __name__ == "__main__":
    main()
