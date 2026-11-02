"""The NF4 refusal through a real guest process, in the gate.

    run_in_gate.sh <snapshot dir holding ComfyUI_bitsandbytes_NF4-HEAD> \
        <.../v2/tests> <results dir> test_comfyui_bitsandbytes_nf4_guest.py

Core's own validation and execution paths run CheckpointLoaderNF4 with an
execution backend that sends every SDK plan to a GuestSession started on a
fresh copy of v2. The guest, not this process, must produce the refusal: at
queue time (validate_inputs) and at execute. No bitsandbytes is mounted here.
The gate container is the confinement; the guest sandbox kind is recorded.

Writes /results/guest.json; exits 1 on any failed check.
"""

import asyncio
import json
import os
import shutil
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import nodes as core_nodes  # noqa: E402  (ComfyUI's nodes.py)
import execution  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402
from encode_manifest import load_package, pack_head  # noqa: E402
from test_comfyui_bitsandbytes_nf4_parity import EXPECTED_REFUSAL, NODE_ID  # noqa: E402

checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))


async def run() -> dict:
    v2 = pack_head() / "v2"
    fresh = Path("/tmp/nf4-guest/v2")
    shutil.copytree(v2, fresh, ignore=shutil.ignore_patterns(
        "tests", "__pycache__", ".pytest_cache"))
    module = load_package("nf4_guest_v2", fresh)
    cls = module.NODE_CLASS_MAPPINGS[NODE_ID]
    facts = {}
    previous_backend = _sdk.providers.execution_backend
    previous_class = core_nodes.NODE_CLASS_MAPPINGS.get(NODE_ID)
    session = await GuestSession("nf4-guest", guest_runtime_root=fresh).start()
    facts["sandbox_kind"] = session.sandbox_kind
    dispatched = []

    class Backend:
        async def dispatch(self, plan, local_call, runtime):
            dispatched.append(plan.method)
            return await session.execute(plan, runtime, capabilities=(), tenant="nf4-parity")

    _sdk.providers.register_execution_backend(Backend())
    core_nodes.NODE_CLASS_MAPPINGS[NODE_ID] = cls
    try:
        prompt = {"4": {"class_type": NODE_ID,
                        "inputs": {"ckpt_name": "flux1-dev-bnb-nf4-v2.safetensors"}}}
        ok, errors, _ = await execution.validate_inputs("nf4-guest", prompt, "4", {})
        record("guest/validate-refused", ok is False and [e.get("details") for e in errors]
               == [f"ckpt_name - {EXPECTED_REFUSAL}"], errors)
        record("guest/validate-dispatched", "validate_inputs" in dispatched, dispatched)
        try:
            out = await execution._async_map_node_over_list(
                prompt_id="nf4-guest", unique_id="4", obj=cls,
                input_data_all={"ckpt_name": ["flux1-dev-bnb-nf4-v2.safetensors"]},
                func=cls.FUNCTION, v3_data=None)
            if out and isinstance(out[0], asyncio.Task):
                await out[0]
            record("guest/execute-refused", False, f"no error: {out!r}")
        except Exception as error:  # noqa: BLE001
            text = str(error)
            facts["execute_error"] = {"type": type(error).__name__, "message": text}
            record("guest/execute-refused", EXPECTED_REFUSAL in text
                   and "NF4LoaderUnavailableError" in (type(error).__name__ + text),
                   facts["execute_error"])
        record("guest/execute-dispatched", "execute" in dispatched, dispatched)
        facts["guest_pid"] = session.last_guest_pid
        record("guest/out-of-process", session.last_guest_pid not in (None, os.getpid()),
               [session.last_guest_pid, os.getpid()])
    finally:
        if previous_class is None:
            core_nodes.NODE_CLASS_MAPPINGS.pop(NODE_ID, None)
        else:
            core_nodes.NODE_CLASS_MAPPINGS[NODE_ID] = previous_class
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
    result = {"node": NODE_ID, "verdict": "REFUSED-AS-DESIGNED" if not failed else "MISMATCH",
              "checks": checks, "failed": failed, "facts": facts}
    Path("/results/guest.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": result["verdict"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
