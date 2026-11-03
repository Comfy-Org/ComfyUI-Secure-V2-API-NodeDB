"""Regression test for comfyui-ppm repair r1: AttentionCouplePPM captures MASK refs (gate).

    run_in_gate.sh <snapshot dir x80f6c43, or the pack folder> <.../v2/tests> <results> \
        test_attention_couple_mask_refs.py

The case is the one that failed in deployment: the masks come from core nodes (SolidMask and MaskComposite) and
reach the SDK_REFS node through core's own refs-mode input wrapping, which types any tensor as an IMAGE
ref. The deployed runtime's regional_attention capture schema accepts only MASK refs ("masks[0] must be a MASK ref, got
ImageRef"). The gate's SDK predates that check, so the test adds the same rule to the closure kind's
validate_captures, the function both the in-process SDK and the guest host call. It then checks:
  * in-process (core's V3 path, in-process SDK): the node retains its closure; every captured mask is a
    MASK ref holding exactly the tensor the core node produced; the base and region conditionings arrive;
  * through a real guest (host proxy from secure-nodes.json, backend mirroring CloudExecutionBackend,
    GuestSession): the host accepts the captures under the same rule;
  * negative control: with the repair's re-declaration switched off, the rule rejects the capture with
    the deployed runtime's message.
Attaching the closure to a real UNet is not exercised (no checkpoint in the CPU gate); the host's
attach_model is replaced by a recorder. Writes /results/mask_refs.json; exits 1 on any failed check.
"""

import asyncio
import importlib.util
import json
import os
import shutil
import sys
import traceback
import types
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import nodes as core_nodes  # noqa: E402
import torch  # noqa: E402
from comfy_api.latest import _node_closures, _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport import host as host_module  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

PACK_FOLDER = "ComfyUI-ppm-HEAD"
checks = []
RECORD = {"kinds": [], "masks": [], "conditionings": 0, "attached": 0}


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    return heads[0]


def snapshot_dir() -> Path:
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/ppm-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER, ignore=shutil.ignore_patterns("__pycache__"))
    return snap


