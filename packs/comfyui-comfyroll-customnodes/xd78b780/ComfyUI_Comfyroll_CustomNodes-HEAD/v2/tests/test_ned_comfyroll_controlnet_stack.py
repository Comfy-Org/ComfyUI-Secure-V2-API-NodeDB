"""Prepared per-ID pinned stack behavior/typed admission; copy only after185 freeze."""
import ast,asyncio,copy,json,os,types
import pytest,torch
from test_ned_comfyroll_controlnet import NEW,V2,PACK,_sdk,GuestSession,wire,image
import nodes,comfy.controlnet,comfy.sd,folder_paths
IDS=['CR Multi-ControlNet Stack','CR Apply Multi-ControlNet']
LEDGER=json.loads((V2/'controlnet-stack-draft-ledger.json').read_text());TREE=ast.parse((PACK/'nodes/nodes_controlnet.py').read_text())
class Control:
    def __init__(self,name='fixture',records=None):self.name=name;self.records=[] if records is None else records
    def copy(self):
        value=Control(self.name,self.records);self.records.append(value);return value
    def get_control(self,*a,**k):raise AssertionError('Recording only, no trained inference')
    def set_extra_arg(self,*a,**k):raise AssertionError('No arbitrary control extras')
    def set_cond_hint(self,hint,strength,range=None,**kw):self.hint=hint;self.strength=strength;self.range=range;self.kw=kw;return self
    def set_previous_controlnet(self,previous):self.previous=previous;return self
@pytest.fixture
def loader(monkeypatch):
    calls=[]
    def load(name,*a,**k):calls.append(name);return Control(name)
    monkeypatch.setattr(folder_paths,'get_full_path_or_raise',lambda folder,name:name)
    monkeypatch.setattr(comfy.controlnet,'load_controlnet',load)
    return calls,load
def oracle(id,loader,repair=True):
    node=copy.deepcopy(next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name==LEDGER[id]['class']))
    if id==IDS[1] and repair:
        for call in [n for n in ast.walk(node) if isinstance(n,ast.Call) and ast.unparse(n.func)=='comfy.sd.load_controlnet']:
            call.func=ast.parse('comfy.controlnet.load_controlnet',mode='eval').body
    ns={'icons':NEW.secure_controlnet.icons,'folder_paths':types.SimpleNamespace(get_filename_list=lambda _:[],get_full_path=lambda f,n:n),'comfy':types.SimpleNamespace(controlnet=types.SimpleNamespace(load_controlnet=loader[1]),sd=comfy.sd),'ControlNetApplyAdvanced':nodes.ControlNetApplyAdvanced}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(PACK/'nodes/nodes_controlnet.py'),'exec'),ns);return ns[LEDGER[id]['class']]()
def producer(**changes):
    a={}
    for i in range(1,4):
        a.update({f'switch_{i}':'On',f'controlnet_{i}':'cn'+str(i),f'controlnet_strength_{i}':i*.3,f'start_percent_{i}':.8,f'end_percent_{i}':.2,f'image_{i}':image(torch.float32)})
    a['controlnet_stack']=None;a.update(changes);return a
def conditioning(dtype):
    t=torch.arange(8,dtype=dtype).reshape(1,2,4);p=Control('prior')
    return [[t,{'tag':'A'}],[t,{'tag':'B','control':p}],[t,{'tag':'C','control':p,'control_apply_to_uncond':True}]]
def consumer(dtype=torch.float32,**changes):
    positive=conditioning(dtype);negative=[[positive[0][0],{'tag':'negative'}]]
    a=dict(base_positive=positive,base_negative=negative,switch='On',controlnet_stack=[(Control('first'),image(dtype),.7,.8,.2),(Control('second'),image(dtype),1.,.4,.4)])
    a.update(changes);return a
async def local(id,a):
    refs=_sdk.InProcessRefResolver();hints={'base_positive':'CONDITIONING','base_negative':'CONDITIONING'} if id==IDS[1] else {}
    wrapped=await _sdk.wrap_inputs(refs,a,hints)
    with _sdk.bind_runtime(refs,types.SimpleNamespace(models=_sdk._InProcessModels()),_sdk.InProcessOps()):r=await NEW.NODE_CLASS_MAPPINGS[id].execute(**wrapped)
    async def resolve(value):
        if isinstance(value,_sdk.Ref):return await refs.resolve(value)
        if isinstance(value,list):return [await resolve(x) for x in value]
        if isinstance(value,tuple):return tuple([await resolve(x) for x in value])
        return value
    return await resolve(r.result)
