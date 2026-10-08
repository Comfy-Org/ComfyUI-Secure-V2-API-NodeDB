"""Whole3 source math, true sampler wrapper, required guests and exact artifacts."""
import asyncio
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import pytest
import torch

sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packdb,packmanifest,packpatch,packruntime
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-inversednoise/xacd7773/comfyui-inversednoise-xacd7773'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('amy_inverse_original',PACK)
NEW=load('amy_inverse_converted',V2)
for cls in NEW.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
MOD=sys.modules[NEW.NODE_CLASS_MAPPINGS['MixNoiseNode'].__module__]
IDs=sorted(OLD.NODE_CLASS_MAPPINGS)

def exact(x,y):
    assert x.shape==y.shape and x.dtype==y.dtype
    assert torch.equal(x.contiguous().reshape(-1).view(torch.uint8),y.contiguous().reshape(-1).view(torch.uint8))

def receiver(samples):
    value={'samples':samples,'opaque':object(),'noise_mask':torch.ones(1,2,3),'batch_index':[3,8],'nested':{'marker':object()}}
    value['cycle']=value
    return value

def extras(original,result):
    assert result is not original and set(result)==set(original)
    for key in original.keys()-{'samples'}:assert result[key] is original[key]
    assert result['cycle'] is original

async def local(node,inputs):
    refs=_sdk.InProcessRefResolver()
    wrapped=await _sdk.wrap_inputs(refs,inputs,input_types={'latent':'LATENT','noise':'LATENT','sigmas':'SIGMAS'})
    context=SimpleNamespace(closures=_sdk._InProcessClosures())
    with _sdk.bind_runtime(refs,context,_sdk.InProcessOps()):
        result=await NEW.NODE_CLASS_MAPPINGS[node].execute(**wrapped)
    return await refs.resolve(result.result[0])

