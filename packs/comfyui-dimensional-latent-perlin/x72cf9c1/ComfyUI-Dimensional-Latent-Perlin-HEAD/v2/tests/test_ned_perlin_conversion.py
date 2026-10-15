"""One-node Perlin source, typed model, buffer and exact artifact evidence."""
import ast
import asyncio
import copy
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import pytest
import torch
sys.dont_write_bytecode = True
CORE = Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0] = [str(CORE), '/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu = True
import execution
import comfy.utils
from comfy.model_patcher import ModelPatcher
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb, packpatch
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
DB = SNAPSHOT.parents[2]
PAIR = DB/'patches/comfyui-dimensional-latent-perlin/x72cf9c1/comfyui-dimensional-latent-perlin-x72cf9c1'
ID = 'NoisyLatentPerlinD'
DEFAULT = dict(seed=0,width=1024,height=1024,batch_size=1,detail_level=0,downsample_factor=8)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

OLD=load('ned_oct8_perlin_old',PACK)
NEW=load('ned_oct8_perlin_new',V2)
CLASS=NEW.NODE_CLASS_MAPPINGS[ID]
CLASS.GET_SCHEMA()
MOD=sys.modules[CLASS.__module__]

@pytest.fixture(autouse=True)
def restore_global_rng_and_threads():
    state=torch.random.get_rng_state().clone();threads=torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.random.set_rng_state(state);torch.set_num_threads(threads)

def model(channels=4,patch=None,backup=None):
    inner=torch.nn.Module();inner.latent_format=SimpleNamespace(latent_channels=channels)
    value=ModelPatcher(inner,load_device=torch.device('cpu'),offload_device=torch.device('cpu'))
    if patch is not None:value.object_patches['latent_format']=SimpleNamespace(latent_channels=patch)
    if backup is not None:value.object_patches_backup['latent_format']=SimpleNamespace(latent_channels=backup)
    return value

async def wrapped(refs,kind,value):
    types={'MODEL':_sdk.ModelRef,'LATENT':_sdk.LatentRef}
    return types[kind]._wrap(await refs.create(kind,value))

def old(inputs):
    return OLD.NODE_CLASS_MAPPINGS[ID]().generate_noise(**inputs)[0]

async def new_async(inputs):
    refs=_sdk.InProcessRefResolver();typed=dict(inputs)
    for key,kind in [('model','MODEL'),('latent_image','LATENT')]:
        if typed.get(key) is not None:typed[key]=await wrapped(refs,kind,typed[key])
    with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
        result=await CLASS.execute(**typed)
        return await result.result[0].value()

def new(inputs):return asyncio.run(new_async(inputs))

def same(a,b):
    assert type(a) is type(b) is dict and set(a)==set(b)=={'samples'}
    x,y=a['samples'],b['samples']
    assert type(x) is type(y) is torch.Tensor and x.shape==y.shape and x.dtype==y.dtype and x.device==y.device
    # Exact bits are stricter than numeric equality and include native NaN
    # payloads/signed zeros. torch.equal rejects a NaN even against itself.
    if x.numel():
        assert torch.equal(x.contiguous().view(torch.uint8),y.contiguous().view(torch.uint8))

def manifest():
    return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{ID:{'module':'_secure_nodes','class':CLASS.__name__,
        'sdk_refs':True,'permissions':['raw','inspect'],'methods':{key:False for key in ('validate_inputs','fingerprint_inputs','check_lazy_status')},
        'schema':encode_schema(copy.deepcopy(CLASS.GET_SCHEMA()))}}}

def test_real_pristine_root_census_and_exact_complete_schema():
    assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[ID]
    assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
    schema=CLASS.GET_SCHEMA();schema.validate();source=OLD.NODE_CLASS_MAPPINGS[ID]
    assert schema.node_id==ID and schema.category==source.CATEGORY and schema.display_name==OLD.NODE_DISPLAY_NAME_MAPPINGS[ID]
    assert [o.io_type for o in schema.outputs]==list(source.RETURN_TYPES)
    expected=source.INPUT_TYPES();assert [i.id for i in schema.inputs]==list(expected['required'])+list(expected['optional'])
    for item in schema.inputs:
        spec=(expected['optional'] if item.optional else expected['required'])[item.id]
        assert item.io_type==spec[0]
        if len(spec)>1:
            for key,value in spec[1].items():assert item.as_dict()[key]==value
    assert CLASS.SDK_REFS is True and CLASS.SDK_PERMISSIONS==('raw','inspect')

