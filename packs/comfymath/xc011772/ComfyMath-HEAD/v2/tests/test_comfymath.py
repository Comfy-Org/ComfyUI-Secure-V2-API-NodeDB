"""Pinned-source differential, actual public outer guests, and artifact gates."""
import ast
import asyncio
from dataclasses import replace
import hashlib
import importlib.util
import io as bytesio
import json
import math
import os
from pathlib import Path
import shutil
import sys
import zipfile

sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1]
PACK=V2.parent
SNAPSHOT=PACK.parent
CORPUS=PACK.parents[3]
CORE='/Users/ben/comfy/ComfyUI-secure-nodes'
BACKEND='/Users/ben/comfy/ComfyUI_secure_nodes/backend'
HOST_VENV='/Users/ben/comfy/ComfyUI/.venv'
sys.path[:0]=[CORE,BACKEND]
os.environ.setdefault('COMFY_CORE_ROOT',CORE)
import numpy as np
import pytest
import torch
from comfy_api.latest import io, _sdk
from comfy_secure_nodes import packdb, packpatch, packruntime
from comfy_secure_nodes.packmanifest import encode_schema
from comfy_secure_nodes.transport import wire
from comfy_secure_nodes.transport.host import GuestSession

def load(root):
    name='_jack_math_'+str(root).replace('/','_').replace('-','_')
    if name in sys.modules:return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod

def equivalent(a,b):
    assert type(a) is type(b),(type(a),type(b),repr(a),repr(b))
    if type(a) in (tuple,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):equivalent(x,y)
    elif isinstance(a,(float,np.floating)) and math.isnan(a):assert math.isnan(b)
    elif isinstance(a,(complex,np.complexfloating)):
        assert a.real==b.real and a.imag==b.imag
    else:assert a==b

def kwargs(cls):
    args={}
    for name,spec in cls.INPUT_TYPES()['required'].items():
        kind=spec[0]
        if isinstance(kind,list):args[name]=kind[0]
        elif kind=='IMAGE':args[name]=torch.zeros(1,4,6,3)
        elif kind.startswith('VEC'):args[name]=tuple(float(i+1+(name=='b')) for i in range(int(kind[-1])))
        elif kind=='BOOLEAN':args[name]=(name=='a')
        elif kind=='INT':args[name]=3 if name=='a' else 2
        else:args[name]=.25 if name=='a' else .5
    return args

def cases():
    old=load(PACK)
    rows=[]
    for node_id,cls in old.NODE_CLASS_MAPPINGS.items():
        base=kwargs(cls);schema=cls.INPUT_TYPES()['required']
        name=next((x for x in ('op','resolution') if x in schema),None)
        for value in schema[name][0] if name else [None]:
            fields=dict(base)
            if name:fields[name]=value
            rows.append((node_id,fields))
    return rows

TARGETED=[
 ('CM_IntUnaryOperation',dict(op='Factorial',a=-1)),
 ('CM_IntBinaryOperation',dict(op='Div',a=1,b=0)),
 ('CM_IntBinaryOperation',dict(op='Shl',a=1,b=-1)),
 ('CM_IntBinaryOperation',dict(op='Pow',a=2,b=-1)),
 ('CM_IntBinaryOperation',dict(op='Nand',a=3,b=2)),
 ('CM_IntBinaryOperation',dict(op='Nor',a=3,b=2)),
 ('CM_IntBinaryOperation',dict(op='Xor',a=True,b=False)),
 ('CM_FloatBinaryOperation',dict(op='Pow',a=-1.,b=.5)),
 ('CM_NumberBinaryOperation',dict(op='Pow',a=-1.,b=.5)),
 ('CM_FloatUnaryOperation',dict(op='Round',a=2.5)),
 ('CM_FloatUnaryOperation',dict(op='Sqrt',a=-1.)),
 ('CM_FloatUnaryCondition',dict(op='IsNaN',a=float('nan'))),
 ('CM_FloatUnaryCondition',dict(op='IsInfinite',a=float('inf'))),
 ('CM_SDXLResolution',dict(resolution='1x0')),
 ('CM_SDXLResolution',dict(resolution='invalid')),
 ('CM_SDXLResolution',dict(resolution='1x2x3')),
 ('CM_FloatBinaryOperation',dict(op='NotAnOperation',a=1.,b=2.)),
]
for a in (False,True):
    for b in (False,True):
        for op in ('Nor','Xor','Nand','And','Xnor','Or','Eq','Neq'):
            TARGETED.append(('CM_BoolBinaryOperation',dict(op=op,a=a,b=b)))
