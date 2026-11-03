"""Tier-1 parity for reservedvram: the original and v2 side by side in the gate container.

    run_in_gate.sh <pack root (pristine + v2/) or a snapshot dir holding it> <.../v2/tests> <results dir> \
        test_reservedvram_parity.py

Writes /results/parity.json and exits 1 on any failed check. ReservedVRAMSetter is a passthrough output node that
frees GPU memory and sets the host's reserved VRAM, so parity covers:
  * the outputs: the passthrough object (the very same object in-process; ExecutionBlocker(None) when nothing is
    connected), the seed, and the reserved value (type and float bits);
  * the host memory operations, recorded on the same comfy.model_management / gc functions on both sides. The
    original's EXTRA_RESERVED_VRAM assignment is recorded too: v2 cannot make it (known difference 1), but the value v2
    reports as requested must equal what the original set;
  * GPU memory readings: a CPU device (no GPU: both fall back to the manual value) and a fake CUDA device that feeds
    the same physical numbers to both sides. For the original this goes through torch.cuda.mem_get_info, and also
    through a fake NVML that reports used = total - free. For v2 it goes through Core's get_total_memory /
    get_free_memory behind the SDK's system.stats;
  * the console output, apart from v2's one extra line saying the host setting was not changed;
  * IS_CHANGED vs fingerprint_inputs, and that neither touches the global random state;
  * the node interface: INPUT_TYPES, RETURN_TYPES/NAMES, OUTPUT_NODE, CATEGORY and display name.
Two negative controls (a perturbed reserved value and a perturbed fingerprint) must turn red.
"""
import asyncio
import contextlib
import gc
import importlib.util
import io as _stdio
import json
import random
import sys
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]
from comfy.cli_args import args as _cli_args  # noqa: E402

_cli_args.cpu = True

import torch  # noqa: E402
import comfy.model_management as mm  # noqa: E402
from comfy_execution.graph_utils import ExecutionBlocker  # noqa: E402
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


ORIGINAL = load("rv_original", PACK)
ORIGINAL_NODES = sys.modules["rv_original.nodes"]
CONVERTED = load("rv_v2", V2)
NODE = "ReservedVRAMSetter"
V2_NOTE = "[ReservedVRAM]Secure Nodes V2: the host's reserved VRAM is not changed"

LOG = []
GIB = 1024 * 1024 * 1024


@contextlib.contextmanager
def recording():
    saved = (mm.unload_all_models, mm.soft_empty_cache, gc.collect, mm.EXTRA_RESERVED_VRAM)
    mm.unload_all_models = lambda *a, **k: LOG.append("unload_all_models")
    mm.soft_empty_cache = lambda *a, **k: LOG.append("soft_empty_cache")

    def _collect(*a, **k):
        LOG.append("gc.collect")
        return 0
    gc.collect = _collect
    mm.EXTRA_RESERVED_VRAM = -12345  # sentinel: shows whether a run assigned it
    LOG.clear()
    try:
        yield LOG
    finally:
        mm.unload_all_models, mm.soft_empty_cache, gc.collect, mm.EXTRA_RESERVED_VRAM = saved


# A device as both sides see it: total, the CUDA driver's free bytes, and torch's reserved-but-inactive bytes.
DEVICES = {
    "cpu": None,
    "cuda-24g": {"total": 24 * GIB, "free_cuda": 24 * GIB - 3_435_973_837, "torch_free": 512 * 1024 * 1024},
    "cuda-8g-busy": {"total": 8 * GIB, "free_cuda": 1_288_490_189, "torch_free": 0},
}


