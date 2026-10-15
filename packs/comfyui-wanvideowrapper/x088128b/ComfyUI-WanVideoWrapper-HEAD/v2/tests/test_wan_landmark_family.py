"""Pinned coordinate consumer; no FantasyPortrait model/detector inference."""
import ast
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
CORE='/Users/ben/comfy/ComfyUI-secure-nodes'
sys.path[:0]=[CORE,'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
os.environ.setdefault('COMFY_CORE_ROOT',CORE)
from comfy_api.latest import _sdk, sdk
from comfy_secure_nodes.transport.host import GuestSession
ID='LandmarksToImage'

def candidate(root=V2):
    name='_wan_landmark_'+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg)
    return pkg.NODE_CLASS_MAPPINGS[ID]

def source(events=None):
    cls=next(x for x in ast.parse((PACK/'fantasyportrait/nodes.py').read_text()).body if getattr(x,'name',None)==ID)
    class Progress:
        def __init__(self,total):self.total=total;self.value=0
        def update(self,value):
            self.value+=value
            if events is not None:events.append((self.value,self.total))
    ns=dict(np=np,torch=torch,ProgressBar=Progress)
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'fantasyportrait/nodes.py'),'exec'),ns)
    return ns[ID]()

def ctx(monkeypatch,events):
    class Progress:
        async def update(self,value,total,preview=None):
            assert preview is None
            events.append((value,total))
    monkeypatch.setattr(sdk,'ctx',lambda:SimpleNamespace(progress=Progress()))

def same(left,right):
    assert left.shape==right.shape and left.dtype==right.dtype
    assert left.device==right.device==torch.device('cpu')
    torch.testing.assert_close(left,right,rtol=0,atol=0,equal_nan=True)

