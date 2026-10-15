"""Pack-side Bindweave tensor math; no model/device/opaque materialization.

Raw is explicit and host-granted. Existing metadata handles are forwarded,
never resolved. 64 MiB is a conservative CPU fixture-work reserve, not a
physical memory/profile grant or trained sampling certification.
"""
import logging
import math
import torch
import torch.nn.functional as F
from comfy_api.latest import io, sdk
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES, MAX_TENSOR_ELEMENTS

log = logging.getLogger(__name__)


def _nearest_upscale(samples, width, height, upscale_method, crop):
    # Exact pinned common_upscale branch used here: nearest + disabled crop.
    assert upscale_method == 'nearest' and crop == 'disabled'
    orig_shape = tuple(samples.shape)
    if len(orig_shape) > 4:
        samples = samples.reshape(samples.shape[0], samples.shape[1], -1, samples.shape[-2], samples.shape[-1])
        samples = samples.movedim(2, 1)
        samples = samples.reshape(-1, orig_shape[1], orig_shape[-2], orig_shape[-1])
    out = F.interpolate(samples, size=(height, width), mode=upscale_method)
    if len(orig_shape) == 4:
        return out
    out = out.reshape((orig_shape[0], -1, orig_shape[1]) + (height, width))
    return out.movedim(2, 1).reshape(orig_shape[:-2] + (height, width))


def _preflight(embeds, reference_latents, ref_masks, qwenvl_embeds_pos, qwenvl_embeds_neg):
    # Only the field used by source contributes to LATENT compute admission;
    # ignored metadata is not recursively inspected even in direct CPU calls.
    latent_payload = {'samples':reference_latents.get('samples')} if isinstance(reference_latents,dict) else reference_latents
    _bound_payload((embeds, latent_payload, ref_masks, qwenvl_embeds_pos, qwenvl_embeds_neg))
    if not isinstance(embeds, dict) or not isinstance(reference_latents, dict):
        # Bounded native malformed mappings fail in the source body below.
        return
    image = embeds.get('image_embeds')
    refs = reference_latents.get('samples')
    mask = embeds.get('mask')
    context = embeds.get('clip_context')
    tensors = [x for x in (image, refs, mask, ref_masks, context) if isinstance(x, torch.Tensor)]
    for value in tensors:
        if value.layout != torch.strided or value.device.type not in ('cpu', 'meta'):
            raise ValueError('Wan Bindweave fixture math requires dense CPU tensors')
    # Lifetime upper bound: all source temporaries plus inputs and a second
    # final-output reserve for publication coexist conservatively. A view is
    # not charged as a new allocation; float-preview output is charged.
    total = sum(x.numel()*x.element_size() for x in tensors)
    def allocation(shape, dtype):
        nonlocal total
        if any(x < 0 for x in shape):
            return  # Source torch.zeros must raise its native negative-pad error.
        count = math.prod(shape)
        if count > MAX_TENSOR_ELEMENTS:
            raise ValueError('Wan Bindweave projected tensor exceeds 16777216 elements')
        total += count * dtype.itemsize
        if total > MAX_PAYLOAD_BYTES:
            raise ValueError('Wan Bindweave projected simultaneous work exceeds 64 MiB')
    if not (isinstance(image, torch.Tensor) and image.ndim >= 4
            and isinstance(refs, torch.Tensor) and refs.ndim >= 1):
        return
    R = refs.shape[0]
    if R > 4:
        return  # Native source negative pad occurs first, without allocation.
    c, t, h, w = image.shape[:4]
    allocation((c,4-R,h,w), image.dtype)
    if image.ndim != 4:
        return  # Source pad/cat has mismatched ranks; the pad is bounded above.
    padded = t + (4-R if R < 4 else 0)
    if R < 4:
        allocation((c,padded,h,w), image.dtype)
    if refs.ndim != 5:
        return  # Source reference slices cannot concatenate with a 4D image.
    _, C, L, H, W = refs.shape
    image_dtype = torch.promote_types(image.dtype,refs.dtype) if R else image.dtype
    final_t = padded + R*L
    allocation((c,final_t,h,w),image_dtype)
    allocation((c,final_t,h,w),image_dtype)  # published output reserve
    allocation((c,final_t,h,w),image_dtype)  # separately published LATENT view
    if isinstance(mask,torch.Tensor) and mask.ndim >= 4:
        mc,mt,mh,mw = mask.shape[:4]
        allocation((mc,4-R,mh,mw),mask.dtype)
        if mask.ndim != 4:
            if R == 4 and ref_masks is None:
                allocation((mc,R,mh,mw),mask.dtype)
            elif R == 4 and isinstance(ref_masks,torch.Tensor) and ref_masks.ndim >= 3:
                allocation((*ref_masks.shape[:-2],mh,mw),ref_masks.dtype)
                moved_shape = (1,ref_masks.shape[0],*ref_masks.shape[1:-2],mh,mw)
                allocation((3,*moved_shape[1:4]),ref_masks.dtype)
            return  # Native mismatched-rank cat, after bounded temporaries.
        padded_mt = mt + (4-R if R < 4 else 0)
        if R < 4:
            allocation((mc,padded_mt,mh,mw),mask.dtype)
        if ref_masks is None:
            allocation((mc,R,mh,mw),mask.dtype)
            mask_dtype = mask.dtype
            final_mt = padded_mt + R
        elif isinstance(ref_masks,torch.Tensor) and ref_masks.ndim == 3:
            n = ref_masks.shape[0]
            allocation((n,1,mh,mw),ref_masks.dtype)  # nearest-resize result
            allocation((3,n,mh,mw),ref_masks.dtype)
            ref_dtype = ref_masks.dtype
            allocation((4,n,mh,mw),ref_dtype)
            mask_dtype = torch.promote_types(mask.dtype,ref_dtype)
            final_mt = padded_mt+n
        else:
            if isinstance(ref_masks,torch.Tensor) and ref_masks.ndim > 3:
                allocation((*ref_masks.shape[:-2],mh,mw),ref_masks.dtype)
                # Source subsequently constructs this zero before its native
                # dimensionality-mismatched cat; still bound that allocation.
                allocation((3,ref_masks.shape[0],ref_masks.shape[1],mh),ref_masks.dtype)
            return  # Native malformed ref-mask interpolation/cat path.
        allocation((mc,final_mt,mh,mw),mask_dtype)
        allocation((mc,final_mt,mh,mw),mask_dtype)  # published embedded mask
        allocation((final_mt,mh,mw),torch.float32)  # float preview
        allocation((final_mt,mh,mw),torch.float32)  # published MASK
    if isinstance(context,torch.Tensor) and context.ndim == 3:
        B,T,D = context.shape
        if T < 1028:
            allocation((B,1028-T,D),context.dtype)
            allocation((B,1028,D),context.dtype)
            allocation((B,1028,D),context.dtype)  # publication reserve


