from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
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
COMMIT = "08d2b3a08e65e3bb8f334e65a073f852a817bd57"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/comfyui-custom-switch/x08d2b3a/comfyui-custom-switch-x08d2b3a"

for root in (COMFYUI, BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


NODE_IDS = (
    "OrchestratorNodeToogle",
    "OrchestratorNodeMuter",
    "OrchestratorNodeGroupBypasser",
    "OrchestratorNodeGroupMuter",
    "AutomaticImageSwitcher",
)


def _import_package(name: str, root: pathlib.Path):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_custom_switch_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_custom_switch_test", root)


def _plan(node, inputs, permissions=()):
    return _sdk.ExecutionPlan(
        prompt_id="custom-switch", node_id="1", node_type=node.__name__,
        tier="sandbox", node_module=node.__module__, inputs=inputs,
        input_mode="values", permissions=permissions, method="execute",
    )


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node in pack.NODE_CLASS_MAPPINGS.items():
        nodes[node_id] = {
            "class": node.__name__,
            "methods": {
                name: name in node.__dict__
                for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")
            },
            "module": "nodes",
            "permissions": list(node.SDK_PERMISSIONS),
            "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            "sdk_refs": node.SDK_REFS,
        }
    return {
        "format": FORMAT,
        "frontend_permissions": [],
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(root.rglob("*"))
        if item.is_file() and not any(
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in item.relative_to(root).parts
        )
    }


def test_census_schemas_and_manifest_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert tuple(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert tuple(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pristine.WEB_DIRECTORY == "./js"
    assert secure.WEB_DIRECTORY == "./web"
    assert sum(path.read_text().count("app.registerExtension(") for path in (PACK / "js").glob("*.js")) == 4

    for node_id in NODE_IDS[:4]:
        old = pristine.NODE_CLASS_MAPPINGS[node_id]
        new = secure.NODE_CLASS_MAPPINGS[node_id]
        schema = new.GET_SCHEMA()
        assert schema.node_id == node_id
        assert schema.display_name == pristine.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert schema.category == old.CATEGORY == "Logic"
        assert schema.inputs == []
        assert schema.outputs == []
        assert schema.is_output_node is True
        assert new.SDK_REFS is False
        assert new.SDK_PERMISSIONS == ()

    old = pristine.NODE_CLASS_MAPPINGS["AutomaticImageSwitcher"]
    new = secure.NODE_CLASS_MAPPINGS["AutomaticImageSwitcher"]
    schema = new.GET_SCHEMA()
    assert schema.node_id == "AutomaticImageSwitcher"
    assert schema.display_name == pristine.NODE_DISPLAY_NAME_MAPPINGS["AutomaticImageSwitcher"]
    assert schema.category == old.CATEGORY == "Logic"
    assert [item.id for item in schema.inputs] == ["image_1", "image_2", "image_3"]
    assert all(item.optional for item in schema.inputs)
    assert [item.io_type for item in schema.inputs] == ["IMAGE", "IMAGE", "IMAGE"]
    assert [item.io_type for item in schema.outputs] == ["IMAGE"]
    assert new.SDK_REFS is False
    assert new.SDK_PERMISSIONS == ("raw",)

    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.custom_switch_secure_test")
    assert set(loaded.node_mappings) == set(NODE_IDS)
    assert loaded.web_directory == V2 / "web"
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


def test_backend_behavior_matches_pristine(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    for node_id in NODE_IDS[:4]:
        old = pristine.NODE_CLASS_MAPPINGS[node_id]().do_nothing()
        new = secure.NODE_CLASS_MAPPINGS[node_id].execute().result
        assert old == ()
        assert new is None

    images = [
        torch.full((1, 2, 3, 3), 0.1),
        torch.full((1, 2, 3, 3), 0.2),
        torch.full((1, 2, 3, 3), 0.3),
    ]
    old_node = pristine.NODE_CLASS_MAPPINGS["AutomaticImageSwitcher"]()
    new_node = secure.NODE_CLASS_MAPPINGS["AutomaticImageSwitcher"]
    for args in (
        (images[0], images[1], images[2]),
        (None, images[1], images[2]),
        (None, None, images[2]),
        (None, None, None),
    ):
        old = old_node.switch_image(*args)[0]
        new = new_node.execute(*args).result[0]
        assert torch.equal(new, old)
        if args[0] is not None:
            assert new is args[0]
        elif args[1] is not None:
            assert new is args[1]
        elif args[2] is not None:
            assert new is args[2]
        else:
            assert tuple(new.shape) == (1, 64, 64, 3)
            assert new.dtype == torch.float32


def test_real_isolated_guest_and_raw_denial():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession("custom-switch", guest_runtime_root=V2).start()
        try:
            noop = secure.NODE_CLASS_MAPPINGS["OrchestratorNodeToogle"]
            plan = _plan(noop, {})
            result = await session.execute(plan, _runtime(plan, refs), capabilities=())
            assert result.result is None

            image = torch.linspace(0, 1, 18).reshape(1, 2, 3, 3)
            image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
            switch = secure.NODE_CLASS_MAPPINGS["AutomaticImageSwitcher"]
            switch_plan = _plan(
                switch,
                {"image_1": None, "image_2": image_ref, "image_3": None},
                ("raw",),
            )
            result = await session.execute(
                switch_plan, _runtime(switch_plan, refs), capabilities=("raw",),
            )
            output = await refs.resolve(result.result[0])
            assert torch.equal(output, image)
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(
                    switch_plan, _runtime(switch_plan, refs), capabilities=(),
                )
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_security_and_typecheck():
    source = (V2 / "web/main.js").read_text()
    for forbidden in (
        "/scripts/app.js", "app.registerExtension", "LiteGraph", "addWidget",
        "localStorage", "sessionStorage", "document.", "window.", "fetch(",
        "_nodes", "_groups", "setDirtyCanvas", "innerHTML",
    ):
        assert forbidden not in source
    commands = (
        ["node", "--experimental-vm-modules", str(V2 / "tests/custom_switch_frontend_harness.mjs"), str(V2 / "web/main.js")],
        ["node", "--check", str(V2 / "web/main.js")],
        [str(pathlib.Path("/Users/ben/comfy/ComfyUI_frontend-secure-nodes/node_modules/.bin/tsc")), "--project", str(V2 / "tsconfig.json")],
    )
    for command in commands:
        completed = subprocess.run(command, cwd=V2, text=True, capture_output=True, timeout=60, check=False)
        assert completed.returncode == 0, completed.stdout + completed.stderr


def test_contract_assets_and_authority_boundary_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    for relative in ("README.md", "LICENSE", ".github/workflows/publish.yml"):
        assert (V2 / relative).read_bytes() == (PACK / relative).read_bytes()
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests", "aiohttp",
        "subprocess", "open(", "_from_raw",
    ):
        assert forbidden not in source


def test_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-custom-switch/x08d2b3a"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
