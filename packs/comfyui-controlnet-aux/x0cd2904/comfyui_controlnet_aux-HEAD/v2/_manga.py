"""Manga line inference using checksum-verified, managed tensor data."""
import torch
from comfy_api.latest import sdk
from ._annotator import common_annotator_call
from ._lineart import weight
from ._manga_network import res_skip, LineartMangaDetector

WEIGHT = weight('erika.pth', 'badbd6baf013cefbd98993307b02cc14a26c770d067416e4fdecc8720b88feeb')


def _render_loaded(state,image,resolution=512):
    state=dict(state)
    # Exact pinned normalization, including substring rather than prefix matching.
    for key in list(state):
        if 'module.' in key:
            state[key.replace('module.', '')] = state[key]
            del state[key]
    network = res_skip()
    network.load_state_dict(state, strict=True)
    network.eval()
    return common_annotator_call(LineartMangaDetector(network), image, resolution=resolution)

async def execute(image, resolution=512):
    asset=await sdk.ctx().assets.resolve(WEIGHT.folder,WEIGHT.catalogue_name)
    if await sdk.ctx().assets.digest(asset)!=WEIGHT.sha256:
        raise ValueError('manga weight digest differs from reviewed declaration')
    state=await sdk.ctx().assets.load_state_dict(asset)
    return _render_loaded(state,image,resolution)
