"""Eighteen-output user-ID draft; native images, logical library identities.

Main registration and authenticated authored-library/UI selection stay pending.
"""
from __future__ import annotations

from comfy_api.latest import io, sdk

from .secure_algorithms.metadata_recovery import parse_overrides, prepare_settings, finish_settings
from .secure_algorithms.bounds import bounded_json
from .secure_algorithms.core_sampling_names import SAMPLERS, SCHEDULERS
from .secure_services.image_metadata_source import read_image_source, MAX_AXIS, MAX_ENCODED, MAX_PIXELS
from .secure_services.metadata_catalogue import read_metadata_catalogue
from .secure_services.managed_library import _logical


async def _first_frame_mask(asset, expected_digest):
    """Core LoadImage's MASK for the first frame, from the same managed bytes as the pixels.

    Deployed core (6257422) LoadImage decodes with PyAV: a frame has alpha when its pixel format
    has an alpha component or is paletted (PNG tRNS applied), and the mask is 1 - alpha;
    otherwise it is a 64x64 zero mask. The deployed SDK's assets.load_image returns RGB pixels
    only (first frame, EXIF-transposed), so the mask is decoded here with the same orientation
    and returned through the SDK raw tier.
    """
    import hashlib
    from io import BytesIO

    import numpy as np
    import torch
    from PIL import Image, ImageOps

    size = await sdk.ctx().assets.size(asset)
    if type(size) is not int or not 0 < size <= MAX_ENCODED:
        raise ValueError('Encoded image exceeds the mask decode bound')
    data = await sdk.ctx().assets.read_range(asset, 0, size)
    if len(data) != size or hashlib.sha256(data).hexdigest() != expected_digest:
        raise ValueError('Image source changed during managed decoding')
    with Image.open(BytesIO(data)) as source:
        width, height = source.size
        if not 1 <= width <= MAX_AXIS or not 1 <= height <= MAX_AXIS or width * height > MAX_PIXELS:
            raise ValueError('Image geometry exceeds the mask decode bound')
        source.seek(0)
        frame = ImageOps.exif_transpose(source)
        if 'A' in frame.getbands():
            alpha = frame.getchannel('A')
        elif frame.mode == 'P' or 'transparency' in frame.info:
            alpha = frame.convert('RGBA').getchannel('A')
        else:
            alpha = None
        if alpha is None:
            mask = torch.zeros((64, 64), dtype=torch.float32)
        else:
            mask = 1.0 - torch.from_numpy(np.array(alpha, dtype=np.uint8)).float() / 255.0
    return await sdk.MaskRef._from_raw(mask.unsqueeze(0))


