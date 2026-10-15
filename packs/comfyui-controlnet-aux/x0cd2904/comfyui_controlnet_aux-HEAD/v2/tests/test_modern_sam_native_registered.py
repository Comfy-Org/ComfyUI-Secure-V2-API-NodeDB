"""Future genuine dispatch and native oracles only; unexecuted source preparation."""
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

ROOT=Path(__file__).resolve().parents[1]
PRISTINE=Path(os.environ['AMY_AUX_PRISTINE']);ID='SAMPreprocessor'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def issued(positive=False):
    p=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']);assert digest(p)==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(p.read_text());assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==[ID]
    for k in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','controller_cleanup_plan_sha256'):
        assert type(r[k]) is str and len(r[k])==64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required' and os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    assert digest(ROOT/'secure-nodes.json')==r['manifest_sha256']
    assert digest(ROOT/'_modern_sam/asset-selection.json')==r['asset_selection_sha256']
    hashes=json.loads((ROOT/'_modern_sam/native-sources.json').read_text())['hashes']
    assert r['native_source_hashes']==hashes
    for name,h in hashes.items():assert digest(PRISTINE/name)==h
    selected=json.loads((ROOT/'_modern_sam/asset-selection.json').read_text())
    if positive:
        assert r['actual_new_supported_managed_constructor_source_qualified'] is True
        assert r['actual_vendor_bundle_operator_device_image_rng_lifetime_workspace_qualified'] is True
        assert selected['actual_constructor_supported'] is True
        assert 'exact Transformers SamProcessor/SamModel vendor and complete immutable bundle contract required' not in (ROOT/'_modern_sam/selection.py').read_text()
        assert digest(ROOT/'_modern_sam/selection.py')==r['new_constructor_selection_source_sha256']
        # Public execution inputs do not control/observe guest NumPy state.
        # A separately REAL source-bound guest observer is a required new input,
        # not a fabricated API, test model or seeded local generator here.
        assert r['actual_guest_rng_observer_source_qualified'] is True
        observer=Path(r['actual_guest_rng_observer_source_path'])
        assert digest(observer)==r['actual_guest_rng_observer_source_sha256']
        assert r['actual_guest_rng_observer_source_sha256']==selected['guest_same_numpy_state_observer_source']['sha256']
    else:assert selected['actual_constructor_supported'] is False
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_modern_sam',pack_id=r['pack_id'])
    assert pack.node_mappings[ID].define_schema().node_id==ID
    assert set(pack.node_mappings[ID].SDK_PERMISSIONS)=={'raw','assets'}
    return r,selected,pack

async def dispatch(pack,node,values,prompt_id='amy-modern-sam'):
    cls=pack.node_mappings[node]
    mapped=await execution._async_map_node_over_list(prompt_id,node,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui

def same(actual,expected):
    result,ui=actual;assert not ui and type(result) is type(expected) is tuple and len(result)==1
    assert type(result[0]) is type(expected[0]) is torch.Tensor
    assert result[0].dtype==expected[0].dtype and result[0].shape==expected[0].shape
    assert torch.equal(result[0],expected[0])

def test_real_registered_held_constructor_numeric_refusal_recoveries():
    r,selected,pack=issued();image=torch.ones(1,17,29,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for values,message in [(dict(image=image),'Modern SAM managed constructor source unsupported'),
                                   (dict(image=image,resolution=10**30),'numeric input exceeds bounded finite range')]:
                with pytest.raises(Exception,match=message):await dispatch(pack,ID,values)
                result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
                assert not ui and torch.equal(result[0],image)
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_refusals=2,actual_registered_recoveries=2,
        pre_import_asset_rpc_model_allocation_observation=None,actual_constructor_supported=False,whole_acceptance=False),indent=2)+'\n')

