"""Future genuine UniMatch retained-native/registered optical-flow gate."""
import ast
import asyncio
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
from unittest import mock

import execution
import numpy as np
import pytest
import torch
import comfy.model_management as model_management
from PIL import Image
from einops import rearrange
import torch.nn.functional as F
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT=Path(__file__).resolve().parents[1];PRISTINE=Path(os.environ['AMY_AUX_PRISTINE'])
ID='Unimatch_OptFlowPreprocessor';FILENAMES=('gmflow-scale1-mixdata.pth','gmflow-scale2-mixdata.pth','gmflow-scale2-regrefine6-mixdata.pth')
PREFIX='src/custom_controlnet_aux/unimatch/'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def issued_inputs(positive):
    p=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']);assert digest(p)==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r=json.loads(p.read_text());assert r['authorized'] is True and r['issuer']=='chat_f38536805264'
    assert r['execution_owner']=='chat_c98a0ab5c4ba' and r['node_ids']==[ID]
    for k in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256','controller_cleanup_plan_sha256'):
        assert type(r[k]) is str and len(r[k])==64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required' and os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    assert digest(ROOT/'secure-nodes.json')==r['manifest_sha256']
    assert digest(ROOT/'_unimatch/asset-selection.json')==r['asset_selection_sha256']
    selected=json.loads((ROOT/'_unimatch/asset-selection.json').read_text());assert selected['approved'] is positive
    sources=json.loads((ROOT/'_unimatch/native-sources.json').read_text())['hashes'];assert r['native_source_hashes']==sources
    for name,value in sources.items():assert digest(PRISTINE/name)==value
    if positive:
        assert r['actual_raw_model_member_reader_projection_cpu_storage_qualified'] is True
        assert r['actual_flow_image_realm_and_config_device_workspace_lifetime_qualified'] is True
        assert str(model_management.get_torch_device())==selected['device']
        assert selected['authority']==r['selection_authority']
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_unimatch',pack_id=r['pack_id'])
    assert set(pack.node_mappings[ID].SDK_PERMISSIONS)=={'raw','assets'}
    assert pack.node_mappings[ID].define_schema().node_id==ID
    return r,selected,pack


async def dispatch(pack,node_id,values):
    cls=pack.node_mappings[node_id]
    mapped=await execution._async_map_node_over_list('amy-unimatch',node_id,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui


def same_result(actual,expected):
    result,ui=actual;assert not ui and type(result) is type(expected) is tuple and len(result)==2
    for a,b in zip(result,expected):
        assert type(a) is type(b) is torch.Tensor and a.shape==b.shape and a.dtype==b.dtype
        assert torch.equal(a,b)


def retained_wrappers(native):
    tree=ast.parse((PRISTINE/'node_wrappers/unimatch.py').read_text())
    class RelocateNativeImport(ast.NodeTransformer):
        def visit_ImportFrom(self,node):return None
    classes=[RelocateNativeImport().visit(x) for x in tree.body if isinstance(x,ast.ClassDef)]
    ns=dict(torch=torch,np=np,F=F,rearrange=rearrange,model_management=model_management,
            UnimatchDetector=native.UnimatchDetector,flow_to_image=native.flow_to_image)
    exec(compile(ast.fix_missing_locations(ast.Module(body=classes,type_ignores=[])),str(PRISTINE/'node_wrappers/unimatch.py'),'exec'),ns)
    return ns[ID](),ns['MaskOptFlow']()


@contextlib.contextmanager
def pinned_acquisition(native,paths):
    acquired=[];real=torch.load
    def download(repo,filename):
        assert repo=='hr16/Unimatch' and filename in paths;acquired.append(filename);return str(paths[filename])
    def restricted_load(path,*args,**kwargs):
        assert Path(path) in paths.values() and kwargs.get('map_location')=='cpu' and not args
        kwargs['weights_only']=True
        return real(path,**kwargs)
    with mock.patch.object(native,'custom_hf_download',download),mock.patch.object(torch,'load',restricted_load):yield acquired


def test_actual_registered_assertion_unselected_and_workload_refusal_recovery():
    r,selected,pack=issued_inputs(False);image=torch.ones(2,25,41,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            cases=[(dict(image=image[:1],ckpt_name=FILENAMES[-1]),'Requiring as least two frames'),
                   (dict(image=image,ckpt_name=FILENAMES[-1]),'UniMatch checkpoint model-key/vendor/device/flow-lifetime selection pending'),
                   (dict(image=torch.ones(17,256,512,3),ckpt_name=FILENAMES[-1]),'workspace exceeds bounded compute')]
            for values,error in cases:
                with pytest.raises(Exception,match=error):await dispatch(pack,ID,values)
                outputs,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image[:1],preprocessor='none',resolution=64))
                assert not ui and len(outputs)==1 and torch.equal(outputs[0],image[:1])
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_refusals=3,registered_recoveries=3,
        actual_pre_asset_rpc_observation=None,whole_acceptance=False),indent=2)+'\n')


