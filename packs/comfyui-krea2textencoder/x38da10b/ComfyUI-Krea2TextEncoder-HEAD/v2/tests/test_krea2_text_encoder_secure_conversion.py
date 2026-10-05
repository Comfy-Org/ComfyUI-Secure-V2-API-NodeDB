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
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "38da10b0d4655098d867c14af10093baa76a85c4"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "comfyui-krea2textencoder" / "x38da10b" / (
    "comfyui-krea2textencoder-x38da10b"
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


def _secure():
    return _import_package("_secure_krea2_text_test", V2)


def _upstream():
    return _import_package("_upstream_krea2_text_test", PACK)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "class": node_class.__name__,
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "check_lazy_status", "fingerprint_inputs", "validate_inputs",
                )
            },
            "module": "nodes",
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts)
    }


def test_census_schema_manifest_and_contract_are_exact():
    upstream = _upstream()
    secure = _secure()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {"TextEncodeKrea2", "Krea2SystemPrompt"}
    assert set(secure.NODE_CLASS_MAPPINGS) == set(upstream.NODE_CLASS_MAPPINGS)
    assert upstream.WEB_DIRECTORY == secure.WEB_DIRECTORY == "./web"
    assert len(list((PACK / "web").glob("*.js"))) == 1
    assert len(list((V2 / "web").glob("*.js"))) == 1
    extension = asyncio.run(secure.comfy_entrypoint())
    assert {node.GET_SCHEMA().node_id for node in asyncio.run(
        extension.get_node_list())} == set(secure.NODE_CLASS_MAPPINGS)

    encoder = secure.TextEncodeKrea2
    schema = encoder.GET_SCHEMA()
    assert encoder.SDK_REFS is True
    assert encoder.SDK_PERMISSIONS == ("raw",)
    assert schema.accept_all_inputs is True
    assert [item.id for item in schema.inputs] == [
        "clip", "prompt", "system_prompt", "image1", "mask1",
        "vision_megapixels", "mask_padding", "vision_position", "print_prompt",
    ]
    assert [item.io_type for item in schema.outputs] == ["CONDITIONING"]
    assert secure.Krea2SystemPrompt.GET_SCHEMA().outputs[0].display_name == "system_prompt"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.krea2_text_secure_test")
    assert set(loaded.node_mappings) == set(secure.NODE_CLASS_MAPPINGS)
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()


def test_wire_schema_matches_pinned_upstream_declarations():
    upstream = _upstream()
    secure = _secure()
    property_names = {
        "default": "default",
        "min": "min",
        "max": "max",
        "step": "step",
        "multiline": "multiline",
        "dynamicPrompts": "dynamic_prompts",
        "forceInput": "force_input",
        "tooltip": "tooltip",
    }
    for node_id, old_class in upstream.NODE_CLASS_MAPPINGS.items():
        new_schema = secure.NODE_CLASS_MAPPINGS[node_id].GET_SCHEMA()
        declared = old_class.INPUT_TYPES()
        expected_order = [
            name
            for group in ("required", "optional")
            for name in declared.get(group, {})
        ]
        assert [item.id for item in new_schema.inputs] == expected_order
        by_id = {item.id: item for item in new_schema.inputs}
        for group in ("required", "optional"):
            for name, spec in declared.get(group, {}).items():
                actual = by_id[name]
                old_type = spec[0]
                metadata = spec[1] if len(spec) > 1 else {}
                assert actual.io_type == ("COMBO" if isinstance(old_type, list) else old_type)
                assert actual.optional is (group == "optional")
                if isinstance(old_type, list):
                    assert actual.options == old_type
                for old_name, new_name in property_names.items():
                    if old_name in metadata:
                        assert getattr(actual, new_name) == metadata[old_name]
        assert new_schema.category == old_class.CATEGORY
        assert new_schema.description == old_class.DESCRIPTION
        assert [item.io_type for item in new_schema.outputs] == list(old_class.RETURN_TYPES)
        expected_names = list(getattr(old_class, "RETURN_NAMES", old_class.RETURN_TYPES))
        assert [item.display_name for item in new_schema.outputs] == expected_names


