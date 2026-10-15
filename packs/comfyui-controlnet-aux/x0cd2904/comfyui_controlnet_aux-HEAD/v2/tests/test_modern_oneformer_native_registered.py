"""Future genuine OneFormer registered/native gates; unexecuted source."""
import ast
import asyncio
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

import execution
import numpy as np
import pytest
import torch
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT=Path(__file__).resolve().parents[1];PRISTINE=Path(os.environ['AMY_AUX_PRISTINE'])
CLASSES={'OneFormer-COCO-SemSegPreprocessor':'OneFormer_COCO_SemSegPreprocessor',
         'OneFormer-ADE20K-SemSegPreprocessor':'OneFormer_ADE20K_SemSegPreprocessor'}
FILES={'OneFormer-COCO-SemSegPreprocessor':'150_16_swin_l_oneformer_coco_100ep.pth',
       'OneFormer-ADE20K-SemSegPreprocessor':'250_16_swin_l_oneformer_ade20k_160k.pth'}
MODELS={'OneFormer-COCO-SemSegPreprocessor':'shi-labs/oneformer_coco_swin_large',
        'OneFormer-ADE20K-SemSegPreprocessor':'shi-labs/oneformer_ade20k_swin_large'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def issued(positive=False):
    p=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']);assert digest(p)==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(p.read_text());assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==list(CLASSES)
    for k in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','controller_cleanup_plan_sha256'):
        assert type(r[k]) is str and len(r[k])==64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required' and os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    assert digest(ROOT/'secure-nodes.json')==r['manifest_sha256']
    assert digest(ROOT/'_modern_oneformer/asset-selection.json')==r['asset_selection_sha256']
    hashes=json.loads((ROOT/'_modern_oneformer/native-sources.json').read_text())['hashes'];assert r['native_source_hashes']==hashes
    for name,h in hashes.items():assert digest(PRISTINE/name)==h
    selected=json.loads((ROOT/'_modern_oneformer/asset-selection.json').read_text())
    if positive:
        assert r['actual_new_supported_managed_constructor_source_qualified'] is True
        assert r['actual_vendor_both_bundles_operator_device_image_lifetime_workspace_qualified'] is True
        assert selected['actual_constructor_supported'] is True
        assert 'exact Transformers OneFormerProcessor/OneFormerForUniversalSegmentation and complete immutable tokenizer/processor/config/model/weights bundle required' not in (ROOT/'_modern_oneformer/selection.py').read_text()
        assert digest(ROOT/'_modern_oneformer/selection.py')==r['new_constructor_selection_source_sha256']
    else:assert selected['actual_constructor_supported'] is False
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_modern_oneformer',pack_id=r['pack_id'])
    for node in CLASSES:
        assert pack.node_mappings[node].define_schema().node_id==node
        assert set(pack.node_mappings[node].SDK_PERMISSIONS)=={'raw','assets'}
    return r,selected,pack

async def dispatch(pack,node,values,prompt_id='amy-modern-oneformer'):
    cls=pack.node_mappings[node]
    mapped=await execution._async_map_node_over_list(prompt_id,node,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui

def same(actual,expected):
    result,ui=actual;assert not ui and type(result) is type(expected) is tuple and len(result)==1
    assert type(result[0]) is type(expected[0]) is torch.Tensor
    assert result[0].dtype==expected[0].dtype and result[0].shape==expected[0].shape and torch.equal(result[0],expected[0])

def test_real_registered_both_held_constructors_numeric_refusals_recoveries():
    r,selected,pack=issued();image=torch.ones(1,17,29,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for node in CLASSES:
                for values,message in [(dict(image=image),'Modern OneFormer managed constructor source unsupported'),
                                       (dict(image=image,resolution=10**30),'numeric input exceeds bounded finite range')]:
                    with pytest.raises(Exception,match=message):await dispatch(pack,node,values)
                    result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
                    assert not ui and torch.equal(result[0],image)
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_refusals=4,actual_registered_recoveries=4,
        actual_pre_import_asset_rpc_model_call_observation=None,actual_constructor_supported=False,whole_acceptance=False),indent=2)+'\n')

def real_native_wrappers(native,helpers):
    import comfy.model_management as model_management
    t=(PRISTINE/'node_wrappers/oneformer.py').read_text();tree=ast.parse(t)
    class BindRealNativeImport(ast.NodeTransformer):
        def visit_ImportFrom(self,n):
            assert n.module=='custom_controlnet_aux.oneformer'
            return None
    classes=[BindRealNativeImport().visit(n) for n in tree.body if isinstance(n,ast.ClassDef)]
    ns=dict(OneformerSegmentor=native.OneformerSegmentor,model_management=model_management,
        common_annotator_call=helpers.common_annotator_call,define_preprocessor_inputs=helpers.define_preprocessor_inputs,INPUT=helpers.INPUT)
    exec(compile(ast.fix_missing_locations(ast.Module(body=classes,type_ignores=[])),str(PRISTINE/'node_wrappers/oneformer.py'),'exec'),ns)
    return {node:ns[name]() for node,name in CLASSES.items()}

def actual_value(v):
    if isinstance(v,torch.Tensor):v=v.cpu().numpy()
    if isinstance(v,np.ndarray):
        return dict(dtype=str(v.dtype),shape=list(v.shape),sha256=hashlib.sha256(v.tobytes()).hexdigest(),unique=np.unique(v).tolist())
    assert v is None
    return None

