"""Ids ComfyUI core registers itself (gate only).

Core's loader takes the ids registered before custom nodes load (nodes.py, comfy_extras and comfy_api_nodes) as its
ignore set, and skips any custom node id in it, for the class and the display name alike (nodes.py:2314-2322 and
:2376 on core 6257422b). On V1 core's node therefore serves such an id and the original's never registers. This
pack leaves those ids out (_frozen_nodes.json, meta.core_owned) and so registers none of them.

Checks, against the gate core's full id set:
  * no id in the committed manifest (v2/secure-nodes.json) or the frozen declarations is one core registers;
  * every id in meta.core_owned is one core registers, and the pack registers none of them;
  * the frozen declarations plus meta.core_owned are the original's ids (meta.original_counts);
  * every core module that defines nodes loaded (else the id set would be incomplete).
Writes /results/core-ids.json and exits 1 on any finding.
Run: run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> test_core_ids.py
"""
import asyncio
import json
import os
import sys
import tempfile
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
for entry in (str(CORE), "/overlay"):
    if entry not in sys.path:
        sys.path.insert(0, entry)
from comfy.cli_args import args  # noqa: E402

args.cpu = True
import folder_paths  # noqa: E402
import server  # noqa: E402
from aiohttp import web  # noqa: E402
from app.node_replace_manager import NodeReplaceManager  # noqa: E402

# What core's extras touch at load: route tables, the node-replacement registry and the input folder.
server.PromptServer.instance = types.SimpleNamespace(
    routes=web.RouteTableDef(), supports={"custom_nodes_from_web"}, send_sync=lambda *a, **k: None,
    client_id=None, last_node_id=None, node_replace_manager=NodeReplaceManager())
folder_paths.set_input_directory(tempfile.mkdtemp(prefix="res4-core-ids-input-"))
import nodes  # noqa: E402

PACK = Path(os.environ.get("RES4_PACK", "/pack"))
V2 = PACK / "v2"


def main():
    before = set(nodes.NODE_CLASS_MAPPINGS)
    failed_extras = list(asyncio.run(nodes.init_builtin_extra_nodes()) or [])
    after_extras = set(nodes.NODE_CLASS_MAPPINGS)
    failed_api = list(asyncio.run(nodes.init_builtin_api_nodes()) or [])
    core_ids = set(nodes.NODE_CLASS_MAPPINGS)

    frozen_doc = json.loads((V2 / "_frozen_nodes.json").read_text())
    info_meta = json.loads((V2 / "tests" / "original_node_info.json").read_text())["meta"]
    frozen = set(frozen_doc["nodes"])
    core_owned = frozen_doc["meta"].get("core_owned", {})
    manifest = set(json.loads((V2 / "secure-nodes.json").read_text())["nodes"])
    original_total = sum(frozen_doc["meta"]["original_counts"].values())

    def owner(node_id):
        if node_id in before:
            return "nodes.py"
        return "comfy_extras" if node_id in after_extras else "comfy_api_nodes"

    findings = {
        "manifest_ids_core_registers": sorted(manifest & core_ids),
        "frozen_ids_core_registers": sorted(frozen & core_ids),
        "core_owned_core_does_not_register": sorted(set(core_owned) - core_ids),
        "core_owned_registered_by_pack": sorted(set(core_owned) & (manifest | frozen)),
        "manifest_not_frozen": sorted(manifest ^ frozen),
        "original_ids_unaccounted": original_total - len(frozen | set(core_owned)),
        "fixture_meta_differs": info_meta != frozen_doc["meta"],
        "core_modules_failed": failed_extras + failed_api,
    }
    ok = not any(findings.values())
    doc = {
        "passed": ok,
        "core_ids": {"total": len(core_ids), "nodes.py": len(before), "comfy_extras": len(after_extras - before),
                     "comfy_api_nodes": len(core_ids - after_extras)},
        "pack": {"manifest": len(manifest), "frozen": len(frozen), "original": original_total},
        "core_owned": {node_id: {"registered_by": owner(node_id) if node_id in core_ids else None,
                                 "core_class": getattr(nodes.NODE_CLASS_MAPPINGS.get(node_id), "__name__", None),
                                 "core_display_name": nodes.NODE_DISPLAY_NAME_MAPPINGS.get(node_id),
                                 "note": note}
                       for node_id, note in sorted(core_owned.items())},
        "findings": findings,
    }
    out = Path(os.environ.get("RES4_RESULTS", "/results"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "core-ids.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps(doc, indent=1, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