def test_future_actual_trained_native_registered_configs_directions_and_mask_consumer():
    r,selected,pack=issued_inputs(True);paths={}
    for filename in FILENAMES:
        row=selected['resources'][filename];path=Path(r['native_checkpoint_paths'][filename])
        assert path.is_file() and not path.is_symlink() and path.stat().st_size==row['bytes'] and digest(path)==row['sha256']
        for field in ('raw_container_evidence_sha256','projected_model_state_evidence_sha256','cpu_storage_evidence_sha256'):
            assert digest(Path(r['resource_evidence_paths'][filename][field]))==row[field]
        raw=torch.load(path,map_location='cpu',weights_only=True)
        assert list(raw)==row['raw_top_level_keys'] and 'state_dict' not in raw
        state=raw['model'];assert isinstance(state,dict) and not hasattr(state,'_metadata')
        assert list(state)==[v['key'] for v in row['model_state_records']]
        assert all(type(v) is torch.Tensor and v.device.type=='cpu' for v in state.values())
        paths[filename]=path
    assert r['native_unimatch_module']=='custom_controlnet_aux.unimatch'
    native=importlib.import_module(r['native_unimatch_module'])
    assert Path(native.__file__).resolve().parent==(PRISTINE/PREFIX).resolve()
    oracle,mask_oracle=retained_wrappers(native)
    schema=json.loads((ROOT/'_schemas.json').read_text())[ID]
    assert json.loads(json.dumps(oracle.INPUT_TYPES()))==schema['inputs']
    assert oracle.RETURN_TYPES==tuple(schema['return_types'])
    fixtures={}
    for name,row in r['trained_frame_fixtures'].items():
        path=Path(row['path']);assert digest(path)==row['sha256']
        # Actual owner-provided .npy images must be primitive numeric arrays,
        # never pickle/object data or fabricated inference outputs.
        array=np.load(path,allow_pickle=False)
        fixtures[name]=torch.from_numpy(array)
    cases=r['finite_trained_cases'];assert 0<len(cases)<=24
    assert {(c['ckpt_name'],c['backward_flow'],c['bidirectional_flow']) for c in cases}>={(f,a,b) for f in FILENAMES for a,b in [(False,False),(True,False),(False,True),(True,True)]}
    assert {'portrait_odd','rectangular_batch3','fp16','rgba'}<={c['fixture'] for c in cases}
    report=[];mask_report=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            with pinned_acquisition(native,paths):
                for c in cases:
                    values={k:v for k,v in c.items() if k!='fixture'};values['image']=fixtures[c['fixture']]
                    expected=oracle.estimate(**values);actual=await dispatch(pack,ID,values);same_result(actual,expected)
                    assert expected[0].shape[-1]==2
                    assert expected[0].shape[0]==len(values['image'])-1 and expected[1].shape[-1]==3
                    report.append(c)
                model=native.UnimatchDetector.from_pretrained(filename=FILENAMES[-1]).to(selected['device'])
                # Constructor MUST not gain eval/freeze. Native trained model
                # state and __call__ no_grad behavior remain separate facts.
                assert model.unimatch.training is True
                x=fixtures['portrait_odd'][0].cpu().numpy();x=np.asarray(x*255,dtype=np.uint8)
                with pytest.raises(AssertionError,match='must have the same size'):model(x,x[:-1])
                with pytest.raises(AssertionError,match='Couldn\x27t find hardcoded'):
                    # Pin only acquisition to an ACTUAL selected checkpoint;
                    # config assertion must still fail before network/load.
                    with mock.patch.object(native,'custom_hf_download',lambda *_:str(paths[FILENAMES[-1]])):
                        native.UnimatchDetector.from_pretrained(filename='unsupported.pth')
                flow,preview=model(x,x,output_type='np',pred_bidir_flow=True)
                assert flow.shape[-1]==2 and preview.shape[-1]==3
                with pytest.raises(Exception):model(np.ones((13,17,2),dtype=np.uint8),np.ones((13,17,2),dtype=np.uint8),output_type='np')
                # Real source downstream mutation test on actual trained flow.
                owned=torch.from_numpy(flow.copy())[None];owned[0,0,0,0]=1e8
                mask=torch.ones(1,1,*owned.shape[1:3]);before=owned.clone()
                expected=mask_oracle.mask_opt_flow(owned,mask)
                assert expected[0] is owned and owned[0,0,0,0]==0 and not torch.equal(owned,before)
                if r.get('mask_b1hw_registered_transport_qualified') is True:
                    incoming=before.clone();host_before=incoming.clone()
                    actual=await dispatch(pack,'MaskOptFlow',dict(optical_flow=incoming,mask=mask))
                    same_result(actual,expected)
                    mask_report.append(dict(actual_host_input_mutated=not torch.equal(incoming,host_before),
                        serialized_output_same_host_storage=actual[0][0].data_ptr()==incoming.data_ptr(),
                        host_guest_alias_equivalence_claimed=False))
                with pytest.raises(AssertionError,match='Not enough masks'):mask_oracle.mask_opt_flow(owned,mask[:0])
                for values,error in [(dict(image=fixtures['portrait_odd'][:1],ckpt_name=FILENAMES[-1]),'Requiring as least two frames')]:
                    with pytest.raises(Exception,match=error):await dispatch(pack,ID,values)
                    recovery=dict(image=fixtures['portrait_odd'],ckpt_name=FILENAMES[-1])
                    same_result(await dispatch(pack,ID,recovery),oracle.estimate(**recovery))
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_trained_cases=report,mask_consumer_observations=mask_report,
        bidirectional_member_selection_native_source_preserved=True,actual_guest_alias_lifetime_proof=None,
        registered_raw_reader_order_observation=None,wrong_channel_registered_type_error_parity=None,whole_acceptance=False),indent=2)+'\n')
