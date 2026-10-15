"""Independent source pose math + actual guest/custom output transport."""
import ast
import asyncio
import copy
import importlib.util
import itertools
import math
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from typing import NamedTuple,List,Optional,Tuple,Union

import cv2
import matplotlib.colors
import numpy as np
import pytest
import torch
from einops import rearrange
from PIL import ImageColor

CORE=Path(os.environ.get('COMFY_CORE_ROOT','/Users/ben/comfy/ComfyUI-secure-nodes'))
OVERLAY=Path('/Users/ben/comfy/ComfyUI_secure_nodes')
sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
import execution

V2=Path(__file__).resolve().parents[1];PRISTINE=V2.parent
def load(name,root):
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    package=importlib.util.module_from_spec(spec);sys.modules[name]=package;spec.loader.exec_module(package)
    return sys.modules[name+'.nodes']
converted=load('_many_pose_test',V2)

def lift(path,namespace,names=None,assignments=False):
    tree=ast.parse((PRISTINE/path).read_text())
    body=[n for n in tree.body if (isinstance(n,(ast.ClassDef,ast.FunctionDef)) and (names is None or n.name in names)) or (assignments and isinstance(n,ast.Assign))]
    exec(compile(ast.Module(body=body,type_ignores=[]),str(PRISTINE/path),'exec'),namespace)

def reference():
    types=dict(NamedTuple=NamedTuple,List=List,Optional=Optional,Tuple=Tuple,Union=Union)
    lift('src/custom_controlnet_aux/dwpose/types.py',types,assignments=True)
    draw=dict(types,math=math,np=np,cv2=cv2,matplotlib=matplotlib,eps=0.01)
    lift('src/custom_controlnet_aux/dwpose/util.py',draw,['is_normalized','draw_bodypose','draw_handpose','draw_facepose'])
    render=dict(types,np=np,cv2=cv2,util=SimpleNamespace(**draw))
    lift('src/custom_controlnet_aux/dwpose/__init__.py',render,['draw_poses','draw_animalposes','draw_animalpose','decode_json_as_poses'])
    result=dict(render,np=np,cv2=cv2,torch=torch,itertools=itertools,ImageColor=ImageColor,rearrange=rearrange)
    # Full pure classes plus source constants, excluding the ambient saver.
    source=ast.parse((PRISTINE/'node_wrappers/pose_keypoint_postprocess.py').read_text())
    names={'kps_idxs','is_normalized','FacialPartColoringFromPoseKps','SinglePersonProcess','UpperBodyTrackingFromPoseKps','numpy2torch','RenderPeopleKps','RenderAnimalKps'}
    body=[n for n in source.body if (isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names) or (isinstance(n,ast.Assign) and not any(isinstance(t,ast.Name) and t.id.startswith('NODE_') for t in n.targets))]
    exec(compile(ast.Module(body=body,type_ignores=[]),'pristine_pose_wrapper','exec'),result)
    return result
old=reference()

def points(count,normalized=True,missing=False):
    rows=[]
    for i in range(count):
        x=0.15+(i%9)*0.065;y=0.2+(i%7)*0.065
        if not normalized:x*=96;y*=64
        rows.extend([x,y,0.0 if missing and i%5==0 else 1.0])
    return rows

def pose(normalized=True,missing=False):
    person=dict(pose_keypoints_2d=points(18,normalized,missing),face_keypoints_2d=points(68,normalized,missing),
                hand_left_keypoints_2d=points(21,normalized,missing),hand_right_keypoints_2d=points(21,normalized,missing))
    return {'canvas_width':96,'canvas_height':64,'people':[person],'animals':[points(17,False,missing)],'version':'ap10k'}

def values(node,normalized=True,missing=False):
    frame=pose(normalized,missing)
    if node=='RenderPeopleKps':return dict(kps=[frame,{'canvas_width':32,'canvas_height':32,'people':[]}],render_body=True,render_hand=True,render_face=True)
    if node=='RenderAnimalKps':return dict(kps=[frame])
    if node=='FacialPartColoringFromPoseKps':return dict(pose_kps=[frame,copy.deepcopy(frame)],mode='polygon',**old['LAPA_COLORS'])
    return dict(pose_kps=[frame,dict(frame,people=[])],id_include='',**{key+'_width_height':old['BODY_PART_DEFAULT_W_H'][key] for key in old['UpperBodyTrackingFromPoseKps'].PART_NAMES})

def expected(node,inputs):
    cls=old[node];return getattr(cls(),cls.FUNCTION)(**inputs)

