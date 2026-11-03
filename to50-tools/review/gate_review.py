"""In-gate publication review for one V2 pack (MERVYN, to-50% lane, 2026-11-02). Runs INSIDE run_in_gate.sh:

  run_in_gate.sh <pack_root (pristine + v2/)> <this dir> <results dir> gate_review.py

Parent process spawns two children (separate interpreters, so V1 and V2 never share module state):
  v1: imports the ORIGINAL pack (sys.path: /core first) from a /tmp copy and dumps each node's V1 interface.
  v2: imports the V2 pack against the guest SDK base 0cd9adec (then /overlay, /core) from a /tmp copy, recomputes every
      manifest row with the real encoder (comfy_secure_nodes.packmanifest, live overlay) and dumps the same interface.
The parent compares and writes /results/gate-review.json:
  manifest: FAIL on any row/field mismatch, id-set mismatch, runtime/format mismatch; WARN on non-canonical serialization.
  interface: per node V1 vs V2 differences in INPUT_TYPES (names, order, types, options), RETURN_TYPES/NAMES, OUTPUT_IS_LIST,
             OUTPUT_NODE, CATEGORY, display name. Reported for MANUAL review (benign keys such as tooltip are marked).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback
import types
from pathlib import Path

PACK = Path("/pack")
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("REVIEW_RESULTS", "/results"))
BASE = "/bases/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages"
METHODS = ("validate_inputs", "fingerprint_inputs", "check_lazy_status")
ATTRS = ("RETURN_TYPES", "RETURN_NAMES", "OUTPUT_IS_LIST", "INPUT_IS_LIST", "OUTPUT_NODE", "CATEGORY", "OUTPUT_TOOLTIPS",
         "NOT_IDEMPOTENT", "DESCRIPTION")
BENIGN_OPTION_KEYS = {"tooltip"}
V3_DEFAULT_KEYS = {"multiselect", "lazy", "forceInput", "advanced", "socketless", "control_after_generate", "dynamicPrompts",
                   "multiline"}
MAX_COPY = 300 * 1024 * 1024


def jsonable(v, depth=0):
    if depth > 12:
        return repr(v)[:200]
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return {"__float__": v.hex()} if v != v or v in (float("inf"), float("-inf")) else v
    if isinstance(v, (list, tuple)):
        return [jsonable(x, depth + 1) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted((jsonable(x, depth + 1) for x in v), key=repr)
    if isinstance(v, dict):
        return {str(k): jsonable(x, depth + 1) for k, x in v.items()}
    if hasattr(v, "value") and type(v).__mro__[1].__name__ in ("str", "Enum", "int"):
        return jsonable(v.value, depth + 1)
    return {"__repr__": repr(v)[:300]}


class _Anything:
    """Permissive stand-in for PromptServer.instance at import time (routes decorators, send_sync...)."""

    def __getattr__(self, name):
        return _Anything()

    def __call__(self, *a, **k):
        if len(a) == 1 and not k and callable(a[0]):
            return a[0]
        return _Anything()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False


def copy_tree(src: Path, dst: Path, skip_v2: bool):
    def ignore(d, names):
        out = {n for n in names if n in (".git", "__pycache__", "node_modules")}
        if skip_v2 and Path(d) == src:
            out.add("v2")
        for n in names:
            p = Path(d) / n
            try:
                if p.is_file() and p.stat().st_size > MAX_COPY:
                    out.add(n)
            except OSError:
                pass
        return out
    shutil.copytree(src, dst, ignore=ignore)


def import_package(name: str, root: Path):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def mount_namespace(name: str, root: Path):
    """Same as the production loader (packdb.mount): a bare package over root; __init__.py is NOT executed."""
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(root)]
    pkg.__package__ = name
    sys.modules[name] = pkg
    return pkg


def registered_nodes(mod) -> tuple[dict, dict, list]:
    """NODE_CLASS_MAPPINGS plus V3 comfy_entrypoint() nodes -> ({id: cls}, display map, notes)."""
    import asyncio
    import inspect
    notes = []
    mappings = dict(getattr(mod, "NODE_CLASS_MAPPINGS", {}) or {})
    display = dict(getattr(mod, "NODE_DISPLAY_NAME_MAPPINGS", {}) or {})
    ep = getattr(mod, "comfy_entrypoint", None)
    if callable(ep):
        try:
            ext = ep()
            if inspect.isawaitable(ext):
                ext = asyncio.run(ext)
            nodes = ext.get_node_list()
            if inspect.isawaitable(nodes):
                nodes = asyncio.run(nodes)
            for cls in nodes:
                node_id = cls.GET_SCHEMA().node_id
                if node_id in mappings and mappings[node_id] is not cls:
                    notes.append(f"{node_id}: in both NODE_CLASS_MAPPINGS and comfy_entrypoint with different classes")
                mappings.setdefault(node_id, cls)
            notes.append(f"comfy_entrypoint: {len(nodes)} nodes")
        except Exception as e:  # noqa: BLE001
            notes.append(f"comfy_entrypoint failed: {e!r}"[:300])
    return mappings, display, notes


def iface(cls, node_id, display_map, v3: bool):
    d = {}
    try:
        d["INPUT_TYPES"] = jsonable(cls.INPUT_TYPES())
    except Exception as e:  # noqa: BLE001
        d["INPUT_TYPES_error"] = repr(e)[:400]
    for a in ATTRS:
        try:
            d[a] = jsonable(getattr(cls, a, None))
        except Exception as e:  # noqa: BLE001
            d[a + "_error"] = repr(e)[:200]
    dn = display_map.get(node_id)
    if v3:
        try:
            dn = cls.GET_SCHEMA().display_name or dn
        except Exception as e:  # noqa: BLE001
            d["display_error"] = repr(e)[:200]
    d["display_name"] = dn
    return d


def force_cpu():
    """CPU gate: make ComfyUI's model_management choose the CPU instead of probing CUDA at import."""
    try:
        from comfy.cli_args import args
        args.cpu = True
    except Exception:  # noqa: BLE001
        pass


