"""Pinned pack PIL and actual canonical tiny tiled CPU controls, NOT trained inference."""
import ast,asyncio,copy,hashlib,json,types
import numpy as np
import pytest,torch
from PIL import Image
from test_ned_comfyroll_pure import NEW,V2,PACK,_sdk,GuestSession
from comfy_secure_nodes.transport import wire
import comfy.utils,comfy.model_management,folder_paths
from spandrel import Architecture,ImageModelDescriptor,ModelLoader
IDS=['CR Upscale Image','CR Multi Upscale Stack','CR Apply Multi Upscale']
LEDGER=json.loads((V2/'upscale-draft-ledger.json').read_text())
SOURCE=ast.parse((PACK/'nodes/nodes_upscale.py').read_text())
HELPER=ast.parse((PACK/'nodes/functions_upscale.py').read_text())
ICONS=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
class Tiny(torch.nn.Module):
    """Real deterministic nearest-neighbor CPU module, not a trained superresolution model."""
    def __init__(self,scale):
        super().__init__();self.weight=torch.nn.Parameter(torch.tensor([1.]));self.scale=scale;self.calls=[]
    def forward(self,value):
        self.calls.append(tuple(value.shape))
        return torch.nn.functional.interpolate(value,size=(value.shape[-2]*self.scale,value.shape[-1]*self.scale),mode='nearest')*self.weight
class Arch(Architecture):
    def load(self,state):raise AssertionError('No trained architecture parsing in this fixture')
ARCH=Arch(id='ned-tiny-nearest-fixture',detect=lambda state:False)
def descriptor(scale):
    model=Tiny(scale)
    return ImageModelDescriptor(model,model.state_dict(),ARCH,'SR',[],True,True,scale,3,3)
@pytest.fixture
def loader(monkeypatch,tmp_path):
    from safetensors.torch import save_file
    state={'calls':[],'loaded':[],'file_loads':[],'paths':{}}
    for name,scale in [('one',1),('two',2),('three',3)]:
        p=tmp_path/(name+'.safetensors');save_file({'fixture_scale':torch.tensor(scale)},str(p));state['paths'][name]=str(p)
    def path(folder,name):
        assert folder=='upscale_models'
        state['file_loads'].append(name);return state['paths'][name]
    def load_from_state_dict(self,values):
        assert set(values)=={'fixture_scale'}
        scale=int(values['fixture_scale']);state['calls'].append(scale);d=descriptor(scale);state['loaded'].append(d);return d
    monkeypatch.setattr(folder_paths,'get_full_path_or_raise',path)
    monkeypatch.setattr(ModelLoader,'load_from_state_dict',load_from_state_dict)
    def legacy_load(values):return load_from_state_dict(None,values)
    state['legacy_load']=legacy_load
    # CPU fixture policy is explicit; no host/GPU lifecycle certification.
    monkeypatch.setattr(comfy.model_management,'get_torch_device',lambda:torch.device('cpu'))
    monkeypatch.setattr(comfy.model_management,'free_memory',lambda *a,**k:None)
    return state
def oracle(loader):
    ns={'torch':torch,'np':np,'Image':Image,'icons':ICONS,'folder_paths':types.SimpleNamespace(get_filename_list=lambda _:[],get_full_path=lambda f,n:loader['paths'][n]),'model_loading':types.SimpleNamespace(load_state_dict=loader['legacy_load']),'model_management':comfy.model_management,'comfy':types.SimpleNamespace(utils=comfy.utils)}
    funcs=[copy.deepcopy(n) for n in HELPER.body if isinstance(n,ast.FunctionDef)]
    classes=[copy.deepcopy(n) for n in SOURCE.body if isinstance(n,ast.ClassDef) and n.name in {r['class'] for r in LEDGER.values()}]
    exec(compile(ast.Module(body=funcs+classes,type_ignores=[]),'pinned-upscale-functions-and-nodes','exec'),ns)
    return ns
def image(dtype=torch.float32,batch=1):
    t=torch.linspace(-.1,1.1,4*6*3,dtype=dtype).reshape(1,4,6,3)
    return t.repeat(batch,1,1,1)
