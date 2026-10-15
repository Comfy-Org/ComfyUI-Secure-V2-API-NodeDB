"""Trained source-wrapper CPU/guest comparisons; operator catalogue fixture."""
import ast
import asyncio
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace,ModuleType
import warnings
from enum import Enum

import cv2
import numpy as np
import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F
from einops import rearrange
from PIL import Image

CORE=Path(os.environ.get('COMFY_CORE_ROOT','/Users/ben/comfy/ComfyUI-secure-nodes'))
OVERLAY=Path('/Users/ben/comfy/ComfyUI_secure_nodes')
sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
import execution
import folder_paths

V2=Path(__file__).resolve().parents[1]
PRISTINE=V2.parent
WEIGHTS=Path('/tmp/many-oct6-controlnet-aux-edges-982e7ed')

def load(name,root):
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    package=importlib.util.module_from_spec(spec)
    sys.modules[name]=package
    spec.loader.exec_module(package)
    return sys.modules[name+'.nodes']

converted=load('_many_aux_edges_test',V2)

def lifted(path,names,namespace,assignments=False):
    tree=ast.parse((PRISTINE/path).read_text())
    body=[n for n in tree.body if (isinstance(n,(ast.FunctionDef,ast.ClassDef)) and (names is None or n.name in names)) or (assignments and isinstance(n,ast.Assign))]
    exec(compile(ast.Module(body=body,type_ignores=[]),str(PRISTINE/path),'exec'),namespace)

def reference(image,node,options):
    import math
    namespace=dict(torch=torch,nn=nn,F=F,np=np,cv2=cv2,Image=Image,rearrange=rearrange,warnings=warnings,math=math,Enum=Enum,MAX_RESOLUTION=16384,
                   HF_MODEL_NAME='lllyasviel/Annotators',UPSCALE_METHODS=['INTER_NEAREST','INTER_LINEAR','INTER_AREA','INTER_CUBIC','INTER_LANCZOS4'])
    lifted('src/custom_controlnet_aux/util.py',['HWC3','nms','safe_step','safer_memory','pad64','get_upscale_method','resize_image_with_pad','common_input_validate'],namespace)
    # Provision identity and device-policy doubles only: exact trained state/math.
    namespace['custom_hf_download']=lambda repo,filename,**kwargs:str(WEIGHTS/filename)
    namespace['model_management']=SimpleNamespace(get_torch_device=lambda:torch.device('cpu'))
    class Progress:
        def __init__(self,count): pass
        def update(self,step): pass
    namespace['comfy']=SimpleNamespace(utils=SimpleNamespace(ProgressBar=Progress))
    lifted('utils.py',['common_annotator_call','INPUT','define_preprocessor_inputs'],namespace)
    if node=='M-LSDPreprocessor':
        lifted('src/custom_controlnet_aux/mlsd/models/mbv2_mlsd_large.py',None,namespace)
        lifted('src/custom_controlnet_aux/mlsd/utils.py',['deccode_output_score_and_ptss','pred_lines'],namespace)
        lifted('src/custom_controlnet_aux/mlsd/__init__.py',['MLSDdetector'],namespace)
        name='custom_controlnet_aux.mlsd';detector='MLSDdetector';wrapper='MLSD_Preprocessor';path='node_wrappers/mlsd.py'
    else:
        lifted('src/custom_controlnet_aux/pidi/model.py',None,namespace,assignments=True)
        lifted('src/custom_controlnet_aux/pidi/__init__.py',['PidiNetDetector'],namespace)
        name='custom_controlnet_aux.pidi';detector='PidiNetDetector'
        if node=='PiDiNetPreprocessor': wrapper='PIDINET_Preprocessor';path='node_wrappers/pidinet.py'
        else: wrapper='Scribble_PiDiNet_Preprocessor';path='node_wrappers/scribble.py'
    module=ModuleType(name);setattr(module,detector,namespace[detector])
    previous=sys.modules.get(name)
    sys.modules[name]=module
    try:
        lifted(path,[wrapper],namespace)
        return namespace[wrapper]().execute(image=image,resolution=64,**options)[0]
    finally:
        if previous is None: sys.modules.pop(name,None)
        else: sys.modules[name]=previous

