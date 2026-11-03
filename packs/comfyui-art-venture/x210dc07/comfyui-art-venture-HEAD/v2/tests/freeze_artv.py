"""Freeze every ORIGINAL comfyui-art-venture node declaration at 210dc072 on the gate core (gate only).

Writes /results/artv-frozen.json: for each registered id the V1 declaration (INPUT_TYPES, RETURN_TYPES, ...),
JSON-encoded with tags for non-JSON values, plus the node info core serves for it (server.py node_info logic).
Also records which classes define IS_CHANGED / VALIDATE_INPUTS / CHECK_LAZY_STATUS. Import failures of the
original's submodules are recorded, not hidden.
Run: DEPS=<deps> run_in_gate.sh <comfyui-art-venture-HEAD> <this dir> <out> freeze_artv.py
"""
import enum
import json
import math
import os
import shutil
import sys
import tempfile
import traceback
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

PIN = "210dc072b1f103f91be18a33bdeb13ab315aaae5"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_stubs  # noqa: E402

STUB_ROOTS = ["cv2", "timm", "fairscale", "pycocoevalcap", "qrcode", "pytorch_lightning", "kornia",
              "segment_anything", "omegaconf", "boto3", "botocore", "transformers", "skimage", "onnxruntime"]
STUBBED = import_stubs.install(STUB_ROOTS)
TMP = Path(tempfile.mkdtemp(prefix="artv-freeze-"))

# Model-menu probes: every model folder holds one probe file BEFORE the original is imported (some lists are built in
# class bodies). A frozen option list that contains a folder's probe name was built from that folder's listing.
import folder_paths  # noqa: E402

PROBES = {}
for folder, (paths, extensions) in list(folder_paths.folder_names_and_paths.items()):
    if folder in ("custom_nodes", "configs"):
        continue
    known = sorted(e for e in (extensions or ()) if e)
    ext = ".safetensors" if (not known or ".safetensors" in known) else known[0]
    probe_dir = TMP / "models" / folder
    probe_dir.mkdir(parents=True, exist_ok=True)
    name = f"__probe_{folder}__{ext}"
    (probe_dir / name).write_bytes(b"")
    folder_paths.folder_names_and_paths[folder] = ([str(probe_dir)], extensions)
    PROBES[name] = folder
folder_paths.filename_list_cache.clear() if hasattr(folder_paths, "filename_list_cache") else None
shutil.copytree("/pack", TMP / "comfyui_art_venture", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
import importlib  # noqa: E402

try:
    PACKAGE = importlib.import_module("comfyui_art_venture")
    IMPORT_ERROR = None
except Exception:  # noqa: BLE001
    PACKAGE = None
    IMPORT_ERROR = traceback.format_exc()[-3000:]
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
    PROBLEMS.append({"where": where, "type": f"{type(value).__module__}.{type(value).__qualname__}",
                     "repr": repr(value)[:200]})
    return {"$opaque": f"{type(value).__module__}.{type(value).__qualname__}"}


def node_info_v1(node_id, cls, display):
    """server.py node_info for a non-V3 class."""
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
    info['display_name'] = display.get(node_id, node_id)
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
    out = Path("/results")
    out.mkdir(parents=True, exist_ok=True)
    if PACKAGE is None:
        (out / "artv-frozen.json").write_text(json.dumps({"pin": PIN, "import_error": IMPORT_ERROR}, indent=1) + "\n")
        print(IMPORT_ERROR)
        return 1
    display = dict(getattr(PACKAGE, "NODE_DISPLAY_NAME_MAPPINGS", {}))
    nodes = {}
    for node_id in sorted(PACKAGE.NODE_CLASS_MAPPINGS):
        cls = PACKAGE.NODE_CLASS_MAPPINGS[node_id]
        row = {"class": cls.__name__, "module": cls.__module__.replace("comfyui_art_venture.", "", 1),
               "display_name": display.get(node_id),
               "methods": {m: hasattr(cls, m) for m in ("IS_CHANGED", "VALIDATE_INPUTS", "check_lazy_status")}}
        try:
            if issubclass(cls, _ComfyNodeBaseInternal):
                row["api"] = "v3"
            else:
                row["api"] = "v1"
                v1 = {"INPUT_TYPES": enc(cls.INPUT_TYPES(), f"{node_id}.INPUT_TYPES")}
                for attr in ("RETURN_TYPES", "RETURN_NAMES", "OUTPUT_IS_LIST", "OUTPUT_TOOLTIPS", "OUTPUT_NODE",
                             "CATEGORY", "DESCRIPTION", "DEPRECATED", "EXPERIMENTAL", "INPUT_IS_LIST", "FUNCTION",
                             "SEARCH_ALIASES", "NOT_IDEMPOTENT", "API_NODE"):
                    if hasattr(cls, attr):
                        v1[attr] = enc(getattr(cls, attr), f"{node_id}.{attr}")
                row["v1"] = v1
            row["node_info"] = enc(node_info_v1(node_id, cls, display), f"{node_id}.node_info")
        except Exception:  # noqa: BLE001
            row["error"] = traceback.format_exc()[-1500:]
        nodes[node_id] = row
    menus = {}
    for node_id, row in nodes.items():
        types_ = PACKAGE.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES() if row.get("api") == "v1" else {}
        for section in ("required", "optional"):
            for name, spec in (types_.get(section) or {}).items():
                options = spec[0] if isinstance(spec, (list, tuple)) and spec else None
                if isinstance(options, (list, tuple)):
                    folders = sorted({PROBES[o] for o in options if isinstance(o, str) and o in PROBES})
                    if folders:
                        menus.setdefault(node_id, {})[name] = {
                            "folders": folders, "static": [o for o in options if o not in PROBES],
                            "probe_positions": [i for i, o in enumerate(options) if o in PROBES]}
        outputs = getattr(PACKAGE.NODE_CLASS_MAPPINGS[node_id], "RETURN_TYPES", ())
        for index, rtype in enumerate(outputs):
            if isinstance(rtype, (list, tuple)) and any(o in PROBES for o in rtype if isinstance(o, str)):
                menus.setdefault(node_id, {})[f"output:{index}"] = {
                    "folders": sorted({PROBES[o] for o in rtype if o in PROBES}),
                    "static": [o for o in rtype if o not in PROBES]}
    doc = {"pin": PIN, "problems": PROBLEMS, "nodes": nodes, "stubbed_imports": STUBBED, "model_menus": menus,
           "probes": PROBES,
           "counts": {"nodes": len(nodes), "v3": sum(1 for r in nodes.values() if r.get("api") == "v3"),
                      "errors": sum(1 for r in nodes.values() if "error" in r)}}
    (out / "artv-frozen.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps(doc["counts"], indent=1))
    for node_id, row in nodes.items():
        if "error" in row:
            print("ERROR", node_id, row["error"][-300:])
    for p in PROBLEMS[:20]:
        print("PROBLEM", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