@contextlib.contextmanager
def original_device(device, nvml):
    """The original's view: pynvml (fake) or torch.cuda.mem_get_info (fake) on a CUDA device; nothing on CPU."""
    saved = (ORIGINAL_NODES.pynvml_installed, ORIGINAL_NODES.pynvml, torch.cuda.is_available,
             getattr(torch.cuda, "mem_get_info", None))
    try:
        if device is None:
            ORIGINAL_NODES.pynvml_installed, ORIGINAL_NODES.pynvml = False, None
            torch.cuda.is_available = lambda: False
        else:
            torch.cuda.is_available = lambda: True
            torch.cuda.mem_get_info = lambda *a: (device["free_cuda"], device["total"])
            if nvml:
                info = types.SimpleNamespace(total=device["total"], used=device["total"] - device["free_cuda"])
                ORIGINAL_NODES.pynvml_installed = True
                ORIGINAL_NODES.pynvml = types.SimpleNamespace(nvmlDeviceGetHandleByIndex=lambda index: "gpu0",
                                                              nvmlDeviceGetMemoryInfo=lambda handle: info)
            else:
                ORIGINAL_NODES.pynvml_installed, ORIGINAL_NODES.pynvml = False, None
        yield
    finally:
        (ORIGINAL_NODES.pynvml_installed, ORIGINAL_NODES.pynvml, torch.cuda.is_available) = saved[:3]
        if saved[3] is not None:
            torch.cuda.mem_get_info = saved[3]


@contextlib.contextmanager
def host_device(device):
    """The host's view behind system.stats: Core's memory functions on a fake CUDA primary device."""
    if device is None:
        yield
        return
    names = ("get_torch_device", "get_all_torch_devices", "get_total_memory", "get_free_memory",
             "get_torch_device_name")
    saved = {name: getattr(mm, name) for name in names}
    cuda0, cpu = torch.device("cuda", 0), torch.device("cpu")

    def total_memory(dev=None, torch_total_too=False):
        if dev is not None and dev.type == "cpu":
            return 64 * GIB if not torch_total_too else (64 * GIB, 64 * GIB)
        return (device["total"], 2 * GIB) if torch_total_too else device["total"]

    def free_memory(dev=None, torch_free_too=False):
        if dev is not None and dev.type == "cpu":
            return 32 * GIB if not torch_free_too else (32 * GIB, 32 * GIB)
        free = device["free_cuda"] + device["torch_free"]
        return (free, device["torch_free"]) if torch_free_too else free

    try:
        mm.get_torch_device = lambda: cuda0
        mm.get_all_torch_devices = lambda *a, **k: [cuda0]
        mm.get_total_memory = total_memory
        mm.get_free_memory = free_memory
        mm.get_torch_device_name = lambda dev: "Fake CUDA device"
        yield
    finally:
        for name, value in saved.items():
            setattr(mm, name, value)


@contextlib.contextmanager
def runtime(permissions):
    refs = _sdk.InProcessRefResolver()
    plan = sdk.ExecutionPlan(prompt_id="reservedvram-parity", node_id="1", node_type=NODE,
                             permissions=tuple(permissions))
    context = _sdk.InProcessCtxProvider().build(plan)
    with _sdk.bind_runtime(refs, context, _sdk.InProcessOps()):
        try:
            yield context
        finally:
            refs.clear()


def run_original(kwargs, device, nvml):
    cls = ORIGINAL.NODE_CLASS_MAPPINGS[NODE]
    out = _stdio.StringIO()
    with recording() as log, original_device(device, nvml), contextlib.redirect_stdout(out):
        result = getattr(cls(), cls.FUNCTION)(**kwargs)
        reserved_set = mm.EXTRA_RESERVED_VRAM
        ops = list(log)
    return result, ops, out.getvalue(), reserved_set


def run_converted(kwargs, device, perturb=0.0):
    cls = CONVERTED.NODE_CLASS_MAPPINGS[NODE]
    out = _stdio.StringIO()
    with recording() as log, host_device(device), contextlib.redirect_stdout(out), runtime(cls.SDK_PERMISSIONS):
        result = asyncio.run(cls.execute(**kwargs))
        reserved_set = mm.EXTRA_RESERVED_VRAM
        ops = list(log)
    args = tuple(result.args)
    if perturb:
        args = (args[0], args[1], args[2] + perturb)
    return args, ops, out.getvalue(), reserved_set


def same_number(a, b):
    if type(a) is not type(b):
        return False
    return a.hex() == b.hex() if isinstance(a, float) else a == b


def values():
    return [("none", None), ("int", 0), ("str", "text"), ("image", torch.zeros((1, 8, 8, 3))),
            ("latent", {"samples": torch.zeros((1, 4, 8, 8))}), ("opaque", object())]


CHECKS = []


def check(case, what, ok, detail=None):
    CHECKS.append({"case": case, "check": what, "ok": bool(ok), "detail": None if ok else detail})
    return bool(ok)


