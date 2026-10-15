"""Future genuine V2 native/registered gates. No execution in source delivery."""
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
PRISTINE=Path(os.environ['AMY_AUX_PRISTINE'])
ID='DepthAnythingV2Preprocessor'
FILENAMES=('depth_anything_v2_vitg.pth','depth_anything_v2_vitl.pth','depth_anything_v2_vitb.pth','depth_anything_v2_vits.pth')
SMALL=FILENAMES[-1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def issued(positive=False):
    p=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT'])
    assert digest(p)==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(p.read_text())
    assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==[ID]
    for k in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256',
              'controller_cleanup_plan_sha256','source_to_installed_sdk_manifest_sha256'):
        assert type(r[k]) is str and len(r[k])==64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    assert digest(ROOT/'secure-nodes.json')==r['manifest_sha256']
    assert digest(ROOT/'_depth_v2_asset_selection.json')==r['asset_selection_sha256']
    for name,h in r['selected_graph_hashes'].items():
        assert name.startswith('_depth_anything_v2') and digest(ROOT/name)==h
    assert len(r['selected_graph_hashes'])==16
    for name,h in r['native_source_hashes'].items():assert digest(PRISTINE/name)==h
    selected=json.loads((ROOT/'_depth_v2_asset_selection.json').read_text())
    if positive:
        assert selected['approved'] is True and selected['assets'][SMALL]['approved'] is True
        authority=Path(r['invocation_authority_receipt_path'])
        assert digest(authority)==r['invocation_authority_receipt_sha256']==selected['issued_invocation_receipt_sha256']
        a=json.loads(authority.read_text());assert a['authorized'] is True
        assert a['issued_attempt_id']==r['issued_attempt_id'] and a['node_ids']==[ID]
        assert a['issuer']=='chat_f38536805264' and a['execution_owner']=='chat_c98a0ab5c4ba'
        for k in ('actual_raw_flat_state_order_dtype_shape_cpu_storage_equivalence_qualified',
                  'actual_sdk_transport_manifest_qualified','actual_device_auto_policy_image_realm_qualified',
                  'actual_model_workspace_exclusive_lifetime_cleanup_qualified','actual_native_no_remote_cache_qualified'):
            assert r[k] is True
    else:assert selected['approved'] is False
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_depth_v2_caller',pack_id=r['pack_id'])
    cls=pack.node_mappings[ID]
    assert cls.define_schema().node_id==ID and set(cls.SDK_PERMISSIONS)=={'raw','assets'}
    return r,selected,pack

async def dispatch(pack,node,values,prompt):
    cls=pack.node_mappings[node]
    mapped=await execution._async_map_node_over_list(prompt,node,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui

async def recovery(pack,image,prompt):
    result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64),prompt)
    assert not ui and type(result) is tuple and torch.equal(result[0],image)

def published_guest_observation(r,index,prompt,image):
    # No controller/native-only observer is promoted to guest-internal proof.
    assert r['actual_guest_asset_graph_observer_qualified'] is True
    source=Path(r['actual_guest_observer_source_path'])
    assert digest(source)==r['actual_guest_observer_source_sha256']
    root=Path(r['actual_guest_observation_root']).resolve()
    publication=root/str(index)/'PUBLICATION.json';assert publication.is_file() and not publication.is_symlink()
    row=json.loads(publication.read_text());p=root/row['relative_path']
    assert p.resolve().is_relative_to(root) and p.is_file() and not p.is_symlink() and digest(p)==row['sha256']
    event=json.loads(p.read_text())
    assert event['actual_guest_execution'] is True and event['node_id']==ID
    assert event['issued_attempt_id']==r['issued_attempt_id'] and event['outer_dispatch_id']==prompt
    assert event['input_sha256']==hashlib.sha256(image.cpu().numpy().tobytes()).hexdigest()
    assert event['source_selection_sha256']==r['source_selection_sha256']
    assert event['observer_source_sha256']==r['actual_guest_observer_source_sha256']
    return event

