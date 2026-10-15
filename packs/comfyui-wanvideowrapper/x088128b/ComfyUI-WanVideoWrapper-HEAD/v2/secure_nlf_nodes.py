"""Original NLF TorchScript behind bounded public asset reads; not yet qualified."""
import hashlib
import io as byte_io
import re
import torch
from comfy_api.latest import io,sdk
from ._wan_catalogue import valid_catalogue_name
from .secure_tensor_nodes import _bound_payload

FORMAT='wan-nlf-torchscript-recipe-v1'
RECIPE_KEYS={'format','model_name','weights_sha256','warmup'}
MAX_ARCHIVE_BYTES=2*1024**3
RANGE_BYTES=8*1024**2


def validate_nlf_recipe(recipe):
    if (not isinstance(recipe,dict) or set(recipe)!=RECIPE_KEYS
            or recipe['format']!=FORMAT or not valid_catalogue_name(recipe['model_name'])
            or type(recipe['warmup']) is not bool or not isinstance(recipe['weights_sha256'],str)
            or re.fullmatch('[0-9a-f]{64}',recipe['weights_sha256']) is None):
        raise ValueError('Invalid digest-bound original NLF TorchScript recipe')


async def load_nlf_resource(nlf_model,warmup=True,*,expected_sha256=None,preserve_rng=False):
    if (not valid_catalogue_name(nlf_model) or not nlf_model.lower().endswith(('.torchscript','.pt','.pth'))
            or type(warmup) is not bool):
        raise ValueError('NLF requires a confined original TorchScript asset and Boolean warmup')
    from .secure_nlf_algorithms import check_jit_script_function,construct_nlf_from_stream
    check_jit_script_function()
    assets=sdk.current_context().assets
    # Keep the original catalogue visible. Current host catalogue admission is
    # a documented gate; never retarget an unrelated SCAIL safetensors model.
    asset=await assets.resolve('nlf',nlf_model)
    size=await assets.size(asset)
    if not 0<size<=MAX_ARCHIVE_BYTES:
        raise ValueError('NLF archive exceeds its bounded 2 GiB source domain')
    digest=await assets.digest(asset)
    if expected_sha256 is not None and digest!=expected_sha256:
        raise ValueError('NLF TorchScript changed after recipe creation')
    actual=hashlib.sha256()
    with byte_io.BytesIO() as stream:
        for offset in range(0,size,RANGE_BYTES):
            count=min(RANGE_BYTES,size-offset)
            chunk=await assets.read_range(asset,offset=offset,length=count)
            if not isinstance(chunk,bytes) or len(chunk)!=count:
                raise ValueError('NLF public asset range returned incomplete bytes')
            actual.update(chunk)
            stream.write(chunk)
        del chunk
        if actual.hexdigest()!=digest or await assets.digest(asset)!=digest:
            raise ValueError('NLF TorchScript changed during bounded public asset reads')
        stream.seek(0)
        with torch.random.fork_rng(devices=[],enabled=preserve_rng):
            model=construct_nlf_from_stream(stream,warmup)
    return model,{'format':FORMAT,'model_name':nlf_model,'weights_sha256':digest,'warmup':warmup}


async def rebuild_nlf_resource(recipe):
    validate_nlf_recipe(recipe)
    return await load_nlf_resource(recipe['model_name'],recipe['warmup'],
        expected_sha256=recipe['weights_sha256'],preserve_rng=True)


def preflight_nlf_images(images,per_batch):
    _bound_payload(images)
    if (not isinstance(images,torch.Tensor) or images.layout!=torch.strided
            or images.ndim!=4 or not 0<=images.shape[0]<=64
            or not all(1<=dimension<=1024 for dimension in images.shape[1:3])
            or images.shape[-1]!=3 or images.device.type!='cpu'):
        raise ValueError('NLF requires bounded dense CPU BHWC RGB images')
    if not isinstance(per_batch,int) or not -10000<=per_batch<=10000:
        raise ValueError('NLF per_batch exceeds its bounded integer domain')
    # Preserve native zero/negative batch behavior in predict_nlf_original.


class LoadNLFModel(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='LoadNLFModel',display_name='Load NLF Model',category='WanVideoWrapper',
            inputs=[io.Combo.Input('nlf_model',options=[],
                tooltip="These models are loaded from the 'ComfyUI/models/nlf' -folder",
                remote=io.RemoteOptions(route='/models/nlf',refresh_button=True,control_after_refresh='first')),
                io.Boolean.Input('warmup',default=True,optional=True,tooltip='Whether to warmup the model after loading')],
            outputs=[io.Custom('NLFMODEL').Output(display_name='nlf_model')])

    @classmethod
    def validate_inputs(cls,input_types=None,**kwargs):
        name=kwargs.get('nlf_model')
        return True if name is None or valid_catalogue_name(name) else 'NLF requires a confined logical catalogue name'

    @classmethod
    async def execute(cls,nlf_model,warmup=True):
        _,recipe=await load_nlf_resource(nlf_model,warmup)
        return io.NodeOutput(recipe)


class NLFPredict(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='NLFPredict',display_name='NLF Predict',category='WanVideoWrapper',
            inputs=[io.Custom('NLFMODEL').Input('model'),io.Image.Input('images',tooltip='Input images for the model'),
                io.Int.Input('per_batch',default=-1,min=-1,max=10000,step=1,optional=True,
                    tooltip='How many images to process at once. -1 means all at once.')],
            outputs=[io.Custom('NLFPRED').Output(display_name='pose_results'),io.Custom('BBOX').Output(display_name='bboxes')])

    @classmethod
    async def execute(cls,model,images,per_batch=-1):
        preflight_nlf_images(images,per_batch)
        resource,_=await rebuild_nlf_resource(model)
        from .secure_nlf_algorithms import predict_nlf_original
        with torch.inference_mode():
            results,boxes=predict_nlf_original(resource,images,per_batch)
        _bound_payload((results,boxes))
        return io.NodeOutput(results,boxes)


NODE_CLASS_MAPPINGS={'LoadNLFModel':LoadNLFModel,'NLFPredict':NLFPredict}
