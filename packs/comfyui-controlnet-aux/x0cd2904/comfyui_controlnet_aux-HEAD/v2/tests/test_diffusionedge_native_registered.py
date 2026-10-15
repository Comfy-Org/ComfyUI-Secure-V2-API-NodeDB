"""Future real retained native and registered diffusion gate, never run at authoring."""
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

import execution
import numpy as np
import pytest
import torch
import comfy.model_management as model_management
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT=Path(__file__).resolve().parents[1];PRISTINE=Path(os.environ['AMY_AUX_PRISTINE'])
ID='DiffusionEdge_Preprocessor';ENVIRONMENTS=('indoor','urban','natrual')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def inputs(positive):
    path=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']);assert digest(path)==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(path.read_text());assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==[ID]
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required' and os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    for k in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','controller_cleanup_plan_sha256'):
        assert type(r[k]) is str and len(r[k])==64
    assert digest(ROOT/'secure-nodes.json')==r['manifest_sha256']
    assert digest(ROOT/'_diffusionedge/asset-selection.json')==r['asset_selection_sha256']
    selected=json.loads((ROOT/'_diffusionedge/asset-selection.json').read_text());assert selected['approved'] is positive
    hashes=json.loads((ROOT/'_diffusionedge/native-sources.json').read_text())['hashes'];assert r['native_source_hashes']==hashes
    for name,value in hashes.items():assert digest(PRISTINE/name)==value
    if positive:
        assert r['actual_nested_ema_model_metadata_saved_cpu_storage_and_auxiliary_loads_qualified'] is True
        assert r['actual_yaml_vendor_device_rng_exclusive_invocation_workspace_qualified'] is True
        assert str(model_management.get_torch_device())==selected['device']
        assert selected['authority']==r['selection_authority']
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_diffusionedge',pack_id=r['pack_id'])
    assert set(pack.node_mappings[ID].SDK_PERMISSIONS)=={'raw','assets'}
    assert pack.node_mappings[ID].define_schema().node_id==ID
    return r,selected,pack

async def dispatch(pack,node_id,values):
    cls=pack.node_mappings[node_id]
    mapped=await execution._async_map_node_over_list('amy-diffusionedge',node_id,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui

def same(actual,expected):
    result,ui=actual;assert not ui and type(result) is type(expected) is tuple and len(result)==1
    assert type(result[0]) is type(expected[0]) is torch.Tensor
    assert result[0].dtype==expected[0].dtype and result[0].shape==expected[0].shape and torch.equal(result[0],expected[0])

def test_real_registered_unselected_and_guard_refusal_recovery():
    r,selected,pack=inputs(False);image=torch.ones(1,19,31,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for values,error in [(dict(image=image),'nested checkpoint/auxiliary resources/vendor/global lifetime selection pending'),
                                 (dict(image=image,patch_batch_size=10**30),'numeric input exceeds bounded finite range')]:
                with pytest.raises(Exception,match=error):await dispatch(pack,ID,values)
                outputs,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
                assert not ui and len(outputs)==1 and torch.equal(outputs[0],image)
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_refusals=2,registered_recoveries=2,
        actual_pre_import_asset_rpc_allocation_observation=None,whole_acceptance=False),indent=2)+'\n')

def retained_wrapper(native,helpers):
    t=(PRISTINE/'node_wrappers/diffusion_edge.py').read_text();tree=ast.parse(t)
    class BindRealNativeImport(ast.NodeTransformer):
        def visit_ImportFrom(self,node):return None
    classes=[BindRealNativeImport().visit(n) for n in tree.body if isinstance(n,ast.ClassDef)]
    installer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install_deps')
    def no_installer(*args,**kwargs):raise RuntimeError('qualified native dependency missing; auto-install refused')
    ns=dict(sys=sys,run_script=no_installer,model_management=model_management,DiffusionEdgeDetector=native.DiffusionEdgeDetector,
            common_annotator_call=helpers.common_annotator_call,define_preprocessor_inputs=helpers.define_preprocessor_inputs,INPUT=helpers.INPUT)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[installer,*classes],type_ignores=[])),str(PRISTINE/'node_wrappers/diffusion_edge.py'),'exec'),ns)
    return ns[ID]()

