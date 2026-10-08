"""Actual canonical CLIP methods with synthetic CPU token arithmetic, not trained inference."""
import ast,asyncio,copy,importlib.util,os,sys,types
from pathlib import Path
import pytest,torch
sys.dont_write_bytecode=True;sys.argv=['ned-cr-sdxl','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
import comfy.sd
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_cr_sdxl',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
path=PACK/'nodes/nodes_sdxl.py';node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='CR_SDXLBasePromptEncoder')
ns={'icons':NEW.secure_sdxl.icons,'MAX_RESOLUTION':16384}
exec(compile(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]),str(path),'exec'),ns);OLD=ns['CR_SDXLBasePromptEncoder']
class Stage:
    def __init__(self,dtype,pooled):self.dtype,self.pooled=dtype,pooled;self.encodes=[];self.options=[]
    def reset_clip_options(self):self.options.append('reset')
    def set_clip_options(self,opts):self.options.append(dict(opts))
    def encode_token_weights(self,tokens):
        self.encodes.append(copy.deepcopy(tokens))
        values=[sum(x[0]*x[1] for row in tokens[k] for x in row) for k in ('g','l')]
        return torch.tensor(values,dtype=self.dtype).reshape(1,1,2),torch.tensor([sum(values)],dtype=self.dtype) if self.pooled else None,{'source_extra':7}
class Hooks:
    def get_hooks_for_clip_schedule(self):return [((0.,.5),[]),((.5,1.),[])]
    def reset(self):pass
def make(dtype=torch.float32,pooled=True,scheduled=True):
    clip=object.__new__(comfy.sd.CLIP);clip.cond_stage_model=Stage(dtype,pooled);clip.layer_idx=-2;clip.use_clip_schedule=scheduled
    clip.apply_hooks_to_conds='synthetic-hooks';clip.patcher=types.SimpleNamespace(forced_hooks=Hooks(),load_device=torch.device('cpu'),patch_hooks=lambda _:None)
    clip.loads=[];clip.load_model=lambda tokens:clip.loads.append(copy.deepcopy(tokens))
    clip.texts=[]
    def tokenize(text,**kwargs):
        clip.texts.append(text)
        return {k:[[(len(part)+index+1,1.,index)] for index,part in enumerate(text.split('|'))] for k in ('g','l')}
    clip.tokenize=tokenize
    return clip
def args(preset='preset C',texts=('p|q','style','bad','neg|style|tail'),**kwargs):
    return dict(pos_g=texts[0],pos_l=texts[1],neg_g=texts[2],neg_l=texts[3],preset=preset,
        base_width=4096,base_height=3072,crop_w=0,crop_h=64,target_width=1024,target_height=768,**kwargs)
async def local(clip,values):
    refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,dict(values,base_clip=clip))
    with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):result=await NEW.secure_sdxl.CR_SDXLBasePromptEncoder.execute(**wrapped)
    return (await refs.resolve(result.result[0]),await refs.resolve(result.result[1]),result.result[2])
def same(actual,expected):
    assert actual[2]==expected[2]
    for got,want in zip(actual[:2],expected[:2]):
        assert len(got)==len(want)
        for g,w in zip(got,want):
            assert g[0].shape==w[0].shape and g[0].dtype==w[0].dtype and torch.equal(g[0],w[0])
            assert set(g[1])==set(w[1])=={'pooled_output','width','height','crop_w','crop_h','target_width','target_height'}
            for key,value in w[1].items():
                if isinstance(value,torch.Tensor):assert torch.equal(g[1][key],value) and g[1][key].dtype==value.dtype
                else:assert type(g[1][key]) is type(value) and g[1][key]==value
@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('pooled',[False,True])
@pytest.mark.parametrize('scheduled',[False,True])
@pytest.mark.parametrize('preset',['preset A','preset B','preset C'])
@pytest.mark.parametrize('texts',[('','','',''),('p|q','style','bad','neg|style|tail'),('long','a|b|c','x|y','z'),('注釈🐈|comment','<script>','bad\\ntext','negative')])
def test_exact_source_four_calls_padding_order_presets_metadata(dtype,pooled,scheduled,preset,texts):
    old,new=make(dtype,pooled,scheduled),make(dtype,pooled,scheduled);values=args(preset,texts)
    expected=OLD().encode(base_clip=old,**values);actual=asyncio.run(local(new,values));same(actual,expected)
    assert len(new.cond_stage_model.encodes)==len(old.cond_stage_model.encodes)==4
    assert new.cond_stage_model.encodes==old.cond_stage_model.encodes and new.texts==old.texts
    assert new.loads==old.loads and new.cond_stage_model.options==old.cond_stage_model.options
