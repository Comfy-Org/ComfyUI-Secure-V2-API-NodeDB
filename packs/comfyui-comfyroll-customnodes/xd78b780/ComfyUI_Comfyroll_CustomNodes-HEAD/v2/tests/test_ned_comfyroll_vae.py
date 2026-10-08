"""Actual canonical CPU synthetic VAE source math and reviewed scoped-padding lifetime, no weights."""
import ast,asyncio,copy,importlib.util,json,os,sys,types
from pathlib import Path
import pytest,torch
sys.dont_write_bytecode=True;sys.argv=['ned-cr-vae','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy.sd import VAE
from comfy import model_management
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_cr_vae',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
LEDGER=json.loads((V2/'vae-draft-ledger.json').read_text())['CR VAE Decode']
path=PACK/'nodes/nodes_core.py';source=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='CR_VAEDecode')
ns={'torch':torch,'icons':{}};exec(compile(ast.Module(body=[copy.deepcopy(source)],type_ignores=[]),str(path),'exec'),ns)
OLD=ns['CR_VAEDecode']

class Decoder(torch.nn.Module):
    def __init__(self,dtype,video=False):
        super().__init__();self.video=video;self.calls=[];self.fail=False;self.oom_once=False
        self.conv=(torch.nn.Conv3d if video else torch.nn.Conv2d)(3,3,3,padding=1,groups=3,bias=False,dtype=dtype)
        self.conv.weight.data.copy_(torch.arange(self.conv.weight.numel(),dtype=dtype).reshape_as(self.conv.weight)/self.conv.weight.numel())
        self.unused=torch.nn.Conv2d(1,1,3,padding=1,padding_mode='replicate')
        self.one=torch.nn.Conv1d(1,1,3,padding=1,padding_mode='reflect')
    def decode(self,samples,**kwargs):
        self.calls.append((self.conv.padding_mode,self.unused.padding_mode,kwargs))
        if self.fail:raise RuntimeError('controlled VAE decode failure')
        if self.oom_once:self.oom_once=False;raise torch.OutOfMemoryError('controlled VAE OOM')
        return self.conv(samples)

@pytest.fixture
def make(monkeypatch):
    monkeypatch.setattr(model_management,'load_models_gpu',lambda *a,**k:None)
    monkeypatch.setattr(model_management,'soft_empty_cache',lambda *a,**k:None)
    def factory(dtype=torch.float32,video=False,mode='zeros'):
        vae=object.__new__(VAE);vae.first_stage_model=Decoder(dtype,video)
        vae.first_stage_model.conv.padding_mode=mode
        vae.device=vae.output_device=torch.device('cpu');vae.vae_dtype=dtype;vae.vae_output_dtype=lambda:dtype
        vae.patcher=types.SimpleNamespace(get_free_memory=lambda _:4096)
        vae.memory_used_decode=vae.memory_used_encode=lambda *a:1
        vae.disable_offload=False;vae.latent_dim=3 if video else 2;vae.latent_channels=vae.output_channels=3
        vae.extra_1d_channel=None;vae.handles_tiling=False;vae.format_encoded=None;vae.crop_input=False;vae.pad_channel_value=None
        vae.upscale_ratio=vae.downscale_ratio=(1,1,1) if video else 1;vae.upscale_index_formula=None
        vae.process_output=vae.process_input=lambda x:x
        return vae
    return factory

def samples(dtype=torch.float32,video=False,batch=1):
    shape=(batch,3,2,5,7) if video else (batch,3,5,7)
    return {'samples':torch.arange(torch.Size(shape).numel(),dtype=dtype).reshape(shape)/max(1,torch.Size(shape).numel()),'extra_metadata':'retained input not modified'}

async def migrated(value,args):
    refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,dict(args,vae=value))
    with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
        result=await NEW.secure_vae.CR_VAEDecode.execute(**wrapped)
    return (await refs.resolve(result.result[0]),result.result[1])

