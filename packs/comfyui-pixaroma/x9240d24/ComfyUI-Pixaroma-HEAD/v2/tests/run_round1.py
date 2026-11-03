"""Finite source differential and schema driver, executable only inside the gate."""
from __future__ import annotations

import ast
import asyncio
import copy
import faulthandler
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import sys
import traceback
import types

sys.dont_write_bytecode = True
sys.path[:0] = ["/core", "/overlay"]
from comfy.cli_args import args
args.cpu = True
import torch
from comfy_api.latest import io, _sdk as sdk
from comfy_secure_nodes import packmanifest
from comfy_secure_nodes.packruntime import manifest_declaration

PACK = Path("/pack")
V2 = PACK / "v2"
RESULTS = Path("/results")
ROWS = json.loads((V2 / "_frozen_schemas.json").read_text())
CASES = json.loads(Path("/tests/cases.json").read_text())
R1 = list(dict.fromkeys(case["node"] for case in CASES))
RECEIPT = {
    "status": "RUNNING", "evidence": "gate, B13 sources 38f28c98",
    "core": "6257422b", "overlay": "6f58bcec/e4d93d0d",
    "guest_bases": ["0cd9adec", "0b86765f"],
    "commit": "9240d24b60ab234b355cedea11045965b6683843",
    "scheduled_cases": len(CASES), "timeout_seconds": 240,
    "stages": {}, "nodes": {}, "failures": [],
}


def save():
    (RESULTS / "round1-receipt.json").write_text(json.dumps(RECEIPT, indent=2, sort_keys=True) + "\n")


def deadline(signum, frame):
    raise TimeoutError("finite Round 1 driver exceeded 240 seconds")


signal.signal(signal.SIGALRM, deadline)
signal.alarm(240)
faulthandler.enable()


class GuestImports(importlib.abc.MetaPathFinder):
    """Check imports throughout execution, including already imported modules."""
    allowed = set(sys.stdlib_module_names) | {
        "torch", "numpy", "PIL", "comfy_api", "typing_extensions",
        "packaging", "safetensors", "psutil", "jinja2", "av", "sympy",
        "mpmath", "networkx", "filelock", "fsspec",
    }

    def check(self, fullname, importer=None):
        if fullname.split(".")[0] in self.allowed:
            return
        if importer and str(importer).startswith(str(V2) + "/"):
            if fullname.startswith("pixaroma_recovery_v2"):
                return
            raise ImportError(f"guest profile excludes {fullname!r} from {importer}")

    def find_spec(self, fullname, path=None, target=None):
        self.check(fullname)
        return None


def namespace(name, root):
    module = types.ModuleType(name)
    module.__path__ = [str(root)]
    sys.modules[name] = module
    return module


