"""Tier-1 parity for comfyui-inspire-pack (pin d23db9aa, 1.23), round 1: pristine vs v2, CPU gate.

    DEPS=<opencv-python-headless unpacked> run_in_gate.sh <snapshot dir, or the pack folder> \
        <.../v2/tests> <results> test_comfyui-inspire-pack_parity.py

Nodes: LoadImagesFromDir //Inspire, LoadImageListFromDir //Inspire, ChangeImageBatchSize //Inspire.
The pristine directory loaders read the synthetic fixture folders through their absolute host paths.
V2 reads the same folders through the SDK, as input-relative ("mixed", "input/mixed") or
output-relative ("output/frames") names. Outputs are compared exactly; file paths are compared as
os.path.join(<the directory each side was given>, <same file name>).

Documented differences checked here, not hidden:
- Listing order: V2 lists a folder in name order; the original's os.listdir order depends on the
  filesystem. It decides the "None" sort, and the order of ties in the stable Numerical sorts
  (names without a number). The pristine module's os.listdir is therefore given name order
  (H.name_ordered_listing: a module-scoped os proxy, nothing else changes). Every sort method is
  then compared like for like.
- An existing but empty folder reports "cannot be found" in V2 ("No files in directory" originally).
- Datetime sorts, absolute paths and '..' are refused by name.

A published snapshot may omit upstream media, example workflows and bundled model files; the
integrity checks accept their absence. Writes /results/parity.json; exits 1 on any failed check.
"""

import ast
import asyncio
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

import _ins_harness as H  # noqa: E402
import torch  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from encode_manifest import build_manifest, serialize  # noqa: E402

NODES = ["LoadImagesFromDir //Inspire", "LoadImageListFromDir //Inspire", "ChangeImageBatchSize //Inspire"]
ROUND2_NODES = ["GlobalSeed //Inspire"]  # its schema and behaviour: tests/test_global_seed.py
EDITED = {"__init__.py", "pyproject.toml"}
GUEST_MODULES = ["__init__.py", "secure_inspire.py", "_sn_image.py", "_sn_dir.py", "_sn_comfy_utils.py",
                 "_sn_global_seed.py"]
DENIED = ("comfy.", "comfy_execution", "folder_paths", "nodes", "server", "execution", "urllib",
          "requests", "huggingface_hub", "cv2")
MEDIA = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".mov", ".webm", ".avi", ".mkv",
         ".wav", ".mp3", ".flac", ".ogg")
MODEL_FILES = (".pt", ".pth", ".ckpt", ".bin", ".safetensors", ".sft", ".gguf", ".onnx")
INFO_FIELDS = ("name", "display_name", "category", "description", "output", "output_is_list",
               "output_name", "output_node", "is_input_list", "input_order", "has_intermediate_output")
UNSET_FIELDS = ("deprecated", "experimental", "dev_only", "api_node", "search_aliases",
                "output_tooltips", "essentials_category", "price_badge", "output_matchtypes")
SORTS = ["None", "Alphabetical (ASC)", "Alphabetical (DESC)", "Numerical (ASC)", "Numerical (DESC)", None]
DATETIME = ["Datetime (ASC)", "Datetime (DESC)"]
FIXTURE_DIRS = ["mixed", "rgb_only", "alpha_sizes", "single"]

checks = []
per_node = {}


def record(node, name, ok, detail=None, cases=1, kind="parity"):
    checks.append({"node": node, "check": name, "ok": bool(ok), "cases": cases, "kind": kind,
                   "detail": None if ok else str(detail)[:1500]})
    row = per_node.setdefault(node, {"cases": 0, "failed": [], "kinds": set()})
    row["cases"] += cases
    row["kinds"].add(kind)
    if not ok:
        row["failed"].append(name)
    print(("PASS " if ok else "FAIL ") + f"{node} :: {name}" + ("" if ok else f": {str(detail)[:300]}"),
          flush=True)
    return ok


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def omittable(name: str) -> bool:
    lower = name.lower()
    return (lower.endswith(MEDIA + MODEL_FILES)
            or (lower.startswith("example_workflows/") and lower.endswith(".json")))


