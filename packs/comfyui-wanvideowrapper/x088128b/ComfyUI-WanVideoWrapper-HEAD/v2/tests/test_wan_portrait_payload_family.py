"""Exact portrait payload composition, not portrait encoder/model inference."""
import ast
import asyncio
import importlib.util
import itertools
import os
from pathlib import Path
import shutil
import sys
import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = "/Users/ben/comfy/ComfyUI-secure-nodes"
BACKEND = "/Users/ben/comfy/ComfyUI_secure_nodes/backend"
for path in (CORE, BACKEND):
    sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packdb

ID = "WanVideoAddFantasyPortrait"


def source():
    tree = ast.parse((PACK/"fantasyportrait/nodes.py").read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == ID)
    namespace = {}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(PACK/"fantasyportrait/nodes.py"), "exec"), namespace)
    return namespace[ID]


def candidate(root=V2):
    name = "_wan_portrait_" + str(id(root))
    spec = importlib.util.spec_from_file_location(name, root/"__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]


class ModelSentinel:
    def __call__(self, *args, **kwargs):
        raise AssertionError("No portrait model inference authorized")

    def clone(self):
        raise AssertionError("No model operation authorized")


class NoOps:
    async def apply(self, *args, **kwargs):
        raise AssertionError("No host broker operation required")


def assert_result(expected, actual, original, portrait, strength, start, end, cfg, identity=True):
    assert isinstance(actual, tuple) and len(actual) == 1
    result = actual[0]
    assert list(result) == list(expected[0])
    assert result is not original
    for key, value in expected[0].items():
        if key != "portrait_embeds":
            if identity:
                assert result[key] is value
            elif isinstance(value, torch.Tensor):
                assert result[key].shape == value.shape and result[key].dtype == value.dtype
                assert torch.equal(result[key], value)
            elif isinstance(value, dict):
                assert list(result[key]) == list(value)
                for subkey, subvalue in value.items():
                    if isinstance(subvalue, torch.Tensor):
                        assert torch.equal(result[key][subkey], subvalue)
                    elif isinstance(subvalue, ModelSentinel):
                        assert result[key][subkey] is subvalue
                    else:
                        assert result[key][subkey] == subvalue
            else:
                assert result[key] == value
    entry = result["portrait_embeds"]
    assert list(entry) == ["adapter_proj", "strength", "start_percent", "end_percent", "cfg_scale"]
    if identity or isinstance(portrait, ModelSentinel):
        assert entry["adapter_proj"] is portrait
    elif isinstance(portrait, torch.Tensor):
        assert torch.equal(entry["adapter_proj"], portrait) and entry["adapter_proj"].dtype == portrait.dtype
    else:
        assert entry["adapter_proj"] == portrait
    for key, value in (("strength", strength), ("start_percent", start), ("end_percent", end), ("cfg_scale", cfg)):
        assert entry[key] == value


def test_exact_schema_widgets_output_and_no_authority():
    old = source()
    new = candidate()
    schema = new.GET_SCHEMA()
    assert schema.node_id == ID and schema.category == old.CATEGORY
    assert schema.display_name == "WanVideo Add Fantasy Portrait"
    fields = old.INPUT_TYPES()["required"]
    assert [item.id for item in schema.inputs] == list(fields)
    for item in schema.inputs:
        expected = fields[item.id]
        assert not item.optional and item.io_type == expected[0]
        for key, value in expected[1].items() if len(expected) > 1 else ():
            assert getattr(item, key) == value
    assert tuple(item.io_type for item in schema.outputs) == old.RETURN_TYPES
    assert tuple(item.display_name for item in schema.outputs) == old.RETURN_NAMES
    assert new.SDK_REFS and new.SDK_PERMISSIONS == ()


def test_direct_60_cases_order_overwrite_no_mutation_and_aliases():
    old = source()()
    new = candidate()
    model = ModelSentinel()
    tensor = torch.arange(12, dtype=torch.float64).reshape(1, 3, 4)
    inputs = [
        {}, {"y": tensor, "model": model}, {"portrait_embeds": {"old": model}, "nested": {"tensor": tensor}},
        [("before", tensor), ("portrait_embeds", "old"), ("before", model)],
        (("unrelated", {"model": model}),),
    ]
    portraits = [model, tensor, {"a": 3}, None]
    settings = [(1.0, 0.0, 1.0, 1.0), (100.0, 1.0, 0.0, 20.0), (-2.0, -1.0, 4.0, "native")]
    total = 0
    for embeds, portrait, (strength, start, end, cfg) in itertools.product(inputs, portraits, settings):
        before = list(embeds.items()) if isinstance(embeds, dict) else list(embeds)
        expected = old.add(embeds, portrait, strength, start, end, cfg)
        actual = new.execute(embeds, portrait, strength, start, end, cfg).result
        assert_result(expected, actual, embeds, portrait, strength, start, end, cfg)
        assert before == (list(embeds.items()) if isinstance(embeds, dict) else list(embeds))
        total += 1
    assert total == 60
    actual = new.execute({}, model, 1.0).result
    assert_result(old.add({}, model, 1.0), actual, {}, model, 1.0, 0.0, 1.0, 1.0)


@pytest.mark.parametrize("embeds", [None, 2, 1.5, "", "abc", [1], [("bad", 1, 2)]])
def test_direct_native_malformed_mapping_results(embeds):
    old = source()()
    try:
        expected = old.add(embeds, "portrait", 1)
    except Exception as error:
        with pytest.raises(type(error)) as actual:
            candidate().execute(embeds, "portrait", 1)
        assert str(actual.value) == str(error)
    else:
        assert candidate().execute(embeds, "portrait", 1).result == expected


def test_projected_bounds_and_no_unbounded_iterable():
    cls = candidate()
    with pytest.raises(ValueError, match="4096"):
        cls.execute({str(i): None for i in range(4097)}, None, 1)
    with pytest.raises(ValueError, match="64 KiB"):
        cls.execute({"x" * 65537: None}, None, 1)
    with pytest.raises(ValueError, match="64 KiB"):
        cls.execute({}, "x" * 65537, 1)
    with pytest.raises(ValueError, match="4096"):
        cls.execute({}, [None] * 4097, 1)
    value = {}; cursor = value
    for _ in range(18):
        cursor["next"] = {}; cursor = cursor["next"]
    with pytest.raises(ValueError, match="depth"):
        cls.execute(value, None, 1)
    class Unbounded:
        def __iter__(self):
            raise AssertionError("Must refuse before iterating an unknown producer")
    with pytest.raises(TypeError, match="bounded mapping"):
        cls.execute(Unbounded(), None, 1)


def test_in_process_public_refs_not_resolved():
    async def run():
        model = ModelSentinel()
        tensor = torch.arange(12, dtype=torch.float32).reshape(1, 3, 4)
        values = dict(embeds={"y": tensor, "model": model}, portrait_embeds=model, strength=1.5)
        refs = _sdk.InProcessRefResolver()
        wrapped = await _sdk.wrap_inputs(refs, values)
        plan = _sdk.ExecutionPlan("portrait-inproc", "1", ID, permissions=())
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=NoOps())
        with _sdk.bind_runtime(runtime.refs, runtime.ctx, runtime.ops):
            actual = candidate().execute(**wrapped)
        assert actual.result[0]["y"] is wrapped["embeds"]["y"]
        assert actual.result[0]["portrait_embeds"]["adapter_proj"] is wrapped["portrait_embeds"]
        result = await _sdk.unwrap_outputs(refs, actual)
        assert_result(source()().add(**values), result.result, values["embeds"], model, 1.5, 0., 1., 1.)
    asyncio.run(run())