@pytest.mark.parametrize('seed',[0,1,42,2**63,2**64-1])
@pytest.mark.parametrize('detail',[-1,0,1])
@pytest.mark.parametrize('shape',[(8,8,8),(16,24,8),(39,29,3),(64,40,1)])
def test_all_seed_detail_grid_order_exact_source_and_no_global_rng_mutation(seed,detail,shape):
    width,height,downsample=shape
    inputs=DEFAULT|dict(seed=seed,width=width,height=height,downsample_factor=downsample,detail_level=detail,batch_size=2)
    expected=old(inputs);state=torch.random.get_rng_state().clone()
    same(new(inputs),expected);assert torch.equal(state,torch.random.get_rng_state())

def test_source_default1024_normal_usability_and_repeat_determinism():
    same(new(DEFAULT),old(DEFAULT));same(new(DEFAULT),new(DEFAULT))
    assert new(DEFAULT)['samples'].shape==(1,4,128,128)
    assert torch.isfinite(new(DEFAULT)['samples']).all()

@pytest.mark.parametrize('channels,patch,backup',[(1,None,None),(4,None,None),(16,None,None),(24,None,None),(48,None,None),(128,None,None),(4,16,8),(4,None,8)])
def test_actual_canonical_model_patcher_and_object_patch_precedence(channels,patch,backup):
    original=model(channels,patch,backup)
    inputs=DEFAULT|dict(width=32,height=24,model=original)
    same(new(inputs),old(inputs))
    assert new(inputs)['samples'].shape[1]==original.get_model_object('latent_format').latent_channels

@pytest.mark.parametrize('target',[(1,4,3,4),(3,7,9,10),(2,3,2,4),(1,1,0,4),(0,0,0,0),(1,4,2,3,4)])
@pytest.mark.parametrize('channels',[None,2,16])
def test_optional_latent_model_precedence_repeat_slice_no_batch_or_spatial_expansion(target,channels):
    latent={'samples':torch.zeros(target),'noise_mask':torch.ones(1),'unrelated_metadata':'ignored'}
    inputs=DEFAULT|dict(width=32,height=24,batch_size=2,latent_image=latent)
    if channels is not None:inputs['model']=model(channels)
    same(new(inputs),old(inputs));assert set(new(inputs))=={'samples'}
    assert torch.count_nonzero(latent['samples'])==0

@pytest.mark.parametrize('channels',[0,-1,4097,True,4.0])
def test_unadmitted_model_channels_public_refuses_without_claiming_zero_channel_native_parity(channels):
    inputs=DEFAULT|dict(width=32,height=24,model=model(channels))
    if channels==0 and type(channels) is int:assert old(inputs)['samples'].shape==(1,0,3,4)
    with pytest.raises((ValueError,TypeError)):new(inputs)

def test_native_zero_model_repeat_and_zero_spatial_errors_preserved_separately():
    inputs=DEFAULT|dict(width=32,height=24,model=model(0),latent_image={'samples':torch.zeros(1,4,3,4)})
    with pytest.raises(ZeroDivisionError):old(inputs)
    with pytest.raises(ValueError,match='channels'):new(inputs)
    inputs=DEFAULT|dict(width=8,height=8,downsample_factor=64)
    with pytest.raises(ZeroDivisionError):old(inputs)
    with pytest.raises(ZeroDivisionError):new(inputs)