@contextlib.contextmanager
def actual_pinned_native_acquisition(native,lpips,cond,paths):
    real=torch.load
    def hf(repo,filename):assert repo=='hr16/Diffusion-Edge';return str(paths[filename])
    def auxiliary(filename):assert filename in paths;return str(paths[filename])
    def local_lpips(name,*args,**kwargs):assert name=='vgg_lpips';return str(paths['vgg.pth'])
    def restricted(path,*args,**kwargs):
        assert not args and Path(path) in paths.values()
        kwargs['weights_only']=True;kwargs['map_location']='cpu'
        return real(path,**kwargs)
    with mock.patch.object(native,'custom_hf_download',hf),mock.patch.object(lpips,'custom_torch_download',auxiliary),mock.patch.object(lpips,'get_ckpt_path',local_lpips),mock.patch.object(cond,'custom_torch_download',auxiliary),mock.patch.object(torch,'load',restricted):yield

def test_future_real_trained_native_registered_all_environments_and_constructor_math():
    r,selected,pack=inputs(True);paths={}
    for env in ENVIRONMENTS:
        for key,row in selected['environments'][env].items():
            path=Path(r['native_resource_paths'][env][key]);assert path.is_file() and not path.is_symlink()
            assert digest(path)==row['sha256'] and path.stat().st_size==row['bytes']
            for field in ('raw_container_evidence_sha256','saved_cpu_storage_evidence_sha256'):
                assert digest(Path(r['resource_evidence_paths'][env][key][field]))==row[field]
            if row['filename'] in paths:assert digest(paths[row['filename']])==digest(path)
            paths[row['filename']]=path
        raw=torch.load(paths[f'diffusion_edge_{env}.pt'],map_location='cpu',weights_only=True)
        assert isinstance(raw['ema'],dict) and isinstance(raw['model'],dict)
        assert any(k.startswith('ema_model.') for k in raw['ema'])
    assert r['native_module']=='custom_controlnet_aux.diffusion_edge'
    native=importlib.import_module(r['native_module'])
    assert Path(native.__file__).resolve().parent==(PRISTINE/'src/custom_controlnet_aux/diffusion_edge').resolve()
    lpips=importlib.import_module(r['native_module']+'.taming.modules.losses.lpips')
    cond=importlib.import_module(r['native_module']+'.denoising_diffusion_pytorch.mask_cond_unet')
    helpers=importlib.import_module(r['native_pack_utils_module'])
    assert Path(helpers.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    oracle=retained_wrapper(native,helpers)
    schema=json.loads((ROOT/'_schemas.json').read_text())[ID]
    assert json.loads(json.dumps(oracle.INPUT_TYPES()))==schema['inputs']
    frames={}
    for key,row in r['actual_image_fixtures'].items():
        p=Path(row['path']);assert digest(p)==row['sha256'];frames[key]=torch.from_numpy(np.load(p,allow_pickle=False))
    cases=r['finite_trained_cases'];assert 0<len(cases)<=24
    assert set(c['environment'] for c in cases)==set(ENVIRONMENTS)
    assert {1,4,16}<={c['patch_batch_size'] for c in cases}
    assert {'default512','batch2','odd_rectangular_fp16','rgba'}<={c['fixture'] for c in cases}
    cpu_rng=torch.get_rng_state();numpy_rng=np.random.get_state();cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None
    results=[];direct=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            with actual_pinned_native_acquisition(native,lpips,cond,paths):
                for c in cases:
                    values={k:v for k,v in c.items() if k!='fixture'};values['image']=frames[c['fixture']]
                    expected=oracle.execute(**values);same(await dispatch(pack,ID,values),expected);results.append(c)
                model=native.DiffusionEdgeDetector.from_pretrained().to(selected['device'])
                assert model.model.model.training is False
                original_type=model.model.cfg.sampler.sample_type
                x=np.asarray(frames['default512'][0].cpu()*255,dtype=np.uint8)
                try:
                    for mode in ('whole','slide'):
                        model.model.cfg.sampler.sample_type=mode
                        value=model(x,patch_batch_size=8,output_type='np')
                        assert type(value) is np.ndarray and value.dtype==np.uint8
                        direct.append(dict(sample_type=mode,shape=list(value.shape),sha256=hashlib.sha256(value.tobytes()).hexdigest(),registered_mode_widget=False))
                    model.model.cfg.sampler.sample_type='slide'
                    with pytest.raises(Exception):model(x,patch_batch_size=0,output_type='np')
                    with pytest.raises(Exception):model(np.ones((17,31,2),dtype=np.uint8),output_type='np')
                finally:model.model.cfg.sampler.sample_type=original_type
                with pytest.raises(Exception):await dispatch(pack,ID,dict(image=frames['default512'],patch_batch_size=10**30))
                good=dict(image=frames['default512'],environment='indoor',patch_batch_size=4,resolution=512)
                same(await dispatch(pack,ID,good),oracle.execute(**good))
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    try:asyncio.run(run())
    finally:
        torch.set_rng_state(cpu_rng);np.random.set_state(numpy_rng)
        if cuda_rng is not None:torch.cuda.set_rng_state_all(cuda_rng)
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_trained_cases=results,direct_native_whole_slide_cases=direct,
        actual_guest_rng_restore_or_process_cleanup_proof=None,raw_reader_model_vs_ema_scale_factor_order_observation=None,
        malformed_checkpoint_native_strict_errors_registered_parity=None,constructor_whole_mode_registered_transport='no source widget; native direct only, no guest bridge invented',whole_acceptance=False),indent=2)+'\n')

