"""Tier-1 parity for RES4LYF's small value nodes: the ORIGINAL in-process vs V2 in a real guest (gate only).

Nodes: TextBox1, SetImageSizeWithScale, "Sigmas Power". The original package is imported in this process (it needs
its own test dependencies on /deps); each V2 node runs in a comfy_secure_nodes GuestSession with exactly its
declared permissions. Comparisons are type-strict; tensors compare by dtype, shape and bits (torch.equal, which
treats equal infinities as equal). Writes /results/simple.json; exit 1 on any difference.
Run: DEPS=<original's test deps> run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> test_res4lyf_simple.py
"""
import asyncio
import importlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay"]
if Path("/deps").is_dir():
    sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import torch  # noqa: E402

import folder_paths  # noqa: E402,F401
import server  # noqa: E402
from aiohttp import web  # noqa: E402

server.PromptServer.instance = types.SimpleNamespace(
    routes=web.RouteTableDef(), supports={"custom_nodes_from_web"}, send_sync=lambda *a, **k: None,
    client_id=None, last_node_id=None)

from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK = Path(os.environ.get("RES4_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("RES4_RESULTS", "/results"))
TMP = Path(tempfile.mkdtemp(prefix="res4-simple-"))
shutil.copytree(PACK, TMP / "RES4LYF", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
ORIGINAL = dict(importlib.import_module("RES4LYF").NODE_CLASS_MAPPINGS)


def import_package(name, root):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SECURE = dict(import_package("res4lyf_secure", V2).NODE_CLASS_MAPPINGS)
GUEST = {"session": None, "pids": set()}
ROWS = []


async def run_v2(node_id, inputs):
    cls = SECURE[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope("res4-simple", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="res4-simple", node_id="9", node_type=cls.__name__, tier="sandbox", node_module=cls.__module__,
            inputs=dict(inputs), input_mode="refs" if getattr(cls, "SDK_REFS", False) else "values",
            method="execute", permissions=permissions, prompt=None, extra_pnginfo=None,
            dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if GUEST["session"] is None:
            GUEST["session"] = await GuestSession("res4-simple", guest_runtime_root=V2).start()
        guest = GUEST["session"]
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="res4-simple")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        return tuple([await refs.resolve(v) if isinstance(v, _sdk.Ref) else v for v in (result.result or ())])
    finally:
        scope.__exit__(None, None, None)


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, torch.Tensor):
        return a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
    if isinstance(a, float):
        return a.hex() == b.hex()
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def show(value):
    if isinstance(value, torch.Tensor):
        return {"dtype": str(value.dtype), "values": [float(v).hex() for v in value.flatten().tolist()][:12]}
    if isinstance(value, (list, tuple)):
        return [show(v) for v in value]
    return value if not isinstance(value, str) or len(value) < 80 else value[:77] + "..."


def cases():
    out = []
    for text in ("", "a", "multi\nline ☀ \U0001d11e", "  spaced  ", "x" * 10000):
        out.append(("TextBox1", {"text1": text}))
    for width, height, scale in ((1024, 1024, 1.0), (1000, 777, 1.5), (512, 768, 0.333), (1, 1, 0.0),
                                 (10000, 10000, 10000.0), (833, 1217, 2.71828), (7, 3, 0.9999999), (640, 480, 0.1)):
        out.append(("SetImageSizeWithScale", {"width": width, "height": height, "scale_by": scale}))
    schedules = {
        "karras_f32": torch.tensor([14.614642, 7.4930, 3.5961, 1.5761, 0.6146, 0.2068, 0.0291675, 0.0],
                                   dtype=torch.float32),
        "karras_f64": torch.tensor([14.614642, 7.4930, 3.5961, 1.5761, 0.6146, 0.2068, 0.0291675, 0.0],
                                   dtype=torch.float64),
        "flow_f32": torch.linspace(1.0, 0.0, 9, dtype=torch.float32),
        "no_zero_f32": torch.tensor([10.0, 5.0, 2.5, 1.25, 0.6], dtype=torch.float32),
    }
    for name, sigmas in schedules.items():
        for power in (1.0, 2.0, 0.5, 3.7, 0.0, -1.0, -0.5, 100.0):
            out.append(("Sigmas Power", {"sigmas": sigmas.clone(), "power": power, "_label": name}))
    return out


async def main():
    for node_id, inputs in cases():
        label = inputs.pop("_label", None)
        case = f"{node_id}:{label + ':' if label else ''}" + ",".join(
            f"{k}={v if not isinstance(v, (torch.Tensor, str)) else (len(v) if isinstance(v, str) else 'tensor')}"
            for k, v in inputs.items())
        cls = ORIGINAL[node_id]
        try:
            expected = tuple(getattr(cls(), cls.FUNCTION)(**{k: (v.clone() if isinstance(v, torch.Tensor) else v)
                                                            for k, v in inputs.items()}))
            expected_error = None
        except Exception as error:  # noqa: BLE001
            expected, expected_error = None, f"{type(error).__name__}: {error}"
        try:
            actual = await run_v2(node_id, inputs)
            actual_error = None
        except Exception as error:  # noqa: BLE001
            actual, actual_error = None, f"{type(error).__name__}: {error}"[:300]
        if expected_error or actual_error:
            ok = bool(expected_error) and bool(actual_error)
            verdict = "BOTH_FAIL" if ok else "MISMATCH"
        else:
            ok = same(expected, actual)
            verdict = "EXACT" if ok else "MISMATCH"
        ROWS.append({"node": node_id, "case": case, "verdict": verdict, "expected": show(expected),
                     "actual": show(actual), "expected_error": expected_error, "actual_error": actual_error})
        if verdict != "EXACT":
            print(verdict, case, expected_error, actual_error, flush=True)
    if GUEST["session"] is not None:
        await GUEST["session"].kill()
    alive = [pid for pid in GUEST["pids"] if Path(f"/proc/{pid}").exists()]
    totals = {}
    for row in ROWS:
        totals.setdefault(row["node"], {}).setdefault(row["verdict"], 0)
        totals[row["node"]][row["verdict"]] += 1
    doc = {"totals": totals, "guest_pids": sorted(GUEST["pids"]), "alive_after_kill": alive, "rows": ROWS}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "simple.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("totals", "guest_pids", "alive_after_kill")}, indent=1))
    return 1 if any(r["verdict"] == "MISMATCH" for r in ROWS) or alive else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
