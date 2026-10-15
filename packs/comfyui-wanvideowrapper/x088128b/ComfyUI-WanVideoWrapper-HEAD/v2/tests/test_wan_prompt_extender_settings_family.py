"""Settings/prompt/catalogue evidence only, not Qwen loading or inference."""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import itertools
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = '/Users/ben/comfy/ComfyUI-secure-nodes'
BACKEND = '/Users/ben/comfy/ComfyUI_secure_nodes/backend'
for path in (CORE, BACKEND):
    sys.path.insert(0, path)
os.environ.setdefault('COMFY_CORE_ROOT', CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession

ID = 'WanVideoPromptExtenderSelect'


def prompts():
    # Immutable assignments/string data only; no arbitrary imported Qwen code.
    path = PACK / 'qwen/system_prompt.py'
    tree = ast.parse(path.read_text())
    assert all(isinstance(n, ast.Assign) for n in tree.body)
    namespace = {}
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace['SYSTEM_PROMPT_MAP']


def source():
    import folder_paths
    path = PACK / 'qwen/qwen.py'
    cls = next(n for n in ast.parse(path.read_text()).body if getattr(n, 'name', None) == ID)
    namespace = dict(folder_paths=folder_paths, SYSTEM_PROMPT_MAP=prompts(),
                     SYSTEM_PROMPT_KEYS=[item['label'] for item in prompts()])
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[ID]


def candidate():
    name = '_wan_prompt_extender_settings_family'
    spec = importlib.util.spec_from_file_location(name, V2 / '__init__.py', submodule_search_locations=[str(V2)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]


def test_exact_scalar_schema_six_immutable_prompts_and_closed_remote_catalogue():
    old, cls = source(), candidate()
    schema = cls.GET_SCHEMA()
    assert schema.node_id == ID and schema.category == old.CATEGORY
    assert schema.display_name == 'Wan Video Prompt Extender Select'
    fields = old.INPUT_TYPES()
    assert [field.id for field in schema.inputs] == [key for group in fields.values() for key in group]
    for field in schema.inputs:
        optional = field.id in fields['optional']
        expected = fields['optional' if optional else 'required'][field.id]
        assert field.optional == optional
        if field.id != 'model':
            assert (field.options if isinstance(expected[0], list) else field.io_type) == expected[0]
        for key, value in (expected[1] if len(expected) > 1 else {}).items():
            assert getattr(field, {'forceInput': 'force_input'}.get(key, key)) == value
    model = schema.inputs[0]
    assert model.options == [] and model.remote.route == '/secure-nodes/models/text_encoders'
    assert model.remote.refresh_button is True
    assert len(schema.inputs[2].options) == 6 and schema.inputs[-1].max == 2**64-1
    assert tuple(item.io_type for item in schema.outputs) == old.RETURN_TYPES
    assert tuple(item.display_name for item in schema.outputs) == old.RETURN_NAMES
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS == ()
    assert (V2/'qwen/system_prompt.py').read_bytes() == (PACK/'qwen/system_prompt.py').read_bytes()
    assert len(prompts()) == 6


def test_120_scalar_default_selection_and_empty_custom_overrides_exact():
    old, new = source()(), candidate()
    labels = [item['label'] for item in prompts()] + ['not registered', None]
    custom_values = [None, '', '  exact unicode 🎥\n<script>not markup</script>  ', 17]
    total = 0
    for label, custom, seed in itertools.product(labels, custom_values, (0, 2**64-1)):
        args = dict(model='nested/model.safetensors', system_prompt=label, max_new_tokens=512,
                    custom_system_prompt=custom, seed=seed)
        expected = old.set(**args)
        actual = new.execute(**args).result
        assert actual == expected
        assert list(actual[0]) == list(expected[0]) == ['model', 'system_prompt', 'max_new_tokens', 'device', 'force_offload', 'seed']
        assert actual[0]['device'] == 'gpu' and actual[0]['force_offload'] is True
        if custom is not None:
            assert actual[0]['system_prompt'] is custom
        total += 1
    assert total == 64
    # Distinct missing/default and explicit-None semantics are also preserved.
    for label, tokens in itertools.product(labels, (1, 2048, -1, 'source-data')):
        assert new.execute('model', label, tokens).result == old.set('model', label, tokens)
        total += 1
    assert total == 96
    for label, model in itertools.product(labels, ('', None, 'unknown-but-direct')):
        assert new.execute(model, label, 512, seed=None).result == old.set(model, label, 512, seed=None)
        total += 1
    assert total == 120


def test_bounded_native_missing_arguments_and_metadata_no_inference():
    old, cls = source()(), candidate()
    for args in ((), ('only-model',), ('model', 'label')):
        with pytest.raises(TypeError):
            old.set(*args)
        with pytest.raises(TypeError):
            cls.execute(*args)
    for field in ('model', 'system_prompt', 'custom_system_prompt'):
        given = dict(model='m', system_prompt='label', max_new_tokens=1)
        given[field] = 'x' * 65537
        with pytest.raises(ValueError, match='64 KiB'):
            cls.execute(**given)
    with pytest.raises(ValueError, match='4096'):
        cls.execute('m', 'label', [None] * 4097)


def install_local_catalogue(tmp_path, monkeypatch):
    import folder_paths
    folder = tmp_path/'models'
    folder.mkdir()
    (folder/'beta.safetensors').touch()
    (folder/'alpha.safetensors').touch()
    (folder/'ignore.txt').touch()
    # Test-scoped registered roots with inert placeholders; never parsed as
    # model weights and never establish trained-model/device admission.
    monkeypatch.setitem(folder_paths.folder_names_and_paths, 'text_encoders', ([str(folder)], {'.safetensors'}))
    monkeypatch.setattr(folder_paths, 'filename_list_cache', {})
    return folder


def test_real_host_catalogue_hydration_and_prompt_admission_before_guest(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(CORE)
    import execution
    import nodes
    from comfy_secure_nodes.webassets import remote_catalogue_options
    folder = install_local_catalogue(tmp_path, monkeypatch)
    cls = packdb.load_pack(PACK.parent, mount_name='custom_nodes.wan_extender_catalogue').node_mappings[ID]
    assert cls.GET_SCHEMA().inputs[0].options == remote_catalogue_options('/secure-nodes/models/text_encoders') == ['alpha.safetensors', 'beta.safetensors']
    assert source().INPUT_TYPES()['required']['model'][0] == cls.GET_SCHEMA().inputs[0].options
    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS, ID, cls)
    async def validate(name):
        graph = {'owner': {'class_type': ID, 'inputs': dict(model=name, max_new_tokens=512, system_prompt=prompts()[0]['label'])}}
        return await execution.validate_inputs('catalogue-settings', graph, 'owner', {})
    assert asyncio.run(validate('alpha.safetensors'))[0] is True
    for name in ('missing.safetensors', '../escape.safetensors', str(folder/'alpha.safetensors')):
        result = asyncio.run(validate(name))
        assert result[0] is False and any(e['type'] == 'value_not_in_list' for e in result[1])
    (folder/'alpha.safetensors').unlink()
    (folder/'beta.safetensors').unlink()
    import folder_paths
    folder_paths.filename_list_cache.clear()
    assert cls.GET_SCHEMA().inputs[0].options == []
    assert asyncio.run(validate('alpha.safetensors'))[0] is False


def test_actual_outer_zero_capability_six_prompts_two_fresh_guests(tmp_path, monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE', 'required')
    monkeypatch.syspath_prepend(CORE)
    install_local_catalogue(tmp_path, monkeypatch)
    async def run():
        import execution
        previous = _sdk.providers.execution_backend
        pids = []
        try:
            for index in range(2):
                snapshot, root = PACK.parent, V2
                if index:
                    snapshot = tmp_path/'fresh-snapshot'
                    root = snapshot/PACK.name/'v2'
                    shutil.copytree(V2, root)
                cls = packdb.load_pack(snapshot, mount_name='custom_nodes.wan_extender_outer_' + str(index)).node_mappings[ID]
                session = await GuestSession('wan-extender-settings', guest_runtime_root=root).start()
                assert session.sandbox_kind == 'seatbelt'
                class Backend:
                    async def dispatch(self, plan, local_call, runtime):
                        assert plan.input_mode == 'refs' and plan.permissions == ()
                        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                        return await session.execute(plan, runtime, capabilities=(), tenant='extender-' + str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for item in prompts():
                        for custom in (None, '', '自定义🎥\nkeep <b>literal</b>'):
                            given = dict(model='alpha.safetensors', system_prompt=item['label'], max_new_tokens=512,
                                         custom_system_prompt=custom, seed=2**64-1)
                            finalized, missing, data = execution.get_input_data(given, cls, 'owner', None)
                            assert not missing
                            result = await execution._async_map_node_over_list(prompt_id='extender-settings', unique_id='owner',
                                obj=cls, input_data_all=finalized, func='execute', v3_data=data)
                            assert tuple(cls.RETURN_TYPES) == ('WANVIDEOPROMPTEXTENDER_ARGS',)
                            assert result[0].result == source()().set(**given)
                            assert result[0].result[0]['device'] == 'gpu'
                    pids.append(session.pid)
                finally:
                    await session.kill()
            assert len(set(pids)) == 2 and os.getpid() not in pids
        finally:
            _sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
