"""Future real Zoe registered/native/constructor observations; NOT_RUN."""
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

ROOT=Path(__file__).resolve().parents[1];PRISTINE=Path(os.environ['AMY_AUX_PRISTINE'])
CLASSES={'Zoe-DepthMapPreprocessor':'Zoe_Depth_Map_Preprocessor','Zoe_DepthAnythingPreprocessor':'Zoe_Depth_Anything_Preprocessor'}
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
    assert digest(ROOT/'_modern_zoe/asset-selection.json')==r['asset_selection_sha256']
    hashes=json.loads((ROOT/'_modern_zoe/native-sources.json').read_text())['hashes'];assert r['native_source_hashes']==hashes
    for name,h in hashes.items():assert digest(PRISTINE/name)==h
    selected=json.loads((ROOT/'_modern_zoe/asset-selection.json').read_text())
    if positive:
        assert r['actual_new_supported_managed_pipeline_constructor_source_qualified'] is True
        assert r['actual_vendor_complete_bundle_operator_device_image_alias_lifetime_workspace_qualified'] is True
        assert selected['actual_constructor_supported'] is True
        assert 'actual Transformers AutoImageProcessor/ZoeDepthForDepthEstimation/depth-estimation pipeline and complete immutable bundle required' not in (ROOT/'_modern_zoe/selection.py').read_text()
        assert digest(ROOT/'_modern_zoe/selection.py')==r['new_constructor_selection_source_sha256']
    else:assert selected['actual_constructor_supported'] is False
    pack=packdb.load_pack(Path(r['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_modern_zoe',pack_id=r['pack_id'])
    for node in CLASSES:
        assert pack.node_mappings[node].define_schema().node_id==node
        assert set(pack.node_mappings[node].SDK_PERMISSIONS)=={'raw','assets'}
    return r,selected,pack

async def dispatch(pack,node,values,prompt_id='amy-modern-zoe'):
    cls=pack.node_mappings[node]
    mapped=await execution._async_map_node_over_list(prompt_id,node,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
    out=(await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result,out.ui

def same(actual,expected):
    result,ui=actual;assert not ui and type(result) is type(expected) is tuple and len(result)==1
    assert type(result[0]) is type(expected[0]) is torch.Tensor
    assert result[0].dtype==expected[0].dtype and result[0].shape==expected[0].shape and torch.equal(result[0],expected[0])

def test_actual_both_held_constructor_numeric_refusals_recoveries():
    r,selected,pack=issued();image=torch.ones(1,17,29,3)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for node in CLASSES:
                for values,message in [(dict(image=image),'Modern Zoe managed constructor source unsupported'),
                                       (dict(image=image,resolution=10**30),'numeric input exceeds bounded finite range')]:
                    with pytest.raises(Exception,match=message):await dispatch(pack,node,values)
                    result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=image,preprocessor='none',resolution=64))
                    assert not ui and torch.equal(result[0],image)
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_refusals=4,actual_registered_recoveries=4,
        actual_pre_import_asset_rpc_pipeline_model_calls=None,actual_constructor_supported=False,whole_acceptance=False),indent=2)+'\n')

def real_native_wrappers(native,helpers):
    import comfy.model_management as model_management
    class BindRealNativeImport(ast.NodeTransformer):
        def visit_ImportFrom(self,n):
            assert n.module=='custom_controlnet_aux.zoe'
            return None
    nodes=[]
    for name,cls in [('zoe.py','Zoe_Depth_Map_Preprocessor'),('depth_anything.py','Zoe_Depth_Anything_Preprocessor')]:
        p=PRISTINE/'node_wrappers'/name
        n=next(x for x in ast.parse(p.read_text()).body if isinstance(x,ast.ClassDef) and x.name==cls)
        nodes.append(BindRealNativeImport().visit(n))
    ns=dict(ZoeDetector=native.ZoeDetector,ZoeDepthAnythingDetector=native.ZoeDepthAnythingDetector,
        model_management=model_management,common_annotator_call=helpers.common_annotator_call,define_preprocessor_inputs=helpers.define_preprocessor_inputs,INPUT=helpers.INPUT)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(PRISTINE/'node_wrappers/zoe.py'),'exec'),ns)
    return {node:ns[cls]() for node,cls in CLASSES.items()}

def real_array(v):
    is_pil=isinstance(v,Image.Image)
    if is_pil:v=np.asarray(v)
    assert isinstance(v,np.ndarray)
    return dict(kind='PIL' if is_pil else 'ndarray',dtype=str(v.dtype),shape=list(v.shape),sha256=hashlib.sha256(v.tobytes()).hexdigest())

