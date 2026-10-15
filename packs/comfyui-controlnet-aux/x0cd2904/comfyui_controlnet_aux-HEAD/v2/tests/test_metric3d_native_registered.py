"""Future genuine trained Metric3D/native/registered cases. Authored NOT_RUN."""
import ast
import asyncio
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from unittest import mock

import comfy
import comfy.model_management as model_management
import comfy.utils
import execution
import numpy as np
import pytest
import torch
from PIL import Image
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT=Path(__file__).resolve().parents[1]
PRISTINE=Path(os.environ['AMY_AUX_PRISTINE'])
IDS=('Metric3D-DepthMapPreprocessor','Metric3D-NormalMapPreprocessor')
BACKBONES=('vit-small','vit-large','vit-giant2')
PREFIX='src/custom_controlnet_aux/metric3d/'


def file_digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def owning_inputs(positive):
    data=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(data)
    assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==list(IDS)
    for key in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','controller_cleanup_plan_sha256'):
        assert type(r[key]) is str and len(r[key])==64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    assert file_digest(ROOT/'secure-nodes.json')==r['manifest_sha256']
    assert file_digest(ROOT/'_metric3d/asset-selection.json')==r['asset_selection_sha256']
    selected=json.loads((ROOT/'_metric3d/asset-selection.json').read_text())
    assert selected['approved'] is positive
    sources=json.loads((ROOT/'_metric3d/native-sources.json').read_text())['hashes']
    assert r['native_source_hashes']==sources
    for name,digest in sources.items():assert file_digest(PRISTINE/name)==digest
    if positive:
        assert r['actual_raw_model_state_dict_cpu_storage_qualified'] is True
        assert r['actual_config_environment_internal_device_and_exclusive_state_cache_qualified'] is True
        assert str(model_management.get_torch_device())==selected['device']
        for key in ('runtime_abi_evidence_sha256','preimport_environment_authority_sha256','config_evaluation_authority_sha256',
                    'exclusive_state_cache_lifetime_sha256','device_correspondence_sha256','current_invocation_admission_sha256',
                    'restricted_vendor_source_evidence_sha256','fixed_crop_workspace_admission_sha256','internal_device_policy_sha256'):
            assert r[key]==selected[key] and type(r[key]) is str and len(r[key])==64
        for module,digest in [('torch.serialization','b50f806f9aee71df8c412db95332218deca1ebcb74e694d3e5241da8eefc056c'),
                              ('torch._weights_only_unpickler','bc2f0fdcb5657109d066951d58864ec4227c8f65ce4d1f144015062ef097e4b2')]:
            assert file_digest(Path(importlib.import_module(module).__file__))==digest
        assert not torch.serialization.get_safe_globals()
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_metric3d',pack_id=r['pack_id'])
    for node_id in IDS:assert set(pack.node_mappings[node_id].SDK_PERMISSIONS)=={'raw','assets'}
    return r,selected,sources,pack


