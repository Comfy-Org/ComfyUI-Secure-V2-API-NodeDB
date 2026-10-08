"""Typed model/conditioning operations; all fusion and crop algorithms pack-side."""
import math
import torch
from comfy_api.latest import io, sdk
from . import _math as equations
from ._loader_crop import LoaderCrop
from ._schema import schema

MAX_OUTPUT=128*1024*1024
MAX_OWNERSHIP=256*1024*1024
MAX_ROWS=4096
MAX_WORK=128_000_000

def budget(rows,feature,advanced=False,resolution=16,prompt=1.0,super_redux=False,mode='Mix',extra=0):
    """Before fusion allocation: snapshots, feature/reorder, FFT, cats, wire copies."""
    if not isinstance(feature,torch.Tensor) or feature.layout!=torch.strided:
        raise TypeError('Redux feature must be a dense tensor')
    base=feature.numel()*feature.element_size()+extra
    output=0;work=0
    if advanced:
        # Preserve nonsquare and rank errors in the literal source math rather
        # than invent a square or repair an eight-token StyleAdapter output.
        if feature.ndim!=3:return
        batch,tokens,channels=feature.shape
        side=int(math.sqrt(tokens))*resolution//16
        count=batch*side*side
    else:
        if feature.ndim<2:return
        count=feature.shape[0]*feature.shape[1]
        channels=feature.shape[-1]
    for tensor,_ in rows:
        if not isinstance(tensor,torch.Tensor) or tensor.layout!=torch.strided:
            raise TypeError('Redux conditioning embedding must be dense')
        base+=tensor.numel()*tensor.element_size()
        if tensor.ndim!=3:continue  # Source owns its exact native error.
        batch,txt_tokens,txt_channels=tensor.shape
        new_tokens=txt_tokens
        passes=2 if super_redux else 1
        for _ in range(passes):
            if advanced and prompt>1.0:new_tokens*=2
            new_tokens+=count
        element_size=max(tensor.element_size(),feature.element_size(),4 if mode=='FrequencyMix' else 0)
        row_output=batch*new_tokens*max(txt_channels,channels)*element_size
        output+=row_output
        work+=batch*new_tokens*max(txt_channels,channels)*passes
    # Frequency domain uses float32/complex64 fields regardless of incoming
    # half/bfloat16. No backing-store/temporary budget is inferred from target.
    field_elements=max(feature.numel(),count*channels) if advanced else feature.numel()
    temp=field_elements*max(feature.element_size(),4)*(24 if mode=='FrequencyMix' else 12)
    projected=base+temp+4*output
    if output>MAX_OUTPUT or projected>MAX_OWNERSHIP or work>MAX_WORK:
        raise ValueError('Redux projected snapshot/fusion/output/work ownership budget exceeded')
    return {'output_bytes':output,'projected_bytes':projected,'work':work}

async def raw_checked(ref,held=0):
    description=await ref.describe()
    shape=description['shape']
    if shape is None or len(shape)>32 or any(type(n) is not int or n<0 for n in shape):
        raise TypeError('Redux admitted dense tensor shape required')
    # Worst standard Torch dtype is16 bytes; before any guest import. Refine
    # using the actual owned buffer only after this conservative admission.
    if math.prod(shape)*16+held>MAX_OWNERSHIP:
        raise ValueError('Redux input snapshot ownership budget exceeded')
    value=await ref.raw()
    if value.numel()*value.element_size()+held>MAX_OWNERSHIP:
        raise ValueError('Redux input snapshot ownership budget exceeded')
    return value

async def embedding_rows(conditioning):
    rows=[];held=0
    length=(await conditioning.describe())['length']
    if type(length) is not int:
        raise TypeError('Redux admitted canonical CONDITIONING list or tuple required')
    if not 0<=length<=MAX_ROWS:raise ValueError('Redux conditioning row budget exceeded')
    for index in range(length):
        ref=await conditioning.embedding(index)
        value=await raw_checked(ref,held)
        held+=value.numel()*value.element_size()
        rows.append([value,{}])  # Opaque row metadata NEVER enters the guest.
    return rows

async def replace(conditioning,rows):
    embeddings=[await sdk.TensorRef.from_value(row[0]) for row in rows]
    return await conditioning.replace_embeddings(embeddings)

async def encode_retry(vision,image,crop=False):
    for attempt in range(2):
        try:return await vision.encode_image(image,crop=crop)
        except Exception:
            if attempt==1:raise

