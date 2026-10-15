"""Managed tensor weights; pinned network remains pack-owned."""
from comfy_api.latest import sdk
from ._annotator import common_annotator_call
from ._hed_network import ControlNetHED_Apache2, HEDdetector

WEIGHT=sdk.HuggingFaceWeight(repo_id='lllyasviel/Annotators', filename='ControlNetHED.pth',
    revision='982e7edaec38759d914a963c48c4726685de7d96',
    sha256='5ca93762ffd68a29fee1af9d495bf6aab80ae86f08905fb35472a083a4c7a8fa', folder='controlnet')


def _render_loaded(node_id,state,image,resolution=512,safe='enable'):
    # The original flat state is loaded strictly into the real native network.
    network=ControlNetHED_Apache2()
    network.load_state_dict(state,strict=True)
    network.float().eval()
    detector=HEDdetector(network)
    return common_annotator_call(detector,image,resolution=resolution,safe=safe=='enable',scribble=node_id=='FakeScribblePreprocessor')

async def execute(node_id, image, resolution=512, safe='enable'):
    asset=await sdk.ctx().assets.resolve(WEIGHT.folder, WEIGHT.catalogue_name)
    if await sdk.ctx().assets.digest(asset) != WEIGHT.sha256:
        raise ValueError('HED weight digest differs from the reviewed declaration')
    state=await sdk.ctx().assets.load_state_dict(asset)
    return _render_loaded(node_id,state,image,resolution,safe)
