"""Tier-1 parity for comfyui_memory_cleanup: the original and v2 side by side in the gate container.

    run_in_gate.sh <pack root (pristine + v2/) or a snapshot dir holding it> <.../v2/tests> <results dir> \
        test_comfyui_memory_cleanup_parity.py

Writes /results/parity.json. Both nodes are passthrough output nodes, so parity covers:
  * the returned value: the very same object for every input type, in both versions (in-process; across a real guest
    boundary plain values come back equal but new, see SECURE_CONVERSION.md);
  * the host memory operations: the original's calls into comfy.model_management / gc are recorded, and v2's calls through
    the SDK verb models.memory_cleanup reach the same functions in the in-process SDK. The sequences must match, apart
    from the documented differences (no prompt-queue flag; no OS-level RAM trimming or sleeps);
  * IS_CHANGED vs fingerprint_inputs on a frozen clock;
  * the node interface (INPUT_TYPES, RETURN_TYPES/NAMES, OUTPUT_NODE, CATEGORY, display names).
Two negative controls must turn red.
"""
import asyncio
import contextlib
import ctypes
import gc
import importlib.util
import io as _stdio
import json
import sys
import time
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]
from comfy.cli_args import args as _cli_args  # noqa: E402

_cli_args.cpu = True

import torch  # noqa: E402
import comfy.model_management as mm  # noqa: E402
import server  # noqa: E402
from comfy_api.latest import sdk, _sdk  # noqa: E402  (tests only)


def pack_root(root=Path("/pack")):
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


PACK = pack_root()
V2 = PACK / "v2"
RESULTS = Path("/results")


