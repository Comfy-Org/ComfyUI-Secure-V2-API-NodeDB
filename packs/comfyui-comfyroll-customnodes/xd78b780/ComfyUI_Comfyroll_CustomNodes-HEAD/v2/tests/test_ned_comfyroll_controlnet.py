"""Pinned ControlNet protocol differentials and fresh opaque-guest boundaries; no trained weights."""
import ast,asyncio,copy,importlib.util,inspect,os,sys,types
from pathlib import Path
import pytest,torch
sys.dont_write_bytecode=True;sys.argv=['ned-cr-controlnet','--cpu']
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
spec=importlib.util.spec_from_file_location('ned_cr_cn',V2/'__init__.py',submodule_search_locations=[str(V2)])
NEW=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NEW;spec.loader.exec_module(NEW)
def original(file,name):
    node=next(n for n in ast.parse((PACK/'nodes'/file).read_text()).body if isinstance(n,ast.ClassDef) and n.name==name)
    ns={'icons':NEW.secure_controlnet.icons};exec(compile(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]),str(PACK/'nodes'/file),'exec'),ns)
    return ns[name]
OLD=original('nodes_controlnet.py','CR_ApplyControlNet')
OLD_SWITCH=original('nodes_utils_logic.py','CR_ControlNetInputSwitch')
class Control:
    """Only recording canonical control protocol; no inference."""
    def __init__(self,records=None):self.records=[] if records is None else records;self.calls=[]
    def copy(self):
        result=Control(self.records);self.records.append(result);return result
    def get_control(self,*a,**k):raise AssertionError('No trained inference in fixture')
    def set_extra_arg(self,*a,**k):raise AssertionError('No extra-argument use allowed')
    def set_cond_hint(self,*args,**kw):
        assert len(args)==2 and not kw
        self.hint,self.strength=args;self.calls.append('hint');return self
    def set_previous_controlnet(self,previous):self.previous=previous;self.calls.append('previous');return self
def conditioning(dtype):
    tensor=torch.arange(8,dtype=dtype).reshape(1,2,4);previous=Control()
    return [[tensor,meta] for meta in ({'tag':'absent','nested':{'kept':7}},{'control':None},{'control':previous,'control_apply_to_uncond':True},{'control':previous,'control_apply_to_uncond':False},{'control':previous,'control_apply_to_uncond':'preserved'},{'control_apply_to_uncond':None})]
def image(dtype):return torch.arange(210,dtype=dtype).reshape(2,5,7,3)
async def local(cls,args):
    refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,args)
    with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
        r=cls.execute(**wrapped)
        if inspect.isawaitable(r):r=await r
    out=[]
    for x in r.result:
        out.append(await refs.resolve(x) if isinstance(x,_sdk.Ref) else x)
    return tuple(out)
def same(actual,expected,before,control,active):
    assert actual[1]==expected[1]
    if not active:
        assert actual[0] is before and not control.records;return
    assert len(actual[0])==len(expected[0])==len(before)
    assert len(control.records)==len(before) and len({id(x) for x in control.records})==len(before)
    for got,want,prior in zip(actual[0],expected[0],before):
        assert got[0] is want[0] is prior[0]
        assert got[1] is not prior[1] and set(got[1])==set(want[1])
        for key in want[1]:
            if key!='control':assert got[1][key] is want[1][key]
        gc,wc=got[1]['control'],want[1]['control']
        assert gc.calls==wc.calls and gc.strength==wc.strength
        assert torch.equal(gc.hint,wc.hint) and gc.hint.dtype==wc.hint.dtype
        if 'control' in prior[1]:assert gc.previous is wc.previous is prior[1]['control']
        else:assert not hasattr(gc,'previous')
