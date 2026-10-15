"""Future real registered refusal and native/trained gate. No authoring execution."""
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
ID='MediaPipe-FaceMeshPreprocessor'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def issued(positive=False):
    path=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']);assert digest(path)==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(path.read_text());assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==[ID]
    for k in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','controller_cleanup_plan_sha256'):
        assert type(r[k]) is str and len(r[k])==64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required' and os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    assert digest(ROOT/'secure-nodes.json')==r['manifest_sha256']
    assert digest(ROOT/'_facemesh/asset-selection.json')==r['asset_selection_sha256']
    hashes=json.loads((ROOT/'_facemesh/native-sources.json').read_text())['hashes'];assert r['native_source_hashes']==hashes
    for name,value in hashes.items():assert digest(PRISTINE/name)==value
    selected=json.loads((ROOT/'_facemesh/asset-selection.json').read_text())
    if positive:
        assert r['actual_new_managed_constructor_source_supported'] is True
        assert r['actual_vendor_code_resources_operator_image_realm_exclusive_engine_lifetime_qualified'] is True
        assert selected['actual_constructor_supported'] is True
        # This held source guard cannot be enabled by metadata. Positive gates
        # require a genuinely NEW implemented/qualified constructor successor.
        assert 'exact MediaPipe task buffer and old-solutions bundle definitions/resources required' not in (ROOT/'_facemesh/selection.py').read_text()
        assert digest(ROOT/'_facemesh/selection.py')==r['new_constructor_selection_source_sha256']
    else:assert selected['actual_constructor_supported'] is False
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_facemesh',pack_id=r['pack_id'])
    assert pack.node_mappings[ID].define_schema().node_id==ID and set(pack.node_mappings[ID].SDK_PERMISSIONS)=={'raw','assets'}
    return r,selected,pack

async def dispatch(pack,node,values):
    cls=pack.node_mappings[node]
    mapped=await execution._async_map_node_over_list('amy-facemesh',node,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui

def same(actual,expected):
    result,ui=actual;assert not ui and type(result) is type(expected) is tuple and len(result)==1
    assert type(result[0]) is type(expected[0]) is torch.Tensor
    assert result[0].dtype==expected[0].dtype and result[0].shape==expected[0].shape and torch.equal(result[0],expected[0])

def test_actual_registered_unsupported_constructor_and_numeric_refusal_recovery():
    r,selected,pack=issued();image=torch.ones(1,17,29,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for values,error in [(dict(image=image),'MediaPipe FaceMesh managed constructor source unsupported'),
                                 (dict(image=image,max_faces=10**30),'numeric input exceeds bounded finite range')]:
                with pytest.raises(Exception,match=error):await dispatch(pack,ID,values)
                out,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
                assert not ui and torch.equal(out[0],image)
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_refusals=2,actual_registered_recoveries=2,
        pre_import_asset_rpc_engine_call_observation=None,positive_constructor_supported=False,whole_acceptance=False),indent=2)+'\n')

def real_native_wrapper(native,helpers):
    t=(PRISTINE/'node_wrappers/mediapipe_face.py').read_text();tree=ast.parse(t)
    class BindRealNativeImport(ast.NodeTransformer):
        def visit_ImportFrom(self,n):return None
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Media_Pipe_Face_Mesh_Preprocessor')
    installer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install_deps')
    def no_installer(*args,**kwargs):raise RuntimeError('native dependency absent; auto-install refused')
    ns=dict(sys=sys,run_script=no_installer,MediapipeFaceDetector=native.MediapipeFaceDetector,
            common_annotator_call=helpers.common_annotator_call,define_preprocessor_inputs=helpers.define_preprocessor_inputs,INPUT=helpers.INPUT)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[installer,BindRealNativeImport().visit(cls)],type_ignores=[])),str(PRISTINE/'node_wrappers/mediapipe_face.py'),'exec'),ns)
    return ns['Media_Pipe_Face_Mesh_Preprocessor']()

