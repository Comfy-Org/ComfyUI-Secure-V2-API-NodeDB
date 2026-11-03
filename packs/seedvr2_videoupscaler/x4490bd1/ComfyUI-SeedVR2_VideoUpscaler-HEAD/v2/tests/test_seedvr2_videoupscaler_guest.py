"""Host proxy -> real guest, end to end, for seedvr2_videoupscaler (gate).

    DEPS=<wheels + checkpoints, see _sv_harness.py> run_in_gate.sh <snapshot dir, or the pack folder> \
        <.../v2/tests> <results> test_seedvr2_videoupscaler_guest.py

The proxies packdb builds from secure-nodes.json are registered in core. An execution backend
mirroring the overlay's CloudExecutionBackend.dispatch sends every plan to a GuestSession. So the
config nodes run in a separate process: that process imports the pack and reads the executing node
id through the SDK graph domain. The GGUF refusal is checked at core's queue-time validation, also
through the guest. Results are compared exactly with the pristine nodes.

The upscaler itself is not run through the guest here: its multi-GB checkpoint would have to cross
the container's guest transport. Its tier-1 parity runs in-process (parity test), and the guest
run belongs to tier 2.

Writes /results/guest.json; exits 1 on any failed check.
"""

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

import _sv_harness as H  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

checks = []
GGUF_REFUSAL = ("seedvr2_videoupscaler: the GGUF checkpoint 'seedvr2_ema_3b-Q4_K_M.gguf' is not "
                "available in Secure Nodes V2 yet. Its reader needs a model file on disk, and a Secure "
                "Nodes guest receives verified tensors, not files. Use a .safetensors model "
                "(e.g. seedvr2_ema_3b_fp8_e4m3fn.safetensors).")


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:300]}"), flush=True)


async def run() -> dict:
    H.setup_weights()
    loaded = packdb.load_pack(H.snapshot_dir(), mount_name="custom_nodes.sv_guest_proxy",
                              pack_id=f"{H.SLUG}/{H.KEY}")
    proxies = loaded.node_mappings
    H.load_package("seedvr2_pristine", H.pack_head())
    P = sys.modules["seedvr2_pristine.src.interfaces"]
    # The guest imports the node module from the file the proxy points at (the v2 tree). Its
    # PYTHONPATH is its runtime root. In production the pack's dependency profile supplies
    # diffusers, omegaconf, rotary_embedding_torch, gguf and cv2; here /deps (the same pinned
    # wheels, unpacked) stands in for that profile.
    facts = {"guest_runtime_root": "/deps", "module_root": str(loaded.v2_dir)}
    session = await GuestSession("sv-guest", guest_runtime_root=Path("/deps")).start()
    facts["sandbox_kind"] = session.sandbox_kind
    dispatched = []

    class Backend:
        # As comfy_secure_nodes/execution.py:430-483, without the per-pack consent filter.
        async def dispatch(self, plan, local_call, runtime):
            dispatched.append([plan.node_type, plan.method])
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="sv-guest")

    previous_backend = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    previous = {node_id: H.core_nodes.NODE_CLASS_MAPPINGS.get(node_id) for node_id in proxies}
    for node_id, proxy in proxies.items():
        H.core_nodes.NODE_CLASS_MAPPINGS[node_id] = proxy
    try:
        compile_inputs = dict(backend="inductor", mode="reduce-overhead", fullgraph=True, dynamic=False,
                              dynamo_cache_size_limit=32, dynamo_recompile_limit=64)
        got = await H.run_v2(proxies["SeedVR2TorchCompileSettings"], node_id="51", **compile_inputs)
        want = H.run_pristine(P.SeedVR2TorchCompileSettings, node_id="51", **compile_inputs)
        record("guest/TorchCompileSettings == pristine", *H.same(want, got))
        dit_inputs = dict(model=H.DIT, device="cuda:0", offload_device="cpu", cache_model=True,
                          blocks_to_swap=8, swap_io_components=True, attention_mode="sdpa",
                          torch_compile_args=want[0])
        got = await H.run_v2(proxies["SeedVR2LoadDiTModel"], node_id="52", **dit_inputs)
        expected = H.run_pristine(P.SeedVR2LoadDiTModel, node_id="52", **dit_inputs)
        record("guest/LoadDiTModel == pristine (node_id via SDK graph)", *H.same(expected, got))
        vae_inputs = dict(model=H.VAE, device="cuda:0", encode_tiled=True, decode_tiled=True,
                          tile_debug="decode")
        got = await H.run_v2(proxies["SeedVR2LoadVAEModel"], node_id="53", **vae_inputs)
        expected = H.run_pristine(P.SeedVR2LoadVAEModel, node_id="53", **vae_inputs)
        record("guest/LoadVAEModel == pristine (node_id via SDK graph)", *H.same(expected, got))
        prompt = {"5": {"class_type": "SeedVR2LoadDiTModel",
                        "inputs": {"model": "seedvr2_ema_3b-Q4_K_M.gguf", "device": "cuda:0"}}}
        ok_flag, errors, _ = await H.execution.validate_inputs("sv-guest", prompt, "5", {})
        record("guest/GGUF refused at core validation via proxy",
               ok_flag is False and [e.get("details") for e in errors] == [f"model - {GGUF_REFUSAL}"],
               errors)
        record("guest/dispatched", ["SeedVR2LoadDiTModel", "execute"] in dispatched
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