def child_v1(out: Path):
    res = {"ok": False}
    try:
        sys.argv = [sys.argv[0]]
        dst = Path("/tmp/review-v1") / PACK.name
        copy_tree(PACK, dst, skip_v2=True)
        sys.path[:0] = ["/core"] + (["/deps"] if os.path.isdir("/deps") else [])
        os.chdir("/tmp")
        force_cpu()
        try:
            import server  # noqa: F401
            if getattr(server.PromptServer, "instance", None) is None:
                server.PromptServer.instance = _Anything()
        except Exception as e:  # noqa: BLE001
            m = types.ModuleType("server")
            m.PromptServer = type("PromptServer", (), {"instance": _Anything()})
            sys.modules["server"] = m
            res["server_stub"] = repr(e)[:200]
        mod = import_package("review_v1_pack", dst)
        mappings, display, notes = registered_nodes(mod)
        res["registry_notes"] = notes
        res["ids"] = list(mappings)
        res["nodes"] = {}
        for node_id, cls in mappings.items():
            try:
                res["nodes"][node_id] = iface(cls, node_id, display, v3=hasattr(cls, "GET_SCHEMA"))
            except Exception as e:  # noqa: BLE001
                res["nodes"][node_id] = {"error": repr(e)[:400]}
        res["web_directory"] = getattr(mod, "WEB_DIRECTORY", None)
        res["ok"] = True
    except BaseException as e:  # noqa: BLE001
        res["error"] = repr(e)[:600]
        res["traceback"] = traceback.format_exc()[-4000:]
    out.write_text(json.dumps(res, indent=1, sort_keys=True))


