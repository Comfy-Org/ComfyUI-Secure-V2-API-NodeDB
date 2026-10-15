"""Literal source, ordered dynamic sockets, confined guests, caps and artifacts."""
import ast,asyncio,copy,hashlib,importlib.util,inspect,json,math,os,shutil,sys
from pathlib import Path
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution
import comfy.sd
from comfy.model_patcher import ModelPatcher
from comfy_api.latest import io,_io,_sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packpatch,packdb
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;DB=PACK.parents[3]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('ned_logicmath_pristine',PACK);NEW=load('ned_logicmath_owned',V2)
ORIGINAL={c.__name__:c for c in asyncio.run(OLD.LogicMathExtension().get_node_list())}
NODES=NEW.NODE_CLASS_MAPPINGS
GUARD=sys.modules[NEW.__name__+'._admission'];BOUND=sys.modules[NEW.__name__+'._boundary']
for cls in NODES.values():cls.GET_SCHEMA().validate()

DEFAULTS={
'MathAdd':{'operands':{'operand0':8,'operand1':2}},
'MathSubtract':{'operands':{'operand0':8,'operand1':2}},
'MathMultiply':{'operands':{'operand0':8,'operand1':2}},
'MathDivide':{'operands':{'operand0':8,'operand1':2},'handle_zero':True},
'MathPower':{'base':2,'exponent':3},'MathFloor':{'value':2.7},'MathCeil':{'value':2.2},
'MathRound':{'value':2.345,'decimals':2},'MathModulo':{'value_a':8,'value_b':3},
'MathAbs':{'value':-2},'MathSqrt':{'value':4},
'MathSin':{'angle':30,'unit':'Degrees'},'MathCos':{'angle':30,'unit':'Degrees'},'MathTan':{'angle':30,'unit':'Degrees'},
'MathMin':{'values':{'value0':8,'value1':2}},'MathMax':{'values':{'value0':8,'value1':2}},
'MathClamp':{'value':7,'min_value':0,'max_value':5},'MathNumberConvert':{'number_value':2.7},
'StringToNumber':{'string':'1.5'},'NumberToString':{'number':3.5},
'MathCompare':{'value_a':3,'value_b':2,'comparison':'Greater Than'},
'MathOperation':{'value_a':8,'value_b':2,'operation':'Add'},'MathAspectRatio':{'width':1920,'height':1080},
'LogicIF':{'if_condition':True,'when_true':'selected','when_false':'other'},
'LogicAND':{'inputs':{'input0':True,'input1':False}},'LogicOR':{'inputs':{'input0':True,'input1':False}},
'LogicNOT':{'input':True},'LogicXOR':{'inputs':{'input0':True,'input1':False}}}

async def converted(name,fields):
    refs=_sdk.InProcessRefResolver()
    with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
        out=NODES[name].execute(**fields)
        if inspect.isawaitable(out):out=await out
        return tuple([await refs.resolve(v) if isinstance(v,_sdk.Ref) else v for v in out.result])

def equivalent(a,b):
    assert type(a) is type(b)
    if type(a) in (list,tuple):
        assert len(a)==len(b)
        for x,y in zip(a,b):equivalent(x,y)
    elif type(a) is torch.Tensor:
        assert a.dtype==b.dtype;torch.testing.assert_close(a,b,rtol=0,atol=0,equal_nan=True)
    elif type(a) is np.ndarray:
        assert a.dtype==b.dtype;np.testing.assert_array_equal(a,b,strict=True)
    elif isinstance(a,(float,complex,np.number)):
        np.testing.assert_equal(a,b)
    else:assert a==b

def compare(name,fields):
    try:expected=ORIGINAL[name].execute(**fields).result
    except Exception as error:
        with pytest.raises(type(error)) as got:asyncio.run(converted(name,fields))
        assert str(got.value)==str(error)
    else:equivalent(asyncio.run(converted(name,fields)),expected)