async def dispatch(pack,node_id,values):
    cls=pack.node_mappings[node_id]
    mapped=await execution._async_map_node_over_list('amy-metric3d',node_id,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui


def same_result(actual,expected):
    outputs,ui=actual
    assert type(outputs) is type(expected) is tuple and len(outputs)==1 and not ui
    a,b=outputs[0],expected[0]
    assert type(a) is type(b) is torch.Tensor
    assert a.dtype==b.dtype and a.shape==b.shape and torch.equal(a,b)


def native_wrappers(native,utils):
    tree=ast.parse((PRISTINE/'node_wrappers/metric3d.py').read_text())
    classes=[x for x in tree.body if isinstance(x,ast.ClassDef)]
    class RelocatedImport(ast.NodeTransformer):
        def visit_ImportFrom(self,node):return None
    classes=[RelocatedImport().visit(x) for x in classes]
    annotator=next(x for x in ast.parse((PRISTINE/'utils.py').read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='common_annotator_call')
    ns=dict(torch=torch,np=np,comfy=comfy,model_management=model_management,Metric3DDetector=native.Metric3DDetector,
            INPUT=utils.INPUT,MAX_RESOLUTION=utils.MAX_RESOLUTION,define_preprocessor_inputs=utils.define_preprocessor_inputs)
    # Actual retained class and annotator algorithms; ONLY local import binding
    # is relocated. Real native constructors and inference stay in this oracle.
    exec(compile(ast.fix_missing_locations(ast.Module(body=[annotator,*classes],type_ignores=[])),str(PRISTINE/'node_wrappers/metric3d.py'),'exec'),ns)
    return dict(zip(IDS,[ns['Metric3D_Depth_Map_Preprocessor'](),ns['Metric3D_Normal_Map_Preprocessor']()]))


@contextlib.contextmanager
def pinned_native_acquisition(native,paths):
    acquired=[]
    def download(repo,filename):
        assert repo=='JUGGHM/Metric3D' and filename in paths
        acquired.append((repo,filename))
        return str(paths[filename])
    with mock.patch.object(native,'custom_hf_download',download):yield acquired


def test_actual_registered_unselected_refusal_and_recovery():
    r,selection,sources,pack=owning_inputs(False)
    image=torch.ones(1,25,41,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for node_id in IDS:
                with pytest.raises(Exception,match='Metric3D raw checkpoint/config/vendor/device/state-cache selection pending'):
                    await dispatch(pack,node_id,dict(image=image,resolution=64))
                outputs,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
                assert len(outputs)==1 and torch.equal(outputs[0],image) and not ui
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_refusals=2,registered_recoveries=2,
        actual_pre_asset_rpc_observation=None,whole_acceptance=False),indent=2)+'\n')


