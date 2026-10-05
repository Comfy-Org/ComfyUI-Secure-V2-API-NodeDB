from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import sys
from types import SimpleNamespace

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
COMMIT = "a2d601ad360cd6c0fdfd7cbd118d4bfa9d40ed0a"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/comfyui-wanmoescheduler/xa2d601a/comfyui-wanmoescheduler-xa2d601a"

for root in (BACKEND, CORE, COMFYUI):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
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
    return _import_package("_secure_wanmoe_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_wanmoe_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": node_class.SDK_REFS is True,
            "permissions": list(node_class.SDK_PERMISSIONS),
            "methods": {
                method: method in node_class.__dict__
                for method in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
    }


class FakeSampling:
    def __init__(self, config=None):
        self.config = config
        self.shift = 1.0

    def set_parameters(self, *, shift):
        self.shift = float(shift)


class FakeModel:
    def __init__(self):
        self.model = SimpleNamespace(model_config="wan-test")
        self.original = FakeSampling("original")
        self.current = self.original

    def get_model_object(self, name):
        if name != "model_sampling":
            raise KeyError(name)
        return self.current

    def add_object_patch(self, name, value):
        assert name == "model_sampling"
        self.current = value


def _fake_calculate_sigmas(sampling, scheduler, steps):
    assert scheduler in {"simple", "sgm_uniform", "ddim_uniform", "beta", "normal"}
    high = 0.5 + 0.1 * sampling.shift
    return torch.linspace(high, 0.0, steps + 1)


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_actual_loader_census_schema_and_manifest_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"WanMoEScheduler"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"WanMoEScheduler"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert secure.WanMoEScheduler.SDK_REFS is True
    assert secure.WanMoEScheduler.SDK_PERMISSIONS == ()

    original = pristine.NODE_CLASS_MAPPINGS["WanMoEScheduler"]
    schema = secure.WanMoEScheduler.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "WanMoEScheduler", "WanMoEScheduler", original.CATEGORY,
    )
    assert [item.id for item in schema.inputs] == list(original.INPUT_TYPES()["required"])
    assert schema.inputs[1].options == [
        "simple", "sgm_uniform", "ddim_uniform", "beta", "normal",
    ]
    assert [item.io_type for item in schema.outputs] == list(original.RETURN_TYPES)
    assert [item.display_name for item in schema.outputs] == list(original.RETURN_NAMES)
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.wanmoe_secure_test")
    assert set(loaded.node_mappings) == {"WanMoEScheduler"}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


@pytest.mark.parametrize(
    "scheduler,steps_high,steps_low,denoise,boundary,interval",
    [
        ("normal", 4, 4, 1.0, 0.55, 1.0),
        ("simple", 2, 5, 0.5, 0.30, 0.5),
        ("beta", 1, 1, 1.0, 0.40, 0.25),
    ],
)
def test_shift_search_and_all_three_sigma_outputs_match_pristine(
    tmp_path, monkeypatch, scheduler, steps_high, steps_low, denoise, boundary,
    interval,
):
    import comfy.samplers

    monkeypatch.setattr(comfy.samplers, "calculate_sigmas", _fake_calculate_sigmas)
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["WanMoEScheduler"]()
    secure = _secure()
    original_model = FakeModel()
    expected = pristine.find_and_apply_shift(
        original_model, scheduler, steps_high, steps_low, denoise, boundary,
        interval,
    )
    assert original_model.current is original_model.original

    async def run():
        refs = _sdk.InProcessRefResolver()
        model_value = FakeModel()
        model_ref = _sdk.ModelRef._wrap(await refs.create("MODEL", model_value))
        plan = _sdk.ExecutionPlan(
            prompt_id="wanmoe-in-process",
            node_id="1",
            node_type=secure.WanMoEScheduler.__name__,
            permissions=(),
        )
        with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()):
            result = await secure.WanMoEScheduler.execute(
                model_ref, scheduler, steps_high, steps_low, boundary,
                interval, denoise,
            )
        values = [*result.result[:4]]
        values.extend([await refs.resolve(ref) for ref in result.result[4:]])
        assert model_value.current is model_value.original
        return values

    actual = asyncio.run(run())
    assert actual[:4] == list(expected[:4])
    for converted, legacy in zip(actual[4:], expected[4:]):
        assert torch.equal(converted, legacy)


def test_real_guest_uses_host_schedule_and_returns_opaque_refs(monkeypatch):
    import comfy.samplers

    monkeypatch.setattr(comfy.samplers, "calculate_sigmas", _fake_calculate_sigmas)
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        model = FakeModel()
        model_ref = _sdk.ModelRef._wrap(await refs.create("MODEL", model))
        plan = _sdk.ExecutionPlan(
            prompt_id="wanmoe-guest",
            node_id="1",
            node_type=secure.WanMoEScheduler.__name__,
            tier="sandbox",
            node_module=secure.WanMoEScheduler.__module__,
            inputs={
                "model": model_ref,
                "scheduler": "normal",
                "steps_high": 4,
                "steps_low": 4,
                "boundary": 0.55,
                "interval": 1.0,
                "denoise": 1.0,
            },
            permissions=(),
            method="execute",
        )
        session = await GuestSession("wanmoe-conversion", guest_runtime_root=V2).start()
        try:
            result = await session.execute(plan, _runtime(plan, refs), capabilities=())
            shift, steps, high_steps, low_steps, full, high, low = result.result
            assert (shift, steps, high_steps, low_steps) == (6.0, 8, 4, 4)
            assert torch.equal(await refs.resolve(high), (await refs.resolve(full))[:5])
            assert torch.equal(await refs.resolve(low), (await refs.resolve(full))[4:])
            assert session.last_guest_pid not in (None, os.getpid())
            assert model.current is model.original
        finally:
            await session.kill()

    asyncio.run(run())


def test_bounds_stubs_license_and_authority_are_exact():
    secure = _secure()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = (V2 / "nodes.py").read_text()
    assert "model.sampling_sigmas(" in source
    assert "found_sigmas.slice(" in source
    for forbidden in (
        "import torch", "import comfy", "model.model", "get_model_object",
        "add_object_patch", "folder_paths", "PromptServer", "open(",
        "requests", "aiohttp", "subprocess", "_from_raw", "from_value",
    ):
        assert forbidden not in source

    async def invalid():
        with pytest.raises(ZeroDivisionError, match="division by zero"):
            await secure.WanMoEScheduler.execute(
                None, "normal", 4, 4, 0.875, 0.01, 0.0,
            )

    asyncio.run(invalid())


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-wanmoescheduler" / "xa2d601a"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)

    def tree(root):
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts
        }

    assert tree(fresh / PACK.name / "v2") == tree(V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