def test_existing_whole_latent_value_exports_unrelated_opaque_metadata_red_required_guest():
    async def run():
        probe=importlib.import_module(NEW.__name__+'.tests.guest_probe')
        refs=_sdk.InProcessRefResolver()
        ref=await wrapped(refs,'LATENT',{'samples':torch.zeros(1,4,3,4),'unrelated_metadata':object()})
        runtime=_sdk.Runtime(refs=refs,ctx=SimpleNamespace(),ops=_sdk.InProcessOps())
        session=await GuestSession('ned-perlin-metadata-red',guest_runtime_root=V2).start()
        try:
            assert session.sandbox_kind=='seatbelt'
            plan=_sdk.ExecutionPlan(prompt_id='perlin-red',node_id='probe',node_type='LatentMetadataProbe',node_module=probe.__name__,inputs={'latent_image':ref},permissions=('raw',))
            with pytest.raises(Exception,match='cannot export a object'):
                await session.execute(plan,runtime,capabilities=('raw',))
        finally:await session.kill()
    asyncio.run(run())

@pytest.mark.parametrize('target,channels',[(None,4),((3,7,9,10),2),((1,4096,3,4),1),((1,0,3,4),4)])
def test_preflight_exact_repeat_backing_and_no_input_snapshot(target,channels):
    result=MOD.preflight(**(DEFAULT|dict(width=32,height=24)),target_shape=target,latent_channels=channels)
    original=1*channels*3*4*4
    expected=original
    if target is not None and target[1]>channels:expected=original*__import__('math').ceil(target[1]/channels)
    assert result['output_bytes']==original and result['repeat_backing_bytes']==expected
    assert result['input_snapshot_bytes']==0
    assert result['projected_bytes']>=original+3*expected+64*4*3*4

@pytest.mark.parametrize('key,bad',[('seed',-1),('seed',2**64),('width',True),('width',8193),('height',7),
    ('batch_size',0),('batch_size',65),('batch_size',1.0),('downsample_factor',0),('downsample_factor',65),
    ('detail_level',float('nan')),('detail_level',float('inf')),('detail_level',True),('detail_level',1.1)])
def test_closed_scalar_admission_and_global_rng_not_changed(key,bad):
    state=torch.random.get_rng_state().clone()
    with pytest.raises(ValueError):new(DEFAULT|{key:bad})
    assert torch.equal(state,torch.random.get_rng_state())

def test_extreme_output_plane_repeat_and_work_refuse_before_buffer_allocations(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('allocation before preflight')
    for name in ('zeros','empty','rand','arange','stack','meshgrid'):
        monkeypatch.setattr(torch,name,forbidden)
    cases=[dict(width=8192,height=8192,batch_size=64,downsample_factor=1),
           dict(width=8192,height=8192,downsample_factor=1),
           dict(width=1024,height=1024)]
    for options in cases[:2]:
        with pytest.raises(ValueError,match='budget'):MOD.preflight(**(DEFAULT|options))
    with pytest.raises(ValueError,match='budget'):
        MOD.preflight(**DEFAULT,target_shape=(1,4096,128,128),latent_channels=1)
    with pytest.raises(ValueError,match='budget'):
        MOD.preflight(**DEFAULT,latent_channels=4096)

def test_normalized_source_algorithm_ast_only_approved_rng_channel_query_and_repeat_replacement():
    def normalize(path):
        tree=ast.parse(path.read_text())
        tree.body=[n for n in tree.body if not isinstance(n,ast.FunctionDef) and not (isinstance(n,ast.Import) and any(a.name=='comfy.utils' for a in n.names))]
        class Normalize(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                if node.name=='generate_noise':
                    node.args.args[-1].arg='channels_projection'
                return self.generic_visit(node)
            def visit_Expr(self,node):
                if isinstance(node.value,ast.Call) and ast.unparse(node.value.func)=='torch.manual_seed':
                    return ast.Pass()
                return self.generic_visit(node)
            def visit_Assign(self,node):
                if any(ast.unparse(t)=='self._generator' for t in node.targets):return ast.Pass()
                node=self.generic_visit(node)
                if any(isinstance(t,ast.Name) and t.id=='dimensions' for t in node.targets):
                    value=ast.unparse(node.value)
                    if value in ('latent_channels', 'model.get_model_object(\'latent_format\').latent_channels'):
                        node.value=ast.Name(id='channels_projection',ctx=ast.Load())
                return node
            def visit_Compare(self,node):
                node=self.generic_visit(node)
                if isinstance(node.left,ast.Name) and node.left.id in ('model','latent_channels'):
                    node.left=ast.Name(id='channels_projection',ctx=ast.Load())
                return node
            def visit_Call(self,node):
                node=self.generic_visit(node)
                node.keywords=[k for k in node.keywords if k.arg!='generator']
                if ast.unparse(node.func) in ('comfy.utils.repeat_to_batch_size','repeat_to_batch_size'):
                    node.func=ast.Name(id='canonical_repeat',ctx=ast.Load())
                return node
        return ast.dump(Normalize().visit(tree),include_attributes=False)
    assert normalize(PACK/'dimensional_latent_perlin.py')==normalize(V2/'dimensional_latent_perlin.py')

@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16])
def test_admitted_host_default_floating_policy_same_algorithm_without_global_mutation(dtype):
    previous=torch.get_default_dtype()
    try:
        torch.set_default_dtype(dtype)
        inputs=DEFAULT|dict(width=32,height=24)
        same(new(inputs),old(inputs));assert new(inputs)['samples'].dtype==torch.float32
        assert torch.get_default_dtype()==dtype
    finally:torch.set_default_dtype(previous)

