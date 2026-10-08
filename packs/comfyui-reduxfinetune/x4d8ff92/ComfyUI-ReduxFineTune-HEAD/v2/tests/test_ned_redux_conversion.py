"""Exact pinned math, typed registered entrypoints, confined guests and artifacts."""
import ast
import asyncio
import copy
from functools import lru_cache
import gc
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import numpy as np
import pytest
import torch
import torch.nn.functional as F
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution
import comfy.sd
import comfy.clip_vision
from comfy.ldm.flux.redux import ReduxImageEncoder
from comfy.t2i_adapter.adapter import StyleAdapter
from comfy.hooks import HookGroup
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;DB=PACK.parents[3]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
NEW=load('ned_redux_owned',V2)
NODES=NEW.NODE_CLASS_MAPPINGS
for cls in NODES.values():cls.GET_SCHEMA().validate()
MATH=sys.modules[NEW.__name__+'._math'];WRAP=sys.modules[NEW.__name__+'._secure_nodes']
OLD={'torch':torch,'math':math,'F':F,'lru_cache':lru_cache,'gc':gc}
tree=ast.parse((PACK/'ReduxFineTune.py').read_text())
selected=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
exec(compile(ast.Module(body=selected,type_ignores=[]),str(PACK/'ReduxFineTune.py'),'exec'),OLD)
loader_env={'torch':torch,'np':np,'folder_paths':SimpleNamespace(get_filename_list=lambda x:[])}
cls=next(n for n in ast.parse((PACK/'ClipVisionStyleLoader.py').read_text()).body if isinstance(n,ast.ClassDef))
exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'ClipVisionStyleLoader.py'),'exec'),loader_env)
OLD_LOADER=loader_env['ClipVisionStyleLoader']

@pytest.fixture(autouse=True)
def ambient_state():
    state=torch.random.get_rng_state().clone();threads=torch.get_num_threads();torch.set_num_threads(1)
    yield
    torch.random.set_rng_state(state);torch.set_num_threads(threads)
    for name in ('get_sharpen_kernel','_get_fft_params','_get_fusion_strength'):OLD[name].cache_clear()
    OLD['ReduxFineTuneAdvanced']._get_interpolated_mask.cache_clear()

def features(dtype=torch.float32,shape=(1,4,10)):
    return torch.linspace(-.4,.7,math.prod(shape),dtype=dtype).reshape(shape)
def rows(dtype=torch.float32,count=2,channels=10):
    meta={'pooled_output':torch.ones(1,channels,dtype=dtype),'hooks':HookGroup(),'control':object(),'opaque':object()}
    meta['cycle']=meta
    return [[torch.linspace(-.2,.8,(i+2)*channels,dtype=dtype).reshape(1,i+2,channels),meta] for i in range(count)]
def canonical(dtype=torch.float32,adapter=False):
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7)
        model=StyleAdapter(width=8,context_dim=10,num_head=2,n_layes=1,num_token=8) if adapter else ReduxImageEncoder(redux_dim=6,txt_in_features=10,dtype=dtype)
        with torch.no_grad():
            for i,param in enumerate(model.parameters()):param.copy_(torch.linspace(-.03,.04,param.numel(),dtype=param.dtype).reshape(param.shape)+i*.001)
    out=comfy.clip_vision.Output();out.last_hidden_state=features(dtype,(1,4,8 if adapter else 6));out.unused=object()
    out.image_embeds=torch.zeros(1,8 if adapter else 6,dtype=dtype)
    out.penultimate_hidden_states=out.last_hidden_state
    return comfy.sd.StyleModel(model),out

def canonical_vision(channels=6):
    config={'model_type':'siglip_vision_model','hidden_size':channels,'intermediate_size':channels*2,
            'num_attention_heads':2,'num_hidden_layers':2,'hidden_act':'gelu','num_channels':3,
            'patch_size':4,'image_size':8,'layer_norm_eps':1e-5}
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(31);encoder=comfy.clip_vision.ClipVisionModel(config)
        with torch.no_grad():
            for i,param in enumerate(encoder.model.parameters()):
                param.copy_(torch.linspace(-.04,.04,param.numel(),dtype=param.dtype).reshape(param.shape)+i*.001)
    return encoder

def advanced_inputs(mode='Mix',super_redux=False,crop='none',mask=True):
    model,_=canonical();image=torch.linspace(0,1,1*8*10*3).reshape(1,8,10,3)
    inputs=dict(conditioning=rows(count=1),style_model=model,clip_vision=canonical_vision(),image=image,
                crop=crop,fusion_mode=mode,style_strength=.7,color_strength=.3,content_strength=.2,
                structure_strength=.1,texture_strength=.4,prompt_strength=1.2,
                feature_noise=0.,feature_resolution=16,SUPER_REDUX=super_redux)
    if mask:
        value=torch.zeros(1,8,10);value[:,1:7,2:8]=1;inputs['mask']=value
    return inputs

