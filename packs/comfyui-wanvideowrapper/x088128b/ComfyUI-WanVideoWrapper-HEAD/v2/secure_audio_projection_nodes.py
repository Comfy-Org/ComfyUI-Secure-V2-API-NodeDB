"""Typed projection loaders; trained and main-consumer qualification pending.

FantasyTalking SafeTensors loading retains all keys internally. MultiTalk keeps
the original diffusion_models lookup and name-based InfiniteTalk discriminator.
The original ordered menu union is provided by web/wan_audio_model_menus.js;
actual browser/host execution and catalogue qualification remain open.
"""
from comfy_api.latest import io
from ._wan_catalogue import valid_catalogue_name
from .secure_audio_projection_runtime import load_fantasytalking, load_multitalk


class FantasyTalkingModelLoader(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FantasyTalkingModelLoader', display_name='FantasyTalking Model Loader', category='WanVideoWrapper',
            inputs=[io.Combo.Input('model', options=[], tooltip="These models are loaded from the 'ComfyUI/models/diffusion_models' -folder", remote=io.RemoteOptions(route='/models/diffusion_models', refresh_button=True, control_after_refresh='first')),
                    io.Combo.Input('base_precision', options=['fp32', 'bf16', 'fp16'], default='fp16')],
            outputs=[io.Custom('FANTASYTALKINGMODEL').Output(display_name='model')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model')
        return True if name is None or valid_catalogue_name(name) else 'Audio projection requires a confined diffusion_models catalogue name'

    @classmethod
    async def execute(cls, model, base_precision):
        materialized, recipe = await load_fantasytalking(model, base_precision)
        del materialized
        return io.NodeOutput(recipe)


class MultiTalkModelLoader(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'assets')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MultiTalkModelLoader', display_name='Multi/InfiniteTalk Model Loader', category='WanVideoWrapper',
            inputs=[io.Combo.Input('model', options=[], tooltip="These models are loaded from the 'ComfyUI/models/diffusion_models' -folder")],
            outputs=[io.Custom('MULTITALKMODEL').Output(display_name='model')])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get('model')
        return True if name is None or valid_catalogue_name(name) else 'Audio projection requires a confined diffusion_models catalogue name'

    @classmethod
    async def execute(cls, model, base_precision=None):
        materialized, recipe = await load_multitalk(model, base_precision)
        del materialized
        return io.NodeOutput(recipe)


NODE_CLASS_MAPPINGS = {'FantasyTalkingModelLoader': FantasyTalkingModelLoader, 'MultiTalkModelLoader': MultiTalkModelLoader}
