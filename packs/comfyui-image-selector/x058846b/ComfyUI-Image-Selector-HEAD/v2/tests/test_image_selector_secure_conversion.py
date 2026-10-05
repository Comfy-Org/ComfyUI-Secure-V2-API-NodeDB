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
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "058846b177626a226590d355a342ae8f364591ac"
COMFY_API_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
COMFY_API_PYI_SHA256 = "beb4d0f61b31d65df706ebfa5b4bc3f901cba061d32ba36a468d50dd92da244e"
PAIR = PACK_DB / "patches" / "comfyui-image-selector" / "x058846b" / (
    "comfyui-image-selector-x058846b"
)

for root in (BACKEND, CORE):
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


def _import_v2():
    return _import_package("_secure_image_selector_test", V2)


def _import_upstream():
    return _import_package("_upstream_image_selector_test", PACK)


def _generated_manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(
                node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs",
                    "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
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


def test_pinned_census_schema_and_manifest_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    upstream = _import_upstream()
    secure = _import_v2()
    expected = {
        "ImageSelector", "ImageDuplicator", "LatentSelector",
        "LatentDuplicator",
    }
    assert set(upstream.NODE_CLASS_MAPPINGS) == expected
    assert set(secure.NODE_CLASS_MAPPINGS) == expected
    assert not list(PACK.rglob("*.js"))
    assert not list(PACK.rglob("*_routes.py"))

    expected_schemas = {
        "ImageSelector": ("image", (("images", "IMAGE"),
                                     ("selected_indexes", "STRING")), "IMAGE"),
        "ImageDuplicator": ("image", (("images", "IMAGE"),
                                       ("dup_times", "INT")), "IMAGE"),
        "LatentSelector": ("latent", (("latent_image", "LATENT"),
                                       ("selected_indexes", "STRING")), "LATENT"),
        "LatentDuplicator": ("latent", (("latent_image", "LATENT"),
                                         ("dup_times", "INT")), "LATENT"),
    }
    for node_id, node in secure.NODE_CLASS_MAPPINGS.items():
        schema = node.GET_SCHEMA()
        category, inputs, output_type = expected_schemas[node_id]
        assert schema.node_id == schema.display_name == node_id
        assert schema.category == category
        assert tuple((item.id, item.io_type) for item in schema.inputs) == inputs
        assert [item.io_type for item in schema.outputs] == [output_type]
        assert node.SDK_REFS is True and node.SDK_PERMISSIONS == ()
        if node_id.endswith("Selector"):
            selector = schema.inputs[1]
            assert selector.default == "1,2,3" and selector.multiline is False
        else:
            amount = schema.inputs[1]
            assert (amount.default, amount.min, amount.max, amount.step) == (
                2, 1, 16, 1,
            )

    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(secure))
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.image_selector_secure_test")
    assert set(loaded.node_mappings) == expected
    assert loaded.web_directory is None
    assert loaded.frontend_permissions == frozenset()


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1,3,5", [0, 2, 4]),
        ("1:4", [0, 1, 2]),
        (":3", [0, 1]),
        ("3:", [2, 3, 4]),
        ("1,1", [0, 0]),
        ("0,-1", [4, 3]),
        ("bad,2:nope,4", [3]),
        ("4:2", []),
    ],
)
def test_selector_parser_matches_upstream(expression, expected):
    secure = _import_v2()
    module = sys.modules[secure.ImageSelector.__module__]
    assert module._parse_indices(expression, 5) == expected

    upstream = _import_upstream()
    images = torch.arange(5 * 2 * 3 * 3).reshape(5, 2, 3, 3)
    upstream_result = upstream.ImageSelector().run(images, expression)[0]
    secure_result = images if not expected else images[expected]
    assert torch.equal(secure_result, upstream_result)


def test_selector_parser_bounds_and_legacy_negative_failure():
    secure = _import_v2()
    parser = sys.modules[secure.ImageSelector.__module__]._parse_indices
    with pytest.raises(ValueError, match="too large"):
        parser("1" * 65_537, 4)
    with pytest.raises(IndexError, match="out of range"):
        parser("-5", 4)