class ReduxFineTune(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','inspect')
    @classmethod
    def define_schema(cls):return schema('ReduxFineTune')
    @classmethod
    async def execute(cls,conditioning,style_model,clip_vision_output,fusion_mode='Mix',fusion_strength=1.0,SUPER_REDUX=False):
        rows=await embedding_rows(conditioning)
        with equations.rng_scope():
            for _ in range(2 if SUPER_REDUX else 1):
                feature=await raw_checked(await style_model.features(clip_vision_output),sum(t.numel()*t.element_size() for t,_ in rows))
                budget(rows,feature,super_redux=SUPER_REDUX,mode=fusion_mode)
                with torch.no_grad():rows=equations.basic_once(rows,feature,fusion_mode,fusion_strength)[0]
                del feature
        return io.NodeOutput(await replace(conditioning,rows),style_model,clip_vision_output)

class ReduxFineTuneAdvanced(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('raw','inspect')
    @classmethod
    def define_schema(cls):return schema('ReduxFineTuneAdvanced')
    @classmethod
    async def execute(cls,conditioning,style_model,clip_vision,image,crop='none',fusion_mode='Mix',style_strength=1.0,color_strength=0.0,content_strength=0.0,structure_strength=0.0,texture_strength=0.0,prompt_strength=1.0,feature_noise=0.0,feature_resolution=16,mask=None,SUPER_REDUX=False):
        if type(feature_resolution) is not int or not 1<=feature_resolution<=64:
            raise ValueError('Redux bounded feature resolution required')
        rows=await embedding_rows(conditioning)
        image_shape=(await image.describe())['shape']
        if image_shape is None or len(image_shape)!=4:
            raise TypeError('Redux admitted IMAGE must have BHWC shape')
        if math.prod(image_shape)*16>MAX_OUTPUT:
            raise ValueError('Redux image projection ownership budget exceeded')
        raw_image=None;raw_mask=None
        held=sum(t.numel()*t.element_size() for t,_ in rows)
        if mask is not None:raw_mask=await raw_checked(mask,held)
        if crop=='mask_area' and mask is not None:raw_image=await raw_checked(image,held+raw_mask.numel()*raw_mask.element_size())
        if raw_image is not None:
            # Source nonzero owns int64 coordinates before selecting views.
            # Include both crop publication copies and retained input snapshots.
            projected=held+3*raw_image.numel()*raw_image.element_size()+2*raw_mask.numel()*raw_mask.element_size()+17*raw_mask.numel()
            if projected>MAX_OWNERSHIP:raise ValueError('Redux mask-area crop ownership budget exceeded')
        async def processed():
            if crop=='mask_area' and mask is not None:
                pixels,cropped=equations.crop_math.crop_to_mask_area(raw_image,raw_mask)
                return await sdk.ImageRef.from_value(pixels),cropped
            return image,raw_mask
        strengths=[style_strength,color_strength,content_strength,structure_strength,texture_strength]
        extra=sum(x.numel()*x.element_size() for x in (raw_image,raw_mask) if x is not None)
        with equations.rng_scope():
            for index in range(2 if SUPER_REDUX else 1):
                processed_image,local_mask=await processed()
                vision=await encode_retry(clip_vision,processed_image,crop=='center')
                feature=await raw_checked(await style_model.features(vision),extra+sum(t.numel()*t.element_size() for t,_ in rows))
                budget(rows,feature,True,feature_resolution,prompt_strength,SUPER_REDUX,fusion_mode,extra)
                current=strengths if index==0 else [min(style_strength*1.2,2.0)]+[min(x*1.1,10.0) if x>0 else x for x in strengths[1:]]
                with torch.no_grad():rows=equations.advanced_once(rows,feature,fusion_mode,*current,prompt_strength,feature_noise,feature_resolution,local_mask)[0]
                del feature
        processed_image,local_mask=await processed()
        final_vision=await encode_retry(clip_vision,processed_image,crop=='center')
        if mask is None:
            elements=image_shape[1]*image_shape[2]
            if elements*torch.tensor(0.).element_size()>MAX_OUTPUT:raise ValueError('Redux default mask ownership budget exceeded')
            mask_output=await sdk.MaskRef.from_value(torch.zeros((1,image_shape[1],image_shape[2])))
        elif crop=='mask_area':mask_output=await sdk.MaskRef.from_value(local_mask)
        else:mask_output=mask
        return io.NodeOutput(await replace(conditioning,rows),style_model,final_vision,image,mask_output)

class ClipVisionStyleLoader(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('models','raw','inspect')
    @classmethod
    def define_schema(cls):return schema('ClipVisionStyleLoader')
    @classmethod
    async def execute(cls,clip_vision,style_model,image,crop_method,mask=None):
        vision=await sdk.ctx().models.load_clip_vision(clip_vision)
        if vision is None:raise Exception(f'CLIP Vision model {clip_vision} not found')
        style=await sdk.ctx().models.load_style_model(style_model)
        pixels=await raw_checked(image)
        cropper=LoaderCrop()
        crop_flag=False;cropped=pixels
        mask_pixels=None
        if crop_method=='mask' and mask is not None:
            mask_pixels=await raw_checked(mask,pixels.numel()*pixels.element_size())
        image_bytes=pixels.numel()*pixels.element_size()
        mask_bytes=0 if mask_pixels is None else mask_pixels.numel()*mask_pixels.element_size()
        resized_mask=0 if mask_pixels is None else mask_pixels.shape[0]*pixels.shape[1]*pixels.shape[2]*mask_pixels.element_size()
        coordinates=0 if mask_pixels is None else 17*pixels.shape[1]*pixels.shape[2]
        if 4*image_bytes+3*mask_bytes+4*resized_mask+coordinates>MAX_OWNERSHIP:
            raise ValueError('Redux loader crop/clone/publication ownership budget exceeded')
        if crop_method=='center':cropped=cropper.crop_center(pixels);crop_flag=True
        elif crop_method=='mask' and mask is not None:
            cropped=cropper.crop_mask(pixels,mask_pixels);crop_flag=True
        result_image=image if cropped is pixels else await sdk.ImageRef.from_value(cropped)
        clone=await sdk.ImageRef.from_value(cropped.clone())
        try:out=await vision.encode_image(clone,crop=crop_flag)
        except Exception:out=await vision.encode_image(clone)
        return io.NodeOutput([result_image],style,out)

NODE_CLASS_MAPPINGS={'ReduxFineTune':ReduxFineTune,'ReduxFineTuneAdvanced':ReduxFineTuneAdvanced,'ClipVisionStyleLoader':ClipVisionStyleLoader}
