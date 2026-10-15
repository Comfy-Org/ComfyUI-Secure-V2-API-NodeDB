"""Pinned face tracking/contour parity, not pose-detector or model inference."""
import ast
import asyncio
import copy
import importlib.util
import logging
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import pytest
import torch
from einops import rearrange

sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1]
PACK=V2.parent
CORE=Path('/Users/ben/comfy/ComfyUI-secure-nodes')
BACKEND=Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
for path in (CORE,BACKEND):sys.path.insert(0,str(path))
os.environ.setdefault('COMFY_CORE_ROOT',str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packdb

ID='FaceMaskFromPoseKeypoints'
INPUT_TYPES={'pose_kps':'POSE_KEYPOINT'}

def original():
    tree=ast.parse((PACK/'nodes_utility.py').read_text())
    cls=next(item for item in tree.body if isinstance(item,ast.ClassDef) and item.name==ID)
    namespace={'torch':torch,'np':np,'rearrange':rearrange,'log':logging.getLogger('wan-pose-oracle')}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'nodes_utility.py'),'exec'),namespace)
    return namespace[ID]

def candidate(root=V2):
    name='_wan_pose_'+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS[ID]

def person(x=30,y=30,radius=12,variant='normal'):
    angles=np.linspace(0,2*np.pi,17,endpoint=False)
    points=np.stack((x+radius*np.cos(angles),y+radius*np.sin(angles),np.ones(17)),axis=1)
    if variant=='missing':return {}
    if variant=='empty':return {'face_keypoints_2d':[]}
    if variant=='zero':points[:,:2]=0
    if variant=='short':points=points[:16]
    if variant=='nan':points[2,0]=float('nan')
    if variant=='inf':points[2,0]=float('inf')
    if variant=='negative':points[2,0]=-1
    if variant=='corner':points[:4,:2]=0
    if variant=='duplicate':points[:,:2]=[x,y]
    if variant=='thin':points[:,1]=y
    if variant=='large':points[:,:2]=(points[:,:2]-[x,y])*10+[x,y]
    return {'face_keypoints_2d':points.reshape(-1).tolist()}

def frame(people,width=96,height=80):
    return {'people':people,'canvas_width':width,'canvas_height':height}

def cases():
    values=[dict(pose_kps=[],person_index=0)]
    for width,height in ((96,80),(128,64),(64,64)):
        for variant in ('normal','missing','empty','zero','short','nan','inf','negative','corner','duplicate','thin','large'):
            for index in (0,1,100,-1):
                values.append(dict(pose_kps=[frame([person(variant='zero'),person(variant=variant),person(45,35,8)],width,height)],person_index=index))
    for index in (0,1,100):
        values.append(dict(pose_kps=[frame([person(20,30),person(60,30)]),
            frame([person(58,31),person(22,31)]),frame([]),
            frame([person(25,32),person(55,32)]),frame([person(variant='missing')])],person_index=index))
    return values

def assert_output(expected,actual):
    assert len(actual)==1
    left,right=expected[0],actual[0]
    assert left.shape==right.shape and left.dtype==right.dtype and left.device==right.device
    assert torch.equal(left,right)

async def direct(inputs):
    refs=_sdk.InProcessRefResolver()
    plan=_sdk.ExecutionPlan('pose','1',ID,permissions=('raw',),input_types=INPUT_TYPES,input_mode='values')
    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
    with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):result=await candidate().execute(**inputs)
    return (await _sdk.unwrap_outputs(refs,result)).result

def test_pose_schema_exact_and_raw_value_mode():
    old=original();new=candidate();schema=new.GET_SCHEMA()
    assert schema.category==old.CATEGORY and schema.display_name=='Face Mask From Pose Keypoints'
    specs=old.INPUT_TYPES()['required']
    assert [field.id for field in schema.inputs]==list(specs)
    for field in schema.inputs:
        spec=specs[field.id];assert field.io_type==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert getattr(field,key)==value
    assert tuple(output.io_type for output in schema.outputs)==old.RETURN_TYPES
    assert new.SDK_REFS is False and new.SDK_PERMISSIONS==('raw',)

def test_pose_exact_contour_pixels_tracking_fallback_and_invalid_detections():
    async def run():
        for inputs in cases():
            assert_output(original()().createmask(**copy.deepcopy(inputs)),await direct(copy.deepcopy(inputs)))
    asyncio.run(run())

