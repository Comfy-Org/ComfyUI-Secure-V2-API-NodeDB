"""Original UniAnimate DWPose with pinned managed assets and pack-side math."""
import hashlib
import io as byte_io
import json
from pathlib import Path
import torch
from comfy_api.latest import io,sdk
from .secure_tensor_nodes import _bound_payload

ASSET_BINDINGS=json.loads(Path(__file__).with_name('secure_unianimate_asset_bindings.json').read_text())
WEIGHTS=tuple(sdk.HuggingFaceWeight(**{key:row[key] for key in
    ('repo_id','filename','folder','revision','sha256')}) for row in ASSET_BINDINGS)
RANGE_BYTES=8*1024**2
MAX_ARCHIVE_BYTES=256*1024**2


async def load_unianimate_jit(binding):
    assets=sdk.current_context().assets
    asset=await assets.resolve(binding['folder'],binding['catalogue_name'])
    size=await assets.size(asset)
    if size!=binding['bytes'] or not 0<size<=MAX_ARCHIVE_BYTES:
        raise ValueError('UniAnimate original archive has an unexpected or oversized length')
    digest=await assets.digest(asset)
    if digest!=binding['sha256']:
        raise ValueError('UniAnimate requires the pinned original trained archive')
    actual=hashlib.sha256()
    with byte_io.BytesIO() as stream:
        for offset in range(0,size,RANGE_BYTES):
            count=min(RANGE_BYTES,size-offset)
            chunk=await assets.read_range(asset,offset=offset,length=count)
            if not isinstance(chunk,bytes) or len(chunk)!=count:
                raise ValueError('UniAnimate public asset range returned incomplete bytes')
            stream.write(chunk)
            actual.update(chunk)
        del chunk
        if actual.hexdigest()!=digest or await assets.digest(asset)!=digest:
            raise ValueError('UniAnimate original archive changed during bounded reads')
        stream.seek(0)
        # This is the original TorchScript loader and explicit CPU compute tier.
        # JIT operator/model qualification is still required before admission.
        return torch.jit.load(stream,map_location=torch.device('cpu'))


def preflight_unianimate_images(pose_images,reference_pose_image=None):
    _bound_payload((pose_images,reference_pose_image))
    for image in (pose_images,reference_pose_image):
        if image is None:continue
        if (not isinstance(image,torch.Tensor) or image.layout!=torch.strided
                or image.device.type!='cpu' or image.ndim!=4
                or not 1<=image.shape[0]<=64 or image.shape[-1]!=3
                or not all(1<=dimension<=1024 for dimension in image.shape[1:3])):
            raise ValueError('UniAnimate requires bounded dense CPU BHWC RGB images')
    if reference_pose_image is not None and reference_pose_image.shape[0]!=1:
        raise ValueError('Original UniAnimate reference pose requires one image')


class WanVideoUniAnimateDWPoseDetector(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets','models.download')
    SDK_REQUIRED_WEIGHTS=WEIGHTS

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoUniAnimateDWPoseDetector',
            display_name='WanVideo UniAnimate DWPose Detector',category='WanVideoWrapper',inputs=[
                io.Image.Input('pose_images',tooltip='Pose images'),
                io.Float.Input('score_threshold',default=.3,min=0.,max=1.,step=.01,tooltip='Score threshold for pose detection'),
                io.Int.Input('stick_width',default=4,min=1,max=100,step=1,tooltip='Stick width for drawing keypoints'),
                io.Boolean.Input('draw_body',default=True,tooltip='Draw body keypoints'),
                io.Int.Input('body_keypoint_size',default=4,min=0,max=100,step=1,tooltip='Body keypoint size'),
                io.Boolean.Input('draw_feet',default=True,tooltip='Draw feet keypoints'),
                io.Boolean.Input('draw_hands',default=True,tooltip='Draw hand keypoints'),
                io.Int.Input('hand_keypoint_size',default=4,min=0,max=100,step=1,tooltip='Hand keypoint size'),
                io.Combo.Input('colorspace',options=['RGB','BGR'],tooltip='Color space for the output image'),
                io.Combo.Input('handle_not_detected',options=['empty','repeat'],default='empty',
                    tooltip='How to handle undetected poses, empty inserts black and repeat inserts previous detection'),
                io.Boolean.Input('draw_head',default=True,tooltip='Draw head keypoints'),
                io.Image.Input('reference_pose_image',optional=True,tooltip='Reference pose image')],
            outputs=[io.Image.Output(display_name='poses'),io.Image.Output(display_name='reference_pose')])

    @classmethod
    async def execute(cls,pose_images,score_threshold,stick_width,reference_pose_image=None,
                      draw_body=True,body_keypoint_size=4,draw_feet=True,draw_hands=True,
                      hand_keypoint_size=4,colorspace='RGB',handle_not_detected='empty',draw_head=True):
        preflight_unianimate_images(pose_images,reference_pose_image)
        from .secure_unianimate_algorithms import DWposeDetector,process_unianimate_original
        detector_model=await load_unianimate_jit(ASSET_BINDINGS[0])
        pose_model=await load_unianimate_jit(ASSET_BINDINGS[1])
        detector=DWposeDetector(detector_model,pose_model)
        result=process_unianimate_original(detector,pose_images,score_threshold,stick_width,
            reference_pose_image,draw_body,body_keypoint_size,draw_feet,draw_hands,
            hand_keypoint_size,colorspace,handle_not_detected,draw_head)
        _bound_payload(result)
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS={'WanVideoUniAnimateDWPoseDetector':WanVideoUniAnimateDWPoseDetector}