for dim in (2,3,4):
    TARGETED += [
      (f'CM_Vec{dim}UnaryOperation',dict(op='Normalize',a=(0.,)*dim)),
      (f'CM_Vec{dim}UnaryOperation',dict(op='Neg',a=())),
      (f'CM_Vec{dim}BinaryOperation',dict(op='Add',a=(1.,),b=(2.,)*dim)),
      (f'CM_Vec{dim}BinaryOperation',dict(op='Cross',a=(1.,)*dim,b=(2.,)*dim)),
      (f'CM_Vec{dim}BinaryOperation',dict(op='Add',a=(1.,2.),b=(1.,2.,3.))),
      (f'CM_Vec{dim}UnaryOperation',dict(op='Neg',a=(1j,)*dim)),
      (f'CM_BreakoutVec{dim}',dict(a=(1.,))),
    ]

def native(node_id,fields):
    cls=load(PACK).NODE_CLASS_MAPPINGS[node_id]
    with np.errstate(all='ignore'):
        return getattr(cls(),cls.FUNCTION)(**fields)

class SpatialMetadata:
    def __init__(self,image):self.image=image
    async def spatial_shape(self):return tuple(self.image.shape[1:3])

def test_exact_census_schema_options_defaults_names_and_resource_provenance():
    old=load(PACK);new=load(V2)
    assert list(old.NODE_CLASS_MAPPINGS)==list(new.NODE_CLASS_MAPPINGS)
    assert len(new.NODE_CLASS_MAPPINGS)==53
    assert np.__version__=='2.4.6'
    for node_id,cls in old.NODE_CLASS_MAPPINGS.items():
        v=new.NODE_CLASS_MAPPINGS[node_id];schema=v.GET_SCHEMA()
        assert schema.node_id==node_id and schema.category==cls.CATEGORY
        assert schema.display_name==old.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert v.SDK_REFS is True and v.SDK_PERMISSIONS==()
        assert [x.id for x in schema.inputs]==list(cls.INPUT_TYPES()['required'])
        for inp,spec in zip(schema.inputs,cls.INPUT_TYPES()['required'].values()):
            typ=spec[0];attrs=spec[1] if len(spec)>1 else {}
            assert not inp.optional
            if isinstance(typ,list):assert inp.io_type=='COMBO' and inp.options==typ
            else:assert inp.io_type==typ
            if typ in ('INT','FLOAT','BOOLEAN'):
                for key,value in attrs.items():assert getattr(inp,key)==value
            elif 'default' in attrs:
                assert not hasattr(inp,'default') # source custom socket metadata, no widget
        assert [x.io_type for x in schema.outputs]==list(cls.RETURN_TYPES)
        assert [x.display_name for x in schema.outputs]==list(getattr(cls,'RETURN_NAMES',[None]*len(cls.RETURN_TYPES)))
    assert all('FillVec' not in i for i in new.NODE_CLASS_MAPPINGS)
    assert not list(PACK.rglob('*.js'))

