from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

import pytest

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
DB = SNAPSHOT.parents[2]
CORE = Path(os.environ['COMFY_CORE_ROOT']).resolve()
BACKEND = Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
for root in (CORE, BACKEND):
    sys.path.insert(0, str(root))
sys.path.append('/Users/ben/comfy/ComfyUI')
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

COMMIT = '58769e57f190ff7d7a22ad0227f4caa0dfb3ac3c'
PAIR = DB / 'patches/comfyui_resolution-and-ratio/x58769e5/comfyui_resolution-and-ratio-x58769e5'
STUBS = {'comfy-api.d.ts':'4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3',
         'comfy-api.pyi':'50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78'}
PRISTINE = {'__init__.py':'e8996b23ba32b648214a79b07f708340c3b7d85dda05073014f8c5ff3f76b70c',
 'resolution_and_ratio.py':'0a4a5c73a5ac87e80e2826202b699e21a64d903d4a0a22cdd85cdde523e1deac',
 'web/resolution_and_ratio.js':'40692b98f25f63ba052d4c97f9ebb9f4565d06e34e698c6f26581980a342dea2',
 'README.md':'0a0189e48dc669cd2e8003bda374e6cc084a64d95325fcec901caddd40fccde1',
 'LICENSE':'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4',
 'pyproject.toml':'67eedb6bc9b04e37d792987f1a7d13cede9c7ab6a809fbce14008f8dd6f3e495',
 '.github/workflows/publish.yml':'0e09848ec760147b581f4fbbb1746cc19ef3a725bf3ac86d95d797907da8504e'}


