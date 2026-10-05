from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import shutil
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
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "770d7b8e4104b8d864d1fed0a65713e4a3e7a953"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = PACK_DB / (
    "patches/comfyui-powershiftscheduler/x770d7b8/"
    "comfyui-powershiftscheduler-x770d7b8"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch, schedulerproviders  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


NODE_IDS = (
    "PowerShiftScheduler",
    "RadianceShiftScheduler",
    "SigmaCurveFromPointsScheduler",
    "SigmaCurvePchipScheduler",
)
PROVIDER_NAMES = (
    "beta_32",
    "beta_33",
    "beta_42",
    "beta_43",
    "beta_44",
    "beta_53",
    "beta_54",
    "beta_57",
    "power_shift",
    "radiance_shift",
    "sigma_curve_from_points",
    "sigma_curve_pchip",
)
PRISTINE_PROVIDER_FUNCTIONS = {
    "beta_32": "beta_32_scheduler",
    "beta_33": "beta_33_scheduler",
    "beta_42": "beta_42_scheduler",
    "beta_43": "beta_43_scheduler",
    "beta_44": "beta_44_scheduler",
    "beta_53": "beta_53_scheduler",
    "beta_54": "beta_54_scheduler",
    "beta_57": "beta_57_scheduler",
    "power_shift": "power_shift_scheduler",
    "radiance_shift": "radiance_shift_scheduler",
    "sigma_curve_from_points": "sigma_curve_scheduler",
    "sigma_curve_pchip": "sigma_curve_pchip_scheduler",
}


def _import_package(name: str, root: pathlib.Path):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_power_shift_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    fake = types.ModuleType("comfy.samplers")

    class SchedulerHandler:
        def __init__(self, handler, use_ms):
            self.handler = handler
            self.use_ms = use_ms

    fake.SchedulerHandler = SchedulerHandler
    fake.SCHEDULER_HANDLERS = {}
    fake.SCHEDULER_NAMES = []
    previous = sys.modules.get("comfy.samplers")
    sys.modules["comfy.samplers"] = fake
    try:
        return _import_package("_pristine_power_shift_test", root)
    finally:
        if previous is None:
            sys.modules.pop("comfy.samplers", None)
        else:
            sys.modules["comfy.samplers"] = previous


def _providers() -> list[dict]:
    return [
        {
            "name": name,
            "module": "scheduler_program",
            "function": "provide",
            "projection": "model_sigmas",
            "min_steps": 1,
            "max_steps": 10_000,
            "config": {"name": name},
        }
        for name in PROVIDER_NAMES
    ]


def _manifest(pack) -> dict:
    nodes = {}
    for node_id in NODE_IDS:
        node = pack.NODE_CLASS_MAPPINGS[node_id]
        nodes[node_id] = {
            "module": "nodes",
            "class": node.__name__,
            "sdk_refs": True,
            "permissions": [],
            "methods": {
                method: method in node.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status"
                )
            },
            "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "scheduler_providers": _providers(),
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)
    }


class FakeSampling:
    def __init__(self, length=1_000):
        self.sigmas = torch.linspace(0.01, 14.0, length)
        self.sigma_min = self.sigmas[0]
        self.sigma_max = self.sigmas[-1]

    def percent_to_sigma(self, percent):
        if percent <= 0.0:
            return self.sigma_max
        if percent >= 1.0:
            return self.sigma_min
        index = round((1.0 - float(percent)) * (len(self.sigmas) - 1))
        return self.sigmas[index]


class FakeModel:
    def __init__(self, length=1_000):
        self.sampling = FakeSampling(length)

    def get_model_object(self, name):
        if name != "model_sampling":
            raise KeyError(name)
        return self.sampling


class FakeModelRef:
    def __init__(self, sampling: FakeSampling):
        self.sampling = sampling

    async def sigma_for_percent(self, percent, actual_endpoints=False):
        if actual_endpoints and percent == 0.0:
            return float(self.sampling.sigma_max)
        if actual_endpoints and percent == 1.0:
            return float(self.sampling.sigma_min)
        return float(self.sampling.percent_to_sigma(percent))


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _legacy_input_details(node):
    inputs = node.INPUT_TYPES()
    return [
        (name, declaration, optional)
        for section, optional in (("required", False), ("optional", True))
        for name, declaration in inputs.get(section, {}).items()
    ]


