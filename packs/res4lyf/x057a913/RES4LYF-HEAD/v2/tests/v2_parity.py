"""Tier-1 parity, V2 side: RES4LYF ClownsharKSampler_Beta V2 in a REAL guest vs the ORIGINAL reference (gate only).

This process never imports the original pack. Core is clean apart from the two scheduler names that the V2
manifest registers.
* The reference comes from ref_original.py, run in a separate process (see below).
* The V2 node runs through core's dispatch shape (ExecutionPlan + wrap_inputs + InProcessCtxProvider) in a
  comfy_secure_nodes GuestSession, with exactly its declared SDK permissions. The guest starts through
  _res4_sealed_guest_entry.py with its guest import audit on (pack code may import only the stdlib, the sealed guest
  lock or the declared profile); the summary lists any import it refused.
* Comparisons are bitwise and dtype-strict: output samples and noise_mask, denoised samples and noise_mask, the
  OPTIONS dict, and on both output latents the chain marker's denoised estimate against the original's
  state_info['denoised'] (what LatentUpscaleWithVAE decodes). Each row also records the sha256 of V2's samples, so
  two pack versions' runs of the same cases can be compared directly.
* Every ctx.sample call is recorded: the model evaluations it made and the wall time it took.
* A negative control flips one value and must turn the comparator red.
Writes /results/v2-parity.json and exits 1 on any MISMATCH or harness failure.
The reference is a mounted ref_original.py result (DEPS = that result folder), or, when /deps holds none, it is
computed first by ref_original.py in a child process of the same container (see reference_dir).
Run: run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> v2_parity.py
     (optional: DEPS=<a ref_original.py result> to reuse a reference, or DEPS=<the original's test deps>)
"""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, "/tests")
CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import torch  # noqa: E402
from safetensors.torch import load_file  # noqa: E402

import folder_paths  # noqa: E402,F401
import comfy.model_base as mb  # noqa: E402
import comfy.model_management  # noqa: E402
import comfy.model_patcher as mp  # noqa: E402
import comfy.sample  # noqa: E402
import comfy.samplers  # noqa: E402
import comfy.supported_models as sm  # noqa: E402
from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes import packdb, packmanifest, packruntime, schedulerproviders  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

import cases  # noqa: E402

PACK = Path("/pack")
V2 = PACK / "v2"
REF = Path("/deps")  # replaced in main() by reference_dir()
OUT = Path("/results")


def reference_dir():
    """The original's reference: a mounted one (DEPS = an earlier ref_original.py result), else computed now by
    ref_original.py in a child process of this container. The original never loads into this process, because it
    patches core globally."""
    if (Path("/deps") / "ref.json").is_file():
        return Path("/deps"), "mounted at /deps"
    import subprocess
    out = Path(tempfile.mkdtemp(prefix="res4-ref-run-"))
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve().parent / "ref_original.py")],
                   env=dict(os.environ, RES4_REF_OUT=str(out)), check=True, timeout=3600)
    return out, f"computed by ref_original.py in a child process ({time.perf_counter() - t0:.1f} s)"
NODE = "ClownsharKSampler_Beta"
PREFIX = "RES4LYF/ClownsharKSampler_Beta:"


def import_package(name, root):
    for key in list(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key)
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SECURE = import_package("res4lyf_secure", V2)
SCHED = importlib.import_module("res4lyf_secure.schedulers")
try:
    CHAIN_KEY = importlib.import_module("res4lyf_secure.latent_chain").CHAIN_KEY
except ImportError:  # an earlier pack version under this harness (the cross-version sample check)
    CHAIN_KEY = "res4lyf_v2_chain"


def register_providers():
    """The manifest exactly as encode_manifest.py builds it (it must equal the committed v2/secure-nodes.json),
    loaded by the real loader, with the pack's scheduler providers registered."""
    import encode_manifest
    data = encode_manifest.dump(encode_manifest.build(SECURE, SCHED))
    committed = V2 / "secure-nodes.json"
    matches = committed.is_file() and committed.read_bytes() == data
    loaded = encode_manifest.load_snapshot(data, "custom_nodes.res4lyf_parity")
    return loaded, hashlib.sha256(data).hexdigest(), matches


COUNT = {"n": 0}
PASSES = []


