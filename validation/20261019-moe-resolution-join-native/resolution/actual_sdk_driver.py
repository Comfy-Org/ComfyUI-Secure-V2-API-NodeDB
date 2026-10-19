"""Fresh real original/SDK scalar differential; no historical driver imports."""
import argparse
import importlib.util
import inspect
import json
from pathlib import Path
import random
import sys


def mount(root, name):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load real pinned package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    for name in ("backend", "site", "core", "original", "candidate", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(args.backend), str(args.site), str(args.core)]
    sys.argv = ["resolution-ratio-real-sdk", "--cpu"]
    import comfy.options
    comfy.options.enable_args_parsing()
    import comfy.cli_args
    from comfy_api.latest import io
    from comfy_secure_nodes import packmanifest
    assert Path(io.__file__).resolve().is_relative_to(args.site.resolve())
    assert Path(packmanifest.__file__).resolve().is_relative_to(args.backend.resolve())
    assert Path(comfy.cli_args.__file__).resolve().is_relative_to(args.core.resolve())
    assert comfy.cli_args.args.cpu is True
    original = mount(args.original, "_resolution_original_actual")
    converted = mount(args.candidate, "_resolution_sdk_actual")
    assert set(original.NODE_CLASS_MAPPINGS) == set(converted.NODE_CLASS_MAPPINGS) == {"ResolutionAndRatio"}
    native = original.NODE_CLASS_MAPPINGS["ResolutionAndRatio"]
    sdk_node = converted.NODE_CLASS_MAPPINGS["ResolutionAndRatio"]
    assert issubclass(sdk_node, io.ComfyNode)
    assert sdk_node.SDK_REFS is False and sdk_node.SDK_PERMISSIONS == ()
    assert Path(original.WEB_DIRECTORY) == Path(converted.WEB_DIRECTORY) == Path("web")
    assert original.NODE_DISPLAY_NAME_MAPPINGS == converted.NODE_DISPLAY_NAME_MAPPINGS
    required = native.INPUT_TYPES()["required"]
    schema = packmanifest.encode_schema(sdk_node.GET_SCHEMA())
    assert schema["attrs"]["node_id"] == "ResolutionAndRatio"
    assert schema["attrs"]["category"] == native.CATEGORY == "CustomUtils"
    assert schema["attrs"]["display_name"] == original.NODE_DISPLAY_NAME_MAPPINGS["ResolutionAndRatio"]
    assert [row["attrs"]["id"] for row in schema["inputs"]] == list(required)
    defaults = {}
    for row, (name, declaration) in zip(schema["inputs"], required.items(), strict=True):
        first = declaration[0]
        config = declaration[1] if len(declaration) > 1 else {}
        attrs = row["attrs"]
        assert attrs["optional"] is False
        if isinstance(first, list):
            assert row["io_type"] == "COMBO" and attrs["options"] == first
            assert attrs["default"] is None
            defaults[name] = first[0]
        else:
            assert row["io_type"] == first
            assert attrs["default"] == config["default"]
            defaults[name] = config["default"]
        for key in ("min", "max", "step", "label_on", "label_off", "multiline"):
            if key in config:
                assert attrs[key] == config[key], (name, key)
        if "display" in config:
            assert attrs["display_mode"] == {"$type": "enum", "enum": "NumberDisplay", "name": config["display"]}
    assert [row["io_type"] for row in schema["outputs"]] == list(native.RETURN_TYPES) == ["INT", "INT"]
    assert [row["attrs"]["id"] for row in schema["outputs"]] == list(native.RETURN_NAMES) == ["width", "height"]
    assert schema["hidden"] == []
    assert str(inspect.signature(native.VALIDATE_INPUTS)) == str(inspect.signature(sdk_node.validate_inputs))
    validation_inputs = packmanifest.encode_validation_inputs(sdk_node)
    assert isinstance(validation_inputs, dict)
    cases = []
    validators = 0

    def assert_pair_equal(actual, expected):
        assert type(expected) is tuple and type(actual) is tuple and len(actual) == 2
        assert all(type(value) is int for value in actual)
        assert actual == expected and all(8 <= value <= 4096 for value in actual)

    def compare(values, kind):
        nonlocal validators
        expected = native().get_resolution(**values)
        result = sdk_node.execute(**values)
        assert isinstance(result, io.NodeOutput)
        actual = result.result
        assert_pair_equal(actual, expected)
        expected_validation = native.VALIDATE_INPUTS(**values)
        actual_validation = sdk_node.validate_inputs(**values)
        assert actual_validation == expected_validation
        validators += 1
        cases.append({"kind": kind, "inputs": values, "expected": list(expected), "actual": list(actual)})

    for width, height in ((8, 32), (25, 31), (33, 47), (48, 80), (80, 112), (525, 533), (4095, 4096), (512, 768)):
        for reset in (False, True):
            for swap in (False, True):
                compare(dict(defaults, width=width, height=height, reset=reset, swap=swap), "fixed")
    rng = random.Random(20261019)
    for _ in range(1000):
        values = dict(defaults, width=rng.uniform(-10000, 10000), height=rng.uniform(-10000, 10000),
                      W_ratio=rng.randint(1, 512), H_ratio=rng.randint(1, 512), scale_percent=rng.randint(10, 200),
                      reset=bool(rng.getrandbits(1)), swap=bool(rng.getrandbits(1)))
        compare(values, "deterministic_random_direct_scalar")
    # Ratio/scale/preset strings are frontend controls. Backend must retain the
    # original rule of using dimensions and flags rather than recomputing them.
    compare(dict(defaults, width=1152, height=1536, W_ratio=512, H_ratio=1,
                 scale_percent=200, preset="Custom", custom_presets="different authored text"), "backend_frontend_separation")
    guard_cases = []
    for name in ("width", "height", "W_ratio", "H_ratio", "scale_percent"):
        for value, label in ((True, "bool"), ("12", "text"), (float("nan"), "nan"), (float("inf"), "inf"), (1000000001, "resource")):
            guard_cases.append((name + ":" + label, dict(defaults, **{name: value})))
    guard_cases += [("reset:notbool", dict(defaults, reset=1)), ("swap:notbool", dict(defaults, swap="true")),
        ("preset:nottext", dict(defaults, preset=1)), ("preset:length", dict(defaults, preset="x" * 129)),
        ("custom:nottext", dict(defaults, custom_presets=False)),
        ("custom:length", dict(defaults, custom_presets="x" * 65537)),
        ("custom:lines", dict(defaults, custom_presets="x\n" * 1024)),
        ("custom:utf8", dict(defaults, custom_presets="é" * 32769))]
    denials = []
    for label, values in guard_cases:
        try:
            sdk_node.execute(**values)
        except (TypeError, ValueError) as error:
            denials.append({"case": label, "type": type(error).__name__})
        else:
            raise AssertionError("guard did not deny: " + label)
    controls = []
    for label, values, corrupted in (
        ("swapped_dimensions", dict(defaults, width=512, height=768), (768, 512)),
        ("javascript_tie_rounding", dict(defaults, width=80, height=112), (96, 128)),
        ("unwanted_scale_recompute", dict(defaults, width=512, height=768, scale_percent=200), (1024, 1536))):
        expected = native().get_resolution(**values)
        assert sdk_node.execute(**values).result == expected
        try:
            assert_pair_equal(corrupted, expected)
        except AssertionError:
            controls.append({"control": label, "detected": True})
        else:
            raise AssertionError("wrong-output control escaped the actual comparator: " + label)
    report = {"status": "PASS_REAL_ORIGINAL_AND_SELECTED_SDK_BACKEND_ONLY", "node_id": "ResolutionAndRatio",
        "schema_count": 1, "execution_comparisons": len(cases), "validator_comparisons": validators,
        "guard_denials": denials, "negative_controls": controls,
        "validator_signature_encoded_by_actual_encoder": validation_inputs,
        "fixed_cases": [row for row in cases if row["kind"] != "deterministic_random_direct_scalar"],
        "random_comparisons": 1000, "random_seed": 20261019,
        "sdk_io_origin": str(Path(io.__file__).resolve()), "encoder_origin": str(Path(packmanifest.__file__).resolve()),
        "frontend_tested": False, "service_tested": False, "general_runtime_adoption": False,
        "limits": "Direct scalar out-of-schema clamps and resource denials are explicit; no native UI/browser/Guest/service acceptance implied."}
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "schema_count", "execution_comparisons", "validator_comparisons", "random_comparisons")}))


if __name__ == "__main__":
    main()