def test_future_actual_trained_metric3d_native_registered_and_state_cache():
    r,selected,sources,pack=owning_inputs(True)
    paths={}
    for backbone in BACKBONES:
        row=selected['resources'][backbone];path=Path(r['native_checkpoint_paths'][backbone])
        assert row['approved'] is True and row['raw_container_approved'] is True
        assert path.is_file() and not path.is_symlink() and path.stat().st_size==row['bytes']
        assert file_digest(path)==row['sha256'] and str(path)==row['native_model_path_discriminator']
        for field in ('raw_container_evidence_sha256','saved_storage_correspondence_sha256','native_path_regex_correspondence_sha256'):
            assert file_digest(Path(r['resource_evidence_paths'][backbone][field]))==row[field]
        raw=torch.load(path,map_location='cpu',weights_only=True)
        assert type(raw).__name__==r['raw_mapping_kinds'][backbone] and list(raw)==row['raw_top_level_keys']
        state=raw['model_state_dict']
        assert type(state).__name__==row['state_mapping_kind'] and list(state)==row['state_keys']
        assert all(type(v) is torch.Tensor and v.device.type=='cpu' for v in state.values())
        assert sum(v.numel()*v.element_size() for v in state.values())==row['tensor_bytes']
        paths[row['source_filename']]=path
    os.environ['NPU_DEVICE_COUNT']='0';os.environ['MMCV_WITH_OPS']='0'
    assert r['native_metric3d_module']=='custom_controlnet_aux.metric3d'
    native=importlib.import_module(r['native_metric3d_module'])
    assert Path(native.__file__).resolve().parent==(PRISTINE/PREFIX).resolve()
    reused=json.loads((ROOT/'_uniformer/native-sources.json').read_text())['hashes']
    for name,module in list(sys.modules.items()):
        if name.startswith(('custom_controlnet_aux.metric3d','custom_mmpkg')):
            path=getattr(module,'__file__',None)
            if path and Path(path).suffix=='.py':
                origin=str(Path(path).resolve().relative_to(PRISTINE))
                assert file_digest(Path(path))==(sources if name.startswith('custom_controlnet_aux.metric3d') else reused)[origin]
    utils=importlib.import_module(r['native_wrapper_utils_module'])
    assert Path(utils.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    assert file_digest(Path(utils.__file__))==sources['utils.py']
    oracles=native_wrappers(native,utils)
    schemas=json.loads((ROOT/'_schemas.json').read_text())
    for node_id in IDS:
        assert json.loads(json.dumps(oracles[node_id].INPUT_TYPES()))==schemas[node_id]['inputs']
        assert oracles[node_id].RETURN_TYPES==tuple(schemas[node_id]['return_types'])
        actual_schema=pack.node_mappings[node_id].define_schema()
        assert actual_schema.node_id==node_id
    fixture=Path(r['trained_image_fixture']['path']);assert file_digest(fixture)==r['trained_image_fixture']['sha256']
    rgb=np.array(Image.open(fixture).convert('RGB'));assert rgb.shape[0]!=rgb.shape[1]
    images=dict(rectangular=torch.from_numpy(rgb.astype(np.float32)/255)[None])
    images['batch2']=images['rectangular'].repeat(2,1,1,1)
    images['fp16']=images['rectangular'].to(torch.float16)
    images['rgba']=torch.cat((images['rectangular'],torch.ones_like(images['rectangular'][...,:1])),dim=-1)
    planned=r['finite_trained_cases']
    assert planned and len(planned)<=24
    assert {(c['node_id'],c['backbone']) for c in planned}=={(i,b) for i in IDS for b in BACKBONES}
    assert {'rectangular','batch2','fp16','rgba'}<={c['image'] for c in planned}
    assert any(c['resolution']==512 and c['fx']==c['fy']==1000 for c in planned)
    reports=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            with pinned_native_acquisition(native,paths) as acquired:
                for c in planned:
                    values=dict(image=images[c['image']],backbone=c['backbone'],resolution=c['resolution'],fx=c['fx'],fy=c['fy'])
                    reference=oracles[c['node_id']].execute(**values)
                    same_result(await dispatch(pack,c['node_id'],values),reference)
                    reports.append(c)
                # Direct genuine trained calls separately exercise mutable
                # default cache aliasing and unchanged PIL/tuple/type errors.
                model=native.Metric3DDetector.from_pretrained(filename=selected['resources']['vit-small']['source_filename']).to(selected['device'])
                cache=native.predict_depth_normal.__defaults__[-1]
                old=dict(cache)
                try:
                    _,_,first=native.predict_depth_normal(model.model,model.cfg,rgb,fx=901,fy=1099)
                    _,_,second=native.predict_depth_normal(model.model,model.cfg,rgb,fx=1000,fy=1000)
                    assert first is second is cache and cache['img'] is rgb
                    assert cache['intrinsic']==[1000,1000,rgb.shape[1]/2,rgb.shape[0]/2]
                    direct=model(rgb,detect_resolution=64,output_type='pil')
                    assert type(direct) is tuple and len(direct)==2 and all(isinstance(x,Image.Image) for x in direct)
                    assert isinstance(model(rgb,detect_resolution=64,output_type='pil',depth_and_normal=False),Image.Image)
                    with pytest.raises(NotImplementedError):native.load_model('vit-unsupported',paths[selected['resources']['vit-small']['source_filename']])
                    with pytest.raises(Exception):model(np.ones((17,23,2),dtype=np.uint8),detect_resolution=64)
                finally:
                    cache.clear();cache.update(old)  # issued exclusive owner lifetime only
                for node_id in IDS:
                    with pytest.raises(Exception,match='bounded'):
                        await dispatch(pack,node_id,dict(image=images['rectangular'],resolution=16384))
                    values=dict(image=images['rectangular'],backbone='vit-small',resolution=64,fx=1000,fy=1000)
                    same_result(await dispatch(pack,node_id,values),oracles[node_id].execute(**values))
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_trained_comparisons=reports,registered_guard_refusals=2,
        registered_recoveries=2,native_default_cache_alias_observed=True,
        guest_default_cache_alias_observation=None,raw_decoder_guest_order_observation=None,
        strict_false_missing_unexpected_error_fixture_results=None,
        missing_native_checkpoint_and_optimizer_scheduler_scaler_quirk_results=None,
        actual_native_typed_shape_error_results=None,whole_acceptance=False),indent=2)+'\n')