def future_real_trained_native_registered_gate():
    # Not a runnable positive test for this held source. A real NEW source
    # constructor must first be produced and independently qualified by G/M.
    r,selected,pack=issued(True)
    assert r['native_module']=='custom_controlnet_aux.mediapipe_face'
    native=importlib.import_module(r['native_module']);assert Path(native.__file__).resolve().parent==(PRISTINE/'src/custom_controlnet_aux/mediapipe_face').resolve()
    common=importlib.import_module(r['native_module']+'.mediapipe_face_common')
    helpers=importlib.import_module(r['native_pack_utils_module']);assert Path(helpers.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    import mediapipe as mp
    assert common.mp is mp and common.USE_NEW_API is (r['actual_api_discriminator']=='tasks')
    # Real source probe and optional protobuf remain actual installed behavior;
    # no monkeypatch replaces APIs, landmarks, inference engines or delegates.
    vendor=Path(mp.__file__);assert digest(vendor)==r['native_vendor_module_sha256']
    original_task_path=common.FACE_LANDMARKER_TASK
    if common.USE_NEW_API:
        path=Path(r['native_task_path']);assert path.is_file() and not path.is_symlink() and digest(path)==r['native_task_sha256']
        assert path.stat().st_size==r['native_task_bytes']
        common.FACE_LANDMARKER_TASK=str(path)  # exact approved acquisition input only
    else:
        for row in r['old_solution_bundle_files']:
            p=Path(row['path']);assert p.is_file() and digest(p)==row['sha256']
    oracle=real_native_wrapper(native,helpers)
    assert json.loads(json.dumps(oracle.INPUT_TYPES()))==json.loads((ROOT/'_schemas.json').read_text())[ID]['inputs']
    images={}
    for name,row in r['actual_face_image_fixtures'].items():
        p=Path(row['path']);assert digest(p)==row['sha256'];images[name]=torch.from_numpy(np.load(p,allow_pickle=False))
    cases=r['finite_trained_cases'];assert 0<len(cases)<=24
    assert {1,10,50}<={c['max_faces'] for c in cases}
    assert {'default512','batch2','multiple_faces','no_face','small_face','rectangular_fp16','rgba'}<={c['fixture'] for c in cases}
    report=[];native_errors=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for c in cases:
                values={k:v for k,v in c.items() if k!='fixture'};values['image']=images[c['fixture']]
                same(await dispatch(pack,ID,values),oracle.detect(**values));report.append(c)
            face=np.asarray(images['multiple_faces'][0].cpu()*255,dtype=np.uint8)
            with common.FaceMeshWrapper() as engine:
                actual=engine.process(face)
                assert actual is not None and actual.multi_face_landmarks
                landmarks=actual.multi_face_landmarks[0];assert hasattr(landmarks,'landmark')
                assert all(hasattr(x,'x') and hasattr(x,'y') and hasattr(x,'z') for x in landmarks.landmark)
                assert isinstance(common.reverse_channels(face),np.ndarray)
                # Genuine vendor output supplies pupil field/protobuf shape.
                canvas=np.zeros_like(face);common.draw_pupils(canvas,landmarks,common.iris_landmark_spec,2)
                assert np.shares_memory(common.reverse_channels(canvas),canvas)
            for arr in (np.zeros((17,29),np.uint8),np.zeros((17,29,4),np.uint8)):
                with pytest.raises(ValueError):common.draw_pupils(arr,landmarks,common.iris_landmark_spec)
            # Real engine construction precedes native channel assertion.
            with pytest.raises(AssertionError):common.generate_annotation(np.zeros((17,29,4),np.uint8),1,.5)
            if common.USE_NEW_API:
                original=common.FACE_LANDMARKER_TASK;missing=Path(r['actual_missing_native_task_path']);assert not missing.exists()
                try:
                    common.FACE_LANDMARKER_TASK=str(missing)
                    with pytest.raises(FileNotFoundError) as error:common.FaceMeshWrapper()
                    native_errors.append(dict(type=type(error.value).__name__,before_new_api_try_fallback=True))
                finally:common.FACE_LANDMARKER_TASK=original
                if r.get('actual_present_invalid_task_case_qualified') is True:
                    row=r['actual_present_invalid_task_fixture'];p=Path(row['path']);assert p.is_file() and digest(p)==row['sha256']
                    original=common.FACE_LANDMARKER_TASK
                    try:
                        common.FACE_LANDMARKER_TASK=str(p)
                        if hasattr(mp,'solutions'):
                            # Actual vendor construction failure falls back to
                            # the real installed old engine, never a fake.
                            with common.FaceMeshWrapper() as engine:
                                assert hasattr(engine,'facemesh') and not hasattr(engine,'landmarker')
                                engine.process(face)
                            native_errors.append(dict(actual_constructor_failure_old_fallback=True))
                        else:
                            with pytest.raises(Exception) as error:common.FaceMeshWrapper()
                            native_errors.append(dict(actual_constructor_failure_rethrow=type(error.value).__name__))
                    finally:common.FACE_LANDMARKER_TASK=original
                if r.get('actual_process_failure_fixture_qualified') is True:
                    row=r['actual_process_failure_fixture'];p=Path(row['path']);assert digest(p)==row['sha256']
                    bad=np.load(p,allow_pickle=False)
                    with common.FaceMeshWrapper() as engine:
                        assert hasattr(engine,'landmarker') and not hasattr(engine,'facemesh')
                        with pytest.raises(Exception) as error:engine.process(bad)
                        if hasattr(mp,'solutions'):
                            assert isinstance(error.value,AttributeError) and 'facemesh' in str(error.value)
                        native_errors.append(dict(actual_process_failure_type=type(error.value).__name__,native_absent_facemesh=not hasattr(engine,'facemesh')))
            with pytest.raises(Exception):await dispatch(pack,ID,dict(image=images['default512'],max_faces=10**30))
            values=dict(image=images['default512'],max_faces=10,min_confidence=.5,resolution=512)
            same(await dispatch(pack,ID,values),oracle.detect(**values))
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    try:asyncio.run(run())
    finally:common.FACE_LANDMARKER_TASK=original_task_path
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_api_discriminator=r['actual_api_discriminator'],registered_cases=report,
        actual_native_errors=native_errors,native_source_close_calls_kernel_release_proof=None,
        real_constructor_process_failure_conditional_old_fallback_case=None,absent_native_facemesh_error_priority=None,
        actual_protobuf_visibility_presence_threshold_boundary_proof=None,whole_acceptance=False),indent=2)+'\n')