def test_native_fp16_default_overflow_nan_control_is_bit_exact_not_repaired():
    previous=torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float16)
        inputs=DEFAULT|dict(width=32,height=24)
        expected=old(inputs);actual=new(inputs)
        assert torch.isnan(expected['samples']).any()
        assert not torch.equal(expected['samples'],expected['samples'])
        assert torch.equal(torch.isnan(actual['samples']),torch.isnan(expected['samples']))
        same(actual,expected)
    finally:torch.set_default_dtype(previous)

def test_two_fresh_required_typed_guests_full_default_model_latent_opaque_metadata_and_denials(tmp_path):
    async def run():
        pids=set();prior=_sdk.providers.execution_backend
        try:
            for generation in range(2):
                root=tmp_path/str(generation);shutil.copytree(V2,root)
                module=load('ned_perlin_fresh_'+str(generation),root)
                cls=module.NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
                session=await GuestSession('ned-perlin-fresh-'+str(generation),guest_runtime_root=root).start()
                assert session.sandbox_kind=='seatbelt'
                capabilities=('raw','inspect')
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        return await session.execute(plan,runtime,capabilities=capabilities,tenant='ned-perlin-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(inputs):
                    value=await execution._async_map_node_over_list(prompt_id='ned-perlin',unique_id='1',obj=cls,
                        input_data_all={k:[v] for k,v in inputs.items()},func=cls.FUNCTION,v3_data=None)
                    value=await execution.resolve_map_node_over_list_results(value)
                    return value[0].result[0]
                try:
                    scenarios=[DEFAULT,
                        DEFAULT|dict(seed=2**64-1,width=32,height=24,batch_size=3),
                        DEFAULT|dict(width=32,height=24,detail_level=-1,model=model(4,16,8)),
                        DEFAULT|dict(width=32,height=24,model=model(4,None,8)),
                        DEFAULT|dict(width=32,height=24,model=model(1)),
                        DEFAULT|dict(width=32,height=24,latent_image={'samples':torch.zeros(3,7,9,10)}),
                        DEFAULT|dict(width=32,height=24,latent_image={'samples':torch.zeros(2,3,2,4)}),
                        DEFAULT|dict(width=32,height=24,latent_image={'samples':torch.zeros(1,4,2,3,4)}),
                        DEFAULT|dict(width=32,height=24,model=model(2),latent_image={'samples':torch.zeros(1,7,3,4)}),
                        DEFAULT|dict(width=32,height=24,model=model(16),latent_image={'samples':torch.zeros(1,2,3,4)}),
                        DEFAULT|dict(width=32,height=24,latent_image={'samples':torch.zeros(0,0,0,0)})]
                    opaque=object();latent={'samples':torch.zeros(1,7,3,4),'noise_mask':torch.ones(1),
                        'unrelated_opaque':opaque,'model_metadata':model(4)}
                    scenarios.append(DEFAULT|dict(width=32,height=24,model=model(2),latent_image=latent))
                    for inputs in scenarios:same(await outer(inputs),old(inputs))
                    assert latent['unrelated_opaque'] is opaque and latent['model_metadata'].get_model_object('latent_format').latent_channels==4
                    assert torch.count_nonzero(latent['samples'])==0
                    with pytest.raises(Exception,match='ZeroDivisionError'):
                        await outer(DEFAULT|dict(width=8,height=8,downsample_factor=64))
                    with pytest.raises(Exception,match='budget'):
                        await outer(DEFAULT|dict(width=8192,height=8192,batch_size=64,downsample_factor=1))
                    for bad in (0,4097,True):
                        with pytest.raises(Exception,match='channels'):
                            await outer(DEFAULT|dict(width=32,height=24,model=model(bad)))
                    with pytest.raises(Exception,match='admitted tensor shape'):
                        await outer(DEFAULT|dict(width=32,height=24,latent_image={'samples':None,'opaque':opaque}))
                    capabilities=('raw',)
                    with pytest.raises(Exception,match='inspect.*not granted'):
                        await outer(DEFAULT|dict(width=32,height=24,latent_image=latent))
                    # No optional LATENT means no inspect operation is requested.
                    same(await outer(DEFAULT|dict(width=32,height=24,model=model(16))),old(DEFAULT|dict(width=32,height=24,model=model(16))))
                    capabilities=('inspect',)
                    with pytest.raises(Exception,match='raw.*not granted|raw.*permission|raw.*capabil'):
                        await outer(DEFAULT|dict(width=32,height=24))
                    capabilities=('raw','inspect')
                    same(await outer(DEFAULT|dict(width=32,height=24,model=model(2),latent_image=latent)),old(DEFAULT|dict(width=32,height=24,model=model(2),latent_image=latent)))
                    pids.add(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(pids)==2 and os.getpid() not in pids
    asyncio.run(run())

def test_actual_production_cloud_backend_typed_outer_model_and_opaque_shape_only_latent():
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        backend=CloudExecutionBackend();prior=_sdk.providers.execution_backend
        _sdk.providers.register_execution_backend(backend)
        try:
            for channels in (4,16):
                inputs=DEFAULT|dict(width=32,height=24,model=model(4,channels,8),latent_image={'samples':torch.zeros(2,7,9,10),'unused_opaque':object()})
                value=await execution._async_map_node_over_list('ned-perlin-production','1',CLASS,{k:[v] for k,v in inputs.items()},CLASS.FUNCTION)
                value=await execution.resolve_map_node_over_list_results(value)
                same(value[0].result[0],old(inputs))
        finally:
            await backend.guests.shutdown();_sdk.providers.register_execution_backend(prior)
    asyncio.run(run())

@pytest.mark.parametrize('initial',[0,1,2,4,7])
@pytest.mark.parametrize('target',[0,1,2,5,8])
def test_retained_canonical_repeat_formula_full_channel_helper_and_native_empty_error(initial,target):
    algorithm=importlib.import_module(NEW.__name__+'.dimensional_latent_perlin')
    tensor=torch.arange(2*initial*3*4,dtype=torch.float32).reshape(2,initial,3,4)
    try:expected=comfy.utils.repeat_to_batch_size(tensor,target,dim=1)
    except Exception as error:
        with pytest.raises(type(error)):algorithm.repeat_to_batch_size(tensor,target,dim=1)
    else:
        actual=algorithm.repeat_to_batch_size(tensor,target,dim=1)
        assert torch.equal(actual,expected) and actual.shape==expected.shape
        assert actual.untyped_storage().nbytes()==expected.untyped_storage().nbytes()

def test_shape_only_latent_opaque_metadata_never_materialized_in_process(monkeypatch):
    class Trap:
        def __repr__(self):raise AssertionError('unused metadata inspected')
        def __str__(self):raise AssertionError('unused metadata stringified')
    opaque=Trap();latent={'samples':torch.ones(3,7,9,10),'opaque':opaque}
    async def forbidden(self):raise AssertionError('LATENT input materialized')
    monkeypatch.setattr(_sdk.LatentRef,'value',forbidden)
    async def run():
        refs=_sdk.InProcessRefResolver();ref=await wrapped(refs,'LATENT',latent)
        with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
            result=await CLASS.execute(**(DEFAULT|dict(width=32,height=24,latent_image=ref)))
        actual=await refs.resolve(result.result[0])
        same(actual,old(DEFAULT|dict(width=32,height=24,latent_image=latent)))
    asyncio.run(run());assert latent['opaque'] is opaque

def test_manifest_pristine_resources_stubs_import_boundary_and_cache_hygiene():
    assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
    provenance=json.loads((V2/'source-provenance.json').read_text())
    pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert pristine==provenance['source_hashes'] and len(pristine)==5
    assert provenance['exact_archive_and_retained_path_bytes'] is True
    for name in ('README.md','LICENSE','assets/Node.png'):assert (V2/name).read_bytes()==(PACK/name).read_bytes()
    assert 'MIT License' in (PACK/'LICENSE').read_text()
    for name,row in provenance['stubs'].items():assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==row['sha256']
    assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
    for name in ('__init__.py','dimensional_latent_perlin.py','_secure_nodes.py'):
        text=(V2/name).read_text()
        for forbidden in ('_from_raw','_wrap(', 'get_model_object','folder_paths','PromptServer','subprocess','requests','torch.manual_seed','eval(', 'exec(', 'open('):
            assert forbidden not in text
        for item in ast.walk(ast.parse(text)):
            if isinstance(item,ast.Import):assert all(a.name in ('torch','math','numpy') for a in item.names)
            if isinstance(item,ast.ImportFrom):assert item.level or item.module=='comfy_api.latest'

def test_live_catalogue_and_exact_registered_node_negative_and_proxy_census():
    catalog=Path('/Users/ben/comfy/ComfyUI_secure_nodes/pack-db/packs/packs.json')
    entries=json.loads(catalog.read_text())
    provenance=json.loads((V2/'source-provenance.json').read_text())
    normalize=lambda s:s.lower().rstrip('/').removesuffix('.git')
    assert not [k for k,v in entries.items() if normalize(v['upstream'])==normalize(provenance['upstream']) or v['commit']==provenance['commit']]
    for path in catalog.parent.rglob('secure-nodes.json'):
        assert ID not in json.loads(path.read_text()).get('nodes',{})
    loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_perlin_proxy')
    assert list(loaded.node_mappings)==[ID] and not loaded.routes and loaded.web_directory is None

def test_stored_pair_and_zip_two_byte_exact_roundtrips_mode_and_wrong_pristine_refusal(tmp_path):
    expected,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text())==expected
    # The pinned source uses CRLF. No universal-newline normalization of the
    # distribution diff is allowed when checking byte-exact reconstruction.
    assert PAIR.with_suffix('.diff').read_bytes().decode('utf-8')==diff
    bundle=packpatch.bundle(expected,diff)
    assert PAIR.with_suffix('.zip').read_bytes()==bundle
    for number in range(2):
        fresh=tmp_path/str(number)/'comfyui-dimensional-latent-perlin/x72cf9c1';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if number==0:packpatch.apply(fresh,expected,diff)
        else:packpatch.apply_bundle(fresh,bundle)
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
        for path in V2.rglob('*'):
            if path.is_file():assert (fresh/PACK.name/'v2'/path.relative_to(V2)).stat().st_mode&0o777==path.stat().st_mode&0o777
    wrong=tmp_path/'wrong/comfyui-dimensional-latent-perlin/x72cf9c1';wrong.mkdir(parents=True)
    shutil.copytree(PACK,wrong/PACK.name,ignore=shutil.ignore_patterns('v2'))
    with (wrong/PACK.name/'dimensional_latent_perlin.py').open('ab') as target:target.write(b'\n#wrong pristine\n')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(wrong,expected,diff)
    assert not (wrong/PACK.name/'v2').exists()
