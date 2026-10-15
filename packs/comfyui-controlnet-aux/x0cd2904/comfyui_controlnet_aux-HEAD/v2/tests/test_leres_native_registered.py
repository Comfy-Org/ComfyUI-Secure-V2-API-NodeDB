"""Future genuine trained LeReS/boost/native/registered gate. Never run in authoring."""
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

import numpy as np
import pytest
import torch
import comfy.model_management as model_management
import comfy.utils
import execution
from comfy.cli_args import args
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT=Path(__file__).resolve().parents[1]
PRISTINE=Path(os.environ['AMY_AUX_PRISTINE'])
NODE_ID='LeReS-DepthMapPreprocessor'

def file_digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def verify_assets(item,receipt):
    paths={}
    for kind in ('depth','pix2pix'):
        asset=item['assets'][kind];path=Path(receipt['native_checkpoint_paths'][kind])
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size==asset['bytes'] and file_digest(path)==asset['sha256']
        raw=torch.load(path,map_location='cpu',weights_only=True)
        assert isinstance(raw,dict) and list(raw)==asset['raw_top_level_keys'] and 'state_dict' not in raw
        original=raw['depth_model'] if kind=='depth' else raw
        data=Path(receipt['restricted_shape_evidence_paths'][kind]).read_bytes()
        assert hashlib.sha256(data).hexdigest()==asset['restricted_shape_evidence_sha256']
        proof=json.loads(data)
        assert proof['actual_inspection'] is True and proof['restricted_weights_only'] is True
        assert proof['asset_sha256']==asset['sha256'] and proof['raw_top_level_keys']==list(raw)
        actual=comfy.utils.load_torch_file(str(path),safe_load=True)
        if kind=='depth' and asset['load_state_contract']=='nested-depth-model-retained':actual=actual['depth_model']
        assert isinstance(original,dict) and isinstance(actual,dict) and list(actual)==list(original)
        # Real pix2pix metadata attribute deletion remains source semantics.
        if kind=='pix2pix':assert hasattr(actual,'_metadata')==hasattr(raw,'_metadata')
        total=0
        for key,value in original.items():
            assert type(key) is str and type(value) is torch.Tensor and type(actual[key]) is torch.Tensor
            assert actual[key].shape==value.shape and actual[key].dtype==value.dtype and torch.equal(actual[key],value)
            total+=value.numel()*value.element_size()
        assert total<=512*1024*1024
        paths[kind]=path
    return paths

def real_native_wrapper(module):
    # Compile only the exact retained wrapper class, changing only its import
    # origin to the already verified genuine native detector class.
    tree=ast.parse((PRISTINE/'node_wrappers/leres.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LERES_Depth_Map_Preprocessor')
    class OwnedImport(ast.NodeTransformer):
        def visit_ImportFrom(self,node):return None
    cls=OwnedImport().visit(cls)
    original_utils=ast.parse((PRISTINE/'utils.py').read_text())
    annotator=next(n for n in original_utils.body if isinstance(n,ast.FunctionDef) and n.name=='common_annotator_call')
    ns=dict(np=np,torch=torch,comfy=comfy,model_management=model_management,LeresDetector=module.LeresDetector)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[annotator,cls],type_ignores=[])),str(PRISTINE/'node_wrappers/leres.py'),'exec'),ns)
    return ns['LERES_Depth_Map_Preprocessor']()

@contextlib.contextmanager
def pinned_native_acquisition(module,selection,paths):
    real_load=torch.load
    def downloaded(repo,filename):
        assert repo=='lllyasviel/Annotators'
        kind={'res101.pth':'depth','latest_net_G.pth':'pix2pix'}[filename]
        return str(paths[kind])
    def restricted_load(path,*pargs,**kwargs):
        assert Path(path) in paths.values()
        assert not pargs
        kwargs['weights_only']=True
        return real_load(path,**kwargs)
    # Exact argv selection, restored even on parser/error paths. Reference
    # follows original ambient parse; production takes explicit private argv.
    previous=sys.argv
    try:
        sys.argv=[previous[0],*selection['argv']]
        with mock.patch.object(module,'custom_hf_download',downloaded),mock.patch.object(torch,'load',restricted_load):
            yield
    finally:sys.argv=previous