def test_pose_tracking_selects_same_subject_when_person_order_changes():
    inputs=cases()[-3]
    result=asyncio.run(direct(copy.deepcopy(inputs)))[0]
    assert result[0,:,15:35].sum()>0 and result[1,:,15:35].sum()>0
    assert result[1,:,45:75].sum()==0
    assert result[2].sum()==0 and result[4].sum()==0
    assert torch.equal(result,original()().createmask(**copy.deepcopy(inputs))[0])

@pytest.mark.parametrize('inputs',[
    dict(pose_kps=[{}],person_index=0),
    dict(pose_kps=[frame([{'face_keypoints_2d':[1,2,3,4]}])],person_index=0),
    dict(pose_kps=[frame([],width=-1)],person_index=0),
    dict(pose_kps=[frame([],width=3.5)],person_index=0),
    dict(pose_kps=[frame([],width=12),frame([],width=15)],person_index=0),
])
def test_pose_bounded_native_malformed_errors(inputs):
    def failure(fn):
        try:fn()
        except Exception as error:return type(error).__name__,str(error)
        raise AssertionError('Expected source failure')
    assert failure(lambda:original()().createmask(**copy.deepcopy(inputs)))==failure(lambda:asyncio.run(direct(copy.deepcopy(inputs))))

def test_pose_preallocation_limits_and_input_immutability(monkeypatch):
    inputs=dict(pose_kps=[frame([person()])],person_index=0)
    before=copy.deepcopy(inputs)
    assert_output(original()().createmask(**copy.deepcopy(inputs)),asyncio.run(direct(inputs)))
    assert inputs==before
    def forbidden(*args,**kwargs):raise AssertionError('No canvas allocation before quota rejection')
    monkeypatch.setattr(np,'zeros',forbidden)
    with pytest.raises(ValueError,match='projected'):asyncio.run(direct(dict(pose_kps=[frame([],width=10000,height=10000)],person_index=0)))
    with pytest.raises(ValueError,match='4096'):asyncio.run(direct(dict(pose_kps=[frame([{}]*4097)],person_index=0)))

def guest_cases():
    return [cases()[0],cases()[1],cases()[6],cases()[37],cases()[-3],cases()[-2],cases()[-1]]

def test_pose_real_guest_raw_denial_and_fresh_render(tmp_path):
    fresh=tmp_path/'fresh';shutil.copytree(V2,fresh)
    async def run():
        for root in (V2,fresh):
            cls=candidate(root);session=await GuestSession('wan-pose',guest_runtime_root=root).start()
            try:
                for inputs in guest_cases():
                    refs=_sdk.InProcessRefResolver()
                    plan=_sdk.ExecutionPlan('wan-pose','1',ID,node_module=cls.__module__,input_mode='values',
                        input_types=INPUT_TYPES,permissions=('raw',),tier='sandbox',inputs=inputs)
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    with pytest.raises(Exception,match='raw'):await session.execute(plan,runtime,capabilities=())
                    actual=await session.execute(plan,runtime,capabilities=('raw',))
                    assert_output(original()().createmask(**copy.deepcopy(inputs)),(await _sdk.unwrap_outputs(refs,actual)).result)
                assert session.last_guest_pid not in (None,os.getpid())
            finally:await session.kill()
    asyncio.run(run())

def test_pose_production_outer_mask_pixels(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE))
    import execution
    cls=packdb.load_pack(PACK.parent,mount_name='custom_nodes.wan_pose_outer').node_mappings[ID]
    async def run():
        previous=_sdk.providers.execution_backend
        class Backend:
            sessions=[]
            async def dispatch(self,plan,local_call,runtime):
                assert plan.input_mode=='values'
                session=await GuestSession('pose-outer',guest_runtime_root=V2).start()
                self.sessions.append(session)
                return await session.execute(plan,runtime,capabilities=('raw',))
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        try:
            for inputs in guest_cases():
                cls.GET_SCHEMA()
                finalized,missing,data=execution.get_input_data(copy.deepcopy(inputs),cls,'1',None)
                assert not missing
                values=await execution._async_map_node_over_list(prompt_id='pose-outer',unique_id='1',obj=cls,
                    input_data_all=finalized,func='execute',v3_data=data)
                assert tuple(cls.RETURN_TYPES)==('MASK',)
                assert_output(original()().createmask(**copy.deepcopy(inputs)),values[0].result)
        finally:
            _sdk.providers.register_execution_backend(previous)
            for session in backend.sessions:await session.kill()
    asyncio.run(run())
