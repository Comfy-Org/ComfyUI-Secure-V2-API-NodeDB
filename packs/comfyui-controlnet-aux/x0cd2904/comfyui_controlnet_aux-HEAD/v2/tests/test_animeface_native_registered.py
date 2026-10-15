"""Future real native/registered AnimeFace gate; source authoring never runs it.

The native oracle consumes retained source classes and real scientific modules.
Only pretrained file acquisition is replaced by preverified restricted states.
No detector output, SDK provider, RPC, or transport is replaced.
"""
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import warnings

import cv2
import numpy as np
import pytest
import torch
import torchvision
from PIL import Image
from einops import rearrange
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
NODE_ID='AnimeFace_SemSegPreprocessor'
SOURCE_PREFIX='src/custom_controlnet_aux/anime_face_segment/'

def lift(path, ns, names=None, transform=None, assignments=False):
    text=(PRISTINE/path).read_text()
    tree=ast.parse(text)
    body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))
          and (names is None or n.name in names)]
    if assignments:
        body=[n for n in tree.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and (t.id.startswith('COLOR_') or t.id=='PALETTE') for t in n.targets)]+body
    if transform: body=[transform.visit(n) for n in body]
    assert body
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(PRISTINE/path),'exec'),ns)

def native_oracle(states):
    ns=dict(torch=torch,nn=torch.nn,F=torch.nn.functional,torchvision=torchvision,
            models=torchvision.models,np=np,cv2=cv2,Image=Image,rearrange=rearrange,
            warnings=warnings,model_management=model_management,comfy=comfy,
            DEVICE='cpu',mobilenet_state=states['mobilenet'],BDS_MODEL_NAME='bdsqlsz/qinglong_controlnet-lllite')
    lift('src/custom_controlnet_aux/util.py',ns,
         ['HWC3','safer_memory','pad64','get_upscale_method','resize_image_with_pad','common_input_validate'])
    ns['UPSCALE_METHODS']=['INTER_NEAREST','INTER_LINEAR','INTER_AREA','INTER_CUBIC','INTER_LANCZOS4']
    lift(SOURCE_PREFIX+'util.py',ns,['seg2img'],assignments=True)
    # Preserve full native UNet constructor and strict MobileNet state load;
    # replace only its torch.load(custom_torch_download(...)) acquisition.
    class MobileAcquisition(ast.NodeTransformer):
        def visit_Call(self,node):
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='torch' and node.func.attr=='load':
                return ast.Name(id='mobilenet_state',ctx=ast.Load())
            return self.generic_visit(node)
    lift(SOURCE_PREFIX+'network.py',ns,['UNet'],transform=MobileAcquisition())
    # Load every retained ISNet definition, including native module loss objects.
    text=(PRISTINE/(SOURCE_PREFIX+'isnet.py')).read_text()
    tree=ast.parse(text)
    tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
    exec(compile(ast.fix_missing_locations(tree),str(PRISTINE/(SOURCE_PREFIX+'isnet.py')),'exec'),ns)
    class BackgroundAcquisition(ast.NodeTransformer):
        def visit_Call(self,node):
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='torch' and node.func.attr=='load':
                return ast.Name(id='background_state',ctx=ast.Load())
            return self.generic_visit(node)
    ns['background_state']=states['background']
    lift(SOURCE_PREFIX+'anime_segmentation.py',ns,['AnimeSegmentation'],transform=BackgroundAcquisition())
    lift(SOURCE_PREFIX+'__init__.py',ns,['AnimeFaceSegmentor'])
    cls=ns['AnimeFaceSegmentor']
    def native_construct(_cls):
        model=ns['UNet']()
        model.load_state_dict(states['unet'])
        model.eval()
        background=ns['AnimeSegmentation']('preverified-state-only')
        background.net.eval()
        return _cls(model,background)
    cls.from_pretrained=classmethod(native_construct)
    lift('utils.py',ns,['common_annotator_call'])
    # Original wrapper performs a local import; bind the independent native
    # class above rather than import a host/downloading source package.
    class WrapperImport(ast.NodeTransformer):
        def visit_ImportFrom(self,node): return None
    lift('node_wrappers/anime_face_segment.py',ns,[NODE_ID],transform=WrapperImport())
    return ns[NODE_ID]()

def verified_states(receipt,selection):
    paths=receipt['native_artifact_paths']
    assert set(paths)==set(selection['artifacts'])=={'unet','background','mobilenet'}
    states={}
    total=0
    for key in ('unet','background','mobilenet'):
        item=selection['artifacts'][key]
        p=Path(paths[key])
        assert p.stat().st_size==item['bytes']
        digest=hashlib.sha256()
        with p.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
        assert digest.hexdigest()==item['sha256']
        value=torch.load(p,map_location='cpu',weights_only=True)
        assert isinstance(value,dict) and value
        for name,tensor in value.items():
            assert isinstance(name,str) and isinstance(tensor,torch.Tensor)
            assert tensor.layout==torch.strided and tensor.device.type=='cpu'
            total+=tensor.numel()*tensor.element_size()
        assert total<=256*1024*1024
        states[key]=value
    return states