def module_level_imports(path: Path):
    tree = ast.parse(path.read_bytes())
    out = []
    for item in tree.body:
        if isinstance(item, ast.Import):
            out += [alias.name for alias in item.names]
        elif isinstance(item, ast.ImportFrom) and item.level == 0:
            out.append(item.module)
    return out


def v1_node_info(node_class, obj_class):
    """Core's /object_info for a V1 class (server.py node_info at ComfyUI 6257422b)."""
    info = {"input": obj_class.INPUT_TYPES()}
    info["input_order"] = {key: list(value.keys()) for key, value in obj_class.INPUT_TYPES().items()}
    info["is_input_list"] = getattr(obj_class, "INPUT_IS_LIST", False)
    info["output"] = obj_class.RETURN_TYPES
    info["output_is_list"] = (obj_class.OUTPUT_IS_LIST if hasattr(obj_class, "OUTPUT_IS_LIST")
                              else [False] * len(obj_class.RETURN_TYPES))
    info["output_name"] = obj_class.RETURN_NAMES if hasattr(obj_class, "RETURN_NAMES") else info["output"]
    info["name"] = node_class
    info["display_name"] = H.V1_DISPLAY.get(node_class, node_class)
    info["description"] = obj_class.DESCRIPTION if hasattr(obj_class, "DESCRIPTION") else ""
    info["category"] = getattr(obj_class, "CATEGORY", "sd")
    info["output_node"] = bool(getattr(obj_class, "OUTPUT_NODE", False) is True)
    info["has_intermediate_output"] = bool(getattr(obj_class, "HAS_INTERMEDIATE_OUTPUT", False) is True)
    if hasattr(obj_class, "OUTPUT_TOOLTIPS"):
        info["output_tooltips"] = obj_class.OUTPUT_TOOLTIPS
    info["search_aliases"] = getattr(obj_class, "SEARCH_ALIASES", [])
    return info


def plain(value):
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    return value


def unset(value):
    if value is None or value is False or value == [] or value == {}:
        return True
    return isinstance(value, (list, tuple)) and all(item is None for item in value)


def info_differences(v1, v2):
    diffs = []
    for field in INFO_FIELDS:
        if plain(v1.get(field)) != plain(v2.get(field)):
            diffs.append((field, plain(v1.get(field)), plain(v2.get(field))))
    for field in UNSET_FIELDS:
        a, b = v1.get(field), v2.get(field)
        if not (unset(a) and unset(b)) and plain(a) != plain(b):
            diffs.append((field, plain(a), plain(b)))
    for section in ("required", "optional", "hidden"):
        a, b = v1["input"].get(section, {}), v2["input"].get(section, {})
        if list(a) != list(b):
            diffs.append((f"input.{section}", list(a), list(b)))
            continue
        for name in a:
            ta, tb = a[name], b[name]
            v1_options = list(ta[0]) if isinstance(ta[0], (list, tuple)) else None
            kind_a = "COMBO" if v1_options is not None else ta[0]
            if kind_a != tb[0]:
                diffs.append((f"input.{section}.{name}.type", kind_a, tb[0]))
            opts_a = dict(ta[1]) if len(ta) > 1 else {}
            opts_b = dict(tb[1]) if len(tb) > 1 else {}
            if v1_options is not None and plain(v1_options) != plain(opts_b.get("options")):
                diffs.append((f"input.{section}.{name}.choices", v1_options, opts_b.get("options")))
            opts_b.pop("options", None)
            # V3 always serializes two defaults that V1 omits: a Combo's multiselect=false and a
            # String's multiline=false. Both mean the same as the key being absent.
            if opts_b.get("multiselect") is False and "multiselect" not in opts_a:
                opts_b.pop("multiselect")
            if kind_a == "STRING" and opts_b.get("multiline") is False and "multiline" not in opts_a:
                opts_b.pop("multiline")
            opts_b = {k: v for k, v in opts_b.items() if v is not None}
            if plain(opts_a) != plain(opts_b):
                diffs.append((f"input.{section}.{name}.options", opts_a, opts_b))
    return diffs


