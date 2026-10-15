"""Future genuine ordinary DepthAnything native/registered gates; NOT_RUN."""
import ast
import asyncio
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import warnings

import execution
import numpy as np
from PIL import Image
import pytest
import torch
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT=Path(__file__).resolve().parents[1];PRISTINE=Path(os.environ['AMY_AUX_PRISTINE']);ID='DepthAnythingPreprocessor'
MODELS={'depth_anything_vitl14.pth':'LiheYoung/depth-anything-large-hf','depth_anything_vitb14.pth':'LiheYoung/depth-anything-base-hf','depth_anything_vits14.pth':'LiheYoung/depth-anything-small-hf'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def issued(positive=False):
    p=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']);assert digest(p)==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(p.read_text());assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==[ID]
    for k in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','controller_cleanup_plan_sha256'):
        assert type(r[k]) is str and len(r[k])==64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required' and os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    assert digest(ROOT/'secure-nodes.json')==r['manifest_sha256'] and digest(ROOT/'_modern_depth_anything/asset-selection.json')==r['asset_selection_sha256']
    hashes=json.loads((ROOT/'_modern_depth_anything/native-sources.json').read_text())['hashes'];assert r['native_source_hashes']==hashes
    for name,h in hashes.items():assert digest(PRISTINE/name)==h
    selected=json.loads((ROOT/'_modern_depth_anything/asset-selection.json').read_text())
    if positive:
        assert r['actual_new_supported_managed_pipeline_constructor_source_qualified'] is True
        assert r['actual_vendor_all_three_bundles_operator_device_image_lifetime_workspace_qualified'] is True
        assert selected['actual_constructor_supported'] is True
        assert 'actual Transformers AutoImageProcessor/AutoModelForDepthEstimation/depth-estimation pipeline and complete immutable bundles required' not in (ROOT/'_modern_depth_anything/selection.py').read_text()
        assert digest(ROOT/'_modern_depth_anything/selection.py')==r['new_constructor_selection_source_sha256']
    else:assert selected['actual_constructor_supported'] is False
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_modern_depth_anything',pack_id=r['pack_id'])
    assert pack.node_mappings[ID].define_schema().node_id==ID and set(pack.node_mappings[ID].SDK_PERMISSIONS)=={'raw','assets'}
    return r,selected,pack

async def dispatch(pack,node,values,prompt_id='amy-modern-depth-anything'):
    cls=pack.node_mappings[node]
    mapped=await execution._async_map_node_over_list(prompt_id,node,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui

def same(actual,expected):
    result,ui=actual;assert not ui and type(result) is type(expected) is tuple and len(result)==1
    assert type(result[0]) is type(expected[0]) is torch.Tensor
    assert result[0].dtype==expected[0].dtype and result[0].shape==expected[0].shape and torch.equal(result[0],expected[0])

def test_actual_registered_held_constructor_numeric_refusals_recoveries():
    r,selected,pack=issued();image=torch.ones(1,17,29,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for filename in MODELS:
                with pytest.raises(Exception,match='Modern DepthAnything managed constructor source unsupported'):
                    await dispatch(pack,ID,dict(image=image,ckpt_name=filename))
                result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
                assert not ui and torch.equal(result[0],image)
            with pytest.raises(Exception,match='numeric input exceeds bounded finite range'):
                await dispatch(pack,ID,dict(image=image,resolution=10**30))
            result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
            assert not ui and torch.equal(result[0],image)
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_refusals=4,actual_registered_recoveries=4,
        actual_pre_import_asset_rpc_pipeline_model_call_observation=None,actual_constructor_supported=False,whole_acceptance=False),indent=2)+'\n')

def real_native_wrapper(native,helpers):
    import comfy.model_management as model_management
    p=PRISTINE/'node_wrappers/depth_anything.py'
    cls=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Depth_Anything_Preprocessor')
    class BindRealNativeImport(ast.NodeTransformer):
        def visit_ImportFrom(self,n):
            assert n.module=='custom_controlnet_aux.depth_anything';return None
    ns=dict(DepthAnythingDetector=native.DepthAnythingDetector,model_management=model_management,common_annotator_call=helpers.common_annotator_call,define_preprocessor_inputs=helpers.define_preprocessor_inputs,INPUT=helpers.INPUT)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[BindRealNativeImport().visit(cls)],type_ignores=[])),str(p),'exec'),ns)
    return ns['Depth_Anything_Preprocessor']()