def test_genuine_animeface_native_registered_masks_errors_and_recovery():
    raw=Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    receipt=json.loads(raw)
    assert receipt['authorized'] is True and receipt['execution_owner']=='chat_f38536805264'
    assert receipt['node_id']==NODE_ID
    for field in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256'):
        assert isinstance(receipt[field],str) and len(receipt[field])==64
    assert receipt['manifest_sha256']==hashlib.sha256((ROOT/'secure-nodes.json').read_bytes()).hexdigest()
    assert receipt['artifact_selection_sha256']==hashlib.sha256((ROOT/'_anime_face_assets.json').read_bytes()).hexdigest()
    selection=json.loads((ROOT/'_anime_face_assets.json').read_text())
    assert selection['approved'] is True
    assert args.cpu is True and model_management.get_torch_device().type=='cpu'
    assert os.environ['COMFY_SECURE_SANDBOX_MODE']=='required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND']=='gvisor'
    assert sandbox.available()==[sandbox.KIND_GVISOR]
    # Bind only named consumed pristine bytes, not a reconstructed transcript.
    expected_sources=json.loads((ROOT/'_anime_face_native_sources.json').read_text())
    assert expected_sources['source_pin']=='0cd290477128d42cdc3e76a826a402d866e8c684'
    assert receipt['native_source_hashes']==expected_sources['hashes']
    for name, expected in expected_sources['hashes'].items():
        assert hashlib.sha256((PRISTINE/name).read_bytes()).hexdigest()==expected
    states=verified_states(receipt,selection)
    oracle=native_oracle(states)
    pack=packdb.load_pack(Path(receipt['stable_snapshot_path']),
                         mount_name='custom_nodes.amy_aux_animeface',pack_id=receipt['pack_id'])
    cls=pack.node_mappings[NODE_ID]
    assert set(cls.SDK_PERMISSIONS)=={'raw','assets'}
    image=torch.linspace(0,1,2*32*32*3).reshape(2,32,32,3)
    async def dispatch(values):
        mapped=await execution._async_map_node_over_list('amy-animeface',NODE_ID,cls,
                    {k:[v] for k,v in values.items()},cls.FUNCTION)
        return (await execution.resolve_map_node_over_list_results(mapped))[0].result
    def equal(actual,expected):
        assert len(actual)==len(expected)==2
        for got,want in zip(actual,expected):
            assert type(got) is type(want) is torch.Tensor
            assert got.dtype==want.dtype and got.shape==want.shape
            assert torch.equal(got,want)
    async def run():
        previous=_sdk.providers.execution_backend
        backend=CloudExecutionBackend()
        _sdk.providers.execution_backend=backend
        receipts=[]
        try:
            for remove in (True,False):
                values=dict(image=image,remove_background_using_abg=remove,resolution=512)
                before=image.clone()
                expected=oracle.execute(**values)
                actual=await dispatch(values)
                equal(actual,expected)
                assert torch.equal(image,before)
                assert actual[1].ndim==4 and actual[1].shape[1]==(1 if remove else 3)
                if not remove: assert torch.equal(actual[1],torch.ones_like(actual[1]))
                receipts.append({'remove_background_using_abg':remove,'image_shape':list(actual[0].shape),
                                 'native_mask_shape':list(actual[1].shape)})
            # Preserve convolution's native wrong-channel error; don't HWC3
            # the input or pretend the outer error envelope is its native type.
            bad=dict(image=image[...,:1],remove_background_using_abg=False,resolution=512)
            with pytest.raises(RuntimeError): oracle.execute(**bad)
            with pytest.raises(Exception): await dispatch(bad)
            recovery=dict(image=image[:1],remove_background_using_abg=False,resolution=512)
            equal(await dispatch(recovery),oracle.execute(**recovery))
            with pytest.raises(Exception,match='projected|workspace|bounded'):
                await dispatch(dict(recovery,resolution=16384))
            equal(await dispatch(recovery),oracle.execute(**recovery))
            return receipts
        finally:
            try: await backend.guests.shutdown()
            finally: _sdk.providers.execution_backend=previous
    actual=asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps({'node_id':NODE_ID,
      'branches':actual,'native_channel_error':True,'workload_refusal':True,'recoveries':2,
      'mask_transport_exact':True,'whole_pack_acceptance':False},indent=2)+'\n')
