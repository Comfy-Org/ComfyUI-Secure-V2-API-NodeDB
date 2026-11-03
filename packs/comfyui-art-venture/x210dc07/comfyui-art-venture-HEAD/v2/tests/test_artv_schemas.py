"""Schema parity: every V2 comfyui-art-venture node's node info against the ORIGINAL's (gate only).

The original's node info was frozen from upstream 210dc072 (freeze_artv.py -> original_node_info.json), with a probe
file in every model folder so model menus are recognisable. Two V2 sides are compared with it:
  * served: the host proxies packdb builds from the manifest, with the same probe files in the host's model folders,
    so the host fills each model menu as it would in production;
  * in-process: each V2 class's GET_NODE_INFO_V1(); model menus are unfilled there (no host), so the probe names are
    removed from the original's menus before comparing.
Representation-only differences are normalised and counted:
  * V1 combos serve (options, opts); V3 combos serve ("COMBO", {options, multiselect: false, ...}).
  * V1 hidden serves "PROMPT"; V3 serves ("PROMPT",). Core's V3 finalize adds hidden prompt/extra_pnginfo to output
    nodes.
  * V1 omits empty search_aliases/output_tooltips; V3 serves None/[None...].
  * A V2 model menu carries its host refresh route ("remote").
  * The host appends folder names after a menu's static entries. Where the original lists the folder first (core's
    VAE menu puts "pixel_space" last), only the order differs; such menus compare as sets, counted.
  * A model-folder list OUTPUT (CheckpointNameSelector) cannot be declared statically and serves as generic COMBO;
    counted (known difference, SECURE_CONVERSION.md).
Writes /results/schemas.json; exit 1 on any other difference.
"""
import json
import os
import sys
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay", str(Path(__file__).resolve().parent)]
from comfy.cli_args import args  # noqa: E402

args.cpu = True
import tempfile  # noqa: E402

import folder_paths  # noqa: E402
from comfy_api.latest import io  # noqa: E402

import encode_manifest  # noqa: E402

PACK = Path(os.environ.get("ARTV_PACK", "/pack"))
V2 = PACK / "v2"
FIXTURE = json.loads((V2 / "tests" / "original_node_info.json").read_text())
PROBES = FIXTURE["meta"]["probes"]          # probe file name -> model folder
MENUS = FIXTURE["model_menus"]
TMP = Path(tempfile.mkdtemp(prefix="artv-schema-"))
for name, folder in PROBES.items():
    directory = TMP / "models" / folder
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(b"")
    extensions = folder_paths.folder_names_and_paths.get(folder, ([], set()))[1]
    folder_paths.folder_names_and_paths[folder] = ([str(directory)], extensions)

CORE_REPORTS_OPTIONS = "get_io_type" in vars(io.Combo.Output)
SECURE = encode_manifest.load_v2("artv_secure")
RUNTIME = sys.modules["artv_secure._secure_runtime"]
NOTES = {k: 0 for k in ("combo_representation", "hidden_representation", "v3_output_node_hidden",
                        "empty_aliases_or_tooltips", "v3_multiselect_false", "none_valued_option_pruned",
                        "model_menu_remote", "model_menu_order_host_appends", "in_process_menu_unfilled",
                        "dynamic_list_output_generic", "combo_output_generic_core")}
OUTPUT_NODE_HIDDEN = {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}


def plain(value):
    return json.loads(json.dumps(value, default=list))


def norm_spec(spec, menu=None, side="original", in_process=False):
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
    if "remote" in opts and menu:
        NOTES["model_menu_remote"] += 1
        opts.pop("remote")
    if menu and type_ == "COMBO":
        options = list(opts.get("options") or [])
        if in_process and side == "original":
            NOTES["in_process_menu_unfilled"] += 1
            options = [o for o in options if o not in PROBES]
        if menu.get("probe_positions") and max(menu["probe_positions"]) != len(options) - 1:
            NOTES["model_menu_order_host_appends"] += 1
            options = sorted(options, key=str)
        opts["options"] = options
    pruned = {k: v for k, v in opts.items() if v is not None}
    if len(pruned) != len(opts):
        NOTES["none_valued_option_pruned"] += 1
    return [type_, pruned]


def norm_info(node_id, info, *, side, in_process, original_hidden=None):
    info = plain(info)
    menus = MENUS.get(node_id, {})
    out = {}
    norm_inputs = {}
    for section, entries in (info.get("input") or {}).items():
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
        norm_inputs[section] = {name: norm_spec(spec, menus.get(name), side, in_process)
                                for name, spec in (entries or {}).items()}
    out["input"] = {k: v for k, v in norm_inputs.items() if v}
    out["input_order"] = {k: v for k, v in (info.get("input_order") or {}).items() if k != "hidden" and v}
    outputs = []
    for index, value in enumerate(info.get("output") or []):
        if f"output:{index}" in menus:
            NOTES["dynamic_list_output_generic"] += 1
            outputs.append("COMBO")
        elif isinstance(value, list) and not CORE_REPORTS_OPTIONS:
            NOTES["combo_output_generic_core"] += 1
            outputs.append("COMBO")
        else:
            outputs.append(value)
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


def compare(node_id, original, v2_info, in_process):
    a = norm_info(node_id, original, side="original", in_process=in_process)
    b = norm_info(node_id, v2_info, side="v2", in_process=in_process,
                  original_hidden=a["input"].get("hidden") or {})
    return a, b


def main():
    frozen = FIXTURE["node_info"]
    manifest = encode_manifest.build(SECURE)
    served = dict(encode_manifest.load_snapshot(encode_manifest.dump(manifest),
                                                "custom_nodes.artv_schema_check").node_mappings)
    rows, differ = {}, []
    for node_id, original_tagged in sorted(frozen.items()):
        original = RUNTIME.decode(original_tagged)
        row = {}
        for side, classes, in_process in (("in_process", SECURE.NODE_CLASS_MAPPINGS, True),
                                          ("served", served, False)):
            cls = classes.get(node_id)
            if cls is None:
                row[side] = {"ok": False, "why": "not registered"}
                continue
            schema = cls.GET_SCHEMA()
            schema.validate()
            a, b = compare(node_id, original, cls.GET_NODE_INFO_V1(), in_process)
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
    doc = {"core_reports_combo_options": CORE_REPORTS_OPTIONS, "nodes": len(rows), "equal": len(rows) - len(differ),
           "differ": differ, "extra_registered": extra, "normalisations": NOTES, "rows": rows}
    out = Path(os.environ.get("ARTV_RESULTS", "/results"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "schemas.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("core_reports_combo_options", "nodes", "equal", "extra_registered",
                                         "normalisations")}, indent=1))
    for node_id in differ[:12]:
        print("DIFF", node_id, json.dumps(rows[node_id])[:900])
    return 1 if differ or extra else 0


if __name__ == "__main__":
    sys.exit(main())
