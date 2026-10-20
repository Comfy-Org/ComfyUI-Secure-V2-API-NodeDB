"""Finite full original versus genuine default-SDK scalar comparisons. Unrun."""
import argparse
import asyncio
import contextlib
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import sys
import traceback
import warnings


def record(value):
    if value is None:
        return {"type": "NoneType"}
    if type(value) is bool:
        return {"type": "bool", "value": value}
    if type(value) is int:
        return {"type": "int", "decimal": str(value)}
    if type(value) is float:
        return {"type": "float", "hex": value.hex()}
    if type(value) is str:
        return {"type": "str", "value": value}
    if type(value) in (tuple, list):
        return {"type": type(value).__name__, "items": [record(item) for item in value]}
    if type(value) is dict:
        return {"type": "dict", "items": [[record(key), record(item)] for key, item in value.items()]}
    raise TypeError("Unexpected finite scalar fixture value: " + type(value).__name__)


def save(path, value):
    body = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()
    assert len(body) < 8 * 1024**2
    path.write_bytes(body)


def package_at(name, root):
    assert name not in sys.modules
    source = root / "__init__.py"
    spec = importlib.util.spec_from_file_location(name, source, submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    assert Path(package.__file__).resolve() == source.resolve()
    return package


async def sdk_call(cls, inputs, sdk, index):
    # Accepted SplitString/ProPost default-provider boundary, without substitutes.
    providers = sdk.providers
    assert not providers.overlay_active and not providers.engaged
    assert type(providers.execution_backend) is sdk.InProcessExecutionBackend
    assert cls.SDK_REFS is False and tuple(cls.SDK_PERMISSIONS) == ()
    plan = sdk.ExecutionPlan(prompt_id="swap-native-r1", node_id=str(index), node_type="SwapAndScale",
                             node_module=cls.__module__, tier="default", inputs=inputs,
                             input_mode="values", permissions=())
    refs = providers.ref_resolver_factory()
    scope = sdk.bind_runtime(refs, providers.ctx_provider.build(plan), providers.ops_provider)

    async def local_call():
        with scope:
            result = cls.execute(**inputs)
            if inspect.isawaitable(result):
                result = await result
            return result

    try:
        return await sdk.unwrap_outputs(refs, await providers.execution_backend.dispatch(plan, local_call, scope.runtime))
    finally:
        refs.clear()


def schema_record(package, cls, converted):
    v1 = cls.INPUT_TYPES()
    names = ["IN_HEIGHT", "IN_WIDTH", "Swap_Width_Height", "factor_32px", "Limit_1MP"]
    sdk_metadata = None
    if converted:
        # Pinned56fe Schema.finalize adds these hidden inputs to output nodes.
        # They are SDK metadata, separate from the original declared schema.
        assert list(v1) == ["required", "hidden"]
        assert list(v1["hidden"]) == ["prompt", "extra_pnginfo"]
        assert v1["hidden"] == {"prompt": ("PROMPT",), "extra_pnginfo": ("EXTRA_PNGINFO",)}
        sdk_metadata = {"hidden_inputs": record(v1["hidden"]), "legacy_parity_claim": False}
    else:
        assert list(v1) == ["required"]
    assert list(v1["required"]) == names
    fields = []
    for name, value in v1["required"].items():
        attrs = value[1] if len(value) > 1 else {}
        # Input bounds/defaults affect actual behavior; omission stays omission.
        fields.append({"id": name, "type": value[0],
                       "attrs": {key: record(attrs[key]) for key in ("default", "min", "max", "step") if key in attrs}})
    if converted:
        schema = cls.GET_SCHEMA()
        result = {"node_id": schema.node_id, "display_name": schema.display_name, "category": schema.category,
                  "inputs": fields, "outputs": [item.io_type for item in schema.outputs],
                  "output_names": [item.display_name for item in schema.outputs],
                  "output_is_list": [item.is_output_list for item in schema.outputs],
                  "is_input_list": schema.is_input_list, "is_output_node": schema.is_output_node}
    else:
        result = {"node_id": "SwapAndScale", "display_name": package.NODE_DISPLAY_NAME_MAPPINGS["SwapAndScale"],
                  "category": cls.CATEGORY, "inputs": fields, "outputs": list(cls.RETURN_TYPES),
                  "output_names": list(cls.RETURN_NAMES),
                  "output_is_list": list(getattr(cls, "OUTPUT_IS_LIST", (False, False))),
                  "is_input_list": getattr(cls, "INPUT_IS_LIST", False), "is_output_node": cls.OUTPUT_NODE}
    return result, sdk_metadata


async def execute(args, report):
    assert args.cases.stat().st_size < 1024**2
    cases = json.loads(args.cases.read_bytes())
    assert cases["count"] == len(cases["cases"]) == 148
    assert cases["ordinary_count"] == 144 and cases["original_error_count"] == 4
    assert len({row["id"] for row in cases["cases"]}) == 148
    sdk = None
    if args.role == "converted":
        sys.path[:0] = [str(args.backend), str(args.site), str(args.core)]
        sys.argv = ["swap-native", "--cpu"]
        import comfy.options
        comfy.options.enable_args_parsing()
        import comfy.cli_args
        from comfy_api.latest import _io, _sdk
        assert comfy.cli_args.args.cpu is True
        assert Path(comfy.cli_args.__file__).resolve().is_relative_to(args.core.resolve())
        assert Path(_io.__file__).resolve().is_relative_to(args.site.resolve())
        assert Path(_sdk.__file__).resolve().is_relative_to(args.site.resolve())
        sdk = _sdk
        report["genuine_io_sha256"] = hashlib.sha256(Path(_io.__file__).read_bytes()).hexdigest()
        report["genuine_sdk_sha256"] = hashlib.sha256(Path(_sdk.__file__).read_bytes()).hexdigest()
        assert report["genuine_io_sha256"] == "56fe27bdd63f5e78b9b36b95957d93db1021a955d10a015734cf42ccffc599b6"
        assert report["genuine_sdk_sha256"] == "f1a73e4f160e70862f51abdddbb9268e2ce94dd96e18455a79e42307a443f91c"
    package = package_at("_swap_" + args.role, args.root)
    assert set(package.NODE_CLASS_MAPPINGS) == {"SwapAndScale"}
    cls = package.NODE_CLASS_MAPPINGS["SwapAndScale"]
    origin = Path(sys.modules[cls.__module__].__file__).resolve()
    assert origin.is_relative_to(args.root.resolve())
    report["class_source_relative"] = origin.relative_to(args.root.resolve()).as_posix()
    report["registered_count"] = 1
    if sdk is None:
        assert not any(name == "comfy_api" or name.startswith("comfy_api.") for name in sys.modules)
        method = getattr(cls(), cls.FUNCTION)
    else:
        extension = await package.comfy_entrypoint()
        assert await extension.get_node_list() == [cls]
        report["extension_same_registered_class"] = True
        assert report["class_source_relative"] == "swap_and_scale.py"
    report["schema"], report["schema_sdk_metadata"] = schema_record(package, cls, sdk is not None)
    for index, case in enumerate(cases["cases"], 1):
        inputs = case["inputs"]
        assert set(inputs) == {"IN_HEIGHT", "IN_WIDTH", "Swap_Width_Height", "factor_32px", "Limit_1MP"}
        assert type(inputs["IN_HEIGHT"]) is type(inputs["IN_WIDTH"]) is int
        assert all(type(inputs[name]) is bool for name in ("Swap_Width_Height", "factor_32px", "Limit_1MP"))
        row = {"inputs_before": record(inputs)}
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture), warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            try:
                if sdk is None:
                    result = method(**inputs)
                    ui = None
                else:
                    output = await sdk_call(cls, inputs, sdk, index)
                    result, ui = output.result, output.ui
                assert type(result) is tuple and len(result) == 2 and all(type(item) is int for item in result)
                row.update(outcome="returned", result=record(result), ui=record(ui))
            except Exception as error:
                row.update(outcome="error", error={"type": type(error).__name__, "message": str(error)})
        assert len(capture.getvalue().encode()) <= 16384
        row["console"] = capture.getvalue()
        row["warnings"] = [{"type": item.category.__name__, "message": str(item.message)} for item in seen]
        row["inputs_after"] = record(inputs)
        report["cases"][case["id"]] = row
    report["status"] = "ORIGINAL_DONE" if sdk is None else "CONVERTED_REAL_SDK_DONE"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["original", "converted"], required=True)
    for name in ("root", "site", "core", "backend", "cases", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = {"status": "RUNNING", "role": args.role, "cases": {}, "pid": os.getpid(),
              "Guest_public_executor_or_service_acceptance": False}
    code = 1
    try:
        asyncio.run(execute(args, report))
        code = 0
    except BaseException as error:
        report.update(status="FAILED_WORKER", error_type=type(error).__name__, error=str(error)[:2048],
                      traceback=traceback.format_exc()[-8192:])
    finally:
        save(args.output, report)
        print(json.dumps({"status": report["status"], "role": args.role, "cases": len(report["cases"])}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