def bindweave_math(embeds, reference_latents, ref_masks=None, qwenvl_embeds_pos=None, qwenvl_embeds_neg=None):
    _preflight(embeds, reference_latents, ref_masks, qwenvl_embeds_pos, qwenvl_embeds_neg)
    updated = dict(embeds)
    image_embeds = embeds["image_embeds"]
    max_refs = 4
    num_refs = reference_latents["samples"].shape[0]
    pad = torch.zeros(image_embeds.shape[0], max_refs-num_refs, image_embeds.shape[2], image_embeds.shape[3], device=image_embeds.device, dtype=image_embeds.dtype)
    if num_refs < max_refs:
        image_embeds = torch.cat([pad, image_embeds], dim=1)
    ref_latents = [ref_latent for ref_latent in reference_latents["samples"]]
    image_embeds = torch.cat([*ref_latents, image_embeds], dim=1)
    mask = embeds.get("mask", None)
    if mask is not None:
        mask_pad = torch.zeros(mask.shape[0], max_refs-num_refs, mask.shape[2], mask.shape[3], device=mask.device, dtype=mask.dtype)
        if num_refs < max_refs:
            mask = torch.cat([mask_pad, mask], dim=1)
        if ref_masks is not None:
            ref_mask_ = _nearest_upscale(ref_masks.unsqueeze(1), mask.shape[3], mask.shape[2], "nearest", "disabled").movedim(0,1)
            ref_mask_ = torch.cat([ref_mask_, torch.zeros(3, ref_mask_.shape[1], ref_mask_.shape[2], ref_mask_.shape[3], device=ref_mask_.device, dtype=ref_mask_.dtype)])
            mask = torch.cat([ref_mask_, mask], dim=1)
        else:
            mask = torch.cat([torch.ones(mask.shape[0], num_refs, mask.shape[2], mask.shape[3], device=mask.device, dtype=mask.dtype), mask], dim=1)
        updated["mask"] = mask
    clip_embeds = updated.get("clip_context", None)
    if clip_embeds is not None:
        B, T, C = clip_embeds.shape
        target_len = max_refs * 257
        if T < target_len:
            pad = torch.zeros(B, target_len - T, C, device=clip_embeds.device, dtype=clip_embeds.dtype)
            padded_embeds = torch.cat([clip_embeds, pad], dim=1)
            log.info(f"Padded clip embeds from {clip_embeds.shape} to {padded_embeds.shape} for Bindweave")
            updated["clip_context"] = padded_embeds
        else:
            updated["clip_context"] = clip_embeds
    updated["image_embeds"] = image_embeds
    updated["qwenvl_embeds_pos"] = qwenvl_embeds_pos
    updated["qwenvl_embeds_neg"] = qwenvl_embeds_neg
    return (updated, {"samples": image_embeds.unsqueeze(0)}, mask[0].float())


