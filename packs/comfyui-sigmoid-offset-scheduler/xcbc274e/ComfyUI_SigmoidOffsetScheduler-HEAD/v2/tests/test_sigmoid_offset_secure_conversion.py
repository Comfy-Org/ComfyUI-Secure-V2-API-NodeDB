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

import pytest
import torch


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"))
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "cbc274e54eb9229f16c60e8c30058135140931c2"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = PACK_DB / (
    "patches/comfyui-sigmoid-offset-scheduler/xcbc274e/"
    "comfyui-sigmoid-offset-scheduler-xcbc274e"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch, schedulerproviders  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


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
    return _import_package("_secure_sigmoid_offset_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_sigmoid_offset_test", root)


def _manifest(pack) -> dict:
    node = pack.NODE_CLASS_MAPPINGS["SigmoidOffsetScheduler"]
    return {
        "format": FORMAT,
        "nodes": {
            "SigmoidOffsetScheduler": {
                "module": "nodes",
                "class": "SigmoidOffsetScheduler",
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
        },
        "runtime": manifest_declaration(V2),
        "scheduler_providers": [{
            "name": "sigmoid_offset",
            "module": "scheduler_program",
            "function": "provide",
            "projection": "model_sigmas",
            "min_steps": 1,
            "max_steps": 10_000,
            "config": {"square_k": 1.0, "base_c": 0.5},
        }],
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)
    }


class FakeSampling:
    def __init__(self):
        self.sigmas = torch.linspace(0.01, 14.0, 1_000)
        self.sigma_min = self.sigmas[0]
        self.sigma_max = self.sigmas[-1]

    def percent_to_sigma(self, percent):
        if percent <= 0.0:
            return 999999999.9
        if percent >= 1.0:
            return 0.0
        index = round((1.0 - float(percent)) * 999)
        return self.sigmas[index]


class FakeModel:
    def __init__(self):
        self.sampling = FakeSampling()

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


def test_actual_loader_census_schema_manifest_and_provider_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"SigmoidOffsetScheduler"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"SigmoidOffsetScheduler"}
    assert not hasattr(pristine, "WEB_DIRECTORY")

    original = pristine.NODE_CLASS_MAPPINGS["SigmoidOffsetScheduler"]
    schema = secure.SigmoidOffsetScheduler.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "SigmoidOffsetScheduler", "SigmoidOffsetScheduler", original.CATEGORY,
    )
    assert [item.id for item in schema.inputs] == list(original.INPUT_TYPES()["required"])
    assert [item.io_type for item in schema.outputs] == list(original.RETURN_TYPES)
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.sigmoid_offset_test")
    assert set(loaded.node_mappings) == {"SigmoidOffsetScheduler"}
    assert len(loaded.scheduler_providers) == 1
    provider = loaded.scheduler_providers[0]
    assert (provider.name, provider.projection, provider.min_steps, provider.max_steps) == (
        "sigmoid_offset", "model_sigmas", 1, 10_000,
    )
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


@pytest.mark.parametrize(
    "length,steps,square_k,base_c",
    [
        (1_000, 1, 1.0, 0.5),
        (1_000, 30, 1.0, 0.5),
        (1_000, 111, 4.3, -0.75),
        (1_000, 10_000, 10.0, 5.0),
        (37, 19, 0.3, 1.25),
        (2_048, 250, 2.0, -2.0),
        (1_000, 30, 0.0, 0.5),
    ],
)
def test_scheduler_math_matches_pristine_exactly(
    tmp_path, length, steps, square_k, base_c,
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    sampling = FakeSampling()
    sampling.sigmas = torch.linspace(0.01, 20.0, length)
    sampling.sigma_min = sampling.sigmas[0]
    sampling.sigma_max = sampling.sigmas[-1]
    with pytest.warns(RuntimeWarning) if square_k == 0.0 else _nullcontext():
        expected = pristine.sigmoid_offset_scheduler(
            sampling, steps, square_k=square_k, base_c=base_c,
        )
    actual = secure.scheduler_program.schedule_from_projection(
        sampling.sigmas.tolist(), steps, square_k=square_k, base_c=base_c,
    )
    assert torch.equal(torch.tensor(actual, dtype=torch.float32), expected)


class _nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *_args):
        return False