@pytest.fixture
def catalogue(tmp_path,monkeypatch):
    root=tmp_path/'controlnet'
    for weight in (converted._edges.PIDI,converted._edges.MLSD):
        source=WEIGHTS/weight.filename
        assert hashlib.sha256(source.read_bytes()).hexdigest()==weight.sha256
        target=root/weight.catalogue_name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    monkeypatch.setitem(folder_paths.folder_names_and_paths,'controlnet',([str(root)],{'.pth'}))
    return root

CASES=[('PiDiNetPreprocessor',{'safe':'enable'},3,torch.float32),
       ('PiDiNetPreprocessor',{'safe':'disable'},1,torch.float16),
       ('Scribble_PiDiNet_Preprocessor',{'safe':'enable'},4,torch.float64),
       ('Scribble_PiDiNet_Preprocessor',{'safe':'disable'},3,torch.float32),
       ('M-LSDPreprocessor',{'score_threshold':0.1,'dist_threshold':0.1},3,torch.float32),
       ('M-LSDPreprocessor',{'score_threshold':1.9,'dist_threshold':19.0},4,torch.float64)]

def image_values(channels=3,dtype=torch.float32):
    return torch.linspace(0,1,2*24*40*channels,dtype=dtype).reshape(2,24,40,channels)

@pytest.mark.parametrize('node,options,channels,dtype',CASES)
def test_trained_original_wrapper_cpu_pixels(catalogue,node,options,channels,dtype):
    image=image_values(channels,dtype);before=image.clone()
    expected=reference(image,node,options)
    async def run():
        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='edges',node_id='1',node_type=node)
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            return (await converted.NODE_CLASS_MAPPINGS[node].execute(image=image,resolution=64,**options)).result[0]
    actual=asyncio.run(run())
    assert actual.dtype==expected.dtype and actual.shape==expected.shape and torch.equal(actual,expected)
    assert torch.isfinite(actual).all() and torch.equal(image,before)

def test_exact_architecture_and_detector_ast():
    for source,target in [('pidi/model.py','_pidi_model.py'),('mlsd/models/mbv2_mlsd_large.py','_mlsd_model.py')]:
        old=ast.parse((PRISTINE/'src/custom_controlnet_aux'/source).read_text())
        new=ast.parse((V2/target).read_text())
        for node in new.body:
            if not isinstance(node,(ast.FunctionDef,ast.ClassDef)):continue
            before=next(n for n in old.body if type(n)==type(node) and n.name==node.name)
            if node.name=='MobileNetV2':
                # The unused pretrained=True downloader is deliberately refused.
                before.body=[m for m in before.body if not (isinstance(m,ast.FunctionDef) and m.name=='_load_pretrained_model')]
                node.body=[m for m in node.body if not (isinstance(m,ast.FunctionDef) and m.name=='_load_pretrained_model')]
            assert ast.dump(before,include_attributes=False)==ast.dump(node,include_attributes=False)
    for source,name in [('pidi/__init__.py','PidiNetDetector'),('mlsd/__init__.py','MLSDdetector')]:
        old=ast.parse((PRISTINE/'src/custom_controlnet_aux'/source).read_text())
        new=ast.parse((V2/'_edge_networks.py').read_text())
        before=next(n for n in old.body if isinstance(n,ast.ClassDef) and n.name==name)
        before.body=[m for m in before.body if isinstance(m,ast.FunctionDef) and m.name in ('__init__','__call__')]
        after=next(n for n in new.body if isinstance(n,ast.ClassDef) and n.name==name)
        assert ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False)