def stack_same(actual,expected):
    assert actual[1]==expected[1] and len(actual[0])==len(expected[0])
    for a,b in zip(actual[0],expected[0]):
        assert type(a) is type(b) is tuple and len(a)==len(b)==5
        assert a[0].name==b[0].name and a[1] is b[1] and a[2:]==b[2:]
def control_same(a,b):
    if not hasattr(b,'hint'):
        assert a is b # Original prior control/no-op, not an applied clone.
        return
    assert a.name==b.name and a.strength==b.strength and a.range==b.range and a.kw==b.kw
    assert a.hint.dtype==b.hint.dtype and torch.equal(a.hint,b.hint)
    ap,bp=a.previous,b.previous
    if hasattr(bp,'hint'):control_same(ap,bp)
    else:assert ap is bp
def paired_same(actual,expected):
    assert actual[2]==expected[2]
    for aa,bb in zip(actual[:2],expected[:2]):
        assert type(aa)==type(bb) and len(aa)==len(bb)
        for a,b in zip(aa,bb):
            assert a[0] is b[0] and set(a[1])==set(b[1])
            for key in b[1]:
                if key=='control':control_same(a[1][key],b[1][key])
                else:assert a[1][key]==b[1][key]
@pytest.mark.parametrize('mask',range(8))
@pytest.mark.parametrize('missing',[False,True])
@pytest.mark.parametrize('previous',[None,[],[(Control('prior'),None,1.,.2,.8)], [('None',None,0.,0.,1.)]])
def test_producer_exact_optional_switch_sentinel_filter_row_order_and_image_identity(loader,mask,missing,previous):
    a=producer(controlnet_stack=previous)
    for i in range(1,4):
        a[f'switch_{i}']='On' if mask&(1<<(i-1)) else 'Off'
        if missing and i==2:a[f'image_{i}']=None
        if missing and i==3:a[f'controlnet_{i}']='None'
    expected=oracle(IDS[0],loader).controlnet_stacker(**a);calls=list(loader[0]);loader[0].clear();actual=asyncio.run(local(IDS[0],a))
    stack_same(actual,expected);assert loader[0]==calls
@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('switch',['On','Off','unknown'])
@pytest.mark.parametrize('endpoint',[(0.,1.),(.8,.2),(.4,.4)])
@pytest.mark.parametrize('empty',[None,'positive','negative','both'])
def test_consumer_exact_pair_metadata_previous_dedup_and_unsorted_equal_endpoints(loader,dtype,switch,endpoint,empty):
    a=consumer(dtype,switch=switch);a['controlnet_stack']=[(Control('first'),image(dtype),.7,*endpoint)]
    if empty in ('positive','both'):a['base_positive']=[]
    if empty in ('negative','both'):a['base_negative']=[]
    expected=oracle(IDS[1],loader).apply_controlnet_stack(**a);actual=asyncio.run(local(IDS[1],a));paired_same(actual,expected)
    if switch=='Off':assert actual[0] is a['base_positive'] and actual[1] is a['base_negative']
@pytest.mark.parametrize('strength',[0,1.,-.3])
def test_string_loader_native_attribute_failure_reviewed_repair_and_zero_load_first(loader,strength):
    a=consumer();a['controlnet_stack']=[('registered',None if strength==0 else image(torch.float32),strength,.8,.2)]
    with pytest.raises(AttributeError,match='load_controlnet'):oracle(IDS[1],loader,repair=False).apply_controlnet_stack(**a)
    assert not loader[0]
    expected=oracle(IDS[1],loader).apply_controlnet_stack(**a);calls=list(loader[0]);loader[0].clear();actual=asyncio.run(local(IDS[1],a));paired_same(actual,expected)
    assert loader[0]==calls==['registered']
    if strength==0:assert actual[0] is a['base_positive'] and actual[1] is a['base_negative']
@pytest.mark.parametrize('rows',[None,[],[()],[[None]],[(Control(),None,0,0,1)]])
def test_none_empty_and_native_malformed_rows_with_zero_image_noop(loader,rows):
    a=consumer(controlnet_stack=rows)
    try:expected=('value',oracle(IDS[1],loader).apply_controlnet_stack(**a))
    except Exception as exc:expected=('error',type(exc),str(exc))
    try:actual=('value',asyncio.run(local(IDS[1],a)))
    except Exception as exc:actual=('error',type(exc),str(exc))
    assert actual[0]==expected[0]
    if expected[0]=='error':assert actual[1:]==expected[1:]
    else:paired_same(actual[1],expected[1])