def actual_array(v):
    pil=isinstance(v,Image.Image)
    if pil:v=np.asarray(v)
    assert isinstance(v,np.ndarray)
    return dict(kind='PIL' if pil else 'ndarray',dtype=str(v.dtype),shape=list(v.shape),sha256=hashlib.sha256(v.tobytes()).hexdigest())

def native_observed_call(call,module):
    assert sys.gettrace() is None;path=Path(module.__file__).resolve();events=[]
    def trace(frame,event,arg):
        if Path(frame.f_code.co_filename).resolve()!=path:return trace
        name=frame.f_code.co_name
        if name=='__init__' and event in ('call','return'):
            item=dict(event=event,method=name,requested_model_name=frame.f_locals['model_name'])
            if event=='return' and hasattr(frame.f_locals['self'],'pipe'):
                pipe=frame.f_locals['self'].pipe;item['actual_pipeline_type']=type(pipe).__module__+'.'+type(pipe).__name__
                item['actual_model_type']=type(pipe.model).__module__+'.'+type(pipe.model).__name__
            events.append(item)
        elif name=='__call__' and event=='return':
            events.append(dict(event=event,method=name,result=actual_array(arg),actual_pipeline_depth=actual_array(frame.f_locals['depth']),
                depth_min=float(frame.f_locals['depth_min']),depth_max=float(frame.f_locals['depth_max']),
                normalization_branch=bool(frame.f_locals['depth_max']>frame.f_locals['depth_min']),
                normalized_or_zero_depth=actual_array(frame.f_locals['depth_array']),quantized_depth=actual_array(frame.f_locals['depth_image'])))
        return trace
    sys.settrace(trace)
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always');out=call()
        return out,events,[dict(type=w.category.__name__,message=str(w.message)) for w in captured]
    finally:sys.settrace(None)

def real_guest_observation(r,index,image,prompt_id):
    assert r['actual_guest_pipeline_depth_observer_qualified'] is True
    p=Path(r['actual_guest_source_observer_path']);assert digest(p)==r['actual_guest_source_observer_sha256']
    root=Path(r['actual_guest_observation_publication_root']).resolve();publication=root/str(index)/'PUBLICATION.json'
    assert publication.is_file() and not publication.is_symlink();row=json.loads(publication.read_text())
    p=root/row['relative_path'];assert p.resolve().is_relative_to(root) and p.is_file() and not p.is_symlink() and digest(p)==row['sha256']
    o=json.loads(p.read_text());assert o['actual_guest_execution'] is True and o['node_id']==ID and o['case_index']==index
    assert o['actual_outer_dispatch_id']==prompt_id and o['issued_attempt_id']==r['issued_attempt_id']
    assert o['source_selection_sha256']==r['source_selection_sha256'] and o['observer_source_sha256']==r['actual_guest_source_observer_sha256']
    assert o['input_tensor_sha256']==hashlib.sha256(image.cpu().numpy().tobytes()).hexdigest()
    return o,row['sha256']

