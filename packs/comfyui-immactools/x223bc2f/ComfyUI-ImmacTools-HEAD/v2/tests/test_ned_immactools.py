"""Exact source, all-nine typed guest/outer and ownership controls."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import pytest
import torch
import numpy as np
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
OVERLAY=Path(os.environ.get('NED_OVERLAY_ROOT','/Users/ben/comfy/ComfyUI_secure_nodes-many-oct8-owner-provider'))
sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy.cli_args import args
args.cpu=True
import execution
from comfy_api.latest import _sdk
from comfy.model_patcher import ModelPatcher
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packpatch,packdb
V2=Path(__file__).resolve().parents[1]
PACK=V2.parent
IDS=['ConcatenateSigmasImmacTools','SpliceSigmasAtImmacTools','ResampleSigmasImmacTools',
     'SkipEveryNthImagesImmacTools','MatchContrastImmacTools','SwitchImmacTools',
     'ForwardAnyImmacTools','ForwardConditioningImmacTools','ForwardModelImmacTools']
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p/'__init__.py',submodule_search_locations=[str(p)])
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
OLD=load('ned_immac_old',PACK)
NEW=load('ned_immac_new',V2)
for cls in [*OLD.NODE_CLASS_MAPPINGS.values(),*NEW.NODE_CLASS_MAPPINGS.values()]: cls.GET_SCHEMA()
GUARD=sys.modules[NEW.__name__+'._bounded']

def source(id,inputs): return OLD.NODE_CLASS_MAPPINGS[id].execute(**inputs).result
async def new_async(id,inputs):
    refs=_sdk.InProcessRefResolver()
    cls=NEW.NODE_CLASS_MAPPINGS[id]
    hints={x.id:x.io_type for x in cls.GET_SCHEMA().inputs}
    typed=await _sdk.wrap_inputs(refs,inputs,hints)
    with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
        result=cls.execute(**typed)
        if hasattr(result,'__await__'): result=await result
        return (await _sdk.unwrap_outputs(refs,result)).result
def converted(id,inputs): return asyncio.run(new_async(id,inputs))
def same(a,b):
    assert type(a) is type(b)
    if isinstance(a,torch.Tensor):
        assert a.shape==b.shape and a.dtype==b.dtype and a.device==b.device
        assert torch.equal(a.contiguous().reshape(-1).view(torch.uint8),b.contiguous().reshape(-1).view(torch.uint8))
    elif type(a) in (list,tuple):
        assert len(a)==len(b)
        for x,y in zip(a,b): same(x,y)
    elif a is None or type(a) in (str,int,float,bool):
        assert a==b or (isinstance(a,float) and np.isnan(a) and np.isnan(b))
    else: assert a is b
def compare(id,inputs):
    try: expected=source(id,inputs)
    except Exception as e:
        with pytest.raises(type(e)): converted(id,inputs)
    else: same(converted(id,inputs),expected)

def manifest():
    return {'format':FORMAT,'runtime':manifest_declaration(V2),'web_directory':'web/js',
      'nodes':{id:{'module':'_secure_nodes','class':cls.__name__,'sdk_refs':True,
      'permissions':list(cls.SDK_PERMISSIONS),
      'methods':{'validate_inputs':False,'fingerprint_inputs':False,'check_lazy_status':True},
      'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for id,cls in NEW.NODE_CLASS_MAPPINGS.items()}}

def test_full_actual_v3_legacy_nine_schema_lazy_census_and_source_algorithms_unchanged():
    assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==IDS
    assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
    assert [c.GET_SCHEMA().node_id for c in asyncio.run(NEW.ImmacToolsExtension().get_node_list())]==IDS
    for id in IDS:
        old,new=OLD.NODE_CLASS_MAPPINGS[id],NEW.NODE_CLASS_MAPPINGS[id]
        assert encode_schema(old.GET_SCHEMA())==encode_schema(new.GET_SCHEMA())
        assert new.SDK_REFS
        new.GET_SCHEMA().validate()
    for name in ('src/immac_tools/nodes.py','src/immac_tools/forwarding_nodes.py'):
        assert (PACK/name).read_bytes()==(V2/name).read_bytes()

@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16,torch.int64])
@pytest.mark.parametrize('a,b',[(None,[2,1]),([3,2],None),([3,2],[2,1]),([3,2],[1,0]),
    ([],[2,1]),([3,2],[]),([2],[2]),([2],[2.0000001]),(3,2),([[3,2]],[[2,1]])])
def test_concat_source_comparison_dedup_dtype_empty_scalar_native_errors(dtype,a,b):
    f=lambda x:None if x is None else torch.tensor(x,dtype=dtype)
    compare(IDS[0],dict(sigmas_1=f(a),sigmas_2=f(b)))

@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16,torch.int64])
@pytest.mark.parametrize('boundary',[-1,0,0.5,1,2,'invalid',float('nan')])
@pytest.mark.parametrize('include',[False,True])
def test_splice_exact_masks_boundary_rounding_order(dtype,boundary,include):
    compare(IDS[1],dict(sigmas_a=torch.tensor([5,3,1,0],dtype=dtype),
        sigmas_b=torch.tensor([4,2,0],dtype=dtype),boundary=boundary,include_boundary=include))

@pytest.mark.parametrize('value',[None,2,[2],[3,2,0],[],[[3,2],[2,1]],[[2,1]]])
@pytest.mark.parametrize('steps',[1,10,0,-1,'invalid'])
@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16,torch.int64])
def test_resample_all_source_branches_default_singleton_native_defect(value,steps,dtype):
    x=None if value is None else torch.tensor(value,dtype=dtype)
    compare(IDS[2],dict(sigmas=x,steps=steps))

@pytest.mark.parametrize('value',[None,'abc',[],[1,2,3],(1,2,3),torch.tensor(1),
    torch.empty(0,2),torch.arange(5*2*3).reshape(5,2,3)])
@pytest.mark.parametrize('n',[-1,0,1,2,7,'invalid'])
def test_skip_tensor_sequence_order_native_empty_and_fallback(value,n):
    compare(IDS[3],dict(images=value,n=n))

@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
@pytest.mark.parametrize('mode',['rgb','luminance','other'])
@pytest.mark.parametrize('strength',[-1,0,0.3,1,2,float('nan')])
def test_exact_histogram_lab_batch_reference_last_frame_math(dtype,mode,strength):
    image=torch.linspace(0,1,3*4*5*3).reshape(3,4,5,3).to(dtype)
    reference=torch.linspace(0.9,0.1,2*3*4*3).reshape(2,3,4,3).to(dtype)
    compare(IDS[4],dict(image=image,reference=reference,channel_mode=mode,strength=strength))

@pytest.mark.parametrize('shape,ref',[( (0,3,4,3),(1,3,4,3)),((1,3,4,3),(0,3,4,3)),
    ((1,3,4,2),(1,3,4,2)),((1,0,4,3),(1,3,4,3)),((1,3),(1,3))])
def test_image_native_rank_empty_and_channel_errors(shape,ref):
    compare(IDS[4],dict(image=torch.zeros(shape),reference=torch.ones(ref),channel_mode='luminance',strength=1))

@pytest.mark.parametrize('mode',['rgb','luminance'])
def test_normal256_image_source_default_strength_channel_usability(mode):
    image=torch.linspace(0,1,256*256*3).reshape(1,256,256,3)
    compare(IDS[4],dict(image=image,reference=1-image,channel_mode=mode,strength=1))

@pytest.mark.parametrize('dtype1,dtype2',[(torch.float32,torch.float64),(torch.float16,torch.float32),(torch.int64,torch.float64)])
def test_concat_native_dtype_policy_and_noncontiguous_inputs(dtype1,dtype2):
    compare(IDS[0],dict(sigmas_1=torch.tensor([4,3,2,1],dtype=dtype1)[::2],
                       sigmas_2=torch.tensor([2,9,1,8],dtype=dtype2)[::2]))

@pytest.mark.parametrize('count',[1,5,20])
@pytest.mark.parametrize('index',[-1,0,1,4,19,20])
@pytest.mark.parametrize('one',[False,True])
def test_switch_exact_selected_any_identity_no_unselected_traversal(count,index,one):
    values={f'input_{i}':object() for i in range(20)}
    compare(IDS[5],dict(num_inputs=count,index=index,one_indexed=one,**values))

def test_forward_all_zero_capability_host_identities_inprocess():
    model=ModelPatcher(torch.nn.Linear(2,2),load_device=torch.device('cpu'),offload_device=torch.device('cpu'))
    opaque=object();cond=[[torch.ones(1,2,3),{'control':opaque,'pooled_output':torch.ones(1,3)}]]
    for id,inputs in [(IDS[6],{'value':{'model':model,'value':opaque}}),(IDS[7],{'conditioning':cond}),(IDS[8],{'model':model})]:
        result=converted(id,inputs)[0]
        if id==IDS[6]: assert result['model'] is model and result['value'] is opaque
        else: assert result is next(iter(inputs.values()))

def test_metadata_only_pre_raw_ownership_refusals_admitted_native_errors_and_recovery(monkeypatch):
    async def forbidden(value): raise AssertionError('raw before resource plan')
    module=sys.modules[NEW.__name__+'._secure_nodes']
    monkeypatch.setattr(module,'raw',forbidden)
    async def huge(value): return (( (8_388_608,),8_388_608,8_388_608*8),8)
    monkeypatch.setattr(module,'description',huge)
    for id,inputs in [(IDS[0],{'sigmas_1':1,'sigmas_2':1}),
        (IDS[1],dict(sigmas_a=1,sigmas_b=1,boundary=.5,include_boundary=True)),
        (IDS[2],dict(sigmas=1,steps=1)),(IDS[4],dict(image=1,reference=1,channel_mode='rgb',strength=1)),
        (IDS[3],dict(images=_sdk.TensorRef._wrap(_sdk.Ref('probe','TENSOR')),n=2))]:
        with pytest.raises(ValueError,match='budget'): asyncio.run(NEW.NODE_CLASS_MAPPINGS[id].execute(**inputs))
    GUARD.sigma_plan('resample',[(((3,),3,12),4)],10)
    with pytest.raises(ValueError,match='budget'): GUARD.sigma_plan('resample',[(((3,),3,12),4)],2**40)
    with pytest.raises(ValueError,match='budget'): GUARD.image_plan([(((64,512,512,3),50_331_648,201_326_592),4)]*2)

def scenarios():
    model=ModelPatcher(torch.nn.Linear(2,2),load_device=torch.device('cpu'),offload_device=torch.device('cpu'))
    opaque=object();cond=[[torch.ones(1,2,3),{'control':opaque,'cyclic':None}]];cond[0][1]['cyclic']=cond[0][1]
    return [
      (IDS[0],dict(sigmas_1=torch.tensor([3.,2.]),sigmas_2=torch.tensor([2.,1.]))),
      (IDS[1],dict(sigmas_a=torch.tensor([3.,2.,0.]),sigmas_b=torch.tensor([2.,1.,0.]),boundary=.5,include_boundary=True)),
      (IDS[2],dict(sigmas=torch.tensor([3.,2.,0.]),steps=10)),
      (IDS[3],dict(images=torch.arange(5*2*3).reshape(5,2,3),n=2)),
      (IDS[4],dict(image=torch.linspace(0,1,2*4*5*3).reshape(2,4,5,3),reference=torch.ones(1,3,4,3)*.25,channel_mode='luminance',strength=.3)),
      (IDS[5],dict(num_inputs=2,index=0,one_indexed=False,input_0=model,input_1=opaque)),
      (IDS[6],dict(value=model)),(IDS[7],dict(conditioning=cond)),(IDS[8],dict(model=model))]

def test_all_nine_two_fresh_required_guests_actual_outer_types_identity_native_errors_denial_recovery(tmp_path):
    async def run():
        prior=_sdk.providers.execution_backend;pids=set()
        try:
            for generation in range(2):
                root=tmp_path/str(generation);shutil.copytree(V2,root)
                mod=load('ned_immac_fresh_'+str(generation),root)
                session=await GuestSession('ned-immac-'+str(generation),guest_runtime_root=root).start()
                assert session.sandbox_kind=='seatbelt'
                capabilities=('raw','inspect')
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        return await session.execute(plan,runtime,capabilities=capabilities,tenant='ned-immac-fixture')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(id,inputs):
                    cls=mod.NODE_CLASS_MAPPINGS[id];cls.GET_SCHEMA()
                    value=await execution._async_map_node_over_list('ned-immac','1',cls,{k:[v] for k,v in inputs.items()},cls.FUNCTION)
                    value=await execution.resolve_map_node_over_list_results(value)
                    return value[0].result
                try:
                    for id,inputs in scenarios():
                        if id in IDS[5:]: capabilities=()
                        else: capabilities=('raw','inspect')
                        actual=await outer(id,inputs);expected=source(id,inputs)
                        same(actual,expected)
                    capabilities=('raw','inspect')
                    same(await outer(IDS[3],dict(images=[1,2,3,4],n=2)),([1,3],[1,3]))
                    for dtype in (torch.float16,torch.float64,torch.bfloat16):
                        same(await outer(IDS[0],dict(sigmas_1=torch.tensor([3,2],dtype=dtype),sigmas_2=torch.tensor([2,1],dtype=dtype))),source(IDS[0],dict(sigmas_1=torch.tensor([3,2],dtype=dtype),sigmas_2=torch.tensor([2,1],dtype=dtype))))
                    with pytest.raises(Exception,match='repeat|dimensions'):
                        await outer(IDS[2],dict(sigmas=torch.tensor([1.]),steps=10))
                    with pytest.raises(Exception,match='BFloat16|bfloat16'):
                        await outer(IDS[4],dict(image=torch.ones(1,2,3,3,dtype=torch.bfloat16),reference=torch.ones(1,2,3,3),channel_mode='rgb',strength=1))
                    with pytest.raises(Exception,match='budget'):
                        await outer(IDS[2],dict(sigmas=torch.tensor([3.,2.]),steps=2**40))
                    # Real metadata-only tensors: a raw request would fail meta
                    # export rather than the pack resource projection. No large
                    # real buffer or broad memory grant is exercised.
                    with pytest.raises(Exception,match='budget'):
                        await outer(IDS[0],dict(sigmas_1=torch.empty(8_388_608,device='meta'),sigmas_2=torch.empty(8_388_608,device='meta')))
                    with pytest.raises(Exception,match='budget'):
                        await outer(IDS[4],dict(image=torch.empty(1,512,512,3,device='meta'),reference=torch.empty(1,512,512,3,device='meta'),channel_mode='luminance',strength=1))
                    capabilities=('inspect',)
                    with pytest.raises(Exception,match='raw.*not granted|raw.*permission|raw.*capabil'):
                        await outer(*scenarios()[0])
                    capabilities=('raw',)
                    with pytest.raises(Exception,match='inspect.*not granted|inspect.*permission'):
                        await outer(*scenarios()[0])
                    capabilities=('raw','inspect');same(await outer(*scenarios()[0]),source(*scenarios()[0]))
                    pids.add(session.last_guest_pid)
                finally: await session.kill()
        finally: _sdk.providers.register_execution_backend(prior)
        assert len(pids)==2 and os.getpid() not in pids
    asyncio.run(run())

def test_production_overlay_cloud_backend_all_nine_real_outer():
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        backend=CloudExecutionBackend();prior=_sdk.providers.execution_backend
        _sdk.providers.register_execution_backend(backend)
        try:
            for id,inputs in scenarios():
                cls=NEW.NODE_CLASS_MAPPINGS[id]
                value=await execution._async_map_node_over_list('ned-immac-production','1',cls,{k:[v] for k,v in inputs.items()},cls.FUNCTION)
                value=await execution.resolve_map_node_over_list_results(value)
                same(value[0].result,source(id,inputs))
        finally:
            await backend.guests.shutdown();_sdk.providers.register_execution_backend(prior)
    asyncio.run(run())

def test_pristine_git_hash_modes_resources_license_and_no_bytecode():
    packet=json.loads(Path('/Users/ben/popbot/raw-chats/outputs/ned-oct8-immactools-screen/screen.json').read_text())
    for row in packet['files']:
        p=PACK/row['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
        assert p.stat().st_mode&511==row['mode']
    assert len(packet['files'])==22
    assert 'MIT License' in (PACK/'LICENSE').read_text()
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))

def test_final_manifest_and_exact_pair_zip_two_roundtrips(tmp_path):
    stored=json.loads((V2/'secure-nodes.json').read_text());assert stored==manifest()
    db=PACK.parents[3];pair=db/'patches/comfyui-immactools/x223bc2f/comfyui-immactools-x223bc2f'
    recorded=json.loads(pair.with_suffix('.json').read_text());diff=pair.with_suffix('.diff').read_text()
    actual,delta=packpatch.generate(PACK.parent)
    assert recorded==actual and diff==delta
    bundle=pair.with_suffix('.zip').read_bytes()
    assert bundle==packpatch.bundle(recorded,diff)
    for i in range(2):
        root=tmp_path/str(i)/'comfyui-immactools/x223bc2f'
        shutil.copytree(PACK,root/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if i==0: packpatch.apply(root,recorded,diff)
        else: packpatch.apply_bundle(root,bundle)
        def data(p):return {str(f.relative_to(p)):(f.read_bytes(),f.stat().st_mode&511) for f in p.rglob('*') if f.is_file()}
        assert data(root/PACK.name/'v2')==data(V2)
    wrong=tmp_path/'wrong/comfyui-immactools/x223bc2f'
    shutil.copytree(PACK,wrong/PACK.name,ignore=shutil.ignore_patterns('v2'))
    target=wrong/PACK.name/'README.md'
    target.write_bytes(target.read_bytes()+b'\nwrong pristine\n')
    with pytest.raises(packpatch.PackPatchError): packpatch.apply(wrong,recorded,diff)
    assert not (wrong/PACK.name/'v2').exists()

def test_real_manifest_proxy_all_nine_web_scope_and_current_negative_census():
    proxy=packdb.load_pack(PACK.parent,mount_name='custom_nodes.ned_immac_proxy')
    assert list(proxy.node_mappings)==IDS and not proxy.routes
    assert proxy.web_directory is not None
    for id,cls in proxy.node_mappings.items():
        assert cls.GET_SCHEMA().node_id==id
    catalog=Path('/Users/ben/comfy/ComfyUI_secure_nodes/pack-db/packs/packs.json')
    entries=json.loads(catalog.read_text())
    normalized=lambda x:x.lower().rstrip('/').removesuffix('.git')
    assert not any(normalized(v['upstream'])=='https://github.com/immac/comfyui-immactools' for v in entries.values())
    for p in catalog.parent.rglob('secure-nodes.json'):
        assert not set(IDS)&set(json.loads(p.read_text()).get('nodes',{}))