def args_single(**changes):
    args=dict(image=image(),upscale_model='two',rounding_modulus=8,loops=1,mode='rescale',supersample='false',resampling_method='lanczos',rescale_factor=.75,resize_width=5);args.update(changes);return args
def args_stack(**changes):
    a=dict(switch_1='On',upscale_model_1='one',rescale_factor_1=.5,switch_2='On',upscale_model_2='two',rescale_factor_2=1.5,switch_3='On',upscale_model_3='three',rescale_factor_3=2.,upscale_stack=None);a.update(changes);return a
def args_apply(**changes):
    a=dict(image=image(),resampling_method='lanczos',supersample='false',rounding_modulus=8,upscale_stack=[('two',1.5),('three',.5)]);a.update(changes);return a
def outcome(call):
    try:return 'value',call()
    except Exception as e:return 'error',type(e),str(e)
async def migrated(id,a):
    refs=_sdk.InProcessRefResolver()
    wrapped=await _sdk.wrap_inputs(refs,a)
    with _sdk.bind_runtime(refs,types.SimpleNamespace(models=_sdk._InProcessModels()),_sdk.InProcessOps()):
        r=NEW.NODE_CLASS_MAPPINGS[id].execute(**wrapped)
        if hasattr(r,'__await__'):r=await r
    out=[]
    for v in r.result:out.append(await refs.resolve(v) if isinstance(v,_sdk.Ref) else v)
    return tuple(out)
def same(actual,expected):
    assert actual[0]==expected[0]
    if expected[0]=='error':assert actual[1:]==expected[1:];return
    a,b=actual[1],expected[1];assert len(a)==len(b)==2 and a[1]==b[1]
    if isinstance(b[0],torch.Tensor):assert a[0].shape==b[0].shape and a[0].dtype==b[0].dtype and torch.equal(a[0],b[0])
    else:assert type(a[0]) is type(b[0]) and a[0]==b[0]
@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('name',['one','two'])
@pytest.mark.parametrize('mode',['rescale','resize'])
@pytest.mark.parametrize('resampler',['nearest','bilinear','bicubic','lanczos'])
@pytest.mark.parametrize('supersample',['true','false'])
@pytest.mark.parametrize('factor',[1.,.75])
def test_single_exact_source_actual_tiled_pixels_bicubic_binding_quantization_and_native_bf16(loader,dtype,name,mode,resampler,supersample,factor):
    a=args_single(image=image(dtype,batch=2),upscale_model=name,mode=mode,resampling_method=resampler,supersample=supersample,rescale_factor=factor)
    old=oracle(loader);expected=outcome(lambda:old['CR_UpscaleImage']().upscale(**a));calls=list(loader['calls']);loader['calls'].clear()
    if dtype is torch.bfloat16:assert expected[0]=='error' and expected[1] is TypeError and 'BFloat16' in expected[2]
    else:assert expected[0]=='value' # Matching fixture failures never qualify as positive pixels.
    actual=outcome(lambda:asyncio.run(migrated(IDS[0],a)));same(actual,expected);assert loader['calls']==calls
@pytest.mark.parametrize('mask',range(8))
@pytest.mark.parametrize('previous',[None,[],[('one',.25)],[('None',1.),('one',.25)]])
def test_producer_exact_sentinel_order_rows_and_zero_authority(loader,mask,previous):
    a=args_stack(upscale_stack=previous)
    for i in range(1,4):a[f'switch_{i}']='On' if mask&(1<<(i-1)) else 'Off'
    old=oracle(loader);expected=old['CR_MultiUpscaleStack']().stack(**a);actual=asyncio.run(migrated(IDS[1],a))
    assert actual==expected and all(type(row) is tuple for row in actual[0]) and not loader['calls']