def requested_from_note(stdout):
    for line in stdout.splitlines():
        if line.startswith(V2_NOTE):
            return float(line.split("(requested ", 1)[1].split("GB", 1)[0])
    return None


def node_cases():
    count = 0
    for device_name, device in DEVICES.items():
        for nvml in ((False, True) if device is not None else (False,)):
            for mode in ("manual", "auto"):
                for reserved in (-2.0, -0.5, 0.0, 0.6, 1.25, 7.0):
                    for auto_max in (0.0, 0.5, 3.0):
                        for clean in (True, False):
                            for seed in (0, 7, -1):
                                for name, value in values():
                                    kwargs = dict(reserved=reserved, mode=mode, seed=seed, auto_max_reserved=auto_max,
                                                  clean_gpu_before=clean)
                                    if name != "none":
                                        kwargs["anything"] = value
                                    case = (f"{device_name},nvml={nvml},{mode},r={reserved},max={auto_max},"
                                            f"clean={clean},seed={seed},{name}")
                                    r1, ops1, out1, set1 = run_original(dict(kwargs), device, nvml)
                                    r2, ops2, out2, set2 = run_converted(dict(kwargs), device)
                                    count += 1
                                    compare(case, kwargs, r1, ops1, out1, set1, r2, ops2, out2, set2)
    return count


def compare(case, kwargs, r1, ops1, out1, set1, r2, ops2, out2, set2):
    expected = kwargs.get("anything")
    if expected is None:
        ok = (isinstance(r1[0], ExecutionBlocker) and isinstance(r2[0], ExecutionBlocker)
              and r1[0].message is None and r2[0].message is None)
    else:
        ok = r1[0] is expected and r2[0] is expected
    check(case, "output", ok, [type(r1[0]).__name__, type(r2[0]).__name__])
    check(case, "seed", same_number(r1[1], r2[1]), [r1[1], r2[1]])
    check(case, "reserved_value", same_number(r1[2], r2[2]), [repr(r1[2]), repr(r2[2])])
    check(case, "host_ops", ops1 == ops2, {"original": ops1, "v2": ops2})
    # Known difference 1: the original assigns EXTRA_RESERVED_VRAM; v2 leaves it alone but reports the same request.
    requested = requested_from_note(out2)
    original_bytes = set1
    check(case, "original_assigned_reservation", original_bytes != -12345, original_bytes)
    check(case, "v2_left_reservation_alone", set2 == -12345, set2)
    check(case, "v2_requested_equals_original_set",
          requested is not None and int(requested * GIB) == original_bytes, [requested, original_bytes])
    stripped = "".join(line + "\n" for line in out2.splitlines() if not line.startswith(V2_NOTE))
    check(case, "stdout", out1 == stripped, {"original": out1, "v2": stripped})


def fingerprint_cases():
    a, b = ORIGINAL.NODE_CLASS_MAPPINGS[NODE], CONVERTED.NODE_CLASS_MAPPINGS[NODE]
    kwargs = dict(reserved=0.6, mode="auto", auto_max_reserved=0.0, clean_gpu_before=True)
    for seed in (0, 1, 7, 1125899906842624):
        check(f"seed={seed}", "fingerprint", a.IS_CHANGED(seed=seed, **kwargs) == b.fingerprint_inputs(seed=seed, **kwargs))
    before = random.getstate()
    drawn_a = [a.IS_CHANGED(seed=-1, **kwargs) for _ in range(5)]
    drawn_b = [b.fingerprint_inputs(seed=-1, **kwargs) for _ in range(5)]
    check("seed=-1", "global_random_untouched", random.getstate() == before)
    check("seed=-1", "fingerprint_range",
          all(isinstance(x, int) and 1 <= x <= 1125899906842624 for x in drawn_a + drawn_b), [drawn_a, drawn_b])
    check("seed=-1", "fingerprint_changes_every_call", len(set(drawn_a)) == 5 and len(set(drawn_b)) == 5)