def test_all_four_nodes_execute_in_isolated_guest_with_exact_order():
    secure = _import_v2()

    async def run():
        refs = _sdk.InProcessRefResolver()
        ops = _sdk.InProcessOps()
        images = torch.arange(4 * 2 * 3 * 3).reshape(4, 2, 3, 3)
        latent_value = {
            "samples": torch.arange(4 * 2 * 2 * 3).reshape(4, 2, 2, 3),
            "noise_mask": torch.arange(4 * 2 * 3).reshape(4, 2, 3),
            "batch_index": [10, 11, 12, 13],
            "stable": "metadata",
        }
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", images))
        latent_ref = _sdk.LatentRef._wrap(await refs.create(
            "LATENT", latent_value))
        session = await GuestSession(
            "image-selector-pack", guest_runtime_root=V2).start()
        outputs = {}
        try:
            cases = (
                ("ImageSelector", {
                    "images": image_ref, "selected_indexes": "1,3:5,1"}),
                ("ImageDuplicator", {
                    "images": image_ref, "dup_times": 2}),
                ("LatentSelector", {
                    "latent_image": latent_ref,
                    "selected_indexes": "0,2,2"}),
                ("LatentDuplicator", {
                    "latent_image": latent_ref, "dup_times": 2}),
            )
            for number, (node_id, inputs) in enumerate(cases, 1):
                node = secure.NODE_CLASS_MAPPINGS[node_id]
                plan = _sdk.ExecutionPlan(
                    prompt_id="image-selector-test",
                    node_id=str(number),
                    node_type=node.__name__,
                    tier="sandbox",
                    node_module=node.__module__,
                    inputs=inputs,
                    permissions=(),
                )
                runtime = _sdk.Runtime(
                    refs=refs,
                    ctx=_sdk.InProcessCtxProvider().build(plan),
                    ops=ops,
                )
                result = await session.execute(plan, runtime, capabilities=())
                outputs[node_id] = await refs.resolve(result.result[0])
            return outputs, images, latent_value, session.last_guest_pid
        finally:
            await session.kill()

    outputs, images, latent, guest_pid = asyncio.run(run())
    assert guest_pid not in (None, os.getpid())
    assert torch.equal(outputs["ImageSelector"], images[[0, 2, 3, 0]])
    assert torch.equal(outputs["ImageDuplicator"], images.repeat(2, 1, 1, 1))
    selected = outputs["LatentSelector"]
    assert torch.equal(selected["samples"], latent["samples"][[3, 1, 1]])
    assert torch.equal(selected["noise_mask"], latent["noise_mask"][[3, 1, 1]])
    assert selected["batch_index"] == [13, 11, 11]
    assert selected["stable"] == "metadata"
    repeated = outputs["LatentDuplicator"]
    assert torch.equal(repeated["samples"], latent["samples"].repeat(2, 1, 1, 1))
    assert repeated["stable"] == "metadata"


def test_empty_selection_is_identity_and_stub_contract_is_current():
    secure = _import_v2()

    class _Image:
        async def batch_size(self):
            return 3

        async def select_batch(self, _indices):
            raise AssertionError("empty selection must not call host operation")

    class _Latent(_Image):
        pass

    async def run():
        image = _Image()
        latent = _Latent()
        image_output = await secure.ImageSelector.execute(image, "bad,4:2")
        latent_output = await secure.LatentSelector.execute(latent, "bad,4:2")
        return image, latent, image_output.result[0], latent_output.result[0]

    image, latent, image_output, latent_output = asyncio.run(run())
    assert image_output is image
    assert latent_output is latent
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_SHA256)
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256)
    source = (V2 / "nodes.py").read_text()
    for forbidden in (".raw()", "import torch", "folder_paths", "PromptServer"):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest = json.loads(PAIR.with_suffix(".json").read_text())
    diff_text = PAIR.with_suffix(".diff").read_bytes().decode("utf-8")
    fresh = tmp_path / "comfyui-image-selector" / "x058846b"
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