@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.float16,torch.bfloat16])
@pytest.mark.parametrize('switch',['On','Off','unknown'])
@pytest.mark.parametrize('strength',[0,.7,10])
def test_exact_pinned_copy_hint_previous_and_uncond_metadata(dtype,switch,strength):
    before=conditioning(dtype);saved=[dict(row[1]) for row in before];cn=Control();args=dict(conditioning=before,control_net=cn,image=image(dtype),switch=switch,strength=strength)
    expected=OLD().apply_controlnet(**dict(args,control_net=Control()))
    actual=asyncio.run(local(NEW.secure_controlnet.CR_ApplyControlNet,args))
    same(actual,expected,before,cn,switch!='Off' and strength!=0)
    assert [row[1] for row in before]==saved
@pytest.mark.parametrize('value',[[],()])
def test_registered_empty_conditioning_admission(value):
    args=dict(conditioning=value,control_net=Control(),image=image(torch.float32),switch='On',strength=.7)
    actual=asyncio.run(local(NEW.secure_controlnet.CR_ApplyControlNet,args))
    assert actual[0]==OLD().apply_controlnet(**args)[0]==[] and not args['control_net'].records
@pytest.mark.parametrize('value',[[],()])
@pytest.mark.parametrize('switch,strength',[('Off',1),('On',0)])
def test_empty_noop_preserves_original_container(value,switch,strength):
    args=dict(conditioning=value,control_net=Control(),image=None,switch=switch,strength=strength)
    out=asyncio.run(local(NEW.secure_controlnet.CR_ApplyControlNet,args))
    assert out[0] is value and not args['control_net'].records
@pytest.mark.parametrize('selection',[1,2,0,3,True,1.0,'1',None])
@pytest.mark.parametrize('missing',[False,True])
def test_switch_exact_identity_none_routing_and_direct_selection(selection,missing):
    a,b=(None,None) if missing else (Control(),Control())
    expected=OLD_SWITCH().switch(selection,a,b)
    actual=asyncio.run(local(NEW.secure_controlnet.CR_ControlNetInputSwitch,dict(Input=selection,control_net1=a,control_net2=b)))
    assert actual[0] is expected[0] and actual[1]==expected[1]
