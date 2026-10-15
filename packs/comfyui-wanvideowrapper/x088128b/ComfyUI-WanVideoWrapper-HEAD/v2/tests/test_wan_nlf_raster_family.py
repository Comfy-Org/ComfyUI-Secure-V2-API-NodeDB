"""Pinned full NLF raster helper; projection fixtures, not learned NLF inference."""
import ast
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
CORE='/Users/ben/comfy/ComfyUI-secure-nodes'
sys.path[:0]=[CORE,'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
os.environ.setdefault('COMFY_CORE_ROOT',CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
ID='DrawNLFPoses'

def load(root,name):
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg);return pkg

def candidate(root=V2):return load(root,'_wan_nlf_'+str(id(root))).NODE_CLASS_MAPPINGS[ID]

def helper():
    spec=importlib.util.spec_from_file_location('_wan_nlf_draw_oracle',PACK/'MTV/draw_pose.py')
    pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg);return pkg

def source():
    cls=next(x for x in ast.parse((PACK/'MTV/nodes.py').read_text()).body if getattr(x,'name',None)==ID)
    fn=next(x for x in cls.body if getattr(x,'name',None)=='predict')
    fn.body=fn.body[1:] # replace relative helper import only with exact pinned helper
    ns={'get_control_conditions':helper().get_control_conditions}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'MTV/nodes.py'),'exec'),ns)
    return ns[ID]()

def poses(frames=2,joints=24,dtype=np.float32):
    data=np.zeros((frames,1,joints,3),dtype=dtype)
    data[...,0]=np.linspace(-.5,.5,joints)
    data[...,1]=np.sin(np.linspace(0,5,joints))*.5
    data[...,2]=2
    for index in range(frames):data[index,...,0]+=.03*index
    return data

def same(a,b):
    assert a.shape==b.shape and a.dtype==b.dtype
    assert a.device==b.device==torch.device('cpu')
    torch.testing.assert_close(a,b,rtol=0,atol=0,equal_nan=True)

def test_exact_schema_helpers_and_native_widget_method_default_mismatch():
    old=source();cls=candidate();schema=cls.GET_SCHEMA();spec=old.INPUT_TYPES();fields={**spec['required'],**spec['optional']}
    assert schema.node_id==ID and schema.category==old.CATEGORY and schema.display_name=='Draw NLF Poses'
    assert [x.id for x in schema.inputs]==list(fields)
    for item,(name,record) in zip(schema.inputs,fields.items()):
        assert item.optional==(name in spec['optional'])
        if isinstance(record[0],list):assert item.options==record[0]
        else:assert item.io_type==record[0]
        for key,value in (record[1] if len(record)>1 else {}).items():assert getattr(item,key)==value
    assert schema.outputs[0].display_name==old.RETURN_NAMES[0] and schema.outputs[0].io_type=='IMAGE'
    assert (V2/'MTV/draw_pose.py').read_bytes()==(PACK/'MTV/draw_pose.py').read_bytes()
    assert cls.execute.__defaults__==(1.0,2,'original')
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)

def test_complete_pixel_methods_styles_containers_and_nonmutation():
    cls=candidate();old=source();rng=torch.random.get_rng_state().clone();count=0
    for size in ((64,32),(256,350),(512,512)):
        for style in ('original','scail','unknown'):
            for kind in ('numpy','torch','dict'):
                for frames in (1,2):
                    data=poses(frames,32,np.float64)
                    inputs=data if kind=='numpy' else torch.from_numpy(data.copy()) if kind=='torch' else {'joints3d_nonparam':data[None],'metadata':'kept'}
                    before=copy.deepcopy(inputs)
                    args=dict(poses=inputs,width=size[0],height=size[1],stick_width=4.0,point_radius=5,style=style)
                    same(old.predict(**copy.deepcopy(args))[0],cls.execute(**args).result[0]);count+=1
                    if kind=='numpy':np.testing.assert_array_equal(inputs,before)
                    elif kind=='torch':assert torch.equal(inputs,before)
                    else:np.testing.assert_array_equal(inputs['joints3d_nonparam'],before['joints3d_nonparam'])
    assert count==54 and torch.equal(torch.random.get_rng_state(),rng)
    for style in ('original','scail'):
        assert cls.execute(poses(1),256,350,4,5,style).result[0].sum()>0
    # Direct method defaults differ from optional widget defaults; preserve both.
    same(old.predict(poses(1),256,350)[0],cls.execute(poses(1),256,350).result[0])

