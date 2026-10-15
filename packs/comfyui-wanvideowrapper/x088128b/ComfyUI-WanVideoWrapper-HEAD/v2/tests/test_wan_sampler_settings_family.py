"""Exact settings-only assembly; no Wan model or sampler inference proof."""
import ast
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys

import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = '/Users/ben/comfy/ComfyUI-secure-nodes'
BACKEND = '/Users/ben/comfy/ComfyUI_secure_nodes/backend'
for path in (CORE, BACKEND):
    sys.path.insert(0, path)
os.environ.setdefault('COMFY_CORE_ROOT', CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packdb

ID = 'WanVideoSamplerSettings'


def source():
    tree = ast.parse((PACK / 'nodes_sampler.py').read_text())
    base = copy.deepcopy(next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'WanVideoSampler'))
    # Preserve exact source schema/signature/defaults, never execute the huge
    # sampler body or import its model/device/dependency modules.
    base.body = [n for n in base.body if isinstance(n, (ast.Assign, ast.FunctionDef))
                 and (isinstance(n, ast.Assign) or n.name in ('INPUT_TYPES', 'process'))]
    process = next(n for n in base.body if isinstance(n, ast.FunctionDef) and n.name == 'process')
    process.body = [ast.Raise(exc=ast.Call(func=ast.Name(id='AssertionError', ctx=ast.Load()),
                                         args=[ast.Constant('No sampler execution authorized')], keywords=[]))]
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == ID)
    schedulers = ast.parse((PACK / 'wanvideo/schedulers/__init__.py').read_text())
    choices = next(ast.literal_eval(n.value) for n in schedulers.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'scheduler_list' for t in n.targets))
    namespace = {'scheduler_list': choices, 'rope_functions': ['default', 'comfy', 'comfy_chunked']}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[base, cls], type_ignores=[])),
                 str(PACK / 'nodes_sampler.py'), 'exec'), namespace)
    return namespace[ID]


def candidate():
    name = '_wan_sampler_settings_family'
    spec = importlib.util.spec_from_file_location(name, V2 / '__init__.py', submodule_search_locations=[str(V2)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]


class ModelSentinel:
    def clone(self):
        raise AssertionError('Settings must not clone a model')

    def __call__(self, *args, **kwargs):
        raise AssertionError('Settings must not run a model')


class NoOps:
    async def apply(self, *args, **kwargs):
        raise AssertionError('No broker operation required')


def assert_tree(expected, actual):
    if isinstance(expected, dict):
        assert list(actual) == list(expected)
        for key, value in expected.items():
            assert_tree(value, actual[key])
    elif isinstance(expected, torch.Tensor):
        assert type(actual) is type(expected)
        assert actual.shape == expected.shape and actual.dtype == expected.dtype
        assert torch.equal(actual, expected)
    elif isinstance(expected, ModelSentinel):
        assert actual is expected
    else:
        assert actual == expected


def values(model):
    return dict(model=model, image_embeds={'y': torch.arange(12, dtype=torch.float64).reshape(1, 3, 4),
                                        'vae': model, 'opaque_note': 'untouched'},
                steps=30, cfg=6., shift=5., seed=2**64-1, force_offload=True,
                scheduler='unipc', riflex_freq_index=0, text_embeds={'model': model},
                samples={'samples': torch.arange(24, dtype=torch.float32).reshape(1, 2, 3, 4)},
                context_options={'reference_model': model}, sigmas=torch.tensor([1., .5, 0.], dtype=torch.float64))


def test_exact_inherited_schema_all_30_inputs_and_31_signature_keys():
    old, new = source(), candidate()
    schema = new.GET_SCHEMA()
    assert schema.node_id == ID and schema.category == old.CATEGORY
    assert schema.display_name == 'WanVideo Sampler Settings' and schema.description == old.DESCRIPTION
    fields = old.INPUT_TYPES()
    expected_ids = [name for group in fields.values() for name in group]
    assert len(expected_ids) == 30 and [field.id for field in schema.inputs] == expected_ids
    for field in schema.inputs:
        optional = field.id in fields['optional']
        declaration = fields['optional' if optional else 'required'][field.id]
        assert field.optional == optional
        assert (field.options if isinstance(declaration[0], list) else field.io_type) == declaration[0]
        for key, value in (declaration[1] if len(declaration) > 1 else {}).items():
            assert getattr(field, key) == value
    assert schema.inputs[5].max == 2**64-1
    assert tuple(item.io_type for item in schema.outputs) == old.RETURN_TYPES == ('SAMPLER_ARGS',)
    assert tuple(item.display_name for item in schema.outputs) == old.RETURN_NAMES
    assert new.SDK_REFS and new.SDK_PERMISSIONS == ()
    assert len(old().process()[0]) == 31 and 'teacache_args' not in expected_ids


def test_direct_defaults_omissions_ignored_unknown_and_positional_aliases():
    old, new = source()(), candidate()
    baseline = old.process()[0]
    assert new.execute().result == (baseline,)
    assert baseline['rope_function'] == 'default'
    assert baseline['force_offload'] is True and baseline['model'] is None
    model = ModelSentinel()
    fields = values(model)
    cases = [{}, fields, {'rope_function': 'comfy', 'flowedit_args': {'deprecated': 'still forwarded'}},
             {'seed': -1, 'steps': 'native', 'cfg': None}, {'teacache_args': model}]
    for name in baseline:
        cases.extend(({name: None}, {name: model}))
    for given in cases:
        expected = old.process(model, 'ignored', **given)[0]
        actual = new.execute(model, 'ignored', **given).result[0]
        assert list(actual) == list(expected)
        for key, value in expected.items():
            if key in given:
                assert actual[key] is value
            else:
                assert type(actual[key]) is type(value) and actual[key] == value
        assert list(given) == list(given.copy())
    assert len(cases) == 67
    # Dropped values are not inspected/materialized or bounded by the source.
    assert new.execute(unrecognized='x' * 100000).result == (baseline,)


def test_projected_metadata_bounds_before_forwarding():
    new = candidate()
    with pytest.raises(ValueError, match='4096'):
        new.execute(image_embeds={str(n): None for n in range(4097)})
    with pytest.raises(ValueError, match='64 KiB'):
        new.execute(scheduler='x' * 65537)
    deep = {}; cursor = deep
    for _ in range(18):
        cursor['next'] = {}; cursor = cursor['next']
    with pytest.raises(ValueError, match='depth'):
        new.execute(image_embeds=deep)
    with pytest.raises(ValueError, match='16777216'):
        new.execute(samples={'samples': torch.empty(16777217, device='meta')})
    # Aggregate known tensor/text budget, not a physical model memory profile.
    with pytest.raises(ValueError, match='64 MiB'):
        new.execute(image_embeds=torch.empty(8388608, dtype=torch.float64, device='meta'), text_embeds='x')


def test_inprocess_public_refs_remain_unresolved_without_broker_calls():
    async def run():
        given = values(ModelSentinel())
        refs = _sdk.InProcessRefResolver()
        wrapped = await _sdk.wrap_inputs(refs, given)
        plan = _sdk.ExecutionPlan('settings-inproc', '1', ID, permissions=())
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=NoOps())
        with _sdk.bind_runtime(runtime.refs, runtime.ctx, runtime.ops):
            result = candidate().execute(**wrapped)
        for key, value in wrapped.items():
            assert result.result[0][key] is value
        unwrapped = await _sdk.unwrap_outputs(refs, result)
        assert_tree(source()().process(**given)[0], unwrapped.result[0])
    asyncio.run(run())