def child_v2(out: Path):
    res = {"ok": False}
    try:
        sys.argv = [sys.argv[0]]
        dst = Path("/tmp/review-v2/v2")
        copy_tree(V2, dst, skip_v2=False)
        sys.path[:0] = [BASE, "/overlay", "/core"] + (["/deps"] if os.path.isdir("/deps") else [])
        os.chdir("/tmp")
        force_cpu()
        from comfy_secure_nodes import packmanifest
        from comfy_secure_nodes.packruntime import manifest_declaration
        import comfy_api
        res["comfy_api_file"] = comfy_api.__file__
        res["encoder_file"] = packmanifest.__file__
        raw = (V2 / "secure-nodes.json").read_bytes()
        manifest = json.loads(raw)
        res["canonical_serialization"] = raw == (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        for label, kw in (("indent2_sorted", dict(indent=2, sort_keys=True)), ("indent2", dict(indent=2)),
                          ("indent1_sorted", dict(indent=1, sort_keys=True)), ("indent1", dict(indent=1))):
            for nl in ("\n", ""):
                if raw == (json.dumps(manifest, **kw) + nl).encode("utf-8"):
                    res["serialization"] = label + ("+newline" if nl else "")
        res.setdefault("serialization", "other")
        res["manifest_ids"] = list(manifest.get("nodes", {}))
        fails, rows, warns = [], {}, []
        if manifest.get("format") != packmanifest.FORMAT:
            fails.append(f"format {manifest.get('format')!r} != {packmanifest.FORMAT!r}")
        try:
            prof = ((manifest.get("runtime") or {}).get("dependencies") or {}).get("profile_sha256")
            decl = manifest_declaration(dst, dependency_profile_sha256=prof)
            if prof:
                warns.append(f"dependency profile {prof} declared: verify it exists in GERALD's dependency store")
            if manifest.get("runtime") != decl:
                fails.append(f"runtime {manifest.get('runtime')!r} != manifest_declaration {decl!r}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"manifest_declaration failed: {e!r}"[:300])
        # Load every node exactly as the production loader does: mount v2/ as a bare package (no __init__.py),
        # import <pkg>.<row module>, take <row class>.
        mount_namespace("review_v2_pack", dst)
        mappings = {}
        for node_id, row in manifest.get("nodes", {}).items():
            try:
                m = importlib.import_module(f"review_v2_pack.{row['module']}")
                # Same lookup as the guest (comfy_secure_nodes/guest/__init__.py:1484-1490): getattr, then any
                # module-level class whose __name__ matches (classes made by a factory and bound under another name).
                cls = getattr(m, row["class"], None)
                if cls is None:
                    cls = next((v for v in vars(m).values() if isinstance(v, type) and v.__name__ == row["class"]), None)
                if cls is None:
                    raise AttributeError(f"{row['class']} not found in {row['module']} (guest lookup would fail)")
                mappings[node_id] = cls
            except Exception as e:  # noqa: BLE001
                fails.append(f"{node_id}: production-style load of {row.get('module')}.{row.get('class')} failed: {e!r}"[:400])
        display = {}
        # Registry view (v2/__init__.py executed under another name): ids only, for the census cross-check.
        try:
            init_mod = import_package("review_v2_init", dst)
            reg, display, notes = registered_nodes(init_mod)
            res["registry_ids"] = list(reg)
            res["registry_notes"] = notes
            if set(reg) != set(manifest.get("nodes", {})):
                warns.append(f"v2 registry ids != manifest ids: only_registry={sorted(set(reg) - set(manifest['nodes']))[:20]} "
                             f"only_manifest={sorted(set(manifest['nodes']) - set(reg))[:20]}")
        except Exception as e:  # noqa: BLE001
            res["registry_ids"] = None
            warns.append(f"v2/__init__.py import failed (registry view unavailable): {e!r}"[:300])
        res["ids"] = list(manifest.get("nodes", {}))
        for node_id in sorted(manifest.get("nodes", {})):
            row = manifest["nodes"][node_id]
            cls = mappings.get(node_id)
            if cls is None:
                continue
            r = {}
            try:
                modfile = Path(sys.modules[cls.__module__].__file__).resolve()
                r["module"] = ".".join(modfile.relative_to(dst.resolve()).with_suffix("").parts)
            except Exception as e:  # noqa: BLE001
                r["module"] = f"<error {e!r}>"[:200]
            r["class"] = cls.__name__
            r["sdk_refs"] = getattr(cls, "SDK_REFS", False) is True
            r["permissions"] = list(getattr(cls, "SDK_PERMISSIONS", ()) or ())
            # MRO-aware: a method counts when the class's resolved method is not io.ComfyNode's placeholder (inherited
            # validators, e.g. a shared refusal base class, must still be called by the host proxy).
            from comfy_api.latest import io as _io_mod

            def _overrides(c, name):
                mine, base = getattr(c, name, None), getattr(_io_mod.ComfyNode, name, None)
                return getattr(mine, "__func__", mine) is not getattr(base, "__func__", base)
            r["methods"] = {m: _overrides(cls, m) for m in METHODS}
            if r["methods"] != {m: m in cls.__dict__ for m in METHODS}:
                warns.append(f"{node_id}: methods inherited from a pack base class: "
                             f"{[m for m in METHODS if r['methods'][m] and m not in cls.__dict__]}")
            try:
                schema = copy.deepcopy(cls.GET_SCHEMA())
                r["schema"] = packmanifest.encode_schema(schema)
                if getattr(schema, "node_id", node_id) != node_id:
                    fails.append(f"{node_id}: schema.node_id is {schema.node_id!r}")
                if r["schema"] != row.get("schema"):
                    # Production decodes the manifest schema and finalizes it (default output ids, output-node hidden
                    # inputs). Equal after that = benign encoding variance (e.g. encoded before finalize).
                    try:
                        dec = packmanifest.decode_schema(copy.deepcopy(row["schema"]))
                        dec.finalize()
                        if packmanifest.encode_schema(dec) == r["schema"]:
                            warns.append(f"{node_id}: schema encoded pre-finalize (equal after host decode+finalize)")
                            r["schema"] = row["schema"]
                    except Exception as e:  # noqa: BLE001
                        warns.append(f"{node_id}: manifest schema does not decode: {e!r}"[:300])
            except Exception as e:  # noqa: BLE001
                r["schema"] = f"<error {e!r}>"[:300]
            if "validation_inputs" in row or r["methods"]["validate_inputs"]:
                try:
                    r["validation_inputs"] = packmanifest.encode_validation_inputs(cls)
                except Exception as e:  # noqa: BLE001
                    r["validation_inputs"] = f"<error {e!r}>"[:200]
            if "required_weights" in row or getattr(cls, "SDK_REQUIRED_WEIGHTS", None):
                try:
                    r["required_weights"] = packmanifest.encode_required_weights(cls)
                except Exception as e:  # noqa: BLE001
                    r["required_weights"] = f"<error {e!r}>"[:200]
            diffs = [k for k in sorted(set(r) | set(row)) if r.get(k, "<absent>") != row.get(k, "<absent>")]
            if diffs:
                fails.append(f"{node_id}: manifest row differs from real encoder in {diffs}")
                rows[node_id] = {k: {"manifest": row.get(k, "<absent>"), "encoder": r.get(k, "<absent>")} for k in diffs}
        res["manifest_fail"] = fails
        res["manifest_warn"] = warns
        res["manifest_row_diffs"] = rows
        init_mod = sys.modules.get("review_v2_init")
        res["web_directory"] = {"manifest": manifest.get("web_directory"),
                                "package": getattr(init_mod, "WEB_DIRECTORY", None) if init_mod else None}
        res["nodes"] = {}
        for node_id, cls in mappings.items():
            try:
                res["nodes"][node_id] = iface(cls, node_id, display, v3=True)
            except Exception as e:  # noqa: BLE001
                res["nodes"][node_id] = {"error": repr(e)[:400]}
        res["ok"] = True
    except BaseException as e:  # noqa: BLE001
        res["error"] = repr(e)[:600]
        res["traceback"] = traceback.format_exc()[-4000:]
    out.write_text(json.dumps(res, indent=1, sort_keys=True))


def norm_input(spec):
    """V1 input spec -> (type, options dict). Lists as type = COMBO with options."""
    if not isinstance(spec, list) or not spec:
        return ("<unparsed>", {"raw": spec})
    t, opts = spec[0], (spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {})
    opts = dict(opts)
    if isinstance(t, list):
        opts = {**opts, "options": t}
        t = "COMBO"
    elif t == "COMBO" and "options" not in opts:
        opts["options"] = []
    return (t, opts)


def compare_inputs(a: dict, b: dict):
    out = []
    for sec in ("required", "optional", "hidden"):
        sa, sb = (a or {}).get(sec, {}) or {}, (b or {}).get(sec, {}) or {}
        if list(sa) != list(sb):
            if set(sa) != set(sb):
                out.append({"what": f"{sec} names", "v1": list(sa), "v2": list(sb), "severity": "MISMATCH"})
            else:
                out.append({"what": f"{sec} order", "v1": list(sa), "v2": list(sb), "severity": "MISMATCH"})
        for name in sa:
            if name not in sb:
                continue
            if sec == "hidden":
                a1, b1 = sa[name], sb[name]
                # V3's v1-compat projection emits hidden values as ['PROMPT']; V1 declares 'PROMPT'. Same meaning.
                if isinstance(b1, list) and len(b1) == 1 and not isinstance(a1, list):
                    b1 = b1[0]
                if isinstance(a1, list) and len(a1) == 1 and not isinstance(b1, list):
                    a1 = a1[0]
                if a1 != b1:
                    out.append({"what": f"hidden {name}", "v1": sa[name], "v2": sb[name], "severity": "MISMATCH"})
                continue
            ta, oa = norm_input(sa[name])
            tb, ob = norm_input(sb[name])
            if ta != tb:
                out.append({"what": f"{sec}.{name} type", "v1": ta, "v2": tb, "severity": "MISMATCH"})
            for k in sorted(set(oa) | set(ob)):
                va, vb = oa.get(k, "<absent>"), ob.get(k, "<absent>")
                if va == vb:
                    continue
                sev = "BENIGN" if k in BENIGN_OPTION_KEYS else ("REMOTE" if k in ("remote", "options") and "remote" in ob
                                                               else "MISMATCH")
                # V3 serializes some defaults explicitly (e.g. multiselect: false); V1 omits them -> same behaviour.
                if sev == "MISMATCH" and va == "<absent>" and vb in (False, None) and k in V3_DEFAULT_KEYS:
                    sev = "BENIGN"
                # A V1 combo without a default uses its first option; V3 serializes that default explicitly.
                if sev == "MISMATCH" and k == "default" and va == "<absent>" and ta == "COMBO" \
                        and isinstance(oa.get("options"), list) and oa["options"] and vb == oa["options"][0]:
                    sev = "BENIGN"
                if k == "options" and isinstance(va, list) and isinstance(vb, list) and len(va) + len(vb) > 40:
                    va = {"len": len(va), "only_v1": [x for x in va if x not in vb][:20]}
                    vb = {"len": len(vb), "only_v2": [x for x in vb if x not in oa.get(k, [])][:20]}
                out.append({"what": f"{sec}.{name}.{k}", "v1": va, "v2": vb, "severity": sev})
    return out


def compare(v1: dict, v2: dict):
    report = {}
    n1, n2 = v1.get("nodes", {}), v2.get("nodes", {})
    for node_id in sorted(set(n1) | set(n2)):
        if node_id not in n2:
            report[node_id] = [{"what": "node missing in V2", "severity": "MISMATCH"}]
            continue
        if node_id not in n1:
            report[node_id] = [{"what": "node not in V1 NODE_CLASS_MAPPINGS", "severity": "INFO"}]
            continue
        a, b = n1[node_id], n2[node_id]
        diffs = []
        if "INPUT_TYPES" in a and "INPUT_TYPES" in b:
            diffs += compare_inputs(a["INPUT_TYPES"], b["INPUT_TYPES"])
        else:
            diffs.append({"what": "INPUT_TYPES unavailable", "v1": a.get("INPUT_TYPES_error"), "v2": b.get("INPUT_TYPES_error"),
                          "severity": "UNCHECKED"})
        for k in ("RETURN_TYPES", "RETURN_NAMES", "OUTPUT_IS_LIST", "OUTPUT_NODE", "CATEGORY", "display_name", "INPUT_IS_LIST"):
            va, vb = a.get(k), b.get(k)
            if k in ("OUTPUT_IS_LIST",) and va in (None, []) and not any(vb or []):
                continue
            if k in ("RETURN_NAMES",) and va in (None, []) and vb == a.get("RETURN_TYPES"):
                continue
            if k in ("OUTPUT_NODE", "INPUT_IS_LIST") and not va and not vb:
                continue
            if k == "RETURN_TYPES" and isinstance(va, list) and isinstance(vb, list):
                va = ["COMBO" if isinstance(x, list) else x for x in va]
            if k == "display_name" and va is None and vb == node_id:
                continue  # V1 without a display mapping shows the node id; V3 sets display_name = node id
            if va != vb:
                diffs.append({"what": k, "v1": va, "v2": vb, "severity": "MISMATCH"})
        if a.get("DESCRIPTION") != b.get("DESCRIPTION") and (a.get("DESCRIPTION") or b.get("DESCRIPTION")):
            diffs.append({"what": "DESCRIPTION", "v1": a.get("DESCRIPTION"), "v2": b.get("DESCRIPTION"), "severity": "BENIGN"})
        if diffs:
            report[node_id] = diffs
    return report


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("v1", "v2"):
        (child_v1 if sys.argv[1] == "v1" else child_v2)(Path(sys.argv[2]))
        return 0
    RESULTS.mkdir(parents=True, exist_ok=True)
    outs = {}
    for mode in ("v1", "v2"):
        o = Path(f"/tmp/gate-review-{mode}.json")
        p = subprocess.run([sys.executable, "-I", "-B", __file__, mode, str(o)], capture_output=True, text=True, timeout=1800)
        outs[mode] = json.loads(o.read_text()) if o.exists() else {"ok": False, "error": "no output"}
        outs[mode]["stderr_tail"] = p.stderr[-3000:]
        outs[mode]["returncode"] = p.returncode
    v1, v2 = outs["v1"], outs["v2"]
    manifest_fail = list(v2.get("manifest_fail", [])) if v2.get("ok") else [f"v2 import failed: {v2.get('error')}"]
    ids = {"v1": v1.get("ids"), "v2": v2.get("ids"), "manifest": v2.get("manifest_ids")}
    id_report = {}
    if v1.get("ok") and v2.get("ok"):
        s1, s2 = set(v1["ids"]), set(v2["ids"])
        id_report = {"missing_in_v2": sorted(s1 - s2), "extra_in_v2": sorted(s2 - s1)}
    interface = compare(v1, v2) if v1.get("ok") and v2.get("ok") else {}
    sev = {}
    for diffs in interface.values():
        for d in diffs:
            sev[d["severity"]] = sev.get(d["severity"], 0) + 1
    verdict = "FAIL" if manifest_fail or id_report.get("missing_in_v2") else "PASS"
    summary = {
        "tool": "to50 review gate_review.py", "pack": PACK.name, "verdict_manifest_and_ids": verdict,
        "manifest_fail": manifest_fail, "manifest_warn": v2.get("manifest_warn", []),
        "registry": {"v1_notes": v1.get("registry_notes"), "v2_notes": v2.get("registry_notes"),
                     "v2_registry_ids": v2.get("registry_ids")},
        "manifest_canonical_serialization": v2.get("canonical_serialization"), "manifest_serialization": v2.get("serialization"),
        "manifest_row_diffs": v2.get("manifest_row_diffs", {}), "web_directory": v2.get("web_directory"),
        "v1_web_directory": v1.get("web_directory"), "id_report": id_report, "ids": ids,
        "interface_severity_counts": sev, "interface_diffs": interface,
        "children": {m: {k: outs[m].get(k) for k in ("ok", "error", "traceback", "returncode", "stderr_tail", "server_stub",
                                                     "comfy_api_file", "encoder_file")} for m in outs},
    }
    (RESULTS / "gate-review.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    print(json.dumps({"verdict": verdict, "manifest_fail": manifest_fail[:10], "manifest_warn": v2.get("manifest_warn", [])[:5],
                      "canonical": v2.get("canonical_serialization"), "serialization": v2.get("serialization"),
                      "v1_registry_notes": v1.get("registry_notes"), "id_report": id_report,
                      "interface_severity_counts": sev, "v1_ok": v1.get("ok"), "v2_ok": v2.get("ok"),
                      "v1_error": v1.get("error"), "v2_error": v2.get("error")}, indent=1))
    return 1 if verdict == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
