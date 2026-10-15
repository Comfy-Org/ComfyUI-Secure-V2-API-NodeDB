"""Typed native schemas for unfinished execution adapters.

These factories preserve native ports, controls and hidden inputs. They do not
register nodes, provide metadata/cache/hook authority, or qualify execution.
"""
from __future__ import annotations

from comfy_api.latest import io


def save_image_schema() -> io.Schema:
    return io.Schema(
        node_id='Save Image (LoraManager)',
        category='Lora Manager/utils',
        description='Save images with embedded generation metadata in compatible format',
        inputs=[io.Image.Input('images'), io.String.Input('filename_prefix', default='ComfyUI', tooltip='Base filename for saved images. Supports format patterns like %seed%, %width%, %height%, %model%, etc.'), io.Combo.Input('file_format', options=['png', 'jpeg', 'webp'], tooltip='Image format to save as. PNG preserves quality, JPEG is smaller, WebP balances size and quality.'), io.Boolean.Input('lossless_webp', default=False, tooltip='When enabled, saves WebP images with lossless compression. Results in larger files but no quality loss.', optional=True), io.Int.Input('quality', default=100, min=1, max=100, tooltip='Compression quality for JPEG and lossy WebP formats (1-100). Higher values mean better quality but larger files.', optional=True), io.Int.Input('webp_method', default=6, min=0, max=6, tooltip="WebP compression method (0-6). 0=fastest/largest, 6=slowest/smallest. Only applies when file_format is 'webp'.", optional=True), io.Int.Input('jpeg_subsampling', default=0, min=0, max=2, tooltip="JPEG chroma subsampling level. 0=4:4:4 (best quality), 1=4:2:2, 2=4:2:0 (smallest files). Only applies when file_format is 'jpeg'.", optional=True), io.Boolean.Input('embed_workflow', default=False, tooltip='When enabled, saved images store the complete workflow. Drag the image back into ComfyUI to restore the original node graph. PNG and WebP only.', optional=True), io.Boolean.Input('save_with_metadata', default=True, tooltip='When enabled, embeds generation parameters into the saved image metadata. Disable to skip writing generation metadata.', optional=True), io.Boolean.Input('add_loras_to_prompt', default=False, tooltip='When enabled, appends the LoRA syntax line (e.g. <lora:name:strength>) after the positive prompt in the saved metadata.', optional=True), io.Boolean.Input('add_counter_to_filename', default=True, tooltip='Adds an incremental counter to filenames to prevent overwriting previous images.', optional=True), io.Boolean.Input('save_as_recipe', default=False, tooltip='Also saves each generated image as a LoRA Manager recipe.', optional=True)],
        outputs=[io.Image.Output(display_name='images')],
        hidden=[io.Hidden.unique_id, io.Hidden.prompt, io.Hidden.extra_pnginfo],
        is_output_node=True
    )


def debug_metadata_schema() -> io.Schema:
    return io.Schema(
        node_id='Debug Metadata (LoraManager)',
        category='Lora Manager/utils',
        description='Debug node to verify metadata_processor functionality',
        inputs=[io.Image.Input('images')],
        outputs=[],
        hidden=[io.Hidden.unique_id],
        is_output_node=True
    )


def wan_widget_schema() -> io.Schema:
    return io.Schema(
        node_id='WanVideo Lora Select (LoraManager)',
        category='Lora Manager/stackers',
        inputs=[io.Boolean.Input('low_mem_load', default=False, tooltip='Load LORA models with less VRAM usage, slower loading. This affects ALL LoRAs, not just the current ones. No effect if merge_loras is False'), io.Boolean.Input('merge_loras', default=True, tooltip='Merge LoRAs into the model, otherwise they are loaded on the fly. Always disabled for GGUF and scaled fp8 models. This affects ALL LoRAs, not just the current one'), io.Custom('AUTOCOMPLETE_TEXT_LORAS').Input('text', tooltip='Format: <lora:lora_name:strength> separated by spaces or punctuation', extra_dict={'placeholder': 'Search LoRAs to add...'}), io.Custom('LORAS').Input('loras')],
        outputs=[io.Custom('WANVIDLORA').Output(display_name='lora'), io.String.Output(display_name='trigger_words'), io.String.Output(display_name='active_loras')],
        accept_all_inputs=True
    )


def wan_text_schema() -> io.Schema:
    return io.Schema(
        node_id='WanVideo Lora Select From Text (LoraManager)',
        category='Lora Manager/stackers',
        inputs=[io.Boolean.Input('low_mem_load', default=False, tooltip='Load LORA models with less VRAM usage, slower loading. This affects ALL LoRAs, not just the current ones. No effect if merge_loras is False'), io.Boolean.Input('merge_lora', default=True, tooltip='Merge LoRAs into the model, otherwise they are loaded on the fly. Always disabled for GGUF and scaled fp8 models. This affects ALL LoRAs, not just the current one'), io.String.Input('lora_syntax', multiline=True, force_input=True, tooltip='Connect a TEXT output for LoRA syntax: <lora:name:strength>'), io.Custom('WANVIDLORA').Input('prev_lora', optional=True), io.Custom('BLOCKS').Input('blocks', optional=True)],
        outputs=[io.Custom('WANVIDLORA').Output(display_name='lora'), io.String.Output(display_name='trigger_words'), io.String.Output(display_name='active_loras')]
    )


def create_hook_schema() -> io.Schema:
    return io.Schema(
        node_id='Create Hook LoRA (LoraManager)',
        category='Lora Manager/hooks',
        inputs=[io.Custom('AUTOCOMPLETE_TEXT_LORAS').Input('text', tooltip='Search and select LoRAs. Each LoRA gets its own model/clip strength. Hooks chain with prev_hooks.', extra_dict={'placeholder': 'Search LoRAs to add...'}), io.Custom('LORAS').Input('loras')],
        outputs=[io.Custom('HOOKS').Output(display_name='HOOKS'), io.String.Output(display_name='trigger_words'), io.String.Output(display_name='active_loras')],
        accept_all_inputs=True
    )