@pytest.mark.parametrize(
    "steps,square_k,base_c,start_sigma",
    [
        (1, 1.0, 0.5, 1.0),
        (30, 1.0, 0.5, 1.0),
        (73, 4.0, -0.5, 0.983),
        (333, 0.25, 2.0, 0.25),
        (30, 0.0, 0.5, 1.0),
    ],
)
def test_node_matches_pristine_for_all_controls(
    tmp_path, steps, square_k, base_c, start_sigma,
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    model = FakeModel()
    with pytest.warns(RuntimeWarning) if square_k == 0.0 else _nullcontext():
        expected = pristine.NODE_CLASS_MAPPINGS["SigmoidOffsetScheduler"]().get_sigmas(
            model, steps, square_k, base_c, start_sigma,
        )[0]

    async def run_with_runtime():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="sigmoid-offset-direct",
            node_id="1",
            node_type=secure.SigmoidOffsetScheduler.__name__,
            tier="sandbox",
            node_module=secure.SigmoidOffsetScheduler.__module__,
            permissions=(),
        )
        with _sdk.bind_runtime(
            refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps(),
        ):
            result = await secure.SigmoidOffsetScheduler.execute(
                FakeModelRef(model.sampling), steps, square_k, base_c, start_sigma,
            )
        return await refs.resolve(result.result[0])

    actual = asyncio.run(run_with_runtime())
    assert torch.equal(actual, expected)


def test_real_isolated_guest_uses_typed_model_projection_without_authority(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        model = FakeModel()
        model_ref = _sdk.ModelRef._wrap(await refs.create("MODEL", model))
        inputs = {
            "model": model_ref,
            "steps": 17,
            "square_k": 2.4,
            "base_c": -0.2,
            "start_sigma": 0.75,
        }
        plan = _sdk.ExecutionPlan(
            prompt_id="sigmoid-offset-guest",
            node_id="1",
            node_type=secure.SigmoidOffsetScheduler.__name__,
            tier="sandbox",
            node_module=secure.SigmoidOffsetScheduler.__module__,
            inputs=inputs,
            input_mode="refs",
            permissions=(),
            method="execute",
        )
        session = await GuestSession("sigmoid-offset", guest_runtime_root=V2).start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=(),
            )
            actual = await refs.resolve(result.result[0])
            expected = pristine.NODE_CLASS_MAPPINGS["SigmoidOffsetScheduler"]().get_sigmas(
                model, 17, 2.4, -0.2, 0.75,
            )[0]
            assert torch.equal(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_declarative_provider_runs_in_fresh_guest_and_rejects_bad_requests(tmp_path):
    pristine = _pristine(tmp_path)
    projection = torch.linspace(0.01, 20.0, 1_000)
    sampling = FakeSampling()
    sampling.sigmas = projection
    sampling.sigma_min = projection[0]
    expected = pristine.sigmoid_offset_scheduler(sampling, 30)

    async def run():
        session = await GuestSession(
            "sigmoid-offset-provider", module_source_root=V2, guest_runtime_root=V2,
        ).start()
        try:
            values = await session.invoke_scheduler_provider(
                module_name="custom_nodes.sigmoid_offset.scheduler_program",
                module_file=str(V2 / "scheduler_program.py"),
                function_name="provide",
                projection=projection.tolist(),
                steps=30,
                config={"square_k": 1.0, "base_c": 0.5},
            )
            actual = schedulerproviders._validate_result(values, 30)
            assert torch.equal(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception):
                await session.invoke_scheduler_provider(
                    module_name="custom_nodes.sigmoid_offset.scheduler_program",
                    module_file=str(V2 / "scheduler_program.py"),
                    function_name="provide",
                    projection=projection.tolist(),
                    steps=30,
                    config={"square_k": 2.0, "base_c": 0.5},
                )
        finally:
            await session.kill()

    asyncio.run(run())


def test_bounds_and_malformed_inputs_fail_closed():
    secure = _secure()
    program = secure.scheduler_program
    with pytest.raises(TypeError, match="steps"):
        program.sigmoid_indices(999, True, 1.0, 0.5)
    with pytest.raises(ValueError, match="steps"):
        program.sigmoid_indices(999, 10_001, 1.0, 0.5)
    with pytest.raises(ValueError, match="square_k"):
        program.sigmoid_indices(999, 30, math.nan, 0.5)
    with pytest.raises(ValueError, match="base_c"):
        program.sigmoid_indices(999, 30, 1.0, 5.1)
    with pytest.raises(ValueError, match="projection"):
        program.schedule_from_projection([1.0], 30)
    with pytest.raises(ValueError, match="model sigma"):
        program.schedule_from_projection([0.0, math.inf], 30)


def test_manifest_stubs_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = "\n".join(
        (V2 / name).read_text() for name in ("__init__.py", "nodes.py", "scheduler_program.py")
    )
    for required in (
        "SDK_REFS = True", "SDK_PERMISSIONS = ()",
        "model.sigma_for_percent(", "sdk.SigmasRef.from_values(",
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
    fresh = tmp_path / "comfyui-sigmoid-offset-scheduler" / "xcbc274e"
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
