"""Original FantasyPortrait face detection behind its bounded model recipe."""
import hashlib
import json
from pathlib import Path
import torch
from comfy_api.latest import io
from .secure_portrait_resource import rebuild_portrait_resource
from .secure_tensor_nodes import _bound_payload

_ROOT=Path(__file__).parent
DETECTOR_ASSETS=json.loads((_ROOT/'secure_portrait_detector_assets.json').read_text())


def verify_portrait_detector_assets():
    for row in DETECTOR_ASSETS:
        path=_ROOT/row['path']
        if path.stat().st_size!=row['bytes'] or not 0<row['bytes']<4*1024**2:
            raise ValueError('Bundled original FantasyPortrait ONNX asset length changed')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Bundled original FantasyPortrait ONNX asset changed')


def preflight_portrait_images(images,device):
    _bound_payload(images)
    if (not isinstance(images,torch.Tensor) or images.layout!=torch.strided
            or images.device.type!='cpu' or images.ndim!=4
            or not 1<=images.shape[0]<=65 or images.shape[-1] not in (3,4)
            or not all(1<=dimension<=1024 for dimension in images.shape[1:3])):
        raise ValueError('FantasyPortrait requires bounded dense CPU BHWC images')
    if device not in ('cpu','cuda'):
        raise ValueError('FantasyPortrait retains only the original CPU/CUDA choices')
    if device=='cuda' and not torch.cuda.is_available():
        raise RuntimeError('FantasyPortrait CUDA selection requires an admitted CUDA execution device')


class FantasyPortraitFaceDetector(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FantasyPortraitFaceDetector',display_name='FantasyPortrait Face Detector',
            category='WanVideoWrapper',inputs=[
                io.Custom('FANTASYPORTRAITMODEL').Input('portrait_model'),io.Image.Input('images'),
                io.Float.Input('adapter_scale',default=1.,min=0.,max=10.,step=.01,optional=True,tooltip='Scale for the adapter projection'),
                io.Float.Input('mouth_scale',default=1.,min=0.,max=10.,step=.01,optional=True,tooltip='Scale for the mouth projection'),
                io.Float.Input('emo_scale',default=1.,min=0.,max=10.,step=.01,optional=True,tooltip='Scale for the emotion projection'),
                io.Combo.Input('device',options=['cuda','cpu'],default='cuda',optional=True,tooltip='Device to run the model on')],
            outputs=[io.Custom('PORTRAIT_EMBEDS').Output(display_name='portrait_embeds'),
                io.Custom('BBOX').Output(display_name='bbox'),io.Custom('LANDMARKS').Output(display_name='landmarks')])

    @classmethod
    async def execute(cls,images,portrait_model,adapter_scale=1.,mouth_scale=1.,emo_scale=1.,device='cuda'):
        preflight_portrait_images(images,device)
        verify_portrait_detector_assets()
        # Import the original dependency path before rebuilding a large adapter,
        # so an unadmitted ONNX profile fails before any trained model load.
        from .fantasyportrait.pd_fgc.face_align import FaceAlignment
        from .secure_portrait_detector_algorithm import detect_portrait_original
        resource,_=await rebuild_portrait_resource(portrait_model)
        result=detect_portrait_original(images,resource,adapter_scale,mouth_scale,emo_scale,device)
        _bound_payload(result)
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS={'FantasyPortraitFaceDetector':FantasyPortraitFaceDetector}
