"""Schema parity: every V2 RES4LYF node's node info against the ORIGINAL's (gate only).

The original's node info was frozen from upstream 057a913e on the gate core (freeze_all.py ->
original_node_info.json). Two V2 sides are compared with it:
  * in-process: each V2 class's GET_NODE_INFO_V1();
  * served: the host proxies that packdb builds from the manifest (encode_manifest.build), i.e. what a
    ComfyUI server registers and serves.
Comparison is exact apart from representation-only differences, each normalised below and counted:
  * V1 combos serve (options, opts); V3 combos serve ("COMBO", {options, multiselect: false, ...}).
  * V1 hidden serves "PROMPT"; V3 serves ("PROMPT",).
  * Core's V3 Schema.finalize gives every output node the hidden prompt and extra_pnginfo inputs.
  * V1 omits empty search_aliases/output_tooltips; V3 serves None/[None...].
  * python_module is assigned by the loader, not the pack.
List-typed outputs are compared exactly when Core's Combo.Output reports its declared options as its type.
On a Core that serves every COMBO output as the plain string "COMBO", both sides are reduced to "COMBO" and
counted (platform-dependent, not a pack difference).
Writes /results/schemas.json and exits 1 on any other difference.
Run: run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> test_res4lyf_schemas.py
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay", str(Path(__file__).resolve().parent)]
from comfy.cli_args import args  # noqa: E402

args.cpu = True
from comfy_api.latest import io  # noqa: E402

import encode_manifest  # noqa: E402

PACK = Path(os.environ.get("RES4_PACK", "/pack"))
V2 = PACK / "v2"
CORE_REPORTS_OPTIONS = "get_io_type" in vars(io.Combo.Output)
SECURE, SCHEDULERS = encode_manifest.load_v2("res4lyf_secure")
RUNTIME = sys.modules["res4lyf_secure._secure_runtime"]
NOTES = {"combo_representation": 0, "hidden_representation": 0, "v3_output_node_hidden": 0,
         "empty_aliases_or_tooltips": 0, "v3_multiselect_false": 0, "none_valued_option_pruned": 0,
         "combo_output_generic_core": 0, "combo_outputs_compared_exactly": 0}
OUTPUT_NODE_HIDDEN = {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}


def plain(value):
    """JSON round trip so tuples/lists and key order compare structurally."""
    return json.loads(json.dumps(value, default=list))


def norm_spec(spec):
    spec = list(spec)
    type_, opts = spec[0], dict(spec[1]) if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if isinstance(type_, list):
        NOTES["combo_representation"] += 1
        opts = dict(opts)
        opts["options"] = type_
        type_ = "COMBO"
    if type_ == "COMBO" and opts.get("multiselect") is False:
        NOTES["v3_multiselect_false"] += 1
        opts.pop("multiselect")
    pruned = {k: v for k, v in opts.items() if v is not None}
    if len(pruned) != len(opts):
        NOTES["none_valued_option_pruned"] += 1
    return [type_, pruned]


def norm_info(info, *, original_hidden=None):
    info = plain(info)
    out = {}
    inputs = info.get("input") or {}
    norm_inputs = {}
    for section, entries in inputs.items():
        if section == "hidden":
            hidden = {}
            for key, value in (entries or {}).items():
                if isinstance(value, list):
                    NOTES["hidden_representation"] += 1
                    value = value[0]
                hidden[key] = value
            if original_hidden is not None and info.get("output_node"):
                extra = {k: v for k, v in hidden.items() if k not in original_hidden}
                if extra and all(OUTPUT_NODE_HIDDEN.get(k) == v for k, v in extra.items()):
                    NOTES["v3_output_node_hidden"] += 1
                    hidden = {k: v for k, v in hidden.items() if k in original_hidden}
            norm_inputs["hidden"] = hidden
            continue
        norm_inputs[section] = {name: norm_spec(spec) for name, spec in (entries or {}).items()}
    out["input"] = {k: v for k, v in norm_inputs.items() if v}
    out["input_order"] = {k: v for k, v in (info.get("input_order") or {}).items() if k != "hidden" and v}
    outputs = info.get("output") or []
    if any(isinstance(o, list) for o in outputs) or "COMBO" in outputs:
        if CORE_REPORTS_OPTIONS:
            NOTES["combo_outputs_compared_exactly"] += 1
        else:
            NOTES["combo_output_generic_core"] += 1
            outputs = ["COMBO" if isinstance(o, list) else o for o in outputs]
    out["output"] = outputs
    for key in ("output_is_list", "output_name", "name", "display_name", "description", "category", "output_node"):
        out[key] = info.get(key)
    out["deprecated"] = bool(info.get("deprecated", False))
    out["experimental"] = bool(info.get("experimental", False))
    tips = info.get("output_tooltips")
    if not tips or all(t is None for t in tips):
        NOTES["empty_aliases_or_tooltips"] += 1
        tips = None
    out["output_tooltips"] = tips
    out["search_aliases"] = info.get("search_aliases") or None
    return out


def compare(original, v2_info):
    a = norm_info(original)
    original_hidden = (a["input"].get("hidden") or {})
    b = norm_info(v2_info, original_hidden=original_hidden)
    if not a["input"].get("hidden") and b["input"].get("hidden") == {}:
        b["input"].pop("hidden")
    return a, b


def main():
    frozen = json.loads((V2 / "tests" / "original_node_info.json").read_text())["node_info"]
    manifest = encode_manifest.build(SECURE, SCHEDULERS)
    served = dict(encode_manifest.load_snapshot(encode_manifest.dump(manifest),
                                                "custom_nodes.res4lyf_schema_check").node_mappings)
    rows, differ = {}, []
    for node_id, original_tagged in sorted(frozen.items()):
        original = RUNTIME.decode(original_tagged)
        row = {"api": RUNTIME.FROZEN.get(node_id, {}).get("api")}
        for side, classes in (("in_process", SECURE.NODE_CLASS_MAPPINGS), ("served", served)):
            cls = classes.get(node_id)
            if cls is None:
                row[side] = {"ok": False, "why": "not registered"}
                continue
            schema = cls.GET_SCHEMA()
            schema.validate()
            a, b = compare(original, cls.GET_NODE_INFO_V1())
            ok = a == b and schema.node_id == node_id
            entry = {"ok": ok}
            if not ok:
                keys = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
                entry.update(diff_keys=keys, original={k: a.get(k) for k in keys}, v2={k: b.get(k) for k in keys})
            row[side] = entry
        row["ok"] = all(row[side].get("ok") for side in ("in_process", "served"))
        if not row["ok"]:
            differ.append(node_id)
        rows[node_id] = row
    extra = sorted(set(SECURE.NODE_CLASS_MAPPINGS) - set(frozen))
    validation = {node_id: manifest["nodes"][node_id].get("validation_inputs") for node_id in manifest["nodes"]}
    doc = {"core_reports_combo_options": CORE_REPORTS_OPTIONS, "nodes": len(rows),
           "equal": len(rows) - len(differ), "differ": differ, "extra_registered": extra,
           "normalisations": NOTES, "manifest_sha256": __import__("hashlib").sha256(
               encode_manifest.dump(manifest)).hexdigest(),
           "nodes_validating_at_queue_time": sum(1 for v in validation.values() if v), "rows": rows}
    out = Path(os.environ.get("RES4_RESULTS", "/results"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "schemas.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("core_reports_combo_options", "nodes", "equal", "extra_registered",
                                         "normalisations", "nodes_validating_at_queue_time")}, indent=1))
    for node_id in differ[:12]:
        print("DIFF", node_id, json.dumps(rows[node_id])[:900])
    return 1 if differ or extra else 0


if __name__ == "__main__":
    sys.exit(main())
