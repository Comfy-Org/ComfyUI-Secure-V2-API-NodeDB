"""Pinned multi-list concat and approved one/zero branch normalization; typed original identity."""
import ast,asyncio,copy,os
import pytest,torch
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire
node=next(n for n in ast.parse((PACK/'nodes/nodes_list.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='CR_MakeBatchFromImageList')
ns={'torch':torch,'icons':NEW.secure_image_batch.icons};exec(compile(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]),str(PACK/'nodes/nodes_list.py'),'exec'),ns);OLD=ns['CR_MakeBatchFromImageList']
ID='CR Batch Images From List';HELP='https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-binary-to-list'
def images(dtype,n=3):return [torch.arange((i+1)*3*4*3,dtype=torch.float32).reshape(i+1,3,4,3).to(dtype)/100 for i in range(n)]
async def migrated(values):
    refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,{'image_list':values},{'image_list':'IMAGE'})
    with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):r=await NEW.secure_image_batch.CR_MakeBatchFromImageList.execute(**wrapped)
    return await refs.resolve(r.result[0]),r.result[1]
@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('n',[2,3,5])
def test_source_multibatch_order_shape_values_dtype_and_no_mutation(dtype,n):
    values=images(dtype,n);before=[t.clone() for t in values];expected=OLD().make_batch(values);actual=asyncio.run(migrated(values))
    assert actual[0].dtype==expected[0].dtype and torch.equal(actual[0],expected[0]) and actual[1]==expected[1]==HELP
    for a,b in zip(values,before):assert torch.equal(a,b)
@pytest.mark.parametrize('n',[0,1])
def test_original_one_slot_list_defect_and_reviewed_empty_single_fix(n):
    values=images(torch.float32,n);expected=OLD().make_batch(values)
    assert len(expected)==1 and expected[0] is values
    if not values:
        with pytest.raises(ValueError,match='empty'):asyncio.run(migrated(values))
    else:
        actual=asyncio.run(migrated(values));assert actual[0] is values[0] and actual[1]==HELP
@pytest.mark.parametrize('values',[[torch.empty(0,3,4,3),torch.zeros(1,3,4,3)],[torch.zeros(1,3,4,3),torch.zeros(1,2,4,3)],[torch.zeros(1,3,4,3),torch.zeros(1,3,4,4)],[torch.ones(1,3,4,3,dtype=torch.float16),torch.ones(1,3,4,3,dtype=torch.bfloat16)]])
def test_admitted_empty_batches_and_native_cat_shape_errors(values):
    try:expected=('value',OLD().make_batch(values))
    except Exception as exc:expected=('error',type(exc),str(exc))
    try:actual=('value',asyncio.run(migrated(values)))
    except Exception as exc:actual=('error',type(exc),str(exc))
    assert actual[0]==expected[0]
    if expected[0]=='error':assert actual[1:]==expected[1:]
    else:assert torch.equal(actual[1][0],expected[1][0])
def test_exact_list_schema_and_preflight_before_cat(monkeypatch):
    c=NEW.secure_image_batch.CR_MakeBatchFromImageList;s=c.GET_SCHEMA()
    assert s.node_id==ID and s.is_input_list and s.category==OLD.CATEGORY and c.SDK_PERMISSIONS==('raw',)
    assert [i.id for i in s.inputs]==['image_list'] and [o.io_type for o in s.outputs]==list(OLD.RETURN_TYPES)
    assert [o.display_name for o in s.outputs]==list(OLD.RETURN_NAMES)
    with pytest.raises(ValueError,match='bound'):asyncio.run(migrated(images(torch.float32,1)*65))
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
def test_real_two_guests_outer_list_admission_single_identity_raw_deny_and_production(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[];cls=NEW.secure_image_batch.CR_MakeBatchFromImageList;cls.GET_SCHEMA()
        async def execute(values):
            r=await execution._async_map_node_over_list(prompt_id='image-batch',unique_id='batch',obj=cls,input_data_all={'image_list':values},func=cls.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0].result
        try:
            for render in range(2):
                session=await GuestSession('ned-image-batch-'+str(render),guest_runtime_root=V2).start();caps={'value':('raw',)}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for dtype in (torch.float32,torch.float16,torch.bfloat16):
                        for n in (1,3):
                            values=images(dtype,n);actual=await execute(values)
                            assert actual[1]==HELP and torch.equal(actual[0],values[0] if n==1 else torch.cat(values,dim=0))
                            if n==1:assert actual[0] is values[0]
                    caps['value']=()
                    values=images(torch.float32,1);actual=await execute(values);assert actual[0] is values[0] # Single opaque pass does not need raw resolution.
                    with pytest.raises(wire.WireError,match='raw|capability|permission'):await execute(images(torch.float32,2))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
            session=await GuestSession('ned-image-batch-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                values=images(torch.bfloat16);actual=await execute(values);assert torch.equal(actual[0],torch.cat(values,dim=0)) and actual[0].dtype==torch.bfloat16
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