def assert_rows(actual,expected,original=None):
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        torch.testing.assert_close(a[0],b[0],rtol=0,atol=0,equal_nan=True)
        assert a[0].dtype==b[0].dtype
    if original is not None:
        for a,b in zip(actual,original):
            assert a[1] is not b[1]
            assert set(a[1])==set(b[1])
            for key in b[1]:assert a[1][key] is b[1][key]

async def typed_execute(name,inputs,ctx=None):
    refs=_sdk.InProcessRefResolver();types={'conditioning':('CONDITIONING',_sdk.CondRef),'style_model':('STYLE_MODEL',_sdk.StyleModelRef),'clip_vision_output':('CLIP_VISION_OUTPUT',_sdk.ClipVisionOutputRef),'clip_vision':('CLIP_VISION',_sdk.ClipVisionRef),'image':('IMAGE',_sdk.ImageRef),'mask':('MASK',_sdk.MaskRef)}
    typed={}
    for key,value in inputs.items():
        if key in types and value is not None:
            kind,cls=types[key];typed[key]=cls._wrap(await refs.create(kind,value))
        else:typed[key]=value
    with _sdk.bind_runtime(refs,ctx,_sdk.InProcessOps()):out=await NODES[name].execute(**typed)
    return tuple([await refs.resolve(v) if isinstance(v,_sdk.Ref) else v for v in out.result])

def manifest():
    return {'format':FORMAT,'runtime':manifest_declaration(V2),'web_directory':'web','nodes':{name:{'module':'_secure_nodes','class':cls.__name__,'sdk_refs':True,'permissions':list(cls.SDK_PERMISSIONS),'methods':{key:False for key in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for name,cls in NODES.items()}}

def test_full_pinned_loader_census_schema_and_frontend_scope():
    init=ast.parse((PACK/'__init__.py').read_text());maps={}
    for module in ('ClipVisionStyleLoader.py','ReduxFineTune.py'):
        for n in ast.parse((PACK/module).read_text()).body:
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NODE_CLASS_MAPPINGS' for t in n.targets):maps.update({ast.literal_eval(k):v.id for k,v in zip(n.value.keys,n.value.values)})
    assert set(maps)==set(NODES)=={'ReduxFineTune','ReduxFineTuneAdvanced','ClipVisionStyleLoader'}
    for name,node in NODES.items():
        old=OLD_LOADER if name=='ClipVisionStyleLoader' else OLD[name]
        expected=old.INPUT_TYPES();schema=node.GET_SCHEMA()
        assert schema.node_id==name and schema.category==old.CATEGORY
        assert [i.id for i in schema.inputs]==list(expected['required'])+list(expected.get('optional',{}))
        assert [o.io_type for o in schema.outputs]==list(old.RETURN_TYPES)
        for item in schema.inputs:
            spec=(expected['optional'] if item.optional else expected['required'])[item.id]
            assert item.io_type==('COMBO' if isinstance(spec[0],list) else spec[0])
            for k,v in (spec[1] if len(spec)>1 else {}).items():assert item.as_dict()[k]==v
        if name=='ClipVisionStyleLoader':
            assert [o.is_output_list for o in schema.outputs]==[True,False,False]
            assert [i.as_dict()['remote']['route'] for i in schema.inputs[:2]]==['/secure-nodes/models/clip_vision','/secure-nodes/models/style_models']
    assert NEW.WEB_DIRECTORY=='./web'
    assert len(list((PACK/'web').rglob('*.js')))==1

def test_actual_pristine_dynamic_root_import_census_and_display_names():
    # The reviewed root imports exactly the two source modules and prints its
    # version. No imports start services/downloads; bytecode writes are disabled.
    old=load('ned_redux_pristine_dynamic',PACK)
    assert set(old.NODE_CLASS_MAPPINGS)==set(NODES)
    assert old.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
    assert old.__version__==NEW.__version__=='1.1.0'
    assert old.WEB_DIRECTORY==NEW.WEB_DIRECTORY=='./web'

def test_normalized_fusion_ast_equations_exact_only_cache_rng_changes():
    new=ast.parse((V2/'_math.py').read_text())
    class Normalize(ast.NodeTransformer):
        def visit_FunctionDef(self,node):
            node=self.generic_visit(node);node.decorator_list=[];return node
        def visit_Name(self,node):
            if node.id in ('local_rand_like','local_randn_like'):
                return ast.Attribute(value=ast.Name(id='torch',ctx=ast.Load()),attr=node.id[6:],ctx=ast.Load())
            return node
    for original in tree.body:
        if not isinstance(original,ast.FunctionDef):continue
        converted=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==original.name)
        assert ast.dump(Normalize().visit(copy.deepcopy(original)),include_attributes=False)==ast.dump(Normalize().visit(copy.deepcopy(converted)),include_attributes=False)

def test_current_url_pin_and_all_exact_ids_absent_before_intake():
    catalog=Path('/Users/ben/comfy/ComfyUI_secure_nodes/pack-db/packs/packs.json')
    entries=json.loads(catalog.read_text())
    normalize=lambda s:s.lower().rstrip('/').removesuffix('.git')
    url='https://github.com/1038lab/ComfyUI-ReduxFineTune'
    pin='4d8ff9239bf7b86d62a9b3bc52745aeef229c18c'
    assert not [k for k,v in entries.items() if normalize(v['upstream'])==normalize(url) or v['commit']==pin]
    for path in catalog.parent.rglob('secure-nodes.json'):
        assert not set(NODES).intersection(json.loads(path.read_text()).get('nodes',{}))

@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('mode',OLD['FUSION_MODES'])
@pytest.mark.parametrize('strength',[0.1,1.,2.])
def test_all11_exact_fusion_draw_order_precision_native_nan(dtype,mode,strength):
    feature=features(dtype);text=rows(dtype)[0][0].mean(1)
    torch.manual_seed(71);expected=OLD['fuse_features'](feature,text,mode,strength)
    state=torch.random.get_rng_state().clone()
    with MATH.rng_scope(71):actual=MATH.fuse_features(feature,text,mode,strength)
    torch.testing.assert_close(actual,expected,rtol=0,atol=0,equal_nan=True)
    assert actual.dtype==expected.dtype and torch.equal(torch.random.get_rng_state(),state)

@pytest.mark.parametrize('mode',OLD['FUSION_MODES'])
@pytest.mark.parametrize('super_redux',[False,True])
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16])
def test_basic_literal_source_equations_all11_both_passes(dtype,mode,super_redux):
    original=rows(dtype);feature=features(dtype);producer=SimpleNamespace(get_cond=lambda vision:feature)
    torch.manual_seed(117);expected=OLD['ReduxFineTune']().apply_style(original,producer,None,mode,.7,super_redux)[0]
    state=torch.random.get_rng_state().clone()
    actual=[[x,{}] for x,_ in original]
    with MATH.rng_scope(117):
        for _ in range(2 if super_redux else 1):actual=MATH.basic_once(actual,feature,mode,.7)[0]
    assert_rows(actual,expected);assert torch.equal(state,torch.random.get_rng_state())