def test_real_outer_zero_capability_guests_fresh_roots_and_tensor_aliases(tmp_path, monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE', 'required')
    monkeypatch.syspath_prepend(CORE)
    async def run():
        import execution
        previous = _sdk.providers.execution_backend
        pids = []
        try:
            for index in range(2):
                snapshot = PACK.parent
                root = V2
                if index:
                    snapshot = tmp_path / 'fresh-snapshot'
                    root = snapshot / PACK.name / 'v2'
                    shutil.copytree(V2, root)
                cls = packdb.load_pack(snapshot, mount_name='custom_nodes.wan_sampler_settings_' + str(index)).node_mappings[ID]
                session = await GuestSession('wan-settings', guest_runtime_root=root).start()
                assert session.sandbox_kind == 'seatbelt'
                class Backend:
                    async def dispatch(self, plan, local_call, runtime):
                        assert plan.input_mode == 'refs' and plan.permissions == ()
                        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                        return await session.execute(plan, runtime, capabilities=(), tenant='settings-' + str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for mode in ('minimal', 'all', 'none-and-nonnative'):
                        given = values(ModelSentinel())
                        if mode == 'minimal':
                            given = {key: value for key, value in given.items() if key in source().INPUT_TYPES()['required']}
                        if mode == 'none-and-nonnative':
                            given.update(rope_function='comfy_chunked', flowedit_args={'legacy': 1}, text_embeds=None)
                        before = dict(given)
                        expected = source()().process(**given)[0]
                        finalized, missing, data = execution.get_input_data(given, cls, 'owner', None)
                        assert not missing
                        result = await execution._async_map_node_over_list(prompt_id='wan-settings', unique_id='owner',
                            obj=cls, input_data_all=finalized, func='execute', v3_data=data)
                        assert tuple(cls.RETURN_TYPES) == ('SAMPLER_ARGS',)
                        assert_tree(expected, result[0].result[0])
                        for key, value in before.items():
                            assert given[key] is value
                    pids.append(session.pid)
                finally:
                    await session.kill()
            assert len(set(pids)) == 2 and os.getpid() not in pids
        finally:
            _sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
