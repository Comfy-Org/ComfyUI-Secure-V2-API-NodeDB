"""Trained TEED CPU parity; managed provision and deployment stay separate."""
import ast
import asyncio
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
WEIGHTS=Path('/tmp/many-oct6-controlnet-aux-teed-67006a3/7_model.pth')


def load(name,root):
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    package=importlib.util.module_from_spec(spec);sys.modules[name]=package
    spec.loader.exec_module(package)
    return sys.modules[name+'.nodes']


converted=load('_many_aux_teed',V2)


def lift(path,names,namespace):
    tree=ast.parse((PRISTINE/path).read_text())
    selected=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    assert len(selected)==len(names)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(PRISTINE/path),'exec'),namespace)


def original_network():
    path=PRISTINE/'src/custom_controlnet_aux/teed/Fsmish.py'
    spec=importlib.util.spec_from_file_location('_many_pristine_teed_smish',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    namespace=dict(torch=torch,nn=torch.nn,F=torch.nn.functional,Fsmish=module.smish,smish=module.smish,np=np,cv2=cv2,Image=Image,rearrange=rearrange)
    lift('src/custom_controlnet_aux/teed/Xsmish.py',['Smish'],namespace)
    tree=ast.parse((PRISTINE/'src/custom_controlnet_aux/teed/ted.py').read_text())
    names=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
    lift('src/custom_controlnet_aux/teed/ted.py',names,namespace)
    lift('src/custom_controlnet_aux/util.py',['HWC3','safe_step','safer_memory','pad64','get_upscale_method','resize_image_with_pad','common_input_validate'],namespace)
    namespace['UPSCALE_METHODS']=['INTER_NEAREST','INTER_LINEAR','INTER_AREA','INTER_CUBIC','INTER_LANCZOS4']
    namespace['BDS_MODEL_NAME']='unused'
    lift('src/custom_controlnet_aux/teed/__init__.py',['TEDDetector'],namespace)
    class Progress:
        def __init__(self,count):pass
        def update(self,step):pass
    namespace['comfy']=SimpleNamespace(utils=SimpleNamespace(ProgressBar=Progress))
    lift('utils.py',['common_annotator_call'],namespace)
    network=namespace['TED']()
    network.load_state_dict(torch.load(WEIGHTS,map_location='cpu',weights_only=True,mmap=False),strict=True)
    network.float().eval()
    return namespace,network


def reference(image,steps):
    namespace,network=original_network()
    return namespace['common_annotator_call'](namespace['TEDDetector'](network),image,resolution=64,safe_steps=steps)


@pytest.fixture
def catalogue(tmp_path,monkeypatch):
    assert hashlib.sha256(WEIGHTS.read_bytes()).hexdigest()==converted._teed.WEIGHT.sha256
    target=tmp_path/'controlnet'/converted._teed.WEIGHT.catalogue_name
    target.parent.mkdir(parents=True);shutil.copyfile(WEIGHTS,target)
    monkeypatch.setitem(folder_paths.folder_names_and_paths,'controlnet',([str(tmp_path/'controlnet')],{'.pth'}))
    return target


def image(channels=3,dtype=torch.float32):
    return torch.linspace(0,1,2*24*40*channels,dtype=dtype).reshape(2,24,40,channels)


def test_pinned_math_ast_and_declaration():
    new=ast.parse((V2/'_teed_network.py').read_text())
    for filename in ('Fsmish.py','Xsmish.py','ted.py','__init__.py'):
        original=ast.parse((PRISTINE/'src/custom_controlnet_aux/teed'/filename).read_text())
        for before in (n for n in original.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))):
            after=next(n for n in new.body if isinstance(n,type(before)) and n.name==before.name)
            if before.name=='smish':before.decorator_list=[]
            if before.name=='TEDDetector':before.body=[m for m in before.body if isinstance(m,ast.FunctionDef) and m.name in ('__init__','__call__')]
            assert ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False)
    cls=converted.NODE_CLASS_MAPPINGS['TEEDPreprocessor']
    assert cls.SDK_REQUIRED_WEIGHTS==(converted._teed.WEIGHT,)
    assert set(cls.SDK_PERMISSIONS)=={'raw','assets','models.download'}


