"""First-family evidence, not full Wan import or inference certification.

The pinned pure classes are extracted as AST without their heavyweight module
imports. Real guest execution below exercises converted classes independently.
"""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import shutil
import sys

import pytest

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = Path('/Users/ben/comfy/ComfyUI-secure-nodes')
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
for root in (CORE, BACKEND):
    sys.path.insert(0, str(root))
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession

NODES = {
    'nodes.py': ['WanVideoEnhanceAVideo', 'WanVideoBlockList', 'WanVideoSLG',
        'WanVideoLoopArgs', 'WanVideoExperimentalArgs', 'WanVideoFreeInitArgs', 'WanVideoRoPEFunction'],
    'nodes_model_loading.py': ['WanVideoBlockSwap', 'WanVideoVRAMManagement', 'WanVideoTorchCompileSettings',
        'WanVideoLoraBlockEdit'],
    'nodes_utility.py': ['WanVideoSigmaToStep'],
}
IDS = [name for names in NODES.values() for name in names]


def load(name, root=V2):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def legacy():
    """Pure-class extraction only; explicitly not a loaded upstream census."""
    result = {}
    for file, names in NODES.items():
        tree = ast.parse((PACK / file).read_text())
        classes = [item for item in tree.body if isinstance(item, ast.ClassDef) and item.name in names]
        assert len(classes) == len(names)
        subset = ast.Module(body=classes, type_ignores=[])
        namespace = {'rope_functions': ['default', 'comfy', 'comfy_chunked']}
        exec(compile(subset, str(PACK / file), 'exec'), namespace)
        result.update({name:namespace[name] for name in names})
    return result


def defaults(cls):
    result = {}
    for fields in cls.INPUT_TYPES().values():
        for name, spec in fields.items():
            if len(spec) > 1 and 'default' in spec[1]:
                result[name] = spec[1]['default']
            elif isinstance(spec[0], list):
                result[name] = spec[0][0]
    return result


def outcome(fn, inputs, new=False):
    try:
        value = fn(**inputs)
        return ('value', value.result if new else value)
    except Exception as exc:
        return ('error', type(exc).__name__, str(exc))


@pytest.mark.parametrize('node_id', IDS)
def test_exact_subset_schema_options_defaults_output_contract(node_id):
    old = legacy()[node_id]
    new = load('_wan_schema').NODE_CLASS_MAPPINGS[node_id]
    schema = new.GET_SCHEMA()
    assert schema.node_id == node_id
    assert schema.category == old.CATEGORY
    assert schema.description == getattr(old, 'DESCRIPTION', '')
    assert schema.is_experimental == getattr(old, 'EXPERIMENTAL', False)
    original = old.INPUT_TYPES()
    assert [field.id for field in schema.inputs] == [name for fields in original.values() for name in fields]
    for field in schema.inputs:
        group = 'optional' if field.optional else 'required'
        spec = original[group][field.id]
        typ = spec[0]
        if isinstance(typ, list):
            assert field.options == typ
        else:
            assert field.io_type == typ
        for key, value in (spec[1] if len(spec) > 1 else {}).items():
            assert getattr(field, key) == value
    for index, output in enumerate(schema.outputs):
        typ = old.RETURN_TYPES[index]
        assert (output.options if isinstance(typ, list) else output.io_type) == typ
        assert output.display_name == old.RETURN_NAMES[index]
    assert new.SDK_PERMISSIONS == () and new.SDK_REFS is False


@pytest.mark.parametrize('node_id', IDS)
def test_exact_scalar_algorithms_native_errors_and_optional_defaults(node_id):
    old = legacy()[node_id]
    new = load('_wan_differential').NODE_CLASS_MAPPINGS[node_id]
    original = getattr(old(), old.FUNCTION)
    cases = [defaults(old)]
    schema = old.INPUT_TYPES()
    rng = random.Random(721)
    for iteration in range(20):
        values = defaults(old)
        for name, spec in schema.get('required', {}).items():
            typ = spec[0]
            if isinstance(typ, list):
                values[name] = typ[iteration % len(typ)]
            elif typ == 'BOOLEAN':
                values[name] = bool(iteration % 2)
            elif typ == 'FLOAT':
                options = spec[1] if len(spec) > 1 else {}
                lo, hi = options.get('min', 0), options.get('max', 10)
                values[name] = lo + (hi - lo) * rng.random()
            elif typ == 'INT':
                options = spec[1] if len(spec) > 1 else {}
                values[name] = rng.randint(options.get('min', 0), options.get('max', 100))
        cases.append(values)
    if node_id == 'WanVideoBlockList':
        cases += [{'blocks':text} for text in ['', '  ', '0,2,3-5', '2-1', '1\n1,4-6', '-1', '2--1', '1-2-3', 'a', '1, ', None]]
    if node_id == 'WanVideoSLG':
        cases += [dict(blocks=text, start_percent=.1, end_percent=.9) for text in ['1, 2,-3', '', '2,', '1-3', 'x', None]]
    if node_id == 'WanVideoRoPEFunction':
        cases += [dict(rope_function=option, ntk_scale_f=f, ntk_scale_h=h, ntk_scale_w=w)
            for option in ['default', 'comfy', 'comfy_chunked']
            for f,h,w in [(1,1,1), (1.1,1,1), (0,0,0), (1,2,3)]]
    if node_id == 'WanVideoTorchCompileSettings':
        values = defaults(old)
        values.pop('force_parameter_static_shapes')
        cases.append(values)  # source method default True differs from widget False
    if node_id == 'WanVideoLoraBlockEdit':
        cases += [dict(layer_filter=layer,**{'blocks.0.':True,'blocks.1.':False,'blocks.2.':1,
            'arbitrary':True,'number':2,'nothing':None}) for layer in ['', '  q,k,v  ', 'a,,b', None, [], 2]]
        cases += [{},dict(layer_filter='a',**{'blocks.39.':True})]
    for values in cases:
        assert outcome(new.execute, values, True) == outcome(original, values)


