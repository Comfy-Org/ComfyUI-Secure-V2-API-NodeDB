"""Host proxy -> real guest, end to end, for comfyui-frame-interpolation (gate).

    DEPS=<weights dir> run_in_gate.sh <snapshot dir, or the pack folder> <.../v2/tests> <results> \
        test_comfyui-frame-interpolation_guest.py

These are the classes the host really registers: the proxies packdb builds from secure-nodes.json.
They are registered in core. An execution backend sends each SDK plan (validate_inputs and execute)
to a GuestSession, so every node body runs in a separate guest process. That process imports the v2
module the proxy points at. The checkpoint reaches it only through the host broker:
models.download_huggingface_weights, then assets.resolve/digest/load_state_dict.
Results are compared exactly with the pristine node (same harness as the parity test).
The gate container is the confinement; the guest sandbox kind is recorded.

Writes /results/guest.json; exits 1 on any failed check.
"""

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

import _fi_harness as H  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:300]}"))


async def outer(cls, **inputs):
    cls.GET_SCHEMA()
    out = await H.execution._async_map_node_over_list(
        prompt_id="fi-guest", unique_id="9", obj=cls,
        input_data_all={key: [value] for key, value in inputs.items()},
        func=cls.FUNCTION, v3_data=None)
    first = out[0]
    if isinstance(first, asyncio.Task):
        first = await first
    return tuple(first.result) if hasattr(first, "result") else tuple(first)


async def run() -> dict:
    H.register_weights()
    loaded = packdb.load_pack(H.snapshot_dir(), mount_name="custom_nodes.fi_guest_proxy",
                              pack_id=f"{H.SLUG}/{H.KEY}")
    proxies = loaded.node_mappings
    V1 = H.pristine_classes()
    v1_rife_module = sys.modules["vfi_models.rife"]
    v1_states = sys.modules["vfi_utils"].InterpolationStateList
    weights = H.load_package("fi_guest_weights_view", H.pack_head() / "v2")  # for file names only
    W = sys.modules["fi_guest_weights_view._fi_weights"]
    del weights

    facts = {"guest_runtime_root": str(loaded.v2_dir)}
    session = await GuestSession("fi-guest", guest_runtime_root=loaded.v2_dir).start()
    facts["sandbox_kind"] = session.sandbox_kind
    dispatched = []

    class Backend:
        # Mirrors the overlay's CloudExecutionBackend.dispatch (comfy_secure_nodes/execution.py
        # :430-483): grant the declared capabilities (+ raw for a values-mode plan, :127-128), wrap
        # values-mode inputs into refs (:433-436), then session.execute. The one step left out is
        # the per-pack user-consent filter (consent.py): declared capabilities are granted as if
        # consented.
        async def dispatch(self, plan, local_call, runtime):
            dispatched.append([plan.node_type, plan.method])
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps),
                                         tenant="fi-guest")

    previous_backend = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    previous = {node_id: H.core_nodes.NODE_CLASS_MAPPINGS.get(node_id)
                for node_id in ("RIFE VFI", "Make Interpolation State List", "CAIN VFI")}
    for node_id in previous:
        H.core_nodes.NODE_CLASS_MAPPINGS[node_id] = proxies[node_id]
    try:
        frames = H.frames(3, 64, 64, seed=11)
        base = dict(ckpt_name="rife49.pth", frames=frames, clear_cache_after_n_frames=10,
                    multiplier=3, fast_mode=True, ensemble=True, scale_factor=1.0, dtype="float32",
                    torch_compile=False, batch_size=1)
        # 1. RIFE through proxy -> guest, against the pristine node.
        got = await outer(proxies["RIFE VFI"], **base)
        with H.pristine_weights(v1_rife_module, W):
            want = V1["RIFE VFI"]().vfi(**base)
        ok, detail = H.same(tuple(want), tuple(got))
        record("guest/RIFE rife49 multiplier=3 == pristine", ok, detail)

        # 2. The state-list token is made in the guest and consumed by RIFE in the guest.
        (token,) = await outer(proxies["Make Interpolation State List"], frame_indices="0",
                               is_skip_list=True)
        record("guest/state-list token", token == {"frame_indices": [0], "is_skip_list": True}, token)
        got = await outer(proxies["RIFE VFI"], **dict(base, optional_interpolation_states=token))
        with H.pristine_weights(v1_rife_module, W):
            want = V1["RIFE VFI"]().vfi(**dict(base, optional_interpolation_states=v1_states(
                frame_indices=[0], is_skip_list=True)))
        ok, detail = H.same(tuple(want), tuple(got))
        record("guest/RIFE with guest-made states token == pristine", ok, detail)

        # 3. A refused node at queue time: core -> proxy -> guest validate_inputs.
        prompt = {"2": {"class_type": "EmptyImage",
                        "inputs": {"width": 64, "height": 64, "batch_size": 3, "color": 0}},
                  "4": {"class_type": "CAIN VFI",
                        "inputs": {"ckpt_name": "pretrained_cain.pth", "frames": ["2", 0],
                                   "clear_cache_after_n_frames": 10, "multiplier": 2}}}
        ok_flag, errors, _ = await H.execution.validate_inputs("fi-guest", prompt, "4", {})
        expected = ("comfyui-frame-interpolation/CAIN VFI is not yet converted to Secure Nodes V2: "
                    "its checkpoints (pretrained_cain.pth) are pickle files that have not yet been "
                    "converted to declared, verified weights")
        record("guest/CAIN refused at core validation via proxy",
               ok_flag is False and [e.get("details") for e in errors] == [f"ckpt_name - {expected}"],
               errors)
        record("guest/dispatched execute and validate_inputs",
               ["RIFE_VFI", "execute"] in dispatched
               and any(m == "validate_inputs" for _, m in dispatched), dispatched)
        facts["guest_pid"] = session.last_guest_pid
        record("guest/out-of-process", session.last_guest_pid not in (None, os.getpid()),
               [session.last_guest_pid, os.getpid()])
    finally:
        for node_id, cls in previous.items():
            if cls is None:
                H.core_nodes.NODE_CLASS_MAPPINGS.pop(node_id, None)
            else:
                H.core_nodes.NODE_CLASS_MAPPINGS[node_id] = cls
        _sdk.providers.register_execution_backend(previous_backend)
        await session.kill()
    facts["dispatched"] = dispatched
    return facts


def main() -> int:
    try:
        facts = asyncio.run(run())
    except Exception:  # noqa: BLE001
        facts = {"error": traceback.format_exc()}
        record("guest/session", False, facts["error"])
    failed = [item["check"] for item in checks if not item["ok"]]
    result = {"pack": H.SLUG, "checks": checks, "failed": failed, "facts": facts,
              "verdict": "PASS" if not failed else "FAIL"}
    Path("/results/guest.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