def test_trained_logits_match_original_jit_before_pixel_quantization():
    _,original=original_network()
    new=converted._teed.TED()
    new.load_state_dict(torch.load(WEIGHTS,map_location='cpu',weights_only=True,mmap=False),strict=True)
    new.float().eval()
    with torch.no_grad():
        for h,w in ((64,64),(64,128)):
            value=torch.linspace(0,255,3*h*w).reshape(1,3,h,w)
            expected,actual=original(value),new(value)
            assert len(expected)==len(actual)
            for before,after in zip(expected,actual):
                assert torch.equal(before,after) and torch.isfinite(after).all()


@pytest.mark.parametrize('steps,channels,dtype',[(0,3,torch.float32),(2,1,torch.float16),(10,4,torch.float64),(1,3,torch.float32)])
def test_trained_original_jit_pixel_parity(catalogue,steps,channels,dtype):
    value=image(channels,dtype);before=value.clone()
    async def run():
        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='teed',node_id='1',node_type='TEEDPreprocessor')
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            return (await converted.NODE_CLASS_MAPPINGS['TEEDPreprocessor'].execute(image=value,resolution=64,safe_steps=steps)).result[0]
    actual=asyncio.run(run());expected=reference(value,steps)
    assert torch.equal(actual,expected) and actual.dtype==expected.dtype==torch.float32
    assert torch.isfinite(actual).all() and torch.equal(value,before)


def test_real_trained_guest_fresh_roots_and_public_outer(catalogue,tmp_path):
    value=image();fresh=tmp_path/'fresh';shutil.copytree(V2,fresh)
    desired={steps:reference(value,steps) for steps in (0,2,10)}
    async def run():
        pids=[]
        for index,root in enumerate((V2,fresh)):
            nodes=load('_many_teed_guest'+str(index),root);cls=nodes.NODE_CLASS_MAPPINGS['TEEDPreprocessor']
            session=await GuestSession('many-teed',guest_runtime_root=root).start();refs=_sdk.InProcessRefResolver()
            try:
                for steps,expected in desired.items():
                    inputs=dict(image=value,resolution=64,safe_steps=steps)
                    plan=_sdk.ExecutionPlan(prompt_id='teed',node_id='teed',node_type=cls.__name__,node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,inputs),input_mode='values')
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    result=await session.execute(plan,runtime,capabilities=cls.SDK_PERMISSIONS)
                    assert torch.equal(await refs.resolve(result.result[0]),expected)
                    for caps in (('raw',),('assets',)):
                        with pytest.raises(Exception,match='raw|assets'):await session.execute(plan,runtime,capabilities=caps)
                pids.append(session.last_guest_pid)
            finally:await session.kill()
        assert len(set(pids))==2 and os.getpid() not in pids
        loaded=packdb.load_pack(PRISTINE.parent,mount_name='custom_nodes.many_teed_outer')
        class Backend:
            session=None
            async def dispatch(self,plan,local_call,runtime):
                if self.session is None:self.session=await GuestSession('many-teed-outer',guest_runtime_root=V2).start()
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                return await self.session.execute(plan,runtime,capabilities=plan.permissions)
        backend=Backend();previous=_sdk.providers.execution_backend;_sdk.providers.execution_backend=backend
        try:
            cls=loaded.node_mappings['TEEDPreprocessor']
            for steps,expected in desired.items():
                output=await execution._async_map_node_over_list('teed-outer','1',cls,{'image':[value],'resolution':[64],'safe_steps':[steps]},cls.FUNCTION)
                assert isinstance(output[0].result[0],torch.Tensor) and torch.equal(output[0].result[0],expected)
        finally:
            _sdk.providers.execution_backend=previous
            if backend.session:await backend.session.kill()
    asyncio.run(run())


def test_digest_and_work_guards_before_constructor(catalogue,monkeypatch):
    monkeypatch.setattr(converted._teed,'TED',lambda:pytest.fail('network constructed'))
    async def run():
        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='bad-teed',node_id='1',node_type='TEEDPreprocessor')
        with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
            with pytest.raises(ValueError,match='projected'):await converted.NODE_CLASS_MAPPINGS['TEEDPreprocessor'].execute(image=image(),resolution=4096,safe_steps=2)
            catalogue.write_bytes(b'corrupt')
            with pytest.raises(ValueError,match='digest'):await converted.NODE_CLASS_MAPPINGS['TEEDPreprocessor'].execute(image=image(),resolution=64,safe_steps=2)
    asyncio.run(run())
