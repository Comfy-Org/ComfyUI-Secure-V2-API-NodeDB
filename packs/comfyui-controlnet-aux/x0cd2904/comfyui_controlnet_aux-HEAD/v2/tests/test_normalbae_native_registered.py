"""Future genuine native/registered NormalBAE gate. Source authoring never runs it.

Retained native timm/Torch networks and source preprocessing are independent
of the converted modules. Only native file acquisition consumes preverified
restricted checkpoint data. No fake model, SDK, RPC or source fallback.
"""
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import types
import warnings

import cv2
import numpy as np
import pytest
import torch
import torchvision.transforms as transforms
from PIL import Image
from einops import rearrange
import comfy.model_management as model_management
import comfy.utils
import execution
from comfy.cli_args import args
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT=Path(__file__).resolve().parents[1]
PRISTINE=Path(os.environ['AMY_AUX_PRISTINE'])
NODE_ID='BAE-NormalMapPreprocessor'
PREFIX='src/custom_controlnet_aux/normalbae/'

def lift(path,ns,names=None,transform=None):
    source=(PRISTINE/path).read_text()
    tree=ast.parse(source)
    body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and (names is None or n.name in names)]
    assert body
    if transform: body=[transform.visit(n) for n in body]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(PRISTINE/path),'exec'),ns)

def native_oracle(raw_checkpoint,asset_path):
    def custom_hf_download(repo,filename):
        assert repo=='lllyasviel/Annotators' and filename=='scannet.pt'
        return str(asset_path)
    ns=dict(torch=torch,nn=torch.nn,F=torch.nn.functional,np=np,cv2=cv2,
            Image=Image,rearrange=rearrange,transforms=transforms,types=types,
            warnings=warnings,model_management=model_management,comfy=comfy,
            custom_hf_download=custom_hf_download,HF_MODEL_NAME='lllyasviel/Annotators',
            raw_checkpoint=raw_checkpoint,
            UPSCALE_METHODS=['INTER_NEAREST','INTER_LINEAR','INTER_AREA','INTER_CUBIC','INTER_LANCZOS4'])
    lift('src/custom_controlnet_aux/util.py',ns,
         ['HWC3','safer_memory','pad64','get_upscale_method','resize_image_with_pad','common_input_validate'])
    lift(PREFIX+'nets/submodules/submodules.py',ns)
    lift(PREFIX+'nets/submodules/encoder.py',ns,['Encoder'])
    lift(PREFIX+'nets/submodules/decoder.py',ns,['Decoder'])
    lift(PREFIX+'nets/NNET.py',ns,['NNET'])
    class RestrictedNativeAcquisition(ast.NodeTransformer):
        def visit_Call(self,node):
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='torch' and node.func.attr=='load':
                return ast.Name(id='raw_checkpoint',ctx=ast.Load())
            return self.generic_visit(node)
    lift(PREFIX+'__init__.py',ns,['load_checkpoint','NormalBaeDetector'],transform=RestrictedNativeAcquisition())
    lift('utils.py',ns,['common_annotator_call'])
    class WrapperImport(ast.NodeTransformer):
        def visit_ImportFrom(self,node): return None
    lift('node_wrappers/normalbae.py',ns,['BAE_Normal_Map_Preprocessor'],transform=WrapperImport())
    return ns['BAE_Normal_Map_Preprocessor']()

def verify_checkpoint(selection,receipt):
    path=Path(receipt['native_checkpoint_path'])
    assert path.stat().st_size==selection['bytes']
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
    assert digest.hexdigest()==selection['sha256']
    raw=torch.load(path,map_location='cpu',weights_only=True)
    assert isinstance(raw,dict)
    assert list(raw)==selection['raw_top_level_keys']
    assert 'model' in raw and 'state_dict' not in raw
    model=raw['model']
    assert isinstance(model,dict) and model
    shape_bytes=Path(receipt['restricted_shape_evidence_path']).read_bytes()
    assert hashlib.sha256(shape_bytes).hexdigest()==selection['restricted_shape_evidence_sha256']
    shape=json.loads(shape_bytes)
    assert shape['asset_sha256']==selection['sha256']
    assert shape['raw_top_level_keys']==list(raw)
    assert shape['restricted_weights_only'] is True
    assert shape['actual_inspection'] is True
    # Run the actual selected public reader, not a fixture implementation.
    published=comfy.utils.load_torch_file(str(path),safe_load=True)
    if selection['load_state_contract']=='model-only-unwrapped':
        assert list(raw)==['model']
        returned=published
    else:
        assert selection['load_state_contract']=='nested-model-retained' and len(raw)>1
        returned=published['model']
    assert isinstance(returned,dict) and list(returned)==list(model)
    total=0
    for name,value in model.items():
        assert isinstance(name,str) and isinstance(value,torch.Tensor)
        assert value.device.type=='cpu' and value.layout==torch.strided
        assert type(returned[name]) is torch.Tensor
        assert returned[name].dtype==value.dtype and returned[name].shape==value.shape
        assert torch.equal(returned[name],value)
        total+=value.numel()*value.element_size()
    assert total<=512*1024*1024
    return raw,path

