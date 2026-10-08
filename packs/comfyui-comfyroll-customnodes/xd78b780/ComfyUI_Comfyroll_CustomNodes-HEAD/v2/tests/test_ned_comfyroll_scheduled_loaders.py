"""Exact pinned schedule policy + approved two repairs; recording loads, not inference."""
import ast,asyncio,copy,json,os,types
import pytest
from test_ned_comfyroll_cycle_models import NEW,V2,PACK,_sdk,GuestSession,wire,loaders as checkpoint_loaders,ModelPatcher,CLIP,VaeDouble
from test_ned_comfyroll_animation_models import managed,ModelTrace,ClipTrace
import nodes,folder_paths,comfy.sd
@pytest.fixture
def loaders(checkpoint_loaders,monkeypatch):
    # The checkpoint-only fixture's logical path double must not override real
    # managed safetensors paths used by the native LoRA control in mixed tests.
    checkpoint_resolve=folder_paths.get_full_path_or_raise
    monkeypatch.setattr(folder_paths,'get_full_path_or_raise',lambda kind,name:folder_paths.get_full_path(kind,name) if kind=='loras' else checkpoint_resolve(kind,name))
    return checkpoint_loaders
IDS=['CR Load Scheduled Models','CR Load Scheduled LoRAs']
LEDGER=json.loads((V2/'scheduled-loaders-draft-ledger.json').read_text())
SOURCE=ast.parse((PACK/'nodes/nodes_animation_schedulers.py').read_text())
helper=next(n for n in ast.parse((PACK/'nodes/functions_animation.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='keyframe_scheduler')
icons=ast.literal_eval(ast.parse((PACK/'categories.py').read_text()).body[0].value)
def oracle(id,loaders=None,repair_log=True):
    node=copy.deepcopy(next(n for n in SOURCE.body if isinstance(n,ast.ClassDef) and n.name==LEDGER[id]['class']))
    if id==IDS[1] and repair_log:
        for value in ast.walk(node):
            if isinstance(value,ast.Name) and value.id=='lora_name' and value.lineno==461:value.id='default_lora'
    ns={'icons':icons,'LoraLoader':nodes.LoraLoader,'folder_paths':types.SimpleNamespace(get_filename_list=lambda folder:[],get_full_path=lambda k,n:n,get_folder_paths=lambda k:[]),'comfy':types.SimpleNamespace(sd=types.SimpleNamespace(load_checkpoint_guess_config=loaders['load'] if loaders else None))}
    exec(compile(ast.Module(body=[copy.deepcopy(helper),node],type_ignores=[]),str(PACK/'nodes/nodes_animation_schedulers.py'),'exec'),ns)
    return ns[LEDGER[id]['class']]()
def model_args(**changes):
    args=dict(mode='Schedule',current_frame=3,schedule_alias='model',default_model='one',schedule_format='CR',model_list=[('A','two'),('A','three'),('B','one')],schedule=[('model','0, A'),('model','10, B')]);args.update(changes);return args
def lora_args(**changes):
    args=dict(mode='Schedule',model=ModelTrace(),clip=ClipTrace(),current_frame=3,schedule_alias='lora',default_lora='3.safetensors',strength_model=.2,strength_clip=-.4,schedule_format='CR',lora_list=[('A','1.safetensors',99,-98),('A','2.safetensors',2,3),('B','2.safetensors',1,1)],schedule=[('lora','0, A, .5, -8'),('lora','10, B, -.7, not-used')]);args.update(changes);return args
async def migrated(id,args):
    refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,args)
    ctx=types.SimpleNamespace(models=_sdk._InProcessModels(),assets=_sdk._InProcessAssets())
    with _sdk.bind_runtime(refs,ctx,_sdk.InProcessOps()):r=await NEW.NODE_CLASS_MAPPINGS[id].execute(**wrapped)
    if isinstance(r,tuple):return r
    out=[]
    for value in r.result:out.append(await refs.resolve(value) if isinstance(value,_sdk.Ref) else value)
    return tuple(out)
def outcome(fn):
    try:return 'value',fn()
    except Exception as exc:return 'error',type(exc),str(exc)
def model_value(value):
    if not value:return value
    return value[0].model_options,value[1].tokenizer_options,type(value[2]),value[3]
def lora_value(value):return value[0].trace,value[1].trace,value[2]
@pytest.mark.parametrize('mode',['Load default Model','Schedule','other'])
@pytest.mark.parametrize('frame',[-1,0,3,10,11,99,0.0,1.5])
@pytest.mark.parametrize('fmt',['CR','Deforum'])
@pytest.mark.parametrize('schedule',[[],[('different','0, A')],[('model','0, A'),('model','10, B')],[('model','10, B'),('model','0, A')],[('model','  '),('model','0, B')]])
def test_model_exact_first_alias_frame_default_order_and_ignored_format(loaders,mode,frame,fmt,schedule):
    args=model_args(mode=mode,current_frame=frame,schedule_format=fmt,schedule=schedule)
    native=oracle(IDS[0],loaders).schedule(**args);calls=list(loaders['calls']);loaders['calls'].clear()
    assert len(native)==2 and len(native[0])==3
    actual=asyncio.run(migrated(IDS[0],args))
    assert model_value(actual)==model_value((*native[0],native[1])) and len(actual)==4
    assert loaders['calls']==calls
@pytest.mark.parametrize('mode',['Off','Load default LoRA','Schedule','other'])
@pytest.mark.parametrize('frame',[-1,0,3,10,99,0.0,1.5])
@pytest.mark.parametrize('fmt',['CR','Deforum'])
@pytest.mark.parametrize('strengths',[(0,0),(.2,-.4),(-1.,.5)])
def test_lora_exact_draw_frame_alias_and_both_scheduled_strengths_from_part1(managed,mode,frame,fmt,strengths):
    old,applications=managed;args=lora_args(mode=mode,current_frame=frame,schedule_format=fmt,strength_model=strengths[0],strength_clip=strengths[1])
    expected=oracle(IDS[1]).schedule(**args);calls=list(applications);applications.clear()
    actual=asyncio.run(migrated(IDS[1],args));assert lora_value(actual)==lora_value(expected) and applications==calls
    if calls and mode not in ('Off','Load default LoRA') and frame>=0:
        assert all(call[1]==call[2] for call in calls)
        assert calls[0][0] in (1.,2.)
def test_default_lora_native_unbound_after_load_and_only_log_repair(managed):
    old,applications=managed;args=lora_args(mode='Load default LoRA')
    with pytest.raises(UnboundLocalError,match='lora_name'):oracle(IDS[1],repair_log=False).schedule(**args)
    source_calls=list(applications);applications.clear();actual=asyncio.run(migrated(IDS[1],args))
    assert applications==source_calls==[(3.,.2,-.4)] and lora_value(actual)[:2]==(((3.,.2),),((3.,-.4),))
@pytest.mark.parametrize('id',IDS)
@pytest.mark.parametrize('changes',[{'schedule':None},{'schedule':[('model','bad')]},{'schedule':[('lora','bad')]},{'model_list':None,'lora_list':None},{'model_list':[],'lora_list':[]},{'schedule':[('model','0, missing'),('lora','0, missing,.5,.2')]},{'schedule':[('lora','0, A, invalid, .2')]},{'schedule':[('lora','0, A,.1')]},{'schedule':[('model','0, A')],'model_list':[('A','')]},{'schedule':[('lora','0, A,.5,.2')],'lora_list':[('A','',1,1)]}])
def test_native_missing_alias_parse_and_empty_dispositions(id,changes,loaders,managed):
    args=model_args() if id==IDS[0] else lora_args()
    args.update({k:v for k,v in changes.items() if k in args})
    native=outcome(lambda:oracle(id,loaders).schedule(**args))
    actual=outcome(lambda:asyncio.run(migrated(id,args)))
    assert actual[0]==native[0]
    if native[0]=='error':assert actual[1:]==native[1:]
    elif native[1]==():assert actual[1]==()
    elif id==IDS[0]:assert model_value(actual[1])==model_value((*native[1][0],native[1][1]))
    else:assert lora_value(actual[1])==lora_value(native[1])
@pytest.mark.parametrize('id',IDS)
def test_exact_schema_remote_catalogues_default_floats_and_permissions(id):
    row=LEDGER[id];c=NEW.NODE_CLASS_MAPPINGS[id];s=c.GET_SCHEMA()
    assert s.node_id==id and s.display_name==row['display_name'] and s.category==row['category']
    assert c.SDK_REFS and list(c.SDK_PERMISSIONS)==row['permissions']
    assert [o.io_type for o in s.outputs]==row['return_types'] and [o.display_name for o in s.outputs]==row['return_names']
    inputs={k:(group,info) for group,values in row['source_inputs'].items() for k,info in values.items()}
    assert [i.id for i in s.inputs]==list(inputs)
    for i in s.inputs:
        group,info=inputs[i.id];assert i.optional==(group=='optional')
        if i.id in ('default_model','default_lora'):assert i.remote.route==('/secure-nodes/models/checkpoints' if i.id=='default_model' else '/secure-nodes/models/loras')
        elif isinstance(info[0],list):assert i.options==info[0]
        else:assert i.io_type==info[0]
        for k,v in (info[1] if len(info)>1 else {}).items():assert i.as_dict()[k]==v
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
@pytest.mark.parametrize('id',IDS)
@pytest.mark.parametrize('change',['rows','text','name','finite','weight'])
def test_bounds_precede_loading_and_path_denial(id,change,loaders,managed):
    args=model_args() if id==IDS[0] else lora_args();old,applications=managed
    if change=='rows':args['schedule']=[('other','0, A')]*257
    if change=='text':args['schedule_alias']='x'*262145
    if change=='name':
        args['mode']='Load default Model' if id==IDS[0] else 'Load default LoRA';args['default_model' if id==IDS[0] else 'default_lora']='../secret'
    if change=='finite':args['current_frame']=float('inf')
    if change=='weight':
        if id==IDS[0]:args['schedule_alias']='x'*262145
        else:args['schedule']=[('lora','0, A, 101, 0')]
    with pytest.raises(ValueError,match='bound|logical|finite|workload'):
        asyncio.run(migrated(id,args))
    assert not loaders['calls'] and not applications
def test_two_fresh_guests_all_branches_outer_models_and_lora_denials(loaders,managed,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(id,args):
            cls=NEW.NODE_CLASS_MAPPINGS[id];cls.GET_SCHEMA()
            result=await execution._async_map_node_over_list(prompt_id='scheduled-load',unique_id='loader',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
            result=await execution.resolve_map_node_over_list_results(result);return result[0].result
        try:
            for render in range(2):
                session=await GuestSession('ned-scheduled-loaders-'+str(render),guest_runtime_root=V2).start();caps={'value':('models','assets')}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for mode,frame in [('Load default Model',0.0),('Schedule',-1),('Schedule',0),('Schedule',10),('Schedule',99)]:
                        actual=await execute(IDS[0],model_args(mode=mode,current_frame=frame))
                        assert len(actual)==4 and all(actual[i] is loaders['loaded'][-1][i] for i in range(3)) and type(actual[3]) is str
                    for mode,frame in [('Off',3),('Load default LoRA',0.0),('Schedule',-1),('Schedule',3),('Schedule',10)]:
                        args=lora_args(mode=mode,current_frame=frame);expected=oracle(IDS[1]).schedule(**args);actual=await execute(IDS[1],args)
                        assert lora_value(actual)==lora_value(expected)
                        if mode=='Off':assert actual[0] is args['model'] and actual[1] is args['clip']
                    caps['value']=();before=(len(loaders['calls']),len(managed[1]))
                    with pytest.raises(wire.WireError,match='models|capability|permission'):await execute(IDS[0],model_args())
                    with pytest.raises(wire.WireError,match='assets|capability|permission'):await execute(IDS[1],lora_args())
                    assert before==(len(loaders['calls']),len(managed[1]));pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
            session=await GuestSession('ned-scheduled-loaders-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                actual=await execute(IDS[0],model_args());assert len(actual)==4 and all(actual[i] is loaders['loaded'][-1][i] for i in range(3))
                args=lora_args();expected=oracle(IDS[1]).schedule(**args);actual=await execute(IDS[1],args);assert lora_value(actual)==lora_value(expected)
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