def load_v2():
    spec = importlib.util.spec_from_file_location(
        "pixaroma_recovery_v2", V2 / "__init__.py",
        submodule_search_locations=[str(V2)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def equivalent(actual, expected, path="result"):
    if isinstance(expected, torch.Tensor):
        assert isinstance(actual, torch.Tensor), (path, type(actual))
        assert actual.dtype == expected.dtype, (path, actual.dtype, expected.dtype)
        assert actual.shape == expected.shape, (path, actual.shape, expected.shape)
        assert torch.equal(actual, expected), path
        # torch.equal does not distinguish signed zero, so also compare bits.
        assert actual.contiguous().view(torch.uint8).numpy().tobytes() == expected.contiguous().view(torch.uint8).numpy().tobytes(), path
    elif type(expected) is float:
        assert type(actual) is float, (path, type(actual))
        assert (math.isnan(actual) and math.isnan(expected)) or actual.hex() == expected.hex(), (path, actual, expected)
    else:
        assert type(actual) is type(expected), (path, type(actual), type(expected))
        if isinstance(expected, (tuple, list)):
            assert len(actual) == len(expected), path
            for index, (a, e) in enumerate(zip(actual, expected)):
                equivalent(a, e, f"{path}/{index}")
        elif isinstance(expected, dict):
            assert actual.keys() == expected.keys(), path
            for key in expected:
                equivalent(actual[key], expected[key], f"{path}/{key}")
        else:
            assert actual == expected, (path, actual, expected)


def fixture(value):
    if isinstance(value, list):
        return [fixture(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "__float__" in value:
        return float(value["__float__"])
    if value.get("__fixture__") == "tensor":
        shape = value["shape"]
        count = math.prod(shape)
        return torch.arange(count, dtype=getattr(torch, value["dtype"])).reshape(shape)
    if value.get("__fixture__") == "image-info":
        b, h, w = value["batch"], value["height"], value["width"]
        image = torch.arange(b * h * w * 3, dtype=getattr(torch, value["dtype"])).reshape(b, h, w, 3) / 97
        out = {"image": image, "width": w, "height": h, "filename": "synthetic-α.png"}
        if value["mask"]:
            out["mask"] = torch.arange(b * h * w, dtype=getattr(torch, value["dtype"])).reshape(b, h, w) / 71
        return out
    return {key: fixture(item) for key, item in value.items()}


async def read_output(value):
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    if isinstance(value, sdk.Ref):
        return value
    if isinstance(value, tuple):
        return tuple([await read_output(item) for item in value])
    if isinstance(value, list):
        return [await read_output(item) for item in value]
    if isinstance(value, dict):
        return {key: await read_output(item) for key, item in value.items()}
    return value


def plan_for(node_id, fields, *, current="17", dynamic=None):
    def has_tensor(value):
        if isinstance(value, torch.Tensor): return True
        if isinstance(value, dict): return any(has_tensor(item) for item in value.values())
        if isinstance(value, (tuple, list)): return any(has_tensor(item) for item in value)
        return False
    # A real prompt contains producer links; tensors are execution inputs,
    # never serialized literals in the prompt embedded by an image writer.
    prompt_fields = {key: ["fixture-producer", 0] if has_tensor(value) else value for key, value in fields.items()}
    return sdk.ExecutionPlan(
        prompt_id="pixaroma-recovery-finite", node_id=current, node_type=node_id,
        permissions=("graph", "raw"), prompt={current: {"class_type": node_id, "inputs": prompt_fields}},
        dynamic_prompt=dynamic,
    )


async def in_runtime(plan, operation):
    refs = sdk.InProcessRefResolver()
    ctx = sdk.InProcessCtxProvider().build(plan)
    ops = sdk.InProcessOps()
    try:
        with sdk.bind_runtime(refs, ctx, ops):
            return await operation()
    finally:
        refs.clear()


async def compare_case(case, new, original):
    node_id = case["node"]
    fields = fixture(case["fields"])
    cls = new.NODE_CLASS_MAPPINGS[node_id]
    old_cls = getattr(importlib.import_module("pixaroma_recovery_original." + ROWS[node_id]["module"]), cls.__name__)
    hidden = ROWS[node_id]["input_types"].get("hidden", {})
    guest_fields = {key: value for key, value in fields.items() if key not in hidden}
    custom_formula = node_id == "PixaromaDuration" and '"custom"' in str(fields.get("DurationState", ""))
    if custom_formula:
        async def refused():
            try:
                await cls.execute(**guest_fields)
            except RuntimeError as error:
                assert "custom formula requires the pinned simpleeval" in str(error)
                return "REFUSED-AS-DESIGNED"
            raise AssertionError("custom-formula dependency refusal was not raised")
        return await in_runtime(plan_for(node_id, fields), refused)
    expected_error = None
    try:
        expected = getattr(old_cls(), ROWS[node_id]["function"])(**fields)
    except Exception as error:
        expected_error = error

    async def run():
        try:
            got = await cls.execute(**guest_fields)
            if expected_error:
                raise AssertionError(f"source raised {expected_error!r}, conversion returned")
            if isinstance(expected, dict):
                if "result" in expected:
                    equivalent(await read_output(got.args), expected["result"])
                else:
                    equivalent(got.args, ())
                equivalent(got.ui, expected.get("ui"), "ui")
            else:
                equivalent(await read_output(got.args), expected)
                equivalent(got.ui, None, "ui")
        except Exception as error:
            if expected_error is None:
                raise
            assert type(error) is type(expected_error), (type(error), type(expected_error), str(error))
            assert str(error) == str(expected_error), (str(error), str(expected_error))
        return "EXACT"
    return await in_runtime(plan_for(node_id, fields), run)


async def lifecycle(new):
    checked = 0
    for node_id in R1:
        cls = new.NODE_CLASS_MAPPINGS[node_id]
        source = getattr(importlib.import_module("pixaroma_recovery_original." + ROWS[node_id]["module"]), cls.__name__)
        if hasattr(source, "IS_CHANGED"):
            case = next(case for case in CASES if case["node"] == node_id)
            fields = fixture(case["fields"])
            hidden = ROWS[node_id]["input_types"].get("hidden", {})
            guest_fields = {k: v for k, v in fields.items() if k not in hidden}
            async def fingerprint():
                equivalent(await cls.fingerprint_inputs(**guest_fields), source.IS_CHANGED(**fields), "fingerprint")
            await in_runtime(plan_for(node_id, fields), fingerprint)
            checked += 1
    switch = new.NODE_CLASS_MAPPINGS["PixaromaSwitch"]
    source = getattr(importlib.import_module("pixaroma_recovery_original.nodes.node_switch"), "PixaromaSwitch")
    for active in range(1, 33):
        fields = {"SwitchState": str(active), **{f"input_{i}": None for i in range(1, 33)}}
        async def lazy():
            got = await switch.check_lazy_status(**{k: v for k, v in fields.items() if k != "SwitchState"})
            equivalent(got, source().check_lazy_status(**fields), "lazy")
            assert got == [f"input_{active}"]
        await in_runtime(plan_for("PixaromaSwitch", fields), lazy)
        checked += 1
    # Test actual B13 dynamic-prompt precedence and current-node scoping, not a
    # replacement graph object. Browser-injected values must not be defaults.
    class Dynamic:
        def has_node(self, node_id): return node_id == "17"
        def get_node(self, node_id):
            return {"inputs": {"SeedState": '{"runSeed":987654321}'}}
    async def precedence():
        got = await new.NODE_CLASS_MAPPINGS["PixaromaSeed"].execute()
        equivalent(got.args, (987654321,))
    await in_runtime(plan_for("PixaromaSeed", {"SeedState": '{"runSeed":1}'}, dynamic=Dynamic()), precedence)
    checked += 1
    async def zero():
        try:
            await new.NODE_CLASS_MAPPINGS["PixaromaSeed"].execute()
        except RuntimeError as error:
            assert "prompt node id 0" in str(error)
            return
        raise AssertionError("node zero must be visibly refused")
    await in_runtime(plan_for("PixaromaSeed", {}, current="0"), zero)
    checked += 1
    return checked


def encode_and_check(new):
    manifest = {"format": packmanifest.FORMAT, "runtime": manifest_declaration(V2),
        "nodes": {}, "web_directory": None, "frontend_permissions": []}
    mismatches = []
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        schema = cls.GET_SCHEMA()
        schema.validate()
        encoded = packmanifest.encode_schema(schema)
        reference = copy.deepcopy(ROWS[node_id]["schema"])
        reference["attrs"]["description"] = ROWS[node_id]["description"]
        if encoded != reference:
            mismatches.append(node_id)
            (RESULTS / (node_id + "-schema-diff.json")).write_text(json.dumps({"reference": reference, "actual": encoded}, indent=2, sort_keys=True) + "\n")
        methods = {name: name in cls.__dict__ for name in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")}
        row = {"module": ROWS[node_id]["module"], "class": cls.__name__, "sdk_refs": True,
            "permissions": list(cls.SDK_PERMISSIONS), "methods": methods, "schema": encoded}
        if methods["validate_inputs"]:
            row["validation_inputs"] = packmanifest.encode_validation_inputs(cls)
            validation = cls.validate_inputs()
            assert validation is True or validation == f"comfyui-pixaroma/{node_id} is not yet converted to Secure Nodes V2"
        manifest["nodes"][node_id] = row
    assert set(manifest["nodes"]) == set(ROWS) and len(ROWS) == 96
    if mismatches:
        raise AssertionError(f"frozen schema mismatches: {mismatches}")
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (RESULTS / "secure-nodes.json").write_text(text)
    return {"registered": len(ROWS), "schema_exact": len(ROWS), "bytes": len(text.encode()),
        "sha256": hashlib.sha256(text.encode()).hexdigest(), "encoder": packmanifest.__file__}


async def main():
    for root in (PACK, V2):
        count = 0
        for file in root.rglob("*.py"):
            if root == PACK and file.is_relative_to(V2):
                continue
            compile(file.read_bytes(), str(file), "exec")
            count += 1
        RECEIPT["stages"]["compile_" + root.name] = count
    namespace("pixaroma_recovery_original", PACK)
    namespace("pixaroma_recovery_original.nodes", PACK / "nodes")
    guard = GuestImports()
    sys.meta_path.insert(0, guard)
    real_import = __import__
    import builtins
    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0:
            guard.check(name, (globals or {}).get("__file__"))
        return real_import(name, globals, locals, fromlist, level)
    builtins.__import__ = guarded_import
    try:
        new = load_v2()
        RECEIPT["stages"]["schemas"] = encode_and_check(new)
        for index, case in enumerate(CASES):
            row = RECEIPT["nodes"].setdefault(case["node"], {"EXACT": 0, "REFUSED-AS-DESIGNED": 0, "MISMATCH": 0})
            try:
                verdict = await compare_case(case, new, None)
                row[verdict] += 1
            except Exception as error:
                row["MISMATCH"] += 1
                RECEIPT["failures"].append({"index": index, "node": case["node"], "label": case["label"],
                    "type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
        RECEIPT["stages"]["lifecycle_cases"] = await lifecycle(new)
        # Comparator control: a changed scalar and a changed tensor must fail.
        red = 0
        for actual, expected in [((2,), (1,)), (torch.tensor([-0.0]), torch.tensor([0.0]))]:
            try:
                equivalent(actual, expected)
            except AssertionError:
                red += 1
        assert red == 2
        RECEIPT["stages"]["negative_controls_detected"] = red
        RECEIPT["status"] = "PASS" if not RECEIPT["failures"] else "FAIL"
    finally:
        builtins.__import__ = real_import
        sys.meta_path.remove(guard)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except BaseException as error:
        RECEIPT["status"] = "FAIL"
        RECEIPT["failures"].append({"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
    finally:
        signal.alarm(0)
        save()
        print(json.dumps({key: RECEIPT[key] for key in ("status", "scheduled_cases", "stages", "nodes", "failures")}, indent=2), flush=True)
    if RECEIPT["status"] != "PASS":
        raise SystemExit(1)