def native_observed_call(call,module):
    # Source-frame observation preserves all native function/model/pipeline
    # bodies and REAL aliasing. No substitute pipeline/depth fixture is used.
    assert sys.gettrace() is None;path=Path(module.__file__).resolve();events=[]
    def trace(frame,event,arg):
        if Path(frame.f_code.co_filename).resolve()!=path:return trace
        self=frame.f_locals.get('self');name=frame.f_code.co_name
        if self is None or event not in ('call','return'):return trace
        cls=type(self).__name__
        if name=='__init__':
            item=dict(event=event,class_name=cls,method=name,requested_model_name=frame.f_locals['model_name'])
            if event=='return' and hasattr(self,'pipe'):
                item['actual_pipeline_type']=type(self.pipe).__module__+'.'+type(self.pipe).__name__
                item['actual_model_type']=type(self.pipe.model).__module__+'.'+type(self.pipe.model).__name__
            events.append(item)
        elif name=='__call__' and event=='return':
            item=dict(event=event,class_name=cls,method=name,result=real_array(arg))
            if cls=='ZoeDetector':
                item['actual_pipeline_depth']=real_array(frame.f_locals['depth'])
                item['vmin']=float(frame.f_locals['vmin']);item['vmax']=float(frame.f_locals['vmax'])
                item['constant_depth_denominator']=bool(frame.f_locals['vmax']==frame.f_locals['vmin'])
                item['normalized_depth']=real_array(frame.f_locals['depth_array'])
                item['quantized_depth']=real_array(frame.f_locals['depth_image'])
            elif cls=='ZoeDepthAnythingDetector':
                child=frame.f_locals['detector']
                item['child_pipe_is_parent_pipe']=child.pipe is self.pipe
                item['child_device_equals_parent_device']=child.device==self.device
            events.append(item)
        return trace
    sys.settrace(trace)
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always');out=call()
        return out,events,[dict(type=w.category.__name__,message=str(w.message)) for w in captured]
    finally:sys.settrace(None)

def actual_guest_observation(r,index,node,image,prompt_id):
    assert r['actual_guest_pipeline_constructor_observer_qualified'] is True
    p=Path(r['actual_guest_source_observer_path']);assert digest(p)==r['actual_guest_source_observer_sha256']
    root=Path(r['actual_guest_observation_publication_root']).resolve();publication=root/str(index)/'PUBLICATION.json'
    assert publication.is_file() and not publication.is_symlink();row=json.loads(publication.read_text())
    p=root/row['relative_path'];assert p.resolve().is_relative_to(root) and p.is_file() and not p.is_symlink() and digest(p)==row['sha256']
    o=json.loads(p.read_text());assert o['actual_guest_execution'] is True and o['node_id']==node and o['case_index']==index
    assert o['actual_outer_dispatch_id']==prompt_id and o['issued_attempt_id']==r['issued_attempt_id']
    assert o['source_selection_sha256']==r['source_selection_sha256'] and o['observer_source_sha256']==r['actual_guest_source_observer_sha256']
    assert o['input_tensor_sha256']==hashlib.sha256(image.cpu().numpy().tobytes()).hexdigest()
    return o,row['sha256']

