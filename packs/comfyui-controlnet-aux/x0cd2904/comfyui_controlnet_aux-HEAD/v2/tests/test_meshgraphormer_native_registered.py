"""Future real registered refusals and retained native hand/MASK comparisons."""
import asyncio
import hashlib
import json
import os
from pathlib import Path

import execution
import pytest
import torch
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT=Path(__file__).resolve().parents[1]
ID='MeshGraphormer-DepthMapPreprocessor'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def issued_inputs():
    p=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT'])
    assert digest(p)==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(p.read_text())
    assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==[ID]
    for k in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','controller_cleanup_plan_sha256'):
        assert type(r[k]) is str and len(r[k])==64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required' and os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    assert digest(ROOT/'secure-nodes.json')==r['manifest_sha256']
    assert digest(ROOT/'_meshgraphormer/asset-selection.json')==r['asset_selection_sha256']
    selection=json.loads((ROOT/'_meshgraphormer/asset-selection.json').read_text())
    assert selection['approved'] is False and selection['constructor_supported'] is False
    source=json.loads((ROOT/'_meshgraphormer/native-sources.json').read_text())['hashes']
    assert source==r['native_source_hashes']
    pristine=Path(os.environ['AMY_AUX_PRISTINE'])
    for name,sha in source.items():assert digest(pristine/name)==sha
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_meshgraphormer',pack_id=r['pack_id'])
    assert set(pack.node_mappings[ID].SDK_PERMISSIONS)=={'raw','assets'}
    assert pack.node_mappings[ID].define_schema().node_id==ID
    return r,pack


async def dispatch(pack,node_id,values):
    cls=pack.node_mappings[node_id]
    mapped=await execution._async_map_node_over_list('amy-meshgraphormer',node_id,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui


def test_actual_registered_unselected_and_workload_refusals_recover():
    r,pack=issued_inputs();image=torch.ones(1,31,47,3)
    async def run():
        old=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for values,error in [(dict(image=image,resolution=64),'MeshGraphormer managed dependencies/resource/vendor/device/lifetime selection pending'),
                                 (dict(image=image,resolution=64,mask_expand=257),'mask expansion exceeds bounded compute'),
                                 (dict(image=image,resolution=64,rand_seed=1<<65),'seed integer work exceeds bounded compute')]:
                with pytest.raises(Exception,match=error):await dispatch(pack,ID,values)
                outputs,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
                assert len(outputs)==1 and torch.equal(outputs[0],image) and not ui
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=old
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_refusals=3,registered_recoveries=3,
        actual_pre_import_asset_rpc_observation=None,constructor_supported=False,whole_acceptance=False),indent=2)+'\n')


# Native numerical and registered trained cases are deliberately not runnable
# against the unsupported constructor. These are exact finite future inputs,
# not synthetic reference arrays or a replacement MediaPipe/model facade.
FUTURE_TRAINED_CASES=[
    dict(fixture='actual_two_hands',mask_type='based_on_depth',mask_expand=5,resolution=512,rand_seed=88),
    dict(fixture='actual_two_hands',mask_type='tight_bboxes',mask_expand=0,resolution=512,rand_seed=88),
    dict(fixture='actual_two_hands',mask_type='original',mask_expand=-3,resolution=512,rand_seed=88),
    dict(fixture='actual_no_hand',mask_type='original',mask_expand=5,resolution=512,rand_seed=88),
    dict(fixture='actual_rectangular_batch2_fp16',mask_type='tight_bboxes',mask_expand=5,resolution=512,rand_seed=88),
    dict(fixture='actual_rgba',mask_type='based_on_depth',mask_expand=5,resolution=512,rand_seed=88),
    dict(fixture='actual_two_hands',mask_type='original',mask_expand=0,resolution=512,rand_seed=89,detect_thr=.7,presence_thr=.7),
]


def future_real_trained_gate(native_wrapper,registered_pack,fixtures,issued_supported_contract):
    """Called only by a NEW supported/issued successor, never current packet."""
    assert issued_supported_contract['authorized'] is True
    assert issued_supported_contract['actual_mano_geometry_restricted_vendor_constructor_implemented_and_qualified'] is True
    assert issued_supported_contract['source_successor_sha256']!=issued_supported_contract['frozen_held_source_sha256']
    assert issued_supported_contract['actual_exclusive_args_hrnet_rng_mediapipe_lifetime'] is True
    for case in FUTURE_TRAINED_CASES:
        values={k:v for k,v in case.items() if k!='fixture'}
        values['image']=fixtures[case['fixture']]
        # Both oracles are genuine actual trained implementations. No unsafe
        # deserializer/ambient installer/acquisition is authorized by this fn.
        reference=native_wrapper.execute(**values)
        actual,ui=asyncio.run(dispatch(registered_pack,ID,values))
        assert not ui and type(actual) is type(reference) is tuple and len(actual)==2
        for a,b in zip(actual,reference):
            assert type(a) is type(b) is torch.Tensor and a.dtype==b.dtype and a.shape==b.shape
            assert torch.equal(a,b)
        assert reference[1].ndim==3  # native expand_mask reshapes N1HW to NHW
    # Remaining owner procedures are in NATIVE_MATRIX: constructor/order/code
    # proof, actual cache/RNG realm evidence, malformed/source errors and legal
    # PRIVATE actual model override, never a registered callable model bridge.
