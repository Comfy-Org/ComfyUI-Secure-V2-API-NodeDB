"""Wan model-control nodes bound to JACK's confined workflow context v1.

These nodes never load or materialize a model. The model producer validates
its resource descriptor; option nodes retain every other field unchanged
and perform only the pinned original option mutations.
"""
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from ._wan_model_control_options import (
    attention_override_options, block_swap_options, radial_options,
    ultravico_options,
)
from .wan_workflow_context import (
    MODEL_FORMAT, clone_model, model_options, original_attention_mode,
)

MODEL_CONTEXT_FORMAT = MODEL_FORMAT
ATTENTION_MODES = ['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn',
                   'sageattn_3', 'radial_sage_attention', 'sageattn_compiled',
                   'sageattn_ultravico', 'comfy']


def _options(model):
    _bound_payload(model)
    return model_options(model)


def _with_options(model, options):
    result = clone_model(model)
    # The pinned option algorithm supplies the output options. The shared
    # context clone preserves its resource and envelope identities.
    result['model_options'] = options
    _bound_payload(result)
    return io.NodeOutput(result)


def _attention_mode(model):
    return original_attention_mode(model)


class WanVideoSetBlockSwap(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSetBlockSwap', display_name='WanVideo Set BlockSwap',
            category='WanVideoWrapper', inputs=[
                io.Custom('WANVIDEOMODEL').Input('model'),
                io.Custom('BLOCKSWAPARGS').Input('block_swap_args', optional=True),
            ], outputs=[io.Custom('WANVIDEOMODEL').Output(display_name='model')])

    @classmethod
    def execute(cls, model, block_swap_args=None):
        if block_swap_args is None:
            return io.NodeOutput(model)
        return _with_options(model, block_swap_options(_options(model), block_swap_args))


class WanVideoSetAttentionModeOverride(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSetAttentionModeOverride',
            display_name='WanVideo Set Attention Mode Override', category='WanVideoWrapper',
            description='Override the attention mode for the model for specific step and/or block range',
            inputs=[
                io.Custom('WANVIDEOMODEL').Input('model'),
                io.Combo.Input('attention_mode', options=ATTENTION_MODES, default='sdpa'),
                io.Int.Input('start_step', default=0, min=0, max=10000, step=1,
                             tooltip='Step to start applying the attention mode override'),
                io.Int.Input('end_step', default=10000, min=1, max=10000, step=1,
                             tooltip='Step to end applying the attention mode override'),
                io.Boolean.Input('verbose', default=False,
                                 tooltip='Print verbose info about attention mode override during generation'),
                io.Int.Input('blocks', optional=True, force_input=True),
            ], outputs=[io.Custom('WANVIDEOMODEL').Output(display_name='model')])

    @classmethod
    def execute(cls, model, attention_mode, start_step, end_step, verbose, blocks=None):
        return _with_options(model, attention_override_options(
            _options(model), attention_mode, start_step, end_step, verbose, blocks))


class WanVideoUltraVicoSettings(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoUltraVicoSettings', display_name='WanVideo UltraVico Settings',
            category='WanVideoWrapper',
            description='Set UltraVico parameters, attention mode still needs to be set to sageattn_ultravico, https://github.com/thu-ml/DiT-Extrapolation',
            inputs=[
                io.Custom('WANVIDEOMODEL').Input('model'),
                io.Float.Input('alpha', default=0.9, min=0.0, max=1.0, step=0.001,
                               tooltip='Alpha value for the decay, higher values mean slower decay'),
            ], outputs=[io.Custom('WANVIDEOMODEL').Output(display_name='model')])

    @classmethod
    def execute(cls, model, alpha):
        return _with_options(model, ultravico_options(_options(model), alpha))


class WanVideoSetRadialAttention(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSetRadialAttention', display_name='WanVideo Set Radial Attention',
            category='WanVideoWrapper',
            description='Sets radial attention parameters, dense attention refers to normal attention',
            inputs=[
                io.Custom('WANVIDEOMODEL').Input('model'),
                io.Combo.Input('dense_attention_mode',
                               options=['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sparse_sage_attention'],
                               default='sageattn', tooltip='The attention mode for dense attention'),
                io.Int.Input('dense_blocks', default=1, min=0, max=40, step=1,
                             tooltip='Number of blocks to apply normal attention to'),
                io.Int.Input('dense_vace_blocks', default=1, min=0, max=15, step=1,
                             tooltip='Number of vace blocks to apply normal attention to'),
                io.Int.Input('dense_timesteps', default=2, min=0, max=100, step=1,
                             tooltip='The step to start applying sparse attention'),
                io.Float.Input('decay_factor', default=0.2, min=0, max=1, step=0.01,
                               tooltip='Controls how quickly the attention window shrinks as the distance between frames increases in the sparse attention mask.'),
                io.Combo.Input('block_size', options=[128, 64], default=128,
                               tooltip='Radial attention block size, larger blocks are faster but restricts usable dimensions more.'),
            ], outputs=[io.Custom('WANVIDEOMODEL').Output(display_name='model')])

    @classmethod
    def execute(cls, model, dense_attention_mode, dense_blocks, dense_vace_blocks,
                dense_timesteps, decay_factor, block_size):
        options = _options(model)
        return _with_options(model, radial_options(
            options, _attention_mode(model), dense_attention_mode, dense_blocks,
            dense_vace_blocks, dense_timesteps, decay_factor, block_size))


NODE_CLASS_MAPPINGS = {
    'WanVideoSetBlockSwap': WanVideoSetBlockSwap,
    'WanVideoSetAttentionModeOverride': WanVideoSetAttentionModeOverride,
    'WanVideoUltraVicoSettings': WanVideoUltraVicoSettings,
    'WanVideoSetRadialAttention': WanVideoSetRadialAttention,
}