def real_native_wrapper(native,helpers):
    # Compile the retained class with its ONE local import bound to the exact
    # actual native detector. No method/model/math/processor is substituted.
    import comfy.model_management as model_management
    t=(PRISTINE/'node_wrappers/segment_anything.py').read_text()
    cls=next(n for n in ast.parse(t).body if isinstance(n,ast.ClassDef) and n.name=='SAM_Preprocessor')
    class BindRealNativeImport(ast.NodeTransformer):
        def visit_ImportFrom(self,n):
            assert n.module=='custom_controlnet_aux.sam'
            return None
    ns=dict(SamDetector=native.SamDetector,model_management=model_management,
        common_annotator_call=helpers.common_annotator_call,define_preprocessor_inputs=helpers.define_preprocessor_inputs,INPUT=helpers.INPUT)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[BindRealNativeImport().visit(cls)],type_ignores=[])),str(PRISTINE/'node_wrappers/segment_anything.py'),'exec'),ns)
    return ns['SAM_Preprocessor']()

def rng_record(state):
    return dict(algorithm=state[0],keys=state[1].tolist(),position=int(state[2]),has_gauss=int(state[3]),cached_gaussian=float(state[4]))

def observed_rng_state(record):
    assert record['algorithm']=='MT19937'
    assert len(record['keys'])==624 and all(type(v) is int and 0<=v<=2**32-1 for v in record['keys'])
    assert type(record['position']) is int and 0<=record['position']<=624
    assert type(record['has_gauss']) is int and record['has_gauss'] in (0,1)
    assert type(record['cached_gaussian']) in (int,float)
    return ('MT19937',np.asarray(record['keys'],dtype=np.uint32),record['position'],record['has_gauss'],record['cached_gaussian'])

def fresh_real_guest_observation(r,index,image,prompt_id):
    directory=Path(r['actual_guest_observation_publication_root']).resolve()
    publication=directory/str(index)/'PUBLICATION.json'
    assert publication.is_file() and not publication.is_symlink()
    row=json.loads(publication.read_text())
    p=directory/row['relative_path'];assert p.resolve().is_relative_to(directory)
    assert p.is_file() and not p.is_symlink() and digest(p)==row['sha256']
    o=json.loads(p.read_text())
    assert o['actual_guest_execution'] is True and o['case_index']==index
    assert o['actual_outer_dispatch_id']==prompt_id==row['actual_outer_dispatch_id']
    assert o['issued_attempt_id']==r['issued_attempt_id'] and o['node_id']==ID
    assert o['observer_source_sha256']==r['actual_guest_rng_observer_source_sha256']
    assert o['source_selection_sha256']==r['source_selection_sha256']
    assert o['rng_boundary']=='before_source_wrapper_execute_to_after_source_wrapper_execute'
    assert o['input_tensor_sha256']==hashlib.sha256(image.cpu().numpy().tobytes()).hexdigest()
    assert o['global_numpy_rng_restored'] is True
    # Written by a separately qualified REAL guest observer after this dispatch;
    # records/trace bindings are required evidence, not guest control facilities.
    trace=Path(o['actual_source_trace_path']);assert digest(trace)==o['actual_source_trace_sha256']
    o['actual_observation_sha256']=row['sha256']
    return o

def source_value(v):
    # Real observational serialization, never a synthetic detector input/result.
    if isinstance(v,np.ndarray):
        return dict(dtype=str(v.dtype),shape=list(v.shape),sha256=hashlib.sha256(v.tobytes()).hexdigest())
    if isinstance(v,dict):return [[k,source_value(value)] for k,value in v.items()]
    if isinstance(v,(list,tuple)):return [source_value(x) for x in v]
    if isinstance(v,np.generic):return v.item()
    assert v is None or type(v) in (str,int,float,bool)
    return v

