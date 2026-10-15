"""Managed line-art tensors with exact source-owned networks."""
import functools
import torch
from comfy_api.latest import sdk
from ._annotator import common_annotator_call
from ._lineart_network import Generator,LineartDetector
from ._lineart_anime_network import UnetGenerator,LineartAnimeDetector

REVISION='982e7edaec38759d914a963c48c4726685de7d96'


def weight(filename,digest):
    return sdk.HuggingFaceWeight(repo_id='lllyasviel/Annotators',filename=filename,revision=REVISION,sha256=digest,folder='controlnet')


FINE=weight('sk_model.pth','c686ced2a666b4850b4bb6ccf0748031c3eda9f822de73a34b8979970d90f0c6')
COARSE=weight('sk_model2.pth','30a534781061f34e83bb9406b4335da4ff2616c95d22a585c1245aa8363e74e0')
ANIME=weight('netG.pth','ccabdcc3f5cf3c07cf65d58776acb21df7dfda825cdc70c9766a93fd62bfc488')
WEIGHTS={'LineArtPreprocessor':(FINE,COARSE),'AnimeLineArtPreprocessor':(ANIME,)}


async def state(declaration):
    asset=await sdk.ctx().assets.resolve(declaration.folder,declaration.catalogue_name)
    if await sdk.ctx().assets.digest(asset)!=declaration.sha256:
        raise ValueError('line-art weight digest differs from the reviewed declaration')
    value=await sdk.ctx().assets.load_state_dict(asset)
    return value


def _render_loaded(node_id,states,image,resolution=512,coarse='disable'):
    if node_id=='LineArtPreprocessor':
        fine_state=states[FINE.filename]
        coarse_state=states[COARSE.filename]
        fine=Generator(3,1,3)
        fine.load_state_dict(fine_state,strict=True)
        fine.float().eval()
        other=Generator(3,1,3)
        other.load_state_dict(coarse_state,strict=True)
        other.float().eval()
        return common_annotator_call(LineartDetector(fine,other),image,resolution=resolution,coarse=coarse=='enable')
    value=dict(states[ANIME.filename])
    for key in list(value):
        if 'module.' in key:
            value[key.replace('module.','')]=value[key]
            del value[key]
    norm=functools.partial(torch.nn.InstanceNorm2d,affine=False,track_running_stats=False)
    network=UnetGenerator(3,1,8,64,norm_layer=norm,use_dropout=False)
    network.load_state_dict(value,strict=True)
    network.float().eval()
    return common_annotator_call(LineartAnimeDetector(network),image,resolution=resolution)

async def execute(node_id,image,resolution=512,coarse='disable'):
    states={w.filename:await state(w) for w in WEIGHTS[node_id]}
    return _render_loaded(node_id,states,image,resolution,coarse)