def cases():
    result=[]
    for count in (1,3):
        for width,height in ((12,10),(32,18)):
            for pattern in ('empty','inside','outside','fractional'):
                points={'empty':[],'inside':[[0,0],[width-1,height-1],[width//2,height//2]],
                    'outside':[[-20,-3],[width+4,height+4],[1000000,-1000000]],
                    'fractional':[[1.9,2.1],[-1.8,0.8],['3','4']]}[pattern]
                landmarks=copy.deepcopy([points]*count)
                for dtype in (None,torch.uint8,torch.float16,torch.bfloat16,torch.float32,torch.float64):
                    image=None
                    if dtype is not None:
                        image=(torch.arange(count*height*width*3).reshape(count,height,width,3)%255).to(dtype)
                        if dtype.is_floating_point:image/=255
                    result.append(dict(landmarks=landmarks,width=width,height=height,image=image))
    return result

def test_exact_schema_default_metadata_and_raster_ast():
    old=source();cls=candidate();schema=cls.GET_SCHEMA();specs=old.INPUT_TYPES()
    assert schema.node_id==ID and schema.category==old.CATEGORY and schema.display_name=='Landmarks to Image'
    all_specs={**specs['required'],**specs['optional']}
    assert [x.id for x in schema.inputs]==list(all_specs)
    for item,(name,spec) in zip(schema.inputs,all_specs.items()):
        assert item.io_type==spec[0] and item.optional==(name in specs['optional'])
        for key,value in (spec[1] if len(spec)>1 else {}).items():
            assert (item.extra_dict[key] if name=='landmarks' else getattr(item,key))==value
    assert schema.outputs[0].io_type==old.RETURN_TYPES[0] and schema.outputs[0].display_name==old.RETURN_NAMES[0]
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
    old_cls=next(x for x in ast.parse((PACK/'fantasyportrait/nodes.py').read_text()).body if getattr(x,'name',None)==ID)
    old_fn=next(x for x in old_cls.body if getattr(x,'name',None)=='drawkeypoints')
    new_cls=next(x for x in ast.parse((V2/'secure_landmark_nodes.py').read_text()).body if getattr(x,'name',None)==ID)
    new_fn=next(x for x in new_cls.body if getattr(x,'name',None)=='execute')
    body=old_fn.body[1:]
    body=[x for x in body if not (isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name) and x.targets[0].id=='pbar')]
    loop=next(x for x in body if isinstance(x,ast.For))
    loop.body[-1]=ast.parse('await sdk.ctx().progress.update(i+1,len(landmarks))').body[0]
    body[-1]=ast.parse('return io.NodeOutput(keypoints_img_tensor)').body[0]
    assert ast.dump(ast.Module(body=body,type_ignores=[]),include_attributes=False)==ast.dump(ast.Module(body=new_fn.body[1:],type_ignores=[]),include_attributes=False)

def test_pixels_all_background_dtypes_empty_regions_coordinates_input_integrity(monkeypatch):
    events=[];ctx(monkeypatch,events);cls=candidate();rng=torch.random.get_rng_state().clone();values=cases()
    successes=failures=0
    for inputs in values:
        before=copy.deepcopy(inputs);expected_events=[]
        expected=actual=None;expected_error=actual_error=None
        try:expected=source(expected_events).drawkeypoints(**copy.deepcopy(inputs))[0]
        except Exception as error:expected_error=(type(error).__name__,str(error))
        events.clear()
        try:actual=asyncio.run(cls.execute(**inputs)).result[0]
        except Exception as error:actual_error=(type(error).__name__,str(error))
        assert expected_error==actual_error
        if expected_error is None:same(expected,actual);successes+=1
        else:failures+=1
        assert events==expected_events
        assert inputs['landmarks']==before['landmarks']
        if inputs['image'] is not None:same(inputs['image'],before['image'])
    assert len(values)==96 and torch.equal(torch.random.get_rng_state(),rng)
    assert successes==80 and failures==16
    # Source ignores supplied background on empty landmark frames.
    image=torch.ones(1,10,12,3)
    assert asyncio.run(cls.execute([[]],12,10,image)).result[0].sum()==0
    # Populated frames retain supplied dimensions/channels, not width/height.
    image=torch.ones(1,8,9,4)
    same(source().drawkeypoints([[[1,1]]],12,10,image)[0],asyncio.run(cls.execute([[[1,1]]],12,10,image)).result[0])

def test_bounded_native_errors_and_progress_before_stack_failure(monkeypatch):
    events=[];ctx(monkeypatch,events);cls=candidate()
    bad=[dict(landmarks=[],width=12,height=10),dict(landmarks=[[[1,2,3]]],width=12,height=10),
        dict(landmarks=[[[float('nan'),2]]],width=12,height=10),dict(landmarks=[[[float('inf'),2]]],width=12,height=10),
        dict(landmarks=[[[1,2]]],width=-1,height=10),dict(landmarks=[[]],width=2.5,height=10),
        dict(landmarks=[[[1,2]],[]],width=12,height=10,image=torch.zeros(2,8,9,3)),
        dict(landmarks=[[[1,2]],[[3,4]]],width=12,height=10,image=torch.zeros(1,10,12,3)),
        dict(landmarks=[[[1,2]]],width=12,height=10,image=torch.tensor(0.))]
    for inputs in bad:
        observed=[];expected_events=[];events.clear()
        for call in (lambda:source(expected_events).drawkeypoints(**copy.deepcopy(inputs)),lambda:asyncio.run(cls.execute(**copy.deepcopy(inputs)))):
            try:call();observed.append(None)
            except Exception as error:observed.append((type(error).__name__,str(error)))
        assert observed[0] is not None and observed[0]==observed[1],observed
        assert events==expected_events

def test_preallocation_bounds_and_raster_limits(monkeypatch):
    events=[];ctx(monkeypatch,events);cls=candidate()
    monkeypatch.setattr(np,'zeros',lambda *args,**kwargs:pytest.fail('allocation before bound'))
    for inputs in (dict(landmarks=[[]]*513,width=12,height=10),dict(landmarks=[[[0,0]]*513],width=12,height=10),
            dict(landmarks=[[[1000001,0]]],width=12,height=10),dict(landmarks=[[]],width=2049,height=10),
            dict(landmarks=[[]]*10,width=512,height=512)):
        with pytest.raises(ValueError):asyncio.run(cls.execute(**inputs))
    assert not events

def test_fresh_required_guest_outer_image_and_numeric_progress_raw_denial(tmp_path,monkeypatch):
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required');monkeypatch.syspath_prepend(CORE)
    fresh=tmp_path/'fresh-render';shutil.copytree(V2,fresh)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index,root in enumerate((V2,fresh)):
                cls=candidate(root);session=await GuestSession('wan-landmark-raster',guest_runtime_root=root).start()
                assert session.sandbox_kind=='seatbelt'
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                        return await session.execute(plan,runtime,capabilities=('raw',),tenant='landmark-'+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for inputs in (dict(landmarks=[[[2,3]],[]],width=12,height=10),
                            dict(landmarks=[[[2.2,3.8]],[[7,6]]],width=12,height=10,image=torch.linspace(0,1,720).reshape(2,10,12,3)),
                            dict(landmarks=[[[2,3]]],width=12,height=10,image=torch.ones(1,8,9,4,dtype=torch.float64))):
                        expected=source().drawkeypoints(**copy.deepcopy(inputs))[0];before=copy.deepcopy(inputs)
                        count=len(session.progress_events)
                        finalized,missing,data=execution.get_input_data(inputs,cls,'owner',None);assert not missing
                        result=await execution._async_map_node_over_list(prompt_id='landmark',unique_id='owner',obj=cls,
                            input_data_all=finalized,func='execute',v3_data=data)
                        same(expected,result[0].result[0]);assert cls.GET_SCHEMA().outputs[0].io_type=='IMAGE'
                        assert session.progress_events[count:]==[(i+1,len(inputs['landmarks'])) for i in range(len(inputs['landmarks']))]
                        if inputs.get('image') is not None:same(inputs['image'],before['image'])
                        refs=_sdk.InProcessRefResolver()
                        plan=_sdk.ExecutionPlan(prompt_id='denied',node_id='owner',node_type=ID,node_module=cls.__module__,
                            inputs=await _sdk.wrap_inputs(refs,inputs),input_mode='values',permissions=('raw',),tier='sandbox')
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match='raw'):
                            await session.execute(plan,runtime,capabilities=(),tenant='landmark-'+str(index))
                    for inputs,message in ((dict(landmarks=[[]],width=12,height=10,image=torch.zeros(1,10,12,3,dtype=torch.bfloat16)),'unsupported ScalarType BFloat16'),
                            (dict(landmarks=[[[2,3]],[]],width=12,height=10,image=torch.zeros(2,8,9,3)),'stack expects each tensor to be equal size')):
                        finalized,missing,data=execution.get_input_data(inputs,cls,'owner',None);assert not missing
                        with pytest.raises(Exception,match=message):
                            await execution._async_map_node_over_list(prompt_id='native-error',unique_id='owner',obj=cls,
                                input_data_all=finalized,func='execute',v3_data=data)
                    pids.append(session.pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