def test_actual_native_registered_leres_both_constructors_boost_thresholds_and_recovery():
    encoded=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(encoded).hexdigest()==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    receipt=json.loads(encoded)
    assert receipt['authorized'] is True and receipt['execution_owner']=='chat_f38536805264' and receipt['node_id']==NODE_ID
    for field in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256'):
        assert type(receipt[field]) is str and len(receipt[field])==64
    assert hashlib.sha256((ROOT/'secure-nodes.json').read_bytes()).hexdigest()==receipt['manifest_sha256']
    data=(ROOT/'_leres/asset-selection.json').read_bytes()
    assert hashlib.sha256(data).hexdigest()==receipt['asset_selection_sha256']
    selected=json.loads(data);assert selected['approved'] is True
    assert file_digest(Path(comfy.utils.__file__))==selected['published_loader_source_sha256']
    sources=json.loads((ROOT/'_leres/native-sources.json').read_text())
    assert receipt['native_source_hashes']==sources['hashes']
    for name,digest in sources['hashes'].items():assert file_digest(PRISTINE/name)==digest
    assert str(model_management.get_torch_device())==selected['depth_device']
    assert torch.cuda.is_available() is selected['expected_cuda_available']
    assert receipt['pix2pix_constructor_device_qualified'] is True
    assert receipt['parsed_native_options_correspondence_qualified'] is True
    assert receipt['boost_true_workspace_qualified'] is True
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor' and sandbox.available()==[sandbox.KIND_GVISOR]
    paths=verify_assets(selected,receipt)
    assert selected['pix2pix_save_dir_label']==str(paths['pix2pix'].parent)
    # Owner-selected genuine native package; never an unverified reconstructed
    # vendor/provider. Complete path identities are checked before import.
    native_root=Path(receipt['native_leres_package_root']).resolve()
    assert native_root==(PRISTINE/'src/custom_controlnet_aux/leres').resolve()
    assert receipt['native_leres_module']=='custom_controlnet_aux.leres'
    native=importlib.import_module(receipt['native_leres_module'])
    assert Path(native.__file__).resolve().parent==native_root
    assert file_digest(Path(native.__file__))==sources['hashes']['src/custom_controlnet_aux/leres/__init__.py']
    prefix=receipt['native_leres_module']+'.'
    for module_name,module in list(sys.modules.items()):
        if module_name.startswith(prefix) and getattr(module,'__file__',None):
            path=Path(module.__file__)
            if path.suffix=='.py':
                name='src/custom_controlnet_aux/leres/'+str(path.relative_to(Path(native.__file__).parent))
                assert name in sources['hashes'] and file_digest(path)==sources['hashes'][name]
    oracle=real_native_wrapper(native)
    # Preserve both native loads, model setter/defaults and original CUDA clear.
    with pinned_native_acquisition(native,selected,paths):
        native_options=native.TestOptions().parse()
        if not torch.cuda.is_available():native_options.gpu_ids=[]
    def project(opt):
        import math
        def value(v):
            if type(v) is float and not math.isfinite(v):return {'native_float':'nan' if math.isnan(v) else ('+inf' if v>0 else '-inf')}
            if type(v) is list:return [value(x) for x in v]
            return v
        return {k:value(v) for k,v in sorted(vars(opt).items())}
    assert project(native_options)==selected['expected_effective_options']
    pack=packdb.load_pack(Path(receipt['stable_snapshot_path']),mount_name='custom_nodes.amy_aux_leres',pack_id=receipt['pack_id'])
    cls=pack.node_mappings[NODE_ID];assert set(cls.SDK_PERMISSIONS)=={'raw','assets'}
    async def dispatch(values):
        mapped=await execution._async_map_node_over_list('amy-leres',NODE_ID,cls,{k:[v] for k,v in values.items()},cls.FUNCTION)
        return (await execution.resolve_map_node_over_list_results(mapped))[0].result[0]
    def expected(values):
        with pinned_native_acquisition(native,selected,paths):return oracle.execute(**values)[0]
    def same(a,b):
        assert type(a) is type(b) is torch.Tensor and a.dtype==b.dtype and a.shape==b.shape
        assert torch.equal(a,b)
    async def run():
        previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.execution_backend=backend
        cases=[]
        try:
            for shape,dtype,parameters in [
                ((2,32,32,3),torch.float32,{}),
                ((1,25,41,4),torch.float16,dict(resolution=64,rm_nearest=30.0,rm_background=70.0)),
                ((1,41,25,3),torch.float32,dict(resolution=64,boost='enable',rm_nearest=100.0,rm_background=100.0))]:
                image=torch.linspace(0,1,int(np.prod(shape)),dtype=dtype).reshape(shape);before=image.clone()
                values=dict(image=image,**parameters);reference=expected(values);actual=await dispatch(values);same(actual,reference)
                assert torch.equal(image,before)
                cases.append(dict(input_shape=list(shape),parameters=parameters,output_shape=list(actual.shape),dtype=str(actual.dtype)))
            recovery=dict(image=torch.ones(1,25,41,3),resolution=64)
            invalid=dict(recovery,image=torch.ones(1,25,41,2))
            with pytest.raises(AssertionError):expected(invalid)
            with pytest.raises(Exception):await dispatch(invalid)
            same(await dispatch(recovery),expected(recovery))
            with pytest.raises(Exception,match='projected|workspace|bounded'):await dispatch(dict(recovery,resolution=16384))
            same(await dispatch(recovery),expected(recovery))
            return cases
        finally:
            try:await backend.guests.shutdown()
            finally:_sdk.providers.execution_backend=previous
    cases=asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(node_id=NODE_ID,native_registered_cases=cases,
        actual_dual_checkpoint_reader_equality=True,actual_native_options=project(native_options),constructor_both_assets_even_boost_false=True,
        native_channel_error=True,registered_error_observed=True,workload_refusal=True,recoveries=2,
        constructor_device_correspondence=True,pix2pix_migration_todo_preserved=True,device_portability=None,
        cache_or_cold_warm_acceptance=None,whole_pack_acceptance=False),indent=2)+'\n')