@pytest.mark.parametrize('stack',[[],[('one',1.)],[('two',.75)],[('two',1.5),('three',.5)],[('one',1.),('two',1.5),('three',.75)]])
@pytest.mark.parametrize('resampler',['nearest','bilinear','bicubic','lanczos'])
@pytest.mark.parametrize('supersample',['true','false'])
def test_multi_exact_source_noncompounding_targets_order_and_empty_identity(loader,stack,resampler,supersample):
    a=args_apply(upscale_stack=stack,resampling_method=resampler,supersample=supersample)
    old=oracle(loader);expected=outcome(lambda:old['CR_ApplyMultiUpscale']().apply(**a));calls=list(loader['calls']);loader['calls'].clear()
    assert expected[0]=='value' # These cases must positively execute source and broker.
    actual=outcome(lambda:asyncio.run(migrated(IDS[2],a)));same(actual,expected);assert loader['calls']==calls
    if not stack:assert actual[1][0] is a['image']
@pytest.mark.parametrize('changes',[{'rounding_modulus':0,'mode':'resize'},{'rescale_factor':0},{'rescale_factor':-.1},{'image':image(batch=2)},{'upscale_stack':[()]},{'upscale_stack':None}])
def test_native_shape_target_row_and_division_failures_are_not_silently_fixed(loader,changes):
    id=IDS[2] if 'upscale_stack' in changes or changes.get('image') is not None else IDS[0]
    a=(args_apply if id==IDS[2] else args_single)(**changes)
    old=oracle(loader);c=old[LEDGER[id]['class']]
    expected=outcome(lambda:getattr(c(),c.FUNCTION)(**a));actual=outcome(lambda:asyncio.run(migrated(id,a)));same(actual,expected)
def test_selected_resampling_binding_really_ignores_four_ui_options_and_correct_keyword_would_differ(loader):
    old=oracle(loader);a=args_single(rescale_factor=1.25)
    outputs=[old['CR_UpscaleImage']().upscale(**dict(a,resampling_method=r))[0] for r in ('nearest','bilinear','bicubic','lanczos')]
    assert all(torch.equal(outputs[0],x) for x in outputs)
    sample=old['tensor2pil'](image()[0])
    wrong=old['apply_resize_image'](sample,6,4,8,'rescale','false',1.25,5,'nearest')
    explicit=old['apply_resize_image'](sample,6,4,8,'rescale','false',1.25,5,resample='nearest')
    assert not np.array_equal(np.asarray(wrong),np.asarray(explicit))
def test_actual_public_broker_restores_owned_dtype_and_exact_source_tile_overlap_calls(loader,monkeypatch):
    calls=[];original=comfy.utils.tiled_scale
    def record(*a,**kw):calls.append(dict(kw));return original(*a,**kw)
    monkeypatch.setattr(comfy.utils,'tiled_scale',record)
    a=args_single(image=image(batch=3),supersample='false')
    result=asyncio.run(migrated(IDS[0],a));assert result[0].shape[0]==3
    assert len(calls)==1 and calls[0]['tile_x']==512 and calls[0]['tile_y']==512 and calls[0]['overlap']==32
    assert loader['loaded'][-1].model.weight.dtype is torch.float32 and loader['loaded'][-1].model.weight.device.type=='cpu'
    assert len(loader['loaded'][-1].model.calls)>=3
    # This checks restoration for this owned CPU descriptor only, not aliases/threads/GPU.
