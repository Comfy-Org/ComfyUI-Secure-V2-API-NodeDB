"""Finite real out-of-process follow-up; never disables sandbox policy."""
import asyncio
import builtins
import contextvars
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import traceback
import types

sys.path.insert(0, "/tests")
import run_round1 as base
from comfy_api.latest import io, _sdk as sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire

RECEIPT = {"status": "RUNNING", "evidence": "gate, B13 sources 38f28c98",
    "scheduled_differential_cases": len(base.CASES), "timeout_seconds": 240,
    "execution": "real GuestSession subprocess; selected development gate runtime",
    "namespace_init_guard": False, "nodes": {}, "failures": []}
active_plan = contextvars.ContextVar("pixaroma_test_plan")
real_in_runtime = base.in_runtime


class GuardedSession(GuestSession):
    def _guest_command(self, python):
        return [python, "/tests/_pixaroma_guest_entry.py"]

    def _adjust_guest_env(self, env):
        super()._adjust_guest_env(env)
        env["PIXAROMA_GUARD_ROOT"] = str(self.guest_runtime_root)
        env["PIXAROMA_GUARD_LOG"] = "/results/guest-import-denials.jsonl"
        env["PIXAROMA_GUARD_REPORT"] = "/results/guest-import-guard.json"


async def in_runtime(plan, operation):
    token = active_plan.set(plan)
    try:
        return await real_in_runtime(plan, operation)
    finally:
        active_plan.reset(token)


def save():
    (Path("/results") / "guest-receipt.json").write_text(json.dumps(RECEIPT, indent=2, sort_keys=True) + "\n")


async def main():
    base.namespace("pixaroma_recovery_original", base.PACK)
    base.namespace("pixaroma_recovery_original.nodes", base.PACK / "nodes")
    with tempfile.TemporaryDirectory(prefix="pixaroma-namespace-") as folder:
        root = Path(folder) / "v2"
        shutil.copytree(base.V2, root)
        (root / "__init__.py").write_text("raise AssertionError('guest executed pack __init__.py')\n")
        classes = {}
        for node_id in base.R1:
            module = packdb.load("custom_nodes.pixaroma_namespace_guest", root, base.ROWS[node_id]["module"])
            cls = getattr(module, node_id)
            cls.GET_SCHEMA()
            classes[node_id] = cls
        new = types.SimpleNamespace(NODE_CLASS_MAPPINGS=classes)
        session = await asyncio.wait_for(GuardedSession("pixaroma-r1-finite", guest_runtime_root=root).start(), 45)
        try:
            RECEIPT["sandbox_kind"] = session.sandbox_kind
            RECEIPT["host_pid"] = os.getpid()
            RECEIPT["python_executable"] = str(session.python_executable)
            async def call_guest(cls, method, fields):
                runtime = sdk.current_runtime()
                plan = replace(active_plan.get(), node_module=cls.__module__, node_type=cls.__name__,
                    inputs=await sdk.wrap_inputs(runtime.refs, fields), method=method,
                    permissions=tuple(cls.SDK_PERMISSIONS))
                try:
                    out = await session.execute(plan, runtime, capabilities=tuple(cls.SDK_PERMISSIONS), tenant="pixaroma-gate")
                except wire.WireError as error:
                    # Compare source error type/message with the wire's typed
                    # remote exception, rather than the transport envelope.
                    error_name = getattr(error, "remote_type", "")
                    error_text = getattr(error, "remote_message", "")
                    if error_name in {"ValueError", "TypeError", "RuntimeError", "AttributeError", "OverflowError", "KeyError", "IndexError", "RecursionError"}:
                        raise getattr(builtins, error_name)(error_text) from error
                    raise
                assert session.last_guest_pid != os.getpid()
                RECEIPT["guest_pid"] = session.last_guest_pid
                return out
            for cls in classes.values():
                async def execute(cls, **fields):
                    return await call_guest(cls, "execute", fields)
                cls.execute = classmethod(execute)
                if "fingerprint_inputs" in cls.__dict__:
                    async def fingerprint(cls, **fields):
                        return await call_guest(cls, "fingerprint_inputs", fields)
                    cls.fingerprint_inputs = classmethod(fingerprint)
                if "check_lazy_status" in cls.__dict__:
                    async def lazy(cls, **fields):
                        return await call_guest(cls, "check_lazy_status", fields)
                    cls.check_lazy_status = classmethod(lazy)
            base.in_runtime = in_runtime
            for index, case in enumerate(base.CASES):
                row = RECEIPT["nodes"].setdefault(case["node"], {"EXACT": 0, "REFUSED-AS-DESIGNED": 0, "MISMATCH": 0})
                try:
                    verdict = await base.compare_case(case, new, None)
                    row[verdict] += 1
                except Exception as error:
                    row["MISMATCH"] += 1
                    RECEIPT["failures"].append({"index": index, "node": case["node"], "label": case["label"],
                        "type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc(),
                        "guest_stdout": session.last_stdout, "guest_stderr": session.last_stderr})
                    if len(RECEIPT["failures"]) >= 10:
                        break
            RECEIPT["lifecycle_cases"] = await base.lifecycle(new)
            RECEIPT["namespace_init_guard"] = True
            RECEIPT["status"] = "PASS" if not RECEIPT["failures"] else "FAIL"
        finally:
            await session.kill()
            base.in_runtime = real_in_runtime


try:
    asyncio.run(main())
except BaseException as error:
    RECEIPT["status"] = "FAIL"
    RECEIPT["failures"].append({"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
finally:
    signal.alarm(0)
    save()
    print(json.dumps(RECEIPT, indent=2), flush=True)
if RECEIPT["status"] != "PASS":
    raise SystemExit(1)