@pytest.mark.parametrize('mode',OLD['FUSION_MODES'])
@pytest.mark.parametrize('super_redux',[False,True])
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16])
def test_advanced_literal_source_all11_noise_prompt_order(dtype,mode,super_redux):
    original=rows(dtype);feature=features(dtype);image=torch.zeros(1,8,8,3,dtype=dtype)
    producer=SimpleNamespace(get_cond=lambda vision:feature);vision=SimpleNamespace(encode_image=lambda image,**kw:object())
    kw=dict(fusion_mode=mode,style_strength=.7,color_strength=.3,content_strength=.2,structure_strength=.1,texture_strength=.4,prompt_strength=1.2,feature_noise=.2,feature_resolution=16,SUPER_REDUX=super_redux)
    torch.manual_seed(201);expected=OLD['ReduxFineTuneAdvanced']().apply_style(original,producer,vision,image,**kw)[0]
    state=torch.random.get_rng_state().clone();actual=[[x,{}] for x,_ in original]
    with MATH.rng_scope(201):
        for index in range(2 if super_redux else 1):
            strengths=[.7,.3,.2,.1,.4] if index==0 else [.84,.33,.22,.11,.44]
            actual=MATH.advanced_once(actual,feature,mode,*strengths,1.2,.2,16,None)[0]
    assert_rows(actual,expected);assert torch.equal(state,torch.random.get_rng_state())

@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('mode',[m for m in OLD['FUSION_MODES'] if m!='Random'])
@pytest.mark.parametrize('super_redux',[False,True])
def test_registered_basic_actual_canonical_redux_and_opaque_metadata(dtype,mode,super_redux):
    model,vision=canonical(dtype);original=rows(dtype)
    expected=OLD['ReduxFineTune']().apply_style(original,model,vision,mode,.7,super_redux)[0]
    result=asyncio.run(typed_execute('ReduxFineTune',dict(conditioning=original,style_model=model,clip_vision_output=vision,fusion_mode=mode,fusion_strength=.7,SUPER_REDUX=super_redux)))
    assert_rows(result[0],expected,original);assert result[1] is model and result[2] is vision