def test_projected_parser_and_text_bounds_without_large_allocation():
    new = load('_wan_bounds').NODE_CLASS_MAPPINGS
    assert new['WanVideoBlockList'].execute('0-10000').result[0][-1] == 10000
    with pytest.raises(ValueError):
        new['WanVideoBlockList'].execute('0-100000000000')
    with pytest.raises(ValueError, match='64 KiB'):
        new['WanVideoBlockList'].execute('1' * 65537)
    with pytest.raises(ValueError, match='10001'):
        new['WanVideoBlockList'].execute(','.join(['1'] * 10002))
    with pytest.raises(ValueError, match='64 KiB'):
        new['WanVideoExperimentalArgs'].execute(video_attention_split_steps='x' * 65537)
    with pytest.raises(ValueError, match='64 KiB'):
        new['WanVideoLoraBlockEdit'].execute(layer_filter='x' * 65537)
    with pytest.raises(ValueError, match='4096'):
        new['WanVideoLoraBlockEdit'].execute(layer_filter=',' * 4096)
    with pytest.raises(ValueError, match='4096'):
        new['WanVideoLoraBlockEdit'].execute(layer_filter='',**{str(index):True for index in range(4097)})


def test_real_guest_each_scalar_id_and_fresh_render_no_durable_state(tmp_path):
    original = legacy()
    fresh = tmp_path / 'fresh-render'
    shutil.copytree(V2, fresh)
    async def run():
        for index, root in enumerate((V2, fresh)):
            classes = load(f'_wan_render_{index}', root).NODE_CLASS_MAPPINGS
            session = await GuestSession('wan-scalar', guest_runtime_root=root).start()
            refs = _sdk.InProcessRefResolver()
            try:
                for node_id in IDS:
                    cls = classes[node_id]
                    inputs = defaults(original[node_id])
                    if node_id == 'WanVideoBlockList': inputs['blocks'] = '0,2-4\n8'
                    plan = _sdk.ExecutionPlan(prompt_id='wan-scalar', node_id='1', node_type=cls.__name__,
                        node_module=cls.__module__, inputs=inputs, input_mode='values', permissions=(), tier='sandbox')
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    actual = await session.execute(plan, runtime, capabilities=())
                    expected = getattr(original[node_id](), original[node_id].FUNCTION)(**inputs)
                    assert actual.result == expected
                assert session.last_guest_pid not in (None, os.getpid())
                assert not refs._table  # all current outputs are JSON-safe
            finally:
                await session.kill()
    asyncio.run(run())


def test_pristine_complete_capture_census_and_current_stub_hashes():
    expected = {'comfy-api.d.ts': '2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090',
        'comfy-api.pyi': 'd6ea0cd4f925b2ee29bd37674117656791926fad6b190535b1a17f00f7944384'}
    for file, digest in expected.items():
        assert hashlib.sha256((V2 / file).read_bytes()).hexdigest() == digest
    root = ast.parse((PACK / '__init__.py').read_text())
    modules = []
    for item in root.body:
        if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id in ('REQUIRED_MODULES', 'OPTIONAL_MODULES') for target in item.targets):
            modules += ast.literal_eval(item.value)
    ids = []
    for module, label in modules:
        path = PACK / (module.lstrip('.').replace('.', '/') + '.py')
        for item in ast.parse(path.read_text()).body:
            if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'NODE_CLASS_MAPPINGS' for target in item.targets):
                ids += [ast.literal_eval(key) for key in item.value.keys]
    assert len(ids) == len(set(ids)) == 147
    assert set(IDS) < set(ids)  # do not misrepresent subset as entire pack
    assert not list(PACK.rglob('__pycache__'))
    assert not list(PACK.rglob('*.pyc'))


def test_public_outer_executor_scalar_outputs_and_rope_dict_variant(monkeypatch):
    # Pytest prepends the pristine pack's parent, which also has a module named
    # latent_preview. Resolve the real executor's dependencies from core first.
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    from comfy_secure_nodes import packdb
    classes = packdb.load_pack(PACK.parent,mount_name='custom_nodes.wan_scalar_outer').node_mappings
    original = legacy()
    async def run():
        previous = _sdk.providers.execution_backend
        class Backend:
            sessions = []
            async def dispatch(self, plan, local_call, runtime):
                session = await GuestSession('wan-outer', guest_runtime_root=V2).start()
                self.sessions.append(session)
                return await session.execute(plan, runtime, capabilities=())
        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            for node_id in IDS:
                cls = classes[node_id]
                cls.GET_SCHEMA()
                cases = [defaults(original[node_id])]
                if node_id == 'WanVideoRoPEFunction':
                    cases.append(dict(rope_function='comfy', ntk_scale_f=1.5, ntk_scale_h=1., ntk_scale_w=1.))
                for inputs in cases:
                    finalized, missing, data = execution.get_input_data(inputs, cls, '1', None)
                    assert not missing
                    values = await execution._async_map_node_over_list(prompt_id='wan-outer', unique_id='1', obj=cls,
                        input_data_all=finalized, func='execute', v3_data=data)
                    expected = getattr(original[node_id](), original[node_id].FUNCTION)(**inputs)
                    assert values[0].result == expected
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:
                await session.kill()
    asyncio.run(run())