def load_package(name, folder):
    spec = importlib.util.spec_from_file_location(name, folder / "__init__.py",
                                                  submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_typed_capture_rule():
    """The deployed runtime's regional_attention captures: masks must be MASK refs, conditionings CONDITIONING refs."""
    spec = _node_closures.get_kind("regional_attention")
    original = spec.validate_captures

    def validate_captures(captures):
        captures = dict(captures or {})
        for index, item in enumerate(captures.get("masks") or []):
            RECORD["kinds"].append(type(item).__name__)
            if not isinstance(item, _sdk.MaskRef):
                raise _node_closures.ClosureError(
                    f"masks[{index}] must be a MASK ref, got {type(item).__name__}")
        for index, item in enumerate(captures.get("conditionings") or []):
            if not isinstance(item, _sdk.CondRef):
                raise _node_closures.ClosureError(
                    f"conditionings[{index}] must be a CONDITIONING ref, got {type(item).__name__}")
        return original(captures)

    try:
        object.__setattr__(spec, "validate_captures", validate_captures)
    except Exception:  # noqa: BLE001
        spec.validate_captures = validate_captures


def install_recorders():
    """Record the resolved captures; replace attaching to a UNet (none in the gate)."""
    in_process = _sdk._InProcessClosures
    original_retain = in_process.retain

    async def retain(self, kind, fn, *, captures=None):
        ref = await original_retain(self, kind, fn, captures=captures)
        entry = await _sdk.current_runtime().refs.resolve(ref)
        RECORD["masks"] = [m for m in entry["captures"].get("masks", [])]
        RECORD["conditionings"] = len(entry["captures"].get("conditionings", []))
        return ref

    async def attach_model(self, closure, model):
        RECORD["attached"] += 1
        return model

    in_process.retain = retain
    in_process.attach_model = attach_model

    async def h_attach_model(self, closure, model):
        RECORD["attached"] += 1
        return model

    host_module.GuestSession._h_closures_attach_model = h_attach_model


def core_masks():
    """The failing graph's masks, made by core's own nodes (comfy_extras/nodes_mask.py)."""
    from comfy_extras import nodes_mask

    base = nodes_mask.SolidMask.execute(value=1.0, width=128, height=128).result[0]
    zero = nodes_mask.SolidMask.execute(value=0.0, width=128, height=128).result[0]
    region = nodes_mask.SolidMask.execute(value=1.0, width=64, height=128).result[0]
    half = nodes_mask.MaskComposite.execute(destination=zero, source=region, x=0, y=0,
                                            operation="add").result[0]
    return base, half


def conditioning(seed):
    g = torch.Generator().manual_seed(seed)
    return [[torch.randn(1, 77, 768, generator=g), {"pooled_output": torch.randn(1, 768, generator=g)}]]


class Model:
    """Stands in for a ModelPatcher on the way in (typed MODEL by core's wrapping)."""
    model_options = {}
    load_device = "cpu"


async def run_node(cls, inputs):
    cls.GET_SCHEMA()
    out = await execution._async_map_node_over_list(
        prompt_id="ppm-mask-refs", unique_id="20", obj=cls,
        input_data_all={key: [value] for key, value in inputs.items()},
        func=cls.FUNCTION, v3_data=None)
    first = out[0]
    if isinstance(first, asyncio.Task):
        first = await first
    return first


async def run() -> dict:
    facts = {}
    install_typed_capture_rule()
    install_recorders()
    head = pack_head()
    base_mask, half_mask = core_masks()
    inputs = {"model": Model(), "base_cond": conditioning(1), "base_mask": base_mask,
              "cond_1": conditioning(2), "mask_1": half_mask}

    # In-process: core's V3 refs path and the in-process SDK.
    package = load_package("ppm_v2", head / "v2")
    cls = package.NODE_CLASS_MAPPINGS["AttentionCouplePPM"]
    facts["permissions"] = list(cls.SDK_PERMISSIONS)
    RECORD.update(kinds=[], masks=[], conditionings=0, attached=0)
    try:
        await run_node(cls, dict(inputs))
        ok = (RECORD["kinds"] == ["MaskRef", "MaskRef"] and RECORD["attached"] == 1
              and len(RECORD["masks"]) == 2 and RECORD["conditionings"] == 1
              and torch.equal(RECORD["masks"][0], base_mask) and torch.equal(RECORD["masks"][1], half_mask))
        record("in-process: masks captured as MASK refs holding the core nodes' tensors", ok,
               {"kinds": RECORD["kinds"], "attached": RECORD["attached"], "n": len(RECORD["masks"])})
    except Exception:  # noqa: BLE001
        record("in-process: masks captured as MASK refs holding the core nodes' tensors", False,
               traceback.format_exc()[-1500:])

    # Negative control: switch the re-declaration off; the typed-capture rule must reject the capture.
    nodes_module = sys.modules.get("ppm_v2.nodes")
    saved = getattr(nodes_module, "_as_mask_ref", None)
    if saved is not None:
        async def identity(value):
            return value
        nodes_module._as_mask_ref = identity
        try:
            await run_node(cls, dict(inputs))
            record("negative control: without the repair the capture is rejected", False, "accepted")
        except Exception as error:  # noqa: BLE001
            record("negative control: without the repair the capture is rejected",
                   "masks[0] must be a MASK ref, got ImageRef" in str(error), repr(error)[:400])
        finally:
            nodes_module._as_mask_ref = saved
    else:
        record("negative control: without the repair the capture is rejected", False,
               "nodes._as_mask_ref is missing (unrepaired tree)")

    # Through a real guest.
    loaded = packdb.load_pack(snapshot_dir(), mount_name="custom_nodes.ppm_guest_proxy",
                              pack_id="comfyui-ppm/x80f6c43")
    proxy = loaded.node_mappings["AttentionCouplePPM"]
    session = await GuestSession("ppm-guest").start()
    facts["sandbox_kind"] = session.sandbox_kind

    class Backend:
        async def dispatch(self, plan, local_call, runtime):
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            facts["guest_caps"] = sorted(caps)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="ppm-guest")

    previous = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    RECORD.update(kinds=[], attached=0)
    try:
        await run_node(proxy, dict(inputs))
        record("guest: the host accepts the captures under the typed-capture rule",
               RECORD["kinds"] == ["MaskRef", "MaskRef"] and RECORD["attached"] == 1,
               {"kinds": RECORD["kinds"], "attached": RECORD["attached"]})
    except Exception:  # noqa: BLE001
        record("guest: the host accepts the captures under the typed-capture rule", False, traceback.format_exc()[-1500:])
    finally:
        _sdk.providers.register_execution_backend(previous)
        facts["guest_pid"] = session.last_guest_pid
        await session.kill()
    record("guest: out-of-process", facts.get("guest_pid") not in (None, os.getpid()), facts.get("guest_pid"))
    return facts


def main() -> int:
    try:
        facts = asyncio.run(run())
    except Exception:  # noqa: BLE001
        facts = {"error": traceback.format_exc()}
        record("session", False, facts["error"])
    failed = [c["check"] for c in checks if not c["ok"]]
    result = {"pack": "comfyui-ppm", "repair": "r1", "checks": checks, "failed": failed, "facts": facts,
              "verdict": "PASS" if not failed else "FAIL"}
    Path("/results/mask_refs.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