def test_native_empty_nonsquare_rank_channel_and_nan_boundaries():
    feature=features();producer=SimpleNamespace(get_cond=lambda vision:feature)
    with pytest.raises(UnboundLocalError):OLD['ReduxFineTune']().apply_style([],producer,None)
    with pytest.raises(UnboundLocalError):MATH.basic_once([],feature,'Mix',1.)
    for shape in [(1,8,10),(1,0,10),(1,4,10,2)]:
        f=features(shape=shape)
        try:MATH.advanced_once(rows(),f,'Mix',1.,0.,0.,0.,0.,1.,0.,16,None)
        except Exception as error:
            with pytest.raises(type(error)):OLD['ReduxFineTuneAdvanced']().apply_style(rows(),SimpleNamespace(get_cond=lambda vision:f),SimpleNamespace(encode_image=lambda *a,**k:None),torch.zeros(1,8,8,3))
        else:pytest.fail('expected native shape error')
    singleton=torch.ones(1,1,1)
    assert torch.isnan(MATH.fuse_features(singleton,singleton,'AdaIN',1.)).all()
    assert torch.isneginf(MATH.fuse_features(feature,rows()[0][0].mean(1),'AttnBias',0.)).all()
    assert torch.isnan(MATH.fuse_features(feature,rows()[0][0].mean(1),'AttnBias',-1.)).all()

@pytest.mark.parametrize('shape',[(1,6,8,3),(2,9,5,4),(1,3,3,1)])
@pytest.mark.parametrize('kind',['empty','one','edge','mismatch'])
def test_loader_crops_exact_inclusive_exclusive_and_empty_masks(shape,kind):
    pixels=torch.arange(math.prod(shape)).reshape(shape).float()
    mask=torch.zeros(shape[0],shape[1],shape[2]);mask[:,1:3,1:3]=1
    if kind=='empty':mask.zero_()
    elif kind=='one':mask.zero_();mask[:,1,1]=1
    elif kind=='edge':mask.fill_(1)
    elif kind=='mismatch':mask=torch.ones(shape[0],2,2)
    for method in ('crop_center','crop_mask'):
        args=(pixels,) if method=='crop_center' else (pixels,mask)
        a=getattr(OLD_LOADER(),method)(*args);b=getattr(WRAP.LoaderCrop(),method)(*args)
        assert torch.equal(a,b) and a.shape==b.shape

def test_no_cross_execution_rng_tensor_cache_and_controlled_native_cache_staleness():
    assert not hasattr(MATH._get_fft_params,'cache_info')
    mask=torch.ones(1,4,4)
    old=OLD['ReduxFineTuneAdvanced']._get_interpolated_mask(mask,2,torch.device('cpu'))
    mask.zero_();assert torch.equal(OLD['ReduxFineTuneAdvanced']._get_interpolated_mask(mask,2,torch.device('cpu')),old)
    assert torch.count_nonzero(MATH.crop_math._get_interpolated_mask(mask,2,torch.device('cpu')))==0
    state=torch.random.get_rng_state().clone()
    with MATH.rng_scope():a=MATH.local_rand_like(torch.zeros(32))
    with MATH.rng_scope():b=MATH.local_rand_like(torch.zeros(32))
    assert a.shape==b.shape==(32,) and ((a>=0)&(a<1)).all() and not torch.equal(a,b)
    assert torch.equal(state,torch.random.get_rng_state())

def test_workload_preflight_before_large_math_and_snapshot_refusal(monkeypatch):
    def fail(*a,**k):raise AssertionError('allocation before resource preflight')
    big=torch.empty((1,729,4096),device='meta');text=torch.empty((1,77,4096),device='meta')
    assert WRAP.budget([[text,{}]],big)['output_bytes']<WRAP.MAX_OUTPUT
    monkeypatch.setattr(torch,'cat',fail);monkeypatch.setattr(F,'interpolate',fail)
    with pytest.raises(ValueError,match='budget'):WRAP.budget([[text,{}]],big,True,64,2.,True,'FrequencyMix')
    with pytest.raises(ValueError,match='budget'):WRAP.budget([[text,{}]]*4096,big)
    assert WRAP.MAX_OUTPUT==128*1024*1024 and WRAP.MAX_OWNERSHIP==256*1024*1024

@pytest.mark.parametrize('mode',[m for m in OLD['FUSION_MODES'] if m!='Random'])
@pytest.mark.parametrize('crop',['none','center','mask_area'])
@pytest.mark.parametrize('super_redux',[False,True])
def test_registered_advanced_actual_canonical_encoder_and_redux_source_exact(mode,crop,super_redux):
    inputs=advanced_inputs(mode,super_redux,crop)
    expected=OLD['ReduxFineTuneAdvanced']().apply_style(**inputs)
    actual=asyncio.run(typed_execute('ReduxFineTuneAdvanced',inputs))
    assert_rows(actual[0],expected[0],inputs['conditioning'])
    assert actual[1] is inputs['style_model'] and actual[3] is inputs['image']
    torch.testing.assert_close(actual[2].last_hidden_state,expected[2].last_hidden_state,rtol=0,atol=0)
    assert torch.equal(actual[4],expected[4])
    if crop!='mask_area':assert actual[4] is inputs['mask']