@pytest.mark.parametrize('dtype',[torch.float32,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('failure',[False,True])
def test_actual_typed_host_broker_restores_previous_cpu_dtype_even_failure_without_module_escape(loader,monkeypatch,dtype,failure):
    d=descriptor(2);d.to(torch.device('cpu'),dtype=dtype);pixels=image(dtype)
    if failure:
        def broken(*a,**k):raise ValueError('synthetic non-OOM module failure')
        monkeypatch.setattr(comfy.utils,'tiled_scale',broken)
    async def run():
        refs=_sdk.InProcessRefResolver()
        m=_sdk.UpscaleModelRef._wrap(await refs.create('UPSCALE_MODEL',d));i=_sdk.ImageRef._wrap(await refs.create('IMAGE',pixels))
        with _sdk.bind_runtime(refs,types.SimpleNamespace(),_sdk.InProcessOps()):
            if failure:
                with pytest.raises(ValueError,match='non-OOM'):await m.upscale(i,per_batch=1,tile_size=512)
            else:
                result=await m.upscale(i,per_batch=1,tile_size=512)
                assert (await refs.resolve(result)).shape==(1,8,12,3)
        assert d.model.weight.dtype is dtype and d.model.weight.device.type=='cpu'
    asyncio.run(run()) # Direct trusted fixture refs only; no pack/module exposure.
def test_public_oom_tile_retries_versus_native_exhaustion_are_explicit(loader,monkeypatch):
    original=comfy.utils.tiled_scale;tiles=[]
    def fail_first_two(*a,**kw):
        tiles.append(kw['tile_x'])
        if kw['tile_x']>128:raise comfy.model_management.OOM_EXCEPTION('synthetic tile pressure')
        return original(*a,**kw)
    monkeypatch.setattr(comfy.utils,'tiled_scale',fail_first_two)
    a=args_single();old=oracle(loader);expected=old['CR_UpscaleImage']().upscale(**a)
    assert tiles==[512,256,128];tiles.clear()
    actual=asyncio.run(migrated(IDS[0],a));assert tiles==[512,256,128];same(('value',actual),('value',expected))
    def fail_all(*a,**kw):raise comfy.model_management.OOM_EXCEPTION('synthetic exhausted pressure')
    monkeypatch.setattr(comfy.utils,'tiled_scale',fail_all)
    with pytest.raises(comfy.model_management.OOM_EXCEPTION):old['CR_UpscaleImage']().upscale(**a)
    with pytest.raises(RuntimeError,match='exhausted safe tile'):asyncio.run(migrated(IDS[0],a))
    # Public host changes exhausted OOM exception type; this is NOT native error parity.
def test_empty_batch_native_unbound_versus_existing_broker_empty_cat_boundary_remains_pending(loader):
    a=args_single(image=image()[:0]);old=oracle(loader)
    with pytest.raises(UnboundLocalError):old['CR_UpscaleImage']().upscale(**a)
    with pytest.raises(ValueError,match='non-empty'):asyncio.run(migrated(IDS[0],a))
    # Separate admitted-host seam, not claimed exact legacy empty batch behavior.
@pytest.mark.parametrize('name',['../host','/host','a\\b','x'*2049])
def test_selected_names_fail_closed_before_loader(loader,name):
    with pytest.raises(ValueError,match='logical'):asyncio.run(migrated(IDS[0],args_single(upscale_model=name)))
    assert not loader['calls'] and not loader['file_loads']
@pytest.mark.parametrize('changes',[{'resize_width':8193,'mode':'resize'},{'rescale_factor':10000.},{'supersample':'true','rescale_factor':1000.}])
def test_pil_projected_target_and_supersample_workload_refused_before_resize(loader,monkeypatch,changes):
    calls=[];resize=Image.Image.resize
    def record(self,*a,**k):calls.append(a);return resize(self,*a,**k)
    monkeypatch.setattr(Image.Image,'resize',record)
    with pytest.raises(ValueError,match='PIL target/temporary'):asyncio.run(migrated(IDS[0],args_single(**changes)))
    assert not calls
def test_stack_inputs_and_batch_bounds_no_loader(loader):
    for id,a in [(IDS[1],args_stack(upscale_stack=[('one',1)]*17)),(IDS[0],args_single(image=image(batch=65)))]:
        with pytest.raises(ValueError,match='bound|exceeds'):asyncio.run(migrated(id,a))
    assert not loader['calls']
def test_whole_batch_pil_output_and_cat_workload_bound_not_only_each_image(loader,monkeypatch):
    calls=[];resize=Image.Image.resize
    def record(self,*a,**k):calls.append(a);return resize(self,*a,**k)
    monkeypatch.setattr(Image.Image,'resize',record)
    a=args_single(image=image(batch=64),rescale_factor=100.,supersample='false')
    assert 600*400*3*4<32*1024*1024 and 64*600*400*3*4>64*1024*1024
    with pytest.raises(ValueError,match='PIL target/temporary'):asyncio.run(migrated(IDS[0],a))
    assert not calls # Refuse whole output before FIRST Pillow target allocation.
@pytest.mark.parametrize('id',IDS)
def test_schema_exact_ids_default_options_output_types_and_authority(id):
    row=LEDGER[id];c=NEW.NODE_CLASS_MAPPINGS[id];s=c.GET_SCHEMA()
    assert s.node_id==id and s.display_name==row['display_name'] and s.category==row['category']
    assert c.SDK_REFS is True and list(c.SDK_PERMISSIONS)==row['permissions']
    source={k:spec for fields in row['source_inputs'].values() for k,spec in fields.items()}
    assert [i.id for i in s.inputs]==list(source) and [o.io_type for o in s.outputs]==row['return_types'] and [o.display_name for o in s.outputs]==row['return_names']
    for i in s.inputs:
        if i.id.startswith('upscale_model'):
            assert i.remote.route=='/secure-nodes/models/upscale_models' and i.options==(['None'] if id==IDS[1] else [])
        elif isinstance(source[i.id][0],list):assert i.options==source[i.id][0]
        for k,v in (source[i.id][1] if len(source[i.id])>1 else {}).items():assert i.as_dict()[k]==v
    assert hashlib.sha256((PACK/'nodes'/row['source_file']).read_bytes()).hexdigest()==row['source_sha256']
    assert hashlib.sha256((PACK/'nodes'/row['helper_source_file']).read_bytes()).hexdigest()==row['helper_source_sha256']
def test_two_recreated_guests_actual_tiled_and_outer_image_identity_models_raw_denial(loader,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for generation in range(2):
                session=await GuestSession('ned-upscale-'+str(generation),guest_runtime_root=V2).start()
                class Backend:
                    caps=('models','raw')
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=self.caps)
                backend=Backend();_sdk.providers.register_execution_backend(backend)
                async def execute(id,a):
                    cls=NEW.NODE_CLASS_MAPPINGS[id];cls.GET_SCHEMA()
                    result=await execution._async_map_node_over_list(prompt_id='upscale',unique_id='n',obj=cls,input_data_all={k:[v] for k,v in a.items()},func=cls.FUNCTION,v3_data=None)
                    return result[0].result
                try:
                    for id,a in [(IDS[0],args_single()),(IDS[0],args_single(upscale_model='one',rescale_factor=1)),(IDS[2],args_apply()),(IDS[2],args_apply(upscale_stack=[]))]:
                        old=oracle(loader);cls=old[LEDGER[id]['class']]
                        expected=getattr(cls(),cls.FUNCTION)(**a);actual=await execute(id,a);same(('value',actual),('value',expected))
                        assert type(actual[0]) is torch.Tensor and actual[0].dtype==expected[0].dtype
                        if id==IDS[2] and not a['upscale_stack']:assert actual[0] is a['image']
                    producer=await execute(IDS[1],args_stack());assert all(type(row) is tuple for row in producer[0])
                    for caps,error in [(('models',),'raw'),(('raw',),'models')]:
                        backend.caps=caps;before=len(loader['calls'])
                        with pytest.raises(wire.WireError,match=error):await execute(IDS[0],args_single())
                        assert len(loader['calls'])==before
                    backend.caps=();assert await execute(IDS[1],args_stack())==oracle(loader)['CR_MultiUpscaleStack']().stack(**args_stack())
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert pids[0]!=pids[1]
            session=await GuestSession('ned-upscale-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                cls=NEW.NODE_CLASS_MAPPINGS[IDS[0]];cls.GET_SCHEMA();a=args_single()
                expected=oracle(loader)['CR_UpscaleImage']().upscale(**a)
                r=await execution._async_map_node_over_list(prompt_id='upscale-production',unique_id='n',obj=cls,input_data_all={k:[v] for k,v in a.items()},func=cls.FUNCTION,v3_data=None)
                r=await execution.resolve_map_node_over_list_results(r);same(('value',r[0].result),('value',expected))
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
