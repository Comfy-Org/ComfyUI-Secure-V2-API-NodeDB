"""Real retained NormalBAE network + published managed loader composition.

No checkpoint layout or artifact is guessed. An unselected container contract
refuses before any asset RPC or timm/network construction.
"""
import json
import re
import types
from pathlib import Path
from comfy_api.latest import sdk
from .._annotator import common_annotator_call


def selected_checkpoint():
    item=json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    if item.get('approved') is not True:
        raise RuntimeError('BAE-NormalMapPreprocessor: exact managed scannet model-container selection pending')
    if item.get('format')!='amy-normalbae-managed-checkpoint/1' or item.get('source_pin')!='0cd290477128d42cdc3e76a826a402d866e8c684':
        raise ValueError('NormalBAE selected source differs')
    if (item.get('source_repo'),item.get('source_filename'),item.get('folder'))!=('lllyasviel/Annotators','scannet.pt','controlnet'):
        raise ValueError('NormalBAE asset identity differs from retained source')
    for name,width in [('sha256',64),('revision',40),('restricted_shape_evidence_sha256',64)]:
        if not isinstance(item.get(name),str) or not re.fullmatch('[0-9a-f]{'+str(width)+'}',item[name]):
            raise ValueError('NormalBAE exact asset/container evidence pending')
    if item.get('published_loader_source_sha256')!='9320cf5c624e96acc1d9ec92ff120ed6387a2142707f3194cb21dd0d11ac2500':
        raise ValueError('NormalBAE loader policy source differs')
    if type(item.get('bytes')) is not int or item['bytes'] <= 0:
        raise ValueError('NormalBAE exact serialized state size is missing')
    if not isinstance(item.get('catalogue_name'),str) or not item['catalogue_name']:
        raise ValueError('NormalBAE actual managed catalogue binding pending')
    keys=item.get('raw_top_level_keys')
    if not isinstance(keys,list) or not keys or any(not isinstance(k,str) for k in keys) or len(keys)!=len(set(keys)):
        raise ValueError('NormalBAE actual original checkpoint keys pending')
    if 'model' not in keys or 'state_dict' in keys:
        raise RuntimeError('NormalBAE native model container is not preserved by this published loader policy')
    contract='model-only-unwrapped' if keys==['model'] else 'nested-model-retained'
    if item.get('load_state_contract')!=contract:
        raise ValueError('NormalBAE selected container contract contradicts original keys')
    return item

def model_member(loaded,contract):
    if contract=='nested-model-retained':
        return loaded['model']
    if contract=='model-only-unwrapped':
        return loaded
    raise RuntimeError('NormalBAE published loader container contract remains unsupported')

async def execute(image,resolution=512,**kwargs):
    item=selected_checkpoint()
    from .nets.NNET import NNET
    from .checkpoint import load_checkpoint
    from .detector import NormalBaeDetector
    asset=await sdk.ctx().assets.resolve(item['folder'],item['catalogue_name'])
    if await sdk.ctx().assets.digest(asset)!=item['sha256']:
        raise ValueError('NormalBAE weight digest differs from exact selection')
    args=types.SimpleNamespace()
    args.mode='client'
    args.architecture='BN'
    args.pretrained='scannet'
    args.sampling_ratio=0.4
    args.importance_ratio=0.7
    # Source constructs the NNET before loading/checking the checkpoint.
    model=NNET(args)
    loaded=await sdk.ctx().assets.load_state_dict(asset)
    model=load_checkpoint(model_member(loaded,item['load_state_contract']),model)
    model.eval()
    detector=NormalBaeDetector(model).to('cpu')
    out=common_annotator_call(detector,image,resolution=resolution)
    del detector
    return out