def counting(args_):
    COUNT["n"] += 1
    if COUNT.get("interrupt_at") == COUNT["n"]:  # cancellation case: an interrupt surfaces at this evaluation
        raise comfy.model_management.InterruptProcessingException()
    return comfy.samplers.calc_cond_batch(args_["model"], args_["conds"], args_["input"], args_["sigma"],
                                          args_["model_options"])


async def cancellation_row(by_name, ref_cancel):
    """Interrupt mid-sampling (raised host side at a model evaluation, where a cancel surfaces during sampling).
    Then the same case again, on a fresh guest if the platform retired the old one (as its guest manager does):
    it must be EXACT, the retired guest process must be gone and no host threads may be left behind."""
    import threading
    case = next(c for c in cases.case_table() if c["name"] == cases.CANCEL["case"])
    model = model_for(case["model"])
    threads_before = sorted(t.name for t in threading.enumerate())
    pos, neg, latent = cases.inputs(mask=case["mask"], batch=case["batch"], zero_latent=case["zero_latent"])
    COUNT["n"] = 0
    COUNT["interrupt_at"] = cases.CANCEL["interrupt_at"]
    pid_before = GUEST["session"].last_guest_pid if GUEST["session"] else None
    print("CANCEL step 1: interrupted run", flush=True)
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(run_v2(widgets_inputs(case["widgets"], model, pos, neg, latent)), timeout=90)
        raised = None
    except asyncio.TimeoutError:
        raised = "TIMEOUT: no result or error within 90 s after the interrupt"
    except BaseException as error:  # noqa: BLE001
        raised = f"{type(error).__name__}: {error}"[:400]
    finally:
        COUNT["interrupt_at"] = None
    seconds_to_surface = round(time.perf_counter() - t0, 2)
    evaluations = COUNT["n"]
    print(f"CANCEL step 2: surfaced after {seconds_to_surface}s: {raised}", flush=True)
    session = GUEST["session"]
    pid_interrupted = session.last_guest_pid if session else None
    stderr_tail = (getattr(session, "last_stderr", "") or "")[-1500:] if session else ""
    # The platform retires a guest that died or hung; start a fresh one as its guest manager would.
    retired = raised is not None and ("GuestDied" in raised or raised.startswith("TIMEOUT"))
    if retired:
        try:
            await asyncio.wait_for(session.kill(), timeout=30)
        except BaseException as error:  # noqa: BLE001
            print("CANCEL kill failed:", type(error).__name__, error, flush=True)
        GUEST["session"] = None
    print("CANCEL step 3: retired" if retired else "CANCEL step 3: guest kept", flush=True)
    await asyncio.sleep(0.5)
    gone = [pid for pid in {pid_before, pid_interrupted} if pid] if retired else []
    alive_retired = [pid for pid in gone if Path(f"/proc/{pid}").exists()]
    pos, neg, latent = cases.inputs(mask=case["mask"], batch=case["batch"], zero_latent=case["zero_latent"])
    print("CANCEL step 4: rerun", flush=True)
    try:
        values = await asyncio.wait_for(run_v2(widgets_inputs(case["widgets"], model, pos, neg, latent)), timeout=90)
        ok, checks, _diff = compare(by_name[case["name"]], values)
    except BaseException as error:  # noqa: BLE001
        ok, checks = False, {"rerun_error": f"{type(error).__name__}: {error}"[:300]}
    await asyncio.sleep(0.5)
    threads_after = sorted(t.name for t in threading.enumerate())
    row = {"case": case["name"], "original": ref_cancel, "v2_raised": raised, "v2_evaluations": evaluations,
           "seconds_to_surface": seconds_to_surface, "guest_stderr_tail": stderr_tail,
           "guest_retired": retired, "retired_pids_still_alive": alive_retired, "rerun_exact": ok,
           "rerun_checks": checks, "guest_pid_before": pid_before,
           "guest_pid_rerun": GUEST["session"].last_guest_pid if GUEST["session"] else None,
           "threads_before": threads_before, "threads_after": threads_after,
           "surface_differs_from_original": raised is not None and ref_cancel.get("raised") not in raised}
    row["verdict"] = ("CLEAN" if raised is not None and ok and evaluations == ref_cancel.get("evaluations")
                      and not alive_retired and set(threads_after) <= set(threads_before) else "MISMATCH")
    print("CANCEL", row["verdict"], raised, evaluations, ok, alive_retired, flush=True)
    return row


_ORIG_SAMPLE_CUSTOM = comfy.sample.sample_custom


