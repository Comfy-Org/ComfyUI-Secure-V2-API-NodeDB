"""Exact trained line-art CPU behavior with restricted managed tensors."""
import ast
import asyncio
import functools
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
import torch
from einops import rearrange
from PIL import Image

V2=Path(__file__).resolve().parents[1];PRISTINE=V2.parent
CORE=Path(os.environ.get('COMFY_CORE_ROOT','/Users/ben/comfy/ComfyUI-secure-nodes'))
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
import execution
import folder_paths
WEIGHTS=Path('/tmp/many-oct6-controlnet-aux-lineart-982e7ed')


def load(name,root):
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    package=importlib.util.module_from_spec(spec);sys.modules[name]=package;spec.loader.exec_module(package)
    return sys.modules[name+'.nodes']


converted=load('_many_aux_lineart',V2)


def lift(path,names,namespace):
    tree=ast.parse((PRISTINE/path).read_text())
    selected=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    assert len(selected)==len(names)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(PRISTINE/path),'exec'),namespace)


def reference(value,node,coarse):
    scope=dict(torch=torch,nn=torch.nn,np=np,cv2=cv2,Image=Image,rearrange=rearrange,functools=functools,HF_MODEL_NAME='unused',norm_layer=torch.nn.InstanceNorm2d)
    scope['UPSCALE_METHODS']=['INTER_NEAREST','INTER_LINEAR','INTER_AREA','INTER_CUBIC','INTER_LANCZOS4']
    lift('src/custom_controlnet_aux/util.py',['HWC3','safer_memory','pad64','get_upscale_method','resize_image_with_pad','common_input_validate'],scope)
    class Progress:
        def __init__(self,count):pass
        def update(self,step):pass
    scope['comfy']=SimpleNamespace(utils=SimpleNamespace(ProgressBar=Progress))
    lift('utils.py',['common_annotator_call'],scope)
    def read(name):return torch.load(WEIGHTS/name,map_location='cpu',weights_only=True,mmap=False)
    if node=='LineArtPreprocessor':
        lift('src/custom_controlnet_aux/lineart/__init__.py',['ResidualBlock','Generator','LineartDetector'],scope)
        fine=scope['Generator'](3,1,3);fine.load_state_dict(read('sk_model.pth'),strict=True);fine.eval()
        other=scope['Generator'](3,1,3);other.load_state_dict(read('sk_model2.pth'),strict=True);other.eval()
        return scope['common_annotator_call'](scope['LineartDetector'](fine,other),value,resolution=64,coarse=coarse=='enable')
    lift('src/custom_controlnet_aux/lineart_anime/__init__.py',['UnetGenerator','UnetSkipConnectionBlock','LineartAnimeDetector'],scope)
    state=read('netG.pth')
    for key in list(state):
        if 'module.' in key:state[key.replace('module.','')]=state.pop(key)
    norm=functools.partial(torch.nn.InstanceNorm2d,affine=False,track_running_stats=False)
    network=scope['UnetGenerator'](3,1,8,64,norm_layer=norm,use_dropout=False);network.load_state_dict(state,strict=True);network.eval()
    return scope['common_annotator_call'](scope['LineartAnimeDetector'](network),value,resolution=64)


@pytest.fixture
def catalogue(tmp_path,monkeypatch):
    root=tmp_path/'controlnet'
    for declaration in (converted._lineart.FINE,converted._lineart.COARSE,converted._lineart.ANIME):
        source=WEIGHTS/declaration.filename
        assert hashlib.file_digest(source.open('rb'),'sha256').hexdigest()==declaration.sha256
        target=root/declaration.catalogue_name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    monkeypatch.setitem(folder_paths.folder_names_and_paths,'controlnet',([str(root)],{'.pth'}))
    return root


def inputs(node,coarse='disable',channels=3,dtype=torch.float32):
    value=torch.linspace(0,1,24*40*channels,dtype=dtype).reshape(1,24,40,channels)
    fields=dict(image=value,resolution=64)
    if node=='LineArtPreprocessor':fields['coarse']=coarse
    return fields


def test_architecture_and_detector_math_ast_exact():
    for family,detector in (('lineart','LineartDetector'),('lineart_anime','LineartAnimeDetector')):
        original=ast.parse((PRISTINE/'src/custom_controlnet_aux'/family/'__init__.py').read_text())
        new=ast.parse((V2/('_'+family+'_network.py')).read_text())
        for before in (n for n in original.body if isinstance(n,ast.ClassDef)):
            after=next(n for n in new.body if isinstance(n,ast.ClassDef) and n.name==before.name)
            if before.name==detector:before.body=[m for m in before.body if isinstance(m,ast.FunctionDef) and m.name in ('__init__','__call__')]
            assert ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False)
    for node,weights in converted._lineart.WEIGHTS.items():assert converted.NODE_CLASS_MAPPINGS[node].SDK_REQUIRED_WEIGHTS==weights