def load(root, name):
    spec = importlib.util.spec_from_file_location(name, root/'__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def old():
    return load(PACK, '_ned_ratio_pristine')


def new():
    return load(V2, '_ned_ratio_secure')


def args(**updates):
    result = dict(width=1152, height=1536, W_ratio=3, H_ratio=4,
                  scale_percent=100, reset=False, swap=False, preset='Custom', custom_presets='')
    result.update(updates)
    return result


def manifest():
    cls = new().ResolutionAndRatio
    return {'format':FORMAT,'nodes':{'ResolutionAndRatio':{
        'module':'resolution_and_ratio','class':'ResolutionAndRatio','sdk_refs':False,'permissions':[],
        'methods':{key:key in cls.__dict__ for key in ('validate_inputs','fingerprint_inputs','check_lazy_status')},
        'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))}},
        'frontend_permissions':[], 'runtime':manifest_declaration(V2),'web_directory':'web'}


def test_pristine_census_and_v2_exact_schema():
    upstream, secure = old(), new()
    assert set(upstream.NODE_CLASS_MAPPINGS) == set(secure.NODE_CLASS_MAPPINGS) == {'ResolutionAndRatio'}
    assert upstream.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    schema = secure.ResolutionAndRatio.GET_SCHEMA(); schema.validate()
    legacy = upstream.ResolutionAndRatio.INPUT_TYPES()['required']
    assert [i.id for i in schema.inputs] == list(legacy)
    assert (schema.display_name, schema.category, schema.is_output_node) == ('Resolution and Ratio', 'CustomUtils',False)
    for i in schema.inputs:
        kind, *options = legacy[i.id]
        assert not i.optional
        if isinstance(kind,list): assert i.io_type == 'COMBO' and i.options == kind
        else: assert i.io_type == kind
        for key,value in (options[0] if options else {}).items():
            if key == 'display': assert i.display_mode.value == value
            else: assert getattr(i,key) == value
    assert [(i.io_type,i.display_name) for i in schema.outputs] == [('INT','width'),('INT','height')]
    loaded = packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_ratio_census')
    assert set(loaded.node_mappings) == {'ResolutionAndRatio'}
    assert loaded.web_directory == V2/'web' and not loaded.routes and not loaded.frontend_permissions
    js=(PACK/'web/resolution_and_ratio.js').read_text()
    assert js.count('app.registerExtension({') == 1 and 'Comfy.ResolutionAndRatio' in js
    assert 'registerNodeType' not in js
    assert list((PACK/'web').glob('*.js')) == [PACK/'web/resolution_and_ratio.js']


@pytest.mark.parametrize('width,height',[(8,8),(32,33),(47,48),(80,112),(1152,1536),(4096,4096),(-1,99999),(48.5,79.5)])
@pytest.mark.parametrize('reset,swap',[(False,False),(True,False),(False,True),(True,True)])
def test_backend_reset_swap_grid_bankers_ties_are_differential(width,height,reset,swap):
    inputs=args(width=width,height=height,reset=reset,swap=swap)
    assert new().ResolutionAndRatio.execute(**inputs).result == old().ResolutionAndRatio().get_resolution(**inputs)


def test_randomized_and_fresh_render_scalar_behavior():
    rng=random.Random(58769)
    for _ in range(1000):
        inputs=args(width=rng.uniform(-100,5000),height=rng.uniform(-100,5000),
                    reset=rng.choice([False,True]),swap=rng.choice([False,True]))
        assert new().ResolutionAndRatio.execute(**inputs).result == old().ResolutionAndRatio().get_resolution(**inputs)
    assert new().ResolutionAndRatio.execute(**args(custom_presets='1024×2048')).result == (1152,1536)
    assert new().ResolutionAndRatio.execute(**args(scale_percent=200,W_ratio=1,H_ratio=9)).result == (1152,1536)


@pytest.mark.parametrize('overrides',[{'width':True},{'height':None},{'width':float('nan')},{'height':float('inf')},
 {'width':10**100},{'reset':1},{'swap':'true'},{'preset':[]},{'preset':'x'*129},
 {'custom_presets':None},{'custom_presets':'x'*65537},{'custom_presets':'🙂'*16385},{'custom_presets':'\n'*1024}])
def test_malformed_inputs_and_workload_bounds_fail_closed(overrides):
    with pytest.raises((TypeError,ValueError)): new().ResolutionAndRatio.execute(**args(**overrides))


def test_exact_upstream_validation_errors():
    for width,height in [(7,512),(512,4097),(8,4096),(4096,8)]:
        assert new().ResolutionAndRatio.validate_inputs(width,height) == old().ResolutionAndRatio.VALIDATE_INPUTS(width,height)
    assert new().ResolutionAndRatio.execute(**args(custom_presets='a'*65536)).result == (1152,1536)


def test_actual_zero_capability_guest_and_raw_denial():
    node = new().ResolutionAndRatio
    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession('ned-ratio',guest_runtime_root=V2).start()
        try:
            for inputs in [args(),args(width=48,height=80),args(swap=True),args(reset=True),args(width=8,height=32)]:
                plan=_sdk.ExecutionPlan(prompt_id='ratio',node_id='1',node_type=node.__name__,node_module=node.__module__,
                    tier='sandbox',inputs=inputs,input_mode='values',permissions=(),method='execute')
                runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                output=await session.execute(plan,runtime,capabilities=())
                assert output.result == old().ResolutionAndRatio().get_resolution(**inputs)
                assert all(type(x) is int for x in output.result)
            import torch
            ref = await refs.create('IMAGE',torch.zeros(1,1,1,3))
            plan.inputs=args(width=_sdk.ImageRef._wrap(ref))
            with pytest.raises(Exception,match='raw'): await session.execute(plan,runtime,capabilities=())
            await refs.release(ref)
            assert session.last_guest_pid not in (None,os.getpid())
        finally: await session.kill()
    asyncio.run(run())


def test_real_outer_executor_preserves_two_scalar_int_outputs():
    import execution
    node=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_ratio_outer').node_mappings['ResolutionAndRatio']
    async def run():
        previous=_sdk.providers.execution_backend
        class Backend:
            session=None
            async def dispatch(self,plan,local_call,runtime):
                self.session=await GuestSession('ned-ratio-outer',guest_runtime_root=V2).start()
                return await self.session.execute(plan,runtime,capabilities=())
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        try:
            returns=await execution._async_map_node_over_list(prompt_id='ratio',unique_id='1',obj=node,
                input_data_all={k:[v] for k,v in args(width=864,height=1536,swap=True).items()},func=node.FUNCTION,v3_data=None)
            assert len(returns)==1 and returns[0].result==(1536,864)
            assert all(type(v) is int for v in returns[0].result)
            assert tuple(node.RETURN_TYPES)==('INT','INT')
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session:await backend.session.kill()
    asyncio.run(run())


def test_manifest_stubs_pristine_resources_and_cache_hygiene():
    assert json.loads((V2/'secure-nodes.json').read_text()) == manifest()
    for filename,sha in STUBS.items():assert hashlib.sha256((V2/filename).read_bytes()).hexdigest()==sha
    for filename,sha in PRISTINE.items():assert hashlib.sha256((PACK/filename).read_bytes()).hexdigest()==sha
    assert {str(p.relative_to(PACK)) for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)} == set(PRISTINE)
    for filename in ('README.md','LICENSE'):assert (PACK/filename).read_bytes()==(V2/filename).read_bytes()
    for root in (PACK,V2):assert not list(root.rglob('__pycache__')) and not list(root.rglob('*.pyc'))
    source=(V2/'resolution_and_ratio.py').read_text()
    for denied in ('folder_paths','PromptServer','subprocess','requests','_from_raw','open(','eval(','exec('):assert denied not in source
    js=(V2/'web/resolution_and_ratio.js').read_text()
    for denied in ('window.','document.','localStorage','indexedDB','fetch(','LiteGraph','app.','innerHTML'):assert denied not in js


def test_frontend_production_bridge_drag_commit_reload_and_isolation():
    result=subprocess.run(['node',str(V2/'tests/resolution_ratio_bridge_harness.mjs')],text=True,capture_output=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr


def test_exact_artifact_pair_roundtrip(tmp_path):
    metadata,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text())==metadata
    assert PAIR.with_suffix('.diff').read_bytes()==diff.encode()
    fresh=tmp_path/'comfyui_resolution-and-ratio/x58769e5';fresh.mkdir(parents=True)
    shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh,metadata,diff)
    packpatch.validate_tree(fresh/PACK.name/'v2',V2)