def test_trained_networks_strict_forward_not_swallowed_by_mlsd_wrapper():
    pidi=converted._edges.pidinet();state=torch.load(WEIGHTS/'table5_pidinet.pth',weights_only=True,map_location='cpu')['state_dict']
    pidi.load_state_dict({k.replace('module.',''):v for k,v in state.items()},strict=True);pidi.eval()
    mlsd=converted._edges.MobileV2_MLSD_Large();mlsd.load_state_dict(torch.load(WEIGHTS/'mlsd_large_512_fp32.pth',weights_only=True,map_location='cpu'),strict=True);mlsd.eval()
    with torch.inference_mode():
        result=pidi(torch.linspace(0,1,3*64*64).reshape(1,3,64,64))
        lines=mlsd(torch.linspace(-1,1,4*64*64).reshape(1,4,64,64))
    assert len(result)==5 and all(torch.isfinite(t).all() for t in result)
    assert lines.shape[1]>=5 and torch.isfinite(lines).all()

def test_actual_guests_and_outer_all_three_nodes(catalogue,tmp_path):
    image=image_values();cases=[(node,options) for node,options,_,_ in CASES]
    expected=[reference(image,node,options) for node,options in cases]
    fresh=tmp_path/'fresh';shutil.copytree(V2,fresh)
    async def run():
        pids=[]
        for index,root in enumerate((V2,fresh)):
            package=load('_many_edges_guest'+str(index),root)
            session=await GuestSession('many-edges',guest_runtime_root=root).start();refs=_sdk.InProcessRefResolver()
            try:
                for (node,options),desired in zip(cases,expected):
                    cls=package.NODE_CLASS_MAPPINGS[node]
                    plan=_sdk.ExecutionPlan(prompt_id='edge',node_id=node,node_type=cls.__name__,node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,dict(image=image,resolution=64,**options)),input_mode='values')
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    result=await session.execute(plan,runtime,capabilities=cls.SDK_PERMISSIONS)
                    actual=await refs.resolve(result.result[0]);assert torch.equal(actual,desired)
                    for caps in (('raw',),('assets',)):
                        with pytest.raises(Exception,match='raw|assets'):await session.execute(plan,runtime,capabilities=caps)
                pids.append(session.last_guest_pid)
            finally:await session.kill()
        assert len(set(pids))==2
        loaded=packdb.load_pack(PRISTINE.parent,mount_name='custom_nodes.many_edges_outer')
        class Backend:
            session=None
            async def dispatch(self,plan,local_call,runtime):
                if self.session is None:self.session=await GuestSession('many-edges-outer',guest_runtime_root=V2).start()
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                return await self.session.execute(plan,runtime,capabilities=plan.permissions)
        backend=Backend();previous=_sdk.providers.execution_backend;_sdk.providers.execution_backend=backend
        try:
            for (node,options),desired in zip(cases,expected):
                cls=loaded.node_mappings[node]
                inputs={k:[v] for k,v in dict(image=image,resolution=64,**options).items()}
                result=await execution._async_map_node_over_list('edges-outer',node,cls,inputs,cls.FUNCTION)
                assert isinstance(result[0].result[0],torch.Tensor) and torch.equal(result[0].result[0],desired)
        finally:
            _sdk.providers.execution_backend=previous
            if backend.session:await backend.session.kill()
    asyncio.run(run())

def test_projected_bounds_and_digest_before_model(catalogue,monkeypatch):
    monkeypatch.setattr(converted._edges,'pidinet',lambda:pytest.fail('constructor ran'))
    async def run():
        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='edge-deny',node_id='1',node_type='PiDiNetPreprocessor')
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            with pytest.raises(ValueError,match='projected'):
                await converted.NODE_CLASS_MAPPINGS['PiDiNetPreprocessor'].execute(image=image_values(),resolution=4096,safe='enable')
            (catalogue/converted._edges.PIDI.catalogue_name).write_bytes(b'corrupt')
            with pytest.raises(ValueError,match='digest'):
                await converted.NODE_CLASS_MAPPINGS['PiDiNetPreprocessor'].execute(image=image_values(),resolution=64,safe='enable')
    asyncio.run(run())