@pytest.mark.parametrize('super_redux',[False,True])
def test_default_basic_advanced_usability_and_native_empty_errors(super_redux):
    model,vision=canonical();original=rows(count=1)
    expected=OLD['ReduxFineTune']().apply_style(original,model,vision,SUPER_REDUX=super_redux)
    actual=asyncio.run(typed_execute('ReduxFineTune',dict(conditioning=original,style_model=model,clip_vision_output=vision,SUPER_REDUX=super_redux)))
    assert_rows(actual[0],expected[0],original)
    inputs=advanced_inputs(super_redux=super_redux,mask=False)
    for key in ('crop','fusion_mode','style_strength','color_strength','content_strength','structure_strength','texture_strength','prompt_strength','feature_noise','feature_resolution'):inputs.pop(key)
    expected=OLD['ReduxFineTuneAdvanced']().apply_style(**inputs)
    actual=asyncio.run(typed_execute('ReduxFineTuneAdvanced',inputs))
    assert_rows(actual[0],expected[0],inputs['conditioning']);assert torch.equal(actual[4],expected[4])
    assert actual[4].shape==(1,8,10) and torch.isfinite(actual[0][0][0]).all()
    inputs['conditioning']=[]
    with pytest.raises(UnboundLocalError):OLD['ReduxFineTuneAdvanced']().apply_style(**inputs)
    with pytest.raises(UnboundLocalError):asyncio.run(typed_execute('ReduxFineTuneAdvanced',inputs))