def recording_sample_custom(*a, **k):
    before = COUNT["n"]
    t0 = time.perf_counter()
    try:
        return _ORIG_SAMPLE_CUSTOM(*a, **k)
    finally:
        PASSES.append({"evaluations": COUNT["n"] - before, "sigmas": int(a[4].numel()),
                       "seconds": round(time.perf_counter() - t0, 4)})


comfy.sample.sample_custom = recording_sample_custom
MODELS = {}


def model_for(kind):
    if kind not in MODELS:
        m = cases.tiny_model(mb, mp, sm, kind)
        m.set_model_sampler_calc_cond_batch_function(counting)
        MODELS[kind] = m
    return MODELS[kind]


GUEST = {"session": None, "pids": set()}


GUARD_LOG = Path(tempfile.mkdtemp(prefix="res4-parity-guard-")) / "import-guard.jsonl"


def guard_summary():
    events = [json.loads(line) for line in GUARD_LOG.read_text().splitlines()] if GUARD_LOG.exists() else []
    return {"on": True, "refused_imports": sorted({e["module"] for e in events}), "refused_import_events": len(events)}


class SealedEntryGuestSession(GuestSession):
    """Start the guest the way production pack guests start: fixr1_compat applied before the guest main. The entry's
    guest import audit is on: pack code may import only the stdlib, the sealed guest lock or the declared profile."""

    def _guest_command(self, python):
        return [python, "/tests/_res4_sealed_guest_entry.py"]

    def _adjust_guest_env(self, env):
        super()._adjust_guest_env(env)
        env["RES4_GUARD_ROOT"] = str(self.guest_runtime_root)
        env["RES4_GUARD_LOG"] = str(GUARD_LOG)


async def session():
    if GUEST["session"] is None:
        GUEST["session"] = await SealedEntryGuestSession("res4-parity", guest_runtime_root=V2).start()
    return GUEST["session"]


PROVIDER_CALLS = []


async def gate_invoke_provider(pack, provider, projection, steps):
    """Gate adaptation (labelled): production starts a scheduler-provider guest from pack.runtime, which needs a
    render root the gate does not have (schedulerproviders.py:232-250). Here the provider guest starts through the
    same sealed test entry as the node guest; the provider call itself is the production call."""
    guest = SealedEntryGuestSession(f"scheduler:{pack.name}:{provider.name}", guest_runtime_root=V2)
    await guest.start()
    try:
        result = await guest.invoke_scheduler_provider(
            module_name=provider.module_name, module_file=str(provider.module_file), function_name=provider.function,
            projection=projection, steps=steps, config=copy.deepcopy(provider.config))
        PROVIDER_CALLS.append({"name": provider.name, "steps": steps, "pid": result.get("pid")
                               if isinstance(result, dict) else None})
        return result
    finally:
        await guest.kill()


schedulerproviders._invoke_async = gate_invoke_provider


async def run_v2(inputs, method="execute", prompt_id="res4-parity", node_id=NODE):
    cls = SECURE.NODE_CLASS_MAPPINGS[node_id]
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope(prompt_id, DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id=prompt_id, node_id="9", node_type=cls.__name__, tier="sandbox", node_module=cls.__module__,
            inputs=dict(inputs), input_mode="refs", method=method, permissions=permissions, prompt={},
            extra_pnginfo=None, dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        guest = await session()
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="res4-parity")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        if method != "execute":
            return result

        async def resolve(value):  # nested refs too, as the host's unwrap_outputs does
            if isinstance(value, _sdk.Ref):
                return await refs.resolve(value)
            if isinstance(value, dict):
                return {key: await resolve(item) for key, item in value.items()}
            if isinstance(value, list):
                return [await resolve(item) for item in value]
            if isinstance(value, tuple):
                return tuple([await resolve(item) for item in value])
            return value

        return [await resolve(item) for item in (result.result or ())]
    finally:
        scope.__exit__(None, None, None)


def jsonable(value):
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, float):
        return {"float": value.hex()}
    if isinstance(value, torch.Tensor):  # exact: dtype, shape and the bytes
        data = value.detach().cpu().contiguous()
        return {"tensor": str(data.dtype), "shape": list(data.shape),
                "sha256": hashlib.sha256(data.view(torch.uint8).numpy().tobytes()).hexdigest()}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return {"type": type(value).__name__}


