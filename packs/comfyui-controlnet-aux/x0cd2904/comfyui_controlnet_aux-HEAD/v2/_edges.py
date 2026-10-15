"""Native CPU detector computations through exact declared managed weights."""
import cv2
from comfy_api.latest import sdk
from ._annotator import common_annotator_call
from ._image_math import nms
from ._pidi_model import pidinet
from ._mlsd_model import MobileV2_MLSD_Large
from ._edge_networks import PidiNetDetector,MLSDdetector

REVISION='982e7edaec38759d914a963c48c4726685de7d96'
PIDI=sdk.HuggingFaceWeight(repo_id='lllyasviel/Annotators',filename='table5_pidinet.pth',revision=REVISION,
    sha256='80860ac267258b5f27486e0ef152a211d0b08120f62aeb185a050acc30da486c',folder='controlnet')
MLSD=sdk.HuggingFaceWeight(repo_id='lllyasviel/Annotators',filename='mlsd_large_512_fp32.pth',revision=REVISION,
    sha256='5696f168eb2c30d4374bbfd45436f7415bb4d88da29bea97eea0101520fba082',folder='controlnet')
WEIGHTS={'PiDiNetPreprocessor':PIDI,'Scribble_PiDiNet_Preprocessor':PIDI,'M-LSDPreprocessor':MLSD}

def _render_loaded(node_id,state,image,resolution=512,safe='enable',score_threshold=0.1,dist_threshold=0.1):
    # The published reader selects the original PiDiNet state_dict member.
    # Native normalization and strict Torch loading perform their own checks.
    normalized=state if node_id=='M-LSDPreprocessor' else {key.replace('module.',''):value for key,value in state.items()}
    if node_id=='M-LSDPreprocessor':
        network=MobileV2_MLSD_Large()
        network.load_state_dict(normalized,strict=True)
        network.eval()
        return common_annotator_call(MLSDdetector(network),image,resolution=resolution,thr_v=score_threshold,thr_d=dist_threshold)
    if node_id=='PiDiNetPreprocessor':
        network=pidinet()
        network.load_state_dict(normalized,strict=True)
        network.eval()
        return common_annotator_call(PidiNetDetector(network),image,resolution=resolution,safe=safe=='enable')
    def scribble(img,**kwargs):
        # Original Scribble creates a fresh native network for every frame.
        network=pidinet()
        network.load_state_dict(normalized,strict=True)
        network.eval()
        detector=PidiNetDetector(network)
        result=detector(img,scribble=True,**kwargs)
        # Both native detector and wrapper filter; preserve both passes.
        result=nms(result,127,3.0)
        result=cv2.GaussianBlur(result,(0,0),3.0)
        result[result>4]=255
        result[result<255]=0
        return result
    return common_annotator_call(scribble,image,resolution=resolution,safe=safe=='enable')

async def execute(node_id,image,resolution=512,safe='enable',score_threshold=0.1,dist_threshold=0.1):
    weight=WEIGHTS[node_id]
    asset=await sdk.ctx().assets.resolve(weight.folder,weight.catalogue_name)
    if await sdk.ctx().assets.digest(asset)!=weight.sha256:
        raise ValueError('Edge detector weight digest differs from reviewed declaration')
    state=await sdk.ctx().assets.load_state_dict(asset)
    return _render_loaded(node_id,state,image,resolution,safe,score_threshold,dist_threshold)