def test_actual_native_registered_normalbae_loader_math_errors_and_recovery():
    receipt_bytes=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(receipt_bytes).hexdigest()==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    receipt=json.loads(receipt_bytes)
    assert receipt['authorized'] is True and receipt['execution_owner']=='chat_f38536805264'
    assert receipt['node_id']==NODE_ID
    for field in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256'):
        assert isinstance(receipt[field],str) and len(receipt[field])==64
    assert hashlib.sha256((ROOT/'secure-nodes.json').read_bytes()).hexdigest()==receipt['manifest_sha256']
    asset_bytes=(ROOT/'_normalbae/asset-selection.json').read_bytes()
    assert hashlib.sha256(asset_bytes).hexdigest()==receipt['asset_selection_sha256']
    selection=json.loads(asset_bytes)
    assert selection['approved'] is True
    assert receipt['selected_utils_source_sha256']==selection['published_loader_source_sha256']
    # Bind the genuinely loaded public reader's complete source file identity.
    assert hashlib.sha256(Path(comfy.utils.__file__).read_bytes()).hexdigest()==selection['published_loader_source_sha256']
    source=json.loads((ROOT/'_normalbae/native-sources.json').read_text())
    assert source['source_pin']=='0cd290477128d42cdc3e76a826a402d866e8c684'
    assert receipt['native_source_hashes']==source['hashes']
    for name,digest in source['hashes'].items():
        assert hashlib.sha256((PRISTINE/name).read_bytes()).hexdigest()==digest
    assert args.cpu is True and model_management.get_torch_device().type=='cpu'
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    raw,path=verify_checkpoint(selection,receipt)
    oracle=native_oracle(raw,path)
    pack=packdb.load_pack(Path(receipt['stable_snapshot_path']),
                         mount_name='custom_nodes.amy_aux_normalbae',pack_id=receipt['pack_id'])
    cls=pack.node_mappings[NODE_ID]
    assert set(cls.SDK_PERMISSIONS)=={'raw','assets'}
    async def dispatch(values):
        mapped=await execution._async_map_node_over_list('amy-normalbae',NODE_ID,cls,
                    {name:[value] for name,value in values.items()},cls.FUNCTION)
        return (await execution.resolve_map_node_over_list_results(mapped))[0].result[0]
    def same(actual,expected):
        assert type(actual) is type(expected) is torch.Tensor
        assert actual.dtype==expected.dtype and actual.shape==expected.shape
        assert torch.equal(actual,expected)
    async def run():
        previous=_sdk.providers.execution_backend
        backend=CloudExecutionBackend()
        _sdk.providers.execution_backend=backend
        cases=[]
        try:
            for batch,height,width,dtype,resolution in [(2,32,32,torch.float32,512),(1,24,40,torch.float16,64)]:
                image=torch.linspace(0,1,batch*height*width*3,dtype=dtype).reshape(batch,height,width,3)
                before=image.clone()
                values=dict(image=image,resolution=resolution)
                expected=oracle.execute(**values)[0]
                actual=await dispatch(values)
                same(actual,expected)
                assert torch.equal(image,before)
                cases.append({'batch':batch,'resolution':resolution,'shape':list(actual.shape),'dtype':str(actual.dtype)})
            # Preserve Normalize's native four-channel mismatch; do not coerce
            # RGBA to RGB. Outer error envelope is separately observed.
            invalid=dict(image=torch.ones(1,24,40,4),resolution=64)
            with pytest.raises(RuntimeError): oracle.execute(**invalid)
            with pytest.raises(Exception): await dispatch(invalid)
            recovery=dict(image=torch.ones(1,24,40,3),resolution=64)
            same(await dispatch(recovery),oracle.execute(**recovery)[0])
            with pytest.raises(Exception,match='projected|workspace|bounded'):
                await dispatch(dict(recovery,resolution=16384))
            same(await dispatch(recovery),oracle.execute(**recovery)[0])
            return cases
        finally:
            try: await backend.guests.shutdown()
            finally: _sdk.providers.execution_backend=previous
    cases=asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps({
      'node_id':NODE_ID,'loader_contract':selection['load_state_contract'],
      'actual_published_reader_native_model_member_equal':True,'native_registered_cases':cases,
      'native_normalize_error':True,'registered_error_observed':True,
      'workload_refusal':True,'recoveries':2,'sampling_train_branch_executed':False,
      'gpu_device_equivalence':None,'cold_warm_acceptance':None,'whole_pack_acceptance':False},indent=2)+'\n')
