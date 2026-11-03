"""Host proxy -> real guest, end to end, for comfyui-inspire-pack round 1 (gate).

    DEPS=<opencv-python-headless unpacked> run_in_gate.sh <snapshot dir, or the pack folder> \
        <.../v2/tests> <results> test_comfyui-inspire-pack_guest.py

The proxies packdb builds from secure-nodes.json are registered in core. An execution backend
mirroring the overlay's CloudExecutionBackend.dispatch sends every plan to a GuestSession. So the
directory loaders run in a separate process and list and read the synthetic input folder only
through the SDK (assets.list / resolve / read_bytes, served by the host). The results are compared
exactly with the pristine nodes. The Datetime and absolute-path refusals are checked at core's
queue-time validation through the guest.

Writes /results/guest.json; exits 1 on any failed check.
"""

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

import _ins_harness as H  # noqa: E402
import torch  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:300]}"), flush=True)


async def run() -> dict:
    head = H.pack_head()
    H.make_fixtures()
    loaded = packdb.load_pack(H.snapshot_dir(), mount_name="custom_nodes.ins_guest_proxy",
                              pack_id=f"{H.SLUG}/{H.KEY}")
    proxies = loaded.node_mappings
    P = H.load_pristine_image_util(head)
    H.name_ordered_listing(P)
    facts = {"module_root": str(loaded.v2_dir)}
    # Production pack guests run with guest/fixr1_compat.py applied, which publishes a values-mode
    # output by its declared type (a MASK stays a MASK). The gate cannot build a sealed runtime
    # (no render root), so the session starts through _ins_sealed_guest_entry.py, which applies
    # that same patch before the guest main.
    class PatchedEntryGuestSession(GuestSession):
        def _guest_command(self, python):
            return [python, "/tests/_ins_sealed_guest_entry.py"]

    session = await PatchedEntryGuestSession("ins-guest").start()
    facts["sandbox_kind"] = session.sandbox_kind
    facts["guest_entry"] = "tests/_ins_sealed_guest_entry.py (guest main + fixr1_compat.install)"
    dispatched = []

    class Backend:
        # As comfy_secure_nodes/execution.py:430-483, without the per-pack consent filter.
        async def dispatch(self, plan, local_call, runtime):
            dispatched.append([plan.node_type, plan.method])
            caps = set(plan.permissions or ())
            if getattr(plan, "input_mode", "refs") == "values":
                caps.add("raw")
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await session.execute(plan, runtime, capabilities=frozenset(caps), tenant="ins-guest")

    previous_backend = _sdk.providers.execution_backend
    _sdk.providers.register_execution_backend(Backend())
    previous = {node_id: H.core_nodes.NODE_CLASS_MAPPINGS.get(node_id) for node_id in proxies}
    for node_id, proxy in proxies.items():
        H.core_nodes.NODE_CLASS_MAPPINGS[node_id] = proxy
    try:
        inputs = dict(image_load_cap=4, start_index=1, load_always=False, sort_method="Alphabetical (ASC)")
        got = await H.run_v2(proxies["LoadImagesFromDir //Inspire"], node_id="61", directory="mixed", **inputs)
        want = H.run_pristine(P.LoadImagesFromDirBatch, directory=str(H.INPUT / "mixed"), **inputs)
        record("guest/LoadImagesFromDir == pristine (mixed sizes, alpha, EXIF)", *H.same(tuple(want), tuple(got)))
        got = await H.run_v2(proxies["LoadImagesFromDir //Inspire"], node_id="62", directory="input/alpha_sizes")
        want = H.run_pristine(P.LoadImagesFromDirBatch, directory=str(H.INPUT / "alpha_sizes"))
        record("guest/LoadImagesFromDir == pristine (no sort saved: listing order)", *H.same(tuple(want), tuple(got)))
        got = await H.run_v2(proxies["LoadImageListFromDir //Inspire"], node_id="63", directory="rgb_only",
                             sort_method="Numerical (DESC)")
        want = H.run_pristine(P.LoadImagesFromDirList, directory=str(H.INPUT / "rgb_only"),
                              sort_method="Numerical (DESC)")
        ok, detail = H.same(tuple(want)[:2], tuple(got)[:2])
        paths_ok = [os.path.basename(p) for p in want[2]] == [os.path.basename(p) for p in got[2]] \
            and all(p == os.path.join("rgb_only", os.path.basename(p)) for p in got[2])
        record("guest/LoadImageListFromDir == pristine (+ file paths)", ok and paths_ok, detail or (want[2], got[2]))
        got = await H.run_v2(proxies["LoadImagesFromDir //Inspire"], node_id="64", directory="output/frames")
        want = H.run_pristine(P.LoadImagesFromDirBatch, directory=str(H.OUTPUT / "frames"))
        record("guest/LoadImagesFromDir output folder == pristine", *H.same(tuple(want), tuple(got)))
        frames = torch.rand(2, 8, 8, 3, generator=torch.Generator().manual_seed(71))
        got = await H.run_v2(proxies["ChangeImageBatchSize //Inspire"], node_id="65", image=frames,
                             batch_size=5, mode="simple")
        record("guest/ChangeImageBatchSize == pristine",
               *H.same(P.ChangeImageBatchSize.doit(frames, 5, "simple"), tuple(got)))
        try:
            await H.run_v2(proxies["LoadImagesFromDir //Inspire"], node_id="66", directory="nope")
            record("guest/missing folder error", False, "no error")
        except Exception as error:  # noqa: BLE001
            record("guest/missing folder error", "Directory 'nope cannot be found.'" in str(error), repr(error))
        for label, node_inputs, needle in (
                ("Datetime sort", {"directory": "mixed", "sort_method": "Datetime (DESC)"},
                 "sort_method 'Datetime (DESC)' is not available in Secure Nodes V2 yet"),
                ("absolute folder", {"directory": "C:\\frames"}, "'C:\\frames' is an absolute path")):
            prompt = {"5": {"class_type": "LoadImagesFromDir //Inspire", "inputs": node_inputs}}
            ok_flag, errors, _ = await H.execution.validate_inputs("ins-guest", prompt, "5", {})
            # Core reports a custom validation failure once per input the validator takes.
            record(f"guest/{label} refused at core validation via proxy",
                   ok_flag is False and errors
                   and all(e.get("type") == "custom_validation_failed" and needle in (e.get("details") or "")
                           for e in errors), errors)
        # Plans name the node class.
        record("guest/dispatched", ["LoadImagesFromDirBatch", "execute"] in dispatched
               and ["LoadImagesFromDirList", "execute"] in dispatched
               and ["ChangeImageBatchSize", "execute"] in dispatched
               and ["LoadImagesFromDirBatch", "validate_inputs"] in dispatched, dispatched)
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
