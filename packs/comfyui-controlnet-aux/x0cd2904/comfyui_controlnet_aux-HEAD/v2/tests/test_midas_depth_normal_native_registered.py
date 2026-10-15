"""Future real modern MiDaS depth/normal native + registered gate.

Requires a NEW qualified production resource-constructor revision. The current
source successor holds that constructor and cannot produce a passing result.
No fake processor/model or host-source fallback replaces registered execution.
"""
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import warnings

import cv2
import numpy as np
import pytest
import torch
from PIL import Image
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
IDS=['MiDaS-DepthMapPreprocessor','MiDaS-NormalMapPreprocessor']

def lift(path,ns,names=None,transform=None):
    text=(PRISTINE/path).read_text()
    body=[n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and (names is None or n.name in names)]
    assert body
    if transform:body=[transform.visit(n) for n in body]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(PRISTINE/path),'exec'),ns)

def verify_native_bundle(receipt):
    # This is an actual owning native-oracle directory, never a guessed SDK
    # directory or parent derived from an AssetRef path.
    root=Path(receipt['native_model_directory'])
    assert root.is_absolute() and root.resolve()==root and root.is_dir()
    assert receipt['native_model_repository']=='Intel/dpt-hybrid-midas'
    revision=receipt['native_model_revision']
    assert isinstance(revision,str) and re.fullmatch('[0-9a-f]{40}',revision)
    inventory=receipt['native_model_inventory']
    assert isinstance(inventory,list) and inventory
    names=set()
    for item in inventory:
        relative=Path(item['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        assert item['path'] not in names
        names.add(item['path'])
        path=root/relative
        assert path.resolve().is_relative_to(root)
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size==item['bytes']
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        assert digest.hexdigest()==item['sha256']
    # The owner's inventory must be complete; hidden extra config/weight files
    # cannot silently select a different Transformers constructor.
    entries=list(root.rglob('*'))
    assert all(not p.is_symlink() for p in entries)
    actual={str(p.relative_to(root)) for p in entries if p.is_file()}
    assert actual==names
    assert receipt['native_model_inventory_complete'] is True
    assert receipt['processor_config_weight_constructor_qualified'] is True
    return root

def native_oracles(bundle):
    ns=dict(torch=torch,np=np,cv2=cv2,Image=Image,warnings=warnings,
            model_management=model_management,comfy=comfy,native_bundle_path=str(bundle),
            UPSCALE_METHODS=['INTER_NEAREST','INTER_LINEAR','INTER_AREA','INTER_CUBIC','INTER_LANCZOS4'])
    lift('src/custom_controlnet_aux/util.py',ns,
         ['HWC3','safer_memory','pad64','get_upscale_method','resize_image_with_pad','common_input_validate'])
    class OwnedNativeAcquisition(ast.NodeTransformer):
        def visit_Call(self,node):
            node=self.generic_visit(node)
            if isinstance(node.func,ast.Attribute) and node.func.attr=='from_pretrained' and isinstance(node.func.value,ast.Name) and node.func.value.id in ('DPTImageProcessor','DPTForDepthEstimation'):
                node.args=[ast.Name(id='native_bundle_path',ctx=ast.Load())]
                node.keywords=[ast.keyword(arg='local_files_only',value=ast.Constant(value=True))]
            return node
        def visit_ExceptHandler(self,node):
            # Native remote fallback is deliberately disabled for the owned
            # reference resource phase. A local failure is a failed gate.
            node.body=ast.parse("raise RuntimeError('native owned DPT local resource load failed; remote fallback refused')").body
            return node
    lift('src/custom_controlnet_aux/midas/transformers.py',ns,['MidasDetector'],transform=OwnedNativeAcquisition())
    lift('utils.py',ns,['common_annotator_call'])
    class WrapperImport(ast.NodeTransformer):
        def visit_ImportFrom(self,node):return None
    lift('node_wrappers/midas.py',ns,['MIDAS_Depth_Map_Preprocessor','MIDAS_Normal_Map_Preprocessor'],transform=WrapperImport())
    return {IDS[0]:ns['MIDAS_Depth_Map_Preprocessor'](),IDS[1]:ns['MIDAS_Normal_Map_Preprocessor']()}

def test_future_actual_modern_midas_depth_normal_registered_gate():
    raw=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    receipt=json.loads(raw)
    assert receipt['authorized'] is True and receipt['execution_owner']=='chat_f38536805264'
    assert receipt['node_ids']==IDS
    assert receipt['managed_dpt_constructor_qualified'] is True
    # The unimplemented current resource constructor never counts as qualified.
    contract_bytes=(ROOT/'_midas/resource-contract.json').read_bytes()
    assert hashlib.sha256(contract_bytes).hexdigest()==receipt['resource_contract_sha256']
    contract=json.loads(contract_bytes)
    assert contract['approved'] is True and contract['actual_managed_construction_contract'] is not None
    assert hashlib.sha256((ROOT/'_midas/__init__.py').read_bytes()).hexdigest()==receipt['production_constructor_source_sha256']
    assert hashlib.sha256((ROOT/'secure-nodes.json').read_bytes()).hexdigest()==receipt['manifest_sha256']
    for key in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','managed_dpt_resource_selection_sha256'):
        assert isinstance(receipt[key],str) and len(receipt[key])==64
    source=json.loads((ROOT/'_midas/native-sources.json').read_text())
    assert source['source_pin']=='0cd290477128d42cdc3e76a826a402d866e8c684'
    assert receipt['native_source_hashes']==source['hashes']
    for name,expected in source['hashes'].items():
        assert hashlib.sha256((PRISTINE/name).read_bytes()).hexdigest()==expected
    assert args.cpu is True and model_management.get_torch_device().type=='cpu'
    assert receipt['native_network_disabled'] is True and receipt['native_model_mount_readonly'] is True
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    bundle=verify_native_bundle(receipt)
    oracles=native_oracles(bundle)
    pack=packdb.load_pack(Path(receipt['stable_snapshot_path']),
                         mount_name='custom_nodes.amy_aux_midas',pack_id=receipt['pack_id'])
    async def dispatch(node_id,values):
        cls=pack.node_mappings[node_id]
        mapped=await execution._async_map_node_over_list('amy-midas',node_id,cls,
                  {name:[value] for name,value in values.items()},cls.FUNCTION)
        return (await execution.resolve_map_node_over_list_results(mapped))[0].result[0]
    def equal(actual,expected):
        assert type(actual) is type(expected) is torch.Tensor
        assert actual.dtype==expected.dtype and actual.shape==expected.shape
        assert torch.equal(actual,expected)
    async def run():
        previous=_sdk.providers.execution_backend
        backend=CloudExecutionBackend()
        _sdk.providers.execution_backend=backend
        records=[];native_errors=[];recoveries=0
        try:
            for node_id in IDS:
                for batch,height,width,dtype,resolution,a,threshold in [
                    (2,32,32,torch.float32,512,np.pi*2,0.1),
                    (1,24,40,torch.float16,64,0.0,1.0)]:
                    image=torch.linspace(0,1,batch*height*width*3,dtype=dtype).reshape(batch,height,width,3)
                    before=image.clone()
                    values=dict(image=image,resolution=resolution,a=a,bg_threshold=threshold)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        expected=oracles[node_id].execute(**values)[0]
                    actual=await dispatch(node_id,values)
                    equal(actual,expected)
                    assert torch.equal(image,before)
                    records.append({'node_id':node_id,'batch':batch,'resolution':resolution,
                                    'a':a,'bg_threshold':threshold,'shape':list(actual.shape),
                                    'native_warning_types':[type(w.message).__name__ for w in caught]})
                # Observe actual native RGBA support or error; do not guess a
                # processor conversion policy or silently coerce channel count.
                rgba=dict(image=torch.ones(1,24,40,4),resolution=64,a=np.pi*2,bg_threshold=0.1)
                try: expected=oracles[node_id].execute(**rgba)[0]
                except (ValueError,RuntimeError,TypeError,KeyError) as exc:
                    native_errors.append({'node_id':node_id,'case':'rgba','type':type(exc).__name__})
                    with pytest.raises(Exception):await dispatch(node_id,rgba)
                    recovery=dict(image=torch.ones(1,24,40,3),resolution=64)
                    equal(await dispatch(node_id,recovery),oracles[node_id].execute(**recovery)[0])
                    recoveries+=1
                else:
                    equal(await dispatch(node_id,rgba),expected)
                    records.append({'node_id':node_id,'case':'rgba-native-supported'})
                recovery=dict(image=torch.ones(1,24,40,3),resolution=64)
                with pytest.raises(Exception,match='projected|workspace|bounded'):
                    await dispatch(node_id,dict(recovery,resolution=16384))
                equal(await dispatch(node_id,recovery),oracles[node_id].execute(**recovery)[0])
                recoveries+=1
            return records,native_errors,recoveries
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    records,errors,recoveries=asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps({
      'node_ids':IDS,'actual_native_registered_cases':records,'actual_native_channel_errors':errors,
      'recoveries':recoveries,'default_wrapper_model':'Intel/dpt-hybrid-midas',
      'native_remote_fallback_tested':False,'native_cache_lifetime_tested':False,
      'constant_predicted_depth_forced':False,'gpu_other_model_dispatch_proof':None,
      'cold_warm_acceptance':None,'whole_pack_acceptance':False},indent=2)+'\n')