@pytest.mark.parametrize('node,coarse,channels,dtype',[
    ('LineArtPreprocessor','disable',3,torch.float32),('LineArtPreprocessor','enable',4,torch.float16),
    ('AnimeLineArtPreprocessor','disable',1,torch.float64),('AnimeLineArtPreprocessor','disable',3,torch.float32)])
def test_trained_pixels(catalogue,node,coarse,channels,dtype):
    fields=inputs(node,coarse,channels,dtype);before=fields['image'].clone()
    async def run():
        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='lineart',node_id='1',node_type=node)
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):return (await converted.NODE_CLASS_MAPPINGS[node].execute(**fields)).result[0]
    actual=asyncio.run(run());expected=reference(fields['image'],node,coarse)
    assert torch.equal(actual,expected) and actual.dtype==expected.dtype==torch.float32
    assert torch.isfinite(actual).all() and torch.equal(fields['image'],before)


def test_actual_guests_and_declared_outer_images(catalogue,tmp_path):
    cases=[(node,coarse,inputs(node,coarse)) for node,coarse in [('LineArtPreprocessor','disable'),('LineArtPreprocessor','enable'),('AnimeLineArtPreprocessor','disable')]]
    expected={(node,coarse):reference(fields['image'],node,coarse) for node,coarse,fields in cases}
    fresh=tmp_path/'fresh';shutil.copytree(V2,fresh)
    async def run():
        pids=[]
        for index,root in enumerate((V2,fresh)):
            nodes=load('_many_lineart_guest'+str(index),root);session=await GuestSession('many-lineart',guest_runtime_root=root).start();refs=_sdk.InProcessRefResolver()
            try:
                for node,coarse,fields in cases:
                    cls=nodes.NODE_CLASS_MAPPINGS[node];plan=_sdk.ExecutionPlan(prompt_id='lineart',node_id=node,node_type=cls.__name__,node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,fields),input_mode='values')
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    result=await session.execute(plan,runtime,capabilities=cls.SDK_PERMISSIONS)
                    assert torch.equal(await refs.resolve(result.result[0]),expected[node,coarse])
                    for caps in (('raw',),('assets',)):
                        with pytest.raises(Exception,match='raw|assets'):await session.execute(plan,runtime,capabilities=caps)
                pids.append(session.last_guest_pid)
            finally:await session.kill()
        assert len(set(pids))==2 and os.getpid() not in pids
        loaded=packdb.load_pack(PRISTINE.parent,mount_name='custom_nodes.many_lineart_outer')
        class Backend:
            session=None
            async def dispatch(self,plan,local_call,runtime):
                if self.session is None:self.session=await GuestSession('many-lineart-outer',guest_runtime_root=V2).start()
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                return await self.session.execute(plan,runtime,capabilities=plan.permissions)
        backend=Backend();previous=_sdk.providers.execution_backend;_sdk.providers.execution_backend=backend
        try:
            for node,coarse,fields in cases:
                cls=loaded.node_mappings[node]
                result=await execution._async_map_node_over_list('lineart-outer',node,cls,{k:[v] for k,v in fields.items()},cls.FUNCTION)
                assert isinstance(result[0].result[0],torch.Tensor) and torch.equal(result[0].result[0],expected[node,coarse])
        finally:
            _sdk.providers.execution_backend=previous
            if backend.session:await backend.session.kill()
    asyncio.run(run())


def test_digest_and_projected_guards_precede_constructor(catalogue,monkeypatch):
    monkeypatch.setattr(converted._lineart,'Generator',lambda *a,**k:pytest.fail('generator constructed'))
    monkeypatch.setattr(converted._lineart,'UnetGenerator',lambda *a,**k:pytest.fail('anime constructed'))
    async def run():
        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='bad-lineart',node_id='1',node_type='LineArtPreprocessor')
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            for node in converted._lineart.WEIGHTS:
                fields=inputs(node);fields['resolution']=4096
                with pytest.raises(ValueError,match='projected'):await converted.NODE_CLASS_MAPPINGS[node].execute(**fields)
                declaration=converted._lineart.WEIGHTS[node][0];(catalogue/declaration.catalogue_name).write_bytes(b'corrupt')
                with pytest.raises(ValueError,match='digest'):await converted.NODE_CLASS_MAPPINGS[node].execute(**inputs(node))
    asyncio.run(run())