def test_two_fresh_required_outer_basic_advanced_all11_and_denial_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    async def run():
        prior=_sdk.providers.execution_backend;pids=set()
        try:
            for generation in range(2):
                root=tmp_path/str(generation);shutil.copytree(V2,root);module=load('ned_redux_fresh_'+str(generation),root)
                for cls in module.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
                session=await GuestSession('ned-redux-full-'+str(generation),guest_runtime_root=root).start()
                capabilities=('raw','inspect','models')
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=capabilities,tenant='ned-redux-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(name,inputs):
                    cls=module.NODE_CLASS_MAPPINGS[name]
                    mapped=await execution._async_map_node_over_list('ned-redux','1',cls,{k:[v] for k,v in inputs.items()},cls.FUNCTION)
                    return (await execution.resolve_map_node_over_list_results(mapped))[0].result
                try:
                    assert session.sandbox_kind=='seatbelt'
                    for dtype in (torch.float32,torch.float16,torch.bfloat16):
                        model,vision=canonical(dtype);original=rows(dtype)
                        for mode in OLD['FUSION_MODES']:
                            inputs=dict(conditioning=original,style_model=model,clip_vision_output=vision,fusion_mode=mode,fusion_strength=.7,SUPER_REDUX=True)
                            if mode=='Random':
                                actual=await outer('ReduxFineTune',inputs)
                                assert actual[0][0][0].shape==(1,10,10) and actual[0][0][0].dtype==dtype
                            else:
                                expected=OLD['ReduxFineTune']().apply_style(**inputs)
                                actual=await outer('ReduxFineTune',inputs);assert_rows(actual[0],expected[0],original)
                            assert actual[1] is model and actual[2] is vision
                    for mode in OLD['FUSION_MODES']:
                        inputs=advanced_inputs(mode,True,'mask_area')
                        actual=await outer('ReduxFineTuneAdvanced',inputs)
                        if mode!='Random':
                            expected=OLD['ReduxFineTuneAdvanced']().apply_style(**inputs)
                            assert_rows(actual[0],expected[0],inputs['conditioning'])
                            assert torch.equal(actual[4],expected[4])
                        else:assert actual[0][0][0].shape==(1,20,10)
                        assert actual[1] is inputs['style_model'] and actual[3] is inputs['image']
                    inputs=advanced_inputs(mask=False)
                    actual=await outer('ReduxFineTuneAdvanced',inputs)
                    assert actual[4].shape==(1,8,10) and not actual[4].any()
                    # Published exact-tuple descriptor: source-valid tuple rows
                    # reach the registered guest without exporting opaque metadata.
                    for name,tuple_inputs in (
                        ('ReduxFineTune',dict(conditioning=tuple(rows()),style_model=model,clip_vision_output=vision)),
                        ('ReduxFineTuneAdvanced',advanced_inputs()),
                    ):
                        tuple_inputs['conditioning']=tuple(tuple_inputs['conditioning'])
                        expected=OLD[name]().apply_style(**tuple_inputs)
                        actual=await outer(name,tuple_inputs)
                        assert_rows(actual[0],expected[0],tuple_inputs['conditioning'])
                    capabilities=('inspect',)
                    with pytest.raises(Exception,match='raw.*not granted'):await outer('ReduxFineTuneAdvanced',inputs)
                    capabilities=('raw',)
                    with pytest.raises(Exception,match='inspect.*not granted'):await outer('ReduxFineTuneAdvanced',inputs)
                    capabilities=('raw','inspect','models')
                    assert (await outer('ReduxFineTuneAdvanced',inputs))[4].shape==(1,8,10)
                    model,vision=canonical(adapter=True)
                    basic=dict(conditioning=rows(),style_model=model,clip_vision_output=vision)
                    expected=OLD['ReduxFineTune']().apply_style(**basic);actual=await outer('ReduxFineTune',basic)
                    assert_rows(actual[0],expected[0],basic['conditioning'])
                    bad=advanced_inputs();bad['style_model']=model;bad['clip_vision']=canonical_vision(8)
                    with pytest.raises(Exception,match='shape'):await outer('ReduxFineTuneAdvanced',bad)
                    empty=advanced_inputs();empty['conditioning']=[]
                    with pytest.raises(Exception,match='UnboundLocalError'):await outer('ReduxFineTuneAdvanced',empty)
                    with pytest.raises(Exception,match='UnboundLocalError'):await outer('ReduxFineTune',basic|{'conditioning':[]})
                    too_many=basic|{'conditioning':rows(count=1)*4097}
                    with pytest.raises(Exception,match='row budget'):await outer('ReduxFineTune',too_many)
                    massive=advanced_inputs(mask=False);massive['image']=torch.empty((1,10000,10000,3),device='meta')
                    with pytest.raises(Exception,match='image projection.*budget'):await outer('ReduxFineTuneAdvanced',massive)
                    for tokens,reason in ((20000000,'bounded inference profile'),(30000000,'geometry profile')):
                        oversized=comfy.clip_vision.Output();oversized.image_embeds=torch.empty(0)
                        oversized.last_hidden_state=torch.empty((1,tokens,6),device='meta')
                        with pytest.raises(Exception,match=reason):await outer('ReduxFineTune',basic|{'clip_vision_output':oversized})
                    inputs=advanced_inputs();inputs['feature_resolution']=64;inputs['conditioning']=rows(count=32)
                    # Small canonical10-wide fixtures remain admitted, unlike
                    # analytical4096-wide default/high-resolution projections.
                    assert len((await outer('ReduxFineTuneAdvanced',inputs))[0])==32
                    pids.add(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(pids)==2 and os.getpid() not in pids
        print('Required full Redux/advanced fresh PIDs',sorted(pids))
    asyncio.run(run())

def test_declared_input_snapshot_limit_and_source_valid_tuple_conditioning():
    model,vision=canonical();original=rows(count=1)
    inputs=dict(conditioning=tuple(original),style_model=model,clip_vision_output=vision)
    expected=OLD['ReduxFineTune']().apply_style(**inputs)
    actual=asyncio.run(typed_execute('ReduxFineTune',inputs))
    assert_rows(actual[0],expected[0],original)
    async def run():
        refs=_sdk.InProcessRefResolver();large=torch.empty((1,10000000,10),device='meta')
        ref=_sdk.TensorRef._wrap(await refs.create('TENSOR',large))
        with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
            with pytest.raises(ValueError,match='snapshot'):await WRAP.raw_checked(ref)
    asyncio.run(run())

@pytest.fixture(scope='module')
def owned_full_style_file(tmp_path_factory):
    from safetensors.torch import save_file
    path=tmp_path_factory.mktemp('ned-redux-owned-untrained')/'owned.safetensors'
    with torch.device('meta'):model=ReduxImageEncoder(dtype=torch.float16)
    state={key:torch.zeros(value.shape,dtype=torch.float16) for key,value in model.state_dict().items()}
    save_file(state,str(path));del state,model
    return path

def test_loader_two_fresh_required_guests_real_safe_parser_crops_catalogue_denials(tmp_path,monkeypatch,owned_full_style_file):
    import folder_paths
    from safetensors.torch import save_file
    from comfy_secure_nodes.webassets import remote_catalogue_options
    clip_path=tmp_path/'vision.safetensors';save_file({'owned-fixture':torch.zeros(1)},str(clip_path))
    monkeypatch.setitem(folder_paths.folder_names_and_paths,'style_models',([str(owned_full_style_file.parent)],{'.sft','.safetensors'}))
    monkeypatch.setitem(folder_paths.folder_names_and_paths,'clip_vision',([str(tmp_path)],{'.sft','.safetensors'}))
    monkeypatch.setattr(folder_paths,'filename_list_cache',{})
    encoder=canonical_vision();calls=[];native_encode=encoder.encode_image
    def record(pixels,crop=True):
        calls.append((pixels.clone(),crop))
        return native_encode(pixels,crop=crop)
    encoder.encode_image=record
    # The actual style SafeTensors parser/loader is not mocked. CLIP loader
    # selection is a recording fixture returning a tiny canonical CPU encoder;
    # no default trained CLIP checkpoint is claimed by this whole node proof.
    paths=[]
    def vision_loader(path):paths.append(path);return encoder
    monkeypatch.setattr(comfy.clip_vision,'load',vision_loader)
    assert remote_catalogue_options('/secure-nodes/models/style_models')==[owned_full_style_file.name]
    assert remote_catalogue_options('/secure-nodes/models/clip_vision')==[clip_path.name]
    assert remote_catalogue_options('/secure-nodes/models/style_models?path=../private') is None
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    async def run():
        prior=_sdk.providers.execution_backend;pids=set()
        try:
            for generation in range(2):
                root=tmp_path/('pack'+str(generation));shutil.copytree(V2,root)
                module=load('ned_redux_loader_'+str(generation),root);cls=module.NODE_CLASS_MAPPINGS['ClipVisionStyleLoader'];cls.GET_SCHEMA()
                session=await GuestSession('ned-redux-loader-'+str(generation),guest_runtime_root=root).start()
                capabilities=('models','raw','inspect')
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=capabilities,tenant='ned-redux-loader-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(inputs):
                    mapped=await execution._async_map_node_over_list('redux-loader','1',cls,{k:[v] for k,v in inputs.items()},cls.FUNCTION)
                    return (await execution.resolve_map_node_over_list_results(mapped))[0].result
                try:
                    assert session.sandbox_kind=='seatbelt'
                    pixels=torch.linspace(0,1,8*10*3).reshape(1,8,10,3);mask=torch.zeros(1,8,10);mask[:,1:7,2:8]=1
                    base=dict(clip_vision=clip_path.name,style_model=owned_full_style_file.name,image=pixels,crop_method='none')
                    for crop in ('none','center','mask'):
                        for present in (False,True):
                            inputs=base|dict(crop_method=crop)
                            if present:inputs['mask']=mask
                            expected=pixels if crop=='none' or crop=='mask' and not present else (OLD_LOADER().crop_center(pixels) if crop=='center' else OLD_LOADER().crop_mask(pixels,mask))
                            result=await outer(inputs)
                            assert len(result[0])==1 and torch.equal(result[0][0],expected)
                            if expected is pixels:assert result[0][0] is pixels
                            assert type(result[1]) is comfy.sd.StyleModel and type(result[1].model) is ReduxImageEncoder
                            assert result[1].model.redux_up.in_features==1152 and result[1].model.redux_down.out_features==4096
                            assert type(result[2]) is comfy.clip_vision.Output
                            torch.testing.assert_close(result[2].last_hidden_state,native_encode(expected,crop=crop!='none' and (crop!='mask' or present)).last_hidden_state,rtol=0,atol=0)
                            assert torch.equal(calls[-1][0],expected)
                    capabilities=('raw','inspect')
                    with pytest.raises(Exception,match='models.*not granted'):await outer(base)
                    capabilities=('models','inspect')
                    with pytest.raises(Exception,match='raw.*not granted'):await outer(base)
                    capabilities=('models','raw')
                    with pytest.raises(Exception,match='inspect.*not granted'):await outer(base)
                    capabilities=('models','raw','inspect')
                    for field in ('clip_vision','style_model'):
                        for label in ('../vision.safetensors','/absolute.safetensors','missing.safetensors','unsafe.bin'):
                            with pytest.raises(Exception):await outer(base|{field:label})
                    result=await outer(base);assert torch.equal(result[0][0],pixels)
                    pids.add(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(pids)==2 and os.getpid() not in pids
        print('Required full-loader PIDs',sorted(pids),'actual SafeTensors parser; recorded CLIP catalogue load/tiny canonical encoder')
    asyncio.run(run())

def test_loader_retry_exact_crop_flag_and_clone_identity(monkeypatch):
    async def run():
        refs=_sdk.InProcessRefResolver();pixels=torch.zeros(1,6,8,3)
        image=_sdk.ImageRef._wrap(await refs.create('IMAGE',pixels));model,output=canonical()
        calls=[]
        class Vision:
            async def encode_image(self,value,crop=True):
                raw=await refs.resolve(value);calls.append((raw,crop))
                if len(calls)%2:raise RuntimeError('original encode failure')
                return _sdk.ClipVisionOutputRef._wrap(await refs.create('CLIP_VISION_OUTPUT',output))
        class Models:
            async def load_clip_vision(self,label):assert label=='vision';return Vision()
            async def load_style_model(self,label):assert label=='style';return _sdk.StyleModelRef._wrap(await refs.create('STYLE_MODEL',model))
        with _sdk.bind_runtime(refs,SimpleNamespace(models=Models()),_sdk.InProcessOps()):
            result=await NODES['ClipVisionStyleLoader'].execute('vision','style',image,'none')
        assert [crop for _,crop in calls]==[False,True]
        assert calls[0][0] is calls[1][0] and calls[0][0] is not pixels and torch.equal(calls[0][0],pixels)
        assert result.result[0][0] is image
    asyncio.run(run())

@pytest.mark.parametrize('dtype',[torch.float16,torch.float64,torch.uint8,torch.bfloat16])
def test_mask_loader_native_dtype_numpy_boundaries(dtype):
    pixels=torch.zeros(1,6,8,3);mask=torch.ones(1,6,8,dtype=dtype)
    if dtype==torch.bfloat16:
        with pytest.raises(TypeError):OLD_LOADER().crop_mask(pixels,mask)
        with pytest.raises(TypeError):WRAP.LoaderCrop().crop_mask(pixels,mask)
    else:assert torch.equal(OLD_LOADER().crop_mask(pixels,mask),WRAP.LoaderCrop().crop_mask(pixels,mask))

def test_advanced_retry_call_counts_crop_and_mask_return_identity():
    class Recording:
        def __init__(self):self.calls=[]
        def encode_image(self,image,crop=False):self.calls.append((image,crop));return object()
    for super_redux in (False,True):
        for crop in ('none','center','mask_area'):
            inputs=advanced_inputs(super_redux=super_redux,crop=crop)
            vision=Recording();feature=features()
            result=OLD['ReduxFineTuneAdvanced']().apply_style(**(inputs|{'clip_vision':vision,'style_model':SimpleNamespace(get_cond=lambda v:feature)}))
            assert len(vision.calls)==(3 if super_redux else 2)
            assert all(flag==(crop=='center') for _,flag in vision.calls)
            assert result[3] is inputs['image']
            if crop=='mask_area':
                assert result[4] is not inputs['mask'] and result[4].untyped_storage().data_ptr()==inputs['mask'].untyped_storage().data_ptr()
            else:assert result[4] is inputs['mask']

def test_proxy_manifest_resources_stubs_pristine_and_guest_import_contract():
    from comfy_secure_nodes import packdb
    assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
    provenance=json.loads((V2/'source-provenance.json').read_text())
    pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert pristine==provenance['source_hashes'] and len(pristine)==10
    for name in ('LICENSE','README.md','update.md','.github/workflows/publish.yml'):
        assert (V2/name).read_bytes()==(PACK/name).read_bytes()
    assert 'GNU GENERAL PUBLIC LICENSE' in (PACK/'LICENSE').read_text()
    for name,row in provenance['stubs'].items():assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==row['sha256']
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
    for filename in ('__init__.py','ReduxFineTune.py','ClipVisionStyleLoader.py','_math.py','_secure_nodes.py','_loader_crop.py'):
        text=(V2/filename).read_text()
        for forbidden in ('_wrap(','_from_raw','folder_paths','PromptServer','subprocess','requests','torch.manual_seed','empty_cache','gc.collect','eval(','exec('):assert forbidden not in text
        for n in ast.walk(ast.parse(text)):
            if isinstance(n,ast.Import):assert all(x.name in ('torch','torch.nn.functional','math','numpy') for x in n.names)
            if isinstance(n,ast.ImportFrom):assert n.level or n.module in ('comfy_api.latest','contextvars','contextlib')
    loaded=packdb.load_pack(PACK.parent,mount_name='custom_nodes.ned_redux_proxy')
    assert set(loaded.node_mappings)==set(NODES) and not loaded.routes and loaded.web_directory is not None

def test_stored_pair_and_zip_two_exact_roundtrips_modes_and_wrong_preimage(tmp_path):
    pair=DB/'patches/comfyui-reduxfinetune/x4d8ff92/comfyui-reduxfinetune-x4d8ff92'
    manifest,diff=packpatch.generate(PACK.parent)
    assert json.loads(pair.with_suffix('.json').read_text())==manifest
    assert pair.with_suffix('.diff').read_bytes().decode()==diff
    bundle=packpatch.bundle(manifest,diff);assert pair.with_suffix('.zip').read_bytes()==bundle
    for n in range(2):
        fresh=tmp_path/str(n)/'comfyui-reduxfinetune/x4d8ff92';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if n:packpatch.apply_bundle(fresh,bundle)
        else:packpatch.apply(fresh,manifest,diff)
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
        for p in V2.rglob('*'):
            if p.is_file():assert (fresh/PACK.name/'v2'/p.relative_to(V2)).stat().st_mode&0o777==p.stat().st_mode&0o777
    wrong=tmp_path/'wrong/comfyui-reduxfinetune/x4d8ff92';wrong.mkdir(parents=True)
    shutil.copytree(PACK,wrong/PACK.name,ignore=shutil.ignore_patterns('v2'))
    target=wrong/PACK.name/'README.md';target.write_bytes(target.read_bytes()+b'\nwrong pristine\n')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(wrong,manifest,diff)
    assert not (wrong/PACK.name/'v2').exists()

def test_expanded_resolution_workspace_metered_not_only_original_feature(monkeypatch):
    # Analytic meta controls only: old-size-only FFT projection would admit
    #1MiB*16 resized fields while24 simultaneous fields exceed256MiB.
    feature=torch.empty((1,64,4096),device='meta')
    embedding=torch.empty((1,2,4096),device='meta')
    def forbidden(*args,**kwargs):raise AssertionError('no fusion allocation before projection')
    monkeypatch.setattr(F,'interpolate',forbidden)
    with pytest.raises(ValueError,match='budget'):
        WRAP.budget([[embedding,{}]],feature,True,64,1.,False,'FrequencyMix')
    assert WRAP.budget([[embedding,{}]],feature,True,16,1.,False,'Mix')['projected_bytes']<WRAP.MAX_OWNERSHIP
