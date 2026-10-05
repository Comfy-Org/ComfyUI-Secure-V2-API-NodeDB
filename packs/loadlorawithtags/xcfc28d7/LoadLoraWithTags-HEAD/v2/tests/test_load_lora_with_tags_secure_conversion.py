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

sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "cfc28d70e362695b001854172013bf643e851313"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/loadlorawithtags/xcfc28d7/loadlorawithtags-xcfc28d7"

for root in (BACKEND, BACKEND / "tests", CORE):
    sys.path.insert(0, str(root))
sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch, storage  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402
from integrations_double import IntegrationsDouble  # noqa: E402


def _import(name: str, root: pathlib.Path):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(
        name,
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _import("_secure_load_lora_tags_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import("_pristine_load_lora_tags_test", root)


def _manifest(pack):
    node = pack.LoraLoaderTagsQuery
    return {
        "format": FORMAT,
        "nodes": {
            "LoraLoaderTagsQuery": {
                "module": "nodes",
                "class": "LoraLoaderTagsQuery",
                "sdk_refs": True,
                "permissions": ["assets", "integrations.civitai", "storage"],
                "methods": {
                    name: name in node.__dict__
                    for name in (
                        "validate_inputs",
                        "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
    }


class _Storage:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.calls = []

    async def get(self, key):
        self.calls.append(("get", key))
        return self.values.get(key)

    async def set(self, key, value):
        self.calls.append(("set", key, value))
        self.values[key] = value


class _AssetsUnit:
    def __init__(self):
        self.calls = []
        self.asset = object()

    async def resolve(self, folder, name):
        self.calls.append(("resolve", folder, name))
        return self.asset

    async def digest(self, asset, algorithm="sha256"):
        self.calls.append(("digest", asset, algorithm))
        return "a" * 64


class _IntegrationsUnit:
    def __init__(self, words=None, error=None):
        self.words = ["alpha", "beta"] if words is None else words
        self.error = error
        self.calls = []

    async def call(self, integration, operation, **params):
        self.calls.append((integration, operation, params))
        if self.error is not None:
            raise self.error
        return {"trainedWords": self.words}


class _Context:
    def __init__(self, *, cached=None, words=None, error=None):
        self.storage = _Storage(cached)
        self.assets = _AssetsUnit()
        self.integrations = _IntegrationsUnit(words, error)


class _Model:
    def __init__(self):
        self.calls = []

    async def apply_lora(self, asset, clip, strength_model, strength_clip):
        self.calls.append((asset, clip, strength_model, strength_clip))
        return "patched-model", "patched-clip"


def _inputs(**overrides):
    values = {
        "model": _Model(),
        "clip": object(),
        "lora_name": "folder/demo.safetensors",
        "strength_model": 0.75,
        "strength_clip": -0.25,
        "query_tags": True,
        "tags_out": True,
        "print_tags": False,
        "bypass": False,
        "force_fetch": False,
        "opt_prompt": None,
    }
    values.update(overrides)
    return values


def _run(module, context, **overrides):
    module.nodes._ctx = lambda: context
    values = _inputs(**overrides)
    result = asyncio.run(module.LoraLoaderTagsQuery.execute(**values))
    return result.result, values


def test_census_schema_manifest_and_contract(tmp_path, monkeypatch):
    old, new = _pristine(tmp_path), _secure()
    legacy_class = old.NODE_CLASS_MAPPINGS["LoraLoaderTagsQuery"]
    monkeypatch.setattr(
        sys.modules[legacy_class.__module__].folder_paths,
        "get_filename_list",
        lambda folder: ["z.safetensors", "a.safetensors"],
    )
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert (
        set(old.NODE_CLASS_MAPPINGS)
        == set(new.NODE_CLASS_MAPPINGS)
        == {"LoraLoaderTagsQuery"}
    )
    assert not hasattr(old, "WEB_DIRECTORY") and not list(PACK.rglob("*.js"))
    legacy_groups = legacy_class.INPUT_TYPES()
    legacy = list(legacy_groups["required"].items()) + list(
        legacy_groups["optional"].items()
    )
    schema = new.LoraLoaderTagsQuery.GET_SCHEMA()
    schema.validate()
    assert [item.id for item in schema.inputs] == [name for name, _ in legacy]
    for item, (name, specification) in zip(schema.inputs, legacy, strict=True):
        legacy_type = specification[0]
        options = specification[1] if len(specification) > 1 else {}
        assert item.id == name
        assert item.optional == (name == "opt_prompt")
        if name == "lora_name":
            assert item.io_type == "COMBO"
            assert item.options == []
            assert item.remote.route == "/models/loras"
            assert item.remote.refresh_button is True
        else:
            assert item.io_type == legacy_type
        for attribute in ("default", "min", "max", "step", "forceInput"):
            if attribute not in options:
                continue
            field = "force_input" if attribute == "forceInput" else attribute
            assert getattr(item, field) == options[attribute]
    assert [item.io_type for item in schema.outputs] == list(
        legacy_class.RETURN_TYPES
    )
    assert [item.display_name for item in schema.outputs] == list(
        legacy_class.RETURN_TYPES
    )
    assert schema.category == legacy_class.CATEGORY
    assert new.LoraLoaderTagsQuery.SDK_REFS is True
    assert new.LoraLoaderTagsQuery.SDK_PERMISSIONS == (
        "assets",
        "integrations.civitai",
        "storage",
    )
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(new)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.load_lora_with_tags_test"
    )
    assert set(loaded.node_mappings) == {"LoraLoaderTagsQuery"}
    assert not loaded.routes and loaded.frontend_permissions == frozenset()


@pytest.mark.parametrize(
    ("strength_model", "strength_clip", "bypass", "prompt", "expected"),
    (
        (0.0, 0.0, False, None, ""),
        (0.0, 0.0, False, "prompt", "prompt"),
        (1.0, 1.0, True, None, ""),
        (1.0, 1.0, True, "prompt", "prompt"),
    ),
)
def test_bypass_and_zero_strength_never_request_authority(
    strength_model, strength_clip, bypass, prompt, expected
):
    new = _secure()

    def forbidden():
        raise AssertionError("bypass must not request host authority")

    new.nodes._ctx = forbidden
    model, clip = _Model(), object()
    result = asyncio.run(
        new.LoraLoaderTagsQuery.execute(
            **_inputs(
                model=model,
                clip=clip,
                strength_model=strength_model,
                strength_clip=strength_clip,
                bypass=bypass,
                opt_prompt=prompt,
            )
        )
    ).result
    assert result == (model, clip, expected)
    assert not model.calls


def test_cached_tags_apply_without_network_and_preserve_prompt_rules(capsys):
    new = _secure()
    name = "folder/demo.safetensors"
    key = new.nodes._cache_key(name)
    context = _Context(cached={key: '["cached one","cached two"]'})
    result, values = _run(new, context, print_tags=True, opt_prompt="base")
    assert result == ("patched-model", "patched-clip", "base, cached one, cached two")
    assert values["model"].calls == [
        (context.assets.asset, values["clip"], 0.75, -0.25)
    ]
    assert not context.integrations.calls
    assert ("digest", context.assets.asset, "sha256") not in context.assets.calls
    assert "trainedWords: cached one, cached two" in capsys.readouterr().out

    result, _ = _run(new, context, opt_prompt="base", tags_out=False)
    assert result[2] == "base"


def test_query_false_does_not_fetch_but_force_fetch_replaces_cache():
    new = _secure()
    context = _Context(words=["fresh", "words"])
    result, _ = _run(new, context, query_tags=False)
    assert result[2] == ""
    assert not context.integrations.calls

    result, _ = _run(new, context, query_tags=False, force_fetch=True)
    assert result[2] == "fresh, words"
    assert context.integrations.calls == [
        (
            "civitai",
            "model_version_by_hash",
            {"hash_value": "a" * 64, "refresh": True},
        )
    ]
    written = [call for call in context.storage.calls if call[0] == "set"]
    assert json.loads(written[-1][2]) == ["fresh", "words"]


def test_empty_or_malformed_cache_refetches_and_tenants_are_isolated():
    new = _secure()
    key = new.nodes._cache_key("folder/demo.safetensors")
    first = _Context(cached={key: "not-json"}, words=["tenant-a"])
    second = _Context(cached={key: "[]"}, words=["tenant-b"])
    assert _run(new, first)[0][2] == "tenant-a"
    assert _run(new, second)[0][2] == "tenant-b"
    assert first.storage.values[key] != second.storage.values[key]


def test_vendor_outage_is_empty_but_authority_denial_is_fail_closed():
    new = _secure()
    outage = _Context(error=RuntimeError("vendor unavailable"))
    assert _run(new, outage)[0][2] == ""

    denied = _Context(
        error=PermissionError("capability integrations.civitai not granted")
    )
    with pytest.raises(PermissionError, match="integrations.civitai"):
        _run(new, denied)


@pytest.mark.parametrize(
    "name",
    ("", "../escape.safetensors", "/absolute.safetensors", "C:/escape.safetensors"),
)
def test_catalogue_names_are_confined_before_asset_access(name):
    new = _secure()
    context = _Context()
    with pytest.raises(ValueError, match="confined|traversal"):
        _run(new, context, lora_name=name)
    assert not context.assets.calls


def test_tag_projection_is_bounded_and_filters_invalid_values():
    new = _secure()
    tags = ["ok", 7, "bad\x00tag", "x" * (new.nodes._MAX_TAG_BYTES + 1)]
    tags.extend(f"tag-{index}" for index in range(new.nodes._MAX_TAGS + 20))
    bounded = new.nodes._bounded_tags(tags)
    assert bounded[0] == "ok"
    assert len(bounded) == new.nodes._MAX_TAGS - 3
    assert all(isinstance(tag, str) and "\x00" not in tag for tag in bounded)
    assert len(json.dumps(bounded).encode("utf-8")) <= new.nodes._MAX_CACHE_BYTES


class _AssetsGuest:
    def __init__(self, refs, root, records):
        self.refs = refs
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.paths = {}
        self.calls = []
        for name, data in records.items():
            path = self.root.joinpath(*name.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            self.paths[name] = path

    async def resolve(self, folder, name):
        self.calls.append(("resolve", folder, name))
        if folder != "loras" or name not in self.paths:
            raise FileNotFoundError(f"{folder}/{name}")
        return _sdk.AssetRef._wrap(
            await self.refs.create("ASSET", str(self.paths[name]))
        )

    async def digest(self, ref, algorithm="sha256"):
        assert algorithm == "sha256"
        path = pathlib.Path(await self.refs.resolve(ref))
        return hashlib.sha256(path.read_bytes()).hexdigest()


class _Civitai:
    def __init__(self):
        self.calls = []

    async def model_version_by_hash(self, hash_value, refresh=False):
        self.calls.append((hash_value, refresh))
        return {"trainedWords": ["civitai trigger", "second tag"]}


async def _resolve(value, refs):
    if isinstance(value, _sdk.Ref):
        return await refs.resolve(value)
    if isinstance(value, tuple):
        return tuple([await _resolve(item, refs) for item in value])
    return value


def test_real_guest_applies_lora_caches_tags_and_denies_capabilities(
    tmp_path, monkeypatch
):
    import comfy.sd
    import comfy.utils
    import folder_paths

    new = _secure()
    loads = []

    def load_torch_file(path, *, safe_load, return_metadata):
        loads.append((pathlib.Path(path), safe_load, return_metadata))
        return {"weight": 1}, {"source": "fixture"}

    def apply_lora(model, clip, state, strength_model, strength_clip, **kwargs):
        assert state == {"weight": 1}
        assert kwargs["lora_metadata"] == {"source": "fixture"}
        return ("patched-model", model), ("patched-clip", clip)

    monkeypatch.setattr(comfy.utils, "load_torch_file", load_torch_file)
    monkeypatch.setattr(comfy.sd, "load_lora_for_models", apply_lora)
    monkeypatch.setattr(storage, "_STORAGE", storage.PackStorage(tmp_path / "storage"))
    monkeypatch.setattr(
        folder_paths,
        "get_folder_paths",
        lambda folder: [str(tmp_path / "loras")] if folder == "loras" else [],
    )
    monkeypatch.setattr(
        folder_paths,
        "get_filename_list",
        lambda folder: ["folder/demo.safetensors"] if folder == "loras" else [],
    )

    async def run():
        refs = _sdk.InProcessRefResolver()
        assets = _AssetsGuest(
            refs,
            tmp_path / "loras",
            {"folder/demo.safetensors": b"safe fixture"},
        )
        civitai = _Civitai()
        source_model, source_clip = object(), object()
        model = _sdk.ModelRef._wrap(await refs.create("MODEL", source_model))
        clip = _sdk.ClipRef._wrap(await refs.create("CLIP", source_clip))
        node = new.LoraLoaderTagsQuery
        inputs = _inputs(model=model, clip=clip, force_fetch=True)
        plan = _sdk.ExecutionPlan(
            prompt_id="load-lora-tags",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs=inputs,
            permissions=node.SDK_PERMISSIONS,
            required_weights=(),
            method="execute",
        )
        context = _sdk.InProcessCtxProvider().build(plan)
        context.assets = assets
        context.integrations = IntegrationsDouble(civitai=civitai)
        runtime = _sdk.Runtime(refs=refs, ctx=context, ops=_sdk.InProcessOps())
        session = await GuestSession(
            "load-lora-with-tags", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(
                plan, runtime, capabilities=node.SDK_PERMISSIONS
            )
            values = await _resolve(result.result, refs)
            assert values == (
                ("patched-model", source_model),
                ("patched-clip", source_clip),
                "civitai trigger, second tag",
            )
            assert len(civitai.calls) == 1
            assert session.last_guest_pid not in (None, os.getpid())

            cached_inputs = {**inputs, "force_fetch": False}
            cached_plan = copy.copy(plan)
            cached_plan.inputs = cached_inputs
            cached = await session.execute(
                cached_plan, runtime, capabilities=node.SDK_PERMISSIONS
            )
            assert cached.result[2] == "civitai trigger, second tag"
            assert len(civitai.calls) == 1

            with pytest.raises(Exception, match="assets"):
                await session.execute(plan, runtime, capabilities=())
            with pytest.raises(Exception, match="storage"):
                await session.execute(
                    plan,
                    runtime,
                    capabilities=("assets", "integrations.civitai"),
                )
            with pytest.raises(Exception, match="integrations.civitai"):
                await session.execute(
                    plan,
                    runtime,
                    capabilities=("assets", "storage"),
                )
        finally:
            await session.kill()

    asyncio.run(run())
    assert loads and all(safe and metadata for _path, safe, metadata in loads)


def test_stubs_authority_patch_and_no_cache(tmp_path):
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy",
        "folder_paths",
        "requests",
        "subprocess",
        "open(",
        "assets.path",
        "_from_raw",
    ):
        assert forbidden not in source
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "loadlorawithtags" / "xcfc28d7"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