class LoadImageMetadata(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets', 'storage', 'raw')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Load Image Metadata (LoraManager)', category='Lora Manager/loaders',
            description='Load an image and recover prompts, LoRAs and sampling settings from its metadata. '
                'Connect lora_stack to Lora Loader. Convert loader/sampler widgets to inputs for the other outputs. '
                'Extraction failures use starter defaults and are shown as ERROR messages in readable_report.',
            inputs=[io.Combo.Input('image', options=[], upload=io.UploadType.image, image_folder=io.FolderType.input,
                remote=io.RemoteOptions(route='/secure-nodes/assets/input?kind=image', refresh_button=True)),
                io.String.Input('sampler_node_id', default='', tooltip='Leave empty for a single sampler. Subgraphs: use the full API ID, e.g. 1481:1783 (or 1481/1783). A container or leaf ID works only when unique.'),
                io.Combo.Input('missing_settings', options=['use_defaults', 'strict'], tooltip='Extraction errors always return defaults and an ERROR report, including for saved strict settings. Unresolved files are listed in missing_files.'),
                io.String.Input('overrides_json', default='{}', multiline=True, dynamic_prompts=False,
                    tooltip='Explicit replacements, e.g. {"scheduler":"normal", "model_name":"folder/model.safetensors"}. Use "loras": [] to clear the recovered stack.'),
                io.Boolean.Input('prefer_saved_image_metadata', default=True, tooltip='Prefer saved A1111-style generation parameters. Disable to select an active workflow sampler; muted/bypassed samplers are excluded.')],
            outputs=[io.Image.Output(display_name='image'), io.Mask.Output(display_name='mask'),
                io.String.Output(display_name='positive'), io.String.Output(display_name='negative'),
                io.AnyType.Output(display_name='model_name'), io.Custom('LORA_STACK').Output(display_name='lora_stack'),
                io.String.Output(display_name='lora_stack_text'), io.Int.Output(display_name='seed'),
                io.Int.Output(display_name='steps'), io.Float.Output(display_name='cfg'),
                io.AnyType.Output(display_name='sampler_name'), io.AnyType.Output(display_name='scheduler'),
                io.Int.Output(display_name='width'), io.Int.Output(display_name='height'),
                io.Float.Output(display_name='denoise'), io.String.Output(display_name='report'),
                io.String.Output(display_name='readable_report'), io.String.Output(display_name='missing_files')])

    @classmethod
    async def validate_inputs(cls, image, **kwargs):
        # Original VALIDATE_INPUTS(image, **kwargs): reject a missing image at queue time.
        # The remote image list has no static options, so core cannot check membership itself.
        # Annotated [input]/[output]/[temp] names are not supported by this conversion
        # (execute reads confined input names), so they are rejected here, not later.
        del kwargs
        try:
            name = _logical(image)
            exists = await sdk.ctx().assets.exists('input', name)
        except ValueError:
            exists = False
        if not exists:
            return f'Invalid image file: {image}'
        return True

    @classmethod
    async def fingerprint_inputs(cls, image, **kwargs):
        asset = await sdk.ctx().assets.resolve('input', _logical(image))
        return await sdk.ctx().assets.digest(asset)

    @classmethod
    async def execute(cls, image, sampler_node_id='', missing_settings='use_defaults',
                      overrides_json='{}', prefer_saved_image_metadata=True):
        # Preserve source policy/JSON errors before decoding, without admitting
        # arbitrary path selectors or swallowing resource/capability failures.
        bounded_json([sampler_node_id, missing_settings, overrides_json])
        parse_overrides(overrides_json)
        if missing_settings not in ('strict', 'use_defaults'):
            raise ValueError('Invalid missing_settings policy')
        name = _logical(image)
        asset = await sdk.ctx().assets.resolve('input', name)
        initial_digest = await sdk.ctx().assets.digest(asset)
        pixels = await sdk.ctx().assets.load_image(asset)
        mask = await _first_frame_mask(asset, initial_digest)
        height, width = await pixels.spatial_shape()
        # Metadata parsing uses managed bytes, not a second native pixel decoder.
        # Distinct broker reads are not an atomic filesystem snapshot; reject
        # detected changes rather than silently binding unrelated metadata.
        source = await read_image_source(name, interpret=False)
        if source['sha256'] != initial_digest or await sdk.ctx().assets.digest(asset) != initial_digest:
            raise ValueError('Image source changed during managed decoding')
        # The deployed SDK has no sampling catalogue: names are pinned to the deployed core and
        # tests/test_core_sampling_names.py fails if core's KSampler lists drift.
        prepared = prepare_settings(source['fields'], image_width=width, image_height=height,
            samplers=list(SAMPLERS), schedulers=list(SCHEDULERS),
            diagnostics='Managed input: ' + source['name'] + '; SHA256: ' + source['sha256'],
            sampler_node_id=sampler_node_id, missing_settings=missing_settings, overrides_json=overrides_json,
            prefer_saved_image_metadata=prefer_saved_image_metadata)
        try:
            catalogue = await read_metadata_catalogue()
            recovered = finish_settings(prepared, catalogue, name)
        except PermissionError:
            raise
        except (ValueError, TypeError, KeyError, OSError) as error:
            recovered = finish_settings(prepared, [], name, library_error=str(error))
        values = recovered['values']
        return io.NodeOutput(pixels, mask, values['positive'], values['negative'], values['model_name'],
            recovered['lora_stack'], recovered['lora_stack_text'], values['seed'], values['steps'],
            values['cfg'], values['sampler_name'], values['scheduler'], values['width'], values['height'],
            values['denoise'], recovered['report'], recovered['readable_report'], recovered['missing_files'])
