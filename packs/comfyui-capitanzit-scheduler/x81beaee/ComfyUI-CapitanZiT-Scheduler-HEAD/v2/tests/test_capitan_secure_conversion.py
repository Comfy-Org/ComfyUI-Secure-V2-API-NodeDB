from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import types

import pytest
import torch


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "81beaee4331df26ba040e0c6103766702651dfa0"
COMFY_API_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
COMFY_API_PYI_SHA256 = "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"
PAIR = PACK_DB / "patches" / "comfyui-capitanzit-scheduler" / "x81beaee" / (
    "comfyui-capitanzit-scheduler-x81beaee"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch, schedulerproviders  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_v2():
    name = "_secure_capitan_scheduler_test"
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _pack_module(pack, name: str):
    return __import__(f"{pack.__name__}.{name}", fromlist=[name])


def _import_source(filename: str):
    name = f"_upstream_capitan_{pathlib.Path(filename).stem}"
    comfy = types.ModuleType("comfy")
    samplers = types.ModuleType("comfy.samplers")
    utils = types.ModuleType("comfy.utils")

    class SchedulerHandler:
        def __init__(self, function, **options):
            self.function = function
            self.options = options

    samplers.SchedulerHandler = SchedulerHandler
    samplers.SCHEDULER_HANDLERS = {}
    samplers.SCHEDULER_NAMES = []
    samplers.KSAMPLER = lambda function: types.SimpleNamespace(
        sampler_function=function
    )
    comfy.samplers = samplers
    comfy.utils = utils
    comfy.model_management = types.SimpleNamespace(
        get_torch_device=lambda: torch.device("cpu")
    )
    saved = {
        key: sys.modules.get(key)
        for key in ("comfy", "comfy.samplers", "comfy.utils")
    }
    try:
        sys.modules["comfy"] = comfy
        sys.modules["comfy.samplers"] = samplers
        sys.modules["comfy.utils"] = utils
        spec = importlib.util.spec_from_file_location(name, PACK / filename)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for key, value in saved.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


def _generated_manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status"
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "frontend_permissions": [],
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "scheduler_providers": [{
            "name": "capitanZiT",
            "module": "scheduler_program",
            "function": "provide",
            "projection": "none",
            "min_steps": 1,
            "max_steps": 100,
            "config": {},
        }],
        "web_directory": "web",
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    result = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root)
        if not item.is_file() or any(
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in relative.parts
        ):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _plan(node_class, inputs, permissions, *, number=1):
    return _sdk.ExecutionPlan(
        prompt_id="capitan-behavior",
        node_id=str(number),
        node_type=node_class.__name__,
        tier="sandbox",
        node_module=node_class.__module__,
        inputs=inputs,
        permissions=permissions,
    )


def test_pinned_pristine_and_secure_census_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    expected = {
        "CapitanZiTLinearSigma",
        "FlowMatchSchedulerKleinEdit",
        "FlowMatchSchedulerSmoothCosine",
        "SamplerMinimalChangeFlow",
    }
    source_classes = set()
    for path in PACK.glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text())
        source_classes.update(
            item.name for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name in expected
        )
    assert source_classes == expected
    pristine_frontend = (PACK / "js" / "klein_xy_pad.js").read_text()
    assert pristine_frontend.count("app.registerExtension({") == 1
    pristine_python = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.glob("*.py")
    )
    assert "SCHEDULER_HANDLERS" in pristine_python
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == expected
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == expected
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.capitan_scheduler_test"
    )
    assert set(loaded.node_mappings) == expected
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert len(loaded.scheduler_providers) == 1
    assert loaded.scheduler_providers[0].name == "capitanZiT"


