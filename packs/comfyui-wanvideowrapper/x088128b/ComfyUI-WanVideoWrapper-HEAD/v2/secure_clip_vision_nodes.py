"""Complete Wan CLIP vision orchestration, pending trained-model qualification.

Custom Wan architecture remains pack-side. Canonical encoders stay opaque
ClipVisionRefs; their pending public token/offload primitives are explicit.
"""
import torch
from comfy_api.latest import io, sdk
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES
from .secure_vision_algorithms import encode_native_vision, _encode_tokens, split_tiles, merge_hiddenstates
from .secure_wan_clip_preprocess import clip_preprocess
from .secure_wan_clip_resource import rebuild_wan_clip


def check_images(images, tiles):
    _bound_payload(images)
    if (not isinstance(images, torch.Tensor) or images.device.type != 'cpu'
            or images.layout != torch.strided or images.ndim != 4
            or not 1 <= images.shape[0] <= 64 or min(images.shape[1:3]) < 1
            or images.shape[-1] not in (3, 4)):
        raise ValueError('Wan CLIP requires bounded dense CPU BHWC RGB/RGBA images')
    if type(tiles) is not int:
        raise ValueError('Wan CLIP tiles must be an integer')
    actual_tiles = min(tiles, 16)
    if actual_tiles > 1 and min(images.shape[1:3]) < actual_tiles:
        raise ValueError('Wan CLIP image tiles must be nonempty')
    projected_tokens = max(images.shape[0], actual_tiles**2 if actual_tiles > 1 else 1)*257*1280*4
    if projected_tokens*4 > MAX_PAYLOAD_BYTES:
        raise ValueError('Wan CLIP projected tokens exceed the bounded 64 MiB working domain')
    if images.numel()*images.element_size()*3 > MAX_PAYLOAD_BYTES:
        raise ValueError('Wan CLIP projected image work exceeds 64 MiB')


def combine_clip_embeddings(clip_embeds, strength_1, strength_2, combine_embeds):
    weighted_embeds = []
    weighted_embeds.append(clip_embeds[0:1] * strength_1)
    if clip_embeds.shape[0] > 1:
        weighted_embeds.append(clip_embeds[1:2] * strength_2)
        if clip_embeds.shape[0] > 2:
            for i in range(2, clip_embeds.shape[0]):
                weighted_embeds.append(clip_embeds[i:i+1])
        if combine_embeds == 'average':
            clip_embeds = torch.mean(torch.stack(weighted_embeds), dim=0)
        elif combine_embeds == 'sum':
            clip_embeds = torch.sum(torch.stack(weighted_embeds), dim=0)
        elif combine_embeds == 'concat':
            clip_embeds = torch.cat(weighted_embeds, dim=1)
        elif combine_embeds == 'batch':
            clip_embeds = torch.cat(weighted_embeds, dim=0)
    else:
        clip_embeds = weighted_embeds[0]
    return clip_embeds


def encode_wan_tiled(model, image, tiles=1, ratio=1.0):
    # Original helper always crops, independently of the node's crop widget.
    embeds = model.visual(clip_preprocess(image, size=224, crop=True).float())
    tiles = min(tiles, 16)
    if tiles > 1:
        image_split = split_tiles(image, tiles)
        embeds_split = {}
        for row in image_split:
            encoded = model.visual(clip_preprocess(row, size=224, crop=True).float())
            # Preserve original hasattr(dict,...) behavior: final row wins.
            if not hasattr(embeds_split, 'last_hidden_state'):
                embeds_split['last_hidden_state'] = encoded
            else:
                embeds_split['last_hidden_state'] = torch.cat(embeds_split['last_hidden_state'], encoded, dim=0)
        merged = merge_hiddenstates(embeds_split['last_hidden_state'], tiles)
        if embeds.shape[0] > 1:
            embeds = embeds*ratio + merged*(1-ratio)
        else:
            embeds = torch.cat([embeds*ratio, merged])
    return embeds