def test_actual_loader_census_schemas_manifest_and_providers_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert tuple(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert tuple(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")

    for node_id in NODE_IDS:
        original = pristine.NODE_CLASS_MAPPINGS[node_id]
        schema = secure.NODE_CLASS_MAPPINGS[node_id].GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        assert schema.display_name == pristine.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert schema.category == original.CATEGORY
        expected = _legacy_input_details(original)
        assert [item.id for item in schema.inputs] == [item[0] for item in expected]
        assert [item.optional for item in schema.inputs] == [item[2] for item in expected]
        assert [item.io_type for item in schema.outputs] == list(original.RETURN_TYPES)
        for actual, (_, declaration, _) in zip(schema.inputs, expected):
            io_type = declaration[0]
            options = declaration[1] if len(declaration) > 1 else {}
            expected_type = io_type if isinstance(io_type, str) else "COMBO"
            assert actual.io_type == expected_type
            if isinstance(options, dict):
                for key in ("default", "min", "max", "step", "multiline", "tooltip"):
                    if key in options:
                        assert getattr(actual, key) == options[key]

    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.power_shift_test")
    assert tuple(loaded.node_mappings) == NODE_IDS
    assert tuple(provider.name for provider in loaded.scheduler_providers) == PROVIDER_NAMES
    assert all(provider.projection == "model_sigmas" for provider in loaded.scheduler_providers)
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


@pytest.mark.parametrize("name", PROVIDER_NAMES)
@pytest.mark.parametrize("steps", [1, 37, 100])
def test_all_provider_programs_match_pristine_exactly(tmp_path, name, steps):
    pristine = _pristine(tmp_path)
    secure = _secure()
    sampling = FakeSampling(1_000 if steps != 100 else 2_048)
    expected = getattr(pristine, PRISTINE_PROVIDER_FUNCTIONS[name])(
        sampling, steps
    )
    actual = secure.scheduler_program.provide(
        sampling.sigmas.tolist(), steps, {"name": name}
    )
    assert torch.equal(torch.tensor(actual, dtype=torch.float32), expected)


@pytest.mark.parametrize("name", PROVIDER_NAMES)
def test_each_provider_runs_in_its_own_fresh_guest(tmp_path, name):
    pristine = _pristine(tmp_path)
    sampling = FakeSampling()
    expected = getattr(pristine, PRISTINE_PROVIDER_FUNCTIONS[name])(
        sampling, 37
    )

    async def run():
        session = await GuestSession(
            f"power-shift-provider-{name}",
            module_source_root=V2,
            guest_runtime_root=V2,
        ).start()
        try:
            values = await session.invoke_scheduler_provider(
                module_name=f"custom_nodes.power_shift.{name}",
                module_file=str(V2 / "scheduler_program.py"),
                function_name="provide",
                projection=sampling.sigmas.tolist(),
                steps=37,
                config={"name": name},
            )
            actual = schedulerproviders._validate_result(values, 37)
            assert torch.equal(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


NODE_CASES = (
    ("PowerShiftScheduler", (20, 2.0, 1.0, False, 1.0)),
    ("PowerShiftScheduler", (73, 3.7, 0.42, True, 0.5)),
    ("RadianceShiftScheduler", (31, 2.4, 0.98, True, 1.0)),
    ("RadianceShiftScheduler", (45, 0.0, 0.0, False, 0.75)),
    ("SigmaCurveFromPointsScheduler", (8, False, 1.0, None)),
    ("SigmaCurveFromPointsScheduler", (41, True, 0.5, "1.0, .8, .4, .2")),
    ("SigmaCurveFromPointsScheduler", (9, False, 0.0, "1.0")),
    ("SigmaCurvePchipScheduler", (8, False, 1.0, None)),
    ("SigmaCurvePchipScheduler", (57, True, 0.5, "1.0, .9, .3, .1")),
)


@pytest.mark.parametrize("node_id,args", NODE_CASES)
def test_all_nodes_match_pristine_exactly(tmp_path, node_id, args):
    pristine = _pristine(tmp_path)
    secure = _secure()
    model = FakeModel()
    expected = pristine.NODE_CLASS_MAPPINGS[node_id]().get_sigmas(model, *args)[0]

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="power-shift-direct",
            node_id="1",
            node_type=node_id,
            tier="sandbox",
            node_module=secure.NODE_CLASS_MAPPINGS[node_id].__module__,
            permissions=(),
        )
        with _sdk.bind_runtime(
            refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps(),
        ):
            result = await secure.NODE_CLASS_MAPPINGS[node_id].execute(
                FakeModelRef(model.sampling), *args
            )
        return await refs.resolve(result.result[0])

    actual = asyncio.run(run())
    assert torch.equal(actual, expected)


@pytest.mark.parametrize(
    "node_id,args", (NODE_CASES[0], NODE_CASES[2], NODE_CASES[4], NODE_CASES[7])
)
def test_representative_nodes_run_in_real_zero_capability_guest(
    tmp_path, node_id, args,
):
    pristine = _pristine(tmp_path)
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        model = FakeModel()
        model_ref = _sdk.ModelRef._wrap(await refs.create("MODEL", model))
        original = pristine.NODE_CLASS_MAPPINGS[node_id]
        names = list(original.INPUT_TYPES()["required"])
        names += list(original.INPUT_TYPES().get("optional", {}))
        inputs = dict(zip(names, (model_ref, *args)))
        plan = _sdk.ExecutionPlan(
            prompt_id=f"power-shift-guest-{node_id}",
            node_id="1",
            node_type=secure.NODE_CLASS_MAPPINGS[node_id].__name__,
            tier="sandbox",
            node_module=secure.NODE_CLASS_MAPPINGS[node_id].__module__,
            inputs=inputs,
            input_mode="refs",
            permissions=(),
            method="execute",
        )
        session = await GuestSession(
            f"power-shift-node-{node_id}", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(plan, _runtime(plan, refs), capabilities=())
            actual = await refs.resolve(result.result[0])
            expected = original().get_sigmas(model, *args)[0]
            assert torch.equal(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_bounds_and_malformed_inputs_fail_closed():
    secure = _secure()
    program = secure.scheduler_program
    projection = torch.linspace(0.01, 14.0, 1_000).tolist()
    with pytest.raises(TypeError, match="steps"):
        program.provide(projection, True, {"name": "beta_33"})
    with pytest.raises(ValueError, match="steps"):
        program.provide(projection, 10_001, {"name": "beta_33"})
    with pytest.raises(ValueError, match="config"):
        program.provide(projection, 30, {"name": "beta_33", "extra": True})
    with pytest.raises(ValueError, match="unknown"):
        program.provide(projection, 30, {"name": "not_a_scheduler"})
    with pytest.raises(TypeError, match="model sigma"):
        program.provide([[1.0], [0.0]], 30, {"name": "beta_33"})
    with pytest.raises(ValueError, match="model sigma"):
        program.provide([1.0, math.nan], 30, {"name": "beta_33"})
    with pytest.raises(ValueError, match="negative"):
        program.sigma_curve_values(8, False, [1.0, -0.1], method="linear")
    with pytest.raises(ValueError, match="65536 bytes"):
        program.parse_float_list("1" * 65_537)
    with pytest.raises(ValueError, match="10001 values"):
        program.parse_float_list(",".join("1" for _ in range(10_002)))
    with pytest.raises(ValueError, match="effective steps"):
        secure.nodes._total_steps(1_000, 0.001, zero_divides=True)
    with pytest.raises(ZeroDivisionError):
        secure.nodes._total_steps(20, 0.0, zero_divides=True)
    assert secure.nodes._total_steps(20, 0.0, zero_divides=False) == 20


def test_manifest_stubs_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = "\n".join(
        (V2 / name).read_text()
        for name in ("__init__.py", "nodes.py", "scheduler_program.py")
    )
    for required in (
        "SDK_REFS = True",
        "SDK_PERMISSIONS = ()",
        "model.sigma_for_percent(",
        "sdk.SigmasRef.from_values(",
    ):
        assert required in source
    for forbidden in (
        "comfy.samplers", "SCHEDULER_HANDLERS", "SCHEDULER_NAMES",
        "get_model_object", "model.model", "folder_paths", "PromptServer",
        "requests", "aiohttp", "subprocess", "open(", "ctx()", "_from_raw",
        ".from_value(", "import torch", "socket", "urllib",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-powershiftscheduler" / "x770d7b8"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_no_generated_caches():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