async def _tensor(value):
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value,sdk.Ref):
        raise TypeError('Wan Bindweave numeric fields require tensor refs, not engine objects')
    return value


class WanVideoAddBindweaveEmbeds(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw','inspect')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoAddBindweaveEmbeds', display_name='WanVideo Add Bindweave Embeds',category='WanVideoWrapper',
            inputs=[io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Latent.Input('reference_latents',tooltip='Reference image to encode'),
                io.Mask.Input('ref_masks',optional=True,tooltip='Reference mask to encode'),
                io.Custom('QWENVL_EMBEDS').Input('qwenvl_embeds_pos',optional=True,
                    tooltip='Qwen-VL image embeddings for the reference image'),
                io.Custom('QWENVL_EMBEDS').Input('qwenvl_embeds_neg',optional=True,
                    tooltip='Qwen-VL image embeddings for the reference image')],
            outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds'),
                io.Latent.Output(display_name='image_embed_preview'),io.Mask.Output(display_name='mask_preview')])

    @classmethod
    async def execute(cls, embeds, reference_latents, ref_masks=None, qwenvl_embeds_pos=None, qwenvl_embeds_neg=None):
        _bound_payload((embeds,ref_masks,qwenvl_embeds_pos,qwenvl_embeds_neg))
        if not isinstance(embeds,(dict,list,tuple,str,type(None),bool,int,float)):
            raise TypeError('Wan Bindweave embeds must be a bounded mapping, not an engine ref')
        prepared = dict(embeds) if isinstance(embeds,dict) else embeds
        original_context = embeds.get('clip_context') if isinstance(embeds,dict) else None
        # Only math fields are resolved; opaque and extra metadata stay handles.
        if isinstance(prepared,dict):
            for key in ('image_embeds','mask','clip_context'):
                if key in prepared:
                    prepared[key] = await _tensor(prepared[key])
        if isinstance(reference_latents,sdk.LatentRef):
            # Source reads only samples. Do not export or traverse unrelated
            # latent metadata, which may contain host-owned opaque objects.
            samples = await reference_latents.samples()
            description = await samples.describe()
            shape = description.get('shape')
            if (not isinstance(shape,list) or any(type(x) is not int or x < 0 for x in shape)):
                raise TypeError('Wan Bindweave samples require a bounded tensor shape')
            if math.prod(shape) > MAX_TENSOR_ELEMENTS:
                raise ValueError('Wan tensor input exceeds 16777216 elements')
            reference_latents = {'samples':await samples.raw()}
        elif isinstance(reference_latents,sdk.Ref):
            raise TypeError('Wan Bindweave references require LATENT, not an engine object')
        ref_masks = await _tensor(ref_masks)
        updated, latent, mask = bindweave_math(prepared,reference_latents,ref_masks,qwenvl_embeds_pos,qwenvl_embeds_neg)
        image_ref = await sdk.TensorRef.from_value(updated['image_embeds'])
        updated['image_embeds'] = image_ref
        if 'mask' in updated:
            updated['mask'] = await sdk.TensorRef.from_value(updated['mask'])
        if updated.get('clip_context') is not None:
            if updated['clip_context'] is prepared.get('clip_context') and isinstance(original_context,sdk.TensorRef):
                # Source does not replace an already-long context. Forward its
                # existing handle instead of copying or resolving any engine.
                updated['clip_context'] = original_context
            else:
                updated['clip_context'] = await sdk.TensorRef.from_value(updated['clip_context'])
        mask_ref = await sdk.MaskRef.from_value(mask)
        # LATENT preview is a view over the same final image storage in source.
        preview_ref = await sdk.TensorRef.from_value(latent['samples'])
        return io.NodeOutput(updated,{'samples':preview_ref},mask_ref)


NODE_CLASS_MAPPINGS = {'WanVideoAddBindweaveEmbeds':WanVideoAddBindweaveEmbeds}