@pytest.mark.parametrize('preset',[None,'invalid','preset a'])
def test_native_bad_preset_failure_after_all_four_calls(preset):
    old,new=make(),make();values=args(preset)
    with pytest.raises(UnboundLocalError):OLD().encode(base_clip=old,**values)
    with pytest.raises(UnboundLocalError):asyncio.run(local(new,values))
    assert len(new.cond_stage_model.encodes)==len(old.cond_stage_model.encodes)==4
    assert new.cond_stage_model.encodes==old.cond_stage_model.encodes
def test_exact_schema_defaults_options_and_outputs():
    schema=NEW.secure_sdxl.CR_SDXLBasePromptEncoder.GET_SCHEMA();source=OLD.INPUT_TYPES()['required']
    assert [i.id for i in schema.inputs]==list(source)
    assert [o.io_type for o in schema.outputs]==list(OLD.RETURN_TYPES) and [o.display_name for o in schema.outputs]==list(OLD.RETURN_NAMES)
    assert schema.category==OLD.CATEGORY
    for i in schema.inputs:
        src=source[i.id]
        if isinstance(src[0],list):assert i.as_dict()['options']==src[0]
        else:assert i.io_type==src[0]
        for key,value in (src[1] if len(src)>1 else {}).items():
            actual=i.as_dict()[key];assert actual==value and type(actual) is type(value)
    assert NEW.secure_sdxl.CR_SDXLBasePromptEncoder.SDK_PERMISSIONS==()
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
def test_default_float_metadata_direct_source_parity():
    values=args();values.update(base_width=4096.,base_height=4096.,target_width=4096.,target_height=4096.)
    old,new=make(),make();expected=OLD().encode(base_clip=old,**values)
    actual=asyncio.run(local(new,values))
    same(actual,expected)
@pytest.mark.parametrize('component',['g','l'])
def test_nonprogressing_padding_is_bounded_not_native_infinite_loop(component):
    clip=make()
    def tokenize(text,**kw):
        if text=='':return {'g':[] if component=='g' else [[(1,1.)]],'l':[] if component=='l' else [[(1,1.)]]}
        return {'g':[[(1,1.)]]*(3 if component=='l' else 1),'l':[[(1,1.)]]*(3 if component=='g' else 1)}
    clip.tokenize=tokenize
    with pytest.raises(ValueError,match='would not terminate'):asyncio.run(local(clip,args(texts=('a','b','c','d'))))
    assert not clip.cond_stage_model.encodes
def test_text_and_token_work_are_bounded_before_encoder():
    clip=make();values=args();values['pos_g']='a'*262145
    with pytest.raises(ValueError,match='workload'):asyncio.run(local(clip,values))
    assert not clip.texts and not clip.cond_stage_model.encodes
    clip=make();clip.tokenize=lambda text,**kw:{'g':[[(1,1.)]]*5000,'l':[[(1,1.)]]}
    with pytest.raises(ValueError,match='workload'):asyncio.run(local(clip,args()))
    assert not clip.cond_stage_model.encodes
def test_fresh_zero_capability_guest_real_canonical_four_calls_outer():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-cr-sdxl-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                cls=NEW.secure_sdxl.CR_SDXLBasePromptEncoder;cls.GET_SCHEMA()
                try:
                    for dtype in (torch.float32,torch.float16,torch.bfloat16):
                        for preset in ('preset A','preset B','preset C'):
                            clip,old=make(dtype),make(dtype);values=args(preset)
                            r=await execution._async_map_node_over_list(prompt_id='sdxl',unique_id='encode',obj=cls,input_data_all={k:[v] for k,v in dict(values,base_clip=clip).items()},func=cls.FUNCTION,v3_data=None)
                            same(r[0].result,OLD().encode(base_clip=old,**values))
                            assert clip.cond_stage_model.encodes==old.cond_stage_model.encodes and clip.loads==old.loads and clip.texts==old.texts
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1] and all(pid!=os.getpid() for pid in pids)
    asyncio.run(run())
def test_production_sdxl_entrypoint_outer_unscheduled_no_extra_metadata(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-cr-sdxl-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*a,**k):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            cls=NEW.secure_sdxl.CR_SDXLBasePromptEncoder;cls.GET_SCHEMA();clip,old=make(torch.bfloat16),make(torch.bfloat16);values=args()
            r=await execution._async_map_node_over_list(prompt_id='sdxl-production',unique_id='encode',obj=cls,input_data_all={k:[v] for k,v in dict(values,base_clip=clip).items()},func=cls.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);same(r[0].result,OLD().encode(base_clip=old,**values))
            assert clip.cond_stage_model.encodes==old.cond_stage_model.encodes and len(clip.loads)==4
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