def manifest():
    return {'format':packmanifest.FORMAT,'runtime':packruntime.manifest_declaration(V2),'nodes':{
        node:{'module':'nodes','class':cls.__name__,'sdk_refs':True,'permissions':list(cls.SDK_PERMISSIONS),
        'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},
        'schema':packmanifest.encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for node,cls in sorted(NEW.NODE_CLASS_MAPPINGS.items())}}

def test_actual_census_exact_schema_names_permissions_and_proxy():
    assert sorted(NEW.NODE_CLASS_MAPPINGS)==IDs==['CombineNoiseLatentNode','MixNoiseNode','SamplerInversedEulerNode']
    assert NEW.NODE_DISPLAY_NAME_MAPPINGS==OLD.NODE_DISPLAY_NAME_MAPPINGS
    for node,cls in NEW.NODE_CLASS_MAPPINGS.items():
        schema=cls.GET_SCHEMA();schema.validate();source=OLD.NODE_CLASS_MAPPINGS[node]
        assert schema.category==source.CATEGORY and schema.display_name==OLD.NODE_DISPLAY_NAME_MAPPINGS[node]
        assert [i.id for i in schema.inputs]==list(source.INPUT_TYPES()['required'])
        assert [o.io_type for o in schema.outputs]==list(source.RETURN_TYPES)
        for inp in schema.inputs:
            spec=source.INPUT_TYPES()['required'][inp.id];assert inp.io_type==spec[0]
            for key,value in (spec[1] if len(spec)>1 else {}).items():assert inp.as_dict()[key]==value
        assert cls.SDK_REFS is True
    assert NEW.NODE_CLASS_MAPPINGS['CombineNoiseLatentNode'].GET_SCHEMA().outputs[0].display_name=='noise'
    proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_inverse_proxy')
    assert sorted(proxy.node_mappings)==IDs and not proxy.routes and proxy.web_directory is None

@pytest.mark.parametrize('dtype',[torch.float16,torch.bfloat16,torch.float32,torch.float64,torch.complex64,torch.complex128])
@pytest.mark.parametrize('shape',[(),(0,2),(1,2,3),(1,2,1,2,3)])
@pytest.mark.parametrize('randomness',[0.,.1,.5,1.])
def test_mix_one_draw_source_exact_dtype_shape_and_local_rng(monkeypatch,dtype,shape,randomness):
    value=receiver(torch.ones(shape,dtype=dtype));before=torch.random.get_rng_state().clone()
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(783);expected=OLD.MixNoiseNode().mix(value,randomness)[0]
    generators=[]
    def fixed():
        generator=torch.Generator().manual_seed(783);generators.append(generator);return generator
    monkeypatch.setattr(MOD,'local_generator',fixed)
    result=asyncio.run(local('MixNoiseNode',{'latent':value,'randomness':randomness}))
    exact(result['samples'],expected['samples']);extras(value,result)
    oracle=torch.Generator().manual_seed(783);torch.empty_like(value['samples']).normal_(generator=oracle)
    assert len(generators)==1 and torch.equal(generators[0].get_state(),oracle.get_state())
    assert torch.equal(torch.random.get_rng_state(),before)

@pytest.mark.parametrize('style',['transpose','slice','expand','channels_last'])
def test_mix_preserved_noncontiguous_draw_layout(monkeypatch,style):
    x=torch.arange(48,dtype=torch.float32).reshape(2,3,2,4)
    if style=='transpose':x=x.transpose(1,3)
    if style=='slice':x=x[...,::2]
    if style=='expand':x=x[:1].expand(3,-1,-1,-1)
    if style=='channels_last':x=x.contiguous(memory_format=torch.channels_last)
    value=receiver(x)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(91);expected=OLD.MixNoiseNode().mix(value,.1)[0]
    monkeypatch.setattr(MOD,'local_generator',lambda:torch.Generator().manual_seed(91))
    result=asyncio.run(local('MixNoiseNode',{'latent':value,'randomness':.1}))
    exact(result['samples'],expected['samples']);extras(value,result)

@pytest.mark.parametrize('case',[0,1,2,3,4,5])
@pytest.mark.parametrize('sigma',[2.,0.,float('nan'),float('inf')])
def test_combine_native_broadcast_promotion_nonfinite_selected_noise_metadata(case,sigma):
    specs=[((),(),torch.float32,torch.float64),((1,2,1),(3,1,4),torch.float32,torch.float64),
        ((2,1,3),(1,4,1),torch.int64,torch.float32),((1,2,1,2,3),(1,1,1,2,3),torch.float32,torch.bfloat16),
        ((0,2,3),(1,2,3),torch.float32,torch.float32),((1,2,3),(1,2,3),torch.complex64,torch.complex128)]
    a,b,ad,bd=specs[case];latent=receiver(torch.ones(a,dtype=ad));noise=receiver(torch.ones(b,dtype=bd)*3)
    sigmas=torch.tensor([sigma],dtype=torch.float64)
    expected=OLD.CombineNoiseLatentNode().combine(latent,noise,sigmas)[0]
    result=asyncio.run(local('CombineNoiseLatentNode',dict(latent=latent,noise=noise,sigmas=sigmas)))
    exact(result['samples'],expected['samples']);extras(noise,result)
    assert result['opaque'] is not latent['opaque']

@pytest.mark.parametrize('kind',['integer_mix','bool_mix','empty_sigma','scalar_sigma','broadcast_failure'])
def test_native_errors_without_work_or_metadata_substitution(kind):
    latent=receiver(torch.ones(2,3));noise=receiver(torch.ones(2,3));sigmas=torch.tensor([1.])
    node='CombineNoiseLatentNode';values=dict(latent=latent,noise=noise,sigmas=sigmas)
    if kind in ('integer_mix','bool_mix'):
        latent=receiver(torch.ones(2,3,dtype=torch.int64 if kind=='integer_mix' else torch.bool))
        node='MixNoiseNode';values=dict(latent=latent,randomness=.1)
    elif kind=='empty_sigma':values['sigmas']=torch.empty(0)
    elif kind=='scalar_sigma':values['sigmas']=torch.tensor(1.)
    elif kind=='broadcast_failure':values['noise']=receiver(torch.ones(4,5))
    source=OLD.NODE_CLASS_MAPPINGS[node]()
    with pytest.raises(Exception) as native:getattr(source,source.FUNCTION)(**values)
    with pytest.raises(type(native.value)):asyncio.run(local(node,values))

@pytest.mark.parametrize('bad',[True,-.01,1.01,float('nan'),float('inf')])
def test_mix_closed_randomness_refusal(bad):
    with pytest.raises(ValueError,match='randomness'):asyncio.run(local('MixNoiseNode',dict(latent=receiver(torch.ones(2)),randomness=bad)))

def test_budget_refuses_before_draw_and_broadcast_allocation(monkeypatch):
    def no_draw():raise AssertionError('draw reached')
    monkeypatch.setattr(MOD,'local_generator',no_draw)
    with pytest.raises(ValueError,match='byte budget'):MOD.tensor_budget(torch.zeros(1).expand(8_388_609))
    with pytest.raises(ValueError,match='rank'):MOD.tensor_budget(torch.ones((1,)*33))
    with pytest.raises(ValueError,match='workspace'):MOD.work_budget([torch.ones(1)],(2_097_153,),16,3)
    with pytest.raises(ValueError,match='byte'):asyncio.run(local('MixNoiseNode',dict(latent=receiver(torch.zeros(1).expand(8_388_609)),randomness=0.)))
    with pytest.raises(ValueError,match='workspace'):asyncio.run(local('CombineNoiseLatentNode',dict(
        latent=receiver(torch.ones(4097,1)),noise=receiver(torch.ones(1,4097)),sigmas=torch.ones(1))))

class Sampling:
    sigma_max=10
    def noise_scaling(self,sigma,noise,latent,max_denoise):return noise+latent
    def inverse_noise_scaling(self,sigma,samples):return samples
class Model:
    def __init__(self):
        self.seen=[];sampling=Sampling()
        self.model_patcher=SimpleNamespace(model=SimpleNamespace(),get_model_object=lambda name:sampling)
        self.inner_model=SimpleNamespace(model_sampling=sampling,model_patcher=self.model_patcher);self.cfg=1.
    def __call__(self,x,sigma,**kwargs):self.seen.append((x.clone(),sigma.clone(),kwargs));return x-.5

def invoke(sampler,sigmas,events,full=False):
    model=Model();x=torch.ones(1,1,2,3,dtype=sigmas.dtype)
    if full:
        return sampler.sample(model,sigmas,{},lambda i,d,x,n:events.append((i,d.clone(),x.clone(),n)),
            torch.zeros_like(x),latent_image=x,disable_pbar=True)
    return sampler.sampler_function(model,x,sigmas,extra_args={'marker':42},callback=events.append,disable=True)

def event_exact(expected,actual,full):
    assert len(expected)==len(actual)
    for left,right in zip(expected,actual):
        if full:
            assert left[0]==right[0] and left[3]==right[3];exact(left[1],right[1]);exact(left[2],right[2])
        else:
            assert left['i']==right['i'] and type(right['i']) is int
            for key in ('x','denoised','sigma','sigma_hat'):exact(left[key],right[key])

@pytest.mark.parametrize('dtype',[torch.float16,torch.bfloat16,torch.float32,torch.float64])
@pytest.mark.parametrize('values',[[0.,1.,2.],[0.,0.,0.],[.5,1.,1.],[0.,1.]])
@pytest.mark.parametrize('full',[False,True])
def test_sampler_exact_native_onebased_updated_callbacks_and_true_wrapper(dtype,values,full):
    async def run():
        sampler=await local('SamplerInversedEulerNode',{});sigmas=torch.tensor(values,dtype=dtype)
        expected_events=[];expected=await asyncio.to_thread(invoke,OLD.SamplerInversedEulerNode().get_sampler()[0],sigmas,expected_events,full)
        actual=[];result=await asyncio.to_thread(invoke,sampler,sigmas,actual,full)
        exact(result,expected);event_exact(expected_events,actual,full)
        assert (actual[-1][0] if full else actual[-1]['i'])==len(sigmas)-1
    asyncio.run(run())

@pytest.mark.parametrize('values',[[2.,1.,0.],[-1.,0.,1.],[0.,float('nan'),2.],[0.],[0.,float('inf')]])
def test_ascending_admission_refuses_invalid_before_model(values):
    async def run():
        sampler=await local('SamplerInversedEulerNode',{});model=Model()
        with pytest.raises(Exception):await asyncio.to_thread(sampler.sampler_function,model,torch.ones(1,1,2,3),torch.tensor(values))
        assert model.seen==[]
    asyncio.run(run())

@pytest.mark.parametrize('batch',[1,2,8,64])
def test_sampler_batch_sigma_expansion_matches_source_model_arguments(batch):
    async def run():
        sigmas=torch.tensor([0.,.5,1.]);x=torch.ones(batch,1,2,3)
        expected_model=Model();native=[]
        expected=OLD.SamplerInversedEulerNode().get_sampler()[0].sampler_function(expected_model,x,sigmas,extra_args={'marker':42},callback=native.append,disable=True)
        sampler=await local('SamplerInversedEulerNode',{});actual_model=Model();actual=[]
        result=await asyncio.to_thread(sampler.sampler_function,actual_model,x,sigmas,extra_args={'marker':42},callback=actual.append)
        exact(result,expected);event_exact(native,actual,False)
        for left,right in zip(expected_model.seen,actual_model.seen):
            exact(left[0],right[0]);exact(left[1],right[1]);assert left[2]==right[2]
    asyncio.run(run())

def test_two_fresh_required_guests_production_outer_all3_metadata_rng_denial_recovery(tmp_path):
    async def run():
        prior=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
                pack=load('amy_inverse_fresh_'+str(render),fresh)
                for cls in pack.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
                session=await GuestSession('amy-inverse-'+str(render),guest_runtime_root=fresh).start()
                allowed=None
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        caps=tuple(plan.permissions) if allowed is None else allowed
                        return await session.execute(plan,runtime,capabilities=caps,tenant='amy-inverse-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(node,values):
                    cls=pack.NODE_CLASS_MAPPINGS[node]
                    result=await execution._async_map_node_over_list(prompt_id='amy-inverse-outer',unique_id=node,obj=cls,
                        input_data_all={k:[v] for k,v in values.items()},func=cls.FUNCTION,v3_data=None)
                    return result[0].result[0]
                try:
                    assert session.sandbox_kind=='seatbelt'
                    for dtype,shape in [(torch.float32,()),(torch.float64,(0,2)),(torch.bfloat16,(1,2,1,2,3)),(torch.complex64,(1,2,3))]:
                        value=receiver(torch.ones(shape,dtype=dtype));before=torch.random.get_rng_state().clone()
                        mixed=await outer('MixNoiseNode',dict(latent=value,randomness=0.))
                        exact(mixed['samples'],value['samples']);extras(value,mixed)
                        sampled=await outer('MixNoiseNode',dict(latent=value,randomness=1.))
                        assert sampled['samples'].shape==shape and sampled['samples'].dtype==dtype;extras(value,sampled)
                        assert torch.equal(torch.random.get_rng_state(),before)
                    # Source default randomness and ordinary default latent workload.
                    value=receiver(torch.ones(1,4,64,64))
                    sampled=await outer('MixNoiseNode',dict(latent=value,randomness=.1));extras(value,sampled)
                    assert sampled['samples'].std()>.05 and sampled['samples'].std()<.2
                    for sigma in (2.,0.,float('nan')):
                        latent=receiver(torch.ones(1,2,1,dtype=torch.float64));noise=receiver(torch.ones(3,1,4)*3)
                        sigmas=torch.tensor([sigma],dtype=torch.float64)
                        expected=OLD.CombineNoiseLatentNode().combine(latent,noise,sigmas)[0]
                        result=await outer('CombineNoiseLatentNode',dict(latent=latent,noise=noise,sigmas=sigmas))
                        exact(result['samples'],expected['samples']);extras(noise,result)
                    sampler=await outer('SamplerInversedEulerNode',{})
                    for values in ([0.,1.,2.],[0.,0.,0.]):
                        sigmas=torch.tensor(values);native=[];actual=[]
                        expected=await asyncio.to_thread(invoke,OLD.SamplerInversedEulerNode().get_sampler()[0],sigmas,native,True)
                        result=await asyncio.to_thread(invoke,sampler,sigmas,actual,True)
                        exact(result,expected);event_exact(native,actual,True)
                        assert session._closure_capabilities=={} and session._store_reservations==set()
                    for batch in (2,64):
                        x=torch.ones(batch,1,2,3);sigmas=torch.tensor([0.,.5,1.]);native=[];actual=[]
                        expected_model=Model();actual_model=Model()
                        expected=OLD.SamplerInversedEulerNode().get_sampler()[0].sampler_function(expected_model,x,sigmas,extra_args={'marker':42},callback=native.append,disable=True)
                        result=await asyncio.to_thread(sampler.sampler_function,actual_model,x,sigmas,extra_args={'marker':42},callback=actual.append)
                        exact(result,expected);event_exact(native,actual,False)
                        for left,right in zip(expected_model.seen,actual_model.seen):
                            exact(left[1],right[1]);assert left[2]==right[2]
                    allowed=()
                    for node,values in [('MixNoiseNode',dict(latent=value,randomness=.1)),
                        ('CombineNoiseLatentNode',dict(latent=value,noise=value,sigmas=torch.ones(1))),('SamplerInversedEulerNode',{})]:
                        with pytest.raises(Exception,match='raw|closures|permission|capability|granted'):await outer(node,values)
                    allowed=None
                    recovered=await outer('MixNoiseNode',dict(latent=value,randomness=0.));extras(value,recovered)
                    with pytest.raises(Exception,match='workspace'):
                        await outer('CombineNoiseLatentNode',dict(latent=receiver(torch.ones(4097,1)),noise=receiver(torch.ones(1,4097)),sigmas=torch.ones(1)))
                    recovered=await outer('CombineNoiseLatentNode',dict(latent=value,noise=value,sigmas=torch.ones(1)));extras(value,recovered)
                    with pytest.raises(Exception,match='IndexError'):await outer('CombineNoiseLatentNode',dict(latent=value,noise=value,sigmas=torch.empty(0)))
                    recovered=await outer('CombineNoiseLatentNode',dict(latent=value,noise=value,sigmas=torch.ones(1)));extras(value,recovered)
                    pids.append(session.last_guest_pid)
                    print('INVERSE_REQUIRED_OUTER_PID',session.last_guest_pid,session.sandbox_kind,'all3/default/metadata/denial/recovery')
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())

def test_real_guest_ctx_sample_true_canonical_FLOW_diffusion_kernel_and_metadata(tmp_path):
    import comfy.model_base,comfy.supported_models_base,comfy.latent_formats,comfy.model_patcher,comfy.sample
    class Config(comfy.supported_models_base.BASE):
        latent_format=comfy.latent_formats.LatentFormat
    class Kernel(torch.nn.Module):
        def __init__(self):super().__init__();self.bias=torch.nn.Parameter(torch.zeros(()));self.dtype=torch.float32
        def forward(self,x,timesteps,context=None,**kwargs):
            shape=(x.shape[0],)+(1,)*(x.ndim-1)
            return x*.125+timesteps.to(x).reshape(shape)*.00001+self.bias
    config=Config({'disable_unet_model_creation':True,'in_channels':4})
    model=comfy.model_base.BaseModel(config,comfy.model_base.ModelType.FLOW,device=torch.device('cpu'))
    model.diffusion_model=Kernel()
    patcher=comfy.model_patcher.ModelPatcher(model,torch.device('cpu'),torch.device('cpu'))
    positive=[[torch.ones((1,2,4)),{}]];negative=[[torch.zeros((1,2,4)),{}]]
    async def run():
        from amy_inverse_converted.tests.entry_probe import InverseEntryProbe
        refs=_sdk.InProcessRefResolver();session=await GuestSession('amy-inverse-full-FLOW',guest_runtime_root=V2).start()
        runtime=_sdk.Runtime(refs=refs,ctx=SimpleNamespace(),ops=_sdk.InProcessOps())
        try:
            assert session.sandbox_kind=='seatbelt'
            for values in ([0.,.5,1.],[0.,0.,0.]):
                sigmas=torch.tensor(values);latent=receiver(torch.ones(1,4,4,4))
                # No model=None, no recorded sample_custom/diffusion substitution.
                expected=await asyncio.to_thread(comfy.sample.sample_custom,patcher,torch.zeros_like(latent['samples']),1.,
                    OLD.SamplerInversedEulerNode().get_sampler()[0],sigmas,positive,negative,latent['samples'],disable_pbar=True)
                wrapped=await _sdk.wrap_inputs(refs,{'model':patcher,'latent':latent,'sigmas':sigmas,'positive':positive,'negative':negative},
                    input_types={'model':'MODEL','latent':'LATENT','sigmas':'SIGMAS','positive':'CONDITIONING','negative':'CONDITIONING'})
                plan=_sdk.ExecutionPlan(prompt_id='amy-inverse-full',node_id='1',node_type='InverseEntryProbe',
                    node_module=InverseEntryProbe.__module__,inputs=wrapped)
                output=await session.execute(plan,runtime,capabilities=('closures','sample'))
                actual=await refs.resolve(output.result[0]);exact(actual['samples'],expected);extras(latent,actual)
                assert session._closure_capabilities=={} and session._store_reservations==set()
            print('INVERSE_ACTUAL_CANONICAL_FLOW',session.last_guest_pid,'CPU synthetic kernel/untrained; real sample_custom+KSAMPLER+guest ctx.sample')
        finally:await session.kill()
    asyncio.run(run())

def test_pristine_resources_git_blobs_manifest_stubs_and_hygiene():
    assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
    provenance=json.loads((V2/'source-provenance.json').read_text())
    assert provenance['git_blob_path_mode_match'] is True and len(provenance['source_hashes'])==5
    actual={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert actual==provenance['source_hashes']
    for rel in ('.gitignore','README.md','example_workflow/example_noise_inversion.json'):assert (PACK/rel).read_bytes()==(V2/rel).read_bytes()
    for name,expected in [('comfy-api.pyi','55d56d8d40913a2c5c9cba6f81ac9035d4d1f600099b1f03ae345b3b9dd6a949'),
        ('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:
        assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==expected
    active=(V2/'nodes.py').read_text()
    for forbidden in ('_wrap(','.value()', 'folder_paths','from comfy.','subprocess','requests','eval(','exec(','open('):assert forbidden not in active
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('*.js'))
    report=(V2/'SECURE_CONVERSION.md').read_text()
    for node in IDs:assert f'| {node} | supported |' in report
    assert 'NO LICENSE' in report and 'Cloud' in report

def test_exact_pair_zip_twice_and_wrong_pristine_denial(tmp_path):
    pair,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_text())==pair and PAIR.with_suffix('.diff').read_text()==diff
    for index in range(2):
        fresh=tmp_path/str(index)/'comfyui-inversednoise/xacd7773';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if index==0:packpatch.apply(fresh,pair,diff)
        else:packpatch.apply_bundle(fresh,packpatch.bundle(pair,diff))
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
    fresh=tmp_path/'wrong/comfyui-inversednoise/xacd7773';fresh.mkdir(parents=True)
    shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
    (fresh/PACK.name/'README.md').write_text('wrong pristine')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,pair,diff)
    assert not (fresh/PACK.name/'v2').exists()