@pytest.mark.parametrize('id',IDS)
def test_exact_schema_optional_defaults_and_permissions(id):
    row=LEDGER[id];c=NEW.NODE_CLASS_MAPPINGS[id];s=c.GET_SCHEMA()
    assert s.node_id==id and s.display_name==row['display_name'] and s.category==row['category'] and c.SDK_PERMISSIONS==('models',)
    inputs={k:(group,info) for group,values in row['source_inputs'].items() for k,info in values.items()}
    assert [i.id for i in s.inputs]==list(inputs)
    for i in s.inputs:
        group,info=inputs[i.id];assert i.optional==(group=='optional')
        if i.id in ('controlnet_1','controlnet_2','controlnet_3'):assert i.options==['None'] and i.remote.route=='/secure-nodes/models/controlnet'
        elif isinstance(info[0],list):assert i.options==info[0]
        else:assert i.io_type==info[0]
        for k,v in (info[1] if len(info)>1 else {}).items():assert i.as_dict()[k]==v
    assert [o.io_type for o in s.outputs]==row['return_types'] and [o.display_name for o in s.outputs]==row['return_names']
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
@pytest.mark.parametrize('changes',[{'controlnet_stack':[(Control(),None,0,0,1)]*257},{'controlnet_stack':[('../host',None,1,0,1)]},{'controlnet_stack':[(Control(),image(torch.float32),1,-.1,1)]},{'controlnet_stack':[(Control(),image(torch.float32),1,0,1.1)]},{'controlnet_stack':[(Control(),image(torch.float32),float('nan'),0,1)]}])
def test_closed_bounds_path_and_endpoints_do_not_silently_normalize(loader,changes):
    with pytest.raises((ValueError,TypeError)):asyncio.run(local(IDS[1],consumer(**changes)))
    assert not loader[0]
def test_two_fresh_guests_producer_consumer_outer_empty_tuples_models_deny_and_production(loader,monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        async def execute(id,a):
            c=NEW.NODE_CLASS_MAPPINGS[id];c.GET_SCHEMA()
            r=await execution._async_map_node_over_list(prompt_id='control-stack',unique_id='cn',obj=c,input_data_all={k:[v] for k,v in a.items()},func=c.FUNCTION,v3_data=None)
            r=await execution.resolve_map_node_over_list_results(r);return r[0].result
        try:
            for render in range(2):
                session=await GuestSession('ned-control-stack-'+str(render),guest_runtime_root=V2).start();caps={'value':('models',)}
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=caps['value'])
                _sdk.providers.register_execution_backend(Backend())
                try:
                    a=producer();expected=oracle(IDS[0],loader).controlnet_stacker(**a);out=await execute(IDS[0],a);stack_same(out,expected)
                    for empty in (None,[],()):
                        a=consumer(controlnet_stack=out[0])
                        if empty is not None:a['base_positive']=empty
                        expected=oracle(IDS[1],loader).apply_controlnet_stack(**a);paired_same(await execute(IDS[1],a),expected)
                    caps['value']=()
                    a=consumer();expected=oracle(IDS[1],loader).apply_controlnet_stack(**a);paired_same(await execute(IDS[1],a),expected) # Object-only pair requires no models grant/raw.
                    before=len(loader[0])
                    with pytest.raises(wire.WireError,match='models|capability|permission'):await execute(IDS[0],producer())
                    a=consumer(controlnet_stack=[('registered',image(torch.float32),1,.8,.2)])
                    with pytest.raises(wire.WireError,match='models|capability|permission'):await execute(IDS[1],a)
                    assert len(loader[0])==before;pids.append(session.last_guest_pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
            session=await GuestSession('ned-control-stack-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
            monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
            async def session_for(*a,**k):return session
            monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
            try:
                a=producer();stack_same(await execute(IDS[0],a),oracle(IDS[0],loader).controlnet_stacker(**a))
                a=consumer(base_positive=[],controlnet_stack=[('registered',image(torch.bfloat16),1,.8,.2)]);paired_same(await execute(IDS[1],a),oracle(IDS[1],loader).apply_controlnet_stack(**a))
            finally:await session.kill();await backend.shutdown()
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