def test_real_registered_unselected_modes_refusal_recovery():
    r,selected,pack=issued();image=torch.ones(1,17,29,3);records=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for i,name in enumerate(FILENAMES):
                prompt=r['issued_attempt_id']+'-unselected-'+str(i)
                with pytest.raises(Exception,match='DepthAnythingV2 managed selection unapproved'):
                    await dispatch(pack,ID,dict(image=image,ckpt_name=name),prompt)
                await recovery(pack,image,prompt+'-recovery')
                record=dict(filename=name,actual_registered_refusal=True,actual_recovery=True,actual_guest_pre_import_rpc_allocation_observation=None)
                if r.get('actual_guest_asset_graph_observer_qualified') is True:
                    event=published_guest_observation(r,i,prompt,image)
                    assert event['new_depth_import_calls']==event['asset_rpc_calls']==event['model_allocation_calls']==0
                    record['actual_guest_pre_import_rpc_allocation_observation']=event
                records.append(record)
            with pytest.raises(Exception,match='numeric input exceeds bounded finite range'):
                await dispatch(pack,ID,dict(image=image,resolution=10**30),r['issued_attempt_id']+'-numeric')
            await recovery(pack,image,r['issued_attempt_id']+'-numeric-recovery')
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(records=records,actual_refusals=5,actual_recoveries=5,
        positive_trained_cases='NOT_RUN',constructor_order_parity=False,whole_acceptance=False),indent=2)+'\n')

def native_wrapper(native,helpers):
    import comfy.model_management as model_management
    p=PRISTINE/'node_wrappers/depth_anything_v2.py'
    cls=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Depth_Anything_V2_Preprocessor')
    class BindActualNativeImport(ast.NodeTransformer):
        def visit_ImportFrom(self,n):
            assert n.module=='custom_controlnet_aux.depth_anything_v2';return None
    ns=dict(DepthAnythingV2Detector=native.DepthAnythingV2Detector,model_management=model_management,
            common_annotator_call=helpers.common_annotator_call,define_preprocessor_inputs=helpers.define_preprocessor_inputs,INPUT=helpers.INPUT)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[BindActualNativeImport().visit(cls)],type_ignores=[])),str(p),'exec'),ns)
    return ns['Depth_Anything_V2_Preprocessor']()

def observe_native_constructor(call,native,r):
    assert sys.getprofile() is None
    path=Path(native.__file__).resolve();events=[]
    def profile(frame,event,arg):
        if event=='call' and Path(frame.f_code.co_filename).resolve()==path:
            if frame.f_code.co_name in ('from_pretrained','__init__','to','__call__'):
                events.append(frame.f_code.co_name)
        if event=='return' and frame.f_code is native.custom_hf_download.__code__:
            expected=Path(r['native_verified_small_payload']).resolve()
            assert Path(arg).resolve()==expected and digest(expected)==r['verified_small_sha256']
            events.append('actual_native_cached_payload_return')
    sys.setprofile(profile)
    try:return call(),events
    finally:sys.setprofile(None)

def future_real_trained_small_native_registered_gate():
    r,selected,pack=issued(True)
    assert r['native_module']=='custom_controlnet_aux.depth_anything_v2'
    native=importlib.import_module(r['native_module'])
    assert Path(native.__file__).resolve()==(PRISTINE/'src/custom_controlnet_aux/depth_anything_v2/__init__.py').resolve()
    helpers=importlib.import_module(r['native_pack_utils_module'])
    assert Path(helpers.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    payload=Path(r['native_verified_small_payload'])
    assert payload.stat().st_size==99218434 and digest(payload)=='715fade13be8f229f8a70cc02066f656f2423a59effd0579197bbf57860e1378'
    assert r['verified_small_sha256']==digest(payload)
    cases=r['native_registered_image_cases'];assert 1<=len(cases)<=12
    wrapper=native_wrapper(native,helpers);records=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for i,case in enumerate(cases):
                p=Path(case['input_npy_path']);assert digest(p)==case['input_npy_sha256']
                array=np.load(p,allow_pickle=False);assert array.dtype in (np.float16,np.float32) and array.ndim==4 and array.shape[-1] in (3,4)
                image=torch.from_numpy(array.copy())
                values=dict(image=image,ckpt_name=SMALL)
                # Omit resolution to exercise the real registered 512 default.
                if 'resolution' in case:values['resolution']=case['resolution']
                expected,events=observe_native_constructor(lambda:wrapper.execute(**values),native,r)
                assert 'actual_native_cached_payload_return' in events and 'from_pretrained' in events and 'to' in events
                prompt=r['issued_attempt_id']+'-small-'+str(i)
                result,ui=await dispatch(pack,ID,values,prompt)
                assert not ui and type(result) is type(expected) is tuple and len(result)==1
                assert type(result[0]) is type(expected[0]) is torch.Tensor
                assert result[0].dtype==expected[0].dtype and result[0].shape==expected[0].shape and torch.equal(result[0],expected[0])
                observation=None
                if r.get('actual_guest_asset_graph_observer_qualified') is True:
                    observation=published_guest_observation(r,i,prompt,image)
                    assert observation['filename']==SMALL and observation['asset_digest']==digest(payload)
                    assert observation['model_constructor']=='DepthAnythingV2' and observation['strict_load'] is True
                    assert observation['eval_called'] is True and observation['infer_image_input_size']==518 and observation['max_depth']==1
                    assert observation['actual_state_correspondence_receipt_sha256']==selected['evidence']['restricted_raw_state_correspondence']
                records.append(dict(case=case['label'],actual_native_constructor_events=events,actual_registered_output_equal=True,actual_guest_observation=observation))
                await recovery(pack,image,prompt+'-recovery')
            with pytest.raises(Exception,match='numeric input exceeds bounded finite range'):
                await dispatch(pack,ID,dict(image=torch.ones(1,17,29,3),ckpt_name=SMALL,resolution=10**30),r['issued_attempt_id']+'-guard')
            await recovery(pack,torch.ones(1,17,29,3),r['issued_attempt_id']+'-guard-recovery')
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(records=records,
        default_model='Large remains unselected; trained Small uses explicit ckpt_name with real resolution default',
        native_allocation_before_decode=True,managed_decode_before_allocation=True,constructor_failure_order_parity=False,
        guest_internal_proof_requires_actual_observer=True,actual_additional_strict_state_negative_cases=None,whole_acceptance=False),indent=2)+'\n')

