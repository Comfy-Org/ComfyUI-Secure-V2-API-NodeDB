"""Future real trained DSINE/native/registered gate; source author never runs it."""
import ast
import asyncio
import contextlib
import hashlib
import io as text_io
import json
import os
from pathlib import Path
import warnings

import cv2
import numpy as np
import pytest
import timm
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
NODE_ID='DSINE-NormalMapPreprocessor'
PREFIX='src/custom_controlnet_aux/dsine/'

def lift(path,ns,names=None,transform=None):
    tree=ast.parse((PRISTINE/path).read_text())
    body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and (names is None or n.name in names)]
    assert body
    if transform:body=[transform.visit(n) for n in body]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(PRISTINE/path),'exec'),ns)

def native_oracle(raw,path):
    def acquired(repo,filename):
        assert repo=='hr16/Diffusion-Edge' and filename=='dsine.pt'
        return str(path)
    ns=dict(np=np,torch=torch,nn=torch.nn,F=torch.nn.functional,cv2=cv2,timm=timm,
            Image=Image,rearrange=rearrange,transforms=transforms,warnings=warnings,
            custom_hf_download=acquired,DIFFUSION_EDGE_MODEL_NAME='hr16/Diffusion-Edge',
            raw_checkpoint=raw,model_management=model_management,comfy=comfy)
    # Literal channel declaration is retained, never fabricated vendor output.
    sub=ast.parse((PRISTINE/(PREFIX+'models/submodules/__init__.py')).read_text())
    assignment=next(n for n in sub.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='INPUT_CHANNELS_DICT' for t in n.targets))
    ns['INPUT_CHANNELS_DICT']=ast.literal_eval(assignment.value)
    lift(PREFIX+'models/submodules/standalone_encoder.py',ns,['StandaloneEncoder'])
    ns['Encoder']=ns['StandaloneEncoder']
    lift(PREFIX+'models/submodules/__init__.py',ns)
    lift(PREFIX+'utils/rotation.py',ns)
    lift(PREFIX+'utils/utils.py',ns,['get_intrins_from_fov'])
    lift(PREFIX+'models/dsine_arch.py',ns)
    class RestrictedNativeAcquisition(ast.NodeTransformer):
        def visit_Call(self,node):
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='torch' and node.func.attr=='load':
                return ast.Name(id='raw_checkpoint',ctx=ast.Load())
            return self.generic_visit(node)
    lift(PREFIX+'__init__.py',ns,['HWC3','pad64','safer_memory','resize_image_with_pad','common_input_validate','get_pad','load_checkpoint','DsineDetector'],RestrictedNativeAcquisition())
    lift('utils.py',ns,['common_annotator_call'])
    class WrapperImport(ast.NodeTransformer):
        def visit_ImportFrom(self,node):return None
    lift('node_wrappers/dsine.py',ns,['DSINE_Normal_Map_Preprocessor'],WrapperImport())
    return ns['DSINE_Normal_Map_Preprocessor'](),ns

def verify_checkpoint(selection,receipt):
    path=Path(receipt['native_checkpoint_path'])
    assert not path.is_symlink() and path.is_file()
    assert path.stat().st_size==selection['bytes']
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    assert digest.hexdigest()==selection['sha256']
    raw=torch.load(path,map_location='cpu',weights_only=True)
    assert isinstance(raw,dict) and list(raw)==selection['raw_top_level_keys']
    assert 'model' in raw and 'state_dict' not in raw
    original=raw['model'];assert isinstance(original,dict) and original
    evidence_bytes=Path(receipt['restricted_shape_evidence_path']).read_bytes()
    assert hashlib.sha256(evidence_bytes).hexdigest()==selection['restricted_shape_evidence_sha256']
    evidence=json.loads(evidence_bytes)
    assert evidence['actual_inspection'] is True and evidence['restricted_weights_only'] is True
    assert evidence['asset_sha256']==selection['sha256'] and evidence['raw_top_level_keys']==list(raw)
    actual=comfy.utils.load_torch_file(str(path),safe_load=True)
    if selection['load_state_contract']=='model-only-unwrapped':
        assert list(raw)==['model'];member=actual
    else:
        assert selection['load_state_contract']=='nested-model-retained' and len(raw)>1
        member=actual['model']
    assert isinstance(member,dict) and list(member)==list(original)
    total=0
    for key,value in original.items():
        assert isinstance(key,str) and type(value) is torch.Tensor
        assert value.device.type=='cpu' and value.layout==torch.strided
        assert member[key].dtype==value.dtype and member[key].shape==value.shape
        assert torch.equal(member[key],value)
        total+=value.numel()*value.element_size()
    assert total<=512*1024*1024
    return raw,path

