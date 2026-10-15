"""Full original Lynx face operations; trained/provider equivalence pending."""
import hashlib
import json
from pathlib import Path
import tempfile
import torch
from comfy_api.latest import io,sdk
from .secure_lynx_resampler import rebuild_lynx_resampler
from .secure_tensor_nodes import _bound_payload

BINDINGS=json.loads(Path(__file__).with_name('secure_lynx_face_asset_bindings.json').read_text())
ARCFACE=next(row for row in BINDINGS if row['role']=='arcface')
INSIGHTFACE=tuple(row for row in BINDINGS if row['role']=='insightface')
RANGE_BYTES=8*1024**2
MAX_ASSET_BYTES=256*1024**2
MAX_SCRATCH_BYTES=384*1024**2


def weight_declaration(row):
    return sdk.HuggingFaceWeight(**{key:row[key] for key in
        ('repo_id','filename','folder','revision','sha256')})


def preflight_lynx_images(images):
    _bound_payload(images)
    if (not isinstance(images,torch.Tensor) or images.layout!=torch.strided
            or images.device.type!='cpu' or images.ndim!=4 or images.shape[-1]!=3
            or not 1<=images.shape[0]<=16
            or not all(1<=dimension<=1024 for dimension in images.shape[1:3])):
        raise ValueError('Lynx requires bounded dense CPU BHWC RGB images')


def require_native_arcface_cuda():
    if not torch.cuda.is_available():
        raise RuntimeError('Original Lynx ArcFace constructor requires CUDA; no CPU substitute is implemented')


async def resolve_pinned_lynx_asset(binding):
    assets=sdk.current_context().assets
    asset=await assets.resolve(binding['folder'],binding['catalogue_name'])
    size=await assets.size(asset)
    if size!=binding['bytes'] or not 0<size<=MAX_ASSET_BYTES:
        raise ValueError('Lynx model archive length differs from the pinned bounded asset')
    if await assets.digest(asset)!=binding['sha256']:
        raise ValueError('Lynx model differs from the pinned archive')
    return assets,asset


async def project_insightface_assets(scratch):
    # Fixed basenames are internal metadata, never a user-selected filesystem
    # path. This temporary tree is disposable and is removed by its owner.
    assert {row['leaf_filename'] for row in INSIGHTFACE}=={
        '1k3d68.onnx','2d106det.onnx','det_10g.onnx','genderage.onnx','w600k_r50.onnx'}
    if sum(row['bytes'] for row in INSIGHTFACE)>MAX_SCRATCH_BYTES:
        raise ValueError('Original InsightFace pack exceeds its bounded scratch allocation')
    destination=Path(scratch)/'models/buffalo_l'
    destination.mkdir(parents=True,exist_ok=False)
    for binding in INSIGHTFACE:
        assets,asset=await resolve_pinned_lynx_asset(binding)
        actual=hashlib.sha256()
        with (destination/binding['leaf_filename']).open('xb') as output:
            for offset in range(0,binding['bytes'],RANGE_BYTES):
                count=min(RANGE_BYTES,binding['bytes']-offset)
                chunk=await assets.read_range(asset,offset=offset,length=count)
                if not isinstance(chunk,bytes) or len(chunk)!=count:
                    raise ValueError('Lynx public asset range returned incomplete bytes')
                output.write(chunk)
                actual.update(chunk)
        if actual.hexdigest()!=binding['sha256'] or await assets.digest(asset)!=binding['sha256']:
            raise ValueError('Lynx original model pack changed during bounded reads')
    return destination


class LynxInsightFaceCrop(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets','models.download')
    SDK_REQUIRED_WEIGHTS=tuple(weight_declaration(row) for row in INSIGHTFACE)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LynxInsightFaceCrop',display_name='Lynx InsightFace Crop',category='WanVideoWrapper',
            inputs=[io.Image.Input('image',tooltip='Input images for the model')],
            outputs=[io.Image.Output(display_name='ip_image'),io.Image.Output(display_name='ref_image')])

    @classmethod
    async def execute(cls,image,image_size=112):
        preflight_lynx_images(image)
        from insightface.app import FaceAnalysis
        from .secure_lynx_face_algorithms import crop_lynx_face_original
        with tempfile.TemporaryDirectory(prefix='wan-lynx-insightface-') as scratch:
            await project_insightface_assets(scratch)
            # Default name/providers/full model inventory stay those of the
            # qualified native dependency. Only its local root is redirected.
            detector=FaceAnalysis(root=scratch)
            detector.prepare(ctx_id=0,det_size=(640,640))
            result=crop_lynx_face_original(detector,image,image_size)
            del detector
        _bound_payload(result)
        return io.NodeOutput(*result)


class LynxEncodeFaceIP(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw','assets','models.download')
    SDK_REQUIRED_WEIGHTS=(weight_declaration(ARCFACE),)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LynxEncodeFaceIP',display_name='Lynx Encode Face IP',category='WanVideoWrapper',
            inputs=[io.Custom('LYNXRESAMPLER').Input('resampler',tooltip='lynx resampler model'),
                io.Image.Input('ip_image',tooltip='Input images for the model')],
            outputs=[io.Custom('LYNXIP').Output(display_name='lynx_face_embeds')])

    @classmethod
    async def execute(cls,resampler,ip_image):
        preflight_lynx_images(ip_image)
        require_native_arcface_cuda()
        from .secure_lynx_face_algorithms import FaceEncoderArcFace,encode_lynx_face_original
        resource,_=await rebuild_lynx_resampler(resampler)
        assets,asset=await resolve_pinned_lynx_asset(ARCFACE)
        state=await assets.load_state_dict(asset)
        if await assets.digest(asset)!=ARCFACE['sha256']:
            raise ValueError('Lynx ArcFace archive changed during state loading')
        face_encoder=FaceEncoderArcFace()
        face_encoder.init_encoder_model(torch.device('cuda'),state)
        del state
        result=encode_lynx_face_original(face_encoder,resource,ip_image)
        _bound_payload(result)
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS={'LynxEncodeFaceIP':LynxEncodeFaceIP,'LynxInsightFaceCrop':LynxInsightFaceCrop}