def both_fail_in_core(v1_cls, v2_cls, v1_inputs, v2_inputs):
    """No image left: the original's load_images returns None, which core's V1 output handling
    rejects. Both sides run through core's full output path (get_output_data) and must fail with
    the same error type and text."""
    r1 = H.outcome(lambda: asyncio.run(H.run_core(v1_cls(), **v1_inputs)))
    r2 = H.outcome(lambda: asyncio.run(H.run_core(v2_cls, **v2_inputs)))
    return (r1[0] == "error" and r1 == r2), {"pristine": r1, "v2": r2}


def nan_or_equal(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return type(a) is type(b) and a == b


def main():
    head = H.pack_head()
    v2 = head / "v2"
    environment = {"python": platform.python_version(), "torch": torch.__version__,
                   "threads": torch.get_num_threads(), "pack_head": str(head)}

    # 1. Integrity. Files the mirror policy omits may be absent, from pristine and v2 alike.
    expected = json.loads((Path("/tests") / "pristine_blobs.json").read_text())
    actual = {p.relative_to(head).as_posix(): p for p in sorted(head.rglob("*"))
              if p.is_file() and not p.relative_to(head).as_posix().startswith("v2/")}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    environment["omitted_from_snapshot"] = missing
    record("(pack)", "pristine/file-set", not extra and all(omittable(n) for n in missing),
           {"extra": extra, "missing": [n for n in missing if not omittable(n)]}, kind="integrity")
    bad = [n for n, p in actual.items() if blob_id(p.read_bytes()) != expected.get(n)]
    record("(pack)", "pristine/blob-ids", not bad, bad, cases=len(actual), kind="integrity")
    changed = [n for n in sorted(expected) if n not in EDITED and (
        (n in actual) != (v2 / n).is_file()
        or (n in actual and (v2 / n).read_bytes() != actual[n].read_bytes()))]
    record("(pack)", "v2/untouched-copies", not changed, changed, cases=len(expected) - len(EDITED),
           kind="integrity")
    for name in GUEST_MODULES:
        denied = [m for m in module_level_imports(v2 / name) if m and m.startswith(DENIED)]
        record("(pack)", f"guest-imports/{name}", not denied, denied, kind="integrity")

    # 2. Both sides.
    P = H.load_pristine_image_util(head)
    new = H.load_package("ins_v2", v2)
    S = sys.modules["ins_v2._sn_image"]
    pristine_classes = {"LoadImagesFromDir //Inspire": P.LoadImagesFromDirBatch,
                        "LoadImageListFromDir //Inspire": P.LoadImagesFromDirList,
                        "ChangeImageBatchSize //Inspire": P.ChangeImageBatchSize}
    for node_id, cls in pristine_classes.items():
        record("(pack)", f"ids/{node_id}", P.NODE_CLASS_MAPPINGS.get(node_id) is cls
               and P.NODE_DISPLAY_NAME_MAPPINGS.get(node_id) == H.V1_DISPLAY[node_id], node_id, kind="integrity")
    manifest = json.loads((v2 / "secure-nodes.json").read_bytes())
    record("(pack)", "ids", list(new.NODE_CLASS_MAPPINGS) == NODES + ROUND2_NODES
           and set(manifest["nodes"]) == set(NODES + ROUND2_NODES),
           [list(new.NODE_CLASS_MAPPINGS), sorted(manifest["nodes"])], kind="integrity")
    record("(pack)", "manifest-is-encoder-output",
           serialize(build_manifest(v2, "ins_v2_regen")) == (v2 / "secure-nodes.json").read_text(),
           "secure-nodes.json differs from the encoder", kind="integrity")

    # 3. /object_info: the pristine V1 class vs the v2 guest class and the host proxy.
    loaded = packdb.load_pack(H.snapshot_dir(), mount_name="custom_nodes.ins_parity_proxy",
                              pack_id=f"{H.SLUG}/{H.KEY}")
    v1_infos = {node_id: v1_node_info(node_id, cls) for node_id, cls in pristine_classes.items()}
    for node_id in NODES:
        for side, cls in (("guest-class", new.NODE_CLASS_MAPPINGS[node_id]),
                          ("host-proxy", loaded.node_mappings[node_id])):
            diffs = info_differences(v1_infos[node_id], cls.GET_NODE_INFO_V1())
            record(node_id, f"object-info/{side}", not diffs, diffs, cases=len(v1_infos[node_id]), kind="schema")

    # 4. The directory loaders on synthetic folders.
    H.make_fixtures()
    H.name_ordered_listing(P)
    batch_v1, list_v1 = P.LoadImagesFromDirBatch, P.LoadImagesFromDirList
    batch_v2, list_v2 = S.LoadImagesFromDirBatch, S.LoadImagesFromDirList
    first = {}
    for node_id, v1_cls, v2_cls in (("LoadImagesFromDir //Inspire", batch_v1, batch_v2),
                                    ("LoadImageListFromDir //Inspire", list_v1, list_v2)):
        starts = [(0, 0), (1, 2), (-1, 0)] if node_id.startswith("LoadImagesFromDir") else [(0, 0), (1, 2), (3, 0)]
        variant = 0
        for folder in FIXTURE_DIRS:
            for sort in SORTS:
                for start, cap in starts:
                    variant += 1
                    v2_dir = folder if variant % 2 else f"input/{folder}"
                    common = dict(image_load_cap=cap, start_index=start, load_always=False)
                    if sort is not None:
                        common["sort_method"] = sort
                    v1_inputs = dict(common, directory=str(H.INPUT / folder))
                    v2_inputs = dict(common, directory=v2_dir)
                    r1 = H.outcome(lambda: H.run_pristine(v1_cls, **v1_inputs))
                    r2 = H.outcome(lambda: asyncio.run(H.run_v2(v2_cls, **v2_inputs)))
                    label = f"{folder} sort={sort} start={start} cap={cap} dir={v2_dir!r}"
                    if r1[0] == r2[0] == "ok" and r1[1] is not None and r2[1] is not None:
                        a, b = tuple(r1[1]), tuple(r2[1])
                        if node_id.startswith("LoadImageList"):
                            paths_ok = [os.path.basename(p) for p in a[2]] == [os.path.basename(p) for p in b[2]] \
                                and all(p == os.path.join(v2_dir, os.path.basename(p)) for p in b[2])
                            ok, detail = H.same(a[:2], b[:2])
                            ok, detail = ok and paths_ok, detail or ("file paths", a[2], b[2])
                        else:
                            ok, detail = H.same(a, b)
                        first.setdefault(node_id, (a, b, v2_inputs))
                    elif r1 == ("ok", None):
                        ok, detail = both_fail_in_core(v1_cls, v2_cls, v1_inputs, v2_inputs)
                    else:
                        ok, detail = r1 == r2, f"pristine {r1} vs v2 {r2}"
                    record(node_id, f"load/{label}", ok, detail)
        # Output folder, through "output/<folder>".
        r1 = H.outcome(lambda: H.run_pristine(v1_cls, directory=str(H.OUTPUT / "frames"), sort_method="Alphabetical (ASC)"))
        r2 = H.outcome(lambda: asyncio.run(H.run_v2(v2_cls, directory="output/frames", sort_method="Alphabetical (ASC)")))
        if r1[0] == r2[0] == "ok":
            a, b = tuple(r1[1]), tuple(r2[1])
            ok, detail = H.same(a[:2], b[:2]) if node_id.startswith("LoadImageList") else H.same(a, b)
        else:
            ok, detail = False, f"pristine {r1} vs v2 {r2}"
        record(node_id, "load/output/frames", ok, detail)
        # Folders without images: the list loader returns empty lists on both sides; the batch
        # loader returns nothing, and core then fails on both sides.
        for folder in ("only_txt", "only_sub"):
            if node_id.startswith("LoadImageList"):
                r1 = H.outcome(lambda: H.run_pristine(v1_cls, directory=str(H.INPUT / folder)))
                r2 = H.outcome(lambda: asyncio.run(H.run_v2(v2_cls, directory=folder)))
                ok = r1[0] == r2[0] == "ok" and H.same(tuple(r1[1]), tuple(r2[1]))[0] and list(r1[1]) == [[], [], []]
                detail = f"pristine {r1} vs v2 {r2}"
            else:
                ok, detail = both_fail_in_core(v1_cls, v2_cls, dict(directory=str(H.INPUT / folder)),
                                               dict(directory=folder))
            record(node_id, f"no-images/{folder}", ok, detail)
        # Errors with the original's messages.
        not_found = ("Directory '{} cannot be found.'" if node_id.startswith("LoadImagesFromDir")
                     else "Directory '{}' cannot be found.")
        r1 = H.outcome(lambda: H.run_pristine(v1_cls, directory=""))
        r2 = H.outcome(lambda: asyncio.run(H.run_v2(v2_cls, directory="")))
        record(node_id, "error/empty directory string (same error)",
               r1 == r2 == ("error", ("FileNotFoundError", not_found.format(""))), f"pristine {r1} vs v2 {r2}")
        r1 = H.outcome(lambda: H.run_pristine(v1_cls, directory=str(H.INPUT / "nope")))
        r2 = H.outcome(lambda: asyncio.run(H.run_v2(v2_cls, directory="nope")))
        record(node_id, "error/missing folder (same error, own directory text)",
               r1 == ("error", ("FileNotFoundError", not_found.format(str(H.INPUT / "nope"))))
               and r2 == ("error", ("FileNotFoundError", not_found.format("nope"))), f"pristine {r1} vs v2 {r2}")
        r2 = H.outcome(lambda: asyncio.run(H.run_v2(v2_cls, directory="empty")))
        record(node_id, "known-difference/empty folder reads as not found",
               r2 == ("error", ("FileNotFoundError", not_found.format("empty"))), r2, kind="refusal")
        # Refusals: at validation, and at execute for linked inputs.
        refusals = [(method, dict(directory="mixed", sort_method=method),
                     S._sn_dir.refusal_datetime(node_id, method)) for method in DATETIME]
        for text in ("/tmp/ins-input/mixed", "C:\\images\\batch", "\\\\server\\share\\x"):
            refusals.append(("absolute " + text, dict(directory=text), S._sn_dir.refusal_absolute(node_id, text)))
        refusals.append(("parent", dict(directory="mixed/../x"), S._sn_dir.refusal_parent(node_id, "mixed/../x")))
        for label, inputs, message in refusals:
            validated = v2_cls.validate_inputs(**{k: v for k, v in inputs.items() if k in ("directory", "sort_method")})
            executed = H.outcome(lambda: asyncio.run(H.run_v2(v2_cls, **inputs)))
            record(node_id, f"refusal/{label}", validated == message
                   and executed == ("error", ("DirectoryRefused", message)), [validated, executed], kind="refusal")
        record(node_id, "validate/menu-check-kept",
               v2_cls.validate_inputs(directory="mixed", sort_method="Bogus")
               == f"Value not in list: sort_method: 'Bogus' not in {S.sort_methods}"
               and v2_cls.validate_inputs(directory=None, sort_method=None) is True, None, kind="refusal")
        # fingerprint_inputs vs IS_CHANGED.
        for kwargs in (dict(directory="mixed", load_always=True), dict(directory="mixed", load_always=False),
                       dict(directory="mixed", image_load_cap=2, start_index=1, load_always=False, sort_method="None")):
            a, b = v1_cls.IS_CHANGED(**kwargs), v2_cls.fingerprint_inputs(**kwargs)
            record(node_id, f"fingerprint/{sorted(kwargs)} load_always={kwargs.get('load_always')}",
                   nan_or_equal(a, b), [a, b])

    # 5. ChangeImageBatchSize.
    frames = torch.rand(3, 8, 8, 3, generator=torch.Generator().manual_seed(70))
    for batch_size in (1, 2, 3, 5, 4096):
        r1 = H.outcome(lambda: P.ChangeImageBatchSize.doit(frames, batch_size, "simple"))
        r2 = H.outcome(lambda: asyncio.run(H.run_v2(S.ChangeImageBatchSize, image=frames, batch_size=batch_size, mode="simple")))
        ok, detail = (H.same(tuple(r1[1]), tuple(r2[1])) if r1[0] == r2[0] == "ok" else (False, f"{r1} vs {r2}"))
        record("ChangeImageBatchSize //Inspire", f"batch_size={batch_size}", ok, detail)

    # 6. Negative controls.
    controls = {}
    if "LoadImagesFromDir //Inspire" in first:
        a, b, _ = first["LoadImagesFromDir //Inspire"]
        perturbed = b[0].clone()
        perturbed[0, 0, 0, 0] += 1.0 / 255
        controls["perturbed-output-detected"] = H.same(a, b)[0] and not H.same(a[0], perturbed)[0]
    original = S.LoadImagesFromDirBatch.__dict__["define_schema"]

    def perturbed_schema(cls):
        schema = original.__func__(cls)
        schema.display_name = "Load Image Batch From Dir (Inspire) (perturbed)"
        return schema

    S.LoadImagesFromDirBatch.define_schema = classmethod(perturbed_schema)
    try:
        controls["perturbed-schema-detected"] = bool(info_differences(
            v1_infos["LoadImagesFromDir //Inspire"], S.LoadImagesFromDirBatch.GET_NODE_INFO_V1()))
    finally:
        S.LoadImagesFromDirBatch.define_schema = original
    saved = S._sn_dir.refusal_datetime
    S._sn_dir.refusal_datetime = lambda node, method: saved(node, method) + " (perturbed)"
    try:
        controls["perturbed-refusal-detected"] = (
            S.LoadImagesFromDirBatch.validate_inputs(directory="mixed", sort_method=DATETIME[0])
            != saved("LoadImagesFromDir //Inspire", DATETIME[0]))
    finally:
        S._sn_dir.refusal_datetime = saved
    for name, ok in controls.items():
        record("(pack)", f"negative-control/{name}", ok, kind="control")
    return finish(environment, controls)


def finish(environment, controls):
    nodes = {}
    for node_id, row in per_node.items():
        if node_id.startswith("("):
            continue
        if row["failed"]:
            verdict = "MISMATCH"
        elif "parity" in row["kinds"] and "refusal" in row["kinds"]:
            verdict = "EXACT (Datetime sorts, absolute and '..' folders: REFUSED-AS-DESIGNED)"
        elif "parity" in row["kinds"]:
            verdict = "EXACT"
        else:
            verdict = "REFUSED-AS-DESIGNED"
        nodes[node_id] = {"verdict": verdict, "cases": row["cases"], "failed": row["failed"]}
    failed = [c["node"] + " :: " + c["check"] for c in checks if not c["ok"]]
    result = {"pack": H.SLUG, "pin": H.PIN, "nodes": nodes, "negative_control": controls,
              "checks": checks, "failed": failed, "environment": environment}
    Path("/results/parity.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"nodes": {k: v["verdict"] for k, v in nodes.items()}, "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
