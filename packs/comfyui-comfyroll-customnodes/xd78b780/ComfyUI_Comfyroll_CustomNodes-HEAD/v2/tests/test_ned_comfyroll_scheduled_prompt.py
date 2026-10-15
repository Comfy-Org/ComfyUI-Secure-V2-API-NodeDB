"""Pinned weighted conditioning with actual canonical CLIP and raw-isolated guests; CPU synthetic only."""
import ast,asyncio,copy,os
import pytest,torch
from test_ned_comfyroll_sdxl import V2,PACK,NEW,make,Stage,_sdk,GuestSession,wire
node=next(n for n in ast.parse((PACK/'nodes/nodes_animation_prompt.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='CR_EncodeScheduledPrompts')
ns={'torch':torch,'icons':NEW.secure_sdxl.icons}
exec(compile(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]),str(PACK/'nodes/nodes_animation_prompt.py'),'exec'),ns);OLD=ns['CR_EncodeScheduledPrompts']
class SequenceStage(Stage):
    def encode_token_weights(self,tokens):
        self.encodes.append(copy.deepcopy(tokens))
        n=len(tokens['g']);values=[entry[0]*entry[1] for row in tokens['g'] for entry in row]
        cond=torch.tensor(values,dtype=self.dtype).reshape(1,n,1).repeat(1,1,4)
        pool=torch.tensor([sum(values)]*4,dtype=self.dtype).reshape(1,4) if self.pooled else None
        return cond,pool,{'source_extra':7}
def clip(dtype=torch.float32,pooled=True):
    value=make(dtype,pooled);value.cond_stage_model=SequenceStage(dtype,pooled);return value
def same(actual,expected):
    assert actual[1]==expected[1] and len(actual[0])==len(expected[0])==1
    a,b=actual[0][0],expected[0][0];assert a[0].shape==b[0].shape and a[0].dtype==b[0].dtype and torch.equal(a[0],b[0])
    assert set(a[1])==set(b[1])=={'pooled_output'}
    ap,bp=a[1]['pooled_output'],b[1]['pooled_output']
    if bp is None:assert ap is None
    else:assert ap.dtype==bp.dtype and torch.equal(ap,bp)
async def migrated(value,args):
    refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,dict(args,clip=value))
    with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):r=await NEW.secure_scheduled_prompt.CR_EncodeScheduledPrompts.execute(**wrapped)
    return await refs.resolve(r.result[0]),r.result[1]
@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('pooled',[False,True])
@pytest.mark.parametrize('weight',[-2,0,.25,1,5])
@pytest.mark.parametrize('current,next_', [('same','same'),('a|b|c','short'),('short','a|b|c'),('','注釈🐈|<script>')])
def test_pinned_padding_pooled_dtype_order_and_extrapolation(dtype,pooled,weight,current,next_):
    old,new=clip(dtype,pooled),clip(dtype,pooled);args=dict(current_prompt=current,next_prompt=next_,weight=weight)
    expected=OLD().condition(clip=old,**args);actual=asyncio.run(migrated(new,args));same(actual,expected)
    assert old.texts==new.texts==[next_,current]
    assert old.cond_stage_model.encodes==new.cond_stage_model.encodes and len(new.loads)==2
@pytest.mark.parametrize('weight',[None,'bad'])
def test_source_native_weight_errors_after_both_encodes(weight):
    args=dict(current_prompt='a|b|c',next_prompt='short',weight=weight);old,new=clip(),clip()
    with pytest.raises(TypeError):OLD().condition(clip=old,**args)
    with pytest.raises(TypeError):asyncio.run(migrated(new,args))
    assert old.texts==new.texts and len(new.loads)==2
def test_exact_schema_raw_only_and_no_cache():
    schema=NEW.secure_scheduled_prompt.CR_EncodeScheduledPrompts.GET_SCHEMA();inputs=OLD.INPUT_TYPES()['required']
    assert [i.id for i in schema.inputs]==list(inputs)
    assert [o.io_type for o in schema.outputs]==list(OLD.RETURN_TYPES) and [o.display_name for o in schema.outputs]==list(OLD.RETURN_NAMES)
    assert schema.category==OLD.CATEGORY and NEW.secure_scheduled_prompt.CR_EncodeScheduledPrompts.SDK_PERMISSIONS==('raw',)
    for i in schema.inputs:
        assert i.io_type==inputs[i.id][0]
        for k,v in (inputs[i.id][1] if len(inputs[i.id])>1 else {}).items():assert i.as_dict()[k]==v
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
def test_text_token_input_bound_and_nonfinite_weight_before_encoder():
    value=clip()
    for args in [dict(current_prompt='x'*262145,next_prompt='',weight=1),dict(current_prompt='',next_prompt='',weight=float('nan'))]:
        with pytest.raises(ValueError,match='workload|finite'):asyncio.run(migrated(value,args))
        assert not value.loads and not value.texts
def test_two_fresh_raw_guests_outer_exact_dtype_pooled_and_denial():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-cr-scheduled-prompt-'+str(render),guest_runtime_root=V2).start();caps={'value':('raw',)}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend());cls=NEW.secure_scheduled_prompt.CR_EncodeScheduledPrompts;cls.GET_SCHEMA()
                async def execute(value,args):
                    result=await execution._async_map_node_over_list(prompt_id='scheduled',unique_id='encode',obj=cls,input_data_all={k:[v] for k,v in dict(args,clip=value).items()},func=cls.FUNCTION,v3_data=None)
                    return result[0].result
                try:
                    for dtype in (torch.float32,torch.float16,torch.bfloat16):
                        for pooled in (False,True):
                            value,old=clip(dtype,pooled),clip(dtype,pooled);args=dict(current_prompt='a|b|c',next_prompt='short',weight=.25)
                            same(await execute(value,args),OLD().condition(clip=old,**args))
                            assert value.cond_stage_model.encodes==old.cond_stage_model.encodes and len(value.loads)==2
                    caps['value']=()
                    with pytest.raises(wire.WireError,match='raw|capability|permission'):
                        await execute(clip(),dict(current_prompt='current',next_prompt='next',weight=1))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1] and all(pid!=os.getpid() for pid in pids)
    asyncio.run(run())
def test_production_scheduled_prompt_outer_raw_only(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-cr-scheduled-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*a,**k):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            cls=NEW.secure_scheduled_prompt.CR_EncodeScheduledPrompts;cls.GET_SCHEMA();value,old=clip(torch.bfloat16),clip(torch.bfloat16)
            args=dict(current_prompt='a|b|c',next_prompt='short',weight=-2)
            result=await execution._async_map_node_over_list(prompt_id='scheduled-production',unique_id='encode',obj=cls,input_data_all={k:[v] for k,v in dict(args,clip=value).items()},func=cls.FUNCTION,v3_data=None)
            result=await execution.resolve_map_node_over_list_results(result);same(result[0].result,OLD().condition(clip=old,**args))
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())

