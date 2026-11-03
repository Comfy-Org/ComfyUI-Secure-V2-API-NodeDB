"""Finite actual GuestSession parity, selected base 0cd9adec and sealed imports.

Default cases exercise every converted backend class. Deterministic seed values
are used across processes; host-global-RNG branches must refuse by name without
advancing either process's RNG. UI is compared as exact serialized JSON, matching its
ordinary engine/frontend boundary. Output values retain exact Python types.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import random
import signal
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]
import test_d2_parity as parity
from comfy_api.latest import _sdk
from comfy_api.latest._execution_metadata import ExecutionMetadataScope
from comfy_execution.graph import DynamicPrompt
from comfy_secure_nodes.transport.host import GuestSession

BASE = Path("/bases/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages")
RESULTS = Path("/results")
REPORT = {"environment": "gate, B13 sources 38f28c98; core 6257422b; guest base 0cd9adec",
          "cases": [], "guest": {}, "failure_count": 0}
LAST_WIRE_KINDS = []


class SelectedGuest(GuestSession):
    def _guest_command(self, python):
        return [python, "/tests/d2_guest_entry.py"]

    def _extra_ro_paths(self):
        return ["/tests", str(BASE)]

    def _adjust_guest_env(self, env):
        env["COMFY_GUEST_API_ROOT"] = str(BASE / "comfy_api")


def normalized_error(error):
    return ("error", getattr(error, "remote_type", type(error).__name__),
            getattr(error, "remote_message", str(error)))


def values_output(result):
    return ("value", result.result, result.expand, result.block_execution)


def ui_output(result):
    return json.dumps(result.ui, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


async def guest_call(session, cls, node_id, fields, method="execute"):
    global LAST_WIRE_KINDS
    refs = _sdk.InProcessRefResolver()
    permissions = tuple(getattr(cls, "SDK_PERMISSIONS", ()))
    plan = _sdk.ExecutionPlan(
        "d2-actual-guest", "17", cls.__name__, tier="sandbox",
        permissions=permissions, node_module=cls.__module__, method=method,
        prompt=parity.PROMPT, extra_pnginfo={})
    plan.execution_metadata = ExecutionMetadataScope(
        plan.prompt_id, DynamicPrompt(copy.deepcopy(parity.PROMPT)), {})
    plan.inputs = await _sdk.wrap_inputs(refs, fields)
    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
                           ops=_sdk.InProcessOps())
    result = await session.execute(plan, runtime, capabilities=permissions, tenant="d2-recovery-test")
    if method != "execute":
        return result
    LAST_WIRE_KINDS = [getattr(value, "kind", None) for value in (result.result or ())]
    if node_id == "D2 Image Resize":
        assert result.result[0].kind == "IMAGE"
        if fields.get("mask") is None:
            assert result.result[5] is None
        else:
            assert result.result[5].kind == "MASK", LAST_WIRE_KINDS
        if fields.get("vae") is None:
            assert result.result[4] is None
        else:
            assert result.result[4].kind == "LATENT", LAST_WIRE_KINDS
    return await _sdk.unwrap_outputs(refs, result)


async def main():
    RESULTS.mkdir(exist_ok=True)
    new = parity.load_v2()
    old = parity.source_classes(new)
    # The real encoder output is compared here, not authored by the test.
    encoded = parity.encode(new)
    assert encoded == (Path("/pack/v2/secure-nodes.json")).read_bytes()
    rows = []
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        if node_id not in parity.BACKEND_IDS:
            continue
        fields = parity.defaults(cls)
        if node_id == "D2 XY Seed":
            fields["seeds"] = "7\n8"
        if node_id == "D2 XY Seed2":
            fields.update(initial_number=7, count=4, mode="increment")
        rows.append((node_id, "default-or-deterministic-seed", fields))
    rows += [
        ("D2 Image Resize", "mask-wire", parity.defaults(new.NODE_CLASS_MAPPINGS["D2 Image Resize"]) |
         {"mask": parity.tensor((1, 9, 11)), "round_method": "None"}),
        ("D2 Image Resize", "vae-normal-wire", parity.defaults(new.NODE_CLASS_MAPPINGS["D2 Image Resize"]) |
         {"image": parity.tensor((2, 9, 11, 4)), "round_method": "None",
          "vae": parity.VAE(expected_pixel_stride=4), "use_tiled_vae": False}),
        ("D2 Image Resize", "vae-tiled-wire", parity.defaults(new.NODE_CLASS_MAPPINGS["D2 Image Resize"]) |
         {"image": parity.tensor((2, 9, 11, 4)), "round_method": "None",
          "vae": parity.VAE(expected_pixel_stride=4), "use_tiled_vae": True}),
        ("D2 Filename Template", "hidden-prompt", parity.defaults(new.NODE_CLASS_MAPPINGS["D2 Filename Template"]) |
         {"format": "%node:17.seed%/%Source.seed%/%Text.value%", "arg_1": ["a", "b"]}),
        ("D2 Filename Template2", "hidden-prompt", parity.defaults(new.NODE_CLASS_MAPPINGS["D2 Filename Template2"]) |
         {"format": "%node:17.seed%/%Source.seed%", "arg_1": {"key": "value"}}),
        ("D2 Regex Switcher", "native-error", parity.defaults(new.NODE_CLASS_MAPPINGS["D2 Regex Switcher"]) |
         {"text": "x", "regex_and_output": "[--bad"}),
        ("D2 Multi Output", "list-types-wire", {"type": "FLOAT", "parameter": "-0.0\n1.25\n-3.5"}),
        ("D2 XY Seed2", "list-output-flags", {"initial_number": 2**64 - 1, "count": 3,
                                           "mode": "decrement"}),
        ("D2 XY Seed2", "randomize-zero-count", {"initial_number": 7, "count": 0,
                                                "mode": "randomize"}),
        ("D2 Multi Output", "seed-literal-minus-one", {"type": "SEED", "parameter": "-1\n0\n42"}),
        ("D2 XY Seed", "malformed-before-minus-one", {"seeds": "bad\n-1"}),
        ("D2 XY Seed", "malformed-float-text", {"seeds": "-1.0"}),
    ]
    rng_inputs = [
        ("D2 XY Seed", f"seed-text-{i}", {"seeds": text}, parity.RNG_REFUSAL_XY)
        for i, text in enumerate(["-1\n-1", "7\n-1", " -01 \n2", "-\u0661\n8"])
    ]
    rng_inputs += [
        ("D2 XY Seed2", f"initial-minus-one-{count}-{mode}",
         {"initial_number": -1, "count": count, "mode": mode}, parity.RNG_REFUSAL_INITIAL)
        for count in (0, 1) for mode in ("fixed", "increment", "decrement", "randomize")
    ]
    rng_inputs += [
        ("D2 XY Seed2", "positive-randomize", {"initial_number": 7, "count": 1,
                                               "mode": "randomize"}, parity.RNG_REFUSAL_RANDOMIZE),
        ("D2 XY Seed2", "max-randomize", {"initial_number": 2**64-1, "count": 2,
                                          "mode": "randomize"}, parity.RNG_REFUSAL_RANDOMIZE),
    ]
    assert len(rows) == 36 and len(rng_inputs) == 14
    print(f"PLAN: {len(rows)} actual guest differential cases, 46 guest refusal validations, "
          "2 partial/remote validators, 14 RNG inputs x validation+execution refusal", flush=True)
    session = await SelectedGuest("d2-recovery-0cd9", guest_runtime_root=parity.V2).start()
    try:
        for node_id, label, fields in rows:
            try:
                expected_node = parity.source_call(old[node_id], copy.deepcopy(fields))
                expected, expected_ui = values_output(expected_node), ui_output(expected_node)
            except Exception as error:
                expected, expected_ui = normalized_error(error), None
            try:
                actual_node = await guest_call(session, new.NODE_CLASS_MAPPINGS[node_id], node_id,
                                               copy.deepcopy(fields))
                actual, actual_ui = values_output(actual_node), ui_output(actual_node)
            except Exception as error:
                actual, actual_ui = normalized_error(error), None
            record = {"node_id": node_id, "case": label, "verdict": "EXACT"}
            record["wire_output_kinds"] = list(LAST_WIRE_KINDS)
            try:
                parity.equal(expected, actual)
                assert expected_ui == actual_ui, f"UI JSON differs: {expected_ui!r} != {actual_ui!r}"
            except Exception as error:
                record.update(verdict="MISMATCH", detail=str(error),
                              original=repr(expected)[:1600], converted=repr(actual)[:1600])
                REPORT["failure_count"] += 1
            REPORT["cases"].append(record)
            print(f"{record['verdict']} {node_id}/{label}", flush=True)
        REPORT["rng_refusals"] = []
        for node_id, label, fields, message in rng_inputs:
            host_before = random.getstate()
            actual = await guest_call(session, new.NODE_CLASS_MAPPINGS[node_id], node_id,
                                      copy.deepcopy(fields), method="validate_inputs")
            assert actual == message, (node_id, label, actual)
            assert random.getstate() == host_before, "host validation advanced Python RNG"
            try:
                await guest_call(session, new.NODE_CLASS_MAPPINGS[node_id], node_id,
                                 copy.deepcopy(fields))
            except Exception as error:
                assert normalized_error(error) == ("error", "SecureConversionRefusal", message)
            else:
                raise AssertionError(f"{node_id}/{label}: RNG branch did not refuse")
            assert random.getstate() == host_before, "host execute advanced Python RNG"
            REPORT["rng_refusals"].append({"node_id": node_id, "case": label,
                "inputs": fields, "message": message, "validation": "NAMED-REFUSAL",
                "execution": "NAMED-REFUSAL", "host_rng_unchanged": True})
            print(f"NAMED-RNG-REFUSAL {node_id}/{label}: host RNG unchanged", flush=True)
        for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
            if node_id in parity.BACKEND_IDS:
                continue
            expected = f"d2-nodes-comfyui/{node_id} is not yet converted to Secure Nodes V2"
            actual = await guest_call(session, cls, node_id, {}, method="validate_inputs")
            assert actual == expected, (node_id, actual)
        assert await guest_call(session, new.NODE_CLASS_MAPPINGS["D2 Prompt"], "D2 Prompt",
                                {"insert_lora": "logical-model.safetensors"}, "validate_inputs") is True
        assert "upscale_model is not yet converted" in await guest_call(
            session, new.NODE_CLASS_MAPPINGS["D2 Image Resize"], "D2 Image Resize",
            {"upscale_model": "logical-model.safetensors"}, "validate_inputs")
        seal = json.loads((Path(session._guest_tmp) / "d2-import-seal.json").read_text())
        assert seal["pid"] == session.last_guest_pid and seal["pid"] != os.getpid()
        assert seal["api_root"] == str(BASE / "comfy_api")
        assert seal["cached_yaml_was_present"] and all(
            x == "DENIED" for x in seal["negative_probes"].values())
        assert seal["lock_sha256"] == hashlib.sha256(Path("/tests/guest_common.lock").read_bytes()).hexdigest()
        REPORT["guest"] = {"pid": session.last_guest_pid, "host_pid": os.getpid(),
                           "sandbox_kind": session.sandbox_kind, "import_seal": seal}
        REPORT["guest_refusal_checks"] = 46
        REPORT["partial_remote_validator_checks"] = 2
        rng_receipts = [json.loads(line) for line in
                        (Path(session._guest_tmp) / "d2-rng-receipts.jsonl").read_text().splitlines()]
        refused = [record for record in rng_receipts if record["named_rng_refusal"]]
        assert len(refused) == 28
        assert sum(row["method"] == "validate_inputs" for row in refused) == 14
        assert sum(row["method"] == "execute" for row in refused) == 14
        assert all(row["rng_unchanged"] and row["pid"] == session.last_guest_pid
                   and row["rng_before_sha256"] == row["rng_after_sha256"] for row in rng_receipts)
        REPORT["rng_refusal_input_count"] = 14
        REPORT["rng_refusal_method_checks"] = 28
        REPORT["guest_rng_receipts"] = rng_receipts
    finally:
        await session.kill()
    (RESULTS / "guest-parity.json").write_text(json.dumps(REPORT, indent=2, sort_keys=True) + "\n")
    assert REPORT["failure_count"] == 0, f"{REPORT['failure_count']} actual guest mismatches"
    print(f"DONE: {len(rows)} actual guest cases EXACT; 14 RNG inputs x2 refusals with both "
          "RNG states unchanged; import seal retained; 46 whole-node refusals", flush=True)


if __name__ == "__main__":
    def timed_out(signum, frame):
        raise TimeoutError("finite actual-guest budget exceeded: 240 seconds")
    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(240)
    try:
        asyncio.run(main())
    except BaseException as error:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "guest-failure.json").write_text(json.dumps({
            "error_type": type(error).__name__, "message": str(error),
            "traceback": traceback.format_exc(), "partial_report": REPORT,
        }, indent=2, sort_keys=True) + "\n")
        raise
    finally:
        signal.alarm(0)