async def option_rows(by_name):
    """Sampler cases fed by OPTIONS chains: the V2 options nodes and the V2 sampler, all in the real guest."""
    rows = []
    for case in cases.option_cases():
        ref_row = by_name[case["name"]]
        if ref_row.get("needs_deps"):  # the original reached an import stub (no DEPS): no reference to compare
            rows.append({"name": case["name"], "verdict": "NOT_RUNNABLE_WITHOUT_DEPS", "original_error": ref_row["error"]})
            print("OPTION NOT_RUNNABLE_WITHOUT_DEPS", case["name"], flush=True)
            continue
        model = model_for(case["model"])
        pos, neg, latent = cases.inputs()
        PASSES.clear()
        COUNT["n"] = 0
        t0 = time.perf_counter()
        row = {"name": case["name"], "expect": case["expect"], "original_ok": ref_row["ok"],
               "original_calls": ref_row.get("calls"), "original_seconds": ref_row.get("seconds")}
        try:
            opts = None
            for node_id, widgets in case["chain"]:
                inputs = dict(widgets)
                if opts is not None:
                    inputs["options"] = opts
                opts = (await run_v2(inputs, node_id=node_id))[0]
            row["option_chain_equal"] = jsonable(opts) == ref_row.get("option_chain_output")
            inputs = widgets_inputs(case["widgets"], model, pos, neg, latent)
            inputs["options_group"] = {"options0": opts}
            values = await run_v2(inputs)
            row["v2_seconds"] = round(time.perf_counter() - t0, 4)
            row["v2_calls"] = COUNT["n"]
            row["passes"] = list(PASSES)
            row["v2_sha256"] = sample_hashes(values)
            if not ref_row["ok"]:
                row["verdict"] = "MISMATCH"
                row["note"] = f"original failed: {ref_row.get('error')}; V2 ran"
            else:
                ok, checks, diff = compare(ref_row, values)
                ok = ok and row["option_chain_equal"]
                row.update(checks=checks, max_abs_diff=diff)
                row["verdict"] = "EXACT" if ok and case["expect"] == "exact" else "MISMATCH"
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            row["v2_error"] = message[:600]
            row["passes"] = list(PASSES)
            if not ref_row["ok"] and PREFIX in message:
                row["verdict"] = "BOTH_FAIL"
                row["original_error"] = ref_row.get("error")
            else:
                row["verdict"] = refusal_verdict(message, case["expect"])
            if row["verdict"] == "MISMATCH":
                row["trace"] = traceback.format_exc()[-2000:]
        rows.append(row)
        print("OPTION", row["verdict"], case["name"], row.get("v2_error", row.get("note", ""))[:180], flush=True)
    return rows


def tensors_equal(a, b):
    return a.dtype == b.dtype and tuple(a.shape) == tuple(b.shape) and torch.equal(a, b)


def compare(ref_row, values):
    ref_t = load_file(str(REF / "ref" / f"{ref_row['index']}.safetensors"))
    out, den, options = values
    checks = {}
    checks["out_samples"] = tensors_equal(ref_t["out_samples"], out["samples"])
    checks["den_samples"] = tensors_equal(ref_t["den_samples"], den["samples"])
    if "out_noise_mask" in ref_t:
        checks["out_noise_mask"] = "noise_mask" in out and tensors_equal(ref_t["out_noise_mask"], out["noise_mask"])
    else:
        checks["out_no_noise_mask"] = "noise_mask" not in out
    if "den_noise_mask" in ref_t:
        checks["den_noise_mask"] = "noise_mask" in den and tensors_equal(ref_t["den_noise_mask"], den["noise_mask"])
    checks["options"] = jsonable(options) == ref_row["options"]
    # The chain marker in place of state_info: its denoised estimate must be the original's state_info['denoised']
    # bit for bit (dtype, shape, values), on both output latents; absent exactly when the original has none.
    for side, latent in (("out", out), ("den", den)):
        chain = latent.get(CHAIN_KEY)
        checks[f"{side}_chain_node"] = isinstance(chain, dict) and chain.get("node") == NODE
        if f"{side}_state_denoised" in ref_t:
            carried = chain.get("denoised") if isinstance(chain, dict) else None
            checks[f"{side}_chain_denoised"] = (isinstance(carried, torch.Tensor)
                                                and tensors_equal(ref_t[f"{side}_state_denoised"], carried))
        else:
            checks[f"{side}_chain_without_denoised"] = isinstance(chain, dict) and "denoised" not in chain
    diff = None
    if tuple(ref_t["out_samples"].shape) == tuple(out["samples"].shape):
        diff = float((ref_t["out_samples"].double() - out["samples"].double()).abs().max())
    return all(checks.values()), checks, diff