def manifest():
    return {'format':FORMAT,'runtime':manifest_declaration(V2),'web_directory':None,
      'nodes':{name:{'module':cls.__module__.split('.')[-1],'class':name,'sdk_refs':cls.SDK_REFS,
      'permissions':list(cls.SDK_PERMISSIONS),'methods':{'validate_inputs':name=='MathDivide','fingerprint_inputs':False,'check_lazy_status':False},
      'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for name,cls in NODES.items()}}

@pytest.mark.parametrize('name',DEFAULTS)
def test_all28_exact_native_default_controls(name):compare(name,DEFAULTS[name])

def test_actual_pristine_export_order_full_schema_matchtype_autogrow():
    assert list(ORIGINAL)==list(NODES)==list(DEFAULTS)
    assert asyncio.run(NEW.LogicMathExtension().get_node_list())==list(NODES.values())
    for name in NODES:
        assert encode_schema(ORIGINAL[name].GET_SCHEMA())==encode_schema(NODES[name].GET_SCHEMA())
    assert not list(PACK.glob('*.js')) and not hasattr(NEW,'WEB_DIRECTORY')
    assert len(NODES)==28

@pytest.mark.parametrize('name',['MathAdd','MathSubtract','MathMultiply','MathDivide','MathMin','MathMax','LogicAND','LogicOR','LogicXOR'])
@pytest.mark.parametrize('count',[0,1,2,10])
def test_ordered_native_folds_empty_short_and10(name,count):
    field='operands' if name in ('MathAdd','MathSubtract','MathMultiply','MathDivide') else 'values' if name in ('MathMin','MathMax') else 'inputs'
    prefix={'operands':'operand','values':'value','inputs':'input'}[field]
    values={prefix+str(i):i+1 for i in reversed(range(count))}
    fields={field:values}
    if name=='MathDivide':fields['handle_zero']=False
    compare(name,fields)

@pytest.mark.parametrize('name',['MathFloor','MathCeil','MathAbs','MathSqrt'])
@pytest.mark.parametrize('value',[-4.,0.,2.5,float('nan'),float('inf'),float('-inf'),1+2j,np.float32(2.5),np.int64(-3)])
def test_unary_native_types_nonfinite_complex_and_errors(name,value):compare(name,{'value':value})

@pytest.mark.parametrize('name',['MathSin','MathCos','MathTan'])
@pytest.mark.parametrize('unit',['Degrees','Radians','source-direct-other'])
@pytest.mark.parametrize('angle',[-180.,0.,30.,float('nan'),float('inf')])
def test_trig_all_options_native_nonfinite(name,unit,angle):compare(name,dict(angle=angle,unit=unit))

@pytest.mark.parametrize('value',[-2.5,2.5,2.345,np.float32(2.345),float('inf'),float('nan'),1+2j])
@pytest.mark.parametrize('decimals',[0,2,10,-1])
def test_round_bankers_precision_native_errors(value,decimals):compare('MathRound',dict(value=value,decimals=decimals))

@pytest.mark.parametrize('a,b',[(-8,3),(8,0),(0,0),(8,-3),(float('nan'),2),(np.int64(8),np.int64(3)),(1+2j,2)])
def test_modulo_zero_negative_numpy_complex_errors(a,b):compare('MathModulo',dict(value_a=a,value_b=b))

@pytest.mark.parametrize('base,exponent',[(-1.,.5),(0,0),(0,-1),(2,-2),(float('nan'),2),(float('inf'),-1),(np.int64(2),np.int64(3))])
def test_power_native_complex_zero_negative_numpy(base,exponent):compare('MathPower',dict(base=base,exponent=exponent))

@pytest.mark.parametrize('text',['1.5','1e3','nan','inf','garbage','003','-0','+1_000','1.0e999','0xFF'])
def test_source_string_dot_branch_default_fallback(text):compare('StringToNumber',dict(string=text,default_value=-7.5))

@pytest.mark.parametrize('number',[True,0,-3,2.5,np.float32(2.5),1+2j,float('inf'),float('nan')])
@pytest.mark.parametrize('name',['NumberToString','MathNumberConvert'])
def test_conversion_type_and_string_native_errors(number,name):compare(name,{'number' if name=='NumberToString' else 'number_value':number})

@pytest.mark.parametrize('label',['Equal','Not Equal','Greater Than','Greater Than or Equal','Less Than','Less Than or Equal','unknown'])
@pytest.mark.parametrize('a,b',[(1,2),(2,2),(np.float32(2),np.float32(3)),(float('nan'),2),(1+2j,2)])
def test_all_comparisons_exact_source_labels(label,a,b):compare('MathCompare',dict(value_a=a,value_b=b,comparison=label))

@pytest.mark.parametrize('name,fields',[
('MathDivide',dict(operands={'operand0':8,'operand1':0},handle_zero=True)),
('MathDivide',dict(operands={'operand0':8,'operand1':0},handle_zero=False)),
('MathClamp',dict(value=5,min_value=8,max_value=1)),
('MathAspectRatio',dict(width=0,height=0)),('MathAspectRatio',dict(width=-1920,height=1080)),
('LogicXOR',dict(inputs={'input0':1,'input1':2,'input2':3}))])
def test_source_native_validation_and_direct_quirks(name,fields):compare(name,fields)

@pytest.mark.parametrize('op',['Add','Subtract','Multiply','Divide','unknown'])
@pytest.mark.parametrize('a,b',[(8,2),(8,0),(1+2j,2),('ab','cd'),([1,2],[3]),((1,2),(3,)),('xy',-2),(3,[1,2]),(np.int64(2),[1,2]),(np.float32(2),[1,2])])
def test_any_native_inert_closed_types_sequence_order_numpy_result(op,a,b):compare('MathOperation',dict(value_a=a,value_b=b,operation=op))

def test_guards_before_ops_integer_text_depth_and_fold_growth():
    for name,fields in [('MathPower',dict(base=2,exponent=4096)),('StringToNumber',dict(string='9'*2000)),('MathMultiply',dict(operands={'operand0':2**2047,'operand1':2**2047,'operand2':2}))]:
        with pytest.raises(ValueError,match='budget'):asyncio.run(converted(name,fields))
    for a,b in [('x',65537),([1],4096)]:
        with pytest.raises(ValueError,match='budget'):asyncio.run(converted('MathOperation',dict(value_a=a,value_b=b,operation='Multiply')))
    with pytest.raises(ValueError,match='operand'):asyncio.run(converted('MathAdd',dict(operands={str(i):1 for i in range(11)})))
    for shapes in (((4194304,),(4194303,)),((1025,1024),(1025,1024))):
        with pytest.raises(ValueError,match='ownership'):GUARD.tensor_plan(shapes)
    assert GUARD.tensor_plan(((3,2),(4,2)))['native_broadcast_error']
    assert GUARD.tensor_plan(((1024,1024),(1024,1024)))['projected_bytes']==128*1024*1024

def test_pre_raw_metadata_only_oversize_mismatch_sentinel(monkeypatch):
    async def run():
        refs=_sdk.InProcessRefResolver()
        left=_sdk.TensorRef._wrap(await refs.create('TENSOR',torch.empty(1)))
        right=_sdk.TensorRef._wrap(await refs.create('TENSOR',torch.empty(1)))
        shapes={left.id:[4194304],right.id:[4194303]};calls=[]
        async def describe(self,**kwargs):return {'shape':shapes[self.id]}
        async def raw(self):calls.append(self.id);raise AssertionError('raw before ownership')
        monkeypatch.setattr(_sdk.TensorRef,'describe',describe);monkeypatch.setattr(_sdk.TensorRef,'raw',raw)
        with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
            with pytest.raises(ValueError,match='input/snapshot'):await NODES['MathOperation'].execute(left,right,'Add')
        assert calls==[]
    asyncio.run(run())

def test_numpy_repetition_and_padded_conversion_before_native_operator(monkeypatch):
    calls=[]
    source=NODES['MathOperation'].execute.__func__.__wrapped__
    # This sentinel operates on the exact guard called by the wrapper: no
    # source NumPy/list operation runs for growth or padded text conversion.
    for a,b,op in [(np.int64(65537),[1,2],'Multiply'),([1,2],np.int64(65537),'Multiply'),(np.int64(2),['x'*64000]+['']*1000,'Add')]:
        with pytest.raises(ValueError,match='budget'):
            GUARD.project_tree(a,b,op);calls.append('source');source(None,a,b,op)
    assert calls==[]

def test_review_rectangular_array_list_broadcast_refuses_before_raw(monkeypatch):
    async def run():
        refs=_sdk.InProcessRefResolver()
        ref=_sdk.TensorRef._wrap(await refs.create('TENSOR',torch.empty(1)))
        async def describe(self,**kwargs):return {'shape':[4096,1]}
        async def raw(self):raise AssertionError('raw before true array/list broadcast budget')
        monkeypatch.setattr(_sdk.TensorRef,'describe',describe);monkeypatch.setattr(_sdk.TensorRef,'raw',raw)
        with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
            with pytest.raises(ValueError,match='budget'):await NODES['MathOperation'].execute(ref,list(range(4095)),'Add')
    asyncio.run(run())

@pytest.mark.parametrize('value',[np.float64(2),np.complex128(2)])
def test_review_numpy_noninteger_multiply_padded_conversion_before_work(value):
    with pytest.raises(ValueError,match='budget'):
        GUARD.project_tree(value,['a'*32768]+[0]*1023,'Multiply')
        raise AssertionError('native Multiply would run before padded conversion budget')

@pytest.mark.parametrize('op',['Add','Subtract','Multiply','Divide'])
@pytest.mark.parametrize('other',[[1,2,3],[[1,2,3]],[],[[],[]],[[1],[2,3]],['a',0]])
@pytest.mark.parametrize('reverse',[False,True])
def test_small_native_array_sequence_rectangles_empty_ragged_errors(op,other,reverse):
    array=np.arange(1,5,dtype=np.float64).reshape(4,1)
    a,b=(other,array) if reverse else (array,other)
    compare('MathOperation',dict(value_a=a,value_b=b,operation=op))

@pytest.mark.parametrize('value',[np.float32(2),np.float64(2),np.complex64(2),np.complex128(2)])
@pytest.mark.parametrize('other',[[1,2,3],['a',0]])
def test_small_native_numpy_float_complex_multiply_conversion(value,other):
    compare('MathOperation',dict(value_a=value,value_b=other,operation='Multiply'))

def test_rectangular_projection_true_shape_and_plain_lists_not_rectangularized():
    assert GUARD.sequence_projection([1,2,3])['shape']==[3]
    assert GUARD.sequence_projection([[1],[2]])['shape']==[2,1]
    assert GUARD.sequence_projection([[],[]])['shape']==[2,0]
    assert GUARD.sequence_projection([[1],[2,3]])['native_conversion_error']
    actual=asyncio.run(converted('MathOperation',dict(value_a=['a'*32768]+[0]*1023,value_b=[],operation='Add')))
    assert actual[0]==['a'*32768]+[0]*1023

def test_numpy_object_sequence_native_control_and_before_raw_refusal(monkeypatch):
    # Tiny literal source control: this is an object buffer, not a 16B dense
    # numeric result. Its source behavior is retained outside our admission.
    values=[2**100,2**101]
    native=ORIGINAL['MathOperation'].execute(np.ones((2,1)),values,'Add').result[0]
    assert native.dtype==object and native.shape==(2,2)
    with pytest.raises(TypeError,match='object'):
        GUARD.project_tree(np.float64(2),values,'Add')
    async def run():
        refs=_sdk.InProcessRefResolver()
        ref=_sdk.TensorRef._wrap(await refs.create('TENSOR',np.ones((2,1))))
        async def describe(self,**kwargs):return {'shape':[2,1]}
        async def raw(self):raise AssertionError('raw before object conversion refusal')
        monkeypatch.setattr(_sdk.TensorRef,'describe',describe);monkeypatch.setattr(_sdk.TensorRef,'raw',raw)
        with _sdk.bind_runtime(refs,None,_sdk.InProcessOps()):
            with pytest.raises(TypeError,match='object'):
                await NODES['MathOperation'].execute(ref,values,'Add')
    asyncio.run(run())

def test_numpy_large_scalar_native_overflow_not_object_promotion():
    compare('MathOperation',dict(value_a=np.ones((2,1),dtype=np.int64),value_b=2**100,operation='Add'))

def test_declared_source_validate_zero_and_input_bound():
    for flag in (False,True):
        values={'operand0':8,'operand1':0}
        assert NODES['MathDivide'].validate_inputs(values,flag)==ORIGINAL['MathDivide'].validate_inputs(values,flag)
    with pytest.raises(ValueError,match='operand'):NODES['MathDivide'].validate_inputs({str(i):1 for i in range(11)},False)

def test_literal_original_algorithm_ast_except_three_before_fold_guards():
    for filename in ('nodes_math.py','nodes_logic.py'):
        old=ast.parse((PACK/filename).read_text());new=ast.parse((V2/filename).read_text())
        oldclasses={n.name:n for n in old.body if isinstance(n,ast.ClassDef)}
        newclasses={n.name:n for n in new.body if isinstance(n,ast.ClassDef)}
        for name,n in newclasses.items():
            n=copy.deepcopy(n)
            for member in n.body:
                if isinstance(member,ast.FunctionDef) and member.name=='execute':
                    for loop in ast.walk(member):
                        if isinstance(loop,ast.For):loop.body=[x for x in loop.body if not (isinstance(x,ast.Expr) and isinstance(x.value,ast.Call) and isinstance(x.value.func,ast.Attribute) and x.value.func.attr=='fold_step')]
            assert ast.dump(n,include_attributes=False)==ast.dump(oldclasses[name],include_attributes=False)

async def outer(module,name,fields):
    cls=module.NODE_CLASS_MAPPINGS[name]
    mapped=await execution._async_map_node_over_list('ned-logicmath','1',cls,{k:[v] for k,v in fields.items()},cls.FUNCTION)
    return (await execution.resolve_map_node_over_list_results(mapped))[0].result

def test_required_fresh_guests_outer_all28_complex_numpy_chain_caps_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    async def run():
        prior=_sdk.providers.execution_backend;pids=set()
        try:
            for generation in range(2):
                root=tmp_path/str(generation);shutil.copytree(V2,root);module=load('ned_logicmath_fresh_'+str(generation),root)
                for cls in module.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
                session=await GuestSession('ned-logicmath-'+str(generation),guest_runtime_root=root).start()
                caps=()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=caps,tenant='ned-logicmath-user')
                _sdk.providers.register_execution_backend(Backend())
                try:
                    assert session.sandbox_kind=='seatbelt'
                    for name,fields in DEFAULTS.items():equivalent(await outer(module,name,fields),ORIGINAL[name].execute(**fields).result)
                    for name in ('MathAdd','MathSubtract','MathMultiply','MathDivide','MathMin','MathMax','LogicAND','LogicOR','LogicXOR'):
                        field='operands' if name in ('MathAdd','MathSubtract','MathMultiply','MathDivide') else 'values' if name in ('MathMin','MathMax') else 'inputs'
                        prefix={'operands':'operand','values':'value','inputs':'input'}[field]
                        flat={field+'.'+prefix+str(i):i+1 for i in reversed(range(10))}
                        if name=='MathDivide':flat['handle_zero']=False
                        core_inputs,missing,v3=execution.get_input_data(flat,ORIGINAL[name],'dynamic10')
                        assert not missing
                        nested=_io.build_nested_inputs(flat,v3)
                        assert len(nested[field])==10
                        cls=module.NODE_CLASS_MAPPINGS[name]
                        mapped=await execution._async_map_node_over_list('ned-logicmath','dynamic10',cls,core_inputs,cls.FUNCTION,v3_data=v3)
                        actual=(await execution.resolve_map_node_over_list_results(mapped))[0].result
                        equivalent(actual,ORIGINAL[name].execute(**nested).result)
                    value=(await outer(module,'MathPower',dict(base=-1.,exponent=.5)))[0]
                    assert type(value) is complex and value==(-1.)**.5
                    equivalent(await outer(module,'NumberToString',dict(number=value)),ORIGINAL['NumberToString'].execute(value).result)
                    with pytest.raises(Exception,match='real number|complex'):await outer(module,'MathFloor',dict(value=value))
                    repeated=(await outer(module,'MathOperation',dict(value_a=np.int64(2),value_b=[1,2],operation='Multiply')))[0]
                    equivalent(repeated,np.int64(2)*[1,2])
                    caps=('raw','inspect')
                    array=(await outer(module,'MathOperation',dict(value_a=np.int64(2),value_b=[1,2],operation='Add')))[0]
                    assert type(array) is np.ndarray and array.dtype==np.dtype('int64')
                    caps=('raw','inspect')
                    equivalent((await outer(module,'MathOperation',dict(value_a=array,value_b=1,operation='Add')))[0],array+1)
                    rectangle=np.arange(1,5,dtype=np.float64).reshape(4,1)
                    for op in ('Add','Subtract','Multiply','Divide'):
                        equivalent((await outer(module,'MathOperation',dict(value_a=rectangle,value_b=[1,2,3],operation=op)))[0],ORIGINAL['MathOperation'].execute(rectangle,[1,2,3],op).result[0])
                    caps=('inspect',)
                    with pytest.raises(Exception,match='budget'):await outer(module,'MathOperation',dict(value_a=np.zeros((4096,1),dtype=np.float64),value_b=list(range(4095)),operation='Add'))
                    with pytest.raises(Exception,match='object sequence'):
                        await outer(module,'MathOperation',dict(value_a=np.ones((2,1)),value_b=[2**100,2**101],operation='Add'))
                    caps=()
                    with pytest.raises(Exception,match='object sequence'):
                        await outer(module,'MathOperation',dict(value_a=np.float64(2),value_b=[2**100,2**101],operation='Add'))
                    for value in (np.float64(2),np.complex128(2)):
                        with pytest.raises(Exception,match='budget'):await outer(module,'MathOperation',dict(value_a=value,value_b=['a'*32768]+[0]*1023,operation='Multiply'))
                    model=ModelPatcher(torch.nn.Linear(1,1),load_device=torch.device('cpu'),offload_device=torch.device('cpu'))
                    clip=object.__new__(comfy.sd.CLIP);opaque=object();tensor=torch.arange(6).reshape(2,3)
                    caps=()
                    for selected in (model,clip,opaque,tensor,{'model':model,'rows':[(clip,opaque)]}):
                        out=await outer(module,'LogicIF',dict(if_condition=True,when_true=selected,when_false=opaque))
                        if type(selected) is dict:
                            assert out[0]['model'] is model and out[0]['rows'][0][0] is clip and out[0]['rows'][0][1] is opaque
                        else:assert out[0] is selected
                    assert (await outer(module,'LogicIF',dict(if_condition=False,when_true=model)))[0] is None
                    for dtype in (torch.float32,torch.float16,torch.bfloat16,torch.int64,torch.complex64):
                        a=torch.arange(6,dtype=torch.float32).reshape(2,3).to(dtype);b=torch.ones(1,3,dtype=dtype)
                        caps=('raw','inspect')
                        for op in ('Add','Subtract','Multiply','Divide'):
                            expected=ORIGINAL['MathOperation'].execute(a,b,op).result[0]
                            equivalent((await outer(module,'MathOperation',dict(value_a=a,value_b=b,operation=op)))[0],expected)
                    for missing in ('raw','inspect'):
                        caps=tuple(c for c in ('raw','inspect') if c!=missing)
                        with pytest.raises(Exception,match=missing+'.*not granted'):await outer(module,'MathOperation',dict(value_a=tensor,value_b=1,operation='Add'))
                    caps=('raw','inspect')
                    with pytest.raises(Exception,match='opaque arithmetic'):await outer(module,'MathOperation',dict(value_a=model,value_b=1,operation='Add'))
                    with pytest.raises(Exception,match='budget'):await outer(module,'MathPower',dict(base=2,exponent=4096))
                    for a,b in [(np.int64(65537),[1,2]),([1,2],np.int64(65537))]:
                        with pytest.raises(Exception,match='budget'):await outer(module,'MathOperation',dict(value_a=a,value_b=b,operation='Multiply'))
                    with pytest.raises(Exception,match='size|broadcast|dimension'):await outer(module,'MathOperation',dict(value_a=torch.zeros(3,2),value_b=torch.zeros(4,2),operation='Add'))
                    caps=('inspect',)
                    # No physical large operands allocated: actual host-owned
                    # meta shapes describe normally. Missing raw grants prove
                    # refusal occurs before any materialization attempt.
                    for shapes in (((4194304,),(4194303,)),((1,2048,1),(1,1,2048))):
                        a=torch.empty(shapes[0],device='meta');b=torch.empty(shapes[1],device='meta')
                        with pytest.raises(Exception,match='ownership.*budget'):await outer(module,'MathOperation',dict(value_a=a,value_b=b,operation='Add'))
                    caps=('raw','inspect')
                    equivalent(await outer(module,'MathAdd',DEFAULTS['MathAdd']),(10,))
                    pids.add(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(pids)==2 and os.getpid() not in pids
        print('Required fresh LogicMath PIDs',sorted(pids))
    asyncio.run(run())

def test_manifest_resources_stubs_actual_proxy_and_no_cache():
    assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
    assert (V2/'LICENSE').read_bytes()==(PACK/'LICENSE').read_bytes()
    assert (V2/'assets/math-icon.png').read_bytes()==(PACK/'assets/math-icon.png').read_bytes()
    assert 'MIT License' in (PACK/'LICENSE').read_text()
    evidence=json.loads((V2/'conversion-evidence.json').read_text())
    for name,expected in evidence['stubs'].items():
        assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==expected['sha256']
        assert (V2/name).read_bytes()==Path(expected['origin']).read_bytes()
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
    loaded=packdb.load_pack(PACK.parent,mount_name='custom_nodes.ned_logicmath_proxy')
    assert set(loaded.node_mappings)==set(NODES) and not loaded.routes and loaded.web_directory is None

def test_current_catalogue_normalized_url_pin_and_all28_ids_absent():
    catalog=Path('/Users/ben/comfy/ComfyUI_secure_nodes/pack-db/packs/packs.json')
    rows=json.loads(catalog.read_text());url='https://github.com/silveroxides/ComfyUI-LogicMath'
    norm=lambda x:x.lower().rstrip('/').removesuffix('.git')
    assert not [key for key,row in rows.items() if norm(row['upstream'])==norm(url) or row['commit']=='102d49201d488084a0978fc39dd5742a09475a88']
    for path in catalog.parent.rglob('secure-nodes.json'):
        assert not set(NODES).intersection(json.loads(path.read_text()).get('nodes',{})),str(path)

def test_required_independent_dynamic10_ref_identity_tensor_bounds_and_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    async def run():
        prior=_sdk.providers.execution_backend;pids=set()
        try:
            for generation in range(2):
                root=tmp_path/str(generation);shutil.copytree(V2,root);module=load('ned_logicmath_independent_'+str(generation),root)
                for cls in module.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
                session=await GuestSession('ned-logicmath-independent-'+str(generation),guest_runtime_root=root).start();caps=()
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=caps,tenant='ned-logicmath-user')
                _sdk.providers.register_execution_backend(Backend())
                try:
                    assert session.sandbox_kind=='seatbelt'
                    for name in ('MathAdd','MathSubtract','MathMultiply','MathDivide','MathMin','MathMax','LogicAND','LogicOR','LogicXOR'):
                        field='operands' if name in ('MathAdd','MathSubtract','MathMultiply','MathDivide') else 'values' if name in ('MathMin','MathMax') else 'inputs'
                        prefix={'operands':'operand','values':'value','inputs':'input'}[field]
                        flat={field+'.'+prefix+str(i):i+1 for i in reversed(range(10))}
                        if name=='MathDivide':flat['handle_zero']=False
                        core_inputs,missing,v3=execution.get_input_data(flat,ORIGINAL[name],'dynamic10')
                        assert not missing
                        expected=ORIGINAL[name].execute(**_io.build_nested_inputs(flat,v3)).result
                        cls=module.NODE_CLASS_MAPPINGS[name]
                        mapped=await execution._async_map_node_over_list('ned-logicmath','dynamic10',cls,core_inputs,cls.FUNCTION,v3_data=v3)
                        equivalent((await execution.resolve_map_node_over_list_results(mapped))[0].result,expected)
                    model=ModelPatcher(torch.nn.Linear(1,1),load_device=torch.device('cpu'),offload_device=torch.device('cpu'))
                    clip=object.__new__(comfy.sd.CLIP);opaque=object();tensor=torch.arange(6).reshape(2,3)
                    for selected in (model,clip,opaque,tensor):
                        assert (await outer(module,'LogicIF',dict(if_condition=False,when_true=opaque,when_false=selected)))[0] is selected
                    for dtype in (torch.float32,torch.float16,torch.bfloat16,torch.int64,torch.complex64):
                        a=torch.arange(6,dtype=torch.float32).reshape(2,3).to(dtype);b=torch.ones(1,3,dtype=dtype);caps=('raw','inspect')
                        for op in ('Add','Subtract','Multiply','Divide'):
                            equivalent((await outer(module,'MathOperation',dict(value_a=a,value_b=b,operation=op)))[0],ORIGINAL['MathOperation'].execute(a,b,op).result[0])
                    caps=('inspect',)
                    for shapes in (((4194304,),(4194303,)),((1,2048,1),(1,1,2048))):
                        with pytest.raises(Exception,match='ownership.*budget'):await outer(module,'MathOperation',dict(value_a=torch.empty(shapes[0],device='meta'),value_b=torch.empty(shapes[1],device='meta'),operation='Add'))
                    for missing in ('inspect','raw'):
                        caps=tuple(x for x in ('raw','inspect') if x!=missing)
                        with pytest.raises(Exception,match=missing+'.*not granted'):await outer(module,'MathOperation',dict(value_a=tensor,value_b=1,operation='Add'))
                    caps=('raw','inspect')
                    with pytest.raises(Exception,match='size|dimension|broadcast'):await outer(module,'MathOperation',dict(value_a=torch.zeros(3,2),value_b=torch.zeros(4,2),operation='Add'))
                    with pytest.raises(Exception,match='budget'):await outer(module,'MathOperation',dict(value_a=np.int64(65537),value_b=[1,2],operation='Multiply'))
                    equivalent(await outer(module,'MathAdd',DEFAULTS['MathAdd']),(10,))
                    pids.add(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(prior)
        assert len(pids)==2 and os.getpid() not in pids
        print('Independent required LogicMath PIDs',sorted(pids))
    asyncio.run(run())

def test_stored_pair_zip_two_roundtrips_modes_and_wrong_preimage(tmp_path):
    pair=DB/'patches/comfyui-logicmath/x102d492/comfyui-logicmath-x102d492'
    manifest,diff=packpatch.generate(PACK.parent)
    assert json.loads(pair.with_suffix('.json').read_text())==manifest
    assert pair.with_suffix('.diff').read_text()==diff
    bundle=packpatch.bundle(manifest,diff);assert pair.with_suffix('.zip').read_bytes()==bundle
    for n in range(2):
        fresh=tmp_path/str(n)/'comfyui-logicmath/x102d492';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if n:packpatch.apply_bundle(fresh,bundle)
        else:packpatch.apply(fresh,manifest,diff)
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
        for p in V2.rglob('*'):
            if p.is_file():assert (fresh/PACK.name/'v2'/p.relative_to(V2)).stat().st_mode&0o777==p.stat().st_mode&0o777
    wrong=tmp_path/'wrong/comfyui-logicmath/x102d492';wrong.mkdir(parents=True)
    shutil.copytree(PACK,wrong/PACK.name,ignore=shutil.ignore_patterns('v2'))
    target=wrong/PACK.name/'README.md';target.write_bytes(target.read_bytes()+b'wrong')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(wrong,manifest,diff)
    assert not (wrong/PACK.name/'v2').exists()
