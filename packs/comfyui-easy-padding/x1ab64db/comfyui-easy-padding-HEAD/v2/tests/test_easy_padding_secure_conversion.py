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
COMMIT = "1ab64dbce7420fc09400cfe7d5563a42e4250f7d"
NODE_ID = "comfyui-easy-padding"
PAIR = PACK_DB / "patches/comfyui-easy-padding/x1ab64db/comfyui-easy-padding-x1ab64db"
for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession


def _load(name, root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load("_easy_padding_secure", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _load("_easy_padding_pristine", root)


def _manifest(module):
    node = module.AddPadding
    return {
        "format": FORMAT,
        "nodes": {
            NODE_ID: {
                "class": "AddPadding",
                "module": "nodes",
                "permissions": ["raw"],
                "sdk_refs": False,
                "methods": {
                    name: name in node.__dict__
                    for name in (
                        "check_lazy_status",
                        "fingerprint_inputs",
                        "validate_inputs",
                    )
                },
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
    }


def _image(channels=3, batch=1, dtype=torch.float32):
    return torch.linspace(-0.2, 1.2, batch * 8 * 10 * channels, dtype=dtype).reshape(
        batch, 8, 10, channels
    )


def _inputs(**overrides):
    values = {
        "image": _image(),
        "left": 2,
        "top": 3,
        "right": 4,
        "bottom": 1,
        "color": "#12abEF",
        "transparent": False,
    }
    values.update(overrides)
    return values


def _equal(actual, expected):
    assert len(actual) == len(expected) == 2
    for a, b in zip(actual, expected):
        assert a.dtype == b.dtype == torch.float32
        assert a.shape == b.shape
        assert a.device == b.device == torch.device("cpu")
        assert torch.equal(a, b)


def test_actual_registration_schema_and_manifest(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(old, "WEB_DIRECTORY") and not list(PACK.rglob("*.js"))
    assert len(asyncio.run(asyncio.run(new.comfy_entrypoint()).get_node_list())) == 1
    schema = new.AddPadding.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == NODE_ID
    assert schema.display_name == "ComfyUI Easy Padding"
    assert schema.category == old.NODE_CLASS_MAPPINGS[NODE_ID].CATEGORY
    expected = old.NODE_CLASS_MAPPINGS[NODE_ID].INPUT_TYPES()["required"]
    assert [i.id for i in schema.inputs] == list(expected)
    for item in schema.inputs[1:5]:
        attrs = expected[item.id][1]
        assert (item.default, item.min, item.max, item.step) == tuple(
            attrs[k] for k in ("default", "min", "max", "step")
        )
    assert schema.inputs[5].default == "#ffffff"
    assert schema.inputs[6].default is False
    assert tuple(i.io_type for i in schema.outputs) == ("IMAGE", "MASK")
    assert all(i.display_name is None for i in schema.outputs)
    assert new.AddPadding.SDK_REFS is False
    assert new.AddPadding.SDK_PERMISSIONS == ("raw",)
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(new)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.easy_padding_schema")
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.web_directory is None


@pytest.mark.parametrize("channels", [3, 4])
@pytest.mark.parametrize("batch", [1, 3])
@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("padding", [(0, 0, 0, 0), (1, 2, 3, 4), (5, 0, 0, 2)])
def test_full_padding_differential(
    tmp_path, channels, batch, dtype, transparent, padding
):
    values = _inputs(
        image=_image(channels, batch, dtype),
        transparent=transparent,
        **dict(zip(("left", "top", "right", "bottom"), padding)),
    )
    old = _pristine(tmp_path).NODE_CLASS_MAPPINGS[NODE_ID]()
    expected = old.resize(**values)
    actual = _secure().AddPadding.execute(**values).result
    _equal(actual, expected)
    assert actual[0].shape[-1] == (4 if transparent else 3)
    assert actual[1].ndim == 3


@pytest.mark.parametrize(
    "color",
    ["ffffff", "#000000", "##abCD12##", "#abcdef", "#ff00", "#gghhii", "", "#12345678"],
)
@pytest.mark.parametrize("transparent", [False, True])
def test_exact_color_parsing_and_error_or_bypass(tmp_path, color, transparent):
    values = _inputs(color=color, transparent=transparent)
    old = _pristine(tmp_path).NODE_CLASS_MAPPINGS[NODE_ID]()
    try:
        expected = old.resize(**values)
    except (ValueError, TypeError) as error:
        with pytest.raises(type(error)):
            _secure().AddPadding.execute(**values)
    else:
        _equal(_secure().AddPadding.execute(**values).result, expected)


def test_inclusive_mask_edge_quantization_and_input_rng_isolation():
    new = _secure().AddPadding
    values = _inputs(image=torch.ones((1, 8, 10, 3)) * 0.5)
    before = values["image"].clone()
    rng = torch.random.get_rng_state().clone()
    first = new.execute(**values).result
    _equal(first, new.execute(**values).result)
    assert float(first[0][0, 3, 2, 0]) == pytest.approx(127 / 255)
    # Pillow's rectangle endpoint is inclusive, including one extra right/bottom pixel.
    assert first[1][0, 11, 12] == 0
    assert first[1][0, 11, 13] == 1
    assert torch.equal(before, values["image"])
    assert torch.equal(rng, torch.random.get_rng_state())


@pytest.mark.parametrize(
    "override",
    [
        {"image": "bad"},
        {"image": torch.empty((0, 8, 10, 3))},
        {"image": torch.zeros((65, 8, 10, 3))},
        {"image": torch.zeros((1, 8, 10, 2))},
        {"image": torch.zeros((1, 1, 10, 3))},
        {"image": torch.zeros((8, 10, 3))},
        {"image": torch.ones((1, 8, 10, 3), dtype=torch.int32)},
        {"image": torch.full((1, 8, 10, 3), float("nan"))},
        {"left": True},
        {"left": -1},
        {"top": 4097},
        {"bottom": 0.5},
        {"color": None},
        {"color": "a" * 65},
        {"transparent": 1},
    ],
)
def test_malformed_inputs_fail_closed(override):
    with pytest.raises((ValueError, TypeError)):
        _secure().AddPadding.execute(**_inputs(**override))


def test_resource_bounds_reject_before_pillow(monkeypatch):
    module = _secure().nodes

    def forbidden(*args, **kwargs):
        raise AssertionError("algorithm must not run")

    monkeypatch.setattr(module._LegacyPadding, "resize", forbidden)
    with pytest.raises(ValueError, match="dimensions"):
        module.AddPadding.execute(**_inputs(left=4096, right=4096))
    monkeypatch.setattr(module, "MAX_PIXELS", 100)
    with pytest.raises(ValueError, match="pixel"):
        module.AddPadding.execute(**_inputs())


@pytest.mark.parametrize("transparent", [False, True])
def test_real_guest_raw_denial_and_outer_image_mask_types(transparent):
    module = _secure()
    node = module.AddPadding
    values = _inputs(image=_image(4, 2), transparent=transparent)
    expected = node.execute(**values).result

    async def run():
        refs = _sdk.InProcessRefResolver()
        wrapped = dict(values)
        wrapped["image"] = _sdk.ImageRef._wrap(
            await refs.create("IMAGE", values["image"])
        )
        plan = _sdk.ExecutionPlan(
            prompt_id="easy-padding",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs=wrapped,
            input_mode="values",
            permissions=("raw",),
            method="execute",
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession("easy-padding", guest_runtime_root=V2).start()
        try:
            result = await session.execute(plan, runtime, capabilities=("raw",))
            actual = [await refs.resolve(ref) for ref in result.result]
            _equal(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
        finally:
            await session.kill()

        loaded = packdb.load_pack(
            SNAPSHOT, mount_name=f"custom_nodes.easy_padding_outer_{transparent}"
        )
        outer_node = loaded.node_mappings[NODE_ID]
        assert tuple(outer_node.RETURN_TYPES) == ("IMAGE", "MASK")
        previous = _sdk.providers.execution_backend

        class Backend:
            session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "easy-padding-outer", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            results = await execution._async_map_node_over_list(
                prompt_id="easy-padding-outer",
                unique_id="1",
                obj=outer_node,
                input_data_all={k: [v] for k, v in values.items()},
                func=outer_node.FUNCTION,
                v3_data=None,
            )
            _equal(results[0].result, expected)
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session is not None:
                await backend.session.kill()

    asyncio.run(run())


def test_source_contract_and_license_boundary():
    assert (PACK / "node.py").read_bytes() == (V2 / "algorithm.py").read_bytes()
    assert (PACK / "LICENCE").read_bytes() == (V2 / "LICENCE").read_bytes()
    assert (
        hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest()
        == "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
    )
    assert (
        hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest()
        == "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
    )
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    sources = "\n".join(
        (V2 / f).read_text() for f in ("nodes.py", "algorithm.py", "__init__.py")
    )
    for forbidden in (
        "folder_paths",
        "PromptServer",
        "subprocess",
        "requests",
        "_from_raw",
        "open(",
        "comfy.model_management",
    ):
        assert forbidden not in sources
    assert (
        len(
            [
                p
                for p in PACK.rglob("*")
                if p.is_file() and "v2" not in p.relative_to(PACK).parts
            ]
        )
        == 11
    )


def test_exact_patch_pair_and_tree_roundtrip(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes() == diff.encode()
    fresh = tmp_path / "comfyui-easy-padding/x1ab64db"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)


def test_cache_hygiene():
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))


if __name__ == "__main__":
    (V2 / "secure-nodes.json").write_text(
        json.dumps(_manifest(_secure()), indent=2, sort_keys=True) + "\n"
    )