def test_source_swallowed_raster_failures_empty_shapes_and_native_errors():
    cls=candidate();old=source()
    values=[poses(1,2),poses(1,24)*0,poses(1,24)*float('nan'),poses(1,24)*float('inf'),
        {},[],{'joints3d_nonparam':np.empty((1,0,1,24,3),dtype=np.float32)}]
    for value in values:
        same(old.predict(copy.deepcopy(value),32,64)[0],cls.execute(copy.deepcopy(value),32,64).result[0])
    assert cls.execute({},32,64).result[0].shape==torch.Size([0]) # source malformed IMAGE shape, direct only
    for args in (dict(poses=poses(1),width=-1,height=32),dict(poses=poses(1),width=2.5,height=32),
            dict(poses={'joints3d_nonparam':[]},width=32,height=64),dict(poses=None,width=32,height=64)):
        outcomes=[]
        for call in (lambda:old.predict(**copy.deepcopy(args)),lambda:cls.execute(**copy.deepcopy(args))):
            try:call();outcomes.append(None)
            except Exception as error:outcomes.append((type(error).__name__,str(error)))
        assert outcomes[0] is not None and outcomes[0]==outcomes[1]

def test_preallocation_limits_before_canvas_generation(monkeypatch):
    cls=candidate();mod=sys.modules[cls.__module__]
    monkeypatch.setattr(mod,'get_control_conditions',lambda *args,**kwargs:pytest.fail('raster before bound'))
    for args in (dict(poses=poses(513),width=32,height=64),dict(poses=poses(1,1025),width=32,height=64),
            dict(poses=poses(1),width=2049,height=64),dict(poses=poses(1),width=32,height=64,point_radius=1001),
            dict(poses=poses(10),width=512,height=512),dict(poses={str(i):None for i in range(513)},width=32,height=64),
            dict(poses=poses(250,1024),width=32,height=64)):
        with pytest.raises(ValueError):cls.execute(**args)

def test_actual_outer_images_allstyles_and_inputs_fresh_guests_raw_denial(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required');monkeypatch.syspath_prepend(CORE)
    fresh=tmp_path/'fresh-render';shutil.copytree(V2,fresh)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index,root in enumerate((V2,fresh)):
                cls=candidate(root);session=await GuestSession('wan-nlf-raster',guest_runtime_root=root).start()
                assert session.sandbox_kind=='seatbelt'
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                        return await session.execute(plan,runtime,capabilities=('raw',),tenant='nlf-'+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for style,kind in (('original','numpy'),('scail','dict'),('unknown','torch')):
                        value=poses(2)
                        data=value if kind=='numpy' else {'joints3d_nonparam':value[None],'source':'projection-fixture'} if kind=='dict' else torch.from_numpy(value)
                        args=dict(poses=data,width=256,height=350,stick_width=4.0,point_radius=5,style=style)
                        expected=source().predict(**copy.deepcopy(args))[0]
                        finalized,missing,meta=execution.get_input_data(args,cls,'owner',None);assert not missing
                        result=await execution._async_map_node_over_list(prompt_id='nlf',unique_id='owner',obj=cls,input_data_all=finalized,func='execute',v3_data=meta)
                        same(expected,result[0].result[0]);assert cls.GET_SCHEMA().outputs[0].io_type=='IMAGE'
                        refs=_sdk.InProcessRefResolver()
                        plan=_sdk.ExecutionPlan(prompt_id='denied',node_id='owner',node_type=ID,node_module=cls.__module__,
                            inputs=await _sdk.wrap_inputs(refs,args),input_mode='values',permissions=('raw',),tier='sandbox')
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match='raw'):
                            await session.execute(plan,runtime,capabilities=(),tenant='nlf-'+str(index))
                    pids.append(session.pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