def actual_native_trace(oracle,values,module):
    # Future source-local observation of actual native function frames; no
    # processor/model/mask/method replacement and no prior profiler override.
    assert sys.gettrace() is None
    path=Path(module.__file__).resolve();events=[]
    def trace(frame,event,arg):
        if Path(frame.f_code.co_filename).resolve()!=path:return trace
        name=frame.f_code.co_name
        if event=='return' and name in ('generate_automatic_masks','_postprocess_mask','show_anns'):
            entry=dict(function=name,result=source_value(arg))
            if name=='generate_automatic_masks':entry['grid_points']=source_value(frame.f_locals['grid_points'])
            events.append(entry)
        return trace
    sys.settrace(trace)
    try:return oracle.execute(**values),events
    finally:sys.settrace(None)

def future_real_trained_native_registered_same_state_gate():
    # Not executable positive construction for this held packet. Requires NEW
    # exact constructor AND a genuinely supported guest measurement source.
    r,selected,pack=issued(True)
    assert r['native_module']=='custom_controlnet_aux.sam'
    native=importlib.import_module(r['native_module'])
    assert Path(native.__file__).resolve()==(PRISTINE/'src/custom_controlnet_aux/sam/__init__.py').resolve()
    module=importlib.import_module('custom_controlnet_aux.sam.sam')
    assert digest(Path(module.__file__))=='54ece98dc25abbff250b8b8c665e27455b2f13febb2170afd81494302a4372ea'
    helpers=importlib.import_module(r['native_pack_utils_module']);assert Path(helpers.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    import transformers
    assert digest(Path(transformers.__file__))==r['actual_transformers_vendor_module_sha256']
    for row in r['actual_native_complete_local_bundle_files']:
        p=Path(row['path']);assert p.is_file() and digest(p)==row['sha256']
    assert r['actual_native_constructor_local_only_no_remote_qualified'] is True
    oracle=real_native_wrapper(native,helpers)
    assert json.loads(json.dumps(oracle.INPUT_TYPES()))==json.loads((ROOT/'_schemas.json').read_text())[ID]['inputs']
    images={}
    for name,row in r['actual_image_fixtures'].items():
        p=Path(row['path']);assert digest(p)==row['sha256'];images[name]=torch.from_numpy(np.load(p,allow_pickle=False))
    cases=r['finite_trained_cases'];assert 0<len(cases)<=24
    assert {'default512','batch2','rectangular_fp16','rgba','small_objects','no_objects','multiple_objects'}<={c['fixture'] for c in cases}
    host_original=np.random.get_state();observed=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for index,c in enumerate(cases):
                values=dict(image=images[c['fixture']],resolution=c.get('resolution',512))
                prompt_id=r['issued_attempt_id']+'-sam-'+str(index)
                actual=await dispatch(pack,ID,values,prompt_id)
                o=fresh_real_guest_observation(r,index,values['image'],prompt_id)
                before=np.random.get_state()
                try:
                    np.random.set_state(observed_rng_state(o['numpy_rng_before']))
                    expected,native_trace=actual_native_trace(oracle,values,module)
                    assert rng_record(np.random.get_state())==o['numpy_rng_after_native_work']
                    same(actual,expected)
                    assert native_trace==json.loads(Path(o['actual_source_trace_path']).read_text())['source_return_events']
                finally:np.random.set_state(before)
                observed.append(dict(case=c,actual_guest_observation_sha256=o['actual_observation_sha256'],same_initial_and_final_rng=True,actual_native_guest_source_trace_equal=True))
            with pytest.raises(Exception):await dispatch(pack,ID,dict(image=images['default512'],resolution=10**30))
            result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=images['default512'],preprocessor='none',resolution=64))
            assert not ui and torch.equal(result[0],images['default512'])
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    try:asyncio.run(run())
    finally:np.random.set_state(host_original)
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_cases=observed,actual_numeric_refusal_and_recovery=1,
        native_host_rng_restored=True,actual_guest_rng_observer_source_sha256=r['actual_guest_rng_observer_source_sha256'],
        private_large_huge_type_dispatch='unregistered, separate actual bundle selection and trained cases required',
        actual_point_grid_mask_dictionary_morphology_color_trace_numerical_comparison=True,
        actual_native_constructor_error_and_registered_error_type_parity=None,whole_acceptance=False),indent=2)+'\n')
