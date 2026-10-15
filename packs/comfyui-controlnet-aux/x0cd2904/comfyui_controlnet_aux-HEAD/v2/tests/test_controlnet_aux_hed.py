"""Reviewed trained HED CPU math/transport; deployment remains pending."""
import ast
import asyncio
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import warnings

import cv2
import numpy as np
import pytest
import torch
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
WEIGHTS=Path(os.environ.get('HED_TEST_WEIGHTS','/tmp/many-oct6-controlnet-aux-hed-982e7ed/ControlNetHED.pth'))


def load(name,root):
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    package=importlib.util.module_from_spec(spec)
    sys.modules[name]=package
    spec.loader.exec_module(package)
    return sys.modules[name+'.nodes']


converted=load('_many_aux_hed',V2)


def lift(path,names,namespace):
    tree=ast.parse((PRISTINE/path).read_text())
    selected=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    assert len(selected)==len(names)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(PRISTINE/path),'exec'),namespace)


def reference(image,node,safe):
    namespace=dict(torch=torch,np=np,cv2=cv2,Image=Image,rearrange=rearrange,warnings=warnings,
                   HF_MODEL_NAME='unused',UPSCALE_METHODS=['INTER_NEAREST','INTER_LINEAR','INTER_AREA','INTER_CUBIC','INTER_LANCZOS4'])
    lift('src/custom_controlnet_aux/util.py',['HWC3','nms','safe_step','safer_memory','pad64','get_upscale_method','resize_image_with_pad','common_input_validate'],namespace)
    lift('src/custom_controlnet_aux/hed/__init__.py',['DoubleConvBlock','ControlNetHED_Apache2','HEDdetector'],namespace)
    class Progress:
        def __init__(self,count): pass
        def update(self,step): pass
    namespace['comfy']=SimpleNamespace(utils=SimpleNamespace(ProgressBar=Progress))
    lift('utils.py',['common_annotator_call'],namespace)
    state=torch.load(WEIGHTS,map_location='cpu',weights_only=True,mmap=False)
    model=namespace['ControlNetHED_Apache2']()
    model.load_state_dict(state,strict=True)
    model.float().eval()
    return namespace['common_annotator_call'](namespace['HEDdetector'](model),image,resolution=64,safe=safe=='enable',scribble=node=='FakeScribblePreprocessor')


@pytest.fixture
def catalogue(tmp_path,monkeypatch):
    assert hashlib.sha256(WEIGHTS.read_bytes()).hexdigest()==converted._hed.WEIGHT.sha256
    root=tmp_path/'controlnet'
    target=root/converted._hed.WEIGHT.catalogue_name
    target.parent.mkdir(parents=True)
    shutil.copyfile(WEIGHTS,target)
    monkeypatch.setitem(folder_paths.folder_names_and_paths,'controlnet',([str(root)],{'.pth'}))
    return target


def values(channels=3,dtype=torch.float32):
    return torch.linspace(0,1,2*24*40*channels,dtype=dtype).reshape(2,24,40,channels)


def test_architecture_and_call_ast_equal_pristine_without_downloader():
    original=ast.parse((PRISTINE/'src/custom_controlnet_aux/hed/__init__.py').read_text())
    new=ast.parse((V2/'_hed_network.py').read_text())
    for name in ('DoubleConvBlock','ControlNetHED_Apache2','HEDdetector'):
        before=next(n for n in original.body if isinstance(n,ast.ClassDef) and n.name==name)
        after=next(n for n in new.body if isinstance(n,ast.ClassDef) and n.name==name)
        if name=='HEDdetector':
            before.body=[m for m in before.body if isinstance(m,ast.FunctionDef) and m.name in ('__init__','__call__')]
        assert ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False)
    for name in ('HEDPreprocessor','FakeScribblePreprocessor'):
        cls=converted.NODE_CLASS_MAPPINGS[name]
        assert cls.SDK_REQUIRED_WEIGHTS==(converted._hed.WEIGHT,)
        assert set(cls.SDK_PERMISSIONS)=={'raw','assets','models.download'}