def test_all_278_choices_and_native_quirks_differential():
    async def run():
        rows=cases()+TARGETED
        assert len(cases())==278
        for node_id,fields in rows:
            converted=dict(fields)
            if 'image' in fields:converted['image']=SpatialMetadata(fields['image'])
            try:old=native(node_id,fields)
            except Exception as e:
                with pytest.raises(type(e)) as observed:
                    await load(V2).NODE_CLASS_MAPPINGS[node_id].execute(**converted)
                assert str(observed.value)==str(e),(node_id,fields)
            else:
                with np.errstate(all='ignore'):
                    actual=await load(V2).NODE_CLASS_MAPPINGS[node_id].execute(**converted)
                equivalent(old,actual.result)
        # Metadata-only zero-height preserves native arithmetic failure, not a
        # claim that the IMAGE broker admits an empty image allocation.
        fields={'image':torch.zeros(1,0,2,3)}
        with pytest.raises(ZeroDivisionError):native('CM_NearestSDXLResolution',fields)
        with pytest.raises(ZeroDivisionError):
            await load(V2).NODE_CLASS_MAPPINGS['CM_NearestSDXLResolution'].execute(image=SpatialMetadata(fields['image']))
        print(json.dumps({'differential_cases':len(rows),'choice_cases':278,'targeted_cases':len(TARGETED),
            'positively_or_native_error_exercised_ids':53,'numpy':np.__version__}))
    asyncio.run(run())

@pytest.mark.parametrize('node_id,args',[
 ('CM_IntUnaryOperation',dict(op='Factorial',a=513)),
 ('CM_IntUnaryOperation',dict(op='Cube',a=2**2047)),
 ('CM_IntBinaryOperation',dict(op='Pow',a=2,b=4097)),
 ('CM_IntBinaryOperation',dict(op='Pow',a=2**2047,b=3)),
 ('CM_IntBinaryOperation',dict(op='Shr',a=1,b=4097)),
 ('CM_IntBinaryOperation',dict(op='Shl',a=1,b=10**100)),
 ('CM_IntBinaryOperation',dict(op='Add',a=2**2048,b=0)),
 ('CM_FloatBinaryOperation',dict(op='Pow',a=2,b=4097)),
 ('CM_Vec3BinaryOperation',dict(op='Add',a=[[1]],b=(2.,3.,4.))),
 ('CM_Vec3BinaryOperation',dict(op='Add',a=(1.,)*5,b=(2.,3.,4.))),
 ('CM_Vec3BinaryOperation',dict(op='Add',a=('x',),b=(2.,3.,4.))),
 ('CM_Vec3BinaryOperation',dict(op='Add',a=(2**2048,),b=(2.,3.,4.))),
 ('CM_Vec3ScalarOperation',dict(op='Mul',a=(1.,2.,3.),b=object())),
])
def test_refusal_before_expensive_math_or_numpy_allocation(node_id,args,monkeypatch):
    nodes=sys.modules[load(V2).NODE_CLASS_MAPPINGS[node_id].__module__]
    calls=[]
    def forbidden(*a,**kw):calls.append(1);raise AssertionError('computation before refusal')
    monkeypatch.setattr(nodes.numpy,'array',forbidden)
    monkeypatch.setattr(nodes.iops,'INT_UNARY_OPERATIONS',{'Factorial':forbidden,'Cube':forbidden})
    monkeypatch.setattr(nodes.iops,'INT_BINARY_OPERATIONS',{args.get('op'):forbidden})
    with pytest.raises((ValueError,TypeError)):
        asyncio.run(load(V2).NODE_CLASS_MAPPINGS[node_id].execute(**args))
    assert not calls

async def development_session(name,root,monkeypatch):
    real_resolve=packruntime.resolve_for_tenant
    def selected(spec,tenant):
        assert spec is None
        original=real_resolve(spec,tenant)
        assert original.python_executable==Path(sys.executable)
        return replace(original,spec=replace(original.spec,pack_root=root.resolve()))
    with monkeypatch.context() as context:
        context.setattr(packruntime,'resolve_for_tenant',selected)
        guest=await GuestSession(name,module_source_root=root,guest_runtime_root=HOST_VENV).start()
    assert guest.sandbox_kind=='seatbelt' and guest.python_executable==Path(sys.executable)
    return guest