def actual_native_trace(oracle,values,module):
    # Real native frames only. No model, processor, mask or palette replacement.
    assert sys.gettrace() is None;path=Path(module.__file__).resolve();events=[]
    def trace(frame,event,arg):
        if Path(frame.f_code.co_filename).resolve()!=path:return trace
        name=frame.f_code.co_name
        if event=='return' and name in ('_generate_professional_colormap','_generate_detectron2_style_palette','__call__'):
            entry=dict(function=name,result=actual_value(arg))
            if name=='__call__':
                entry['raw_prediction']=actual_value(frame.f_locals['predicted_semantic_map'])
                entry['uint8_before_colormap']=actual_value(frame.f_locals['seg_map'])
            if name=='_generate_professional_colormap':entry['native_input_class_ids']=actual_value(frame.f_locals['seg_map'])
            events.append(entry)
        return trace
    sys.settrace(trace)
    try:return oracle.semantic_segmentate(**values),events
    finally:sys.settrace(None)

def actual_guest_trace(r,index,node,image,prompt_id):
    # Optional separately qualified REAL guest observer: no public raw-class
    # socket, callback/provider facade or host source import is invented here.
    assert r['actual_guest_source_observer_qualified'] is True
    source=Path(r['actual_guest_source_observer_path']);assert digest(source)==r['actual_guest_source_observer_sha256']
    root=Path(r['actual_guest_observation_publication_root']).resolve()
    publication=root/str(index)/'PUBLICATION.json';assert publication.is_file() and not publication.is_symlink()
    row=json.loads(publication.read_text());p=root/row['relative_path']
    assert p.resolve().is_relative_to(root) and p.is_file() and not p.is_symlink() and digest(p)==row['sha256']
    o=json.loads(p.read_text());assert o['actual_guest_execution'] is True
    assert o['actual_outer_dispatch_id']==prompt_id and o['issued_attempt_id']==r['issued_attempt_id'] and o['node_id']==node
    assert o['case_index']==index and o['observer_source_sha256']==r['actual_guest_source_observer_sha256']
    assert o['source_selection_sha256']==r['source_selection_sha256']
    assert o['input_tensor_sha256']==hashlib.sha256(image.cpu().numpy().tobytes()).hexdigest()
    return o['source_return_events'],row['sha256']

def future_real_trained_both_native_registered_gate():
    # Current hard constructor cannot run positive. Requires a genuinely NEW
    # complete managed constructor, both real bundles and actual issued profile.
    r,selected,pack=issued(True)
    assert r['native_module']=='custom_controlnet_aux.oneformer'
    native=importlib.import_module(r['native_module'])
    assert Path(native.__file__).resolve()==(PRISTINE/'src/custom_controlnet_aux/oneformer/__init__.py').resolve()
    module=importlib.import_module('custom_controlnet_aux.oneformer.transformers')
    assert digest(Path(module.__file__))=='8f1ad862a74b9ada46835439ab66a21938e4e4ea3c5c2f8f2b194c03b855a3fd'
    helpers=importlib.import_module(r['native_pack_utils_module']);assert Path(helpers.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    import transformers
    assert digest(Path(transformers.__file__))==r['actual_transformers_vendor_module_sha256']
    assert module.HF_MODEL_NAME=='lllyasviel/Annotators'
    assert r['actual_native_local_bundle_no_remote_qualified'] is True
    for node in CLASSES:
        assert r['actual_native_bundles'][node]['model_name']==MODELS[node]
        for row in r['actual_native_bundles'][node]['files']:
            p=Path(row['path']);assert p.is_file() and digest(p)==row['sha256']
    oracles=real_native_wrappers(native,helpers)
    for node,oracle in oracles.items():
        assert json.loads(json.dumps(oracle.INPUT_TYPES()))==json.loads((ROOT/'_schemas.json').read_text())[node]['inputs']
    images={}
    for name,row in r['actual_image_fixtures'].items():
        p=Path(row['path']);assert digest(p)==row['sha256'];images[name]=torch.from_numpy(np.load(p,allow_pickle=False))
    cases=r['finite_trained_cases'];assert 0<len(cases)<=24
    for node in CLASSES:
        assert {'default512','batch2','rectangular_fp16','rgba'}<={c['fixture'] for c in cases if c['node_id']==node}
    report=[];private_errors=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for index,c in enumerate(cases):
                node=c['node_id'];values=dict(image=images[c['fixture']],resolution=c.get('resolution',512))
                expected,native_trace=actual_native_trace(oracles[node],values,module)
                prompt_id=r['issued_attempt_id']+'-oneformer-'+str(index)
                same(await dispatch(pack,node,values,prompt_id),expected)
                internal_guest_proof=None
                if r.get('actual_guest_source_observer_qualified') is True:
                    trace,proof=actual_guest_trace(r,index,node,values['image'],prompt_id)
                    assert trace==native_trace;internal_guest_proof=proof
                report.append(dict(case=c,actual_native_source_trace=native_trace,actual_guest_internal_class_palette_trace_sha256=internal_guest_proof))
            # Genuine source filename failures occur BEFORE model construction;
            # these are PRIVATE errors, not unsupported registered inputs.
            for value,error in [(None,AttributeError),(1,AttributeError),([],TypeError),({},TypeError)]:
                with pytest.raises(error) as e:native.OneformerSegmentor.from_pretrained(filename=value)
                private_errors.append(dict(input_type=type(value).__name__,error_type=type(e.value).__name__,registered=False))
            for node in CLASSES:
                with pytest.raises(Exception):await dispatch(pack,node,dict(image=images['default512'],resolution=10**30))
                result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=images['default512'],preprocessor='none',resolution=64))
                assert not ui and torch.equal(result[0],images['default512'])
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_cases=report,actual_private_filename_errors=private_errors,
        actual_numeric_refusals_and_recoveries=2,actual_private_fallback_filename_trained_cases=None,
        actual_direct_pil_channel_and_constructor_failure_case_results=None,actual_independent_model_lifecycle_kernel_cleanup=None,
        whole_acceptance=False),indent=2)+'\n')