def test_exact_schema_and_required_first_duplicate_normalization():
    for old,new in ((OLD,NEW.secure_controlnet.CR_ApplyControlNet),(OLD_SWITCH,NEW.secure_controlnet.CR_ControlNetInputSwitch)):
        schema=new.GET_SCHEMA();inputs=old.INPUT_TYPES()['required']
        assert [i.id for i in schema.inputs]==list(inputs)
        assert [o.io_type for o in schema.outputs]==list(old.RETURN_TYPES)
        assert [o.display_name for o in schema.outputs]==list(old.RETURN_NAMES)
        assert schema.category==old.CATEGORY and new.SDK_PERMISSIONS==() and new.SDK_REFS
        for i in schema.inputs:
            src=inputs[i.id];assert not i.optional
            if isinstance(src[0],list):assert i.as_dict()['options']==src[0]
            else:assert i.io_type==src[0]
            for k,v in (src[1] if len(src)>1 else {}).items():assert i.as_dict()[k]==v
    assert set(OLD_SWITCH.INPUT_TYPES()['optional'])=={'control_net1','control_net2'}
    assert len(NEW.secure_controlnet.CR_ControlNetInputSwitch.GET_SCHEMA().inputs)==3
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
def test_actual_two_fresh_zero_authority_guests_outer_and_ref_identity():
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for render in range(2):
                session=await GuestSession('ned-cr-cn-'+str(render),guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                async def execute(cls,args):
                    cls.GET_SCHEMA()
                    r=await execution._async_map_node_over_list(prompt_id='cr-cn',unique_id='cn',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                    return r[0].result
                try:
                    for dtype in (torch.float32,torch.float16,torch.bfloat16):
                        before=conditioning(dtype);cn=Control();args=dict(conditioning=before,control_net=cn,image=image(dtype),switch='On',strength=.7)
                        expected=OLD().apply_controlnet(**dict(args,control_net=Control()))
                        same(await execute(NEW.secure_controlnet.CR_ApplyControlNet,args),expected,before,cn,True)
                        args['switch']='Off';assert (await execute(NEW.secure_controlnet.CR_ApplyControlNet,args))[0] is before
                    cn=Control();args=dict(conditioning=[],control_net=cn,image=image(torch.float32),switch='On',strength=1)
                    assert (await execute(NEW.secure_controlnet.CR_ApplyControlNet,args))[0]==[] and not cn.records
                    for selection in (1,2,0):
                        a,b=Control(),Control()
                        result=await execute(NEW.secure_controlnet.CR_ControlNetInputSwitch,dict(Input=selection,control_net1=a,control_net2=b))
                        assert result[0] is (a if selection==1 else b)
                    args=dict(conditioning=conditioning(torch.float32),control_net=Control(),image=image(torch.float32),switch='On',strength=float('nan'))
                    with pytest.raises(wire.WireError,match='finite'):await execute(NEW.secure_controlnet.CR_ApplyControlNet,args)
                    assert not args['control_net'].records;pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert pids[0]!=pids[1] and all(pid!=os.getpid() for pid in pids)
    asyncio.run(run())

@pytest.mark.parametrize('strength',[float('nan'),float('inf'),-10.01,10.01,'1'])
def test_public_strength_bound_refusal_before_control_copy(strength):
    cn=Control();values=dict(conditioning=conditioning(torch.float32),control_net=cn,image=image(torch.float32),switch='On',strength=strength)
    with pytest.raises((TypeError,ValueError)):
        asyncio.run(local(NEW.secure_controlnet.CR_ApplyControlNet,values))
    assert not cn.records
def test_source_malformed_empty_image_difference_is_explicit_not_claimed():
    values=dict(conditioning=[],control_net=Control(),image=torch.zeros(1),switch='On',strength=1)
    with pytest.raises(IndexError):OLD().apply_controlnet(**values)
    # Approved branch is only fidelity-claimed for normal typed BHWC; no raw validation added.
    result=asyncio.run(local(NEW.secure_controlnet.CR_ApplyControlNet,values))
    assert result[0]==[] and not values['control_net'].records

def test_production_outer_single_and_switch_zero_authority(monkeypatch):
    import execution
    from comfy_secure_nodes.execution import CloudExecutionBackend
    async def run():
        previous=_sdk.providers.execution_backend;session=await GuestSession('ned-cr-cn-production',guest_runtime_root=V2).start();backend=CloudExecutionBackend()
        monkeypatch.setattr(backend,'_is_sandbox',lambda plan:True)
        async def session_for(*a,**k):return session
        monkeypatch.setattr(backend.guests,'session_for',session_for);_sdk.providers.register_execution_backend(backend)
        try:
            for cls,args in ((NEW.secure_controlnet.CR_ApplyControlNet,dict(conditioning=conditioning(torch.bfloat16),control_net=Control(),image=image(torch.bfloat16),switch='On',strength=1)),(NEW.secure_controlnet.CR_ControlNetInputSwitch,dict(Input=2,control_net1=Control(),control_net2=Control()))):
                cls.GET_SCHEMA()
                r=await execution._async_map_node_over_list(prompt_id='cn-production',unique_id='cn',obj=cls,input_data_all={k:[v] for k,v in args.items()},func=cls.FUNCTION,v3_data=None)
                r=await execution.resolve_map_node_over_list_results(r)
                if cls is NEW.secure_controlnet.CR_ApplyControlNet:
                    expected=OLD().apply_controlnet(**dict(args,control_net=Control()));same(r[0].result,expected,args['conditioning'],args['control_net'],True)
                else:assert r[0].result[0] is args['control_net2']
            assert session.last_guest_pid not in (None,os.getpid())
        finally:await session.kill();await backend.shutdown();_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