@pytest.mark.parametrize("shape", ((1, 20, 30, 3), (2, 72, 96, 4)))
@pytest.mark.parametrize("padding", (0.0, 0.1, 0.5))
def test_crop_resize_and_prompt_assembly_match_upstream(shape, padding):
    upstream = _upstream()
    secure = _secure()
    up = sys.modules[f"{upstream.__name__}.nodes"]
    new = sys.modules[f"{secure.__name__}.nodes"]
    image = torch.linspace(0, 1, int(torch.tensor(shape).prod())).reshape(shape)
    mask = torch.zeros((shape[0], shape[1] // 2, shape[2] // 2))
    mask[:, 2:-2, 3:-3] = 1
    expected = up.TextEncodeKrea2._prepare_vision(
        {"image1": image, "mask1": mask}, 0.1, padding)[0][0]
    actual = new.prepare_vision_tensor(image, mask, 0.1, padding)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    for position in ("before prompt", "after prompt"):
        assert new.build_text(" custom ", "prompt", "<image>", position) == (
            up.TextEncodeKrea2._build_text(" custom ", "prompt", "<image>", position)
        )


def test_empty_mask_and_small_reference_are_not_rescaled():
    upstream = _upstream()
    secure = _secure()
    up = sys.modules[f"{upstream.__name__}.nodes"]
    new = sys.modules[f"{secure.__name__}.nodes"]
    image = torch.rand(1, 7, 11, 4)
    mask = torch.zeros(1, 7, 11)
    expected = up.TextEncodeKrea2._prepare_vision(
        {"image1": image, "mask1": mask}, 8.0, 0.0)[0][0]
    actual = new.prepare_vision_tensor(image, mask, 8.0, 0.0)
    assert actual.shape == (1, 7, 11, 3)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)


def test_real_guest_keeps_tensor_tokens_host_side_and_matches_upstream():
    secure = _secure()
    upstream = _upstream()
    up = sys.modules[f"{upstream.__name__}.nodes"]
    calls = []

    class RecordingClip:
        def tokenize(self, text, **kwargs):
            calls.append(("tokenize", text, kwargs))
            return {"vision_tensor": torch.arange(6).reshape(1, 6)}

        def encode_from_tokens_scheduled(self, tokens):
            calls.append(("encode", tokens))
            return [[torch.ones((1, 2, 3)), {"tag": "host-only-tokens"}]]

    image1 = torch.rand(1, 18, 24, 4)
    mask1 = torch.zeros(1, 9, 12)
    mask1[:, 2:7, 3:10] = 1
    image2 = torch.rand(2, 10, 14, 3)

    async def run(capabilities=("raw",)):
        refs = _sdk.InProcessRefResolver()
        inputs = {
            "clip": _sdk.ClipRef._wrap(await refs.create("CLIP", RecordingClip())),
            "prompt": "paint this",
            "system_prompt": "custom system",
            "image1": _sdk.ImageRef._wrap(await refs.create("IMAGE", image1)),
            "mask1": _sdk.MaskRef._wrap(await refs.create("MASK", mask1)),
            "image2": _sdk.ImageRef._wrap(await refs.create("IMAGE", image2)),
            "vision_megapixels": 0.1,
            "mask_padding": 0.1,
            "vision_position": "after prompt",
            "print_prompt": False,
        }
        node = secure.TextEncodeKrea2
        plan = _sdk.ExecutionPlan(
            prompt_id="krea2-text", node_id="1", node_type="TextEncodeKrea2",
            tier="sandbox", node_module=node.__module__, inputs=inputs,
            permissions=node.SDK_PERMISSIONS,
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps())
        session = await GuestSession(
            "krea2-text-pack", guest_runtime_root=V2).start()
        try:
            result = await session.execute(plan, runtime, capabilities=capabilities)
            return await refs.resolve(result.result[0]), session.last_guest_pid
        finally:
            await session.kill()

    actual, pid = asyncio.run(run())
    expected_images, image_prompt = up.TextEncodeKrea2._prepare_vision(
        {"image1": image1, "mask1": mask1, "image2": image2}, 0.1, 0.1)
    expected_text, expected_template = up.TextEncodeKrea2._build_text(
        "custom system", "paint this", image_prompt, "after prompt")
    assert calls[0][0:2] == ("tokenize", expected_text)
    assert calls[0][2]["llama_template"] == expected_template
    assert len(calls[0][2]["images"]) == 2
    for got, want in zip(calls[0][2]["images"], expected_images):
        torch.testing.assert_close(got, want, rtol=0, atol=0)
    assert torch.equal(calls[1][1]["vision_tensor"], torch.arange(6).reshape(1, 6))
    assert actual[0][1]["tag"] == "host-only-tokens"
    assert pid not in (None, os.getpid())
    with pytest.raises(Exception, match="raw.*capability"):
        asyncio.run(run(capabilities=()))


def test_system_prompt_and_invalid_inputs_fail_closed():
    secure = _secure()
    result = secure.Krea2SystemPrompt.execute("hello")
    assert result.result == ("hello",)
    node = secure.TextEncodeKrea2

    class Dummy:
        async def encode(self, *_args, **_kwargs):
            return "conditioning"

    for kwargs in (
        {"vision_megapixels": 0.0},
        {"mask_padding": 2.0},
        {"vision_position": "middle"},
        {"print_prompt": 1},
        {"image17": object()},
        {"unrelated": object()},
    ):
        with pytest.raises((TypeError, ValueError)):
            asyncio.run(node.execute(Dummy(), "prompt", **kwargs))
    with pytest.raises(ValueError, match="too large"):
        asyncio.run(node.execute(Dummy(), "x" * (64 * 1024 + 1)))


def test_frontend_dynamic_pairs_and_security_contract():
    subprocess.run(
        ["node", str(V2 / "tests" / "krea2_text_frontend_harness.mjs")],
        check=True,
    )
    source = (V2 / "web" / "krea2_dynamic_images.js").read_text()
    for forbidden in (
        "window.", "document.", "globalThis.document", "fetch(",
        "app.", "registerExtension", "addDOMWidget", "setDirtyCanvas",
    ):
        assert forbidden not in source
    assert 'comfy.defs.extend("TextEncodeKrea2"' in source
    assert "node.inputs.add" in source
    assert "node.inputs.remove" in source


def test_backend_has_only_declared_raw_authority():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests",
        "subprocess", "open(", "os.", "sys.",
    ):
        assert forbidden not in source
    assert source.count('SDK_PERMISSIONS = ("raw",)') == 1
    assert "clip.encode(" in source
    assert "clip.tokenize(" not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-krea2textencoder" / "x38da10b"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_leave_no_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