async def raw_image(image):
    return await image.raw() if isinstance(image, sdk.ImageRef) else image


async def encode_wan_vision(recipe, image_1, strength_1, strength_2, force_offload, crop, combine_embeds, image_2=None, negative_image=None, tiles=0, ratio=1.0):
    image_1 = await raw_image(image_1)
    image_2 = await raw_image(image_2) if image_2 is not None else None
    negative_image = await raw_image(negative_image) if negative_image is not None else None
    _bound_payload((image_1, image_2, negative_image))
    for value in (image_1, image_2, negative_image):
        if value is not None:
            check_images(value, tiles)
    image = torch.cat([image_1, image_2], dim=0) if image_2 is not None else image_1
    check_images(image, tiles)
    model, _ = await rebuild_wan_clip(recipe)
    with torch.inference_mode():
        if tiles > 0:
            clip_embeds = encode_wan_tiled(model, image, tiles, ratio)
            negative = encode_wan_tiled(model, negative_image, tiles, ratio) if negative_image is not None else None
        else:
            clip_embeds = model.visual(clip_preprocess(image, size=224, crop=(crop != 'disabled')).float())
            negative = model.visual(clip_preprocess(negative_image, size=224, crop=(crop != 'disabled')).float()) if negative_image is not None else None
        clip_embeds = combine_clip_embeddings(clip_embeds, strength_1, strength_2, combine_embeds)
    if force_offload:
        model.model.to(torch.device('cpu'))
    result = {'clip_embeds': clip_embeds, 'negative_clip_embeds': negative}
    _bound_payload(result)
    return result


class WanVideoClipVisionEncode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'assets', 'models', 'models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoClipVisionEncode', display_name='WanVideo ClipVision Encode', category='WanVideoWrapper',
            inputs=[io.Custom('CLIP_VISION').Input('clip_vision'), io.Image.Input('image_1', tooltip='Image to encode'),
                io.Float.Input('strength_1', default=1.0, min=0.0, max=10.0, step=0.001, tooltip='Additional clip embed multiplier'),
                io.Float.Input('strength_2', default=1.0, min=0.0, max=10.0, step=0.001, tooltip='Additional clip embed multiplier'),
                io.Combo.Input('crop', options=['center', 'disabled'], default='center', tooltip='Crop image to 224x224 before encoding'),
                io.Combo.Input('combine_embeds', options=['average', 'sum', 'concat', 'batch'], default='average', tooltip='Method to combine multiple clip embeds'),
                io.Boolean.Input('force_offload', default=True), io.Image.Input('image_2', optional=True),
                io.Image.Input('negative_image', optional=True, tooltip='image to use for uncond'),
                io.Int.Input('tiles', optional=True, default=0, min=0, max=16, step=2, tooltip="Use matteo's tiled image encoding for improved accuracy"),
                io.Float.Input('ratio', optional=True, default=0.5, min=0.0, max=1.0, step=0.01, tooltip='Ratio of the tile average')],
            outputs=[io.Custom('WANVIDIMAGE_CLIPEMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, clip_vision, image_1, strength_1, strength_2, force_offload, crop, combine_embeds, image_2=None, negative_image=None, tiles=0, ratio=1.0):
        arguments = dict(image_1=image_1, strength_1=strength_1, strength_2=strength_2,
            force_offload=force_offload, crop=crop, combine_embeds=combine_embeds,
            image_2=image_2, negative_image=negative_image, tiles=tiles, ratio=ratio)
        if isinstance(clip_vision, sdk.ClipVisionRef):
            result = await encode_native_vision(clip_vision, **arguments)
        else:
            result = await encode_wan_vision(clip_vision, **arguments)
        # Explicit-ref mode retains the canonical model handle on input. Its
        # numeric dictionary must also be published through the public raw API.
        return io.NodeOutput(await sdk.ValueRef.from_value(result))


NODE_CLASS_MAPPINGS = {'WanVideoClipVisionEncode': WanVideoClipVisionEncode}