def future_real_strict_state_registered_error_gate():
    # Each deliberately invalid state is a separately verified, owner-sealed
    # negative pack snapshot; the test never edits selections or assets.
    r,selected,pack=issued(True)
    native=importlib.import_module(r['native_module'])
    assert Path(native.__file__).resolve()==(PRISTINE/'src/custom_controlnet_aux/depth_anything_v2/__init__.py').resolve()
    cases=r['actual_strict_state_negative_cases'];assert 1<=len(cases)<=4
    records=[];image=torch.ones(1,17,29,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for i,case in enumerate(cases):
                assert case['authorized_qualified_negative_asset_scope'] is True
                p=Path(case['verified_negative_payload']);assert digest(p)==case['verified_sha256']
                state=torch.load(p,map_location='cpu',weights_only=True)
                assert isinstance(state,dict) and not hasattr(state,'_metadata') and 'state_dict' not in state
                assert state and all(type(k) is str and isinstance(v,torch.Tensor) and v.device.type=='cpu' for k,v in state.items())
                model=native.DepthAnythingV2(**native.model_configs[SMALL])
                try:model.load_state_dict(state,strict=True)
                except RuntimeError as error:native_error=str(error)
                else:raise AssertionError('actual negative state unexpectedly accepted by native strict load')
                finally:del model
                snapshot=Path(case['stable_snapshot_path']);selection_path=snapshot/'_depth_v2_asset_selection.json'
                assert digest(selection_path)==case['asset_selection_sha256']
                candidate=json.loads(selection_path.read_text())
                assert candidate['assets'][SMALL]['verified_sha256']==digest(p)
                assert candidate['evidence']['restricted_raw_state_correspondence']==case['actual_raw_reader_correspondence_sha256']
                assert digest(snapshot/'secure-nodes.json')==case['manifest_sha256']
                negative=packdb.load_pack(snapshot,mount_name=case['mount_name'],pack_id=case['pack_id'])
                prompt=r['issued_attempt_id']+'-strict-'+str(i)
                with pytest.raises(Exception) as captured:
                    await dispatch(negative,ID,dict(image=image,ckpt_name=SMALL),prompt)
                # RPC may wrap the native RuntimeError; require the actual
                # original diagnostic, not exception-class equality across RPC.
                assert native_error in str(captured.value)
                await recovery(negative,image,prompt+'-recovery')
                records.append(dict(label=case['label'],actual_native_strict_error=native_error,
                    registered_diagnostic_contains_native=True,registered_exception_type=type(captured.value).__name__,actual_recovery=True))
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(records=records,
        raw_container_and_constructor_failure_order_parity=False,whole_acceptance=False),indent=2)+'\n')
