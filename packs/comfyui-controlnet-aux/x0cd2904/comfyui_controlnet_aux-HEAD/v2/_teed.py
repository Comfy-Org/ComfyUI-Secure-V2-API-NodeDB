"""Pinned tiny edge detector; managed reviewed tensor checkpoint."""
from comfy_api.latest import sdk
from ._annotator import common_annotator_call
from ._teed_network import TED, TEDDetector

WEIGHT=sdk.HuggingFaceWeight(repo_id='bdsqlsz/qinglong_controlnet-lllite', filename='Annotators/7_model.pth',
    revision='67006a35a5955437d118490bfec822402eff09f5',
    sha256='b9037964149c55156c6adbffdfbd7e8ca7d2ef2a4d90573520efa7f3a1aacf06', folder='controlnet')


def _render_loaded(state,image,safe_steps=2,resolution=512):
    # Original model strict loading owns checkpoint validation.
    network=TED()
    network.load_state_dict(state,strict=True)
    network.float().eval()
    return common_annotator_call(TEDDetector(network),image,resolution=resolution,safe_steps=safe_steps)

async def execute(image, safe_steps=2, resolution=512, *, declaration=WEIGHT):
    asset=await sdk.ctx().assets.resolve(declaration.folder,declaration.catalogue_name)
    if await sdk.ctx().assets.digest(asset)!=declaration.sha256:
        raise ValueError('TEED weight digest differs from the reviewed declaration')
    state=await sdk.ctx().assets.load_state_dict(asset)
    return _render_loaded(state,image,safe_steps,resolution)