def test_future_actual_safe_negative_checkpoint_registered_error_and_recovery():
    # A separately issued finite negative phase binds ACTUAL owner-produced
    # immutable safe primitive/Tensor checkpoint variants in its selection.
    # No synthetic mapping, unsafe global or forged reader return is injected.
    r,selected,pack=inputs(True)
    assert r['phase']=='actual_safe_negative_checkpoint'
    bad_env=r['negative_environment'];good_env=r['recovery_environment'];assert bad_env!=good_env
    paths={}
    for env in ENVIRONMENTS:
        for key,row in selected['environments'][env].items():
            p=Path(r['native_resource_paths'][env][key]);assert digest(p)==row['sha256'] and p.stat().st_size==row['bytes']
            if row['filename'] in paths:assert digest(paths[row['filename']])==digest(p)
            paths[row['filename']]=p
    assert r['native_module']=='custom_controlnet_aux.diffusion_edge'
    native=importlib.import_module(r['native_module']);assert Path(native.__file__).resolve().parent==(PRISTINE/'src/custom_controlnet_aux/diffusion_edge').resolve()
    lpips=importlib.import_module(r['native_module']+'.taming.modules.losses.lpips')
    cond=importlib.import_module(r['native_module']+'.denoising_diffusion_pytorch.mask_cond_unet')
    helpers=importlib.import_module(r['native_pack_utils_module']);assert Path(helpers.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    oracle=retained_wrapper(native,helpers)
    p=Path(r['negative_frame_fixture']['path']);assert digest(p)==r['negative_frame_fixture']['sha256']
    image=torch.from_numpy(np.load(p,allow_pickle=False));values=dict(image=image,environment=bad_env,patch_batch_size=4,resolution=512)
    observed={}
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            with actual_pinned_native_acquisition(native,lpips,cond,paths):
                try:oracle.execute(**values)
                except Exception as e:observed.update(native_type=type(e).__name__,native_message=str(e))
                else:raise AssertionError('actual negative native checkpoint did not fail')
                assert observed['native_type']==r['negative_expected_native_type']
                assert r['negative_expected_message_fragment'] in observed['native_message']
                with pytest.raises(Exception,match=r['negative_registered_message_regex']) as error:await dispatch(pack,ID,values)
                observed.update(actual_registered_exception_type=type(error.value).__name__,actual_registered_exception_message=str(error.value),remote_native_exception_type_proof=None)
                good=dict(image=image,environment=good_env,patch_batch_size=4,resolution=512)
                same(await dispatch(pack,ID,good),oracle.execute(**good));observed['genuine_registered_recovery']=True
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    cpu=torch.get_rng_state();np_state=np.random.get_state();cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None
    try:asyncio.run(run())
    finally:
        torch.set_rng_state(cpu);np.random.set_state(np_state)
        if cuda is not None:torch.cuda.set_rng_state_all(cuda)
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_safe_negative_checkpoint=observed,whole_acceptance=False),indent=2)+'\n')