def test_schemas_preserve_names_types_options_and_permissions():
    pack = _import_v2()
    expected = {
        "CapitanZiTLinearSigma": (
            ["steps"], ["INT"], ["SIGMAS"], ("raw",)
        ),
        "FlowMatchSchedulerKleinEdit": (
            ["model", "steps", "denoise", "sigma_min", "shift", "curve", "draw_mode", "custom_sigmas"],
            ["MODEL", "INT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "STRING", "STRING"],
            ["MODEL", "SIGMAS"], ("raw",),
        ),
        "FlowMatchSchedulerSmoothCosine": (
            ["model", "steps", "denoise"], ["MODEL", "INT", "FLOAT"],
            ["MODEL", "SIGMAS"], ("raw",),
        ),
        "SamplerMinimalChangeFlow": (
            ["max_change_per_step"], ["FLOAT"], ["SAMPLER"], ("closures",),
        ),
    }
    for node_id, (names, types_, outputs, permissions) in expected.items():
        node = pack.NODE_CLASS_MAPPINGS[node_id]
        schema = node.GET_SCHEMA()
        assert [item.id for item in schema.inputs] == names
        assert [item.io_type for item in schema.inputs] == types_
        assert [item.io_type for item in schema.outputs] == outputs
        assert node.SDK_REFS is True
        assert node.SDK_PERMISSIONS == permissions
        assert schema.not_idempotent is False
    klein = pack.FlowMatchSchedulerKleinEdit.GET_SCHEMA()
    assert klein.inputs[6].optional is True
    assert klein.inputs[6].default == "parametric"
    assert klein.inputs[7].optional is True
    assert klein.inputs[7].default == "[]"


@pytest.mark.parametrize("steps", [1, 2, 4, 9, 37, 100])
def test_linear_sigma_node_and_provider_are_numerically_differential(steps):
    upstream = _import_source("capitan_zit_scheduler.py")
    pack = _import_v2()
    actual = torch.tensor(_pack_module(pack, "nodes").linear_sigmas(steps), dtype=torch.float32)
    assert torch.allclose(
        actual, upstream.capitan_zit_scheduler(None, steps), atol=6e-8, rtol=0
    )
    provider = _pack_module(pack, "scheduler_program").provide(None, steps, {})
    assert torch.equal(torch.tensor(provider), actual)


@pytest.mark.parametrize(
    "steps,denoise",
    [(4, 0.0), (4, 1.0), (8, 1.0), (17, 0.42), (100, 0.99)],
)
def test_smooth_cosine_is_numerically_differential(steps, denoise):
    upstream = _import_source("smooth_cosine_scheduler.py")
    expected = upstream.FlowMatchSchedulerSmoothCosine().get_sigmas(
        object(), steps, denoise
    )[1]
    actual = torch.tensor(
        _pack_module(_import_v2(), "nodes").smooth_cosine_sigmas(steps, denoise),
        dtype=torch.float32,
    )
    assert torch.allclose(actual, expected, atol=1e-7, rtol=1e-6)


@pytest.mark.parametrize(
    "steps,denoise,sigma_min,shift,curve",
    [
        (1, 0.001, 0.0, 0.01, 0.01),
        (4, 1.0, 0.0, 1.0, 1.0),
        (9, 1.4, 0.02, 3.7, 0.35),
        (37, 0.7, 0.3, 20.0, 10.0),
        (100, 2.0, 1.0, 0.01, 10.0),
    ],
)
def test_klein_parametric_is_numerically_differential(
    steps, denoise, sigma_min, shift, curve,
):
    upstream = _import_source("capitan_zit_scheduler.py")
    expected = upstream.FlowMatchSchedulerKleinEdit().get_sigmas(
        object(), steps, denoise, sigma_min, shift, curve
    )[1]
    actual = torch.tensor(
        _pack_module(_import_v2(), "nodes").klein_parametric_sigmas(
            steps, denoise, sigma_min, shift, curve
        ),
        dtype=torch.float32,
    )
    assert torch.allclose(actual, expected, atol=2e-6, rtol=2e-6)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("[1.2, 0.7, 0]", [1.2, 0.7, 0]),
        ("[1.2, 0.7]", [1.2, 0.7, 0]),
        ("not json", None),
        ("[]", None),
        ("[1, true]", None),
        ("{\"sigma\": 1}", None),
    ],
)
def test_drawn_schedule_parsing_and_fallback(text, expected):
    pack = _import_v2()
    actual = _pack_module(pack, "nodes")._drawn_sigmas(text)
    if expected is None:
        assert actual is None
    else:
        assert actual == pytest.approx(expected)
    with pytest.raises(ValueError, match="byte limit"):
        _pack_module(pack, "nodes")._drawn_sigmas("[" + "0," * 32769 + "0]")