def future_real_trained_both_native_registered_gate():
    # NOT positive execution for the current hard-refusing packet; actual NEW
    # constructor source must preserve the per-call ZoeDetector construction.
    r,selected,pack=issued(True);assert r['native_module']=='custom_controlnet_aux.zoe'
    native=importlib.import_module(r['native_module'])
    assert Path(native.__file__).resolve()==(PRISTINE/'src/custom_controlnet_aux/zoe/__init__.py').resolve()
    module=importlib.import_module('custom_controlnet_aux.zoe.transformers')
    assert digest(Path(module.__file__))=='98bc0c2f889a4dab6de45c907387483d4981810eb571a28ad47f23a796c620ec'
    helpers=importlib.import_module(r['native_pack_utils_module']);assert Path(helpers.__file__).resolve()==(PRISTINE/'utils.py').resolve()
    import transformers
    assert digest(Path(transformers.__file__))==r['actual_transformers_vendor_module_sha256']
    assert r['actual_native_model_name']=='Intel/zoedepth-nyu-kitti'
    assert r['actual_native_complete_local_bundle_no_remote_qualified'] is True
    for row in r['actual_native_complete_bundle_files']:
        p=Path(row['path']);assert p.is_file() and digest(p)==row['sha256']
    oracles=real_native_wrappers(native,helpers)
    for node,oracle in oracles.items():
        assert json.loads(json.dumps(oracle.INPUT_TYPES()))==json.loads((ROOT/'_schemas.json').read_text())[node]['inputs']
    images={}
    for name,row in r['actual_image_fixtures'].items():
        p=Path(row['path']);assert digest(p)==row['sha256'];images[name]=torch.from_numpy(np.load(p,allow_pickle=False))
    cases=r['finite_trained_cases'];assert 0<len(cases)<=24
    for node in CLASSES:
        assert {'default512','batch2','odd_rectangular_fp16','rgba'}<={c['fixture'] for c in cases if c['node_id']==node}
    assert {'indoor','outdoor'}<={c.get('environment','indoor') for c in cases if c['node_id']=='Zoe_DepthAnythingPreprocessor'}
    report=[];direct=[]
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        try:
            for index,c in enumerate(cases):
                node=c['node_id'];values=dict(image=images[c['fixture']],resolution=c.get('resolution',512))
                if node=='Zoe_DepthAnythingPreprocessor':values['environment']=c.get('environment','indoor')
                expected,trace,warn=native_observed_call(lambda:oracles[node].execute(**values),module)
                prompt_id=r['issued_attempt_id']+'-zoe-'+str(index)
                same(await dispatch(pack,node,values,prompt_id),expected)
                constructors=[e for e in trace if e['method']=='__init__' and e['event']=='call']
                if node=='Zoe_DepthAnythingPreprocessor':
                    assert len(constructors)==1+values['image'].shape[0]
                    assert constructors[0]['class_name']=='ZoeDepthAnythingDetector'
                    assert all(e['requested_model_name']=='Intel/zoedepth-nyu-kitti' for e in constructors)
                    assert all(e['child_pipe_is_parent_pipe'] and e['child_device_equals_parent_device'] for e in trace if e['method']=='__call__' and e['class_name']=='ZoeDepthAnythingDetector')
                else:assert len(constructors)==1 and constructors[0]['class_name']=='ZoeDetector'
                internal=None
                if r.get('actual_guest_pipeline_constructor_observer_qualified') is True:
                    o,internal=actual_guest_observation(r,index,node,values['image'],prompt_id)
                    assert o['source_events']==trace and o['source_warning_events']==warn
                report.append(dict(case=c,native_source_events=trace,native_warning_events=warn,actual_guest_internal_constructor_pipeline_observation_sha256=internal))
            # Native private ignored filename/kwargs and deprecations. Both use
            # real actual vendor constructors, never a stubbed pipeline.
            for cls in (native.ZoeDetector,native.ZoeDepthAnythingDetector):
                detector=cls.from_pretrained(filename=['ignored_unhashable'],ignored_kwarg=True).to(r['actual_native_device'])
                array=np.asarray(images['default512'][0].cpu()*255,dtype=np.uint8)
                out,trace,warn=native_observed_call(lambda:detector(array,detect_resolution=512,output_type='pil'),module)
                assert isinstance(out,Image.Image)
                out2,trace2,warn2=native_observed_call(lambda:detector(None,detect_resolution=512,img=array,return_pil=False),module)
                assert isinstance(out2,np.ndarray) and any(w['type']=='DeprecationWarning' for w in warn2)
                with pytest.raises(ValueError,match='input_image must be defined'):detector(None)
                direct.append(dict(class_name=cls.__name__,actual_pil_result=real_array(out),actual_array_result=real_array(out2),actual_source_events=trace+trace2,actual_warnings=warn+warn2,ignored_filename_and_kwargs_native_only=True))
                del detector
            for node in CLASSES:
                with pytest.raises(Exception):await dispatch(pack,node,dict(image=images['default512'],resolution=10**30))
                result,ui=await dispatch(pack,'AIO_Preprocessor',dict(image=images['default512'],preprocessor='none',resolution=64))
                assert not ui and torch.equal(result[0],images['default512'])
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(actual_registered_cases=report,actual_native_private_cases=direct,
        actual_numeric_refusals_and_recoveries=2,actual_pipeline_constant_depth_case=None,actual_pipeline_nonPIL_depth_case=None,
        actual_selected_local_constructor_failure_error_order=None,actual_independent_pipeline_model_lifecycle_kernel_cleanup=None,whole_acceptance=False),indent=2)+'\n')
