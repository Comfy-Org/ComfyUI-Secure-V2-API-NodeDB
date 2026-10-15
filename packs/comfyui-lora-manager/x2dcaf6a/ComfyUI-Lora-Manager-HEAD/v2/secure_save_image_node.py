"""Original Save IMAGE/UI bridge, pending native and installed qualification."""
from comfy_api.latest import io, sdk

from .native_metadata import metadata_processor
from .secure_remaining_schemas import save_image_schema
from .snapshot_metadata import from_snapshot
from .secure_services.image_save_body import save_image_body
from .secure_services.image_save_resources import read_save_resources
from .secure_services.image_result_body import image_result_body

metadata_processor.standalone_mode = False


class SaveImageLM(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('graph.metadata', 'assets', 'storage', 'raw', 'output')

    @classmethod
    def define_schema(cls):
        return save_image_schema()

    @classmethod
    async def execute(cls, images, filename_prefix='ComfyUI', file_format='png',
        lossless_webp=True, quality=100, webp_method=6, jpeg_subsampling=0,
        embed_workflow=False, save_with_metadata=True, add_counter_to_filename=True,
        save_as_recipe=False, add_loras_to_prompt=False, **kwargs):
        del kwargs
        snapshot = await sdk.current_context().graph.execution_metadata(include_observations=True)
        metadata = metadata_processor.MetadataProcessor.to_dict(from_snapshot(snapshot), snapshot['node_id'])
        resources = await read_save_resources(metadata)
        saved_ui = await save_image_body(images, filename_prefix=filename_prefix, file_format=file_format,
            metadata=metadata, resources=resources, workflow=snapshot['extra_pnginfo'],
            lossless_webp=lossless_webp, quality=quality, webp_method=webp_method,
            jpeg_subsampling=jpeg_subsampling, embed_workflow=embed_workflow,
            save_with_metadata=save_with_metadata, add_counter_to_filename=add_counter_to_filename,
            save_as_recipe=save_as_recipe, add_loras_to_prompt=add_loras_to_prompt)
        return await image_result_body(images, saved_ui)