def test_actual_trained_native_registered_dsine_and_recovery():
    encoded=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(encoded).hexdigest()==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    receipt=json.loads(encoded)
    assert receipt['authorized'] is True and receipt['execution_owner']=='chat_f38536805264'
    assert receipt['node_id']==NODE_ID
    for key in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256'):
        assert isinstance(receipt[key],str) and len(receipt[key])==64
    assert hashlib.sha256((ROOT/'secure-nodes.json').read_bytes()).hexdigest()==receipt['manifest_sha256']
    selection_bytes=(ROOT/'_dsine/asset-selection.json').read_bytes()
    assert hashlib.sha256(selection_bytes).hexdigest()==receipt['asset_selection_sha256']
    selection=json.loads(selection_bytes);assert selection['approved'] is True
    assert hashlib.sha256(Path(comfy.utils.__file__).read_bytes()).hexdigest()==selection['published_loader_source_sha256']
    sources=json.loads((ROOT/'_dsine/native-sources.json').read_text())
    assert receipt['native_source_hashes']==sources['hashes']
    for name,digest in sources['hashes'].items():
        assert hashlib.sha256((PRISTINE/name).read_bytes()).hexdigest()==digest
    assert args.cpu is True and model_management.get_torch_device().type=='cpu'
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    raw,path=verify_checkpoint(selection,receipt)
    oracle,ns=native_oracle(raw,path)
    # Native strict=False may retain random missing parameters. Do not report
    # host-vs-guest parity if those independent RNG states affect predictions.
    probe=ns['DSINE']()
    normalized={k.replace('module.','') if k.startswith('module.') else k:v for k,v in raw['model'].items()}
    missing=[k for k,v in probe.state_dict().items() if k not in normalized or normalized[k].shape!=v.shape]
    assert not missing, 'native partial/random DSINE state needs an explicit RNG-fidelity disposition before comparison'
    expected_diagnostics=text_io.StringIO()
    with contextlib.redirect_stdout(expected_diagnostics):ns['load_checkpoint'](str(path),probe)
    del probe
    pack=packdb.load_pack(Path(receipt['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_dsine',pack_id=receipt['pack_id'])
    cls=pack.node_mappings[NODE_ID]
    assert set(cls.SDK_PERMISSIONS)=={'raw','assets'}
    async def dispatch(values):
        mapped=await execution._async_map_node_over_list('amy-dsine',NODE_ID,cls,{name:[value] for name,value in values.items()},cls.FUNCTION)
        return (await execution.resolve_map_node_over_list_results(mapped))[0].result[0]
    def same(actual,expected):
        assert type(actual) is type(expected) is torch.Tensor
        assert actual.dtype==expected.dtype and actual.shape==expected.shape
        assert torch.equal(actual,expected)
    async def run():
        previous=_sdk.providers.execution_backend
        backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        cases=[]
        try:
            for batch,height,width,channels,dtype,params in [
                (2,32,32,3,torch.float32,{}),
                (1,25,41,3,torch.float16,dict(fov=90.0,iterations=1,resolution=64)),
                (1,41,25,4,torch.float32,dict(fov=365.0,iterations=2,resolution=64))]:
                image=torch.linspace(0,1,batch*height*width*channels,dtype=dtype).reshape(batch,height,width,channels)
                before=image.clone();values=dict(image=image,**params)
                expected=oracle.execute(**values)[0]
                actual=await dispatch(values);same(actual,expected)
                assert torch.equal(image,before)
                cases.append(dict(batch=batch,input_shape=list(image.shape),parameters=params,output_shape=list(actual.shape),dtype=str(actual.dtype)))
            recovery=dict(image=torch.ones(1,25,41,3),resolution=64,iterations=1)
            invalid=dict(recovery,image=torch.ones(1,25,41,2))
            with pytest.raises(AssertionError):oracle.execute(**invalid)
            with pytest.raises(Exception):await dispatch(invalid)
            same(await dispatch(recovery),oracle.execute(**recovery)[0])
            with pytest.raises(Exception,match='projected|workspace|bounded'):
                await dispatch(dict(recovery,resolution=16384))
            same(await dispatch(recovery),oracle.execute(**recovery)[0])
            return cases
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    cases=asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(node_id=NODE_ID,native_registered_cases=cases,
        actual_reader_model_member_equal=True,native_loader_diagnostics=expected_diagnostics.getvalue(),
        trained_model_key_shape_coverage_complete=True,native_channel_error=True,registered_error_observed=True,
        workload_refusal=True,recoveries=2,native_unused_remove_pad_preserved=True,
        partial_checkpoint_rng_fidelity=None,gpu_device_equivalence=None,cold_warm_acceptance=None,whole_pack_acceptance=False),indent=2)+'\n')