def test_all_53_all_choices_and_custom_consumer_complex_successor_real_outer_fresh_guests(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    import execution
    async def run():
        previous=_sdk.providers.execution_backend;pids=[];totals=[]
        try:
            for index in range(2):
                root=V2 if index==0 else tmp_path/'fresh'/'ComfyMath-HEAD'/'v2'
                if index:shutil.copytree(V2,root)
                mapping=packdb.load_pack(root.parent.parent,mount_name='custom_nodes.jack_math_'+str(index)).node_mappings
                guest=await development_session('jack-comfymath-'+str(index),root,monkeypatch)
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await guest.execute(plan,runtime,capabilities=(),tenant='jack-math-user-'+str(index))
                _sdk.providers.register_execution_backend(Backend())
                async def outer(node_id,fields):
                    cls=mapping[node_id]
                    values,missing,meta=execution.get_input_data(fields,cls,node_id,None)
                    assert not missing
                    result=await execution._async_map_node_over_list('jack-math',node_id,cls,values,'execute',v3_data=meta)
                    return (await execution.resolve_map_node_over_list_results(result))[0].result
                count=errors=0
                try:
                    for node_id,fields in cases()+TARGETED:
                        try:old=native(node_id,fields)
                        except Exception as expected:
                            with pytest.raises(wire.WireError) as failure:await outer(node_id,fields)
                            assert failure.value.remote_type==type(expected).__name__
                            assert str(expected) in str(failure.value)
                            errors+=1
                        else:
                            equivalent(old,await outer(node_id,fields));count+=1
                    print(json.dumps({'stage':'all-source-cases','differential_cases':len(cases()+TARGETED),'pid':guest.pid,'positive':count,'native_errors':errors,'capabilities':[]}))
                    # Exact converted producers feed actual converted consumers.
                    for producer in ('CM_FloatBinaryOperation','CM_NumberBinaryOperation'):
                        z=(await outer(producer,dict(op='Pow',a=-1.,b=.5)))[0]
                        assert type(z) is complex and z==(-1.)**.5
                        for operation in ('Add','Mul'):
                            fields=dict(op=operation,a=z,b=2.)
                            equivalent(native('CM_FloatBinaryOperation',fields),await outer('CM_FloatBinaryOperation',fields))
                        fields=dict(op='Neg',a=z)
                        equivalent(native('CM_FloatUnaryOperation',fields),await outer('CM_FloatUnaryOperation',fields))
                        equivalent(native('CM_FloatToNumber',dict(a=z)),await outer('CM_FloatToNumber',dict(a=z)))
                        for consumer,fields in [('CM_NumberBinaryOperation',dict(op='Add',a=z,b=2.)),
                                ('CM_NumberUnaryOperation',dict(op='Neg',a=z)),
                                ('CM_NumberToFloat',dict(a=z)),('CM_NumberToInt',dict(a=z)),
                                ('CM_FloatUnaryCondition',dict(op='IsFinite',a=z))]:
                            with pytest.raises(wire.WireError) as failure:await outer(consumer,fields)
                            assert failure.value.remote_type=='TypeError'
                            assert 'complex' in str(failure.value)
                            assert (await outer('CM_FloatBinaryOperation',dict(op='Pow',a=4.,b=.5)))[0]==2.
                    print(json.dumps({'stage':'complex-successor','pid':guest.pid,'complex_producers':2,'positive_producer_consumer_calls':10,'native_errors':10,'recovery_calls':10}))
                    # Actual NUMPY producers exercise SDK wrapping as well as wire.
                    norm=(await outer('CM_Vec3ToScalarUnaryOperation',dict(op='Norm',a=(3.,4.,0.))))[0]
                    assert type(norm) is np.float64
                    equivalent(native('CM_FloatBinaryOperation',dict(op='Add',a=norm,b=1.)),
                        await outer('CM_FloatBinaryOperation',dict(op='Add',a=norm,b=1.)))
                    boolean=(await outer('CM_Vec3UnaryCondition',dict(op='IsNotZero',a=(1.,0.,0.))))[0]
                    assert type(boolean) is np.bool_
                    equivalent(native('CM_BoolUnaryOperation',dict(op='Not',a=boolean)),
                        await outer('CM_BoolUnaryOperation',dict(op='Not',a=boolean)))
                    vec=(await outer('CM_ComposeVec3',dict(x=norm,y=2.,z=3.)))[0]
                    equivalent(native('CM_Vec3UnaryOperation',dict(op='Neg',a=vec)),
                        await outer('CM_Vec3UnaryOperation',dict(op='Neg',a=vec)))
                    # Source ComposeVec preserves numeric leaf types; its VEC
                    # output is then a genuinely matching VEC consumer input.
                    leaf_types=(np.bool_,np.int8,np.int16,np.int32,np.int64,
                        np.uint8,np.uint16,np.uint32,np.uint64,np.float16,
                        np.float32,np.float64,np.complex64,np.complex128)
                    for leaf in leaf_types:
                        fields=dict(x=leaf(1),y=leaf(2))
                        made=await outer('CM_ComposeVec2',fields)
                        equivalent(native('CM_ComposeVec2',fields),made)
                        consumed=dict(op='Dot',a=made[0],b=made[0])
                        equivalent(native('CM_Vec2ToScalarBinaryOperation',consumed),
                            await outer('CM_Vec2ToScalarBinaryOperation',consumed))
                    print(json.dumps({'stage':'numpy-leaf-source-vec-chains','pid':guest.pid,
                        'closed_numpy_classes':[t.__name__ for t in leaf_types],
                        'scope':'host scalar fixtures into actual ComposeVec2 -> typed VEC2 Dot; no synthetic replacement algorithm'}))
                    print(json.dumps({'required_seatbelt_pid':guest.pid,'fresh_root':str(root),'positive':count,'native_errors':errors,'all_ids':sorted(mapping),'complex_successor':True,'capabilities':[]}))
                    pids.append(guest.pid);totals.append((count,errors))
                finally:await guest.kill()
            assert len(set(pids))==2
            print(json.dumps({'pids':pids,'totals':totals,'scope':'unsealed Mac development, no Linux/Cloud deployment'}))
        finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())