def future_real_all_three_native_registered_gate():
    # Current constructor is hard-held; NEW actual pipeline source and complete
    # original large/base/small HF bundles must first be independently selected.
    r,selected,pack=issued(True);assert r['native_module']=='custom_controlnet_aux.depth_anything'
    native=importlib.import_module(r['native_module'])
    assert Path(native.__file__).resolve()==(PRISTINE/'src/custom_controlnet_aux/depth_anything/__init__.py').resolve()
    module=importlib.import_module('custom_controlnet_aux.depth_anything.transformers')
    assert digest(Path(module.__file__))=='7f9f571ab6a410fb43c14dc70a292d8987f8e1a2ac389b19ecc1b4e852966c22'
    helpers=importlib.import_module(r['native_pack_utils_module']);assert Path(helpers.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    import transformers
    assert digest(Path(transformers.__file__))==r['actual_transformers_vendor_module_sha256']
    assert r['actual_native_complete_local_bundles_no_remote_qualified'] is True
    for filename,model in MODELS.items():
        assert r['actual_native_bundles'][filename]['model_name']==model
        for row in r['actual_native_bundles'][filename]['files']:
            p=Path(row['path']);assert p.is_file() and digest(p)==row['sha256']
    oracle=real_native_wrapper(native,helpers)
    assert json.loads(json.dumps(oracle.INPUT_TYPES()))==json.loads((ROOT/'_schemas.json').read_text())[ID]['inputs']
    images={}
    for name,row in r['actual_image_fixtures'].items():
        p=Path(row['path']);assert digest(p)==row['sha256'];images[name]=torch.from_numpy(np.load(p,allow_pickle=False))
    cases=r['finite_trained_cases'];assert 0<len(cases)<=24
    for filename in MODELS:
        assert {'default512','batch2','odd_rectangular_fp16','rgba'}<={c['fixture'] for c in cases if c.get('ckpt_name','depth_anything_vitl14.pth')==filename}
    report=[];private=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for index,c in enumerate(cases):
                filename=c.get('ckpt_name','depth_anything_vitl14.pth')
                values=dict(image=images[c['fixture']],ckpt_name=filename,resolution=c.get('resolution',512))
                expected,trace,warn=native_observed_call(lambda:oracle.execute(**values),module)
                constructors=[e for e in trace if e['method']=='__init__' and e['event']=='call']
                assert len(constructors)==1 and constructors[0]['requested_model_name']==MODELS[filename]
                prompt_id=r['issued_attempt_id']+'-depth-anything-'+str(index)
                same(await dispatch(pack,ID,values,prompt_id),expected)
                internal=None
                if r.get('actual_guest_pipeline_depth_observer_qualified') is True:
                    o,internal=real_guest_observation(r,index,values['image'],prompt_id)
                    assert o['source_events']==trace and o['source_warning_events']==warn
                report.append(dict(case=c,native_source_events=trace,native_warning_events=warn,actual_guest_internal_pipeline_depth_observation_sha256=internal))
            for value in ([],{}):
                with pytest.raises(TypeError):native.DepthAnythingDetector.from_pretrained(filename=value)
            # Private None/unknown filename and ignoredrepo exercise REAL large
            # construction, not a monkeypatched class/model/from_pretrained.
            for filename in (None,'unknown_filename'):
                detector,ctor_trace,_=native_observed_call(lambda:native.DepthAnythingDetector.from_pretrained(pretrained_model_or_path='ignored_source_repository',filename=filename).to(r['actual_native_device']),module)
                assert any(e.get('requested_model_name')=='LiheYoung/depth-anything-large-hf' for e in ctor_trace)
                array=np.asarray(images['default512'][0].cpu()*255,dtype=np.uint8)
                out,trace,warn=native_observed_call(lambda:detector(array,detect_resolution=512,output_type='pil'),module)
                assert isinstance(out,Image.Image)
                with pytest.raises(ValueError,match='input_image must be defined'):detector(None)
                private.append(dict(filename=filename,actual_pil_result=actual_array(out),actual_source_events=ctor_trace+trace,actual_warnings=warn,ignored_repository_native_only=True));del detector
            with pytest.raises(Exception):await dispatch(pack,ID,dict(image=images['default512'],resolution=10**30))
            result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=images['default512'],preprocessor='none',resolution=64))
            assert not ui and torch.equal(result[0],images['default512'])
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_cases=report,actual_native_private_cases=private,
        actual_unhashable_filename_errors=2,actual_numeric_refusal_and_recovery=1,actual_genuine_constant_or_noncomparable_depth_case=None,
        actual_nonPIL_pipeline_depth_case=None,actual_source_channel_and_local_constructor_failure_case=None,
        actual_independent_pipeline_model_lifecycle_kernel_cleanup=None,whole_acceptance=False),indent=2)+'\n')
