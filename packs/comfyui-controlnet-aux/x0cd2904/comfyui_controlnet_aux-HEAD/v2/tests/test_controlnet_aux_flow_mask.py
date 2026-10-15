"""Pinned flow visualization/masking and explicit canonical MASK layout repair."""
import ast
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch
import torch.nn.functional as F
from einops import rearrange

CORE = Path(os.environ.get('COMFY_CORE_ROOT', '/Users/ben/comfy/ComfyUI-secure-nodes'))
OVERLAY = Path('/Users/ben/comfy/ComfyUI_secure_nodes')
sys.path[:0] = [str(CORE), str(OVERLAY / 'backend')]
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
import execution

V2 = Path(__file__).resolve().parents[1]
PRISTINE = V2.parent


def load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return sys.modules[name + '.nodes']


converted = load('_many_flow_mask_test', V2)


def reference():
    namespace = dict(np=np, torch=torch, F=F, rearrange=rearrange, UNKNOWN_FLOW_THRESH=1e7)
    path = PRISTINE / 'src/custom_controlnet_aux/unimatch/utils/flow_viz.py'
    functions = [node for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef) and node.name in {'make_color_wheel', 'compute_color', 'flow_to_image'}]
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    path = PRISTINE / 'node_wrappers/unimatch.py'
    cls = next(node for node in ast.parse(path.read_text()).body if isinstance(node, ast.ClassDef) and node.name == 'MaskOptFlow')
    cls = copy.deepcopy(cls)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'mask_opt_flow')
    method.body = [node for node in method.body if not isinstance(node, ast.ImportFrom)]
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


old = reference()


def values(dtype=torch.float32, batch=2, mask_rank=4, resize=True):
    flow = torch.arange(batch * 7 * 9 * 2, dtype=torch.float32).reshape(batch, 7, 9, 2) % 19 - 9
    flow[0, 0, 0, 0] = 1.1e7 if dtype != torch.float16 else 0
    flow = flow.to(dtype)
    h, w = (5, 6) if resize else (7, 9)
    mask = torch.arange((batch + 1) * h * w, dtype=torch.float32).reshape(batch + 1, 1, h, w) % 5 / 4
    if mask_rank == 3:
        mask = mask[:, 0]
    return dict(optical_flow=flow, mask=mask.to(dtype))


def expected(inputs):
    mask = inputs['mask']
    if mask.ndim == 3:
        mask = mask.unsqueeze(1)
    return old['MaskOptFlow']().mask_opt_flow(inputs['optical_flow'], mask)


def equal(actual, wanted):
    assert len(actual) == len(wanted) == 2
    for got, want in zip(actual, wanted):
        assert got.dtype == want.dtype and got.shape == want.shape and torch.equal(got, want)