def test_no_ambient_authority_legacy_class_bridge_or_new_registration():
    for file in [V2/'nodes.py',V2/'bounds.py',*(V2/'algorithms').glob('*.py')]:
        tree=ast.parse(file.read_text())
        assert not any(isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('comfy.') for n in ast.walk(tree))
        assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('open','eval','exec','__import__','compile') for n in ast.walk(tree))
        assert not any(isinstance(n,ast.FunctionDef) and n.name=='INPUT_TYPES' for n in ast.walk(tree))
        if file.parent.name=='algorithms':assert not any(isinstance(n,ast.ClassDef) for n in tree.body)
    # Source operator dictionaries/helper functions/ordered resolution constants
    # are pack-local AST-equivalent, rather than substituted approximations.
    for name in ('bool','int','float','number','vec','graphics'):
        old=ast.parse((PACK/'src/comfymath'/f'{name}.py').read_text())
        kept=[]
        for node in old.body:
            if isinstance(node,ast.ClassDef):continue
            targets=node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,ast.AnnAssign) else []
            if any(isinstance(t,ast.Name) and t.id=='NODE_CLASS_MAPPINGS' for t in targets):continue
            kept.append(node)
        expected=ast.Module(body=kept,type_ignores=[])
        new=ast.parse((V2/'algorithms'/f'{name}.py').read_text())
        assert ast.dump(expected,include_attributes=False)==ast.dump(new,include_attributes=False)

def test_small_integer_admission_extrema_and_vector_dot_projection(monkeypatch):
    async def run():
        inputs=[('CM_IntUnaryOperation',dict(op='Factorial',a=512)),
            ('CM_IntBinaryOperation',dict(op='Pow',a=2,b=2048)),
            ('CM_IntBinaryOperation',dict(op='Pow',a=1,b=4096)),
            ('CM_IntBinaryOperation',dict(op='Shl',a=1,b=4095)),
            ('CM_IntBinaryOperation',dict(op='Shr',a=1,b=4096)),
            ('CM_IntBinaryOperation',dict(op='Mul',a=2**2047,b=2**2047))]
        for node_id,args in inputs:
            equivalent(native(node_id,args),(await load(V2).NODE_CLASS_MAPPINGS[node_id].execute(**args)).result)
    asyncio.run(run())
    nodes=sys.modules[load(V2).NODE_CLASS_MAPPINGS['CM_Vec3ToScalarBinaryOperation'].__module__]
    def forbidden(*args,**kw):raise AssertionError('np.array reached before projected refusal')
    monkeypatch.setattr(nodes.numpy,'array',forbidden)
    with pytest.raises(ValueError,match='projected vector'):
        asyncio.run(nodes.Vec3ToScalarBinaryOperation.execute(op='Dot',a=(2**2047,)*3,b=(2**2047,)*3))