def test_actual_outer_custom_output_zero_caps_two_fresh_filesystems(tmp_path, monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE", "required")
    monkeypatch.syspath_prepend(CORE)
    fresh = tmp_path/"fresh-render"
    shutil.copytree(V2, fresh)
    async def run():
        import execution
        previous = _sdk.providers.execution_backend
        pids = []
        try:
            for index, root in enumerate((V2, fresh)):
                snapshot = PACK.parent if index == 0 else tmp_path/"snapshot"
                if index:
                    snapshot.mkdir()
                    mounted = snapshot/PACK.name
                    mounted.mkdir()
                    shutil.copytree(root, mounted/"v2")
                    root = mounted/"v2"
                cls = packdb.load_pack(snapshot, mount_name="custom_nodes.wan_portrait_outer_" + str(index)).node_mappings[ID]
                session = await GuestSession("wan-portrait", guest_runtime_root=root).start()
                assert session.sandbox_kind == "seatbelt"
                class Backend:
                    async def dispatch(self, plan, local_call, runtime):
                        assert plan.input_mode == "refs" and plan.permissions == ()
                        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                        return await session.execute(plan, runtime, capabilities=(), tenant="portrait-" + str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    model = ModelSentinel()
                    for overwrite in (False, True):
                        tensor = torch.arange(24, dtype=torch.float64).reshape(2, 3, 4)
                        embeds = {"nested": {"model": model, "note": "unchanged"}, "y": tensor}
                        if overwrite:
                            embeds["portrait_embeds"] = "old"
                        for portrait in (model, tensor):
                            args = dict(embeds=embeds, portrait_embeds=portrait, strength=2.5,
                                        start_percent=.1, end_percent=.9, portrait_cfg=1.25)
                            expected = source()().add(**args)
                            finalized, missing, data = execution.get_input_data(args, cls, "owner", None)
                            assert not missing
                            result = await execution._async_map_node_over_list(prompt_id="portrait", unique_id="owner",
                                obj=cls, input_data_all=finalized, func="execute", v3_data=data)
                            assert cls.GET_SCHEMA().outputs[0].io_type == "WANVIDIMAGE_EMBEDS"
                            assert_result(expected, result[0].result, embeds, portrait, 2.5, .1, .9, 1.25, identity=False)
                            assert ("portrait_embeds" in embeds) == overwrite
                    pids.append(session.pid)
                finally:
                    await session.kill()
            assert len(set(pids)) == 2 and os.getpid() not in pids
        finally:
            _sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
