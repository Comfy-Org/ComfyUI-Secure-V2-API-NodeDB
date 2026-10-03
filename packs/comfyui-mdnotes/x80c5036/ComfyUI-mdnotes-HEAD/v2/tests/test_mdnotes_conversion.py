from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "80c503631f15229c5a0437fe6eb244b4b98b9037"
COMFY_API_SHA256 = (
    "7f3e36c54f827ac69395c9574d2230b0639c6dd7964f95690017d79853cf72f1"
)
NODE_IDS = {
    "mdnotes_ckpt_name_list",
    "mdnotes_lora_name_list",
    "mdnotes_dfm_name_list",
}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402


def _import_v2():
    name = "_secure_mdnotes_conversion_test"
    sys.modules.pop(name, None)
    sys.modules.pop(f"{name}.nodes", None)
    spec = importlib.util.spec_from_file_location(
        name,
        V2 / "__init__.py",
        submodule_search_locations=[str(V2)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _tree(root: pathlib.Path, *, omit_v2: bool = False) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if omit_v2 and relative.parts[0] == "v2":
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"}
               for part in relative.parts):
            continue
        files[relative.as_posix()] = hashlib.sha256(
            path.read_bytes()).hexdigest()
    return files


def _generated_manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(
                getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs",
                    "fingerprint_inputs",
                    "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "frontend_permissions": [],
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def test_pinned_pristine_census_and_secure_runtime_census_are_exact():
    conversion = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in conversion

    tree = ast.parse((PACK / "__init__.py").read_text())
    upstream_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Attribute) and base.attr == "ComfyNode"
            for base in node.bases
        )
    }
    assert upstream_classes == {
        "CheckpointNameList", "LoraNameList", "DfmNameList",
    }
    assert (PACK / "src" / "main.ts").read_text().count(
        "comfyApp.registerExtension({") == 1

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == NODE_IDS
    assert pack.WEB_DIRECTORY == "web"

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.mdnotes_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_three_nodes_preserve_schema_and_passthrough_behavior():
    pack = _import_v2()
    expected = {
        "mdnotes_ckpt_name_list": (
            "Checkpoint Name List", "ckpt_name", "Checkpoint Names",
            "/models/checkpoints", "Checkpoint Name",
        ),
        "mdnotes_lora_name_list": (
            "Lora Name List", "lora_name", "Lora Names",
            "/models/loras", "Lora Name",
        ),
        "mdnotes_dfm_name_list": (
            "Diffusion Model Name List", "dfm_name",
            "Diffusion Model Names", "/models/diffusion_models",
            "Diffusion Model Name",
        ),
    }
    for node_id, details in expected.items():
        display, input_id, input_display, route, output_display = details
        node_class = pack.NODE_CLASS_MAPPINGS[node_id]
        schema = node_class.GET_SCHEMA()
        assert schema.node_id == node_id
        assert schema.display_name == display
        assert schema.category == "mdnotes"
        assert len(schema.inputs) == len(schema.outputs) == 1
        input_ = schema.inputs[0]
        assert input_.id == input_id
        assert input_.display_name == input_display
        assert input_.options == []
        assert input_.default == 0
        assert input_.remote.route == route
        assert input_.remote.refresh_button is True
        output = schema.outputs[0]
        assert output.id == "name_of_selected_model"
        assert output.display_name == output_display
        chosen = "nested/model.safetensors"
        assert node_class.execute(**{input_id: chosen}).result == (chosen,)
        assert node_class.SDK_REFS is True
        assert node_class.SDK_PERMISSIONS == ()


def test_manifest_is_fresh_and_frontend_is_worker_safe():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(pack))
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_SHA256
    )

    python_source = "\n".join(
        path.read_text(errors="replace")
        for path in sorted(V2.glob("*.py"))
    )
    for forbidden in (
        "import folder_paths",
        "from folder_paths",
        "import server",
        "from server",
        "PromptServer",
        "aiohttp",
        "subprocess",
    ):
        assert forbidden not in python_source

    frontend = (V2 / "web" / "main.js").read_text()
    assert "from '/comfy/api/v2.js'" in frontend
    assert "comfy.models.list" in frontend
    assert "comfy.models.readSidecar" in frontend
    assert "comfy.storage.get" in frontend
    assert "comfy.storage.set" in frontend
    assert "comfy.ui.showDialog" in frontend
    assert "comfy.backend" not in frontend
    assert "fetch(" not in frontend
    assert "window" not in frontend
    assert "document" not in frontend


def test_frontend_behavior_security_and_scoped_shortcuts():
    completed = subprocess.run(
        [
            "node",
            "--experimental-vm-modules",
            str(V2 / "tests" / "mdnotes_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (
        "PASS: MDNotes catalogued sidecars, private editing, safe modal UI"
        in completed.stdout
    )


def test_pristine_to_v2_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    fresh = tmp_path / "comfyui-mdnotes" / "x80c5036"
    fresh.mkdir(parents=True)
    shutil.copytree(
        PACK,
        fresh / PACK.name,
        ignore=shutil.ignore_patterns("v2"),
    )
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_do_not_dirty_pristine_or_v2_with_bytecode():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
