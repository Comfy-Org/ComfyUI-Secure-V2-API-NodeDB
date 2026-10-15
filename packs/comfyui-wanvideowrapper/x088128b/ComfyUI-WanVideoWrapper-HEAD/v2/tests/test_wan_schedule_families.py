"""Pinned scalar schedule parity plus actual scoped guest TEXT transport.

AST-extracted classes are the oracle, not full dependency-loaded Wan imports.
No model inference, trained weights, browser or cloud deployment is exercised.
"""
import ast
import asyncio
import importlib.util
import os
from pathlib import Path
import shutil
import struct
import sys
from types import MethodType, SimpleNamespace
import pytest

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = Path('/Users/ben/comfy/ComfyUI-secure-nodes')
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
sys.path[:0] = [str(CORE), str(BACKEND)]
os.environ.setdefault('COMFY_CORE_ROOT', str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession

IDS = ['CreateCFGScheduleFloatList', 'CreateScheduleFloatList']


def original(node_id, server=None):
    tree = ast.parse((PACK/'nodes_utility.py').read_text())
    cls = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == node_id)
    namespace = {'PromptServer': server}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(PACK/'nodes_utility.py'), 'exec'), namespace)
    return namespace[node_id]


def mapping(root=V2):
    name = '_wan_schedules_' + str(id(root))
    spec = importlib.util.spec_from_file_location(name, root/'__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS


def defaults(node_id):
    return {key: spec[1]['default'] for key, spec in original(node_id).INPUT_TYPES()['required'].items()}


def cases(node_id):
    values = []
    for steps in (2, 3, 30, 1000):
        for interpolation in ('linear', 'ease_in', 'ease_out'):
            for start, end in ((0, 1), (.25, .75), (1, 1), (.7, .2), (-.01, .4), (0, 1.2)):
                inputs = defaults(node_id)
                inputs.update(steps=steps, interpolation=interpolation, start_percent=start, end_percent=end)
                if node_id == IDS[0]:
                    inputs.update(cfg_scale_start=2.345, cfg_scale_end=7.891)
                else:
                    inputs.update(start_value=2.345, end_value=7.891, default_value=9.25)
                values.append(inputs)
    return values


def outcome(node_id, inputs, new=False):
    try:
        if new:
            result = asyncio.run(mapping()[node_id].execute(**inputs)).result
        else:
            result = original(node_id)().process(**inputs, unique_id='owner-node')
        return ('value', result)
    except Exception as error:
        return ('error', type(error).__name__, str(error))


@pytest.mark.parametrize('node_id', IDS)
def test_exact_schedule_schema_hidden_defaults_and_float_list_contract(node_id):
    cls = mapping()[node_id]
    old = original(node_id)
    schema = cls.GET_SCHEMA()
    assert schema.node_id == node_id
    assert schema.category == old.CATEGORY and schema.description == old.DESCRIPTION
    assert schema.hidden == ['UNIQUE_ID']
    assert [field.id for field in schema.inputs] == list(old.INPUT_TYPES()['required'])
    for field in schema.inputs:
        typ, options = old.INPUT_TYPES()['required'][field.id]
        assert (field.options if isinstance(typ, list) else field.io_type) == typ
        for key, value in options.items():
            assert getattr(field, key) == value
    assert len(schema.outputs) == 1 and schema.outputs[0].io_type == 'FLOAT'
    assert schema.outputs[0].display_name == 'float_list'
    assert not getattr(schema.outputs[0], 'is_output_list', False)
    assert cls.SDK_PERMISSIONS == () and cls.SDK_REFS is False


@pytest.mark.parametrize('node_id', IDS)
def test_72_exact_schedules_each_all_interpolations_rounding_ranges(node_id):
    for inputs in cases(node_id):
        assert outcome(node_id, inputs, True) == outcome(node_id, inputs)


@pytest.mark.parametrize('node_id', IDS)
def test_bounded_native_malformed_schedule_outcomes(node_id):
    overrides = [{'steps': 0}, {'steps': -1}, {'steps': 0, 'start_percent': .5},
        {'steps': 1.5}, {'interpolation': 'unknown'}, {'interpolation': None},
        {'start_percent': -2.0, 'end_percent': .2},
        {'interpolation': 'unknown', 'start_percent': .9, 'end_percent': .1}]
    for override in overrides:
        inputs = defaults(node_id); inputs.update(override)
        assert outcome(node_id, inputs, True) == outcome(node_id, inputs)


def test_schedule_bounds_before_large_list_or_unbounded_loop():
    for node_id in IDS:
        for override in ({'steps': 1001}, {'steps': 10**12}, {'start_percent': float('nan')},
                {'end_percent': float('inf')}, {'start_percent': -1000000},
                {'interpolation': 'x'*65537}):
            inputs = defaults(node_id); inputs.update(override)
            with pytest.raises(ValueError):
                asyncio.run(mapping()[node_id].execute(**inputs))


def test_best_effort_progress_failure_preserves_output(monkeypatch):
    from comfy_api.latest import sdk
    calls = []
    class Progress:
        async def text(self, message):
            calls.append(message)
            raise RuntimeError('progress unavailable')
    monkeypatch.setattr(sdk, 'ctx', lambda: SimpleNamespace(progress=Progress()))
    for node_id in IDS:
        expected = original(node_id)().process(**defaults(node_id), unique_id=None)
        assert asyncio.run(mapping()[node_id].execute(**defaults(node_id))).result == expected
        assert calls[-1] == str(expected[0])


def server(monkeypatch, client='owner-client'):
    monkeypatch.syspath_prepend(str(CORE))
    from server import PromptServer
    frames = []
    value = SimpleNamespace(client_id=client, send_sync=lambda event, payload, sid: frames.append((event, payload, sid)))
    value.send_progress_text = MethodType(PromptServer.send_progress_text, value)
    monkeypatch.setattr(PromptServer, 'instance', value, raising=False)
    return value, frames


def decode(frame):
    from server import BinaryEventTypes
    event, payload, sid = frame
    assert event == BinaryEventTypes.TEXT
    size = struct.unpack('>I', payload[:4])[0]
    return payload[4:4+size].decode('utf-8'), payload[4+size:].decode('utf-8'), sid


def test_real_guest_both_schedules_fresh_render_captured_client_no_broadcast(tmp_path, monkeypatch):
    value, frames = server(monkeypatch)
    fresh = tmp_path/'fresh-render'
    shutil.copytree(V2, fresh)
    async def run():
        pids = []
        for index, root in enumerate((V2, fresh)):
            classes = mapping(root)
            session = await GuestSession('wan-schedule', guest_runtime_root=root).start()
            try:
                for client in ('owner-client', None):
                    for node_id in IDS:
                        cls = classes[node_id]
                        inputs = defaults(node_id)
                        inputs.update(interpolation='ease_out', start_percent=.25)
                        plan = _sdk.ExecutionPlan(prompt_id='schedule-prompt', node_id='schedule-'+str(index),
                            node_type=cls.__name__, node_module=cls.__module__, inputs=inputs,
                            input_mode='values', permissions=(), tier='sandbox')
                        value.client_id = client
                        ctx = _sdk.InProcessCtxProvider().build(plan)
                        value.client_id = 'later-other-client'
                        runtime = _sdk.Runtime(refs=_sdk.InProcessRefResolver(), ctx=ctx, ops=_sdk.InProcessOps())
                        actual = await session.execute(plan, runtime, capabilities=(), tenant='schedule-owner')
                        expected = original(node_id)().process(**inputs, unique_id=plan.node_id)
                        assert actual.result == expected
                        if client:
                            assert decode(frames[-1]) == (plan.node_id, str(expected[0]), client)
                    assert len(frames) == 2*(index+1)
                pids.append(session.last_guest_pid)
                with pytest.raises(RuntimeError, match='active prompt'):
                    await session._h_progress_text('late')
                with pytest.raises(TypeError):
                    await session._h_progress_text('forged', node_id='victim', sid='victim')
            finally:
                await session.kill()
        assert len(set(pids)) == 2 and os.getpid() not in pids
    asyncio.run(run())
    assert len(frames) == 4


def test_actual_outer_executor_preserves_list_valued_float_socket_and_progress(monkeypatch):
    value, frames = server(monkeypatch)
    import execution
    from comfy_secure_nodes import packdb
    classes = packdb.load_pack(PACK.parent, mount_name='custom_nodes.wan_schedule_outer').node_mappings
    async def run():
        previous = _sdk.providers.execution_backend
        class Backend:
            sessions = []
            async def dispatch(self, plan, local_call, runtime):
                session = await GuestSession('wan-schedule-outer', guest_runtime_root=V2).start()
                self.sessions.append(session)
                return await session.execute(plan, runtime, capabilities=(), tenant='outer-owner')
        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            for node_id in IDS:
                cls = classes[node_id]; cls.GET_SCHEMA()
                inputs = defaults(node_id)
                finalized, missing, data = execution.get_input_data(inputs, cls, 'outer-node', None)
                assert not missing
                results = await execution._async_map_node_over_list(prompt_id='wan-schedules', unique_id='outer-node',
                    obj=cls, input_data_all=finalized, func='execute', v3_data=data)
                expected = original(node_id)().process(**inputs, unique_id='outer-node')
                assert results[0].result == expected
                assert isinstance(results[0].result[0], list)
                assert decode(frames[-1]) == ('outer-node', str(expected[0]), 'owner-client')
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:
                await session.kill()
    asyncio.run(run())
    assert len(frames) == 2
