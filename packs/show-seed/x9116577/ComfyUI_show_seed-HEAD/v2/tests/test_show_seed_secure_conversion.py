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
COMMIT = "9116577f49444ce33e9cd091da71d445dd12e1a9"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/show-seed/x9116577/show-seed-x9116577"

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
    return _import_package("_secure_show_seed_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_show_seed_test", root)


def _manifest(pack):
    node = pack.NODE_CLASS_MAPPINGS["Show Seed"]
    return {
        "format": FORMAT,
        "nodes": {
            "Show Seed": {
                "module": "node",
                "class": "ShowSeed",
                "sdk_refs": True,
                "permissions": [],
                "methods": {
                    name: name in node.__dict__
                    for name in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")
                },
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
    }


def test_census_schema_manifest_and_authority_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"Show Seed"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"Show Seed"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    node = secure.ShowSeed
    schema = node.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "Show Seed", "Show Seed", "image",
    )
    assert [(item.id, item.io_type) for item in schema.inputs] == [("images", "IMAGE")]
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        ("images", "IMAGE"), ("seed_info", "STRING"),
    ]
    assert [item.value for item in schema.hidden] == ["PROMPT"]
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.show_seed_secure_test")
    assert set(loaded.node_mappings) == {"Show Seed"}
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


@pytest.mark.parametrize("prompt", [
    None,
    {},
    {"1": {"class_type": "KSampler", "inputs": {"seed": 123}}},
    {"a": {"class_type": "Other", "inputs": {"seed": 1}},
     "b": {"class_type": "KSamplerAdvanced", "inputs": {"seed": 987654321}}},
    ("ignored", {"x": {"class_type": "KSampler", "inputs": {"seed": 0}}}),
    {"x": {"class_type": "NotKSamplerButContainsKSampler", "inputs": {"seed": "widget"}}},
    {"x": {"class_type": "KSampler", "inputs": {}}},
])
def test_prompt_seed_extraction_matches_pristine(tmp_path, prompt):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["Show Seed"]()
    secure = _secure().ShowSeed
    image = object()
    expected = pristine.process(image, prompt)
    actual = secure.execute(image, prompt).result
    assert actual == expected
    assert actual[0] is image


def test_first_matching_sampler_wins(tmp_path):
    prompt = {
        "1": {"class_type": "KSampler", "inputs": {"seed": 11}},
        "2": {"class_type": "KSamplerAdvanced", "inputs": {"seed": 22}},
    }
    assert _pristine(tmp_path).NODE_CLASS_MAPPINGS["Show Seed"]().extract_seed(prompt) == 11
    assert _secure().ShowSeed.extract_seed(prompt) == 11


def test_real_guest_preserves_opaque_image_identity_and_seed_text():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = torch.rand((2, 9, 13, 3))
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
        prompt = {
            "sampler": {"class_type": "KSamplerAdvanced", "inputs": {"seed": 404}},
        }
        plan = _sdk.ExecutionPlan(
            prompt_id="show-seed", node_id="1", node_type=secure.ShowSeed.__name__,
            tier="sandbox", node_module=secure.ShowSeed.__module__,
            inputs={"images": image_ref, "prompt": prompt}, permissions=(), method="execute",
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps(),
        )
        session = await GuestSession("show-seed-conversion", guest_runtime_root=V2).start()
        try:
            result = await session.execute(plan, runtime, capabilities=())
            assert result.result == (image_ref, "Seed: 404")
            assert await refs.resolve(result.result[0]) is image
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_contract_assets_and_source_boundary_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    for relative in ("README.md", "example/workflow.png"):
        assert (V2 / relative).read_bytes() == (PACK / relative).read_bytes()
    assert not (PACK / "LICENSE").exists()
    assert not (V2 / "LICENSE").exists()
    source = (V2 / "node.py").read_text()
    for forbidden in (
        ".raw()", "import torch", "folder_paths", "PromptServer", "requests",
        "aiohttp", "subprocess", "open(", "ctx()",
    ):
        assert forbidden not in source


def test_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "show-seed" / "x9116577"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