def test_real_guest_preserves_model_identity_and_all_sigma_outputs():
    pack = _import_v2()
    nodes = _pack_module(pack, "nodes")

    async def run():
        refs = _sdk.InProcessRefResolver()
        source_model = object()
        model = _sdk.ModelRef._wrap(await refs.create("MODEL", source_model))
        session = await GuestSession("capitan-sigma-behavior", guest_runtime_root=V2).start()
        try:
            cases = [
                (pack.CapitanZiTLinearSigma, {"steps": 9}, None, nodes.linear_sigmas(9)),
                (
                    pack.FlowMatchSchedulerKleinEdit,
                    {
                        "model": model, "steps": 4, "denoise": 1.0,
                        "sigma_min": 0.0, "shift": 1.0, "curve": 1.0,
                        "draw_mode": "draw", "custom_sigmas": "[1,0.6,0.2]",
                    },
                    source_model, [1.0, 0.6, 0.2, 0.0],
                ),
                (
                    pack.FlowMatchSchedulerSmoothCosine,
                    {"model": model, "steps": 8, "denoise": 0.75},
                    source_model, nodes.smooth_cosine_sigmas(8, 0.75),
                ),
            ]
            pids = []
            for number, (node, inputs, expected_model, expected_sigmas) in enumerate(cases, 1):
                plan = _plan(node, inputs, ("raw",), number=number)
                output = await session.execute(
                    plan, _runtime(plan, refs), capabilities=("raw",)
                )
                if expected_model is None:
                    sigma_ref = output.result[0]
                else:
                    assert await refs.resolve(output.result[0]) is expected_model
                    sigma_ref = output.result[1]
                actual = await refs.resolve(sigma_ref)
                assert torch.allclose(
                    actual, torch.tensor(expected_sigmas, dtype=torch.float32),
                    atol=2e-6, rtol=2e-6,
                )
                pids.append(session.last_guest_pid)
            assert all(pid not in (None, os.getpid()) for pid in pids)
        finally:
            await session.kill()

    asyncio.run(run())


class _Sampling:
    noise_scale = 1.0


class _ModelPatcher:
    @staticmethod
    def get_model_object(name):
        assert name == "model_sampling"
        return _Sampling()


class _SamplerModel:
    def __init__(self):
        self.inner_model = types.SimpleNamespace(model_patcher=_ModelPatcher())
        self.calls = []

    def __call__(self, value, sigma, **extra):
        self.calls.append((value.clone(), sigma.clone(), dict(extra)))
        sigma_value = sigma.reshape((-1,) + (1,) * (value.ndim - 1))
        return value * 0.25 + sigma_value * 0.1


def test_minimal_change_sampler_matches_upstream_with_real_callback_flow():
    pack = _import_v2()
    upstream = _import_source("minimal_change_sampler.py")
    latent = torch.tensor([[[[1.0, -2.0], [0.5, -0.25]]]])
    sigmas = torch.tensor([2.0, 1.0, 0.4, 0.0])

    expected_model = _SamplerModel()
    expected_callbacks = []
    expected = upstream.sample_minimal_change_flow(
        expected_model, latent.clone(), sigmas,
        extra_args={"tag": "kept"}, callback=expected_callbacks.append,
        disable=True, max_change_per_step=0.20,
    )

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession("capitan-sampler-behavior", guest_runtime_root=V2).start()
        try:
            plan = _plan(
                pack.SamplerMinimalChangeFlow,
                {"max_change_per_step": 0.20},
                ("closures",),
            )
            output = await session.execute(
                plan, _runtime(plan, refs), capabilities=("closures",)
            )
            sampler = await refs.resolve(output.result[0])
            actual_model = _SamplerModel()
            actual_callbacks = []
            actual = await asyncio.to_thread(
                sampler.sampler_function,
                actual_model,
                latent.clone(),
                sigmas,
                extra_args={"tag": "kept"},
                callback=actual_callbacks.append,
                disable=True,
            )
            assert session.last_guest_pid not in (None, os.getpid())
            assert torch.allclose(actual, expected, atol=1e-6, rtol=1e-6)
            assert len(actual_model.calls) == len(expected_model.calls) == 3
            assert [item["i"] for item in actual_callbacks] == [0, 1, 2]
            assert [item["i"] for item in expected_callbacks] == [0, 1, 2]
            for actual_item, expected_item in zip(actual_callbacks, expected_callbacks):
                assert set(actual_item) == set(expected_item)
                for key in ("x", "denoised"):
                    assert torch.allclose(actual_item[key], expected_item[key])
                for key in ("sigma", "sigma_hat"):
                    assert float(actual_item[key]) == pytest.approx(
                        float(expected_item[key])
                    )
            assert all(call[2] == {"tag": "kept"} for call in actual_model.calls)
        finally:
            await session.kill()

    asyncio.run(run())