def exact(actual,expected):
    assert actual[1]==expected[1] and type(actual[1]) is str
    assert actual[0].shape==expected[0].shape and actual[0].dtype==expected[0].dtype and torch.equal(actual[0],expected[0])

@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('tiled',[False,True])
@pytest.mark.parametrize('circular',[False,True])
@pytest.mark.parametrize('batch',[1,2])
def test_exact_pinned_convolution_native_tiles_dtype_batch_and_prior_state_restoration(make,dtype,tiled,circular,batch):
    old_value=make(dtype);new_value=make(dtype);args=dict(samples=samples(dtype,batch=batch),tiled=tiled,circular=circular)
    expected=OLD().vae_decode(vae=old_value,**args)
    original=args['samples']['samples'].clone()
    actual=asyncio.run(migrated(new_value,args));exact(actual,expected)
    assert old_value.first_stage_model.conv.padding_mode==('circular' if circular else 'zeros')
    assert old_value.first_stage_model.unused.padding_mode==('circular' if circular else 'replicate')
    assert new_value.first_stage_model.conv.padding_mode=='zeros' and new_value.first_stage_model.unused.padding_mode=='replicate'
    assert new_value.first_stage_model.one.padding_mode=='reflect'
    assert new_value.first_stage_model.calls==old_value.first_stage_model.calls
    assert torch.equal(args['samples']['samples'],original) and args['samples']['extra_metadata']=='retained input not modified'

@pytest.mark.parametrize('mode',['zeros','replicate','reflect','circular'])
@pytest.mark.parametrize('tiled',[False,True])
def test_exact_prior_padding_modes_restore_success(make,mode,tiled):
    value=make(mode=mode);baseline=value.decode(samples()['samples'])
    actual=asyncio.run(migrated(value,dict(samples=samples(),tiled=tiled,circular=True)))
    assert value.first_stage_model.conv.padding_mode==mode and value.first_stage_model.unused.padding_mode=='replicate'
    assert torch.equal(value.decode(samples()['samples']),baseline)
    assert actual[0].shape==(1,5,7,3)

@pytest.mark.parametrize('tiled',[False,True])
@pytest.mark.parametrize('flag',[0,1,2,1.0,'true',None])
def test_source_equals_true_semantics_not_truthiness(make,tiled,flag):
    args=dict(samples=samples(),tiled=tiled,circular=flag)
    exact(asyncio.run(migrated(make(),args)),OLD().vae_decode(vae=make(),**args))

@pytest.mark.parametrize('video',[False,True])
@pytest.mark.parametrize('tiled',[False,True])
def test_source_video_layout_is_not_flattened_by_public_native_operation(make,video,tiled):
    args=dict(samples=samples(video=video),tiled=tiled,circular=True)
    actual=asyncio.run(migrated(make(video=video),args));expected=OLD().vae_decode(vae=make(video=video),**args);exact(actual,expected)
    assert actual[0].shape==((1,2,5,7,3) if video else (1,5,7,3))

@pytest.mark.parametrize('tiled',[False,True])
def test_circular_failure_restoration_without_suppressing_native_error(make,tiled):
    value=make(mode='reflect');value.first_stage_model.fail=True
    with pytest.raises(RuntimeError,match='controlled VAE decode failure'):
        asyncio.run(migrated(value,dict(samples=samples(),tiled=tiled,circular=True)))
    assert value.first_stage_model.conv.padding_mode=='reflect' and value.first_stage_model.unused.padding_mode=='replicate'

def test_circular_oom_fallback_scope_restores_after_exact_success(make):
    value=make();value.first_stage_model.oom_once=True
    actual=asyncio.run(migrated(value,dict(samples=samples(),tiled=False,circular=True)))
    control=make();control.first_stage_model.conv.padding_mode='circular';control.first_stage_model.unused.padding_mode='circular'
    expected=control.decode_tiled_(samples()['samples']).movedim(1,-1)
    assert torch.equal(actual[0],expected)
    assert set(mode for mode,_,kw in value.first_stage_model.calls)=={'circular'}
    assert value.first_stage_model.conv.padding_mode=='zeros' and value.first_stage_model.unused.padding_mode=='replicate'