def load(name, folder):
    spec = importlib.util.spec_from_file_location(name, folder / "__init__.py",
                                                  submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LOG = []


class _Queue:
    def set_flag(self, name, value):
        LOG.append(f"prompt_queue.set_flag({name}={value})")


server.PromptServer.instance = types.SimpleNamespace(prompt_queue=_Queue())

ORIGINAL = load("mc_original", PACK)
CONVERTED = load("mc_v2", V2)


@contextlib.contextmanager
def recording():
    saved = (mm.unload_all_models, mm.soft_empty_cache, gc.collect, time.sleep, ctypes.CDLL)
    mm.unload_all_models = lambda *a, **k: LOG.append("unload_all_models")
    mm.soft_empty_cache = lambda *a, **k: LOG.append("soft_empty_cache")

    def _collect(*a, **k):
        LOG.append("gc.collect")
        return 0
    gc.collect = _collect
    time.sleep = lambda seconds: LOG.append(f"sleep({seconds})")
    ctypes.CDLL = lambda name, *a, **k: types.SimpleNamespace(
        malloc_trim=lambda n: LOG.append(f"{name}.malloc_trim({n})"))
    LOG.clear()
    try:
        yield LOG
    finally:
        mm.unload_all_models, mm.soft_empty_cache, gc.collect, time.sleep, ctypes.CDLL = saved


@contextlib.contextmanager
def runtime(node_type, permissions):
    refs = _sdk.InProcessRefResolver()
    plan = sdk.ExecutionPlan(prompt_id="memory-cleanup-parity", node_id="1", node_type=node_type,
                             permissions=tuple(permissions))
    context = _sdk.InProcessCtxProvider().build(plan)
    with _sdk.bind_runtime(refs, context, _sdk.InProcessOps()):
        try:
            yield context
        finally:
            refs.clear()


def run_original(node_id, kwargs):
    cls = ORIGINAL.NODE_CLASS_MAPPINGS[node_id]
    out = _stdio.StringIO()
    with recording() as log, contextlib.redirect_stdout(out):
        result = getattr(cls(), cls.FUNCTION)(**kwargs)
        ops = list(log)
    return result, ops, out.getvalue()


def run_converted(node_id, kwargs):
    cls = CONVERTED.NODE_CLASS_MAPPINGS[node_id]
    out = _stdio.StringIO()
    with recording() as log, contextlib.redirect_stdout(out), runtime(node_id, cls.SDK_PERMISSIONS):
        result = asyncio.run(cls.execute(**kwargs))
        ops = list(log)
    return tuple(result.args), ops, out.getvalue()


def values():
    return [
        ("none", None), ("int", 0), ("float", 1.5), ("str", "text"), ("list", [1, 2]), ("dict", {"a": 1}),
        ("image", torch.zeros((1, 8, 8, 3))), ("latent", {"samples": torch.zeros((1, 4, 8, 8))}),
        ("opaque", object()),
    ]


CHECKS = []


def check(node, case, ok, detail=None):
    CHECKS.append({"node": node, "case": case, "ok": bool(ok), "detail": detail})
    return bool(ok)


def vram_cases():
    for offload_model in (True, False):
        for offload_cache in (True, False):
            for name, value in values():
                kwargs = dict(offload_model=offload_model, offload_cache=offload_cache)
                if name != "none":
                    kwargs["anything"] = value
                case = f"om={offload_model},oc={offload_cache},{name}"
                r1, ops1, out1 = run_original("VRAMCleanup", kwargs)
                r2, ops2, out2 = run_converted("VRAMCleanup", kwargs)
                expected_value = kwargs.get("anything")
                check("VRAMCleanup", case + ":value", len(r1) == len(r2) == 1 and r1[0] is expected_value
                      and r2[0] is expected_value, [type(r1[0]).__name__, type(r2[0]).__name__])
                # Documented difference: the guest cannot set the prompt queue's free_memory flag.
                ops1_without_flag = [op for op in ops1 if not op.startswith("prompt_queue.set_flag")]
                check("VRAMCleanup", case + ":host-ops", ops1_without_flag == ops2, {"original": ops1, "v2": ops2})
                check("VRAMCleanup", case + ":stdout", out1 == out2, {"original": out1, "v2": out2})


def ram_cases():
    for fc in (True, False):
        for cp in (True, False):
            for cd in (True, False):
                for retry in (1, 3, 10):
                    for name, value in (("none", None), ("image", torch.zeros((1, 8, 8, 3))), ("opaque", object())):
                        kwargs = dict(clean_file_cache=fc, clean_processes=cp, clean_dlls=cd, retry_times=retry)
                        if name != "none":
                            kwargs["anything"] = value
                        case = f"fc={fc},cp={cp},cd={cd},retry={retry},{name}"
                        r1, ops1, _ = run_original("RAMCleanup", kwargs)
                        r2, ops2, _ = run_converted("RAMCleanup", kwargs)
                        expected_value = kwargs.get("anything")
                        check("RAMCleanup", case + ":value", r1[0] is expected_value and r2[0] is expected_value)
                        # Documented difference: no OS-level trimming and no sleeps in a sandboxed guest.
                        check("RAMCleanup", case + ":host-ops", ops2 == [], {"original": ops1, "v2": ops2})


def interface_cases():
    for node_id in ("VRAMCleanup", "RAMCleanup"):
        a, b = ORIGINAL.NODE_CLASS_MAPPINGS[node_id], CONVERTED.NODE_CLASS_MAPPINGS[node_id]
        ia, ib = a.INPUT_TYPES(), b.INPUT_TYPES()
        for section in ("required", "optional"):
            sa, sb = ia.get(section, {}), ib.get(section, {})
            check(node_id, f"inputs.{section}.names", list(sa) == list(sb), [list(sa), list(sb)])
            for name in sa:
                ta, oa = str(sa[name][0]), (sa[name][1] if len(sa[name]) > 1 else {})
                tb, ob = str(sb[name][0]), (sb[name][1] if len(sb[name]) > 1 else {})
                check(node_id, f"inputs.{section}.{name}.type", ta == tb, [ta, tb])
                # V3 serializes a few defaults explicitly; everything the original declares must be identical.
                missing = {k: (oa[k], ob.get(k, "<absent>")) for k in oa if ob.get(k, "<absent>") != oa[k]}
                check(node_id, f"inputs.{section}.{name}.options", not missing, missing)
        ha = {k: str(v) for k, v in ia.get("hidden", {}).items()}
        # V3's v1-compat projection gives hidden values as 1-tuples ('PROMPT',); V1 declares the bare string.
        hb = {k: (str(v[0]) if isinstance(v, (list, tuple)) and len(v) == 1 else str(v))
              for k, v in ib.get("hidden", {}).items()}
        # Documented difference: V3 adds the PROMPT hidden input to every output node.
        check(node_id, "hidden", all(hb.get(k) == v for k, v in ha.items()) and set(hb) - set(ha) <= {"prompt"},
              [ha, hb])
        check(node_id, "RETURN_TYPES", [str(t) for t in a.RETURN_TYPES] == [str(t) for t in b.RETURN_TYPES],
              [list(map(str, a.RETURN_TYPES)), list(map(str, b.RETURN_TYPES))])
        check(node_id, "RETURN_NAMES", list(a.RETURN_NAMES) == list(b.RETURN_NAMES))
        check(node_id, "OUTPUT_NODE", bool(a.OUTPUT_NODE) == bool(b.OUTPUT_NODE))
        check(node_id, "CATEGORY", a.CATEGORY == b.CATEGORY)
        check(node_id, "display_name",
              ORIGINAL.NODE_DISPLAY_NAME_MAPPINGS[node_id] == CONVERTED.NODE_DISPLAY_NAME_MAPPINGS[node_id]
              == b.GET_SCHEMA().display_name)
        saved = time.time
        time.time = lambda: 1700000000.25
        try:
            fa, fb = a.IS_CHANGED(), b.fingerprint_inputs()
        finally:
            time.time = saved
        check(node_id, "fingerprint(frozen clock)", fa == fb == 1700000000.25 and type(fa) is type(fb) is float,
              [fa, fb])


def negative_controls():
    controls = {}
    cls = CONVERTED.NODE_CLASS_MAPPINGS["VRAMCleanup"]
    original_execute = cls.execute

    async def broken(cls_, offload_model, offload_cache, anything=None):
        return CONVERTED.nodes.io.NodeOutput(None)
    cls.execute = classmethod(broken)
    try:
        value = object()
        r2, _, _ = run_converted("VRAMCleanup", dict(offload_model=False, offload_cache=False, anything=value))
        controls["perturbed-output-detected"] = r2[0] is not value
    finally:
        cls.execute = original_execute
    original_fp = cls.fingerprint_inputs
    cls.fingerprint_inputs = classmethod(lambda c, **k: 0.0)
    try:
        saved = time.time
        time.time = lambda: 1700000000.25
        try:
            controls["perturbed-fingerprint-detected"] = cls.fingerprint_inputs() != \
                ORIGINAL.NODE_CLASS_MAPPINGS["VRAMCleanup"].IS_CHANGED()
        finally:
            time.time = saved
    finally:
        cls.fingerprint_inputs = original_fp
    return controls


def main():
    vram_cases()
    ram_cases()
    interface_cases()
    controls = negative_controls()
    nodes = {}
    for node in ("VRAMCleanup", "RAMCleanup"):
        mine = [c for c in CHECKS if c["node"] == node]
        failed = [c for c in mine if not c["ok"]]
        nodes[node] = {"verdict": "EXACT" if not failed else "MISMATCH", "cases": len(mine),
                       "failed": failed[:10]}
    nodes["VRAMCleanup"]["known_differences"] = ["the prompt queue's free_memory flag is not set (no PromptServer in a guest)"]
    nodes["RAMCleanup"]["known_differences"] = ["no OS-level RAM trimming and no per-retry sleeps in a sandboxed guest",
                                                "the console message reports the skipped trim instead of RAM usage"]
    result = {"pack": "comfyui_memory_cleanup", "nodes": nodes,
              "negative_control": {**controls, "turned_red": all(controls.values())}}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "parity.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=str))
    print(json.dumps({n: (v["verdict"], v["cases"]) for n, v in nodes.items()}),
          json.dumps(result["negative_control"]))
    bad = any(v["verdict"] != "EXACT" for v in nodes.values()) or not result["negative_control"]["turned_red"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