def test_sampler_and_sigmas_fail_closed_without_declared_capabilities():
    pack = _import_v2()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession("capitan-denied", guest_runtime_root=V2).start()
        try:
            sampler_plan = _plan(
                pack.SamplerMinimalChangeFlow,
                {"max_change_per_step": 0.7},
                ("closures",),
            )
            with pytest.raises(Exception):
                await session.execute(
                    sampler_plan, _runtime(sampler_plan, refs), capabilities=()
                )
            sigma_plan = _plan(
                pack.CapitanZiTLinearSigma, {"steps": 9}, ("raw",), number=2
            )
            with pytest.raises(Exception):
                await session.execute(
                    sigma_plan, _runtime(sigma_plan, refs), capabilities=()
                )
        finally:
            await session.kill()

    asyncio.run(run())


def test_scheduler_provider_runs_in_a_fresh_guest_and_rejects_bad_requests():
    module = V2 / "scheduler_program.py"

    async def run():
        session = await GuestSession(
            "capitan-provider",
            module_source_root=V2,
            guest_runtime_root=V2,
        ).start()
        try:
            values = await session.invoke_scheduler_provider(
                module_name="custom_nodes.capitan_scheduler.scheduler_program",
                module_file=str(module),
                function_name="provide",
                projection=None,
                steps=9,
                config={},
            )
            assert torch.equal(
                schedulerproviders._validate_result(values, 9),
                torch.linspace(1.0, 0.0, 10),
            )
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception):
                await session.invoke_scheduler_provider(
                    module_name="custom_nodes.capitan_scheduler.scheduler_program",
                    module_file=str(module),
                    function_name="provide",
                    projection=None,
                    steps=9,
                    config={"unexpected": True},
                )
        finally:
            await session.kill()

    asyncio.run(run())


def test_bounds_and_malformed_inputs_fail_closed():
    pack = _import_v2()
    nodes = _pack_module(pack, "nodes")
    with pytest.raises(ValueError, match="steps"):
        nodes.linear_sigmas(0)
    with pytest.raises(TypeError, match="steps"):
        nodes.linear_sigmas(True)
    with pytest.raises(ValueError, match="denoise"):
        nodes.smooth_cosine_sigmas(8, math.nan)
    with pytest.raises(ValueError, match="shift"):
        nodes.klein_parametric_sigmas(4, 1, 0, 21, 1)
    with pytest.raises(ValueError, match="out-of-range"):
        nodes._drawn_sigmas("[1, 10001]")


def test_manifest_security_contract_frontend_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256
    source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "comfy.samplers", "SCHEDULER_HANDLERS", "SCHEDULER_NAMES", "PromptServer",
        "aiohttp", "subprocess", "folder_paths", "open(", "eval(", "exec(",
    ):
        assert forbidden not in source
    frontend = "\n".join(path.read_text() for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "LiteGraph", "app.graph", "app.canvas", "document.",
        "window.", "localStorage", "indexedDB", "fetch(", "comfy.backend",
        "innerHTML", "addEventListener",
    ):
        assert forbidden not in frontend
    assert "node.widgets.canvas" in frontend
    assert "setHidden(true)" in frontend
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_curve_pointer_serialization_and_teardown():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "klein_frontend_harness.mjs"),
            str(V2 / "web" / "klein_xy_pad.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: Klein graph" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    # The pristine pack contains CRLF files; decode bytes without universal
    # newline translation so the distributable is compared byte-for-byte.
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-capitanzit-scheduler" / "x81beaee"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_leave_no_bytecode_or_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