def test_exact_pure_function_and_masking_ast():
    for name in ('make_color_wheel', 'compute_color', 'flow_to_image'):
        original = next(node for node in ast.parse((PRISTINE / 'src/custom_controlnet_aux/unimatch/utils/flow_viz.py').read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
        migrated = next(node for node in ast.parse((V2 / '_flow_mask.py').read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(original) == ast.dump(migrated)
    original = next(node for node in ast.parse((PRISTINE / 'node_wrappers/unimatch.py').read_text()).body if isinstance(node, ast.ClassDef) and node.name == 'MaskOptFlow')
    for method in original.body:
        if isinstance(method, ast.FunctionDef) and method.name == 'mask_opt_flow':
            method.body = [node for node in method.body if not isinstance(node, ast.ImportFrom)]
    migrated = next(node for node in ast.parse((V2 / '_flow_mask.py').read_text()).body if isinstance(node, ast.ClassDef) and node.name == 'MaskOptFlow')
    assert ast.dump(original) == ast.dump(migrated)


@pytest.mark.parametrize('dtype', [torch.float32, torch.float64, torch.float16])
@pytest.mark.parametrize('batch', [1, 2])
@pytest.mark.parametrize('rank', [3, 4])
@pytest.mark.parametrize('resize', [True, False])
def test_pinned_pixels_mutation_and_explicit_bhw_layout(dtype, batch, rank, resize):
    inputs = values(dtype, batch, rank, resize)
    oracle = {key: value.clone() for key, value in inputs.items()}
    desired = expected(oracle)
    output = asyncio.run(converted.NODE_CLASS_MAPPINGS['MaskOptFlow'].execute(**inputs)).result
    equal(output, desired)
    assert output[0] is inputs['optical_flow']
    assert torch.equal(inputs['optical_flow'], oracle['optical_flow'])


def test_source_bhw_error_and_native_bfloat_error_are_retained():
    inputs = values(mask_rank=3)
    with pytest.raises(ValueError, match='spatial dimensions'):
        old['MaskOptFlow']().mask_opt_flow(**inputs)
    inputs = values(torch.bfloat16)
    with pytest.raises(TypeError):
        expected({key: value.clone() for key, value in inputs.items()})
    with pytest.raises(TypeError):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['MaskOptFlow'].execute(**inputs))
    inputs = values()
    inputs['mask'] = inputs['mask'][:1]
    with pytest.raises(AssertionError, match='Not enough masks'):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['MaskOptFlow'].execute(**inputs))


def test_workspace_and_layout_refused_before_visualization(monkeypatch):
    monkeypatch.setattr(converted._flow_mask, 'flow_to_image', lambda *args: pytest.fail('work attempted'))
    inputs = values()
    inputs['optical_flow'] = torch.zeros(1, 2048, 2048, 2)
    with pytest.raises(ValueError, match='projected'):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['MaskOptFlow'].execute(**inputs))
    inputs = values()
    inputs['optical_flow'] = inputs['optical_flow'][..., :1]
    with pytest.raises(ValueError, match='NHW2'):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['MaskOptFlow'].execute(**inputs))


def test_flow_mask_actual_guests_and_production_outer(tmp_path, monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE', 'required')
    fresh = tmp_path / 'fresh'
    shutil.copytree(V2, fresh)
    async def run():
        pids = set()
        for index, root in enumerate((V2, fresh)):
            package = load('_many_flow_mask_guest' + str(index), root)
            session = await GuestSession('many-flow-mask', guest_runtime_root=root).start()
            try:
                assert session.sandbox_kind == 'seatbelt'
                for rank in (3, 4):
                    inputs = values(mask_rank=rank)
                    before = inputs['optical_flow'].clone()
                    desired = expected({key: value.clone() for key, value in inputs.items()})
                    refs = _sdk.InProcessRefResolver()
                    cls = package.NODE_CLASS_MAPPINGS['MaskOptFlow']
                    plan = _sdk.ExecutionPlan(prompt_id='flow-mask', node_id='1', node_type=cls.__name__, node_module=cls.__module__, inputs=await _sdk.wrap_inputs(refs, inputs), input_mode='values')
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    output = await session.execute(plan, runtime, capabilities=('raw',))
                    equal((await _sdk.unwrap_outputs(refs, output)).result, desired)
                    assert torch.equal(inputs['optical_flow'], before)
                    with pytest.raises(Exception, match="raw buffer access requires the 'raw' capability"):
                        await session.execute(plan, runtime, capabilities=())
                pids.add(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(pids) == 2
        loaded = packdb.load_pack(PRISTINE.parent, mount_name='custom_nodes.many_flow_mask_outer')
        class Backend:
            session = None
            async def dispatch(self, plan, local_call, runtime):
                if self.session is None:
                    self.session = await GuestSession('many-flow-mask-outer', guest_runtime_root=V2).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                return await self.session.execute(plan, runtime, capabilities=plan.permissions)
        backend = Backend()
        previous = _sdk.providers.execution_backend
        _sdk.providers.execution_backend = backend
        try:
            inputs = values(mask_rank=3)
            before = inputs['optical_flow'].clone()
            desired = expected({key: value.clone() for key, value in inputs.items()})
            cls = loaded.node_mappings['MaskOptFlow']
            output = await execution._async_map_node_over_list('flow-mask-outer', '1', cls, {key: [value] for key, value in inputs.items()}, cls.FUNCTION)
            equal(output[0].result, desired)
            assert torch.equal(inputs['optical_flow'], before)
        finally:
            _sdk.providers.execution_backend = previous
            if backend.session:
                await backend.session.kill()
    asyncio.run(run())