def sample_hashes(values):
    """sha256 of V2's output samples and masks (dtype, shape and bytes), for comparing two pack versions' runs."""
    out, den = values[0], values[1]
    hashes = {}
    for side, latent in (("out", out), ("den", den)):
        for key in ("samples", "noise_mask"):
            if isinstance(latent.get(key), torch.Tensor):
                hashes[f"{side}_{key}"] = jsonable(latent[key])
    return hashes


def widgets_inputs(case_widgets, model, pos, neg, latent):
    inputs = dict(case_widgets)
    inputs.update(model=model, positive=pos, negative=neg, latent_image=latent)
    return inputs


def refusal_verdict(message, expect):
    """A failure is a designed refusal only when it is the node's own named refusal (OutOfEnvelope, prefixed with
    the node's name)."""
    named = PREFIX in message and ("OutOfEnvelope" in message or "outside the V2 reduced envelope" in message
                                   or "cannot confirm" in message)
    if named or (PREFIX in message and expect == "refused_v2"):
        return "REFUSED_AS_DESIGNED" if expect == "refused_v2" else "REFUSED_NAMED"
    return "MISMATCH"


CORE_WORDING = ("value not in list", "smaller than min", "bigger than max")


def provider_rows(ref_schedules):
    """Core's calculate_sigmas through V2's registered scheduler providers (real provider guests, gate-started)
    vs the original's global registration: bitwise values and dtype, or the same failure."""
    rows = []
    for kind, name, steps in cases.PROVIDER_CASES:
        key = f"{kind}:{name}:{steps}"
        ref = ref_schedules[key]
        model_sampling = model_for(kind).get_model_object("model_sampling")
        try:
            sigmas = comfy.samplers.calculate_sigmas(model_sampling, name, steps)
            mine = {"ok": True, "dtype": str(sigmas.dtype), "values": [float(v).hex() for v in sigmas.tolist()]}
        except Exception as error:  # noqa: BLE001
            mine = {"ok": False, "error": type(error).__name__, "message": str(error)[:200]}
        if ref["ok"] and mine["ok"]:
            verdict = "EXACT" if mine == ref else "MISMATCH"
        elif not ref["ok"] and not mine["ok"]:
            verdict = "BOTH_FAIL"
        else:
            verdict = "MISMATCH"
        rows.append({"case": key, "verdict": verdict, "original": ref, "v2": mine})
        print("PROVIDER", verdict, key, mine.get("error", ""), ref.get("error", ""), flush=True)
    return rows


async def queue_rows(ref_queue):
    """V2 validate_inputs (real guest) against core's validate_inputs on the original, per queue case."""
    original = {row["name"]: row for row in ref_queue}
    rows = []
    for case in cases.queue_cases():
        ref = original[case["name"]]
        verdict = await run_v2({k: case["widgets"][k] for k in cases.QUEUE_WIDGETS}, method="validate_inputs")
        v2_ok = verdict is True
        message = "" if v2_ok else str(verdict)
        refused_inputs = sorted({name for _type, name in ref["errors"]})
        if ref["ok"] and v2_ok:
            outcome = "ACCEPT_BOTH"
        elif not ref["ok"] and not v2_ok:
            # same refusal: every input core refuses for the original is refused by V2 with core's wording
            same = all(f"{name}: " in message for name in refused_inputs) and any(w in message for w in CORE_WORDING)
            outcome = "REFUSE_BOTH" if same else "MISMATCH"
        elif ref["ok"] and not v2_ok:
            core_like = any(w in message for w in CORE_WORDING)
            outcome = "REFUSED_NAMED" if message.startswith(PREFIX) and not core_like else "MISMATCH"
        else:
            outcome = "MISMATCH"  # V2 accepts what core refuses for the original
        rows.append({"name": case["name"], "original": ref, "v2": True if v2_ok else message[:400],
                     "verdict": outcome})
        print("QUEUE", outcome, case["name"], message[:160], flush=True)
    return rows