def equal(a,b):
    if isinstance(a,torch.Tensor):assert isinstance(b,torch.Tensor) and a.dtype==b.dtype and a.shape==b.shape and torch.equal(a,b)
    elif isinstance(a,dict):
        assert isinstance(b,dict) and a.keys()==b.keys()
        for key in a:equal(a[key],b[key])
    elif isinstance(a,(tuple,list)):
        assert isinstance(b,(tuple,list)) and len(a)==len(b)
        for x,y in zip(a,b):equal(x,y)
    elif isinstance(a,np.generic):assert a==b
    else:assert a==b

@pytest.mark.parametrize('node',list(converted._pose_algorithms.IMPLEMENTED))
@pytest.mark.parametrize('normalized,missing',[(True,False),(False,False),(True,True)])
def test_source_pure_pixels_tracking_and_direct_mutation(node,normalized,missing):
    inputs=values(node,normalized,missing);oracle=copy.deepcopy(inputs)
    desired=expected(node,oracle)
    async def run():
        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='pose',node_id='1',node_type=node)
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            return (await converted.NODE_CLASS_MAPPINGS[node].execute(**inputs)).result
    actual=asyncio.run(run());equal(actual,desired);equal(inputs,oracle)

@pytest.mark.parametrize('mode',['point','polygon'])
@pytest.mark.parametrize('empty',[False,True])
def test_facial_modes_and_empty_people(mode,empty):
    inputs=values('FacialPartColoringFromPoseKps');inputs['mode']=mode
    if empty:
        for frame in inputs['pose_kps']:frame['people']=[]
    desired=expected('FacialPartColoringFromPoseKps',copy.deepcopy(inputs))
    actual=converted._pose_algorithms.FacialPartColoringFromPoseKps().colorize(**inputs);equal(actual,desired)

def test_native_malformed_and_guard_before_canvas(monkeypatch):
    with pytest.raises(IndexError):converted._pose_algorithms.RenderPeopleKps().render([],True,True,True)
    with pytest.raises(AssertionError):converted._pose_algorithms.RenderAnimalKps().render({'canvas_width':64,'canvas_height':64,'animals':[[1,2]]})
    with pytest.raises(ValueError):converted._pose_algorithms.UpperBodyTrackingFromPoseKps().convert(**dict(values('UpperBodyTrackingFromPoseKps'),id_include='bad'))
    monkeypatch.setattr(converted._pose_algorithms.np,'zeros',lambda *a,**kw:pytest.fail('allocation attempted'))
    inputs=values('RenderPeopleKps');inputs['kps'][0]['canvas_width']=16384;inputs['kps'][0]['canvas_height']=16384
    with pytest.raises(ValueError,match='projected'):converted._pose_bounds.validate(inputs)
    cycle={};cycle['x']=cycle
    with pytest.raises(ValueError,match='cyclic'):converted._pose_bounds.validate(cycle)

def test_four_actual_guests_fresh_roots_outer_custom_tracking(tmp_path):
    names=list(converted._pose_algorithms.IMPLEMENTED);desired={n:expected(n,values(n)) for n in names}
    fresh=tmp_path/'fresh';shutil.copytree(V2,fresh)
    async def run():
        pids=[]
        for index,root in enumerate((V2,fresh)):
            package=load('_many_pose_guest'+str(index),root);refs=_sdk.InProcessRefResolver()
            session=await GuestSession('many-poses',guest_runtime_root=root).start()
            try:
                for node in names:
                    cls=package.NODE_CLASS_MAPPINGS[node]
                    plan=_sdk.ExecutionPlan(prompt_id='pose',node_id=node,node_type=cls.__name__,node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,values(node)),input_mode='values')
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    result=await session.execute(plan,runtime,capabilities=('raw',))
                    actual=(await _sdk.unwrap_outputs(refs,result)).result;equal(actual,desired[node])
                pids.append(session.last_guest_pid)
            finally:await session.kill()
        assert len(set(pids))==2
        loaded=packdb.load_pack(PRISTINE.parent,mount_name='custom_nodes.many_pose_outer')
        class Backend:
            session=None
            async def dispatch(self,plan,local_call,runtime):
                if self.session is None:self.session=await GuestSession('many-pose-outer',guest_runtime_root=V2).start()
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                return await self.session.execute(plan,runtime,capabilities=plan.permissions)
        backend=Backend();previous=_sdk.providers.execution_backend;_sdk.providers.execution_backend=backend
        try:
            for node in names:
                cls=loaded.node_mappings[node]
                result=await execution._async_map_node_over_list('pose-outer',node,cls,{k:[v] for k,v in values(node).items()},cls.FUNCTION)
                equal(result[0].result,desired[node])
        finally:
            _sdk.providers.execution_backend=previous
            if backend.session:await backend.session.kill()
    asyncio.run(run())