def test_actual_required_guest_outside_read_import_raw_denial_recovery(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    probe=load(V2)
    spec=importlib.util.spec_from_file_location(probe.__name__+'.tests.boundary_probe',V2/'tests/boundary_probe.py')
    boundary=importlib.util.module_from_spec(spec);sys.modules[spec.name]=boundary;spec.loader.exec_module(boundary)
    outside=tmp_path/'outside_marker.py'
    # Scratch-only existing harmless marker; copy an immutable pack resource.
    shutil.copyfile(PACK/'src/comfymath/types.py',outside)
    async def run():
        guest=await development_session('jack-math-boundary',V2,monkeypatch)
        try:
            refs=_sdk.InProcessRefResolver()
            async def dispatch(cls,fields):
                plan=_sdk.ExecutionPlan('boundary','1',cls.__name__,node_module=cls.__module__,
                    inputs=await _sdk.wrap_inputs(refs,fields),input_mode='refs',permissions=(),tier='sandbox')
                rt=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                return await guest.execute(plan,rt,capabilities=(),tenant='jack-math-boundary')
            assert (await dispatch(boundary.OutsideBoundaryProbe,{'outside':str(outside)})).result[0]=='read,import'
            with pytest.raises(wire.WireError,match='raw'):
                await dispatch(boundary.RawImageProbe,{'image':torch.zeros(1,2,3,3)})
            cls=probe.NODE_CLASS_MAPPINGS['CM_FloatBinaryOperation']
            assert (await dispatch(cls,dict(op='Pow',a=4.,b=.5))).result[0]==2.
            print(json.dumps({'boundary_pid':guest.pid,'outside_read_refusals':1,'outside_import_refusals':1,'raw_refusals':1,'recovery':True}))
        finally:await guest.kill()
    asyncio.run(run())

def test_pristine_manifest_stubs_exact_pair_and_zip(tmp_path):
    refs=json.loads((V2/'tests/pristine-sha256.json').read_text())
    actual={f.relative_to(PACK).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
        for f in PACK.rglob('*') if f.is_file() and f.relative_to(PACK).parts[0]!='v2'}
    assert len(actual)==17 and actual==refs['files']
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))
    runtime=json.loads((V2/'DEVELOPMENT_RUNTIME.json').read_text())
    for name,digest in runtime['stubs'].items():assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==digest
    manifest=json.loads((V2/'secure-nodes.json').read_text());mapping=load(V2).NODE_CLASS_MAPPINGS
    assert set(manifest['nodes'])==set(mapping)
    report=(V2/'SECURE_CONVERSION.md').read_text()
    rows=[line.split('|')[1].strip() for line in report.splitlines() if '| supported — bounded local development |' in line]
    assert rows==list(mapping)
    for node_id,cls in mapping.items():
        assert manifest['nodes'][node_id]['schema']==encode_schema(cls.GET_SCHEMA())
        assert manifest['nodes'][node_id]['permissions']==[]
    patch,diff=packpatch.generate(SNAPSHOT)
    pair=CORPUS/'patches/comfymath/xc011772';stem='comfymath-xc011772'
    assert json.loads((pair/(stem+'.json')).read_text())==patch
    assert (pair/(stem+'.diff')).read_text()==diff
    bundle=packpatch.bundle(patch,diff);assert bundle==packpatch.bundle(patch,diff)
    with zipfile.ZipFile(bytesio.BytesIO(bundle)) as z:assert sorted(z.namelist())==[stem+'.diff',stem+'.json']
    for mode in ('pair','zip'):
        fresh=tmp_path/mode/'comfymath/xc011772';dest=fresh/PACK.name
        shutil.copytree(PACK,dest,ignore=shutil.ignore_patterns('v2'))
        if mode=='pair':packpatch.apply(fresh,patch,diff)
        else:packpatch.apply_bundle(fresh,bundle)
        packpatch.validate_tree(dest/'v2',V2)
