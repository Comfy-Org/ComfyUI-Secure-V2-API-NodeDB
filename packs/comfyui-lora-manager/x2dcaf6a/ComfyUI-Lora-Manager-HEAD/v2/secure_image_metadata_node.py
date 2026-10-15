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
from .secure_services.image_names import managed_image_name
from .secure_services.image_pixels import load_managed_pixels


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
        # Preserve pinned input/output/temp annotations as managed identities.
        # The shared name boundary rejects paths outside those managed folders.
        del kwargs
        try:
            folder, name = managed_image_name(image)
            exists = await sdk.ctx().assets.exists(folder, name)
        except ValueError:
            exists = False
        if not exists:
            return f'Invalid image file: {image}'
        return True

    @classmethod
    async def fingerprint_inputs(cls, image, **kwargs):
        folder, name = managed_image_name(image)
        asset = await sdk.ctx().assets.resolve(folder, name)
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
        folder, name = managed_image_name(image)
        asset = await sdk.ctx().assets.resolve(folder, name)
        initial_digest = await sdk.ctx().assets.digest(asset)
        pixels, mask = await load_managed_pixels(asset, initial_digest)
        height, width = await pixels.spatial_shape()
        # Pixel and metadata parsing use digest-verified managed bytes.
        # Distinct broker reads are not an atomic filesystem snapshot; reject
        # detected changes rather than silently binding unrelated metadata.
        source = await read_image_source(name, interpret=False, folder=folder)
        if source['sha256'] != initial_digest or await sdk.ctx().assets.digest(asset) != initial_digest:
            raise ValueError('Image source changed during managed decoding')
        # The deployed SDK has no sampling catalogue: names are pinned to the deployed core and
        # tests/test_core_sampling_names.py fails if core's KSampler lists drift.
        prepared = prepare_settings(source['fields'], image_width=width, image_height=height,
            samplers=list(SAMPLERS), schedulers=list(SCHEDULERS),
            diagnostics='Managed ' + folder + ': ' + source['name'] + '; SHA256: ' + source['sha256'],
            sampler_node_id=sampler_node_id, missing_settings=missing_settings, overrides_json=overrides_json,
            prefer_saved_image_metadata=prefer_saved_image_metadata)
        try:
            catalogue = await read_metadata_catalogue()
            recovered = finish_settings(prepared, catalogue, image)
        except PermissionError:
            raise
        except (ValueError, TypeError, KeyError, OSError) as error:
            recovered = finish_settings(prepared, [], image, library_error=str(error))
        values = recovered['values']
        return io.NodeOutput(pixels, mask, values['positive'], values['negative'], values['model_name'],
            recovered['lora_stack'], recovered['lora_stack_text'], values['seed'], values['steps'],
            values['cfg'], values['sampler_name'], values['scheduler'], values['width'], values['height'],
            values['denoise'], recovered['report'], recovered['readable_report'], recovered['missing_files'])