@pytest.mark.parametrize('node,safe,channels,dtype',[
    ('HEDPreprocessor','enable',3,torch.float32),('HEDPreprocessor','disable',1,torch.float16),
    ('FakeScribblePreprocessor','enable',4,torch.float64),('FakeScribblePreprocessor','disable',3,torch.float32)])
def test_trained_cpu_pixel_parity(catalogue,node,safe,channels,dtype):
    image=values(channels,dtype)
    before=image.clone()
    async def run():
        refs=_sdk.InProcessRefResolver()
        plan=_sdk.ExecutionPlan(prompt_id='hed',node_id='1',node_type=node)
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            return (await converted.NODE_CLASS_MAPPINGS[node].execute(image=image,resolution=64,safe=safe)).result[0]
    actual=asyncio.run(run())
    expected=reference(image,node,safe)
    assert actual.dtype==expected.dtype==torch.float32
    assert actual.shape==expected.shape and torch.equal(actual,expected)
    assert torch.isfinite(actual).all() and torch.equal(image,before)


def test_actual_trained_guest_fresh_roots_and_manifest_outer(catalogue,tmp_path):
    image=values()
    fresh=tmp_path/'fresh'
    shutil.copytree(V2,fresh)
    desired={(node,safe):reference(image,node,safe) for node in ('HEDPreprocessor','FakeScribblePreprocessor') for safe in ('enable','disable')}
    async def run():
        pids=[]
        for index,root in enumerate((V2,fresh)):
            package=load('_many_hed_guest'+str(index),root)
            session=await GuestSession('many-aux-hed',guest_runtime_root=root).start()
            refs=_sdk.InProcessRefResolver()
            try:
                for (node,safe),expected in desired.items():
                    cls=package.NODE_CLASS_MAPPINGS[node]
                    inputs=dict(image=image,resolution=64,safe=safe)
                    plan=_sdk.ExecutionPlan(prompt_id='hed',node_id=node,node_type=cls.__name__,node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,inputs),input_mode='values')
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    result=await session.execute(plan,runtime,capabilities=('raw','assets','models.download'))
                    actual=await refs.resolve(result.result[0])
                    assert torch.equal(actual,expected)
                    for caps in (('raw',),('assets',)):
                        with pytest.raises(Exception,match='assets|raw'):
                            await session.execute(plan,runtime,capabilities=caps)
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids))==2 and os.getpid() not in pids
        loaded=packdb.load_pack(PRISTINE.parent,mount_name='custom_nodes.many_hed_outer')
        class Backend:
            session=None
            async def dispatch(self,plan,local_call,runtime):
                if self.session is None:
                    self.session=await GuestSession('many-hed-outer',guest_runtime_root=V2).start()
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                return await self.session.execute(plan,runtime,capabilities=plan.permissions)
        backend=Backend()
        previous=_sdk.providers.execution_backend
        _sdk.providers.execution_backend=backend
        try:
            for (node,safe),expected in desired.items():
                cls=loaded.node_mappings[node]
                result=await execution._async_map_node_over_list('hed-outer',node,cls,{'image':[image],'resolution':[64],'safe':[safe]},cls.FUNCTION)
                assert isinstance(result[0].result[0],torch.Tensor) and torch.equal(result[0].result[0],expected)
        finally:
            _sdk.providers.execution_backend=previous
            if backend.session: await backend.session.kill()
    asyncio.run(run())


def test_digest_and_projected_network_guard_precede_model_load(catalogue,monkeypatch):
    monkeypatch.setattr(converted._hed,'ControlNetHED_Apache2',lambda:pytest.fail('model constructed'))
    async def run():
        refs=_sdk.InProcessRefResolver()
        plan=_sdk.ExecutionPlan(prompt_id='bad-hed',node_id='1',node_type='HEDPreprocessor')
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            with pytest.raises(ValueError,match='projected'):
                await converted.NODE_CLASS_MAPPINGS['HEDPreprocessor'].execute(image=values(),resolution=4096,safe='enable')
            catalogue.write_bytes(b'corrupt')
            with pytest.raises(ValueError,match='digest'):
                await converted.NODE_CLASS_MAPPINGS['HEDPreprocessor'].execute(image=values(),resolution=64,safe='enable')
    asyncio.run(run())