async def main():
    global REF
    REF, ref_source = reference_dir()
    ref = json.loads((REF / "ref.json").read_text())
    by_name = {row["name"]: row for row in ref["cases"]}
    needs_deps = sorted(name for name, row in by_name.items() if row.get("needs_deps"))
    loaded, manifest_sha, manifest_matches = register_providers()
    rows = []
    for case in cases.case_table():
        ref_row = by_name[case["name"]]
        if ref_row.get("needs_deps"):
            rows.append({"name": case["name"], "verdict": "NOT_RUNNABLE_WITHOUT_DEPS", "original_error": ref_row["error"]})
            continue
        model = model_for(case["model"])
        pos, neg, latent = cases.inputs(mask=case["mask"], batch=case["batch"], zero_latent=case["zero_latent"])
        PASSES.clear()
        COUNT["n"] = 0
        t0 = time.perf_counter()
        row = {"name": case["name"], "expect": case["expect"], "original_ok": ref_row["ok"],
               "original_calls": ref_row.get("calls"), "original_seconds": ref_row.get("seconds")}
        try:
            names = ("sampler_name", "scheduler", "steps", "cfg", "seed", "sampler_mode", "denoise")
            verdict = await run_v2({k: case["widgets"][k] for k in names}, method="validate_inputs")
            row["validate"] = verdict if verdict is True else str(verdict)[:400]
            if verdict is not True:
                raise RuntimeError(str(verdict))
            values = await run_v2(widgets_inputs(case["widgets"], model, pos, neg, latent))
            row["v2_seconds"] = round(time.perf_counter() - t0, 4)
            row["v2_calls"] = COUNT["n"]
            row["passes"] = list(PASSES)
            row["v2_sha256"] = sample_hashes(values)
            ok, checks, diff = compare(ref_row, values)
            row.update(checks=checks, max_abs_diff=diff)
            row["verdict"] = "EXACT" if ok and case["expect"] == "exact" else "MISMATCH"
            row["output_keys"] = sorted(values[0])
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            row["v2_error"] = message[:600]
            row["passes"] = list(PASSES)
            row["verdict"] = refusal_verdict(message, case["expect"])
            if row["verdict"] == "MISMATCH":
                row["trace"] = traceback.format_exc()[-2000:]
                guest = GUEST["session"]
                row["guest_stderr"] = (getattr(guest, "last_stderr", "") or "")[-3000:]
        rows.append(row)
        print(row["verdict"], case["name"], row.get("max_abs_diff"), row.get("v2_error", "")[:160], flush=True)
    for chain in cases.CHAIN:
        ref_row = by_name[chain["name"]]
        if ref_row.get("needs_deps"):
            rows.append({"name": chain["name"], "verdict": "NOT_RUNNABLE_WITHOUT_DEPS", "original_error": ref_row["error"]})
            continue
        model = model_for(chain["model"])
        pos, neg, latent = cases.inputs()
        PASSES.clear()
        COUNT["n"] = 0
        t0 = time.perf_counter()
        row = {"name": chain["name"], "expect": "exact", "original_calls": ref_row.get("calls"),
               "original_seconds": ref_row.get("seconds"), "original_upstream_keys": ref_row.get("upstream_keys")}
        try:
            up = await run_v2(widgets_inputs(chain["up"], model, pos, neg, latent))
            down = await run_v2(widgets_inputs(chain["down"], model, pos, neg, up[0]))
            row["v2_seconds"] = round(time.perf_counter() - t0, 4)
            row["v2_calls"] = COUNT["n"]
            row["passes"] = list(PASSES)
            row["v2_sha256"] = sample_hashes(down)
            ok, checks, diff = compare(ref_row, down)
            row.update(checks=checks, max_abs_diff=diff, v2_upstream_keys=sorted(up[0]))
            row["verdict"] = "EXACT" if ok else "MISMATCH"
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            row["v2_error"] = message[:600]
            row["passes"] = list(PASSES)
            row["verdict"] = refusal_verdict(message, "exact")
            if row["verdict"] == "MISMATCH":
                row["trace"] = traceback.format_exc()[-2000:]
        rows.append(row)
        print(row["verdict"], chain["name"], row.get("max_abs_diff"), row.get("v2_error", "")[:160], flush=True)
    options = await option_rows(by_name)
    queue = await queue_rows(ref.get("queue", []))
    cancel = await cancellation_row(by_name, ref.get("cancellation", {}))
    clown_provider_calls = len(PROVIDER_CALLS)  # the node computes beta57/bong_tangent in its own guest
    providers = provider_rows(ref.get("provider_schedules", {}))

    # negative control: the comparator must go red on a one-element change
    neg_ok = None
    exact_rows = [r for r in rows if r["verdict"] == "EXACT" and "chain" not in r["name"]]
    if exact_rows:
        name = exact_rows[0]["name"]
        case = next(c for c in cases.case_table() if c["name"] == name)
        model = model_for(case["model"])
        pos, neg, latent = cases.inputs(mask=case["mask"], batch=case["batch"], zero_latent=case["zero_latent"])
        values = await run_v2(widgets_inputs(case["widgets"], model, pos, neg, latent))
        tampered = copy.deepcopy(values)
        flat = tampered[0]["samples"].view(-1)
        flat[0] = torch.nextafter(flat[0], torch.tensor(float("inf")))
        ok, _checks, _diff = compare(by_name[name], tampered)
        neg_ok = not ok
    # Pass accounting: per sampler invocation, every ctx.sample pass except the main one must evaluate nothing.
    extra_evals, extra_passes = 0, 0
    for r in rows:
        passes = r.get("passes", [])
        if not passes:
            continue
        evals = [p["evaluations"] for p in passes]
        mains = 2 if r["name"].startswith("chain:") else 1
        top = sorted(evals, reverse=True)[:mains]
        extra_evals += sum(evals) - sum(top)
        extra_passes += len(passes) - mains
    summary = {
        "cases": len(rows),
        "verdicts": {v: sum(1 for r in rows if r["verdict"] == v)
                     for v in ("EXACT", "REFUSED_AS_DESIGNED", "REFUSED_NAMED", "NOT_RUNNABLE_WITHOUT_DEPS",
                               "MISMATCH")},
        "refused_named": [r["name"] for r in rows if r["verdict"] == "REFUSED_NAMED"],
        "provider_calls": len(PROVIDER_CALLS),
        "negative_control_red": neg_ok,
        "extra_passes": extra_passes,
        "extra_pass_model_evaluations": extra_evals,
        "manifest_sha256": manifest_sha,
        "manifest_equals_committed": manifest_matches,
        "guest_pids": sorted(GUEST["pids"]),
        "torch": torch.__version__,
        "queue_verdicts": {v: sum(1 for r in queue if r["verdict"] == v)
                           for v in ("ACCEPT_BOTH", "REFUSE_BOTH", "REFUSED_NAMED", "MISMATCH")},
        "queue_refused_named": [r["name"] for r in queue if r["verdict"] == "REFUSED_NAMED"],
        "provider_verdicts": {v: sum(1 for r in providers if r["verdict"] == v)
                              for v in ("EXACT", "BOTH_FAIL", "MISMATCH")},
        "cancellation": {k: cancel[k] for k in ("verdict", "v2_raised", "v2_evaluations", "rerun_exact")},
        "option_verdicts": {v: sum(1 for r in options if r["verdict"] == v)
                            for v in ("EXACT", "REFUSED_AS_DESIGNED", "REFUSED_NAMED", "BOTH_FAIL", "NOT_RUNNABLE_WITHOUT_DEPS",
                                      "MISMATCH")},
        "option_refused": {r["name"]: r.get("v2_error", "")[:160] for r in options
                           if r["verdict"] in ("REFUSED_NAMED", "REFUSED_AS_DESIGNED", "BOTH_FAIL")},
        "provider_calls_by_the_node": clown_provider_calls,
        "provider_calls_by_core_calculate_sigmas": len(PROVIDER_CALLS) - clown_provider_calls,
        "reference_source": ref_source,
        "stubbed_imports_reference": ref.get("stubbed_imports", []),
        "not_runnable_without_deps": sorted(r["name"] for r in rows + options
                                            if r["verdict"] == "NOT_RUNNABLE_WITHOUT_DEPS"),
        "reference_cases_needing_deps": needs_deps,
        "guest_import_audit": guard_summary(),
    }
    doc = {"summary": summary, "cases": rows, "options": options, "queue": queue, "providers": providers,
           "cancellation": cancel}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v2-parity.json").write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps(summary, indent=1, default=str))
    if GUEST["session"] is not None:
        await GUEST["session"].kill()
    bad = (summary["verdicts"]["MISMATCH"] or summary["queue_verdicts"]["MISMATCH"]
           or summary["provider_verdicts"]["MISMATCH"] or summary["option_verdicts"]["MISMATCH"]
           or cancel["verdict"] != "CLEAN" or not neg_ok)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