def interface_cases():
    a, b = ORIGINAL.NODE_CLASS_MAPPINGS[NODE], CONVERTED.NODE_CLASS_MAPPINGS[NODE]
    ia, ib = a.INPUT_TYPES(), b.INPUT_TYPES()
    for section in ("required", "optional"):
        sa, sb = ia.get(section, {}), ib.get(section, {})
        check("interface", f"inputs.{section}.names", list(sa) == list(sb), [list(sa), list(sb)])
        for name in sa:
            ta, oa = sa[name][0], (sa[name][1] if len(sa[name]) > 1 else {})
            tb, ob = sb[name][0], (sb[name][1] if len(sb[name]) > 1 else {})
            ta = list(ta) if isinstance(ta, list) else str(ta)
            tb = list(tb) if isinstance(tb, list) else str(tb)
            if ta == ["manual", "auto"] and tb == "COMBO":  # V3 projects a combo as ("COMBO", {"options": [...]})
                tb = list(ob.get("options", []))
            check("interface", f"inputs.{section}.{name}.type", ta == tb, [ta, tb])
            missing = {k: (oa[k], ob.get(k, "<absent>")) for k in oa if ob.get(k, "<absent>") != oa[k]}
            check("interface", f"inputs.{section}.{name}.options", not missing, missing)
    ha = {k: str(v) for k, v in ia.get("hidden", {}).items()}
    hb = {k: (str(v[0]) if isinstance(v, (list, tuple)) and len(v) == 1 else str(v))
          for k, v in ib.get("hidden", {}).items()}
    # V3 adds the PROMPT hidden input to every output node (documented).
    check("interface", "hidden", all(hb.get(k) == v for k, v in ha.items()) and set(hb) - set(ha) <= {"prompt"},
          [ha, hb])
    check("interface", "RETURN_TYPES", [str(x) for x in a.RETURN_TYPES] == [str(x) for x in b.RETURN_TYPES],
          [list(map(str, a.RETURN_TYPES)), list(map(str, b.RETURN_TYPES))])
    check("interface", "RETURN_NAMES", list(a.RETURN_NAMES) == list(b.RETURN_NAMES),
          [list(a.RETURN_NAMES), list(b.RETURN_NAMES)])
    check("interface", "OUTPUT_NODE", bool(a.OUTPUT_NODE) == bool(b.OUTPUT_NODE))
    check("interface", "CATEGORY", a.CATEGORY == b.CATEGORY, [a.CATEGORY, b.CATEGORY])
    check("interface", "display_name",
          ORIGINAL.NODE_DISPLAY_NAME_MAPPINGS[NODE] == CONVERTED.NODE_DISPLAY_NAME_MAPPINGS[NODE])


def negative_controls():
    kwargs = dict(reserved=0.6, mode="manual", seed=0, auto_max_reserved=0.0, clean_gpu_before=False)
    r1, *_ = run_original(dict(kwargs), None, False)
    r2, *_ = run_converted(dict(kwargs), None, perturb=1e-9)
    value_red = not same_number(r1[2], r2[2])
    a, b = ORIGINAL.NODE_CLASS_MAPPINGS[NODE], CONVERTED.NODE_CLASS_MAPPINGS[NODE]
    fingerprint_red = a.IS_CHANGED(seed=5) != b.fingerprint_inputs(seed=5) + 1
    return {"perturbed_reserved_value": value_red, "perturbed_fingerprint": fingerprint_red}


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    cases = node_cases()
    fingerprint_cases()
    interface_cases()
    controls = negative_controls()
    failed = [c for c in CHECKS if not c["ok"]]
    verdict = "PASS" if not failed and all(controls.values()) else "FAIL"
    report = {
        "pack": "reservedvram",
        "node": NODE,
        "verdict": verdict,
        "node_cases": cases,
        "checks": len(CHECKS),
        "failed_checks": len(failed),
        "failed_examples": failed[:20],
        "negative_controls": controls,
        "nodes": {NODE: {"verdict": "EXACT" if not failed else "MISMATCH", "cases": cases}},
        "known_differences": ["the host's EXTRA_RESERVED_VRAM is not changed (no SDK verb); v2 reports the same value",
                              "one extra console line saying so"],
    }
    (RESULTS / "parity.json").write_text(json.dumps(report, indent=1, default=str))
    print(json.dumps({k: report[k] for k in ("verdict", "node_cases", "checks", "failed_checks",
                                             "negative_controls")}, indent=1))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