def test_exact_native_kwargs_omission_and_two_output_schema():
    cls=NEW.secure_vae.CR_VAEDecode;schema=cls.GET_SCHEMA()
    assert schema.node_id=='CR VAE Decode' and schema.display_name==LEDGER['display_name'] and schema.category==LEDGER['category']
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==()
    assert [o.io_type for o in schema.outputs]==LEDGER['return_types'] and [o.display_name for o in schema.outputs]==LEDGER['return_names']
    assert [i.id for i in schema.inputs]==list(LEDGER['source_inputs']['required'])
    for i in schema.inputs:
        info=LEDGER['source_inputs']['required'][i.id];assert i.io_type==info[0]
        for k,v in (info[1] if len(info)>1 else {}).items():assert i.as_dict()[k]==v
    class Trace:
        def __init__(self):self.calls=[]
        async def decode(self,latent,**kwargs):self.calls.append(('decode',latent,kwargs));return 'opaque-test-image'
        async def decode_tiled_native(self,latent,**kwargs):self.calls.append(('native',latent,kwargs));return 'opaque-test-image'
    for tiled in (False,True):
        trace=Trace();r=asyncio.run(cls.execute('latent-test-token',trace,tiled=tiled,circular=False))
        assert len(r.result)==2
        assert trace.calls==[('native' if tiled else 'decode','latent-test-token',dict(tile_x=512,tile_y=512,padding_mode='default') if tiled else {'padding_mode':'default'})]
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_two_fresh_zero_capability_guests_outer_exact_convolution_video_and_scoped_failure(make):
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-cr-vae-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                async def execute(value,args):
                    cls=NEW.secure_vae.CR_VAEDecode;cls.GET_SCHEMA()
                    r=await execution._async_map_node_over_list(prompt_id='cr-vae',unique_id='vae',obj=cls,input_data_all={k:[v] for k,v in dict(args,vae=value).items()},func=cls.FUNCTION,v3_data=None)
                    return r[0].result
                try:
                    for dtype in (torch.float32,torch.float16,torch.bfloat16):
                        for tiled,circular in ((False,False),(False,True),(True,False),(True,True)):
                            value=make(dtype);args=dict(samples=samples(dtype),tiled=tiled,circular=circular)
                            exact(await execute(value,args),OLD().vae_decode(vae=make(dtype),**args))
                            assert value.first_stage_model.conv.padding_mode=='zeros' and value.first_stage_model.unused.padding_mode=='replicate'
                    value=make(video=True);args=dict(samples=samples(video=True),tiled=True,circular=True)
                    actual=await execute(value,args);exact(actual,OLD().vae_decode(vae=make(video=True),**args))
                    assert actual[0].ndim==5 and value.first_stage_model.unused.padding_mode=='replicate'
                    value=make();value.first_stage_model.fail=True
                    with pytest.raises(wire.WireError,match='controlled VAE decode failure'):await execute(value,dict(samples=samples(),tiled=True,circular=True))
                    assert value.first_stage_model.conv.padding_mode=='zeros' and value.first_stage_model.unused.padding_mode=='replicate'
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1]
    asyncio.run(run())

def test_production_dispatch_registered_vae_zero_authority(make,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-cr-vae-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*a,**k):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            cls=NEW.secure_vae.CR_VAEDecode;cls.GET_SCHEMA()
            for tiled in (False,True):
                value=make();args=dict(samples=samples(),vae=value,tiled=tiled,circular=True)
                r=await execution._async_map_node_over_list(prompt_id='vae-production',unique_id='vae',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                r=await execution.resolve_map_node_over_list_results(r);expected=OLD().vae_decode(vae=make(),samples=args['samples'],tiled=tiled,circular=True)
                exact(r[0].result,expected);assert value.first_stage_model.conv.padding_mode=='zeros'
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

